import type { AppLanguage } from "@/lib/preferences";
import type {
  ApiResearchDeliveryEvidenceLedger,
  ApiResearchMarketIntelligencePack,
  ApiResearchSolutionDeliveryPack,
} from "@/lib/api/type-contracts/research-delivery";
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
  source_origin?: "search" | "adapter" | "snapshot_cache" | "user_supplied";
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
  search_query_count?: number;
  search_retry_count?: number;
  search_zero_result_query_count?: number;
  search_unique_domain_count?: number;
  fresh_source_count?: number;
  snapshot_recovery_used?: boolean;
  snapshot_recovery_source_count?: number;
  snapshot_recovery_job_id?: string;
  snapshot_recovery_age_hours?: number;
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
  source_topology_counts?: Record<string, number>;
  local_target_proof_count?: number;
  local_decision_source_count?: number;
  external_benchmark_count?: number;
  policy_context_count?: number;
  historical_context_count?: number;
  unsafe_source_count?: number;
  corrective_query_plan?: string[];
  correction_notes?: string[];
  generation_grounding_score?: number;
  response_quality_score?: number;
  generation_provider?: string;
  generation_model?: string;
  generation_status?: "succeeded" | "fallback" | "failed" | "";
  generation_fallback_used?: boolean;
  generation_notes?: string[];
  entity_authenticity_gate_status?: "not_run" | "pass" | "fail";
  entity_authenticity_gate_passed?: boolean;
  entity_authenticity_checked_count?: number;
  entity_authenticity_rejected_count?: number;
  entity_authenticity_repaired_count?: number;
  entity_authenticity_unsupported_count?: number;
  entity_authenticity_rejected_samples?: string[];
  entity_authenticity_repair_samples?: string[];
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

export interface ApiResearchScopeContract {
  framework: "research_scope_contract_v1";
  contract_id: string;
  keyword: string;
  research_focus: string;
  research_mode: "fast" | "deep";
  task_type: "industry_research" | "account_intelligence" | "competitive_research" | "solution_research" | "general_research";
  regions: string[];
  industries: string[];
  clients: string[];
  time_scope: string[];
  must_include_terms: string[];
  generic_terms: string[];
  exclusion_terms: string[];
  industry_methodology: string;
  scope_namespace: string;
  status: "ready" | "needs_clarification";
  reasons: string[];
}

export interface ApiResearchQuestionNode {
  question_id: string;
  axis: string;
  question: string;
  query: string;
  required_source_count: number;
  preferred_source_tiers: string[];
  matched_source_ids: string[];
  accepted_source_count: number;
  official_source_count: number;
  coverage_status: "covered" | "partial" | "uncovered";
  corrective_queries: string[];
}

export interface ApiResearchQuestionTree {
  framework: "research_question_tree_v1";
  root_question: string;
  question_count: number;
  covered_question_count: number;
  partial_question_count: number;
  uncovered_question_count: number;
  coverage_percent: number;
  status: "ready" | "needs_retrieval" | "blocked";
  questions: ApiResearchQuestionNode[];
  corrective_queries: string[];
}

export interface ApiResearchSourceAdmission {
  source_id: string;
  title: string;
  url: string;
  domain: string;
  source_tier: "official" | "media" | "aggregate";
  source_origin?: "search" | "adapter" | "snapshot_cache" | "user_supplied";
  decision: "accepted" | "ambiguous" | "rejected";
  relevance_score: number;
  source_topology?: "local_target_proof" | "local_comparable" | "external_benchmark" | "policy_context" | "historical_context" | "unqualified";
  evidence_lane?: "decision" | "benchmark" | "context" | "rejected";
  local_scope_match?: boolean;
  current_signal?: boolean;
  primary_origin?: boolean;
  url_safe?: boolean;
  snapshot_or_reused?: boolean;
  formal_claim_eligible?: boolean;
  account_pursuit_eligible?: boolean;
  matched_scope_terms: string[];
  missing_scope_terms: string[];
  matched_question_ids: string[];
  reasons: string[];
}

export interface ApiResearchEvidenceGate {
  framework: "research_evidence_gate_v1";
  enforced: boolean;
  status: "evidence_ready" | "evidence_gap" | "blocked_topic_mismatch" | "blocked_runtime_degraded";
  passed: boolean;
  formal_report_allowed: boolean;
  solution_delivery_allowed: boolean;
  minimum_source_count: number;
  minimum_official_source_count: number;
  minimum_unique_domain_count: number;
  minimum_question_coverage_percent: number;
  candidate_source_count: number;
  accepted_source_count: number;
  ambiguous_source_count: number;
  rejected_source_count: number;
  official_source_count: number;
  unique_domain_count: number;
  question_coverage_percent: number;
  local_target_proof_count?: number;
  local_decision_source_count?: number;
  external_benchmark_count?: number;
  policy_context_count?: number;
  historical_context_count?: number;
  unsafe_source_count?: number;
  blockers: string[];
  warnings: string[];
  next_actions: string[];
}

export type ApiResearchInteractionState =
  | "ready"
  | "provisional"
  | "awaiting_user"
  | "recovering"
  | "system_degraded"
  | "blocked";

export type ApiResearchClarificationAction =
  | "submit_answers"
  | "continue_search"
  | "view_provisional"
  | "retry_system";

export interface ApiResearchClarificationOption {
  value: string;
  label: string;
  description?: string;
}

export interface ApiResearchClarificationQuestion {
  question_id: string;
  input_kind: "single_choice" | "multi_choice" | "short_text" | "url_list" | "file_or_url";
  prompt: string;
  reason: string;
  required: boolean;
  placeholder: string;
  accepted_file_types: string[];
  options: ApiResearchClarificationOption[];
}

export interface ApiResearchRecoveryOption {
  action: ApiResearchClarificationAction;
  label: string;
  description: string;
  recommended: boolean;
}

export interface ApiResearchClarificationPacket {
  schema_version: "research_clarification_v1";
  active: boolean;
  interaction_state: ApiResearchInteractionState;
  reason_code: string;
  title: string;
  summary: string;
  accepted_source_count: number;
  minimum_source_count: number;
  evidence_snapshot_digest: string;
  can_view_provisional: boolean;
  formal_delivery_allowed: boolean;
  system_retryable: boolean;
  questions: ApiResearchClarificationQuestion[];
  recovery_options: ApiResearchRecoveryOption[];
  next_steps: string[];
}

export interface ApiResearchCitationGate {
  framework: "research_citation_gate_v1";
  enforced: boolean;
  status: "pass" | "watch" | "fail";
  passed: boolean;
  claim_count: number;
  supported_claim_count: number;
  critical_claim_count: number;
  supported_critical_claim_count: number;
  conflicted_claim_count: number;
  citation_completeness_percent: number;
  critical_claim_coverage_percent: number;
  citation_support_percent: number;
  unsupported_critical_claim_ids: string[];
  blockers: string[];
  warnings: string[];
}

export interface ApiResearchEntityAuthenticityGate {
  framework: "research_entity_authenticity_gate_v1";
  enforced: boolean;
  status: "not_run" | "pass" | "fail";
  passed: boolean;
  checked_count: number;
  accepted_count: number;
  rejected_count: number;
  repaired_count: number;
  unsupported_count: number;
  rejected_samples: string[];
  repair_samples: string[];
  blockers: string[];
  warnings: string[];
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

export interface ApiResearchDeliveryTruth {
  framework: "research_delivery_truth_v1";
  status: "formal" | "provisional" | "awaiting_user" | "system_degraded";
  delivery_mode: "account_pursuit" | "market_scan" | "evidence_recovery";
  formal_delivery_allowed: boolean;
  customer_material_allowed: boolean;
  section_confidence_cap: "high" | "low";
  decisive_reasons: string[];
  blocking_gate_keys: string[];
  next_action: string;
}

export interface ApiResearchAccountPursuitCard {
  account_name: string;
  account_role: string;
  status: "verified" | "market_hypothesis" | "blocked";
  confidence: "high" | "medium" | "low";
  current_signal: string;
  signal_kind: "procurement" | "owner" | "policy" | "unknown";
  procurement_stage: "intent" | "tender" | "award" | "discovery" | "unknown";
  budget_signal: string;
  incumbent_or_partner: string;
  facts: string[];
  inferences: string[];
  evidence_links: ApiResearchEntityEvidence[];
  next_proof_sources: string[];
  next_action: string;
  timebox: string;
}

export interface ApiResearchAccountPursuitPack {
  framework: "account_pursuit_research_v1";
  status: "ready" | "market_scan" | "evidence_recovery";
  summary: string;
  verified_account_count: number;
  cards: ApiResearchAccountPursuitCard[];
  market_scan_actions: string[];
  blockers: string[];
}

export interface ApiResearchCommercialBuyerMapEntry {
  role: string;
  organization: string;
  status: "verified" | "to_verify" | "unknown";
  evidence_links: ApiResearchEntityEvidence[];
  next_proof: string;
}

export interface ApiResearchCommercialBidPack {
  framework: "commercial_bid_engineering_v1";
  status: "ready_for_review" | "market_only" | "blocked";
  account_name: string;
  buyer_map: ApiResearchCommercialBuyerMapEntry[];
  budget_route: string;
  procurement_calendar: string[];
  competitor_or_incumbent_evidence: string[];
  partner_role_fit: string[];
  qualification_plan: string[];
  win_themes: string[];
  loss_risks: string[];
  no_bid_triggers: string[];
  next_actions: string[];
  blockers: string[];
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
  research_scope_contract?: ApiResearchScopeContract;
  research_question_tree?: ApiResearchQuestionTree;
  research_source_admissions?: ApiResearchSourceAdmission[];
  research_evidence_gate?: ApiResearchEvidenceGate;
  interaction_state?: ApiResearchInteractionState;
  clarification_packet?: ApiResearchClarificationPacket;
  research_claim_evidence_ledger?: ApiResearchDeliveryEvidenceLedger;
  research_citation_gate?: ApiResearchCitationGate;
  research_entity_authenticity_gate?: ApiResearchEntityAuthenticityGate;
  entity_graph?: ApiResearchEntityGraph;
  report_readiness?: ApiResearchReportReadiness;
  delivery_truth?: ApiResearchDeliveryTruth;
  account_pursuit_pack?: ApiResearchAccountPursuitPack;
  commercial_bid_pack?: ApiResearchCommercialBidPack;
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
  status: "queued" | "running" | "succeeded" | "needs_evidence" | "failed";
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
  metrics?: ApiResearchRunMetrics | null;
  timeline?: ApiResearchJobTimelineEvent[];
  interaction_state?: ApiResearchInteractionState;
  clarification_packet?: ApiResearchClarificationPacket;
  parent_job_id?: string | null;
  root_job_id?: string | null;
  resumed_child_job_id?: string | null;
  recovery_attempt?: number;
  accepted_snapshot_digest?: string;
  formal_delivery_allowed?: boolean;
}

export interface ApiResearchRunMetrics {
  run_id?: string;
  workflow_engine?: string;
  status?: string;
  cost_ledger?: {
    model_call_count?: number;
    total_tokens?: number;
    estimated_cost_usd?: number | null;
  };
  billing?: {
    status?: string;
    currency?: string;
    quota_units?: number;
    estimated_cost_cny?: number;
    pricing_source?: string;
  };
}

export interface ApiResearchSupplementalDocument {
  file_name: string;
  mime_type: string;
  extracted_text?: string;
  file_base64?: string | null;
  source_url?: string | null;
}

export interface ApiResearchClarificationSubmitPayload {
  action: ApiResearchClarificationAction;
  idempotency_key: string;
  answers: Array<{ question_id: string; values: string[] }>;
  supplemental_urls: string[];
  supplemental_text: string;
  supplemental_documents: ApiResearchSupplementalDocument[];
}

export interface ApiResearchClarificationSubmitResponse {
  parent_job_id: string;
  action: ApiResearchClarificationAction;
  idempotent_replay: boolean;
  child_job?: ApiResearchJob | null;
  parent_job: ApiResearchJob;
}

export interface ApiResearchExperienceFeedback {
  job_id: string;
  score: number;
  reason: string;
  comment: string;
  recorded_at: string;
}

export interface ApiResearchExperienceMetrics {
  generated_at: string;
  sample_size: number;
  completed_count: number;
  ready_count: number;
  provisional_count: number;
  awaiting_user_count: number;
  system_degraded_count: number;
  clarification_started_count: number;
  clarification_resumed_count: number;
  clarification_recovery_count: number;
  clarification_conversion_rate: number;
  stale_recovery_count: number;
  idempotent_replay_count: number;
  median_time_to_result_seconds: number;
  industry_bucket_count: number;
  industry_distribution: Record<string, number>;
  user_supplied_source_count: number;
  provenance_missing_count: number;
  formal_gate_bypass_count: number;
  feedback_count: number;
  average_feedback_score: number;
  too_technical_feedback_rate: number;
  top_feedback_reasons: string[];
}

export interface ApiResearchExperienceReadiness {
  generated_at: string;
  release_version: string;
  status: "pass" | "watch" | "blocked";
  score: number;
  sample_target: number;
  metrics: ApiResearchExperienceMetrics;
  blockers: string[];
  warnings: string[];
  next_actions: string[];
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
