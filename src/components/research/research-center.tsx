"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ApiKnowledgeEntry,
  ApiResearchSavedView,
  ApiResearchSourceSettings,
  ApiResearchTrackingTopic,
  ApiResearchWatchlist,
  createResearchWatchlist,
  deleteResearchTrackingTopic,
  deleteResearchView,
  listResearchWatchlists,
  getResearchSourceSettings,
  getResearchWorkspace,
  listKnowledgeEntries,
  refreshResearchWatchlist,
  refreshResearchTrackingTopic,
  saveResearchTrackingTopic,
  saveResearchView,
  updateResearchSourceSettings,
} from "@/lib/api";
import {
  buildFacetOptions,
  getResearchFacets,
  getResearchPerspectiveScore,
  type ResearchPerspective,
} from "@/lib/research-facets";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { ResearchConsolePanel } from "@/components/research/research-console-panel";
import { AppIcon } from "@/components/ui/app-icon";

type ResearchFilter = "all" | "reports" | "actions";

type ResearchCenterActionCard = {
  title: string;
  target_persona?: string;
  execution_window?: string;
  deliverable?: string;
  recommended_steps?: string[];
};

function sortEntries<T extends ApiKnowledgeEntry>(items: T[]): T[] {
  return [...items].sort((left, right) => {
    const leftTime = new Date(left.updated_at || left.created_at).getTime();
    const rightTime = new Date(right.updated_at || right.created_at).getTime();
    return rightTime - leftTime;
  });
}

function normalizeTextList(values: unknown): string[] {
  return Array.isArray(values)
    ? values.map((value) => String(value || "").trim()).filter(Boolean)
    : [];
}

function parseActionPhases(steps: string[] | undefined) {
  return (Array.isArray(steps) ? steps : [])
    .map((step) => String(step || "").trim())
    .filter(Boolean)
    .map((step) => {
      const match = step.match(/^(短期|中期|长期|Short term|Mid term|Long term)(?:（([^）]+)）|\(([^)]+)\))?[:：]\s*(.+)$/i);
      if (!match) {
        return {
          label: "关键动作",
          horizon: "",
          content: step,
        };
      }
      return {
        label: match[1],
        horizon: match[2] || match[3] || "",
        content: match[4],
      };
    })
    .slice(0, 3);
}

function getResearchActionCards(entry: ApiKnowledgeEntry): ResearchCenterActionCard[] {
  const payload = (entry.metadata_payload || {}) as {
    action_cards?: ResearchCenterActionCard[];
  };
  return Array.isArray(payload.action_cards)
    ? payload.action_cards
        .map((card) => ({
          title: String(card.title || "").trim(),
          target_persona: String(card.target_persona || "").trim(),
          execution_window: String(card.execution_window || "").trim(),
          deliverable: String(card.deliverable || "").trim(),
          recommended_steps: normalizeTextList(card.recommended_steps),
        }))
        .filter((card) => card.title)
        .slice(0, 2)
    : [];
}

function buildPreview(entry: ApiKnowledgeEntry): string {
  const report = (entry.metadata_payload as { report?: { executive_summary?: string } } | null)?.report;
  const summary = report?.executive_summary || entry.content || "";
  return summary.length > 110 ? `${summary.slice(0, 109).trim()}…` : summary;
}

function getActionType(entry: ApiKnowledgeEntry): string {
  const payload = entry.metadata_payload as { card?: { action_type?: string } } | null;
  return payload?.card?.action_type || "";
}

function getResearchKeyword(entry: ApiKnowledgeEntry): string {
  const payload = entry.metadata_payload as
    | {
        report?: { keyword?: string };
        keyword?: string;
      }
    | null;
  return payload?.report?.keyword || payload?.keyword || "";
}

function getResearchSourceCount(entry: ApiKnowledgeEntry): number {
  const payload = entry.metadata_payload as
    | {
        report?: { source_count?: number };
      }
    | null;
  return Number(payload?.report?.source_count || 0);
}

function getResearchReportMeta(
  entry: ApiKnowledgeEntry,
): { evidenceDensity: string; sourceQuality: string } {
  const payload = entry.metadata_payload as
    | {
        report?: { evidence_density?: string; source_quality?: string };
      }
    | null;
  return {
    evidenceDensity: String(payload?.report?.evidence_density || "low"),
    sourceQuality: String(payload?.report?.source_quality || "low"),
  };
}

function getResearchSourceDiagnostics(entry: ApiKnowledgeEntry): {
  topicAnchors: string[];
  matchedThemes: string[];
  scopeRegions: string[];
  scopeIndustries: string[];
  scopeClients: string[];
  filteredOldSourceCount: number;
  filteredRegionConflictCount: number;
  strictTopicSourceCount: number;
  retrievalQuality: "low" | "medium" | "high";
  evidenceMode: "strong" | "provisional" | "fallback";
  strictMatchRatio: number;
  officialSourceRatio: number;
  uniqueDomainCount: number;
  normalizedEntityCount: number;
  normalizedTargetCount: number;
  normalizedCompetitorCount: number;
  normalizedPartnerCount: number;
  expansionTriggered: boolean;
  correctiveTriggered: boolean;
  candidateProfileCompanies: string[];
  candidateProfileHitCount: number;
  candidateProfileOfficialHitCount: number;
  candidateProfileSourceLabels: string[];
} {
  const payload = entry.metadata_payload as
    | {
        report?: {
          source_diagnostics?: {
            topic_anchor_terms?: string[];
            matched_theme_labels?: string[];
            filtered_old_source_count?: number;
            filtered_region_conflict_count?: number;
            strict_topic_source_count?: number;
            retrieval_quality?: "low" | "medium" | "high";
            evidence_mode?: "strong" | "provisional" | "fallback";
            strict_match_ratio?: number;
            official_source_ratio?: number;
            unique_domain_count?: number;
            normalized_entity_count?: number;
            normalized_target_count?: number;
            normalized_competitor_count?: number;
            normalized_partner_count?: number;
            expansion_triggered?: boolean;
            corrective_triggered?: boolean;
            candidate_profile_companies?: string[];
            candidate_profile_hit_count?: number;
            candidate_profile_official_hit_count?: number;
            candidate_profile_source_labels?: string[];
          };
        };
      }
    | null;
  const diagnostics = payload?.report?.source_diagnostics;
  return {
    topicAnchors: normalizeTextList(diagnostics?.topic_anchor_terms).slice(0, 3),
    matchedThemes: normalizeTextList(diagnostics?.matched_theme_labels).slice(0, 3),
    scopeRegions: normalizeTextList((diagnostics as { scope_regions?: string[] } | undefined)?.scope_regions).slice(0, 2),
    scopeIndustries: normalizeTextList((diagnostics as { scope_industries?: string[] } | undefined)?.scope_industries).slice(0, 2),
    scopeClients: normalizeTextList((diagnostics as { scope_clients?: string[] } | undefined)?.scope_clients).slice(0, 2),
    filteredOldSourceCount: Number(diagnostics?.filtered_old_source_count || 0),
    filteredRegionConflictCount: Number((diagnostics as { filtered_region_conflict_count?: number } | undefined)?.filtered_region_conflict_count || 0),
    strictTopicSourceCount: Number(diagnostics?.strict_topic_source_count || 0),
    retrievalQuality: (String(diagnostics?.retrieval_quality || "low") as "low" | "medium" | "high"),
    evidenceMode: (String((diagnostics as { evidence_mode?: string } | undefined)?.evidence_mode || "fallback") as "strong" | "provisional" | "fallback"),
    strictMatchRatio: Number(diagnostics?.strict_match_ratio || 0),
    officialSourceRatio: Number(diagnostics?.official_source_ratio || 0),
    uniqueDomainCount: Number(diagnostics?.unique_domain_count || 0),
    normalizedEntityCount: Number(diagnostics?.normalized_entity_count || 0),
    normalizedTargetCount: Number(diagnostics?.normalized_target_count || 0),
    normalizedCompetitorCount: Number(diagnostics?.normalized_competitor_count || 0),
    normalizedPartnerCount: Number(diagnostics?.normalized_partner_count || 0),
    expansionTriggered: Boolean(diagnostics?.expansion_triggered),
    correctiveTriggered: Boolean((diagnostics as { corrective_triggered?: boolean } | undefined)?.corrective_triggered),
    candidateProfileCompanies: normalizeTextList((diagnostics as { candidate_profile_companies?: string[] } | undefined)?.candidate_profile_companies).slice(0, 4),
    candidateProfileHitCount: Number((diagnostics as { candidate_profile_hit_count?: number } | undefined)?.candidate_profile_hit_count || 0),
    candidateProfileOfficialHitCount: Number((diagnostics as { candidate_profile_official_hit_count?: number } | undefined)?.candidate_profile_official_hit_count || 0),
    candidateProfileSourceLabels: normalizeTextList((diagnostics as { candidate_profile_source_labels?: string[] } | undefined)?.candidate_profile_source_labels).slice(0, 4),
  };
}

function classifyResearchSourceTier(source: { domain?: string | null; source_type?: string | null; source_tier?: string | null }) {
  const domain = String(source.domain || "").toLowerCase();
  const sourceType = String(source.source_type || "").toLowerCase();
  const sourceTier = String(source.source_tier || "").toLowerCase();
  if (sourceTier === "official" || sourceTier === "aggregate" || sourceTier === "media") return sourceTier;
  if (
    sourceType === "policy" ||
    sourceType === "procurement" ||
    sourceType === "filing" ||
    domain.includes("gov.cn") ||
    domain.includes("ggzy.gov.cn") ||
    domain.includes("cninfo.com.cn") ||
    domain.includes("sec.gov") ||
    domain.includes("hkexnews.hk")
  ) {
    return "official";
  }
  if (
    sourceType === "tender_feed" ||
    domain.includes("jianyu") ||
    domain.includes("cecbid") ||
    domain.includes("cebpubservice") ||
    domain.includes("china-cpp") ||
    domain.includes("chinabidding")
  ) {
    return "aggregate";
  }
  return "media";
}

function buildFallbackRankedPreview(
  entry: ApiKnowledgeEntry,
  role: "target" | "competitor" | "partner",
) {
  const valueLabel = (score: number) => {
    if (score >= 75) return "高价值";
    if (score >= 55) return "普通价值";
    return "低价值";
  };
  const payload = (entry.metadata_payload || {}) as {
    report?: {
      keyword?: string;
      research_focus?: string;
      source_count?: number;
      sources?: Array<{ title?: string; url?: string; snippet?: string; search_query?: string; source_label?: string | null; source_tier?: string | null; source_type?: string | null; domain?: string | null }>;
      pending_target_candidates?: Array<{ name?: string; score?: number; evidence_links?: Array<{ title?: string; url?: string; source_tier?: string | null }> }>;
      pending_competitor_candidates?: Array<{ name?: string; score?: number; evidence_links?: Array<{ title?: string; url?: string; source_tier?: string | null }> }>;
      pending_partner_candidates?: Array<{ name?: string; score?: number; evidence_links?: Array<{ title?: string; url?: string; source_tier?: string | null }> }>;
    };
  };
  const report = payload.report;
  if (!report) return [];
  const normalize = (items: Array<{ name?: string; score?: number; evidence_links?: Array<{ title?: string; url?: string; source_tier?: string | null }> }> | undefined) =>
    (items || []).slice(0, 3).map((item) => ({
      name: String(item?.name || "").trim(),
      score: Number(item?.score || 0),
      score_label: valueLabel(Number(item?.score || 0)),
      evidence_links: (item?.evidence_links || []).map((link) => ({
        title: link.title || link.url || "来源待确认",
        url: link.url || "",
        source_tier: classifyResearchSourceTier(link),
      })),
    })).filter((item) => item.name);
  const sourceMap = {
    target: normalize(report.pending_target_candidates),
    competitor: normalize(report.pending_competitor_candidates),
    partner: normalize(report.pending_partner_candidates),
  };
  return sourceMap[role] || [];
}

function getResearchRankedPreview(entry: ApiKnowledgeEntry) {
  const valueLabel = (score: number) => {
    if (score >= 75) return "高价值";
    if (score >= 55) return "普通价值";
    return "低价值";
  };
  const payload = (entry.metadata_payload || {}) as {
    report?: {
      top_target_accounts?: Array<{ name: string; score: number; evidence_links?: Array<{ title?: string; url?: string; source_tier?: string | null }> }>;
      top_competitors?: Array<{ name: string; score: number; evidence_links?: Array<{ title?: string; url?: string; source_tier?: string | null }> }>;
      top_ecosystem_partners?: Array<{ name: string; score: number; evidence_links?: Array<{ title?: string; url?: string; source_tier?: string | null }> }>;
      pending_target_candidates?: Array<{ name?: string; score?: number; evidence_links?: Array<{ title?: string; url?: string; source_tier?: string | null }> }>;
      pending_competitor_candidates?: Array<{ name?: string; score?: number; evidence_links?: Array<{ title?: string; url?: string; source_tier?: string | null }> }>;
      pending_partner_candidates?: Array<{ name?: string; score?: number; evidence_links?: Array<{ title?: string; url?: string; source_tier?: string | null }> }>;
    };
  };
  const report = payload.report;
  if (!report) return [];
  const normalize = (items: Array<{ name: string; score: number; evidence_links?: Array<{ title?: string; url?: string; source_tier?: string | null }> }> | undefined) =>
    (items || []).slice(0, 3).map((item) => ({
      name: item.name,
      score: item.score,
      score_label: valueLabel(Number(item.score || 0)),
      evidence_links: (item.evidence_links || []).map((link) => ({
        title: link.title || link.url || "来源待确认",
        url: link.url || "",
        source_tier: classifyResearchSourceTier(link),
      })),
    }));
  return [
    {
      key: "target",
      title: normalize(report.top_target_accounts).length ? "甲方" : "待补证甲方",
      items: normalize(report.top_target_accounts).length ? normalize(report.top_target_accounts) : buildFallbackRankedPreview(entry, "target"),
    },
    {
      key: "competitor",
      title: normalize(report.top_competitors).length ? "竞品" : "待补证竞品",
      items: normalize(report.top_competitors).length ? normalize(report.top_competitors) : buildFallbackRankedPreview(entry, "competitor"),
    },
    {
      key: "partner",
      title: normalize(report.top_ecosystem_partners).length ? "伙伴" : "待补证伙伴",
      items: normalize(report.top_ecosystem_partners).length ? normalize(report.top_ecosystem_partners) : buildFallbackRankedPreview(entry, "partner"),
    },
  ].filter((group) => group.items.length);
}

function qualityLabel(value: string) {
  if (value === "high") return "高";
  if (value === "medium") return "中";
  return "低";
}

function qualityTone(value: string) {
  if (value === "high") return "bg-emerald-100 text-emerald-700";
  if (value === "medium") return "bg-amber-100 text-amber-700";
  return "bg-slate-100 text-slate-500";
}

function trackingStatusLabel(value?: string | null) {
  if (value === "running") return "刷新中";
  if (value === "succeeded") return "刷新成功";
  if (value === "failed") return "刷新失败";
  return "待刷新";
}

function trackingStatusTone(value?: string | null) {
  if (value === "running") return "bg-sky-100 text-sky-700";
  if (value === "succeeded") return "bg-emerald-100 text-emerald-700";
  if (value === "failed") return "bg-rose-100 text-rose-700";
  return "bg-slate-100 text-slate-500";
}

type ResearchCenterEntry = ApiKnowledgeEntry & {
  region_label: string;
  industry_label: string;
  action_type_label: string;
};

function normalizeResearchEntry(entry: ApiKnowledgeEntry): ResearchCenterEntry {
  const facets = getResearchFacets(entry);
  return {
    ...entry,
    region_label: facets.region,
    industry_label: facets.industry,
    action_type_label: facets.actionType,
  };
}

function buildTopicWorkspaceHref(topicId: string) {
  return `/research/topics/${topicId}`;
}

export function ResearchCenter() {
  const { t } = useAppPreferences();
  const [filter, setFilter] = useState<ResearchFilter>("all");
  const [perspective, setPerspective] = useState<ResearchPerspective>("all");
  const [focusOnly, setFocusOnly] = useState(false);
  const [queryDraft, setQueryDraft] = useState("");
  const [query, setQuery] = useState("");
  const [regionFilter, setRegionFilter] = useState("");
  const [industryFilter, setIndustryFilter] = useState("");
  const [actionTypeFilter, setActionTypeFilter] = useState("");
  const [reports, setReports] = useState<ResearchCenterEntry[]>([]);
  const [actions, setActions] = useState<ResearchCenterEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sourceSettings, setSourceSettings] = useState<ApiResearchSourceSettings | null>(null);
  const [sourceSaving, setSourceSaving] = useState(false);
  const [savedViews, setSavedViews] = useState<ApiResearchSavedView[]>([]);
  const [trackingTopics, setTrackingTopics] = useState<ApiResearchTrackingTopic[]>([]);
  const [watchlists, setWatchlists] = useState<ApiResearchWatchlist[]>([]);
  const [workspaceSaving, setWorkspaceSaving] = useState(false);
  const [refreshingTopicId, setRefreshingTopicId] = useState<string>("");
  const [refreshingWatchlistId, setRefreshingWatchlistId] = useState<string>("");

  useEffect(() => {
    let active = true;
    getResearchSourceSettings()
      .then((res) => {
        if (!active) return;
        setSourceSettings(res);
      })
      .catch(() => {
        if (!active) return;
        setSourceSettings({
          enable_jianyu_tender_feed: true,
          enable_yuntoutiao_feed: true,
          enable_ggzy_feed: true,
          enable_cecbid_feed: true,
          enable_ccgp_feed: true,
          enable_gov_policy_feed: true,
          enable_local_ggzy_feed: true,
          enabled_source_labels: ["剑鱼标讯", "云头条", "全国公共资源交易平台", "中国招标投标网", "政府采购合规聚合", "中国政府网政策/讲话", "地方公共资源交易平台"],
          connector_statuses: [
            {
              key: "public_open_source_adapters",
              label: "公开招采与行业源适配器",
              status: "active",
              detail: "当前已接入公开招投标、政策讲话、行业媒体与聚合源；不绕过登录墙和付费墙。",
              requires_authorization: false,
            },
          ],
          updated_at: null,
        });
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    getResearchWorkspace()
      .then((res) => {
        if (!active) return;
        setSavedViews(res.saved_views || []);
        setTrackingTopics(res.tracking_topics || []);
      })
      .catch(() => {
        if (!active) return;
        setSavedViews([]);
        setTrackingTopics([]);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    listResearchWatchlists()
      .then((res) => {
        if (!active) return;
        setWatchlists(res || []);
      })
      .catch(() => {
        if (!active) return;
        setWatchlists([]);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    Promise.all([
      listKnowledgeEntries(40, {
        sourceDomain: "research.report",
        query: query || undefined,
        focusReferenceOnly: focusOnly,
      }),
      listKnowledgeEntries(60, {
        sourceDomain: "research.action_card",
        query: query || undefined,
        focusReferenceOnly: focusOnly,
      }),
    ])
      .then(([reportRes, actionRes]) => {
        if (!active) return;
        setReports(sortEntries((reportRes.items || []).map(normalizeResearchEntry)));
        setActions(sortEntries((actionRes.items || []).map(normalizeResearchEntry)));
      })
      .catch(() => {
        if (!active) return;
        setReports([]);
        setActions([]);
        setError(t("research.centerLoadFailed", "研报中心加载失败，请稍后重试"));
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [focusOnly, query, t]);

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
        return getResearchPerspectiveScore(item, perspective) > 0;
      })
      .sort((left, right) => {
        const scoreGap = getResearchPerspectiveScore(right, perspective) - getResearchPerspectiveScore(left, perspective);
        if (scoreGap !== 0) return scoreGap;
        return new Date(right.updated_at || right.created_at).getTime() - new Date(left.updated_at || left.created_at).getTime();
      });
  }, [actionTypeFilter, allItems, filter, industryFilter, perspective, regionFilter, reports, actions]);

  const filterMeta = [
    { key: "all" as const, label: t("research.centerFilterAll", "全部"), count: reports.length + actions.length },
    { key: "reports" as const, label: t("research.centerFilterReports", "研报"), count: reports.length },
    { key: "actions" as const, label: t("research.centerFilterActions", "行动卡"), count: actions.length },
  ];

  const perspectiveMeta: Array<{ key: ResearchPerspective; label: string; desc: string }> = [
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
  ];

  const activePerspective = perspectiveMeta.find((item) => item.key === perspective) || perspectiveMeta[0];

  const activeFilterLabels = [
    regionFilter ? `${t("research.centerRegionLabel", "区域")} · ${regionFilter}` : "",
    industryFilter ? `${t("research.centerIndustryLabel", "行业")} · ${industryFilter}` : "",
    actionTypeFilter ? `${t("research.centerActionTypeLabel", "动作类型")} · ${actionTypeFilter}` : "",
    focusOnly ? t("research.centerFocusOnlyOn", "仅看 Focus 参考") : "",
    query ? `${t("common.searchPlaceholder", "搜索")} · ${query}` : "",
    perspective !== "all" ? `${t("research.centerPerspectiveLabel", "业务视角")} · ${activePerspective.label}` : "",
  ].filter(Boolean);

  const overviewStats = [
    {
      label: t("research.centerMetricAll", "总卡片"),
      value: String(allItems.length),
      tone: "text-slate-900",
    },
    {
      label: t("research.centerMetricReports", "研报"),
      value: String(reports.length),
      tone: "text-sky-700",
    },
    {
      label: t("research.centerMetricActions", "行动卡"),
      value: String(actions.length),
      tone: "text-amber-700",
    },
    {
      label: t("research.centerMetricFocus", "Focus 参考"),
      value: String(allItems.filter((item) => item.is_focus_reference).length),
      tone: "text-emerald-700",
    },
  ];

  const handleSearchSubmit = () => {
    setQuery(queryDraft.trim());
  };

  const clearFacetFilters = () => {
    setRegionFilter("");
    setIndustryFilter("");
    setActionTypeFilter("");
    setFocusOnly(false);
    setQuery("");
    setQueryDraft("");
    setPerspective("all");
  };

  const buildCompareHref = (overrides?: {
    query?: string;
    region?: string;
    industry?: string;
  }) => {
    const params = new URLSearchParams();
    const compareQuery = (overrides?.query ?? query).trim();
    const compareRegion = overrides?.region ?? regionFilter;
    const compareIndustry = overrides?.industry ?? industryFilter;
    if (compareQuery) params.set("query", compareQuery);
    if (compareRegion) params.set("region", compareRegion);
    if (compareIndustry) params.set("industry", compareIndustry);
    const queryString = params.toString();
    return queryString ? `/research/compare?${queryString}` : "/research/compare";
  };

  const applySavedView = (view: ApiResearchSavedView) => {
    setFilter(view.filter_mode);
    setPerspective(view.perspective);
    setRegionFilter(view.region_filter || "");
    setIndustryFilter(view.industry_filter || "");
    setActionTypeFilter(view.action_type_filter || "");
    setFocusOnly(!!view.focus_only);
    setQuery(view.query || "");
    setQueryDraft(view.query || "");
  };

  const handleSaveCurrentView = async () => {
    const trimmedQuery = query.trim();
    const nameSeed = trimmedQuery || activePerspective.label || t("research.centerViewAll", "全部视角");
    setWorkspaceSaving(true);
    try {
      const saved = await saveResearchView({
        name: `${nameSeed} · ${new Date().toLocaleDateString()}`,
        query: trimmedQuery,
        filter_mode: filter,
        perspective,
        region_filter: regionFilter,
        industry_filter: industryFilter,
        action_type_filter: actionTypeFilter,
        focus_only: focusOnly,
      });
      setSavedViews((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
    } finally {
      setWorkspaceSaving(false);
    }
  };

  const handleDeleteSavedView = async (viewId: string) => {
    setWorkspaceSaving(true);
    try {
      await deleteResearchView(viewId);
      setSavedViews((current) => current.filter((item) => item.id !== viewId));
    } finally {
      setWorkspaceSaving(false);
    }
  };

  const handleSaveTrackingTopic = async () => {
    const keyword = query.trim() || getResearchKeyword(visibleItems[0] || reports[0] || actions[0] || ({} as ApiKnowledgeEntry));
    if (!keyword) return;
    const focusText = activeFilterLabels.join(" / ");
    setWorkspaceSaving(true);
    try {
      const saved = await saveResearchTrackingTopic({
        name: `${keyword} 跟踪`,
        keyword,
        research_focus: focusText,
        perspective,
        region_filter: regionFilter,
        industry_filter: industryFilter,
        notes: visibleItems[0]?.title || "",
      });
      setTrackingTopics((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
    } finally {
      setWorkspaceSaving(false);
    }
  };

  const applyTrackingTopic = (topic: ApiResearchTrackingTopic) => {
    setPerspective(topic.perspective);
    setRegionFilter(topic.region_filter || "");
    setIndustryFilter(topic.industry_filter || "");
    setQuery(topic.keyword || "");
    setQueryDraft(topic.keyword || "");
    setActionTypeFilter("");
    setFocusOnly(false);
  };

  const handleDeleteTrackingTopic = async (topicId: string) => {
    setWorkspaceSaving(true);
    try {
      await deleteResearchTrackingTopic(topicId);
      setTrackingTopics((current) => current.filter((item) => item.id !== topicId));
    } finally {
      setWorkspaceSaving(false);
    }
  };

  const handleRefreshTrackingTopic = async (topicId: string) => {
    setRefreshingTopicId(topicId);
    setTrackingTopics((current) =>
      current.map((item) =>
        item.id === topicId
          ? {
              ...item,
              last_refresh_status: "running",
              last_refresh_error: "",
              last_refresh_note: "正在刷新专题研报并补充新增情报",
            }
          : item,
      ),
    );
    try {
      const result = await refreshResearchTrackingTopic(topicId, {
        output_language: "zh-CN",
        include_wechat: true,
        max_sources: 12,
        save_to_knowledge: true,
      });
      setTrackingTopics((current) =>
        current.map((item) => (item.id === topicId ? result.topic : item)),
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "专题刷新失败";
      setTrackingTopics((current) =>
        current.map((item) =>
          item.id === topicId
            ? {
                ...item,
                last_refresh_status: "failed",
                last_refresh_error: message,
                last_refresh_note: "专题刷新失败，请检查当前关键词公开源与模型链路",
              }
            : item,
        ),
      );
    } finally {
      setRefreshingTopicId("");
    }
  };

  const handleCreateWatchlist = async (topic: ApiResearchTrackingTopic) => {
    setWorkspaceSaving(true);
    try {
      const saved = await createResearchWatchlist({
        name: `${topic.name} Watchlist`,
        watch_type: "topic",
        query: topic.keyword,
        tracking_topic_id: topic.id,
        research_focus: topic.research_focus,
        perspective: topic.perspective,
        region_filter: topic.region_filter,
        industry_filter: topic.industry_filter,
        alert_level: "medium",
        schedule: "manual",
      });
      setWatchlists((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
    } finally {
      setWorkspaceSaving(false);
    }
  };

  const handleRefreshWatchlist = async (watchlistId: string) => {
    setRefreshingWatchlistId(watchlistId);
    try {
      const result = await refreshResearchWatchlist(watchlistId, {
        output_language: "zh-CN",
        include_wechat: true,
        max_sources: 12,
        save_to_knowledge: true,
      });
      setWatchlists((current) =>
        current.map((item) => (item.id === watchlistId ? result.watchlist : item)),
      );
      setTrackingTopics((current) =>
        current.map((item) => (item.id === result.topic.id ? result.topic : item)),
      );
    } finally {
      setRefreshingWatchlistId("");
    }
  };

  const toggleResearchSource = async (
    key:
      | "enable_jianyu_tender_feed"
      | "enable_yuntoutiao_feed"
      | "enable_ggzy_feed"
      | "enable_cecbid_feed"
      | "enable_ccgp_feed"
      | "enable_gov_policy_feed"
      | "enable_local_ggzy_feed",
  ) => {
    if (!sourceSettings || sourceSaving) return;
    const nextPayload = {
      enable_jianyu_tender_feed:
        key === "enable_jianyu_tender_feed"
          ? !sourceSettings.enable_jianyu_tender_feed
          : sourceSettings.enable_jianyu_tender_feed,
      enable_yuntoutiao_feed:
        key === "enable_yuntoutiao_feed"
          ? !sourceSettings.enable_yuntoutiao_feed
          : sourceSettings.enable_yuntoutiao_feed,
      enable_ggzy_feed:
        key === "enable_ggzy_feed"
          ? !sourceSettings.enable_ggzy_feed
          : sourceSettings.enable_ggzy_feed,
      enable_cecbid_feed:
        key === "enable_cecbid_feed"
          ? !sourceSettings.enable_cecbid_feed
          : sourceSettings.enable_cecbid_feed,
      enable_ccgp_feed:
        key === "enable_ccgp_feed"
          ? !sourceSettings.enable_ccgp_feed
          : sourceSettings.enable_ccgp_feed,
      enable_gov_policy_feed:
        key === "enable_gov_policy_feed"
          ? !sourceSettings.enable_gov_policy_feed
          : sourceSettings.enable_gov_policy_feed,
      enable_local_ggzy_feed:
        key === "enable_local_ggzy_feed"
          ? !sourceSettings.enable_local_ggzy_feed
          : sourceSettings.enable_local_ggzy_feed,
    };
    setSourceSaving(true);
    try {
      const next = await updateResearchSourceSettings(nextPayload);
      setSourceSettings(next);
    } finally {
      setSourceSaving(false);
    }
  };

  return (
    <div className="space-y-5">
      <section className="af-glass rounded-[34px] p-5 md:p-7">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div className="max-w-3xl">
            <p className="af-kicker">{t("research.centerKicker", "Research Center")}</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-slate-900 md:text-[2rem]">
              {t("research.centerTitle", "关键词研报与行动卡")}
            </h2>
            <p className="mt-3 text-sm leading-6 text-slate-500 md:text-[15px]">
              {t(
                "research.centerDesc",
                "统一查看保存过的行业研报、行动卡和 Focus 参考，快速回到方案设计、销售推进与投标规划。",
              )}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="af-glass-orb-btn inline-flex h-11 items-center gap-2 rounded-full px-4 text-sm font-medium text-slate-700">
              <AppIcon name="source" className="h-4 w-4" />
              <span>{t("research.centerSourceToggle", "公开源")}</span>
              <span className="rounded-full bg-white/70 px-2 py-0.5 text-[11px] text-slate-500">
                {sourceSettings?.enabled_source_labels?.length || 0}
              </span>
            </div>
            <Link href={buildCompareHref()} className="af-btn af-btn-secondary border px-4 py-2">
              {t("research.centerOpenCompare", "打开对比矩阵")}
            </Link>
            <Link href="/inbox" className="af-btn af-btn-secondary border px-4 py-2">
              {t("research.centerBackToInbox", "返回解决方案智囊")}
            </Link>
          </div>
        </div>

        <div className="mt-5 rounded-[28px] border border-white/70 bg-white/72 p-4 shadow-[0_18px_45px_rgba(15,23,42,0.08)] backdrop-blur-xl">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="max-w-2xl">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                {t("research.centerSourcePanelKicker", "Research Sources")}
              </p>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {t(
                  "research.centerSourcePanelDesc",
                  "将公开招投标与行业媒体流并入研报线索池。当前仅抓取公开页面，不绕过登录或付费墙。",
                )}
              </p>
            </div>
            <div className="rounded-full border border-white/70 bg-white/70 px-3 py-1 text-xs font-medium text-slate-500">
              {t("research.centerSourceActive", "当前开启")} · {sourceSettings?.enabled_source_labels?.join(" / ") || t("research.centerSourceNone", "无")}
            </div>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {[
              {
                key: "enable_jianyu_tender_feed" as const,
                title: t("research.centerSourceJianyu", "剑鱼标讯"),
                desc: t(
                  "research.centerSourceJianyuDesc",
                  "补充公开招标公告、中标成交、采购意向与项目分包线索。",
                ),
                enabled: !!sourceSettings?.enable_jianyu_tender_feed,
              },
              {
                key: "enable_yuntoutiao_feed" as const,
                title: t("research.centerSourceYuntoutiao", "云头条"),
                desc: t(
                  "research.centerSourceYuntoutiaoDesc",
                  "补充云计算、AI、产业竞争和技术商业化动态解读。",
                ),
                enabled: !!sourceSettings?.enable_yuntoutiao_feed,
              },
              {
                key: "enable_ggzy_feed" as const,
                title: t("research.centerSourceGgzy", "全国公共资源交易平台"),
                desc: t(
                  "research.centerSourceGgzyDesc",
                  "补充工程建设、政府采购、成交公示等全国公共资源交易公告。",
                ),
                enabled: !!sourceSettings?.enable_ggzy_feed,
              },
              {
                key: "enable_cecbid_feed" as const,
                title: t("research.centerSourceCecbid", "中国招标投标网"),
                desc: t(
                  "research.centerSourceCecbidDesc",
                  "补充招标、结果、资讯和招标前信息公示等公开招采流。",
                ),
                enabled: !!sourceSettings?.enable_cecbid_feed,
              },
              {
                key: "enable_ccgp_feed" as const,
                title: t("research.centerSourceCcgp", "政府采购合规聚合"),
                desc: t(
                  "research.centerSourceCcgpDesc",
                  "以公开、合规、稳定的采购聚合源替代直抓政府采购网，补充采购人、预算和中标线索。",
                ),
                enabled: !!sourceSettings?.enable_ccgp_feed,
              },
              {
                key: "enable_gov_policy_feed" as const,
                title: t("research.centerSourceGovPolicy", "中国政府网政策/讲话"),
                desc: t(
                  "research.centerSourceGovPolicyDesc",
                  "补充政府工作报告、政策文件、领导讲话与战略规划等官方信号。",
                ),
                enabled: !!sourceSettings?.enable_gov_policy_feed,
              },
              {
                key: "enable_local_ggzy_feed" as const,
                title: t("research.centerSourceLocalGgzy", "地方公共资源交易平台"),
                desc: t(
                  "research.centerSourceLocalGgzyDesc",
                  "按区域定向补充省市公共资源交易平台与地方政府采购平台公开公告。",
                ),
                enabled: !!sourceSettings?.enable_local_ggzy_feed,
              },
            ].map((source) => (
              <button
                key={source.key}
                type="button"
                onClick={() => void toggleResearchSource(source.key)}
                className={`rounded-[24px] border px-4 py-4 text-left transition ${
                  source.enabled
                    ? "border-sky-200 bg-sky-50/75 shadow-[0_14px_35px_rgba(56,189,248,0.14)]"
                    : "border-white/70 bg-white/72"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{source.title}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {source.enabled
                        ? t("research.centerSourceEnabled", "已开启")
                        : t("research.centerSourceDisabled", "已关闭")}
                    </p>
                  </div>
                  <span
                    className={`inline-flex h-8 min-w-14 items-center rounded-full px-1 ${
                      source.enabled ? "bg-sky-500/90" : "bg-slate-300/90"
                    }`}
                  >
                    <span
                      className={`h-6 w-6 rounded-full bg-white shadow transition ${
                        source.enabled ? "translate-x-6" : "translate-x-0"
                      }`}
                    />
                  </span>
                </div>
                <p className="mt-3 text-sm leading-6 text-slate-600">{source.desc}</p>
              </button>
            ))}
          </div>
          {sourceSettings?.connector_statuses?.length ? (
            <div className="mt-4 rounded-[24px] border border-white/70 bg-white/68 p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                {t("research.centerConnectorStatus", "授权/接入状态")}
              </p>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                {sourceSettings.connector_statuses.map((status) => (
                  <div key={status.key} className="rounded-[18px] border border-slate-200/80 bg-slate-50/75 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-slate-900">{status.label}</p>
                      <span
                        className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${
                          status.status === "active"
                            ? "bg-emerald-100 text-emerald-700"
                            : status.status === "authorization_required"
                              ? "bg-amber-100 text-amber-700"
                              : "bg-slate-100 text-slate-500"
                        }`}
                      >
                        {status.status === "active"
                          ? t("research.centerConnectorActive", "已启用")
                          : status.status === "authorization_required"
                            ? t("research.centerConnectorAuthorization", "需授权")
                            : t("research.centerConnectorAvailable", "可接入")}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{status.detail}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          {sourceSaving ? (
            <p className="mt-3 text-xs text-slate-500">
              {t("research.centerSourceSaving", "正在保存公开源设置...")}
            </p>
          ) : null}
        </div>

        <div className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {overviewStats.map((stat) => (
            <div key={stat.label} className="rounded-[26px] border border-white/60 bg-white/60 p-4 shadow-[0_12px_35px_rgba(15,23,42,0.06)]">
              <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-slate-400">
                {stat.label}
              </p>
              <p className={`mt-3 text-3xl font-semibold tracking-[-0.05em] ${stat.tone}`}>{stat.value}</p>
            </div>
          ))}
        </div>
      </section>

      <ResearchConsolePanel
        trackingTopics={trackingTopics.map((item) => ({
          id: item.id,
          name: item.name,
          keyword: item.keyword,
        }))}
      />

      <div className="grid gap-5 xl:grid-cols-[300px,minmax(0,1fr)]">
        <aside className="space-y-4 xl:sticky xl:top-24 xl:self-start">
          <section className="af-glass rounded-[30px] p-5">
            <p className="af-kicker">{t("research.centerFilterTitle", "视图筛选")}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {filterMeta.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setFilter(item.key)}
                  className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                    filter === item.key
                      ? "bg-slate-900 text-white"
                      : "border border-slate-200 bg-white/70 text-slate-600"
                  }`}
                >
                  {item.label} · {item.count}
                </button>
              ))}
            </div>

            <div className="mt-4 space-y-3">
              <div className="flex items-center gap-2 rounded-[20px] border border-white/60 bg-white/70 px-3 py-2 shadow-[0_10px_30px_rgba(15,23,42,0.05)]">
                <input
                  value={queryDraft}
                  onChange={(event) => setQueryDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      handleSearchSubmit();
                    }
                  }}
                  placeholder={t("research.centerSearchPlaceholder", "搜索关键词、甲方、预算、投标...")}
                  className="min-w-0 flex-1 bg-transparent text-sm text-slate-700 outline-none placeholder:text-slate-400"
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
                <p className="text-sm text-slate-500">{t("research.centerPerspectiveLabel", "业务视角")}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {perspectiveMeta.map((item) => (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => setPerspective(item.key)}
                      className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                        perspective === item.key
                          ? "bg-slate-900 text-white"
                          : "border border-slate-200 bg-white/70 text-slate-600"
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
                <p className="mt-2 text-sm text-slate-500">{activePerspective.desc}</p>
              </div>

              <label className="space-y-2 text-sm text-slate-500">
                <span>{t("research.centerRegionLabel", "区域")}</span>
                <select
                  value={regionFilter}
                  onChange={(event) => setRegionFilter(event.target.value)}
                  className="af-input w-full bg-white/70"
                >
                  {regionOptions.map((option, index) => (
                    <option key={option} value={index === 0 ? "" : option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-2 text-sm text-slate-500">
                <span>{t("research.centerIndustryLabel", "行业")}</span>
                <select
                  value={industryFilter}
                  onChange={(event) => setIndustryFilter(event.target.value)}
                  className="af-input w-full bg-white/70"
                >
                  {industryOptions.map((option, index) => (
                    <option key={option} value={index === 0 ? "" : option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-2 text-sm text-slate-500">
                <span>{t("research.centerActionTypeLabel", "动作类型")}</span>
                <select
                  value={actionTypeFilter}
                  onChange={(event) => setActionTypeFilter(event.target.value)}
                  className="af-input w-full bg-white/70"
                >
                  {actionTypeOptions.map((option, index) => (
                    <option key={option} value={index === 0 ? "" : option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="mt-4 rounded-[22px] border border-white/60 bg-white/55 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.2em] text-slate-400">
                {t("research.centerFilteredResult", "当前视图")}
              </p>
              <p className="mt-3 text-3xl font-semibold tracking-[-0.05em] text-slate-900">{visibleItems.length}</p>
              <p className="mt-1 text-sm text-slate-500">
                {t("research.centerFilteredResultHint", "张匹配卡片，适合继续整理为方案或行动卡。")}
              </p>
              <button type="button" onClick={clearFacetFilters} className="mt-4 text-sm font-medium text-slate-700 underline decoration-slate-300 underline-offset-4">
                {t("research.centerClearFilters", "清空筛选")}
              </button>
            </div>
          </section>

          <section className="af-glass rounded-[30px] p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="af-kicker">{t("research.centerSavedViewsKicker", "Saved Views")}</p>
                <h3 className="mt-2 text-lg font-semibold text-slate-900">
                  {t("research.centerSavedViewsTitle", "保存视图")}
                </h3>
                <p className="mt-2 text-sm text-slate-500">
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
                  <article key={view.id} className="rounded-[22px] border border-white/60 bg-white/65 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{view.name}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          {view.query || t("research.centerSavedViewsNoQuery", "无关键词")} · {new Date(view.updated_at).toLocaleDateString()}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => void handleDeleteSavedView(view.id)}
                        className="text-xs font-medium text-slate-400 hover:text-slate-700"
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
                <p className="text-sm text-slate-500">
                  {t("research.centerSavedViewsEmpty", "还没有保存视图，先固定一组筛选条件。")}
                </p>
              )}
            </div>
          </section>

          <section className="af-glass rounded-[30px] p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="af-kicker">{t("research.centerTrackingKicker", "Tracking Topics")}</p>
                <h3 className="mt-2 text-lg font-semibold text-slate-900">
                  {t("research.centerTrackingTitle", "长期跟踪专题")}
                </h3>
                <p className="mt-2 text-sm text-slate-500">
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
                  <article key={topic.id} className="rounded-[22px] border border-white/60 bg-white/65 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{topic.name}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          {topic.keyword} · {new Date(topic.updated_at).toLocaleDateString()}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => void handleDeleteTrackingTopic(topic.id)}
                        className="text-xs font-medium text-slate-400 hover:text-slate-700"
                      >
                        {t("common.delete", "删除")}
                      </button>
                    </div>
                    {topic.research_focus ? (
                      <p className="mt-2 text-sm leading-6 text-slate-600">{topic.research_focus}</p>
                    ) : null}
                    {topic.last_refreshed_at ? (
                      <p className="mt-2 text-xs text-slate-500">
                        {t("research.centerTrackingLastRefresh", "最近刷新")} · {new Date(topic.last_refreshed_at).toLocaleString()}
                      </p>
                    ) : null}
                    <div className="mt-2 flex flex-wrap gap-2 text-xs">
                      <span className={`rounded-full px-2.5 py-1 font-medium ${trackingStatusTone(topic.last_refresh_status)}`}>
                        {trackingStatusLabel(topic.last_refresh_status)}
                      </span>
                      {topic.last_refresh_new_targets?.length ? (
                        <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
                          新增甲方 {topic.last_refresh_new_targets.length}
                        </span>
                      ) : null}
                      {topic.last_refresh_new_competitors?.length ? (
                        <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-700">
                          新增竞品 {topic.last_refresh_new_competitors.length}
                        </span>
                      ) : null}
                      {topic.last_refresh_new_budget_signals?.length ? (
                        <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700">
                          新增预算线索 {topic.last_refresh_new_budget_signals.length}
                        </span>
                      ) : null}
                    </div>
                    {topic.last_refresh_note ? (
                      <p className="mt-2 text-xs leading-5 text-slate-500">{topic.last_refresh_note}</p>
                    ) : null}
                    {topic.last_refresh_error ? (
                      <p className="mt-2 text-xs leading-5 text-rose-600">{topic.last_refresh_error}</p>
                    ) : null}
                    {topic.last_refresh_new_targets?.length || topic.last_refresh_new_competitors?.length || topic.last_refresh_new_budget_signals?.length ? (
                      <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
                        {topic.last_refresh_new_targets?.slice(0, 2).map((value) => (
                          <span key={`${topic.id}-new-target-${value}`} className="rounded-full bg-sky-50 px-2 py-1 text-sky-700">
                            甲方 · {value}
                          </span>
                        ))}
                        {topic.last_refresh_new_competitors?.slice(0, 2).map((value) => (
                          <span key={`${topic.id}-new-competitor-${value}`} className="rounded-full bg-amber-50 px-2 py-1 text-amber-700">
                            竞品 · {value}
                          </span>
                        ))}
                        {topic.last_refresh_new_budget_signals?.slice(0, 1).map((value) => (
                          <span key={`${topic.id}-new-budget-${value}`} className="rounded-full bg-emerald-50 px-2 py-1 text-emerald-700">
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
                      <Link href={buildCompareHref({ query: topic.keyword, region: topic.region_filter, industry: topic.industry_filter })} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                        {t("research.centerOpenCompare", "打开对比矩阵")}
                      </Link>
                    </div>
                    {topic.report_history?.length ? (
                      <div className="mt-3 rounded-[18px] border border-white/60 bg-white/55 p-3">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                          {t("research.centerTopicHistory", "最近版本")}
                        </p>
                        <div className="mt-2 space-y-2">
                          {topic.report_history.slice(0, 2).map((version) => (
                            <div key={`${topic.id}-${version.refreshed_at}`} className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
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
                <p className="text-sm text-slate-500">
                  {t("research.centerTrackingEmpty", "还没有长期跟踪专题，可把高价值关键词固定下来。")}
                </p>
              )}
            </div>
          </section>

          <section className="af-glass rounded-[30px] p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="af-kicker">{t("research.watchlistKicker", "Watchlists")}</p>
                <h3 className="mt-2 text-lg font-semibold text-slate-900">
                  {t("research.watchlistTitle", "长期监控 Watchlist")}
                </h3>
                <p className="mt-2 text-sm text-slate-500">
                  {t("research.watchlistDesc", "把专题刷新结果沉淀成变化摘要，快速知道今天新增了什么。")}
                </p>
              </div>
            </div>
            <div className="mt-4 space-y-3">
              {watchlists.length ? (
                watchlists.map((watchlist) => (
                  <article key={watchlist.id} className="rounded-[22px] border border-white/60 bg-white/65 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{watchlist.name}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          {watchlist.query} · {watchlist.alert_level}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => void handleRefreshWatchlist(watchlist.id)}
                        className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                        disabled={refreshingWatchlistId === watchlist.id}
                      >
                        {refreshingWatchlistId === watchlist.id
                          ? t("research.watchlistRefreshing", "刷新中...")
                          : t("research.watchlistRefresh", "刷新 Watchlist")}
                      </button>
                    </div>
                    <div className="mt-3 space-y-2">
                      {(watchlist.latest_changes?.length
                        ? watchlist.latest_changes.slice(0, 3)
                        : []).map((change) => (
                        <div key={change.id} className="rounded-2xl border border-slate-200/80 bg-slate-50/80 px-3 py-2">
                          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                            {change.change_type} · {change.severity}
                          </p>
                          <p className="mt-1 text-sm text-slate-700">{change.summary}</p>
                        </div>
                      ))}
                      {!watchlist.latest_changes?.length ? (
                        <p className="text-sm text-slate-500">
                          {t("research.watchlistEmpty", "还没有变化摘要，可先刷新一次 Watchlist。")}
                        </p>
                      ) : null}
                    </div>
                  </article>
                ))
              ) : (
                <p className="text-sm text-slate-500">
                  {t("research.watchlistEmpty", "还没有变化摘要，可先刷新一次 Watchlist。")}
                </p>
              )}
            </div>
          </section>
        </aside>

        <div className="space-y-4">
          <section className="af-glass rounded-[30px] p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="af-kicker">{t("research.centerResultKicker", "Workspace")}</p>
                <h3 className="mt-2 text-xl font-semibold tracking-[-0.03em] text-slate-900">
                  {t("research.centerResultTitle", "研究结果工作台")}
                </h3>
                <p className="mt-2 text-sm text-slate-500">{activePerspective.desc}</p>
              </div>
              <div className="rounded-full border border-white/70 bg-white/70 px-3 py-1.5 text-sm text-slate-500">
                {t("research.centerVisibleCount", "可见卡片")} · {visibleItems.length}
              </div>
            </div>

            {activeFilterLabels.length ? (
              <div className="mt-4 flex flex-wrap gap-2">
                {activeFilterLabels.map((label) => (
                  <span key={label} className="rounded-full bg-slate-900 px-3 py-1.5 text-xs font-medium text-white/90">
                    {label}
                  </span>
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-500">
                {t("research.centerNoFilterHint", "当前展示全部研报与行动卡，可从左侧按区域、行业或动作类型快速收窄。")}
              </p>
            )}
          </section>

          {loading ? (
            <section className="af-glass rounded-[30px] p-5 md:p-7 text-sm text-slate-500">
              {t("common.loading", "加载中")}
            </section>
          ) : null}
          {error ? (
            <section className="af-glass rounded-[30px] p-5 md:p-7 text-sm text-rose-600">
              {error}
            </section>
          ) : null}

          {!loading && !error && visibleItems.length === 0 ? (
            <section className="af-glass rounded-[30px] p-5 md:p-7 text-sm text-slate-500">
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
                          isReport ? "bg-sky-100 text-sky-700" : "bg-amber-100 text-amber-700"
                        }`}
                      >
                        {isReport ? t("research.centerReportBadge", "研报") : t("research.centerActionBadge", "行动卡")}
                      </span>
                      {entry.is_focus_reference ? (
                        <span className="rounded-full bg-slate-900 px-2.5 py-1 text-[11px] font-semibold text-white/90">
                          {t("research.centerFocusBadge", "Focus 参考")}
                        </span>
                      ) : null}
                    </div>

                    <Link href={`/knowledge/${entry.id}`} className="block">
                      <h3 className="mt-4 text-lg font-semibold leading-7 text-slate-900">{entry.title}</h3>
                      <p className="mt-3 text-sm leading-6 text-slate-600">{buildPreview(entry)}</p>
                    </Link>

                    {isReport && actionCards.length ? (
                      <div className="mt-4 grid gap-3">
                        {actionCards.map((card) => (
                          <div key={`${entry.id}-${card.title}`} className="rounded-[18px] border border-white/60 bg-white/55 p-3">
                            <p className="break-words text-sm font-semibold leading-6 text-slate-900">{card.title}</p>
                            <div className="mt-2 grid gap-2 break-words text-xs text-slate-500">
                              {card.target_persona ? (
                                <div className="rounded-2xl border border-slate-200/70 bg-slate-50/85 px-3 py-2">
                                  <span className="font-medium text-slate-700">{t("research.actionTarget", "优先对象")}：</span>
                                  {card.target_persona}
                                </div>
                              ) : null}
                              {card.execution_window ? (
                                <div className="rounded-2xl border border-slate-200/70 bg-slate-50/85 px-3 py-2">
                                  <span className="font-medium text-slate-700">{t("research.actionWindow", "执行窗口")}：</span>
                                  {card.execution_window}
                                </div>
                              ) : null}
                              {card.deliverable ? (
                                <div className="rounded-2xl border border-slate-200/70 bg-slate-50/85 px-3 py-2">
                                  <span className="font-medium text-slate-700">{t("research.actionDeliverable", "产出物")}：</span>
                                  {card.deliverable}
                                </div>
                              ) : null}
                            </div>
                            {parseActionPhases(card.recommended_steps).length ? (
                              <div className="mt-3 grid gap-2">
                                {parseActionPhases(card.recommended_steps).map((phase) => (
                                  <div key={`${card.title}-${phase.label}-${phase.content}`} className="min-w-0 overflow-hidden rounded-2xl border border-slate-200/70 bg-white/85 px-3 py-2">
                                    <div className="flex flex-wrap items-center gap-2">
                                      <span className="rounded-full bg-slate-900 px-2 py-0.5 text-[10px] font-semibold text-white/90">
                                        {phase.label}
                                      </span>
                                      {phase.horizon ? (
                                        <span className="text-[11px] font-medium text-slate-500">{phase.horizon}</span>
                                      ) : null}
                                    </div>
                                    <p className="mt-2 min-w-0 break-words whitespace-pre-wrap text-xs leading-5 text-slate-600 [overflow-wrap:anywhere]">
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
                        <span className="rounded-full bg-white/70 px-2.5 py-1 text-[11px] text-slate-500">
                          {keyword}
                        </span>
                      ) : null}
                      {actionType ? (
                        <span className="rounded-full bg-white/70 px-2.5 py-1 text-[11px] text-slate-500">
                          {entry.action_type_label || actionType}
                        </span>
                      ) : null}
                      {entry.region_label ? (
                        <span className="rounded-full bg-white/70 px-2.5 py-1 text-[11px] text-slate-500">
                          {entry.region_label}
                        </span>
                      ) : null}
                      {entry.industry_label ? (
                        <span className="rounded-full bg-white/70 px-2.5 py-1 text-[11px] text-slate-500">
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
                      <div className="rounded-[18px] border border-white/60 bg-white/55 p-3">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                          {t("research.centerCardCollection", "分组")}
                        </p>
                        <p className="mt-2 text-sm font-medium text-slate-700">
                          {entry.collection_name || t("common.none", "暂无")}
                        </p>
                      </div>
                      <div className="rounded-[18px] border border-white/60 bg-white/55 p-3">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                          {t("research.centerCardSources", "来源数")}
                        </p>
                        <p className="mt-2 text-sm font-medium text-slate-700">{sourceCount || "—"}</p>
                      </div>
                      <div className="rounded-[18px] border border-white/60 bg-white/55 p-3">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                          {t("research.centerCardUpdated", "更新")}
                        </p>
                        <p className="mt-2 text-sm font-medium text-slate-700">
                          {new Date(entry.updated_at || entry.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>

                    {isReport && rankedPreview.length ? (
                      <div className="mt-4 grid gap-3">
                        {rankedPreview.map((group) => (
                          <div key={`${entry.id}-${group.key}`} className="rounded-[18px] border border-white/60 bg-white/55 p-3">
                            <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{group.title}</p>
                            <div className="mt-2 flex flex-wrap gap-2">
                              {group.items.map((itemValue) => (
                                <span key={`${group.key}-${itemValue.name}`} className="rounded-full bg-slate-900 px-2.5 py-1 text-[11px] text-white/90">
                                  {itemValue.name} · {itemValue.score_label}
                                </span>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : null}

                    {isReport && diagnosticsMeta && (diagnosticsMeta.scopeRegions.length || diagnosticsMeta.scopeIndustries.length || diagnosticsMeta.scopeClients.length || diagnosticsMeta.topicAnchors.length || diagnosticsMeta.matchedThemes.length || diagnosticsMeta.filteredOldSourceCount || diagnosticsMeta.filteredRegionConflictCount || diagnosticsMeta.normalizedEntityCount || diagnosticsMeta.uniqueDomainCount || diagnosticsMeta.candidateProfileCompanies.length || diagnosticsMeta.candidateProfileHitCount) ? (
                      <div className="mt-4 rounded-[18px] border border-white/60 bg-white/55 p-3">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                          {t("research.sourceDiagnosticsTitle", "采集诊断")}
                        </p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          <span
                            className={`rounded-full px-2.5 py-1 text-[11px] ${
                              diagnosticsMeta.evidenceMode === "strong"
                                ? "bg-emerald-50 text-emerald-700"
                                : diagnosticsMeta.evidenceMode === "provisional"
                                  ? "bg-amber-50 text-amber-700"
                                  : "bg-slate-100 text-slate-600"
                            }`}
                          >
                            {diagnosticsMeta.evidenceMode === "strong"
                              ? "强证据"
                              : diagnosticsMeta.evidenceMode === "provisional"
                                ? "可用初版"
                                : "兜底候选"}
                          </span>
                          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-500">
                            检索质量 {diagnosticsMeta.retrievalQuality === "high" ? "高" : diagnosticsMeta.retrievalQuality === "medium" ? "中" : "低"}
                          </span>
                          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-500">
                            严格命中 {Math.round(diagnosticsMeta.strictMatchRatio * 100)}%
                          </span>
                          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-500">
                            官方源 {Math.round(diagnosticsMeta.officialSourceRatio * 100)}%
                          </span>
                          {diagnosticsMeta.uniqueDomainCount > 0 ? (
                            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-500">
                              域名 {diagnosticsMeta.uniqueDomainCount}
                            </span>
                          ) : null}
                          {diagnosticsMeta.scopeRegions.map((value) => (
                            <span key={`${entry.id}-scope-region-${value}`} className="rounded-full bg-cyan-50 px-2.5 py-1 text-[11px] text-cyan-700">
                              区域 · {value}
                            </span>
                          ))}
                          {diagnosticsMeta.scopeIndustries.map((value) => (
                            <span key={`${entry.id}-scope-industry-${value}`} className="rounded-full bg-blue-50 px-2.5 py-1 text-[11px] text-blue-700">
                              领域 · {value}
                            </span>
                          ))}
                          {diagnosticsMeta.scopeClients.map((value) => (
                            <span key={`${entry.id}-scope-client-${value}`} className="rounded-full bg-fuchsia-50 px-2.5 py-1 text-[11px] text-fuchsia-700">
                              公司 · {value}
                            </span>
                          ))}
                          {diagnosticsMeta.topicAnchors.map((value) => (
                            <span key={`${entry.id}-anchor-${value}`} className="rounded-full bg-violet-50 px-2.5 py-1 text-[11px] text-violet-700">
                              {value}
                            </span>
                          ))}
                          {diagnosticsMeta.matchedThemes.map((value) => (
                            <span key={`${entry.id}-theme-${value}`} className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] text-emerald-700">
                              {value}
                            </span>
                          ))}
                          {diagnosticsMeta.filteredOldSourceCount > 0 ? (
                            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-500">
                              {t("research.sourceDiagnosticsFilteredOld", "剔除过旧来源")} {diagnosticsMeta.filteredOldSourceCount}
                            </span>
                          ) : null}
                          {diagnosticsMeta.filteredRegionConflictCount > 0 ? (
                            <span className="rounded-full bg-rose-50 px-2.5 py-1 text-[11px] text-rose-700">
                              拦截越界区域 {diagnosticsMeta.filteredRegionConflictCount}
                            </span>
                          ) : null}
                          {diagnosticsMeta.strictTopicSourceCount > 0 ? (
                            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-500">
                              {t("research.sourceDiagnosticsStrictTopic", "严格主题保留")} {diagnosticsMeta.strictTopicSourceCount}
                            </span>
                          ) : null}
                          {diagnosticsMeta.normalizedEntityCount > 0 ? (
                            <span className="rounded-full bg-violet-50 px-2.5 py-1 text-[11px] text-violet-700">
                              实体 {diagnosticsMeta.normalizedEntityCount}
                            </span>
                          ) : null}
                          {diagnosticsMeta.expansionTriggered ? (
                            <span className="rounded-full bg-amber-50 px-2.5 py-1 text-[11px] text-amber-700">
                              已扩搜
                            </span>
                          ) : null}
                          {diagnosticsMeta.correctiveTriggered ? (
                            <span className="rounded-full bg-orange-50 px-2.5 py-1 text-[11px] text-orange-700">
                              已触发纠错检索
                            </span>
                          ) : null}
                          {diagnosticsMeta.candidateProfileCompanies.length ? (
                            <span className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] text-sky-700">
                              候选补证公司 {diagnosticsMeta.candidateProfileCompanies.length}
                            </span>
                          ) : null}
                          {diagnosticsMeta.candidateProfileHitCount > 0 ? (
                            <span className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] text-sky-700">
                              补证公开源 {diagnosticsMeta.candidateProfileHitCount}
                            </span>
                          ) : null}
                          {diagnosticsMeta.candidateProfileOfficialHitCount > 0 ? (
                            <span className="rounded-full bg-cyan-50 px-2.5 py-1 text-[11px] text-cyan-700">
                              其中官方源 {diagnosticsMeta.candidateProfileOfficialHitCount}
                            </span>
                          ) : null}
                        </div>
                        {diagnosticsMeta.normalizedEntityCount > 0 ? (
                          <div className="mt-2 flex flex-wrap gap-2">
                            <span className="rounded-full bg-violet-50 px-2.5 py-1 text-[11px] text-violet-700">
                              甲方 {diagnosticsMeta.normalizedTargetCount}
                            </span>
                            <span className="rounded-full bg-violet-50 px-2.5 py-1 text-[11px] text-violet-700">
                              竞品 {diagnosticsMeta.normalizedCompetitorCount}
                            </span>
                            <span className="rounded-full bg-violet-50 px-2.5 py-1 text-[11px] text-violet-700">
                              伙伴 {diagnosticsMeta.normalizedPartnerCount}
                            </span>
                          </div>
                        ) : null}
                        {diagnosticsMeta.candidateProfileCompanies.length ? (
                          <div className="mt-2 flex flex-wrap gap-2">
                            {diagnosticsMeta.candidateProfileCompanies.map((value) => (
                              <span
                                key={`${entry.id}-candidate-profile-${value}`}
                                className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] text-sky-700"
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
                                className="rounded-full bg-cyan-50 px-2.5 py-1 text-[11px] text-cyan-700"
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
      </div>
    </div>
  );
}
