"use client";

import type { AppLanguage } from "@/lib/preferences";
import { CollectorOpsStatCard as StatCard } from "@/components/settings/collector-ops-stat-card";
import type { useCollectorOpsPanelController } from "@/components/settings/use-collector-ops-panel-controller";
import {
  daemonCoverageClass,
  daemonCoverageLabel,
  formatDuration,
  formatPercent,
  formatTs,
  shortText,
} from "@/components/settings/collector-ops-panel-utils";

type CollectorOpsPanelController = ReturnType<typeof useCollectorOpsPanelController>;

type CollectorOpsDaemonSectionProps = {
  controller: CollectorOpsPanelController;
  language: AppLanguage;
  text: (key: string) => string;
};

export function CollectorOpsDaemonSection({
  controller,
  language,
  text,
}: CollectorOpsDaemonSectionProps) {
  const {
    daemonStatus,
    startingDaemon,
    stoppingDaemon,
    runningOnce,
    handleStartDaemon,
    handleStopDaemon,
    handleRunOnce,
  } = controller;

  return (
      <div className="mt-4 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-4">
        <p className="text-sm font-semibold text-[var(--af-text-primary)]">{text("daemonTitle")}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span
            className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
              daemonStatus?.running
                ? "border af-chip-success"
                : "border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] text-[var(--af-text-secondary)]"
            }`}
          >
            {daemonStatus?.running
              ? text("daemonRunning")
              : text("daemonStopped")}
          </span>
          <button
            type="button"
            onClick={() => void handleStartDaemon()}
            disabled={startingDaemon}
            className="af-btn af-btn-secondary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
          >
            {startingDaemon ? "..." : text("startDaemon")}
          </button>
          <button
            type="button"
            onClick={() => void handleStopDaemon()}
            disabled={stoppingDaemon}
            className="af-btn af-btn-secondary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
          >
            {stoppingDaemon ? "..." : text("stopDaemon")}
          </button>
          <button
            type="button"
            onClick={() => void handleRunOnce()}
            disabled={runningOnce}
            className="af-btn af-btn-primary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
          >
            {runningOnce ? "..." : text("runOnce")}
          </button>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <span
            className={`rounded-full border px-3 py-1 font-medium ${daemonCoverageClass(
              daemonStatus?.coverage_state,
            )}`}
          >
            {daemonCoverageLabel(language, daemonStatus?.coverage_state)}
          </span>
          {daemonStatus?.coverage_recommendation ? (
            <span className="text-[var(--af-text-tertiary)]">{daemonStatus.coverage_recommendation}</span>
          ) : null}
        </div>

        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
          <StatCard label={text("daemonPid")} value={String(daemonStatus?.pid ?? "-")} />
          <StatCard label={text("daemonUptime")} value={formatDuration(daemonStatus?.uptime_seconds ?? null)} />
          <StatCard
            label={text("daemonSources")}
            value={daemonStatus?.source_file_count ?? 0}
          />
          <StatCard
            label={text("daemonLastReport")}
            value={formatTs(daemonStatus?.last_report_at ?? null)}
          />
          <StatCard
            label={text("daemonLastDaily")}
            value={formatTs(daemonStatus?.last_daily_summary_at ?? null)}
          />
          <StatCard
            label={text("daemonLastRun")}
            value={formatTs(daemonStatus?.last_run_at ?? null)}
          />
          <StatCard
            label={text("daemonSubmitMode")}
            value={daemonStatus?.last_run_submit_mode || "-"}
          />
          <StatCard
            label={text("daemonDiscovered")}
            value={daemonStatus?.last_run_discovered_count ?? 0}
          />
          <StatCard
            label={text("daemonHandledCount")}
            value={daemonStatus?.last_run_handled_count ?? 0}
          />
          <StatCard
            label={text("daemonCoverageRate")}
            value={formatPercent(daemonStatus?.last_run_coverage_rate)}
          />
          <StatCard
            label={text("daemonBodyRate")}
            value={formatPercent(daemonStatus?.last_run_body_success_rate)}
          />
          <StatCard
            label={text("daemonCollected")}
            value={daemonStatus?.last_run_collected_count ?? 0}
          />
          <StatCard
            label={text("daemonPluginCount")}
            value={daemonStatus?.last_run_plugin_count ?? 0}
          />
          <StatCard
            label={text("daemonUrlFallbackCount")}
            value={daemonStatus?.last_run_url_count ?? 0}
          />
          <StatCard
            label={text("daemonFailedCount")}
            value={daemonStatus?.last_run_failed_count ?? 0}
          />
        </div>

        <div className="af-surface-card mt-3 rounded-xl border px-3 py-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-semibold text-[var(--af-text-primary)]">微信收藏自动导入</p>
            <span
              className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${
                daemonStatus?.favorites_auto_status === "imported"
                  ? "af-chip-success"
                  : daemonStatus?.favorites_auto_status === "error"
                    ? "af-chip-danger"
                    : daemonStatus?.favorites_auto_status === "unavailable"
                      ? "af-chip-warning"
                      : "af-chip-info"
              }`}
            >
              {daemonStatus?.favorites_auto_status || "idle"}
            </span>
          </div>
          <p className="mt-2 text-xs leading-5 text-[var(--af-text-secondary)]">
            {daemonStatus?.favorites_auto_message ||
              "采集守护进程会检测本地只读 wechat-cli 适配器，并增量导入新的公众号文章收藏。"}
          </p>
          <p className="mt-2 text-[11px] text-[var(--af-text-tertiary)]">
            最近检查 {formatTs(daemonStatus?.favorites_auto_last_at ?? null)} · 发现{" "}
            {daemonStatus?.favorites_auto_discovered_count ?? 0} · 新增{" "}
            {daemonStatus?.favorites_auto_imported_count ?? 0} · 去重{" "}
            {daemonStatus?.favorites_auto_deduplicated_count ?? 0}
          </p>
          {daemonStatus?.favorites_auto_status === "unavailable" ? (
            <p className="mt-2 text-[11px] leading-5 text-[var(--af-warning)]">
              需用户自行完成本地只读适配器安装和授权；Anti-FOMO 不会自动解密、重签名或上传微信数据库。
            </p>
          ) : null}
        </div>

        <p className="mt-2 text-[11px] text-[var(--af-text-tertiary)]">{daemonStatus?.log_file || "-"}</p>
        <div className="mt-3 rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-3">
          <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--af-text-tertiary)]">
            {text("daemonSourceHealth")}
          </p>
          <div className="mt-2 space-y-2">
            {(daemonStatus?.source_health || []).length ? (
              (daemonStatus?.source_health || []).slice(0, 8).map((source) => (
                <div
                  key={source.source_url || source.source_token}
                  className="rounded-lg border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-xs text-[var(--af-text-tertiary)]"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium text-[var(--af-text-secondary)]">{shortText(source.source_token, 64)}</span>
                    <span
                      className={`rounded-full border px-2.5 py-0.5 font-medium ${daemonCoverageClass(
                        source.health_state,
                      )}`}
                    >
                      {daemonCoverageLabel(language, source.health_state)}
                    </span>
                  </div>
                  <p className="mt-1">
                    {text("daemonDiscovered")}: {source.discovered_count} ·{" "}
                    {text("daemonHandledCount")}: {source.handled_count} ·{" "}
                    {text("daemonCoverageRate")}: {formatPercent(source.coverage_rate)} ·{" "}
                    {text("daemonBodyRate")}: {formatPercent(source.body_success_rate)}
                  </p>
                  <p className="mt-1">{shortText(source.last_error || source.recommendation, 150)}</p>
                </div>
              ))
            ) : (
              <p className="text-xs text-[var(--af-text-tertiary)]">-</p>
            )}
          </div>
        </div>
        <div className="mt-3 rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-3">
          <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--af-text-tertiary)]">
            {text("daemonRecentRows")}
          </p>
          <div className="mt-2 space-y-2">
            {(daemonStatus?.last_rows || []).length ? (
              (daemonStatus?.last_rows || []).map((row, index) => (
                <div
                  key={`${row.article_token || "row"}-${index}`}
                  className="rounded-lg border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2 text-[11px] text-[var(--af-text-secondary)]"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-[var(--af-text-primary)]">{row.article_token || "-"}</span>
                    <span className="rounded-full bg-[var(--af-surface-inset)] px-2 py-0.5 text-[10px] uppercase tracking-[0.08em] text-[var(--af-text-secondary)]">
                      {row.mode || "-"}
                    </span>
                    <span className="rounded-full bg-[var(--af-surface-elevated)] px-2 py-0.5 text-[10px] text-[var(--af-text-secondary)]">
                      {row.status || "-"}
                    </span>
                  </div>
                  <p className="mt-1 text-[var(--af-text-tertiary)]">
                    source={row.source_token || "-"} item={row.item_id || "-"}
                  </p>
                  <p className="mt-1 text-[var(--af-text-secondary)]">{row.note || "-"}</p>
                </div>
              ))
            ) : (
              <p className="text-[11px] text-[var(--af-text-tertiary)]">-</p>
            )}
          </div>
        </div>
        <div className="mt-2 rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-inset)] px-3 py-2">
          <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--af-text-tertiary)]">
            {text("daemonLogTail")}
          </p>
          <pre className="mt-2 max-h-36 overflow-auto whitespace-pre-wrap text-[11px] leading-5 text-[var(--af-text-secondary)]">
            {(daemonStatus?.log_tail || []).join("\n") || "-"}
          </pre>
        </div>
      </div>
  );
}
