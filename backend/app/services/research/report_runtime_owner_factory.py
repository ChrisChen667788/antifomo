from __future__ import annotations

from app.services.research.entity_ranking import rank_report_entities
from app.services.research.entity_authenticity_gate import (
    enforce_report_entity_authenticity,
    sanitize_report_result_entities,
)
from app.services.research.entity_ranking_runtime import (
    build_entity_specific_contact_rows,
    build_entity_specific_team_rows,
    build_runtime_entity_graph,
    filtered_rank_fallback_values,
    rank_runtime_top_entities,
    source_supports_target_account,
)
from app.services.research.report_delivery_runtime import (
    evidence_density_level,
    merge_result_with_intelligence,
    source_quality_level,
)
from app.services.research.report_delivery_runtime_dependencies import (
    build_sections,
    enrich_report_for_delivery,
)
from app.services.research.report_delivery_strategy_runtime import (
    apply_topic_specific_overrides,
    compress_title_segments,
    summary_contains_output_noise,
)
from app.services.research.report_runtime_dependencies import (
    ReportDeliveryOwnerPorts,
    ReportRankingOwnerPorts,
    ReportRuntimeOwnerPorts,
    ReportScopeOwnerPorts,
    ReportStorageOwnerPorts,
    stored_report_rewrite_dependencies,
)
from app.services.research.report_ranking_runtime import build_runtime_source_diagnostics
from app.services.research.report_scope_runtime import (
    collect_matched_theme_labels,
    prune_industry_hints,
    scope_anchor_text_segments,
)
from app.services.research.scope_hints import (
    infer_input_scope_hints,
    infer_scope_hints,
    merge_scope_hints,
    source_theme_match_score,
)
from app.services.research.report_storage_runtime import (
    report_intelligence_from_result,
    report_sources_to_documents,
    stored_report_to_runtime_result,
)
from app.services.research.stored_entity_runtime_dependencies import (
    canonicalize_entity_name,
    canonicalize_report_entities,
    canonicalize_result_entities,
    clean_candidate_company_names,
)
from app.services.research.scope_entity_runtime_dependencies import scope_entity_runtime_functions
from app.services.research.source_scope_policy import SOURCE_MAX_AGE_YEARS
from app.services.research.source_intelligence_runtime import build_source_intelligence
from app.services.research.stored_report_rewrite import (
    apply_guarded_rewrite_diagnostics,
    assess_stored_report_rewrite_mode,
    build_guarded_rewrite_title,
    resolve_stored_report_target_support,
)


def build_report_runtime_owner_ports() -> ReportRuntimeOwnerPorts:
    ports_ref: dict[str, ReportRuntimeOwnerPorts] = {}

    def current_rewrite_dependencies():
        return stored_report_rewrite_dependencies(ports_ref["ports"])

    def bound_resolve_stored_report_target_support(*args, **kwargs):
        return resolve_stored_report_target_support(
            *args,
            **kwargs,
            deps=current_rewrite_dependencies(),
        )

    def bound_apply_guarded_rewrite_diagnostics(*args, **kwargs):
        return apply_guarded_rewrite_diagnostics(
            *args,
            **kwargs,
            deps=current_rewrite_dependencies(),
        )

    def bound_assess_stored_report_rewrite_mode(*args, **kwargs):
        return assess_stored_report_rewrite_mode(
            *args,
            **kwargs,
            deps=current_rewrite_dependencies(),
        )

    def bound_build_guarded_rewrite_title(*args, **kwargs):
        return build_guarded_rewrite_title(
            *args,
            **kwargs,
            deps=current_rewrite_dependencies(),
        )

    ports = ReportRuntimeOwnerPorts(
        scope=ReportScopeOwnerPorts(
            scope_entity=scope_entity_runtime_functions(),
            source_theme_match_score=source_theme_match_score,
            infer_input_scope_hints=infer_input_scope_hints,
            merge_scope_hints=merge_scope_hints,
            infer_scope_hints=infer_scope_hints,
            prune_industry_hints=prune_industry_hints,
            collect_matched_theme_labels=collect_matched_theme_labels,
            scope_anchor_text_segments=scope_anchor_text_segments,
        ),
        storage=ReportStorageOwnerPorts(
            report_sources_to_source_documents=report_sources_to_documents,
            canonicalize_stored_report_entities=canonicalize_report_entities,
            canonicalize_stored_entity_name=canonicalize_entity_name,
            clean_candidate_profile_company_names=clean_candidate_company_names,
            resolve_stored_report_target_support=bound_resolve_stored_report_target_support,
            apply_guarded_rewrite_diagnostics=bound_apply_guarded_rewrite_diagnostics,
            assess_stored_report_rewrite_mode=bound_assess_stored_report_rewrite_mode,
            stored_report_to_result=stored_report_to_runtime_result,
            report_intelligence_from_result=report_intelligence_from_result,
            canonicalize_stored_result_entities=canonicalize_result_entities,
        ),
        ranking=ReportRankingOwnerPorts(
            source_supports_target_account=source_supports_target_account,
            build_entity_graph=build_runtime_entity_graph,
            build_source_diagnostics=build_runtime_source_diagnostics,
            rank_report_entities=rank_report_entities,
            rank_top_entities=rank_runtime_top_entities,
            filtered_rank_fallback_values=filtered_rank_fallback_values,
            build_entity_specific_contact_rows=build_entity_specific_contact_rows,
            build_entity_specific_team_rows=build_entity_specific_team_rows,
        ),
        delivery=ReportDeliveryOwnerPorts(
            compress_title_segments=compress_title_segments,
            summary_contains_output_noise=summary_contains_output_noise,
            build_source_intelligence=build_source_intelligence,
            merge_result_with_intelligence=merge_result_with_intelligence,
            apply_topic_specific_overrides=apply_topic_specific_overrides,
            build_sections=build_sections,
            evidence_density_level=evidence_density_level,
            source_quality_level=source_quality_level,
            enrich_report_for_delivery=enrich_report_for_delivery,
            sanitize_report_result_entities=sanitize_report_result_entities,
            enforce_report_entity_authenticity=enforce_report_entity_authenticity,
            build_guarded_rewrite_title=bound_build_guarded_rewrite_title,
            source_max_age_years=SOURCE_MAX_AGE_YEARS,
        ),
    )
    ports_ref["ports"] = ports
    return ports
