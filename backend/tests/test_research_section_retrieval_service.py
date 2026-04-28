from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.research import ResearchReportResponse, ResearchReportSectionOut, ResearchSourceOut
from app.services.research_retrieval_index_service import ResearchRetrievalIndex, ResearchRetrievalIndexChunk
from app.services.research_section_retrieval_service import (
    attach_section_retrieval_packs,
    build_section_retrieval_packs,
    build_section_retrieval_targets,
)


def _report() -> ResearchReportResponse:
    return ResearchReportResponse(
        keyword="上海数据集团政务云预算",
        research_focus="用于解决方案设计和针对性打单的情报收集。",
        output_language="zh-CN",
        research_mode="deep",
        report_title="上海数据集团政务云预算窗口研判",
        executive_summary="上海数据集团政务云扩容存在预算复核窗口，需要核验采购中心和方案比选节奏。",
        consulting_angle="围绕预算、采购中心、方案切口和生态伙伴形成打单策略。",
        sections=[
            ResearchReportSectionOut(
                title="项目与商机判断",
                items=["7 月预算复核后，采购中心可能启动政务云扩容方案比选。"],
                evidence_quota=2,
                evidence_count=1,
                quota_gap=1,
            ),
            ResearchReportSectionOut(
                title="解决方案设计建议",
                items=["优先准备安全合规、信创适配和云平台扩容路线。"],
                evidence_quota=2,
                evidence_count=1,
                quota_gap=1,
            ),
        ],
        target_accounts=["上海数据集团"],
        target_departments=["采购中心", "数字化办公室"],
        budget_signals=["7 月预算复核"],
        tender_timeline=["8 月方案比选"],
        source_count=2,
        evidence_density="medium",
        source_quality="medium",
        sources=[
            ResearchSourceOut(
                title="上海数据集团公开公告",
                url="https://example.gov.cn/shanghai-data-budget",
                domain="example.gov.cn",
                snippet="公告披露 7 月预算复核、采购意向与政务云扩容需求确认时间窗。",
                search_query="上海数据集团 政务云 预算复核",
                source_type="policy",
                content_status="fetched",
                source_tier="official",
            )
        ],
        generated_at=datetime.now(timezone.utc),
    )


def _index() -> ResearchRetrievalIndex:
    return ResearchRetrievalIndex(
        built_at=datetime.now(timezone.utc),
        chunks=[
            ResearchRetrievalIndexChunk(
                chunk_id="official-budget",
                document_id="doc-1",
                document_type="knowledge_entry",
                title="上海数据集团预算复核公告",
                text="上海数据集团 7 月预算复核，采购中心确认政务云扩容采购意向，8 月进入方案比选。",
                field_key="entry_content",
                label="官方公告",
                source_tier="official",
                source_url="https://example.gov.cn/shanghai-data-budget",
                priority=16,
            ),
            ResearchRetrievalIndexChunk(
                chunk_id="solution-fit",
                document_id="doc-2",
                document_type="knowledge_entry",
                title="政务云安全合规方案笔记",
                text="政务云扩容需要安全合规、等保、信创适配和云平台迁移路线。",
                field_key="entry_content",
                label="方案笔记",
                source_tier="media",
                priority=8,
            ),
        ],
        source_counts={"knowledge_entry": 2},
    )


def test_section_targets_convert_methodology_axes_into_section_queries() -> None:
    targets = build_section_retrieval_targets(_report())
    by_title = {target.section_title: target for target in targets}

    opportunity_target = by_title["项目与商机判断"]

    assert "上海数据集团" in opportunity_target.query
    assert "预算" in opportunity_target.query
    assert any(axis.label == "预算与招采" for axis in opportunity_target.axes)


def test_section_retrieval_pack_routes_index_hits_to_relevant_sections() -> None:
    packs = build_section_retrieval_packs(_report(), _index(), limit_per_section=3)
    by_title = {pack.section_title: pack for pack in packs}

    opportunity_pack = by_title["项目与商机判断"]
    solution_pack = by_title["解决方案设计建议"]

    assert opportunity_pack.status in {"ready", "degraded"}
    assert opportunity_pack.official_hit_count >= 1
    assert any(hit.chunk_id == "official-budget" for hit in opportunity_pack.hits)
    assert solution_pack.hit_count >= 1
    assert "方案切口" in solution_pack.target_axes


def test_attach_section_retrieval_packs_updates_quality_profile_without_mutating_report() -> None:
    report = _report()
    enriched = attach_section_retrieval_packs(report, _index(), limit_per_section=2)

    assert report.quality_profile.section_retrieval_packs == []
    assert enriched.quality_profile.section_retrieval_packs
    assert enriched.quality_profile.methodology.industry_key == "government_cloud"
