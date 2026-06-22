
"use client";

import { CollectorOpsStatCard as StatCard } from "@/components/settings/collector-ops-stat-card";
import type { useCollectorOpsPanelController } from "@/components/settings/use-collector-ops-panel-controller";
import {
  formatDuration,
  formatTs,
} from "@/components/settings/collector-ops-panel-utils";

type CollectorOpsPanelController = ReturnType<typeof useCollectorOpsPanelController>;

type CollectorOpsWechatAgentStatusSectionProps = {
  controller: CollectorOpsPanelController;
  text: (key: string) => string;
};

export function CollectorOpsWechatAgentStatusSection({
  controller,
  text,
}: CollectorOpsWechatAgentStatusSectionProps) {
  const {
    wechatAgentStatus,
    wechatAgentHealth,
    wechatAgentDedupSummary,
    startingWechatAgent,
    stoppingWechatAgent,
    runningWechatAgentOnce,
    runningWechatAgentBatch,
    checkingWechatAgentHealth,
    healingWechatAgent,
    capturingWechatPreview,
    runningWechatOCRPreview,
    resettingWechatDedup,
    resettingWechatDedupHard,
    handleStartWechatAgent,
    handleStopWechatAgent,
    handleRunWechatAgentOnce,
    handleRunWechatAgentBatch,
    handleResetWechatDedup,
    handleCheckWechatAgentHealth,
    handleWechatAgentSelfHeal,
    handleWechatPreviewCapture,
    handleWechatPreviewOCR,
  } = controller;

  return (
    <>
      <p className="text-sm font-semibold text-[var(--af-text-primary)]">{text("wechatAgentTitle")}</p>
      <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">{text("wechatAgentHint")}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span
          className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
            wechatAgentStatus?.running
              ? "border af-chip-success"
              : "border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] text-[var(--af-text-secondary)]"
          }`}
        >
          {wechatAgentStatus?.running
            ? text("daemonRunning")
            : text("daemonStopped")}
        </span>
        <button
          type="button"
          onClick={() => void handleStartWechatAgent()}
          disabled={startingWechatAgent}
          className="af-btn af-btn-secondary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
        >
          {startingWechatAgent ? "..." : text("wechatAgentStart")}
        </button>
        <button
          type="button"
          onClick={() => void handleStopWechatAgent()}
          disabled={stoppingWechatAgent}
          className="af-btn af-btn-secondary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
        >
          {stoppingWechatAgent ? "..." : text("wechatAgentStop")}
        </button>
        <button
          type="button"
          onClick={() => void handleRunWechatAgentOnce()}
          disabled={runningWechatAgentOnce}
          className="af-btn af-btn-primary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
        >
          {runningWechatAgentOnce ? "..." : text("wechatAgentRunOnce")}
        </button>
        <button
          type="button"
          onClick={() => void handleRunWechatAgentBatch()}
          disabled={runningWechatAgentBatch}
          className="af-btn af-btn-secondary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
        >
          {runningWechatAgentBatch ? "..." : text("wechatAgentRunBatch")}
        </button>
        <button
          type="button"
          onClick={() => void handleCheckWechatAgentHealth()}
          disabled={checkingWechatAgentHealth}
          className="af-btn af-btn-secondary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
        >
          {checkingWechatAgentHealth ? "..." : text("wechatAgentHealthCheck")}
        </button>
        <button
          type="button"
          onClick={() => void handleWechatAgentSelfHeal()}
          disabled={healingWechatAgent}
          className="af-btn af-btn-secondary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
        >
          {healingWechatAgent ? "..." : text("wechatAgentSelfHeal")}
        </button>
        <button
          type="button"
          onClick={() => void handleWechatPreviewCapture()}
          disabled={capturingWechatPreview}
          className="af-btn af-btn-secondary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
        >
          {capturingWechatPreview ? "..." : text("wechatAgentPreviewCapture")}
        </button>
        <button
          type="button"
          onClick={() => void handleWechatPreviewOCR()}
          disabled={runningWechatOCRPreview}
          className="af-btn af-btn-secondary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
        >
          {runningWechatOCRPreview ? "..." : text("wechatAgentPreviewOCR")}
        </button>
      </div>

      {wechatAgentHealth ? (
        <div className="mt-2 rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-xs text-[var(--af-text-secondary)]">
          <p className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full px-2 py-0.5 ${
                wechatAgentHealth.healthy
                  ? "border af-chip-success"
                  : "border af-chip-warning"
              }`}
            >
              {wechatAgentHealth.healthy
                ? text("wechatAgentHealthHealthy")
                : text("wechatAgentHealthUnhealthy")}
            </span>
            <span>
              {text("wechatAgentHealthCheckedAt")}: {formatTs(wechatAgentHealth.checked_at)}
            </span>
          </p>
          {!wechatAgentHealth.healthy ? (
            <p className="mt-1 text-[var(--af-warning)]">
              {text("wechatAgentHealthReasons")}:
              {" "}
              {wechatAgentHealth.reasons.length ? wechatAgentHealth.reasons.join(", ") : "-"}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
        <StatCard label={text("daemonPid")} value={String(wechatAgentStatus?.pid ?? "-")} />
        <StatCard label={text("daemonUptime")} value={formatDuration(wechatAgentStatus?.uptime_seconds ?? null)} />
        <StatCard
          label={text("wechatAgentProcessedHashes")}
          value={wechatAgentStatus?.processed_hashes ?? 0}
        />
        <StatCard
          label={text("wechatAgentLastCycle")}
          value={formatTs(wechatAgentStatus?.last_cycle_at ?? null)}
        />
        <StatCard
          label={text("wechatAgentRunOncePid")}
          value={wechatAgentStatus?.run_once_running ? String(wechatAgentStatus?.run_once_pid ?? "-") : "-"}
        />
        <StatCard
          label={text("wechatAgentCycleSubmitted")}
          value={wechatAgentStatus?.last_cycle_submitted ?? 0}
        />
        <StatCard
          label={text("wechatAgentCycleFailed")}
          value={wechatAgentStatus?.last_cycle_failed ?? 0}
        />
        <StatCard
          label={text("wechatAgentCycleSkippedSeen")}
          value={wechatAgentStatus?.last_cycle_skipped_seen ?? 0}
        />
        <StatCard
          label={text("wechatAgentCycleLowQuality")}
          value={wechatAgentStatus?.last_cycle_skipped_low_quality ?? 0}
        />
      </div>
      <div className="mt-3 rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3 text-xs text-[var(--af-text-secondary)]">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="font-semibold text-[var(--af-text-primary)]">{text("wechatAgentDedupTitle")}</p>
            <p className="mt-1 text-[var(--af-text-tertiary)]">{text("wechatAgentDedupResetHint")}</p>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <button
              type="button"
              onClick={() => void handleResetWechatDedup(false)}
              disabled={resettingWechatDedup || resettingWechatDedupHard}
              className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-1 text-[var(--af-text-secondary)] transition hover:border-[var(--af-border-strong)] hover:bg-[var(--af-surface-elevated)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {resettingWechatDedup ? `${text("wechatAgentDedupReset")}...` : text("wechatAgentDedupReset")}
            </button>
            <button
              type="button"
              onClick={() => void handleResetWechatDedup(true)}
              disabled={resettingWechatDedup || resettingWechatDedupHard}
              className="rounded-full border af-chip-warning px-3 py-1 transition hover:border-[var(--af-border-strong)] hover:bg-[var(--af-surface-hover)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {resettingWechatDedupHard ? `${text("wechatAgentDedupResetHard")}...` : text("wechatAgentDedupResetHard")}
            </button>
          </div>
        </div>
        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
          <StatCard label={text("wechatAgentProcessedHashes")} value={wechatAgentDedupSummary?.processed_hashes ?? 0} />
          <StatCard label={text("wechatAgentDedupRuns")} value={wechatAgentDedupSummary?.run_count ?? 0} />
          <StatCard label={text("wechatAgentDedupLastRun")} value={formatTs(wechatAgentDedupSummary?.last_run_finished_at ?? null)} />
        </div>
      </div>
    </>
  );
}
