import { describe, expect, it } from "vitest";
import {
  buildArchiveComparison,
  buildArchiveSections,
  buildMarkdownArchiveHref,
  normalizeDiffText,
  parseMarkdownBlocks,
} from "@/components/research/research-markdown-archive-model";

describe("research markdown archive model", () => {
  it("parses headings, lists, paragraphs, and code without React", () => {
    const blocks = parseMarkdownBlocks(`# 标题\n\n说明第一行\n说明第二行\n\n- 结论 A\n  - 证据 A1\n\n\`\`\`text\nraw evidence\n\`\`\``);

    expect(blocks).toEqual([
      { type: "h1", text: "标题" },
      { type: "p", text: "说明第一行 说明第二行" },
      {
        type: "ul",
        items: [
          { text: "结论 A", indent: 0 },
          { text: "证据 A1", indent: 1 },
        ],
      },
      { type: "code", text: "raw evidence" },
    ]);
  });

  it("normalizes linked markdown and deduplicates section items", () => {
    expect(normalizeDiffText("**[Evidence](https://example.com)**")).toBe("evidence");
    expect(buildArchiveSections("Opening note\n\n## Evidence\n\n- [Source](https://example.com)\n- Source")).toEqual([
      {
        key: "document-opening",
        title: "Document Opening",
        level: 1,
        items: ["Opening note"],
      },
      {
        key: "evidence",
        title: "Evidence",
        level: 2,
        items: ["[Source](https://example.com)"],
      },
    ]);
  });

  it("reports added, removed, and changed sections deterministically", () => {
    const current = "# Summary\n\n- Shared\n- New fact\n\n## Added\n\nCurrent only";
    const previous = "# Summary\n\n- Shared\n- Old fact\n\n## Removed\n\nPrevious only";
    const comparison = buildArchiveComparison(current, previous);

    expect(comparison).toMatchObject({
      currentSectionCount: 2,
      compareSectionCount: 2,
      sharedSectionCount: 1,
    });
    expect(comparison.addedSections.map((section) => section.title)).toEqual(["Added"]);
    expect(comparison.removedSections.map((section) => section.title)).toEqual(["Removed"]);
    expect(comparison.changedSections[0]).toMatchObject({
      title: "Summary",
      currentOnly: ["New fact"],
      compareOnly: ["Old fact"],
      sharedCount: 1,
    });
  });

  it("encodes archive and comparison identifiers in navigation links", () => {
    expect(buildMarkdownArchiveHref("archive/one", "compare two")).toBe(
      "/research/archives/archive%2Fone?compare=compare%20two",
    );
  });
});
