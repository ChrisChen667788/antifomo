import type { ApiResearchReport } from "@/lib/api/type-contracts/research-report";
import type { ApiResearchTrackingTopic } from "@/lib/api/type-contracts/research-workspace";

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
  next_due_at?: string | null;
  is_due?: boolean;
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

export interface ApiResearchWatchlistRunDueItem {
  watchlist_id: string;
  name: string;
  status: "refreshed" | "failed";
  change_count: number;
  attempt_count: number;
  retry_count: number;
  summary: string;
  next_due_at?: string | null;
  error?: string | null;
  notification_level: "low" | "medium" | "high";
}

export interface ApiResearchWatchlistRunDueResponse {
  checked_at: string;
  run_id: string;
  due_count: number;
  refreshed_count: number;
  failed_count: number;
  retry_count: number;
  notifications: string[];
  items: ApiResearchWatchlistRunDueItem[];
}

export interface ApiResearchWatchlistRun {
  id: string;
  run_id: string;
  watchlist_id?: string | null;
  watchlist_name: string;
  status: "refreshed" | "failed";
  change_count: number;
  attempt_count: number;
  retry_count: number;
  summary: string;
  error?: string | null;
  notification_level: "low" | "medium" | "high";
  notification_payload: Record<string, unknown>;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
}

export interface ApiResearchWatchlistDigestExport {
  generated_at: string;
  window_start: string;
  window_end: string;
  run_count: number;
  refreshed_count: number;
  failed_count: number;
  change_count: number;
  retry_count: number;
  alert_level: "low" | "medium" | "high";
  summary_lines: string[];
  runs: ApiResearchWatchlistRun[];
  export_markdown: string;
}

export interface ApiResearchWatchlistOpsIssue {
  watchlist_id?: string | null;
  topic_id?: string | null;
  name: string;
  issue_type: "due" | "overdue" | "refresh_failed" | "stale" | "unlinked";
  severity: "low" | "medium" | "high";
  summary: string;
  last_checked_at?: string | null;
  next_due_at?: string | null;
  last_refreshed_at?: string | null;
  error?: string | null;
}

export interface ApiResearchWatchlistOpsSummary {
  checked_at: string;
  active_count: number;
  paused_count: number;
  scheduled_count: number;
  manual_count: number;
  due_count: number;
  overdue_count: number;
  stale_count: number;
  failed_topic_count: number;
  unlinked_count: number;
  next_due_at?: string | null;
  oldest_checked_at?: string | null;
  last_checked_at?: string | null;
  alert_level: "low" | "medium" | "high";
  action_required: boolean;
  recommendations: string[];
  issues: ApiResearchWatchlistOpsIssue[];
}

export interface ApiResearchWatchlistAutomationStatus {
  installed: boolean;
  loaded: boolean;
  label: string;
  plist_path: string;
  state_path: string;
  log_path: string;
  interval_seconds: number;
  last_checked_at?: string | null;
  last_due_count: number;
  last_refreshed_count: number;
  last_failed_count: number;
  last_run_status: "idle" | "ok" | "partial_failure" | "failed";
  last_summary: string;
  last_failure_hint: string;
  alert_level: "low" | "medium" | "high";
  action_required: boolean;
  action_required_reason: string;
  state_stale: boolean;
  state_age_seconds: number;
  recent_request_failure_count: number;
  consecutive_request_failure_count: number;
  failed_items: ApiResearchWatchlistRunDueItem[];
  last_log_size_bytes: number;
  recommended_run_due_command: string;
  recommended_status_command: string;
  recommended_install_command: string;
  recommended_uninstall_command: string;
}
