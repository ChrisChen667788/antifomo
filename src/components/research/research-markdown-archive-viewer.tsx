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
  extractArchiveOfflineEvaluationSnapshot,
  extractArchiveSectionDiagnosticsSummary,
  type ArchiveOfflineEvaluationSnapshot,
  type ArchiveSectionDiagnosticsSummary,
  buildArchiveDeliveryDigest,
} from "@/lib/research-archive-metadata";
import { buildSimplePdfFromText, triggerFileDownload } from "@/lib/research-delivery-export";

type MarkdownBlock =
  | { type: "h1" | "h2" | "h3"; text: string }
  | { type: "p"; text: string }
  | { type: "ul" | "ol"; items: Array<{ text: string; indent: number }> }
  | { type: "code"; text: string };

type ArchiveSection = {
  key: string;
  title: string;
  level: 1 | 2 | 3;
  items: string[];
};

type ArchiveSectionDiff = {
  key: string;
  title: string;
  level: 1 | 2 | 3;
  currentOnly: string[];
  compareOnly: string[];
  sharedCount: number;
};

type ArchiveComparison = {
  currentSectionCount: number;
  compareSectionCount: number;
  sharedSectionCount: number;
  addedSections: ArchiveSection[];
  removedSections: ArchiveSection[];
  changedSections: ArchiveSectionDiff[];
};

function archiveKindLabel(kind: ApiResearchMarkdownArchive["archive_kind"]) {
  if (kind === "topic_version_recap") return "版本复盘";
  if (kind === "archive_diff_recap") return "差异复盘";
  return "Compare 导出";
}

function archiveKindTone(kind: ApiResearchMarkdownArchive["archive_kind"]) {
  if (kind === "topic_version_recap") return "bg-amber-50 text-amber-700";
  if (kind === "archive_diff_recap") return "bg-emerald-50 text-emerald-700";
  return "bg-sky-50 text-sky-700";
}

function buildCompareSnapshotHref(snapshotId: string) {
  return `/research/compare?snapshot=${encodeURIComponent(snapshotId)}`;
}

function buildTopicWorkspaceHref(topicId: string) {
  return `/research/topics/${topicId}`;
}

function buildMarkdownArchiveHref(archiveId: string, compareId?: string | null) {
  const basePath = `/research/archives/${encodeURIComponent(archiveId)}`;
  if (!compareId) return basePath;
  return `${basePath}?compare=${encodeURIComponent(compareId)}`;
}

function buildOriginalArchiveCompareHref(
  currentArchiveId?: string | null,
  compareArchiveId?: string | null,
) {
  if (!currentArchiveId || !compareArchiveId) return "";
  return `${buildMarkdownArchiveHref(currentArchiveId, compareArchiveId)}#${RESEARCH_MARKDOWN_ARCHIVE_COMPARE_SUMMARY_ANCHOR}`;
}

function buildAbsoluteArchiveCompareHref(currentArchiveId?: string | null, compareArchiveId?: string | null) {
  if (!currentArchiveId || typeof window === "undefined") return "";
  const href = buildMarkdownArchiveHref(currentArchiveId, compareArchiveId);
  return new URL(href, window.location.origin).toString();
}

function archiveSourceCompareHref(archive: ApiResearchMarkdownArchiveDetail) {
  const metadata = archive.metadata_payload && typeof archive.metadata_payload === "object" ? archive.metadata_payload : {};
  const currentArchiveId = typeof metadata.current_archive_id === "string" ? metadata.current_archive_id.trim() : "";
  const compareArchiveId = typeof metadata.compare_archive_id === "string" ? metadata.compare_archive_id.trim() : "";
  return buildOriginalArchiveCompareHref(currentArchiveId, compareArchiveId);
}

function offlineStatusTone(status: string) {
  if (status === "good") return "bg-emerald-100 text-emerald-700";
  if (status === "watch") return "bg-amber-100 text-amber-700";
  return "bg-rose-100 text-rose-700";
}

function offlineStatusLabel(status: string) {
  if (status === "good") return "达标";
  if (status === "watch") return "观察";
  return "偏弱";
}

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
        className="font-medium text-sky-700 underline decoration-sky-200 underline-offset-4 hover:text-sky-800"
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

function parseMarkdownBlocks(content: string): MarkdownBlock[] {
  const lines = String(content || "").replace(/\r/g, "").split("\n");
  const blocks: MarkdownBlock[] = [];
  let index = 0;

  while (index < lines.length) {
    const rawLine = lines[index] || "";
    const trimmed = rawLine.trim();

    if (!trimmed) {
      index += 1;
      continue;
    }

    if (trimmed.startsWith("```")) {
      const codeLines: string[] = [];
      index += 1;
      while (index < lines.length && !String(lines[index] || "").trim().startsWith("```")) {
        codeLines.push(lines[index] || "");
        index += 1;
      }
      if (index < lines.length) {
        index += 1;
      }
      blocks.push({ type: "code", text: codeLines.join("\n") });
      continue;
    }

    const h3Match = trimmed.match(/^###\s+(.+)$/);
    if (h3Match) {
      blocks.push({ type: "h3", text: h3Match[1] });
      index += 1;
      continue;
    }

    const h2Match = trimmed.match(/^##\s+(.+)$/);
    if (h2Match) {
      blocks.push({ type: "h2", text: h2Match[1] });
      index += 1;
      continue;
    }

    const h1Match = trimmed.match(/^#\s+(.+)$/);
    if (h1Match) {
      blocks.push({ type: "h1", text: h1Match[1] });
      index += 1;
      continue;
    }

    const bulletMatch = rawLine.match(/^(\s*)-\s+(.+)$/);
    if (bulletMatch) {
      const items: Array<{ text: string; indent: number }> = [];
      while (index < lines.length) {
        const currentLine = lines[index] || "";
        const currentMatch = currentLine.match(/^(\s*)-\s+(.+)$/);
        if (!currentMatch) break;
        items.push({
          text: currentMatch[2],
          indent: Math.floor((currentMatch[1] || "").length / 2),
        });
        index += 1;
      }
      blocks.push({ type: "ul", items });
      continue;
    }

    const orderedMatch = rawLine.match(/^(\s*)\d+\.\s+(.+)$/);
    if (orderedMatch) {
      const items: Array<{ text: string; indent: number }> = [];
      while (index < lines.length) {
        const currentLine = lines[index] || "";
        const currentMatch = currentLine.match(/^(\s*)\d+\.\s+(.+)$/);
        if (!currentMatch) break;
        items.push({
          text: currentMatch[2],
          indent: Math.floor((currentMatch[1] || "").length / 2),
        });
        index += 1;
      }
      blocks.push({ type: "ol", items });
      continue;
    }

    const paragraphLines: string[] = [];
    while (index < lines.length) {
      const currentLine = lines[index] || "";
      const currentTrimmed = currentLine.trim();
      if (
        !currentTrimmed ||
        currentTrimmed.startsWith("```") ||
        /^#{1,3}\s+/.test(currentTrimmed) ||
        /^\s*-\s+/.test(currentLine) ||
        /^\s*\d+\.\s+/.test(currentLine)
      ) {
        break;
      }
      paragraphLines.push(currentTrimmed);
      index += 1;
    }
    blocks.push({ type: "p", text: paragraphLines.join(" ") });
  }

  return blocks;
}

function normalizeDiffText(text: string) {
  return String(text || "")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1")
    .replace(/[`*_>#]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function shortenText(text: string, maxLength = 120) {
  const value = String(text || "").trim();
  if (value.length <= maxLength) return value;
  return `${value.slice(0, maxLength - 1).trimEnd()}...`;
}

function dedupeItems(items: string[]) {
  const seen = new Set<string>();
  const output: string[] = [];
  items.forEach((item) => {
    const normalized = normalizeDiffText(item);
    if (!normalized || seen.has(normalized)) return;
    seen.add(normalized);
    output.push(item.trim());
  });
  return output;
}

function blockToLines(block: MarkdownBlock): string[] {
  if (block.type === "p") {
    return block.text ? [block.text] : [];
  }
  if (block.type === "ul" || block.type === "ol") {
    return block.items.map((item) => item.text).filter(Boolean);
  }
  if (block.type === "code") {
    const codeLine = block.text
      .split("\n")
      .map((line) => line.trim())
      .find(Boolean);
    return codeLine ? [`Code: ${codeLine}`] : [];
  }
  return [];
}

function buildArchiveSections(content: string): ArchiveSection[] {
  const blocks = parseMarkdownBlocks(content);
  const sections: ArchiveSection[] = [];
  const introItems: string[] = [];
  let currentSection: ArchiveSection | null = null;

  blocks.forEach((block, index) => {
    if (block.type === "h1" || block.type === "h2" || block.type === "h3") {
      currentSection = {
        key: normalizeDiffText(block.text) || `section-${index}`,
        title: block.text,
        level: block.type === "h1" ? 1 : block.type === "h2" ? 2 : 3,
        items: [],
      };
      sections.push(currentSection);
      return;
    }

    const lines = blockToLines(block);
    if (!lines.length) return;
    if (currentSection) {
      currentSection.items.push(...lines);
      return;
    }
    introItems.push(...lines);
  });

  if (introItems.length) {
    sections.unshift({
      key: "document-opening",
      title: "Document Opening",
      level: 1,
      items: introItems,
    });
  }

  return sections
    .map((section) => ({
      ...section,
      items: dedupeItems(section.items),
    }))
    .filter((section) => section.title || section.items.length > 0);
}

function buildArchiveComparison(currentContent: string, compareContent: string): ArchiveComparison {
  const currentSections = buildArchiveSections(currentContent);
  const compareSections = buildArchiveSections(compareContent);
  const compareMap = new Map(compareSections.map((section) => [section.key, section]));
  const currentMap = new Map(currentSections.map((section) => [section.key, section]));

  const sharedSectionCount = currentSections.filter((section) => compareMap.has(section.key)).length;
  const addedSections = currentSections.filter((section) => !compareMap.has(section.key));
  const removedSections = compareSections.filter((section) => !currentMap.has(section.key));
  const changedSections = currentSections
    .filter((section) => compareMap.has(section.key))
    .map<ArchiveSectionDiff | null>((section) => {
      const compareSection = compareMap.get(section.key);
      if (!compareSection) return null;

      const currentItems = dedupeItems(section.items);
      const compareItems = dedupeItems(compareSection.items);
      const compareItemMap = new Map(compareItems.map((item) => [normalizeDiffText(item), item]));
      const currentItemMap = new Map(currentItems.map((item) => [normalizeDiffText(item), item]));

      const currentOnly = currentItems.filter((item) => !compareItemMap.has(normalizeDiffText(item)));
      const compareOnly = compareItems.filter((item) => !currentItemMap.has(normalizeDiffText(item)));
      const sharedCount = currentItems.filter((item) => compareItemMap.has(normalizeDiffText(item))).length;

      if (currentOnly.length === 0 && compareOnly.length === 0) return null;
      return {
        key: section.key,
        title: section.title,
        level: section.level,
        currentOnly,
        compareOnly,
        sharedCount,
      };
    })
    .filter((section): section is ArchiveSectionDiff => Boolean(section))
    .sort(
      (left, right) =>
        right.currentOnly.length + right.compareOnly.length - (left.currentOnly.length + left.compareOnly.length),
    );

  return {
    currentSectionCount: currentSections.length,
    compareSectionCount: compareSections.length,
    sharedSectionCount,
    addedSections,
    removedSections,
    changedSections,
  };
}

function MarkdownPreview({ content }: { content: string }) {
  const blocks = parseMarkdownBlocks(content);
  return (
    <div className="space-y-4">
      {blocks.map((block, index) => {
        if (block.type === "h1") {
          return (
            <h1 key={`block-${index}`} className="text-2xl font-semibold tracking-[-0.04em] text-slate-900">
              {block.text}
            </h1>
          );
        }
        if (block.type === "h2") {
          return (
            <h2 key={`block-${index}`} className="pt-2 text-xl font-semibold text-slate-900">
              {block.text}
            </h2>
          );
        }
        if (block.type === "h3") {
          return (
            <h3 key={`block-${index}`} className="pt-1 text-base font-semibold text-slate-800">
              {block.text}
            </h3>
          );
        }
        if (block.type === "code") {
          return (
            <pre
              key={`block-${index}`}
              className="overflow-auto rounded-[20px] border border-slate-200 bg-slate-950 px-4 py-4 text-xs leading-6 text-slate-100"
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
              className={`space-y-2 text-sm leading-7 text-slate-700 ${block.type === "ol" ? "list-decimal pl-5" : "list-none"}`}
            >
              {block.items.map((item, itemIndex) => (
                <li
                  key={`block-${index}-item-${itemIndex}`}
                  className={block.type === "ul" ? "flex gap-2" : ""}
                  style={item.indent > 0 ? { marginLeft: `${item.indent * 18}px` } : undefined}
                >
                  {block.type === "ul" ? <span className="mt-[11px] h-1.5 w-1.5 rounded-full bg-sky-300" /> : null}
                  <span>{renderInlineMarkdown(item.text, `block-${index}-item-${itemIndex}`)}</span>
                </li>
              ))}
            </ListTag>
          );
        }
        if (block.type === "p") {
          return (
            <p key={`block-${index}`} className="text-sm leading-7 text-slate-700">
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
      <span className="rounded-full bg-white/75 px-2.5 py-1 text-slate-600">
        文件 · {archive.filename}
      </span>
      <span className="rounded-full bg-white/75 px-2.5 py-1 text-slate-600">
        大小 · {Math.max(1, Math.round(archive.content_length / 1024))} KB
      </span>
      <span className="rounded-full bg-white/75 px-2.5 py-1 text-slate-600">
        更新 · {new Date(archive.updated_at).toLocaleString()}
      </span>
      {archive.query ? (
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">
          关键词 · {archive.query}
        </span>
      ) : null}
      {archive.tracking_topic_name ? (
        <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
          专题 · {archive.tracking_topic_name}
        </span>
      ) : null}
      {archive.report_version_title ? (
        <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-700">
          版本 · {archive.report_version_title}
        </span>
      ) : null}
      {archive.compare_snapshot_name ? (
        <span className="rounded-full bg-cyan-50 px-2.5 py-1 text-cyan-700">
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
    <article className="rounded-[24px] border border-white/70 bg-white/85 p-5">
      <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-slate-400">
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
        <ul className="mt-4 space-y-2 text-sm leading-6 text-slate-600">
          {digest.notes.map((note) => (
            <li key={`${title || digest.title}-${note}`} className="flex gap-2">
              <span className="mt-[10px] h-1.5 w-1.5 rounded-full bg-sky-300" />
              <span>{note}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {digest.outstandingItems.length ? (
        <p className="mt-4 text-sm leading-6 text-rose-600">
          {digest.outstandingLabel} · {digest.outstandingItems.slice(0, 5).join(" / ")}
        </p>
      ) : null}
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
    <article className="rounded-[24px] border border-white/70 bg-white/80 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-2.5 py-1 text-[11px] ${archiveKindTone(archive.archive_kind)}`}>
          {archiveKindLabel(archive.archive_kind)}
        </span>
        {archive.tracking_topic_name ? (
          <span className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] text-sky-700">
            {archive.tracking_topic_name}
          </span>
        ) : null}
      </div>
      <h3 className="mt-3 text-sm font-semibold text-slate-900">{archive.name}</h3>
      <p className="mt-2 text-xs leading-6 text-slate-500">
        {archive.summary || archive.preview_text || "归档已保存，可作为当前文档的对照基线。"}
      </p>
      <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-500">
        <span className="rounded-full bg-slate-100 px-2 py-1">
          {new Date(archive.updated_at).toLocaleDateString()}
        </span>
        {archive.report_version_title ? (
          <span className="rounded-full bg-amber-50 px-2 py-1 text-amber-700">
            {archive.report_version_title}
          </span>
        ) : null}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Link
          href={buildMarkdownArchiveHref(baseArchiveId, archive.id)}
          className={`af-btn border px-3 py-1.5 text-xs ${isActive ? "border-sky-200 bg-sky-50 text-sky-700" : "af-btn-secondary"}`}
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
        highlightAnchor ? "border border-sky-200 bg-sky-50/65 shadow-[0_0_0_4px_rgba(125,211,252,0.25)]" : ""
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="af-kicker">Archive Compare</p>
          <h3 className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-slate-900">
            当前归档 vs 对照归档
          </h3>
          <p className="mt-2 text-sm leading-6 text-slate-500">
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
        <div className="mt-5 rounded-[24px] border border-white/70 bg-white/85 p-5">
          <p className="text-xs font-medium uppercase tracking-[0.22em] text-slate-500">Diff Summary</p>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
            {summaryLines.map((line, index) => (
              <li key={`summary-line-${index}`} className="flex gap-2">
                <span className="mt-[10px] h-1.5 w-1.5 rounded-full bg-sky-300" />
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
                        ? "border-sky-200 bg-sky-50 text-sky-700"
                        : "border-white/70 bg-white/85 text-slate-500 hover:border-sky-100 hover:text-sky-700"
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
        <div className="rounded-[22px] border border-white/70 bg-white/85 p-4">
          <p className="text-[11px] uppercase tracking-[0.24em] text-slate-400">Shared Sections</p>
          <p className="mt-2 text-2xl font-semibold text-slate-900">{comparison.sharedSectionCount}</p>
        </div>
        <div className="rounded-[22px] border border-emerald-100 bg-emerald-50/80 p-4">
          <p className="text-[11px] uppercase tracking-[0.24em] text-emerald-500">Current Added</p>
          <p className="mt-2 text-2xl font-semibold text-emerald-700">{comparison.addedSections.length}</p>
        </div>
        <div className="rounded-[22px] border border-rose-100 bg-rose-50/80 p-4">
          <p className="text-[11px] uppercase tracking-[0.24em] text-rose-500">Baseline Only</p>
          <p className="mt-2 text-2xl font-semibold text-rose-700">{comparison.removedSections.length}</p>
        </div>
        <div className="rounded-[22px] border border-amber-100 bg-amber-50/80 p-4">
          <p className="text-[11px] uppercase tracking-[0.24em] text-amber-500">Changed Sections</p>
          <p className="mt-2 text-2xl font-semibold text-amber-700">{comparison.changedSections.length}</p>
        </div>
        <div className="rounded-[22px] border border-slate-200 bg-slate-50/90 p-4">
          <p className="text-[11px] uppercase tracking-[0.24em] text-slate-400">Coverage</p>
          <p className="mt-2 text-2xl font-semibold text-slate-900">
            {comparison.currentSectionCount}/{comparison.compareSectionCount}
          </p>
        </div>
      </div>

      {(currentSectionSummary || compareSectionSummary || currentOfflineSnapshot || compareOfflineSnapshot) ? (
        <div className="mt-5 grid gap-4 xl:grid-cols-2">
          <article className="rounded-[24px] border border-white/70 bg-white/85 p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-slate-400">Section Diagnostics</p>
                <h4 className="mt-2 text-base font-semibold text-slate-900">章节风险对照</h4>
              </div>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <div className="rounded-[20px] border border-sky-100 bg-sky-50/70 p-4">
                <p className="text-[11px] uppercase tracking-[0.16em] text-sky-600">当前归档</p>
                <p className="mt-2 text-sm leading-6 text-slate-700">
                  待补证 {currentSectionSummary?.mode === "compare" ? currentSectionSummary.weakSectionCount : currentSectionSummary?.currentWeakSectionCount || 0}
                  {" / "}配额风险 {currentSectionSummary?.quotaRiskSectionCount || 0}
                  {" / "}矛盾 {currentSectionSummary?.contradictionSectionCount || 0}
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  重点章节 · {currentSectionSummary?.highlightedSections?.length ? currentSectionSummary.highlightedSections.slice(0, 4).join(" / ") : "无"}
                </p>
              </div>
              <div className="rounded-[20px] border border-amber-100 bg-amber-50/70 p-4">
                <p className="text-[11px] uppercase tracking-[0.16em] text-amber-600">对照归档</p>
                <p className="mt-2 text-sm leading-6 text-slate-700">
                  待补证 {compareSectionSummary?.mode === "compare" ? compareSectionSummary.weakSectionCount : compareSectionSummary?.currentWeakSectionCount || 0}
                  {" / "}配额风险 {compareSectionSummary?.quotaRiskSectionCount || 0}
                  {" / "}矛盾 {compareSectionSummary?.contradictionSectionCount || 0}
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  重点章节 · {compareSectionSummary?.highlightedSections?.length ? compareSectionSummary.highlightedSections.slice(0, 4).join(" / ") : "无"}
                </p>
              </div>
            </div>
          </article>

          <article className="rounded-[24px] border border-white/70 bg-white/85 p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-slate-400">Offline Regression</p>
                <h4 className="mt-2 text-base font-semibold text-slate-900">离线回归快照对照</h4>
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
                  className={`rounded-[20px] border p-4 ${item.tone === "sky" ? "border-sky-100 bg-sky-50/70" : "border-amber-100 bg-amber-50/70"}`}
                >
                  <p className={`text-[11px] uppercase tracking-[0.16em] ${item.tone === "sky" ? "text-sky-600" : "text-amber-600"}`}>
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
                        <p className="mt-3 text-sm leading-6 text-slate-600">
                          {item.value.summaryLines[0]}
                        </p>
                      ) : null}
                    </>
                  ) : (
                    <p className="mt-3 text-sm text-slate-500">没有可用回归快照。</p>
                  )}
                </div>
              ))}
            </div>
          </article>
        </div>
      ) : null}

      <div className="mt-5 grid gap-4 xl:grid-cols-[1.25fr_0.75fr]">
        <div className="rounded-[24px] border border-white/70 bg-white/85 p-5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] text-sky-700">当前</span>
            <p className="text-sm font-semibold text-slate-900">{archive.name}</p>
          </div>
          <ArchiveMetaChips archive={archive} />
          {comparison.addedSections.length ? (
            <div className="mt-4">
              <p className="text-xs font-medium uppercase tracking-[0.22em] text-emerald-500">新增 Section</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {comparison.addedSections.slice(0, 5).map((section) => (
                  <span key={`current-added-${section.key}`} className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs text-emerald-700">
                    {section.title}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <div className="rounded-[24px] border border-white/70 bg-white/85 p-5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-amber-50 px-2.5 py-1 text-[11px] text-amber-700">对照</span>
            <p className="text-sm font-semibold text-slate-900">{compareArchive.name}</p>
          </div>
          <ArchiveMetaChips archive={compareArchive} />
          {comparison.removedSections.length ? (
            <div className="mt-4">
              <p className="text-xs font-medium uppercase tracking-[0.22em] text-rose-500">仅对照中存在</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {comparison.removedSections.slice(0, 5).map((section) => (
                  <span key={`compare-removed-${section.key}`} className="rounded-full bg-rose-50 px-2.5 py-1 text-xs text-rose-700">
                    {section.title}
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
                  ? "border-sky-200 bg-sky-50/70 shadow-[0_0_0_4px_rgba(125,211,252,0.22)]"
                  : "border-white/70 bg-white/80"
              }`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-500">
                  H{section.level}
                </span>
                <h4 className="text-sm font-semibold text-slate-900">{section.title}</h4>
                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-500">
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
                <div className="rounded-[20px] border border-emerald-100 bg-emerald-50/70 p-4">
                  <p className="text-xs font-medium uppercase tracking-[0.22em] text-emerald-600">当前新增</p>
                  {section.currentOnly.length ? (
                    <ul className="mt-3 space-y-2 text-sm leading-6 text-emerald-900">
                      {section.currentOnly.slice(0, 4).map((item, index) => (
                        <li key={`${section.key}-current-${index}`} className="flex gap-2">
                          <span className="mt-[10px] h-1.5 w-1.5 rounded-full bg-emerald-400" />
                          <span>{shortenText(item, 160)}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-3 text-sm text-emerald-800">没有额外新增要点。</p>
                  )}
                </div>
                <div className="rounded-[20px] border border-rose-100 bg-rose-50/70 p-4">
                  <p className="text-xs font-medium uppercase tracking-[0.22em] text-rose-600">对照独有</p>
                  {section.compareOnly.length ? (
                    <ul className="mt-3 space-y-2 text-sm leading-6 text-rose-900">
                      {section.compareOnly.slice(0, 4).map((item, index) => (
                        <li key={`${section.key}-compare-${index}`} className="flex gap-2">
                          <span className="mt-[10px] h-1.5 w-1.5 rounded-full bg-rose-400" />
                          <span>{shortenText(item, 160)}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-3 text-sm text-rose-800">该 section 在当前版本里已完全覆盖。</p>
                  )}
                </div>
              </div>
            </article>
          );
          })
        ) : (
          <div className="rounded-[24px] border border-emerald-100 bg-emerald-50/80 p-5 text-sm text-emerald-800">
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
                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-600">
                  对照中
                </span>
              ) : null}
            </div>
            <h2 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-slate-900">{archive.name}</h2>
            <p className="mt-3 text-sm leading-6 text-slate-600">
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
        {message ? <p className="mt-3 text-sm text-slate-500">{message}</p> : null}
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
            <p className="mt-2 text-sm text-slate-500">
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
          <div className="mt-5 rounded-[24px] border border-white/70 bg-white/80 p-5 text-sm text-slate-500">
            当前还没有足够接近的历史归档可供对照。先从 compare 导出或专题复盘报告继续沉淀版本。
          </div>
        )}
      </section>

      <section className="af-glass rounded-[30px] p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="af-kicker">{compareArchive ? "Side-by-Side Preview" : "Archive Preview"}</p>
            <p className="mt-2 text-sm text-slate-500">
              {compareArchive
                ? "左右并排查看当前归档和对照归档的正文结构，适合做快速复盘。"
                : "当前为应用内轻量预览，保留标题、列表和链接结构，适合快速复盘。"}
            </p>
          </div>
        </div>
        {compareArchive ? (
          <div className="mt-5 grid gap-4 xl:grid-cols-2">
            <div className="rounded-[24px] border border-white/70 bg-white/80 p-5">
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] text-sky-700">当前归档</span>
                <p className="text-sm font-semibold text-slate-900">{archive.name}</p>
              </div>
              <MarkdownPreview content={archive.content} />
            </div>
            <div className="rounded-[24px] border border-white/70 bg-white/80 p-5">
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-amber-50 px-2.5 py-1 text-[11px] text-amber-700">对照归档</span>
                <p className="text-sm font-semibold text-slate-900">{compareArchive.name}</p>
              </div>
              <MarkdownPreview content={compareArchive.content} />
            </div>
          </div>
        ) : (
          <div className="mt-5 rounded-[24px] border border-white/70 bg-white/80 p-5">
            <MarkdownPreview content={archive.content} />
          </div>
        )}
      </section>

      <section className="af-glass rounded-[30px] p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="af-kicker">Raw Markdown</p>
            <p className="mt-2 text-sm text-slate-500">
              保留原始内容，方便复制到外部文档或继续交给别的系统处理。
            </p>
          </div>
        </div>
        <pre className="mt-5 overflow-auto rounded-[24px] border border-slate-200 bg-slate-950 px-5 py-5 text-xs leading-6 text-slate-100">
          {archive.content}
        </pre>
      </section>
    </div>
  );
}
