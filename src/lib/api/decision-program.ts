import { request } from "@/lib/api/client";
import type {
  DecisionProgramOverview,
  DecisionReleaseCandidate,
  DecisionReleaseCandidatePreview,
  DecisionVerticalPack,
} from "@/lib/api/type-contracts/decision-program";


export function getDecisionProgramOverview(): Promise<DecisionProgramOverview> {
  return request<DecisionProgramOverview>("/api/decision-studio/program/overview");
}

export function freezeDecisionReleaseCandidate(payload: {
  version: "2.0.7";
  manifest: Record<string, unknown>;
  validation_run_ids?: string[];
  external_attestations?: Record<string, unknown>;
}): Promise<DecisionReleaseCandidate> {
  return request<DecisionReleaseCandidate>("/api/decision-studio/program/release-candidates", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function previewDecisionReleaseCandidate(payload: {
  version: "2.0.7";
  manifest: Record<string, unknown>;
  validation_run_ids?: string[];
  external_attestations?: Record<string, unknown>;
}): Promise<DecisionReleaseCandidatePreview> {
  return request<DecisionReleaseCandidatePreview>("/api/decision-studio/program/release-candidates/preview", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getDecisionVerticalPacks(): Promise<DecisionVerticalPack[]> {
  return request<DecisionVerticalPack[]>("/api/decision-studio/program/vertical-packs");
}

export function seedDecisionVerticalPacks(): Promise<DecisionVerticalPack[]> {
  return request<DecisionVerticalPack[]>("/api/decision-studio/program/vertical-packs/seed", {
    method: "POST",
  });
}
