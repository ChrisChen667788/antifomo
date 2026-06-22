"use client";

import { ExternalLinkActions, normalizeExternalUrl } from "@/components/ui/external-link-actions";
import type { ApiResearchReport } from "@/lib/api/types";
import type {
  ReportToneMeta,
  ResearchPipelineStageSummary,
  ResearchReportCoreEntity,
  ResearchReportSource,
  RetrievalRoutingCard,
} from "@/components/inbox/research-report-section-types";

export function ResearchReportSourcesDiagnosticsSection({
  report,
  queryPlanLabel,
  sourcesLabel,
  hideSources,
  diagnostics,
  evidenceMode,
  retrievalRoutingCards,
  pipelineStages,
  enabledSourceLabels,
  candidateProfileCompanies,
  guardedBacklog,
  guardedReasonLabels,
  supportedTargetAccounts,
  unsupportedTargetAccounts,
  qualityExpansionQueries,
  coreEntities,
  scopeRegions,
  scopeIndustries,
  scopeClients,
  matchedSourceLabels,
  topicAnchorTerms,
  matchedThemeLabels,
  candidateProfileSourceLabels,
  groupedSources,
  sourcePathTitle,
  sourceDiagTitle,
  qualityLabel,
  sourceTierLabel,
  classifySourceTier,
}: {
  report: ApiResearchReport;
  queryPlanLabel: string;
  sourcesLabel: string;
  hideSources: boolean;
  diagnostics: ApiResearchReport["source_diagnostics"];
  evidenceMode: ReportToneMeta;
  retrievalRoutingCards: RetrievalRoutingCard[];
  pipelineStages: ResearchPipelineStageSummary[];
  enabledSourceLabels: string[];
  candidateProfileCompanies: string[];
  guardedBacklog: boolean;
  guardedReasonLabels: string[];
  supportedTargetAccounts: string[];
  unsupportedTargetAccounts: string[];
  qualityExpansionQueries: string[];
  coreEntities: ResearchReportCoreEntity[];
  scopeRegions: string[];
  scopeIndustries: string[];
  scopeClients: string[];
  matchedSourceLabels: string[];
  topicAnchorTerms: string[];
  matchedThemeLabels: string[];
  candidateProfileSourceLabels: string[];
  groupedSources: Record<"official" | "media" | "aggregate", ResearchReportSource[]>;
  sourcePathTitle: string;
  sourceDiagTitle: string;
  qualityLabel: (value: string) => string;
  sourceTierLabel: (value: string) => string;
  classifySourceTier: (source: ResearchReportSource) => string;
}) {
  return (
    <>
      <div className={`mt-6 grid grid-cols-1 gap-4 ${hideSources ? "md:grid-cols-1" : "md:grid-cols-[1.15fr_0.85fr]"}`}>
        <div className="af-report-muted-surface rounded-2xl border border-[var(--af-border-subtle)] p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">{sourcePathTitle}</p>
          <div className="mt-3">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">
              {queryPlanLabel}
            </p>
            <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
              {report.query_plan.map((query) => (
                <li key={query} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                  {query}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {!hideSources ? (
        <div className="af-report-muted-surface rounded-2xl border border-[var(--af-border-subtle)] p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">{sourcesLabel}</p>
          {diagnostics ? (
            <div className="mt-3 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">{sourceDiagTitle}</p>
              <div className={`mt-3 rounded-2xl border px-3.5 py-3 ${evidenceMode.className}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px] font-semibold">
                    {diagnostics.evidence_mode_label || evidenceMode.label}
                  </span>
                  {diagnostics.corrective_triggered ? (
                    <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px]">
                      已补充核验
                    </span>
                  ) : null}
                  {diagnostics.expansion_triggered ? (
                    <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px]">
                      已扩展来源
                    </span>
                  ) : null}
                  {diagnostics.quality_expansion_triggered ? (
                    <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px]">
                      质量扩源 {diagnostics.quality_expansion_rounds || 1} 轮
                    </span>
                  ) : null}
                </div>
                <p className="mt-2 text-xs leading-5">
                  {evidenceMode.note}
                </p>
                <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
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
                        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">
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
                <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-secondary)]">
                  启用源 {enabledSourceLabels.length}
                </span>
                <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-secondary)]">
                  命中公开源 {diagnostics.adapter_hit_count}
                </span>
                <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-secondary)]">
                  命中搜索源 {diagnostics.search_hit_count}
                </span>
                <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-secondary)]">
                  近 {diagnostics.recency_window_years} 年窗口
                </span>
                {diagnostics.filtered_old_source_count > 0 ? (
                  <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-secondary)]">
                    剔除过旧来源 {diagnostics.filtered_old_source_count}
                  </span>
                ) : null}
                {diagnostics.filtered_region_conflict_count > 0 ? (
                  <span className="rounded-full bg-[color-mix(in_srgb,var(--af-danger)_10%,var(--af-surface-muted))] px-2.5 py-1 text-[var(--af-danger)]">
                    拦截越界区域 {diagnostics.filtered_region_conflict_count}
                  </span>
                ) : null}
                {diagnostics.strict_topic_source_count > 0 ? (
                  <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-secondary)]">
                    严格主题保留 {diagnostics.strict_topic_source_count}
                  </span>
                ) : null}
                <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-secondary)]">
                  来源质量 {qualityLabel(diagnostics.retrieval_quality)}
                </span>
                <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-secondary)]">
                  严格命中 {Math.round(diagnostics.strict_match_ratio * 100)}%
                </span>
                <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-secondary)]">
                  官方源 {Math.round(diagnostics.official_source_ratio * 100)}%
                </span>
                {diagnostics.unique_domain_count > 0 ? (
                  <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-secondary)]">
                    覆盖域名 {diagnostics.unique_domain_count}
                  </span>
                ) : null}
                {candidateProfileCompanies.length ? (
                  <span className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-2.5 py-1 text-[var(--af-info)]">
                    建议核验公司 {candidateProfileCompanies.length}
                  </span>
                ) : null}
                {diagnostics.candidate_profile_hit_count > 0 ? (
                  <span className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-2.5 py-1 text-[var(--af-info)]">
                    公开来源 {diagnostics.candidate_profile_hit_count}
                  </span>
                ) : null}
                {diagnostics.candidate_profile_official_hit_count > 0 ? (
                  <span className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-2.5 py-1 text-[var(--af-info)]">
                    其中官方源 {diagnostics.candidate_profile_official_hit_count}
                  </span>
                ) : null}
                {diagnostics.quality_expansion_triggered ? (
                  <>
                    <span className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-2.5 py-1 text-[var(--af-info)]">
                      质量扩源新增 {diagnostics.quality_expansion_added_source_count || 0}
                    </span>
                    <span className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-2.5 py-1 text-[var(--af-info)]">
                      自评分 {diagnostics.quality_expansion_before_score || 0}→{diagnostics.quality_expansion_after_score || 0}
                    </span>
                  </>
                ) : null}
                {guardedBacklog ? (
                  <span className="rounded-full bg-[color-mix(in_srgb,var(--af-danger)_10%,var(--af-surface-muted))] px-2.5 py-1 text-[var(--af-danger)]">
                    已降级为 guarded backlog
                  </span>
                ) : null}
              </div>
              {guardedReasonLabels.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-text-tertiary)]">降级原因</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {guardedReasonLabels.map((label) => (
                      <span key={label} className="rounded-full border border-[color-mix(in_srgb,var(--af-danger)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-danger)_10%,var(--af-surface-muted))] px-2.5 py-1 text-xs text-[var(--af-danger)]">
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {supportedTargetAccounts.length || unsupportedTargetAccounts.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-text-tertiary)]">目标账户支撑</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {supportedTargetAccounts.map((label) => (
                      <span key={`supported-${label}`} className="rounded-full border border-[color-mix(in_srgb,var(--af-success)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-success)_9%,var(--af-surface-muted))] px-2.5 py-1 text-xs text-[var(--af-success)]">
                        已支撑 · {label}
                      </span>
                    ))}
                    {unsupportedTargetAccounts.map((label) => (
                      <span key={`unsupported-${label}`} className="rounded-full border border-[color-mix(in_srgb,var(--af-danger)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-danger)_10%,var(--af-surface-muted))] px-2.5 py-1 text-xs text-[var(--af-danger)]">
                        未支撑 · {label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {qualityExpansionQueries.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-text-tertiary)]">质量扩源查询</p>
                  <div className="mt-2 space-y-2">
                    {qualityExpansionQueries.slice(0, 3).map((query) => (
                      <p
                        key={`quality-expansion-${query}`}
                        className="rounded-2xl border border-[color-mix(in_srgb,var(--af-info)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-3 py-2 text-xs leading-5 text-[var(--af-info)]"
                      >
                        {query}
                      </p>
                    ))}
                  </div>
                </div>
              ) : null}
              {diagnostics.normalized_entity_count > 0 ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-text-tertiary)]">实体归一化</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <span className="rounded-full border border-[color-mix(in_srgb,var(--af-info)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-2.5 py-1 text-xs text-[var(--af-info)]">
                      总实体 {diagnostics.normalized_entity_count}
                    </span>
                    <span className="rounded-full border border-[color-mix(in_srgb,var(--af-info)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-2.5 py-1 text-xs text-[var(--af-info)]">
                      甲方 {diagnostics.normalized_target_count}
                    </span>
                    <span className="rounded-full border border-[color-mix(in_srgb,var(--af-info)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-2.5 py-1 text-xs text-[var(--af-info)]">
                      竞品 {diagnostics.normalized_competitor_count}
                    </span>
                    <span className="rounded-full border border-[color-mix(in_srgb,var(--af-info)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-2.5 py-1 text-xs text-[var(--af-info)]">
                      伙伴 {diagnostics.normalized_partner_count}
                    </span>
                  </div>
                </div>
              ) : null}
              {report.entity_graph?.entities?.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-text-tertiary)]">核心实体候选</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {coreEntities.map((entity) => (
                      <span
                        key={`entity-${entity.canonical_name}`}
                        className="rounded-full border border-[color-mix(in_srgb,var(--af-info)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-2.5 py-1 text-xs text-[var(--af-info)]"
                      >
                        {entity.canonical_name}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {enabledSourceLabels.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-text-tertiary)]">当前启用</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {enabledSourceLabels.map((label) => (
                      <span key={label} className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-2.5 py-1 text-xs text-[var(--af-text-secondary)]">
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {scopeRegions.length || scopeIndustries.length || scopeClients.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-text-tertiary)]">范围锁定</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {scopeRegions.map((label) => (
                      <span key={`scope-region-${label}`} className="rounded-full border border-[color-mix(in_srgb,var(--af-info)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-2.5 py-1 text-xs text-[var(--af-info)]">
                        区域 · {label}
                      </span>
                    ))}
                    {scopeIndustries.map((label) => (
                      <span key={`scope-industry-${label}`} className="rounded-full border border-[color-mix(in_srgb,var(--af-info)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-2.5 py-1 text-xs text-[var(--af-info)]">
                        领域 · {label}
                      </span>
                    ))}
                    {scopeClients.map((label) => (
                      <span key={`scope-client-${label}`} className="rounded-full border border-[color-mix(in_srgb,var(--af-info)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-2.5 py-1 text-xs text-[var(--af-info)]">
                        公司 · {label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {matchedSourceLabels.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-text-tertiary)]">本次命中</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {matchedSourceLabels.map((label) => (
                      <span key={label} className="rounded-full border border-[color-mix(in_srgb,var(--af-info)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-2.5 py-1 text-xs text-[var(--af-info)]">
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {topicAnchorTerms.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-text-tertiary)]">主题锚点</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {topicAnchorTerms.map((label) => (
                      <span key={label} className="rounded-full border border-[color-mix(in_srgb,var(--af-info)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-2.5 py-1 text-xs text-[var(--af-info)]">
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {matchedThemeLabels.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-text-tertiary)]">命中主题</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {matchedThemeLabels.map((label) => (
                      <span key={label} className="rounded-full border border-[color-mix(in_srgb,var(--af-success)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-success)_9%,var(--af-surface-muted))] px-2.5 py-1 text-xs text-[var(--af-success)]">
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {candidateProfileCompanies.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-text-tertiary)]">建议核验公司</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {candidateProfileCompanies.map((label) => (
                      <span key={label} className="rounded-full border border-[color-mix(in_srgb,var(--af-info)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-2.5 py-1 text-xs text-[var(--af-info)]">
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {candidateProfileSourceLabels.length ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-text-tertiary)]">公开来源</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {candidateProfileSourceLabels.map((label) => (
                      <span key={label} className="rounded-full border border-[color-mix(in_srgb,var(--af-info)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-2.5 py-1 text-xs text-[var(--af-info)]">
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
              <p className="text-sm leading-6 text-[var(--af-text-tertiary)]">当前未获取到可展示来源，显示的是本地演示框架。</p>
            ) : null}
            {[
              { key: "official", title: "官方源", items: groupedSources.official },
              { key: "media", title: "媒体源", items: groupedSources.media },
              { key: "aggregate", title: "聚合源", items: groupedSources.aggregate },
            ]
              .filter((group) => group.items.length)
              .map((group) => (
                <div key={group.key} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">{group.title}</p>
                    <span className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-2 py-0.5 text-[11px] text-[var(--af-text-tertiary)]">
                      {group.items.length}
                    </span>
                  </div>
                  <div className="mt-3 space-y-3">
                    {group.items.map((source) => (
                      <div
                        key={`${group.key}-${source.url}-${source.search_query}`}
                        className="block rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3 transition hover:border-[var(--af-border-strong)] hover:bg-[var(--af-surface-hover)]"
                      >
                        <div className="flex items-center gap-2 text-xs text-[var(--af-text-tertiary)]">
                          <span className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-2 py-0.5">
                            {sourceTierLabel(source.source_tier || classifySourceTier(source))}
                          </span>
                          {source.source_label ? (
                            <span className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-2 py-0.5">
                              {source.source_label}
                            </span>
                          ) : null}
                          <span className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-2 py-0.5">
                            {source.domain || "web"}
                          </span>
                          <span>{source.search_query}</span>
                        </div>
                        <a
                          href={normalizeExternalUrl(source.url)}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-2 block text-sm font-semibold leading-6 text-[var(--af-text-primary)] underline-offset-4 text-[var(--af-info)] hover:underline"
                        >
                          {source.title}
                        </a>
                        <p className="mt-1 text-sm leading-6 text-[var(--af-text-secondary)]">{source.snippet}</p>
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
    </>
  );
}
