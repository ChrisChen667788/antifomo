import type { AppLanguage } from "@/lib/preferences";
import type { ApiCollectorIngestAttempt } from "@/lib/api/type-contracts/collector";

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

export interface ApiItemInterpretation {
  item_id: string;
  output_language: AppLanguage;
  insight_title: string;
  expert_take: string;
  key_signals: string[];
  knowledge_note: string;
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

export interface ApiBatchReprocessResult {
  item_id: string;
  status: "accepted" | "skipped" | "missing";
  item_status?: string | null;
  detail?: string | null;
}

export interface ApiBatchReprocessResponse {
  requested: number;
  accepted: number;
  skipped: number;
  missing: number;
  results: ApiBatchReprocessResult[];
}
