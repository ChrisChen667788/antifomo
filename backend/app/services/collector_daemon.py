from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Literal


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TMP_DIR = PROJECT_ROOT / ".tmp"

PID_FILE = TMP_DIR / "collector.pid"
LOG_FILE = TMP_DIR / "collector.log"
SOURCE_FILE = TMP_DIR / "wechat_collector_sources.txt"
STATE_FILE = TMP_DIR / "wechat_collector_state.json"
REPORT_FILE = TMP_DIR / "wechat_collector_latest.md"
DAILY_REPORT_FILE = TMP_DIR / "collector_daily_summary.md"
CONFIG_FILE = TMP_DIR / "wechat_collector_config.json"
BROWSER_EXTENSION_DIR = PROJECT_ROOT / "browser-extension" / "chrome"
BROWSER_EXTENSION_MANIFEST = BROWSER_EXTENSION_DIR / "manifest.json"
BROWSER_EXTENSION_README = PROJECT_ROOT / "browser-extension" / "README.md"
BROWSER_EXTENSION_VERIFY_SCRIPT = PROJECT_ROOT / "scripts" / "chrome_plugin_pipeline_validate.mjs"
BROWSER_EXTENSION_VERIFY_REPORT = TMP_DIR / "chrome_plugin_pipeline_verify.md"
BROWSER_EXTENSION_VERIFY_STATE = TMP_DIR / "browser_extension_verification.json"

START_SCRIPT = PROJECT_ROOT / "scripts" / "start_collector.sh"
STOP_SCRIPT = PROJECT_ROOT / "scripts" / "stop_collector.sh"
COLLECTOR_SCRIPT = PROJECT_ROOT / "scripts" / "desktop_wechat_collector.mjs"

DEFAULT_COLLECTOR_CONFIG: dict[str, Any] = {
    "wechat_clipboard_auto_import": True,
    "wechat_export_directory_auto_import": True,
    "wechat_export_directory_path": str(TMP_DIR / "wechat_favorites_inbox"),
}


@dataclass(slots=True)
class CollectorSourceHealth:
    source_url: str
    source_token: str
    scanned: bool
    health_state: str
    recommendation: str
    discovered_count: int
    handled_count: int
    collected_count: int
    plugin_count: int
    url_count: int
    skipped_seen_count: int
    failed_count: int
    coverage_rate: float
    body_success_rate: float
    last_error: str | None


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
    last_run_at: datetime | None
    last_run_submit_mode: str | None
    last_run_discovered_count: int
    last_run_collected_count: int
    last_run_plugin_count: int
    last_run_url_count: int
    last_run_failed_count: int
    last_run_skipped_seen_count: int
    last_run_handled_count: int
    last_run_coverage_rate: float
    last_run_body_success_rate: float
    coverage_state: str
    coverage_recommendation: str
    poor_source_count: int
    watch_source_count: int
    favorites_auto_status: str
    favorites_auto_available: bool
    favorites_auto_last_at: datetime | None
    favorites_auto_discovered_count: int
    favorites_auto_imported_count: int
    favorites_auto_deduplicated_count: int
    favorites_auto_message: str
    favorites_clipboard_auto_enabled: bool
    favorites_clipboard_adapter_available: bool
    favorites_clipboard_last_message: str
    favorites_export_directory_auto_enabled: bool
    favorites_export_directory_path: str
    favorites_export_directory_adapter_available: bool
    favorites_export_directory_last_message: str
    favorites_export_directory_last_processed_count: int
    favorites_wechat_cli_adapter_available: bool
    favorites_wechat_cli_last_message: str
    browser_extension_path: str
    browser_extension_manifest_present: bool
    browser_extension_readme_path: str
    browser_extension_pipeline_script: str
    browser_extension_last_verification_at: datetime | None
    browser_extension_last_verification_ok: bool
    browser_extension_last_verification_message: str
    browser_extension_last_verification_report: str
    source_health: list[CollectorSourceHealth]
    last_rows: list[dict[str, str | None]]
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


def _read_latest_run_summary() -> dict[str, object]:
    if not STATE_FILE.exists():
        return {}
    try:
        payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    runs = payload.get("runs")
    if not isinstance(runs, list) or not runs:
        return {}
    latest = runs[0]
    return latest if isinstance(latest, dict) else {}


def _read_favorites_auto_summary() -> dict[str, object]:
    if not STATE_FILE.exists():
        return {}
    try:
        payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    summary = payload.get("last_favorites_auto")
    return summary if isinstance(summary, dict) else {}


def read_collector_daemon_config() -> dict[str, Any]:
    config = dict(DEFAULT_COLLECTOR_CONFIG)
    if not CONFIG_FILE.exists():
        return config
    try:
        payload = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return config
    if not isinstance(payload, dict):
        return config
    if isinstance(payload.get("wechat_clipboard_auto_import"), bool):
        config["wechat_clipboard_auto_import"] = payload["wechat_clipboard_auto_import"]
    if isinstance(payload.get("wechat_export_directory_auto_import"), bool):
        config["wechat_export_directory_auto_import"] = payload["wechat_export_directory_auto_import"]
    export_directory_path = payload.get("wechat_export_directory_path")
    if isinstance(export_directory_path, str) and export_directory_path.strip():
        config["wechat_export_directory_path"] = export_directory_path.strip()
    if isinstance(payload.get("updated_at"), str):
        config["updated_at"] = payload["updated_at"]
    return config


def update_collector_daemon_config(
    *,
    wechat_clipboard_auto_import: bool | None = None,
    wechat_export_directory_auto_import: bool | None = None,
    wechat_export_directory_path: str | None = None,
) -> dict[str, Any]:
    config = read_collector_daemon_config()
    if wechat_clipboard_auto_import is not None:
        config["wechat_clipboard_auto_import"] = bool(wechat_clipboard_auto_import)
    if wechat_export_directory_auto_import is not None:
        config["wechat_export_directory_auto_import"] = bool(wechat_export_directory_auto_import)
    if wechat_export_directory_path is not None and wechat_export_directory_path.strip():
        config["wechat_export_directory_path"] = wechat_export_directory_path.strip()
    config["updated_at"] = datetime.now(timezone.utc).isoformat()
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return config


def _read_browser_extension_verification() -> dict[str, object]:
    if not BROWSER_EXTENSION_VERIFY_STATE.exists():
        return {}
    try:
        payload = json.loads(BROWSER_EXTENSION_VERIFY_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_browser_extension_verification(record: dict[str, Any]) -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    BROWSER_EXTENSION_VERIFY_STATE.write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_latest_rows(limit: int = 12) -> list[dict[str, str | None]]:
    if not STATE_FILE.exists():
        return []
    try:
        payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("last_rows")
    if not isinstance(rows, list):
        return []
    output: list[dict[str, str | None]] = []
    for row in rows[:limit]:
        if not isinstance(row, dict):
            continue
        output.append(
            {
                "source_token": str(row.get("sourceToken") or "").strip() or None,
                "article_token": str(row.get("articleToken") or "").strip() or None,
                "mode": str(row.get("mode") or "").strip() or None,
                "item_id": str(row.get("itemId") or "").strip() or None,
                "status": str(row.get("status") or "").strip() or None,
                "note": str(row.get("note") or "").strip() or None,
            }
        )
    return output


def _safe_str(value: object) -> str:
    return str(value or "").strip()


def _safe_int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: object) -> float:
    try:
        return round(max(0.0, min(1.0, float(value or 0))), 3)
    except (TypeError, ValueError):
        return 0.0


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(max(0.0, min(1.0, numerator / denominator)), 3)


def _coverage_summary(
    *,
    running: bool,
    source_count: int,
    last_run_at: datetime | None,
    discovered_count: int,
    collected_count: int,
    skipped_seen_count: int,
    failed_count: int,
    plugin_count: int,
) -> tuple[int, float, float, str, str]:
    handled_count = collected_count + skipped_seen_count
    denominator = max(discovered_count, handled_count + failed_count)
    coverage_rate = _ratio(handled_count, denominator)
    body_success_rate = _ratio(plugin_count, collected_count)

    if source_count <= 0:
        return (
            handled_count,
            coverage_rate,
            body_success_rate,
            "idle",
            "还没有配置源页面 URL，先在采集器设置中导入高价值公众号源。",
        )

    if last_run_at is None:
        return (
            handled_count,
            coverage_rate,
            body_success_rate,
            "watch" if running else "idle",
            "采集器还没有完成第一轮，等待下一次报告或手动执行单轮采集。",
        )

    now = datetime.now(timezone.utc)
    normalized_run_at = last_run_at if last_run_at.tzinfo else last_run_at.replace(tzinfo=timezone.utc)
    stale = now - normalized_run_at > timedelta(minutes=30)

    if stale and not running:
        return (
            handled_count,
            coverage_rate,
            body_success_rate,
            "poor",
            "最近一轮已超过 30 分钟，建议检查守护进程或手动执行单轮采集。",
        )

    if discovered_count <= 0:
        return (
            handled_count,
            coverage_rate,
            body_success_rate,
            "watch",
            "最近一轮没有发现新文章；如果预期有更新，请检查源页面是否仍可访问。",
        )

    if failed_count > 0 and coverage_rate < 0.8:
        return (
            handled_count,
            coverage_rate,
            body_success_rate,
            "poor",
            "最近一轮存在较多未处理文章，建议检查浏览器登录态、源页面结构或网络状态。",
        )

    if coverage_rate < 0.9:
        return (
            handled_count,
            coverage_rate,
            body_success_rate,
            "watch",
            "最近一轮仍有部分文章未处理，建议关注失败列表和采集器日志。",
        )

    if collected_count > 0 and body_success_rate < 0.5:
        return (
            handled_count,
            coverage_rate,
            body_success_rate,
            "watch",
            "多数文章走链接兜底，建议检查浏览器正文抽取链路和登录态。",
        )

    return (
        handled_count,
        coverage_rate,
        body_success_rate,
        "good",
        "最近一轮覆盖稳定，源页面采集可作为专注模式主链路。",
    )


def _read_source_health(limit: int = 20) -> list[CollectorSourceHealth]:
    if not STATE_FILE.exists():
        return []
    try:
        payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("last_source_summaries")
    if not isinstance(rows, list):
        return []

    output: list[CollectorSourceHealth] = []
    for row in rows[:limit]:
        if not isinstance(row, dict):
            continue
        health_state = _safe_str(row.get("health_state")) or "watch"
        if health_state not in {"good", "watch", "poor"}:
            health_state = "watch"
        output.append(
            CollectorSourceHealth(
                source_url=_safe_str(row.get("source_url")),
                source_token=_safe_str(row.get("source_token")) or _safe_str(row.get("source_url")) or "-",
                scanned=bool(row.get("scanned")),
                health_state=health_state,
                recommendation=_safe_str(row.get("recommendation")),
                discovered_count=_safe_int(row.get("discovered_count")),
                handled_count=_safe_int(row.get("handled_count")),
                collected_count=_safe_int(row.get("collected_count")),
                plugin_count=_safe_int(row.get("plugin_count")),
                url_count=_safe_int(row.get("url_count")),
                skipped_seen_count=_safe_int(row.get("skipped_seen_count")),
                failed_count=_safe_int(row.get("failed_count")),
                coverage_rate=_safe_float(row.get("coverage_rate")),
                body_success_rate=_safe_float(row.get("body_success_rate")),
                last_error=_safe_str(row.get("last_error")) or None,
            )
        )
    return output


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
    latest_run = _read_latest_run_summary()
    last_rows = _read_latest_rows()
    last_run_at_text = str(latest_run.get("ts") or "").strip()
    try:
        last_run_at = datetime.fromisoformat(last_run_at_text) if last_run_at_text else None
    except ValueError:
        last_run_at = None

    source_count = _count_source_file_urls()
    discovered_count = _safe_int(latest_run.get("discovered_count"))
    collected_count = _safe_int(latest_run.get("collected_count"))
    plugin_count = _safe_int(latest_run.get("plugin_count"))
    url_count = _safe_int(latest_run.get("url_count"))
    failed_count = _safe_int(latest_run.get("failed_count"))
    skipped_seen_count = _safe_int(latest_run.get("skipped_seen_count"))
    source_health = _read_source_health()
    collector_config = read_collector_daemon_config()
    favorites_auto = _read_favorites_auto_summary()
    favorites_adapters = favorites_auto.get("adapters")
    if not isinstance(favorites_adapters, dict):
        favorites_adapters = {}
    clipboard_adapter = favorites_adapters.get("clipboard")
    if not isinstance(clipboard_adapter, dict):
        clipboard_adapter = {}
    export_directory_adapter = favorites_adapters.get("export_directory")
    if not isinstance(export_directory_adapter, dict):
        export_directory_adapter = {}
    wechat_cli_adapter = favorites_adapters.get("wechat_cli")
    if not isinstance(wechat_cli_adapter, dict):
        wechat_cli_adapter = {}
    favorites_auto_at_text = _safe_str(favorites_auto.get("ts"))
    try:
        favorites_auto_last_at = datetime.fromisoformat(favorites_auto_at_text) if favorites_auto_at_text else None
    except ValueError:
        favorites_auto_last_at = None
    browser_verify = _read_browser_extension_verification()
    browser_verify_at_text = _safe_str(browser_verify.get("verified_at"))
    try:
        browser_verify_at = datetime.fromisoformat(browser_verify_at_text) if browser_verify_at_text else None
    except ValueError:
        browser_verify_at = None
    poor_source_count = sum(1 for source in source_health if source.health_state == "poor")
    watch_source_count = sum(1 for source in source_health if source.health_state == "watch")
    (
        handled_count,
        coverage_rate,
        body_success_rate,
        coverage_state,
        coverage_recommendation,
    ) = _coverage_summary(
        running=running,
        source_count=source_count,
        last_run_at=last_run_at,
        discovered_count=discovered_count,
        collected_count=collected_count,
        skipped_seen_count=skipped_seen_count,
        failed_count=failed_count,
        plugin_count=plugin_count,
    )

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
        source_file_count=source_count,
        last_run_at=last_run_at,
        last_run_submit_mode=str(latest_run.get("submit_mode") or "").strip() or None,
        last_run_discovered_count=discovered_count,
        last_run_collected_count=collected_count,
        last_run_plugin_count=plugin_count,
        last_run_url_count=url_count,
        last_run_failed_count=failed_count,
        last_run_skipped_seen_count=skipped_seen_count,
        last_run_handled_count=handled_count,
        last_run_coverage_rate=coverage_rate,
        last_run_body_success_rate=body_success_rate,
        coverage_state=coverage_state,
        coverage_recommendation=coverage_recommendation,
        poor_source_count=poor_source_count,
        watch_source_count=watch_source_count,
        favorites_auto_status=_safe_str(favorites_auto.get("status")) or "idle",
        favorites_auto_available=bool(favorites_auto.get("available")),
        favorites_auto_last_at=favorites_auto_last_at,
        favorites_auto_discovered_count=_safe_int(favorites_auto.get("discovered_count")),
        favorites_auto_imported_count=_safe_int(favorites_auto.get("imported_count")),
        favorites_auto_deduplicated_count=_safe_int(favorites_auto.get("deduplicated_count")),
        favorites_auto_message=_safe_str(favorites_auto.get("message")),
        favorites_clipboard_auto_enabled=bool(collector_config.get("wechat_clipboard_auto_import", True)),
        favorites_clipboard_adapter_available=bool(clipboard_adapter.get("available")),
        favorites_clipboard_last_message=_safe_str(clipboard_adapter.get("message")),
        favorites_export_directory_auto_enabled=bool(collector_config.get("wechat_export_directory_auto_import", True)),
        favorites_export_directory_path=_safe_str(
            collector_config.get("wechat_export_directory_path") or export_directory_adapter.get("path")
        )
        or str(TMP_DIR / "wechat_favorites_inbox"),
        favorites_export_directory_adapter_available=bool(export_directory_adapter.get("available")),
        favorites_export_directory_last_message=_safe_str(export_directory_adapter.get("message")),
        favorites_export_directory_last_processed_count=_safe_int(export_directory_adapter.get("processed_count")),
        favorites_wechat_cli_adapter_available=bool(wechat_cli_adapter.get("available")),
        favorites_wechat_cli_last_message=_safe_str(wechat_cli_adapter.get("message")),
        browser_extension_path=str(BROWSER_EXTENSION_DIR),
        browser_extension_manifest_present=BROWSER_EXTENSION_MANIFEST.exists(),
        browser_extension_readme_path=str(BROWSER_EXTENSION_README),
        browser_extension_pipeline_script=str(BROWSER_EXTENSION_VERIFY_SCRIPT),
        browser_extension_last_verification_at=browser_verify_at,
        browser_extension_last_verification_ok=bool(browser_verify.get("ok")),
        browser_extension_last_verification_message=_safe_str(browser_verify.get("message")),
        browser_extension_last_verification_report=str(BROWSER_EXTENSION_VERIFY_REPORT),
        source_health=source_health,
        last_rows=last_rows,
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


def verify_browser_extension_pipeline() -> dict[str, Any]:
    verified_at = datetime.now(timezone.utc).isoformat()
    if not BROWSER_EXTENSION_MANIFEST.exists():
        record = {
            "ok": False,
            "verified_at": verified_at,
            "message": f"browser extension manifest not found: {BROWSER_EXTENSION_MANIFEST}",
            "output": "",
            "report_file": str(BROWSER_EXTENSION_VERIFY_REPORT),
        }
        _write_browser_extension_verification(record)
        return record
    if not BROWSER_EXTENSION_VERIFY_SCRIPT.exists():
        record = {
            "ok": False,
            "verified_at": verified_at,
            "message": f"verification script not found: {BROWSER_EXTENSION_VERIFY_SCRIPT}",
            "output": "",
            "report_file": str(BROWSER_EXTENSION_VERIFY_REPORT),
        }
        _write_browser_extension_verification(record)
        return record

    command = [
        "node",
        str(BROWSER_EXTENSION_VERIFY_SCRIPT),
        "--limit",
        "1",
        "--report",
        str(BROWSER_EXTENSION_VERIFY_REPORT),
        "--timeout-sec",
        "120",
    ]
    try:
        ok, output = _run_command(command, timeout_sec=180)
        clipped_output = _clip_output(output, max_chars=4000) or ""
        record = {
            "ok": ok,
            "verified_at": verified_at,
            "message": "browser extension extraction pipeline verified"
            if ok
            else "browser extension extraction pipeline failed",
            "output": clipped_output,
            "report_file": str(BROWSER_EXTENSION_VERIFY_REPORT),
        }
    except subprocess.TimeoutExpired:
        record = {
            "ok": False,
            "verified_at": verified_at,
            "message": "browser extension extraction pipeline timeout",
            "output": "timeout after 180 seconds",
            "report_file": str(BROWSER_EXTENSION_VERIFY_REPORT),
        }
    _write_browser_extension_verification(record)
    return record


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
        "--submit-mode",
        "browser-batch",
        "--batch-submit-size",
        "10",
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
