export interface ApiResearchLowQualityIssueSummary {
  code: string;
  count: number;
}

export interface ApiResearchLowQualityIssue {
  code: string;
  severity: "low" | "medium" | "high";
  weight: number;
  summary: string;
  evidence: string;
}

export interface ApiResearchLowQualitySuspiciousRow {
  field: string;
  value: string;
  reason: string;
}

export interface ApiResearchLowQualitySourcePreview {
  title: string;
  domain: string;
  source_tier: string;
}

export interface ApiResearchLowQualityRewriteDiff {
  rewrite_mode: "rewrite" | "guarded";
  before_title: string;
  after_title: string;
  before_summary: string;
  after_summary: string;
  before_next_action: string;
  after_next_action: string;
  before_top_targets: string[];
  after_top_targets: string[];
  after_pending_targets: string[];
  before_risk_score: number;
  after_risk_score: number;
  rewritten_at?: string | null;
}

export interface ApiResearchLowQualityReviewQueueItem {
  entry_id: string;
  updated_at?: string | null;
  entry_title: string;
  report_title: string;
  keyword: string;
  research_focus: string;
  risk_score: number;
  issue_count: number;
  readiness_status: string;
  guarded_backlog: boolean;
  source_count: number;
  official_source_ratio: number;
  retrieval_quality: string;
  evidence_mode: string;
  issue_codes: string[];
  issues: ApiResearchLowQualityIssue[];
  suggested_focus: string[];
  executive_summary: string;
  next_action: string;
  suspicious_rows: ApiResearchLowQualitySuspiciousRow[];
  important_section_failures: string[];
  source_preview: ApiResearchLowQualitySourcePreview[];
  review_status: "pending" | "rewritten" | "accepted" | "reverted";
  review_updated_at?: string | null;
  has_rewrite_snapshot: boolean;
  latest_rewrite?: ApiResearchLowQualityRewriteDiff | null;
}

export interface ApiResearchLowQualityReviewQueue {
  generated_at: string;
  total_reports: number;
  flagged_reports: number;
  invalid_payloads: number;
  issue_summary: ApiResearchLowQualityIssueSummary[];
  recommendations: string[];
  items: ApiResearchLowQualityReviewQueueItem[];
}

export interface ApiResearchLowQualityReviewActionResponse {
  entry_id: string;
  review_status: "rewritten" | "accepted" | "reverted";
  item?: ApiResearchLowQualityReviewQueueItem | null;
  diff?: ApiResearchLowQualityRewriteDiff | null;
}

export interface ApiResearchOfflineEvaluationMetric {
  key: string;
  label: string;
  numerator: number;
  denominator: number;
  rate: number;
  percent: number;
  benchmark: number;
  status: "good" | "watch" | "bad" | string;
  summary: string;
}

export interface ApiResearchOfflineEvaluationWeakReport {
  entry_id: string;
  entry_title: string;
  report_title: string;
  keyword: string;
  weakness_score: number;
  retrieval_hit: boolean;
  supported_target_accounts: number;
  unsupported_target_accounts: number;
  unsupported_targets: string[];
  quota_passed_section_count: number;
  quota_total_section_count: number;
  failing_sections: string[];
  official_source_ratio: number;
  strict_match_ratio: number;
  retrieval_quality: "low" | "medium" | "high" | string;
  solution_delivery_quality_score: number;
  project_proposal_quality_score: number;
  delivery_quality_status: "pass" | "watch" | "fail";
  delivery_missing_axes: string[];
}

export interface ApiResearchOfflineEvaluation {
  generated_at: string;
  total_reports: number;
  evaluated_reports: number;
  invalid_payloads: number;
  metrics: ApiResearchOfflineEvaluationMetric[];
  weakest_reports: ApiResearchOfflineEvaluationWeakReport[];
  summary_lines: string[];
}

export interface ApiResearchFollowupDeltaMetric {
  key:
    | "followup_title_resolution_rate"
    | "followup_summary_resolution_rate"
    | "followup_impacted_section_routing_rate"
    | "followup_delta_official_support_rate";
  label: string;
  numerator: number;
  denominator: number;
  rate: number;
  percent: number;
  benchmark: number;
  status: "good" | "watch" | "bad";
  summary: string;
}

export interface ApiResearchFollowupDeltaWeakReport {
  entry_id: string;
  entry_title: string;
  report_title: string;
  keyword: string;
  impacted_section_count: number;
  official_supported_section_count: number;
  title_resolution: "baseline" | "reused" | "corrected";
  summary_resolution: "baseline" | "reused" | "corrected";
  weak_reasons: string[];
}

export interface ApiResearchFollowupDeltaEvaluation {
  generated_at: string;
  total_reports: number;
  followup_reports: number;
  invalid_payloads: number;
  metrics: ApiResearchFollowupDeltaMetric[];
  weakest_reports: ApiResearchFollowupDeltaWeakReport[];
  summary_lines: string[];
}

export interface ApiResearchDeliveryExportTrendPoint {
  archive_id: string;
  archive_kind: "compare_markdown" | "topic_version_recap" | "archive_diff_recap";
  archive_name: string;
  updated_at: string;
  solution_quality_percent: number;
  proposal_quality_percent: number;
  self_review_gain_percent: number;
  followup_impacted_section_count: number;
  changed_section_count: number;
}

export interface ApiResearchDeliveryExportVersionDelta {
  key:
    | "solution_delivery_quality_pass_rate"
    | "project_proposal_quality_pass_rate"
    | "delivery_self_review_gain_rate"
    | "followup_impacted_section_count"
    | "changed_section_count";
  label: string;
  current_value: number;
  previous_value: number;
  delta_value: number;
  trend: "up" | "flat" | "down";
  summary: string;
}

export interface ApiResearchDeliveryExportDiagnostics {
  generated_at: string;
  total_archives: number;
  analyzed_archives: number;
  archives_with_quality_snapshot: number;
  archives_with_followup_summary: number;
  trend_points: ApiResearchDeliveryExportTrendPoint[];
  version_deltas: ApiResearchDeliveryExportVersionDelta[];
  summary_lines: string[];
}

export interface ApiResearchGoldenEvaluationCase {
  case_id: string;
  title: string;
  expected_methodology: string;
  professional_score: number;
  intelligence_value_score: number;
  target_support_rate: number;
  section_quota_pass_rate: number;
  passed: boolean;
  issues: string[];
}

export interface ApiResearchGoldenEvaluation {
  generated_at: string;
  total_cases: number;
  passed_cases: number;
  average_professional_score: number;
  average_intelligence_value_score: number;
  average_target_support_rate: number;
  average_section_quota_pass_rate: number;
  cases: ApiResearchGoldenEvaluationCase[];
  summary_lines: string[];
}
