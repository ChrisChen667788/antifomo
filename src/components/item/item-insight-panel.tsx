"use client";

import Link from "next/link";
import { useState } from "react";
import {
  addItemToKnowledge,
  interpretItem,
  type ApiItemInterpretation,
} from "@/lib/api";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { AppIcon } from "@/components/ui/app-icon";

interface ItemInsightPanelProps {
  itemId: string;
}

export function ItemInsightPanel({ itemId }: ItemInsightPanelProps) {
  const { preferences, t } = useAppPreferences();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [entryId, setEntryId] = useState("");
  const [insight, setInsight] = useState<ApiItemInterpretation | null>(null);

  const handleInterpret = async () => {
    setLoading(true);
    setMessage("");
    try {
      const result = await interpretItem(itemId, {
        output_language: preferences.language,
      });
      setInsight(result);
    } catch {
      setMessage(t("insight.failed", "解读生成失败"));
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!insight) return;
    setSaving(true);
    setMessage("");
    try {
      const result = await addItemToKnowledge(itemId, {
        title: insight.insight_title,
        content: insight.knowledge_note,
        output_language: preferences.language,
      });
      setEntryId(result.entry_id);
      setMessage(t("insight.added", "已加入知识库"));
    } catch {
      setMessage(t("action.feedbackLocalOnly", "本地已记录，API 未连接（可稍后重试）"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="af-glass rounded-[30px] p-5 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="af-kicker">{t("insight.title", "专业解读")}</p>
          <p className="mt-2 max-w-2xl text-sm text-slate-600">
            {t("insight.subtitle", "用更专业、可决策的方式解释这条内容。")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => {
              void handleInterpret();
            }}
            disabled={loading}
            className="af-btn af-btn-primary px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <AppIcon name="spark" className="h-4 w-4" />
            {loading ? t("insight.loading", "正在生成专业解读...") : t("item.interpretButton", "生成专业解读")}
          </button>
          <Link href="/knowledge" className="af-btn af-btn-secondary border px-4 py-2">
            <AppIcon name="knowledge" className="h-4 w-4" />
            {t("item.openKnowledgeList", "知识库列表")}
          </Link>
        </div>
      </div>

      {insight ? (
        <div className="mt-5 space-y-4">
          <div className="rounded-[24px] border border-slate-200/80 bg-white/70 p-4">
            <h3 className="text-lg font-semibold tracking-[-0.02em] text-slate-900">
              {insight.insight_title}
            </h3>
            <p className="mt-3 text-sm leading-7 text-slate-700">{insight.expert_take}</p>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-[24px] border border-slate-200/80 bg-white/70 p-4">
              <p className="af-kicker">{t("insight.keySignals", "关键信号")}</p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
                {insight.key_signals.map((signal) => (
                  <li key={signal}>- {signal}</li>
                ))}
              </ul>
            </div>
            <div className="rounded-[24px] border border-sky-200/80 bg-sky-50/60 p-4">
              <p className="af-kicker">{t("insight.knowledge", "知识库笔记")}</p>
              <p className="mt-3 text-sm leading-7 text-slate-700">{insight.knowledge_note}</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => {
                void handleSave();
              }}
              disabled={saving}
              className="af-btn af-btn-primary px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <AppIcon name="bookmark" className="h-4 w-4" />
              {saving ? t("insight.addKnowledge", "加入知识库") : t("insight.addKnowledge", "加入知识库")}
            </button>
            {entryId ? (
              <Link
                href={`/knowledge/${entryId}`}
                className="af-btn af-btn-secondary border px-4 py-2"
              >
                <AppIcon name="knowledge" className="h-4 w-4" />
                {t("item.openKnowledge", "查看知识卡片")}
              </Link>
            ) : null}
            {message ? <span className="text-sm text-slate-500">{message}</span> : null}
          </div>
        </div>
      ) : message ? (
        <p className="mt-4 text-sm text-slate-500">{message}</p>
      ) : null}
    </section>
  );
}
