import { request } from "@/lib/api/client";
import type {
  ApiProductStrategyCompetitiveLandscape,
  ApiProductStrategyCompetitiveLandscapePreview,
  ApiProductStrategyArtifactAcceptance,
  ApiProductStrategyArtifactAcceptanceInitialization,
  ApiProductStrategyArtifactAcceptancePreview,
  ApiProductStrategyDecisionContextPackets,
  ApiProductStrategyDecisionContextPacketsInitialization,
  ApiProductStrategyDecisionContextPacketsPreview,
  ApiProductStrategyIterationProgram,
  ApiProductStrategyIterationProgramInitialization,
  ApiProductStrategyIterationProgramPreview,
  ApiProductStrategyOfficeEvidenceCreateRequest,
  ApiProductStrategyOfficeEvidenceCreateResponse,
  ApiProductStrategyOfficeEvidenceLandscape,
  ApiProductStrategyVisualEvidenceCreateRequest,
  ApiProductStrategyVisualEvidenceCreateResponse,
  ApiProductStrategyVisualEvidenceLandscape,
  ApiProductStrategyResponsiveEvidence,
  ApiProductStrategyHumanAcceptanceCreateRequest,
  ApiProductStrategyHumanAcceptanceCreateResponse,
  ApiProductStrategyHumanAcceptanceLandscape,
  ApiProductStrategyReleaseEvidenceBridge,
  ApiProductStrategySeedLandscape,
} from "@/lib/api/type-contracts/competitive-intelligence";

const COMPETITIVE_LANDSCAPE_PATH = "/api/product-strategy/competitive-landscape";
const DECISION_CONTEXT_PACKETS_PATH = "/api/product-strategy/decision-context-packets";
const ARTIFACT_ACCEPTANCE_PATH = "/api/product-strategy/artifact-acceptance";
const ITERATION_PROGRAM_PATH = "/api/product-strategy/iteration-program";
const OFFICE_EVIDENCE_RECEIPTS_PATH = "/api/product-strategy/office-evidence-receipts";
const VISUAL_EVIDENCE_REVISIONS_PATH = "/api/product-strategy/visual-evidence-revisions";
const RESPONSIVE_EVIDENCE_PATH = "/api/product-strategy/responsive-evidence";
const HUMAN_ACCEPTANCE_EVENTS_PATH = "/api/product-strategy/human-acceptance-events";
const RELEASE_EVIDENCE_BRIDGE_PATH = "/api/product-strategy/release-evidence-bridge";

export function getCompetitiveLandscapePreview(): Promise<ApiProductStrategyCompetitiveLandscapePreview> {
  return request<ApiProductStrategyCompetitiveLandscapePreview>(`${COMPETITIVE_LANDSCAPE_PATH}/preview`);
}

export function getCompetitiveLandscape(): Promise<ApiProductStrategyCompetitiveLandscape> {
  return request<ApiProductStrategyCompetitiveLandscape>(COMPETITIVE_LANDSCAPE_PATH);
}

export function seedCompetitiveLandscape(): Promise<ApiProductStrategySeedLandscape> {
  return request<ApiProductStrategySeedLandscape>(`${COMPETITIVE_LANDSCAPE_PATH}/seed`, {
    method: "POST",
  });
}

export function getDecisionContextPacketsPreview(): Promise<ApiProductStrategyDecisionContextPacketsPreview> {
  return request<ApiProductStrategyDecisionContextPacketsPreview>(`${DECISION_CONTEXT_PACKETS_PATH}/preview`);
}

export function getDecisionContextPackets(): Promise<ApiProductStrategyDecisionContextPackets> {
  return request<ApiProductStrategyDecisionContextPackets>(DECISION_CONTEXT_PACKETS_PATH);
}

export function initializeDecisionContextPackets(): Promise<ApiProductStrategyDecisionContextPacketsInitialization> {
  return request<ApiProductStrategyDecisionContextPacketsInitialization>(`${DECISION_CONTEXT_PACKETS_PATH}/initialize`, {
    method: "POST",
  });
}

export function getArtifactAcceptancePreview(): Promise<ApiProductStrategyArtifactAcceptancePreview> {
  return request<ApiProductStrategyArtifactAcceptancePreview>(`${ARTIFACT_ACCEPTANCE_PATH}/preview`);
}

export function getArtifactAcceptance(): Promise<ApiProductStrategyArtifactAcceptance> {
  return request<ApiProductStrategyArtifactAcceptance>(ARTIFACT_ACCEPTANCE_PATH);
}

export function initializeArtifactAcceptance(): Promise<ApiProductStrategyArtifactAcceptanceInitialization> {
  return request<ApiProductStrategyArtifactAcceptanceInitialization>(`${ARTIFACT_ACCEPTANCE_PATH}/initialize`, {
    method: "POST",
  });
}

export function getOfficeEvidenceReceipts(): Promise<ApiProductStrategyOfficeEvidenceLandscape> {
  return request<ApiProductStrategyOfficeEvidenceLandscape>(OFFICE_EVIDENCE_RECEIPTS_PATH);
}

export function createOfficeEvidenceReceipt(
  payload: ApiProductStrategyOfficeEvidenceCreateRequest,
): Promise<ApiProductStrategyOfficeEvidenceCreateResponse> {
  return request<ApiProductStrategyOfficeEvidenceCreateResponse>(OFFICE_EVIDENCE_RECEIPTS_PATH, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getIterationProgramPreview(): Promise<ApiProductStrategyIterationProgramPreview> {
  return request<ApiProductStrategyIterationProgramPreview>(`${ITERATION_PROGRAM_PATH}/preview`);
}

export function getVisualEvidenceRevisions(): Promise<ApiProductStrategyVisualEvidenceLandscape> {
  return request<ApiProductStrategyVisualEvidenceLandscape>(VISUAL_EVIDENCE_REVISIONS_PATH);
}

export function getResponsiveEvidence(): Promise<ApiProductStrategyResponsiveEvidence> {
  return request<ApiProductStrategyResponsiveEvidence>(RESPONSIVE_EVIDENCE_PATH);
}

export function createVisualEvidenceRevision(
  payload: ApiProductStrategyVisualEvidenceCreateRequest,
): Promise<ApiProductStrategyVisualEvidenceCreateResponse> {
  return request<ApiProductStrategyVisualEvidenceCreateResponse>(VISUAL_EVIDENCE_REVISIONS_PATH, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getHumanAcceptanceEvents(): Promise<ApiProductStrategyHumanAcceptanceLandscape> {
  return request<ApiProductStrategyHumanAcceptanceLandscape>(HUMAN_ACCEPTANCE_EVENTS_PATH);
}

export function createHumanAcceptanceEvent(
  payload: ApiProductStrategyHumanAcceptanceCreateRequest,
): Promise<ApiProductStrategyHumanAcceptanceCreateResponse> {
  return request<ApiProductStrategyHumanAcceptanceCreateResponse>(HUMAN_ACCEPTANCE_EVENTS_PATH, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getReleaseEvidenceBridge(artifactKey: string): Promise<ApiProductStrategyReleaseEvidenceBridge> {
  return request<ApiProductStrategyReleaseEvidenceBridge>(`${RELEASE_EVIDENCE_BRIDGE_PATH}?artifact_key=${encodeURIComponent(artifactKey)}`);
}

export function getIterationProgram(): Promise<ApiProductStrategyIterationProgram> {
  return request<ApiProductStrategyIterationProgram>(ITERATION_PROGRAM_PATH);
}

export function initializeIterationProgram(): Promise<ApiProductStrategyIterationProgramInitialization> {
  return request<ApiProductStrategyIterationProgramInitialization>(`${ITERATION_PROGRAM_PATH}/initialize`, {
    method: "POST",
  });
}
