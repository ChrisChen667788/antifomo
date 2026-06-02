import type { CollectorDaemonStatus } from "@/lib/api/types";
import type { AppLanguage } from "@/lib/preferences";

export function pickText(
  language: AppLanguage,
  mapping: Partial<Record<AppLanguage, string>>,
  fallback: string,
): string {
  if (mapping[language]) return mapping[language] as string;
  if (language === "zh-TW" && mapping["zh-CN"]) return mapping["zh-CN"] as string;
  if (mapping.en) return mapping.en as string;
  return fallback;
}

export function formatTs(value: string | null): string {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

export function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return "-";
  const safe = Math.max(0, Math.floor(seconds));
  const h = Math.floor(safe / 3600);
  const m = Math.floor((safe % 3600) / 60);
  const s = safe % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export function formatPercent(value: number | null | undefined): string {
  const safe = Math.max(0, Math.min(1, Number(value || 0)));
  return `${Math.round(safe * 100)}%`;
}

export function daemonCoverageLabel(
  language: AppLanguage,
  state: CollectorDaemonStatus["coverage_state"] | undefined,
): string {
  if (state === "good") {
    return pickText(language, { "zh-CN": "覆盖稳定", "zh-TW": "覆蓋穩定", en: "Stable" }, "Stable");
  }
  if (state === "watch") {
    return pickText(language, { "zh-CN": "需观察", "zh-TW": "需觀察", en: "Watch" }, "Watch");
  }
  if (state === "poor") {
    return pickText(language, { "zh-CN": "需处理", "zh-TW": "需處理", en: "Needs attention" }, "Needs attention");
  }
  return pickText(language, { "zh-CN": "待配置", "zh-TW": "待配置", en: "Idle" }, "Idle");
}

export function daemonCoverageClass(state: CollectorDaemonStatus["coverage_state"] | undefined): string {
  if (state === "good") return "af-chip-success";
  if (state === "watch") return "af-chip-warning";
  if (state === "poor") return "af-chip-danger";
  return "border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] text-[var(--af-text-secondary)]";
}

export function shortText(value: string | null, maxLength = 96): string {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (!text) return "-";
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 1)}…`;
}

export function formatBytes(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  const size = Number(value);
  if (size < 1024) return `${size} B`;
  const kb = size / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(2)} MB`;
}

export function formatPointPairs<T extends Record<string, number>>(
  points: T[] | undefined,
  xKey: keyof T,
  yKey: keyof T,
): string {
  if (!Array.isArray(points) || !points.length) return "";
  return points
    .map((point) => `${Number(point[xKey]) || 0}:${Number(point[yKey]) || 0}`)
    .join(", ");
}

export function parsePointPairs(
  value: string,
  options: {
    xKey: string;
    yKey: string;
  },
): Array<Record<string, number>> | null {
  const { xKey, yKey } = options;
  const parts = String(value || "")
    .split(/[,\n]+/)
    .map((entry) => entry.trim())
    .filter(Boolean);
  if (!parts.length) return [];
  const parsed: Array<Record<string, number>> = [];
  for (const part of parts) {
    const [xRaw, yRaw] = part.split(":").map((entry) => entry.trim());
    const x = Number.parseInt(xRaw || "", 10);
    const y = Number.parseInt(yRaw || "", 10);
    if (Number.isNaN(x) || Number.isNaN(y)) {
      return null;
    }
    parsed.push({ [xKey]: x, [yKey]: y });
  }
  return parsed;
}
