#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    ".codex-project",
    ".git",
    ".next",
    ".pytest_cache",
    ".storage",
    ".tmp",
    ".venv",
    ".venv311",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "out",
}
EXCLUDED_SUFFIXES = {
    ".db",
    ".db-shm",
    ".db-wal",
    ".gz",
    ".ico",
    ".jpg",
    ".jpeg",
    ".lockb",
    ".pdf",
    ".png",
    ".pyc",
    ".sqlite",
    ".webp",
    ".zip",
}


@dataclass(frozen=True)
class SecretPattern:
    name: str
    regex: re.Pattern[str]


PATTERNS = [
    SecretPattern("openai_api_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    SecretPattern("anthropic_api_key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    SecretPattern("github_token", re.compile(r"\bgh[opsru]_[A-Za-z0-9_]{20,}\b")),
    SecretPattern("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    SecretPattern("wechat_app_id", re.compile(r"\bwx[0-9a-fA-F]{16,32}\b")),
    SecretPattern(
        "private_key_block",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ),
    SecretPattern(
        "generic_secret_assignment",
        re.compile(
            r"""(?ix)
            \b(?:api[_-]?key|app[_-]?secret|client[_-]?secret|secret|token|password|
            bearer[_-]?token|access[_-]?token|refresh[_-]?token)\b
            ["']?\s*[:=]\s*["']?
            ([A-Za-z0-9_./+=:@-]{16,})
            """
        ),
    ),
]


def run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)


def is_placeholder(value: str) -> bool:
    lowered = value.strip().strip("\"'").lower()
    if not lowered:
        return True
    if re.fullmatch(r"[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)+(?:\(\))?", lowered):
        return True
    if any(token in lowered for token in (".get", ".strip", ".rstrip", ".split", "settings.", "row.", "self.", "source_")):
        return True
    placeholder_tokens = (
        "...",
        "<",
        ">",
        "changeme",
        "example",
        "placeholder",
        "touristappid",
        "your",
        "your_",
    )
    if lowered.startswith(("$", "${")):
        return True
    return any(token in lowered for token in placeholder_tokens)


def mask(value: str) -> str:
    clean = value.strip().strip("\"',")
    if len(clean) <= 8:
        return "<masked>"
    return f"{clean[:4]}...{clean[-4:]}"


def scan_line(line: str) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    for pattern in PATTERNS:
        for match in pattern.regex.finditer(line):
            value = match.group(1) if pattern.name == "generic_secret_assignment" else match.group(0)
            if is_placeholder(value):
                continue
            findings.append((pattern.name, mask(value)))
    return findings


def should_skip_path(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDED_DIRS:
        return True
    if any(part.startswith(".venv") for part in path.parts):
        return True
    return path.suffix.lower() in EXCLUDED_SUFFIXES


def tracked_and_untracked_files() -> list[Path]:
    result = run_git(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"])
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        return []
    files = []
    for raw in result.stdout.split("\0"):
        if not raw:
            continue
        path = Path(raw)
        if not should_skip_path(path):
            files.append(path)
    return files


def filesystem_files() -> Iterable[Path]:
    for current_root, dirs, files in os.walk(ROOT):
        rel_root = Path(current_root).relative_to(ROOT)
        dirs[:] = [name for name in dirs if name not in EXCLUDED_DIRS]
        if should_skip_path(rel_root):
            continue
        for name in files:
            path = rel_root / name
            if not should_skip_path(path):
                yield path


def scan_file(path: Path) -> list[str]:
    full_path = ROOT / path
    try:
        data = full_path.read_bytes()
    except OSError as exc:
        return [f"{path}:0 read_error <{exc.__class__.__name__}>"]
    if b"\0" in data:
        return []
    text = data.decode("utf-8", errors="ignore")
    results = []
    for line_no, line in enumerate(text.splitlines(), 1):
        for name, masked_value in scan_line(line):
            results.append(f"{path}:{line_no} {name} {masked_value}")
    return results


def scan_worktree(include_ignored_local: bool) -> list[str]:
    files = filesystem_files() if include_ignored_local else tracked_and_untracked_files()
    results: list[str] = []
    for path in files:
        results.extend(scan_file(path))
    return results


def scan_history() -> list[str]:
    combined = (
        r"sk-(proj-)?[A-Za-z0-9_-]{20,}|"
        r"sk-ant-[A-Za-z0-9_-]{20,}|"
        r"gh[opsru]_[A-Za-z0-9_]{20,}|"
        r"(AKIA|ASIA)[0-9A-Z]{16}|"
        r"wx[0-9a-fA-F]{16,32}|"
        r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
    )
    revisions = run_git(["git", "rev-list", "--all"])
    if revisions.returncode != 0:
        print(revisions.stderr.strip(), file=sys.stderr)
        return []
    commits = [line.strip() for line in revisions.stdout.splitlines() if line.strip()]
    results: list[str] = []
    for start in range(0, len(commits), 50):
        chunk = commits[start : start + 50]
        grep = run_git(["git", "grep", "-I", "-n", "-E", combined, *chunk])
        if grep.returncode not in (0, 1):
            print(grep.stderr.strip(), file=sys.stderr)
            return ["history_scan_error:0 scanner_error <git grep failed>"]
        for raw in grep.stdout.splitlines():
            commit, sep, rest = raw.partition(":")
            if not sep:
                continue
            path, sep, line_and_text = rest.partition(":")
            if not sep:
                continue
            line_no, sep, text = line_and_text.partition(":")
            if not sep:
                continue
            for name, masked_value in scan_line(text):
                rel_path = Path(path)
                if should_skip_path(rel_path):
                    continue
                results.append(f"{commit[:12]}:{path}:{line_no} {name} {masked_value}")
    return sorted(set(results))


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan the repository for likely secrets without printing raw values.")
    parser.add_argument("--history", action="store_true", help="also scan committed Git history")
    parser.add_argument(
        "--include-ignored-local",
        action="store_true",
        help="include ignored local files such as .env and project.private.config.json",
    )
    parser.add_argument("--report-only", action="store_true", help="always exit 0 after reporting findings")
    args = parser.parse_args()

    findings = scan_worktree(include_ignored_local=args.include_ignored_local)
    if args.history:
        findings.extend(scan_history())

    findings = sorted(set(findings))
    if not findings:
        print("No likely secrets found.")
        return 0

    print("Likely secrets found:")
    for finding in findings:
        print(f"- {finding}")
    return 0 if args.report_only else 1


if __name__ == "__main__":
    raise SystemExit(main())
