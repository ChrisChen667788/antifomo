const {
  createTask,
  getKnowledgeBatchMarkdown,
  getKnowledgeEntry,
  getKnowledgeMarkdown,
  getKnowledgeRule,
  listRelatedKnowledgeEntries,
  listKnowledgeEntries,
  mergeKnowledgeEntries,
  sendWorkBuddyWebhook,
  updateKnowledgeEntry,
  updateKnowledgeEntriesBatch,
  updateKnowledgeRule
} = require("../../utils/api");
const { t } = require("../../utils/i18n");
const { getPreferenceClass } = require("../../utils/preferences");
const RULE_THRESHOLDS = [3.8, 4.0, 4.3];

function buildRuleThresholdOptions(rule) {
  const current = rule || { min_score_value: 4.0 };
  return RULE_THRESHOLDS.map((value) => ({
    value,
    label: value.toFixed(1),
    active: Math.abs(Number(current.min_score_value || 4.0) - value) < 0.01
  }));
}

function buildRuleExplain(i18n, rule) {
  if (!rule) return "";
  const parts = [];
  parts.push(`${i18n.ruleThreshold} ${Number(rule.min_score_value || 4).toFixed(1)}`);
  if (rule.archive_on_like) parts.push(i18n.ruleLike);
  if (rule.archive_on_save) parts.push(i18n.ruleSave);
  return parts.join(" · ");
}

function buildCollectionOptions(entries, i18n) {
  const options = [
    { key: "all", label: i18n.groupAll || "全部分组" },
    { key: "focus_ref", label: i18n.groupFocusRef || "Focus 参考" },
    { key: "pinned", label: i18n.groupPinned || "仅看置顶" },
    { key: "ungrouped", label: i18n.groupUngrouped || "未分组" }
  ];
  const seen = new Set();
  (entries || []).forEach((entry) => {
    const name = String(entry.collection_name || "").trim();
    if (!name || seen.has(name)) return;
    seen.add(name);
    options.push({ key: name, label: name });
  });
  return options;
}

function buildKnowledgeOverview(entries) {
  const list = Array.isArray(entries) ? entries : [];
  return {
    total: list.length,
    focusReferenceCount: list.filter((entry) => !!entry.is_focus_reference).length,
    pinnedCount: list.filter((entry) => !!entry.is_pinned).length
  };
}

function safeMarkdownFilename(filename) {
  const normalized = String(filename || "knowledge-card.md")
    .replace(/[\\/:*?"<>|]/g, "")
    .trim();
  return normalized || "knowledge-card.md";
}

function buildBatchExportTitle(entries, i18n) {
  const list = Array.isArray(entries) ? entries.filter(Boolean) : [];
  if (!list.length) {
    return i18n.batchExportTitle || "知识库批量导出";
  }
  if (list.length === 1) {
    return `${list[0].title || i18n.title} - ${i18n.batchExportTitle || "知识库批量导出"}`;
  }
  return `${list[0].title || i18n.title} + ${list.length - 1} ${i18n.batchExportTitleSuffix || "条补充卡片"}`;
}

function buildBatchMarkdownFallback(entries, i18n, title) {
  const resolvedTitle = title || i18n.batchExportTitle || "知识库批量导出";
  const lines = [
    `# ${resolvedTitle}`,
    "",
    `- ${i18n.batchExportCount || "卡片数量"}：${entries.length}`,
    "",
  ];
  entries.forEach((entry, index) => {
    lines.push(`## ${index + 1}. ${entry.title}`);
    lines.push("");
    lines.push(`- ${i18n.source}：${entry.source_domain || i18n.unknownSource}`);
    if (entry.collection_name) {
      lines.push(`- ${i18n.group}：${entry.collection_name}`);
    }
    lines.push(`- ${i18n.pinned}：${entry.is_pinned ? "Yes" : "No"}`);
    lines.push(`- ${i18n.focusRef}：${entry.is_focus_reference ? "Yes" : "No"}`);
    lines.push("");
    lines.push(entry.content || "");
    lines.push("");
  });
  return lines.join("\n");
}

function buildMergePreview(entries, selectedEntryIds, mergeTitle, i18n) {
  const selectedIds = Array.isArray(selectedEntryIds) ? selectedEntryIds : [];
  if (!selectedIds.length) {
    return null;
  }
  const order = new Map(selectedIds.map((id, index) => [id, index]));
  const selectedEntries = (entries || [])
    .filter((entry) => order.has(entry.id))
    .sort((left, right) => (order.get(left.id) || 0) - (order.get(right.id) || 0));
  if (!selectedEntries.length) {
    return null;
  }

  const typedTitle = String(mergeTitle || "").trim();
  let autoTitle = typedTitle;
  if (!autoTitle) {
    const uniqueTitles = [];
    selectedEntries.forEach((entry) => {
      const title = String(entry.title || "").trim();
      if (title && uniqueTitles.indexOf(title) === -1) {
        uniqueTitles.push(title);
      }
    });
    if (uniqueTitles.length === 1) {
      autoTitle = `${uniqueTitles[0]} / ${i18n.mergePreviewSuffix || "综合卡片"}`;
    } else {
      autoTitle = `${uniqueTitles[0] || i18n.title} + ${Math.max(0, uniqueTitles.length - 1)} ${i18n.mergePreviewPlus || "条延展"}`;
    }
  }

  const collections = selectedEntries
    .map((entry) => String(entry.collection_name || "").trim())
    .filter(Boolean);
  const uniqueCollections = Array.from(new Set(collections));

  return {
    title: autoTitle,
    count: selectedEntries.length,
    titles: selectedEntries.slice(0, 3).map((entry) => entry.title),
    moreCount: Math.max(0, selectedEntries.length - 3),
    inheritPinned: selectedEntries.some((entry) => !!entry.is_pinned),
    inheritFocus: selectedEntries.some((entry) => !!entry.is_focus_reference),
    inheritCollection: uniqueCollections.length === 1 ? uniqueCollections[0] : "",
    ready: selectedEntries.length >= 2
  };
}

function buildResearchMeta(entry) {
  const payload = entry && entry.metadata_payload;
  if (!payload || payload.kind !== "research_report" || !payload.report) {
    return null;
  }
  const report = payload.report;
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
  const normalizeRanked = (items) =>
    (Array.isArray(items) ? items : []).map((entity) => ({
      name: entity && entity.name ? entity.name : "",
      score: Number((entity && entity.score) || 0),
      score_label: scoreLabel(entity && entity.score),
      reasoning: entity && entity.reasoning ? entity.reasoning : "",
      score_breakdown: Array.isArray(entity && entity.score_breakdown)
        ? entity.score_breakdown
            .map((factor) => ({
              label: (factor && factor.label) || "",
              score: Number((factor && factor.score) || 0),
              note: (factor && factor.note) || "",
              score_label: factorLabel(factor && factor.score),
            }))
            .filter((factor) => factor.label)
        : [],
      evidence_links: Array.isArray(entity && entity.evidence_links)
        ? entity.evidence_links
            .map((link) => {
              const tier = String((link && link.source_tier) || "media");
              return {
                title: (link && link.title) || (link && link.url) || "来源待确认",
                url: (link && link.url) || "",
                source_label: (link && link.source_label) || "",
                tier_label: tier === "official" ? "官方源" : tier === "aggregate" ? "聚合源" : "媒体源"
              };
            })
            .filter((link) => link.url)
        : []
    }));
  const buildFallbackRanked = (values, role) =>
    (Array.isArray(values) ? values : [])
      .slice(0, 3)
      .map((value, index) => {
        const name = String((value && value.name) || "").trim();
        const baseScore = role === "target" ? 68 : role === "competitor" ? 64 : 60;
        const score = Number((value && value.score) || Math.max(42, baseScore - index * 6));
        return {
          name,
          score,
          score_label: "待补证",
          reasoning: String((value && value.reasoning) || "当前仍处于待补证阶段，建议继续补官方源或专项交叉验证。"),
          score_breakdown: Array.isArray(value && value.score_breakdown)
            ? value.score_breakdown.map((factor) => ({
                label: factor.label || "",
                score: Number(factor.score || 0),
                score_label: factorLabel(Number(factor.score || 0)),
                note: factor.note || "",
              }))
            : [],
          evidence_links: Array.isArray(value && value.evidence_links)
            ? value.evidence_links
                .map((link) => ({
                  title: (link && link.title) || (link && link.url) || "来源待确认",
                  url: (link && link.url) || "",
                  source_label: (link && link.source_label) || "",
                  tier_label: String((link && link.source_tier) || "media") === "official"
                    ? "官方源"
                    : String((link && link.source_tier) || "media") === "aggregate"
                      ? "聚合源"
                      : "媒体源"
                }))
                .filter((link) => link.url)
            : [],
        };
      })
      .filter((item) => item.name);
  const topTargets = normalizeRanked(report.top_target_accounts);
  const topCompetitors = normalizeRanked(report.top_competitors);
  const topPartners = normalizeRanked(report.top_ecosystem_partners);
  return {
    executive_summary: report.executive_summary || "",
    consulting_angle: report.consulting_angle || "",
    five_year_outlook: Array.isArray(report.five_year_outlook) ? report.five_year_outlook : [],
    top_target_accounts: topTargets.length ? topTargets : buildFallbackRanked(report.pending_target_candidates, "target"),
    top_competitors: topCompetitors.length ? topCompetitors : buildFallbackRanked(report.pending_competitor_candidates, "competitor"),
    top_ecosystem_partners: topPartners.length ? topPartners : buildFallbackRanked(report.pending_partner_candidates, "partner"),
    source_diagnostics: report.source_diagnostics || null,
    evidence_mode: (report.source_diagnostics && report.source_diagnostics.evidence_mode) || "fallback",
    evidence_mode_label: (report.source_diagnostics && report.source_diagnostics.evidence_mode_label) || "兜底候选",
    corrective_triggered: Boolean(report.source_diagnostics && report.source_diagnostics.corrective_triggered),
    expansion_triggered: Boolean(report.source_diagnostics && report.source_diagnostics.expansion_triggered),
    candidate_profile_companies: Array.isArray(report.source_diagnostics && report.source_diagnostics.candidate_profile_companies)
      ? report.source_diagnostics.candidate_profile_companies.slice(0, 4)
      : [],
    candidate_profile_hit_count: Number((report.source_diagnostics && report.source_diagnostics.candidate_profile_hit_count) || 0),
    candidate_profile_official_hit_count: Number((report.source_diagnostics && report.source_diagnostics.candidate_profile_official_hit_count) || 0),
    candidate_profile_source_labels: Array.isArray(report.source_diagnostics && report.source_diagnostics.candidate_profile_source_labels)
      ? report.source_diagnostics.candidate_profile_source_labels.slice(0, 4)
      : [],
    client_peer_moves: Array.isArray(report.client_peer_moves) ? report.client_peer_moves : [],
    winner_peer_moves: Array.isArray(report.winner_peer_moves) ? report.winner_peer_moves : [],
    competition_analysis: Array.isArray(report.competition_analysis) ? report.competition_analysis : [],
    sections: Array.isArray(report.sections)
      ? report.sections.map((section) => ({
          title: section.title || "分析板块",
          items: Array.isArray(section.items) ? section.items : []
        }))
      : []
  };
}

Page({
  data: {
    entryId: "",
    entry: null,
    relatedEntries: [],
    sourceEntries: [],
    entries: [],
    query: "",
    sourceFilter: "all",
    collectionFilter: "all",
    sourceOptions: [],
    collectionOptions: [],
    selectionMode: false,
    selectedEntryIds: [],
    mergeTitle: "",
    batchCollectionName: "",
    mergeBusy: false,
    mergeMessage: "",
    batchExporting: false,
    batchWorkBuddyExporting: false,
    mergePreview: null,
    overview: {
      total: 0,
      focusReferenceCount: 0,
      pinnedCount: 0
    },
    rule: null,
    ruleExplainText: "",
    ruleThresholdOptions: [],
    editingEntry: false,
    entryDraftTitle: "",
    entryDraftContent: "",
    entryDraftCollection: "",
    entrySaving: false,
    entryMessage: "",
    researchMeta: null,
    entryExporting: false,
    entryWorkBuddyExporting: false,
    loading: true,
    loadError: false,
    pageNotice: "",
    pageNoticeTone: "info",
    lastMergedEntryId: "",
    prefClass: "",
    settingsLabel: "设置",
    i18n: {}
  },

  onLoad(options) {
    const entryId = options.id || "";
    this.setData({ entryId });
    this.applyPreferences();
    if (entryId) {
      this.loadEntry(entryId);
    } else {
      this.loadEntries();
    }
  },

  onShow() {
    this.applyPreferences();
    if (!this.data.entryId) {
      this.loadEntries();
    }
  },

  applyPreferences() {
    const app = getApp();
    const preferences = app.globalData.preferences;
    const language = preferences.language;
    const i18n = {
      kicker: t(language, "knowledge.kicker", "知识库"),
      title: t(language, "knowledge.title", "知识卡片"),
      subtitle: t(language, "knowledge.subtitle", "将沉淀下来的结构化理解整理成可复用记录。"),
      researchReportTitle: t(language, "research.structuredReport", "结构化研报"),
      researchSummary: t(language, "inbox.researchSummary", "执行摘要"),
      researchAngle: t(language, "inbox.researchAngle", "咨询价值"),
      researchFiveYear: t(language, "research.fiveYearOutlook", "未来五年演化判断"),
      researchCompetition: t(language, "research.competition", "竞争分析"),
      researchClientPeers: t(language, "research.clientPeers", "甲方同行 Top 3 动态"),
      researchWinnerPeers: t(language, "research.winnerPeers", "中标方同行 Top 3 动态"),
      overviewTitle: t(language, "knowledge.overviewTitle", "知识概览"),
      overviewTotal: t(language, "knowledge.overviewTotal", "总卡片"),
      overviewFocus: t(language, "knowledge.overviewFocus", "Focus 参考"),
      overviewPinned: t(language, "knowledge.overviewPinned", "置顶"),
      selectionSummary: t(language, "knowledge.selectionSummary", "已选中"),
      selectionHint: t(language, "knowledge.selectionHint", "批量操作将作用到当前已选知识卡片"),
      loading: t(language, "knowledge.loading", "正在加载知识卡片..."),
      empty: t(language, "knowledge.empty", "未找到这张知识卡片。"),
      emptyList: t(language, "knowledge.emptyList", "知识库里还没有内容，先在详情页加入一张卡片。"),
      emptyListHint: t(language, "knowledge.emptyListHint", "先从今日重点里加入一张卡片，知识库才会开始积累。"),
      loadFailedTitle: t(language, "common.loadingFailed", "加载失败"),
      loadFailedHint: t(language, "knowledge.loadFailedHint", "知识库暂时不可用，可以先重试，或回到首页继续浏览。"),
      latest: t(language, "knowledge.latest", "最近加入"),
      retryLoad: t(language, "common.retryLoad", "重新加载"),
      backToFeed: t(language, "knowledge.backToFeed", "返回首页"),
      openMerged: t(language, "knowledge.openMerged", "打开新卡片"),
      mergeTitle: t(language, "knowledge.mergeTitle", "知识卡片合并"),
      mergeHint: t(language, "knowledge.mergeHint", "勾选 2 条及以上卡片后可合并为新卡片"),
      mergePlaceholder: t(language, "knowledge.mergePlaceholder", "可选：为合并后的卡片指定标题"),
      mergeAction: t(language, "knowledge.mergeAction", "合并为新卡片"),
      merging: t(language, "knowledge.merging", "合并中..."),
      mergeSelectionHint: t(language, "knowledge.mergeSelectionHint", "建议先选同主题卡片，再补一个自然语言标题。"),
      mergePreviewTitle: t(language, "knowledge.mergePreviewTitle", "合并预览"),
      mergePreviewHint: t(language, "knowledge.mergePreviewHint", "新卡片会继承选中卡片里更稳定的组织状态。"),
      mergePreviewReady: t(language, "knowledge.mergePreviewReady", "已满足合并条件"),
      mergePreviewWaiting: t(language, "knowledge.mergePreviewWaiting", "至少再选 1 张卡片才可合并"),
      mergePreviewSuffix: t(language, "knowledge.mergePreviewSuffix", "综合卡片"),
      mergePreviewPlus: t(language, "knowledge.mergePreviewPlus", "条延展"),
      inheritPinned: t(language, "knowledge.inheritPinned", "继承置顶"),
      inheritFocusRef: t(language, "knowledge.inheritFocusRef", "继承 Focus 参考"),
      inheritCollection: t(language, "knowledge.inheritCollection", "继承分组"),
      batchPin: t(language, "knowledge.batchPin", "批量置顶"),
      batchUnpin: t(language, "knowledge.batchUnpin", "批量取消置顶"),
      batchFocusAdd: t(language, "knowledge.batchFocusAdd", "批量加入 Focus 参考"),
      batchFocusRemove: t(language, "knowledge.batchFocusRemove", "批量移出 Focus 参考"),
      batchGroupApply: t(language, "knowledge.batchGroupApply", "批量设分组"),
      batchGroupPlaceholder: t(language, "knowledge.batchGroupPlaceholder", "为选中卡片设置分组"),
      batchExport: t(language, "knowledge.batchExport", "批量导出 Markdown"),
      batchExportWorkBuddy: t(language, "knowledge.batchExportWorkBuddy", "批量通过 WorkBuddy 导出"),
      batchExporting: t(language, "knowledge.batchExporting", "批量导出中..."),
      batchExportDone: t(language, "knowledge.batchExportDone", "已导出选中知识卡片"),
      batchExportFallback: t(language, "knowledge.batchExportFallback", "已使用本地内容回退导出"),
      batchExportWorkBuddyDone: t(language, "knowledge.batchExportWorkBuddyDone", "已通过 WorkBuddy 导出选中知识卡片"),
      batchExportWorkBuddyFallback: t(language, "knowledge.batchExportWorkBuddyFallback", "WorkBuddy 不可用，已回退直连导出"),
      batchExportWorkBuddyFailed: t(language, "knowledge.batchExportWorkBuddyFailed", "批量导出失败，请稍后重试"),
      batchExportTitle: t(language, "knowledge.batchExportTitle", "知识库批量导出"),
      batchExportTitleSuffix: t(language, "knowledge.batchExportTitleSuffix", "条补充卡片"),
      batchExportCount: t(language, "knowledge.batchExportCount", "卡片数量"),
      batchDone: t(language, "knowledge.batchDone", "批量更新已完成"),
      batchFailed: t(language, "knowledge.batchFailed", "批量更新失败，请稍后重试"),
      mergeCreated: t(language, "knowledge.mergeCreated", "已生成新的合并知识卡片"),
      mergeFailed: t(language, "knowledge.mergeFailed", "合并失败，请稍后重试"),
      mergeCreatedHint: t(language, "knowledge.mergeCreatedHint", "新卡片已经继承常用状态，可继续编辑或直接加入 Focus。"),
      selectMode: t(language, "knowledge.selectMode", "选择合并"),
      exitSelectMode: t(language, "knowledge.exitSelectMode", "完成选择"),
      select: t(language, "knowledge.select", "选择"),
      selected: t(language, "knowledge.selected", "已选中"),
      searchPlaceholder: t(language, "knowledge.searchPlaceholder", "搜索标题、笔记或来源"),
      filterAll: t(language, "knowledge.filterAll", "全部来源"),
      source: t(language, "knowledge.source", "来源"),
      createdAt: t(language, "knowledge.createdAt", "创建时间"),
      content: t(language, "knowledge.content", "卡片内容"),
      openItem: t(language, "knowledge.openItem", "打开原内容详情"),
      openRelated: t(language, "knowledge.openRelated", "打开关联卡片"),
      unknownSource: t(language, "common.unknownSource", "未知来源"),
      copyMarkdown: t(language, "knowledge.copyMarkdown", "复制 Markdown"),
      copyMarkdownDone: t(language, "knowledge.copyMarkdownDone", "Markdown 已复制"),
      copyMarkdownFailed: t(language, "knowledge.copyMarkdownFailed", "复制失败，请稍后重试"),
      relatedTitle: t(language, "knowledge.relatedTitle", "关联卡片"),
      relatedSubtitle: t(language, "knowledge.relatedSubtitle", "这些卡片和当前主题接近，适合继续串联或合并。"),
      group: t(language, "knowledge.group", "分组"),
      groupPlaceholder: t(language, "knowledge.groupPlaceholder", "输入分组名称，例如：AI 制药"),
      groupAll: t(language, "knowledge.groupAll", "全部分组"),
      groupFocusRef: t(language, "knowledge.groupFocusRef", "Focus 参考"),
      groupPinned: t(language, "knowledge.groupPinned", "仅看置顶"),
      groupUngrouped: t(language, "knowledge.groupUngrouped", "未分组"),
      focusRef: t(language, "knowledge.focusRef", "Focus 参考"),
      focusRefAdd: t(language, "knowledge.focusRefAdd", "加入 Focus 参考"),
      focusRefRemove: t(language, "knowledge.focusRefRemove", "移出 Focus 参考"),
      focusRefAdded: t(language, "knowledge.focusRefAdded", "已加入 Focus 参考"),
      focusRefRemoved: t(language, "knowledge.focusRefRemoved", "已移出 Focus 参考"),
      focusRefFailed: t(language, "knowledge.focusRefFailed", "Focus 参考更新失败，请稍后重试"),
      pin: t(language, "knowledge.pin", "置顶"),
      unpin: t(language, "knowledge.unpin", "取消置顶"),
      pinned: t(language, "knowledge.pinned", "置顶"),
      pinEnabled: t(language, "knowledge.pinEnabled", "已置顶这张知识卡片"),
      pinDisabled: t(language, "knowledge.pinDisabled", "已取消置顶"),
      pinFailed: t(language, "knowledge.pinFailed", "置顶更新失败，请稍后重试"),
      download: t(language, "knowledge.download", "保存 Markdown"),
      downloading: t(language, "knowledge.downloading", "导出中..."),
      downloadDone: t(language, "knowledge.downloadDone", "Markdown 已保存到本地缓存"),
      downloadFallback: t(language, "knowledge.downloadFallback", "已使用本地内容导出 Markdown"),
      workbuddyExport: t(language, "knowledge.workbuddyExport", "通过 WorkBuddy 导出"),
      workbuddyExporting: t(language, "knowledge.workbuddyExporting", "导出中..."),
      workbuddyDone: t(language, "knowledge.workbuddyDone", "已通过 WorkBuddy 导出 Markdown"),
      workbuddyFallback: t(language, "knowledge.workbuddyFallback", "WorkBuddy 不可用，已回退直连导出"),
      workbuddyFailed: t(language, "knowledge.workbuddyFailed", "导出失败，请稍后重试"),
      rulesTitle: t(language, "knowledge.rulesTitle", "自动归档规则"),
      rulesSubtitle: t(language, "knowledge.rulesSubtitle", "高价值且已感兴趣的内容会自动进入知识库，减少重复整理。"),
      ruleEnabled: t(language, "knowledge.ruleEnabled", "已开启自动归档"),
      ruleDisabled: t(language, "knowledge.ruleDisabled", "自动归档已关闭"),
      ruleThreshold: t(language, "knowledge.ruleThreshold", "最低价值分"),
      ruleLike: t(language, "knowledge.ruleLike", "感兴趣后归档"),
      ruleSave: t(language, "knowledge.ruleSave", "稍后再读后归档"),
      ruleSaved: t(language, "knowledge.ruleSaved", "自动归档规则已更新"),
      ruleSaveFailed: t(language, "knowledge.ruleSaveFailed", "规则更新失败，已保留原设置"),
      ruleUnavailable: t(language, "knowledge.ruleUnavailable", "规则服务暂不可用，当前使用默认规则。"),
      searchSorted: t(language, "knowledge.searchSorted", "搜索结果已按相关度优先排序"),
      latestFirst: t(language, "knowledge.latestFirst", "默认按最新归档时间排序"),
      updatedAt: t(language, "knowledge.updatedAt", "最近更新"),
      edit: t(language, "knowledge.edit", "编辑"),
      editStandalone: t(language, "knowledge.editStandalone", "进入编辑页"),
      editSaved: t(language, "knowledge.editSaved", "知识卡片已保存"),
      editSaveFailed: t(language, "knowledge.editSaveFailed", "保存失败，请稍后重试"),
      editValidation: t(language, "knowledge.editValidation", "标题和内容都需要保留，避免生成空卡片。"),
      openMergeWorkspace: t(language, "knowledge.openMergeWorkspace", "进入正式合并流"),
      offlineNotice: t(language, "knowledge.offlineNotice", "后端未连接，当前显示本地回退结果。"),
      save: t(language, "common.save", "保存"),
      saving: t(language, "common.saving", "保存中..."),
      cancel: t(language, "common.cancel", "取消")
    };
    this.setData({
      prefClass: getPreferenceClass(preferences, app.globalData.systemTheme),
      settingsLabel: t(language, "common.settings", "设置"),
      i18n
    }, () => this.syncMergePreview());
    wx.setNavigationBarTitle({
      title: t(language, "knowledge.title", "知识卡片")
    });
  },

  loadEntries() {
    this.setData({ loading: true, loadError: false });
    Promise.all([listKnowledgeEntries(30), getKnowledgeRule()])
      .then(([res, rule]) => {
        const sourceEntries = res.items || [];
        const sourceOptions = [
          { key: "all", label: this.data.i18n.filterAll || "全部来源" }
        ];
        const seen = new Set();
        sourceEntries.forEach((entry) => {
          const source = entry.source_domain || this.data.i18n.unknownSource;
          if (!seen.has(source)) {
            seen.add(source);
            sourceOptions.push({ key: source, label: source });
          }
        });
        this.setData({
          sourceEntries,
          overview: buildKnowledgeOverview(sourceEntries),
          rule,
          ruleExplainText: buildRuleExplain(this.data.i18n, rule),
          ruleThresholdOptions: buildRuleThresholdOptions(rule),
          selectionMode: false,
          selectedEntryIds: [],
          mergeTitle: "",
          batchCollectionName: "",
          mergeBusy: false,
          mergeMessage: "",
          batchExporting: false,
          batchWorkBuddyExporting: false,
          mergePreview: null,
          sourceOptions,
          collectionFilter: "all",
          collectionOptions: buildCollectionOptions(sourceEntries, this.data.i18n),
          loading: false,
          loadError: false,
          pageNotice: res.fromMock || rule._fromMock ? this.data.i18n.offlineNotice : "",
          pageNoticeTone: res.fromMock || rule._fromMock ? "warning" : "info",
          lastMergedEntryId: ""
        }, () => this.applyFilters());
      })
      .catch(() => {
        this.setData({
          loading: false,
          loadError: true,
          sourceEntries: [],
          entries: [],
          overview: buildKnowledgeOverview([]),
          sourceOptions: [],
          collectionOptions: buildCollectionOptions([], this.data.i18n),
          rule: {
            enabled: true,
            min_score_value: 4.0,
            archive_on_like: true,
            archive_on_save: true
          },
          ruleExplainText: buildRuleExplain(this.data.i18n, {
            enabled: true,
            min_score_value: 4.0,
            archive_on_like: true,
            archive_on_save: true
          }),
          ruleThresholdOptions: buildRuleThresholdOptions({
            enabled: true,
            min_score_value: 4.0,
            archive_on_like: true,
            archive_on_save: true
          }),
          selectionMode: false,
          selectedEntryIds: [],
          mergeTitle: "",
          batchCollectionName: "",
          mergeBusy: false,
          mergeMessage: "",
          batchExporting: false,
          batchWorkBuddyExporting: false,
          mergePreview: null,
          pageNotice: "",
          lastMergedEntryId: ""
        });
      });
  },

  applyFilters() {
    const query = String(this.data.query || "").trim().toLowerCase();
    const sourceFilter = this.data.sourceFilter;
    const collectionFilter = this.data.collectionFilter;
    const entries = (this.data.sourceEntries || [])
      .filter((entry) => {
        const source = entry.source_domain || this.data.i18n.unknownSource;
        if (sourceFilter !== "all" && source !== sourceFilter) {
          return false;
        }
        if (collectionFilter === "focus_ref" && !entry.is_focus_reference) {
          return false;
        }
        if (collectionFilter === "pinned" && !entry.is_pinned) {
          return false;
        }
        if (collectionFilter === "ungrouped" && entry.collection_name) {
          return false;
        }
        if (collectionFilter !== "all" && collectionFilter !== "pinned" && collectionFilter !== "ungrouped" && entry.collection_name !== collectionFilter) {
          return false;
        }
        if (!query) return true;
        const haystack = `${entry.title} ${entry.content} ${source} ${entry.collection_name || ""}`.toLowerCase();
        return haystack.indexOf(query) >= 0;
      })
      .sort((left, right) => {
        if (!query) {
          return (
            Number(!!right.is_focus_reference) - Number(!!left.is_focus_reference)
          ) || (
            Number(!!right.is_pinned) - Number(!!left.is_pinned)
          ) || (Date.parse(right.created_at) - Date.parse(left.created_at));
        }
        const score = (entry) => {
          const title = String(entry.title || "").toLowerCase();
          const content = String(entry.content || "").toLowerCase();
          const source = String(entry.source_domain || "").toLowerCase();
          const collection = String(entry.collection_name || "").toLowerCase();
          let value = 0;
          if (title.indexOf(query) === 0) value += 120;
          else if (title.indexOf(query) >= 0) value += 80;
          if (source.indexOf(query) >= 0) value += 36;
          if (content.indexOf(query) >= 0) value += 24;
          if (collection.indexOf(query) >= 0) value += 30;
          if (entry.is_focus_reference) value += 18;
          if (entry.is_pinned) value += 12;
          value += Math.max(0, 20 - Math.floor((Date.now() - Date.parse(entry.created_at)) / 86400000));
          return value;
        };
        return score(right) - score(left);
      });
    this.setData({ entries });
  },

  onSearchInput(e) {
    this.setData({ query: e.detail.value || "" }, () => this.applyFilters());
  },

  setSourceFilter(e) {
    this.setData({ sourceFilter: e.currentTarget.dataset.key || "all" }, () => this.applyFilters());
  },

  setCollectionFilter(e) {
    this.setData({ collectionFilter: e.currentTarget.dataset.key || "all" }, () => this.applyFilters());
  },

  loadEntry(entryId) {
    this.setData({ loading: true, loadError: false });
    getKnowledgeEntry(entryId)
      .then((entry) => {
        this.setData({
          entry,
          researchMeta: buildResearchMeta(entry),
          relatedEntries: [],
          editingEntry: false,
          entryDraftTitle: entry.title,
          entryDraftContent: entry.content,
          entryDraftCollection: entry.collection_name || "",
          entrySaving: false,
          entryMessage: "",
          entryExporting: false,
          entryWorkBuddyExporting: false,
          loading: false,
          loadError: false,
          pageNotice: entry._fromMock ? this.data.i18n.offlineNotice : "",
          pageNoticeTone: entry._fromMock ? "warning" : "info"
        });
        this.loadRelatedEntries(entryId);
      })
      .catch(() => {
        this.setData({
          loading: false,
          loadError: true,
          entry: null,
          researchMeta: null,
          relatedEntries: [],
          pageNotice: "",
          lastMergedEntryId: ""
        });
      });
  },

  loadRelatedEntries(entryId) {
    listRelatedKnowledgeEntries(entryId, 4)
      .then((res) => {
        this.setData({ relatedEntries: res.items || [] });
      })
      .catch(() => {
        this.setData({ relatedEntries: [] });
      });
  },

  openEntry(e) {
    const entryId = e.currentTarget.dataset.id;
    if (!entryId) return;
    if (this.data.selectionMode) {
      this.toggleSelectEntry(entryId);
      return;
    }
    wx.navigateTo({
      url: `/pages/knowledge/index?id=${entryId}`
    });
  },

  openItem() {
    const itemId = this.data.entry && this.data.entry.item_id;
    if (!itemId) return;
    wx.navigateTo({
      url: `/pages/item/index?id=${itemId}`
    });
  },

  openRelatedEntry(e) {
    const entryId = e.currentTarget.dataset.id;
    if (!entryId) return;
    wx.navigateTo({
      url: `/pages/knowledge/index?id=${entryId}`
    });
  },

  openEditEntry() {
    const entryId = this.data.entry && this.data.entry.id;
    if (!entryId) return;
    wx.navigateTo({
      url: `/pages/knowledge-edit/index?id=${entryId}`
    });
  },

  copyKnowledgeMarkdown() {
    const entry = this.data.entry;
    if (!entry) return;
    const lines = [
      `# ${entry.title}`,
      "",
      `- ${this.data.i18n.source}：${entry.source_domain || this.data.i18n.unknownSource}`,
      `- ${this.data.i18n.createdAt}：${entry.created_at}`
    ];
    if (entry.updated_at) {
      lines.push(`- ${this.data.i18n.updatedAt}：${entry.updated_at}`);
    }
    lines.push("", `## ${this.data.i18n.content}`, "", entry.content);
    wx.setClipboardData({
      data: lines.join("\n"),
      success: () => {
        this.setData({ entryMessage: this.data.i18n.copyMarkdownDone });
      },
      fail: () => {
        this.setData({ entryMessage: this.data.i18n.copyMarkdownFailed });
      }
    });
  },

  saveKnowledgeMarkdownFile(content, filename, successMessage) {
    const filePath = `${wx.env.USER_DATA_PATH}/${safeMarkdownFilename(filename)}`;
    const fs = wx.getFileSystemManager();
    fs.writeFile({
      filePath,
      data: content,
      encoding: "utf8",
      success: () => {
        this.setData({ entryMessage: successMessage || this.data.i18n.downloadDone });
      },
      fail: () => {
        this.setData({ entryMessage: this.data.i18n.downloadFallback });
      }
    });
  },

  getSelectedEntries() {
    const selectedIds = this.data.selectedEntryIds || [];
    const order = new Map(selectedIds.map((id, index) => [id, index]));
    return (this.data.sourceEntries || [])
      .filter((entry) => order.has(entry.id))
      .sort((left, right) => (order.get(left.id) || 0) - (order.get(right.id) || 0));
  },

  downloadKnowledgeMarkdown() {
    const entry = this.data.entry;
    if (!entry || this.data.entryExporting) return;
    this.setData({ entryExporting: true, entryMessage: "" });
    getKnowledgeMarkdown(entry.id)
      .then((result) => {
        this.saveKnowledgeMarkdownFile(result.content, result.filename, this.data.i18n.downloadDone);
      })
      .catch(() => {
        const lines = [
          `# ${entry.title}`,
          "",
          `- ${this.data.i18n.source}：${entry.source_domain || this.data.i18n.unknownSource}`,
          `- ${this.data.i18n.createdAt}：${entry.created_at}`,
          "",
          `## ${this.data.i18n.content}`,
          "",
          entry.content
        ];
        this.saveKnowledgeMarkdownFile(lines.join("\n"), `${entry.title || "knowledge-card"}.md`, this.data.i18n.downloadFallback);
      })
      .finally(() => {
        this.setData({ entryExporting: false });
      });
  },

  exportKnowledgeViaWorkBuddy() {
    const entry = this.data.entry;
    if (!entry || this.data.entryWorkBuddyExporting) return;
    this.setData({ entryWorkBuddyExporting: true, entryMessage: "" });
    sendWorkBuddyWebhook({
      event_type: "create_task",
      request_id: `knowledge_${entry.id}`,
      task_type: "export_knowledge_markdown",
      input_payload: {
        entry_id: entry.id
      }
    })
      .then((res) => {
        const payload = (res && res.task && res.task.output_payload) || {};
        const content = payload.content || `# ${entry.title}\n\n${entry.content}`;
        const filename = payload.filename || `${entry.title || "knowledge-card"}.md`;
        this.saveKnowledgeMarkdownFile(content, filename, this.data.i18n.workbuddyDone);
      })
      .catch(() => {
        return createTask({
          task_type: "export_knowledge_markdown",
          input_payload: { entry_id: entry.id }
        }).then((task) => {
          const payload = task.output_payload || {};
          const content = payload.content || `# ${entry.title}\n\n${entry.content}`;
          const filename = payload.filename || `${entry.title || "knowledge-card"}.md`;
          this.saveKnowledgeMarkdownFile(content, filename, this.data.i18n.workbuddyFallback);
        }).catch(() => {
          this.setData({ entryMessage: this.data.i18n.workbuddyFailed });
        });
      })
      .finally(() => {
        this.setData({ entryWorkBuddyExporting: false });
      });
  },

  toggleSelectionMode() {
    const nextMode = !this.data.selectionMode;
    this.setData({
      selectionMode: nextMode,
      selectedEntryIds: nextMode ? this.data.selectedEntryIds : [],
      mergeMessage: nextMode ? this.data.mergeMessage : "",
      batchExporting: false,
      batchWorkBuddyExporting: false
    }, () => this.syncMergePreview());
  },

  toggleSelectEntry(entryId) {
    const current = this.data.selectedEntryIds || [];
    const next = current.indexOf(entryId) >= 0
      ? current.filter((id) => id !== entryId)
      : current.concat(entryId);
    this.setData({ selectedEntryIds: next }, () => this.syncMergePreview());
  },

  onMergeTitleInput(e) {
    this.setData({ mergeTitle: e.detail.value || "" }, () => this.syncMergePreview());
  },

  openMergeWorkspace() {
    const entryIds = this.data.selectedEntryIds || [];
    if (entryIds.length < 2) return;
    const params = [`ids=${encodeURIComponent(entryIds.join(","))}`];
    const mergeTitle = String(this.data.mergeTitle || "").trim();
    if (mergeTitle) {
      params.push(`title=${encodeURIComponent(mergeTitle)}`);
    }
    wx.navigateTo({
      url: `/pages/knowledge-merge/index?${params.join("&")}`
    });
  },

  onBatchCollectionInput(e) {
    this.setData({ batchCollectionName: e.detail.value || "" });
  },

  mergeSelectedEntries() {
    const entryIds = this.data.selectedEntryIds || [];
    if (entryIds.length < 2 || this.data.mergeBusy) return;
    this.setData({ mergeBusy: true, mergeMessage: "" });
    mergeKnowledgeEntries({
      entry_ids: entryIds,
      title: (this.data.mergeTitle || "").trim() || undefined
    })
      .then((entry) => {
        const sourceEntries = [entry].concat(this.data.sourceEntries || []);
        this.setData({
          sourceEntries,
          overview: buildKnowledgeOverview(sourceEntries),
          selectionMode: false,
          selectedEntryIds: [],
          mergeTitle: "",
          batchCollectionName: "",
          mergeBusy: false,
          mergeMessage: this.data.i18n.mergeCreated,
          lastMergedEntryId: entry.id,
          pageNotice: this.data.i18n.mergeCreatedHint,
          pageNoticeTone: "success",
          mergePreview: null
        }, () => this.applyFilters());
      })
      .catch(() => {
        this.setData({
          mergeBusy: false,
          mergeMessage: this.data.i18n.mergeFailed,
          pageNotice: this.data.i18n.mergeFailed,
          pageNoticeTone: "error"
        });
      });
  },

  applyBatchUpdate(patch, successMessage) {
    const entryIds = this.data.selectedEntryIds || [];
    if (!entryIds.length || this.data.mergeBusy) return;
    this.setData({ mergeBusy: true, mergeMessage: "" });
    updateKnowledgeEntriesBatch({
      entry_ids: entryIds,
      ...patch
    })
      .then((result) => {
        const updatedEntries = result.items || [];
        const updatedMap = {};
        updatedEntries.forEach((entry) => {
          updatedMap[entry.id] = entry;
        });
        const sourceEntries = (this.data.sourceEntries || []).map((entry) => {
          if (!updatedMap[entry.id]) {
            return entry;
          }
          if (result.fromMock) {
            return {
              ...entry,
              ...patch,
              collection_name: Object.prototype.hasOwnProperty.call(patch, "collection_name")
                ? (patch.collection_name || "")
                : entry.collection_name,
            };
          }
          return updatedMap[entry.id];
        });
        this.setData({
          sourceEntries,
          overview: buildKnowledgeOverview(sourceEntries),
          selectionMode: false,
          selectedEntryIds: [],
          batchCollectionName: "",
          mergeBusy: false,
          mergeMessage: successMessage,
          collectionOptions: buildCollectionOptions(sourceEntries, this.data.i18n),
          pageNotice: successMessage,
          pageNoticeTone: "success"
        }, () => {
          this.applyFilters();
          this.syncMergePreview();
        });
      })
      .catch(() => {
        this.setData({
          mergeBusy: false,
          mergeMessage: this.data.i18n.batchFailed,
          pageNotice: this.data.i18n.batchFailed,
          pageNoticeTone: "error"
        });
      });
  },

  syncMergePreview() {
    this.setData({
      mergePreview: this.data.selectionMode
        ? buildMergePreview(this.data.sourceEntries, this.data.selectedEntryIds, this.data.mergeTitle, this.data.i18n)
        : null
    });
  },

  batchPinSelected() {
    this.applyBatchUpdate({ is_pinned: true }, this.data.i18n.batchDone);
  },

  batchUnpinSelected() {
    this.applyBatchUpdate({ is_pinned: false }, this.data.i18n.batchDone);
  },

  batchApplyCollection() {
    const name = String(this.data.batchCollectionName || "").trim();
    this.applyBatchUpdate({ collection_name: name || null }, this.data.i18n.batchDone);
  },

  batchAddFocusSelected() {
    this.applyBatchUpdate({ is_focus_reference: true }, this.data.i18n.focusRefAdded);
  },

  batchRemoveFocusSelected() {
    this.applyBatchUpdate({ is_focus_reference: false }, this.data.i18n.focusRefRemoved);
  },

  batchExportSelected() {
    const selectedEntries = this.getSelectedEntries();
    if (!selectedEntries.length || this.data.batchExporting) return;
    const title = buildBatchExportTitle(selectedEntries, this.data.i18n);
    this.setData({ batchExporting: true, mergeMessage: "" });
    getKnowledgeBatchMarkdown({
      entry_ids: selectedEntries.map((entry) => entry.id),
      title,
      output_language: getApp().globalData.preferences.language
    })
      .then((result) => {
        this.saveKnowledgeMarkdownFile(
          result.content,
          result.filename,
          result._fromMock ? this.data.i18n.batchExportFallback : this.data.i18n.batchExportDone
        );
        this.setData({
          mergeMessage: result._fromMock ? this.data.i18n.batchExportFallback : this.data.i18n.batchExportDone
        });
      })
      .finally(() => {
        this.setData({ batchExporting: false });
      });
  },

  batchExportSelectedViaWorkBuddy() {
    const selectedEntries = this.getSelectedEntries();
    if (!selectedEntries.length || this.data.batchWorkBuddyExporting) return;
    const title = buildBatchExportTitle(selectedEntries, this.data.i18n);
    const entryIds = selectedEntries.map((entry) => entry.id);
    this.setData({ batchWorkBuddyExporting: true, mergeMessage: "" });
    sendWorkBuddyWebhook({
      event_type: "create_task",
      request_id: `knowledge_bundle_${Date.now()}`,
      task_type: "export_knowledge_bundle_markdown",
      input_payload: {
        entry_ids: entryIds,
        title,
        output_language: getApp().globalData.preferences.language
      }
    })
      .then((res) => {
        const payload = (res && res.task && res.task.output_payload) || {};
        const content = payload.content || buildBatchMarkdownFallback(selectedEntries, this.data.i18n, title);
        const filename = payload.filename || `${title}.md`;
        const successMessage = res && res._fromMock
          ? this.data.i18n.batchExportWorkBuddyFallback
          : this.data.i18n.batchExportWorkBuddyDone;
        this.saveKnowledgeMarkdownFile(content, filename, successMessage);
        this.setData({ mergeMessage: successMessage });
      })
      .catch(() => {
        return createTask({
          task_type: "export_knowledge_bundle_markdown",
          input_payload: {
            entry_ids: entryIds,
            title,
            output_language: getApp().globalData.preferences.language
          }
        })
          .then((task) => {
            const payload = task.output_payload || {};
            const content = payload.content || buildBatchMarkdownFallback(selectedEntries, this.data.i18n, title);
            const filename = payload.filename || `${title}.md`;
            this.saveKnowledgeMarkdownFile(content, filename, this.data.i18n.batchExportWorkBuddyFallback);
            this.setData({ mergeMessage: this.data.i18n.batchExportWorkBuddyFallback });
          })
          .catch(() => {
            this.setData({ mergeMessage: this.data.i18n.batchExportWorkBuddyFailed });
          });
      })
      .finally(() => {
        this.setData({ batchWorkBuddyExporting: false });
      });
  },

  startEditEntry() {
    const entry = this.data.entry;
    if (!entry) return;
    this.setData({
      editingEntry: true,
      entryDraftTitle: entry.title || "",
      entryDraftContent: entry.content || "",
      entryDraftCollection: entry.collection_name || "",
      entryMessage: ""
    });
  },

  cancelEditEntry() {
    const entry = this.data.entry;
    this.setData({
      editingEntry: false,
      entryDraftTitle: entry ? entry.title : "",
      entryDraftContent: entry ? entry.content : "",
      entryDraftCollection: entry ? (entry.collection_name || "") : "",
      entryMessage: ""
    });
  },

  toggleEditEntry() {
    if (this.data.editingEntry) {
      this.cancelEditEntry();
      return;
    }
    this.startEditEntry();
  },

  onEntryTitleInput(e) {
    this.setData({ entryDraftTitle: e.detail.value || "" });
  },

  onEntryContentInput(e) {
    this.setData({ entryDraftContent: e.detail.value || "" });
  },

  onEntryCollectionInput(e) {
    this.setData({ entryDraftCollection: e.detail.value || "" });
  },

  saveEntryEdit() {
    const entry = this.data.entry;
    if (!entry || this.data.entrySaving) return;
    const title = String(this.data.entryDraftTitle || "").trim();
    const content = String(this.data.entryDraftContent || "").trim();
    const collectionName = String(this.data.entryDraftCollection || "").trim();
    if (!title || !content) {
      this.setData({ entryMessage: this.data.i18n.editValidation });
      return;
    }

    this.setData({ entrySaving: true, entryMessage: "" });
    updateKnowledgeEntry(entry.id, { title, content, collection_name: collectionName || null })
      .then((updated) => {
        this.setData({
          entry: updated,
          researchMeta: buildResearchMeta(updated),
          entryDraftTitle: updated.title,
          entryDraftContent: updated.content,
          entryDraftCollection: updated.collection_name || "",
          editingEntry: false,
          entrySaving: false,
          entryMessage: this.data.i18n.editSaved,
          pageNotice: this.data.i18n.editSaved,
          pageNoticeTone: "success"
        });
      })
      .catch(() => {
        this.setData({
          entrySaving: false,
          entryMessage: this.data.i18n.editSaveFailed,
          pageNotice: this.data.i18n.editSaveFailed,
          pageNoticeTone: "error"
        });
      });
  },

  toggleEntryPinned() {
    const entry = this.data.entry;
    if (!entry || this.data.entrySaving) return;
    updateKnowledgeEntry(entry.id, { is_pinned: !entry.is_pinned })
      .then((updated) => {
        this.setData({
          entry: updated,
          researchMeta: buildResearchMeta(updated),
          entryDraftCollection: updated.collection_name || "",
          entryMessage: updated.is_pinned ? this.data.i18n.pinEnabled : this.data.i18n.pinDisabled,
          pageNotice: updated.is_pinned ? this.data.i18n.pinEnabled : this.data.i18n.pinDisabled,
          pageNoticeTone: "success"
        });
      })
      .catch(() => {
        this.setData({
          entryMessage: this.data.i18n.pinFailed,
          pageNotice: this.data.i18n.pinFailed,
          pageNoticeTone: "error"
        });
      });
  },

  toggleEntryFocusReference() {
    const entry = this.data.entry;
    if (!entry || this.data.entrySaving) return;
    updateKnowledgeEntry(entry.id, { is_focus_reference: !entry.is_focus_reference })
      .then((updated) => {
        this.setData({
          entry: updated,
          researchMeta: buildResearchMeta(updated),
          entryDraftCollection: updated.collection_name || "",
          entryMessage: updated.is_focus_reference ? this.data.i18n.focusRefAdded : this.data.i18n.focusRefRemoved,
          pageNotice: updated.is_focus_reference ? this.data.i18n.focusRefAdded : this.data.i18n.focusRefRemoved,
          pageNoticeTone: "success"
        });
      })
      .catch(() => {
        this.setData({
          entryMessage: this.data.i18n.focusRefFailed,
          pageNotice: this.data.i18n.focusRefFailed,
          pageNoticeTone: "error"
        });
      });
  },

  openResearchEvidenceLink(e) {
    const url = String((e.currentTarget.dataset && e.currentTarget.dataset.url) || "").trim();
    if (!url) return;
    wx.navigateTo({
      url: `/pages/webview/index?url=${encodeURIComponent(url)}`
    }).catch(() => {
      wx.setClipboardData({ data: url });
    });
  },

  toggleListPinned(e) {
    const entryId = e.currentTarget.dataset.id;
    if (!entryId) return;
    const current = (this.data.sourceEntries || []).find((entry) => entry.id === entryId);
    if (!current) return;
    updateKnowledgeEntry(entryId, { is_pinned: !current.is_pinned })
      .then((updated) => {
        const sourceEntries = (this.data.sourceEntries || []).map((entry) => (entry.id === entryId ? updated : entry));
        this.setData({
          sourceEntries,
          overview: buildKnowledgeOverview(sourceEntries),
          collectionOptions: buildCollectionOptions(sourceEntries, this.data.i18n),
          mergeMessage: updated.is_pinned ? this.data.i18n.pinEnabled : this.data.i18n.pinDisabled,
          pageNotice: updated.is_pinned ? this.data.i18n.pinEnabled : this.data.i18n.pinDisabled,
          pageNoticeTone: "success"
        }, () => this.applyFilters());
      })
      .catch(() => {
        this.setData({
          mergeMessage: this.data.i18n.pinFailed,
          pageNotice: this.data.i18n.pinFailed,
          pageNoticeTone: "error"
        });
      });
  },

  reloadCurrentView() {
    if (this.data.entryId) {
      this.loadEntry(this.data.entryId);
      return;
    }
    this.loadEntries();
  },

  openFeed() {
    wx.switchTab({
      url: "/pages/feed/index"
    });
  },

  openLastMergedEntry() {
    const entryId = this.data.lastMergedEntryId;
    if (!entryId) return;
    wx.navigateTo({
      url: `/pages/knowledge/index?id=${entryId}`
    });
  },

  patchRule(patch) {
    const currentRule = this.data.rule || {
      enabled: true,
      min_score_value: 4.0,
      archive_on_like: true,
      archive_on_save: true
    };
    const optimistic = { ...currentRule, ...patch };
    this.setData({
      rule: optimistic,
      ruleExplainText: buildRuleExplain(this.data.i18n, optimistic),
      ruleThresholdOptions: buildRuleThresholdOptions(optimistic)
    });
    updateKnowledgeRule(patch)
      .then((rule) => {
        this.setData({
          rule,
          ruleExplainText: buildRuleExplain(this.data.i18n, rule),
          ruleThresholdOptions: buildRuleThresholdOptions(rule)
        });
        wx.showToast({ title: this.data.i18n.ruleSaved, icon: "none" });
      })
      .catch(() => {
        this.setData({
          rule: currentRule,
          ruleExplainText: buildRuleExplain(this.data.i18n, currentRule),
          ruleThresholdOptions: buildRuleThresholdOptions(currentRule)
        });
        wx.showToast({ title: this.data.i18n.ruleSaveFailed, icon: "none" });
      });
  },

  toggleRuleEnabled() {
    const rule = this.data.rule;
    if (!rule) return;
    this.patchRule({ enabled: !rule.enabled });
  },

  setRuleThreshold(e) {
    const value = Number(e.currentTarget.dataset.value || 4.0);
    this.patchRule({ min_score_value: value });
  },

  toggleRuleLike() {
    const rule = this.data.rule;
    if (!rule) return;
    this.patchRule({ archive_on_like: !rule.archive_on_like });
  },

  toggleRuleSave() {
    const rule = this.data.rule;
    if (!rule) return;
    this.patchRule({ archive_on_save: !rule.archive_on_save });
  }
});
