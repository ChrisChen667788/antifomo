"use client";

import Link from "next/link";
import type { useResearchCenterController } from "@/components/research/use-research-center-controller";
import {
  buildTopicWorkspaceHref,
  qualityLabel,
  qualityTone,
  trackingStatusLabel,
  trackingStatusTone,
} from "@/components/research/research-center-utils";
import { sanitizeExternalDisplayText } from "@/lib/commercial-risk-copy";

type ResearchCenterController = ReturnType<typeof useResearchCenterController>;
type ResearchCenterWorkspaceSectionsProps = ResearchCenterController["workspaceSectionsProps"];

export function ResearchCenterWorkspaceSections({
  t,
  compareSnapshots,
  savedViews,
  trackingTopics,
  workspaceSaving,
  refreshingTopicId,
  buildCompareHref,
  buildCompareSnapshotHref,
  handleDeleteCompareSnapshot,
  handleSaveCurrentView,
  handleDeleteSavedView,
  applySavedView,
  handleSaveTrackingTopic,
  handleDeleteTrackingTopic,
  handleRefreshTrackingTopic,
  applyTrackingTopic,
  handleCreateWatchlist,
}: ResearchCenterWorkspaceSectionsProps) {
  return (
    <>
          <section className="af-glass rounded-[30px] p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="af-kicker">{t("research.compareSnapshotKicker", "Compare Snapshots")}</p>
                <h3 className="mt-2 text-lg font-semibold text-[var(--af-text-primary)]">
                  {t("research.compareSnapshotTitle", "已保存对比快照")}
                </h3>
                <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">
                  {t("research.compareSnapshotWorkspaceDesc", "冻结当前 compare 结果，便于复盘、转发和后续与新版本继续对照。")}
                </p>
              </div>
            </div>

            <div className="mt-4 space-y-3">
              {compareSnapshots.length ? (
                compareSnapshots.map((snapshot) => (
                  <article key={snapshot.id} className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-[var(--af-text-primary)]">{snapshot.name}</p>
                        <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">
                          {snapshot.query || t("research.centerSavedViewsNoQuery", "无关键词")} · {new Date(snapshot.updated_at).toLocaleDateString()}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => void handleDeleteCompareSnapshot(snapshot.id)}
                        className="text-xs font-medium text-[var(--af-text-tertiary)] hover:text-[var(--af-text-secondary)]"
                      >
                        {t("common.delete", "删除")}
                      </button>
                    </div>
                    {snapshot.summary ? (
                      <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{sanitizeExternalDisplayText(snapshot.summary)}</p>
                    ) : null}
                    <div className="mt-2 flex flex-wrap gap-2 text-xs">
                      <span className="rounded-full af-chip px-2.5 py-1 ">
                        实体 {snapshot.row_count}
                      </span>
                      <span className="rounded-full af-chip px-2.5 py-1 ">
                        来源研报 {snapshot.source_entry_count}
                      </span>
                      {snapshot.roles.map((role) => (
                        <span key={`${snapshot.id}-${role}`} className="rounded-full af-chip px-2.5 py-1 ">
                          {role}
                        </span>
                      ))}
                      {snapshot.tracking_topic_name ? (
                        <span className="rounded-full af-chip af-chip-info px-2.5 py-1 ">
                          {snapshot.tracking_topic_name}
                        </span>
                      ) : null}
                      {snapshot.report_version_title ? (
                        <span className="rounded-full af-chip af-chip-warning px-2.5 py-1 ">
                          {snapshot.report_version_title}
                        </span>
                      ) : null}
                    </div>
                    {snapshot.preview_names.length ? (
                      <p className="mt-2 text-xs leading-5 text-[var(--af-text-tertiary)]">
                        {snapshot.preview_names.join(" / ")}
                      </p>
                    ) : null}
                    {snapshot.linked_report_diff?.summary_lines?.length ? (
                      <p className="mt-2 text-xs leading-5 text-[var(--af-text-tertiary)]">
                        {snapshot.linked_report_diff.summary_lines[0]}
                      </p>
                    ) : null}
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Link href={buildCompareSnapshotHref(snapshot.id)} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                        {t("research.compareOpenSnapshot", "打开快照")}
                      </Link>
                      {snapshot.tracking_topic_id ? (
                        <Link href={buildTopicWorkspaceHref(snapshot.tracking_topic_id)} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                          {t("research.openTopicWorkspace", "专题工作台")}
                        </Link>
                      ) : null}
                    </div>
                  </article>
                ))
              ) : (
                <p className="text-sm text-[var(--af-text-tertiary)]">
                  {t("research.compareSnapshotEmpty", "还没有保存的对比快照，先在对比矩阵里固定一次结果。")}
                </p>
              )}
            </div>
          </section>

          <section className="af-glass rounded-[30px] p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="af-kicker">{t("research.centerSavedViewsKicker", "Saved Views")}</p>
                <h3 className="mt-2 text-lg font-semibold text-[var(--af-text-primary)]">
                  {t("research.centerSavedViewsTitle", "保存视图")}
                </h3>
                <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">
                  {t("research.centerSavedViewsDesc", "把当前筛选和业务视角保存成可复用入口。")}
                </p>
              </div>
              <button
                type="button"
                onClick={() => void handleSaveCurrentView()}
                disabled={workspaceSaving}
                className="af-btn af-btn-secondary border px-3 py-1.5 text-sm"
              >
                {t("research.centerSaveCurrentView", "保存当前视图")}
              </button>
            </div>

            <div className="mt-4 space-y-3">
              {savedViews.length ? (
                savedViews.map((view) => (
                  <article key={view.id} className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-[var(--af-text-primary)]">{view.name}</p>
                        <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">
                          {view.query || t("research.centerSavedViewsNoQuery", "无关键词")} · {new Date(view.updated_at).toLocaleDateString()}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => void handleDeleteSavedView(view.id)}
                        className="text-xs font-medium text-[var(--af-text-tertiary)] hover:text-[var(--af-text-secondary)]"
                      >
                        {t("common.delete", "删除")}
                      </button>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button type="button" onClick={() => applySavedView(view)} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                        {t("research.centerApplyView", "应用视图")}
                      </button>
                      <Link href={buildCompareHref({ query: view.query, region: view.region_filter, industry: view.industry_filter })} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                        {t("research.centerOpenCompare", "打开对比矩阵")}
                      </Link>
                    </div>
                  </article>
                ))
              ) : (
                <p className="text-sm text-[var(--af-text-tertiary)]">
                  {t("research.centerSavedViewsEmpty", "还没有保存视图，先固定一组筛选条件。")}
                </p>
              )}
            </div>
          </section>

          <section className="af-glass rounded-[30px] p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="af-kicker">{t("research.centerTrackingKicker", "Tracking Topics")}</p>
                <h3 className="mt-2 text-lg font-semibold text-[var(--af-text-primary)]">
                  {t("research.centerTrackingTitle", "长期跟踪专题")}
                </h3>
                <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">
                  {t("research.centerTrackingDesc", "把高价值关键词沉淀成长期专题，便于持续刷新研报和竞对观察。")}
                </p>
              </div>
              <button
                type="button"
                onClick={() => void handleSaveTrackingTopic()}
                disabled={workspaceSaving}
                className="af-btn af-btn-secondary border px-3 py-1.5 text-sm"
              >
                {t("research.centerSaveTopic", "加入长期跟踪")}
              </button>
            </div>

            <div className="mt-4 space-y-3">
              {trackingTopics.length ? (
                trackingTopics.map((topic) => (
                  <article key={topic.id} className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-[var(--af-text-primary)]">{topic.name}</p>
                        <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">
                          {topic.keyword} · {new Date(topic.updated_at).toLocaleDateString()}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => void handleDeleteTrackingTopic(topic.id)}
                        className="text-xs font-medium text-[var(--af-text-tertiary)] hover:text-[var(--af-text-secondary)]"
                      >
                        {t("common.delete", "删除")}
                      </button>
                    </div>
                    {topic.research_focus ? (
                      <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{topic.research_focus}</p>
                    ) : null}
                    {topic.last_refreshed_at ? (
                      <p className="mt-2 text-xs text-[var(--af-text-tertiary)]">
                        {t("research.centerTrackingLastRefresh", "最近刷新")} · {new Date(topic.last_refreshed_at).toLocaleString()}
                      </p>
                    ) : null}
                    <div className="mt-2 flex flex-wrap gap-2 text-xs">
                      <span className={`rounded-full px-2.5 py-1 font-medium ${trackingStatusTone(topic.last_refresh_status)}`}>
                        {trackingStatusLabel(topic.last_refresh_status)}
                      </span>
                      {topic.last_refresh_new_targets?.length ? (
                        <span className="rounded-full af-chip af-chip-info px-2.5 py-1 ">
                          新增甲方 {topic.last_refresh_new_targets.length}
                        </span>
                      ) : null}
                      {topic.last_refresh_new_competitors?.length ? (
                        <span className="rounded-full af-chip af-chip-warning px-2.5 py-1 ">
                          新增竞品 {topic.last_refresh_new_competitors.length}
                        </span>
                      ) : null}
                      {topic.last_refresh_new_budget_signals?.length ? (
                        <span className="rounded-full af-chip af-chip-success px-2.5 py-1 ">
                          新增预算线索 {topic.last_refresh_new_budget_signals.length}
                        </span>
                      ) : null}
                    </div>
                    {topic.last_refresh_note ? (
                      <p className="mt-2 text-xs leading-5 text-[var(--af-text-tertiary)]">{sanitizeExternalDisplayText(topic.last_refresh_note)}</p>
                    ) : null}
                    {topic.last_refresh_error ? (
                      <p className="mt-2 text-xs leading-5 text-[var(--af-danger)]">{topic.last_refresh_error}</p>
                    ) : null}
                    {topic.last_refresh_new_targets?.length || topic.last_refresh_new_competitors?.length || topic.last_refresh_new_budget_signals?.length ? (
                      <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
                        {topic.last_refresh_new_targets?.slice(0, 2).map((value) => (
                          <span key={`${topic.id}-new-target-${value}`} className="rounded-full af-chip af-chip-info px-2 py-1 ">
                            甲方 · {value}
                          </span>
                        ))}
                        {topic.last_refresh_new_competitors?.slice(0, 2).map((value) => (
                          <span key={`${topic.id}-new-competitor-${value}`} className="rounded-full af-chip af-chip-warning px-2 py-1 ">
                            竞品 · {value}
                          </span>
                        ))}
                        {topic.last_refresh_new_budget_signals?.slice(0, 1).map((value) => (
                          <span key={`${topic.id}-new-budget-${value}`} className="rounded-full af-chip af-chip-success px-2 py-1 ">
                            预算 · {value}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => void handleRefreshTrackingTopic(topic.id)}
                        className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                        disabled={refreshingTopicId === topic.id}
                      >
                        {refreshingTopicId === topic.id
                          ? t("research.centerRefreshingTopic", "刷新中...")
                          : t("research.centerRefreshTopic", "一键刷新研报")}
                      </button>
                      <button type="button" onClick={() => applyTrackingTopic(topic)} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                        {t("research.centerApplyTopic", "应用专题")}
                      </button>
                      <button type="button" onClick={() => void handleCreateWatchlist(topic)} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                        {t("research.centerCreateWatchlist", "设为 Watchlist")}
                      </button>
                      {topic.last_report_entry_id ? (
                        <Link href={`/knowledge/${topic.last_report_entry_id}`} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                          {t("research.centerOpenLatestReport", "打开最新研报")}
                        </Link>
                      ) : null}
                      <Link href={buildTopicWorkspaceHref(topic.id)} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                        {t("research.centerOpenTopicWorkspace", "专题版本对比")}
                      </Link>
                      <Link href={buildCompareHref({ query: topic.keyword, region: topic.region_filter, industry: topic.industry_filter, topicId: topic.id })} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                        {t("research.centerOpenCompare", "打开对比矩阵")}
                      </Link>
                    </div>
                    {topic.report_history?.length ? (
                      <div className="mt-3 rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">
                          {t("research.centerTopicHistory", "最近版本")}
                        </p>
                        <div className="mt-2 space-y-2">
                          {topic.report_history.slice(0, 2).map((version) => (
                            <div key={`${topic.id}-${version.refreshed_at}`} className="flex flex-wrap items-center gap-2 text-xs text-[var(--af-text-tertiary)]">
                              <span>{new Date(version.refreshed_at).toLocaleString()}</span>
                              <span className={`rounded-full px-2 py-0.5 font-medium ${qualityTone(version.evidence_density)}`}>
                                {t("research.centerEvidenceDensity", "证据密度")}·{qualityLabel(version.evidence_density)}
                              </span>
                              <span className={`rounded-full px-2 py-0.5 font-medium ${qualityTone(version.source_quality)}`}>
                                {t("research.centerSourceQuality", "来源质量")}·{qualityLabel(version.source_quality)}
                              </span>
                              <span>{t("research.centerCardSources", "来源数")} {version.source_count}</span>
                              {version.new_target_count ? <span>新增甲方 {version.new_target_count}</span> : null}
                              {version.new_competitor_count ? <span>新增竞品 {version.new_competitor_count}</span> : null}
                              {version.new_budget_signal_count ? <span>新增预算 {version.new_budget_signal_count}</span> : null}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </article>
                ))
              ) : (
                <p className="text-sm text-[var(--af-text-tertiary)]">
                  {t("research.centerTrackingEmpty", "还没有长期跟踪专题，可把高价值关键词固定下来。")}
                </p>
              )}
            </div>
          </section>
    </>
  );
}
