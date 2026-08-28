"use client";

import { useEffect, useState } from "react";
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

function favoritesAutoStatusLabel(status?: string | null) {
  if (status === "imported") return "已导入";
  if (status === "error") return "需处理";
  if (status === "unavailable") return "不可用";
  if (status === "checked") return "已检查";
  return "待机";
}

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
    updatingClipboardAutoImport,
    updatingExportDirectoryAutoImport,
    verifyingBrowserExtension,
    handleStartDaemon,
    handleStopDaemon,
    handleRunOnce,
    handleToggleClipboardAutoImport,
    handleUpdateExportDirectoryAutoImport,
    handleVerifyBrowserExtension,
  } = controller;
  const clipboardEnabled = daemonStatus?.favorites_clipboard_auto_enabled ?? true;
  const exportDirectoryEnabled = daemonStatus?.favorites_export_directory_auto_enabled ?? true;
  const exportDirectoryPath = daemonStatus?.favorites_export_directory_path || ".tmp/wechat_favorites_inbox";
  const extensionPath = daemonStatus?.browser_extension_path || "browser-extension/chrome";
  const [exportDirectoryInput, setExportDirectoryInput] = useState(exportDirectoryPath);

  useEffect(() => {
    setExportDirectoryInput(exportDirectoryPath);
  }, [exportDirectoryPath]);

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
              {favoritesAutoStatusLabel(daemonStatus?.favorites_auto_status)}
            </span>
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
            <div>
              <p className="text-xs font-medium text-[var(--af-text-primary)]">剪贴板链接自动导入</p>
              <p className="mt-1 text-[11px] leading-5 text-[var(--af-text-tertiary)]">
                {clipboardEnabled
                  ? "复制公众号文章链接后，下一轮采集会自动入队；该链路只稳定获取链接。"
                  : "已关闭剪贴板监听；仍可手动导入，或用浏览器扩展获取正文。"}
              </p>
            </div>
            <label className="inline-flex cursor-pointer items-center gap-2 text-[11px] font-medium text-[var(--af-text-secondary)]">
              <input
                type="checkbox"
                checked={clipboardEnabled}
                disabled={updatingClipboardAutoImport}
                onChange={(event) => void handleToggleClipboardAutoImport(event.target.checked)}
                className="h-4 w-4 accent-[var(--af-accent)] disabled:cursor-not-allowed disabled:opacity-60"
              />
              {updatingClipboardAutoImport ? "保存中" : clipboardEnabled ? "已开启" : "已关闭"}
            </label>
          </div>
          <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
            <div className="rounded-lg border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
              <p className="text-[11px] font-medium text-[var(--af-text-secondary)]">剪贴板</p>
              <p className="mt-1 text-[11px] leading-5 text-[var(--af-text-tertiary)]">
                {daemonStatus?.favorites_clipboard_last_message || "等待下一轮检查。"}
              </p>
            </div>
            <div className="rounded-lg border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
              <p className="text-[11px] font-medium text-[var(--af-text-secondary)]">本地微信适配器</p>
              <p className="mt-1 text-[11px] leading-5 text-[var(--af-text-tertiary)]">
                {daemonStatus?.favorites_wechat_cli_last_message || "未检测到可用适配器。"}
              </p>
            </div>
          </div>
          <div className="mt-2 rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-medium text-[var(--af-text-primary)]">导出文件夹自动导入</p>
                <p className="mt-1 text-[11px] leading-5 text-[var(--af-text-tertiary)]">
                  把微信收藏导出的 HTML/TXT/URL 文件放入该目录，下一轮采集会增量导入。
                </p>
              </div>
              <label className="inline-flex cursor-pointer items-center gap-2 text-[11px] font-medium text-[var(--af-text-secondary)]">
                <input
                  type="checkbox"
                  checked={exportDirectoryEnabled}
                  disabled={updatingExportDirectoryAutoImport}
                  onChange={(event) =>
                    void handleUpdateExportDirectoryAutoImport({
                      enabled: event.target.checked,
                      path: exportDirectoryInput,
                    })
                  }
                  className="h-4 w-4 accent-[var(--af-accent)] disabled:cursor-not-allowed disabled:opacity-60"
                />
                {updatingExportDirectoryAutoImport ? "保存中" : exportDirectoryEnabled ? "已开启" : "已关闭"}
              </label>
            </div>
            <div className="mt-2 flex flex-col gap-2 sm:flex-row">
              <input
                value={exportDirectoryInput}
                onChange={(event) => setExportDirectoryInput(event.target.value)}
                className="min-w-0 flex-1 rounded-lg border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-xs text-[var(--af-text-primary)] outline-none focus:border-[var(--af-accent)]"
                placeholder=".tmp/wechat_favorites_inbox"
              />
              <button
                type="button"
                onClick={() =>
                  void handleUpdateExportDirectoryAutoImport({
                    enabled: exportDirectoryEnabled,
                    path: exportDirectoryInput,
                  })
                }
                disabled={updatingExportDirectoryAutoImport}
                className="af-btn af-btn-secondary px-3 py-2 text-xs disabled:cursor-not-allowed disabled:opacity-60"
              >
                保存目录
              </button>
              <button
                type="button"
                onClick={() => void navigator.clipboard?.writeText(exportDirectoryPath)}
                className="af-btn af-btn-secondary px-3 py-2 text-xs"
              >
                复制路径
              </button>
            </div>
            <p className="mt-2 text-[11px] leading-5 text-[var(--af-text-tertiary)]">
              {daemonStatus?.favorites_export_directory_last_message || "等待下一轮检查。"} · 最近处理{" "}
              {daemonStatus?.favorites_export_directory_last_processed_count ?? 0} 个文件
            </p>
          </div>
          <p className="mt-2 text-[11px] text-[var(--af-text-tertiary)]">
            最近检查 {formatTs(daemonStatus?.favorites_auto_last_at ?? null)} · 发现{" "}
            {daemonStatus?.favorites_auto_discovered_count ?? 0} · 新增{" "}
            {daemonStatus?.favorites_auto_imported_count ?? 0} · 去重{" "}
            {daemonStatus?.favorites_auto_deduplicated_count ?? 0}
          </p>
          {daemonStatus?.favorites_auto_status === "unavailable" ? (
            <p className="mt-2 text-[11px] leading-5 text-[var(--af-warning)]">
              请先完成本机授权；Anti-FOMO 不会上传微信数据库。
            </p>
          ) : null}
        </div>

        <div className="af-surface-card mt-3 rounded-xl border px-3 py-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold text-[var(--af-text-primary)]">浏览器扩展正文导入</p>
              <p className="mt-1 text-[11px] leading-5 text-[var(--af-text-tertiary)]">
                用扩展打开公众号文章页后导入，优先获取正文；这是微信文章知识库的主链路。
              </p>
            </div>
            <span
              className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${
                daemonStatus?.browser_extension_manifest_present ? "af-chip-success" : "af-chip-warning"
              }`}
            >
              {daemonStatus?.browser_extension_manifest_present ? "可安装" : "缺少扩展文件"}
            </span>
          </div>
          <div className="mt-3 rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2 text-[11px] leading-5 text-[var(--af-text-secondary)]">
            <p>1. 打开 Chrome/Edge 扩展管理页，开启开发者模式。</p>
            <p>2. 选择“加载已解压的扩展程序”，目录填入：{extensionPath}</p>
            <p>3. 打开公众号文章页，点击扩展发送正文，再回到首页队列确认。</p>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void navigator.clipboard?.writeText(extensionPath)}
              className="af-btn af-btn-secondary px-3 py-1 text-xs"
            >
              复制扩展目录
            </button>
            <button
              type="button"
              onClick={() => void handleVerifyBrowserExtension()}
              disabled={verifyingBrowserExtension}
              className="af-btn af-btn-primary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
            >
              {verifyingBrowserExtension ? "验证中..." : "验证正文链路"}
            </button>
          </div>
          <p className="mt-2 text-[11px] leading-5 text-[var(--af-text-tertiary)]">
            最近验证 {formatTs(daemonStatus?.browser_extension_last_verification_at ?? null)} ·{" "}
            {daemonStatus?.browser_extension_last_verification_message || "未验证"}
            {daemonStatus?.browser_extension_last_verification_report
              ? " · 已生成验证报告"
              : ""}
          </p>
        </div>

        <details className="mt-3 rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-3">
          <summary className="cursor-pointer text-[11px] uppercase tracking-[0.14em] text-[var(--af-text-tertiary)]">
            高级记录
          </summary>
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
        </details>
      </div>
  );
}
