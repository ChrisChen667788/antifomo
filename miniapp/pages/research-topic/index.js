const {
  getResearchTrackingTopicVersions,
  getResearchWorkspace,
  refreshResearchTrackingTopic,
  createResearchActionPlan,
  saveResearchActionCards,
} = require("../../utils/api");
const { t } = require("../../utils/i18n");
const { getPreferenceClass } = require("../../utils/preferences");

function formatDateLabel(value) {
  const date = new Date(value || "");
  if (Number.isNaN(date.getTime())) {
    return String(value || "");
  }
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  const hours = `${date.getHours()}`.padStart(2, "0");
  const minutes = `${date.getMinutes()}`.padStart(2, "0");
  return `${year}-${month}-${day} ${hours}:${minutes}`;
}

function normalizeList(values) {
  return (Array.isArray(values) ? values : [])
    .map((item) => String(item || "").trim())
    .filter(Boolean);
}

function qualityLabel(value) {
  if (value === "high") return "高";
  if (value === "medium") return "中";
  return "低";
}

function qualityTone(value) {
  if (value === "high") return "quality-high";
  if (value === "medium") return "quality-medium";
  return "quality-low";
}

function buildAddedRows(current, baseline) {
  const baselineSet = new Set(normalizeList(baseline));
  return normalizeList(current).filter((item) => !baselineSet.has(item)).slice(0, 4);
}

function buildRemovedRows(current, baseline) {
  const currentSet = new Set(normalizeList(current));
  return normalizeList(baseline).filter((item) => !currentSet.has(item)).slice(0, 4);
}

function buildRewrittenRows(current, baseline) {
  const normalizedCurrent = normalizeList(current);
  const normalizedBaseline = normalizeList(baseline);
  const currentSet = new Set(normalizedCurrent);
  const baselineSet = new Set(normalizedBaseline);
  const rows = [];
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

function buildVersionHighlights(currentReport, baselineReport, i18n) {
  if (!currentReport) return [];
  const rows = [
    {
      title: i18n.diffNewAccounts || "新增甲方",
      items: buildAddedRows(currentReport.target_accounts, baselineReport && baselineReport.target_accounts),
    },
    {
      title: i18n.diffNewCompetitors || "新增竞品",
      items: buildAddedRows(currentReport.competitor_profiles, baselineReport && baselineReport.competitor_profiles),
    },
    {
      title: i18n.diffNewBudgetSignals || "新增预算线索",
      items: buildAddedRows(currentReport.budget_signals, baselineReport && baselineReport.budget_signals),
    },
  ].filter((item) => item.items.length);
  if (rows.length) return rows;
  return [
    {
      title: i18n.diffCurrentFocus || "当前重点线索",
      items: [
        ...normalizeList(currentReport.target_accounts).slice(0, 1),
        ...normalizeList(currentReport.competitor_profiles).slice(0, 1),
        ...normalizeList(currentReport.budget_signals).slice(0, 1),
      ].filter(Boolean),
    },
  ].filter((item) => item.items.length);
}

function buildFieldDiffRows(baselineReport, currentReport, i18n) {
  if (!currentReport) return [];
  const fields = [
    ["target_accounts", i18n.diffFieldAccounts || "甲方"],
    ["target_departments", i18n.diffFieldDepartments || "决策部门"],
    ["public_contact_channels", i18n.diffFieldContacts || "公开联系方式"],
    ["budget_signals", i18n.diffFieldBudget || "预算线索"],
    ["project_distribution", i18n.diffFieldProjects || "项目分布"],
    ["strategic_directions", i18n.diffFieldStrategy || "战略方向"],
    ["tender_timeline", i18n.diffFieldTender || "招标节奏"],
    ["competitor_profiles", i18n.diffFieldCompetitors || "竞品"],
    ["ecosystem_partners", i18n.diffFieldPartners || "生态伙伴"],
    ["client_peer_moves", i18n.diffFieldClientPeers || "甲方同行"],
    ["winner_peer_moves", i18n.diffFieldWinnerPeers || "中标方同行"],
    ["benchmark_cases", i18n.diffFieldBenchmarks || "标杆案例"],
  ];
  return fields
    .map(([key, title]) => {
      const baseline = normalizeList((baselineReport && baselineReport[key]) || []);
      const current = normalizeList(currentReport[key] || []);
      return {
        key,
        title,
        baseline,
        current,
        added: buildAddedRows(current, baseline),
        removed: buildRemovedRows(current, baseline),
        rewritten: buildRewrittenRows(current, baseline),
      };
    })
    .filter((row) => row.baseline.length || row.current.length);
}

function buildVersionCards(report, version, i18n) {
  if (!version) return null;
  return {
    title: version.title || "—",
    refreshed_label: formatDateLabel(version.refreshed_at),
    evidence_label: qualityLabel(version.evidence_density || "low"),
    evidence_tone: qualityTone(version.evidence_density || "low"),
    quality_label: qualityLabel(version.source_quality || "low"),
    quality_tone: qualityTone(version.source_quality || "low"),
    source_count: String(version.source_count || 0),
    summary: String((report && report.executive_summary) || "").slice(0, 180),
    account_items: normalizeList(report && report.target_accounts).slice(0, 3),
    budget_items: normalizeList(report && report.budget_signals).slice(0, 3),
    competitor_items: normalizeList(report && report.competitor_profiles).slice(0, 3),
    partner_items: normalizeList(report && report.ecosystem_partners).slice(0, 3),
  };
}

function classifySourceTier(source) {
  const domain = String((source && source.domain) || "").toLowerCase();
  const sourceType = String((source && source.source_type) || "").toLowerCase();
  const sourceTier = String((source && source.source_tier) || "").toLowerCase();
  if (sourceTier === "official" || sourceType.indexOf("official") >= 0 || sourceType === "policy" || sourceType === "procurement" || sourceType === "filing") {
    return "official";
  }
  if (sourceTier === "aggregate" || sourceType === "tender_feed" || sourceType === "compliant_procurement_aggregate") {
    return "aggregate";
  }
  if (domain.indexOf("gov.cn") >= 0 || domain.indexOf("ggzy.gov.cn") >= 0 || domain.indexOf("sec.gov") >= 0 || domain.indexOf("hkexnews.hk") >= 0 || domain.indexOf("cninfo.com.cn") >= 0) {
    return "official";
  }
  if (domain.indexOf("jianyu") >= 0 || domain.indexOf("cecbid") >= 0 || domain.indexOf("cebpubservice") >= 0 || domain.indexOf("china-cpp") >= 0 || domain.indexOf("chinabidding") >= 0) {
    return "aggregate";
  }
  return "media";
}

function sourceTierLabel(source, i18n) {
  const tier = classifySourceTier(source);
  if (tier === "official") return i18n.sourceOfficial || "官方源";
  if (tier === "aggregate") return i18n.sourceAggregate || "聚合源";
  return i18n.sourceMedia || "媒体源";
}

function buildTieredSourceDetails(report, i18n) {
  const sources = Array.isArray(report && report.sources) ? report.sources : [];
  const groups = [
    { key: "official", title: i18n.sourceOfficial || "官方源" },
    { key: "media", title: i18n.sourceMedia || "媒体源" },
    { key: "aggregate", title: i18n.sourceAggregate || "聚合源" },
  ]
    .map((group) => ({
      ...group,
      items: sources.filter((source) => classifySourceTier(source) === group.key).slice(0, 4).map((source) => ({
        title: source.title || source.url || "来源待确认",
        url: source.url || "",
        meta: [source.source_label, source.domain].filter(Boolean).join(" · "),
        tier_label: sourceTierLabel(source, i18n),
      })),
    }))
    .filter((group) => group.items.length);
  return groups;
}

function buildEvidenceLinks(items, report, i18n) {
  const sources = Array.isArray(report && report.sources) ? report.sources : [];
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
        if (token && haystack.indexOf(token) >= 0) score += 1;
      });
      if (classifySourceTier(source) === "official") score += 2;
      if (classifySourceTier(source) === "aggregate") score += 1;
      return {
        title: source.title || source.url || "来源待确认",
        url: source.url || "",
        meta: [source.source_label, source.domain].filter(Boolean).join(" · "),
        tier_label: sourceTierLabel(source, i18n),
        score,
      };
    })
    .filter((item) => item.url && item.score > 0)
    .sort((left, right) => right.score - left.score);
  const deduped = [];
  const seen = new Set();
  scored.forEach((item) => {
    if (seen.has(item.url) || deduped.length >= 2) return;
    seen.add(item.url);
    deduped.push(item);
  });
  return deduped;
}

function buildCompareMatrixCards(baselineReport, currentReport, i18n) {
  if (!currentReport) return [];
  const configs = [
    ["top_target_accounts", i18n.diffFieldAccounts || "甲方", "name"],
    ["top_competitors", i18n.diffFieldCompetitors || "竞品", "name"],
    ["top_ecosystem_partners", i18n.diffFieldPartners || "生态伙伴", "name"],
    ["target_departments", i18n.diffFieldDepartments || "决策部门", null],
    ["public_contact_channels", i18n.diffFieldContacts || "公开联系方式", null],
    ["benchmark_cases", i18n.diffFieldBenchmarks || "标杆案例", null],
  ];
  return configs
    .map(([key, title, field]) => {
      const baselineSource = (baselineReport && baselineReport[key]) || [];
      const currentSource = (currentReport && currentReport[key]) || [];
      const baselineItems = field
        ? normalizeList((Array.isArray(baselineSource) ? baselineSource : []).map((item) => item && item[field]))
        : normalizeList(baselineSource);
      const currentItems = field
        ? normalizeList((Array.isArray(currentSource) ? currentSource : []).map((item) => item && item[field]))
        : normalizeList(currentSource);
      const evidenceSeed = []
        .concat(currentItems || [])
        .concat(field ? normalizeList((Array.isArray(currentSource) ? currentSource : []).map((item) => item && item.reasoning)) : [])
        .slice(0, 6);
      return {
        key,
        title,
        baseline_items: baselineItems.slice(0, 3),
        current_items: currentItems.slice(0, 3),
        evidence_links: buildEvidenceLinks(evidenceSeed, currentReport, i18n),
      };
    })
    .filter((item) => item.baseline_items.length || item.current_items.length);
}

function buildSourceContributionRows(entities, i18n) {
  const contributionLabel = (score) => {
    const numeric = Number(score || 0);
    if (numeric >= 45) return "高贡献";
    if (numeric >= 24) return "中贡献";
    return "低贡献";
  };
  const tierWeights = {
    official: 1,
    aggregate: 0.82,
    media: 0.64,
  };
  const scores = {
    official: 0,
    aggregate: 0,
    media: 0,
  };
  (Array.isArray(entities) ? entities : []).forEach((entity) => {
    const links = Array.isArray(entity && entity.evidence_links) && entity.evidence_links.length
      ? entity.evidence_links
      : [{ source_tier: "media" }];
    const normalized = links.map((link) => {
      const tier = String((link && link.source_tier) || "media");
      return {
        tier: tier === "official" || tier === "aggregate" ? tier : "media",
        weight: tierWeights[tier === "official" || tier === "aggregate" ? tier : "media"],
      };
    });
    const totalWeight = normalized.reduce((sum, item) => sum + item.weight, 0) || 1;
    normalized.forEach((item) => {
      scores[item.tier] += Number((entity && entity.score) || 0) * (item.weight / totalWeight);
    });
  });
  const total = scores.official + scores.aggregate + scores.media;
  return [
    {
      tier: "official",
      label: i18n.sourceOfficial || "官方源",
      score: scores.official,
      score_label: contributionLabel(scores.official),
      percent: total ? Math.round((scores.official / total) * 100) : 0,
    },
    {
      tier: "aggregate",
      label: i18n.sourceAggregate || "聚合源",
      score: scores.aggregate,
      score_label: contributionLabel(scores.aggregate),
      percent: total ? Math.round((scores.aggregate / total) * 100) : 0,
    },
    {
      tier: "media",
      label: i18n.sourceMedia || "媒体源",
      score: scores.media,
      score_label: contributionLabel(scores.media),
      percent: total ? Math.round((scores.media / total) * 100) : 0,
    },
  ].filter((row) => row.score > 0);
}

function normalizeRankedEntities(items) {
  const scoreLabel = (score) => {
    const numeric = Number(score || 0);
    if (numeric >= 75) return "高价值";
    if (numeric >= 55) return "普通价值";
    return "低价值";
  };
  const factorLabel = (score) => {
    const numeric = Number(score || 0);
    if (numeric >= 14) return "强支撑";
    if (numeric >= 6) return "中支撑";
    if (numeric > 0) return "弱支撑";
    if (numeric < 0) return "风险提示";
    return "待补证据";
  };
  return (Array.isArray(items) ? items : [])
    .map((entity) => ({
      name: String((entity && entity.name) || "").trim(),
      score: Number((entity && entity.score) || 0),
      score_label: scoreLabel(entity && entity.score),
      reasoning: String((entity && entity.reasoning) || "").trim(),
      score_breakdown: (Array.isArray(entity && entity.score_breakdown) ? entity.score_breakdown : [])
        .map((factor) => ({
          label: String((factor && factor.label) || "").trim(),
          score: Number((factor && factor.score) || 0),
          note: String((factor && factor.note) || "").trim(),
          score_label: factorLabel(factor && factor.score),
        }))
        .filter((factor) => factor.label),
      evidence_links: (Array.isArray(entity && entity.evidence_links) ? entity.evidence_links : [])
        .map((link) => ({
          title: String((link && link.title) || (link && link.url) || "来源待确认").trim(),
          url: String((link && link.url) || "").trim(),
          source_label: String((link && link.source_label) || "").trim(),
          tier_label:
            String((link && link.source_tier) || "media") === "official"
              ? i18n.sourceOfficial || "官方源"
              : String((link && link.source_tier) || "media") === "aggregate"
                ? i18n.sourceAggregate || "聚合源"
                : i18n.sourceMedia || "媒体源",
        }))
        .filter((link) => link.url),
    }))
    .filter((entity) => entity.name);
}

function buildFallbackRankedEntities(report, role, i18n) {
  if (!report) return [];
  const scoreLabel = (score) => {
    const numeric = Number(score || 0);
    if (numeric >= 75) return "高价值";
    if (numeric >= 55) return "普通价值";
    return "低价值";
  };
  const factorLabel = (score) => {
    const numeric = Number(score || 0);
    if (numeric >= 14) return "强支撑";
    if (numeric >= 6) return "中支撑";
    if (numeric > 0) return "弱支撑";
    if (numeric < 0) return "风险提示";
    return "待补证据";
  };
  const sourceMap = {
    target: Array.isArray(report.pending_target_candidates) ? report.pending_target_candidates : [],
    competitor: Array.isArray(report.pending_competitor_candidates) ? report.pending_competitor_candidates : [],
    partner: Array.isArray(report.pending_partner_candidates) ? report.pending_partner_candidates : [],
  };
  return (sourceMap[role] || []).slice(0, 3).map((item, index) => {
    const name = String((item && item.name) || "").trim();
    const baseScore = role === "target" ? 68 : role === "competitor" ? 64 : 60;
    const evidenceLinks = Array.isArray(item && item.evidence_links) && item.evidence_links.length
      ? item.evidence_links.map((link) => ({
          title: link.title,
          url: link.url,
          source_label: link.source_label,
          source_tier: link.source_tier,
          tier_label:
            link.source_tier === "official"
              ? (i18n.sourceOfficial || "官方源")
              : link.source_tier === "aggregate"
                ? (i18n.sourceAggregate || "聚合源")
                : (i18n.sourceMedia || "媒体源"),
        }))
      : buildEvidenceLinks([name], report, i18n);
    return {
      name,
      score: Number((item && item.score) || Math.max(42, baseScore - index * 6)),
      score_label: "待补证",
      reasoning:
        (item && item.reasoning) ||
        (role === "target"
          ? i18n.topEntityFallbackTarget || "基于当前专题中的甲方线索、预算/招采语义和公开来源覆盖做的收敛排序。"
          : role === "competitor"
            ? i18n.topEntityFallbackCompetitor || "基于当前专题中的中标/方案/落地语义和公开来源覆盖做的威胁度排序。"
            : i18n.topEntityFallbackPartner || "基于当前专题中的合作/渠道/集成语义和公开来源覆盖做的生态影响力排序。"),
      score_breakdown: Array.isArray(item && item.score_breakdown)
        ? item.score_breakdown.map((factor) => ({
            label: factor.label || "",
            score: Number(factor.score || 0),
            score_label: factorLabel(Number(factor.score || 0)),
            note: factor.note || "",
          }))
        : [],
      evidence_links: evidenceLinks,
    };
  }).filter((entity) => entity.name);
}

function buildScoreBreakdownPanels(baselineReport, currentReport, i18n) {
  const configs = [
    ["targets", i18n.topAccountsExplain || "高价值甲方 Top 3 评分拆解", "top_target_accounts"],
    ["competitors", i18n.topCompetitorsExplain || "高威胁竞品 Top 3 评分拆解", "top_competitors"],
    ["partners", i18n.topPartnersExplain || "高影响力生态伙伴 Top 3 评分拆解", "top_ecosystem_partners"],
  ];
  return configs
    .map(([key, title, field]) => ({
      key,
      title,
      baseline_entities: normalizeRankedEntities((baselineReport && baselineReport[field]) || []).length
        ? normalizeRankedEntities((baselineReport && baselineReport[field]) || [])
        : buildFallbackRankedEntities(
            baselineReport,
            key === "targets" ? "target" : key === "competitors" ? "competitor" : "partner",
            i18n,
          ),
      current_entities: normalizeRankedEntities((currentReport && currentReport[field]) || []).length
        ? normalizeRankedEntities((currentReport && currentReport[field]) || [])
        : buildFallbackRankedEntities(
            currentReport,
            key === "targets" ? "target" : key === "competitors" ? "competitor" : "partner",
            i18n,
          ),
    }))
    .filter((panel) => panel.baseline_entities.length || panel.current_entities.length);
}

function buildSourceContributionPanels(baselineReport, currentReport, i18n) {
  const configs = [
    ["targets", i18n.topAccountsExplain || "高价值甲方 Top 3 评分拆解", "top_target_accounts"],
    ["competitors", i18n.topCompetitorsExplain || "高威胁竞品 Top 3 评分拆解", "top_competitors"],
    ["partners", i18n.topPartnersExplain || "高影响力生态伙伴 Top 3 评分拆解", "top_ecosystem_partners"],
  ];
  return configs
    .map(([key, title, field]) => ({
      key,
      title,
      baseline_rows: buildSourceContributionRows(
        normalizeRankedEntities((baselineReport && baselineReport[field]) || []).length
          ? normalizeRankedEntities((baselineReport && baselineReport[field]) || [])
          : buildFallbackRankedEntities(
              baselineReport,
              key === "targets" ? "target" : key === "competitors" ? "competitor" : "partner",
              i18n,
            ),
        i18n,
      ),
      current_rows: buildSourceContributionRows(
        normalizeRankedEntities((currentReport && currentReport[field]) || []).length
          ? normalizeRankedEntities((currentReport && currentReport[field]) || [])
          : buildFallbackRankedEntities(
              currentReport,
              key === "targets" ? "target" : key === "competitors" ? "competitor" : "partner",
              i18n,
            ),
        i18n,
      ),
    }))
    .filter((panel) => panel.baseline_rows.length || panel.current_rows.length);
}

Page({
  data: {
    prefClass: "",
    i18n: {},
    topicId: "",
    topic: null,
    versions: [],
    loading: true,
    loadError: "",
    refreshing: false,
    actionBusy: false,
    actionMessage: "",
    latestEntryId: "",
    versionOptions: [],
    compareLeftIndex: 0,
    compareRightIndex: 0,
    compareLeftEntryId: "",
    compareRightEntryId: "",
    compareLeftCard: null,
    compareRightCard: null,
    compareSummary: [],
    diffHighlights: [],
    fieldDiffRows: [],
    historyCards: [],
    sourceTierDetails: [],
    compareMatrixCards: [],
    scoreBreakdownPanels: [],
    sourceContributionPanels: [],
  },

  onLoad(options) {
    this.applyPreferences();
    this.setData({ topicId: options.id || "" });
    this.loadTopic();
  },

  onShow() {
    this.applyPreferences();
  },

  applyPreferences() {
    const app = getApp();
    const preferences = app.globalData.preferences;
    const language = preferences.language;
    this.setData({
      prefClass: getPreferenceClass(preferences),
      i18n: {
        kicker: t(language, "research.centerTrackingTitle", "长期跟踪专题"),
        title: t(language, "research.versionSideBySide", "历史版本并排对照"),
        subtitle: t(language, "research.versionSideBySideDesc", "选择两个历史版本，对照执行摘要、质量等级与关键线索变化。"),
        loading: t(language, "common.loading", "加载中"),
        retryLoad: t(language, "common.retryLoad", "重新加载"),
        back: t(language, "item.backToFeed", "返回首页"),
        topicNotFound: t(language, "research.topicNotFound", "未找到对应长期专题"),
        topicLoadFailed: t(language, "research.topicLoadFailed", "专题工作台加载失败，请稍后重试"),
        latestVersion: t(language, "research.latestVersion", "最新版本"),
        versionCompare: t(language, "research.versionCompare", "版本对比"),
        versionCompareStable: t(language, "research.versionCompareStable", "最近两次版本在关键指标上基本稳定"),
        versionBaseline: t(language, "research.versionBaseline", "基线版本"),
        versionCurrent: t(language, "research.versionCurrent", "对照版本"),
        versionFieldDiff: t(language, "research.versionFieldDiff", "字段级正式 Diff"),
        versionFieldDiffDesc: t(language, "research.versionFieldDiffDesc", "按字段对照基线版本与对照版本的核心线索，明确新增、减少与当前保留项。"),
        versionFieldDelta: t(language, "research.versionFieldDelta", "字段变化"),
        versionFieldAdded: t(language, "research.versionFieldAdded", "新增"),
        versionFieldRemoved: t(language, "research.versionFieldRemoved", "减少"),
        versionFieldRewritten: t(language, "research.versionFieldRewritten", "改写"),
        versionFieldStable: t(language, "research.versionFieldStable", "结构稳定"),
        versionFieldEmpty: t(language, "research.versionFieldEmpty", "暂无明确线索"),
        versionFieldNone: t(language, "research.versionFieldNone", "无"),
        versionDiffHighlights: t(language, "research.versionDiffHighlights", "版本差异高亮"),
        topicHistory: t(language, "research.topicHistory", "专题历史"),
        openLatestReport: t(language, "research.centerOpenLatestReport", "打开最新研报"),
        openSelectedVersion: t(language, "research.openSelectedVersion", "打开该版本研报"),
        cardSources: t(language, "research.centerCardSources", "来源数"),
        evidenceDensity: t(language, "research.centerEvidenceDensity", "证据密度"),
        sourceQuality: t(language, "research.centerSourceQuality", "来源质量"),
        refreshTopic: t(language, "research.centerRefreshTopic", "一键刷新研报"),
        refreshingTopic: t(language, "research.centerRefreshingTopic", "刷新中..."),
        regenerateActions: t(language, "research.topicRegenerateActions", "一键重新生成行动卡"),
        regenerateActionsFocus: t(language, "research.topicRegenerateActionsFocus", "生成并加入 Focus 参考"),
        topicActionsSaved: t(language, "research.topicActionsSaved", "已重新生成并保存行动卡"),
        topicActionsSavedToFocus: t(language, "research.topicActionsSavedToFocus", "已重新生成行动卡并加入 Focus 参考"),
        topicActionsFailed: t(language, "research.topicActionsFailed", "重新生成行动卡失败，请稍后重试"),
        diffNewAccounts: t(language, "research.diffNewAccounts", "新增甲方"),
        diffNewCompetitors: t(language, "research.diffNewCompetitors", "新增竞品"),
        diffNewBudgetSignals: t(language, "research.diffNewBudgetSignals", "新增预算线索"),
        diffCurrentFocus: t(language, "research.diffCurrentFocus", "当前重点线索"),
        diffFieldAccounts: t(language, "research.diffFieldAccounts", "甲方"),
        diffFieldBudget: t(language, "research.diffFieldBudget", "预算线索"),
        diffFieldProjects: t(language, "research.diffFieldProjects", "项目分布"),
        diffFieldStrategy: t(language, "research.diffFieldStrategy", "战略方向"),
        diffFieldTender: t(language, "research.diffFieldTender", "招标节奏"),
        diffFieldCompetitors: t(language, "research.diffFieldCompetitors", "竞品"),
        diffFieldPartners: t(language, "research.diffFieldPartners", "生态伙伴"),
        diffFieldDepartments: t(language, "research.diffFieldDepartments", "决策部门"),
        diffFieldContacts: t(language, "research.diffFieldContacts", "公开联系方式"),
        diffFieldClientPeers: t(language, "research.diffFieldClientPeers", "甲方同行"),
        diffFieldWinnerPeers: t(language, "research.diffFieldWinnerPeers", "中标方同行"),
        diffFieldBenchmarks: t(language, "research.diffFieldBenchmarks", "标杆案例"),
        sourceOfficial: t(language, "research.sourceOfficial", "官方源"),
        sourceMedia: t(language, "research.sourceMedia", "媒体源"),
        sourceAggregate: t(language, "research.sourceAggregate", "聚合源"),
        sourceTierDetails: t(language, "research.sourceTierDetails", "来源可信度分层明细"),
        sourceTierDetailsDesc: t(language, "research.sourceTierDetailsDesc", "按官方源、媒体源、聚合源查看当前对照版本的证据来源。"),
        evidenceLinks: t(language, "research.evidenceLinks", "证据链接"),
        evidenceLinkCopied: t(language, "research.evidenceLinkCopied", "证据链接已复制"),
        compareMatrixTitle: t(language, "research.compareMatrixTitle", "Compare Matrix"),
        compareMatrixDesc: t(language, "research.compareMatrixDesc", "按字段并排查看甲方、竞品、伙伴、部门、联系方式和标杆案例。"),
        scorePanelTitle: t(language, "research.scorePanelTitle", "Top 3 评分拆解"),
        scorePanelDesc: t(language, "research.scorePanelDesc", "对照基线版本与当前版本的 Top 3 候选，拆开显示评分因素、推理和证据链。"),
        scorePanelEmpty: t(language, "research.scorePanelEmpty", "当前版本暂无评分拆解明细。"),
        topAccountsExplain: t(language, "research.topAccountsExplain", "高价值甲方 Top 3 评分拆解"),
        topCompetitorsExplain: t(language, "research.topCompetitorsExplain", "高威胁竞品 Top 3 评分拆解"),
        topPartnersExplain: t(language, "research.topPartnersExplain", "高影响力生态伙伴 Top 3 评分拆解"),
        topEntityFallbackTarget: t(language, "research.topEntityFallbackTarget", "基于当前专题中的甲方线索、预算/招采语义和公开来源覆盖做的收敛排序。"),
        topEntityFallbackCompetitor: t(language, "research.topEntityFallbackCompetitor", "基于当前专题中的中标/方案/落地语义和公开来源覆盖做的威胁度排序。"),
        topEntityFallbackPartner: t(language, "research.topEntityFallbackPartner", "基于当前专题中的合作/渠道/集成语义和公开来源覆盖做的生态影响力排序。"),
        scoreFallbackScope: t(language, "research.scoreFallbackScope", "范围收敛"),
        scoreFallbackScopeDefault: t(language, "research.scoreFallbackScopeDefault", "当前专题范围"),
        scoreFallbackCoverage: t(language, "research.scoreFallbackCoverage", "公开来源覆盖"),
        scoreFallbackPriority: t(language, "research.scoreFallbackPriority", "当前专题优先级"),
        sourceContributionTitle: t(language, "research.sourceContributionTitle", "来源类型贡献占比"),
        sourceContributionDesc: t(language, "research.sourceContributionDesc", "按证据链里的官方源、媒体源、聚合源，估算 Top 3 得分的来源贡献结构。"),
        sourceContributionScore: t(language, "research.sourceContributionScore", "折算贡献分"),
        versionBaselineEvidence: t(language, "research.versionBaselineEvidence", "基线版本证据"),
        versionCurrentEvidence: t(language, "research.versionCurrentEvidence", "对照版本证据"),
      },
    });
  },

  loadTopic() {
    const topicId = this.data.topicId;
    if (!topicId) {
      this.setData({ loading: false, loadError: this.data.i18n.topicNotFound });
      return;
    }
    this.setData({ loading: true, loadError: "", actionMessage: "" });
    getResearchWorkspace()
      .then((workspace) => {
        const topic = (workspace.tracking_topics || []).find((item) => item.id === topicId);
        if (!topic) {
          this.setData({ loading: false, loadError: this.data.i18n.topicNotFound, topic: null });
          return Promise.resolve(null);
        }
        return getResearchTrackingTopicVersions(topicId).then((versions) => {
          this.applyTopicState(topic, Array.isArray(versions) ? versions : []);
        });
      })
      .catch(() => {
        this.setData({ loading: false, loadError: this.data.i18n.topicLoadFailed });
      });
  },

  applyTopicState(topic, versions) {
    const safeVersions = Array.isArray(versions) ? versions : [];
    const rightIndex = 0;
    const leftIndex = safeVersions.length > 1 ? 1 : 0;
    const latestEntryId = (safeVersions[0] && safeVersions[0].entry_id) || topic.last_report_entry_id || "";
    this.setData({ topic, versions: safeVersions, latestEntryId }, () => {
      this.syncCompareState(safeVersions, leftIndex, rightIndex);
    });
  },

  syncCompareState(versions, leftIndex, rightIndex) {
    const safeRightIndex = Math.max(0, Math.min(rightIndex, Math.max(versions.length - 1, 0)));
    const safeLeftIndex = Math.max(0, Math.min(leftIndex, Math.max(versions.length - 1, 0)));
    const baselineVersion = versions[safeLeftIndex] || versions[0] || null;
    const currentVersion = versions[safeRightIndex] || versions[0] || null;
    const baselineReport = (baselineVersion && baselineVersion.report) || null;
    const currentReport = (currentVersion && currentVersion.report) || null;
    const compareSummary = [];
    if (baselineVersion && currentVersion) {
      const sourceDelta = Number(currentVersion.source_count || 0) - Number(baselineVersion.source_count || 0);
      if (sourceDelta !== 0) {
        compareSummary.push(`${this.data.i18n.cardSources} ${sourceDelta > 0 ? "+" : ""}${sourceDelta}`);
      }
      if (String(currentVersion.evidence_density || "") !== String(baselineVersion.evidence_density || "")) {
        compareSummary.push(`${this.data.i18n.evidenceDensity} ${qualityLabel(baselineVersion.evidence_density || "low")} → ${qualityLabel(currentVersion.evidence_density || "low")}`);
      }
      if (String(currentVersion.source_quality || "") !== String(baselineVersion.source_quality || "")) {
        compareSummary.push(`${this.data.i18n.sourceQuality} ${qualityLabel(baselineVersion.source_quality || "low")} → ${qualityLabel(currentVersion.source_quality || "low")}`);
      }
    }
    const versionOptions = versions.map((version) => `${formatDateLabel(version.refreshed_at)} · ${version.title}`);
    const historyCards = versions.map((version) => ({
      ...version,
      refreshed_label: formatDateLabel(version.refreshed_at),
      evidence_label: qualityLabel(version.evidence_density || "low"),
      evidence_tone: qualityTone(version.evidence_density || "low"),
      quality_label: qualityLabel(version.source_quality || "low"),
      quality_tone: qualityTone(version.source_quality || "low"),
    }));
    const diffHighlights = buildVersionHighlights(currentReport, baselineReport, this.data.i18n).map((item) => ({
      ...item,
      evidence_links: buildEvidenceLinks(item.items, currentReport, this.data.i18n),
    }));
    const fieldDiffRows = buildFieldDiffRows(baselineReport, currentReport, this.data.i18n).map((row) => ({
      ...row,
      baseline_evidence_links: buildEvidenceLinks([].concat(row.baseline || [], row.removed || [], row.rewritten || []).slice(0, 6), baselineReport, this.data.i18n),
      current_evidence_links: buildEvidenceLinks([].concat(row.current || [], row.added || [], row.rewritten || []).slice(0, 6), currentReport, this.data.i18n),
    }));
    this.setData({
      loading: false,
      loadError: "",
      versionOptions,
      compareLeftIndex: safeLeftIndex,
      compareRightIndex: safeRightIndex,
      compareLeftEntryId: (baselineVersion && baselineVersion.entry_id) || "",
      compareRightEntryId: (currentVersion && currentVersion.entry_id) || "",
      compareLeftCard: buildVersionCards(baselineReport, baselineVersion, this.data.i18n),
      compareRightCard: buildVersionCards(currentReport, currentVersion, this.data.i18n),
      compareSummary: compareSummary.length ? compareSummary : [this.data.i18n.versionCompareStable],
      diffHighlights,
      fieldDiffRows,
      historyCards,
      sourceTierDetails: buildTieredSourceDetails(currentReport, this.data.i18n),
      compareMatrixCards: buildCompareMatrixCards(baselineReport, currentReport, this.data.i18n),
      scoreBreakdownPanels: buildScoreBreakdownPanels(baselineReport, currentReport, this.data.i18n),
      sourceContributionPanels: buildSourceContributionPanels(baselineReport, currentReport, this.data.i18n),
    });
  },

  onBaselineChange(e) {
    const index = Number((e.detail && e.detail.value) || 0);
    const versions = this.data.versions || [];
    this.syncCompareState(versions, index, this.data.compareRightIndex);
  },

  onCurrentChange(e) {
    const index = Number((e.detail && e.detail.value) || 0);
    const versions = this.data.versions || [];
    this.syncCompareState(versions, this.data.compareLeftIndex, index);
  },

  refreshTopic() {
    const topicId = this.data.topicId;
    if (!topicId || this.data.refreshing) return;
    this.setData({ refreshing: true, actionMessage: "" });
    refreshResearchTrackingTopic(topicId, {
      output_language: "zh-CN",
      include_wechat: true,
      max_sources: 12,
      save_to_knowledge: true,
    })
      .then(() => {
        this.loadTopic();
      })
      .finally(() => {
        this.setData({ refreshing: false });
      });
  },

  handleRegenerateActions(e) {
    const focusReference = String((e.currentTarget.dataset.focus || "")) === "true";
    const topic = this.data.topic;
    const currentVersion = (this.data.versions || [])[this.data.compareRightIndex];
    const report = currentVersion && currentVersion.report;
    if (!topic || !currentVersion || !report || this.data.actionBusy) return;
    this.setData({ actionBusy: true, actionMessage: "" });
    createResearchActionPlan({ report })
      .then((plan) =>
        saveResearchActionCards({
          keyword: topic.keyword,
          cards: plan.cards,
          collection_name: `${topic.name} 行动卡`,
          is_focus_reference: focusReference,
        }),
      )
      .then((res) => {
        this.setData({
          actionMessage: focusReference
            ? this.data.i18n.topicActionsSavedToFocus
            : `${this.data.i18n.topicActionsSaved} ${res.created_count || 0}`,
        });
      })
      .catch(() => {
        this.setData({ actionMessage: this.data.i18n.topicActionsFailed });
      })
      .finally(() => {
        this.setData({ actionBusy: false });
      });
  },

  openVersionReport(e) {
    const entryId = e.currentTarget.dataset.entryId;
    if (!entryId) return;
    wx.navigateTo({ url: `/pages/knowledge/index?id=${entryId}` });
  },

  openLatestReport() {
    const entryId = this.data.latestEntryId;
    if (!entryId) return;
    wx.navigateTo({ url: `/pages/knowledge/index?id=${entryId}` });
  },

  openCompareMatrix() {
    wx.navigateTo({ url: "/pages/research/index" });
  },

  openEvidenceLink(e) {
    const url = String((e.currentTarget.dataset && e.currentTarget.dataset.url) || "").trim();
    if (!url) return;
    const encoded = encodeURIComponent(url);
    wx.navigateTo({
      url: `/pages/webview/index?url=${encoded}`,
      fail: () => this.copyEvidenceLink(e),
    });
  },

  copyEvidenceLink(e) {
    const url = String((e.currentTarget.dataset && e.currentTarget.dataset.url) || "").trim();
    if (!url) return;
    wx.setClipboardData({
      data: url,
      success: () => {
        wx.showToast({
          title: this.data.i18n.evidenceLinkCopied || "证据链接已复制",
          icon: "success",
        });
      },
    });
  },
});
