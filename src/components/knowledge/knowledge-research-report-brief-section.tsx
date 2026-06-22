"use client";

import type { ApiResearchReport } from "@/lib/api/types";
import { qualityLabel, qualityTone, type KnowledgeDiagnosticCard, type KnowledgeEvidenceModeMeta, type KnowledgeFollowupResolutionMeta, type KnowledgeReportSurfaceCopy, type KnowledgeTranslateFn } from "@/components/knowledge/knowledge-detail-card-model";

interface KnowledgeResearchReportBriefSectionProps {
  report: ApiResearchReport;
  diagnostics?: ApiResearchReport["source_diagnostics"];
  followupDiagnostics?: ApiResearchReport["followup_diagnostics"];
  evidenceMode: KnowledgeEvidenceModeMeta;
  diagnosticCards: KnowledgeDiagnosticCard[];
  pipelineStages: NonNullable<ApiResearchReport["source_diagnostics"]>["pipeline_stages"];
  guardedBacklog: boolean;
  guardedReasonLabels: string[];
  supportedTargetAccounts: string[];
  unsupportedTargetAccounts: string[];
  candidateProfileCompanies: string[];
  candidateProfileSourceLabels: string[];
  followupTitleResolution: KnowledgeFollowupResolutionMeta;
  followupSummaryResolution: KnowledgeFollowupResolutionMeta;
  followupImpactedSections: NonNullable<ApiResearchReport["followup_diagnostics"]>["impacted_sections"];
  copy: KnowledgeReportSurfaceCopy;
  t: KnowledgeTranslateFn;
}

export function KnowledgeResearchReportBriefSection({
  report,
  diagnostics,
  followupDiagnostics,
  evidenceMode,
  diagnosticCards,
  pipelineStages,
  guardedBacklog,
  guardedReasonLabels,
  supportedTargetAccounts,
  unsupportedTargetAccounts,
  candidateProfileCompanies,
  candidateProfileSourceLabels,
  followupTitleResolution,
  followupSummaryResolution,
  followupImpactedSections,
  copy,
  t,
}: KnowledgeResearchReportBriefSectionProps) {
  return (
    <div className="rounded-2xl border border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-info)]">
        {copy.briefKicker}
      </p>
      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        <span className={`rounded-full px-2.5 py-1 ${qualityTone(report.evidence_density)}`}>
          {t("research.centerEvidenceDensity", "证据密度")}·{qualityLabel(report.evidence_density)}
        </span>
        <span className={`rounded-full px-2.5 py-1 ${qualityTone(report.source_quality)}`}>
          {t("research.centerSourceQuality", "来源质量")}·{qualityLabel(report.source_quality)}
        </span>
        <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-tertiary)]">
          {t("research.centerCardSources", "来源数")} {report.source_count}
        </span>
      </div>
      {diagnostics ? (
        <div className={`mt-3 rounded-2xl border px-3.5 py-3 ${evidenceMode.className}`}>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px] font-semibold">
              {diagnostics.evidence_mode_label || evidenceMode.label}
            </span>
            {guardedBacklog ? (
              <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px] text-[var(--af-danger)]">
                待复核
              </span>
            ) : null}
            {diagnostics.corrective_triggered ? (
              <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px]">
                {t("research.correctiveTriggered", "已补充核验")}
              </span>
            ) : null}
            {diagnostics.expansion_triggered ? (
              <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px]">
                {t("research.expansionTriggered", "已扩展来源")}
              </span>
            ) : null}
            {candidateProfileCompanies.length ? (
              <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px]">
                {t("research.candidateProfiles", "建议核验公司")} {candidateProfileCompanies.length}
              </span>
            ) : null}
            {diagnostics.candidate_profile_hit_count > 0 ? (
              <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px]">
                {t("research.candidateProfileHits", "公开来源")} {diagnostics.candidate_profile_hit_count}
              </span>
            ) : null}
            {diagnostics.candidate_profile_official_hit_count > 0 ? (
              <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px]">
                {t("research.candidateProfileOfficialHits", "其中官方源")} {diagnostics.candidate_profile_official_hit_count}
              </span>
            ) : null}
          </div>
          <p className="mt-2 text-xs leading-5">{evidenceMode.note}</p>
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
            {diagnosticCards.map((card) => (
              <div key={card.title} className={`rounded-[18px] border px-3 py-3 ${card.tone}`}>
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] opacity-70">
                  {card.title}
                </p>
                <p className="mt-1 text-sm font-semibold leading-6">{card.value}</p>
                <p className="mt-1 text-xs leading-5 opacity-80">{card.detail}</p>
              </div>
            ))}
          </div>
          {pipelineStages.length ? (
            <div className="af-knowledge-stage-grid mt-3">
              {pipelineStages.map((stage) => (
                <div key={stage.key} className="af-knowledge-stage-card">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">
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
                <span key={`guarded-reason-${value}`} className="rounded-full bg-[color-mix(in_srgb,var(--af-danger)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-danger)]">
                  {value}
                </span>
              ))}
            </div>
          ) : null}
          {supportedTargetAccounts.length || unsupportedTargetAccounts.length ? (
            <div className="mt-2 flex flex-wrap gap-2">
              {supportedTargetAccounts.map((value) => (
                <span key={`supported-target-${value}`} className="rounded-full bg-[color-mix(in_srgb,var(--af-success)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-success)]">
                  已支撑 · {value}
                </span>
              ))}
              {unsupportedTargetAccounts.map((value) => (
                <span key={`unsupported-target-${value}`} className="rounded-full bg-[color-mix(in_srgb,var(--af-danger)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-danger)]">
                  未支撑 · {value}
                </span>
              ))}
            </div>
          ) : null}
          {candidateProfileCompanies.length ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {candidateProfileCompanies.map((value) => (
                <span key={`candidate-profile-${value}`} className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-info)]">
                  {value}
                </span>
              ))}
            </div>
          ) : null}
          {candidateProfileSourceLabels.length ? (
            <div className="mt-2 flex flex-wrap gap-2">
              {candidateProfileSourceLabels.map((value) => (
                <span key={`candidate-profile-source-${value}`} className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-info)]">
                  {value}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
      <p className="mt-3 text-sm leading-7 text-[var(--af-text-secondary)]">{report.executive_summary}</p>
      <p className="mt-3 rounded-2xl border border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)] px-4 py-3 text-sm leading-6 text-[var(--af-info)]">
        {report.consulting_angle}
      </p>
      {followupDiagnostics?.enabled ? (
        <div className="mt-4 rounded-[24px] border border-[color-mix(in_srgb,var(--af-warning)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)] p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-warning)]">补充信息影响</p>
              <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                {followupDiagnostics.summary || "补充信息已用于更新相关章节。"}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className={`rounded-full border px-2.5 py-1 font-semibold ${followupTitleResolution.className}`}>
                标题 · {followupTitleResolution.label}
              </span>
              <span className={`rounded-full border px-2.5 py-1 font-semibold ${followupSummaryResolution.className}`}>
                摘要 · {followupSummaryResolution.label}
              </span>
            </div>
          </div>
          {followupImpactedSections.length ? (
            <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
              {followupImpactedSections.map((section) => (
                <div key={`knowledge-followup-impact-${section.section_title}`} className="rounded-[20px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold text-[var(--af-text-primary)]">{section.section_title}</span>
                    <span
                      className={`rounded-full px-2.5 py-1 text-[11px] ${
                        section.impact_label === "high"
                          ? "af-chip af-chip-success"
                          : section.impact_label === "medium"
                            ? "af-chip af-chip-warning"
                            : "af-chip"
                      }`}
                    >
                      影响度 {section.impact_score}
                    </span>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-[var(--af-text-secondary)]">{section.reason}</p>
                  {section.matched_inputs?.length ? (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {section.matched_inputs.slice(0, 3).map((value) => (
                        <span key={`${section.section_title}-${value}`} className="rounded-full border border-[color-mix(in_srgb,var(--af-warning)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-warning)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-warning)]">
                          {value}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  <p className="mt-2 text-[11px] text-[var(--af-text-tertiary)]">{section.next_action}</p>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
