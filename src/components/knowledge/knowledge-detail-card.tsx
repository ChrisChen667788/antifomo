"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { ApiKnowledgeEntry, ApiResearchActionCard, ApiResearchReport } from "@/lib/api";
import {
  createResearchActionPlan,
  createTask,
  getKnowledgeMarkdown,
  listRelatedKnowledgeEntries,
  saveResearchActionCards,
  sendWorkBuddyWebhook,
  updateKnowledgeEntry,
} from "@/lib/api";
import { ResearchActionCardsPanel } from "@/components/research/research-action-cards-panel";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { AppIcon } from "@/components/ui/app-icon";
import { WorkBuddyMark } from "@/components/ui/workbuddy-mark";
import { normalizeResearchActionCards } from "@/lib/research-action-cards";

export function KnowledgeDetailCard({ item }: { item: ApiKnowledgeEntry }) {
  const { t } = useAppPreferences();
  const pendingRankedEntities = (
    report: ApiResearchReport,
    role: "target" | "competitor" | "partner",
  ) => {
    if (role === "target") return report.pending_target_candidates || [];
    if (role === "competitor") return report.pending_competitor_candidates || [];
    return report.pending_partner_candidates || [];
  };
  const classifySourceTier = (source: ApiResearchReport["sources"][number]) => {
    const domain = String(source.domain || "").toLowerCase();
    const sourceType = String(source.source_type || "").toLowerCase();
    const sourceTier = String(source.source_tier || "").toLowerCase();
    if (sourceTier === "official" || sourceTier === "media" || sourceTier === "aggregate") {
      return sourceTier;
    }
    if (
      sourceType === "policy" ||
      sourceType === "procurement" ||
      sourceType === "filing" ||
      domain.endsWith(".gov.cn") ||
      domain.includes("gov.cn") ||
      domain.includes("ggzy.gov.cn") ||
      domain.includes("cninfo.com.cn") ||
      domain.includes("sec.gov") ||
      domain.includes("hkexnews.hk")
    ) {
      return "official";
    }
    if (
      sourceType === "tender_feed" ||
      domain.includes("jianyu") ||
      domain.includes("cecbid") ||
      domain.includes("cebpubservice") ||
      domain.includes("china-cpp") ||
      domain.includes("chinabidding")
    ) {
      return "aggregate";
    }
    return "media";
  };
  const qualityTone = (value: string) => {
    if (value === "high") return "bg-emerald-100 text-emerald-700";
    if (value === "medium") return "bg-amber-100 text-amber-700";
    return "bg-slate-100 text-slate-500";
  };
  const qualityLabel = (value: string) => {
    if (value === "high") return "高";
    if (value === "medium") return "中";
    return "低";
  };
  const evidenceModeMeta = (value: string) => {
    if (value === "strong") {
      return {
        label: t("research.evidenceStrong", "强证据"),
        className: "border-emerald-200/90 bg-emerald-50 text-emerald-800",
        note: t("research.evidenceStrongNote", "当前结果有较稳定的主题命中、官方源和多域名交叉支撑。"),
      };
    }
    if (value === "provisional") {
      return {
        label: t("research.evidenceProvisional", "可用初版"),
        className: "border-amber-200/90 bg-amber-50 text-amber-800",
        note: t("research.evidenceProvisionalNote", "当前已有可用线索，但仍建议继续补官方源或专项交叉验证。"),
      };
    }
    return {
      label: t("research.evidenceFallback", "兜底候选"),
      className: "border-slate-200/90 bg-slate-100 text-slate-700",
      note: t("research.evidenceFallbackNote", "当前更像高价值候选，不应直接视为最终结论。"),
    };
  };
  const valueBucket = (score: number) => {
    if (score >= 75) return { label: t("summary.score.high", "高价值"), className: "bg-emerald-100 text-emerald-700" };
    if (score >= 55) return { label: t("summary.score.medium", "普通价值"), className: "bg-amber-100 text-amber-700" };
    return { label: t("summary.score.low", "低价值"), className: "bg-slate-100 text-slate-500" };
  };
  const factorBucket = (score: number) => {
    if (score >= 14) return { label: "强支撑", className: "bg-emerald-100 text-emerald-700" };
    if (score >= 6) return { label: "中支撑", className: "bg-amber-100 text-amber-700" };
    if (score > 0) return { label: "弱支撑", className: "bg-sky-100 text-sky-700" };
    if (score < 0) return { label: "风险提示", className: "bg-rose-100 text-rose-700" };
    return { label: "待补证据", className: "bg-slate-100 text-slate-500" };
  };
  const [entry, setEntry] = useState(item);
  const [editing, setEditing] = useState(false);
  const [draftTitle, setDraftTitle] = useState(item.title);
  const [draftContent, setDraftContent] = useState(item.content);
  const [draftCollection, setDraftCollection] = useState(item.collection_name || "");
  const [saving, setSaving] = useState(false);
  const [pinning, setPinning] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [workBuddyExporting, setWorkBuddyExporting] = useState(false);
  const [message, setMessage] = useState("");
  const [relatedEntries, setRelatedEntries] = useState<ApiKnowledgeEntry[]>([]);
  const [researchActionCards, setResearchActionCards] = useState<ApiResearchActionCard[]>([]);
  const [planningResearchActions, setPlanningResearchActions] = useState(false);
  const [savingResearchActions, setSavingResearchActions] = useState(false);
  const uiResearchActionCards = useMemo(
    () => normalizeResearchActionCards(researchActionCards, t),
    [researchActionCards, t],
  );

  const researchReport = useMemo(() => {
    const payload = entry.metadata_payload;
    if (!payload || typeof payload !== "object") return null;
    const typedPayload = payload as { kind?: string; report?: ApiResearchReport };
    if (typedPayload.kind !== "research_report" || !typedPayload.report) return null;
    return typedPayload.report;
  }, [entry.metadata_payload]);
  const groupedResearchSources = useMemo(() => {
    if (!researchReport) {
      return [];
    }
    const groups = [
      { key: "official", title: t("research.sourceOfficial", "官方源"), items: researchReport.sources.filter((source) => classifySourceTier(source) === "official") },
      { key: "media", title: t("research.sourceMedia", "媒体源"), items: researchReport.sources.filter((source) => classifySourceTier(source) === "media") },
      { key: "aggregate", title: t("research.sourceAggregate", "聚合源"), items: researchReport.sources.filter((source) => classifySourceTier(source) === "aggregate") },
    ];
    return groups.filter((group) => group.items.length);
  }, [researchReport, t]);
  const researchDiagnostics = researchReport?.source_diagnostics;
  const evidenceMode = evidenceModeMeta(researchDiagnostics?.evidence_mode || "fallback");
  const rankedPanels = useMemo(
    () =>
      researchReport
        ? [
            {
              title: researchReport.top_target_accounts?.length
                ? t("research.topTargets", "高价值甲方 Top 3")
                : t("research.pendingTargets", "待补证甲方候选"),
              items: researchReport.top_target_accounts?.length
                ? researchReport.top_target_accounts
                : pendingRankedEntities(researchReport, "target"),
              tone: "sky",
            },
            {
              title: researchReport.top_competitors?.length
                ? t("research.topCompetitors", "高威胁竞品 Top 3")
                : t("research.pendingCompetitors", "待补证竞品候选"),
              items: researchReport.top_competitors?.length
                ? researchReport.top_competitors
                : pendingRankedEntities(researchReport, "competitor"),
              tone: "amber",
            },
            {
              title: researchReport.top_ecosystem_partners?.length
                ? t("research.topPartners", "高影响力生态伙伴 Top 3")
                : t("research.pendingPartners", "待补证生态伙伴候选"),
              items: researchReport.top_ecosystem_partners?.length
                ? researchReport.top_ecosystem_partners
                : pendingRankedEntities(researchReport, "partner"),
              tone: "emerald",
            },
          ].filter((panel) => panel.items.length)
        : [],
    [researchReport, t],
  );
  const sourceTierLabel = (tier: string) => {
    if (tier === "official") return t("research.sourceOfficial", "官方源");
    if (tier === "aggregate") return t("research.sourceAggregate", "聚合源");
    return t("research.sourceMedia", "媒体源");
  };

  const triggerMarkdownDownload = (filename: string, content: string) => {
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  useEffect(() => {
    let active = true;
    void listRelatedKnowledgeEntries(item.id, 4)
      .then((response) => {
        if (!active) return;
        setRelatedEntries(response.items || []);
      })
      .catch(() => {
        if (!active) return;
        setRelatedEntries([]);
      });
    return () => {
      active = false;
    };
  }, [item.id]);

  const markdownContent = useMemo(() => {
    const lines = [
      `# ${entry.title}`,
      "",
      `- ${t("knowledge.source", "来源")}: ${entry.source_domain || t("common.unknownSource", "未知来源")}`,
      `- ${t("knowledge.createdAt", "创建时间")}: ${new Date(entry.created_at).toLocaleString()}`,
    ];
    if (entry.updated_at) {
      lines.push(`- ${t("knowledge.updatedAt", "最近更新")}: ${new Date(entry.updated_at).toLocaleString()}`);
    }
    if (entry.collection_name) {
      lines.push(`- ${t("knowledge.group", "分组")}: ${entry.collection_name}`);
    }
    lines.push(`- ${t("knowledge.pinned", "置顶")}: ${entry.is_pinned ? t("common.yes", "是") : t("common.no", "否")}`);
    lines.push("", "## " + t("knowledge.content", "卡片内容"), "", entry.content);
    return lines.join("\n");
  }, [entry, t]);

  const handlePlanResearchActions = async () => {
    if (!researchReport) return;
    setPlanningResearchActions(true);
    setMessage("");
    try {
      const result = await createResearchActionPlan({ report: researchReport });
      setResearchActionCards(result.cards || []);
      setMessage(
        result.cards?.length
          ? t("research.actionsPlanned", "已生成研报行动卡")
          : t("research.actionsEmpty", "当前研报暂未生成可执行行动卡"),
      );
    } catch {
      setMessage(t("research.actionsPlanFailed", "生成行动卡失败，请稍后重试"));
    } finally {
      setPlanningResearchActions(false);
    }
  };

  const handleSaveResearchActions = async (asFocusReference = false) => {
    if (!researchReport || researchActionCards.length === 0) return;
    setSavingResearchActions(true);
    setMessage("");
    try {
      const result = await saveResearchActionCards({
        keyword: researchReport.keyword,
        cards: researchActionCards,
        collection_name: `${researchReport.keyword} 行动卡`,
        is_focus_reference: asFocusReference,
      });
      setMessage(
        asFocusReference
          ? t("research.actionsSavedToFocus", "行动卡已加入 Focus 参考")
          : t("research.actionsSaved", `已保存 ${result.created_count} 张行动卡`),
      );
    } catch {
      setMessage(t("research.actionsSaveFailed", "保存行动卡失败，请稍后重试"));
    } finally {
      setSavingResearchActions(false);
    }
  };

  const handleCopyMarkdown = async () => {
    setMessage("");
    try {
      await navigator.clipboard.writeText(markdownContent);
      setMessage(t("knowledge.copyMarkdownDone", "Markdown 已复制"));
    } catch {
      setMessage(t("knowledge.copyMarkdownFailed", "复制失败，请稍后重试"));
    }
  };

  const handleSave = async () => {
    if (!draftTitle.trim() || !draftContent.trim()) return;
    setSaving(true);
    setMessage("");
    try {
      const updated = await updateKnowledgeEntry(entry.id, {
        title: draftTitle.trim(),
        content: draftContent.trim(),
        collection_name: draftCollection.trim() || null,
      });
      setEntry(updated);
      setDraftTitle(updated.title);
      setDraftContent(updated.content);
      setDraftCollection(updated.collection_name || "");
      setEditing(false);
      setMessage(t("knowledge.editSaved", "知识卡片已保存"));
    } catch {
      setMessage(t("knowledge.editSaveFailed", "保存失败，请稍后重试"));
    } finally {
      setSaving(false);
    }
  };

  const handleTogglePinned = async () => {
    setPinning(true);
    setMessage("");
    try {
      const updated = await updateKnowledgeEntry(entry.id, {
        is_pinned: !entry.is_pinned,
      });
      setEntry(updated);
      setDraftCollection(updated.collection_name || "");
      setMessage(
        updated.is_pinned
          ? t("knowledge.pinEnabled", "已置顶这张知识卡片")
          : t("knowledge.pinDisabled", "已取消置顶"),
      );
    } catch {
      setMessage(t("knowledge.pinFailed", "置顶更新失败，请稍后重试"));
    } finally {
      setPinning(false);
    }
  };

  const handleDownloadMarkdown = async () => {
    setExporting(true);
    setMessage("");
    try {
      const result = await getKnowledgeMarkdown(entry.id);
      triggerMarkdownDownload(result.filename, result.content);
      setMessage(t("knowledge.downloadDone", "Markdown 文件已下载"));
    } catch {
      triggerMarkdownDownload(`${entry.title || "knowledge-card"}.md`, markdownContent);
      setMessage(t("knowledge.downloadFallback", "已使用本地内容导出 Markdown"));
    } finally {
      setExporting(false);
    }
  };

  const handleWorkBuddyExport = async () => {
    setWorkBuddyExporting(true);
    setMessage("");
    try {
      const response = await sendWorkBuddyWebhook({
        event_type: "create_task",
        request_id: `knowledge_${entry.id}`,
        task_type: "export_knowledge_markdown",
        input_payload: {
          entry_id: entry.id,
        },
      });
      const content = response.task?.output_payload?.content;
      const filename =
        typeof response.task?.output_payload?.filename === "string"
          ? response.task.output_payload.filename
          : `${entry.title || "knowledge-card"}.md`;
      if (content) {
        triggerMarkdownDownload(filename, content);
      }
      setMessage(t("knowledge.workbuddyDone", "已通过 WorkBuddy 导出 Markdown"));
    } catch {
      try {
        const task = await createTask({
          task_type: "export_knowledge_markdown",
          input_payload: {
            entry_id: entry.id,
          },
        });
        const content = String(task.output_payload?.content || markdownContent);
        const filename =
          typeof task.output_payload?.filename === "string"
            ? task.output_payload.filename
            : `${entry.title || "knowledge-card"}.md`;
        triggerMarkdownDownload(filename, content);
        setMessage(t("knowledge.workbuddyFallback", "WorkBuddy 不可用，已回退直连导出"));
      } catch {
        setMessage(t("knowledge.workbuddyFailed", "导出失败，请稍后重试"));
      }
    } finally {
      setWorkBuddyExporting(false);
    }
  };

  return (
    <div className="space-y-5">
      <section className="af-glass rounded-[30px] p-5 md:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="af-kicker">{t("knowledge.title", "知识卡片")}</p>
            {editing ? (
              <input
                value={draftTitle}
                onChange={(event) => setDraftTitle(event.target.value)}
                className="af-input mt-2 w-full bg-white/80 text-lg font-semibold text-slate-900"
              />
            ) : (
              <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-slate-900">
                {entry.title}
              </h2>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              {entry.is_pinned ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-sky-100 px-2.5 py-1 text-xs text-sky-700">
                  <AppIcon name="flag" className="h-3.5 w-3.5" />
                  {t("knowledge.pinned", "置顶")}
                </span>
              ) : null}
              {entry.collection_name ? (
                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                  {entry.collection_name}
                </span>
              ) : null}
            </div>
            <p className="mt-3 text-sm text-slate-500">
              {t("knowledge.source", "来源")}：{entry.source_domain || t("common.unknownSource", "未知来源")}
            </p>
            <p className="mt-1 text-xs text-slate-400">
              {t("knowledge.createdAt", "创建时间")}：{new Date(entry.created_at).toLocaleString()}
            </p>
            {entry.updated_at ? (
              <p className="mt-1 text-xs text-slate-400">
                {t("knowledge.updatedAt", "最近更新")}：{new Date(entry.updated_at).toLocaleString()}
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => {
                void handleTogglePinned();
              }}
              disabled={pinning}
              className={`af-btn border px-4 py-2 ${entry.is_pinned ? "af-btn-primary" : "af-btn-secondary"} disabled:cursor-not-allowed disabled:opacity-60`}
            >
              <AppIcon name="flag" className="h-4 w-4" />
              {entry.is_pinned ? t("knowledge.unpin", "取消置顶") : t("knowledge.pin", "置顶")}
            </button>
            <button
              type="button"
              onClick={() => {
                void handleCopyMarkdown();
              }}
              className="af-btn af-btn-secondary border px-4 py-2"
            >
              <AppIcon name="copy" className="h-4 w-4" />
              {t("knowledge.copyMarkdown", "复制 Markdown")}
            </button>
            <button
              type="button"
              onClick={() => {
                void handleDownloadMarkdown();
              }}
              disabled={exporting}
              className="af-btn af-btn-secondary border px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <AppIcon name="summary" className="h-4 w-4" />
              {exporting ? t("knowledge.downloading", "导出中...") : t("knowledge.download", "下载 Markdown")}
            </button>
            <button
              type="button"
              onClick={() => {
                void handleWorkBuddyExport();
              }}
              disabled={workBuddyExporting}
              className="af-btn af-btn-secondary border px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <WorkBuddyMark size={14} />
              {workBuddyExporting
                ? t("knowledge.workbuddyExporting", "导出中...")
                : t("knowledge.workbuddyExport", "通过 WorkBuddy 导出")}
            </button>
            <Link href={`/knowledge/${entry.id}/edit`} className="af-btn af-btn-secondary border px-4 py-2">
              <AppIcon name="edit" className="h-4 w-4" />
              {t("knowledge.edit", "编辑")}
            </Link>
            <Link href="/knowledge" className="af-btn af-btn-secondary border px-4 py-2">
              <AppIcon name="knowledge" className="h-4 w-4" />
              {t("item.openKnowledgeList", "知识库列表")}
            </Link>
          </div>
        </div>
      </section>

      <section className="af-glass rounded-[30px] p-5 md:p-6">
        <p className="af-kicker">{t("knowledge.content", "卡片内容")}</p>
        {researchReport ? (
          <div className="mt-3 space-y-4">
            <div className="rounded-2xl border border-sky-100/90 bg-sky-50/75 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-500">
                {t("research.structuredReport", "结构化研报")}
              </p>
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <span className={`rounded-full px-2.5 py-1 ${qualityTone(researchReport.evidence_density)}`}>
                  {t("research.centerEvidenceDensity", "证据密度")}·{qualityLabel(researchReport.evidence_density)}
                </span>
                <span className={`rounded-full px-2.5 py-1 ${qualityTone(researchReport.source_quality)}`}>
                  {t("research.centerSourceQuality", "来源质量")}·{qualityLabel(researchReport.source_quality)}
                </span>
                <span className="rounded-full bg-white/70 px-2.5 py-1 text-slate-500">
                  {t("research.centerCardSources", "来源数")} {researchReport.source_count}
                </span>
              </div>
              {researchDiagnostics ? (
                <div className={`mt-3 rounded-2xl border px-3.5 py-3 ${evidenceMode.className}`}>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-white/80 px-2.5 py-1 text-[11px] font-semibold">
                      {researchDiagnostics.evidence_mode_label || evidenceMode.label}
                    </span>
                    {researchDiagnostics.corrective_triggered ? (
                      <span className="rounded-full bg-white/80 px-2.5 py-1 text-[11px]">
                        {t("research.correctiveTriggered", "已触发纠错检索")}
                      </span>
                    ) : null}
                    {researchDiagnostics.expansion_triggered ? (
                      <span className="rounded-full bg-white/80 px-2.5 py-1 text-[11px]">
                        {t("research.expansionTriggered", "已触发扩搜补证")}
                      </span>
                    ) : null}
                    {researchDiagnostics.candidate_profile_companies?.length ? (
                      <span className="rounded-full bg-white/80 px-2.5 py-1 text-[11px]">
                        {t("research.candidateProfiles", "候选补证公司")} {researchDiagnostics.candidate_profile_companies.length}
                      </span>
                    ) : null}
                    {researchDiagnostics.candidate_profile_hit_count > 0 ? (
                      <span className="rounded-full bg-white/80 px-2.5 py-1 text-[11px]">
                        {t("research.candidateProfileHits", "补证公开源")} {researchDiagnostics.candidate_profile_hit_count}
                      </span>
                    ) : null}
                    {researchDiagnostics.candidate_profile_official_hit_count > 0 ? (
                      <span className="rounded-full bg-white/80 px-2.5 py-1 text-[11px]">
                        {t("research.candidateProfileOfficialHits", "其中官方源")} {researchDiagnostics.candidate_profile_official_hit_count}
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-2 text-xs leading-5">{evidenceMode.note}</p>
                  {researchDiagnostics.candidate_profile_companies?.length ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {researchDiagnostics.candidate_profile_companies.map((value) => (
                        <span key={`candidate-profile-${value}`} className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] text-sky-700">
                          {value}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  {researchDiagnostics.candidate_profile_source_labels?.length ? (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {researchDiagnostics.candidate_profile_source_labels.map((value) => (
                        <span key={`candidate-profile-source-${value}`} className="rounded-full bg-cyan-50 px-2.5 py-1 text-[11px] text-cyan-700">
                          {value}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
              <p className="mt-3 text-sm leading-7 text-slate-700">{researchReport.executive_summary}</p>
              <p className="mt-3 rounded-2xl border border-sky-100/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.86),rgba(238,247,255,0.74))] px-4 py-3 text-sm leading-6 text-sky-900">
                {researchReport.consulting_angle}
              </p>
            </div>

            {(researchReport.five_year_outlook.length || researchReport.competition_analysis.length) ? (
              <div className="grid gap-4 md:grid-cols-2">
                {researchReport.five_year_outlook.length ? (
                  <article className="rounded-2xl border border-sky-100/90 bg-[linear-gradient(180deg,rgba(240,249,255,0.92),rgba(231,245,255,0.76))] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                      {t("research.fiveYearOutlook", "未来五年演化判断")}
                    </p>
                    <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
                      {researchReport.five_year_outlook.map((itemValue) => (
                        <li key={itemValue} className="flex gap-2">
                          <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-sky-300" />
                          <span>{itemValue}</span>
                        </li>
                      ))}
                    </ul>
                  </article>
                ) : null}
                {researchReport.competition_analysis.length ? (
                  <article className="rounded-2xl border border-amber-100/90 bg-[linear-gradient(180deg,rgba(255,251,235,0.94),rgba(255,245,214,0.76))] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                      {t("research.competition", "竞争分析")}
                    </p>
                    <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
                      {researchReport.competition_analysis.map((itemValue) => (
                        <li key={itemValue} className="flex gap-2">
                          <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-amber-300" />
                          <span>{itemValue}</span>
                        </li>
                      ))}
                    </ul>
                  </article>
                ) : null}
              </div>
            ) : null}

            {(researchReport.target_departments?.length || researchReport.public_contact_channels?.length || researchReport.account_team_signals?.length) ? (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {researchReport.target_departments?.length ? (
                  <article className="rounded-2xl border border-slate-200/90 bg-[linear-gradient(180deg,rgba(248,251,255,0.9),rgba(241,245,249,0.72))] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                      {t("research.targetDepartments", "高概率决策部门")}
                    </p>
                    <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
                      {researchReport.target_departments.map((itemValue) => (
                        <li key={itemValue} className="flex gap-2">
                          <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-slate-300" />
                          <span>{itemValue}</span>
                        </li>
                      ))}
                    </ul>
                  </article>
                ) : null}
                {researchReport.public_contact_channels?.length ? (
                  <article className="rounded-2xl border border-emerald-100/90 bg-[linear-gradient(180deg,rgba(236,253,245,0.94),rgba(220,252,231,0.76))] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                      {t("research.publicContacts", "公开业务联系方式")}
                    </p>
                    <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
                      {researchReport.public_contact_channels.map((itemValue) => (
                        <li key={itemValue} className="flex gap-2">
                          <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-slate-300" />
                          <span>{itemValue}</span>
                        </li>
                      ))}
                    </ul>
                  </article>
                ) : null}
                {researchReport.account_team_signals?.length ? (
                  <article className="rounded-2xl border border-sky-100/90 bg-[linear-gradient(180deg,rgba(239,246,255,0.94),rgba(224,242,254,0.76))] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                      {t("research.accountTeams", "目标区域活跃团队")}
                    </p>
                    <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
                      {researchReport.account_team_signals.map((itemValue) => (
                        <li key={itemValue} className="flex gap-2">
                          <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-sky-300" />
                          <span>{itemValue}</span>
                        </li>
                      ))}
                    </ul>
                  </article>
                ) : null}
              </div>
            ) : null}

            {(researchReport.client_peer_moves.length || researchReport.winner_peer_moves.length) ? (
              <div className="grid gap-4 md:grid-cols-2">
                {researchReport.client_peer_moves.length ? (
                  <article className="rounded-2xl border border-slate-200/90 bg-[linear-gradient(180deg,rgba(248,251,255,0.9),rgba(241,245,249,0.72))] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                      {t("research.clientPeers", "甲方同行 Top 3 动态")}
                    </p>
                    <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
                      {researchReport.client_peer_moves.map((itemValue) => (
                        <li key={itemValue} className="flex gap-2">
                          <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-slate-300" />
                          <span>{itemValue}</span>
                        </li>
                      ))}
                    </ul>
                  </article>
                ) : null}
                {researchReport.winner_peer_moves.length ? (
                  <article className="rounded-2xl border border-slate-200/90 bg-[linear-gradient(180deg,rgba(248,251,255,0.9),rgba(241,245,249,0.72))] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                      {t("research.winnerPeers", "中标方同行 Top 3 动态")}
                    </p>
                    <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
                      {researchReport.winner_peer_moves.map((itemValue) => (
                        <li key={itemValue} className="flex gap-2">
                          <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-slate-300" />
                          <span>{itemValue}</span>
                        </li>
                      ))}
                    </ul>
                  </article>
                ) : null}
              </div>
            ) : null}

            {rankedPanels.length ? (
              <div className="grid gap-4 xl:grid-cols-3">
                {rankedPanels.map((panel) => (
                  <article key={panel.title} className="rounded-2xl border border-white/80 bg-[linear-gradient(180deg,rgba(248,251,255,0.9),rgba(241,245,249,0.72))] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{panel.title}</p>
                    <div className="mt-3 space-y-3">
                      {panel.items.map((entity) => (
                        <div key={`${panel.title}-${entity.name}`} className="rounded-2xl border border-white/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.84),rgba(246,249,252,0.72))] p-3">
                          <div className="flex items-center justify-between gap-3">
                            <h4 className="text-sm font-semibold text-slate-900">{entity.name}</h4>
                            <span className={`rounded-full px-2 py-0.5 text-[11px] ${valueBucket(entity.score).className}`}>
                              {valueBucket(entity.score).label}
                            </span>
                          </div>
                          <p className="mt-2 text-sm leading-6 text-slate-600">{entity.reasoning}</p>
                          {entity.score_breakdown?.length ? (
                            <div className="mt-3 grid gap-2">
                              {entity.score_breakdown.slice(0, 3).map((factor) => (
                                <div key={`${entity.name}-${factor.label}`} className="rounded-2xl border border-slate-200/80 bg-slate-50/86 px-3 py-2">
                                  <div className="flex items-center justify-between gap-2">
                                    <span className="text-xs font-medium text-slate-700">{factor.label}</span>
                                    <span className={`rounded-full px-2 py-0.5 text-[10px] ${factorBucket(factor.score).className}`}>
                                      {factorBucket(factor.score).label}
                                    </span>
                                  </div>
                                  {factor.note ? <p className="mt-1 text-[11px] leading-5 text-slate-500">{factor.note}</p> : null}
                                </div>
                              ))}
                            </div>
                          ) : null}
                          {entity.evidence_links?.length ? (
                            <div className="mt-3 space-y-2">
                              {entity.evidence_links.map((link) => (
                                <a
                                  key={`${entity.name}-${link.url}`}
                                  href={link.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="block rounded-2xl border border-slate-200/80 bg-slate-50/82 px-3 py-2 transition hover:border-slate-300 hover:bg-white/82"
                                >
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="text-xs font-medium text-slate-900">{link.title}</span>
                                    <span className="rounded-full bg-sky-50 px-2 py-0.5 text-[10px] text-sky-700">
                                      {sourceTierLabel(link.source_tier || "media")}
                                    </span>
                                    {link.source_label ? (
                                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">
                                        {link.source_label}
                                      </span>
                                    ) : null}
                                  </div>
                                </a>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </article>
                ))}
              </div>
            ) : null}

            {researchReport.sections.length ? (
              <div className="grid gap-4 md:grid-cols-2">
                {researchReport.sections.map((section) => (
                  <article key={section.title} className="rounded-2xl border border-white/80 bg-[linear-gradient(180deg,rgba(248,251,255,0.9),rgba(241,245,249,0.72))] p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                        {section.title}
                      </p>
                      <div className="flex flex-wrap gap-2 text-[11px]">
                        <span className={`rounded-full px-2 py-0.5 ${qualityTone(section.evidence_density || "low")}`}>
                          {t("research.centerEvidenceDensity", "证据密度")}·{qualityLabel(section.evidence_density || "low")}
                        </span>
                        <span className={`rounded-full px-2 py-0.5 ${qualityTone(section.source_quality || "low")}`}>
                          {t("research.centerSourceQuality", "来源质量")}·{qualityLabel(section.source_quality || "low")}
                        </span>
                      </div>
                    </div>
                    <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
                      {section.items.map((itemValue) => (
                        <li key={`${section.title}-${itemValue}`} className="flex gap-2">
                          <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-slate-300" />
                          <span>{itemValue}</span>
                        </li>
                      ))}
                    </ul>
                    {section.evidence_note ? (
                      <p className="mt-3 text-xs leading-5 text-slate-500">{section.evidence_note}</p>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : null}

            {groupedResearchSources.length ? (
              <div className="grid gap-4 md:grid-cols-3">
                {groupedResearchSources.map((group) => (
                  <article key={group.key} className="rounded-2xl border border-white/80 bg-[linear-gradient(180deg,rgba(248,251,255,0.9),rgba(241,245,249,0.72))] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{group.title}</p>
                    <div className="mt-3 space-y-3">
                      {group.items.slice(0, 4).map((source) => (
                        <a
                          key={`${group.key}-${source.url}`}
                          href={source.url}
                          target="_blank"
                          rel="noreferrer"
                          className="block rounded-2xl border border-slate-200/80 bg-slate-50/84 p-3 transition hover:border-slate-300 hover:bg-white/84"
                        >
                          <p className="text-sm font-semibold leading-6 text-slate-900">{source.title}</p>
                          <p className="mt-1 text-xs leading-5 text-slate-500">
                            {[source.source_label, source.domain || "web"].filter(Boolean).join(" · ")}
                          </p>
                        </a>
                      ))}
                    </div>
                  </article>
                ))}
              </div>
            ) : null}

            <ResearchActionCardsPanel
              t={t}
              title={t("research.actionCardsTitle", "把研报拆成可执行建议")}
              subtitle={t("research.actionCardsHint", "将研报中的方案、销售、投标与生态建议拆成可执行卡片。")}
              cards={uiResearchActionCards}
              planning={planningResearchActions}
              saving={savingResearchActions}
              onPlan={() => {
                void handlePlanResearchActions();
              }}
              onSave={() => {
                void handleSaveResearchActions(false);
              }}
              onSaveToFocus={() => {
                void handleSaveResearchActions(true);
              }}
            />
          </div>
        ) : null}
        {editing ? (
          <div className="mt-3 space-y-3">
            <input
              value={draftCollection}
              onChange={(event) => setDraftCollection(event.target.value)}
              placeholder={t("knowledge.groupPlaceholder", "输入分组名称，例如：AI 制药")}
              className="af-input w-full bg-white/80 text-sm text-slate-700"
            />
            <textarea
              value={draftContent}
              onChange={(event) => setDraftContent(event.target.value)}
              rows={12}
              className="af-input w-full bg-white/80 text-sm leading-7 text-slate-700"
            />
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => {
                  void handleSave();
                }}
                disabled={saving || !draftTitle.trim() || !draftContent.trim()}
                className="af-btn af-btn-primary px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <AppIcon name="bookmark" className="h-4 w-4" />
                {saving ? t("common.saving", "保存中...") : t("common.save", "保存")}
              </button>
              {message ? <span className="text-sm text-slate-500">{message}</span> : null}
            </div>
          </div>
        ) : (
          <>
            <p className="mt-3 text-sm leading-7 text-slate-700">{entry.content}</p>
            {message ? <p className="mt-3 text-sm text-slate-500">{message}</p> : null}
          </>
        )}
      </section>

      {relatedEntries.length ? (
        <section className="af-glass rounded-[30px] p-5 md:p-6">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="af-kicker">{t("knowledge.relatedTitle", "关联卡片")}</p>
              <p className="mt-2 text-sm text-slate-500">
                {t("knowledge.relatedSubtitle", "这些卡片和当前主题接近，适合继续串联或合并。")}
              </p>
            </div>
          </div>
          <div className="mt-4 grid gap-3">
            {relatedEntries.map((related) => (
              <Link
                key={related.id}
                href={`/knowledge/${related.id}`}
                className="rounded-[22px] border border-white/70 bg-white/55 px-4 py-4 transition hover:-translate-y-0.5 hover:bg-white/75"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap gap-2">
                      {related.is_pinned ? (
                        <span className="rounded-full bg-sky-100 px-2 py-0.5 text-[11px] text-sky-700">
                          {t("knowledge.pinned", "置顶")}
                        </span>
                      ) : null}
                      {related.collection_name ? (
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">
                          {related.collection_name}
                        </span>
                      ) : null}
                    </div>
                    <h3 className="truncate text-sm font-semibold text-slate-900">{related.title}</h3>
                    <p className="mt-1 text-xs text-slate-500">
                      {related.source_domain || t("common.unknownSource", "未知来源")}
                    </p>
                  </div>
                  <AppIcon name="external" className="mt-0.5 h-4 w-4 text-slate-400" />
                </div>
                <p
                  className="mt-3 text-sm leading-6 text-slate-600"
                  style={{
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                    overflow: "hidden",
                  }}
                >
                  {related.content}
                </p>
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      {entry.item_id ? (
        <section className="af-glass rounded-[30px] p-5 md:p-6">
          <Link href={`/items/${entry.item_id}`} className="af-btn af-btn-primary px-4 py-2">
            <AppIcon name="external" className="h-4 w-4" />
            {t("knowledge.openItem", "打开原内容详情")}
          </Link>
        </section>
      ) : null}
    </div>
  );
}
