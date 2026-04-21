#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import plistlib
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LABEL = "com.antifomo.watchlists"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
STATE_FILE = PROJECT_ROOT / ".tmp" / "watchlist_scheduler.last.json"
LOG_FILE = PROJECT_ROOT / ".tmp" / "watchlist_scheduler.log"
RUNNER = PROJECT_ROOT / "scripts" / "run_research_watchlists.py"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install or inspect the local AntiFomo watchlist launch agent.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install = subparsers.add_parser("install", help="Install and load the local watchlist scheduler")
    install.add_argument("--interval-seconds", type=int, default=3600, help="launchd StartInterval in seconds")
    install.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL")
    install.add_argument("--limit", type=int, default=6, help="Max due watchlists per run")
    install.add_argument("--output-language", default="zh-CN", help="Research output language")
    install.add_argument("--max-sources", type=int, default=12, help="Max sources per watchlist refresh")
    install.add_argument("--without-wechat", action="store_true", help="Skip WeChat sources")
    install.add_argument("--no-save", action="store_true", help="Do not save generated reports")
    install.add_argument("--notify", action="store_true", help="Send macOS notifications for refreshed/failed runs")
    install.add_argument("--python", default="", help="Explicit Python executable for the launch agent")

    subparsers.add_parser("uninstall", help="Unload and remove the local watchlist scheduler")
    subparsers.add_parser("status", help="Show launch agent status")
    return parser


def _python_executable(explicit: str) -> str:
    if explicit:
        return explicit
    candidates = [
        PROJECT_ROOT / "backend" / ".venv311" / "bin" / "python",
        PROJECT_ROOT / "backend" / ".venv" / "bin" / "python",
        Path(sys.executable),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    return sys.executable


def _launchctl(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False, timeout=12)


def _load_agent() -> str:
    uid = os.getuid()
    bootstrap = _launchctl(["launchctl", "bootstrap", f"gui/{uid}", str(PLIST_PATH)])
    if bootstrap.returncode == 0:
        return "launchctl bootstrap"
    legacy = _launchctl(["launchctl", "load", "-w", str(PLIST_PATH)])
    if legacy.returncode == 0:
        return "launchctl load -w"
    stderr = (bootstrap.stderr or legacy.stderr or bootstrap.stdout or legacy.stdout).strip()
    raise RuntimeError(stderr or "failed to load launch agent")


def _unload_agent() -> str:
    uid = os.getuid()
    bootout = _launchctl(["launchctl", "bootout", f"gui/{uid}", str(PLIST_PATH)])
    if bootout.returncode == 0:
        return "launchctl bootout"
    legacy = _launchctl(["launchctl", "unload", "-w", str(PLIST_PATH)])
    if legacy.returncode == 0:
        return "launchctl unload -w"
    stderr = (bootout.stderr or legacy.stderr or bootout.stdout or legacy.stdout).strip()
    if "No such process" in stderr or "Could not find specified service" in stderr:
        return "already unloaded"
    raise RuntimeError(stderr or "failed to unload launch agent")


def install_agent(args: argparse.Namespace) -> int:
    python_exec = _python_executable(args.python)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    arguments = [
        python_exec,
        str(RUNNER),
        "--base-url",
        args.base_url,
        "--limit",
        str(max(1, min(args.limit, 12))),
        "--output-language",
        args.output_language,
        "--max-sources",
        str(max(6, min(args.max_sources, 24))),
        "--state-file",
        str(STATE_FILE),
    ]
    if args.without_wechat:
        arguments.append("--without-wechat")
    if args.no_save:
        arguments.append("--no-save")
    if args.notify:
        arguments.append("--notify")

    payload = {
        "Label": LABEL,
        "ProgramArguments": arguments,
        "RunAtLoad": True,
        "StartInterval": max(300, int(args.interval_seconds)),
        "WorkingDirectory": str(PROJECT_ROOT),
        "StandardOutPath": str(LOG_FILE),
        "StandardErrorPath": str(LOG_FILE),
    }
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PLIST_PATH.open("wb") as handle:
        plistlib.dump(payload, handle, sort_keys=True)
    try:
        _unload_agent()
    except Exception:
        pass
    action = _load_agent()
    print(json.dumps({"installed": True, "loaded_via": action, "plist_path": str(PLIST_PATH)}, ensure_ascii=False))
    return 0


def uninstall_agent() -> int:
    if PLIST_PATH.exists():
        try:
            action = _unload_agent()
        except Exception as exc:
            print(json.dumps({"installed": True, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 1
        PLIST_PATH.unlink(missing_ok=True)
        print(json.dumps({"installed": False, "action": action, "plist_path": str(PLIST_PATH)}, ensure_ascii=False))
        return 0
    print(json.dumps({"installed": False, "plist_path": str(PLIST_PATH)}, ensure_ascii=False))
    return 0


def status_agent() -> int:
    state = {}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    loaded = _launchctl(["launchctl", "list", LABEL]).returncode == 0
    interval_seconds = 0
    if PLIST_PATH.exists():
        try:
            with PLIST_PATH.open("rb") as handle:
                interval_seconds = int(plistlib.load(handle).get("StartInterval") or 0)
        except Exception:
            interval_seconds = 0
    print(
        json.dumps(
            {
                "installed": PLIST_PATH.exists(),
                "loaded": loaded,
                "interval_seconds": interval_seconds,
                "plist_path": str(PLIST_PATH),
                "state_path": str(STATE_FILE),
                "log_path": str(LOG_FILE),
                "last_state": state if isinstance(state, dict) else {},
            },
            ensure_ascii=False,
        )
    )
    return 0


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "install":
        return install_agent(args)
    if args.command == "uninstall":
        return uninstall_agent()
    return status_agent()


if __name__ == "__main__":
    raise SystemExit(main())
