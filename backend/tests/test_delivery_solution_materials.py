from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.research import ResearchReportResponse, ResearchSourceOut
from app.services.delivery.market_intelligence import build_market_intelligence_pack
from app.services.delivery.solution_materials import (
    build_advisory_artifacts,
    build_solution_delivery_markdown,
    build_solution_delivery_outlines,
)
from app.services.research_delivery_quality_service import review_and_improve_solution_delivery_pack
from app.services.research_solution_intelligence_service import build_solution_delivery_pack


def _report() -> ResearchReportResponse:
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
        budget_signals=["一期预算 300 万-500 万"],
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
                snippet="2025年公开招标，采购人：某市数据局，预算金额 520万元，包含知识库、智能问答、工单协同，要求支持 API 接口、私有化部署、等保三级。",
                search_query="政务AI 助手 招标 技术参数",
                source_type="procurement",
                content_status="fetched",
                source_tier="official",
            )
        ],
        generated_at=datetime.now(timezone.utc),
    )


def test_solution_materials_builds_outlines_and_advisory_artifacts_without_orchestration() -> None:
    report = _report()
    market_pack = build_market_intelligence_pack(
        report,
        scenario="政务AI解决方案",
        target_customer="某市数据局",
        vertical_scene="政务热线 AI 助手",
    )

    outlines = build_solution_delivery_outlines(
        report,
        market_pack=market_pack,
        scenario="政务AI解决方案",
        target_customer="某市数据局",
        vertical_scene="政务热线 AI 助手",
    )
    artifacts = build_advisory_artifacts(
        report,
        market_pack=market_pack,
        scenario="政务AI解决方案",
        target_customer="某市数据局",
        vertical_scene="政务热线 AI 助手",
        evidence_policy="仅把已命中公开来源的内容写成确定判断。",
    )

    assert {document.document_kind for document in outlines.compiled_documents} == {
        "solution_design",
        "consulting_report",
        "project_proposal",
        "feasibility_study",
    }
    assert [section.title for section in outlines.feasibility_outline][:2] == [
        "一、项目概况、研究依据与范围边界",
        "二、现状评价、需求预测与建设必要性",
    ]
    assert any("政务AI解决方案" in bullet for section in outlines.project_proposal_outline for bullet in section.bullets)
    assert any(section.title == "7. 下一步共创计划" for section in outlines.client_ppt_outline)
    assert {artifact.artifact_type for artifact in artifacts} == {
        "client_brief",
        "bidding_prep_memo",
        "execution_materials",
    }
    assert all("证据口径" in artifact.markdown for artifact in artifacts)
    assert any("投标准备" in artifact.markdown for artifact in artifacts)


def test_solution_delivery_markdown_serializes_complete_pack_sections() -> None:
    pack = build_solution_delivery_pack(
        _report(),
        scenario="政务AI解决方案",
        target_customer="某市数据局",
        vertical_scene="政务热线 AI 助手",
        supplemental_context="客户希望先做小范围试点。",
    )
    pack = review_and_improve_solution_delivery_pack(pack)

    markdown = build_solution_delivery_markdown(pack)

    assert "可行性研究报告大纲" in markdown
    assert "项目建议书大纲" in markdown
    assert "对客汇报 PPT 大纲" in markdown
    assert "Advisory-grade 交付产物" in markdown
    assert "解决方案架构就绪度" in markdown
    assert "解决方案架构师工作台" in markdown
    assert "交付质量自审" in markdown
    assert "语义挑战者审查记录" in markdown
    assert "四类专用文档编译器" in markdown
    assert "量化决策模型" in markdown
    assert "可研财务三情景" in markdown
