"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  type ApiResearchNormalizedEntity,
  createResearchActionPlan,
  getResearchTrackingTopicVersions,
  getResearchWorkspace,
  saveResearchActionCards,
  type ApiResearchRankedEntity,
  type ApiResearchReport,
  type ApiResearchTrackingTopic,
  type ApiResearchTrackingTopicVersionDetail,
} from "@/lib/api";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { ResearchConsolePanel } from "@/components/research/research-console-panel";

type ResearchTopicWorkspaceProps = {
  topicId: string;
};

type ResearchFieldDiffRow = {
  key: string;
  title: string;
  baseline: string[];
  current: string[];
  added: string[];
  removed: string[];
  rewritten: string[];
  baselineEvidenceLinks: Array<{
    title: string;
    url: string;
    meta: string;
    tierLabel: string;
  }>;
  currentEvidenceLinks: Array<{
    title: string;
    url: string;
    meta: string;
    tierLabel: string;
  }>;
};

type ResearchScorePanel = {
  key: string;
  title: string;
  baselineEntities: ApiResearchRankedEntity[];
  currentEntities: ApiResearchRankedEntity[];
};

type ResearchSourceContributionRow = {
  tier: "official" | "media" | "aggregate";
  label: string;
  score: number;
  percent: number;
};

type ResearchSourceContributionPanel = {
  key: string;
  title: string;
  baselineRows: ResearchSourceContributionRow[];
  currentRows: ResearchSourceContributionRow[];
};

function qualityTone(value: string) {
  if (value === "high") return "bg-emerald-100 text-emerald-700";
  if (value === "medium") return "bg-amber-100 text-amber-700";
  return "bg-slate-100 text-slate-500";
}

function qualityLabel(value: string) {
  if (value === "high") return "高";
  if (value === "medium") return "中";
  return "低";
}

function valueBucket(score: number) {
  if (score >= 75) return { label: "高价值", className: "bg-emerald-100 text-emerald-700" };
  if (score >= 55) return { label: "普通价值", className: "bg-amber-100 text-amber-700" };
  return { label: "低价值", className: "bg-slate-100 text-slate-500" };
}

function factorBucket(score: number) {
  if (score >= 14) return { label: "强支撑", className: "bg-emerald-100 text-emerald-700" };
  if (score >= 6) return { label: "中支撑", className: "bg-amber-100 text-amber-700" };
  if (score > 0) return { label: "弱支撑", className: "bg-sky-100 text-sky-700" };
  if (score < 0) return { label: "风险提示", className: "bg-rose-100 text-rose-700" };
  return { label: "待补证据", className: "bg-slate-100 text-slate-500" };
}

function contributionBucket(score: number) {
  if (score >= 45) return "高贡献";
  if (score >= 24) return "中贡献";
  return "低贡献";
}

function normalizeList(values: string[]) {
  return values.map((item) => item.trim()).filter(Boolean);
}

function buildAddedRows(latest: string[], previous: string[]) {
  const previousSet = new Set(normalizeList(previous));
  return normalizeList(latest).filter((item) => !previousSet.has(item)).slice(0, 4);
}

function buildRemovedRows(current: string[], baseline: string[]) {
  const currentSet = new Set(normalizeList(current));
  return normalizeList(baseline).filter((item) => !currentSet.has(item)).slice(0, 4);
}

function buildRewrittenRows(current: string[], baseline: string[]) {
  const normalizedCurrent = normalizeList(current);
  const normalizedBaseline = normalizeList(baseline);
  const currentSet = new Set(normalizedCurrent);
  const baselineSet = new Set(normalizedBaseline);
  const rows: string[] = [];
  const maxLength = Math.max(normalizedCurrent.length, normalizedBaseline.length);
  for (let index = 0; index < maxLength; index += 1) {
    const left = normalizedBaseline[index];
    const right = normalizedCurrent[index];
    if (!left || !right || left === right) continue;
    if (!currentSet.has(left) && !baselineSet.has(right)) {
      rows.push(`${left} → ${right}`);
    }
    if (rows.length >= 3) break;
  }
  return rows;
}

function buildVersionFocusBlocks(report: ApiResearchReport | null) {
  if (!report) return [];
  return [
    { key: "accounts", title: "重点甲方", items: normalizeList(report.target_accounts).slice(0, 3) },
    { key: "budget", title: "预算线索", items: normalizeList(report.budget_signals).slice(0, 3) },
    { key: "competitors", title: "竞品", items: normalizeList(report.competitor_profiles).slice(0, 3) },
    { key: "partners", title: "伙伴", items: normalizeList(report.ecosystem_partners).slice(0, 3) },
  ].filter((item) => item.items.length);
}

function buildCandidateProfileSummary(report: ApiResearchReport | null) {
  const diagnostics = report?.source_diagnostics;
  return {
    companies: (diagnostics?.candidate_profile_companies || []).map((item) => item.trim()).filter(Boolean).slice(0, 4),
    hitCount: Number(diagnostics?.candidate_profile_hit_count || 0),
    officialHitCount: Number(diagnostics?.candidate_profile_official_hit_count || 0),
    sourceLabels: (diagnostics?.candidate_profile_source_labels || []).map((item) => item.trim()).filter(Boolean).slice(0, 4),
  };
}

function buildFallbackRankedEntities(
  report: ApiResearchReport | null,
  role: "target" | "competitor" | "partner",
  t: (key: string, fallback: string) => string,
): ApiResearchRankedEntity[] {
  if (!report) return [];
  const normalizeTier = (tier: string | null | undefined): "official" | "media" | "aggregate" => {
    if (tier === "official") return "official";
    if (tier === "aggregate") return "aggregate";
    return "media";
  };
  const sourceMap = {
    target: report.pending_target_candidates || [],
    competitor: report.pending_competitor_candidates || [],
    partner: report.pending_partner_candidates || [],
  };
  const values = (sourceMap[role] || []).slice(0, 3);
  return values.map((item, index) => {
    const name = item.name || "";
    const score = Number(item.score || Math.max(48, 70 - index * 8));
    const evidenceLinks = Array.isArray(item.evidence_links) && item.evidence_links.length
      ? item.evidence_links.map((link) => ({
          title: link.title,
          url: link.url,
          source_label: link.source_label,
          source_tier: normalizeTier(link.source_tier),
        }))
      : buildEvidenceLinks([name], report, t).map((link) => ({
          title: link.title,
          url: link.url,
          source_label: link.meta,
          source_tier: normalizeTier(
            link.tierLabel === t("research.sourceOfficial", "官方源")
              ? "official"
              : link.tierLabel === t("research.sourceAggregate", "聚合源")
                ? "aggregate"
                : "media",
          ),
        }));
    return {
      name,
      score,
      reasoning:
        item.reasoning ||
        (role === "target"
          ? t("research.topEntityFallbackTarget", "基于当前专题中的甲方线索、预算/招采语义和公开来源覆盖做的收敛排序。")
          : role === "competitor"
            ? t("research.topEntityFallbackCompetitor", "基于当前专题中的中标/方案/落地语义和公开来源覆盖做的威胁度排序。")
            : t("research.topEntityFallbackPartner", "基于当前专题中的合作/渠道/集成语义和公开来源覆盖做的生态影响力排序。")),
      score_breakdown: Array.isArray(item.score_breakdown) && item.score_breakdown.length
        ? item.score_breakdown
        : [
            {
              label: t("research.scoreFallbackScope", "范围收敛"),
              score: 18,
              note: [report.keyword, report.research_focus].filter(Boolean).join(" / ") || t("research.scoreFallbackScopeDefault", "当前专题范围"),
            },
          ],
      evidence_links: evidenceLinks,
      entity_mode: item.entity_mode || "pending",
    };
  });
}

function buildRankedScorePanels(
  baselineReport: ApiResearchReport | null,
  currentReport: ApiResearchReport | null,
  t: (key: string, fallback: string) => string,
): ResearchScorePanel[] {
  const configs: Array<{
    key: string;
    title: string;
    read: (report: ApiResearchReport | null) => ApiResearchRankedEntity[];
  }> = [
    {
      key: "targets",
      title: t("research.topAccountsExplain", "高价值甲方 Top 3 评分拆解"),
      read: (report) => report?.top_target_accounts || [],
    },
    {
      key: "competitors",
      title: t("research.topCompetitorsExplain", "高威胁竞品 Top 3 评分拆解"),
      read: (report) => report?.top_competitors || [],
    },
    {
      key: "partners",
      title: t("research.topPartnersExplain", "高影响力生态伙伴 Top 3 评分拆解"),
      read: (report) => report?.top_ecosystem_partners || [],
    },
  ];

  return configs
    .map((config) => ({
      key: config.key,
      title: config.title,
      baselineEntities: config.read(baselineReport).length
        ? config.read(baselineReport)
        : buildFallbackRankedEntities(
            baselineReport,
            config.key === "targets" ? "target" : config.key === "competitors" ? "competitor" : "partner",
            t,
          ),
      currentEntities: config.read(currentReport).length
        ? config.read(currentReport)
        : buildFallbackRankedEntities(
            currentReport,
            config.key === "targets" ? "target" : config.key === "competitors" ? "competitor" : "partner",
            t,
          ),
    }))
    .filter((panel) => panel.baselineEntities.length || panel.currentEntities.length);
}

function buildSourceContributionRows(
  entities: ApiResearchRankedEntity[],
  t: (key: string, fallback: string) => string,
): ResearchSourceContributionRow[] {
  type ResearchSourceTier = ResearchSourceContributionRow["tier"];
  const tierWeights = {
    official: 1,
    aggregate: 0.82,
    media: 0.64,
  } satisfies Record<ResearchSourceTier, number>;
  const scores = {
    official: 0,
    aggregate: 0,
    media: 0,
  } satisfies Record<ResearchSourceTier, number>;

  entities.forEach((entity) => {
    const links = entity.evidence_links.length
      ? entity.evidence_links
      : [{ title: "", url: "", source_tier: "media" as const }];
    const normalized = links.map((link) => {
      const tier: ResearchSourceTier =
        link.source_tier === "official" || link.source_tier === "aggregate" ? link.source_tier : "media";
      return {
        tier,
        weight: tierWeights[tier],
      };
    });
    const totalWeight = normalized.reduce((sum, item) => sum + item.weight, 0) || 1;
    normalized.forEach((item) => {
      scores[item.tier] += entity.score * (item.weight / totalWeight);
    });
  });

  const total = scores.official + scores.aggregate + scores.media;
  const rows: ResearchSourceContributionRow[] = [
    {
      tier: "official",
      label: t("research.sourceOfficial", "官方源"),
      score: scores.official,
      percent: total ? Math.round((scores.official / total) * 100) : 0,
    },
    {
      tier: "aggregate",
      label: t("research.sourceAggregate", "聚合源"),
      score: scores.aggregate,
      percent: total ? Math.round((scores.aggregate / total) * 100) : 0,
    },
    {
      tier: "media",
      label: t("research.sourceMedia", "媒体源"),
      score: scores.media,
      percent: total ? Math.round((scores.media / total) * 100) : 0,
    },
  ];
  return rows.filter((row) => row.score > 0);
}

function buildSourceContributionPanels(
  baselineReport: ApiResearchReport | null,
  currentReport: ApiResearchReport | null,
  t: (key: string, fallback: string) => string,
): ResearchSourceContributionPanel[] {
  const configs: Array<{
    key: string;
    title: string;
    read: (report: ApiResearchReport | null) => ApiResearchRankedEntity[];
  }> = [
    {
      key: "targets",
      title: t("research.topAccountsExplain", "高价值甲方 Top 3 评分拆解"),
      read: (report) => report?.top_target_accounts || [],
    },
    {
      key: "competitors",
      title: t("research.topCompetitorsExplain", "高威胁竞品 Top 3 评分拆解"),
      read: (report) => report?.top_competitors || [],
    },
    {
      key: "partners",
      title: t("research.topPartnersExplain", "高影响力生态伙伴 Top 3 评分拆解"),
      read: (report) => report?.top_ecosystem_partners || [],
    },
  ];
  return configs
    .map((config) => ({
      key: config.key,
      title: config.title,
      baselineRows: buildSourceContributionRows(
        config.read(baselineReport).length
          ? config.read(baselineReport)
          : buildFallbackRankedEntities(
              baselineReport,
              config.key === "targets" ? "target" : config.key === "competitors" ? "competitor" : "partner",
              t,
            ),
        t,
      ),
      currentRows: buildSourceContributionRows(
        config.read(currentReport).length
          ? config.read(currentReport)
          : buildFallbackRankedEntities(
              currentReport,
              config.key === "targets" ? "target" : config.key === "competitors" ? "competitor" : "partner",
              t,
            ),
        t,
      ),
    }))
    .filter((panel) => panel.baselineRows.length || panel.currentRows.length);
}

function classifyEvidenceTier(tier: string | null | undefined) {
  if (tier === "official" || tier === "aggregate") return tier;
  return "media";
}

function sourceTierLabel(
  tier: string | null | undefined,
  t: (key: string, fallback: string) => string,
) {
  if (classifyEvidenceTier(tier) === "official") return t("research.sourceOfficial", "官方源");
  if (classifyEvidenceTier(tier) === "aggregate") return t("research.sourceAggregate", "聚合源");
  return t("research.sourceMedia", "媒体源");
}

function buildEvidenceLinks(
  items: string[],
  report: ApiResearchReport | null,
  t: (key: string, fallback: string) => string,
) {
  const sources = Array.isArray(report?.sources) ? report.sources : [];
  const tokens = normalizeList(items)
    .join(" ")
    .split(/[，,。；;、\s]+/)
    .map((item) => String(item || "").trim().toLowerCase())
    .filter((item) => item.length >= 2);
  const scored = sources
    .map((source) => {
      const haystack = `${source.title || ""} ${source.snippet || ""} ${source.search_query || ""}`.toLowerCase();
      let score = 0;
      tokens.forEach((token) => {
        if (token && haystack.includes(token)) score += 1;
      });
      const tier = classifyEvidenceTier(source.source_tier);
      if (tier === "official") score += 2;
      if (tier === "aggregate") score += 1;
      return {
        title: source.title || source.url || t("research.sourcePending", "来源待确认"),
        url: source.url || "",
        meta: [source.source_label, source.domain].filter(Boolean).join(" · "),
        tierLabel: sourceTierLabel(source.source_tier, t),
        score,
      };
    })
    .filter((item) => item.url && item.score > 0)
    .sort((left, right) => right.score - left.score);
  const deduped: Array<{ title: string; url: string; meta: string; tierLabel: string }> = [];
  const seen = new Set<string>();
  scored.forEach((item) => {
    if (seen.has(item.url) || deduped.length >= 2) return;
    seen.add(item.url);
    deduped.push(item);
  });
  return deduped;
}

export function ResearchTopicWorkspace({ topicId }: ResearchTopicWorkspaceProps) {
  const { t } = useAppPreferences();
  const [topic, setTopic] = useState<ApiResearchTrackingTopic | null>(null);
  const [versions, setVersions] = useState<ApiResearchTrackingTopicVersionDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [planningActions, setPlanningActions] = useState(false);
  const [savingActions, setSavingActions] = useState(false);
  const [actionMessage, setActionMessage] = useState("");
  const [compareLeftId, setCompareLeftId] = useState("");
  const [compareRightId, setCompareRightId] = useState("");
  const [selectedEntityKey, setSelectedEntityKey] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    getResearchWorkspace()
      .then(async (workspace) => {
        if (!active) return;
        const found = (workspace.tracking_topics || []).find((item) => item.id === topicId) || null;
        if (!found) {
          setTopic(null);
          setVersions([]);
          setError(t("research.topicNotFound", "未找到对应长期专题"));
          setLoading(false);
          return;
        }
        setTopic(found);
        const detailedVersions = await getResearchTrackingTopicVersions(topicId);
        if (!active) return;
        setVersions(detailedVersions);
        setLoading(false);
      })
      .catch(() => {
        if (!active) return;
        setError(t("research.topicLoadFailed", "专题工作台加载失败，请稍后重试"));
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [topicId, t]);

  const latest = versions[0] || null;
  const previous = versions[1] || null;
  const latestReport = latest?.report || null;
  const previousReport = previous?.report || null;
  const latestEntityGroups = useMemo(
    () => [
      {
        key: "target",
        title: "甲方实体",
        items: latestReport?.entity_graph?.target_entities || [],
      },
      {
        key: "competitor",
        title: "竞品实体",
        items: latestReport?.entity_graph?.competitor_entities || [],
      },
      {
        key: "partner",
        title: "伙伴实体",
        items: latestReport?.entity_graph?.partner_entities || [],
      },
    ].filter((group) => group.items.length),
    [latestReport],
  );
  const selectedEntity = useMemo<ApiResearchNormalizedEntity | null>(() => {
    const pool = latestEntityGroups.flatMap((group) => group.items);
    if (!pool.length) return null;
    if (!selectedEntityKey) return pool[0] || null;
    return pool.find((item) => item.canonical_name === selectedEntityKey) || pool[0] || null;
  }, [latestEntityGroups, selectedEntityKey]);

  useEffect(() => {
    if (!versions.length) {
      setCompareLeftId("");
      setCompareRightId("");
      return;
    }
    const validIds = new Set(versions.map((item) => item.id));
    if (!compareRightId || !validIds.has(compareRightId)) {
      setCompareRightId(versions[0]?.id || "");
    }
    if (!compareLeftId || !validIds.has(compareLeftId) || compareLeftId === (versions[0]?.id || "")) {
      setCompareLeftId(versions[1]?.id || versions[0]?.id || "");
    }
  }, [versions, compareLeftId, compareRightId]);

  const compareLeftVersion = versions.find((item) => item.id === compareLeftId) || previous || latest;
  const compareRightVersion = versions.find((item) => item.id === compareRightId) || latest || previous;
  const compareLeftReport = compareLeftVersion?.report || null;
  const compareRightReport = compareRightVersion?.report || null;

  const compareSummary = useMemo(() => {
    if (!compareLeftVersion || !compareRightVersion) return [];
    const rows: string[] = [];
    const sourceDelta = compareRightVersion.source_count - compareLeftVersion.source_count;
    if (sourceDelta !== 0) {
      rows.push(`${t("research.centerCardSources", "来源数")} ${sourceDelta > 0 ? "+" : ""}${sourceDelta}`);
    }
    if (compareRightVersion.evidence_density !== compareLeftVersion.evidence_density) {
      rows.push(
        `${t("research.centerEvidenceDensity", "证据密度")} ${qualityLabel(compareLeftVersion.evidence_density)} → ${qualityLabel(compareRightVersion.evidence_density)}`,
      );
    }
    if (compareRightVersion.source_quality !== compareLeftVersion.source_quality) {
      rows.push(
        `${t("research.centerSourceQuality", "来源质量")} ${qualityLabel(compareLeftVersion.source_quality)} → ${qualityLabel(compareRightVersion.source_quality)}`,
      );
    }
    return rows;
  }, [compareLeftVersion, compareRightVersion, t]);

  const diffHighlights = useMemo(() => {
    if (!compareRightReport) {
      return [];
    }
    const rows = [
      {
        title: t("research.diffNewAccounts", "新增甲方"),
        items: buildAddedRows(compareRightReport.target_accounts, compareLeftReport?.target_accounts || []),
      },
      {
        title: t("research.diffNewCompetitors", "新增竞品"),
        items: buildAddedRows(compareRightReport.competitor_profiles, compareLeftReport?.competitor_profiles || []),
      },
      {
        title: t("research.diffNewBudgetSignals", "新增预算线索"),
        items: buildAddedRows(compareRightReport.budget_signals, compareLeftReport?.budget_signals || []),
      },
    ].filter((row) => row.items.length);
    if (rows.length) {
      return rows;
    }
    if (!compareLeftReport) {
      return [
        {
          title: t("research.diffCurrentFocus", "当前重点线索"),
          items: [
            ...(compareRightReport.target_accounts || []).slice(0, 1),
            ...(compareRightReport.competitor_profiles || []).slice(0, 1),
            ...(compareRightReport.budget_signals || []).slice(0, 1),
          ].filter(Boolean),
        },
      ].filter((row) => row.items.length);
    }
    return [];
  }, [compareLeftReport, compareRightReport, t]);

  const fieldDiffRows = useMemo<ResearchFieldDiffRow[]>(() => {
    if (!compareRightReport) return [];
    const fieldConfigs = [
      { key: "target_accounts", title: t("research.diffFieldAccounts", "甲方") },
      { key: "budget_signals", title: t("research.diffFieldBudget", "预算线索") },
      { key: "project_distribution", title: t("research.diffFieldProjects", "项目分布") },
      { key: "strategic_directions", title: t("research.diffFieldStrategy", "战略方向") },
      { key: "tender_timeline", title: t("research.diffFieldTender", "招标节奏") },
      { key: "competitor_profiles", title: t("research.diffFieldCompetitors", "竞品") },
      { key: "ecosystem_partners", title: t("research.diffFieldPartners", "生态伙伴") },
      { key: "client_peer_moves", title: t("research.diffFieldClientPeers", "甲方同行") },
      { key: "winner_peer_moves", title: t("research.diffFieldWinnerPeers", "中标方同行") },
      { key: "benchmark_cases", title: t("research.diffFieldBenchmarks", "标杆案例") },
    ] as const;
    return fieldConfigs
      .map((config) => {
        const baseline = normalizeList(
          ((compareLeftReport as unknown as Record<string, string[] | undefined> | null)?.[config.key] as string[] | undefined) || [],
        );
        const current = normalizeList(
          ((compareRightReport as unknown as Record<string, string[] | undefined>)[config.key] as string[] | undefined) || [],
        );
        return {
          key: config.key,
          title: config.title,
          baseline,
          current,
          added: buildAddedRows(current, baseline),
          removed: buildRemovedRows(current, baseline),
          rewritten: buildRewrittenRows(current, baseline),
          baselineEvidenceLinks: buildEvidenceLinks(
            [...baseline.slice(0, 4), ...buildRemovedRows(current, baseline), ...buildRewrittenRows(current, baseline)].slice(0, 6),
            compareLeftReport,
            t,
          ),
          currentEvidenceLinks: buildEvidenceLinks(
            [...current.slice(0, 4), ...buildAddedRows(current, baseline), ...buildRewrittenRows(current, baseline)].slice(0, 6),
            compareRightReport,
            t,
          ),
        };
      })
      .filter((row) => row.baseline.length || row.current.length);
  }, [compareLeftReport, compareRightReport, t]);

  const compareFocusBlocks = useMemo(
    () => ({
      left: buildVersionFocusBlocks(compareLeftReport),
      right: buildVersionFocusBlocks(compareRightReport),
    }),
    [compareLeftReport, compareRightReport],
  );

  const scorePanels = useMemo(
    () => buildRankedScorePanels(compareLeftReport, compareRightReport, t),
    [compareLeftReport, compareRightReport, t],
  );

  const sourceContributionPanels = useMemo(
    () => buildSourceContributionPanels(compareLeftReport, compareRightReport, t),
    [compareLeftReport, compareRightReport, t],
  );
  const latestCandidateProfileSummary = useMemo(() => buildCandidateProfileSummary(latestReport), [latestReport]);
  const compareLeftCandidateProfileSummary = useMemo(() => buildCandidateProfileSummary(compareLeftReport), [compareLeftReport]);
  const compareRightCandidateProfileSummary = useMemo(() => buildCandidateProfileSummary(compareRightReport), [compareRightReport]);

  const handleRegenerateActions = async (asFocusReference = false) => {
    if (!latestReport || !topic) return;
    setPlanningActions(true);
    setSavingActions(true);
    setActionMessage("");
    try {
      const plan = await createResearchActionPlan({ report: latestReport });
      const saved = await saveResearchActionCards({
        keyword: latestReport.keyword,
        cards: plan.cards,
        collection_name: `${topic.name} 行动卡`,
        is_focus_reference: asFocusReference,
      });
      setActionMessage(
        asFocusReference
          ? t("research.topicActionsSavedToFocus", "已重新生成行动卡并加入 Focus 参考")
          : t("research.topicActionsSaved", `已重新生成并保存 ${saved.created_count} 张行动卡`),
      );
    } catch {
      setActionMessage(t("research.topicActionsFailed", "重新生成行动卡失败，请稍后重试"));
    } finally {
      setPlanningActions(false);
      setSavingActions(false);
    }
  };

  if (loading) {
    return <section className="af-glass rounded-[30px] p-6 text-sm text-slate-500">{t("common.loading", "加载中")}</section>;
  }

  if (error || !topic) {
    return <section className="af-glass rounded-[30px] p-6 text-sm text-rose-600">{error || t("research.topicNotFound", "未找到对应长期专题")}</section>;
  }

  return (
    <div className="space-y-5">
      <section className="af-glass rounded-[30px] p-6">
        <p className="af-kicker">{t("research.centerTrackingKicker", "Tracking Topics")}</p>
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
            href={`/research/compare?query=${encodeURIComponent(topic.keyword)}${topic.region_filter ? `&region=${encodeURIComponent(topic.region_filter)}` : ""}${topic.industry_filter ? `&industry=${encodeURIComponent(topic.industry_filter)}` : ""}`}
            className="af-btn af-btn-secondary border px-4 py-2 text-sm"
          >
            {t("research.centerOpenCompare", "打开对比矩阵")}
          </Link>
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
        title={t("research.consoleTopicKicker", "Topic Console")}
        description={t(
          "research.consoleTopicDesc",
          "继续围绕当前专题追问预算节点、甲方、竞品与伙伴，同时保留研究阶段进度。",
        )}
      />

      {latest ? (
        <section className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
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
                  候选补证公司 {latestCandidateProfileSummary.companies.length}
                </span>
              ) : null}
              {latestCandidateProfileSummary.hitCount > 0 ? (
                <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
                  补证公开源 {latestCandidateProfileSummary.hitCount}
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

      {latestEntityGroups.length ? (
        <section className="af-glass rounded-[30px] p-6">
          <p className="af-kicker">{t("research.entityWorkspace", "Entity Workspace")}</p>
          <div className="mt-3 grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
            <div className="space-y-3">
              {latestEntityGroups.map((group) => (
                <article key={group.key} className="rounded-[24px] border border-white/70 bg-white/70 p-4">
                  <p className="text-sm font-semibold text-slate-900">{group.title}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {group.items.map((entity) => (
                      <button
                        key={`${group.key}-${entity.canonical_name}`}
                        type="button"
                        onClick={() => setSelectedEntityKey(entity.canonical_name)}
                        className={`rounded-full border px-3 py-1.5 text-xs font-medium ${
                          selectedEntity?.canonical_name === entity.canonical_name
                            ? "border-sky-300 bg-sky-50 text-sky-700"
                            : "border-slate-200 bg-white text-slate-600"
                        }`}
                      >
                        {entity.canonical_name}
                      </button>
                    ))}
                  </div>
                </article>
              ))}
            </div>

            <article className="rounded-[24px] border border-white/70 bg-white/70 p-5">
              {selectedEntity ? (
                <>
                  <p className="text-sm font-semibold text-slate-900">{selectedEntity.canonical_name}</p>
                  <p className="mt-2 text-xs text-slate-500">
                    {selectedEntity.entity_type} · {t("research.entityAliasCount", "别名")} {selectedEntity.aliases.length} ·{" "}
                    {t("research.entitySourceCount", "来源")} {selectedEntity.source_count}
                  </p>
                  {selectedEntity.aliases.length ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {selectedEntity.aliases.map((alias) => (
                        <span key={alias} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                          {alias}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  <div className="mt-4 space-y-3">
                    {(selectedEntity.evidence_links || []).slice(0, 4).map((link) => (
                      <a
                        key={`${selectedEntity.canonical_name}-${link.url}`}
                        href={link.url}
                        target="_blank"
                        rel="noreferrer"
                        className="block rounded-2xl border border-slate-200/80 bg-slate-50/80 px-3 py-3"
                      >
                        <p className="text-sm font-medium text-slate-900">{link.title}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          {[link.source_label, link.source_tier].filter(Boolean).join(" · ")}
                        </p>
                      </a>
                    ))}
                    {!selectedEntity.evidence_links?.length ? (
                      <p className="text-sm text-slate-500">
                        {t("research.entityEvidenceEmpty", "当前实体还没有稳定证据链接。")}
                      </p>
                    ) : null}
                  </div>
                </>
              ) : (
                <p className="text-sm text-slate-500">{t("research.entityWorkspaceEmpty", "当前专题还没有归一化实体。")}</p>
              )}
            </article>
          </div>
        </section>
      ) : null}

      {versions.length > 1 ? (
        <section className="af-glass rounded-[30px] p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="af-kicker">{t("research.versionSideBySide", "历史版本并排对照")}</p>
              <p className="mt-2 text-sm text-slate-500">
                {t("research.versionSideBySideDesc", "选择两个历史版本，对照执行摘要、质量等级与关键线索变化。")}
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="flex min-w-[210px] flex-col gap-1 text-xs text-slate-400">
                <span>{t("research.versionBaseline", "基线版本")}</span>
                <select
                  value={compareLeftId}
                  onChange={(event) => setCompareLeftId(event.target.value)}
                  className="af-input bg-white/70 text-sm text-slate-700"
                >
                  {versions.map((version) => (
                    <option key={`left-${version.id}`} value={version.id}>
                      {new Date(version.refreshed_at).toLocaleString()} · {version.title}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex min-w-[210px] flex-col gap-1 text-xs text-slate-400">
                <span>{t("research.versionCurrent", "对照版本")}</span>
                <select
                  value={compareRightId}
                  onChange={(event) => setCompareRightId(event.target.value)}
                  className="af-input bg-white/70 text-sm text-slate-700"
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
          <div className="mt-5 grid gap-4 xl:grid-cols-2">
            {[
              {
                key: "baseline",
                label: t("research.versionBaseline", "基线版本"),
                version: compareLeftVersion,
                report: compareLeftReport,
                blocks: compareFocusBlocks.left,
              },
              {
                key: "current",
                label: t("research.versionCurrent", "对照版本"),
                version: compareRightVersion,
                report: compareRightReport,
                blocks: compareFocusBlocks.right,
              },
            ].map((panel) => (
              <article key={panel.key} className="rounded-[24px] border border-white/60 bg-white/65 p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-slate-400">{panel.label}</p>
                    <h3 className="mt-2 text-lg font-semibold text-slate-900">{panel.version?.title || "—"}</h3>
                    <p className="mt-1 text-xs text-slate-500">
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
                <p className="mt-4 text-sm leading-7 text-slate-600">
                  {String(panel.report?.executive_summary || "").slice(0, 220) || "—"}
                </p>
                {(() => {
                  const candidateSummary =
                    panel.key === "baseline" ? compareLeftCandidateProfileSummary : compareRightCandidateProfileSummary;
                  if (!candidateSummary.companies.length && candidateSummary.hitCount <= 0) return null;
                  return (
                    <div className="mt-4 flex flex-wrap gap-2 text-xs">
                      {candidateSummary.companies.length ? (
                        <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
                          候选补证公司 {candidateSummary.companies.length}
                        </span>
                      ) : null}
                      {candidateSummary.hitCount > 0 ? (
                        <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
                          补证公开源 {candidateSummary.hitCount}
                        </span>
                      ) : null}
                      {candidateSummary.officialHitCount > 0 ? (
                        <span className="rounded-full bg-cyan-50 px-2.5 py-1 text-cyan-700">
                          其中官方源 {candidateSummary.officialHitCount}
                        </span>
                      ) : null}
                      {candidateSummary.companies.map((value) => (
                        <span key={`${panel.key}-candidate-${value}`} className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
                          候选公司 · {value}
                        </span>
                      ))}
                      {candidateSummary.sourceLabels.map((value) => (
                        <span key={`${panel.key}-candidate-source-${value}`} className="rounded-full bg-cyan-50 px-2.5 py-1 text-cyan-700">
                          {value}
                        </span>
                      ))}
                    </div>
                  );
                })()}
                {panel.blocks.length ? (
                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    {panel.blocks.map((block) => (
                      <div key={`${panel.key}-${block.key}`} className="rounded-[18px] border border-white/60 bg-white/72 p-4">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{block.title}</p>
                        <ul className="mt-2 space-y-2 text-sm leading-6 text-slate-600">
                          {block.items.map((item) => (
                            <li key={item} className="flex gap-2">
                              <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-sky-300" />
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                ) : null}
                {panel.version?.entry_id ? (
                  <Link href={`/knowledge/${panel.version.entry_id}`} className="mt-4 inline-flex text-sm font-medium text-slate-700 underline-offset-4 hover:underline">
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
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            {diffHighlights.map((group) => (
              <article key={group.title} className="rounded-[22px] border border-white/60 bg-white/65 p-4">
                <p className="text-sm font-semibold text-slate-900">{group.title}</p>
                <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
                  {group.items.map((item) => (
                    <li key={item} className="flex gap-2">
                      <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-sky-300" />
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
              <p className="af-kicker">{t("research.versionFieldDiff", "字段级正式 Diff")}</p>
              <p className="mt-2 text-sm text-slate-500">
                {t("research.versionFieldDiffDesc", "按字段对照基线版本与对照版本的核心线索，明确新增、减少与当前保留项。")}
              </p>
            </div>
          </div>
          <div className="mt-5 grid gap-3">
            {fieldDiffRows.map((row) => (
              <article key={row.key} className="rounded-[24px] border border-white/60 bg-white/65 p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h3 className="text-base font-semibold text-slate-900">{row.title}</h3>
                  <div className="flex flex-wrap gap-2 text-xs">
                    {row.added.length ? (
                      <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-emerald-700">
                        {t("research.versionFieldAdded", "新增")} {row.added.length}
                      </span>
                    ) : null}
                    {row.removed.length ? (
                      <span className="rounded-full bg-rose-100 px-2.5 py-1 text-rose-700">
                        {t("research.versionFieldRemoved", "减少")} {row.removed.length}
                      </span>
                    ) : null}
                    {row.rewritten.length ? (
                      <span className="rounded-full bg-sky-100 px-2.5 py-1 text-sky-700">
                        {t("research.versionFieldRewritten", "改写")} {row.rewritten.length}
                      </span>
                    ) : null}
                    {!row.added.length && !row.removed.length ? (
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-500">
                        {t("research.versionFieldStable", "结构稳定")}
                      </span>
                    ) : null}
                  </div>
                </div>
                <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_1fr_0.9fr]">
                  <div className="rounded-[18px] border border-white/60 bg-white/72 p-4">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{t("research.versionBaseline", "基线版本")}</p>
                    <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
                      {(row.baseline.length ? row.baseline.slice(0, 4) : [t("research.versionFieldEmpty", "暂无明确线索")]).map((item) => (
                        <li key={`base-${row.key}-${item}`} className="flex gap-2">
                          <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-slate-300" />
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="rounded-[18px] border border-white/60 bg-white/72 p-4">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{t("research.versionCurrent", "对照版本")}</p>
                    <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
                      {(row.current.length ? row.current.slice(0, 4) : [t("research.versionFieldEmpty", "暂无明确线索")]).map((item) => (
                        <li key={`current-${row.key}-${item}`} className="flex gap-2">
                          <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-sky-300" />
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="rounded-[18px] border border-white/60 bg-white/72 p-4">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{t("research.versionFieldDelta", "字段变化")}</p>
                    <div className="mt-3 space-y-3 text-sm leading-6 text-slate-600">
                      <div>
                        <p className="font-medium text-emerald-700">{t("research.versionFieldAdded", "新增")}</p>
                        <p>{row.added.length ? row.added.join("；") : t("research.versionFieldNone", "无")}</p>
                      </div>
                      <div>
                        <p className="font-medium text-rose-700">{t("research.versionFieldRemoved", "减少")}</p>
                        <p>{row.removed.length ? row.removed.join("；") : t("research.versionFieldNone", "无")}</p>
                      </div>
                      <div>
                        <p className="font-medium text-sky-700">{t("research.versionFieldRewritten", "改写")}</p>
                        <p>{row.rewritten.length ? row.rewritten.join("；") : t("research.versionFieldNone", "无")}</p>
                      </div>
                    </div>
                  </div>
                </div>
                {(row.baselineEvidenceLinks.length || row.currentEvidenceLinks.length) ? (
                  <div className="mt-4 grid gap-4 lg:grid-cols-2">
                    <div className="rounded-[18px] border border-white/60 bg-white/72 p-4">
                      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                        {t("research.versionBaselineEvidence", "基线版本证据")}
                      </p>
                      <div className="mt-3 grid gap-2">
                        {(row.baselineEvidenceLinks.length ? row.baselineEvidenceLinks : []).map((link) => (
                          <a
                            key={`base-${row.key}-${link.url}`}
                            href={link.url}
                            target="_blank"
                            rel="noreferrer"
                            className="rounded-[14px] border border-white/70 bg-white/88 px-3 py-2 text-sm text-slate-600 transition hover:border-sky-200 hover:bg-sky-50/70"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <span className="font-medium text-slate-700">{link.title}</span>
                              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">{link.tierLabel}</span>
                            </div>
                            {link.meta ? <p className="mt-1 text-xs leading-5 text-slate-500">{link.meta}</p> : null}
                          </a>
                        ))}
                        {!row.baselineEvidenceLinks.length ? (
                          <p className="rounded-[14px] border border-dashed border-slate-200 bg-white/70 px-3 py-3 text-xs text-slate-400">
                            {t("research.versionFieldNone", "无")}
                          </p>
                        ) : null}
                      </div>
                    </div>
                    <div className="rounded-[18px] border border-white/60 bg-white/72 p-4">
                      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                        {t("research.versionCurrentEvidence", "对照版本证据")}
                      </p>
                      <div className="mt-3 grid gap-2">
                        {(row.currentEvidenceLinks.length ? row.currentEvidenceLinks : []).map((link) => (
                          <a
                            key={`current-${row.key}-${link.url}`}
                            href={link.url}
                            target="_blank"
                            rel="noreferrer"
                            className="rounded-[14px] border border-white/70 bg-white/88 px-3 py-2 text-sm text-slate-600 transition hover:border-sky-200 hover:bg-sky-50/70"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <span className="font-medium text-slate-700">{link.title}</span>
                              <span className="rounded-full bg-sky-100 px-2 py-0.5 text-[11px] text-sky-700">{link.tierLabel}</span>
                            </div>
                            {link.meta ? <p className="mt-1 text-xs leading-5 text-slate-500">{link.meta}</p> : null}
                          </a>
                        ))}
                        {!row.currentEvidenceLinks.length ? (
                          <p className="rounded-[14px] border border-dashed border-slate-200 bg-white/70 px-3 py-3 text-xs text-slate-400">
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
              <p className="af-kicker">{t("research.scorePanelTitle", "Top 3 评分拆解")}</p>
              <p className="mt-2 text-sm text-slate-500">
                {t("research.scorePanelDesc", "对照基线版本与当前版本的 Top 3 候选，拆开显示评分因素、推理和证据链。")}
              </p>
            </div>
          </div>
          <div className="mt-5 grid gap-4">
            {scorePanels.map((panel) => (
              <article key={panel.key} className="rounded-[24px] border border-white/60 bg-white/65 p-5">
                <h3 className="text-base font-semibold text-slate-900">{panel.title}</h3>
                <div className="mt-4 grid gap-4 xl:grid-cols-2">
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
                    <div key={column.key} className="rounded-[18px] border border-white/60 bg-white/72 p-4">
                      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{column.label}</p>
                      <div className="mt-3 grid gap-3">
                        {(column.entities.length ? column.entities : []).map((entity) => (
                          <article key={`${column.key}-${entity.name}`} className="rounded-[18px] border border-slate-200/70 bg-white/88 p-4">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <h4 className="text-sm font-semibold text-slate-900">{entity.name}</h4>
                              <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${valueBucket(entity.score).className}`}>
                                {valueBucket(entity.score).label}
                              </span>
                            </div>
                            {entity.reasoning ? <p className="mt-3 text-sm leading-6 text-slate-600">{entity.reasoning}</p> : null}
                            <div className="mt-3 grid gap-2">
                              {(entity.score_breakdown.length ? entity.score_breakdown : []).map((factor) => (
                                <div
                                  key={`${entity.name}-${factor.label}`}
                                  className="rounded-[14px] border border-white/70 bg-slate-50/90 px-3 py-2 text-sm text-slate-600"
                                >
                                  <div className="flex items-center justify-between gap-3">
                                    <span className="font-medium text-slate-700">{factor.label}</span>
                                    <span
                                      className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${factorBucket(factor.score).className}`}
                                    >
                                      {factorBucket(factor.score).label}
                                    </span>
                                  </div>
                                  {factor.note ? <p className="mt-1 text-xs leading-5 text-slate-500">{factor.note}</p> : null}
                                </div>
                              ))}
                              {!entity.score_breakdown.length ? (
                                <p className="rounded-[14px] border border-dashed border-slate-200 bg-slate-50/70 px-3 py-2 text-xs text-slate-400">
                                  {t("research.scorePanelEmpty", "当前版本暂无评分拆解明细。")}
                                </p>
                              ) : null}
                            </div>
                            {entity.evidence_links.length ? (
                              <div className="mt-3 grid gap-2">
                                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-400">
                                  {t("research.evidenceLinks", "证据链接")}
                                </p>
                                {entity.evidence_links.map((link) => (
                                  <a
                                    key={`${entity.name}-${link.url}`}
                                    href={link.url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="rounded-[14px] border border-white/70 bg-white/88 px-3 py-2 text-sm text-slate-600 transition hover:border-sky-200 hover:bg-sky-50/70"
                                  >
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                      <span className="font-medium text-slate-700">{link.title}</span>
                                      <span className="rounded-full bg-sky-100 px-2 py-0.5 text-[11px] text-sky-700">
                                        {link.source_tier === "official"
                                          ? t("research.sourceOfficial", "官方源")
                                          : link.source_tier === "aggregate"
                                            ? t("research.sourceAggregate", "聚合源")
                                            : t("research.sourceMedia", "媒体源")}
                                      </span>
                                    </div>
                                    {link.source_label ? <p className="mt-1 text-xs leading-5 text-slate-500">{link.source_label}</p> : null}
                                  </a>
                                ))}
                              </div>
                            ) : null}
                          </article>
                        ))}
                        {!column.entities.length ? (
                          <p className="rounded-[16px] border border-dashed border-slate-200 bg-white/70 px-4 py-4 text-sm text-slate-400">
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
              <p className="af-kicker">{t("research.sourceContributionTitle", "来源类型贡献占比")}</p>
              <p className="mt-2 text-sm text-slate-500">
                {t("research.sourceContributionDesc", "按证据链里的官方源、媒体源、聚合源，估算 Top 3 得分的来源贡献结构。")}
              </p>
            </div>
          </div>
          <div className="mt-5 grid gap-4">
            {sourceContributionPanels.map((panel) => (
              <article key={panel.key} className="rounded-[24px] border border-white/60 bg-white/65 p-5">
                <h3 className="text-base font-semibold text-slate-900">{panel.title}</h3>
                <div className="mt-4 grid gap-4 xl:grid-cols-2">
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
                    <div key={column.key} className="rounded-[18px] border border-white/60 bg-white/72 p-4">
                      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{column.label}</p>
                      <div className="mt-3 grid gap-3">
                        {(column.rows.length ? column.rows : []).map((row) => (
                          <div key={`${column.key}-${row.tier}`} className="rounded-[16px] border border-white/70 bg-white/88 p-4">
                            <div className="flex items-center justify-between gap-3">
                              <span className="text-sm font-medium text-slate-700">{row.label}</span>
                              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                                {row.percent}%
                              </span>
                            </div>
                            <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
                              <div
                                className={`h-full rounded-full ${
                                  row.tier === "official"
                                    ? "bg-emerald-400"
                                    : row.tier === "aggregate"
                                      ? "bg-amber-400"
                                      : "bg-sky-400"
                                }`}
                                style={{ width: `${Math.max(row.percent, 6)}%` }}
                              />
                            </div>
                            <p className="mt-2 text-xs text-slate-500">
                              {t("research.sourceContributionScore", "来源贡献等级")} {contributionBucket(row.score)}
                            </p>
                          </div>
                        ))}
                        {!column.rows.length ? (
                          <p className="rounded-[16px] border border-dashed border-slate-200 bg-white/70 px-4 py-4 text-sm text-slate-400">
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

      <section className="af-glass rounded-[30px] p-6">
        <p className="af-kicker">{t("research.topicHistory", "专题历史")}</p>
        <div className="mt-4 space-y-3">
          {versions.map((version) => (
            <article key={`${version.refreshed_at}-${version.title}`} className="rounded-[22px] border border-white/60 bg-white/65 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-900">{version.title}</p>
                  <p className="mt-1 text-xs text-slate-500">{new Date(version.refreshed_at).toLocaleString()}</p>
                </div>
              <div className="flex flex-wrap gap-2 text-xs">
                <span className={`rounded-full px-2.5 py-1 ${qualityTone(version.evidence_density)}`}>
                  {t("research.centerEvidenceDensity", "证据密度")}·{qualityLabel(version.evidence_density)}
                </span>
                  <span className={`rounded-full px-2.5 py-1 ${qualityTone(version.source_quality)}`}>
                    {t("research.centerSourceQuality", "来源质量")}·{qualityLabel(version.source_quality)}
                  </span>
                <span className="rounded-full bg-white/70 px-2.5 py-1 text-slate-500">
                  {t("research.centerCardSources", "来源数")} {version.source_count}
                </span>
                {version.new_targets?.length ? (
                  <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">新增甲方 {version.new_targets.length}</span>
                ) : null}
                {version.new_competitors?.length ? (
                  <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-700">新增竞品 {version.new_competitors.length}</span>
                ) : null}
                {version.new_budget_signals?.length ? (
                  <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700">新增预算 {version.new_budget_signals.length}</span>
                ) : null}
                {version.report && buildCandidateProfileSummary(version.report).companies.length ? (
                  <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
                    候选补证公司 {buildCandidateProfileSummary(version.report).companies.length}
                  </span>
                ) : null}
              </div>
              </div>
              {version.entry_id ? (
                <Link href={`/knowledge/${version.entry_id}`} className="mt-3 inline-flex text-sm font-medium text-slate-700 underline-offset-4 hover:underline">
                  {t("research.centerOpenLatestReport", "打开最新研报")}
                </Link>
              ) : null}
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
