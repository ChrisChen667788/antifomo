#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable
from urllib import error, request
from urllib.parse import parse_qs, urlparse, urlunparse

try:
    from PIL import Image, ImageChops, ImageDraw, ImageOps, ImageStat
except Exception:  # noqa: BLE001
    Image = None
    ImageChops = None
    ImageDraw = None
    ImageOps = None
    ImageStat = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TMP_DIR = PROJECT_ROOT / ".tmp"

DEFAULT_CONFIG: dict[str, Any] = {
    "api_base": "http://127.0.0.1:8000",
    "output_language": "zh-CN",
    "coordinate_mode": "auto",
    "article_url_strategy": "hybrid",
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
    "rows_per_batch": 2,
    "batches_per_cycle": 12,
    "article_open_wait_sec": 1.2,
    "article_capture_region": {"x": 360, "y": 110, "width": 1020, "height": 860},
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
    "article_allow_targeted_ocr_fallback": True,
    "article_verify_with_ocr": True,
    "article_verify_min_text_length": 120,
    "article_verify_retries": 2,
    "scan_today_unread_only": True,
    "scan_stop_old_article_streak": 2,
    "loop_interval_sec": 300,
}

ARTICLE_CAPTURE_VARIANT_PROFILES: dict[str, dict[str, float]] = {
    "article_right_focus": {"left": 0.34, "top": 0.06, "right": 0.98, "bottom": 0.92},
    "article_right_tight": {"left": 0.42, "top": 0.08, "right": 0.98, "bottom": 0.92},
    "article_right_lower": {"left": 0.38, "top": 0.16, "right": 0.98, "bottom": 0.98},
    "article_far_right": {"left": 0.56, "top": 0.08, "right": 0.98, "bottom": 0.92},
}

ARTICLE_CAPTURE_VARIANT_REASONS: dict[str, list[str]] = {
    "timeline_feed": ["article_right_focus", "article_far_right", "article_right_tight"],
    "chat_ui": ["article_right_focus", "article_far_right", "article_right_tight"],
    "chat_ui_multi": ["article_right_focus", "article_far_right", "article_right_tight"],
    "chat_list_brackets": ["article_right_focus", "article_far_right", "article_right_tight"],
    "non_article_hub": ["article_right_focus", "article_far_right", "article_right_tight"],
    "image_viewer": ["article_right_focus", "article_far_right", "article_right_lower"],
    "app_ui": ["article_right_focus", "article_far_right"],
    "comment_gate": ["article_right_focus", "article_far_right"],
    "comment_fragment": ["article_right_focus", "article_far_right"],
}

ARTICLE_BODY_FOCUS_PROFILES: dict[str, list[tuple[float, float]]] = {
    "default": [(0.72, 0.26), (0.74, 0.44), (0.72, 0.60)],
    "far_right": [(0.84, 0.24), (0.86, 0.42), (0.82, 0.60)],
}

ARTICLE_BODY_FOCUS_REASONS: dict[str, str] = {
    "timeline_feed": "far_right",
    "chat_ui": "far_right",
    "chat_ui_multi": "far_right",
    "chat_list_brackets": "far_right",
    "non_article_hub": "far_right",
    "image_viewer": "default",
    "app_ui": "far_right",
    "comment_gate": "default",
    "comment_fragment": "default",
    "url_probe_no_url_after_ui_probe": "far_right",
    "url_probe_no_action_signal": "far_right",
}

ARTICLE_LINK_PROFILES: dict[str, dict[str, list[dict[str, int]]]] = {
    "compact": {
        "hotspots": [
            {"right_inset": 34, "top_offset": 24},
            {"right_inset": 68, "top_offset": 24},
            {"right_inset": 102, "top_offset": 24},
            {"right_inset": 34, "top_offset": 54},
        ],
        "menu_offsets": [
            {"dx": 0, "dy": 40},
            {"dx": 0, "dy": 74},
            {"dx": 0, "dy": 108},
            {"dx": -48, "dy": 74},
            {"dx": 48, "dy": 74},
        ],
    },
    "standard": {
        "hotspots": [
            {"right_inset": 44, "top_offset": 26},
            {"right_inset": 84, "top_offset": 26},
            {"right_inset": 124, "top_offset": 26},
            {"right_inset": 44, "top_offset": 58},
        ],
        "menu_offsets": [
            {"dx": 0, "dy": 42},
            {"dx": 0, "dy": 78},
            {"dx": 0, "dy": 112},
            {"dx": -52, "dy": 78},
            {"dx": 52, "dy": 78},
        ],
    },
    "wide": {
        "hotspots": [
            {"right_inset": 52, "top_offset": 26},
            {"right_inset": 98, "top_offset": 26},
            {"right_inset": 144, "top_offset": 26},
            {"right_inset": 52, "top_offset": 62},
        ],
        "menu_offsets": [
            {"dx": 0, "dy": 44},
            {"dx": 0, "dy": 82},
            {"dx": 0, "dy": 118},
            {"dx": -60, "dy": 82},
            {"dx": 60, "dy": 82},
        ],
    },
}

WECHAT_ARTICLE_QUERY_KEYS = {"__biz", "mid", "idx", "sn", "chksm"}
WECHAT_ARTICLE_BAD_PATH_PREFIXES = ("/cgi-bin/", "/mp/profile_", "/mp/homepage", "/mp/msg", "/mp/readtemplate")
WECHAT_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

UNEXPECTED_FRONT_PROCESS_BLACKLIST = {
    "哔哩哔哩",
    "Bilibili",
    "PyCharm",
    "IntelliJ IDEA",
    "微信开发者工具",
    "WeChat DevTools",
    "Finder",
    "Preview",
    "Terminal",
    "iTerm2",
}

ACTION_BUTTON_KEYWORDS = (
    "更多",
    "分享",
    "share",
    "more",
    "menu",
    "菜单",
    "转发",
)

BROWSER_PROCESS_NAMES = {
    "Safari",
    "Google Chrome",
    "Chromium",
    "Arc",
    "Brave Browser",
    "Microsoft Edge",
    "Opera",
    "Vivaldi",
}

OPEN_IN_BROWSER_KEYWORDS = (
    "在默认浏览器打开",
    "在浏览器打开",
    "用浏览器打开",
    "默认浏览器打开",
    "Open in Default Browser",
    "Open in Browser",
    "open browser",
)

COPY_LINK_KEYWORDS = (
    "复制链接",
    "複製連結",
    "复制文章链接",
    "复制网址",
    "拷贝链接",
    "copy link",
    "copy article link",
    "copy url",
)

WECHAT_APP_MENU_CANDIDATES = (
    "消息",
    "会话",
    "查看",
    "文件",
    "更多",
    "Message",
    "View",
    "File",
)

DEFAULT_APPLESCRIPT_TIMEOUT_SEC = 4.0
DEFAULT_CLIPBOARD_TIMEOUT_SEC = 2.0
DEFAULT_SCREENSHOT_TIMEOUT_SEC = 6.0
DEFAULT_UI_ACTION_TIMEOUT_SEC = 3.0
DEFAULT_WHICH_TIMEOUT_SEC = 2.0
DEFAULT_URL_EXTRACT_PROFILE_BUDGET_SEC = 4.0
DEFAULT_URL_EXTRACT_SHARE_POINTS = 1
DEFAULT_URL_EXTRACT_MENU_POINTS = 1
DEFAULT_NO_SIGNAL_URL_EXTRACT_PROFILE_BUDGET_SEC = 2.5
DEFAULT_NO_SIGNAL_URL_EXTRACT_SHARE_POINTS = 2
DEFAULT_NO_SIGNAL_URL_EXTRACT_MENU_POINTS = 1
DEFAULT_TEMPLATE_SIGNAL_URL_EXTRACT_SHARE_POINTS = 2
DEFAULT_TEMPLATE_SIGNAL_URL_EXTRACT_MENU_POINTS = 3
DEFAULT_BROWSER_FIRST_TEMPLATE_SIGNAL_URL_EXTRACT_SHARE_POINTS = 3
DEFAULT_BROWSER_FIRST_TEMPLATE_SIGNAL_URL_EXTRACT_MENU_POINTS = 6
DEFAULT_TARGETED_URL_RESOLVE_TIMEOUT_SEC = 6


@dataclass(slots=True)
class AgentPaths:
    config_file: Path
    state_file: Path
    report_file: Path


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def log(message: str) -> None:
    print(f"[wechat-pc-agent] {message}", flush=True)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return fallback
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return fallback
    if not isinstance(loaded, dict):
        return fallback
    return loaded


def ensure_config_file(config_path: Path) -> None:
    if config_path.exists():
        return
    write_json(config_path, DEFAULT_CONFIG)


def load_config(config_path: Path) -> dict[str, Any]:
    ensure_config_file(config_path)
    cfg = read_json(config_path, DEFAULT_CONFIG.copy())
    merged = DEFAULT_CONFIG.copy()
    merged.update(cfg)
    merged["api_base"] = str(merged.get("api_base") or DEFAULT_CONFIG["api_base"]).rstrip("/")
    return merged


def load_state(path: Path) -> dict[str, Any]:
    state = read_json(path, {"processed_hashes": {}, "runs": []})
    processed_hashes = state.get("processed_hashes")
    runs = state.get("runs")
    loop_next_batch_index = state.get("loop_next_batch_index")
    if not isinstance(processed_hashes, dict):
        processed_hashes = {}
    if not isinstance(runs, list):
        runs = []
    try:
        loop_next_batch_index = max(0, int(loop_next_batch_index or 0))
    except (TypeError, ValueError):
        loop_next_batch_index = 0
    return {
        "processed_hashes": processed_hashes,
        "runs": runs[-200:],
        "loop_next_batch_index": loop_next_batch_index,
    }


def save_state(path: Path, state: dict[str, Any]) -> None:
    write_json(path, state)


def _coerce_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _coerce_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _coerce_coordinate_mode(value: Any, default: str = "auto") -> str:
    mode = str(value or "").strip().lower()
    return mode if mode in {"auto", "absolute", "window_relative"} else default


def _coerce_article_url_strategy(value: Any, default: str = "hybrid") -> str:
    strategy = str(value or "").strip().lower()
    return strategy if strategy in {"hybrid", "browser_first"} else default


def _run_command(
    command: list[str],
    *,
    input_text: str | None = None,
    timeout_sec: float | None,
    error_label: str,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            input=input_text,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as exc:
        timeout_text = "unknown" if timeout_sec is None else f"{float(timeout_sec):.1f}s"
        raise RuntimeError(f"{error_label}_timeout:{timeout_text}") from exc


def _applescript(lines: list[str], *, timeout_sec: float = DEFAULT_APPLESCRIPT_TIMEOUT_SEC) -> str:
    command: list[str] = ["osascript"]
    for line in lines:
        command.extend(["-e", line])
    run = _run_command(
        command,
        timeout_sec=timeout_sec,
        error_label="applescript",
    )
    output = "\n".join(part for part in [run.stdout.strip(), run.stderr.strip()] if part).strip()
    if run.returncode != 0:
        raise RuntimeError(output or "osascript failed")
    return output


def _find_cliclick() -> str | None:
    candidates = [
        os.environ.get("WECHAT_CLICLICK_BIN", "").strip(),
        shutil.which("cliclick") or "",
        "/opt/homebrew/bin/cliclick",
        "/usr/local/bin/cliclick",
    ]
    for candidate in candidates:
        path = candidate.strip()
        if not path:
            continue
        if Path(path).exists() and os.access(path, os.X_OK):
            return path
    return None


def activate_wechat(bundle_id: str, app_name: str) -> None:
    try:
        _applescript(
            [
                f'tell application id "{bundle_id}"',
                "activate",
                "end tell",
            ]
        )
        return
    except RuntimeError:
        pass
    _applescript(
        [
            f'tell application "{app_name}"',
            "activate",
            "end tell",
        ]
    )


def _activate_wechat_via_open(app_name: str) -> None:
    run = _run_command(
        ["open", "-a", app_name],
        timeout_sec=DEFAULT_UI_ACTION_TIMEOUT_SEC,
        error_label="open",
    )
    if run.returncode != 0:
        message = "\n".join(part for part in [run.stdout.strip(), run.stderr.strip()] if part).strip()
        raise RuntimeError(message or "open failed")


def _set_wechat_process_frontmost(app_name: str) -> None:
    _applescript(
        [
            'tell application "System Events"',
            f'tell process "{app_name}"',
            "set frontmost to true",
            "end tell",
            "end tell",
        ]
    )


def get_front_window_rect(app_name: str) -> tuple[int, int, int, int]:
    output = _applescript(
        [
            'tell application "System Events"',
            f'tell process "{app_name}"',
            "set frontmost to true",
            "set rectData to {position, size} of front window",
            "return rectData",
            "end tell",
            "end tell",
        ]
    )
    numbers = [int(part.strip()) for part in output.replace("{", "").replace("}", "").split(",") if part.strip()]
    if len(numbers) != 4:
        raise RuntimeError(f"unexpected window rect: {output}")
    return numbers[0], numbers[1], numbers[2], numbers[3]


def list_window_rects(app_name: str) -> list[tuple[int, int, int, int]]:
    output = _applescript(
        [
            'tell application "System Events"',
            f'tell process "{app_name}"',
            'set outText to ""',
            "repeat with i from 1 to count of windows",
            "set w to window i",
            "set p to position of w",
            "set s to size of w",
            'set outText to outText & (item 1 of p) & "," & (item 2 of p) & "," & (item 1 of s) & "," & (item 2 of s) & linefeed',
            "end repeat",
            "return outText",
            "end tell",
            "end tell",
        ]
    )
    rects: list[tuple[int, int, int, int]] = []
    for raw_line in str(output or "").splitlines():
        parts = [part.strip() for part in raw_line.split(",")]
        if len(parts) != 4:
            continue
        try:
            x, y, width, height = [int(part) for part in parts]
        except ValueError:
            continue
        rects.append((x, y, width, height))
    return rects


def get_best_window_rect(app_name: str, *, min_width: int = 900, min_height: int = 600) -> tuple[int, int, int, int] | None:
    try:
        rects = list_window_rects(app_name)
    except Exception:
        rects = []
    usable = [rect for rect in rects if rect[2] >= min_width and rect[3] >= min_height]
    if usable:
        usable.sort(key=lambda rect: rect[2] * rect[3], reverse=True)
        return usable[0]
    try:
        rect = get_front_window_rect(app_name)
    except Exception:
        return None
    return rect if rect[2] >= min_width and rect[3] >= min_height else None


def is_usable_front_window(app_name: str, *, min_width: int = 900, min_height: int = 600) -> tuple[bool, tuple[int, int, int, int] | None]:
    try:
        rect = get_front_window_rect(app_name)
    except Exception:
        return False, None
    return rect[2] >= min_width and rect[3] >= min_height, rect


def get_usable_window_rect(app_name: str, *, min_width: int = 900, min_height: int = 600) -> tuple[bool, tuple[int, int, int, int] | None]:
    rect = get_best_window_rect(app_name, min_width=min_width, min_height=min_height)
    if rect is not None:
        return True, rect
    try:
        front_rect = get_front_window_rect(app_name)
    except Exception:
        return False, None
    return False, front_rect


def click_at(x: int, y: int) -> None:
    # Prefer cliclick because System Events "click at" is unstable on some macOS setups.
    cliclick = _find_cliclick()
    if cliclick:
        try:
            run = _run_command(
                [cliclick, f"c:{x},{y}"],
                timeout_sec=DEFAULT_UI_ACTION_TIMEOUT_SEC,
                error_label="cliclick",
            )
            if run.returncode == 0:
                return
        except RuntimeError:
            pass

    # Fallback to AppleScript click.
    _applescript(
        [
            'tell application "System Events"',
            f"click at {{{x}, {y}}}",
            "end tell",
        ]
    )


def key_code(code: int) -> None:
    cliclick = _find_cliclick()
    if cliclick:
        key_mapping = {
            121: "page-down",
            116: "page-up",
            53: "esc",
            36: "return",
        }
        key_name = key_mapping.get(int(code))
        if key_name:
            try:
                run = _run_command(
                    [cliclick, f"kp:{key_name}"],
                    timeout_sec=DEFAULT_UI_ACTION_TIMEOUT_SEC,
                    error_label="cliclick",
                )
                if run.returncode == 0:
                    return
            except RuntimeError:
                pass

    _applescript(
        [
            'tell application "System Events"',
            f"key code {code}",
            "end tell",
        ]
    )


def key_combo_command(char: str) -> None:
    key = (char or "").strip().lower()
    if len(key) != 1:
        raise RuntimeError("invalid key combo char")
    _applescript(
        [
            'tell application "System Events"',
            f'keystroke "{key}" using command down',
            "end tell",
        ]
    )


def resolve_point(x: int, y: int, *, coordinate_mode: str, app_name: str) -> tuple[int, int]:
    if coordinate_mode == "absolute":
        return x, y
    try:
        rect = get_best_window_rect(app_name, min_width=600, min_height=400)
        if rect is None:
            rect = get_front_window_rect(app_name)
        win_x, win_y, win_width, win_height = rect
        if win_width >= 600 and win_height >= 400:
            return win_x + x, win_y + y
    except Exception:
        pass
    return x, y


def resolve_region(region: dict[str, Any], *, coordinate_mode: str, app_name: str) -> dict[str, int]:
    x = _coerce_int(region.get("x"), 0, 0, 10000)
    y = _coerce_int(region.get("y"), 0, 0, 10000)
    width = _coerce_int(region.get("width"), 1200, 60, 10000)
    height = _coerce_int(region.get("height"), 900, 60, 10000)
    rx, ry = resolve_point(x, y, coordinate_mode=coordinate_mode, app_name=app_name)
    return {"x": rx, "y": ry, "width": width, "height": height}


def _calibrate_article_capture_region(
    region: dict[str, Any],
    *,
    coordinate_mode: str,
    window_rect: tuple[int, int, int, int] | None,
) -> dict[str, int]:
    calibrated = {
        "x": _coerce_int(region.get("x"), 360, 0, 10000),
        "y": _coerce_int(region.get("y"), 110, 0, 10000),
        "width": _coerce_int(region.get("width"), 1020, 60, 10000),
        "height": _coerce_int(region.get("height"), 860, 60, 10000),
    }
    if coordinate_mode == "absolute" or not window_rect:
        return calibrated

    _, _, window_width, window_height = window_rect
    region_right = calibrated["x"] + calibrated["width"]
    looks_like_legacy_region = (
        window_width >= 2200
        and calibrated["x"] <= int(window_width * 0.2)
        and region_right <= int(window_width * 0.62)
    )
    if not looks_like_legacy_region:
        return calibrated

    left = max(calibrated["x"], int(window_width * 0.27))
    top = max(calibrated["y"], int(window_height * 0.08))
    right_margin = max(140, int(window_width * 0.1))
    bottom_margin = max(70, int(window_height * 0.06))
    right = max(left + 780, window_width - right_margin)
    bottom = max(top + 720, window_height - bottom_margin)
    right = min(window_width, right)
    bottom = min(window_height, bottom)
    return {
        "x": left,
        "y": top,
        "width": max(780, right - left),
        "height": max(720, bottom - top),
    }


def read_clipboard_text() -> str:
    run = _run_command(
        ["pbpaste"],
        timeout_sec=DEFAULT_CLIPBOARD_TIMEOUT_SEC,
        error_label="clipboard",
    )
    if run.returncode != 0:
        return ""
    return str(run.stdout or "")


def write_clipboard_text(value: str) -> None:
    _run_command(
        ["pbcopy"],
        input_text=value,
        timeout_sec=DEFAULT_CLIPBOARD_TIMEOUT_SEC,
        error_label="clipboard",
    )


def normalize_http_url(url: str | None) -> str | None:
    text = str(url or "").strip()
    if not text:
        return None
    try:
        parsed = urlparse(text)
    except ValueError:
        return None
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not parsed.netloc:
        return None
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    normalized = parsed._replace(scheme=scheme, netloc=netloc, path=path, fragment="")
    return urlunparse(normalized)


def extract_domain(url: str | None) -> str:
    normalized = normalize_http_url(url)
    if not normalized:
        return ""
    try:
        return (urlparse(normalized).netloc or "").lower()
    except Exception:
        return ""


def is_allowed_article_url(url: str | None) -> bool:
    domain = extract_domain(url)
    if not domain:
        return False
    allowed_suffixes = (
        "mp.weixin.qq.com",
        "weixin.qq.com",
    )
    return any(domain == suffix or domain.endswith(f".{suffix}") for suffix in allowed_suffixes)


def looks_like_wechat_article_url(url: str | None) -> bool:
    normalized = normalize_http_url(url)
    if not normalized or not is_allowed_article_url(normalized):
        return False
    try:
        parsed = urlparse(normalized)
    except Exception:
        return False
    path = (parsed.path or "/").strip() or "/"
    lowered_path = path.lower()
    if any(lowered_path.startswith(prefix) for prefix in WECHAT_ARTICLE_BAD_PATH_PREFIXES):
        return False
    query = parse_qs(parsed.query)
    has_query_shape = any(key in query for key in WECHAT_ARTICLE_QUERY_KEYS)
    has_path_shape = lowered_path == "/s" or lowered_path.startswith("/s/")
    return has_query_shape or has_path_shape


def _is_synthetic_title_hint(title_hint: str | None) -> bool:
    text = normalize_text(title_hint)
    return not text or text.startswith("WeChat Auto ")


def _tokenize_title(value: str | None) -> set[str]:
    text = normalize_text(value)
    if not text:
        return set()
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", text)
        if len(token.strip()) >= 2
    }


def _titles_overlap(expected: str | None, observed: str | None) -> bool:
    expected_tokens = _tokenize_title(expected)
    observed_tokens = _tokenize_title(observed)
    if not expected_tokens or not observed_tokens:
        return True
    overlap = expected_tokens & observed_tokens
    return bool(overlap) and (len(overlap) / max(1, min(len(expected_tokens), len(observed_tokens)))) >= 0.25


def _extract_candidate_article_title(html: str) -> str | None:
    for pattern in (
        r'var\s+msg_title\s*=\s*"([^"]+)"',
        r"var\s+msg_title\s*=\s*'([^']+)'",
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r"<title>(.*?)</title>",
    ):
        match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            value = normalize_text(match.group(1))
            if value:
                return value
    return None


def _fetch_article_html(url: str, *, timeout_sec: int = 6) -> tuple[str | None, str | None]:
    normalized = normalize_http_url(url)
    if not normalized:
        return None, "empty_url"
    req = request.Request(normalized, headers=WECHAT_FETCH_HEADERS)
    try:
        with request.urlopen(req, timeout=timeout_sec) as resp:
            content_type = str(resp.headers.get("Content-Type") or "")
            if "html" not in content_type.lower() and "text" not in content_type.lower():
                return None, f"non_html:{content_type or 'unknown'}"
            payload = resp.read(180_000).decode("utf-8", errors="ignore")
            return payload, None
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def validate_article_url_candidate(
    article_url: str | None,
    *,
    title_hint: str | None = None,
) -> tuple[str | None, str]:
    normalized = normalize_http_url(article_url)
    if not normalized:
        return None, "empty_url"
    if not is_allowed_article_url(normalized):
        return None, "domain_rejected"
    if not looks_like_wechat_article_url(normalized):
        return None, "shape_rejected"
    html, fetch_error = _fetch_article_html(normalized)
    if not html:
        return normalized, f"shape_verified:{fetch_error or 'fetch_skipped'}"

    lowered = html.lower()
    if any(token in lowered for token in ("访问过于频繁", "环境异常", "请在微信客户端打开链接")):
        return normalized, "shape_verified:challenge_page"

    candidate_title = _extract_candidate_article_title(html)
    if candidate_title and not _is_synthetic_title_hint(title_hint):
        if not _titles_overlap(title_hint, candidate_title):
            return None, f"title_mismatch:{candidate_title[:48]}"

    if candidate_title:
        return normalized, f"html_verified:{candidate_title[:48]}"
    if "msg_title" in lowered or "activity-name" in lowered:
        return normalized, "html_verified:wechat_article"
    return normalized, "shape_verified:html_unknown"


def normalize_text(value: str | None) -> str:
    text = str(value or "")
    return " ".join(text.split()).strip()


def _image_resample_filter() -> int:
    if Image is None:
        return 1
    resampling = getattr(Image, "Resampling", None)
    if resampling is not None:
        return int(getattr(resampling, "LANCZOS"))
    return int(getattr(Image, "LANCZOS", 1))


def build_preview_digest(preview: dict[str, Any]) -> str | None:
    title = normalize_text(str(preview.get("title") or ""))
    body = normalize_text(str(preview.get("body_text") or preview.get("body_preview") or ""))
    seed = "\n".join(part for part in [title, body[:320]] if part).strip()
    if len(seed) < 24:
        return None
    return f"preview:{hashlib.sha1(seed.encode('utf-8')).hexdigest()}"


def build_preview_title_digest(preview: dict[str, Any]) -> str | None:
    title = normalize_text(str(preview.get("title") or ""))
    if len(title) < 4:
        return None
    return f"preview-title:{hashlib.sha1(title.lower().encode('utf-8')).hexdigest()}"


def _parse_accessibility_rows(output: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_line in str(output or "").splitlines():
        parts = [part.strip() for part in raw_line.split("\t")]
        if len(parts) < 4:
            continue
        rect_parts = [part.strip() for part in parts[3].split(",")]
        if len(rect_parts) != 4:
            continue
        try:
            x, y, width, height = [int(part) for part in rect_parts]
        except ValueError:
            continue
        rows.append(
            {
                "role": parts[0],
                "name": parts[1],
                "description": parts[2],
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "center_x": x + max(0, width // 2),
                "center_y": y + max(0, height // 2),
            }
        )
    return rows


def _parse_accessibility_action_rows(output: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_line in str(output or "").splitlines():
        parts = [part.strip() for part in raw_line.split("\t")]
        if len(parts) < 6:
            continue
        rect_parts = [part.strip() for part in parts[5].split(",")]
        if len(rect_parts) != 4:
            continue
        try:
            x, y, width, height = [int(part) for part in rect_parts]
        except ValueError:
            continue
        actions = [normalize_text(action) for action in str(parts[4] or "").split(",") if normalize_text(action)]
        rows.append(
            {
                "role": parts[0],
                "subrole": parts[1],
                "name": parts[2],
                "description": parts[3],
                "actions": actions,
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "center_x": x + max(0, width // 2),
                "center_y": y + max(0, height // 2),
            }
        )
    return rows


def _list_accessibility_button_candidates(app_name: str) -> list[dict[str, Any]]:
    output = _applescript(
        [
            'tell application "System Events"',
            f'tell process "{app_name}"',
            "set frontmost to true",
            'set outText to ""',
            "tell front window",
            "set nodeList to entire contents",
            "repeat with node in nodeList",
            "try",
            'set roleValue to ""',
            'try',
            'set roleValue to (value of attribute "AXRole" of node) as text',
            'end try',
            'if roleValue is in {"AXButton", "AXMenuButton", "AXPopUpButton"} then',
            "try",
            "set p to position of node",
            "set s to size of node",
            'set nodeName to ""',
            'try',
            'set nodeName to name of node as text',
            'end try',
            'set nodeDesc to ""',
            'try',
            'set nodeDesc to description of node as text',
            'end try',
            'set outText to outText & roleValue & tab & nodeName & tab & nodeDesc & tab & (item 1 of p) & "," & (item 2 of p) & "," & (item 1 of s) & "," & (item 2 of s) & linefeed',
            "end try",
            "end if",
            "end try",
            "end repeat",
            "end tell",
            "return outText",
            "end tell",
            "end tell",
        ]
    )
    return _parse_accessibility_rows(output)


def _list_accessibility_action_candidates(app_name: str) -> list[dict[str, Any]]:
    output = _applescript(
        [
            'tell application "System Events"',
            f'tell process "{app_name}"',
            "set frontmost to true",
            'set outText to ""',
            "tell front window",
            "set nodeList to entire contents",
            "repeat with node in nodeList",
            "try",
            "set p to position of node",
            "set s to size of node",
            'set actionText to ""',
            'try',
            'set actionText to (name of every action of node) as text',
            'end try',
            'if actionText contains "AXPress" or actionText contains "AXShowMenu" then',
            'set roleValue to ""',
            'try',
            'set roleValue to (value of attribute "AXRole" of node) as text',
            'end try',
            'set subroleValue to ""',
            'try',
            'set subroleValue to (value of attribute "AXSubrole" of node) as text',
            'end try',
            'set nodeName to ""',
            'try',
            'set nodeName to name of node as text',
            'end try',
            'set nodeDesc to ""',
            'try',
            'set nodeDesc to description of node as text',
            'end try',
            'set outText to outText & roleValue & tab & subroleValue & tab & nodeName & tab & nodeDesc & tab & actionText & tab & (item 1 of p) & "," & (item 2 of p) & "," & (item 1 of s) & "," & (item 2 of s) & linefeed',
            "end if",
            "end try",
            "end repeat",
            "end tell",
            "return outText",
            "end tell",
            "end tell",
        ]
    )
    return _parse_accessibility_action_rows(output)


def _score_accessibility_candidate(candidate: dict[str, Any], *, region: dict[str, int]) -> int:
    region_x = int(region.get("x") or 0)
    region_y = int(region.get("y") or 0)
    region_width = int(region.get("width") or 0)
    region_height = int(region.get("height") or 0)
    name = normalize_text(str(candidate.get("name") or "")).lower()
    description = normalize_text(str(candidate.get("description") or "")).lower()
    combined = " ".join(part for part in [name, description] if part)
    cx = int(candidate.get("center_x") or 0)
    cy = int(candidate.get("center_y") or 0)
    if cx < region_x or cx > region_x + region_width:
        return -100
    top_band = region_y + max(90, min(region_height // 3, 180))
    if cy < region_y or cy > top_band:
        return -100

    score = 0
    if combined:
        if any(token in combined for token in ACTION_BUTTON_KEYWORDS):
            score += 10
        if "button" in str(candidate.get("role") or "").lower():
            score += 2
    if cx >= region_x + int(region_width * 0.72):
        score += 5
    if cy <= region_y + max(44, min(region_height // 5, 90)):
        score += 3
    if not combined:
        score += 1
    return score


def _score_accessibility_action_candidate(candidate: dict[str, Any], *, region: dict[str, int]) -> int:
    region_x = int(region.get("x") or 0)
    region_y = int(region.get("y") or 0)
    region_width = int(region.get("width") or 0)
    region_height = int(region.get("height") or 0)
    name = normalize_text(str(candidate.get("name") or "")).lower()
    description = normalize_text(str(candidate.get("description") or "")).lower()
    subrole = normalize_text(str(candidate.get("subrole") or "")).lower()
    role = normalize_text(str(candidate.get("role") or "")).lower()
    actions = [normalize_text(action).lower() for action in candidate.get("actions") or []]
    combined = " ".join(part for part in [name, description, subrole, role] if part)
    cx = int(candidate.get("center_x") or 0)
    cy = int(candidate.get("center_y") or 0)
    width = int(candidate.get("width") or 0)
    height = int(candidate.get("height") or 0)
    if cx < region_x or cx > region_x + region_width:
        return -100
    top_band = region_y + max(120, min(region_height // 3, 220))
    if cy < region_y or cy > top_band:
        return -100

    score = 0
    if "axshowmenu" in actions:
        score += 12
    if "axpress" in actions:
        score += 8
    if any(token in combined for token in ACTION_BUTTON_KEYWORDS):
        score += 12
    if "menu" in role or "menu" in subrole:
        score += 5
    if "button" in role or "button" in subrole:
        score += 4
    if cx >= region_x + int(region_width * 0.72):
        score += 5
    if cy <= region_y + max(56, min(region_height // 5, 110)):
        score += 4
    if 12 <= width <= 96 and 12 <= height <= 96:
        score += 3
    if not combined:
        score += 1
    return score


def _find_accessibility_action_candidates(app_name: str, *, region: dict[str, int], limit: int = 4) -> list[dict[str, Any]]:
    try:
        candidates = _list_accessibility_action_candidates(app_name)
    except Exception:
        return []
    scored = [
        (_score_accessibility_action_candidate(candidate, region=region), candidate)
        for candidate in candidates
    ]
    scored = [item for item in scored if item[0] > 0]
    scored.sort(key=lambda item: item[0], reverse=True)
    return [candidate for _, candidate in scored[: max(1, limit)]]


def _find_accessibility_action_points(app_name: str, *, region: dict[str, int], limit: int = 4) -> list[tuple[int, int]]:
    action_candidates = _find_accessibility_action_candidates(app_name, region=region, limit=limit)
    if action_candidates:
        return _dedupe_points(
            [
                (int(candidate["center_x"]), int(candidate["center_y"]))
                for candidate in action_candidates
            ]
        )
    try:
        candidates = _list_accessibility_button_candidates(app_name)
    except Exception:
        return []
    scored = [
        (_score_accessibility_candidate(candidate, region=region), candidate)
        for candidate in candidates
    ]
    scored = [item for item in scored if item[0] > 0]
    scored.sort(key=lambda item: item[0], reverse=True)
    points = [
        (int(candidate["center_x"]), int(candidate["center_y"]))
        for _, candidate in scored[: max(1, limit)]
    ]
    return _dedupe_points(points)


def _trigger_accessibility_action_candidate(app_name: str, candidate: dict[str, Any]) -> str | None:
    role = normalize_text(str(candidate.get("role") or ""))
    subrole = normalize_text(str(candidate.get("subrole") or ""))
    name = normalize_text(str(candidate.get("name") or ""))
    description = normalize_text(str(candidate.get("description") or ""))
    x = int(candidate.get("x") or 0)
    y = int(candidate.get("y") or 0)
    width = int(candidate.get("width") or 0)
    height = int(candidate.get("height") or 0)
    actions = [normalize_text(action) for action in candidate.get("actions") or []]
    if width <= 0 or height <= 0:
        return None
    preferred_actions = [action for action in ("AXShowMenu", "AXPress") if action in actions]
    if not preferred_actions:
        preferred_actions = ["AXPress"]
    action_literals = ", ".join(json.dumps(action) for action in preferred_actions)
    output = _applescript(
        [
            'tell application "System Events"',
            f'tell process "{app_name}"',
            "set frontmost to true",
            f"set targetX to {x}",
            f"set targetY to {y}",
            f"set targetW to {width}",
            f"set targetH to {height}",
            f"set targetRole to {json.dumps(role)}",
            f"set targetSubrole to {json.dumps(subrole)}",
            f"set targetName to {json.dumps(name)}",
            f"set targetDesc to {json.dumps(description)}",
            f"set preferredActions to {{{action_literals}}}",
            "tell front window",
            "set nodeList to entire contents",
            "repeat with node in nodeList",
            "try",
            "set p to position of node",
            "set s to size of node",
            'set roleValue to ""',
            'try',
            'set roleValue to (value of attribute "AXRole" of node) as text',
            'end try',
            'set subroleValue to ""',
            'try',
            'set subroleValue to (value of attribute "AXSubrole" of node) as text',
            'end try',
            'set nodeName to ""',
            'try',
            'set nodeName to name of node as text',
            'end try',
            'set nodeDesc to ""',
            'try',
            'set nodeDesc to description of node as text',
            'end try',
            'if (item 1 of p) is targetX and (item 2 of p) is targetY and (item 1 of s) is targetW and (item 2 of s) is targetH then',
            'if roleValue is targetRole and subroleValue is targetSubrole and nodeName is targetName and nodeDesc is targetDesc then',
            'repeat with preferredAction in preferredActions',
            'try',
            'perform action (preferredAction as text) of node',
            'return preferredAction as text',
            'end try',
            'end repeat',
            'try',
            'click node',
            'return "click"',
            'end try',
            'end if',
            'end if',
            'end try',
            'end repeat',
            'end tell',
            'return ""',
            'end tell',
            'end tell',
        ]
    )
    value = normalize_text(output)
    return value or None


def _click_accessibility_named_element(app_name: str, names: tuple[str, ...]) -> bool:
    if not names:
        return False
    name_literals = ", ".join(json.dumps(name) for name in names if normalize_text(name))
    if not name_literals:
        return False
    output = _applescript(
        [
            'tell application "System Events"',
            f'tell process "{app_name}"',
            "set frontmost to true",
            f"set targetNames to {{{name_literals}}}",
            "set nodeList to entire contents",
            "repeat with targetName in targetNames",
            "repeat with node in nodeList",
            "try",
            'set nodeName to ""',
            'try',
            'set nodeName to name of node as text',
            'end try',
            'set nodeDesc to ""',
            'try',
            'set nodeDesc to description of node as text',
            'end try',
            'if nodeName contains (targetName as text) or nodeDesc contains (targetName as text) then',
            "click node",
            'return "clicked"',
            "end if",
            "end try",
            "end repeat",
            "end repeat",
            'return ""',
            "end tell",
            "end tell",
        ]
    )
    return normalize_text(output).lower() == "clicked"


def _click_app_menu_item_by_keywords(
    app_name: str,
    *,
    menu_names: tuple[str, ...],
    item_keywords: tuple[str, ...],
) -> str | None:
    if not menu_names or not item_keywords:
        return None
    menu_literals = ", ".join(json.dumps(name) for name in menu_names if normalize_text(name))
    item_literals = ", ".join(json.dumps(name) for name in item_keywords if normalize_text(name))
    if not menu_literals or not item_literals:
        return None
    output = _applescript(
        [
            'tell application "System Events"',
            f'tell process "{app_name}"',
            "set frontmost to true",
            f"set targetMenus to {{{menu_literals}}}",
            f"set targetItems to {{{item_literals}}}",
            "repeat with targetMenu in targetMenus",
            "repeat with topItem in menu bar items of menu bar 1",
            "try",
            'set topName to name of topItem as text',
            'if topName contains (targetMenu as text) then',
            "click topItem",
            "delay 0.15",
            "tell menu 1 of topItem",
            "repeat with node in menu items",
            "try",
            'set nodeName to name of node as text',
            "repeat with targetItem in targetItems",
            'if nodeName contains (targetItem as text) then',
            "click node",
            'return topName & ":" & nodeName',
            "end if",
            "end repeat",
            "end try",
            "end repeat",
            "end tell",
            "end if",
            "end try",
            "end repeat",
            "end repeat",
            'return ""',
            "end tell",
            "end tell",
        ]
    )
    value = normalize_text(output)
    if not value:
        try:
            _dismiss_wechat_overlay()
        except Exception:
            pass
        return None
    return value


def _build_action_icon_templates() -> list[tuple[str, Any]]:
    if Image is None or ImageDraw is None:
        return []
    templates: list[tuple[str, Any]] = []
    for name, centers in (
        ("ellipsis-horizontal", ((8, 14), (14, 14), (20, 14))),
        ("ellipsis-vertical", ((14, 8), (14, 14), (14, 20))),
    ):
        img = Image.new("L", (28, 28), 255)
        draw = ImageDraw.Draw(img)
        for center_x, center_y in centers:
            draw.ellipse((center_x - 2, center_y - 2, center_x + 2, center_y + 2), fill=48)
        templates.append((name, img))
    return templates


def _locate_visual_action_points(
    *,
    wechat_app_name: str,
    article_region: dict[str, int],
    limit: int = 3,
) -> list[tuple[int, int]]:
    if Image is None or ImageOps is None or ImageChops is None or ImageStat is None:
        return []
    templates = _build_action_icon_templates()
    if not templates:
        return []
    width = int(article_region.get("width") or 0)
    height = int(article_region.get("height") or 0)
    if width <= 120 or height <= 60:
        return []
    scan_region = _build_url_probe_scan_region(article_region)
    scan_region["width"] = min(240, scan_region["width"])
    scan_region["height"] = min(132, scan_region["height"])
    temp_dir = TMP_DIR / "wechat_agent_visual"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"action_match_{int(time.time() * 1000)}.png"
    try:
        capture_region(scan_region, temp_path)
        with Image.open(temp_path) as image:
            grayscale = ImageOps.grayscale(image)
            best_matches: list[tuple[float, int, int]] = []
            patch_size = 28
            step = 6
            max_x = max(0, grayscale.width - patch_size)
            max_y = max(0, grayscale.height - patch_size)
            for top in range(0, max_y + 1, step):
                for left in range(0, max_x + 1, step):
                    patch = grayscale.crop((left, top, left + patch_size, top + patch_size))
                    normalized_patch = ImageOps.autocontrast(patch)
                    best_score = 255.0
                    for _, template in templates:
                        diff = ImageChops.difference(normalized_patch, template)
                        score = float(ImageStat.Stat(diff).mean[0])
                        if score < best_score:
                            best_score = score
                    if best_score <= 92:
                        best_matches.append((best_score, left, top))
            best_matches.sort(key=lambda item: item[0])
            points = [
                (
                    scan_region["x"] + left + patch_size // 2,
                    scan_region["y"] + top + patch_size // 2,
                )
                for _, left, top in best_matches[: max(1, limit)]
            ]
            return _dedupe_points(points)
    except Exception:
        return []
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass


def _build_url_probe_scan_region(article_region: dict[str, int]) -> dict[str, int]:
    width = int(article_region.get("width") or 0)
    height = int(article_region.get("height") or 0)
    return {
        "x": int(article_region.get("x") or 0) + max(0, width - 360),
        "y": int(article_region.get("y") or 0),
        "width": min(360, width),
        "height": min(220, height),
    }


def _build_url_menu_scan_region(article_region: dict[str, int]) -> dict[str, int]:
    width = int(article_region.get("width") or 0)
    height = int(article_region.get("height") or 0)
    return {
        "x": int(article_region.get("x") or 0) + max(0, width - 560),
        "y": int(article_region.get("y") or 0),
        "width": min(560, width),
        "height": min(360, height),
    }


def _analyze_visual_region_transition(
    before_path: Path,
    after_path: Path,
) -> dict[str, Any] | None:
    if Image is None or ImageChops is None or ImageOps is None or ImageStat is None:
        return None
    try:
        with Image.open(before_path) as before_image, Image.open(after_path) as after_image:
            before_gray = ImageOps.grayscale(before_image)
            after_gray = ImageOps.grayscale(after_image)
            width = min(before_gray.width, after_gray.width)
            height = min(before_gray.height, after_gray.height)
            if width <= 24 or height <= 24:
                return None
            if before_gray.size != (width, height):
                before_gray = before_gray.crop((0, 0, width, height))
            if after_gray.size != (width, height):
                after_gray = after_gray.crop((0, 0, width, height))
            diff = ImageChops.difference(before_gray, after_gray)
            before_stats = ImageStat.Stat(before_gray)
            after_stats = ImageStat.Stat(after_gray)
            diff_stats = ImageStat.Stat(diff)
            before_mean = float(before_stats.mean[0]) if before_stats.mean else 0.0
            before_stddev = float(before_stats.stddev[0]) if before_stats.stddev else 0.0
            after_mean = float(after_stats.mean[0]) if after_stats.mean else 0.0
            after_stddev = float(after_stats.stddev[0]) if after_stats.stddev else 0.0
            diff_mean = float(diff_stats.mean[0]) if diff_stats.mean else 0.0
            changed = diff_mean >= 8.0 or abs(after_mean - before_mean) >= 9.0 or abs(after_stddev - before_stddev) >= 7.0
            if diff_mean >= 18.0:
                state = "strong_change"
            elif diff_mean >= 8.0:
                state = "weak_change"
            else:
                state = "no_change"
            return {
                "state": state,
                "changed": changed,
                "before_mean": round(before_mean, 2),
                "before_stddev": round(before_stddev, 2),
                "after_mean": round(after_mean, 2),
                "after_stddev": round(after_stddev, 2),
                "diff_mean": round(diff_mean, 2),
                "scan_width": width,
                "scan_height": height,
            }
    except Exception:
        return None
    return None


def _classify_url_probe_surface(*, wechat_app_name: str, article_region: dict[str, int]) -> str | None:
    if Image is None or ImageOps is None or ImageStat is None:
        return None
    width = int(article_region.get("width") or 0)
    height = int(article_region.get("height") or 0)
    if width <= 120 or height <= 60:
        return None
    scan_region = _build_url_probe_scan_region(article_region)
    temp_dir = TMP_DIR / "wechat_agent_visual"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"surface_match_{int(time.time() * 1000)}.png"
    try:
        capture_region(scan_region, temp_path)
        with Image.open(temp_path) as image:
            grayscale = ImageOps.grayscale(image)
            stats = ImageStat.Stat(grayscale)
            mean = float(stats.mean[0]) if stats.mean else 255.0
            stddev = float(stats.stddev[0]) if stats.stddev else 0.0
            if mean <= 26.0 and stddev <= 12.0:
                return "dark_blank"
    except Exception:
        return None
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass
    return None


def _write_menu_probe_debug_artifact(
    *,
    article_region: dict[str, int],
    profile_name: str,
    share_point: tuple[int, int],
    scan_region: dict[str, int],
    before_path: Path,
    after_path: Path,
    note: str,
    analysis: dict[str, Any],
) -> str | None:
    if Image is None or ImageDraw is None:
        return None
    debug_dir = TMP_DIR / "wechat_agent_debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    stem = f"url_menu_{int(time.time() * 1000)}"
    image_path = debug_dir / f"{stem}.png"
    meta_path = debug_dir / f"{stem}.json"
    try:
        with Image.open(before_path) as before_image, Image.open(after_path) as after_image:
            before_canvas = before_image.convert("RGB")
            after_canvas = after_image.convert("RGB")
            width = max(before_canvas.width, after_canvas.width)
            height = before_canvas.height + after_canvas.height + 44
            canvas = Image.new("RGB", (width, height), (248, 250, 252))
            canvas.paste(before_canvas, (0, 22))
            canvas.paste(after_canvas, (0, before_canvas.height + 30))
            draw = ImageDraw.Draw(canvas)
            local_x = share_point[0] - scan_region["x"]
            local_y = share_point[1] - scan_region["y"]
            for offset_y, label in ((22, "before"), (before_canvas.height + 30, "after")):
                draw.text((12, max(2, offset_y - 18)), label, fill=(30, 41, 59))
                if 0 <= local_x <= width and 0 <= local_y <= max(before_canvas.height, after_canvas.height):
                    draw.ellipse(
                        (local_x - 6, offset_y + local_y - 6, local_x + 6, offset_y + local_y + 6),
                        outline=(14, 165, 233),
                        width=3,
                    )
            draw.text(
                (12, 4),
                f"{profile_name} | {note} | state={analysis.get('state')} | diff={analysis.get('diff_mean')}",
                fill=(30, 41, 59),
            )
            canvas.save(image_path)
        meta_path.write_text(
            json.dumps(
                {
                    "at": iso_now(),
                    "profile_name": profile_name,
                    "note": note,
                    "article_region": article_region,
                    "scan_region": scan_region,
                    "share_point": share_point,
                    "analysis": analysis,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        return None
    return str(image_path.relative_to(PROJECT_ROOT))


def _probe_template_menu_visual_state(
    *,
    article_region: dict[str, int],
    profile_name: str,
    share_point: tuple[int, int],
    note: str,
    click_callback: Callable[[], None],
    settle_sec: float,
) -> dict[str, Any]:
    if Image is None or ImageDraw is None or ImageOps is None or ImageChops is None or ImageStat is None:
        click_callback()
        time.sleep(settle_sec)
        return {}
    width = int(article_region.get("width") or 0)
    height = int(article_region.get("height") or 0)
    if width <= 120 or height <= 60:
        click_callback()
        time.sleep(settle_sec)
        return {}
    scan_region = _build_url_menu_scan_region(article_region)
    debug_dir = TMP_DIR / "wechat_agent_debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    stem = f"url_menu_probe_tmp_{int(time.time() * 1000)}"
    before_path = debug_dir / f"{stem}_before.png"
    after_path = debug_dir / f"{stem}_after.png"
    try:
        capture_region(scan_region, before_path)
        click_callback()
        time.sleep(settle_sec)
        capture_region(scan_region, after_path)
        analysis = _analyze_visual_region_transition(before_path, after_path)
        if not analysis:
            return {}
        artifact = _write_menu_probe_debug_artifact(
            article_region=article_region,
            profile_name=profile_name,
            share_point=share_point,
            scan_region=scan_region,
            before_path=before_path,
            after_path=after_path,
            note=note,
            analysis=analysis,
        )
        result = dict(analysis)
        if artifact:
            result["debug_artifact"] = artifact
        return result
    except Exception:
        return {}
    finally:
        try:
            before_path.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            after_path.unlink(missing_ok=True)
        except Exception:
            pass


def _write_url_probe_debug_artifact(
    *,
    wechat_app_name: str,
    article_region: dict[str, int],
    profile_name: str,
    share_points: list[tuple[int, int]],
    template_points: list[tuple[int, int]],
    accessibility_points: list[tuple[int, int]],
    note: str,
) -> str | None:
    if Image is None or ImageDraw is None:
        return None
    width = int(article_region.get("width") or 0)
    height = int(article_region.get("height") or 0)
    if width <= 120 or height <= 60:
        return None
    scan_region = _build_url_probe_scan_region(article_region)
    debug_dir = TMP_DIR / "wechat_agent_debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    stem = f"url_probe_{int(time.time() * 1000)}"
    image_path = debug_dir / f"{stem}.png"
    meta_path = debug_dir / f"{stem}.json"
    try:
        capture_region(scan_region, image_path)
        with Image.open(image_path) as image:
            canvas = image.convert("RGB")
            draw = ImageDraw.Draw(canvas)

            def draw_points(points: list[tuple[int, int]], color: tuple[int, int, int]) -> None:
                for point_x, point_y in points:
                    local_x = point_x - scan_region["x"]
                    local_y = point_y - scan_region["y"]
                    if local_x < 0 or local_y < 0 or local_x > canvas.width or local_y > canvas.height:
                        continue
                    draw.ellipse(
                        (local_x - 6, local_y - 6, local_x + 6, local_y + 6),
                        outline=color,
                        width=3,
                    )

            draw_points(share_points, (59, 130, 246))
            draw_points(template_points, (14, 165, 233))
            draw_points(accessibility_points, (34, 197, 94))
            draw.text((12, 10), f"{profile_name} | {note}", fill=(30, 41, 59))
            canvas.save(image_path)
        meta_path.write_text(
            json.dumps(
                {
                    "at": iso_now(),
                    "wechat_app_name": wechat_app_name,
                    "profile_name": profile_name,
                    "note": note,
                    "scan_region": scan_region,
                    "article_region": article_region,
                    "share_points": share_points,
                    "template_points": template_points,
                    "accessibility_points": accessibility_points,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        return None
    return str(image_path.relative_to(PROJECT_ROOT))


def file_perceptual_hash(path: Path) -> str | None:
    if Image is None or ImageOps is None:
        return None
    try:
        with Image.open(path) as image:
            grayscale = ImageOps.grayscale(image)
            resized = grayscale.resize((9, 8), _image_resample_filter())
            pixels = list(resized.get_flattened_data())
    except Exception:
        return None
    bits = 0
    for row in range(8):
        for col in range(8):
            left = int(pixels[row * 9 + col])
            right = int(pixels[row * 9 + col + 1])
            bits = (bits << 1) | (1 if left > right else 0)
    return f"phash:{bits:016x}"


def _perceptual_hamming_distance(left: str, right: str) -> int | None:
    if not left.startswith("phash:") or not right.startswith("phash:"):
        return None
    try:
        return (int(left.split(":", 1)[1], 16) ^ int(right.split(":", 1)[1], 16)).bit_count()
    except Exception:
        return None


def find_similar_perceptual_hash(
    state: dict[str, Any],
    digest: str | None,
    *,
    threshold: int = 6,
) -> tuple[str | None, int | None]:
    if not digest:
        return None, None
    processed = state.get("processed_hashes", {})
    if not isinstance(processed, dict):
        return None, None
    best_digest = None
    best_distance = None
    for candidate in processed.keys():
        if not isinstance(candidate, str) or not candidate.startswith("phash:"):
            continue
        distance = _perceptual_hamming_distance(candidate, digest)
        if distance is None or distance > threshold:
            continue
        if best_distance is None or distance < best_distance:
            best_digest = candidate
            best_distance = distance
    return best_digest, best_distance


def _build_ocr_preview_payload(
    *,
    image_base64: str,
    mime_type: str,
    source_url: str | None,
    title_hint: str | None,
    output_language: str,
) -> dict[str, Any]:
    return {
        "image_base64": image_base64,
        "mime_type": mime_type,
        "source_url": source_url,
        "title_hint": title_hint,
        "output_language": output_language,
    }


def request_ocr_preview(
    api_base: str,
    *,
    image_base64: str,
    mime_type: str,
    source_url: str | None,
    title_hint: str | None,
    output_language: str,
    timeout_sec: int = 120,
) -> dict[str, Any]:
    return post_json(
        api_base,
        "/api/collector/ocr/preview",
        _build_ocr_preview_payload(
            image_base64=image_base64,
            mime_type=mime_type,
            source_url=source_url,
            title_hint=title_hint,
            output_language=output_language,
        ),
        timeout_sec=timeout_sec,
    )


def request_url_resolve(
    api_base: str,
    *,
    title_hint: str | None,
    body_preview: str | None,
    body_text: str | None,
    candidate_limit: int = 5,
    timeout_sec: int = 45,
) -> dict[str, Any]:
    return post_json(
        api_base,
        "/api/collector/url/resolve",
        {
            "title_hint": title_hint,
            "body_preview": body_preview,
            "body_text": body_text,
            "candidate_limit": max(1, min(int(candidate_limit or 5), 10)),
        },
        timeout_sec=timeout_sec,
    )


def _targeted_ocr_fallback_reason(
    *,
    allow_ocr_fallback: bool,
    allow_targeted_ocr_fallback: bool,
    article_url: str | None,
    route_meta: dict[str, Any] | None,
) -> str | None:
    if allow_ocr_fallback or not allow_targeted_ocr_fallback or article_url:
        return None
    if not isinstance(route_meta, dict):
        return None
    if normalize_text(str(route_meta.get("surface_state") or "")).lower() == "dark_blank":
        return None
    if bool(route_meta.get("budget_exhausted")):
        return "url_probe_budget_exhausted"
    accessibility_candidates = int(route_meta.get("accessibility_candidates") or 0)
    template_candidates = int(route_meta.get("template_candidates") or 0)
    if accessibility_candidates <= 0 and template_candidates <= 0:
        return "url_probe_no_action_signal"
    return "url_probe_no_url_after_ui_probe"


def _is_placeholder_wechat_preview_title(title: str | None, title_hint: str | None = None) -> bool:
    normalized_title = normalize_text(title or "")
    if not normalized_title:
        return True
    normalized_hint = normalize_text(title_hint or "")
    lowered = normalized_title.lower()
    if normalized_hint and normalized_title == normalized_hint:
        return True
    if lowered.startswith("wechat auto "):
        return True
    if re.match(r"^b\d+r\d+$", lowered):
        return True
    return False


def _plan_preview_url_resolve_budget(
    *,
    preview: dict[str, Any],
    title_hint: str | None,
    targeted_fallback: bool,
    targeted_timeout_sec: int,
) -> tuple[int, int, str | None]:
    if not targeted_fallback:
        return 4, 45, None

    title = normalize_text(str(preview.get("title") or ""))
    body_preview = normalize_text(str(preview.get("body_preview") or ""))
    body_text = normalize_text(str(preview.get("body_text") or ""))
    text_length = int(preview.get("text_length") or len(body_text) or len(body_preview))
    placeholder_title = _is_placeholder_wechat_preview_title(title, title_hint)
    candidate_limit = 3
    timeout_sec = max(3, min(int(targeted_timeout_sec or DEFAULT_TARGETED_URL_RESOLVE_TIMEOUT_SEC), 6))

    if placeholder_title:
        candidate_limit = 2
        timeout_sec = min(timeout_sec, 4)
        if text_length < 180 and len(body_preview) < 96:
            return 0, 0, "placeholder_title_short_preview"
    elif text_length < 220 or len(body_preview) < 120:
        candidate_limit = 2
        timeout_sec = min(timeout_sec, 5)

    return candidate_limit, timeout_sec, None


def _is_template_only_profile_miss(route_meta: dict[str, Any] | None) -> bool:
    if not isinstance(route_meta, dict):
        return False
    accessibility_candidates = int(route_meta.get("accessibility_candidates") or 0)
    template_candidates = int(route_meta.get("template_candidates") or 0)
    if accessibility_candidates > 0:
        return False
    if template_candidates < 3:
        return False
    if bool(route_meta.get("budget_exhausted")):
        return False
    return True


def _should_stop_profile_probe_after_miss(
    *,
    profile_name: str,
    route_meta: dict[str, Any] | None,
    template_only_miss_streak: int,
) -> tuple[bool, str | None]:
    route_meta = route_meta if isinstance(route_meta, dict) else {}
    normalized_profile = normalize_text(str(profile_name or "")).lower()
    accessibility_candidates = int(route_meta.get("accessibility_candidates") or 0)
    template_candidates = int(route_meta.get("template_candidates") or 0)
    if normalized_profile == "standard" and accessibility_candidates >= 2 and template_candidates >= 1:
        return True, "standard_ui_signal_exhausted"
    if (
        normalized_profile == "standard"
        and accessibility_candidates <= 0
        and template_candidates >= 3
        and bool(route_meta.get("budget_exhausted"))
    ):
        return True, "template_menu_probe_exhausted"
    if not _is_template_only_profile_miss(route_meta):
        return False, None
    if normalized_profile == "standard":
        return True, "template_only_no_accessibility"
    if template_only_miss_streak >= 2:
        return True, "repeated_template_only_miss"
    return False, None


def validate_article_preview(
    preview: dict[str, Any],
    *,
    min_text_length: int,
) -> tuple[bool, str]:
    title = normalize_text(str(preview.get("title") or ""))
    body_text = normalize_text(str(preview.get("body_text") or preview.get("body_preview") or ""))
    text_length = int(preview.get("text_length") or len(body_text))
    quality_ok = bool(preview.get("quality_ok"))
    quality_reason = normalize_text(str(preview.get("quality_reason") or ""))
    combined = f"{title}\n{body_text}".strip()
    lowered = combined.lower()

    if not quality_ok:
        return False, f"ocr_quality:{quality_reason or 'bad'}"
    if text_length < min_text_length:
        return False, f"text_too_short:{text_length}"
    if not body_text:
        return False, "empty_body_text"

    strong_chat_tokens = [
        "文件传输助手",
        "@所有人",
        "服务号",
        "视频号",
        "常看的号",
        "最近转发",
        "聊天信息",
        "通讯录",
    ]
    weak_chat_tokens = [
        "搜索",
        "发现",
        "群聊",
        "订阅号消息",
        "小程序",
        "图片",
        "链接",
    ]
    strong_hits = [token for token in strong_chat_tokens if token.lower() in lowered]
    if strong_hits:
        return False, f"chat_ui:{strong_hits[0]}"

    weak_hits = [token for token in weak_chat_tokens if token.lower() in lowered]
    timestamp_hits = len(re.findall(r"\b\d{1,2}:\d{2}\b", combined))
    bracket_hits = combined.count("［") + combined.count("[")
    if timestamp_hits >= 3:
        return False, f"chat_timestamps:{timestamp_hits}"
    if bracket_hits >= 4 and len(weak_hits) >= 1:
        return False, "chat_list_brackets"
    if len(weak_hits) >= 3 and text_length < 320:
        return False, f"chat_ui_multi:{','.join(weak_hits[:3])}"

    app_ui_tokens = [
        "anti-fomo demo",
        "专注模式",
        "focus mode",
        "稍后再读",
        "知识库",
        "收集箱",
        "本次目标",
        "生成待办建议",
        "准备开始",
        "pycharm”想要控制“safari 浏览器",
        "pycharm wants to control",
    ]
    app_ui_hits = [token for token in app_ui_tokens if token in lowered]
    if "anti-fomo demo" in lowered:
        return False, "app_ui:anti-fomo-demo"
    if len(app_ui_hits) >= 3:
        return False, f"app_ui_multi:{','.join(app_ui_hits[:3])}"

    comment_tokens = [
        "评论",
        "回复",
        "网友",
        "文明上网理性发言",
        "请先登录后发表评论",
        "内容由ai生成",
        "手机看",
        "打开小游戏",
        "前天",
        "昨天",
        "点赞",
    ]
    comment_hits = [token for token in comment_tokens if token in lowered]
    reply_like_count = lowered.count("回复") + lowered.count("网友")
    if "请先登录后发表评论" in lowered or "文明上网理性发言" in lowered:
        return False, "comment_gate"
    if reply_like_count >= 3 and len(comment_hits) >= 3:
        return False, "comment_fragment"
    if "评论" in lowered and reply_like_count >= 2 and text_length < 900:
        return False, "comment_section"

    hub_tokens = [
        "查看历史消息",
        "历史消息",
        "全部消息",
        "进入公众号",
        "公众号名片",
        "公众号主页",
        "关注公众号",
        "篇原创内容",
        "最近更新",
        "更多文章",
        "继续滑动看下一个",
        "推荐阅读",
        "相关文章",
    ]
    hub_hits = [token for token in hub_tokens if token in lowered]
    if len(hub_hits) >= 2 and text_length < 900:
        return False, f"non_article_hub:{','.join(hub_hits[:2])}"

    image_viewer_tokens = [
        "保存图片",
        "识别图中二维码",
        "轻触两下关闭",
        "正在加载图片",
        "下一张",
        "上一张",
        "图片详情",
        "长按图片",
    ]
    image_viewer_hits = [token for token in image_viewer_tokens if token in lowered]
    if len(image_viewer_hits) >= 2 and text_length < 320:
        return False, f"image_viewer:{','.join(image_viewer_hits[:2])}"

    article_signal_count = 0
    article_tokens = [
        "原创",
        "作者",
        "发布于",
        "发表于",
        "阅读",
        "在看",
        "分享",
        "收藏",
        "点击上方",
        "蓝字",
    ]
    for token in article_tokens:
        if token in combined:
            article_signal_count += 1
            break
    if re.search(r"\d{4}年\d{1,2}月\d{1,2}日", combined):
        article_signal_count += 1
    sentence_hits = sum(combined.count(ch) for ch in "。！？；")
    if sentence_hits >= 2:
        article_signal_count += 1

    incomplete_tokens = [
        "展开剩余",
        "余下全文",
        "全文完",
        "点击阅读全文",
        "查看更多",
        "登录后",
        "打开app",
    ]
    incomplete_hits = [token for token in incomplete_tokens if token in lowered]
    if len(incomplete_hits) >= 2 and article_signal_count <= 1:
        return False, f"incomplete_body:{','.join(incomplete_hits[:2])}"

    if article_signal_count == 0 and text_length < 240:
        return False, "missing_article_signals"
    return True, "ok"


def _classify_preview_article_recency(
    preview: dict[str, Any],
    *,
    now: datetime | None = None,
) -> tuple[str, str]:
    reference_now = now or datetime.now()
    combined = normalize_text(
        " ".join(
            part
            for part in [
                str(preview.get("title") or ""),
                str(preview.get("body_text") or ""),
                str(preview.get("body_preview") or ""),
            ]
            if normalize_text(part)
        )
    )
    if not combined:
        return "unknown", "no_date_signal"
    if any(token in combined for token in ("刚刚", "今天")) or re.search(r"\d+\s*(分钟前|小時前|小时前)", combined):
        return "same_day", "relative_today"
    if any(token in combined for token in ("昨天", "昨日", "前天")):
        return "old", "relative_old"

    patterns = (
        (r"((?:19|20)\d{2})年(\d{1,2})月(\d{1,2})日", True),
        (r"((?:19|20)\d{2})[-/.](\d{1,2})[-/.](\d{1,2})", True),
        (r"(\d{1,2})月(\d{1,2})日", False),
    )
    today = reference_now.date()
    for pattern, has_year in patterns:
        match = re.search(pattern, combined)
        if not match:
            continue
        try:
            if has_year:
                year, month, day = [int(value) for value in match.groups()]
            else:
                year = reference_now.year
                month, day = [int(value) for value in match.groups()]
            candidate = datetime(year, month, day).date()
        except Exception:
            continue
        if candidate == today:
            return "same_day", f"date:{candidate.isoformat()}"
        if candidate < today:
            return "old", f"date:{candidate.isoformat()}"
        return "unknown", f"future:{candidate.isoformat()}"
    return "unknown", "no_date_signal"


def _normalize_capture_variant_reason(reason: str | None) -> str:
    text = normalize_text(reason or "")
    if not text:
        return ""
    if text.startswith("ocr_quality:"):
        text = text.split(":", 1)[1]
    return text.split(":", 1)[0]


def _select_capture_variant_profiles(reason: str | None) -> list[str]:
    normalized_reason = _normalize_capture_variant_reason(reason)
    variants = ARTICLE_CAPTURE_VARIANT_REASONS.get(normalized_reason, [])
    return [variant for variant in variants if variant in ARTICLE_CAPTURE_VARIANT_PROFILES]


def _materialize_capture_variant(
    source_path: Path,
    *,
    variant_name: str,
    temp_root: Path,
) -> Path | None:
    if variant_name == "base":
        return source_path
    if Image is None:
        return None
    profile = ARTICLE_CAPTURE_VARIANT_PROFILES.get(variant_name)
    if profile is None:
        return None
    try:
        with Image.open(source_path) as image:
            width, height = image.size
            if width < 120 or height < 120:
                return None
            left = max(0, min(width - 60, int(width * float(profile["left"]))))
            top = max(0, min(height - 60, int(height * float(profile["top"]))))
            right = max(left + 60, min(width, int(width * float(profile["right"]))))
            bottom = max(top + 60, min(height, int(height * float(profile["bottom"]))))
            if right - left < 160 or bottom - top < 160:
                return None
            cropped = image.crop((left, top, right, bottom))
            target = temp_root / f"{source_path.stem}_{variant_name}{source_path.suffix}"
            cropped.save(target)
            return target
    except Exception:
        return None


def _resolve_article_body_focus_profile(reason: str | None) -> str:
    normalized_reason = _normalize_capture_variant_reason(reason)
    return ARTICLE_BODY_FOCUS_REASONS.get(normalized_reason, "default")


def _focus_article_body_view(
    *,
    wechat_app_name: str,
    coordinate_mode: str,
    article_region: dict[str, Any],
    reason: str | None,
) -> str | None:
    resolved = resolve_region(article_region, coordinate_mode=coordinate_mode, app_name=wechat_app_name)
    region_x = int(resolved.get("x") or 0)
    region_y = int(resolved.get("y") or 0)
    region_width = int(resolved.get("width") or 0)
    region_height = int(resolved.get("height") or 0)
    if region_width < 180 or region_height < 180:
        return None
    profile_name = _resolve_article_body_focus_profile(reason)
    focus_points = ARTICLE_BODY_FOCUS_PROFILES.get(profile_name) or ARTICLE_BODY_FOCUS_PROFILES["default"]
    for point_x_ratio, point_y_ratio in focus_points:
        click_at(
            region_x + int(region_width * point_x_ratio),
            region_y + int(region_height * point_y_ratio),
        )
        time.sleep(0.18)
    return profile_name


def _prime_article_action_surface(
    *,
    article_region: dict[str, Any],
    share_point: tuple[int, int] | None = None,
) -> str | None:
    region_x = int(article_region.get("x") or 0)
    region_y = int(article_region.get("y") or 0)
    region_width = int(article_region.get("width") or 0)
    region_height = int(article_region.get("height") or 0)
    if region_width < 240 or region_height < 240:
        return None
    near_right_edge = bool(share_point and share_point[0] >= region_x + int(region_width * 0.82))
    if near_right_edge:
        targets = [
            (region_x + int(region_width * 0.78), region_y + int(region_height * 0.16)),
            (region_x + int(region_width * 0.72), region_y + int(region_height * 0.24)),
        ]
        profile_name = "right_header"
    else:
        targets = [
            (region_x + int(region_width * 0.66), region_y + int(region_height * 0.18)),
            (region_x + int(region_width * 0.62), region_y + int(region_height * 0.26)),
        ]
        profile_name = "mid_header"
    for target_x, target_y in targets:
        click_at(target_x, target_y)
        time.sleep(0.16)
    return profile_name


def append_stage_log(
    summary: dict[str, Any],
    *,
    batch_index: int,
    row_index: int,
    stage: str,
    outcome: str = "info",
    detail: str | None = None,
) -> None:
    logs = summary.setdefault("stage_logs", [])
    if not isinstance(logs, list):
        return
    logs.append(
        {
            "at": iso_now(),
            "batch": batch_index + 1,
            "row": row_index + 1,
            "stage": stage,
            "outcome": outcome,
            "detail": detail or "",
        }
    )
    if len(logs) > 240:
        del logs[:-240]


def ensure_batch_result(summary: dict[str, Any], batch_index: int) -> dict[str, Any]:
    batches = summary.setdefault("batch_results", [])
    if not isinstance(batches, list):
        batches = []
        summary["batch_results"] = batches
    target_batch = batch_index + 1
    for entry in batches:
        if isinstance(entry, dict) and int(entry.get("batch") or 0) == target_batch:
            return entry
    entry = {
        "batch": target_batch,
        "clicked": 0,
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
        "skipped_seen": 0,
        "skipped_invalid_article": 0,
        "skipped_low_quality": 0,
        "failed": 0,
        "rows": [],
    }
    batches.append(entry)
    batches.sort(key=lambda item: int(item.get("batch") or 0) if isinstance(item, dict) else 0)
    return entry


def append_row_result(
    summary: dict[str, Any],
    *,
    batch_index: int,
    row_index: int,
    status: str,
    detail: str | None = None,
    attempts: int = 1,
    item_id: str | None = None,
) -> None:
    batch = ensure_batch_result(summary, batch_index)
    rows = batch.setdefault("rows", [])
    if not isinstance(rows, list):
        rows = []
        batch["rows"] = rows
    rows.append(
        {
            "row": row_index + 1,
            "status": status,
            "attempts": attempts,
            "detail": detail or "",
            "item_id": item_id or "",
        }
    )


def increment_batch_metric(summary: dict[str, Any], batch_index: int, metric: str, delta: int = 1) -> None:
    batch = ensure_batch_result(summary, batch_index)
    current = int(batch.get(metric) or 0)
    batch[metric] = current + delta


def get_front_process_name() -> str | None:
    try:
        output = _applescript(
            [
                'tell application "System Events"',
                "set frontProc to first application process whose frontmost is true",
                "return name of frontProc",
                "end tell",
            ]
        )
    except Exception:
        return None
    text = str(output or "").strip()
    return text or None


def wait_for_front_process(target_names: set[str], *, timeout_sec: float = 2.0, interval_sec: float = 0.2) -> bool:
    deadline = time.time() + max(0.1, timeout_sec)
    normalized = {str(name).strip() for name in target_names if str(name).strip()}
    while time.time() < deadline:
        current = get_front_process_name()
        if current and current in normalized:
            return True
        time.sleep(max(0.05, interval_sec))
    current = get_front_process_name()
    return bool(current and current in normalized)


def _is_wechat_front_ready(app_name: str) -> tuple[bool, tuple[int, int, int, int] | None]:
    current = get_front_process_name()
    if current not in {app_name, "WeChat"}:
        return False, None
    usable_window, rect = get_usable_window_rect(app_name)
    return usable_window, rect


def _ensure_wechat_front_ready(bundle_id: str, app_name: str) -> tuple[bool, tuple[int, int, int, int] | None]:
    ready, rect = _is_wechat_front_ready(app_name)
    if ready:
        return True, rect

    activation_steps: list[tuple[Callable[[], None], float, float]] = [
        (lambda: activate_wechat(bundle_id, app_name), 1.6, 0.22),
        (lambda: _activate_wechat_via_open(app_name), 1.8, 0.35),
        (lambda: _set_wechat_process_frontmost(app_name), 1.2, 0.12),
    ]
    for activate_step, timeout_sec, settle_sec in activation_steps:
        activate_step()
        time.sleep(settle_sec)
        if wait_for_front_process({app_name, "WeChat"}, timeout_sec=timeout_sec, interval_sec=0.15):
            try:
                switch_to_main_wechat_window(app_name)
                time.sleep(0.18)
                activate_wechat(bundle_id, app_name)
                time.sleep(0.12)
            except Exception:
                pass
            usable_window, rect = get_usable_window_rect(app_name)
            if usable_window:
                return True, rect

    ready, rect = _is_wechat_front_ready(app_name)
    return ready, rect


def _read_front_browser_url(front_process_name: str) -> str | None:
    process_name = str(front_process_name or "").strip()
    if not process_name:
        return None

    chrome_family = {
        "Google Chrome",
        "Chromium",
        "Arc",
        "Brave Browser",
        "Microsoft Edge",
        "Opera",
        "Vivaldi",
    }
    try:
        if process_name == "Safari":
            output = _applescript(
                [
                    'tell application "Safari"',
                    "if not (exists front document) then return \"\"",
                    "return URL of front document",
                    "end tell",
                ]
            )
            return normalize_http_url(output)
        if process_name in chrome_family:
            output = _applescript(
                [
                    f'tell application "{process_name}"',
                    "if not (exists front window) then return \"\"",
                    "return URL of active tab of front window",
                    "end tell",
                ]
            )
            return normalize_http_url(output)
    except Exception:
        return None
    return None


def wait_for_allowed_front_browser_url(
    front_process_name: str,
    *,
    timeout_sec: float = 2.4,
    interval_sec: float = 0.25,
) -> str | None:
    deadline = time.time() + max(0.2, timeout_sec)
    while time.time() < deadline:
        browser_url = _read_front_browser_url(front_process_name)
        if is_allowed_article_url(browser_url):
            return browser_url
        time.sleep(max(0.05, interval_sec))
    browser_url = _read_front_browser_url(front_process_name)
    return browser_url if is_allowed_article_url(browser_url) else None


def wait_for_article_destination(
    wechat_app_name: str,
    *,
    timeout_sec: float = 2.6,
    interval_sec: float = 0.2,
) -> tuple[str | None, list[str]]:
    allowed = {wechat_app_name, "WeChat", *BROWSER_PROCESS_NAMES}
    seen_foregrounds: list[str] = []
    deadline = time.time() + max(0.2, timeout_sec)
    while time.time() < deadline:
        current = get_front_process_name()
        if current:
            if current not in seen_foregrounds:
                seen_foregrounds.append(current)
            if current in allowed:
                return current, seen_foregrounds
        time.sleep(max(0.05, interval_sec))
    return get_front_process_name(), seen_foregrounds


def is_unexpected_front_process(process_name: str | None, *, wechat_app_name: str) -> bool:
    current = str(process_name or "").strip()
    if not current:
        return True
    if current in {wechat_app_name, "WeChat"}:
        return False
    if current in BROWSER_PROCESS_NAMES:
        return False
    return current in UNEXPECTED_FRONT_PROCESS_BLACKLIST


def try_copy_current_article_url(*, wechat_app_name: str) -> str | None:
    front_process_name = get_front_process_name()
    if not front_process_name:
        return None
    if front_process_name in {wechat_app_name, "WeChat"}:
        # On macOS WeChat, Command+L maps to "锁定". Never send browser shortcuts here.
        return None
    return wait_for_allowed_front_browser_url(front_process_name)


def _dismiss_wechat_overlay() -> None:
    try:
        key_code(53)  # Escape
        time.sleep(0.15)
    except Exception:
        return


def _dedupe_points(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    seen: set[tuple[int, int]] = set()
    deduped: list[tuple[int, int]] = []
    for point in points:
        if point in seen:
            continue
        deduped.append(point)
        seen.add(point)
    return deduped


def _build_article_row_click_points(
    *,
    row_x: int,
    row_y: int,
    row_height: int,
    route_issue_streak: int = 0,
    duplicate_article_streak: int = 0,
) -> list[tuple[int, int]]:
    horizontal_step = max(26, min(84, row_height // 3))
    wide_step = max(horizontal_step + 20, min(118, row_height // 2 + 16))
    vertical_step = max(8, min(20, row_height // 8))
    left_backoff = max(10, min(26, row_height // 7))
    points = _dedupe_points(
        [
            (row_x, row_y),
            (row_x + horizontal_step, row_y),
            (row_x + wide_step, row_y),
            (row_x + horizontal_step, row_y + vertical_step),
            (row_x + wide_step, row_y + vertical_step),
            (row_x - left_backoff, row_y),
        ]
    )
    if not points:
        return [(row_x, row_y)]
    rotation = max(0, route_issue_streak - 1) + max(0, duplicate_article_streak - 1)
    if rotation:
        shift = rotation % len(points)
        points = points[shift:] + points[:shift]
    return points


def _select_unblocked_candidate_index(
    *,
    total_candidates: int,
    blocked_candidates: set[int] | None,
    attempt_idx: int,
) -> int:
    if total_candidates <= 0:
        return -1
    blocked = blocked_candidates or set()
    available_indices = [index for index in range(total_candidates) if index not in blocked]
    if not available_indices:
        return -1
    return available_indices[min(attempt_idx, len(available_indices) - 1)]


def _pick_article_link_profile(profile_name: str, region_width: int) -> str:
    normalized = str(profile_name or "auto").strip().lower()
    if normalized in {"compact", "standard", "wide", "manual"}:
        return normalized
    if region_width >= 1160:
        return "wide"
    if region_width <= 880:
        return "compact"
    return "standard"


def _expand_article_link_profiles(profile_name: str) -> list[str]:
    normalized = str(profile_name or "auto").strip().lower()
    if normalized == "manual":
        return ["manual"]
    if normalized == "auto":
        return ["standard", "wide", "compact"]
    profiles = [normalized]
    for candidate in ("standard", "wide", "compact"):
        if candidate not in profiles:
            profiles.append(candidate)
    return profiles


def _build_article_link_points(
    *,
    region_x: int,
    region_y: int,
    region_width: int,
    profile_name: str,
    share_hotspots: list[dict[str, int]] | None,
    menu_offsets: list[dict[str, int]] | None,
) -> tuple[list[tuple[int, int]], list[tuple[int, int]], str]:
    resolved_profile = _pick_article_link_profile(profile_name, region_width)
    builtin_profile = ARTICLE_LINK_PROFILES.get("standard", {})
    if resolved_profile != "manual":
        builtin_profile = ARTICLE_LINK_PROFILES.get(resolved_profile, ARTICLE_LINK_PROFILES["standard"])

    raw_profile_hotspots = builtin_profile.get("hotspots") or []
    raw_profile_offsets = builtin_profile.get("menu_offsets") or []
    raw_custom_hotspots = share_hotspots or []
    raw_custom_offsets = menu_offsets or []

    hotspot_source = raw_custom_hotspots if resolved_profile == "manual" and raw_custom_hotspots else raw_profile_hotspots
    offset_source = raw_custom_offsets if resolved_profile == "manual" and raw_custom_offsets else raw_profile_offsets

    share_points = [
        (
            region_x + region_width - _coerce_int(point.get("right_inset"), 44, 0, 600),
            region_y + _coerce_int(point.get("top_offset"), 26, -600, 600),
        )
        for point in hotspot_source
        if isinstance(point, dict)
    ]
    menu_points = [
        (
            _coerce_int(point.get("dx"), 0, -800, 800),
            _coerce_int(point.get("dy"), 42, -800, 800),
        )
        for point in offset_source
        if isinstance(point, dict)
    ]

    if resolved_profile != "manual" and raw_custom_hotspots:
        share_points.extend(
            (
                region_x + region_width - _coerce_int(point.get("right_inset"), 44, 0, 600),
                region_y + _coerce_int(point.get("top_offset"), 26, -600, 600),
            )
            for point in raw_custom_hotspots
            if isinstance(point, dict)
        )
    if resolved_profile != "manual" and raw_custom_offsets:
        menu_points.extend(
            (
                _coerce_int(point.get("dx"), 0, -800, 800),
                _coerce_int(point.get("dy"), 42, -800, 800),
            )
            for point in raw_custom_offsets
            if isinstance(point, dict)
        )

    return _dedupe_points(share_points), _dedupe_points(menu_points), resolved_profile


def _build_no_signal_share_probe_points(
    *,
    region_x: int,
    region_y: int,
    region_width: int,
) -> list[tuple[int, int]]:
    probe_specs = [
        (30, 22),
        (44, 22),
        (58, 22),
        (44, 34),
        (58, 34),
        (74, 34),
        (44, 48),
        (58, 48),
    ]
    return _dedupe_points(
        [
            (region_x + region_width - right_inset, region_y + top_offset)
            for right_inset, top_offset in probe_specs
        ]
    )


def _build_no_signal_menu_probe_points() -> list[tuple[int, int]]:
    return _dedupe_points(
        [
            (0, 42),
            (0, 78),
            (0, 112),
            (-48, 78),
            (48, 78),
            (0, 146),
        ]
    )


def _build_template_menu_probe_points(
    *,
    region_x: int,
    region_width: int,
    share_x: int,
) -> list[tuple[int, int]]:
    near_right_edge = share_x >= region_x + int(region_width * 0.82)
    if near_right_edge:
        return _dedupe_points(
            [
                (-128, 42),
                (-128, 78),
                (-128, 112),
                (-172, 78),
                (-96, 78),
                (0, 42),
                (0, 78),
            ]
        )
    return _dedupe_points(
        [
            (-96, 42),
            (-96, 78),
            (-96, 112),
            (-144, 78),
            (0, 42),
            (0, 78),
        ]
    )


def _build_browser_first_template_menu_probe_points(
    *,
    region_x: int,
    region_width: int,
    share_x: int,
) -> list[tuple[int, int]]:
    near_right_edge = share_x >= region_x + int(region_width * 0.82)
    if near_right_edge:
        return _dedupe_points(
            [
                (-208, 42),
                (-208, 78),
                (-208, 112),
                (-248, 78),
                (-160, 42),
                (-160, 78),
                (-160, 112),
                (-208, 146),
                (-128, 42),
                (-128, 78),
            ]
        )
    return _dedupe_points(
        [
            (-160, 42),
            (-160, 78),
            (-160, 112),
            (-208, 78),
            (-128, 42),
            (-128, 78),
            (-128, 112),
        ]
    )


def _build_template_action_target_points(
    *,
    region_x: int,
    region_y: int,
    region_width: int,
    share_x: int,
    share_y: int,
) -> list[tuple[int, int]]:
    near_right_edge = share_x >= region_x + int(region_width * 0.82)
    if near_right_edge:
        offsets = [
            (0, 0),
            (-14, 8),
            (-22, 12),
            (-30, 8),
            (-18, 18),
            (-8, 14),
        ]
    else:
        offsets = [
            (0, 0),
            (-10, 8),
            (-18, 12),
            (-4, 14),
            (10, 10),
        ]
    return _dedupe_points(
        [
            (
                max(region_x + 8, share_x + dx),
                max(region_y + 8, share_y + dy),
            )
            for dx, dy in offsets
        ]
    )


def _read_clipboard_url_safe() -> str | None:
    try:
        return normalize_http_url(read_clipboard_text())
    except Exception:
        return None


def try_extract_article_url_from_wechat_ui(
    *,
    wechat_app_name: str,
    coordinate_mode: str,
    article_region: dict[str, Any],
    url_strategy: str = "hybrid",
    link_profile: str = "auto",
    share_hotspots: list[dict[str, int]] | None = None,
    menu_offsets: list[dict[str, int]] | None = None,
) -> tuple[str | None, dict[str, Any]]:
    meta: dict[str, Any] = {
        "used_accessibility": False,
        "used_browser_open": False,
        "used_template_match": False,
        "accessibility_candidates": 0,
        "template_candidates": 0,
        "resolved_profile": str(link_profile or "auto"),
        "budget_exhausted": False,
        "debug_artifact": "",
        "surface_state": "",
        "menu_visual_state": "",
        "menu_visual_change": 0.0,
        "menu_debug_artifact": "",
        "action_surface_prime": "",
    }
    browser_first = _coerce_article_url_strategy(url_strategy, default="hybrid") == "browser_first"
    front_process_name = get_front_process_name()
    if front_process_name not in {wechat_app_name, "WeChat"}:
        return None, meta

    resolved = resolve_region(article_region, coordinate_mode=coordinate_mode, app_name=wechat_app_name)
    region_x = int(resolved.get("x") or 0)
    region_y = int(resolved.get("y") or 0)
    region_width = int(resolved.get("width") or 0)
    region_height = int(resolved.get("height") or 0)
    if region_width <= 0:
        return None, meta

    share_points, menu_points, resolved_profile = _build_article_link_points(
        region_x=region_x,
        region_y=region_y,
        region_width=region_width,
        profile_name=link_profile,
        share_hotspots=share_hotspots,
        menu_offsets=menu_offsets,
    )
    meta["resolved_profile"] = resolved_profile
    accessibility_candidates = _find_accessibility_action_candidates(
        wechat_app_name,
        region=resolved,
        limit=4,
    )
    accessibility_points = [
        (int(candidate.get("center_x") or 0), int(candidate.get("center_y") or 0))
        for candidate in accessibility_candidates
        if int(candidate.get("center_x") or 0) > 0 and int(candidate.get("center_y") or 0) > 0
    ]
    if not accessibility_points:
        accessibility_points = _find_accessibility_action_points(
            wechat_app_name,
            region=resolved,
            limit=4,
        )
    template_points = _locate_visual_action_points(
        wechat_app_name=wechat_app_name,
        article_region={
            "x": region_x,
            "y": region_y,
            "width": region_width,
            "height": region_height,
        },
        limit=3,
    )
    meta["accessibility_candidates"] = len(accessibility_points)
    meta["template_candidates"] = len(template_points)
    template_action_targets = _dedupe_points(
        [
            point
            for template_x, template_y in template_points
            for point in _build_template_action_target_points(
                region_x=region_x,
                region_y=region_y,
                region_width=region_width,
                share_x=template_x,
                share_y=template_y,
            )
        ]
    )
    accessibility_point_set = set(accessibility_points)
    accessibility_candidate_map = {
        (int(candidate.get("center_x") or 0), int(candidate.get("center_y") or 0)): candidate
        for candidate in accessibility_candidates
        if int(candidate.get("center_x") or 0) > 0 and int(candidate.get("center_y") or 0) > 0
    }
    template_point_set = set([*template_points, *template_action_targets])
    share_points = _dedupe_points([*accessibility_points, *template_action_targets, *template_points, *share_points])
    no_action_signal = not accessibility_points and not template_points
    if no_action_signal:
        surface_state = _classify_url_probe_surface(
            wechat_app_name=wechat_app_name,
            article_region={
                "x": region_x,
                "y": region_y,
                "width": region_width,
                "height": region_height,
            },
        )
        if surface_state:
            meta["surface_state"] = surface_state
            share_points = []
            menu_points = []
        else:
            share_points = _dedupe_points(
                [
                    *share_points,
                    *_build_no_signal_share_probe_points(
                        region_x=region_x,
                        region_y=region_y,
                        region_width=region_width,
                    ),
                ]
            )
            menu_points = _dedupe_points([*menu_points, *_build_no_signal_menu_probe_points()])
    profile_budget_sec = (
        DEFAULT_URL_EXTRACT_PROFILE_BUDGET_SEC
        if not no_action_signal
        else DEFAULT_NO_SIGNAL_URL_EXTRACT_PROFILE_BUDGET_SEC
    )
    share_probe_limit = (
        DEFAULT_URL_EXTRACT_SHARE_POINTS
        if not no_action_signal
        else min(DEFAULT_NO_SIGNAL_URL_EXTRACT_SHARE_POINTS, len(share_points) or 0)
    )
    menu_probe_limit = (
        DEFAULT_URL_EXTRACT_MENU_POINTS
        if not no_action_signal
        else min(DEFAULT_NO_SIGNAL_URL_EXTRACT_MENU_POINTS, len(menu_points) or 0)
    )
    if template_points and not accessibility_points and not no_action_signal:
        template_share_limit = DEFAULT_TEMPLATE_SIGNAL_URL_EXTRACT_SHARE_POINTS
        template_menu_limit = DEFAULT_TEMPLATE_SIGNAL_URL_EXTRACT_MENU_POINTS
        if browser_first:
            template_share_limit = DEFAULT_BROWSER_FIRST_TEMPLATE_SIGNAL_URL_EXTRACT_SHARE_POINTS
            template_menu_limit = DEFAULT_BROWSER_FIRST_TEMPLATE_SIGNAL_URL_EXTRACT_MENU_POINTS
        share_probe_limit = max(share_probe_limit, min(template_share_limit, len(share_points) or 0))
        menu_probe_limit = max(menu_probe_limit, template_menu_limit)
    share_points = share_points[: max(1, share_probe_limit)]
    menu_points = menu_points[:menu_probe_limit] if menu_probe_limit > 0 else []
    deadline = time.time() + profile_budget_sec
    try:
        original_clipboard = read_clipboard_text()
    except RuntimeError:
        original_clipboard = ""

    def try_open_in_browser_menu() -> str | None:
        try:
            if not _click_accessibility_named_element(wechat_app_name, OPEN_IN_BROWSER_KEYWORDS):
                return None
            time.sleep(0.3)
            front_after_browser, _ = wait_for_article_destination(
                wechat_app_name,
                timeout_sec=2.0,
                interval_sec=0.2,
            )
            if front_after_browser in BROWSER_PROCESS_NAMES:
                return wait_for_allowed_front_browser_url(front_after_browser or "")
        except Exception:
            return None
        return None

    def try_open_in_browser_app_menu() -> str | None:
        try:
            if not _click_app_menu_item_by_keywords(
                wechat_app_name,
                menu_names=WECHAT_APP_MENU_CANDIDATES,
                item_keywords=OPEN_IN_BROWSER_KEYWORDS,
            ):
                return None
            time.sleep(0.35)
            front_after_browser, _ = wait_for_article_destination(
                wechat_app_name,
                timeout_sec=2.2,
                interval_sec=0.2,
            )
            if front_after_browser in BROWSER_PROCESS_NAMES:
                return wait_for_allowed_front_browser_url(front_after_browser or "")
        except Exception:
            return None
        return None

    def try_copy_link_action(*, used_accessibility_point: bool, used_template_point: bool) -> str | None:
        try:
            write_clipboard_text("")
        except Exception:
            pass
        try:
            if _click_accessibility_named_element(wechat_app_name, COPY_LINK_KEYWORDS):
                time.sleep(0.25)
                clipboard_url = _read_clipboard_url_safe()
                if is_allowed_article_url(clipboard_url):
                    if used_accessibility_point:
                        meta["used_accessibility"] = True
                    if used_template_point:
                        meta["used_template_match"] = True
                    return clipboard_url
        except Exception:
            return None
        return None

    def try_browser_open_sequence(*, used_accessibility_point: bool, used_template_point: bool) -> str | None:
        browser_url = try_open_in_browser_menu()
        if is_allowed_article_url(browser_url):
            if used_accessibility_point:
                meta["used_accessibility"] = True
            if used_template_point:
                    meta["used_template_match"] = True
            meta["used_browser_open"] = True
            return browser_url
        browser_url = try_open_in_browser_app_menu()
        if is_allowed_article_url(browser_url):
            if used_accessibility_point:
                meta["used_accessibility"] = True
            if used_template_point:
                meta["used_template_match"] = True
            meta["used_browser_open"] = True
            return browser_url
        clipboard_url = try_copy_link_action(
            used_accessibility_point=used_accessibility_point,
            used_template_point=used_template_point,
        )
        if is_allowed_article_url(clipboard_url):
            return clipboard_url
        return None

    try:
        for share_x, share_y in share_points:
            if time.time() >= deadline:
                meta["budget_exhausted"] = True
                break
            used_accessibility_point = (share_x, share_y) in accessibility_point_set
            used_template_point = (share_x, share_y) in template_point_set
            menu_visual_state = ""
            try:
                settle_sec = 0.52 if used_template_point and not used_accessibility_point else 0.4
                if used_accessibility_point:
                    triggered = _trigger_accessibility_action_candidate(
                        wechat_app_name,
                        accessibility_candidate_map.get((share_x, share_y), {}),
                    )
                    if triggered:
                        meta["used_accessibility"] = True
                        time.sleep(settle_sec)
                    else:
                        click_at(share_x, share_y)
                        time.sleep(settle_sec)
                elif used_template_point and not used_accessibility_point:
                    if not meta.get("action_surface_prime"):
                        prime_profile = _prime_article_action_surface(
                            article_region={
                                "x": region_x,
                                "y": region_y,
                                "width": region_width,
                                "height": region_height,
                            },
                            share_point=(share_x, share_y),
                        )
                        if prime_profile:
                            meta["action_surface_prime"] = prime_profile
                    menu_probe = _probe_template_menu_visual_state(
                        article_region={
                            "x": region_x,
                            "y": region_y,
                            "width": region_width,
                            "height": region_height,
                        },
                        profile_name=resolved_profile,
                        share_point=(share_x, share_y),
                        note=f"template={len(template_points)}:accessibility={len(accessibility_points)}",
                        click_callback=lambda: click_at(share_x, share_y),
                        settle_sec=settle_sec,
                    )
                    if menu_probe:
                        menu_visual_state = str(menu_probe.get("state") or "")
                        meta["menu_visual_state"] = menu_visual_state
                        meta["menu_visual_change"] = float(menu_probe.get("diff_mean") or 0.0)
                        if menu_probe.get("debug_artifact") and not meta.get("menu_debug_artifact"):
                            meta["menu_debug_artifact"] = str(menu_probe.get("debug_artifact"))
                else:
                    click_at(share_x, share_y)
                    time.sleep(settle_sec)
            except Exception:
                continue

            front_after_click = get_front_process_name()
            if front_after_click in BROWSER_PROCESS_NAMES:
                browser_url = wait_for_allowed_front_browser_url(front_after_click or "")
                if is_allowed_article_url(browser_url):
                    if used_accessibility_point:
                        meta["used_accessibility"] = True
                    if used_template_point:
                        meta["used_template_match"] = True
                    return browser_url, meta

            browser_url = try_browser_open_sequence(
                used_accessibility_point=used_accessibility_point,
                used_template_point=used_template_point,
            )
            if is_allowed_article_url(browser_url):
                return browser_url, meta

            if browser_first:
                try:
                    click_at(share_x, share_y)
                    time.sleep(0.18)
                except Exception:
                    pass
                browser_url = try_browser_open_sequence(
                    used_accessibility_point=used_accessibility_point,
                    used_template_point=used_template_point,
                )
                if is_allowed_article_url(browser_url):
                    return browser_url, meta

            if used_template_point and not used_accessibility_point:
                try:
                    click_at(share_x, share_y)
                    time.sleep(0.24)
                except Exception:
                    pass
                front_after_retry_click = get_front_process_name()
                if front_after_retry_click in BROWSER_PROCESS_NAMES:
                    browser_url = wait_for_allowed_front_browser_url(front_after_retry_click or "")
                    if is_allowed_article_url(browser_url):
                        meta["used_template_match"] = True
                        return browser_url, meta
                browser_url = try_browser_open_sequence(
                    used_accessibility_point=False,
                    used_template_point=True,
                )
                if is_allowed_article_url(browser_url):
                    return browser_url, meta

            if used_template_point and not used_accessibility_point and menu_visual_state == "no_change":
                continue

            active_menu_points = menu_points
            if used_template_point and not used_accessibility_point:
                active_menu_points = _dedupe_points(
                    [
                        *(
                            _build_browser_first_template_menu_probe_points(
                                region_x=region_x,
                                region_width=region_width,
                                share_x=share_x,
                            )
                            if browser_first
                            else []
                        ),
                        *_build_template_menu_probe_points(
                            region_x=region_x,
                            region_width=region_width,
                            share_x=share_x,
                        ),
                        *menu_points,
                    ]
                )
                active_menu_points = active_menu_points[: max(1, menu_probe_limit)]

            for option_dx, option_dy in active_menu_points:
                if time.time() >= deadline:
                    meta["budget_exhausted"] = True
                    break
                try:
                    write_clipboard_text("")
                except Exception:
                    pass
                try:
                    click_at(share_x + option_dx, share_y + option_dy)
                    time.sleep(0.35)
                except Exception:
                    continue

                front_after_option = get_front_process_name()
                if front_after_option in BROWSER_PROCESS_NAMES:
                    browser_url = wait_for_allowed_front_browser_url(front_after_option or "")
                    if is_allowed_article_url(browser_url):
                        if used_accessibility_point:
                            meta["used_accessibility"] = True
                        if used_template_point:
                            meta["used_template_match"] = True
                        return browser_url, meta

                browser_url = try_open_in_browser_menu()
                if is_allowed_article_url(browser_url):
                    if used_accessibility_point:
                        meta["used_accessibility"] = True
                    if used_template_point:
                        meta["used_template_match"] = True
                    meta["used_browser_open"] = True
                    return browser_url, meta

                clipboard_url = _read_clipboard_url_safe()
                if is_allowed_article_url(clipboard_url):
                    if used_accessibility_point:
                        meta["used_accessibility"] = True
                    if used_template_point:
                        meta["used_template_match"] = True
                    return clipboard_url, meta

                _dismiss_wechat_overlay()

            if bool(meta.get("budget_exhausted")):
                break
            try:
                write_clipboard_text("")
                key_combo_command("c")
                time.sleep(0.25)
            except Exception:
                pass
            clipboard_url = _read_clipboard_url_safe()
            if is_allowed_article_url(clipboard_url):
                if used_accessibility_point:
                    meta["used_accessibility"] = True
                if used_template_point:
                    meta["used_template_match"] = True
                return clipboard_url, meta

            _dismiss_wechat_overlay()
    finally:
        try:
            if original_clipboard:
                write_clipboard_text(original_clipboard)
        except Exception:
            pass
    if template_points or accessibility_points or no_action_signal:
        debug_note = (
            f"template={len(template_points)}:"
            f"accessibility={len(accessibility_points)}:"
            f"budget={'hit' if meta.get('budget_exhausted') else 'ok'}"
        )
        debug_artifact = _write_url_probe_debug_artifact(
            wechat_app_name=wechat_app_name,
            article_region={
                "x": region_x,
                "y": region_y,
                "width": region_width,
                "height": region_height,
            },
            profile_name=resolved_profile,
            share_points=share_points,
            template_points=template_points,
            accessibility_points=accessibility_points,
            note=debug_note,
        )
        if debug_artifact:
            meta["debug_artifact"] = debug_artifact
    return None, meta


def restore_wechat_focus(bundle_id: str, app_name: str) -> None:
    try:
        activate_wechat(bundle_id, app_name)
        wait_for_front_process({app_name, "WeChat"}, timeout_sec=1.6, interval_sec=0.2)
        time.sleep(0.35)
        key_combo_command("1")
        wait_for_front_process({app_name, "WeChat"}, timeout_sec=1.0, interval_sec=0.2)
        time.sleep(0.2)
    except Exception:
        return


def click_menu_item(app_name: str, menu_bar_item: str, menu_item: str) -> None:
    _applescript(
        [
            'tell application "System Events"',
            f'tell process "{app_name}"',
            "set frontmost to true",
            f'click menu item "{menu_item}" of menu 1 of menu bar item "{menu_bar_item}" of menu bar 1',
            "end tell",
            "end tell",
        ]
    )


def switch_to_main_wechat_window(app_name: str) -> None:
    try:
        click_menu_item(app_name, "窗口", "微信")
        return
    except Exception:
        pass
    try:
        click_menu_item(app_name, "窗口", "微信 (窗口)")
    except Exception:
        return


def capture_region(region: dict[str, Any], output_path: Path) -> None:
    x = _coerce_int(region.get("x"), 0, 0, 10000)
    y = _coerce_int(region.get("y"), 0, 0, 10000)
    width = _coerce_int(region.get("width"), 1200, 60, 10000)
    height = _coerce_int(region.get("height"), 900, 60, 10000)
    ensure_parent(output_path)
    run = _run_command(
        [
            "screencapture",
            "-x",
            f"-R{x},{y},{width},{height}",
            str(output_path),
        ],
        timeout_sec=DEFAULT_SCREENSHOT_TIMEOUT_SEC,
        error_label="screencapture",
    )
    if run.returncode != 0:
        message = "\n".join(part for part in [run.stdout.strip(), run.stderr.strip()] if part).strip()
        raise RuntimeError(message or "screencapture failed")


def file_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(data).hexdigest()


def to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def post_json(api_base: str, route: str, payload: dict[str, Any], timeout_sec: int = 120) -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}{route}"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        method="POST",
        headers={"Content-Type": "application/json"},
        data=body,
    )
    try:
        with request.urlopen(req, timeout=timeout_sec) as resp:
            text = resp.read().decode("utf-8")
            return json.loads(text) if text else {}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"API unavailable: {exc}") from exc


def remember_hash(state: dict[str, Any], digest: str, *, max_items: int) -> None:
    processed = state["processed_hashes"]
    processed[digest] = iso_now()
    if len(processed) <= max_items:
        return
    sorted_items = sorted(processed.items(), key=lambda kv: kv[1], reverse=True)[:max_items]
    state["processed_hashes"] = dict(sorted_items)


def was_seen(state: dict[str, Any], digest: str) -> bool:
    return digest in state.get("processed_hashes", {})


def _build_title_hint(batch_index: int, row_index: int) -> str:
    ts = datetime.now().strftime("%m-%d %H:%M")
    return f"WeChat Auto {ts} B{batch_index + 1}R{row_index + 1}"


def _check_required_binaries() -> None:
    for command in ["osascript", "screencapture"]:
        run = _run_command(
            ["which", command],
            timeout_sec=DEFAULT_WHICH_TIMEOUT_SEC,
            error_label="which",
        )
        if run.returncode != 0:
            raise RuntimeError(f"required command not found: {command}")
    if not _find_cliclick():
        # Still runnable with AppleScript fallback, but less stable.
        log("warning: cliclick not found, fallback to System Events may be unstable")


def run_cycle(
    config: dict[str, Any],
    state: dict[str, Any],
    *,
    max_items: int | None = None,
    output_language: str | None = None,
    start_batch_index: int = 0,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    _check_required_binaries()

    api_base = str(config.get("api_base") or DEFAULT_CONFIG["api_base"]).rstrip("/")
    language = str(output_language or config.get("output_language") or "zh-CN")
    coordinate_mode = _coerce_coordinate_mode(config.get("coordinate_mode"), default="auto")
    article_url_strategy = _coerce_article_url_strategy(
        config.get("article_url_strategy"),
        default="hybrid",
    )
    article_link_profile = str(config.get("article_link_profile") or "auto").strip().lower()
    bundle_id = str(config.get("wechat_bundle_id") or DEFAULT_CONFIG["wechat_bundle_id"])
    app_name = str(config.get("wechat_app_name") or DEFAULT_CONFIG["wechat_app_name"])

    list_origin = config.get("list_origin") or {}
    list_x = _coerce_int(list_origin.get("x"), 1221, 0, 10000)
    list_y = _coerce_int(list_origin.get("y"), 271, 0, 10000)
    public_origin = config.get("public_account_origin") or {}
    public_x = _coerce_int(public_origin.get("x"), 151, 0, 10000)
    public_y = _coerce_int(public_origin.get("y"), 236, 0, 10000)
    public_hotspots_cfg = config.get("public_account_hotspots") or []
    row_height = _coerce_int(config.get("article_row_height"), 140, 20, 300)
    rows_per_batch = _coerce_int(config.get("rows_per_batch"), 2, 1, 20)
    batches_per_cycle = _coerce_int(config.get("batches_per_cycle"), 12, 1, 30)
    open_wait = _coerce_float(config.get("article_open_wait_sec"), 1.4, 0.1, 8.0)
    page_down_wait = _coerce_float(config.get("page_down_wait_sec"), 0.8, 0.1, 4.0)
    between_item_delay = _coerce_float(config.get("between_item_delay_sec"), 0.7, 0.0, 8.0)
    # Stay near the title/share zone by default. A small configurable value can
    # still be used for tuned profiles that need a slightly lower viewport.
    extra_page_down = _coerce_int(config.get("article_extra_page_down"), 0, 0, 4)
    article_reset_page_up = _coerce_int(config.get("article_reset_page_up"), 3, 0, 10)
    feed_reset_page_up = _coerce_int(config.get("feed_reset_page_up"), 4, 0, 10)
    list_page_down = _coerce_int(config.get("list_page_down_after_batch"), 1, 0, 8)
    duplicate_escape_page_down = _coerce_int(config.get("duplicate_escape_page_down"), 2, 1, 8)
    duplicate_escape_max_extra_pages = _coerce_int(config.get("duplicate_escape_max_extra_pages"), 6, 1, 24)
    dedup_max = _coerce_int(config.get("dedup_max_hashes"), 8000, 200, 50000)
    min_capture_file_size_kb = _coerce_int(config.get("min_capture_file_size_kb"), 45, 1, 2048)
    allow_ocr_fallback = _coerce_bool(config.get("article_allow_ocr_fallback"), False)
    allow_targeted_ocr_fallback = _coerce_bool(config.get("article_allow_targeted_ocr_fallback"), True)
    if article_url_strategy == "browser_first":
        allow_ocr_fallback = False
        allow_targeted_ocr_fallback = False
    verify_with_ocr = _coerce_bool(config.get("article_verify_with_ocr"), True)
    verify_min_text_length = _coerce_int(config.get("article_verify_min_text_length"), 120, 60, 1200)
    verify_retries = _coerce_int(config.get("article_verify_retries"), 2, 1, 5)
    scan_today_unread_only = _coerce_bool(config.get("scan_today_unread_only"), True)
    scan_stop_old_article_streak = _coerce_int(config.get("scan_stop_old_article_streak"), 2, 1, 6)
    targeted_url_resolve_timeout_sec = _coerce_int(
        config.get("article_targeted_url_resolve_timeout_sec"),
        DEFAULT_TARGETED_URL_RESOLVE_TIMEOUT_SEC,
        3,
        45,
    )
    capture_region_cfg = config.get("article_capture_region") or {}
    effective_capture_region_cfg = _calibrate_article_capture_region(
        capture_region_cfg,
        coordinate_mode=coordinate_mode,
        window_rect=None,
    )
    link_hotspots_cfg = config.get("article_link_hotspots") or []
    link_menu_offsets_cfg = config.get("article_link_menu_offsets") or []

    effective_max_items = max_items if max_items is not None else rows_per_batch * batches_per_cycle
    effective_max_items = max(1, min(200, int(effective_max_items)))
    start_batch_index = max(0, int(start_batch_index or 0))

    activate_wechat(bundle_id, app_name)
    time.sleep(0.45)

    public_points: list[tuple[int, int]] = []
    for point in public_hotspots_cfg if isinstance(public_hotspots_cfg, list) else []:
        if not isinstance(point, dict):
            continue
        public_points.append(
            (
                _coerce_int(point.get("x"), public_x, 0, 10000),
                _coerce_int(point.get("y"), public_y, 0, 10000),
            )
        )
    if not public_points:
        public_points = [
            (public_x, public_y),
            (public_x, public_y + 16),
            (public_x + 15, public_y),
            (public_x - 15, public_y),
        ]
    public_points = _dedupe_points(public_points)

    def open_public_account_feed(scroll_pages: int) -> None:
        nonlocal effective_capture_region_cfg
        usable_window, rect = _ensure_wechat_front_ready(bundle_id, app_name)
        if not usable_window:
            try:
                switch_to_main_wechat_window(app_name)
                time.sleep(0.18)
                activate_wechat(bundle_id, app_name)
                time.sleep(0.18)
                usable_window, rect = get_usable_window_rect(app_name)
            except Exception:
                pass
        if not usable_window:
            current_front = get_front_process_name()
            if current_front not in {app_name, "WeChat"}:
                raise RuntimeError("wechat_not_frontmost_after_activate")
            rect_text = "unknown" if rect is None else f"{rect[2]}x{rect[3]}"
            raise RuntimeError(f"wechat_window_too_small:{rect_text}")
        effective_capture_region_cfg = _calibrate_article_capture_region(
            capture_region_cfg,
            coordinate_mode=coordinate_mode,
            window_rect=rect,
        )
        time.sleep(0.22)
        cmd_ready = False
        usable_window_after_cmd = False
        rect_after_cmd: tuple[int, int, int, int] | None = None
        for cmd_attempt in range(2):
            key_combo_command("1")
            if wait_for_front_process({app_name, "WeChat"}, timeout_sec=0.7, interval_sec=0.15):
                usable_window_after_cmd, rect_after_cmd = get_usable_window_rect(app_name)
                if usable_window_after_cmd:
                    cmd_ready = True
                    break
            if cmd_attempt == 0:
                try:
                    activate_wechat(bundle_id, app_name)
                    time.sleep(0.18)
                    switch_to_main_wechat_window(app_name)
                    time.sleep(0.18)
                except Exception:
                    pass
        if not cmd_ready:
            if not wait_for_front_process({app_name, "WeChat"}, timeout_sec=0.3, interval_sec=0.15):
                raise RuntimeError("wechat_not_frontmost_after_cmd1")
            usable_window_after_cmd, rect_after_cmd = get_usable_window_rect(app_name)
            if not usable_window_after_cmd:
                rect_text = "unknown" if rect_after_cmd is None else f"{rect_after_cmd[2]}x{rect_after_cmd[3]}"
                raise RuntimeError(f"wechat_window_too_small_after_cmd1:{rect_text}")
        time.sleep(0.18)
        for point_index, (point_x, point_y) in enumerate(public_points[:2]):
            click_x, click_y = resolve_point(point_x, point_y, coordinate_mode=coordinate_mode, app_name=app_name)
            click_at(click_x, click_y)
            time.sleep(0.18 if point_index == 0 else 0.12)
            if not is_unexpected_front_process(get_front_process_name(), wechat_app_name=app_name):
                # Two nearby taps within the same nav target significantly reduce
                # misses on different window sizes without wandering into content.
                continue
        time.sleep(0.22)
        for _ in range(feed_reset_page_up):
            key_code(116)  # PageUp
            time.sleep(0.18)
        for _ in range(max(0, scroll_pages)):
            key_code(121)  # PageDown
            time.sleep(page_down_wait)

    def recover_feed_state(*, batch_index: int, row_index: int, reason: str) -> None:
        recovery_actions = summary.setdefault("recovery_actions", [])
        if isinstance(recovery_actions, list):
            recovery_actions.append(
                {
                    "at": iso_now(),
                    "batch": batch_index + 1,
                    "row": row_index + 1,
                    "reason": reason,
                }
            )
            if len(recovery_actions) > 120:
                del recovery_actions[:-120]
        summary["recovery_action_count"] = int(summary.get("recovery_action_count") or 0) + 1
        append_stage_log(summary, batch_index=batch_index, row_index=row_index, stage="recover", outcome="info", detail=reason)
        try:
            switch_to_main_wechat_window(app_name)
            time.sleep(0.3)
        except Exception:
            pass
        restore_wechat_focus(bundle_id, app_name)
        if navigation_escape_pages > 0 and any(
            token in reason
            for token in (
                "seen",
                "deduplicated_existing",
                "url_digest_seen",
                "ocr_preview_seen",
                "ocr_title_seen",
                "url_only_no_article_url",
                "invalid_browser_url",
                "unexpected_front_process",
                "applescript_timeout",
                "clipboard_timeout",
                "screencapture_timeout",
                "cliclick_timeout",
            )
        ):
            try:
                open_public_account_feed(feed_scroll_pages(batch_index))
                append_stage_log(
                    summary,
                    batch_index=batch_index,
                    row_index=row_index,
                    stage="recover_reopen_feed",
                    outcome="info",
                    detail=f"extra_pages={navigation_escape_pages}:{reason}",
                )
            except Exception as exc:  # noqa: BLE001
                append_stage_log(
                    summary,
                    batch_index=batch_index,
                    row_index=row_index,
                    stage="recover_reopen_feed",
                    outcome="error",
                    detail=str(exc),
                )
        emit_progress()

    summary: dict[str, Any] = {
        "started_at": iso_now(),
        "api_base": api_base,
        "output_language": language,
        "coordinate_mode": coordinate_mode,
        "article_url_strategy": article_url_strategy,
        "rows_per_batch": rows_per_batch,
        "batches_per_cycle": batches_per_cycle,
        "start_batch_index": start_batch_index,
        "max_items": effective_max_items,
        "planned_clicks": min(effective_max_items, rows_per_batch * batches_per_cycle),
        "clicked": 0,
        "captured": 0,
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
        "skipped_seen": 0,
        "skipped_low_quality": 0,
        "skipped_invalid_article": 0,
        "validation_retries": 0,
        "failed": 0,
        "duplicate_escape_count": 0,
        "route_backoff_count": 0,
        "route_circuit_breaker_count": 0,
        "recovery_action_count": 0,
        "url_only_skip_count": 0,
        "ocr_preview_seen_count": 0,
        "ocr_title_seen_count": 0,
        "accessibility_action_hits": 0,
        "browser_open_menu_hits": 0,
        "template_match_hits": 0,
        "perceptual_duplicate_count": 0,
        "hard_escape_count": 0,
        "submenu_trap_count": 0,
        "today_article_hits": 0,
        "older_article_hits": 0,
        "today_scan_enabled": scan_today_unread_only,
        "scan_stop_reason": "",
        "item_ids": [],
        "new_item_ids": [],
        "errors": [],
        "stage_logs": [],
        "batch_results": [],
        "recovery_actions": [],
    }

    def emit_progress() -> None:
        if progress_callback is None:
            return
        summary["last_checkpoint_at"] = iso_now()
        progress_callback(summary)

    route_issue_streak = 0
    duplicate_article_streak = 0
    navigation_escape_pages = 0
    non_article_view_streak = 0
    older_article_streak = 0
    stop_scan_requested = False
    active_row_candidate_index: int | None = None
    row_trap_state: dict[str, dict[str, Any]] = {}

    def feed_scroll_pages(batch_idx: int) -> int:
        return max(0, batch_idx * list_page_down + navigation_escape_pages)

    def _row_trap_key(batch_idx: int, row_idx: int) -> str:
        return f"{batch_idx}:{row_idx}"

    def _get_row_trap_state(batch_idx: int, row_idx: int) -> dict[str, Any]:
        key = _row_trap_key(batch_idx, row_idx)
        existing = row_trap_state.get(key)
        if existing is not None:
            return existing
        created = {
            "blocked_candidates": set(),
            "trap_count": 0,
            "last_reason": "",
            "skip_row": False,
        }
        row_trap_state[key] = created
        return created

    def remember_row_trap_candidate(*, batch_idx: int, row_idx: int, reason: str, hard: bool = False) -> None:
        if active_row_candidate_index is None:
            return
        state = _get_row_trap_state(batch_idx, row_idx)
        blocked_candidates = state.get("blocked_candidates")
        if isinstance(blocked_candidates, set):
            blocked_candidates.add(active_row_candidate_index)
            if len(blocked_candidates) >= 3:
                state["skip_row"] = True
        if hard:
            state["trap_count"] = int(state.get("trap_count") or 0) + 1
            if int(state.get("trap_count") or 0) >= 2:
                state["skip_row"] = True
        state["last_reason"] = reason[:160]

    def select_row_click_candidate(
        *,
        batch_idx: int,
        row_idx: int,
        row_x: int,
        row_y: int,
        row_height: int,
        attempt_idx: int,
    ) -> tuple[list[tuple[int, int]], int]:
        row_click_points = _build_article_row_click_points(
            row_x=row_x,
            row_y=row_y,
            row_height=row_height,
            route_issue_streak=route_issue_streak,
            duplicate_article_streak=duplicate_article_streak,
        )
        trap = _get_row_trap_state(batch_idx, row_idx)
        if bool(trap.get("skip_row")):
            return row_click_points, -1
        blocked_candidates = trap.get("blocked_candidates")
        blocked = blocked_candidates if isinstance(blocked_candidates, set) else set()
        candidate_index = _select_unblocked_candidate_index(
            total_candidates=len(row_click_points),
            blocked_candidates=blocked,
            attempt_idx=attempt_idx,
        )
        if candidate_index < 0:
            trap["skip_row"] = True
            return row_click_points, -1
        return row_click_points, candidate_index

    def reset_route_issue_streak() -> None:
        nonlocal route_issue_streak
        route_issue_streak = 0

    def reset_duplicate_article_streak() -> None:
        nonlocal duplicate_article_streak, navigation_escape_pages
        duplicate_article_streak = 0
        navigation_escape_pages = 0

    def reset_non_article_view_streak() -> None:
        nonlocal non_article_view_streak
        non_article_view_streak = 0

    def register_article_recency(*, batch_idx: int, row_idx: int, preview: dict[str, Any]) -> tuple[str, str]:
        nonlocal older_article_streak, stop_scan_requested
        status, detail = _classify_preview_article_recency(preview)
        append_stage_log(
            summary,
            batch_index=batch_idx,
            row_index=row_idx,
            stage="article_recency",
            outcome="info",
            detail=f"{status}:{detail}",
        )
        if status == "same_day":
            older_article_streak = 0
            summary["today_article_hits"] = int(summary.get("today_article_hits") or 0) + 1
        elif status == "old":
            older_article_streak += 1
            summary["older_article_hits"] = int(summary.get("older_article_hits") or 0) + 1
            if scan_today_unread_only and older_article_streak >= scan_stop_old_article_streak:
                stop_scan_requested = True
                summary["scan_stop_reason"] = f"older_article_streak:{older_article_streak}"
        return status, detail

    def hard_escape_current_account(*, batch_idx: int, row_idx: int, reason: str, trap: bool = False) -> None:
        nonlocal route_issue_streak, duplicate_article_streak, navigation_escape_pages, non_article_view_streak
        remember_row_trap_candidate(batch_idx=batch_idx, row_idx=row_idx, reason=reason, hard=trap)
        summary["hard_escape_count"] = int(summary.get("hard_escape_count") or 0) + 1
        if trap:
            summary["submenu_trap_count"] = int(summary.get("submenu_trap_count") or 0) + 1
        navigation_escape_pages = min(
            duplicate_escape_max_extra_pages,
            max(1, navigation_escape_pages + max(1, duplicate_escape_page_down)),
        )
        append_stage_log(
            summary,
            batch_index=batch_idx,
            row_index=row_idx,
            stage="hard_escape",
            outcome="info",
            detail=f"extra_pages={navigation_escape_pages}:{reason}",
        )
        emit_progress()
        try:
            key_code(53)
            time.sleep(0.12)
            key_code(53)
            time.sleep(0.12)
        except Exception:
            pass
        try:
            key_combo_command("[")
            time.sleep(0.22)
            key_combo_command("[")
            time.sleep(0.22)
        except Exception:
            pass
        try:
            switch_to_main_wechat_window(app_name)
            time.sleep(0.25)
        except Exception:
            pass
        restore_wechat_focus(bundle_id, app_name)
        try:
            open_public_account_feed(feed_scroll_pages(batch_idx))
            append_stage_log(
                summary,
                batch_index=batch_idx,
                row_index=row_idx,
                stage="hard_escape_reopen",
                outcome="info",
                detail=f"extra_pages={navigation_escape_pages}",
            )
        except Exception as exc:  # noqa: BLE001
            append_stage_log(
                summary,
                batch_index=batch_idx,
                row_index=row_idx,
                stage="hard_escape_reopen",
                outcome="error",
                detail=str(exc),
            )
        route_issue_streak = 0
        duplicate_article_streak = 0
        non_article_view_streak = 0
        emit_progress()

    def bump_non_article_view_streak(*, batch_idx: int, row_idx: int, reason: str) -> None:
        nonlocal non_article_view_streak
        remember_row_trap_candidate(batch_idx=batch_idx, row_idx=row_idx, reason=reason, hard=False)
        non_article_view_streak += 1
        append_stage_log(
            summary,
            batch_index=batch_idx,
            row_index=row_idx,
            stage="non_article_view",
            outcome="info",
            detail=f"streak={non_article_view_streak}:{reason}",
        )
        emit_progress()
        if any(token in reason for token in ("non_article_hub", "image_viewer", "chat_ui", "app_ui", "comment_gate", "dark_blank")):
            hard_escape_current_account(batch_idx=batch_idx, row_idx=row_idx, reason=reason, trap=True)
            return
        if non_article_view_streak >= 2:
            hard_escape_current_account(batch_idx=batch_idx, row_idx=row_idx, reason=reason, trap=True)

    def bump_duplicate_article_streak(*, batch_idx: int, row_idx: int, reason: str) -> None:
        nonlocal duplicate_article_streak, navigation_escape_pages
        if any(token in reason for token in ("ocr_preview_seen", "ocr_title_seen", "perceptual_duplicate", "invalid_browser_url")):
            remember_row_trap_candidate(batch_idx=batch_idx, row_idx=row_idx, reason=reason, hard=True)
        duplicate_article_streak += 1
        if duplicate_article_streak < 2:
            return
        summary["duplicate_escape_count"] = int(summary.get("duplicate_escape_count") or 0) + 1
        navigation_escape_pages = min(
            duplicate_escape_max_extra_pages,
            navigation_escape_pages + duplicate_escape_page_down,
        )
        append_stage_log(
            summary,
            batch_index=batch_idx,
            row_index=row_idx,
            stage="duplicate_escape",
            outcome="info",
            detail=f"streak={duplicate_article_streak}:extra_pages={navigation_escape_pages}:{reason}",
        )
        if duplicate_article_streak >= 3:
            if any(token in reason for token in ("ocr_preview_seen", "ocr_title_seen", "perceptual_duplicate")):
                hard_escape_current_account(batch_idx=batch_idx, row_idx=row_idx, reason=reason, trap=True)
            else:
                try:
                    restore_wechat_focus(bundle_id, app_name)
                    open_public_account_feed(feed_scroll_pages(batch_idx))
                    append_stage_log(
                        summary,
                        batch_index=batch_idx,
                        row_index=row_idx,
                        stage="duplicate_escape_reopen",
                        outcome="info",
                        detail=f"streak={duplicate_article_streak}:extra_pages={navigation_escape_pages}",
                    )
                except Exception as exc:  # noqa: BLE001
                    append_stage_log(
                        summary,
                        batch_index=batch_idx,
                        row_index=row_idx,
                        stage="duplicate_escape_reopen",
                        outcome="error",
                        detail=str(exc),
                    )
        emit_progress()

    def bump_route_issue_streak(*, batch_idx: int, row_idx: int, reason: str) -> None:
        nonlocal route_issue_streak, navigation_escape_pages
        route_issue_streak += 1
        if route_issue_streak < 2:
            return
        summary["route_backoff_count"] = int(summary.get("route_backoff_count") or 0) + 1
        append_stage_log(
            summary,
            batch_index=batch_idx,
            row_index=row_idx,
            stage="route_backoff",
            outcome="info",
            detail=f"streak={route_issue_streak}:{reason}",
        )
        emit_progress()
        if route_issue_streak >= 3:
            next_escape_pages = min(
                duplicate_escape_max_extra_pages,
                max(1, navigation_escape_pages + 1),
            )
            if next_escape_pages != navigation_escape_pages:
                navigation_escape_pages = next_escape_pages
                append_stage_log(
                    summary,
                    batch_index=batch_idx,
                    row_index=row_idx,
                    stage="route_escape",
                    outcome="info",
                    detail=f"streak={route_issue_streak}:extra_pages={navigation_escape_pages}:{reason}",
                )
                emit_progress()
        if route_issue_streak >= 4:
            summary["route_circuit_breaker_count"] = int(summary.get("route_circuit_breaker_count") or 0) + 1
            append_stage_log(
                summary,
                batch_index=batch_idx,
                row_index=row_idx,
                stage="route_circuit_breaker",
                outcome="info",
                detail=f"streak={route_issue_streak}",
            )
            emit_progress()
            try:
                key_code(53)
                time.sleep(0.12)
                key_code(53)
                time.sleep(0.12)
            except Exception:
                pass
        if route_issue_streak >= 2 and any(
            token in reason
            for token in (
                "applescript_timeout",
                "clipboard_timeout",
                "screencapture_timeout",
                "cliclick_timeout",
            )
        ):
            hard_escape_current_account(batch_idx=batch_idx, row_idx=row_idx, reason=reason, trap=True)
            return
        if route_issue_streak >= 3 and any(
            token in reason
            for token in (
                "url_only_no_article_url",
                "invalid_browser_url",
                "invalid_article",
                "non_article_hub",
                "image_viewer",
                "unexpected_front_process",
                "applescript_timeout",
                "clipboard_timeout",
                "screencapture_timeout",
                "cliclick_timeout",
            )
        ):
            hard_escape_current_account(batch_idx=batch_idx, row_idx=row_idx, reason=reason, trap=True)
            return
        restore_wechat_focus(bundle_id, app_name)
        open_public_account_feed(feed_scroll_pages(batch_idx))
        time.sleep(min(3.0, 0.8 + route_issue_streak * 0.4))

    def try_submit_article_url(
        article_url: str,
        *,
        batch_idx: int,
        row_idx: int,
        attempt_idx: int,
        stage_label: str,
        stage_detail: str,
        route_kind: str,
        related_digests: list[str] | None = None,
    ) -> bool:
        append_stage_log(
            summary,
            batch_index=batch_idx,
            row_index=row_idx,
            stage=stage_label,
            outcome="info",
            detail=stage_detail,
        )
        emit_progress()
        validated_url, validation_detail = validate_article_url_candidate(
            article_url,
            title_hint=title_hint,
        )
        append_stage_log(
            summary,
            batch_index=batch_idx,
            row_index=row_idx,
            stage="url_validate",
            outcome="success" if validated_url else "error",
            detail=validation_detail,
        )
        emit_progress()
        if not validated_url:
            return False
        article_url = validated_url

        digest = hashlib.sha1(article_url.encode("utf-8")).hexdigest()
        combined_digests = [digest] + [item for item in (related_digests or []) if item]
        if any(was_seen(state, seen_digest) for seen_digest in combined_digests):
            reset_route_issue_streak()
            bump_duplicate_article_streak(
                batch_idx=batch_idx,
                row_idx=row_idx,
                reason="url_digest_seen",
            )
            summary["skipped_seen"] += 1
            increment_batch_metric(summary, batch_idx, "skipped_seen")
            append_row_result(
                summary,
                batch_index=batch_idx,
                row_index=row_idx,
                status="skipped_seen",
                detail="url_digest_seen",
                attempts=attempt_idx + 1,
            )
            emit_progress()
            recover_feed_state(
                batch_index=batch_idx,
                row_index=row_idx,
                reason="url_digest_seen",
            )
            return True

        url_payload = {
            "source_url": article_url,
            "title": title_hint,
            "output_language": language,
            "deduplicate": True,
            "process_immediately": False,
        }
        url_response: dict[str, Any] | None = None
        last_url_error: Exception | None = None
        ingest_route = "/api/collector/browser/ingest"
        ingest_stage = "browser_ingest"
        ingest_detail = "browser_plugin_preferred"
        for url_attempt in range(2):
            append_stage_log(
                summary,
                batch_index=batch_idx,
                row_index=row_idx,
                stage=ingest_stage,
                outcome="info",
                detail=f"{stage_label}:{ingest_detail}:attempt={url_attempt + 1}",
            )
            emit_progress()
            try:
                url_response = post_json(
                    api_base,
                    ingest_route,
                    url_payload,
                    timeout_sec=120,
                )
                break
            except Exception as exc:  # noqa: BLE001
                last_url_error = exc
                append_stage_log(
                    summary,
                    batch_index=batch_idx,
                    row_index=row_idx,
                    stage=ingest_stage,
                    outcome="error",
                    detail=str(exc),
                )
                emit_progress()
                if url_attempt == 0:
                    time.sleep(0.9)
        if url_response is None:
            ingest_route = "/api/collector/url/ingest"
            ingest_stage = "url_ingest"
            ingest_detail = "browser_ingest_unavailable"
            for url_attempt in range(2):
                append_stage_log(
                    summary,
                    batch_index=batch_idx,
                    row_index=row_idx,
                    stage=ingest_stage,
                    outcome="info",
                    detail=f"{stage_label}:{ingest_detail}:attempt={url_attempt + 1}",
                )
                emit_progress()
                try:
                    url_response = post_json(
                        api_base,
                        ingest_route,
                        url_payload,
                        timeout_sec=120,
                    )
                    break
                except Exception as exc:  # noqa: BLE001
                    last_url_error = exc
                    append_stage_log(
                        summary,
                        batch_index=batch_idx,
                        row_index=row_idx,
                        stage=ingest_stage,
                        outcome="error",
                        detail=str(exc),
                    )
                    emit_progress()
                    if url_attempt == 0:
                        time.sleep(0.9)
        if url_response is None:
            if last_url_error:
                summary["errors"].append(
                    f"batch={batch_idx + 1},row={row_idx + 1},attempt={attempt_idx + 1}: "
                    f"url_ingest_failed={last_url_error}"
                )
                emit_progress()
            return False

        item = url_response.get("item") if isinstance(url_response, dict) else None
        item_id = item.get("id") if isinstance(item, dict) else None
        deduplicated = bool(url_response.get("deduplicated")) if isinstance(url_response, dict) else False
        if item_id:
            summary["item_ids"].append(item_id)
        summary["submitted"] += 1
        summary["submitted_url"] += 1
        increment_batch_metric(summary, batch_idx, "submitted")
        increment_batch_metric(summary, batch_idx, "submitted_url")
        if route_kind == "direct":
            summary["submitted_url_direct"] += 1
            increment_batch_metric(summary, batch_idx, "submitted_url_direct")
        elif route_kind == "share_copy":
            summary["submitted_url_share_copy"] += 1
            increment_batch_metric(summary, batch_idx, "submitted_url_share_copy")
        elif route_kind == "resolved":
            summary["submitted_url_resolved"] += 1
            increment_batch_metric(summary, batch_idx, "submitted_url_resolved")
        if deduplicated:
            bump_duplicate_article_streak(
                batch_idx=batch_idx,
                row_idx=row_idx,
                reason=f"deduplicated_existing_url:{route_kind}",
            )
            summary["deduplicated_existing"] += 1
            summary["deduplicated_existing_url"] += 1
            increment_batch_metric(summary, batch_idx, "deduplicated_existing")
            increment_batch_metric(summary, batch_idx, "deduplicated_existing_url")
            if route_kind == "direct":
                summary["deduplicated_existing_url_direct"] += 1
                increment_batch_metric(summary, batch_idx, "deduplicated_existing_url_direct")
            elif route_kind == "share_copy":
                summary["deduplicated_existing_url_share_copy"] += 1
                increment_batch_metric(summary, batch_idx, "deduplicated_existing_url_share_copy")
            elif route_kind == "resolved":
                summary["deduplicated_existing_url_resolved"] += 1
                increment_batch_metric(summary, batch_idx, "deduplicated_existing_url_resolved")
        else:
            reset_duplicate_article_streak()
            summary["submitted_new"] += 1
            increment_batch_metric(summary, batch_idx, "submitted_new")
            if item_id:
                summary["new_item_ids"].append(item_id)
        for seen_digest in combined_digests:
            remember_hash(state, seen_digest, max_items=dedup_max)
        reset_route_issue_streak()
        ingest_response_route = (
            str(url_response.get("ingest_route") or "")
            if isinstance(url_response, dict)
            else ""
        )
        append_stage_log(
            summary,
            batch_index=batch_idx,
            row_index=row_idx,
            stage=ingest_stage,
            outcome="success",
            detail=(
                f"deduplicated:{item_id}:{ingest_response_route}"
                if deduplicated
                else (f"{item_id}:{ingest_response_route}" if item_id else f"{article_url}:{ingest_response_route}")
            ),
        )
        append_row_result(
            summary,
            batch_index=batch_idx,
            row_index=row_idx,
            status="deduplicated_existing_url" if deduplicated else "submitted_url",
            detail=article_url,
            attempts=attempt_idx + 1,
            item_id=item_id,
        )
        emit_progress()
        recover_feed_state(
            batch_index=batch_idx,
            row_index=row_idx,
            reason=f"{stage_label}:submitted_url",
        )
        return True

    processed_count = 0
    emit_progress()
    with tempfile.TemporaryDirectory(prefix="wechat_pc_agent_") as tmp_dir:
        temp_root = Path(tmp_dir)

        for batch_idx in range(start_batch_index, start_batch_index + batches_per_cycle):
            if stop_scan_requested:
                break
            append_stage_log(
                summary,
                batch_index=batch_idx,
                row_index=0,
                stage="batch_start",
                outcome="info",
                detail=f"scroll_pages={feed_scroll_pages(batch_idx)}:escape_pages={navigation_escape_pages}",
            )
            emit_progress()
            for row_idx in range(rows_per_batch):
                if processed_count >= effective_max_items or stop_scan_requested:
                    break
                y = list_y + row_idx * row_height
                row_done = False
                active_row_candidate_index = None
                title_hint = _build_title_hint(batch_idx, row_idx)
                append_stage_log(
                    summary,
                    batch_index=batch_idx,
                    row_index=row_idx,
                    stage="row_start",
                    outcome="info",
                    detail=title_hint,
                )
                emit_progress()
                for attempt_idx in range(verify_retries):
                    if attempt_idx > 0:
                        summary["validation_retries"] += 1
                        append_stage_log(
                            summary,
                            batch_index=batch_idx,
                            row_index=row_idx,
                            stage="retry",
                            outcome="info",
                            detail=f"attempt={attempt_idx + 1}",
                        )
                        emit_progress()
                        time.sleep(0.5)
                    try:
                        append_stage_log(
                            summary,
                            batch_index=batch_idx,
                            row_index=row_idx,
                            stage="open_feed",
                            outcome="info",
                            detail=f"attempt={attempt_idx + 1}",
                        )
                        emit_progress()
                        open_public_account_feed(feed_scroll_pages(batch_idx))
                        row_click_points, candidate_index = select_row_click_candidate(
                            batch_idx=batch_idx,
                            row_idx=row_idx,
                            row_x=list_x,
                            row_y=y,
                            row_height=row_height,
                            attempt_idx=attempt_idx,
                        )
                        if candidate_index < 0:
                            trap_state = _get_row_trap_state(batch_idx, row_idx)
                            detail = normalize_text(str(trap_state.get("last_reason") or "all_candidates_blocked"))
                            summary["skipped_invalid_article"] += 1
                            increment_batch_metric(summary, batch_idx, "skipped_invalid_article")
                            append_stage_log(
                                summary,
                                batch_index=batch_idx,
                                row_index=row_idx,
                                stage="row_skip",
                                outcome="info",
                                detail=detail or "all_candidates_blocked",
                            )
                            append_row_result(
                                summary,
                                batch_index=batch_idx,
                                row_index=row_idx,
                                status="skipped_invalid_article",
                                detail=detail or "all_candidates_blocked",
                                attempts=attempt_idx + 1,
                            )
                            emit_progress()
                            row_done = True
                            break
                        active_row_candidate_index = candidate_index
                        click_point_x, click_point_y = row_click_points[candidate_index]
                        item_x, item_y = resolve_point(
                            click_point_x,
                            click_point_y,
                            coordinate_mode=coordinate_mode,
                            app_name=app_name,
                        )
                        click_at(item_x, item_y)
                        summary["clicked"] += 1
                        increment_batch_metric(summary, batch_idx, "clicked")
                        append_stage_log(
                            summary,
                            batch_index=batch_idx,
                            row_index=row_idx,
                            stage="click_article",
                            outcome="info",
                            detail=f"x={item_x},y={item_y}:candidate={candidate_index + 1}/{len(row_click_points)}",
                        )
                        emit_progress()
                        time.sleep(open_wait)
                        front_after_click, seen_foregrounds = wait_for_article_destination(
                            app_name,
                            timeout_sec=max(1.8, open_wait + 1.0),
                            interval_sec=0.2,
                        )
                        if is_unexpected_front_process(front_after_click, wechat_app_name=app_name):
                            restore_wechat_focus(bundle_id, app_name)
                            front_after_click, seen_retry_foregrounds = wait_for_article_destination(
                                app_name,
                                timeout_sec=1.4,
                                interval_sec=0.2,
                            )
                            seen_foregrounds.extend(
                                current
                                for current in seen_retry_foregrounds
                                if current and current not in seen_foregrounds
                            )
                            if is_unexpected_front_process(front_after_click, wechat_app_name=app_name):
                                seen_detail = " -> ".join(seen_foregrounds[-4:]) if seen_foregrounds else "unknown"
                                raise RuntimeError(
                                    f"unexpected_front_process:{front_after_click or 'unknown'}:seen={seen_detail}"
                                )
                        append_stage_log(
                            summary,
                            batch_index=batch_idx,
                            row_index=row_idx,
                            stage="front_process",
                            outcome="info",
                            detail=(front_after_click or "unknown") + (f" via {' -> '.join(seen_foregrounds[-3:])}" if seen_foregrounds else ""),
                        )
                        emit_progress()

                        if article_reset_page_up > 0:
                            append_stage_log(
                                summary,
                                batch_index=batch_idx,
                                row_index=row_idx,
                                stage="article_reset_page_up",
                                outcome="info",
                                detail=f"count={article_reset_page_up}",
                            )
                            emit_progress()
                            for _ in range(article_reset_page_up):
                                key_code(116)  # PageUp
                                time.sleep(0.16)

                        for _ in range(extra_page_down):
                            key_code(121)  # PageDown
                            time.sleep(page_down_wait)

                        append_stage_log(
                            summary,
                            batch_index=batch_idx,
                            row_index=row_idx,
                            stage="url_extract_direct",
                            outcome="info",
                            detail="start",
                        )
                        emit_progress()
                        article_url = try_copy_current_article_url(wechat_app_name=app_name)
                        article_url_route_kind = "direct" if article_url else ""
                        article_url_stage_label = "direct_url_detected" if article_url else ""
                        route_meta: dict[str, Any] = {}
                        append_stage_log(
                            summary,
                            batch_index=batch_idx,
                            row_index=row_idx,
                            stage="url_extract_direct",
                            outcome="success" if article_url else "info",
                            detail=article_url or "miss",
                        )
                        emit_progress()
                        if not article_url:
                            template_only_miss_streak = 0
                            for profile_name in _expand_article_link_profiles(article_link_profile):
                                append_stage_log(
                                    summary,
                                    batch_index=batch_idx,
                                    row_index=row_idx,
                                    stage="url_extract_profile",
                                    outcome="info",
                                    detail=f"profile={profile_name}:start",
                                )
                                emit_progress()
                                article_url, route_meta = try_extract_article_url_from_wechat_ui(
                                    wechat_app_name=app_name,
                                    coordinate_mode=coordinate_mode,
                                    article_region=effective_capture_region_cfg,
                                    url_strategy=article_url_strategy,
                                    link_profile=profile_name,
                                    share_hotspots=link_hotspots_cfg if isinstance(link_hotspots_cfg, list) else None,
                                    menu_offsets=link_menu_offsets_cfg if isinstance(link_menu_offsets_cfg, list) else None,
                                )
                                if route_meta.get("used_accessibility"):
                                    summary["accessibility_action_hits"] = int(
                                        summary.get("accessibility_action_hits") or 0
                                    ) + 1
                                    increment_batch_metric(summary, batch_idx, "accessibility_action_hits")
                                if route_meta.get("used_browser_open"):
                                    summary["browser_open_menu_hits"] = int(
                                        summary.get("browser_open_menu_hits") or 0
                                    ) + 1
                                    increment_batch_metric(summary, batch_idx, "browser_open_menu_hits")
                                if route_meta.get("used_template_match"):
                                    summary["template_match_hits"] = int(summary.get("template_match_hits") or 0) + 1
                                    increment_batch_metric(summary, batch_idx, "template_match_hits")
                                append_stage_log(
                                    summary,
                                    batch_index=batch_idx,
                                    row_index=row_idx,
                                    stage="url_extract_profile",
                                    outcome="success" if article_url else "info",
                                    detail=(
                                        article_url
                                        or (
                                            f"profile={profile_name}:miss:"
                                            f"accessibility={int(route_meta.get('accessibility_candidates') or 0)}:"
                                            f"template={int(route_meta.get('template_candidates') or 0)}:"
                                            f"budget={'hit' if route_meta.get('budget_exhausted') else 'ok'}"
                                            f"{':surface=' + str(route_meta.get('surface_state')) if route_meta.get('surface_state') else ''}"
                                            f"{':prime=' + str(route_meta.get('action_surface_prime')) if route_meta.get('action_surface_prime') else ''}"
                                            f"{':menu=' + str(route_meta.get('menu_visual_state')) if route_meta.get('menu_visual_state') else ''}"
                                            f"{':menu_diff=' + str(route_meta.get('menu_visual_change')) if route_meta.get('menu_visual_state') else ''}"
                                            f"{':debug=' + str(route_meta.get('debug_artifact')) if route_meta.get('debug_artifact') else ''}"
                                            f"{':menu_debug=' + str(route_meta.get('menu_debug_artifact')) if route_meta.get('menu_debug_artifact') else ''}"
                                        )
                                    ),
                                )
                                emit_progress()
                                if article_url:
                                    article_url_route_kind = "share_copy"
                                    resolved_profile = normalize_text(str(route_meta.get("resolved_profile") or profile_name))
                                    article_url_stage_label = f"share_copy_url_detected:{resolved_profile or profile_name}"
                                    break
                                template_only_miss_streak = (
                                    template_only_miss_streak + 1 if _is_template_only_profile_miss(route_meta) else 0
                                )
                                if not route_meta.get("accessibility_candidates") and not route_meta.get("template_candidates"):
                                    append_stage_log(
                                        summary,
                                        batch_index=batch_idx,
                                        row_index=row_idx,
                                        stage="url_extract_profile_stop",
                                        outcome="info",
                                        detail=f"profile={profile_name}:no_action_signal",
                                    )
                                    emit_progress()
                                    break
                                should_stop_profile_probe, stop_reason = _should_stop_profile_probe_after_miss(
                                    profile_name=profile_name,
                                    route_meta=route_meta,
                                    template_only_miss_streak=template_only_miss_streak,
                                )
                                if should_stop_profile_probe:
                                    append_stage_log(
                                        summary,
                                        batch_index=batch_idx,
                                        row_index=row_idx,
                                        stage="url_extract_profile_stop",
                                        outcome="info",
                                        detail=f"profile={profile_name}:{stop_reason}",
                                    )
                                    emit_progress()
                                    break
                        targeted_ocr_fallback_reason = _targeted_ocr_fallback_reason(
                            allow_ocr_fallback=allow_ocr_fallback,
                            allow_targeted_ocr_fallback=allow_targeted_ocr_fallback,
                            article_url=article_url,
                            route_meta=route_meta,
                        )
                        if article_url:
                            if not is_allowed_article_url(article_url):
                                append_stage_log(
                                    summary,
                                    batch_index=batch_idx,
                                    row_index=row_idx,
                                    stage="url_validate",
                                    outcome="error",
                                    detail=f"invalid_browser_url:{article_url}",
                                )
                                emit_progress()
                                recover_feed_state(
                                    batch_index=batch_idx,
                                    row_index=row_idx,
                                    reason=f"invalid_browser_url:{article_url}",
                                )
                                bump_non_article_view_streak(
                                    batch_idx=batch_idx,
                                    row_idx=row_idx,
                                    reason=f"invalid_browser_url:{article_url}",
                                )
                                if attempt_idx + 1 >= verify_retries:
                                    summary["skipped_invalid_article"] += 1
                                    increment_batch_metric(summary, batch_idx, "skipped_invalid_article")
                                    summary["errors"].append(
                                        f"batch={batch_idx + 1},row={row_idx + 1}: invalid_browser_url={article_url}"
                                    )
                                    append_row_result(
                                        summary,
                                        batch_index=batch_idx,
                                        row_index=row_idx,
                                        status="skipped_invalid_article",
                                        detail=f"invalid_browser_url:{article_url}",
                                        attempts=attempt_idx + 1,
                                    )
                                    emit_progress()
                                    bump_route_issue_streak(
                                        batch_idx=batch_idx,
                                        row_idx=row_idx,
                                        reason=f"invalid_browser_url:{article_url}",
                                    )
                                    row_done = True
                                continue
                            if try_submit_article_url(
                                article_url,
                                batch_idx=batch_idx,
                                row_idx=row_idx,
                                attempt_idx=attempt_idx,
                                stage_label=article_url_stage_label or "direct_url_detected",
                                stage_detail=article_url,
                                route_kind=article_url_route_kind or "direct",
                            ):
                                reset_non_article_view_streak()
                                row_done = True
                                break
                        if normalize_text(str(route_meta.get("surface_state") or "")).lower() == "dark_blank":
                            append_stage_log(
                                summary,
                                batch_index=batch_idx,
                                row_index=row_idx,
                                stage="url_extract_surface",
                                outcome="info",
                                detail="dark_blank",
                            )
                            emit_progress()
                            recover_feed_state(
                                batch_index=batch_idx,
                                row_index=row_idx,
                                reason="dark_blank_surface",
                            )
                            bump_non_article_view_streak(
                                batch_idx=batch_idx,
                                row_idx=row_idx,
                                reason="dark_blank_surface",
                            )
                            bump_route_issue_streak(
                                batch_idx=batch_idx,
                                row_idx=row_idx,
                                reason="dark_blank_surface",
                            )
                            if attempt_idx + 1 >= verify_retries:
                                summary["skipped_invalid_article"] += 1
                                increment_batch_metric(summary, batch_idx, "skipped_invalid_article")
                                append_row_result(
                                    summary,
                                    batch_index=batch_idx,
                                    row_index=row_idx,
                                    status="skipped_invalid_article",
                                    detail="dark_blank_surface",
                                    attempts=attempt_idx + 1,
                                )
                                emit_progress()
                                row_done = True
                                break
                            continue
                        if not allow_ocr_fallback and not targeted_ocr_fallback_reason:
                            append_stage_log(
                                summary,
                                batch_index=batch_idx,
                                row_index=row_idx,
                                stage="ocr_fallback",
                                outcome="info",
                                detail="disabled:url_only_mode",
                            )
                            recover_feed_state(
                                batch_index=batch_idx,
                                row_index=row_idx,
                                reason="url_only_no_article_url",
                            )
                            bump_non_article_view_streak(
                                batch_idx=batch_idx,
                                row_idx=row_idx,
                                reason="url_only_no_article_url",
                            )
                            bump_route_issue_streak(
                                batch_idx=batch_idx,
                                row_idx=row_idx,
                                reason="url_only_no_article_url",
                            )
                            if attempt_idx + 1 >= verify_retries:
                                summary["url_only_skip_count"] = int(summary.get("url_only_skip_count") or 0) + 1
                                append_row_result(
                                    summary,
                                    batch_index=batch_idx,
                                    row_index=row_idx,
                                    status="skipped_invalid_article",
                                    detail="url_only_no_article_url",
                                    attempts=attempt_idx + 1,
                                )
                                emit_progress()
                                row_done = True
                                break
                            continue
                        if targeted_ocr_fallback_reason:
                            append_stage_log(
                                summary,
                                batch_index=batch_idx,
                                row_index=row_idx,
                                stage="ocr_fallback",
                                outcome="info",
                                detail=f"targeted:{targeted_ocr_fallback_reason}",
                            )
                            emit_progress()

                        shot_path = temp_root / f"article_b{batch_idx}_r{row_idx}_{int(time.time() * 1000)}.png"
                        append_stage_log(
                            summary,
                            batch_index=batch_idx,
                            row_index=row_idx,
                            stage="capture_prepare",
                            outcome="info",
                            detail=shot_path.name,
                        )
                        emit_progress()
                        capture_region(
                            resolve_region(
                                effective_capture_region_cfg,
                                coordinate_mode=coordinate_mode,
                                app_name=app_name,
                            ),
                            shot_path,
                        )
                        summary["captured"] += 1
                        append_stage_log(
                            summary,
                            batch_index=batch_idx,
                            row_index=row_idx,
                            stage="capture",
                            outcome="info",
                            detail=shot_path.name,
                        )
                        emit_progress()

                        file_size_kb = int(shot_path.stat().st_size / 1024)
                        if file_size_kb < min_capture_file_size_kb:
                            if attempt_idx + 1 >= verify_retries:
                                summary["skipped_low_quality"] += 1
                                increment_batch_metric(summary, batch_idx, "skipped_low_quality")
                                append_row_result(
                                    summary,
                                    batch_index=batch_idx,
                                    row_index=row_idx,
                                    status="skipped_low_quality",
                                    detail=f"capture_file_size_kb={file_size_kb}",
                                    attempts=attempt_idx + 1,
                                )
                                emit_progress()
                                recover_feed_state(
                                    batch_index=batch_idx,
                                    row_index=row_idx,
                                    reason=f"low_quality_capture:{file_size_kb}kb",
                                )
                                row_done = True
                            continue

                        active_capture_path = shot_path
                        image_base64 = to_base64(active_capture_path)
                        preview_source_url = None
                        preview_digest = None
                        preview_title_digest = None
                        if verify_with_ocr:
                            preview = None
                            article_ok = False
                            article_reason = "preview_missing"
                            body_focus_retry_done = False
                            while True:
                                attempted_preview_variants: set[str] = set()
                                preview_variant_queue: list[tuple[str, Path]] = [("base", active_capture_path)]
                                while preview_variant_queue:
                                    preview_variant_name, preview_variant_path = preview_variant_queue.pop(0)
                                    if preview_variant_name in attempted_preview_variants:
                                        continue
                                    attempted_preview_variants.add(preview_variant_name)
                                    current_base64 = image_base64 if preview_variant_path == active_capture_path else to_base64(preview_variant_path)
                                    append_stage_log(
                                        summary,
                                        batch_index=batch_idx,
                                        row_index=row_idx,
                                        stage="ocr_preview",
                                        outcome="info",
                                        detail=f"attempt={attempt_idx + 1}:variant={preview_variant_name}",
                                    )
                                    emit_progress()
                                    preview = request_ocr_preview(
                                        api_base,
                                        image_base64=current_base64,
                                        mime_type="image/png",
                                        source_url=None,
                                        title_hint=title_hint,
                                        output_language=language,
                                        timeout_sec=120,
                                    )
                                    article_ok, article_reason = validate_article_preview(
                                        preview,
                                        min_text_length=verify_min_text_length,
                                    )
                                    if article_ok:
                                        active_capture_path = preview_variant_path
                                        image_base64 = current_base64
                                        append_stage_log(
                                            summary,
                                            batch_index=batch_idx,
                                            row_index=row_idx,
                                            stage="ocr_preview",
                                            outcome="success",
                                            detail=f"{preview_variant_name}:{article_reason}",
                                        )
                                        emit_progress()
                                        break
                                    append_stage_log(
                                        summary,
                                        batch_index=batch_idx,
                                        row_index=row_idx,
                                        stage="ocr_preview",
                                        outcome="error",
                                        detail=f"{preview_variant_name}:{article_reason}",
                                    )
                                    emit_progress()
                                    if preview_variant_name != "base":
                                        continue
                                    retry_variants = _select_capture_variant_profiles(article_reason)
                                    if not retry_variants:
                                        continue
                                    append_stage_log(
                                        summary,
                                        batch_index=batch_idx,
                                        row_index=row_idx,
                                        stage="capture_variant",
                                        outcome="info",
                                        detail=f"{_normalize_capture_variant_reason(article_reason)}:{','.join(retry_variants)}",
                                    )
                                    emit_progress()
                                    for retry_variant_name in retry_variants:
                                        if retry_variant_name in attempted_preview_variants:
                                            continue
                                        retry_path = _materialize_capture_variant(
                                            shot_path,
                                            variant_name=retry_variant_name,
                                            temp_root=temp_root,
                                        )
                                        if retry_path is None:
                                            continue
                                        preview_variant_queue.append((retry_variant_name, retry_path))
                                if article_ok or body_focus_retry_done:
                                    break
                                focus_profile = _focus_article_body_view(
                                    wechat_app_name=app_name,
                                    coordinate_mode=coordinate_mode,
                                    article_region=effective_capture_region_cfg,
                                    reason=article_reason,
                                )
                                body_focus_retry_done = True
                                if not focus_profile:
                                    break
                                append_stage_log(
                                    summary,
                                    batch_index=batch_idx,
                                    row_index=row_idx,
                                    stage="article_refocus",
                                    outcome="info",
                                    detail=f"{focus_profile}:{_normalize_capture_variant_reason(article_reason)}",
                                )
                                emit_progress()
                                active_capture_path = temp_root / (
                                    f"{shot_path.stem}_focus_{int(time.time() * 1000)}.png"
                                )
                                append_stage_log(
                                    summary,
                                    batch_index=batch_idx,
                                    row_index=row_idx,
                                    stage="capture_prepare",
                                    outcome="info",
                                    detail=active_capture_path.name,
                                )
                                emit_progress()
                                capture_region(
                                    resolve_region(
                                        effective_capture_region_cfg,
                                        coordinate_mode=coordinate_mode,
                                        app_name=app_name,
                                    ),
                                    active_capture_path,
                                )
                                summary["captured"] += 1
                                append_stage_log(
                                    summary,
                                    batch_index=batch_idx,
                                    row_index=row_idx,
                                    stage="capture",
                                    outcome="info",
                                    detail=active_capture_path.name,
                                )
                                emit_progress()
                                image_base64 = to_base64(active_capture_path)
                            if not article_ok or preview is None:
                                if attempt_idx + 1 >= verify_retries:
                                    summary["skipped_invalid_article"] += 1
                                    increment_batch_metric(summary, batch_idx, "skipped_invalid_article")
                                    summary["errors"].append(
                                        f"batch={batch_idx + 1},row={row_idx + 1}: invalid_article={article_reason}"
                                    )
                                    append_row_result(
                                        summary,
                                        batch_index=batch_idx,
                                        row_index=row_idx,
                                        status="skipped_invalid_article",
                                        detail=article_reason,
                                        attempts=attempt_idx + 1,
                                    )
                                    emit_progress()
                                    recover_feed_state(
                                        batch_index=batch_idx,
                                        row_index=row_idx,
                                        reason=f"invalid_article:{article_reason}",
                                    )
                                    bump_non_article_view_streak(
                                        batch_idx=batch_idx,
                                        row_idx=row_idx,
                                        reason=f"invalid_article:{article_reason}",
                                    )
                                    row_done = True
                                continue
                            preview_digest = build_preview_digest(preview)
                            preview_title_digest = build_preview_title_digest(preview)
                            preview_source_url = f"https://wechat.local/article/{file_sha1(active_capture_path)}"
                            recency_status, recency_detail = register_article_recency(
                                batch_idx=batch_idx,
                                row_idx=row_idx,
                                preview=preview,
                            )
                            emit_progress()
                            if scan_today_unread_only and recency_status == "old":
                                append_row_result(
                                    summary,
                                    batch_index=batch_idx,
                                    row_index=row_idx,
                                    status="skipped_seen",
                                    detail=f"older_article:{recency_detail}",
                                    attempts=attempt_idx + 1,
                                )
                                recover_feed_state(
                                    batch_index=batch_idx,
                                    row_index=row_idx,
                                    reason=f"older_article:{recency_detail}",
                                )
                                row_done = True
                                break
                            url_resolve_candidate_limit, url_resolve_timeout_sec, url_resolve_skip_reason = (
                                _plan_preview_url_resolve_budget(
                                    preview=preview,
                                    title_hint=title_hint,
                                    targeted_fallback=bool(targeted_ocr_fallback_reason),
                                    targeted_timeout_sec=targeted_url_resolve_timeout_sec,
                                )
                            )
                            if url_resolve_skip_reason:
                                append_stage_log(
                                    summary,
                                    batch_index=batch_idx,
                                    row_index=row_idx,
                                    stage="url_resolve_skip",
                                    outcome="info",
                                    detail=url_resolve_skip_reason,
                                )
                                emit_progress()
                            else:
                                try:
                                    append_stage_log(
                                        summary,
                                        batch_index=batch_idx,
                                        row_index=row_idx,
                                        stage="url_resolve",
                                        outcome="info",
                                        detail=(
                                            normalize_text(str(preview.get("title") or title_hint or ""))[:96]
                                            + f":timeout={url_resolve_timeout_sec}s"
                                        ),
                                    )
                                    emit_progress()
                                    url_resolve = request_url_resolve(
                                        api_base,
                                        title_hint=str(preview.get("title") or title_hint or ""),
                                        body_preview=str(preview.get("body_preview") or ""),
                                        body_text=str(preview.get("body_text") or ""),
                                        candidate_limit=url_resolve_candidate_limit,
                                        timeout_sec=url_resolve_timeout_sec,
                                    )
                                    resolved_url = normalize_http_url(url_resolve.get("resolved_url"))
                                    if resolved_url and is_allowed_article_url(resolved_url):
                                        if try_submit_article_url(
                                            resolved_url,
                                            batch_idx=batch_idx,
                                            row_idx=row_idx,
                                            attempt_idx=attempt_idx,
                                            stage_label="url_resolve",
                                            stage_detail=f"{resolved_url} ({url_resolve.get('matched_via') or 'search'})",
                                            route_kind="resolved",
                                            related_digests=[item for item in [preview_digest, preview_title_digest] if item],
                                        ):
                                            reset_non_article_view_streak()
                                            row_done = True
                                            break
                                    append_stage_log(
                                        summary,
                                        batch_index=batch_idx,
                                        row_index=row_idx,
                                        stage="url_resolve",
                                        outcome="error" if not resolved_url else "info",
                                        detail=(url_resolve.get("matched_via") or "no_resolved_url"),
                                    )
                                    emit_progress()
                                except Exception as exc:  # noqa: BLE001
                                    append_stage_log(
                                        summary,
                                        batch_index=batch_idx,
                                        row_index=row_idx,
                                        stage="url_resolve",
                                        outcome="error",
                                        detail=str(exc),
                                    )
                                    emit_progress()
                        else:
                            preview_source_url = f"https://wechat.local/article/{file_sha1(active_capture_path)}"

                        digest = file_sha1(active_capture_path)
                        perceptual_digest = file_perceptual_hash(active_capture_path)
                        similar_perceptual_digest, similar_perceptual_distance = find_similar_perceptual_hash(
                            state,
                            perceptual_digest,
                            threshold=6,
                        )
                        if similar_perceptual_digest:
                            summary["perceptual_duplicate_count"] = int(
                                summary.get("perceptual_duplicate_count") or 0
                            ) + 1
                            increment_batch_metric(summary, batch_idx, "perceptual_duplicate_count")
                            if perceptual_digest:
                                remember_hash(state, perceptual_digest, max_items=dedup_max)
                            reset_route_issue_streak()
                            bump_duplicate_article_streak(
                                batch_idx=batch_idx,
                                row_idx=row_idx,
                                reason="perceptual_duplicate",
                            )
                            summary["skipped_seen"] += 1
                            increment_batch_metric(summary, batch_idx, "skipped_seen")
                            append_stage_log(
                                summary,
                                batch_index=batch_idx,
                                row_index=row_idx,
                                stage="perceptual_dedup",
                                outcome="info",
                                detail=f"distance={similar_perceptual_distance or 0}",
                            )
                            append_row_result(
                                summary,
                                batch_index=batch_idx,
                                row_index=row_idx,
                                status="skipped_seen",
                                detail=f"perceptual_duplicate:{similar_perceptual_distance or 0}",
                                attempts=attempt_idx + 1,
                            )
                            emit_progress()
                            recover_feed_state(
                                batch_index=batch_idx,
                                row_index=row_idx,
                                reason=f"perceptual_duplicate:{similar_perceptual_distance or 0}",
                            )
                            row_done = True
                            break
                        preview_seen = bool(preview_digest and was_seen(state, preview_digest))
                        preview_title_seen = bool(preview_title_digest and was_seen(state, preview_title_digest))
                        screenshot_seen = was_seen(state, digest)
                        if preview_seen or preview_title_seen or screenshot_seen:
                            if preview_title_digest:
                                remember_hash(state, preview_title_digest, max_items=dedup_max)
                            if perceptual_digest:
                                remember_hash(state, perceptual_digest, max_items=dedup_max)
                            if preview_seen:
                                duplicate_reason = "ocr_preview_seen"
                                summary["ocr_preview_seen_count"] = int(summary.get("ocr_preview_seen_count") or 0) + 1
                            elif preview_title_seen:
                                duplicate_reason = "ocr_title_seen"
                                summary["ocr_title_seen_count"] = int(summary.get("ocr_title_seen_count") or 0) + 1
                            else:
                                duplicate_reason = "ocr_digest_seen"
                            bump_duplicate_article_streak(
                                batch_idx=batch_idx,
                                row_idx=row_idx,
                                reason=duplicate_reason,
                            )
                            summary["skipped_seen"] += 1
                            increment_batch_metric(summary, batch_idx, "skipped_seen")
                            append_row_result(
                                summary,
                                batch_index=batch_idx,
                                row_index=row_idx,
                                status="skipped_seen",
                                detail=duplicate_reason,
                                attempts=attempt_idx + 1,
                            )
                            emit_progress()
                            recover_feed_state(
                                batch_index=batch_idx,
                                row_index=row_idx,
                                reason=duplicate_reason,
                            )
                            bump_route_issue_streak(
                                batch_idx=batch_idx,
                                row_idx=row_idx,
                                reason=duplicate_reason,
                            )
                            row_done = True
                            break

                        payload = {
                            "image_base64": image_base64,
                            "mime_type": "image/png",
                            "source_url": preview_source_url,
                            "title_hint": title_hint,
                            "output_language": language,
                            "deduplicate": True,
                            "process_immediately": False,
                        }
                        response: dict[str, Any] | None = None
                        last_ingest_error: Exception | None = None
                        for ingest_attempt in range(2):
                            append_stage_log(
                                summary,
                                batch_index=batch_idx,
                                row_index=row_idx,
                                stage="ocr_ingest",
                                outcome="info",
                                detail=f"attempt={ingest_attempt + 1}",
                            )
                            emit_progress()
                            try:
                                response = post_json(
                                    api_base,
                                    "/api/collector/ocr/ingest",
                                    payload,
                                    timeout_sec=120,
                                )
                                break
                            except Exception as exc:  # noqa: BLE001
                                last_ingest_error = exc
                                append_stage_log(
                                    summary,
                                    batch_index=batch_idx,
                                    row_index=row_idx,
                                    stage="ocr_ingest",
                                    outcome="error",
                                    detail=str(exc),
                                )
                                emit_progress()
                                if ingest_attempt == 0:
                                    time.sleep(1.0)
                        if response is None:
                            raise RuntimeError(f"ingest failed: {last_ingest_error}")
                        item = response.get("item") if isinstance(response, dict) else None
                        item_id = item.get("id") if isinstance(item, dict) else None
                        deduplicated = bool(response.get("deduplicated")) if isinstance(response, dict) else False
                        if item_id:
                            summary["item_ids"].append(item_id)
                        summary["submitted"] += 1
                        summary["submitted_ocr"] += 1
                        increment_batch_metric(summary, batch_idx, "submitted")
                        increment_batch_metric(summary, batch_idx, "submitted_ocr")
                        if deduplicated:
                            bump_duplicate_article_streak(
                                batch_idx=batch_idx,
                                row_idx=row_idx,
                                reason="deduplicated_existing_ocr",
                            )
                            summary["deduplicated_existing"] += 1
                            summary["deduplicated_existing_ocr"] += 1
                            increment_batch_metric(summary, batch_idx, "deduplicated_existing")
                        else:
                            reset_duplicate_article_streak()
                            reset_non_article_view_streak()
                            summary["submitted_new"] += 1
                            increment_batch_metric(summary, batch_idx, "submitted_new")
                            if item_id:
                                summary["new_item_ids"].append(item_id)
                        remember_hash(state, digest, max_items=dedup_max)
                        if preview_digest:
                            remember_hash(state, preview_digest, max_items=dedup_max)
                        if preview_title_digest:
                            remember_hash(state, preview_title_digest, max_items=dedup_max)
                        if perceptual_digest:
                            remember_hash(state, perceptual_digest, max_items=dedup_max)
                        reset_route_issue_streak()
                        append_stage_log(
                            summary,
                            batch_index=batch_idx,
                            row_index=row_idx,
                            stage="ocr_ingest",
                            outcome="success",
                            detail=(f"deduplicated:{item_id}" if deduplicated else (item_id or preview_source_url)),
                        )
                        append_row_result(
                            summary,
                            batch_index=batch_idx,
                            row_index=row_idx,
                            status="deduplicated_existing_ocr" if deduplicated else "submitted_ocr",
                            detail=preview_source_url,
                            attempts=attempt_idx + 1,
                            item_id=item_id,
                        )
                        emit_progress()
                        recover_feed_state(
                            batch_index=batch_idx,
                            row_index=row_idx,
                            reason="submitted_ocr",
                        )
                        row_done = True
                        break
                    except Exception as exc:  # noqa: BLE001
                        error_text = str(exc)
                        recover_feed_state(
                            batch_index=batch_idx,
                            row_index=row_idx,
                            reason=f"exception:{error_text}",
                        )
                        if (
                            "unexpected_front_process" in error_text
                            or "invalid_browser_url" in error_text
                            or "invalid_browser_url:" in error_text
                            or "_timeout" in error_text
                        ):
                            bump_route_issue_streak(
                                batch_idx=batch_idx,
                                row_idx=row_idx,
                                reason=error_text,
                            )
                        if attempt_idx + 1 >= verify_retries:
                            summary["failed"] += 1
                            increment_batch_metric(summary, batch_idx, "failed")
                            summary["errors"].append(
                                f"batch={batch_idx + 1},row={row_idx + 1},attempt={attempt_idx + 1}: {error_text}"
                            )
                            append_row_result(
                                summary,
                                batch_index=batch_idx,
                                row_index=row_idx,
                                status="failed",
                                detail=error_text,
                                attempts=attempt_idx + 1,
                            )
                            emit_progress()
                            row_done = True
                        continue

                if not row_done:
                    append_row_result(
                        summary,
                        batch_index=batch_idx,
                        row_index=row_idx,
                        status="unfinished",
                        detail="row exited without terminal state",
                        attempts=verify_retries,
                    )
                    emit_progress()
                processed_count += 1
                if between_item_delay > 0:
                    time.sleep(between_item_delay)

            if processed_count >= effective_max_items or stop_scan_requested:
                break
            append_stage_log(
                summary,
                batch_index=batch_idx,
                row_index=rows_per_batch - 1,
                stage="batch_end",
                outcome="info",
                detail=f"processed_count={processed_count}",
            )
            emit_progress()

    summary["finished_at"] = iso_now()
    summary["processed_hashes"] = len(state.get("processed_hashes", {}))
    return summary


def write_report(report_file: Path, report: dict[str, Any]) -> None:
    write_json(report_file, report)


def append_state_run(state: dict[str, Any], report: dict[str, Any]) -> None:
    runs = state.get("runs", [])
    runs.append(
        {
            "started_at": report.get("started_at"),
            "finished_at": report.get("finished_at"),
            "submitted": report.get("submitted", 0),
            "skipped_seen": report.get("skipped_seen", 0),
            "failed": report.get("failed", 0),
            "item_ids": report.get("item_ids", [])[:24],
        }
    )
    state["runs"] = runs[-300:]


def _compute_next_loop_batch_index(config: dict[str, Any], used_start_batch_index: int) -> int:
    batches_per_cycle = _coerce_int(config.get("batches_per_cycle"), 5, 1, 30)
    wrap_after_batches = max(batches_per_cycle * 6, 12)
    next_batch_index = max(0, int(used_start_batch_index)) + batches_per_cycle
    if next_batch_index >= wrap_after_batches:
        return 0
    return next_batch_index


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WeChat PC full-auto collector agent (URL first, OCR fallback)")
    parser.add_argument("--config", default=str(TMP_DIR / "wechat_pc_agent_config.json"))
    parser.add_argument("--state-file", default=str(TMP_DIR / "wechat_pc_agent_state.json"))
    parser.add_argument("--report-file", default=str(TMP_DIR / "wechat_pc_agent_latest.json"))
    parser.add_argument("--loop", action="store_true", help="Run forever")
    parser.add_argument("--interval-sec", type=int, default=300, help="Loop interval in seconds")
    parser.add_argument("--max-items", type=int, default=None, help="Max articles per cycle")
    parser.add_argument("--start-batch-index", type=int, default=0, help="Start feed scan from batch index")
    parser.add_argument("--output-language", default=None, help="zh-CN|zh-TW|en|ja|ko")
    parser.add_argument("--api-base", default=None, help="Override API base")
    parser.add_argument("--init-config-only", action="store_true", help="Create config file then exit")
    return parser.parse_args(argv)


def run_once(paths: AgentPaths, args: argparse.Namespace) -> int:
    config = load_config(paths.config_file)
    if args.api_base:
        config["api_base"] = str(args.api_base).rstrip("/")
    if args.output_language:
        config["output_language"] = args.output_language

    state = load_state(paths.state_file)

    def write_progress(snapshot: dict[str, Any]) -> None:
        progress_report = dict(snapshot)
        progress_report["running"] = True
        write_report(paths.report_file, progress_report)

    try:
        report = run_cycle(
            config,
            state,
            max_items=args.max_items,
            output_language=args.output_language,
            start_batch_index=args.start_batch_index,
            progress_callback=write_progress,
        )
    except Exception as exc:  # noqa: BLE001
        report = {
            "started_at": iso_now(),
            "finished_at": iso_now(),
            "submitted": 0,
            "skipped_seen": 0,
            "failed": 1,
            "errors": [str(exc)],
        }
        write_report(paths.report_file, report)
        append_state_run(state, report)
        save_state(paths.state_file, state)
        log(f"cycle failed: {exc}")
        return 1

    write_report(paths.report_file, report)
    append_state_run(state, report)
    save_state(paths.state_file, state)

    log(
        "cycle done "
        f"submitted={report.get('submitted', 0)} "
        f"skipped={report.get('skipped_seen', 0)} "
        f"failed={report.get('failed', 0)}"
    )
    errors = report.get("errors", [])
    if isinstance(errors, list) and errors:
        log(f"first_error: {errors[0]}")
    if (
        int(report.get("failed", 0) or 0) > 0
        and int(report.get("submitted", 0) or 0) == 0
        and int(report.get("skipped_seen", 0) or 0) == 0
    ):
        return 2
    return 0


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    paths = AgentPaths(
        config_file=Path(args.config).expanduser().resolve(),
        state_file=Path(args.state_file).expanduser().resolve(),
        report_file=Path(args.report_file).expanduser().resolve(),
    )

    ensure_config_file(paths.config_file)
    if args.init_config_only:
        log(f"config ready: {paths.config_file}")
        return 0

    if not args.loop:
        return run_once(paths, args)

    interval = max(20, int(args.interval_sec))
    log(
        f"loop start interval={interval}s config={paths.config_file} "
        f"state={paths.state_file} report={paths.report_file}"
    )
    while True:
        started = time.time()
        loop_state = load_state(paths.state_file)
        loop_start_batch_index = max(0, int(loop_state.get("loop_next_batch_index") or args.start_batch_index or 0))
        loop_args = argparse.Namespace(**vars(args))
        loop_args.start_batch_index = loop_start_batch_index
        run_once(paths, loop_args)
        post_state = load_state(paths.state_file)
        config = load_config(paths.config_file)
        post_state["loop_next_batch_index"] = _compute_next_loop_batch_index(config, loop_start_batch_index)
        save_state(paths.state_file, post_state)
        elapsed = time.time() - started
        sleep_sec = max(1, interval - int(elapsed))
        time.sleep(sleep_sec)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
