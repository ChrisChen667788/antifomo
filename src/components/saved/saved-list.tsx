"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { FeedItem } from "@/lib/mock-data";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";

type TagFilter = "all" | "ai" | "business" | "job";
type SortMode = "latest" | "score" | "relevance";

interface SavedListProps {
  items: FeedItem[];
}

function relevanceScore(item: FeedItem): number {
  let score = item.valueScore;
  if (item.tags.some((tag) => tag.toLowerCase().includes("ai"))) score += 8;
  if (item.tags.some((tag) => tag.includes("商业"))) score += 4;
  if (item.tags.some((tag) => tag.includes("求职"))) score += 4;
  return score;
}

export function SavedList({ items }: SavedListProps) {
  const { t } = useAppPreferences();
  const [tagFilter, setTagFilter] = useState<TagFilter>("all");
  const [sortMode, setSortMode] = useState<SortMode>("latest");

  const tagOptions: TagFilter[] = ["all", "ai", "business", "job"];
  const sortOptions: SortMode[] = ["latest", "score", "relevance"];

  const result = useMemo(() => {
    const filtered = items.filter((item) => {
      if (tagFilter === "all") return true;
      if (tagFilter === "ai") {
        return item.tags.some((tag) => tag.toLowerCase().includes("ai"));
      }
      if (tagFilter === "business") {
        return item.tags.some((tag) => tag.includes("商业") || tag.toLowerCase().includes("business"));
      }
      return item.tags.some((tag) => tag.includes("求职") || tag.toLowerCase().includes("job"));
    });

    if (sortMode === "score") {
      return [...filtered].sort((a, b) => b.valueScore - a.valueScore);
    }

    if (sortMode === "relevance") {
      return [...filtered].sort((a, b) => relevanceScore(b) - relevanceScore(a));
    }

    return filtered;
  }, [items, tagFilter, sortMode]);

  return (
    <div className="space-y-4">
      <div className="af-glass flex flex-wrap items-center gap-3 rounded-3xl p-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-slate-500">{t("saved.filter", "筛选")}：</span>
          {tagOptions.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setTagFilter(option)}
              className={`af-btn px-3 py-1.5 ${
                tagFilter === option
                  ? "af-btn-primary"
                  : "af-btn-secondary"
              }`}
            >
              {t(`saved.filter.${option}`, option)}
            </button>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-2">
          <span className="text-sm text-slate-500">{t("saved.sort", "排序")}：</span>
          <select
            value={sortMode}
            onChange={(event) => setSortMode(event.target.value as SortMode)}
            className="af-input w-28 py-1.5 text-sm"
          >
            {sortOptions.map((option) => (
              <option key={option} value={option}>
                {t(`saved.sort.${option}`, option)}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="space-y-3">
        {result.map((item, idx) => (
          <article
            key={item.id}
            className="af-glass rounded-[28px] p-5"
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <h2 className="text-base font-semibold tracking-[-0.02em] text-slate-900 md:text-lg">
                {idx + 1}. {item.title || t("common.untitled", "未命名内容")}
              </h2>
              <span className="rounded-full border border-slate-200/80 bg-white/70 px-3 py-1 text-xs font-semibold text-slate-600">
                {t("saved.score", "评分")} {item.valueScore}
              </span>
            </div>

            <p className="mt-2 text-sm text-slate-500">
              {t("feed.deck.source", "来源")}：{item.source || t("common.unknownSource", "未知来源")}
            </p>
            <p className="mt-3 text-sm leading-6 text-slate-700 [display:-webkit-box] [-webkit-line-clamp:2] [-webkit-box-orient:vertical] overflow-hidden">
              {item.summary || t("common.noSummary", "暂无摘要")}
            </p>

            <div className="mt-3 flex flex-wrap gap-2">
              {item.tags.map((tag) => (
                <span
                  key={tag}
                  className="af-pill"
                >
                  #{tag}
                </span>
              ))}
            </div>

            <div className="mt-4">
              <Link
                href={`/items/${item.id}`}
                className="af-btn af-btn-secondary px-3 py-1.5"
              >
                {t("saved.openDetail", "查看详情")}
              </Link>
            </div>
          </article>
        ))}

        {result.length === 0 ? (
          <div className="af-glass rounded-3xl p-6 text-sm text-slate-500">
            {t("saved.empty", "当前筛选条件下暂无收藏内容。")}
          </div>
        ) : null}
      </div>
    </div>
  );
}
