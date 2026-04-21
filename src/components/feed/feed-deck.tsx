"use client";

import Link from "next/link";
import { useState } from "react";
import { submitFeedback } from "@/lib/api";
import type { FeedItem } from "@/lib/mock-data";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";

interface FeedDeckProps {
  items: FeedItem[];
}

interface ItemActionState {
  liked: boolean;
  ignored: boolean;
  saved: boolean;
}

type ActionName = keyof ItemActionState;

function scoreClass(score: number): string {
  if (score >= 85) return "text-emerald-700 bg-emerald-50/80 border-emerald-200/80";
  if (score >= 60) return "text-amber-700 bg-amber-50/80 border-amber-200/80";
  return "text-slate-600 bg-slate-100/80 border-slate-200/80";
}

function actionChipClass(action: FeedItem["suggestedActionType"] | undefined): string {
  if (action === "deep_read") return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (action === "later") return "border-amber-200 bg-amber-50 text-amber-700";
  return "border-slate-200 bg-slate-100 text-slate-600";
}

export function FeedDeck({ items }: FeedDeckProps) {
  const { preferences, t } = useAppPreferences();
  const [index, setIndex] = useState(0);
  const [apiMessage, setApiMessage] = useState("");
  const [states, setStates] = useState<Record<string, ItemActionState>>({});

  if (items.length === 0) {
    return (
      <div className="af-glass rounded-3xl p-8 text-sm text-slate-600">
        {t("feed.deck.noData", "暂无数据。")}
      </div>
    );
  }

  const safeIndex = Math.min(index, Math.max(0, items.length - 1));
  const current = items[safeIndex];
  const currentState = states[current.id] || {
    liked: false,
    ignored: false,
    saved: false,
  };
  const createdAtLabel = current.createdAt
    ? new Date(current.createdAt).toLocaleString(preferences.language, { hour12: false })
    : t("feed.deck.timeUnknown", "未知");

  const scoreLabel = (score: number): string => {
    if (score >= 85) return t("feed.deck.score.high", "高价值");
    if (score >= 60) return t("feed.deck.score.mid", "中价值");
    return t("feed.deck.score.low", "低价值");
  };

  const actionLabel =
    current.suggestedActionType === "deep_read"
      ? t("action.deep_read", "立即深读")
      : current.suggestedActionType === "later"
        ? t("action.later", "稍后精读")
        : t("action.skip", "可放心忽略");

  const toggleAction = (action: ActionName) => {
    setStates((prev) => {
      const prevState = prev[current.id] || {
        liked: false,
        ignored: false,
        saved: false,
      };
      const nextState: ItemActionState = {
        ...prevState,
        [action]: !prevState[action],
      };

      if (action === "liked" && nextState.liked) {
        nextState.ignored = false;
      }

      if (action === "ignored" && nextState.ignored) {
        nextState.liked = false;
      }

      return {
        ...prev,
        [current.id]: nextState,
      };
    });
  };

  const sendFeedback = async (
    feedbackType: "like" | "ignore" | "save" | "open_detail",
  ) => {
    try {
      await submitFeedback(current.id, feedbackType);
      setApiMessage(`${t("action.feedbackSynced", "已同步反馈")}：${feedbackType}`);
    } catch {
      setApiMessage(
        t("action.feedbackLocalOnly", "本地已记录，API 未连接（可稍后重试）"),
      );
    }
  };

  return (
    <div className="space-y-4">
      <div className="af-glass flex items-center justify-between rounded-2xl px-4 py-3 text-sm text-slate-500">
        <p>
          {t("feed.deck.cardProgress", "卡片")} {safeIndex + 1} / {items.length}
        </p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setIndex((prev) => Math.max(0, prev - 1))}
            disabled={safeIndex === 0}
            className="af-btn af-btn-secondary rounded-full px-3 py-1.5 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("feed.deck.prev", "上一条")}
          </button>
          <button
            type="button"
            onClick={() =>
              setIndex((prev) => Math.min(items.length - 1, prev + 1))
            }
            disabled={safeIndex === items.length - 1}
            className="af-btn af-btn-secondary rounded-full px-3 py-1.5 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("feed.deck.next", "下一条")}
          </button>
        </div>
      </div>

      <article className="af-glass w-full rounded-[32px] p-6 md:p-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span className="rounded-full border border-slate-200 bg-white/80 px-2.5 py-1">
              {t("feed.deck.source", "来源")}：{current.source}
            </span>
            <span className="rounded-full border border-slate-200 bg-white/80 px-2.5 py-1">
              {t("feed.deck.ingestedAt", "入库")}：{createdAtLabel}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full border px-3 py-1 text-sm font-semibold ${scoreClass(
                current.valueScore,
              )}`}
            >
              {t("feed.deck.value", "价值")} · {scoreLabel(current.valueScore)}
            </span>
            <span
              className={`rounded-full border px-3 py-1 text-sm font-semibold ${actionChipClass(
                current.suggestedActionType,
              )}`}
            >
              {actionLabel}
            </span>
          </div>
        </div>

        <h2 className="mt-4 text-[2rem] font-semibold leading-[1.2] tracking-[-0.03em] text-slate-900 md:text-[2.4rem]">
          {current.title}
        </h2>

        <section className="af-glass af-hero-surface mt-5 rounded-3xl border border-white/75 px-5 py-4 shadow-[0_24px_40px_-30px_rgba(67,108,184,0.22)]">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-sky-700/75">
            {t("feed.deck.oneLineSummary", "一句话概要")}
          </p>
          <p className="mt-2 text-base font-medium leading-7 text-slate-800 md:text-lg">
            {current.shortSummary}
          </p>
        </section>

        <section className="mt-4">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
            {t("feed.deck.keywords", "关键词")}
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {(current.tags.length
              ? current.tags
              : [t("feed.deck.tagsPending", "待补充标签")]).map((tag) => (
              <span key={tag} className="af-pill text-[12px]">
                {tag}
              </span>
            ))}
          </div>
        </section>

        <div className="mt-5 grid gap-4 md:grid-cols-[1.3fr_1fr]">
          <section className="rounded-3xl border border-white/70 bg-white/70 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
              {t("feed.deck.summary3line", "3 行摘要")}
            </p>
            <p className="mt-2 text-sm leading-7 text-slate-700 [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:3] overflow-hidden md:text-[15px]">
              {current.summary}
            </p>
          </section>

          <section className="rounded-3xl border border-white/70 bg-white/70 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
              {t("feed.deck.reasons", "推荐理由")}
            </p>
            <ul className="mt-2 space-y-1.5 text-sm text-slate-700">
              {(current.whyRecommended?.length
                ? current.whyRecommended.slice(0, 3)
                : current.recommendationReasons?.length
                  ? current.recommendationReasons.slice(0, 3)
                  : [t("feed.deck.reasonEmpty", "暂无解释，建议先看详情页")]).map((reason) => (
                <li key={reason} className="line-clamp-1">
                  {reason}
                </li>
              ))}
            </ul>
            {current.matchedPreferences?.length ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {current.matchedPreferences.slice(0, 4).map((reason) => (
                  <span
                    key={reason}
                    className="rounded-full border border-sky-200/80 bg-sky-50/80 px-2.5 py-1 text-[11px] font-medium text-sky-700"
                  >
                    {reason}
                  </span>
                ))}
              </div>
            ) : null}
            {(current.topicMatchScore !== undefined || current.sourceMatchScore !== undefined) ? (
              <p className="mt-3 text-xs text-slate-500">
                {t("feed.deck.preferenceScore", "偏好命中")} · Topic {Math.round(current.topicMatchScore ?? 0)} / Source{" "}
                {Math.round(current.sourceMatchScore ?? 0)}
              </p>
            ) : null}
          </section>
        </div>

        <p className="mt-4 line-clamp-1 text-xs text-slate-500">
          {t("feed.deck.originalLink", "原文链接")}：{current.url}
        </p>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => {
              toggleAction("liked");
              void sendFeedback("like");
            }}
            className={`af-btn rounded-full px-4 py-2 text-sm ${
              currentState.liked
                ? "bg-emerald-600 text-white shadow-[0_16px_24px_-18px_rgba(5,150,105,0.9)]"
                : "af-btn-primary"
            }`}
          >
            {currentState.liked
              ? t("action.likeDone", "已 Like")
              : t("action.like", "Like")}
          </button>
          <button
            type="button"
            onClick={() => {
              toggleAction("ignored");
              void sendFeedback("ignore");
            }}
            className={`af-btn rounded-full px-4 py-2 text-sm ${
              currentState.ignored
                ? "border border-slate-300 bg-slate-200 text-slate-700"
                : "af-btn-secondary"
            }`}
          >
            {currentState.ignored
              ? t("action.ignoreDone", "已 Ignore")
              : t("action.ignore", "Ignore")}
          </button>
          <button
            type="button"
            onClick={() => {
              toggleAction("saved");
              void sendFeedback("save");
            }}
            className={`af-btn rounded-full border px-4 py-2 text-sm ${
              currentState.saved
                ? "border-blue-300 bg-blue-50 text-blue-700 shadow-[0_16px_24px_-18px_rgba(37,99,235,0.8)]"
                : "af-btn-secondary"
            }`}
          >
            {currentState.saved
              ? t("action.saveDone", "已 Save")
              : t("action.save", "Save")}
          </button>
          <Link
            href={`/items/${current.id}`}
            onClick={() => {
              void sendFeedback("open_detail");
            }}
            className="af-btn af-btn-primary rounded-full border px-4 py-2 text-sm"
          >
            {t("action.openDetail", "Open Detail")}
          </Link>
        </div>

        {apiMessage ? (
          <p className="mt-3 text-xs text-slate-500">{apiMessage}</p>
        ) : null}
      </article>
    </div>
  );
}
