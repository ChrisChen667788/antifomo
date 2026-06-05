from __future__ import annotations

from datetime import datetime, timezone
import re

from app.schemas.research import (
    ResearchCommercialSummaryOut,
    ResearchFollowupContextOut,
    ResearchFollowupDiagnosticsOut,
    ResearchReportResponse,
    ResearchReportReadinessOut,
    ResearchReportSectionOut,
    ResearchSourceOut,
    ResearchTechnicalAppendixOut,
)
from app.services.content_extractor import normalize_text
from app.services.delivery.market_intelligence import build_market_intelligence_pack
from app.services.research.delivery_enrichment import (
    DeliveryEnrichmentDependencies,
    enrich_report_for_delivery,
)
from app.services.research.followup_diagnostics import (
    FollowupDiagnosticsDependencies,
    enrich_followup_diagnostics,
    render_followup_section_focus_prompt_context,
)
from app.services.research.report_storage import report_sources_to_source_documents
from app.services.research.source_documents import (
    SourceDocument,
    clean_source_text_for_analysis,
    looks_like_source_noise_segment,
)
from app.services.research_quality_service import build_research_quality_profile
from app.services.research_retrieval_index_service import ResearchRetrievalIndex, ResearchRetrievalIndexChunk
from app.services.research_section_retrieval_service import (
    attach_section_retrieval_packs,
    build_section_retrieval_packs,
    build_section_retrieval_targets,
    render_section_retrieval_prompt_context,
)
from app.services.research_solution_intelligence_service import build_solution_delivery_pack


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


def _dedupe_strings(values, limit: int) -> list[str]:
    seen: set[str] = set()
    rows: list[str] = []
    for value in values:
        normalized = normalize_text(str(value or ""))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        rows.append(normalized)
        if len(rows) >= limit:
            break
    return rows


def _followup_dependencies() -> FollowupDiagnosticsDependencies:
    return FollowupDiagnosticsDependencies(
        truncate_text=lambda value, limit: normalize_text(value)[:limit],
        sanitize_research_focus_text=lambda value: normalize_text(value or ""),
        looks_like_source_noise_segment=looks_like_source_noise_segment,
        merge_scope_hints=lambda base, followup: {**base, **followup},
        dedupe_strings=_dedupe_strings,
        prune_industry_hints=lambda values: _dedupe_strings(values, 6),
        infer_input_scope_hints=lambda *_args, **_kwargs: {},
        theme_labels_from_scope=lambda *_args, **_kwargs: [],
        clean_scope_entity_names=lambda values, limit=6, **_kwargs: _dedupe_strings(values, limit),
        build_query_plan=lambda *_args, **_kwargs: [],
        extract_topic_anchor_terms=lambda _keyword, _focus: [],
        tokenize_for_match=lambda value, **_kwargs: re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_]{2,}", normalize_text(value)),
        generic_focus_tokens={"项目", "方案", "预算", "采购"},
        org_pattern=re.compile(r"[\u4e00-\u9fffA-Za-z0-9]+(?:集团|公司|中心|办公室|数据局)"),
    )


def _enrich_report_for_delivery(report: ResearchReportResponse) -> ResearchReportResponse:
    return enrich_report_for_delivery(
        report,
        deps=DeliveryEnrichmentDependencies(
            build_report_readiness=lambda _report: ResearchReportReadinessOut(
                status="ready",
                score=90,
                actionable=True,
                evidence_gate_passed=True,
            ),
            build_commercial_summary=lambda _report: ResearchCommercialSummaryOut(next_action="继续补充官方证据"),
            build_technical_appendix=lambda _report: ResearchTechnicalAppendixOut(),
            build_review_queue=lambda _report: [],
            build_research_quality_profile=build_research_quality_profile,
            report_sources_to_source_documents=_report_sources_to_source_documents,
            load_runtime_research_retrieval_index=lambda **_kwargs: _index(),
            attach_section_retrieval_packs=attach_section_retrieval_packs,
            build_market_intelligence_pack=build_market_intelligence_pack,
            build_solution_delivery_pack=build_solution_delivery_pack,
            enrich_followup_diagnostics=lambda enriched: enrich_followup_diagnostics(
                enriched,
                deps=_followup_dependencies(),
            ),
            apply_report_readiness_guardrails=lambda enriched: enriched,
        ),
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


def _followup_report() -> ResearchReportResponse:
    return _report().model_copy(
        update={
            "followup_context": ResearchFollowupContextOut(
                followup_report_title="上海数据集团政务云预算窗口研判",
                followup_report_summary="上一版判断预算窗口存在，但未明确采购中心和方案节奏。",
                supplemental_context="新增采购中心和数字化办公室的组织入口线索。",
                supplemental_evidence="公开公告提到 7 月预算复核、8 月方案比选。",
                supplemental_requirements="优先重写项目与商机判断、解决方案设计建议。",
            ),
            "followup_diagnostics": ResearchFollowupDiagnosticsOut(
                enabled=True,
                input_sections=["人工补充新信息", "人工补充新证据/待核验线索", "人工补充新需求"],
                planning_focus="补采购中心、预算复核和方案比选节奏",
                summary="已根据补证输入重建二次检索范围",
                scope_rebuilt=True,
                query_decomposition_applied=True,
                decomposition_queries=["上海数据集团 采购中心 政务云 预算复核", "上海数据集团 方案比选 政务云"],
                rebuilt_regions=["上海"],
                rebuilt_industries=["政务云"],
                rebuilt_clients=["上海数据集团"],
                rebuilt_company_anchors=["上海数据集团"],
                rebuilt_must_include_terms=["采购中心", "预算复核", "方案比选"],
            ),
        }
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


def test_render_section_retrieval_prompt_context_includes_ranked_evidence() -> None:
    context = render_section_retrieval_prompt_context(
        _report(),
        index=_index(),
        limit_per_section=2,
    )

    assert "[Section] 项目与商机判断" in context
    assert "上海数据集团预算复核公告" in context
    assert "Next Steps:" in context
    assert "Support Score" in context


def test_enrich_report_for_delivery_attaches_runtime_section_retrieval_packs() -> None:
    enriched = _enrich_report_for_delivery(_report())

    assert enriched.quality_profile.section_retrieval_packs
    assert any(pack.hit_count >= 1 for pack in enriched.quality_profile.section_retrieval_packs)
    assert any(
        hit.title == "上海数据集团公开公告" or hit.source_url == "https://example.gov.cn/shanghai-data-budget"
        for pack in enriched.quality_profile.section_retrieval_packs
        for hit in pack.hits
    )


def test_followup_diagnostics_enrichment_builds_impacted_sections_and_resolution_flags() -> None:
    enriched = _enrich_report_for_delivery(_followup_report())

    assert enriched.followup_diagnostics.enabled is True
    assert enriched.followup_diagnostics.title_resolution == "reused"
    assert enriched.followup_diagnostics.summary_resolution == "corrected"
    assert enriched.followup_diagnostics.impacted_sections
    assert any(item.section_title == "项目与商机判断" for item in enriched.followup_diagnostics.impacted_sections)
    assert any("采购中心" in item.reason or "采购中心" in " / ".join(item.matched_inputs) for item in enriched.followup_diagnostics.impacted_sections)


def test_render_followup_section_focus_prompt_context_lists_impacted_sections() -> None:
    enriched = attach_section_retrieval_packs(_followup_report(), _index(), limit_per_section=2)
    context = render_followup_section_focus_prompt_context(
        enriched,
        deps=_followup_dependencies(),
    )

    assert "项目与商机判断" in context
    assert "impact=" in context
    assert "采购中心" in context or "预算复核" in context
