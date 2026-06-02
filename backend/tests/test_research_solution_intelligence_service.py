from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.research import ResearchReportResponse, ResearchSourceOut
from app.services.delivery.market_intelligence import build_market_intelligence_pack
from app.services.research_solution_intelligence_service import build_solution_delivery_pack


def _report() -> ResearchReportResponse:
    return ResearchReportResponse(
        keyword="文旅AIGC平台",
        research_focus="面向景区客户设计 AIGC 导览、数字人讲解和营销内容生成平台。",
        output_language="zh-CN",
        research_mode="deep",
        report_title="文旅AIGC平台解决方案机会研判",
        executive_summary="近三年文旅数字化和AIGC内容建设需求增加，景区客户更关注导览体验、内容生产和营销转化。",
        consulting_angle="先锁定目标景区和文旅集团，再用近三年招采、产品清单和技术参数反推方案边界。",
        target_accounts=["某文旅集团"],
        target_departments=["数字化部", "市场营销部"],
        budget_signals=["2025 年智慧景区平台升级预算"],
        tender_timeline=["2025 年采购意向后进入公开招标"],
        strategic_directions=["先做数字人导览试点，再扩展到AIGC营销内容平台。"],
        benchmark_cases=["智慧景区数字人讲解项目"],
        flagship_products=["数字人导览平台", "AIGC内容生成平台"],
        source_count=3,
        evidence_density="medium",
        source_quality="medium",
        sources=[
            ResearchSourceOut(
                title="某市智慧文旅AIGC导览平台公开招标公告",
                url="https://ggzy.example.gov.cn/tender/aigc-tourism",
                domain="ggzy.example.gov.cn",
                snippet=(
                    "2025年5月公开招标，项目编号 WLAIGC-2025-01，采购人：某文旅集团，招标代理：某招标代理公司，"
                    "预算金额 680万元，建设数字人导览、AIGC内容生成、支持并发不少于500路、接口API、等保二级，"
                    "投标人需提供大模型相关软件著作权证书。"
                ),
                search_query="文旅 AIGC 数字人 公开招标 技术参数",
                source_type="procurement",
                content_status="fetched",
                source_tier="official",
            ),
            ResearchSourceOut(
                title="景区AI营销平台中标成交公告",
                url="https://ccgp.example.gov.cn/win/ai-marketing",
                domain="ccgp.example.gov.cn",
                snippet="2024年中标成交，AI营销平台包含游客画像、内容生成、活动投放和数据看板，中标供应商：某科技公司。第一中标候选人：某科技公司；第二中标候选人：某数智公司。",
                search_query="景区 AI营销平台 中标",
                source_type="procurement",
                content_status="fetched",
                source_tier="official",
            ),
        ],
        generated_at=datetime.now(timezone.utc),
    )


def test_market_intelligence_pack_extracts_three_year_tenders_products_and_parameters() -> None:
    pack = build_market_intelligence_pack(
        _report(),
        scenario="文旅AIGC平台",
        target_customer="某文旅集团",
        vertical_scene="景区数字人导览",
    )

    assert pack.lookback_years == 3
    assert pack.tender_projects
    assert pack.tender_projects[0].buyer == "某文旅集团"
    assert "680万元" in pack.tender_projects[0].amount
    assert pack.tender_projects[0].tender_agency == "某招标代理公司"
    assert pack.tender_projects[0].project_code == "WLAIGC-2025-01"
    assert any(
        "某数智公司" in value or "某科技公司" in value
        for project in pack.tender_projects
        for value in project.bidder_candidates
    )
    assert any("并发" in value or "API" in value for value in pack.tender_projects[0].technical_parameters)
    assert any(item.name == "数字人" or "数字人" in item.name for item in pack.product_catalog)
    assert any("site:ccgp.gov.cn" in query for query in pack.external_source_queries)
    assert pack.source_support_score > 0
    assert pack.validated_source_count >= 1
    assert "招投标项目明细" in pack.export_markdown
    assert "来源支撑" in pack.export_markdown
    assert "招标代理" in pack.export_markdown


def test_solution_delivery_pack_builds_feasibility_proposal_and_ppt_outlines() -> None:
    pack = build_solution_delivery_pack(
        _report(),
        scenario="文旅AIGC平台",
        target_customer="某文旅集团",
        vertical_scene="景区数字人导览",
        supplemental_context="客户希望先做小范围试点。",
    )

    assert pack.scenario == "文旅AIGC平台"
    assert pack.target_customer == "某文旅集团"
    assert pack.feasibility_outline
    assert pack.project_proposal_outline
    assert pack.client_ppt_outline
    assert {item.artifact_type for item in pack.advisory_artifacts} == {
        "client_brief",
        "bidding_prep_memo",
        "execution_materials",
    }
    assert any("客户 brief" in item.title for item in pack.advisory_artifacts)
    assert any("投标准备" in item.markdown for item in pack.advisory_artifacts)
    assert pack.source_support_score > 0
    assert pack.grounding_checks
    assert any("目标客户" in item for item in pack.clarification_questions)
    assert "Advisory-grade 交付产物" in pack.export_markdown
    assert "对客汇报 PPT 大纲" in pack.export_markdown
    assert pack.solution_quality_profile.overall_score > 0
    assert pack.project_proposal_quality_profile.overall_score > 0
    assert pack.architecture_readiness.overall_score > 0
    assert pack.architecture_readiness.blueprint_sections
    assert any(section.title == "模型、数据与集成层" for section in pack.architecture_readiness.blueprint_sections)
    assert any("接口" in item or "API" in item for item in pack.architecture_readiness.non_functional_requirements)
    assert pack.architecture_readiness.validation_actions
    assert pack.architect_workbench.customer_scenarios
    assert any("信息化" in stakeholder.role for stakeholder in pack.architect_workbench.stakeholders)
    assert any("系统集成" in criterion.criterion for criterion in pack.architect_workbench.decision_criteria)
    assert pack.architect_workbench.capability_architecture_matrix
    assert any(
        "接口" in " ".join(mapping.integration_surfaces)
        or "API" in " ".join(mapping.integration_surfaces)
        for mapping in pack.architect_workbench.capability_architecture_matrix
    )
    assert pack.architect_workbench.architecture_decision_records
    assert any("API-first" in record.selected_direction for record in pack.architect_workbench.architecture_decision_records)
    assert pack.architect_workbench.integration_dependencies
    assert any(
        dependency.operational_owner == "安全合规负责人"
        for dependency in pack.architect_workbench.integration_dependencies
    )
    assert pack.architect_workbench.next_meeting_agenda
    assert pack.project_proposal_quality_profile.self_review.triggered is True
    assert (
        pack.project_proposal_quality_profile.self_review.after_score
        >= pack.project_proposal_quality_profile.self_review.before_score
    )
    assert any("安全合规" in section.title for section in pack.project_proposal_outline)
    assert "交付质量自审" in pack.export_markdown
    assert "解决方案架构就绪度" in pack.export_markdown
    assert "架构蓝图" in pack.export_markdown
    assert "解决方案架构师工作台" in pack.export_markdown
    assert "干系人问题地图" in pack.export_markdown
    assert "能力到架构矩阵" in pack.export_markdown
    assert "ADR 架构决策记录" in pack.export_markdown
    assert "集成依赖诊断" in pack.export_markdown
