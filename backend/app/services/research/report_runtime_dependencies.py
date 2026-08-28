from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.services.research.action_cards import ResearchActionCardDependencies
from app.services.research.report_common import dedupe_strings
from app.services.research.report_readiness import (
    ReportReadinessDependencies,
    is_low_signal_execution_report,
    resolved_report_readiness,
)
from app.services.research.report_row_quality import (
    BAD_EXEC_SUMMARY_PHRASES,
    FIELD_ROW_NOISE_TOKENS,
    is_actionable_budget_row,
    is_summary_fact_row,
    looks_like_insufficient,
    summary_fact_rows,
)
from app.services.research.stored_report_rewrite import (
    StoredReportRewriteDependencies,
    StoredReportRewriteOrchestrationDependencies,
)
from app.services.research.report_text_quality import (
    ReportTextQualityDependencies,
    looks_like_bad_executive_summary,
)
from app.services.research.scope_entity_runtime_dependencies import ScopeEntityRuntimeFunctions
from app.services.research.source_documents import (
    source_document_text,
    source_documents_to_research_source_outputs,
)


@dataclass(frozen=True, slots=True)
class ReportScopeOwnerPorts:
    scope_entity: ScopeEntityRuntimeFunctions
    source_theme_match_score: Callable[..., int]
    infer_input_scope_hints: Callable[..., dict[str, object]]
    merge_scope_hints: Callable[..., dict[str, object]]
    infer_scope_hints: Callable[..., dict[str, object]]
    prune_industry_hints: Callable[..., list[str]]
    collect_matched_theme_labels: Callable[..., list[str]]
    scope_anchor_text_segments: Callable[[str | None], list[str]]


@dataclass(frozen=True, slots=True)
class ReportStorageOwnerPorts:
    report_sources_to_source_documents: Callable[..., list[Any]]
    canonicalize_stored_report_entities: Callable[..., Any]
    canonicalize_stored_entity_name: Callable[..., str]
    clean_candidate_profile_company_names: Callable[..., list[str]]
    resolve_stored_report_target_support: Callable[..., Any]
    apply_guarded_rewrite_diagnostics: Callable[..., Any]
    assess_stored_report_rewrite_mode: Callable[..., Any]
    stored_report_to_result: Callable[..., Any]
    report_intelligence_from_result: Callable[..., dict[str, list[str]]]
    canonicalize_stored_result_entities: Callable[..., Any]


@dataclass(frozen=True, slots=True)
class ReportRankingOwnerPorts:
    source_supports_target_account: Callable[..., bool]
    build_entity_graph: Callable[..., Any]
    build_source_diagnostics: Callable[..., Any]
    rank_report_entities: Callable[..., Any]
    rank_top_entities: Callable[..., Any]
    filtered_rank_fallback_values: Callable[..., list[str]]
    build_entity_specific_contact_rows: Callable[..., list[str]]
    build_entity_specific_team_rows: Callable[..., list[str]]


@dataclass(frozen=True, slots=True)
class ReportDeliveryOwnerPorts:
    compress_title_segments: Callable[..., list[str]]
    summary_contains_output_noise: Callable[[str], bool]
    build_source_intelligence: Callable[..., dict[str, list[str]]]
    merge_result_with_intelligence: Callable[..., Any]
    apply_topic_specific_overrides: Callable[..., Any]
    build_sections: Callable[..., list[Any]]
    evidence_density_level: Callable[..., str]
    source_quality_level: Callable[..., str]
    enrich_report_for_delivery: Callable[..., Any]
    sanitize_report_result_entities: Callable[..., Any]
    enforce_report_entity_authenticity: Callable[..., Any]
    build_guarded_rewrite_title: Callable[..., str]
    source_max_age_years: int


@dataclass(frozen=True, slots=True)
class ReportRuntimeOwnerPorts:
    scope: ReportScopeOwnerPorts
    storage: ReportStorageOwnerPorts
    ranking: ReportRankingOwnerPorts
    delivery: ReportDeliveryOwnerPorts


def action_card_dependencies(owners: ReportRuntimeOwnerPorts) -> ResearchActionCardDependencies:
    scope_entity = owners.scope.scope_entity
    return ResearchActionCardDependencies(
        dedupe_strings=dedupe_strings,
        extract_rank_entity_name=scope_entity.extract_rank_entity_name,
        theme_labels_from_scope=scope_entity.theme_labels_from_scope,
        looks_like_scope_prompt_noise=scope_entity.looks_like_scope_prompt_noise,
        looks_like_placeholder_entity_name=scope_entity.looks_like_placeholder_entity_name,
        looks_like_fragment_entity_name=scope_entity.looks_like_fragment_entity_name,
        contains_low_value_entity_token=scope_entity.contains_low_value_entity_token,
        is_trustworthy_scope_client_name=scope_entity.is_trustworthy_scope_client_name,
        is_theme_aligned_entity_name=scope_entity.is_theme_aligned_entity_name,
        is_lightweight_entity_name=scope_entity.is_lightweight_entity_name,
        is_actionable_budget_row=is_actionable_budget_row,
        is_summary_fact_row=is_summary_fact_row,
        is_low_signal_execution_report=lambda report: is_low_signal_execution_report(
            report,
            deps=report_readiness_dependencies(owners),
        ),
    )


def report_readiness_dependencies(owners: ReportRuntimeOwnerPorts) -> ReportReadinessDependencies:
    scope_entity = owners.scope.scope_entity
    return ReportReadinessDependencies(
        dedupe_strings=dedupe_strings,
        sanitize_entity_row=scope_entity.sanitize_entity_row,
        is_actionable_budget_row=is_actionable_budget_row,
    )


def stored_report_rewrite_dependencies(owners: ReportRuntimeOwnerPorts) -> StoredReportRewriteDependencies:
    scope = owners.scope
    ranking = owners.ranking
    delivery = owners.delivery
    scope_entity = scope.scope_entity
    return StoredReportRewriteDependencies(
        source_text=source_document_text,
        source_theme_match_score=scope.source_theme_match_score,
        looks_like_insufficient=looks_like_insufficient,
        dedupe_strings=dedupe_strings,
        sanitize_entity_row=scope_entity.sanitize_entity_row,
        build_theme_terms=scope_entity.build_theme_terms,
        source_supports_target_account=ranking.source_supports_target_account,
        resolved_report_readiness=lambda report: resolved_report_readiness(
            report,
            deps=report_readiness_dependencies(owners),
        ),
        is_actionable_budget_row=is_actionable_budget_row,
        is_summary_fact_row=is_summary_fact_row,
        looks_like_bad_executive_summary=lambda value: looks_like_bad_executive_summary(
            value,
            deps=report_text_quality_dependencies(owners),
        ),
        compress_title_segments=delivery.compress_title_segments,
        field_row_noise_tokens=FIELD_ROW_NOISE_TOKENS,
    )


def report_text_quality_dependencies(owners: ReportRuntimeOwnerPorts) -> ReportTextQualityDependencies:
    return ReportTextQualityDependencies(
        summary_contains_output_noise=owners.delivery.summary_contains_output_noise,
        bad_executive_summary_phrases=BAD_EXEC_SUMMARY_PHRASES,
    )


def stored_report_rewrite_orchestration_dependencies(
    owners: ReportRuntimeOwnerPorts,
) -> StoredReportRewriteOrchestrationDependencies:
    scope = owners.scope
    storage = owners.storage
    ranking = owners.ranking
    delivery = owners.delivery
    scope_entity = scope.scope_entity
    return StoredReportRewriteOrchestrationDependencies(
        report_sources_to_source_documents=storage.report_sources_to_source_documents,
        infer_input_scope_hints=scope.infer_input_scope_hints,
        canonicalize_stored_report_entities=storage.canonicalize_stored_report_entities,
        dedupe_strings=dedupe_strings,
        canonicalize_stored_entity_name=storage.canonicalize_stored_entity_name,
        merge_scope_hints=scope.merge_scope_hints,
        infer_scope_hints=scope.infer_scope_hints,
        prune_industry_hints=scope.prune_industry_hints,
        sanitize_entity_row=scope_entity.sanitize_entity_row,
        build_entity_graph=ranking.build_entity_graph,
        extract_topic_anchor_terms=scope_entity.extract_topic_anchor_terms,
        collect_matched_theme_labels=scope.collect_matched_theme_labels,
        clean_candidate_profile_company_names=storage.clean_candidate_profile_company_names,
        build_source_diagnostics=ranking.build_source_diagnostics,
        resolve_stored_report_target_support=storage.resolve_stored_report_target_support,
        apply_guarded_rewrite_diagnostics=storage.apply_guarded_rewrite_diagnostics,
        assess_stored_report_rewrite_mode=storage.assess_stored_report_rewrite_mode,
        stored_report_to_result=storage.stored_report_to_result,
        report_intelligence_from_result=storage.report_intelligence_from_result,
        build_source_intelligence=delivery.build_source_intelligence,
        sanitize_report_field_rows=scope_entity.sanitize_report_field_rows,
        merge_result_with_intelligence=delivery.merge_result_with_intelligence,
        apply_topic_specific_overrides=delivery.apply_topic_specific_overrides,
        canonicalize_stored_result_entities=storage.canonicalize_stored_result_entities,
        build_theme_terms=scope_entity.build_theme_terms,
        rank_report_entities=ranking.rank_report_entities,
        rank_top_entities=ranking.rank_top_entities,
        filtered_rank_fallback_values=ranking.filtered_rank_fallback_values,
        build_entity_specific_contact_rows=ranking.build_entity_specific_contact_rows,
        build_entity_specific_team_rows=ranking.build_entity_specific_team_rows,
        build_sections=delivery.build_sections,
        evidence_density_level=delivery.evidence_density_level,
        source_quality_level=delivery.source_quality_level,
        source_documents_to_research_source_outputs=source_documents_to_research_source_outputs,
        enrich_report_for_delivery=delivery.enrich_report_for_delivery,
        sanitize_report_result_entities=delivery.sanitize_report_result_entities,
        enforce_report_entity_authenticity=delivery.enforce_report_entity_authenticity,
        is_low_signal_execution_report=lambda report: is_low_signal_execution_report(
            report,
            deps=report_readiness_dependencies(owners),
        ),
        theme_labels_from_scope=scope_entity.theme_labels_from_scope,
        source_supports_target_account=ranking.source_supports_target_account,
        summary_fact_rows=summary_fact_rows,
        compress_title_segments=delivery.compress_title_segments,
        scope_anchor_text_segments=scope.scope_anchor_text_segments,
        build_guarded_rewrite_title=delivery.build_guarded_rewrite_title,
        source_max_age_years=delivery.source_max_age_years,
    )
