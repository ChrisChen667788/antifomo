"use client";

import type { ApiResearchReport } from "@/lib/api/types";
import type { KnowledgeReportSurfaceCopy } from "@/components/knowledge/knowledge-detail-card-model";

interface KnowledgeResearchReportReadinessSectionProps {
  reportReadiness?: ApiResearchReport["report_readiness"];
  commercialSummary?: ApiResearchReport["commercial_summary"];
  copy: KnowledgeReportSurfaceCopy;
}

export function KnowledgeResearchReportReadinessSection({
  reportReadiness,
  commercialSummary,
  copy,
}: KnowledgeResearchReportReadinessSectionProps) {
  if (!reportReadiness && !commercialSummary) {
    return null;
  }

  return (
    <div className="grid gap-4">
      {reportReadiness ? (
        <article className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">{copy.readinessTitle}</p>
              <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">
                {reportReadiness.status === "ready"
                  ? "当前结果已经满足较完整的销售/咨询推进条件。"
                  : reportReadiness.status === "degraded"
                    ? "当前可以先做候选推进，但仍建议继续核验。"
                    : "当前更适合作为候选名单和待核验清单。"}
              </p>
            </div>
            <div className="flex flex-wrap gap-2 text-xs">
              <span className={`rounded-full px-2.5 py-1 ${reportReadiness.status === "ready" ? "af-chip af-chip-success" : reportReadiness.status === "degraded" ? "af-chip af-chip-warning" : "af-chip"}`}>
                {reportReadiness.status === "ready" ? "可直接推进" : reportReadiness.status === "degraded" ? "候选推进" : "待核验"}
              </span>
              <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-secondary)]">评分 {reportReadiness.score}</span>
              <span className={`rounded-full px-2.5 py-1 ${reportReadiness.evidence_gate_passed ? "af-chip af-chip-success" : "af-chip af-chip-warning"}`}>
                {reportReadiness.evidence_gate_passed ? "证据门槛已通过" : "证据门槛待补"}
              </span>
            </div>
          </div>
          {reportReadiness.reasons?.length ? (
            <div className="mt-4 space-y-2">
              {reportReadiness.reasons.map((value) => (
                <div key={`report-readiness-reason-${value}`} className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                  {value}
                </div>
              ))}
            </div>
          ) : null}
          {(reportReadiness.missing_axes?.length || reportReadiness.next_verification_steps?.length) ? (
            <div className="mt-4 grid gap-3">
              {reportReadiness.missing_axes?.length ? (
                <div className="rounded-[18px] border border-[color-mix(in_srgb,var(--af-warning)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-warning)_14%,var(--af-surface-muted))] p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-warning)]">仍缺关键维度</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {reportReadiness.missing_axes.map((value) => (
                      <span key={`report-readiness-axis-${value}`} className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px] text-[var(--af-warning)]">
                        {value}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {reportReadiness.next_verification_steps?.length ? (
                <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">下一步补证</p>
                  <ul className="mt-2 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                    {reportReadiness.next_verification_steps.slice(0, 3).map((value) => (
                      <li key={`report-readiness-step-${value}`} className="flex gap-2">
                        <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[var(--af-surface-inset)]" />
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
        <article className="rounded-[24px] border border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)] p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">{copy.playbookTitle}</p>
          <div className="mt-4 grid gap-3">
            <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">重点账户</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {commercialSummary.account_focus?.length ? commercialSummary.account_focus.map((value) => (
                  <span key={`commercial-summary-account-${value}`} className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-info)]">
                    {value}
                  </span>
                )) : <span className="text-sm text-[var(--af-text-tertiary)]">仍待收敛到账户对象</span>}
              </div>
            </div>
            <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">预算与信号</p>
              <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{commercialSummary.budget_signal || "当前仍缺直接预算或采购信号"}</p>
            </div>
            <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">推进窗口</p>
              <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{commercialSummary.entry_window || "当前仍缺明确进入窗口"}</p>
            </div>
            <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">竞合与伙伴</p>
              <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{commercialSummary.competition_or_partner || "当前仍需补竞品或伙伴格局"}</p>
            </div>
          </div>
          <div className="mt-3 rounded-[18px] border border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)] p-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">下一步推进</p>
            <p className="mt-2 text-sm leading-6 text-[var(--af-info)]">{commercialSummary.next_action || "继续补组织入口、预算和进入窗口后再生成行动卡。"}</p>
          </div>
        </article>
      ) : null}
    </div>
  );
}
