from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from app.services.content_extractor import extract_domain, normalize_text
from app.services.knowledge_retrieval_service import TextRetrievalCandidate, retrieve_text_matches
from app.services.research.source_documents import SourceDocument
from app.services.research.web_search import SearchHit


PROCUREMENT_DOMAINS = {
    "ccgp.gov.cn",
    "www.ccgp.gov.cn",
    "ggzy.gov.cn",
    "www.ggzy.gov.cn",
    "chinabidding.com",
    "www.chinabidding.com",
}

EXCHANGE_DOMAINS = {
    "cninfo.com.cn",
    "www.cninfo.com.cn",
    "hkexnews.hk",
    "www.hkexnews.hk",
    "sec.gov",
    "www.sec.gov",
}


@dataclass(frozen=True, slots=True)
class SourceRankingDependencies:
    dedupe_hits: Callable[[Iterable[SearchHit]], list[SearchHit]]
    dedupe_sources: Callable[[Iterable[SourceDocument]], list[SourceDocument]]
    extract_topic_anchor_terms: Callable[[str, str | None], list[str]]
    build_theme_terms: Callable[[str, str | None, dict[str, object]], list[str]]
    resolved_company_anchor_terms: Callable[[str, str | None, dict[str, object] | None], list[str]]
    source_scope_match_score: Callable[..., int]
    get_settings: Callable[[], Any]
    safe_int: Callable[..., int]
    rerank_sources_cross_encoder: Callable[..., tuple[list[SourceDocument], Any]]
    retrieve_text_matches: Callable[..., list[Any]] = retrieve_text_matches


def classify_source_type(url: str) -> str:
    domain = (extract_domain(url) or "").lower()
    if "jianyu360.com" in domain or "jianyu360.cn" in domain:
        return "tender_feed"
    if "yuntoutiao.com" in domain:
        return "tech_media_feed"
    if "mp.weixin.qq.com" in domain:
        return "wechat"
    if domain in PROCUREMENT_DOMAINS or "ccgp.gov.cn" in domain or "ggzy.gov.cn" in domain:
        return "procurement"
    if domain in EXCHANGE_DOMAINS:
        return "filing"
    if ".gov." in domain or domain.endswith(".gov.cn"):
        return "policy"
    return "web"


def classify_source_tier(*, source_type: str, domain: str | None, source_label: str | None) -> str:
    normalized_domain = (domain or "").lower()
    normalized_label = normalize_text(source_label or "").lower()
    if source_type in {
        "policy",
        "procurement",
        "filing",
        "official_tender_feed",
        "official_tender_news",
        "official_policy_speech",
        "regional_public_resource",
    }:
        return "official"
    if any(token in normalized_label for token in ("官网", "投资者关系", "联系我们", "官方")):
        return "official"
    if any(token in normalized_label for token in ("公共资源", "招标投标网", "政府采购", "中国政府网")):
        return "official"
    if any(token in normalized_domain for token in ("gov.cn", "ggzy.gov.cn", "cninfo.com.cn", "sec.gov", "hkexnews.hk")):
        return "official"
    if source_type in {"tender_feed", "compliant_procurement_aggregate"}:
        return "aggregate"
    if any(token in normalized_label for token in ("剑鱼标讯", "云头条", "合规聚合")):
        return "aggregate" if "云头条" not in normalized_label else "media"
    if any(token in normalized_domain for token in ("jianyu", "cecbid", "cebpubservice", "china-cpp", "chinabidding")):
        return "aggregate"
    return "media"


def derive_source_label(*, source_type: str, domain: str | None, fallback: str | None) -> str | None:
    if fallback:
        return fallback
    normalized_domain = (domain or "").lower()
    if "ggzy.gov.cn" in normalized_domain:
        return "全国公共资源交易平台"
    if "gov.cn" in normalized_domain:
        return "中国政府网政策/讲话"
    if "cninfo.com.cn" in normalized_domain:
        return "巨潮资讯公告"
    if "hkexnews.hk" in normalized_domain:
        return "港交所公告"
    if "sec.gov" in normalized_domain:
        return "SEC 公告"
    if "mp.weixin.qq.com" in normalized_domain:
        return "微信公众号"
    if "cecbid" in normalized_domain or "cebpubservice" in normalized_domain or "china-cpp" in normalized_domain:
        return "政府采购合规聚合"
    if "jianyu" in normalized_domain:
        return "剑鱼标讯"
    if "yuntoutiao" in normalized_domain:
        return "云头条"
    if source_type == "web":
        return "互联网公开网页"
    return None


def search_query_text_for_matching(source: SearchHit | SourceDocument) -> str:
    if isinstance(source, SearchHit):
        return str(getattr(source, "search_query", "") or "")
    return ""


def source_matches_company_anchor(source: SearchHit | SourceDocument, company_anchor_terms: list[str]) -> bool:
    if not company_anchor_terms:
        return True
    haystack = normalize_text(
        " ".join(
            [
                str(getattr(source, "title", "") or ""),
                str(getattr(source, "snippet", "") or ""),
                str(getattr(source, "excerpt", "") or ""),
                search_query_text_for_matching(source),
                str(getattr(source, "source_label", "") or ""),
                str(getattr(source, "url", "") or ""),
                str(getattr(source, "domain", "") or ""),
            ]
        )
    ).lower()
    return any(normalize_text(term).lower() in haystack for term in company_anchor_terms if normalize_text(term))


def _semantic_score_hit(
    hit: SearchHit,
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object] | None,
    deps: SourceRankingDependencies,
) -> tuple[int, SearchHit]:
    scope = scope_hints or {}
    haystack = normalize_text(
        " ".join(
            [
                hit.title,
                hit.snippet,
                hit.search_query,
                hit.source_label or "",
                hit.url,
                extract_domain(hit.url) or "",
            ]
        )
    ).lower()
    title_haystack = normalize_text(hit.title).lower()
    domain = (extract_domain(hit.url) or "").lower()
    topic_anchor_terms = [normalize_text(item).lower() for item in deps.extract_topic_anchor_terms(keyword, research_focus) if normalize_text(item)]
    company_anchor_terms = [
        normalize_text(item).lower()
        for item in deps.resolved_company_anchor_terms(keyword, research_focus, scope)
        if normalize_text(item)
    ]
    theme_terms = [normalize_text(item).lower() for item in deps.build_theme_terms(keyword, research_focus, scope) if normalize_text(item)]
    scope_regions = [normalize_text(str(item)).lower() for item in scope.get("regions", []) or [] if normalize_text(str(item))]
    scope_industries = [normalize_text(str(item)).lower() for item in scope.get("industries", []) or [] if normalize_text(str(item))]
    scope_clients = [normalize_text(str(item)).lower() for item in scope.get("clients", []) or [] if normalize_text(str(item))]
    source_type = hit.source_hint or classify_source_type(hit.url)
    source_label = derive_source_label(source_type=source_type, domain=domain, fallback=hit.source_label)
    source_tier = classify_source_tier(source_type=source_type, domain=domain, source_label=source_label)

    theme_match_count = sum(1 for term in theme_terms if term in haystack)
    topic_match_count = sum(1 for term in topic_anchor_terms if term in haystack)
    company_match_count = sum(1 for term in company_anchor_terms if term in haystack or term in domain)
    region_match_count = sum(1 for term in scope_regions if term in haystack)
    industry_match_count = sum(1 for term in scope_industries if term in haystack)
    client_match_count = sum(1 for term in scope_clients if term in haystack)

    score = 0
    if theme_match_count:
        score += 12 + min(theme_match_count, 4) * 4
    if topic_match_count:
        score += 10 + min(topic_match_count, 3) * 4
    if company_match_count:
        score += 16 + min(company_match_count, 2) * 6
    if region_match_count:
        score += 6 + min(region_match_count, 2) * 2
    if industry_match_count:
        score += 6 + min(industry_match_count, 2) * 2
    if client_match_count:
        score += 10 + min(client_match_count, 2) * 4
    if any(term in title_haystack for term in topic_anchor_terms[:4]):
        score += 6
    if any(term in title_haystack for term in company_anchor_terms[:4]):
        score += 8
    if source_tier == "official":
        score += 8
    elif source_tier == "aggregate":
        score += 4
    if source_type == "wechat":
        score += 3
    if bool(scope.get("prefer_company_entities")) and company_anchor_terms and company_match_count == 0:
        return 0, hit
    if topic_anchor_terms and topic_match_count == 0 and theme_match_count == 0 and company_match_count == 0:
        return 0, hit
    return score, hit


def _rrf_score(rank: int, *, k: int = 60) -> float:
    return 1.0 / float(k + max(rank, 1))


def build_search_hit_retrieval_query(
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object] | None,
    *,
    deps: SourceRankingDependencies,
) -> str:
    scope = scope_hints or {}
    candidates: list[str] = [
        normalize_text(keyword),
        normalize_text(research_focus or ""),
        *deps.extract_topic_anchor_terms(keyword, research_focus),
        *deps.resolved_company_anchor_terms(keyword, research_focus, scope),
        *(normalize_text(str(item)) for item in scope.get("clients", []) or [] if normalize_text(str(item))),
        *(normalize_text(str(item)) for item in scope.get("regions", []) or [] if normalize_text(str(item))),
        *(normalize_text(str(item)) for item in scope.get("industries", []) or [] if normalize_text(str(item))),
        *(
            normalize_text(str(item))
            for item in scope.get("strategy_must_include_terms", []) or []
            if normalize_text(str(item))
        ),
        *(
            normalize_text(str(item))
            for item in scope.get("strategy_query_expansions", []) or []
            if normalize_text(str(item))
        ),
    ]
    return normalize_text(" ".join(_dedupe_strings(candidates, 18)))


def _dedupe_strings(values: Iterable[object], limit: int) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_text(str(value or ""))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        rows.append(normalized)
        if len(rows) >= limit:
            break
    return rows


def build_search_hit_retrieval_candidates(hit: SearchHit) -> list[TextRetrievalCandidate]:
    normalized_url = normalize_text(hit.url)
    if not normalized_url:
        return []
    domain = extract_domain(hit.url)
    source_type = hit.source_hint or classify_source_type(hit.url)
    source_label = derive_source_label(
        source_type=source_type,
        domain=domain,
        fallback=hit.source_label,
    )
    source_tier = classify_source_tier(
        source_type=source_type,
        domain=domain,
        source_label=source_label,
    )
    priority = 0
    if source_tier == "official":
        priority += 10
    elif source_tier == "aggregate":
        priority += 5
    if source_type in {"policy", "procurement", "filing"}:
        priority += 3
    elif source_type == "wechat":
        priority += 2
    if normalize_text(hit.snippet):
        priority += 2

    primary_text = normalize_text(
        " ".join(
            part
            for part in [
                hit.title,
                hit.snippet,
                source_label or "",
                domain or "",
                hit.url,
            ]
            if normalize_text(part)
        )
    )
    title_text = normalize_text(
        " ".join(
            part
            for part in [
                hit.title,
                source_label or "",
                domain or "",
            ]
            if normalize_text(part)
        )
    )

    candidates = [
        TextRetrievalCandidate(
            key=normalized_url,
            text=primary_text,
            source_tier=source_tier,
            priority=priority,
        )
    ]
    if title_text and title_text != primary_text:
        candidates.append(
            TextRetrievalCandidate(
                key=normalized_url,
                text=title_text,
                source_tier=source_tier,
                priority=max(1, priority - 2),
            )
        )
    return candidates


def hybrid_rank_hits(
    hits: Iterable[SearchHit],
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object] | None = None,
    deps: SourceRankingDependencies,
) -> list[SearchHit]:
    deduped_hits = deps.dedupe_hits(hits)
    if not deduped_hits:
        return []

    retrieval_scores: dict[str, float] = {}
    semantic_scores: dict[str, int] = {}
    scope_scores: dict[str, int] = {}
    hits_by_url: dict[str, SearchHit] = {}
    theme_terms = deps.build_theme_terms(keyword, research_focus, scope_hints or {})
    company_anchor_terms = deps.resolved_company_anchor_terms(keyword, research_focus, scope_hints)
    retrieval_candidates: list[TextRetrievalCandidate] = []

    for hit in deduped_hits:
        normalized_url = normalize_text(hit.url)
        if not normalized_url:
            continue
        hits_by_url[normalized_url] = hit
        retrieval_candidates.extend(build_search_hit_retrieval_candidates(hit))
        semantic_scores[normalized_url] = _semantic_score_hit(
            hit,
            keyword=keyword,
            research_focus=research_focus,
            scope_hints=scope_hints,
            deps=deps,
        )[0]
        scope_scores[normalized_url] = deps.source_scope_match_score(
            hit,
            scope_hints=scope_hints or {},
            company_anchor_terms=company_anchor_terms,
            theme_terms=theme_terms,
        )

    retrieval_query = build_search_hit_retrieval_query(keyword, research_focus, scope_hints, deps=deps)
    retrieval_matches = deps.retrieve_text_matches(
        retrieval_candidates,
        retrieval_query,
        limit=max(40, len(retrieval_candidates)),
    )
    retrieval_scores = {
        match.key: match.score
        for match in retrieval_matches
        if match.key in hits_by_url and match.score > 0
    }

    retrieval_ranked = [
        match.key
        for match in retrieval_matches
        if match.key in hits_by_url and match.score > 0
    ]
    semantic_ranked = [url for url, score in sorted(semantic_scores.items(), key=lambda item: item[1], reverse=True) if score > 0]
    scope_ranked = [url for url, score in sorted(scope_scores.items(), key=lambda item: item[1], reverse=True) if score > 0]

    hybrid_scores: dict[str, float] = {}
    for ranked_urls, score_map in (
        (retrieval_ranked, retrieval_scores),
        (semantic_ranked, semantic_scores),
        (scope_ranked, scope_scores),
    ):
        for index, url in enumerate(ranked_urls, start=1):
            hybrid_scores[url] = hybrid_scores.get(url, 0.0) + _rrf_score(index) + float(score_map.get(url, 0)) / 1000.0

    ordered_urls = sorted(
        hybrid_scores,
        key=lambda url: (
            hybrid_scores.get(url, 0.0),
            retrieval_scores.get(url, 0.0),
            semantic_scores.get(url, 0),
            scope_scores.get(url, 0),
        ),
        reverse=True,
    )
    ranked_hits: list[SearchHit] = []
    for url in ordered_urls:
        hit = hits_by_url[url]
        if hybrid_scores.get(url, 0.0) <= 0:
            continue
        if (
            bool((scope_hints or {}).get("prefer_company_entities"))
            and company_anchor_terms
            and not source_matches_company_anchor(hit, company_anchor_terms)
        ):
            continue
        if (
            retrieval_scores.get(url, 0.0) <= 0
            and semantic_scores.get(url, 0) <= 0
            and scope_scores.get(url, 0) <= 0
        ):
            continue
        ranked_hits.append(hit)
    return ranked_hits


def build_source_retrieval_candidates(source: SourceDocument) -> list[TextRetrievalCandidate]:
    normalized_url = normalize_text(source.url)
    if not normalized_url:
        return []
    domain = normalize_text(source.domain or "") or extract_domain(source.url) or ""
    source_type = normalize_text(source.source_type) or classify_source_type(source.url)
    source_label = derive_source_label(
        source_type=source_type,
        domain=domain,
        fallback=source.source_label,
    )
    source_tier = normalize_text(source.source_tier) or classify_source_tier(
        source_type=source_type,
        domain=domain,
        source_label=source_label,
    )
    priority = 0
    if source_tier == "official":
        priority += 10
    elif source_tier == "aggregate":
        priority += 5
    if source.content_status == "browser_extracted":
        priority += 8
    elif source.content_status == "extracted":
        priority += 6
    elif source.content_status == "reader_proxy":
        priority += 4
    elif source.content_status in {"snippet_only", "fetch_failed"}:
        priority -= 4
    excerpt = normalize_text(source.excerpt)
    if len(excerpt) >= 260:
        priority += 3

    primary_text = normalize_text(
        " ".join(
            part
            for part in [
                source.title,
                source.snippet,
                excerpt,
                source_label or "",
                domain,
                source.url,
            ]
            if normalize_text(part)
        )
    )
    title_text = normalize_text(
        " ".join(
            part
            for part in [
                source.title,
                source_label or "",
                domain,
            ]
            if normalize_text(part)
        )
    )

    candidates = [
        TextRetrievalCandidate(
            key=normalized_url,
            text=primary_text,
            source_tier=source_tier,
            priority=max(0, priority),
        )
    ]
    if title_text and title_text != primary_text:
        candidates.append(
            TextRetrievalCandidate(
                key=normalized_url,
                text=title_text,
                source_tier=source_tier,
                priority=max(0, priority - 2),
            )
        )
    if excerpt and excerpt not in {primary_text, title_text}:
        candidates.append(
            TextRetrievalCandidate(
                key=normalized_url,
                text=normalize_text(" ".join(part for part in [source.title, excerpt] if normalize_text(part))),
                source_tier=source_tier,
                priority=max(0, priority - 1),
            )
        )
    return candidates


def source_rerank_score(
    source: SourceDocument,
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object] | None = None,
    deps: SourceRankingDependencies,
) -> int:
    theme_terms = deps.build_theme_terms(keyword, research_focus, scope_hints or {})
    company_anchor_terms = deps.resolved_company_anchor_terms(keyword, research_focus, scope_hints)
    base = deps.source_scope_match_score(
        source,
        scope_hints=scope_hints or {},
        company_anchor_terms=company_anchor_terms,
        theme_terms=theme_terms,
    )
    text = normalize_text(
        " ".join(
            [
                source.title,
                source.snippet,
                source.excerpt,
                source.source_label or "",
                source.url,
                source.domain or "",
            ]
        )
    ).lower()
    score = base
    if source.source_tier == "official":
        score += 18
    elif source.source_tier == "aggregate":
        score += 8
    if source.content_status == "browser_extracted":
        score += 10
    elif source.content_status == "extracted":
        score += 7
    elif source.content_status == "reader_proxy":
        score += 5
    elif source.content_status in {"snippet_only", "fetch_failed"}:
        score -= 6
    if len(normalize_text(source.excerpt)) >= 260:
        score += 4
    if len(normalize_text(source.excerpt)) < 120:
        score -= 4
    if company_anchor_terms and not source_matches_company_anchor(source, company_anchor_terms):
        score -= 14 if bool((scope_hints or {}).get("prefer_company_entities")) else 6
    if any(term in text for term in ("官网", "联系我们", "投资者关系", "合作", "采购", "招标", "中标")):
        score += 4
    if any(term in text for term in ("访问受限", "待补全", "captcha", "验证后即可继续访问")):
        score -= 10
    return score


def rerank_sources_hybrid(
    sources: Iterable[SourceDocument],
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object] | None = None,
    deps: SourceRankingDependencies,
) -> list[SourceDocument]:
    deduped_sources = deps.dedupe_sources(sources)
    if not deduped_sources:
        return []
    quality_scores: dict[str, int] = {}
    sources_by_url: dict[str, SourceDocument] = {}
    retrieval_candidates: list[TextRetrievalCandidate] = []
    company_anchor_terms = deps.resolved_company_anchor_terms(keyword, research_focus, scope_hints)

    for source in deduped_sources:
        normalized_url = normalize_text(source.url)
        if not normalized_url:
            continue
        sources_by_url[normalized_url] = source
        quality_scores[normalized_url] = source_rerank_score(
            source,
            keyword=keyword,
            research_focus=research_focus,
            scope_hints=scope_hints,
            deps=deps,
        )
        retrieval_candidates.extend(build_source_retrieval_candidates(source))

    retrieval_query = build_search_hit_retrieval_query(keyword, research_focus, scope_hints, deps=deps)
    retrieval_matches = deps.retrieve_text_matches(
        retrieval_candidates,
        retrieval_query,
        limit=max(40, len(retrieval_candidates)),
    )
    retrieval_scores = {
        match.key: match.score
        for match in retrieval_matches
        if match.key in sources_by_url and match.score > 0
    }
    retrieval_ranked = [
        match.key
        for match in retrieval_matches
        if match.key in sources_by_url and match.score > 0
    ]
    quality_ranked = [url for url, score in sorted(quality_scores.items(), key=lambda item: item[1], reverse=True) if score > 0]

    hybrid_scores: dict[str, float] = {}
    for ranked_urls, score_map in (
        (retrieval_ranked, retrieval_scores),
        (quality_ranked, quality_scores),
    ):
        for index, url in enumerate(ranked_urls, start=1):
            hybrid_scores[url] = hybrid_scores.get(url, 0.0) + _rrf_score(index) + float(score_map.get(url, 0)) / 1000.0

    ranked_urls = sorted(
        sources_by_url,
        key=lambda url: (
            hybrid_scores.get(url, 0.0),
            retrieval_scores.get(url, 0.0),
            quality_scores.get(url, 0),
            1 if normalize_text(sources_by_url[url].source_tier) == "official" else 0,
            len(normalize_text(sources_by_url[url].excerpt)),
        ),
        reverse=True,
    )
    ranked: list[SourceDocument] = []
    for url in ranked_urls:
        source = sources_by_url[url]
        if (
            bool((scope_hints or {}).get("prefer_company_entities"))
            and company_anchor_terms
            and not source_matches_company_anchor(source, company_anchor_terms)
        ):
            continue
        if hybrid_scores.get(url, 0.0) <= 0 and quality_scores.get(url, 0) <= 0:
            continue
        ranked.append(source)
    ranked = ranked or [sources_by_url[url] for url in ranked_urls]

    settings = deps.get_settings()
    mutable_scope_hints = scope_hints if isinstance(scope_hints, dict) else {}
    reranker_enabled = bool(
        settings.research_cross_encoder_rerank_enabled
        or mutable_scope_hints.get("enable_cross_encoder_rerank")
        or mutable_scope_hints.get("cross_encoder_rerank")
    )
    if not reranker_enabled:
        return ranked
    reranker_backend = normalize_text(str(mutable_scope_hints.get("runtime_reranker_backend") or settings.research_cross_encoder_backend))
    reranker_top_k = deps.safe_int(
        mutable_scope_hints.get("runtime_reranker_top_k"),
        settings.research_cross_encoder_top_k,
        minimum=1,
        maximum=80,
    )
    reranker_model = normalize_text(str(mutable_scope_hints.get("runtime_reranker_model") or settings.research_cross_encoder_model))
    reranked, profile = deps.rerank_sources_cross_encoder(
        ranked,
        query=retrieval_query,
        model_name=reranker_model,
        top_k=reranker_top_k,
        backend=reranker_backend,
    )
    mutable_scope_hints.update(profile.to_diagnostics_update())
    return list(reranked)


def select_hits_with_source_balance(hits: list[SearchHit], *, limit: int) -> list[SearchHit]:
    selected: list[SearchHit] = []
    seen_urls: set[str] = set()
    official_quota = max(2, round(limit * 0.45))
    aggregate_quota = max(1, round(limit * 0.25))

    def classify_hit_tier(hit: SearchHit) -> str:
        source_type = hit.source_hint or classify_source_type(hit.url)
        domain = extract_domain(hit.url)
        source_label = derive_source_label(
            source_type=source_type,
            domain=domain,
            fallback=getattr(hit, "source_label", None),
        )
        return classify_source_tier(source_type=source_type, domain=domain, source_label=source_label)

    def take_hits(match: Callable[[SearchHit], bool], quota: int) -> None:
        if quota <= 0:
            return
        taken = 0
        for hit in hits:
            if taken >= quota:
                break
            normalized_url = normalize_text(hit.url)
            if not normalized_url or normalized_url in seen_urls or not match(hit):
                continue
            seen_urls.add(normalized_url)
            selected.append(hit)
            taken += 1

    take_hits(lambda hit: classify_hit_tier(hit) == "official", official_quota)
    take_hits(lambda hit: classify_hit_tier(hit) == "aggregate", aggregate_quota)
    take_hits(lambda hit: hit.source_hint == "tech_media_feed", 1)
    take_hits(lambda hit: True, limit - len(selected))
    return selected[:limit]
