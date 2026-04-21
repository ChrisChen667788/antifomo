#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request


@dataclass
class ValidateRow:
    source_url: str
    item_id: str
    status: str
    title: str
    tags: list[str]
    short_summary: str
    action_suggestion: str
    used_reader_content: bool


def api_call(
    api_base: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = request.Request(
        f"{api_base}{path}",
        method=method,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            return json.loads(body) if body else {}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code} {path}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"API unreachable: {exc}") from exc


def load_urls(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    for line in lines:
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        out.append(value)
    return out


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def contains_access_block(text: str) -> bool:
    lowered = text.lower()
    hints = (
        "requiring captcha",
        "环境异常",
        "去验证",
        "访问受限",
        "完成验证后即可继续访问",
    )
    return any(hint in lowered for hint in hints)


def reader_proxy_extract(url: str) -> tuple[str | None, str | None]:
    target = url.strip()
    if target.startswith("https://"):
        target = "http://" + target[len("https://") :]
    elif not target.startswith("http://"):
        target = "http://" + target

    proxy_url = f"https://r.jina.ai/{target}"
    req = request.Request(
        proxy_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            )
        },
    )
    try:
        with request.urlopen(req, timeout=20) as resp:
            text = resp.read(2_000_000).decode("utf-8", errors="ignore")
    except Exception:
        return None, None

    if not text:
        return None, None

    title_match = re.search(r"^Title:\s*(.+)$", text, flags=re.MULTILINE)
    title = normalize(title_match.group(1)) if title_match else None
    _, _, markdown_part = text.partition("Markdown Content:")
    body = normalize(markdown_part or text)

    if not body or len(body) < 140 or contains_access_block(f"{title or ''} {body}"):
        return title, None
    return title, body[:18000]


def build_plugin_payload(url: str) -> tuple[dict[str, Any], bool]:
    title, body = reader_proxy_extract(url)
    if body:
        lines = []
        if title:
            lines.append(f"标题：{title}")
        lines.append(f"正文：{body}")
        payload = {
            "source_type": "plugin",
            "source_url": url,
            "title": title,
            "raw_content": "\n".join(lines),
        }
        return payload, True

    payload = {
        "source_type": "plugin",
        "source_url": url,
        "title": title,
        "raw_content": None,
    }
    return payload, False


def wait_items(
    api_base: str,
    item_ids: list[str],
    *,
    timeout_seconds: int,
    poll_interval: float,
) -> dict[str, dict[str, Any]]:
    pending = set(item_ids)
    out: dict[str, dict[str, Any]] = {}
    deadline = time.time() + timeout_seconds

    while pending and time.time() < deadline:
        for item_id in list(pending):
            item = api_call(api_base, f"/api/items/{item_id}")
            out[item_id] = item
            if item.get("status") in {"ready", "failed"}:
                pending.remove(item_id)
        if pending:
            time.sleep(poll_interval)

    for item_id in pending:
        out[item_id] = api_call(api_base, f"/api/items/{item_id}")
    return out


def render_report(
    output: Path,
    *,
    api_base: str,
    source_file: Path,
    total_input: int,
    excluded: str | None,
    rows: list[ValidateRow],
) -> None:
    status_count: dict[str, int] = {}
    for row in rows:
        status_count[row.status] = status_count.get(row.status, 0) + 1

    lines = [
        "# Chrome 插件批量验证报告（剩余16条）",
        "",
        f"- API: `{api_base}`",
        f"- URL 文件: `{source_file}`",
        f"- 输入链接数: **{total_input}**",
        f"- 本次验证数: **{len(rows)}**",
        f"- 排除链接: `{excluded or '无'}`",
        f"- ready: **{status_count.get('ready', 0)}**",
        f"- failed: **{status_count.get('failed', 0)}**",
        "",
        "| token | status | used_reader_content | title | tags | short_summary | action |",
        "|---|---|---:|---|---|---|---|",
    ]

    for row in rows:
        token = row.source_url.rstrip("/").split("/")[-1]
        tags = ",".join(row.tags).replace("|", "%7C")
        title = row.title.replace("|", "%7C")
        short_summary = row.short_summary.replace("|", "%7C")
        action = row.action_suggestion or "-"
        lines.append(
            f"| {token} | {row.status} | {'yes' if row.used_reader_content else 'no'} | "
            f"{title} | {tags} | {short_summary} | {action} |"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate URLs via plugin-like submission pipeline.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--file", default=".tmp/wechat_urls_17_wechat_only.txt")
    parser.add_argument("--exclude-url", default="https://mp.weixin.qq.com/s/KA-D3o_8Eil7jdkmIjW8XA")
    parser.add_argument("--timeout-seconds", type=int, default=220)
    parser.add_argument("--poll-interval", type=float, default=1.5)
    parser.add_argument("--report", default=".tmp/plugin_validation_remaining16.md")
    args = parser.parse_args()

    api_base = args.api_base.rstrip("/")
    source_file = Path(args.file).resolve()
    report = Path(args.report).resolve()

    urls = load_urls(source_file)
    targets = [u for u in urls if u != args.exclude_url]

    health = api_call(api_base, "/healthz")
    if health.get("status") != "ok":
        raise RuntimeError("API health check failed")

    created: list[tuple[str, str, bool]] = []
    for url in targets:
        payload, used_reader_content = build_plugin_payload(url)
        item = api_call(api_base, "/api/items", method="POST", payload=payload)
        created.append((url, item["id"], used_reader_content))

    details = wait_items(
        api_base,
        [item_id for _, item_id, _ in created],
        timeout_seconds=args.timeout_seconds,
        poll_interval=args.poll_interval,
    )

    rows: list[ValidateRow] = []
    for url, item_id, used_reader_content in created:
        detail = details[item_id]
        rows.append(
            ValidateRow(
                source_url=url,
                item_id=item_id,
                status=str(detail.get("status", "unknown")),
                title=str(detail.get("title") or ""),
                tags=[tag.get("tag_name", "") for tag in detail.get("tags", [])],
                short_summary=str(detail.get("short_summary") or "")[:120],
                action_suggestion=str(detail.get("action_suggestion") or ""),
                used_reader_content=used_reader_content,
            )
        )

    render_report(
        report,
        api_base=api_base,
        source_file=source_file,
        total_input=len(urls),
        excluded=args.exclude_url,
        rows=rows,
    )

    ready_count = sum(1 for row in rows if row.status == "ready")
    failed_count = sum(1 for row in rows if row.status == "failed")
    rich_count = sum(1 for row in rows if row.used_reader_content)
    print(
        f"[done] validated={len(rows)} ready={ready_count} failed={failed_count} "
        f"with_reader_content={rich_count}"
    )
    print(f"[report] {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
