from __future__ import annotations

import warnings

from datetime import datetime, timezone
from types import SimpleNamespace

from app.schemas.research import (
    ResearchEntityGraphOut,
    ResearchEvidenceGateOut,
    ResearchReportDocument,
    ResearchReportResponse,
    ResearchSourceDiagnosticsOut,
    ResearchSourceOut,
)
from app.services.content_extractor import normalize_text
from app.services.delivery.market_intelligence import build_market_intelligence_pack
from app.services.llm_parser import ResearchReportResult
from app.services.research.quality_expansion import (
    QualityExpansionDependencies,
    expand_report_public_sources_until_quality_improves,
)
from app.services.research.report_storage import report_sources_to_source_documents
from app.services.research.source_documents import (
    SourceDocument,
    clean_source_text_for_analysis,
    source_documents_to_research_source_outputs,
)
from app.services.research.web_search import SearchHit
from app.services.research_quality_service import build_research_quality_profile
from app.services.research_solution_intelligence_service import build_solution_delivery_pack
from app.services.research_report_evaluation_service import (
    evaluate_and_improve_research_report,
    evaluate_research_report,
)


def _report_sources_to_source_documents(sources: list[ResearchSourceOut]) -> list[SourceDocument]:
    return report_sources_to_source_documents(
        sources,
        classify_source_type=lambda _url: "web",
        classify_source_tier=lambda **_kwargs: "media",
        derive_source_label=lambda *, fallback=None, **_kwargs: fallback,
        clean_source_text_for_analysis=clean_source_text_for_analysis,
        truncate_text=lambda value, limit: normalize_text(value)[:limit],
        dedupe_sources=lambda documents: list(documents),
    )


def _dedupe_strings(values: list[object], limit: int = 10) -> list[str]:
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


def _dedupe_sources(sources: list[SourceDocument]) -> list[SourceDocument]:
    rows: list[SourceDocument] = []
    seen: set[str] = set()
    for source in sources:
        key = normalize_text(source.url or source.title)
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(source)
    return rows


def _dedupe_hits(hits: list[SearchHit]) -> list[SearchHit]:
    rows: list[SearchHit] = []
    seen: set[str] = set()
    for hit in hits:
        key = normalize_text(hit.url or hit.title)
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(hit)
    return rows


def _scope_hints(
    keyword: str,
    research_focus: str | None,
    sources: list[SourceDocument] | None = None,
) -> dict[str, object]:
    text = normalize_text(
        " ".join(
            [
                keyword,
                research_focus or "",
                *(source.title for source in sources or []),
                *(source.snippet for source in sources or []),
            ]
        )
    )
    return {
        "regions": ["南京"] if "南京" in text else [],
        "industries": ["政务云"] if "政务云" in text else [],
        "clients": ["南京市数据局"] if "南京市数据局" in text else [],
        "company_anchors": [],
        "strategy_query_expansions": [],
        "strategy_exclusion_terms": [],
        "strategy_scope_summary": "",
    }


def _merge_scope_hints(base: dict[str, object], followup: dict[str, object]) -> dict[str, object]:
    merged = dict(base)
    for key, value in followup.items():
        if isinstance(value, list):
            merged[key] = _dedupe_strings([*(merged.get(key, []) or []), *value], 10)
        elif value:
            merged[key] = value
        else:
            merged.setdefault(key, value)
    return merged


def _stored_report_to_result(report: ResearchReportResponse) -> ResearchReportResult:
    return ResearchReportResult(
        report_title=report.report_title,
        executive_summary=report.executive_summary,
        consulting_angle=report.consulting_angle,
        target_accounts=list(report.target_accounts),
        budget_signals=list(report.budget_signals),
        strategic_directions=list(report.strategic_directions),
        solution_design=list(report.strategic_directions),
        next_actions=["补齐官方采购公告后准备客户 brief 和投标准备 memo。"],
    )


def _build_source_diagnostics(
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
    source_type_counts: dict[str, int] = {}
    source_tier_counts: dict[str, int] = {}
    for source in sources:
        source_type_counts[source.source_type] = source_type_counts.get(source.source_type, 0) + 1
        source_tier_counts[source.source_tier] = source_tier_counts.get(source.source_tier, 0) + 1
    official_count = source_tier_counts.get("official", 0)
    official_source_ratio = official_count / max(len(sources), 1)
    return ResearchSourceDiagnosticsOut(
        enabled_source_labels=_dedupe_strings(enabled_source_labels, 10),
        matched_source_labels=_dedupe_strings([source.source_label for source in sources], 8),
        scope_regions=_dedupe_strings(list(scope_hints.get("regions", []) or []), 3),
        scope_industries=_dedupe_strings(list(scope_hints.get("industries", []) or []), 3),
        scope_clients=_dedupe_strings(list(scope_hints.get("clients", []) or []), 3),
        source_type_counts=source_type_counts,
        source_tier_counts=source_tier_counts,
        recency_window_years=recency_window_years,
        filtered_old_source_count=filtered_old_source_count,
        filtered_region_conflict_count=filtered_region_conflict_count,
        retained_source_count=retained_source_count,
        strict_topic_source_count=strict_topic_source_count,
        topic_anchor_terms=_dedupe_strings(topic_anchor_terms, 8),
        matched_theme_labels=_dedupe_strings(matched_theme_labels, 8),
        retrieval_quality="high" if official_count else "medium",
        evidence_mode="strong" if official_count else "provisional",
        evidence_mode_label="强证据" if official_count else "候选证据",
        strict_match_ratio=round(strict_topic_source_count / max(retained_source_count, 1), 3),
        official_source_ratio=round(official_source_ratio, 3),
        unique_domain_count=len({source.domain for source in sources if normalize_text(source.domain)}),
        normalized_entity_count=len(entity_graph.entities),
        normalized_target_count=len(entity_graph.target_entities),
        normalized_competitor_count=len(entity_graph.competitor_entities),
        normalized_partner_count=len(entity_graph.partner_entities),
        expansion_triggered=expansion_triggered,
        corrective_triggered=corrective_triggered,
        candidate_profile_companies=_dedupe_strings(candidate_profile_companies, 6),
        candidate_profile_hit_count=candidate_profile_hit_count,
        candidate_profile_official_hit_count=candidate_profile_official_hit_count,
        candidate_profile_source_labels=_dedupe_strings(candidate_profile_source_labels, 8),
        generation_grounding_score=88,
        response_quality_score=88,
    )


def _enrich_report_for_delivery(report: ResearchReportResponse) -> ResearchReportResponse:
    return report.model_copy(
        update={
            "market_intelligence": build_market_intelligence_pack(report),
            "solution_delivery_pack": build_solution_delivery_pack(report),
            "quality_profile": build_research_quality_profile(report),
        }
    )


class _GroundingReview:
    def to_diagnostics_update(self) -> dict[str, object]:
        return {
            "generation_grounding_score": 90,
            "response_quality_score": 90,
        }


def _quality_expansion_dependencies(
    *,
    search_public_web,
    extract_source_document_best_effort,
) -> QualityExpansionDependencies:
    settings = SimpleNamespace(
        research_quality_expansion_enabled=True,
        research_quality_expansion_min_score=82,
        research_quality_expansion_max_rounds=1,
        research_quality_expansion_query_limit=16,
        research_search_timeout_seconds=6,
        research_max_search_results=3,
        research_max_sources=6,
        url_fetch_timeout_seconds=8,
        research_source_excerpt_chars=500,
    )
    return QualityExpansionDependencies(
        get_settings=lambda: settings,
        dedupe_strings=_dedupe_strings,
        infer_input_scope_hints=lambda keyword, research_focus: _scope_hints(keyword, research_focus),
        infer_scope_hints=_scope_hints,
        merge_scope_hints=_merge_scope_hints,
        build_corrective_query_plan=lambda **_kwargs: [],
        build_expanded_query_plan=lambda *_args, **_kwargs: [],
        curated_wechat_channels=("政采云",),
        build_company_seed_hits=lambda *_args, **_kwargs: [],
        search_public_web=search_public_web,
        hybrid_rank_hits=lambda hits, **_kwargs: _dedupe_hits(list(hits)),
        select_hits_with_source_balance=lambda hits, *, limit: hits[:limit],
        dedupe_hits=_dedupe_hits,
        extract_source_document_best_effort=extract_source_document_best_effort,
        filter_recent_sources=lambda sources: sources,
        build_theme_terms=lambda keyword, research_focus, scope_hints: _dedupe_strings(
            [keyword, research_focus or "", *list(scope_hints.get("industries", []) or [])],
            8,
        ),
        resolved_company_anchor_terms=lambda keyword, research_focus, scope_hints: _dedupe_strings(
            [keyword, research_focus or "", *list(scope_hints.get("clients", []) or [])],
            8,
        ),
        refine_sources_for_report=lambda sources, **_kwargs: list(sources),
        stored_report_to_result=_stored_report_to_result,
        build_entity_graph=lambda *_args, **_kwargs: ResearchEntityGraphOut(),
        rank_top_entities=lambda *_args, **_kwargs: ([], []),
        filtered_rank_fallback_values=lambda values, **_kwargs: _dedupe_strings(values, 6),
        build_entity_specific_contact_rows=lambda *_args, **_kwargs: [],
        build_entity_specific_team_rows=lambda *_args, **_kwargs: [],
        extract_topic_anchor_terms=lambda keyword, research_focus: _dedupe_strings([keyword, research_focus or ""], 6),
        collect_matched_theme_labels=lambda sources, **_kwargs: _dedupe_strings(
            [source.source_label for source in sources],
            8,
        ),
        build_source_diagnostics=_build_source_diagnostics,
        source_max_age_years=7,
        evidence_density_level=lambda sources, _parsed: "high" if len(sources) >= 2 else "low",
        source_quality_level=lambda sources: "high" if any(source.source_tier == "official" for source in sources) else "low",
        source_documents_to_outputs=source_documents_to_research_source_outputs,
        build_sections=lambda *_args, **_kwargs: [],
        enrich_report_for_delivery=_enrich_report_for_delivery,
        report_sources_to_source_documents=_report_sources_to_source_documents,
        dedupe_sources=_dedupe_sources,
        review_generation_grounding=lambda *_args, **_kwargs: _GroundingReview(),
        evaluate_and_improve_research_report=lambda candidate, **_kwargs: candidate,
        emit_research_progress=lambda *_args, **_kwargs: None,
        build_progress_message=lambda message, **_kwargs: message,
    )


def _source(snippet: str) -> ResearchSourceOut:
    return ResearchSourceOut(
        title="某市智慧文旅AIGC平台采购项目中标公告",
        url="https://ggzy.example.gov.cn/tender/123",
        domain="ggzy.example.gov.cn",
        snippet=snippet,
        search_query="某市 智慧文旅 AIGC 中标公告",
        source_type="procurement",
        content_status="browser_extracted",
        source_label="公共资源交易公告",
        source_tier="official",
    )


def _report() -> ResearchReportDocument:
    source = _source(
        "项目名称：某市智慧文旅AIGC平台采购项目。采购人：某市文化和旅游局。"
        "中标人：智慧云科技有限公司。投标人：未来智能科技有限公司、华东数科有限公司。"
        "招标代理：东方招标代理有限公司。技术参数包括数字人导览、AIGC内容生成、接口API和等保要求。"
    )
    return ResearchReportDocument(
        keyword="某市智慧文旅AIGC平台",
        research_focus="输出解决方案研报，关注招投标实体、技术参数和进入路径",
        report_title="某市智慧文旅AIGC平台机会研判",
        executive_summary="公开公告显示某市文化和旅游局正在推进智慧文旅AIGC平台。",
        consulting_angle="围绕文旅局预算窗口准备解决方案。",
        sections=[],
        target_accounts=["某市文化和旅游局"],
        budget_signals=["公开采购项目已经披露预算与技术参数"],
        strategic_directions=["先做数字人导览和AIGC内容生成方案"],
        source_count=1,
        evidence_density="medium",
        source_quality="high",
        sources=[source],
        source_diagnostics=ResearchSourceDiagnosticsOut(
            retained_source_count=1,
            strict_topic_source_count=1,
            retrieval_quality="medium",
            evidence_mode="provisional",
            evidence_mode_label="候选证据",
            strict_match_ratio=0.74,
            official_source_ratio=1.0,
            unique_domain_count=1,
            generation_grounding_score=74,
            response_quality_score=70,
        ),
    )


def test_research_report_evaluation_scores_procurement_entity_recall() -> None:
    report = _report()

    evaluation = evaluate_research_report(report)

    assert evaluation.framework == "deepeval_style_custom"
    assert evaluation.procurement_entity_recall_score < 100
    assert "智慧云科技有限公司" in evaluation.missing_procurement_entities
    assert any("招标人" in query and "中标方" in query for query in evaluation.corrective_queries)


def test_low_quality_evaluation_self_improves_missing_entities_before_delivery() -> None:
    report = _report()

    improved = evaluate_and_improve_research_report(report, min_overall_score=95, min_entity_recall_score=95)

    evaluation = improved.evaluation_profile
    added_names = [entity.name for entity in improved.pending_partner_candidates]
    assert evaluation.self_improvement.triggered is True
    assert evaluation.self_improvement.before_score <= evaluation.self_improvement.after_score
    assert "智慧云科技有限公司" in added_names
    assert evaluation.self_improvement.corrective_queries
    assert improved.market_intelligence.intelligence_gaps
    assert any(item.id == "review-report-evaluation-entity-recall" for item in improved.review_queue)


def test_research_report_assignment_coerces_ranked_entities_without_serializer_warning() -> None:
    report = _report()
    report.top_target_accounts = [
        {
            "name": "某市文化和旅游局",
            "score": 82,
            "reasoning": "采购公告确认采购人。",
            "entity_mode": "instance",
            "score_breakdown": [],
            "evidence_links": [],
        }
    ]

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        payload = report.model_dump(mode="json")

    assert payload["top_target_accounts"][0]["name"] == "某市文化和旅游局"
    assert not [item for item in caught if "Pydantic serializer warnings" in str(item.message)]


def test_watch_quality_triggers_public_expansion_for_delivery_materials() -> None:
    base = ResearchReportResponse(
        keyword="南京政务云",
        research_focus="准备政务云客户 brief、投标准备 memo 和执行材料",
        output_language="zh-CN",
        research_mode="deep",
        report_title="南京政务云机会初判",
        executive_summary="当前只有泛化媒体线索，仍需补官方采购和公共资源交易来源。",
        consulting_angle="先补证再形成对客材料。",
        target_accounts=["南京市数据局"],
        budget_signals=["疑似存在政务云预算窗口"],
        strategic_directions=["围绕政务云迁移和数据治理形成方案"],
        source_count=1,
        evidence_density="low",
        source_quality="low",
        sources=[
            ResearchSourceOut(
                title="行业观察：政务云建设持续升温",
                url="https://media.example.cn/nanjing-cloud",
                domain="media.example.cn",
                snippet="泛行业评论提到政务云，但缺少采购人、预算和项目编号。",
                search_query="南京 政务云 行业观察",
                source_type="media",
                content_status="snippet_only",
                source_tier="media",
            )
        ],
        source_diagnostics=ResearchSourceDiagnosticsOut(
            retained_source_count=1,
            strict_topic_source_count=0,
            retrieval_quality="low",
            evidence_mode="fallback",
            response_quality_score=58,
        ),
        generated_at=datetime.now(timezone.utc),
    )
    evaluated = evaluate_and_improve_research_report(base, min_overall_score=95, min_entity_recall_score=95)

    calls: list[str] = []

    def _fake_search(query: str, *, timeout_seconds: int, limit: int) -> list[SearchHit]:
        calls.append(query)
        if "采购" not in query and "招标" not in query and "公共资源" not in query:
            return []
        return [
            SearchHit(
                title="南京市数据局政务云采购意向公告",
                url="https://ccgp.gov.cn/cggg/nanjing-data-cloud",
                snippet=(
                    "采购人：南京市数据局。项目名称：南京政务云升级项目。预算金额 1200万元，"
                    "建设内容包括政务云迁移、数据治理、等保和运维服务。"
                ),
                search_query=query,
                source_hint="procurement",
                source_label="政府采购公告",
            )
        ]

    def _fake_extract(
        hit: SearchHit,
        *,
        timeout_seconds: int,
        excerpt_chars: int,
    ) -> SourceDocument:
        return SourceDocument(
            title=hit.title,
            url=hit.url,
            domain="ccgp.gov.cn",
            snippet=hit.snippet,
            search_query=hit.search_query,
            source_type="procurement",
            content_status="fetched",
            excerpt=hit.snippet,
            source_label="政府采购公告",
            source_tier="official",
            source_origin="search",
        )

    expanded = expand_report_public_sources_until_quality_improves(
        evaluated,
        source_documents=_report_sources_to_source_documents(evaluated.sources),
        runtime={
            "search_timeout_seconds": 1,
            "search_result_limit": 3,
            "url_timeout_seconds": 1,
            "expanded_selected_limit": 6,
        },
        deps=_quality_expansion_dependencies(
            search_public_web=_fake_search,
            extract_source_document_best_effort=_fake_extract,
        ),
    )

    diagnostics = expanded.source_diagnostics
    assert calls
    assert diagnostics.quality_expansion_triggered is True
    assert diagnostics.quality_expansion_added_source_count >= 1
    assert diagnostics.quality_expansion_after_score >= diagnostics.quality_expansion_before_score
    assert any("site:ccgp.gov.cn" in query for query in diagnostics.quality_expansion_query_plan)
    assert any("site:mp.weixin.qq.com" in query for query in diagnostics.quality_expansion_query_plan)
    assert expanded.source_count > evaluated.source_count
    assert expanded.solution_delivery_pack.advisory_artifacts
    assert "政府采购公告" in expanded.source_diagnostics.matched_source_labels


def test_evidence_governed_report_skips_legacy_post_draft_expansion() -> None:
    report = _report().model_copy(
        update={
            "research_evidence_gate": ResearchEvidenceGateOut(
                enforced=True,
                status="evidence_ready",
                passed=True,
                formal_report_allowed=True,
                solution_delivery_allowed=True,
            )
        }
    )
    calls: list[str] = []

    def _unexpected_search(query: str, **_kwargs) -> list[SearchHit]:
        calls.append(query)
        return []

    expanded = expand_report_public_sources_until_quality_improves(
        report,
        source_documents=_report_sources_to_source_documents(report.sources),
        deps=_quality_expansion_dependencies(
            search_public_web=_unexpected_search,
            extract_source_document_best_effort=lambda *_args, **_kwargs: None,
        ),
    )

    assert expanded == report
    assert calls == []
