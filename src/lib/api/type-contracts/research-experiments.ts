export interface ApiResearchExperimentArm {
  key: string;
  label: string;
  role: "baseline" | "candidate";
  numerator: number;
  denominator: number;
  rate: number;
  percent: number;
  summary: string;
}

export interface ApiResearchExperimentLane {
  key: "query_recovery" | "routing_followup" | "reranker_official_recall";
  label: string;
  metric_label: string;
  baseline: ApiResearchExperimentArm;
  candidate: ApiResearchExperimentArm;
  uplift_points: number;
  status: "ready" | "watch" | "insufficient";
  interpretation: string;
}

export interface ApiResearchExperimentControlPlane {
  generated_at: string;
  total_reports: number;
  evaluated_reports: number;
  invalid_payloads: number;
  lanes: ApiResearchExperimentLane[];
  summary_lines: string[];
}

export interface ApiResearchExperimentGateConfig {
  minimum_sample_size: number;
  minimum_uplift_points: number;
}

export interface ApiResearchExperimentRolloutGate {
  decision: "allow" | "hold" | "block";
  lane_key: ApiResearchExperimentLane["key"];
  baseline_version_label: string;
  locked_baseline_percent: number;
  candidate_percent: number;
  observed_uplift_points: number;
  required_uplift_points: number;
  sample_size: number;
  minimum_sample_size: number;
  reasons: string[];
  evaluated_at: string;
  current_lane?: ApiResearchExperimentLane | null;
}

export interface ApiResearchExperimentRolloutManifest {
  decision: "promoted" | "revoked";
  plan_id: string;
  plan_name: string;
  lane_key: ApiResearchExperimentLane["key"];
  strategy_family: "query_plan" | "routing_policy" | "reranker";
  candidate_label: string;
  baseline_version_label: string;
  promoted_version_label: string;
  gate_evaluated_at?: string | null;
  locked_baseline_percent: number;
  candidate_percent: number;
  observed_uplift_points: number;
  sample_size: number;
  note: string;
  activation_payload: Record<string, unknown>;
  promoted_at?: string | null;
  revoked_at?: string | null;
}

export interface ApiResearchExperimentActivePolicy {
  lane_key: ApiResearchExperimentLane["key"];
  plan_id: string;
  plan_name: string;
  strategy_family: "query_plan" | "routing_policy" | "reranker";
  candidate_label: string;
  promoted_version_label: string;
  baseline_version_label: string;
  candidate_percent: number;
  observed_uplift_points: number;
  sample_size: number;
  promoted_at?: string | null;
  gate_evaluated_at?: string | null;
  activation_payload: Record<string, unknown>;
  conflict_plan_ids: string[];
}

export interface ApiResearchExperimentRuntimeStrategy {
  lane_key: ApiResearchExperimentLane["key"];
  plan_id: string;
  plan_name: string;
  strategy_family: "query_plan" | "routing_policy" | "reranker";
  candidate_label: string;
  enabled: boolean;
  promoted_version_label: string;
  baseline_version_label: string;
  promoted_at?: string | null;
  gate_evaluated_at?: string | null;
  runtime_config: Record<string, unknown>;
  gate: Record<string, unknown>;
  provenance: Record<string, unknown>;
  warnings: string[];
}

export interface ApiResearchExperimentRuntimeSnapshot {
  generated_at: string;
  project_version_label: string;
  status: "ready" | "degraded" | "empty";
  policy_count: number;
  conflict_count: number;
  strategy_count: number;
  runtime_config: Record<string, unknown>;
  strategies: ApiResearchExperimentRuntimeStrategy[];
  warnings: string[];
  summary_lines: string[];
}

export interface ApiResearchExperimentEffectiveRuntimeConfig {
  generated_at: string;
  project_version_label: string;
  consumer: "all" | "query_generation" | "section_routing" | "retrieval_search" | "source_reranker";
  status: "ready" | "degraded" | "fallback";
  enabled_lane_count: number;
  applied_lanes: ApiResearchExperimentLane["key"][];
  fallback_lanes: ApiResearchExperimentLane["key"][];
  effective_config: Record<string, unknown>;
  provenance: Record<string, unknown>;
  warnings: string[];
  summary_lines: string[];
}

export interface ApiResearchExperimentPlan {
  id: string;
  name: string;
  lane_key: ApiResearchExperimentLane["key"];
  strategy_family: "query_plan" | "routing_policy" | "reranker";
  candidate_label: string;
  notes: string;
  strategy_payload: Record<string, unknown>;
  gate_config: ApiResearchExperimentGateConfig;
  status:
    | "draft"
    | "cohort_frozen"
    | "baseline_locked"
    | "gate_allowed"
    | "gate_hold"
    | "gate_blocked"
    | "rollout_promoted"
    | "rollout_revoked";
  cohort_size: number;
  cohort_entry_ids: string[];
  cohort_preview_titles: string[];
  cohort_frozen_at?: string | null;
  baseline_version_label: string;
  baseline_lane?: ApiResearchExperimentLane | null;
  baseline_locked_at?: string | null;
  latest_gate?: ApiResearchExperimentRolloutGate | null;
  gate_history: ApiResearchExperimentRolloutGate[];
  gate_history_count: number;
  rollout_manifest?: ApiResearchExperimentRolloutManifest | null;
  last_gate_evaluated_at?: string | null;
  promoted_at?: string | null;
  rollout_revoked_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApiResearchExperimentOrchestration {
  generated_at: string;
  total_plans: number;
  frozen_plan_count: number;
  locked_plan_count: number;
  allowed_plan_count: number;
  blocked_plan_count: number;
  hold_plan_count: number;
  promoted_plan_count: number;
  revoked_plan_count: number;
  active_policy_count: number;
  active_policy_conflict_count: number;
  active_policies: ApiResearchExperimentActivePolicy[];
  plans: ApiResearchExperimentPlan[];
  summary_lines: string[];
}
