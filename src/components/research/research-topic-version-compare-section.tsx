"use client";

import Link from "next/link";
import { ExternalLinkActions, normalizeExternalUrl } from "@/components/ui/external-link-actions";
import type { useResearchTopicWorkspaceController } from "@/components/research/use-research-topic-workspace-controller";
import {
  contributionBucket,
  factorBucket,
  followupImpactTone,
  qualityLabel,
  qualityTone,
  valueBucket,
} from "@/components/research/research-topic-workspace-utils";

type ResearchTopicWorkspaceController = ReturnType<typeof useResearchTopicWorkspaceController>;

type ResearchTopicVersionCompareSectionProps = {
  controller: ResearchTopicWorkspaceController;
  t: (key: string, fallback: string) => string;
};

export function ResearchTopicVersionCompareSection({
  controller,
  t,
}: ResearchTopicVersionCompareSectionProps) {
  const {
    versions,
    compareLeftId,
    setCompareLeftId,
    compareRightId,
    setCompareRightId,
    compareLeftVersion,
    compareRightVersion,
    compareLeftReport,
    compareRightReport,
    compareFocusBlocks,
    compareLeftFollowupImpactPanel,
    compareRightFollowupImpactPanel,
    compareLeftCandidateProfileSummary,
    compareRightCandidateProfileSummary,
    diffHighlights,
    fieldDiffRows,
    scorePanels,
    sourceContributionPanels,
  } = controller;

  return (
    <>
      {versions.length > 1 ? (
        <section className="af-glass rounded-[30px] p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="af-kicker">{t("research.versionSideBySide", "历史版本并排对照")}</p>
              <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">
                {t("research.versionSideBySideDesc", "选择两个历史版本，对照执行摘要、质量等级与关键线索变化。")}
              </p>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="flex min-w-[210px] flex-col gap-1 text-xs text-[var(--af-text-tertiary)]">
                <span>{t("research.versionBaseline", "基线版本")}</span>
                <select
                  value={compareLeftId}
                  onChange={(event) => setCompareLeftId(event.target.value)}
                  className="af-input bg-[var(--af-surface-elevated)] text-sm text-[var(--af-text-secondary)]"
                >
                  {versions.map((version) => (
                    <option key={`left-${version.id}`} value={version.id}>
                      {new Date(version.refreshed_at).toLocaleString()} · {version.title}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex min-w-[210px] flex-col gap-1 text-xs text-[var(--af-text-tertiary)]">
                <span>{t("research.versionCurrent", "对照版本")}</span>
                <select
                  value={compareRightId}
                  onChange={(event) => setCompareRightId(event.target.value)}
                  className="af-input bg-[var(--af-surface-elevated)] text-sm text-[var(--af-text-secondary)]"
                >
                  {versions.map((version) => (
                    <option key={`right-${version.id}`} value={version.id}>
                      {new Date(version.refreshed_at).toLocaleString()} · {version.title}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>
          <div className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-2">
            {[
              {
                key: "baseline",
                label: t("research.versionBaseline", "基线版本"),
                version: compareLeftVersion,
                report: compareLeftReport,
                blocks: compareFocusBlocks.left,
                followup: compareLeftFollowupImpactPanel,
              },
              {
                key: "current",
                label: t("research.versionCurrent", "对照版本"),
                version: compareRightVersion,
                report: compareRightReport,
                blocks: compareFocusBlocks.right,
                followup: compareRightFollowupImpactPanel,
              },
            ].map((panel) => (
              <article key={panel.key} className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">{panel.label}</p>
                    <h3 className="mt-2 text-lg font-semibold text-[var(--af-text-primary)]">{panel.version?.title || "—"}</h3>
                    <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">
                      {panel.version ? new Date(panel.version.refreshed_at).toLocaleString() : "—"}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2 text-xs">
                    {panel.version ? (
                      <>
                        <span className={`rounded-full px-2.5 py-1 ${qualityTone(panel.version.evidence_density)}`}>
                          {t("research.centerEvidenceDensity", "证据密度")}·{qualityLabel(panel.version.evidence_density)}
                        </span>
                        <span className={`rounded-full px-2.5 py-1 ${qualityTone(panel.version.source_quality)}`}>
                          {t("research.centerSourceQuality", "来源质量")}·{qualityLabel(panel.version.source_quality)}
                        </span>
                      </>
                    ) : null}
                  </div>
                </div>
                <p className="mt-4 text-sm leading-7 text-[var(--af-text-secondary)]">
                  {String(panel.report?.executive_summary || "").slice(0, 220) || "—"}
                </p>
                {(panel.followup.impactedSections.length || panel.followup.titleResolution !== "无" || panel.followup.summaryResolution !== "无") ? (
                  <div className="mt-4 rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="rounded-full af-chip af-chip-info px-2.5 py-1 ">
                        标题 · {panel.followup.titleResolution}
                      </span>
                      <span className="rounded-full af-chip px-2.5 py-1 ">
                        摘要 · {panel.followup.summaryResolution}
                      </span>
                    </div>
                    <div className="mt-3 grid grid-cols-1 gap-2">
                      {panel.followup.impactedSections.length ? (
                        panel.followup.impactedSections.map((impact) => (
                          <div key={`${panel.key}-${impact.sectionTitle}`} className="rounded-[14px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-3">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-sm font-medium text-[var(--af-text-secondary)]">{impact.sectionTitle}</p>
                              <span className={`rounded-full px-2 py-0.5 text-[11px] ${followupImpactTone(impact.impactLabel)}`}>
                                {impact.impactLabel}
                              </span>
                            </div>
                            {impact.reason ? <p className="mt-2 text-xs leading-5 text-[var(--af-text-tertiary)]">变化原因 · {impact.reason}</p> : null}
                            {impact.nextAction ? <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">下一步 · {impact.nextAction}</p> : null}
                          </div>
                        ))
                      ) : (
                        <p className="rounded-[14px] border border-dashed border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-3 text-xs text-[var(--af-text-tertiary)]">
                          当前版本没有显式追问影响章节。
                        </p>
                      )}
                    </div>
                  </div>
                ) : null}
                {(() => {
                  const candidateSummary =
                    panel.key === "baseline" ? compareLeftCandidateProfileSummary : compareRightCandidateProfileSummary;
                  if (!candidateSummary.companies.length && candidateSummary.hitCount <= 0) return null;
                  return (
                    <div className="mt-4 flex flex-wrap gap-2 text-xs">
                      {candidateSummary.companies.length ? (
                        <span className="rounded-full af-chip af-chip-info px-2.5 py-1 ">
                          建议核验公司 {candidateSummary.companies.length}
                        </span>
                      ) : null}
                      {candidateSummary.hitCount > 0 ? (
                        <span className="rounded-full af-chip af-chip-info px-2.5 py-1 ">
                          公开来源 {candidateSummary.hitCount}
                        </span>
                      ) : null}
                      {candidateSummary.officialHitCount > 0 ? (
                        <span className="rounded-full af-chip af-chip-info px-2.5 py-1 ">
                          其中官方源 {candidateSummary.officialHitCount}
                        </span>
                      ) : null}
                      {candidateSummary.companies.map((value) => (
                        <span key={`${panel.key}-candidate-${value}`} className="rounded-full af-chip af-chip-info px-2.5 py-1 ">
                          候选公司 · {value}
                        </span>
                      ))}
                      {candidateSummary.sourceLabels.map((value) => (
                        <span key={`${panel.key}-candidate-source-${value}`} className="rounded-full af-chip af-chip-info px-2.5 py-1 ">
                          {value}
                        </span>
                      ))}
                    </div>
                  );
                })()}
                {panel.blocks.length ? (
                  <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
                    {panel.blocks.map((block) => (
                      <div key={`${panel.key}-${block.key}`} className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">{block.title}</p>
                        <ul className="mt-2 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                          {block.items.map((item) => (
                            <li key={item} className="flex gap-2">
                              <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[var(--af-info)]" />
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                ) : null}
                {panel.version?.entry_id ? (
                  <Link href={`/knowledge/${panel.version.entry_id}`} className="mt-4 inline-flex text-sm font-medium text-[var(--af-text-secondary)] underline-offset-4 hover:underline">
                    {t("research.openSelectedVersion", "打开该版本研报")}
                  </Link>
                ) : null}
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {diffHighlights.length ? (
        <section className="af-glass rounded-[30px] p-6">
          <p className="af-kicker">{t("research.versionDiffHighlights", "版本差异高亮")}</p>
          <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
            {diffHighlights.map((group) => (
              <article key={group.title} className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                <p className="text-sm font-semibold text-[var(--af-text-primary)]">{group.title}</p>
                <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                  {group.items.map((item) => (
                    <li key={item} className="flex gap-2">
                      <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[var(--af-info)]" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {fieldDiffRows.length ? (
        <section className="af-glass rounded-[30px] p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="af-kicker">{t("research.versionFieldDiff", "关键变化")}</p>
              <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">
                {t("research.versionFieldDiffDesc", "对照两个版本的新增、减少和保留线索。")}
              </p>
            </div>
          </div>
          <div className="mt-5 grid grid-cols-1 gap-3">
            {fieldDiffRows.map((row) => (
              <article key={row.key} className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h3 className="text-base font-semibold text-[var(--af-text-primary)]">{row.title}</h3>
                  <div className="flex flex-wrap gap-2 text-xs">
                    {row.added.length ? (
                      <span className="rounded-full af-chip af-chip-success px-2.5 py-1 ">
                        {t("research.versionFieldAdded", "新增")} {row.added.length}
                      </span>
                    ) : null}
                    {row.removed.length ? (
                      <span className="rounded-full af-chip af-chip-danger px-2.5 py-1 ">
                        {t("research.versionFieldRemoved", "减少")} {row.removed.length}
                      </span>
                    ) : null}
                    {row.rewritten.length ? (
                      <span className="rounded-full af-chip af-chip-info px-2.5 py-1 ">
                        {t("research.versionFieldRewritten", "改写")} {row.rewritten.length}
                      </span>
                    ) : null}
                    {!row.added.length && !row.removed.length ? (
                      <span className="rounded-full af-chip px-2.5 py-1 ">
                        {t("research.versionFieldStable", "结构稳定")}
                      </span>
                    ) : null}
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[1fr_1fr_0.9fr]">
                  <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">{t("research.versionBaseline", "基线版本")}</p>
                    <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                      {(row.baseline.length ? row.baseline.slice(0, 4) : [t("research.versionFieldEmpty", "暂无明确线索")]).map((item) => (
                        <li key={`base-${row.key}-${item}`} className="flex gap-2">
                          <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[var(--af-text-tertiary)]" />
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">{t("research.versionCurrent", "对照版本")}</p>
                    <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                      {(row.current.length ? row.current.slice(0, 4) : [t("research.versionFieldEmpty", "暂无明确线索")]).map((item) => (
                        <li key={`current-${row.key}-${item}`} className="flex gap-2">
                          <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[var(--af-info)]" />
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">{t("research.versionFieldDelta", "字段变化")}</p>
                    <div className="mt-3 space-y-3 text-sm leading-6 text-[var(--af-text-secondary)]">
                      <div>
                        <p className="font-medium text-[var(--af-success)]">{t("research.versionFieldAdded", "新增")}</p>
                        <p>{row.added.length ? row.added.join("；") : t("research.versionFieldNone", "无")}</p>
                      </div>
                      <div>
                        <p className="font-medium text-[var(--af-danger)]">{t("research.versionFieldRemoved", "减少")}</p>
                        <p>{row.removed.length ? row.removed.join("；") : t("research.versionFieldNone", "无")}</p>
                      </div>
                      <div>
                        <p className="font-medium text-[var(--af-info)]">{t("research.versionFieldRewritten", "改写")}</p>
                        <p>{row.rewritten.length ? row.rewritten.join("；") : t("research.versionFieldNone", "无")}</p>
                      </div>
                    </div>
                  </div>
                </div>
                {(row.baselineEvidenceLinks.length || row.currentEvidenceLinks.length) ? (
                  <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
                    <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                      <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">
                        {t("research.versionBaselineEvidence", "基线版本证据")}
                      </p>
                      <div className="mt-3 grid grid-cols-1 gap-2">
                        {(row.baselineEvidenceLinks.length ? row.baselineEvidenceLinks : []).map((link) => (
                          <a
                            key={`base-${row.key}-${link.url}`}
                            href={link.url}
                            target="_blank"
                            rel="noreferrer"
                            className="rounded-[14px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-sm text-[var(--af-text-secondary)] transition hover:border-[var(--af-border-subtle)] hover:bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))]"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <span className="font-medium text-[var(--af-text-secondary)]">{link.title}</span>
                              <span className="rounded-full af-chip px-2 py-0.5 text-[11px] ">{link.tierLabel}</span>
                            </div>
                            {link.meta ? <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">{link.meta}</p> : null}
                          </a>
                        ))}
                        {!row.baselineEvidenceLinks.length ? (
                          <p className="rounded-[14px] border border-dashed border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-3 text-xs text-[var(--af-text-tertiary)]">
                            {t("research.versionFieldNone", "无")}
                          </p>
                        ) : null}
                      </div>
                    </div>
                    <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                      <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">
                        {t("research.versionCurrentEvidence", "对照版本证据")}
                      </p>
                      <div className="mt-3 grid grid-cols-1 gap-2">
                        {(row.currentEvidenceLinks.length ? row.currentEvidenceLinks : []).map((link) => (
                          <a
                            key={`current-${row.key}-${link.url}`}
                            href={link.url}
                            target="_blank"
                            rel="noreferrer"
                            className="rounded-[14px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-sm text-[var(--af-text-secondary)] transition hover:border-[var(--af-border-subtle)] hover:bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))]"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <span className="font-medium text-[var(--af-text-secondary)]">{link.title}</span>
                              <span className="rounded-full af-chip af-chip-info px-2 py-0.5 text-[11px] ">{link.tierLabel}</span>
                            </div>
                            {link.meta ? <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">{link.meta}</p> : null}
                          </a>
                        ))}
                        {!row.currentEvidenceLinks.length ? (
                          <p className="rounded-[14px] border border-dashed border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-3 text-xs text-[var(--af-text-tertiary)]">
                            {t("research.versionFieldNone", "无")}
                          </p>
                        ) : null}
                      </div>
                    </div>
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {scorePanels.length ? (
        <section className="af-glass rounded-[30px] p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="af-kicker">{t("research.scorePanelTitle", "Top 3 候选")}</p>
              <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">
                {t("research.scorePanelDesc", "查看两个版本的重点候选变化。")}
              </p>
            </div>
          </div>
          <div className="mt-5 grid grid-cols-1 gap-4">
            {scorePanels.map((panel) => (
              <article key={panel.key} className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-5">
                <h3 className="text-base font-semibold text-[var(--af-text-primary)]">{panel.title}</h3>
                <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
                  {[
                    {
                      key: `${panel.key}-baseline`,
                      label: t("research.versionBaseline", "基线版本"),
                      entities: panel.baselineEntities,
                    },
                    {
                      key: `${panel.key}-current`,
                      label: t("research.versionCurrent", "对照版本"),
                      entities: panel.currentEntities,
                    },
                  ].map((column) => (
                    <div key={column.key} className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                      <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">{column.label}</p>
                      <div className="mt-3 grid grid-cols-1 gap-3">
                        {(column.entities.length ? column.entities : []).map((entity) => (
                          <article key={`${column.key}-${entity.name}`} className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <h4 className="text-sm font-semibold text-[var(--af-text-primary)]">{entity.name}</h4>
                              <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${valueBucket(entity.score).className}`}>
                                {valueBucket(entity.score).label}
                              </span>
                            </div>
                            {entity.reasoning ? <p className="mt-3 text-sm leading-6 text-[var(--af-text-secondary)]">{entity.reasoning}</p> : null}
                            <div className="mt-3 grid grid-cols-1 gap-2">
                              {(entity.score_breakdown.length ? entity.score_breakdown : []).map((factor) => (
                                <div
                                  key={`${entity.name}-${factor.label}`}
                                  className="rounded-[14px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2 text-sm text-[var(--af-text-secondary)]"
                                >
                                  <div className="flex items-center justify-between gap-3">
                                    <span className="font-medium text-[var(--af-text-secondary)]">{factor.label}</span>
                                    <span
                                      className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${factorBucket(factor.score).className}`}
                                    >
                                      {factorBucket(factor.score).label}
                                    </span>
                                  </div>
                                  {factor.note ? <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">{factor.note}</p> : null}
                                </div>
                              ))}
                              {!entity.score_breakdown.length ? (
                                <p className="rounded-[14px] border border-dashed border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2 text-xs text-[var(--af-text-tertiary)]">
                                  {t("research.scorePanelEmpty", "当前版本暂无评分拆解明细。")}
                                </p>
                              ) : null}
                            </div>
                            {entity.evidence_links.length ? (
                              <div className="mt-3 grid grid-cols-1 gap-2">
                                <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--af-text-tertiary)]">
                                  {t("research.evidenceLinks", "依据链接")}
                                </p>
                                {entity.evidence_links.map((link) => (
                                  <div
                                    key={`${entity.name}-${link.url}`}
                                    className="rounded-[14px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-sm text-[var(--af-text-secondary)] transition hover:border-[var(--af-border-subtle)] hover:bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))]"
                                  >
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                      <a
                                        href={normalizeExternalUrl(link.url)}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="font-medium text-[var(--af-text-secondary)] underline-offset-4 hover:text-[var(--af-info)] hover:underline"
                                      >
                                        {link.title}
                                      </a>
                                      <span className="rounded-full af-chip af-chip-info px-2 py-0.5 text-[11px] ">
                                        {link.source_tier === "official"
                                          ? t("research.sourceOfficial", "官方源")
                                          : link.source_tier === "aggregate"
                                            ? t("research.sourceAggregate", "聚合源")
                                            : t("research.sourceMedia", "媒体源")}
                                      </span>
                                    </div>
                                    {link.source_label ? <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">{link.source_label}</p> : null}
                                    <ExternalLinkActions url={link.url} className="mt-2" openLabel={t("research.openEvidenceLink", "网页打开")} />
                                  </div>
                                ))}
                              </div>
                            ) : null}
                          </article>
                        ))}
                        {!column.entities.length ? (
                          <p className="rounded-[16px] border border-dashed border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-4 py-4 text-sm text-[var(--af-text-tertiary)]">
                            {t("research.versionFieldEmpty", "暂无明确线索")}
                          </p>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {sourceContributionPanels.length ? (
        <section className="af-glass rounded-[30px] p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="af-kicker">{t("research.sourceContributionTitle", "来源结构")}</p>
              <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">
                {t("research.sourceContributionDesc", "查看官方、媒体和聚合来源的占比。")}
              </p>
            </div>
          </div>
          <div className="mt-5 grid grid-cols-1 gap-4">
            {sourceContributionPanels.map((panel) => (
              <article key={panel.key} className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-5">
                <h3 className="text-base font-semibold text-[var(--af-text-primary)]">{panel.title}</h3>
                <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
                  {[
                    {
                      key: `${panel.key}-baseline`,
                      label: t("research.versionBaseline", "基线版本"),
                      rows: panel.baselineRows,
                    },
                    {
                      key: `${panel.key}-current`,
                      label: t("research.versionCurrent", "对照版本"),
                      rows: panel.currentRows,
                    },
                  ].map((column) => (
                    <div key={column.key} className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                      <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">{column.label}</p>
                      <div className="mt-3 grid grid-cols-1 gap-3">
                        {(column.rows.length ? column.rows : []).map((row) => (
                          <div key={`${column.key}-${row.tier}`} className="rounded-[16px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                            <div className="flex items-center justify-between gap-3">
                              <span className="text-sm font-medium text-[var(--af-text-secondary)]">{row.label}</span>
                              <span className="rounded-full af-chip px-2.5 py-1 text-xs ">
                                {row.percent}%
                              </span>
                            </div>
                            <div className="mt-3 h-2 overflow-hidden rounded-full bg-[var(--af-surface-muted)]">
                              <div
                                className={`h-full rounded-full ${
                                  row.tier === "official"
                                    ? "bg-[var(--af-success)]"
                                    : row.tier === "aggregate"
                                      ? "bg-[var(--af-warning)]"
                                      : "bg-[var(--af-info)]"
                                }`}
                                style={{ width: `${Math.max(row.percent, 6)}%` }}
                              />
                            </div>
                            <p className="mt-2 text-xs text-[var(--af-text-tertiary)]">
                              {t("research.sourceContributionScore", "来源贡献等级")} {contributionBucket(row.score)}
                            </p>
                          </div>
                        ))}
                        {!column.rows.length ? (
                          <p className="rounded-[16px] border border-dashed border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-4 py-4 text-sm text-[var(--af-text-tertiary)]">
                            {t("research.versionFieldEmpty", "暂无明确线索")}
                          </p>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </>
  );
}
