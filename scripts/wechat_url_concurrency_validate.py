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
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class BatchResult:
    index: int
    ok: bool
    status: int | None
    elapsed_ms: int
    total: int = 0
    created: int = 0
    skipped: int = 0
    invalid: int = 0
    item_ids: list[str] | None = None
    error: str | None = None


def percentile(values: list[int], p: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * p))))
    return ordered[index]


def api_call(
    api_base: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 20.0,
) -> tuple[int, dict[str, Any]]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = request.Request(
        f"{api_base.rstrip('/')}{path}",
        data=data,
        method=method,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    with request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        parsed = json.loads(body) if body else {}
        return response.status, parsed if isinstance(parsed, dict) else {}


def load_urls_from_file(path: Path) -> list[str]:
    if not path.exists():
        raise RuntimeError(f"URL file not found: {path}")
    urls: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            urls.append(value)
    return urls


def load_urls_from_api(api_base: str, *, limit: int, timeout: float) -> list[str]:
    _, payload = api_call(api_base, f"/api/items?limit={max(1, min(limit, 1000))}", timeout=timeout)
    rows = payload.get("items")
    if not isinstance(rows, list):
        return []
    urls: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = str(row.get("source_url") or "").strip()
        if value:
            urls.append(value)
    return urls


def normalize_urls(raw_urls: list[str], *, mp_only: bool, max_urls: int) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for raw in raw_urls:
        value = raw.strip()
        if not value.startswith(("http://", "https://")):
            continue
        if mp_only and "mp.weixin.qq.com/" not in value:
            continue
        if value in seen:
            continue
        seen.add(value)
        urls.append(value)
        if len(urls) >= max(1, max_urls):
            break
    return urls


def make_batch(urls: list[str], *, index: int, batch_size: int) -> list[str]:
    return [urls[(index * batch_size + offset) % len(urls)] for offset in range(batch_size)]


def submit_batch(
    api_base: str,
    index: int,
    urls: list[str],
    *,
    deduplicate: bool,
    output_language: str,
    timeout: float,
) -> BatchResult:
    started = time.perf_counter()
    try:
        status, payload = api_call(
            api_base,
            "/api/items/batch",
            method="POST",
            payload={
                "source_type": "url",
                "urls": urls,
                "deduplicate": deduplicate,
                "output_language": output_language,
            },
            timeout=timeout,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        rows = payload.get("results") if isinstance(payload, dict) else []
        item_ids = [
            str(row.get("item_id"))
            for row in rows
            if isinstance(row, dict) and row.get("status") == "created" and row.get("item_id")
        ]
        return BatchResult(
            index=index,
            ok=200 <= status < 300,
            status=status,
            elapsed_ms=elapsed_ms,
            total=int(payload.get("total") or 0),
            created=int(payload.get("created") or 0),
            skipped=int(payload.get("skipped") or 0),
            invalid=int(payload.get("invalid") or 0),
            item_ids=item_ids,
        )
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return BatchResult(index=index, ok=False, status=exc.code, elapsed_ms=elapsed_ms, error=body[:800])
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return BatchResult(index=index, ok=False, status=None, elapsed_ms=elapsed_ms, error=str(exc))


def write_report(path: str, report: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Concurrent WeChat URL batch-ingest validation. Default mode is non-destructive: "
            "deduplicate=true, so existing URLs should be skipped instead of creating duplicate items."
        )
    )
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--urls-file", default="")
    parser.add_argument("--source-api-limit", type=int, default=300)
    parser.add_argument("--max-urls", type=int, default=50)
    parser.add_argument("--requests", type=int, default=64)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--output-language", default="zh-CN")
    parser.add_argument("--include-non-mp", action="store_true")
    parser.add_argument(
        "--force-create",
        action="store_true",
        help="Set deduplicate=false. This creates duplicate test items and should only be used intentionally.",
    )
    parser.add_argument("--min-url-count", type=int, default=1)
    parser.add_argument("--max-error-rate", type=float, default=0.0)
    parser.add_argument("--max-p95-ms", type=int, default=4000)
    parser.add_argument("--report", default=".tmp/wechat_url_concurrency_validate_report.json")
    args = parser.parse_args()

    api_base = args.api_base.rstrip("/")
    started_at = datetime.now(timezone.utc)
    try:
        _, health = api_call(api_base, "/healthz", timeout=args.timeout)
        if health.get("status") != "ok":
            raise RuntimeError(f"backend not healthy: {health}")
    except Exception as exc:  # noqa: BLE001
        report = {
            "status": "failed",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "apiBase": api_base,
            "error": f"health check failed: {exc}",
        }
        write_report(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    raw_urls = (
        load_urls_from_file(Path(args.urls_file).expanduser())
        if args.urls_file
        else load_urls_from_api(api_base, limit=args.source_api_limit, timeout=args.timeout)
    )
    urls = normalize_urls(raw_urls, mp_only=not args.include_non_mp, max_urls=args.max_urls)
    if len(urls) < max(1, args.min_url_count):
        report = {
            "status": "failed",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "apiBase": api_base,
            "urlCount": len(urls),
            "thresholds": {"minUrlCount": args.min_url_count},
            "error": "not enough usable WeChat mp.weixin URLs for validation",
        }
        write_report(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    request_count = max(1, min(args.requests, 2000))
    concurrency = max(1, min(args.concurrency, 128))
    batch_size = max(1, min(args.batch_size, 200))
    deduplicate = not args.force_create
    results: list[BatchResult] = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(
                submit_batch,
                api_base,
                index,
                make_batch(urls, index=index, batch_size=batch_size),
                deduplicate=deduplicate,
                output_language=args.output_language,
                timeout=args.timeout,
            )
            for index in range(request_count)
        ]
        for future in as_completed(futures):
            results.append(future.result())

    finished_at = datetime.now(timezone.utc)
    ok_count = sum(1 for item in results if item.ok)
    fail_count = len(results) - ok_count
    error_rate = fail_count / len(results) if results else 1.0
    latencies = [item.elapsed_ms for item in results]
    created_total = sum(item.created for item in results)
    skipped_total = sum(item.skipped for item in results)
    invalid_total = sum(item.invalid for item in results)
    created_item_ids = [
        item_id
        for item in sorted(results, key=lambda row: row.index)
        for item_id in (item.item_ids or [])
    ]
    assertions = {
        "urlCountWithinLimit": len(urls) >= max(1, args.min_url_count),
        "errorRateWithinLimit": error_rate <= max(0.0, args.max_error_rate),
        "p95WithinLimit": percentile(latencies, 0.95) <= max(1, args.max_p95_ms),
        "invalidIsZero": invalid_total == 0,
    }
    failed_assertions = [key for key, ok in assertions.items() if not ok]
    report = {
        "status": "passed" if not failed_assertions else "failed",
        "apiBase": api_base,
        "generatedAt": finished_at.isoformat(),
        "startedAt": started_at.isoformat(),
        "durationSec": round((finished_at - started_at).total_seconds(), 2),
        "mode": "force-create" if args.force_create else "safe-deduplicate",
        "destructive": bool(args.force_create),
        "urlCount": len(urls),
        "sampleUrls": urls[:10],
        "requests": len(results),
        "concurrency": concurrency,
        "batchSize": batch_size,
        "deduplicate": deduplicate,
        "passed": ok_count,
        "failed": fail_count,
        "errorRate": round(error_rate, 6),
        "totals": {
            "submittedUrls": len(results) * batch_size,
            "created": created_total,
            "skipped": skipped_total,
            "invalid": invalid_total,
            "createdItemIds": created_item_ids[:100],
            "createdItemIdCount": len(created_item_ids),
        },
        "latency": {
            "minMs": min(latencies) if latencies else 0,
            "medianMs": int(statistics.median(latencies)) if latencies else 0,
            "p95Ms": percentile(latencies, 0.95),
            "p99Ms": percentile(latencies, 0.99),
            "maxMs": max(latencies) if latencies else 0,
        },
        "thresholds": {
            "minUrlCount": args.min_url_count,
            "maxErrorRate": args.max_error_rate,
            "maxP95Ms": args.max_p95_ms,
        },
        "assertions": assertions,
        "failedAssertions": failed_assertions,
        "failures": [asdict(item) for item in results if not item.ok][:50],
    }
    write_report(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
