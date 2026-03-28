const {
  createResearchConversation,
  listKnowledgeEntries,
  listResearchConversations,
  getResearchSourceSettings,
  getResearchJobTimeline,
  sendResearchConversationMessage,
  updateResearchSourceSettings,
  getResearchWorkspace,
  listResearchWatchlists,
  createResearchWatchlist,
  saveResearchView,
  deleteResearchView,
  saveResearchTrackingTopic,
  deleteResearchTrackingTopic,
  refreshResearchTrackingTopic,
  refreshResearchWatchlist,
} = require("../../utils/api");
const { t } = require("../../utils/i18n");
const { getPreferenceClass } = require("../../utils/preferences");
const { buildFacetOptions, getResearchFacets, getResearchPerspectiveScore } = require("../../utils/research-facets");

function sortEntries(items) {
  return (Array.isArray(items) ? items.slice() : []).sort((left, right) => {
    const leftTime = new Date((left && (left.updated_at || left.created_at)) || 0).getTime();
    const rightTime = new Date((right && (right.updated_at || right.created_at)) || 0).getTime();
    return rightTime - leftTime;
  });
}

function buildPreview(entry) {
  const report = entry && entry.metadata_payload && entry.metadata_payload.report;
  const summary = (report && report.executive_summary) || entry.content || "";
  return summary.length > 92 ? `${summary.slice(0, 91).trim()}…` : summary;
}

function normalizeList(values) {
  return (Array.isArray(values) ? values : [])
    .map((value) => String(value || "").trim())
    .filter(Boolean);
}

function parseActionPhases(steps) {
  return normalizeList(steps)
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

function formatDateLabel(value) {
  const date = new Date(value || "");
  if (Number.isNaN(date.getTime())) {
    return String(value || "");
  }
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
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

function classifySourceTier(source) {
  const domain = String((source && source.domain) || "").toLowerCase();
  const sourceType = String((source && source.source_type) || "").toLowerCase();
  if (
    sourceType === "policy" ||
    sourceType === "procurement" ||
    sourceType === "filing" ||
    domain.indexOf("gov.cn") >= 0 ||
    domain.indexOf("ggzy.gov.cn") >= 0 ||
    domain.indexOf("cninfo.com.cn") >= 0 ||
    domain.indexOf("sec.gov") >= 0 ||
    domain.indexOf("hkexnews.hk") >= 0
  ) {
    return "official";
  }
  if (
    sourceType === "tender_feed" ||
    domain.indexOf("jianyu") >= 0 ||
    domain.indexOf("cecbid") >= 0 ||
    domain.indexOf("cebpubservice") >= 0 ||
    domain.indexOf("china-cpp") >= 0 ||
    domain.indexOf("chinabidding") >= 0
  ) {
    return "aggregate";
  }
  return "media";
}

function buildSourceTierPreview(report) {
  const sources = Array.isArray(report && report.sources) ? report.sources : [];
  const counts = { official: 0, media: 0, aggregate: 0 };
  sources.forEach((source) => {
    counts[classifySourceTier(source)] += 1;
  });
  return [
    counts.official ? { key: "official", label: "官方源", value: counts.official } : null,
    counts.media ? { key: "media", label: "媒体源", value: counts.media } : null,
    counts.aggregate ? { key: "aggregate", label: "聚合源", value: counts.aggregate } : null,
  ].filter(Boolean);
}

function buildSourceTierBreakdown(report) {
  const diagnostics = report && report.source_diagnostics;
  const tierCounts = diagnostics && diagnostics.source_tier_counts ? diagnostics.source_tier_counts : {};
  return [
    tierCounts.official ? { key: "official", label: "官方源", value: Number(tierCounts.official || 0) } : null,
    tierCounts.media ? { key: "media", label: "媒体源", value: Number(tierCounts.media || 0) } : null,
    tierCounts.aggregate ? { key: "aggregate", label: "聚合源", value: Number(tierCounts.aggregate || 0) } : null,
  ].filter(Boolean);
}

function buildSourceDiagnosticsMeta(report) {
  const diagnostics = report && report.source_diagnostics;
  const retrievalLabel = (value) => {
    if (value === "high") return "高质量检索";
    if (value === "medium") return "中质量检索";
    return "低质量检索";
  };
  const evidenceLabel = (value) => {
    if (value === "strong") return "强证据";
    if (value === "provisional") return "可用初版";
    return "兜底候选";
  };
  if (!diagnostics) {
    return {
      enabled_labels: [],
      matched_labels: [],
      adapter_hits: 0,
      search_hits: 0,
      tier_breakdown: [],
      recency_window_years: 7,
      filtered_old_source_count: 0,
      retained_source_count: 0,
      strict_topic_source_count: 0,
      topic_anchor_terms: [],
      matched_theme_labels: [],
      retrieval_quality: "low",
      retrieval_quality_label: retrievalLabel("low"),
      evidence_mode: "fallback",
      evidence_mode_label: evidenceLabel("fallback"),
      strict_match_ratio: 0,
      strict_match_percent: 0,
      official_source_ratio: 0,
      official_source_percent: 0,
      unique_domain_count: 0,
      normalized_entity_count: 0,
      normalized_target_count: 0,
      normalized_competitor_count: 0,
      normalized_partner_count: 0,
      expansion_triggered: false,
      corrective_triggered: false,
      candidate_profile_companies: [],
      candidate_profile_hit_count: 0,
      candidate_profile_official_hit_count: 0,
      candidate_profile_source_labels: [],
    };
  }
  return {
    enabled_labels: Array.isArray(diagnostics.enabled_source_labels) ? diagnostics.enabled_source_labels.slice(0, 4) : [],
    matched_labels: Array.isArray(diagnostics.matched_source_labels) ? diagnostics.matched_source_labels.slice(0, 4) : [],
    adapter_hits: Number(diagnostics.adapter_hit_count || 0),
    search_hits: Number(diagnostics.search_hit_count || 0),
    tier_breakdown: buildSourceTierBreakdown(report),
    recency_window_years: Number(diagnostics.recency_window_years || 7),
    filtered_old_source_count: Number(diagnostics.filtered_old_source_count || 0),
    retained_source_count: Number(diagnostics.retained_source_count || 0),
    strict_topic_source_count: Number(diagnostics.strict_topic_source_count || 0),
    topic_anchor_terms: Array.isArray(diagnostics.topic_anchor_terms) ? diagnostics.topic_anchor_terms.slice(0, 4) : [],
    matched_theme_labels: Array.isArray(diagnostics.matched_theme_labels) ? diagnostics.matched_theme_labels.slice(0, 4) : [],
    retrieval_quality: String(diagnostics.retrieval_quality || "low"),
    retrieval_quality_label: retrievalLabel(String(diagnostics.retrieval_quality || "low")),
    evidence_mode: String(diagnostics.evidence_mode || "fallback"),
    evidence_mode_label: String(diagnostics.evidence_mode_label || evidenceLabel(String(diagnostics.evidence_mode || "fallback"))),
    strict_match_ratio: Number(diagnostics.strict_match_ratio || 0),
    strict_match_percent: Math.round(Number(diagnostics.strict_match_ratio || 0) * 100),
    official_source_ratio: Number(diagnostics.official_source_ratio || 0),
    official_source_percent: Math.round(Number(diagnostics.official_source_ratio || 0) * 100),
    unique_domain_count: Number(diagnostics.unique_domain_count || 0),
    normalized_entity_count: Number(diagnostics.normalized_entity_count || 0),
    normalized_target_count: Number(diagnostics.normalized_target_count || 0),
    normalized_competitor_count: Number(diagnostics.normalized_competitor_count || 0),
    normalized_partner_count: Number(diagnostics.normalized_partner_count || 0),
    expansion_triggered: Boolean(diagnostics.expansion_triggered),
    corrective_triggered: Boolean(diagnostics.corrective_triggered),
    candidate_profile_companies: Array.isArray(diagnostics.candidate_profile_companies) ? diagnostics.candidate_profile_companies.slice(0, 4) : [],
    candidate_profile_hit_count: Number(diagnostics.candidate_profile_hit_count || 0),
    candidate_profile_official_hit_count: Number(diagnostics.candidate_profile_official_hit_count || 0),
    candidate_profile_source_labels: Array.isArray(diagnostics.candidate_profile_source_labels) ? diagnostics.candidate_profile_source_labels.slice(0, 4) : [],
  };
}

function buildFallbackRankedPreview(report, role) {
  const scoreLabel = (score) => {
    const numeric = Number(score || 0);
    if (numeric >= 75) return "高价值";
    if (numeric >= 55) return "普通价值";
    return "低价值";
  };
  if (!report) return [];
  const sourceMap = {
    target: Array.isArray(report.pending_target_candidates) ? report.pending_target_candidates : [],
    competitor: Array.isArray(report.pending_competitor_candidates) ? report.pending_competitor_candidates : [],
    partner: Array.isArray(report.pending_partner_candidates) ? report.pending_partner_candidates : [],
  };
  return (sourceMap[role] || []).slice(0, 3).map((value, index) => {
    const name = String((value && value.name) || "").trim();
    const baseScore = role === "target" ? 68 : role === "competitor" ? 64 : 60;
    const score = Number((value && value.score) || Math.max(42, baseScore - index * 6));
    return {
      name,
      score,
      score_label: "待补证",
    };
  }).filter((item) => item.name);
}

function buildRankedPreview(report) {
  const scoreLabel = (score) => {
    const numeric = Number(score || 0);
    if (numeric >= 75) return "高价值";
    if (numeric >= 55) return "普通价值";
    return "低价值";
  };
  if (!report) return [];
  const normalize = (items) =>
    (Array.isArray(items) ? items : [])
      .slice(0, 3)
      .map((entity) => ({
        name: String((entity && entity.name) || "").trim(),
        score: Number((entity && entity.score) || 0),
        score_label: scoreLabel(entity && entity.score),
      }))
      .filter((entity) => entity.name);
  return [
    {
      key: "target",
      title: normalize(report.top_target_accounts).length ? "甲方" : "待补证甲方",
      items: normalize(report.top_target_accounts).length ? normalize(report.top_target_accounts) : buildFallbackRankedPreview(report, "target"),
    },
    {
      key: "competitor",
      title: normalize(report.top_competitors).length ? "竞品" : "待补证竞品",
      items: normalize(report.top_competitors).length ? normalize(report.top_competitors) : buildFallbackRankedPreview(report, "competitor"),
    },
    {
      key: "partner",
      title: normalize(report.top_ecosystem_partners).length ? "伙伴" : "待补证伙伴",
      items: normalize(report.top_ecosystem_partners).length ? normalize(report.top_ecosystem_partners) : buildFallbackRankedPreview(report, "partner"),
    },
  ].filter((group) => group.items.length);
}

function buildReportCardMeta(entry) {
  const report = entry && entry.metadata_payload && entry.metadata_payload.report;
  const actionCardsRaw = entry && entry.metadata_payload && Array.isArray(entry.metadata_payload.action_cards)
    ? entry.metadata_payload.action_cards
    : [];
  if (!report) {
    return {
      report_source_count: "",
      report_evidence_density: "",
      report_evidence_label: "",
      report_evidence_tone: "",
      report_source_quality: "",
      report_source_quality_label: "",
      report_source_quality_tone: "",
      report_source_tiers: [],
      report_source_diagnostics: {
        enabled_labels: [],
        matched_labels: [],
        adapter_hits: 0,
        search_hits: 0,
        tier_breakdown: [],
      },
      report_ranked_preview: [],
      report_action_cards: [],
    };
  }
  return {
    report_source_count: String(report.source_count || ""),
    report_evidence_density: report.evidence_density || "low",
    report_evidence_label: qualityLabel(report.evidence_density || "low"),
    report_evidence_tone: qualityTone(report.evidence_density || "low"),
    report_source_quality: report.source_quality || "low",
    report_source_quality_label: qualityLabel(report.source_quality || "low"),
    report_source_quality_tone: qualityTone(report.source_quality || "low"),
    report_source_tiers: buildSourceTierPreview(report),
    report_source_diagnostics: buildSourceDiagnosticsMeta(report),
    report_ranked_preview: buildRankedPreview(report),
    report_action_cards: actionCardsRaw
      .map((card) => ({
        title: String(card.title || "").trim(),
        target_persona: String(card.target_persona || "").trim(),
        execution_window: String(card.execution_window || "").trim(),
        deliverable: String(card.deliverable || "").trim(),
        phases: parseActionPhases(card.recommended_steps),
      }))
      .filter((card) => card.title)
      .slice(0, 2),
  };
}

function normalizeTrackingTopic(topic) {
  const latestVersion = Array.isArray(topic && topic.report_history) ? topic.report_history[0] : null;
  const status = String((topic && topic.last_refresh_status) || "idle");
  return {
    ...topic,
    last_refresh_status: status,
    last_refresh_status_label:
      status === "running" ? "刷新中" : status === "failed" ? "刷新失败" : status === "succeeded" ? "刷新成功" : "待刷新",
    last_refresh_status_tone:
      status === "running" ? "quality-info" : status === "failed" ? "quality-low" : status === "succeeded" ? "quality-high" : "quality-neutral",
    last_refresh_new_targets: Array.isArray(topic && topic.last_refresh_new_targets) ? topic.last_refresh_new_targets.slice(0, 2) : [],
    last_refresh_new_competitors: Array.isArray(topic && topic.last_refresh_new_competitors) ? topic.last_refresh_new_competitors.slice(0, 2) : [],
    last_refresh_new_budget_signals: Array.isArray(topic && topic.last_refresh_new_budget_signals) ? topic.last_refresh_new_budget_signals.slice(0, 1) : [],
    latest_version_source_count: latestVersion ? String(latestVersion.source_count || "") : "",
    latest_version_evidence_label: latestVersion ? qualityLabel(latestVersion.evidence_density || "low") : "",
    latest_version_evidence_tone: latestVersion ? qualityTone(latestVersion.evidence_density || "low") : "",
    latest_version_quality_label: latestVersion ? qualityLabel(latestVersion.source_quality || "low") : "",
    latest_version_quality_tone: latestVersion ? qualityTone(latestVersion.source_quality || "low") : "",
    latest_version_updated_label: latestVersion ? formatDateLabel(latestVersion.refreshed_at) : "",
  };
}

function buildConsoleSuggestedFollowups(conversation) {
  const messages = Array.isArray(conversation && conversation.messages) ? conversation.messages.slice() : [];
  const latestAssistant = messages.reverse().find((message) => message && message.role === "assistant");
  const followups = latestAssistant && latestAssistant.payload && Array.isArray(latestAssistant.payload.suggested_followups)
    ? latestAssistant.payload.suggested_followups
    : [];
  return followups.map((item) => String(item || "").trim()).filter(Boolean).slice(0, 4);
}

function normalizeConversation(conversation) {
  const messages = Array.isArray(conversation && conversation.messages) ? conversation.messages : [];
  const lastMessage = messages.length ? messages[messages.length - 1] : null;
  return {
    ...conversation,
    messages,
    updated_label: formatDateLabel((conversation && conversation.updated_at) || ""),
    last_message_preview: lastMessage && lastMessage.content
      ? String(lastMessage.content).replace(/\s+/g, " ").trim().slice(0, 72)
      : "",
    suggested_followups: buildConsoleSuggestedFollowups(conversation),
  };
}

function normalizeResearchEntry(entry, kind) {
  const facets = getResearchFacets(entry || {});
  const reportMeta = buildReportCardMeta(entry);
  return {
    ...entry,
    kind,
    action_type: kind === "action" ? facets.actionType : "",
    region_label: facets.region,
    industry_label: facets.industry,
    updated_label: formatDateLabel((entry && (entry.updated_at || entry.created_at)) || ""),
    preview_summary: buildPreview(entry),
    ...reportMeta,
  };
}

Page({
  data: {
    prefClass: "",
    settingsLabel: "设置",
    i18n: {},
    loading: true,
    error: "",
    query: "",
    filter: "all",
    perspective: "all",
    regionFilter: "",
    industryFilter: "",
    actionTypeFilter: "",
    regionOptions: [],
    industryOptions: [],
    actionTypeOptions: [],
    focusOnly: false,
    reports: [],
    actions: [],
    visibleItems: [],
    summaryCards: [],
    activeFilters: [],
    sourcePanelOpen: false,
    sourceSaving: false,
    workspaceSaving: false,
    refreshingTopicId: "",
    refreshingWatchlistId: "",
    consoleLoading: false,
    consoleError: "",
    consoleAllConversations: [],
    consoleConversations: [],
    consoleSelectedConversationId: "",
    consoleSelectedConversation: null,
    consoleTimeline: [],
    consoleDraft: "",
    consoleSubmitting: false,
    consoleFilterTopicId: "all",
    consoleSuggestedFollowups: [],
    sourceSettings: {
      enable_jianyu_tender_feed: true,
      enable_yuntoutiao_feed: true,
      enable_ggzy_feed: true,
      enable_cecbid_feed: true,
      enable_ccgp_feed: true,
      enable_gov_policy_feed: true,
      enable_local_ggzy_feed: true,
      enabled_source_labels: ["剑鱼标讯", "云头条", "全国公共资源交易平台", "中国招标投标网", "政府采购合规聚合", "中国政府网政策/讲话", "地方公共资源交易平台"],
      connector_statuses: [],
      updated_at: null,
    },
    savedViews: [],
    trackingTopics: [],
    watchlists: [],
  },

  onLoad() {
    this.applyPreferences();
    this.loadSourceSettings();
    this.loadWorkspace();
    this.loadResearchConsole();
    this.loadData();
  },

  onShow() {
    this.applyPreferences();
    this.loadSourceSettings();
    this.loadWorkspace();
    this.loadResearchConsole(true);
  },

  applyPreferences() {
    const app = getApp();
    const preferences = app.globalData.preferences;
    const language = preferences.language;
    this.setData({
      prefClass: getPreferenceClass(preferences),
      settingsLabel: t(language, "common.settings", "设置"),
      i18n: {
        kicker: t(language, "research.centerKicker", "Research Center"),
        title: t(language, "research.centerTitle", "关键词研报与行动卡"),
        subtitle: t(
          language,
          "research.centerDesc",
          "统一查看保存过的行业研报、行动卡和 Focus 参考，快速回到方案设计、销售推进与投标规划。"
        ),
        searchPlaceholder: t(language, "research.centerSearchPlaceholder", "搜索关键词、甲方、预算、投标..."),
        filterAll: t(language, "research.centerFilterAll", "全部"),
        filterReports: t(language, "research.centerFilterReports", "研报"),
        filterActions: t(language, "research.centerFilterActions", "行动卡"),
        regionLabel: t(language, "research.centerRegionLabel", "区域"),
        industryLabel: t(language, "research.centerIndustryLabel", "行业"),
        actionTypeLabel: t(language, "research.centerActionTypeLabel", "动作类型"),
        perspectiveLabel: t(language, "research.centerPerspectiveLabel", "业务视角"),
        viewAll: t(language, "research.centerViewAll", "全部视角"),
        viewRegional: t(language, "research.centerViewRegional", "区域情报"),
        viewClient: t(language, "research.centerViewClient", "甲方跟进"),
        viewBidding: t(language, "research.centerViewBidding", "投标排期"),
        viewEcosystem: t(language, "research.centerViewEcosystem", "生态合作"),
        viewAllDesc: t(language, "research.centerViewAllDesc", "综合查看全部研报与行动卡"),
        viewRegionalDesc: t(language, "research.centerViewRegionalDesc", "优先看地区、区域和分层推进线索"),
        viewClientDesc: t(language, "research.centerViewClientDesc", "聚焦甲方角色、拜访和销售推进"),
        viewBiddingDesc: t(language, "research.centerViewBiddingDesc", "集中看预算、采购、中标和项目分期"),
        viewEcosystemDesc: t(language, "research.centerViewEcosystemDesc", "查看伙伴、渠道、联合交付与竞合"),
        regionAll: t(language, "research.centerRegionAll", "全部区域"),
        industryAll: t(language, "research.centerIndustryAll", "全部行业"),
        actionTypeAll: t(language, "research.centerActionTypeAll", "全部动作类型"),
        metricAll: t(language, "research.centerMetricAll", "总卡片"),
        metricReports: t(language, "research.centerMetricReports", "研报"),
        metricActions: t(language, "research.centerMetricActions", "行动卡"),
        metricFocus: t(language, "research.centerMetricFocus", "Focus 参考"),
        searchSubmit: t(language, "research.centerSearchSubmit", "搜索"),
        filterTitle: t(language, "research.centerFilterTitle", "视图筛选"),
        resultTitle: t(language, "research.centerResultTitle", "研究结果工作台"),
        clearFilters: t(language, "research.centerClearFilters", "清空筛选"),
        noFilterHint: t(language, "research.centerNoFilterHint", "当前展示全部研报与行动卡，可按区域、行业或动作类型收窄。"),
        focusOnlyOn: t(language, "research.centerFocusOnlyOn", "仅看 Focus 参考"),
        focusOnlyOff: t(language, "research.centerFocusOnlyOff", "包含全部"),
        loading: t(language, "common.loading", "加载中"),
        empty: t(language, "research.centerEmpty", "当前没有匹配的研报或行动卡。"),
        loadFailed: t(language, "research.centerLoadFailed", "研报中心加载失败，请稍后重试"),
        reportBadge: t(language, "research.centerReportBadge", "研报"),
        actionBadge: t(language, "research.centerActionBadge", "行动卡"),
        focusBadge: t(language, "research.centerFocusBadge", "Focus 参考"),
        collectionLabel: t(language, "research.centerCardCollection", "分组"),
        sourcesLabel: t(language, "research.centerCardSources", "来源数"),
        updatedLabel: t(language, "research.centerCardUpdated", "更新"),
        openKnowledge: t(language, "inbox.researchHistoryOpen", "打开知识卡片"),
        retryLoad: t(language, "common.retryLoad", "重新加载"),
        sourceToggle: t(language, "research.centerSourceToggle", "公开源"),
        sourcePanelKicker: t(language, "research.centerSourcePanelKicker", "Research Sources"),
        sourcePanelDesc: t(
          language,
          "research.centerSourcePanelDesc",
          "将公开招投标与行业媒体流并入研报线索池。当前仅抓取公开页面，不绕过登录或付费墙。"
        ),
        sourceActive: t(language, "research.centerSourceActive", "当前开启"),
        sourceNone: t(language, "research.centerSourceNone", "无"),
        sourceJianyu: t(language, "research.centerSourceJianyu", "剑鱼标讯"),
        sourceJianyuDesc: t(
          language,
          "research.centerSourceJianyuDesc",
          "补充公开招标公告、中标成交、采购意向与项目分包线索。"
        ),
        sourceYuntoutiao: t(language, "research.centerSourceYuntoutiao", "云头条"),
        sourceYuntoutiaoDesc: t(
          language,
          "research.centerSourceYuntoutiaoDesc",
          "补充云计算、AI、产业竞争和技术商业化动态解读。"
        ),
        sourceGgzy: t(language, "research.centerSourceGgzy", "全国公共资源交易平台"),
        sourceGgzyDesc: t(
          language,
          "research.centerSourceGgzyDesc",
          "补充工程建设、政府采购、成交公示等全国公共资源交易公告。"
        ),
        sourceCecbid: t(language, "research.centerSourceCecbid", "中国招标投标网"),
        sourceCecbidDesc: t(
          language,
          "research.centerSourceCecbidDesc",
          "补充招标、结果、资讯和招标前信息公示等公开招采流。"
        ),
        sourceCcgp: t(language, "research.centerSourceCcgp", "政府采购合规聚合"),
        sourceCcgpDesc: t(
          language,
          "research.centerSourceCcgpDesc",
          "以公开、合规、稳定的采购聚合源替代直抓政府采购网，补充采购人、预算和中标线索。"
        ),
        sourceGovPolicy: t(language, "research.centerSourceGovPolicy", "中国政府网政策/讲话"),
        sourceGovPolicyDesc: t(
          language,
          "research.centerSourceGovPolicyDesc",
          "补充政府工作报告、政策文件、领导讲话与战略规划等官方信号。"
        ),
        sourceLocalGgzy: t(language, "research.centerSourceLocalGgzy", "地方公共资源交易平台"),
        sourceLocalGgzyDesc: t(
          language,
          "research.centerSourceLocalGgzyDesc",
          "按区域定向补充省市公共资源交易平台与地方政府采购平台公开公告。"
        ),
        sourceEnabled: t(language, "research.centerSourceEnabled", "已开启"),
        sourceDisabled: t(language, "research.centerSourceDisabled", "已关闭"),
        sourceSaving: t(language, "research.centerSourceSaving", "正在保存公开源设置..."),
        evidenceDensity: t(language, "research.centerEvidenceDensity", "证据密度"),
        sourceQuality: t(language, "research.centerSourceQuality", "来源质量"),
        sourceOfficial: t(language, "research.sourceOfficial", "官方源"),
        sourceMedia: t(language, "research.sourceMedia", "媒体源"),
        sourceAggregate: t(language, "research.sourceAggregate", "聚合源"),
        sourceDiagnosticsTitle: t(language, "research.sourceDiagnosticsTitle", "采集诊断"),
        sourceDiagnosticsEnabled: t(language, "research.sourceDiagnosticsEnabled", "启用信息源"),
        sourceDiagnosticsMatched: t(language, "research.sourceDiagnosticsMatched", "实际命中"),
        sourceDiagnosticsHits: t(language, "research.sourceDiagnosticsHits", "命中爬虫源"),
        sourceDiagnosticsNoMatch: t(language, "research.sourceDiagnosticsNoMatch", "当前卡片暂无额外命中源信息"),
        sourceDiagnosticsTier: t(language, "research.sourceDiagnosticsTier", "来源分层"),
        sourceDiagnosticsRecency: t(language, "research.sourceDiagnosticsRecency", "近 7 年窗口"),
        sourceDiagnosticsFilteredOld: t(language, "research.sourceDiagnosticsFilteredOld", "剔除过旧来源"),
        sourceDiagnosticsStrictTopic: t(language, "research.sourceDiagnosticsStrictTopic", "严格主题保留"),
        sourceDiagnosticsTopicAnchors: t(language, "research.sourceDiagnosticsTopicAnchors", "主题锚点"),
        sourceDiagnosticsThemes: t(language, "research.sourceDiagnosticsThemes", "命中主题"),
        sourceConnectorTitle: t(language, "research.sourceConnectorTitle", "授权/接入状态"),
        sourceConnectorAuthorization: t(language, "research.sourceConnectorAuthorization", "需授权"),
        sourceConnectorActive: t(language, "research.sourceConnectorActive", "已启用"),
        sourceConnectorAvailable: t(language, "research.sourceConnectorAvailable", "可接入"),
        actionTarget: t(language, "research.actionTarget", "优先对象"),
        actionWindow: t(language, "research.actionWindow", "执行窗口"),
        actionDeliverable: t(language, "research.actionDeliverable", "产出物"),
        actionTimeline: t(language, "research.actionTimeline", "推进节奏"),
        trackingLatestVersion: t(language, "research.trackingLatestVersion", "最新版本"),
        savedViewsTitle: t(language, "research.centerSavedViewsTitle", "保存视图"),
        savedViewsDesc: t(language, "research.centerSavedViewsDesc", "把当前筛选和业务视角固定下来，便于重复使用。"),
        saveCurrentView: t(language, "research.centerSaveCurrentView", "保存当前视图"),
        savedViewsEmpty: t(language, "research.centerSavedViewsEmpty", "还没有保存视图。"),
        applyView: t(language, "research.centerApplyView", "应用视图"),
        trackingTitle: t(language, "research.centerTrackingTitle", "长期跟踪专题"),
        trackingDesc: t(language, "research.centerTrackingDesc", "把高价值关键词沉淀成长期专题，后续持续刷新。"),
        saveTopic: t(language, "research.centerSaveTopic", "加入长期跟踪"),
        trackingEmpty: t(language, "research.centerTrackingEmpty", "还没有长期跟踪专题。"),
        watchlistTitle: t(language, "research.watchlistTitle", "Watchlist"),
        watchlistDesc: t(language, "research.watchlistDesc", "把专题刷新结果沉淀成变化摘要，快速看今天新增了什么。"),
        watchlistEmpty: t(language, "research.watchlistEmpty", "还没有 Watchlist。"),
        createWatchlist: t(language, "research.centerCreateWatchlist", "设为 Watchlist"),
        refreshWatchlist: t(language, "research.watchlistRefresh", "刷新 Watchlist"),
        refreshingWatchlist: t(language, "research.watchlistRefreshing", "刷新中..."),
        applyTopic: t(language, "research.centerApplyTopic", "应用专题"),
        openTopicWorkspace: t(language, "research.openTopicWorkspace", "专题工作台"),
        refreshTopic: t(language, "research.centerRefreshTopic", "一键刷新研报"),
        refreshingTopic: t(language, "research.centerRefreshingTopic", "刷新中..."),
        openLatestReport: t(language, "research.centerOpenLatestReport", "打开最新研报"),
        trackingLastRefresh: t(language, "research.centerTrackingLastRefresh", "最近刷新"),
        deleteLabel: t(language, "common.delete", "删除"),
        consoleTitle: t(language, "research.consoleTitle", "边追问边查看研究过程"),
        consoleDesc: t(language, "research.consoleDesc", "围绕专题或历史研究任务继续追问，保留关键证据和阶段进度。"),
        consoleAllTopics: t(language, "research.consoleAllTopics", "全部专题"),
        consoleNewConversation: t(language, "research.consoleNewConversation", "新建对话"),
        consoleRefresh: t(language, "common.refresh", "刷新"),
        consoleEmpty: t(language, "research.consoleEmpty", "当前还没有研究对话，先创建一个专题追问窗口。"),
        consoleSend: t(language, "research.consoleSend", "发送追问"),
        consoleSending: t(language, "research.consoleSending", "发送中..."),
        consolePlaceholder: t(language, "research.consoleInputPlaceholder", "继续追问预算节点、甲方、竞品、伙伴或执行动作..."),
        consoleMessages: t(language, "research.consoleMessageCount", "条消息"),
        consoleAssistant: t(language, "research.consoleAssistant", "assistant"),
        consoleUser: t(language, "research.consoleUser", "user"),
        consoleTimelineTitle: t(language, "research.consoleTimelineTitle", "研究进度 / Timeline"),
        consoleTimelineDesc: t(language, "research.consoleTimelineDesc", "展示该研究任务的阶段推进和关键状态。"),
        consoleTimelineNoJob: t(language, "research.consoleTimelineNoJob", "当前对话未绑定研究任务，先基于专题版本继续追问。"),
        consoleTimelineEmpty: t(language, "research.consoleTimelineEmpty", "当前任务还没有额外的阶段事件。"),
        consoleTimelineTopicHint: t(language, "research.consoleTimelineTopicHint", "继续追问时会直接使用当前专题的最新版本内容。"),
        consoleSelectHint: t(language, "research.consoleSelectHint", "先选择一个对话，或新建一个专题追问窗口。"),
        consoleRefreshFailed: t(language, "research.consoleLoadFailed", "研究对话加载失败，请稍后重试。"),
      },
    });
  },

  loadSourceSettings() {
    getResearchSourceSettings()
      .then((res) => {
        this.setData({ sourceSettings: res });
      })
      .catch(() => {
        this.setData({
          sourceSettings: {
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
          }
        });
      });
  },

  loadWorkspace() {
    Promise.all([getResearchWorkspace(), listResearchWatchlists()])
      .then(([res, watchlists]) => {
        const trackingTopics = Array.isArray(res.tracking_topics) ? res.tracking_topics.map(normalizeTrackingTopic) : [];
        const nextFilterTopicId =
          this.data.consoleFilterTopicId !== "all" &&
          !trackingTopics.some((item) => item.id === this.data.consoleFilterTopicId)
            ? "all"
            : this.data.consoleFilterTopicId;
        this.setData({
          savedViews: Array.isArray(res.saved_views) ? res.saved_views : [],
          trackingTopics,
          watchlists: Array.isArray(watchlists) ? watchlists : [],
          consoleFilterTopicId: nextFilterTopicId,
        });
        this.syncResearchConsoleState({ filterTopicId: nextFilterTopicId });
      })
      .catch(() => {
        this.setData({
          savedViews: [],
          trackingTopics: [],
          watchlists: [],
        });
      });
  },

  syncResearchConsoleState(options = {}) {
    const allConversations = Array.isArray(options.allConversations)
      ? options.allConversations
      : (this.data.consoleAllConversations || []);
    const filterTopicId = options.filterTopicId || this.data.consoleFilterTopicId || "all";
    const visibleConversations =
      filterTopicId === "all"
        ? allConversations
        : allConversations.filter((conversation) => conversation.topic_id === filterTopicId);
    let selectedConversationId =
      options.selectedConversationId !== undefined
        ? options.selectedConversationId
        : this.data.consoleSelectedConversationId || "";
    if (!visibleConversations.some((conversation) => conversation.id === selectedConversationId)) {
      selectedConversationId = visibleConversations[0] ? visibleConversations[0].id : "";
    }
    const selectedConversation =
      visibleConversations.find((conversation) => conversation.id === selectedConversationId) || null;
    const suggested = buildConsoleSuggestedFollowups(selectedConversation);
    this.setData({
      consoleAllConversations: allConversations,
      consoleConversations: visibleConversations,
      consoleFilterTopicId: filterTopicId,
      consoleSelectedConversationId: selectedConversationId,
      consoleSelectedConversation: selectedConversation,
      consoleSuggestedFollowups: suggested,
    });
    if (selectedConversation && selectedConversation.job_id) {
      this.loadResearchConsoleTimeline(selectedConversation.job_id);
      return;
    }
    this.setData({ consoleTimeline: [] });
  },

  loadResearchConsole(preserveSelection = false) {
    this.setData({
      consoleLoading: true,
      consoleError: "",
    });
    listResearchConversations()
      .then((conversations) => {
        const normalized = (Array.isArray(conversations) ? conversations : []).map(normalizeConversation);
        this.syncResearchConsoleState({
          allConversations: normalized,
          selectedConversationId: preserveSelection ? this.data.consoleSelectedConversationId : "",
        });
      })
      .catch(() => {
        this.setData({
          consoleError: this.data.i18n.consoleRefreshFailed,
          consoleAllConversations: [],
          consoleConversations: [],
          consoleSelectedConversationId: "",
          consoleSelectedConversation: null,
          consoleTimeline: [],
          consoleSuggestedFollowups: [],
        });
      })
      .finally(() => {
        this.setData({ consoleLoading: false });
      });
  },

  loadResearchConsoleTimeline(jobId) {
    if (!jobId) {
      this.setData({ consoleTimeline: [] });
      return;
    }
    getResearchJobTimeline(jobId)
      .then((timeline) => {
        this.setData({
          consoleTimeline: Array.isArray(timeline) ? timeline : [],
        });
      })
      .catch(() => {
        this.setData({ consoleTimeline: [] });
      });
  },

  setConsoleTopicFilter(e) {
    const topicId = e.currentTarget.dataset.topicId || "all";
    this.syncResearchConsoleState({
      filterTopicId: topicId,
      selectedConversationId: "",
    });
  },

  openConsoleConversation(e) {
    const conversationId = e.currentTarget.dataset.id;
    if (!conversationId) return;
    this.syncResearchConsoleState({ selectedConversationId: conversationId });
  },

  onConsoleDraftInput(e) {
    this.setData({ consoleDraft: (e.detail && e.detail.value) || "" });
  },

  useConsoleFollowup(e) {
    const value = e.currentTarget.dataset.value;
    if (!value) return;
    this.setData({ consoleDraft: value });
  },

  createConsoleConversation() {
    const topicId =
      this.data.consoleFilterTopicId && this.data.consoleFilterTopicId !== "all"
        ? this.data.consoleFilterTopicId
        : ((this.data.trackingTopics || [])[0] && (this.data.trackingTopics || [])[0].id) || null;
    const topic = (this.data.trackingTopics || []).find((item) => item.id === topicId);
    this.setData({ consoleSubmitting: true, consoleError: "" });
    return createResearchConversation({
      title: topic && topic.name ? `${topic.name} 继续追问` : "研究对话",
      topic_id: topicId || undefined,
    })
      .then((conversation) => {
        const normalized = normalizeConversation(conversation);
        const allConversations = [normalized].concat(
          (this.data.consoleAllConversations || []).filter((item) => item.id !== normalized.id)
        );
        this.syncResearchConsoleState({
          allConversations,
          selectedConversationId: normalized.id,
          filterTopicId: this.data.consoleFilterTopicId || "all",
        });
        return normalized;
      })
      .catch(() => {
        this.setData({ consoleError: this.data.i18n.consoleRefreshFailed });
        return null;
      })
      .finally(() => {
        this.setData({ consoleSubmitting: false });
      });
  },

  submitConsoleMessage() {
    const content = String(this.data.consoleDraft || "").trim();
    if (!content || this.data.consoleSubmitting) return;
    this.setData({ consoleSubmitting: true, consoleError: "" });
    const ensureConversation = this.data.consoleSelectedConversation
      ? Promise.resolve(this.data.consoleSelectedConversation)
      : createResearchConversation({
          title:
            ((this.data.trackingTopics || []).find((item) => item.id === this.data.consoleFilterTopicId) || {}).name
              ? `${((this.data.trackingTopics || []).find((item) => item.id === this.data.consoleFilterTopicId) || {}).name} 继续追问`
              : "研究对话",
          topic_id:
            this.data.consoleFilterTopicId && this.data.consoleFilterTopicId !== "all"
              ? this.data.consoleFilterTopicId
              : undefined,
        }).then((conversation) => {
          const normalized = normalizeConversation(conversation);
          const allConversations = [normalized].concat(
            (this.data.consoleAllConversations || []).filter((item) => item.id !== normalized.id)
          );
          this.syncResearchConsoleState({
            allConversations,
            selectedConversationId: normalized.id,
          });
          return normalized;
        });
    ensureConversation
      .then((conversation) => {
        if (!conversation || !conversation.id) {
          throw new Error("missing conversation");
        }
        return sendResearchConversationMessage(conversation.id, { content });
      })
      .then((conversation) => {
        const normalized = normalizeConversation(conversation);
        const allConversations = [normalized].concat(
          (this.data.consoleAllConversations || []).filter((item) => item.id !== normalized.id)
        );
        this.setData({ consoleDraft: "" });
        this.syncResearchConsoleState({
          allConversations,
          selectedConversationId: normalized.id,
        });
      })
      .catch(() => {
        this.setData({ consoleError: this.data.i18n.consoleRefreshFailed });
      })
      .finally(() => {
        this.setData({ consoleSubmitting: false });
      });
  },

  loadData() {
    const query = String(this.data.query || "").trim();
    const focusOnly = !!this.data.focusOnly;
    this.setData({ loading: true, error: "" });
    Promise.all([
      listKnowledgeEntries(40, { sourceDomain: "research.report", query: query || undefined, focusReferenceOnly: focusOnly }),
      listKnowledgeEntries(60, { sourceDomain: "research.action_card", query: query || undefined, focusReferenceOnly: focusOnly }),
    ])
      .then(([reportRes, actionRes]) => {
        const reports = sortEntries((reportRes.items || []).map((item) => normalizeResearchEntry(item, "report")));
        const actions = sortEntries((actionRes.items || []).map((item) => normalizeResearchEntry(item, "action")));
        const combined = sortEntries([].concat(reports, actions));
        this.setData({
          reports,
          actions,
          regionOptions: buildFacetOptions(combined.map((item) => item.region_label), this.data.i18n.regionAll),
          industryOptions: buildFacetOptions(combined.map((item) => item.industry_label), this.data.i18n.industryAll),
          actionTypeOptions: buildFacetOptions(actions.map((item) => item.action_type), this.data.i18n.actionTypeAll),
        }, () => this.syncVisibleItems());
      })
      .catch(() => {
        this.setData({
          error: this.data.i18n.loadFailed,
          reports: [],
          actions: [],
          visibleItems: [],
          regionOptions: [],
          industryOptions: [],
          actionTypeOptions: [],
        });
      })
      .finally(() => {
        this.setData({ loading: false });
      });
  },

  syncVisibleItems() {
    const filter = this.data.filter || "all";
    const perspective = this.data.perspective || "all";
    let visibleItems = [];
    if (filter === "reports") {
      visibleItems = this.data.reports || [];
    } else if (filter === "actions") {
      visibleItems = this.data.actions || [];
    } else {
      visibleItems = sortEntries([].concat(this.data.reports || [], this.data.actions || []));
    }
    const regionFilter = this.data.regionFilter || "";
    const industryFilter = this.data.industryFilter || "";
    const actionTypeFilter = this.data.actionTypeFilter || "";
    visibleItems = visibleItems.filter((item) => {
      if (regionFilter && item.region_label !== regionFilter) return false;
      if (industryFilter && item.industry_label !== industryFilter) return false;
      if (actionTypeFilter) {
        if (item.kind !== "action") return false;
        if (item.action_type !== actionTypeFilter) return false;
      }
      if (getResearchPerspectiveScore(item, perspective) <= 0) return false;
      return true;
    });
    visibleItems = visibleItems.sort((left, right) => {
      const scoreGap = getResearchPerspectiveScore(right, perspective) - getResearchPerspectiveScore(left, perspective);
      if (scoreGap !== 0) return scoreGap;
      const leftTime = new Date((left && (left.updated_at || left.created_at)) || 0).getTime();
      const rightTime = new Date((right && (right.updated_at || right.created_at)) || 0).getTime();
      return rightTime - leftTime;
    });
    const allItems = sortEntries([].concat(this.data.reports || [], this.data.actions || []));
    const perspectiveMeta = this.getPerspectiveMeta();
    const activePerspective = perspectiveMeta.find((item) => item.key === perspective) || perspectiveMeta[0];
    const activeFilters = [
      regionFilter ? `${this.data.i18n.regionLabel} · ${regionFilter}` : "",
      industryFilter ? `${this.data.i18n.industryLabel} · ${industryFilter}` : "",
      actionTypeFilter ? `${this.data.i18n.actionTypeLabel} · ${actionTypeFilter}` : "",
      this.data.focusOnly ? this.data.i18n.focusOnlyOn : "",
      this.data.query ? `搜索 · ${this.data.query}` : "",
      perspective !== "all" ? `${this.data.i18n.perspectiveLabel} · ${activePerspective.label}` : "",
    ].filter(Boolean);
    const summaryCards = [
      { label: this.data.i18n.metricAll, value: String(allItems.length), tone: "default" },
      { label: this.data.i18n.metricReports, value: String((this.data.reports || []).length), tone: "report" },
      { label: this.data.i18n.metricActions, value: String((this.data.actions || []).length), tone: "action" },
      {
        label: this.data.i18n.metricFocus,
        value: String(allItems.filter((item) => !!item.is_focus_reference).length),
        tone: "focus",
      },
    ];
    this.setData({ visibleItems, activeFilters, summaryCards, activePerspectiveDesc: activePerspective.desc });
  },

  getPerspectiveMeta() {
    return [
      { key: "all", label: this.data.i18n.viewAll, desc: this.data.i18n.viewAllDesc },
      { key: "regional", label: this.data.i18n.viewRegional, desc: this.data.i18n.viewRegionalDesc },
      { key: "client_followup", label: this.data.i18n.viewClient, desc: this.data.i18n.viewClientDesc },
      { key: "bidding", label: this.data.i18n.viewBidding, desc: this.data.i18n.viewBiddingDesc },
      { key: "ecosystem", label: this.data.i18n.viewEcosystem, desc: this.data.i18n.viewEcosystemDesc },
    ];
  },

  onQueryInput(e) {
    this.setData({ query: e.detail.value || "" });
  },

  submitSearch() {
    this.loadData();
  },

  setFilter(e) {
    this.setData({ filter: e.currentTarget.dataset.key || "all" }, () => this.syncVisibleItems());
  },

  setPerspective(e) {
    this.setData({ perspective: e.currentTarget.dataset.key || "all" }, () => this.syncVisibleItems());
  },

  onRegionChange(e) {
    const index = Number((e.detail && e.detail.value) || 0);
    const option = (this.data.regionOptions || [])[index] || "";
    this.setData({ regionFilter: index === 0 ? "" : option }, () => this.syncVisibleItems());
  },

  onIndustryChange(e) {
    const index = Number((e.detail && e.detail.value) || 0);
    const option = (this.data.industryOptions || [])[index] || "";
    this.setData({ industryFilter: index === 0 ? "" : option }, () => this.syncVisibleItems());
  },

  onActionTypeChange(e) {
    const index = Number((e.detail && e.detail.value) || 0);
    const option = (this.data.actionTypeOptions || [])[index] || "";
    this.setData({ actionTypeFilter: index === 0 ? "" : option }, () => this.syncVisibleItems());
  },

  toggleFocusOnly() {
    this.setData({ focusOnly: !this.data.focusOnly }, () => this.loadData());
  },

  clearFilters() {
    this.setData({
      query: "",
      filter: "all",
      perspective: "all",
      focusOnly: false,
      regionFilter: "",
      industryFilter: "",
      actionTypeFilter: "",
    }, () => this.loadData());
  },

  toggleSourcePanel() {
    this.setData({ sourcePanelOpen: !this.data.sourcePanelOpen });
  },

  toggleResearchSource(e) {
    if (this.data.sourceSaving) return;
    const key = e.currentTarget.dataset.key;
    if (!key) return;
    const current = this.data.sourceSettings || {};
    const payload = {
      enable_jianyu_tender_feed:
        key === "enable_jianyu_tender_feed"
          ? !current.enable_jianyu_tender_feed
          : !!current.enable_jianyu_tender_feed,
      enable_yuntoutiao_feed:
        key === "enable_yuntoutiao_feed"
          ? !current.enable_yuntoutiao_feed
          : !!current.enable_yuntoutiao_feed,
      enable_ggzy_feed:
        key === "enable_ggzy_feed"
          ? !current.enable_ggzy_feed
          : !!current.enable_ggzy_feed,
      enable_cecbid_feed:
        key === "enable_cecbid_feed"
          ? !current.enable_cecbid_feed
          : !!current.enable_cecbid_feed,
      enable_ccgp_feed:
        key === "enable_ccgp_feed"
          ? !current.enable_ccgp_feed
          : !!current.enable_ccgp_feed,
      enable_gov_policy_feed:
        key === "enable_gov_policy_feed"
          ? !current.enable_gov_policy_feed
          : !!current.enable_gov_policy_feed,
      enable_local_ggzy_feed:
        key === "enable_local_ggzy_feed"
          ? !current.enable_local_ggzy_feed
          : !!current.enable_local_ggzy_feed,
    };
    this.setData({ sourceSaving: true });
    updateResearchSourceSettings(payload)
      .then((res) => {
        this.setData({ sourceSettings: res });
      })
      .finally(() => {
        this.setData({ sourceSaving: false });
      });
  },

  saveCurrentView() {
    const payload = {
      name: `${(this.data.query || this.data.i18n.viewAll || "全部视角").trim() || "全部视角"} · ${formatDateLabel(new Date().toISOString())}`,
      query: this.data.query || "",
      filter_mode: this.data.filter || "all",
      perspective: this.data.perspective || "all",
      region_filter: this.data.regionFilter || "",
      industry_filter: this.data.industryFilter || "",
      action_type_filter: this.data.actionTypeFilter || "",
      focus_only: !!this.data.focusOnly,
    };
    this.setData({ workspaceSaving: true });
    saveResearchView(payload)
      .then((saved) => {
        const next = [saved].concat((this.data.savedViews || []).filter((item) => item.id !== saved.id));
        this.setData({ savedViews: next.slice(0, 12) });
      })
      .finally(() => {
        this.setData({ workspaceSaving: false });
      });
  },

  applySavedView(e) {
    const id = e.currentTarget.dataset.id;
    const view = (this.data.savedViews || []).find((item) => item.id === id);
    if (!view) return;
    this.setData({
      query: view.query || "",
      filter: view.filter_mode || "all",
      perspective: view.perspective || "all",
      regionFilter: view.region_filter || "",
      industryFilter: view.industry_filter || "",
      actionTypeFilter: view.action_type_filter || "",
      focusOnly: !!view.focus_only,
    }, () => this.loadData());
  },

  deleteSavedView(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    this.setData({ workspaceSaving: true });
    deleteResearchView(id)
      .then(() => {
        this.setData({
          savedViews: (this.data.savedViews || []).filter((item) => item.id !== id),
        });
      })
      .finally(() => {
        this.setData({ workspaceSaving: false });
      });
  },

  saveTrackingTopic() {
    const fallback = this.data.visibleItems && this.data.visibleItems[0];
    const payload = {
      name: `${(this.data.query || (fallback && fallback.title) || "长期专题").trim().slice(0, 24)} 跟踪`,
      keyword: (this.data.query || (fallback && fallback.title) || "").trim(),
      research_focus: (this.data.activeFilters || []).join(" / "),
      perspective: this.data.perspective || "all",
      region_filter: this.data.regionFilter || "",
      industry_filter: this.data.industryFilter || "",
      notes: (fallback && fallback.preview_summary) || "",
    };
    if (!payload.keyword) return;
    this.setData({ workspaceSaving: true });
    saveResearchTrackingTopic(payload)
      .then((saved) => {
        const next = [saved].concat((this.data.trackingTopics || []).filter((item) => item.id !== saved.id));
        this.setData({ trackingTopics: next.slice(0, 12) });
      })
      .finally(() => {
        this.setData({ workspaceSaving: false });
      });
  },

  applyTrackingTopic(e) {
    const id = e.currentTarget.dataset.id;
    const topic = (this.data.trackingTopics || []).find((item) => item.id === id);
    if (!topic) return;
    this.setData({
      query: topic.keyword || "",
      perspective: topic.perspective || "all",
      regionFilter: topic.region_filter || "",
      industryFilter: topic.industry_filter || "",
      actionTypeFilter: "",
      focusOnly: false,
    }, () => this.loadData());
  },

  deleteTrackingTopic(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    this.setData({ workspaceSaving: true });
    deleteResearchTrackingTopic(id)
      .then(() => {
        this.setData({
          trackingTopics: (this.data.trackingTopics || []).filter((item) => item.id !== id),
        });
      })
      .finally(() => {
        this.setData({ workspaceSaving: false });
      });
  },

  refreshTrackingTopic(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    this.setData({
      refreshingTopicId: id,
      trackingTopics: (this.data.trackingTopics || []).map((item) =>
        item.id === id
          ? {
              ...item,
              last_refresh_status: "running",
              last_refresh_status_label: "刷新中",
              last_refresh_status_tone: "quality-info",
              last_refresh_note: "正在刷新专题研报并补充新增情报",
              last_refresh_error: "",
            }
          : item
      ),
    });
    refreshResearchTrackingTopic(id, {
      output_language: "zh-CN",
      include_wechat: true,
      max_sources: 12,
      save_to_knowledge: true,
    })
      .then((res) => {
        const next = (this.data.trackingTopics || []).map((item) => (item.id === id ? normalizeTrackingTopic(res.topic) : item));
        this.setData({ trackingTopics: next });
      })
      .catch(() => {
        this.setData({
          trackingTopics: (this.data.trackingTopics || []).map((item) =>
            item.id === id
              ? {
                  ...item,
                  last_refresh_status: "failed",
                  last_refresh_status_label: "刷新失败",
                  last_refresh_status_tone: "quality-low",
                  last_refresh_note: "专题刷新失败，请检查当前关键词公开源与模型链路",
                }
              : item
          ),
        });
        wx.showToast({
          title: "刷新失败",
          icon: "none",
        });
      })
      .finally(() => {
        this.setData({ refreshingTopicId: "" });
      });
  },

  createWatchlistFromTopic(e) {
    const id = e.currentTarget.dataset.id;
    const topic = (this.data.trackingTopics || []).find((item) => item.id === id);
    if (!topic) return;
    this.setData({ workspaceSaving: true });
    createResearchWatchlist({
      name: `${topic.name} Watchlist`,
      watch_type: "topic",
      query: topic.keyword,
      tracking_topic_id: topic.id,
      research_focus: topic.research_focus || "",
      perspective: topic.perspective || "all",
      region_filter: topic.region_filter || "",
      industry_filter: topic.industry_filter || "",
      alert_level: "medium",
      schedule: "manual",
    })
      .then((saved) => {
        const next = [saved].concat((this.data.watchlists || []).filter((item) => item.id !== saved.id));
        this.setData({ watchlists: next.slice(0, 12) });
      })
      .finally(() => {
        this.setData({ workspaceSaving: false });
      });
  },

  refreshWatchlist(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    this.setData({ refreshingWatchlistId: id });
    refreshResearchWatchlist(id, {
      output_language: "zh-CN",
      include_wechat: true,
      max_sources: 12,
      save_to_knowledge: true,
    })
      .then((res) => {
        const nextWatchlists = (this.data.watchlists || []).map((item) => (item.id === id ? res.watchlist : item));
        const nextTopics = (this.data.trackingTopics || []).map((item) => (item.id === res.topic.id ? normalizeTrackingTopic(res.topic) : item));
        this.setData({
          watchlists: nextWatchlists,
          trackingTopics: nextTopics,
        });
      })
      .catch(() => {
        wx.showToast({
          title: "刷新失败",
          icon: "none",
        });
      })
      .finally(() => {
        this.setData({ refreshingWatchlistId: "" });
      });
  },

  openEntry(e) {
    const entryId = e.currentTarget.dataset.id;
    if (!entryId) return;
    wx.navigateTo({
      url: `/pages/knowledge/index?id=${entryId}`
    });
  },
});
