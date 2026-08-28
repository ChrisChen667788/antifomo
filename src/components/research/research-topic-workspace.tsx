"use client";

import Link from "next/link";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { ResearchConsolePanel } from "@/components/research/research-console-panel";
import {
  qualityLabel,
  qualityTone,
} from "@/components/research/research-topic-workspace-utils";
import { ResearchTopicEntityWorkspaceSection } from "@/components/research/research-topic-entity-workspace-section";
import { ResearchTopicTimelineSection } from "@/components/research/research-topic-timeline-section";
import { ResearchTopicVersionCompareSection } from "@/components/research/research-topic-version-compare-section";
import { useResearchTopicWorkspaceController } from "@/components/research/use-research-topic-workspace-controller";

type ResearchTopicWorkspaceProps = {
  topicId: string;
};

export function ResearchTopicWorkspace({ topicId }: ResearchTopicWorkspaceProps) {
  const { t } = useAppPreferences();
  const controller = useResearchTopicWorkspaceController({ topicId, t });
  const {
    topic,
    loading,
    error,
    planningActions,
    savingActions,
    savingArchive,
    actionMessage,
    latest,
    latestReport,
    compareLeftVersion,
    compareRightVersion,
    compareSummary,
    latestCandidateProfileSummary,
    handleRegenerateActions,
    handleExportVersionRecap,
    handleExportVersionRecapPdf,
    handleExportVersionRecapExecBrief,
    handleSaveVersionRecapArchive,
  } = controller;
  if (loading) {
    return <section className="af-glass rounded-[30px] p-6 text-sm text-slate-500">{t("common.loading", "加载中")}</section>;
  }

  if (error || !topic) {
    return <section className="af-glass rounded-[30px] p-6 text-sm text-rose-600">{error || t("research.topicNotFound", "未找到对应长期专题")}</section>;
  }

  return (
    <div className="space-y-5">
      <section className="af-glass rounded-[30px] p-6">
        <p className="af-kicker">{t("research.centerTrackingKicker", "长期专题")}</p>
        <h2 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-slate-900">{topic.name}</h2>
        <p className="mt-2 text-sm text-slate-500">{topic.keyword}</p>
        {topic.research_focus ? <p className="mt-3 text-sm leading-6 text-slate-600">{topic.research_focus}</p> : null}
        <div className="mt-4 flex flex-wrap gap-2 text-xs">
          <span
            className={`rounded-full px-2.5 py-1 ${
              topic.last_refresh_status === "running"
                ? "bg-sky-100 text-sky-700"
                : topic.last_refresh_status === "failed"
                  ? "bg-rose-100 text-rose-700"
                  : topic.last_refresh_status === "succeeded"
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-slate-100 text-slate-500"
            }`}
          >
            {topic.last_refresh_status === "running"
              ? "刷新中"
              : topic.last_refresh_status === "failed"
                ? "刷新失败"
                : topic.last_refresh_status === "succeeded"
                  ? "刷新成功"
                  : "待刷新"}
          </span>
          {topic.last_refresh_new_targets?.length ? (
            <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">新增甲方 {topic.last_refresh_new_targets.length}</span>
          ) : null}
          {topic.last_refresh_new_competitors?.length ? (
            <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-700">新增竞品 {topic.last_refresh_new_competitors.length}</span>
          ) : null}
          {topic.last_refresh_new_budget_signals?.length ? (
            <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700">新增预算线索 {topic.last_refresh_new_budget_signals.length}</span>
          ) : null}
        </div>
        {topic.last_refresh_note ? <p className="mt-3 text-sm text-slate-500">{topic.last_refresh_note}</p> : null}
        {topic.last_refresh_error ? <p className="mt-2 text-sm text-rose-600">{topic.last_refresh_error}</p> : null}
        <div className="mt-4 flex flex-wrap gap-2">
          {topic.last_report_entry_id ? (
            <Link href={`/knowledge/${topic.last_report_entry_id}`} className="af-btn af-btn-primary px-4 py-2 text-sm">
              {t("research.centerOpenLatestReport", "打开最新研报")}
            </Link>
          ) : null}
          <Link
            href={`/research/compare?query=${encodeURIComponent(topic.keyword)}${topic.region_filter ? `&region=${encodeURIComponent(topic.region_filter)}` : ""}${topic.industry_filter ? `&industry=${encodeURIComponent(topic.industry_filter)}` : ""}&topicId=${encodeURIComponent(topic.id)}`}
            className="af-btn af-btn-secondary border px-4 py-2 text-sm"
          >
            {t("research.centerOpenCompare", "打开对比矩阵")}
          </Link>
          <button
            type="button"
            onClick={() => void handleSaveVersionRecapArchive()}
            disabled={!latest || savingArchive}
            className="af-btn af-btn-secondary border px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
          >
            {savingArchive
              ? t("research.topicArchiving", "归档中...")
              : t("research.topicSaveVersionRecapArchive", "保存到历史归档")}
          </button>
          <button
            type="button"
            onClick={handleExportVersionRecap}
            disabled={!latest}
            className="af-btn af-btn-secondary border px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
          >
            {t("research.topicExportVersionRecap", "导出版本复盘")}
          </button>
          <button
            type="button"
            onClick={handleExportVersionRecapPdf}
            disabled={!latest}
            className="af-btn af-btn-secondary border px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
          >
            {t("research.topicExportVersionRecapPdf", "导出 PDF")}
          </button>
          <button
            type="button"
            onClick={handleExportVersionRecapExecBrief}
            disabled={!latest}
            className="af-btn af-btn-secondary border px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
          >
            {t("research.topicExportVersionRecapExecBrief", "导出 Exec Brief")}
          </button>
          {latestReport ? (
            <>
              <button
                type="button"
                onClick={() => void handleRegenerateActions(false)}
                disabled={planningActions || savingActions}
                className="af-btn af-btn-secondary border px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
              >
                {t("research.topicRegenerateActions", "一键重新生成行动卡")}
              </button>
              <button
                type="button"
                onClick={() => void handleRegenerateActions(true)}
                disabled={planningActions || savingActions}
                className="af-btn af-btn-secondary border px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
              >
                {t("research.topicRegenerateActionsFocus", "生成并加入 Focus 参考")}
              </button>
            </>
          ) : null}
        </div>
        {actionMessage ? <p className="mt-3 text-sm text-slate-500">{actionMessage}</p> : null}
      </section>

      <ResearchConsolePanel
        topicId={topic.id}
        topicName={topic.name}
        title={t("research.consoleTopicKicker", "专题追问")}
        description={t(
          "research.consoleTopicDesc",
          "继续围绕当前专题追问预算、客户、竞品和伙伴。",
        )}
      />

      {latest ? (
        <section className="grid grid-cols-1 gap-4 lg:grid-cols-[1.15fr_0.85fr]">
          <article className="af-glass rounded-[28px] p-5">
            <p className="af-kicker">{t("research.latestVersion", "最新版本")}</p>
            <h3 className="mt-2 text-xl font-semibold text-slate-900">{latest.title}</h3>
            <div className="mt-3 flex flex-wrap gap-2 text-xs">
              <span className={`rounded-full px-2.5 py-1 ${qualityTone(latest.evidence_density)}`}>
                {t("research.centerEvidenceDensity", "证据密度")}·{qualityLabel(latest.evidence_density)}
              </span>
              <span className={`rounded-full px-2.5 py-1 ${qualityTone(latest.source_quality)}`}>
                {t("research.centerSourceQuality", "来源质量")}·{qualityLabel(latest.source_quality)}
              </span>
              <span className="rounded-full bg-white/70 px-2.5 py-1 text-slate-500">
                {t("research.centerCardSources", "来源数")} {latest.source_count}
              </span>
              {latestCandidateProfileSummary.companies.length ? (
                <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
                  建议核验公司 {latestCandidateProfileSummary.companies.length}
                </span>
              ) : null}
              {latestCandidateProfileSummary.hitCount > 0 ? (
                <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
                  公开来源 {latestCandidateProfileSummary.hitCount}
                </span>
              ) : null}
              {latestCandidateProfileSummary.officialHitCount > 0 ? (
                <span className="rounded-full bg-cyan-50 px-2.5 py-1 text-cyan-700">
                  其中官方源 {latestCandidateProfileSummary.officialHitCount}
                </span>
              ) : null}
              {topic.last_refresh_new_targets?.length ? (
                <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">新增甲方 {topic.last_refresh_new_targets.length}</span>
              ) : null}
              {topic.last_refresh_new_competitors?.length ? (
                <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-700">新增竞品 {topic.last_refresh_new_competitors.length}</span>
              ) : null}
              {topic.last_refresh_new_budget_signals?.length ? (
                <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700">新增预算线索 {topic.last_refresh_new_budget_signals.length}</span>
              ) : null}
            </div>
            {topic.last_refresh_new_targets?.length || topic.last_refresh_new_competitors?.length || topic.last_refresh_new_budget_signals?.length ? (
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                {topic.last_refresh_new_targets?.slice(0, 2).map((value) => (
                  <span key={`topic-new-target-${value}`} className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
                    甲方 · {value}
                  </span>
                ))}
                {topic.last_refresh_new_competitors?.slice(0, 2).map((value) => (
                  <span key={`topic-new-competitor-${value}`} className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-700">
                    竞品 · {value}
                  </span>
                ))}
                {topic.last_refresh_new_budget_signals?.slice(0, 1).map((value) => (
                  <span key={`topic-new-budget-${value}`} className="rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700">
                    预算 · {value}
                  </span>
                ))}
              </div>
            ) : null}
            {latestCandidateProfileSummary.companies.length ? (
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                {latestCandidateProfileSummary.companies.map((value) => (
                  <span key={`latest-candidate-${value}`} className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
                    候选公司 · {value}
                  </span>
                ))}
                {latestCandidateProfileSummary.sourceLabels.map((value) => (
                  <span key={`latest-candidate-source-${value}`} className="rounded-full bg-cyan-50 px-2.5 py-1 text-cyan-700">
                    {value}
                  </span>
                ))}
              </div>
            ) : null}
            {latestReport?.executive_summary ? (
              <p className="mt-4 text-sm leading-7 text-slate-600">
                {String(latestReport.executive_summary || "").slice(0, 240)}
              </p>
            ) : null}
          </article>

          <article className="af-glass rounded-[28px] p-5">
            <p className="af-kicker">{t("research.versionCompare", "版本对比")}</p>
            {compareLeftVersion && compareRightVersion ? (
              <>
                <p className="mt-2 text-sm text-slate-500">
                  {new Date(compareLeftVersion.refreshed_at).toLocaleString()} → {new Date(compareRightVersion.refreshed_at).toLocaleString()}
                </p>
                <ul className="mt-4 space-y-2 text-sm leading-6 text-slate-700">
                  {(compareSummary.length ? compareSummary : [t("research.versionCompareStable", "最近两次版本在关键指标上基本稳定")]).map((row) => (
                    <li key={row} className="flex gap-2">
                      <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-slate-300" />
                      <span>{row}</span>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="mt-3 text-sm text-slate-500">{t("research.versionCompareEmpty", "当前只有一个版本，继续刷新后可查看版本变化。")}</p>
            )}
          </article>
        </section>
      ) : null}

      <ResearchTopicEntityWorkspaceSection controller={controller} t={t} />

      <ResearchTopicVersionCompareSection controller={controller} t={t} />

      <ResearchTopicTimelineSection controller={controller} t={t} />
    </div>
  );
}
