"use client";

import type { ApiResearchReport } from "@/lib/api/types";

export function ResearchReportAppendixSection({
  technicalAppendix,
  appendixTitle,
}: {
  technicalAppendix: ApiResearchReport["technical_appendix"];
  appendixTitle: string;
}) {
  return (
    <>
      {technicalAppendix ? (
        <article className="mt-5 af-report-muted-surface rounded-2xl border border-[var(--af-border-subtle)] p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">{appendixTitle}</p>
          <div className="mt-4 grid gap-3">
            {technicalAppendix.key_assumptions?.length ? (
              <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">关键假设</p>
                <ul className="mt-2 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                  {technicalAppendix.key_assumptions.map((value) => (
                    <li key={`appendix-assumption-${value}`} className="flex gap-2">
                      <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[var(--af-border-strong)]" />
                      <span>{value}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {technicalAppendix.scenario_comparison?.length ? (
              <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">情景对比</p>
                <div className="mt-3 grid gap-3">
                  {technicalAppendix.scenario_comparison.map((scenario) => (
                    <div key={`scenario-${scenario.name}`} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-[var(--af-text-primary)]">{scenario.name}</p>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{scenario.summary}</p>
                      {scenario.implication ? (
                        <p className="mt-2 text-sm font-medium leading-6 text-[var(--af-info)]">影响：{scenario.implication}</p>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            {(technicalAppendix.limitations?.length || technicalAppendix.technical_appendix?.length) ? (
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-2xl border border-[color-mix(in_srgb,var(--af-warning)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-warning)_10%,var(--af-surface-muted))] p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-warning)]">限制条件</p>
                  <ul className="mt-2 space-y-2 text-sm leading-6 text-[var(--af-warning)]">
                    {(technicalAppendix.limitations || []).map((value) => (
                      <li key={`appendix-limit-${value}`} className="flex gap-2">
                        <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[var(--af-warning)]" />
                        <span>{value}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">方法说明</p>
                  <ul className="mt-2 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                    {(technicalAppendix.technical_appendix || []).map((value) => (
                      <li key={`appendix-note-${value}`} className="flex gap-2">
                        <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[var(--af-border-strong)]" />
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
    </>
  );
}
