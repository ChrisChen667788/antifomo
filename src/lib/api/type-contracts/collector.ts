import type { AppLanguage } from "@/lib/preferences";
import type { ApiItem } from "@/lib/api/type-contracts/items";

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
  last_run_at: string | null;
  last_run_submit_mode: string | null;
  last_run_discovered_count: number;
  last_run_collected_count: number;
  last_run_plugin_count: number;
  last_run_url_count: number;
  last_run_failed_count: number;
  last_run_skipped_seen_count: number;
  last_run_handled_count: number;
  last_run_coverage_rate: number;
  last_run_body_success_rate: number;
  coverage_state: "idle" | "good" | "watch" | "poor";
  coverage_recommendation: string;
  poor_source_count: number;
  watch_source_count: number;
  favorites_auto_status: "idle" | "disabled" | "unavailable" | "imported" | "error";
  favorites_auto_available: boolean;
  favorites_auto_last_at: string | null;
  favorites_auto_discovered_count: number;
  favorites_auto_imported_count: number;
  favorites_auto_deduplicated_count: number;
  favorites_auto_message: string;
  favorites_clipboard_auto_enabled: boolean;
  favorites_clipboard_adapter_available: boolean;
  favorites_clipboard_last_message: string;
  favorites_export_directory_auto_enabled: boolean;
  favorites_export_directory_path: string;
  favorites_export_directory_adapter_available: boolean;
  favorites_export_directory_last_message: string;
  favorites_export_directory_last_processed_count: number;
  favorites_wechat_cli_adapter_available: boolean;
  favorites_wechat_cli_last_message: string;
  browser_extension_path: string;
  browser_extension_manifest_present: boolean;
  browser_extension_readme_path: string;
  browser_extension_pipeline_script: string;
  browser_extension_last_verification_at: string | null;
  browser_extension_last_verification_ok: boolean;
  browser_extension_last_verification_message: string;
  browser_extension_last_verification_report: string;
  source_health: Array<{
    source_url: string;
    source_token: string;
    scanned: boolean;
    health_state: "good" | "watch" | "poor";
    recommendation: string;
    discovered_count: number;
    handled_count: number;
    collected_count: number;
    plugin_count: number;
    url_count: number;
    skipped_seen_count: number;
    failed_count: number;
    coverage_rate: number;
    body_success_rate: number;
    last_error: string | null;
  }>;
  last_rows: Array<{
    source_token: string | null;
    article_token: string | null;
    mode: string | null;
    item_id: string | null;
    status: string | null;
    note: string | null;
  }>;
  log_tail: string[];
}

export interface CollectorDaemonConfig {
  wechat_clipboard_auto_import: boolean;
  wechat_export_directory_auto_import: boolean;
  wechat_export_directory_path: string;
  config_file: string;
  updated_at: string | null;
}

export interface CollectorBrowserExtensionVerifyResult {
  ok: boolean;
  verified_at: string;
  message: string;
  output: string;
  report_file: string;
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
  submitted_url_tab_copy_link: number;
  submitted_url_tab_browser_open: number;
  submitted_ocr: number;
  deduplicated_existing: number;
  deduplicated_existing_url: number;
  deduplicated_existing_url_direct: number;
  deduplicated_existing_url_share_copy: number;
  deduplicated_existing_url_resolved: number;
  deduplicated_existing_url_tab_copy_link: number;
  deduplicated_existing_url_tab_browser_open: number;
  deduplicated_existing_ocr: number;
  skipped_invalid_article: number;
  skipped_seen: number;
  failed: number;
  validation_retries: number;
  duplicate_escape_count: number;
  route_backoff_count: number;
  route_circuit_breaker_count: number;
  recovery_action_count: number;
  url_only_skip_count: number;
  ocr_preview_seen_count: number;
  ocr_title_seen_count: number;
  accessibility_action_hits: number;
  template_match_hits: number;
  perceptual_duplicate_count: number;
  hard_escape_count: number;
  submenu_trap_count: number;
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
  live_report_submitted_url_tab_copy_link: number;
  live_report_submitted_url_tab_browser_open: number;
  live_report_submitted_ocr: number;
  live_report_skipped_seen: number;
  live_report_skipped_invalid_article: number;
  live_report_failed: number;
  live_report_duplicate_escape_count: number;
  live_report_route_backoff_count: number;
  live_report_route_circuit_breaker_count: number;
  live_report_recovery_action_count: number;
  live_report_url_only_skip_count: number;
  live_report_ocr_preview_seen_count: number;
  live_report_ocr_title_seen_count: number;
  live_report_accessibility_action_hits: number;
  live_report_template_match_hits: number;
  live_report_perceptual_duplicate_count: number;
  live_report_hard_escape_count: number;
  live_report_submenu_trap_count: number;
  live_report_checkpoint_at: string | null;
  route_quality: {
    url_first_share: number;
    ocr_share: number;
    accessibility_hit_rate: number;
    template_hit_rate: number;
    route_stability: "good" | "watch" | "poor";
    recommendation: string;
  };
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

export interface CollectorWechatFavoriteImportItem {
  source_url: string | null;
  title: string | null;
  item_id?: string | null;
  status: "created" | "deduplicated" | "invalid" | "skipped";
  detail?: string | null;
  body_source?: string | null;
}

export interface CollectorWechatFavoriteImportBatch {
  id: string;
  import_type: "wechat_favorites";
  source_label: string;
  status: "empty" | "reviewed" | "processing" | "failed" | "ready" | string;
  output_language: AppLanguage;
  processing_deferred: boolean;
  total_candidates: number;
  created: number;
  deduplicated: number;
  invalid: number;
  skipped: number;
  item_ids: string[];
  created_item_ids: string[];
  review_item_ids: string[];
  ready: number;
  processing: number;
  failed: number;
  triaged: number;
  failed_item_ids: string[];
  results: CollectorWechatFavoriteImportItem[];
  source_summary: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CollectorWechatFavoriteImportBatchList {
  total: number;
  items: CollectorWechatFavoriteImportBatch[];
}

export interface CollectorWechatFavoriteImportResponse {
  ingest_route: "wechat_favorites";
  batch_id?: string | null;
  batch?: CollectorWechatFavoriteImportBatch | null;
  total_candidates: number;
  created: number;
  deduplicated: number;
  invalid: number;
  skipped: number;
  processing_deferred: boolean;
  created_item_ids: string[];
  results: CollectorWechatFavoriteImportItem[];
}

export interface CollectorWechatFavoritePreviewCandidate {
  source_url: string | null;
  title: string | null;
  body_source: string;
}

export interface CollectorWechatFavoritePreviewResponse {
  total_candidates: number;
  url_candidates: number;
  text_candidates: number;
  samples: CollectorWechatFavoritePreviewCandidate[];
}
