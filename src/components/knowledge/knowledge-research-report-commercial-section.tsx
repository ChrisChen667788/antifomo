"use client";

import Link from "next/link";
import type { ApiKnowledgeEntry } from "@/lib/api/types";
import { qualityTone, valueBucket, type KnowledgeTranslateFn } from "@/components/knowledge/knowledge-detail-card-model";

interface KnowledgeResearchReportCommercialSectionProps {
  commercialIntelligence: ApiKnowledgeEntry["commercial_intelligence"] | null | undefined;
  t: KnowledgeTranslateFn;
}

export function KnowledgeResearchReportCommercialSection({
  commercialIntelligence,
  t,
}: KnowledgeResearchReportCommercialSectionProps) {
  const intelligenceAccounts = commercialIntelligence?.accounts || [];
  const intelligenceOpportunities = commercialIntelligence?.opportunities || [];
  const intelligenceBenchmark = commercialIntelligence?.benchmark;
  const intelligenceMaturity = commercialIntelligence?.maturity;

  if (!intelligenceAccounts.length && !intelligenceOpportunities.length && !intelligenceBenchmark && !intelligenceMaturity) {
    return null;
  }

  return (
    <div className="grid grid-cols-1 gap-4">
      <div className="space-y-4">
        {intelligenceAccounts.length ? (
          <article className="rounded-[24px] border border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)] p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">账户对象</p>
                <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">把研报中的重点对象转成可持续跟进的账户页。</p>
              </div>
              <Link href="/knowledge/accounts" className="text-sm font-medium text-[var(--af-info)]">
                查看账户页
              </Link>
            </div>
            <div className="mt-4 space-y-3">
              {intelligenceAccounts.slice(0, 3).map((account) => (
                <Link
                  key={`intelligence-account-${account.slug}`}
                  href={`/knowledge/accounts/${account.slug}`}
                  className="block rounded-[20px] border border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)] p-4 transition hover:border-[var(--af-border-strong)] hover:bg-[var(--af-surface-hover)]"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-sm font-semibold text-[var(--af-text-primary)]">{account.name}</h3>
                    <div className="flex flex-wrap gap-2 text-[11px]">
                      <span className={`rounded-full px-2 py-0.5 ${valueBucket(account.confidence_score, t).className}`}>
                        {valueBucket(account.confidence_score, t).label}
                      </span>
                      <span className="rounded-full bg-[var(--af-surface-muted)] px-2 py-0.5 text-[var(--af-text-secondary)]">
                        预算概率 {account.budget_probability}%
                      </span>
                    </div>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{account.summary}</p>
                  {account.next_best_action ? (
                    <p className="mt-2 text-sm font-medium leading-6 text-[var(--af-info)]">下一步：{account.next_best_action}</p>
                  ) : null}
                </Link>
              ))}
            </div>
          </article>
        ) : null}

        {intelligenceOpportunities.length ? (
          <article className="rounded-[24px] border border-[color-mix(in_srgb,var(--af-success)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)] p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">机会对象</p>
            <div className="mt-4 space-y-3">
              {intelligenceOpportunities.slice(0, 3).map((opportunity) => (
                <Link
                  key={`intelligence-opportunity-${opportunity.title}`}
                  href={`/knowledge/accounts/${opportunity.account_slug}`}
                  className="block rounded-[20px] border border-[color-mix(in_srgb,var(--af-success)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)] p-4 transition hover:border-[var(--af-border-strong)] hover:bg-[var(--af-surface-hover)]"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-sm font-semibold text-[var(--af-text-primary)]">{opportunity.title}</h3>
                    <span className={`rounded-full px-2 py-0.5 text-[11px] ${valueBucket(opportunity.score, t).className}`}>
                      {opportunity.confidence_label || valueBucket(opportunity.score, t).label}
                    </span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{opportunity.next_best_action}</p>
                  <p className="mt-2 text-xs text-[var(--af-text-tertiary)]">窗口：{opportunity.entry_window}</p>
                </Link>
              ))}
            </div>
          </article>
        ) : null}
      </div>

      <div className="space-y-4">
        {intelligenceBenchmark ? (
          <article className="rounded-[24px] border border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)] p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">标杆与对标</p>
            <p className="mt-3 text-sm leading-6 text-[var(--af-text-secondary)]">{intelligenceBenchmark.summary}</p>
            {intelligenceBenchmark.cases?.length ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {intelligenceBenchmark.cases.map((value) => (
                  <span key={`benchmark-${value}`} className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-info)]">
                    {value}
                  </span>
                ))}
              </div>
            ) : null}
          </article>
        ) : null}

        {intelligenceMaturity ? (
          <article className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">成熟度评估</p>
              <span className="rounded-full bg-[var(--af-surface-muted)] px-2.5 py-1 text-xs text-[var(--af-text-secondary)]">
                {intelligenceMaturity.stage}
              </span>
            </div>
            <p className="mt-3 text-sm leading-6 text-[var(--af-text-secondary)]">{intelligenceMaturity.summary}</p>
            <div className="mt-3 grid grid-cols-1 gap-3">
              {intelligenceMaturity.dimensions?.map((dimension) => (
                <div key={`maturity-${dimension.name}`} className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium text-[var(--af-text-primary)]">{dimension.name}</p>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] ${qualityTone(dimension.level || "low")}`}>
                      {dimension.level === "high" ? "高" : dimension.level === "medium" ? "中" : "低"}
                    </span>
                  </div>
                  <p className="mt-1 text-sm leading-6 text-[var(--af-text-secondary)]">{dimension.note}</p>
                </div>
              ))}
            </div>
          </article>
        ) : null}
      </div>
    </div>
  );
}
