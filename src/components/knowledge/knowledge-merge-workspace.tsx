"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { ApiKnowledgeEntry, ApiKnowledgeMergePreview } from "@/lib/api";
import { getKnowledgeMergePreview, mergeKnowledgeEntries } from "@/lib/api";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { AppIcon } from "@/components/ui/app-icon";

export function KnowledgeMergeWorkspace({
  entries,
  initialTitle,
}: {
  entries: ApiKnowledgeEntry[];
  initialTitle?: string;
}) {
  const { t } = useAppPreferences();
  const [mergeTitle, setMergeTitle] = useState(initialTitle || "");
  const [preview, setPreview] = useState<ApiKnowledgeMergePreview | null>(null);
  const [syncingPreview, setSyncingPreview] = useState(false);
  const [merging, setMerging] = useState(false);
  const [message, setMessage] = useState("");
  const [mergedEntryId, setMergedEntryId] = useState("");

  useEffect(() => {
    let active = true;
    if (!entries.length) {
      setPreview(null);
      return () => {
        active = false;
      };
    }
    setSyncingPreview(true);
    void getKnowledgeMergePreview({
      entry_ids: entries.map((entry) => entry.id),
      title: mergeTitle.trim() || undefined,
    })
      .then((result) => {
        if (!active) return;
        setPreview(result);
      })
      .catch(() => {
        if (!active) return;
        setPreview(null);
      })
      .finally(() => {
        if (!active) return;
        setSyncingPreview(false);
      });

    return () => {
      active = false;
    };
  }, [entries, mergeTitle]);

  const handleMerge = async () => {
    if (entries.length < 2) return;
    setMerging(true);
    setMessage("");
    try {
      const merged = await mergeKnowledgeEntries({
        entry_ids: entries.map((entry) => entry.id),
        title: mergeTitle.trim() || undefined,
      });
      setMergedEntryId(merged.id);
      setMessage(t("knowledge.mergeCreated", "已生成新的合并知识卡片"));
    } catch {
      setMessage(t("knowledge.mergeFailed", "合并失败，请稍后重试"));
    } finally {
      setMerging(false);
    }
  };

  return (
    <div className="space-y-5">
      <section className="af-glass rounded-[30px] p-5 md:p-6">
        <p className="af-kicker">{t("knowledge.mergeTitle", "知识卡片合并")}</p>
        <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-slate-900">
          {t("knowledge.mergeHint", "勾选 2 条及以上卡片后可合并为新卡片")}
        </h2>
        <p className="mt-3 text-sm leading-6 text-slate-500">
          {t("knowledge.mergePreviewHint", "新卡片会继承选中卡片里更稳定的组织状态。")}
        </p>
      </section>

      <section className="af-glass rounded-[30px] p-5 md:p-6">
        <label className="block">
          <span className="af-kicker">{t("knowledge.mergePreviewTitle", "合并预览")}</span>
          <input
            value={mergeTitle}
            onChange={(event) => setMergeTitle(event.target.value)}
            placeholder={t("knowledge.mergePlaceholder", "可选：为合并后的卡片指定标题")}
            className="af-input mt-2 w-full bg-white/80 text-slate-900"
          />
        </label>
        {preview ? (
          <div className="mt-4 rounded-[24px] border border-slate-200 bg-white/80 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="af-kicker">{t("knowledge.mergePreviewTitle", "合并预览")}</p>
                <h3 className="mt-2 text-lg font-semibold tracking-[-0.02em] text-slate-900">
                  {preview.title}
                </h3>
              </div>
              <span
                className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${
                  preview.ready ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-500"
                }`}
              >
                {preview.ready
                  ? t("knowledge.mergePreviewReady", "已满足合并条件")
                  : t("knowledge.mergePreviewWaiting", "至少再选 1 张卡片才可合并")}
              </span>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {preview.inherit_pinned ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-sky-100 px-2.5 py-1 text-xs text-sky-700">
                  <AppIcon name="flag" className="h-3.5 w-3.5" />
                  {t("knowledge.inheritPinned", "继承置顶")}
                </span>
              ) : null}
              {preview.inherit_focus_reference ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-indigo-100 px-2.5 py-1 text-xs text-indigo-700">
                  <AppIcon name="focus" className="h-3.5 w-3.5" />
                  {t("knowledge.inheritFocusRef", "继承 Focus 参考")}
                </span>
              ) : null}
              {preview.inherit_collection ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                  <AppIcon name="knowledge" className="h-3.5 w-3.5" />
                  {t("knowledge.inheritCollection", "继承分组")}：{preview.inherit_collection}
                </span>
              ) : null}
            </div>
            <div className="mt-4 space-y-2">
              {preview.titles.map((title, index) => (
                <div key={`${title}-${index}`} className="flex gap-3 text-sm text-slate-600">
                  <span className="min-w-5 text-sky-600">{index + 1}.</span>
                  <span>{title}</span>
                </div>
              ))}
              {preview.more_count > 0 ? (
                <p className="pl-8 text-sm text-slate-400">+{preview.more_count}</p>
              ) : null}
            </div>
          </div>
        ) : null}
        {syncingPreview ? <p className="mt-3 text-sm text-slate-400">{t("common.loading", "加载中...")}</p> : null}
      </section>

      <section className="af-glass rounded-[30px] p-5 md:p-6">
        <p className="af-kicker">{t("knowledge.selected", "已选中")} {entries.length}</p>
        <div className="mt-4 space-y-3">
          {entries.map((entry) => (
            <Link
              key={entry.id}
              href={`/knowledge/${entry.id}`}
              className="block rounded-[22px] border border-slate-200 bg-white/80 p-4 transition hover:border-slate-300"
            >
              <div className="flex items-start justify-between gap-3">
                <h3 className="text-sm font-semibold leading-6 text-slate-900">{entry.title}</h3>
                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-500">
                  {t("knowledge.selected", "已选中")}
                </span>
              </div>
              <p className="mt-2 text-xs text-slate-400">
                {t("knowledge.source", "来源")}：{entry.source_domain || t("common.unknownSource", "未知来源")}
              </p>
            </Link>
          ))}
        </div>
      </section>

      <section className="af-glass rounded-[30px] p-5 md:p-6">
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => {
              void handleMerge();
            }}
            disabled={entries.length < 2 || merging}
            className="af-btn af-btn-primary border px-5 py-2.5 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <AppIcon name="knowledge" className="h-4 w-4" />
            {merging ? t("knowledge.merging", "合并中...") : t("knowledge.mergeAction", "合并为新卡片")}
          </button>
          <Link href="/knowledge" className="af-btn af-btn-secondary border px-5 py-2.5">
            <AppIcon name="ignore" className="h-4 w-4" />
            {t("common.cancel", "取消")}
          </Link>
          {mergedEntryId ? (
            <Link href={`/knowledge/${mergedEntryId}`} className="af-btn af-btn-secondary border px-5 py-2.5">
              <AppIcon name="external" className="h-4 w-4" />
              {t("knowledge.openMerged", "打开新卡片")}
            </Link>
          ) : null}
        </div>
        {message ? <p className="mt-3 text-sm text-slate-500">{message}</p> : null}
      </section>
    </div>
  );
}
