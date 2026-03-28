from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile
from threading import Event, Lock, Thread
import time
from typing import Literal


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TMP_DIR = PROJECT_ROOT / ".tmp"

PID_FILE = TMP_DIR / "wechat_pc_agent.pid"
RUN_ONCE_PID_FILE = TMP_DIR / "wechat_pc_agent_run_once.pid"
LOG_FILE = TMP_DIR / "wechat_pc_agent.log"
CONFIG_FILE = TMP_DIR / "wechat_pc_agent_config.json"
STATE_FILE = TMP_DIR / "wechat_pc_agent_state.json"
REPORT_FILE = TMP_DIR / "wechat_pc_agent_latest.json"
BATCH_STATUS_FILE = TMP_DIR / "wechat_pc_agent_batch_status.json"

START_SCRIPT = PROJECT_ROOT / "scripts" / "start_wechat_pc_agent.sh"
STOP_SCRIPT = PROJECT_ROOT / "scripts" / "stop_wechat_pc_agent.sh"
AGENT_SCRIPT = PROJECT_ROOT / "scripts" / "wechat_pc_full_auto_agent.py"

DEFAULT_WECHAT_AGENT_CONFIG: dict[str, object] = {
    "api_base": "http://127.0.0.1:8000",
    "output_language": "zh-CN",
    "coordinate_mode": "auto",
    "article_link_profile": "auto",
    "wechat_bundle_id": "com.tencent.xinWeChat",
    "wechat_app_name": "WeChat",
    "public_account_origin": {"x": 151, "y": 236},
    "public_account_hotspots": [
        {"x": 151, "y": 236},
        {"x": 151, "y": 252},
        {"x": 166, "y": 236},
        {"x": 136, "y": 236},
    ],
    "list_origin": {"x": 1221, "y": 271},
    "article_row_height": 140,
    "rows_per_batch": 1,
    "batches_per_cycle": 5,
    "article_open_wait_sec": 1.2,
    "article_capture_region": {"x": 360, "y": 110, "width": 1020, "height": 860},
    "article_link_hotspots": [
        {"right_inset": 44, "top_offset": 26},
        {"right_inset": 84, "top_offset": 26},
        {"right_inset": 124, "top_offset": 26},
        {"right_inset": 44, "top_offset": 58},
    ],
    "article_link_menu_offsets": [
        {"dx": 0, "dy": 42},
        {"dx": 0, "dy": 78},
        {"dx": 0, "dy": 112},
        {"dx": -52, "dy": 78},
        {"dx": 52, "dy": 78},
    ],
    "article_reset_page_up": 3,
    "article_extra_page_down": 0,
    "feed_reset_page_up": 4,
    "page_down_wait_sec": 0.65,
    "list_page_down_after_batch": 1,
    "duplicate_escape_page_down": 2,
    "duplicate_escape_max_extra_pages": 6,
    "between_item_delay_sec": 0.55,
    "dedup_max_hashes": 8000,
    "min_capture_file_size_kb": 45,
    "article_allow_ocr_fallback": False,
    "article_verify_with_ocr": True,
    "article_verify_min_text_length": 120,
    "article_verify_retries": 2,
    "loop_interval_sec": 300,
    "health_stale_minutes": 20,
}


@dataclass(slots=True)
class WechatAgentStatus:
    running: bool
    pid: int | None
    pid_from_file: int | None
    pid_file_present: bool
    run_once_running: bool
    run_once_pid: int | None
    uptime_seconds: int | None
    config_file: str
    config_file_present: bool
    state_file: str
    state_file_present: bool
    report_file: str
    report_file_present: bool
    processed_hashes: int
    last_cycle_at: datetime | None
    last_cycle_submitted: int
    last_cycle_submitted_new: int
    last_cycle_deduplicated_existing: int
    last_cycle_failed: int
    last_cycle_skipped_seen: int
    last_cycle_skipped_low_quality: int
    last_cycle_error: str | None
    last_cycle_new_item_ids: list[str]
    log_file: str
    log_size_bytes: int
    log_tail: list[str]


@dataclass(slots=True)
class WechatAgentCommandResult:
    action: Literal["start", "stop", "run_once"]
    ok: bool
    message: str
    status: WechatAgentStatus
    output: str | None = None


@dataclass(slots=True)
class WechatAgentHealthReport:
    healthy: bool
    checked_at: datetime
    stale_threshold_minutes: int
    running: bool
    last_cycle_at: datetime | None
    minutes_since_last_cycle: float | None
    reasons: list[str]
    recommendation: str | None
    status: WechatAgentStatus


@dataclass(slots=True)
class WechatAgentSelfHealResult:
    ok: bool
    action: Literal["none", "start", "restart"]
    message: str
    health_before: WechatAgentHealthReport
    health_after: WechatAgentHealthReport
    output: str | None = None


@dataclass(slots=True)
class WechatAgentBatchStatus:
    running: bool
    total_items: int
    segment_items: int
    start_batch_index: int
    current_segment_index: int
    total_segments: int
    current_batch_index: int
    started_at: datetime | None
    finished_at: datetime | None
    submitted: int
    submitted_new: int
    submitted_url: int
    submitted_url_direct: int
    submitted_url_share_copy: int
    submitted_url_resolved: int
    submitted_ocr: int
    deduplicated_existing: int
    deduplicated_existing_url: int
    deduplicated_existing_url_direct: int
    deduplicated_existing_url_share_copy: int
    deduplicated_existing_url_resolved: int
    deduplicated_existing_ocr: int
    skipped_invalid_article: int
    skipped_seen: int
    failed: int
    validation_retries: int
    new_item_ids: list[str]
    last_message: str | None
    last_error: str | None
    live_report_running: bool = False
    live_report_batch: int | None = None
    live_report_row: int | None = None
    live_report_stage: str | None = None
    live_report_detail: str | None = None
    live_report_clicked: int = 0
    live_report_submitted: int = 0
    live_report_submitted_url: int = 0
    live_report_submitted_url_direct: int = 0
    live_report_submitted_url_share_copy: int = 0
    live_report_submitted_url_resolved: int = 0
    live_report_submitted_ocr: int = 0
    live_report_skipped_seen: int = 0
    live_report_skipped_invalid_article: int = 0
    live_report_failed: int = 0
    live_report_checkpoint_at: datetime | None = None


@dataclass(slots=True)
class WechatAgentDedupStateSummary:
    processed_hashes: int
    run_count: int
    last_run_started_at: datetime | None
    last_run_finished_at: datetime | None
    last_run_submitted: int
    last_run_skipped_seen: int
    last_run_failed: int
    last_run_item_ids: list[str]


@dataclass(slots=True)
class WechatAgentBatchCommandResult:
    ok: bool
    message: str
    batch_status: WechatAgentBatchStatus


_batch_lock = Lock()
_batch_thread: Thread | None = None
_batch_stop_event: Event | None = None
_batch_process: subprocess.Popen[str] | None = None


def _parse_pid(value: str | None) -> int | None:
    text = str(value or "").strip()
    if not text or not text.isdigit():
        return None
    pid = int(text)
    if pid <= 1:
        return None
    return pid


def _read_pid_from_file(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return _parse_pid(path.read_text(encoding="utf-8"))
    except OSError:
        return None


def _read_pid_file() -> int | None:
    return _read_pid_from_file(PID_FILE)


def _read_run_once_pid_file() -> int | None:
    return _read_pid_from_file(RUN_ONCE_PID_FILE)


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _find_pid_by_pgrep() -> int | None:
    pattern = f"{AGENT_SCRIPT}.*--loop"
    try:
        run = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if run.returncode not in {0, 1}:
        return None

    pids: list[int] = []
    for line in run.stdout.splitlines():
        pid = _parse_pid(line)
        if pid:
            pids.append(pid)
    return pids[-1] if pids else None


def _find_run_once_pid_by_pgrep() -> int | None:
    try:
        run = subprocess.run(
            ["pgrep", "-f", str(AGENT_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if run.returncode not in {0, 1}:
        return None

    matched: list[int] = []
    for line in run.stdout.splitlines():
        pid = _parse_pid(line)
        if not pid:
            continue
        try:
            ps = subprocess.run(
                ["ps", "-o", "command=", "-p", str(pid)],
                capture_output=True,
                text=True,
                timeout=4,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if ps.returncode != 0:
            continue
        command = ps.stdout.strip()
        if not command:
            continue
        if "--loop" in command:
            continue
        if "--init-config-only" in command:
            continue
        matched.append(pid)
    return matched[-1] if matched else None


def _resolve_running_pid() -> tuple[int | None, int | None, bool]:
    pid_file_present = PID_FILE.exists()
    pid_from_file = _read_pid_file()
    if _pid_alive(pid_from_file):
        return pid_from_file, pid_from_file, pid_file_present
    return _find_pid_by_pgrep(), pid_from_file, pid_file_present


def _resolve_run_once_pid() -> tuple[int | None, int | None, bool]:
    pid_file_present = RUN_ONCE_PID_FILE.exists()
    pid_from_file = _read_run_once_pid_file()
    if _pid_alive(pid_from_file):
        return pid_from_file, pid_from_file, pid_file_present
    return _find_run_once_pid_by_pgrep(), pid_from_file, pid_file_present


def _parse_etime_to_seconds(etime: str) -> int | None:
    text = etime.strip()
    if not text:
        return None
    day_part = 0
    time_part = text
    if "-" in text:
        day_text, _, rest = text.partition("-")
        if day_text.isdigit():
            day_part = int(day_text)
            time_part = rest

    segments = [seg for seg in time_part.split(":") if seg]
    if not segments or any(not seg.isdigit() for seg in segments):
        return None
    if len(segments) == 2:
        hours = 0
        minutes, seconds = int(segments[0]), int(segments[1])
    elif len(segments) == 3:
        hours, minutes, seconds = int(segments[0]), int(segments[1]), int(segments[2])
    else:
        return None
    return day_part * 86400 + hours * 3600 + minutes * 60 + seconds


def _get_uptime_seconds(pid: int | None) -> int | None:
    if not pid:
        return None
    try:
        run = subprocess.run(
            ["ps", "-o", "etime=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if run.returncode != 0:
        return None
    return _parse_etime_to_seconds(run.stdout.strip())


def _tail_log(max_lines: int = 14, max_chars: int = 2800) -> list[str]:
    if not LOG_FILE.exists():
        return []
    try:
        lines = LOG_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    selected = [line.strip() for line in lines[-max_lines:] if line.strip()]
    while selected and sum(len(line) for line in selected) > max_chars:
        selected = selected[1:]
    return selected


def _read_json_dict(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(loaded, dict):
        return {}
    return loaded


def _write_json_dict(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _default_batch_status_payload() -> dict[str, object]:
    return {
        "running": False,
        "total_items": 0,
        "segment_items": 0,
        "start_batch_index": 0,
        "current_segment_index": 0,
        "total_segments": 0,
        "current_batch_index": 0,
        "started_at": None,
        "finished_at": None,
        "submitted": 0,
        "submitted_new": 0,
        "submitted_url": 0,
        "submitted_url_direct": 0,
        "submitted_url_share_copy": 0,
        "submitted_url_resolved": 0,
        "submitted_ocr": 0,
        "deduplicated_existing": 0,
        "deduplicated_existing_url": 0,
        "deduplicated_existing_url_direct": 0,
        "deduplicated_existing_url_share_copy": 0,
        "deduplicated_existing_url_resolved": 0,
        "deduplicated_existing_ocr": 0,
        "skipped_invalid_article": 0,
        "skipped_seen": 0,
        "failed": 0,
        "validation_retries": 0,
        "new_item_ids": [],
        "last_message": None,
        "last_error": None,
        "live_report_running": False,
        "live_report_batch": None,
        "live_report_row": None,
        "live_report_stage": None,
        "live_report_detail": None,
        "live_report_clicked": 0,
        "live_report_submitted": 0,
        "live_report_submitted_url": 0,
        "live_report_submitted_url_direct": 0,
        "live_report_submitted_url_share_copy": 0,
        "live_report_submitted_url_resolved": 0,
        "live_report_submitted_ocr": 0,
        "live_report_skipped_seen": 0,
        "live_report_skipped_invalid_article": 0,
        "live_report_failed": 0,
        "live_report_checkpoint_at": None,
    }


def _parse_dt(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _sanitize_batch_status_payload(raw: dict[str, object]) -> dict[str, object]:
    payload = _default_batch_status_payload()
    payload["running"] = bool(raw.get("running"))
    payload["total_items"] = _coerce_int(raw.get("total_items"), 0, 0, 500)
    payload["segment_items"] = _coerce_int(raw.get("segment_items"), 0, 0, 200)
    payload["start_batch_index"] = _coerce_int(raw.get("start_batch_index"), 0, 0, 1_000)
    payload["current_segment_index"] = _coerce_int(raw.get("current_segment_index"), 0, 0, 1_000)
    payload["total_segments"] = _coerce_int(raw.get("total_segments"), 0, 0, 1_000)
    payload["current_batch_index"] = _coerce_int(raw.get("current_batch_index"), 0, 0, 1_000)
    payload["started_at"] = (_parse_dt(raw.get("started_at")) or None)
    payload["finished_at"] = (_parse_dt(raw.get("finished_at")) or None)
    payload["submitted"] = _coerce_int(raw.get("submitted"), 0, 0, 1_000_000)
    payload["submitted_new"] = _coerce_int(raw.get("submitted_new"), 0, 0, 1_000_000)
    payload["submitted_url"] = _coerce_int(raw.get("submitted_url"), 0, 0, 1_000_000)
    payload["submitted_url_direct"] = _coerce_int(raw.get("submitted_url_direct"), 0, 0, 1_000_000)
    payload["submitted_url_share_copy"] = _coerce_int(raw.get("submitted_url_share_copy"), 0, 0, 1_000_000)
    payload["submitted_url_resolved"] = _coerce_int(raw.get("submitted_url_resolved"), 0, 0, 1_000_000)
    payload["submitted_ocr"] = _coerce_int(raw.get("submitted_ocr"), 0, 0, 1_000_000)
    payload["deduplicated_existing"] = _coerce_int(raw.get("deduplicated_existing"), 0, 0, 1_000_000)
    payload["deduplicated_existing_url"] = _coerce_int(
        raw.get("deduplicated_existing_url"),
        0,
        0,
        1_000_000,
    )
    payload["deduplicated_existing_url_direct"] = _coerce_int(
        raw.get("deduplicated_existing_url_direct"),
        0,
        0,
        1_000_000,
    )
    payload["deduplicated_existing_url_share_copy"] = _coerce_int(
        raw.get("deduplicated_existing_url_share_copy"),
        0,
        0,
        1_000_000,
    )
    payload["deduplicated_existing_url_resolved"] = _coerce_int(
        raw.get("deduplicated_existing_url_resolved"),
        0,
        0,
        1_000_000,
    )
    payload["deduplicated_existing_ocr"] = _coerce_int(
        raw.get("deduplicated_existing_ocr"),
        0,
        0,
        1_000_000,
    )
    payload["skipped_invalid_article"] = _coerce_int(raw.get("skipped_invalid_article"), 0, 0, 1_000_000)
    payload["skipped_seen"] = _coerce_int(raw.get("skipped_seen"), 0, 0, 1_000_000)
    payload["failed"] = _coerce_int(raw.get("failed"), 0, 0, 1_000_000)
    payload["validation_retries"] = _coerce_int(raw.get("validation_retries"), 0, 0, 1_000_000)
    new_item_ids = raw.get("new_item_ids")
    if isinstance(new_item_ids, list):
        payload["new_item_ids"] = [str(value).strip() for value in new_item_ids if str(value or "").strip()][:64]
    payload["last_message"] = str(raw.get("last_message")).strip() if raw.get("last_message") else None
    payload["last_error"] = str(raw.get("last_error")).strip() if raw.get("last_error") else None
    payload["live_report_running"] = bool(raw.get("live_report_running"))
    payload["live_report_batch"] = _coerce_int(raw.get("live_report_batch"), 0, 0, 10_000) or None
    payload["live_report_row"] = _coerce_int(raw.get("live_report_row"), 0, 0, 1_000) or None
    payload["live_report_stage"] = str(raw.get("live_report_stage")).strip() if raw.get("live_report_stage") else None
    payload["live_report_detail"] = str(raw.get("live_report_detail")).strip() if raw.get("live_report_detail") else None
    payload["live_report_clicked"] = _coerce_int(raw.get("live_report_clicked"), 0, 0, 1_000_000)
    payload["live_report_submitted"] = _coerce_int(raw.get("live_report_submitted"), 0, 0, 1_000_000)
    payload["live_report_submitted_url"] = _coerce_int(raw.get("live_report_submitted_url"), 0, 0, 1_000_000)
    payload["live_report_submitted_url_direct"] = _coerce_int(
        raw.get("live_report_submitted_url_direct"),
        0,
        0,
        1_000_000,
    )
    payload["live_report_submitted_url_share_copy"] = _coerce_int(
        raw.get("live_report_submitted_url_share_copy"),
        0,
        0,
        1_000_000,
    )
    payload["live_report_submitted_url_resolved"] = _coerce_int(
        raw.get("live_report_submitted_url_resolved"),
        0,
        0,
        1_000_000,
    )
    payload["live_report_submitted_ocr"] = _coerce_int(raw.get("live_report_submitted_ocr"), 0, 0, 1_000_000)
    payload["live_report_skipped_seen"] = _coerce_int(raw.get("live_report_skipped_seen"), 0, 0, 1_000_000)
    payload["live_report_skipped_invalid_article"] = _coerce_int(
        raw.get("live_report_skipped_invalid_article"),
        0,
        0,
        1_000_000,
    )
    payload["live_report_failed"] = _coerce_int(raw.get("live_report_failed"), 0, 0, 1_000_000)
    payload["live_report_checkpoint_at"] = (_parse_dt(raw.get("live_report_checkpoint_at")) or None)
    return payload


def _serialize_batch_status_payload(payload: dict[str, object]) -> dict[str, object]:
    serialized = dict(payload)
    for key in ("started_at", "finished_at"):
        value = serialized.get(key)
        if isinstance(value, datetime):
            serialized[key] = value.isoformat()
    return serialized


def _batch_status_from_payload(payload: dict[str, object]) -> WechatAgentBatchStatus:
    sanitized = _sanitize_batch_status_payload(payload)
    return WechatAgentBatchStatus(
        running=bool(sanitized["running"]),
        total_items=int(sanitized["total_items"]),
        segment_items=int(sanitized["segment_items"]),
        start_batch_index=int(sanitized["start_batch_index"]),
        current_segment_index=int(sanitized["current_segment_index"]),
        total_segments=int(sanitized["total_segments"]),
        current_batch_index=int(sanitized["current_batch_index"]),
        started_at=sanitized["started_at"] if isinstance(sanitized["started_at"], datetime) else None,
        finished_at=sanitized["finished_at"] if isinstance(sanitized["finished_at"], datetime) else None,
        submitted=int(sanitized["submitted"]),
        submitted_new=int(sanitized["submitted_new"]),
        submitted_url=int(sanitized["submitted_url"]),
        submitted_url_direct=int(sanitized["submitted_url_direct"]),
        submitted_url_share_copy=int(sanitized["submitted_url_share_copy"]),
        submitted_url_resolved=int(sanitized["submitted_url_resolved"]),
        submitted_ocr=int(sanitized["submitted_ocr"]),
        deduplicated_existing=int(sanitized["deduplicated_existing"]),
        deduplicated_existing_url=int(sanitized["deduplicated_existing_url"]),
        deduplicated_existing_url_direct=int(sanitized["deduplicated_existing_url_direct"]),
        deduplicated_existing_url_share_copy=int(sanitized["deduplicated_existing_url_share_copy"]),
        deduplicated_existing_url_resolved=int(sanitized["deduplicated_existing_url_resolved"]),
        deduplicated_existing_ocr=int(sanitized["deduplicated_existing_ocr"]),
        skipped_invalid_article=int(sanitized["skipped_invalid_article"]),
        skipped_seen=int(sanitized["skipped_seen"]),
        failed=int(sanitized["failed"]),
        validation_retries=int(sanitized["validation_retries"]),
        new_item_ids=list(sanitized["new_item_ids"]),
        last_message=sanitized["last_message"] if isinstance(sanitized["last_message"], str) else None,
        last_error=sanitized["last_error"] if isinstance(sanitized["last_error"], str) else None,
        live_report_running=bool(sanitized["live_report_running"]),
        live_report_batch=int(sanitized["live_report_batch"]) if sanitized["live_report_batch"] is not None else None,
        live_report_row=int(sanitized["live_report_row"]) if sanitized["live_report_row"] is not None else None,
        live_report_stage=sanitized["live_report_stage"] if isinstance(sanitized["live_report_stage"], str) else None,
        live_report_detail=sanitized["live_report_detail"] if isinstance(sanitized["live_report_detail"], str) else None,
        live_report_clicked=int(sanitized["live_report_clicked"]),
        live_report_submitted=int(sanitized["live_report_submitted"]),
        live_report_submitted_url=int(sanitized["live_report_submitted_url"]),
        live_report_submitted_url_direct=int(sanitized["live_report_submitted_url_direct"]),
        live_report_submitted_url_share_copy=int(sanitized["live_report_submitted_url_share_copy"]),
        live_report_submitted_url_resolved=int(sanitized["live_report_submitted_url_resolved"]),
        live_report_submitted_ocr=int(sanitized["live_report_submitted_ocr"]),
        live_report_skipped_seen=int(sanitized["live_report_skipped_seen"]),
        live_report_skipped_invalid_article=int(sanitized["live_report_skipped_invalid_article"]),
        live_report_failed=int(sanitized["live_report_failed"]),
        live_report_checkpoint_at=(
            sanitized["live_report_checkpoint_at"] if isinstance(sanitized["live_report_checkpoint_at"], datetime) else None
        ),
    )


def read_wechat_agent_batch_status() -> WechatAgentBatchStatus:
    payload = _read_json_dict(BATCH_STATUS_FILE)
    sanitized = _sanitize_batch_status_payload(payload)
    if bool(sanitized.get("running")):
        sanitized.update(_read_live_report_snapshot())
    return _batch_status_from_payload(sanitized)


def _write_wechat_agent_batch_status(payload: dict[str, object]) -> WechatAgentBatchStatus:
    sanitized = _sanitize_batch_status_payload(payload)
    _write_json_dict(BATCH_STATUS_FILE, _serialize_batch_status_payload(sanitized))
    return _batch_status_from_payload(sanitized)


def _coerce_int(value: object, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _coerce_float(value: object, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _coerce_output_language(value: object, default: str = "zh-CN") -> str:
    language = str(value or "").strip()
    supported = {"zh-CN", "zh-TW", "en", "ja", "ko"}
    return language if language in supported else default


def _coerce_coordinate_mode(value: object, default: str = "auto") -> str:
    mode = str(value or "").strip().lower()
    return mode if mode in {"auto", "absolute", "window_relative"} else default


def _sanitize_wechat_relative_points(
    raw: object,
    *,
    default: list[dict[str, int]],
    primary_x_key: str,
    primary_x_default: int,
    primary_x_min: int,
    primary_x_max: int,
    primary_y_key: str,
    primary_y_default: int,
    primary_y_min: int,
    primary_y_max: int,
    min_items: int,
    max_items: int,
) -> list[dict[str, int]]:
    if not isinstance(raw, list):
        raw = default

    sanitized: list[dict[str, int]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        sanitized.append(
            {
                primary_x_key: _coerce_int(entry.get(primary_x_key), primary_x_default, primary_x_min, primary_x_max),
                primary_y_key: _coerce_int(entry.get(primary_y_key), primary_y_default, primary_y_min, primary_y_max),
            }
        )

    if len(sanitized) < min_items:
        return [dict(item) for item in default[:max_items]]
    return sanitized[:max_items]


def _sanitize_wechat_agent_config(raw: dict[str, object]) -> dict[str, object]:
    merged = dict(DEFAULT_WECHAT_AGENT_CONFIG)
    merged.update(raw)

    public_origin_raw = merged.get("public_account_origin")
    public_origin_map = public_origin_raw if isinstance(public_origin_raw, dict) else {}
    list_origin_raw = merged.get("list_origin")
    list_origin_map = list_origin_raw if isinstance(list_origin_raw, dict) else {}
    capture_raw = merged.get("article_capture_region")
    capture_map = capture_raw if isinstance(capture_raw, dict) else {}
    public_hotspots_raw = merged.get("public_account_hotspots")
    link_hotspots_raw = merged.get("article_link_hotspots")
    link_menu_offsets_raw = merged.get("article_link_menu_offsets")

    sanitized: dict[str, object] = {
        "api_base": str(merged.get("api_base") or "http://127.0.0.1:8000").strip().rstrip("/"),
        "output_language": _coerce_output_language(merged.get("output_language"), default="zh-CN"),
        "coordinate_mode": _coerce_coordinate_mode(merged.get("coordinate_mode"), default="auto"),
        "article_link_profile": str(merged.get("article_link_profile") or "auto").strip().lower()
        if str(merged.get("article_link_profile") or "auto").strip().lower() in {"auto", "compact", "standard", "wide", "manual"}
        else "auto",
        "wechat_bundle_id": str(merged.get("wechat_bundle_id") or "com.tencent.xinWeChat").strip(),
        "wechat_app_name": str(merged.get("wechat_app_name") or "WeChat").strip(),
        "public_account_origin": {
            "x": _coerce_int(public_origin_map.get("x"), 151, 0, 10000),  # type: ignore[arg-type]
            "y": _coerce_int(public_origin_map.get("y"), 236, 0, 10000),  # type: ignore[arg-type]
        },
        "public_account_hotspots": _sanitize_wechat_relative_points(
            public_hotspots_raw,
            default=DEFAULT_WECHAT_AGENT_CONFIG["public_account_hotspots"],  # type: ignore[arg-type]
            primary_x_key="x",
            primary_x_default=151,
            primary_x_min=0,
            primary_x_max=10000,
            primary_y_key="y",
            primary_y_default=236,
            primary_y_min=0,
            primary_y_max=10000,
            min_items=1,
            max_items=6,
        ),
        "list_origin": {
            "x": _coerce_int(list_origin_map.get("x"), 1221, 0, 10000),  # type: ignore[arg-type]
            "y": _coerce_int(list_origin_map.get("y"), 271, 0, 10000),  # type: ignore[arg-type]
        },
        "article_row_height": _coerce_int(merged.get("article_row_height"), 140, 20, 300),
        "rows_per_batch": _coerce_int(merged.get("rows_per_batch"), 1, 1, 20),
        "batches_per_cycle": _coerce_int(merged.get("batches_per_cycle"), 5, 1, 30),
        "article_open_wait_sec": _coerce_float(merged.get("article_open_wait_sec"), 1.4, 0.1, 8.0),
        "article_capture_region": {
            "x": _coerce_int(capture_map.get("x"), 360, 0, 10000),  # type: ignore[arg-type]
            "y": _coerce_int(capture_map.get("y"), 110, 0, 10000),  # type: ignore[arg-type]
            "width": _coerce_int(capture_map.get("width"), 1020, 60, 10000),  # type: ignore[arg-type]
            "height": _coerce_int(capture_map.get("height"), 860, 60, 10000),  # type: ignore[arg-type]
        },
        "article_link_hotspots": _sanitize_wechat_relative_points(
            link_hotspots_raw,
            default=DEFAULT_WECHAT_AGENT_CONFIG["article_link_hotspots"],  # type: ignore[arg-type]
            primary_x_key="right_inset",
            primary_x_default=44,
            primary_x_min=0,
            primary_x_max=600,
            primary_y_key="top_offset",
            primary_y_default=26,
            primary_y_min=-600,
            primary_y_max=600,
            min_items=1,
            max_items=8,
        ),
        "article_link_menu_offsets": _sanitize_wechat_relative_points(
            link_menu_offsets_raw,
            default=DEFAULT_WECHAT_AGENT_CONFIG["article_link_menu_offsets"],  # type: ignore[arg-type]
            primary_x_key="dx",
            primary_x_default=0,
            primary_x_min=-800,
            primary_x_max=800,
            primary_y_key="dy",
            primary_y_default=42,
            primary_y_min=-800,
            primary_y_max=800,
            min_items=1,
            max_items=10,
        ),
        "article_reset_page_up": _coerce_int(merged.get("article_reset_page_up"), 3, 0, 10),
        "article_extra_page_down": _coerce_int(merged.get("article_extra_page_down"), 0, 0, 10),
        "feed_reset_page_up": _coerce_int(merged.get("feed_reset_page_up"), 4, 0, 20),
        "page_down_wait_sec": _coerce_float(merged.get("page_down_wait_sec"), 0.8, 0.1, 8.0),
        "list_page_down_after_batch": _coerce_int(merged.get("list_page_down_after_batch"), 1, 0, 10),
        "duplicate_escape_page_down": _coerce_int(merged.get("duplicate_escape_page_down"), 2, 1, 8),
        "duplicate_escape_max_extra_pages": _coerce_int(merged.get("duplicate_escape_max_extra_pages"), 6, 1, 24),
        "between_item_delay_sec": _coerce_float(merged.get("between_item_delay_sec"), 0.7, 0.0, 8.0),
        "dedup_max_hashes": _coerce_int(merged.get("dedup_max_hashes"), 8000, 200, 50000),
        "min_capture_file_size_kb": _coerce_int(merged.get("min_capture_file_size_kb"), 45, 1, 2048),
        "article_allow_ocr_fallback": bool(merged.get("article_allow_ocr_fallback", False)),
        "article_verify_with_ocr": bool(merged.get("article_verify_with_ocr", True)),
        "article_verify_min_text_length": _coerce_int(
            merged.get("article_verify_min_text_length"),
            120,
            60,
            1200,
        ),
        "article_verify_retries": _coerce_int(merged.get("article_verify_retries"), 2, 1, 5),
        "loop_interval_sec": _coerce_int(merged.get("loop_interval_sec"), 300, 20, 3600),
        "health_stale_minutes": _coerce_int(merged.get("health_stale_minutes"), 20, 3, 240),
    }

    if not sanitized["api_base"]:
        sanitized["api_base"] = "http://127.0.0.1:8000"
    return sanitized


def ensure_wechat_agent_config_file() -> dict[str, object]:
    current = _read_json_dict(CONFIG_FILE)
    sanitized = _sanitize_wechat_agent_config(current)
    if not CONFIG_FILE.exists() or sanitized != current:
        _write_json_dict(CONFIG_FILE, sanitized)
    return sanitized


def read_wechat_agent_config() -> dict[str, object]:
    return ensure_wechat_agent_config_file()


def update_wechat_agent_config(patch: dict[str, object]) -> dict[str, object]:
    current = ensure_wechat_agent_config_file()
    merged = dict(current)
    for key, value in patch.items():
        if key in {"public_account_origin", "list_origin", "article_capture_region"}:
            current_map = merged.get(key)
            base_map = current_map if isinstance(current_map, dict) else {}
            incoming_map = value if isinstance(value, dict) else {}
            merged[key] = {**base_map, **incoming_map}
        else:
            merged[key] = value

    sanitized = _sanitize_wechat_agent_config(merged)
    _write_json_dict(CONFIG_FILE, sanitized)
    return sanitized


def capture_wechat_agent_preview() -> dict[str, object]:
    config = ensure_wechat_agent_config_file()
    app_name = str(config.get("wechat_app_name") or "WeChat").strip()
    bundle_id = str(config.get("wechat_bundle_id") or "com.tencent.xinWeChat").strip()
    coordinate_mode = _coerce_coordinate_mode(config.get("coordinate_mode"), default="auto")
    region_raw = config.get("article_capture_region")
    region = region_raw if isinstance(region_raw, dict) else {}
    x = _coerce_int(region.get("x"), 360, 0, 10000)  # type: ignore[arg-type]
    y = _coerce_int(region.get("y"), 110, 0, 10000)  # type: ignore[arg-type]
    width = _coerce_int(region.get("width"), 1020, 60, 10000)  # type: ignore[arg-type]
    height = _coerce_int(region.get("height"), 860, 60, 10000)  # type: ignore[arg-type]
    try:
        subprocess.run(
            ["osascript", "-e", f'tell application id "{bundle_id}" to activate'],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        pass
    if coordinate_mode in {"auto", "window_relative"}:
        try:
            run = subprocess.run(
                [
                    "osascript",
                    "-e",
                    'tell application "System Events"',
                    "-e",
                    f'tell process "{app_name}"',
                    "-e",
                    "set frontmost to true",
                    "-e",
                    "set rectData to {position, size} of front window",
                    "-e",
                    "return rectData",
                    "-e",
                    "end tell",
                    "-e",
                    "end tell",
                ],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            output = (run.stdout or "").strip()
            numbers = [int(part.strip()) for part in output.replace("{", "").replace("}", "").split(",") if part.strip()]
            if len(numbers) == 4 and numbers[2] >= 600 and numbers[3] >= 400:
                x += numbers[0]
                y += numbers[1]
        except Exception:
            pass

    with tempfile.NamedTemporaryFile(prefix="wechat_agent_preview_", suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        run = subprocess.run(
            [
                "screencapture",
                "-x",
                f"-R{x},{y},{width},{height}",
                str(tmp_path),
            ],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if run.returncode != 0:
            output = "\n".join(part for part in [run.stdout.strip(), run.stderr.strip()] if part).strip()
            raise RuntimeError(output or "screencapture failed")

        binary = tmp_path.read_bytes()
        return {
            "captured_at": datetime.now(timezone.utc),
            "image_base64": base64.b64encode(binary).decode("utf-8"),
            "mime_type": "image/png",
            "region": {"x": x, "y": y, "width": width, "height": height},
            "image_size_bytes": len(binary),
        }
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def _file_mtime(path: Path) -> datetime | None:
    if not path.exists():
        return None
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def _read_processed_hashes_count() -> int:
    state = _read_wechat_agent_state()
    processed = state.get("processed_hashes") if isinstance(state, dict) else None
    if not isinstance(processed, dict):
        return 0
    return len(processed)


def _read_wechat_agent_state() -> dict[str, object]:
    if not STATE_FILE.exists():
        return {}
    try:
        loaded = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _read_recent_runs(limit: int = 5) -> list[dict[str, object]]:
    state = _read_wechat_agent_state()
    runs = state.get("runs") if isinstance(state, dict) else None
    if not isinstance(runs, list):
        return []
    cleaned: list[dict[str, object]] = []
    for raw in runs[-max(1, min(limit, 500)):]:
        if isinstance(raw, dict):
            cleaned.append(raw)
    return cleaned


def _read_live_report_snapshot() -> dict[str, object]:
    snapshot: dict[str, object] = {
        "live_report_running": False,
        "live_report_batch": None,
        "live_report_row": None,
        "live_report_stage": None,
        "live_report_detail": None,
        "live_report_clicked": 0,
        "live_report_submitted": 0,
        "live_report_submitted_url": 0,
        "live_report_submitted_url_direct": 0,
        "live_report_submitted_url_share_copy": 0,
        "live_report_submitted_url_resolved": 0,
        "live_report_submitted_ocr": 0,
        "live_report_skipped_seen": 0,
        "live_report_skipped_invalid_article": 0,
        "live_report_failed": 0,
        "live_report_checkpoint_at": None,
    }
    if not REPORT_FILE.exists():
        return snapshot
    try:
        loaded = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return snapshot
    if not isinstance(loaded, dict):
        return snapshot

    snapshot["live_report_running"] = bool(loaded.get("running"))
    snapshot["live_report_clicked"] = _coerce_int(loaded.get("clicked"), 0, 0, 1_000_000)
    snapshot["live_report_submitted"] = _coerce_int(loaded.get("submitted"), 0, 0, 1_000_000)
    snapshot["live_report_submitted_url"] = _coerce_int(loaded.get("submitted_url"), 0, 0, 1_000_000)
    snapshot["live_report_submitted_url_direct"] = _coerce_int(
        loaded.get("submitted_url_direct"),
        0,
        0,
        1_000_000,
    )
    snapshot["live_report_submitted_url_share_copy"] = _coerce_int(
        loaded.get("submitted_url_share_copy"),
        0,
        0,
        1_000_000,
    )
    snapshot["live_report_submitted_url_resolved"] = _coerce_int(
        loaded.get("submitted_url_resolved"),
        0,
        0,
        1_000_000,
    )
    snapshot["live_report_submitted_ocr"] = _coerce_int(loaded.get("submitted_ocr"), 0, 0, 1_000_000)
    snapshot["live_report_skipped_seen"] = _coerce_int(loaded.get("skipped_seen"), 0, 0, 1_000_000)
    snapshot["live_report_skipped_invalid_article"] = _coerce_int(
        loaded.get("skipped_invalid_article"),
        0,
        0,
        1_000_000,
    )
    snapshot["live_report_failed"] = _coerce_int(loaded.get("failed"), 0, 0, 1_000_000)
    snapshot["live_report_checkpoint_at"] = _parse_dt(loaded.get("last_checkpoint_at"))

    stage_logs = loaded.get("stage_logs")
    if isinstance(stage_logs, list):
        for value in reversed(stage_logs):
            if not isinstance(value, dict):
                continue
            batch = _coerce_int(value.get("batch"), 0, 0, 10_000) or None
            row = _coerce_int(value.get("row"), 0, 0, 1_000) or None
            stage = str(value.get("stage")).strip() if value.get("stage") else None
            detail = str(value.get("detail")).strip() if value.get("detail") else None
            snapshot["live_report_batch"] = batch
            snapshot["live_report_row"] = row
            snapshot["live_report_stage"] = stage
            snapshot["live_report_detail"] = detail
            break
    return snapshot


def read_wechat_agent_dedup_summary() -> WechatAgentDedupStateSummary:
    processed_hashes = _read_processed_hashes_count()
    all_runs = _read_recent_runs(limit=500)
    last_run = all_runs[-1] if all_runs else {}
    return WechatAgentDedupStateSummary(
        processed_hashes=processed_hashes,
        run_count=len(all_runs),
        last_run_started_at=_parse_dt(last_run.get("started_at")) if isinstance(last_run, dict) else None,
        last_run_finished_at=_parse_dt(last_run.get("finished_at")) if isinstance(last_run, dict) else None,
        last_run_submitted=_coerce_int(last_run.get("submitted") if isinstance(last_run, dict) else 0, 0, 0, 1_000_000),
        last_run_skipped_seen=_coerce_int(
            last_run.get("skipped_seen") if isinstance(last_run, dict) else 0,
            0,
            0,
            1_000_000,
        ),
        last_run_failed=_coerce_int(last_run.get("failed") if isinstance(last_run, dict) else 0, 0, 0, 1_000_000),
        last_run_item_ids=[
            str(value).strip()
            for value in (last_run.get("item_ids") if isinstance(last_run, dict) and isinstance(last_run.get("item_ids"), list) else [])
            if str(value or "").strip()
        ][:24],
    )


def reset_wechat_agent_dedup_state(*, clear_runs: bool = False) -> WechatAgentDedupStateSummary:
    current_status = read_wechat_agent_status()
    current_batch = read_wechat_agent_batch_status()
    if current_status.running or current_status.run_once_running or current_batch.running:
        raise RuntimeError("wechat pc agent is busy; stop current run before resetting dedup state")

    state = _read_wechat_agent_state()
    state["processed_hashes"] = {}
    if clear_runs:
        state["runs"] = []
    _write_json_dict(STATE_FILE, state)
    return read_wechat_agent_dedup_summary()


def _read_last_cycle_at() -> datetime | None:
    if not REPORT_FILE.exists():
        return None
    try:
        loaded = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _file_mtime(REPORT_FILE)
    if not isinstance(loaded, dict):
        return _file_mtime(REPORT_FILE)
    finished_at = loaded.get("finished_at")
    if not isinstance(finished_at, str) or not finished_at.strip():
        return _file_mtime(REPORT_FILE)
    try:
        return datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
    except ValueError:
        return _file_mtime(REPORT_FILE)


def _read_last_cycle_metrics() -> dict[str, object]:
    output: dict[str, object] = {
        "submitted": 0,
        "submitted_new": 0,
        "deduplicated_existing": 0,
        "failed": 0,
        "skipped_seen": 0,
        "skipped_low_quality": 0,
        "first_error": None,
        "new_item_ids": [],
    }
    if not REPORT_FILE.exists():
        return output
    try:
        loaded = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return output
    if not isinstance(loaded, dict):
        return output

    output["submitted"] = _coerce_int(loaded.get("submitted"), 0, 0, 1_000_000)
    output["submitted_new"] = _coerce_int(loaded.get("submitted_new"), 0, 0, 1_000_000)
    output["deduplicated_existing"] = _coerce_int(loaded.get("deduplicated_existing"), 0, 0, 1_000_000)
    output["failed"] = _coerce_int(loaded.get("failed"), 0, 0, 1_000_000)
    output["skipped_seen"] = _coerce_int(loaded.get("skipped_seen"), 0, 0, 1_000_000)
    output["skipped_low_quality"] = _coerce_int(
        loaded.get("skipped_low_quality"),
        0,
        0,
        1_000_000,
    )
    errors = loaded.get("errors")
    if isinstance(errors, list):
        for value in errors:
            text = str(value or "").strip()
            if text:
                output["first_error"] = text
                break
    item_ids = loaded.get("new_item_ids")
    if isinstance(item_ids, list):
        output["new_item_ids"] = [str(value).strip() for value in item_ids if str(value or "").strip()][:24]
    return output


def read_wechat_agent_status() -> WechatAgentStatus:
    running_pid, pid_from_file, pid_file_present = _resolve_running_pid()
    running = running_pid is not None and _pid_alive(running_pid)
    run_once_pid, _, _ = _resolve_run_once_pid()
    run_once_running = run_once_pid is not None and _pid_alive(run_once_pid)
    if not run_once_running and RUN_ONCE_PID_FILE.exists():
        try:
            RUN_ONCE_PID_FILE.unlink()
        except OSError:
            pass

    ensure_wechat_agent_config_file()
    metrics = _read_last_cycle_metrics()
    uptime_seconds = _get_uptime_seconds(running_pid if running else None)
    log_size = 0
    if LOG_FILE.exists():
        try:
            log_size = int(LOG_FILE.stat().st_size)
        except OSError:
            log_size = 0

    return WechatAgentStatus(
        running=running,
        pid=running_pid if running else None,
        pid_from_file=pid_from_file,
        pid_file_present=pid_file_present,
        run_once_running=run_once_running,
        run_once_pid=run_once_pid if run_once_running else None,
        uptime_seconds=uptime_seconds,
        config_file=str(CONFIG_FILE),
        config_file_present=CONFIG_FILE.exists(),
        state_file=str(STATE_FILE),
        state_file_present=STATE_FILE.exists(),
        report_file=str(REPORT_FILE),
        report_file_present=REPORT_FILE.exists(),
        processed_hashes=_read_processed_hashes_count(),
        last_cycle_at=_read_last_cycle_at(),
        last_cycle_submitted=int(metrics.get("submitted") or 0),
        last_cycle_submitted_new=int(metrics.get("submitted_new") or 0),
        last_cycle_deduplicated_existing=int(metrics.get("deduplicated_existing") or 0),
        last_cycle_failed=int(metrics.get("failed") or 0),
        last_cycle_skipped_seen=int(metrics.get("skipped_seen") or 0),
        last_cycle_skipped_low_quality=int(metrics.get("skipped_low_quality") or 0),
        last_cycle_error=(str(metrics.get("first_error")).strip() if metrics.get("first_error") else None),
        last_cycle_new_item_ids=list(metrics.get("new_item_ids") or []),
        log_file=str(LOG_FILE),
        log_size_bytes=log_size,
        log_tail=_tail_log(),
    )


def _ensure_script(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"script not found: {path}")


def _run_command(
    command: list[str],
    timeout_sec: int,
    env_overrides: dict[str, str] | None = None,
) -> tuple[bool, str]:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    run = subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        check=False,
    )
    output = "\n".join(part for part in [run.stdout.strip(), run.stderr.strip()] if part).strip()
    return run.returncode == 0, output


def _clip_output(output: str | None, max_chars: int = 2200) -> str | None:
    text = (output or "").strip()
    if not text:
        return None
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _build_run_once_command(
    *,
    output_language: str,
    max_items: int,
    start_batch_index: int,
) -> list[str]:
    safe_max_items = max(1, min(max_items, 200))
    safe_start_batch_index = max(0, min(start_batch_index, 1_000))
    return [
        "python3",
        str(AGENT_SCRIPT),
        "--config",
        str(CONFIG_FILE),
        "--state-file",
        str(STATE_FILE),
        "--report-file",
        str(REPORT_FILE),
        "--max-items",
        str(safe_max_items),
        "--start-batch-index",
        str(safe_start_batch_index),
        "--output-language",
        output_language,
    ]


def _terminate_process(process: subprocess.Popen[str], *, grace_seconds: float = 2.0) -> None:
    if process.poll() is not None:
        return
    try:
        process.terminate()
    except Exception:
        return
    deadline = datetime.now(timezone.utc) + timedelta(seconds=grace_seconds)
    while process.poll() is None and datetime.now(timezone.utc) < deadline:
        time.sleep(0.1)
    if process.poll() is None:
        try:
            process.kill()
        except Exception:
            return


def _run_segment_process(command: list[str], *, stop_event: Event) -> tuple[bool, bool, str]:
    global _batch_process
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            cwd=str(PROJECT_ROOT),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
    RUN_ONCE_PID_FILE.write_text(str(process.pid), encoding="utf-8")
    _batch_process = process
    aborted = False
    try:
        while process.poll() is None:
            if stop_event.is_set():
                aborted = True
                _terminate_process(process)
                break
            stop_event.wait(0.25)
        return process.returncode == 0, aborted, f"pid={process.pid} rc={process.returncode}"
    finally:
        if RUN_ONCE_PID_FILE.exists():
            try:
                current = RUN_ONCE_PID_FILE.read_text(encoding="utf-8").strip()
            except OSError:
                current = ""
            if current == str(process.pid):
                try:
                    RUN_ONCE_PID_FILE.unlink()
                except OSError:
                    pass
        _batch_process = None


def start_wechat_agent() -> WechatAgentCommandResult:
    _ensure_script(START_SCRIPT)
    config = ensure_wechat_agent_config_file()
    interval_sec = _coerce_int(config.get("loop_interval_sec"), 300, 20, 3600)
    ok, output = _run_command(
        ["bash", str(START_SCRIPT)],
        timeout_sec=45,
        env_overrides={"WECHAT_AGENT_INTERVAL_SEC": str(interval_sec)},
    )
    status = read_wechat_agent_status()
    final_ok = ok and status.running
    message = (
        f"wechat pc agent running (interval={interval_sec}s)"
        if status.running
        else "start command finished, but agent is not running"
    )
    return WechatAgentCommandResult(
        action="start",
        ok=final_ok,
        message=message,
        status=status,
        output=_clip_output(output),
    )


def stop_wechat_agent() -> WechatAgentCommandResult:
    global _batch_stop_event, _batch_process, _batch_thread
    if _batch_stop_event is not None:
        _batch_stop_event.set()
    if _batch_process is not None and _batch_process.poll() is None:
        _terminate_process(_batch_process)
    if _batch_thread is not None and _batch_thread.is_alive():
        _batch_thread.join(timeout=4.0)
    _ensure_script(STOP_SCRIPT)
    ok, output = _run_command(["bash", str(STOP_SCRIPT)], timeout_sec=45)
    if RUN_ONCE_PID_FILE.exists():
        try:
            RUN_ONCE_PID_FILE.unlink()
        except OSError:
            pass
    status = read_wechat_agent_status()
    batch_status = read_wechat_agent_batch_status()
    final_ok = ok and (not status.running) and (not status.run_once_running) and (not batch_status.running)
    if batch_status.running:
        _write_wechat_agent_batch_status(
            {
                **_serialize_batch_status_payload(_sanitize_batch_status_payload(_read_json_dict(BATCH_STATUS_FILE))),
                "running": False,
                "finished_at": datetime.now(timezone.utc),
                "last_message": "wechat pc agent batch stopped",
                "last_error": batch_status.last_error,
            }
        )
    with _batch_lock:
        if _batch_thread is not None and not _batch_thread.is_alive():
            _batch_thread = None
        _batch_stop_event = None
        _batch_process = None
    message = "wechat pc agent stopped" if not status.running else "stop command finished, but agent still running"
    return WechatAgentCommandResult(
        action="stop",
        ok=final_ok,
        message=message,
        status=status,
        output=_clip_output(output),
    )


def run_wechat_agent_once(
    *,
    output_language: str = "zh-CN",
    max_items: int = 12,
    start_batch_index: int = 0,
    wait: bool = False,
) -> WechatAgentCommandResult:
    _ensure_script(AGENT_SCRIPT)
    ensure_wechat_agent_config_file()
    current_status = read_wechat_agent_status()
    if current_status.running:
        return WechatAgentCommandResult(
            action="run_once",
            ok=False,
            message="wechat pc agent loop is running; stop it before run_once",
            status=current_status,
            output=None,
        )
    if current_status.run_once_running:
        return WechatAgentCommandResult(
            action="run_once",
            ok=False,
            message="wechat pc agent run_once already in progress",
            status=current_status,
            output=f"pid={current_status.run_once_pid}",
        )

    safe_max_items = max(1, min(max_items, 200))
    safe_start_batch_index = max(0, min(start_batch_index, 1_000))
    command = _build_run_once_command(
        output_language=output_language,
        max_items=safe_max_items,
        start_batch_index=safe_start_batch_index,
    )
    if not wait:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                command,
                cwd=str(PROJECT_ROOT),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
        RUN_ONCE_PID_FILE.write_text(str(process.pid), encoding="utf-8")
        status = read_wechat_agent_status()
        return WechatAgentCommandResult(
            action="run_once",
            ok=True,
            message="wechat pc agent single cycle started",
            status=status,
            output=f"pid={process.pid}",
        )

    try:
        ok, output = _run_command(command, timeout_sec=720)
        status = read_wechat_agent_status()
        message = "wechat pc agent single cycle completed" if ok else "wechat pc agent single cycle failed"
        return WechatAgentCommandResult(
            action="run_once",
            ok=ok,
            message=message,
            status=status,
            output=_clip_output(output),
        )
    except subprocess.TimeoutExpired:
        status = read_wechat_agent_status()
        return WechatAgentCommandResult(
            action="run_once",
            ok=False,
            message="wechat pc agent single cycle timeout",
            status=status,
            output="timeout after 720 seconds",
        )


def run_wechat_agent_batch(
    *,
    output_language: str = "zh-CN",
    total_items: int = 50,
    segment_items: int = 10,
    start_batch_index: int = 0,
) -> WechatAgentBatchCommandResult:
    global _batch_thread, _batch_stop_event

    _ensure_script(AGENT_SCRIPT)
    config = ensure_wechat_agent_config_file()
    current_status = read_wechat_agent_status()
    current_batch = read_wechat_agent_batch_status()
    if current_status.running:
        return WechatAgentBatchCommandResult(
            ok=False,
            message="wechat pc agent loop is running; stop it before run_batch",
            batch_status=current_batch,
        )
    if current_status.run_once_running:
        return WechatAgentBatchCommandResult(
            ok=False,
            message="wechat pc agent run_once already in progress",
            batch_status=current_batch,
        )
    if current_batch.running and _batch_thread is not None and _batch_thread.is_alive():
        return WechatAgentBatchCommandResult(
            ok=False,
            message="wechat pc agent segmented batch already in progress",
            batch_status=current_batch,
        )

    safe_total_items = max(1, min(total_items, 200))
    safe_segment_items = max(1, min(segment_items, safe_total_items, 100))
    safe_start_batch_index = max(0, min(start_batch_index, 1_000))
    rows_per_batch = _coerce_int(config.get("rows_per_batch"), 1, 1, 20)
    batches_per_segment = max(1, (safe_segment_items + rows_per_batch - 1) // rows_per_batch)
    total_segments = max(1, (safe_total_items + safe_segment_items - 1) // safe_segment_items)

    initial_payload: dict[str, object] = {
        "running": True,
        "total_items": safe_total_items,
        "segment_items": safe_segment_items,
        "start_batch_index": safe_start_batch_index,
        "current_segment_index": 0,
        "total_segments": total_segments,
        "current_batch_index": safe_start_batch_index,
        "started_at": datetime.now(timezone.utc),
        "finished_at": None,
        "submitted": 0,
        "submitted_new": 0,
        "submitted_url": 0,
        "submitted_url_direct": 0,
        "submitted_url_share_copy": 0,
        "submitted_url_resolved": 0,
        "submitted_ocr": 0,
        "deduplicated_existing": 0,
        "deduplicated_existing_url": 0,
        "deduplicated_existing_url_direct": 0,
        "deduplicated_existing_url_share_copy": 0,
        "deduplicated_existing_url_resolved": 0,
        "deduplicated_existing_ocr": 0,
        "skipped_invalid_article": 0,
        "skipped_seen": 0,
        "failed": 0,
        "validation_retries": 0,
        "new_item_ids": [],
        "last_message": "wechat pc agent segmented batch started",
        "last_error": None,
    }

    stop_event = Event()

    def worker() -> None:
        global _batch_thread, _batch_stop_event
        payload = dict(initial_payload)
        try:
            _write_wechat_agent_batch_status(payload)
            remaining = safe_total_items
            next_batch_index = safe_start_batch_index
            collected_new_ids: list[str] = []
            last_error: str | None = None

            for segment_index in range(total_segments):
                if stop_event.is_set():
                    payload["running"] = False
                    payload["finished_at"] = datetime.now(timezone.utc)
                    payload["last_message"] = "wechat pc agent segmented batch stopped"
                    payload["last_error"] = last_error
                    _write_wechat_agent_batch_status(payload)
                    return

                current_items = min(safe_segment_items, remaining)
                payload["current_segment_index"] = segment_index + 1
                payload["current_batch_index"] = next_batch_index
                payload["last_message"] = (
                    f"running segment {segment_index + 1}/{total_segments} "
                    f"(start_batch={next_batch_index}, items={current_items})"
                )
                _write_wechat_agent_batch_status(payload)

                command = _build_run_once_command(
                    output_language=output_language,
                    max_items=current_items,
                    start_batch_index=next_batch_index,
                )
                ok, aborted, output = _run_segment_process(command, stop_event=stop_event)
                status = read_wechat_agent_status()
                latest_report = _read_json_dict(REPORT_FILE)
                payload["submitted"] = int(payload["submitted"]) + int(status.last_cycle_submitted or 0)
                payload["submitted_new"] = int(payload["submitted_new"]) + int(status.last_cycle_submitted_new or 0)
                payload["submitted_url"] = int(payload["submitted_url"]) + int(
                    _coerce_int(latest_report.get("submitted_url"), 0, 0, 1_000_000)
                )
                payload["submitted_url_direct"] = int(payload["submitted_url_direct"]) + int(
                    _coerce_int(latest_report.get("submitted_url_direct"), 0, 0, 1_000_000)
                )
                payload["submitted_url_share_copy"] = int(payload["submitted_url_share_copy"]) + int(
                    _coerce_int(latest_report.get("submitted_url_share_copy"), 0, 0, 1_000_000)
                )
                payload["submitted_url_resolved"] = int(payload["submitted_url_resolved"]) + int(
                    _coerce_int(latest_report.get("submitted_url_resolved"), 0, 0, 1_000_000)
                )
                payload["submitted_ocr"] = int(payload["submitted_ocr"]) + int(
                    _coerce_int(latest_report.get("submitted_ocr"), 0, 0, 1_000_000)
                )
                payload["deduplicated_existing"] = int(payload["deduplicated_existing"]) + int(
                    status.last_cycle_deduplicated_existing or 0
                )
                payload["deduplicated_existing_url"] = int(payload["deduplicated_existing_url"]) + int(
                    _coerce_int(latest_report.get("deduplicated_existing_url"), 0, 0, 1_000_000)
                )
                payload["deduplicated_existing_url_direct"] = int(payload["deduplicated_existing_url_direct"]) + int(
                    _coerce_int(latest_report.get("deduplicated_existing_url_direct"), 0, 0, 1_000_000)
                )
                payload["deduplicated_existing_url_share_copy"] = int(payload["deduplicated_existing_url_share_copy"]) + int(
                    _coerce_int(latest_report.get("deduplicated_existing_url_share_copy"), 0, 0, 1_000_000)
                )
                payload["deduplicated_existing_url_resolved"] = int(payload["deduplicated_existing_url_resolved"]) + int(
                    _coerce_int(latest_report.get("deduplicated_existing_url_resolved"), 0, 0, 1_000_000)
                )
                payload["deduplicated_existing_ocr"] = int(payload["deduplicated_existing_ocr"]) + int(
                    _coerce_int(latest_report.get("deduplicated_existing_ocr"), 0, 0, 1_000_000)
                )
                payload["skipped_seen"] = int(payload["skipped_seen"]) + int(status.last_cycle_skipped_seen or 0)
                payload["failed"] = int(payload["failed"]) + int(status.last_cycle_failed or 0)
                payload["validation_retries"] = int(payload["validation_retries"]) + int(
                    _coerce_int(latest_report.get("validation_retries"), 0, 0, 1_000_000)
                )
                payload["skipped_invalid_article"] = int(payload["skipped_invalid_article"]) + int(
                    _coerce_int(latest_report.get("skipped_invalid_article"), 0, 0, 1_000_000)
                )
                latest_new_ids = [str(value).strip() for value in status.last_cycle_new_item_ids if str(value).strip()]
                for item_id in latest_new_ids:
                    if item_id not in collected_new_ids:
                        collected_new_ids.append(item_id)
                payload["new_item_ids"] = collected_new_ids[-64:]
                payload["last_message"] = (
                    "wechat pc agent segmented batch stopped"
                    if aborted
                    else ("wechat pc agent single cycle completed" if ok else "wechat pc agent single cycle failed")
                )
                if aborted:
                    payload["running"] = False
                    payload["finished_at"] = datetime.now(timezone.utc)
                    payload["last_error"] = None
                    current_state = _read_wechat_agent_state()
                    current_state["loop_next_batch_index"] = next_batch_index
                    _write_json_dict(STATE_FILE, current_state)
                    _write_wechat_agent_batch_status(payload)
                    return
                if not ok:
                    last_error = output or status.last_cycle_error or payload["last_message"]
                    payload["last_error"] = last_error
                    payload["running"] = False
                    payload["finished_at"] = datetime.now(timezone.utc)
                    current_state = _read_wechat_agent_state()
                    current_state["loop_next_batch_index"] = next_batch_index
                    _write_json_dict(STATE_FILE, current_state)
                    _write_wechat_agent_batch_status(payload)
                    return

                remaining -= current_items
                next_batch_index += batches_per_segment
                current_state = _read_wechat_agent_state()
                current_state["loop_next_batch_index"] = next_batch_index
                _write_json_dict(STATE_FILE, current_state)
                _write_wechat_agent_batch_status(payload)

            payload["running"] = False
            payload["finished_at"] = datetime.now(timezone.utc)
            payload["last_message"] = "wechat pc agent segmented batch completed"
            payload["last_error"] = last_error
            _write_wechat_agent_batch_status(payload)
        finally:
            with _batch_lock:
                _batch_thread = None
                _batch_stop_event = None

    with _batch_lock:
        _batch_stop_event = stop_event
        _batch_thread = Thread(target=worker, name="wechat-agent-batch", daemon=True)
        _batch_thread.start()

    return WechatAgentBatchCommandResult(
        ok=True,
        message="wechat pc agent segmented batch started",
        batch_status=_batch_status_from_payload(initial_payload),
    )


def get_wechat_agent_health_report(stale_threshold_minutes: int | None = None) -> WechatAgentHealthReport:
    config = ensure_wechat_agent_config_file()
    threshold = _coerce_int(
        stale_threshold_minutes if stale_threshold_minutes is not None else config.get("health_stale_minutes"),
        20,
        3,
        240,
    )
    status = read_wechat_agent_status()
    now = datetime.now(timezone.utc)

    reasons: list[str] = []
    minutes_since_last_cycle: float | None = None
    if status.last_cycle_at:
        delta = now - status.last_cycle_at
        minutes_since_last_cycle = max(0.0, round(delta.total_seconds() / 60.0, 2))

    if not status.running:
        reasons.append("not_running")
    else:
        if status.last_cycle_at is None and (status.uptime_seconds or 0) > threshold * 60:
            reasons.append("no_cycle_report")
        if minutes_since_last_cycle is not None and minutes_since_last_cycle > threshold:
            reasons.append("cycle_stale")
        if status.last_cycle_submitted == 0 and status.last_cycle_failed > 0:
            reasons.append("last_cycle_failed")

    healthy = len(reasons) == 0
    recommendation: str | None = None
    if not healthy:
        if "not_running" in reasons:
            recommendation = "start"
        else:
            recommendation = "restart"

    return WechatAgentHealthReport(
        healthy=healthy,
        checked_at=now,
        stale_threshold_minutes=threshold,
        running=status.running,
        last_cycle_at=status.last_cycle_at,
        minutes_since_last_cycle=minutes_since_last_cycle,
        reasons=reasons,
        recommendation=recommendation,
        status=status,
    )


def self_heal_wechat_agent(*, force: bool = False) -> WechatAgentSelfHealResult:
    health_before = get_wechat_agent_health_report()
    batch_status = read_wechat_agent_batch_status()
    if (health_before.status.run_once_running or batch_status.running) and not force:
        message = "wechat pc agent batch/run_once in progress, skip self-heal"
        return WechatAgentSelfHealResult(
            ok=True,
            action="none",
            message=message,
            health_before=health_before,
            health_after=health_before,
            output=None,
        )
    if health_before.healthy and not force:
        return WechatAgentSelfHealResult(
            ok=True,
            action="none",
            message="wechat pc agent healthy, no heal needed",
            health_before=health_before,
            health_after=health_before,
            output=None,
        )

    output_parts: list[str] = []
    action: Literal["none", "start", "restart"] = "none"

    if not health_before.status.running:
        action = "start"
        start_result = start_wechat_agent()
        output_parts.append(f"[start] {start_result.message}")
        if start_result.output:
            output_parts.append(start_result.output)
    else:
        action = "restart"
        stop_result = stop_wechat_agent()
        output_parts.append(f"[stop] {stop_result.message}")
        if stop_result.output:
            output_parts.append(stop_result.output)
        start_result = start_wechat_agent()
        output_parts.append(f"[start] {start_result.message}")
        if start_result.output:
            output_parts.append(start_result.output)

    health_after = get_wechat_agent_health_report(health_before.stale_threshold_minutes)
    ok = health_after.healthy or (health_after.running and (health_after.last_cycle_at is not None))
    message = "wechat pc agent self-heal completed" if ok else "wechat pc agent self-heal attempted but still unhealthy"
    return WechatAgentSelfHealResult(
        ok=ok,
        action=action,
        message=message,
        health_before=health_before,
        health_after=health_after,
        output=_clip_output("\n".join(part for part in output_parts if part)),
    )


def format_uptime(uptime_seconds: int | None) -> str:
    if uptime_seconds is None:
        return "-"
    if uptime_seconds < 60:
        return f"{uptime_seconds}s"
    delta = timedelta(seconds=uptime_seconds)
    total = int(delta.total_seconds())
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    return f"{minutes}m {seconds}s"
