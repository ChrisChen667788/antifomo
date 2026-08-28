#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any
from urllib import request


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TMP_DIR = PROJECT_ROOT / ".tmp"
DEFAULT_API_BASE = "http://127.0.0.1:8000"
DEFAULT_CONFIG = TMP_DIR / "wechat_pc_agent_config.json"
AGENT_SCRIPT = PROJECT_ROOT / "scripts" / "wechat_pc_full_auto_agent.py"


def resolve_python() -> str:
    for candidate in [
        PROJECT_ROOT / "backend" / ".venv312" / "bin" / "python",
        PROJECT_ROOT / "backend" / ".venv" / "bin" / "python",
        PROJECT_ROOT / "backend" / ".venv311" / "bin" / "python",
    ]:
        if candidate.exists():
            return str(candidate)
    return sys.executable or "python3"


def call_json(api_base: str, path: str, *, method: str = "GET", timeout: float = 10.0) -> dict[str, Any]:
    req = request.Request(f"{api_base.rstrip('/')}{path}", method=method, headers={"Accept": "application/json"})
    if method != "GET":
        req.data = b"{}"
        req.add_header("Content-Type", "application/json")
    with request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
        parsed = json.loads(raw) if raw else {}
        return parsed if isinstance(parsed, dict) else {}


def read_json(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def int_metric(report: dict[str, Any], key: str) -> int:
    try:
        return max(0, int(report.get(key) or 0))
    except (TypeError, ValueError):
        return 0


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Force a non-destructive strict URL-path validation run for WeChat articles. "
            "Uses an isolated agent state file so processed_hashes from production runs do not skip URL extraction."
        )
    )
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--max-items", type=int, default=3)
    parser.add_argument("--start-batch-index", type=int, default=0)
    parser.add_argument("--min-url-paths", type=int, default=1)
    parser.add_argument("--max-ocr", type=int, default=0)
    parser.add_argument("--max-failed", type=int, default=0)
    parser.add_argument("--timeout-sec", type=int, default=600)
    parser.add_argument("--output-language", default="zh-CN")
    parser.add_argument("--tag", default="")
    parser.add_argument("--report", default=".tmp/force_url_path_batch_validate_latest.json")
    args = parser.parse_args()

    api_base = args.api_base.rstrip("/")
    max_items = max(1, min(int(args.max_items), 30))
    start_batch_index = max(0, min(int(args.start_batch_index), 1000))
    min_url_paths = max(1, min(int(args.min_url_paths), max_items))
    max_ocr = max(0, int(args.max_ocr))
    max_failed = max(0, int(args.max_failed))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tag = "".join(ch for ch in (args.tag or "") if ch.isalnum() or ch in ("-", "_"))[:40]
    suffix = f"{stamp}-{tag}" if tag else stamp
    run_dir = TMP_DIR / "strict-url-validation"
    state_file = run_dir / f"state-{suffix}.json"
    agent_report_file = run_dir / f"agent-report-{suffix}.json"
    summary_report_file = Path(args.report)
    archived_summary_report_file = run_dir / f"summary-{suffix}.json"

    try:
        health = call_json(api_base, "/healthz")
        if health.get("status") != "ok":
            raise RuntimeError(f"backend not healthy: {health}")
    except Exception as exc:  # noqa: BLE001
        payload = {"status": "error", "error": f"backend health failed: {exc}"}
        write_report(summary_report_file, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1

    # Avoid fighting a resident or previous run-once agent. This does not clear
    # production state; it only stops automation processes.
    call_json(api_base, "/api/collector/wechat-agent/stop", method="POST", timeout=30.0)

    run_dir.mkdir(parents=True, exist_ok=True)
    write_report(state_file, {"processed_hashes": {}, "runs": []})

    command = [
        resolve_python(),
        str(AGENT_SCRIPT),
        "--config",
        str(Path(args.config)),
        "--state-file",
        str(state_file),
        "--report-file",
        str(agent_report_file),
        "--max-items",
        str(max_items),
        "--start-batch-index",
        str(start_batch_index),
        "--output-language",
        args.output_language,
        "--api-base",
        api_base,
        "--strict-url-only",
    ]
    started_at = datetime.now(timezone.utc)
    completed = subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=max(60, int(args.timeout_sec)),
        check=False,
    )
    finished_at = datetime.now(timezone.utc)
    agent_report = read_json(agent_report_file)
    submitted_url = int_metric(agent_report, "submitted_url")
    dedup_url = int_metric(agent_report, "deduplicated_existing_url")
    tab_url = (
        int_metric(agent_report, "submitted_url_tab_copy_link")
        + int_metric(agent_report, "submitted_url_tab_browser_open")
        + int_metric(agent_report, "deduplicated_existing_url_tab_copy_link")
        + int_metric(agent_report, "deduplicated_existing_url_tab_browser_open")
    )
    ocr = int_metric(agent_report, "submitted_ocr") + int_metric(agent_report, "deduplicated_existing_ocr")
    failed = int_metric(agent_report, "failed")
    url_path_total = submitted_url + dedup_url
    assertions = {
        "processExitedZero": completed.returncode == 0,
        "urlPathThresholdMet": url_path_total >= min_url_paths,
        "tabRouteObserved": tab_url >= min_url_paths,
        "ocrWithinLimit": ocr <= max_ocr,
        "failedWithinLimit": failed <= max_failed,
    }
    failed_assertions = [key for key, ok in assertions.items() if not ok]
    payload = {
        "status": "passed" if not failed_assertions else "failed",
        "generatedAt": finished_at.isoformat(),
        "startedAt": started_at.isoformat(),
        "durationSec": round((finished_at - started_at).total_seconds(), 2),
        "apiBase": api_base,
        "command": command,
        "returnCode": completed.returncode,
        "stdoutTail": completed.stdout[-4000:],
        "isolatedStateFile": str(state_file),
        "agentReportFile": str(agent_report_file),
        "summaryArchiveFile": str(archived_summary_report_file),
        "thresholds": {
            "maxItems": max_items,
            "startBatchIndex": start_batch_index,
            "minUrlPaths": min_url_paths,
            "maxOcr": max_ocr,
            "maxFailed": max_failed,
        },
        "metrics": {
            "submitted": int_metric(agent_report, "submitted"),
            "submitted_new": int_metric(agent_report, "submitted_new"),
            "submitted_url": submitted_url,
            "deduplicated_existing": int_metric(agent_report, "deduplicated_existing"),
            "deduplicated_existing_url": dedup_url,
            "url_path_total": url_path_total,
            "tab_url_path_total": tab_url,
            "submitted_ocr": int_metric(agent_report, "submitted_ocr"),
            "deduplicated_existing_ocr": int_metric(agent_report, "deduplicated_existing_ocr"),
            "skipped_seen": int_metric(agent_report, "skipped_seen"),
            "skipped_invalid_article": int_metric(agent_report, "skipped_invalid_article"),
            "failed": failed,
            "validation_retries": int_metric(agent_report, "validation_retries"),
            "recovery_action_count": int_metric(agent_report, "recovery_action_count"),
            "duplicate_escape_count": int_metric(agent_report, "duplicate_escape_count"),
        },
        "assertions": assertions,
        "failedAssertions": failed_assertions,
        "agentReport": agent_report,
    }
    write_report(summary_report_file, payload)
    write_report(archived_summary_report_file, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
