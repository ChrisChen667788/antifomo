from __future__ import annotations

from collections.abc import Iterable
import re

from app.services.content_extractor import normalize_text
from app.services.research.entity_policy import INDUSTRY_SCOPE_ALIASES, THEME_GENERIC_SUPPRESSIONS
from app.services.research.report_common import dedupe_strings
from app.services.research.source_documents import SourceDocument


def prune_industry_hints(values: Iterable[str]) -> list[str]:
    hints = dedupe_strings((normalize_text(value) for value in values), 4)
    if not hints:
        return []
    pruned = list(hints)
    for dominant, suppressed in THEME_GENERIC_SUPPRESSIONS.items():
        if dominant in pruned:
            pruned = [item for item in pruned if item == dominant or item not in suppressed]
    generic_hints = {"大模型", "人工智能", "信息化"}
    specific_hints = [item for item in pruned if item not in generic_hints]
    if specific_hints:
        pruned = specific_hints
    pruned = [
        item
        for item in pruned
        if not any(
            item != other
            and len(other) > len(item)
            and item.casefold() in other.casefold()
            for other in pruned
        )
    ]
    return dedupe_strings(pruned, 4)


def collect_matched_theme_labels(
    sources: list[SourceDocument],
    *,
    scope_hints: dict[str, object],
    topic_anchor_terms: list[str],
) -> list[str]:
    if not sources:
        return topic_anchor_terms[:4]
    haystack = normalize_text(
        " ".join(
            " ".join(
                [
                    source.title,
                    source.snippet,
                    source.excerpt,
                    source.search_query,
                    source.source_label or "",
                    source.domain or "",
                ]
            )
            for source in sources
        )
    ).lower()
    candidates: list[str] = []
    scope_values = [
        *(scope_hints.get("industries", []) or []),
        *(scope_hints.get("clients", []) or []),
        *(scope_hints.get("regions", []) or []),
    ]
    for label in scope_values:
        normalized = normalize_text(str(label))
        if not normalized:
            continue
        aliases = [normalized, *INDUSTRY_SCOPE_ALIASES.get(normalized, ())]
        if any(normalize_text(alias).lower() in haystack for alias in aliases if normalize_text(alias)):
            candidates.append(normalized)
    if not candidates:
        candidates.extend(topic_anchor_terms[:4])
    return list(dict.fromkeys(item for item in candidates if normalize_text(item)))


def scope_anchor_text_segments(value: str | None) -> list[str]:
    normalized = normalize_text(value or "")
    if not normalized:
        return []
    return [
        normalize_text(part)
        for part in re.split(r"[|｜/／]+", normalized)
        if normalize_text(part)
    ]
