import type { ApiResearchEntityEvidence } from "@/lib/api/type-contracts/research";

export interface ApiKnowledgeEntry {
  id: string;
  item_id: string | null;
  title: string;
  content: string;
  source_domain: string | null;
  metadata_payload?: Record<string, unknown> | null;
  commercial_intelligence?: ApiKnowledgeCommercialIntelligence | null;
  collection_name?: string | null;
  is_pinned?: boolean;
  is_focus_reference?: boolean;
  created_at: string;
  updated_at?: string | null;
}

export interface ApiKnowledgeMethodologyCard {
  scope_summary: string;
  pipeline_summary: string;
  query_plan: string[];
  data_boundary: string;
  retained_source_count: number;
  unique_domain_count: number;
  matched_source_labels: string[];
  matched_theme_labels: string[];
}

export interface ApiKnowledgeConfidenceCard {
  level: "low" | "medium" | "high" | string;
  score: number;
  source_count: number;
  official_source_ratio: number;
  evidence_density: string;
  source_quality: string;
  reasons: string[];
  concerns: string[];
}

export interface ApiKnowledgeCoverageGap {
  title: string;
  severity: "low" | "medium" | "high" | string;
  detail: string;
  recommended_action: string;
}

export interface ApiKnowledgeAccountSnapshot {
  slug: string;
  name: string;
  role: string;
  priority: string;
  confidence_score: number;
  summary: string;
  why_now: string[];
  departments: string[];
  contacts: string[];
  signals: string[];
  benchmark_cases: string[];
  next_best_action: string;
  maturity_stage: string;
  budget_probability: number;
  evidence_links: ApiResearchEntityEvidence[];
}

export interface ApiKnowledgeOpportunity {
  title: string;
  account_slug: string;
  account_name: string;
  stage: string;
  score: number;
  confidence_label: string;
  budget_probability: number;
  entry_window: string;
  next_best_action: string;
  why_now: string[];
  risk_flags: string[];
  benchmark_case: string;
  related_action_titles: string[];
}

export interface ApiKnowledgeBenchmarkCard {
  summary: string;
  cases: string[];
  comparators: string[];
}

export interface ApiKnowledgeMaturityDimension {
  name: string;
  level: string;
  note: string;
}

export interface ApiKnowledgeMaturityAssessment {
  stage: string;
  score: number;
  summary: string;
  dimensions: ApiKnowledgeMaturityDimension[];
}

export interface ApiKnowledgeCommercialIntelligence {
  schema_version?: number;
  methodology: ApiKnowledgeMethodologyCard;
  confidence: ApiKnowledgeConfidenceCard;
  coverage_gaps: ApiKnowledgeCoverageGap[];
  accounts: ApiKnowledgeAccountSnapshot[];
  opportunities: ApiKnowledgeOpportunity[];
  benchmark: ApiKnowledgeBenchmarkCard;
  maturity: ApiKnowledgeMaturityAssessment;
  why_now: string[];
  next_steps: string[];
}

export interface ApiKnowledgeLinkedEntry {
  entry_id: string;
  title: string;
  source_domain?: string | null;
  collection_name?: string | null;
  created_at: string;
}

export interface ApiKnowledgeAccountTimelineItem {
  id: string;
  kind: string;
  title: string;
  summary: string;
  severity: string;
  created_at: string;
  watchlist_name?: string | null;
  next_action: string;
  budget_probability: number;
  related_entry_id?: string | null;
  related_watchlist_id?: string | null;
  tags: string[];
  resolution_status?: string | null;
  resolution_note?: string;
}

export interface ApiKnowledgeAccountPlan {
  objective: string;
  relationship_goal: string;
  value_hypothesis: string;
  strategic_wedges: string[];
  proof_points: string[];
  next_meeting_goal: string;
}

export interface ApiKnowledgeStakeholder {
  name: string;
  role: string;
  stance: string;
  priority: string;
  next_move: string;
  evidence_links: ApiResearchEntityEvidence[];
}

export interface ApiKnowledgeClosePlanStep {
  title: string;
  owner: string;
  due_window: string;
  exit_criteria: string;
}

export interface ApiKnowledgePipelineRisk {
  title: string;
  severity: string;
  detail: string;
  mitigation: string;
}

export interface ApiKnowledgeAccountDigest {
  slug: string;
  name: string;
  priority: string;
  report_count: number;
  opportunity_count: number;
  confidence_score: number;
  budget_probability: number;
  maturity_stage: string;
  latest_signal: string;
  next_best_action: string;
  benchmark_cases: string[];
  related_entry_ids: string[];
}

export interface ApiKnowledgeAccountDetail extends ApiKnowledgeAccountDigest {
  summary: string;
  why_now: string[];
  contacts: string[];
  departments: string[];
  signals: string[];
  risks: string[];
  evidence_links: ApiResearchEntityEvidence[];
  opportunities: ApiKnowledgeOpportunity[];
  related_entries: ApiKnowledgeLinkedEntry[];
  timeline: ApiKnowledgeAccountTimelineItem[];
  account_plan: ApiKnowledgeAccountPlan;
  stakeholder_map: ApiKnowledgeStakeholder[];
  close_plan: ApiKnowledgeClosePlanStep[];
  pipeline_risks: ApiKnowledgePipelineRisk[];
}

export interface ApiKnowledgeDashboardAlert {
  id: string;
  kind: string;
  severity: string;
  title: string;
  summary: string;
  account_slug?: string | null;
  account_name?: string | null;
  recommended_action: string;
  created_at?: string | null;
}

export interface ApiKnowledgeRoleView {
  key: string;
  label: string;
  summary: string;
  focus_items: string[];
  account_slugs: string[];
  opportunity_titles: string[];
}

export interface ApiKnowledgeReviewQueueItem {
  id: string;
  severity: string;
  title: string;
  summary: string;
  account_slug?: string | null;
  account_name?: string | null;
  related_entry_id?: string | null;
  recommended_action: string;
  evidence_links: ApiResearchEntityEvidence[];
  resolution_status: string;
  resolution_note: string;
  resolved_at?: string | null;
}

export interface ApiKnowledgeDashboard {
  account_count: number;
  opportunity_count: number;
  high_confidence_report_count: number;
  benchmark_case_count: number;
  top_accounts: ApiKnowledgeAccountDigest[];
  top_opportunities: ApiKnowledgeOpportunity[];
  top_alerts: ApiKnowledgeDashboardAlert[];
  role_views: ApiKnowledgeRoleView[];
  review_queue: ApiKnowledgeReviewQueueItem[];
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
