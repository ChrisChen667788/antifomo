"use client";

import Link from "next/link";
import type { ApiResearchMarkdownArchive } from "@/lib/api/types";
import { ResearchArchiveSectionLinkPopover } from "@/components/research/research-archive-section-link-popover";
import { sanitizeExternalDisplayText } from "@/lib/commercial-risk-copy";
import {
  archiveDeliveryMetricToneClassName,
  extractArchiveFollowupImpactSummary,
  type ArchiveDeliveryDigest,
  type ArchiveDeliveryScore,
} from "@/lib/research-archive-metadata";

export type ArchiveDeliveryFilter = "all" | "strong_evidence" | "needs_followup" | "official_rich";
export type ArchiveSortMode = "updated_desc" | "evidence_strength" | "outstanding_count" | "official_ratio";

export type ResearchCenterMarkdownArchiveItem = {
  archive: ApiResearchMarkdownArchive;
  digest: ArchiveDeliveryDigest | null;
  score: ArchiveDeliveryScore;
};

type ArchiveOption<T extends string> = {
  key: T;
  label: string;
};

function markdownArchiveKindLabel(kind: ApiResearchMarkdownArchive["archive_kind"]) {
  if (kind === "topic_version_recap") return "版本复盘";
  if (kind === "archive_diff_recap") return "差异复盘";
  return "Compare 导出";
}

function markdownArchiveKindTone(kind: ApiResearchMarkdownArchive["archive_kind"]) {
  if (kind === "topic_version_recap") return "af-chip af-chip-warning";
  if (kind === "archive_diff_recap") return "af-chip af-chip-success";
  return "af-chip af-chip-info";
}

export function ResearchCenterMarkdownArchivesSection({
  archiveDeliveryFilter,
  archiveFilterMeta,
  archiveLinkMessage,
  archiveSortMeta,
  archiveSortMode,
  buildCompareSnapshotHref,
  buildMarkdownArchiveHref,
  buildTopicWorkspaceHref,
  onArchiveDeliveryFilterChange,
  onArchiveLinkMessage,
  onArchiveSortModeChange,
  onDeleteMarkdownArchive,
  onDownloadMarkdownArchive,
  t,
  visibleMarkdownArchives,
  workspaceSaving,
}: {
  archiveDeliveryFilter: ArchiveDeliveryFilter;
  archiveFilterMeta: Array<ArchiveOption<ArchiveDeliveryFilter>>;
  archiveLinkMessage: string;
  archiveSortMeta: Array<ArchiveOption<ArchiveSortMode>>;
  archiveSortMode: ArchiveSortMode;
  buildCompareSnapshotHref: (snapshotId: string) => string;
  buildMarkdownArchiveHref: (archiveId: string) => string;
  buildTopicWorkspaceHref: (topicId: string) => string;
  onArchiveDeliveryFilterChange: (filter: ArchiveDeliveryFilter) => void;
  onArchiveLinkMessage: (message: string) => void;
  onArchiveSortModeChange: (mode: ArchiveSortMode) => void;
  onDeleteMarkdownArchive: (archiveId: string) => void | Promise<void>;
  onDownloadMarkdownArchive: (archive: ApiResearchMarkdownArchive) => void | Promise<void>;
  t: (key: string, fallback: string) => string;
  visibleMarkdownArchives: ResearchCenterMarkdownArchiveItem[];
  workspaceSaving: boolean;
}) {
  const activeFilterLabel =
    archiveFilterMeta.find((item) => item.key === archiveDeliveryFilter)?.label ||
    t("research.archiveFilterAll", "全部归档");
  const activeSortLabel =
    archiveSortMeta.find((item) => item.key === archiveSortMode)?.label ||
    t("research.archiveSortUpdated", "按更新时间");

  return (
    <section className="af-glass rounded-[30px] p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="af-kicker">{t("research.markdownArchiveKicker", "历史归档")}</p>
          <h3 className="mt-2 text-lg font-semibold text-[var(--af-text-primary)]">
            {t("research.markdownArchiveTitle", "历史归档中心")}
          </h3>
          <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">
            {t("research.markdownArchiveDesc", "查看、下载和对比历史结果。")}
          </p>
        </div>
        <div className="grid min-w-[260px] gap-3 sm:grid-cols-2">
          <label className="space-y-2 text-sm text-[var(--af-text-tertiary)]">
            <span>{t("research.archiveFilterLabel", "交付筛选")}</span>
            <select
              value={archiveDeliveryFilter}
              onChange={(event) => onArchiveDeliveryFilterChange(event.target.value as ArchiveDeliveryFilter)}
              className="af-input w-full bg-[var(--af-surface-elevated)]"
            >
              {archiveFilterMeta.map((option) => (
                <option key={option.key} value={option.key}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-2 text-sm text-[var(--af-text-tertiary)]">
            <span>{t("research.archiveSortLabel", "排序方式")}</span>
            <select
              value={archiveSortMode}
              onChange={(event) => onArchiveSortModeChange(event.target.value as ArchiveSortMode)}
              className="af-input w-full bg-[var(--af-surface-elevated)]"
            >
              {archiveSortMeta.map((option) => (
                <option key={option.key} value={option.key}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
      {archiveLinkMessage ? <p className="mt-3 text-sm text-[var(--af-text-tertiary)]">{archiveLinkMessage}</p> : null}
      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        <span className="rounded-full af-chip px-2.5 py-1 ">
          {t("research.archiveVisibleCount", "可见归档")} · {visibleMarkdownArchives.length}
        </span>
        <span className="rounded-full af-chip px-2.5 py-1 ">{activeFilterLabel}</span>
        <span className="rounded-full af-chip px-2.5 py-1 ">{activeSortLabel}</span>
      </div>

      <div className="mt-4 space-y-3">
        {visibleMarkdownArchives.length ? (
          visibleMarkdownArchives.map(({ archive, digest: archiveDigest }) => {
            const followupSummary = extractArchiveFollowupImpactSummary(archive.metadata_payload);
            return (
              <article key={archive.id} className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold text-[var(--af-text-primary)]">{archive.name}</p>
                      <span className={`rounded-full px-2.5 py-1 text-[11px] ${markdownArchiveKindTone(archive.archive_kind)}`}>
                        {markdownArchiveKindLabel(archive.archive_kind)}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">
                      {archive.query || t("research.centerSavedViewsNoQuery", "无关键词")} · {new Date(archive.updated_at).toLocaleDateString()}
                    </p>
                  </div>
                  <button
                    type="button"
                    disabled={workspaceSaving}
                    onClick={() => void onDeleteMarkdownArchive(archive.id)}
                    className="text-xs font-medium text-[var(--af-text-tertiary)] hover:text-[var(--af-text-secondary)] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {t("common.delete", "删除")}
                  </button>
                </div>
                {archive.summary ? (
                  <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{sanitizeExternalDisplayText(archive.summary)}</p>
                ) : null}
                {archive.preview_text ? (
                  <p className="mt-2 text-xs leading-5 text-[var(--af-text-tertiary)]">{archive.preview_text}</p>
                ) : null}
                {archiveDigest ? (
                  <>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs">
                      {archiveDigest.metrics.map((metric) => (
                        <span
                          key={`${archive.id}-${metric.label}`}
                          className={`rounded-full px-2.5 py-1 ${archiveDeliveryMetricToneClassName(metric.tone)}`}
                        >
                          {metric.label} {metric.value}
                        </span>
                      ))}
                    </div>
                    {archiveDigest.notes.length ? (
                      <p className="mt-2 text-xs leading-5 text-[var(--af-text-tertiary)]">{archiveDigest.notes[0]}</p>
                    ) : null}
                    {archiveDigest.outstandingItems.length ? (
                      <p className="mt-2 text-xs leading-5 text-[var(--af-danger)]">
                        {archiveDigest.outstandingLabel} · {archiveDigest.outstandingItems.slice(0, 3).join(" / ")}
                      </p>
                    ) : null}
                  </>
                ) : null}
                {followupSummary ? (
                  <div className="mt-2 rounded-[16px] af-state-panel-info px-3 py-3">
                    <div className="flex flex-wrap gap-2 text-xs">
                      <span className="rounded-full af-chip af-chip-info px-2.5 py-1 ">
                        标题 · {followupSummary.currentTitleResolution || "无"}
                      </span>
                      <span className="rounded-full af-chip px-2.5 py-1 ">
                        摘要 · {followupSummary.currentSummaryResolution || "无"}
                      </span>
                    </div>
                    <p className="mt-2 text-xs leading-5 text-[var(--af-text-secondary)]">
                      追问影响章节 ·{" "}
                      {followupSummary.currentImpactedSections.length
                        ? followupSummary.currentImpactedSections.slice(0, 3).join(" / ")
                        : "无"}
                    </p>
                  </div>
                ) : null}
                <div className="mt-2 flex flex-wrap gap-2 text-xs">
                  <span className="rounded-full af-chip px-2.5 py-1 ">
                    {Math.max(1, Math.round(archive.content_length / 1024))} KB
                  </span>
                  {archive.tracking_topic_name ? (
                    <span className="rounded-full af-chip af-chip-info px-2.5 py-1 ">{archive.tracking_topic_name}</span>
                  ) : null}
                  {archive.compare_snapshot_name ? (
                    <span className="rounded-full af-chip af-chip-info px-2.5 py-1 ">{archive.compare_snapshot_name}</span>
                  ) : null}
                  {archive.report_version_title ? (
                    <span className="rounded-full af-chip af-chip-warning px-2.5 py-1 ">{archive.report_version_title}</span>
                  ) : null}
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Link href={buildMarkdownArchiveHref(archive.id)} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                    {t("research.markdownArchivePreview", "在线预览")}
                  </Link>
                  <button
                    type="button"
                    onClick={() => void onDownloadMarkdownArchive(archive)}
                    className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                  >
                    {t("research.markdownArchiveDownload", "下载归档")}
                  </button>
                  {archive.archive_kind === "archive_diff_recap" ? (
                    <ResearchArchiveSectionLinkPopover
                      archiveId={archive.id}
                      buttonLabel="复制定位链接"
                      buttonClassName="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                      onCopyMessage={onArchiveLinkMessage}
                    />
                  ) : null}
                  {archive.compare_snapshot_id ? (
                    <Link href={buildCompareSnapshotHref(archive.compare_snapshot_id)} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                      {t("research.compareOpenSnapshot", "打开对比")}
                    </Link>
                  ) : null}
                  {archive.tracking_topic_id ? (
                    <Link href={buildTopicWorkspaceHref(archive.tracking_topic_id)} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                      {t("research.openTopicWorkspace", "专题工作台")}
                    </Link>
                  ) : null}
                </div>
              </article>
            );
          })
        ) : (
          <p className="text-sm text-[var(--af-text-tertiary)]">
            {t("research.markdownArchiveEmpty", "还没有归档，先保存一次导出结果。")}
          </p>
        )}
      </div>
    </section>
  );
}
