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


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TMP_DIR = PROJECT_ROOT / ".tmp"

DEFAULT_CONFIG: dict[str, Any] = {
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


def _applescript(lines: list[str]) -> str:
    command: list[str] = ["osascript"]
    for line in lines:
        command.extend(["-e", line])
    run = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
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
        run = subprocess.run(
            [cliclick, f"c:{x},{y}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if run.returncode == 0:
            return

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
            run = subprocess.run(
                [cliclick, f"kp:{key_name}"],
                capture_output=True,
                text=True,
                check=False,
            )
            if run.returncode == 0:
                return

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


def read_clipboard_text() -> str:
    run = subprocess.run(
        ["pbpaste"],
        capture_output=True,
        text=True,
        check=False,
    )
    if run.returncode != 0:
        return ""
    return str(run.stdout or "")


def write_clipboard_text(value: str) -> None:
    subprocess.run(
        ["pbcopy"],
        input=value,
        text=True,
        capture_output=True,
        check=False,
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


def build_preview_digest(preview: dict[str, Any]) -> str | None:
    title = normalize_text(str(preview.get("title") or ""))
    body = normalize_text(str(preview.get("body_text") or preview.get("body_preview") or ""))
    seed = "\n".join(part for part in [title, body[:320]] if part).strip()
    if len(seed) < 24:
        return None
    return f"preview:{hashlib.sha1(seed.encode('utf-8')).hexdigest()}"


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
    browser_names = {
        "Safari",
        "Google Chrome",
        "Chromium",
        "Arc",
        "Brave Browser",
        "Microsoft Edge",
        "Opera",
        "Vivaldi",
    }
    allowed = {wechat_app_name, "WeChat", *browser_names}
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
    if current in {
        "Safari",
        "Google Chrome",
        "Chromium",
        "Arc",
        "Brave Browser",
        "Microsoft Edge",
        "Opera",
        "Vivaldi",
    }:
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


def try_extract_article_url_from_wechat_ui(
    *,
    wechat_app_name: str,
    coordinate_mode: str,
    article_region: dict[str, Any],
    link_profile: str = "auto",
    share_hotspots: list[dict[str, int]] | None = None,
    menu_offsets: list[dict[str, int]] | None = None,
) -> str | None:
    front_process_name = get_front_process_name()
    if front_process_name not in {wechat_app_name, "WeChat"}:
        return None

    resolved = resolve_region(article_region, coordinate_mode=coordinate_mode, app_name=wechat_app_name)
    region_x = int(resolved.get("x") or 0)
    region_y = int(resolved.get("y") or 0)
    region_width = int(resolved.get("width") or 0)
    if region_width <= 0:
        return None

    share_points, menu_points, resolved_profile = _build_article_link_points(
        region_x=region_x,
        region_y=region_y,
        region_width=region_width,
        profile_name=link_profile,
        share_hotspots=share_hotspots,
        menu_offsets=menu_offsets,
    )
    original_clipboard = read_clipboard_text()
    browser_names = {
        "Safari",
        "Google Chrome",
        "Chromium",
        "Arc",
        "Brave Browser",
        "Microsoft Edge",
        "Opera",
        "Vivaldi",
    }
    try:
        for share_x, share_y in share_points:
            try:
                click_at(share_x, share_y)
                time.sleep(0.4)
            except Exception:
                continue

            front_after_click = get_front_process_name()
            if front_after_click in browser_names:
                browser_url = wait_for_allowed_front_browser_url(front_after_click or "")
                if is_allowed_article_url(browser_url):
                    return browser_url

            for option_dx, option_dy in menu_points:
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
                if front_after_option in browser_names:
                    browser_url = wait_for_allowed_front_browser_url(front_after_option or "")
                    if is_allowed_article_url(browser_url):
                        return browser_url

                clipboard_url = normalize_http_url(read_clipboard_text())
                if is_allowed_article_url(clipboard_url):
                    return clipboard_url

                _dismiss_wechat_overlay()

            try:
                write_clipboard_text("")
                key_combo_command("c")
                time.sleep(0.25)
            except Exception:
                pass
            clipboard_url = normalize_http_url(read_clipboard_text())
            if is_allowed_article_url(clipboard_url):
                return clipboard_url

            _dismiss_wechat_overlay()
    finally:
        try:
            if original_clipboard:
                write_clipboard_text(original_clipboard)
        except Exception:
            pass
    return None


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
    run = subprocess.run(
        [
            "screencapture",
            "-x",
            f"-R{x},{y},{width},{height}",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
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
        run = subprocess.run(
            ["which", command],
            capture_output=True,
            text=True,
            check=False,
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
    rows_per_batch = _coerce_int(config.get("rows_per_batch"), 1, 1, 20)
    batches_per_cycle = _coerce_int(config.get("batches_per_cycle"), 5, 1, 30)
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
    verify_with_ocr = _coerce_bool(config.get("article_verify_with_ocr"), True)
    verify_min_text_length = _coerce_int(config.get("article_verify_min_text_length"), 120, 60, 1200)
    verify_retries = _coerce_int(config.get("article_verify_retries"), 2, 1, 5)
    capture_region_cfg = config.get("article_capture_region") or {}
    link_hotspots_cfg = config.get("article_link_hotspots") or []
    link_menu_offsets_cfg = config.get("article_link_menu_offsets") or []

    effective_max_items = max_items if max_items is not None else rows_per_batch * batches_per_cycle
    effective_max_items = max(1, min(200, int(effective_max_items)))
    start_batch_index = max(0, int(start_batch_index or 0))

    activate_wechat(bundle_id, app_name)
    time.sleep(0.9)

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
        activate_wechat(bundle_id, app_name)
        if not wait_for_front_process({app_name, "WeChat"}, timeout_sec=1.8, interval_sec=0.2):
            raise RuntimeError("wechat_not_frontmost_after_activate")
        try:
            switch_to_main_wechat_window(app_name)
            time.sleep(0.35)
            activate_wechat(bundle_id, app_name)
        except Exception:
            pass
        usable_window, rect = get_usable_window_rect(app_name)
        if not usable_window:
            try:
                switch_to_main_wechat_window(app_name)
                time.sleep(0.5)
            except Exception:
                pass
            usable_window, rect = get_usable_window_rect(app_name)
            if not usable_window:
                rect_text = "unknown" if rect is None else f"{rect[2]}x{rect[3]}"
                raise RuntimeError(f"wechat_window_too_small:{rect_text}")
        time.sleep(0.6)
        cmd_ready = False
        usable_window_after_cmd = False
        rect_after_cmd: tuple[int, int, int, int] | None = None
        for cmd_attempt in range(2):
            key_combo_command("1")
            if wait_for_front_process({app_name, "WeChat"}, timeout_sec=1.0, interval_sec=0.2):
                usable_window_after_cmd, rect_after_cmd = get_usable_window_rect(app_name)
                if usable_window_after_cmd:
                    cmd_ready = True
                    break
            if cmd_attempt == 0:
                try:
                    activate_wechat(bundle_id, app_name)
                    time.sleep(0.3)
                    switch_to_main_wechat_window(app_name)
                    time.sleep(0.3)
                except Exception:
                    pass
        if not cmd_ready:
            if not wait_for_front_process({app_name, "WeChat"}, timeout_sec=0.4, interval_sec=0.2):
                raise RuntimeError("wechat_not_frontmost_after_cmd1")
            usable_window_after_cmd, rect_after_cmd = get_usable_window_rect(app_name)
            if not usable_window_after_cmd:
                rect_text = "unknown" if rect_after_cmd is None else f"{rect_after_cmd[2]}x{rect_after_cmd[3]}"
                raise RuntimeError(f"wechat_window_too_small_after_cmd1:{rect_text}")
        time.sleep(0.35)
        for point_index, (point_x, point_y) in enumerate(public_points[:2]):
            click_x, click_y = resolve_point(point_x, point_y, coordinate_mode=coordinate_mode, app_name=app_name)
            click_at(click_x, click_y)
            time.sleep(0.28 if point_index == 0 else 0.18)
            if not is_unexpected_front_process(get_front_process_name(), wechat_app_name=app_name):
                # Two nearby taps within the same nav target significantly reduce
                # misses on different window sizes without wandering into content.
                continue
        time.sleep(0.45)
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
        append_stage_log(summary, batch_index=batch_index, row_index=row_index, stage="recover", outcome="info", detail=reason)
        try:
            switch_to_main_wechat_window(app_name)
            time.sleep(0.3)
        except Exception:
            pass
        restore_wechat_focus(bundle_id, app_name)
        emit_progress()

    summary: dict[str, Any] = {
        "started_at": iso_now(),
        "api_base": api_base,
        "output_language": language,
        "coordinate_mode": coordinate_mode,
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

    def feed_scroll_pages(batch_idx: int) -> int:
        return max(0, batch_idx * list_page_down + navigation_escape_pages)

    def reset_route_issue_streak() -> None:
        nonlocal route_issue_streak
        route_issue_streak = 0

    def reset_duplicate_article_streak() -> None:
        nonlocal duplicate_article_streak, navigation_escape_pages
        duplicate_article_streak = 0
        navigation_escape_pages = 0

    def bump_duplicate_article_streak(*, batch_idx: int, row_idx: int, reason: str) -> None:
        nonlocal duplicate_article_streak, navigation_escape_pages
        duplicate_article_streak += 1
        if duplicate_article_streak < 2:
            return
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
        emit_progress()

    def bump_route_issue_streak(*, batch_idx: int, row_idx: int, reason: str) -> None:
        nonlocal route_issue_streak
        route_issue_streak += 1
        if route_issue_streak < 2:
            return
        append_stage_log(
            summary,
            batch_index=batch_idx,
            row_index=row_idx,
            stage="route_backoff",
            outcome="info",
            detail=f"streak={route_issue_streak}:{reason}",
        )
        emit_progress()
        if route_issue_streak >= 4:
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
        for url_attempt in range(2):
            append_stage_log(
                summary,
                batch_index=batch_idx,
                row_index=row_idx,
                stage="url_ingest",
                outcome="info",
                detail=f"{stage_label}:attempt={url_attempt + 1}",
            )
            emit_progress()
            try:
                url_response = post_json(
                    api_base,
                    "/api/collector/url/ingest",
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
                    stage="url_ingest",
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
        append_stage_log(
            summary,
            batch_index=batch_idx,
            row_index=row_idx,
            stage="url_ingest",
            outcome="success",
            detail=(f"deduplicated:{item_id}" if deduplicated else (item_id or article_url)),
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
                if processed_count >= effective_max_items:
                    break
                y = list_y + row_idx * row_height
                row_done = False
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
                        item_x, item_y = resolve_point(list_x, y, coordinate_mode=coordinate_mode, app_name=app_name)
                        click_at(item_x, item_y)
                        summary["clicked"] += 1
                        increment_batch_metric(summary, batch_idx, "clicked")
                        append_stage_log(
                            summary,
                            batch_index=batch_idx,
                            row_index=row_idx,
                            stage="click_article",
                            outcome="info",
                            detail=f"x={item_x},y={item_y}",
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

                        article_url = try_copy_current_article_url(wechat_app_name=app_name)
                        article_url_route_kind = "direct" if article_url else ""
                        article_url_stage_label = "direct_url_detected" if article_url else ""
                        if not article_url:
                            for profile_name in _expand_article_link_profiles(article_link_profile):
                                article_url = try_extract_article_url_from_wechat_ui(
                                    wechat_app_name=app_name,
                                    coordinate_mode=coordinate_mode,
                                    article_region=capture_region_cfg,
                                    link_profile=profile_name,
                                    share_hotspots=link_hotspots_cfg if isinstance(link_hotspots_cfg, list) else None,
                                    menu_offsets=link_menu_offsets_cfg if isinstance(link_menu_offsets_cfg, list) else None,
                                )
                                if article_url:
                                    article_url_route_kind = "share_copy"
                                    article_url_stage_label = f"share_copy_url_detected:{profile_name}"
                                    break
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
                                row_done = True
                                break
                        if not allow_ocr_fallback:
                            append_stage_log(
                                summary,
                                batch_index=batch_idx,
                                row_index=row_idx,
                                stage="ocr_fallback",
                                outcome="info",
                                detail="disabled:url_only_mode",
                            )
                            append_row_result(
                                summary,
                                batch_index=batch_idx,
                                row_index=row_idx,
                                status="skipped_invalid_article",
                                detail="url_only_no_article_url",
                                attempts=attempt_idx + 1,
                            )
                            emit_progress()
                            recover_feed_state(
                                batch_index=batch_idx,
                                row_index=row_idx,
                                reason="url_only_no_article_url",
                            )
                            bump_route_issue_streak(
                                batch_idx=batch_idx,
                                row_idx=row_idx,
                                reason="url_only_no_article_url",
                            )
                            row_done = True
                            break

                        shot_path = temp_root / f"article_b{batch_idx}_r{row_idx}_{int(time.time() * 1000)}.png"
                        capture_region(
                            resolve_region(capture_region_cfg, coordinate_mode=coordinate_mode, app_name=app_name),
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

                        image_base64 = to_base64(shot_path)
                        preview_source_url = None
                        preview_digest = None
                        if verify_with_ocr:
                            append_stage_log(
                                summary,
                                batch_index=batch_idx,
                                row_index=row_idx,
                                stage="ocr_preview",
                                outcome="info",
                                detail=f"attempt={attempt_idx + 1}",
                            )
                            emit_progress()
                            preview = request_ocr_preview(
                                api_base,
                                image_base64=image_base64,
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
                            if not article_ok:
                                append_stage_log(
                                    summary,
                                    batch_index=batch_idx,
                                    row_index=row_idx,
                                    stage="ocr_preview",
                                    outcome="error",
                                    detail=article_reason,
                                )
                                emit_progress()
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
                                    row_done = True
                                continue
                            append_stage_log(
                                summary,
                                batch_index=batch_idx,
                                row_index=row_idx,
                                stage="ocr_preview",
                                outcome="success",
                                detail=article_reason,
                            )
                            emit_progress()
                            preview_digest = build_preview_digest(preview)
                            preview_source_url = f"https://wechat.local/article/{file_sha1(shot_path)}"
                            try:
                                append_stage_log(
                                    summary,
                                    batch_index=batch_idx,
                                    row_index=row_idx,
                                    stage="url_resolve",
                                    outcome="info",
                                    detail=normalize_text(str(preview.get("title") or title_hint or ""))[:120],
                                )
                                emit_progress()
                                url_resolve = request_url_resolve(
                                    api_base,
                                    title_hint=str(preview.get("title") or title_hint or ""),
                                    body_preview=str(preview.get("body_preview") or ""),
                                    body_text=str(preview.get("body_text") or ""),
                                    candidate_limit=4,
                                    timeout_sec=45,
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
                                        related_digests=[preview_digest] if preview_digest else None,
                                    ):
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
                            preview_source_url = f"https://wechat.local/article/{file_sha1(shot_path)}"

                        digest = file_sha1(shot_path)
                        preview_seen = bool(preview_digest and was_seen(state, preview_digest))
                        screenshot_seen = was_seen(state, digest)
                        if preview_seen or screenshot_seen:
                            bump_duplicate_article_streak(
                                batch_idx=batch_idx,
                                row_idx=row_idx,
                                reason="ocr_preview_seen" if preview_seen else "ocr_digest_seen",
                            )
                            summary["skipped_seen"] += 1
                            increment_batch_metric(summary, batch_idx, "skipped_seen")
                            append_row_result(
                                summary,
                                batch_index=batch_idx,
                                row_index=row_idx,
                                status="skipped_seen",
                                detail="ocr_preview_seen" if preview_seen else "ocr_digest_seen",
                                attempts=attempt_idx + 1,
                            )
                            emit_progress()
                            recover_feed_state(
                                batch_index=batch_idx,
                                row_index=row_idx,
                                reason="ocr_preview_seen" if preview_seen else "ocr_digest_seen",
                            )
                            bump_route_issue_streak(
                                batch_idx=batch_idx,
                                row_idx=row_idx,
                                reason="ocr_preview_seen" if preview_seen else "ocr_digest_seen",
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
                            summary["submitted_new"] += 1
                            increment_batch_metric(summary, batch_idx, "submitted_new")
                            if item_id:
                                summary["new_item_ids"].append(item_id)
                        remember_hash(state, digest, max_items=dedup_max)
                        if preview_digest:
                            remember_hash(state, preview_digest, max_items=dedup_max)
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
                        recover_feed_state(
                            batch_index=batch_idx,
                            row_index=row_idx,
                            reason=f"exception:{exc}",
                        )
                        if (
                            "unexpected_front_process" in str(exc)
                            or "invalid_browser_url" in str(exc)
                            or "invalid_browser_url:" in str(exc)
                        ):
                            bump_route_issue_streak(
                                batch_idx=batch_idx,
                                row_idx=row_idx,
                                reason=str(exc),
                            )
                        if attempt_idx + 1 >= verify_retries:
                            summary["failed"] += 1
                            increment_batch_metric(summary, batch_idx, "failed")
                            summary["errors"].append(
                                f"batch={batch_idx + 1},row={row_idx + 1},attempt={attempt_idx + 1}: {exc}"
                            )
                            append_row_result(
                                summary,
                                batch_index=batch_idx,
                                row_index=row_idx,
                                status="failed",
                                detail=str(exc),
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

            if processed_count >= effective_max_items:
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
