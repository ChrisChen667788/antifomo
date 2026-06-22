from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.research import ResearchReportResponse, ResearchSourceOut
from app.services.delivery.market_intelligence import build_market_intelligence_pack
from app.services.delivery.quantitative_models import (
    build_quantitative_decision_model,
    quantitative_decision_model_sections_for_formal_export,
)
from app.services.work_tasks.formal_documents import (
    _build_formal_document_context,
    _build_formal_document_sections,
)


def _report(*, with_amount: bool = True) -> ResearchReportResponse:
    snippet = (
        "2025年公开招标，采购人：某市数据局，预算金额 520万元，包含知识库、智能问答、工单协同、"
        "API 接口、私有化部署、等保三级。"
        if with_amount
        else "2025年公开招标，采购人：某市数据局，包含知识库、智能问答、工单协同、API 接口和私有化部署。"
    )
    return ResearchReportResponse(
        keyword="政务AI解决方案",
        research_focus="面向政务热线和政务服务大厅的 AI 助手、知识库和工单协同平台。",
        output_language="zh-CN",
        research_mode="deep",
        report_title="政务AI解决方案机会研判",
        executive_summary="政务服务和热线场景近三年持续出现数字化、智能问答和工单协同建设需求。",
        consulting_angle="先锁定目标数据局/政务服务中心，再用近三年招采和产品参数反推方案边界。",
        target_accounts=["某市数据局"],
        target_departments=["政务服务中心", "热线管理处"],
        budget_signals=["一期预算 300 万-500 万"] if with_amount else [],
        tender_timeline=["2026 Q3 招采窗口"],
        strategic_directions=["先做政务AI助手试点，再扩到热线和大厅联动。"],
        benchmark_cases=["政务热线智能问答项目"],
        flagship_products=["政务AI助手平台", "知识库问答平台"],
        source_count=1,
        evidence_density="medium",
        source_quality="medium",
        sources=[
            ResearchSourceOut(
                title="某市政务服务AI助手公开招标公告",
                url="https://ggzy.example.gov.cn/tender/gov-ai",
                domain="ggzy.example.gov.cn",
                snippet=snippet,
                search_query="政务AI 助手 招标 技术参数",
                source_type="procurement",
                content_status="fetched",
                source_tier="official",
            )
        ],
        generated_at=datetime.now(timezone.utc),
    )


def _model(*, with_amount: bool = True):
    report = _report(with_amount=with_amount)
    market_pack = build_market_intelligence_pack(
        report,
        scenario="政务AI解决方案",
        target_customer="某市数据局",
        vertical_scene="政务热线 AI 助手",
    )
    return build_quantitative_decision_model(
        report,
        market_pack=market_pack,
        scenario="政务AI解决方案",
        target_customer="某市数据局",
        vertical_scene="政务热线 AI 助手",
    )


def test_quantitative_decision_model_builds_weighted_options_score_matrix_and_financials() -> None:
    model = _model()

    assert model.framework == "delivery_quantitative_decision_model_v1"
    assert model.recommended_option_id
    assert [option.rank for option in model.alternative_options] == [1, 2, 3]
    assert {option.option_id for option in model.alternative_options} == {
        "status_quo",
        "phased_pilot",
        "full_build",
    }
    assert all(sum(criterion.weight_percent for criterion in option.criterion_scores) == 100 for option in model.alternative_options)
    assert any(item.owner == "商务/财务负责人" for item in model.tender_score_response_matrix)
    assert any(item.risk_level == "high" for item in model.tender_score_response_matrix)
    assert {scenario.scenario_key for scenario in model.financial_scenarios} == {
        "pessimistic",
        "base",
        "optimistic",
    }
    base = next(scenario for scenario in model.financial_scenarios if scenario.scenario_key == "base")
    assert base.capex_cny and base.capex_cny > 0
    assert base.tco_3y_cny and base.tco_3y_cny > base.capex_cny
    assert base.npv_3y_cny is not None
    assert base.irr_percent is not None
    assert any(variable.variable_key == "capex" for variable in model.sensitivity_variables)
    assert "量化决策模型" in model.export_markdown
    assert "投标评分项" in model.export_markdown


def test_quantitative_decision_model_marks_finance_as_assumption_required_without_amount_basis() -> None:
    model = _model(with_amount=False)

    assert model.status == "assumption_required"
    assert all(scenario.capex_cny is None for scenario in model.financial_scenarios)
    assert any("缺少公开预算" in item for item in model.assumptions)
    assert any(variable.variable_key == "capex" and variable.base_value is None for variable in model.sensitivity_variables)


def test_quantitative_decision_model_formal_export_sections_are_appendable() -> None:
    model = _model()

    sections = quantitative_decision_model_sections_for_formal_export(model)

    assert any("备选方案加权比选" in title for title, _rows in sections)
    assert any("投标评分项响应矩阵" in title for title, _rows in sections)
    assert any("财务三情景" in title for title, _rows in sections)
    assert any("CAPEX" in row or "IRR" in row or "ROI" in row for _title, rows in sections for row in rows)


def test_formal_document_sections_append_quantitative_model_from_runtime_pack() -> None:
    report, supplement, context = _build_formal_document_context(
        _report().model_dump(mode="json"),
        output_language="zh-CN",
        delivery_supplement={
            "project_name": "政务AI助手建设项目",
            "target_customer": "某市数据局",
            "solution_scenario": "政务AI解决方案",
            "vertical_scene": "政务热线 AI 助手",
        },
    )

    sections, _market_pack, solution_pack = _build_formal_document_sections(
        report=report,
        output_language="zh-CN",
        document_kind="feasibility_study",
        context=context,
        supplement=supplement,
    )

    assert solution_pack.quantitative_decision_model.alternative_options
    assert any("附：量化决策模型摘要" == title for title, _rows in sections)
    assert any("附：可研财务三情景与敏感性分析" == title for title, _rows in sections)
