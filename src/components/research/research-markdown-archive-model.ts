import type { ApiResearchMarkdownArchive, ApiResearchMarkdownArchiveDetail } from "@/lib/api";
import { RESEARCH_MARKDOWN_ARCHIVE_COMPARE_SUMMARY_ANCHOR } from "@/lib/research-markdown-archive-recap";

export type MarkdownBlock =
  | { type: "h1" | "h2" | "h3"; text: string }
  | { type: "p"; text: string }
  | { type: "ul" | "ol"; items: Array<{ text: string; indent: number }> }
  | { type: "code"; text: string };

export type ArchiveSection = {
  key: string;
  title: string;
  level: 1 | 2 | 3;
  items: string[];
};

export type ArchiveSectionDiff = {
  key: string;
  title: string;
  level: 1 | 2 | 3;
  currentOnly: string[];
  compareOnly: string[];
  sharedCount: number;
};

export type ArchiveComparison = {
  currentSectionCount: number;
  compareSectionCount: number;
  sharedSectionCount: number;
  addedSections: ArchiveSection[];
  removedSections: ArchiveSection[];
  changedSections: ArchiveSectionDiff[];
};

export function archiveKindLabel(kind: ApiResearchMarkdownArchive["archive_kind"]) {
  if (kind === "topic_version_recap") return "版本复盘";
  if (kind === "archive_diff_recap") return "差异复盘";
  return "Compare 导出";
}

export function archiveKindTone(kind: ApiResearchMarkdownArchive["archive_kind"]) {
  if (kind === "topic_version_recap") return "af-chip af-chip-warning";
  if (kind === "archive_diff_recap") return "af-chip af-chip-success";
  return "af-chip af-chip-info";
}

export function buildCompareSnapshotHref(snapshotId: string) {
  return `/research/compare?snapshot=${encodeURIComponent(snapshotId)}`;
}

export function buildTopicWorkspaceHref(topicId: string) {
  return `/research/topics/${topicId}`;
}

export function buildMarkdownArchiveHref(archiveId: string, compareId?: string | null) {
  const basePath = `/research/archives/${encodeURIComponent(archiveId)}`;
  if (!compareId) return basePath;
  return `${basePath}?compare=${encodeURIComponent(compareId)}`;
}

export function buildOriginalArchiveCompareHref(
  currentArchiveId?: string | null,
  compareArchiveId?: string | null,
) {
  if (!currentArchiveId || !compareArchiveId) return "";
  return `${buildMarkdownArchiveHref(currentArchiveId, compareArchiveId)}#${RESEARCH_MARKDOWN_ARCHIVE_COMPARE_SUMMARY_ANCHOR}`;
}

export function buildAbsoluteArchiveCompareHref(
  currentArchiveId?: string | null,
  compareArchiveId?: string | null,
) {
  if (!currentArchiveId || typeof window === "undefined") return "";
  const href = buildMarkdownArchiveHref(currentArchiveId, compareArchiveId);
  return new URL(href, window.location.origin).toString();
}

export function archiveSourceCompareHref(archive: ApiResearchMarkdownArchiveDetail) {
  const metadata = archive.metadata_payload && typeof archive.metadata_payload === "object" ? archive.metadata_payload : {};
  const currentArchiveId = typeof metadata.current_archive_id === "string" ? metadata.current_archive_id.trim() : "";
  const compareArchiveId = typeof metadata.compare_archive_id === "string" ? metadata.compare_archive_id.trim() : "";
  return buildOriginalArchiveCompareHref(currentArchiveId, compareArchiveId);
}

export function offlineStatusTone(status: string) {
  if (status === "good") return "af-chip af-chip-success";
  if (status === "watch") return "af-chip af-chip-warning";
  return "af-chip af-chip-danger";
}

export function offlineStatusLabel(status: string) {
  if (status === "good") return "达标";
  if (status === "watch") return "观察";
  return "偏弱";
}

export function followupResolutionLabel(value: string | null | undefined) {
  return String(value || "").trim() || "无";
}

export function parseMarkdownBlocks(content: string): MarkdownBlock[] {
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
      if (index < lines.length) index += 1;
      blocks.push({ type: "code", text: codeLines.join("\n") });
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,3})\s+(.+)$/);
    if (headingMatch) {
      blocks.push({ type: `h${headingMatch[1].length}` as "h1" | "h2" | "h3", text: headingMatch[2] });
      index += 1;
      continue;
    }

    const bulletMatch = rawLine.match(/^(\s*)-\s+(.+)$/);
    if (bulletMatch) {
      const items: Array<{ text: string; indent: number }> = [];
      while (index < lines.length) {
        const currentMatch = (lines[index] || "").match(/^(\s*)-\s+(.+)$/);
        if (!currentMatch) break;
        items.push({ text: currentMatch[2], indent: Math.floor((currentMatch[1] || "").length / 2) });
        index += 1;
      }
      blocks.push({ type: "ul", items });
      continue;
    }

    const orderedMatch = rawLine.match(/^(\s*)\d+\.\s+(.+)$/);
    if (orderedMatch) {
      const items: Array<{ text: string; indent: number }> = [];
      while (index < lines.length) {
        const currentMatch = (lines[index] || "").match(/^(\s*)\d+\.\s+(.+)$/);
        if (!currentMatch) break;
        items.push({ text: currentMatch[2], indent: Math.floor((currentMatch[1] || "").length / 2) });
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

export function normalizeDiffText(text: string) {
  return String(text || "")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1")
    .replace(/[`*_>#]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

export function shortenText(text: string, maxLength = 120) {
  const value = String(text || "").trim();
  if (value.length <= maxLength) return value;
  return `${value.slice(0, maxLength - 1).trimEnd()}...`;
}

export function dedupeItems(items: string[]) {
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
  if (block.type === "p") return block.text ? [block.text] : [];
  if (block.type === "ul" || block.type === "ol") return block.items.map((item) => item.text).filter(Boolean);
  if (block.type === "code") {
    const codeLine = block.text.split("\n").map((line) => line.trim()).find(Boolean);
    return codeLine ? [`Code: ${codeLine}`] : [];
  }
  return [];
}

export function buildArchiveSections(content: string): ArchiveSection[] {
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
    if (currentSection) currentSection.items.push(...lines);
    else introItems.push(...lines);
  });

  if (introItems.length) {
    sections.unshift({ key: "document-opening", title: "Document Opening", level: 1, items: introItems });
  }

  return sections
    .map((section) => ({ ...section, items: dedupeItems(section.items) }))
    .filter((section) => section.title || section.items.length > 0);
}

export function buildArchiveComparison(currentContent: string, compareContent: string): ArchiveComparison {
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
      return { key: section.key, title: section.title, level: section.level, currentOnly, compareOnly, sharedCount };
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
