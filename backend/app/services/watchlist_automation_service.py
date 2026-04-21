from __future__ import annotations

import json
import plistlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path


WATCHLIST_AUTOMATION_LABEL = "com.antifomo.watchlists"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
WATCHLIST_AUTOMATION_STATE_FILE = PROJECT_ROOT / ".tmp" / "watchlist_scheduler.last.json"
WATCHLIST_AUTOMATION_LOG_FILE = PROJECT_ROOT / ".tmp" / "watchlist_scheduler.log"
WATCHLIST_AUTOMATION_PLIST = Path.home() / "Library" / "LaunchAgents" / f"{WATCHLIST_AUTOMATION_LABEL}.plist"


def _parse_dt(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _read_json_dict(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_log_lines(path: Path, *, max_lines: int = 80) -> list[str]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    return [line.strip() for line in lines[-max_lines:] if line.strip()]


def _read_launch_agent_config(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        with path.open("rb") as handle:
            payload = plistlib.load(handle)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _is_launch_agent_loaded(label: str) -> bool:
    try:
        run = subprocess.run(
            ["launchctl", "list", label],
            capture_output=True,
            text=True,
            check=False,
            timeout=8,
        )
    except Exception:
        return False
    return run.returncode == 0


def _last_summary(state: dict[str, object]) -> str:
    items = state.get("items")
    if isinstance(items, list):
        summaries = []
        for item in items[:2]:
            if not isinstance(item, dict):
                continue
            text = str(item.get("summary") or item.get("error") or "").strip()
            if text:
                summaries.append(text)
        if summaries:
            return "；".join(summaries[:2])
    return ""


def _failed_items(state: dict[str, object]) -> list[dict[str, object]]:
    items = state.get("items")
    if not isinstance(items, list):
        return []
    failed: list[dict[str, object]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").strip().lower()
        error = str(item.get("error") or "").strip()
        if status != "failed" and not error:
            continue
        failed.append(
            {
                "watchlist_id": str(item.get("watchlist_id") or ""),
                "name": str(item.get("name") or "Watchlist").strip() or "Watchlist",
                "status": "failed",
                "change_count": int(item.get("change_count") or 0),
                "summary": str(item.get("summary") or error or "刷新失败").strip(),
                "next_due_at": item.get("next_due_at"),
                "error": error or None,
            }
        )
    return failed[:3]


def _last_run_status(state: dict[str, object]) -> str:
    checked_at = _parse_dt(state.get("checked_at"))
    due_count = int(state.get("due_count") or 0)
    refreshed_count = int(state.get("refreshed_count") or 0)
    failed_count = int(state.get("failed_count") or 0)
    if checked_at is None and due_count == 0 and refreshed_count == 0 and failed_count == 0:
        return "idle"
    if failed_count and refreshed_count:
        return "partial_failure"
    if failed_count:
        return "failed"
    return "ok"


def _last_failure_hint(state: dict[str, object]) -> str:
    failed_items = _failed_items(state)
    if not failed_items:
        return ""
    first_error = str(failed_items[0].get("error") or failed_items[0].get("summary") or "").strip()
    if "not found" in first_error.lower():
        return "先检查 watchlist 绑定的 tracking topic 是否仍存在，再重跑自动巡检。"
    if "公开源" in first_error or "source" in first_error.lower():
        return "先检查该专题关键词、官方源和公开检索窗口，再结合日志定位失败原因。"
    return "优先查看最近失败样本和本地调度日志，确认关键词、公开源和专题绑定是否正常。"


def _request_failure_stats(log_lines: list[str]) -> tuple[int, int]:
    recent = 0
    consecutive = 0
    for line in log_lines:
        if "request failed:" in line.lower():
            recent += 1
    for line in reversed(log_lines):
        if "request failed:" not in line.lower():
            break
        consecutive += 1
    return recent, consecutive


def _state_age_seconds(last_checked_at: datetime | None) -> int:
    if last_checked_at is None:
        return 0
    now = datetime.now(timezone.utc)
    checked_at = last_checked_at if last_checked_at.tzinfo else last_checked_at.replace(tzinfo=timezone.utc)
    return max(0, int((now - checked_at).total_seconds()))


def _stale_state(*, last_checked_at: datetime | None, interval_seconds: int, loaded: bool) -> bool:
    if not loaded or last_checked_at is None or interval_seconds <= 0:
        return False
    age_seconds = _state_age_seconds(last_checked_at)
    return age_seconds > max(interval_seconds * 2 + 300, interval_seconds + 900)


def _action_required_profile(
    *,
    installed: bool,
    loaded: bool,
    last_run_status: str,
    state_stale: bool,
    recent_request_failure_count: int,
    consecutive_request_failure_count: int,
    last_failed_count: int,
) -> tuple[str, bool, str]:
    if installed and not loaded:
        return "high", True, "launchd 已安装但未加载，自动巡检当前没有实际运行。"
    if consecutive_request_failure_count >= 3:
        return "high", True, "最近连续请求失败，自动巡检很可能无法访问本地后端。"
    if state_stale:
        return "high", True, "自动巡检状态已过期，当前可能没有按预期触发。"
    if last_run_status in {"failed", "partial_failure"} or last_failed_count > 0:
        return "medium", True, "最近自动巡检存在失败样本，建议先手动重跑并核对失败原因。"
    if recent_request_failure_count > 0:
        return "medium", False, "日志里出现过请求失败，建议顺手核对本地后端可用性。"
    return "low", False, ""


def get_watchlist_automation_status() -> dict[str, object]:
    config = _read_launch_agent_config(WATCHLIST_AUTOMATION_PLIST)
    state = _read_json_dict(WATCHLIST_AUTOMATION_STATE_FILE)
    installed = WATCHLIST_AUTOMATION_PLIST.exists()
    loaded = _is_launch_agent_loaded(WATCHLIST_AUTOMATION_LABEL)
    interval_seconds = 0
    if config:
        try:
            interval_seconds = max(0, int(config.get("StartInterval") or 0))
        except (TypeError, ValueError):
            interval_seconds = 0
    last_checked_at = _parse_dt(state.get("checked_at"))
    last_run_status = _last_run_status(state)
    log_lines = _read_log_lines(WATCHLIST_AUTOMATION_LOG_FILE)
    recent_request_failure_count, consecutive_request_failure_count = _request_failure_stats(log_lines)
    state_stale = _stale_state(last_checked_at=last_checked_at, interval_seconds=interval_seconds, loaded=loaded)
    alert_level, action_required, action_required_reason = _action_required_profile(
        installed=installed,
        loaded=loaded,
        last_run_status=last_run_status,
        state_stale=state_stale,
        recent_request_failure_count=recent_request_failure_count,
        consecutive_request_failure_count=consecutive_request_failure_count,
        last_failed_count=int(state.get("failed_count") or 0),
    )
    return {
        "installed": installed,
        "loaded": loaded,
        "label": WATCHLIST_AUTOMATION_LABEL,
        "plist_path": str(WATCHLIST_AUTOMATION_PLIST),
        "state_path": str(WATCHLIST_AUTOMATION_STATE_FILE),
        "log_path": str(WATCHLIST_AUTOMATION_LOG_FILE),
        "interval_seconds": interval_seconds,
        "last_checked_at": last_checked_at,
        "last_due_count": int(state.get("due_count") or 0),
        "last_refreshed_count": int(state.get("refreshed_count") or 0),
        "last_failed_count": int(state.get("failed_count") or 0),
        "last_run_status": last_run_status,
        "last_summary": _last_summary(state),
        "last_failure_hint": _last_failure_hint(state),
        "alert_level": alert_level,
        "action_required": action_required,
        "action_required_reason": action_required_reason,
        "state_stale": state_stale,
        "state_age_seconds": _state_age_seconds(last_checked_at),
        "recent_request_failure_count": recent_request_failure_count,
        "consecutive_request_failure_count": consecutive_request_failure_count,
        "failed_items": _failed_items(state),
        "last_log_size_bytes": int(WATCHLIST_AUTOMATION_LOG_FILE.stat().st_size) if WATCHLIST_AUTOMATION_LOG_FILE.exists() else 0,
        "recommended_run_due_command": "npm run research:watchlists:run-due",
        "recommended_status_command": "npm run research:watchlists:automation:status",
        "recommended_install_command": "npm run research:watchlists:automation:install",
        "recommended_uninstall_command": "npm run research:watchlists:automation:uninstall",
    }
