import { request } from "@/lib/api/client";

export type OperationFormKind = "capabilities" | "skills" | "proposals" | "dry-runs" | "rollback-rehearsals" | "performance" | "feedback" | "source-reviews" | "gate-reviews";
export type OperationEvidenceKind = "capability" | "skill_inventory" | "execution_proposal" | "dry_run" | "performance" | "task_feedback" | "source_review" | "replay" | "rollback_rehearsal" | "evidence_gate_review";

export interface OperationBoundary {
  can_auto_execute: false;
  can_auto_accept: false;
  can_auto_approve_release: false;
  production_status: "not_authorized";
  acceptance_status: "hold";
}

export interface OperationEvidence extends OperationBoundary {
  evidence_key: string;
  kind: OperationEvidenceKind;
  digest: string;
  payload: Record<string, unknown>;
  created_at: string | null;
}

export interface OperationLandscape extends OperationBoundary {
  records: OperationEvidence[];
  limit: number;
}

export interface OperationWriteResult {
  outcome: "created" | "existing";
  evidence: OperationEvidence;
}

export interface OperationAuditBundle extends OperationBoundary {
  schema_version: "operation-audit-v1";
  records: OperationEvidence[];
  index: { evidence_key: string; digest: string; kind: OperationEvidenceKind }[];
  bundle_digest: string;
  missing_evidence_kinds: OperationEvidenceKind[];
  independent_audit_status: "not_performed";
  scope: "product_strategy_operation_evidence_only";
  required_default_strategy: "baseline_hybrid";
}

export interface OperationAuditHandoff extends OperationBoundary {
  schema_version: "independent-audit-handoff-v1";
  iteration_program_version: string;
  iteration_program_digest: string;
  operation_bundle_digest: string;
  artifact_key: string | null;
  release_readiness: { overall_status: string; release_version: string };
  bridge: Record<string, unknown> | null;
  blockers: string[];
  independent_audit_status: "not_performed";
  read_only: true;
  release_gate_mutated: false;
  production_default: "baseline_hybrid";
  handoff_digest: string;
}

const PATH = "/api/product-strategy/operations";

export function getOperationEvidence(): Promise<OperationLandscape> {
  return request<OperationLandscape>(PATH);
}

// The advanced JSON editor uses backend Pydantic schemas as the authoritative
// validation contract. No client-supplied approval flags are added here.
export function createOperationEvidence(kind: OperationFormKind, payload: Record<string, unknown>): Promise<OperationWriteResult> {
  return request<OperationWriteResult>(`${PATH}/${kind}`, { method: "POST", body: JSON.stringify(payload) });
}

export function replayOperationProposal(evidenceKey: string): Promise<OperationWriteResult> {
  return request<OperationWriteResult>(`${PATH}/proposals/${encodeURIComponent(evidenceKey)}/replay`, { method: "POST" });
}

export function getOperationAuditBundle(): Promise<OperationAuditBundle> {
  return request<OperationAuditBundle>(`${PATH}/audit-bundle`);
}

export function getOperationAuditHandoff(artifactKey?: string): Promise<OperationAuditHandoff> {
  const suffix = artifactKey ? `?artifact_key=${encodeURIComponent(artifactKey)}` : "";
  return request<OperationAuditHandoff>(`${PATH}/audit-handoff${suffix}`);
}
