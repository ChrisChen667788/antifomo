import type {
  ApiResearchRankedEntity,
  ApiResearchReport,
  ApiResearchTrackingTopicTimelineEvent,
} from "@/lib/api";
import {
  buildResearchMarkdownArchiveCompareHref,
  RESEARCH_MARKDOWN_ARCHIVE_COMPARE_SUMMARY_ANCHOR,
} from "@/lib/research-markdown-archive-recap";

export type ResearchFieldDiffRow = {
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

export type ResearchScorePanel = {
  key: string;
  title: string;
  baselineEntities: ApiResearchRankedEntity[];
  currentEntities: ApiResearchRankedEntity[];
};

export type ResearchSourceContributionRow = {
  tier: "official" | "media" | "aggregate";
  label: string;
  score: number;
  percent: number;
};

export type ResearchSourceContributionPanel = {
  key: string;
  title: string;
  baselineRows: ResearchSourceContributionRow[];
  currentRows: ResearchSourceContributionRow[];
};

export type ResearchFollowupImpactPanel = {
  titleResolution: string;
  summaryResolution: string;
  impactedSections: Array<{
    sectionTitle: string;
    impactLabel: string;
    reason: string;
    nextAction: string;
  }>;
};

export function qualityTone(value: string) {
  if (value === "high") return "af-chip af-chip-success";
  if (value === "medium") return "af-chip af-chip-warning";
  return "af-chip";
}

export function qualityLabel(value: string) {
  if (value === "high") return "高";
  if (value === "medium") return "中";
  return "低";
}

export function timelineArchiveKindLabel(
  kind: ApiResearchTrackingTopicTimelineEvent["markdown_archive_kind"] | undefined | null,
) {
  if (kind === "archive_diff_recap") return "差异复盘";
  if (kind === "topic_version_recap") return "版本复盘";
  return "Markdown 归档";
}

export function timelineEventTone(eventType: ApiResearchTrackingTopicTimelineEvent["event_type"]) {
  if (eventType === "compare_snapshot") return "af-chip af-chip-info";
  if (eventType === "markdown_archive") return "af-chip af-chip-success";
  return "af-chip";
}

export function buildArchiveCompareHref(
  currentArchiveId?: string | null,
  compareArchiveId?: string | null,
) {
  return buildResearchMarkdownArchiveCompareHref(
    currentArchiveId,
    compareArchiveId,
    RESEARCH_MARKDOWN_ARCHIVE_COMPARE_SUMMARY_ANCHOR,
  );
}

export function valueBucket(score: number) {
  if (score >= 75) return { label: "高价值", className: "af-chip af-chip-success" };
  if (score >= 55) return { label: "普通价值", className: "af-chip af-chip-warning" };
  return { label: "低价值", className: "af-chip" };
}

export function factorBucket(score: number) {
  if (score >= 14) return { label: "强支撑", className: "af-chip af-chip-success" };
  if (score >= 6) return { label: "中支撑", className: "af-chip af-chip-warning" };
  if (score > 0) return { label: "弱支撑", className: "af-chip af-chip-info" };
  if (score < 0) return { label: "风险提示", className: "af-chip af-chip-danger" };
  return { label: "待补依据", className: "af-chip" };
}

export function contributionBucket(score: number) {
  if (score >= 45) return "高贡献";
  if (score >= 24) return "中贡献";
  return "低贡献";
}

export function normalizeList(values: string[]) {
  return values.map((item) => item.trim()).filter(Boolean);
}

export function buildAddedRows(latest: string[], previous: string[]) {
  const previousSet = new Set(normalizeList(previous));
  return normalizeList(latest).filter((item) => !previousSet.has(item)).slice(0, 4);
}

export function buildRemovedRows(current: string[], baseline: string[]) {
  const currentSet = new Set(normalizeList(current));
  return normalizeList(baseline).filter((item) => !currentSet.has(item)).slice(0, 4);
}

export function buildRewrittenRows(current: string[], baseline: string[]) {
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

export function buildVersionFocusBlocks(report: ApiResearchReport | null) {
  if (!report) return [];
  return [
    { key: "accounts", title: "重点甲方", items: normalizeList(report.target_accounts).slice(0, 3) },
    { key: "budget", title: "预算线索", items: normalizeList(report.budget_signals).slice(0, 3) },
    { key: "competitors", title: "竞品", items: normalizeList(report.competitor_profiles).slice(0, 3) },
    { key: "partners", title: "伙伴", items: normalizeList(report.ecosystem_partners).slice(0, 3) },
  ].filter((item) => item.items.length);
}

export function buildCandidateProfileSummary(report: ApiResearchReport | null) {
  const diagnostics = report?.source_diagnostics;
  return {
    companies: (diagnostics?.candidate_profile_companies || []).map((item) => item.trim()).filter(Boolean).slice(0, 4),
    hitCount: Number(diagnostics?.candidate_profile_hit_count || 0),
    officialHitCount: Number(diagnostics?.candidate_profile_official_hit_count || 0),
    sourceLabels: (diagnostics?.candidate_profile_source_labels || []).map((item) => item.trim()).filter(Boolean).slice(0, 4),
  };
}

export function followupResolutionDisplay(value: string | null | undefined) {
  if (value === "corrected") return "已按追问纠偏";
  if (value === "reused") return "沿用基线";
  if (value === "baseline") return "初始版本";
  return String(value || "").trim() || "无";
}

export function followupImpactTone(impactLabel: string | null | undefined) {
  const normalized = String(impactLabel || "").trim().toLowerCase();
  if (normalized === "high") return "af-chip af-chip-danger";
  if (normalized === "medium") return "af-chip af-chip-warning";
  return "af-chip af-chip-info";
}

export function buildFollowupImpactPanel(report: ApiResearchReport | null): ResearchFollowupImpactPanel {
  const diagnostics = report?.followup_diagnostics;
  const impactedSections = Array.isArray(diagnostics?.impacted_sections)
    ? diagnostics.impacted_sections.slice(0, 3).map((impact) => ({
        sectionTitle: String(impact.section_title || "").trim() || "未命名章节",
        impactLabel: String(impact.impact_label || "").trim() || "low",
        reason: String(impact.reason || "").trim(),
        nextAction: String(impact.next_action || "").trim(),
      }))
    : [];
  return {
    titleResolution: followupResolutionDisplay(diagnostics?.title_resolution),
    summaryResolution: followupResolutionDisplay(diagnostics?.summary_resolution),
    impactedSections,
  };
}

export function buildFallbackRankedEntities(
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

export function buildRankedScorePanels(
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

export function buildSourceContributionRows(
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

export function buildSourceContributionPanels(
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

export function classifyEvidenceTier(tier: string | null | undefined) {
  if (tier === "official" || tier === "aggregate") return tier;
  return "media";
}

export function sourceTierLabel(
  tier: string | null | undefined,
  t: (key: string, fallback: string) => string,
) {
  if (classifyEvidenceTier(tier) === "official") return t("research.sourceOfficial", "官方源");
  if (classifyEvidenceTier(tier) === "aggregate") return t("research.sourceAggregate", "聚合源");
  return t("research.sourceMedia", "媒体源");
}

export function buildEvidenceLinks(
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
