#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request


@dataclass
class SimResult:
    total_urls: int
    ready_items: int
    feedback_count: int
    session_id: str
    session_metrics: dict[str, int]
    task_statuses: dict[str, str]
    task_preview: dict[str, str]


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
        with request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code} {path}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"API unreachable: {exc}") from exc


def load_urls(path: Path) -> list[str]:
    urls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        urls.append(value)
    return urls


def wait_items_terminal(
    api_base: str,
    item_ids: list[str],
    timeout_seconds: int = 180,
    poll_interval: float = 2.0,
) -> dict[str, dict[str, Any]]:
    pending = set(item_ids)
    result: dict[str, dict[str, Any]] = {}
    deadline = time.time() + timeout_seconds
    while pending and time.time() < deadline:
        for item_id in list(pending):
            item = api_call(api_base, f"/api/items/{item_id}")
            status = item.get("status")
            result[item_id] = item
            if status in {"ready", "failed"}:
                pending.remove(item_id)
        if pending:
            time.sleep(poll_interval)
    return result


def find_latest_ready_items_for_urls(api_base: str, urls: list[str], limit: int = 400) -> list[dict[str, Any]]:
    feed = api_call(api_base, f"/api/items?limit={limit}&mode=normal")
    items = feed.get("items", [])
    target = set(urls)
    seen = set()
    picked: list[dict[str, Any]] = []
    for item in items:
        source_url = item.get("source_url")
        if source_url in target and source_url not in seen and item.get("status") == "ready":
            picked.append(item)
            seen.add(source_url)
        if len(seen) == len(target):
            break
    return picked


def apply_feedback_cycle(api_base: str, items: list[dict[str, Any]]) -> int:
    # 覆盖主流程反馈：like / save / ignore / open_detail / inaccurate
    cycle = ["like", "save", "ignore", "open_detail", "inaccurate"]
    count = 0
    for idx, item in enumerate(items):
        feedback_type = cycle[idx % len(cycle)]
        api_call(
            api_base,
            f"/api/items/{item['id']}/feedback",
            method="POST",
            payload={"feedback_type": feedback_type},
        )
        count += 1
    return count


def run_simulation(
    api_base: str,
    urls: list[str],
    goal_text: str,
    focus_reinject_count: int,
) -> SimResult:
    if not urls:
        raise RuntimeError("URL list is empty")

    # 1) 拉取当前 17 条对应的 ready item（用于 feedback 闭环）
    ready_items = find_latest_ready_items_for_urls(api_base, urls, limit=500)
    feedback_count = apply_feedback_cycle(api_base, ready_items)

    # 2) 开启 focus session
    session_started = api_call(
        api_base,
        "/api/sessions/start",
        method="POST",
        payload={"goal_text": goal_text, "duration_minutes": 25},
    )
    session_id = session_started["id"]

    # 3) 在 focus 期间再注入若干条（用已有 URL，模拟“专注期间新增内容”）
    reinject_urls = urls[: max(1, min(focus_reinject_count, len(urls)))]
    batch = api_call(
        api_base,
        "/api/items/batch",
        method="POST",
        payload={"source_type": "url", "urls": reinject_urls, "deduplicate": False},
    )
    created_ids = [row["item_id"] for row in batch.get("results", []) if row.get("status") == "created"]
    if created_ids:
        wait_items_terminal(api_base, created_ids, timeout_seconds=240, poll_interval=2.0)

    # 4) 结束 session，拿到 summary + metrics
    session_finished = api_call(api_base, f"/api/sessions/{session_id}/finish", method="POST")
    session_out = session_finished["session"]
    metrics = session_out.get("metrics", {})

    # 5) 生成三类 WorkTask
    task_types = ["export_markdown_summary", "export_reading_list", "export_todo_draft"]
    task_statuses: dict[str, str] = {}
    task_preview: dict[str, str] = {}
    for task_type in task_types:
        payload: dict[str, Any] = {"task_type": task_type}
        if task_type in {"export_markdown_summary", "export_todo_draft"}:
            payload["session_id"] = session_id
        task = api_call(api_base, "/api/tasks", method="POST", payload=payload)
        task_statuses[task_type] = task.get("status", "unknown")
        content = ((task.get("output_payload") or {}).get("content") or "").strip()
        preview = content.splitlines()[:4]
        task_preview[task_type] = "\n".join(preview)

    return SimResult(
        total_urls=len(urls),
        ready_items=len(ready_items),
        feedback_count=feedback_count,
        session_id=session_id,
        session_metrics={
            "new_content_count": int(metrics.get("new_content_count", 0)),
            "deep_read_count": int(metrics.get("deep_read_count", 0)),
            "later_count": int(metrics.get("later_count", 0)),
            "skip_count": int(metrics.get("skip_count", 0)),
        },
        task_statuses=task_statuses,
        task_preview=task_preview,
    )


def render_report(
    output: Path,
    api_base: str,
    source_file: Path,
    result: SimResult,
) -> None:
    lines = [
        "# Anti-fomo 17条业务流程模拟报告",
        "",
        f"- API: `{api_base}`",
        f"- URL 文件: `{source_file}`",
        f"- 输入 URL 数: **{result.total_urls}**",
        f"- 可用 ready item 数: **{result.ready_items}**",
        f"- 已执行反馈次数: **{result.feedback_count}**",
        f"- Focus Session ID: `{result.session_id}`",
        "",
        "## Session 指标",
        "",
        f"- new_content_count: **{result.session_metrics['new_content_count']}**",
        f"- deep_read_count: **{result.session_metrics['deep_read_count']}**",
        f"- later_count: **{result.session_metrics['later_count']}**",
        f"- skip_count: **{result.session_metrics['skip_count']}**",
        "",
        "## WorkTask 状态",
        "",
    ]

    for task_type, status in result.task_statuses.items():
        lines.append(f"- {task_type}: **{status}**")

    lines.extend(["", "## WorkTask 预览", ""])
    for task_type, preview in result.task_preview.items():
        lines.extend([f"### {task_type}", "", "```markdown", preview or "(empty)", "```", ""])

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate Anti-fomo MVP flow with imported WeChat URLs.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--file", required=True)
    parser.add_argument("--goal", default="整理AI与云厂商动态，输出可执行结论")
    parser.add_argument("--focus-reinject-count", type=int, default=6)
    parser.add_argument("--report", default=".tmp/mvp_simulation_report.md")
    args = parser.parse_args()

    api_base = args.api_base.rstrip("/")
    source_file = Path(args.file).resolve()
    output = Path(args.report).resolve()
    urls = load_urls(source_file)

    health = api_call(api_base, "/healthz")
    if health.get("status") != "ok":
        raise RuntimeError("API health check failed")

    result = run_simulation(
        api_base=api_base,
        urls=urls,
        goal_text=args.goal,
        focus_reinject_count=args.focus_reinject_count,
    )
    render_report(output, api_base, source_file, result)

    summary = Counter(result.task_statuses.values())
    print(
        "[done] ready_items={ready} feedbacks={feedback} session={session} tasks={tasks}".format(
            ready=result.ready_items,
            feedback=result.feedback_count,
            session=result.session_id,
            tasks=dict(summary),
        )
    )
    print(f"[report] {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
