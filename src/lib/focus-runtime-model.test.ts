import { describe, expect, it } from "vitest";
import type { ApiSession, WechatAgentBatchStatus } from "@/lib/api/types";
import {
  clampProgress,
  formatCountdown,
  formatRatioPercent,
  getBatchProgress,
  hasBatchSnapshot,
  parseServerUtcDate,
  resolveSessionRemainingSeconds,
  sourceCoverageClass,
  sourceCoverageLabel,
} from "@/lib/focus-runtime-model";

const batch = (overrides: Partial<WechatAgentBatchStatus> = {}) =>
  ({
    running: false,
    total_segments: 0,
    current_segment_index: 0,
    finished_at: null,
    submitted: 0,
    submitted_new: 0,
    deduplicated_existing: 0,
    skipped_seen: 0,
    failed: 0,
    ...overrides,
  }) as WechatAgentBatchStatus;

describe("focus runtime model", () => {
  it("formats and clamps timer presentation values", () => {
    expect(formatCountdown(65)).toBe("01:05");
    expect(formatCountdown(-5)).toBe("00:00");
    expect(clampProgress(Number.NaN)).toBe(0);
    expect(clampProgress(140)).toBe(100);
    expect(formatRatioPercent(1.2)).toBe("100%");
  });

  it("treats server timestamps without offsets as UTC", () => {
    expect(parseServerUtcDate("2026-06-13T12:00:00")).toBe(Date.parse("2026-06-13T12:00:00Z"));
  });

  it("prefers authoritative remaining seconds and otherwise restores a running window", () => {
    const base = {
      duration_minutes: 25,
      start_time: "2026-06-13T12:00:00Z",
      status: "running",
    } as ApiSession;
    expect(resolveSessionRemainingSeconds({ ...base, remaining_seconds: 321 }, 25)).toBe(321);
    expect(
      resolveSessionRemainingSeconds(
        { ...base, elapsed_seconds: 120, current_window_started_at: "2026-06-13T12:05:00Z" },
        25,
        Date.parse("2026-06-13T12:06:00Z"),
      ),
    ).toBe(1320);
  });

  it("uses bounded progress for running and completed collection batches", () => {
    expect(hasBatchSnapshot(null)).toBe(false);
    expect(hasBatchSnapshot(batch({ submitted_new: 1 }))).toBe(true);
    expect(getBatchProgress(batch({ running: true, total_segments: 10, current_segment_index: 0 }))).toBe(10);
    expect(getBatchProgress(batch({ total_segments: 10, finished_at: "2026-06-13T12:00:00Z" }))).toBe(100);
  });

  it("maps collector health to semantic theme classes", () => {
    expect(sourceCoverageLabel("good")).toBe("覆盖稳定");
    expect(sourceCoverageLabel(undefined)).toBe("待配置");
    expect(sourceCoverageClass("poor")).toContain("af-chip-danger");
    expect(sourceCoverageClass("watch")).not.toContain("bg-amber-50");
  });
});
