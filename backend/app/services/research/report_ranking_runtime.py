from __future__ import annotations

from app.schemas.research import ResearchEntityGraphOut, ResearchSourceDiagnosticsOut
from app.services.research.report_common import dedupe_strings
from app.services.research.source_diagnostics import SourceDiagnosticsDependencies, build_source_diagnostics
from app.services.research.source_documents import SourceDocument


def retrieval_quality_band(
    *,
    strict_match_ratio: float,
    official_source_ratio: float,
    unique_domain_count: int,
    normalized_entity_count: int,
) -> str:
    score = 0
    if strict_match_ratio >= 0.7:
        score += 2
    elif strict_match_ratio >= 0.45:
        score += 1
    if official_source_ratio >= 0.45:
        score += 2
    elif official_source_ratio >= 0.25:
        score += 1
    if unique_domain_count >= 5:
        score += 2
    elif unique_domain_count >= 3:
        score += 1
    if normalized_entity_count >= 9:
        score += 2
    elif normalized_entity_count >= 4:
        score += 1
    if score >= 6:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def evidence_mode_from_metrics(
    *,
    retained_source_count: int,
    strict_topic_source_count: int,
    strict_match_ratio: float,
    official_source_ratio: float,
    unique_domain_count: int,
) -> tuple[str, str]:
    if (
        retained_source_count >= 4
        and strict_topic_source_count >= 2
        and strict_match_ratio >= 0.45
        and official_source_ratio >= 0.25
        and unique_domain_count >= 3
    ):
        return "strong", "强证据"
    if retained_source_count > 0 and (strict_topic_source_count > 0 or unique_domain_count >= 1):
        return "provisional", "可用初版"
    return "fallback", "兜底候选"


def build_runtime_source_diagnostics(
    sources: list[SourceDocument],
    *,
    enabled_source_labels: list[str],
    scope_hints: dict[str, object],
    recency_window_years: int,
    filtered_old_source_count: int,
    filtered_region_conflict_count: int,
    retained_source_count: int,
    strict_topic_source_count: int,
    topic_anchor_terms: list[str],
    matched_theme_labels: list[str],
    entity_graph: ResearchEntityGraphOut,
    expansion_triggered: bool,
    corrective_triggered: bool,
    candidate_profile_companies: list[str],
    candidate_profile_hit_count: int,
    candidate_profile_official_hit_count: int,
    candidate_profile_source_labels: list[str],
) -> ResearchSourceDiagnosticsOut:
    return build_source_diagnostics(
        sources,
        enabled_source_labels=enabled_source_labels,
        scope_hints=scope_hints,
        recency_window_years=recency_window_years,
        filtered_old_source_count=filtered_old_source_count,
        filtered_region_conflict_count=filtered_region_conflict_count,
        retained_source_count=retained_source_count,
        strict_topic_source_count=strict_topic_source_count,
        topic_anchor_terms=topic_anchor_terms,
        matched_theme_labels=matched_theme_labels,
        entity_graph=entity_graph,
        expansion_triggered=expansion_triggered,
        corrective_triggered=corrective_triggered,
        candidate_profile_companies=candidate_profile_companies,
        candidate_profile_hit_count=candidate_profile_hit_count,
        candidate_profile_official_hit_count=candidate_profile_official_hit_count,
        candidate_profile_source_labels=candidate_profile_source_labels,
        deps=SourceDiagnosticsDependencies(
            dedupe_strings=dedupe_strings,
            retrieval_quality_band=retrieval_quality_band,
            evidence_mode_from_metrics=evidence_mode_from_metrics,
        ),
    )
