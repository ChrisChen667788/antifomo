"use client";

import Link from "next/link";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { ResearchConsolePanel } from "@/components/research/research-console-panel";
import { ResearchCenterExperimentControlSection } from "@/components/research/research-center-experiment-control-section";
import { ResearchCenterLowQualityReviewSection } from "@/components/research/research-center-low-quality-review-section";
import { ResearchCenterSourceSettingsSection } from "@/components/research/research-center-source-settings-section";
import { ResearchCenterSidebarControls } from "@/components/research/research-center-sidebar-controls";
import { ResearchCenterReleaseReadinessSection } from "@/components/research/research-center-release-readiness-section";
import { ResearchCenterAssuranceSection } from "@/components/research/research-center-assurance-section";
import { ResearchCenterUpgradeDiagnosticsSection } from "@/components/research/research-center-upgrade-diagnostics-section";
import { ResearchIndustryKnowledgeRetrievalRankingSection } from "@/components/research/research-industry-knowledge-retrieval-ranking-section";
import { ResearchIndustryKnowledgeRetrievalAssuranceSection } from "@/components/research/research-industry-knowledge-retrieval-assurance-section";
import { ResearchIndustryKnowledgeRetrievalEvidenceOperationsSection } from "@/components/research/research-industry-knowledge-retrieval-evidence-operations-section";
import { ResearchCenterResultsSection } from "@/components/research/research-center-results-section";
import { ResearchCenterWatchlistSection } from "@/components/research/research-center-watchlist-section";
import { ResearchCenterWorkspaceSections } from "@/components/research/research-center-workspace-sections";
import { ResearchCenterMarkdownArchivesSection } from "@/components/research/research-center-markdown-archives-section";
import { AppIcon } from "@/components/ui/app-icon";
import { useResearchCenterController } from "@/components/research/use-research-center-controller";

export function ResearchCenter() {
  const { t } = useAppPreferences();
  const controller = useResearchCenterController({ t });

  return (
    <div className="space-y-5">
      <section className="af-glass rounded-[34px] p-5 md:p-7">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div className="max-w-3xl">
            <p className="af-kicker">{t("research.centerKicker", "Research Center")}</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-[var(--af-text-primary)] md:text-[2rem]">
              {t("research.centerTitle", "商机情报中心")}
            </h2>
            <p className="mt-3 text-sm leading-6 text-[var(--af-text-secondary)] md:text-[15px]">
              {t(
                "research.centerDesc",
                "查看情报、动作和重点提醒。",
              )}
            </p>
          </div>
          <div className="flex max-w-full flex-wrap items-center justify-start gap-3 md:justify-end">
            <div className="af-pill inline-flex h-11 max-w-full items-center gap-2 px-4 text-sm font-semibold">
              <AppIcon name="source" className="h-4 w-4 shrink-0 text-[var(--af-info)]" />
              <span>{t("research.centerSourceToggle", "公开源")}</span>
              <span className="shrink-0 rounded-full bg-[var(--af-surface-elevated)] px-2 py-0.5 text-[11px] text-[var(--af-text-tertiary)]">
                {controller.heroProps.enabledSourceCount}
              </span>
            </div>
            <Link href={controller.heroProps.compareHref} className="af-btn af-btn-secondary border px-4 py-2">
              {t("research.centerOpenCompare", "打开对比矩阵")}
            </Link>
            <Link href="/inbox" className="af-btn af-btn-secondary border px-4 py-2">
              {t("research.centerBackToInbox", "返回解决方案智囊")}
            </Link>
          </div>
        </div>

        <ResearchCenterSourceSettingsSection {...controller.sourceSettingsSectionProps} />

        <ResearchCenterReleaseReadinessSection t={t} />

        <ResearchCenterAssuranceSection t={t} />

        <ResearchCenterUpgradeDiagnosticsSection t={t} />

        <div className="mt-6 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          {controller.heroProps.overviewStats.map((stat) => (
            <div key={stat.label} className="rounded-[26px] border border-white/60 bg-white/60 p-4 shadow-[0_12px_35px_rgba(15,23,42,0.06)]">
              <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-slate-400">
                {stat.label}
              </p>
              <p className={`mt-3 text-3xl font-semibold tracking-[-0.05em] ${stat.tone}`}>{stat.value}</p>
            </div>
          ))}
        </div>
      </section>

      <ResearchConsolePanel {...controller.consolePanelProps} />

      <ResearchCenterExperimentControlSection {...controller.experimentControlSectionProps} />

      <ResearchIndustryKnowledgeRetrievalRankingSection t={t} />
      <ResearchIndustryKnowledgeRetrievalAssuranceSection t={t} />
      <ResearchIndustryKnowledgeRetrievalEvidenceOperationsSection t={t} />

      <div className="grid min-w-0 gap-5 xl:grid-cols-[300px,minmax(0,1fr)]">
        <aside className="min-w-0 space-y-4 xl:sticky xl:top-24 xl:self-start">
          <ResearchCenterSidebarControls {...controller.sidebarControlsProps} />

          <ResearchCenterMarkdownArchivesSection {...controller.markdownArchivesSectionProps} />

          <ResearchCenterWorkspaceSections {...controller.workspaceSectionsProps} />

          <ResearchCenterLowQualityReviewSection {...controller.lowQualityReviewSectionProps} />

          <ResearchCenterWatchlistSection {...controller.watchlistSectionProps} />
        </aside>

        <div className="min-w-0">
          <ResearchCenterResultsSection {...controller.resultsSectionProps} />
        </div>
      </div>
    </div>
  );
}
