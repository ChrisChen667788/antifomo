export type ApiProductStrategyEvidenceTier = "vendor_claim" | "local_implementation" | "independent_verification" | "unknown";

export type ApiProductStrategyEvidenceStatus =
  | "vendor_claim_unverified"
  | "independently_verified"
  | "stale"
  | "unknown"
  | "blocked";

export type ApiProductStrategyLocalStatus =
  | "partial_boundary_only"
  | "not_implemented"
  | "not_assessed"
  | "not_evaluated"
  | "implemented"
  | "release_blocked"
  | "planned"
  | "not_applicable";

export type ApiProductStrategyDecision = "build" | "integrate" | "defer" | "explicitly_not_copy";

export interface ApiProductStrategyEvidence {
  tier: ApiProductStrategyEvidenceTier;
  status: ApiProductStrategyEvidenceStatus;
  recorded_status: ApiProductStrategyEvidenceStatus | null;
  vendor_claim_is_not_independent_verification: true;
}

export interface ApiProductStrategyLocalState {
  status: ApiProductStrategyLocalStatus;
  notes: string;
}

export interface ApiProductStrategyProduct {
  catalog_key: string;
  product_key: string;
  vendor: string;
  product_name: string;
  source_title: string;
  source_url: string;
  source_kind: string;
  source_digest: string;
  observed_at: string;
  expires_at: string;
  evidence: ApiProductStrategyEvidence;
  vendor_claim: string;
  claimed_capabilities: string[];
  local_implementation: ApiProductStrategyLocalState;
  local_release: ApiProductStrategyLocalState;
  seed_managed: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface ApiProductStrategyRoadmapCard {
  card_key: string;
  product_key: string;
  title: string;
  decision: ApiProductStrategyDecision;
  status: string;
  rationale: string;
  source_catalog_keys: string[];
  source_digest: string;
  observed_at: string;
  expires_at: string;
  evidence: ApiProductStrategyEvidence;
  acceptance_criteria: string[];
  module_targets: string[];
  approval_status: string;
  release_impact: string;
  can_auto_approve_roadmap: boolean;
  can_auto_approve_release: boolean;
  seed_managed: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface ApiProductStrategyGovernance {
  evidence_tier: ApiProductStrategyEvidenceTier;
  evidence_status: ApiProductStrategyEvidenceStatus;
  vendor_claim_is_not_independent_verification: boolean;
  can_auto_approve_roadmap: boolean;
  can_auto_approve_release: boolean;
  release_gate_mutated: boolean;
  note: string;
}

export interface ApiProductStrategyCompetitiveLandscape {
  catalog_version: string;
  catalog_digest: string;
  observed_at: string | null;
  expires_at: string | null;
  read_only: boolean;
  initialized: boolean;
  persistent_snapshot_digest: string | null;
  governance: ApiProductStrategyGovernance;
  products: ApiProductStrategyProduct[];
  roadmap_cards: ApiProductStrategyRoadmapCard[];
}

export type ApiProductStrategyCompetitiveLandscapePreview = ApiProductStrategyCompetitiveLandscape;

export interface ApiProductStrategySeedSummary {
  sources: {
    created: number;
    updated: number;
    preserved_human: number;
  };
  roadmap_cards: {
    created: number;
    updated: number;
    preserved_human: number;
  };
}

export interface ApiProductStrategySeedLandscape extends ApiProductStrategyCompetitiveLandscape {
  seed: ApiProductStrategySeedSummary;
}

/**
 * 2.10.1 keeps a decision context separate from the roadmap card itself. A
 * recorded user instruction establishes scope only; it is deliberately
 * anonymous and never becomes execution or release authority.
 */
export type ApiProductStrategyDecisionContextDecision = "build" | "integrate" | "defer";

export interface ApiProductStrategyDecisionContextOwner {
  kind: string;
  named_individual: false;
  display_name: string | null;
}

export interface ApiProductStrategyDecisionContextApprovalEvidence {
  kind: "user_instruction";
  actor_identity_status: "unverified";
  scope: "product_strategy_only";
  approval_kind: string;
  owner: ApiProductStrategyDecisionContextOwner;
  instruction: string;
  recorded_at: string;
  authorization_scope: string;
  does_not_approve_release: true;
  does_not_authorize_execution: true;
  requires_human_change_approval: true;
}

export interface ApiProductStrategyDecisionContextSourceReference {
  catalog_key: string;
  source_digest: string;
  observed_at: string;
  expires_at: string;
  evidence: ApiProductStrategyEvidence;
}

export interface ApiProductStrategyDecisionContextPacketRevision {
  id: string | null;
  packet_key: string;
  revision: number;
  previous_revision_digest: string | null;
  revision_digest: string;
  event_type: string;
  snapshot: Record<string, unknown>;
  approval_evidence: ApiProductStrategyDecisionContextApprovalEvidence;
  is_immutable: true;
  seed_managed: boolean;
  created_at: string | null;
}

export interface ApiProductStrategyDecisionContextPacket {
  id: string | null;
  packet_key: string;
  project_scope: "anti-fomo";
  source_catalog_version: string;
  packet_catalog_digest: string;
  roadmap_card_key: string;
  product_key: string;
  decision: ApiProductStrategyDecisionContextDecision;
  decision_approval_status: "approved_by_explicit_product_owner_instruction" | "human_review_required";
  title: string;
  problem_statement: string;
  rationale: string;
  source_catalog_keys: string[];
  source_digests: string[];
  source_references: ApiProductStrategyDecisionContextSourceReference[];
  assumptions: string[];
  constraints: string[];
  module_targets: string[];
  approval_evidence: ApiProductStrategyDecisionContextApprovalEvidence;
  retention_until: string;
  revision: number;
  revision_digest: string;
  status: "approved_for_context";
  can_auto_execute: false;
  can_auto_approve_release: false;
  requires_human_change_approval: true;
  production_status: "not_authorized";
  release_impact: "none";
  seed_managed: boolean;
  created_at: string | null;
  updated_at: string | null;
  revisions: ApiProductStrategyDecisionContextPacketRevision[];
}

export interface ApiProductStrategyDecisionContextExcludedCard {
  card_key: string;
  product_key: string;
  decision: "explicitly_not_copy";
  title: string;
  rationale: string;
  exclusion_reason: string;
  can_auto_execute: false;
  can_auto_approve_release: false;
}

export interface ApiProductStrategyDecisionContextGovernance {
  approval_kind: "user_instruction";
  actor_identity_status: "unverified";
  scope: "product_strategy_only";
  context_packets_require_explicit_initialization: true;
  decision_authorization_is_not_execution_authorization: true;
  decision_authorization_is_not_release_approval: true;
  can_auto_execute: false;
  can_auto_approve_release: false;
  requires_human_change_approval: true;
  release_gate_mutated: false;
  production_status: "not_authorized";
  note: string;
}

export interface ApiProductStrategyDecisionContextInitializationAudit {
  id: string | null;
  event_key: string;
  project_scope: "anti-fomo";
  event_type: string;
  approval_evidence: ApiProductStrategyDecisionContextApprovalEvidence;
  allowed_decisions: ApiProductStrategyDecisionContextDecision[];
  excluded_card_keys: string[];
  source_catalog_version: string;
  packet_catalog_digest: string;
  event_digest: string;
  can_auto_execute: false;
  can_auto_approve_release: false;
  release_gate_mutated: false;
  created_at: string | null;
}

export interface ApiProductStrategyDecisionContextInitializationCounts {
  created: number;
  existing_seed_managed?: number | null;
  preserved_human?: number | null;
  existing?: number | null;
}

export interface ApiProductStrategyDecisionContextInitialization {
  packets: ApiProductStrategyDecisionContextInitializationCounts;
  revisions: ApiProductStrategyDecisionContextInitializationCounts;
  approval_audit: ApiProductStrategyDecisionContextInitializationCounts;
}

export interface ApiProductStrategyDecisionContextPackets {
  context_packet_version: "2.10.1";
  source_catalog_version: string;
  catalog_digest: string;
  read_only: boolean;
  initialized: boolean;
  persistent_snapshot_digest: string | null;
  approval_evidence: ApiProductStrategyDecisionContextApprovalEvidence;
  governance: ApiProductStrategyDecisionContextGovernance;
  packets: ApiProductStrategyDecisionContextPacket[];
  excluded_cards: ApiProductStrategyDecisionContextExcludedCard[];
  initialization_audit: ApiProductStrategyDecisionContextInitializationAudit | null;
}

export type ApiProductStrategyDecisionContextPacketsPreview = ApiProductStrategyDecisionContextPackets;

export interface ApiProductStrategyDecisionContextPacketsInitialization extends ApiProductStrategyDecisionContextPackets {
  initialization: ApiProductStrategyDecisionContextInitialization;
}

/**
 * 2.10.2 records the evidence needed to review an editable artifact and its
 * field-level changes. It deliberately cannot convert a missing Office or
 * visual review into acceptance, release, or execution authority.
 */
export type ApiProductStrategyArtifactAcceptanceStatus = "hold";
export type ApiProductStrategyArtifactBlockingStatus = "blocked";
export type ApiProductStrategyArtifactEvidenceStatus = "missing" | "not_recorded";
export type ApiProductStrategyArtifactEvidenceResult = "hold";

export interface ApiProductStrategyArtifactAcceptanceInstructionEvidence {
  kind: "user_instruction";
  actor_identity_status: "unverified";
  scope: "artifact_acceptance_definition_only";
  instruction: string;
  recorded_at: string;
  authorization_scope: string;
  does_not_approve_artifact_acceptance: true;
  does_not_approve_release: true;
  does_not_authorize_execution: true;
  requires_human_evidence_review: true;
}

export interface ApiProductStrategyArtifactAcceptanceChecklistItem {
  check_key: string;
  title: string;
  required: true;
  evidence_kind: string;
  evidence_status: ApiProductStrategyArtifactEvidenceStatus;
  result: ApiProductStrategyArtifactEvidenceResult;
  blocks_acceptance: true;
  note: string;
}

export interface ApiProductStrategyArtifactContextPacketBinding {
  packet_key: string;
  roadmap_card_key: string;
  decision: ApiProductStrategyDecisionContextDecision;
  revision: number;
  revision_digest: string;
  source_catalog_version: string;
  source_catalog_keys: string[];
  source_digests: string[];
  source_references: ApiProductStrategyDecisionContextSourceReference[];
}

export interface ApiProductStrategyArtifactEvidenceCollection {
  office_file_processing_performed: false;
  visual_render_processing_performed: false;
  office_evidence_status: "missing";
  visual_evidence_status: "missing";
  note: string;
}

export interface ApiProductStrategyArtifactSourceBundle {
  bundle_kind: "decision_context_packet_binding";
  decision_context_packet: ApiProductStrategyArtifactContextPacketBinding;
  evidence_collection: ApiProductStrategyArtifactEvidenceCollection;
}

export interface ApiProductStrategyArtifactFieldChange {
  field: string;
  before: unknown;
  after: unknown;
  change_type: "added" | "removed" | "modified";
}

export interface ApiProductStrategyArtifactFieldLevelDiff {
  from_revision: number | null;
  to_revision: number;
  changed_fields: ApiProductStrategyArtifactFieldChange[];
  auto_acceptance_forbidden: true;
  release_gate_mutated: false;
}

export interface ApiProductStrategyArtifactAcceptanceRevision {
  id: string | null;
  artifact_key: string;
  revision: number;
  previous_revision_digest: string | null;
  revision_digest: string;
  event_type: string;
  snapshot: Record<string, unknown>;
  evidence_source_bundle: ApiProductStrategyArtifactSourceBundle;
  evidence_source_bundle_digest: string;
  field_level_diff: ApiProductStrategyArtifactFieldLevelDiff;
  is_immutable: true;
  seed_managed: boolean;
  created_at: string | null;
}

export interface ApiProductStrategyArtifactAcceptanceArtifact {
  id: string | null;
  artifact_key: string;
  project_scope: "anti-fomo";
  artifact_acceptance_catalog_digest: string;
  decision_context_packet_key: string;
  roadmap_card_key: string;
  decision: ApiProductStrategyDecisionContextDecision;
  artifact_type: string;
  title: string;
  artifact_summary: string;
  acceptance_status: ApiProductStrategyArtifactAcceptanceStatus;
  acceptance_label: "HOLD";
  blocking_status: ApiProductStrategyArtifactBlockingStatus;
  office_evidence_status: "missing";
  visual_evidence_status: "missing";
  acceptance_checklist: ApiProductStrategyArtifactAcceptanceChecklistItem[];
  evidence_source_bundle: ApiProductStrategyArtifactSourceBundle;
  evidence_source_bundle_digest: string;
  revision: number;
  revision_digest: string;
  can_auto_accept: false;
  can_auto_execute: false;
  can_auto_approve_release: false;
  requires_human_evidence_review: true;
  production_status: "not_authorized";
  release_impact: "none";
  seed_managed: boolean;
  created_at: string | null;
  updated_at: string | null;
  revisions: ApiProductStrategyArtifactAcceptanceRevision[];
  initial_field_level_diff: ApiProductStrategyArtifactFieldLevelDiff | null;
}

export interface ApiProductStrategyArtifactAcceptanceGovernance {
  instruction_kind: "user_instruction";
  actor_identity_status: "unverified";
  scope: "artifact_acceptance_definition_only";
  artifact_definitions_require_explicit_initialization: true;
  requires_persisted_decision_context_packets: true;
  missing_office_or_visual_evidence_results_in_hold: true;
  no_external_office_file_processing: true;
  no_visual_render_validation_claim: true;
  can_auto_accept: false;
  can_auto_execute: false;
  can_auto_approve_release: false;
  requires_human_evidence_review: true;
  release_gate_mutated: false;
  production_status: "not_authorized";
  note: string;
}

export interface ApiProductStrategyArtifactAcceptanceContextPacketReadiness {
  required_context_packet_keys: string[];
  missing_context_packet_keys: string[];
  unusable_context_packet_keys: string[];
  ready_for_explicit_initialization: boolean;
}

export interface ApiProductStrategyArtifactAcceptanceInitializationAudit {
  id: string | null;
  event_key: string;
  project_scope: "anti-fomo";
  event_type: string;
  instruction_evidence: ApiProductStrategyArtifactAcceptanceInstructionEvidence;
  required_context_packet_keys: string[];
  artifact_catalog_digest: string;
  context_packet_catalog_digest: string;
  event_digest: string;
  can_auto_accept: false;
  can_auto_execute: false;
  can_auto_approve_release: false;
  release_gate_mutated: false;
  created_at: string | null;
}

export interface ApiProductStrategyArtifactAcceptance {
  artifact_acceptance_version: "2.10.2";
  source_catalog_version: string;
  read_only: boolean;
  initialized: boolean;
  catalog_digest: string;
  context_packet_catalog_digest: string;
  persistent_snapshot_digest: string | null;
  instruction_evidence: ApiProductStrategyArtifactAcceptanceInstructionEvidence;
  governance: ApiProductStrategyArtifactAcceptanceGovernance;
  context_packet_readiness: ApiProductStrategyArtifactAcceptanceContextPacketReadiness | null;
  artifacts: ApiProductStrategyArtifactAcceptanceArtifact[];
  initialization_audit: ApiProductStrategyArtifactAcceptanceInitializationAudit | null;
}

export type ApiProductStrategyArtifactAcceptancePreview = ApiProductStrategyArtifactAcceptance;

export interface ApiProductStrategyArtifactAcceptanceInitialization extends ApiProductStrategyArtifactAcceptance {
  initialization: {
    drafts: ApiProductStrategyArtifactAcceptanceInitializationCounts;
    revisions: ApiProductStrategyArtifactAcceptanceInitializationCounts;
    initialization_audit: ApiProductStrategyArtifactAcceptanceInitializationCounts;
  };
}

export interface ApiProductStrategyArtifactAcceptanceInitializationCounts {
  created: number;
  existing_seed_managed?: number | null;
  preserved_human?: number | null;
  existing?: number | null;
}

export interface ApiProductStrategyIterationProgramInstructionEvidence {
  kind: "user_instruction";
  actor_identity_status: "unverified";
  scope: "product_strategy_iteration_program_only";
  instruction: string;
  recorded_at: string;
  authorization_scope: string;
  does_not_approve_artifact_acceptance: true;
  does_not_authorize_execution: true;
  does_not_approve_release: true;
  requires_human_evidence_review: true;
}

export interface ApiProductStrategyIterationProgramAgentSource {
  catalog_key: string;
  product_key: string;
  vendor: string;
  product_name: string;
  source_title: string;
  source_url: string;
  source_kind: string;
  source_digest: string;
  observed_at: string;
  expires_at: string;
  evidence: ApiProductStrategyEvidence;
  vendor_claim: string;
  claimed_capabilities: string[];
  current_model_signal: string;
  lesson: string;
  anti_fomo_decision: string;
}

export interface ApiProductStrategyIterationProgramFieldChange {
  field: string;
  before: unknown;
  after: unknown;
  change_type: "added" | "removed" | "modified";
}

export interface ApiProductStrategyIterationProgramFieldLevelDiff {
  from_revision: number | null;
  to_revision: number;
  changed_fields: ApiProductStrategyIterationProgramFieldChange[];
  auto_acceptance_forbidden: true;
  release_gate_mutated: false;
}

export interface ApiProductStrategyIterationProgramRevision {
  id: string | null;
  iteration_key: string;
  revision: number;
  previous_revision_digest: string | null;
  revision_digest: string;
  event_type: string;
  snapshot: Record<string, unknown>;
  field_level_diff: ApiProductStrategyIterationProgramFieldLevelDiff;
  is_immutable: true;
  seed_managed: boolean;
  created_at: string | null;
}

export interface ApiProductStrategyIterationProgramItem {
  id: string | null;
  iteration_key: string;
  project_scope: "anti-fomo";
  version: string;
  sequence: number;
  title: string;
  workstream: string;
  decision: ApiProductStrategyDecision;
  purpose: string;
  scope_boundary: string;
  implementation_status: "planning_control_plane_implemented";
  feature_implementation_status: "gated_or_pending_evidence";
  external_evidence_status: "pending";
  acceptance_status: "hold";
  dependencies: string[];
  source_basis: string[];
  delivery_artifacts: string[];
  acceptance_criteria: string[];
  external_evidence_requirements: string[];
  can_auto_accept: false;
  can_auto_execute: false;
  can_auto_approve_release: false;
  requires_human_evidence_review: true;
  production_status: "not_authorized";
  revision: number;
  revision_digest: string;
  seed_managed: boolean;
  created_at: string | null;
  updated_at: string | null;
  revisions: ApiProductStrategyIterationProgramRevision[];
  initial_field_level_diff: ApiProductStrategyIterationProgramFieldLevelDiff | null;
}

export interface ApiProductStrategyIterationProgramGovernance {
  instruction_kind: "user_instruction";
  actor_identity_status: "unverified";
  scope: "product_strategy_iteration_program_only";
  iterations_require_explicit_initialization: true;
  vendor_claim_is_not_independent_verification: true;
  source_change_requires_human_review: true;
  office_and_visual_acceptance_remain_gated: true;
  can_auto_accept: false;
  can_auto_execute: false;
  can_auto_approve_release: false;
  release_gate_mutated: false;
  production_status: "not_authorized";
  note: string;
}

export interface ApiProductStrategyIterationProgramInitializationAudit {
  id: string | null;
  event_key: string;
  project_scope: "anti-fomo";
  event_type: string;
  instruction_evidence: ApiProductStrategyIterationProgramInstructionEvidence;
  iteration_program_digest: string;
  iteration_keys: string[];
  event_digest: string;
  can_auto_accept: false;
  can_auto_execute: false;
  can_auto_approve_release: false;
  release_gate_mutated: false;
  created_at: string | null;
}

export interface ApiProductStrategyIterationProgram {
  iteration_program_version: "2.10.3-2.11.7";
  observed_at: string;
  expires_at: string;
  program_digest: string;
  read_only: boolean;
  initialized: boolean;
  persistent_snapshot_digest: string | null;
  instruction_evidence: ApiProductStrategyIterationProgramInstructionEvidence;
  governance: ApiProductStrategyIterationProgramGovernance;
  agent_sources: ApiProductStrategyIterationProgramAgentSource[];
  iterations: ApiProductStrategyIterationProgramItem[];
  initialization_audit: ApiProductStrategyIterationProgramInitializationAudit | null;
}

export type ApiProductStrategyIterationProgramPreview = ApiProductStrategyIterationProgram;

export interface ApiProductStrategyIterationProgramInitializationCounts {
  created: number;
  existing_seed_managed?: number | null;
  preserved_human?: number | null;
  existing?: number | null;
}

export interface ApiProductStrategyIterationProgramInitialization extends ApiProductStrategyIterationProgram {
  initialization: {
    iterations: ApiProductStrategyIterationProgramInitializationCounts;
    revisions: ApiProductStrategyIterationProgramInitializationCounts;
    initialization_audit: ApiProductStrategyIterationProgramInitializationCounts;
  };
}
