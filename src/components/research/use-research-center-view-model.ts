"use client";

import { useMemo } from "react";
import {
  buildFacetOptions,
  getResearchPerspectiveScore,
  type ResearchPerspective,
} from "@/lib/research-facets";
import {
  matchesRetrievalLens,
  sortEntries,
  type ResearchCenterEntry,
  type ResearchFilter,
  type ResearchRetrievalLens,
} from "@/components/research/research-center-utils";

type TranslationFn = (key: string, fallback: string) => string;

type UseResearchCenterViewModelParams = {
  t: TranslationFn;
  reports: ResearchCenterEntry[];
  actions: ResearchCenterEntry[];
  filter: ResearchFilter;
  retrievalLens: ResearchRetrievalLens;
  perspective: ResearchPerspective;
  focusOnly: boolean;
  query: string;
  regionFilter: string;
  industryFilter: string;
  actionTypeFilter: string;
};

export function useResearchCenterViewModel({
  t,
  reports,
  actions,
  filter,
  retrievalLens,
  perspective,
  focusOnly,
  query,
  regionFilter,
  industryFilter,
  actionTypeFilter,
}: UseResearchCenterViewModelParams) {
  const allItems = useMemo(() => sortEntries([...reports, ...actions]), [actions, reports]);

  const regionOptions = useMemo(
    () => buildFacetOptions(allItems.map((item) => item.region_label), t("research.centerRegionAll", "全部区域")),
    [allItems, t],
  );
  const industryOptions = useMemo(
    () =>
      buildFacetOptions(
        allItems.map((item) => item.industry_label),
        t("research.centerIndustryAll", "全部行业"),
      ),
    [allItems, t],
  );
  const actionTypeOptions = useMemo(
    () =>
      buildFacetOptions(
        actions.map((item) => item.action_type_label),
        t("research.centerActionTypeAll", "全部动作类型"),
      ),
    [actions, t],
  );

  const visibleItems = useMemo(() => {
    let baseItems: ResearchCenterEntry[] = allItems;
    if (filter === "reports") baseItems = reports;
    if (filter === "actions") baseItems = actions;
    return baseItems
      .filter((item) => {
        if (regionFilter && item.region_label !== regionFilter) return false;
        if (industryFilter && item.industry_label !== industryFilter) return false;
        if (actionTypeFilter) {
          if (item.source_domain !== "research.action_card") return false;
          if (item.action_type_label !== actionTypeFilter) return false;
        }
        if (!matchesRetrievalLens(item, retrievalLens)) return false;
        return getResearchPerspectiveScore(item, perspective) > 0;
      })
      .sort((left, right) => {
        const scoreGap = getResearchPerspectiveScore(right, perspective) - getResearchPerspectiveScore(left, perspective);
        if (scoreGap !== 0) return scoreGap;
        return new Date(right.updated_at || right.created_at).getTime() - new Date(left.updated_at || left.created_at).getTime();
      });
  }, [actionTypeFilter, actions, allItems, filter, industryFilter, perspective, regionFilter, reports, retrievalLens]);

  const filterMeta = useMemo(
    () => [
      { key: "all" as const, label: t("research.centerFilterAll", "全部"), count: reports.length + actions.length },
      { key: "reports" as const, label: t("research.centerFilterReports", "研报"), count: reports.length },
      { key: "actions" as const, label: t("research.centerFilterActions", "行动卡"), count: actions.length },
    ],
    [actions.length, reports.length, t],
  );

  const perspectiveMeta = useMemo<Array<{ key: ResearchPerspective; label: string; desc: string }>>(
    () => [
      {
        key: "all",
        label: t("research.centerViewAll", "全部视角"),
        desc: t("research.centerViewAllDesc", "综合查看全部研报与行动卡"),
      },
      {
        key: "regional",
        label: t("research.centerViewRegional", "区域情报"),
        desc: t("research.centerViewRegionalDesc", "优先看地区、区域和分层推进线索"),
      },
      {
        key: "client_followup",
        label: t("research.centerViewClient", "甲方跟进"),
        desc: t("research.centerViewClientDesc", "聚焦甲方角色、拜访和销售推进"),
      },
      {
        key: "bidding",
        label: t("research.centerViewBidding", "投标排期"),
        desc: t("research.centerViewBiddingDesc", "集中看预算、采购、中标和项目分期"),
      },
      {
        key: "ecosystem",
        label: t("research.centerViewEcosystem", "生态合作"),
        desc: t("research.centerViewEcosystemDesc", "查看伙伴、渠道、联合交付与竞合"),
      },
    ],
    [t],
  );

  const activePerspective = perspectiveMeta.find((item) => item.key === perspective) || perspectiveMeta[0];

  const overviewStats = useMemo(
    () => [
      {
        label: t("research.centerMetricAll", "总卡片"),
        value: String(allItems.length),
        tone: "text-slate-900",
        detail: "当前工作区中的全部研报与行动卡",
      },
      {
        label: t("research.centerMetricReports", "研报"),
        value: String(reports.length),
        tone: "text-sky-700",
        detail: "已沉淀的关键词研究与专题研报",
      },
      {
        label: t("research.centerMetricActions", "行动卡"),
        value: String(actions.length),
        tone: "text-amber-700",
        detail: "可以直接下发的推进建议与动作包",
      },
      {
        label: t("research.centerMetricFocus", "Focus 参考"),
        value: String(allItems.filter((item) => item.is_focus_reference).length),
        tone: "text-emerald-700",
        detail: "已加入 Focus 的研究素材",
      },
    ],
    [actions.length, allItems, reports.length, t],
  );

  const retrievalLensMeta = useMemo<Array<{ key: ResearchRetrievalLens; label: string; desc: string; count: number }>>(
    () => [
      {
        key: "all",
        label: "全部",
        desc: "综合查看全部研报与行动卡",
        count: allItems.length,
      },
      {
        key: "high_trust",
        label: "高可信",
        desc: "优先看强证据和较稳的检索结果",
        count: allItems.filter((item) => matchesRetrievalLens(item, "high_trust")).length,
      },
      {
        key: "official_rich",
        label: "官方源强",
        desc: "优先看官方来源更充分的条目",
        count: allItems.filter((item) => matchesRetrievalLens(item, "official_rich")).length,
      },
      {
        key: "action_ready",
        label: "可推进",
        desc: "更接近可推进账户与机会信号",
        count: allItems.filter((item) => matchesRetrievalLens(item, "action_ready")).length,
      },
      {
        key: "needs_review",
        label: "待复核",
        desc: "优先处理待复核和依据较弱的条目",
        count: allItems.filter((item) => matchesRetrievalLens(item, "needs_review")).length,
      },
    ],
    [allItems],
  );

  const activeFilterLabels = useMemo(
    () =>
      [
        regionFilter ? `${t("research.centerRegionLabel", "区域")} · ${regionFilter}` : "",
        industryFilter ? `${t("research.centerIndustryLabel", "行业")} · ${industryFilter}` : "",
        actionTypeFilter ? `${t("research.centerActionTypeLabel", "动作类型")} · ${actionTypeFilter}` : "",
        focusOnly ? t("research.centerFocusOnlyOn", "仅看 Focus 参考") : "",
        query ? `${t("common.searchPlaceholder", "搜索")} · ${query}` : "",
        retrievalLens !== "all"
          ? `检索视图 · ${(retrievalLensMeta.find((item) => item.key === retrievalLens) || retrievalLensMeta[0]).label}`
          : "",
        perspective !== "all" ? `${t("research.centerPerspectiveLabel", "业务视角")} · ${activePerspective.label}` : "",
      ].filter(Boolean),
    [
      actionTypeFilter,
      activePerspective.label,
      focusOnly,
      industryFilter,
      perspective,
      query,
      regionFilter,
      retrievalLens,
      retrievalLensMeta,
      t,
    ],
  );

  return {
    allItems,
    regionOptions,
    industryOptions,
    actionTypeOptions,
    visibleItems,
    filterMeta,
    perspectiveMeta,
    activePerspective,
    overviewStats,
    retrievalLensMeta,
    activeFilterLabels,
  };
}
