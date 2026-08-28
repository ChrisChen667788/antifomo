from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.services.content_extractor import normalize_text
from app.services.research.source_documents import SourceDocument
from app.services.research.web_search import SearchHit


SOURCE_MAX_AGE_YEARS = 7


@dataclass(frozen=True, slots=True)
class SourceScopePolicyDependencies:
    dedupe_sources: Callable[[Iterable[SourceDocument]], list[SourceDocument]]
    rerank_sources_hybrid: Callable[..., list[SourceDocument]]
    filter_sources_by_theme_relevance: Callable[..., list[SourceDocument]]
    source_text: Callable[[SourceDocument], str]
    search_query_text_for_matching: Callable[[SourceDocument | SearchHit], str]
    expand_region_scope_terms: Callable[[list[str]], list[str]]
    classify_source_type: Callable[[str], str]
    classify_source_tier: Callable[..., str]
    extract_domain: Callable[[str], str | None]
    source_supports_company_intent: Callable[..., bool]
    build_strict_theme_terms: Callable[[dict[str, object]], list[str]]
    source_matches_company_anchor: Callable[[SourceDocument | SearchHit, list[str]], bool]
    source_has_region_conflict: Callable[..., bool]
    infer_source_published_at: Callable[[SourceDocument], datetime | None]
    region_scope_aliases: dict[str, tuple[str, ...]]
    industry_scope_aliases: dict[str, tuple[str, ...]]


def refine_sources_for_report(
    sources: Iterable[SourceDocument],
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
    company_anchor_terms: list[str],
    theme_terms: list[str],
    deps: SourceScopePolicyDependencies,
) -> list[SourceDocument]:
    deduped_sources = deps.dedupe_sources(sources)
    if not deduped_sources:
        return []
    filtered_sources = deps.filter_sources_by_theme_relevance(
        deduped_sources,
        theme_terms=theme_terms,
        scope_hints=scope_hints,
        company_anchor_terms=company_anchor_terms,
    )
    return deps.rerank_sources_hybrid(
        filtered_sources or deduped_sources,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
    )


def source_scope_match_score(
    source: SourceDocument | SearchHit,
    *,
    scope_hints: dict[str, object],
    company_anchor_terms: list[str],
    theme_terms: list[str],
    deps: SourceScopePolicyDependencies,
) -> int:
    text = normalize_text(
        " ".join(
            [
                str(getattr(source, "title", "") or ""),
                str(getattr(source, "snippet", "") or ""),
                str(getattr(source, "excerpt", "") or ""),
                deps.search_query_text_for_matching(source),
                str(getattr(source, "source_label", "") or ""),
                str(getattr(source, "domain", "") or ""),
                str(getattr(source, "url", "") or ""),
            ]
        )
    ).lower()
    score = 0
    regions = [
        item.lower()
        for item in deps.expand_region_scope_terms(
            [normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
        )
    ]
    industries = [normalize_text(str(item)).lower() for item in scope_hints.get("industries", []) if normalize_text(str(item))]
    industry_aliases = [
        normalize_text(alias).lower()
        for industry in scope_hints.get("industries", []) or []
        for alias in deps.industry_scope_aliases.get(normalize_text(str(industry)), ())
        if normalize_text(alias)
    ]
    clients = [normalize_text(str(item)).lower() for item in scope_hints.get("clients", []) if normalize_text(str(item))]
    company_terms = [normalize_text(item).lower() for item in company_anchor_terms if normalize_text(item)]
    if bool(scope_hints.get("prefer_company_entities")) and company_terms and not any(term in text for term in company_terms):
        return 0
    source_tier = normalize_text(str(getattr(source, "source_tier", "") or "")).lower()
    if not source_tier:
        url = str(getattr(source, "url", "") or "")
        source_type = str(getattr(source, "source_type", "") or getattr(source, "source_hint", "") or deps.classify_source_type(url))
        domain = str(getattr(source, "domain", "") or deps.extract_domain(url) or "")
        source_label = str(getattr(source, "source_label", "") or "")
        source_tier = deps.classify_source_tier(source_type=source_type, domain=domain, source_label=source_label)
    if any(term in text for term in theme_terms):
        score += 4
    if any(region in text for region in regions):
        score += 4
    if any(industry in text for industry in [*industries, *industry_aliases]):
        score += 4
    if any(client in text for client in clients):
        score += 6
    if any(term in text for term in company_terms):
        score += 8
    if source_tier == "official" and score > 0:
        score += 2
    return score


def filter_recent_sources(
    sources: list[SourceDocument],
    *,
    max_age_years: int,
    deps: SourceScopePolicyDependencies,
) -> list[SourceDocument]:
    now = datetime.now(timezone.utc)
    cutoff = datetime(max(now.year - max_age_years, 1900), now.month, now.day, tzinfo=timezone.utc)
    filtered: list[SourceDocument] = []
    for source in sources:
        published_at = deps.infer_source_published_at(source)
        if published_at and published_at < cutoff:
            continue
        filtered.append(source)
    return filtered


def source_theme_match_score(
    source: SourceDocument,
    *,
    theme_terms: list[str],
    scope_hints: dict[str, object],
    deps: SourceScopePolicyDependencies,
) -> int:
    if not theme_terms:
        return 0
    text = deps.source_text(source)
    lowered = text.lower()
    title_lower = normalize_text(source.title).lower()
    label_lower = normalize_text(source.source_label or "").lower()
    regions = [
        item.lower()
        for item in deps.expand_region_scope_terms(
            [normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
        )
    ]
    clients = [normalize_text(str(item)).lower() for item in scope_hints.get("clients", []) if normalize_text(str(item))]
    exclusion_terms = [
        normalize_text(str(item)).lower()
        for item in scope_hints.get("strategy_exclusion_terms", [])
        if normalize_text(str(item))
    ]
    score = 0
    title_hits = sum(1 for term in theme_terms if term in title_lower)
    body_hits = sum(1 for term in theme_terms if term in lowered)
    label_hits = sum(1 for term in theme_terms if term in label_lower)
    if title_hits:
        score += min(title_hits, 3) * 6
    if body_hits:
        score += min(body_hits, 4) * 4
    if label_hits:
        score += min(label_hits, 2) * 3
    if regions and any(region in lowered for region in regions):
        score += 3
    if clients and any(client in lowered or client in title_lower for client in clients):
        score += 5
    if exclusion_terms and any(term in lowered or term in title_lower for term in exclusion_terms):
        score -= 18
    return score


def filter_sources_by_theme_relevance(
    sources: list[SourceDocument],
    *,
    theme_terms: list[str],
    scope_hints: dict[str, object],
    company_anchor_terms: list[str] | None,
    deps: SourceScopePolicyDependencies,
) -> list[SourceDocument]:
    if not sources or not theme_terms:
        return sources
    sources = [source for source in sources if not deps.source_has_region_conflict(source, scope_hints=scope_hints)]
    if not sources:
        return []
    prefer_company_entities = bool(scope_hints.get("prefer_company_entities"))
    theme_labels = [
        normalize_text(str(item))
        for item in scope_hints.get("industries", []) or []
        if normalize_text(str(item))
    ]
    seed_companies = [
        normalize_text(str(item))
        for item in scope_hints.get("seed_companies", []) or []
        if normalize_text(str(item))
    ]
    if prefer_company_entities:
        company_scoped_sources = [
            source
            for source in sources
            if deps.source_supports_company_intent(
                source,
                theme_labels=theme_labels,
                seed_companies=seed_companies,
            )
        ]
        if company_scoped_sources:
            sources = company_scoped_sources
    strict_theme_terms = deps.build_strict_theme_terms(scope_hints)
    if strict_theme_terms:
        strict_sources = [
            source
            for source in sources
            if any(term in deps.source_text(source).lower() or term in normalize_text(source.title).lower() for term in strict_theme_terms)
        ]
        if strict_sources:
            strict_source_ids = {id(source) for source in strict_sources}
            sources = [
                *strict_sources,
                *(source for source in sources if id(source) not in strict_source_ids),
            ]
    company_terms = (
        [normalize_text(item) for item in company_anchor_terms or [] if normalize_text(item)]
        if prefer_company_entities
        else []
    )
    scored_sources = [
        (
            source,
            source_theme_match_score(source, theme_terms=theme_terms, scope_hints=scope_hints, deps=deps),
            source_scope_match_score(
                source,
                scope_hints=scope_hints,
                company_anchor_terms=company_terms,
                theme_terms=theme_terms,
                deps=deps,
            ),
        )
        for source in sources
    ]
    matched = [source for source, theme_score, _ in scored_sources if theme_score >= 8]
    if company_terms:
        matched = [source for source in matched if deps.source_matches_company_anchor(source, company_terms)]
        if matched:
            return matched
        title_matched = [
            source
            for source, theme_score, scope_score in scored_sources
            if theme_score >= 12 and scope_score >= 8 and deps.source_matches_company_anchor(source, company_terms)
        ]
        if title_matched:
            return title_matched
        return []
    scoped_matched = [source for source, theme_score, scope_score in scored_sources if theme_score >= 6 and scope_score >= 4]
    if scoped_matched:
        minimum = min(4, len(sources))
        if len(scoped_matched) >= max(2, minimum):
            return scoped_matched
        title_scoped = [source for source, theme_score, scope_score in scored_sources if theme_score >= 10 and scope_score >= 3]
        if len(title_scoped) >= 2:
            return title_scoped
        return scoped_matched
    if len(matched) >= min(4, len(sources)):
        return matched
    title_matched = [source for source, theme_score, _ in scored_sources if theme_score >= 12]
    if len(title_matched) >= 2:
        return title_matched
    return sources


def source_has_region_conflict(source: SourceDocument, *, scope_hints: dict[str, object], text_has_region_conflict: Callable[..., bool], source_text: Callable[[SourceDocument], str]) -> bool:
    return text_has_region_conflict(source_text(source), scope_hints=scope_hints)


def region_conflict_signature(source: SourceDocument) -> str:
    return normalize_text(" | ".join([source.url or "", source.title or "", source.domain or ""]))
