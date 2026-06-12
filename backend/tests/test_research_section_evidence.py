from __future__ import annotations

from collections.abc import Iterable
import re

from app.schemas.research import ResearchEntityEvidenceOut, ResearchReportDocument, ResearchReportSectionOut
from app.services.content_extractor import normalize_text
from app.services.llm_parser import ResearchReportResult
from app.services.research.report_sections import ReportSectionsDependencies, build_sections
from app.services.research.section_quality import (
    SectionQualityDependencies,
    build_section_evidence_links,
    section_confidence_profile,
    section_evidence_quota,
    section_insufficiency_profile,
    section_next_verification_steps,
    section_quota_note,
    section_signal_quality,
)
from app.services.research.action_cards import build_research_action_cards as _build_research_action_cards
from app.services.research.report_runtime_dependencies import action_card_dependencies
from app.services.research.source_documents import SourceDocument, source_document_text
from app.services.research.report_runtime_owner_factory import build_report_runtime_owner_ports


GENERIC_FOCUS_TOKENS = {
    "预算",
    "招标",
    "采购",
    "中标",
    "甲方",
    "竞品",
    "生态伙伴",
    "生态",
    "伙伴",
    "领导讲话",
    "领导",
    "讲话",
    "项目",
    "商机",
    "区域",
    "行业",
    "客户",
    "公司",
    "同行",
    "战略",
    "规划",
}


def _dedupe_strings(values: Iterable[str], limit: int) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        rows.append(normalized)
        if len(rows) >= limit:
            break
    return rows


def _tokenize_for_match(*values: str) -> list[str]:
    tokens: list[str] = []
    for value in values:
        tokens.extend(re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", normalize_text(value)))
    return _dedupe_strings(tokens, 24)


def _concrete_rows(values: Iterable[str]) -> list[str]:
    return [normalize_text(value) for value in values if normalize_text(value) and "证据不足" not in normalize_text(value)]


def _section_quality_dependencies() -> SectionQualityDependencies:
    return SectionQualityDependencies(
        source_text=source_document_text,
        tokenize_for_match=_tokenize_for_match,
        concrete_rows=_concrete_rows,
        dedupe_strings=_dedupe_strings,
        generic_focus_tokens=GENERIC_FOCUS_TOKENS,
    )


def _report_sections_dependencies() -> ReportSectionsDependencies:
    return ReportSectionsDependencies(
        build_section_evidence_links=lambda **kwargs: build_section_evidence_links(
            **kwargs,
            deps=_section_quality_dependencies(),
        ),
        section_signal_quality=lambda *args, **kwargs: section_signal_quality(
            *args,
            **kwargs,
            deps=_section_quality_dependencies(),
        ),
        section_evidence_quota=section_evidence_quota,
        section_quota_note=section_quota_note,
        section_confidence_profile=lambda **kwargs: section_confidence_profile(
            **kwargs,
            deps=_section_quality_dependencies(),
        ),
        section_next_verification_steps=lambda **kwargs: section_next_verification_steps(
            **kwargs,
            deps=_section_quality_dependencies(),
        ),
        section_insufficiency_profile=lambda **kwargs: section_insufficiency_profile(
            **kwargs,
            deps=_section_quality_dependencies(),
        ),
    )


def _build_sections(
    result: ResearchReportResult,
    output_language: str,
    sources: list[SourceDocument],
) -> list[ResearchReportSectionOut]:
    return build_sections(result, output_language, sources, deps=_report_sections_dependencies())


def build_research_action_cards(report: ResearchReportDocument):
    return _build_research_action_cards(
        report,
        deps=action_card_dependencies(build_report_runtime_owner_ports()),
    )


def test_build_sections_attaches_official_evidence_links() -> None:
    result = ResearchReportResult(
        report_title="AI漫剧头部公司研报",
        executive_summary="聚焦头部平台与商业化路径。",
        consulting_angle="优先识别头部平台、合作方式和公开商务入口。",
        commercial_opportunities=[
            "快看漫画正在围绕 AI 漫剧与短剧内容做平台化合作与商业化探索。",
            "头部内容平台更适合先从商务合作和版权分发入口切入。",
        ],
        target_accounts=["快看漫画"],
    )
    sources = [
        SourceDocument(
            title="快看漫画官网｜商务合作",
            url="https://www.kuaikanmanhua.com/business",
            domain="kuaikanmanhua.com",
            snippet="快看漫画 AI漫剧 商务合作 联系我们",
            search_query="AI漫剧 头部公司 商务合作",
            source_type="company",
            content_status="full_text",
            excerpt="快看漫画围绕 AI漫剧、短剧内容和商务合作提供公开入口。",
            source_label="快看漫画官网",
            source_tier="official",
            source_origin="search",
        ),
        SourceDocument(
            title="行业媒体：AI漫剧平台合作趋势",
            url="https://example.com/ai-comic-platform",
            domain="example.com",
            snippet="AI漫剧 平台 合作 商业化",
            search_query="AI漫剧 平台 商业化",
            source_type="web",
            content_status="full_text",
            excerpt="行业媒体提到头部平台正加速 AI漫剧商业化与合作分发。",
            source_label="行业媒体",
            source_tier="media",
            source_origin="search",
        ),
    ]

    sections = _build_sections(result, "zh-CN", sources)

    opportunity_section = next(section for section in sections if section.title == "项目与商机判断")
    assert opportunity_section.evidence_links
    assert opportunity_section.source_tier_counts.get("official", 0) >= 1
    assert opportunity_section.official_source_ratio > 0
    assert any(link.source_tier == "official" for link in opportunity_section.evidence_links)
    assert any("快看漫画" in (link.anchor_text or link.title) for link in opportunity_section.evidence_links)


def test_action_cards_prefer_section_evidence_links_and_filter_static_urls() -> None:
    report = ResearchReportDocument(
        keyword="AI漫剧头部公司",
        output_language="zh-CN",
        research_mode="deep",
        report_title="AI漫剧头部公司研报",
        executive_summary="聚焦平台、合作与商务入口。",
        consulting_angle="优先沉淀对商业化团队有用的甲方、竞品和伙伴线索。",
        sections=[
            ResearchReportSectionOut(
                title="项目与商机判断",
                items=["快看漫画与头部平台正在推进 AI漫剧商业化合作。"],
                evidence_links=[
                    ResearchEntityEvidenceOut(
                        title="快看漫画官网｜商务合作",
                        url="https://www.kuaikanmanhua.com/business",
                        source_label="快看漫画官网",
                        source_tier="official",
                        anchor_text="快看漫画 / 商务合作",
                    )
                ],
            ),
            ResearchReportSectionOut(
                title="投标规划",
                items=["先围绕预算与采购节奏判断进入窗口。"],
                evidence_links=[
                    ResearchEntityEvidenceOut(
                        title="采购公告｜项目预算",
                        url="https://www.ccgp.gov.cn/project-budget",
                        source_label="中国政府采购网",
                        source_tier="official",
                        anchor_text="预算 / 采购",
                    )
                ],
            ),
        ],
        target_accounts=["快看漫画"],
        public_contact_channels=[
            "(http://www.jsxishan.gov.cn/static_common/images/gouhuijx_sgouhui_normal.png)",
            "快看漫画官网商务合作入口 https://www.kuaikanmanhua.com/business",
        ],
        budget_signals=["预算信号来自公开采购公告。"],
        tender_timeline=["当前阶段适合先验证预算与采购节奏。"],
        source_count=2,
    )

    cards = build_research_action_cards(report)
    buyer_entry = next(card for card in cards if card.action_type == "buyer_entry")
    project_timing = next(card for card in cards if card.action_type == "project_timing")

    assert any("kuaikanmanhua.com/business" in item for item in buyer_entry.evidence)
    assert all("static_common/images" not in item for item in buyer_entry.evidence)
    assert any("ccgp.gov.cn/project-budget" in item for item in project_timing.evidence)


def test_build_sections_adds_next_verification_steps_for_low_evidence_sections() -> None:
    result = ResearchReportResult(
        report_title="AI漫剧头部公司研报",
        executive_summary="聚焦头部平台与商业化路径。",
        consulting_angle="优先识别头部平台、合作方式和公开商务入口。",
        commercial_opportunities=[
            "快看漫画正在围绕 AI 漫剧与短剧内容做平台化合作与商业化探索。",
            "头部内容平台更适合先从商务合作和版权分发入口切入。",
        ],
        target_accounts=["快看漫画"],
    )
    sources = [
        SourceDocument(
            title="行业媒体：AI漫剧平台合作趋势",
            url="https://example.com/ai-comic-platform",
            domain="example.com",
            snippet="AI漫剧 平台 合作 商业化",
            search_query="AI漫剧 平台 商业化",
            source_type="web",
            content_status="full_text",
            excerpt="行业媒体提到头部平台正加速 AI漫剧商业化与合作分发。",
            source_label="行业媒体",
            source_tier="media",
            source_origin="search",
        ),
    ]

    sections = _build_sections(result, "zh-CN", sources)

    opportunity_section = next(section for section in sections if section.title == "项目与商机判断")
    assert opportunity_section.status == "needs_evidence"
    assert opportunity_section.meets_evidence_quota is False
    assert opportunity_section.insufficiency_reasons
    assert "未达到稳定推进门槛" in opportunity_section.insufficiency_summary
    assert opportunity_section.next_verification_steps
    assert any("官方" in step or "采购公告" in step for step in opportunity_section.next_verification_steps)
