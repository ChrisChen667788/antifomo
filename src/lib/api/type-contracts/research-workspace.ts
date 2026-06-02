import type { ApiResearchActionCard, ApiResearchEntityEvidence, ApiResearchReport } from "@/lib/api/type-contracts/research-report";

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

export interface ApiResearchTrackingTopicTimelineEvent {
  id: string;
  topic_id: string;
  event_type: "report_version" | "compare_snapshot" | "markdown_archive";
  occurred_at: string;
  title: string;
  summary: string;
  query: string;
  entry_id?: string | null;
  report_version_id?: string | null;
  linked_report_version_id?: string | null;
  linked_report_version_title?: string | null;
  linked_report_version_refreshed_at?: string | null;
  source_count: number;
  evidence_density?: "low" | "medium" | "high" | null;
  source_quality?: "low" | "medium" | "high" | null;
  new_targets: string[];
  new_competitors: string[];
  new_budget_signals: string[];
  compare_snapshot_id?: string | null;
  compare_snapshot_name?: string | null;
  markdown_archive_id?: string | null;
  markdown_archive_kind?: "compare_markdown" | "topic_version_recap" | "archive_diff_recap" | null;
  current_markdown_archive_id?: string | null;
  compare_markdown_archive_id?: string | null;
  row_count: number;
  source_entry_count: number;
  roles: Array<"甲方" | "中标方" | "竞品" | "伙伴">;
  preview_names: string[];
  linked_report_diff_summary: string[];
  followup_title_resolution: string;
  followup_summary_resolution: string;
  followup_impacted_sections: string[];
}

export interface ApiResearchCompareSnapshotDiffAxis {
  key: string;
  label: string;
  snapshot_count: number;
  linked_count: number;
  overlap_count: number;
  snapshot_only: string[];
  linked_only: string[];
}

export interface ApiResearchCompareSnapshotLinkedVersionDiff {
  status: "unavailable" | "aligned" | "expanded" | "trimmed" | "mixed";
  headline: string;
  summary_lines: string[];
  axes: ApiResearchCompareSnapshotDiffAxis[];
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

export interface ApiResearchCompareSnapshot {
  id: string;
  name: string;
  query: string;
  region_filter: string;
  industry_filter: string;
  role_filter: "all" | "甲方" | "中标方" | "竞品" | "伙伴";
  tracking_topic_id?: string | null;
  tracking_topic_name?: string | null;
  report_version_id?: string | null;
  report_version_title?: string | null;
  report_version_refreshed_at?: string | null;
  summary: string;
  row_count: number;
  source_entry_count: number;
  roles: Array<"甲方" | "中标方" | "竞品" | "伙伴">;
  preview_names: string[];
  linked_report_diff?: ApiResearchCompareSnapshotLinkedVersionDiff | null;
  metadata_payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ApiResearchCompareSnapshotDetail extends ApiResearchCompareSnapshot {
  rows: Array<Record<string, unknown>>;
}

export interface ApiResearchMarkdownArchive {
  id: string;
  archive_kind: "compare_markdown" | "topic_version_recap" | "archive_diff_recap";
  name: string;
  filename: string;
  query: string;
  region_filter: string;
  industry_filter: string;
  tracking_topic_id?: string | null;
  tracking_topic_name?: string | null;
  compare_snapshot_id?: string | null;
  compare_snapshot_name?: string | null;
  report_version_id?: string | null;
  report_version_title?: string | null;
  report_version_refreshed_at?: string | null;
  summary: string;
  preview_text: string;
  content_length: number;
  metadata_payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ApiResearchMarkdownArchiveDetail extends ApiResearchMarkdownArchive {
  content: string;
  metadata_payload: Record<string, unknown>;
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
  compare_snapshots: ApiResearchCompareSnapshot[];
  markdown_archives: ApiResearchMarkdownArchive[];
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
