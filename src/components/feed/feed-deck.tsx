"use client";

import Link from "next/link";
import { useState, type PointerEvent } from "react";
import { submitFeedback } from "@/lib/api";
import type { FeedItem } from "@/lib/mock-data";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";

interface FeedDeckProps {
  items: FeedItem[];
  onItemTriaged?: (
    itemId: string,
    feedbackType: "like" | "ignore" | "save",
  ) => boolean | void;
}

interface ItemActionState {
  liked: boolean;
  ignored: boolean;
  saved: boolean;
}

type ActionName = keyof ItemActionState;

function scoreClass(score: number): string {
  if (score >= 85) return "af-chip-success";
  if (score >= 60) return "af-chip-warning";
  return "af-chip";
}

function actionChipClass(action: FeedItem["suggestedActionType"] | undefined): string {
  if (action === "deep_read") return "af-chip-success";
  if (action === "later") return "af-chip-warning";
  return "af-chip";
}

function shouldSkipSwipeTarget(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && Boolean(target.closest("a,button,input,label,select,textarea"));
}

function clampDragOffset(value: number): number {
  return Math.max(-96, Math.min(96, value));
}

export function FeedDeck({ items, onItemTriaged }: FeedDeckProps) {
  const { preferences, t } = useAppPreferences();
  const [index, setIndex] = useState(0);
  const [apiMessage, setApiMessage] = useState("");
  const [states, setStates] = useState<Record<string, ItemActionState>>({});
  const [dragStartX, setDragStartX] = useState<number | null>(null);
  const [dragOffset, setDragOffset] = useState(0);

  if (items.length === 0) {
    return (
      <div className="af-glass rounded-lg p-8 text-sm text-[var(--af-text-secondary)]">
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

  const advanceToNext = () => {
    setIndex((prev) => Math.min(items.length - 1, prev + 1));
  };

  const toggleAction = (action: ActionName, itemId = current.id) => {
    setStates((prev) => {
      const prevState = prev[itemId] || {
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
        [itemId]: nextState,
      };
    });
  };

  const sendFeedback = async (
    feedbackType: "like" | "ignore" | "save" | "open_detail",
    itemId = current.id,
  ) => {
    try {
      await submitFeedback(itemId, feedbackType);
      setApiMessage(`${t("action.feedbackSynced", "已同步反馈")}：${feedbackType}`);
    } catch {
      setApiMessage(
        t("action.feedbackLocalOnly", "已在本机记录，稍后会再同步。"),
      );
    }
  };

  const runTriageAction = (
    action: ActionName,
    feedbackType: "like" | "ignore" | "save",
    options: { advance: boolean },
  ) => {
    const itemId = current.id;
    toggleAction(action, itemId);
    void sendFeedback(feedbackType, itemId);
    const parentRemovedItem = onItemTriaged?.(itemId, feedbackType) === true;
    if (options.advance && !parentRemovedItem) {
      advanceToNext();
    }
  };

  const handlePointerDown = (event: PointerEvent<HTMLElement>) => {
    if (shouldSkipSwipeTarget(event.target)) return;
    setDragStartX(event.clientX);
    setDragOffset(0);
    event.currentTarget.setPointerCapture?.(event.pointerId);
  };

  const handlePointerMove = (event: PointerEvent<HTMLElement>) => {
    if (dragStartX === null) return;
    const nextOffset = event.clientX - dragStartX;
    if (Math.abs(nextOffset) > 8) {
      event.preventDefault();
    }
    setDragOffset(clampDragOffset(nextOffset));
  };

  const finishPointerAction = (event: PointerEvent<HTMLElement>) => {
    if (dragStartX === null) return;
    const finalOffset = event.clientX - dragStartX;
    setDragStartX(null);
    setDragOffset(0);
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    if (Math.abs(finalOffset) < 90) return;
    if (finalOffset < 0) {
      runTriageAction("ignored", "ignore", { advance: true });
    } else {
      runTriageAction("saved", "save", { advance: true });
    }
  };

  return (
    <div className="space-y-4">
      <div className="af-glass flex items-center justify-between rounded-lg px-4 py-3 text-sm text-[var(--af-text-secondary)]">
        <p>
          {t("feed.deck.cardProgress", "卡片")} {safeIndex + 1} / {items.length}
        </p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setIndex((prev) => Math.max(0, prev - 1))}
            disabled={safeIndex === 0}
            className="af-btn af-btn-secondary px-3 py-1.5 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("feed.deck.prev", "上一条")}
          </button>
          <button
            type="button"
            onClick={() =>
              setIndex((prev) => Math.min(items.length - 1, prev + 1))
            }
            disabled={safeIndex === items.length - 1}
            className="af-btn af-btn-secondary px-3 py-1.5 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("feed.deck.next", "下一条")}
          </button>
        </div>
      </div>

      <article
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={finishPointerAction}
        onPointerCancel={() => {
          setDragStartX(null);
          setDragOffset(0);
        }}
        style={{
          transform: dragOffset
            ? `translateX(${dragOffset}px) rotate(${dragOffset / 28}deg)`
            : undefined,
          transition: dragStartX === null ? "transform 160ms ease" : undefined,
        }}
        className="af-glass w-full touch-pan-y rounded-lg p-6 md:p-8"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--af-text-tertiary)]">
            <span className="af-chip px-2.5 py-1">
              {t("feed.deck.source", "来源")}：{current.source}
            </span>
            <span className="af-chip px-2.5 py-1">
              {t("feed.deck.ingestedAt", "入库")}：{createdAtLabel}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`af-chip border px-3 py-1 text-sm font-semibold ${scoreClass(
                current.valueScore,
              )}`}
            >
              {t("feed.deck.value", "价值")} · {scoreLabel(current.valueScore)}
            </span>
            <span
              className={`af-chip border px-3 py-1 text-sm font-semibold ${actionChipClass(
                current.suggestedActionType,
              )}`}
            >
              {actionLabel}
            </span>
          </div>
        </div>

        <h2 className="mt-4 break-words text-2xl font-semibold leading-tight tracking-normal text-[var(--af-text-primary)] md:text-3xl">
          {current.title}
        </h2>

        <section className="af-hero-surface mt-5 rounded-lg px-5 py-4">
          <p className="af-kicker">
            {t("feed.deck.oneLineSummary", "一句话概要")}
          </p>
          <p className="mt-2 text-base font-medium leading-7 text-[var(--af-text-primary)] md:text-lg">
            {current.shortSummary}
          </p>
        </section>

        <section className="mt-4">
          <p className="af-kicker">
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

        <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-[1.3fr_1fr]">
          <section className="af-subpanel p-4">
            <p className="af-kicker">
              {t("feed.deck.summary3line", "3 行摘要")}
            </p>
            <p className="mt-2 text-sm leading-7 text-[var(--af-text-secondary)] [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:3] overflow-hidden md:text-[15px]">
              {current.summary}
            </p>
          </section>

          <section className="af-subpanel p-4">
            <p className="af-kicker">
              {t("feed.deck.reasons", "推荐理由")}
            </p>
            <ul className="mt-2 space-y-1.5 text-sm text-[var(--af-text-secondary)]">
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
                    className="af-chip af-chip-info px-2.5 py-1 text-[11px] font-medium"
                  >
                    {reason}
                  </span>
                ))}
              </div>
            ) : null}
            {(current.topicMatchScore !== undefined || current.sourceMatchScore !== undefined) ? (
              <p className="mt-3 text-xs text-[var(--af-text-tertiary)]">
                {t("feed.deck.preferenceScore", "偏好命中")} · Topic {Math.round(current.topicMatchScore ?? 0)} / Source{" "}
                {Math.round(current.sourceMatchScore ?? 0)}
              </p>
            ) : null}
          </section>
        </div>

        <p className="mt-4 line-clamp-1 text-xs text-[var(--af-text-tertiary)]">
          {t("feed.deck.originalLink", "原文链接")}：{current.url}
        </p>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => {
              runTriageAction("liked", "like", { advance: false });
            }}
            className={`af-btn px-4 py-2 text-sm ${
              currentState.liked
                ? "af-chip-success"
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
              runTriageAction("ignored", "ignore", { advance: true });
            }}
            className={`af-btn px-4 py-2 text-sm ${
              currentState.ignored
                ? "af-chip"
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
              runTriageAction("saved", "save", { advance: true });
            }}
            className={`af-btn border px-4 py-2 text-sm ${
              currentState.saved
                ? "af-chip-info"
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
            className="af-btn af-btn-primary border px-4 py-2 text-sm"
          >
            {t("action.openDetail", "Open Detail")}
          </Link>
        </div>

        {apiMessage ? (
          <p className="mt-3 text-xs text-[var(--af-text-tertiary)]">{apiMessage}</p>
        ) : null}
      </article>
    </div>
  );
}
