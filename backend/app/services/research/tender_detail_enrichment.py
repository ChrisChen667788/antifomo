from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import re
from typing import Any

from app.services.content_extractor import normalize_text
from app.services.research.source_documents import SourceDocument
from app.services.research.web_search import SearchHit


CONFIRMED_TENDER_TERMS = ("招标", "中标", "采购", "采购意向", "成交", "竞争性磋商", "招标文件", "中标候选人")
TENDER_DETAIL_TERMS = ("招标人", "采购人", "中标人", "中标方", "投标人", "招标代理", "项目编号", "技术参数", "招标文件")


@dataclass(frozen=True, slots=True)
class TenderDetailDependencies:
    dedupe_strings: Callable[..., list[str]]
    search_public_web: Callable[..., list[SearchHit]]
    hybrid_rank_hits: Callable[..., list[SearchHit]]
    select_hits_with_source_balance: Callable[..., list[SearchHit]]
    extract_source_document_best_effort: Callable[..., SourceDocument | None]
    filter_recent_sources: Callable[[list[SourceDocument]], list[SourceDocument]]
    emit_research_progress: Callable[..., None]
    build_progress_message: Callable[..., str]
    dedupe_sources: Callable[[list[SourceDocument]], list[SourceDocument]]
    refine_sources_for_report: Callable[..., list[SourceDocument]]
    merge_scope_hints: Callable[[dict[str, object], dict[str, object]], dict[str, object]]
    infer_scope_hints: Callable[[str, str | None, list[SourceDocument]], dict[str, object]]
    build_theme_terms: Callable[[str, str | None, dict[str, object]], list[str]]
    resolved_company_anchor_terms: Callable[[str, str | None, dict[str, object]], list[str]]
    build_source_intelligence: Callable[..., dict[str, list[str]]]


@dataclass(frozen=True, slots=True)
class TenderDetailEnrichmentResult:
    sources: list[SourceDocument]
    effective_query_plan: list[str]
    scope_hints: dict[str, object]
    theme_terms: list[str]
    company_anchor_terms: list[str]
    source_intelligence: dict[str, list[str]]


def source_confirmed_tender_score(source: SourceDocument) -> int:
    text = normalize_text(" ".join([source.title, source.snippet, source.excerpt, source.search_query, source.source_label or ""]))
    if not text:
        return 0
    score = 0
    if source.source_tier == "official":
        score += 28
    if source.source_type in {"procurement", "tender_feed", "official_tender_feed", "regional_public_resource"}:
        score += 24
    score += min(24, sum(6 for term in CONFIRMED_TENDER_TERMS if term in text))
    score += min(24, sum(6 for term in TENDER_DETAIL_TERMS if term in text))
    if re.search(r"(预算|金额|中标价|成交价|最高限价)[^。；;，,\n]{0,36}(万元|亿元|元)", text):
        score += 10
    return min(score, 100)


def confirmed_tender_sources(sources: list[SourceDocument], *, limit: int = 4) -> list[SourceDocument]:
    scored = [
        (score, source)
        for source in sources
        if (score := source_confirmed_tender_score(source)) >= 42
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    return [source for _, source in scored[:limit]]


def tender_project_seed(source: SourceDocument, *, keyword: str, research_focus: str | None) -> str:
    title = normalize_text(source.title)
    title = re.sub(r"[-_｜|].*$", "", title).strip("，,、:：- ")
    title = re.sub(r"(公开招标公告|招标公告|中标成交公告|中标公告|成交公告|采购意向|结果公示)$", "", title)
    if 8 <= len(title) <= 80:
        return title
    text = normalize_text(" ".join([source.snippet, source.excerpt]))
    for pattern in (
        r"([\u4e00-\u9fffA-Za-z0-9（）()《》]{4,60}(?:项目|平台|系统|服务|工程|采购))",
        r"([\u4e00-\u9fffA-Za-z0-9（）()《》]{4,60}(?:招标|中标|成交))",
    ):
        match = re.search(pattern, text)
        if match:
            return normalize_text(match.group(1))[:80]
    return normalize_text(" ".join([keyword, research_focus or ""]))[:80]


def build_tender_detail_query_plan(
    sources: list[SourceDocument],
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
    limit: int = 10,
    deps: TenderDetailDependencies,
) -> list[str]:
    queries: list[str] = []
    regions = [normalize_text(str(item)) for item in scope_hints.get("regions", []) or [] if normalize_text(str(item))]
    industries = [normalize_text(str(item)) for item in scope_hints.get("industries", []) or [] if normalize_text(str(item))]
    clients = [normalize_text(str(item)) for item in scope_hints.get("clients", []) or [] if normalize_text(str(item))]
    scope_tail = normalize_text(" ".join([*(regions[:1]), *(industries[:1]), *(clients[:1])]))
    for source in confirmed_tender_sources(sources):
        seed = tender_project_seed(source, keyword=keyword, research_focus=research_focus)
        if not seed:
            continue
        quoted_seed = f"\"{seed}\"" if len(seed) <= 60 else seed
        queries.extend(
            [
                f"{quoted_seed} 招标人 中标人 投标人 招标代理 项目编号 技术参数",
                f"{quoted_seed} 招标文件 中标候选人 投标报价 评标 采购需求",
                f"site:ccgp.gov.cn {quoted_seed} 招标人 中标人 招标代理",
                f"site:ggzy.gov.cn {quoted_seed} 中标候选人 投标人 技术参数",
                f"site:cecbid.org.cn {quoted_seed} 招标代理 投标人 中标候选人",
            ]
        )
    if scope_tail:
        queries.append(f"{scope_tail} {keyword} 招标人 中标方 投标方 招标代理 招标参数")
    return deps.dedupe_strings(queries, limit)


def collect_tender_detail_sources(
    sources: list[SourceDocument],
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
    timeout_seconds: int,
    result_limit: int,
    selected_limit: int,
    excerpt_chars: int,
    deps: TenderDetailDependencies,
) -> tuple[list[SourceDocument], list[str]]:
    query_plan = build_tender_detail_query_plan(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
        limit=10,
        deps=deps,
    )
    if not query_plan:
        return [], []
    hits: list[SearchHit] = []
    for query in query_plan:
        try:
            hits.extend(
                deps.search_public_web(
                    query,
                    timeout_seconds=max(8, timeout_seconds),
                    limit=max(4, result_limit),
                )
            )
        except Exception:
            continue
    ranked_hits = deps.hybrid_rank_hits(
        hits,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
    )
    selected_hits = deps.select_hits_with_source_balance(ranked_hits, limit=max(3, selected_limit))
    detail_sources = [
        source
        for source in (
            deps.extract_source_document_best_effort(
                hit,
                timeout_seconds=max(8, timeout_seconds),
                excerpt_chars=excerpt_chars,
            )
            for hit in selected_hits
        )
        if source is not None and source_confirmed_tender_score(source) >= 36
    ]
    return deps.filter_recent_sources(detail_sources), query_plan


def apply_tender_detail_enrichment(
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
    effective_query_plan: list[str],
    runtime: dict[str, int | str | bool],
    source_excerpt_chars: int,
    progress_callback: Any | None,
    deps: TenderDetailDependencies,
) -> TenderDetailEnrichmentResult:
    if not confirmed_tender_sources(sources):
        return TenderDetailEnrichmentResult(
            sources=sources,
            effective_query_plan=effective_query_plan,
            scope_hints=scope_hints,
            theme_terms=theme_terms,
            company_anchor_terms=company_anchor_terms,
            source_intelligence=source_intelligence,
        )
    deps.emit_research_progress(
        progress_callback,
        "tender_details",
        78,
        deps.build_progress_message("正在深挖招投标项目明细", keyword=keyword, research_focus=research_focus, mode=research_mode),
    )
    tender_detail_sources, tender_detail_queries = collect_tender_detail_sources(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
        timeout_seconds=int(runtime["search_timeout_seconds"]),
        result_limit=max(4, int(runtime["search_result_limit"])),
        selected_limit=4 if research_mode == "fast" else 7,
        excerpt_chars=source_excerpt_chars,
        deps=deps,
    )
    if tender_detail_sources:
        effective_query_plan = deps.dedupe_strings(
            effective_query_plan + tender_detail_queries,
            max(int(runtime["query_limit"]), int(runtime["expanded_query_limit"])) + 14,
        )
        sources = deps.dedupe_sources([*sources, *tender_detail_sources])
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
        source_intelligence = deps.build_source_intelligence(
            sources,
            keyword=keyword,
            research_focus=research_focus,
            output_language=output_language,
            scope_hints=scope_hints,
        )
    return TenderDetailEnrichmentResult(
        sources=sources,
        effective_query_plan=effective_query_plan,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        company_anchor_terms=company_anchor_terms,
        source_intelligence=source_intelligence,
    )
