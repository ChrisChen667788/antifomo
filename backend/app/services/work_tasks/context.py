from __future__ import annotations

import re
from typing import Any

_WECHAT_AUTO_PREFIX_RE = re.compile(r"^(?:主题[:：]\s*)?(?:wechat\s*(?:auto|ocr)|截图ocr)\b.*$", re.IGNORECASE)
_WECHAT_AUTO_LABEL_RE = re.compile(r"^(?:主题[:：]\s*)?(?:wechat\s*(?:auto|ocr)|截图ocr)\b[\s\S]*?[：:]\s*", re.IGNORECASE)
_CONTEXT_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_CONTEXT_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_CONTEXT_DOMAIN_RE = re.compile(r"\b[a-z0-9.-]+\.(?:gov|com|cn|net|org)(?:\.[a-z]{2})?\b", re.IGNORECASE)
_CONTEXT_IMAGE_LABEL_RE = re.compile(r"^(?:image|图片)\s*\d+$", re.IGNORECASE)
_BRIEFING_LOW_QUALITY_PATTERNS = (
    "主体账号 行业账号",
    "省级账号 地市级账号",
    "扫码关注我们",
    "当前运行在本地 OCR 模拟模式",
    "ocr screenshot content",
    "首页 >>",
)
_BRIEFING_META_MARKERS = ("原创", "听全文", "微信扫一扫", "微信搜索", "公众号", "作者", "发布于")
_BRIEFING_DATE_RE = re.compile(r"20\d{2}年\d{1,2}月\d{1,2}日")
_BRIEFING_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")


def _normalize_briefing_text(value: str | None) -> str:
    return " ".join(str(value or "").split()).strip()


def _looks_like_briefing_meta_heavy(value: str | None) -> bool:
    normalized = _normalize_briefing_text(value)
    if not normalized:
        return True
    prefix = normalized[:96]
    marker_hits = sum(1 for marker in _BRIEFING_META_MARKERS if marker in prefix)
    date_hit = bool(_BRIEFING_DATE_RE.search(prefix))
    time_hit = bool(_BRIEFING_TIME_RE.search(prefix))
    return marker_hits >= 2 or (date_hit and time_hit and marker_hits >= 1)


def _context_text(value: Any, *, preserve_labels: bool = False) -> str:
    raw = _normalize_briefing_text(str(value or ""))
    if not raw:
        return ""

    def _replace_markdown_link(match: re.Match[str]) -> str:
        label = _normalize_briefing_text(match.group(1))
        if not label or _CONTEXT_IMAGE_LABEL_RE.match(label):
            return ""
        return label

    text = _CONTEXT_MARKDOWN_LINK_RE.sub(_replace_markdown_link, raw)
    text = text.replace("](", " ")
    strip_chars = "，,、- " if preserve_labels else "，,、:：- "
    text = _normalize_briefing_text(text).strip(strip_chars)
    if not text:
        return ""
    candidate_clauses: list[str] = []
    for raw_clause in re.split(r"[；;]", text):
        clause = _normalize_briefing_text(raw_clause).strip("，,、:：- ")
        if not clause:
            continue
        if any(marker in clause for marker in ("官网/公开入口", "优先核验公开触达入口", "实体归一后命中")):
            continue
        candidate_clauses.append(clause)
    if candidate_clauses:
        text = candidate_clauses[0]
    elif any(marker in text for marker in ("官网/公开入口", "优先核验公开触达入口", "实体归一后命中")):
        return ""
    lower = text.lower()
    if any(pattern in text for pattern in _BRIEFING_LOW_QUALITY_PATTERNS):
        return ""
    if "wechat auto" in lower or "微信扫一扫" in text or "听全文" in text:
        return ""
    if _CONTEXT_IMAGE_LABEL_RE.match(text):
        return ""
    if _looks_like_briefing_meta_heavy(text):
        return ""
    if not preserve_labels:
        for _ in range(2):
            if "：" not in text:
                break
            head, tail = text.split("：", 1)
            head = _normalize_briefing_text(head)
            tail = _normalize_briefing_text(tail).strip("，,、:：- ")
            if tail and (head.startswith("短期") or head.startswith("中期") or head.startswith("长期") or len(head) <= 8):
                text = tail
                continue
            break

    meaningful = _CONTEXT_URL_RE.sub("", text)
    meaningful = _CONTEXT_DOMAIN_RE.sub("", meaningful)
    meaningful = re.sub(r"[\W_]+", "", meaningful, flags=re.UNICODE)
    if len(meaningful) < 6 and (_CONTEXT_URL_RE.search(text) or _CONTEXT_DOMAIN_RE.search(text)):
        return ""
    text = _CONTEXT_DOMAIN_RE.sub("", text).strip(strip_chars)
    text = _normalize_briefing_text(text)
    if not text:
        return ""
    return text[:240]


def _context_list(values: Any, *, limit: int = 4) -> list[str]:
    rows: list[str] = []
    for value in values if isinstance(values, list) else []:
        text = _context_text(value)
        if text and text not in rows:
            rows.append(text)
    return rows[:limit]


def _context_dict_rows(values: Any, *, limit: int = 4) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value in values if isinstance(values, list) else []:
        if not isinstance(value, dict):
            continue
        has_meaningful = False
        for field_value in value.values():
            if isinstance(field_value, str) and _context_text(field_value):
                has_meaningful = True
                break
            if isinstance(field_value, (int, float)) and field_value:
                has_meaningful = True
                break
        if not has_meaningful:
            continue
        rows.append(value)
    return rows[:limit]


def _sanitize_task_context_value(value: Any) -> Any:
    if isinstance(value, str):
        return _context_text(value)
    if isinstance(value, list):
        rows = []
        for item in value:
            sanitized = _sanitize_task_context_value(item)
            if sanitized in ("", None, [], {}):
                continue
            rows.append(sanitized)
        return rows
    if isinstance(value, dict):
        payload: dict[str, Any] = {}
        for key, item in value.items():
            sanitized = _sanitize_task_context_value(item)
            if sanitized in ("", None, [], {}):
                continue
            payload[str(key)] = sanitized
        return payload
    return value


def sanitize_task_context_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return payload
    sanitized = _sanitize_task_context_value(payload)
    return sanitized if isinstance(sanitized, dict) else {}

