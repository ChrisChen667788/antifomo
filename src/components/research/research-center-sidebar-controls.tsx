"use client";

import Link from "next/link";
import type { useResearchCenterController } from "@/components/research/use-research-center-controller";
import { formatWatchlistTime } from "@/components/research/research-center-utils";
import { sanitizeExternalDisplayText } from "@/lib/commercial-risk-copy";

type ResearchCenterController = ReturnType<typeof useResearchCenterController>;
type ResearchCenterSidebarControlsProps = ResearchCenterController["sidebarControlsProps"];

export function ResearchCenterSidebarControls({
  t,
  dailyBrief,
  dailyBriefLoading,
  dailyBriefRefreshing,
  dailyBriefError,
  filter,
  setFilter,
  filterMeta,
  queryDraft,
  setQueryDraft,
  focusOnly,
  setFocusOnly,
  retrievalLens,
  setRetrievalLens,
  retrievalLensMeta,
  perspective,
  setPerspective,
  perspectiveMeta,
  activePerspective,
  regionFilter,
  setRegionFilter,
  regionOptions,
  industryFilter,
  setIndustryFilter,
  industryOptions,
  actionTypeFilter,
  setActionTypeFilter,
  actionTypeOptions,
  visibleItems,
  handleRefreshDailyBrief,
  handleSearchSubmit,
  clearFacetFilters,
}: ResearchCenterSidebarControlsProps) {
  const segmentButtonClass = (active: boolean) =>
    `rounded-full px-3 py-1.5 text-sm font-medium transition ${
      active
        ? "bg-[var(--af-text-primary)] text-[var(--af-text-inverse)]"
        : "border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] text-[var(--af-text-secondary)] hover:border-[var(--af-border-strong)] hover:bg-[var(--af-surface-hover)]"
    }`;

  return (
    <>
          <section className="af-glass rounded-[30px] p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="af-kicker">今日摘要</p>
                <h3 className="mt-2 text-lg font-semibold text-[var(--af-text-primary)]">今日研究摘要</h3>
                <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">
                  {sanitizeExternalDisplayText("先看今日重点，再决定是否刷新专题。")}
                </p>
              </div>
              <button
                type="button"
                onClick={() => void handleRefreshDailyBrief()}
                className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                disabled={dailyBriefRefreshing}
              >
                {dailyBriefRefreshing ? "刷新中..." : "刷新"}
              </button>
            </div>
            {dailyBriefLoading ? (
              <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">{t("common.loading", "加载中")}</p>
            ) : dailyBrief ? (
              <div className="mt-4 space-y-3">
                <div className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                  <p className="text-sm font-semibold text-[var(--af-text-primary)]">
                    {sanitizeExternalDisplayText(dailyBrief.headline || "今天优先处理监控变化和新增高价值内容。")}
                  </p>
                  <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                    {sanitizeExternalDisplayText(dailyBrief.summary || "今天暂无新的高价值内容，建议刷新专题或继续处理稍后读。")}
                  </p>
                  {dailyBrief.generated_at ? (
                    <p className="mt-2 text-xs text-[var(--af-text-tertiary)]">
                      生成于 · {formatWatchlistTime(dailyBrief.generated_at)}
                    </p>
                  ) : null}
                </div>
                {dailyBrief.top_items?.length ? (
                  <div className="space-y-2">
                    {dailyBrief.top_items.slice(0, 3).map((item) => (
                      <Link
                        key={item.id}
                        href={`/items/${item.id}`}
                        className="block rounded-[20px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3 transition hover:border-[var(--af-border-strong)] hover:bg-[var(--af-surface-hover)]"
                      >
                        <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">{item.source_domain}</p>
                        <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">{item.title}</p>
                        <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">{sanitizeExternalDisplayText(item.summary)}</p>
                      </Link>
                    ))}
                  </div>
                ) : null}
                {dailyBrief.watchlist_changes?.length ? (
                  <div className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">监控变化</p>
                    <div className="mt-2 space-y-2">
                      {dailyBrief.watchlist_changes.slice(0, 2).map((change) => (
                        <div key={change.id} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                          <p className="text-sm text-[var(--af-text-secondary)]">{sanitizeExternalDisplayText(change.summary)}</p>
                          <p className="mt-1 text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">
                            {change.change_type} · {change.severity}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : (
              <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">当前还没有今日摘要，可先刷新一次。</p>
            )}
            {dailyBriefError ? <p className="mt-3 text-sm text-[var(--af-danger)]">{dailyBriefError}</p> : null}
          </section>

          <section className="af-glass rounded-[30px] p-5">
            <p className="af-kicker">{t("research.centerFilterTitle", "视图筛选")}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {filterMeta.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setFilter(item.key)}
                  className={segmentButtonClass(filter === item.key)}
                >
                  {item.label} · {item.count}
                </button>
              ))}
            </div>

            <div className="mt-4 space-y-3">
              <div className="flex items-center gap-2 rounded-[20px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 shadow-[var(--af-shadow-soft)]">
                <input
                  value={queryDraft}
                  onChange={(event) => setQueryDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      handleSearchSubmit();
                    }
                  }}
                  placeholder={t("research.centerSearchPlaceholder", "搜索关键词、甲方、预算、投标...")}
                  className="min-w-0 flex-1 bg-transparent text-sm text-[var(--af-text-secondary)] outline-none placeholder:text-[var(--af-text-tertiary)]"
                />
                <button type="button" onClick={handleSearchSubmit} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                  {t("research.centerSearchSubmit", "搜索")}
                </button>
              </div>

              <button
                type="button"
                onClick={() => setFocusOnly((value) => !value)}
                className={`af-btn w-full justify-center border px-4 py-2 ${focusOnly ? "af-btn-primary" : "af-btn-secondary"}`}
              >
                {focusOnly
                  ? t("research.centerFocusOnlyOn", "仅看 Focus 参考")
                  : t("research.centerFocusOnlyOff", "包含全部")}
              </button>
            </div>

            <div className="mt-4 space-y-3">
              <div>
                <p className="text-sm text-[var(--af-text-tertiary)]">检索视图</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {retrievalLensMeta.map((item) => (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => setRetrievalLens(item.key)}
                      className={segmentButtonClass(retrievalLens === item.key)}
                    >
                      {item.label} · {item.count}
                    </button>
                  ))}
                </div>
                <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">
                  {(retrievalLensMeta.find((item) => item.key === retrievalLens) || retrievalLensMeta[0]).desc}
                </p>
              </div>

              <div>
                <p className="text-sm text-[var(--af-text-tertiary)]">{t("research.centerPerspectiveLabel", "业务视角")}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {perspectiveMeta.map((item) => (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => setPerspective(item.key)}
                      className={segmentButtonClass(perspective === item.key)}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
                <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">{activePerspective.desc}</p>
              </div>

              <label className="space-y-2 text-sm text-[var(--af-text-tertiary)]">
                <span>{t("research.centerRegionLabel", "区域")}</span>
                <select
                  value={regionFilter}
                  onChange={(event) => setRegionFilter(event.target.value)}
                  className="af-input w-full"
                >
                  {regionOptions.map((option, index) => (
                    <option key={option} value={index === 0 ? "" : option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-2 text-sm text-[var(--af-text-tertiary)]">
                <span>{t("research.centerIndustryLabel", "行业")}</span>
                <select
                  value={industryFilter}
                  onChange={(event) => setIndustryFilter(event.target.value)}
                  className="af-input w-full"
                >
                  {industryOptions.map((option, index) => (
                    <option key={option} value={index === 0 ? "" : option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-2 text-sm text-[var(--af-text-tertiary)]">
                <span>{t("research.centerActionTypeLabel", "动作类型")}</span>
                <select
                  value={actionTypeFilter}
                  onChange={(event) => setActionTypeFilter(event.target.value)}
                  className="af-input w-full"
                >
                  {actionTypeOptions.map((option, index) => (
                    <option key={option} value={index === 0 ? "" : option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="mt-4 rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-4">
              <p className="text-xs font-medium uppercase tracking-[0.2em] text-[var(--af-text-tertiary)]">
                {t("research.centerFilteredResult", "当前视图")}
              </p>
              <p className="mt-3 text-3xl font-semibold tracking-[-0.05em] text-[var(--af-text-primary)]">{visibleItems.length}</p>
              <p className="mt-1 text-sm text-[var(--af-text-tertiary)]">
                {t("research.centerFilteredResultHint", "张匹配卡片，适合继续整理为方案或行动卡。")}
              </p>
              <button type="button" onClick={clearFacetFilters} className="mt-4 text-sm font-medium text-[var(--af-text-secondary)] underline decoration-[var(--af-border-strong)] underline-offset-4">
                {t("research.centerClearFilters", "清空筛选")}
              </button>
            </div>
          </section>
    </>
  );
}
