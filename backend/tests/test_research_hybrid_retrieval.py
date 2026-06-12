from __future__ import annotations

from collections.abc import Iterable
from types import SimpleNamespace

from app.services.content_extractor import extract_domain, normalize_text
from app.services.research.delivery_enrichment import apply_report_readiness_guardrails
from app.services.research.delivery_materials import (
    DeliveryMaterialsDependencies,
    build_commercial_summary,
    build_review_queue,
    build_technical_appendix,
)
from app.services.research.entity_ranking import (
    EntityRankingHeuristicDependencies,
    build_candidate_profile_support,
    promote_pending_entities_with_candidate_profiles,
)
from app.services.research.report_readiness import (
    ReportReadinessDependencies,
    build_report_readiness,
    is_low_signal_execution_report,
    resolved_report_readiness,
)
from app.services.research.report_row_quality import is_actionable_budget_row, summary_fact_rows
from app.services.research.runtime_config import (
    build_research_runtime,
    build_runtime_strategy_scope_hints,
    runtime_consumer_effective_config,
)
from app.services.research.source_ranking import (
    SourceRankingDependencies,
    classify_source_tier,
    classify_source_type,
    hybrid_rank_hits,
    rerank_sources_hybrid,
)
from app.services.research.source_diagnostics import (
    SourceDiagnosticsDependencies,
    build_source_diagnostics,
)
from app.services.research.source_documents import SourceDocument
from app.services.research.source_query_plans import (
    SourceQueryPlanDependencies,
    build_company_profile_query_plan,
    build_corrective_query_plan,
    build_expanded_query_plan,
    build_query_plan,
)
from app.services.research.tender_detail_enrichment import TenderDetailDependencies, build_tender_detail_query_plan
from app.services.research.web_search import SearchHit
from app.schemas.research import (
    ResearchEntityEvidenceOut,
    ResearchEntityGraphOut,
    ResearchRankedEntityOut,
    ResearchReportDocument,
    ResearchReportRequest,
    ResearchReportSectionOut,
)


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


def _resolve_research_mode(payload: ResearchReportRequest) -> str:
    mode = normalize_text(str(getattr(payload, "research_mode", "") or "")).lower()
    if mode in {"fast", "deep"}:
        return mode
    return "fast" if getattr(payload, "deep_research", None) is False else "deep"


def _safe_int(value: object, default: int, *, minimum: int = 0, maximum: int = 1000) -> int:
    try:
        parsed = int(value if value is not None else default)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _retrieval_quality_band(
    *,
    strict_match_ratio: float,
    official_source_ratio: float,
    unique_domain_count: int,
    normalized_entity_count: int,
) -> str:
    if strict_match_ratio >= 0.7 and official_source_ratio >= 0.3 and unique_domain_count >= 2:
        return "high"
    if strict_match_ratio >= 0.4 or official_source_ratio >= 0.2 or normalized_entity_count:
        return "medium"
    return "low"


def _evidence_mode_from_metrics(
    *,
    retained_source_count: int,
    strict_topic_source_count: int,
    strict_match_ratio: float,
    official_source_ratio: float,
    unique_domain_count: int,
) -> tuple[str, str]:
    if retained_source_count >= 2 and strict_topic_source_count >= 2 and official_source_ratio >= 0.3:
        return "strong", "强证据"
    if strict_match_ratio >= 0.4:
        return "provisional", "候选证据"
    return "fallback", "兜底候选"


def _source_diagnostics_dependencies() -> SourceDiagnosticsDependencies:
    return SourceDiagnosticsDependencies(
        dedupe_strings=_dedupe_strings,
        retrieval_quality_band=_retrieval_quality_band,
        evidence_mode_from_metrics=_evidence_mode_from_metrics,
    )


def _extract_topic_anchor_terms(keyword: str, research_focus: str | None) -> list[str]:
    text = normalize_text(" ".join([keyword, research_focus or ""]))
    terms = [keyword]
    for token in ("AI漫剧", "快手可灵", "政务云", "预算窗口", "采购意向", "南京市数据局"):
        if token in text:
            terms.append(token)
    return _dedupe_strings(terms, 8)


def _build_theme_terms(keyword: str, research_focus: str | None, scope_hints: dict[str, object]) -> list[str]:
    return _dedupe_strings(
        [
            *_extract_topic_anchor_terms(keyword, research_focus),
            *list(scope_hints.get("industries", []) or []),
            *list(scope_hints.get("regions", []) or []),
        ],
        12,
    )


def _resolved_company_anchor_terms(
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object] | None,
) -> list[str]:
    scope = scope_hints or {}
    text = normalize_text(" ".join([keyword, research_focus or ""]))
    terms = [
        *list(scope.get("company_anchors", []) or []),
        *list(scope.get("clients", []) or []),
    ]
    for token in ("快手可灵", "阅文", "中文在线", "南京市数据局"):
        if token in text:
            terms.append(token)
    return _dedupe_strings(terms, 12)


def _source_scope_match_score(
    source: SourceDocument | SearchHit,
    *,
    scope_hints: dict[str, object],
    company_anchor_terms: list[str],
    theme_terms: list[str],
) -> int:
    text = normalize_text(
        " ".join(
            [
                str(getattr(source, "title", "") or ""),
                str(getattr(source, "snippet", "") or ""),
                str(getattr(source, "excerpt", "") or ""),
                str(getattr(source, "search_query", "") or "") if isinstance(source, SearchHit) else "",
                str(getattr(source, "source_label", "") or ""),
                str(getattr(source, "domain", "") or ""),
                str(getattr(source, "url", "") or ""),
            ]
        )
    ).lower()
    company_terms = [normalize_text(item).lower() for item in company_anchor_terms if normalize_text(item)]
    if bool(scope_hints.get("prefer_company_entities")) and company_terms and not any(term in text for term in company_terms):
        return 0
    score = 0
    if any(normalize_text(item).lower() in text for item in theme_terms if normalize_text(item)):
        score += 4
    if any(normalize_text(str(item)).lower() in text for item in scope_hints.get("regions", []) or []):
        score += 4
    if any(normalize_text(str(item)).lower() in text for item in scope_hints.get("industries", []) or []):
        score += 4
    if any(normalize_text(str(item)).lower() in text for item in scope_hints.get("clients", []) or []):
        score += 6
    if any(term in text for term in company_terms):
        score += 8
    source_tier = normalize_text(str(getattr(source, "source_tier", "") or ""))
    if not source_tier:
        url = str(getattr(source, "url", "") or "")
        source_type = str(getattr(source, "source_type", "") or getattr(source, "source_hint", "") or classify_source_type(url))
        source_tier = classify_source_tier(
            source_type=source_type,
            domain=str(getattr(source, "domain", "") or extract_domain(url) or ""),
            source_label=str(getattr(source, "source_label", "") or ""),
        )
    if source_tier == "official" and score > 0:
        score += 2
    return score


class _PassthroughRerankProfile:
    def to_diagnostics_update(self) -> dict[str, object]:
        return {
            "reranker_used": True,
            "reranker_model": "test-local-reranker",
            "reranker_top_k": 1,
            "reranker_backend": "local",
            "reranker_notes": ["test profile"],
        }


def _passthrough_rerank_sources_cross_encoder(
    sources: list[SourceDocument],
    *,
    query: str,
    model_name: str,
    top_k: int = 20,
    backend: str = "auto",
) -> tuple[list[SourceDocument], _PassthroughRerankProfile]:
    return list(sources), _PassthroughRerankProfile()


def _dedupe_hits(hits: list[SearchHit]) -> list[SearchHit]:
    rows: list[SearchHit] = []
    seen: set[str] = set()
    for hit in hits:
        key = normalize_text(hit.url)
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(hit)
    return rows


def _dedupe_sources(sources: list[SourceDocument]) -> list[SourceDocument]:
    rows: list[SourceDocument] = []
    seen: set[str] = set()
    for source in sources:
        key = normalize_text(source.url)
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(source)
    return rows


def _source_ranking_dependencies(
    *,
    rerank_sources_cross_encoder=_passthrough_rerank_sources_cross_encoder,
) -> SourceRankingDependencies:
    settings = SimpleNamespace(
        research_cross_encoder_rerank_enabled=False,
        research_cross_encoder_backend="auto",
        research_cross_encoder_top_k=20,
        research_cross_encoder_model="cross-encoder/ms-marco-MiniLM-L-6-v2",
    )
    return SourceRankingDependencies(
        dedupe_hits=lambda hits: _dedupe_hits(list(hits)),
        dedupe_sources=lambda sources: _dedupe_sources(list(sources)),
        extract_topic_anchor_terms=_extract_topic_anchor_terms,
        build_theme_terms=_build_theme_terms,
        resolved_company_anchor_terms=_resolved_company_anchor_terms,
        source_scope_match_score=_source_scope_match_score,
        get_settings=lambda: settings,
        safe_int=_safe_int,
        rerank_sources_cross_encoder=rerank_sources_cross_encoder,
    )


INDUSTRY_SCOPE_ALIASES = {
    "政务云": ("政务云", "政务", "政府云", "数据局", "电子政务"),
    "AI漫剧": ("AI漫剧", "漫剧", "AI短剧", "AIGC短剧", "AIGC漫剧", "AI动画", "AIGC动画"),
    "医疗": ("医疗", "医院", "卫健", "医共体", "医保", "AI影像"),
    "文旅": ("文旅", "景区", "旅游", "数字人导览", "AIGC"),
}


REGION_SCOPE_ALIASES = {
    "江苏": ("南京", "苏州", "无锡"),
    "上海": ("上海市", "浦东", "徐汇"),
    "华东": ("上海", "江苏", "浙江"),
}


THEME_QUERY_EXPANSION_TEMPLATES = {
    "AI漫剧": (
        "{keyword} AIGC动画 短剧 平台 商业化",
        "{keyword} 漫剧 IP 内容平台 合作 发行",
    ),
    "政务云": (
        "{keyword} 数据局 政务云 一体化 招标 预算",
        "site:gov.cn {keyword} 数据局 政务云 规划",
    ),
}


RESEARCH_SOURCE_SITE_QUERIES = (
    ("official_policy", "site:gov.cn {keyword} 领导 讲话 规划 战略"),
    ("public_procurement", "site:ccgp.gov.cn {keyword} 招标 中标 预算"),
    ("public_resource", "site:ggzy.gov.cn {keyword} 招标 中标 项目"),
)


THEME_OFFICIAL_QUERY_TEMPLATES = {
    "AI漫剧": (
        "site:kuaishou.com {keyword} 短剧 AIGC 内容 平台",
        "site:yuewen.com {keyword} IP 动漫 短剧 合作",
    ),
    "政务云": (
        "site:aliyun.com {keyword} 政务云 政务 合作",
        "site:huawei.com {keyword} 政务云 行业 数字政府",
    ),
}


def _strip_query_noise(value: str) -> str:
    return normalize_text(value)


def _sanitize_research_focus_text(value: str | None) -> str:
    return normalize_text(value or "")


def _expand_region_scope_terms(regions: list[str]) -> list[str]:
    expanded: list[str] = []
    for region in regions:
        normalized = normalize_text(region)
        if not normalized:
            continue
        expanded.append(normalized)
        expanded.extend(REGION_SCOPE_ALIASES.get(normalized, ()))
    return _dedupe_strings(expanded, 24)


def _collect_theme_seed_companies(
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
) -> list[str]:
    text = normalize_text(" ".join([keyword, research_focus or "", *map(str, scope_hints.get("industries", []) or [])]))
    candidates: list[str] = []
    if "AI漫剧" in text or "漫剧" in text:
        candidates.extend(["快手可灵", "阅文集团", "中文在线"])
    if "政务云" in text or "数据局" in text:
        candidates.extend(["阿里云", "华为云", "腾讯云"])
    return _dedupe_strings(candidates, 8)


def _is_plausible_entity_name(value: str) -> bool:
    normalized = normalize_text(value)
    return bool(normalized and len(normalized) >= 2 and not any(char in normalized for char in "，,。；;"))


def _source_query_plan_dependencies() -> SourceQueryPlanDependencies:
    return SourceQueryPlanDependencies(
        strip_query_noise=_strip_query_noise,
        sanitize_research_focus_text=_sanitize_research_focus_text,
        extract_topic_anchor_terms=_extract_topic_anchor_terms,
        expand_region_scope_terms=_expand_region_scope_terms,
        dedupe_strings=_dedupe_strings,
        collect_theme_seed_companies=_collect_theme_seed_companies,
        is_plausible_entity_name=_is_plausible_entity_name,
        industry_scope_aliases=INDUSTRY_SCOPE_ALIASES,
        theme_query_expansion_templates=THEME_QUERY_EXPANSION_TEMPLATES,
        research_source_site_queries=RESEARCH_SOURCE_SITE_QUERIES,
        theme_official_query_templates=THEME_OFFICIAL_QUERY_TEMPLATES,
    )


def _tender_detail_dependencies() -> TenderDetailDependencies:
    return TenderDetailDependencies(
        dedupe_strings=_dedupe_strings,
        search_public_web=lambda *args, **kwargs: [],
        hybrid_rank_hits=lambda hits, *args, **kwargs: list(hits),
        select_hits_with_source_balance=lambda hits, *, limit: list(hits)[:limit],
        extract_source_document_best_effort=lambda *args, **kwargs: None,
        filter_recent_sources=lambda sources: list(sources),
        emit_research_progress=lambda *args, **kwargs: None,
        build_progress_message=lambda *args, **kwargs: "",
        dedupe_sources=_dedupe_sources,
        refine_sources_for_report=lambda sources, *args, **kwargs: list(sources),
        merge_scope_hints=lambda base, updates: {**base, **updates},
        infer_scope_hints=lambda *args, **kwargs: {},
        build_theme_terms=_build_theme_terms,
        resolved_company_anchor_terms=_resolved_company_anchor_terms,
        build_source_intelligence=lambda *args, **kwargs: {},
    )


def _infer_input_scope_hints(keyword: str, research_focus: str | None) -> dict[str, object]:
    text = normalize_text(" ".join([keyword, research_focus or ""]))
    hints: dict[str, object] = {
        "anchor_text": normalize_text(" ".join([keyword, research_focus or ""])),
        "regions": [],
        "industries": [],
        "clients": [],
        "strategy_query_expansions": [],
        "industry_methodology_questions": [],
    }
    if "上海" in text:
        hints["regions"] = ["上海"]
    if any(token in text for token in ("医疗", "医院", "卫健", "AI影像", "AI 影像")):
        hints["industries"] = ["医疗"]
        hints["clients"] = ["三甲医院"] if "三甲" in text else []
        hints.update(
            {
                "industry_methodology_profile": "医疗",
                "industry_methodology_framework": "临床场景 -> 信息科与医务线 -> 合规安全 -> 系统集成 -> 投入产出",
                "industry_methodology_questions": [
                    "需求来自临床、医务、运营还是科研教学场景",
                    "信息科、医务处、设备处、财务处和采购办的分工如何",
                    "试点科室、医院集团复制和区域医共体扩展节奏如何",
                ],
                "strategy_query_expansions": [
                    "上海 医院 AI影像 信息化 建设 采购 预算",
                    "上海 卫健 AI影像 试点 示范 预算",
                    '"三甲医院" AI影像 信息科 医务处 招标',
                ],
                "industry_methodology_source_preferences": ["医院官网", "卫健委官网", "招采公告"],
            }
        )
    return hints


def _source_text(source: SourceDocument) -> str:
    return normalize_text(
        " ".join(
            [
                source.title,
                source.snippet,
                source.excerpt,
                source.search_query,
                source.source_label or "",
                source.domain or "",
                source.url,
            ]
        )
    )


def _entity_canonical_key(name: str) -> str:
    return normalize_text(name).lower().replace(" ", "")


def _extract_rank_entity_name(value: str) -> str:
    return normalize_text(value)


def _org_entity_variants(value: str) -> list[str]:
    normalized = normalize_text(value)
    variants = [normalized]
    if normalized == "快手可灵":
        variants.extend(["快手", "Kling AI", "Kuaishou", "kling-ai"])
    return _dedupe_strings(variants, 8)


def _source_mentions_entity(source: SourceDocument, entity_name: str) -> bool:
    text = _source_text(source).lower()
    return any(normalize_text(variant).lower() in text for variant in _org_entity_variants(entity_name))


def _source_negates_entity(source: SourceDocument, entity_name: str) -> bool:
    normalized_name = normalize_text(entity_name)
    if not normalized_name:
        return False
    return any(
        normalized_name in sentence and any(token in sentence for token in ("未提及", "未覆盖", "不涉及"))
        for sentence in _source_text(source).split("。")
    )


def _build_entity_evidence(source: SourceDocument) -> ResearchEntityEvidenceOut:
    return ResearchEntityEvidenceOut(
        title=source.title,
        url=source.url,
        source_label=source.source_label,
        source_tier=source.source_tier if source.source_tier in {"official", "media", "aggregate"} else "media",
        excerpt=normalize_text(source.excerpt or source.snippet),
    )


def _entity_ranking_dependencies() -> EntityRankingHeuristicDependencies:
    return EntityRankingHeuristicDependencies(
        clean_scope_entity_names=lambda *args, **kwargs: [],
        entity_graph_lookup=lambda graph: {},
        is_theme_aligned_entity_name=lambda *args, **kwargs: True,
        is_company_like_entity_name=lambda *args, **kwargs: True,
        source_text=_source_text,
        extract_rank_entity_candidates=lambda *args, **kwargs: [],
        canonical_org_name_from_domain=lambda domain: "",
        dedupe_strings=_dedupe_strings,
        resolve_known_org_name=lambda value, *args, **kwargs: normalize_text(value),
        source_type_weight=lambda source: 30 if source.source_tier == "official" else 10,
        build_entity_evidence=_build_entity_evidence,
        entity_canonical_key=_entity_canonical_key,
        extract_rank_entity_name=_extract_rank_entity_name,
        extract_org_candidates=lambda *args, **kwargs: [],
        is_plausible_entity_name=_is_plausible_entity_name,
        is_lightweight_entity_name=lambda value: bool(normalize_text(value)),
        org_entity_variants=_org_entity_variants,
        source_mentions_entity=_source_mentions_entity,
        source_negates_entity=_source_negates_entity,
        known_company_public_source_seeds={
            "快手可灵": (("https://www.kuaishou.com/brand/kling-ai", "快手官网"),),
        },
        company_profile_page_tokens=("官网", "官方", "公开入口", "official", "profile", "company", "business", "brand"),
        theme_entity_allow_tokens={},
        generic_company_name_tokens=(),
        theme_role_archetypes={},
        partner_connector_aliases=(),
    )


def _sanitize_entity_row(field_key: str, value: str) -> str:
    return normalize_text(value)


def _report_readiness_dependencies() -> ReportReadinessDependencies:
    return ReportReadinessDependencies(
        dedupe_strings=_dedupe_strings,
        sanitize_entity_row=_sanitize_entity_row,
        is_actionable_budget_row=is_actionable_budget_row,
    )


def _theme_labels_from_scope(
    scope_hints: dict[str, object],
    *,
    keyword: str,
    research_focus: str | None,
) -> list[str]:
    text = normalize_text(" ".join([keyword, research_focus or ""]))
    labels = [normalize_text(str(item)) for item in scope_hints.get("industries", []) or [] if normalize_text(str(item))]
    if "漫剧" in text:
        labels.append("AI漫剧")
    if "政务云" in text:
        labels.append("政务云")
    if any(token in text for token in ("医疗", "医院", "AI影像")):
        labels.append("医疗")
    return _dedupe_strings(labels, 4)


def _entity_names_from_ranked(
    ranked: list[ResearchRankedEntityOut],
    fallback_rows: list[str],
    *,
    limit: int = 3,
) -> list[str]:
    names: list[str] = []
    for item in ranked:
        names.append(normalize_text(getattr(item, "name", "")))
    names.extend(normalize_text(row) for row in fallback_rows)
    return _dedupe_strings(names, limit)


def _entity_display_labels(values: Iterable[str], *, limit: int = 2) -> list[str]:
    return _dedupe_strings(values, limit)


def _derive_entry_window(report: ResearchReportDocument, output_language: str) -> str:
    return normalize_text((report.tender_timeline or report.strategic_directions or ["近期预算窗口"])[0])


def _truncate_sentence(value: str, limit: int) -> str:
    text = normalize_text(value)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip(' ，,：:；;、')}…"


def _delivery_materials_dependencies() -> DeliveryMaterialsDependencies:
    return DeliveryMaterialsDependencies(
        dedupe_strings=_dedupe_strings,
        theme_labels_from_scope=_theme_labels_from_scope,
        entity_names_from_ranked=_entity_names_from_ranked,
        looks_like_scope_prompt_noise=lambda value: False,
        looks_like_placeholder_entity_name=lambda value: False,
        looks_like_fragment_entity_name=lambda value: False,
        contains_low_value_entity_token=lambda value: False,
        is_trustworthy_scope_client_name=lambda *args, **kwargs: True,
        is_theme_aligned_entity_name=lambda *args, **kwargs: True,
        is_lightweight_entity_name=lambda value: bool(normalize_text(value)),
        entity_display_labels=_entity_display_labels,
        is_actionable_budget_row=is_actionable_budget_row,
        summary_fact_rows=summary_fact_rows,
        derive_entry_window=_derive_entry_window,
        truncate_sentence=_truncate_sentence,
        is_useful_public_contact_row=lambda value: bool(normalize_text(value)),
        looks_like_placeholder_contact_row=lambda value: False,
        looks_like_source_artifact_text=lambda value: False,
        resolved_report_readiness=lambda report: resolved_report_readiness(report, deps=_report_readiness_dependencies()),
        is_low_signal_execution_report=lambda report: is_low_signal_execution_report(
            report,
            deps=_report_readiness_dependencies(),
        ),
        field_row_noise_tokens=(),
    )


def test_hybrid_rank_prefers_company_official_hits_for_company_intent() -> None:
    keyword = "AI漫剧头部公司"
    research_focus = "分析快手可灵、阅文、中文在线这些公司的AI商机、合作平台与商业化路径"
    scope_hints = {
        "industries": ["AI漫剧"],
        "prefer_company_entities": True,
        "company_anchors": ["快手可灵", "阅文", "中文在线"],
    }
    hits = [
        SearchHit(
            title="广州大学 AIGC 研究中心年度论坛",
            url="https://news.gzhu.edu.cn/aigc-forum",
            snippet="AIGC 动画、教学与研究活动。",
            search_query=keyword,
            source_hint="web",
        ),
        SearchHit(
            title="快手可灵 内容平台与 AI 漫剧合作",
            url="https://www.kuaishou.com/brand/kling-ai-comic",
            snippet="快手可灵开放 AIGC 漫剧内容平台、合作与商业化入口。",
            search_query=keyword,
            source_hint="web",
            source_label="官网",
        ),
        SearchHit(
            title="AI漫剧行业趋势观察",
            url="https://36kr.com/p/ai-comic-market",
            snippet="行业趋势与多家公司布局概览。",
            search_query=keyword,
            source_hint="web",
            source_label="36氪",
        ),
    ]

    ranked = hybrid_rank_hits(
        hits,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
        deps=_source_ranking_dependencies(),
    )

    assert ranked
    assert ranked[0].url == "https://www.kuaishou.com/brand/kling-ai-comic"
    assert all("广州大学" not in hit.title for hit in ranked[:2])


def test_hybrid_rank_does_not_promote_search_query_only_overlap_noise() -> None:
    keyword = "政务云预算窗口"
    research_focus = "梳理江苏重点甲方、采购意向和预算路径"
    scope_hints = {
        "regions": ["江苏"],
        "industries": ["政务云"],
        "clients": ["南京市数据局"],
    }
    hits = [
        SearchHit(
            title="某高校论坛圆桌回顾",
            url="https://news.example.edu.cn/forum-roundtable",
            snippet="围绕 AI 教学、论坛活动和研究分享。",
            search_query='site:gov.cn "南京市数据局" 政务云预算窗口 规划 预算',
            source_hint="web",
        ),
        SearchHit(
            title="南京市数据局电子政务云平台采购意向公告",
            url="https://www.nanjing.gov.cn/data/procurement-intent",
            snippet="公告披露电子政务云平台采购意向、预算安排与项目建设路径。",
            search_query='site:ccgp.gov.cn "南京市数据局" 政务云预算窗口 采购意向 中标',
            source_hint="policy",
            source_label="中国政府网政策/讲话",
        ),
    ]

    ranked = hybrid_rank_hits(
        hits,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
        deps=_source_ranking_dependencies(),
    )

    assert ranked
    assert ranked[0].url == "https://www.nanjing.gov.cn/data/procurement-intent"
    assert all("论坛" not in hit.title for hit in ranked[:1])


def test_source_rerank_prefers_official_browser_extracted_sources() -> None:
    keyword = "AI漫剧头部公司"
    research_focus = "分析快手可灵、阅文、中文在线这些公司的AI商机"
    scope_hints = {
        "industries": ["AI漫剧"],
        "prefer_company_entities": True,
        "company_anchors": ["快手可灵"],
    }
    sources = [
        SourceDocument(
            title="AI漫剧行业趋势",
            url="https://36kr.com/p/ai-comic-market",
            domain="36kr.com",
            snippet="行业趋势综述",
            search_query=keyword,
            source_type="web",
            content_status="snippet_only",
            excerpt="AI漫剧市场趋势与行业观察。",
            source_label="36氪",
            source_tier="media",
            source_origin="search",
        ),
        SourceDocument(
            title="快手可灵 AI 漫剧合作平台",
            url="https://www.kuaishou.com/brand/kling-ai-comic",
            domain="www.kuaishou.com",
            snippet="官方合作平台介绍",
            search_query=keyword,
            source_type="web",
            content_status="browser_extracted",
            excerpt="快手可灵面向AI漫剧内容合作提供开放平台、商业化能力、合作入口与团队信息。",
            source_label="官网",
            source_tier="official",
            source_origin="search",
        ),
    ]

    ranked = rerank_sources_hybrid(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
        deps=_source_ranking_dependencies(),
    )

    assert ranked[0].url == "https://www.kuaishou.com/brand/kling-ai-comic"
    assert ranked[0].content_status == "browser_extracted"


def test_source_rerank_does_not_promote_query_only_overlap_noise() -> None:
    keyword = "政务云预算窗口"
    research_focus = "梳理江苏重点甲方、采购意向和预算路径"
    scope_hints = {
        "regions": ["江苏"],
        "industries": ["政务云"],
        "clients": ["南京市数据局"],
    }
    sources = [
        SourceDocument(
            title="某高校数字化论坛纪要",
            url="https://news.example.edu.cn/forum-roundtable",
            domain="news.example.edu.cn",
            snippet="论坛讨论 AI 教学、数字化趋势和经验分享。",
            search_query='site:gov.cn "南京市数据局" 政务云预算窗口 规划 预算',
            source_type="web",
            content_status="body_acquired",
            excerpt="内容主要围绕高校数字化论坛与教学案例，并未涉及南京市数据局采购意向。",
            source_label="互联网公开网页",
            source_tier="media",
            source_origin="search",
        ),
        SourceDocument(
            title="南京市数据局电子政务云平台采购意向公告",
            url="https://www.nanjing.gov.cn/data/procurement-intent",
            domain="www.nanjing.gov.cn",
            snippet="公告披露电子政务云平台采购意向、预算安排与项目建设路径。",
            search_query='site:ccgp.gov.cn "南京市数据局" 政务云预算窗口 采购意向 中标',
            source_type="policy",
            content_status="browser_extracted",
            excerpt="公告明确电子政务云平台采购意向、预算安排和后续项目建设路径。",
            source_label="中国政府网政策/讲话",
            source_tier="official",
            source_origin="search",
        ),
    ]

    ranked = rerank_sources_hybrid(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
        deps=_source_ranking_dependencies(),
    )

    assert ranked
    assert ranked[0].url == "https://www.nanjing.gov.cn/data/procurement-intent"
    assert "论坛" not in ranked[0].title


def test_cross_encoder_style_reranker_is_feature_flagged_and_records_scope_diagnostics() -> None:
    keyword = "南京市数据局 政务云 预算"
    research_focus = "核验采购意向、预算窗口和官方来源"
    scope_hints = {
        "regions": ["江苏"],
        "industries": ["政务云"],
        "clients": ["南京市数据局"],
        "enable_cross_encoder_rerank": True,
    }
    sources = [
        SourceDocument(
            title="政务云预算行业观察",
            url="https://media.example.cn/gov-cloud-opinion",
            domain="media.example.cn",
            snippet="泛行业观点，提到政务云预算。",
            search_query=keyword,
            source_type="web",
            content_status="snippet_only",
            excerpt="泛行业观点，缺少南京市数据局采购意向原文。",
            source_label="行业媒体",
            source_tier="media",
            source_origin="search",
        ),
        SourceDocument(
            title="南京市数据局电子政务云采购意向公告",
            url="https://www.nanjing.gov.cn/data/procurement-intent",
            domain="www.nanjing.gov.cn",
            snippet="官方公告披露采购意向、预算安排和后续项目建设路径。",
            search_query=keyword,
            source_type="policy",
            content_status="browser_extracted",
            excerpt="南京市数据局电子政务云采购意向公告披露预算安排、采购意向、项目建设路径和后续方案比选窗口。",
            source_label="官网",
            source_tier="official",
            source_origin="search",
        ),
    ]

    ranked = rerank_sources_hybrid(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
        deps=_source_ranking_dependencies(),
    )

    assert ranked[0].url == "https://www.nanjing.gov.cn/data/procurement-intent"
    assert scope_hints["reranker_used"] is True
    assert scope_hints["reranker_model"]
    assert scope_hints["reranker_top_k"] >= 1
    assert scope_hints["reranker_notes"]


def test_runtime_strategy_config_feeds_query_and_reranker_scope_hints() -> None:
    payload = ResearchReportRequest(
        keyword="南京市数据局 政务云",
        research_focus="核验采购意向、预算窗口和官方来源",
        runtime_strategy_config={
            "query_generation": {
                "status": "ready",
                "applied_lanes": ["query_recovery"],
                "fallback_lanes": [],
                "warnings": [],
                "effective_config": {
                    "enabled": True,
                    "query_recovery_enabled": True,
                    "public_expansion_on_watch": True,
                    "corrective_query_limit": 7,
                },
            },
            "source_reranker": {
                "status": "ready",
                "applied_lanes": ["reranker_official_recall"],
                "fallback_lanes": [],
                "warnings": [],
                "effective_config": {
                    "enabled": True,
                    "reranker_adapter": "sentence_transformers_cross_encoder",
                    "official_source_bias": True,
                    "recall_at_k": 7,
                    "fallback_adapter": "local_rrf",
                },
            },
        },
    )

    runtime = build_research_runtime(
        payload,
        resolve_research_mode=_resolve_research_mode,
        runtime_consumer_effective_config=runtime_consumer_effective_config,
        safe_int=_safe_int,
    )
    hints = build_runtime_strategy_scope_hints(
        payload,
        dedupe_strings=_dedupe_strings,
        safe_int=_safe_int,
    )

    assert runtime["runtime_query_recovery_enabled"] is True
    assert runtime["corrective_query_limit"] == 7
    assert hints["runtime_strategy_status"] == "ready"
    assert hints["runtime_query_recovery_enabled"] is True
    assert hints["runtime_source_reranker_enabled"] is True
    assert hints["enable_cross_encoder_rerank"] is True
    assert hints["runtime_reranker_backend"] == "sentence_transformers"
    assert hints["runtime_reranker_top_k"] == 7

    captured: dict[str, object] = {}

    class _FakeRerankProfile:
        def to_diagnostics_update(self) -> dict[str, object]:
            return {
                "reranker_used": True,
                "reranker_model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
                "reranker_top_k": 7,
                "reranker_backend": "sentence-transformers",
                "reranker_notes": ["runtime strategy test"],
            }

    def _fake_rerank(sources, *, query, model_name, top_k=20, backend="auto"):
        captured.update({"top_k": top_k, "backend": backend})
        return list(sources), _FakeRerankProfile()

    scope_hints = {
        "enable_cross_encoder_rerank": True,
        "runtime_reranker_backend": "sentence_transformers",
        "runtime_reranker_top_k": 7,
    }
    rerank_sources_hybrid(
        [
            SourceDocument(
                title="南京市数据局电子政务云采购意向公告",
                url="https://www.nanjing.gov.cn/data/procurement-intent",
                domain="www.nanjing.gov.cn",
                snippet="官方公告披露采购意向、预算安排和后续项目建设路径。",
                search_query=payload.keyword,
                source_type="policy",
                content_status="browser_extracted",
                excerpt="南京市数据局电子政务云采购意向公告披露预算安排、采购意向和项目建设路径。",
                source_label="官网",
                source_tier="official",
                source_origin="search",
            )
        ],
        keyword=payload.keyword,
        research_focus=payload.research_focus,
        scope_hints=scope_hints,
        deps=_source_ranking_dependencies(rerank_sources_cross_encoder=_fake_rerank),
    )

    assert captured == {"top_k": 7, "backend": "sentence_transformers"}


def test_source_diagnostics_exposes_fetch_clean_analyze_pipeline() -> None:
    sources = [
        SourceDocument(
            title="快手可灵 AI 漫剧合作平台",
            url="https://www.kuaishou.com/brand/kling-ai-comic",
            domain="www.kuaishou.com",
            snippet="官方合作平台介绍",
            search_query="AI漫剧头部公司",
            source_type="web",
            content_status="browser_extracted",
            excerpt="快手可灵开放 AIGC 漫剧平台与合作入口。",
            source_label="官网",
            source_tier="official",
            source_origin="search",
        ),
        SourceDocument(
            title="AI漫剧行业趋势观察",
            url="https://36kr.com/p/ai-comic-market",
            domain="36kr.com",
            snippet="行业趋势综述",
            search_query="AI漫剧头部公司",
            source_type="web",
            content_status="body_acquired",
            excerpt="行业趋势与多家公司布局。",
            source_label="36氪",
            source_tier="media",
            source_origin="adapter",
        ),
    ]

    diagnostics = build_source_diagnostics(
        sources,
        enabled_source_labels=["官网", "36氪"],
        scope_hints={"industries": ["AI漫剧"], "clients": ["快手可灵"]},
        recency_window_years=7,
        filtered_old_source_count=1,
        filtered_region_conflict_count=1,
        retained_source_count=2,
        strict_topic_source_count=2,
        topic_anchor_terms=["AI漫剧", "快手可灵"],
        matched_theme_labels=["AI漫剧"],
        entity_graph=ResearchEntityGraphOut(),
        expansion_triggered=False,
        corrective_triggered=True,
        candidate_profile_companies=["快手可灵"],
        candidate_profile_hit_count=2,
        candidate_profile_official_hit_count=1,
        candidate_profile_source_labels=["官网"],
        deps=_source_diagnostics_dependencies(),
    )

    assert diagnostics.pipeline_stages[0].key == "fetch"
    assert diagnostics.pipeline_stages[0].value == 2
    assert diagnostics.pipeline_stages[1].key == "clean"
    assert diagnostics.pipeline_stages[1].value == 2
    assert diagnostics.pipeline_stages[2].key == "analyze"
    assert "官方源占比" in diagnostics.pipeline_stages[2].summary
    assert "保留 2 条可用来源" in diagnostics.pipeline_summary


def test_company_profile_query_plan_adds_official_profile_queries() -> None:
    queries = build_company_profile_query_plan(
        ["阅文集团"],
        keyword="AI漫剧头部公司",
        research_focus="分析商业化路径与合作窗口",
        limit=12,
        deps=_source_query_plan_dependencies(),
    )

    assert any("关于我们" in query for query in queries)
    assert any("公司简介" in query for query in queries)
    assert any("投资者关系" in query for query in queries)


def test_query_plan_adds_scoped_official_queries_for_narrow_buyer_scope() -> None:
    scope_hints = {
        "regions": ["江苏"],
        "industries": ["政务云"],
        "clients": ["南京市数据局"],
    }

    queries = build_query_plan(
        "政务云预算窗口",
        "梳理重点甲方、预算窗口和采购路径",
        False,
        scope_hints=scope_hints,
        preferred_wechat_accounts=None,
        limit=24,
        deps=_source_query_plan_dependencies(),
    )

    assert any('site:gov.cn 江苏 政务云 政务云预算窗口 规划 预算 战略' == query for query in queries)
    assert any('site:ggzy.gov.cn "南京市数据局" 政务云预算窗口 招标 项目' == query for query in queries)
    assert any('site:ccgp.gov.cn "南京市数据局" 政务云预算窗口 采购意向 中标' == query for query in queries)


def test_expanded_and_corrective_query_plans_add_scoped_official_queries() -> None:
    scope_hints = {
        "regions": ["江苏"],
        "industries": ["政务云"],
        "clients": ["南京市数据局"],
    }

    expanded_queries = build_expanded_query_plan(
        "政务云预算窗口",
        "梳理重点甲方、预算窗口和采购路径",
        scope_hints=scope_hints,
        include_wechat=False,
        preferred_wechat_accounts=None,
        limit=24,
        deps=_source_query_plan_dependencies(),
    )
    corrective_queries = build_corrective_query_plan(
        keyword="政务云预算窗口",
        research_focus="梳理重点甲方、预算窗口和采购路径",
        scope_hints=scope_hints,
        include_wechat=False,
        preferred_wechat_accounts=None,
        limit=24,
        deps=_source_query_plan_dependencies(),
    )

    assert any('site:gov.cn 江苏 "南京市数据局" 规划 战略' == query for query in expanded_queries)
    assert any('site:ggzy.gov.cn 江苏 政务云 政务云预算窗口 招标 项目 中标' == query for query in expanded_queries)
    assert any('site:gov.cn "南京市数据局" 政务云预算窗口 规划 预算' == query for query in corrective_queries)
    assert any('site:ccgp.gov.cn 江苏 政务云 政务云预算窗口 采购意向 招标 中标' == query for query in corrective_queries)


def test_tender_detail_query_plan_targets_confirmed_project_fields() -> None:
    source = SourceDocument(
        title="某市智慧文旅AIGC导览平台公开招标公告",
        url="https://ggzy.example.gov.cn/tender/aigc-tourism",
        domain="ggzy.example.gov.cn",
        snippet="采购人：某文旅集团，预算金额 680万元，建设数字人导览、接口API、等保二级。",
        search_query="文旅AIGC平台 招标",
        source_type="procurement",
        content_status="fetched",
        excerpt="招标代理：某招标代理公司；投标人需提供大模型相关软件著作权证书。",
        source_label="公共资源交易平台",
        source_tier="official",
    )

    queries = build_tender_detail_query_plan(
        [source],
        keyword="文旅AIGC平台",
        research_focus="景区数字人导览",
        scope_hints={"regions": ["华东"], "industries": ["文旅"], "clients": ["某文旅集团"]},
        limit=8,
        deps=_tender_detail_dependencies(),
    )

    assert queries
    assert any("招标人" in query and "投标人" in query and "招标代理" in query for query in queries)
    assert any("site:ggzy.gov.cn" in query for query in queries)


def test_query_plans_include_curated_wechat_accounts_when_enabled() -> None:
    preferred_accounts = ("云技术", "智能超参数")

    queries = build_query_plan(
        "算力大模型商机",
        "关注采购路径和生态伙伴",
        True,
        scope_hints={},
        preferred_wechat_accounts=preferred_accounts,
        limit=24,
        deps=_source_query_plan_dependencies(),
    )
    expanded_queries = build_expanded_query_plan(
        "算力大模型商机",
        "关注采购路径和生态伙伴",
        scope_hints={},
        include_wechat=True,
        preferred_wechat_accounts=preferred_accounts,
        limit=24,
        deps=_source_query_plan_dependencies(),
    )
    corrective_queries = build_corrective_query_plan(
        keyword="算力大模型商机",
        research_focus="关注采购路径和生态伙伴",
        scope_hints={},
        include_wechat=True,
        preferred_wechat_accounts=preferred_accounts,
        limit=24,
        deps=_source_query_plan_dependencies(),
    )

    assert any('site:mp.weixin.qq.com "云技术"' in query and "算力大模型" in query for query in queries)
    assert any('site:mp.weixin.qq.com "智能超参数"' in query and "算力大模型" in query for query in expanded_queries)
    assert any('site:mp.weixin.qq.com "云技术"' in query and "算力大模型" in query for query in corrective_queries)


def test_scope_hints_attach_industry_methodology_profile_for_medical_topics() -> None:
    scope_hints = _infer_input_scope_hints(
        "上海医疗 AI 影像商机",
        "关注三甲医院信息科、医务处、预算批次和试点扩面",
    )

    assert scope_hints["industry_methodology_profile"] == "医疗"
    assert "临床场景 -> 信息科与医务线 -> 合规安全 -> 系统集成 -> 投入产出" in scope_hints["industry_methodology_framework"]
    assert any("医院" in query and "信息化" in query for query in scope_hints["strategy_query_expansions"])
    assert any("信息科" in item for item in scope_hints["industry_methodology_questions"])


def test_query_plan_prioritizes_industry_methodology_expansions() -> None:
    scope_hints = _infer_input_scope_hints(
        "上海医疗 AI 影像商机",
        "关注三甲医院信息科、医务处、预算批次和试点扩面",
    )

    queries = build_query_plan(
        "上海医疗 AI 影像商机",
        "关注三甲医院信息科、医务处、预算批次和试点扩面",
        False,
        scope_hints=scope_hints,
        limit=12,
        preferred_wechat_accounts=None,
        deps=_source_query_plan_dependencies(),
    )

    assert any("医院" in query and "采购" in query for query in queries[:8])
    assert any("卫健" in query or "信息科" in query for query in queries[:10])


def test_candidate_profile_support_promotes_entity_from_official_profile_query() -> None:
    profile_sources = [
        SourceDocument(
            title="Kling AI | Kuaishou",
            url="https://www.kuaishou.com/brand/kling-ai",
            domain="www.kuaishou.com",
            snippet="Official creator platform and business profile.",
            search_query="AI漫剧头部公司 快手可灵 官方公开入口",
            source_type="web",
            content_status="browser_extracted",
            excerpt="Kling AI is an official creative platform for video and comic generation.",
            source_label="快手官网",
            source_tier="official",
            source_origin="search",
        )
    ]
    pending = [
        ResearchRankedEntityOut(
            name="快手可灵",
            score=38,
            reasoning="待补证候选",
            entity_mode="pending",
        )
    ]

    support = build_candidate_profile_support(
        profile_sources,
        ["快手可灵"],
        deps=_entity_ranking_dependencies(),
    )
    promoted, remaining = promote_pending_entities_with_candidate_profiles(
        [],
        pending,
        candidate_profile_support=support,
        limit=3,
    )

    assert support["快手可灵"]["hit_count"] == 1
    assert support["快手可灵"]["official_hit_count"] == 1
    assert len(promoted) == 1
    assert promoted[0].name == "快手可灵"
    assert promoted[0].entity_mode == "instance"
    assert remaining == []


def test_report_readiness_and_commercial_summary_enforce_business_slots() -> None:
    report = ResearchReportDocument(
        keyword="AI漫剧头部公司",
        research_focus="分析头部公司的商业化路径、预算窗口与合作机会",
        output_language="zh-CN",
        research_mode="deep",
        report_title="AI漫剧头部公司商业化研判",
        executive_summary="优先围绕快手可灵和阅文集团推进预算与平台合作切入。",
        consulting_angle="先锁定头部平台和内容方，再围绕预算、入口和伙伴关系收敛销售路径。",
        sections=[
            ResearchReportSectionOut(
                title="重点甲方",
                items=["快手可灵", "阅文集团"],
                evidence_density="high",
                source_quality="high",
                official_source_ratio=0.5,
                evidence_count=2,
                evidence_quota=2,
                meets_evidence_quota=True,
            ),
            ResearchReportSectionOut(
                title="预算与投资信号",
                items=["2026 年内容平台合作预算已释放", "未来两个季度是首轮签约窗口"],
                evidence_density="medium",
                source_quality="high",
                official_source_ratio=0.4,
                evidence_count=2,
                evidence_quota=2,
                meets_evidence_quota=True,
            ),
            ResearchReportSectionOut(
                title="公开业务联系方式",
                items=["官网商务合作入口", "公开 BD 邮箱"],
                evidence_density="medium",
                source_quality="medium",
                official_source_ratio=0.5,
                evidence_count=2,
                evidence_quota=1,
                meets_evidence_quota=True,
            ),
            ResearchReportSectionOut(
                title="竞争分析",
                items=["公开线索对竞品进入窗口存在分歧，需继续核验。"],
                evidence_density="low",
                source_quality="medium",
                confidence_tone="conflict",
                contradiction_detected=True,
                contradiction_note="两类来源对竞品推进节奏表述相互矛盾。",
                official_source_ratio=0.0,
                evidence_count=1,
                evidence_quota=2,
                meets_evidence_quota=False,
            ),
        ],
        target_accounts=["快手可灵", "阅文集团"],
        top_target_accounts=[
            {
                "name": "快手可灵",
                "score": 84,
                "reasoning": "官方平台与合作入口明确。",
                "score_breakdown": [],
                "evidence_links": [],
            }
        ],
        target_departments=["商务合作", "内容平台"],
        public_contact_channels=["官网商务合作入口", "公开 BD 邮箱"],
        budget_signals=["2026 年内容平台合作预算已释放"],
        strategic_directions=["先从平台合作和联合发行切入"],
        tender_timeline=["未来两个季度是重点进入窗口"],
        ecosystem_partners=["内容分发平台"],
        competitor_profiles=["中文在线"],
        source_count=7,
        evidence_density="high",
        source_quality="high",
        query_plan=["AI漫剧头部公司 商业化", "快手可灵 合作 平台"],
        sources=[],
        source_diagnostics={
            "official_source_ratio": 0.43,
            "pipeline_summary": "取数 -> 清洗 -> 分析",
            "pipeline_stages": [],
        },
        entity_graph=ResearchEntityGraphOut(),
    )

    readiness = build_report_readiness(report, deps=_report_readiness_dependencies())
    commercial_summary = build_commercial_summary(report, deps=_delivery_materials_dependencies())
    report = report.model_copy(
        update={
            "report_readiness": readiness,
            "commercial_summary": commercial_summary,
        }
    )
    technical_appendix = build_technical_appendix(report, deps=_delivery_materials_dependencies())
    review_queue = build_review_queue(report, deps=_delivery_materials_dependencies())

    assert readiness.status == "ready"
    assert readiness.actionable is True
    assert readiness.evidence_gate_passed is True
    assert commercial_summary.account_focus == ["快手可灵", "阅文集团"]
    assert "预算" in commercial_summary.budget_signal
    assert "窗口" in commercial_summary.entry_window
    assert "快手可灵" in commercial_summary.next_action
    assert "预算" in commercial_summary.next_action or "窗口" in commercial_summary.next_action
    assert technical_appendix.key_assumptions
    assert technical_appendix.scenario_comparison
    assert technical_appendix.technical_appendix
    assert review_queue
    assert review_queue[0].severity == "high"


def test_report_readiness_guardrails_keep_title_clean() -> None:
    report = ResearchReportDocument(
        keyword="政务云商机",
        research_focus="关注预算和采购窗口",
        output_language="zh-CN",
        research_mode="deep",
        report_title="华东｜政务云：账户优先级与推进路径",
        executive_summary="优先围绕省级客户与预算窗口继续收敛目标名单。",
        consulting_angle="先轻量推进，同时继续补官方源与预算归口。",
        sections=[],
        target_accounts=["省级客户"],
        source_count=3,
        evidence_density="low",
        source_quality="medium",
        query_plan=["政务云 预算", "政务云 采购"],
        sources=[],
        source_diagnostics={
            "official_source_ratio": 0.1,
            "pipeline_summary": "取数 -> 清洗 -> 分析",
            "pipeline_stages": [],
        },
        entity_graph=ResearchEntityGraphOut(),
    )

    readiness = build_report_readiness(report, deps=_report_readiness_dependencies())
    guarded = apply_report_readiness_guardrails(
        report.model_copy(update={"report_readiness": readiness})
    )

    assert guarded.report_title == "华东｜政务云：账户优先级与推进路径"
    assert "待补证研判" not in guarded.report_title
    assert "候选推进版" not in guarded.report_title
    assert "待核验" in guarded.executive_summary or "候选推进" in guarded.executive_summary
