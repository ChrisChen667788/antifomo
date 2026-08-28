#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import statistics
import time
from typing import Any
from urllib import error, request


DEFAULT_API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000").rstrip("/")
DEFAULT_ENDPOINTS = [
    ("health", "GET", "/healthz"),
    ("items", "GET", "/api/items?limit=20"),
    ("collector status", "GET", "/api/collector/status"),
    ("collector daemon", "GET", "/api/collector/daemon/status"),
    ("wechat agent", "GET", "/api/collector/wechat-agent/status"),
    ("wechat batch", "GET", "/api/collector/wechat-agent/batch-status"),
    ("knowledge dashboard", "GET", "/api/knowledge/dashboard"),
    ("knowledge accounts", "GET", "/api/knowledge/accounts"),
    ("research workspace", "GET", "/api/research/workspace"),
    ("research watchlists", "GET", "/api/research/watchlists"),
    ("research retrieval", "GET", "/api/research/retrieval-index/status"),
    ("decision studio overview", "GET", "/api/decision-studio/overview"),
    ("decision studio release", "GET", "/api/decision-studio/release-program"),
]


@dataclass
class ConcurrencyResult:
    label: str
    method: str
    path: str
    ok: bool
    status: int | None
    elapsed_ms: int
    error: str | None = None


def percentile(values: list[int], p: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * p))))
    return ordered[index]


def call_api(api_base: str, label: str, method: str, path: str, *, timeout: float) -> ConcurrencyResult:
    started = time.perf_counter()
    req = request.Request(f"{api_base}{path}", method=method, headers={"Accept": "application/json"})
    try:
        with request.urlopen(req, timeout=timeout) as response:
            response.read()
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return ConcurrencyResult(label, method, path, True, response.status, elapsed_ms)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return ConcurrencyResult(label, method, path, False, exc.code, elapsed_ms, body[:500])
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return ConcurrencyResult(label, method, path, False, None, elapsed_ms, str(exc))


def write_report(path: str, report: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Concurrent read-path stability smoke for Anti-FOMO APIs.")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    parser.add_argument("--max-p95-ms", type=int, default=2500)
    parser.add_argument(
        "--max-endpoint-p95-ms",
        type=int,
        default=None,
        help="Per-endpoint p95 budget. Defaults to --max-p95-ms.",
    )
    parser.add_argument("--report", default=".tmp/stability_concurrency_smoke_report.json")
    parser.add_argument("--environment", choices=("local", "staging", "production"), default="local")
    parser.add_argument("--model-cold-start-seconds", type=float, default=0.0)
    parser.add_argument("--long-report-cost-cny", type=float, default=0.0)
    parser.add_argument(
        "--validation-input",
        help="Optionally write a Decision Studio performance_cost_benchmark input JSON.",
    )
    args = parser.parse_args()

    api_base = args.api_base.rstrip("/")
    request_count = max(1, min(args.requests, 5000))
    concurrency = max(1, min(args.concurrency, 256))
    max_endpoint_p95_ms = max(1, args.max_endpoint_p95_ms if args.max_endpoint_p95_ms is not None else args.max_p95_ms)
    started_at = datetime.now(timezone.utc)
    jobs = [DEFAULT_ENDPOINTS[index % len(DEFAULT_ENDPOINTS)] for index in range(request_count)]
    results: list[ConcurrencyResult] = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(call_api, api_base, label, method, path, timeout=args.timeout)
            for label, method, path in jobs
        ]
        for future in as_completed(futures):
            results.append(future.result())

    finished_at = datetime.now(timezone.utc)
    ok_count = sum(1 for item in results if item.ok)
    fail_count = len(results) - ok_count
    elapsed_values = [item.elapsed_ms for item in results]
    error_rate = fail_count / len(results) if results else 1.0
    by_endpoint: dict[str, dict[str, Any]] = {}
    for label, _, path in DEFAULT_ENDPOINTS:
        endpoint_results = [item for item in results if item.path == path]
        endpoint_latencies = [item.elapsed_ms for item in endpoint_results]
        by_endpoint[path] = {
            "label": label,
            "requests": len(endpoint_results),
            "passed": sum(1 for item in endpoint_results if item.ok),
            "failed": sum(1 for item in endpoint_results if not item.ok),
            "minMs": min(endpoint_latencies) if endpoint_latencies else 0,
            "medianMs": int(statistics.median(endpoint_latencies)) if endpoint_latencies else 0,
            "p95Ms": percentile(endpoint_latencies, 0.95),
            "p99Ms": percentile(endpoint_latencies, 0.99),
            "maxMs": max(endpoint_latencies) if endpoint_latencies else 0,
        }
    slow_endpoints = [
        {
            "label": values["label"],
            "path": path,
            "p95Ms": values["p95Ms"],
            "thresholdMs": max_endpoint_p95_ms,
        }
        for path, values in by_endpoint.items()
        if int(values["p95Ms"] or 0) > max_endpoint_p95_ms
    ]

    assertions = {
        "errorRateWithinLimit": error_rate <= max(0.0, args.max_error_rate),
        "p95WithinLimit": percentile(elapsed_values, 0.95) <= max(1, args.max_p95_ms),
        "endpointP95WithinLimit": not slow_endpoints,
    }
    failed_assertions = [key for key, value in assertions.items() if not value]
    validation_metrics = {
        "environment": args.environment,
        "concurrent_users": concurrency,
        "request_count": len(results),
        "p95_ms": percentile(elapsed_values, 0.95),
        "error_rate": round(error_rate, 6),
        "model_cold_start_seconds": max(0.0, args.model_cold_start_seconds),
        "long_report_cost_cny": max(0.0, args.long_report_cost_cny),
    }
    release_contract_complete = (
        args.environment == "production"
        and validation_metrics["model_cold_start_seconds"] > 0
        and validation_metrics["long_report_cost_cny"] > 0
    )
    report = {
        "status": "passed" if not failed_assertions else "failed",
        "apiBase": api_base,
        "startedAt": started_at.isoformat(),
        "finishedAt": finished_at.isoformat(),
        "durationSec": round((finished_at - started_at).total_seconds(), 2),
        "requests": len(results),
        "concurrency": concurrency,
        "passed": ok_count,
        "failed": fail_count,
        "errorRate": round(error_rate, 6),
        "latency": {
            "minMs": min(elapsed_values) if elapsed_values else 0,
            "medianMs": int(statistics.median(elapsed_values)) if elapsed_values else 0,
            "p95Ms": percentile(elapsed_values, 0.95),
            "p99Ms": percentile(elapsed_values, 0.99),
            "maxMs": max(elapsed_values) if elapsed_values else 0,
        },
        "thresholds": {
            "maxErrorRate": args.max_error_rate,
            "maxP95Ms": args.max_p95_ms,
            "maxEndpointP95Ms": max_endpoint_p95_ms,
        },
        "assertions": assertions,
        "failedAssertions": failed_assertions,
        "byEndpoint": by_endpoint,
        "slowEndpoints": slow_endpoints,
        "failures": [asdict(item) for item in results if not item.ok][:50],
        "decisionStudioValidation": {
            "suiteKey": "performance_cost_benchmark",
            "releaseContractComplete": release_contract_complete,
            "metrics": validation_metrics,
        },
    }
    write_report(args.report, report)
    if args.validation_input:
        report_uri = Path(args.report).resolve().as_uri()
        write_report(
            args.validation_input,
            {
                "suite_key": "performance_cost_benchmark",
                "metrics": validation_metrics,
                "evidence": {
                    "generated_by": "stability_concurrency_smoke.py",
                    "release_contract_complete": release_contract_complete,
                    "load_report_uri": report_uri,
                },
                "source_artifact_uri": report_uri,
            },
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
