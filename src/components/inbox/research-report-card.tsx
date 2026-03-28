"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { ApiResearchReport } from "@/lib/api";

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
    return sourceMap[role];
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
  const evidenceMode = evidenceModeMeta(diagnostics?.evidence_mode || "fallback");
  const rankedPanels = [
    {
      title: (report.top_target_accounts && report.top_target_accounts.length) ? "高价值甲方 Top 3" : "待补证甲方候选",
      items: (report.top_target_accounts && report.top_target_accounts.length)
        ? report.top_target_accounts
        : pendingRankedEntities("target"),
      tone: "sky",
    },
    {
      title: (report.top_competitors && report.top_competitors.length) ? "高威胁竞品 Top 3" : "待补证竞品候选",
      items: (report.top_competitors && report.top_competitors.length)
        ? report.top_competitors
        : pendingRankedEntities("competitor"),
      tone: "amber",
    },
    {
      title: (report.top_ecosystem_partners && report.top_ecosystem_partners.length) ? "高影响力生态伙伴 Top 3" : "待补证伙伴候选",
      items: (report.top_ecosystem_partners && report.top_ecosystem_partners.length)
        ? report.top_ecosystem_partners
        : pendingRankedEntities("partner"),
      tone: "emerald",
    },
  ].filter((panel) => panel.items.length);

  return (
    <section className="af-glass rounded-[30px] p-5 md:p-7">
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
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
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
          {report.query_plan.slice(0, 4).map((query) => (
            <span
              key={query}
              className="rounded-full border border-slate-200 bg-white/75 px-3 py-1 text-xs font-medium text-slate-600"
            >
              {query}
            </span>
          ))}
        </div>
        {actionMessage ? <p className="w-full text-sm text-slate-500">{actionMessage}</p> : null}
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
        <div className="rounded-2xl border border-sky-100/80 bg-[linear-gradient(180deg,rgba(248,251,255,0.92),rgba(238,246,255,0.8))] p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{summaryLabel}</p>
          <p className="mt-3 text-[15px] leading-7 text-slate-700">{report.executive_summary}</p>
        </div>
        <div className="rounded-2xl border border-cyan-100/90 bg-[linear-gradient(180deg,rgba(240,249,255,0.95),rgba(230,247,255,0.82))] p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-500">{angleLabel}</p>
          <p className="mt-3 text-sm leading-6 text-sky-900">{report.consulting_angle}</p>
        </div>
      </div>

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
                          <a
                            key={`${entity.name}-${link.url}`}
                            href={link.url}
                            target="_blank"
                            rel="noreferrer"
                            className="block rounded-2xl border border-slate-200/80 bg-slate-50/76 px-3 py-2 transition hover:border-slate-300 hover:bg-white/82"
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
        <div className="rounded-2xl border border-white/80 bg-[linear-gradient(180deg,rgba(248,251,255,0.9),rgba(242,246,250,0.72))] p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">检索与研究路径</p>
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
        <div className="rounded-2xl border border-white/80 bg-[linear-gradient(180deg,rgba(248,251,255,0.9),rgba(242,246,250,0.72))] p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{sourcesLabel}</p>
          {diagnostics ? (
            <div className="mt-3 rounded-2xl border border-slate-200/80 bg-slate-50/80 p-3">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">采集诊断</p>
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
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                <span className="rounded-full bg-white px-2.5 py-1 text-slate-600">
                  启用源 {diagnostics.enabled_source_labels.length}
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
                {diagnostics.candidate_profile_companies?.length ? (
                  <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
                    候选补证公司 {diagnostics.candidate_profile_companies.length}
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
              </div>
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
                    {report.entity_graph.entities.slice(0, 6).map((entity) => (
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
              {diagnostics.enabled_source_labels.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">当前启用</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {diagnostics.enabled_source_labels.map((label) => (
                      <span key={label} className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600">
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {diagnostics.scope_regions.length || diagnostics.scope_industries.length || diagnostics.scope_clients.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">范围锁定</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {diagnostics.scope_regions.map((label) => (
                      <span key={`scope-region-${label}`} className="rounded-full border border-cyan-200 bg-cyan-50 px-2.5 py-1 text-xs text-cyan-700">
                        区域 · {label}
                      </span>
                    ))}
                    {diagnostics.scope_industries.map((label) => (
                      <span key={`scope-industry-${label}`} className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs text-blue-700">
                        领域 · {label}
                      </span>
                    ))}
                    {diagnostics.scope_clients.map((label) => (
                      <span key={`scope-client-${label}`} className="rounded-full border border-fuchsia-200 bg-fuchsia-50 px-2.5 py-1 text-xs text-fuchsia-700">
                        公司 · {label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {diagnostics.matched_source_labels.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">本次命中</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {diagnostics.matched_source_labels.map((label) => (
                      <span key={label} className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs text-sky-700">
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {diagnostics.topic_anchor_terms.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">主题锚点</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {diagnostics.topic_anchor_terms.map((label) => (
                      <span key={label} className="rounded-full border border-violet-200 bg-violet-50 px-2.5 py-1 text-xs text-violet-700">
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {diagnostics.matched_theme_labels.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">命中主题</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {diagnostics.matched_theme_labels.map((label) => (
                      <span key={label} className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs text-emerald-700">
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {diagnostics.candidate_profile_companies?.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">候选补证公司</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {diagnostics.candidate_profile_companies.map((label) => (
                      <span key={label} className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs text-sky-700">
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {diagnostics.candidate_profile_source_labels?.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">补证命中源</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {diagnostics.candidate_profile_source_labels.map((label) => (
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
                      <a
                        key={`${group.key}-${source.url}-${source.search_query}`}
                        href={source.url}
                        target="_blank"
                        rel="noreferrer"
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
                        <p className="mt-2 text-sm font-semibold leading-6 text-slate-900">{source.title}</p>
                        <p className="mt-1 text-sm leading-6 text-slate-600">{source.snippet}</p>
                      </a>
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
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">扩展分析模块</p>
            <p className="mt-1 text-sm text-slate-500">按主题继续展开证据、判断和补充建议。</p>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
          {report.sections.map((section) => (
            <article
              key={section.title}
              className="rounded-2xl border border-white/80 bg-white/60 p-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h4 className="text-sm font-semibold text-slate-900">{section.title}</h4>
                <div className="flex flex-wrap gap-2 text-[11px]">
                  <span className={`rounded-full px-2 py-0.5 ${qualityTone(section.evidence_density || "low")}`}>
                    证据密度·{qualityLabel(section.evidence_density || "low")}
                  </span>
                  <span className={`rounded-full px-2 py-0.5 ${qualityTone(section.source_quality || "low")}`}>
                    来源质量·{qualityLabel(section.source_quality || "low")}
                  </span>
                </div>
              </div>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
                {section.items.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-slate-300" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
              {section.evidence_note ? (
                <p className="mt-3 text-xs leading-5 text-slate-500">{section.evidence_note}</p>
              ) : null}
            </article>
          ))}
          </div>
        </div>
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
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2 block text-sm font-semibold leading-6 text-slate-900 underline-offset-4 hover:underline"
                >
                  {source.title}
                </a>
                <p className="mt-1 text-sm leading-6 text-slate-600">{source.snippet}</p>
                <p className="mt-1 text-xs text-slate-500">{source.url}</p>
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </section>
  );
}
