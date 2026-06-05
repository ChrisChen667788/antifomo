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
    ContentExtractionError,
    extract_domain,
    extract_from_reader_proxy,
    extract_from_url,
    normalize_text,
)
from app.services.knowledge_retrieval_service import (
    TextRetrievalCandidate,
    retrieve_knowledge_entry_matches,
    retrieve_text_matches,
)
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
from app.services.research.report_storage import (
    report_sources_to_source_documents as _storage_report_sources_to_source_documents,
    stored_report_section_aliases as _stored_report_section_aliases,
    stored_report_to_result as _storage_stored_report_to_result,
)
from app.services.research.runtime_config import (
    build_research_runtime as _runtime_config_build_research_runtime,
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
    tokenize_for_match as _scope_terms_tokenize_for_match,
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
from app.services.research.source_collection import (
    collect_adapter_hits as _source_collection_collect_adapter_hits,
    collect_public_search_hits as _source_collection_collect_public_search_hits,
    extract_initial_sources as _source_collection_extract_initial_sources,
)
from app.services.research.source_diagnostics import (
    SourceDiagnosticsDependencies,
    build_source_diagnostics as _source_diagnostics_build,
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
    SourceScopePolicyDependencies,
    filter_recent_sources as _source_scope_policy_filter_recent,
    filter_sources_by_theme_relevance as _source_scope_policy_filter_by_theme,
    refine_sources_for_report as _source_scope_policy_refine,
    region_conflict_signature as _source_scope_policy_region_conflict_signature,
    source_has_region_conflict as _source_scope_policy_has_region_conflict,
    source_scope_match_score as _source_scope_policy_scope_score,
    source_theme_match_score as _source_scope_policy_theme_score,
)
from app.services.research.strategy_refinement import (
    StrategyRefinementDependencies,
    apply_strategy_llm_refinement as _strategy_refinement_apply_llm,
    apply_strategy_scope_planning as _strategy_refinement_apply_scope,
    apply_topic_specific_overrides as _strategy_refinement_apply_topic_overrides,
)
from app.services.research.stored_entity_canonicalization import (
    StoredEntityCanonicalizationDependencies,
    canonicalize_stored_entity_name as _stored_entity_canonicalization_entity_name,
    canonicalize_stored_report_entities as _stored_entity_canonicalization_report_entities,
    canonicalize_stored_result_entities as _stored_entity_canonicalization_result_entities,
    clean_candidate_profile_company_names as _stored_entity_canonicalization_clean_candidate_names,
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


@dataclass(frozen=True, slots=True)
class IndustryMethodologyProfile:
    key: str
    authority_label: str
    framework: str
    primary_questions: tuple[str, ...]
    query_templates: tuple[str, ...]
    source_preferences: tuple[str, ...]
    solution_lenses: tuple[str, ...]
    sales_lenses: tuple[str, ...]
    bidding_lenses: tuple[str, ...]
    outreach_lenses: tuple[str, ...]
    ecosystem_lenses: tuple[str, ...]


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

INDUSTRY_SCOPE_ALIASES: dict[str, tuple[str, ...]] = {
    "政务云": ("政务云", "政务", "政府云", "政务大模型", "数据局", "智慧政务", "电子政务"),
    "大模型": ("大模型", "模型", "生成式AI", "AI", "人工智能", "算力", "MaaS"),
    "人工智能": ("人工智能", "AI", "智能", "大模型", "模型", "算力"),
    "AI漫剧": ("AI漫剧", "漫剧", "AI短剧", "AIGC短剧", "AIGC漫剧", "AI动画", "AIGC动画", "动漫短剧", "漫画短剧"),
    "数据中心": ("数据中心", "算力", "服务器", "机房", "存储", "智算中心"),
    "信息化": ("信息化", "数字化", "平台", "系统", "软件", "集成"),
    "智慧城市": ("智慧城市", "城市治理", "城市运行", "数字城市", "城市大脑"),
    "医疗": ("医疗", "医院", "卫健", "医共体", "医保"),
    "教育": ("教育", "学校", "高校", "职教", "教委"),
    "金融": ("金融", "银行", "证券", "保险", "资管"),
    "能源": ("能源", "电力", "电网", "光伏", "风电", "储能"),
}

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

THEME_GENERIC_SUPPRESSIONS: dict[str, tuple[str, ...]] = {
    "AI漫剧": ("大模型", "人工智能"),
}

THEME_STRICT_MUST_INCLUDE_TERMS: dict[str, tuple[str, ...]] = {
    "AI漫剧": ("ai漫剧", "漫剧", "ai短剧", "aigc短剧", "aigc漫剧", "ai动画", "aigc动画", "动漫短剧", "漫画短剧"),
}

THEME_ROLE_ARCHETYPES: dict[str, dict[str, tuple[str, ...]]] = {
    "AI漫剧": {
        "target": (
            "短剧内容平台运营方（待验证）",
            "动漫 IP 版权运营机构（待验证）",
            "文旅/教育数字内容运营主体（待验证）",
        ),
        "competitor": (
            "AIGC 短剧生成平台服务商（待验证）",
            "动漫内容工业化制作团队（待验证）",
            "AI 视频分镜与角色生成厂商（待验证）",
        ),
        "partner": (
            "动漫 IP 咨询与发行伙伴（待验证）",
            "区域内容集成与渠道分发伙伴（待验证）",
            "文旅/教育场景牵线伙伴（待验证）",
        ),
    },
    "政务云": {
        "target": (
            "省级数据局/政务服务管理局（待验证）",
            "地市级大数据中心或信息中心（待验证）",
            "政务云运营平台公司或城投平台（待验证）",
        ),
        "competitor": (
            "政务云总集厂商（待验证）",
            "政务一体化平台交付厂商（待验证）",
            "本地云资源与集成服务商（待验证）",
        ),
        "partner": (
            "区域总包与咨询伙伴（待验证）",
            "本地政务集成与运维伙伴（待验证）",
            "有政府关系的生态牵线方（待验证）",
        ),
    },
}

THEME_COMPANY_PUBLIC_SOURCE_SEEDS: dict[str, tuple[str, ...]] = {
    "AI漫剧": (
        "爱奇艺",
        "哔哩哔哩",
        "腾讯视频",
        "腾讯动漫",
        "优酷",
        "快手",
        "快看漫画",
        "抖音",
        "字节跳动",
        "阅文集团",
        "芒果超媒",
        "中文在线",
        "掌阅科技",
        "美图",
        "华策影视",
        "光线传媒",
        "上海儒意",
        "追光动画",
    ),
    "政务云": (
        "阿里云",
        "腾讯云",
        "华为",
        "中兴通讯",
        "神州数码",
        "新华三",
        "软通动力",
        "太极股份",
        "中国移动",
        "中国电信",
        "中国联通",
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

INDUSTRY_METHODOLOGY_PROFILES: dict[str, IndustryMethodologyProfile] = {
    "政务云": IndustryMethodologyProfile(
        key="政务云",
        authority_label="公共部门数字化项目调研框架",
        framework="政策牵引 -> 预算归口 -> 招采窗口 -> 建设期次 -> 运维绩效",
        primary_questions=(
            "当前牵头部门、预算归口部门和招采执行部门分别是谁",
            "项目处于立项、试点、一期建设还是二三期扩容",
            "是否已有可研、预算草案、采购意向或中标续建信号",
            "云资源、平台总包、集成运维和安全厂商分别由谁承担",
        ),
        query_templates=(
            "{region} {industry} 财政预算 采购意向 可研 批复",
            "\"{client}\" {keyword} 预算 立项 可研 采购意向",
            "{region} {industry} 一体化平台 续建 扩容 运维",
        ),
        source_preferences=("gov.cn", "ccgp.gov.cn", "ggzy.gov.cn", "数据局/政务服务局官网", "财政预算公开"),
        solution_lenses=("顶层架构统建", "试点到统建分期", "云网安一体化", "运维与绩效闭环"),
        sales_lenses=("牵头部门切入", "预算归口核验", "年度规划节点", "续建扩容窗口"),
        bidding_lenses=("采购意向前置布局", "总包与分包角色", "资质与案例匹配", "续建项目壁垒"),
        outreach_lenses=("数据局/信息中心优先", "财政与招采并行摸排", "总包伙伴联动"),
        ecosystem_lenses=("本地集成商", "云资源伙伴", "咨询可研单位", "运维服务商"),
    ),
    "医疗": IndustryMethodologyProfile(
        key="医疗",
        authority_label="临床价值与医院信息化调研框架",
        framework="临床场景 -> 信息科与医务线 -> 合规安全 -> 系统集成 -> 投入产出",
        primary_questions=(
            "需求来自临床、医务、运营还是科研教学场景",
            "信息科、医务处、设备处、财务处和采购办的分工如何",
            "是否涉及电子病历、互联互通、医保支付、数据安全等约束",
            "试点科室、医院集团复制和区域医共体扩展节奏如何",
        ),
        query_templates=(
            "{region} 医院 {keyword} 信息化 建设 采购 预算",
            "{region} 卫健 {keyword} 试点 示范 预算",
            "\"{client}\" {keyword} 信息科 医务处 招标",
        ),
        source_preferences=("医院官网", "卫健委官网", "招采公告", "试点示范名单", "医院年报/新闻"),
        solution_lenses=("临床价值闭环", "科室试点复制", "HIS/PACS/EMR 集成", "合规与数据安全"),
        sales_lenses=("信息科与医务双线推进", "示范科室案例", "ROI 与效率提升", "院级预算窗口"),
        bidding_lenses=("设备/软件采购口径", "集成改造复杂度", "资质合规", "医院集团复制能力"),
        outreach_lenses=("信息科 -> 医务处 -> 业务科室 -> 财务采购", "专家共识与标杆医院材料"),
        ecosystem_lenses=("区域总代", "医疗集成商", "科研教学伙伴", "数据安全伙伴"),
    ),
    "金融": IndustryMethodologyProfile(
        key="金融",
        authority_label="金融科技与监管约束调研框架",
        framework="监管约束 -> 场景优先级 -> 数据治理 -> 风控审计 -> ROI 与复制性",
        primary_questions=(
            "需求落在营销、风控、运营、投研还是客服场景",
            "监管合规、模型可解释、审计留痕和数据边界要求是什么",
            "总行、分行、科技子公司和业务条线的决策链如何分布",
            "试点是否能复制到更多分支机构或条线",
        ),
        query_templates=(
            "{region} 银行 {keyword} 科技 招标 采购",
            "{region} 证券 保险 {keyword} 数据治理 风控 预算",
            "\"{client}\" {keyword} 科技部 数字化 招标",
        ),
        source_preferences=("银行/保险/证券官网", "监管公告", "招采公告", "年报与业绩会", "科技子公司新闻"),
        solution_lenses=("监管合规", "数据治理", "风控审计", "场景复制"),
        sales_lenses=("科技条线切入", "业务条线共创", "监管合规证明", "总分行复制"),
        bidding_lenses=("资质安全要求", "POC 与试点", "总包合作", "审计留痕"),
        outreach_lenses=("科技部/数字化部先行", "业务部门共识", "监管与审计口径同步"),
        ecosystem_lenses=("咨询与总包", "安全厂商", "数据治理伙伴", "本地交付团队"),
    ),
    "教育": IndustryMethodologyProfile(
        key="教育",
        authority_label="教育数字化项目调研框架",
        framework="教学科研场景 -> 教委/信息中心 -> 预算批次 -> 试点扩面 -> 安全与绩效",
        primary_questions=(
            "场景属于课堂教学、科研平台、校园治理还是职教实训",
            "教委、学校信息中心、教务处和资产采购部门的分工如何",
            "是否有试点校、示范校、专项资金或年度采购批次",
            "项目是单校部署还是区域复制/集团统建",
        ),
        query_templates=(
            "{region} 教委 {keyword} 预算 试点 示范",
            "{region} 高校 学校 {keyword} 招标 采购 信息化",
            "\"{client}\" {keyword} 信息中心 教务处 采购",
        ),
        source_preferences=("教委官网", "学校官网", "招采公告", "试点示范名单", "专项资金文件"),
        solution_lenses=("教学场景闭环", "试点校复制", "教务与科研平台集成", "校园数据安全"),
        sales_lenses=("教委/学校双线", "示范校案例", "年度预算批次", "集团化复制"),
        bidding_lenses=("专项资金口径", "校园网与平台集成", "安全等保", "实施交付保障"),
        outreach_lenses=("信息中心 -> 教务处 -> 学院/职能部门", "试点校样板材料"),
        ecosystem_lenses=("本地教育集成商", "内容与平台伙伴", "科研合作单位", "安全运维伙伴"),
    ),
    "AI漫剧": IndustryMethodologyProfile(
        key="AI漫剧",
        authority_label="内容产业与 IP 商业化调研框架",
        framework="IP 供给 -> 制作工具链 -> 分发平台 -> 商业化路径 -> 版权合规",
        primary_questions=(
            "核心机会在 IP、平台分发、内容生产还是商业化变现",
            "平台方、版权方、制作工作室和发行渠道分别是谁",
            "当前信号来自立项合作、内容招商、生态伙伴还是投资布局",
            "未来机会是试水项目还是平台级长期内容供给",
        ),
        query_templates=(
            "{keyword} IP 合作 分发 平台 商业化",
            "{keyword} 版权 发行 工作室 生态 预算",
            "\"{client}\" AIGC 动画 短剧 合作 平台",
        ),
        source_preferences=("平台/内容公司官网", "IR/年报", "行业媒体", "公众号深度稿", "版权与合作公告"),
        solution_lenses=("IP 供给链路", "制作工具链", "平台分发接口", "版权与变现"),
        sales_lenses=("平台运营/内容生态切入", "先谈合作形态再谈产品", "以内容供给与效率证明价值"),
        bidding_lenses=("合作招商口径", "版权与交付边界", "联合方案伙伴", "平台准入条件"),
        outreach_lenses=("平台运营 -> 内容生态 -> 商务合作 -> 工作室", "案例以内容效率和变现为核心"),
        ecosystem_lenses=("IP 版权方", "发行渠道", "动画工作室", "内容技术伙伴"),
    ),
    "数据中心": IndustryMethodologyProfile(
        key="数据中心",
        authority_label="算力与基础设施投资调研框架",
        framework="项目批复 -> 机电土建 -> 算力设备 -> 运维能耗 -> 二三期扩容",
        primary_questions=(
            "项目处于规划、批复、一期建设还是扩容阶段",
            "预算大头落在土建机电、服务器存储还是运营服务",
            "牵头主体是国资平台、运营商还是产业园区",
            "二三期扩容和能源约束是否已经出现公开信号",
        ),
        query_templates=(
            "{region} {keyword} 可研 批复 能耗 指标",
            "{region} 智算中心 数据中心 {keyword} 招标 中标",
            "\"{client}\" {keyword} 扩容 二期 三期",
        ),
        source_preferences=("发改/工信官网", "园区与国资平台官网", "招采公告", "能耗与批复文件", "运营商官网"),
        solution_lenses=("基础设施分层", "算力与存储组合", "运维监控", "扩容节奏"),
        sales_lenses=("牵头主体摸排", "批复与能耗指标", "一期到扩容延续", "总包合作"),
        bidding_lenses=("土建机电/设备分包", "能耗与资质", "交付周期", "运维 SLA"),
        outreach_lenses=("发改/园区/国资平台先行", "总包与运营商联动"),
        ecosystem_lenses=("机电总包", "服务器存储厂商", "运营商", "运维服务商"),
    ),
    "大模型": IndustryMethodologyProfile(
        key="大模型",
        authority_label="AI 场景落地与投资验证框架",
        framework="场景优先级 -> 数据可得性 -> 模型与算力 -> 集成改造 -> ROI 与复制",
        primary_questions=(
            "是政企、医疗、金融、教育还是内容生产场景在驱动需求",
            "数据、算力、模型部署和安全合规约束分别是什么",
            "预算更偏平台建设、试点验证还是行业复制扩容",
            "需要总包、ISV、模型厂商还是本地交付伙伴共同推进",
        ),
        query_templates=(
            "{region} {keyword} 试点 示范 预算 采购",
            "{region} 大模型 {keyword} 招标 中标 项目",
            "\"{client}\" {keyword} 数据 安全 预算 采购",
        ),
        source_preferences=("gov.cn/招采网", "行业主管部门官网", "客户官网", "模型厂商官网", "公开案例与年报"),
        solution_lenses=("场景优先级", "数据与合规", "模型部署架构", "复制扩容"),
        sales_lenses=("业务场景负责人", "预算归口", "试点 ROI", "复制节奏"),
        bidding_lenses=("数据与安全要求", "模型/算力边界", "总包协同", "案例资质"),
        outreach_lenses=("业务部门 -> 信息化/科技部门 -> 预算与采购", "试点样板先行"),
        ecosystem_lenses=("模型厂商", "算力伙伴", "ISV", "本地交付伙伴"),
    ),
}

THEME_ENTITY_ALLOW_TOKENS: dict[str, dict[str, tuple[str, ...]]] = {
    "AI漫剧": {
        "target": ("视频", "动漫", "漫画", "影业", "传媒", "内容", "动画", "平台", "IP", "短剧", "文旅", "教育", "发行"),
        "competitor": ("视频", "动漫", "漫画", "影业", "传媒", "内容", "动画", "平台", "IP", "短剧", "AIGC", "AI", "生成"),
        "partner": ("咨询", "顾问", "发行", "渠道", "版权", "IP", "运营", "集成", "联盟", "文旅", "教育", "生态"),
    },
}

THEME_ENTITY_BLOCK_TOKENS: dict[str, dict[str, tuple[str, ...]]] = {
    "AI漫剧": {
        "target": ("政府", "市委", "市政府", "局", "委", "办", "中心", "大学", "学院", "学校", "医院", "银行", "证券"),
        "competitor": ("政府", "市委", "局", "委", "办", "中心", "大学", "学院", "学校", "医院", "银行", "证券"),
        "partner": ("政府", "市委", "局", "委", "办", "中心", "大学", "学院", "学校", "医院", "银行", "证券"),
    },
}


GENERIC_FOCUS_TOKENS = {
    "预算", "招标", "采购", "中标", "甲方", "竞品", "生态伙伴", "生态", "伙伴", "领导讲话",
    "领导", "讲话", "项目", "商机", "区域", "行业", "客户", "公司", "同行", "战略", "规划",
}

GENERIC_COMPANY_ANCHOR_TOKENS = {
    "ai", "aigc", "大模型", "模型", "人工智能", "短剧", "漫剧", "动画", "内容", "平台",
    "方案", "商机", "调研", "研究", "研报", "采购", "招标", "预算", "项目", "行业", "客户",
    "生态", "伙伴", "竞品", "机会", "线索",
}

COMPANY_ENTITY_QUERY_TOKENS = (
    "公司", "企业", "厂商", "平台方", "平台", "工作室", "发行方", "版权方", "内容方", "甲方公司",
    "公司名单", "企业名单", "头部玩家", "company", "companies", "player", "players", "studio",
)

HEAD_COMPANY_QUERY_TOKENS = (
    "头部", "龙头", "领先", "头部玩家", "top", "leading", "leader", "leaders", "头部公司",
)

GENERIC_COMPANY_NAME_TOKENS = (
    "集团", "公司", "有限公司", "股份有限公司", "科技", "智能", "信息", "传媒", "影业", "视频",
    "动漫", "漫画", "平台", "工作室", "网络", "数据", "云", "软件", "娱乐", "文化",
)

INVALID_COMPANY_ANCHOR_PHRASES = (
    "优先给具体公司",
    "官方业务联系方式",
    "公开渠道联络人信息",
    "公开业务联系方式",
    "公开联络人信息",
    "联系方式",
    "联络人信息",
    "聚焦内容平台",
    "聚焦动漫ip",
    "即使暂时没有明确公司",
)

SCOPE_PROMPT_NOISE_PREFIXES = (
    "我作为",
    "我想",
    "我们想",
    "我们要",
    "帮我",
    "请帮",
    "请把",
    "作为",
    "该在",
    "想在",
    "预计",
    "它将",
    "是依托",
    "不仅",
)

SCOPE_PROMPT_NOISE_TOKENS = (
    "我们公司",
    "找客户",
    "找项目",
    "决策权",
    "预算规模",
    "哪些重点公司",
    "这些客户",
    "一并调研",
    "把竞品公司",
    "竞品公司情况",
    "竟品公司",
    "包括但不限于",
    "精确到决策单位",
    "精确到决策部门",
    "已经有了哪些标杆案例",
    "可扩展的计算服务",
    "大型国际银行",
    "全球银行",
    "全球服务中心",
)

GENERIC_SCOPE_CLIENT_TOKENS = (
    "头部公司",
    "重点公司",
    "行业竞品公司",
    "甲方公司",
    "一家公司",
    "一人公司",
)

SCOPE_PROMPT_NOISE_REGEXES = (
    r"\b(?:maas|iaas|paas|saas|agent)\b.*公司",
    r"哪些[^。；;\n]{0,24}(?:公司|客户|部门|领导)",
    r"(?:预算|金额|规模)[^。；;\n]{0,16}如何",
)

QUERY_NOISE_SUFFIXES = (
    "相关商机",
    "商机",
    "机会",
    "线索",
    "情报",
    "调研",
    "研究",
    "研报",
    "专题",
    "分析",
    "建议",
    "方案",
    "报告",
)

PROCUREMENT_DOMAINS = {
    "ccgp.gov.cn",
    "www.ccgp.gov.cn",
    "ggzy.gov.cn",
    "www.ggzy.gov.cn",
    "chinabidding.com",
    "www.chinabidding.com",
}

GENERIC_CONTENT_DOMAINS = {
    "zhuanlan.zhihu.com",
    "www.zhihu.com",
    "www.bilibili.com",
    "segmentfault.com",
    "www.cnblogs.com",
    "news.qq.com",
    "mp.weixin.qq.com",
}

POLICY_DOMAINS = {
    "gov.cn",
    "www.gov.cn",
}

EXCHANGE_DOMAINS = {
    "cninfo.com.cn",
    "www.cninfo.com.cn",
    "hkexnews.hk",
    "www.hkexnews.hk",
    "sec.gov",
    "www.sec.gov",
}

REGION_TOKENS = (
    "北京", "上海", "广州", "深圳", "杭州", "南京", "苏州", "成都", "重庆", "武汉", "西安",
    "天津", "青岛", "郑州", "长沙", "合肥", "福州", "厦门", "宁波", "无锡", "济南", "沈阳",
    "大连", "哈尔滨", "长春", "昆明", "南宁", "南昌", "石家庄", "太原", "贵阳", "兰州",
    "乌鲁木齐", "呼和浩特", "海南", "河北", "河南", "山东", "山西", "陕西", "江苏", "浙江",
    "安徽", "福建", "江西", "湖北", "湖南", "广东", "广西", "云南", "贵州", "四川", "重庆",
    "甘肃", "青海", "宁夏", "新疆", "西藏", "内蒙古", "辽宁", "吉林", "黑龙江",
)

REGION_SCOPE_ALIASES: dict[str, tuple[str, ...]] = {
    "长三角": ("长三角", "上海", "江苏", "浙江", "安徽", "南京", "苏州", "杭州", "宁波", "无锡", "合肥"),
    "京津冀": ("京津冀", "北京", "天津", "河北"),
    "粤港澳": ("粤港澳", "广东", "广州", "深圳", "珠海", "佛山", "东莞", "中山", "香港", "澳门"),
    "成渝": ("成渝", "成都", "重庆", "四川"),
}

ORG_PATTERN = re.compile(
    r"([A-Za-z0-9\u4e00-\u9fa5·（）()]{2,40}"
    r"(?:集团|公司|有限公司|股份有限公司|研究院|研究所|大学|医院|银行|政府|厅|局|委|办|中心|学院|学校|科技|智能|信息|控股|实验室))"
)

COMPACT_ENTITY_PATTERN = re.compile(
    r"([A-Za-z0-9\u4e00-\u9fa5·]{2,24}(?:数码|软件|信息|科技|咨询|顾问|股份|集团|服务|运营|网络|系统|通信|集成|研究院|协会|联盟))"
)

SPECIAL_ENTITY_ALIASES = (
    "德勤", "普华永道", "毕马威", "安永", "埃森哲", "IBM",
    "Microsoft", "OpenAI",
    "阿里云", "腾讯云", "华为", "中兴通讯", "神州数码", "新华三",
    "太极股份", "东软集团", "浪潮软件", "软通动力", "中电金信",
    "中国移动", "中国电信", "中国联通", "用友网络", "金蝶",
)

PARTNER_CONNECTOR_ALIASES = (
    "德勤", "普华永道", "毕马威", "安永", "埃森哲",
    "神州数码", "新华三", "软通动力", "中电金信",
    "中国移动", "中国电信", "中国联通", "太极股份",
)

KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS: dict[str, tuple[tuple[str, str], ...]] = {
    "爱奇艺": (
        ("https://www.iqiyi.com/", "爱奇艺官网"),
        ("https://ir.iqiyi.com/", "爱奇艺投资者关系"),
    ),
    "快手": (
        ("https://www.kuaishou.com/", "快手官网"),
        ("https://ir.kuaishou.com/", "快手投资者关系"),
    ),
    "抖音": (
        ("https://www.douyin.com/", "抖音官网"),
        ("https://www.bytedance.com/zh/", "字节跳动官网"),
    ),
    "字节跳动": (
        ("https://www.bytedance.com/zh/", "字节跳动官网"),
        ("https://www.bytedance.com/zh/contact", "字节跳动联系我们"),
    ),
    "阿里云": (
        ("https://www.aliyun.com/", "阿里云官网"),
        ("https://www.alibabagroup.com/cn/global/home", "阿里巴巴集团官网"),
    ),
    "优酷": (
        ("https://www.youku.com/", "优酷官网"),
        ("https://www.alibabagroup.com/cn/global/home", "阿里巴巴集团官网"),
    ),
    "腾讯云": (
        ("https://cloud.tencent.com/", "腾讯云官网"),
        ("https://www.tencent.com/zh-cn/", "腾讯官网"),
    ),
    "腾讯视频": (
        ("https://v.qq.com/", "腾讯视频官网"),
        ("https://www.tencent.com/zh-cn/", "腾讯官网"),
    ),
    "腾讯动漫": (
        ("https://ac.qq.com/", "腾讯动漫官网"),
        ("https://www.tencent.com/zh-cn/", "腾讯官网"),
    ),
    "华为": (
        ("https://www.huawei.com/cn/", "华为官网"),
        ("https://www.huawei.com/cn/contact-us", "华为联系我们"),
    ),
    "哔哩哔哩": (
        ("https://www.bilibili.com/", "哔哩哔哩官网"),
        ("https://ir.bilibili.com/", "哔哩哔哩投资者关系"),
    ),
    "快看漫画": (
        ("https://www.kuaikanmanhua.com/", "快看漫画官网"),
        ("https://www.kuaikanmanhua.com/about", "快看漫画公开入口"),
    ),
    "阅文集团": (
        ("https://www.yuewen.com/", "阅文集团官网"),
        ("https://ir.yuewen.com/", "阅文集团投资者关系"),
    ),
    "芒果超媒": (
        ("https://www.mgtv.com/", "芒果TV官网"),
        ("https://www.mangomedia.com.cn/", "芒果超媒官网"),
    ),
    "小红书": (
        ("https://www.xiaohongshu.com/", "小红书官网"),
        ("https://www.xiaohongshu.com/explore", "小红书公开入口"),
    ),
    "美图": (
        ("https://www.meitu.com/", "美图官网"),
        ("https://ir.meitu.com/", "美图投资者关系"),
    ),
    "中文在线": (
        ("https://www.col.com/", "中文在线官网"),
        ("https://www.col.com/About/contact", "中文在线联系我们"),
    ),
    "掌阅科技": (
        ("https://www.zhangyue.com/", "掌阅官网"),
        ("https://www.zhangyue.com/about", "掌阅公开入口"),
    ),
    "华策影视": (
        ("https://www.huacemedia.com/", "华策影视官网"),
        ("https://www.huacemedia.com/contact", "华策影视联系我们"),
    ),
    "光线传媒": (
        ("https://www.ewang.com/", "光线传媒官网"),
        ("https://www.ewang.com/about", "光线传媒公开入口"),
    ),
    "上海儒意": (
        ("https://www.ruyi.cn/", "儒意官网"),
        ("https://www.ruyi.cn/contact", "儒意联系我们"),
    ),
    "追光动画": (
        ("https://www.zhuiguang.com/", "追光动画官网"),
        ("https://www.zhuiguang.com/about", "追光动画公开入口"),
    ),
    "中兴通讯": (
        ("https://www.zte.com.cn/china/", "中兴通讯官网"),
        ("https://www.zte.com.cn/china/about/contact", "中兴通讯联系我们"),
    ),
    "中国移动": (
        ("https://www.10086.cn/", "中国移动官网"),
        ("https://ir.chinamobile.com/", "中国移动投资者关系"),
    ),
    "中国电信": (
        ("https://www.189.cn/", "中国电信官网"),
        ("https://www.chinatelecom-h.com/", "中国电信投资者关系"),
    ),
    "中国联通": (
        ("https://www.10010.com/", "中国联通官网"),
        ("https://www.chinaunicom.com.hk/", "中国联通投资者关系"),
    ),
    "神州数码": (
        ("https://www.digitalchina.com/", "神州数码官网"),
        ("https://www.digitalchina.com/Contact/index.html", "神州数码联系我们"),
    ),
    "新华三": (
        ("https://www.h3c.com/cn/", "新华三官网"),
        ("https://www.h3c.com/cn/About_H3C/Contact_Us/", "新华三联系我们"),
    ),
    "软通动力": (
        ("https://www.isoftstone.com/", "软通动力官网"),
        ("https://www.isoftstone.com/contact", "软通动力联系我们"),
    ),
    "太极股份": (
        ("https://www.taiji.com.cn/", "太极股份官网"),
        ("https://www.taiji.com.cn/col/col25/index.html", "太极股份联系我们"),
    ),
    "德勤": (
        ("https://www2.deloitte.com/cn/zh.html", "德勤官网"),
        ("https://www2.deloitte.com/cn/zh/pages/about-deloitte/articles/contact-us.html", "德勤联系我们"),
    ),
    "埃森哲": (
        ("https://www.accenture.com/cn-zh", "埃森哲官网"),
        ("https://www.accenture.com/cn-zh/about/contact-us", "埃森哲联系我们"),
    ),
}

KNOWN_LIGHTWEIGHT_ENTITY_NAMES = {
    *SPECIAL_ENTITY_ALIASES,
    *KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS.keys(),
}

_RESEARCH_ACCOUNT_ALIAS_MAP = {
    "微软": "Microsoft",
    "Open AI": "OpenAI",
    "上海市文旅局": "上海市文化和旅游局",
    "华为云服务": "华为云",
    "阿里巴巴云": "阿里云",
    "腾讯视频": "腾讯",
    "腾讯动漫": "腾讯",
}

_OFFICIAL_DOMAIN_ENTITY_MAP: dict[str, str] = {}
for _canonical_name, _seed_sources in KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS.items():
    for _seed_url, _seed_label in _seed_sources:
        _seed_domain = normalize_text(extract_domain(_seed_url) or "").lower().removeprefix("www.")
        if _seed_domain:
            _OFFICIAL_DOMAIN_ENTITY_MAP.setdefault(_seed_domain, _canonical_name)

ENTITY_BLACKLIST_TOKENS = (
    "发布", "推进", "围绕", "布局", "显示", "启动", "持续", "建设", "合作", "联合", "方案",
    "项目", "预算", "政务云", "咨询与集成", "联合交付", "公开线索", "项目建设",
)

ENTITY_INVALID_PHRASE_TOKENS = (
    "怎么办", "如何", "制作", "利用", "是指", "一种", "相关商机", "相关讯息", "教程", "指南",
    "步骤", "案例拆解", "经验", "相关", "方向", "赛道", "行业", "领域", "信息", "新闻",
    "建议追加", "如果短期", "当前关键词范围", "公开线索", "优先给具体公司",
    "官方业务联系方式", "公开渠道联络人信息", "公开业务联系方式",
    "美国证券交易委", "证券交易委", "已向美国证券交易委", "公有云服务", "基础设施即服务", "模型即服务",
    "新协议", "保留了", "两家公司", "几家公司", "多家公司", "现在可以", "可以通过", "任何云服务",
    "不用再", "不再给", "宣布修订", "长期合作", "绑定关系", "合作协议", "基本框架",
    "各有关", "并经",
)

LOW_VALUE_ENTITY_NAME_TOKENS = (
    "会员中心", "入局", "掘金赛道", "保姆级", "最新版", "工作流", "完全指南", "怎么个事",
    "所有人都", "关于加强", "促进政府", "已成为", "改变系统", "支撑软件", "应用系统", "弹性服务",
    "模型服务", "公有云服务", "基础设施即服务", "模型即服务", "主力与协办", "标签服务", "用户画像服务",
    "英寸", "毫米硅片", "逻辑制程", "CIS集成",
)

ENTITY_FRAGMENT_PREFIX_TOKENS = (
    "此次", "由于", "相应", "相关", "本次", "该", "该类", "这个", "这类", "基于", "围绕", "通过",
    "针对", "聚焦", "正在", "已经", "主要", "因为", "如果", "对于", "已向", "即使",
    "现在", "过去", "未来", "同时", "但", "而是", "新协议", "双方",
    "各有关", "并经",
)

ENTITY_FRAGMENT_INFIX_TOKENS = (
    "主要基于", "相应调整", "调整系统", "相应系统", "由于公司", "基于公司", "围绕公司", "赋能",
    "服务于", "用于", "模式", "路径", "打法", "策略", "方法", "场景", "机会", "商机",
    "保留了", "可以通过", "任何云服务", "不用再", "不再给", "宣布修订", "长期合作",
    "绑定关系", "合作协议", "基本框架",
    "先进逻辑制程", "全自动智能",
    "各有关", "并经",
)

ENTITY_SUFFIX_TOKENS = (
    "集团", "公司", "有限公司", "股份有限公司", "研究院", "研究所", "大学", "医院", "银行", "政府",
    "厅", "局", "委", "办", "中心", "学院", "学校", "科技", "信息", "控股", "实验室",
    "协会", "联盟", "咨询", "顾问", "集成", "服务", "运营", "系统", "通信", "半导体",
)

PERSON_ROLE_PATTERN = re.compile(
    r"([\u4e00-\u9fa5]{2,4})(?:同志)?(?:在[^。；;\n]{0,12})?"
    r"(?:表示|指出|强调|要求|担任|出席|主持|提到|介绍)?"
    r"[^。；;\n]{0,18}?"
    r"(书记|市长|局长|厅长|主任|董事长|总经理|总裁|副总裁|院长|校长|负责人)"
)

DEPARTMENT_PATTERN = re.compile(
    r"([A-Za-z0-9\u4e00-\u9fa5·（）()]{2,40}"
    r"(?:采购部|采购中心|招标办|招采中心|集采中心|信息中心|信息化部|数字化部|科技部|战略发展部|数据局|数据资源局|办公室|财务部|计划财务部|运营部|网络安全部|政务服务中心|行政审批局|事业发展部|建设管理部|投资管理部))"
)

EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:\+?86[- ]?)?(?:1[3-9]\d{9}|0\d{2,3}[- ]?\d{7,8})(?!\d)"
)

MONEY_PATTERN = re.compile(
    r"(?:预算|投资|金额|规模|采购金额|中标金额|合同金额|总投资|资金|经费|财政投入|项目投资)"
    r"[^。；;\n]{0,28}?"
    r"(\d+(?:\.\d+)?(?:亿|万|千)?元|\d+(?:\.\d+)?\s?(?:million|billion|mn|bn)\s?(?:usd|dollars?)?)",
    re.IGNORECASE,
)

SOURCE_DATE_PATTERN = re.compile(
    r"(?P<year>20\d{2}|19\d{2})"
    r"(?:[\-/年\.](?P<month>0?[1-9]|1[0-2]))?"
    r"(?:[\-/月\.](?P<day>0?[1-9]|[12]\d|3[01]))?"
    r"(?:日)?"
)

SOURCE_MAX_AGE_YEARS = 7


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
    return ScopeTermDependencies(
        dedupe_strings=_dedupe_strings,
        is_plausible_entity_name=_is_plausible_entity_name,
        is_lightweight_entity_name=_is_lightweight_entity_name,
        looks_like_fragment_entity_name=_looks_like_fragment_entity_name,
        contains_low_value_entity_token=_contains_low_value_entity_token,
        org_pattern=ORG_PATTERN,
        compact_entity_pattern=COMPACT_ENTITY_PATTERN,
        query_noise_suffixes=QUERY_NOISE_SUFFIXES,
        scope_prompt_noise_prefixes=SCOPE_PROMPT_NOISE_PREFIXES,
        scope_prompt_noise_tokens=SCOPE_PROMPT_NOISE_TOKENS,
        scope_prompt_noise_regexes=SCOPE_PROMPT_NOISE_REGEXES,
        entity_suffix_tokens=ENTITY_SUFFIX_TOKENS,
        generic_focus_tokens=GENERIC_FOCUS_TOKENS,
        invalid_company_anchor_phrases=INVALID_COMPANY_ANCHOR_PHRASES,
        industry_scope_aliases=INDUSTRY_SCOPE_ALIASES,
        theme_generic_suppressions=THEME_GENERIC_SUPPRESSIONS,
        special_entity_aliases=SPECIAL_ENTITY_ALIASES,
        generic_company_anchor_tokens=GENERIC_COMPANY_ANCHOR_TOKENS,
        known_lightweight_entity_names=KNOWN_LIGHTWEIGHT_ENTITY_NAMES,
    )


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
    if isinstance(source, SearchHit):
        return str(getattr(source, "search_query", "") or "")
    return ""


def _source_matches_company_anchor(source: SearchHit | SourceDocument, company_anchor_terms: list[str]) -> bool:
    if not company_anchor_terms:
        return True
    haystack = normalize_text(
        " ".join(
            [
                str(getattr(source, "title", "") or ""),
                str(getattr(source, "snippet", "") or ""),
                str(getattr(source, "excerpt", "") or ""),
                _search_query_text_for_matching(source),
                str(getattr(source, "source_label", "") or ""),
                str(getattr(source, "url", "") or ""),
                str(getattr(source, "domain", "") or ""),
            ]
        )
    ).lower()
    return any(normalize_text(term).lower() in haystack for term in company_anchor_terms if normalize_text(term))


def _semantic_score_hit(
    hit: SearchHit,
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object] | None = None,
) -> tuple[int, SearchHit]:
    scope = scope_hints or {}
    haystack = normalize_text(
        " ".join(
            [
                hit.title,
                hit.snippet,
                hit.search_query,
                hit.source_label or "",
                hit.url,
                extract_domain(hit.url) or "",
            ]
        )
    ).lower()
    title_haystack = normalize_text(hit.title).lower()
    domain = (extract_domain(hit.url) or "").lower()
    topic_anchor_terms = [normalize_text(item).lower() for item in _extract_topic_anchor_terms(keyword, research_focus) if normalize_text(item)]
    company_anchor_terms = [
        normalize_text(item).lower()
        for item in _resolved_company_anchor_terms(keyword, research_focus, scope)
        if normalize_text(item)
    ]
    theme_terms = [normalize_text(item).lower() for item in _build_theme_terms(keyword, research_focus, scope) if normalize_text(item)]
    scope_regions = [
        normalize_text(item).lower()
        for item in _expand_region_scope_terms(
            [normalize_text(str(item)) for item in scope.get("regions", []) or [] if normalize_text(str(item))]
        )
    ]
    scope_industries = [
        normalize_text(item).lower()
        for item in [
            *[normalize_text(str(item)) for item in scope.get("industries", []) or [] if normalize_text(str(item))],
            *[
                normalize_text(alias)
                for industry in scope.get("industries", []) or []
                for alias in INDUSTRY_SCOPE_ALIASES.get(normalize_text(str(industry)), ())
                if normalize_text(alias)
            ],
        ]
    ]
    scope_clients = [normalize_text(str(item)).lower() for item in scope.get("clients", []) or [] if normalize_text(str(item))]
    source_type = hit.source_hint or _classify_source_type(hit.url)
    source_label = _derive_source_label(source_type=source_type, domain=domain, fallback=hit.source_label)
    source_tier = _classify_source_tier(source_type=source_type, domain=domain, source_label=source_label)

    theme_match_count = sum(1 for term in theme_terms if term in haystack)
    topic_match_count = sum(1 for term in topic_anchor_terms if term in haystack)
    company_match_count = sum(1 for term in company_anchor_terms if term in haystack or term in domain)
    region_match_count = sum(1 for term in scope_regions if term in haystack)
    industry_match_count = sum(1 for term in scope_industries if term in haystack)
    client_match_count = sum(1 for term in scope_clients if term in haystack)

    score = 0
    if theme_match_count:
        score += 12 + min(theme_match_count, 4) * 4
    if topic_match_count:
        score += 10 + min(topic_match_count, 3) * 4
    if company_match_count:
        score += 16 + min(company_match_count, 2) * 6
    if region_match_count:
        score += 6 + min(region_match_count, 2) * 2
    if industry_match_count:
        score += 6 + min(industry_match_count, 2) * 2
    if client_match_count:
        score += 10 + min(client_match_count, 2) * 4
    if any(term in title_haystack for term in topic_anchor_terms[:4]):
        score += 6
    if any(term in title_haystack for term in company_anchor_terms[:4]):
        score += 8
    if source_tier == "official":
        score += 8
    elif source_tier == "aggregate":
        score += 4
    if source_type == "wechat":
        score += 3
    if bool(scope.get("prefer_company_entities")) and company_anchor_terms and company_match_count == 0:
        return 0, hit
    if topic_anchor_terms and topic_match_count == 0 and theme_match_count == 0 and company_match_count == 0:
        return 0, hit
    return score, hit


def _rrf_score(rank: int, *, k: int = 60) -> float:
    return 1.0 / float(k + max(rank, 1))


def _build_search_hit_retrieval_query(
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object] | None = None,
) -> str:
    scope = scope_hints or {}
    candidates: list[str] = [
        normalize_text(keyword),
        normalize_text(research_focus or ""),
        *_extract_topic_anchor_terms(keyword, research_focus),
        *_resolved_company_anchor_terms(keyword, research_focus, scope),
        *(normalize_text(str(item)) for item in scope.get("clients", []) or [] if normalize_text(str(item))),
        *(normalize_text(str(item)) for item in scope.get("regions", []) or [] if normalize_text(str(item))),
        *(normalize_text(str(item)) for item in scope.get("industries", []) or [] if normalize_text(str(item))),
        *(
            normalize_text(str(item))
            for item in scope.get("strategy_must_include_terms", []) or []
            if normalize_text(str(item))
        ),
        *(
            normalize_text(str(item))
            for item in scope.get("strategy_query_expansions", []) or []
            if normalize_text(str(item))
        ),
    ]
    return normalize_text(" ".join(_dedupe_strings(candidates, 18)))


def _build_search_hit_retrieval_candidates(hit: SearchHit) -> list[TextRetrievalCandidate]:
    normalized_url = normalize_text(hit.url)
    if not normalized_url:
        return []
    domain = extract_domain(hit.url)
    source_type = hit.source_hint or _classify_source_type(hit.url)
    source_label = _derive_source_label(
        source_type=source_type,
        domain=domain,
        fallback=hit.source_label,
    )
    source_tier = _classify_source_tier(
        source_type=source_type,
        domain=domain,
        source_label=source_label,
    )
    priority = 0
    if source_tier == "official":
        priority += 10
    elif source_tier == "aggregate":
        priority += 5
    if source_type in {"policy", "procurement", "filing"}:
        priority += 3
    elif source_type == "wechat":
        priority += 2
    if normalize_text(hit.snippet):
        priority += 2

    primary_text = normalize_text(
        " ".join(
            part
            for part in [
                hit.title,
                hit.snippet,
                source_label or "",
                domain or "",
                hit.url,
            ]
            if normalize_text(part)
        )
    )
    title_text = normalize_text(
        " ".join(
            part
            for part in [
                hit.title,
                source_label or "",
                domain or "",
            ]
            if normalize_text(part)
        )
    )

    candidates = [
        TextRetrievalCandidate(
            key=normalized_url,
            text=primary_text,
            source_tier=source_tier,
            priority=priority,
        )
    ]
    if title_text and title_text != primary_text:
        candidates.append(
            TextRetrievalCandidate(
                key=normalized_url,
                text=title_text,
                source_tier=source_tier,
                priority=max(1, priority - 2),
            )
        )
    return candidates


def _hybrid_rank_hits(
    hits: Iterable[SearchHit],
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object] | None = None,
) -> list[SearchHit]:
    deduped_hits = _dedupe_hits(hits)
    if not deduped_hits:
        return []

    retrieval_scores: dict[str, float] = {}
    semantic_scores: dict[str, int] = {}
    scope_scores: dict[str, int] = {}
    hits_by_url: dict[str, SearchHit] = {}
    theme_terms = _build_theme_terms(keyword, research_focus, scope_hints or {})
    company_anchor_terms = _resolved_company_anchor_terms(keyword, research_focus, scope_hints)
    retrieval_candidates: list[TextRetrievalCandidate] = []

    for hit in deduped_hits:
        normalized_url = normalize_text(hit.url)
        if not normalized_url:
            continue
        hits_by_url[normalized_url] = hit
        retrieval_candidates.extend(_build_search_hit_retrieval_candidates(hit))
        semantic_scores[normalized_url] = _semantic_score_hit(
            hit,
            keyword=keyword,
            research_focus=research_focus,
            scope_hints=scope_hints,
        )[0]
        scope_scores[normalized_url] = _source_scope_match_score(
            hit,
            scope_hints=scope_hints or {},
            company_anchor_terms=company_anchor_terms,
            theme_terms=theme_terms,
        )

    retrieval_query = _build_search_hit_retrieval_query(keyword, research_focus, scope_hints)
    retrieval_matches = retrieve_text_matches(
        retrieval_candidates,
        retrieval_query,
        limit=max(40, len(retrieval_candidates)),
    )
    retrieval_scores = {
        match.key: match.score
        for match in retrieval_matches
        if match.key in hits_by_url and match.score > 0
    }

    retrieval_ranked = [
        match.key
        for match in retrieval_matches
        if match.key in hits_by_url and match.score > 0
    ]
    semantic_ranked = [url for url, _ in sorted(semantic_scores.items(), key=lambda item: item[1], reverse=True) if _ > 0]
    scope_ranked = [url for url, _ in sorted(scope_scores.items(), key=lambda item: item[1], reverse=True) if _ > 0]

    hybrid_scores: dict[str, float] = {}
    for ranked_urls, score_map in (
        (retrieval_ranked, retrieval_scores),
        (semantic_ranked, semantic_scores),
        (scope_ranked, scope_scores),
    ):
        for index, url in enumerate(ranked_urls, start=1):
            hybrid_scores[url] = hybrid_scores.get(url, 0.0) + _rrf_score(index) + float(score_map.get(url, 0)) / 1000.0

    ordered_urls = sorted(
        hybrid_scores,
        key=lambda url: (
            hybrid_scores.get(url, 0.0),
            retrieval_scores.get(url, 0.0),
            semantic_scores.get(url, 0),
            scope_scores.get(url, 0),
        ),
        reverse=True,
    )
    ranked_hits: list[SearchHit] = []
    for url in ordered_urls:
        hit = hits_by_url[url]
        if hybrid_scores.get(url, 0.0) <= 0:
            continue
        if (
            bool((scope_hints or {}).get("prefer_company_entities"))
            and company_anchor_terms
            and not _source_matches_company_anchor(hit, company_anchor_terms)
        ):
            continue
        if (
            retrieval_scores.get(url, 0.0) <= 0
            and semantic_scores.get(url, 0) <= 0
            and scope_scores.get(url, 0) <= 0
        ):
            continue
        ranked_hits.append(hit)
    return ranked_hits


def _build_source_retrieval_candidates(source: SourceDocument) -> list[TextRetrievalCandidate]:
    normalized_url = normalize_text(source.url)
    if not normalized_url:
        return []
    domain = normalize_text(source.domain or "") or extract_domain(source.url) or ""
    source_type = normalize_text(source.source_type) or _classify_source_type(source.url)
    source_label = _derive_source_label(
        source_type=source_type,
        domain=domain,
        fallback=source.source_label,
    )
    source_tier = normalize_text(source.source_tier) or _classify_source_tier(
        source_type=source_type,
        domain=domain,
        source_label=source_label,
    )
    priority = 0
    if source_tier == "official":
        priority += 10
    elif source_tier == "aggregate":
        priority += 5
    if source.content_status == "browser_extracted":
        priority += 8
    elif source.content_status == "extracted":
        priority += 6
    elif source.content_status == "reader_proxy":
        priority += 4
    elif source.content_status in {"snippet_only", "fetch_failed"}:
        priority -= 4
    excerpt = normalize_text(source.excerpt)
    if len(excerpt) >= 260:
        priority += 3

    primary_text = normalize_text(
        " ".join(
            part
            for part in [
                source.title,
                source.snippet,
                excerpt,
                source_label or "",
                domain,
                source.url,
            ]
            if normalize_text(part)
        )
    )
    title_text = normalize_text(
        " ".join(
            part
            for part in [
                source.title,
                source_label or "",
                domain,
            ]
            if normalize_text(part)
        )
    )

    candidates = [
        TextRetrievalCandidate(
            key=normalized_url,
            text=primary_text,
            source_tier=source_tier,
            priority=max(0, priority),
        )
    ]
    if title_text and title_text != primary_text:
        candidates.append(
            TextRetrievalCandidate(
                key=normalized_url,
                text=title_text,
                source_tier=source_tier,
                priority=max(0, priority - 2),
            )
        )
    if excerpt and excerpt not in {primary_text, title_text}:
        candidates.append(
            TextRetrievalCandidate(
                key=normalized_url,
                text=normalize_text(" ".join(part for part in [source.title, excerpt] if normalize_text(part))),
                source_tier=source_tier,
                priority=max(0, priority - 1),
            )
        )
    return candidates


def _source_rerank_score(
    source: SourceDocument,
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object] | None = None,
) -> int:
    theme_terms = _build_theme_terms(keyword, research_focus, scope_hints or {})
    company_anchor_terms = _resolved_company_anchor_terms(keyword, research_focus, scope_hints)
    base = _source_scope_match_score(
        source,
        scope_hints=scope_hints or {},
        company_anchor_terms=company_anchor_terms,
        theme_terms=theme_terms,
    )
    text = normalize_text(
        " ".join(
            [
                source.title,
                source.snippet,
                source.excerpt,
                source.source_label or "",
                source.url,
                source.domain or "",
            ]
        )
    ).lower()
    score = base
    if source.source_tier == "official":
        score += 18
    elif source.source_tier == "aggregate":
        score += 8
    if source.content_status == "browser_extracted":
        score += 10
    elif source.content_status == "extracted":
        score += 7
    elif source.content_status == "reader_proxy":
        score += 5
    elif source.content_status in {"snippet_only", "fetch_failed"}:
        score -= 6
    if len(normalize_text(source.excerpt)) >= 260:
        score += 4
    if len(normalize_text(source.excerpt)) < 120:
        score -= 4
    if company_anchor_terms and not _source_matches_company_anchor(source, company_anchor_terms):
        score -= 14 if bool((scope_hints or {}).get("prefer_company_entities")) else 6
    if any(term in text for term in ("官网", "联系我们", "投资者关系", "合作", "采购", "招标", "中标")):
        score += 4
    if any(term in text for term in ("访问受限", "待补全", "captcha", "验证后即可继续访问")):
        score -= 10
    return score


def _rerank_sources_hybrid(
    sources: Iterable[SourceDocument],
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object] | None = None,
) -> list[SourceDocument]:
    deduped_sources = _dedupe_sources(sources)
    if not deduped_sources:
        return []
    quality_scores: dict[str, int] = {}
    sources_by_url: dict[str, SourceDocument] = {}
    retrieval_candidates: list[TextRetrievalCandidate] = []
    company_anchor_terms = _resolved_company_anchor_terms(keyword, research_focus, scope_hints)

    for source in deduped_sources:
        normalized_url = normalize_text(source.url)
        if not normalized_url:
            continue
        sources_by_url[normalized_url] = source
        quality_scores[normalized_url] = _source_rerank_score(
            source,
            keyword=keyword,
            research_focus=research_focus,
            scope_hints=scope_hints,
        )
        retrieval_candidates.extend(_build_source_retrieval_candidates(source))

    retrieval_query = _build_search_hit_retrieval_query(keyword, research_focus, scope_hints)
    retrieval_matches = retrieve_text_matches(
        retrieval_candidates,
        retrieval_query,
        limit=max(40, len(retrieval_candidates)),
    )
    retrieval_scores = {
        match.key: match.score
        for match in retrieval_matches
        if match.key in sources_by_url and match.score > 0
    }
    retrieval_ranked = [
        match.key
        for match in retrieval_matches
        if match.key in sources_by_url and match.score > 0
    ]
    quality_ranked = [url for url, score in sorted(quality_scores.items(), key=lambda item: item[1], reverse=True) if score > 0]

    hybrid_scores: dict[str, float] = {}
    for ranked_urls, score_map in (
        (retrieval_ranked, retrieval_scores),
        (quality_ranked, quality_scores),
    ):
        for index, url in enumerate(ranked_urls, start=1):
            hybrid_scores[url] = hybrid_scores.get(url, 0.0) + _rrf_score(index) + float(score_map.get(url, 0)) / 1000.0

    ranked_urls = sorted(
        sources_by_url,
        key=lambda url: (
            hybrid_scores.get(url, 0.0),
            retrieval_scores.get(url, 0.0),
            quality_scores.get(url, 0),
            1 if normalize_text(sources_by_url[url].source_tier) == "official" else 0,
            len(normalize_text(sources_by_url[url].excerpt)),
        ),
        reverse=True,
    )
    ranked: list[SourceDocument] = []
    for url in ranked_urls:
        source = sources_by_url[url]
        if (
            bool((scope_hints or {}).get("prefer_company_entities"))
            and company_anchor_terms
            and not _source_matches_company_anchor(source, company_anchor_terms)
        ):
            continue
        if hybrid_scores.get(url, 0.0) <= 0 and quality_scores.get(url, 0) <= 0:
            continue
        ranked.append(source)
    ranked = ranked or [sources_by_url[url] for url in ranked_urls]

    settings = get_settings()
    mutable_scope_hints = scope_hints if isinstance(scope_hints, dict) else {}
    reranker_enabled = bool(
        settings.research_cross_encoder_rerank_enabled
        or mutable_scope_hints.get("enable_cross_encoder_rerank")
        or mutable_scope_hints.get("cross_encoder_rerank")
    )
    if not reranker_enabled:
        return ranked
    reranker_backend = normalize_text(str(mutable_scope_hints.get("runtime_reranker_backend") or settings.research_cross_encoder_backend))
    reranker_top_k = _safe_int(
        mutable_scope_hints.get("runtime_reranker_top_k"),
        settings.research_cross_encoder_top_k,
        minimum=1,
        maximum=80,
    )
    reranker_model = normalize_text(str(mutable_scope_hints.get("runtime_reranker_model") or settings.research_cross_encoder_model))
    reranked, profile = rerank_sources_cross_encoder(
        ranked,
        query=retrieval_query,
        model_name=reranker_model,
        top_k=reranker_top_k,
        backend=reranker_backend,
    )
    mutable_scope_hints.update(profile.to_diagnostics_update())
    return list(reranked)


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
    selected: list[SearchHit] = []
    seen_urls: set[str] = set()
    official_quota = max(2, round(limit * 0.45))
    aggregate_quota = max(1, round(limit * 0.25))

    def classify_hit_tier(hit: SearchHit) -> str:
        source_type = hit.source_hint or _classify_source_type(hit.url)
        domain = extract_domain(hit.url)
        source_label = _derive_source_label(
            source_type=source_type,
            domain=domain,
            fallback=getattr(hit, "source_label", None),
        )
        return _classify_source_tier(source_type=source_type, domain=domain, source_label=source_label)

    def take_hits(match: Callable[[SearchHit], bool], quota: int) -> None:
        if quota <= 0:
            return
        taken = 0
        for hit in hits:
            if taken >= quota:
                break
            normalized_url = normalize_text(hit.url)
            if not normalized_url or normalized_url in seen_urls or not match(hit):
                continue
            seen_urls.add(normalized_url)
            selected.append(hit)
            taken += 1

    take_hits(lambda hit: classify_hit_tier(hit) == "official", official_quota)
    take_hits(lambda hit: classify_hit_tier(hit) == "aggregate", aggregate_quota)
    take_hits(lambda hit: hit.source_hint == "tech_media_feed", 1)
    take_hits(lambda hit: True, limit - len(selected))
    return selected[:limit]


def _classify_source_type(url: str) -> str:
    domain = (extract_domain(url) or "").lower()
    if "jianyu360.com" in domain or "jianyu360.cn" in domain:
        return "tender_feed"
    if "yuntoutiao.com" in domain:
        return "tech_media_feed"
    if "mp.weixin.qq.com" in domain:
        return "wechat"
    if domain in PROCUREMENT_DOMAINS or "ccgp.gov.cn" in domain or "ggzy.gov.cn" in domain:
        return "procurement"
    if domain in EXCHANGE_DOMAINS:
        return "filing"
    if ".gov." in domain or domain.endswith(".gov.cn"):
        return "policy"
    return "web"


def _classify_source_tier(*, source_type: str, domain: str | None, source_label: str | None) -> str:
    normalized_domain = (domain or "").lower()
    normalized_label = normalize_text(source_label or "").lower()
    if source_type in {"policy", "procurement", "filing", "official_tender_feed", "official_tender_news", "official_policy_speech", "regional_public_resource"}:
        return "official"
    if any(token in normalized_label for token in ("官网", "投资者关系", "联系我们", "官方")):
        return "official"
    if any(token in normalized_label for token in ("公共资源", "招标投标网", "政府采购", "中国政府网")):
        return "official"
    if any(token in normalized_domain for token in ("gov.cn", "ggzy.gov.cn", "cninfo.com.cn", "sec.gov", "hkexnews.hk")):
        return "official"
    if source_type in {"tender_feed", "compliant_procurement_aggregate"}:
        return "aggregate"
    if any(token in normalized_label for token in ("剑鱼标讯", "云头条", "合规聚合")):
        return "aggregate" if "云头条" not in normalized_label else "media"
    if any(token in normalized_domain for token in ("jianyu", "cecbid", "cebpubservice", "china-cpp", "chinabidding")):
        return "aggregate"
    return "media"


def _derive_source_label(*, source_type: str, domain: str | None, fallback: str | None) -> str | None:
    if fallback:
        return fallback
    normalized_domain = (domain or "").lower()
    if "ggzy.gov.cn" in normalized_domain:
        return "全国公共资源交易平台"
    if "gov.cn" in normalized_domain:
        return "中国政府网政策/讲话"
    if "cninfo.com.cn" in normalized_domain:
        return "巨潮资讯公告"
    if "hkexnews.hk" in normalized_domain:
        return "港交所公告"
    if "sec.gov" in normalized_domain:
        return "SEC 公告"
    if "mp.weixin.qq.com" in normalized_domain:
        return "微信公众号"
    if "cecbid" in normalized_domain or "cebpubservice" in normalized_domain or "china-cpp" in normalized_domain:
        return "政府采购合规聚合"
    if "jianyu" in normalized_domain:
        return "剑鱼标讯"
    if "yuntoutiao" in normalized_domain:
        return "云头条"
    if source_type == "web":
        return "互联网公开网页"
    return None


def _extract_source_document(hit: SearchHit, *, timeout_seconds: int, excerpt_chars: int) -> SourceDocument:
    title = normalize_text(hit.title) or hit.url
    domain = extract_domain(hit.url)
    source_type = hit.source_hint or _classify_source_type(hit.url)
    source_origin = "adapter" if bool(getattr(hit, "source_label", None)) else "search"
    source_label = _derive_source_label(source_type=source_type, domain=domain, fallback=getattr(hit, "source_label", None))
    source_tier = _classify_source_tier(source_type=source_type, domain=domain, source_label=source_label)
    snippet = _truncate_text(
        _clean_source_text_for_analysis(hit.snippet or "") or _clean_source_text_for_analysis(title),
        180,
    )

    extracted_title = title
    excerpt = snippet
    content_status = "snippet_only"

    if source_type != "tender_feed":
        if source_type == "wechat" or (domain or "").endswith("mp.weixin.qq.com"):
            try:
                extracted = extract_from_browser(hit.url, timeout_seconds=max(timeout_seconds, 12))
                extracted_title = normalize_text(extracted.title or title) or title
                excerpt = _truncate_text(
                    _clean_source_text_for_analysis(extracted.clean_content or extracted.raw_content or snippet),
                    excerpt_chars,
                )
                content_status = "browser_extracted"
            except ContentExtractionError:
                pass
        if content_status == "snippet_only":
            try:
                extracted = extract_from_url(hit.url, timeout_seconds=timeout_seconds)
                extracted_title = normalize_text(extracted.title or title) or title
                excerpt = _truncate_text(
                    _clean_source_text_for_analysis(extracted.clean_content or extracted.raw_content or snippet),
                    excerpt_chars,
                )
                content_status = "extracted"
            except ContentExtractionError:
                try:
                    extracted = extract_from_reader_proxy(hit.url, timeout_seconds=max(timeout_seconds + 2, 10))
                    extracted_title = normalize_text(extracted.title or title) or title
                    excerpt = _truncate_text(
                        _clean_source_text_for_analysis(extracted.clean_content or extracted.raw_content or snippet),
                        excerpt_chars,
                    )
                    content_status = "reader_proxy"
                except ContentExtractionError:
                    pass

    return SourceDocument(
        title=extracted_title,
        url=hit.url,
        domain=domain,
        snippet=snippet,
        search_query=hit.search_query,
        source_type=source_type,
        content_status=content_status,
        excerpt=excerpt,
        source_label=source_label,
        source_tier=source_tier,
        source_origin=source_origin,
    )


def _extract_source_document_best_effort(
    hit: SearchHit,
    *,
    timeout_seconds: int,
    excerpt_chars: int,
) -> SourceDocument | None:
    try:
        return _extract_source_document(
            hit,
            timeout_seconds=timeout_seconds,
            excerpt_chars=excerpt_chars,
        )
    except Exception:
        domain = extract_domain(hit.url)
        source_type = hit.source_hint or _classify_source_type(hit.url)
        source_label = _derive_source_label(
            source_type=source_type,
            domain=domain,
            fallback=getattr(hit, "source_label", None),
        )
        source_tier = _classify_source_tier(
            source_type=source_type,
            domain=domain,
            source_label=source_label,
        )
        if not normalize_text(hit.url):
            return None
        return SourceDocument(
            title=normalize_text(hit.title) or hit.url,
            url=hit.url,
            domain=domain,
            snippet=_truncate_text(
                _clean_source_text_for_analysis(hit.snippet or "") or _clean_source_text_for_analysis(hit.title or hit.url),
                180,
            ),
            search_query=hit.search_query,
            source_type=source_type,
            content_status="fetch_failed",
            excerpt=_truncate_text(
                _clean_source_text_for_analysis(hit.snippet or "") or _clean_source_text_for_analysis(hit.title or hit.url),
                excerpt_chars,
            ),
            source_label=source_label,
            source_tier=source_tier,
            source_origin="adapter" if bool(getattr(hit, "source_label", None)) else "search",
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
    return _source_scope_policy_theme_score(
        source,
        theme_terms=theme_terms,
        scope_hints=scope_hints,
        deps=_source_scope_policy_dependencies(),
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
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
        if len(deduped) >= limit:
            break
    return deduped


def _prune_industry_hints(values: Iterable[str]) -> list[str]:
    hints = _dedupe_strings((normalize_text(value) for value in values), 4)
    if not hints:
        return []
    pruned = list(hints)
    for dominant, suppressed in THEME_GENERIC_SUPPRESSIONS.items():
        if dominant in pruned:
            pruned = [item for item in pruned if item == dominant or item not in suppressed]
    generic_hints = {"大模型", "人工智能", "信息化"}
    if any(item not in generic_hints for item in pruned):
        pruned = [item for item in pruned if item not in generic_hints] + [item for item in pruned if item in generic_hints]
    return _dedupe_strings(pruned, 4)


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
    return _entity_canonical_key_cached(name)


@lru_cache(maxsize=16384)
def _entity_canonical_key_cached(name: str) -> str:
    normalized = normalize_text(_resolve_known_org_name(name))
    return _entity_alias_lookup_key(normalized)


def _entity_graph_builder_dependencies() -> EntityGraphBuilderDependencies:
    return EntityGraphBuilderDependencies(
        source_text=_source_text,
        extract_rank_entity_candidates=_extract_rank_entity_candidates,
        canonical_org_name_from_domain=_canonical_org_name_from_domain,
        extract_domain=extract_domain,
        resolve_known_org_name=_resolve_known_org_name,
        is_plausible_entity_name=_is_plausible_entity_name,
        entity_canonical_key=_entity_canonical_key,
        org_entity_variants=_org_entity_variants,
        org_surface_variants=_org_surface_variants,
        build_entity_evidence=_build_entity_evidence,
    )


def _build_entity_graph(
    sources: list[SourceDocument],
    *,
    scope_hints: dict[str, object],
) -> ResearchEntityGraphOut:
    return _entity_graph_builder_build(
        sources,
        scope_hints=scope_hints,
        deps=_entity_graph_builder_dependencies(),
    )


def _entity_graph_lookup(graph: ResearchEntityGraphOut) -> dict[str, ResearchNormalizedEntityOut]:
    return _entity_graph_builder_lookup(graph, entity_canonical_key=_entity_canonical_key)


def _retrieval_quality_band(
    *,
    strict_match_ratio: float,
    official_source_ratio: float,
    unique_domain_count: int,
    normalized_entity_count: int,
) -> str:
    score = 0
    if strict_match_ratio >= 0.7:
        score += 2
    elif strict_match_ratio >= 0.45:
        score += 1
    if official_source_ratio >= 0.45:
        score += 2
    elif official_source_ratio >= 0.25:
        score += 1
    if unique_domain_count >= 5:
        score += 2
    elif unique_domain_count >= 3:
        score += 1
    if normalized_entity_count >= 9:
        score += 2
    elif normalized_entity_count >= 4:
        score += 1
    if score >= 6:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def _evidence_mode_from_metrics(
    *,
    retained_source_count: int,
    strict_topic_source_count: int,
    strict_match_ratio: float,
    official_source_ratio: float,
    unique_domain_count: int,
) -> tuple[str, str]:
    if (
        retained_source_count >= 4
        and strict_topic_source_count >= 2
        and strict_match_ratio >= 0.45
        and official_source_ratio >= 0.25
        and unique_domain_count >= 3
    ):
        return "strong", "强证据"
    if retained_source_count > 0 and (strict_topic_source_count > 0 or unique_domain_count >= 1):
        return "provisional", "可用初版"
    return "fallback", "兜底候选"


SUMMARY_GUIDANCE_TOKENS = (
    "建议",
    "建議",
    "追加",
    "优先",
    "優先",
    "继续",
    "繼續",
    "收敛到",
    "收斂到",
    "交叉检索",
    "交叉檢索",
    "重新生成",
    "后重试",
    "後重試",
    "把搜索范围",
    "把搜尋範圍",
    "不要只盯",
    "至少要回答",
)

BAD_SUMMARY_PHRASES = (
    *SUMMARY_GUIDANCE_TOKENS,
    "当前关键词范围",
    "优先给具体公司",
    "官方业务联系方式",
    "公开渠道联络人信息",
    "已向美国证券交易委",
    "美国证券交易委",
    "当前证据不足",
    "建议补充",
)

BAD_EXEC_SUMMARY_PHRASES = (
    "当前关键词范围",
    "优先给具体公司",
    "官方业务联系方式",
    "公开渠道联络人信息",
    "已向美国证券交易委",
    "美国证券交易委",
    "当前证据不足",
    "建议补充",
    "继续扩大搜索范围",
    "扩大搜索范围",
)

FIELD_ROW_NOISE_TOKENS = (
    "若金额仍缺失",
    "若暂未拿到明确金额",
    "可先给出高价值预算口径",
    "这些口径最适合后续销售",
    "尽量颗粒度细致到具体的垂直赛道",
    "精确到有预算的甲方公司",
    "建议补充公开服务热线",
    "建议将关键词收敛到具体甲方公司或项目名称",
    "继续扩大搜索范围",
    "当前证据不足",
    "优先给具体公司",
    "把高价值甲方",
    "预算判断不要只盯",
    "优先收集公开业务入口",
    "当前已收敛到具体公司，但公开联系方式仍不足",
    "如果公开联系方式依旧不足",
    "若需形成前三名单",
    "建议追加政府采购、公共资源交易、上市公告和行业媒体对",
)

ENTITY_LEADING_NOISE_PREFIXES = (
    "新增范围锁定到",
    "新增范围集中到",
    "新增重点锁定到",
    "新增重点集中到",
    "范围锁定到",
    "范围集中到",
    "重点锁定到",
    "重点集中到",
    "锁定到",
    "集中到",
    "收敛到",
    "聚焦到",
    "落到",
    "落在",
    "其中就包括",
    "其中包括",
    "其中有",
    "过去一段时间",
    "如果这一方案最终成形",
    "若最终落地",
    "它将被视为",
    "预计将是",
    "但该公司",
    "该公司",
    "关于",
    "例如",
    "比如",
    "诸如",
    "包括",
)

ENTITY_ACTION_PHRASE_TOKENS = (
    "进一步",
    "扩大",
    "推进",
    "推动",
    "打造",
    "贯彻",
    "落实",
    "印发",
    "实施",
    "支持",
    "促进",
    "加强",
    "提升",
    "降低",
    "举办",
    "表示",
    "介绍",
    "显示",
    "获得",
    "收购",
    "聚焦",
)

CONTACT_PLACEHOLDER_TOKENS = (
    "当前已收敛到具体公司，但公开联系方式仍不足",
    "优先收集公开业务入口",
    "建议补充公开服务热线",
    "建议将关键词收敛到具体甲方公司或项目名称",
    "如果公开联系方式依旧不足",
)

ENTITY_PLACEHOLDER_TOKENS = (
    "关键词已明确收敛到该公司",
    "该公司",
    "我方切口在于",
    "需重点验证",
    "优先核验",
    "顶层设计与咨询",
    "动漫 IP 咨询与发行伙伴",
    "区域内容集成与渠道分发伙伴",
    "文旅/教育场景牵线伙伴",
    "推出首批",
    "掌握底层AI服务",
    "大视听公共服务",
    "全方位服务",
)

GENERIC_COUNT_ENTITY_PATTERN = re.compile(r"^[一二三四五六七八九十百千两几多\d]+家")

COMMERCIAL_BUDGET_SIGNAL_TOKENS = (
    "预算",
    "采购",
    "招标",
    "中标",
    "项目",
    "投资",
    "经费",
    "金额",
    "资金",
    "专项",
    "立项",
    "合同额",
    "财政",
    "扩容",
)

BUDGET_ROW_NOISE_TOKENS = (
    "同比增长",
    "经济数据",
    "中国经济",
    "开局良好",
    "民生网首页",
    "微信 微博",
    "豆瓣 ",
    "关注民生周刊",
    "客户端 专题报道",
    "市场规模",
    "爆发元年",
    "公开市场投资者",
    "newcomer",
    "云头条",
)

BUDGET_ROW_CONTEXT_TOKENS = (
    "预算",
    "采购",
    "招标",
    "中标",
    "项目",
    "立项",
    "合同",
    "签约",
    "批复",
    "经费",
    "专项",
    "财政",
)


def _looks_like_insufficient(value: str) -> bool:
    lowered = normalize_text(value).lower()
    return any(
        token in lowered
        for token in (
            "当前证据不足",
            "目前證據不足",
            "current evidence is insufficient",
            "evidence is insufficient",
            "待补充",
            "待補充",
            "insufficient",
        )
    )


@lru_cache(maxsize=8192)
def _strip_entity_leading_noise(value: str) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    compact = normalized
    changed = True
    while changed and compact:
        changed = False
        for prefix in ENTITY_LEADING_NOISE_PREFIXES:
            if compact.startswith(prefix):
                compact = normalize_text(compact[len(prefix) :].lstrip("：:，,;；- "))
                changed = True
    return compact


@lru_cache(maxsize=8192)
def _looks_like_sentence_fragment_entity(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return False
    if normalized in SPECIAL_ENTITY_ALIASES or normalized in KNOWN_LIGHTWEIGHT_ENTITY_NAMES:
        return False
    lowered = normalized.lower()
    if lowered in {"microsoft", "openai"}:
        return False
    if re.search(r"(?:一|两|二|几|多|\d+)\s*家(?:公司|企业|厂商|机构)$", normalized):
        return True
    if normalized.startswith(ENTITY_FRAGMENT_PREFIX_TOKENS):
        return True
    if any(token in normalized for token in ENTITY_FRAGMENT_INFIX_TOKENS):
        return True
    if any(token in normalized for token in ENTITY_INVALID_PHRASE_TOKENS):
        return True
    if len(normalized) >= 10 and any(token in normalized for token in ("了", "可以", "通过", "不用", "仍是", "仍将", "转向")):
        return True
    return False


def _looks_like_source_artifact_text(value: str) -> bool:
    return _source_documents_looks_like_artifact(value)


def _looks_like_source_noise_segment(value: str, *, raw_value: str | None = None) -> bool:
    return _source_documents_looks_like_noise_segment(value, raw_value=raw_value)


def _clean_source_text_for_analysis(value: str) -> str:
    return _source_documents_clean_source_text(value)


@lru_cache(maxsize=8192)
def _looks_like_placeholder_entity_name(value: str) -> bool:
    normalized = _strip_entity_leading_noise(value)
    lowered = normalized.lower()
    if not normalized:
        return False
    if normalized in SPECIAL_ENTITY_ALIASES or normalized in KNOWN_LIGHTWEIGHT_ENTITY_NAMES:
        return False
    if _looks_like_sentence_fragment_entity(normalized):
        return True
    if "（如" in normalized or "(如" in normalized:
        return True
    if normalized.startswith(("AI的", "一直", "此前", "在杭州市", "相关负责人", "对公开市场投资者而言", "上海作为")):
        return True
    if normalized.startswith(("推出首批", "构建PC端", "构建移动端", "对具有重大影响力的")):
        return True
    industry_alias_values = {
        normalize_text(alias)
        for aliases in INDUSTRY_SCOPE_ALIASES.values()
        for alias in aliases
        if normalize_text(alias)
    }
    if normalized in industry_alias_values:
        return False
    if GENERIC_COUNT_ENTITY_PATTERN.match(normalized):
        return True
    if re.search(r"(19|20)\d{2}", normalized):
        return True
    if "待验证" in normalized or "待驗證" in normalized:
        return True
    if any(token in normalized for token in ENTITY_PLACEHOLDER_TOKENS):
        return True
    if any(token in normalized for token in GENERIC_SCOPE_CLIENT_TOKENS):
        return True
    if any(token in lowered for token in ("报名通道开启", "多端联动", "opc社区", "opc创新社区", "超级个体")):
        return True
    if normalized in {"科技数码", "主办与协办", "基础算力与云服务", "区域大型系统集成", "开发集团", "各有关大学", "并经市政府"}:
        return True
    if len(normalized) <= 6 and normalized.endswith("公司") and any(token in normalized for token in ("音乐", "内容", "行业", "平台", "企业", "厂商")):
        return True
    if normalized.endswith(("服务中心", "信息中心", "数据中心")) and not any(
        token in normalized for token in (*REGION_TOKENS, "人民", "市", "省", "区", "县", "集团", "公司", "大学", "医院")
    ):
        return True
    if normalized.endswith(("系统", "方案", "平台")) and not any(
        token in normalized for token in ("公司", "集团", "科技", "软件", "信息", "智能", "云", "股份", "有限公司")
    ):
        return True
    if normalized.endswith(("伙伴", "咨询", "顾问", "发行伙伴", "牵线伙伴")) and not any(
        token in normalized for token in ENTITY_SUFFIX_TOKENS
    ):
        return True
    if len(normalized) <= 6 and normalized.endswith(("数码", "团队", "云服务")) and not any(
        token in normalized for token in ENTITY_SUFFIX_TOKENS
    ):
        return True
    if any(token in normalized for token in ENTITY_ACTION_PHRASE_TOKENS) and not any(
        token in normalized for token in ENTITY_SUFFIX_TOKENS
    ):
        return True
    if normalized.endswith(("人工智能", "生成式AI", "大模型", "AI")) and not any(
        token in normalized for token in ENTITY_SUFFIX_TOKENS
    ):
        return True
    return False


def _looks_like_placeholder_contact_row(value: str) -> bool:
    normalized = normalize_text(value)
    return bool(normalized) and any(token in normalized for token in CONTACT_PLACEHOLDER_TOKENS)


def _is_actionable_budget_row(value: str) -> bool:
    normalized = normalize_text(value)
    if (
        not normalized
        or _looks_like_insufficient(normalized)
        or _looks_like_source_artifact_text(normalized)
        or any(token in normalized for token in BUDGET_ROW_NOISE_TOKENS)
        or any(token in normalized for token in FIELD_ROW_NOISE_TOKENS)
    ):
        return False
    has_money_signal = bool(MONEY_PATTERN.search(normalized))
    has_strict_budget_signal = any(
        token in normalized for token in ("预算", "采购", "招标", "中标", "经费", "金额", "资金", "专项", "立项", "合同额", "财政", "扩容")
    )
    has_budget_context = any(token in normalized for token in BUDGET_ROW_CONTEXT_TOKENS)
    has_project_or_investment_signal = any(token in normalized for token in ("项目", "投资"))
    if has_money_signal or has_strict_budget_signal:
        return True
    if has_project_or_investment_signal and any(
        token in normalized for token in ("预算", "采购", "招标", "中标", "立项", "合同", "财政", "金额", "经费", "专项")
    ):
        return True
    if "投资" in normalized and not (has_money_signal or has_budget_context):
        return False
    return False


def _summary_contains_output_noise(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return False
    if len(normalized) > 320:
        return True
    if _looks_like_source_artifact_text(normalized):
        return True
    if any(token in normalized for token in FIELD_ROW_NOISE_TOKENS):
        return True
    if any(token in normalized for token in ("CSDN博客", "腾讯新闻", "文章标签", "报告共计", "中国政府网政策/讲话")):
        return True
    for candidate in _extract_rank_entity_candidates(normalized)[:6]:
        cleaned = _strip_entity_leading_noise(candidate)
        if not cleaned or _looks_like_scope_prompt_noise(cleaned) or _looks_like_placeholder_entity_name(cleaned):
            return True
    return False


def _concrete_rows(values: Iterable[str]) -> list[str]:
    return [normalize_text(value) for value in values if normalize_text(value) and not _looks_like_insufficient(value)]


def _is_summary_fact_row(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized or _looks_like_insufficient(normalized):
        return False
    if _looks_like_source_artifact_text(normalized):
        return False
    if any(token in normalized for token in SUMMARY_GUIDANCE_TOKENS):
        return False
    if any(token in normalized for token in FIELD_ROW_NOISE_TOKENS):
        return False
    if len(normalized) > 48 and "：" not in normalized and ":" not in normalized and "（" not in normalized:
        return False
    return True


def _summary_fact_rows(values: Iterable[str], *, limit: int = 3) -> list[str]:
    return _dedupe_strings([normalize_text(value) for value in values if _is_summary_fact_row(value)], limit)


def _looks_like_bad_executive_summary(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return True
    if len(normalized) < 36:
        return True
    if _summary_contains_output_noise(normalized):
        return True
    if any(token in normalized for token in BAD_EXEC_SUMMARY_PHRASES):
        return True
    if normalized.count("：") > 3 or normalized.count(":") > 3:
        return True
    if normalized.startswith(("本次", "当前", "建议", "研究", "报告")) and len(normalized) > 80:
        return True
    if len(normalized) > 220 and "。" not in normalized and "." not in normalized:
        return True
    return False


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


ENTITY_ROLE_FIELDS: dict[str, str] = {
    "target_accounts": "target",
    "client_peer_moves": "target",
    "competitor_profiles": "competitor",
    "winner_peer_moves": "competitor",
    "ecosystem_partners": "partner",
}

ENTITY_ROLE_CONTEXT_TOKENS: dict[str, tuple[str, ...]] = {
    "target": ("采购", "预算", "招标", "项目", "建设", "立项", "规划", "部署", "业主", "甲方"),
    "competitor": ("中标", "成交", "方案", "平台", "交付", "厂商", "案例", "竞品", "产品", "解决方案"),
    "partner": ("合作", "伙伴", "联合", "生态", "咨询", "顾问", "渠道", "集成", "联盟", "牵线", "总包"),
}

ENTITY_ROLE_NAME_HINTS: dict[str, tuple[str, ...]] = {
    "target": ("政府", "局", "委", "办", "中心", "医院", "大学", "银行", "学校", "集团", "城投", "交投", "水务", "地铁"),
    "competitor": ("科技", "信息", "软件", "智能", "云", "数据", "通信", "平台", "系统", "股份", "有限公司"),
    "partner": ("咨询", "顾问", "集成", "渠道", "联盟", "协会", "研究院", "研究所", "运营", "服务"),
}

CONTACT_PAGE_TOKENS = ("contact", "lxwm", "about", "relation", "ir", "investor", "join", "service", "联系我们", "联络", "联系")
COMPANY_PROFILE_PAGE_TOKENS = (
    *CONTACT_PAGE_TOKENS,
    "官网",
    "官方",
    "公开入口",
    "关于我们",
    "公司简介",
    "企业简介",
    "品牌介绍",
    "aboutus",
    "about-us",
    "official",
    "profile",
    "company",
    "business",
    "solution",
    "brand",
    "investor relations",
)
CONTACT_ROW_HINT_TOKENS = (
    "公开邮箱",
    "公开电话",
    "公开联系人",
    "高概率公开联系页",
    "官网/公开入口",
    "服务热线",
    "联系邮箱",
    "联系电话",
    "采购人联系人",
    "代理机构联系人",
    "可能归口部门",
)
DEPARTMENT_HINT_TOKENS = (
    "采购部",
    "采购中心",
    "招标办",
    "招采中心",
    "集采中心",
    "信息中心",
    "信息化部",
    "数字化部",
    "科技部",
    "数据局",
    "数据资源局",
    "办公室",
    "财务部",
    "计划财务部",
    "运营部",
    "网络安全部",
    "政务服务中心",
    "行政审批局",
    "事业发展部",
    "建设管理部",
    "投资管理部",
)
CASE_HINT_TOKENS = ("案例", "项目", "落地", "部署", "平台", "中标", "示范", "试点", "标杆")
PRODUCT_HINT_TOKENS = ("产品", "平台", "系统", "方案", "服务", "引擎", "模型", "套件")
NON_CONTACT_SOURCE_LABEL_TOKENS = ("云头条", "剑鱼标讯", "微信公众号", "互联网公开网页", "政府采购合规聚合")


@lru_cache(maxsize=8192)
def _contains_low_value_entity_token(value: str) -> bool:
    normalized = normalize_text(value)
    return any(token in normalized for token in LOW_VALUE_ENTITY_NAME_TOKENS)


@lru_cache(maxsize=8192)
def _trim_product_spec_from_entity_name(value: str) -> str:
    normalized = _strip_entity_leading_noise(value)
    if not normalized:
        return ""
    product_tail_patterns = (
        r"^([A-Za-z0-9\u4e00-\u9fa5·]{2,18}半导体)(?:\d|[一二三四五六七八九十]|先进|用|CIS|芯片|硅片|制程|工艺|项目|产线|封装|传感器).+$",
        r"^([A-Za-z0-9\u4e00-\u9fa5·]{2,18}集成电路)(?:\d|[一二三四五六七八九十]|先进|用|芯片|硅片|制程|工艺|项目|产线).+$",
    )
    for pattern in product_tail_patterns:
        match = re.match(pattern, normalized, flags=re.IGNORECASE)
        if match:
            candidate = _strip_entity_leading_noise(match.group(1))
            if candidate and not any(token in candidate for token in LOW_VALUE_ENTITY_NAME_TOKENS):
                return candidate
    return normalized


@lru_cache(maxsize=8192)
def _is_lightweight_entity_name(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized or len(normalized) < 2 or len(normalized) > 14:
        return False
    if normalized not in KNOWN_LIGHTWEIGHT_ENTITY_NAMES:
        return False
    if _contains_low_value_entity_token(normalized):
        return False
    if any(token in normalized for token in ENTITY_INVALID_PHRASE_TOKENS):
        return False
    if any(token in normalized for token in ("入口", "官网", "官网入口", "公开入口", "联系页", "会员中心")):
        return False
    if any(char in normalized for char in "：:（）()[]【】"):
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9\u4e00-\u9fa5·]{2,14}", normalized))


@lru_cache(maxsize=8192)
def _looks_like_fragment_entity_name(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return True
    if _looks_like_sentence_fragment_entity(normalized):
        return True
    if _looks_like_placeholder_entity_name(normalized):
        return True
    if re.match(r"^(19|20)\d{2}", normalized):
        return True
    if normalized.startswith(ENTITY_FRAGMENT_PREFIX_TOKENS):
        return True
    if any(token in normalized for token in ENTITY_FRAGMENT_INFIX_TOKENS):
        return True
    if (
        len(normalized) <= 4
        and normalized.endswith(("局", "委", "办", "中心", "政府"))
        and not any(token in normalized for token in (*REGION_TOKENS, "人民", "文物", "数据", "信息", "交通", "教育", "医疗"))
        and normalized not in KNOWN_LIGHTWEIGHT_ENTITY_NAMES
    ):
        return True
    if (
        normalized.endswith(("服务", "系统", "社区"))
        and not any(token in normalized for token in ENTITY_SUFFIX_TOKENS)
        and normalized not in KNOWN_LIGHTWEIGHT_ENTITY_NAMES
    ):
        return True
    if (
        normalized.endswith("中心")
        and (
            "新型" in normalized
            or not any(
                token in normalized
                for token in (
                    *REGION_TOKENS,
                    "市", "省", "区", "县", "政府", "政务", "局", "委", "办", "大学", "医院", "学校",
                    "人民", "公共", "资源", "交易", "采购", "服务", "管理", "研究", "信息化",
                )
            )
        )
        and normalized not in KNOWN_LIGHTWEIGHT_ENTITY_NAMES
    ):
        return True
    return False


@lru_cache(maxsize=8192)
def _fallback_entity_name_from_row(value: str) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    head = _strip_entity_leading_noise(normalized.split("：", 1)[0].split(":", 1)[0])
    if _is_lightweight_entity_name(head):
        return head
    match = re.match(r"([A-Za-z0-9\u4e00-\u9fa5·]{2,14})(?:等|与|及|和|在|已|将|正|宣布|布局|入局|合作|参与)", normalized)
    if match:
        candidate = _strip_entity_leading_noise(match.group(1))
        if _is_lightweight_entity_name(candidate):
            return candidate
    return ""


def _report_field_sanitization_dependencies() -> ReportFieldSanitizationDependencies:
    return ReportFieldSanitizationDependencies(
        looks_like_insufficient=_looks_like_insufficient,
        looks_like_source_artifact_text=_looks_like_source_artifact_text,
        looks_like_placeholder_contact_row=_looks_like_placeholder_contact_row,
        contains_low_value_entity_token=_contains_low_value_entity_token,
        is_plausible_entity_name=_is_plausible_entity_name,
        is_lightweight_entity_name=_is_lightweight_entity_name,
        extract_rank_entity_name=_extract_rank_entity_name,
        fallback_entity_name_from_row=_fallback_entity_name_from_row,
        strip_entity_leading_noise=_strip_entity_leading_noise,
        looks_like_fragment_entity_name=_looks_like_fragment_entity_name,
        looks_like_scope_prompt_noise=_looks_like_scope_prompt_noise,
        looks_like_placeholder_entity_name=_looks_like_placeholder_entity_name,
        is_actionable_budget_row=_is_actionable_budget_row,
        entity_canonical_key=_entity_canonical_key,
        email_pattern=EMAIL_PATTERN,
        phone_pattern=PHONE_PATTERN,
        department_pattern=DEPARTMENT_PATTERN,
        generic_content_domains=GENERIC_CONTENT_DOMAINS,
        non_contact_source_label_tokens=NON_CONTACT_SOURCE_LABEL_TOKENS,
        contact_row_hint_tokens=CONTACT_ROW_HINT_TOKENS,
        contact_page_tokens=CONTACT_PAGE_TOKENS,
        department_hint_tokens=DEPARTMENT_HINT_TOKENS,
        entity_role_fields=ENTITY_ROLE_FIELDS,
        entity_role_name_hints=ENTITY_ROLE_NAME_HINTS,
        entity_role_context_tokens=ENTITY_ROLE_CONTEXT_TOKENS,
        partner_connector_aliases=PARTNER_CONNECTOR_ALIASES,
        field_row_noise_tokens=FIELD_ROW_NOISE_TOKENS,
        case_hint_tokens=CASE_HINT_TOKENS,
        product_hint_tokens=PRODUCT_HINT_TOKENS,
    )


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


def _extract_matching_sentences(
    sources: list[SourceDocument],
    *,
    keywords: tuple[str, ...],
    limit: int,
    scope_hints: dict[str, object] | None = None,
) -> list[str]:
    sentences: list[str] = []
    normalized_keywords = tuple(normalize_text(item).lower() for item in keywords if normalize_text(item))
    for source in sources:
        chunks = re.split(r"[。！？!?；;\n]", _source_text(source))
        for chunk in chunks:
            text = normalize_text(chunk)
            lowered = text.lower()
            if not text:
                continue
            if any(keyword in lowered for keyword in normalized_keywords):
                if scope_hints and _text_has_region_conflict(text, scope_hints=scope_hints):
                    continue
                sentences.append(_truncate_text(text, 110))
    return _dedupe_strings(sentences, limit)


def _extract_money_signals(
    sources: list[SourceDocument],
    *,
    limit: int,
    scope_hints: dict[str, object] | None = None,
) -> list[str]:
    signals: list[str] = []
    for source in sources:
        text = _source_text(source)
        for match in MONEY_PATTERN.finditer(text):
            start = max(0, match.start() - 18)
            end = min(len(text), match.end() + 26)
            candidate = _truncate_text(text[start:end], 110)
            if scope_hints and _text_has_region_conflict(candidate, scope_hints=scope_hints):
                continue
            signals.append(candidate)
    if not signals:
        signals = _extract_matching_sentences(
            sources,
            keywords=("预算", "投资", "金额", "经费", "财政投入"),
            limit=limit,
            scope_hints=scope_hints,
        )
    return _dedupe_strings(signals, limit)


def _extract_region_distribution(
    sources: list[SourceDocument],
    *,
    limit: int,
    scope_hints: dict[str, object] | None = None,
) -> list[str]:
    counter: Counter[str] = Counter()
    region_examples: dict[str, str] = {}
    allowed_regions = set()
    if scope_hints:
        allowed_regions = {
            item.lower()
            for item in _expand_region_scope_terms(
                [normalize_text(str(region)) for region in scope_hints.get("regions", []) if normalize_text(str(region))]
            )
        }
    for source in sources:
        text = _source_text(source)
        for region in REGION_TOKENS:
            if allowed_regions and region.lower() not in allowed_regions:
                continue
            if region in text:
                counter[region] += 1
                region_examples.setdefault(region, _truncate_text(source.title, 64))
    rows = [
        f"{region}：公开线索 {count} 条，代表样本 {region_examples.get(region, '待补充')}"
        for region, count in counter.most_common(limit)
    ]
    return _dedupe_strings(rows, limit)


def _expand_region_scope_terms(regions: list[str]) -> list[str]:
    expanded: list[str] = []
    for raw_region in regions:
        normalized = normalize_text(raw_region)
        if not normalized:
            continue
        expanded.append(normalized)
        expanded.extend(REGION_SCOPE_ALIASES.get(normalized, ()))
    return _dedupe_strings(expanded, 24)


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


def _pick_industry_methodology_profile(
    industries: Iterable[str],
    *,
    keyword: str,
    research_focus: str | None,
) -> IndustryMethodologyProfile | None:
    candidates = [normalize_text(str(item)) for item in industries if normalize_text(str(item))]
    priority_order = (
        "政务云",
        "医疗",
        "教育",
        "金融",
        "能源",
        "数据中心",
        "智慧城市",
        "AI漫剧",
        "信息化",
        "大模型",
        "人工智能",
    )
    sorted_candidates = sorted(
        candidates,
        key=lambda candidate: priority_order.index(candidate) if candidate in priority_order else len(priority_order),
    )
    for candidate in sorted_candidates:
        profile = INDUSTRY_METHODOLOGY_PROFILES.get(candidate)
        if profile is not None:
            return profile
    lowered_seed = normalize_text(f"{keyword} {research_focus or ''}").lower()
    for label, aliases in INDUSTRY_SCOPE_ALIASES.items():
        if not any(normalize_text(alias).lower() in lowered_seed for alias in aliases):
            continue
        profile = INDUSTRY_METHODOLOGY_PROFILES.get(label)
        if profile is not None:
            return profile
    if any(token in lowered_seed for token in ("ai", "人工智能", "大模型", "生成式")):
        return INDUSTRY_METHODOLOGY_PROFILES.get("大模型")
    return None


def _format_methodology_query_templates(
    profile: IndustryMethodologyProfile | None,
    *,
    keyword: str,
    research_focus: str | None,
    regions: list[str],
    industries: list[str],
    clients: list[str],
) -> list[str]:
    if profile is None:
        return []
    replacements = {
        "keyword": _strip_query_noise(keyword) or normalize_text(keyword),
        "focus": _strip_query_noise(research_focus or "") or normalize_text(research_focus or ""),
        "region": normalize_text(regions[0]) if regions else "",
        "industry": normalize_text(industries[0]) if industries else profile.key,
        "client": normalize_text(clients[0]) if clients else "",
    }
    queries: list[str] = []
    for template in profile.query_templates:
        try:
            rendered = template.format(**replacements)
        except Exception:
            rendered = template
        normalized = normalize_text(rendered)
        if normalized:
            queries.append(normalized)
    return _dedupe_strings(queries, 8)


def _build_industry_methodology_scope_hints(
    *,
    keyword: str,
    research_focus: str | None,
    regions: list[str],
    industries: list[str],
    clients: list[str],
) -> dict[str, object]:
    profile = _pick_industry_methodology_profile(industries, keyword=keyword, research_focus=research_focus)
    if profile is None:
        return {}
    query_expansions = _format_methodology_query_templates(
        profile,
        keyword=keyword,
        research_focus=research_focus,
        regions=regions,
        industries=industries,
        clients=clients,
    )
    return {
        "industry_methodology_profile": profile.key,
        "industry_methodology_authority": profile.authority_label,
        "industry_methodology_framework": profile.framework,
        "industry_methodology_questions": list(profile.primary_questions),
        "industry_methodology_source_preferences": list(profile.source_preferences),
        "industry_methodology_solution_lenses": list(profile.solution_lenses),
        "industry_methodology_sales_lenses": list(profile.sales_lenses),
        "industry_methodology_bidding_lenses": list(profile.bidding_lenses),
        "industry_methodology_outreach_lenses": list(profile.outreach_lenses),
        "industry_methodology_ecosystem_lenses": list(profile.ecosystem_lenses),
        "strategy_query_expansions": query_expansions,
        "strategy_scope_summary": normalize_text(f"{profile.authority_label}｜{profile.framework}"),
    }


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


def _build_industry_methodology_rows(
    *,
    scope_hints: dict[str, object],
    output_language: str,
    scope_anchor: str,
) -> dict[str, list[str]]:
    profile = normalize_text(str(scope_hints.get("industry_methodology_profile", "")))
    framework = normalize_text(str(scope_hints.get("industry_methodology_framework", "")))
    if not profile and not framework:
        return {}
    solution_lenses = _dedupe_strings(scope_hints.get("industry_methodology_solution_lenses", []) or [], 4)
    sales_lenses = _dedupe_strings(scope_hints.get("industry_methodology_sales_lenses", []) or [], 4)
    bidding_lenses = _dedupe_strings(scope_hints.get("industry_methodology_bidding_lenses", []) or [], 4)
    outreach_lenses = _dedupe_strings(scope_hints.get("industry_methodology_outreach_lenses", []) or [], 4)
    ecosystem_lenses = _dedupe_strings(scope_hints.get("industry_methodology_ecosystem_lenses", []) or [], 4)
    questions = _dedupe_strings(scope_hints.get("industry_methodology_questions", []) or [], 4)
    label = profile or scope_anchor
    return {
        "industry_brief": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"{label} 建议按“{framework or '需求拆解 -> 预算验证 -> 招采节奏 -> 扩容路径'}”来组织研究，而不是只做泛行业素材汇总。",
                    "zh-TW": f"{label} 建議按「{framework or '需求拆解 -> 預算驗證 -> 招採節奏 -> 擴容路徑'}」來組織研究，而不是只做泛行業素材彙整。",
                    "en": f"For {label}, organize the memo around {framework or 'demand, budget, procurement timing, and expansion path'} instead of generic market commentary.",
                },
                f"{label} 建议按“{framework or '需求拆解 -> 预算验证 -> 招采节奏 -> 扩容路径'}”来组织研究，而不是只做泛行业素材汇总。",
            )
        ],
        "solution_design": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"方案设计优先围绕 {label} 的 {(' / '.join(solution_lenses) or '场景闭环 / 分期实施 / 集成改造 / 扩容路径')} 拆解。",
                    "zh-TW": f"方案設計優先圍繞 {label} 的 {(' / '.join(solution_lenses) or '場景閉環 / 分期實施 / 整合改造 / 擴容路徑')} 拆解。",
                    "en": f"Solution design should emphasize {', '.join(solution_lenses) or 'use-case closure, phased rollout, integration, and expansion'} for {label}.",
                },
                f"方案设计优先围绕 {label} 的 {(' / '.join(solution_lenses) or '场景闭环 / 分期实施 / 集成改造 / 扩容路径')} 拆解。",
            )
        ],
        "sales_strategy": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"销售推进优先验证 {(' / '.join(sales_lenses) or '牵头部门 / 预算归口 / 年度节点 / 扩容窗口')}，避免只聊产品能力。",
                    "zh-TW": f"銷售推進優先驗證 {(' / '.join(sales_lenses) or '牽頭部門 / 預算歸口 / 年度節點 / 擴容窗口')}，避免只聊產品能力。",
                    "en": f"Sales planning should validate {', '.join(sales_lenses) or 'the buyer lead, budget owner, planning cycle, and expansion window'} before pitching product.",
                },
                f"销售推进优先验证 {(' / '.join(sales_lenses) or '牵头部门 / 预算归口 / 年度节点 / 扩容窗口')}，避免只聊产品能力。",
            )
        ],
        "bidding_strategy": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"投标布局优先核验 {(' / '.join(bidding_lenses) or '采购意向 / 总分包结构 / 资质要求 / 交付壁垒')}。",
                    "zh-TW": f"投標布局優先核驗 {(' / '.join(bidding_lenses) or '採購意向 / 總分包結構 / 資質要求 / 交付壁壘')}。",
                    "en": f"Bidding planning should verify {', '.join(bidding_lenses) or 'intent notices, prime/subcontract structure, qualification requirements, and delivery barriers'}.",
                },
                f"投标布局优先核验 {(' / '.join(bidding_lenses) or '采购意向 / 总分包结构 / 资质要求 / 交付壁垒')}。",
            )
        ],
        "outreach_strategy": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"拜访顺序建议按 {(' / '.join(outreach_lenses) or '牵头部门 -> 预算归口 -> 采购执行 -> 落地部门')} 展开。",
                    "zh-TW": f"拜訪順序建議按 {(' / '.join(outreach_lenses) or '牽頭部門 -> 預算歸口 -> 採購執行 -> 落地部門')} 展開。",
                    "en": f"Outreach should follow {', '.join(outreach_lenses) or 'business lead, budget owner, procurement, then implementation teams'}.",
                },
                f"拜访顺序建议按 {(' / '.join(outreach_lenses) or '牵头部门 -> 预算归口 -> 采购执行 -> 落地部门')} 展开。",
            )
        ],
        "ecosystem_strategy": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"生态优先围绕 {(' / '.join(ecosystem_lenses) or '总包 / 集成 / 顾问 / 本地交付')} 建立牵线链路。",
                    "zh-TW": f"生態優先圍繞 {(' / '.join(ecosystem_lenses) or '總包 / 整合 / 顧問 / 在地交付')} 建立牽線鏈路。",
                    "en": f"Ecosystem mapping should prioritize {', '.join(ecosystem_lenses) or 'primes, integrators, advisors, and local delivery partners'}.",
                },
                f"生态优先围绕 {(' / '.join(ecosystem_lenses) or '总包 / 集成 / 顾问 / 本地交付')} 建立牵线链路。",
            )
        ],
        "next_actions": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"先补证这几个问题：{'；'.join(questions) if questions else '锁定牵头部门、预算口径、招采窗口和扩容路径'}。",
                    "zh-TW": f"先補證這幾個問題：{'；'.join(questions) if questions else '鎖定牽頭部門、預算口徑、招採窗口與擴容路徑'}。",
                    "en": f"First validate these questions: {'; '.join(questions) if questions else 'buyer lead, budget line, procurement window, and expansion path'}.",
                },
                f"先补证这几个问题：{'；'.join(questions) if questions else '锁定牵头部门、预算口径、招采窗口和扩容路径'}。",
            )
        ],
    }


def _infer_input_scope_hints(
    keyword: str,
    research_focus: str | None,
) -> dict[str, object]:
    seed_text = normalize_text(" ".join([keyword, _sanitize_research_focus_text(research_focus)]))
    exclusion_terms = _extract_explicit_exclusion_terms(research_focus)
    if not seed_text:
        return {
            "regions": [],
            "industries": [],
            "clients": [],
            "company_anchors": [],
            "strategy_must_include_terms": [],
            "strategy_exclusion_terms": exclusion_terms,
            "strategy_query_expansions": [],
            "strategy_scope_summary": "",
            "anchor_text": "",
            "industry_methodology_profile": "",
            "industry_methodology_authority": "",
            "industry_methodology_framework": "",
            "industry_methodology_questions": [],
            "industry_methodology_source_preferences": [],
            "industry_methodology_solution_lenses": [],
            "industry_methodology_sales_lenses": [],
            "industry_methodology_bidding_lenses": [],
            "industry_methodology_outreach_lenses": [],
            "industry_methodology_ecosystem_lenses": [],
        }

    region_hints = _dedupe_strings(
        [
            label
            for label, aliases in REGION_SCOPE_ALIASES.items()
            if any(alias in seed_text for alias in aliases)
        ]
        + [region for region in REGION_TOKENS if region in seed_text],
        4,
    )
    industry_hints = _prune_industry_hints(
        [
            label
            for label, aliases in INDUSTRY_SCOPE_ALIASES.items()
            if any(alias in seed_text for alias in aliases)
        ]
    )
    theme_labels = _dedupe_strings(
        [*industry_hints, *_theme_labels_from_scope({}, keyword=keyword, research_focus=research_focus)],
        3,
    )
    prefer_company_entities, prefer_head_companies = _infer_company_query_preferences(
        seed_text,
        theme_labels=theme_labels,
    )
    company_anchors = _extract_company_anchor_terms(keyword, research_focus)
    client_candidates = [
        item
        for item in company_anchors[:3]
        if _is_theme_aligned_entity_name(item, role="target", theme_labels=theme_labels)
    ]
    if not client_candidates:
        client_candidates = _dedupe_strings(
            [
                item
                for item in ORG_PATTERN.findall(seed_text)
                if _is_theme_aligned_entity_name(item, role="target", theme_labels=theme_labels)
            ],
            3,
        )
    strategy_must_include_terms = _dedupe_strings(
        [
            term
            for label in industry_hints
            for term in THEME_STRICT_MUST_INCLUDE_TERMS.get(label, ())
        ],
        8,
    )
    seed_companies = _dedupe_strings(
        [
            item
            for label in theme_labels
            for item in THEME_COMPANY_PUBLIC_SOURCE_SEEDS.get(label, ())
        ],
        12,
    )
    methodology_scope_hints = _build_industry_methodology_scope_hints(
        keyword=keyword,
        research_focus=research_focus,
        regions=region_hints,
        industries=theme_labels or industry_hints,
        clients=client_candidates,
    )

    return {
        "regions": region_hints,
        "industries": industry_hints,
        "clients": client_candidates,
        "company_anchors": company_anchors[:4],
        "prefer_company_entities": prefer_company_entities,
        "prefer_head_companies": prefer_head_companies,
        "seed_companies": seed_companies if prefer_company_entities or prefer_head_companies else [],
        "strategy_must_include_terms": strategy_must_include_terms,
        "strategy_exclusion_terms": exclusion_terms,
        "strategy_query_expansions": [],
        "strategy_scope_summary": "",
        "anchor_text": normalize_text(" / ".join(region_hints[:2] + industry_hints[:2] + client_candidates[:2])),
        **methodology_scope_hints,
    }


def _infer_scope_hints(
    keyword: str,
    research_focus: str | None,
    sources: list[SourceDocument],
) -> dict[str, object]:
    seed_text = normalize_text(
        " ".join([keyword, _sanitize_research_focus_text(research_focus)] + [f"{source.title} {source.snippet}" for source in sources[:10]])
    )
    region_counter: Counter[str] = Counter()
    for label, aliases in REGION_SCOPE_ALIASES.items():
        if any(alias in seed_text for alias in aliases):
            region_counter[label] += 4
    for region in REGION_TOKENS:
        if region in seed_text:
            region_counter[region] += 3
    for source in sources:
        text = _source_text(source)
        for label, aliases in REGION_SCOPE_ALIASES.items():
            if any(alias in text for alias in aliases):
                region_counter[label] += 1
        for region in REGION_TOKENS:
            if region in text:
                region_counter[region] += 1

    region_hints = [region for region, _ in region_counter.most_common(3)]

    normalized_seed = seed_text.lower()
    industry_hints: list[str] = []
    for label, aliases in INDUSTRY_SCOPE_ALIASES.items():
        if any(alias.lower() in normalized_seed for alias in aliases):
            industry_hints.append(label)
    industry_hints = list(dict.fromkeys(industry_hints))[:3]
    theme_labels = _dedupe_strings(
        [*industry_hints, *_theme_labels_from_scope({}, keyword=keyword, research_focus=research_focus)],
        3,
    )
    prefer_company_entities, prefer_head_companies = _infer_company_query_preferences(
        seed_text,
        theme_labels=theme_labels,
    )

    company_anchors = _extract_company_anchor_terms(keyword, research_focus)
    org_candidates = _extract_org_candidates(sources, limit=24)
    client_candidates = [
        item
        for item in company_anchors[:3]
        if _is_theme_aligned_entity_name(item, role="target", theme_labels=theme_labels)
    ]
    if theme_labels:
        client_candidates.extend(
            item
            for item in org_candidates
            if _is_theme_aligned_entity_name(item, role="target", theme_labels=theme_labels)
            and _looks_like_target_scope_entity_name(item)
        )
    else:
        client_candidates.extend(
            item
            for item in org_candidates
            if any(
                token in item
                for token in ("政府", "局", "委", "办", "中心", "医院", "大学", "银行", "学校", "集团", "城投", "交投", "水务", "地铁")
            )
        )
    client_candidates = _dedupe_strings(client_candidates, 3)
    if not client_candidates:
        keyword_orgs = [
            normalize_text(item)
            for item in ORG_PATTERN.findall(seed_text)
            if _is_plausible_entity_name(normalize_text(item)) or _is_lightweight_entity_name(normalize_text(item))
        ]
        client_candidates = _dedupe_strings(
            [
                item
                for item in keyword_orgs
                if _is_theme_aligned_entity_name(item, role="target", theme_labels=theme_labels)
            ],
            3,
        )

    seed_companies = _dedupe_strings(
        [
            item
            for label in theme_labels
            for item in THEME_COMPANY_PUBLIC_SOURCE_SEEDS.get(label, ())
        ],
        12,
    )
    methodology_scope_hints = _build_industry_methodology_scope_hints(
        keyword=keyword,
        research_focus=research_focus,
        regions=region_hints,
        industries=theme_labels or industry_hints,
        clients=client_candidates,
    )

    return {
        "regions": region_hints,
        "industries": industry_hints,
        "clients": client_candidates,
        "company_anchors": company_anchors[:4],
        "prefer_company_entities": prefer_company_entities,
        "prefer_head_companies": prefer_head_companies,
        "seed_companies": seed_companies if prefer_company_entities or prefer_head_companies else [],
        "anchor_text": normalize_text(" / ".join(region_hints[:2] + industry_hints[:2] + client_candidates[:2])),
        **methodology_scope_hints,
    }


def _merge_scope_hints(
    base: dict[str, object],
    refined: dict[str, object],
) -> dict[str, object]:
    base_regions = [normalize_text(str(item)) for item in (base.get("regions", []) or []) if normalize_text(str(item))]
    refined_regions = [normalize_text(str(item)) for item in (refined.get("regions", []) or []) if normalize_text(str(item))]
    if base_regions:
        allowed_terms = {item.lower() for item in _expand_region_scope_terms(base_regions)}
        region_candidates = list(base_regions)
        region_candidates.extend(
            item
            for item in refined_regions
            if item.lower() in allowed_terms
            or any(alias.lower() in allowed_terms for alias in REGION_SCOPE_ALIASES.get(item, ()))
        )
        regions = _dedupe_strings(region_candidates, 3)
    else:
        regions = _dedupe_strings([*refined_regions], 3)
    base_industries = [normalize_text(str(item)) for item in (base.get("industries", []) or []) if normalize_text(str(item))]
    refined_industries = [normalize_text(str(item)) for item in (refined.get("industries", []) or []) if normalize_text(str(item))]
    if base_industries:
        allowed_industry_terms = {
            normalize_text(alias)
            for industry in base_industries
            for alias in (industry, *INDUSTRY_SCOPE_ALIASES.get(industry, ()))
            if normalize_text(alias)
        }
        industry_candidates = list(base_industries)
        industry_candidates.extend(
            item
            for item in refined_industries
            if item in allowed_industry_terms
            or any(normalize_text(alias) in allowed_industry_terms for alias in INDUSTRY_SCOPE_ALIASES.get(item, ()))
        )
        industries = _prune_industry_hints(industry_candidates)
    else:
        industries = _prune_industry_hints(refined_industries)

    base_clients = [normalize_text(str(item)) for item in (base.get("clients", []) or []) if normalize_text(str(item))]
    refined_clients = [normalize_text(str(item)) for item in (refined.get("clients", []) or []) if normalize_text(str(item))]
    if base_clients:
        clients = _dedupe_strings(
            [
                *base_clients,
                *[
                    item
                    for item in refined_clients
                    if any(base_client in item or item in base_client for base_client in base_clients)
                ],
            ],
            3,
        )
    else:
        clients = _dedupe_strings(refined_clients, 3)

    base_company_anchors = [
        normalize_text(str(item))
        for item in (base.get("company_anchors", []) or [])
        if normalize_text(str(item))
    ]
    refined_company_anchors = [
        normalize_text(str(item))
        for item in (refined.get("company_anchors", []) or [])
        if normalize_text(str(item))
    ]
    if base_company_anchors:
        company_anchors = _dedupe_strings(
            [
                *base_company_anchors,
                *[
                    item
                    for item in refined_company_anchors
                    if any(anchor in item or item in anchor for anchor in base_company_anchors)
                ],
            ],
            4,
        )
    else:
        company_anchors = _dedupe_strings(refined_company_anchors, 4)
    clients = _clean_scope_entity_names(clients, limit=3, theme_labels=industries)
    company_anchors = _clean_scope_entity_names(company_anchors, limit=4, theme_labels=industries)
    strategy_must_include_terms = _dedupe_strings(
        [*(base.get("strategy_must_include_terms", []) or []), *(refined.get("strategy_must_include_terms", []) or [])],
        8,
    )
    strategy_exclusion_terms = _dedupe_strings(
        [*(base.get("strategy_exclusion_terms", []) or []), *(refined.get("strategy_exclusion_terms", []) or [])],
        8,
    )
    strategy_query_expansions = _dedupe_strings(
        [
            item
            for item in [*(base.get("strategy_query_expansions", []) or []), *(refined.get("strategy_query_expansions", []) or [])]
            if normalize_text(str(item))
            and not any(exclusion in normalize_text(str(item)) for exclusion in strategy_exclusion_terms)
        ],
        10,
    )
    strategy_scope_summary = normalize_text(str(refined.get("strategy_scope_summary", ""))) or normalize_text(
        str(base.get("strategy_scope_summary", ""))
    )
    prefer_company_entities = bool(base.get("prefer_company_entities")) or bool(refined.get("prefer_company_entities"))
    prefer_head_companies = bool(base.get("prefer_head_companies")) or bool(refined.get("prefer_head_companies"))
    seed_companies = _dedupe_strings(
        [
            normalize_text(str(item))
            for item in [*(base.get("seed_companies", []) or []), *(refined.get("seed_companies", []) or [])]
            if normalize_text(str(item))
        ],
        12,
    )
    industry_methodology_profile = normalize_text(str(refined.get("industry_methodology_profile", ""))) or normalize_text(
        str(base.get("industry_methodology_profile", ""))
    )
    industry_methodology_authority = normalize_text(str(refined.get("industry_methodology_authority", ""))) or normalize_text(
        str(base.get("industry_methodology_authority", ""))
    )
    industry_methodology_framework = normalize_text(str(refined.get("industry_methodology_framework", ""))) or normalize_text(
        str(base.get("industry_methodology_framework", ""))
    )
    industry_methodology_questions = _dedupe_strings(
        [*(base.get("industry_methodology_questions", []) or []), *(refined.get("industry_methodology_questions", []) or [])],
        6,
    )
    industry_methodology_source_preferences = _dedupe_strings(
        [
            *(base.get("industry_methodology_source_preferences", []) or []),
            *(refined.get("industry_methodology_source_preferences", []) or []),
        ],
        6,
    )
    industry_methodology_solution_lenses = _dedupe_strings(
        [
            *(base.get("industry_methodology_solution_lenses", []) or []),
            *(refined.get("industry_methodology_solution_lenses", []) or []),
        ],
        6,
    )
    industry_methodology_sales_lenses = _dedupe_strings(
        [
            *(base.get("industry_methodology_sales_lenses", []) or []),
            *(refined.get("industry_methodology_sales_lenses", []) or []),
        ],
        6,
    )
    industry_methodology_bidding_lenses = _dedupe_strings(
        [
            *(base.get("industry_methodology_bidding_lenses", []) or []),
            *(refined.get("industry_methodology_bidding_lenses", []) or []),
        ],
        6,
    )
    industry_methodology_outreach_lenses = _dedupe_strings(
        [
            *(base.get("industry_methodology_outreach_lenses", []) or []),
            *(refined.get("industry_methodology_outreach_lenses", []) or []),
        ],
        6,
    )
    industry_methodology_ecosystem_lenses = _dedupe_strings(
        [
            *(base.get("industry_methodology_ecosystem_lenses", []) or []),
            *(refined.get("industry_methodology_ecosystem_lenses", []) or []),
        ],
        6,
    )
    runtime_strategy_applied_lanes = _dedupe_strings(
        [
            *(base.get("runtime_strategy_applied_lanes", []) or []),
            *(refined.get("runtime_strategy_applied_lanes", []) or []),
        ],
        8,
    )
    runtime_strategy_fallback_lanes = _dedupe_strings(
        [
            *(base.get("runtime_strategy_fallback_lanes", []) or []),
            *(refined.get("runtime_strategy_fallback_lanes", []) or []),
        ],
        8,
    )
    runtime_strategy_warnings = _dedupe_strings(
        [
            *(base.get("runtime_strategy_warnings", []) or []),
            *(refined.get("runtime_strategy_warnings", []) or []),
        ],
        8,
    )
    runtime_strategy_status = normalize_text(str(refined.get("runtime_strategy_status") or base.get("runtime_strategy_status") or ""))
    runtime_query_recovery_enabled = bool(base.get("runtime_query_recovery_enabled")) or bool(
        refined.get("runtime_query_recovery_enabled")
    )
    runtime_source_reranker_enabled = bool(base.get("runtime_source_reranker_enabled")) or bool(
        refined.get("runtime_source_reranker_enabled")
    )
    runtime_corrective_query_limit = _safe_int(
        refined.get("runtime_corrective_query_limit") or base.get("runtime_corrective_query_limit"),
        0,
        minimum=0,
        maximum=12,
    )
    runtime_public_expansion_on_watch = bool(base.get("runtime_public_expansion_on_watch")) or bool(
        refined.get("runtime_public_expansion_on_watch")
    )
    runtime_reranker_adapter = normalize_text(str(refined.get("runtime_reranker_adapter") or base.get("runtime_reranker_adapter") or ""))
    runtime_reranker_backend = normalize_text(str(refined.get("runtime_reranker_backend") or base.get("runtime_reranker_backend") or ""))
    runtime_reranker_top_k = _safe_int(
        refined.get("runtime_reranker_top_k") or base.get("runtime_reranker_top_k"),
        0,
        minimum=0,
        maximum=20,
    )
    runtime_reranker_fallback_adapter = normalize_text(
        str(refined.get("runtime_reranker_fallback_adapter") or base.get("runtime_reranker_fallback_adapter") or "")
    )
    runtime_official_source_bias = bool(base.get("runtime_official_source_bias")) or bool(
        refined.get("runtime_official_source_bias")
    )
    enable_cross_encoder_rerank = bool(base.get("enable_cross_encoder_rerank")) or bool(
        refined.get("enable_cross_encoder_rerank")
    )
    cross_encoder_rerank = bool(base.get("cross_encoder_rerank")) or bool(refined.get("cross_encoder_rerank"))
    anchor_text = normalize_text(" / ".join(regions[:2] + industries[:2] + clients[:2]))
    if not anchor_text:
        anchor_text = normalize_text(str(refined.get("anchor_text", ""))) or normalize_text(str(base.get("anchor_text", "")))
    return {
        "regions": regions,
        "industries": industries,
        "clients": clients,
        "company_anchors": company_anchors,
        "prefer_company_entities": prefer_company_entities,
        "prefer_head_companies": prefer_head_companies,
        "seed_companies": seed_companies,
        "strategy_must_include_terms": strategy_must_include_terms,
        "strategy_exclusion_terms": strategy_exclusion_terms,
        "strategy_query_expansions": strategy_query_expansions,
        "strategy_scope_summary": strategy_scope_summary,
        "anchor_text": anchor_text,
        "industry_methodology_profile": industry_methodology_profile,
        "industry_methodology_authority": industry_methodology_authority,
        "industry_methodology_framework": industry_methodology_framework,
        "industry_methodology_questions": industry_methodology_questions,
        "industry_methodology_source_preferences": industry_methodology_source_preferences,
        "industry_methodology_solution_lenses": industry_methodology_solution_lenses,
        "industry_methodology_sales_lenses": industry_methodology_sales_lenses,
        "industry_methodology_bidding_lenses": industry_methodology_bidding_lenses,
        "industry_methodology_outreach_lenses": industry_methodology_outreach_lenses,
        "industry_methodology_ecosystem_lenses": industry_methodology_ecosystem_lenses,
        "runtime_strategy_status": runtime_strategy_status,
        "runtime_strategy_applied_lanes": runtime_strategy_applied_lanes,
        "runtime_strategy_fallback_lanes": runtime_strategy_fallback_lanes,
        "runtime_strategy_warnings": runtime_strategy_warnings,
        "runtime_query_recovery_enabled": runtime_query_recovery_enabled,
        "runtime_source_reranker_enabled": runtime_source_reranker_enabled,
        "runtime_corrective_query_limit": runtime_corrective_query_limit,
        "runtime_public_expansion_on_watch": runtime_public_expansion_on_watch,
        "runtime_reranker_adapter": runtime_reranker_adapter,
        "runtime_reranker_backend": runtime_reranker_backend,
        "runtime_reranker_top_k": runtime_reranker_top_k,
        "runtime_reranker_fallback_adapter": runtime_reranker_fallback_adapter,
        "runtime_official_source_bias": runtime_official_source_bias,
        "enable_cross_encoder_rerank": enable_cross_encoder_rerank,
        "cross_encoder_rerank": cross_encoder_rerank,
    }


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
    labels = [
        normalize_text(str(item))
        for item in scope_hints.get("industries", []) or []
        if normalize_text(str(item))
    ]
    lowered_terms = " ".join(_extract_topic_anchor_terms(keyword, research_focus)).lower()
    if any(token in lowered_terms for token in ("ai漫剧", "漫剧", "ai短剧", "aigc动画", "动漫短剧", "漫画短剧")):
        labels.append("AI漫剧")
    if any(token in lowered_terms for token in ("政务云", "数字政府", "政务")):
        labels.append("政务云")
    return _dedupe_strings(labels, 3)


def _infer_company_query_preferences(
    seed_text: str,
    *,
    theme_labels: list[str],
) -> tuple[bool, bool]:
    lowered = normalize_text(seed_text).lower()
    prefer_company_entities = any(token in lowered for token in COMPANY_ENTITY_QUERY_TOKENS)
    prefer_head_companies = prefer_company_entities and any(token in lowered for token in HEAD_COMPANY_QUERY_TOKENS)
    if not prefer_company_entities and "AI漫剧" in theme_labels:
        prefer_company_entities = any(
            token in lowered
            for token in ("发行方", "版权方", "平台方", "工作室", "内容平台", "短剧平台", "动漫平台")
        )
    return prefer_company_entities, prefer_head_companies


def _is_theme_aligned_entity_name(
    value: str,
    *,
    role: str,
    theme_labels: list[str],
) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return False
    if not theme_labels:
        return True
    for theme_label in theme_labels:
        if normalized in THEME_COMPANY_PUBLIC_SOURCE_SEEDS.get(theme_label, ()):
            return True
        allow_tokens = THEME_ENTITY_ALLOW_TOKENS.get(theme_label, {}).get(role, ())
        block_tokens = THEME_ENTITY_BLOCK_TOKENS.get(theme_label, {}).get(role, ())
        if any(token in normalized for token in block_tokens):
            return False
        if any(token in normalized for token in allow_tokens):
            return True
    return not any(
        token in normalized
        for theme_label in theme_labels
        for token in THEME_ENTITY_BLOCK_TOKENS.get(theme_label, {}).get(role, ())
    )


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


def _looks_like_target_scope_entity_name(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized or not _is_plausible_entity_name(normalized):
        return False
    if normalized in SPECIAL_ENTITY_ALIASES and normalized not in {"中国移动", "中国电信", "中国联通"}:
        return False
    target_tokens = (
        "政府",
        "人民政府",
        "局",
        "委",
        "厅",
        "办",
        "中心",
        "医院",
        "大学",
        "学院",
        "学校",
        "银行",
        "集团",
        "城投",
        "交投",
        "水务",
        "地铁",
        "文旅",
        "医药",
        "药业",
        "制药",
        "生物",
    )
    vendor_only_tokens = ("OpenAI", "Microsoft", "Azure", "云", "软件", "信息", "算法", "模型")
    if any(token in normalized for token in target_tokens):
        return True
    if any(token in normalized for token in vendor_only_tokens):
        return False
    return False


def _filtered_rank_fallback_values(
    values: Iterable[str],
    *,
    role: str,
    scope_hints: dict[str, object],
) -> list[str]:
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
    prefer_company_entities = bool(scope_hints.get("prefer_company_entities"))
    candidates: list[str] = []
    for value in values:
        normalized = normalize_text(str(value))
        if (
            not normalized
            or _looks_like_insufficient(normalized)
            or _looks_like_source_artifact_text(normalized)
            or _looks_like_scope_prompt_noise(normalized)
        ):
            continue
        extracted = _extract_rank_entity_candidates(normalized, scope_hints=scope_hints)
        fallback = _fallback_entity_name_from_row(normalized)
        for candidate in [*extracted, *([fallback] if fallback else [])]:
            compact = _resolve_known_org_name(candidate, scope_hints=scope_hints)
            compact = _strip_entity_leading_noise(compact)
            if (
                not compact
                or _looks_like_fragment_entity_name(compact)
                or _contains_low_value_entity_token(compact)
                or _looks_like_placeholder_entity_name(compact)
                or _looks_like_scope_prompt_noise(compact)
            ):
                continue
            if theme_labels and not _is_theme_aligned_entity_name(compact, role=role, theme_labels=theme_labels):
                continue
            if prefer_company_entities and role in {"target", "competitor"} and not _is_company_like_entity_name(
                compact,
                role=role,
                theme_labels=theme_labels,
                seed_companies=seed_companies,
            ):
                continue
            candidates.append(compact)
    return _dedupe_strings(candidates, 12)


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
    cleaned: list[str] = []
    for item in segments:
        normalized = _sanitize_title_scope_token(item)
        if not normalized:
            continue
        if normalized in cleaned:
            continue
        cleaned.append(normalized)
        if len(cleaned) >= limit:
            break
    return cleaned


def _scope_anchor_text_segments(value: str | None) -> list[str]:
    normalized = normalize_text(value or "")
    if not normalized:
        return []
    return [
        normalize_text(part)
        for part in re.split(r"[|｜/／]+", normalized)
        if normalize_text(part)
    ]


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
        get_strategy_llm_service=get_strategy_llm_service,
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
    return _strategy_refinement_apply_topic_overrides(
        result,
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        scope_hints=scope_hints,
        intelligence=intelligence,
        deps=_strategy_refinement_dependencies(),
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


def _source_supports_target_account(
    source: SourceDocument,
    entity_name: str,
    *,
    theme_terms: list[str],
    scope_hints: dict[str, object],
) -> bool:
    if not _source_mentions_entity(source, entity_name):
        return False
    if _source_negates_entity(source, entity_name):
        return False
    if _stored_source_is_low_signal(source, theme_terms=theme_terms, scope_hints=scope_hints):
        return False
    return True


def _build_entity_specific_contact_rows(
    sources: list[SourceDocument],
    *,
    entity_names: list[str],
    output_language: str,
    limit: int,
) -> list[str]:
    if not entity_names:
        return []

    normalized_entities = [
        normalize_text(name)
        for name in entity_names
        if normalize_text(name) and "待验证" not in normalize_text(name) and "待驗證" not in normalize_text(name)
        and (_is_plausible_entity_name(normalize_text(name)) or _is_lightweight_entity_name(normalize_text(name)))
    ]
    if not normalized_entities:
        return []

    contact_person_pattern = re.compile(
        r"(联系人|联络人|联系人姓名|项目联系人|采购人联系人|代理机构联系人)[:：]?\s*([A-Za-z\u4e00-\u9fa5]{2,24})"
    )
    line_contact_pattern = re.compile(
        r"([A-Za-z0-9\u4e00-\u9fa5·（）()]{2,36})(联系人|联系电话|联系邮箱|服务热线|咨询电话)[:：]?\s*([A-Za-z0-9@\-.+\u4e00-\u9fa5]{2,48})"
    )
    procurement_like_source_types = {
        "procurement",
        "official_tender_feed",
        "compliant_procurement_aggregate",
        "tender_feed",
    }
    official_contact_source_types = {
        "policy",
        "filing",
        "official_policy_speech",
    }

    def is_valid_contact_value(value: str) -> bool:
        normalized = normalize_text(value)
        lowered = normalized.lower()
        if not normalized:
            return False
        if any(lowered.endswith(ext) for ext in (".webp", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".bmp")):
            return False
        if lowered.startswith("http") and any(domain in lowered for domain in GENERIC_CONTENT_DOMAINS):
            return False
        return True

    def looks_like_company_domain(domain: str) -> bool:
        lowered = normalize_text(domain).lower()
        if not lowered:
            return False
        if lowered in GENERIC_CONTENT_DOMAINS or lowered in PROCUREMENT_DOMAINS or lowered in POLICY_DOMAINS or lowered in EXCHANGE_DOMAINS:
            return False
        if lowered.endswith(".gov.cn") or lowered.endswith(".edu.cn"):
            return False
        return "." in lowered

    scored_rows: dict[str, int] = {}

    def add_row(row: str, score: int) -> None:
        normalized = normalize_text(row)
        if not normalized or not _is_useful_public_contact_row(normalized):
            return
        current = scored_rows.get(normalized)
        if current is None or score > current:
            scored_rows[normalized] = score

    for entity in _dedupe_strings(normalized_entities, 6):
        for source in sources:
            if not _source_mentions_entity(source, entity):
                continue
            text = _source_text(source)
            domain = normalize_text(source.domain or "")
            title_or_url = f"{source.title or ''} {source.url or ''}".lower()
            label = normalize_text(source.source_label or source.title or domain or entity)
            contact_page = any(token in title_or_url for token in CONTACT_PAGE_TOKENS)
            official_like = source.source_tier == "official" or source.source_type in official_contact_source_types
            procurement_like = source.source_type in procurement_like_source_types

            if looks_like_company_domain(domain) and official_like:
                add_row(f"{entity}：官方公开入口 https://{domain}", 92)

            if contact_page and source.url and is_valid_contact_value(source.url):
                add_row(f"{entity}：高概率公开联系页 {source.url}", 96 if official_like else 82)

            for _, person in contact_person_pattern.findall(text)[:2]:
                normalized_person = normalize_text(person)
                if not normalized_person:
                    continue
                prefix = "采购/项目联系人" if procurement_like else "公开联系人"
                add_row(
                    f"{entity}：{prefix} {normalized_person}（{label}）",
                    94 if procurement_like else 84,
                )

            for owner, field_name, value in line_contact_pattern.findall(text)[:3]:
                normalized_owner = normalize_text(owner)
                normalized_value = normalize_text(value)
                if not normalized_value or not is_valid_contact_value(normalized_value):
                    continue
                owner_text = normalized_owner if normalized_owner and normalized_owner != entity else ""
                add_row(
                    f"{entity}：{owner_text}{field_name} {normalized_value}（{label}）",
                    98 if procurement_like else (90 if official_like else 80),
                )

            for email in EMAIL_PATTERN.findall(text)[:2]:
                if not is_valid_contact_value(email):
                    continue
                add_row(
                    f"{entity}：公开邮箱 {email}（{label}）",
                    96 if official_like else (92 if procurement_like else 78),
                )

            for phone in PHONE_PATTERN.findall(text)[:2]:
                normalized_phone = normalize_text(phone)
                if not is_valid_contact_value(normalized_phone):
                    continue
                add_row(
                    f"{entity}：公开电话 {normalized_phone}（{label}）",
                    95 if procurement_like else (88 if official_like else 76),
                )

    ordered = [
        row
        for row, _ in sorted(
            scored_rows.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]
    if ordered:
        return ordered[:limit]
    return []


def _build_entity_specific_team_rows(
    sources: list[SourceDocument],
    *,
    entity_names: list[str],
    scope_hints: dict[str, object],
    output_language: str,
    limit: int,
) -> list[str]:
    if not entity_names:
        return []

    normalized_entities = [
        normalize_text(name)
        for name in entity_names
        if normalize_text(name) and "待验证" not in normalize_text(name) and "待驗證" not in normalize_text(name)
        and (_is_plausible_entity_name(normalize_text(name)) or _is_lightweight_entity_name(normalize_text(name)))
    ]
    if not normalized_entities:
        return []

    team_keywords = (
        "团队",
        "事业群",
        "事业部",
        "业务线",
        "业务部",
        "行业线",
        "政企",
        "政务",
        "行业解决方案",
        "行业方案",
        "区域公司",
        "区域团队",
        "创新中心",
        "研究院",
        "交付中心",
        "运营团队",
        "商务合作",
        "合作团队",
        "内容生态",
        "生态合作",
        "大客户部",
        "客户成功",
        "公共事务",
        "投资者关系",
    )
    scope_regions = [normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    scope_region_terms = _expand_region_scope_terms(scope_regions)
    scope_industries = [normalize_text(str(item)) for item in scope_hints.get("industries", []) if normalize_text(str(item))]
    scored_rows: dict[str, int] = {}

    def add_row(row: str, score: int) -> None:
        normalized = normalize_text(row)
        if not normalized:
            return
        current = scored_rows.get(normalized)
        if current is None or score > current:
            scored_rows[normalized] = score

    for entity in _dedupe_strings(normalized_entities, 6):
        for source in sources:
            if not _source_mentions_entity(source, entity):
                continue
            text = _source_text(source)
            chunks = re.split(r"[。！？!?；;\n]", text)
            label = normalize_text(source.source_label or source.title or source.domain or entity)
            for chunk in chunks:
                sentence = normalize_text(chunk)
                if not sentence or entity not in sentence:
                    continue
                if _text_has_region_conflict(sentence, scope_hints=scope_hints):
                    continue
                if not any(token in sentence for token in team_keywords):
                    continue
                score = 72
                if source.source_tier == "official":
                    score += 12
                elif source.source_tier == "aggregate":
                    score += 6
                if any(region and region in sentence for region in scope_region_terms):
                    score += 8
                if any(industry and industry in sentence for industry in scope_industries):
                    score += 6
                if any(token in sentence for token in ("负责", "牵头", "落地", "推进", "合作", "运营", "交付")):
                    score += 6
                add_row(f"{entity}：{_truncate_text(sentence, 108)}（{label}）", score)

    ordered = [
        row
        for row, _ in sorted(
            scored_rows.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]
    if ordered:
        return ordered[:limit]

    scope_text = " / ".join(_dedupe_strings([*scope_regions[:2], *scope_industries[:2]], 3)) or normalize_text(
        str(scope_hints.get("anchor_text", ""))
    ) or localized_text(
        output_language,
        {
            "zh-CN": "当前范围",
            "zh-TW": "目前範圍",
            "en": "the current scope",
        },
        "当前范围",
    )
    return _dedupe_strings(
        [
            localized_text(
                output_language,
                {
                    "zh-CN": f"当前已收敛到具体公司，建议优先核验其在 {scope_text} 下的政企/行业方案团队、区域交付团队与商务合作团队公开线索。",
                    "zh-TW": f"目前已收斂到具體公司，建議優先核驗其在 {scope_text} 下的政企/產業方案團隊、區域交付團隊與商務合作團隊公開線索。",
                    "en": f"The report converged to specific companies. Next verify public signals for their regional delivery, industry solution, and business partnership teams within {scope_text}.",
                },
                f"当前已收敛到具体公司，建议优先核验其在 {scope_text} 下的政企/行业方案团队、区域交付团队与商务合作团队公开线索。",
            ),
        ],
        limit,
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


def _section_quality_dependencies() -> SectionQualityDependencies:
    return SectionQualityDependencies(
        source_text=_source_text,
        tokenize_for_match=_tokenize_for_match,
        concrete_rows=_concrete_rows,
        dedupe_strings=_dedupe_strings,
        generic_focus_tokens=GENERIC_FOCUS_TOKENS,
    )


def _section_confidence_profile(
    *,
    section_title: str,
    items: list[str],
    sources: list[SourceDocument],
    evidence_density: str,
    source_quality: str,
    official_source_ratio: float,
    meets_evidence_quota: bool,
    evidence_links: list[ResearchEntityEvidenceOut],
) -> tuple[str, str, str, bool, str]:
    return _section_quality_confidence_profile(
        section_title=section_title,
        items=items,
        sources=sources,
        evidence_density=evidence_density,
        source_quality=source_quality,
        official_source_ratio=official_source_ratio,
        meets_evidence_quota=meets_evidence_quota,
        evidence_links=evidence_links,
        deps=_section_quality_dependencies(),
    )


def _extract_rank_entity_name(value: str) -> str:
    candidates = _extract_rank_entity_candidates(value)
    return candidates[0] if candidates else ""


@lru_cache(maxsize=16384)
def _is_plausible_entity_name(value: str) -> bool:
    normalized = _strip_entity_leading_noise(value)
    if not normalized or len(normalized) < 3:
        return False
    if _looks_like_sentence_fragment_entity(normalized):
        return False
    if _looks_like_fragment_entity_name(normalized):
        return False
    if _looks_like_placeholder_entity_name(normalized):
        return False
    if _contains_low_value_entity_token(normalized):
        return False
    if any(token in normalized for token in ENTITY_BLACKLIST_TOKENS):
        return False
    if any(token in normalized for token in ENTITY_INVALID_PHRASE_TOKENS):
        return False
    if any(char in normalized for char in "，,。；;"):
        return False
    if normalized.startswith(("和", "与", "及", "或", "如", "例如", "比如", "诸如", "优先给", "官方", "公开")):
        return False
    if (
        any(connector in normalized for connector in ("与", "及", "和"))
        and normalized not in SPECIAL_ENTITY_ALIASES
        and not any(token in normalized for token in ENTITY_SUFFIX_TOKENS)
    ):
        return False
    if "：" in normalized or ":" in normalized:
        return False
    if normalized.endswith(("怎么办", "如何", "制作", "是指", "相关")):
        return False
    if re.search(r"(路径|节奏|策略|打法|能力|场景|机会|商机|窗口|趋势|布局|运营|建设|规划|升级|协同|统筹)$", normalized):
        return False
    industry_alias_values = {
        normalize_text(alias)
        for aliases in INDUSTRY_SCOPE_ALIASES.values()
        for alias in aliases
        if normalize_text(alias)
    }
    if normalized in industry_alias_values:
        return False
    if any(alias == normalized or alias in normalized for alias in SPECIAL_ENTITY_ALIASES):
        return True
    if any(token in normalized for token in ENTITY_SUFFIX_TOKENS):
        return True
    compact = re.sub(r"\s+", "", normalized)
    if ORG_PATTERN.fullmatch(compact) or COMPACT_ENTITY_PATTERN.fullmatch(compact):
        return True
    return False


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
    return _entity_ranking_rank_top_entities(
        sources,
        role=role,
        output_language=output_language,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        entity_graph=entity_graph,
        fallback_values=fallback_values,
        limit=limit,
        deps=_entity_ranking_heuristic_dependencies(),
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


def _scope_insufficient_rows(
    *,
    output_language: str,
    scope_hints: dict[str, object],
    dimension_label: str,
    limit: int,
) -> list[str]:
    anchor = normalize_text(str(scope_hints.get("anchor_text", "")))
    scope_text = anchor or localized_text(
        output_language,
        {
            "zh-CN": "当前关键词范围",
            "zh-TW": "目前關鍵詞範圍",
            "en": "the current keyword scope",
        },
        "当前关键词范围",
    )
    templates = localized_text(
        output_language,
        {
            "zh-CN": f"当前证据不足：建议继续补充 {scope_text} 的 {dimension_label} 公开线索。",
            "zh-TW": f"目前證據不足：建議繼續補充 {scope_text} 的 {dimension_label} 公開線索。",
            "en": f"Current evidence is insufficient: expand public evidence for {dimension_label} within {scope_text}.",
        },
        f"当前证据不足：建议继续补充 {scope_text} 的 {dimension_label} 公开线索。",
    )
    followups = [
        localized_text(
            output_language,
            {
                "zh-CN": f"建议追加政府采购、公共资源交易、上市公告和行业媒体对 {scope_text} 的交叉检索。",
                "zh-TW": f"建議追加政府採購、公共資源交易、上市公告與產業媒體對 {scope_text} 的交叉檢索。",
                "en": f"Add government procurement, public resource exchange, filings, and media cross-searches around {scope_text}.",
            },
            f"建议追加政府采购、公共资源交易、上市公告和行业媒体对 {scope_text} 的交叉检索。",
        ),
        localized_text(
            output_language,
            {
                "zh-CN": f"若需形成前三名单，建议继续加入甲方全称、区域或项目代号后重试。",
                "zh-TW": f"若需形成前三名單，建議加入甲方全稱、區域或專案代號後重試。",
                "en": "To derive a top-3 list, add the buyer full name, region, or project code and rerun.",
            },
            "若需形成前三名单，建议继续加入甲方全称、区域或项目代号后重试。",
        ),
    ]
    return _dedupe_strings([templates] + followups, limit)


def _build_dimension_fallback_rows(
    *,
    output_language: str,
    scope_hints: dict[str, object],
    dimension_key: str,
    dimension_label: str,
    limit: int,
) -> list[str]:
    anchor = normalize_text(str(scope_hints.get("anchor_text", "")))
    regions = [normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    industries = [normalize_text(str(item)) for item in scope_hints.get("industries", []) if normalize_text(str(item))]
    clients = [normalize_text(str(item)) for item in scope_hints.get("clients", []) if normalize_text(str(item))]
    region_text = "、".join(regions[:2]) or localized_text(
        output_language,
        {"zh-CN": "重点区域", "zh-TW": "重點區域", "en": "priority regions"},
        "重点区域",
    )
    industry_text = "、".join(industries[:2]) or anchor or localized_text(
        output_language,
        {"zh-CN": "目标行业", "zh-TW": "目標行業", "en": "target sector"},
        "目标行业",
    )
    client_text = "、".join(clients[:2]) or localized_text(
        output_language,
        {"zh-CN": "目标业主类型", "zh-TW": "目標業主類型", "en": "target buyer types"},
        "目标业主类型",
    )

    templates: dict[str, list[str]] = {
        "target_accounts": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"若当前还无法锁定具体甲方，优先在 {region_text} 内跟踪与 {industry_text} 直接相关的业主单位，如数据局、政务服务中心、信息中心、城运中心、行业主管部门或大型平台型国企。",
                    "zh-TW": f"若目前仍無法鎖定具體甲方，優先在 {region_text} 內追蹤與 {industry_text} 直接相關的業主單位，如資料局、政務服務中心、資訊中心、城運中心、行業主管部門或大型平台型國企。",
                    "en": f"If named buyers are still unclear, prioritize buyer entities in {region_text} that are directly tied to {industry_text}, such as data bureaus, digital service centers, information centers, city operation centers, sector regulators, or platform SOEs.",
                },
                f"若当前还无法锁定具体甲方，优先在 {region_text} 内跟踪与 {industry_text} 直接相关的业主单位，如数据局、政务服务中心、信息中心、城运中心、行业主管部门或大型平台型国企。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": f"把搜索范围收敛到 {client_text} + “预算/采购意向/二期/扩容/升级”，优先识别近 12 个月出现过统建、试点、一期上线后二期扩容的业主。",
                    "zh-TW": f"把檢索範圍收斂到 {client_text} +「預算/採購意向/二期/擴容/升級」，優先識別近 12 個月出現過統建、試點、一期上線後二期擴容的業主。",
                    "en": f"Narrow searches to {client_text} plus budget/procurement intention/phase-two expansion terms, prioritizing buyers that showed pilot-to-phase-two expansion in the past 12 months.",
                },
                f"把搜索范围收敛到 {client_text} + “预算/采购意向/二期/扩容/升级”，优先识别近 12 个月出现过统建、试点、一期上线后二期扩容的业主。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": f"即使暂时没有明确公司名，也应优先建立一份 {region_text} {industry_text} 的重点业主名单池，再用招标公告联系人、预算归口和项目代号反推具体甲方。",
                    "zh-TW": f"即使暫時沒有明確公司名，也應優先建立一份 {region_text} {industry_text} 的重點業主名單池，再用招標公告聯絡人、預算歸口與專案代號反推具體甲方。",
                    "en": f"Even without named companies, build a priority buyer pool for {region_text} and {industry_text}, then use tender contacts, budget owners, and project codes to infer specific accounts.",
                },
                f"即使暂时没有明确公司名，也应优先建立一份 {region_text} {industry_text} 的重点业主名单池，再用招标公告联系人、预算归口和项目代号反推具体甲方。",
            ),
        ],
        "target_departments": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"若缺少明确部门名称，优先把 {industry_text} 相关业主拆成四类部门：业务牵头部门、预算审批部门、采购招采部门、实施落地部门，并分别收集公开线索。",
                    "zh-TW": f"若缺少明確部門名稱，優先把 {industry_text} 相關業主拆成四類部門：業務牽頭、預算審批、採購招採、實施落地，並分別收集公開線索。",
                    "en": f"If department names are missing, split buyers tied to {industry_text} into four groups: business lead, budget owner, procurement, and implementation departments, then collect public signals for each.",
                },
                f"若缺少明确部门名称，优先把 {industry_text} 相关业主拆成四类部门：业务牵头部门、预算审批部门、采购招采部门、实施落地部门，并分别收集公开线索。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "优先排查采购中心、招标办、信息中心、数据局/数字化部、科技部、计划财务部、运营管理部等部门是否在公告、工作报告或组织架构中直接出现。",
                    "zh-TW": "優先排查採購中心、招標辦、資訊中心、資料局/數位化部、科技部、計畫財務部、營運管理部等部門是否在公告、工作報告或組織架構中直接出現。",
                    "en": "Prioritize procurement centers, tender offices, information centers, data/digital departments, technology teams, finance/planning, and operations functions in public notices and org disclosures.",
                },
                "优先排查采购中心、招标办、信息中心、数据局/数字化部、科技部、计划财务部、运营管理部等部门是否在公告、工作报告或组织架构中直接出现。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "如果目标是销售推进，先锁定“预算归口 + 技术把关 + 招采执行”三类部门组合，再反推关键联系人。",
                    "zh-TW": "如果目標是銷售推進，先鎖定「預算歸口 + 技術把關 + 招採執行」三類部門組合，再反推關鍵聯絡人。",
                    "en": "For sales progression, first lock the combination of budget owner, technical gatekeeper, and procurement executor, then infer the likely contacts.",
                },
                "如果目标是销售推进，先锁定“预算归口 + 技术把关 + 招采执行”三类部门组合，再反推关键联系人。",
            ),
        ],
        "public_contact_channels": [
            localized_text(
                output_language,
                {
                    "zh-CN": "优先收集公开业务入口：官网“联系我们”、采购/中标公告联系人、服务热线、投资者关系邮箱、政务公开电话。",
                    "zh-TW": "優先收集公開業務入口：官網「聯絡我們」、採購/中標公告聯絡人、服務熱線、投資者關係郵箱、政務公開電話。",
                    "en": "Collect public business channels first: official contact pages, tender contacts, hotlines, investor-relations mailboxes, and public-service phones.",
                },
                "优先收集公开业务入口：官网“联系我们”、采购/中标公告联系人、服务热线、投资者关系邮箱、政务公开电话。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": f"对于 {region_text} 的重点业主，优先从公共资源交易公告和采购意向公告中提取联系人、联系方式和代理机构信息。",
                    "zh-TW": f"對於 {region_text} 的重點業主，優先從公共資源交易公告與採購意向公告中提取聯絡人、聯絡方式與代理機構資訊。",
                    "en": f"For buyers in {region_text}, extract contacts, phone/email clues, and agency information from public procurement and tender notices.",
                },
                f"对于 {region_text} 的重点业主，优先从公共资源交易公告和采购意向公告中提取联系人、联系方式和代理机构信息。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "如果公开联系方式依旧不足，不要停在“无数据”，而应明确下一步去哪个官方公告栏目、哪个官网板块补证据。",
                    "zh-TW": "如果公開聯絡方式仍不足，不要停在「無資料」，而應明確下一步去哪個官方公告欄目、哪個官網板塊補證據。",
                    "en": "If public contact data is still weak, specify exactly which official notice pages or website sections should be checked next instead of returning blank.",
                },
                "如果公开联系方式依旧不足，不要停在“无数据”，而应明确下一步去哪个官方公告栏目、哪个官网板块补证据。",
            ),
        ],
        "budget_signals": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"若暂未拿到明确金额，优先看 {region_text} 内与 {industry_text} 相关的采购意向、预算草案、立项批复、可研批复、财政报告与年报披露。",
                    "zh-TW": f"若暫未拿到明確金額，優先查看 {region_text} 內與 {industry_text} 相關的採購意向、預算草案、立項批復、可研批復、財政報告與年報披露。",
                    "en": f"If exact amounts are missing, inspect procurement intentions, budget drafts, project approvals, feasibility approvals, fiscal reports, and filings tied to {industry_text} in {region_text}.",
                },
                f"若暂未拿到明确金额，优先看 {region_text} 内与 {industry_text} 相关的采购意向、预算草案、立项批复、可研批复、财政报告与年报披露。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "预算判断不要只盯单笔中标额，应同时跟踪总投资、年度预算、二三期扩容预算和运维服务预算。",
                    "zh-TW": "預算判斷不要只盯單筆中標額，應同時追蹤總投資、年度預算、二三期擴容預算與運維服務預算。",
                    "en": "Do not rely only on single award sizes; also track total investment, annual budgets, phase-two/three expansion budgets, and service OPEX budgets.",
                },
                "预算判断不要只盯单笔中标额，应同时跟踪总投资、年度预算、二三期扩容预算和运维服务预算。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "若金额仍缺失，可先给出高价值预算口径：平台统建、算力扩容、应用试点、集成实施、运维续费，这些口径最适合后续销售和投标拆解。",
                    "zh-TW": "若金額仍缺失，可先給出高價值預算口徑：平台統建、算力擴容、應用試點、整合實施、運維續費，這些口徑最適合後續銷售與投標拆解。",
                    "en": "If hard amounts are still missing, output the highest-value budget buckets first: platform build, capacity expansion, pilot applications, integration delivery, and renewal services.",
                },
                "若金额仍缺失，可先给出高价值预算口径：平台统建、算力扩容、应用试点、集成实施、运维续费，这些口径最适合后续销售和投标拆解。",
            ),
        ],
        "competitor_profiles": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"如果竞品公司名不够明确，先围绕 {industry_text} 抽取“高频中标方 / 集成总包 / 平台厂商 / 咨询牵线方”四类主体，再按威胁度排序。",
                    "zh-TW": f"如果競品公司名不夠明確，先圍繞 {industry_text} 抽取「高頻中標方 / 整合總包 / 平台廠商 / 諮詢牽線方」四類主體，再按威脅度排序。",
                    "en": f"If named competitors are still weak, first group entities around {industry_text} into frequent winners, integration primes, platform vendors, and connector advisors, then rank by threat.",
                },
                f"如果竞品公司名不够明确，先围绕 {industry_text} 抽取“高频中标方 / 集成总包 / 平台厂商 / 咨询牵线方”四类主体，再按威胁度排序。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "竞品画像至少要回答三件事：谁拿预算、谁有平台能力、谁掌握地方关系或交付生态。",
                    "zh-TW": "競品畫像至少要回答三件事：誰拿預算、誰有平台能力、誰掌握地方關係或交付生態。",
                    "en": "A usable competitor profile must answer three things: who captures budget, who owns the platform layer, and who controls local relationships or delivery ecosystems.",
                },
                "竞品画像至少要回答三件事：谁拿预算、谁有平台能力、谁掌握地方关系或交付生态。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "若缺少公司名，也应给出相对聚焦的竞对类型组合，方便后续继续查公司名单，而不是停在“证据不足”。",
                    "zh-TW": "若缺少公司名，也應給出相對聚焦的競對類型組合，方便後續繼續查公司名單，而不是停在「證據不足」。",
                    "en": "Even without exact names, provide a focused competitor-type cluster so the next step can resolve company names instead of stopping at 'insufficient evidence'.",
                },
                "若缺少公司名，也应给出相对聚焦的竞对类型组合，方便后续继续查公司名单，而不是停在“证据不足”。",
            ),
        ],
        "ecosystem_partners": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"生态伙伴优先找“能牵线、能带项目、能补关系或交付”的主体，而不是只看纯产品公司；在 {region_text} 内优先排查总包、集成商、咨询顾问、运营商和研究院。",
                    "zh-TW": f"生態夥伴優先找「能牽線、能帶專案、能補關係或交付」的主體，而不是只看純產品公司；在 {region_text} 內優先排查總包、整合商、諮詢顧問、運營商與研究院。",
                    "en": f"For ecosystem partners, prioritize connectors, project carriers, relationship brokers, and delivery enablers over pure product vendors, especially integrators, advisors, operators, and institutes in {region_text}.",
                },
                f"生态伙伴优先找“能牵线、能带项目、能补关系或交付”的主体，而不是只看纯产品公司；在 {region_text} 内优先排查总包、集成商、咨询顾问、运营商和研究院。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "如果短期找不到明确伙伴公司名，也至少应先圈定“咨询牵线方 + 区域总包 + 行业集成商”三种伙伴角色。",
                    "zh-TW": "如果短期找不到明確夥伴公司名，也至少應先圈定「諮詢牽線方 + 區域總包 + 行業整合商」三種夥伴角色。",
                    "en": "If partner names are still unclear, first lock three partner roles: connector advisor, regional prime, and sector integrator.",
                },
                "如果短期找不到明确伙伴公司名，也至少应先圈定“咨询牵线方 + 区域总包 + 行业集成商”三种伙伴角色。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "伙伴筛选标准应包含行业影响力、牵线概率、项目协同能力和地方落地资源，而不是只看技术强弱。",
                    "zh-TW": "夥伴篩選標準應包含行業影響力、牽線機率、專案協同能力與地方落地資源，而不是只看技術強弱。",
                    "en": "Partner screening should prioritize industry influence, introduction probability, delivery synergy, and local access instead of raw product strength alone.",
                },
                "伙伴筛选标准应包含行业影响力、牵线概率、项目协同能力和地方落地资源，而不是只看技术强弱。",
            ),
        ],
    }
    if dimension_key in templates:
        return _dedupe_strings(templates[dimension_key], limit)
    return _scope_insufficient_rows(
        output_language=output_language,
        scope_hints=scope_hints,
        dimension_label=dimension_label,
        limit=limit,
    )


def _ensure_minimum_rows(
    primary: list[str],
    *,
    backup: list[str],
    output_language: str,
    scope_hints: dict[str, object],
    dimension_key: str,
    dimension_label: str,
    min_count: int = 3,
    limit: int = 6,
) -> list[str]:
    rows = _dedupe_strings(primary + backup, limit)
    if len(rows) >= min_count:
        return rows
    fill = _build_dimension_fallback_rows(
        output_language=output_language,
        scope_hints=scope_hints,
        dimension_key=dimension_key,
        dimension_label=dimension_label,
        limit=max(min_count, 3),
    )
    return _dedupe_strings(rows + fill, limit)


def _extract_people_signals(sources: list[SourceDocument], *, limit: int) -> list[str]:
    rows = _extract_matching_sentences(
        sources,
        keywords=("董事长", "总经理", "副总裁", "主任", "局长", "厅长", "书记", "市长", "负责人", "总裁"),
        limit=limit,
    )
    return rows


def _build_source_intelligence(
    sources: list[SourceDocument],
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    scope_hints: dict[str, object],
) -> dict[str, list[str]]:
    return _source_intelligence_build(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        scope_hints=scope_hints,
        deps=SourceIntelligenceDependencies(
            build_theme_terms=_build_theme_terms,
            dedupe_strings=_dedupe_strings,
            rank_org_rows=_rank_org_rows,
            extract_department_rows=_extract_department_rows,
            extract_public_contact_rows=_extract_public_contact_rows,
            build_entity_specific_team_rows=_build_entity_specific_team_rows,
            extract_rank_entity_name=_extract_rank_entity_name,
            extract_money_signals=_extract_money_signals,
            extract_region_distribution=_extract_region_distribution,
            extract_matching_sentences=_extract_matching_sentences,
            extract_key_people_rows=_extract_key_people_rows,
            extract_people_signals=_extract_people_signals,
            ensure_minimum_rows=_ensure_minimum_rows,
            build_industry_methodology_rows=_build_industry_methodology_rows,
        ),
    )


def _merge_result_with_intelligence(
    parsed: ResearchReportResult,
    intelligence: dict[str, list[str]],
) -> ResearchReportResult:
    payload = parsed.model_dump(mode="python")
    grounded_first_fields = {
        "public_contact_channels",
        "budget_signals",
        "project_distribution",
        "strategic_directions",
        "tender_timeline",
        "leadership_focus",
        "benchmark_cases",
        "flagship_products",
        "key_people",
        "five_year_outlook",
        "client_peer_moves",
        "winner_peer_moves",
        "competition_analysis",
    }
    min_count_overrides = {
        "target_accounts": 3,
        "target_departments": 3,
        "public_contact_channels": 3,
        "account_team_signals": 3,
        "budget_signals": 3,
        "project_distribution": 3,
        "strategic_directions": 3,
        "tender_timeline": 3,
        "leadership_focus": 3,
        "ecosystem_partners": 3,
        "competitor_profiles": 3,
        "benchmark_cases": 3,
        "flagship_products": 3,
        "key_people": 3,
        "five_year_outlook": 3,
        "client_peer_moves": 3,
        "winner_peer_moves": 3,
        "competition_analysis": 3,
    }
    for key, values in intelligence.items():
        current = _sanitize_report_field_rows(key, payload.get(key, []))
        sanitized_values = _sanitize_report_field_rows(key, values)
        min_count = min_count_overrides.get(key, 2)
        if key in grounded_first_fields and sanitized_values:
            payload[key] = sanitized_values
            continue
        if len(current) >= min_count:
            payload[key] = current
            continue
        payload[key] = _sanitize_report_field_rows(
            key,
            _dedupe_strings(current + sanitized_values, max(6, min_count)),
        )
    for key, values in list(payload.items()):
        if isinstance(values, list):
            payload[key] = _sanitize_report_field_rows(key, values)
    return ResearchReportResult.model_validate(payload)


def _source_quality_level(sources: list[SourceDocument]) -> str:
    if not sources:
        return "low"
    official_count = sum(1 for source in sources if source.source_tier == "official")
    official_ratio = official_count / max(len(sources), 1)
    if official_count >= 4 or official_ratio >= 0.55:
        return "high"
    if official_count >= 2 or official_ratio >= 0.3:
        return "medium"
    return "low"


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
    if not sources:
        return "low"
    concrete_groups = 0
    for values in (
        parsed.target_accounts,
        parsed.target_departments,
        parsed.public_contact_channels,
        parsed.account_team_signals,
        parsed.budget_signals,
        parsed.project_distribution,
        parsed.strategic_directions,
        parsed.tender_timeline,
        parsed.leadership_focus,
        parsed.ecosystem_partners,
        parsed.competitor_profiles,
        parsed.benchmark_cases,
        parsed.flagship_products,
        parsed.key_people,
        parsed.five_year_outlook,
        parsed.client_peer_moves,
        parsed.winner_peer_moves,
        parsed.competition_analysis,
    ):
        if _concrete_rows(values):
            concrete_groups += 1
    if len(sources) >= 8 and concrete_groups >= 8:
        return "high"
    if len(sources) >= 4 and concrete_groups >= 4:
        return "medium"
    return "low"


def _build_section_evidence_links(
    *,
    section_title: str,
    items: list[str],
    sources: list[SourceDocument],
    limit: int = 3,
) -> tuple[list[ResearchEntityEvidenceOut], dict[str, int], float]:
    return _section_quality_build_evidence_links(
        section_title=section_title,
        items=items,
        sources=sources,
        limit=limit,
        deps=_section_quality_dependencies(),
    )


def _section_signal_quality(
    items: list[str],
    sources: list[SourceDocument],
    *,
    evidence_links: list[ResearchEntityEvidenceOut] | None = None,
    source_tier_counts: dict[str, int] | None = None,
    official_source_ratio: float = 0.0,
) -> tuple[str, str, str]:
    return _section_quality_signal_quality(
        items,
        sources,
        evidence_links=evidence_links,
        source_tier_counts=source_tier_counts,
        official_source_ratio=official_source_ratio,
        deps=_section_quality_dependencies(),
    )


def _section_evidence_quota(section_key: str, items: list[str]) -> int:
    return _section_quality_evidence_quota(section_key, items)


def _section_quota_note(
    *,
    section_title: str,
    evidence_count: int,
    evidence_quota: int,
    official_source_ratio: float,
) -> tuple[bool, int, str]:
    return _section_quality_quota_note(
        section_title=section_title,
        evidence_count=evidence_count,
        evidence_quota=evidence_quota,
        official_source_ratio=official_source_ratio,
    )


def _section_next_verification_steps(
    *,
    section_title: str,
    output_language: str,
    evidence_density: str,
    source_quality: str,
    official_source_ratio: float,
    evidence_count: int,
    evidence_quota: int,
    contradiction_detected: bool,
) -> list[str]:
    return _section_quality_next_verification_steps(
        section_title=section_title,
        output_language=output_language,
        evidence_density=evidence_density,
        source_quality=source_quality,
        official_source_ratio=official_source_ratio,
        evidence_count=evidence_count,
        evidence_quota=evidence_quota,
        contradiction_detected=contradiction_detected,
        deps=_section_quality_dependencies(),
    )


def _section_insufficiency_profile(
    *,
    section_title: str,
    output_language: str,
    evidence_density: str,
    source_quality: str,
    official_source_ratio: float,
    quota_gap: int,
    contradiction_detected: bool,
) -> tuple[str, list[str], str]:
    return _section_quality_insufficiency_profile(
        section_title=section_title,
        output_language=output_language,
        evidence_density=evidence_density,
        source_quality=source_quality,
        official_source_ratio=official_source_ratio,
        quota_gap=quota_gap,
        contradiction_detected=contradiction_detected,
        deps=_section_quality_dependencies(),
    )


def _report_readiness_dependencies() -> ReportReadinessDependencies:
    return ReportReadinessDependencies(
        dedupe_strings=_dedupe_strings,
        sanitize_entity_row=_sanitize_entity_row,
        is_actionable_budget_row=_is_actionable_budget_row,
    )


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


def _build_report_readiness(report: ResearchReportDocument) -> ResearchReportReadinessOut:
    return _report_readiness_build(report, deps=_report_readiness_dependencies())


def _build_technical_appendix(report: ResearchReportDocument) -> ResearchTechnicalAppendixOut:
    return _delivery_materials_build_technical_appendix(report, deps=_delivery_materials_dependencies())


def _build_review_queue(report: ResearchReportDocument) -> list[ResearchReviewQueueItemOut]:
    return _delivery_materials_build_review_queue(report, deps=_delivery_materials_dependencies())


def _enrich_report_for_delivery(report: ResearchReportResponse) -> ResearchReportResponse:
    return _delivery_enrichment_enrich_report(
        report,
        deps=DeliveryEnrichmentDependencies(
            build_report_readiness=_build_report_readiness,
            build_commercial_summary=_build_commercial_summary,
            build_technical_appendix=_build_technical_appendix,
            build_review_queue=_build_review_queue,
            build_research_quality_profile=build_research_quality_profile,
            report_sources_to_source_documents=_report_sources_to_source_documents,
            load_runtime_research_retrieval_index=_load_runtime_research_retrieval_index,
            attach_section_retrieval_packs=attach_section_retrieval_packs,
            build_market_intelligence_pack=build_market_intelligence_pack,
            build_solution_delivery_pack=build_solution_delivery_pack,
            enrich_followup_diagnostics=_enrich_followup_diagnostics,
            apply_report_readiness_guardrails=_apply_report_readiness_guardrails,
        ),
    )


def _apply_report_readiness_guardrails(report: ResearchReportResponse) -> ResearchReportResponse:
    return _delivery_enrichment_apply_guardrails(report)


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
    return _source_diagnostics_build(
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
        deps=SourceDiagnosticsDependencies(
            dedupe_strings=_dedupe_strings,
            retrieval_quality_band=_retrieval_quality_band,
            evidence_mode_from_metrics=_evidence_mode_from_metrics,
        ),
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
    if not sources:
        return topic_anchor_terms[:4]
    haystack = normalize_text(
        " ".join(
            " ".join(
                [
                    source.title,
                    source.snippet,
                    source.excerpt,
                    source.search_query,
                    source.source_label or "",
                    source.domain or "",
                ]
            )
            for source in sources
        )
    ).lower()
    candidates: list[str] = []
    for label in [*(scope_hints.get("industries", []) or []), *(scope_hints.get("clients", []) or []), *(scope_hints.get("regions", []) or [])]:
        normalized = normalize_text(str(label))
        if not normalized:
            continue
        aliases = [normalized, *INDUSTRY_SCOPE_ALIASES.get(normalized, ())]
        if any(normalize_text(alias).lower() in haystack for alias in aliases if normalize_text(alias)):
            candidates.append(normalized)
    if not candidates:
        candidates.extend(topic_anchor_terms[:4])
    return list(dict.fromkeys(item for item in candidates if normalize_text(item)))


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
    title_map = {
        "industry_brief": localized_text(
            output_language,
            {"zh-CN": "行业资讯判断", "zh-TW": "產業資訊判斷", "en": "Industry View"},
            "行业资讯判断",
        ),
        "key_signals": localized_text(
            output_language,
            {"zh-CN": "关键信号", "zh-TW": "關鍵信號", "en": "Key Signals"},
            "关键信号",
        ),
        "policy_and_leadership": localized_text(
            output_language,
            {"zh-CN": "政策与领导信号", "zh-TW": "政策與領導信號", "en": "Policy and Leadership"},
            "政策与领导信号",
        ),
        "commercial_opportunities": localized_text(
            output_language,
            {"zh-CN": "项目与商机判断", "zh-TW": "專案與商機判斷", "en": "Opportunity Map"},
            "项目与商机判断",
        ),
        "solution_design": localized_text(
            output_language,
            {"zh-CN": "解决方案设计建议", "zh-TW": "解決方案設計建議", "en": "Solution Design"},
            "解决方案设计建议",
        ),
        "sales_strategy": localized_text(
            output_language,
            {"zh-CN": "销售策略", "zh-TW": "銷售策略", "en": "Sales Strategy"},
            "销售策略",
        ),
        "bidding_strategy": localized_text(
            output_language,
            {"zh-CN": "投标规划", "zh-TW": "投標規劃", "en": "Bidding Strategy"},
            "投标规划",
        ),
        "outreach_strategy": localized_text(
            output_language,
            {"zh-CN": "陌生拜访建议", "zh-TW": "陌生拜訪建議", "en": "Outreach Strategy"},
            "陌生拜访建议",
        ),
        "ecosystem_strategy": localized_text(
            output_language,
            {"zh-CN": "生态伙伴建议", "zh-TW": "生態夥伴建議", "en": "Ecosystem Strategy"},
            "生态伙伴建议",
        ),
        "target_accounts": localized_text(
            output_language,
            {"zh-CN": "重点甲方与目标客户", "zh-TW": "重點甲方與目標客戶", "en": "Target Accounts"},
            "重点甲方与目标客户",
        ),
        "target_departments": localized_text(
            output_language,
            {"zh-CN": "高概率决策部门", "zh-TW": "高機率決策部門", "en": "Likely Decision Departments"},
            "高概率决策部门",
        ),
        "public_contact_channels": localized_text(
            output_language,
            {"zh-CN": "公开业务联系方式", "zh-TW": "公開業務聯絡方式", "en": "Public Contact Channels"},
            "公开业务联系方式",
        ),
        "account_team_signals": localized_text(
            output_language,
            {"zh-CN": "活跃团队与推进抓手", "zh-TW": "活躍團隊與推進抓手", "en": "Active Teams and Execution Handles"},
            "活跃团队与推进抓手",
        ),
        "budget_signals": localized_text(
            output_language,
            {"zh-CN": "预算与投资信号", "zh-TW": "預算與投資信號", "en": "Budget Signals"},
            "预算与投资信号",
        ),
        "project_distribution": localized_text(
            output_language,
            {"zh-CN": "项目分布与期次判断", "zh-TW": "專案分佈與期次判斷", "en": "Project Distribution"},
            "项目分布与期次判断",
        ),
        "strategic_directions": localized_text(
            output_language,
            {"zh-CN": "战略方向", "zh-TW": "戰略方向", "en": "Strategic Directions"},
            "战略方向",
        ),
        "tender_timeline": localized_text(
            output_language,
            {"zh-CN": "招标时间预测", "zh-TW": "招標時間預測", "en": "Tender Timeline"},
            "招标时间预测",
        ),
        "leadership_focus": localized_text(
            output_language,
            {"zh-CN": "领导近三年关注点", "zh-TW": "領導近三年關注點", "en": "Leadership Focus"},
            "领导近三年关注点",
        ),
        "ecosystem_partners": localized_text(
            output_language,
            {"zh-CN": "活跃生态伙伴", "zh-TW": "活躍生態夥伴", "en": "Ecosystem Partners"},
            "活跃生态伙伴",
        ),
        "competitor_profiles": localized_text(
            output_language,
            {"zh-CN": "竞品公司概况", "zh-TW": "競品公司概況", "en": "Competitor Profiles"},
            "竞品公司概况",
        ),
        "benchmark_cases": localized_text(
            output_language,
            {"zh-CN": "同领域标杆案例", "zh-TW": "同領域標竿案例", "en": "Benchmark Cases"},
            "同领域标杆案例",
        ),
        "flagship_products": localized_text(
            output_language,
            {"zh-CN": "明星产品与方案", "zh-TW": "明星產品與方案", "en": "Flagship Products"},
            "明星产品与方案",
        ),
        "key_people": localized_text(
            output_language,
            {"zh-CN": "关键人物", "zh-TW": "關鍵人物", "en": "Key People"},
            "关键人物",
        ),
        "five_year_outlook": localized_text(
            output_language,
            {"zh-CN": "未来五年演化判断", "zh-TW": "未來五年演化判斷", "en": "Five-Year Outlook"},
            "未来五年演化判断",
        ),
        "client_peer_moves": localized_text(
            output_language,
            {"zh-CN": "甲方同行 Top 3 动态", "zh-TW": "甲方同行 Top 3 動態", "en": "Top 3 Buyer Peer Moves"},
            "甲方同行 Top 3 动态",
        ),
        "winner_peer_moves": localized_text(
            output_language,
            {"zh-CN": "中标方同行 Top 3 动态", "zh-TW": "中標方同行 Top 3 動態", "en": "Top 3 Winner Peer Moves"},
            "中标方同行 Top 3 动态",
        ),
        "competition_analysis": localized_text(
            output_language,
            {"zh-CN": "竞争分析", "zh-TW": "競爭分析", "en": "Competition Analysis"},
            "竞争分析",
        ),
        "risks": localized_text(
            output_language,
            {"zh-CN": "风险提示", "zh-TW": "風險提示", "en": "Risks"},
            "风险提示",
        ),
        "next_actions": localized_text(
            output_language,
            {"zh-CN": "下一步行动", "zh-TW": "下一步行動", "en": "Next Actions"},
            "下一步行动",
        ),
    }
    sections: list[ResearchReportSectionOut] = []
    for key in (
        "industry_brief",
        "key_signals",
        "policy_and_leadership",
        "commercial_opportunities",
        "solution_design",
        "sales_strategy",
        "bidding_strategy",
        "outreach_strategy",
        "ecosystem_strategy",
        "target_accounts",
        "target_departments",
        "public_contact_channels",
        "account_team_signals",
        "budget_signals",
        "project_distribution",
        "strategic_directions",
        "tender_timeline",
        "leadership_focus",
        "ecosystem_partners",
        "competitor_profiles",
        "benchmark_cases",
        "flagship_products",
        "key_people",
        "five_year_outlook",
        "client_peer_moves",
        "winner_peer_moves",
        "competition_analysis",
        "risks",
        "next_actions",
    ):
        items = getattr(result, key)
        if items:
            evidence_links, source_tier_counts, official_source_ratio = _build_section_evidence_links(
                section_title=title_map[key],
                items=items,
                sources=sources,
                limit=3,
            )
            evidence_density, source_quality, evidence_note = _section_signal_quality(
                items,
                sources,
                evidence_links=evidence_links,
                source_tier_counts=source_tier_counts,
                official_source_ratio=official_source_ratio,
            )
            evidence_quota = _section_evidence_quota(key, items)
            meets_evidence_quota, quota_gap, quota_note = _section_quota_note(
                section_title=title_map[key],
                evidence_count=len(evidence_links),
                evidence_quota=evidence_quota,
                official_source_ratio=official_source_ratio,
            )
            confidence_tone, confidence_label, confidence_reason, contradiction_detected, contradiction_note = _section_confidence_profile(
                section_title=title_map[key],
                items=items,
                sources=sources,
                evidence_density=evidence_density,
                source_quality=source_quality,
                official_source_ratio=official_source_ratio,
                meets_evidence_quota=meets_evidence_quota,
                evidence_links=evidence_links,
            )
            next_verification_steps = _section_next_verification_steps(
                section_title=title_map[key],
                output_language=output_language,
                evidence_density=evidence_density,
                source_quality=source_quality,
                official_source_ratio=official_source_ratio,
                evidence_count=len(evidence_links),
                evidence_quota=evidence_quota,
                contradiction_detected=contradiction_detected,
            )
            section_status, insufficiency_reasons, insufficiency_summary = _section_insufficiency_profile(
                section_title=title_map[key],
                output_language=output_language,
                evidence_density=evidence_density,
                source_quality=source_quality,
                official_source_ratio=official_source_ratio,
                quota_gap=quota_gap,
                contradiction_detected=contradiction_detected,
            )
            tinted_evidence_links = [
                link.model_copy(update={"confidence_tone": confidence_tone})
                for link in evidence_links
            ]
            sections.append(
                ResearchReportSectionOut(
                    title=title_map[key],
                    items=items,
                    status=section_status,
                    evidence_density=evidence_density,
                    source_quality=source_quality,
                    confidence_tone=confidence_tone,
                    confidence_label=confidence_label,
                    confidence_reason=confidence_reason,
                    evidence_note=evidence_note,
                    insufficiency_reasons=insufficiency_reasons,
                    insufficiency_summary=insufficiency_summary,
                    source_tier_counts=source_tier_counts,
                    official_source_ratio=official_source_ratio,
                    evidence_links=tinted_evidence_links,
                    evidence_count=len(evidence_links),
                    evidence_quota=evidence_quota,
                    meets_evidence_quota=meets_evidence_quota,
                    quota_gap=quota_gap,
                    quota_note=quota_note,
                    next_verification_steps=next_verification_steps,
                    contradiction_detected=contradiction_detected,
                    contradiction_note=contradiction_note,
                )
            )
    return sections


def _research_section_items(report: ResearchReportDocument, aliases: tuple[str, ...]) -> list[str]:
    normalized_aliases = tuple(alias.lower() for alias in aliases)
    for section in report.sections:
        title = normalize_text(section.title).lower()
        if any(alias in title for alias in normalized_aliases):
            return [normalize_text(item) for item in section.items if normalize_text(item)]
    return []


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
    return ResearchActionCardDependencies(
        dedupe_strings=_dedupe_strings,
        extract_rank_entity_name=_extract_rank_entity_name,
        theme_labels_from_scope=_theme_labels_from_scope,
        looks_like_scope_prompt_noise=_looks_like_scope_prompt_noise,
        looks_like_placeholder_entity_name=_looks_like_placeholder_entity_name,
        looks_like_fragment_entity_name=_looks_like_fragment_entity_name,
        contains_low_value_entity_token=_contains_low_value_entity_token,
        is_trustworthy_scope_client_name=_is_trustworthy_scope_client_name,
        is_theme_aligned_entity_name=_is_theme_aligned_entity_name,
        is_lightweight_entity_name=_is_lightweight_entity_name,
        is_actionable_budget_row=_is_actionable_budget_row,
        is_summary_fact_row=_is_summary_fact_row,
        is_low_signal_execution_report=_is_low_signal_execution_report,
    )


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


def _runtime_consumer_list(payload: ResearchReportRequest, consumer: str, key: str) -> list[str]:
    data = _runtime_consumer_payload(payload, consumer)
    values = data.get(key)
    return _dedupe_strings(values if isinstance(values, list) else [], 8)


def _runtime_consumer_status(payload: ResearchReportRequest, consumer: str) -> str:
    return normalize_text(str(_runtime_consumer_payload(payload, consumer).get("status") or ""))


def _runtime_consumer_warnings(payload: ResearchReportRequest, consumer: str) -> list[str]:
    return _runtime_consumer_list(payload, consumer, "warnings")


def _runtime_strategy_scope_hints(payload: ResearchReportRequest) -> dict[str, object]:
    query_config = _runtime_consumer_effective_config(payload, "query_generation")
    reranker_config = _runtime_consumer_effective_config(payload, "source_reranker")
    query_enabled = bool(query_config.get("enabled") or query_config.get("query_recovery_enabled"))
    reranker_enabled = bool(reranker_config.get("enabled"))
    applied_lanes = _dedupe_strings(
        [
            *_runtime_consumer_list(payload, "query_generation", "applied_lanes"),
            *_runtime_consumer_list(payload, "source_reranker", "applied_lanes"),
        ],
        8,
    )
    fallback_lanes = _dedupe_strings(
        [
            *_runtime_consumer_list(payload, "query_generation", "fallback_lanes"),
            *_runtime_consumer_list(payload, "source_reranker", "fallback_lanes"),
        ],
        8,
    )
    warnings = _dedupe_strings(
        [
            *_runtime_consumer_warnings(payload, "query_generation"),
            *_runtime_consumer_warnings(payload, "source_reranker"),
        ],
        8,
    )
    statuses = [
        _runtime_consumer_status(payload, "query_generation"),
        _runtime_consumer_status(payload, "source_reranker"),
    ]
    runtime_status = "fallback"
    if "degraded" in statuses:
        runtime_status = "degraded"
    elif "ready" in statuses:
        runtime_status = "ready"

    reranker_adapter = normalize_text(str(reranker_config.get("reranker_adapter") or ""))
    reranker_backend = "local"
    if reranker_adapter == "sentence_transformers_cross_encoder":
        reranker_backend = "sentence_transformers"
    elif reranker_adapter and reranker_adapter != "local_rrf":
        reranker_backend = "auto"

    hints: dict[str, object] = {
        "runtime_strategy_status": runtime_status,
        "runtime_strategy_applied_lanes": applied_lanes,
        "runtime_strategy_fallback_lanes": fallback_lanes,
        "runtime_strategy_warnings": warnings,
        "runtime_query_recovery_enabled": query_enabled,
        "runtime_source_reranker_enabled": reranker_enabled,
    }
    if query_enabled:
        hints["runtime_corrective_query_limit"] = _safe_int(
            query_config.get("corrective_query_limit"),
            4,
            minimum=1,
            maximum=12,
        )
        hints["runtime_public_expansion_on_watch"] = bool(query_config.get("public_expansion_on_watch"))
    if reranker_enabled:
        hints.update(
            {
                "enable_cross_encoder_rerank": reranker_adapter != "local_rrf",
                "cross_encoder_rerank": reranker_adapter != "local_rrf",
                "runtime_reranker_adapter": reranker_adapter or "local_rrf",
                "runtime_reranker_backend": reranker_backend,
                "runtime_reranker_top_k": _safe_int(reranker_config.get("recall_at_k"), 5, minimum=3, maximum=20),
                "runtime_reranker_fallback_adapter": normalize_text(str(reranker_config.get("fallback_adapter") or "local_rrf")),
                "runtime_official_source_bias": bool(reranker_config.get("official_source_bias", True)),
            }
        )
    return hints


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


def _enrich_followup_diagnostics(report: ResearchReportResponse) -> ResearchReportResponse:
    return _followup_diagnostics_enrich(report, deps=_followup_diagnostics_dependencies())


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
    return _storage_report_sources_to_source_documents(
        sources,
        classify_source_type=_classify_source_type,
        classify_source_tier=_classify_source_tier,
        derive_source_label=_derive_source_label,
        clean_source_text_for_analysis=_clean_source_text_for_analysis,
        truncate_text=_truncate_text,
        dedupe_sources=_dedupe_sources,
    )


def _stored_report_to_result(report: ResearchReportResponse) -> ResearchReportResult:
    return _storage_stored_report_to_result(
        report,
        research_section_items=_research_section_items,
        sanitize_report_field_rows=_sanitize_report_field_rows,
    )


def _report_intelligence_from_result(report: ResearchReportResponse, result: ResearchReportResult) -> dict[str, list[str]]:
    return {
        "industry_brief": list(result.industry_brief),
        "key_signals": list(result.key_signals),
        "policy_and_leadership": list(result.policy_and_leadership),
        "commercial_opportunities": list(result.commercial_opportunities),
        "solution_design": list(result.solution_design),
        "sales_strategy": list(result.sales_strategy),
        "bidding_strategy": list(result.bidding_strategy),
        "outreach_strategy": list(result.outreach_strategy),
        "ecosystem_strategy": list(result.ecosystem_strategy),
        "target_accounts": _dedupe_strings(
            [
                *result.target_accounts,
                *(normalize_text(item.name) for item in report.top_target_accounts if normalize_text(item.name)),
                *(normalize_text(item.name) for item in report.pending_target_candidates if normalize_text(item.name)),
            ],
            6,
        ),
        "target_departments": list(result.target_departments),
        "public_contact_channels": list(result.public_contact_channels),
        "account_team_signals": list(result.account_team_signals),
        "budget_signals": list(result.budget_signals),
        "project_distribution": list(result.project_distribution),
        "strategic_directions": list(result.strategic_directions),
        "tender_timeline": list(result.tender_timeline),
        "leadership_focus": list(result.leadership_focus),
        "ecosystem_partners": _dedupe_strings(
            [
                *result.ecosystem_partners,
                *(normalize_text(item.name) for item in report.top_ecosystem_partners if normalize_text(item.name)),
                *(normalize_text(item.name) for item in report.pending_partner_candidates if normalize_text(item.name)),
            ],
            6,
        ),
        "competitor_profiles": _dedupe_strings(
            [
                *result.competitor_profiles,
                *(normalize_text(item.name) for item in report.top_competitors if normalize_text(item.name)),
                *(normalize_text(item.name) for item in report.pending_competitor_candidates if normalize_text(item.name)),
            ],
            6,
        ),
        "benchmark_cases": list(result.benchmark_cases),
        "flagship_products": list(result.flagship_products),
        "key_people": list(result.key_people),
        "five_year_outlook": list(result.five_year_outlook),
        "client_peer_moves": list(result.client_peer_moves),
        "winner_peer_moves": list(result.winner_peer_moves),
        "competition_analysis": list(result.competition_analysis),
        "risks": list(result.risks),
        "next_actions": list(result.next_actions),
    }


def _stored_entity_canonicalization_dependencies() -> StoredEntityCanonicalizationDependencies:
    return StoredEntityCanonicalizationDependencies(
        canonical_org_name_from_domain=_canonical_org_name_from_domain,
        resolve_known_org_name=_resolve_known_org_name,
        extract_rank_entity_candidates=_extract_rank_entity_candidates,
        strip_org_public_suffixes=_strip_org_public_suffixes,
        is_plausible_entity_name=_is_plausible_entity_name,
        is_lightweight_entity_name=_is_lightweight_entity_name,
        sanitize_entity_row=_sanitize_entity_row,
        extract_rank_entity_name=_extract_rank_entity_name,
        fallback_entity_name_from_row=_fallback_entity_name_from_row,
        looks_like_fragment_entity_name=_looks_like_fragment_entity_name,
        contains_low_value_entity_token=_contains_low_value_entity_token,
        looks_like_placeholder_entity_name=_looks_like_placeholder_entity_name,
        entity_canonical_key=_entity_canonical_key,
        source_mentions_entity=_source_mentions_entity,
        dedupe_strings=_dedupe_strings,
        looks_like_insufficient=_looks_like_insufficient,
        looks_like_scope_prompt_noise=_looks_like_scope_prompt_noise,
        looks_like_source_artifact_text=_looks_like_source_artifact_text,
        strip_entity_leading_noise=_strip_entity_leading_noise,
        entity_role_fields=ENTITY_ROLE_FIELDS,
    )


def _canonicalize_stored_entity_name(
    value: str,
    *,
    field_key: str,
    scope_hints: dict[str, object],
    source_documents: list[SourceDocument],
    evidence_links: Iterable[object] | None = None,
) -> str:
    return _stored_entity_canonicalization_entity_name(
        value,
        field_key=field_key,
        scope_hints=scope_hints,
        source_documents=source_documents,
        evidence_links=evidence_links,
        deps=_stored_entity_canonicalization_dependencies(),
    )


def _canonicalize_stored_report_entities(
    report: ResearchReportResponse,
    *,
    scope_hints: dict[str, object],
    source_documents: list[SourceDocument],
) -> ResearchReportResponse:
    return _stored_entity_canonicalization_report_entities(
        report,
        scope_hints=scope_hints,
        source_documents=source_documents,
        deps=_stored_entity_canonicalization_dependencies(),
    )


def _canonicalize_stored_result_entities(
    result: ResearchReportResult,
    *,
    scope_hints: dict[str, object],
    source_documents: list[SourceDocument],
) -> ResearchReportResult:
    return _stored_entity_canonicalization_result_entities(
        result,
        scope_hints=scope_hints,
        source_documents=source_documents,
        deps=_stored_entity_canonicalization_dependencies(),
    )


def _clean_candidate_profile_company_names(values: Iterable[str]) -> list[str]:
    return _stored_entity_canonicalization_clean_candidate_names(
        values,
        deps=_stored_entity_canonicalization_dependencies(),
    )


def _is_trustworthy_scope_client_name(value: str, *, theme_labels: list[str] | None = None) -> bool:
    normalized = _strip_entity_leading_noise(value)
    active_theme_labels = [normalize_text(item) for item in theme_labels or [] if normalize_text(item)]
    lowered = normalized.lower()
    if not normalized:
        return False
    if re.search(r"(19|20)\d{2}", normalized):
        return False
    if _looks_like_scope_prompt_noise(normalized):
        return False
    if _looks_like_placeholder_entity_name(normalized):
        return False
    if normalized in {"中国政府", "办公厅", "一网通办", "随申办"}:
        return False
    if any(token in normalized for token in GENERIC_SCOPE_CLIENT_TOKENS):
        return False
    if any(token in normalized for token in ("公开招标公告", "采购项目", "中标结果", "代表样本", "成功举办")):
        return False
    if normalized.startswith(("访", "第", "相关负责人", "对公开市场投资者而言", "在杭州市")):
        return False
    if normalized.startswith(("一家", "一人", "一个", "一种", "是依托", "不仅", "构建", "办公厅", "上海作为")):
        return False
    if (
        any(token in normalized for token in ("和", "及", "与"))
        and any(token in normalized for token in ("全球", "国际", "重点"))
        and not any(token in normalized for token in ("集团", "公司", "局", "委", "办", "中心", "政府"))
    ):
        return False
    if "AI漫剧" in active_theme_labels and any(token in normalized for token in ("政府", "办公厅", "市委", "局", "委", "办")):
        return False
    if "政务云" in active_theme_labels and not any(
        token in normalized
        for token in ("政府", "局", "委", "办", "中心", "集团", "公司", "平台", "城投", "国资", "大数据", "信息")
    ):
        return False
    if normalized in KNOWN_LIGHTWEIGHT_ENTITY_NAMES or normalized in SPECIAL_ENTITY_ALIASES:
        return True
    if any(token in normalized for token in ENTITY_SUFFIX_TOKENS):
        if any(token in lowered for token in ("maas", "iaas", "paas", "saas")) and "公司" in normalized:
            return False
        return True
    return False


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
    return StoredReportRewriteDependencies(
        source_text=_source_text,
        source_theme_match_score=_source_theme_match_score,
        looks_like_insufficient=_looks_like_insufficient,
        dedupe_strings=_dedupe_strings,
        sanitize_entity_row=_sanitize_entity_row,
        build_theme_terms=_build_theme_terms,
        source_supports_target_account=_source_supports_target_account,
        resolved_report_readiness=_resolved_report_readiness,
        is_actionable_budget_row=_is_actionable_budget_row,
        is_summary_fact_row=_is_summary_fact_row,
        looks_like_bad_executive_summary=_looks_like_bad_executive_summary,
        compress_title_segments=_compress_title_segments,
        field_row_noise_tokens=FIELD_ROW_NOISE_TOKENS,
    )


def _stored_source_is_low_signal(
    source: SourceDocument,
    *,
    theme_terms: list[str],
    scope_hints: dict[str, object],
) -> bool:
    return _stored_report_rewrite_source_is_low_signal(
        source,
        theme_terms=theme_terms,
        scope_hints=scope_hints,
        deps=_stored_report_rewrite_dependencies(),
    )


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


def _apply_guarded_rewrite_diagnostics(
    source_diagnostics: ResearchSourceDiagnosticsOut,
    *,
    output_language: str,
    guarded_backlog: bool,
    guarded_rewrite_reasons: Iterable[str],
    supported_target_accounts: Iterable[str],
    unsupported_target_accounts: Iterable[str],
) -> ResearchSourceDiagnosticsOut:
    return _stored_report_rewrite_apply_guarded_diagnostics(
        source_diagnostics,
        output_language=output_language,
        guarded_backlog=guarded_backlog,
        guarded_rewrite_reasons=guarded_rewrite_reasons,
        supported_target_accounts=supported_target_accounts,
        unsupported_target_accounts=unsupported_target_accounts,
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


def _build_guarded_rewrite_title(
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
    output_language: str,
) -> str:
    return _stored_report_rewrite_build_guarded_title(
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
        output_language=output_language,
        deps=_stored_report_rewrite_dependencies(),
    )


def _stored_report_rewrite_orchestration_dependencies() -> StoredReportRewriteOrchestrationDependencies:
    return StoredReportRewriteOrchestrationDependencies(
        report_sources_to_source_documents=_report_sources_to_source_documents,
        infer_input_scope_hints=_infer_input_scope_hints,
        canonicalize_stored_report_entities=_canonicalize_stored_report_entities,
        dedupe_strings=_dedupe_strings,
        canonicalize_stored_entity_name=_canonicalize_stored_entity_name,
        merge_scope_hints=_merge_scope_hints,
        infer_scope_hints=_infer_scope_hints,
        prune_industry_hints=_prune_industry_hints,
        sanitize_entity_row=_sanitize_entity_row,
        build_entity_graph=_build_entity_graph,
        extract_topic_anchor_terms=_extract_topic_anchor_terms,
        collect_matched_theme_labels=_collect_matched_theme_labels,
        clean_candidate_profile_company_names=_clean_candidate_profile_company_names,
        build_source_diagnostics=_build_source_diagnostics,
        resolve_stored_report_target_support=_resolve_stored_report_target_support,
        apply_guarded_rewrite_diagnostics=_apply_guarded_rewrite_diagnostics,
        assess_stored_report_rewrite_mode=_assess_stored_report_rewrite_mode,
        stored_report_to_result=_stored_report_to_result,
        report_intelligence_from_result=_report_intelligence_from_result,
        build_source_intelligence=_build_source_intelligence,
        sanitize_report_field_rows=_sanitize_report_field_rows,
        merge_result_with_intelligence=_merge_result_with_intelligence,
        apply_topic_specific_overrides=_apply_topic_specific_overrides,
        canonicalize_stored_result_entities=_canonicalize_stored_result_entities,
        build_theme_terms=_build_theme_terms,
        rank_report_entities=_entity_ranking_rank_report_entities,
        rank_top_entities=_rank_top_entities,
        filtered_rank_fallback_values=_filtered_rank_fallback_values,
        build_entity_specific_contact_rows=_build_entity_specific_contact_rows,
        build_entity_specific_team_rows=_build_entity_specific_team_rows,
        build_sections=_build_sections,
        evidence_density_level=_evidence_density_level,
        source_quality_level=_source_quality_level,
        source_documents_to_research_source_outputs=_to_research_source_outputs,
        enrich_report_for_delivery=_enrich_report_for_delivery,
        is_low_signal_execution_report=_is_low_signal_execution_report,
        theme_labels_from_scope=_theme_labels_from_scope,
        source_supports_target_account=_source_supports_target_account,
        summary_fact_rows=_summary_fact_rows,
        compress_title_segments=_compress_title_segments,
        scope_anchor_text_segments=_scope_anchor_text_segments,
        build_guarded_rewrite_title=_build_guarded_rewrite_title,
        source_max_age_years=SOURCE_MAX_AGE_YEARS,
    )


def rewrite_stored_research_report(report: ResearchReportResponse) -> ResearchReportResponse:
    return _stored_report_rewrite_rewrite_report(
        report,
        deps=_stored_report_rewrite_orchestration_dependencies(),
    )


def _generation_setup_dependencies() -> ResearchGenerationSetupDependencies:
    return ResearchGenerationSetupDependencies(
        get_settings=get_settings,
        get_llm_service=get_llm_service,
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


def generate_research_report(
    payload: ResearchReportRequest,
    *,
    progress_callback: ResearchProgressCallback | None = None,
    snapshot_callback: ResearchSnapshotCallback | None = None,
) -> ResearchReportResponse:
    setup = _generation_setup_prepare(payload, deps=_generation_setup_dependencies())
    return _generation_workflow_run(
        payload,
        setup=setup,
        progress_callback=progress_callback,
        snapshot_callback=snapshot_callback,
        deps=_generation_workflow_dependencies(),
    )
