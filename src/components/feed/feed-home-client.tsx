"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { listItems, toFeedCardLabel } from "@/lib/api";
import type { FeedItem } from "@/lib/mock-data";
import { FeedDeck } from "@/components/feed/feed-deck";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { resolveItemTitle } from "@/lib/item-title";

const FEED_MODE_KEY = "anti_fomo_feed_mode";
const SESSION_GOAL_KEY = "anti_fomo_session_goal";
const FEED_REFRESH_MS = 12000;

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

  const refreshFeed = useCallback(async (nextMode: "normal" | "focus", nextGoalText: string) => {
    setLoading(true);
    try {
      const response = await listItems(30, {
        mode: nextMode,
        goalText: nextGoalText || undefined,
        includePending: false,
      });
      if (response.items.length > 0) {
        setItems(
          mapApiItemsToFeed(response.items, {
            untitled: t("common.untitled", "未命名内容"),
            unknownSource: t("common.unknownSource", "未知来源"),
            noSummary: t("common.noSummary", "暂无摘要"),
          }),
        );
        setMessage("");
        setDataSource("api");
      } else {
        setItems([]);
        setMessage(t("feed.status.noRealData", "暂无真实数据，当前不再自动回退演示卡片。"));
        setDataSource("empty");
      }
    } catch {
      setItems([]);
      setMessage(t("feed.status.apiOfflineNoMock", "API 未连接，当前不再自动回退演示卡片。"));
      setDataSource("api_offline");
    } finally {
      setLastRefreshedAt(
        new Date().toLocaleTimeString(preferences.language, { hour12: false }),
      );
      setLoading(false);
    }
  }, [preferences.language, t]);

  useEffect(() => {
    const storedMode = typeof window !== "undefined" ? window.localStorage.getItem(FEED_MODE_KEY) : null;
    const storedGoal = typeof window !== "undefined" ? window.localStorage.getItem(SESSION_GOAL_KEY) : null;
    const nextMode = storedMode === "focus" ? "focus" : "normal";
    const nextGoal = storedGoal || "";
    setMode(nextMode);
    setGoalText(nextGoal);
    void refreshFeed(nextMode, nextGoal);
  }, [refreshFeed]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void refreshFeed(mode, goalText);
    }, FEED_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [mode, goalText, refreshFeed]);

  const switchMode = (nextMode: "normal" | "focus") => {
    setMode(nextMode);
    window.localStorage.setItem(FEED_MODE_KEY, nextMode);
    const storedGoal = window.localStorage.getItem(SESSION_GOAL_KEY) || "";
    const nextGoal = nextMode === "focus" ? storedGoal : "";
    setGoalText(nextGoal);
    void refreshFeed(nextMode, nextGoal);
  };

  return (
    <>
      <div className="af-glass af-hero-surface mb-5 rounded-3xl px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              {t("feed.status.title", "Feed Status")}
            </p>
            <p className="mt-1 text-2xl font-semibold tracking-[-0.02em] text-slate-900">
              {t("feed.status.processedToday", "今日已处理")} {items.length}{" "}
              {t("feed.status.itemsUnit", "条")}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {t("feed.status.dataSource", "数据源")}：
              {dataSource === "api"
                ? t("data.api", "实时 API")
                : dataSource === "api_offline"
                  ? t("feed.status.apiOffline", "API 离线")
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
                void refreshFeed(mode, goalText);
              }}
              className="af-btn af-btn-secondary px-3 py-1"
            >
              {t("feed.status.refresh", "刷新")}
            </button>
          </div>
        </div>

        {mode === "focus" ? (
          <p className="mt-2 text-xs text-slate-500">
            {t("feed.status.focusGoal", "Focus 目标")}：
            {goalText || t("feed.status.focusGoalUnset", "未设置（可去 Focus 页面输入）")}
          </p>
        ) : null}
        {loading ? (
          <p className="mt-2 text-xs text-slate-500">
            {t("feed.status.refreshing", "正在刷新 Feed...")}
          </p>
        ) : null}
        {message ? <p className="mt-2 text-xs text-slate-500">{message}</p> : null}
      </div>
      <FeedDeck items={items} />
    </>
  );
}
