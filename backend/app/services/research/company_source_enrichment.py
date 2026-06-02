from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.services.content_extractor import extract_domain, normalize_text
from app.services.research.source_documents import SourceDocument
from app.services.research.web_search import SearchHit


@dataclass(frozen=True, slots=True)
class CompanySourceEnrichmentDependencies:
    dedupe_strings: Callable[..., list[str]]
    build_company_contact_query_plan: Callable[..., list[str]]
    build_company_profile_query_plan: Callable[..., list[str]]
    emit_research_progress: Callable[..., None]
    build_progress_message: Callable[..., str]
    build_company_seed_hits: Callable[..., list[SearchHit]]
    search_public_web: Callable[..., list[SearchHit]]
    hybrid_rank_hits: Callable[..., list[SearchHit]]
    select_hits_with_source_balance: Callable[..., list[SearchHit]]
    dedupe_hits: Callable[[list[SearchHit]], list[SearchHit]]
    classify_source_tier: Callable[..., str]
    classify_source_type: Callable[[str], str]
    derive_source_label: Callable[..., str]
    extract_source_document_best_effort: Callable[..., SourceDocument | None]
    dedupe_sources: Callable[[list[SourceDocument]], list[SourceDocument]]
    region_conflict_signature: Callable[[SourceDocument], str]
    source_has_region_conflict: Callable[..., bool]
    refine_sources_for_report: Callable[..., list[SourceDocument]]
    merge_scope_hints: Callable[[dict[str, object], dict[str, object]], dict[str, object]]
    infer_scope_hints: Callable[[str, str | None, list[SourceDocument]], dict[str, object]]
    build_theme_terms: Callable[[str, str | None, dict[str, object]], list[str]]
    build_source_intelligence: Callable[..., dict[str, list[str]]]


@dataclass(frozen=True, slots=True)
class CompanySourceEnrichmentResult:
    sources: list[SourceDocument]
    scope_hints: dict[str, object]
    theme_terms: list[str]
    source_intelligence: dict[str, list[str]]
    region_conflict_signatures: set[str]


def enrich_company_sources(
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    research_mode: str,
    sources: list[SourceDocument],
    input_scope_hints: dict[str, object],
    scope_hints: dict[str, object],
    theme_terms: list[str],
    company_anchor_terms: list[str],
    theme_seed_companies: list[str],
    runtime: dict[str, int | str | bool],
    source_excerpt_chars: int,
    progress_callback: Any | None,
    deps: CompanySourceEnrichmentDependencies,
) -> CompanySourceEnrichmentResult:
    company_seed_names = [
        *company_anchor_terms[:3],
        *scope_hints.get("company_anchors", [])[:3],
        *scope_hints.get("clients", [])[:2],
        *theme_seed_companies[:4],
    ]
    company_contact_queries = deps.build_company_contact_query_plan(
        company_seed_names,
        keyword=keyword,
        research_focus=research_focus,
        limit=4 if research_mode == "fast" else 6,
    )
    company_profile_queries = deps.build_company_profile_query_plan(
        company_seed_names,
        keyword=keyword,
        research_focus=research_focus,
        limit=4 if research_mode == "fast" else 6,
    )
    company_enrichment_queries = deps.dedupe_strings(
        [*company_profile_queries, *company_contact_queries],
        6 if research_mode == "fast" else 10,
    )
    region_conflict_signatures: set[str] = set()
    if company_enrichment_queries:
        deps.emit_research_progress(
            progress_callback,
            "company_contacts",
            61,
            deps.build_progress_message("正在补充官网与公开联系方式", keyword=keyword, research_focus=research_focus, mode=research_mode),
        )
        company_contact_hits: list[SearchHit] = []
        seed_contact_hits = deps.build_company_seed_hits(company_seed_names, keyword=keyword)
        company_contact_hits.extend(seed_contact_hits)
        for query in company_enrichment_queries:
            try:
                results = deps.search_public_web(
                    query,
                    timeout_seconds=max(8, int(runtime["search_timeout_seconds"]) - 1),
                    limit=max(3, int(runtime["search_result_limit"]) - 2),
                )
            except Exception:
                results = []
            company_contact_hits.extend(results)
        ranked_contact_hits = [
            hit
            for hit in deps.hybrid_rank_hits(
                company_contact_hits,
                keyword=keyword,
                research_focus=research_focus,
                scope_hints=scope_hints,
            )
        ]
        selected_contact_hits = deps.select_hits_with_source_balance(
            ranked_contact_hits,
            limit=3 if research_mode == "fast" else 5,
        )
        if not selected_contact_hits and seed_contact_hits:
            selected_contact_hits = deps.dedupe_hits(seed_contact_hits)[:2]
        elif seed_contact_hits:
            selected_urls = {normalize_text(hit.url) for hit in selected_contact_hits if normalize_text(hit.url)}
            official_seed_hits = [
                hit
                for hit in deps.dedupe_hits(seed_contact_hits)
                if normalize_text(hit.url) and normalize_text(hit.url) not in selected_urls
            ]
            if official_seed_hits and not any(
                deps.classify_source_tier(
                    source_type=hit.source_hint or deps.classify_source_type(hit.url),
                    domain=extract_domain(hit.url),
                    source_label=deps.derive_source_label(
                        source_type=hit.source_hint or deps.classify_source_type(hit.url),
                        domain=extract_domain(hit.url),
                        fallback=getattr(hit, "source_label", None),
                    ),
                )
                == "official"
                for hit in selected_contact_hits
            ):
                selected_contact_hits = [official_seed_hits[0], *selected_contact_hits]
                selected_contact_hits = deps.dedupe_hits(selected_contact_hits)[: (3 if research_mode == "fast" else 5)]
        if selected_contact_hits:
            contact_sources = [
                source
                for source in (
                    deps.extract_source_document_best_effort(
                        hit,
                        timeout_seconds=int(runtime["url_timeout_seconds"]),
                        excerpt_chars=source_excerpt_chars,
                    )
                    for hit in selected_contact_hits
                )
                if source is not None
            ]
            if not contact_sources and seed_contact_hits:
                contact_sources = [
                    source
                    for source in (
                        deps.extract_source_document_best_effort(
                            hit,
                            timeout_seconds=int(runtime["url_timeout_seconds"]),
                            excerpt_chars=source_excerpt_chars,
                        )
                        for hit in deps.dedupe_hits(seed_contact_hits)[:2]
                    )
                    if source is not None
                ]
            if contact_sources:
                sources = deps.dedupe_sources([*sources, *contact_sources])
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
                elif contact_sources:
                    sources = deps.dedupe_sources(contact_sources)
    scope_hints = deps.merge_scope_hints(input_scope_hints, deps.infer_scope_hints(keyword, research_focus, sources))
    theme_terms = deps.build_theme_terms(keyword, research_focus, scope_hints)
    source_intelligence = deps.build_source_intelligence(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        scope_hints=scope_hints,
    )
    return CompanySourceEnrichmentResult(
        sources=sources,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        source_intelligence=source_intelligence,
        region_conflict_signatures=region_conflict_signatures,
    )
