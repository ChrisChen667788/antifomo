from __future__ import annotations

import json
import plistlib
from datetime import datetime, timezone
from pathlib import Path

from app.services import watchlist_automation_service


def test_watchlist_automation_status_reads_plist_and_state(monkeypatch, tmp_path: Path) -> None:
    plist_path = tmp_path / "com.antifomo.watchlists.plist"
    state_path = tmp_path / "watchlist_scheduler.last.json"
    log_path = tmp_path / "watchlist_scheduler.log"
    with plist_path.open("wb") as handle:
        plistlib.dump({"Label": "com.antifomo.watchlists", "StartInterval": 3600}, handle)
    state_path.write_text(
        json.dumps(
            {
                "checked_at": "2026-03-29T08:00:00+00:00",
                "due_count": 3,
                "refreshed_count": 2,
                "failed_count": 1,
                "items": [
                    {"summary": "新增 2 条甲方预算线索", "status": "refreshed", "name": "AI Browser"},
                    {
                        "watchlist_id": "watch-2",
                        "name": "政务云专题",
                        "status": "failed",
                        "summary": "刷新失败",
                        "error": "公开源不足，当前关键词没有命中稳定来源",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    log_path.write_text("watchlist runner log", encoding="utf-8")

    monkeypatch.setattr(watchlist_automation_service, "WATCHLIST_AUTOMATION_PLIST", plist_path)
    monkeypatch.setattr(watchlist_automation_service, "WATCHLIST_AUTOMATION_STATE_FILE", state_path)
    monkeypatch.setattr(watchlist_automation_service, "WATCHLIST_AUTOMATION_LOG_FILE", log_path)
    monkeypatch.setattr(watchlist_automation_service, "_is_launch_agent_loaded", lambda _label: True)

    payload = watchlist_automation_service.get_watchlist_automation_status()

    assert payload["installed"] is True
    assert payload["loaded"] is True
    assert payload["interval_seconds"] == 3600
    assert payload["last_due_count"] == 3
    assert payload["last_refreshed_count"] == 2
    assert payload["last_failed_count"] == 1
    assert payload["last_summary"] == "新增 2 条甲方预算线索；刷新失败"
    assert payload["last_run_status"] == "partial_failure"
    assert payload["last_failure_hint"]
    assert payload["alert_level"] == "high"
    assert payload["action_required"] is True
    assert payload["action_required_reason"]
    assert payload["state_stale"] is True
    assert payload["recent_request_failure_count"] == 0
    assert payload["consecutive_request_failure_count"] == 0
    assert payload["recommended_run_due_command"] == "npm run research:watchlists:run-due"
    assert payload["recommended_status_command"] == "npm run research:watchlists:automation:status"
    assert len(payload["failed_items"]) == 1
    assert payload["failed_items"][0]["name"] == "政务云专题"
    assert payload["failed_items"][0]["error"] == "公开源不足，当前关键词没有命中稳定来源"


def test_watchlist_automation_status_detects_consecutive_request_failures(monkeypatch, tmp_path: Path) -> None:
    plist_path = tmp_path / "com.antifomo.watchlists.plist"
    state_path = tmp_path / "watchlist_scheduler.last.json"
    log_path = tmp_path / "watchlist_scheduler.log"
    with plist_path.open("wb") as handle:
        plistlib.dump({"Label": "com.antifomo.watchlists", "StartInterval": 3600}, handle)
    state_path.write_text(
        json.dumps(
            {
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "due_count": 0,
                "refreshed_count": 0,
                "failed_count": 0,
                "items": [],
            }
        ),
        encoding="utf-8",
    )
    log_path.write_text(
        "\n".join(
            [
                "[watchlists] checked=2026-04-17T20:30:47.785980Z due=0 refreshed=0 failed=0",
                "[watchlists] request failed: <urlopen error [Errno 61] Connection refused>",
                "[watchlists] request failed: <urlopen error [Errno 61] Connection refused>",
                "[watchlists] request failed: <urlopen error [Errno 61] Connection refused>",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(watchlist_automation_service, "WATCHLIST_AUTOMATION_PLIST", plist_path)
    monkeypatch.setattr(watchlist_automation_service, "WATCHLIST_AUTOMATION_STATE_FILE", state_path)
    monkeypatch.setattr(watchlist_automation_service, "WATCHLIST_AUTOMATION_LOG_FILE", log_path)
    monkeypatch.setattr(watchlist_automation_service, "_is_launch_agent_loaded", lambda _label: True)

    payload = watchlist_automation_service.get_watchlist_automation_status()

    assert payload["recent_request_failure_count"] == 3
    assert payload["consecutive_request_failure_count"] == 3
    assert payload["alert_level"] == "high"
    assert payload["action_required"] is True
    assert "连续请求失败" in payload["action_required_reason"]
