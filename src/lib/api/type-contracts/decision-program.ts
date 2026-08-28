export type DecisionProgramStatus = "pass" | "watch" | "blocked";

export interface DecisionProgramMilestone {
  version: string;
  label: string;
  engineering_status: "implemented";
  acceptance_status: DecisionProgramStatus;
  evidence: Record<string, unknown>;
  blockers: string[];
}

export interface DecisionProgramOverview {
  version: string;
  generated_at: string;
  engineering_status: "implemented";
  overall_acceptance_status: DecisionProgramStatus;
  milestones: DecisionProgramMilestone[];
  honesty_note: string;
}

export interface DecisionReleaseCandidate {
  id: string;
  version: string;
  build_digest: string;
  status: "frozen";
  acceptance_status: DecisionProgramStatus;
  manifest: Record<string, unknown>;
  validation_run_ids: string[];
  external_attestations: Record<string, unknown>;
  evidence_snapshot: Record<string, unknown>;
  blockers: string[];
  frozen_at: string;
}

export interface DecisionReleaseCandidatePreview {
  version: "2.0.7";
  build_digest: string;
  acceptance_status: DecisionProgramStatus;
  validation_run_ids: string[];
  evidence_snapshot: Record<string, unknown>;
  blockers: string[];
  persisted: false;
}

export interface DecisionVerticalPack {
  id: string;
  pack_key: string;
  version: string;
  sector: "medical" | "finance" | "tourism";
  title: string;
  status: "validation_pending" | "active";
  benchmark: Record<string, unknown>;
  content_hash: string;
}
