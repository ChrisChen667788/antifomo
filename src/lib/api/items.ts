import type { AppLanguage } from "@/lib/preferences";
import { request } from "@/lib/api/client";
import type {
  ApiBatchCreateResponse,
  ApiBatchReprocessResponse,
  ApiCollectorIngestAttempt,
  ApiFeedbackResponse,
  ApiItem,
  ApiItemDiagnostics,
  ApiItemInterpretation,
  ApiPreferenceBoostResponse,
  ApiPreferenceSummary,
  FeedbackType,
} from "@/lib/api/types";

export function listItems(
  limit = 30,
  options?: {
    mode?: "normal" | "focus";
    goalText?: string;
    includePending?: boolean;
    itemIds?: string[];
  },
): Promise<{ items: ApiItem[] }> {
  const mode = options?.mode === "focus" ? "focus" : "normal";
  const params = new URLSearchParams({
    limit: String(limit),
    mode,
    include_pending: String(options?.includePending ?? true),
  });
  if (options?.goalText?.trim()) {
    params.set("goal_text", options.goalText.trim());
  }
  const itemIds = (options?.itemIds || []).map((itemId) => itemId.trim()).filter(Boolean);
  if (itemIds.length) {
    params.set("item_ids", itemIds.join(","));
  }
  return request<{ items: ApiItem[] }>(`/api/items?${params.toString()}`);
}

export function listSavedItems(limit = 30): Promise<{ items: ApiItem[] }> {
  return request<{ items: ApiItem[] }>(`/api/items/saved?limit=${limit}`);
}

export function getItem(itemId: string): Promise<ApiItem> {
  return request<ApiItem>(`/api/items/${itemId}`);
}

export function getPreferenceSummary(): Promise<ApiPreferenceSummary> {
  return request<ApiPreferenceSummary>("/api/preferences/summary");
}

export function resetPreferences(scope: "all" | "topics" | "sources" = "all"): Promise<ApiPreferenceSummary> {
  return request<ApiPreferenceSummary>("/api/preferences/reset", {
    method: "POST",
    body: JSON.stringify({ scope }),
  });
}

export function boostPreference(payload: {
  dimension: "topic" | "source";
  key: string;
  delta?: number;
}): Promise<ApiPreferenceBoostResponse> {
  return request<ApiPreferenceBoostResponse>("/api/preferences/boost", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getItemDiagnostics(itemId: string): Promise<ApiItemDiagnostics> {
  return request<ApiItemDiagnostics>(`/api/items/${itemId}/diagnostics`);
}

export function getCollectorItemAttempts(itemId: string): Promise<ApiCollectorIngestAttempt[]> {
  return request<ApiCollectorIngestAttempt[]>(`/api/collector/items/${itemId}/attempts`);
}

export function createItem(payload: {
  source_type: "url" | "text" | "plugin";
  source_url?: string;
  title?: string;
  raw_content?: string;
  output_language?: AppLanguage;
}): Promise<ApiItem> {
  return request<ApiItem>("/api/items", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createItemsBatch(payload: {
  source_type?: "url" | "plugin";
  urls: string[];
  deduplicate?: boolean;
  output_language?: AppLanguage;
}): Promise<ApiBatchCreateResponse> {
  return request<ApiBatchCreateResponse>("/api/items/batch", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function submitFeedback(itemId: string, feedbackType: FeedbackType): Promise<ApiFeedbackResponse> {
  return request<ApiFeedbackResponse>(`/api/items/${itemId}/feedback`, {
    method: "POST",
    body: JSON.stringify({ feedback_type: feedbackType }),
  });
}

export function reprocessItem(
  itemId: string,
  payload?: {
    output_language?: AppLanguage;
  },
): Promise<{
  item_id: string;
  status: string;
  output_language?: AppLanguage;
}> {
  return request(`/api/items/${itemId}/reprocess`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
}

export function reprocessItemsBatch(payload: {
  item_ids: string[];
  output_language?: AppLanguage;
  failed_only?: boolean;
}): Promise<ApiBatchReprocessResponse> {
  return request<ApiBatchReprocessResponse>("/api/items/reprocess-batch", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function interpretItem(
  itemId: string,
  payload?: {
    output_language?: AppLanguage;
  },
): Promise<ApiItemInterpretation> {
  return request<ApiItemInterpretation>(`/api/items/${itemId}/interpret`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
}

export function addItemToKnowledge(
  itemId: string,
  payload?: {
    title?: string;
    content?: string;
    output_language?: AppLanguage;
  },
): Promise<{
  entry_id: string;
  item_id: string;
  title: string;
  content: string;
  source_domain: string | null;
  created_at: string;
}> {
  return request(`/api/items/${itemId}/knowledge`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
}
