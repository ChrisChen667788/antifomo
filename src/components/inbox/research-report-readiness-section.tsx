"use client";

import type { ApiResearchReport } from "@/lib/api/types";
import type { ReportToneMeta } from "@/components/inbox/research-report-section-types";

export function ResearchReportReadinessSection({
  readiness,
  commercialSummary,
  weakSections,
  readinessState,
  readinessTitle,
  playbookTitle,
  sectionStatusMeta,
}: {
  readiness: ApiResearchReport["report_readiness"];
  commercialSummary: ApiResearchReport["commercial_summary"];
  weakSections: ApiResearchReport["sections"];
  readinessState: ReportToneMeta;
  readinessTitle: string;
  playbookTitle: string;
  sectionStatusMeta: (value?: string) => ReportToneMeta;
}) {
  return (
    <>
      {(readiness || commercialSummary) ? (
        <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-[0.92fr_1.08fr]">
          {readiness ? (
            <article className="af-report-muted-surface rounded-2xl border border-[var(--af-border-subtle)] p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">{readinessTitle}</p>
                  <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">{readinessState.note}</p>
                </div>
                <div className="flex flex-wrap gap-2 text-xs">
                  <span className={`rounded-full border px-2.5 py-1 ${readinessState.className}`}>
                    {readinessState.label}
                  </span>
                  <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-secondary)]">
                    评分 {readiness.score}
                  </span>
                  <span className={`rounded-full px-2.5 py-1 ${readiness.evidence_gate_passed ? "af-chip af-chip-success" : "af-chip af-chip-warning"}`}>
                    {readiness.evidence_gate_passed ? "证据门槛已通过" : "证据门槛待补"}
                  </span>
                </div>
              </div>
              {readiness.reasons?.length ? (
                <div className="mt-4 space-y-2">
                  {readiness.reasons.map((reason) => (
                    <div key={`readiness-reason-${reason}`} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                      {reason}
                    </div>
                  ))}
                </div>
              ) : null}
              {(readiness.missing_axes?.length || readiness.next_verification_steps?.length) ? (
                <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
                  {readiness.missing_axes?.length ? (
                    <div className="rounded-2xl border border-[color-mix(in_srgb,var(--af-warning)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-warning)_10%,var(--af-surface-muted))] p-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-warning)]">仍缺关键维度</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {readiness.missing_axes.map((value) => (
                          <span key={`readiness-axis-${value}`} className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px] text-[var(--af-warning)]">
                            {value}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {readiness.next_verification_steps?.length ? (
                    <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">下一步核验</p>
                      <ul className="mt-2 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                        {readiness.next_verification_steps.slice(0, 3).map((value) => (
                          <li key={`readiness-step-${value}`} className="flex gap-2">
                            <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[var(--af-border-strong)]" />
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
            <article className="af-report-surface rounded-2xl border border-[color-mix(in_srgb,var(--af-info)_28%,var(--af-border-subtle))] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-info)]">{playbookTitle}</p>
              <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
                <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">重点账户</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {(commercialSummary.account_focus || []).length ? (
                      commercialSummary.account_focus.map((value) => (
                        <span key={`commercial-account-${value}`} className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-info)]">
                          {value}
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-[var(--af-text-tertiary)]">仍待收敛到账户对象</span>
                    )}
                  </div>
                </div>
                <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">预算与信号</p>
                  <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{commercialSummary.budget_signal || "当前仍缺直接预算或采购信号"}</p>
                </div>
                <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">推进窗口</p>
                  <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{commercialSummary.entry_window || "当前仍缺明确进入窗口"}</p>
                </div>
                <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">竞合与伙伴</p>
                  <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{commercialSummary.competition_or_partner || "当前仍需补竞品或伙伴格局"}</p>
                </div>
              </div>
              <div className="mt-3 rounded-2xl border border-[color-mix(in_srgb,var(--af-info)_28%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)] p-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">下一步推进</p>
                <p className="mt-2 text-sm leading-6 text-[var(--af-info)]">{commercialSummary.next_action || "继续补组织入口、预算和进入窗口后再生成行动卡。"}</p>
              </div>
            </article>
          ) : null}
        </div>
      ) : null}

      {weakSections.length ? (
        <div className="mt-5 rounded-2xl border border-[color-mix(in_srgb,var(--af-warning)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-warning)_10%,var(--af-surface-muted))] p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-warning)]">关键待核验章节</p>
              <p className="mt-1 text-sm text-[var(--af-warning)]">
                先处理最弱章节，再决定是否进入正式推进和导出。
              </p>
            </div>
            <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-xs text-[var(--af-warning)]">
              {weakSections.length} 个章节待收紧
            </span>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
            {weakSections.map((section) => {
              const statusMeta = sectionStatusMeta(section.status);
              return (
                <div key={`weak-section-${section.title}`} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-[var(--af-text-primary)]">{section.title}</p>
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${statusMeta.className}`}>
                      {statusMeta.label}
                    </span>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-[var(--af-text-secondary)]">
                    {section.insufficiency_summary || section.quota_note || section.confidence_reason || "当前章节仍需继续核验。"}
                  </p>
                  {section.next_verification_steps?.length ? (
                    <p className="mt-2 text-xs leading-5 text-[var(--af-warning)]">
                      下一步：{section.next_verification_steps[0]}
                    </p>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      ) : null}
    </>
  );
}
