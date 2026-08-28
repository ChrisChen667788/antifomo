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

export interface ApiHealth {
  status: string;
}

export type ModelRouteStatus = "configured" | "fallback" | "disabled" | "local" | "external";
export type ModelScanStatus = "ready" | "partial" | "blocked";
export type ModelScanRouteStatus = "ready" | "skipped" | "blocked";
export type ModelUpgradeStatus = "applied" | "no_change" | "blocked";

export interface ModelRuntimeRoute {
  key: string;
  label: string;
  provider: string;
  effective_provider: string;
  model?: string | null;
  base_url?: string | null;
  strategy: string;
  fallback: string;
  status: ModelRouteStatus;
  upgrade_managed: boolean;
}

export interface ModuleModelBinding {
  key: string;
  label: string;
  area: string;
  route_key?: string | null;
  provider: string;
  model?: string | null;
  strategy: string;
  fallback: string;
  status: ModelRouteStatus;
  upgrade_managed: boolean;
}

export interface ModelControlPlaneSnapshot {
  generated_at: string;
  policy_version: string;
  routes: ModelRuntimeRoute[];
  modules: ModuleModelBinding[];
}

export interface SupportedModel {
  id: string;
  owned_by: string;
  created?: number | null;
  routes: string[];
  capabilities: string[];
  excluded: boolean;
  exclusion_reason: string;
  scores: Record<string, number>;
  rank_reason: string;
}

export interface ModelScanRoute {
  route_key: string;
  label: string;
  provider: string;
  base_url?: string | null;
  status: ModelScanRouteStatus;
  model_count: number;
  models: string[];
  error_code: string;
  message: string;
}

export interface ModelRecommendation {
  role: "generation" | "strategy" | "vision";
  route_key: string;
  model: string;
  current_model?: string | null;
  change_required: boolean;
  score: number;
  reason: string;
}

export interface SupportedModelScan {
  generated_at: string;
  policy_version: string;
  status: ModelScanStatus;
  total_discovered: number;
  routes: ModelScanRoute[];
  models: SupportedModel[];
  recommendations: ModelRecommendation[];
  message: string;
}

export interface StrongestModelUpgrade {
  generated_at: string;
  status: ModelUpgradeStatus;
  previous_models: Record<string, string | null>;
  applied_models: Record<string, string | null>;
  changed_fields: string[];
  persisted: boolean;
  runtime_reloaded: boolean;
  message: string;
  scan: SupportedModelScan;
}

export type ReleaseReadinessGateStatus = "pass" | "watch" | "blocked";
export type ReleaseReadinessActionPriority = "high" | "medium" | "low";

export interface ReleaseReadinessEvidence {
  label: string;
  status: ReleaseReadinessGateStatus;
  summary: string;
  source: string;
  details: Record<string, unknown>;
}

export interface ReleaseReadinessAction {
  priority: ReleaseReadinessActionPriority;
  owner: string;
  action: string;
  reason: string;
  gate_key: string;
  gate_label: string;
}

export interface ReleaseReadinessOperatorCommand {
  gate_key: string;
  gate_label: string;
  label: string;
  command: string;
  purpose: string;
}

export interface ReleaseReadinessArtifact {
  gate_key: string;
  gate_label: string;
  label: string;
  path: string;
  exists: boolean;
  status: ReleaseReadinessGateStatus;
  summary: string;
}

export interface ReleaseReadinessGate {
  key: string;
  label: string;
  status: ReleaseReadinessGateStatus;
  score: number;
  target: string;
  observed: string;
  summary: string;
  evidence: ReleaseReadinessEvidence[];
  actions: ReleaseReadinessAction[];
}

export interface ReleaseReadinessSnapshot {
  generated_at: string;
  release_version: string;
  overall_status: ReleaseReadinessGateStatus;
  readiness_score: number;
  summary_lines: string[];
  gates: ReleaseReadinessGate[];
  next_actions: ReleaseReadinessAction[];
  operator_commands: ReleaseReadinessOperatorCommand[];
  artifacts: ReleaseReadinessArtifact[];
}

export type InternalSkillStage =
  | "production"
  | "internal_candidate"
  | "third_party_test_package";

export type InternalSkillEvaluationStatus =
  | "passed"
  | "in_progress"
  | "not_evaluated"
  | "blocked";

export type InternalSkillDataBoundary =
  | "local_only"
  | "local_app"
  | "external_optional"
  | "external_blocked";

export type InternalSkillExternalApiStatus =
  | "none"
  | "optional_disabled"
  | "blocked_until_review";

export type InternalSkillSecretStatus =
  | "not_required"
  | "required_for_optional_external_api"
  | "blocked_until_review";

export interface InternalSkillDependency {
  name: string;
  dependency_type: string;
  optional: boolean;
  license: string;
}

export interface InternalSkillRegressionSuite {
  path: string;
  gate: string;
  cadence: string;
}

export interface InternalSkillVersionHistory {
  version: string;
  released_at: string;
  change_summary: string;
  rollback: string;
}

export interface InternalSkillRegistryEntry {
  skill_id: string;
  name: string;
  version: string;
  stage: InternalSkillStage;
  evaluation_status: InternalSkillEvaluationStatus;
  owner: string;
  license: string;
  data_boundary: InternalSkillDataBoundary;
  external_api_status: InternalSkillExternalApiStatus;
  secret_status: InternalSkillSecretStatus;
  default_enabled: boolean;
  default_generation_enabled: boolean;
  admission_reason: string;
  dependencies: InternalSkillDependency[];
  regression_suites: InternalSkillRegressionSuite[];
  applicable_documents: string[];
  baselines: string[];
  version_history: InternalSkillVersionHistory[];
  rollback: string;
  notes: string;
}

export interface InternalSkillGovernanceSummary {
  total_skills: number;
  production_skills: number;
  evaluated_skills: number;
  default_chain_skills: number;
  blocked_from_default_chain: number;
  external_api_skills: number;
  secret_required_skills: number;
  data_egress_modes: string[];
}

export interface InternalSkillRuntimeDiagnostics {
  generated_at: string;
  default_chain_blocking_enforced: boolean;
  unreviewed_default_chain_count: number;
  external_api_status_visible: boolean;
  secret_status_visible: boolean;
  data_egress_status_visible: boolean;
  secret_values_exposed: boolean;
  external_api_skill_ids: string[];
  secret_bound_skill_ids: string[];
  data_egress_modes: string[];
}

export interface InternalSkillGovernanceSnapshot {
  registry_version: string;
  summary: InternalSkillGovernanceSummary;
  diagnostics: InternalSkillRuntimeDiagnostics;
  default_chain_skill_ids: string[];
  blocked_from_default_chain_skill_ids: string[];
  entries: InternalSkillRegistryEntry[];
}
