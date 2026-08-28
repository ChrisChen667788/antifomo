import { request } from "@/lib/api/client";
import type {
  ApiHealth,
  InternalSkillGovernanceSnapshot,
  LLMConfig,
  LLMDryRunResult,
  ModelControlPlaneSnapshot,
  ReleaseReadinessSnapshot,
  StrongestModelUpgrade,
  SupportedModelScan,
} from "@/lib/api/types";

export function getApiHealth(): Promise<ApiHealth> {
  return request<ApiHealth>("/healthz");
}

export function getLLMConfig(): Promise<LLMConfig> {
  return request<LLMConfig>("/api/system/llm/config");
}

export function runLLMDryRun(payload: {
  prompt_name?: string;
  variables?: Record<string, string>;
}): Promise<LLMDryRunResult> {
  return request<LLMDryRunResult>("/api/system/llm/dry-run", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getModelControlPlane(): Promise<ModelControlPlaneSnapshot> {
  return request<ModelControlPlaneSnapshot>("/api/system/llm/control-plane");
}

export function scanSupportedModels(): Promise<SupportedModelScan> {
  return request<SupportedModelScan>("/api/system/llm/models/scan", {
    method: "POST",
  });
}

export function upgradeToStrongestModels(): Promise<StrongestModelUpgrade> {
  return request<StrongestModelUpgrade>("/api/system/llm/models/upgrade-strongest", {
    method: "POST",
  });
}

export function getInternalSkillGovernance(): Promise<InternalSkillGovernanceSnapshot> {
  return request<InternalSkillGovernanceSnapshot>("/api/system/internal-skills");
}

export function getReleaseReadiness(): Promise<ReleaseReadinessSnapshot> {
  return request<ReleaseReadinessSnapshot>("/api/system/release-readiness");
}
