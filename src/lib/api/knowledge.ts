import { request } from "@/lib/api/client";
import type {
  ApiKnowledgeAccountDetail,
  ApiKnowledgeAccountDigest,
  ApiKnowledgeDashboard,
  ApiKnowledgeEntry,
  ApiKnowledgeMarkdown,
  ApiKnowledgeMergePreview,
  ApiKnowledgeOpportunity,
  ApiKnowledgeRule,
} from "@/lib/api/types";

export function listKnowledgeEntries(
  limit = 30,
  options?: {
    itemId?: string;
    focusReferenceOnly?: boolean;
    sourceDomain?: string;
    collectionName?: string;
    query?: string;
  },
): Promise<{ items: ApiKnowledgeEntry[] }> {
  const params = new URLSearchParams({
    limit: String(limit),
  });
  if (options?.itemId) {
    params.set("item_id", options.itemId);
  }
  if (options?.focusReferenceOnly) {
    params.set("focus_reference_only", "true");
  }
  if (options?.sourceDomain) {
    params.set("source_domain", options.sourceDomain);
  }
  if (options?.collectionName) {
    params.set("collection_name", options.collectionName);
  }
  if (options?.query) {
    params.set("query", options.query);
  }
  return request<{ items: ApiKnowledgeEntry[] }>(`/api/knowledge?${params.toString()}`);
}

export function getKnowledgeEntry(entryId: string): Promise<ApiKnowledgeEntry> {
  return request<ApiKnowledgeEntry>(`/api/knowledge/${entryId}`);
}

export function getKnowledgeDashboard(): Promise<ApiKnowledgeDashboard> {
  return request<ApiKnowledgeDashboard>("/api/knowledge/dashboard");
}

export function listKnowledgeAccounts(
  limit = 20,
  options?: { query?: string },
): Promise<{ items: ApiKnowledgeAccountDigest[] }> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (options?.query) {
    params.set("query", options.query);
  }
  return request<{ items: ApiKnowledgeAccountDigest[] }>(`/api/knowledge/accounts?${params.toString()}`);
}

export function getKnowledgeAccountDetail(accountSlug: string): Promise<ApiKnowledgeAccountDetail> {
  return request<ApiKnowledgeAccountDetail>(`/api/knowledge/accounts/${encodeURIComponent(accountSlug)}`);
}

export function listKnowledgeOpportunities(
  limit = 30,
  options?: { accountSlug?: string },
): Promise<{ items: ApiKnowledgeOpportunity[] }> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (options?.accountSlug) {
    params.set("account_slug", options.accountSlug);
  }
  return request<{ items: ApiKnowledgeOpportunity[] }>(`/api/knowledge/opportunities?${params.toString()}`);
}

export function getKnowledgeMarkdown(entryId: string): Promise<ApiKnowledgeMarkdown> {
  return request<ApiKnowledgeMarkdown>(`/api/knowledge/${entryId}/markdown`);
}

export function listRelatedKnowledgeEntries(
  entryId: string,
  limit = 4,
): Promise<{ items: ApiKnowledgeEntry[] }> {
  const params = new URLSearchParams({
    limit: String(limit),
  });
  return request<{ items: ApiKnowledgeEntry[] }>(`/api/knowledge/${entryId}/related?${params.toString()}`);
}

export function updateKnowledgeEntry(
  entryId: string,
  payload: {
    title?: string;
    content?: string;
    collection_name?: string | null;
    is_pinned?: boolean;
    is_focus_reference?: boolean;
    metadata_payload?: Record<string, unknown> | null;
  },
): Promise<ApiKnowledgeEntry> {
  return request<ApiKnowledgeEntry>(`/api/knowledge/${entryId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function resolveKnowledgeReviewQueueItem(
  entryId: string,
  reviewId: string,
  payload: {
    action: "open" | "resolved" | "deferred";
    note?: string;
  },
): Promise<ApiKnowledgeEntry> {
  return request<ApiKnowledgeEntry>(`/api/knowledge/${entryId}/review-queue/${encodeURIComponent(reviewId)}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function mergeKnowledgeEntries(payload: {
  entry_ids: string[];
  title?: string;
  content?: string;
}): Promise<ApiKnowledgeEntry> {
  return request<ApiKnowledgeEntry>("/api/knowledge/merge", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getKnowledgeMergePreview(payload: {
  entry_ids: string[];
  title?: string;
}): Promise<ApiKnowledgeMergePreview> {
  return request<ApiKnowledgeMergePreview>("/api/knowledge/merge/preview", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getKnowledgeRule(): Promise<ApiKnowledgeRule> {
  return request<ApiKnowledgeRule>("/api/knowledge/rules");
}

export function updateKnowledgeRule(
  payload: Partial<ApiKnowledgeRule>,
): Promise<ApiKnowledgeRule> {
  return request<ApiKnowledgeRule>("/api/knowledge/rules", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}
