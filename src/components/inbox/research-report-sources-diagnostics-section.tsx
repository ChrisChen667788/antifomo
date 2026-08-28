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
  const evidenceGate = report.research_evidence_gate;
  const questionTree = report.research_question_tree;
  const scopeContract = report.research_scope_contract;
  const citationGate = report.research_citation_gate;
  const admissions = report.research_source_admissions || [];
  const generationFallbackUsed = Boolean(diagnostics?.generation_fallback_used);
  const gatePassed = Boolean(evidenceGate?.passed);
  const interactionState = report.interaction_state || report.clarification_packet?.interaction_state || (gatePassed ? "ready" : "awaiting_user");
  const gateTone = gatePassed
    ? "border-[color-mix(in_srgb,var(--af-success)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-success)_8%,var(--af-surface-muted))] text-[var(--af-success)]"
    : interactionState === "provisional"
      ? "border-[color-mix(in_srgb,var(--af-warning)_35%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-warning)_8%,var(--af-surface-muted))] text-[var(--af-text-primary)]"
      : "border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_7%,var(--af-surface-muted))] text-[var(--af-text-primary)]";

  return (
    <>
      {generationFallbackUsed ? (
        <section
          className="mt-6 border border-[color-mix(in_srgb,var(--af-danger)_35%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-danger)_8%,var(--af-surface-muted))] p-4 text-[var(--af-danger)]"
          aria-label="正式模型降级状态"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] opacity-70">生成质量门</p>
              <p className="mt-1 text-base font-semibold">正式模型降级稿，不可直接交付</p>
              <p className="mt-1 text-xs leading-5 opacity-85">
                {diagnostics?.generation_notes?.[0] || "正式研报模型未成功返回，当前为降级草稿。"}
              </p>
            </div>
            <span className="border border-current px-2.5 py-1 text-xs font-semibold">系统降级</span>
          </div>
          {diagnostics?.generation_notes?.[1] ? (
            <p className="mt-3 text-xs leading-5 opacity-85">下一步：{diagnostics.generation_notes[1]}</p>
          ) : null}
        </section>
      ) : null}
      {evidenceGate?.enforced ? (
        <section className={`mt-6 border p-4 ${gateTone}`} aria-label="研究证据治理">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] opacity-70">证据检查</p>
              <p className="mt-1 text-base font-semibold">
                {gatePassed
                  ? "来源与引用已达到交付要求"
                  : interactionState === "provisional"
                    ? "草稿可阅读，正式交付仍需补少量证据"
                    : "已保留有效来源，补充信息后可继续"}
              </p>
              <p className="mt-1 text-xs leading-5 opacity-80">
                {report.clarification_packet?.summary
                  || `${scopeContract?.industries?.length ? scopeContract.industries.join(" / ") : "研究范围待确认"}${
                    scopeContract?.regions?.length ? ` · ${scopeContract.regions.join(" / ")}` : ""
                  }`}
              </p>
            </div>
            <span className="border border-current px-2.5 py-1 text-xs font-semibold">
              {gatePassed ? "可交付" : interactionState === "provisional" ? "受限草稿" : "待补充"}
            </span>
          </div>

          <details className="mt-4 border-t border-current/20 pt-3">
            <summary className="cursor-pointer text-xs font-semibold">查看证据检查明细</summary>
          <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-5">
            {[
              ["来源准入", `${evidenceGate.accepted_source_count}/${evidenceGate.candidate_source_count}`],
              ["官方来源", `${evidenceGate.official_source_count}/${evidenceGate.minimum_official_source_count}`],
              ["独立域", `${evidenceGate.unique_domain_count}/${evidenceGate.minimum_unique_domain_count}`],
              ["问题覆盖", `${evidenceGate.question_coverage_percent}%`],
              ["主张覆盖", `${citationGate?.critical_claim_coverage_percent || 0}%`],
            ].map(([label, value]) => (
              <div key={label} className="border border-current/20 bg-[var(--af-surface-elevated)] px-3 py-2 text-[var(--af-text-primary)]">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--af-text-tertiary)]">{label}</p>
                <p className="mt-1 text-sm font-semibold">{value}</p>
              </div>
            ))}
          </div>

          {evidenceGate.blockers.length || evidenceGate.warnings.length ? (
            <div className="mt-4 space-y-1.5 text-xs leading-5">
              {[...evidenceGate.blockers, ...evidenceGate.warnings].slice(0, 6).map((item) => (
                <p key={item}>• {item}</p>
              ))}
            </div>
          ) : null}

          {questionTree?.questions?.length ? (
            <div className="mt-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] opacity-70">研究问题树</p>
              <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
                {questionTree.questions.map((node) => (
                  <div key={node.question_id} className="border border-current/20 bg-[var(--af-surface-elevated)] px-3 py-2 text-[var(--af-text-primary)]">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-xs font-semibold">{node.axis}</p>
                      <span className="text-[10px] text-[var(--af-text-tertiary)]">
                        {node.accepted_source_count} 条 · {node.coverage_status}
                      </span>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-[var(--af-text-secondary)]">{node.question}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {admissions.some((row) => row.decision !== "accepted") ? (
            <div className="mt-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] opacity-70">
                被拦截来源 · 模糊 {evidenceGate.ambiguous_source_count} / 拒绝 {evidenceGate.rejected_source_count}
              </p>
              <div className="mt-2 space-y-2">
                {admissions.filter((row) => row.decision !== "accepted").slice(0, 4).map((row) => (
                  <div key={row.source_id} className="border border-current/20 bg-[var(--af-surface-elevated)] px-3 py-2 text-xs text-[var(--af-text-secondary)]">
                    <p className="font-semibold text-[var(--af-text-primary)]">{row.title || row.domain || "未命名来源"}</p>
                    <p className="mt-1 leading-5">{row.reasons.join("；")}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {citationGate?.enforced ? (
            <div className="mt-4 border-t border-current/20 pt-3 text-xs leading-5">
              <p className="font-semibold">
                主张引用门：{citationGate.status} · 支撑 {citationGate.supported_claim_count}/{citationGate.claim_count} · 引用完整率 {citationGate.citation_completeness_percent}%
              </p>
              {citationGate.blockers.slice(0, 3).map((item) => <p key={item} className="mt-1">• {item}</p>)}
            </div>
          ) : null}
          </details>
        </section>
      ) : null}

      <details className="mt-6 rounded-lg border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-4">
        <summary className="cursor-pointer text-sm font-semibold text-[var(--af-text-secondary)]">
          高级诊断与检索过程
        </summary>
      <div className={`mt-4 grid grid-cols-1 gap-4 ${hideSources ? "md:grid-cols-1" : "md:grid-cols-[1.15fr_0.85fr]"}`}>
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
                  {diagnostics.snapshot_recovery_used ? (
                    <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px]">
                      同题证据恢复 · fresh {diagnostics.fresh_source_count || 0} / snapshot {diagnostics.snapshot_recovery_source_count || 0}
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
                  公开来源 {diagnostics.adapter_hit_count}
                </span>
                <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-secondary)]">
                  搜索来源 {diagnostics.search_hit_count}
                </span>
                <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-secondary)]">
                  近 {diagnostics.recency_window_years} 年窗口
                </span>
                {diagnostics.filtered_old_source_count > 0 ? (
                  <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-secondary)]">
                    过滤旧来源 {diagnostics.filtered_old_source_count}
                  </span>
                ) : null}
                {diagnostics.filtered_region_conflict_count > 0 ? (
                  <span className="rounded-full bg-[color-mix(in_srgb,var(--af-danger)_10%,var(--af-surface-muted))] px-2.5 py-1 text-[var(--af-danger)]">
                    区域冲突 {diagnostics.filtered_region_conflict_count}
                  </span>
                ) : null}
                {diagnostics.strict_topic_source_count > 0 ? (
                  <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-secondary)]">
                    主题相关来源 {diagnostics.strict_topic_source_count}
                  </span>
                ) : null}
                <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-secondary)]">
                  来源质量 {qualityLabel(diagnostics.retrieval_quality)}
                </span>
                <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-secondary)]">
                  主题匹配 {Math.round(diagnostics.strict_match_ratio * 100)}%
                </span>
                <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-secondary)]">
                  官方源 {Math.round(diagnostics.official_source_ratio * 100)}%
                </span>
                {diagnostics.unique_domain_count > 0 ? (
                  <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[var(--af-text-secondary)]">
                    覆盖来源 {diagnostics.unique_domain_count}
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
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-text-tertiary)]">本次来源</p>
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
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-text-tertiary)]">主题线索</p>
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
      </details>
    </>
  );
}
