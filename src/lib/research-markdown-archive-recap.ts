import type { ApiResearchMarkdownArchive, ApiResearchMarkdownArchiveDetail } from "@/lib/api";
import { sanitizeExternalDisplayText } from "@/lib/commercial-risk-copy";
import { buildArchiveEvidenceDeltaLines, buildArchiveDeliveryDigest } from "@/lib/research-archive-metadata";

export const RESEARCH_MARKDOWN_ARCHIVE_COMPARE_SUMMARY_ANCHOR = "archive-compare-summary";

type ResearchMarkdownArchiveSection = {
  key: string;
  title: string;
  level: 1 | 2 | 3;
  items: string[];
};

type ResearchMarkdownArchiveSectionDiff = {
  key: string;
  title: string;
  level: 1 | 2 | 3;
  currentOnly: string[];
  compareOnly: string[];
  sharedCount: number;
};

export type ResearchMarkdownArchiveComparison = {
  currentSectionCount: number;
  compareSectionCount: number;
  sharedSectionCount: number;
  addedSections: ResearchMarkdownArchiveSection[];
  removedSections: ResearchMarkdownArchiveSection[];
  changedSections: ResearchMarkdownArchiveSectionDiff[];
};

export type ResearchMarkdownArchiveCompareSectionLink = {
  title: string;
  label: string;
  href: string;
  anchorId: string;
};

export interface ResearchMarkdownArchiveRecapMarkdownOptions {
  archive: ApiResearchMarkdownArchiveDetail;
  compareArchive: ApiResearchMarkdownArchiveDetail;
  comparison: ResearchMarkdownArchiveComparison;
  generatedAt?: Date;
  appCompareUrl?: string;
}

function normalizeText(value: unknown): string {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function stableAnchorSuffix(value: string): string {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) % 2147483647;
  }
  return Math.abs(hash).toString(36);
}

export function buildResearchMarkdownArchiveCompareSectionAnchor(sectionKey: string): string {
  const normalized = normalizeText(sectionKey).toLowerCase();
  const slug = normalized
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 28);
  const suffix = stableAnchorSuffix(normalized || "section");
  return `archive-compare-section-${slug || "section"}-${suffix}`;
}

export function buildResearchMarkdownArchiveCompareHref(
  currentArchiveId?: string | null,
  compareArchiveId?: string | null,
  anchorId?: string | null,
): string {
  if (!currentArchiveId || !compareArchiveId) return "";
  const basePath = `/research/archives/${encodeURIComponent(currentArchiveId)}?compare=${encodeURIComponent(compareArchiveId)}`;
  if (!anchorId) return basePath;
  return `${basePath}#${String(anchorId).replace(/^#/, "")}`;
}

function sanitizeFilenamePart(value: string): string {
  return normalizeText(value)
    .replace(/[\\/:*?"<>|]+/g, "-")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 24);
}

function formatDateStamp(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatDateTimeStamp(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  const hours = String(value.getHours()).padStart(2, "0");
  const minutes = String(value.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day} ${hours}:${minutes}`;
}

function formatDateTime(value: string | Date | null | undefined): string {
  if (!value) return "—";
  const parsed = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return normalizeText(value);
  }
  return formatDateTimeStamp(parsed);
}

function archiveKindLabel(kind: ApiResearchMarkdownArchive["archive_kind"]) {
  if (kind === "topic_version_recap") return "专题版本复盘";
  if (kind === "archive_diff_recap") return "归档差异复盘";
  return "Compare 导出";
}

function trimText(value: string, limit = 120): string {
  const normalized = normalizeText(value);
  if (normalized.length <= limit) return normalized;
  return `${normalized.slice(0, Math.max(0, limit - 1)).trim()}…`;
}

function uniqueTake(values: string[], limit = 4): string[] {
  const next: string[] = [];
  const seen = new Set<string>();
  values.forEach((value) => {
    const normalized = normalizeText(value);
    if (!normalized || seen.has(normalized)) return;
    seen.add(normalized);
    next.push(normalized);
  });
  return next.slice(0, limit);
}

function formatInlineList(values: string[], fallback = "无", limit = 4): string {
  const next = uniqueTake(values, limit);
  return next.length ? next.join("；") : fallback;
}

function formatArchiveSummary(archive: ApiResearchMarkdownArchiveDetail): string {
  const segments = [
    archive.name,
    archiveKindLabel(archive.archive_kind),
    formatDateTime(archive.updated_at),
    archive.tracking_topic_name ? `专题 ${archive.tracking_topic_name}` : "",
    archive.report_version_title ? `版本 ${archive.report_version_title}` : "",
    archive.compare_snapshot_name ? `快照 ${archive.compare_snapshot_name}` : "",
  ].filter(Boolean);
  return segments.join("｜");
}

function buildMarkdownLink(label: string, href: string): string {
  return `[${label}](${href})`;
}

function normalizeSectionLinkTitle(label: string): string {
  return normalizeText(label).replace(/[（(]H\d[\s\S]*$/, "").trim();
}

export function extractResearchMarkdownArchiveCompareSectionLinks(
  content: string,
  fallbackCurrentArchiveId?: string | null,
  fallbackCompareArchiveId?: string | null,
): ResearchMarkdownArchiveCompareSectionLink[] {
  const lines = String(content || "").replace(/\r/g, "").split("\n");
  const startIndex = lines.findIndex((line) => normalizeText(line) === "## Section 深链接索引");
  if (startIndex < 0) return [];

  const items: ResearchMarkdownArchiveCompareSectionLink[] = [];
  for (let index = startIndex + 1; index < lines.length; index += 1) {
    const trimmed = String(lines[index] || "").trim();
    if (!trimmed) {
      if (items.length) break;
      continue;
    }
    if (/^##\s+/.test(trimmed)) break;
    const match = trimmed.match(/^- (?:\[([^\]]+)\]\(([^)]+)\)|(.+))$/);
    if (!match) continue;

    const label = normalizeText(match[1] || match[3] || "");
    if (!label) continue;
    const title = normalizeSectionLinkTitle(label) || label;
    const anchorId = buildResearchMarkdownArchiveCompareSectionAnchor(title);
    const href =
      normalizeText(match[2] || "") ||
      buildResearchMarkdownArchiveCompareHref(fallbackCurrentArchiveId, fallbackCompareArchiveId, anchorId);
    items.push({
      title,
      label,
      href,
      anchorId,
    });
  }
  return items.filter((item, index, current) => current.findIndex((candidate) => candidate.href === item.href) === index);
}

export function buildResearchMarkdownArchiveCompareSummaryLines(
  archive: ApiResearchMarkdownArchiveDetail,
  compareArchive: ApiResearchMarkdownArchiveDetail,
  comparison: ResearchMarkdownArchiveComparison,
): string[] {
  if (
    comparison.addedSections.length === 0 &&
    comparison.removedSections.length === 0 &&
    comparison.changedSections.length === 0
  ) {
    return [
      `${archive.name} 与 ${compareArchive.name} 的结构和主要要点基本一致。`,
      `共 ${comparison.sharedSectionCount} 个共享 section，没有检测到显著新增或删减。`,
    ];
  }

  const lines: string[] = [];
  if (comparison.addedSections.length) {
    lines.push(
      `当前归档新增 ${comparison.addedSections.length} 个 section，重点包括 ${formatInlineList(
        comparison.addedSections.map((section) => section.title),
        "无",
        3,
      )}。`,
    );
  }
  if (comparison.removedSections.length) {
    lines.push(
      `对照归档独有 ${comparison.removedSections.length} 个 section，主要是 ${formatInlineList(
        comparison.removedSections.map((section) => section.title),
        "无",
        3,
      )}。`,
    );
  }
  if (comparison.changedSections.length) {
    lines.push(
      `${comparison.sharedSectionCount} 个共享 section 中，有 ${comparison.changedSections.length} 个 section 的要点发生变化，变化最明显的是 ${formatInlineList(
        comparison.changedSections.map((section) => section.title),
        "无",
        3,
      )}。`,
    );
  } else if (comparison.sharedSectionCount) {
    lines.push(`共享的 ${comparison.sharedSectionCount} 个 section 基本稳定，变化主要体现在结构增删上。`);
  }
  lines.push(
    `当前归档为 ${archiveKindLabel(archive.archive_kind)}，对照归档为 ${archiveKindLabel(compareArchive.archive_kind)}。`,
  );
  buildArchiveEvidenceDeltaLines(archive, compareArchive).forEach((line) => {
    lines.push(line);
  });
  return lines.slice(0, 6);
}

export function buildResearchMarkdownArchiveCompareExportFilename(
  archiveName: string,
  compareArchiveName: string,
  generatedAt: Date = new Date(),
): string {
  return `${buildResearchMarkdownArchiveCompareFilenameBase("research-archive-diff", archiveName, compareArchiveName, generatedAt)}.md`;
}

export function buildResearchMarkdownArchiveComparePdfFilename(
  archiveName: string,
  compareArchiveName: string,
  generatedAt: Date = new Date(),
): string {
  return `${buildResearchMarkdownArchiveCompareFilenameBase("research-archive-diff", archiveName, compareArchiveName, generatedAt)}.pdf`;
}

export function buildResearchMarkdownArchiveCompareExecBriefFilename(
  archiveName: string,
  compareArchiveName: string,
  generatedAt: Date = new Date(),
): string {
  return `${buildResearchMarkdownArchiveCompareFilenameBase("research-archive-diff-exec", archiveName, compareArchiveName, generatedAt)}.md`;
}

function buildResearchMarkdownArchiveCompareFilenameBase(
  prefix: string,
  archiveName: string,
  compareArchiveName: string,
  generatedAt: Date = new Date(),
): string {
  const segments = [
    prefix,
    sanitizeFilenamePart(archiveName),
    "vs",
    sanitizeFilenamePart(compareArchiveName),
    formatDateStamp(generatedAt),
  ].filter(Boolean);
  return segments.join("-");
}

export function buildResearchMarkdownArchiveCompareMarkdown(
  options: ResearchMarkdownArchiveRecapMarkdownOptions,
): string {
  const generatedAt = options.generatedAt instanceof Date ? options.generatedAt : new Date();
  const { archive, compareArchive, comparison } = options;
  const appCompareUrl = normalizeText(options.appCompareUrl);
  const summaryLines = buildResearchMarkdownArchiveCompareSummaryLines(archive, compareArchive, comparison);
  const lines = [
    "# 历史归档差异复盘报告",
    "",
    `- 导出时间: ${formatDateTimeStamp(generatedAt)}`,
    `- 当前归档: ${formatArchiveSummary(archive)}`,
    `- 对照归档: ${formatArchiveSummary(compareArchive)}`,
    `- 共享 Section: ${comparison.sharedSectionCount}`,
    `- 当前新增 Section: ${comparison.addedSections.length}`,
    `- 对照独有 Section: ${comparison.removedSections.length}`,
    `- 变更 Section: ${comparison.changedSections.length}`,
  ];

  lines.push("", "## 差异结论", "");
  summaryLines.forEach((line) => {
    lines.push(`- ${line}`);
  });

  if (comparison.changedSections.length) {
    lines.push("", "## Section 深链接索引", "");
    comparison.changedSections.slice(0, 10).forEach((section) => {
      const label = `${section.title}（H${section.level}｜重合 ${section.sharedCount}｜当前新增 ${section.currentOnly.length}｜对照独有 ${section.compareOnly.length}）`;
      if (appCompareUrl) {
        const href = `${appCompareUrl.replace(/#.*$/, "")}#${buildResearchMarkdownArchiveCompareSectionAnchor(section.key)}`;
        lines.push(`- ${buildMarkdownLink(label, href)}`);
        return;
      }
      lines.push(`- ${label}`);
    });
  }

  const currentDigest = buildArchiveDeliveryDigest(archive);
  const compareDigest = buildArchiveDeliveryDigest(compareArchive);
  const evidenceDeltaLines = buildArchiveEvidenceDeltaLines(archive, compareArchive);
  if (currentDigest || compareDigest || evidenceDeltaLines.length) {
    lines.push("", "## Evidence Appendix Delta", "");
    evidenceDeltaLines.forEach((line) => {
      lines.push(`- ${line}`);
    });
    if (currentDigest) {
      lines.push("");
      lines.push("### 当前归档证据", "");
      currentDigest.metrics.forEach((metric) => {
        lines.push(`- ${metric.label}: ${metric.value}`);
      });
      currentDigest.notes.forEach((note) => {
        lines.push(`- ${note}`);
      });
      if (currentDigest.outstandingItems.length) {
        lines.push(`- ${currentDigest.outstandingLabel}: ${formatInlineList(currentDigest.outstandingItems, "无", 5)}`);
      }
    }
    if (compareDigest) {
      lines.push("");
      lines.push("### 对照归档证据", "");
      compareDigest.metrics.forEach((metric) => {
        lines.push(`- ${metric.label}: ${metric.value}`);
      });
      compareDigest.notes.forEach((note) => {
        lines.push(`- ${note}`);
      });
      if (compareDigest.outstandingItems.length) {
        lines.push(`- ${compareDigest.outstandingLabel}: ${formatInlineList(compareDigest.outstandingItems, "无", 5)}`);
      }
    }
  }

  if (comparison.addedSections.length) {
    lines.push("", "## 当前归档新增 Section", "");
    comparison.addedSections.slice(0, 8).forEach((section) => {
      lines.push(`### ${section.title}`);
      lines.push("");
      lines.push(`- 层级: H${section.level}`);
      lines.push(`- 关键要点: ${formatInlineList(section.items, "无明显新增要点", 5)}`);
      lines.push("");
    });
  }

  if (comparison.removedSections.length) {
    lines.push("", "## 对照归档独有 Section", "");
    comparison.removedSections.slice(0, 8).forEach((section) => {
      lines.push(`### ${section.title}`);
      lines.push("");
      lines.push(`- 层级: H${section.level}`);
      lines.push(`- 基线要点: ${formatInlineList(section.items, "无明显独有要点", 5)}`);
      lines.push("");
    });
  }

  if (comparison.changedSections.length) {
    lines.push("", "## Section 级要点变化", "");
    comparison.changedSections.slice(0, 10).forEach((section) => {
      lines.push(`### ${section.title}`);
      lines.push("");
      lines.push(`- 层级: H${section.level}`);
      lines.push(`- 重合要点数: ${section.sharedCount}`);
      lines.push(`- 当前新增: ${formatInlineList(section.currentOnly, "无", 5)}`);
      lines.push(`- 对照独有: ${formatInlineList(section.compareOnly, "无", 5)}`);
      lines.push("");
    });
  }

  lines.push("## 归档上下文", "");
  lines.push("### 当前归档", "");
  lines.push(`- 名称: ${archive.name}`);
  lines.push(`- 类型: ${archiveKindLabel(archive.archive_kind)}`);
  lines.push(`- 摘要: ${trimText(archive.summary || archive.preview_text || "—", 180) || "—"}`);
  lines.push(`- 查询词: ${normalizeText(archive.query) || "—"}`);
  lines.push(`- 区域筛选: ${normalizeText(archive.region_filter) || "全部"}`);
  lines.push(`- 行业筛选: ${normalizeText(archive.industry_filter) || "全部"}`);
  lines.push(`- 更新时间: ${formatDateTime(archive.updated_at)}`);
  lines.push("");
  lines.push("### 对照归档", "");
  lines.push(`- 名称: ${compareArchive.name}`);
  lines.push(`- 类型: ${archiveKindLabel(compareArchive.archive_kind)}`);
  lines.push(`- 摘要: ${trimText(compareArchive.summary || compareArchive.preview_text || "—", 180) || "—"}`);
  lines.push(`- 查询词: ${normalizeText(compareArchive.query) || "—"}`);
  lines.push(`- 区域筛选: ${normalizeText(compareArchive.region_filter) || "全部"}`);
  lines.push(`- 行业筛选: ${normalizeText(compareArchive.industry_filter) || "全部"}`);
  lines.push(`- 更新时间: ${formatDateTime(compareArchive.updated_at)}`);
  lines.push("");

  return sanitizeExternalDisplayText(lines.join("\n"));
}

export function buildResearchMarkdownArchiveCompareExecBrief(
  options: ResearchMarkdownArchiveRecapMarkdownOptions,
): string {
  const generatedAt = options.generatedAt instanceof Date ? options.generatedAt : new Date();
  const { archive, compareArchive, comparison } = options;
  const summaryLines = buildResearchMarkdownArchiveCompareSummaryLines(archive, compareArchive, comparison);
  const currentDigest = buildArchiveDeliveryDigest(archive);
  const compareDigest = buildArchiveDeliveryDigest(compareArchive);
  const evidenceDeltaLines = buildArchiveEvidenceDeltaLines(archive, compareArchive);
  const lines = [
    "# Archive Diff Exec Brief",
    "",
    `- 导出时间: ${formatDateTimeStamp(generatedAt)}`,
    `- 当前归档: ${formatArchiveSummary(archive)}`,
    `- 对照归档: ${formatArchiveSummary(compareArchive)}`,
    `- 结构变化: 共享 ${comparison.sharedSectionCount} / 当前新增 ${comparison.addedSections.length} / 对照独有 ${comparison.removedSections.length} / 变更 ${comparison.changedSections.length}`,
  ];

  lines.push("", "## 管理层判断", "");
  summaryLines.forEach((line) => {
    lines.push(`- ${line}`);
  });

  if (evidenceDeltaLines.length || currentDigest || compareDigest) {
    lines.push("", "## Evidence Appendix Delta", "");
    evidenceDeltaLines.forEach((line) => {
      lines.push(`- ${line}`);
    });
    if (currentDigest) {
      lines.push(`- 当前归档信号: ${currentDigest.metrics.map((metric) => `${metric.label} ${metric.value}`).join(" / ")}`);
      if (currentDigest.outstandingItems.length) {
        lines.push(`- 当前待补证: ${formatInlineList(currentDigest.outstandingItems, "无", 4)}`);
      }
    }
    if (compareDigest) {
      lines.push(`- 对照归档信号: ${compareDigest.metrics.map((metric) => `${metric.label} ${metric.value}`).join(" / ")}`);
      if (compareDigest.outstandingItems.length) {
        lines.push(`- 对照待补证: ${formatInlineList(compareDigest.outstandingItems, "无", 4)}`);
      }
    }
  }

  lines.push("", "## 结构变化焦点", "");
  if (comparison.changedSections.length) {
    comparison.changedSections.slice(0, 4).forEach((section) => {
      lines.push(
        `- ${section.title}: 当前新增 ${formatInlineList(section.currentOnly, "无", 3)}；对照独有 ${formatInlineList(section.compareOnly, "无", 3)}`,
      );
    });
  } else if (comparison.addedSections.length || comparison.removedSections.length) {
    if (comparison.addedSections.length) {
      lines.push(`- 当前新增 section: ${formatInlineList(comparison.addedSections.map((section) => section.title), "无", 4)}`);
    }
    if (comparison.removedSections.length) {
      lines.push(`- 对照独有 section: ${formatInlineList(comparison.removedSections.map((section) => section.title), "无", 4)}`);
    }
  } else {
    lines.push("- 当前归档与对照归档的结构和主要要点基本一致。");
  }

  lines.push("", "## 后续动作", "");
  lines.push(
    `- 优先复核 ${formatInlineList(
      currentDigest?.outstandingItems || compareDigest?.outstandingItems || [],
      "暂无明显待补证对象",
      3,
    )} 这类仍缺少直接证据支撑的对象或字段。`,
  );
  if (comparison.changedSections.length) {
    lines.push(`- 重点回看 ${formatInlineList(comparison.changedSections.map((section) => section.title), "无", 3)} 的结论变化，决定是否进入正式对外版本。`);
  }
  return sanitizeExternalDisplayText(lines.join("\n"));
}

export function buildResearchMarkdownArchiveComparePlainText(
  options: ResearchMarkdownArchiveRecapMarkdownOptions,
): string {
  const generatedAt = options.generatedAt instanceof Date ? options.generatedAt : new Date();
  const { archive, compareArchive, comparison } = options;
  const summaryLines = buildResearchMarkdownArchiveCompareSummaryLines(archive, compareArchive, comparison);
  const currentDigest = buildArchiveDeliveryDigest(archive);
  const compareDigest = buildArchiveDeliveryDigest(compareArchive);
  const evidenceDeltaLines = buildArchiveEvidenceDeltaLines(archive, compareArchive);
  const lines = [
    "历史归档差异复盘报告",
    `导出时间: ${formatDateTimeStamp(generatedAt)}`,
    `当前归档: ${formatArchiveSummary(archive)}`,
    `对照归档: ${formatArchiveSummary(compareArchive)}`,
    `共享 Section: ${comparison.sharedSectionCount}`,
    `当前新增 Section: ${comparison.addedSections.length}`,
    `对照独有 Section: ${comparison.removedSections.length}`,
    `变更 Section: ${comparison.changedSections.length}`,
    "",
    "差异结论",
  ];
  summaryLines.forEach((line) => {
    lines.push(line);
  });

  if (evidenceDeltaLines.length || currentDigest || compareDigest) {
    lines.push("", "Evidence Appendix Delta");
    evidenceDeltaLines.forEach((line) => {
      lines.push(line);
    });
    if (currentDigest) {
      lines.push(`当前归档信号: ${currentDigest.metrics.map((metric) => `${metric.label} ${metric.value}`).join(" / ")}`);
      currentDigest.notes.forEach((note) => {
        lines.push(note);
      });
      if (currentDigest.outstandingItems.length) {
        lines.push(`当前待补证: ${formatInlineList(currentDigest.outstandingItems, "无", 5)}`);
      }
    }
    if (compareDigest) {
      lines.push(`对照归档信号: ${compareDigest.metrics.map((metric) => `${metric.label} ${metric.value}`).join(" / ")}`);
      compareDigest.notes.forEach((note) => {
        lines.push(note);
      });
      if (compareDigest.outstandingItems.length) {
        lines.push(`对照待补证: ${formatInlineList(compareDigest.outstandingItems, "无", 5)}`);
      }
    }
  }

  if (comparison.changedSections.length) {
    lines.push("", "Section 级要点变化");
    comparison.changedSections.slice(0, 8).forEach((section) => {
      lines.push(`${section.title}`);
      lines.push(`层级: H${section.level}`);
      lines.push(`重合要点数: ${section.sharedCount}`);
      lines.push(`当前新增: ${formatInlineList(section.currentOnly, "无", 5)}`);
      lines.push(`对照独有: ${formatInlineList(section.compareOnly, "无", 5)}`);
      lines.push("");
    });
  }

  if (comparison.addedSections.length) {
    lines.push("当前归档新增 Section");
    comparison.addedSections.slice(0, 6).forEach((section) => {
      lines.push(`${section.title}: ${formatInlineList(section.items, "无明显新增要点", 4)}`);
    });
    lines.push("");
  }
  if (comparison.removedSections.length) {
    lines.push("对照归档独有 Section");
    comparison.removedSections.slice(0, 6).forEach((section) => {
      lines.push(`${section.title}: ${formatInlineList(section.items, "无明显独有要点", 4)}`);
    });
    lines.push("");
  }
  return sanitizeExternalDisplayText(lines.join("\n"));
}
