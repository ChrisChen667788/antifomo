"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  getWechatFavoriteImportBatch,
  listItems,
  listWechatFavoriteImportBatches,
  reprocessItemsBatch,
  toFeedCardLabel,
  type CollectorWechatFavoriteImportBatch,
} from "@/lib/api";
import type { FeedItem } from "@/lib/mock-data";
import { FeedDeck } from "@/components/feed/feed-deck";
import { WechatFavoritesImportPanel } from "@/components/feed/wechat-favorites-import-panel";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { resolveItemTitle } from "@/lib/item-title";

const FEED_MODE_KEY = "anti_fomo_feed_mode";
const SESSION_GOAL_KEY = "anti_fomo_session_goal";
const WECHAT_IMPORT_REVIEW_KEY = "anti_fomo_wechat_import_review_ids";
const WECHAT_IMPORT_BATCH_KEY = "anti_fomo_wechat_import_review_batch_id";
const FEED_REFRESH_MS = 12000;

interface ImportReviewState {
  active: boolean;
  batchId: string | null;
  itemIds: string[];
  ready: number;
  processing: number;
  failed: number;
  triaged: number;
  total: number;
  failedItemIds: string[];
}

const EMPTY_IMPORT_REVIEW: ImportReviewState = {
  active: false,
  batchId: null,
  itemIds: [],
  ready: 0,
  processing: 0,
  failed: 0,
  triaged: 0,
  total: 0,
  failedItemIds: [],
};

function sanitizeSummary(
  raw: string | null | undefined,
  fallbackSummary: string,
): string {
  const value = (raw || "").replace(/\s+/g, " ").trim();
  if (!value) return fallbackSummary;
  if (value.includes("正文：") || value.includes("正文:")) {
    const parts = value.includes("正文：") ? value.split("正文：") : value.split("正文:");
    const body = (parts[1] || "").trim();
    if (body.length >= 12) return body;
  }
  return value
    .replace(/^标题[:：][^。！？!?]{1,80}/, "")
    .replace(/^关键词[:：][^。！？!?]{1,80}/, "")
    .replace(/^作者[:：][^。！？!?]{1,80}/, "")
    .trim() || value;
}

function mapApiItemsToFeed(
  items: Awaited<ReturnType<typeof listItems>>["items"],
  options: {
    untitled: string;
    unknownSource: string;
    noSummary: string;
  },
): FeedItem[] {
  return items.map((item) => {
    const score =
      item.score_value !== null && item.score_value !== undefined
        ? Math.round(((item.score_value - 1) / 4) * 100)
        : 50;
    const shortSummary = sanitizeSummary(
      item.short_summary || item.long_summary || options.noSummary,
      options.noSummary,
    );
    const longSummary = sanitizeSummary(
      item.long_summary || item.short_summary || options.noSummary,
      options.noSummary,
    );
    const suggestedActionType =
      item.action_suggestion === "deep_read"
        ? "deep_read"
        : item.action_suggestion === "later"
          ? "later"
          : "skip";

    return {
      id: item.id,
      title: resolveItemTitle(item, options.untitled),
      source: item.source_domain || options.unknownSource,
      tags: (item.tags || []).map((tag) => tag.tag_name),
      summary: longSummary,
      shortSummary,
      longSummary,
      valueScore: Math.max(0, Math.min(100, score)),
      suggestedAction: toFeedCardLabel(item.action_suggestion || null),
      suggestedActionType,
      recommendationReasons: item.recommendation_reason || [],
      whyRecommended: item.why_recommended || [],
      matchedPreferences: item.matched_preferences || [],
      url: item.source_url || "#",
      createdAt: item.created_at,
      recommendationScore: item.recommendation_score ?? undefined,
      topicMatchScore: item.topic_match_score ?? undefined,
      sourceMatchScore: item.source_match_score ?? undefined,
      preferenceVersion: item.preference_version || undefined,
      status: item.status,
      ingestRoute: item.ingest_route,
    };
  });
}

export function FeedHomeClient() {
  const { preferences, t } = useAppPreferences();
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<"normal" | "focus">("normal");
  const [goalText, setGoalText] = useState("");
  const [message, setMessage] = useState("");
  const [dataSource, setDataSource] = useState<"api" | "empty" | "api_offline">("empty");
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string>("");
  const [importReview, setImportReview] = useState<ImportReviewState>(EMPTY_IMPORT_REVIEW);
  const [retryingImportFailures, setRetryingImportFailures] = useState(false);

  const setNormalFeedItems = useCallback((apiItems: Awaited<ReturnType<typeof listItems>>["items"]) => {
    setItems(
      mapApiItemsToFeed(apiItems, {
        untitled: t("common.untitled", "未命名内容"),
        unknownSource: t("common.unknownSource", "未知来源"),
        noSummary: t("common.noSummary", "暂无摘要"),
      }),
    );
  }, [t]);

  const applyImportBatch = useCallback(async (batch: CollectorWechatFavoriteImportBatch) => {
    const reviewIds = Array.from(new Set(batch.review_item_ids.map((itemId) => itemId.trim()).filter(Boolean))).slice(0, 500);
    const response = reviewIds.length
      ? await listItems(reviewIds.length, {
          mode: "normal",
          includePending: true,
          itemIds: reviewIds,
        })
      : { items: [] };
    const readyItems = response.items.filter((item) => item.status === "ready");
    setNormalFeedItems(readyItems);
    setImportReview({
      active: reviewIds.length > 0,
      batchId: batch.id,
      itemIds: reviewIds,
      ready: batch.ready,
      processing: batch.processing,
      failed: batch.failed,
      triaged: batch.triaged,
      total: batch.item_ids.length,
      failedItemIds: batch.failed_item_ids,
    });
    setDataSource("api");
    if (reviewIds.length) {
      window.localStorage.setItem(WECHAT_IMPORT_BATCH_KEY, batch.id);
      window.localStorage.setItem(WECHAT_IMPORT_REVIEW_KEY, reviewIds.join(","));
    } else {
      window.localStorage.removeItem(WECHAT_IMPORT_BATCH_KEY);
      window.localStorage.removeItem(WECHAT_IMPORT_REVIEW_KEY);
    }
    if (!readyItems.length && batch.failed > 0 && batch.processing === 0) {
      setMessage("本次导入暂时没有可处理卡片，可重试失败条目或回到全部卡片。");
    } else if (!readyItems.length && batch.processing > 0) {
      setMessage(t("feed.importReview.waiting", "本次导入正在解析，卡片会在处理完成后自动出现。"));
    } else if (!reviewIds.length && batch.triaged > 0) {
      setMessage("最近一次微信收藏导入队列已处理完。");
    } else {
      setMessage("");
    }
    return reviewIds.length > 0;
  }, [setNormalFeedItems, t]);

  const refreshImportBatch = useCallback(async (batchId: string) => {
    const batch = await getWechatFavoriteImportBatch(batchId);
    return applyImportBatch(batch);
  }, [applyImportBatch]);

  const refreshImportReview = useCallback(async (itemIds: string[]) => {
    const ids = Array.from(new Set(itemIds.map((itemId) => itemId.trim()).filter(Boolean))).slice(0, 500);
    if (!ids.length) return false;
    const response = await listItems(ids.length, {
      mode: "normal",
      includePending: true,
      itemIds: ids,
    });
    const readyItems = response.items.filter((item) => item.status === "ready");
    const failedItems = response.items.filter((item) => item.status === "failed");
    const processingCount = response.items.filter((item) => item.status === "pending" || item.status === "processing").length;
    let nextMessage = "";
    if (!readyItems.length && failedItems.length && processingCount === 0) {
      nextMessage = "本次导入暂时没有可处理卡片，可重试失败条目或回到全部卡片。";
    } else if (!readyItems.length) {
      nextMessage = t("feed.importReview.waiting", "本次导入正在解析，卡片会在处理完成后自动出现。");
    }
    setNormalFeedItems(readyItems);
    setImportReview({
      active: true,
      batchId: null,
      itemIds: ids,
      ready: readyItems.length,
      processing: processingCount,
      failed: failedItems.length,
      triaged: 0,
      total: ids.length,
      failedItemIds: failedItems.map((item) => item.id),
    });
    setDataSource("api");
    setMessage(nextMessage);
    return true;
  }, [setNormalFeedItems, t]);

  const refreshFeed = useCallback(async (nextMode: "normal" | "focus", nextGoalText: string, itemIds?: string[]) => {
    setLoading(true);
    try {
      if (itemIds?.length) {
        await refreshImportReview(itemIds);
        return;
      }
      const response = await listItems(30, {
        mode: nextMode,
        goalText: nextGoalText || undefined,
        includePending: false,
      });
      if (response.items.length > 0) {
        setNormalFeedItems(response.items);
        setMessage("");
        setDataSource("api");
      } else {
        setItems([]);
        setMessage(t("feed.status.noRealData", "暂无真实数据，当前不再自动回退演示卡片。"));
        setDataSource("empty");
      }
    } catch {
      setItems([]);
      setMessage(t("feed.status.apiOfflineNoMock", "暂时无法读取实时数据，当前不再自动显示演示卡片。"));
      setDataSource("api_offline");
    } finally {
      setLastRefreshedAt(
        new Date().toLocaleTimeString(preferences.language, { hour12: false }),
      );
      setLoading(false);
    }
  }, [preferences.language, refreshImportReview, setNormalFeedItems, t]);

  useEffect(() => {
    const storedMode = typeof window !== "undefined" ? window.localStorage.getItem(FEED_MODE_KEY) : null;
    const storedGoal = typeof window !== "undefined" ? window.localStorage.getItem(SESSION_GOAL_KEY) : null;
    const storedImportIds = typeof window !== "undefined" ? window.localStorage.getItem(WECHAT_IMPORT_REVIEW_KEY) : null;
    const storedImportBatchId = typeof window !== "undefined" ? window.localStorage.getItem(WECHAT_IMPORT_BATCH_KEY) : null;
    const nextMode = storedMode === "focus" ? "focus" : "normal";
    const nextGoal = storedGoal || "";
    const importIds = (storedImportIds || "").split(",").map((itemId) => itemId.trim()).filter(Boolean);
    setMode(nextMode);
    setGoalText(nextGoal);
    const restore = async () => {
      try {
        if (storedImportBatchId) {
          setImportReview((prev) => ({ ...prev, active: true, batchId: storedImportBatchId }));
          try {
            const restored = await refreshImportBatch(storedImportBatchId);
            if (restored) return;
          } catch {
            window.localStorage.removeItem(WECHAT_IMPORT_BATCH_KEY);
          }
        }
        const latestBatches = await listWechatFavoriteImportBatches({ limit: 1, includeReviewed: false });
        const latestBatch = latestBatches.items[0];
        if (latestBatch && latestBatch.review_item_ids.length) {
          await applyImportBatch(latestBatch);
          return;
        }
        if (importIds.length) {
          setImportReview((prev) => ({
            ...prev,
            active: true,
            itemIds: importIds,
            total: importIds.length,
          }));
          await refreshFeed(nextMode, nextGoal, importIds);
          return;
        }
      } catch {
        window.localStorage.removeItem(WECHAT_IMPORT_BATCH_KEY);
      }
      await refreshFeed(nextMode, nextGoal);
    };
    void restore();
  }, [applyImportBatch, refreshFeed, refreshImportBatch, refreshImportReview]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (importReview.active && importReview.batchId) {
        void refreshImportBatch(importReview.batchId).catch(() => {
          window.localStorage.removeItem(WECHAT_IMPORT_BATCH_KEY);
          setImportReview((current) => ({ ...current, batchId: null }));
          if (importReview.itemIds.length) {
            void refreshImportReview(importReview.itemIds);
          }
        });
      } else {
        void refreshFeed(mode, goalText, importReview.active ? importReview.itemIds : undefined);
      }
    }, FEED_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [
    mode,
    goalText,
    importReview.active,
    importReview.batchId,
    importReview.itemIds,
    refreshFeed,
    refreshImportBatch,
    refreshImportReview,
  ]);

  const switchMode = (nextMode: "normal" | "focus") => {
    setMode(nextMode);
    window.localStorage.setItem(FEED_MODE_KEY, nextMode);
    const storedGoal = window.localStorage.getItem(SESSION_GOAL_KEY) || "";
    const nextGoal = nextMode === "focus" ? storedGoal : "";
    setGoalText(nextGoal);
    setImportReview(EMPTY_IMPORT_REVIEW);
    window.localStorage.removeItem(WECHAT_IMPORT_BATCH_KEY);
    window.localStorage.removeItem(WECHAT_IMPORT_REVIEW_KEY);
    void refreshFeed(nextMode, nextGoal);
  };

  const clearImportReview = () => {
    setImportReview(EMPTY_IMPORT_REVIEW);
    window.localStorage.removeItem(WECHAT_IMPORT_BATCH_KEY);
    window.localStorage.removeItem(WECHAT_IMPORT_REVIEW_KEY);
    void refreshFeed(mode, goalText);
  };

  const retryFailedImportItems = async () => {
    if (!importReview.failedItemIds.length || retryingImportFailures) return;
    setRetryingImportFailures(true);
    try {
      await reprocessItemsBatch({
        item_ids: importReview.failedItemIds,
        output_language: preferences.language,
        failed_only: true,
      });
      if (importReview.batchId) {
        await refreshImportBatch(importReview.batchId);
      } else {
        await refreshFeed(mode, goalText, importReview.itemIds);
      }
    } catch {
      setMessage("重试失败条目时出错，请稍后再试。");
    } finally {
      setRetryingImportFailures(false);
    }
  };

  const removeTriagedImportItem = (itemId: string, feedbackType: "like" | "ignore" | "save") => {
    if (!importReview.active || (feedbackType !== "ignore" && feedbackType !== "save")) {
      return false;
    }
    if (!importReview.itemIds.includes(itemId)) {
      return false;
    }
    const nextItemIds = importReview.itemIds.filter((value) => value !== itemId);
    const nextFailedItemIds = importReview.failedItemIds.filter((value) => value !== itemId);
    setItems((prev) => prev.filter((item) => item.id !== itemId));
    setImportReview((prev) => ({
      ...prev,
      itemIds: nextItemIds,
      failedItemIds: nextFailedItemIds,
      ready: Math.max(0, prev.ready - 1),
      failed: nextFailedItemIds.length,
      triaged: prev.triaged + 1,
      total: prev.batchId ? prev.total : nextItemIds.length,
      active: nextItemIds.length > 0,
    }));
    if (nextItemIds.length) {
      window.localStorage.setItem(WECHAT_IMPORT_REVIEW_KEY, nextItemIds.join(","));
      if (importReview.batchId) {
        window.localStorage.setItem(WECHAT_IMPORT_BATCH_KEY, importReview.batchId);
      }
    } else {
      window.localStorage.removeItem(WECHAT_IMPORT_BATCH_KEY);
      window.localStorage.removeItem(WECHAT_IMPORT_REVIEW_KEY);
      setMessage("本次导入队列已处理完。");
    }
    return true;
  };

  const importReviewParsed = importReview.ready + importReview.failed + importReview.triaged;
  const importReviewProgress = importReview.total
    ? Math.round((importReviewParsed / importReview.total) * 100)
    : 0;

  return (
    <>
      <div className="af-glass af-hero-surface mb-5 rounded-lg px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="af-kicker">
              {t("feed.status.title", "Feed Status")}
            </p>
            <p className="mt-1 text-2xl font-semibold text-[var(--af-text-primary)]">
              {t("feed.status.processedToday", "今日已处理")} {items.length}{" "}
              {t("feed.status.itemsUnit", "条")}
            </p>
            <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">
              {t("feed.status.dataSource", "数据源")}：
              {dataSource === "api"
                ? t("data.api", "实时数据")
                : dataSource === "api_offline"
                  ? t("feed.status.apiOffline", "实时数据暂不可用")
                  : t("feed.status.noRealDataShort", "无真实数据")} ·{" "}
              {t("feed.status.lastRefreshed", "最近刷新")}：{lastRefreshedAt || "--:--:--"}
            </p>
          </div>

          <div className="flex items-center gap-2 text-sm">
            <button
              type="button"
              onClick={() => switchMode("normal")}
              className={`af-btn px-3 py-1 ${mode === "normal" ? "af-btn-primary" : "af-btn-secondary"}`}
            >
              {t("mode.normal", "Normal")}
            </button>
            <button
              type="button"
              onClick={() => switchMode("focus")}
              className={`af-btn px-3 py-1 ${mode === "focus" ? "af-btn-primary" : "af-btn-secondary"}`}
            >
              {t("mode.focus", "Focus")}
            </button>
            <Link href="/focus" className="af-btn af-btn-secondary px-3 py-1">
              {t("feed.status.configureFocus", "配置 Focus")}
            </Link>
            <button
              type="button"
              onClick={() => {
                if (importReview.active && importReview.batchId) {
                  void refreshImportBatch(importReview.batchId);
                } else {
                  void refreshFeed(mode, goalText, importReview.active ? importReview.itemIds : undefined);
                }
              }}
              className="af-btn af-btn-secondary px-3 py-1"
            >
              {t("feed.status.refresh", "刷新")}
            </button>
          </div>
        </div>

        {mode === "focus" ? (
          <p className="mt-2 text-xs text-[var(--af-text-tertiary)]">
            {t("feed.status.focusGoal", "Focus 目标")}：
            {goalText || t("feed.status.focusGoalUnset", "未设置（可去 Focus 页面输入）")}
          </p>
        ) : null}
        {loading ? (
          <p className="mt-2 text-xs text-[var(--af-text-tertiary)]">
            {t("feed.status.refreshing", "正在刷新 Feed...")}
          </p>
        ) : null}
        {message ? <p className="mt-2 text-xs text-[var(--af-text-tertiary)]">{message}</p> : null}
      </div>
      <WechatFavoritesImportPanel
        onImported={(result) => {
          if (result.batch) {
            window.localStorage.setItem(WECHAT_IMPORT_BATCH_KEY, result.batch.id);
            void applyImportBatch(result.batch);
            return;
          }
          const itemIds = Array.from(
            new Set(
              [
                ...result.created_item_ids,
                ...result.results.map((item) => item.item_id || ""),
              ].filter(Boolean),
            ),
          );
          if (itemIds.length) {
            if (result.batch_id) {
              window.localStorage.setItem(WECHAT_IMPORT_BATCH_KEY, result.batch_id);
            }
            window.localStorage.setItem(WECHAT_IMPORT_REVIEW_KEY, itemIds.join(","));
            setImportReview({
              active: true,
              batchId: result.batch_id || null,
              itemIds,
              ready: 0,
              processing: itemIds.length,
              failed: 0,
              triaged: 0,
              total: itemIds.length,
              failedItemIds: [],
            });
            void refreshFeed(mode, goalText, itemIds);
          } else {
            void refreshFeed(mode, goalText);
          }
        }}
        onBatchSelected={(batch) => {
          window.localStorage.setItem(WECHAT_IMPORT_BATCH_KEY, batch.id);
          void applyImportBatch(batch);
        }}
      />
      {importReview.active ? (
        <div className="af-glass mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg px-4 py-3 text-sm">
          <div>
            <p className="font-semibold text-[var(--af-text-primary)]">本次微信收藏导入队列</p>
            <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">
              Ready {importReview.ready} / Processing {importReview.processing} / Failed {importReview.failed} / Done {importReview.triaged} / Total {importReview.total}
            </p>
            <div className="af-progress-track mt-2 h-1.5 w-48 overflow-hidden rounded-full">
              <div
                className="af-progress-fill h-full rounded-full transition-all"
                style={{ width: `${importReviewProgress}%` }}
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => {
                if (importReview.batchId) {
                  void refreshImportBatch(importReview.batchId);
                } else {
                  void refreshFeed(mode, goalText, importReview.itemIds);
                }
              }}
              className="af-btn af-btn-secondary px-3 py-1.5 text-xs"
            >
              刷新本批
            </button>
            {importReview.failed > 0 ? (
              <button
                type="button"
                onClick={() => {
                  void retryFailedImportItems();
                }}
                disabled={retryingImportFailures}
                className="af-btn af-btn-secondary px-3 py-1.5 text-xs disabled:cursor-not-allowed disabled:opacity-60"
              >
                {retryingImportFailures ? "重试中..." : "重试失败"}
              </button>
            ) : null}
            <button
              type="button"
              onClick={clearImportReview}
              className="af-btn af-btn-secondary px-3 py-1.5 text-xs"
            >
              回到全部卡片
            </button>
          </div>
        </div>
      ) : null}
      <FeedDeck items={items} onItemTriaged={removeTriagedImportItem} />
    </>
  );
}
