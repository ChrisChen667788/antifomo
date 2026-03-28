"use client";

import Link from "next/link";
import { useState } from "react";
import { reprocessItem, submitFeedback } from "@/lib/api";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { AppIcon } from "@/components/ui/app-icon";

interface ItemDetailActionsProps {
  itemId: string;
  sourceUrl: string;
}

type ReprocessState = "idle" | "processing" | "done";

function buildArchiveHitMessage(params: {
  language: string;
  trigger: "like" | "save";
  status: "created" | "existing";
  threshold?: number | null;
  score?: number | null;
  likeLabel: string;
  saveLabel: string;
}) {
  const actionLabel = params.trigger === "save" ? params.saveLabel : params.likeLabel;
  const thresholdLabel =
    typeof params.threshold === "number"
      ? params.threshold >= 4
        ? "高价值"
        : params.threshold >= 2.8
          ? "中价值"
          : "低价值"
      : "目标价值";

  if (params.language === "en") {
    return params.status === "existing"
      ? `Already archived: matched the ${thresholdLabel} auto-archive rule, triggered by ${actionLabel}.`
      : `Auto archived: matched the ${thresholdLabel} auto-archive rule, triggered by ${actionLabel}.`;
  }
  if (params.language === "ja") {
    return params.status === "existing"
      ? `既にナレッジ化済み：${thresholdLabel} ルールに一致し、操作は ${actionLabel}。`
      : `自動でナレッジ化：${thresholdLabel} ルールに一致し、操作は ${actionLabel}。`;
  }
  if (params.language === "ko") {
    return params.status === "existing"
      ? `이미 지식베이스에 있습니다: ${thresholdLabel} 규칙을 충족했고 동작은 ${actionLabel}입니다.`
      : `자동 보관됨: ${thresholdLabel} 규칙을 충족했고 동작은 ${actionLabel}입니다.`;
  }
  if (params.language === "zh-TW") {
    return params.status === "existing"
      ? `已命中自動歸檔規則：符合「${thresholdLabel}」門檻，且已標記「${actionLabel}」。`
      : `已自動歸檔：符合「${thresholdLabel}」門檻，且已標記「${actionLabel}」。`;
  }
  return params.status === "existing"
    ? `已命中自动归档规则：符合“${thresholdLabel}”门槛，且已标记“${actionLabel}”。`
    : `已自动归档：符合“${thresholdLabel}”门槛，且已标记“${actionLabel}”。`;
}

export function ItemDetailActions({ itemId, sourceUrl }: ItemDetailActionsProps) {
  const { t, preferences } = useAppPreferences();
  const [liked, setLiked] = useState(false);
  const [ignored, setIgnored] = useState(false);
  const [saved, setSaved] = useState(false);
  const [knowledgeEntryId, setKnowledgeEntryId] = useState("");
  const [reprocessState, setReprocessState] = useState<ReprocessState>("idle");
  const [apiMessage, setApiMessage] = useState("");

  const sendFeedback = async (
    feedbackType: "like" | "ignore" | "save" | "inaccurate",
  ) => {
    try {
      const result = await submitFeedback(itemId, feedbackType);
      if (result.knowledge_entry_id) {
        setKnowledgeEntryId(result.knowledge_entry_id);
      }
      if (result.knowledge_status === "created") {
        setApiMessage(
          buildArchiveHitMessage({
            language: preferences.language,
            trigger: (result.knowledge_trigger || feedbackType) as "like" | "save",
            status: "created",
            threshold: result.knowledge_threshold,
            score: result.knowledge_score_value,
            likeLabel: t("action.like", "感兴趣"),
            saveLabel: t("action.save", "稍后再读"),
          }),
        );
        return;
      }
      if (result.knowledge_status === "existing") {
        setApiMessage(
          buildArchiveHitMessage({
            language: preferences.language,
            trigger: (result.knowledge_trigger || feedbackType) as "like" | "save",
            status: "existing",
            threshold: result.knowledge_threshold,
            score: result.knowledge_score_value,
            likeLabel: t("action.like", "感兴趣"),
            saveLabel: t("action.save", "稍后再读"),
          }),
        );
        return;
      }
      setApiMessage(`${t("action.feedbackSynced", "已同步反馈")}：${feedbackType}`);
    } catch {
      setApiMessage(
        t("action.feedbackLocalOnly", "本地已记录，API 未连接（可稍后重试）"),
      );
    }
  };

  const triggerReprocess = async () => {
    setReprocessState("processing");
    try {
      await reprocessItem(itemId, { output_language: preferences.language });
      setApiMessage(t("action.reprocessSubmitted", "已提交重新处理任务"));
    } catch {
      setApiMessage(t("action.feedbackLocalOnly", "本地已记录，API 未连接（可稍后重试）"));
    }
    window.setTimeout(() => {
      setReprocessState("done");
    }, 1500);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => {
            setLiked((prev) => !prev);
            if (!liked) setIgnored(false);
            void sendFeedback("like");
          }}
          className={`af-btn px-4 py-2 ${
            liked
              ? "bg-emerald-600 text-white shadow-[0_16px_24px_-18px_rgba(5,150,105,0.9)]"
              : "af-btn-primary"
          }`}
        >
          <AppIcon name="thumb" className="h-4 w-4" />
          {liked ? t("action.likeDone", "已 Like") : t("action.like", "Like")}
        </button>
        <button
          type="button"
          onClick={() => {
            setIgnored((prev) => !prev);
            if (!ignored) setLiked(false);
            void sendFeedback("ignore");
          }}
          className={`af-btn px-4 py-2 ${
            ignored
              ? "border border-slate-300 bg-slate-200 text-slate-700"
              : "af-btn-secondary"
          }`}
        >
          <AppIcon name="ignore" className="h-4 w-4" />
          {ignored ? t("action.ignoreDone", "已 Ignore") : t("action.ignore", "Ignore")}
        </button>
        <button
          type="button"
          onClick={() => {
            setSaved((prev) => !prev);
            void sendFeedback("save");
          }}
          className={`af-btn border px-4 py-2 ${
            saved
              ? "border-blue-300 bg-blue-50 text-blue-700"
              : "af-btn-secondary"
          }`}
        >
          <AppIcon name="bookmark" className="h-4 w-4" />
          {saved ? t("action.saveDone", "已 Save") : t("action.save", "Save")}
        </button>
        <a
          href={sourceUrl}
          target="_blank"
          rel="noreferrer"
          className="af-btn af-btn-secondary border px-4 py-2"
        >
          <AppIcon name="external" className="h-4 w-4" />
          {t("item.openSource", "打开原文")}
        </a>
      </div>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => {
            void triggerReprocess();
          }}
          disabled={reprocessState === "processing"}
          className="af-btn af-btn-secondary border px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <AppIcon name="refresh" className="h-4 w-4" />
          {reprocessState === "processing"
            ? t("action.reprocessing", "重新处理中...")
            : t("action.reprocess", "重新处理")}
        </button>

        {reprocessState === "done" ? (
          <span className="text-sm text-emerald-700">
            {t("action.reprocessDone", "已更新摘要与建议动作")}
          </span>
        ) : null}
      </div>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => {
            void sendFeedback("inaccurate");
          }}
          className="af-btn af-btn-secondary border px-4 py-2"
        >
          <AppIcon name="flag" className="h-4 w-4" />
          {t("action.markInaccurate", "标记摘要不准")}
        </button>
        {knowledgeEntryId ? (
          <Link href={`/knowledge/${knowledgeEntryId}`} className="af-btn af-btn-secondary border px-4 py-2">
            <AppIcon name="knowledge" className="h-4 w-4" />
            {t("item.openKnowledge", "查看知识卡片")}
          </Link>
        ) : null}
        {apiMessage ? <span className="text-sm text-slate-500">{apiMessage}</span> : null}
      </div>
    </div>
  );
}
