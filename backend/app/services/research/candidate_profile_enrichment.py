from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.schemas.research import ResearchEntityGraphOut
from app.services.content_extractor import normalize_text
from app.services.llm_parser import ResearchReportResult
from app.services.research.entity_ranking import ResearchEntityRankingSets, rank_report_entities
from app.services.research.source_documents import SourceDocument
from app.services.research.web_search import SearchHit


_INVALID_PROFILE_TITLES = {
    "404",
    "403",
    "not found",
    "page not found",
    "页面不存在",
    "访问被拒绝",
}


def _is_valid_profile_source(source: SourceDocument) -> bool:
    title = normalize_text(source.title).casefold().strip(" -_|:：")
    return bool(
        normalize_text(source.url)
        and title not in _INVALID_PROFILE_TITLES
        and source.content_status not in {"failed", "error", "empty"}
    )


def _topical_profile_sources(
    sources: list[SourceDocument],
    *,
    seed_profile_urls: set[str],
) -> list[SourceDocument]:
    return [
        source
        for source in sources
        if _is_valid_profile_source(source)
        and normalize_text(source.url) not in seed_profile_urls
    ]


def _candidate_profile_enrichment_requested(input_scope_hints: dict[str, object]) -> bool:
    return bool(
        input_scope_hints.get("prefer_company_entities")
        or input_scope_hints.get("company_anchors")
        or input_scope_hints.get("clients")
    )


@dataclass(frozen=True, slots=True)
class CandidateProfileEnrichmentDependencies:
    dedupe_strings: Callable[..., list[str]]
    build_company_profile_query_plan: Callable[..., list[str]]
    build_company_contact_query_plan: Callable[..., list[str]]
    build_company_team_query_plan: Callable[..., list[str]]
    emit_research_progress: Callable[..., None]
    build_progress_message: Callable[..., str]
    build_company_seed_hits: Callable[..., list[SearchHit]]
    search_public_web: Callable[..., list[SearchHit]]
    hybrid_rank_hits: Callable[..., list[SearchHit]]
    select_hits_with_source_balance: Callable[..., list[SearchHit]]
    dedupe_hits: Callable[[list[SearchHit]], list[SearchHit]]
    extract_source_document_best_effort: Callable[..., SourceDocument | None]
    dedupe_sources: Callable[[list[SourceDocument]], list[SourceDocument]]
    region_conflict_signature: Callable[[SourceDocument], str]
    source_has_region_conflict: Callable[..., bool]
    refine_sources_for_report: Callable[..., list[SourceDocument]]
    merge_scope_hints: Callable[[dict[str, object], dict[str, object]], dict[str, object]]
    infer_scope_hints: Callable[[str, str | None, list[SourceDocument]], dict[str, object]]
    build_theme_terms: Callable[[str, str | None, dict[str, object]], list[str]]
    resolved_company_anchor_terms: Callable[[str, str | None, dict[str, object]], list[str]]
    build_entity_graph: Callable[..., ResearchEntityGraphOut]
    rank_top_entities: Callable[..., Any]
    filtered_rank_fallback_values: Callable[..., list[str]]


@dataclass(frozen=True, slots=True)
class CandidateProfileEnrichmentResult:
    sources: list[SourceDocument]
    rankings: ResearchEntityRankingSets
    scope_hints: dict[str, object]
    theme_terms: list[str]
    company_anchor_terms: list[str]
    entity_graph: ResearchEntityGraphOut
    corrective_triggered: bool
    candidate_profile_sources: list[SourceDocument]
    candidate_profile_companies: list[str]
    candidate_profile_hit_count: int
    candidate_profile_official_hit_count: int
    candidate_profile_source_labels: list[str]
    region_conflict_signatures: set[str]


def enrich_candidate_profiles(
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    research_mode: str,
    parsed: ResearchReportResult,
    sources: list[SourceDocument],
    rankings: ResearchEntityRankingSets,
    input_scope_hints: dict[str, object],
    scope_hints: dict[str, object],
    theme_terms: list[str],
    company_anchor_terms: list[str],
    entity_graph: ResearchEntityGraphOut,
    runtime: dict[str, int | str | bool],
    source_excerpt_chars: int,
    corrective_triggered: bool,
    progress_callback: Any | None,
    deps: CandidateProfileEnrichmentDependencies,
) -> CandidateProfileEnrichmentResult:
    candidate_profile_sources: list[SourceDocument] = []
    candidate_profile_companies: list[str] = []
    candidate_profile_hit_count = 0
    candidate_profile_official_hit_count = 0
    candidate_profile_source_labels: list[str] = []
    region_conflict_signatures: set[str] = set()

    if not _candidate_profile_enrichment_requested(input_scope_hints):
        return CandidateProfileEnrichmentResult(
            sources=sources,
            rankings=rankings,
            scope_hints=scope_hints,
            theme_terms=theme_terms,
            company_anchor_terms=company_anchor_terms,
            entity_graph=entity_graph,
            corrective_triggered=corrective_triggered,
            candidate_profile_sources=candidate_profile_sources,
            candidate_profile_companies=candidate_profile_companies,
            candidate_profile_hit_count=candidate_profile_hit_count,
            candidate_profile_official_hit_count=candidate_profile_official_hit_count,
            candidate_profile_source_labels=candidate_profile_source_labels,
            region_conflict_signatures=region_conflict_signatures,
        )

    candidate_public_profile_names = rankings.candidate_public_profile_names
    if not candidate_public_profile_names:
        return CandidateProfileEnrichmentResult(
            sources=sources,
            rankings=rankings,
            scope_hints=scope_hints,
            theme_terms=theme_terms,
            company_anchor_terms=company_anchor_terms,
            entity_graph=entity_graph,
            corrective_triggered=corrective_triggered,
            candidate_profile_sources=candidate_profile_sources,
            candidate_profile_companies=candidate_profile_companies,
            candidate_profile_hit_count=candidate_profile_hit_count,
            candidate_profile_official_hit_count=candidate_profile_official_hit_count,
            candidate_profile_source_labels=candidate_profile_source_labels,
            region_conflict_signatures=region_conflict_signatures,
        )

    candidate_profile_companies = deps.dedupe_strings(candidate_public_profile_names, 6)
    public_profile_queries = deps.dedupe_strings(
        [
            *deps.build_company_profile_query_plan(
                candidate_public_profile_names,
                keyword=keyword,
                research_focus=research_focus,
                limit=4 if research_mode == "fast" else 6,
            ),
            *deps.build_company_contact_query_plan(
                candidate_public_profile_names,
                keyword=keyword,
                research_focus=research_focus,
                limit=4 if research_mode == "fast" else 6,
            ),
            *deps.build_company_team_query_plan(
                candidate_public_profile_names,
                keyword=keyword,
                research_focus=research_focus,
                scope_hints=scope_hints,
                limit=4 if research_mode == "fast" else 6,
            ),
        ],
        8 if research_mode == "fast" else 12,
    )
    if not public_profile_queries:
        return CandidateProfileEnrichmentResult(
            sources=sources,
            rankings=rankings,
            scope_hints=scope_hints,
            theme_terms=theme_terms,
            company_anchor_terms=company_anchor_terms,
            entity_graph=entity_graph,
            corrective_triggered=corrective_triggered,
            candidate_profile_sources=candidate_profile_sources,
            candidate_profile_companies=candidate_profile_companies,
            candidate_profile_hit_count=candidate_profile_hit_count,
            candidate_profile_official_hit_count=candidate_profile_official_hit_count,
            candidate_profile_source_labels=candidate_profile_source_labels,
            region_conflict_signatures=region_conflict_signatures,
        )

    deps.emit_research_progress(
        progress_callback,
        "candidate_profiles",
        94,
        deps.build_progress_message("正在补充候选公司官网、联系页与团队公开线索", keyword=keyword, research_focus=research_focus, mode=research_mode),
    )
    public_profile_hits: list[SearchHit] = []
    seed_profile_hits = deps.build_company_seed_hits(candidate_public_profile_names, keyword=keyword)
    seed_profile_urls = {
        normalize_text(hit.url)
        for hit in seed_profile_hits
        if normalize_text(hit.url)
    }
    public_profile_hits.extend(seed_profile_hits)
    for query in public_profile_queries:
        try:
            results = deps.search_public_web(
                query,
                timeout_seconds=max(8, int(runtime["search_timeout_seconds"]) - 1),
                limit=max(3, int(runtime["search_result_limit"]) - 2),
            )
        except Exception:
            results = []
        public_profile_hits.extend(results)
    ranked_profile_hits = [
        hit
        for hit in deps.hybrid_rank_hits(
            public_profile_hits,
            keyword=keyword,
            research_focus=research_focus,
            scope_hints=scope_hints,
        )
    ]
    selected_profile_hits = deps.select_hits_with_source_balance(
        ranked_profile_hits,
        limit=3 if research_mode == "fast" else 5,
    )
    if not selected_profile_hits and seed_profile_hits:
        selected_profile_hits = deps.dedupe_hits(seed_profile_hits)[:2]
    if not selected_profile_hits:
        return CandidateProfileEnrichmentResult(
            sources=sources,
            rankings=rankings,
            scope_hints=scope_hints,
            theme_terms=theme_terms,
            company_anchor_terms=company_anchor_terms,
            entity_graph=entity_graph,
            corrective_triggered=corrective_triggered,
            candidate_profile_sources=candidate_profile_sources,
            candidate_profile_companies=candidate_profile_companies,
            candidate_profile_hit_count=candidate_profile_hit_count,
            candidate_profile_official_hit_count=candidate_profile_official_hit_count,
            candidate_profile_source_labels=candidate_profile_source_labels,
            region_conflict_signatures=region_conflict_signatures,
        )

    profile_sources = [
        source
        for source in (
            deps.extract_source_document_best_effort(
                hit,
                timeout_seconds=int(runtime["url_timeout_seconds"]),
                excerpt_chars=source_excerpt_chars,
            )
            for hit in selected_profile_hits
        )
        if source is not None and _is_valid_profile_source(source)
    ]
    if not profile_sources:
        return CandidateProfileEnrichmentResult(
            sources=sources,
            rankings=rankings,
            scope_hints=scope_hints,
            theme_terms=theme_terms,
            company_anchor_terms=company_anchor_terms,
            entity_graph=entity_graph,
            corrective_triggered=corrective_triggered,
            candidate_profile_sources=candidate_profile_sources,
            candidate_profile_companies=candidate_profile_companies,
            candidate_profile_hit_count=candidate_profile_hit_count,
            candidate_profile_official_hit_count=candidate_profile_official_hit_count,
            candidate_profile_source_labels=candidate_profile_source_labels,
            region_conflict_signatures=region_conflict_signatures,
        )

    candidate_profile_sources = list(profile_sources)
    candidate_profile_hit_count = len(profile_sources)
    candidate_profile_official_hit_count = sum(1 for source in profile_sources if source.source_tier == "official")
    candidate_profile_source_labels = deps.dedupe_strings(
        [
            normalize_text(source.source_label or source.title or source.domain or "")
            for source in profile_sources
        ],
        8,
    )
    # Static home/contact seeds prove organization identity, but do not prove
    # that the organization is relevant to the current research topic.
    topical_profile_sources = _topical_profile_sources(
        profile_sources,
        seed_profile_urls=seed_profile_urls,
    )
    sources = deps.dedupe_sources([*sources, *topical_profile_sources])
    region_conflict_signatures.update(
        deps.region_conflict_signature(source)
        for source in sources
        if deps.source_has_region_conflict(source, scope_hints=scope_hints)
    )
    refined_sources = deps.refine_sources_for_report(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
        company_anchor_terms=company_anchor_terms,
        theme_terms=theme_terms,
    )
    if refined_sources:
        sources = refined_sources
    corrective_triggered = True
    scope_hints = deps.merge_scope_hints(input_scope_hints, deps.infer_scope_hints(keyword, research_focus, sources))
    theme_terms = deps.build_theme_terms(keyword, research_focus, scope_hints)
    company_anchor_terms = deps.resolved_company_anchor_terms(keyword, research_focus, scope_hints)
    entity_graph = deps.build_entity_graph(
        sources,
        scope_hints=scope_hints,
    )
    rankings = rank_report_entities(
        sources=sources,
        parsed=parsed,
        output_language=output_language,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        entity_graph=entity_graph,
        rank_top_entities=deps.rank_top_entities,
        filtered_rank_fallback_values=deps.filtered_rank_fallback_values,
        dedupe_strings=deps.dedupe_strings,
        limit=3,
    )
    return CandidateProfileEnrichmentResult(
        sources=sources,
        rankings=rankings,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        company_anchor_terms=company_anchor_terms,
        entity_graph=entity_graph,
        corrective_triggered=corrective_triggered,
        candidate_profile_sources=candidate_profile_sources,
        candidate_profile_companies=candidate_profile_companies,
        candidate_profile_hit_count=candidate_profile_hit_count,
        candidate_profile_official_hit_count=candidate_profile_official_hit_count,
        candidate_profile_source_labels=candidate_profile_source_labels,
        region_conflict_signatures=region_conflict_signatures,
    )
