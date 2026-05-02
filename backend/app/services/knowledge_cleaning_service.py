from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Iterable

from app.services.content_extractor import normalize_text


_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_IMAGE_LABEL_RE = re.compile(r"^(?:image|图片|图)\s*\d+$", re.IGNORECASE)
_LOW_SIGNAL_EXACT = {
    "",
    "-",
    "--",
    "—",
    "n/a",
    "na",
    "none",
    "null",
    "todo",
    "tbd",
    "placeholder",
    "lorem ipsum",
    "暂无摘要",
    "暂无长摘要",
    "暂无可归档内容",
    "暂无可写入知识库的内容摘要",
    "待补充",
    "待确认",
    "无",
    "无数据",
    "未设置",
    "测试",
    "示例",
}
_LOW_SIGNAL_CONTAINS = (
    "作为一个ai",
    "作为ai",
    "我是一个ai",
    "无法访问外部链接",
    "不能提供思维链",
    "思维链",
    "推理过程",
    "以下是我的分析过程",
    "下面是处理过程",
    "我会先",
    "我将先",
    "正在分析",
    "正在整理",
    "取数 -> 清洗 -> 分析",
    "当前证据不足，建议补充更多来源后再形成正式判断",
    "解析失败，使用默认推荐",
    "微信扫一扫",
    "听全文",
    "继续滑动看下一个",
)
_PLACEHOLDER_TITLE_PREFIXES = (
    "wechat auto",
    "wechat ocr",
    "untitled",
    "未命名",
    "主题待确认",
    "内容摘要待生成",
    "内容主题待确认",
)
_LOW_SIGNAL_EXACT_COMPACT = {re.sub(r"[\W_]+", "", item.lower(), flags=re.UNICODE) for item in _LOW_SIGNAL_EXACT}


def _compact_for_compare(value: str) -> str:
    return re.sub(r"[\W_]+", "", normalize_text(value).lower(), flags=re.UNICODE)


def _looks_like_low_signal_line(value: str) -> bool:
    text = normalize_text(value).strip("，,、:：- ")
    if not text:
        return True
    lowered = text.lower()
    compact = _compact_for_compare(text)
    if lowered in _LOW_SIGNAL_EXACT or compact in _LOW_SIGNAL_EXACT_COMPACT:
        return True
    if _IMAGE_LABEL_RE.match(text):
        return True
    if any(token in lowered for token in _LOW_SIGNAL_CONTAINS):
        return True
    if _URL_RE.fullmatch(text):
        return True
    if len(compact) <= 3 and not re.search(r"\d", compact):
        return True
    if len(text) >= 12 and len(set(compact)) <= 2:
        return True
    return False


def _split_content_rows(content: str) -> list[str]:
    normalized = normalize_text(content)
    if not normalized:
        return []
    rows: list[str] = []
    for row in re.split(r"(?:\n+|(?<=。)\s+|(?<=；)\s+|(?<=;)\s+)", content):
        cleaned = normalize_text(row).strip("，,、:：- ")
        if cleaned:
            rows.append(cleaned)
    if len(rows) <= 1 and len(normalized) > 240:
        rows = [
            normalize_text(row).strip("，,、:：- ")
            for row in re.split(r"[。！？!?]\s*", normalized)
            if normalize_text(row).strip("，,、:：- ")
        ]
    return rows or [normalized]


def dedupe_meaningful_rows(values: Iterable[str], *, limit: int | None = None) -> list[str]:
    rows: list[str] = []
    compact_rows: list[str] = []
    for value in values:
        cleaned = normalize_text(str(value or "")).strip("，,、:：- ")
        if _looks_like_low_signal_line(cleaned):
            continue
        compact = _compact_for_compare(cleaned)
        if not compact:
            continue
        duplicate = compact in compact_rows
        if not duplicate:
            duplicate = any(
                SequenceMatcher(None, compact, existing).ratio() >= 0.92
                for existing in compact_rows
                if min(len(compact), len(existing)) >= 18
            )
        if duplicate:
            continue
        rows.append(cleaned)
        compact_rows.append(compact)
        if limit is not None and len(rows) >= limit:
            break
    return rows


def clean_knowledge_content(content: str | None, *, max_rows: int | None = None) -> str:
    rows = dedupe_meaningful_rows(_split_content_rows(content or ""), limit=max_rows)
    if not rows:
        return ""
    return "\n".join(rows)


def clean_knowledge_title(title: str | None, *, fallback: str = "知识卡片") -> str:
    text = normalize_text(title or "").strip("，,、:：- ")
    lowered = text.lower()
    if not text or lowered in _LOW_SIGNAL_EXACT or any(lowered.startswith(prefix) for prefix in _PLACEHOLDER_TITLE_PREFIXES):
        return fallback
    if _looks_like_low_signal_line(text):
        return fallback
    text = _URL_RE.sub("", text).strip("，,、:：- ")
    return (text or fallback)[:120]


def is_low_signal_knowledge_payload(title: str | None, content: str | None) -> bool:
    cleaned_content = clean_knowledge_content(content)
    cleaned_title = clean_knowledge_title(title, fallback="")
    if not cleaned_content and not cleaned_title:
        return True
    compact_content = _compact_for_compare(cleaned_content)
    if len(compact_content) < 12 and not cleaned_title:
        return True
    if len(compact_content) < 8 and clean_knowledge_title(title, fallback="") in {"知识卡片", ""}:
        return True
    return False
