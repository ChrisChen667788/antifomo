"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { getResearchMarkdownArchive } from "@/lib/api";
import {
  buildResearchMarkdownArchiveCompareHref,
  extractResearchMarkdownArchiveCompareSectionLinks,
  type ResearchMarkdownArchiveCompareSectionLink,
  RESEARCH_MARKDOWN_ARCHIVE_COMPARE_SUMMARY_ANCHOR,
} from "@/lib/research-markdown-archive-recap";

type ResearchArchiveSectionLinkPopoverProps = {
  archiveId: string;
  fallbackCurrentArchiveId?: string | null;
  fallbackCompareArchiveId?: string | null;
  buttonLabel?: string;
  buttonClassName?: string;
  align?: "left" | "right";
  onCopyMessage?: (message: string) => void;
};

function buildAbsoluteHref(href: string) {
  if (!href || typeof window === "undefined") return href;
  return new URL(href, window.location.origin).toString();
}

function buildLinkSummary(link: ResearchMarkdownArchiveCompareSectionLink) {
  const normalizedLabel = String(link.label || "").trim();
  const normalizedTitle = String(link.title || "").trim();
  if (!normalizedLabel || normalizedLabel === normalizedTitle) return "";

  const fullWidthPrefix = `${normalizedTitle}（`;
  if (normalizedLabel.startsWith(fullWidthPrefix) && normalizedLabel.endsWith("）")) {
    return normalizedLabel.slice(fullWidthPrefix.length, -1).replace(/\s*｜\s*/g, "，");
  }

  const asciiPrefix = `${normalizedTitle}(`;
  if (normalizedLabel.startsWith(asciiPrefix) && normalizedLabel.endsWith(")")) {
    return normalizedLabel.slice(asciiPrefix.length, -1).replace(/\s*\|\s*/g, "，");
  }

  return normalizedLabel;
}

function buildBatchCopyPayload(links: ResearchMarkdownArchiveCompareSectionLink[]) {
  return links
    .map((link, index) =>
      [
        `${index + 1}. ${link.title}`,
        buildLinkSummary(link) ? `摘要: ${buildLinkSummary(link)}` : "",
        buildAbsoluteHref(link.href),
      ]
        .filter(Boolean)
        .join("\n"),
    )
    .join("\n\n");
}

function fallbackSummaryLink(
  currentArchiveId?: string | null,
  compareArchiveId?: string | null,
): ResearchMarkdownArchiveCompareSectionLink | null {
  const href = buildResearchMarkdownArchiveCompareHref(
    currentArchiveId,
    compareArchiveId,
    RESEARCH_MARKDOWN_ARCHIVE_COMPARE_SUMMARY_ANCHOR,
  );
  if (!href) return null;
  return {
    title: "差异总览",
    label: "差异总览",
    href,
    anchorId: RESEARCH_MARKDOWN_ARCHIVE_COMPARE_SUMMARY_ANCHOR,
  };
}

export function ResearchArchiveSectionLinkPopover({
  archiveId,
  fallbackCurrentArchiveId,
  fallbackCompareArchiveId,
  buttonLabel = "定位链接",
  buttonClassName = "af-btn af-btn-secondary border px-3 py-1.5 text-xs",
  align = "left",
  onCopyMessage,
}: ResearchArchiveSectionLinkPopoverProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [links, setLinks] = useState<ResearchMarkdownArchiveCompareSectionLink[] | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return undefined;
    const handlePointerDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [open]);

  const loadSectionLinks = async () => {
    setLoading(true);
    setLoadError("");
    try {
      const detail = await getResearchMarkdownArchive(archiveId);
      const metadata = detail.metadata_payload && typeof detail.metadata_payload === "object" ? detail.metadata_payload : {};
      const currentArchiveId =
        fallbackCurrentArchiveId ||
        (typeof metadata.current_archive_id === "string" ? metadata.current_archive_id.trim() : "");
      const compareArchiveId =
        fallbackCompareArchiveId ||
        (typeof metadata.compare_archive_id === "string" ? metadata.compare_archive_id.trim() : "");
      const resolvedLinks = extractResearchMarkdownArchiveCompareSectionLinks(
        detail.content,
        currentArchiveId,
        compareArchiveId,
      ).slice(0, 3);
      const summaryLink = fallbackSummaryLink(currentArchiveId, compareArchiveId);
      setLinks(resolvedLinks.length ? resolvedLinks : summaryLink ? [summaryLink] : []);
    } catch {
      setLoadError("读取变化位置失败，请稍后重试");
      setLinks([]);
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async () => {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    if (links !== null) return;
    await loadSectionLinks();
  };

  const handleCopyLink = async (link: ResearchMarkdownArchiveCompareSectionLink) => {
    try {
      await navigator.clipboard.writeText(buildAbsoluteHref(link.href));
      onCopyMessage?.(`已复制定位链接：${link.title}`);
      setOpen(false);
    } catch {
      onCopyMessage?.("复制定位链接失败，请稍后重试");
    }
  };

  const handleCopyAllLinks = async () => {
    if (!links?.length) return;
    try {
      await navigator.clipboard.writeText(buildBatchCopyPayload(links));
      onCopyMessage?.(`已复制 ${links.length} 条定位链接`);
      setOpen(false);
    } catch {
      onCopyMessage?.("复制全部定位链接失败，请稍后重试");
    }
  };

  const handleOpenAllLinks = () => {
    if (!links?.length || typeof window === "undefined") return;
    links.forEach((link) => {
      window.open(buildAbsoluteHref(link.href), "_blank", "noopener,noreferrer");
    });
    onCopyMessage?.(`已打开 ${links.length} 个变化位置`);
    setOpen(false);
  };

  const panelAlignClass = align === "right" ? "right-0" : "left-0";

  return (
    <div ref={containerRef} className="relative">
      <button type="button" onClick={() => void handleToggle()} className={buttonClassName}>
        {buttonLabel}
      </button>
      {open ? (
        <div className={`absolute top-full z-30 mt-2 w-80 rounded-[20px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4 shadow-[var(--af-shadow-card)] ${panelAlignClass}`}>
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">Section Links</p>
              <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">复制前 3 个变化 section</p>
            </div>
            <div className="flex flex-wrap items-center justify-end gap-2">
              {!loading && !loadError && links?.length ? (
                <button
                  type="button"
                  onClick={() => void handleCopyAllLinks()}
                  className="af-btn af-btn-secondary border px-2.5 py-1 text-xs"
                >
                  复制全部
                </button>
              ) : null}
              {!loading && !loadError && links?.length ? (
                <button
                  type="button"
                  onClick={handleOpenAllLinks}
                  className="af-btn af-btn-secondary border px-2.5 py-1 text-xs"
                >
                  打开全部
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="text-xs font-medium text-[var(--af-text-tertiary)] hover:text-[var(--af-text-secondary)]"
              >
                关闭
              </button>
            </div>
          </div>

          {loading ? <p className="mt-3 text-sm text-[var(--af-text-tertiary)]">读取中...</p> : null}
          {!loading && loadError ? (
            <div className="mt-3 rounded-[16px] af-state-panel-danger p-3">
              <p className="text-sm text-[var(--af-danger)]">{loadError}</p>
              <button
                type="button"
                onClick={() => void loadSectionLinks()}
                className="mt-2 text-xs font-medium text-[var(--af-danger)] underline decoration-[var(--af-danger)] underline-offset-4"
              >
                重试
              </button>
            </div>
          ) : null}
          {!loading && !loadError && links?.length ? (
            <div className="mt-3 space-y-2">
              {links.map((link, index) => (
                <div key={`${link.anchorId}-${index}`} className="rounded-[16px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
                  <p className="text-sm font-medium text-[var(--af-text-primary)]">{link.title}</p>
                  <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">{link.label}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => void handleCopyLink(link)}
                      className="af-btn af-btn-secondary border px-2.5 py-1 text-xs"
                    >
                      复制
                    </button>
                    <Link href={link.href} className="af-btn af-btn-secondary border px-2.5 py-1 text-xs">
                      打开
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
          {!loading && !loadError && links?.length === 0 ? (
            <p className="mt-3 text-sm text-[var(--af-text-tertiary)]">当前归档没有可用的变化 section 深链。</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
