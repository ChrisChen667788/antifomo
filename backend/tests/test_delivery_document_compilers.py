from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.research import ResearchReportResponse, ResearchSourceOut
from app.services.delivery.document_compilers import (
    build_delivery_compiled_documents,
    compiled_document_sections_for_formal_export,
    compiled_document_to_outline_sections,
    select_compiled_document,
)
from app.services.delivery.market_intelligence import build_market_intelligence_pack


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
                snippet="2025年公开招标，采购人：某市数据局，预算金额 520万元，包含知识库、智能问答、工单协同、API 接口、私有化部署、等保三级。",
                search_query="政务AI 助手 招标 技术参数",
                source_type="procurement",
                content_status="fetched",
                source_tier="official",
            )
        ],
        generated_at=datetime.now(timezone.utc),
    )


def _compiled_documents():
    report = _report()
    market_pack = build_market_intelligence_pack(
        report,
        scenario="政务AI解决方案",
        target_customer="某市数据局",
        vertical_scene="政务热线 AI 助手",
    )
    return build_delivery_compiled_documents(
        report,
        market_pack=market_pack,
        scenario="政务AI解决方案",
        target_customer="某市数据局",
        vertical_scene="政务热线 AI 助手",
        evidence_policy="仅把已命中公开来源的内容写成确定判断。",
    )


def test_delivery_document_compilers_build_four_distinct_documents() -> None:
    documents = _compiled_documents()

    assert {document.document_kind for document in documents} == {
        "solution_design",
        "consulting_report",
        "project_proposal",
        "feasibility_study",
    }
    assert {document.framework for document in documents} == {
        "solution_design_compiler_v1",
        "consulting_report_compiler_v1",
        "project_proposal_compiler_v1",
        "feasibility_study_compiler_v1",
    }
    assert all(document.sections for document in documents)
    assert all(document.quality_gates for document in documents)
    assert all(document.validation_actions for document in documents)
    assert len({tuple(section.title for section in document.sections) for document in documents}) == 4


def test_document_compiler_kind_specific_sections_are_not_title_swaps() -> None:
    documents = _compiled_documents()
    solution = select_compiled_document(documents, "solution_design")
    consulting = select_compiled_document(documents, "consulting_report")
    proposal = select_compiled_document(documents, "project_proposal")
    feasibility = select_compiled_document(documents, "feasibility_study")

    assert solution is not None
    assert consulting is not None
    assert proposal is not None
    assert feasibility is not None

    solution_text = solution.export_markdown
    consulting_text = consulting.export_markdown
    proposal_text = proposal.export_markdown
    feasibility_text = feasibility.export_markdown

    assert "NFR" in solution_text
    assert "数据、模型、接口" in solution_text
    assert "问题树" in consulting_text
    assert "战略选项" in consulting_text
    assert "立项必要性" in proposal_text
    assert "绩效目标" in proposal_text
    assert "CAPEX/OPEX/TCO" in feasibility_text
    assert "敏感性分析" in feasibility_text
    assert "需求预测" in feasibility_text


def test_compiled_document_adapters_feed_legacy_outlines_and_formal_exports() -> None:
    documents = _compiled_documents()
    feasibility = select_compiled_document(documents, "feasibility_study")
    assert feasibility is not None

    outlines = compiled_document_to_outline_sections(feasibility)
    formal_sections = compiled_document_sections_for_formal_export(feasibility)

    assert outlines
    assert formal_sections
    assert any("质量门槛" in title for title, _rows in formal_sections)
    assert any("CAPEX" in row or "OPEX" in row for _title, rows in formal_sections for row in rows)
