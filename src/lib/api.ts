import type { AppLanguage } from "@/lib/preferences";

export type FeedbackType =
  | "ignore"
  | "like"
  | "save"
  | "open_detail"
  | "inaccurate";

export interface ApiItem {
  id: string;
  source_type: string;
  source_url: string | null;
  source_domain: string | null;
  title: string | null;
  raw_content: string | null;
  clean_content: string | null;
  short_summary: string | null;
  long_summary: string | null;
  score_value: number | null;
  action_suggestion: string | null;
  output_language?: AppLanguage;
  ingest_route?: string | null;
  content_acquisition_status?: string | null;
  content_acquisition_note?: string | null;
  resolved_from_url?: string | null;
  fallback_used?: boolean;
  status: string;
  processing_error: string | null;
  created_at: string;
  recommendation_score?: number | null;
  recommendation_bucket?: string | null;
  recommendation_reason?: string[];
  topic_match_score?: number | null;
  source_match_score?: number | null;
  preference_version?: string | null;
  matched_preferences?: string[];
  why_recommended?: string[];
  tags?: Array<{ tag_name: string }>;
}

export interface ApiPreferenceScore {
  key: string;
  preference_score: number;
  mapped_score: number;
  updated_at?: string | null;
}

export interface ApiPreferenceSummary {
  user_id: string;
  generated_at: string;
  preference_version: string;
  feedback_total: number;
  last_feedback_at?: string | null;
  recent_feedback_counts: Record<string, number>;
  top_tags: ApiPreferenceScore[];
  top_domains: ApiPreferenceScore[];
  snapshot_id?: string | null;
}

export interface ApiPreferenceBoostResponse {
  dimension: "topic" | "source";
  key: string;
  delta: number;
  updated_score: number;
  summary: ApiPreferenceSummary;
}

export interface ApiBatchCreateResult {
  source_url: string;
  status: "created" | "skipped" | "invalid";
  item_id?: string | null;
  detail?: string | null;
}

export interface ApiBatchCreateResponse {
  total: number;
  created: number;
  skipped: number;
  invalid: number;
  results: ApiBatchCreateResult[];
}

export interface ApiTask {
  id: string;
  task_type: string;
  status: string;
  session_id?: string | null;
  input_payload?: Record<string, unknown> | null;
  output_payload?: {
    content?: string;
    [key: string]: unknown;
  } | null;
  error_message?: string | null;
}

export interface ApiCollectorIngestAttempt {
  id: string;
  item_id: string;
  source_url?: string | null;
  source_type: string;
  route_type: string;
  resolver?: string | null;
  attempt_status: string;
  error_code?: string | null;
  error_detail?: string | null;
  body_source?: string | null;
  body_length?: number | null;
  confidence?: number | null;
  created_at: string;
}

export interface ApiItemDiagnostics {
  item_id: string;
  source_type: string;
  source_url?: string | null;
  ingest_route: string;
  resolved_from_url?: string | null;
  content_acquisition_status: string;
  content_acquisition_note?: string | null;
  fallback_used: boolean;
  body_source?: string | null;
  processing_status: string;
  processing_error?: string | null;
  latest_attempt?: ApiCollectorIngestAttempt | null;
  attempt_count: number;
}

export interface ApiSessionArtifactItem {
  id: string;
  item_id?: string | null;
  position: number;
  included_reason?: string | null;
  title_snapshot: string;
  source_url_snapshot?: string | null;
  created_at: string;
}

export interface ApiSessionArtifact {
  id: string;
  work_task_id: string;
  session_id?: string | null;
  artifact_type: string;
  markdown: string;
  created_at: string;
  items: ApiSessionArtifactItem[];
}

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
  candidate_profile_companies: string[];
  candidate_profile_hit_count: number;
  candidate_profile_official_hit_count: number;
  candidate_profile_source_labels: string[];
  strategy_model_used: boolean;
  strategy_scope_summary: string;
  strategy_query_expansion_count: number;
  strategy_exclusion_terms: string[];
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
  evidence_density?: "low" | "medium" | "high";
  source_quality?: "low" | "medium" | "high";
  evidence_note?: string;
}

export interface ApiResearchReport {
  keyword: string;
  research_focus?: string | null;
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

export interface ApiResearchTrackingTopicReportVersion {
  id: string;
  entry_id?: string | null;
  title: string;
  refreshed_at: string;
  source_count: number;
  evidence_density: "low" | "medium" | "high";
  source_quality: "low" | "medium" | "high";
  new_target_count: number;
  new_competitor_count: number;
  new_budget_signal_count: number;
}

export interface ApiResearchTrackingTopicVersionDetail {
  id: string;
  topic_id: string;
  entry_id?: string | null;
  title: string;
  refreshed_at: string;
  source_count: number;
  evidence_density: "low" | "medium" | "high";
  source_quality: "low" | "medium" | "high";
  refresh_note?: string | null;
  new_targets: string[];
  new_competitors: string[];
  new_budget_signals: string[];
  report?: ApiResearchReport | null;
  action_cards?: ApiResearchActionCard[];
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
  enabled_source_labels: string[];
  connector_statuses: ApiResearchConnectorStatus[];
  updated_at?: string | null;
}

export interface ApiResearchSavedView {
  id: string;
  name: string;
  query: string;
  filter_mode: "all" | "reports" | "actions";
  perspective: "all" | "regional" | "client_followup" | "bidding" | "ecosystem";
  region_filter: string;
  industry_filter: string;
  action_type_filter: string;
  focus_only: boolean;
  created_at: string;
  updated_at: string;
}

export interface ApiResearchTrackingTopic {
  id: string;
  name: string;
  keyword: string;
  research_focus: string;
  perspective: "all" | "regional" | "client_followup" | "bidding" | "ecosystem";
  region_filter: string;
  industry_filter: string;
  notes: string;
  created_at: string;
  updated_at: string;
  last_refreshed_at?: string | null;
  last_refresh_status?: "idle" | "running" | "succeeded" | "failed";
  last_refresh_error?: string | null;
  last_refresh_note?: string | null;
  last_refresh_new_targets?: string[];
  last_refresh_new_competitors?: string[];
  last_refresh_new_budget_signals?: string[];
  last_report_entry_id?: string | null;
  last_report_title?: string | null;
  report_history?: ApiResearchTrackingTopicReportVersion[];
}

export interface ApiResearchWatchlistChangeEvent {
  id: string;
  watchlist_id: string;
  change_type: "added" | "removed" | "rewritten" | "risk";
  summary: string;
  payload: Record<string, unknown>;
  severity: "low" | "medium" | "high";
  created_at: string;
}

export interface ApiResearchWatchlist {
  id: string;
  tracking_topic_id?: string | null;
  name: string;
  watch_type: "topic" | "company" | "policy" | "competitor";
  query: string;
  research_focus: string;
  perspective: "all" | "regional" | "client_followup" | "bidding" | "ecosystem";
  region_filter: string;
  industry_filter: string;
  alert_level: "low" | "medium" | "high";
  schedule: string;
  status: "active" | "paused";
  last_checked_at?: string | null;
  created_at: string;
  updated_at: string;
  latest_changes?: ApiResearchWatchlistChangeEvent[];
}

export interface ApiResearchWatchlistRefresh {
  watchlist: ApiResearchWatchlist;
  topic: ApiResearchTrackingTopic;
  report: ApiResearchReport;
  changes: ApiResearchWatchlistChangeEvent[];
}

export interface ApiResearchEntityRelation {
  id: string;
  to_entity_id: string;
  relation_type: string;
  weight: number;
  evidence_payload: Record<string, unknown>;
}

export interface ApiResearchEntityDetail {
  id: string;
  canonical_name: string;
  entity_type: "target" | "competitor" | "partner" | "generic";
  region_hint: string;
  industry_hint: string;
  aliases: string[];
  evidence_links: ApiResearchEntityEvidence[];
  linked_topic_ids: string[];
  relations: ApiResearchEntityRelation[];
  profile_payload: Record<string, unknown>;
  last_seen_at?: string | null;
  updated_at: string;
}

export interface ApiResearchWorkspace {
  saved_views: ApiResearchSavedView[];
  tracking_topics: ApiResearchTrackingTopic[];
}

export interface ApiResearchTrackingTopicRefresh {
  topic: ApiResearchTrackingTopic;
  report: ApiResearchReport;
  saved_entry_id?: string | null;
  saved_entry_title?: string | null;
  report_version_id?: string | null;
  persistence_status?: "persisted" | "failed";
  persistence_error?: string | null;
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

export interface ApiItemInterpretation {
  item_id: string;
  output_language: AppLanguage;
  insight_title: string;
  expert_take: string;
  key_signals: string[];
  knowledge_note: string;
}

export interface ApiKnowledgeEntry {
  id: string;
  item_id: string | null;
  title: string;
  content: string;
  source_domain: string | null;
  metadata_payload?: Record<string, unknown> | null;
  collection_name?: string | null;
  is_pinned?: boolean;
  is_focus_reference?: boolean;
  created_at: string;
  updated_at?: string | null;
}

export interface ApiKnowledgeMarkdown {
  filename: string;
  content: string;
}

export interface ApiKnowledgeMergePreview {
  title: string;
  count: number;
  titles: string[];
  more_count: number;
  inherit_pinned: boolean;
  inherit_focus_reference: boolean;
  inherit_collection: string | null;
  ready: boolean;
}

export interface ApiKnowledgeRule {
  enabled: boolean;
  min_score_value: number;
  archive_on_like: boolean;
  archive_on_save: boolean;
}

export interface ApiFeedbackResponse {
  item_id: string;
  feedback_type: FeedbackType;
  status: string;
  knowledge_entry_id?: string | null;
  knowledge_status?: "created" | "existing" | null;
  knowledge_trigger?: FeedbackType | null;
  knowledge_threshold?: number | null;
  knowledge_score_value?: number | null;
}

export interface LLMConfig {
  llm_provider: string;
  llm_fallback_to_mock: boolean;
  openai_base_url: string;
  openai_model: string;
  openai_temperature: number;
  openai_timeout_seconds: number;
  openai_api_key_configured: boolean;
  strategy_openai_base_url?: string;
  strategy_openai_model?: string;
  strategy_openai_timeout_seconds?: number;
  strategy_openai_api_key_configured?: boolean;
}

export interface LLMDryRunResult {
  provider_requested: string;
  provider_used: string;
  fallback_used: boolean;
  raw_preview: string;
  parsed_preview: Record<string, unknown>;
  ok: boolean;
  error?: string | null;
}

export interface WorkBuddyHealth {
  status: string;
  signature_required: boolean;
  integration_mode?: string;
  official_tencent_connected?: boolean;
  provider_label?: string;
  requested_mode?: string;
  official_cli_detected?: boolean;
  official_cli_version?: string | null;
  official_cli_authenticated?: boolean;
  official_cli_auth_detail?: string | null;
  official_gateway_configured?: boolean;
  official_gateway_reachable?: boolean;
  official_gateway_url?: string | null;
  official_gateway_status_code?: number | null;
  official_gateway_detail?: string | null;
  active_roles?: string[];
}

export interface WorkBuddyWebhookResponse {
  accepted: boolean;
  event_type: "ping" | "create_task";
  request_id: string | null;
  message: string;
  signature_check: string | null;
  task: ApiTask | null;
  callback: {
    attempted: boolean;
    ok: boolean | null;
    status_code: number | null;
    detail: string | null;
  };
}

export interface ApiSessionMetrics {
  new_content_count: number;
  deep_read_count: number;
  later_count: number;
  skip_count: number;
}

export interface ApiSessionItem {
  id: string;
  title: string | null;
  source_domain: string | null;
  short_summary: string | null;
  action_suggestion: string | null;
  score_value: number | null;
  tags: string[];
}

export interface ApiSession {
  id: string;
  goal_text: string | null;
  output_language?: AppLanguage;
  duration_minutes: number;
  start_time: string;
  end_time?: string | null;
  status: string;
  summary_text: string | null;
  metrics: ApiSessionMetrics;
  items: ApiSessionItem[];
}

export interface ApiHealth {
  status: string;
}

export interface ApiTodoCalendarEvent {
  title: string;
  notes: string;
  start_time: string;
  end_time: string;
}

export interface ApiTodoCalendarPreview {
  calendar_name: string;
  summary_title: string;
  task_count: number;
  tasks: string[];
  events: ApiTodoCalendarEvent[];
  markdown: string;
}

export interface ApiTodoCalendarImportResult {
  calendar_name: string;
  imported_count: number;
  imported_titles: string[];
}

export interface FocusAssistantAction {
  key:
    | "reading_digest"
    | "session_markdown_summary"
    | "todo_draft"
    | "focus_reference_bundle"
    | "personal_wechat_auto_send";
  title: string;
  description: string;
  available: boolean;
  reason?: string | null;
  task_type?: string | null;
  session_required?: boolean;
  steps: string[];
  handoff_prompt?: string | null;
}

export interface FocusAssistantPlan {
  goal_text?: string | null;
  duration_minutes?: number | null;
  output_language: AppLanguage;
  latest_session_id?: string | null;
  latest_session_status?: string | null;
  focus_reference_count: number;
  focus_reference_ids: string[];
  focus_reference_titles: string[];
  summary: string;
  actions: FocusAssistantAction[];
  blocked_actions: FocusAssistantAction[];
  guardrails: string[];
}

export interface FocusAssistantExecution {
  accepted: boolean;
  action_key: FocusAssistantAction["key"];
  channel_used: "workbuddy" | "direct";
  message: string;
  task: ApiTask | null;
}

export interface CollectorStatus {
  user_id: string;
  now: string;
  last_24h_total: number;
  last_24h_ready: number;
  last_24h_processing: number;
  last_24h_failed: number;
  last_24h_ocr_items: number;
  latest_item_at: string | null;
}

export interface CollectorDaemonStatus {
  running: boolean;
  pid: number | null;
  pid_from_file: number | null;
  pid_file_present: boolean;
  uptime_seconds: number | null;
  last_report_at: string | null;
  last_daily_summary_at: string | null;
  log_file: string;
  log_size_bytes: number;
  source_file_count: number;
  log_tail: string[];
}

export interface CollectorDaemonCommandResult {
  action: "start" | "stop" | "run_once";
  ok: boolean;
  message: string;
  status: CollectorDaemonStatus;
  output: string | null;
}

export interface WechatAgentStatus {
  running: boolean;
  pid: number | null;
  pid_from_file: number | null;
  pid_file_present: boolean;
  run_once_running: boolean;
  run_once_pid: number | null;
  uptime_seconds: number | null;
  config_file: string;
  config_file_present: boolean;
  state_file: string;
  state_file_present: boolean;
  report_file: string;
  report_file_present: boolean;
  processed_hashes: number;
  last_cycle_at: string | null;
  last_cycle_submitted: number;
  last_cycle_submitted_new: number;
  last_cycle_deduplicated_existing: number;
  last_cycle_failed: number;
  last_cycle_skipped_seen: number;
  last_cycle_skipped_low_quality: number;
  last_cycle_error: string | null;
  last_cycle_new_item_ids: string[];
  log_file: string;
  log_size_bytes: number;
  log_tail: string[];
}

export interface WechatAgentCommandResult {
  action: "start" | "stop" | "run_once";
  ok: boolean;
  message: string;
  status: WechatAgentStatus;
  output: string | null;
}

export interface WechatAgentBatchStatus {
  running: boolean;
  total_items: number;
  segment_items: number;
  start_batch_index: number;
  current_segment_index: number;
  total_segments: number;
  current_batch_index: number;
  started_at: string | null;
  finished_at: string | null;
  submitted: number;
  submitted_new: number;
  submitted_url: number;
  submitted_url_direct: number;
  submitted_url_share_copy: number;
  submitted_url_resolved: number;
  submitted_ocr: number;
  deduplicated_existing: number;
  deduplicated_existing_url: number;
  deduplicated_existing_url_direct: number;
  deduplicated_existing_url_share_copy: number;
  deduplicated_existing_url_resolved: number;
  deduplicated_existing_ocr: number;
  skipped_invalid_article: number;
  skipped_seen: number;
  failed: number;
  validation_retries: number;
  new_item_ids: string[];
  last_message: string | null;
  last_error: string | null;
  live_report_running: boolean;
  live_report_batch: number | null;
  live_report_row: number | null;
  live_report_stage: string | null;
  live_report_detail: string | null;
  live_report_clicked: number;
  live_report_submitted: number;
  live_report_submitted_url: number;
  live_report_submitted_url_direct: number;
  live_report_submitted_url_share_copy: number;
  live_report_submitted_url_resolved: number;
  live_report_submitted_ocr: number;
  live_report_skipped_seen: number;
  live_report_skipped_invalid_article: number;
  live_report_failed: number;
  live_report_checkpoint_at: string | null;
}

export interface WechatAgentBatchCommandResult {
  ok: boolean;
  message: string;
  batch_status: WechatAgentBatchStatus;
}

export interface WechatAgentDedupSummary {
  processed_hashes: number;
  run_count: number;
  last_run_started_at: string | null;
  last_run_finished_at: string | null;
  last_run_submitted: number;
  last_run_skipped_seen: number;
  last_run_failed: number;
  last_run_item_ids: string[];
}

export interface WechatAgentConfig {
  api_base: string;
  output_language: AppLanguage;
  coordinate_mode: "auto" | "absolute" | "window_relative";
  article_link_profile: "auto" | "compact" | "standard" | "wide" | "manual";
  public_account_origin: { x: number; y: number };
  wechat_bundle_id: string;
  wechat_app_name: string;
  list_origin: { x: number; y: number };
  article_row_height: number;
  rows_per_batch: number;
  batches_per_cycle: number;
  article_open_wait_sec: number;
  article_capture_region: { x: number; y: number; width: number; height: number };
  article_link_hotspots: Array<{ right_inset: number; top_offset: number }>;
  article_link_menu_offsets: Array<{ dx: number; dy: number }>;
  article_reset_page_up: number;
  article_extra_page_down: number;
  feed_reset_page_up: number;
  page_down_wait_sec: number;
  list_page_down_after_batch: number;
  duplicate_escape_page_down: number;
  duplicate_escape_max_extra_pages: number;
  between_item_delay_sec: number;
  dedup_max_hashes: number;
  min_capture_file_size_kb: number;
  article_allow_ocr_fallback: boolean;
  article_verify_with_ocr: boolean;
  article_verify_min_text_length: number;
  article_verify_retries: number;
  loop_interval_sec: number;
  health_stale_minutes: number;
}

export interface WechatAgentCapturePreview {
  captured_at: string;
  image_base64: string;
  mime_type: string;
  region: { x: number; y: number; width: number; height: number };
  image_size_bytes: number;
}

export interface WechatAgentOCRPreview {
  captured_at: string;
  provider: string;
  confidence: number;
  text_length: number;
  title: string;
  body_preview: string;
  keywords: string[];
  quality_ok: boolean;
  quality_reason: string | null;
}

export interface WechatAgentHealth {
  healthy: boolean;
  checked_at: string;
  stale_threshold_minutes: number;
  running: boolean;
  last_cycle_at: string | null;
  minutes_since_last_cycle: number | null;
  reasons: string[];
  recommendation: string | null;
  status: WechatAgentStatus;
}

export interface WechatAgentSelfHealResult {
  ok: boolean;
  action: "none" | "start" | "restart";
  message: string;
  health_before: WechatAgentHealth;
  health_after: WechatAgentHealth;
  output: string | null;
}

export interface CollectorProcessPendingResult {
  scanned: number;
  processed: number;
  failed: number;
  remaining_pending: number;
  item_ids: string[];
}

export interface CollectorFailedItem {
  id: string;
  title: string | null;
  source_url: string | null;
  source_domain: string | null;
  status: string;
  processing_error: string | null;
  created_at: string;
  processed_at: string | null;
}

export interface CollectorFailedList {
  total_failed: number;
  items: CollectorFailedItem[];
}

export interface CollectorRetryFailedResult {
  scanned: number;
  retried: number;
  ready: number;
  failed: number;
  item_ids: string[];
}

export interface CollectorSummaryItem {
  id: string;
  title: string | null;
  source_url: string | null;
  source_domain: string | null;
  score_value: number | null;
  action_suggestion: string | null;
  short_summary: string | null;
  tags: string[];
  created_at: string;
}

export interface CollectorDailySummary {
  generated_at: string;
  range_hours: number;
  total_ingested: number;
  ready_count: number;
  processing_count: number;
  failed_count: number;
  deep_read_count: number;
  later_count: number;
  skip_count: number;
  top_items: CollectorSummaryItem[];
  failed_items: CollectorFailedItem[];
  markdown: string;
}

export interface CollectorSource {
  id: string;
  source_url: string;
  source_domain: string | null;
  note: string | null;
  enabled: boolean;
  last_collected_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface CollectorSourceList {
  total: number;
  items: CollectorSource[];
}

export interface CollectorSourceImportResult {
  source_url: string;
  status: "created" | "exists" | "invalid";
  source_id?: string | null;
  detail?: string | null;
}

export interface CollectorSourceImportResponse {
  total: number;
  created: number;
  exists: number;
  invalid: number;
  results: CollectorSourceImportResult[];
}

export interface CollectorFeedSource {
  id: string;
  feed_type: string;
  source_url: string;
  title: string;
  note: string;
  enabled: boolean;
  status: string;
  last_synced_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface CollectorFeedSourceList {
  total: number;
  items: CollectorFeedSource[];
}

export interface CollectorFeedPullResult {
  feed_id: string;
  source_url: string;
  feed_title: string;
  new_items: number;
  deduplicated_items: number;
  skipped_items: number;
  item_ids: string[];
  latest_titles: string[];
  status: string;
  error: string | null;
  synced_at: string | null;
}

export interface CollectorFeedPullResponse {
  total: number;
  results: CollectorFeedPullResult[];
}

export interface CollectorExternalIngestResponse {
  item: ApiItem;
  deduplicated: boolean;
  processing_deferred: boolean;
  attempt_id?: string | null;
  ingest_route: string;
  content_acquisition_status: string;
  resolver?: string | null;
  body_source?: string | null;
  fallback_used: boolean;
  metadata: Record<string, unknown>;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API ${response.status}: ${text}`);
  }
  const text = await response.text();
  if (!text) {
    return undefined as T;
  }
  return JSON.parse(text) as T;
}

export function listItems(
  limit = 30,
  options?: { mode?: "normal" | "focus"; goalText?: string; includePending?: boolean }
): Promise<{ items: ApiItem[] }> {
  const mode = options?.mode === "focus" ? "focus" : "normal";
  const params = new URLSearchParams({
    limit: String(limit),
    mode,
    include_pending: String(options?.includePending ?? true),
  });
  if (options?.goalText?.trim()) {
    params.set("goal_text", options.goalText.trim());
  }
  return request<{ items: ApiItem[] }>(`/api/items?${params.toString()}`);
}

export function listSavedItems(limit = 30): Promise<{ items: ApiItem[] }> {
  return request<{ items: ApiItem[] }>(`/api/items/saved?limit=${limit}`);
}

export function getItem(itemId: string): Promise<ApiItem> {
  return request<ApiItem>(`/api/items/${itemId}`);
}

export function getPreferenceSummary(): Promise<ApiPreferenceSummary> {
  return request<ApiPreferenceSummary>("/api/preferences/summary");
}

export function resetPreferences(scope: "all" | "topics" | "sources" = "all"): Promise<ApiPreferenceSummary> {
  return request<ApiPreferenceSummary>("/api/preferences/reset", {
    method: "POST",
    body: JSON.stringify({ scope }),
  });
}

export function boostPreference(payload: {
  dimension: "topic" | "source";
  key: string;
  delta?: number;
}): Promise<ApiPreferenceBoostResponse> {
  return request<ApiPreferenceBoostResponse>("/api/preferences/boost", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getItemDiagnostics(itemId: string): Promise<ApiItemDiagnostics> {
  return request<ApiItemDiagnostics>(`/api/items/${itemId}/diagnostics`);
}

export function getCollectorItemAttempts(itemId: string): Promise<ApiCollectorIngestAttempt[]> {
  return request<ApiCollectorIngestAttempt[]>(`/api/collector/items/${itemId}/attempts`);
}

export function createItem(payload: {
  source_type: "url" | "text" | "plugin";
  source_url?: string;
  title?: string;
  raw_content?: string;
  output_language?: AppLanguage;
}): Promise<ApiItem> {
  return request<ApiItem>("/api/items", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createItemsBatch(payload: {
  source_type?: "url" | "plugin";
  urls: string[];
  deduplicate?: boolean;
  output_language?: AppLanguage;
}): Promise<ApiBatchCreateResponse> {
  return request<ApiBatchCreateResponse>("/api/items/batch", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createResearchReport(payload: {
  keyword: string;
  research_focus?: string;
  output_language?: AppLanguage;
  include_wechat?: boolean;
  max_sources?: number;
  research_mode?: "fast" | "deep";
}): Promise<ApiResearchReport> {
  return request<ApiResearchReport>("/api/research/report", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createResearchJob(payload: {
  keyword: string;
  research_focus?: string;
  output_language?: AppLanguage;
  include_wechat?: boolean;
  max_sources?: number;
  deep_research?: boolean;
  research_mode?: "fast" | "deep";
}): Promise<ApiResearchJob> {
  return request<ApiResearchJob>("/api/research/jobs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getResearchJob(jobId: string): Promise<ApiResearchJob> {
  return request<ApiResearchJob>(`/api/research/jobs/${jobId}`, {
    method: "GET",
  });
}

export function getResearchJobTimeline(jobId: string): Promise<ApiResearchJobTimelineEvent[]> {
  return request<ApiResearchJobTimelineEvent[]>(`/api/research/jobs/${jobId}/timeline`, {
    method: "GET",
  });
}

export function listResearchConversations(): Promise<ApiResearchConversation[]> {
  return request<ApiResearchConversation[]>("/api/research/conversations", {
    method: "GET",
  });
}

export function createResearchConversation(payload: {
  title?: string;
  topic_id?: string;
  job_id?: string;
}): Promise<ApiResearchConversation> {
  return request<ApiResearchConversation>("/api/research/conversations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getResearchConversation(conversationId: string): Promise<ApiResearchConversation> {
  return request<ApiResearchConversation>(`/api/research/conversations/${conversationId}`, {
    method: "GET",
  });
}

export function sendResearchConversationMessage(
  conversationId: string,
  payload: { content: string },
): Promise<ApiResearchConversation> {
  return request<ApiResearchConversation>(`/api/research/conversations/${conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getMobileDailyBrief(forceRefresh = false): Promise<ApiMobileDailyBrief> {
  const suffix = forceRefresh ? "?force_refresh=true" : "";
  return request<ApiMobileDailyBrief>(`/api/mobile/daily-brief${suffix}`);
}

export function getResearchSourceSettings(): Promise<ApiResearchSourceSettings> {
  return request<ApiResearchSourceSettings>("/api/research/source-settings", {
    method: "GET",
  }).catch(() => ({
    enable_jianyu_tender_feed: true,
    enable_yuntoutiao_feed: true,
    enable_ggzy_feed: true,
    enable_cecbid_feed: true,
    enable_ccgp_feed: true,
    enable_gov_policy_feed: true,
    enable_local_ggzy_feed: true,
    enabled_source_labels: ["剑鱼标讯", "云头条", "全国公共资源交易平台", "中国招标投标网", "政府采购合规聚合", "中国政府网政策/讲话", "地方公共资源交易平台"],
    connector_statuses: [
      {
        key: "public_open_source_adapters",
        label: "公开招采与行业源适配器",
        status: "active",
        detail: "当前已接入公开招投标、政策讲话、行业媒体与聚合源；不绕过登录墙和付费墙。",
        requires_authorization: false,
      },
    ],
    updated_at: null,
  }));
}

export function updateResearchSourceSettings(payload: {
  enable_jianyu_tender_feed: boolean;
  enable_yuntoutiao_feed: boolean;
  enable_ggzy_feed: boolean;
  enable_cecbid_feed: boolean;
  enable_ccgp_feed: boolean;
  enable_gov_policy_feed: boolean;
  enable_local_ggzy_feed: boolean;
}): Promise<ApiResearchSourceSettings> {
  return request<ApiResearchSourceSettings>("/api/research/source-settings", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function getResearchWorkspace(): Promise<ApiResearchWorkspace> {
  return request<ApiResearchWorkspace>("/api/research/workspace", {
    method: "GET",
  }).catch(() => ({
    saved_views: [],
    tracking_topics: [],
  }));
}

export function listResearchWatchlists(): Promise<ApiResearchWatchlist[]> {
  return request<ApiResearchWatchlist[]>("/api/research/watchlists", {
    method: "GET",
  }).catch(() => []);
}

export function createResearchWatchlist(payload: {
  name: string;
  watch_type?: "topic" | "company" | "policy" | "competitor";
  query: string;
  tracking_topic_id?: string;
  research_focus?: string;
  perspective?: "all" | "regional" | "client_followup" | "bidding" | "ecosystem";
  region_filter?: string;
  industry_filter?: string;
  alert_level?: "low" | "medium" | "high";
  schedule?: string;
}): Promise<ApiResearchWatchlist> {
  return request<ApiResearchWatchlist>("/api/research/watchlists", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getResearchWatchlistChanges(watchlistId: string): Promise<ApiResearchWatchlistChangeEvent[]> {
  return request<ApiResearchWatchlistChangeEvent[]>(`/api/research/watchlists/${watchlistId}/changes`, {
    method: "GET",
  });
}

export function refreshResearchWatchlist(
  watchlistId: string,
  payload?: {
    output_language?: AppLanguage;
    include_wechat?: boolean;
    max_sources?: number;
    save_to_knowledge?: boolean;
    collection_name?: string | null;
    is_focus_reference?: boolean;
  },
): Promise<ApiResearchWatchlistRefresh> {
  return request<ApiResearchWatchlistRefresh>(`/api/research/watchlists/${watchlistId}/refresh`, {
    method: "POST",
    body: JSON.stringify(payload || {}),
  });
}

export function getResearchEntityDetail(entityId: string): Promise<ApiResearchEntityDetail> {
  return request<ApiResearchEntityDetail>(`/api/research/entities/${entityId}`, {
    method: "GET",
  });
}

export function resolveResearchEntityAlias(payload: {
  entity_id: string;
  alias_name: string;
  confidence?: number;
}): Promise<ApiResearchEntityDetail> {
  return request<ApiResearchEntityDetail>("/api/research/entities/resolve-alias", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function saveResearchView(payload: {
  id?: string;
  name: string;
  query?: string;
  filter_mode?: "all" | "reports" | "actions";
  perspective?: "all" | "regional" | "client_followup" | "bidding" | "ecosystem";
  region_filter?: string;
  industry_filter?: string;
  action_type_filter?: string;
  focus_only?: boolean;
}): Promise<ApiResearchSavedView> {
  return request<ApiResearchSavedView>("/api/research/workspace/views", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteResearchView(viewId: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/research/workspace/views/${viewId}`, {
    method: "DELETE",
  });
}

export function saveResearchTrackingTopic(payload: {
  id?: string;
  name: string;
  keyword: string;
  research_focus?: string;
  perspective?: "all" | "regional" | "client_followup" | "bidding" | "ecosystem";
  region_filter?: string;
  industry_filter?: string;
  notes?: string;
}): Promise<ApiResearchTrackingTopic> {
  return request<ApiResearchTrackingTopic>("/api/research/workspace/topics", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteResearchTrackingTopic(topicId: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/research/workspace/topics/${topicId}`, {
    method: "DELETE",
  });
}

export function refreshResearchTrackingTopic(
  topicId: string,
  payload?: {
    output_language?: AppLanguage;
    include_wechat?: boolean;
    max_sources?: number;
    save_to_knowledge?: boolean;
    collection_name?: string | null;
    is_focus_reference?: boolean;
  },
): Promise<ApiResearchTrackingTopicRefresh> {
  return request<ApiResearchTrackingTopicRefresh>(`/api/research/workspace/topics/${topicId}/refresh`, {
    method: "POST",
    body: JSON.stringify(payload || {}),
  });
}

export function getResearchTrackingTopicVersions(
  topicId: string,
): Promise<ApiResearchTrackingTopicVersionDetail[]> {
  return request<ApiResearchTrackingTopicVersionDetail[]>(`/api/research/workspace/topics/${topicId}/versions`, {
    method: "GET",
  });
}

export function getResearchTrackingTopicVersion(
  topicId: string,
  versionId: string,
): Promise<ApiResearchTrackingTopicVersionDetail> {
  return request<ApiResearchTrackingTopicVersionDetail>(
    `/api/research/workspace/topics/${topicId}/versions/${versionId}`,
    {
      method: "GET",
    },
  );
}

export function saveResearchReport(payload: {
  report: ApiResearchReport;
  collection_name?: string | null;
  is_focus_reference?: boolean;
}): Promise<ApiResearchSaveResponse> {
  return request<ApiResearchSaveResponse>("/api/research/report/save", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createResearchActionPlan(payload: {
  report: ApiResearchReport;
}): Promise<ApiResearchActionPlan> {
  return request<ApiResearchActionPlan>("/api/research/action-plan", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function saveResearchActionCards(payload: {
  keyword: string;
  cards: ApiResearchActionCard[];
  collection_name?: string | null;
  is_focus_reference?: boolean;
}): Promise<ApiResearchActionSaveResponse> {
  return request<ApiResearchActionSaveResponse>("/api/research/action-plan/save", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function submitFeedback(itemId: string, feedbackType: FeedbackType): Promise<ApiFeedbackResponse> {
  return request<ApiFeedbackResponse>(`/api/items/${itemId}/feedback`, {
    method: "POST",
    body: JSON.stringify({ feedback_type: feedbackType }),
  });
}

export function reprocessItem(
  itemId: string,
  payload?: {
    output_language?: AppLanguage;
  },
): Promise<{
  item_id: string;
  status: string;
  output_language?: AppLanguage;
}> {
  return request(`/api/items/${itemId}/reprocess`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
}

export function interpretItem(
  itemId: string,
  payload?: {
    output_language?: AppLanguage;
  },
): Promise<ApiItemInterpretation> {
  return request<ApiItemInterpretation>(`/api/items/${itemId}/interpret`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
}

export function addItemToKnowledge(
  itemId: string,
  payload?: {
    title?: string;
    content?: string;
    output_language?: AppLanguage;
  },
): Promise<{
  entry_id: string;
  item_id: string;
  title: string;
  content: string;
  source_domain: string | null;
  created_at: string;
}> {
  return request(`/api/items/${itemId}/knowledge`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
}

export function listKnowledgeEntries(
  limit = 30,
  options?: {
    itemId?: string;
    focusReferenceOnly?: boolean;
    sourceDomain?: string;
    collectionName?: string;
    query?: string;
  },
): Promise<{ items: ApiKnowledgeEntry[] }> {
  const params = new URLSearchParams({
    limit: String(limit),
  });
  if (options?.itemId) {
    params.set("item_id", options.itemId);
  }
  if (options?.focusReferenceOnly) {
    params.set("focus_reference_only", "true");
  }
  if (options?.sourceDomain) {
    params.set("source_domain", options.sourceDomain);
  }
  if (options?.collectionName) {
    params.set("collection_name", options.collectionName);
  }
  if (options?.query) {
    params.set("query", options.query);
  }
  return request<{ items: ApiKnowledgeEntry[] }>(`/api/knowledge?${params.toString()}`);
}

export function getKnowledgeEntry(entryId: string): Promise<ApiKnowledgeEntry> {
  return request<ApiKnowledgeEntry>(`/api/knowledge/${entryId}`);
}

export function getKnowledgeMarkdown(entryId: string): Promise<ApiKnowledgeMarkdown> {
  return request<ApiKnowledgeMarkdown>(`/api/knowledge/${entryId}/markdown`);
}

export function listRelatedKnowledgeEntries(
  entryId: string,
  limit = 4,
): Promise<{ items: ApiKnowledgeEntry[] }> {
  const params = new URLSearchParams({
    limit: String(limit),
  });
  return request<{ items: ApiKnowledgeEntry[] }>(`/api/knowledge/${entryId}/related?${params.toString()}`);
}

export function updateKnowledgeEntry(
  entryId: string,
  payload: {
    title?: string;
    content?: string;
    collection_name?: string | null;
    is_pinned?: boolean;
    is_focus_reference?: boolean;
    metadata_payload?: Record<string, unknown> | null;
  },
): Promise<ApiKnowledgeEntry> {
  return request<ApiKnowledgeEntry>(`/api/knowledge/${entryId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function mergeKnowledgeEntries(payload: {
  entry_ids: string[];
  title?: string;
  content?: string;
}): Promise<ApiKnowledgeEntry> {
  return request<ApiKnowledgeEntry>("/api/knowledge/merge", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getKnowledgeMergePreview(payload: {
  entry_ids: string[];
  title?: string;
}): Promise<ApiKnowledgeMergePreview> {
  return request<ApiKnowledgeMergePreview>("/api/knowledge/merge/preview", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getKnowledgeRule(): Promise<ApiKnowledgeRule> {
  return request<ApiKnowledgeRule>("/api/knowledge/rules");
}

export function updateKnowledgeRule(
  payload: Partial<ApiKnowledgeRule>,
): Promise<ApiKnowledgeRule> {
  return request<ApiKnowledgeRule>("/api/knowledge/rules", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function startSession(payload: {
  goal_text?: string;
  duration_minutes: number;
  output_language?: AppLanguage;
}) {
  return request("/api/sessions/start", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function finishSession(
  sessionId: string,
  payload?: {
    output_language?: AppLanguage;
  },
) {
  return request(`/api/sessions/${sessionId}/finish`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
}

export function getSession(sessionId: string): Promise<ApiSession> {
  return request<ApiSession>(`/api/sessions/${sessionId}`);
}

export function getLatestSession(): Promise<ApiSession> {
  return request<ApiSession>("/api/sessions/latest");
}

export function getSessionArtifacts(sessionId: string): Promise<ApiSessionArtifact[]> {
  return request<ApiSessionArtifact[]>(`/api/sessions/${sessionId}/artifacts`);
}

export function getApiHealth(): Promise<ApiHealth> {
  return request<ApiHealth>("/healthz");
}

export function previewTodoCalendarImport(
  sessionId: string,
  payload?: {
    output_language?: AppLanguage;
    calendar_name?: string;
    todo_markdown?: string;
  },
): Promise<ApiTodoCalendarPreview> {
  return request<ApiTodoCalendarPreview>(`/api/sessions/${sessionId}/todo-calendar-preview`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
}

export function importTodoCalendar(
  sessionId: string,
  payload?: {
    output_language?: AppLanguage;
    calendar_name?: string;
    todo_markdown?: string;
  },
): Promise<ApiTodoCalendarImportResult> {
  return request<ApiTodoCalendarImportResult>(`/api/sessions/${sessionId}/todo-calendar-import`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
}

export function createFocusAssistantPlan(payload: {
  goal_text?: string;
  duration_minutes?: number;
  session_id?: string;
  output_language?: AppLanguage;
}): Promise<FocusAssistantPlan> {
  return request<FocusAssistantPlan>("/api/focus-assistant/plan", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function executeFocusAssistantAction(payload: {
  action_key: FocusAssistantAction["key"];
  goal_text?: string;
  duration_minutes?: number;
  session_id?: string;
  output_language?: AppLanguage;
  channel?: "workbuddy" | "direct";
}): Promise<FocusAssistantExecution> {
  return request<FocusAssistantExecution>("/api/focus-assistant/execute", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getWorkBuddyHealth(): Promise<WorkBuddyHealth> {
  return request<WorkBuddyHealth>("/api/workbuddy/health");
}

export function sendWorkBuddyWebhook(payload: {
  event_type: "ping" | "create_task";
  request_id?: string;
  task_type?:
    | "export_markdown_summary"
    | "export_reading_list"
    | "export_todo_draft"
    | "export_knowledge_markdown"
    | "export_research_report_markdown"
    | "export_research_report_word"
    | "export_research_report_pdf"
    | "export_exec_brief"
    | "export_sales_brief"
    | "export_outreach_draft"
    | "export_watchlist_digest";
  session_id?: string;
  input_payload?: Record<string, unknown>;
  callback?: { url?: string; headers?: Record<string, string> };
}): Promise<WorkBuddyWebhookResponse> {
  return request<WorkBuddyWebhookResponse>("/api/workbuddy/webhook", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createTask(payload: {
  task_type:
    | "export_markdown_summary"
    | "export_reading_list"
    | "export_todo_draft"
    | "export_knowledge_markdown"
    | "export_research_report_markdown"
    | "export_research_report_word"
    | "export_research_report_pdf"
    | "export_exec_brief"
    | "export_sales_brief"
    | "export_outreach_draft"
    | "export_watchlist_digest";
  session_id?: string;
  input_payload?: Record<string, unknown>;
}): Promise<ApiTask> {
  return request<ApiTask>("/api/tasks", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getTask(taskId: string): Promise<ApiTask> {
  return request<ApiTask>(`/api/tasks/${taskId}`);
}

export function getLLMConfig(): Promise<LLMConfig> {
  return request<LLMConfig>("/api/system/llm/config");
}

export function runLLMDryRun(payload: {
  prompt_name?: string;
  variables?: Record<string, string>;
}): Promise<LLMDryRunResult> {
  return request<LLMDryRunResult>("/api/system/llm/dry-run", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getCollectorStatus(): Promise<CollectorStatus> {
  return request<CollectorStatus>("/api/collector/status");
}

export function getCollectorDaemonStatus(): Promise<CollectorDaemonStatus> {
  return request<CollectorDaemonStatus>("/api/collector/daemon/status");
}

export function startCollectorDaemon(): Promise<CollectorDaemonCommandResult> {
  return request<CollectorDaemonCommandResult>("/api/collector/daemon/start", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function stopCollectorDaemon(): Promise<CollectorDaemonCommandResult> {
  return request<CollectorDaemonCommandResult>("/api/collector/daemon/stop", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function runCollectorDaemonOnce(payload?: {
  output_language?: AppLanguage;
  max_collect_per_cycle?: number;
}): Promise<CollectorDaemonCommandResult> {
  const params = new URLSearchParams();
  if (payload?.output_language) {
    params.set("output_language", payload.output_language);
  }
  if (payload?.max_collect_per_cycle) {
    params.set("max_collect_per_cycle", String(payload.max_collect_per_cycle));
  }
  const query = params.toString();
  const path = query
    ? `/api/collector/daemon/run-once?${query}`
    : "/api/collector/daemon/run-once";
  return request<CollectorDaemonCommandResult>(path, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function getWechatAgentStatus(): Promise<WechatAgentStatus> {
  return request<WechatAgentStatus>("/api/collector/wechat-agent/status");
}

export function getWechatAgentConfig(): Promise<WechatAgentConfig> {
  return request<WechatAgentConfig>("/api/collector/wechat-agent/config");
}

export function updateWechatAgentConfig(
  payload: Partial<WechatAgentConfig>,
): Promise<WechatAgentConfig> {
  return request<WechatAgentConfig>("/api/collector/wechat-agent/config", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function getWechatAgentCapturePreview(): Promise<WechatAgentCapturePreview> {
  return request<WechatAgentCapturePreview>("/api/collector/wechat-agent/preview-capture");
}

export function getWechatAgentOCRPreview(payload?: {
  output_language?: AppLanguage;
}): Promise<WechatAgentOCRPreview> {
  const params = new URLSearchParams();
  if (payload?.output_language) {
    params.set("output_language", payload.output_language);
  }
  const query = params.toString();
  const path = query
    ? `/api/collector/wechat-agent/preview-ocr?${query}`
    : "/api/collector/wechat-agent/preview-ocr";
  return request<WechatAgentOCRPreview>(path);
}

export function getWechatAgentHealth(payload?: {
  stale_minutes?: number;
}): Promise<WechatAgentHealth> {
  const params = new URLSearchParams();
  if (payload?.stale_minutes) {
    params.set("stale_minutes", String(payload.stale_minutes));
  }
  const query = params.toString();
  const path = query
    ? `/api/collector/wechat-agent/health?${query}`
    : "/api/collector/wechat-agent/health";
  return request<WechatAgentHealth>(path);
}

export function runWechatAgentSelfHeal(payload?: {
  force?: boolean;
}): Promise<WechatAgentSelfHealResult> {
  const params = new URLSearchParams();
  if (payload?.force) {
    params.set("force", "true");
  }
  const query = params.toString();
  const path = query
    ? `/api/collector/wechat-agent/self-heal?${query}`
    : "/api/collector/wechat-agent/self-heal";
  return request<WechatAgentSelfHealResult>(path, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function startWechatAgent(): Promise<WechatAgentCommandResult> {
  return request<WechatAgentCommandResult>("/api/collector/wechat-agent/start", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function stopWechatAgent(): Promise<WechatAgentCommandResult> {
  return request<WechatAgentCommandResult>("/api/collector/wechat-agent/stop", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function runWechatAgentOnce(payload?: {
  output_language?: AppLanguage;
  max_items?: number;
  start_batch_index?: number;
  wait?: boolean;
}): Promise<WechatAgentCommandResult> {
  const params = new URLSearchParams();
  if (payload?.output_language) {
    params.set("output_language", payload.output_language);
  }
  if (payload?.max_items) {
    params.set("max_items", String(payload.max_items));
  }
  if (payload?.start_batch_index) {
    params.set("start_batch_index", String(payload.start_batch_index));
  }
  if (payload?.wait) {
    params.set("wait", "true");
  }
  const query = params.toString();
  const path = query
    ? `/api/collector/wechat-agent/run-once?${query}`
    : "/api/collector/wechat-agent/run-once";
  return request<WechatAgentCommandResult>(path, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function getWechatAgentBatchStatus(): Promise<WechatAgentBatchStatus> {
  return request<WechatAgentBatchStatus>("/api/collector/wechat-agent/batch-status");
}

export function getWechatAgentDedupSummary(): Promise<WechatAgentDedupSummary> {
  return request<WechatAgentDedupSummary>("/api/collector/wechat-agent/dedup-summary");
}

export function resetWechatAgentDedupSummary(payload?: {
  clear_runs?: boolean;
}): Promise<WechatAgentDedupSummary> {
  const params = new URLSearchParams();
  if (payload?.clear_runs) {
    params.set("clear_runs", "true");
  }
  const query = params.toString();
  const path = query
    ? `/api/collector/wechat-agent/reset-dedup?${query}`
    : "/api/collector/wechat-agent/reset-dedup";
  return request<WechatAgentDedupSummary>(path, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function runWechatAgentBatch(payload?: {
  output_language?: AppLanguage;
  total_items?: number;
  segment_items?: number;
  start_batch_index?: number;
}): Promise<WechatAgentBatchCommandResult> {
  const params = new URLSearchParams();
  if (payload?.output_language) {
    params.set("output_language", payload.output_language);
  }
  if (payload?.total_items) {
    params.set("total_items", String(payload.total_items));
  }
  if (payload?.segment_items) {
    params.set("segment_items", String(payload.segment_items));
  }
  if (payload?.start_batch_index) {
    params.set("start_batch_index", String(payload.start_batch_index));
  }
  const query = params.toString();
  const path = query
    ? `/api/collector/wechat-agent/run-batch?${query}`
    : "/api/collector/wechat-agent/run-batch";
  return request<WechatAgentBatchCommandResult>(path, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function processCollectorPending(limit = 20): Promise<CollectorProcessPendingResult> {
  return request<CollectorProcessPendingResult>(`/api/collector/process-pending?limit=${limit}`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function listCollectorFailed(limit = 20): Promise<CollectorFailedList> {
  return request<CollectorFailedList>(`/api/collector/failed?limit=${limit}`);
}

export function retryCollectorFailed(limit = 20): Promise<CollectorRetryFailedResult> {
  return request<CollectorRetryFailedResult>(`/api/collector/retry-failed?limit=${limit}`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function getCollectorDailySummary(
  hours = 24,
  limit = 12,
): Promise<CollectorDailySummary> {
  return request<CollectorDailySummary>(`/api/collector/daily-summary?hours=${hours}&limit=${limit}`);
}

export function listCollectorSources(
  limit = 200,
  options?: { enabledOnly?: boolean },
): Promise<CollectorSourceList> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (options?.enabledOnly) {
    params.set("enabled_only", "true");
  }
  return request<CollectorSourceList>(`/api/collector/sources?${params.toString()}`);
}

export function createCollectorSource(payload: {
  source_url: string;
  note?: string;
  enabled?: boolean;
}): Promise<CollectorSource> {
  return request<CollectorSource>("/api/collector/sources", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function importCollectorSources(payload: {
  urls: string[];
  enabled?: boolean;
}): Promise<CollectorSourceImportResponse> {
  return request<CollectorSourceImportResponse>("/api/collector/sources/import", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateCollectorSource(
  sourceId: string,
  payload: { enabled?: boolean; note?: string | null },
): Promise<CollectorSource> {
  return request<CollectorSource>(`/api/collector/sources/${sourceId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteCollectorSource(sourceId: string): Promise<void> {
  return request<void>(`/api/collector/sources/${sourceId}`, {
    method: "DELETE",
  });
}

export function listCollectorFeedSources(feedType = "rss"): Promise<CollectorFeedSourceList> {
  const params = new URLSearchParams();
  if (feedType) params.set("feed_type", feedType);
  return request<CollectorFeedSourceList>(`/api/collector/feeds?${params.toString()}`);
}

export function createCollectorRssSource(payload: {
  source_url: string;
  title?: string;
  note?: string;
  pull_immediately?: boolean;
  output_language?: AppLanguage;
  limit?: number;
}): Promise<CollectorFeedSource> {
  return request<CollectorFeedSource>("/api/collector/rss/sources", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function pullCollectorRssFeeds(payload?: {
  feed_id?: string;
  limit?: number;
  output_language?: AppLanguage;
}): Promise<CollectorFeedPullResponse> {
  return request<CollectorFeedPullResponse>("/api/collector/rss/pull", {
    method: "POST",
    body: JSON.stringify(payload || {}),
  });
}

export function ingestNewsletter(payload: {
  title: string;
  sender?: string;
  source_url?: string;
  raw_content: string;
  output_language?: AppLanguage;
}): Promise<CollectorExternalIngestResponse> {
  return request<CollectorExternalIngestResponse>("/api/collector/newsletter/ingest", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function uploadCollectorFile(payload: {
  file_name: string;
  mime_type: string;
  file_base64: string;
  extracted_text?: string;
  title?: string;
  source_url?: string;
  output_language?: AppLanguage;
}): Promise<CollectorExternalIngestResponse> {
  return request<CollectorExternalIngestResponse>("/api/collector/files/upload", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function ingestYouTubeTranscript(payload: {
  video_url: string;
  transcript_text?: string;
  title?: string;
  output_language?: AppLanguage;
}): Promise<CollectorExternalIngestResponse> {
  return request<CollectorExternalIngestResponse>("/api/collector/youtube/ingest", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function toFeedCardLabel(action: string | null): "立即深读" | "稍后精读" | "可放心忽略" {
  if (action === "deep_read") return "立即深读";
  if (action === "later") return "稍后精读";
  return "可放心忽略";
}
