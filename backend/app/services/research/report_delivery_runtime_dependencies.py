from __future__ import annotations

from app.schemas.research import ResearchReportResponse, ResearchReportSectionOut
from app.services.content_extractor import normalize_text
from app.services.delivery.market_intelligence import build_market_intelligence_pack
from app.services.research.action_cards import (
    ResearchActionCardDependencies,
    derive_entry_window,
    entity_names_from_ranked,
)
from app.services.research.delivery_enrichment import (
    DeliveryEnrichmentDependencies,
    apply_report_readiness_guardrails,
    enrich_report_for_delivery as enrich_report_with_dependencies,
)
from app.services.research.delivery_materials import (
    DeliveryMaterialsDependencies,
    build_commercial_summary,
    build_review_queue,
    build_technical_appendix,
)
from app.services.research.entity_ranking_runtime import is_useful_public_contact_row_bound
from app.services.research.followup_diagnostics import (
    FollowupImpactDependencies,
    enrich_followup_diagnostics,
)
from app.services.research.report_common import dedupe_strings
from app.services.research.report_delivery_strategy_runtime import concrete_rows, entity_display_labels
from app.services.research.report_readiness import (
    ReportReadinessDependencies,
    build_report_readiness,
    is_low_signal_execution_report,
    resolved_report_readiness,
)
from app.services.research.report_row_quality import (
    FIELD_ROW_NOISE_TOKENS,
    is_actionable_budget_row,
    is_summary_fact_row,
    summary_fact_rows,
)
from app.services.research.report_sections import (
    ReportSectionsDependencies,
    build_sections as build_sections_with_dependencies,
)
from app.services.llm_parser import ResearchReportResult
from app.services.research.runtime_retrieval import load_runtime_research_retrieval_index
from app.services.research.scope_entity_runtime_dependencies import scope_entity_runtime_functions
from app.services.research.scope_terms import tokenize_for_match
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
from app.services.research.source_documents import (
    SourceDocument,
    looks_like_source_artifact_text,
    looks_like_source_noise_segment,
    source_document_text,
)
from app.services.research.report_storage_runtime import report_sources_to_documents
from app.services.research_quality_service import build_research_quality_profile
from app.services.research_section_retrieval_service import attach_section_retrieval_packs
from app.services.research_solution_intelligence_service import build_solution_delivery_pack
from app.services.research.entity_policy import GENERIC_FOCUS_TOKENS, looks_like_placeholder_contact_row


def section_quality_dependencies() -> SectionQualityDependencies:
    return SectionQualityDependencies(
        source_text=source_document_text,
        tokenize_for_match=tokenize_for_match,
        concrete_rows=concrete_rows,
        dedupe_strings=dedupe_strings,
        generic_focus_tokens=GENERIC_FOCUS_TOKENS,
    )


def report_sections_dependencies() -> ReportSectionsDependencies:
    quality_deps = section_quality_dependencies()

    def bound_build_section_evidence_links(*args, **kwargs):
        return build_section_evidence_links(*args, **kwargs, deps=quality_deps)

    def bound_section_signal_quality(*args, **kwargs):
        return section_signal_quality(*args, **kwargs, deps=quality_deps)

    def bound_section_confidence_profile(*args, **kwargs):
        return section_confidence_profile(*args, **kwargs, deps=quality_deps)

    def bound_section_next_verification_steps(*args, **kwargs):
        return section_next_verification_steps(*args, **kwargs, deps=quality_deps)

    def bound_section_insufficiency_profile(*args, **kwargs):
        return section_insufficiency_profile(*args, **kwargs, deps=quality_deps)

    return ReportSectionsDependencies(
        build_section_evidence_links=bound_build_section_evidence_links,
        section_signal_quality=bound_section_signal_quality,
        section_evidence_quota=section_evidence_quota,
        section_quota_note=section_quota_note,
        section_confidence_profile=bound_section_confidence_profile,
        section_next_verification_steps=bound_section_next_verification_steps,
        section_insufficiency_profile=bound_section_insufficiency_profile,
    )


def build_sections(
    result: ResearchReportResult,
    output_language: str,
    sources: list[SourceDocument],
) -> list[ResearchReportSectionOut]:
    return build_sections_with_dependencies(
        result,
        output_language,
        sources,
        deps=report_sections_dependencies(),
    )


def report_readiness_dependencies() -> ReportReadinessDependencies:
    runtime = scope_entity_runtime_functions()
    return ReportReadinessDependencies(
        dedupe_strings=dedupe_strings,
        sanitize_entity_row=runtime.sanitize_entity_row,
        is_actionable_budget_row=is_actionable_budget_row,
    )


def action_card_dependencies() -> ResearchActionCardDependencies:
    runtime = scope_entity_runtime_functions()
    readiness_deps = report_readiness_dependencies()
    return ResearchActionCardDependencies(
        dedupe_strings=dedupe_strings,
        extract_rank_entity_name=runtime.extract_rank_entity_name,
        theme_labels_from_scope=runtime.theme_labels_from_scope,
        looks_like_scope_prompt_noise=runtime.looks_like_scope_prompt_noise,
        looks_like_placeholder_entity_name=runtime.looks_like_placeholder_entity_name,
        looks_like_fragment_entity_name=runtime.looks_like_fragment_entity_name,
        contains_low_value_entity_token=runtime.contains_low_value_entity_token,
        is_trustworthy_scope_client_name=runtime.is_trustworthy_scope_client_name,
        is_theme_aligned_entity_name=runtime.is_theme_aligned_entity_name,
        is_lightweight_entity_name=runtime.is_lightweight_entity_name,
        is_actionable_budget_row=is_actionable_budget_row,
        is_summary_fact_row=is_summary_fact_row,
        is_low_signal_execution_report=lambda report: is_low_signal_execution_report(report, deps=readiness_deps),
    )


def truncate_sentence(value: str, limit: int = 82) -> str:
    text = normalize_text(value)
    if len(text) <= limit:
        return text
    clipped = text[: limit - 1].rstrip(" ，,：:；;、")
    return f"{clipped}…"


def delivery_materials_dependencies() -> DeliveryMaterialsDependencies:
    runtime = scope_entity_runtime_functions()
    action_deps = action_card_dependencies()
    readiness_deps = report_readiness_dependencies()

    def bound_entity_names_from_ranked(*args, **kwargs):
        return entity_names_from_ranked(*args, **kwargs, deps=action_deps)

    return DeliveryMaterialsDependencies(
        dedupe_strings=dedupe_strings,
        theme_labels_from_scope=runtime.theme_labels_from_scope,
        entity_names_from_ranked=bound_entity_names_from_ranked,
        looks_like_scope_prompt_noise=runtime.looks_like_scope_prompt_noise,
        looks_like_placeholder_entity_name=runtime.looks_like_placeholder_entity_name,
        looks_like_fragment_entity_name=runtime.looks_like_fragment_entity_name,
        contains_low_value_entity_token=runtime.contains_low_value_entity_token,
        is_trustworthy_scope_client_name=runtime.is_trustworthy_scope_client_name,
        is_theme_aligned_entity_name=runtime.is_theme_aligned_entity_name,
        is_lightweight_entity_name=runtime.is_lightweight_entity_name,
        entity_display_labels=entity_display_labels,
        is_actionable_budget_row=is_actionable_budget_row,
        summary_fact_rows=summary_fact_rows,
        derive_entry_window=derive_entry_window,
        truncate_sentence=truncate_sentence,
        is_useful_public_contact_row=is_useful_public_contact_row_bound,
        looks_like_placeholder_contact_row=looks_like_placeholder_contact_row,
        looks_like_source_artifact_text=looks_like_source_artifact_text,
        resolved_report_readiness=lambda report: resolved_report_readiness(report, deps=readiness_deps),
        is_low_signal_execution_report=lambda report: is_low_signal_execution_report(report, deps=readiness_deps),
        field_row_noise_tokens=FIELD_ROW_NOISE_TOKENS,
    )


def followup_impact_dependencies() -> FollowupImpactDependencies:
    return FollowupImpactDependencies(
        looks_like_source_noise_segment=looks_like_source_noise_segment,
        dedupe_strings=dedupe_strings,
        tokenize_for_match=tokenize_for_match,
        generic_focus_tokens=GENERIC_FOCUS_TOKENS,
    )


def delivery_enrichment_dependencies() -> DeliveryEnrichmentDependencies:
    readiness_deps = report_readiness_dependencies()
    materials_deps = delivery_materials_dependencies()
    impact_deps = followup_impact_dependencies()
    return DeliveryEnrichmentDependencies(
        build_report_readiness=lambda report: build_report_readiness(report, deps=readiness_deps),
        build_commercial_summary=lambda report: build_commercial_summary(report, deps=materials_deps),
        build_technical_appendix=lambda report: build_technical_appendix(report, deps=materials_deps),
        build_review_queue=lambda report: build_review_queue(report, deps=materials_deps),
        build_research_quality_profile=build_research_quality_profile,
        report_sources_to_source_documents=report_sources_to_documents,
        load_runtime_research_retrieval_index=load_runtime_research_retrieval_index,
        attach_section_retrieval_packs=attach_section_retrieval_packs,
        build_market_intelligence_pack=build_market_intelligence_pack,
        build_solution_delivery_pack=build_solution_delivery_pack,
        enrich_followup_diagnostics=lambda report: enrich_followup_diagnostics(report, deps=impact_deps),
        apply_report_readiness_guardrails=apply_report_readiness_guardrails,
    )


def enrich_report_for_delivery(report: ResearchReportResponse) -> ResearchReportResponse:
    return enrich_report_with_dependencies(report, deps=delivery_enrichment_dependencies())
