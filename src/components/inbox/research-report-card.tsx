"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import type { ApiResearchReport, ApiResearchRunMetrics } from "@/lib/api/types";
import { ResearchReportAppendixSection } from "@/components/inbox/research-report-appendix-section";
import { ResearchReportDeliverySection } from "@/components/inbox/research-report-delivery-section";
import { ResearchReportDeliveryTruthSection } from "@/components/inbox/research-report-delivery-truth-section";
import { ResearchReportInsightsSection } from "@/components/inbox/research-report-insights-section";
import { ResearchReportReadinessSection } from "@/components/inbox/research-report-readiness-section";
import { ResearchReportReviewQueueSection } from "@/components/inbox/research-report-review-queue-section";
import { ResearchReportSourceListSection } from "@/components/inbox/research-report-source-list-section";
import { ResearchReportStrategicSection } from "@/components/inbox/research-report-strategic-section";
import { ResearchReportSourcesDiagnosticsSection } from "@/components/inbox/research-report-sources-diagnostics-section";
import {
  buildResearchReportCardViewModel,
  classifySourceTier,
  confidenceToneMeta,
  qualityLabel,
  qualityTone,
  sectionStatusMeta,
  sourceTierLabel,
  valueBucket,
} from "@/components/inbox/research-report-card-view-model";

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
  formalDeliveryAllowed?: boolean;
  actionCardSlot?: ReactNode;
  runMetrics?: ApiResearchRunMetrics | null;
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
  formalDeliveryAllowed = true,
  actionCardSlot,
  runMetrics,
}: ResearchReportCardProps) {
  const {
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
  } = buildResearchReportCardViewModel(report);
  const measuredCostCny = runMetrics?.billing?.estimated_cost_cny;
  const totalTokens = runMetrics?.cost_ledger?.total_tokens;
  return (
    <section data-testid="research-report-card" className="af-report-card">
      {!formalDeliveryAllowed ? (
        <div className="mb-4 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          受限草稿：当前结果未通过正式交付门禁，保存、Word/PDF 和行动计划均已禁用。请补齐证据或恢复正式模型后重跑。
        </div>
      ) : null}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="af-kicker">{titleLabel}</p>
          <h3 className="mt-2 text-2xl font-semibold text-[var(--af-text-primary)]">
            {report.report_title}
          </h3>
          <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">
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
            {typeof totalTokens === "number" && totalTokens > 0 ? (
              <span className="af-chip rounded-full px-2.5 py-1">
                模型用量 · {totalTokens.toLocaleString()} tokens
              </span>
            ) : null}
            {typeof measuredCostCny === "number" ? (
              <span
                className="af-chip rounded-full px-2.5 py-1"
                title="按网关账户额度前后差量估算；并发请求会共同计入。"
              >
                估算成本 · ¥{measuredCostCny.toFixed(4)}
              </span>
            ) : null}
            {guardedBacklog ? (
              <span className="af-chip af-chip-warning rounded-full px-2.5 py-1">
                待复核
              </span>
            ) : null}
          </div>
        </div>

        <div className="flex w-full flex-wrap gap-2 xl:pt-1">
          {onSave ? (
            <button
              type="button"
              onClick={onSave}
              disabled={saving || !formalDeliveryAllowed}
              className="af-btn af-btn-secondary border px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? `${saveLabel}...` : saveLabel}
            </button>
          ) : null}
          {onSaveAsFocus ? (
            <button
              type="button"
              onClick={onSaveAsFocus}
              disabled={savingAsFocus || !formalDeliveryAllowed}
              className="af-btn af-btn-secondary border px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {savingAsFocus ? `${focusSaveLabel}...` : focusSaveLabel}
            </button>
          ) : null}
          {onExport ? (
            <button
              type="button"
              onClick={onExport}
              disabled={exporting || !formalDeliveryAllowed}
              className="af-btn af-btn-primary px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {exporting ? `${exportLabel}...` : exportLabel}
            </button>
          ) : null}
          {onExportWord ? (
            <button
              type="button"
              onClick={onExportWord}
              disabled={exportingWord || !formalDeliveryAllowed}
              className="af-btn af-btn-secondary border px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {exportingWord ? `${exportWordLabel}...` : exportWordLabel}
            </button>
          ) : null}
          {onExportPdf ? (
            <button
              type="button"
              onClick={onExportPdf}
              disabled={exportingPdf || !formalDeliveryAllowed}
              className="af-btn af-btn-secondary border px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {exportingPdf ? `${exportPdfLabel}...` : exportPdfLabel}
            </button>
          ) : null}
          {knowledgeHref && formalDeliveryAllowed ? (
            <Link href={knowledgeHref} className="af-btn af-btn-secondary border px-4 py-2">
              {savedLabel}
            </Link>
          ) : null}
        </div>
      </div>

      {!formalDeliveryAllowed ? (
        <p className="mt-3 rounded-md border border-[color-mix(in_srgb,var(--af-warning)_35%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-warning)_8%,var(--af-surface-muted))] px-3 py-2 text-sm text-[var(--af-text-secondary)]">
          当前是受限草稿。补齐证据并通过交付检查后，才能保存、生成行动卡或正式导出。
        </p>
      ) : null}

      {actionMessage ? <p className="mt-3 text-sm text-[var(--af-accent)]">{actionMessage}</p> : null}

      <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <article className="af-report-muted-surface rounded-2xl border border-[var(--af-border-subtle)] p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">证据档位</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${evidenceMode.className}`}>
              {diagnostics?.evidence_mode_label || evidenceMode.label}
            </span>
            <span className={`rounded-full px-2.5 py-1 text-xs ${qualityTone(report.evidence_density)}`}>
              证据密度 · {qualityLabel(report.evidence_density)}
            </span>
          </div>
          <p className="mt-3 text-sm leading-6 text-[var(--af-text-secondary)]">{evidenceMode.note}</p>
        </article>
        <article className="af-report-muted-surface rounded-2xl border border-[var(--af-border-subtle)] p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">目标账户支撑</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${targetSupportTone}`}>
              {targetSupportValue}
            </span>
          </div>
          <p className="mt-3 text-sm leading-6 text-[var(--af-text-secondary)]">{targetSupportDetail}</p>
        </article>
        <article className="af-report-muted-surface rounded-2xl border border-[var(--af-border-subtle)] p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">交叉验证</p>
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-secondary)]">
              官方来源 {Math.round((diagnostics?.official_source_ratio || 0) * 100)}%
            </span>
            <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-secondary)]">
              主题匹配 {Math.round((diagnostics?.strict_match_ratio || 0) * 100)}%
            </span>
            {diagnostics?.unique_domain_count ? (
              <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-secondary)]">
                来源 {diagnostics.unique_domain_count}
              </span>
            ) : null}
          </div>
          <p className="mt-3 text-sm leading-6 text-[var(--af-text-secondary)]">
            {diagnostics?.candidate_profile_official_hit_count
              ? `建议核验对象命中 ${diagnostics.candidate_profile_official_hit_count} 条官方资料。`
              : "当前以公开网页和主题交叉命中为主，仍可继续补官方资料。"}
          </p>
        </article>
        <article className="af-report-muted-surface rounded-2xl border border-[var(--af-border-subtle)] p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">待核验 / 门槛</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${verificationTone}`}>
              {verificationValue}
            </span>
            {readiness ? (
              <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-xs text-[var(--af-text-secondary)]">
                就绪度 {readiness.score}
              </span>
            ) : null}
          </div>
          <p className="mt-3 text-sm leading-6 text-[var(--af-text-secondary)]">{verificationDetail}</p>
        </article>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-[1.15fr_0.85fr]">
        <div className="af-report-surface rounded-2xl border border-[var(--af-border-subtle)] p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">{summaryLabel}</p>
          <p className="mt-3 text-[15px] leading-7 text-[var(--af-text-secondary)]">{report.executive_summary}</p>
        </div>
        <div className="af-report-surface rounded-2xl border border-[var(--af-border-subtle)] p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-info)]">{angleLabel}</p>
          <p className="mt-3 text-sm leading-6 text-[var(--af-text-secondary)]">{report.consulting_angle}</p>
        </div>
      </div>

      {followupDiagnostics?.enabled ? (
        <article className="mt-5 af-report-surface rounded-2xl border border-[var(--af-border-subtle)] p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-warning)]">补充信息影响</p>
              <h4 className="mt-2 text-lg font-semibold text-[var(--af-text-primary)]">已纳入补充信息</h4>
              <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                {followupDiagnostics.summary || "补充信息已用于更新相关章节。"}
              </p>
            </div>
          </div>
          {followupImpactedSections.length ? (
            <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
              {followupImpactedSections.map((section) => (
                <div key={`followup-impact-${section.section_title}`} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-[var(--af-text-primary)]">{section.section_title}</p>
                    <span
                      className={`rounded-full border px-2.5 py-1 text-[11px] ${
                        section.impact_label === "high"
                          ? "af-chip-success"
                          : section.impact_label === "medium"
                            ? "af-chip-warning"
                            : "bg-[var(--af-surface-muted)] text-[var(--af-text-secondary)]"
                      }`}
                    >
                      {section.impact_label === "high" ? "重点" : section.impact_label === "medium" ? "更新" : "参考"}
                    </span>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-[var(--af-text-secondary)]">{section.reason}</p>
                  <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-[var(--af-text-tertiary)]">
                    <span className="rounded-full bg-[var(--af-surface-muted)] px-2.5 py-1">{sectionStatusMeta(section.status).label}</span>
                    <span className="rounded-full bg-[var(--af-surface-muted)] px-2.5 py-1">来源 {section.retrieval_hit_count}</span>
                    <span className="rounded-full bg-[var(--af-surface-muted)] px-2.5 py-1">官方 {section.official_hit_count}</span>
                  </div>
                  {section.matched_inputs?.length ? (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {section.matched_inputs.slice(0, 3).map((value) => (
                        <span key={`${section.section_title}-${value}`} className="af-chip af-chip-warning rounded-full px-2.5 py-1 text-[11px]">
                          {value}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  <p className="mt-2 text-xs leading-5 text-[var(--af-text-tertiary)]">{section.next_action}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-4 text-sm leading-6 text-[var(--af-text-tertiary)]">当前补充信息还不够明确，可以继续补客户、预算或场景约束。</p>
          )}
        </article>
      ) : null}

      {qualityProfile ? (
        <article className="mt-5 af-report-surface rounded-2xl border border-[var(--af-border-subtle)] p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-success)]">研报质量画像</p>
              <h4 className="mt-2 text-lg font-semibold text-[var(--af-text-primary)]">
                {qualityProfile.methodology?.industry_label || "通用 B2B 解决方案研究"} · {qualityProfile.methodology?.framework_name || "方法论校验"}
              </h4>
              <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                {qualityProfile.headline || qualityProfile.methodology?.summary || "当前报告已生成基础质量画像。"}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className={`rounded-full border px-2.5 py-1 font-semibold ${qualityProfileState.className}`}>
                {qualityProfileState.label}
              </span>
              <span className="rounded-full bg-[var(--af-text-primary)] px-2.5 py-1 font-semibold text-[var(--af-text-inverse)]">
                总分 {qualityProfile.overall_score}
              </span>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-4">
            {[
              { label: "专业度", value: qualityProfile.professional_score },
              { label: "情报价值", value: qualityProfile.intelligence_value_score },
              { label: "行动价值", value: qualityProfile.actionability_score },
              { label: "证据强度", value: qualityProfile.evidence_score },
            ].map((item) => {
              const bucket = valueBucket(item.value);
              return (
                <div key={`quality-score-${item.label}`} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">{item.label}</p>
                  <div className="mt-2 flex items-center justify-between gap-2">
                    <span className="text-2xl font-semibold text-[var(--af-text-primary)]">{item.value}</span>
                    <span className={`rounded-full px-2.5 py-1 text-[11px] ${bucket.className}`}>{bucket.label}</span>
                  </div>
                </div>
              );
            })}
          </div>
          {(qualityProfile.gaps?.length || qualityProfile.next_actions?.length) ? (
            <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
              {qualityProfile.gaps?.length ? (
                <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-warning)]">质量缺口</p>
                  <ul className="mt-2 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                    {qualityProfile.gaps.slice(0, 4).map((value) => (
                      <li key={`quality-gap-${value}`} className="grid grid-cols-[8px_1fr] items-start gap-2">
                        <span className="mt-[9px] h-1.5 w-1.5 rounded-full bg-[var(--af-warning)]" />
                        <span className="min-w-0 break-words">{value}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {qualityProfile.next_actions?.length ? (
                <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-success)]">下一轮提质动作</p>
                  <ul className="mt-2 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                    {qualityProfile.next_actions.slice(0, 4).map((value) => (
                      <li key={`quality-action-${value}`} className="grid grid-cols-[8px_1fr] items-start gap-2">
                        <span className="mt-[9px] h-1.5 w-1.5 rounded-full bg-[var(--af-success)]" />
                        <span className="min-w-0 break-words">{value}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : null}
          {qualityProfile.section_evidence_packs?.length ? (
            <div className="mt-4 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">章节证据包</p>
              <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
                {qualityProfile.section_evidence_packs.slice(0, 4).map((pack) => (
                  <div key={`section-pack-${pack.section_title}`} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-[var(--af-text-primary)]">{pack.section_title}</p>
                      <span className={`rounded-full px-2.5 py-1 text-[11px] ${qualityTone(pack.status === "ready" ? "high" : pack.status === "degraded" ? "medium" : "low")}`}>
                        {pack.support_score}
                      </span>
                    </div>
                    <p className="mt-2 text-xs leading-5 text-[var(--af-text-tertiary)]">
                      证据 {pack.evidence_count} 条，官方 {pack.official_evidence_count} 条{pack.quota_gap ? `，缺口 ${pack.quota_gap}` : ""}
                    </p>
                    {pack.risks?.length ? (
                      <p className="mt-2 break-words text-xs leading-5 text-[var(--af-warning)]">{pack.risks.slice(0, 2).join(" / ")}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </article>
      ) : null}

      <ResearchReportDeliverySection
        report={report}
        marketIntelligence={marketIntelligence}
        solutionDeliveryPack={solutionDeliveryPack}
        solutionDeliveryQuality={solutionDeliveryQuality}
        projectProposalQuality={projectProposalQuality}
        architectureReadiness={architectureReadiness}
        architectWorkbench={architectWorkbench}
        primaryCustomerScenario={primaryCustomerScenario}
        solutionDeliveryQualityMeta={solutionDeliveryQualityMeta}
        projectProposalQualityMeta={projectProposalQualityMeta}
        architectureReadinessState={architectureReadinessState}
        valueBucket={valueBucket}
      />

      <ResearchReportDeliveryTruthSection report={report} />

      <ResearchReportReadinessSection
        readiness={readiness}
        commercialSummary={commercialSummary}
        weakSections={weakSections}
        readinessState={readinessState}
        readinessTitle={reportSurfaceCopy.readinessTitle}
        playbookTitle={reportSurfaceCopy.playbookTitle}
        sectionStatusMeta={sectionStatusMeta}
      />

      {actionCardSlot && formalDeliveryAllowed ? <div className="mt-5">{actionCardSlot}</div> : null}

      <ResearchReportStrategicSection
        report={report}
        valueBucket={valueBucket}
        sourceTierLabel={sourceTierLabel}
      />

      <ResearchReportSourcesDiagnosticsSection
        report={report}
        queryPlanLabel={queryPlanLabel}
        sourcesLabel={sourcesLabel}
        hideSources={hideSources}
        diagnostics={diagnostics}
        evidenceMode={evidenceMode}
        retrievalRoutingCards={retrievalRoutingCards}
        pipelineStages={pipelineStages}
        enabledSourceLabels={enabledSourceLabels}
        candidateProfileCompanies={candidateProfileCompanies}
        guardedBacklog={guardedBacklog}
        guardedReasonLabels={guardedReasonLabels}
        supportedTargetAccounts={supportedTargetAccounts}
        unsupportedTargetAccounts={unsupportedTargetAccounts}
        qualityExpansionQueries={qualityExpansionQueries}
        coreEntities={coreEntities}
        scopeRegions={scopeRegions}
        scopeIndustries={scopeIndustries}
        scopeClients={scopeClients}
        matchedSourceLabels={matchedSourceLabels}
        topicAnchorTerms={topicAnchorTerms}
        matchedThemeLabels={matchedThemeLabels}
        candidateProfileSourceLabels={candidateProfileSourceLabels}
        groupedSources={groupedSources}
        sourcePathTitle={reportSurfaceCopy.sourcePathTitle}
        sourceDiagTitle={reportSurfaceCopy.sourceDiagTitle}
        qualityLabel={qualityLabel}
        sourceTierLabel={sourceTierLabel}
        classifySourceTier={classifySourceTier}
      />

      <ResearchReportInsightsSection
        sections={report.sections}
        insightsTitle={reportSurfaceCopy.insightsTitle}
        insightsDesc={reportSurfaceCopy.insightsDesc}
        confidenceToneMeta={confidenceToneMeta}
        sectionStatusMeta={sectionStatusMeta}
        qualityTone={qualityTone}
        qualityLabel={qualityLabel}
        sourceTierLabel={sourceTierLabel}
      />

      <ResearchReportReviewQueueSection
        reviewQueue={reviewQueue}
        reviewQueueTitle={reportSurfaceCopy.reviewQueueTitle}
        reviewQueueDesc={reportSurfaceCopy.reviewQueueDesc}
      />

      <ResearchReportAppendixSection
        technicalAppendix={technicalAppendix}
        appendixTitle={reportSurfaceCopy.appendixTitle}
      />

      <ResearchReportSourceListSection
        sources={report.sources}
        hideSources={hideSources}
        sourcesLabel={sourcesLabel}
        sourceTierLabel={sourceTierLabel}
        classifySourceTier={classifySourceTier}
      />

      <style jsx global>{`
        .af-report-card {
          border-radius: 8px;
          border: 1px solid var(--af-border-subtle);
          background: var(--af-surface);
          box-shadow: var(--af-shadow-card);
          padding: 1.25rem;
        }

        .af-report-surface {
          background: var(--af-surface-elevated);
          border-color: var(--af-border-subtle);
          box-shadow: var(--af-shadow-soft);
        }

        .af-report-muted-surface {
          background: var(--af-surface-muted);
          border-color: var(--af-border-subtle);
          box-shadow: none;
        }

        .af-report-stage-grid {
          display: grid;
          gap: 0.625rem;
          grid-template-columns: repeat(3, minmax(0, 1fr));
        }

        .af-report-stage-card {
          border-radius: 8px;
          border: 1px solid var(--af-border-subtle);
          background: var(--af-surface-elevated);
          padding: 0.7rem 0.75rem;
          box-shadow: none;
        }

        .af-report-stage-value {
          margin-top: 0.2rem;
          font-size: 1.15rem;
          font-weight: 600;
          letter-spacing: 0;
          color: var(--af-text-primary);
        }

        .af-report-stage-summary {
          margin-top: 0.18rem;
          font-size: 0.7rem;
          line-height: 1.4;
          color: var(--af-text-tertiary);
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
