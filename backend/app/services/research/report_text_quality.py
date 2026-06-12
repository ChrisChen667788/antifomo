from __future__ import annotations

from collections.abc import Callable, Collection
from dataclasses import dataclass

from app.services.content_extractor import normalize_text


@dataclass(frozen=True, slots=True)
class ReportTextQualityDependencies:
    summary_contains_output_noise: Callable[[str], bool]
    bad_executive_summary_phrases: Collection[str]


def looks_like_bad_executive_summary(
    value: str,
    *,
    deps: ReportTextQualityDependencies,
) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return True
    if len(normalized) < 36:
        return True
    if deps.summary_contains_output_noise(normalized):
        return True
    if any(token in normalized for token in deps.bad_executive_summary_phrases):
        return True
    if normalized.count("：") > 3 or normalized.count(":") > 3:
        return True
    if normalized.startswith(("本次", "当前", "建议", "研究", "报告")) and len(normalized) > 80:
        return True
    if len(normalized) > 220 and "。" not in normalized and "." not in normalized:
        return True
    return False
