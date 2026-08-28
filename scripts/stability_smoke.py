#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from typing import Any
from urllib import error, request


DEFAULT_API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000").rstrip("/")


@dataclass
class SmokeResult:
    label: str
    method: str
    path: str
    ok: bool
    status: int | None = None
    elapsed_ms: int | None = None
    error: str | None = None


def call_api(api_base: str, method: str, path: str, *, payload: dict[str, Any] | None = None, timeout: float = 10.0) -> tuple[int, Any, int]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    started = time.perf_counter()
    req = request.Request(f"{api_base}{path}", data=body, headers=headers, method=method)
    with request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        parsed = json.loads(raw) if raw else None
        return response.status, parsed, elapsed_ms


def run_check(
    results: list[SmokeResult],
    api_base: str,
    label: str,
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: float,
) -> Any:
    try:
        status, parsed, elapsed_ms = call_api(api_base, method, path, payload=payload, timeout=timeout)
        ok = 200 <= status < 400
        results.append(SmokeResult(label=label, method=method, path=path, ok=ok, status=status, elapsed_ms=elapsed_ms))
        if not ok:
            raise RuntimeError(f"{label} returned HTTP {status}")
        return parsed
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        results.append(SmokeResult(label=label, method=method, path=path, ok=False, status=exc.code, error=body[:500]))
        raise
    except Exception as exc:
        results.append(SmokeResult(label=label, method=method, path=path, ok=False, error=str(exc)))
        raise


def run_read_checks(results: list[SmokeResult], api_base: str, *, timeout: float) -> None:
    checks = [
        ("system health", "GET", "/healthz"),
        ("feed items", "GET", "/api/items?limit=5"),
        ("knowledge list", "GET", "/api/knowledge?limit=5"),
        ("knowledge dashboard", "GET", "/api/knowledge/dashboard"),
        ("knowledge accounts", "GET", "/api/knowledge/accounts"),
        ("collector status", "GET", "/api/collector/status"),
        ("collector daily summary", "GET", "/api/collector/daily-summary?hours=24&limit=3"),
        ("research source settings", "GET", "/api/research/source-settings"),
        ("research workspace", "GET", "/api/research/workspace"),
        ("research retrieval status", "GET", "/api/research/retrieval-index/status"),
        ("research watchlists", "GET", "/api/research/watchlists"),
    ]
    for label, method, path in checks:
        run_check(results, api_base, label, method, path, timeout=timeout)


def run_write_checks(results: list[SmokeResult], api_base: str, *, timeout: float) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    topic = run_check(
        results,
        api_base,
        "create research topic",
        "POST",
        "/api/research/workspace/topics",
        timeout=timeout,
        payload={
            "name": f"稳定性基准专题 {stamp}",
            "keyword": "2026 上海 AI 商机",
            "research_focus": "预算、甲方、落地场景",
            "perspective": "bidding",
            "region_filter": "上海",
            "industry_filter": "AI",
            "notes": "live stability smoke",
        },
    )
    topic_id = topic["id"]
    run_check(results, api_base, "topic versions", "GET", f"/api/research/workspace/topics/{topic_id}/versions", timeout=timeout)
    run_check(results, api_base, "topic timeline", "GET", f"/api/research/workspace/topics/{topic_id}/timeline", timeout=timeout)

    watchlist = run_check(
        results,
        api_base,
        "create research watchlist",
        "POST",
        "/api/research/watchlists",
        timeout=timeout,
        payload={
            "name": f"稳定性基准监控 {stamp}",
            "query": "2026 上海 AI 商机",
            "tracking_topic_id": topic_id,
            "research_focus": "预算、甲方、落地场景",
            "perspective": "bidding",
            "region_filter": "上海",
            "industry_filter": "AI",
            "alert_level": "medium",
            "schedule": "manual",
        },
    )
    run_check(results, api_base, "watchlist changes", "GET", f"/api/research/watchlists/{watchlist['id']}/changes", timeout=timeout)

    session = run_check(
        results,
        api_base,
        "start focus session",
        "POST",
        "/api/sessions/start",
        timeout=timeout,
        payload={"goal_text": "稳定性基准测试", "duration_minutes": 25, "output_language": "zh-CN"},
    )
    session_id = session["id"]
    run_check(results, api_base, "latest focus session", "GET", "/api/sessions/latest", timeout=timeout)
    run_check(results, api_base, "pause focus session", "POST", f"/api/sessions/{session_id}/pause", timeout=timeout)
    run_check(results, api_base, "resume focus session", "POST", f"/api/sessions/{session_id}/resume", timeout=timeout)


def write_report(
    report_path: str | None,
    *,
    api_base: str,
    results: list[SmokeResult],
    status: str,
    max_elapsed_ms: int,
) -> None:
    if not report_path:
        return
    slow_results = [
        asdict(item)
        for item in results
        if item.ok and item.elapsed_ms is not None and item.elapsed_ms > max_elapsed_ms
    ]
    report = {
        "status": status,
        "apiBase": api_base,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "passed": sum(1 for item in results if item.ok),
        "failed": sum(1 for item in results if not item.ok),
        "thresholds": {"maxElapsedMs": max_elapsed_ms},
        "slow": len(slow_results),
        "slowResults": slow_results,
        "results": [asdict(item) for item in results],
    }
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Live API stability smoke test for Anti-FOMO.")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument(
        "--include-write",
        action="store_true",
        help="Also run small write-path checks against the live database. Default is read-only.",
    )
    parser.add_argument(
        "--max-elapsed-ms",
        type=int,
        default=5000,
        help="Fail if any checked endpoint exceeds this elapsed-time budget.",
    )
    parser.add_argument("--report", default=".tmp/stability_smoke_report.json")
    args = parser.parse_args()

    api_base = args.api_base.rstrip("/")
    results: list[SmokeResult] = []
    status = "failed"
    try:
        run_read_checks(results, api_base, timeout=args.timeout)
        if args.include_write:
            run_write_checks(results, api_base, timeout=args.timeout)
        slow_results = [
            item
            for item in results
            if item.ok and item.elapsed_ms is not None and item.elapsed_ms > max(1, args.max_elapsed_ms)
        ]
        if slow_results:
            labels = ", ".join(f"{item.label}={item.elapsed_ms}ms" for item in slow_results[:5])
            raise RuntimeError(f"slow endpoint budget exceeded: {labels}")
        status = "passed"
    except Exception as exc:
        print(f"[stability-smoke] failed: {exc}", file=sys.stderr)
    finally:
        write_report(
            args.report,
            api_base=api_base,
            results=results,
            status=status,
            max_elapsed_ms=max(1, args.max_elapsed_ms),
        )

    for item in results:
        mark = "PASS" if item.ok else "FAIL"
        elapsed = f" {item.elapsed_ms}ms" if item.elapsed_ms is not None else ""
        detail = f" [{item.status}]" if item.status is not None else ""
        print(f"{mark} {item.label} {item.method} {item.path}{detail}{elapsed}")

    if status != "passed":
        print(f"Report: {args.report}", file=sys.stderr)
        return 1
    print(f"Stability smoke passed. Report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
