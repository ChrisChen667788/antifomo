from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import re
from typing import Any, Callable, Iterable

from sqlalchemy import desc, or_, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.entities import KnowledgeEntry
from app.schemas.research import (
    ResearchActionCardOut,
    ResearchCommercialSummaryOut,
    ResearchEntityGraphOut,
    ResearchEntityEvidenceOut,
    ResearchFollowupContextOut,
    ResearchFollowupDiagnosticsOut,
    ResearchNormalizedEntityOut,
    ResearchReportDocument,
    ResearchReportRequest,
    ResearchReportResponse,
    ResearchReportReadinessOut,
    ResearchReviewQueueItemOut,
    ResearchRankedEntityOut,
    ResearchReportSectionOut,
    ResearchScoreFactorOut,
    ResearchSourceDiagnosticsOut,
    ResearchSourceOut,
    ResearchTechnicalAppendixOut,
)
from app.services.browser_content_extractor import extract_from_browser
from app.services.content_extractor import (
    extract_domain,
    extract_from_reader_proxy,
    extract_from_url,
    normalize_text,
)
from app.services.knowledge_retrieval_service import retrieve_knowledge_entry_matches
from app.services.language import localized_text
from app.services.llm_parser import (
    ResearchReportResult,
    parse_research_report_response,
    parse_research_strategy_scope_response,
    parse_research_strategy_refine_response,
)
from app.services.research_quality_service import build_research_quality_profile
from app.services.research_rag_quality_service import (
    build_retrieval_correction_profile,
    rerank_sources_cross_encoder,
    render_retrieval_correction_context,
    review_generation_grounding,
)
from app.services.research.report_markdown import build_research_report_markdown
from app.services.research.report_readiness import (
    ReportReadinessDependencies,
    build_report_readiness as _report_readiness_build,
    is_low_signal_execution_report as _report_readiness_is_low_signal,
    resolved_report_readiness as _report_readiness_resolved,
)
from app.services.research.report_common import dedupe_strings as _report_common_dedupe_strings
from app.services.research.organization_identity import (
    KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS,
    OFFICIAL_DOMAIN_ENTITY_MAP as _OFFICIAL_DOMAIN_ENTITY_MAP,
    RESEARCH_ACCOUNT_ALIAS_MAP as _RESEARCH_ACCOUNT_ALIAS_MAP,
)
from app.services.research.report_row_quality import (
    BAD_EXEC_SUMMARY_PHRASES,
    BAD_SUMMARY_PHRASES,
    BUDGET_ROW_CONTEXT_TOKENS,
    BUDGET_ROW_NOISE_TOKENS,
    COMMERCIAL_BUDGET_SIGNAL_TOKENS,
    FIELD_ROW_NOISE_TOKENS,
    MONEY_PATTERN,
    SUMMARY_GUIDANCE_TOKENS,
    is_actionable_budget_row as _row_quality_is_actionable_budget_row,
    is_summary_fact_row as _row_quality_is_summary_fact_row,
    looks_like_insufficient as _row_quality_looks_like_insufficient,
    summary_fact_rows as _row_quality_summary_fact_rows,
)
from app.services.research.report_runtime_dependencies import (
    action_card_dependencies as _runtime_action_card_dependencies,
    report_readiness_dependencies as _runtime_report_readiness_dependencies,
    report_text_quality_dependencies as _runtime_report_text_quality_dependencies,
    stored_report_rewrite_dependencies as _runtime_stored_report_rewrite_dependencies,
    stored_report_rewrite_orchestration_dependencies as _runtime_stored_report_rewrite_orchestration_dependencies,
)
from app.services.research.report_runtime_owner_factory import (
    build_report_runtime_owner_ports as _build_report_runtime_owner_ports,
)
from app.services.research.report_ranking_runtime import (
    build_runtime_source_diagnostics as _report_ranking_build_source_diagnostics,
    evidence_mode_from_metrics as _report_ranking_evidence_mode_from_metrics,
    retrieval_quality_band as _report_ranking_retrieval_quality_band,
)
from app.services.research.report_delivery_runtime import (
    evidence_density_level as _report_delivery_evidence_density_level,
    merge_result_with_intelligence as _report_delivery_merge_result_with_intelligence,
    source_quality_level as _report_delivery_source_quality_level,
)
from app.services.research.report_delivery_runtime_dependencies import (
    build_sections as _report_delivery_build_sections,
    enrich_report_for_delivery as _report_delivery_enrich_report,
)
from app.services.research.report_delivery_strategy_runtime import (
    apply_topic_specific_overrides as _report_delivery_apply_topic_overrides,
    compress_title_segments as _report_delivery_compress_title_segments,
    summary_contains_output_noise as _report_delivery_summary_contains_output_noise,
)
from app.services.research.source_intelligence_runtime import (
    build_source_intelligence as _report_delivery_build_source_intelligence,
)
from app.services.research.report_scope_runtime import (
    collect_matched_theme_labels as _report_scope_collect_matched_theme_labels,
    prune_industry_hints as _report_scope_prune_industry_hints,
    scope_anchor_text_segments as _report_scope_anchor_text_segments,
)
from app.services.research.scope_hints import (
    REGION_SCOPE_ALIASES,
    expand_region_scope_terms as _scope_hints_expand_regions,
    infer_company_query_preferences as _scope_hints_infer_company_preferences,
    infer_input_scope_hints as _scope_hints_infer_input,
    infer_scope_hints as _scope_hints_infer,
    merge_scope_hints as _scope_hints_merge,
    source_theme_match_score as _scope_hints_source_theme_match_score,
)
from app.services.research.industry_methodology import (
    IndustryMethodologyProfile,
    build_industry_methodology_scope_hints as _industry_methodology_build_scope_hints,
    format_methodology_query_templates as _industry_methodology_format_queries,
    pick_industry_methodology_profile as _industry_methodology_pick_profile,
)
from app.services.research.report_storage_runtime import (
    report_intelligence_from_result as _report_storage_intelligence_from_result,
    report_sources_to_documents as _report_storage_sources_to_documents,
    stored_report_to_runtime_result as _report_storage_to_runtime_result,
)
from app.services.research.entity_policy import (
    CASE_HINT_TOKENS,
    COMPACT_ENTITY_PATTERN,
    CONTACT_PAGE_TOKENS,
    CONTACT_PLACEHOLDER_TOKENS,
    CONTACT_ROW_HINT_TOKENS,
    DEPARTMENT_HINT_TOKENS,
    DEPARTMENT_PATTERN,
    EMAIL_PATTERN,
    ENTITY_ACTION_PHRASE_TOKENS,
    ENTITY_BLACKLIST_TOKENS,
    ENTITY_FRAGMENT_INFIX_TOKENS,
    ENTITY_FRAGMENT_PREFIX_TOKENS,
    ENTITY_INVALID_PHRASE_TOKENS,
    ENTITY_LEADING_NOISE_PREFIXES,
    ENTITY_PLACEHOLDER_TOKENS,
    ENTITY_ROLE_CONTEXT_TOKENS,
    ENTITY_ROLE_FIELDS,
    ENTITY_ROLE_NAME_HINTS,
    ENTITY_SUFFIX_TOKENS,
    GENERIC_COMPANY_ANCHOR_TOKENS,
    GENERIC_CONTENT_DOMAINS,
    GENERIC_COUNT_ENTITY_PATTERN,
    GENERIC_FOCUS_TOKENS,
    GENERIC_SCOPE_CLIENT_TOKENS,
    INDUSTRY_SCOPE_ALIASES,
    INVALID_COMPANY_ANCHOR_PHRASES,
    KNOWN_LIGHTWEIGHT_ENTITY_NAMES,
    LOW_VALUE_ENTITY_NAME_TOKENS,
    NON_CONTACT_SOURCE_LABEL_TOKENS,
    ORG_PATTERN,
    PARTNER_CONNECTOR_ALIASES,
    PHONE_PATTERN,
    PRODUCT_HINT_TOKENS,
    QUERY_NOISE_SUFFIXES,
    REGION_TOKENS,
    SCOPE_PROMPT_NOISE_PREFIXES,
    SCOPE_PROMPT_NOISE_REGEXES,
    SCOPE_PROMPT_NOISE_TOKENS,
    SPECIAL_ENTITY_ALIASES,
    THEME_COMPANY_PUBLIC_SOURCE_SEEDS,
    THEME_ENTITY_ALLOW_TOKENS,
    THEME_ENTITY_BLOCK_TOKENS,
    THEME_GENERIC_SUPPRESSIONS,
    contains_low_value_entity_token as _entity_policy_contains_low_value_entity_token,
    entity_canonical_key as _entity_policy_entity_canonical_key,
    extract_rank_entity_name as _entity_policy_extract_rank_entity_name,
    fallback_entity_name_from_row as _entity_policy_fallback_entity_name_from_row,
    is_lightweight_entity_name as _entity_policy_is_lightweight_entity_name,
    is_plausible_entity_name as _entity_policy_is_plausible_entity_name,
    is_theme_aligned_entity_name as _entity_policy_is_theme_aligned_entity_name,
    is_trustworthy_scope_client_name as _entity_policy_is_trustworthy_scope_client_name,
    looks_like_fragment_entity_name as _entity_policy_looks_like_fragment_entity_name,
    looks_like_placeholder_contact_row as _entity_policy_looks_like_placeholder_contact_row,
    looks_like_placeholder_entity_name as _entity_policy_looks_like_placeholder_entity_name,
    looks_like_sentence_fragment_entity as _entity_policy_looks_like_sentence_fragment_entity,
    strip_entity_leading_noise as _entity_policy_strip_entity_leading_noise,
    trim_product_spec_from_entity_name as _entity_policy_trim_product_spec_from_entity_name,
)
from app.services.research.report_storage import (
    report_sources_to_source_documents as _storage_report_sources_to_source_documents,
    stored_report_section_aliases as _stored_report_section_aliases,
    stored_report_to_result as _storage_stored_report_to_result,
)
from app.services.research.runtime_config import (
    build_research_runtime as _runtime_config_build_research_runtime,
    build_runtime_strategy_scope_hints as _runtime_config_build_runtime_strategy_scope_hints,
)
from app.services.research.scope_terms import (
    ScopeTermDependencies,
    build_strict_theme_terms as _scope_terms_build_strict_theme_terms,
    build_theme_terms as _scope_terms_build_theme_terms,
    extract_company_anchor_terms as _scope_terms_extract_company_anchor_terms,
    extract_explicit_exclusion_terms as _scope_terms_extract_explicit_exclusion_terms,
    extract_topic_anchor_terms as _scope_terms_extract_topic_anchor_terms,
    looks_like_scope_prompt_noise as _scope_terms_looks_like_prompt_noise,
    resolved_company_anchor_terms as _scope_terms_resolved_company_anchor_terms,
    sanitize_research_focus_text as _scope_terms_sanitize_research_focus,
    strip_query_noise as _scope_terms_strip_query_noise,
    theme_labels_from_scope as _scope_terms_theme_labels_from_scope,
    tokenize_for_match as _scope_terms_tokenize_for_match,
)
from app.services.research.scope_entity_runtime_dependencies import (
    report_field_sanitization_dependencies as _runtime_report_field_sanitization_dependencies,
    scope_term_dependencies as _runtime_scope_term_dependencies,
)
from app.services.research.source_ranking import (
    SourceRankingDependencies,
    classify_source_tier as _source_ranking_classify_source_tier,
    classify_source_type as _source_ranking_classify_source_type,
    derive_source_label as _source_ranking_derive_source_label,
    hybrid_rank_hits as _source_ranking_hybrid_rank_hits,
    rerank_sources_hybrid as _source_ranking_rerank_sources_hybrid,
    search_query_text_for_matching as _source_ranking_search_query_text,
    select_hits_with_source_balance as _source_ranking_select_hits_with_source_balance,
    source_matches_company_anchor as _source_ranking_matches_company_anchor,
)
from app.services.research.action_cards import (
    ResearchActionCardDependencies,
    build_research_action_cards as _action_cards_build,
    derive_entry_window as _action_cards_derive_entry_window,
    entity_names_from_ranked as _action_cards_entity_names_from_ranked,
)
from app.services.research.archive_context import (
    merge_scope_hints_with_archive_context as _archive_context_merge_scope_hints,
    render_archive_prompt_context as _archive_context_render_prompt,
    research_archive_query_text as _archive_context_query_text,
)
from app.services.research.archive_loader import (
    build_archive_context_item as _archive_loader_build_context_item,
    build_archive_report_scope_hints as _archive_loader_build_report_scope_hints,
    load_research_archive_context as _archive_loader_load_context,
)
from app.services.research.candidate_profile_enrichment import (
    CandidateProfileEnrichmentDependencies,
    enrich_candidate_profiles as _candidate_profile_enrichment_enrich,
)
from app.services.research.company_source_enrichment import (
    CompanySourceEnrichmentDependencies,
    enrich_company_sources as _company_source_enrichment_enrich,
)
from app.services.research.corrective_expansion import (
    CorrectiveExpansionDependencies,
    apply_corrective_expansion as _corrective_expansion_apply,
)
from app.services.research.delivery_materials import (
    DeliveryMaterialsDependencies,
    build_commercial_summary as _delivery_materials_build_commercial_summary,
    build_review_queue as _delivery_materials_build_review_queue,
    build_technical_appendix as _delivery_materials_build_technical_appendix,
)
from app.services.research.delivery_enrichment import (
    DeliveryEnrichmentDependencies,
    apply_report_readiness_guardrails as _delivery_enrichment_apply_guardrails,
    enrich_report_for_delivery as _delivery_enrichment_enrich_report,
)
from app.services.research.evidence_expansion import (
    EvidenceExpansionDependencies,
    apply_evidence_expansion as _evidence_expansion_apply,
)
from app.services.research.entity_ranking import (
    EntityRankingHeuristicDependencies,
    build_candidate_profile_support as _entity_ranking_build_candidate_profile_support,
    promote_pending_entities_with_candidate_profiles as _entity_ranking_promote_pending_with_profiles,
    promote_ranked_entities_with_candidate_profiles as _entity_ranking_promote_with_profiles,
    rank_report_entities as _entity_ranking_rank_report_entities,
    rank_top_entities as _entity_ranking_rank_top_entities,
)
from app.services.research.entity_ranking_runtime import (
    COMPANY_PROFILE_PAGE_TOKENS,
    GENERIC_COMPANY_NAME_TOKENS,
    THEME_ROLE_ARCHETYPES,
    build_entity_specific_contact_rows as _ranking_runtime_build_contact_rows,
    build_entity_specific_team_rows as _ranking_runtime_build_team_rows,
    build_runtime_entity_graph as _ranking_runtime_build_entity_graph,
    filtered_rank_fallback_values as _ranking_runtime_filtered_fallback_values,
    rank_runtime_top_entities as _ranking_runtime_rank_top_entities,
    source_supports_target_account as _ranking_runtime_source_supports_target,
)
from app.services.research.entity_graph_builder import (
    EntityGraphBuilderDependencies,
    build_entity_graph as _entity_graph_builder_build,
    entity_graph_lookup as _entity_graph_builder_lookup,
)
from app.services.research.followup_diagnostics import (
    FollowupDiagnosticsDependencies,
    build_followup_context as _followup_diagnostics_build_context,
    build_followup_planning_focus as _followup_diagnostics_build_planning_focus,
    build_followup_research_diagnostics as _followup_diagnostics_build_research,
    enrich_followup_diagnostics as _followup_diagnostics_enrich,
    merge_scope_hints_with_followup_context as _followup_diagnostics_merge_scope_hints,
    render_followup_diagnostics_prompt_context as _followup_diagnostics_render_diagnostics_prompt,
    render_followup_prompt_context as _followup_diagnostics_render_prompt,
    render_followup_section_focus_prompt_context as _followup_diagnostics_render_section_focus_prompt,
)
from app.services.research.generation_artifacts import (
    build_partial_report_response as _generation_artifacts_build_partial_report_response,
    build_partial_report_result as _generation_artifacts_build_partial_report_result,
)
from app.services.research.generation_execution import (
    ResearchGenerationExecutionDependencies,
    execute_research_generation as _generation_execution_execute,
)
from app.services.research.generation_setup import (
    ResearchGenerationSetupDependencies,
    prepare_research_generation_setup as _generation_setup_prepare,
)
from app.services.research.generation_workflow import (
    ResearchGenerationWorkflowDependencies,
    ResearchWorkflowAssemblyPorts,
    ResearchWorkflowEnrichmentPorts,
    ResearchWorkflowGenerationPorts,
    ResearchWorkflowProgressPorts,
    ResearchWorkflowQualityPorts,
    ResearchWorkflowRankingPorts,
    ResearchWorkflowScopePorts,
    ResearchWorkflowSourceCollectionPorts,
    run_research_generation_workflow as _generation_workflow_run,
)
from app.services.research.run_metrics import ResearchRunMetrics, instrument_llm_service
from app.services.research.workflow_engine import (
    DeterministicResearchWorkflowDependencies,
    DeterministicResearchWorkflowEngine,
    ResearchWorkflowEngine,
    ResearchWorkflowExecution,
)
from app.services.research.quality_expansion import (
    QualityExpansionDependencies,
    expand_report_public_sources_until_quality_improves as _quality_expansion_expand_report,
)
from app.services.research.ranking_source_utility import (
    RankingSourceUtilityDependencies,
    extract_department_rows as _ranking_source_extract_department_rows,
    extract_key_people_rows as _ranking_source_extract_key_people_rows,
    extract_public_contact_rows as _ranking_source_extract_public_contact_rows,
    rank_org_rows as _ranking_source_rank_org_rows,
)
from app.services.research.report_field_sanitization import (
    ReportFieldSanitizationDependencies,
    is_useful_public_contact_row as _report_field_sanitization_is_public_contact,
    sanitize_entity_row as _report_field_sanitization_entity_row,
    sanitize_report_field_rows as _report_field_sanitization_rows,
)
from app.services.research.report_assembly import assemble_final_research_report as _report_assembly_assemble_final_report
from app.services.research.retrieval_orchestration import (
    build_section_retrieval_runtime_context as _retrieval_orchestration_build_section_runtime_context,
)
from app.services.research.section_quality import (
    SectionQualityDependencies,
    build_section_evidence_links as _section_quality_build_evidence_links,
    section_confidence_profile as _section_quality_confidence_profile,
    section_evidence_quota as _section_quality_evidence_quota,
    section_insufficiency_profile as _section_quality_insufficiency_profile,
    section_next_verification_steps as _section_quality_next_verification_steps,
    section_quota_note as _section_quality_quota_note,
    section_signal_quality as _section_quality_signal_quality,
)
from app.services.research.report_sections import (
    ReportSectionsDependencies,
    build_sections as _report_sections_build_sections,
)
from app.services.research.report_text_quality import (
    ReportTextQualityDependencies,
    looks_like_bad_executive_summary as _report_text_quality_bad_summary,
)
from app.services.research.source_collection import (
    collect_adapter_hits as _source_collection_collect_adapter_hits,
    collect_public_search_hits as _source_collection_collect_public_search_hits,
    extract_initial_sources as _source_collection_extract_initial_sources,
)
from app.services.research.source_diagnostics import (
    SourceDiagnosticsDependencies,
    build_source_diagnostics as _source_diagnostics_build,
)
from app.services.research.source_extraction import (
    SourceExtractionDependencies,
    extract_source_document as _source_extraction_extract_source_document,
    extract_source_document_best_effort as _source_extraction_extract_source_document_best_effort,
)
from app.services.research.source_documents import (
    SourceDocument,
    clean_source_text_for_analysis as _source_documents_clean_source_text,
    looks_like_source_artifact_text as _source_documents_looks_like_artifact,
    looks_like_source_noise_segment as _source_documents_looks_like_noise_segment,
    source_document_text as _source_documents_text,
    source_documents_to_research_source_outputs as _to_research_source_outputs,
)
from app.services.research.source_intelligence import (
    SourceIntelligenceDependencies,
    build_source_intelligence as _source_intelligence_build,
)
from app.services.research.source_query_plans import (
    SourceQueryPlanDependencies,
    build_company_contact_query_plan as _source_query_plans_build_company_contact,
    build_company_profile_query_plan as _source_query_plans_build_company_profile,
    build_company_team_query_plan as _source_query_plans_build_company_team,
    build_corrective_query_plan as _source_query_plans_build_corrective,
    build_expanded_query_plan as _source_query_plans_build_expanded,
    build_query_plan as _source_query_plans_build_query,
)
from app.services.research.source_scope_policy import (
    SOURCE_MAX_AGE_YEARS,
    SourceScopePolicyDependencies,
    filter_recent_sources as _source_scope_policy_filter_recent,
    filter_sources_by_theme_relevance as _source_scope_policy_filter_by_theme,
    refine_sources_for_report as _source_scope_policy_refine,
    region_conflict_signature as _source_scope_policy_region_conflict_signature,
    source_has_region_conflict as _source_scope_policy_has_region_conflict,
    source_scope_match_score as _source_scope_policy_scope_score,
)
from app.services.research.strategy_refinement import (
    StrategyRefinementDependencies,
    apply_strategy_llm_refinement as _strategy_refinement_apply_llm,
    apply_strategy_scope_planning as _strategy_refinement_apply_scope,
    apply_topic_specific_overrides as _strategy_refinement_apply_topic_overrides,
)
from app.services.research.stored_entity_runtime_dependencies import (
    canonicalize_entity_name as _stored_entity_runtime_canonicalize_name,
    canonicalize_report_entities as _stored_entity_runtime_canonicalize_report,
    canonicalize_result_entities as _stored_entity_runtime_canonicalize_result,
    clean_candidate_company_names as _stored_entity_runtime_clean_candidates,
)
from app.services.research.stored_report_rewrite import (
    StoredReportRewriteDependencies,
    StoredReportRewriteOrchestrationDependencies,
    apply_guarded_rewrite_diagnostics as _stored_report_rewrite_apply_guarded_diagnostics,
    assess_stored_report_rewrite_mode as _stored_report_rewrite_assess_mode,
    build_guarded_rewrite_title as _stored_report_rewrite_build_guarded_title,
    resolve_stored_report_target_support as _stored_report_rewrite_resolve_target_support,
    rewrite_stored_research_report as _stored_report_rewrite_rewrite_report,
    stored_report_concrete_targets as _stored_report_rewrite_concrete_targets,
    stored_source_is_low_signal as _stored_report_rewrite_source_is_low_signal,
)
from app.services.research.tender_detail_enrichment import (
    TenderDetailDependencies,
    apply_tender_detail_enrichment as _tender_detail_enrichment_apply,
)
from app.services.research.web_search import SearchHit, _search_public_web
from app.services.research_report_evaluation_service import evaluate_and_improve_research_report
from app.services.research_retrieval_index_service import (
    ResearchRetrievalIndex,
    ResearchRetrievalIndexChunk,
    build_research_retrieval_index,
    load_persistent_research_retrieval_index,
)
from app.services.research_section_retrieval_service import (
    attach_section_retrieval_packs,
    build_section_retrieval_packs,
    render_section_retrieval_prompt_context as _section_retrieval_render_prompt_context,
)
from app.services.delivery.market_intelligence import build_market_intelligence_pack
from app.services.research_solution_intelligence_service import build_solution_delivery_pack
from app.services.llm_service import get_llm_service, get_strategy_llm_service
from app.services.research_source_adapters import (
    CURATED_WECHAT_CHANNELS,
    collect_enabled_source_hits,
    read_research_source_settings,
)


@dataclass(slots=True)
class RankedEntityCandidate:
    name: str
    score: int
    reasoning: str
    score_breakdown: list[ResearchScoreFactorOut]
    evidence_links: list[ResearchEntityEvidenceOut]


ResearchProgressCallback = Callable[[str, int, str], None]
ResearchSnapshotCallback = Callable[[ResearchReportResponse], None]


RESEARCH_SOURCE_SITE_QUERIES = (
    ("official_policy", "site:gov.cn {keyword} 领导 讲话 规划 战略"),
    ("public_procurement", "site:ccgp.gov.cn {keyword} 招标 中标 预算"),
    ("public_resource", "site:ggzy.gov.cn {keyword} 招标 中标 项目"),
    ("public_tender_portal", "site:cecbid.org.cn {keyword} 招标 中标 采购 预算"),
    ("public_service_portal", "site:cebpubservice.com {keyword} 招标 中标 项目"),
    ("public_procurement_portal", "site:china-cpp.com {keyword} 采购 招标 项目"),
    ("listed_filings", "site:cninfo.com.cn {keyword} 公告 年报 战略 预算"),
    ("hk_listed_filings", "site:hkexnews.hk {keyword} 公告 战略 合作"),
    ("global_filings", "site:sec.gov {keyword} annual report strategy partnership"),
    ("media_and_web", "{keyword} 中标 项目 二期 三期 四期 预算 金额"),
    ("client_peers", "{keyword} 甲方 同行 区域 动向 预算 项目"),
    ("winner_peers", "{keyword} 中标方 同行 集成商 厂商 动向 竞争"),
    ("ecosystem", "{keyword} 生态伙伴 渠道 集成商 ISV 咨询"),
)


THEME_QUERY_EXPANSION_TEMPLATES: dict[str, tuple[str, ...]] = {
    "AI漫剧": (
        "{keyword} AIGC动画 短剧 平台 商业化",
        "{keyword} 漫剧 IP 内容平台 合作 发行",
        "{keyword} AI短剧 动漫 版权 平台 投资",
        "site:mp.weixin.qq.com {keyword} AIGC动画 短剧 平台",
    ),
    "政务云": (
        "{keyword} 数据局 政务云 一体化 招标 预算",
        "{keyword} 政务云 建设 采购 中标 二期 三期",
        "site:gov.cn {keyword} 数据局 政务云 规划",
        "site:ggzy.gov.cn {keyword} 政务云 建设 项目",
    ),
}



THEME_OFFICIAL_QUERY_TEMPLATES: dict[str, tuple[str, ...]] = {
    "AI漫剧": (
        "site:iqiyi.com {keyword} AIGC动画 短剧 合作 平台",
        "site:ir.iqiyi.com {keyword} 内容 业务 合作 生态",
        "site:bilibili.com {keyword} AIGC动画 内容 生态 合作",
        "site:ir.bilibili.com {keyword} 内容 合作 生态 平台",
        "site:v.qq.com {keyword} 短剧 动画 平台 合作",
        "site:ac.qq.com {keyword} 漫画 动漫 IP 合作 平台",
        "site:youku.com {keyword} 动漫 短剧 合作 平台",
        "site:yuewen.com {keyword} IP 动漫 短剧 合作",
        "site:mgtv.com {keyword} 内容 短剧 AIGC 合作",
        "site:kuaishou.com {keyword} 短剧 AIGC 内容 平台",
        "site:ir.kuaishou.com {keyword} 内容 业务 合作",
        "site:bytedance.com {keyword} 短剧 AIGC 内容 平台",
        "site:kuaikanmanhua.com {keyword} 漫画 IP 短剧 合作",
        "site:zhuiguang.com {keyword} 动画 IP 内容 合作",
        "site:col.com {keyword} 动漫 IP AIGC 合作",
    ),
    "政务云": (
        "site:aliyun.com {keyword} 政务云 政务 合作",
        "site:cloud.tencent.com {keyword} 政务云 合作 案例",
        "site:huawei.com {keyword} 政务云 行业 数字政府",
        "site:h3c.com {keyword} 政务云 数字政府 合作",
    ),
}
























PERSON_ROLE_PATTERN = re.compile(
    r"([\u4e00-\u9fa5]{2,4})(?:同志)?(?:在[^。；;\n]{0,12})?"
    r"(?:表示|指出|强调|要求|担任|出席|主持|提到|介绍)?"
    r"[^。；;\n]{0,18}?"
    r"(书记|市长|局长|厅长|主任|董事长|总经理|总裁|副总裁|院长|校长|负责人)"
)




SOURCE_DATE_PATTERN = re.compile(
    r"(?P<year>20\d{2}|19\d{2})"
    r"(?:[\-/年\.](?P<month>0?[1-9]|1[0-2]))?"
    r"(?:[\-/月\.](?P<day>0?[1-9]|[12]\d|3[01]))?"
    r"(?:日)?"
)

def _truncate_text(value: str, limit: int) -> str:
    text = normalize_text(value)
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rstrip(" ，,：:；;")
    return f"{cut}…"


def _source_query_plan_dependencies() -> SourceQueryPlanDependencies:
    return SourceQueryPlanDependencies(
        strip_query_noise=_strip_query_noise,
        sanitize_research_focus_text=_sanitize_research_focus_text,
        extract_topic_anchor_terms=_extract_topic_anchor_terms,
        expand_region_scope_terms=_expand_region_scope_terms,
        dedupe_strings=_dedupe_strings,
        collect_theme_seed_companies=_collect_theme_seed_companies,
        is_plausible_entity_name=_is_plausible_entity_name,
        industry_scope_aliases=INDUSTRY_SCOPE_ALIASES,
        theme_query_expansion_templates=THEME_QUERY_EXPANSION_TEMPLATES,
        research_source_site_queries=RESEARCH_SOURCE_SITE_QUERIES,
        theme_official_query_templates=THEME_OFFICIAL_QUERY_TEMPLATES,
    )


def _build_query_plan(
    keyword: str,
    research_focus: str | None,
    include_wechat: bool,
    *,
    scope_hints: dict[str, object] | None = None,
    preferred_wechat_accounts: Iterable[str] | None = None,
    limit: int = 8,
) -> list[str]:
    return _source_query_plans_build_query(
        keyword,
        research_focus,
        include_wechat,
        scope_hints=scope_hints,
        preferred_wechat_accounts=preferred_wechat_accounts,
        limit=limit,
        deps=_source_query_plan_dependencies(),
    )


def _scope_term_dependencies() -> ScopeTermDependencies:
    return _runtime_scope_term_dependencies()


def _tokenize_for_match(*values: str) -> list[str]:
    return _scope_terms_tokenize_for_match(*values)


@lru_cache(maxsize=8192)
def _looks_like_scope_prompt_noise(value: str) -> bool:
    return _scope_terms_looks_like_prompt_noise(value, deps=_scope_term_dependencies())


def _strip_query_noise(value: str) -> str:
    return _scope_terms_strip_query_noise(value, deps=_scope_term_dependencies())


def _sanitize_research_focus_text(value: str | None) -> str:
    return _scope_terms_sanitize_research_focus(value, deps=_scope_term_dependencies())


def _extract_explicit_exclusion_terms(value: str | None) -> list[str]:
    return _scope_terms_extract_explicit_exclusion_terms(value, deps=_scope_term_dependencies())


def _extract_topic_anchor_terms(keyword: str, research_focus: str | None) -> list[str]:
    return _scope_terms_extract_topic_anchor_terms(keyword, research_focus, deps=_scope_term_dependencies())


def _extract_company_anchor_terms(keyword: str, research_focus: str | None) -> list[str]:
    return _scope_terms_extract_company_anchor_terms(keyword, research_focus, deps=_scope_term_dependencies())


def _resolved_company_anchor_terms(
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object] | None = None,
) -> list[str]:
    return _scope_terms_resolved_company_anchor_terms(
        keyword,
        research_focus,
        scope_hints,
        deps=_scope_term_dependencies(),
    )


def _search_query_text_for_matching(source: SearchHit | SourceDocument) -> str:
    return _source_ranking_search_query_text(source)


def _source_matches_company_anchor(source: SearchHit | SourceDocument, company_anchor_terms: list[str]) -> bool:
    return _source_ranking_matches_company_anchor(source, company_anchor_terms)


def _source_ranking_dependencies() -> SourceRankingDependencies:
    return SourceRankingDependencies(
        dedupe_hits=_dedupe_hits,
        dedupe_sources=_dedupe_sources,
        extract_topic_anchor_terms=_extract_topic_anchor_terms,
        build_theme_terms=_build_theme_terms,
        resolved_company_anchor_terms=_resolved_company_anchor_terms,
        source_scope_match_score=_source_scope_match_score,
        get_settings=get_settings,
        safe_int=_safe_int,
        rerank_sources_cross_encoder=rerank_sources_cross_encoder,
    )


def _hybrid_rank_hits(
    hits: Iterable[SearchHit],
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object] | None = None,
) -> list[SearchHit]:
    return _source_ranking_hybrid_rank_hits(
        hits,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
        deps=_source_ranking_dependencies(),
    )


def _rerank_sources_hybrid(
    sources: Iterable[SourceDocument],
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object] | None = None,
) -> list[SourceDocument]:
    return _source_ranking_rerank_sources_hybrid(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
        deps=_source_ranking_dependencies(),
    )


def _source_scope_policy_dependencies() -> SourceScopePolicyDependencies:
    return SourceScopePolicyDependencies(
        dedupe_sources=_dedupe_sources,
        rerank_sources_hybrid=_rerank_sources_hybrid,
        filter_sources_by_theme_relevance=_filter_sources_by_theme_relevance,
        source_text=_source_text,
        search_query_text_for_matching=_search_query_text_for_matching,
        expand_region_scope_terms=_expand_region_scope_terms,
        classify_source_type=_classify_source_type,
        classify_source_tier=_classify_source_tier,
        extract_domain=extract_domain,
        source_supports_company_intent=_source_supports_company_intent,
        build_strict_theme_terms=_build_strict_theme_terms,
        source_matches_company_anchor=_source_matches_company_anchor,
        source_has_region_conflict=_source_has_region_conflict,
        infer_source_published_at=_infer_source_published_at,
        region_scope_aliases=REGION_SCOPE_ALIASES,
        industry_scope_aliases=INDUSTRY_SCOPE_ALIASES,
    )


def _refine_sources_for_report(
    sources: Iterable[SourceDocument],
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
    company_anchor_terms: list[str],
    theme_terms: list[str],
) -> list[SourceDocument]:
    return _source_scope_policy_refine(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
        company_anchor_terms=company_anchor_terms,
        theme_terms=theme_terms,
        deps=_source_scope_policy_dependencies(),
    )


def _source_scope_match_score(
    source: SourceDocument | SearchHit,
    *,
    scope_hints: dict[str, object],
    company_anchor_terms: list[str],
    theme_terms: list[str],
) -> int:
    return _source_scope_policy_scope_score(
        source,
        scope_hints=scope_hints,
        company_anchor_terms=company_anchor_terms,
        theme_terms=theme_terms,
        deps=_source_scope_policy_dependencies(),
    )


def _dedupe_hits(hits: Iterable[SearchHit]) -> list[SearchHit]:
    deduped: list[SearchHit] = []
    seen_urls: set[str] = set()
    for hit in hits:
        normalized_url = normalize_text(hit.url)
        if not normalized_url or normalized_url in seen_urls:
            continue
        seen_urls.add(normalized_url)
        deduped.append(hit)
    return deduped


def _build_company_seed_hits(company_names: list[str], *, keyword: str) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for company in _dedupe_strings(company_names, 4):
        normalized = normalize_text(company)
        if not normalized:
            continue
        for url, label in KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS.get(normalized, ()):
            hits.append(
                SearchHit(
                    title=f"{normalized} {label}",
                    url=url,
                    snippet=f"{normalized} 官方公开入口，优先用于补充官网、IR、公开业务联系渠道。",
                    search_query=f"{keyword} {normalized} 官方公开入口",
                    source_hint="web",
                    source_label=label,
                )
            )
    return hits


def _collect_theme_seed_companies(
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
) -> list[str]:
    seed_names: list[str] = []
    industries = [normalize_text(str(item)) for item in scope_hints.get("industries", []) or [] if normalize_text(str(item))]
    topic_terms = _extract_topic_anchor_terms(keyword, research_focus)
    for industry in industries:
        seed_names.extend(THEME_COMPANY_PUBLIC_SOURCE_SEEDS.get(industry, ()))
    lowered_terms = " ".join(topic_terms).lower()
    if any(token in lowered_terms for token in ("ai漫剧", "漫剧", "ai短剧", "aigc动画", "动漫短剧")):
        seed_names.extend(THEME_COMPANY_PUBLIC_SOURCE_SEEDS.get("AI漫剧", ()))
    if any(token in lowered_terms for token in ("政务云", "数字政府", "政务")):
        seed_names.extend(THEME_COMPANY_PUBLIC_SOURCE_SEEDS.get("政务云", ()))
    seed_names.extend(
        normalize_text(str(item))
        for item in scope_hints.get("company_anchors", []) or []
        if normalize_text(str(item))
    )
    seed_names.extend(
        normalize_text(str(item))
        for item in scope_hints.get("clients", []) or []
        if normalize_text(str(item))
    )
    return _dedupe_strings(seed_names, 12)


def _build_corrective_query_plan(
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
    include_wechat: bool,
    preferred_wechat_accounts: Iterable[str] | None = None,
    limit: int = 8,
) -> list[str]:
    return _source_query_plans_build_corrective(
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
        include_wechat=include_wechat,
        preferred_wechat_accounts=preferred_wechat_accounts,
        limit=limit,
        deps=_source_query_plan_dependencies(),
    )


def _tender_detail_dependencies() -> TenderDetailDependencies:
    return TenderDetailDependencies(
        dedupe_strings=_dedupe_strings,
        search_public_web=_search_public_web,
        hybrid_rank_hits=_hybrid_rank_hits,
        select_hits_with_source_balance=_select_hits_with_source_balance,
        extract_source_document_best_effort=_extract_source_document_best_effort,
        filter_recent_sources=_filter_recent_sources,
        emit_research_progress=_emit_research_progress,
        build_progress_message=_build_progress_message,
        dedupe_sources=_dedupe_sources,
        refine_sources_for_report=_refine_sources_for_report,
        merge_scope_hints=_merge_scope_hints,
        infer_scope_hints=_infer_scope_hints,
        build_theme_terms=_build_theme_terms,
        resolved_company_anchor_terms=_resolved_company_anchor_terms,
        build_source_intelligence=_build_source_intelligence,
    )


def _dedupe_sources(sources: Iterable[SourceDocument]) -> list[SourceDocument]:
    deduped: list[SourceDocument] = []
    seen_urls: set[str] = set()
    for source in sources:
        normalized_url = normalize_text(source.url)
        if normalized_url and normalized_url in seen_urls:
            continue
        if normalized_url:
            seen_urls.add(normalized_url)
        deduped.append(source)
    return deduped


def _select_hits_with_source_balance(hits: list[SearchHit], *, limit: int) -> list[SearchHit]:
    return _source_ranking_select_hits_with_source_balance(hits, limit=limit)


def _classify_source_type(url: str) -> str:
    return _source_ranking_classify_source_type(url)


def _classify_source_tier(*, source_type: str, domain: str | None, source_label: str | None) -> str:
    return _source_ranking_classify_source_tier(source_type=source_type, domain=domain, source_label=source_label)


def _derive_source_label(*, source_type: str, domain: str | None, fallback: str | None) -> str | None:
    return _source_ranking_derive_source_label(source_type=source_type, domain=domain, fallback=fallback)


def _source_extraction_dependencies() -> SourceExtractionDependencies:
    return SourceExtractionDependencies(
        classify_source_type=_classify_source_type,
        classify_source_tier=_classify_source_tier,
        derive_source_label=_derive_source_label,
        truncate_text=_truncate_text,
        clean_source_text_for_analysis=_clean_source_text_for_analysis,
        extract_from_browser=extract_from_browser,
        extract_from_url=extract_from_url,
        extract_from_reader_proxy=extract_from_reader_proxy,
    )


def _extract_source_document(hit: SearchHit, *, timeout_seconds: int, excerpt_chars: int) -> SourceDocument:
    return _source_extraction_extract_source_document(
        hit,
        timeout_seconds=timeout_seconds,
        excerpt_chars=excerpt_chars,
        deps=_source_extraction_dependencies(),
    )


def _extract_source_document_best_effort(
    hit: SearchHit,
    *,
    timeout_seconds: int,
    excerpt_chars: int,
) -> SourceDocument | None:
    return _source_extraction_extract_source_document_best_effort(
        hit,
        timeout_seconds=timeout_seconds,
        excerpt_chars=excerpt_chars,
        deps=_source_extraction_dependencies(),
    )


def _parse_source_datetime(
    *,
    year: str,
    month: str | None = None,
    day: str | None = None,
) -> datetime | None:
    try:
        resolved_year = int(year)
        resolved_month = max(1, min(12, int(month or "1")))
        resolved_day = max(1, min(28 if resolved_month == 2 else 31, int(day or "1")))
        if resolved_year < 1900:
            return None
        return datetime(resolved_year, resolved_month, resolved_day, tzinfo=timezone.utc)
    except ValueError:
        return None


def _extract_source_dates(value: str) -> list[datetime]:
    text = normalize_text(value)
    if not text:
        return []
    dates: list[datetime] = []
    for match in SOURCE_DATE_PATTERN.finditer(text):
        parsed = _parse_source_datetime(
            year=str(match.group("year") or ""),
            month=match.group("month"),
            day=match.group("day"),
        )
        if parsed:
            dates.append(parsed)
    return dates


def _infer_source_published_at(source: SourceDocument) -> datetime | None:
    date_candidates: list[datetime] = []
    for candidate in (
        source.title,
        source.snippet,
        source.excerpt,
        source.url,
        source.search_query,
    ):
        date_candidates.extend(_extract_source_dates(candidate))
    if not date_candidates:
        return None
    return max(date_candidates)


def _filter_recent_sources(
    sources: list[SourceDocument],
    *,
    max_age_years: int = SOURCE_MAX_AGE_YEARS,
) -> list[SourceDocument]:
    return _source_scope_policy_filter_recent(
        sources,
        max_age_years=max_age_years,
        deps=_source_scope_policy_dependencies(),
    )


def _source_text(source: SourceDocument) -> str:
    return _source_documents_text(source)


def _source_theme_match_score(
    source: SourceDocument,
    *,
    theme_terms: list[str],
    scope_hints: dict[str, object],
) -> int:
    return _scope_hints_source_theme_match_score(
        source,
        theme_terms=theme_terms,
        scope_hints=scope_hints,
    )


def _filter_sources_by_theme_relevance(
    sources: list[SourceDocument],
    *,
    theme_terms: list[str],
    scope_hints: dict[str, object],
    company_anchor_terms: list[str] | None = None,
) -> list[SourceDocument]:
    return _source_scope_policy_filter_by_theme(
        sources,
        theme_terms=theme_terms,
        scope_hints=scope_hints,
        company_anchor_terms=company_anchor_terms,
        deps=_source_scope_policy_dependencies(),
    )


def _dedupe_strings(values: Iterable[str], limit: int) -> list[str]:
    return _report_common_dedupe_strings(values, limit)


def _prune_industry_hints(values: Iterable[str]) -> list[str]:
    return _report_scope_prune_industry_hints(values)


@lru_cache(maxsize=8192)
def _strip_org_public_suffixes(value: str) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    stripped = normalized
    suffixes = (
        "集团官网",
        "官网入口",
        "官网主页",
        "官网首页",
        "官方网站",
        "官网",
        "投资者关系",
        "投资者关系主页",
        "联系我们",
        "公开入口",
        "品牌官网",
    )
    changed = True
    while changed:
        changed = False
        for suffix in suffixes:
            if stripped.endswith(suffix) and len(stripped) > len(suffix) + 1:
                stripped = normalize_text(stripped[: -len(suffix)])
                changed = True
                break
    return stripped


@lru_cache(maxsize=1)
def _normalized_entity_suffixes() -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                normalize_text(suffix)
                for suffix in ENTITY_SUFFIX_TOKENS
                if normalize_text(suffix)
            },
            key=len,
            reverse=True,
        )
    )


@lru_cache(maxsize=1)
def _normalized_entity_suffixes_lower() -> tuple[str, ...]:
    return tuple(suffix.lower() for suffix in _normalized_entity_suffixes())


def _entity_alias_lookup_key(name: str) -> str:
    return _entity_alias_lookup_key_cached(normalize_text(_strip_org_public_suffixes(name)))


@lru_cache(maxsize=16384)
def _entity_alias_lookup_key_cached(normalized_name: str) -> str:
    lowered = normalized_name.lower()
    stripped = lowered
    changed = True
    while changed:
        changed = False
        for suffix_normalized in _normalized_entity_suffixes_lower():
            if stripped.endswith(suffix_normalized) and len(stripped) > len(suffix_normalized) + 1:
                stripped = stripped[: -len(suffix_normalized)]
                changed = True
                break
    stripped = re.sub(r"[^a-z0-9\u4e00-\u9fa5]+", "", stripped)
    return stripped or lowered


def _org_surface_variants(value: str) -> list[str]:
    normalized = normalize_text(_strip_org_public_suffixes(value))
    if not normalized:
        return []
    return list(_org_surface_variants_cached(normalized))


@lru_cache(maxsize=8192)
def _org_surface_variants_cached(normalized_value: str) -> tuple[str, ...]:
    variants = [normalized_value]
    cleaned = _strip_entity_leading_noise(normalized_value)
    if cleaned and cleaned not in variants:
        variants.append(cleaned)
    bracketless = normalize_text(re.sub(r"[（(][^（）()]{1,24}[）)]", "", normalized_value))
    if bracketless and bracketless not in variants:
        variants.append(bracketless)
    stripped = normalized_value
    changed = True
    while changed:
        changed = False
        for suffix in _normalized_entity_suffixes():
            if stripped.endswith(suffix) and len(stripped) > len(suffix) + 1:
                stripped = normalize_text(stripped[: -len(suffix)])
                changed = True
                break
    if (
        stripped
        and stripped != normalized_value
        and len(stripped) >= 2
        and stripped not in variants
        and not _looks_like_scope_prompt_noise(stripped)
        and not _contains_low_value_entity_token(stripped)
    ):
        variants.append(stripped)
    return tuple(_dedupe_strings(variants, 6))


def _scope_org_names_key(scope_hints: dict[str, object] | None) -> tuple[str, ...]:
    if not scope_hints:
        return ()
    bucket_values: list[tuple[str, ...]] = []
    for bucket in ("company_anchors", "clients", "seed_companies"):
        normalized_items: list[str] = []
        for item in scope_hints.get(bucket, []) or []:
            normalized = normalize_text(str(item))
            if normalized:
                normalized_items.append(normalized)
        bucket_values.append(tuple(normalized_items))
    return _scope_org_names_key_cached(*bucket_values)


@lru_cache(maxsize=512)
def _scope_org_names_key_cached(
    company_anchors: tuple[str, ...],
    clients: tuple[str, ...],
    seed_companies: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(_dedupe_strings([*company_anchors, *clients, *seed_companies], 24))


def _register_org_alias(
    alias_map: dict[str, str],
    canonical_name: str,
    alias_name: str | None = None,
    *,
    replace: bool = False,
) -> None:
    canonical = normalize_text(canonical_name)
    alias = normalize_text(alias_name or canonical_name)
    if not canonical or not alias:
        return
    key = _entity_alias_lookup_key(alias)
    if not key:
        return
    if replace or key not in alias_map:
        alias_map[key] = canonical


@lru_cache(maxsize=1)
def _base_org_alias_lookup_map() -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for canonical in [*KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS.keys(), *SPECIAL_ENTITY_ALIASES]:
        for alias in _org_surface_variants(canonical):
            _register_org_alias(alias_map, canonical, alias)
    for alias, canonical in _RESEARCH_ACCOUNT_ALIAS_MAP.items():
        _register_org_alias(alias_map, canonical, canonical, replace=True)
        for variant in _org_surface_variants(alias):
            _register_org_alias(alias_map, canonical, variant, replace=True)
    return alias_map


@lru_cache(maxsize=512)
def _org_alias_lookup_map_cached(scope_org_names: tuple[str, ...]) -> dict[str, str]:
    alias_map = dict(_base_org_alias_lookup_map())
    for canonical in scope_org_names:
        for alias in _org_surface_variants(canonical):
            _register_org_alias(alias_map, canonical, alias, replace=True)
    return alias_map


def _canonical_org_name_from_domain(domain: str | None) -> str:
    normalized = normalize_text(domain or "").lower().removeprefix("www.")
    if not normalized:
        return ""
    for known_domain, canonical_name in _OFFICIAL_DOMAIN_ENTITY_MAP.items():
        if normalized == known_domain or normalized.endswith(f".{known_domain}"):
            return canonical_name
    return ""


def _resolve_known_org_name(
    value: str,
    *,
    scope_hints: dict[str, object] | None = None,
    source: SourceDocument | None = None,
) -> str:
    scope_org_names = _scope_org_names_key(scope_hints)
    normalized = _resolve_known_org_name_cached(value, scope_org_names)
    if not normalized:
        return ""
    if source is not None:
        domain_canonical = _canonical_org_name_from_domain(source.domain or extract_domain(source.url))
        if domain_canonical:
            source_text = _source_text(source)
            if any(alias in source_text for alias in _org_surface_variants(domain_canonical)):
                return domain_canonical
            if _is_lightweight_entity_name(normalized):
                return domain_canonical
    return normalized


@lru_cache(maxsize=16384)
def _resolve_known_org_name_cached(value: str, scope_org_names: tuple[str, ...]) -> str:
    normalized = normalize_text(_strip_org_public_suffixes(value))
    if not normalized:
        return ""
    alias_map = _org_alias_lookup_map_cached(scope_org_names)
    for variant in _org_surface_variants(normalized):
        resolved = alias_map.get(_entity_alias_lookup_key(variant))
        if resolved:
            return resolved
    return normalized


def _org_entity_variants(value: str, *, scope_hints: dict[str, object] | None = None) -> list[str]:
    return list(_org_entity_variants_cached(value, _scope_org_names_key(scope_hints)))


@lru_cache(maxsize=8192)
def _org_entity_variants_cached(value: str, scope_org_names: tuple[str, ...]) -> tuple[str, ...]:
    canonical = _resolve_known_org_name_cached(value, scope_org_names)
    if not canonical:
        return ()
    variants = list(_org_surface_variants(canonical))
    for alias, mapped in _RESEARCH_ACCOUNT_ALIAS_MAP.items():
        if normalize_text(mapped) == canonical:
            variants.extend(_org_surface_variants(alias))
    for candidate in [*KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS.keys(), *SPECIAL_ENTITY_ALIASES, *scope_org_names]:
        if _resolve_known_org_name_cached(candidate, scope_org_names) == canonical:
            variants.extend(_org_surface_variants(candidate))
    return tuple(_dedupe_strings(variants, 10))


@lru_cache(maxsize=4096)
def _known_org_alias_candidates_from_text_cached(value: str, scope_org_names: tuple[str, ...]) -> tuple[str, ...]:
    text = normalize_text(value)
    if not text:
        return ()
    candidates: list[str] = []
    for canonical in [
        *KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS.keys(),
        *SPECIAL_ENTITY_ALIASES,
        *_RESEARCH_ACCOUNT_ALIAS_MAP.keys(),
        *scope_org_names,
    ]:
        if any(alias in text for alias in _org_surface_variants(canonical)):
            candidates.append(_resolve_known_org_name_cached(canonical, scope_org_names))
    return tuple(_dedupe_strings(candidates, 12))


def _entity_canonical_key(name: str) -> str:
    return _entity_policy_entity_canonical_key(name)


def _build_entity_graph(
    sources: list[SourceDocument],
    *,
    scope_hints: dict[str, object],
) -> ResearchEntityGraphOut:
    return _ranking_runtime_build_entity_graph(sources, scope_hints=scope_hints)


def _entity_graph_lookup(graph: ResearchEntityGraphOut) -> dict[str, ResearchNormalizedEntityOut]:
    return _entity_graph_builder_lookup(graph, entity_canonical_key=_entity_canonical_key)


def _retrieval_quality_band(
    *,
    strict_match_ratio: float,
    official_source_ratio: float,
    unique_domain_count: int,
    normalized_entity_count: int,
) -> str:
    return _report_ranking_retrieval_quality_band(
        strict_match_ratio=strict_match_ratio,
        official_source_ratio=official_source_ratio,
        unique_domain_count=unique_domain_count,
        normalized_entity_count=normalized_entity_count,
    )


def _evidence_mode_from_metrics(
    *,
    retained_source_count: int,
    strict_topic_source_count: int,
    strict_match_ratio: float,
    official_source_ratio: float,
    unique_domain_count: int,
) -> tuple[str, str]:
    return _report_ranking_evidence_mode_from_metrics(
        retained_source_count=retained_source_count,
        strict_topic_source_count=strict_topic_source_count,
        strict_match_ratio=strict_match_ratio,
        official_source_ratio=official_source_ratio,
        unique_domain_count=unique_domain_count,
    )







def _looks_like_insufficient(value: str) -> bool:
    return _row_quality_looks_like_insufficient(value)


@lru_cache(maxsize=8192)
def _strip_entity_leading_noise(value: str) -> str:
    return _entity_policy_strip_entity_leading_noise(value)


@lru_cache(maxsize=8192)
def _looks_like_sentence_fragment_entity(value: str) -> bool:
    return _entity_policy_looks_like_sentence_fragment_entity(value)


def _looks_like_source_artifact_text(value: str) -> bool:
    return _source_documents_looks_like_artifact(value)


def _looks_like_source_noise_segment(value: str, *, raw_value: str | None = None) -> bool:
    return _source_documents_looks_like_noise_segment(value, raw_value=raw_value)


def _clean_source_text_for_analysis(value: str) -> str:
    return _source_documents_clean_source_text(value)


@lru_cache(maxsize=8192)
def _looks_like_placeholder_entity_name(value: str) -> bool:
    return _entity_policy_looks_like_placeholder_entity_name(value)


def _looks_like_placeholder_contact_row(value: str) -> bool:
    return _entity_policy_looks_like_placeholder_contact_row(value)


def _is_actionable_budget_row(value: str) -> bool:
    return _row_quality_is_actionable_budget_row(value)


def _summary_contains_output_noise(value: str) -> bool:
    return _report_delivery_summary_contains_output_noise(value)


def _report_text_quality_dependencies() -> ReportTextQualityDependencies:
    return _runtime_report_text_quality_dependencies(_build_report_runtime_owner_ports())


def _concrete_rows(values: Iterable[str]) -> list[str]:
    return [normalize_text(value) for value in values if normalize_text(value) and not _looks_like_insufficient(value)]


def _is_summary_fact_row(value: str) -> bool:
    return _row_quality_is_summary_fact_row(value)


def _summary_fact_rows(values: Iterable[str], *, limit: int = 3) -> list[str]:
    return _row_quality_summary_fact_rows(values, limit=limit)


def _looks_like_bad_executive_summary(value: str) -> bool:
    return _report_text_quality_bad_summary(value, deps=_report_text_quality_dependencies())


def _entity_display_labels(values: Iterable[str], *, limit: int = 2) -> list[str]:
    labels: list[str] = []
    for value in values:
        normalized = normalize_text(value)
        if not normalized or _looks_like_insufficient(normalized):
            continue
        if "待验证" in normalized or "待驗證" in normalized:
            continue
        if _looks_like_source_artifact_text(normalized):
            continue
        if any(token in normalized for token in SUMMARY_GUIDANCE_TOKENS):
            continue
        entity_name = _extract_rank_entity_name(normalized) or _fallback_entity_name_from_row(normalized)
        label = _strip_entity_leading_noise(entity_name or normalized.split("：", 1)[0].split(":", 1)[0])
        if (
            not label
            or _looks_like_fragment_entity_name(label)
            or _contains_low_value_entity_token(label)
            or _looks_like_placeholder_entity_name(label)
            or _looks_like_scope_prompt_noise(label)
        ):
            continue
        labels.append(label)
    return _dedupe_strings(labels, limit)


def _company_convergence_is_weak(
    *,
    scope_hints: dict[str, object],
    target_rows: Iterable[str],
    competitor_rows: Iterable[str],
) -> bool:
    if not bool(scope_hints.get("prefer_company_entities")):
        return False
    theme_labels = [
        normalize_text(str(item))
        for item in scope_hints.get("industries", []) or []
        if normalize_text(str(item))
    ]
    seed_companies = [
        normalize_text(str(item))
        for item in scope_hints.get("seed_companies", []) or []
        if normalize_text(str(item))
    ]
    candidates = _dedupe_strings(
        [*_entity_display_labels(target_rows, limit=3), *_entity_display_labels(competitor_rows, limit=3)],
        4,
    )
    concrete = [
        item
        for item in candidates
        if _is_company_like_entity_name(
            item,
            role="target",
            theme_labels=theme_labels,
            seed_companies=seed_companies,
        )
    ]
    minimum = 2 if bool(scope_hints.get("prefer_head_companies")) else 1
    return len(concrete) < minimum


def _company_intent_summary_needs_override(
    *,
    scope_hints: dict[str, object],
    summary: str,
    accounts: list[str],
    competitors: list[str],
) -> bool:
    if not bool(scope_hints.get("prefer_company_entities")):
        return False
    normalized_summary = normalize_text(summary)
    anchors = _dedupe_strings(
        [
            *accounts,
            *competitors,
            *[
                normalize_text(str(item))
                for item in scope_hints.get("seed_companies", []) or []
                if normalize_text(str(item))
            ],
        ],
        4,
    )
    if _company_convergence_is_weak(
        scope_hints=scope_hints,
        target_rows=accounts,
        competitor_rows=competitors,
    ):
        return True
    if not normalized_summary:
        return True
    if anchors and not any(anchor in normalized_summary for anchor in anchors):
        return True
    blocked_tokens = {
        token
        for label in [
            normalize_text(str(item))
            for item in scope_hints.get("industries", []) or []
            if normalize_text(str(item))
        ]
        for token in THEME_ENTITY_BLOCK_TOKENS.get(label, {}).get("target", ())
        if normalize_text(token)
    }
    return any(token in normalized_summary for token in blocked_tokens) and not any(anchor in normalized_summary for anchor in anchors)






@lru_cache(maxsize=8192)
def _contains_low_value_entity_token(value: str) -> bool:
    return _entity_policy_contains_low_value_entity_token(value)


@lru_cache(maxsize=8192)
def _trim_product_spec_from_entity_name(value: str) -> str:
    return _entity_policy_trim_product_spec_from_entity_name(value)


@lru_cache(maxsize=8192)
def _is_lightweight_entity_name(value: str) -> bool:
    return _entity_policy_is_lightweight_entity_name(value)


@lru_cache(maxsize=8192)
def _looks_like_fragment_entity_name(value: str) -> bool:
    return _entity_policy_looks_like_fragment_entity_name(value)


@lru_cache(maxsize=8192)
def _fallback_entity_name_from_row(value: str) -> str:
    return _entity_policy_fallback_entity_name_from_row(value)


def _report_field_sanitization_dependencies() -> ReportFieldSanitizationDependencies:
    return _runtime_report_field_sanitization_dependencies()


@lru_cache(maxsize=8192)
def _is_useful_public_contact_row(value: str) -> bool:
    return _report_field_sanitization_is_public_contact(
        value,
        deps=_report_field_sanitization_dependencies(),
    )


@lru_cache(maxsize=16384)
def _sanitize_entity_row(field_key: str, value: str) -> str:
    return _report_field_sanitization_entity_row(
        field_key,
        value,
        deps=_report_field_sanitization_dependencies(),
    )


def _sanitize_report_field_rows(field_key: str, values: Iterable[str]) -> list[str]:
    return _report_field_sanitization_rows(
        field_key,
        values,
        deps=_report_field_sanitization_dependencies(),
    )


def _expand_region_scope_terms(regions: list[str]) -> list[str]:
    return _scope_hints_expand_regions(regions)


def _text_has_region_conflict(text: str, *, scope_hints: dict[str, object]) -> bool:
    scope_regions = [normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    if not scope_regions:
        return False
    allowed_regions = [item.lower() for item in _expand_region_scope_terms(scope_regions)]
    normalized_text = normalize_text(text).lower()
    if not normalized_text:
        return False
    explicit_region_hits = [region for region in REGION_TOKENS if region.lower() in normalized_text]
    explicit_region_hits.extend(
        label
        for label in REGION_SCOPE_ALIASES
        if label.lower() in normalized_text
    )
    explicit_region_hits = list(dict.fromkeys(explicit_region_hits))
    if not explicit_region_hits:
        return False
    if any(hit.lower() in allowed_regions for hit in explicit_region_hits):
        return False
    return not any(term in normalized_text for term in allowed_regions)


def _source_has_region_conflict(source: SourceDocument, *, scope_hints: dict[str, object]) -> bool:
    return _source_scope_policy_has_region_conflict(
        source,
        scope_hints=scope_hints,
        text_has_region_conflict=_text_has_region_conflict,
        source_text=_source_text,
    )


def _region_conflict_signature(source: SourceDocument) -> str:
    return _source_scope_policy_region_conflict_signature(source)


def _extract_org_candidates(
    sources: list[SourceDocument],
    *,
    limit: int,
    scope_hints: dict[str, object] | None = None,
) -> list[str]:
    candidates: list[str] = []
    for source in sources:
        for match in _extract_rank_entity_candidates(_source_text(source), scope_hints=scope_hints):
            value = normalize_text(match)
            if 2 <= len(value) <= 36:
                candidates.append(value)
    return _dedupe_strings(candidates, limit)


def _render_industry_methodology_context(scope_hints: dict[str, object]) -> str:
    profile = normalize_text(str(scope_hints.get("industry_methodology_profile", "")))
    framework = normalize_text(str(scope_hints.get("industry_methodology_framework", "")))
    authority = normalize_text(str(scope_hints.get("industry_methodology_authority", "")))
    questions = _dedupe_strings(scope_hints.get("industry_methodology_questions", []) or [], 4)
    sources = _dedupe_strings(scope_hints.get("industry_methodology_source_preferences", []) or [], 5)
    if not profile and not framework and not questions:
        return ""
    rows: list[str] = []
    if profile or authority:
        rows.append(f"行业方法论：{profile or '行业研究'}｜{authority or '咨询调研框架'}")
    if framework:
        rows.append(f"分析框架：{framework}")
    if questions:
        rows.append(f"优先核验：{'；'.join(questions)}")
    if sources:
        rows.append(f"来源优先级：{'、'.join(sources)}")
    return "\n".join(rows)


def _infer_input_scope_hints(
    keyword: str,
    research_focus: str | None,
) -> dict[str, object]:
    return _scope_hints_infer_input(keyword, research_focus)


def _infer_scope_hints(
    keyword: str,
    research_focus: str | None,
    sources: list[SourceDocument],
) -> dict[str, object]:
    return _scope_hints_infer(keyword, research_focus, sources)


def _merge_scope_hints(
    base: dict[str, object],
    refined: dict[str, object],
) -> dict[str, object]:
    return _scope_hints_merge(base, refined)


def _build_theme_terms(
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
) -> list[str]:
    return _scope_terms_build_theme_terms(
        keyword,
        research_focus,
        scope_hints,
        deps=_scope_term_dependencies(),
    )


def _build_strict_theme_terms(scope_hints: dict[str, object]) -> list[str]:
    return _scope_terms_build_strict_theme_terms(scope_hints)


def _research_result_needs_override(result: ResearchReportResult) -> bool:
    title = normalize_text(result.report_title).lower()
    summary = normalize_text(result.executive_summary).lower()
    generic_title_tokens = {
        "研究主题待确认",
        "研究主題待確認",
        "research topic pending",
    }
    return (
        title in generic_title_tokens
        or _looks_like_insufficient(summary)
        or len(_concrete_rows(result.target_accounts)) < 2
        or len(_concrete_rows(result.competitor_profiles)) < 2
    )


def _looks_like_bad_report_title(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return True
    lowered = normalized.lower()
    if re.match(r"^(19|20)\d{2}", normalized):
        return True
    if len(normalized) > 42:
        return True
    if any(token in normalized for token in ENTITY_INVALID_PHRASE_TOKENS):
        return True
    if any(token in normalized for token in ("当前证据不足", "当前證據不足", "建议", "建議", "报告", "研报", "研究主题待确认")):
        return True
    if lowered.startswith(("本次", "当前", "建议", "research", "report")):
        return True
    if normalized.count("：") > 1 or normalized.count(":") > 1:
        return True
    if any(token in normalized for token in ("社区", "服务", "系统")) and not any(token in normalized for token in ("公司", "集团", "中心", "平台", "场景", "赛道")):
        return True
    return False


def _is_theme_aligned_report_title(
    value: str,
    *,
    scope_hints: dict[str, object],
    keyword: str,
    research_focus: str | None,
) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return False
    theme_labels = _theme_labels_from_scope(scope_hints, keyword=keyword, research_focus=research_focus)
    if not theme_labels:
        return True
    scope_text = normalize_text(" ".join([keyword, research_focus or "", str(scope_hints.get("anchor_text", ""))]))
    for theme_label in theme_labels:
        blocked_tokens = THEME_ENTITY_BLOCK_TOKENS.get(theme_label, {}).get("target", ())
        if any(token in normalized for token in blocked_tokens) and not any(token in scope_text for token in blocked_tokens):
            return False
    return True


TITLE_SCOPE_GENERIC_TOKENS = (
    "相关商机",
    "潛在商機",
    "潜在商机",
    "市场机会",
    "市場機會",
    "机会分析",
    "機會分析",
    "解决方案",
    "解決方案",
    "研究",
    "研报",
    "報告",
    "报告",
)

SCENARIO_PRIORITY_TOKENS = (
    "漫剧",
    "短剧",
    "动画",
    "動漫",
    "内容",
    "內容",
    "政务服务",
    "政務服務",
    "政务云",
    "政務雲",
    "数据中心",
    "數據中心",
    "采购",
    "採購",
    "招标",
    "標案",
    "预算",
    "預算",
    "平台",
    "场景",
    "場景",
)

TITLE_STAGE_LABELS = (
    ("四期", "扩容窗口"),
    ("三期", "扩容窗口"),
    ("二期", "扩容窗口"),
    ("扩容", "扩容窗口"),
    ("中标", "交付窗口"),
    ("開標", "招标窗口"),
    ("开标", "招标窗口"),
    ("招标", "招标窗口"),
    ("立项", "立项窗口"),
    ("試點", "试点切入"),
    ("试点", "试点切入"),
    ("预算", "预算窗口"),
)


def _sanitize_title_scope_token(value: str) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    if _looks_like_scope_prompt_noise(normalized):
        return ""
    if _looks_like_fragment_entity_name(normalized) or _contains_low_value_entity_token(normalized):
        return ""
    compact = normalized
    for prefix in ("优先关注", "優先關注", "重点关注", "重點關注", "锁定", "鎖定"):
        if compact.startswith(prefix):
            compact = normalize_text(compact[len(prefix) :])
    for token in TITLE_SCOPE_GENERIC_TOKENS:
        compact = compact.replace(token, "")
    compact = re.sub(r"(?:19|20)\d{2}年?", "", compact)
    compact = re.sub(r"[：:|｜/]+$", "", compact)
    compact = re.sub(r"\s+", "", compact)
    compact = _strip_entity_leading_noise(compact)
    if (
        not compact
        or compact in GENERIC_FOCUS_TOKENS
        or _looks_like_placeholder_entity_name(compact)
        or any(token in compact for token in GENERIC_SCOPE_CLIENT_TOKENS)
    ):
        return ""
    if len(compact) > 18:
        return ""
    return compact


def _theme_labels_from_scope(
    scope_hints: dict[str, object],
    *,
    keyword: str,
    research_focus: str | None,
) -> list[str]:
    return _scope_terms_theme_labels_from_scope(
        scope_hints,
        keyword=keyword,
        research_focus=research_focus,
        deps=_scope_term_dependencies(),
    )


def _is_theme_aligned_entity_name(
    value: str,
    *,
    role: str,
    theme_labels: list[str],
) -> bool:
    return _entity_policy_is_theme_aligned_entity_name(value, role=role, theme_labels=theme_labels)


def _filter_theme_aligned_rows(
    values: Iterable[str],
    *,
    role: str,
    theme_labels: list[str],
    scope_hints: dict[str, object],
) -> list[str]:
    filtered: list[str] = []
    seed_companies = [
        normalize_text(str(item))
        for item in (scope_hints.get("seed_companies", []) or [])
        if normalize_text(str(item))
    ]
    prefer_company_entities = bool(scope_hints.get("prefer_company_entities"))
    for value in values:
        normalized = normalize_text(value)
        if not normalized:
            continue
        entity_name = _extract_rank_entity_name(normalized) or _fallback_entity_name_from_row(normalized) or normalized
        if not _is_theme_aligned_entity_name(entity_name, role=role, theme_labels=theme_labels):
            continue
        if prefer_company_entities and role in {"target", "competitor"} and not _is_company_like_entity_name(
            entity_name,
            role=role,
            theme_labels=theme_labels,
            seed_companies=seed_companies,
        ):
            continue
        filtered.append(normalized)
    return _dedupe_strings(filtered, 6)


def _is_company_like_entity_name(
    value: str,
    *,
    role: str,
    theme_labels: list[str],
    seed_companies: list[str],
) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return False
    if normalized in seed_companies or _is_lightweight_entity_name(normalized) or normalized in SPECIAL_ENTITY_ALIASES:
        return True
    if any(
        token in normalized
        for token in ("政府", "市委", "市政府", "局", "委", "办", "中心", "大学", "学院", "学校", "医院", "银行", "证券")
    ):
        return False
    theme_company_tokens = [
        token
        for label in theme_labels
        for token in THEME_ENTITY_ALLOW_TOKENS.get(label, {}).get(role, ())
        if normalize_text(token) and token not in {"内容", "运营", "服务"}
    ]
    return any(token in normalized for token in [*GENERIC_COMPANY_NAME_TOKENS, *theme_company_tokens])


def _filtered_rank_fallback_values(
    values: Iterable[str],
    *,
    role: str,
    scope_hints: dict[str, object],
) -> list[str]:
    return _ranking_runtime_filtered_fallback_values(values, role=role, scope_hints=scope_hints)


def _source_supports_company_intent(
    source: SourceDocument,
    *,
    theme_labels: list[str],
    seed_companies: list[str],
) -> bool:
    text = _source_text(source)
    normalized_text = normalize_text(text)
    title = normalize_text(source.title)
    domain = normalize_text(source.domain or "").lower()
    if any(company and company in normalized_text for company in seed_companies):
        return True
    if any(
        token in normalized_text
        for token in (
            "官网",
            "官網",
            "投资者关系",
            "投資者關係",
            "联系我们",
            "聯絡我們",
            "商务合作",
            "商務合作",
            "商业化",
            "商業化",
            "发行",
            "發行",
            "版权",
            "版權",
            "IP",
        )
    ):
        return True
    blocked_tokens = {
        token
        for label in theme_labels
        for token in THEME_ENTITY_BLOCK_TOKENS.get(label, {}).get("target", ())
        if normalize_text(token)
    }
    if blocked_tokens and any(token in title for token in blocked_tokens) and not any(token in title for token in GENERIC_COMPANY_NAME_TOKENS):
        return False
    if source.source_tier == "official" and domain and not any(
        token in domain for token in ("gov.cn", "ggzy.gov.cn", "ccgp.gov.cn", "cninfo.com.cn", "hkexnews.hk", "mp.weixin.qq.com")
    ):
        return True
    if any(token in title for token in GENERIC_COMPANY_NAME_TOKENS):
        return True
    theme_company_tokens = [
        token
        for label in theme_labels
        for token in THEME_ENTITY_ALLOW_TOKENS.get(label, {}).get("target", ())
        if normalize_text(token) and token not in {"内容", "內容", "运营", "運營", "服务", "服務"}
    ]
    if any(token in title for token in theme_company_tokens):
        return True
    return any(
        _is_company_like_entity_name(
            candidate,
            role="target",
            theme_labels=theme_labels,
            seed_companies=seed_companies,
        )
        for candidate in _extract_rank_entity_candidates(normalized_text)[:6]
    )


def _pick_primary_stage_phrase(stage_rows: Iterable[str]) -> str:
    for row in stage_rows:
        normalized = normalize_text(row)
        if not normalized:
            continue
        for token, label in TITLE_STAGE_LABELS:
            if token in normalized:
                return label
    return ""


def _pick_primary_scenario_hint(
    *,
    keyword: str,
    research_focus: str | None,
    regions: list[str],
    industries: list[str],
    company_anchors: list[str],
) -> str:
    candidates: list[tuple[int, int, str]] = []
    region_set = {normalize_text(item) for item in regions}
    industry_set = {normalize_text(item) for item in industries}
    company_set = {normalize_text(item) for item in company_anchors}
    for token in _extract_topic_anchor_terms(keyword, research_focus):
        normalized = _sanitize_title_scope_token(token)
        if not normalized:
            continue
        if normalized in region_set or normalized in industry_set or normalized in company_set:
            continue
        score = min(len(normalized), 10)
        if any(priority in normalized for priority in SCENARIO_PRIORITY_TOKENS):
            score += 8
        if any(theme in normalized for theme in ("AI", "AIGC", "政务", "內容", "内容", "采购", "招标", "预算", "交付")):
            score += 3
        candidates.append((score, len(normalized), normalized))
    if not candidates:
        return ""
    candidates.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return candidates[0][2]


def _compress_title_segments(segments: Iterable[str], *, limit: int = 3) -> list[str]:
    return _report_delivery_compress_title_segments(segments, limit=limit)


def _scope_anchor_text_segments(value: str | None) -> list[str]:
    return _report_scope_anchor_text_segments(value)


def _build_report_title_suffix(
    *,
    intelligence: dict[str, list[str]],
    selected_company_anchor: str,
    stage_hint: str,
    output_language: str,
) -> str:
    budget_rows = _summary_fact_rows(intelligence.get("budget_signals", []), limit=2)
    timeline_rows = _summary_fact_rows(
        [*intelligence.get("tender_timeline", []), *intelligence.get("project_distribution", [])],
        limit=2,
    )
    competitor_rows = _entity_display_labels(intelligence.get("competitor_profiles", []), limit=2)
    partner_rows = _entity_display_labels(intelligence.get("ecosystem_partners", []), limit=2)
    target_rows = _entity_display_labels(intelligence.get("target_accounts", []), limit=2)
    if stage_hint:
        suffix = f"{stage_hint}与推进路径"
    elif budget_rows and (competitor_rows or partner_rows):
        suffix = "预算信号与切入策略"
    elif competitor_rows or partner_rows:
        suffix = "竞争格局与切入策略"
    elif selected_company_anchor or target_rows:
        suffix = "账户优先级与推进路径"
    elif budget_rows or timeline_rows:
        suffix = "进入窗口与推进路径"
    else:
        suffix = "重点机会与推进路径"
    return localized_text(
        output_language,
        {
            "zh-CN": suffix,
            "zh-TW": suffix.replace("与", "與"),
            "en": (
                "Entry Window & Execution Path"
                if suffix in {"扩容窗口与推进路径", "交付窗口与推进路径", "招标窗口与推进路径", "立项窗口与推进路径", "试点切入与推进路径", "预算窗口与推进路径", "进入窗口与推进路径"}
                else "Budget Signals & Entry Strategy"
                if suffix == "预算信号与切入策略"
                else "Competition Landscape & Entry Strategy"
                if suffix == "竞争格局与切入策略"
                else "Account Priorities & Execution Path"
                if suffix == "账户优先级与推进路径"
                else "Priority Opportunities & Execution Path"
            ),
        },
        suffix,
    )


def _build_exec_summary_override(
    *,
    scope_anchor: str,
    accounts: list[str],
    budgets: list[str],
    competitors: list[str],
    partners: list[str],
    teams: list[str],
    output_language: str,
) -> str:
    conclusion_subject = "、".join(accounts[:2]) if accounts else scope_anchor
    budget_anchor = next((item for item in budgets if _is_actionable_budget_row(item)), "")
    team_anchor = teams[0] if teams else ""
    competitor_anchor = competitors[0] if competitors else ""
    partner_anchor = partners[0] if partners else ""
    if accounts and budget_anchor:
        conclusion_line = f"优先把{conclusion_subject}列为首批推进对象，当前公开信号已经出现{budget_anchor}这类预算或采购窗口。"
    elif accounts:
        conclusion_line = f"优先把{conclusion_subject}列为首批推进对象，先确认预算归口、业务牵头部门和进入窗口。"
    elif budget_anchor:
        conclusion_line = f"当前更适合围绕{scope_anchor}继续收敛到具体账户，尤其优先核验{budget_anchor}对应的项目窗口。"
    else:
        conclusion_line = f"当前应先把{scope_anchor}收敛到 1-2 个可验证账户，再进入更强的商业判断。"
    evidence_parts = _dedupe_strings(
        [
            budget_anchor,
            team_anchor,
            f"竞品侧出现 {competitor_anchor}" if competitor_anchor else "",
            f"伙伴侧可借力 {partner_anchor}" if partner_anchor else "",
        ],
        3,
    )
    evidence_line = (
        f"公开证据目前主要集中在{'、'.join(evidence_parts)}。"
        if evidence_parts
        else "公开证据目前主要集中在范围锁定、账户筛选和进入窗口判断。"
    )
    action_parts: list[str] = []
    if accounts:
        if team_anchor:
            action_parts.append(f"先围绕{conclusion_subject}核验{team_anchor}是否是业务或预算牵头团队")
        else:
            action_parts.append(f"先围绕{conclusion_subject}补业务牵头部门和预算归口")
    else:
        action_parts.append("先把主题收敛到 1-2 个可验证账户，再补预算归口和组织入口")
    if budget_anchor:
        action_parts.append(f"围绕“{budget_anchor}”倒排会前材料和拜访节奏")
    elif team_anchor:
        action_parts.append(f"从{team_anchor}对应的公开入口补联系人与会前材料")
    if competitor_anchor and partner_anchor:
        action_parts.append(f"准备针对{competitor_anchor}的差异化切口，并评估{partner_anchor}是否适合牵线")
    elif competitor_anchor:
        action_parts.append(f"准备针对{competitor_anchor}的差异化切口")
    elif partner_anchor:
        action_parts.append(f"评估{partner_anchor}是否适合作为牵线或联合推进伙伴")
    action_parts.append("把研判拆成两条主线：方案侧先定义场景、试点与扩容路径，打单侧先锁定账户、部门、预算与伙伴节奏")
    action_line = "；".join(_dedupe_strings(action_parts, 3)) or "先锁定重点账户，再补预算归口、组织入口和首轮沟通材料。"
    if output_language.startswith("en"):
        return (
            f"Prioritize {conclusion_subject} as the first execution target within {scope_anchor}. "
            f"The strongest public signals currently cluster around {', '.join(evidence_parts) if evidence_parts else 'account scoping, buyer qualification, and entry timing'}. "
            f"The next step is to {action_line.rstrip('.')}."
        )
    return f"{conclusion_line}{evidence_line}下一步建议{action_line.rstrip('。')}。"


def _build_scope_summary_sentence(
    *,
    scope_anchor: str,
    accounts: list[str],
    budgets: list[str],
    competitors: list[str],
    partners: list[str],
    teams: list[str],
    output_language: str,
) -> str:
    clauses: list[str] = [
        localized_text(
            output_language,
            {
                "zh-CN": f"本次研判锁定在 {scope_anchor} 范围内",
                "zh-TW": f"本次研判鎖定在 {scope_anchor} 範圍內",
                "en": f"This memo is constrained to {scope_anchor}",
            },
            f"本次研判锁定在 {scope_anchor} 范围内",
        )
    ]
    if accounts:
        clauses.append(localized_text(output_language, {"zh-CN": f"甲方线索优先收敛到 {'、'.join(accounts[:2])}", "zh-TW": f"甲方線索優先收斂到 {'、'.join(accounts[:2])}", "en": f"buyer-side leads converge around {' / '.join(accounts[:2])}"}, f"甲方线索优先收敛到 {'、'.join(accounts[:2])}"))
    if budgets:
        clauses.append(localized_text(output_language, {"zh-CN": f"预算与采购信号集中在 {'、'.join(budgets[:2])}", "zh-TW": f"預算與採購信號集中在 {'、'.join(budgets[:2])}", "en": f"budget and procurement signals cluster around {' / '.join(budgets[:2])}"}, f"预算与采购信号集中在 {'、'.join(budgets[:2])}"))
    if competitors:
        clauses.append(localized_text(output_language, {"zh-CN": f"高相关竞合对象包括 {'、'.join(competitors[:2])}", "zh-TW": f"高相關競合對象包括 {'、'.join(competitors[:2])}", "en": f"high-relevance competitors include {' / '.join(competitors[:2])}"}, f"高相关竞合对象包括 {'、'.join(competitors[:2])}"))
    if partners:
        clauses.append(localized_text(output_language, {"zh-CN": f"可用生态抓手集中在 {'、'.join(partners[:2])}", "zh-TW": f"可用生態抓手集中在 {'、'.join(partners[:2])}", "en": f"ecosystem leverage points include {' / '.join(partners[:2])}"}, f"可用生态抓手集中在 {'、'.join(partners[:2])}"))
    if teams:
        clauses.append(localized_text(output_language, {"zh-CN": f"活跃团队线索包括 {'、'.join(teams[:2])}", "zh-TW": f"活躍團隊線索包括 {'、'.join(teams[:2])}", "en": f"active team signals include {' / '.join(teams[:2])}"}, f"活跃团队线索包括 {'、'.join(teams[:2])}"))
    sentence = "，".join(clauses)
    if output_language.startswith("en"):
        return sentence + "."
    return sentence + "。"


def _select_title_company_anchor(
    company_anchors: list[str],
    *,
    scope_hints: dict[str, object],
    keyword: str,
    research_focus: str | None,
) -> str:
    theme_labels = _theme_labels_from_scope(scope_hints, keyword=keyword, research_focus=research_focus)
    if not company_anchors:
        return ""
    for candidate in company_anchors:
        normalized = normalize_text(candidate)
        if not normalized:
            continue
        if not _is_theme_aligned_entity_name(normalized, role="target", theme_labels=theme_labels):
            continue
        return normalized
    return ""


def _build_report_title_override(
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
    intelligence: dict[str, list[str]],
    output_language: str,
) -> str:
    regions = _dedupe_strings([normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))], 2)
    industries = _dedupe_strings([normalize_text(str(item)) for item in scope_hints.get("industries", []) if normalize_text(str(item))], 2)
    theme_labels = _theme_labels_from_scope(scope_hints, keyword=keyword, research_focus=research_focus)
    company_anchors = _clean_scope_entity_names(
        [
            *[_extract_rank_entity_name(item) for item in intelligence.get("target_accounts", []) if _extract_rank_entity_name(item)],
            *[normalize_text(str(item)) for item in scope_hints.get("company_anchors", []) if normalize_text(str(item))],
        ],
        limit=4,
        theme_labels=theme_labels,
    )
    company_anchors = [
        item
        for item in company_anchors
        if normalize_text(item)
        and not _looks_like_fragment_entity_name(item)
        and not _contains_low_value_entity_token(item)
        and (
            item in KNOWN_LIGHTWEIGHT_ENTITY_NAMES
            or any(token in item for token in ENTITY_SUFFIX_TOKENS)
            or any(token in item for token in ("集团", "公司", "平台", "银行", "大学", "医院", "中心", "局", "委", "办"))
        )
    ]
    selected_company_anchor = _select_title_company_anchor(
        company_anchors,
        scope_hints=scope_hints,
        keyword=keyword,
        research_focus=research_focus,
    )
    stage_rows = _dedupe_strings(
        [
            *[normalize_text(item) for item in intelligence.get("tender_timeline", []) if normalize_text(item)],
            *[normalize_text(item) for item in intelligence.get("project_distribution", []) if normalize_text(item)],
        ],
        2,
    )
    stage_hint = _pick_primary_stage_phrase(stage_rows)
    scenario_hint = _pick_primary_scenario_hint(
        keyword=keyword,
        research_focus=research_focus,
        regions=regions,
        industries=industries,
        company_anchors=company_anchors,
    )
    scope_segments = _compress_title_segments(
        [
            *regions[:1],
            scenario_hint or (industries[0] if industries else ""),
            selected_company_anchor,
        ],
        limit=3,
    )
    if not scope_segments:
        scope_segments = _compress_title_segments(
            [
                normalize_text(str(scope_hints.get("anchor_text", ""))),
                normalize_text(research_focus or ""),
                normalize_text(keyword),
            ],
            limit=3,
        )
    title_scope = "｜".join(scope_segments)
    if not title_scope:
        title_scope = normalize_text(keyword)
    suffix = _build_report_title_suffix(
        intelligence=intelligence,
        selected_company_anchor=selected_company_anchor,
        stage_hint=stage_hint,
        output_language=output_language,
    )
    return localized_text(
        output_language,
        {
            "zh-CN": f"{title_scope}：{suffix}",
            "zh-TW": f"{title_scope}：{suffix}",
            "en": f"{title_scope}: {suffix}",
        },
        f"{title_scope}：{suffix}",
    )


def _strategy_refinement_dependencies() -> StrategyRefinementDependencies:
    return StrategyRefinementDependencies(
        theme_labels_from_scope=_theme_labels_from_scope,
        filter_theme_aligned_rows=_filter_theme_aligned_rows,
        entity_display_labels=_entity_display_labels,
        summary_fact_rows=_summary_fact_rows,
        is_actionable_budget_row=_is_actionable_budget_row,
        research_result_needs_override=_research_result_needs_override,
        company_intent_summary_needs_override=_company_intent_summary_needs_override,
        summary_contains_output_noise=_summary_contains_output_noise,
        build_report_title_override=_build_report_title_override,
        build_scope_summary_sentence=_build_scope_summary_sentence,
        looks_like_insufficient=_looks_like_insufficient,
        looks_like_bad_executive_summary=_looks_like_bad_executive_summary,
        build_exec_summary_override=_build_exec_summary_override,
        concrete_rows=_concrete_rows,
        dedupe_strings=_dedupe_strings,
        get_strategy_llm_service=lambda: instrument_llm_service(
            get_strategy_llm_service(),
            role="strategy",
        ),
        parse_strategy_scope_response=parse_research_strategy_scope_response,
        parse_strategy_refine_response=parse_research_strategy_refine_response,
        merge_scope_hints=_merge_scope_hints,
        looks_like_bad_report_title=_looks_like_bad_report_title,
        is_theme_aligned_report_title=_is_theme_aligned_report_title,
    )


def _apply_topic_specific_overrides(
    result: ResearchReportResult,
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    scope_hints: dict[str, object],
    intelligence: dict[str, list[str]],
) -> ResearchReportResult:
    return _report_delivery_apply_topic_overrides(
        result,
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        scope_hints=scope_hints,
        intelligence=intelligence,
    )


def _apply_strategy_scope_planning(
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    input_scope_hints: dict[str, object],
) -> dict[str, object]:
    return _strategy_refinement_apply_scope(
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        input_scope_hints=input_scope_hints,
        deps=_strategy_refinement_dependencies(),
    )


def _apply_strategy_llm_refinement(
    result: ResearchReportResult,
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    scope_hints: dict[str, object],
    intelligence: dict[str, list[str]],
) -> ResearchReportResult:
    return _strategy_refinement_apply_llm(
        result,
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        scope_hints=scope_hints,
        intelligence=intelligence,
        deps=_strategy_refinement_dependencies(),
    )


def _build_expanded_query_plan(
    keyword: str,
    research_focus: str | None,
    *,
    scope_hints: dict[str, object],
    include_wechat: bool,
    preferred_wechat_accounts: Iterable[str] | None = None,
    limit: int = 8,
) -> list[str]:
    return _source_query_plans_build_expanded(
        keyword,
        research_focus,
        scope_hints=scope_hints,
        include_wechat=include_wechat,
        preferred_wechat_accounts=preferred_wechat_accounts,
        limit=limit,
        deps=_source_query_plan_dependencies(),
    )


def _build_company_contact_query_plan(
    company_names: list[str],
    *,
    keyword: str,
    research_focus: str | None,
    limit: int = 8,
) -> list[str]:
    return _source_query_plans_build_company_contact(
        company_names,
        keyword=keyword,
        research_focus=research_focus,
        limit=limit,
        deps=_source_query_plan_dependencies(),
    )


def _build_company_profile_query_plan(
    company_names: list[str],
    *,
    keyword: str,
    research_focus: str | None,
    limit: int = 8,
) -> list[str]:
    return _source_query_plans_build_company_profile(
        company_names,
        keyword=keyword,
        research_focus=research_focus,
        limit=limit,
        deps=_source_query_plan_dependencies(),
    )


def _build_company_team_query_plan(
    company_names: list[str],
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
    limit: int = 8,
) -> list[str]:
    return _source_query_plans_build_company_team(
        company_names,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
        limit=limit,
        deps=_source_query_plan_dependencies(),
    )


def _ranking_source_utility_dependencies() -> RankingSourceUtilityDependencies:
    return RankingSourceUtilityDependencies(
        source_text=_source_text,
        truncate_text=_truncate_text,
        is_plausible_entity_name=_is_plausible_entity_name,
        dedupe_strings=_dedupe_strings,
        org_pattern=ORG_PATTERN,
        person_role_pattern=PERSON_ROLE_PATTERN,
        department_pattern=DEPARTMENT_PATTERN,
        email_pattern=EMAIL_PATTERN,
        phone_pattern=PHONE_PATTERN,
        generic_content_domains=GENERIC_CONTENT_DOMAINS,
    )


def _rank_org_rows(
    sources: list[SourceDocument],
    *,
    role: str,
    context_keywords: tuple[str, ...],
    preferred_source_types: tuple[str, ...],
    name_bias_tokens: tuple[str, ...],
    scope_hints: dict[str, object],
    theme_terms: list[str],
    limit: int,
) -> list[str]:
    return _ranking_source_rank_org_rows(
        sources,
        role=role,
        context_keywords=context_keywords,
        preferred_source_types=preferred_source_types,
        name_bias_tokens=name_bias_tokens,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        limit=limit,
        deps=_ranking_source_utility_dependencies(),
    )


def _extract_key_people_rows(
    sources: list[SourceDocument],
    *,
    scope_hints: dict[str, object],
    limit: int,
) -> list[str]:
    return _ranking_source_extract_key_people_rows(
        sources,
        scope_hints=scope_hints,
        limit=limit,
        deps=_ranking_source_utility_dependencies(),
    )


def _extract_department_rows(
    sources: list[SourceDocument],
    *,
    scope_hints: dict[str, object],
    limit: int,
) -> list[str]:
    return _ranking_source_extract_department_rows(
        sources,
        scope_hints=scope_hints,
        limit=limit,
        deps=_ranking_source_utility_dependencies(),
    )


def _extract_public_contact_rows(
    sources: list[SourceDocument],
    *,
    output_language: str,
    limit: int,
) -> list[str]:
    return _ranking_source_extract_public_contact_rows(
        sources,
        output_language=output_language,
        limit=limit,
        deps=_ranking_source_utility_dependencies(),
    )


def _source_mentions_entity(source: SourceDocument, entity_name: str) -> bool:
    normalized_name = normalize_text(entity_name)
    if not normalized_name:
        return False
    return _source_mentions_entity_cached(_source_text(source), normalized_name)


@lru_cache(maxsize=16384)
def _source_mentions_entity_cached(text: str, normalized_name: str) -> bool:
    variants = _org_entity_variants(normalized_name)
    if any(variant in text for variant in variants):
        return True
    canonical_name = _entity_canonical_key(normalized_name)
    canonical_text = _entity_canonical_key(text)
    return bool(canonical_name and canonical_text and canonical_name in canonical_text)


def _source_negates_entity(source: SourceDocument, entity_name: str) -> bool:
    normalized_name = normalize_text(entity_name)
    if not normalized_name:
        return False
    negative_tokens = ("未提及", "未出现", "未涉及", "未覆盖", "没有提及", "并未提及", "并未出现", "不涉及", "未见")
    for sentence in re.split(r"[。！？!?；;\n]", _source_text(source)):
        normalized_sentence = normalize_text(sentence)
        if normalized_name in normalized_sentence and any(token in normalized_sentence for token in negative_tokens):
            return True
    return False


def _build_entity_specific_contact_rows(
    sources: list[SourceDocument],
    *,
    entity_names: list[str],
    output_language: str,
    limit: int,
) -> list[str]:
    return _ranking_runtime_build_contact_rows(
        sources,
        entity_names=entity_names,
        output_language=output_language,
        limit=limit,
    )


def _build_entity_specific_team_rows(
    sources: list[SourceDocument],
    *,
    entity_names: list[str],
    scope_hints: dict[str, object],
    output_language: str,
    limit: int,
) -> list[str]:
    return _ranking_runtime_build_team_rows(
        sources,
        entity_names=entity_names,
        scope_hints=scope_hints,
        output_language=output_language,
        limit=limit,
    )


def _source_type_weight(source: SourceDocument) -> int:
    if source.source_tier == "official":
        return 18
    if source.source_tier == "aggregate":
        return 12
    return 8


def _build_entity_evidence(
    source: SourceDocument,
) -> ResearchEntityEvidenceOut:
    return ResearchEntityEvidenceOut(
        title=source.title,
        url=source.url,
        source_label=source.source_label,
        source_tier=source.source_tier if source.source_tier in {"official", "media", "aggregate"} else "media",
        excerpt=_clean_source_text_for_analysis(source.excerpt or source.snippet),
    )


def _extract_rank_entity_name(value: str) -> str:
    return _entity_policy_extract_rank_entity_name(value)


@lru_cache(maxsize=16384)
def _is_plausible_entity_name(value: str) -> bool:
    return _entity_policy_is_plausible_entity_name(value)


def _extract_rank_entity_candidates(
    value: str,
    *,
    scope_hints: dict[str, object] | None = None,
) -> list[str]:
    return list(_extract_rank_entity_candidates_cached(value, _scope_org_names_key(scope_hints)))


@lru_cache(maxsize=16384)
def _extract_rank_entity_candidates_cached(
    value: str,
    scope_org_names: tuple[str, ...],
) -> tuple[str, ...]:
    text = normalize_text(value)
    if not text:
        return ()
    candidates: list[str] = []
    for match in ORG_PATTERN.findall(text):
        candidates.append(normalize_text(match))
    for match in COMPACT_ENTITY_PATTERN.findall(text):
        candidates.append(normalize_text(match))
    for alias in KNOWN_LIGHTWEIGHT_ENTITY_NAMES:
        if alias in text:
            candidates.append(alias)
    candidates.extend(_known_org_alias_candidates_from_text_cached(text, scope_org_names))
    filtered: list[str] = []
    for candidate in candidates:
        normalized = _resolve_known_org_name_cached(candidate, scope_org_names)
        normalized = _trim_product_spec_from_entity_name(normalized)
        normalized = _strip_entity_leading_noise(normalized)
        if not _is_plausible_entity_name(normalized) and not _is_lightweight_entity_name(normalized):
            continue
        if _looks_like_fragment_entity_name(normalized):
            continue
        if (
            any(connector in normalized for connector in ("与", "及", "和"))
            and normalized not in SPECIAL_ENTITY_ALIASES
            and not any(token in normalized for token in ENTITY_SUFFIX_TOKENS)
        ):
            continue
        filtered.append(normalized)
    return tuple(_dedupe_strings(filtered, 5))


def _entity_ranking_heuristic_dependencies() -> EntityRankingHeuristicDependencies:
    return EntityRankingHeuristicDependencies(
        clean_scope_entity_names=_clean_scope_entity_names,
        entity_graph_lookup=_entity_graph_lookup,
        is_theme_aligned_entity_name=_is_theme_aligned_entity_name,
        is_company_like_entity_name=_is_company_like_entity_name,
        source_text=_source_text,
        extract_rank_entity_candidates=_extract_rank_entity_candidates,
        canonical_org_name_from_domain=_canonical_org_name_from_domain,
        dedupe_strings=_dedupe_strings,
        resolve_known_org_name=_resolve_known_org_name,
        source_type_weight=_source_type_weight,
        build_entity_evidence=_build_entity_evidence,
        entity_canonical_key=_entity_canonical_key,
        extract_rank_entity_name=_extract_rank_entity_name,
        extract_org_candidates=_extract_org_candidates,
        is_plausible_entity_name=_is_plausible_entity_name,
        is_lightweight_entity_name=_is_lightweight_entity_name,
        org_entity_variants=_org_entity_variants,
        source_mentions_entity=_source_mentions_entity,
        source_negates_entity=_source_negates_entity,
        known_company_public_source_seeds=KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS,
        company_profile_page_tokens=COMPANY_PROFILE_PAGE_TOKENS,
        theme_entity_allow_tokens=THEME_ENTITY_ALLOW_TOKENS,
        generic_company_name_tokens=GENERIC_COMPANY_NAME_TOKENS,
        theme_role_archetypes=THEME_ROLE_ARCHETYPES,
        partner_connector_aliases=PARTNER_CONNECTOR_ALIASES,
    )


def _rank_top_entities(
    sources: list[SourceDocument],
    *,
    role: str,
    output_language: str,
    scope_hints: dict[str, object],
    theme_terms: list[str],
    entity_graph: ResearchEntityGraphOut | None = None,
    fallback_values: Iterable[str] | None = None,
    limit: int = 3,
) -> tuple[list[ResearchRankedEntityOut], list[ResearchRankedEntityOut]]:
    return _ranking_runtime_rank_top_entities(
        sources,
        role=role,
        output_language=output_language,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        entity_graph=entity_graph,
        fallback_values=fallback_values,
        limit=limit,
    )


def _build_candidate_profile_support(
    profile_sources: list[SourceDocument],
    candidate_names: Iterable[str],
) -> dict[str, dict[str, object]]:
    return _entity_ranking_build_candidate_profile_support(
        profile_sources,
        candidate_names,
        deps=_entity_ranking_heuristic_dependencies(),
    )


def _promote_pending_entities_with_candidate_profiles(
    results: list[ResearchRankedEntityOut],
    pending: list[ResearchRankedEntityOut],
    *,
    candidate_profile_support: dict[str, dict[str, object]],
    limit: int = 3,
) -> tuple[list[ResearchRankedEntityOut], list[ResearchRankedEntityOut]]:
    return _entity_ranking_promote_pending_with_profiles(
        results,
        pending,
        candidate_profile_support=candidate_profile_support,
        limit=limit,
    )


def _build_source_intelligence(
    sources: list[SourceDocument],
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    scope_hints: dict[str, object],
) -> dict[str, list[str]]:
    return _report_delivery_build_source_intelligence(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        scope_hints=scope_hints,
    )


def _merge_result_with_intelligence(
    parsed: ResearchReportResult,
    intelligence: dict[str, list[str]],
) -> ResearchReportResult:
    return _report_delivery_merge_result_with_intelligence(parsed, intelligence)


def _source_quality_level(sources: list[SourceDocument]) -> str:
    return _report_delivery_source_quality_level(sources)


def _official_coverage_is_weak(
    sources: list[SourceDocument],
    *,
    min_ratio: float,
    min_count: int,
) -> bool:
    if not sources:
        return True
    official_count = sum(1 for source in sources if source.source_tier == "official")
    official_ratio = official_count / max(len(sources), 1)
    return official_count < min_count or official_ratio < min_ratio


def _evidence_density_level(sources: list[SourceDocument], parsed: ResearchReportResult) -> str:
    return _report_delivery_evidence_density_level(sources, parsed)


def _report_readiness_dependencies() -> ReportReadinessDependencies:
    return _runtime_report_readiness_dependencies(_build_report_runtime_owner_ports())


def _resolved_report_readiness(report: ResearchReportDocument) -> ResearchReportReadinessOut:
    return _report_readiness_resolved(report, deps=_report_readiness_dependencies())


def _is_low_signal_execution_report(report: ResearchReportDocument) -> bool:
    return _report_readiness_is_low_signal(report, deps=_report_readiness_dependencies())


def _delivery_materials_dependencies() -> DeliveryMaterialsDependencies:
    return DeliveryMaterialsDependencies(
        dedupe_strings=_dedupe_strings,
        theme_labels_from_scope=_theme_labels_from_scope,
        entity_names_from_ranked=_entity_names_from_ranked,
        looks_like_scope_prompt_noise=_looks_like_scope_prompt_noise,
        looks_like_placeholder_entity_name=_looks_like_placeholder_entity_name,
        looks_like_fragment_entity_name=_looks_like_fragment_entity_name,
        contains_low_value_entity_token=_contains_low_value_entity_token,
        is_trustworthy_scope_client_name=_is_trustworthy_scope_client_name,
        is_theme_aligned_entity_name=_is_theme_aligned_entity_name,
        is_lightweight_entity_name=_is_lightweight_entity_name,
        entity_display_labels=_entity_display_labels,
        is_actionable_budget_row=_is_actionable_budget_row,
        summary_fact_rows=_summary_fact_rows,
        derive_entry_window=_derive_entry_window,
        truncate_sentence=_truncate_sentence,
        is_useful_public_contact_row=_is_useful_public_contact_row,
        looks_like_placeholder_contact_row=_looks_like_placeholder_contact_row,
        looks_like_source_artifact_text=_looks_like_source_artifact_text,
        resolved_report_readiness=_resolved_report_readiness,
        is_low_signal_execution_report=_is_low_signal_execution_report,
        field_row_noise_tokens=FIELD_ROW_NOISE_TOKENS,
    )


def _build_commercial_summary(report: ResearchReportDocument) -> ResearchCommercialSummaryOut:
    return _delivery_materials_build_commercial_summary(report, deps=_delivery_materials_dependencies())


def _build_technical_appendix(report: ResearchReportDocument) -> ResearchTechnicalAppendixOut:
    return _delivery_materials_build_technical_appendix(report, deps=_delivery_materials_dependencies())


def _build_review_queue(report: ResearchReportDocument) -> list[ResearchReviewQueueItemOut]:
    return _delivery_materials_build_review_queue(report, deps=_delivery_materials_dependencies())


def _enrich_report_for_delivery(report: ResearchReportResponse) -> ResearchReportResponse:
    return _report_delivery_enrich_report(report)


def _build_source_diagnostics(
    sources: list[SourceDocument],
    *,
    enabled_source_labels: list[str],
    scope_hints: dict[str, object],
    recency_window_years: int,
    filtered_old_source_count: int,
    filtered_region_conflict_count: int,
    retained_source_count: int,
    strict_topic_source_count: int,
    topic_anchor_terms: list[str],
    matched_theme_labels: list[str],
    entity_graph: ResearchEntityGraphOut,
    expansion_triggered: bool,
    corrective_triggered: bool,
    candidate_profile_companies: list[str],
    candidate_profile_hit_count: int,
    candidate_profile_official_hit_count: int,
    candidate_profile_source_labels: list[str],
) -> ResearchSourceDiagnosticsOut:
    return _report_ranking_build_source_diagnostics(
        sources,
        enabled_source_labels=enabled_source_labels,
        scope_hints=scope_hints,
        recency_window_years=recency_window_years,
        filtered_old_source_count=filtered_old_source_count,
        filtered_region_conflict_count=filtered_region_conflict_count,
        retained_source_count=retained_source_count,
        strict_topic_source_count=strict_topic_source_count,
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


def _quality_expansion_dependencies() -> QualityExpansionDependencies:
    return QualityExpansionDependencies(
        get_settings=get_settings,
        dedupe_strings=_dedupe_strings,
        infer_input_scope_hints=_infer_input_scope_hints,
        infer_scope_hints=_infer_scope_hints,
        merge_scope_hints=_merge_scope_hints,
        build_corrective_query_plan=_build_corrective_query_plan,
        build_expanded_query_plan=_build_expanded_query_plan,
        curated_wechat_channels=CURATED_WECHAT_CHANNELS,
        build_company_seed_hits=_build_company_seed_hits,
        search_public_web=_search_public_web,
        hybrid_rank_hits=_hybrid_rank_hits,
        select_hits_with_source_balance=_select_hits_with_source_balance,
        dedupe_hits=_dedupe_hits,
        extract_source_document_best_effort=_extract_source_document_best_effort,
        filter_recent_sources=_filter_recent_sources,
        build_theme_terms=_build_theme_terms,
        resolved_company_anchor_terms=_resolved_company_anchor_terms,
        refine_sources_for_report=_refine_sources_for_report,
        stored_report_to_result=_stored_report_to_result,
        build_entity_graph=_build_entity_graph,
        rank_top_entities=_rank_top_entities,
        filtered_rank_fallback_values=_filtered_rank_fallback_values,
        build_entity_specific_contact_rows=_build_entity_specific_contact_rows,
        build_entity_specific_team_rows=_build_entity_specific_team_rows,
        extract_topic_anchor_terms=_extract_topic_anchor_terms,
        collect_matched_theme_labels=_collect_matched_theme_labels,
        build_source_diagnostics=_build_source_diagnostics,
        source_max_age_years=SOURCE_MAX_AGE_YEARS,
        evidence_density_level=_evidence_density_level,
        source_quality_level=_source_quality_level,
        source_documents_to_outputs=_to_research_source_outputs,
        build_sections=_build_sections,
        enrich_report_for_delivery=_enrich_report_for_delivery,
        report_sources_to_source_documents=_report_sources_to_source_documents,
        dedupe_sources=_dedupe_sources,
        review_generation_grounding=review_generation_grounding,
        evaluate_and_improve_research_report=evaluate_and_improve_research_report,
        emit_research_progress=_emit_research_progress,
        build_progress_message=_build_progress_message,
    )


def _expand_report_public_sources_until_quality_improves(
    report: ResearchReportResponse,
    *,
    source_documents: list[SourceDocument],
    runtime: dict[str, int | str | bool] | None = None,
    progress_callback: ResearchProgressCallback | None = None,
) -> ResearchReportResponse:
    return _quality_expansion_expand_report(
        report,
        source_documents=source_documents,
        runtime=runtime,
        progress_callback=progress_callback,
        deps=_quality_expansion_dependencies(),
    )


def _collect_matched_theme_labels(
    sources: list[SourceDocument],
    *,
    scope_hints: dict[str, object],
    topic_anchor_terms: list[str],
) -> list[str]:
    return _report_scope_collect_matched_theme_labels(
        sources,
        scope_hints=scope_hints,
        topic_anchor_terms=topic_anchor_terms,
    )


def _render_source_digest(sources: list[SourceDocument]) -> str:
    chunks: list[str] = []
    for index, source in enumerate(sources, start=1):
        chunks.append(
            "\n".join(
                [
                    f"[Source {index}]",
                    f"Title: {source.title}",
                    f"Domain: {source.domain or 'unknown'}",
                    f"Label: {source.source_label or 'unknown'}",
                    f"Tier: {source.source_tier}",
                    f"URL: {source.url}",
                    f"Search Query: {source.search_query}",
                    f"Snippet: {source.snippet}",
                    f"Excerpt: {source.excerpt}",
                ]
            )
        )
    return "\n\n".join(chunks)


def _source_documents_to_runtime_retrieval_chunks(
    sources: list[SourceDocument],
    *,
    scope_hints: dict[str, object],
) -> list[ResearchRetrievalIndexChunk]:
    regions = [normalize_text(str(item)) for item in scope_hints.get("regions", []) or [] if normalize_text(str(item))]
    industries = [normalize_text(str(item)) for item in scope_hints.get("industries", []) or [] if normalize_text(str(item))]
    now = datetime.now(timezone.utc)
    chunks: list[ResearchRetrievalIndexChunk] = []
    for index, source in enumerate(sources, start=1):
        text = normalize_text(
            "；".join(
                part
                for part in [
                    source.title,
                    source.search_query,
                    source.snippet,
                    source.excerpt,
                ]
                if normalize_text(part)
            )
        )
        if not text:
            continue
        document_id = normalize_text(source.url) or f"runtime-source-{index}"
        label = normalize_text(source.source_label or "") or normalize_text(source.source_type or "") or "runtime_source"
        chunks.append(
            ResearchRetrievalIndexChunk(
                chunk_id=f"runtime-source-{index}",
                document_id=document_id,
                document_type="runtime_source",
                title=normalize_text(source.title) or document_id,
                text=text[:840],
                field_key="source_excerpt",
                label=label,
                source_tier=source.source_tier if source.source_tier in {"official", "media", "aggregate"} else "media",
                source_url=normalize_text(source.url),
                region=" / ".join(regions[:2]),
                industry=" / ".join(industries[:2]),
                created_at=now,
                updated_at=now,
                priority=18 if source.source_tier == "official" else 10 if source.source_tier == "media" else 7,
                metadata={
                    "source_type": normalize_text(source.source_type),
                    "content_status": normalize_text(source.content_status),
                },
            )
        )
    return chunks


def _load_runtime_research_retrieval_index(
    *,
    sources: list[SourceDocument],
    scope_hints: dict[str, object],
) -> ResearchRetrievalIndex:
    settings = get_settings()
    base_index = ResearchRetrievalIndex(chunks=[], built_at=datetime.now(timezone.utc), source_counts={})
    try:
        with SessionLocal() as db:
            base_index = load_persistent_research_retrieval_index(
                db,
                user_id=settings.single_user_id,
                limit=6000,
            )
            if not base_index.chunks:
                base_index = build_research_retrieval_index(
                    db,
                    user_id=settings.single_user_id,
                    limit_per_source=240,
                )
    except Exception:
        base_index = ResearchRetrievalIndex(chunks=[], built_at=datetime.now(timezone.utc), source_counts={})

    runtime_chunks = _source_documents_to_runtime_retrieval_chunks(sources, scope_hints=scope_hints)
    combined_chunks = [*runtime_chunks, *base_index.chunks]
    return ResearchRetrievalIndex(
        chunks=combined_chunks,
        built_at=datetime.now(timezone.utc),
        source_counts=dict(Counter(chunk.document_type for chunk in combined_chunks)),
    )


def _render_section_retrieval_prompt_context(
    report: ResearchReportDocument,
    *,
    index: ResearchRetrievalIndex,
    limit_per_section: int = 3,
) -> str:
    return _section_retrieval_render_prompt_context(
        report,
        index=index,
        limit_per_section=limit_per_section,
    )


def _build_sections(
    result: ResearchReportResult,
    output_language: str,
    sources: list[SourceDocument],
) -> list[ResearchReportSectionOut]:
    return _report_delivery_build_sections(result, output_language, sources)

def _truncate_sentence(value: str, limit: int = 82) -> str:
    text = normalize_text(value)
    if len(text) <= limit:
        return text
    clipped = text[: limit - 1].rstrip(" ，,：:；;、")
    return f"{clipped}…"


def _entity_names_from_ranked(
    ranked: list[ResearchRankedEntityOut],
    fallback_rows: list[str],
    *,
    limit: int = 3,
) -> list[str]:
    return _action_cards_entity_names_from_ranked(
        ranked,
        fallback_rows,
        limit=limit,
        deps=_action_card_dependencies(),
    )


def _derive_entry_window(report: ResearchReportDocument, output_language: str) -> str:
    return _action_cards_derive_entry_window(report, output_language)


def _action_card_dependencies() -> ResearchActionCardDependencies:
    return _runtime_action_card_dependencies(_build_report_runtime_owner_ports())


def build_research_action_cards(report: ResearchReportDocument) -> list[ResearchActionCardOut]:
    return _action_cards_build(report, deps=_action_card_dependencies())


def _emit_research_progress(
    progress_callback: ResearchProgressCallback | None,
    stage_key: str,
    progress_percent: int,
    message: str,
) -> None:
    if progress_callback is None:
        return
    progress_callback(stage_key, progress_percent, message)


def _emit_research_snapshot(
    snapshot_callback: ResearchSnapshotCallback | None,
    report: ResearchReportResponse,
) -> None:
    if snapshot_callback is None:
        return
    snapshot_callback(report)


def _resolve_research_mode(payload: ResearchReportRequest) -> str:
    mode = normalize_text(str(getattr(payload, "research_mode", "") or "")).lower()
    if mode in {"fast", "deep"}:
        return mode
    deep_flag = getattr(payload, "deep_research", None)
    if deep_flag is False:
        return "fast"
    return "deep"


def _safe_int(value: object, default: int, *, minimum: int = 0, maximum: int = 1000) -> int:
    try:
        parsed = int(value if value is not None else default)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _report_runtime_strategy_payload(payload: ResearchReportRequest) -> dict[str, Any]:
    data = getattr(payload, "runtime_strategy_config", {}) or {}
    return data if isinstance(data, dict) else {}


def _runtime_consumer_payload(payload: ResearchReportRequest, consumer: str) -> dict[str, Any]:
    data = _report_runtime_strategy_payload(payload).get(consumer)
    return data if isinstance(data, dict) else {}


def _runtime_consumer_effective_config(payload: ResearchReportRequest, consumer: str) -> dict[str, Any]:
    data = _runtime_consumer_payload(payload, consumer)
    effective = data.get("effective_config")
    return effective if isinstance(effective, dict) else {}


def _runtime_strategy_scope_hints(payload: ResearchReportRequest) -> dict[str, object]:
    return _runtime_config_build_runtime_strategy_scope_hints(
        payload,
        dedupe_strings=_dedupe_strings,
        safe_int=_safe_int,
    )


def _build_research_runtime(payload: ResearchReportRequest) -> dict[str, int | bool]:
    return _runtime_config_build_research_runtime(
        payload,
        resolve_research_mode=_resolve_research_mode,
        runtime_consumer_effective_config=_runtime_consumer_effective_config,
        safe_int=_safe_int,
    )


def _build_research_focus_terms(keyword: str, research_focus: str | None) -> list[str]:
    chips = [normalize_text(keyword)]
    extra = [
        token
        for token in _tokenize_for_match(research_focus or "")
        if token not in GENERIC_FOCUS_TOKENS and len(normalize_text(token)) >= 2
    ]
    for token in extra:
        normalized = normalize_text(token)
        if not normalized or normalized in chips:
            continue
        chips.append(normalized)
        if len(chips) >= 4:
            break
    if len(chips) == 1 and research_focus:
        chips.append(_truncate_text(re.sub(r"\s+", " / ", research_focus), 18))
    return chips[:4]


def _build_progress_message(stage_label: str, *, keyword: str, research_focus: str | None, mode: str) -> str:
    chips = _build_research_focus_terms(keyword, _sanitize_research_focus_text(research_focus))
    scope = " / ".join(item for item in chips if item)
    mode_label = "深度调研" if mode == "deep" else "极速调研"
    if scope:
        return f"{mode_label} · {scope} · {stage_label}"
    return f"{mode_label} · {stage_label}"


def _followup_diagnostics_dependencies() -> FollowupDiagnosticsDependencies:
    return FollowupDiagnosticsDependencies(
        truncate_text=_truncate_text,
        sanitize_research_focus_text=_sanitize_research_focus_text,
        looks_like_source_noise_segment=_looks_like_source_noise_segment,
        merge_scope_hints=_merge_scope_hints,
        dedupe_strings=_dedupe_strings,
        prune_industry_hints=_prune_industry_hints,
        infer_input_scope_hints=_infer_input_scope_hints,
        theme_labels_from_scope=_theme_labels_from_scope,
        clean_scope_entity_names=_clean_scope_entity_names,
        build_query_plan=_build_query_plan,
        extract_topic_anchor_terms=_extract_topic_anchor_terms,
        tokenize_for_match=_tokenize_for_match,
        generic_focus_tokens=GENERIC_FOCUS_TOKENS,
        org_pattern=ORG_PATTERN,
    )


def _build_followup_context(payload: ResearchReportRequest) -> ResearchFollowupContextOut:
    return _followup_diagnostics_build_context(payload, deps=_followup_diagnostics_dependencies())


def _build_followup_planning_focus(
    research_focus: str | None,
    *,
    followup_context: ResearchFollowupContextOut,
) -> str | None:
    return _followup_diagnostics_build_planning_focus(
        research_focus,
        followup_context=followup_context,
        deps=_followup_diagnostics_dependencies(),
    )


def _merge_scope_hints_with_followup_context(
    base: dict[str, object],
    followup: dict[str, object],
) -> dict[str, object]:
    return _followup_diagnostics_merge_scope_hints(
        base,
        followup,
        deps=_followup_diagnostics_dependencies(),
    )


def _build_followup_research_diagnostics(
    *,
    keyword: str,
    report_research_focus: str | None,
    followup_context: ResearchFollowupContextOut,
    include_wechat: bool,
    base_scope_hints: dict[str, object],
) -> tuple[dict[str, object], ResearchFollowupDiagnosticsOut]:
    return _followup_diagnostics_build_research(
        keyword=keyword,
        report_research_focus=report_research_focus,
        followup_context=followup_context,
        include_wechat=include_wechat,
        base_scope_hints=base_scope_hints,
        deps=_followup_diagnostics_dependencies(),
    )


def _render_followup_diagnostics_prompt_context(followup_diagnostics: ResearchFollowupDiagnosticsOut) -> str:
    return _followup_diagnostics_render_diagnostics_prompt(followup_diagnostics)


def _render_followup_prompt_context(followup_context: ResearchFollowupContextOut) -> str:
    return _followup_diagnostics_render_prompt(followup_context)


def _render_followup_section_focus_prompt_context(report: ResearchReportDocument) -> str:
    return _followup_diagnostics_render_section_focus_prompt(
        report,
        deps=_followup_diagnostics_dependencies(),
    )


def _research_archive_query_text(
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
) -> str:
    return _archive_context_query_text(
        keyword,
        research_focus,
        scope_hints,
        dedupe_strings=_dedupe_strings,
    )


def _build_archive_report_scope_hints(report: ResearchReportResponse) -> dict[str, object]:
    return _archive_loader_build_report_scope_hints(
        report,
        dedupe_strings=_dedupe_strings,
        prune_industry_hints=_prune_industry_hints,
        stored_report_concrete_targets=_stored_report_concrete_targets,
    )


def _build_archive_context_item(
    *,
    entry: KnowledgeEntry,
    match: Any,
    scope_hints: dict[str, object],
) -> dict[str, object] | None:
    return _archive_loader_build_context_item(
        entry=entry,
        match=match,
        scope_hints=scope_hints,
        truncate_text=_truncate_text,
        report_sources_to_source_documents=_report_sources_to_source_documents,
        merge_scope_hints=_merge_scope_hints,
        infer_input_scope_hints=_infer_input_scope_hints,
        build_archive_report_scope_hints=_build_archive_report_scope_hints,
        infer_scope_hints=_infer_scope_hints,
        assess_stored_report_rewrite_mode=_assess_stored_report_rewrite_mode,
        resolve_stored_report_target_support=_resolve_stored_report_target_support,
        theme_labels_from_scope=_theme_labels_from_scope,
        dedupe_strings=_dedupe_strings,
        sanitize_entity_row=_sanitize_entity_row,
        is_trustworthy_scope_client_name=_is_trustworthy_scope_client_name,
        resolved_report_readiness=_resolved_report_readiness,
    )


def _load_research_archive_context(
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
    limit: int,
) -> list[dict[str, object]]:
    return _archive_loader_load_context(
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
        limit=limit,
        session_factory=SessionLocal,
        research_archive_query_text=_research_archive_query_text,
        build_archive_context_item=_build_archive_context_item,
        retrieve_matches=retrieve_knowledge_entry_matches,
    )


def _merge_scope_hints_with_archive_context(
    scope_hints: dict[str, object],
    archive_context_items: list[dict[str, object]],
    *,
    keyword: str,
    research_focus: str | None,
) -> dict[str, object]:
    return _archive_context_merge_scope_hints(
        scope_hints,
        archive_context_items,
        keyword=keyword,
        research_focus=research_focus,
        dedupe_strings=_dedupe_strings,
        sanitize_report_field_rows=_sanitize_report_field_rows,
        is_actionable_budget_row=_is_actionable_budget_row,
        truncate_text=_truncate_text,
        strip_query_noise=_strip_query_noise,
        sanitize_research_focus_text=_sanitize_research_focus_text,
    )


def _render_archive_prompt_context(archive_context_items: list[dict[str, object]]) -> str:
    return _archive_context_render_prompt(archive_context_items)


def _build_partial_report_result(
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    research_mode: str,
    archive_context: str,
    followup_diagnostics: str,
    source_intelligence: dict[str, list[str]],
    scope_hints: dict[str, object],
    llm: object | None,
    llm_timeout_seconds: int,
) -> ResearchReportResult:
    return _generation_artifacts_build_partial_report_result(
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        research_mode=research_mode,
        archive_context=archive_context,
        followup_diagnostics=followup_diagnostics,
        source_intelligence=source_intelligence,
        scope_hints=scope_hints,
        llm=llm,
        llm_timeout_seconds=llm_timeout_seconds,
        render_industry_methodology_context=_render_industry_methodology_context,
        apply_topic_specific_overrides=_apply_topic_specific_overrides,
    )


def _build_partial_report_response(
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    research_mode: str,
    parsed: ResearchReportResult,
    query_plan: list[str],
    sources: list[SourceDocument],
    source_diagnostics: ResearchSourceDiagnosticsOut,
    entity_graph: ResearchEntityGraphOut,
) -> ResearchReportResponse:
    return _generation_artifacts_build_partial_report_response(
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        research_mode=research_mode,
        parsed=parsed,
        query_plan=query_plan,
        sources=sources,
        source_diagnostics=source_diagnostics,
        entity_graph=entity_graph,
        evidence_density_level=_evidence_density_level,
        source_quality_level=_source_quality_level,
        build_sections=_build_sections,
        source_documents_to_outputs=_to_research_source_outputs,
        enrich_report_for_delivery=_enrich_report_for_delivery,
    )


def _report_sources_to_source_documents(sources: list[ResearchSourceOut]) -> list[SourceDocument]:
    return _report_storage_sources_to_documents(sources)


def _stored_report_to_result(report: ResearchReportResponse) -> ResearchReportResult:
    return _report_storage_to_runtime_result(report)


def _is_trustworthy_scope_client_name(value: str, *, theme_labels: list[str] | None = None) -> bool:
    return _entity_policy_is_trustworthy_scope_client_name(
        value,
        theme_labels=theme_labels,
        looks_like_scope_prompt_noise=_looks_like_scope_prompt_noise,
    )


def _clean_scope_entity_names(
    values: Iterable[str],
    *,
    limit: int = 4,
    theme_labels: list[str] | None = None,
) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        normalized = normalize_text(str(value))
        if (
            not normalized
            or _looks_like_insufficient(normalized)
            or _looks_like_scope_prompt_noise(normalized)
            or _looks_like_source_artifact_text(normalized)
        ):
            continue
        candidate = _extract_rank_entity_name(normalized) or _fallback_entity_name_from_row(normalized)
        candidate = _strip_entity_leading_noise(candidate)
        if (
            not candidate
            or _looks_like_fragment_entity_name(candidate)
            or _contains_low_value_entity_token(candidate)
            or _looks_like_scope_prompt_noise(candidate)
            or _looks_like_placeholder_entity_name(candidate)
        ):
            continue
        if not _is_plausible_entity_name(candidate) and not _is_lightweight_entity_name(candidate):
            continue
        if not _is_trustworthy_scope_client_name(candidate, theme_labels=theme_labels):
            continue
        cleaned.append(candidate)
    return _dedupe_strings(cleaned, limit)


def _stored_report_rewrite_dependencies() -> StoredReportRewriteDependencies:
    return _runtime_stored_report_rewrite_dependencies(_build_report_runtime_owner_ports())


def _stored_report_concrete_targets(report: ResearchReportResponse) -> list[str]:
    return _stored_report_rewrite_concrete_targets(
        report,
        deps=_stored_report_rewrite_dependencies(),
    )


def _resolve_stored_report_target_support(
    report: ResearchReportResponse,
    *,
    source_documents: list[SourceDocument],
    scope_hints: dict[str, object],
) -> tuple[list[str], list[str], list[str]]:
    return _stored_report_rewrite_resolve_target_support(
        report,
        source_documents=source_documents,
        scope_hints=scope_hints,
        deps=_stored_report_rewrite_dependencies(),
    )


def _assess_stored_report_rewrite_mode(
    report: ResearchReportResponse,
    *,
    source_documents: list[SourceDocument],
    scope_hints: dict[str, object],
) -> tuple[str, list[str], dict[str, float]]:
    return _stored_report_rewrite_assess_mode(
        report,
        source_documents=source_documents,
        scope_hints=scope_hints,
        deps=_stored_report_rewrite_dependencies(),
    )


def _stored_report_rewrite_orchestration_dependencies() -> StoredReportRewriteOrchestrationDependencies:
    return _runtime_stored_report_rewrite_orchestration_dependencies(_build_report_runtime_owner_ports())


def rewrite_stored_research_report(report: ResearchReportResponse) -> ResearchReportResponse:
    return _stored_report_rewrite_rewrite_report(
        report,
        deps=_stored_report_rewrite_orchestration_dependencies(),
    )


def _generation_setup_dependencies() -> ResearchGenerationSetupDependencies:
    return ResearchGenerationSetupDependencies(
        get_settings=get_settings,
        get_llm_service=lambda: instrument_llm_service(
            get_llm_service(),
            role="generation",
        ),
        build_followup_context=_build_followup_context,
        infer_input_scope_hints=_infer_input_scope_hints,
        build_followup_research_diagnostics=_build_followup_research_diagnostics,
        build_followup_planning_focus=_build_followup_planning_focus,
        resolve_research_mode=_resolve_research_mode,
        build_research_runtime=_build_research_runtime,
        read_research_source_settings=read_research_source_settings,
        merge_scope_hints_with_followup_context=_merge_scope_hints_with_followup_context,
        merge_scope_hints=_merge_scope_hints,
        runtime_strategy_scope_hints=_runtime_strategy_scope_hints,
        apply_strategy_scope_planning=_apply_strategy_scope_planning,
        load_research_archive_context=_load_research_archive_context,
        render_archive_prompt_context=_render_archive_prompt_context,
        merge_scope_hints_with_archive_context=_merge_scope_hints_with_archive_context,
        curated_wechat_channels=CURATED_WECHAT_CHANNELS,
    )


def _generation_workflow_dependencies() -> ResearchGenerationWorkflowDependencies:
    return ResearchGenerationWorkflowDependencies(
        progress=ResearchWorkflowProgressPorts(
            emit_research_progress=_emit_research_progress,
            build_progress_message=_build_progress_message,
            emit_research_snapshot=_emit_research_snapshot,
        ),
        source_collection=ResearchWorkflowSourceCollectionPorts(
            build_query_plan=_build_query_plan,
            source_collection_collect_adapter_hits=_source_collection_collect_adapter_hits,
            collect_enabled_source_hits=collect_enabled_source_hits,
            source_collection_collect_public_search_hits=_source_collection_collect_public_search_hits,
            search_public_web=_search_public_web,
            dedupe_hits=_dedupe_hits,
            source_collection_extract_initial_sources=_source_collection_extract_initial_sources,
            hybrid_rank_hits=_hybrid_rank_hits,
            select_hits_with_source_balance=_select_hits_with_source_balance,
            extract_source_document=_extract_source_document,
            filter_recent_sources=_filter_recent_sources,
            refine_sources_for_report=_refine_sources_for_report,
            build_company_contact_query_plan=_build_company_contact_query_plan,
            build_company_profile_query_plan=_build_company_profile_query_plan,
            build_company_seed_hits=_build_company_seed_hits,
            build_company_team_query_plan=_build_company_team_query_plan,
            classify_source_tier=_classify_source_tier,
            classify_source_type=_classify_source_type,
            derive_source_label=_derive_source_label,
            extract_source_document_best_effort=_extract_source_document_best_effort,
            dedupe_sources=_dedupe_sources,
            build_source_intelligence=_build_source_intelligence,
            build_expanded_query_plan=_build_expanded_query_plan,
            build_corrective_query_plan=_build_corrective_query_plan,
            source_max_age_years=SOURCE_MAX_AGE_YEARS,
        ),
        scope=ResearchWorkflowScopePorts(
            dedupe_strings=_dedupe_strings,
            merge_scope_hints=_merge_scope_hints,
            infer_scope_hints=_infer_scope_hints,
            build_theme_terms=_build_theme_terms,
            extract_topic_anchor_terms=_extract_topic_anchor_terms,
            resolved_company_anchor_terms=_resolved_company_anchor_terms,
            region_conflict_signature=_region_conflict_signature,
            source_has_region_conflict=_source_has_region_conflict,
            collect_theme_seed_companies=_collect_theme_seed_companies,
            collect_matched_theme_labels=_collect_matched_theme_labels,
        ),
        enrichment=ResearchWorkflowEnrichmentPorts(
            company_source_enrichment_enrich=_company_source_enrichment_enrich,
            evidence_expansion_apply=_evidence_expansion_apply,
            corrective_expansion_apply=_corrective_expansion_apply,
            tender_detail_enrichment_apply=_tender_detail_enrichment_apply,
            tender_detail_dependencies=_tender_detail_dependencies,
            candidate_profile_enrichment_enrich=_candidate_profile_enrichment_enrich,
        ),
        generation=ResearchWorkflowGenerationPorts(
            generation_execution_execute=_generation_execution_execute,
            load_runtime_research_retrieval_index=_load_runtime_research_retrieval_index,
            attach_section_retrieval_packs=attach_section_retrieval_packs,
            render_section_retrieval_prompt_context=_render_section_retrieval_prompt_context,
            render_followup_section_focus_prompt_context=_render_followup_section_focus_prompt_context,
            build_partial_report_result=_build_partial_report_result,
            render_followup_diagnostics_prompt_context=_render_followup_diagnostics_prompt_context,
            build_partial_report_response=_build_partial_report_response,
            retrieval_orchestration_build_section_runtime_context=_retrieval_orchestration_build_section_runtime_context,
            render_source_digest=_render_source_digest,
            render_followup_prompt_context=_render_followup_prompt_context,
            render_retrieval_correction_context=render_retrieval_correction_context,
            render_industry_methodology_context=_render_industry_methodology_context,
            parse_research_report_response=parse_research_report_response,
            merge_result_with_intelligence=_merge_result_with_intelligence,
            apply_topic_specific_overrides=_apply_topic_specific_overrides,
            apply_strategy_llm_refinement=_apply_strategy_llm_refinement,
        ),
        ranking=ResearchWorkflowRankingPorts(
            build_entity_graph=_build_entity_graph,
            entity_ranking_rank_report_entities=_entity_ranking_rank_report_entities,
            rank_top_entities=_rank_top_entities,
            filtered_rank_fallback_values=_filtered_rank_fallback_values,
            entity_ranking_promote_with_profiles=_entity_ranking_promote_with_profiles,
            build_candidate_profile_support=_build_candidate_profile_support,
            promote_pending_entities_with_candidate_profiles=_promote_pending_entities_with_candidate_profiles,
            build_entity_specific_contact_rows=_build_entity_specific_contact_rows,
            build_entity_specific_team_rows=_build_entity_specific_team_rows,
        ),
        assembly=ResearchWorkflowAssemblyPorts(
            report_assembly_assemble_final_report=_report_assembly_assemble_final_report,
            build_sections=_build_sections,
            source_documents_to_outputs=_to_research_source_outputs,
            enrich_report_for_delivery=_enrich_report_for_delivery,
        ),
        quality=ResearchWorkflowQualityPorts(
            concrete_rows=_concrete_rows,
            company_convergence_is_weak=_company_convergence_is_weak,
            official_coverage_is_weak=_official_coverage_is_weak,
            retrieval_quality_band=_retrieval_quality_band,
            build_retrieval_correction_profile=build_retrieval_correction_profile,
            build_source_diagnostics=_build_source_diagnostics,
            evidence_density_level=_evidence_density_level,
            source_quality_level=_source_quality_level,
            review_generation_grounding=review_generation_grounding,
            evaluate_and_improve_research_report=evaluate_and_improve_research_report,
            expand_report_public_sources_until_quality_improves=_expand_report_public_sources_until_quality_improves,
        ),
    )


def build_research_workflow_engine(engine_name: str | None = None) -> ResearchWorkflowEngine:
    dependencies = DeterministicResearchWorkflowDependencies(
        prepare_setup=_generation_setup_prepare,
        setup_dependencies=_generation_setup_dependencies,
        run_workflow=_generation_workflow_run,
        workflow_dependencies=_generation_workflow_dependencies,
    )
    selected_engine = engine_name or get_settings().research_workflow_engine
    if selected_engine in {"langgraph", "langgraph_shadow"}:
        from app.services.research.langgraph_workflow_engine import LangGraphResearchWorkflowEngine

        return LangGraphResearchWorkflowEngine(dependencies)
    return DeterministicResearchWorkflowEngine(dependencies)


def execute_research_report_workflow(
    payload: ResearchReportRequest,
    *,
    progress_callback: ResearchProgressCallback | None = None,
    snapshot_callback: ResearchSnapshotCallback | None = None,
    metrics: ResearchRunMetrics | None = None,
    engine: ResearchWorkflowEngine | None = None,
) -> ResearchWorkflowExecution:
    workflow_engine = engine or build_research_workflow_engine()
    return workflow_engine.execute(
        payload,
        progress_callback=progress_callback,
        snapshot_callback=snapshot_callback,
        metrics=metrics,
    )


def generate_research_report(
    payload: ResearchReportRequest,
    *,
    progress_callback: ResearchProgressCallback | None = None,
    snapshot_callback: ResearchSnapshotCallback | None = None,
    metrics: ResearchRunMetrics | None = None,
) -> ResearchReportResponse:
    return execute_research_report_workflow(
        payload,
        progress_callback=progress_callback,
        snapshot_callback=snapshot_callback,
        metrics=metrics,
    ).report
