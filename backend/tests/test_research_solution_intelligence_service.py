from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.research import ResearchReportResponse, ResearchSourceOut
from app.services.research_solution_intelligence_service import (
    build_market_intelligence_pack,
    build_solution_delivery_pack,
)


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
                snippet="2025年5月公开招标，预算金额 680万元，建设数字人导览、AIGC内容生成、支持并发不少于500路、接口API、等保二级。",
                search_query="文旅 AIGC 数字人 公开招标 技术参数",
                source_type="procurement",
                content_status="fetched",
                source_tier="official",
            ),
            ResearchSourceOut(
                title="景区AI营销平台中标成交公告",
                url="https://ccgp.example.gov.cn/win/ai-marketing",
                domain="ccgp.example.gov.cn",
                snippet="2024年中标成交，AI营销平台包含游客画像、内容生成、活动投放和数据看板，中标供应商：某科技公司。",
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
    assert any("并发" in value or "API" in value for value in pack.tender_projects[0].technical_parameters)
    assert any(item.name == "数字人" or "数字人" in item.name for item in pack.product_catalog)
    assert any("site:ccgp.gov.cn" in query for query in pack.external_source_queries)
    assert "招投标项目明细" in pack.export_markdown


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
    assert any("目标客户" in item for item in pack.clarification_questions)
    assert "对客汇报 PPT 大纲" in pack.export_markdown
