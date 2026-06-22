"use client";

import type { ApiKnowledgeEntry } from "@/lib/api/types";
import { qualityTone } from "@/components/knowledge/knowledge-detail-card-model";

interface KnowledgeResearchReportMethodologySectionProps {
  commercialIntelligence: ApiKnowledgeEntry["commercial_intelligence"] | null | undefined;
}

export function KnowledgeResearchReportMethodologySection({
  commercialIntelligence,
}: KnowledgeResearchReportMethodologySectionProps) {
  const methodologyCard = commercialIntelligence?.methodology;
  const confidenceCard = commercialIntelligence?.confidence;
  const coverageGaps = commercialIntelligence?.coverage_gaps || [];

  return (
    <>
      {(methodologyCard || confidenceCard || coverageGaps.length) ? (
        <div className="grid grid-cols-1 gap-4">
          {confidenceCard ? (
            <article className="rounded-[24px] border border-[color-mix(in_srgb,var(--af-success)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">可信度卡</p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span className={`rounded-full px-2.5 py-1 text-xs ${qualityTone(confidenceCard.level || "low")}`}>
                  {confidenceCard.level === "high" ? "高可信" : confidenceCard.level === "medium" ? "中可信" : "待核验"}
                </span>
                <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-xs text-[var(--af-text-secondary)]">
                  可信度 {confidenceCard.score}
                </span>
                <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-xs text-[var(--af-text-secondary)]">
                  官方源 {Math.round((confidenceCard.official_source_ratio || 0) * 100)}%
                </span>
              </div>
              {confidenceCard.reasons?.length ? (
                <div className="mt-4 space-y-2">
                  {confidenceCard.reasons.map((value) => (
                    <div key={`confidence-reason-${value}`} className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                      {value}
                    </div>
                  ))}
                </div>
              ) : null}
              {confidenceCard.concerns?.length ? (
                <div className="mt-4 flex flex-wrap gap-2">
                  {confidenceCard.concerns.map((value) => (
                    <span key={`confidence-concern-${value}`} className="rounded-full bg-[color-mix(in_srgb,var(--af-warning)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-warning)]">
                      {value}
                    </span>
                  ))}
                </div>
              ) : null}
            </article>
          ) : null}
          {methodologyCard ? (
            <article className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">方法论卡</p>
              {methodologyCard.scope_summary ? (
                <p className="mt-3 text-sm leading-6 text-[var(--af-text-secondary)]">{methodologyCard.scope_summary}</p>
              ) : null}
              <div className="mt-3 grid grid-cols-1 gap-3">
                <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">取数与边界</p>
                  <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{methodologyCard.data_boundary}</p>
                </div>
                <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">Pipeline</p>
                  <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{methodologyCard.pipeline_summary}</p>
                </div>
              </div>
              {methodologyCard.query_plan?.length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {methodologyCard.query_plan.slice(0, 4).map((value) => (
                    <span key={`method-query-${value}`} className="rounded-full bg-[var(--af-surface-muted)] px-2.5 py-1 text-[11px] text-[var(--af-text-secondary)]">
                      {value}
                    </span>
                  ))}
                </div>
              ) : null}
            </article>
          ) : null}
        </div>
      ) : null}

      {coverageGaps.length ? (
        <article className="rounded-[24px] border border-[color-mix(in_srgb,var(--af-warning)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)] p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">缺证与补证建议</p>
          <div className="mt-3 grid grid-cols-1 gap-3">
            {coverageGaps.map((gap) => (
              <div key={`${gap.title}-${gap.detail}`} className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-semibold text-[var(--af-text-primary)]">{gap.title}</p>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] ${gap.severity === "high" ? "af-chip af-chip-danger" : gap.severity === "medium" ? "af-chip af-chip-warning" : "af-chip"}`}>
                    {gap.severity === "high" ? "高优先级" : gap.severity === "medium" ? "中优先级" : "低优先级"}
                  </span>
                </div>
                <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{gap.detail}</p>
                <p className="mt-2 text-sm leading-6 text-[var(--af-warning)]">建议：{gap.recommended_action}</p>
              </div>
            ))}
          </div>
        </article>
      ) : null}
    </>
  );
}
