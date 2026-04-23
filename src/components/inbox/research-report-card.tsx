"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { ApiResearchReport } from "@/lib/api";
import { dedupeByKey, dedupeTextList } from "@/lib/display-list";
import { getGuardedRewriteReasonLabels, isGuardedBacklog } from "@/lib/research-diagnostics";
import { ExternalLinkActions, normalizeExternalUrl } from "@/components/ui/external-link-actions";

type ResearchReportCardProps = {
  report: ApiResearchReport;
  titleLabel: string;
  summaryLabel: string;
  angleLabel: string;
  queryPlanLabel: string;
  sourcesLabel: string;
  sourceCountLabel: string;
  generatedAtLabel: string;
  saveLabel: string;
  focusSaveLabel: string;
  exportLabel: string;
  exportWordLabel: string;
  exportPdfLabel: string;
  savedLabel: string;
  actionMessage?: string;
  knowledgeHref?: string | null;
  saving?: boolean;
  savingAsFocus?: boolean;
  exporting?: boolean;
  exportingWord?: boolean;
  exportingPdf?: boolean;
  onSave?: () => void;
  onSaveAsFocus?: () => void;
  onExport?: () => void;
  onExportWord?: () => void;
  onExportPdf?: () => void;
  hideSources?: boolean;
  actionCardSlot?: ReactNode;
};

export function ResearchReportCard({
  report,
  titleLabel,
  summaryLabel,
  angleLabel,
  queryPlanLabel,
  sourcesLabel,
  sourceCountLabel,
  generatedAtLabel,
  saveLabel,
  focusSaveLabel,
  exportLabel,
  exportWordLabel,
  exportPdfLabel,
  savedLabel,
  actionMessage,
  knowledgeHref,
  saving,
  savingAsFocus,
  exporting,
  exportingWord,
  exportingPdf,
  onSave,
  onSaveAsFocus,
  onExport,
  onExportWord,
  onExportPdf,
  hideSources = false,
  actionCardSlot,
}: ResearchReportCardProps) {
  const pendingRankedEntities = (role: "target" | "competitor" | "partner") => {
    const sourceMap = {
      target: report.pending_target_candidates || [],
      competitor: report.pending_competitor_candidates || [],
      partner: report.pending_partner_candidates || [],
    };
    return dedupeByKey(sourceMap[role], (item) => String(item?.name || "").trim(), 3);
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
        label: "强证据",
        className: "border-emerald-200/90 bg-emerald-50 text-emerald-800",
        note: "当前结果有较稳定的主题命中、官方源和多域名交叉支撑。",
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
      label: "兜底候选",
      className: "border-slate-200/90 bg-slate-100 text-slate-700",
      note: "当前更像高价值候选，不应直接视为最终结论。",
    };
  };
  const readinessMeta = (value: string) => {
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
        note: "当前可用于初轮判断和内部讨论，但仍建议先补证再做强结论。",
      };
    }
    return {
      label: "待补证",
      className: "border-slate-200/90 bg-slate-100 text-slate-700",
      note: "当前更适合作为候选名单与待补证路径，不宜直接当作最终商业判断。",
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
  const sectionStatusMeta = (value?: string) => {
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
      label: "章节待补证",
      className: "bg-rose-100 text-rose-700",
    };
  };
  const sourceTierLabel = (value: string) => {
    if (value === "official") return "官方源";
    if (value === "aggregate") return "聚合源";
    return "媒体源";
  };
  const valueBucket = (score: number) => {
    if (score >= 75) return { label: "高价值", className: "bg-emerald-100 text-emerald-700" };
    if (score >= 55) return { label: "普通价值", className: "bg-amber-100 text-amber-700" };
    return { label: "低价值", className: "bg-slate-100 text-slate-500" };
  };
  const factorBucket = (score: number) => {
    if (score >= 14) return { label: "强支撑", className: "bg-emerald-100 text-emerald-700" };
    if (score >= 6) return { label: "中支撑", className: "bg-amber-100 text-amber-700" };
    if (score > 0) return { label: "弱支撑", className: "bg-sky-100 text-sky-700" };
    if (score < 0) return { label: "风险提示", className: "bg-rose-100 text-rose-700" };
    return { label: "待补证据", className: "bg-slate-100 text-slate-500" };
  };
  const hasStrategicPanels =
    report.target_accounts.length ||
    report.target_departments.length ||
    report.public_contact_channels.length ||
    report.account_team_signals.length ||
    report.budget_signals.length ||
    report.project_distribution.length ||
    report.strategic_directions.length ||
    report.tender_timeline.length ||
    report.leadership_focus.length ||
    report.ecosystem_partners.length ||
    report.competitor_profiles.length ||
    report.benchmark_cases.length ||
    report.flagship_products.length ||
    report.key_people.length ||
    report.five_year_outlook.length ||
    report.client_peer_moves.length ||
    report.winner_peer_moves.length ||
    report.competition_analysis.length;

  const highlightPanels = [
    { title: "重点甲方", items: report.target_accounts, tone: "sky" },
    { title: "高概率决策部门", items: report.target_departments, tone: "slate" },
    { title: "公开业务联系方式", items: report.public_contact_channels, tone: "slate" },
    { title: "目标区域活跃团队", items: report.account_team_signals, tone: "sky" },
    { title: "预算与投资信号", items: report.budget_signals, tone: "emerald" },
    { title: "项目分布与期次", items: report.project_distribution, tone: "emerald" },
    { title: "战略方向", items: report.strategic_directions, tone: "violet" },
    { title: "招标时间预测", items: report.tender_timeline, tone: "violet" },
    { title: "领导关注点", items: report.leadership_focus, tone: "slate" },
    { title: "活跃生态伙伴", items: report.ecosystem_partners, tone: "sky" },
    { title: "竞品公司概况", items: report.competitor_profiles, tone: "amber" },
    { title: "标杆案例", items: report.benchmark_cases, tone: "emerald" },
    { title: "明星产品/方案", items: report.flagship_products, tone: "violet" },
    { title: "关键人物", items: report.key_people, tone: "slate" },
  ].filter((panel) => panel.items.length);

  const toneClasses: Record<string, string> = {
    sky: "border-sky-100/90 bg-sky-50/80 text-sky-950 [&_.af-panel-kicker]:text-sky-500 [&_.af-bullet]:bg-sky-300",
    amber:
      "border-amber-100/90 bg-amber-50/80 text-amber-950 [&_.af-panel-kicker]:text-amber-600 [&_.af-bullet]:bg-amber-300",
    emerald:
      "border-emerald-100/90 bg-emerald-50/80 text-emerald-950 [&_.af-panel-kicker]:text-emerald-600 [&_.af-bullet]:bg-emerald-300",
    violet:
      "border-violet-100/90 bg-violet-50/80 text-violet-950 [&_.af-panel-kicker]:text-violet-600 [&_.af-bullet]:bg-violet-300",
    slate:
      "border-white/80 bg-[linear-gradient(180deg,rgba(248,251,255,0.9),rgba(241,245,249,0.68))] text-slate-700 [&_.af-panel-kicker]:text-slate-400 [&_.af-bullet]:bg-slate-300",
  };
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
  const candidateProfileCompanies = dedupeTextList(diagnostics?.candidate_profile_companies || []);
  const candidateProfileSourceLabels = dedupeTextList(diagnostics?.candidate_profile_source_labels || []);
  const coreEntities = dedupeByKey(report.entity_graph?.entities || [], (entity) => String(entity?.canonical_name || "").trim(), 6);
  const readiness = report.report_readiness;
  const readinessState = readinessMeta(readiness?.status || "needs_evidence");
  const commercialSummary = report.commercial_summary;
  const technicalAppendix = report.technical_appendix;
  const reviewQueue = report.review_queue || [];
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
      : "border-slate-200/90 bg-slate-100 text-slate-600";
  const targetSupportValue = unsupportedTargetAccounts.length
    ? "目标账户待补证"
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
      value: diagnostics?.strategy_query_expansion_count
        ? `扩展 ${diagnostics.strategy_query_expansion_count} 条`
        : followupDiagnostics?.decomposition_queries?.length
          ? `追问拆出 ${followupDiagnostics.decomposition_queries.length} 条`
          : "基础混合检索",
      detail:
        followupDiagnostics?.summary ||
        diagnostics?.strategy_scope_summary ||
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
  const reportSurfaceCopy = {
    readinessTitle: "推进就绪度",
    playbookTitle: "推进要点",
    appendixTitle: "方法与边界",
    reviewQueueTitle: "待核验结论",
    reviewQueueDesc: "把冲突结论、弱证据章节和关键缺口集中出来，优先做二次核验。",
    insightsTitle: "深度洞察",
    insightsDesc: "按主题继续展开关键判断、证据锚点与补证建议。",
    sourcePathTitle: "情报路径",
    sourceDiagTitle: "证据诊断",
  };
  const pipelineStages = diagnostics?.pipeline_stages || [];
  const rankedPanels = [
    {
      title: (report.top_target_accounts && report.top_target_accounts.length) ? "高价值甲方 Top 3" : "待补证甲方候选",
      items: dedupeByKey(
        (report.top_target_accounts && report.top_target_accounts.length)
          ? report.top_target_accounts
          : pendingRankedEntities("target"),
        (entity) => String(entity?.name || "").trim(),
        3,
      ),
      tone: "sky",
    },
    {
      title: (report.top_competitors && report.top_competitors.length) ? "高威胁竞品 Top 3" : "待补证竞品候选",
      items: dedupeByKey(
        (report.top_competitors && report.top_competitors.length)
          ? report.top_competitors
          : pendingRankedEntities("competitor"),
        (entity) => String(entity?.name || "").trim(),
        3,
      ),
      tone: "amber",
    },
    {
      title: (report.top_ecosystem_partners && report.top_ecosystem_partners.length) ? "高影响力生态伙伴 Top 3" : "待补证伙伴候选",
      items: dedupeByKey(
        (report.top_ecosystem_partners && report.top_ecosystem_partners.length)
          ? report.top_ecosystem_partners
          : pendingRankedEntities("partner"),
        (entity) => String(entity?.name || "").trim(),
        3,
      ),
      tone: "emerald",
    },
  ].filter((panel) => panel.items.length);

  return (
    <section data-testid="research-report-card" className="af-report-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="af-kicker">{titleLabel}</p>
          <h3 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-slate-900">
            {report.report_title}
          </h3>
          <p className="mt-2 text-sm text-slate-500">
            {sourceCountLabel} {report.source_count}
            {report.generated_at ? ` · ${generatedAtLabel} ${new Date(report.generated_at).toLocaleString()}` : ""}
          </p>
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            <span className={`rounded-full px-2.5 py-1 ${qualityTone(report.evidence_density)}`}>
              证据密度 · {qualityLabel(report.evidence_density)}
            </span>
            <span className={`rounded-full px-2.5 py-1 ${qualityTone(report.source_quality)}`}>
              来源质量 · {qualityLabel(report.source_quality)}
            </span>
            {guardedBacklog ? (
              <span className="rounded-full bg-rose-100 px-2.5 py-1 text-rose-700">
                Guarded backlog
              </span>
            ) : null}
          </div>
        </div>

        <div className="flex w-full flex-wrap gap-2 xl:pt-1">
          {onSave ? (
            <button
              type="button"
              onClick={onSave}
              disabled={saving}
              className="af-btn af-btn-secondary border px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? `${saveLabel}...` : saveLabel}
            </button>
          ) : null}
          {onSaveAsFocus ? (
            <button
              type="button"
              onClick={onSaveAsFocus}
              disabled={savingAsFocus}
              className="af-btn af-btn-secondary border px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {savingAsFocus ? `${focusSaveLabel}...` : focusSaveLabel}
            </button>
          ) : null}
          {onExport ? (
            <button
              type="button"
              onClick={onExport}
              disabled={exporting}
              className="af-btn af-btn-primary px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {exporting ? `${exportLabel}...` : exportLabel}
            </button>
          ) : null}
          {onExportWord ? (
            <button
              type="button"
              onClick={onExportWord}
              disabled={exportingWord}
              className="af-btn af-btn-secondary border px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {exportingWord ? `${exportWordLabel}...` : exportWordLabel}
            </button>
          ) : null}
          {onExportPdf ? (
            <button
              type="button"
              onClick={onExportPdf}
              disabled={exportingPdf}
              className="af-btn af-btn-secondary border px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {exportingPdf ? `${exportPdfLabel}...` : exportPdfLabel}
            </button>
          ) : null}
          {knowledgeHref ? (
            <Link href={knowledgeHref} className="af-btn af-btn-secondary border px-4 py-2">
              {savedLabel}
            </Link>
          ) : null}
        </div>
        {actionMessage ? <p className="w-full text-sm text-slate-500">{actionMessage}</p> : null}
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <article className="af-report-muted-surface rounded-2xl border border-white/80 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">证据档位</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${evidenceMode.className}`}>
              {diagnostics?.evidence_mode_label || evidenceMode.label}
            </span>
            <span className={`rounded-full px-2.5 py-1 text-xs ${qualityTone(report.evidence_density)}`}>
              证据密度 · {qualityLabel(report.evidence_density)}
            </span>
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-600">{evidenceMode.note}</p>
        </article>
        <article className="af-report-muted-surface rounded-2xl border border-white/80 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">目标账户支撑</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${targetSupportTone}`}>
              {targetSupportValue}
            </span>
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-600">{targetSupportDetail}</p>
        </article>
        <article className="af-report-muted-surface rounded-2xl border border-white/80 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">交叉验证</p>
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            <span className="rounded-full bg-white px-2.5 py-1 text-slate-600">
              官方源 {Math.round((diagnostics?.official_source_ratio || 0) * 100)}%
            </span>
            <span className="rounded-full bg-white px-2.5 py-1 text-slate-600">
              严格命中 {Math.round((diagnostics?.strict_match_ratio || 0) * 100)}%
            </span>
            {diagnostics?.unique_domain_count ? (
              <span className="rounded-full bg-white px-2.5 py-1 text-slate-600">
                域名 {diagnostics.unique_domain_count}
              </span>
            ) : null}
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            {diagnostics?.candidate_profile_official_hit_count
              ? `候选实例补证命中 ${diagnostics.candidate_profile_official_hit_count} 条官方资料。`
              : "当前以公开网页和主题交叉命中为主，仍可继续补官方资料。"}
          </p>
        </article>
        <article className="af-report-muted-surface rounded-2xl border border-white/80 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">待核验 / 门槛</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${verificationTone}`}>
              {verificationValue}
            </span>
            {readiness ? (
              <span className="rounded-full bg-white px-2.5 py-1 text-xs text-slate-600">
                就绪度 {readiness.score}
              </span>
            ) : null}
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-600">{verificationDetail}</p>
        </article>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
        <div className="af-report-surface rounded-2xl border border-sky-100/80 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{summaryLabel}</p>
          <p className="mt-3 text-[15px] leading-7 text-slate-700">{report.executive_summary}</p>
        </div>
        <div className="af-report-surface rounded-2xl border border-cyan-100/90 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-500">{angleLabel}</p>
          <p className="mt-3 text-sm leading-6 text-sky-900">{report.consulting_angle}</p>
        </div>
      </div>

      {(readiness || commercialSummary) ? (
        <div className="mt-5 grid gap-4 lg:grid-cols-[0.92fr_1.08fr]">
          {readiness ? (
            <article className="af-report-muted-surface rounded-2xl border border-white/80 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{reportSurfaceCopy.readinessTitle}</p>
                  <p className="mt-2 text-sm text-slate-500">{readinessState.note}</p>
                </div>
                <div className="flex flex-wrap gap-2 text-xs">
                  <span className={`rounded-full border px-2.5 py-1 ${readinessState.className}`}>
                    {readinessState.label}
                  </span>
                  <span className="rounded-full bg-white px-2.5 py-1 text-slate-700">
                    评分 {readiness.score}
                  </span>
                  <span className={`rounded-full px-2.5 py-1 ${readiness.evidence_gate_passed ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
                    {readiness.evidence_gate_passed ? "证据门槛已通过" : "证据门槛待补"}
                  </span>
                </div>
              </div>
              {readiness.reasons?.length ? (
                <div className="mt-4 space-y-2">
                  {readiness.reasons.map((reason) => (
                    <div key={`readiness-reason-${reason}`} className="rounded-2xl border border-slate-200/80 bg-white/86 px-3 py-2 text-sm leading-6 text-slate-700">
                      {reason}
                    </div>
                  ))}
                </div>
              ) : null}
              {(readiness.missing_axes?.length || readiness.next_verification_steps?.length) ? (
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  {readiness.missing_axes?.length ? (
                    <div className="rounded-2xl border border-amber-100/90 bg-amber-50/80 p-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-700">仍缺关键维度</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {readiness.missing_axes.map((value) => (
                          <span key={`readiness-axis-${value}`} className="rounded-full bg-white/88 px-2.5 py-1 text-[11px] text-amber-800">
                            {value}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {readiness.next_verification_steps?.length ? (
                    <div className="rounded-2xl border border-slate-200/80 bg-white/84 p-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">下一步补证</p>
                      <ul className="mt-2 space-y-2 text-sm leading-6 text-slate-600">
                        {readiness.next_verification_steps.slice(0, 3).map((value) => (
                          <li key={`readiness-step-${value}`} className="flex gap-2">
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
            <article className="af-report-surface rounded-2xl border border-cyan-100/90 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-500">{reportSurfaceCopy.playbookTitle}</p>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <div className="rounded-2xl border border-white/80 bg-white/84 p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">重点账户</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {(commercialSummary.account_focus || []).length ? (
                      commercialSummary.account_focus.map((value) => (
                        <span key={`commercial-account-${value}`} className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] text-sky-700">
                          {value}
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-slate-500">仍待收敛到账户对象</span>
                    )}
                  </div>
                </div>
                <div className="rounded-2xl border border-white/80 bg-white/84 p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">预算与信号</p>
                  <p className="mt-2 text-sm leading-6 text-slate-700">{commercialSummary.budget_signal || "当前仍缺直接预算或采购信号"}</p>
                </div>
                <div className="rounded-2xl border border-white/80 bg-white/84 p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">推进窗口</p>
                  <p className="mt-2 text-sm leading-6 text-slate-700">{commercialSummary.entry_window || "当前仍缺明确进入窗口"}</p>
                </div>
                <div className="rounded-2xl border border-white/80 bg-white/84 p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">竞合与伙伴</p>
                  <p className="mt-2 text-sm leading-6 text-slate-700">{commercialSummary.competition_or_partner || "当前仍需补竞品或伙伴格局"}</p>
                </div>
              </div>
              <div className="mt-3 rounded-2xl border border-sky-100/90 bg-white/84 p-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">下一步推进</p>
                <p className="mt-2 text-sm leading-6 text-sky-900">{commercialSummary.next_action || "继续补组织入口、预算和进入窗口后再生成行动卡。"}</p>
              </div>
            </article>
          ) : null}
        </div>
      ) : null}

      {weakSections.length ? (
        <div className="mt-5 rounded-2xl border border-amber-200/80 bg-amber-50/78 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-amber-700">关键补证章节</p>
              <p className="mt-1 text-sm text-amber-900">
                先处理最弱章节，再决定是否进入正式推进和导出。
              </p>
            </div>
            <span className="rounded-full bg-white/90 px-2.5 py-1 text-xs text-amber-800">
              {weakSections.length} 个章节待收紧
            </span>
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            {weakSections.map((section) => {
              const statusMeta = sectionStatusMeta(section.status);
              return (
                <div key={`weak-section-${section.title}`} className="rounded-2xl border border-white/90 bg-white/84 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-slate-900">{section.title}</p>
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${statusMeta.className}`}>
                      {statusMeta.label}
                    </span>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-slate-600">
                    {section.insufficiency_summary || section.quota_note || section.confidence_reason || "当前章节仍需继续补证。"}
                  </p>
                  {section.next_verification_steps?.length ? (
                    <p className="mt-2 text-xs leading-5 text-amber-800">
                      下一步：{section.next_verification_steps[0]}
                    </p>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      {actionCardSlot ? <div className="mt-5">{actionCardSlot}</div> : null}

      {hasStrategicPanels ? (
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          {report.five_year_outlook.length ? (
            <article className="rounded-2xl border border-sky-100/90 bg-sky-50/80 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-500">
                未来五年演化判断
              </p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-sky-950">
                {report.five_year_outlook.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-sky-300" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </article>
          ) : null}
          {report.competition_analysis.length ? (
            <article className="rounded-2xl border border-amber-100/90 bg-amber-50/80 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-amber-600">
                竞争分析
              </p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-amber-950">
                {report.competition_analysis.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-amber-300" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </article>
          ) : null}
        </div>
      ) : null}

      {rankedPanels.length ? (
        <div className="mt-5 grid gap-4 xl:grid-cols-3">
          {rankedPanels.map((panel) => (
            <article
              key={panel.title}
              className={`rounded-2xl border p-4 ${toneClasses[panel.tone] || toneClasses.slate}`}
            >
              <p className="af-panel-kicker text-xs font-semibold uppercase tracking-[0.22em]">
                {panel.title}
              </p>
              <div className="mt-3 space-y-3">
                {panel.items.map((entity) => (
                  <div
                    key={`${panel.title}-${entity.name}`}
                    className="rounded-2xl border border-white/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.82),rgba(246,249,252,0.72))] p-3"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <h4 className="text-sm font-semibold text-slate-900">{entity.name}</h4>
                      <span className={`rounded-full px-2 py-0.5 text-[11px] ${valueBucket(entity.score).className}`}>
                        {valueBucket(entity.score).label}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-700">{entity.reasoning}</p>
                    {entity.score_breakdown?.length ? (
                      <div className="mt-3 grid gap-2">
                        {entity.score_breakdown.slice(0, 3).map((factor) => (
                          <div
                            key={`${entity.name}-${factor.label}`}
                            className="rounded-2xl border border-slate-200/80 bg-slate-50/82 px-3 py-2"
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
                            className="block rounded-2xl border border-slate-200/80 bg-slate-50/76 px-3 py-2 transition hover:border-slate-300 hover:bg-white/82"
                          >
                            <div className="flex flex-wrap items-center gap-2">
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

      {(report.client_peer_moves.length || report.winner_peer_moves.length) ? (
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          {report.client_peer_moves.length ? (
            <article className="rounded-2xl border border-white/80 bg-[linear-gradient(180deg,rgba(248,251,255,0.88),rgba(240,245,249,0.7))] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                甲方同行 Top 3 动态
              </p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
                {report.client_peer_moves.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-slate-300" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </article>
          ) : null}
          {report.winner_peer_moves.length ? (
            <article className="rounded-2xl border border-white/80 bg-[linear-gradient(180deg,rgba(248,251,255,0.88),rgba(240,245,249,0.7))] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                中标方同行 Top 3 动态
              </p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
                {report.winner_peer_moves.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-slate-300" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </article>
          ) : null}
        </div>
      ) : null}

      {highlightPanels.length ? (
        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {highlightPanels.map((panel) => (
            <article
              key={panel.title}
              className={`rounded-2xl border p-4 ${toneClasses[panel.tone] || toneClasses.slate}`}
            >
              <p className="af-panel-kicker text-xs font-semibold uppercase tracking-[0.22em]">{panel.title}</p>
              <ul className="mt-3 space-y-2 text-sm leading-6">
                {panel.items.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className="af-bullet mt-[7px] h-1.5 w-1.5 rounded-full" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      ) : null}

      <div className={`mt-6 grid gap-4 ${hideSources ? "md:grid-cols-1" : "md:grid-cols-[1.15fr_0.85fr]"}`}>
        <div className="af-report-muted-surface rounded-2xl border border-white/80 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{reportSurfaceCopy.sourcePathTitle}</p>
          <div className="mt-3">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
              {queryPlanLabel}
            </p>
            <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
              {report.query_plan.map((query) => (
                <li key={query} className="rounded-2xl border border-slate-200/70 bg-slate-50/70 px-3 py-2">
                  {query}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {!hideSources ? (
        <div className="af-report-muted-surface rounded-2xl border border-white/80 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{sourcesLabel}</p>
          {diagnostics ? (
            <div className="mt-3 rounded-2xl border border-slate-200/80 bg-slate-50/80 p-3">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{reportSurfaceCopy.sourceDiagTitle}</p>
              <div className={`mt-3 rounded-2xl border px-3.5 py-3 ${evidenceMode.className}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-white/80 px-2.5 py-1 text-[11px] font-semibold">
                    {diagnostics.evidence_mode_label || evidenceMode.label}
                  </span>
                  {diagnostics.corrective_triggered ? (
                    <span className="rounded-full bg-white/80 px-2.5 py-1 text-[11px]">
                      已触发纠错检索
                    </span>
                  ) : null}
                  {diagnostics.expansion_triggered ? (
                    <span className="rounded-full bg-white/80 px-2.5 py-1 text-[11px]">
                      已触发扩搜补证
                    </span>
                  ) : null}
                </div>
                <p className="mt-2 text-xs leading-5">
                  {evidenceMode.note}
                </p>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  {retrievalRoutingCards.map((card) => (
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
                  <div className="af-report-stage-grid mt-3">
                    {pipelineStages.map((stage) => (
                      <div key={stage.key} className="af-report-stage-card">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                          {stage.label}
                        </p>
                        <p className="af-report-stage-value">{stage.value}</p>
                        <p className="af-report-stage-summary">{stage.summary}</p>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                <span className="rounded-full bg-white px-2.5 py-1 text-slate-600">
                  启用源 {enabledSourceLabels.length}
                </span>
                <span className="rounded-full bg-white px-2.5 py-1 text-slate-600">
                  命中爬虫源 {diagnostics.adapter_hit_count}
                </span>
                <span className="rounded-full bg-white px-2.5 py-1 text-slate-600">
                  命中搜索源 {diagnostics.search_hit_count}
                </span>
                <span className="rounded-full bg-white px-2.5 py-1 text-slate-600">
                  近 {diagnostics.recency_window_years} 年窗口
                </span>
                {diagnostics.filtered_old_source_count > 0 ? (
                  <span className="rounded-full bg-white px-2.5 py-1 text-slate-600">
                    剔除过旧来源 {diagnostics.filtered_old_source_count}
                  </span>
                ) : null}
                {diagnostics.filtered_region_conflict_count > 0 ? (
                  <span className="rounded-full bg-rose-50 px-2.5 py-1 text-rose-700">
                    拦截越界区域 {diagnostics.filtered_region_conflict_count}
                  </span>
                ) : null}
                {diagnostics.strict_topic_source_count > 0 ? (
                  <span className="rounded-full bg-white px-2.5 py-1 text-slate-600">
                    严格主题保留 {diagnostics.strict_topic_source_count}
                  </span>
                ) : null}
                <span className="rounded-full bg-white px-2.5 py-1 text-slate-600">
                  检索质量 {qualityLabel(diagnostics.retrieval_quality)}
                </span>
                <span className="rounded-full bg-white px-2.5 py-1 text-slate-600">
                  严格命中 {Math.round(diagnostics.strict_match_ratio * 100)}%
                </span>
                <span className="rounded-full bg-white px-2.5 py-1 text-slate-600">
                  官方源 {Math.round(diagnostics.official_source_ratio * 100)}%
                </span>
                {diagnostics.unique_domain_count > 0 ? (
                  <span className="rounded-full bg-white px-2.5 py-1 text-slate-600">
                    覆盖域名 {diagnostics.unique_domain_count}
                  </span>
                ) : null}
                {candidateProfileCompanies.length ? (
                  <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
                    候选补证公司 {candidateProfileCompanies.length}
                  </span>
                ) : null}
                {diagnostics.candidate_profile_hit_count > 0 ? (
                  <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
                    补证公开源 {diagnostics.candidate_profile_hit_count}
                  </span>
                ) : null}
                {diagnostics.candidate_profile_official_hit_count > 0 ? (
                  <span className="rounded-full bg-cyan-50 px-2.5 py-1 text-cyan-700">
                    其中官方源 {diagnostics.candidate_profile_official_hit_count}
                  </span>
                ) : null}
                {guardedBacklog ? (
                  <span className="rounded-full bg-rose-50 px-2.5 py-1 text-rose-700">
                    已降级为 guarded backlog
                  </span>
                ) : null}
              </div>
              {guardedReasonLabels.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">降级原因</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {guardedReasonLabels.map((label) => (
                      <span key={label} className="rounded-full border border-rose-200 bg-rose-50 px-2.5 py-1 text-xs text-rose-700">
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {supportedTargetAccounts.length || unsupportedTargetAccounts.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">目标账户支撑</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {supportedTargetAccounts.map((label) => (
                      <span key={`supported-${label}`} className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs text-emerald-700">
                        已支撑 · {label}
                      </span>
                    ))}
                    {unsupportedTargetAccounts.map((label) => (
                      <span key={`unsupported-${label}`} className="rounded-full border border-rose-200 bg-rose-50 px-2.5 py-1 text-xs text-rose-700">
                        未支撑 · {label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {diagnostics.normalized_entity_count > 0 ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">实体归一化</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <span className="rounded-full border border-violet-200 bg-violet-50 px-2.5 py-1 text-xs text-violet-700">
                      总实体 {diagnostics.normalized_entity_count}
                    </span>
                    <span className="rounded-full border border-violet-200 bg-violet-50 px-2.5 py-1 text-xs text-violet-700">
                      甲方 {diagnostics.normalized_target_count}
                    </span>
                    <span className="rounded-full border border-violet-200 bg-violet-50 px-2.5 py-1 text-xs text-violet-700">
                      竞品 {diagnostics.normalized_competitor_count}
                    </span>
                    <span className="rounded-full border border-violet-200 bg-violet-50 px-2.5 py-1 text-xs text-violet-700">
                      伙伴 {diagnostics.normalized_partner_count}
                    </span>
                  </div>
                </div>
              ) : null}
              {report.entity_graph?.entities?.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">核心实体候选</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {coreEntities.map((entity) => (
                      <span
                        key={`entity-${entity.canonical_name}`}
                        className="rounded-full border border-fuchsia-200 bg-fuchsia-50 px-2.5 py-1 text-xs text-fuchsia-700"
                      >
                        {entity.canonical_name}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {enabledSourceLabels.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">当前启用</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {enabledSourceLabels.map((label) => (
                      <span key={label} className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600">
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {scopeRegions.length || scopeIndustries.length || scopeClients.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">范围锁定</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {scopeRegions.map((label) => (
                      <span key={`scope-region-${label}`} className="rounded-full border border-cyan-200 bg-cyan-50 px-2.5 py-1 text-xs text-cyan-700">
                        区域 · {label}
                      </span>
                    ))}
                    {scopeIndustries.map((label) => (
                      <span key={`scope-industry-${label}`} className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs text-blue-700">
                        领域 · {label}
                      </span>
                    ))}
                    {scopeClients.map((label) => (
                      <span key={`scope-client-${label}`} className="rounded-full border border-fuchsia-200 bg-fuchsia-50 px-2.5 py-1 text-xs text-fuchsia-700">
                        公司 · {label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {matchedSourceLabels.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">本次命中</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {matchedSourceLabels.map((label) => (
                      <span key={label} className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs text-sky-700">
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {topicAnchorTerms.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">主题锚点</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {topicAnchorTerms.map((label) => (
                      <span key={label} className="rounded-full border border-violet-200 bg-violet-50 px-2.5 py-1 text-xs text-violet-700">
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {matchedThemeLabels.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">命中主题</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {matchedThemeLabels.map((label) => (
                      <span key={label} className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs text-emerald-700">
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {candidateProfileCompanies.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">候选补证公司</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {candidateProfileCompanies.map((label) => (
                      <span key={label} className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs text-sky-700">
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {candidateProfileSourceLabels.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">补证命中源</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {candidateProfileSourceLabels.map((label) => (
                      <span key={label} className="rounded-full border border-cyan-200 bg-cyan-50 px-2.5 py-1 text-xs text-cyan-700">
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}
          <div className="mt-3 space-y-3">
            {report.sources.length === 0 ? (
              <p className="text-sm leading-6 text-slate-500">当前未获取到可展示来源，显示的是本地演示框架。</p>
            ) : null}
            {[
              { key: "official", title: "官方源", items: groupedSources.official },
              { key: "media", title: "媒体源", items: groupedSources.media },
              { key: "aggregate", title: "聚合源", items: groupedSources.aggregate },
            ]
              .filter((group) => group.items.length)
              .map((group) => (
                <div key={group.key} className="rounded-2xl border border-slate-200/80 bg-slate-50/70 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{group.title}</p>
                    <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-500">
                      {group.items.length}
                    </span>
                  </div>
                  <div className="mt-3 space-y-3">
                    {group.items.map((source) => (
                      <div
                        key={`${group.key}-${source.url}-${source.search_query}`}
                        className="block rounded-2xl border border-slate-200/80 bg-white/85 p-3 transition hover:border-slate-300 hover:bg-white"
                      >
                        <div className="flex items-center gap-2 text-xs text-slate-500">
                          <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5">
                            {sourceTierLabel(source.source_tier || classifySourceTier(source))}
                          </span>
                          {source.source_label ? (
                            <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5">
                              {source.source_label}
                            </span>
                          ) : null}
                          <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5">
                            {source.domain || "web"}
                          </span>
                          <span>{source.search_query}</span>
                        </div>
                        <a
                          href={normalizeExternalUrl(source.url)}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-2 block text-sm font-semibold leading-6 text-slate-900 underline-offset-4 hover:text-sky-800 hover:underline"
                        >
                          {source.title}
                        </a>
                        <p className="mt-1 text-sm leading-6 text-slate-600">{source.snippet}</p>
                        <ExternalLinkActions
                          url={source.url}
                          className="mt-3"
                          openLabel="网页打开"
                        />
                      </div>
                    ))}
                  </div>
                </div>
              ))}
          </div>
        </div>
        ) : null}
      </div>

      {report.sections.length > 0 ? (
        <div className="mt-5">
          <div className="mb-3">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{reportSurfaceCopy.insightsTitle}</p>
            <p className="mt-1 text-sm text-slate-500">{reportSurfaceCopy.insightsDesc}</p>
          </div>
        <div className="grid gap-4 md:grid-cols-2">
          {report.sections.map((section) => {
            const tone = confidenceToneMeta(section.confidence_tone);
            const statusMeta = sectionStatusMeta(section.status);
            return (
            <article
              key={section.title}
              className={`rounded-2xl border p-4 ${tone.panel}`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h4 className="text-sm font-semibold text-slate-900">{section.title}</h4>
                <div className="flex flex-wrap gap-2 text-[11px]">
                  {section.confidence_label ? (
                    <span className={`rounded-full px-2 py-0.5 ${tone.badge}`}>
                      {section.confidence_label}
                    </span>
                  ) : null}
                  <span className={`rounded-full px-2 py-0.5 ${statusMeta.className}`}>
                    {statusMeta.label}
                  </span>
                  <span className={`rounded-full px-2 py-0.5 ${qualityTone(section.evidence_density || "low")}`}>
                    证据密度·{qualityLabel(section.evidence_density || "low")}
                  </span>
                  <span className={`rounded-full px-2 py-0.5 ${qualityTone(section.source_quality || "low")}`}>
                    来源质量·{qualityLabel(section.source_quality || "low")}
                  </span>
                  {section.official_source_ratio ? (
                    <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-emerald-700">
                      官方源·{Math.round(section.official_source_ratio * 100)}%
                    </span>
                  ) : null}
                  {typeof section.evidence_quota === "number" && section.evidence_quota > 0 ? (
                    <span
                      className={`rounded-full px-2 py-0.5 ${
                        section.meets_evidence_quota
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-amber-50 text-amber-700"
                      }`}
                    >
                      配额 {section.evidence_count || 0}/{section.evidence_quota}
                    </span>
                  ) : null}
                </div>
              </div>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
                {section.items.map((item) => (
                  <li key={item} className={`flex gap-2 rounded-xl px-2 py-1.5 ${tone.item}`}>
                    <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-slate-300" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
              {section.insufficiency_reasons?.length ? (
                <div className="mt-3 rounded-2xl border border-rose-200/80 bg-white/84 p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-rose-700">
                    为什么还不够
                  </p>
                  <ul className="mt-2 space-y-1.5 text-xs leading-5 text-slate-600">
                    {section.insufficiency_reasons.slice(0, 3).map((reason) => (
                      <li key={`${section.title}-${reason}`} className="flex gap-2">
                        <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-rose-300" />
                        <span>{reason}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {section.confidence_reason ? (
                <p className="mt-3 text-xs leading-5 text-slate-600">{section.confidence_reason}</p>
              ) : null}
              {section.evidence_note ? (
                <p className="mt-3 text-xs leading-5 text-slate-500">{section.evidence_note}</p>
              ) : null}
              {section.quota_note ? (
                <p
                  className={`mt-2 text-xs leading-5 ${
                    section.meets_evidence_quota ? "text-emerald-700" : "text-amber-700"
                  }`}
                >
                  {section.quota_note}
                </p>
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
                <div className="mt-3 rounded-2xl border border-slate-200/80 bg-slate-50/85 p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">证据锚点</p>
                  <div className="mt-2 space-y-2">
                    {section.evidence_links.slice(0, 3).map((link) => (
                      <div
                        key={`${section.title}-${link.url}`}
                        className={`block rounded-xl border border-white/80 px-3 py-2 text-xs text-slate-600 transition hover:border-slate-200 hover:bg-white ${tone.excerpt}`}
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <a
                            href={normalizeExternalUrl(link.url)}
                            target="_blank"
                            rel="noreferrer"
                            className="font-medium text-slate-900 underline-offset-4 hover:text-sky-800 hover:underline"
                          >
                            {link.anchor_text || link.title}
                          </a>
                          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">
                            {sourceTierLabel(link.source_tier || "media")}
                          </span>
                          {link.source_label ? (
                            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">
                              {link.source_label}
                            </span>
                          ) : null}
                        </div>
                        {link.excerpt ? (
                          <p className="mt-2 rounded-lg bg-white/66 px-2 py-1.5 text-[11px] leading-5 text-slate-700">
                            {link.excerpt}
                          </p>
                        ) : (
                          <p className="mt-1 line-clamp-1 text-[11px] text-slate-500">{link.title}</p>
                        )}
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
        <article className="mt-5 rounded-2xl border border-rose-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(255,241,242,0.88))] p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{reportSurfaceCopy.reviewQueueTitle}</p>
              <p className="mt-2 text-sm text-slate-500">{reportSurfaceCopy.reviewQueueDesc}</p>
            </div>
            <span className="rounded-full bg-white/86 px-2.5 py-1 text-xs text-slate-600">{reviewQueue.length} 条</span>
          </div>
          <div className="mt-4 space-y-3">
            {reviewQueue.map((item) => (
              <div key={`review-${item.id}`} className="rounded-2xl border border-white/90 bg-white/88 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-slate-900">{item.section_title}</p>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] ${item.severity === "high" ? "bg-rose-100 text-rose-700" : item.severity === "medium" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-500"}`}>
                    {item.severity === "high" ? "高优先级" : item.severity === "medium" ? "中优先级" : "低优先级"}
                  </span>
                </div>
                <p className="mt-2 text-sm leading-6 text-slate-700">{item.summary}</p>
                {item.recommended_action ? (
                  <p className="mt-2 text-sm font-medium leading-6 text-rose-800">建议：{item.recommended_action}</p>
                ) : null}
                {item.evidence_links?.length ? (
                  <div className="mt-3 space-y-2">
                    {item.evidence_links.slice(0, 2).map((link) => (
                      <div key={`review-evidence-${item.id}-${link.url}`} className="rounded-xl border border-rose-100/90 bg-rose-50/72 px-3 py-2">
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
              </div>
            ))}
          </div>
        </article>
      ) : null}

      {technicalAppendix ? (
        <article className="mt-5 af-report-muted-surface rounded-2xl border border-white/80 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{reportSurfaceCopy.appendixTitle}</p>
          <div className="mt-4 grid gap-3">
            {technicalAppendix.key_assumptions?.length ? (
              <div className="rounded-2xl border border-slate-200/80 bg-white/86 p-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">关键假设</p>
                <ul className="mt-2 space-y-2 text-sm leading-6 text-slate-700">
                  {technicalAppendix.key_assumptions.map((value) => (
                    <li key={`appendix-assumption-${value}`} className="flex gap-2">
                      <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-slate-300" />
                      <span>{value}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {technicalAppendix.scenario_comparison?.length ? (
              <div className="rounded-2xl border border-slate-200/80 bg-white/86 p-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">情景对比</p>
                <div className="mt-3 grid gap-3">
                  {technicalAppendix.scenario_comparison.map((scenario) => (
                    <div key={`scenario-${scenario.name}`} className="rounded-2xl border border-slate-200/80 bg-slate-50/82 p-3">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-slate-900">{scenario.name}</p>
                      </div>
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
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-2xl border border-amber-100/90 bg-amber-50/80 p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-700">限制条件</p>
                  <ul className="mt-2 space-y-2 text-sm leading-6 text-amber-900">
                    {(technicalAppendix.limitations || []).map((value) => (
                      <li key={`appendix-limit-${value}`} className="flex gap-2">
                        <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-amber-300" />
                        <span>{value}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="rounded-2xl border border-slate-200/80 bg-white/86 p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">方法说明</p>
                  <ul className="mt-2 space-y-2 text-sm leading-6 text-slate-700">
                    {(technicalAppendix.technical_appendix || []).map((value) => (
                      <li key={`appendix-note-${value}`} className="flex gap-2">
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

      {!hideSources && report.sources.length > 0 ? (
        <div className="mt-6 rounded-2xl border border-white/80 bg-white/60 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{sourcesLabel}</p>
          <ol className="mt-3 space-y-3 text-sm leading-6 text-slate-600">
            {report.sources.map((source, index) => (
              <li key={`${source.url}-${index}`} className="rounded-2xl border border-slate-200/80 bg-slate-50/80 px-3 py-3">
                <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 font-semibold text-slate-600">
                    [{index + 1}]
                  </span>
                  <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5">
                    {sourceTierLabel(source.source_tier || classifySourceTier(source))}
                  </span>
                  {source.source_label ? (
                    <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5">
                      {source.source_label}
                    </span>
                  ) : null}
                  <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5">
                    {source.domain || "web"}
                  </span>
                  <span>{source.source_type}</span>
                </div>
                <a
                  href={normalizeExternalUrl(source.url)}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2 block text-sm font-semibold leading-6 text-slate-900 underline-offset-4 hover:underline"
                >
                  {source.title}
                </a>
                <p className="mt-1 text-sm leading-6 text-slate-600">{source.snippet}</p>
                <p className="mt-1 text-xs text-slate-500">{source.url}</p>
                <ExternalLinkActions
                  url={source.url}
                  className="mt-3"
                  openLabel="网页打开"
                />
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      <style jsx>{`
        .af-report-card {
          border-radius: 30px;
          border: 1px solid rgba(255, 255, 255, 0.82);
          background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(251, 253, 255, 0.92));
          box-shadow:
            0 28px 70px -44px rgba(15, 23, 42, 0.24),
            inset 0 1px 0 rgba(255, 255, 255, 0.72);
          padding: 1.25rem;
        }

        .af-report-surface {
          background:
            radial-gradient(circle at 16% 0%, rgba(233, 245, 255, 0.62), transparent 34%),
            linear-gradient(180deg, rgba(248, 251, 255, 0.94), rgba(240, 247, 255, 0.82));
          box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.78);
        }

        .af-report-muted-surface {
          background: linear-gradient(180deg, rgba(250, 252, 255, 0.94), rgba(244, 248, 252, 0.82));
          box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.75);
        }

        .af-report-stage-grid {
          display: grid;
          gap: 0.625rem;
          grid-template-columns: repeat(3, minmax(0, 1fr));
        }

        .af-report-stage-card {
          border-radius: 18px;
          border: 1px solid rgba(255, 255, 255, 0.82);
          background: linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(248, 250, 252, 0.76));
          padding: 0.7rem 0.75rem;
          box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
        }

        .af-report-stage-value {
          margin-top: 0.2rem;
          font-size: 1.15rem;
          font-weight: 600;
          letter-spacing: -0.04em;
          color: rgb(15 23 42);
        }

        .af-report-stage-summary {
          margin-top: 0.18rem;
          font-size: 0.7rem;
          line-height: 1.4;
          color: rgb(100 116 139);
        }

        @media (min-width: 768px) {
          .af-report-card {
            padding: 1.25rem 1.75rem;
          }
        }

        @media (max-width: 720px) {
          .af-report-stage-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </section>
  );
}
