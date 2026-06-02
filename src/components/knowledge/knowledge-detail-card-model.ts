import type { ApiKnowledgeEntry, ApiResearchReport, ApiResearchSource } from "@/lib/api/types";
import { dedupeByKey } from "@/lib/display-list";

export type KnowledgeTranslateFn = (key: string, fallback?: string) => string;

export type RankedPanelTone = "sky" | "amber" | "emerald";

export interface KnowledgeRankedPanel {
  title: string;
  items: ApiResearchReport["top_target_accounts"];
  tone: RankedPanelTone;
}

export interface KnowledgeDiagnosticCard {
  title: string;
  value: string;
  detail: string;
  tone: string;
}

export type KnowledgeEvidenceModeMeta = ReturnType<typeof evidenceModeMeta>;
export type KnowledgeFollowupResolutionMeta = ReturnType<typeof followupResolutionMeta>;
export type KnowledgeReportSurfaceCopy = ReturnType<typeof buildReportSurfaceCopy>;

export function extractResearchReport(entry: ApiKnowledgeEntry): ApiResearchReport | null {
  const payload = entry.metadata_payload;
  if (!payload || typeof payload !== "object") return null;
  const typedPayload = payload as { kind?: string; report?: ApiResearchReport };
  if (typedPayload.kind !== "research_report" || !typedPayload.report) return null;
  return typedPayload.report;
}

export function extractCommercialIntelligence(entry: ApiKnowledgeEntry) {
  if (entry.commercial_intelligence) {
    return entry.commercial_intelligence;
  }
  const payload = entry.metadata_payload;
  if (!payload || typeof payload !== "object") return null;
  const typedPayload = payload as { commercial_intelligence?: ApiKnowledgeEntry["commercial_intelligence"] };
  return typedPayload.commercial_intelligence || null;
}

export function classifySourceTier(source: ApiResearchSource) {
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
}

export function qualityTone(value: string) {
  if (value === "high") return "af-chip af-chip-success";
  if (value === "medium") return "af-chip af-chip-warning";
  return "af-chip";
}

export function qualityLabel(value: string) {
  if (value === "high") return "高";
  if (value === "medium") return "中";
  return "低";
}

export function evidenceModeMeta(value: string, t: KnowledgeTranslateFn) {
  if (value === "strong") {
    return {
      label: t("research.evidenceStrong", "强证据"),
      className: "af-state-panel-success",
      note: t("research.evidenceStrongNote", "当前结果有较稳定的主题命中、官方源和多域名交叉支撑。"),
    };
  }
  if (value === "provisional") {
    return {
      label: t("research.evidenceProvisional", "可用初版"),
      className: "af-state-panel-warning",
      note: t("research.evidenceProvisionalNote", "当前已有可用线索，但仍建议继续补官方源或专项交叉验证。"),
    };
  }
  return {
    label: t("research.evidenceFallback", "待核实"),
    className: "border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] text-[var(--af-text-secondary)]",
    note: t("research.evidenceFallbackNote", "当前线索有价值，但还需要更多公开来源确认。"),
  };
}

export function confidenceToneMeta(value?: string) {
  if (value === "high") {
    return {
      badge: "af-chip af-chip-success",
      panel: "border-[color-mix(in_srgb,var(--af-success)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)]",
      item: "bg-[color-mix(in_srgb,var(--af-success)_14%,var(--af-surface-muted))]",
      excerpt: "bg-[color-mix(in_srgb,var(--af-success)_14%,var(--af-surface-muted))] text-[var(--af-success)]",
    };
  }
  if (value === "conflict") {
    return {
      badge: "af-chip af-chip-danger",
      panel: "border-[color-mix(in_srgb,var(--af-danger)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)]",
      item: "bg-[color-mix(in_srgb,var(--af-danger)_14%,var(--af-surface-muted))]",
      excerpt: "bg-[color-mix(in_srgb,var(--af-danger)_14%,var(--af-surface-muted))] text-[var(--af-danger)]",
    };
  }
  return {
    badge: "af-chip af-chip-warning",
    panel: "border-[color-mix(in_srgb,var(--af-warning)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)]",
    item: "bg-[color-mix(in_srgb,var(--af-warning)_14%,var(--af-surface-muted))]",
    excerpt: "bg-[color-mix(in_srgb,var(--af-warning)_14%,var(--af-surface-muted))] text-[var(--af-warning)]",
  };
}

export function valueBucket(score: number, t: KnowledgeTranslateFn) {
  if (score >= 75) return { label: t("summary.score.high", "高价值"), className: "af-chip af-chip-success" };
  if (score >= 55) return { label: t("summary.score.medium", "普通价值"), className: "af-chip af-chip-warning" };
  return { label: t("summary.score.low", "低价值"), className: "af-chip" };
}

export function followupResolutionMeta(value?: string) {
  if (value === "corrected") {
    return { label: "已按追问纠偏", className: "af-state-panel-success" };
  }
  if (value === "reused") {
    return { label: "沿用基线", className: "af-state-panel-info" };
  }
  return { label: "基线生成", className: "border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] text-[var(--af-text-secondary)]" };
}

export function factorBucket(score: number) {
  if (score >= 14) return { label: "强支撑", className: "af-chip af-chip-success" };
  if (score >= 6) return { label: "中支撑", className: "af-chip af-chip-warning" };
  if (score > 0) return { label: "弱支撑", className: "af-chip af-chip-info" };
  if (score < 0) return { label: "风险提示", className: "af-chip af-chip-danger" };
  return { label: "待补依据", className: "af-chip" };
}

export function rankedPanelTone(tone: RankedPanelTone) {
  if (tone === "amber") {
    return {
      panelClass:
        "border-[color-mix(in_srgb,var(--af-warning)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)]",
      entityClass:
        "border-[color-mix(in_srgb,var(--af-warning)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)]",
      subtleClass: "border-[color-mix(in_srgb,var(--af-warning)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-warning)_14%,var(--af-surface-muted))]",
      linkClass: "border-[color-mix(in_srgb,var(--af-warning)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-warning)_14%,var(--af-surface-muted))] hover:border-[var(--af-border-strong)] hover:bg-[var(--af-surface-hover)]",
      titleClass: "text-[var(--af-warning)]",
      dotClass: "bg-[color-mix(in_srgb,var(--af-warning)_14%,var(--af-surface-muted))]",
    };
  }
  if (tone === "emerald") {
    return {
      panelClass:
        "border-[color-mix(in_srgb,var(--af-success)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)]",
      entityClass:
        "border-[color-mix(in_srgb,var(--af-success)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)]",
      subtleClass: "border-[color-mix(in_srgb,var(--af-success)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-success)_14%,var(--af-surface-muted))]",
      linkClass: "border-[color-mix(in_srgb,var(--af-success)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-success)_14%,var(--af-surface-muted))] hover:border-[var(--af-border-strong)] hover:bg-[var(--af-surface-hover)]",
      titleClass: "text-[var(--af-success)]",
      dotClass: "bg-[color-mix(in_srgb,var(--af-success)_14%,var(--af-surface-muted))]",
    };
  }
  return {
    panelClass:
      "border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)]",
    entityClass:
      "border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)]",
    subtleClass: "border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))]",
    linkClass: "border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] hover:border-[var(--af-border-strong)] hover:bg-[var(--af-surface-hover)]",
    titleClass: "text-[var(--af-info)]",
    dotClass: "bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))]",
  };
}

export function sourceTierLabel(tier: string, t: KnowledgeTranslateFn) {
  if (tier === "official") return t("research.sourceOfficial", "官方源");
  if (tier === "aggregate") return t("research.sourceAggregate", "聚合源");
  return t("research.sourceMedia", "媒体源");
}

export function buildGroupedResearchSources(report: ApiResearchReport | null, t: KnowledgeTranslateFn) {
  if (!report) {
    return [];
  }
  const groups = [
    { key: "official", title: t("research.sourceOfficial", "官方源"), items: report.sources.filter((source) => classifySourceTier(source) === "official") },
    { key: "media", title: t("research.sourceMedia", "媒体源"), items: report.sources.filter((source) => classifySourceTier(source) === "media") },
    { key: "aggregate", title: t("research.sourceAggregate", "聚合源"), items: report.sources.filter((source) => classifySourceTier(source) === "aggregate") },
  ];
  return groups.filter((group) => group.items.length);
}

function pendingRankedEntities(
  report: ApiResearchReport,
  role: "target" | "competitor" | "partner",
) {
  if (role === "target") return dedupeByKey(report.pending_target_candidates || [], (item) => String(item?.name || "").trim(), 3);
  if (role === "competitor") return dedupeByKey(report.pending_competitor_candidates || [], (item) => String(item?.name || "").trim(), 3);
  return dedupeByKey(report.pending_partner_candidates || [], (item) => String(item?.name || "").trim(), 3);
}

export function buildRankedPanels(report: ApiResearchReport | null, t: KnowledgeTranslateFn): KnowledgeRankedPanel[] {
  if (!report) {
    return [];
  }
  return [
    {
      title: report.top_target_accounts?.length
        ? t("research.topTargets", "高价值甲方 Top 3")
        : t("research.pendingTargets", "待核验甲方候选"),
      items: dedupeByKey(
        report.top_target_accounts?.length
          ? report.top_target_accounts
          : pendingRankedEntities(report, "target"),
        (entity) => String(entity?.name || "").trim(),
        3,
      ),
      tone: "sky" as const,
    },
    {
      title: report.top_competitors?.length
        ? t("research.topCompetitors", "高威胁竞品 Top 3")
        : t("research.pendingCompetitors", "待核验竞品候选"),
      items: dedupeByKey(
        report.top_competitors?.length
          ? report.top_competitors
          : pendingRankedEntities(report, "competitor"),
        (entity) => String(entity?.name || "").trim(),
        3,
      ),
      tone: "amber" as const,
    },
    {
      title: report.top_ecosystem_partners?.length
        ? t("research.topPartners", "高影响力生态伙伴 Top 3")
        : t("research.pendingPartners", "待核验生态伙伴候选"),
      items: dedupeByKey(
        report.top_ecosystem_partners?.length
          ? report.top_ecosystem_partners
          : pendingRankedEntities(report, "partner"),
        (entity) => String(entity?.name || "").trim(),
        3,
      ),
      tone: "emerald" as const,
    },
  ].filter((panel) => panel.items.length);
}

export function buildReportSurfaceCopy(t: KnowledgeTranslateFn) {
  return {
    briefKicker: t("research.structuredReport", "执行简报"),
    readinessTitle: t("research.readinessTitle", "推进就绪度"),
    playbookTitle: t("research.playbookTitle", "推进要点"),
    appendixTitle: t("research.appendixTitle", "方法与边界"),
    reviewQueueTitle: t("research.reviewQueueTitle", "待核验结论"),
    reviewQueueDesc: t("research.reviewQueueDesc", "集中列出冲突结论、依据不足的章节和关键缺口，方便优先复核。"),
    insightsTitle: t("research.deepInsightsTitle", "深度洞察"),
    insightsDesc: t("research.deepInsightsHint", "按主题继续展开关键判断、依据和复核建议。"),
    sourceTitle: t("research.sourcesEvidenceTitle", "来源与证据"),
  };
}

export function buildMarkdownContent(entry: ApiKnowledgeEntry, t: KnowledgeTranslateFn) {
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
}

export function buildDiagnosticCards({
  researchDiagnostics,
  followupDiagnostics,
  followupFilters,
  diagnosticScopeLabels,
  unsupportedTargetAccounts,
  supportedTargetAccounts,
  guardedBacklog,
  reportReadiness,
  reviewQueue,
  guardedReasonLabels,
}: {
  researchDiagnostics: ApiResearchReport["source_diagnostics"] | undefined;
  followupDiagnostics: ApiResearchReport["followup_diagnostics"] | undefined;
  followupFilters: string[];
  diagnosticScopeLabels: string[];
  unsupportedTargetAccounts: string[];
  supportedTargetAccounts: string[];
  guardedBacklog: boolean;
  reportReadiness: ApiResearchReport["report_readiness"] | undefined;
  reviewQueue: NonNullable<ApiResearchReport["review_queue"]>;
  guardedReasonLabels: string[];
}): KnowledgeDiagnosticCard[] {
  return [
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
      tone: "border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] text-[var(--af-info)]",
    },
    {
      title: "查询策略",
      value: researchDiagnostics?.strategy_query_expansion_count
        ? `扩展 ${researchDiagnostics.strategy_query_expansion_count} 条`
        : followupDiagnostics?.decomposition_queries?.length
          ? `追问拆出 ${followupDiagnostics.decomposition_queries.length} 条`
          : "基础来源整理",
      detail:
        followupDiagnostics?.summary ||
        researchDiagnostics?.strategy_scope_summary ||
        "已结合多个公开来源整理报告，并突出关键章节和依据。",
      tone: "border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] text-[var(--af-info)]",
    },
    {
      title: "账户支撑",
      value: unsupportedTargetAccounts.length
        ? `待核验 ${unsupportedTargetAccounts.length} 个`
        : supportedTargetAccounts.length
          ? `已支撑 ${supportedTargetAccounts.length} 个`
          : "未锁定账户",
      detail:
        unsupportedTargetAccounts.slice(0, 2).join(" / ") ||
        supportedTargetAccounts.slice(0, 2).join(" / ") ||
        "当前结果更偏主题线索，仍待收敛到账户。",
      tone: unsupportedTargetAccounts.length
        ? "border-[color-mix(in_srgb,var(--af-danger)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-danger)_14%,var(--af-surface-muted))] text-[var(--af-danger)]"
        : "border-[color-mix(in_srgb,var(--af-success)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-success)_14%,var(--af-surface-muted))] text-[var(--af-success)]",
    },
    {
      title: "证据门槛",
      value: guardedBacklog
        ? "待复核"
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
        "优先补充官方源、账户支撑和关键章节的交叉验证。",
      tone: guardedBacklog || !reportReadiness?.evidence_gate_passed
        ? "border-[color-mix(in_srgb,var(--af-warning)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-warning)_14%,var(--af-surface-muted))] text-[var(--af-warning)]"
        : "border-[color-mix(in_srgb,var(--af-success)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-success)_14%,var(--af-surface-muted))] text-[var(--af-success)]",
    },
  ];
}
