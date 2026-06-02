"use client";

import type { ApiResearchReport } from "@/lib/api/types";
import {
  confidenceToneMeta,
  factorBucket,
  qualityLabel,
  qualityTone,
  rankedPanelTone,
  sourceTierLabel,
  valueBucket,
  type KnowledgeRankedPanel,
  type KnowledgeReportSurfaceCopy,
  type KnowledgeTranslateFn,
  type RankedPanelTone,
} from "@/components/knowledge/knowledge-detail-card-model";
import { ExternalLinkActions, normalizeExternalUrl } from "@/components/ui/external-link-actions";

interface KnowledgeResearchReportInsightsSectionProps {
  report: ApiResearchReport;
  rankedPanels: KnowledgeRankedPanel[];
  copy: KnowledgeReportSurfaceCopy;
  t: KnowledgeTranslateFn;
}

export function KnowledgeResearchReportInsightsSection({
  report,
  rankedPanels,
  copy,
  t,
}: KnowledgeResearchReportInsightsSectionProps) {
  return (
    <>
      {(report.five_year_outlook.length || report.competition_analysis.length) ? (
        <div className="grid gap-4">
          {report.five_year_outlook.length ? (
            <article className="rounded-2xl border border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">
                {t("research.fiveYearOutlook", "未来五年演化判断")}
              </p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                {report.five_year_outlook.map((itemValue) => (
                  <li key={itemValue} className="flex gap-2">
                    <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))]" />
                    <span>{itemValue}</span>
                  </li>
                ))}
              </ul>
            </article>
          ) : null}
          {report.competition_analysis.length ? (
            <article className="rounded-2xl border border-[color-mix(in_srgb,var(--af-warning)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">
                {t("research.competition", "竞争分析")}
              </p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                {report.competition_analysis.map((itemValue) => (
                  <li key={itemValue} className="flex gap-2">
                    <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[color-mix(in_srgb,var(--af-warning)_14%,var(--af-surface-muted))]" />
                    <span>{itemValue}</span>
                  </li>
                ))}
              </ul>
            </article>
          ) : null}
        </div>
      ) : null}

      {(report.target_departments?.length || report.public_contact_channels?.length || report.account_team_signals?.length) ? (
        <div className="grid gap-4">
          {report.target_departments?.length ? (
            <article className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">
                {t("research.targetDepartments", "高概率决策部门")}
              </p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                {report.target_departments.map((itemValue) => (
                  <li key={itemValue} className="flex gap-2">
                    <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[var(--af-surface-inset)]" />
                    <span>{itemValue}</span>
                  </li>
                ))}
              </ul>
            </article>
          ) : null}
          {report.public_contact_channels?.length ? (
            <article className="rounded-2xl border border-[color-mix(in_srgb,var(--af-success)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">
                {t("research.publicContacts", "公开业务联系方式")}
              </p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                {report.public_contact_channels.map((itemValue) => (
                  <li key={itemValue} className="flex gap-2">
                    <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[var(--af-surface-inset)]" />
                    <span>{itemValue}</span>
                  </li>
                ))}
              </ul>
            </article>
          ) : null}
          {report.account_team_signals?.length ? (
            <article className="rounded-2xl border border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">
                {t("research.accountTeams", "目标区域活跃团队")}
              </p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                {report.account_team_signals.map((itemValue) => (
                  <li key={itemValue} className="flex gap-2">
                    <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))]" />
                    <span>{itemValue}</span>
                  </li>
                ))}
              </ul>
            </article>
          ) : null}
        </div>
      ) : null}

      {(report.client_peer_moves.length || report.winner_peer_moves.length) ? (
        <div className="grid gap-4">
          {report.client_peer_moves.length ? (
            <article className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">
                {t("research.clientPeers", "甲方同行 Top 3 动态")}
              </p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                {report.client_peer_moves.map((itemValue) => (
                  <li key={itemValue} className="flex gap-2">
                    <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[var(--af-surface-inset)]" />
                    <span>{itemValue}</span>
                  </li>
                ))}
              </ul>
            </article>
          ) : null}
          {report.winner_peer_moves.length ? (
            <article className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">
                {t("research.winnerPeers", "中标方同行 Top 3 动态")}
              </p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                {report.winner_peer_moves.map((itemValue) => (
                  <li key={itemValue} className="flex gap-2">
                    <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[var(--af-surface-inset)]" />
                    <span>{itemValue}</span>
                  </li>
                ))}
              </ul>
            </article>
          ) : null}
        </div>
      ) : null}

      {rankedPanels.length ? (
        <div className="grid gap-4">
          {rankedPanels.map((panel) => (
            <article
              key={panel.title}
              className={`rounded-[24px] border p-4 shadow-[var(--af-shadow-card)] ${rankedPanelTone(panel.tone as RankedPanelTone).panelClass}`}
            >
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">{panel.title}</p>
              <div className="mt-3 space-y-3">
                {panel.items.map((entity) => (
                  <div
                    key={`${panel.title}-${entity.name}`}
                    className={`rounded-[20px] border p-3 shadow-[var(--af-shadow-card)] ${rankedPanelTone(panel.tone as RankedPanelTone).entityClass}`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <h4 className={`text-sm font-semibold ${rankedPanelTone(panel.tone as RankedPanelTone).titleClass}`}>
                        {entity.name}
                      </h4>
                      <span className={`rounded-full px-2 py-0.5 text-[11px] ${valueBucket(entity.score, t).className}`}>
                        {valueBucket(entity.score, t).label}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{entity.reasoning}</p>
                    {entity.score_breakdown?.length ? (
                      <div className="mt-3 grid gap-2">
                        {entity.score_breakdown.slice(0, 3).map((factor) => (
                          <div
                            key={`${entity.name}-${factor.label}`}
                            className={`rounded-[18px] border px-3 py-2 ${rankedPanelTone(panel.tone as RankedPanelTone).subtleClass}`}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-xs font-medium text-[var(--af-text-secondary)]">{factor.label}</span>
                              <span className={`rounded-full px-2 py-0.5 text-[10px] ${factorBucket(factor.score).className}`}>
                                {factorBucket(factor.score).label}
                              </span>
                            </div>
                            {factor.note ? <p className="mt-1 text-[11px] leading-5 text-[var(--af-text-tertiary)]">{factor.note}</p> : null}
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {entity.evidence_links?.length ? (
                      <div className="mt-3 space-y-2">
                        {entity.evidence_links.map((link) => (
                          <div
                            key={`${entity.name}-${link.url}`}
                            className={`block rounded-[18px] border px-3 py-2 transition ${rankedPanelTone(panel.tone as RankedPanelTone).linkClass}`}
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              <span className={`h-1.5 w-1.5 rounded-full ${rankedPanelTone(panel.tone as RankedPanelTone).dotClass}`} />
                              <a
                                href={normalizeExternalUrl(link.url)}
                                target="_blank"
                                rel="noreferrer"
                                className="text-xs font-medium text-[var(--af-text-primary)] underline-offset-4 hover:text-[var(--af-info)] hover:underline"
                              >
                                {link.title}
                              </a>
                              <span className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2 py-0.5 text-[10px] text-[var(--af-info)]">
                                {sourceTierLabel(link.source_tier || "media", t)}
                              </span>
                              {link.source_label ? (
                                <span className="rounded-full bg-[var(--af-surface-muted)] px-2 py-0.5 text-[10px] text-[var(--af-text-tertiary)]">
                                  {link.source_label}
                                </span>
                              ) : null}
                            </div>
                            <ExternalLinkActions
                              url={link.url}
                              className="mt-2"
                              openLabel="网页打开"
                            />
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      ) : null}

      {report.sections.length ? (
        <div>
          <div className="mb-3">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">{copy.insightsTitle}</p>
            <p className="mt-1 text-sm text-[var(--af-text-tertiary)]">{copy.insightsDesc}</p>
          </div>
          <div className="grid gap-4">
            {report.sections.map((section) => {
              const tone = confidenceToneMeta(section.confidence_tone);
              return (
                <article key={section.title} className={`rounded-2xl border p-4 ${tone.panel}`}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">
                      {section.title}
                    </p>
                    <div className="flex flex-wrap gap-2 text-[11px]">
                      {section.confidence_label ? (
                        <span className={`rounded-full px-2 py-0.5 ${tone.badge}`}>
                          {section.confidence_label}
                        </span>
                      ) : null}
                      <span className={`rounded-full px-2 py-0.5 ${qualityTone(section.evidence_density || "low")}`}>
                        {t("research.centerEvidenceDensity", "证据密度")}·{qualityLabel(section.evidence_density || "low")}
                      </span>
                      <span className={`rounded-full px-2 py-0.5 ${qualityTone(section.source_quality || "low")}`}>
                        {t("research.centerSourceQuality", "来源质量")}·{qualityLabel(section.source_quality || "low")}
                      </span>
                      {typeof section.evidence_quota === "number" && section.evidence_quota > 0 ? (
                        <span
                          className={`rounded-full px-2 py-0.5 ${
                            section.meets_evidence_quota ? "af-chip af-chip-success" : "af-chip af-chip-warning"
                          }`}
                        >
                          配额 {section.evidence_count || 0}/{section.evidence_quota}
                        </span>
                      ) : null}
                    </div>
                  </div>
                  <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                    {section.items.map((itemValue) => (
                      <li key={`${section.title}-${itemValue}`} className={`flex gap-2 rounded-xl px-2 py-1.5 ${tone.item}`}>
                        <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[var(--af-surface-inset)]" />
                        <span>{itemValue}</span>
                      </li>
                    ))}
                  </ul>
                  {section.confidence_reason ? (
                    <p className="mt-3 text-xs leading-5 text-[var(--af-text-secondary)]">{section.confidence_reason}</p>
                  ) : null}
                  {section.evidence_note ? (
                    <p className="mt-3 text-xs leading-5 text-[var(--af-text-tertiary)]">{section.evidence_note}</p>
                  ) : null}
                  {section.quota_note ? (
                    <p className={`mt-2 text-xs leading-5 ${section.meets_evidence_quota ? "text-[var(--af-success)]" : "text-[var(--af-warning)]"}`}>
                      {section.quota_note}
                    </p>
                  ) : null}
                  {section.contradiction_note ? (
                    <p className="mt-2 text-xs leading-5 text-[var(--af-danger)]">{section.contradiction_note}</p>
                  ) : null}
                  {section.next_verification_steps?.length ? (
                    <div className="mt-3 rounded-2xl border border-[color-mix(in_srgb,var(--af-warning)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-warning)_14%,var(--af-surface-muted))] p-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-warning)]">
                        下一步补证
                      </p>
                      <ul className="mt-2 space-y-1.5 text-xs leading-5 text-[var(--af-warning)]">
                        {section.next_verification_steps.slice(0, 3).map((step) => (
                          <li key={`${section.title}-${step}`} className="flex gap-2">
                            <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[color-mix(in_srgb,var(--af-warning)_14%,var(--af-surface-muted))]" />
                            <span>{step}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {section.evidence_links?.length ? (
                    <div className="mt-3 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">证据锚点</p>
                      <div className="mt-2 space-y-2">
                        {section.evidence_links.slice(0, 3).map((link) => (
                          <div
                            key={`${section.title}-${link.url}`}
                            className={`block rounded-xl border border-[var(--af-border-subtle)] px-3 py-2 transition hover:border-[var(--af-border-strong)] hover:bg-[var(--af-surface-hover)] ${tone.excerpt}`}
                          >
                            <div className="flex flex-wrap items-center gap-2 text-xs">
                              <a
                                href={normalizeExternalUrl(link.url)}
                                target="_blank"
                                rel="noreferrer"
                                className="font-medium text-[var(--af-text-primary)] underline-offset-4 hover:text-[var(--af-info)] hover:underline"
                              >
                                {link.anchor_text || link.title}
                              </a>
                              <span className="rounded-full bg-[var(--af-surface-elevated)] px-2 py-0.5 text-[10px] text-[var(--af-text-secondary)]">
                                {link.source_tier === "official"
                                  ? t("research.sourceOfficial", "官方源")
                                  : link.source_tier === "aggregate"
                                    ? t("research.sourceAggregate", "聚合源")
                                    : t("research.sourceMedia", "媒体源")}
                              </span>
                              {link.source_label ? (
                                <span className="rounded-full bg-[var(--af-surface-elevated)] px-2 py-0.5 text-[10px] text-[var(--af-text-secondary)]">{link.source_label}</span>
                              ) : null}
                            </div>
                            {link.excerpt ? (
                              <p className="mt-2 rounded-lg bg-[var(--af-surface-elevated)] px-2 py-1.5 text-[11px] leading-5 text-[var(--af-text-secondary)]">{link.excerpt}</p>
                            ) : null}
                            <ExternalLinkActions
                              url={link.url}
                              className="mt-2"
                              openLabel="网页打开"
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        </div>
      ) : null}
    </>
  );
}
