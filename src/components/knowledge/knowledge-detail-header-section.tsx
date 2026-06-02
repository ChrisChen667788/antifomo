"use client";

import Link from "next/link";
import type { ApiKnowledgeEntry } from "@/lib/api/types";
import type { KnowledgeTranslateFn } from "@/components/knowledge/knowledge-detail-card-model";
import { AppIcon } from "@/components/ui/app-icon";
import { WorkBuddyMark } from "@/components/ui/workbuddy-mark";

interface KnowledgeDetailHeaderSectionProps {
  entry: ApiKnowledgeEntry;
  editing: boolean;
  draftTitle: string;
  pinning: boolean;
  exporting: boolean;
  workBuddyExporting: boolean;
  t: KnowledgeTranslateFn;
  onDraftTitleChange: (value: string) => void;
  onTogglePinned: () => void;
  onCopyMarkdown: () => void;
  onDownloadMarkdown: () => void;
  onWorkBuddyExport: () => void;
}

export function KnowledgeDetailHeaderSection({
  entry,
  editing,
  draftTitle,
  pinning,
  exporting,
  workBuddyExporting,
  t,
  onDraftTitleChange,
  onTogglePinned,
  onCopyMarkdown,
  onDownloadMarkdown,
  onWorkBuddyExport,
}: KnowledgeDetailHeaderSectionProps) {
  return (
    <section className="af-glass rounded-[30px] p-5 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="af-kicker">{t("knowledge.title", "知识卡片")}</p>
          {editing ? (
            <input
              value={draftTitle}
              onChange={(event) => onDraftTitleChange(event.target.value)}
              className="af-input mt-2 w-full bg-[var(--af-surface-elevated)] text-lg font-semibold text-[var(--af-text-primary)]"
            />
          ) : (
            <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-[var(--af-text-primary)]">
              {entry.title}
            </h2>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            {entry.is_pinned ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2.5 py-1 text-xs text-[var(--af-info)]">
                <AppIcon name="flag" className="h-3.5 w-3.5" />
                {t("knowledge.pinned", "置顶")}
              </span>
            ) : null}
            {entry.collection_name ? (
              <span className="rounded-full bg-[var(--af-surface-muted)] px-2.5 py-1 text-xs text-[var(--af-text-secondary)]">
                {entry.collection_name}
              </span>
            ) : null}
          </div>
          <p className="mt-3 text-sm text-[var(--af-text-tertiary)]">
            {t("knowledge.source", "来源")}：{entry.source_domain || t("common.unknownSource", "未知来源")}
          </p>
          <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">
            {t("knowledge.createdAt", "创建时间")}：{new Date(entry.created_at).toLocaleString()}
          </p>
          {entry.updated_at ? (
            <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">
              {t("knowledge.updatedAt", "最近更新")}：{new Date(entry.updated_at).toLocaleString()}
            </p>
          ) : null}
        </div>
        <div className="flex w-full flex-wrap gap-2 xl:pt-1">
          <button
            type="button"
            onClick={onTogglePinned}
            disabled={pinning}
            className={`af-btn border px-4 py-2 ${entry.is_pinned ? "af-btn-primary" : "af-btn-secondary"} disabled:cursor-not-allowed disabled:opacity-60`}
          >
            <AppIcon name="flag" className="h-4 w-4" />
            {entry.is_pinned ? t("knowledge.unpin", "取消置顶") : t("knowledge.pin", "置顶")}
          </button>
          <button
            type="button"
            onClick={onCopyMarkdown}
            className="af-btn af-btn-secondary border px-4 py-2"
          >
            <AppIcon name="copy" className="h-4 w-4" />
            {t("knowledge.copyMarkdown", "复制 Markdown")}
          </button>
          <button
            type="button"
            onClick={onDownloadMarkdown}
            disabled={exporting}
            className="af-btn af-btn-secondary border px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <AppIcon name="summary" className="h-4 w-4" />
            {exporting ? t("knowledge.downloading", "导出中...") : t("knowledge.download", "下载 Markdown")}
          </button>
          <button
            type="button"
            onClick={onWorkBuddyExport}
            disabled={workBuddyExporting}
            className="af-btn af-btn-secondary border px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <WorkBuddyMark size={14} />
            {workBuddyExporting
              ? t("knowledge.workbuddyExporting", "导出中...")
              : t("knowledge.workbuddyExport", "导出 Markdown")}
          </button>
          <Link href={`/knowledge/${entry.id}/edit`} className="af-btn af-btn-secondary border px-4 py-2">
            <AppIcon name="edit" className="h-4 w-4" />
            {t("knowledge.edit", "编辑")}
          </Link>
          <Link href="/knowledge" className="af-btn af-btn-secondary border px-4 py-2">
            <AppIcon name="knowledge" className="h-4 w-4" />
            {t("item.openKnowledgeList", "知识库列表")}
          </Link>
        </div>
      </div>
    </section>
  );
}
