from __future__ import annotations

import warnings

from datetime import datetime, timezone

from app.schemas.research import (
    ResearchReportDocument,
    ResearchReportResponse,
    ResearchSourceDiagnosticsOut,
    ResearchSourceOut,
)
from app.services import research_service
from app.services.content_extractor import normalize_text
from app.services.research.quality_expansion import expand_report_public_sources_until_quality_improves
from app.services.research.report_storage import report_sources_to_source_documents
from app.services.research.source_documents import SourceDocument, clean_source_text_for_analysis
from app.services.research.web_search import SearchHit
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


def test_watch_quality_triggers_public_expansion_for_delivery_materials(monkeypatch) -> None:
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

    monkeypatch.setattr(research_service, "_search_public_web", _fake_search)
    monkeypatch.setattr(research_service, "_extract_source_document_best_effort", _fake_extract)
    local_settings = research_service.get_settings()
    monkeypatch.setattr(local_settings, "research_quality_expansion_enabled", True)
    monkeypatch.setattr(local_settings, "research_quality_expansion_min_score", 82)
    monkeypatch.setattr(local_settings, "research_quality_expansion_query_limit", 16)
    monkeypatch.setattr(research_service, "get_settings", lambda: local_settings)

    expanded = expand_report_public_sources_until_quality_improves(
        evaluated,
        source_documents=_report_sources_to_source_documents(evaluated.sources),
        runtime={
            "search_timeout_seconds": 1,
            "search_result_limit": 3,
            "url_timeout_seconds": 1,
            "expanded_selected_limit": 6,
        },
        deps=research_service._quality_expansion_dependencies(),
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
