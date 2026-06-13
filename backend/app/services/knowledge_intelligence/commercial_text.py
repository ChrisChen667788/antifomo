from __future__ import annotations

import re

from app.services.content_extractor import normalize_text

_COMMERCIAL_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_COMMERCIAL_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_COMMERCIAL_IMAGE_LABEL_RE = re.compile(r"^(?:image|图片)\s*\d+$", re.IGNORECASE)
_COMMERCIAL_NOISY_SUBSTRINGS = (
    "官网/公开入口",
    "优先核验公开触达入口",
    "实体归一后命中",
    "其中官方源",
    "微信扫一扫",
    "听全文",
)

def _clean_commercial_phrase(value: str, *, max_clauses: int = 1, max_length: int = 72) -> str:
    text = normalize_text(str(value or ""))
    if not text:
        return ""

    def _replace_link(match: re.Match[str]) -> str:
        label = normalize_text(match.group(1))
        if not label or _COMMERCIAL_IMAGE_LABEL_RE.match(label):
            return ""
        return label

    text = _COMMERCIAL_MARKDOWN_LINK_RE.sub(_replace_link, text)
    text = normalize_text(text).strip("，,、:：- ")
    if not text:
        return ""

    clauses: list[str] = []
    for raw_clause in re.split(r"[；;]", text):
        clause = normalize_text(raw_clause).strip("，,、:：- ")
        if not clause:
            continue
        if any(marker in clause for marker in _COMMERCIAL_NOISY_SUBSTRINGS):
            continue
        if _COMMERCIAL_URL_RE.search(clause):
            clause = _COMMERCIAL_URL_RE.sub("", clause).strip("，,、:：- ")
        if not clause:
            continue
        if "：" in clause:
            _, tail = clause.split("：", 1)
            tail = normalize_text(tail).strip("，,、:：- ")
            if len(tail) >= 8:
                clause = tail
        if _COMMERCIAL_IMAGE_LABEL_RE.match(clause):
            continue
        compact = re.sub(r"[\W_]+", "", clause, flags=re.UNICODE)
        if len(compact) < 6:
            continue
        clauses.append(clause)
        if len(clauses) >= max_clauses:
            break

    cleaned = "；".join(clauses) if clauses else text
    cleaned = _COMMERCIAL_URL_RE.sub("", cleaned).strip("，,、:：- ")
    if len(cleaned) > max_length:
        cleaned = cleaned[: max_length - 1].rstrip("，,、:：- ") + "…"
    return cleaned


def _clean_commercial_rows(values: list[str] | None, *, limit: int = 4, max_length: int = 72) -> list[str]:
    rows: list[str] = []
    for value in values or []:
        cleaned = _clean_commercial_phrase(str(value or ""), max_clauses=1, max_length=max_length)
        if cleaned and cleaned not in rows:
            rows.append(cleaned)
        if len(rows) >= limit:
            break
    return rows
