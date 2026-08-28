export const FOCUS_WECHAT_BATCH_OVERRIDE_KEY = "anti_fomo_focus_wechat_batch_override";

export interface FocusWechatBatchConfig {
  totalItems: number;
  segmentItems: number;
  startBatchIndex: number;
  runOnceMaxItems: number;
  maxCollectPerCycle: number;
  overrideActive: boolean;
  source: "default" | "query" | "storage" | "query+storage";
}

export const DEFAULT_FOCUS_WECHAT_BATCH_CONFIG: FocusWechatBatchConfig = {
  totalItems: 12,
  segmentItems: 6,
  startBatchIndex: 0,
  runOnceMaxItems: 6,
  maxCollectPerCycle: 12,
  overrideActive: false,
  source: "default",
};

type RawConfigRecord = Record<string, unknown>;

function clampInteger(value: unknown, fallback: number, min: number, max: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, Math.trunc(parsed)));
}

function parseStorageValue(storageValue?: string | null): RawConfigRecord {
  if (!storageValue) {
    return {};
  }
  try {
    const parsed = JSON.parse(storageValue) as unknown;
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? (parsed as RawConfigRecord)
      : {};
  } catch {
    return {};
  }
}

function readFirstQueryValue(params: URLSearchParams, names: string[]): string | null {
  for (const name of names) {
    const value = params.get(name);
    if (value !== null && value.trim() !== "") {
      return value;
    }
  }
  return null;
}

function readFirstRecordValue(record: RawConfigRecord, names: string[]): unknown {
  for (const name of names) {
    if (record[name] !== undefined && record[name] !== null && String(record[name]).trim() !== "") {
      return record[name];
    }
  }
  return undefined;
}

export function parseFocusWechatBatchConfig(options?: {
  search?: string | URLSearchParams | null;
  storageValue?: string | null;
}): FocusWechatBatchConfig {
  const params =
    options?.search instanceof URLSearchParams
      ? options.search
      : new URLSearchParams(String(options?.search || "").replace(/^\?/, ""));
  const storage = parseStorageValue(options?.storageValue);

  const hasQueryOverride = [
    "focusWechatTotalItems",
    "wechatItems",
    "focusWechatSegmentItems",
    "wechatSegmentItems",
    "focusWechatStartBatchIndex",
    "wechatStartBatchIndex",
    "focusWechatRunOnceMaxItems",
    "wechatRunOnceMaxItems",
    "focusCollectorMaxPerCycle",
  ].some((key) => params.has(key));
  const hasStorageOverride = Object.keys(storage).length > 0;

  const source: FocusWechatBatchConfig["source"] =
    hasQueryOverride && hasStorageOverride
      ? "query+storage"
      : hasQueryOverride
        ? "query"
        : hasStorageOverride
          ? "storage"
          : "default";

  const totalItems = clampInteger(
    readFirstQueryValue(params, ["focusWechatTotalItems", "wechatItems"]) ??
      readFirstRecordValue(storage, ["totalItems", "total_items"]),
    DEFAULT_FOCUS_WECHAT_BATCH_CONFIG.totalItems,
    1,
    60,
  );
  const segmentItems = clampInteger(
    readFirstQueryValue(params, ["focusWechatSegmentItems", "wechatSegmentItems"]) ??
      readFirstRecordValue(storage, ["segmentItems", "segment_items"]),
    Math.min(DEFAULT_FOCUS_WECHAT_BATCH_CONFIG.segmentItems, totalItems),
    1,
    totalItems,
  );
  const startBatchIndex = clampInteger(
    readFirstQueryValue(params, ["focusWechatStartBatchIndex", "wechatStartBatchIndex"]) ??
      readFirstRecordValue(storage, ["startBatchIndex", "start_batch_index"]),
    DEFAULT_FOCUS_WECHAT_BATCH_CONFIG.startBatchIndex,
    0,
    5000,
  );
  const runOnceMaxItems = clampInteger(
    readFirstQueryValue(params, ["focusWechatRunOnceMaxItems", "wechatRunOnceMaxItems"]) ??
      readFirstRecordValue(storage, ["runOnceMaxItems", "run_once_max_items"]),
    Math.min(DEFAULT_FOCUS_WECHAT_BATCH_CONFIG.runOnceMaxItems, totalItems),
    1,
    60,
  );
  const maxCollectPerCycle = clampInteger(
    readFirstQueryValue(params, ["focusCollectorMaxPerCycle"]) ??
      readFirstRecordValue(storage, ["maxCollectPerCycle", "max_collect_per_cycle"]),
    DEFAULT_FOCUS_WECHAT_BATCH_CONFIG.maxCollectPerCycle,
    1,
    100,
  );

  return {
    totalItems,
    segmentItems,
    startBatchIndex,
    runOnceMaxItems,
    maxCollectPerCycle,
    overrideActive: source !== "default",
    source,
  };
}

export function resolveFocusWechatBatchConfigFromWindow(): FocusWechatBatchConfig {
  if (typeof window === "undefined") {
    return DEFAULT_FOCUS_WECHAT_BATCH_CONFIG;
  }
  return parseFocusWechatBatchConfig({
    search: window.location.search,
    storageValue: window.localStorage.getItem(FOCUS_WECHAT_BATCH_OVERRIDE_KEY),
  });
}
