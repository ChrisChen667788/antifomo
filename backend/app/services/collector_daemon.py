from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
from typing import Literal


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TMP_DIR = PROJECT_ROOT / ".tmp"

PID_FILE = TMP_DIR / "collector.pid"
LOG_FILE = TMP_DIR / "collector.log"
SOURCE_FILE = TMP_DIR / "wechat_collector_sources.txt"
STATE_FILE = TMP_DIR / "wechat_collector_state.json"
REPORT_FILE = TMP_DIR / "wechat_collector_latest.md"
DAILY_REPORT_FILE = TMP_DIR / "collector_daily_summary.md"

START_SCRIPT = PROJECT_ROOT / "scripts" / "start_collector.sh"
STOP_SCRIPT = PROJECT_ROOT / "scripts" / "stop_collector.sh"
COLLECTOR_SCRIPT = PROJECT_ROOT / "scripts" / "desktop_wechat_collector.mjs"


@dataclass(slots=True)
class CollectorDaemonStatus:
    running: bool
    pid: int | None
    pid_from_file: int | None
    pid_file_present: bool
    uptime_seconds: int | None
    last_report_at: datetime | None
    last_daily_summary_at: datetime | None
    log_file: str
    log_size_bytes: int
    source_file_count: int
    log_tail: list[str]


@dataclass(slots=True)
class CollectorDaemonCommandResult:
    action: Literal["start", "stop", "run_once"]
    ok: bool
    message: str
    status: CollectorDaemonStatus
    output: str | None = None


def _parse_pid(value: str | None) -> int | None:
    text = str(value or "").strip()
    if not text or not text.isdigit():
        return None
    pid = int(text)
    if pid <= 1:
        return None
    return pid


def _read_pid_file() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        return _parse_pid(PID_FILE.read_text(encoding="utf-8"))
    except OSError:
        return None


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _find_collector_pid_by_pgrep() -> int | None:
    pattern = f"{COLLECTOR_SCRIPT}.*--loop"
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


def _resolve_running_pid() -> tuple[int | None, int | None, bool]:
    pid_file_present = PID_FILE.exists()
    pid_from_file = _read_pid_file()
    if _pid_alive(pid_from_file):
        return pid_from_file, pid_from_file, pid_file_present
    return _find_collector_pid_by_pgrep(), pid_from_file, pid_file_present


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
    text = run.stdout.strip()
    if not text:
        return None

    # ps etime format: [[dd-]hh:]mm:ss
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


def _file_mtime(path: Path) -> datetime | None:
    if not path.exists():
        return None
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def _count_source_file_urls() -> int:
    if not SOURCE_FILE.exists():
        return 0
    try:
        lines = SOURCE_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0
    return sum(1 for line in lines if line.strip() and not line.lstrip().startswith("#"))


def _tail_log(max_lines: int = 14, max_chars: int = 2800) -> list[str]:
    if not LOG_FILE.exists():
        return []
    try:
        lines = LOG_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []

    if not lines:
        return []
    selected = [line.strip() for line in lines[-max_lines:] if line.strip()]
    if not selected:
        return []

    while selected and sum(len(line) for line in selected) > max_chars:
        selected = selected[1:]
    return selected


def read_collector_daemon_status() -> CollectorDaemonStatus:
    running_pid, pid_from_file, pid_file_present = _resolve_running_pid()
    running = running_pid is not None and _pid_alive(running_pid)
    uptime_seconds = _get_uptime_seconds(running_pid if running else None)
    log_size = 0
    if LOG_FILE.exists():
        try:
            log_size = int(LOG_FILE.stat().st_size)
        except OSError:
            log_size = 0

    return CollectorDaemonStatus(
        running=running,
        pid=running_pid if running else None,
        pid_from_file=pid_from_file,
        pid_file_present=pid_file_present,
        uptime_seconds=uptime_seconds,
        last_report_at=_file_mtime(REPORT_FILE),
        last_daily_summary_at=_file_mtime(DAILY_REPORT_FILE),
        log_file=str(LOG_FILE),
        log_size_bytes=log_size,
        source_file_count=_count_source_file_urls(),
        log_tail=_tail_log(),
    )


def _ensure_script(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"script not found: {path}")


def _run_command(command: list[str], timeout_sec: int) -> tuple[bool, str]:
    run = subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
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


def start_collector_daemon() -> CollectorDaemonCommandResult:
    _ensure_script(START_SCRIPT)
    ok, output = _run_command(["bash", str(START_SCRIPT)], timeout_sec=45)
    status = read_collector_daemon_status()
    final_ok = ok and status.running
    message = "collector running" if status.running else "collector start command completed, daemon not running"
    return CollectorDaemonCommandResult(
        action="start",
        ok=final_ok,
        message=message,
        status=status,
        output=_clip_output(output),
    )


def stop_collector_daemon() -> CollectorDaemonCommandResult:
    _ensure_script(STOP_SCRIPT)
    ok, output = _run_command(["bash", str(STOP_SCRIPT)], timeout_sec=45)
    status = read_collector_daemon_status()
    final_ok = ok and (not status.running)
    message = "collector stopped" if not status.running else "collector stop command completed, daemon still running"
    return CollectorDaemonCommandResult(
        action="stop",
        ok=final_ok,
        message=message,
        status=status,
        output=_clip_output(output),
    )


def run_collector_once(
    *,
    output_language: str = "zh-CN",
    max_collect_per_cycle: int = 30,
) -> CollectorDaemonCommandResult:
    _ensure_script(COLLECTOR_SCRIPT)
    command = [
        "node",
        str(COLLECTOR_SCRIPT),
        "--source-file",
        str(SOURCE_FILE),
        "--state-file",
        str(STATE_FILE),
        "--report-file",
        str(REPORT_FILE),
        "--language",
        output_language,
        "--max-collect",
        str(max(5, min(max_collect_per_cycle, 200))),
        "--flush-limit",
        "80",
        "--daily-hours",
        "24",
        "--daily-limit",
        "12",
        "--daily-report",
        str(DAILY_REPORT_FILE),
    ]
    try:
        ok, output = _run_command(command, timeout_sec=420)
        status = read_collector_daemon_status()
        message = "collector single cycle completed" if ok else "collector single cycle failed"
        return CollectorDaemonCommandResult(
            action="run_once",
            ok=ok,
            message=message,
            status=status,
            output=_clip_output(output),
        )
    except subprocess.TimeoutExpired:
        status = read_collector_daemon_status()
        return CollectorDaemonCommandResult(
            action="run_once",
            ok=False,
            message="collector single cycle timeout",
            status=status,
            output="timeout after 420 seconds",
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
