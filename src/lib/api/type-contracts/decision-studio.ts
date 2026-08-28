export type DecisionStatus = "pass" | "watch" | "blocked";

export interface DecisionNotebookSummary {
  id: string;
  user_id: string;
  space_id: string | null;
  name: string;
  description: string;
  status: string;
  source_count: number;
  artifact_count: number;
  stale_artifact_count: number;
  created_at: string;
  updated_at: string;
}

export interface DecisionSourceSummary {
  id: string;
  notebook_id: string;
  title: string;
  source_kind: string;
  source_uri: string;
  mime_type: string;
  labels: string[];
  admission_status: string;
  current_revision_id: string | null;
  current_revision_number: number;
  current_content_hash: string;
  current_parser: string;
  current_passage_count: number;
  owner_label: string;
  trust_status: string;
}

export interface DecisionCitation {
  passage_id: string;
  source_id: string;
  source_title: string;
  source_revision_id: string;
  revision_number: number;
  is_current_revision: boolean;
  locator: Record<string, unknown>;
}

export interface DecisionClaim {
  id: string;
  notebook_id: string;
  claim_key: string;
  text: string;
  criticality: "normal" | "critical";
  status: "draft" | "accepted" | "rejected";
  passage_ids: string[];
  depends_on_claim_ids: string[];
  facts: Record<string, unknown>;
  owner_label: string;
  citations: DecisionCitation[];
}

export interface DecisionContract {
  id: string;
  notebook_id: string;
  policy_pack_id: string;
  title: string;
  document_kind: string;
  status: string;
  revision: number;
  fields: Record<string, Record<string, unknown>>;
  assumptions: Array<Record<string, unknown>>;
  calculations: Array<Record<string, unknown>>;
  gaps: Array<Record<string, unknown>>;
  gap_count: number;
  completion_percent: number;
}

export interface DecisionSection {
  id: string;
  notebook_id: string;
  section_key: string;
  title: string;
  status: string;
  claim_ids: string[];
  content: string;
  build_version: number;
  findings: Array<Record<string, unknown>>;
}

export interface DecisionArtifact {
  id: string;
  notebook_id: string;
  artifact_type: string;
  title: string;
  status: string;
  content: Record<string, unknown>;
  source_revision_ids: string[];
  claim_ids: string[];
  stale: boolean;
  reused?: boolean;
}

export interface DecisionNotebookDetail extends DecisionNotebookSummary {
  sources: DecisionSourceSummary[];
  contracts: DecisionContract[];
  claims: DecisionClaim[];
  sections: DecisionSection[];
  artifacts: DecisionArtifact[];
}

export interface DecisionPolicyPack {
  id: string;
  pack_key: string;
  version: string;
  title: string;
  authority: string;
  source_uri: string;
  document_kind: string;
  status: string;
  schema: {
    sections?: string[];
    fields?: Array<Record<string, unknown>>;
  };
  content_hash: string;
}

export interface DecisionSkillSummary {
  id: string;
  skill_key: string;
  version: string;
  publisher: string;
  status: string;
  signature_present: boolean;
  signature_valid: boolean;
  permissions: string[];
  benchmark: Record<string, unknown>;
}

export interface DecisionStudioOverview {
  version: string;
  capabilities: string[];
  embedding: {
    enabled: boolean;
    provider: string;
    model: string;
    device: string;
    batch_size: number;
    cache_dir: string | null;
    xet_cache_dir: string | null;
  };
  spaces: Array<Record<string, unknown>>;
  notebooks: DecisionNotebookSummary[];
  policy_packs: DecisionPolicyPack[];
  skills: DecisionSkillSummary[];
}

export interface DecisionSearchHit {
  passage_id: string;
  source_id: string;
  source_title: string;
  source_uri: string;
  source_revision_id: string;
  revision_number: number;
  text: string;
  score: number;
  mode: "semantic" | "hybrid_rrf" | "lexical" | "lexical_fallback";
  ranking?: Record<string, number>;
  locator: Record<string, unknown>;
}

export interface DecisionSearchResult {
  status: "ready" | "degraded";
  mode: "semantic" | "hybrid_rrf" | "lexical" | "lexical_fallback";
  model: string;
  included_source_ids: string[] | null;
  warnings: string[];
  hits: DecisionSearchHit[];
}

export interface DecisionReadinessGate {
  key: string;
  label: string;
  status: DecisionStatus;
  score: number;
  target: string;
  observed: string;
  actions: Array<{ action: string; reason: string }>;
}

export interface DecisionReadiness {
  generated_at: string;
  release_version: string;
  overall_status: DecisionStatus;
  readiness_score: number;
  summary_lines: string[];
  gates: DecisionReadinessGate[];
  next_actions: Array<{ gate_key: string; gate_label: string; action: string; reason: string }>;
}

export interface DecisionValidationFinding {
  key: string;
  label: string;
  actual: unknown;
  target: string;
  status: DecisionStatus;
}

export interface DecisionValidationRun {
  id: string;
  milestone_version: string;
  suite_key: string;
  label: string;
  evidence_class: string;
  status: DecisionStatus;
  score: number;
  target: string;
  computed_metrics: Record<string, unknown>;
  findings: DecisionValidationFinding[];
  input_digest: string;
  reviewer_id: string;
  reviewer_role: string;
  source_artifact_uri: string;
  created_at: string;
}

export interface DecisionReleaseSuite {
  suite_key: string;
  label: string;
  evidence_class: string;
  status: DecisionStatus;
  score: number;
  target: string;
  latest_run: DecisionValidationRun | null;
  blockers: string[];
}

export interface DecisionReleaseMilestone {
  version: string;
  implementation_status: "implemented";
  acceptance_status: DecisionStatus;
  score: number;
  suite_count: number;
  passed_suite_count: number;
  suites: DecisionReleaseSuite[];
}

export interface DecisionReleaseProgram {
  generated_at: string;
  release_version: string;
  implementation_status: "implemented";
  overall_status: DecisionStatus;
  readiness_score: number;
  milestones: DecisionReleaseMilestone[];
  honesty_note: string;
}

export interface DecisionActivationCandidate {
  source_type: "knowledge_entry" | "research_job";
  source_record_id: string;
  title: string;
  source_uri: string;
  content_chars: number;
  state: "new" | "existing_changed" | "existing_unchanged" | "duplicate_input";
}

export interface DecisionActivationPreview {
  status: "ready" | "blocked";
  candidate_count: number;
  state_counts: Record<string, number>;
  source_type_counts: Record<string, number>;
  notebook_id: string | null;
  candidates: DecisionActivationCandidate[];
  warnings: string[];
}

export interface DecisionActivationResult {
  status: DecisionStatus;
  notebook: DecisionNotebookSummary;
  metrics: {
    candidate_count: number;
    created_source_count: number;
    updated_source_count: number;
    unchanged_source_count: number;
    failed_source_count: number;
    provenance_source_count: number;
  };
  validation_run: DecisionValidationRun;
}

export type DecisionArtifactType =
  | "executive_brief"
  | "mind_map"
  | "data_table"
  | "slide_outline"
  | "infographic_spec"
  | "audio_script";
