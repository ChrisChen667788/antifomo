"use client";

import Link from "next/link";
import type { useResearchCenterController } from "@/components/research/use-research-center-controller";
import { AppIcon } from "@/components/ui/app-icon";
import {
  buildPreview,
  getActionType,
  getResearchActionCards,
  getResearchKeyword,
  getResearchRankedPreview,
  getResearchReadinessStatus,
  getResearchReportMeta,
  getResearchSourceCount,
  getResearchSourceDiagnostics,
  getResearchWeakSectionSummary,
  parseActionPhases,
  qualityLabel,
  qualityTone,
} from "@/components/research/research-center-utils";

type ResearchCenterController = ReturnType<typeof useResearchCenterController>;
type ResearchCenterResultsSectionProps = ResearchCenterController["resultsSectionProps"];

export function ResearchCenterResultsSection({
  t,
  activePerspective,
  activeFilterLabels,
  visibleItems,
  loading,
  error,
}: ResearchCenterResultsSectionProps) {
  return (
        <div className="space-y-4">
          <section className="af-glass rounded-[30px] p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="af-kicker">{t("research.centerResultKicker", "Workspace")}</p>
                <h3 className="mt-2 text-xl font-semibold tracking-[-0.03em] text-[var(--af-text-primary)]">
                  {t("research.centerResultTitle", "研究结果工作台")}
                </h3>
                <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">{activePerspective.desc}</p>
              </div>
              <div className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-1.5 text-sm text-[var(--af-text-tertiary)]">
                {t("research.centerVisibleCount", "可见卡片")} · {visibleItems.length}
              </div>
            </div>

            {activeFilterLabels.length ? (
              <div className="mt-4 flex flex-wrap gap-2">
                {activeFilterLabels.map((label) => (
                  <span key={label} className="rounded-full af-chip af-chip-info px-3 py-1.5 text-xs font-medium ">
                    {label}
                  </span>
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">
                {t("research.centerNoFilterHint", "当前展示全部研报与行动卡，可从左侧按区域、行业或动作类型快速收窄。")}
              </p>
            )}
          </section>

          {loading ? (
            <section className="af-glass rounded-[30px] p-5 md:p-7 text-sm text-[var(--af-text-tertiary)]">
              {t("common.loading", "加载中")}
            </section>
          ) : null}
          {error ? (
            <section className="af-glass rounded-[30px] p-5 md:p-7 text-sm text-[var(--af-danger)]">
              {error}
            </section>
          ) : null}

          {!loading && !error && visibleItems.length === 0 ? (
            <section className="af-glass rounded-[30px] p-5 md:p-7 text-sm text-[var(--af-text-tertiary)]">
              {t("research.centerEmpty", "当前没有匹配的研报或行动卡。")}
            </section>
          ) : null}

          {!loading && !error ? (
            <section className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
              {visibleItems.map((entry) => {
                const isReport = entry.source_domain === "research.report";
                const actionType = isReport ? null : getActionType(entry);
                const sourceCount = getResearchSourceCount(entry);
                const keyword = getResearchKeyword(entry);
                const reportMeta = getResearchReportMeta(entry);
                const diagnosticsMeta = isReport ? getResearchSourceDiagnostics(entry) : null;
                const readinessStatus = isReport ? getResearchReadinessStatus(entry) : "needs_evidence";
                const weakSectionSummary = isReport ? getResearchWeakSectionSummary(entry) : null;
                const rankedPreview = isReport ? getResearchRankedPreview(entry) : [];
                const actionCards = isReport ? getResearchActionCards(entry) : [];
                return (
                  <article
                    key={entry.id}
                    className="af-glass rounded-[28px] p-5 transition duration-200 hover:-translate-y-0.5 hover:shadow-[0_20px_45px_rgba(15,23,42,0.08)]"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${
                          isReport ? "af-chip af-chip-info" : "af-chip af-chip-warning"
                        }`}
                      >
                        {isReport ? t("research.centerReportBadge", "研报") : t("research.centerActionBadge", "行动卡")}
                      </span>
                      {entry.is_focus_reference ? (
                        <span className="rounded-full af-chip af-chip-info px-2.5 py-1 text-[11px] font-semibold ">
                          {t("research.centerFocusBadge", "Focus 参考")}
                        </span>
                      ) : null}
                    </div>

                    <Link href={`/knowledge/${entry.id}`} className="block">
                      <h3 className="mt-4 text-lg font-semibold leading-7 text-[var(--af-text-primary)]">{entry.title}</h3>
                      <p className="mt-3 text-sm leading-6 text-[var(--af-text-secondary)]">{buildPreview(entry)}</p>
                    </Link>

                    {isReport && diagnosticsMeta ? (
                      <div className="mt-4 space-y-3">
                        <div className="grid gap-3 sm:grid-cols-2">
                          <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                            <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">可信度</p>
                            <div className="mt-2 flex flex-wrap gap-2">
                              <span
                                className={`rounded-full px-2.5 py-1 text-[11px] ${
                                  diagnosticsMeta.evidenceMode === "strong"
                                    ? "af-chip af-chip-success"
                                    : diagnosticsMeta.evidenceMode === "provisional"
                                      ? "af-chip af-chip-warning"
                                      : "af-chip"
                                }`}
                              >
                                {diagnosticsMeta.evidenceMode === "strong"
                                  ? "强证据"
                                  : diagnosticsMeta.evidenceMode === "provisional"
                                    ? "可用初版"
                                    : "待核实"}
                              </span>
                              <span className="rounded-full af-chip px-2.5 py-1 text-[11px] ">
                                官方源 {Math.round(diagnosticsMeta.officialSourceRatio * 100)}%
                              </span>
                              <span className="rounded-full af-chip px-2.5 py-1 text-[11px] ">
                                严格命中 {Math.round(diagnosticsMeta.strictMatchRatio * 100)}%
                              </span>
                            </div>
                            <p className="mt-2 text-xs leading-5 text-[var(--af-text-tertiary)]">
                              {diagnosticsMeta.correctiveTriggered
                                ? "已补充核验，优先看新增官方来源和严格命中结果。"
                                : diagnosticsMeta.expansionTriggered
                                  ? "已扩展来源，建议继续核对关键实体和范围。"
                                  : "当前展示的是本次来源可信度摘要。"}
                            </p>
                          </div>
                          <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                            <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">账户与门槛</p>
                            <div className="mt-2 flex flex-wrap gap-2">
                              <span
                                className={`rounded-full px-2.5 py-1 text-[11px] ${
                                  diagnosticsMeta.unsupportedTargetAccounts.length
                                    ? "af-chip af-chip-danger"
                                    : diagnosticsMeta.supportedTargetAccounts.length
                                      ? "af-chip af-chip-success"
                                      : "af-chip"
                                }`}
                              >
                                {diagnosticsMeta.unsupportedTargetAccounts.length
                                  ? "目标账户待支撑"
                                  : diagnosticsMeta.supportedTargetAccounts.length
                                    ? `已支撑 ${diagnosticsMeta.supportedTargetAccounts.length} 个账户`
                                    : "待收敛到账户"}
                              </span>
                              <span
                                className={`rounded-full px-2.5 py-1 text-[11px] ${
                                  readinessStatus === "ready"
                                    ? "af-chip af-chip-success"
                                    : readinessStatus === "degraded"
                                      ? "af-chip af-chip-warning"
                                      : "af-chip"
                                }`}
                              >
                                {readinessStatus === "ready"
                                  ? "可直接推进"
                                  : readinessStatus === "degraded"
                                    ? "候选推进"
                                    : "待核验"}
                              </span>
                              {diagnosticsMeta.guardedBacklog ? (
                                <span className="rounded-full af-chip af-chip-danger px-2.5 py-1 text-[11px] ">
                                  待复核
                                </span>
                              ) : null}
                            </div>
                            <p className="mt-2 text-xs leading-5 text-[var(--af-text-tertiary)]">
                              {diagnosticsMeta.unsupportedTargetAccounts.slice(0, 2).join(" / ") ||
                                diagnosticsMeta.supportedTargetAccounts.slice(0, 2).join(" / ") ||
                                "当前还没有稳定的目标账户支撑，适合继续核验。"}
                            </p>
                          </div>
                        </div>
                        {weakSectionSummary ? (
                          <div className="rounded-[18px] af-state-panel-warning p-3">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--af-warning)]">最弱章节</p>
                              <span
                                className={`rounded-full px-2.5 py-1 text-[11px] ${
                                  weakSectionSummary.status === "needs_evidence"
                                    ? "af-chip af-chip-danger"
                                    : "af-chip af-chip-warning"
                                }`}
                              >
                                {weakSectionSummary.status === "needs_evidence" ? "待核验" : "待收紧"}
                              </span>
                            </div>
                            <p className="mt-2 text-sm font-semibold text-[var(--af-text-primary)]">{weakSectionSummary.title}</p>
                            <p className="mt-2 text-xs leading-5 text-[var(--af-text-secondary)]">{weakSectionSummary.summary}</p>
                          </div>
                        ) : null}
                      </div>
                    ) : null}

                    {isReport && actionCards.length ? (
                      <div className="mt-4 grid gap-3">
                        {actionCards.map((card) => (
                          <div key={`${entry.id}-${card.title}`} className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                            <p className="break-words text-sm font-semibold leading-6 text-[var(--af-text-primary)]">{card.title}</p>
                            <div className="mt-2 grid gap-2 break-words text-xs text-[var(--af-text-tertiary)]">
                              {card.target_persona ? (
                                <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                                  <span className="font-medium text-[var(--af-text-secondary)]">{t("research.actionTarget", "优先对象")}：</span>
                                  {card.target_persona}
                                </div>
                              ) : null}
                              {card.execution_window ? (
                                <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                                  <span className="font-medium text-[var(--af-text-secondary)]">{t("research.actionWindow", "执行窗口")}：</span>
                                  {card.execution_window}
                                </div>
                              ) : null}
                              {card.deliverable ? (
                                <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                                  <span className="font-medium text-[var(--af-text-secondary)]">{t("research.actionDeliverable", "产出物")}：</span>
                                  {card.deliverable}
                                </div>
                              ) : null}
                            </div>
                            {parseActionPhases(card.recommended_steps).length ? (
                              <div className="mt-3 grid gap-2">
                                {parseActionPhases(card.recommended_steps).map((phase) => (
                                  <div key={`${card.title}-${phase.label}-${phase.content}`} className="min-w-0 overflow-hidden rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
                                    <div className="flex flex-wrap items-center gap-2">
                                      <span className="rounded-full af-chip af-chip-info px-2 py-0.5 text-[10px] font-semibold ">
                                        {phase.label}
                                      </span>
                                      {phase.horizon ? (
                                        <span className="text-[11px] font-medium text-[var(--af-text-tertiary)]">{phase.horizon}</span>
                                      ) : null}
                                    </div>
                                    <p className="mt-2 min-w-0 break-words whitespace-pre-wrap text-xs leading-5 text-[var(--af-text-secondary)] [overflow-wrap:anywhere]">
                                      {phase.content}
                                    </p>
                                  </div>
                                ))}
                              </div>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    ) : null}

                    <div className="mt-4 flex flex-wrap gap-2">
                      {keyword ? (
                        <span className="rounded-full af-chip px-2.5 py-1 text-[11px] ">
                          {keyword}
                        </span>
                      ) : null}
                      {actionType ? (
                        <span className="rounded-full af-chip px-2.5 py-1 text-[11px] ">
                          {entry.action_type_label || actionType}
                        </span>
                      ) : null}
                      {entry.region_label ? (
                        <span className="rounded-full af-chip px-2.5 py-1 text-[11px] ">
                          {entry.region_label}
                        </span>
                      ) : null}
                      {entry.industry_label ? (
                        <span className="rounded-full af-chip px-2.5 py-1 text-[11px] ">
                          {entry.industry_label}
                        </span>
                      ) : null}
                      {isReport ? (
                        <>
                          <span className={`rounded-full px-2.5 py-1 text-[11px] ${qualityTone(reportMeta.evidenceDensity)}`}>
                            {t("research.centerEvidenceDensity", "证据密度")}·{qualityLabel(reportMeta.evidenceDensity)}
                          </span>
                          <span className={`rounded-full px-2.5 py-1 text-[11px] ${qualityTone(reportMeta.sourceQuality)}`}>
                            {t("research.centerSourceQuality", "来源质量")}·{qualityLabel(reportMeta.sourceQuality)}
                          </span>
                        </>
                      ) : null}
                    </div>

                    <div className="mt-5 grid gap-3 sm:grid-cols-3">
                      <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">
                          {t("research.centerCardCollection", "分组")}
                        </p>
                        <p className="mt-2 text-sm font-medium text-[var(--af-text-secondary)]">
                          {entry.collection_name || t("common.none", "暂无")}
                        </p>
                      </div>
                      <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">
                          {t("research.centerCardSources", "来源数")}
                        </p>
                        <p className="mt-2 text-sm font-medium text-[var(--af-text-secondary)]">{sourceCount || "—"}</p>
                      </div>
                      <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">
                          {t("research.centerCardUpdated", "更新")}
                        </p>
                        <p className="mt-2 text-sm font-medium text-[var(--af-text-secondary)]">
                          {new Date(entry.updated_at || entry.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>

                    {isReport && rankedPreview.length ? (
                      <div className="mt-4 grid gap-3">
                        {rankedPreview.map((group) => (
                          <div key={`${entry.id}-${group.key}`} className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                            <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">{group.title}</p>
                            <div className="mt-2 flex flex-wrap gap-2">
                              {group.items.map((itemValue) => (
                                <span key={`${group.key}-${itemValue.name}`} className="rounded-full af-chip af-chip-info px-2.5 py-1 text-[11px] ">
                                  {itemValue.name} · {itemValue.score_label}
                                </span>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : null}

                    {isReport && diagnosticsMeta && (diagnosticsMeta.scopeRegions.length || diagnosticsMeta.scopeIndustries.length || diagnosticsMeta.scopeClients.length || diagnosticsMeta.topicAnchors.length || diagnosticsMeta.matchedThemes.length || diagnosticsMeta.guardedBacklog || diagnosticsMeta.guardedReasonLabels.length || diagnosticsMeta.supportedTargetAccounts.length || diagnosticsMeta.unsupportedTargetAccounts.length || diagnosticsMeta.filteredOldSourceCount || diagnosticsMeta.filteredRegionConflictCount || diagnosticsMeta.normalizedEntityCount || diagnosticsMeta.uniqueDomainCount || diagnosticsMeta.candidateProfileCompanies.length || diagnosticsMeta.candidateProfileHitCount) ? (
                      <div className="mt-4 rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">
                          {t("research.sourceDiagnosticsTitle", "来源检查")}
                        </p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          <span
                            className={`rounded-full px-2.5 py-1 text-[11px] ${
                              diagnosticsMeta.evidenceMode === "strong"
                                ? "af-chip af-chip-success"
                                : diagnosticsMeta.evidenceMode === "provisional"
                                  ? "af-chip af-chip-warning"
                                  : "af-chip"
                            }`}
                          >
                            {diagnosticsMeta.evidenceMode === "strong"
                              ? "强证据"
                              : diagnosticsMeta.evidenceMode === "provisional"
                                ? "可用初版"
                                : "待核实"}
                          </span>
                          {diagnosticsMeta.guardedBacklog ? (
                            <span className="rounded-full af-chip af-chip-danger px-2.5 py-1 text-[11px] ">
                              待复核
                            </span>
                          ) : null}
                          <span className="rounded-full af-chip px-2.5 py-1 text-[11px] ">
                            来源质量 {diagnosticsMeta.retrievalQuality === "high" ? "高" : diagnosticsMeta.retrievalQuality === "medium" ? "中" : "低"}
                          </span>
                          <span className="rounded-full af-chip px-2.5 py-1 text-[11px] ">
                            严格命中 {Math.round(diagnosticsMeta.strictMatchRatio * 100)}%
                          </span>
                          <span className="rounded-full af-chip px-2.5 py-1 text-[11px] ">
                            官方源 {Math.round(diagnosticsMeta.officialSourceRatio * 100)}%
                          </span>
                          {diagnosticsMeta.uniqueDomainCount > 0 ? (
                            <span className="rounded-full af-chip px-2.5 py-1 text-[11px] ">
                              域名 {diagnosticsMeta.uniqueDomainCount}
                            </span>
                          ) : null}
                          {diagnosticsMeta.scopeRegions.map((value) => (
                            <span key={`${entry.id}-scope-region-${value}`} className="rounded-full af-chip af-chip-info px-2.5 py-1 text-[11px] ">
                              区域 · {value}
                            </span>
                          ))}
                          {diagnosticsMeta.scopeIndustries.map((value) => (
                            <span key={`${entry.id}-scope-industry-${value}`} className="rounded-full af-chip af-chip-info px-2.5 py-1 text-[11px] ">
                              领域 · {value}
                            </span>
                          ))}
                          {diagnosticsMeta.scopeClients.map((value) => (
                            <span key={`${entry.id}-scope-client-${value}`} className="rounded-full af-chip af-chip-info px-2.5 py-1 text-[11px] ">
                              公司 · {value}
                            </span>
                          ))}
                          {diagnosticsMeta.topicAnchors.map((value) => (
                            <span key={`${entry.id}-anchor-${value}`} className="rounded-full af-chip af-chip-info px-2.5 py-1 text-[11px] ">
                              {value}
                            </span>
                          ))}
                          {diagnosticsMeta.matchedThemes.map((value) => (
                            <span key={`${entry.id}-theme-${value}`} className="rounded-full af-chip af-chip-success px-2.5 py-1 text-[11px] ">
                              {value}
                            </span>
                          ))}
                          {diagnosticsMeta.filteredOldSourceCount > 0 ? (
                            <span className="rounded-full af-chip px-2.5 py-1 text-[11px] ">
                              {t("research.sourceDiagnosticsFilteredOld", "剔除过旧来源")} {diagnosticsMeta.filteredOldSourceCount}
                            </span>
                          ) : null}
                          {diagnosticsMeta.filteredRegionConflictCount > 0 ? (
                            <span className="rounded-full af-chip af-chip-danger px-2.5 py-1 text-[11px] ">
                              拦截越界区域 {diagnosticsMeta.filteredRegionConflictCount}
                            </span>
                          ) : null}
                          {diagnosticsMeta.strictTopicSourceCount > 0 ? (
                            <span className="rounded-full af-chip px-2.5 py-1 text-[11px] ">
                              {t("research.sourceDiagnosticsStrictTopic", "严格主题保留")} {diagnosticsMeta.strictTopicSourceCount}
                            </span>
                          ) : null}
                          {diagnosticsMeta.normalizedEntityCount > 0 ? (
                            <span className="rounded-full af-chip af-chip-info px-2.5 py-1 text-[11px] ">
                              实体 {diagnosticsMeta.normalizedEntityCount}
                            </span>
                          ) : null}
                          {diagnosticsMeta.expansionTriggered ? (
                            <span className="rounded-full af-chip af-chip-warning px-2.5 py-1 text-[11px] ">
                              已扩搜
                            </span>
                          ) : null}
                          {diagnosticsMeta.correctiveTriggered ? (
                            <span className="rounded-full af-chip af-chip-warning px-2.5 py-1 text-[11px] ">
                              已补充核验
                            </span>
                          ) : null}
                          {diagnosticsMeta.candidateProfileCompanies.length ? (
                            <span className="rounded-full af-chip af-chip-info px-2.5 py-1 text-[11px] ">
                              建议核验公司 {diagnosticsMeta.candidateProfileCompanies.length}
                            </span>
                          ) : null}
                          {diagnosticsMeta.candidateProfileHitCount > 0 ? (
                            <span className="rounded-full af-chip af-chip-info px-2.5 py-1 text-[11px] ">
                              公开来源 {diagnosticsMeta.candidateProfileHitCount}
                            </span>
                          ) : null}
                          {diagnosticsMeta.candidateProfileOfficialHitCount > 0 ? (
                            <span className="rounded-full af-chip af-chip-info px-2.5 py-1 text-[11px] ">
                              其中官方源 {diagnosticsMeta.candidateProfileOfficialHitCount}
                            </span>
                          ) : null}
                        </div>
                        {diagnosticsMeta.guardedReasonLabels.length ? (
                          <div className="mt-2 flex flex-wrap gap-2">
                            {diagnosticsMeta.guardedReasonLabels.map((value) => (
                              <span key={`${entry.id}-guarded-reason-${value}`} className="rounded-full af-chip af-chip-danger px-2.5 py-1 text-[11px] ">
                                {value}
                              </span>
                            ))}
                          </div>
                        ) : null}
                        {diagnosticsMeta.supportedTargetAccounts.length || diagnosticsMeta.unsupportedTargetAccounts.length ? (
                          <div className="mt-2 flex flex-wrap gap-2">
                            {diagnosticsMeta.supportedTargetAccounts.map((value) => (
                              <span key={`${entry.id}-supported-target-${value}`} className="rounded-full af-chip af-chip-success px-2.5 py-1 text-[11px] ">
                                已支撑 · {value}
                              </span>
                            ))}
                            {diagnosticsMeta.unsupportedTargetAccounts.map((value) => (
                              <span key={`${entry.id}-unsupported-target-${value}`} className="rounded-full af-chip af-chip-danger px-2.5 py-1 text-[11px] ">
                                未支撑 · {value}
                              </span>
                            ))}
                          </div>
                        ) : null}
                        {diagnosticsMeta.normalizedEntityCount > 0 ? (
                          <div className="mt-2 flex flex-wrap gap-2">
                            <span className="rounded-full af-chip af-chip-info px-2.5 py-1 text-[11px] ">
                              甲方 {diagnosticsMeta.normalizedTargetCount}
                            </span>
                            <span className="rounded-full af-chip af-chip-info px-2.5 py-1 text-[11px] ">
                              竞品 {diagnosticsMeta.normalizedCompetitorCount}
                            </span>
                            <span className="rounded-full af-chip af-chip-info px-2.5 py-1 text-[11px] ">
                              伙伴 {diagnosticsMeta.normalizedPartnerCount}
                            </span>
                          </div>
                        ) : null}
                        {diagnosticsMeta.candidateProfileCompanies.length ? (
                          <div className="mt-2 flex flex-wrap gap-2">
                            {diagnosticsMeta.candidateProfileCompanies.map((value) => (
                              <span
                                key={`${entry.id}-candidate-profile-${value}`}
                                className="rounded-full af-chip af-chip-info px-2.5 py-1 text-[11px] "
                              >
                                候选公司 · {value}
                              </span>
                            ))}
                          </div>
                        ) : null}
                        {diagnosticsMeta.candidateProfileSourceLabels.length ? (
                          <div className="mt-2 flex flex-wrap gap-2">
                            {diagnosticsMeta.candidateProfileSourceLabels.map((value) => (
                              <span
                                key={`${entry.id}-candidate-profile-source-${value}`}
                                className="rounded-full af-chip af-chip-info px-2.5 py-1 text-[11px] "
                              >
                                {value}
                              </span>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    ) : null}

                    <div className="mt-4 flex flex-wrap gap-2">
                      <Link href={`/knowledge/${entry.id}`} className="af-btn af-btn-secondary border px-3 py-1.5 text-sm">
                        <AppIcon name="knowledge" className="h-4 w-4" />
                        {t("research.centerOpenCard", "查看卡片")}
                      </Link>
                      {!isReport ? (
                        <Link
                          href={`/knowledge/${entry.id}/edit`}
                          className="af-btn af-btn-primary px-3 py-1.5 text-sm"
                        >
                          <AppIcon name="edit" className="h-4 w-4" />
                          {t("research.centerEditAction", "编辑行动卡")}
                        </Link>
                      ) : null}
                    </div>
                  </article>
                );
              })}
            </section>
          ) : null}
        </div>
  );
}
