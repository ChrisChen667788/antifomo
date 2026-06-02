"use client";

import Link from "next/link";
import { ResearchArchiveSectionLinkPopover } from "@/components/research/research-archive-section-link-popover";
import type { useResearchTopicWorkspaceController } from "@/components/research/use-research-topic-workspace-controller";
import {
  buildArchiveCompareHref,
  followupResolutionDisplay,
  qualityLabel,
  qualityTone,
  timelineArchiveKindLabel,
  timelineEventTone,
} from "@/components/research/research-topic-workspace-utils";

type ResearchTopicWorkspaceController = ReturnType<typeof useResearchTopicWorkspaceController>;

type ResearchTopicTimelineSectionProps = {
  controller: ResearchTopicWorkspaceController;
  t: (key: string, fallback: string) => string;
};

export function ResearchTopicTimelineSection({
  controller,
  t,
}: ResearchTopicTimelineSectionProps) {
  const {
    topic,
    timelineStats,
    timelineMessage,
    timelineEvents,
    compareLeftId,
    setCompareLeftId,
    compareRightId,
    setCompareRightId,
    setTimelineMessage,
  } = controller;

  if (!topic) return null;

  return (
      <section className="af-glass rounded-[30px] p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="af-kicker">{t("research.topicTimeline", "专题时间线")}</p>
            <p className="mt-2 text-sm text-slate-500">
              {t("research.topicTimelineDesc", "把专题刷新版本、已保存快照和差异复盘放到同一条时间线里，方便回看当时结论。")}
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="rounded-full bg-white/70 px-2.5 py-1 text-slate-600">
              {t("research.topicTimelineVersions", "版本")} {timelineStats.versionCount}
            </span>
            <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
              {t("research.topicTimelineSnapshots", "快照")} {timelineStats.snapshotCount}
            </span>
            <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700">
              {t("research.topicTimelineArchives", "复盘")} {timelineStats.archiveCount}
            </span>
          </div>
        </div>
        {timelineMessage ? <p className="mt-3 text-sm text-slate-500">{timelineMessage}</p> : null}
        <div className="mt-5 space-y-3">
          {timelineEvents.length ? (
            timelineEvents.map((event) => {
              const isVersion = event.event_type === "report_version";
              const isSnapshot = event.event_type === "compare_snapshot";
              const isArchive = event.event_type === "markdown_archive";
              const isBaseline = !!event.report_version_id && event.report_version_id === compareLeftId;
              const isCurrent = !!event.report_version_id && event.report_version_id === compareRightId;
              const snapshotHref = event.compare_snapshot_id
                ? `/research/compare?snapshot=${encodeURIComponent(event.compare_snapshot_id)}&topicId=${encodeURIComponent(topic.id)}`
                : "";
              const archiveHref = event.markdown_archive_id
                ? `/research/archives/${encodeURIComponent(event.markdown_archive_id)}`
                : "";
              const originalArchiveCompareHref = buildArchiveCompareHref(
                event.current_markdown_archive_id,
                event.compare_markdown_archive_id,
              );
              const liveCompareHref = event.query
                ? `/research/compare?query=${encodeURIComponent(event.query)}${topic.region_filter ? `&region=${encodeURIComponent(topic.region_filter)}` : ""}${topic.industry_filter ? `&industry=${encodeURIComponent(topic.industry_filter)}` : ""}&topicId=${encodeURIComponent(topic.id)}`
                : `/research/compare?topicId=${encodeURIComponent(topic.id)}`;
              return (
                <article
                  key={`${event.event_type}-${event.id}`}
                  className={`rounded-[24px] border p-5 ${
                    isBaseline
                      ? "border-emerald-200 bg-emerald-50/55"
                      : isCurrent
                        ? "border-sky-200 bg-sky-50/55"
                        : "border-white/60 bg-white/65"
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="max-w-3xl">
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        <span
                          className={`rounded-full px-2.5 py-1 ${timelineEventTone(event.event_type)}`}
                        >
                          {isVersion
                            ? t("research.topicTimelineVersionEvent", "研报版本")
                            : isSnapshot
                              ? t("research.topicTimelineSnapshotEvent", "Compare 快照")
                              : t("research.topicTimelineArchiveEvent", "差异复盘")}
                        </span>
                        <span className="rounded-full bg-white/75 px-2.5 py-1 text-slate-500">
                          {new Date(event.occurred_at).toLocaleString()}
                        </span>
                        {isBaseline ? (
                          <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-emerald-700">
                            {t("research.versionBaseline", "基线版本")}
                          </span>
                        ) : null}
                        {isCurrent ? (
                          <span className="rounded-full bg-sky-100 px-2.5 py-1 text-sky-700">
                            {t("research.versionCurrent", "对照版本")}
                          </span>
                        ) : null}
                        {isArchive ? (
                          <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700">
                            {timelineArchiveKindLabel(event.markdown_archive_kind)}
                          </span>
                        ) : null}
                      </div>
                      <h3 className="mt-3 text-lg font-semibold text-slate-900">{event.title}</h3>
                      {event.summary ? <p className="mt-2 text-sm leading-6 text-slate-600">{event.summary}</p> : null}
                      <div className="mt-3 flex flex-wrap gap-2 text-xs">
                        {isVersion ? (
                          <>
                            {event.evidence_density ? (
                              <span className={`rounded-full px-2.5 py-1 ${qualityTone(event.evidence_density)}`}>
                                {t("research.centerEvidenceDensity", "证据密度")}·{qualityLabel(event.evidence_density)}
                              </span>
                            ) : null}
                            {event.source_quality ? (
                              <span className={`rounded-full px-2.5 py-1 ${qualityTone(event.source_quality)}`}>
                                {t("research.centerSourceQuality", "来源质量")}·{qualityLabel(event.source_quality)}
                              </span>
                            ) : null}
                            <span className="rounded-full bg-white/70 px-2.5 py-1 text-slate-500">
                              {t("research.centerCardSources", "来源数")} {event.source_count}
                            </span>
                            {event.new_targets.length ? (
                              <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
                                新增甲方 {event.new_targets.length}
                              </span>
                            ) : null}
                            {event.new_competitors.length ? (
                              <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-700">
                                新增竞品 {event.new_competitors.length}
                              </span>
                            ) : null}
                            {event.new_budget_signals.length ? (
                              <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700">
                                新增预算 {event.new_budget_signals.length}
                              </span>
                            ) : null}
                          </>
                        ) : isSnapshot ? (
                          <>
                            <span className="rounded-full bg-white/70 px-2.5 py-1 text-slate-500">
                              实体 {event.row_count}
                            </span>
                            <span className="rounded-full bg-white/70 px-2.5 py-1 text-slate-500">
                              来源研报 {event.source_entry_count}
                            </span>
                            {event.roles.map((role) => (
                              <span key={`${event.id}-${role}`} className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
                                {role}
                              </span>
                            ))}
                            {event.linked_report_version_title ? (
                              <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-700">
                                关联版本 · {event.linked_report_version_title}
                              </span>
                            ) : null}
                          </>
                        ) : (
                          <>
                            {event.compare_snapshot_name ? (
                              <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
                                关联快照 · {event.compare_snapshot_name}
                              </span>
                            ) : null}
                            {event.linked_report_version_title ? (
                              <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-700">
                                关联版本 · {event.linked_report_version_title}
                              </span>
                            ) : null}
                            {event.query ? (
                              <span className="rounded-full bg-white/70 px-2.5 py-1 text-slate-500">
                                查询词 · {event.query}
                              </span>
                            ) : null}
                          </>
                        )}
                      </div>
                      {!isVersion && event.preview_names.length ? (
                        <p className="mt-3 text-xs leading-5 text-slate-500">{event.preview_names.join(" / ")}</p>
                      ) : null}
                      {!isVersion && event.linked_report_diff_summary.length ? (
                        <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
                          {event.linked_report_diff_summary.slice(0, 2).map((line) => (
                            <li key={`${event.id}-${line}`} className="flex gap-2">
                              <span
                                className={`mt-[7px] h-1.5 w-1.5 rounded-full ${
                                  isArchive ? "bg-emerald-300" : "bg-amber-300"
                                }`}
                              />
                              <span>{line}</span>
                            </li>
                          ))}
                        </ul>
                      ) : null}
                      {(event.followup_title_resolution || event.followup_summary_resolution || event.followup_impacted_sections.length) ? (
                        <div className="mt-3 rounded-[16px] border border-sky-100 bg-sky-50/55 px-3 py-3">
                          <div className="flex flex-wrap gap-2 text-xs">
                            {event.followup_title_resolution ? (
                              <span className="rounded-full bg-white/80 px-2.5 py-1 text-sky-700">
                                标题 · {followupResolutionDisplay(event.followup_title_resolution)}
                              </span>
                            ) : null}
                            {event.followup_summary_resolution ? (
                              <span className="rounded-full bg-white/80 px-2.5 py-1 text-slate-600">
                                摘要 · {followupResolutionDisplay(event.followup_summary_resolution)}
                              </span>
                            ) : null}
                            {event.followup_impacted_sections.slice(0, 3).map((section) => (
                              <span key={`${event.id}-followup-${section}`} className="rounded-full bg-sky-100 px-2.5 py-1 text-sky-700">
                                影响章节 · {section}
                              </span>
                            ))}
                          </div>
                        </div>
                      ) : null}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {isVersion ? (
                        <>
                          {event.report_version_id ? (
                            <button
                              type="button"
                              onClick={() => setCompareLeftId(event.report_version_id || "")}
                              className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                            >
                              {t("research.versionSetBaseline", "设为基线")}
                            </button>
                          ) : null}
                          {event.report_version_id ? (
                            <button
                              type="button"
                              onClick={() => setCompareRightId(event.report_version_id || "")}
                              className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                            >
                              {t("research.versionSetCurrent", "设为对照")}
                            </button>
                          ) : null}
                          {event.entry_id ? (
                            <Link href={`/knowledge/${event.entry_id}`} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                              {t("research.openSelectedVersion", "打开该版本研报")}
                            </Link>
                          ) : null}
                        </>
                      ) : isSnapshot ? (
                        <>
                          {snapshotHref ? (
                            <Link href={snapshotHref} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                              {t("research.compareOpenSnapshot", "打开快照")}
                            </Link>
                          ) : null}
                          <Link href={liveCompareHref} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                            {t("research.compareOpenLive", "查看实时结果")}
                          </Link>
                          {event.linked_report_version_id ? (
                            <button
                              type="button"
                              onClick={() => setCompareRightId(event.linked_report_version_id || "")}
                              className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                            >
                              {t("research.topicTimelineUseLinkedVersion", "切到关联版本")}
                            </button>
                          ) : null}
                        </>
                      ) : (
                        <>
                          {archiveHref ? (
                            <Link href={archiveHref} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                              {t("research.topicTimelineOpenArchive", "打开复盘归档")}
                            </Link>
                          ) : null}
                          {event.markdown_archive_kind === "archive_diff_recap" && event.markdown_archive_id ? (
                            <ResearchArchiveSectionLinkPopover
                              archiveId={event.markdown_archive_id}
                              fallbackCurrentArchiveId={event.current_markdown_archive_id}
                              fallbackCompareArchiveId={event.compare_markdown_archive_id}
                              buttonLabel="变化深链"
                              buttonClassName="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                              align="right"
                              onCopyMessage={setTimelineMessage}
                            />
                          ) : null}
                          {originalArchiveCompareHref ? (
                            <Link href={originalArchiveCompareHref} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                              {t("research.topicTimelineOpenOriginalArchiveCompare", "打开原始对照")}
                            </Link>
                          ) : null}
                          {snapshotHref ? (
                            <Link href={snapshotHref} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                              {t("research.compareOpenSnapshot", "打开关联快照")}
                            </Link>
                          ) : null}
                          {event.linked_report_version_id ? (
                            <button
                              type="button"
                              onClick={() => setCompareRightId(event.linked_report_version_id || "")}
                              className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                            >
                              {t("research.topicTimelineUseLinkedVersion", "切到关联版本")}
                            </button>
                          ) : null}
                        </>
                      )}
                    </div>
                  </div>
                </article>
              );
            })
          ) : (
            <p className="text-sm text-slate-500">{t("research.topicTimelineEmpty", "当前还没有可回看的专题时间线事件。")}</p>
          )}
        </div>
      </section>
  );
}
