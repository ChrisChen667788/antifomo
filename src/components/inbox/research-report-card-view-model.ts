import type { ApiResearchReport } from "@/lib/api/types";
import { dedupeByKey, dedupeTextList } from "@/lib/display-list";
import { getGuardedRewriteReasonLabels, isGuardedBacklog } from "@/lib/research-diagnostics";

export const classifySourceTier = (source: ApiResearchReport["sources"][number]) => {
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

export const qualityTone = (value: string) => {
  if (value === "high") return "bg-emerald-100 text-emerald-700";
  if (value === "medium") return "bg-amber-100 text-amber-700";
  return "bg-[var(--af-surface-muted)] text-[var(--af-text-tertiary)]";
};

export const qualityLabel = (value: string) => {
  if (value === "high") return "高";
  if (value === "medium") return "中";
  return "低";
};

export const evidenceModeMeta = (value: string) => {
  if (value === "strong") {
    return {
      label: "强证据",
      className: "border-emerald-200/90 bg-emerald-50 text-emerald-800",
      note: "当前结果有较稳定的主题匹配、官方来源和多来源交叉支撑。",
    };
  }
  if (value === "provisional") {
    return {
      label: "可用初版",
      className: "border-amber-200/90 bg-amber-50 text-amber-800",
      note: "当前已有可用线索，但仍建议继续补官方源或专项交叉验证。",
    };
  }
  return {
    label: "待核实",
    className: "border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] text-[var(--af-text-secondary)]",
    note: "当前线索有价值，但还需要更多公开来源确认。",
  };
};

export const readinessMeta = (value: string) => {
  if (value === "ready") {
    return {
      label: "可直接推进",
      className: "border-emerald-200/90 bg-emerald-50 text-emerald-800",
      note: "当前已经满足账户、预算窗口和证据门槛，可直接进入销售/咨询推进。",
    };
  }
  if (value === "degraded") {
    return {
      label: "候选推进",
      className: "border-amber-200/90 bg-amber-50 text-amber-800",
      note: "当前可用于初轮判断和内部讨论，但仍建议先复核再做强结论。",
    };
  }
  return {
    label: "待核验",
    className: "border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] text-[var(--af-text-secondary)]",
    note: "当前更适合作为候选名单与待核验清单，不宜直接当作最终商业判断。",
  };
};

export const confidenceToneMeta = (value?: string) => {
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

export const sectionStatusMeta = (value?: string) => {
  if (value === "ready") {
    return {
      label: "章节已通过",
      className: "bg-emerald-100 text-emerald-700",
    };
  }
  if (value === "degraded") {
    return {
      label: "章节待收紧",
      className: "bg-amber-100 text-amber-700",
    };
  }
  return {
    label: "章节待核验",
    className: "bg-rose-100 text-rose-700",
  };
};

export const sourceTierLabel = (value: string) => {
  if (value === "official") return "官方源";
  if (value === "aggregate") return "聚合源";
  return "媒体源";
};

export const valueBucket = (score: number) => {
  if (score >= 75) return { label: "高价值", className: "bg-emerald-100 text-emerald-700" };
  if (score >= 55) return { label: "普通价值", className: "bg-amber-100 text-amber-700" };
  return { label: "低价值", className: "bg-[var(--af-surface-muted)] text-[var(--af-text-tertiary)]" };
};

const qualityProfileMeta = (value?: string) => {
  if (value === "high_value") {
    return {
      label: "高情报价值",
      className: "border-emerald-200/90 bg-emerald-50 text-emerald-800",
    };
  }
  if (value === "usable") {
    return {
      label: "可用待补强",
      className: "border-amber-200/90 bg-amber-50 text-amber-800",
    };
  }
  return {
    label: "质量待核验",
    className: "border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] text-[var(--af-text-secondary)]",
  };
};

const deliveryQualityMeta = (value?: string) => {
  if (value === "pass") {
    return {
      label: "交付自审通过",
      className: "border-emerald-200/90 bg-emerald-50 text-emerald-800",
    };
  }
  if (value === "watch") {
    return {
      label: "交付待补强",
      className: "border-amber-200/90 bg-amber-50 text-amber-800",
    };
  }
  return {
    label: "交付待重审",
    className: "border-rose-200/90 bg-rose-50 text-rose-800",
  };
};

const architectureReadinessMeta = (value?: string) => {
  if (value === "ready") {
    return {
      label: "架构可进入方案评审",
      className: "border-emerald-200/90 bg-emerald-50 text-emerald-800",
    };
  }
  if (value === "watch") {
    return {
      label: "架构需补齐边界",
      className: "border-amber-200/90 bg-amber-50 text-amber-800",
    };
  }
  return {
    label: "架构暂不宜外发",
    className: "border-rose-200/90 bg-rose-50 text-rose-800",
  };
};

const followupResolutionMeta = (value?: string) => {
  if (value === "corrected") {
    return { label: "已按追问纠偏", className: "border-emerald-200/90 bg-emerald-50 text-emerald-800" };
  }
  if (value === "reused") {
    return { label: "沿用初始版本", className: "border-sky-200/90 bg-sky-50 text-sky-800" };
  }
  return { label: "初始生成", className: "border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] text-[var(--af-text-secondary)]" };
};

const reportSurfaceCopy = {
  readinessTitle: "推进就绪度",
  playbookTitle: "推进要点",
  appendixTitle: "方法与边界",
  reviewQueueTitle: "待核验结论",
  reviewQueueDesc: "集中列出冲突结论、依据不足的章节和关键缺口，方便优先复核。",
  insightsTitle: "深度洞察",
  insightsDesc: "按主题继续展开关键判断、依据和复核建议。",
  sourcePathTitle: "情报路径",
  sourceDiagTitle: "依据检查",
};

export function buildResearchReportCardViewModel(report: ApiResearchReport) {
  const groupedSources = {
    official: report.sources.filter((source) => classifySourceTier(source) === "official"),
    media: report.sources.filter((source) => classifySourceTier(source) === "media"),
    aggregate: report.sources.filter((source) => classifySourceTier(source) === "aggregate"),
  };
  const diagnostics = report.source_diagnostics;
  const followupDiagnostics = report.followup_diagnostics;
  const guardedBacklog = isGuardedBacklog(diagnostics);
  const guardedReasonLabels = dedupeTextList(getGuardedRewriteReasonLabels(diagnostics));
  const evidenceMode = evidenceModeMeta(diagnostics?.evidence_mode || "fallback");
  const supportedTargetAccounts = dedupeTextList(diagnostics?.supported_target_accounts || []);
  const unsupportedTargetAccounts = dedupeTextList(diagnostics?.unsupported_target_accounts || []);
  const enabledSourceLabels = dedupeTextList(diagnostics?.enabled_source_labels || []);
  const scopeRegions = dedupeTextList(diagnostics?.scope_regions || []);
  const scopeIndustries = dedupeTextList(diagnostics?.scope_industries || []);
  const scopeClients = dedupeTextList(diagnostics?.scope_clients || []);
  const matchedSourceLabels = dedupeTextList(diagnostics?.matched_source_labels || []);
  const topicAnchorTerms = dedupeTextList(diagnostics?.topic_anchor_terms || []);
  const matchedThemeLabels = dedupeTextList(diagnostics?.matched_theme_labels || []);
  const followupFilters = dedupeTextList([
    ...(followupDiagnostics?.rebuilt_regions || []),
    ...(followupDiagnostics?.rebuilt_industries || []),
    ...(followupDiagnostics?.rebuilt_clients || []),
  ]);
  const followupImpactedSections = (followupDiagnostics?.impacted_sections || []).slice(0, 4);
  const followupTitleResolution = followupResolutionMeta(followupDiagnostics?.title_resolution);
  const followupSummaryResolution = followupResolutionMeta(followupDiagnostics?.summary_resolution);
  const candidateProfileCompanies = dedupeTextList(diagnostics?.candidate_profile_companies || []);
  const candidateProfileSourceLabels = dedupeTextList(diagnostics?.candidate_profile_source_labels || []);
  const qualityExpansionQueries = dedupeTextList(diagnostics?.quality_expansion_query_plan || []);
  const qualityExpansionNotes = dedupeTextList(diagnostics?.quality_expansion_notes || []);
  const coreEntities = dedupeByKey(report.entity_graph?.entities || [], (entity) => String(entity?.canonical_name || "").trim(), 6);
  const readiness = report.report_readiness;
  const readinessState = readinessMeta(readiness?.status || "needs_evidence");
  const commercialSummary = report.commercial_summary;
  const technicalAppendix = report.technical_appendix;
  const reviewQueue = report.review_queue || [];
  const qualityProfile = report.quality_profile;
  const qualityProfileState = qualityProfileMeta(qualityProfile?.status);
  const marketIntelligence = report.market_intelligence;
  const solutionDeliveryPack = report.solution_delivery_pack;
  const solutionDeliveryQuality = solutionDeliveryPack?.solution_quality_profile;
  const projectProposalQuality = solutionDeliveryPack?.project_proposal_quality_profile;
  const architectureReadiness = solutionDeliveryPack?.architecture_readiness;
  const architectWorkbench = solutionDeliveryPack?.architect_workbench;
  const primaryCustomerScenario = architectWorkbench?.customer_scenarios?.[0];
  const solutionDeliveryQualityMeta = deliveryQualityMeta(solutionDeliveryQuality?.status);
  const projectProposalQualityMeta = deliveryQualityMeta(projectProposalQuality?.status);
  const architectureReadinessState = architectureReadinessMeta(architectureReadiness?.status);
  const weakSections = (report.sections || [])
    .filter((section) => {
      const status = String(section.status || "").trim();
      return status === "needs_evidence" || status === "degraded" || Boolean(section.insufficiency_reasons?.length);
    })
    .slice(0, 3);
  const targetSupportTone = unsupportedTargetAccounts.length
    ? "border-rose-200/90 bg-rose-50 text-rose-700"
    : supportedTargetAccounts.length
      ? "border-emerald-200/90 bg-emerald-50 text-emerald-700"
      : "border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] text-[var(--af-text-secondary)]";
  const targetSupportValue = unsupportedTargetAccounts.length
    ? "目标账户待核验"
    : supportedTargetAccounts.length
      ? `已支撑 ${supportedTargetAccounts.length} 个目标账户`
      : "未识别明确目标账户";
  const targetSupportDetail = unsupportedTargetAccounts.length
    ? unsupportedTargetAccounts.slice(0, 2).join(" / ")
    : supportedTargetAccounts.length
      ? supportedTargetAccounts.slice(0, 2).join(" / ")
      : "当前结果更偏主题线索，仍待收敛到账户。";
  const verificationTone =
    guardedBacklog || !readiness?.evidence_gate_passed
      ? "border-amber-200/90 bg-amber-50 text-amber-800"
      : "border-emerald-200/90 bg-emerald-50 text-emerald-800";
  const verificationValue = guardedBacklog
    ? "已降级为 guarded backlog"
    : readiness?.evidence_gate_passed
      ? "证据门槛已通过"
      : reviewQueue.length
        ? `待核验 ${reviewQueue.length} 项`
        : "证据门槛待补";
  const verificationDetail =
    guardedReasonLabels.slice(0, 2).join(" / ") ||
    weakSections[0]?.insufficiency_summary ||
    readiness?.next_verification_steps?.[0] ||
    reviewQueue[0]?.summary ||
    reviewQueue[0]?.recommended_action ||
    "优先补官方源、账户支撑和关键章节的交叉验证。";
  const retrievalRoutingCards = [
    {
      title: "范围锁定",
      value: scopeClients.length
        ? `账户 ${scopeClients.length} 个`
        : scopeRegions.length || scopeIndustries.length
          ? "已限定范围"
          : "范围仍偏泛",
      detail:
        followupFilters.slice(0, 3).join(" / ") ||
        dedupeTextList([...scopeRegions, ...scopeIndustries, ...scopeClients]).slice(0, 3).join(" / ") ||
        "当前仍待继续收敛到区域、行业或目标账户。",
      tone: "border-sky-100/90 bg-sky-50/78 text-sky-900",
    },
    {
      title: "查询策略",
      value: diagnostics?.quality_expansion_triggered
        ? `质量扩源 ${diagnostics.quality_expansion_rounds || 1} 轮`
        : diagnostics?.strategy_query_expansion_count
          ? `扩展 ${diagnostics.strategy_query_expansion_count} 条`
          : followupDiagnostics?.decomposition_queries?.length
            ? `追问拆出 ${followupDiagnostics.decomposition_queries.length} 条`
            : "基础来源整理",
      detail:
        qualityExpansionNotes[0] ||
        (diagnostics?.quality_expansion_triggered
          ? `新增 ${diagnostics.quality_expansion_added_source_count || 0} 条公开来源，综合所有来源后再生成材料。`
          : "") ||
        followupDiagnostics?.summary ||
        diagnostics?.strategy_scope_summary ||
        "已结合多个公开来源整理报告，并突出关键章节和依据。",
      tone: "border-violet-100/90 bg-violet-50/78 text-violet-900",
    },
    {
      title: "账户支撑",
      value: unsupportedTargetAccounts.length
        ? `待核验 ${unsupportedTargetAccounts.length} 个`
        : supportedTargetAccounts.length
          ? `已支撑 ${supportedTargetAccounts.length} 个`
          : "未锁定账户",
      detail: targetSupportDetail,
      tone: unsupportedTargetAccounts.length
        ? "border-rose-100/90 bg-rose-50/82 text-rose-900"
        : "border-emerald-100/90 bg-emerald-50/78 text-emerald-900",
    },
    {
      title: "证据门槛",
      value: verificationValue,
      detail: verificationDetail,
      tone: guardedBacklog || !readiness?.evidence_gate_passed
        ? "border-amber-100/90 bg-amber-50/82 text-amber-900"
        : "border-emerald-100/90 bg-emerald-50/78 text-emerald-900",
    },
  ];
  const pipelineStages = diagnostics?.pipeline_stages || [];

  return {
    architectureReadiness,
    architectureReadinessState,
    architectWorkbench,
    candidateProfileCompanies,
    candidateProfileSourceLabels,
    commercialSummary,
    coreEntities,
    diagnostics,
    enabledSourceLabels,
    evidenceMode,
    followupDiagnostics,
    followupImpactedSections,
    followupSummaryResolution,
    followupTitleResolution,
    groupedSources,
    guardedBacklog,
    guardedReasonLabels,
    marketIntelligence,
    matchedSourceLabels,
    matchedThemeLabels,
    pipelineStages,
    primaryCustomerScenario,
    projectProposalQuality,
    projectProposalQualityMeta,
    qualityExpansionQueries,
    qualityProfile,
    qualityProfileState,
    readiness,
    readinessState,
    reportSurfaceCopy,
    retrievalRoutingCards,
    reviewQueue,
    scopeClients,
    scopeIndustries,
    scopeRegions,
    solutionDeliveryPack,
    solutionDeliveryQuality,
    solutionDeliveryQualityMeta,
    supportedTargetAccounts,
    targetSupportDetail,
    targetSupportTone,
    targetSupportValue,
    technicalAppendix,
    topicAnchorTerms,
    unsupportedTargetAccounts,
    verificationDetail,
    verificationTone,
    verificationValue,
    weakSections,
  };
}
