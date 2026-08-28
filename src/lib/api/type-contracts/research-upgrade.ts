export type ApiResearchUpgradeRoundStatus = "ready" | "watch" | "blocked";

export interface ApiResearchUpgradeRoadmapRound {
  index: number;
  key: string;
  title: string;
  status: ApiResearchUpgradeRoundStatus;
  summary: string;
}

export interface ApiResearchUpgradeUrlFirstDiagnostics {
  valid_url_count: number;
  invalid_url_count: number;
  wechat_url_count: number;
  strict_wechat_path_count: number;
  url_first_ratio: number;
  browser_url_check_ready: boolean;
  clipboard_url_check_ready: boolean;
  ocr_fallback_required: boolean;
  warnings: string[];
}

export interface ApiResearchUpgradeQueryFragment {
  key: string;
  intent: string;
  query: string;
  must_terms: string[];
  exclude_terms: string[];
}

export interface ApiResearchUpgradeRetrievalHitEvaluation {
  title: string;
  url: string;
  source_tier: string;
  source_type: string;
  relevance_score: number;
  accepted: boolean;
  reason: string;
  matched_terms: string[];
}

export interface ApiResearchUpgradeRetrievalEvaluation {
  source_count: number;
  accepted_count: number;
  ambiguous_count: number;
  rejected_count: number;
  filtered_old_source_count: number;
  official_source_ratio: number;
  average_relevance_score: number;
  topic_relevance_passed: boolean;
  recency_cutoff_year: number;
  hits: ApiResearchUpgradeRetrievalHitEvaluation[];
}

export interface ApiResearchUpgradeGraphNode {
  name: string;
  role: "buyer" | "competitor" | "partner" | "budget" | "case" | "generic";
  evidence_count: number;
  source_tiers: Record<string, number>;
}

export interface ApiResearchUpgradeGraphEdge {
  source: string;
  target: string;
  relation: string;
  evidence_count: number;
}

export interface ApiResearchUpgradeLightweightGraph {
  nodes: ApiResearchUpgradeGraphNode[];
  edges: ApiResearchUpgradeGraphEdge[];
}

export interface ApiResearchUpgradeExpertPanel {
  role: "buyer_value" | "competitor_threat" | "partner_influence" | "tender_cadence";
  label: string;
  score: number;
  findings: string[];
  next_actions: string[];
}

export interface ApiResearchUpgradeSectionQuota {
  section_title: string;
  required_evidence_count: number;
  actual_evidence_count: number;
  passed: boolean;
  gap: number;
  note: string;
}

export interface ApiResearchUpgradeFieldDiff {
  field: string;
  before: string;
  after: string;
  status: "added" | "removed" | "changed" | "unchanged";
  summary: string;
}

export interface ApiResearchUpgradeFallbackAction {
  priority: "high" | "medium" | "low";
  action: string;
  reason: string;
  owner: string;
}

export interface ApiResearchUpgradeSourceContribution {
  source_type: string;
  count: number;
  accepted_count: number;
  contribution_percent: number;
  average_relevance_score: number;
}

export interface ApiResearchUpgradeDiagnostics {
  generated_at: string;
  roadmap_version: string;
  status: ApiResearchUpgradeRoundStatus;
  readiness_score: number;
  keyword: string;
  research_focus: string;
  roadmap_rounds: ApiResearchUpgradeRoadmapRound[];
  url_first_diagnostics: ApiResearchUpgradeUrlFirstDiagnostics;
  query_plan: ApiResearchUpgradeQueryFragment[];
  retrieval_evaluation: ApiResearchUpgradeRetrievalEvaluation;
  lightweight_graph: ApiResearchUpgradeLightweightGraph;
  expert_panels: ApiResearchUpgradeExpertPanel[];
  section_evidence_quotas: ApiResearchUpgradeSectionQuota[];
  field_diffs: ApiResearchUpgradeFieldDiff[];
  fallback_actions: ApiResearchUpgradeFallbackAction[];
  source_type_contributions: ApiResearchUpgradeSourceContribution[];
  summary_lines: string[];
}
