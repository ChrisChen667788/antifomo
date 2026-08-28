
"use client";

import Link from "next/link";
import { AppIcon } from "@/components/ui/app-icon";
import { CollectorOpsStatCard as StatCard } from "@/components/settings/collector-ops-stat-card";
import type { useCollectorOpsPanelController } from "@/components/settings/use-collector-ops-panel-controller";
import {
  formatTs,
  shortText,
} from "@/components/settings/collector-ops-panel-utils";

type CollectorOpsPanelController = ReturnType<typeof useCollectorOpsPanelController>;

type CollectorOpsWechatAgentBatchSectionProps = {
  controller: CollectorOpsPanelController;
  text: (key: string) => string;
};

export function CollectorOpsWechatAgentBatchSection({
  controller,
  text,
}: CollectorOpsWechatAgentBatchSectionProps) {
  const {
    wechatAgentBatchStatus,
    wechatAgentBatchItems,
    batchProgress,
    submittedUrlDirect,
    submittedUrlShareCopy,
    submittedUrlResolved,
    submittedOcr,
    skippedSeenTotal,
    failedTotal,
    duplicateEscapes,
    routeBackoffs,
    routeCircuitBreakers,
    recoveryActions,
    urlOnlySkips,
    previewLoopHits,
    accessibilityHits,
    templateHits,
    perceptualDedupHits,
    hardEscapes,
    submenuTraps,
    urlFirstShare,
    ocrShare,
  } = controller;

  return (
    <>
      {wechatAgentBatchStatus ? (
        <div className="mt-3 rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3 text-xs text-[var(--af-text-secondary)]">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-semibold text-[var(--af-text-primary)]">
                {text("wechatAgentBatchTitle")}
              </p>
              <p className="mt-1 text-[var(--af-text-tertiary)]">
                {text("wechatAgentBatchProgress")}: {batchProgress}% ·
                {" "}
                {wechatAgentBatchStatus.current_segment_index}/{Math.max(
                  wechatAgentBatchStatus.total_segments,
                  1,
                )}
              </p>
            </div>
            <span
              className={`rounded-full px-2 py-0.5 ${
                wechatAgentBatchStatus.running
                  ? "border af-chip-info"
                  : "border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] text-[var(--af-text-secondary)]"
              }`}
            >
              {wechatAgentBatchStatus.running
                ? text("daemonRunning")
                : text("daemonStopped")}
            </span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--af-surface-inset)]">
            <div
              className="h-full rounded-full bg-[var(--af-accent)] transition-all duration-500"
              style={{ width: `${batchProgress}%` }}
            />
          </div>
          <div
            className={`mt-3 rounded-xl border px-3 py-3 ${
              wechatAgentBatchStatus.route_quality.route_stability === "good"
                ? "af-chip-success"
                : wechatAgentBatchStatus.route_quality.route_stability === "poor"
                  ? "af-chip-warning"
                  : "border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] text-[var(--af-text-secondary)]"
            }`}
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px] font-semibold">
                {wechatAgentBatchStatus.route_quality.route_stability === "good"
                  ? "采集质量 · 健康"
                  : wechatAgentBatchStatus.route_quality.route_stability === "poor"
                    ? "采集质量 · 待优化"
                    : "采集质量 · 观察中"}
              </span>
              <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px]">
                链接优先 {wechatAgentBatchStatus.route_quality.url_first_share}%
              </span>
              <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px]">
                内容补录 {wechatAgentBatchStatus.route_quality.ocr_share}%
              </span>
              <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px]">
                自动操作 {wechatAgentBatchStatus.route_quality.accessibility_hit_rate}%
              </span>
              <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px]">
                模板命中 {wechatAgentBatchStatus.route_quality.template_hit_rate}%
              </span>
            </div>
            <p className="mt-2 text-xs leading-5">{wechatAgentBatchStatus.route_quality.recommendation}</p>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            <StatCard label={text("wechatAgentBatchSubmittedNew")} value={wechatAgentBatchStatus.submitted_new} />
            <StatCard label={text("wechatAgentBatchSubmittedUrl")} value={wechatAgentBatchStatus.submitted_url} />
            <StatCard label={text("wechatAgentBatchSubmittedOcr")} value={submittedOcr} />
            <StatCard label={text("wechatAgentBatchDedup")} value={wechatAgentBatchStatus.deduplicated_existing} />
            <StatCard label={text("wechatAgentBatchSeen")} value={skippedSeenTotal} />
            <StatCard label={text("wechatAgentBatchFailed")} value={failedTotal} />
          </div>
          <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-3">
            <StatCard
              label={text("focus.collectorUrlDirect")}
              value={submittedUrlDirect}
            />
            <StatCard
              label={text("focus.collectorUrlShareCopy")}
              value={submittedUrlShareCopy}
            />
            <StatCard
              label={text("focus.collectorUrlResolved")}
              value={submittedUrlResolved}
            />
          </div>
          <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            <StatCard label={text("wechatAgentBatchUrlFirstShare")} value={`${urlFirstShare}%`} />
            <StatCard label={text("wechatAgentBatchOcrShare")} value={`${ocrShare}%`} />
            <StatCard label={text("wechatAgentBatchDuplicateEscape")} value={duplicateEscapes} />
            <StatCard label={text("wechatAgentBatchHardEscape")} value={hardEscapes} />
            <StatCard label={text("wechatAgentBatchSubmenuTrap")} value={submenuTraps} />
            <StatCard label={text("wechatAgentBatchRouteBackoff")} value={routeBackoffs} />
            <StatCard label={text("wechatAgentBatchRouteBreaker")} value={routeCircuitBreakers} />
            <StatCard label={text("wechatAgentBatchRecoveries")} value={recoveryActions} />
          </div>
          <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-5">
            <StatCard label={text("wechatAgentBatchUrlOnlySkips")} value={urlOnlySkips} />
            <StatCard label={text("wechatAgentBatchPreviewLoops")} value={previewLoopHits} />
            <StatCard label={text("wechatAgentBatchAccessibilityHits")} value={accessibilityHits} />
            <StatCard label={text("wechatAgentBatchTemplateHits")} value={templateHits} />
            <StatCard label={text("wechatAgentBatchPerceptualDedup")} value={perceptualDedupHits} />
          </div>
          {(wechatAgentBatchStatus.live_report_batch || wechatAgentBatchStatus.live_report_stage) ? (
            <div className="mt-3 rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3 text-xs text-[var(--af-text-secondary)]">
              <p className="font-semibold text-[var(--af-text-primary)]">{text("wechatAgentBatchLive")}</p>
              <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-4">
                <StatCard label="批次" value={wechatAgentBatchStatus.live_report_batch ?? "-"} />
                <StatCard label="行号" value={wechatAgentBatchStatus.live_report_row ?? "-"} />
                <StatCard label="阶段" value={wechatAgentBatchStatus.live_report_stage ?? "-"} />
                <StatCard label={text("wechatAgentBatchLiveCheckpoint")} value={formatTs(wechatAgentBatchStatus.live_report_checkpoint_at ?? null)} />
              </div>
              {wechatAgentBatchStatus.live_report_detail ? (
                <p className="mt-2 text-[var(--af-text-tertiary)]">{shortText(wechatAgentBatchStatus.live_report_detail, 180)}</p>
              ) : null}
            </div>
          ) : null}
          {wechatAgentBatchStatus.last_message ? (
            <p className="mt-2 text-[var(--af-text-tertiary)]">
              {text("wechatAgentBatchMessage")}: {shortText(wechatAgentBatchStatus.last_message, 180)}
            </p>
          ) : null}
          {wechatAgentBatchStatus.last_error ? (
            <p className="mt-1 text-[var(--af-warning)]">
              {text("wechatAgentCycleError")}: {shortText(wechatAgentBatchStatus.last_error, 180)}
            </p>
          ) : null}
          {wechatAgentBatchItems.length ? (
            <div className="mt-4 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--af-text-tertiary)]">
                    {text("wechatAgentBatchItemsTitle")}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">
                    {text("wechatAgentBatchItemsHint")}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Link
                    href="/session-summary"
                    className="af-btn af-btn-secondary border border-[var(--af-border-subtle)] px-3 py-1.5 text-xs"
                  >
                    <AppIcon name="summary" className="h-3.5 w-3.5" />
                    {text("wechatAgentBatchOpenSummary")}
                  </Link>
                </div>
              </div>
              <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
                {wechatAgentBatchItems.map((item) => (
                  <article
                    key={item.id}
                    className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-4 shadow-[var(--af-shadow-card)]"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px] font-semibold text-[var(--af-text-tertiary)]">
                        {item.source_domain || text("unknownSource")}
                      </span>
                      <span className="text-[11px] font-medium text-[var(--af-text-tertiary)]">
                        {(item.action_suggestion || "later").replace("_", " ")}
                      </span>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                      <span className="af-chip af-chip-info rounded-full px-2.5 py-1 font-semibold">
                        来源 · {item.ingest_route || "unknown"}
                      </span>
                      <span className="rounded-full bg-[var(--af-surface-muted)] px-2.5 py-1 font-semibold text-[var(--af-text-secondary)]">
                        正文 · {item.content_acquisition_status || "pending"}
                      </span>
                      {item.fallback_used ? (
                        <span className="af-chip af-chip-warning rounded-full px-2.5 py-1 font-semibold">
                          已使用可用内容
                        </span>
                      ) : null}
                    </div>
                    <h4 className="mt-3 text-sm font-semibold leading-6 text-[var(--af-text-primary)]">
                      {item.title || text("untitled")}
                    </h4>
                    <p className="mt-2 line-clamp-3 text-sm leading-6 text-[var(--af-text-secondary)]">
                      {item.short_summary || item.long_summary || "-"}
                    </p>
                    {item.content_acquisition_note ? (
                      <p className="mt-2 text-xs leading-5 text-[var(--af-text-tertiary)]">
                        {item.content_acquisition_note}
                      </p>
                    ) : null}
                    <div className="mt-4">
                      <Link
                        href={`/items/${item.id}`}
                        className="af-btn af-btn-secondary border border-[var(--af-border-subtle)] px-3 py-1.5 text-xs"
                      >
                        <AppIcon name="summary" className="h-3.5 w-3.5" />
                        {text("wechatAgentBatchOpenItem")}
                      </Link>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </>
  );
}
