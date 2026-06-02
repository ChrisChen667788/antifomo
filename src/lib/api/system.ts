import { request } from "@/lib/api/client";
import type {
  ApiHealth,
  LLMConfig,
  LLMDryRunResult,
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
