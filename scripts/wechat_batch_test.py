#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib import error, request


def api_call(
    api_base: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = request.Request(
        f"{api_base}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            if not body:
                return {}
            return json.loads(body)
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code} {path}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"API unreachable: {exc}") from exc


def load_urls(path: Path) -> list[str]:
    if not path.exists():
        raise RuntimeError(f"URL file not found: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    urls: list[str] = []
    for line in lines:
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        urls.append(value)
    return urls


def render_report(
    *,
    output_path: Path,
    api_base: str,
    source_file: Path,
    total_input: int,
    created: int,
    skipped: int,
    invalid: int,
    status_counter: dict[str, int],
    failed_rows: list[tuple[str, str, str]],
) -> None:
    content_lines = [
        "# WeChat 30篇接入测试报告",
        "",
        f"- API: `{api_base}`",
        f"- URL 文件: `{source_file}`",
        f"- 输入链接数: **{total_input}**",
        f"- 创建: **{created}**",
        f"- 跳过: **{skipped}**",
        f"- 无效: **{invalid}**",
        "",
        "## 处理结果",
        "",
        f"- ready: **{status_counter.get('ready', 0)}**",
        f"- failed: **{status_counter.get('failed', 0)}**",
        f"- pending/processing: **{status_counter.get('pending', 0) + status_counter.get('processing', 0)}**",
        "",
    ]

    if failed_rows:
        content_lines.extend(
            [
                "## 失败条目",
                "",
                "| item_id | source_url | error |",
                "|---|---|---|",
            ]
        )
        for item_id, source_url, error_message in failed_rows:
            safe_source = source_url.replace("|", "%7C")
            safe_error = (error_message or "").replace("|", "%7C")
            content_lines.append(f"| {item_id} | {safe_source} | {safe_error} |")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(content_lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch import and verify WeChat article URLs.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--file", default=".tmp/wechat_urls.txt")
    parser.add_argument("--min-count", type=int, default=30)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--report", default=".tmp/wechat_batch_report.md")
    args = parser.parse_args()

    api_base = args.api_base.rstrip("/")
    source_file = Path(args.file).resolve()
    report_file = Path(args.report).resolve()

    urls = load_urls(source_file)
    if len(urls) < args.min_count:
        print(
            f"[error] 需要至少 {args.min_count} 条 URL，当前只有 {len(urls)} 条。文件：{source_file}",
            file=sys.stderr,
        )
        return 2

    print(f"[1/4] 健康检查 {api_base}/healthz")
    health = api_call(api_base, "/healthz")
    if health.get("status") != "ok":
        print("[error] API health check failed.", file=sys.stderr)
        return 3

    print(f"[2/4] 批量提交 URL，共 {len(urls)} 条")
    batch_result = api_call(
        api_base,
        "/api/items/batch",
        method="POST",
        payload={"source_type": "url", "urls": urls, "deduplicate": True},
    )
    created = int(batch_result.get("created", 0))
    skipped = int(batch_result.get("skipped", 0))
    invalid = int(batch_result.get("invalid", 0))
    results = batch_result.get("results", [])
    print(f"      创建={created} 跳过={skipped} 无效={invalid}")

    created_rows = [row for row in results if row.get("status") == "created" and row.get("item_id")]
    if not created_rows:
        print("[3/4] 无新增条目，跳过轮询。")
        render_report(
            output_path=report_file,
            api_base=api_base,
            source_file=source_file,
            total_input=len(urls),
            created=created,
            skipped=skipped,
            invalid=invalid,
            status_counter={},
            failed_rows=[],
        )
        print(f"[4/4] 报告已生成：{report_file}")
        return 0

    item_id_to_source: dict[str, str] = {row["item_id"]: row.get("source_url", "") for row in created_rows}
    pending_ids = set(item_id_to_source.keys())
    statuses: dict[str, dict[str, Any]] = {}

    print(f"[3/4] 轮询处理状态，目标 {len(pending_ids)} 条，超时 {args.timeout_seconds}s")
    deadline = time.time() + args.timeout_seconds
    while pending_ids and time.time() < deadline:
        for item_id in list(pending_ids):
            item = api_call(api_base, f"/api/items/{item_id}")
            status = str(item.get("status", "pending"))
            statuses[item_id] = item
            if status in {"ready", "failed"}:
                pending_ids.discard(item_id)
        if pending_ids:
            time.sleep(args.poll_interval)

    status_counter = {"ready": 0, "failed": 0, "pending": 0, "processing": 0}
    failed_rows: list[tuple[str, str, str]] = []
    for item_id, source_url in item_id_to_source.items():
        item = statuses.get(item_id) or api_call(api_base, f"/api/items/{item_id}")
        status = str(item.get("status", "pending"))
        if status not in status_counter:
            status_counter["pending"] += 1
        else:
            status_counter[status] += 1
        if status == "failed":
            failed_rows.append((item_id, source_url, str(item.get("processing_error") or "")))

    print(
        "[result] ready={ready} failed={failed} pending={pending} processing={processing}".format(
            **status_counter
        )
    )

    render_report(
        output_path=report_file,
        api_base=api_base,
        source_file=source_file,
        total_input=len(urls),
        created=created,
        skipped=skipped,
        invalid=invalid,
        status_counter=status_counter,
        failed_rows=failed_rows,
    )
    print(f"[4/4] 报告已生成：{report_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
