from __future__ import annotations

from dataclasses import dataclass, replace
import logging
from typing import Any

from app.schemas.research import ResearchReportRequest, ResearchReportResponse
from app.services.research.candidate_profile_enrichment import CandidateProfileEnrichmentDependencies
from app.services.research.clarification import (
    attach_research_interaction,
    is_provisional_evidence_eligible,
)
from app.services.research.company_source_enrichment import CompanySourceEnrichmentDependencies
from app.services.research.corrective_expansion import CorrectiveExpansionDependencies
from app.services.research.evidence_expansion import EvidenceExpansionDependencies
from app.services.research.generation_execution import ResearchGenerationExecutionDependencies
from app.services.research.source_documents import SourceDocument


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ResearchWorkflowProgressPorts:
    emit_research_progress: Any
    build_progress_message: Any
    emit_research_snapshot: Any


@dataclass(frozen=True, slots=True)
class ResearchWorkflowSourceCollectionPorts:
    build_query_plan: Any
    source_collection_collect_adapter_hits: Any
    collect_enabled_source_hits: Any
    build_user_supplied_hits: Any
    build_user_supplied_documents: Any
    source_collection_collect_public_search_hits: Any
    search_public_web: Any
    dedupe_hits: Any
    source_collection_extract_initial_sources: Any
    hybrid_rank_hits: Any
    select_hits_with_source_balance: Any
    extract_source_document: Any
    filter_recent_sources: Any
    refine_sources_for_report: Any
    build_company_contact_query_plan: Any
    build_company_profile_query_plan: Any
    build_company_seed_hits: Any
    build_company_team_query_plan: Any
    classify_source_tier: Any
    classify_source_type: Any
    derive_source_label: Any
    extract_source_document_best_effort: Any
    dedupe_sources: Any
    report_sources_to_source_documents: Any
    build_source_intelligence: Any
    build_expanded_query_plan: Any
    build_corrective_query_plan: Any
    source_max_age_years: int


@dataclass(frozen=True, slots=True)
class ResearchWorkflowScopePorts:
    dedupe_strings: Any
    merge_scope_hints: Any
    infer_scope_hints: Any
    build_theme_terms: Any
    extract_topic_anchor_terms: Any
    resolved_company_anchor_terms: Any
    region_conflict_signature: Any
    source_has_region_conflict: Any
    collect_theme_seed_companies: Any
    collect_matched_theme_labels: Any


@dataclass(frozen=True, slots=True)
class ResearchWorkflowEnrichmentPorts:
    company_source_enrichment_enrich: Any
    evidence_expansion_apply: Any
    corrective_expansion_apply: Any
    tender_detail_enrichment_apply: Any
    tender_detail_dependencies: Any
    candidate_profile_enrichment_enrich: Any


@dataclass(frozen=True, slots=True)
class ResearchWorkflowGenerationPorts:
    generation_execution_execute: Any
    load_runtime_research_retrieval_index: Any
    attach_section_retrieval_packs: Any
    render_section_retrieval_prompt_context: Any
    render_followup_section_focus_prompt_context: Any
    build_partial_report_result: Any
    render_followup_diagnostics_prompt_context: Any
    build_partial_report_response: Any
    retrieval_orchestration_build_section_runtime_context: Any
    render_source_digest: Any
    render_followup_prompt_context: Any
    render_retrieval_correction_context: Any
    render_industry_methodology_context: Any
    parse_research_report_response: Any
    merge_result_with_intelligence: Any
    apply_topic_specific_overrides: Any
    apply_strategy_llm_refinement: Any
    render_question_tree_prompt_context: Any
    enforce_entity_authenticity: Any


@dataclass(frozen=True, slots=True)
class ResearchWorkflowRankingPorts:
    build_entity_graph: Any
    entity_ranking_rank_report_entities: Any
    rank_top_entities: Any
    filtered_rank_fallback_values: Any
    entity_ranking_promote_with_profiles: Any
    build_candidate_profile_support: Any
    promote_pending_entities_with_candidate_profiles: Any
    build_entity_specific_contact_rows: Any
    build_entity_specific_team_rows: Any


@dataclass(frozen=True, slots=True)
class ResearchWorkflowAssemblyPorts:
    report_assembly_assemble_final_report: Any
    build_sections: Any
    source_documents_to_outputs: Any
    enrich_report_for_delivery: Any
    sanitize_report_response_fields: Any
    stabilize_report_header: Any


@dataclass(frozen=True, slots=True)
class ResearchWorkflowQualityPorts:
    concrete_rows: Any
    company_convergence_is_weak: Any
    official_coverage_is_weak: Any
    retrieval_quality_band: Any
    build_retrieval_correction_profile: Any
    build_source_diagnostics: Any
    evidence_density_level: Any
    source_quality_level: Any
    review_generation_grounding: Any
    evaluate_and_improve_research_report: Any
    expand_report_public_sources_until_quality_improves: Any
    build_research_evidence_governance: Any
    apply_evidence_governance_diagnostics: Any
    build_evidence_gap_report: Any
    build_research_claim_governance: Any
    load_recent_evidence_snapshot: Any
    load_evidence_snapshot_by_job_id: Any
    enforce_report_entity_authenticity: Any


def _append_evidence_gate_warning(governance: Any, warning: str) -> Any:
    if not warning:
        return governance
    warnings = list(governance.gate.warnings)
    if warning not in warnings:
        warnings.append(warning)
    return replace(
        governance,
        gate=governance.gate.model_copy(update={"warnings": warnings[:8]}),
    )


def _build_snapshot_recovery_scope_hints(
    *,
    input_scope_hints: dict[str, object],
    current_scope_hints: dict[str, object],
    inferred_scope_hints: dict[str, object],
    merge_scope_hints: Any,
) -> dict[str, object]:
    recovered_scope_hints = dict(merge_scope_hints(input_scope_hints, inferred_scope_hints))
    for scope_key, scope_value in current_scope_hints.items():
        if scope_key.startswith("runtime_"):
            recovered_scope_hints[scope_key] = scope_value
    if bool(input_scope_hints.get("input_scope_locked")):
        for scope_key, default_value in (
            ("clients", []),
            ("company_anchors", []),
            ("seed_companies", []),
            ("prefer_company_entities", False),
            ("prefer_head_companies", False),
        ):
            recovered_scope_hints[scope_key] = input_scope_hints.get(scope_key, default_value)
    return recovered_scope_hints


def _accumulate_snapshot_source_pool(
    current_pool: list[SourceDocument],
    snapshot_sources: list[SourceDocument],
    *,
    dedupe_sources: Any,
) -> list[SourceDocument]:
    return dedupe_sources([*current_pool, *snapshot_sources])


@dataclass(frozen=True, slots=True)
class ResearchGenerationWorkflowDependencies:
    progress: ResearchWorkflowProgressPorts
    source_collection: ResearchWorkflowSourceCollectionPorts
    scope: ResearchWorkflowScopePorts
    enrichment: ResearchWorkflowEnrichmentPorts
    generation: ResearchWorkflowGenerationPorts
    ranking: ResearchWorkflowRankingPorts
    assembly: ResearchWorkflowAssemblyPorts
    quality: ResearchWorkflowQualityPorts


def run_research_generation_workflow(
    payload: ResearchReportRequest,
    *,
    setup: Any,
    progress_callback: Any | None = None,
    snapshot_callback: Any | None = None,
    deps: ResearchGenerationWorkflowDependencies,
) -> ResearchReportResponse:
    progress = deps.progress
    source_collection = deps.source_collection
    scope = deps.scope
    enrichment = deps.enrichment
    generation = deps.generation
    ranking = deps.ranking
    assembly = deps.assembly
    quality = deps.quality

    _emit_research_progress = progress.emit_research_progress
    _build_progress_message = progress.build_progress_message
    _build_query_plan = source_collection.build_query_plan
    _dedupe_strings = scope.dedupe_strings
    _source_collection_collect_adapter_hits = source_collection.source_collection_collect_adapter_hits
    collect_enabled_source_hits = source_collection.collect_enabled_source_hits
    _build_user_supplied_hits = source_collection.build_user_supplied_hits
    _build_user_supplied_documents = source_collection.build_user_supplied_documents
    _source_collection_collect_public_search_hits = source_collection.source_collection_collect_public_search_hits
    _search_public_web = source_collection.search_public_web
    _dedupe_hits = source_collection.dedupe_hits
    _source_collection_extract_initial_sources = source_collection.source_collection_extract_initial_sources
    _hybrid_rank_hits = source_collection.hybrid_rank_hits
    _select_hits_with_source_balance = source_collection.select_hits_with_source_balance
    _extract_source_document = source_collection.extract_source_document
    _filter_recent_sources = source_collection.filter_recent_sources
    _merge_scope_hints = scope.merge_scope_hints
    _infer_scope_hints = scope.infer_scope_hints
    _build_theme_terms = scope.build_theme_terms
    _extract_topic_anchor_terms = scope.extract_topic_anchor_terms
    _resolved_company_anchor_terms = scope.resolved_company_anchor_terms
    _region_conflict_signature = scope.region_conflict_signature
    _source_has_region_conflict = scope.source_has_region_conflict
    _refine_sources_for_report = source_collection.refine_sources_for_report
    _collect_theme_seed_companies = scope.collect_theme_seed_companies
    _company_source_enrichment_enrich = enrichment.company_source_enrichment_enrich
    _build_company_contact_query_plan = source_collection.build_company_contact_query_plan
    _build_company_profile_query_plan = source_collection.build_company_profile_query_plan
    _build_company_seed_hits = source_collection.build_company_seed_hits
    _classify_source_tier = source_collection.classify_source_tier
    _classify_source_type = source_collection.classify_source_type
    _derive_source_label = source_collection.derive_source_label
    _extract_source_document_best_effort = source_collection.extract_source_document_best_effort
    _dedupe_sources = source_collection.dedupe_sources
    _report_sources_to_source_documents = source_collection.report_sources_to_source_documents
    _build_source_intelligence = source_collection.build_source_intelligence
    _evidence_expansion_apply = enrichment.evidence_expansion_apply
    _concrete_rows = quality.concrete_rows
    _company_convergence_is_weak = quality.company_convergence_is_weak
    _official_coverage_is_weak = quality.official_coverage_is_weak
    _build_expanded_query_plan = source_collection.build_expanded_query_plan
    _corrective_expansion_apply = enrichment.corrective_expansion_apply
    _retrieval_quality_band = quality.retrieval_quality_band
    build_retrieval_correction_profile = quality.build_retrieval_correction_profile
    _build_corrective_query_plan = source_collection.build_corrective_query_plan
    _tender_detail_enrichment_apply = enrichment.tender_detail_enrichment_apply
    _tender_detail_dependencies = enrichment.tender_detail_dependencies
    _build_entity_graph = ranking.build_entity_graph
    _collect_matched_theme_labels = scope.collect_matched_theme_labels
    _build_source_diagnostics = quality.build_source_diagnostics
    SOURCE_MAX_AGE_YEARS = source_collection.source_max_age_years
    _generation_execution_execute = generation.generation_execution_execute
    _load_runtime_research_retrieval_index = generation.load_runtime_research_retrieval_index
    attach_section_retrieval_packs = generation.attach_section_retrieval_packs
    _render_section_retrieval_prompt_context = generation.render_section_retrieval_prompt_context
    _render_followup_section_focus_prompt_context = generation.render_followup_section_focus_prompt_context
    _build_partial_report_result = generation.build_partial_report_result
    _render_followup_diagnostics_prompt_context = generation.render_followup_diagnostics_prompt_context
    _build_partial_report_response = generation.build_partial_report_response
    _retrieval_orchestration_build_section_runtime_context = generation.retrieval_orchestration_build_section_runtime_context
    _emit_research_snapshot = progress.emit_research_snapshot
    _render_source_digest = generation.render_source_digest
    _render_followup_prompt_context = generation.render_followup_prompt_context
    render_retrieval_correction_context = generation.render_retrieval_correction_context
    _render_industry_methodology_context = generation.render_industry_methodology_context
    parse_research_report_response = generation.parse_research_report_response
    _merge_result_with_intelligence = generation.merge_result_with_intelligence
    _apply_topic_specific_overrides = generation.apply_topic_specific_overrides
    _apply_strategy_llm_refinement = generation.apply_strategy_llm_refinement
    _render_question_tree_prompt_context = generation.render_question_tree_prompt_context
    _enforce_entity_authenticity = generation.enforce_entity_authenticity
    _entity_ranking_rank_report_entities = ranking.entity_ranking_rank_report_entities
    _rank_top_entities = ranking.rank_top_entities
    _filtered_rank_fallback_values = ranking.filtered_rank_fallback_values
    _candidate_profile_enrichment_enrich = enrichment.candidate_profile_enrichment_enrich
    _build_company_team_query_plan = source_collection.build_company_team_query_plan
    _entity_ranking_promote_with_profiles = ranking.entity_ranking_promote_with_profiles
    _build_candidate_profile_support = ranking.build_candidate_profile_support
    _promote_pending_entities_with_candidate_profiles = ranking.promote_pending_entities_with_candidate_profiles
    _build_entity_specific_contact_rows = ranking.build_entity_specific_contact_rows
    _build_entity_specific_team_rows = ranking.build_entity_specific_team_rows
    _report_assembly_assemble_final_report = assembly.report_assembly_assemble_final_report
    _evidence_density_level = quality.evidence_density_level
    _source_quality_level = quality.source_quality_level
    _build_sections = assembly.build_sections
    _to_research_source_outputs = assembly.source_documents_to_outputs
    _enrich_report_for_delivery = assembly.enrich_report_for_delivery
    _sanitize_report_response_fields = assembly.sanitize_report_response_fields
    _stabilize_report_header = assembly.stabilize_report_header
    review_generation_grounding = quality.review_generation_grounding
    evaluate_and_improve_research_report = quality.evaluate_and_improve_research_report
    _expand_report_public_sources_until_quality_improves = quality.expand_report_public_sources_until_quality_improves
    _build_research_evidence_governance = quality.build_research_evidence_governance
    _apply_evidence_governance_diagnostics = quality.apply_evidence_governance_diagnostics
    _build_evidence_gap_report = quality.build_evidence_gap_report
    _build_research_claim_governance = quality.build_research_claim_governance
    _load_recent_evidence_snapshot = quality.load_recent_evidence_snapshot
    _load_evidence_snapshot_by_job_id = quality.load_evidence_snapshot_by_job_id
    _enforce_report_entity_authenticity = quality.enforce_report_entity_authenticity

    settings = setup.settings
    llm = setup.llm
    keyword = setup.keyword
    report_research_focus = setup.report_research_focus
    followup_context = setup.followup_context
    followup_diagnostics = setup.followup_diagnostics
    research_focus = setup.research_focus
    output_language = setup.output_language
    research_mode = setup.research_mode
    runtime = setup.runtime
    preferred_wechat_accounts = setup.preferred_wechat_accounts
    input_scope_hints = setup.input_scope_hints
    base_input_scope_hints = setup.base_input_scope_hints
    archive_context = setup.archive_context
    clarification_runtime = (
        payload.runtime_strategy_config.get("clarification_recovery", {})
        if isinstance(payload.runtime_strategy_config, dict)
        else {}
    )
    delta_rebuild_requested = bool(clarification_runtime.get("delta_rebuild"))

    _emit_research_progress(
        progress_callback,
        "planning",
        6,
        _build_progress_message("正在规划检索路径", keyword=keyword, research_focus=research_focus, mode=research_mode),
    )
    query_plan = _build_query_plan(
        keyword,
        research_focus,
        payload.include_wechat,
        scope_hints=input_scope_hints,
        preferred_wechat_accounts=preferred_wechat_accounts,
        limit=int(runtime["query_limit"]),
    )
    if followup_diagnostics.enabled and followup_diagnostics.decomposition_queries:
        query_plan = _dedupe_strings(
            [*followup_diagnostics.decomposition_queries, *query_plan],
            max(int(runtime["query_limit"]) + 4, len(followup_diagnostics.decomposition_queries) + 2),
        )
    if delta_rebuild_requested:
        delta_queries = (
            list(followup_diagnostics.decomposition_queries)
            if followup_diagnostics.enabled
            else []
        )
        query_plan = _dedupe_strings(
            [*delta_queries, *query_plan[:2]],
            min(6, max(2, len(delta_queries) + 2)),
        )
    _emit_research_progress(
        progress_callback,
        "adapters",
        14,
        _build_progress_message("正在汇总定向信息源", keyword=keyword, research_focus=research_focus, mode=research_mode),
    )
    adapter_collection = _source_collection_collect_adapter_hits(
        keyword=keyword,
        research_focus=research_focus,
        runtime=runtime,
        collect_enabled_source_hits=collect_enabled_source_hits,
    )
    user_supplied_hits = _build_user_supplied_hits(payload.supplemental_evidence)
    if user_supplied_hits:
        adapter_collection = replace(
            adapter_collection,
            search_hits=_dedupe_hits([*adapter_collection.search_hits, *user_supplied_hits]),
            adapter_query_plan=[*adapter_collection.adapter_query_plan, "user:supplemental"],
        )
    adapter_settings = adapter_collection.adapter_settings
    adapter_query_plan = adapter_collection.adapter_query_plan
    _emit_research_progress(
        progress_callback,
        "search",
        26,
        _build_progress_message("正在检索公开网页与招采来源", keyword=keyword, research_focus=research_focus, mode=research_mode),
    )
    public_search_collection = _source_collection_collect_public_search_hits(
        search_hits=adapter_collection.search_hits,
        query_plan=query_plan,
        runtime=runtime,
        search_public_web=_search_public_web,
        dedupe_hits=_dedupe_hits,
    )
    search_hits = public_search_collection.search_hits
    effective_query_plan = public_search_collection.effective_query_plan
    _emit_research_progress(
        progress_callback,
        "extracting",
        42,
        _build_progress_message("正在抽取正文与证据片段", keyword=keyword, research_focus=research_focus, mode=research_mode),
    )
    initial_source_extraction = _source_collection_extract_initial_sources(
        search_hits=search_hits,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=input_scope_hints,
        runtime=runtime,
        max_sources=settings.research_max_sources,
        excerpt_chars=settings.research_source_excerpt_chars,
        hybrid_rank_hits=_hybrid_rank_hits,
        select_hits_with_source_balance=_select_hits_with_source_balance,
        extract_source_document=_extract_source_document,
        filter_recent_sources=_filter_recent_sources,
    )
    sources = initial_source_extraction.sources
    user_supplied_documents = _build_user_supplied_documents(payload.supplemental_documents)
    if user_supplied_documents:
        sources = _dedupe_sources([*sources, *user_supplied_documents])
    parent_snapshot_job_id = str(
        clarification_runtime.get("parent_job_id") or ""
    ).strip()
    parent_snapshot = None
    if parent_snapshot_job_id:
        try:
            parent_snapshot = _load_evidence_snapshot_by_job_id(
                job_id=parent_snapshot_job_id,
                keyword=keyword,
                research_focus=report_research_focus,
                max_age_hours=int(clarification_runtime.get("snapshot_max_age_hours") or 168),
            )
        except Exception:
            logger.exception("Unable to load the requested parent evidence snapshot")
    if parent_snapshot is not None:
        sources = _dedupe_sources([*sources, *parent_snapshot.sources])
    filtered_old_source_count = initial_source_extraction.filtered_old_source_count
    filtered_region_conflict_signatures: set[str] = set()

    _emit_research_progress(
        progress_callback,
        "scoping",
        56,
        _build_progress_message("正在收敛区域、行业与客户范围", keyword=keyword, research_focus=research_focus, mode=research_mode),
    )
    scope_hints = _merge_scope_hints(input_scope_hints, _infer_scope_hints(keyword, research_focus, sources))
    theme_terms = _build_theme_terms(keyword, research_focus, scope_hints)
    topic_anchor_terms = _extract_topic_anchor_terms(keyword, research_focus)
    company_anchor_terms = _resolved_company_anchor_terms(keyword, research_focus, scope_hints)
    expansion_triggered = False
    corrective_triggered = False
    candidate_profile_companies: list[str] = []
    candidate_profile_hit_count = 0
    candidate_profile_official_hit_count = 0
    candidate_profile_source_labels: list[str] = []
    candidate_profile_sources: list[SourceDocument] = []
    filtered_region_conflict_signatures.update(
        _region_conflict_signature(source)
        for source in sources
        if _source_has_region_conflict(source, scope_hints=scope_hints)
    )
    sources = _refine_sources_for_report(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
        company_anchor_terms=company_anchor_terms,
        theme_terms=theme_terms,
    )
    strict_topic_source_count = len(sources)
    theme_seed_companies = _collect_theme_seed_companies(
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
    )
    company_enrichment = _company_source_enrichment_enrich(
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        research_mode=research_mode,
        sources=sources,
        input_scope_hints=input_scope_hints,
        explicit_scope_hints=base_input_scope_hints,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        company_anchor_terms=company_anchor_terms,
        theme_seed_companies=theme_seed_companies,
        runtime=runtime,
        source_excerpt_chars=settings.research_source_excerpt_chars,
        progress_callback=progress_callback,
        deps=CompanySourceEnrichmentDependencies(
            dedupe_strings=_dedupe_strings,
            build_company_contact_query_plan=_build_company_contact_query_plan,
            build_company_profile_query_plan=_build_company_profile_query_plan,
            emit_research_progress=_emit_research_progress,
            build_progress_message=_build_progress_message,
            build_company_seed_hits=_build_company_seed_hits,
            search_public_web=_search_public_web,
            hybrid_rank_hits=_hybrid_rank_hits,
            select_hits_with_source_balance=_select_hits_with_source_balance,
            dedupe_hits=_dedupe_hits,
            classify_source_tier=_classify_source_tier,
            classify_source_type=_classify_source_type,
            derive_source_label=_derive_source_label,
            extract_source_document_best_effort=_extract_source_document_best_effort,
            dedupe_sources=_dedupe_sources,
            region_conflict_signature=_region_conflict_signature,
            source_has_region_conflict=_source_has_region_conflict,
            refine_sources_for_report=_refine_sources_for_report,
            merge_scope_hints=_merge_scope_hints,
            infer_scope_hints=_infer_scope_hints,
            build_theme_terms=_build_theme_terms,
            build_source_intelligence=_build_source_intelligence,
        ),
    )
    sources = company_enrichment.sources
    scope_hints = company_enrichment.scope_hints
    theme_terms = company_enrichment.theme_terms
    source_intelligence = company_enrichment.source_intelligence
    filtered_region_conflict_signatures.update(company_enrichment.region_conflict_signatures)
    evidence_expansion = _evidence_expansion_apply(
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        research_mode=research_mode,
        sources=sources,
        search_hits=search_hits,
        source_intelligence=source_intelligence,
        input_scope_hints=input_scope_hints,
        explicit_scope_hints=base_input_scope_hints,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        company_anchor_terms=company_anchor_terms,
        effective_query_plan=effective_query_plan,
        strict_topic_source_count=strict_topic_source_count,
        filtered_old_source_count=filtered_old_source_count,
        runtime=runtime,
        include_wechat=payload.include_wechat,
        preferred_wechat_accounts=preferred_wechat_accounts,
        source_excerpt_chars=settings.research_source_excerpt_chars,
        progress_callback=progress_callback,
        deps=EvidenceExpansionDependencies(
            concrete_rows=_concrete_rows,
            company_convergence_is_weak=_company_convergence_is_weak,
            official_coverage_is_weak=_official_coverage_is_weak,
            emit_research_progress=_emit_research_progress,
            build_progress_message=_build_progress_message,
            build_expanded_query_plan=_build_expanded_query_plan,
            collect_enabled_source_hits=collect_enabled_source_hits,
            search_public_web=_search_public_web,
            hybrid_rank_hits=_hybrid_rank_hits,
            select_hits_with_source_balance=_select_hits_with_source_balance,
            extract_source_document_best_effort=_extract_source_document_best_effort,
            filter_recent_sources=_filter_recent_sources,
            dedupe_strings=_dedupe_strings,
            dedupe_sources=_dedupe_sources,
            region_conflict_signature=_region_conflict_signature,
            source_has_region_conflict=_source_has_region_conflict,
            refine_sources_for_report=_refine_sources_for_report,
            merge_scope_hints=_merge_scope_hints,
            infer_scope_hints=_infer_scope_hints,
            build_theme_terms=_build_theme_terms,
            resolved_company_anchor_terms=_resolved_company_anchor_terms,
            build_source_intelligence=_build_source_intelligence,
        ),
    )
    sources = evidence_expansion.sources
    effective_query_plan = evidence_expansion.effective_query_plan
    filtered_old_source_count = evidence_expansion.filtered_old_source_count
    filtered_region_conflict_signatures.update(evidence_expansion.region_conflict_signatures)
    scope_hints = evidence_expansion.scope_hints
    theme_terms = evidence_expansion.theme_terms
    company_anchor_terms = evidence_expansion.company_anchor_terms
    source_intelligence = evidence_expansion.source_intelligence
    strict_topic_source_count = evidence_expansion.strict_topic_source_count
    expansion_triggered = evidence_expansion.expansion_triggered
    corrective_expansion = _corrective_expansion_apply(
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        research_mode=research_mode,
        sources=sources,
        source_intelligence=source_intelligence,
        input_scope_hints=input_scope_hints,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        company_anchor_terms=company_anchor_terms,
        theme_seed_companies=theme_seed_companies,
        effective_query_plan=effective_query_plan,
        strict_topic_source_count=strict_topic_source_count,
        filtered_old_source_count=filtered_old_source_count,
        runtime=runtime,
        include_wechat=payload.include_wechat,
        preferred_wechat_accounts=preferred_wechat_accounts,
        source_excerpt_chars=settings.research_source_excerpt_chars,
        max_sources=settings.research_max_sources,
        progress_callback=progress_callback,
        deps=CorrectiveExpansionDependencies(
            company_convergence_is_weak=_company_convergence_is_weak,
            retrieval_quality_band=_retrieval_quality_band,
            build_retrieval_correction_profile=build_retrieval_correction_profile,
            emit_research_progress=_emit_research_progress,
            build_progress_message=_build_progress_message,
            build_corrective_query_plan=_build_corrective_query_plan,
            dedupe_strings=_dedupe_strings,
            build_company_seed_hits=_build_company_seed_hits,
            search_public_web=_search_public_web,
            hybrid_rank_hits=_hybrid_rank_hits,
            select_hits_with_source_balance=_select_hits_with_source_balance,
            dedupe_hits=_dedupe_hits,
            extract_source_document_best_effort=_extract_source_document_best_effort,
            filter_recent_sources=_filter_recent_sources,
            dedupe_sources=_dedupe_sources,
            region_conflict_signature=_region_conflict_signature,
            source_has_region_conflict=_source_has_region_conflict,
            refine_sources_for_report=_refine_sources_for_report,
            merge_scope_hints=_merge_scope_hints,
            infer_scope_hints=_infer_scope_hints,
            build_theme_terms=_build_theme_terms,
            resolved_company_anchor_terms=_resolved_company_anchor_terms,
            build_source_intelligence=_build_source_intelligence,
        ),
    )
    sources = corrective_expansion.sources
    effective_query_plan = corrective_expansion.effective_query_plan
    filtered_old_source_count = corrective_expansion.filtered_old_source_count
    filtered_region_conflict_signatures.update(corrective_expansion.region_conflict_signatures)
    scope_hints = corrective_expansion.scope_hints
    theme_terms = corrective_expansion.theme_terms
    company_anchor_terms = corrective_expansion.company_anchor_terms
    source_intelligence = corrective_expansion.source_intelligence
    corrective_triggered = corrective_triggered or corrective_expansion.corrective_triggered
    retrieval_correction_profile = corrective_expansion.retrieval_correction_profile
    tender_detail_enrichment = _tender_detail_enrichment_apply(
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        research_mode=research_mode,
        sources=sources,
        source_intelligence=source_intelligence,
        input_scope_hints=input_scope_hints,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        company_anchor_terms=company_anchor_terms,
        effective_query_plan=effective_query_plan,
        runtime=runtime,
        source_excerpt_chars=settings.research_source_excerpt_chars,
        progress_callback=progress_callback,
        deps=_tender_detail_dependencies(),
    )
    sources = tender_detail_enrichment.sources
    effective_query_plan = tender_detail_enrichment.effective_query_plan
    scope_hints = tender_detail_enrichment.scope_hints
    theme_terms = tender_detail_enrichment.theme_terms
    company_anchor_terms = tender_detail_enrichment.company_anchor_terms
    source_intelligence = tender_detail_enrichment.source_intelligence
    evidence_governance = _build_research_evidence_governance(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        research_mode=research_mode,
        scope_hints=scope_hints,
    )
    question_query_limit = (
        6
        if research_mode == "deep"
        else max(1, min(int(runtime.get("corrective_query_limit", 4)), 4))
    )
    question_queries = list(evidence_governance.question_tree.corrective_queries[:question_query_limit])
    if (
        research_mode == "deep"
        and not evidence_governance.gate.passed
        and evidence_governance.gate.status in {"evidence_gap", "blocked_topic_mismatch"}
        and not question_queries
    ):
        question_queries = _dedupe_strings(
            [
                *_build_corrective_query_plan(
                    keyword=keyword,
                    research_focus=research_focus,
                    scope_hints=scope_hints,
                    include_wechat=payload.include_wechat,
                    preferred_wechat_accounts=preferred_wechat_accounts,
                    limit=max(6, question_query_limit),
                ),
                *_build_expanded_query_plan(
                    keyword,
                    research_focus,
                    scope_hints=scope_hints,
                    include_wechat=payload.include_wechat,
                    preferred_wechat_accounts=preferred_wechat_accounts,
                    limit=max(6, question_query_limit),
                ),
            ],
            question_query_limit,
        )
    if research_mode == "deep" and not evidence_governance.gate.passed and question_queries:
        _emit_research_progress(
            progress_callback,
            "question_recovery",
            68,
            _build_progress_message(
                "正在按证据缺口逐题补检",
                keyword=keyword,
                research_focus=research_focus,
                mode=research_mode,
            ),
        )
        question_hits = []
        for question_query in question_queries:
            question_hits.extend(
                _search_public_web(
                    question_query,
                    timeout_seconds=min(int(runtime["search_timeout_seconds"]), 10),
                    limit=min(int(runtime["search_result_limit"]), 6),
                )
            )
        ranked_question_hits = _hybrid_rank_hits(
            _dedupe_hits(question_hits),
            keyword=keyword,
            research_focus=research_focus,
            scope_hints=scope_hints,
        )
        selected_question_hits = _select_hits_with_source_balance(
            ranked_question_hits,
            limit=min(int(runtime["expanded_selected_limit"]), 12),
        )
        question_sources: list[SourceDocument] = []
        for hit in selected_question_hits:
            extracted = _extract_source_document_best_effort(
                hit,
                timeout_seconds=int(runtime["url_timeout_seconds"]),
                excerpt_chars=settings.research_source_excerpt_chars,
            )
            if extracted is not None:
                question_sources.append(extracted)
        recent_question_sources = _filter_recent_sources(question_sources)
        filtered_old_source_count += max(0, len(question_sources) - len(recent_question_sources))
        if recent_question_sources:
            sources = _refine_sources_for_report(
                _dedupe_sources([*sources, *recent_question_sources]),
                keyword=keyword,
                research_focus=research_focus,
                scope_hints=scope_hints,
                company_anchor_terms=company_anchor_terms,
                theme_terms=theme_terms,
            )
            effective_query_plan = _dedupe_strings(
                [*effective_query_plan, *question_queries],
                max(len(effective_query_plan) + len(question_queries), 12),
            )
            corrective_triggered = True
            evidence_governance = _build_research_evidence_governance(
                sources,
                keyword=keyword,
                research_focus=research_focus,
                research_mode=research_mode,
                scope_hints=scope_hints,
            )
    parent_snapshot_urls = (
        {source.url for source in parent_snapshot.sources if source.url}
        if parent_snapshot is not None
        else set()
    )
    accepted_parent_snapshot_count = sum(
        source.url in parent_snapshot_urls for source in evidence_governance.accepted_sources
    )
    fresh_source_count = max(
        0,
        evidence_governance.gate.accepted_source_count - accepted_parent_snapshot_count,
    )
    snapshot_recovery_used = parent_snapshot is not None
    snapshot_recovery_source_count = len(parent_snapshot.sources) if parent_snapshot is not None else 0
    snapshot_recovery_job_id = parent_snapshot.job_id if parent_snapshot is not None else ""
    snapshot_recovery_age_hours = parent_snapshot.age_hours if parent_snapshot is not None else 0
    snapshot_recovery_warning = (
        "续跑任务已固定复用父任务证据快照；新增来源仅用于补齐缺口，结论将重新生成。"
        if parent_snapshot is not None
        else ""
    )
    if snapshot_recovery_warning:
        evidence_governance = _append_evidence_gate_warning(
            evidence_governance,
            snapshot_recovery_warning,
        )
    if (
        research_mode == "deep"
        and evidence_governance.gate.status == "evidence_gap"
        and bool(getattr(settings, "research_snapshot_recovery_enabled", True))
    ):
        rejected_snapshot_job_ids: list[str] = []
        snapshot_source_pool: list[SourceDocument] = []
        fresh_urls = {source.url for source in sources if source.url}
        for _snapshot_attempt in range(6):
            try:
                recent_snapshot = _load_recent_evidence_snapshot(
                    keyword=keyword,
                    research_focus=research_focus,
                    max_age_hours=int(getattr(settings, "research_snapshot_recovery_max_age_hours", 48)),
                    excluded_job_ids=tuple(rejected_snapshot_job_ids),
                )
            except Exception:
                logger.exception("Unable to load a recent exact-topic evidence snapshot")
                break
            if recent_snapshot is None:
                break
            rejected_snapshot_job_ids.append(recent_snapshot.job_id)
            snapshot_source_pool = _accumulate_snapshot_source_pool(
                snapshot_source_pool,
                recent_snapshot.sources,
                dedupe_sources=_dedupe_sources,
            )
            recovered_sources = _dedupe_sources([*sources, *snapshot_source_pool])
            recovered_scope_hints = _build_snapshot_recovery_scope_hints(
                input_scope_hints=input_scope_hints,
                current_scope_hints=scope_hints,
                inferred_scope_hints=_infer_scope_hints(keyword, research_focus, recovered_sources),
                merge_scope_hints=_merge_scope_hints,
            )
            recovered_theme_terms = _build_theme_terms(keyword, research_focus, recovered_scope_hints)
            recovered_company_anchor_terms = _resolved_company_anchor_terms(
                keyword,
                research_focus,
                recovered_scope_hints,
            )
            recovered_sources = _refine_sources_for_report(
                recovered_sources,
                keyword=keyword,
                research_focus=research_focus,
                scope_hints=recovered_scope_hints,
                company_anchor_terms=recovered_company_anchor_terms,
                theme_terms=recovered_theme_terms,
            )
            recovered_governance = _build_research_evidence_governance(
                recovered_sources,
                keyword=keyword,
                research_focus=research_focus,
                research_mode=research_mode,
                scope_hints=recovered_scope_hints,
            )
            if not recovered_governance.gate.passed:
                continue
            recovered_url_count = len(
                {
                    source.url
                    for source in recovered_governance.accepted_sources
                    if source.url and source.url not in fresh_urls
                }
            )
            sources = recovered_governance.accepted_sources
            scope_hints = recovered_scope_hints
            theme_terms = recovered_theme_terms
            company_anchor_terms = recovered_company_anchor_terms
            evidence_governance = recovered_governance
            snapshot_recovery_used = True
            snapshot_recovery_source_count = len(snapshot_source_pool)
            snapshot_recovery_job_id = recent_snapshot.job_id
            snapshot_recovery_age_hours = recent_snapshot.age_hours
            snapshot_recovery_warning = (
                f"公开搜索低于硬门槛，累计复用 {len(rejected_snapshot_job_ids)} 个、"
                f"{recent_snapshot.age_hours} 小时内同题任务的 {len(snapshot_source_pool)} 条候选来源"
                f"（本轮新增 {recovered_url_count} 条）；仅复用来源并重新生成结论，仍需新鲜证据复核。"
            )
            evidence_governance = _append_evidence_gate_warning(
                evidence_governance,
                snapshot_recovery_warning,
            )
            _emit_research_progress(
                progress_callback,
                "snapshot_recovery",
                80,
                _build_progress_message(
                    "公开搜索波动，正在复用近期同题证据并重新校验",
                    keyword=keyword,
                    research_focus=research_focus,
                    mode=research_mode,
                ),
            )
            break
    retrieval_correction_profile = build_retrieval_correction_profile(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
        query_plan=effective_query_plan,
        corrective_query_limit=int(runtime.get("corrective_query_limit", 6)),
    )
    sources = evidence_governance.accepted_sources
    scope_hints = {
        **scope_hints,
        "research_scope_namespace": evidence_governance.contract.scope_namespace,
        "research_scope_contract_id": evidence_governance.contract.contract_id,
        "research_question_tree": [
            {
                "question_id": node.question_id,
                "axis": node.axis,
                "question": node.question,
                "coverage_status": node.coverage_status,
                "accepted_source_count": node.accepted_source_count,
            }
            for node in evidence_governance.question_tree.questions
        ],
    }
    source_intelligence = _build_source_intelligence(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        scope_hints=scope_hints,
    )
    entity_graph = _build_entity_graph(
        sources,
        scope_hints=scope_hints,
    )
    matched_theme_labels = _collect_matched_theme_labels(
        sources,
        scope_hints=scope_hints,
        topic_anchor_terms=topic_anchor_terms,
    )
    source_diagnostics = _build_source_diagnostics(
        sources,
        enabled_source_labels=adapter_settings.enabled_labels(),
        scope_hints=scope_hints,
        recency_window_years=SOURCE_MAX_AGE_YEARS,
        filtered_old_source_count=filtered_old_source_count,
        filtered_region_conflict_count=len(filtered_region_conflict_signatures),
        retained_source_count=len(sources),
        strict_topic_source_count=len(sources),
        topic_anchor_terms=topic_anchor_terms,
        matched_theme_labels=matched_theme_labels,
        entity_graph=entity_graph,
        expansion_triggered=expansion_triggered,
        corrective_triggered=corrective_triggered,
        candidate_profile_companies=candidate_profile_companies,
        candidate_profile_hit_count=candidate_profile_hit_count,
        candidate_profile_official_hit_count=candidate_profile_official_hit_count,
        candidate_profile_source_labels=candidate_profile_source_labels,
    )
    source_diagnostics = source_diagnostics.model_copy(update=retrieval_correction_profile.to_diagnostics_update())
    source_diagnostics = _apply_evidence_governance_diagnostics(source_diagnostics, evidence_governance)
    source_diagnostics = source_diagnostics.model_copy(
        update={
            "search_query_count": public_search_collection.query_count,
            "search_hit_count": len(public_search_collection.search_hits),
            "search_retry_count": public_search_collection.retry_count,
            "search_zero_result_query_count": public_search_collection.zero_result_query_count,
            "search_unique_domain_count": public_search_collection.unique_domain_count,
            "fresh_source_count": fresh_source_count,
            "snapshot_recovery_used": snapshot_recovery_used,
            "snapshot_recovery_source_count": snapshot_recovery_source_count,
            "snapshot_recovery_job_id": snapshot_recovery_job_id,
            "snapshot_recovery_age_hours": snapshot_recovery_age_hours,
            "correction_notes": _dedupe_strings(
                [*source_diagnostics.correction_notes, snapshot_recovery_warning],
                10,
            ),
        }
    )
    provisional_generation_allowed = is_provisional_evidence_eligible(
        evidence_governance.gate,
        evidence_governance.contract,
    )
    if not evidence_governance.gate.formal_report_allowed and not provisional_generation_allowed:
        blocked_report = _build_evidence_gap_report(
            keyword=keyword,
            research_focus=report_research_focus,
            output_language=output_language,
            research_mode=research_mode,
            query_plan=[*effective_query_plan, *adapter_query_plan],
            governance=evidence_governance,
            source_diagnostics=source_diagnostics,
            entity_graph=entity_graph,
        )
        blocked_report = _enforce_report_entity_authenticity(
            blocked_report,
            source_documents=sources,
            scope_hints=scope_hints,
        )
        blocked_report = attach_research_interaction(blocked_report)
        _emit_research_snapshot(snapshot_callback, blocked_report)
        return blocked_report
    generation_execution = _generation_execution_execute(
        keyword=keyword,
        research_focus=research_focus,
        report_research_focus=report_research_focus,
        output_language=output_language,
        research_mode=research_mode,
        archive_context=archive_context,
        followup_context=followup_context,
        followup_diagnostics=followup_diagnostics,
        source_intelligence=source_intelligence,
        scope_hints=scope_hints,
        llm=llm,
        runtime=runtime,
        effective_query_plan=effective_query_plan,
        adapter_query_plan=adapter_query_plan,
        sources=sources,
        source_diagnostics=source_diagnostics,
        entity_graph=entity_graph,
        retrieval_correction_profile=retrieval_correction_profile,
        research_question_tree=evidence_governance.question_tree,
        progress_callback=progress_callback,
        snapshot_callback=snapshot_callback,
        section_retrieval_dependencies={
            "load_runtime_research_retrieval_index": _load_runtime_research_retrieval_index,
            "attach_section_retrieval_packs": attach_section_retrieval_packs,
            "render_section_retrieval_prompt_context": _render_section_retrieval_prompt_context,
            "render_followup_section_focus_prompt_context": _render_followup_section_focus_prompt_context,
        },
        deps=ResearchGenerationExecutionDependencies(
            build_partial_report_result=_build_partial_report_result,
            render_followup_diagnostics_prompt_context=_render_followup_diagnostics_prompt_context,
            emit_research_progress=_emit_research_progress,
            build_progress_message=_build_progress_message,
            build_partial_report_response=_build_partial_report_response,
            build_section_retrieval_runtime_context=_retrieval_orchestration_build_section_runtime_context,
            emit_research_snapshot=_emit_research_snapshot,
            render_source_digest=_render_source_digest,
            render_followup_prompt_context=_render_followup_prompt_context,
            render_retrieval_correction_context=render_retrieval_correction_context,
            render_industry_methodology_context=_render_industry_methodology_context,
            parse_research_report_response=parse_research_report_response,
            merge_result_with_intelligence=_merge_result_with_intelligence,
            apply_topic_specific_overrides=_apply_topic_specific_overrides,
            apply_strategy_llm_refinement=_apply_strategy_llm_refinement,
            render_question_tree_prompt_context=_render_question_tree_prompt_context,
            enforce_entity_authenticity=_enforce_entity_authenticity,
        ),
    )
    parsed = generation_execution.parsed
    _emit_research_progress(
        progress_callback,
        "ranking",
        92,
        _build_progress_message("正在生成甲方、竞品与伙伴排序", keyword=keyword, research_focus=research_focus, mode=research_mode),
    )
    rankings = _entity_ranking_rank_report_entities(
        sources=sources,
        parsed=parsed,
        output_language=output_language,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        entity_graph=entity_graph,
        rank_top_entities=_rank_top_entities,
        filtered_rank_fallback_values=_filtered_rank_fallback_values,
        dedupe_strings=_dedupe_strings,
        limit=3,
    )
    candidate_enrichment = _candidate_profile_enrichment_enrich(
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        research_mode=research_mode,
        parsed=parsed,
        sources=sources,
        rankings=rankings,
        input_scope_hints=input_scope_hints,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        company_anchor_terms=company_anchor_terms,
        entity_graph=entity_graph,
        runtime=runtime,
        source_excerpt_chars=settings.research_source_excerpt_chars,
        corrective_triggered=corrective_triggered,
        progress_callback=progress_callback,
        deps=CandidateProfileEnrichmentDependencies(
            dedupe_strings=_dedupe_strings,
            build_company_profile_query_plan=_build_company_profile_query_plan,
            build_company_contact_query_plan=_build_company_contact_query_plan,
            build_company_team_query_plan=_build_company_team_query_plan,
            emit_research_progress=_emit_research_progress,
            build_progress_message=_build_progress_message,
            build_company_seed_hits=_build_company_seed_hits,
            search_public_web=_search_public_web,
            hybrid_rank_hits=_hybrid_rank_hits,
            select_hits_with_source_balance=_select_hits_with_source_balance,
            dedupe_hits=_dedupe_hits,
            extract_source_document_best_effort=_extract_source_document_best_effort,
            dedupe_sources=_dedupe_sources,
            region_conflict_signature=_region_conflict_signature,
            source_has_region_conflict=_source_has_region_conflict,
            refine_sources_for_report=_refine_sources_for_report,
            merge_scope_hints=_merge_scope_hints,
            infer_scope_hints=_infer_scope_hints,
            build_theme_terms=_build_theme_terms,
            resolved_company_anchor_terms=_resolved_company_anchor_terms,
            build_entity_graph=_build_entity_graph,
            rank_top_entities=_rank_top_entities,
            filtered_rank_fallback_values=_filtered_rank_fallback_values,
        ),
    )
    sources = candidate_enrichment.sources
    rankings = candidate_enrichment.rankings
    scope_hints = candidate_enrichment.scope_hints
    theme_terms = candidate_enrichment.theme_terms
    company_anchor_terms = candidate_enrichment.company_anchor_terms
    entity_graph = candidate_enrichment.entity_graph
    corrective_triggered = candidate_enrichment.corrective_triggered
    candidate_profile_sources = candidate_enrichment.candidate_profile_sources
    candidate_profile_companies = candidate_enrichment.candidate_profile_companies
    candidate_profile_hit_count = candidate_enrichment.candidate_profile_hit_count
    candidate_profile_official_hit_count = candidate_enrichment.candidate_profile_official_hit_count
    candidate_profile_source_labels = candidate_enrichment.candidate_profile_source_labels
    filtered_region_conflict_signatures.update(candidate_enrichment.region_conflict_signatures)
    evidence_governance = _build_research_evidence_governance(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        research_mode=research_mode,
        scope_hints=scope_hints,
    )
    evidence_governance = _append_evidence_gate_warning(
        evidence_governance,
        snapshot_recovery_warning,
    )
    sources = evidence_governance.accepted_sources
    entity_graph = _build_entity_graph(sources, scope_hints=scope_hints)
    rankings = _entity_ranking_rank_report_entities(
        sources=sources,
        parsed=parsed,
        output_language=output_language,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        entity_graph=entity_graph,
        rank_top_entities=_rank_top_entities,
        filtered_rank_fallback_values=_filtered_rank_fallback_values,
        dedupe_strings=_dedupe_strings,
        limit=3,
    )
    rankings = _entity_ranking_promote_with_profiles(
        rankings,
        candidate_profile_sources=candidate_profile_sources,
        candidate_profile_companies=candidate_profile_companies,
        build_candidate_profile_support=_build_candidate_profile_support,
        promote_pending_entities_with_candidate_profiles=_promote_pending_entities_with_candidate_profiles,
        limit=3,
    )
    entity_specific_contact_rows = _build_entity_specific_contact_rows(
        sources,
        entity_names=rankings.contact_entity_names(
            scope_clients=list(scope_hints.get("clients", []) or []),
            dedupe_strings=_dedupe_strings,
        ),
        output_language=output_language,
        limit=5,
        scope_hints=scope_hints,
    )
    entity_specific_team_rows = _build_entity_specific_team_rows(
        sources,
        entity_names=rankings.team_entity_names(
            scope_clients=list(scope_hints.get("clients", []) or []),
            dedupe_strings=_dedupe_strings,
        ),
        scope_hints=scope_hints,
        output_language=output_language,
        limit=5,
    )
    merged_public_contact_channels = _dedupe_strings(
        [
            *entity_specific_contact_rows,
            *parsed.public_contact_channels,
        ],
        5,
    )
    merged_account_team_signals = _dedupe_strings(
        [
            *entity_specific_team_rows,
            *parsed.account_team_signals,
        ],
        5,
    )
    matched_theme_labels = _collect_matched_theme_labels(
        sources,
        scope_hints=scope_hints,
        topic_anchor_terms=topic_anchor_terms,
    )
    source_diagnostics = _build_source_diagnostics(
        sources,
        enabled_source_labels=adapter_settings.enabled_labels(),
        scope_hints=scope_hints,
        recency_window_years=SOURCE_MAX_AGE_YEARS,
        filtered_old_source_count=filtered_old_source_count,
        filtered_region_conflict_count=len(filtered_region_conflict_signatures),
        retained_source_count=len(sources),
        strict_topic_source_count=len(sources),
        topic_anchor_terms=topic_anchor_terms,
        matched_theme_labels=matched_theme_labels,
        entity_graph=entity_graph,
        expansion_triggered=expansion_triggered,
        corrective_triggered=corrective_triggered,
        candidate_profile_companies=candidate_profile_companies,
        candidate_profile_hit_count=candidate_profile_hit_count,
        candidate_profile_official_hit_count=candidate_profile_official_hit_count,
        candidate_profile_source_labels=candidate_profile_source_labels,
    )
    source_diagnostics = _apply_evidence_governance_diagnostics(source_diagnostics, evidence_governance)
    source_diagnostics = source_diagnostics.model_copy(
        update={
            "search_query_count": public_search_collection.query_count,
            "search_hit_count": len(public_search_collection.search_hits),
            "search_retry_count": public_search_collection.retry_count,
            "search_zero_result_query_count": public_search_collection.zero_result_query_count,
            "search_unique_domain_count": public_search_collection.unique_domain_count,
            "fresh_source_count": fresh_source_count,
            "snapshot_recovery_used": snapshot_recovery_used,
            "snapshot_recovery_source_count": snapshot_recovery_source_count,
            "snapshot_recovery_job_id": snapshot_recovery_job_id,
            "snapshot_recovery_age_hours": snapshot_recovery_age_hours,
            "correction_notes": _dedupe_strings(
                [*source_diagnostics.correction_notes, snapshot_recovery_warning],
                10,
            ),
            "generation_provider": generation_execution.generation_provider,
            "generation_model": generation_execution.generation_model,
            "generation_status": generation_execution.generation_status,
            "generation_fallback_used": generation_execution.generation_fallback_used,
            "generation_notes": list(generation_execution.generation_notes),
            "entity_authenticity_checked_count": int(
                (generation_execution.entity_authenticity_audit or {}).get("checked_count", 0) or 0
            ),
            "entity_authenticity_rejected_count": int(
                (generation_execution.entity_authenticity_audit or {}).get("rejected_count", 0) or 0
            ),
            "entity_authenticity_repaired_count": int(
                (generation_execution.entity_authenticity_audit or {}).get("repaired_count", 0) or 0
            ),
            "entity_authenticity_unsupported_count": int(
                (generation_execution.entity_authenticity_audit or {}).get("unsupported_count", 0) or 0
            ),
            "entity_authenticity_rejected_samples": list(
                (generation_execution.entity_authenticity_audit or {}).get("rejected_samples", []) or []
            ),
            "entity_authenticity_repair_samples": list(
                (generation_execution.entity_authenticity_audit or {}).get("repair_samples", []) or []
            ),
        }
    )
    provisional_generation_allowed = is_provisional_evidence_eligible(
        evidence_governance.gate,
        evidence_governance.contract,
    )
    if not evidence_governance.gate.formal_report_allowed and not provisional_generation_allowed:
        blocked_report = _build_evidence_gap_report(
            keyword=keyword,
            research_focus=report_research_focus,
            output_language=output_language,
            research_mode=research_mode,
            query_plan=[*effective_query_plan, *adapter_query_plan],
            governance=evidence_governance,
            source_diagnostics=source_diagnostics,
            entity_graph=entity_graph,
        )
        blocked_report = _enforce_report_entity_authenticity(
            blocked_report,
            source_documents=sources,
            scope_hints=scope_hints,
        )
        blocked_report = attach_research_interaction(blocked_report)
        _emit_research_snapshot(snapshot_callback, blocked_report)
        return blocked_report
    _emit_research_progress(
        progress_callback,
        "packaging",
        97,
        _build_progress_message("正在整理结构化结论与来源", keyword=keyword, research_focus=research_focus, mode=research_mode),
    )
    final_report = _report_assembly_assemble_final_report(
        keyword=keyword,
        research_focus=report_research_focus,
        followup_context=followup_context,
        followup_diagnostics=followup_diagnostics,
        output_language=output_language,
        research_mode=research_mode,
        parsed=parsed,
        sources=sources,
        source_diagnostics=source_diagnostics,
        entity_graph=entity_graph,
        rankings=rankings,
        public_contact_channels=merged_public_contact_channels,
        account_team_signals=merged_account_team_signals,
        query_plan=effective_query_plan + adapter_query_plan,
        research_scope_contract=evidence_governance.contract,
        research_question_tree=evidence_governance.question_tree,
        research_source_admissions=evidence_governance.admissions,
        research_evidence_gate=evidence_governance.gate,
        build_research_claim_governance=_build_research_claim_governance,
        evidence_density_level=_evidence_density_level,
        source_quality_level=_source_quality_level,
        build_sections=_build_sections,
        source_documents_to_outputs=_to_research_source_outputs,
        enrich_report_for_delivery=_enrich_report_for_delivery,
    )
    generation_review = review_generation_grounding(final_report, sources)
    final_report = final_report.model_copy(
        update={
            "source_diagnostics": final_report.source_diagnostics.model_copy(
                update=generation_review.to_diagnostics_update()
            )
        }
    )
    final_report = evaluate_and_improve_research_report(final_report, source_documents=sources)
    final_report = _expand_report_public_sources_until_quality_improves(
        final_report,
        source_documents=sources,
        runtime=runtime,
        progress_callback=progress_callback,
    )
    final_source_documents = _report_sources_to_source_documents(final_report.sources)
    final_evidence_governance = _build_research_evidence_governance(
        final_source_documents,
        keyword=keyword,
        research_focus=research_focus,
        research_mode=research_mode,
        scope_hints=scope_hints,
    )
    for warning in final_report.research_evidence_gate.warnings:
        final_evidence_governance = _append_evidence_gate_warning(final_evidence_governance, warning)
    accepted_final_sources = final_evidence_governance.accepted_sources
    final_report = final_report.model_copy(
        update={
            "source_count": len(accepted_final_sources),
            "sources": _to_research_source_outputs(accepted_final_sources),
            "source_quality": _source_quality_level(accepted_final_sources),
            "research_scope_contract": final_evidence_governance.contract,
            "research_question_tree": final_evidence_governance.question_tree,
            "research_source_admissions": final_evidence_governance.admissions,
            "research_evidence_gate": final_evidence_governance.gate,
            "source_diagnostics": _apply_evidence_governance_diagnostics(
                final_report.source_diagnostics,
                final_evidence_governance,
            ),
        }
    )
    final_report = _enforce_report_entity_authenticity(
        final_report,
        source_documents=accepted_final_sources,
        scope_hints=scope_hints,
        prior_audit=generation_execution.entity_authenticity_audit,
    )
    final_report = _sanitize_report_response_fields(
        final_report,
        allowed_source_urls={source.url for source in accepted_final_sources if source.url},
    )
    final_report = _stabilize_report_header(final_report)
    final_claim_governance = _build_research_claim_governance(final_report)
    final_report = final_report.model_copy(
        update={
            "research_claim_evidence_ledger": final_claim_governance.ledger,
            "research_citation_gate": final_claim_governance.citation_gate,
        }
    )
    final_report = _enrich_report_for_delivery(final_report)
    final_report = attach_research_interaction(final_report)
    _emit_research_snapshot(snapshot_callback, final_report)
    return final_report
