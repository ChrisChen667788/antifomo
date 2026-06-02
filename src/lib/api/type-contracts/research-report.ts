import type { AppLanguage } from "@/lib/preferences";
import type { ApiResearchMarketIntelligencePack, ApiResearchSolutionDeliveryPack } from "@/lib/api/type-contracts/research-delivery";
import type { ApiResearchExperimentLane } from "@/lib/api/type-contracts/research-experiments";
import type { ApiResearchSectionEvidencePack, ApiResearchSectionRetrievalPack } from "@/lib/api/type-contracts/research-retrieval";

export interface ApiResearchSource {
  title: string;
  url: string;
  domain: string | null;
  snippet: string;
  search_query: string;
  source_type: string;
  content_status: string;
  source_label?: string | null;
  source_tier?: "official" | "media" | "aggregate";
}

export interface ApiResearchSourceDiagnostics {
  enabled_source_labels: string[];
  matched_source_labels: string[];
  scope_regions: string[];
  scope_industries: string[];
  scope_clients: string[];
  guarded_backlog: boolean;
  guarded_rewrite_reasons: string[];
  guarded_rewrite_reason_labels: string[];
  supported_target_accounts: string[];
  unsupported_target_accounts: string[];
  source_type_counts: Record<string, number>;
  source_tier_counts: Record<string, number>;
  adapter_hit_count: number;
  search_hit_count: number;
  recency_window_years: number;
  filtered_old_source_count: number;
  filtered_region_conflict_count: number;
  retained_source_count: number;
  strict_topic_source_count: number;
  topic_anchor_terms: string[];
  matched_theme_labels: string[];
  retrieval_quality: "low" | "medium" | "high";
  evidence_mode: "strong" | "provisional" | "fallback";
  evidence_mode_label: string;
  strict_match_ratio: number;
  official_source_ratio: number;
  unique_domain_count: number;
  normalized_entity_count: number;
  normalized_target_count: number;
  normalized_competitor_count: number;
  normalized_partner_count: number;
  expansion_triggered: boolean;
  corrective_triggered: boolean;
  correction_status?: "ready" | "needs_filtering" | "needs_expansion";
  retrieval_relevance_score?: number;
  accepted_source_count?: number;
  ambiguous_source_count?: number;
  rejected_source_count?: number;
  corrective_query_plan?: string[];
  correction_notes?: string[];
  generation_grounding_score?: number;
  response_quality_score?: number;
  supported_claims?: string[];
  unsupported_claims?: string[];
  generation_review_notes?: string[];
  reranker_used?: boolean;
  reranker_model?: string;
  reranker_top_k?: number;
  reranker_backend?: string;
  reranker_notes?: string[];
  candidate_profile_companies: string[];
  candidate_profile_hit_count: number;
  candidate_profile_official_hit_count: number;
  candidate_profile_source_labels: string[];
  quality_expansion_triggered?: boolean;
  quality_expansion_rounds?: number;
  quality_expansion_before_score?: number;
  quality_expansion_after_score?: number;
  quality_expansion_added_source_count?: number;
  quality_expansion_query_plan?: string[];
  quality_expansion_notes?: string[];
  strategy_model_used: boolean;
  strategy_scope_summary: string;
  strategy_query_expansion_count: number;
  strategy_exclusion_terms: string[];
  runtime_strategy_status?: "ready" | "degraded" | "fallback" | "";
  runtime_strategy_applied_lanes?: Array<ApiResearchExperimentLane["key"]>;
  runtime_strategy_fallback_lanes?: Array<ApiResearchExperimentLane["key"]>;
  runtime_strategy_warnings?: string[];
  runtime_query_recovery_enabled?: boolean;
  runtime_source_reranker_enabled?: boolean;
  pipeline_summary: string;
  pipeline_stages: Array<{
    key: "fetch" | "clean" | "analyze";
    label: string;
    value: number;
    summary: string;
  }>;
}

export interface ApiResearchConnectorStatus {
  key: string;
  label: string;
  status: "active" | "available" | "authorization_required";
  detail: string;
  requires_authorization: boolean;
}

export interface ApiResearchEntityEvidence {
  title: string;
  url: string;
  source_label?: string | null;
  source_tier?: "official" | "media" | "aggregate";
  anchor_text?: string | null;
  excerpt?: string;
  confidence_tone?: "high" | "low" | "conflict";
}

export interface ApiResearchScoreFactor {
  label: string;
  score: number;
  note: string;
}

export interface ApiResearchRankedEntity {
  name: string;
  score: number;
  reasoning: string;
  entity_mode?: "instance" | "pending";
  score_breakdown: ApiResearchScoreFactor[];
  evidence_links: ApiResearchEntityEvidence[];
}

export interface ApiResearchNormalizedEntity {
  canonical_name: string;
  entity_type: "target" | "competitor" | "partner" | "generic";
  aliases: string[];
  source_count: number;
  source_tier_counts: Record<string, number>;
  evidence_links: ApiResearchEntityEvidence[];
}

export interface ApiResearchEntityGraph {
  entities: ApiResearchNormalizedEntity[];
  target_entities: ApiResearchNormalizedEntity[];
  competitor_entities: ApiResearchNormalizedEntity[];
  partner_entities: ApiResearchNormalizedEntity[];
}

export interface ApiResearchSection {
  title: string;
  items: string[];
  status?: "ready" | "degraded" | "needs_evidence";
  evidence_density?: "low" | "medium" | "high";
  source_quality?: "low" | "medium" | "high";
  confidence_tone?: "high" | "low" | "conflict";
  confidence_label?: string;
  confidence_reason?: string;
  evidence_note?: string;
  insufficiency_reasons?: string[];
  insufficiency_summary?: string;
  source_tier_counts?: Record<string, number>;
  official_source_ratio?: number;
  evidence_links?: ApiResearchEntityEvidence[];
  evidence_count?: number;
  evidence_quota?: number;
  meets_evidence_quota?: boolean;
  quota_gap?: number;
  quota_note?: string;
  next_verification_steps?: string[];
  contradiction_detected?: boolean;
  contradiction_note?: string;
}

export interface ApiResearchReportReadiness {
  status: "ready" | "degraded" | "needs_evidence";
  score: number;
  actionable: boolean;
  evidence_gate_passed: boolean;
  reasons: string[];
  missing_axes: string[];
  next_verification_steps: string[];
}

export interface ApiResearchCommercialSummary {
  account_focus: string[];
  budget_signal: string;
  entry_window: string;
  competition_or_partner: string;
  next_action: string;
}

export interface ApiResearchScenario {
  name: string;
  summary: string;
  implication: string;
}

export interface ApiResearchTechnicalAppendix {
  key_assumptions: string[];
  scenario_comparison: ApiResearchScenario[];
  limitations: string[];
  technical_appendix: string[];
}

export interface ApiResearchReviewQueueItem {
  id: string;
  section_title: string;
  severity: "high" | "medium" | "low";
  summary: string;
  recommended_action: string;
  evidence_links: ApiResearchEntityEvidence[];
  resolution_status: "open" | "resolved" | "deferred";
  resolution_note: string;
  resolved_at?: string | null;
}

export interface ApiResearchQualityDimension {
  key: "professional_rigor" | "intelligence_value" | "actionability" | "evidence_strength";
  label: string;
  score: number;
  status: "strong" | "usable" | "weak";
  summary: string;
  evidence: string[];
  next_steps: string[];
}

export interface ApiResearchMethodologyAxis {
  key: string;
  label: string;
  checkpoints: string[];
  passed: string[];
  missing: string[];
  implication: string;
}

export interface ApiResearchIndustryMethodology {
  industry_key: string;
  industry_label: string;
  framework_name: string;
  summary: string;
  axes: ApiResearchMethodologyAxis[];
  recommended_questions: string[];
}

export interface ApiResearchQualityProfile {
  overall_score: number;
  status: "high_value" | "usable" | "needs_evidence";
  headline: string;
  professional_score: number;
  intelligence_value_score: number;
  actionability_score: number;
  evidence_score: number;
  dimensions: ApiResearchQualityDimension[];
  methodology: ApiResearchIndustryMethodology;
  section_evidence_packs: ApiResearchSectionEvidencePack[];
  section_retrieval_packs: ApiResearchSectionRetrievalPack[];
  strengths: string[];
  gaps: string[];
  next_actions: string[];
}

export interface ApiResearchReportEvaluationMetric {
  key: string;
  label: string;
  score: number;
  threshold: number;
  status: "pass" | "watch" | "fail";
  summary: string;
  evidence: string[];
  gaps: string[];
  improvement_actions: string[];
}

export interface ApiResearchReportSelfImprovement {
  triggered: boolean;
  round_count: number;
  strategies: string[];
  before_score: number;
  after_score: number;
  actions: string[];
  added_entities: string[];
  corrective_queries: string[];
  notes: string[];
}

export interface ApiResearchReportEvaluationProfile {
  framework: "deepeval_style_custom";
  framework_label: string;
  overall_score: number;
  status: "pass" | "watch" | "fail";
  entity_recall_score: number;
  procurement_entity_recall_score: number;
  metrics: ApiResearchReportEvaluationMetric[];
  recalled_entities: string[];
  missing_entities: string[];
  procurement_entities: string[];
  missing_procurement_entities: string[];
  corrective_queries: string[];
  self_improvement: ApiResearchReportSelfImprovement;
}

export interface ApiResearchFollowupContext {
  followup_report_title: string;
  followup_report_summary: string;
  supplemental_context: string;
  supplemental_evidence: string;
  supplemental_requirements: string;
}

export interface ApiResearchFollowupSectionImpact {
  section_title: string;
  status: "ready" | "degraded" | "needs_evidence";
  impact_score: number;
  impact_label: "high" | "medium" | "low";
  reason: string;
  matched_inputs: string[];
  retrieval_support_score: number;
  retrieval_hit_count: number;
  official_hit_count: number;
  next_action: string;
}

export interface ApiResearchFollowupDiagnostics {
  enabled: boolean;
  input_sections: string[];
  planning_focus: string;
  summary: string;
  scope_rebuilt: boolean;
  query_decomposition_applied: boolean;
  decomposition_queries: string[];
  rebuilt_regions: string[];
  rebuilt_industries: string[];
  rebuilt_clients: string[];
  rebuilt_company_anchors: string[];
  rebuilt_must_include_terms: string[];
  rebuilt_exclusion_terms: string[];
  title_resolution: "baseline" | "reused" | "corrected";
  summary_resolution: "baseline" | "reused" | "corrected";
  impacted_sections: ApiResearchFollowupSectionImpact[];
}

export interface ApiResearchReport {
  keyword: string;
  research_focus?: string | null;
  followup_context?: ApiResearchFollowupContext;
  followup_diagnostics?: ApiResearchFollowupDiagnostics;
  output_language: AppLanguage;
  research_mode?: "fast" | "deep";
  report_title: string;
  executive_summary: string;
  consulting_angle: string;
  sections: ApiResearchSection[];
  target_accounts: string[];
  top_target_accounts: ApiResearchRankedEntity[];
  pending_target_candidates: ApiResearchRankedEntity[];
  target_departments: string[];
  public_contact_channels: string[];
  account_team_signals: string[];
  budget_signals: string[];
  project_distribution: string[];
  strategic_directions: string[];
  tender_timeline: string[];
  leadership_focus: string[];
  ecosystem_partners: string[];
  top_ecosystem_partners: ApiResearchRankedEntity[];
  pending_partner_candidates: ApiResearchRankedEntity[];
  competitor_profiles: string[];
  top_competitors: ApiResearchRankedEntity[];
  pending_competitor_candidates: ApiResearchRankedEntity[];
  benchmark_cases: string[];
  flagship_products: string[];
  key_people: string[];
  five_year_outlook: string[];
  client_peer_moves: string[];
  winner_peer_moves: string[];
  competition_analysis: string[];
  source_count: number;
  evidence_density: "low" | "medium" | "high";
  source_quality: "low" | "medium" | "high";
  query_plan: string[];
  sources: ApiResearchSource[];
  source_diagnostics?: ApiResearchSourceDiagnostics;
  entity_graph?: ApiResearchEntityGraph;
  report_readiness?: ApiResearchReportReadiness;
  commercial_summary?: ApiResearchCommercialSummary;
  technical_appendix?: ApiResearchTechnicalAppendix;
  review_queue?: ApiResearchReviewQueueItem[];
  quality_profile?: ApiResearchQualityProfile;
  evaluation_profile?: ApiResearchReportEvaluationProfile;
  market_intelligence?: ApiResearchMarketIntelligencePack;
  solution_delivery_pack?: ApiResearchSolutionDeliveryPack;
  generated_at: string;
}

export interface ApiResearchJob {
  id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  keyword: string;
  research_focus?: string | null;
  output_language: AppLanguage;
  include_wechat: boolean;
  research_mode?: "fast" | "deep";
  max_sources: number;
  deep_research: boolean;
  progress_percent: number;
  stage_key: string;
  stage_label: string;
  message: string;
  estimated_seconds?: number | null;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  report?: ApiResearchReport | null;
  timeline?: ApiResearchJobTimelineEvent[];
}

export interface ApiResearchJobTimelineEvent {
  stage_key: string;
  stage_label: string;
  message: string;
  progress_percent: number;
  created_at: string;
}

export interface ApiResearchConversationMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  message_type: string;
  content: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface ApiResearchConversation {
  id: string;
  topic_id?: string | null;
  job_id?: string | null;
  title: string;
  status: string;
  context_payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  messages: ApiResearchConversationMessage[];
}

export interface ApiMobileDailyBriefItem {
  id: string;
  title: string;
  source_domain: string;
  summary: string;
  action_suggestion: string;
  score_value?: number | null;
  source_url?: string | null;
}

export interface ApiMobileDailyBriefWatchlistChange {
  id: string;
  change_type: string;
  summary: string;
  severity: string;
  created_at?: string | null;
}

export interface ApiMobileDailyBrief {
  snapshot_id: string;
  brief_date: string;
  headline: string;
  summary: string;
  top_items: ApiMobileDailyBriefItem[];
  watchlist_changes: ApiMobileDailyBriefWatchlistChange[];
  generated_at?: string | null;
  audio_status: "pending" | "ready" | "unavailable";
  audio_url?: string | null;
  audio_script?: string | null;
}

export interface ApiResearchActionCard {
  action_type: string;
  priority: string;
  title: string;
  summary: string;
  recommended_steps: string[];
  evidence: string[];
  target_persona?: string;
  execution_window?: string;
  deliverable?: string;
}

export interface ApiResearchActionPlan {
  keyword: string;
  generated_at: string;
  cards: ApiResearchActionCard[];
}

export interface ApiResearchSourceSettings {
  enable_jianyu_tender_feed: boolean;
  enable_yuntoutiao_feed: boolean;
  enable_ggzy_feed: boolean;
  enable_cecbid_feed: boolean;
  enable_ccgp_feed: boolean;
  enable_gov_policy_feed: boolean;
  enable_local_ggzy_feed: boolean;
  enable_curated_wechat_channels: boolean;
  enabled_source_labels: string[];
  connector_statuses: ApiResearchConnectorStatus[];
  updated_at?: string | null;
}

export interface ApiResearchActionSaveResponse {
  created_count: number;
  items: Array<{
    entry_id: string;
    title: string;
    created_at: string;
  }>;
}

export interface ApiResearchSaveResponse {
  entry_id: string;
  title: string;
  created_at: string;
}
