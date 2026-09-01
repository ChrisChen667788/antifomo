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
  ApiProductStrategySeedLandscape,
} from "@/lib/api/type-contracts/competitive-intelligence";

const COMPETITIVE_LANDSCAPE_PATH = "/api/product-strategy/competitive-landscape";
const DECISION_CONTEXT_PACKETS_PATH = "/api/product-strategy/decision-context-packets";
const ARTIFACT_ACCEPTANCE_PATH = "/api/product-strategy/artifact-acceptance";
const ITERATION_PROGRAM_PATH = "/api/product-strategy/iteration-program";

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

export function getIterationProgramPreview(): Promise<ApiProductStrategyIterationProgramPreview> {
  return request<ApiProductStrategyIterationProgramPreview>(`${ITERATION_PROGRAM_PATH}/preview`);
}

export function getIterationProgram(): Promise<ApiProductStrategyIterationProgram> {
  return request<ApiProductStrategyIterationProgram>(ITERATION_PROGRAM_PATH);
}

export function initializeIterationProgram(): Promise<ApiProductStrategyIterationProgramInitialization> {
  return request<ApiProductStrategyIterationProgramInitialization>(`${ITERATION_PROGRAM_PATH}/initialize`, {
    method: "POST",
  });
}
