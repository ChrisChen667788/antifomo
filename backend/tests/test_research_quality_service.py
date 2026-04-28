from __future__ import annotations

from app.schemas.research import (
    ResearchCommercialSummaryOut,
    ResearchEntityEvidenceOut,
    ResearchReportDocument,
    ResearchReportReadinessOut,
    ResearchReportSectionOut,
    ResearchScenarioOut,
    ResearchSourceDiagnosticsOut,
    ResearchSourceOut,
    ResearchTechnicalAppendixOut,
)
from app.services.research_quality_service import build_research_quality_profile


def _official_source(title: str) -> ResearchSourceOut:
    return ResearchSourceOut(
        title=title,
        url="https://example.gov.cn/procurement",
        domain="example.gov.cn",
        snippet="公告披露政务云采购意向、预算复核和采购中心入口。",
        search_query="上海数据集团 政务云 预算复核 采购意向",
        source_type="policy",
        content_status="browser_extracted",
        source_label="政府公告",
        source_tier="official",
    )


def test_quality_profile_selects_government_cloud_methodology_and_scores_actionable_report() -> None:
    evidence = ResearchEntityEvidenceOut(
        title="上海数据集团政务云采购意向公告",
        url="https://example.gov.cn/procurement",
        source_label="政府公告",
        source_tier="official",
        anchor_text="7 月预算复核 / 采购中心",
        excerpt="公告披露 7 月预算复核，并由采购中心牵头政务云扩容。",
        confidence_tone="high",
    )
    report = ResearchReportDocument(
        keyword="上海数据集团政务云预算",
        research_focus="用于解决方案设计和针对性打单的情报收集。",
        report_title="上海数据集团政务云预算窗口研判",
        executive_summary="政策牵引、预算复核、采购中心和政务云扩容路径均已形成公开证据。",
        consulting_angle="围绕政策、预算、招采、部门和生态伙伴设计打单路径。",
        sections=[
            ResearchReportSectionOut(
                title="项目与商机判断",
                items=["7 月预算复核，采购中心同步确认政务云扩容需求。"],
                status="ready",
                evidence_density="high",
                source_quality="high",
                confidence_tone="high",
                evidence_links=[evidence],
                evidence_count=2,
                evidence_quota=2,
                meets_evidence_quota=True,
                source_tier_counts={"official": 2},
                official_source_ratio=1.0,
            )
        ],
        target_accounts=["上海数据集团"],
        target_departments=["采购中心", "数字化办公室"],
        public_contact_channels=["官网公开联系入口"],
        budget_signals=["7 月预算复核"],
        tender_timeline=["7 月复核预算，8 月进入方案比选"],
        ecosystem_partners=["本地政务云集成商"],
        competitor_profiles=["既有云厂商方案"],
        source_count=6,
        evidence_density="high",
        source_quality="high",
        sources=[_official_source("上海数据集团政务云采购意向公告")],
        source_diagnostics=ResearchSourceDiagnosticsOut(
            scope_industries=["政务云"],
            scope_clients=["上海数据集团"],
            supported_target_accounts=["上海数据集团"],
            source_tier_counts={"official": 4, "media": 1, "aggregate": 1},
            retained_source_count=6,
            strict_topic_source_count=5,
            retrieval_quality="high",
            evidence_mode="strong",
            evidence_mode_label="强证据",
            strict_match_ratio=0.83,
            official_source_ratio=0.67,
            unique_domain_count=4,
        ),
        report_readiness=ResearchReportReadinessOut(
            status="ready",
            score=86,
            actionable=True,
            evidence_gate_passed=True,
        ),
        commercial_summary=ResearchCommercialSummaryOut(
            account_focus=["上海数据集团"],
            budget_signal="7 月预算复核",
            entry_window="8 月方案比选",
            competition_or_partner="关注既有云厂商方案与本地集成商。",
            next_action="准备面向采购中心的政务云扩容方案。",
        ),
        technical_appendix=ResearchTechnicalAppendixOut(
            key_assumptions=["以公开公告作为证据基线。"],
            scenario_comparison=[
                ResearchScenarioOut(name="基准情景", summary="预算按期复核。", implication="进入会前准备。")
            ],
            limitations=[],
            technical_appendix=["采用政策-预算-招采-部门-生态-风险六段式。"],
        ),
    )

    profile = build_research_quality_profile(report)

    assert profile.methodology.industry_key == "government_cloud"
    assert profile.overall_score >= 75
    assert profile.status in {"high_value", "usable"}
    assert profile.intelligence_value_score >= 80
    assert profile.section_evidence_packs[0].section_title == "项目与商机判断"
    assert profile.section_evidence_packs[0].official_evidence_count == 2


def test_quality_profile_flags_low_professional_and_evidence_value() -> None:
    report = ResearchReportDocument(
        keyword="某行业机会",
        research_focus="泛泛观察",
        report_title="行业趋势观察",
        executive_summary="市场可能存在机会，但缺少具体账户和证据。",
        consulting_angle="继续观察。",
        sections=[
            ResearchReportSectionOut(
                title="项目与商机判断",
                items=["尚未发现明确预算窗口。"],
                status="needs_evidence",
                evidence_density="low",
                source_quality="low",
                confidence_tone="low",
                evidence_count=0,
                evidence_quota=2,
                meets_evidence_quota=False,
                quota_gap=2,
                insufficiency_reasons=["缺少官方源", "缺少目标账户"],
            )
        ],
        source_count=1,
        evidence_density="low",
        source_quality="low",
        sources=[
            ResearchSourceOut(
                title="行业媒体观察",
                url="https://example.com/news",
                domain="example.com",
                snippet="泛行业观察。",
                search_query="行业机会",
                source_type="web",
                content_status="snippet_only",
                source_label="媒体",
                source_tier="media",
            )
        ],
        source_diagnostics=ResearchSourceDiagnosticsOut(
            retained_source_count=1,
            strict_topic_source_count=0,
            retrieval_quality="low",
            evidence_mode="fallback",
            official_source_ratio=0.0,
            unique_domain_count=1,
        ),
        report_readiness=ResearchReportReadinessOut(
            status="needs_evidence",
            score=24,
            actionable=False,
            evidence_gate_passed=False,
            missing_axes=["具体账户", "预算/窗口", "官方源"],
        ),
    )

    profile = build_research_quality_profile(report)

    assert profile.status == "needs_evidence"
    assert profile.overall_score < 55
    assert profile.gaps
    assert any("官方" in action or "预算" in action for action in profile.next_actions)
