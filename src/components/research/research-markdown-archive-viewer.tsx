"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import {
  createResearchMarkdownArchive,
  type ApiResearchMarkdownArchive,
  type ApiResearchMarkdownArchiveDetail,
} from "@/lib/api";
import {
  RESEARCH_MARKDOWN_ARCHIVE_COMPARE_SUMMARY_ANCHOR,
  buildResearchMarkdownArchiveCompareSectionAnchor,
  buildResearchMarkdownArchiveCompareExecBrief,
  buildResearchMarkdownArchiveCompareExecBriefFilename,
  buildResearchMarkdownArchiveCompareExportFilename,
  buildResearchMarkdownArchiveCompareMarkdown,
  buildResearchMarkdownArchiveComparePdfFilename,
  buildResearchMarkdownArchiveComparePlainText,
  buildResearchMarkdownArchiveCompareSummaryLines,
} from "@/lib/research-markdown-archive-recap";
import {
  archiveDeliveryMetricToneClassName,
  extractArchiveFollowupImpactSummary,
  extractArchiveOfflineEvaluationSnapshot,
  extractArchiveSectionDiagnosticsSummary,
  type ArchiveFollowupImpactSummary,
  type ArchiveOfflineEvaluationSnapshot,
  type ArchiveSectionDiagnosticsSummary,
  buildArchiveDeliveryDigest,
} from "@/lib/research-archive-metadata";
import { buildSimplePdfFromText, triggerFileDownload } from "@/lib/research-delivery-export";
import {
  archiveKindLabel,
  archiveKindTone,
  archiveSourceCompareHref,
  buildAbsoluteArchiveCompareHref,
  buildArchiveComparison,
  buildCompareSnapshotHref,
  buildMarkdownArchiveHref,
  buildTopicWorkspaceHref,
  followupResolutionLabel,
  offlineStatusLabel,
  offlineStatusTone,
  parseMarkdownBlocks,
  shortenText,
  type ArchiveComparison,
} from "@/components/research/research-markdown-archive-model";

function renderInlineMarkdown(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /\[([^\]]+)\]\(([^)]+)\)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null = null;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    nodes.push(
      <a
        key={`${keyPrefix}-${match.index}`}
        href={match[2]}
        target="_blank"
        rel="noreferrer"
        className="font-medium text-[var(--af-info)] underline decoration-[var(--af-info)] underline-offset-4 hover:text-[var(--af-info)]"
      >
        {match[1]}
      </a>,
    );
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }
  return nodes;
}

function MarkdownPreview({ content }: { content: string }) {
  const blocks = parseMarkdownBlocks(content);
  return (
    <div className="space-y-4">
      {blocks.map((block, index) => {
        if (block.type === "h1") {
          return (
            <h1 key={`block-${index}`} className="text-2xl font-semibold tracking-[-0.04em] text-[var(--af-text-primary)]">
              {block.text}
            </h1>
          );
        }
        if (block.type === "h2") {
          return (
            <h2 key={`block-${index}`} className="pt-2 text-xl font-semibold text-[var(--af-text-primary)]">
              {block.text}
            </h2>
          );
        }
        if (block.type === "h3") {
          return (
            <h3 key={`block-${index}`} className="pt-1 text-base font-semibold text-[var(--af-text-primary)]">
              {block.text}
            </h3>
          );
        }
        if (block.type === "code") {
          return (
            <pre
              key={`block-${index}`}
              className="overflow-auto rounded-[20px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-inset)] px-4 py-4 text-xs leading-6 text-[var(--af-text-primary)]"
            >
              {block.text}
            </pre>
          );
        }
        if (block.type === "ul" || block.type === "ol") {
          const ListTag = block.type === "ul" ? "ul" : "ol";
          return (
            <ListTag
              key={`block-${index}`}
              className={`space-y-2 text-sm leading-7 text-[var(--af-text-secondary)] ${block.type === "ol" ? "list-decimal pl-5" : "list-none"}`}
            >
              {block.items.map((item, itemIndex) => (
                <li
                  key={`block-${index}-item-${itemIndex}`}
                  className={block.type === "ul" ? "flex gap-2" : ""}
                  style={item.indent > 0 ? { marginLeft: `${item.indent * 18}px` } : undefined}
                >
                  {block.type === "ul" ? <span className="mt-[11px] h-1.5 w-1.5 rounded-full bg-[var(--af-info)]" /> : null}
                  <span>{renderInlineMarkdown(item.text, `block-${index}-item-${itemIndex}`)}</span>
                </li>
              ))}
            </ListTag>
          );
        }
        if (block.type === "p") {
          return (
            <p key={`block-${index}`} className="text-sm leading-7 text-[var(--af-text-secondary)]">
              {renderInlineMarkdown(block.text, `block-${index}`)}
            </p>
          );
        }
        return null;
      })}
    </div>
  );
}

function ArchiveMetaChips({ archive }: { archive: ApiResearchMarkdownArchive }) {
  return (
    <div className="mt-4 flex flex-wrap gap-2 text-xs">
      <span className="rounded-full af-chip px-2.5 py-1 ">
        文件 · {archive.filename}
      </span>
      <span className="rounded-full af-chip px-2.5 py-1 ">
        大小 · {Math.max(1, Math.round(archive.content_length / 1024))} KB
      </span>
      <span className="rounded-full af-chip px-2.5 py-1 ">
        更新 · {new Date(archive.updated_at).toLocaleString()}
      </span>
      {archive.query ? (
        <span className="rounded-full af-chip px-2.5 py-1 ">
          关键词 · {archive.query}
        </span>
      ) : null}
      {archive.tracking_topic_name ? (
        <span className="rounded-full af-chip af-chip-info px-2.5 py-1 ">
          专题 · {archive.tracking_topic_name}
        </span>
      ) : null}
      {archive.report_version_title ? (
        <span className="rounded-full af-chip af-chip-warning px-2.5 py-1 ">
          版本 · {archive.report_version_title}
        </span>
      ) : null}
      {archive.compare_snapshot_name ? (
        <span className="rounded-full af-chip af-chip-info px-2.5 py-1 ">
          快照 · {archive.compare_snapshot_name}
        </span>
      ) : null}
    </div>
  );
}

function ArchiveDeliveryDigestCard({
  archive,
  title,
  sourcePrefix,
}: {
  archive: ApiResearchMarkdownArchive;
  title?: string;
  sourcePrefix?: "current" | "compare";
}) {
  const digest = buildArchiveDeliveryDigest(archive, sourcePrefix);
  if (!digest) {
    return null;
  }
  return (
    <article className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-5">
      <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">
        {title || digest.title}
      </p>
      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        {digest.metrics.map((metric) => (
          <span
            key={`${title || digest.title}-${metric.label}`}
            className={`rounded-full px-2.5 py-1 ${archiveDeliveryMetricToneClassName(metric.tone)}`}
          >
            {metric.label} {metric.value}
          </span>
        ))}
      </div>
      {digest.notes.length ? (
        <ul className="mt-4 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
          {digest.notes.map((note) => (
            <li key={`${title || digest.title}-${note}`} className="flex gap-2">
              <span className="mt-[10px] h-1.5 w-1.5 rounded-full bg-[var(--af-info)]" />
              <span>{note}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {digest.outstandingItems.length ? (
        <p className="mt-4 text-sm leading-6 text-[var(--af-danger)]">
          {digest.outstandingLabel} · {digest.outstandingItems.slice(0, 5).join(" / ")}
        </p>
      ) : null}
    </article>
  );
}

function ArchiveFollowupImpactCard({
  currentSummary,
  compareSummary,
}: {
  currentSummary: ArchiveFollowupImpactSummary | null;
  compareSummary: ArchiveFollowupImpactSummary | null;
}) {
  if (!currentSummary && !compareSummary) {
    return null;
  }
  return (
    <article className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">Follow-up Routing</p>
          <h4 className="mt-2 text-base font-semibold text-[var(--af-text-primary)]">追问影响章节对照</h4>
        </div>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {[
          { key: "current", label: "当前归档", tone: "sky", value: currentSummary },
          { key: "compare", label: "对照归档", tone: "amber", value: compareSummary },
        ].map((item) => (
          <div
            key={item.key}
            className={`rounded-[20px] border p-4 ${item.tone === "sky" ? "border-[var(--af-border-subtle)] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))]" : "border-[var(--af-border-subtle)] bg-[color-mix(in_srgb,var(--af-warning)_10%,var(--af-surface-muted))]"}`}
          >
            <p className={`text-[11px] uppercase tracking-[0.16em] ${item.tone === "sky" ? "text-[var(--af-info)]" : "text-[var(--af-warning)]"}`}>
              {item.label}
            </p>
            {item.value ? (
              <>
                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                  <span className="rounded-full af-chip px-2.5 py-1 ">
                    标题 · {followupResolutionLabel(item.value.currentTitleResolution)}
                  </span>
                  <span className="rounded-full af-chip px-2.5 py-1 ">
                    摘要 · {followupResolutionLabel(item.value.currentSummaryResolution)}
                  </span>
                </div>
                <p className="mt-3 text-sm leading-6 text-[var(--af-text-secondary)]">
                  重点影响章节 · {item.value.currentImpactedSections.length ? item.value.currentImpactedSections.slice(0, 4).join(" / ") : "无"}
                </p>
                {(item.value.baselineTitleResolution || item.value.baselineSummaryResolution || item.value.baselineImpactedSections.length) ? (
                  <p className="mt-2 text-xs leading-5 text-[var(--af-text-tertiary)]">
                    基线参考 · 标题 {followupResolutionLabel(item.value.baselineTitleResolution)} / 摘要 {followupResolutionLabel(item.value.baselineSummaryResolution)} / 章节 {item.value.baselineImpactedSections.length ? item.value.baselineImpactedSections.slice(0, 3).join(" / ") : "无"}
                  </p>
                ) : null}
              </>
            ) : (
              <p className="mt-3 text-sm text-[var(--af-text-tertiary)]">没有可用追问路由摘要。</p>
            )}
          </div>
        ))}
      </div>
    </article>
  );
}

function ArchiveCandidateCard({
  archive,
  baseArchiveId,
  activeCompareId,
}: {
  archive: ApiResearchMarkdownArchive;
  baseArchiveId: string;
  activeCompareId?: string | null;
}) {
  const isActive = activeCompareId === archive.id;
  return (
    <article className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-2.5 py-1 text-[11px] ${archiveKindTone(archive.archive_kind)}`}>
          {archiveKindLabel(archive.archive_kind)}
        </span>
        {archive.tracking_topic_name ? (
          <span className="rounded-full af-chip af-chip-info px-2.5 py-1 text-[11px] ">
            {archive.tracking_topic_name}
          </span>
        ) : null}
      </div>
      <h3 className="mt-3 text-sm font-semibold text-[var(--af-text-primary)]">{archive.name}</h3>
      <p className="mt-2 text-xs leading-6 text-[var(--af-text-tertiary)]">
        {archive.summary || archive.preview_text || "归档已保存，可作为当前文档的对照基线。"}
      </p>
      <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-[var(--af-text-tertiary)]">
        <span className="rounded-full bg-[var(--af-surface-muted)] px-2 py-1">
          {new Date(archive.updated_at).toLocaleDateString()}
        </span>
        {archive.report_version_title ? (
          <span className="rounded-full af-chip af-chip-warning px-2 py-1 ">
            {archive.report_version_title}
          </span>
        ) : null}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Link
          href={buildMarkdownArchiveHref(baseArchiveId, archive.id)}
          className={`af-btn border px-3 py-1.5 text-xs ${isActive ? "border-[var(--af-border-strong)] bg-[var(--af-surface-selected)] text-[var(--af-info)]" : "af-btn-secondary"}`}
        >
          {isActive ? "当前对照" : "设为对照"}
        </Link>
        <Link href={buildMarkdownArchiveHref(archive.id)} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
          单独打开
        </Link>
      </div>
    </article>
  );
}

function ArchiveComparisonSummary({
  archive,
  compareArchive,
  comparison,
  currentSectionSummary,
  compareSectionSummary,
  currentFollowupSummary,
  compareFollowupSummary,
  currentOfflineSnapshot,
  compareOfflineSnapshot,
  onExportRecapMarkdown,
  onExportRecapPdf,
  onExportRecapExecBrief,
  onSaveRecap,
  onCopySectionLink,
  savingRecap,
  activeHash,
  highlightAnchor,
}: {
  archive: ApiResearchMarkdownArchiveDetail;
  compareArchive: ApiResearchMarkdownArchiveDetail;
  comparison: ArchiveComparison;
  currentSectionSummary: ArchiveSectionDiagnosticsSummary | null;
  compareSectionSummary: ArchiveSectionDiagnosticsSummary | null;
  currentFollowupSummary: ArchiveFollowupImpactSummary | null;
  compareFollowupSummary: ArchiveFollowupImpactSummary | null;
  currentOfflineSnapshot: ArchiveOfflineEvaluationSnapshot | null;
  compareOfflineSnapshot: ArchiveOfflineEvaluationSnapshot | null;
  onExportRecapMarkdown: () => void;
  onExportRecapPdf: () => void;
  onExportRecapExecBrief: () => void;
  onSaveRecap: () => void;
  onCopySectionLink: (anchorId: string, sectionTitle: string) => void;
  savingRecap: boolean;
  activeHash: string;
  highlightAnchor: boolean;
}) {
  const summaryLines = buildResearchMarkdownArchiveCompareSummaryLines(archive, compareArchive, comparison);

  return (
    <section
      id={RESEARCH_MARKDOWN_ARCHIVE_COMPARE_SUMMARY_ANCHOR}
      className={`af-glass rounded-[30px] p-6 transition-all duration-300 ${
        highlightAnchor ? "border border-[var(--af-border-strong)] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] shadow-[var(--af-shadow-soft)]" : ""
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="af-kicker">Archive Compare</p>
          <h3 className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-[var(--af-text-primary)]">
            当前归档 vs 对照归档
          </h3>
          <p className="mt-2 text-sm leading-6 text-[var(--af-text-tertiary)]">
            用统一的 section 和要点切片对照两个 Markdown 版本，优先展示结构变化和新增结论。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onSaveRecap}
            disabled={savingRecap}
            className="af-btn af-btn-secondary border px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
          >
            {savingRecap ? "保存中..." : "保存差异复盘"}
          </button>
          <button type="button" onClick={onExportRecapMarkdown} className="af-btn af-btn-secondary border px-4 py-2 text-sm">
            导出 Markdown
          </button>
          <button type="button" onClick={onExportRecapPdf} className="af-btn af-btn-secondary border px-4 py-2 text-sm">
            导出 PDF
          </button>
          <button type="button" onClick={onExportRecapExecBrief} className="af-btn af-btn-secondary border px-4 py-2 text-sm">
            导出 Exec Brief
          </button>
          <Link href={buildMarkdownArchiveHref(compareArchive.id, archive.id)} className="af-btn af-btn-secondary border px-4 py-2 text-sm">
            交换当前/对照
          </Link>
          <Link href={buildMarkdownArchiveHref(archive.id)} className="af-btn af-btn-secondary border px-4 py-2 text-sm">
            退出对照
          </Link>
        </div>
      </div>

      {summaryLines.length ? (
        <div className="mt-5 rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-5">
          <p className="text-xs font-medium uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">Diff Summary</p>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
            {summaryLines.map((line, index) => (
              <li key={`summary-line-${index}`} className="flex gap-2">
                <span className="mt-[10px] h-1.5 w-1.5 rounded-full bg-[var(--af-info)]" />
                <span>{line}</span>
              </li>
            ))}
          </ul>
          {comparison.changedSections.length ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {comparison.changedSections.slice(0, 6).map((section) => {
                const anchorId = buildResearchMarkdownArchiveCompareSectionAnchor(section.key);
                const isActive = activeHash === `#${anchorId}`;
                return (
                  <Link
                    key={`section-jump-${section.key}`}
                    href={`#${anchorId}`}
                    className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
                      isActive
                        ? "border-[var(--af-border-strong)] bg-[var(--af-surface-selected)] text-[var(--af-info)]"
                        : "border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] text-[var(--af-text-tertiary)] hover:border-[var(--af-border-subtle)] hover:text-[var(--af-info)]"
                    }`}
                  >
                    {section.title}
                  </Link>
                );
              })}
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <div className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
          <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--af-text-tertiary)]">Shared Sections</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--af-text-primary)]">{comparison.sharedSectionCount}</p>
        </div>
        <div className="rounded-[22px] af-state-panel-success p-4">
          <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--af-success)]">Current Added</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--af-success)]">{comparison.addedSections.length}</p>
        </div>
        <div className="rounded-[22px] af-state-panel-danger p-4">
          <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--af-danger)]">Baseline Only</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--af-danger)]">{comparison.removedSections.length}</p>
        </div>
        <div className="rounded-[22px] af-state-panel-warning p-4">
          <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--af-warning)]">Changed Sections</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--af-warning)]">{comparison.changedSections.length}</p>
        </div>
        <div className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-4">
          <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--af-text-tertiary)]">Coverage</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--af-text-primary)]">
            {comparison.currentSectionCount}/{comparison.compareSectionCount}
          </p>
        </div>
      </div>

      {(currentSectionSummary || compareSectionSummary || currentFollowupSummary || compareFollowupSummary || currentOfflineSnapshot || compareOfflineSnapshot) ? (
        <div className="mt-5 grid gap-4 xl:grid-cols-3">
          <article className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">章节检查</p>
                <h4 className="mt-2 text-base font-semibold text-[var(--af-text-primary)]">章节风险对照</h4>
              </div>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <div className="rounded-[20px] af-state-panel-info p-4">
                <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--af-info)]">当前归档</p>
                <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                  待核验 {currentSectionSummary?.mode === "compare" ? currentSectionSummary.weakSectionCount : currentSectionSummary?.currentWeakSectionCount || 0}
                  {" / "}配额风险 {currentSectionSummary?.quotaRiskSectionCount || 0}
                  {" / "}矛盾 {currentSectionSummary?.contradictionSectionCount || 0}
                </p>
                <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                  重点章节 · {currentSectionSummary?.highlightedSections?.length ? currentSectionSummary.highlightedSections.slice(0, 4).join(" / ") : "无"}
                </p>
              </div>
              <div className="rounded-[20px] af-state-panel-warning p-4">
                <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--af-warning)]">对照归档</p>
                <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                  待核验 {compareSectionSummary?.mode === "compare" ? compareSectionSummary.weakSectionCount : compareSectionSummary?.currentWeakSectionCount || 0}
                  {" / "}配额风险 {compareSectionSummary?.quotaRiskSectionCount || 0}
                  {" / "}矛盾 {compareSectionSummary?.contradictionSectionCount || 0}
                </p>
                <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                  重点章节 · {compareSectionSummary?.highlightedSections?.length ? compareSectionSummary.highlightedSections.slice(0, 4).join(" / ") : "无"}
                </p>
              </div>
            </div>
          </article>

          <ArchiveFollowupImpactCard
            currentSummary={currentFollowupSummary}
            compareSummary={compareFollowupSummary}
          />

          <article className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">质量复核</p>
                <h4 className="mt-2 text-base font-semibold text-[var(--af-text-primary)]">质量复核快照对照</h4>
              </div>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {[{
                label: "当前归档",
                value: currentOfflineSnapshot,
                tone: "sky",
              }, {
                label: "对照归档",
                value: compareOfflineSnapshot,
                tone: "amber",
              }].map((item) => (
                <div
                  key={item.label}
                  className={`rounded-[20px] border p-4 ${item.tone === "sky" ? "border-[var(--af-border-subtle)] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))]" : "border-[var(--af-border-subtle)] bg-[color-mix(in_srgb,var(--af-warning)_10%,var(--af-surface-muted))]"}`}
                >
                  <p className={`text-[11px] uppercase tracking-[0.16em] ${item.tone === "sky" ? "text-[var(--af-info)]" : "text-[var(--af-warning)]"}`}>
                    {item.label}
                  </p>
                  {item.value?.metrics?.length ? (
                    <>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {item.value.metrics.slice(0, 3).map((metric) => (
                          <span key={`${item.label}-${metric.key}`} className={`rounded-full px-2.5 py-1 text-xs font-medium ${offlineStatusTone(metric.status)}`}>
                            {metric.label} {metric.percent}% · {offlineStatusLabel(metric.status)}
                          </span>
                        ))}
                      </div>
                      {item.value.summaryLines.length ? (
                        <p className="mt-3 text-sm leading-6 text-[var(--af-text-secondary)]">
                          {item.value.summaryLines[0]}
                        </p>
                      ) : null}
                    </>
                  ) : (
                    <p className="mt-3 text-sm text-[var(--af-text-tertiary)]">没有可用回归快照。</p>
                  )}
                </div>
              ))}
            </div>
          </article>
        </div>
      ) : null}

      <div className="mt-5 grid gap-4 xl:grid-cols-[1.25fr_0.75fr]">
        <div className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full af-chip af-chip-info px-2.5 py-1 text-[11px] ">当前</span>
            <p className="text-sm font-semibold text-[var(--af-text-primary)]">{archive.name}</p>
          </div>
          <ArchiveMetaChips archive={archive} />
          {comparison.addedSections.length ? (
            <div className="mt-4">
              <p className="text-xs font-medium uppercase tracking-[0.22em] text-[var(--af-success)]">新增 Section</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {comparison.addedSections.slice(0, 5).map((section) => (
                  <span key={`current-added-${section.key}`} className="rounded-full af-chip af-chip-success px-2.5 py-1 text-xs ">
                    {section.title}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
          {currentFollowupSummary?.currentImpactedSections.length ? (
            <div className="mt-4">
              <p className="text-xs font-medium uppercase tracking-[0.22em] text-[var(--af-info)]">追问影响章节</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {currentFollowupSummary.currentImpactedSections.slice(0, 4).map((section) => (
                  <span key={`current-followup-${section}`} className="rounded-full af-chip af-chip-info px-2.5 py-1 text-xs ">
                    {section}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <div className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full af-chip af-chip-warning px-2.5 py-1 text-[11px] ">对照</span>
            <p className="text-sm font-semibold text-[var(--af-text-primary)]">{compareArchive.name}</p>
          </div>
          <ArchiveMetaChips archive={compareArchive} />
          {comparison.removedSections.length ? (
            <div className="mt-4">
              <p className="text-xs font-medium uppercase tracking-[0.22em] text-[var(--af-danger)]">仅对照中存在</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {comparison.removedSections.slice(0, 5).map((section) => (
                  <span key={`compare-removed-${section.key}`} className="rounded-full af-chip af-chip-danger px-2.5 py-1 text-xs ">
                    {section.title}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
          {compareFollowupSummary?.currentImpactedSections.length ? (
            <div className="mt-4">
              <p className="text-xs font-medium uppercase tracking-[0.22em] text-[var(--af-warning)]">追问影响章节</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {compareFollowupSummary.currentImpactedSections.slice(0, 4).map((section) => (
                  <span key={`compare-followup-${section}`} className="rounded-full af-chip af-chip-warning px-2.5 py-1 text-xs ">
                    {section}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <div className="mt-5 space-y-3">
        {comparison.changedSections.length ? (
          comparison.changedSections.slice(0, 8).map((section) => {
            const anchorId = buildResearchMarkdownArchiveCompareSectionAnchor(section.key);
            const isSectionFocused = activeHash === `#${anchorId}`;
            return (
            <article
              key={section.key}
              id={anchorId}
              className={`scroll-mt-24 rounded-[24px] border p-5 transition-all duration-300 ${
                isSectionFocused
                  ? "border-[var(--af-border-strong)] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] shadow-[var(--af-shadow-soft)]"
                  : "border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)]"
              }`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full af-chip px-2.5 py-1 text-[11px] ">
                  H{section.level}
                </span>
                <h4 className="text-sm font-semibold text-[var(--af-text-primary)]">{section.title}</h4>
                <span className="rounded-full af-chip px-2.5 py-1 text-[11px] ">
                  重合要点 {section.sharedCount}
                </span>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Link href={`#${anchorId}`} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                    定位
                  </Link>
                  <button
                    type="button"
                    onClick={() => onCopySectionLink(anchorId, section.title)}
                    className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                  >
                    复制深链
                  </button>
                </div>
              </div>
              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <div className="rounded-[20px] af-state-panel-success p-4">
                  <p className="text-xs font-medium uppercase tracking-[0.22em] text-[var(--af-success)]">当前新增</p>
                  {section.currentOnly.length ? (
                    <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--af-success)]">
                      {section.currentOnly.slice(0, 4).map((item, index) => (
                        <li key={`${section.key}-current-${index}`} className="flex gap-2">
                          <span className="mt-[10px] h-1.5 w-1.5 rounded-full bg-[var(--af-success)]" />
                          <span>{shortenText(item, 160)}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-3 text-sm text-[var(--af-success)]">没有额外新增要点。</p>
                  )}
                </div>
                <div className="rounded-[20px] af-state-panel-danger p-4">
                  <p className="text-xs font-medium uppercase tracking-[0.22em] text-[var(--af-danger)]">对照独有</p>
                  {section.compareOnly.length ? (
                    <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--af-danger)]">
                      {section.compareOnly.slice(0, 4).map((item, index) => (
                        <li key={`${section.key}-compare-${index}`} className="flex gap-2">
                          <span className="mt-[10px] h-1.5 w-1.5 rounded-full bg-[var(--af-danger)]" />
                          <span>{shortenText(item, 160)}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-3 text-sm text-[var(--af-danger)]">该 section 在当前版本里已完全覆盖。</p>
                  )}
                </div>
              </div>
            </article>
          );
          })
        ) : (
          <div className="rounded-[24px] af-state-panel-success p-5 text-sm text-[var(--af-success)]">
            两份归档的结构和主要要点基本一致，没有检测到显著差异。
          </div>
        )}
      </div>
    </section>
  );
}

export function ResearchMarkdownArchiveViewer({
  archive,
  compareArchive = null,
  relatedArchives = [],
}: {
  archive: ApiResearchMarkdownArchiveDetail;
  compareArchive?: ApiResearchMarkdownArchiveDetail | null;
  relatedArchives?: ApiResearchMarkdownArchive[];
}) {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [savingRecap, setSavingRecap] = useState(false);
  const [activeHash, setActiveHash] = useState("");
  const comparison = compareArchive ? buildArchiveComparison(archive.content, compareArchive.content) : null;
  const sourceCompareHref = archive.archive_kind === "archive_diff_recap" ? archiveSourceCompareHref(archive) : "";
  const compareSummaryFocused = activeHash === `#${RESEARCH_MARKDOWN_ARCHIVE_COMPARE_SUMMARY_ANCHOR}`;
  const archiveDigest = buildArchiveDeliveryDigest(archive);
  const compareArchiveDigest = compareArchive ? buildArchiveDeliveryDigest(compareArchive) : null;
  const currentSectionSummary = extractArchiveSectionDiagnosticsSummary(archive.metadata_payload);
  const compareSectionSummary = compareArchive ? extractArchiveSectionDiagnosticsSummary(compareArchive.metadata_payload) : null;
  const currentFollowupSummary = extractArchiveFollowupImpactSummary(archive.metadata_payload);
  const compareFollowupSummary = compareArchive ? extractArchiveFollowupImpactSummary(compareArchive.metadata_payload) : null;
  const currentOfflineSnapshot = extractArchiveOfflineEvaluationSnapshot(archive.metadata_payload);
  const compareOfflineSnapshot = compareArchive ? extractArchiveOfflineEvaluationSnapshot(compareArchive.metadata_payload) : null;

  useEffect(() => {
    const syncHash = () => {
      setActiveHash(window.location.hash || "");
    };
    syncHash();
    window.addEventListener("hashchange", syncHash);
    return () => window.removeEventListener("hashchange", syncHash);
  }, []);

  useEffect(() => {
    if (!activeHash) return;
    const element = document.getElementById(activeHash.replace(/^#/, ""));
    if (!element) return;
    element.scrollIntoView({ block: "start", behavior: "smooth" });
  }, [activeHash]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(archive.content);
      setMessage("Markdown 已复制到剪贴板");
    } catch {
      setMessage("复制失败，请稍后重试");
    }
  };

  const handleDownload = () => {
    triggerFileDownload(archive.filename, archive.content, "text/markdown;charset=utf-8");
    setMessage("Markdown 文件已下载");
  };

  const buildCompareRecapBundle = (generatedAt: Date) => {
    if (!compareArchive || !comparison) {
      return null;
    }
    const appCompareUrl = buildAbsoluteArchiveCompareHref(archive.id, compareArchive.id);
    const exportOptions = {
      archive,
      compareArchive,
      comparison,
      generatedAt,
      appCompareUrl,
    };
    return {
      markdownFilename: buildResearchMarkdownArchiveCompareExportFilename(archive.name, compareArchive.name, generatedAt),
      pdfFilename: buildResearchMarkdownArchiveComparePdfFilename(archive.name, compareArchive.name, generatedAt),
      execBriefFilename: buildResearchMarkdownArchiveCompareExecBriefFilename(archive.name, compareArchive.name, generatedAt),
      markdown: buildResearchMarkdownArchiveCompareMarkdown(exportOptions),
      plainText: buildResearchMarkdownArchiveComparePlainText(exportOptions),
      execBrief: buildResearchMarkdownArchiveCompareExecBrief(exportOptions),
      summary:
        buildResearchMarkdownArchiveCompareSummaryLines(archive, compareArchive, comparison)[0] ||
        `${archive.name} vs ${compareArchive.name}`,
    };
  };

  const handleExportCompareRecapMarkdown = () => {
    if (!compareArchive || !comparison) return;
    const generatedAt = new Date();
    const bundle = buildCompareRecapBundle(generatedAt);
    if (!bundle) return;
    triggerFileDownload(bundle.markdownFilename, bundle.markdown, "text/markdown;charset=utf-8");
    setMessage("归档差异复盘 Markdown 已下载");
  };

  const handleExportCompareRecapPdf = () => {
    const generatedAt = new Date();
    const bundle = buildCompareRecapBundle(generatedAt);
    if (!bundle) return;
    triggerFileDownload(bundle.pdfFilename, buildSimplePdfFromText(bundle.plainText), "application/pdf");
    setMessage("归档差异复盘 PDF 已下载");
  };

  const handleExportCompareRecapExecBrief = () => {
    const generatedAt = new Date();
    const bundle = buildCompareRecapBundle(generatedAt);
    if (!bundle) return;
    triggerFileDownload(bundle.execBriefFilename, bundle.execBrief, "text/markdown;charset=utf-8");
    setMessage("归档差异复盘 Exec Brief 已下载");
  };

  const handleSaveCompareRecap = async () => {
    if (!compareArchive || !comparison) return;
    const generatedAt = new Date();
    const bundle = buildCompareRecapBundle(generatedAt);
    if (!bundle) return;
    const defaultName = `${archive.name} vs ${compareArchive.name} · 差异复盘`;
    const name = window.prompt("输入一个差异复盘归档名称，便于后续回看", defaultName)?.trim();
    if (!name) return;
    const summary = bundle.summary;
    setSavingRecap(true);
    try {
      const archiveMetadata = archive.metadata_payload && typeof archive.metadata_payload === "object" ? archive.metadata_payload : {};
      const compareMetadata = compareArchive.metadata_payload && typeof compareArchive.metadata_payload === "object" ? compareArchive.metadata_payload : {};
      const saved = await createResearchMarkdownArchive({
        archive_kind: "archive_diff_recap",
        name,
        filename: bundle.markdownFilename,
        query: archive.query || compareArchive.query || "",
        region_filter: archive.region_filter || compareArchive.region_filter || "",
        industry_filter: archive.industry_filter || compareArchive.industry_filter || "",
        tracking_topic_id: archive.tracking_topic_id || compareArchive.tracking_topic_id || undefined,
        compare_snapshot_id: archive.compare_snapshot_id || undefined,
        report_version_id: archive.report_version_id || undefined,
        summary,
        content: bundle.markdown,
        metadata_payload: {
          current_archive_id: archive.id,
          current_archive_name: archive.name,
          current_archive_kind: archive.archive_kind,
          compare_archive_id: compareArchive.id,
          compare_archive_name: compareArchive.name,
          compare_archive_kind: compareArchive.archive_kind,
          shared_section_count: comparison.sharedSectionCount,
          added_section_count: comparison.addedSections.length,
          removed_section_count: comparison.removedSections.length,
          changed_section_count: comparison.changedSections.length,
          current_evidence_appendix_summary:
            archiveMetadata.evidence_appendix_summary && typeof archiveMetadata.evidence_appendix_summary === "object"
              ? archiveMetadata.evidence_appendix_summary
              : {},
          compare_evidence_appendix_summary:
            compareMetadata.evidence_appendix_summary && typeof compareMetadata.evidence_appendix_summary === "object"
              ? compareMetadata.evidence_appendix_summary
              : {},
          current_section_diagnostics_summary:
            archiveMetadata.section_diagnostics_summary && typeof archiveMetadata.section_diagnostics_summary === "object"
              ? archiveMetadata.section_diagnostics_summary
              : {},
          compare_section_diagnostics_summary:
            compareMetadata.section_diagnostics_summary && typeof compareMetadata.section_diagnostics_summary === "object"
              ? compareMetadata.section_diagnostics_summary
              : {},
          current_offline_evaluation_snapshot:
            archiveMetadata.offline_evaluation_snapshot && typeof archiveMetadata.offline_evaluation_snapshot === "object"
              ? archiveMetadata.offline_evaluation_snapshot
              : {},
          compare_offline_evaluation_snapshot:
            compareMetadata.offline_evaluation_snapshot && typeof compareMetadata.offline_evaluation_snapshot === "object"
              ? compareMetadata.offline_evaluation_snapshot
              : {},
          current_followup_impact_summary:
            archiveMetadata.followup_impact_summary && typeof archiveMetadata.followup_impact_summary === "object"
              ? archiveMetadata.followup_impact_summary
              : {},
          compare_followup_impact_summary:
            compareMetadata.followup_impact_summary && typeof compareMetadata.followup_impact_summary === "object"
              ? compareMetadata.followup_impact_summary
              : {},
          current_linked_report_diff_status:
            typeof archiveMetadata.linked_report_diff_status === "string" ? archiveMetadata.linked_report_diff_status : "",
          compare_linked_report_diff_status:
            typeof compareMetadata.linked_report_diff_status === "string" ? compareMetadata.linked_report_diff_status : "",
        },
      });
      setMessage(`已保存差异复盘归档：${saved.name}`);
      router.refresh();
    } catch {
      setMessage("保存差异复盘归档失败，请稍后重试");
    } finally {
      setSavingRecap(false);
    }
  };

  const handleCopySectionLink = async (anchorId: string, sectionTitle: string) => {
    try {
      const url = new URL(window.location.href);
      url.hash = anchorId;
      await navigator.clipboard.writeText(url.toString());
      setMessage(`${sectionTitle} 深链已复制`);
    } catch {
      setMessage("复制 section 深链失败，请稍后重试");
    }
  };

  return (
    <div className="space-y-5">
      <section className="af-glass rounded-[30px] p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <div className="flex flex-wrap items-center gap-2">
              <p className="af-kicker">Markdown Archive</p>
              <span className={`rounded-full px-2.5 py-1 text-[11px] ${archiveKindTone(archive.archive_kind)}`}>
                {archiveKindLabel(archive.archive_kind)}
              </span>
              {compareArchive ? (
                <span className="rounded-full af-chip px-2.5 py-1 text-[11px] ">
                  对照中
                </span>
              ) : null}
            </div>
            <h2 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-[var(--af-text-primary)]">{archive.name}</h2>
            <p className="mt-3 text-sm leading-6 text-[var(--af-text-secondary)]">
              {archive.summary || archive.preview_text || "当前归档已保存到历史中心，可在线查看、下载或作为版本对照基线。"}
            </p>
            <ArchiveMetaChips archive={archive} />
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleCopy}
              className="af-btn af-btn-secondary border px-4 py-2 text-sm"
            >
              复制 Markdown
            </button>
            <button
              type="button"
              onClick={handleDownload}
              className="af-btn af-btn-secondary border px-4 py-2 text-sm"
            >
              下载 Markdown
            </button>
            <Link href="/research" className="af-btn af-btn-secondary border px-4 py-2 text-sm">
              返回商机情报中心
            </Link>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {archive.compare_snapshot_id ? (
            <Link href={buildCompareSnapshotHref(archive.compare_snapshot_id)} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
              打开关联快照
            </Link>
          ) : null}
          {archive.tracking_topic_id ? (
            <Link href={buildTopicWorkspaceHref(archive.tracking_topic_id)} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
              打开专题工作台
            </Link>
          ) : null}
          {sourceCompareHref ? (
            <Link href={sourceCompareHref} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
              打开原始对照
            </Link>
          ) : null}
          {compareArchive ? (
            <Link href={buildMarkdownArchiveHref(compareArchive.id)} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
              打开对照归档
            </Link>
          ) : null}
        </div>
        {message ? <p className="mt-3 text-sm text-[var(--af-text-tertiary)]">{message}</p> : null}
      </section>

      {archiveDigest || compareArchiveDigest ? (
        <section className="grid gap-4 xl:grid-cols-2">
          <ArchiveDeliveryDigestCard
            archive={archive}
            title={compareArchive ? "当前归档交付信号" : undefined}
          />
          {compareArchive ? (
            <ArchiveDeliveryDigestCard archive={compareArchive} title="对照归档交付信号" />
          ) : null}
        </section>
      ) : null}

      {comparison && compareArchive ? (
          <ArchiveComparisonSummary
            archive={archive}
            compareArchive={compareArchive}
            comparison={comparison}
            currentSectionSummary={currentSectionSummary}
            compareSectionSummary={compareSectionSummary}
            currentFollowupSummary={currentFollowupSummary}
            compareFollowupSummary={compareFollowupSummary}
            currentOfflineSnapshot={currentOfflineSnapshot}
            compareOfflineSnapshot={compareOfflineSnapshot}
            onExportRecapMarkdown={handleExportCompareRecapMarkdown}
            onExportRecapPdf={handleExportCompareRecapPdf}
            onExportRecapExecBrief={handleExportCompareRecapExecBrief}
          onSaveRecap={() => void handleSaveCompareRecap()}
          onCopySectionLink={handleCopySectionLink}
          savingRecap={savingRecap}
          activeHash={activeHash}
          highlightAnchor={compareSummaryFocused}
        />
      ) : null}

      <section className="af-glass rounded-[30px] p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="af-kicker">Related Archives</p>
            <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">
              优先按同专题、同归档类型和相近版本排序，可快速切换对照基线。
            </p>
          </div>
        </div>
        {relatedArchives.length ? (
          <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {relatedArchives.map((item) => (
              <ArchiveCandidateCard
                key={item.id}
                archive={item}
                baseArchiveId={archive.id}
                activeCompareId={compareArchive?.id || null}
              />
            ))}
          </div>
        ) : (
          <div className="mt-5 rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-5 text-sm text-[var(--af-text-tertiary)]">
            当前还没有足够接近的历史归档可供对照。先从 compare 导出或专题复盘报告继续沉淀版本。
          </div>
        )}
      </section>

      <section className="af-glass rounded-[30px] p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="af-kicker">{compareArchive ? "Side-by-Side Preview" : "Archive Preview"}</p>
            <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">
              {compareArchive
                ? "左右并排查看当前归档和对照归档的正文结构，适合做快速复盘。"
                : "当前为应用内轻量预览，保留标题、列表和链接结构，适合快速复盘。"}
            </p>
          </div>
        </div>
        {compareArchive ? (
          <div className="mt-5 grid gap-4 xl:grid-cols-2">
            <div className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-5">
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <span className="rounded-full af-chip af-chip-info px-2.5 py-1 text-[11px] ">当前归档</span>
                <p className="text-sm font-semibold text-[var(--af-text-primary)]">{archive.name}</p>
              </div>
              <MarkdownPreview content={archive.content} />
            </div>
            <div className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-5">
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <span className="rounded-full af-chip af-chip-warning px-2.5 py-1 text-[11px] ">对照归档</span>
                <p className="text-sm font-semibold text-[var(--af-text-primary)]">{compareArchive.name}</p>
              </div>
              <MarkdownPreview content={compareArchive.content} />
            </div>
          </div>
        ) : (
          <div className="mt-5 rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-5">
            <MarkdownPreview content={archive.content} />
          </div>
        )}
      </section>

      <section className="af-glass rounded-[30px] p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="af-kicker">Raw Markdown</p>
            <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">
              保留原始内容，方便复制到外部文档或继续交给别的系统处理。
            </p>
          </div>
        </div>
        <pre className="mt-5 overflow-auto rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-inset)] px-5 py-5 text-xs leading-6 text-[var(--af-text-primary)]">
          {archive.content}
        </pre>
      </section>
    </div>
  );
}
