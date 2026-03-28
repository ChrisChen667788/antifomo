"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { addItemToKnowledge } from "@/lib/api";
import { ItemDetailActions } from "@/components/item/item-detail-actions";
import { ItemInsightPanel } from "@/components/item/item-insight-panel";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { AppIcon } from "@/components/ui/app-icon";
import {
  buildHighlightKeywords,
  extractKeyParagraphs,
  highlightSegments,
  splitIntoParagraphs,
} from "@/lib/item-content-view";

export interface DetailItemViewModel {
  id: string;
  title: string;
  source: string;
  url: string;
  tags: string[];
  rawContent: string;
  cleanContent: string;
  shortSummary: string;
  longSummary: string;
  suggestedActionType: "deep_read" | "later" | "skip";
  valueScore: number;
  recommendationReasons: string[];
  whyRecommended?: string[];
  matchedPreferences?: string[];
  topicMatchScore?: number;
  sourceMatchScore?: number;
  preferenceVersion?: string;
  diagnostics?: {
    ingestRoute: string;
    contentAcquisitionStatus: string;
    contentAcquisitionNote: string;
    bodySource: string;
    fallbackUsed: boolean;
    attemptCount: number;
    processingStatus: string;
  };
}

type DetailView = "original" | "summary" | "insight";

type ExcerptMessageTone = "success" | "error";

function actionLabel(
  action: "deep_read" | "later" | "skip",
  t: (key: string, fallback?: string) => string,
): string {
  if (action === "deep_read") return t("action.deep_read", "立即深读");
  if (action === "later") return t("action.later", "稍后精读");
  return t("action.skip", "可放心忽略");
}

function buildExcerptTitle(
  itemTitle: string,
  index: number,
  t: (key: string, fallback?: string) => string,
): string {
  return `${itemTitle || t("common.untitled", "未命名内容")} / ${t("item.excerptTitle", "关键摘录")} ${index + 1}`;
}

export function ItemDetailContent({ item }: { item: DetailItemViewModel }) {
  const { t, preferences } = useAppPreferences();
  const [activeView, setActiveView] = useState<DetailView>("summary");
  const [excerptSavingKey, setExcerptSavingKey] = useState("");
  const [excerptMessage, setExcerptMessage] = useState("");
  const [excerptMessageTone, setExcerptMessageTone] = useState<ExcerptMessageTone>("success");
  const [excerptEntryId, setExcerptEntryId] = useState("");
  const originalContent =
    item.cleanContent ||
    item.rawContent ||
    t("item.originalEmpty", "当前还没有可展示的原文，建议重新处理或打开原链接。");
  const originalView = useMemo(() => {
    const keywords = buildHighlightKeywords({
      title: item.title,
      tags: item.tags,
      shortSummary: item.shortSummary,
    });
    const paragraphs = splitIntoParagraphs(originalContent);
    const keyParagraphs = extractKeyParagraphs(originalContent, keywords, 3);
    return {
      keywords,
      keyParagraphs,
      paragraphs,
    };
  }, [item.shortSummary, item.tags, item.title, originalContent]);
  const saveExcerpt = async (paragraph: string, index: number) => {
    setExcerptSavingKey(paragraph);
    setExcerptMessage("");
    try {
      const result = await addItemToKnowledge(item.id, {
        title: buildExcerptTitle(item.title, index, t),
        content: paragraph,
        output_language: preferences.language,
      });
      setExcerptEntryId(result.entry_id);
      setExcerptMessageTone("success");
      setExcerptMessage(t("item.excerptSaved", "该段内容已加入知识库"));
    } catch {
      setExcerptMessageTone("error");
      setExcerptMessage(t("item.excerptSaveFailed", "加入知识库失败，请稍后重试"));
    } finally {
      setExcerptSavingKey("");
    }
  };
  const tabs: Array<{ id: DetailView; label: string; icon: "external" | "summary" | "spark" }> = [
    { id: "original", label: t("item.view.original", "原文"), icon: "external" },
    { id: "summary", label: t("item.view.summary", "摘要"), icon: "summary" },
    { id: "insight", label: t("item.view.insight", "专业解读"), icon: "spark" },
  ];

  return (
    <div className="space-y-5">
      <div className="af-glass rounded-[30px] p-5 md:p-7">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="af-kicker mb-2">{t("item.detailKicker", "Detail View")}</p>
            <h2 className="text-xl font-semibold tracking-[-0.03em] text-slate-900 md:text-2xl">
              {item.title || t("common.untitled", "未命名内容")}
            </h2>
            <p className="mt-2 text-sm text-slate-500">
              {t("item.source", "来源")}：{item.source || t("common.unknownSource", "未知来源")}
            </p>
          </div>
          <Link
            href="/"
            className="af-btn af-btn-secondary self-start px-3 py-1.5 text-sm"
          >
            <AppIcon name="home" className="h-4 w-4" />
            {t("item.backToFeed", "返回 Feed")}
          </Link>
        </div>

        <a
          href={item.url}
          target="_blank"
          rel="noreferrer"
          className="mt-4 inline-flex rounded-full border border-blue-200/80 bg-blue-50/70 px-3 py-1 text-sm font-medium text-blue-700"
        >
          <AppIcon name="external" className="h-4 w-4" />
          {t("item.link", "链接")}：{item.url}
        </a>

        {item.diagnostics ? (
          <div className="mt-4 rounded-[22px] border border-sky-200/80 bg-sky-50/60 px-4 py-3 text-sm text-slate-700">
            <div className="flex flex-wrap gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-sky-700">
              <span>Route · {item.diagnostics.ingestRoute}</span>
              <span>Status · {item.diagnostics.contentAcquisitionStatus}</span>
              <span>Body · {item.diagnostics.bodySource}</span>
              <span>Attempts · {item.diagnostics.attemptCount}</span>
              <span>Processing · {item.diagnostics.processingStatus}</span>
              {item.diagnostics.fallbackUsed ? <span>Fallback Used</span> : null}
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {item.diagnostics.contentAcquisitionNote}
            </p>
          </div>
        ) : null}

        {item.whyRecommended?.length || item.matchedPreferences?.length ? (
          <div className="mt-4 rounded-[22px] border border-emerald-200/80 bg-emerald-50/60 px-4 py-3 text-sm text-slate-700">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-emerald-700">
              {t("item.whyRecommended", "为什么推荐给你")}
            </p>
            <ul className="mt-2 space-y-1.5">
              {(item.whyRecommended?.length
                ? item.whyRecommended.slice(0, 4)
                : item.recommendationReasons.slice(0, 3)
              ).map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
            {item.matchedPreferences?.length ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {item.matchedPreferences.map((entry) => (
                  <span key={entry} className="af-pill border-emerald-200/80 bg-white/85 text-emerald-700">
                    {entry}
                  </span>
                ))}
              </div>
            ) : null}
            {(item.topicMatchScore !== undefined || item.sourceMatchScore !== undefined) ? (
              <p className="mt-3 text-xs text-slate-500">
                Topic {Math.round(item.topicMatchScore ?? 0)} / Source {Math.round(item.sourceMatchScore ?? 0)}
                {item.preferenceVersion ? ` · v${item.preferenceVersion.slice(0, 8)}` : ""}
              </p>
            ) : null}
          </div>
        ) : null}

        <div className="mt-5 flex flex-wrap gap-2">
          {(item.tags.length ? item.tags : [t("feed.deck.tagsPending", "待补充标签")]).map((tag) => (
            <span key={tag} className="af-pill">
              #{tag}
            </span>
          ))}
        </div>

        <p className="mt-4 text-sm text-slate-600">
          {t("item.score", "评分")}：{item.valueScore} / 100
        </p>
      </div>

      <section className="af-glass rounded-[30px] p-4 md:p-5">
        <div className="flex flex-wrap gap-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveView(tab.id)}
              className={`af-btn px-4 py-2 text-sm ${
                activeView === tab.id ? "af-btn-primary" : "af-btn-secondary"
              }`}
            >
              <AppIcon name={tab.icon} className="h-4 w-4" />
              {tab.label}
            </button>
          ))}
        </div>

        <div className={activeView === "original" ? "mt-4 block" : "hidden"}>
          <div className="grid gap-4 lg:grid-cols-[0.88fr_1.12fr]">
            <div className="space-y-4">
              <div className="rounded-[26px] border border-slate-200/80 bg-white/70 p-5">
                <p className="af-kicker">{t("item.highlightKeywords", "原文关键词")}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {(originalView.keywords.length
                    ? originalView.keywords
                    : [t("feed.deck.tagsPending", "待补充标签")]).map((keyword) => (
                    <span key={keyword} className="af-pill border-blue-200/80 bg-blue-50/80 text-blue-700">
                      {keyword}
                    </span>
                  ))}
                </div>
              </div>

              <div className="rounded-[26px] border border-slate-200/80 bg-white/70 p-5">
                <p className="af-kicker">{t("item.keyParagraphs", "关键段落")}</p>
                <p className="mt-3 text-sm leading-6 text-slate-500">
                  {t("item.keyParagraphsHint", "下面这些段落最适合单独沉淀进知识库。")}
                </p>
                <div className="mt-3 space-y-3">
                  {originalView.keyParagraphs.length ? (
                    originalView.keyParagraphs.map((paragraph, index) => (
                    <div key={paragraph} className="rounded-[18px] bg-slate-950/[0.04] p-3">
                      <p className="text-sm leading-7 text-slate-700">
                        {highlightSegments(paragraph, originalView.keywords).map((segment, index) => (
                          <span
                            key={`${paragraph.slice(0, 12)}-${index}`}
                            className={
                              segment.hit
                                ? "rounded bg-blue-100 px-0.5 text-slate-900"
                                : ""
                            }
                          >
                            {segment.text}
                          </span>
                        ))}
                      </p>
                      <div className="mt-3 flex flex-wrap items-center gap-3">
                        <button
                          type="button"
                          onClick={() => {
                            void saveExcerpt(paragraph, index);
                          }}
                          disabled={excerptSavingKey === paragraph}
                          className="af-btn af-btn-secondary border px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          <AppIcon name="bookmark" className="h-4 w-4" />
                          {excerptSavingKey === paragraph
                            ? t("common.saving", "保存中...")
                            : t("item.saveExcerpt", "加入知识库")}
                        </button>
                      </div>
                    </div>
                    ))
                  ) : (
                    <div className="rounded-[18px] border border-dashed border-slate-200 bg-slate-50/70 p-4 text-sm leading-6 text-slate-500">
                      {t("item.keyParagraphsEmpty", "当前没有足够稳定的关键段落，可直接查看原文或重新处理。")}
                    </div>
                  )}
                </div>
                {excerptMessage ? (
                  <div
                    className={`mt-3 flex flex-wrap items-center gap-3 rounded-[18px] border px-4 py-3 text-sm ${
                      excerptMessageTone === "success"
                        ? "border-emerald-200 bg-emerald-50/70 text-emerald-700"
                        : "border-rose-200 bg-rose-50/70 text-rose-700"
                    }`}
                  >
                    <span>{excerptMessage}</span>
                    {excerptEntryId ? (
                      <Link href={`/knowledge/${excerptEntryId}`} className="af-btn af-btn-secondary border px-3 py-1.5 text-sm">
                        <AppIcon name="knowledge" className="h-4 w-4" />
                        {t("item.openKnowledge", "查看知识卡片")}
                      </Link>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </div>

            <div className="rounded-[26px] border border-slate-200/80 bg-white/70 p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="af-kicker">{t("item.originalContent", "原文内容")}</p>
                {item.url && item.url !== "#" ? (
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noreferrer"
                    className="af-btn af-btn-secondary border px-3 py-1.5 text-sm"
                  >
                    <AppIcon name="external" className="h-4 w-4" />
                    {t("item.openSource", "打开原文")}
                  </a>
                ) : null}
              </div>
              <div className="mt-4 max-h-[32rem] space-y-3 overflow-auto rounded-[22px] bg-slate-950/[0.04] p-4">
                {(originalView.paragraphs.length ? originalView.paragraphs : [originalContent]).map((paragraph) => (
                  <p key={paragraph} className="text-sm leading-7 text-slate-700">
                    {highlightSegments(paragraph, originalView.keywords).map((segment, index) => (
                      <span
                        key={`${paragraph.slice(0, 12)}-full-${index}`}
                        className={segment.hit ? "rounded bg-blue-100 px-0.5 text-slate-900" : ""}
                      >
                        {segment.text}
                      </span>
                    ))}
                  </p>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className={activeView === "summary" ? "mt-4 block space-y-4" : "hidden"}>
          <div className="grid gap-4 md:grid-cols-2">
            <section className="rounded-[26px] border border-slate-200/80 bg-white/70 p-5">
              <p className="af-kicker">{t("item.shortSummary", "短摘要")}</p>
              <p className="mt-3 text-sm leading-7 text-slate-700">
                {item.shortSummary || t("common.noShortSummary", "暂无短摘要")}
              </p>
            </section>

            <section className="rounded-[26px] border border-slate-200/80 bg-white/70 p-5">
              <p className="af-kicker">{t("item.suggestedAction", "建议动作")}</p>
              <p className="mt-3 text-lg font-semibold text-slate-900">
                {actionLabel(item.suggestedActionType, t)}
              </p>
            </section>
          </div>

          <section className="rounded-[26px] border border-slate-200/80 bg-white/70 p-5">
            <p className="af-kicker">{t("item.longSummary", "长摘要")}</p>
            <p className="mt-3 text-sm leading-7 text-slate-700">
              {item.longSummary || t("common.noLongSummary", "暂无长摘要")}
            </p>
          </section>

          <section className="rounded-[26px] border border-slate-200/80 bg-white/70 p-5">
            <p className="af-kicker">{t("item.reasons", "推荐理由")}</p>
            <ul className="mt-3 space-y-2 text-sm text-slate-700">
              {(item.recommendationReasons.length
                ? item.recommendationReasons
                : [t("feed.deck.reasonEmpty", "暂无解释，建议先看详情页")]).map((reason) => (
                <li key={reason}>- {reason}</li>
              ))}
            </ul>
          </section>
        </div>

        <div className={activeView === "insight" ? "mt-4 block" : "hidden"}>
          <ItemInsightPanel itemId={item.id} />
        </div>
      </section>

      <section className="af-glass rounded-[30px] p-5 md:p-6">
        <p className="af-kicker">{t("item.userActions", "用户操作")}</p>
        <div className="mt-3">
          <ItemDetailActions itemId={item.id} sourceUrl={item.url} />
        </div>
      </section>
    </div>
  );
}
