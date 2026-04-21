#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".tmp"


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    data: dict[str, Any] = field(default_factory=dict)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def http_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: int = 20,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        try:
            return resp.status, json.loads(raw)
        except json.JSONDecodeError:
            return resp.status, raw


def safe_http_json(*args, **kwargs) -> tuple[bool, int | None, Any]:
    try:
        status, data = http_json(*args, **kwargs)
        return True, status, data
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = body
        return False, exc.code, data
    except Exception as exc:  # pragma: no cover - smoke helper
        return False, None, {"error": str(exc)}


def poll_item_ready(base_url: str, item_id: str, timeout_sec: int = 40) -> tuple[bool, dict[str, Any]]:
    deadline = time.time() + timeout_sec
    last_data: dict[str, Any] = {}
    while time.time() < deadline:
        ok, _, data = safe_http_json(base_url, f"/api/items/{item_id}")
        if ok and isinstance(data, dict):
            last_data = data
            if data.get("status") == "ready":
                return True, data
        time.sleep(1.2)
    return False, last_data


def check_web_routes(web_url: str) -> list[CheckResult]:
    routes = ["/", "/inbox", "/focus", "/session-summary", "/research", "/knowledge", "/collector", "/settings"]
    results: list[CheckResult] = []
    for route in routes:
        ok, status, data = safe_http_json(web_url, route, method="GET", headers={"Accept": "text/html"})
        detail = f"HTTP {status}" if status else "request failed"
        if isinstance(data, str):
            detail = f"{detail}, bytes={len(data)}"
        results.append(CheckResult(name=f"web:{route}", ok=ok and status == 200, detail=detail))
    return results


def check_api_health(api_url: str) -> list[CheckResult]:
    checks: list[CheckResult] = []
    for path in ["/healthz", "/api/workbuddy/health", "/api/collector/status", "/api/collector/wechat-agent/status"]:
        ok, status, data = safe_http_json(api_url, path)
        checks.append(
            CheckResult(
                name=f"api:{path}",
                ok=ok and status == 200,
                detail=f"HTTP {status}" if status else "request failed",
                data=data if isinstance(data, dict) else {"raw": str(data)},
            )
        )
    return checks


def run_item_flow(api_url: str) -> list[CheckResult]:
    checks: list[CheckResult] = []
    create_payload = {
        "source_type": "text",
        "title": "Smoke Test 专注场景验证",
        "raw_content": (
            "本测试内容用于验证 Anti-FOMO 的输入、摘要、标签、评分、反馈、知识库与重处理链路。"
            "重点包含预算、招标、二期项目、生态伙伴与销售推进等关键词。"
        ),
        "output_language": "zh-CN",
    }
    ok, status, created = safe_http_json(api_url, "/api/items", method="POST", payload=create_payload)
    item_id = str(created.get("id")) if ok and isinstance(created, dict) and created.get("id") else ""
    checks.append(
        CheckResult(
            name="item:create_text",
            ok=ok and status == 201 and bool(item_id),
            detail=f"HTTP {status}, item_id={item_id or 'n/a'}",
            data=created if isinstance(created, dict) else {},
        )
    )
    if not item_id:
        return checks

    ready, item = poll_item_ready(api_url, item_id)
    checks.append(
        CheckResult(
            name="item:processing_to_ready",
            ok=ready,
            detail=f"status={item.get('status', 'unknown')}",
            data=item,
        )
    )

    ok, status, interpretation = safe_http_json(
        api_url,
        f"/api/items/{item_id}/interpret",
        method="POST",
        payload={"output_language": "zh-CN"},
    )
    checks.append(
        CheckResult(
            name="item:interpret",
            ok=ok and status == 200 and bool(interpretation.get("expert_take")),
            detail=f"HTTP {status}",
            data=interpretation if isinstance(interpretation, dict) else {},
        )
    )

    ok, status, feedback = safe_http_json(
        api_url,
        f"/api/items/{item_id}/feedback",
        method="POST",
        payload={"feedback_type": "save"},
    )
    checks.append(
        CheckResult(
            name="item:feedback_save",
            ok=ok and status == 200 and feedback.get("status") == "ok",
            detail=f"HTTP {status}, knowledge_status={feedback.get('knowledge_status')}",
            data=feedback if isinstance(feedback, dict) else {},
        )
    )

    ok, status, knowledge = safe_http_json(
        api_url,
        f"/api/items/{item_id}/knowledge",
        method="POST",
        payload={"output_language": "zh-CN"},
    )
    checks.append(
        CheckResult(
            name="item:add_to_knowledge",
            ok=ok and status == 201 and bool(knowledge.get("entry_id")),
            detail=f"HTTP {status}, entry_id={knowledge.get('entry_id')}",
            data=knowledge if isinstance(knowledge, dict) else {},
        )
    )

    ok, status, reprocess = safe_http_json(
        api_url,
        f"/api/items/{item_id}/reprocess",
        method="POST",
        payload={"output_language": "zh-CN"},
    )
    checks.append(
        CheckResult(
            name="item:reprocess_submit",
            ok=ok and status == 200 and reprocess.get("status") == "processing",
            detail=f"HTTP {status}, status={reprocess.get('status')}",
            data=reprocess if isinstance(reprocess, dict) else {},
        )
    )

    ready_after_reprocess, item_after_reprocess = poll_item_ready(api_url, item_id)
    checks.append(
        CheckResult(
            name="item:reprocess_ready",
            ok=ready_after_reprocess,
            detail=f"status={item_after_reprocess.get('status', 'unknown')}",
            data=item_after_reprocess,
        )
    )

    ok, status, saved_list = safe_http_json(api_url, "/api/items/saved?limit=20")
    saved_ids = {str(row.get("id")) for row in (saved_list.get("items") or [])} if isinstance(saved_list, dict) else set()
    checks.append(
        CheckResult(
            name="item:saved_list_visible",
            ok=ok and status == 200 and item_id in saved_ids,
            detail=f"HTTP {status}, saved_count={len(saved_ids)}",
            data={"saved_ids_sample": sorted(list(saved_ids))[:5]},
        )
    )
    return checks


def run_focus_flow(api_url: str) -> list[CheckResult]:
    checks: list[CheckResult] = []
    ok, status, session = safe_http_json(
        api_url,
        "/api/sessions/start",
        method="POST",
        payload={
            "goal_text": "测试 50 分钟专注与回流链路",
            "duration_minutes": 50,
            "output_language": "zh-CN",
        },
    )
    session_id = str(session.get("id")) if ok and isinstance(session, dict) and session.get("id") else ""
    checks.append(
        CheckResult(
            name="focus:start_50min",
            ok=ok and status == 201 and session.get("duration_minutes") == 50,
            detail=f"HTTP {status}, session_id={session_id or 'n/a'}, duration={session.get('duration_minutes')}",
            data=session if isinstance(session, dict) else {},
        )
    )
    if not session_id:
        return checks

    ok, status, latest = safe_http_json(api_url, f"/api/sessions/{session_id}")
    checks.append(
        CheckResult(
            name="focus:get_session",
            ok=ok and status == 200 and latest.get("duration_minutes") == 50,
            detail=f"HTTP {status}, status={latest.get('status')}",
            data=latest if isinstance(latest, dict) else {},
        )
    )

    ok, status, plan = safe_http_json(
        api_url,
        "/api/focus-assistant/plan",
        method="POST",
        payload={
            "goal_text": "测试 50 分钟专注与回流链路",
            "duration_minutes": 50,
            "session_id": session_id,
            "output_language": "zh-CN",
        },
    )
    checks.append(
        CheckResult(
            name="focus:assistant_plan",
            ok=ok and status == 200 and bool(plan.get("actions")),
            detail=f"HTTP {status}, actions={len(plan.get('actions') or [])}",
            data=plan if isinstance(plan, dict) else {},
        )
    )

    ok, status, execute = safe_http_json(
        api_url,
        "/api/focus-assistant/execute",
        method="POST",
        payload={
            "action_key": "reading_digest",
            "goal_text": "测试 50 分钟专注与回流链路",
            "duration_minutes": 50,
            "session_id": session_id,
            "output_language": "zh-CN",
            "channel": "direct",
        },
    )
    checks.append(
        CheckResult(
            name="focus:assistant_execute",
            ok=ok and status == 202 and bool((execute.get("task") or {}).get("id")),
            detail=f"HTTP {status}, task_status={(execute.get('task') or {}).get('status')}",
            data=execute if isinstance(execute, dict) else {},
        )
    )

    ok, status, todo_preview = safe_http_json(
        api_url,
        f"/api/sessions/{session_id}/todo-calendar-preview",
        method="POST",
        payload={"output_language": "zh-CN", "calendar_name": "Anti-FOMO Smoke"},
    )
    checks.append(
        CheckResult(
            name="focus:todo_calendar_preview",
            ok=ok and status == 200 and "events" in todo_preview,
            detail=f"HTTP {status}, task_count={todo_preview.get('task_count')}",
            data=todo_preview if isinstance(todo_preview, dict) else {},
        )
    )

    ok, status, finished = safe_http_json(
        api_url,
        f"/api/sessions/{session_id}/finish",
        method="POST",
        payload={"output_language": "zh-CN"},
    )
    finished_session = finished.get("session", {}) if isinstance(finished, dict) else {}
    checks.append(
        CheckResult(
            name="focus:finish_session",
            ok=ok and status == 200 and (finished_session.get("status") == "finished"),
            detail=f"HTTP {status}, status={finished_session.get('status')}",
            data=finished if isinstance(finished, dict) else {},
        )
    )

    return checks


def run_research_flow(api_url: str) -> list[CheckResult]:
    checks: list[CheckResult] = []
    ok, status, report = safe_http_json(
        api_url,
        "/api/research/report",
        method="POST",
        payload={
            "keyword": "政务云",
            "research_focus": "未来五年预算与生态伙伴",
            "output_language": "zh-CN",
            "include_wechat": True,
            "max_sources": 3,
        },
        timeout=60,
    )
    checks.append(
        CheckResult(
            name="research:create_report",
            ok=ok and status == 200 and bool(report.get("report_title")),
            detail=f"HTTP {status}, sources={report.get('source_count')}",
            data={"report_title": report.get("report_title"), "source_count": report.get("source_count")},
        )
    )
    if not ok or not isinstance(report, dict):
        return checks

    ok, status, saved = safe_http_json(
        api_url,
        "/api/research/report/save",
        method="POST",
        payload={"report": report, "collection_name": "Smoke 研报", "is_focus_reference": False},
    )
    research_entry_id = saved.get("entry_id") if isinstance(saved, dict) else None
    checks.append(
        CheckResult(
            name="research:save_report",
            ok=ok and status == 200 and bool(research_entry_id),
            detail=f"HTTP {status}, entry_id={research_entry_id}",
            data=saved if isinstance(saved, dict) else {},
        )
    )

    ok, status, action_plan = safe_http_json(
        api_url,
        "/api/research/action-plan",
        method="POST",
        payload={"report": report},
    )
    cards = action_plan.get("cards") or [] if isinstance(action_plan, dict) else []
    checks.append(
        CheckResult(
            name="research:create_action_plan",
            ok=ok and status == 200 and len(cards) >= 1,
            detail=f"HTTP {status}, cards={len(cards)}",
            data={"card_count": len(cards), "first_keys": list(cards[0].keys()) if cards else []},
        )
    )

    if cards:
      ok, status, saved_actions = safe_http_json(
          api_url,
          "/api/research/action-plan/save",
          method="POST",
          payload={
              "keyword": report["keyword"],
              "cards": cards[:2],
              "collection_name": "Smoke 行动卡",
              "is_focus_reference": True,
          },
      )
      checks.append(
          CheckResult(
              name="research:save_action_cards",
              ok=ok and status == 200 and int(saved_actions.get("created_count", 0)) >= 1,
              detail=f"HTTP {status}, created={saved_actions.get('created_count')}",
              data=saved_actions if isinstance(saved_actions, dict) else {},
          )
      )

    for task_type in [
        "export_research_report_markdown",
        "export_research_report_word",
        "export_research_report_pdf",
    ]:
        ok, status, task = safe_http_json(
            api_url,
            "/api/tasks",
            method="POST",
            payload={
                "task_type": task_type,
                "input_payload": {"report": report},
            },
            timeout=60,
        )
        output_payload = task.get("output_payload") or {} if isinstance(task, dict) else {}
        checks.append(
            CheckResult(
                name=f"research:task:{task_type}",
                ok=ok and status == 201 and task.get("status") == "done" and bool(output_payload),
                detail=f"HTTP {status}, status={task.get('status')}",
                data={"task_id": task.get("id"), "output_keys": sorted(output_payload.keys())},
            )
        )

    return checks


def run_workbuddy_flow(api_url: str) -> list[CheckResult]:
    checks: list[CheckResult] = []
    ok, status, ping = safe_http_json(
        api_url,
        "/api/workbuddy/webhook",
        method="POST",
        payload={"event_type": "ping", "request_id": "smoke_ping"},
    )
    checks.append(
        CheckResult(
            name="workbuddy:ping",
            ok=ok and status == 202 and ping.get("message") == "pong",
            detail=f"HTTP {status}, message={ping.get('message')}",
            data=ping if isinstance(ping, dict) else {},
        )
    )
    ok, status, task = safe_http_json(
        api_url,
        "/api/workbuddy/webhook",
        method="POST",
        payload={
            "event_type": "create_task",
            "request_id": "smoke_task",
            "task_type": "export_reading_list",
            "input_payload": {"output_language": "zh-CN"},
        },
    )
    task_data = task.get("task") or {} if isinstance(task, dict) else {}
    checks.append(
        CheckResult(
            name="workbuddy:create_task",
            ok=ok and status == 202 and task_data.get("status") == "done",
            detail=f"HTTP {status}, task_status={task_data.get('status')}",
            data={"task_id": task_data.get("id"), "message": task.get("message")},
        )
    )
    return checks


def run_collector_flow(api_url: str) -> list[CheckResult]:
    checks: list[CheckResult] = []
    for name, path in [
        ("collector:status", "/api/collector/status"),
        ("collector:daily_summary", "/api/collector/daily-summary"),
        ("collector:wechat_status", "/api/collector/wechat-agent/status"),
        ("collector:wechat_batch_status", "/api/collector/wechat-agent/batch-status"),
        ("collector:wechat_dedup_summary", "/api/collector/wechat-agent/dedup-summary"),
    ]:
        ok, status, data = safe_http_json(api_url, path)
        checks.append(
            CheckResult(
                name=name,
                ok=ok and status == 200,
                detail=f"HTTP {status}",
                data=data if isinstance(data, dict) else {"raw": str(data)},
            )
        )
    return checks


def run_miniapp_syntax_checks() -> list[CheckResult]:
    import subprocess

    targets = [
        "miniapp/app.js",
        "miniapp/utils/api.js",
        "miniapp/pages/feed/index.js",
        "miniapp/pages/inbox/index.js",
        "miniapp/pages/item/index.js",
        "miniapp/pages/focus/index.js",
        "miniapp/pages/session-summary/index.js",
        "miniapp/pages/knowledge/index.js",
        "miniapp/pages/research/index.js",
        "miniapp/pages/settings/index.js",
    ]
    results: list[CheckResult] = []
    for rel_path in targets:
        full = ROOT / rel_path
        proc = subprocess.run(
            ["node", "--check", str(full)],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        detail = "ok" if proc.returncode == 0 else (proc.stderr.strip() or proc.stdout.strip() or "syntax error")
        results.append(CheckResult(name=f"miniapp:{rel_path}", ok=proc.returncode == 0, detail=detail))
    return results


def summarize(results: list[CheckResult]) -> dict[str, Any]:
    passed = sum(1 for item in results if item.ok)
    failed = len(results) - passed
    return {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "pass_rate": round((passed / len(results)) * 100, 2) if results else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Anti-FOMO core smoke tests.")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--web", default="http://127.0.0.1:3000")
    args = parser.parse_args()

    started_at = utc_now()
    results: list[CheckResult] = []
    results.extend(check_api_health(args.api))
    results.extend(check_web_routes(args.web))
    results.extend(run_item_flow(args.api))
    results.extend(run_focus_flow(args.api))
    results.extend(run_research_flow(args.api))
    results.extend(run_workbuddy_flow(args.api))
    results.extend(run_collector_flow(args.api))
    results.extend(run_miniapp_syntax_checks())

    report = {
        "started_at": started_at,
        "finished_at": utc_now(),
        "api_base_url": args.api,
        "web_base_url": args.web,
        "summary": summarize(results),
        "results": [asdict(item) for item in results],
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "smoke_test_core_latest.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"report_path={report_path}")
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
