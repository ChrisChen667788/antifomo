"use client";

import type { useResearchCenterController } from "@/components/research/use-research-center-controller";
import {
  WATCHLIST_SCHEDULE_OPTIONS,
  formatAutomationInterval,
  formatWatchlistAge,
  formatWatchlistSchedule,
  formatWatchlistTime,
  watchlistAutomationAlertLabel,
  watchlistAutomationAlertTone,
  watchlistAutomationStatusLabel,
  watchlistAutomationStatusTone,
  watchlistRunItemStatusLabel,
  watchlistRunItemStatusTone,
  watchlistStatusLabel,
  watchlistStatusTone,
} from "@/components/research/research-center-utils";
import { sanitizeExternalDisplayText } from "@/lib/commercial-risk-copy";

type ResearchCenterController = ReturnType<typeof useResearchCenterController>;
type ResearchCenterWatchlistSectionProps = ResearchCenterController["watchlistSectionProps"];

export function ResearchCenterWatchlistSection({
  t,
  watchlists,
  watchlistAutomation,
  watchlistOpsSummary,
  watchlistDigestExport,
  watchlistMessage,
  watchlistError,
  lastRunDueResult,
  watchlistRunHistory,
  runningDueWatchlists,
  watchlistActionKey,
  refreshingWatchlistId,
  handleDownloadWatchlistDigest,
  handleRunDueWatchlists,
  copyWatchlistOpsText,
  handleUpdateWatchlistSchedule,
  handleToggleWatchlistStatus,
  handleRefreshWatchlist,
}: ResearchCenterWatchlistSectionProps) {
  return (
          <section className="af-glass rounded-[30px] p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="af-kicker">{t("research.watchlistKicker", "Watchlists")}</p>
                <h3 className="mt-2 text-lg font-semibold text-[var(--af-text-primary)]">
                  {t("research.watchlistTitle", "长期监控 Watchlist")}
                </h3>
                <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">
                  {sanitizeExternalDisplayText(t("research.watchlistDesc", "将专题刷新结果沉淀为变化摘要，集中查看当日新增内容。"))}
                </p>
              </div>
              <div className="flex flex-wrap justify-end gap-2">
                <button
                  type="button"
                  onClick={() => void handleDownloadWatchlistDigest()}
                  className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                >
                  导出摘要
                </button>
                <button
                  type="button"
                  onClick={() => void handleRunDueWatchlists()}
                  className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                  disabled={runningDueWatchlists}
                >
                  {runningDueWatchlists
                    ? t("research.watchlistRunDueRunning", "执行中...")
                    : t("research.watchlistRunDue", "执行到期 Watchlist")}
                </button>
              </div>
            </div>
            {watchlistMessage ? <p className="mt-3 text-sm text-[var(--af-success)]">{watchlistMessage}</p> : null}
            {watchlistError ? <p className="mt-2 text-sm text-[var(--af-danger)]">{watchlistError}</p> : null}
            {watchlistOpsSummary ? (
              <div className="mt-4 rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4 text-xs text-[var(--af-text-secondary)]">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">调度健康</p>
                    <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">
                      {watchlistOpsSummary.action_required ? "需要处理" : "运行正常"}
                    </p>
                  </div>
                  <span className={`rounded-full px-2.5 py-1 font-medium ${watchlistAutomationAlertTone(watchlistOpsSummary.alert_level)}`}>
                    {watchlistAutomationAlertLabel(watchlistOpsSummary.alert_level)}
                  </span>
                </div>
                <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                  <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">活跃监控</p>
                    <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">{watchlistOpsSummary.active_count}</p>
                  </div>
                  <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">当前到期</p>
                    <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">{watchlistOpsSummary.due_count}</p>
                  </div>
                  <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">失败专题</p>
                    <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">{watchlistOpsSummary.failed_topic_count}</p>
                  </div>
                  <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">下次到期</p>
                    <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">
                      {watchlistOpsSummary.next_due_at ? formatWatchlistTime(watchlistOpsSummary.next_due_at) : "暂无"}
                    </p>
                  </div>
                </div>
                {watchlistOpsSummary.recommendations?.length ? (
                  <p className="mt-3 text-sm leading-6 text-[var(--af-text-secondary)]">
                    {sanitizeExternalDisplayText(watchlistOpsSummary.recommendations[0])}
                  </p>
                ) : null}
                {watchlistOpsSummary.issues?.length ? (
                  <div className="mt-3 grid gap-2 lg:grid-cols-2">
                    {watchlistOpsSummary.issues.slice(0, 4).map((issue) => (
                      <div key={`${issue.watchlist_id || issue.name}-${issue.issue_type}`} className="rounded-2xl af-state-panel-warning px-3 py-2">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-sm font-semibold text-[var(--af-text-primary)]">{sanitizeExternalDisplayText(issue.name)}</p>
                          <span className={`rounded-full px-2 py-1 text-[11px] ${watchlistAutomationAlertTone(issue.severity)}`}>
                            {watchlistAutomationAlertLabel(issue.severity)}
                          </span>
                        </div>
                        <p className="mt-1 text-xs leading-5 text-[var(--af-text-secondary)]">{sanitizeExternalDisplayText(issue.summary)}</p>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}
            {watchlistDigestExport ? (
              <div className="mt-4 rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4 text-xs text-[var(--af-text-secondary)]">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">摘要导出</p>
                    <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">
                      最近 24 小时 · {watchlistDigestExport.run_count} 次运行
                    </p>
                  </div>
                  <span className={`rounded-full px-2.5 py-1 font-medium ${watchlistAutomationAlertTone(watchlistDigestExport.alert_level)}`}>
                    {watchlistAutomationAlertLabel(watchlistDigestExport.alert_level)}
                  </span>
                </div>
                <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                  <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">成功</p>
                    <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">{watchlistDigestExport.refreshed_count}</p>
                  </div>
                  <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">失败</p>
                    <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">{watchlistDigestExport.failed_count}</p>
                  </div>
                  <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">变化</p>
                    <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">{watchlistDigestExport.change_count}</p>
                  </div>
                  <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">重试</p>
                    <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">{watchlistDigestExport.retry_count}</p>
                  </div>
                </div>
                {watchlistDigestExport.summary_lines?.length ? (
                  <p className="mt-3 text-sm leading-6 text-[var(--af-text-secondary)]">
                    {sanitizeExternalDisplayText(watchlistDigestExport.summary_lines[0])}
                  </p>
                ) : null}
              </div>
            ) : null}
            <div className="mt-4 rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4 text-xs text-[var(--af-text-secondary)]">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded-full px-2.5 py-1 font-medium ${
                    watchlistAutomation?.loaded
                      ? "af-chip af-chip-success"
                      : watchlistAutomation?.installed
                        ? "af-chip af-chip-warning"
                        : "af-chip"
                  }`}
                >
                  {watchlistAutomation?.loaded
                    ? t("research.watchlistAutomationLoaded", "本地自动巡检已加载")
                    : watchlistAutomation?.installed
                      ? t("research.watchlistAutomationInstalled", "已安装，等待 launchd 加载")
                      : t("research.watchlistAutomationMissing", "尚未安装本地自动巡检")}
                </span>
                <span className={`rounded-full px-2.5 py-1 font-medium ${watchlistAutomationStatusTone(watchlistAutomation?.last_run_status)}`}>
                  {watchlistAutomationStatusLabel(watchlistAutomation?.last_run_status)}
                </span>
                <span className={`rounded-full px-2.5 py-1 font-medium ${watchlistAutomationAlertTone(watchlistAutomation?.alert_level)}`}>
                  {watchlistAutomationAlertLabel(watchlistAutomation?.alert_level)}
                </span>
                {watchlistAutomation?.interval_seconds ? (
                  <span className="rounded-full af-chip px-2.5 py-1 ">
                    {t("research.watchlistAutomationInterval", "巡检间隔")} · {formatAutomationInterval(watchlistAutomation.interval_seconds)}
                  </span>
                ) : null}
                {watchlistAutomation?.last_checked_at ? (
                  <span className="rounded-full af-chip px-2.5 py-1 ">
                    {t("research.watchlistAutomationLastRun", "最近自动运行")} · {formatWatchlistTime(watchlistAutomation.last_checked_at)}
                  </span>
                ) : null}
              </div>
              {watchlistAutomation?.action_required ? (
                <div className="mt-3 rounded-2xl af-state-panel-danger p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-danger)]">当前需要处理</p>
                    <div className="flex flex-wrap gap-2">
                      {watchlistAutomation?.recommended_run_due_command ? (
                        <button
                          type="button"
                          className="af-btn af-btn-secondary border px-2.5 py-1 text-[11px]"
                          onClick={() =>
                            void copyWatchlistOpsText(
                              watchlistAutomation.recommended_run_due_command,
                              "手动重跑命令",
                            )
                          }
                        >
                          复制重跑命令
                        </button>
                      ) : null}
                      {watchlistAutomation?.recommended_status_command ? (
                        <button
                          type="button"
                          className="af-btn af-btn-secondary border px-2.5 py-1 text-[11px]"
                          onClick={() =>
                            void copyWatchlistOpsText(
                              watchlistAutomation.recommended_status_command,
                              "巡检状态命令",
                            )
                          }
                        >
                          复制状态命令
                        </button>
                      ) : null}
                    </div>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-[var(--af-danger)]">
                    {sanitizeExternalDisplayText(
                      watchlistAutomation.action_required_reason || watchlistAutomation.last_failure_hint || "当前自动巡检需要人工检查。",
                    )}
                  </p>
                </div>
              ) : null}
              <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">
                    {t("research.watchlistAutomationDue", "最近到期")}
                  </p>
                  <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">{watchlistAutomation?.last_due_count ?? 0}</p>
                </div>
                <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">
                    {t("research.watchlistAutomationRefreshed", "最近刷新")}
                  </p>
                  <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">{watchlistAutomation?.last_refreshed_count ?? 0}</p>
                </div>
                <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">
                    {t("research.watchlistAutomationFailed", "最近失败")}
                  </p>
                  <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">{watchlistAutomation?.last_failed_count ?? 0}</p>
                </div>
                <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">日志大小</p>
                  <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">
                    {watchlistAutomation?.last_log_size_bytes
                      ? `${Math.max(1, Math.round(watchlistAutomation.last_log_size_bytes / 1024))} KB`
                      : "—"}
                  </p>
                </div>
                <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">状态新鲜度</p>
                  <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">
                    {watchlistAutomation?.last_checked_at
                      ? `${formatWatchlistAge(watchlistAutomation.state_age_seconds)} 前`
                      : "—"}
                  </p>
                  <p className={`mt-1 text-[11px] ${watchlistAutomation?.state_stale ? "text-[var(--af-danger)]" : "text-[var(--af-text-tertiary)]"}`}>
                    {watchlistAutomation?.state_stale ? "状态已过期" : "状态仍在刷新窗口内"}
                  </p>
                </div>
                <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">最近请求失败</p>
                  <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">{watchlistAutomation?.recent_request_failure_count ?? 0}</p>
                  <p className="mt-1 text-[11px] text-[var(--af-text-tertiary)]">
                    连续失败 {watchlistAutomation?.consecutive_request_failure_count ?? 0}
                  </p>
                </div>
              </div>
              <p className="mt-2 text-[var(--af-text-tertiary)]">
                {watchlistAutomation?.last_summary
                  ? sanitizeExternalDisplayText(watchlistAutomation.last_summary)
                  : t(
                    "research.watchlistAutomationHint",
                    "建议把本地 watchlist 调度交给 launchd，每小时触发一次，脚本只刷新已到期 watchlist 并写回提醒状态。",
                  )}
              </p>
              {watchlistAutomation?.last_failure_hint ? (
                <p className="mt-2 text-sm text-[var(--af-danger)]">{sanitizeExternalDisplayText(watchlistAutomation.last_failure_hint)}</p>
              ) : null}
              {lastRunDueResult ? (
                <div className="mt-3 rounded-2xl af-state-panel-info p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-info)]">最近一次手动执行</p>
                      <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">
                        {formatWatchlistTime(lastRunDueResult.checked_at) || "刚刚"}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2 text-[11px]">
                      <span className="rounded-full af-chip px-2.5 py-1 ">
                        到期 {lastRunDueResult.due_count}
                      </span>
                      <span className="rounded-full af-chip af-chip-success px-2.5 py-1 ">
                        刷新 {lastRunDueResult.refreshed_count}
                      </span>
                      <span className="rounded-full af-chip af-chip-danger px-2.5 py-1 ">
                        失败 {lastRunDueResult.failed_count}
                      </span>
                    </div>
                  </div>
                  {lastRunDueResult.items.length ? (
                    <div className="mt-3 space-y-2">
                      {lastRunDueResult.items.slice(0, 4).map((item) => (
                        <div key={`${item.watchlist_id}-last-run`} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="text-sm font-semibold text-[var(--af-text-primary)]">{item.name}</p>
                            <span className={`rounded-full px-2 py-1 text-[11px] ${watchlistRunItemStatusTone(item.status)}`}>
                              {watchlistRunItemStatusLabel(item.status)}
                            </span>
                          </div>
                          <p className="mt-1 text-sm leading-6 text-[var(--af-text-secondary)]">
                            {sanitizeExternalDisplayText(item.error || item.summary)}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
              {watchlistRunHistory.length ? (
                <div className="mt-3 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">Run history</p>
                      <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">最近 {watchlistRunHistory.length} 条运行记录</p>
                    </div>
                    <span className="rounded-full af-chip px-2.5 py-1 text-[11px] ">
                      重试 {watchlistRunHistory.reduce((sum, item) => sum + (item.retry_count || 0), 0)}
                    </span>
                  </div>
                  <div className="mt-3 space-y-2">
                    {watchlistRunHistory.slice(0, 5).map((run) => (
                      <div key={run.id} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-sm font-semibold text-[var(--af-text-primary)]">{sanitizeExternalDisplayText(run.watchlist_name)}</p>
                          <span className={`rounded-full px-2 py-1 text-[11px] ${watchlistRunItemStatusTone(run.status)}`}>
                            {watchlistRunItemStatusLabel(run.status)}
                          </span>
                        </div>
                        <p className="mt-1 text-xs leading-5 text-[var(--af-text-secondary)]">
                          {formatWatchlistTime(run.created_at)} · 尝试 {run.attempt_count} · 重试 {run.retry_count} · 变化 {run.change_count}
                        </p>
                        <p className="mt-1 text-sm leading-6 text-[var(--af-text-secondary)]">
                          {sanitizeExternalDisplayText(run.error || run.summary || "无摘要")}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              <div className="mt-3 grid gap-2 lg:grid-cols-2">
                <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">重跑命令</p>
                    <button
                      type="button"
                      className="af-btn af-btn-secondary border px-2.5 py-1 text-[11px]"
                      onClick={() =>
                        void copyWatchlistOpsText(
                          watchlistAutomation?.recommended_run_due_command || "npm run research:watchlists:run-due",
                          "重跑命令",
                        )
                      }
                    >
                      {t("common.copy", "复制")}
                    </button>
                  </div>
                  <code className="mt-2 block overflow-x-auto rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-inset)] px-3 py-2 text-[11px] leading-5 text-[var(--af-text-primary)]">
                    {watchlistAutomation?.recommended_run_due_command || "npm run research:watchlists:run-due"}
                  </code>
                </div>
                <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">状态命令</p>
                    <button
                      type="button"
                      className="af-btn af-btn-secondary border px-2.5 py-1 text-[11px]"
                      onClick={() =>
                        void copyWatchlistOpsText(
                          watchlistAutomation?.recommended_status_command || "npm run research:watchlists:automation:status",
                          "状态命令",
                        )
                      }
                    >
                      {t("common.copy", "复制")}
                    </button>
                  </div>
                  <code className="mt-2 block overflow-x-auto rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-inset)] px-3 py-2 text-[11px] leading-5 text-[var(--af-text-primary)]">
                    {watchlistAutomation?.recommended_status_command || "npm run research:watchlists:automation:status"}
                  </code>
                </div>
              </div>
              <div className="mt-3 grid gap-2 lg:grid-cols-2">
                <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">安装命令</p>
                    <button
                      type="button"
                      className="af-btn af-btn-secondary border px-2.5 py-1 text-[11px]"
                      onClick={() =>
                        void copyWatchlistOpsText(
                          watchlistAutomation?.recommended_install_command ||
                            "npm run research:watchlists:automation:install",
                          "安装命令",
                        )
                      }
                    >
                      {t("common.copy", "复制")}
                    </button>
                  </div>
                  <code className="mt-2 block overflow-x-auto rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-inset)] px-3 py-2 text-[11px] leading-5 text-[var(--af-text-primary)]">
                    {watchlistAutomation?.recommended_install_command || "npm run research:watchlists:automation:install"}
                  </code>
                </div>
                <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">卸载命令</p>
                    <button
                      type="button"
                      className="af-btn af-btn-secondary border px-2.5 py-1 text-[11px]"
                      onClick={() =>
                        void copyWatchlistOpsText(
                          watchlistAutomation?.recommended_uninstall_command ||
                            "npm run research:watchlists:automation:uninstall",
                          "卸载命令",
                        )
                      }
                    >
                      {t("common.copy", "复制")}
                    </button>
                  </div>
                  <code className="mt-2 block overflow-x-auto rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-inset)] px-3 py-2 text-[11px] leading-5 text-[var(--af-text-primary)]">
                    {watchlistAutomation?.recommended_uninstall_command || "npm run research:watchlists:automation:uninstall"}
                  </code>
                </div>
              </div>
              <div className="mt-3 grid gap-2 lg:grid-cols-3">
                {[
                  { label: "launchd plist", value: watchlistAutomation?.plist_path || "" },
                  { label: "状态文件", value: watchlistAutomation?.state_path || "" },
                  { label: "运行日志", value: watchlistAutomation?.log_path || "" },
                ].map((item) => (
                  <div key={item.label} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">{item.label}</p>
                      {item.value ? (
                        <button
                          type="button"
                          className="af-btn af-btn-secondary border px-2.5 py-1 text-[11px]"
                          onClick={() => void copyWatchlistOpsText(item.value, `${item.label}路径`)}
                        >
                          {t("common.copy", "复制")}
                        </button>
                      ) : null}
                    </div>
                    <p className="mt-2 break-all text-[11px] leading-5 text-[var(--af-text-secondary)]">
                      {item.value || "当前未返回路径"}
                    </p>
                  </div>
                ))}
              </div>
              {watchlistAutomation?.failed_items?.length ? (
                <div className="mt-3 space-y-2">
                  <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">最近失败样本</p>
                  {watchlistAutomation.failed_items.map((item) => (
                    <div key={`${item.watchlist_id || item.name}-failed`} className="rounded-2xl af-state-panel-danger px-3 py-2">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-[var(--af-text-primary)]">{item.name}</p>
                        <span className="rounded-full af-chip af-chip-danger px-2 py-1 text-[11px] ">
                          {item.change_count ? `changes ${item.change_count}` : "failed"}
                        </span>
                      </div>
                      <p className="mt-1 text-sm leading-6 text-[var(--af-text-secondary)]">{sanitizeExternalDisplayText(item.error || item.summary)}</p>
                      {item.next_due_at ? (
                        <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">下次到期 · {formatWatchlistTime(item.next_due_at)}</p>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
            <div className="mt-4 space-y-3">
              {watchlists.length ? (
                watchlists.map((watchlist) => (
                  <article key={watchlist.id} className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-[var(--af-text-primary)]">{watchlist.name}</p>
                        <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">
                          {watchlist.query} · {watchlist.alert_level} · {formatWatchlistSchedule(watchlist.schedule, t)}
                        </p>
                        <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
                          <span className={`rounded-full px-2.5 py-1 ${watchlistStatusTone(watchlist.status)}`}>
                            {watchlistStatusLabel(watchlist.status)}
                          </span>
                          {watchlist.is_due ? (
                            <span className="rounded-full af-chip af-chip-warning px-2.5 py-1 ">
                              {t("research.watchlistDueNow", "已到刷新窗口")}
                            </span>
                          ) : null}
                          {watchlist.last_checked_at ? (
                            <span className="rounded-full af-chip px-2.5 py-1 ">
                              {t("research.watchlistLastChecked", "最近检查")} · {formatWatchlistTime(watchlist.last_checked_at)}
                            </span>
                          ) : null}
                          {watchlist.next_due_at ? (
                            <span className="rounded-full af-chip px-2.5 py-1 ">
                              {t("research.watchlistNextDue", "下次到期")} · {formatWatchlistTime(watchlist.next_due_at)}
                            </span>
                          ) : null}
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        <select
                          value={watchlist.schedule}
                          onChange={(event) => void handleUpdateWatchlistSchedule(watchlist.id, event.target.value)}
                          className="af-input min-w-[136px] bg-[var(--af-surface-elevated)] py-1.5 text-xs"
                          disabled={watchlistActionKey === `${watchlist.id}-schedule`}
                        >
                          {WATCHLIST_SCHEDULE_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                              {formatWatchlistSchedule(option.value, t)}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          onClick={() => void handleToggleWatchlistStatus(watchlist)}
                          className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                          disabled={watchlistActionKey === `${watchlist.id}-status`}
                        >
                          {watchlistActionKey === `${watchlist.id}-status`
                            ? "处理中..."
                            : watchlist.status === "paused"
                              ? "恢复 Watchlist"
                              : "暂停 Watchlist"}
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleRefreshWatchlist(watchlist.id)}
                          className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                          disabled={refreshingWatchlistId === watchlist.id}
                        >
                          {refreshingWatchlistId === watchlist.id
                            ? t("research.watchlistRefreshing", "刷新中...")
                            : t("research.watchlistRefresh", "刷新 Watchlist")}
                        </button>
                      </div>
                    </div>
                    {watchlist.status === "paused" ? (
                      <p className="mt-3 text-xs text-[var(--af-text-tertiary)]">
                        当前已暂停自动刷新，仍可手动执行一次 Watchlist。
                      </p>
                    ) : null}
                    <div className="mt-3 space-y-2">
                      {(watchlist.latest_changes?.length
                        ? watchlist.latest_changes.slice(0, 3)
                        : []).map((change) => (
                        <div key={change.id} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">
                            {change.change_type} · {change.severity}
                          </p>
                          <p className="mt-1 text-sm text-[var(--af-text-secondary)]">{sanitizeExternalDisplayText(change.summary)}</p>
                        </div>
                      ))}
                      {!watchlist.latest_changes?.length ? (
                        <p className="text-sm text-[var(--af-text-tertiary)]">
                          {t("research.watchlistEmpty", "还没有变化摘要，可先刷新一次 Watchlist。")}
                        </p>
                      ) : null}
                    </div>
                  </article>
                ))
              ) : (
                <p className="text-sm text-[var(--af-text-tertiary)]">
                  {t("research.watchlistEmpty", "还没有变化摘要，可先刷新一次 Watchlist。")}
                </p>
              )}
            </div>
          </section>
  );
}
