"use client";

import Link from "next/link";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { ResearchConsolePanel } from "@/components/research/research-console-panel";
import { ResearchCenterExperimentControlSection } from "@/components/research/research-center-experiment-control-section";
import { ResearchCenterLowQualityReviewSection } from "@/components/research/research-center-low-quality-review-section";
import { ResearchCenterSourceSettingsSection } from "@/components/research/research-center-source-settings-section";
import { ResearchCenterSidebarControls } from "@/components/research/research-center-sidebar-controls";
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
            <h2 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-slate-900 md:text-[2rem]">
              {t("research.centerTitle", "商机情报中心")}
            </h2>
            <p className="mt-3 text-sm leading-6 text-slate-500 md:text-[15px]">
              {t(
                "research.centerDesc",
                "统一查看保存过的情报简报、推荐动作和 Focus 参考，快速回到客户推进、投标排期与生态协同。",
              )}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="af-glass-orb-btn inline-flex h-11 items-center gap-2 rounded-full px-4 text-sm font-medium text-slate-700">
              <AppIcon name="source" className="h-4 w-4" />
              <span>{t("research.centerSourceToggle", "公开源")}</span>
              <span className="rounded-full bg-white/70 px-2 py-0.5 text-[11px] text-slate-500">
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

        <div className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
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

      <div className="grid gap-5 xl:grid-cols-[300px,minmax(0,1fr)]">
        <aside className="space-y-4 xl:sticky xl:top-24 xl:self-start">
          <ResearchCenterSidebarControls {...controller.sidebarControlsProps} />

          <ResearchCenterMarkdownArchivesSection {...controller.markdownArchivesSectionProps} />

          <ResearchCenterWorkspaceSections {...controller.workspaceSectionsProps} />

          <ResearchCenterLowQualityReviewSection {...controller.lowQualityReviewSectionProps} />

          <ResearchCenterWatchlistSection {...controller.watchlistSectionProps} />
        </aside>

        <ResearchCenterResultsSection {...controller.resultsSectionProps} />
      </div>
    </div>
  );
}
