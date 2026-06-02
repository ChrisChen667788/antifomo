from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.services.content_extractor import normalize_text
from app.services.research.source_documents import SourceDocument
from app.services.research.web_search import SearchHit


@dataclass(frozen=True, slots=True)
class CorrectiveExpansionDependencies:
    company_convergence_is_weak: Callable[..., bool]
    retrieval_quality_band: Callable[..., str]
    build_retrieval_correction_profile: Callable[..., Any]
    emit_research_progress: Callable[..., None]
    build_progress_message: Callable[..., str]
    build_corrective_query_plan: Callable[..., list[str]]
    dedupe_strings: Callable[..., list[str]]
    build_company_seed_hits: Callable[..., list[SearchHit]]
    search_public_web: Callable[..., list[SearchHit]]
    hybrid_rank_hits: Callable[..., list[SearchHit]]
    select_hits_with_source_balance: Callable[..., list[SearchHit]]
    dedupe_hits: Callable[[list[SearchHit]], list[SearchHit]]
    extract_source_document_best_effort: Callable[..., SourceDocument | None]
    filter_recent_sources: Callable[[list[SourceDocument]], list[SourceDocument]]
    dedupe_sources: Callable[[list[SourceDocument]], list[SourceDocument]]
    region_conflict_signature: Callable[[SourceDocument], str]
    source_has_region_conflict: Callable[..., bool]
    refine_sources_for_report: Callable[..., list[SourceDocument]]
    merge_scope_hints: Callable[[dict[str, object], dict[str, object]], dict[str, object]]
    infer_scope_hints: Callable[[str, str | None, list[SourceDocument]], dict[str, object]]
    build_theme_terms: Callable[[str, str | None, dict[str, object]], list[str]]
    resolved_company_anchor_terms: Callable[[str, str | None, dict[str, object]], list[str]]
    build_source_intelligence: Callable[..., dict[str, list[str]]]


@dataclass(frozen=True, slots=True)
class CorrectiveExpansionResult:
    sources: list[SourceDocument]
    effective_query_plan: list[str]
    filtered_old_source_count: int
    region_conflict_signatures: set[str]
    scope_hints: dict[str, object]
    theme_terms: list[str]
    company_anchor_terms: list[str]
    source_intelligence: dict[str, list[str]]
    corrective_triggered: bool
    retrieval_correction_profile: Any


def apply_corrective_expansion(
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    research_mode: str,
    sources: list[SourceDocument],
    source_intelligence: dict[str, list[str]],
    input_scope_hints: dict[str, object],
    scope_hints: dict[str, object],
    theme_terms: list[str],
    company_anchor_terms: list[str],
    theme_seed_companies: list[str],
    effective_query_plan: list[str],
    strict_topic_source_count: int,
    filtered_old_source_count: int,
    runtime: dict[str, int | str | bool],
    include_wechat: bool,
    preferred_wechat_accounts: tuple[str, ...],
    source_excerpt_chars: int,
    max_sources: int,
    progress_callback: Any | None,
    deps: CorrectiveExpansionDependencies,
) -> CorrectiveExpansionResult:
    company_convergence_weak = deps.company_convergence_is_weak(
        scope_hints=scope_hints,
        target_rows=source_intelligence.get("target_accounts", []),
        competitor_rows=source_intelligence.get("competitor_profiles", []),
    )
    provisional_unique_domain_count = len({source.domain for source in sources if normalize_text(source.domain or "")})
    provisional_official_ratio = (
        sum(1 for source in sources if source.source_tier == "official") / len(sources)
        if sources
        else 0.0
    )
    provisional_retrieval_quality = deps.retrieval_quality_band(
        strict_match_ratio=(strict_topic_source_count / len(sources)) if sources else 0.0,
        official_source_ratio=provisional_official_ratio,
        unique_domain_count=provisional_unique_domain_count,
        normalized_entity_count=0,
    )
    retrieval_correction_profile = deps.build_retrieval_correction_profile(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
        query_plan=effective_query_plan,
        corrective_query_limit=int(runtime.get("corrective_query_limit", 6)),
    )
    should_expand = (
        len(sources) == 0
        or strict_topic_source_count == 0
        or company_convergence_weak
        or provisional_retrieval_quality == "low"
        or retrieval_correction_profile.status == "needs_expansion"
    )
    region_conflict_signatures: set[str] = set()
    corrective_triggered = False
    if should_expand:
        corrective_triggered = True
        deps.emit_research_progress(
            progress_callback,
            "corrective",
            74,
            deps.build_progress_message("证据仍偏弱，正在执行纠错检索", keyword=keyword, research_focus=research_focus, mode=research_mode),
        )
        corrective_query_plan = deps.build_corrective_query_plan(
            keyword=keyword,
            research_focus=research_focus,
            scope_hints=scope_hints,
            include_wechat=include_wechat,
            preferred_wechat_accounts=preferred_wechat_accounts,
            limit=int(runtime.get("corrective_query_limit", 6)),
        )
        corrective_query_plan = deps.dedupe_strings(
            [*retrieval_correction_profile.corrective_queries, *corrective_query_plan],
            max(4, min(int(runtime.get("corrective_query_limit", 6)) + 2, 12)),
        )
        corrective_hits: list[SearchHit] = deps.build_company_seed_hits(theme_seed_companies, keyword=keyword)
        for query in corrective_query_plan:
            try:
                results = deps.search_public_web(
                    query,
                    timeout_seconds=max(10, int(runtime["search_timeout_seconds"])),
                    limit=max(4, int(runtime["search_result_limit"])),
                )
            except Exception:
                results = []
            corrective_hits.extend(results)
        ranked_corrective_hits = [
            hit
            for hit in deps.hybrid_rank_hits(
                corrective_hits,
                keyword=keyword,
                research_focus=research_focus,
                scope_hints=scope_hints,
            )
        ]
        selected_corrective_hits = deps.select_hits_with_source_balance(
            ranked_corrective_hits,
            limit=max(4, min(int(runtime["expanded_selected_limit"]), max_sources)),
        )
        if not selected_corrective_hits and corrective_hits:
            selected_corrective_hits = deps.dedupe_hits(corrective_hits)[:3]
        corrective_sources = [
            source
            for source in (
                deps.extract_source_document_best_effort(
                    hit,
                    timeout_seconds=int(runtime["url_timeout_seconds"]),
                    excerpt_chars=source_excerpt_chars,
                )
                for hit in selected_corrective_hits
            )
            if source is not None
        ]
        corrective_recent_input_count = len(corrective_sources)
        corrective_sources = deps.filter_recent_sources(corrective_sources)
        filtered_old_source_count += max(corrective_recent_input_count - len(corrective_sources), 0)
        if corrective_sources:
            effective_query_plan = deps.dedupe_strings(
                effective_query_plan + corrective_query_plan,
                max(int(runtime["query_limit"]), int(runtime["expanded_query_limit"])) + 8,
            )
            sources = deps.dedupe_sources([*sources, *corrective_sources])
            region_conflict_signatures.update(
                deps.region_conflict_signature(source)
                for source in sources
                if deps.source_has_region_conflict(source, scope_hints=scope_hints)
            )
            sources = deps.refine_sources_for_report(
                sources,
                keyword=keyword,
                research_focus=research_focus,
                scope_hints=scope_hints,
                company_anchor_terms=company_anchor_terms,
                theme_terms=theme_terms,
            )
            scope_hints = deps.merge_scope_hints(input_scope_hints, deps.infer_scope_hints(keyword, research_focus, sources))
            theme_terms = deps.build_theme_terms(keyword, research_focus, scope_hints)
            company_anchor_terms = deps.resolved_company_anchor_terms(keyword, research_focus, scope_hints)
            sources = deps.refine_sources_for_report(
                sources,
                keyword=keyword,
                research_focus=research_focus,
                scope_hints=scope_hints,
                company_anchor_terms=company_anchor_terms,
                theme_terms=theme_terms,
            )
            strict_topic_source_count = len(sources)
            source_intelligence = deps.build_source_intelligence(
                sources,
                keyword=keyword,
                research_focus=research_focus,
                output_language=output_language,
                scope_hints=scope_hints,
            )
    retrieval_correction_profile = deps.build_retrieval_correction_profile(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
        query_plan=effective_query_plan,
        corrective_query_limit=int(runtime.get("corrective_query_limit", 6)),
    )
    return CorrectiveExpansionResult(
        sources=sources,
        effective_query_plan=effective_query_plan,
        filtered_old_source_count=filtered_old_source_count,
        region_conflict_signatures=region_conflict_signatures,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        company_anchor_terms=company_anchor_terms,
        source_intelligence=source_intelligence,
        corrective_triggered=corrective_triggered,
        retrieval_correction_profile=retrieval_correction_profile,
    )
