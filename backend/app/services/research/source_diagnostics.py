from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from app.schemas.research import ResearchEntityGraphOut, ResearchSourceDiagnosticsOut
from app.services.content_extractor import normalize_text
from app.services.research.source_documents import SourceDocument


@dataclass(frozen=True, slots=True)
class SourceDiagnosticsDependencies:
    dedupe_strings: Callable[..., list[str]]
    retrieval_quality_band: Callable[..., str]
    evidence_mode_from_metrics: Callable[..., tuple[str, str]]


def build_source_diagnostics(
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
    deps: SourceDiagnosticsDependencies,
) -> ResearchSourceDiagnosticsOut:
    source_type_counts: Counter[str] = Counter()
    source_tier_counts: Counter[str] = Counter()
    source_label_counts: Counter[str] = Counter()
    adapter_hit_count = 0
    for source in sources:
        source_type_counts[source.source_type] += 1
        source_tier_counts[source.source_tier or "media"] += 1
        if source.source_label:
            source_label_counts[source.source_label] += 1
        if source.source_origin == "adapter":
            adapter_hit_count += 1
    matched_source_labels = [label for label, _ in source_label_counts.most_common()]
    unique_domains = len({source.domain for source in sources if normalize_text(source.domain or "")})
    official_count = int(source_tier_counts.get("official", 0))
    strict_match_ratio = (strict_topic_source_count / retained_source_count) if retained_source_count else 0.0
    official_source_ratio = (official_count / retained_source_count) if retained_source_count else 0.0
    retrieval_quality = deps.retrieval_quality_band(
        strict_match_ratio=strict_match_ratio,
        official_source_ratio=official_source_ratio,
        unique_domain_count=unique_domains,
        normalized_entity_count=len(entity_graph.entities),
    )
    evidence_mode, evidence_mode_label = deps.evidence_mode_from_metrics(
        retained_source_count=retained_source_count,
        strict_topic_source_count=strict_topic_source_count,
        strict_match_ratio=strict_match_ratio,
        official_source_ratio=official_source_ratio,
        unique_domain_count=unique_domains,
    )
    fetch_count = max(adapter_hit_count + max(len(sources) - adapter_hit_count, 0), 0)
    clean_removed_count = max(filtered_old_source_count, 0) + max(filtered_region_conflict_count, 0)
    pipeline_stages = [
        {
            "key": "fetch",
            "label": "取数",
            "value": fetch_count,
            "summary": f"汇总 {fetch_count} 条候选来源，覆盖 {max(len(enabled_source_labels), len(matched_source_labels) or 0)} 类输入通道。",
        },
        {
            "key": "clean",
            "label": "清洗",
            "value": max(retained_source_count, 0),
            "summary": f"保留 {max(retained_source_count, 0)} 条可用来源，剔除 {clean_removed_count} 条过旧或越界结果。",
        },
        {
            "key": "analyze",
            "label": "分析",
            "value": len(entity_graph.entities),
            "summary": f"归一 {len(entity_graph.entities)} 个实体，官方源占比 {round(official_source_ratio * 100)}%。",
        },
    ]
    pipeline_summary = " -> ".join(str(stage["summary"]) for stage in pipeline_stages)
    return ResearchSourceDiagnosticsOut(
        enabled_source_labels=list(dict.fromkeys(enabled_source_labels)),
        matched_source_labels=matched_source_labels,
        scope_regions=deps.dedupe_strings(scope_hints.get("regions", []) or [], 3),
        scope_industries=deps.dedupe_strings(scope_hints.get("industries", []) or [], 3),
        scope_clients=deps.dedupe_strings(scope_hints.get("clients", []) or [], 3),
        source_type_counts=dict(source_type_counts),
        source_tier_counts=dict(source_tier_counts),
        adapter_hit_count=adapter_hit_count,
        search_hit_count=max(len(sources) - adapter_hit_count, 0),
        recency_window_years=recency_window_years,
        filtered_old_source_count=max(filtered_old_source_count, 0),
        filtered_region_conflict_count=max(filtered_region_conflict_count, 0),
        retained_source_count=max(retained_source_count, 0),
        strict_topic_source_count=max(strict_topic_source_count, 0),
        topic_anchor_terms=list(dict.fromkeys(item for item in topic_anchor_terms if normalize_text(item)))[:8],
        matched_theme_labels=list(dict.fromkeys(item for item in matched_theme_labels if normalize_text(item)))[:8],
        retrieval_quality=retrieval_quality if retrieval_quality in {"low", "medium", "high"} else "low",
        evidence_mode=evidence_mode if evidence_mode in {"strong", "provisional", "fallback"} else "fallback",
        evidence_mode_label=evidence_mode_label,
        strict_match_ratio=round(strict_match_ratio, 3),
        official_source_ratio=round(official_source_ratio, 3),
        unique_domain_count=unique_domains,
        normalized_entity_count=len(entity_graph.entities),
        normalized_target_count=len(entity_graph.target_entities),
        normalized_competitor_count=len(entity_graph.competitor_entities),
        normalized_partner_count=len(entity_graph.partner_entities),
        expansion_triggered=expansion_triggered,
        corrective_triggered=corrective_triggered,
        candidate_profile_companies=deps.dedupe_strings(candidate_profile_companies, 6),
        candidate_profile_hit_count=max(candidate_profile_hit_count, 0),
        candidate_profile_official_hit_count=max(candidate_profile_official_hit_count, 0),
        candidate_profile_source_labels=deps.dedupe_strings(candidate_profile_source_labels, 8),
        strategy_model_used=bool(scope_hints.get("strategy_scope_summary") or scope_hints.get("strategy_query_expansions")),
        strategy_scope_summary=normalize_text(str(scope_hints.get("strategy_scope_summary", ""))),
        strategy_query_expansion_count=len(scope_hints.get("strategy_query_expansions", []) or []),
        strategy_exclusion_terms=deps.dedupe_strings(scope_hints.get("strategy_exclusion_terms", []) or [], 8),
        runtime_strategy_status=normalize_text(str(scope_hints.get("runtime_strategy_status") or "")),
        runtime_strategy_applied_lanes=deps.dedupe_strings(scope_hints.get("runtime_strategy_applied_lanes", []) or [], 8),
        runtime_strategy_fallback_lanes=deps.dedupe_strings(scope_hints.get("runtime_strategy_fallback_lanes", []) or [], 8),
        runtime_strategy_warnings=deps.dedupe_strings(scope_hints.get("runtime_strategy_warnings", []) or [], 8),
        runtime_query_recovery_enabled=bool(scope_hints.get("runtime_query_recovery_enabled")),
        runtime_source_reranker_enabled=bool(scope_hints.get("runtime_source_reranker_enabled")),
        reranker_used=bool(scope_hints.get("reranker_used")),
        reranker_model=normalize_text(str(scope_hints.get("reranker_model") or "")),
        reranker_top_k=int(scope_hints.get("reranker_top_k") or 0),
        reranker_backend=normalize_text(str(scope_hints.get("reranker_backend") or "")),
        reranker_notes=deps.dedupe_strings(scope_hints.get("reranker_notes", []) or [], 4),
        pipeline_summary=pipeline_summary,
        pipeline_stages=pipeline_stages,
    )
