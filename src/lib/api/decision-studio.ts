import { request } from "@/lib/api/client";
import type {
  DecisionArtifact,
  DecisionArtifactType,
  DecisionActivationPreview,
  DecisionActivationResult,
  DecisionClaim,
  DecisionContract,
  DecisionNotebookDetail,
  DecisionNotebookSummary,
  DecisionPolicyPack,
  DecisionReadiness,
  DecisionReleaseProgram,
  DecisionSearchResult,
  DecisionSection,
  DecisionStatus,
  DecisionStudioOverview,
} from "@/lib/api/type-contracts/decision-studio";

export function getDecisionStudioOverview(): Promise<DecisionStudioOverview> {
  return request<DecisionStudioOverview>("/api/decision-studio/overview");
}

export function createDecisionNotebook(payload: {
  name: string;
  description?: string;
  space_id?: string | null;
}): Promise<DecisionNotebookSummary> {
  return request<DecisionNotebookSummary>("/api/decision-studio/notebooks", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getDecisionNotebook(notebookId: string): Promise<DecisionNotebookDetail> {
  return request<DecisionNotebookDetail>(`/api/decision-studio/notebooks/${notebookId}`);
}

export function addDecisionSource(
  notebookId: string,
  payload: {
    title: string;
    file_name: string;
    mime_type: string;
    content: string;
    source_kind?: string;
    source_uri?: string;
    source_id?: string;
  },
): Promise<{ source: DecisionNotebookDetail["sources"][number]; warnings: string[]; stale_artifact_count: number }> {
  return request(`/api/decision-studio/notebooks/${notebookId}/sources`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function buildDecisionSemanticIndex(notebookId: string): Promise<{
  status: string;
  model: string;
  indexed_passage_count: number;
  dimension: number;
}> {
  return request(`/api/decision-studio/notebooks/${notebookId}/semantic-index`, { method: "POST" });
}

export function verifyDecisionSource(sourceId: string, ownerLabel: string): Promise<DecisionNotebookDetail["sources"][number]> {
  return request<DecisionNotebookDetail["sources"][number]>(`/api/decision-studio/sources/${sourceId}/trust`, {
    method: "PUT",
    body: JSON.stringify({
      trust_status: "verified",
      owner_label: ownerLabel,
      expires_at: null,
    }),
  });
}

export function searchDecisionNotebook(
  notebookId: string,
  payload: {
    query: string;
    included_source_ids: string[] | null;
    limit?: number;
    require_semantic: boolean;
    retrieval_mode?: "semantic" | "hybrid" | "lexical";
  },
): Promise<DecisionSearchResult> {
  return request<DecisionSearchResult>(`/api/decision-studio/notebooks/${notebookId}/search`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createDecisionClaim(
  notebookId: string,
  payload: {
    claim_key: string;
    text: string;
    criticality: "normal" | "critical";
    status: "draft" | "accepted";
    passage_ids: string[];
    depends_on_claim_ids?: string[];
    facts?: Record<string, unknown>;
    owner_label?: string;
  },
): Promise<DecisionClaim> {
  return request<DecisionClaim>(`/api/decision-studio/notebooks/${notebookId}/claims`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createDecisionContract(
  notebookId: string,
  payload: { policy_pack_id: string; title: string },
): Promise<DecisionContract> {
  return request<DecisionContract>(`/api/decision-studio/notebooks/${notebookId}/contracts`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getDecisionPolicyPacks(): Promise<DecisionPolicyPack[]> {
  return request<DecisionPolicyPack[]>("/api/decision-studio/policy-packs");
}

export function upsertDecisionSection(
  notebookId: string,
  payload: { section_key: string; title: string; claim_ids: string[]; contract_id?: string },
): Promise<DecisionSection> {
  return request<DecisionSection>(`/api/decision-studio/notebooks/${notebookId}/sections`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function compileDecisionSections(notebookId: string): Promise<{
  status: DecisionStatus;
  built_section_keys: string[];
  skipped_section_keys: string[];
  blocked_section_keys: string[];
  global_findings: Array<Record<string, unknown>>;
}> {
  return request(`/api/decision-studio/notebooks/${notebookId}/sections/compile`, {
    method: "POST",
    body: JSON.stringify({ force: false, max_workers: 4 }),
  });
}

export function generateDecisionArtifact(
  notebookId: string,
  payload: { artifact_type: DecisionArtifactType; title: string },
): Promise<DecisionArtifact> {
  return request<DecisionArtifact>(`/api/decision-studio/notebooks/${notebookId}/artifacts`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getDecisionReadiness(notebookId?: string): Promise<DecisionReadiness> {
  const query = notebookId ? `?notebook_id=${encodeURIComponent(notebookId)}` : "";
  return request<DecisionReadiness>(`/api/decision-studio/readiness${query}`);
}

export function getDecisionReleaseProgram(): Promise<DecisionReleaseProgram> {
  return request<DecisionReleaseProgram>("/api/decision-studio/release-program");
}

export function previewDecisionDataActivation(payload: {
  notebook_name: string;
  notebook_id?: string | null;
}): Promise<DecisionActivationPreview> {
  return request<DecisionActivationPreview>("/api/decision-studio/activation/preview", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function runDecisionDataActivation(payload: {
  notebook_name: string;
  notebook_id?: string | null;
}): Promise<DecisionActivationResult> {
  return request<DecisionActivationResult>("/api/decision-studio/activation/run", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
