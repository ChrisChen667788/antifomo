from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.services.content_extractor import normalize_text
from app.services.research.source_documents import SourceDocument
from app.services.research.web_search import SearchHit


@dataclass(frozen=True, slots=True)
class EvidenceExpansionDependencies:
    concrete_rows: Callable[[list[str]], list[str]]
    company_convergence_is_weak: Callable[..., bool]
    official_coverage_is_weak: Callable[..., bool]
    emit_research_progress: Callable[..., None]
    build_progress_message: Callable[..., str]
    build_expanded_query_plan: Callable[..., list[str]]
    collect_enabled_source_hits: Callable[..., tuple[Any, list[SearchHit]]]
    search_public_web: Callable[..., list[SearchHit]]
    hybrid_rank_hits: Callable[..., list[SearchHit]]
    select_hits_with_source_balance: Callable[..., list[SearchHit]]
    extract_source_document_best_effort: Callable[..., SourceDocument | None]
    filter_recent_sources: Callable[[list[SourceDocument]], list[SourceDocument]]
    dedupe_strings: Callable[..., list[str]]
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
class EvidenceExpansionResult:
    sources: list[SourceDocument]
    effective_query_plan: list[str]
    filtered_old_source_count: int
    region_conflict_signatures: set[str]
    scope_hints: dict[str, object]
    theme_terms: list[str]
    company_anchor_terms: list[str]
    source_intelligence: dict[str, list[str]]
    strict_topic_source_count: int
    expansion_triggered: bool


def apply_evidence_expansion(
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    research_mode: str,
    sources: list[SourceDocument],
    search_hits: list[SearchHit],
    source_intelligence: dict[str, list[str]],
    input_scope_hints: dict[str, object],
    scope_hints: dict[str, object],
    theme_terms: list[str],
    company_anchor_terms: list[str],
    effective_query_plan: list[str],
    strict_topic_source_count: int,
    filtered_old_source_count: int,
    runtime: dict[str, int | str | bool],
    include_wechat: bool,
    preferred_wechat_accounts: tuple[str, ...],
    source_excerpt_chars: int,
    progress_callback: Any | None,
    deps: EvidenceExpansionDependencies,
) -> EvidenceExpansionResult:
    region_conflict_signatures: set[str] = set()
    concrete_dimension_count = sum(
        1
        for key in (
            "target_accounts",
            "account_team_signals",
            "budget_signals",
            "ecosystem_partners",
            "competitor_profiles",
            "client_peer_moves",
            "winner_peer_moves",
            "leadership_focus",
        )
        if len(deps.concrete_rows(source_intelligence.get(key, []))) >= 3
    )
    company_convergence_weak = deps.company_convergence_is_weak(
        scope_hints=scope_hints,
        target_rows=source_intelligence.get("target_accounts", []),
        competitor_rows=source_intelligence.get("competitor_profiles", []),
    )
    should_expand = bool(runtime["enable_expansion"]) and (
        len(sources) < int(runtime["expansion_min_sources"])
        or concrete_dimension_count < int(runtime["expansion_min_dimensions"])
        or company_convergence_weak
        or deps.official_coverage_is_weak(
            sources,
            min_ratio=0.35 if bool(scope_hints.get("prefer_company_entities")) else (0.25 if research_mode == "fast" else 0.35),
            min_count=2 if bool(scope_hints.get("prefer_company_entities")) else (1 if research_mode == "fast" else 2),
        )
    )
    expansion_triggered = False
    if should_expand:
        expansion_triggered = True
        deps.emit_research_progress(
            progress_callback,
            "expanding",
            66,
            deps.build_progress_message("证据不足，正在扩大搜索范围", keyword=keyword, research_focus=research_focus, mode=research_mode),
        )
        expanded_query_plan = deps.build_expanded_query_plan(
            keyword,
            research_focus,
            scope_hints=scope_hints,
            include_wechat=include_wechat,
            preferred_wechat_accounts=preferred_wechat_accounts,
            limit=int(runtime["expanded_query_limit"]),
        )
        if expanded_query_plan:
            expanded_search_hits: list[SearchHit] = []
            expanded_seed = " ".join(
                str(item)
                for item in [
                    keyword,
                    *(scope_hints.get("regions", []) or [])[:1],
                    *(scope_hints.get("industries", []) or [])[:1],
                    *(scope_hints.get("clients", []) or [])[:1],
                ]
                if normalize_text(str(item))
            )
            _, expanded_adapter_hits = deps.collect_enabled_source_hits(
                expanded_seed or keyword,
                research_focus or normalize_text(str(scope_hints.get("anchor_text", ""))) or None,
                timeout_seconds=max(10, int(runtime["search_timeout_seconds"]) - 1),
                per_source_limit=int(runtime["expanded_adapter_per_source_limit"]),
            )
            expanded_search_hits.extend(expanded_adapter_hits)
            for query in expanded_query_plan:
                try:
                    results = deps.search_public_web(
                        query,
                        timeout_seconds=int(runtime["search_timeout_seconds"]),
                        limit=max(3, int(runtime["search_result_limit"]) - 2),
                    )
                except Exception:
                    results = []
                expanded_search_hits.extend(results)
            combined_ranked_hits = [
                hit
                for hit in deps.hybrid_rank_hits(
                    search_hits + expanded_search_hits,
                    keyword=keyword,
                    research_focus=research_focus,
                    scope_hints=scope_hints,
                )
            ]
            selected_hits = deps.select_hits_with_source_balance(
                combined_ranked_hits,
                limit=int(runtime["expanded_selected_limit"]),
            )
            expanded_sources = [
                source
                for source in (
                    deps.extract_source_document_best_effort(
                        hit,
                        timeout_seconds=int(runtime["url_timeout_seconds"]),
                        excerpt_chars=source_excerpt_chars,
                    )
                    for hit in selected_hits
                )
                if source is not None
            ]
            expanded_recent_input_count = len(expanded_sources)
            expanded_sources = deps.filter_recent_sources(expanded_sources)
            filtered_old_source_count += max(expanded_recent_input_count - len(expanded_sources), 0)
            effective_query_plan = deps.dedupe_strings(
                effective_query_plan + expanded_query_plan,
                max(int(runtime["query_limit"]), int(runtime["expanded_query_limit"])) + 4,
            )
            sources = deps.dedupe_sources([*sources, *expanded_sources])
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
            scope_hints = deps.merge_scope_hints(input_scope_hints, deps.infer_scope_hints(keyword, research_focus, sources))
            theme_terms = deps.build_theme_terms(keyword, research_focus, scope_hints)
            company_anchor_terms = deps.resolved_company_anchor_terms(keyword, research_focus, scope_hints)
            source_intelligence = deps.build_source_intelligence(
                sources,
                keyword=keyword,
                research_focus=research_focus,
                output_language=output_language,
                scope_hints=scope_hints,
            )
    return EvidenceExpansionResult(
        sources=sources,
        effective_query_plan=effective_query_plan,
        filtered_old_source_count=filtered_old_source_count,
        region_conflict_signatures=region_conflict_signatures,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        company_anchor_terms=company_anchor_terms,
        source_intelligence=source_intelligence,
        strict_topic_source_count=strict_topic_source_count,
        expansion_triggered=expansion_triggered,
    )
