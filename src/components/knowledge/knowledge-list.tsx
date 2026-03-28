"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { ApiKnowledgeEntry } from "@/lib/api";
import { mergeKnowledgeEntries, updateKnowledgeEntry } from "@/lib/api";
import { KnowledgeRuleCard } from "@/components/knowledge/knowledge-rule-card";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { AppIcon } from "@/components/ui/app-icon";

export function KnowledgeList({ items }: { items: ApiKnowledgeEntry[] }) {
  const { t } = useAppPreferences();
  const [entryItems, setEntryItems] = useState(items);
  const [query, setQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [collectionFilter, setCollectionFilter] = useState("all");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [mergeTitle, setMergeTitle] = useState("");
  const [groupDraft, setGroupDraft] = useState("");
  const [mergeMessage, setMergeMessage] = useState("");
  const [merging, setMerging] = useState(false);
  const [pinMessage, setPinMessage] = useState("");
  const [lastMergedEntryId, setLastMergedEntryId] = useState("");

  const sourceOptions = useMemo(() => {
    const unique = Array.from(
      new Set(entryItems.map((item) => item.source_domain || t("common.unknownSource", "未知来源"))),
    );
    return ["all", ...unique];
  }, [entryItems, t]);

  const collectionOptions = useMemo(() => {
    const unique = Array.from(
      new Set(
        entryItems
          .map((item) => (item.collection_name || "").trim())
          .filter(Boolean),
      ),
    );
    return ["all", "pinned", "ungrouped", ...unique];
  }, [entryItems]);

  const filteredItems = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return entryItems
      .filter((item) => {
        const source = item.source_domain || t("common.unknownSource", "未知来源");
        if (sourceFilter !== "all" && source !== sourceFilter) {
          return false;
        }
        if (collectionFilter === "pinned" && !item.is_pinned) {
          return false;
        }
        if (collectionFilter === "ungrouped" && item.collection_name) {
          return false;
        }
        if (!["all", "pinned", "ungrouped"].includes(collectionFilter) && item.collection_name !== collectionFilter) {
          return false;
        }
        if (!normalizedQuery) return true;
        const haystack = `${item.title} ${item.content} ${source} ${item.collection_name || ""}`.toLowerCase();
        return haystack.includes(normalizedQuery);
      })
      .sort((left, right) => {
        if (!normalizedQuery) {
          return (
            Number(!!right.is_pinned) - Number(!!left.is_pinned) ||
            Date.parse(right.created_at) - Date.parse(left.created_at)
          );
        }
        const score = (item: ApiKnowledgeEntry) => {
          const title = item.title.toLowerCase();
          const content = item.content.toLowerCase();
          const source = (item.source_domain || "").toLowerCase();
          const collection = (item.collection_name || "").toLowerCase();
          let value = 0;
          if (title.startsWith(normalizedQuery)) value += 120;
          else if (title.includes(normalizedQuery)) value += 80;
          if (source.includes(normalizedQuery)) value += 36;
          if (content.includes(normalizedQuery)) value += 24;
          if (collection.includes(normalizedQuery)) value += 30;
          if (item.is_focus_reference) value += 18;
          if (item.is_pinned) value += 12;
          value += Math.max(0, 20 - Math.floor((Date.now() - Date.parse(item.created_at)) / 86_400_000));
          return value;
        };
        return score(right) - score(left);
      });
  }, [collectionFilter, entryItems, query, sourceFilter, t]);

  const mergePreview = useMemo(() => {
    if (!selectedIds.length) return null;
    const order = new Map(selectedIds.map((id, index) => [id, index]));
    const selectedEntries = entryItems
      .filter((item) => order.has(item.id))
      .sort((left, right) => (order.get(left.id) || 0) - (order.get(right.id) || 0));
    if (!selectedEntries.length) return null;

    const typedTitle = mergeTitle.trim();
    const uniqueTitles: string[] = [];
    selectedEntries.forEach((entry) => {
      const title = entry.title.trim();
      if (title && !uniqueTitles.includes(title)) {
        uniqueTitles.push(title);
      }
    });

    const autoTitle =
      typedTitle ||
      (uniqueTitles.length <= 1
        ? `${uniqueTitles[0] || t("common.untitled", "未命名内容")} / ${t("knowledge.mergePreviewSuffix", "综合卡片")}`
        : `${uniqueTitles[0]} + ${uniqueTitles.length - 1} ${t("knowledge.mergePreviewPlus", "条延展")}`);

    const collections = Array.from(
      new Set(selectedEntries.map((entry) => (entry.collection_name || "").trim()).filter(Boolean)),
    );

    return {
      title: autoTitle,
      count: selectedEntries.length,
      inheritPinned: selectedEntries.some((entry) => !!entry.is_pinned),
      inheritFocusRef: selectedEntries.some((entry) => !!entry.is_focus_reference),
      inheritCollection: collections.length === 1 ? collections[0] : "",
      titles: selectedEntries.slice(0, 3).map((entry) => entry.title),
      moreCount: Math.max(0, selectedEntries.length - 3),
      ready: selectedEntries.length >= 2,
    };
  }, [entryItems, mergeTitle, selectedIds, t]);

  const mergeHref = useMemo(() => {
    if (selectedIds.length < 2) return "/knowledge";
    const params = new URLSearchParams({
      ids: selectedIds.join(","),
    });
    if (mergeTitle.trim()) {
      params.set("title", mergeTitle.trim());
    }
    return `/knowledge/merge?${params.toString()}`;
  }, [mergeTitle, selectedIds]);

  const togglePinned = async (entry: ApiKnowledgeEntry) => {
    setPinMessage("");
    try {
      const updated = await updateKnowledgeEntry(entry.id, {
        is_pinned: !entry.is_pinned,
      });
      setEntryItems((current) => current.map((item) => (item.id === entry.id ? updated : item)));
      setPinMessage(
        updated.is_pinned
          ? t("knowledge.pinEnabled", "已置顶这张知识卡片")
          : t("knowledge.pinDisabled", "已取消置顶"),
      );
    } catch {
      setPinMessage(t("knowledge.pinFailed", "置顶更新失败，请稍后重试"));
    }
  };

  const applyBatchUpdate = async (payload: { is_pinned?: boolean; collection_name?: string | null }) => {
    if (!selectedIds.length) return;
    setMerging(true);
    setMergeMessage("");
    try {
      const updatedEntries = await Promise.all(
        selectedIds.map((entryId) => updateKnowledgeEntry(entryId, payload)),
      );
      const updatedMap = new Map(updatedEntries.map((entry) => [entry.id, entry]));
      setEntryItems((current) => current.map((item) => updatedMap.get(item.id) || item));
      setSelectedIds([]);
      setGroupDraft("");
      setLastMergedEntryId("");
      setMergeMessage(t("knowledge.batchDone", "批量更新已完成"));
    } catch {
      setMergeMessage(t("knowledge.batchFailed", "批量更新失败，请稍后重试"));
    } finally {
      setMerging(false);
    }
  };

  const toggleSelect = (entryId: string) => {
    setSelectedIds((current) =>
      current.includes(entryId) ? current.filter((id) => id !== entryId) : [...current, entryId],
    );
  };

  const handleMerge = async () => {
    if (selectedIds.length < 2) return;
    setMerging(true);
    setMergeMessage("");
    try {
      const merged = await mergeKnowledgeEntries({
        entry_ids: selectedIds,
        title: mergeTitle.trim() || undefined,
      });
      setEntryItems((current) => [merged, ...current]);
      setSelectedIds([]);
      setMergeTitle("");
      setLastMergedEntryId(merged.id);
      setMergeMessage(t("knowledge.mergeCreated", "已生成新的合并知识卡片"));
    } catch {
      setMergeMessage(t("knowledge.mergeFailed", "合并失败，请稍后重试"));
    } finally {
      setMerging(false);
    }
  };

  if (!entryItems.length) {
    return (
      <div className="space-y-4">
        <KnowledgeRuleCard />
        <div className="af-glass rounded-[28px] p-5 text-sm text-slate-500">
          {t("knowledge.emptyList", "知识库里还没有内容，先在详情页加入一张卡片。")}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <KnowledgeRuleCard />
      <div className="af-glass rounded-[28px] p-4">
        <div className="flex flex-wrap items-center gap-3">
          <p className="af-kicker">{t("knowledge.mergeTitle", "知识卡片合并")}</p>
          <span className="text-sm text-slate-500">
            {selectedIds.length > 0
              ? t("knowledge.mergeSelected", `已选择 ${selectedIds.length} 条卡片`)
              : t("knowledge.mergeHint", "勾选 2 条及以上卡片后可合并为新卡片")}
          </span>
        </div>
        {mergePreview ? (
          <div className="mt-4 rounded-[24px] border border-slate-200/80 bg-white/80 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="af-kicker">{t("knowledge.mergePreviewTitle", "合并预览")}</p>
                <h3 className="mt-2 text-lg font-semibold tracking-[-0.02em] text-slate-900">
                  {mergePreview.title}
                </h3>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  {t("knowledge.mergePreviewHint", "新卡片会继承选中卡片里更稳定的组织状态。")}
                </p>
              </div>
              <span
                className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${
                  mergePreview.ready
                    ? "bg-blue-100 text-blue-700"
                    : "bg-slate-100 text-slate-500"
                }`}
              >
                {mergePreview.ready
                  ? t("knowledge.mergePreviewReady", "已满足合并条件")
                  : t("knowledge.mergePreviewWaiting", "至少再选 1 张卡片才可合并")}
              </span>
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
              {mergePreview.inheritPinned ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-sky-100 px-2.5 py-1 text-xs text-sky-700">
                  <AppIcon name="flag" className="h-3.5 w-3.5" />
                  {t("knowledge.inheritPinned", "继承置顶")}
                </span>
              ) : null}
              {mergePreview.inheritFocusRef ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-indigo-100 px-2.5 py-1 text-xs text-indigo-700">
                  <AppIcon name="focus" className="h-3.5 w-3.5" />
                  {t("knowledge.inheritFocusRef", "继承 Focus 参考")}
                </span>
              ) : null}
              {mergePreview.inheritCollection ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                  <AppIcon name="knowledge" className="h-3.5 w-3.5" />
                  {t("knowledge.inheritCollection", "继承分组")}：{mergePreview.inheritCollection}
                </span>
              ) : null}
            </div>

            <div className="mt-4 space-y-2">
              {mergePreview.titles.map((title, index) => (
                <div key={`${title}-${index}`} className="flex items-start gap-3 text-sm text-slate-600">
                  <span className="mt-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-slate-100 px-1.5 text-xs text-slate-500">
                    {index + 1}
                  </span>
                  <span className="line-clamp-2">{title}</span>
                </div>
              ))}
              {mergePreview.moreCount > 0 ? (
                <p className="text-xs text-slate-400">+{mergePreview.moreCount}</p>
              ) : null}
            </div>
          </div>
        ) : null}
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <input
            value={mergeTitle}
            onChange={(event) => setMergeTitle(event.target.value)}
            placeholder={t("knowledge.mergePlaceholder", "可选：为合并后的卡片指定标题")}
            className="af-input min-w-[260px] flex-1 bg-white/75 text-sm"
          />
          <Link
            href={mergeHref}
            aria-disabled={selectedIds.length < 2}
            className={`af-btn px-4 py-2 ${selectedIds.length < 2 ? "af-btn-secondary pointer-events-none opacity-60" : "af-btn-primary"}`}
          >
            <AppIcon name="merge" className="h-4 w-4" />
            {t("knowledge.mergeAction", "合并为新卡片")}
          </Link>
        </div>
        {selectedIds.length ? (
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <input
              value={groupDraft}
              onChange={(event) => setGroupDraft(event.target.value)}
              placeholder={t("knowledge.batchGroupPlaceholder", "为选中卡片设置分组")}
              className="af-input min-w-[260px] flex-1 bg-white/75 text-sm"
            />
            <button
              type="button"
              onClick={() => {
                void applyBatchUpdate({ is_pinned: true });
              }}
              disabled={merging}
              className="af-btn af-btn-secondary px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <AppIcon name="flag" className="h-4 w-4" />
              {t("knowledge.batchPin", "批量置顶")}
            </button>
            <button
              type="button"
              onClick={() => {
                void applyBatchUpdate({ is_pinned: false });
              }}
              disabled={merging}
              className="af-btn af-btn-secondary px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <AppIcon name="ignore" className="h-4 w-4" />
              {t("knowledge.batchUnpin", "批量取消置顶")}
            </button>
            <button
              type="button"
              onClick={() => {
                void applyBatchUpdate({ collection_name: groupDraft.trim() || null });
              }}
              disabled={merging}
              className="af-btn af-btn-secondary px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <AppIcon name="knowledge" className="h-4 w-4" />
              {t("knowledge.batchGroupApply", "批量设分组")}
            </button>
          </div>
        ) : null}
        {mergeMessage ? (
          <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-slate-500">
            <span>{mergeMessage}</span>
            {lastMergedEntryId ? (
              <Link href={`/knowledge/${lastMergedEntryId}`} className="af-btn af-btn-secondary border px-3 py-1.5 text-sm">
                <AppIcon name="knowledge" className="h-4 w-4" />
                {t("knowledge.openMerged", "打开新卡片")}
              </Link>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="af-glass rounded-[28px] p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-[220px] flex-1">
            <AppIcon
              name="search"
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
            />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("knowledge.searchPlaceholder", "搜索标题、笔记或来源")}
              className="af-input w-full bg-white/75 py-2 pl-10 pr-3 text-sm"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            {sourceOptions.map((source) => (
              <button
                key={source}
                type="button"
                onClick={() => setSourceFilter(source)}
                className={`af-btn px-3 py-1.5 ${
                  sourceFilter === source ? "af-btn-primary" : "af-btn-secondary"
                }`}
              >
                {source === "all" ? t("knowledge.filterAll", "全部来源") : source}
              </button>
            ))}
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {collectionOptions.map((collection) => (
            <button
              key={collection}
              type="button"
              onClick={() => setCollectionFilter(collection)}
              className={`af-btn px-3 py-1.5 text-sm ${
                collectionFilter === collection ? "af-btn-primary" : "af-btn-secondary"
              }`}
            >
              {collection === "all"
                ? t("knowledge.groupAll", "全部分组")
                : collection === "pinned"
                  ? t("knowledge.groupPinned", "仅看置顶")
                  : collection === "ungrouped"
                    ? t("knowledge.groupUngrouped", "未分组")
                    : collection}
            </button>
          ))}
        </div>
        <p className="mt-3 text-xs text-slate-400">
          {query.trim()
            ? t("knowledge.searchSorted", "搜索结果已按相关度优先排序")
            : t("knowledge.latestFirst", "默认按最新归档时间排序")}
        </p>
        {pinMessage ? <p className="mt-2 text-sm text-slate-500">{pinMessage}</p> : null}
      </div>

      <div className="grid gap-4">
        {filteredItems.map((item) => {
          const selected = selectedIds.includes(item.id);
          return (
            <div
              key={item.id}
              className={`af-glass rounded-[28px] p-5 transition-transform duration-200 hover:-translate-y-0.5 ${
                selected ? "ring-2 ring-blue-200" : ""
              }`}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    {item.is_pinned ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-sky-100 px-2 py-1 text-xs text-sky-700">
                        <AppIcon name="flag" className="h-3.5 w-3.5" />
                        {t("knowledge.pinned", "置顶")}
                      </span>
                    ) : null}
                    {item.is_focus_reference ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-indigo-100 px-2 py-1 text-xs text-indigo-700">
                        <AppIcon name="focus" className="h-3.5 w-3.5" />
                        {t("knowledge.focusRef", "Focus 参考")}
                      </span>
                    ) : null}
                    {item.collection_name ? (
                      <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">
                        {item.collection_name}
                      </span>
                    ) : null}
                  </div>
                  <h2 className="mt-2 text-lg font-semibold tracking-[-0.02em] text-slate-900">{item.title}</h2>
                  <p className="mt-2 text-sm text-slate-500">
                    {t("knowledge.source", "来源")}：{item.source_domain || t("common.unknownSource", "未知来源")}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    {t("knowledge.createdAt", "创建时间")}：{new Date(item.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      void togglePinned(item);
                    }}
                    className={`af-btn px-3 py-1.5 text-sm ${
                      item.is_pinned ? "af-btn-primary" : "af-btn-secondary"
                    }`}
                  >
                    <AppIcon name="flag" className="h-4 w-4" />
                    {item.is_pinned ? t("knowledge.unpin", "取消置顶") : t("knowledge.pin", "置顶")}
                  </button>
                  <button
                    type="button"
                    onClick={() => toggleSelect(item.id)}
                    className={`af-btn px-3 py-1.5 text-sm ${
                      selected ? "af-btn-primary" : "af-btn-secondary"
                    }`}
                  >
                    <AppIcon name="merge" className="h-4 w-4" />
                    {selected ? t("knowledge.selected", "已选中") : t("knowledge.select", "选择")}
                  </button>
                  <Link href={`/knowledge/${item.id}`} className="af-btn af-btn-secondary border px-3 py-1.5 text-sm">
                    <AppIcon name="external" className="h-4 w-4" />
                    {t("saved.openDetail", "查看详情")}
                  </Link>
                </div>
              </div>
              <p
                className="mt-4 text-sm leading-7 text-slate-700"
                style={{
                  display: "-webkit-box",
                  WebkitLineClamp: 3,
                  WebkitBoxOrient: "vertical",
                  overflow: "hidden",
                }}
              >
                {item.content}
              </p>
            </div>
          );
        })}
      </div>

      {!filteredItems.length ? (
        <div className="af-glass rounded-[28px] p-5 text-sm text-slate-500">
          {t("knowledge.emptyList", "知识库里还没有内容，先在详情页加入一张卡片。")}
        </div>
      ) : null}
    </div>
  );
}
