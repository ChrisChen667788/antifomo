"use client";

import type { ApiResearchReport } from "@/lib/api/types";
import type { KnowledgeReportSurfaceCopy } from "@/components/knowledge/knowledge-detail-card-model";

interface KnowledgeResearchReportAppendixSectionProps {
  technicalAppendix?: ApiResearchReport["technical_appendix"];
  copy: KnowledgeReportSurfaceCopy;
}

export function KnowledgeResearchReportAppendixSection({
  technicalAppendix,
  copy,
}: KnowledgeResearchReportAppendixSectionProps) {
  if (!technicalAppendix) {
    return null;
  }

  return (
    <article className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">{copy.appendixTitle}</p>
      <div className="mt-4 grid grid-cols-1 gap-3">
        {technicalAppendix.key_assumptions?.length ? (
          <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">关键假设</p>
            <ul className="mt-2 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
              {technicalAppendix.key_assumptions.map((value) => (
                <li key={`knowledge-appendix-assumption-${value}`} className="flex gap-2">
                  <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[var(--af-surface-inset)]" />
                  <span>{value}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {technicalAppendix.scenario_comparison?.length ? (
          <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">情景对比</p>
            <div className="mt-3 grid grid-cols-1 gap-3">
              {technicalAppendix.scenario_comparison.map((scenario) => (
                <div key={`knowledge-scenario-${scenario.name}`} className="rounded-[16px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
                  <p className="text-sm font-semibold text-[var(--af-text-primary)]">{scenario.name}</p>
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
          <div className="grid grid-cols-1 gap-3">
            <div className="rounded-[18px] border border-[color-mix(in_srgb,var(--af-warning)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-warning)_14%,var(--af-surface-muted))] p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-warning)]">限制条件</p>
              <ul className="mt-2 space-y-2 text-sm leading-6 text-[var(--af-warning)]">
                {(technicalAppendix.limitations || []).map((value) => (
                  <li key={`knowledge-appendix-limit-${value}`} className="flex gap-2">
                    <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[color-mix(in_srgb,var(--af-warning)_14%,var(--af-surface-muted))]" />
                    <span>{value}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">方法说明</p>
              <ul className="mt-2 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                {(technicalAppendix.technical_appendix || []).map((value) => (
                  <li key={`knowledge-appendix-note-${value}`} className="flex gap-2">
                    <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[var(--af-surface-inset)]" />
                    <span>{value}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ) : null}
      </div>
    </article>
  );
}
