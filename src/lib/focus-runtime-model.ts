import type { ApiSession, CollectorDaemonStatus, WechatAgentBatchStatus } from "@/lib/api/types";

export const FOCUS_DURATIONS = [25, 50] as const;
export type FocusDuration = (typeof FOCUS_DURATIONS)[number];

export function formatCountdown(totalSeconds: number): string {
  const safeSeconds = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  const minutes = Math.floor(safeSeconds / 60).toString().padStart(2, "0");
  const seconds = (safeSeconds % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}

export function clampProgress(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, value));
}

export function parseServerUtcDate(value: string | null | undefined): number {
  const text = String(value || "").trim();
  if (!text) return Number.NaN;
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/i.test(text) ? text : `${text}Z`;
  return Date.parse(normalized);
}

export function resolveSessionRemainingSeconds(
  session: ApiSession,
  fallbackDuration: FocusDuration,
  nowMs = Date.now(),
): number {
  const totalSeconds = Math.max(60, Number(session.duration_minutes || fallbackDuration) * 60);
  if (typeof session.remaining_seconds === "number" && Number.isFinite(session.remaining_seconds)) {
    return Math.max(0, Math.round(session.remaining_seconds));
  }

  const elapsedSeconds =
    typeof session.elapsed_seconds === "number" && Number.isFinite(session.elapsed_seconds)
      ? Math.max(0, Math.round(session.elapsed_seconds))
      : 0;
  if (session.status !== "running") {
    return Math.max(0, totalSeconds - elapsedSeconds);
  }

  const currentWindowStartMs = parseServerUtcDate(session.current_window_started_at || session.start_time);
  if (Number.isNaN(currentWindowStartMs)) {
    return Math.max(0, totalSeconds - elapsedSeconds);
  }

  const liveElapsed = Math.max(0, Math.floor((nowMs - currentWindowStartMs) / 1000));
  return Math.max(0, totalSeconds - elapsedSeconds - liveElapsed);
}

export function hasBatchSnapshot(status: WechatAgentBatchStatus | null): boolean {
  if (!status) return false;
  return Boolean(
    status.total_segments ||
      status.finished_at ||
      status.running ||
      status.submitted ||
      status.submitted_new ||
      status.deduplicated_existing ||
      status.skipped_seen ||
      status.failed,
  );
}

export function getBatchProgress(status: WechatAgentBatchStatus | null): number {
  if (!status || status.total_segments <= 0) return 0;
  if (status.running) {
    return Math.max(8, Math.min(96, Math.round((Math.max(status.current_segment_index, 1) / status.total_segments) * 100)));
  }
  return status.finished_at ? 100 : 0;
}

export function formatRatioPercent(value: number | null | undefined): string {
  const safe = Math.max(0, Math.min(1, Number(value || 0)));
  return `${Math.round(safe * 100)}%`;
}

export function sourceCoverageLabel(state: CollectorDaemonStatus["coverage_state"] | undefined): string {
  if (state === "good") return "覆盖稳定";
  if (state === "watch") return "需观察";
  if (state === "poor") return "需处理";
  return "待配置";
}

export function sourceCoverageClass(state: CollectorDaemonStatus["coverage_state"] | undefined): string {
  if (state === "good") return "af-chip af-chip-success rounded-full px-3 py-1 text-xs font-medium";
  if (state === "watch") return "af-chip af-chip-warning rounded-full px-3 py-1 text-xs font-medium";
  if (state === "poor") return "af-chip af-chip-danger rounded-full px-3 py-1 text-xs font-medium";
  return "af-chip rounded-full px-3 py-1 text-xs font-medium";
}
