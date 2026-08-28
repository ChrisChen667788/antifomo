import type { AppLanguage } from "@/lib/preferences";
import { request } from "@/lib/api/client";
import type {
  CollectorBrowserExtensionVerifyResult,
  CollectorDailySummary,
  CollectorDaemonCommandResult,
  CollectorDaemonConfig,
  CollectorDaemonStatus,
  CollectorExternalIngestResponse,
  CollectorFailedList,
  CollectorFeedPullResponse,
  CollectorFeedSource,
  CollectorFeedSourceList,
  CollectorProcessPendingResult,
  CollectorRetryFailedResult,
  CollectorSource,
  CollectorSourceImportResponse,
  CollectorSourceList,
  CollectorStatus,
  CollectorWechatFavoriteImportBatch,
  CollectorWechatFavoriteImportBatchList,
  CollectorWechatFavoriteImportResponse,
  CollectorWechatFavoritePreviewResponse,
  WechatAgentBatchCommandResult,
  WechatAgentBatchStatus,
  WechatAgentCapturePreview,
  WechatAgentCommandResult,
  WechatAgentConfig,
  WechatAgentDedupSummary,
  WechatAgentHealth,
  WechatAgentOCRPreview,
  WechatAgentSelfHealResult,
  WechatAgentStatus,
} from "@/lib/api/types";

export function getCollectorStatus(): Promise<CollectorStatus> {
  return request<CollectorStatus>("/api/collector/status");
}

export function getCollectorDaemonStatus(): Promise<CollectorDaemonStatus> {
  return request<CollectorDaemonStatus>("/api/collector/daemon/status");
}

export function getCollectorDaemonConfig(): Promise<CollectorDaemonConfig> {
  return request<CollectorDaemonConfig>("/api/collector/daemon/config");
}

export function updateCollectorDaemonConfig(payload: {
  wechat_clipboard_auto_import?: boolean;
  wechat_export_directory_auto_import?: boolean;
  wechat_export_directory_path?: string;
}): Promise<CollectorDaemonConfig> {
  return request<CollectorDaemonConfig>("/api/collector/daemon/config", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function verifyCollectorBrowserExtension(): Promise<CollectorBrowserExtensionVerifyResult> {
  return request<CollectorBrowserExtensionVerifyResult>("/api/collector/browser-extension/verify", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function startCollectorDaemon(): Promise<CollectorDaemonCommandResult> {
  return request<CollectorDaemonCommandResult>("/api/collector/daemon/start", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function stopCollectorDaemon(): Promise<CollectorDaemonCommandResult> {
  return request<CollectorDaemonCommandResult>("/api/collector/daemon/stop", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function runCollectorDaemonOnce(payload?: {
  output_language?: AppLanguage;
  max_collect_per_cycle?: number;
}): Promise<CollectorDaemonCommandResult> {
  const params = new URLSearchParams();
  if (payload?.output_language) {
    params.set("output_language", payload.output_language);
  }
  if (payload?.max_collect_per_cycle) {
    params.set("max_collect_per_cycle", String(payload.max_collect_per_cycle));
  }
  const query = params.toString();
  const path = query
    ? `/api/collector/daemon/run-once?${query}`
    : "/api/collector/daemon/run-once";
  return request<CollectorDaemonCommandResult>(path, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function getWechatAgentStatus(): Promise<WechatAgentStatus> {
  return request<WechatAgentStatus>("/api/collector/wechat-agent/status");
}

export function getWechatAgentConfig(): Promise<WechatAgentConfig> {
  return request<WechatAgentConfig>("/api/collector/wechat-agent/config");
}

export function updateWechatAgentConfig(
  payload: Partial<WechatAgentConfig>,
): Promise<WechatAgentConfig> {
  return request<WechatAgentConfig>("/api/collector/wechat-agent/config", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function getWechatAgentCapturePreview(): Promise<WechatAgentCapturePreview> {
  return request<WechatAgentCapturePreview>("/api/collector/wechat-agent/preview-capture");
}

export function getWechatAgentOCRPreview(payload?: {
  output_language?: AppLanguage;
}): Promise<WechatAgentOCRPreview> {
  const params = new URLSearchParams();
  if (payload?.output_language) {
    params.set("output_language", payload.output_language);
  }
  const query = params.toString();
  const path = query
    ? `/api/collector/wechat-agent/preview-ocr?${query}`
    : "/api/collector/wechat-agent/preview-ocr";
  return request<WechatAgentOCRPreview>(path);
}

export function getWechatAgentHealth(payload?: {
  stale_minutes?: number;
}): Promise<WechatAgentHealth> {
  const params = new URLSearchParams();
  if (payload?.stale_minutes) {
    params.set("stale_minutes", String(payload.stale_minutes));
  }
  const query = params.toString();
  const path = query
    ? `/api/collector/wechat-agent/health?${query}`
    : "/api/collector/wechat-agent/health";
  return request<WechatAgentHealth>(path);
}

export function runWechatAgentSelfHeal(payload?: {
  force?: boolean;
}): Promise<WechatAgentSelfHealResult> {
  const params = new URLSearchParams();
  if (payload?.force) {
    params.set("force", "true");
  }
  const query = params.toString();
  const path = query
    ? `/api/collector/wechat-agent/self-heal?${query}`
    : "/api/collector/wechat-agent/self-heal";
  return request<WechatAgentSelfHealResult>(path, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function startWechatAgent(): Promise<WechatAgentCommandResult> {
  return request<WechatAgentCommandResult>("/api/collector/wechat-agent/start", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function stopWechatAgent(): Promise<WechatAgentCommandResult> {
  return request<WechatAgentCommandResult>("/api/collector/wechat-agent/stop", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function runWechatAgentOnce(payload?: {
  output_language?: AppLanguage;
  max_items?: number;
  start_batch_index?: number;
  wait?: boolean;
}): Promise<WechatAgentCommandResult> {
  const params = new URLSearchParams();
  if (payload?.output_language) {
    params.set("output_language", payload.output_language);
  }
  if (payload?.max_items) {
    params.set("max_items", String(payload.max_items));
  }
  if (payload?.start_batch_index !== undefined) {
    params.set("start_batch_index", String(payload.start_batch_index));
  }
  if (payload?.wait) {
    params.set("wait", "true");
  }
  const query = params.toString();
  const path = query
    ? `/api/collector/wechat-agent/run-once?${query}`
    : "/api/collector/wechat-agent/run-once";
  return request<WechatAgentCommandResult>(path, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function getWechatAgentBatchStatus(): Promise<WechatAgentBatchStatus> {
  return request<WechatAgentBatchStatus>("/api/collector/wechat-agent/batch-status");
}

export function getWechatAgentDedupSummary(): Promise<WechatAgentDedupSummary> {
  return request<WechatAgentDedupSummary>("/api/collector/wechat-agent/dedup-summary");
}

export function resetWechatAgentDedupSummary(payload?: {
  clear_runs?: boolean;
}): Promise<WechatAgentDedupSummary> {
  const params = new URLSearchParams();
  if (payload?.clear_runs) {
    params.set("clear_runs", "true");
  }
  const query = params.toString();
  const path = query
    ? `/api/collector/wechat-agent/reset-dedup?${query}`
    : "/api/collector/wechat-agent/reset-dedup";
  return request<WechatAgentDedupSummary>(path, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function runWechatAgentBatch(payload?: {
  output_language?: AppLanguage;
  total_items?: number;
  segment_items?: number;
  start_batch_index?: number;
}): Promise<WechatAgentBatchCommandResult> {
  const params = new URLSearchParams();
  if (payload?.output_language) {
    params.set("output_language", payload.output_language);
  }
  if (payload?.total_items) {
    params.set("total_items", String(payload.total_items));
  }
  if (payload?.segment_items) {
    params.set("segment_items", String(payload.segment_items));
  }
  if (payload?.start_batch_index !== undefined) {
    params.set("start_batch_index", String(payload.start_batch_index));
  }
  const query = params.toString();
  const path = query
    ? `/api/collector/wechat-agent/run-batch?${query}`
    : "/api/collector/wechat-agent/run-batch";
  return request<WechatAgentBatchCommandResult>(path, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function processCollectorPending(limit = 20): Promise<CollectorProcessPendingResult> {
  return request<CollectorProcessPendingResult>(`/api/collector/process-pending?limit=${limit}`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function listCollectorFailed(limit = 20): Promise<CollectorFailedList> {
  return request<CollectorFailedList>(`/api/collector/failed?limit=${limit}`);
}

export function retryCollectorFailed(limit = 20): Promise<CollectorRetryFailedResult> {
  return request<CollectorRetryFailedResult>(`/api/collector/retry-failed?limit=${limit}`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function getCollectorDailySummary(
  hours = 24,
  limit = 12,
): Promise<CollectorDailySummary> {
  return request<CollectorDailySummary>(`/api/collector/daily-summary?hours=${hours}&limit=${limit}`);
}

export function listCollectorSources(
  limit = 200,
  options?: { enabledOnly?: boolean },
): Promise<CollectorSourceList> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (options?.enabledOnly) {
    params.set("enabled_only", "true");
  }
  return request<CollectorSourceList>(`/api/collector/sources?${params.toString()}`);
}

export function createCollectorSource(payload: {
  source_url: string;
  note?: string;
  enabled?: boolean;
}): Promise<CollectorSource> {
  return request<CollectorSource>("/api/collector/sources", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function importCollectorSources(payload: {
  urls: string[];
  enabled?: boolean;
}): Promise<CollectorSourceImportResponse> {
  return request<CollectorSourceImportResponse>("/api/collector/sources/import", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateCollectorSource(
  sourceId: string,
  payload: { enabled?: boolean; note?: string | null },
): Promise<CollectorSource> {
  return request<CollectorSource>(`/api/collector/sources/${sourceId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteCollectorSource(sourceId: string): Promise<void> {
  return request<void>(`/api/collector/sources/${sourceId}`, {
    method: "DELETE",
  });
}

export function listCollectorFeedSources(feedType = "rss"): Promise<CollectorFeedSourceList> {
  const params = new URLSearchParams();
  if (feedType) params.set("feed_type", feedType);
  return request<CollectorFeedSourceList>(`/api/collector/feeds?${params.toString()}`);
}

export function createCollectorRssSource(payload: {
  source_url: string;
  title?: string;
  note?: string;
  pull_immediately?: boolean;
  output_language?: AppLanguage;
  limit?: number;
}): Promise<CollectorFeedSource> {
  return request<CollectorFeedSource>("/api/collector/rss/sources", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function pullCollectorRssFeeds(payload?: {
  feed_id?: string;
  limit?: number;
  output_language?: AppLanguage;
}): Promise<CollectorFeedPullResponse> {
  return request<CollectorFeedPullResponse>("/api/collector/rss/pull", {
    method: "POST",
    body: JSON.stringify(payload || {}),
  });
}

export function ingestNewsletter(payload: {
  title: string;
  sender?: string;
  source_url?: string;
  raw_content: string;
  output_language?: AppLanguage;
}): Promise<CollectorExternalIngestResponse> {
  return request<CollectorExternalIngestResponse>("/api/collector/newsletter/ingest", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function uploadCollectorFile(payload: {
  file_name: string;
  mime_type: string;
  file_base64: string;
  extracted_text?: string;
  title?: string;
  source_url?: string;
  output_language?: AppLanguage;
}): Promise<CollectorExternalIngestResponse> {
  return request<CollectorExternalIngestResponse>("/api/collector/files/upload", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function ingestYouTubeTranscript(payload: {
  video_url: string;
  transcript_text?: string;
  title?: string;
  output_language?: AppLanguage;
}): Promise<CollectorExternalIngestResponse> {
  return request<CollectorExternalIngestResponse>("/api/collector/youtube/ingest", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function importWechatFavorites(payload: {
  export_text?: string;
  urls?: string[];
  output_language?: AppLanguage;
  limit?: number;
  include_text_blocks?: boolean;
  process_immediately?: boolean;
}): Promise<CollectorWechatFavoriteImportResponse> {
  return request<CollectorWechatFavoriteImportResponse>("/api/collector/wechat-favorites/import", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function previewWechatFavorites(payload: {
  export_text?: string;
  urls?: string[];
  limit?: number;
  include_text_blocks?: boolean;
}): Promise<CollectorWechatFavoritePreviewResponse> {
  return request<CollectorWechatFavoritePreviewResponse>("/api/collector/wechat-favorites/preview", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listWechatFavoriteImportBatches(options?: {
  limit?: number;
  includeReviewed?: boolean;
}): Promise<CollectorWechatFavoriteImportBatchList> {
  const params = new URLSearchParams({
    limit: String(options?.limit ?? 5),
    include_reviewed: String(options?.includeReviewed ?? false),
  });
  return request<CollectorWechatFavoriteImportBatchList>(
    `/api/collector/wechat-favorites/batches?${params.toString()}`,
  );
}

export function getWechatFavoriteImportBatch(
  batchId: string,
): Promise<CollectorWechatFavoriteImportBatch> {
  return request<CollectorWechatFavoriteImportBatch>(
    `/api/collector/wechat-favorites/batches/${batchId}`,
  );
}
