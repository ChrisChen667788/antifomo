
"use client";

import { CollectorOpsStatCard as StatCard } from "@/components/settings/collector-ops-stat-card";
import type { useCollectorOpsPanelController } from "@/components/settings/use-collector-ops-panel-controller";
import {
  formatTs,
  shortText,
} from "@/components/settings/collector-ops-panel-utils";

type CollectorOpsPanelController = ReturnType<typeof useCollectorOpsPanelController>;

type CollectorOpsGeneralSectionProps = {
  controller: CollectorOpsPanelController;
  text: (key: string) => string;
};

export function CollectorOpsGeneralSection({
  controller,
  text,
}: CollectorOpsGeneralSectionProps) {
  const {
    status,
    failedItems,
    message,
    commandOutput,
    loadingState,
    processingPending,
    retryingFailed,
    generatingDaily,
    deferredMarkdown,
    refreshStatus,
    handleFlushPending,
    handleRetryFailed,
    handleGenerateDaily,
    handleCopyMarkdown,
  } = controller;

  return (
    <>
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => void refreshStatus()}
          disabled={loadingState}
          className="af-btn af-btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loadingState ? "..." : text("refresh")}
        </button>
        <button
          type="button"
          onClick={() => void handleFlushPending()}
          disabled={processingPending}
          className="af-btn af-btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
        >
          {processingPending ? "..." : text("flushPending")}
        </button>
        <button
          type="button"
          onClick={() => void handleRetryFailed()}
          disabled={retryingFailed}
          className="af-btn af-btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
        >
          {retryingFailed ? "..." : text("retryFailed")}
        </button>
        <button
          type="button"
          onClick={() => void handleGenerateDaily()}
          disabled={generatingDaily}
          className="af-btn af-btn-primary disabled:cursor-not-allowed disabled:opacity-60"
        >
          {generatingDaily ? "..." : text("generateDaily")}
        </button>
      </div>

      {message ? <p className="mt-3 text-xs text-[var(--af-text-tertiary)]">{message}</p> : null}
      {commandOutput ? (
        <div className="mt-2 rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-inset)] px-3 py-2">
          <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--af-text-tertiary)]">
            {text("daemonOutput")}
          </p>
          <pre className="mt-2 max-h-44 overflow-auto whitespace-pre-wrap text-[11px] leading-5 text-[var(--af-text-secondary)]">
            {commandOutput}
          </pre>
        </div>
      ) : null}

      <div className="mt-4 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-4">
        <p className="text-sm font-semibold text-[var(--af-text-primary)]">{text("statusTitle")}</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          <StatCard label={text("total")} value={status?.last_24h_total ?? 0} />
          <StatCard label={text("ready")} value={status?.last_24h_ready ?? 0} />
          <StatCard label={text("pending")} value={status?.last_24h_processing ?? 0} />
          <StatCard label={text("failed")} value={status?.last_24h_failed ?? 0} />
          <StatCard label={text("ocr")} value={status?.last_24h_ocr_items ?? 0} />
        </div>
        <p className="mt-2 text-xs text-[var(--af-text-tertiary)]">{formatTs(status?.latest_item_at || null)}</p>
      </div>

      <div className="mt-4 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-4">
        <p className="text-sm font-semibold text-[var(--af-text-primary)]">{text("failedTitle")}</p>
        {failedItems.length ? (
          <div className="mt-3 overflow-x-auto">
            <table className="min-w-full text-left text-xs text-[var(--af-text-secondary)]">
              <thead>
                <tr className="text-[var(--af-text-tertiary)]">
                  <th className="px-2 py-1">{text("titleCol")}</th>
                  <th className="px-2 py-1">{text("source")}</th>
                  <th className="px-2 py-1">{text("error")}</th>
                </tr>
              </thead>
              <tbody>
                {failedItems.slice(0, 12).map((item) => (
                  <tr key={item.id} className="border-t border-[var(--af-border-subtle)]">
                    <td className="px-2 py-2">{shortText(item.title, 60)}</td>
                    <td className="px-2 py-2">{item.source_domain || "-"}</td>
                    <td className="px-2 py-2">{shortText(item.processing_error, 84)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="mt-2 text-xs text-[var(--af-text-tertiary)]">{text("failedEmpty")}</p>
        )}
      </div>

      <div className="mt-4 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-4">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm font-semibold text-[var(--af-text-primary)]">{text("dailyTitle")}</p>
          <button
            type="button"
            onClick={() => void handleCopyMarkdown()}
            disabled={!deferredMarkdown}
            className="af-btn af-btn-secondary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
          >
            {text("copy")}
          </button>
        </div>
        <textarea
          readOnly
          rows={12}
          value={deferredMarkdown || text("markdownPlaceholder")}
          className="mt-3 w-full rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-4 py-3 font-mono text-xs leading-6 text-[var(--af-text-secondary)] outline-none"
        />
      </div>
    </>
  );
}
