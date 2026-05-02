from __future__ import annotations

import warnings

from app.schemas.research import (
    ResearchReportDocument,
    ResearchSourceDiagnosticsOut,
    ResearchSourceOut,
)
from app.services.research_report_evaluation_service import (
    evaluate_and_improve_research_report,
    evaluate_research_report,
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
