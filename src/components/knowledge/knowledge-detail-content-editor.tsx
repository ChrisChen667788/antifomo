"use client";

import type { ApiKnowledgeEntry } from "@/lib/api/types";
import type { KnowledgeTranslateFn } from "@/components/knowledge/knowledge-detail-card-model";
import { AppIcon } from "@/components/ui/app-icon";

interface KnowledgeDetailContentEditorProps {
  entry: ApiKnowledgeEntry;
  editing: boolean;
  draftCollection: string;
  draftContent: string;
  draftTitle: string;
  saving: boolean;
  message: string;
  t: KnowledgeTranslateFn;
  onDraftCollectionChange: (value: string) => void;
  onDraftContentChange: (value: string) => void;
  onSave: () => void;
}

export function KnowledgeDetailContentEditor({
  entry,
  editing,
  draftCollection,
  draftContent,
  draftTitle,
  saving,
  message,
  t,
  onDraftCollectionChange,
  onDraftContentChange,
  onSave,
}: KnowledgeDetailContentEditorProps) {
  if (editing) {
    return (
      <div className="mt-3 space-y-3">
        <input
          value={draftCollection}
          onChange={(event) => onDraftCollectionChange(event.target.value)}
          placeholder={t("knowledge.groupPlaceholder", "输入分组名称，例如：AI 制药")}
          className="af-input w-full bg-[var(--af-surface-elevated)] text-sm text-[var(--af-text-secondary)]"
        />
        <textarea
          value={draftContent}
          onChange={(event) => onDraftContentChange(event.target.value)}
          rows={12}
          className="af-input w-full bg-[var(--af-surface-elevated)] text-sm leading-7 text-[var(--af-text-secondary)]"
        />
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={onSave}
            disabled={saving || !draftTitle.trim() || !draftContent.trim()}
            className="af-btn af-btn-primary px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <AppIcon name="bookmark" className="h-4 w-4" />
            {saving ? t("common.saving", "保存中...") : t("common.save", "保存")}
          </button>
          {message ? <span className="text-sm text-[var(--af-text-tertiary)]">{message}</span> : null}
        </div>
      </div>
    );
  }

  return (
    <>
      <p className="mt-3 text-sm leading-7 text-[var(--af-text-secondary)]">{entry.content}</p>
      {message ? <p className="mt-3 text-sm text-[var(--af-text-tertiary)]">{message}</p> : null}
    </>
  );
}
