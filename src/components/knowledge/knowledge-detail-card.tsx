"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { ApiKnowledgeEntry, ApiResearchActionCard, ApiResearchReport } from "@/lib/api";
import { dedupeByKey, dedupeTextList } from "@/lib/display-list";
import {
  createResearchActionPlan,
  createTask,
  getKnowledgeMarkdown,
  listRelatedKnowledgeEntries,
  resolveKnowledgeReviewQueueItem,
  saveResearchActionCards,
  sendWorkBuddyWebhook,
  updateKnowledgeEntry,
} from "@/lib/api";
import { ResearchActionCardsPanel } from "@/components/research/research-action-cards-panel";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { AppIcon } from "@/components/ui/app-icon";
import { ExternalLinkActions, normalizeExternalUrl } from "@/components/ui/external-link-actions";
import { WorkBuddyMark } from "@/components/ui/workbuddy-mark";
import { getGuardedRewriteReasonLabels, isGuardedBacklog } from "@/lib/research-diagnostics";
import { normalizeResearchActionCards } from "@/lib/research-action-cards";

type RankedPanelTone = "sky" | "amber" | "emerald";

export function KnowledgeDetailCard({ item }: { item: ApiKnowledgeEntry }) {
  const { t } = useAppPreferences();
  const pendingRankedEntities = (
    report: ApiResearchReport,
    role: "target" | "competitor" | "partner",
  ) => {
    if (role === "target") return dedupeByKey(report.pending_target_candidates || [], (item) => String(item?.name || "").trim(), 3);
    if (role === "competitor") return dedupeByKey(report.pending_competitor_candidates || [], (item) => String(item?.name || "").trim(), 3);
    return dedupeByKey(report.pending_partner_candidates || [], (item) => String(item?.name || "").trim(), 3);
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
  const confidenceToneMeta = (value?: string) => {
    if (value === "high") {
      return {
        badge: "bg-emerald-100 text-emerald-700",
        panel: "border-emerald-200/90 bg-[linear-gradient(180deg,rgba(240,253,244,0.98),rgba(220,252,231,0.78))]",
        item: "bg-emerald-50/78",
        excerpt: "bg-emerald-50/90 text-emerald-950",
      };
    }
    if (value === "conflict") {
      return {
        badge: "bg-rose-100 text-rose-700",
        panel: "border-rose-200/90 bg-[linear-gradient(180deg,rgba(255,241,242,0.98),rgba(255,228,230,0.78))]",
        item: "bg-rose-50/78",
        excerpt: "bg-rose-50/90 text-rose-950",
      };
    }
    return {
      badge: "bg-amber-100 text-amber-700",
      panel: "border-amber-200/90 bg-[linear-gradient(180deg,rgba(255,251,235,0.98),rgba(254,243,199,0.72))]",
      item: "bg-amber-50/76",
      excerpt: "bg-amber-50/90 text-amber-950",
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
  const rankedPanelTone = (tone: RankedPanelTone) => {
    if (tone === "amber") {
      return {
        panelClass:
          "border-amber-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(255,251,235,0.92))]",
        entityClass:
          "border-amber-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.94),rgba(255,251,235,0.82))]",
        subtleClass: "border-amber-100/80 bg-amber-50/84",
        linkClass: "border-amber-100/80 bg-amber-50/72 hover:border-amber-200 hover:bg-white/92",
        titleClass: "text-amber-700",
        dotClass: "bg-amber-400/80",
      };
    }
    if (tone === "emerald") {
      return {
        panelClass:
          "border-emerald-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(236,253,245,0.92))]",
        entityClass:
          "border-emerald-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.94),rgba(236,253,245,0.82))]",
        subtleClass: "border-emerald-100/80 bg-emerald-50/84",
        linkClass: "border-emerald-100/80 bg-emerald-50/72 hover:border-emerald-200 hover:bg-white/92",
        titleClass: "text-emerald-700",
        dotClass: "bg-emerald-400/80",
      };
    }
    return {
      panelClass:
        "border-sky-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(240,249,255,0.92))]",
      entityClass:
        "border-sky-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.94),rgba(240,249,255,0.82))]",
      subtleClass: "border-sky-100/80 bg-sky-50/84",
      linkClass: "border-sky-100/80 bg-sky-50/72 hover:border-sky-200 hover:bg-white/92",
      titleClass: "text-sky-700",
      dotClass: "bg-sky-400/80",
    };
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
  const [reviewQueueActionId, setReviewQueueActionId] = useState("");
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
  const commercialIntelligence = useMemo(() => {
    if (entry.commercial_intelligence) {
      return entry.commercial_intelligence;
    }
    const payload = entry.metadata_payload;
    if (!payload || typeof payload !== "object") return null;
    const typedPayload = payload as { commercial_intelligence?: ApiKnowledgeEntry["commercial_intelligence"] };
    return typedPayload.commercial_intelligence || null;
  }, [entry.commercial_intelligence, entry.metadata_payload]);
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
  const followupDiagnostics = researchReport?.followup_diagnostics;
  const reportReadiness = researchReport?.report_readiness;
  const commercialSummary = researchReport?.commercial_summary;
  const technicalAppendix = researchReport?.technical_appendix;
  const reviewQueue = researchReport?.review_queue || [];
  const guardedBacklog = isGuardedBacklog(researchDiagnostics);
  const guardedReasonLabels = dedupeTextList(getGuardedRewriteReasonLabels(researchDiagnostics));
  const supportedTargetAccounts = dedupeTextList(researchDiagnostics?.supported_target_accounts || []);
  const unsupportedTargetAccounts = dedupeTextList(researchDiagnostics?.unsupported_target_accounts || []);
  const followupFilters = dedupeTextList([
    ...(followupDiagnostics?.rebuilt_regions || []),
    ...(followupDiagnostics?.rebuilt_industries || []),
    ...(followupDiagnostics?.rebuilt_clients || []),
  ]);
  const candidateProfileCompanies = dedupeTextList(researchDiagnostics?.candidate_profile_companies || []);
  const candidateProfileSourceLabels = dedupeTextList(researchDiagnostics?.candidate_profile_source_labels || []);
  const reportSurfaceCopy = {
    briefKicker: t("research.structuredReport", "执行简报"),
    readinessTitle: t("research.readinessTitle", "推进就绪度"),
    playbookTitle: t("research.playbookTitle", "推进要点"),
    appendixTitle: t("research.appendixTitle", "方法与边界"),
    reviewQueueTitle: t("research.reviewQueueTitle", "待核验结论"),
    reviewQueueDesc: t("research.reviewQueueDesc", "把冲突结论、弱证据章节和关键缺口集中出来，优先做二次核验。"),
    insightsTitle: t("research.deepInsightsTitle", "深度洞察"),
    insightsDesc: t("research.deepInsightsHint", "按主题继续展开关键判断、证据锚点与补证建议。"),
    sourceTitle: t("research.sourcesEvidenceTitle", "来源与证据"),
  };
  const pipelineStages = researchDiagnostics?.pipeline_stages || [];
  const evidenceMode = evidenceModeMeta(researchDiagnostics?.evidence_mode || "fallback");
  const diagnosticScopeLabels = dedupeTextList([
    ...(((researchDiagnostics?.scope_regions || []) as string[])),
    ...(((researchDiagnostics?.scope_industries || []) as string[])),
    ...(((researchDiagnostics?.scope_clients || []) as string[])),
  ]);
  const diagnosticCards = [
    {
      title: "范围锁定",
      value: researchDiagnostics?.scope_clients?.length
        ? `账户 ${researchDiagnostics.scope_clients.length} 个`
        : (researchDiagnostics?.scope_regions?.length || researchDiagnostics?.scope_industries?.length)
          ? "已限定范围"
          : "范围仍偏泛",
      detail:
        followupFilters.slice(0, 3).join(" / ") ||
        diagnosticScopeLabels.slice(0, 3).join(" / ") ||
        "当前仍待继续收敛到区域、行业或目标账户。",
      tone: "border-sky-100/90 bg-sky-50/78 text-sky-900",
    },
    {
      title: "查询策略",
      value: researchDiagnostics?.strategy_query_expansion_count
        ? `扩展 ${researchDiagnostics.strategy_query_expansion_count} 条`
        : followupDiagnostics?.decomposition_queries?.length
          ? `追问拆出 ${followupDiagnostics.decomposition_queries.length} 条`
          : "基础混合检索",
      detail:
        followupDiagnostics?.summary ||
        researchDiagnostics?.strategy_scope_summary ||
        "当前已启用混合检索，并用总览块优先路由到章节与证据块。",
      tone: "border-violet-100/90 bg-violet-50/78 text-violet-900",
    },
    {
      title: "账户支撑",
      value: unsupportedTargetAccounts.length
        ? `待补证 ${unsupportedTargetAccounts.length} 个`
        : supportedTargetAccounts.length
          ? `已支撑 ${supportedTargetAccounts.length} 个`
          : "未锁定账户",
      detail:
        unsupportedTargetAccounts.slice(0, 2).join(" / ") ||
        supportedTargetAccounts.slice(0, 2).join(" / ") ||
        "当前结果更偏主题线索，仍待收敛到账户。",
      tone: unsupportedTargetAccounts.length
        ? "border-rose-100/90 bg-rose-50/82 text-rose-900"
        : "border-emerald-100/90 bg-emerald-50/78 text-emerald-900",
    },
    {
      title: "证据门槛",
      value: guardedBacklog
        ? "Guarded backlog"
        : reportReadiness?.evidence_gate_passed
          ? "证据门槛已通过"
          : reviewQueue.length
            ? `待核验 ${reviewQueue.length} 项`
            : "证据门槛待补",
      detail:
        guardedReasonLabels.slice(0, 2).join(" / ") ||
        reportReadiness?.next_verification_steps?.[0] ||
        reviewQueue[0]?.summary ||
        reviewQueue[0]?.recommended_action ||
        "优先补官方源、账户支撑和关键章节的交叉验证。",
      tone: guardedBacklog || !reportReadiness?.evidence_gate_passed
        ? "border-amber-100/90 bg-amber-50/82 text-amber-900"
        : "border-emerald-100/90 bg-emerald-50/78 text-emerald-900",
    },
  ];
  const methodologyCard = commercialIntelligence?.methodology;
  const confidenceCard = commercialIntelligence?.confidence;
  const coverageGaps = commercialIntelligence?.coverage_gaps || [];
  const intelligenceAccounts = commercialIntelligence?.accounts || [];
  const intelligenceOpportunities = commercialIntelligence?.opportunities || [];
  const intelligenceBenchmark = commercialIntelligence?.benchmark;
  const intelligenceMaturity = commercialIntelligence?.maturity;
  const rankedPanels = useMemo(
    () =>
      researchReport
        ? [
            {
              title: researchReport.top_target_accounts?.length
                ? t("research.topTargets", "高价值甲方 Top 3")
                : t("research.pendingTargets", "待补证甲方候选"),
              items: dedupeByKey(
                researchReport.top_target_accounts?.length
                  ? researchReport.top_target_accounts
                  : pendingRankedEntities(researchReport, "target"),
                (entity) => String(entity?.name || "").trim(),
                3,
              ),
              tone: "sky",
            },
            {
              title: researchReport.top_competitors?.length
                ? t("research.topCompetitors", "高威胁竞品 Top 3")
                : t("research.pendingCompetitors", "待补证竞品候选"),
              items: dedupeByKey(
                researchReport.top_competitors?.length
                  ? researchReport.top_competitors
                  : pendingRankedEntities(researchReport, "competitor"),
                (entity) => String(entity?.name || "").trim(),
                3,
              ),
              tone: "amber",
            },
            {
              title: researchReport.top_ecosystem_partners?.length
                ? t("research.topPartners", "高影响力生态伙伴 Top 3")
                : t("research.pendingPartners", "待补证生态伙伴候选"),
              items: dedupeByKey(
                researchReport.top_ecosystem_partners?.length
                  ? researchReport.top_ecosystem_partners
                  : pendingRankedEntities(researchReport, "partner"),
                (entity) => String(entity?.name || "").trim(),
                3,
              ),
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

  const handleReviewQueueAction = async (
    reviewId: string,
    action: "open" | "resolved" | "deferred",
  ) => {
    setReviewQueueActionId(reviewId);
    setMessage("");
    try {
      const updated = await resolveKnowledgeReviewQueueItem(entry.id, reviewId, { action });
      setEntry(updated);
      setMessage(
        action === "resolved"
          ? "已标记为已核验"
          : action === "deferred"
            ? "已延后处理"
            : "已重新打开审查项",
      );
    } catch {
      setMessage("审查队列更新失败，请稍后重试");
    } finally {
      setReviewQueueActionId("");
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
    <div data-testid="knowledge-detail-card" className="af-knowledge-detail space-y-5">
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
          <div className="flex w-full flex-wrap gap-2 xl:pt-1">
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
          <div data-testid="knowledge-research-card" className="mt-3 space-y-4">
            <div className="rounded-2xl border border-sky-100/90 bg-sky-50/75 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-500">
                {reportSurfaceCopy.briefKicker}
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
                    {guardedBacklog ? (
                      <span className="rounded-full bg-white/80 px-2.5 py-1 text-[11px] text-rose-700">
                        Guarded backlog
                      </span>
                    ) : null}
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
                    {candidateProfileCompanies.length ? (
                      <span className="rounded-full bg-white/80 px-2.5 py-1 text-[11px]">
                        {t("research.candidateProfiles", "候选补证公司")} {candidateProfileCompanies.length}
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
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    {diagnosticCards.map((card) => (
                      <div key={card.title} className={`rounded-[18px] border px-3 py-3 ${card.tone}`}>
                        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] opacity-70">
                          {card.title}
                        </p>
                        <p className="mt-1 text-sm font-semibold leading-6">
                          {card.value}
                        </p>
                        <p className="mt-1 text-xs leading-5 opacity-80">
                          {card.detail}
                        </p>
                      </div>
                    ))}
                  </div>
                  {pipelineStages.length ? (
                    <div className="af-knowledge-stage-grid mt-3">
                      {pipelineStages.map((stage) => (
                        <div key={stage.key} className="af-knowledge-stage-card">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                            {stage.label}
                          </p>
                          <p className="af-knowledge-stage-value">{stage.value}</p>
                          <p className="af-knowledge-stage-summary">{stage.summary}</p>
                        </div>
                      ))}
                    </div>
                  ) : null}
                  {guardedReasonLabels.length ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {guardedReasonLabels.map((value) => (
                        <span key={`guarded-reason-${value}`} className="rounded-full bg-rose-50 px-2.5 py-1 text-[11px] text-rose-700">
                          {value}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  {supportedTargetAccounts.length || unsupportedTargetAccounts.length ? (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {supportedTargetAccounts.map((value) => (
                        <span key={`supported-target-${value}`} className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] text-emerald-700">
                          已支撑 · {value}
                        </span>
                      ))}
                      {unsupportedTargetAccounts.map((value) => (
                        <span key={`unsupported-target-${value}`} className="rounded-full bg-rose-50 px-2.5 py-1 text-[11px] text-rose-700">
                          未支撑 · {value}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  {candidateProfileCompanies.length ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {candidateProfileCompanies.map((value) => (
                        <span key={`candidate-profile-${value}`} className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] text-sky-700">
                          {value}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  {candidateProfileSourceLabels.length ? (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {candidateProfileSourceLabels.map((value) => (
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

            {(reportReadiness || commercialSummary) ? (
              <div className="grid gap-4">
                {reportReadiness ? (
                  <article className="rounded-[24px] border border-slate-200/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(241,245,249,0.86))] p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{reportSurfaceCopy.readinessTitle}</p>
                        <p className="mt-2 text-sm text-slate-500">
                          {reportReadiness.status === "ready"
                            ? "当前结果已经满足较完整的销售/咨询推进条件。"
                            : reportReadiness.status === "degraded"
                              ? "当前可以先做候选推进，但仍建议继续补证。"
                              : "当前更适合作为候选名单和待补证清单。"}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2 text-xs">
                        <span className={`rounded-full px-2.5 py-1 ${reportReadiness.status === "ready" ? "bg-emerald-100 text-emerald-700" : reportReadiness.status === "degraded" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-600"}`}>
                          {reportReadiness.status === "ready" ? "可直接推进" : reportReadiness.status === "degraded" ? "候选推进" : "待补证"}
                        </span>
                        <span className="rounded-full bg-white/86 px-2.5 py-1 text-slate-700">评分 {reportReadiness.score}</span>
                        <span className={`rounded-full px-2.5 py-1 ${reportReadiness.evidence_gate_passed ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
                          {reportReadiness.evidence_gate_passed ? "证据门槛已通过" : "证据门槛待补"}
                        </span>
                      </div>
                    </div>
                    {reportReadiness.reasons?.length ? (
                      <div className="mt-4 space-y-2">
                        {reportReadiness.reasons.map((value) => (
                          <div key={`report-readiness-reason-${value}`} className="rounded-[18px] border border-white/90 bg-white/84 px-3 py-2 text-sm leading-6 text-slate-700">
                            {value}
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {(reportReadiness.missing_axes?.length || reportReadiness.next_verification_steps?.length) ? (
                      <div className="mt-4 grid gap-3">
                        {reportReadiness.missing_axes?.length ? (
                          <div className="rounded-[18px] border border-amber-100/90 bg-amber-50/86 p-3">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-700">仍缺关键维度</p>
                            <div className="mt-2 flex flex-wrap gap-2">
                              {reportReadiness.missing_axes.map((value) => (
                                <span key={`report-readiness-axis-${value}`} className="rounded-full bg-white/84 px-2.5 py-1 text-[11px] text-amber-800">
                                  {value}
                                </span>
                              ))}
                            </div>
                          </div>
                        ) : null}
                        {reportReadiness.next_verification_steps?.length ? (
                          <div className="rounded-[18px] border border-white/90 bg-white/84 p-3">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">下一步补证</p>
                            <ul className="mt-2 space-y-2 text-sm leading-6 text-slate-600">
                              {reportReadiness.next_verification_steps.slice(0, 3).map((value) => (
                                <li key={`report-readiness-step-${value}`} className="flex gap-2">
                                  <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-slate-300" />
                                  <span>{value}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </article>
                ) : null}

                {commercialSummary ? (
                  <article className="rounded-[24px] border border-cyan-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(238,247,255,0.86))] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{reportSurfaceCopy.playbookTitle}</p>
                    <div className="mt-4 grid gap-3">
                      <div className="rounded-[18px] border border-white/90 bg-white/84 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">重点账户</p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {commercialSummary.account_focus?.length ? commercialSummary.account_focus.map((value) => (
                            <span key={`commercial-summary-account-${value}`} className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] text-sky-700">
                              {value}
                            </span>
                          )) : <span className="text-sm text-slate-500">仍待收敛到账户对象</span>}
                        </div>
                      </div>
                      <div className="rounded-[18px] border border-white/90 bg-white/84 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">预算与信号</p>
                        <p className="mt-2 text-sm leading-6 text-slate-700">{commercialSummary.budget_signal || "当前仍缺直接预算或采购信号"}</p>
                      </div>
                      <div className="rounded-[18px] border border-white/90 bg-white/84 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">推进窗口</p>
                        <p className="mt-2 text-sm leading-6 text-slate-700">{commercialSummary.entry_window || "当前仍缺明确进入窗口"}</p>
                      </div>
                      <div className="rounded-[18px] border border-white/90 bg-white/84 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">竞合与伙伴</p>
                        <p className="mt-2 text-sm leading-6 text-slate-700">{commercialSummary.competition_or_partner || "当前仍需补竞品或伙伴格局"}</p>
                      </div>
                    </div>
                    <div className="mt-3 rounded-[18px] border border-sky-100/90 bg-white/84 p-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">下一步推进</p>
                      <p className="mt-2 text-sm leading-6 text-sky-900">{commercialSummary.next_action || "继续补组织入口、预算和进入窗口后再生成行动卡。"}</p>
                    </div>
                  </article>
                ) : null}
              </div>
            ) : null}

            <ResearchActionCardsPanel
              t={t}
              title={t("research.actionCardsTitle", "下一步推进剧本")}
              subtitle={t("research.actionCardsHint", "把账户、销售、投标与生态判断拆成可执行动作。")}
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


            {(methodologyCard || confidenceCard || coverageGaps.length) ? (
              <div className="grid gap-4">
                {confidenceCard ? (
                  <article className="rounded-[24px] border border-emerald-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(236,253,245,0.86))] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">可信度卡</p>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <span className={`rounded-full px-2.5 py-1 text-xs ${qualityTone(confidenceCard.level || "low")}`}>
                        {confidenceCard.level === "high" ? "高可信" : confidenceCard.level === "medium" ? "中可信" : "待补证"}
                      </span>
                      <span className="rounded-full bg-white/86 px-2.5 py-1 text-xs text-slate-700">
                        可信度 {confidenceCard.score}
                      </span>
                      <span className="rounded-full bg-white/86 px-2.5 py-1 text-xs text-slate-700">
                        官方源 {Math.round((confidenceCard.official_source_ratio || 0) * 100)}%
                      </span>
                    </div>
                    {confidenceCard.reasons?.length ? (
                      <div className="mt-4 space-y-2">
                        {confidenceCard.reasons.map((value) => (
                          <div key={`confidence-reason-${value}`} className="rounded-[18px] border border-white/90 bg-white/84 px-3 py-2 text-sm leading-6 text-slate-700">
                            {value}
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {confidenceCard.concerns?.length ? (
                      <div className="mt-4 flex flex-wrap gap-2">
                        {confidenceCard.concerns.map((value) => (
                          <span key={`confidence-concern-${value}`} className="rounded-full bg-amber-50 px-2.5 py-1 text-[11px] text-amber-700">
                            {value}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </article>
                ) : null}
                {methodologyCard ? (
                  <article className="rounded-[24px] border border-slate-200/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(241,245,249,0.86))] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">方法论卡</p>
                    {methodologyCard.scope_summary ? (
                      <p className="mt-3 text-sm leading-6 text-slate-700">{methodologyCard.scope_summary}</p>
                    ) : null}
                    <div className="mt-3 grid gap-3">
                      <div className="rounded-[18px] border border-white/90 bg-white/84 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">取数与边界</p>
                        <p className="mt-2 text-sm leading-6 text-slate-700">{methodologyCard.data_boundary}</p>
                      </div>
                      <div className="rounded-[18px] border border-white/90 bg-white/84 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Pipeline</p>
                        <p className="mt-2 text-sm leading-6 text-slate-700">{methodologyCard.pipeline_summary}</p>
                      </div>
                    </div>
                    {methodologyCard.query_plan?.length ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {methodologyCard.query_plan.slice(0, 4).map((value) => (
                          <span key={`method-query-${value}`} className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-600">
                            {value}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </article>
                ) : null}
              </div>
            ) : null}

            {coverageGaps.length ? (
              <article className="rounded-[24px] border border-amber-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(255,251,235,0.88))] p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">缺证与补证建议</p>
                <div className="mt-3 grid gap-3">
                  {coverageGaps.map((gap) => (
                    <div key={`${gap.title}-${gap.detail}`} className="rounded-[18px] border border-white/90 bg-white/84 p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-semibold text-slate-900">{gap.title}</p>
                        <span className={`rounded-full px-2 py-0.5 text-[10px] ${gap.severity === "high" ? "bg-rose-100 text-rose-700" : gap.severity === "medium" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-500"}`}>
                          {gap.severity === "high" ? "高优先级" : gap.severity === "medium" ? "中优先级" : "低优先级"}
                        </span>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-slate-600">{gap.detail}</p>
                      <p className="mt-2 text-sm leading-6 text-amber-900">建议：{gap.recommended_action}</p>
                    </div>
                  ))}
                </div>
              </article>
            ) : null}

            {(intelligenceAccounts.length || intelligenceOpportunities.length || intelligenceBenchmark || intelligenceMaturity) ? (
              <div className="grid gap-4">
                <div className="space-y-4">
                  {intelligenceAccounts.length ? (
                    <article className="rounded-[24px] border border-sky-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(240,249,255,0.9))] p-4">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">账户对象</p>
                          <p className="mt-2 text-sm text-slate-500">把研报中的重点对象转成可持续跟进的账户页。</p>
                        </div>
                        <Link href="/knowledge/accounts" className="text-sm font-medium text-sky-700">
                          查看账户页
                        </Link>
                      </div>
                      <div className="mt-4 space-y-3">
                        {intelligenceAccounts.slice(0, 3).map((account) => (
                          <Link
                            key={`intelligence-account-${account.slug}`}
                            href={`/knowledge/accounts/${account.slug}`}
                            className="block rounded-[20px] border border-sky-100/80 bg-white/88 p-4 transition hover:border-sky-200 hover:bg-white"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <h3 className="text-sm font-semibold text-slate-900">{account.name}</h3>
                              <div className="flex flex-wrap gap-2 text-[11px]">
                                <span className={`rounded-full px-2 py-0.5 ${valueBucket(account.confidence_score).className}`}>
                                  {valueBucket(account.confidence_score).label}
                                </span>
                                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-600">
                                  预算概率 {account.budget_probability}%
                                </span>
                              </div>
                            </div>
                            <p className="mt-2 text-sm leading-6 text-slate-600">{account.summary}</p>
                            {account.next_best_action ? (
                              <p className="mt-2 text-sm font-medium leading-6 text-sky-800">下一步：{account.next_best_action}</p>
                            ) : null}
                          </Link>
                        ))}
                      </div>
                    </article>
                  ) : null}

                  {intelligenceOpportunities.length ? (
                    <article className="rounded-[24px] border border-emerald-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(236,253,245,0.9))] p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">机会对象</p>
                      <div className="mt-4 space-y-3">
                        {intelligenceOpportunities.slice(0, 3).map((opportunity) => (
                          <Link
                            key={`intelligence-opportunity-${opportunity.title}`}
                            href={`/knowledge/accounts/${opportunity.account_slug}`}
                            className="block rounded-[20px] border border-emerald-100/80 bg-white/88 p-4 transition hover:border-emerald-200 hover:bg-white"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <h3 className="text-sm font-semibold text-slate-900">{opportunity.title}</h3>
                              <span className={`rounded-full px-2 py-0.5 text-[11px] ${valueBucket(opportunity.score).className}`}>
                                {opportunity.confidence_label || valueBucket(opportunity.score).label}
                              </span>
                            </div>
                            <p className="mt-2 text-sm leading-6 text-slate-600">{opportunity.next_best_action}</p>
                            <p className="mt-2 text-xs text-slate-500">窗口：{opportunity.entry_window}</p>
                          </Link>
                        ))}
                      </div>
                    </article>
                  ) : null}
                </div>

                <div className="space-y-4">
                  {intelligenceBenchmark ? (
                    <article className="rounded-[24px] border border-violet-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(245,243,255,0.9))] p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">标杆与对标</p>
                      <p className="mt-3 text-sm leading-6 text-slate-700">{intelligenceBenchmark.summary}</p>
                      {intelligenceBenchmark.cases?.length ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {intelligenceBenchmark.cases.map((value) => (
                            <span key={`benchmark-${value}`} className="rounded-full bg-violet-50 px-2.5 py-1 text-[11px] text-violet-700">
                              {value}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </article>
                  ) : null}

                  {intelligenceMaturity ? (
                    <article className="rounded-[24px] border border-slate-200/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(241,245,249,0.9))] p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">成熟度评估</p>
                        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                          {intelligenceMaturity.stage}
                        </span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-slate-700">{intelligenceMaturity.summary}</p>
                      <div className="mt-3 grid gap-3">
                        {intelligenceMaturity.dimensions?.map((dimension) => (
                          <div key={`maturity-${dimension.name}`} className="rounded-[18px] border border-white/90 bg-white/84 px-3 py-2">
                            <div className="flex items-center justify-between gap-2">
                              <p className="text-sm font-medium text-slate-800">{dimension.name}</p>
                              <span className={`rounded-full px-2 py-0.5 text-[10px] ${qualityTone(dimension.level || "low")}`}>
                                {dimension.level === "high" ? "高" : dimension.level === "medium" ? "中" : "低"}
                              </span>
                            </div>
                            <p className="mt-1 text-sm leading-6 text-slate-600">{dimension.note}</p>
                          </div>
                        ))}
                      </div>
                    </article>
                  ) : null}
                </div>
              </div>
            ) : null}

            {(researchReport.five_year_outlook.length || researchReport.competition_analysis.length) ? (
              <div className="grid gap-4">
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
              <div className="grid gap-4">
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
              <div className="grid gap-4">
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
              <div className="grid gap-4">
                {rankedPanels.map((panel) => (
                  <article
                    key={panel.title}
                    className={`rounded-[24px] border p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)] ${rankedPanelTone(panel.tone as RankedPanelTone).panelClass}`}
                  >
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{panel.title}</p>
                    <div className="mt-3 space-y-3">
                      {panel.items.map((entity) => (
                        <div
                          key={`${panel.title}-${entity.name}`}
                          className={`rounded-[20px] border p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.72)] ${rankedPanelTone(panel.tone as RankedPanelTone).entityClass}`}
                        >
                          <div className="flex items-center justify-between gap-3">
                            <h4 className={`text-sm font-semibold ${rankedPanelTone(panel.tone as RankedPanelTone).titleClass}`}>
                              {entity.name}
                            </h4>
                            <span className={`rounded-full px-2 py-0.5 text-[11px] ${valueBucket(entity.score).className}`}>
                              {valueBucket(entity.score).label}
                            </span>
                          </div>
                          <p className="mt-2 text-sm leading-6 text-slate-600">{entity.reasoning}</p>
                          {entity.score_breakdown?.length ? (
                            <div className="mt-3 grid gap-2">
                              {entity.score_breakdown.slice(0, 3).map((factor) => (
                                <div
                                  key={`${entity.name}-${factor.label}`}
                                  className={`rounded-[18px] border px-3 py-2 ${rankedPanelTone(panel.tone as RankedPanelTone).subtleClass}`}
                                >
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
                                <div
                                  key={`${entity.name}-${link.url}`}
                                  className={`block rounded-[18px] border px-3 py-2 transition ${rankedPanelTone(panel.tone as RankedPanelTone).linkClass}`}
                                >
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className={`h-1.5 w-1.5 rounded-full ${rankedPanelTone(panel.tone as RankedPanelTone).dotClass}`} />
                                    <a
                                      href={normalizeExternalUrl(link.url)}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="text-xs font-medium text-slate-900 underline-offset-4 hover:text-sky-800 hover:underline"
                                    >
                                      {link.title}
                                    </a>
                                    <span className="rounded-full bg-sky-50 px-2 py-0.5 text-[10px] text-sky-700">
                                      {sourceTierLabel(link.source_tier || "media")}
                                    </span>
                                    {link.source_label ? (
                                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">
                                        {link.source_label}
                                      </span>
                                    ) : null}
                                  </div>
                                  <ExternalLinkActions
                                    url={link.url}
                                    className="mt-2"
                                    openLabel="网页打开"
                                  />
                                </div>
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
              <div>
                <div className="mb-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{reportSurfaceCopy.insightsTitle}</p>
                  <p className="mt-1 text-sm text-slate-500">{reportSurfaceCopy.insightsDesc}</p>
                </div>
              <div className="grid gap-4">
                {researchReport.sections.map((section) => {
                  const tone = confidenceToneMeta(section.confidence_tone);
                  return (
                  <article key={section.title} className={`rounded-2xl border p-4 ${tone.panel}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                        {section.title}
                      </p>
                      <div className="flex flex-wrap gap-2 text-[11px]">
                        {section.confidence_label ? (
                          <span className={`rounded-full px-2 py-0.5 ${tone.badge}`}>
                            {section.confidence_label}
                          </span>
                        ) : null}
                        <span className={`rounded-full px-2 py-0.5 ${qualityTone(section.evidence_density || "low")}`}>
                          {t("research.centerEvidenceDensity", "证据密度")}·{qualityLabel(section.evidence_density || "low")}
                        </span>
                        <span className={`rounded-full px-2 py-0.5 ${qualityTone(section.source_quality || "low")}`}>
                          {t("research.centerSourceQuality", "来源质量")}·{qualityLabel(section.source_quality || "low")}
                        </span>
                        {typeof section.evidence_quota === "number" && section.evidence_quota > 0 ? (
                          <span
                            className={`rounded-full px-2 py-0.5 ${
                              section.meets_evidence_quota ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
                            }`}
                          >
                            配额 {section.evidence_count || 0}/{section.evidence_quota}
                          </span>
                        ) : null}
                      </div>
                    </div>
                    <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
                      {section.items.map((itemValue) => (
                        <li key={`${section.title}-${itemValue}`} className={`flex gap-2 rounded-xl px-2 py-1.5 ${tone.item}`}>
                          <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-slate-300" />
                          <span>{itemValue}</span>
                        </li>
                      ))}
                    </ul>
                    {section.confidence_reason ? (
                      <p className="mt-3 text-xs leading-5 text-slate-600">{section.confidence_reason}</p>
                    ) : null}
                    {section.evidence_note ? (
                      <p className="mt-3 text-xs leading-5 text-slate-500">{section.evidence_note}</p>
                    ) : null}
                    {section.quota_note ? (
                      <p className={`mt-2 text-xs leading-5 ${section.meets_evidence_quota ? "text-emerald-700" : "text-amber-700"}`}>
                        {section.quota_note}
                      </p>
                    ) : null}
                    {section.contradiction_note ? (
                      <p className="mt-2 text-xs leading-5 text-rose-700">{section.contradiction_note}</p>
                    ) : null}
                    {section.next_verification_steps?.length ? (
                      <div className="mt-3 rounded-2xl border border-amber-200/80 bg-amber-50/90 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-700">
                          下一步补证
                        </p>
                        <ul className="mt-2 space-y-1.5 text-xs leading-5 text-amber-900">
                          {section.next_verification_steps.slice(0, 3).map((step) => (
                            <li key={`${section.title}-${step}`} className="flex gap-2">
                              <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-amber-400" />
                              <span>{step}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    {section.evidence_links?.length ? (
                      <div className="mt-3 rounded-2xl border border-white/80 bg-white/72 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">证据锚点</p>
                        <div className="mt-2 space-y-2">
                          {section.evidence_links.slice(0, 3).map((link) => (
                            <div
                              key={`${section.title}-${link.url}`}
                              className={`block rounded-xl border border-white/80 px-3 py-2 transition hover:border-slate-200 hover:bg-white ${tone.excerpt}`}
                            >
                              <div className="flex flex-wrap items-center gap-2 text-xs">
                                <a
                                  href={normalizeExternalUrl(link.url)}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="font-medium text-slate-900 underline-offset-4 hover:text-sky-800 hover:underline"
                                >
                                  {link.anchor_text || link.title}
                                </a>
                                <span className="rounded-full bg-white/76 px-2 py-0.5 text-[10px] text-slate-600">
                                  {link.source_tier === "official"
                                    ? t("research.sourceOfficial", "官方源")
                                    : link.source_tier === "aggregate"
                                      ? t("research.sourceAggregate", "聚合源")
                                      : t("research.sourceMedia", "媒体源")}
                                </span>
                                {link.source_label ? (
                                  <span className="rounded-full bg-white/76 px-2 py-0.5 text-[10px] text-slate-600">{link.source_label}</span>
                                ) : null}
                              </div>
                              {link.excerpt ? (
                                <p className="mt-2 rounded-lg bg-white/70 px-2 py-1.5 text-[11px] leading-5 text-slate-700">{link.excerpt}</p>
                              ) : null}
                              <ExternalLinkActions
                                url={link.url}
                                className="mt-2"
                                openLabel="网页打开"
                              />
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </article>
                  );
                })}
              </div>
              </div>
            ) : null}

            {reviewQueue.length ? (
              <article className="rounded-[24px] border border-rose-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(255,241,242,0.88))] p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{reportSurfaceCopy.reviewQueueTitle}</p>
                    <p className="mt-2 text-sm text-slate-500">{reportSurfaceCopy.reviewQueueDesc}</p>
                  </div>
                  <span className="rounded-full bg-white/84 px-2.5 py-1 text-xs text-slate-600">{reviewQueue.length} 条</span>
                </div>
                <div className="mt-4 space-y-3">
                  {reviewQueue.map((item) => (
                    <article key={`knowledge-review-${item.id}`} className="rounded-[18px] border border-white/90 bg-white/88 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-slate-900">{item.section_title}</p>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`rounded-full px-2 py-0.5 text-[10px] ${item.severity === "high" ? "bg-rose-100 text-rose-700" : item.severity === "medium" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-500"}`}>
                            {item.severity === "high" ? "高优先级" : item.severity === "medium" ? "中优先级" : "低优先级"}
                          </span>
                          <span className={`rounded-full px-2 py-0.5 text-[10px] ${item.resolution_status === "resolved" ? "bg-emerald-100 text-emerald-700" : item.resolution_status === "deferred" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-500"}`}>
                            {item.resolution_status === "resolved" ? "已核验" : item.resolution_status === "deferred" ? "已延后" : "待处理"}
                          </span>
                        </div>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-slate-700">{item.summary}</p>
                      {item.recommended_action ? (
                        <p className="mt-2 text-sm font-medium leading-6 text-rose-800">建议：{item.recommended_action}</p>
                      ) : null}
                      {item.resolution_note ? (
                        <p className="mt-2 text-xs leading-5 text-slate-500">备注：{item.resolution_note}</p>
                      ) : null}
                      {item.evidence_links?.length ? (
                        <div className="mt-3 space-y-2">
                          {item.evidence_links.slice(0, 2).map((link) => (
                            <div key={`knowledge-review-evidence-${item.id}-${link.url}`} className="rounded-xl border border-rose-100/90 bg-rose-50/72 px-3 py-2">
                              <a
                                href={normalizeExternalUrl(link.url)}
                                target="_blank"
                                rel="noreferrer"
                                className="text-xs font-medium text-slate-900 underline-offset-4 hover:text-rose-800 hover:underline"
                              >
                                {link.anchor_text || link.title}
                              </a>
                              <ExternalLinkActions
                                url={link.url}
                                className="mt-2"
                                openLabel="网页打开"
                              />
                            </div>
                          ))}
                        </div>
                      ) : null}
                      <div className="mt-3 flex flex-wrap gap-2">
                        {item.resolution_status !== "resolved" ? (
                          <button
                            type="button"
                            onClick={() => {
                              void handleReviewQueueAction(item.id, "resolved");
                            }}
                            disabled={reviewQueueActionId === item.id}
                            className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {reviewQueueActionId === item.id ? "处理中..." : "标记已核验"}
                          </button>
                        ) : null}
                        {item.resolution_status !== "deferred" ? (
                          <button
                            type="button"
                            onClick={() => {
                              void handleReviewQueueAction(item.id, "deferred");
                            }}
                            disabled={reviewQueueActionId === item.id}
                            className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] font-semibold text-amber-700 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {reviewQueueActionId === item.id ? "处理中..." : "延后处理"}
                          </button>
                        ) : null}
                        {item.resolution_status !== "open" ? (
                          <button
                            type="button"
                            onClick={() => {
                              void handleReviewQueueAction(item.id, "open");
                            }}
                            disabled={reviewQueueActionId === item.id}
                            className="rounded-full border border-slate-200 bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {reviewQueueActionId === item.id ? "处理中..." : "重新打开"}
                          </button>
                        ) : null}
                      </div>
                    </article>
                  ))}
                </div>
              </article>
            ) : null}

            {groupedResearchSources.length ? (
              <div>
                <div className="mb-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{reportSurfaceCopy.sourceTitle}</p>
                  <p className="mt-1 text-sm text-slate-500">按来源类型查看原文入口，便于快速复核关键结论和动作依据。</p>
                </div>
              <div className="grid gap-4">
                  {groupedResearchSources.map((group) => (
                    <article key={group.key} className="rounded-2xl border border-white/80 bg-[linear-gradient(180deg,rgba(248,251,255,0.9),rgba(241,245,249,0.72))] p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{group.title}</p>
                      <div className="mt-3 space-y-3">
                        {group.items.slice(0, 4).map((source) => (
                          <div
                            key={`${group.key}-${source.url}`}
                            className="block rounded-2xl border border-slate-200/80 bg-slate-50/84 p-3 transition hover:border-slate-300 hover:bg-white/84"
                          >
                            <a
                              href={normalizeExternalUrl(source.url)}
                              target="_blank"
                              rel="noreferrer"
                              className="text-sm font-semibold leading-6 text-slate-900 underline-offset-4 hover:text-sky-800 hover:underline"
                            >
                              {source.title}
                            </a>
                            <p className="mt-1 text-xs leading-5 text-slate-500">
                              {[source.source_label, source.domain || "web"].filter(Boolean).join(" · ")}
                            </p>
                            <ExternalLinkActions
                              url={source.url}
                              className="mt-3"
                              openLabel="网页打开"
                            />
                          </div>
                        ))}
                      </div>
                    </article>
                  ))}
                </div>
              </div>
            ) : null}

            {technicalAppendix ? (
              <article className="rounded-[24px] border border-slate-200/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(241,245,249,0.86))] p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{reportSurfaceCopy.appendixTitle}</p>
                <div className="mt-4 grid gap-3">
                  {technicalAppendix.key_assumptions?.length ? (
                    <div className="rounded-[18px] border border-white/90 bg-white/84 p-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">关键假设</p>
                      <ul className="mt-2 space-y-2 text-sm leading-6 text-slate-700">
                        {technicalAppendix.key_assumptions.map((value) => (
                          <li key={`knowledge-appendix-assumption-${value}`} className="flex gap-2">
                            <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-slate-300" />
                            <span>{value}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {technicalAppendix.scenario_comparison?.length ? (
                    <div className="rounded-[18px] border border-white/90 bg-white/84 p-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">情景对比</p>
                      <div className="mt-3 grid gap-3">
                        {technicalAppendix.scenario_comparison.map((scenario) => (
                          <div key={`knowledge-scenario-${scenario.name}`} className="rounded-[16px] border border-slate-200/80 bg-slate-50/84 p-3">
                            <p className="text-sm font-semibold text-slate-900">{scenario.name}</p>
                            <p className="mt-2 text-sm leading-6 text-slate-700">{scenario.summary}</p>
                            {scenario.implication ? (
                              <p className="mt-2 text-sm font-medium leading-6 text-sky-800">影响：{scenario.implication}</p>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {(technicalAppendix.limitations?.length || technicalAppendix.technical_appendix?.length) ? (
                    <div className="grid gap-3">
                      <div className="rounded-[18px] border border-amber-100/90 bg-amber-50/86 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-700">限制条件</p>
                        <ul className="mt-2 space-y-2 text-sm leading-6 text-amber-900">
                          {(technicalAppendix.limitations || []).map((value) => (
                            <li key={`knowledge-appendix-limit-${value}`} className="flex gap-2">
                              <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-amber-300" />
                              <span>{value}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                      <div className="rounded-[18px] border border-white/90 bg-white/84 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">方法说明</p>
                        <ul className="mt-2 space-y-2 text-sm leading-6 text-slate-700">
                          {(technicalAppendix.technical_appendix || []).map((value) => (
                            <li key={`knowledge-appendix-note-${value}`} className="flex gap-2">
                              <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-slate-300" />
                              <span>{value}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  ) : null}
                </div>
              </article>
            ) : null}

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

      <style jsx>{`
        .af-knowledge-detail :global(.af-glass) {
          background: linear-gradient(180deg, rgba(255, 255, 255, 0.95), rgba(250, 252, 255, 0.9));
          border-color: rgba(255, 255, 255, 0.84);
          box-shadow:
            0 28px 70px -46px rgba(15, 23, 42, 0.22),
            inset 0 1px 0 rgba(255, 255, 255, 0.7);
          backdrop-filter: saturate(155%) blur(12px);
          -webkit-backdrop-filter: saturate(155%) blur(12px);
        }

        .af-knowledge-stage-grid {
          display: grid;
          gap: 0.625rem;
          grid-template-columns: repeat(3, minmax(0, 1fr));
        }

        .af-knowledge-stage-card {
          border-radius: 18px;
          border: 1px solid rgba(255, 255, 255, 0.82);
          background: linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(248, 250, 252, 0.76));
          padding: 0.7rem 0.75rem;
          box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
        }

        .af-knowledge-stage-value {
          margin-top: 0.2rem;
          font-size: 1.15rem;
          font-weight: 600;
          letter-spacing: -0.04em;
          color: rgb(15 23 42);
        }

        .af-knowledge-stage-summary {
          margin-top: 0.18rem;
          font-size: 0.7rem;
          line-height: 1.4;
          color: rgb(100 116 139);
        }

        @media (max-width: 720px) {
          .af-knowledge-stage-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
}
