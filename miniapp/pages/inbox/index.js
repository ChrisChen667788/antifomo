const {
  createItem,
  createCollectorRssSource,
  createResearchConversation,
  createResearchJob,
  createResearchActionPlan,
  createTask,
  getResearchJob,
  flushPendingQueue,
  getWechatAgentStatus,
  ingestNewsletter,
  ingestYouTubeTranscript,
  listKnowledgeEntries,
  listItems,
  pullCollectorRssFeeds,
  reprocessItem,
  saveResearchActionCards,
  saveResearchReport,
  uploadCollectorFile
} = require("../../utils/api");
const { formatTime } = require("../../utils/format");
const { trackEvent } = require("../../utils/analytics");
const { t } = require("../../utils/i18n");
const { getPreferenceClass } = require("../../utils/preferences");

const STATUS_STYLE = {
  pending: "status-wait",
  processing: "status-run",
  ready: "status-ready",
  failed: "status-fail"
};

function buildPreviewSummary(text, fallback) {
  const normalized = String(text || fallback || "").replace(/\s+/g, " ").trim();
  if (!normalized) return "";
  const limit = 48;
  if (normalized.length <= limit) return normalized;
  const withinLimit = normalized.slice(0, limit);
  const punctuationCut = Math.max(
    withinLimit.lastIndexOf("。"),
    withinLimit.lastIndexOf("！"),
    withinLimit.lastIndexOf("？"),
    withinLimit.lastIndexOf("."),
    withinLimit.lastIndexOf("!"),
    withinLimit.lastIndexOf("?")
  );
  if (punctuationCut >= 16) {
    return withinLimit.slice(0, punctuationCut + 1).trim();
  }
  return `${withinLimit.slice(0, limit - 1).trim()}…`;
}

function buildLatestRunContext(agentStatus, items, i18n) {
  if (!agentStatus) return null;

  const submitted = Number(agentStatus.last_cycle_submitted || 0);
  const submittedNew = Number(agentStatus.last_cycle_submitted_new || 0);
  const deduplicatedExisting = Number(agentStatus.last_cycle_deduplicated_existing || 0);
  const newItemIds = Array.isArray(agentStatus.last_cycle_new_item_ids)
    ? agentStatus.last_cycle_new_item_ids
    : [];
  const itemMap = new Map((items || []).map((item) => [item.id, item]));
  const newItems = newItemIds
    .map((itemId) => itemMap.get(itemId))
    .filter(Boolean)
    .slice(0, 3)
    .map((item) => ({
      id: item.id,
      title: item.title,
      source_domain: item.source_domain || i18n.untitled,
      preview_summary: item.preview_summary || buildPreviewSummary(item.short_summary, item.source_url)
    }));
  const updatedAt = formatTime(agentStatus.last_cycle_at);
  const running = !!(agentStatus.running || agentStatus.run_once_running);
  const hasData =
    running ||
    submitted > 0 ||
    submittedNew > 0 ||
    deduplicatedExisting > 0 ||
    newItems.length > 0 ||
    !!agentStatus.last_cycle_at;

  if (!hasData) return null;

  return {
    running,
    submitted,
    submittedNew,
    deduplicatedExisting,
    metaLine: running
      ? i18n.latestRunRunning
      : updatedAt
        ? `${i18n.latestRunUpdated} ${updatedAt}`
        : i18n.latestRunEmpty,
    emptyText: i18n.latestRunEmpty,
    newItems
  };
}

function buildResearchHistoryPreview(content) {
  const lines = String(content || "")
    .split("\n")
    .map((line) => line.replace(/^#+\s*/, "").replace(/^- /, "").trim())
    .filter(Boolean)
    .filter((line) => !/^来源[:：]/.test(line) && !/^创建时间[:：]/.test(line) && !/^最近更新[:：]/.test(line));
  const seed = lines.find((line) => line.length >= 16) || lines[0] || "";
  return buildPreviewSummary(seed, "");
}

function normalizeShortList(values, limit = 3) {
  return (Array.isArray(values) ? values : [])
    .map((value) => String(value || "").trim())
    .filter(Boolean)
    .slice(0, limit);
}

function extractResearchHistoryMeta(entry) {
  const report = entry && entry.metadata_payload && entry.metadata_payload.report;
  const diagnostics = report && report.source_diagnostics;
  return {
    scope_regions: normalizeShortList(diagnostics && diagnostics.scope_regions),
    scope_industries: normalizeShortList(diagnostics && diagnostics.scope_industries),
    scope_clients: normalizeShortList(diagnostics && diagnostics.scope_clients),
    topic_anchor_terms: normalizeShortList(diagnostics && diagnostics.topic_anchor_terms),
    matched_theme_labels: normalizeShortList(diagnostics && diagnostics.matched_theme_labels),
    filtered_old_source_count: Number((diagnostics && diagnostics.filtered_old_source_count) || 0),
  };
}

function buildResearchRingStyle(progress) {
  const safeProgress = Math.max(0, Math.min(100, Number(progress || 0)));
  const angle = Math.max(safeProgress, 4) * 3.6;
  return `background: conic-gradient(from 220deg, #8b5cf6 0deg, #6366f1 70deg, #0ea5e9 ${angle}deg, rgba(148, 163, 184, 0.16) ${angle}deg 360deg);`;
}

function buildResearchKeywordGroups(keyword, researchFocus) {
  const groups = [String(keyword || "").trim()]
    .concat(
      String(researchFocus || "")
        .split(/[，,、/｜|；;\n\s]+/)
        .map((item) => item.trim())
        .filter(Boolean)
    )
    .filter(Boolean);
  return Array.from(new Set(groups)).slice(0, 4);
}

function buildResearchModeConfig(mode) {
  if (mode === "fast") {
    return {
      research_mode: "fast",
      deep_research: false,
      max_sources: 8,
      estimatedMinutes: 3
    };
  }
  return {
    research_mode: "deep",
    deep_research: true,
    max_sources: 18,
    estimatedMinutes: 6
  };
}

Page({
  data: {
    url: "",
    rawText: "",
    importMode: "rss",
    importSubmitting: false,
    importMessage: "",
    importError: "",
    latestImportItem: null,
    latestImportSummary: "",
    rssUrl: "",
    rssTitle: "",
    newsletterTitle: "",
    newsletterSender: "",
    newsletterUrl: "",
    newsletterBody: "",
    fileName: "",
    fileMimeType: "",
    fileBase64: "",
    fileExtractedText: "",
    fileTitle: "",
    fileSourceUrl: "",
    youtubeUrl: "",
    youtubeTitle: "",
    youtubeTranscript: "",
    researchKeyword: "",
    researchFocus: "",
    researchMode: "deep",
    submitting: false,
    researching: false,
    error: "",
    errorTone: "error",
    researchError: "",
    researchMessage: "",
    researchJob: null,
    researchKeywordGroups: [],
    researchProgress: 0,
    researchRingStyle: buildResearchRingStyle(0),
    researchStageLabel: "",
    researchStageMessage: "",
    status: "pending",
    statusText: "",
    statusClass: "status-wait",
    lastSubmitTime: "",
    recentItems: [],
    researchHistory: [],
    researchReport: null,
    researchActionCards: [],
    savedResearchEntryId: "",
    seededConversationJobId: "",
    latestRun: null,
    loadingRecent: true,
    loadError: false,
    researchPollFailures: 0,
    prefClass: "",
    settingsLabel: "设置",
    i18n: {}
  },

  onLoad() {
    trackEvent("page_view", { page: "inbox" });
    this.applyPreferences();
    this.tryFlushQueue();
    this.refreshRecent();
  },

  onShow() {
    this.applyPreferences();
    this.tryFlushQueue();
    this.startPolling();
  },

  onHide() {
    this.stopPolling();
    this.stopResearchPolling();
  },

  onUnload() {
    this.stopPolling();
    this.stopResearchPolling();
  },

  onPullDownRefresh() {
    this.refreshRecent().finally(() => wx.stopPullDownRefresh());
  },

  applyPreferences() {
    const app = getApp();
    const preferences = app.globalData.preferences;
    const language = preferences.language;
    const i18n = {
      kicker: t(language, "inbox.kicker", "Intake Center"),
      title: t(language, "inbox.title", "解决方案智囊"),
      subtitle: t(language, "inbox.subtitle", "把链接或笔记交给系统，自动进入摘要和优先级处理。"),
      quickSubmit: t(language, "inbox.quickSubmit", "快速提交"),
      helper: t(language, "inbox.helper", "支持 URL / 纯文本，提交后会在右侧流转状态。"),
      urlInput: t(language, "inbox.urlInput", "URL 输入"),
      urlPlaceholder: t(language, "inbox.urlPlaceholder", "https://..."),
      submitUrl: t(language, "inbox.submitUrl", "提交 URL"),
      textInput: t(language, "inbox.textInput", "纯文本输入"),
      textPlaceholder: t(language, "inbox.textPlaceholder", "粘贴你想处理的文本..."),
      submitText: t(language, "inbox.submitText", "提交文本"),
      importTitle: t(language, "collector.multiformat.title", "多格式输入"),
      importDesc: t(language, "collector.multiformat.desc", "把 RSS、newsletter、文件和 YouTube transcript 统一导入同一条内容处理流。"),
      importRss: t(language, "collector.multiformat.rss", "RSS"),
      importNewsletter: t(language, "collector.multiformat.newsletter", "Newsletter"),
      importFile: t(language, "collector.multiformat.file", "PDF / 文件"),
      importYoutube: t(language, "collector.multiformat.youtube", "YouTube"),
      importRssPlaceholder: t(language, "collector.multiformat.rssPlaceholder", "https://example.com/feed.xml"),
      importRssTitle: t(language, "collector.multiformat.rssTitle", "RSS 标题（可选）"),
      importSubmitRss: t(language, "collector.multiformat.submitRss", "创建并同步 RSS"),
      importNewsletterTitle: t(language, "collector.multiformat.newsletterTitle", "Newsletter 标题"),
      importNewsletterSender: t(language, "collector.multiformat.newsletterSender", "发送方 / 邮件列表"),
      importNewsletterUrl: t(language, "collector.multiformat.newsletterUrl", "原文链接（可选）"),
      importNewsletterBody: t(language, "collector.multiformat.newsletterBody", "粘贴邮件正文或转发内容"),
      importSubmitNewsletter: t(language, "collector.multiformat.submitNewsletter", "导入 Newsletter"),
      importChooseFile: t(language, "collector.multiformat.chooseFile", "选择文件"),
      importFileChosen: t(language, "collector.multiformat.fileChosen", "已选择文件"),
      importFileTitle: t(language, "collector.multiformat.fileTitle", "标题覆盖（可选）"),
      importFileUrl: t(language, "collector.multiformat.fileUrl", "原始链接（可选）"),
      importSubmitFile: t(language, "collector.multiformat.submitFile", "上传文件"),
      importYoutubeUrl: t(language, "collector.multiformat.youtubeUrl", "YouTube 链接"),
      importYoutubeTitle: t(language, "collector.multiformat.youtubeTitle", "标题覆盖（可选）"),
      importYoutubeTranscript: t(language, "collector.multiformat.youtubeTranscript", "粘贴 transcript；为空时仅保存视频链接"),
      importSubmitYoutube: t(language, "collector.multiformat.submitYoutube", "导入 YouTube"),
      importLatestTitle: t(language, "collector.multiformat.latestTitle", "最近导入结果"),
      keywordInput: t(language, "inbox.keywordInput", "关键词研究"),
      keywordDesc: t(
        language,
        "inbox.keywordDesc",
        "系统会搜索公开网页与公众号相关文章，生成偏咨询顾问风格的专题研报。"
      ),
      keywordPlaceholder: t(language, "inbox.keywordPlaceholder", "例如：政务云 AI 中标 预算"),
      keywordFocusPlaceholder: t(
        language,
        "inbox.keywordFocusPlaceholder",
        "补充关注点，例如：领导发言、项目二期、销售切入、投标策略"
      ),
      keywordHelper: t(
        language,
        "inbox.keywordHelper",
        "建议输入“行业 + 场景 + 项目阶段/预算/中标”等组合关键词。"
      ),
      researchModeFast: t(language, "inbox.mode.fast", "极速调研"),
      researchModeFastDesc: t(language, "inbox.mode.fastHint", "优先官方与高信号来源，3 分钟内给出可执行初版。"),
      researchModeDeep: t(language, "inbox.mode.deep", "深度调研"),
      researchModeDeepDesc: t(language, "inbox.mode.deepHint", "多轮扩搜 + 定向信息源 + 更长综合研判，通常 5 分钟以上。"),
      submitKeywordResearch: t(language, "inbox.submitKeywordResearch", "生成研报"),
      generatingResearch: t(language, "inbox.generatingResearch", "生成中..."),
      researchProgress: t(language, "inbox.researchProgress", "研究进度"),
      researchEstimated: t(language, "inbox.researchEstimated", "预计耗时"),
      researchScope: t(language, "inbox.researchScope", "策略"),
      researchScopeDesc: t(language, "inbox.researchScopeDesc", "优先收敛到区域 / 行业 / 客户类型，证据不足时自动扩搜。"),
      researchQueued: t(language, "inbox.researchQueued", "已启动深度研究任务，正在持续汇总多源信息。"),
      researchQueuedFast: t(language, "inbox.researchQueuedFast", "已启动极速研究任务，优先汇总高信号来源。"),
      researchQueuedDeep: t(language, "inbox.researchQueuedDeep", "已启动深度研究任务，正在持续汇总多源信息。"),
      researchCompleted: t(language, "inbox.researchCompleted", "研报已生成，可继续保存、导出或生成行动卡。"),
      researchTitle: t(language, "inbox.researchTitle", "关键词研究报告"),
      researchSummary: t(language, "inbox.researchSummary", "执行摘要"),
      researchAngle: t(language, "inbox.researchAngle", "咨询价值"),
      researchQueries: t(language, "inbox.researchQueries", "检索路径"),
      researchSources: t(language, "inbox.researchSources", "来源样本"),
      researchSourceCount: t(language, "inbox.researchSourceCount", "来源数"),
      researchGeneratedAt: t(language, "inbox.researchGeneratedAt", "生成于"),
      researchSave: t(language, "inbox.researchSave", "加入知识库"),
      researchSaveToFocus: t(language, "inbox.researchSaveToFocus", "加入 Focus 参考"),
      researchExport: t(language, "inbox.researchExport", "导出 Markdown"),
      researchExportWord: t(language, "inbox.researchExportWord", "导出 Word"),
      researchExportPdf: t(language, "inbox.researchExportPdf", "导出 PDF"),
      researchOpenKnowledge: t(language, "inbox.researchOpenKnowledge", "查看知识卡片"),
      researchGenerateActions: t(language, "research.generateActions", "生成行动卡"),
      researchPlanningActions: t(language, "research.planningActions", "生成中..."),
      researchSaveActions: t(language, "research.saveActions", "保存行动卡"),
      researchSaveActionsToFocus: t(language, "research.saveActionsToFocus", "加入 Focus 参考"),
      researchActionCards: t(language, "research.actionCards", "行动卡"),
      researchActionCardsHint: t(language, "research.actionCardsHint", "将研报中的销售、投标、生态与陌拜建议拆成可执行动作。"),
      researchActionCardsEmptyHint: t(language, "research.actionCardsEmptyHint", "先生成行动卡，再批量保存到知识库或 Focus 参考。"),
      researchActionTarget: t(language, "research.actionTarget", "优先对象"),
      researchActionWindow: t(language, "research.actionWindow", "执行窗口"),
      researchActionDeliverable: t(language, "research.actionDeliverable", "产出物"),
      researchActionEvidence: t(language, "research.actionEvidence", "关键信号"),
      researchActionTimeline: t(language, "research.actionTimeline", "推进节奏"),
      researchActionsPlanned: t(language, "research.actionsPlanned", "已生成研报行动卡"),
      researchActionsEmpty: t(language, "research.actionsEmpty", "当前研报暂未生成可执行行动卡"),
      researchActionsPlanFailed: t(language, "research.actionsPlanFailed", "生成行动卡失败，请稍后重试"),
      researchActionsSaved: t(language, "research.actionsSaved", "行动卡已保存到知识库"),
      researchActionsSavedToFocus: t(language, "research.actionsSavedToFocus", "行动卡已加入 Focus 参考"),
      researchActionsSaveFailed: t(language, "research.actionsSaveFailed", "保存行动卡失败，请稍后重试"),
      researchSaved: t(language, "inbox.researchSaved", "研究报告已加入知识库"),
      researchSavedToFocus: t(language, "inbox.researchSavedToFocus", "研究报告已加入 Focus 参考"),
      researchSaveFailed: t(language, "inbox.researchSaveFailed", "保存到知识库失败，请稍后重试"),
      researchSaveFocusFailed: t(language, "inbox.researchSaveFocusFailed", "加入 Focus 参考失败，请稍后重试"),
      researchExported: t(language, "inbox.researchExported", "Markdown 已复制，可直接发送或保存"),
      researchExportedWord: t(language, "inbox.researchExportedWord", "Word 已导出，可继续打开或转发"),
      researchExportedPdf: t(language, "inbox.researchExportedPdf", "PDF 已导出，可继续打开或转发"),
      researchExportFailed: t(language, "inbox.researchExportFailed", "导出 Markdown 失败，请稍后重试"),
      researchExportWordFailed: t(language, "inbox.researchExportWordFailed", "导出 Word 失败，请稍后重试"),
      researchExportPdfFailed: t(language, "inbox.researchExportPdfFailed", "导出 PDF 失败，请稍后重试"),
      researchHistory: t(language, "inbox.researchHistory", "最近研报"),
      researchHistoryDesc: t(language, "inbox.researchHistoryDesc", "已保存的关键词研报会沉淀在这里，方便后续深读和复用。"),
      researchHistoryEmpty: t(language, "inbox.researchHistoryEmpty", "还没有保存的研报，先生成一份再加入知识库。"),
      researchHistoryOpen: t(language, "inbox.researchHistoryOpen", "打开知识卡片"),
      researchHistoryFocus: t(language, "inbox.researchHistoryFocus", "Focus 参考"),
      researchHistoryCollection: t(language, "inbox.researchHistoryCollection", "分组"),
      researchCenterOpen: t(language, "research.centerOpen", "打开研报中心"),
      researchingTitle: t(language, "inbox.researchingTitle", "正在汇总多源内容并生成研报"),
      researchingDesc: t(
        language,
        "inbox.researchingDesc",
        "系统会先检索公开网页和公众号结果，再提炼政策、预算、项目分期和销售/投标建议。"
      ),
      characters: t(language, "inbox.characters", "字数"),
      or: t(language, "common.or", "或"),
      recentAdded: t(language, "inbox.recentAdded", "最近添加"),
      latestRunTitle: t(language, "inbox.latestRunTitle", "最新采集结果"),
      latestRunUpdated: t(language, "inbox.latestRunUpdated", "更新于"),
      latestRunRunning: t(language, "inbox.latestRunRunning", "采集器正在处理新文章"),
      latestRunEmpty: t(language, "inbox.latestRunEmpty", "当前这轮没有新的高质量文章进入摘要流。"),
      latestRunSubmitted: t(language, "inbox.latestRunSubmitted", "入流"),
      latestRunNew: t(language, "inbox.latestRunNew", "真正新增"),
      latestRunDedup: t(language, "inbox.latestRunDedup", "历史去重"),
      latestRunPreview: t(language, "inbox.latestRunPreview", "新增样本"),
      noRecent: t(language, "inbox.noRecent", "暂无最近添加。"),
      noRecentHint: t(language, "inbox.noRecentHint", "可以先提交一个 URL 或一段文本，系统会自动开始处理。"),
      backToFeed: t(language, "knowledge.backToFeed", "返回首页"),
      retry: t(language, "inbox.retry", "重试"),
      retryLoad: t(language, "common.retryLoad", "重新加载"),
      retryDone: t(language, "inbox.retryDone", "已重试"),
      enterUrl: t(language, "inbox.error.enterUrl", "请先输入 URL"),
      enterText: t(language, "inbox.error.enterText", "请先输入文本内容"),
      enterKeyword: t(language, "inbox.error.enterKeyword", "请先输入关键词"),
      researchFailed: t(language, "inbox.error.researchFailed", "关键词研究失败，请稍后重试"),
      listFailed: t(language, "inbox.error.listFailed", "读取列表失败"),
      localMockMode: t(language, "common.localMockMode", "后端未连接，当前显示本地演示数据"),
      untitled: t(language, "common.untitled", "未命名内容"),
      statusPending: t(language, "status.pending", "等待处理"),
      statusProcessing: t(language, "status.processing", "处理中"),
      statusReady: t(language, "status.ready", "已完成"),
      statusFailed: t(language, "status.failed", "处理失败"),
      recentSubmit: t(language, "common.recentSubmit", "最近提交")
    };
    this.setData({
      prefClass: getPreferenceClass(preferences, app.globalData.systemTheme),
      settingsLabel: t(language, "common.settings", "设置"),
      i18n,
      statusText: this.mapStatusText(this.data.status, i18n)
    });
    wx.setNavigationBarTitle({
      title: t(language, "nav.inbox", "解决方案智囊")
    });
  },

  startPolling() {
    this.stopPolling();
    this._timer = setInterval(() => this.refreshRecent(), 2500);
  },

  stopPolling() {
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
  },

  refreshRecent() {
    this.setData({ loadingRecent: true, loadError: false });
    return Promise.all([
      listItems(24),
      getWechatAgentStatus().catch(() => null),
      listKnowledgeEntries(6, { sourceDomain: "research.report" }).catch(() => ({ items: [] }))
    ])
      .then(([res, agentStatus, researchHistoryRes]) => {
        const allItems = (res.items || []).map((item) => ({
          ...item,
          preview_summary: buildPreviewSummary(item.short_summary, item.source_url),
          statusText: this.mapStatusText(item.status, this.data.i18n),
          statusClass: STATUS_STYLE[item.status] || "status-run"
        }));
        const researchHistory = (researchHistoryRes.items || []).map((entry) => ({
          id: entry.id,
          title: entry.title,
          collection_name: entry.collection_name || "",
          is_focus_reference: !!entry.is_focus_reference,
          created_at: entry.created_at,
          preview_summary: buildResearchHistoryPreview(entry.content),
          diagnostics: extractResearchHistoryMeta(entry),
        }));
        const recentItems = allItems.slice(0, 10);
        const currentStatus = recentItems[0] ? recentItems[0].status : "pending";
        this.setData({
          recentItems,
          researchHistory,
          latestRun: buildLatestRunContext(agentStatus, allItems, this.data.i18n),
          status: currentStatus,
          statusText: this.mapStatusText(currentStatus, this.data.i18n),
          statusClass: STATUS_STYLE[currentStatus] || "status-run",
          error: res.fromMock ? this.data.i18n.localMockMode : "",
          errorTone: res.fromMock ? "warning" : "error",
          loadingRecent: false,
          loadError: false
        });
      })
      .catch(() => {
        this.setData({
          error: this.data.i18n.listFailed,
          errorTone: "error",
          loadingRecent: false,
          loadError: true
        });
      });
  },

  mapStatusText(status, i18n) {
    if (status === "pending") return i18n.statusPending || "";
    if (status === "processing") return i18n.statusProcessing || "";
    if (status === "ready") return i18n.statusReady || "";
    if (status === "failed") return i18n.statusFailed || "";
    return i18n.statusProcessing || "";
  },

  tryFlushQueue() {
    flushPendingQueue(8).then((result) => {
      if (result.flushed > 0) {
        this.setData({ error: `已自动补发 ${result.flushed} 条离线操作`, errorTone: "info" });
      }
    });
  },

  onUrlInput(e) {
    this.setData({ url: e.detail.value });
  },

  onTextInput(e) {
    this.setData({ rawText: e.detail.value });
  },

  setImportMode(e) {
    const mode = e.currentTarget.dataset.mode || "rss";
    this.setData({
      importMode: mode,
      importMessage: "",
      importError: ""
    });
  },

  onImportInput(e) {
    const field = e.currentTarget.dataset.field;
    if (!field) return;
    this.setData({ [field]: e.detail.value });
  },

  chooseImportFile() {
    if (this.data.importSubmitting) return;
    wx.chooseMessageFile({
      count: 1,
      type: "file",
      success: ({ tempFiles }) => {
        const file = Array.isArray(tempFiles) ? tempFiles[0] : null;
        if (!file || !file.path) {
          this.setData({ importError: "未读取到文件，请重试。" });
          return;
        }
        const fs = wx.getFileSystemManager();
        fs.readFile({
          filePath: file.path,
          encoding: "base64",
          success: (base64Res) => {
            fs.readFile({
              filePath: file.path,
              encoding: "utf8",
              success: (textRes) => {
                this.setData({
                  fileName: file.name || "upload.bin",
                  fileMimeType: file.type || "application/octet-stream",
                  fileBase64: base64Res.data || "",
                  fileExtractedText: typeof textRes.data === "string" ? textRes.data.slice(0, 80000) : "",
                  importMessage: "",
                  importError: ""
                });
              },
              fail: () => {
                this.setData({
                  fileName: file.name || "upload.bin",
                  fileMimeType: file.type || "application/octet-stream",
                  fileBase64: base64Res.data || "",
                  fileExtractedText: "",
                  importMessage: "",
                  importError: ""
                });
              }
            });
          },
          fail: () => {
            this.setData({ importError: "读取文件失败，请重试。" });
          }
        });
      },
      fail: () => {
        this.setData({ importError: "未选择文件。" });
      }
    });
  },

  onResearchKeywordInput(e) {
    this.setData({ researchKeyword: e.detail.value });
  },

  onResearchFocusInput(e) {
    this.setData({ researchFocus: e.detail.value });
  },

  setResearchMode(e) {
    if (this.data.researching) return;
    const mode = e.currentTarget.dataset.mode === "fast" ? "fast" : "deep";
    this.setData({ researchMode: mode });
  },

  submitUrl() {
    const url = (this.data.url || "").trim();
    if (!url) {
      this.setData({ error: this.data.i18n.enterUrl, errorTone: "error" });
      return;
    }

    this.setData({ submitting: true, error: "", errorTone: "info" });
    createItem({
      source_type: "url",
      source_url: url,
      output_language: getApp().globalData.preferences.language
    })
      .then((item) => {
        this.setData({
          url: "",
          status: item.status || "pending",
          lastSubmitTime: formatTime(new Date().toISOString())
        });
        trackEvent("inbox_submit", { source_type: "url", status: "ok" });
        return this.refreshRecent();
      })
      .catch(() => {
        trackEvent("inbox_submit", { source_type: "url", status: "failed" });
      })
      .finally(() => this.setData({ submitting: false }));
  },

  submitText() {
    const rawText = (this.data.rawText || "").trim();
    if (!rawText) {
      this.setData({ error: this.data.i18n.enterText, errorTone: "error" });
      return;
    }

    this.setData({ submitting: true, error: "", errorTone: "info" });
    createItem({
      source_type: "text",
      raw_content: rawText,
      title: rawText.slice(0, 24),
      output_language: getApp().globalData.preferences.language
    })
      .then((item) => {
        this.setData({
          rawText: "",
          status: item.status || "pending",
          lastSubmitTime: formatTime(new Date().toISOString())
        });
        trackEvent("inbox_submit", { source_type: "text", status: "ok" });
        return this.refreshRecent();
      })
      .catch(() => {
        trackEvent("inbox_submit", { source_type: "text", status: "failed" });
      })
      .finally(() => this.setData({ submitting: false }));
  },

  submitRssImport() {
    const rssUrl = (this.data.rssUrl || "").trim();
    if (!rssUrl) {
      this.setData({ importError: "请先输入 RSS URL。", importMessage: "" });
      return;
    }
    this.setData({ importSubmitting: true, importError: "", importMessage: "" });
    createCollectorRssSource({
      source_url: rssUrl,
      title: (this.data.rssTitle || "").trim() || undefined,
      pull_immediately: true,
      output_language: getApp().globalData.preferences.language
    })
      .then(() =>
        pullCollectorRssFeeds({
          limit: 8,
          output_language: getApp().globalData.preferences.language
        })
      )
      .then((res) => {
        const latest = Array.isArray(res.results) ? res.results[0] : null;
        this.setData({
          rssUrl: "",
          rssTitle: "",
          latestImportItem: null,
          latestImportSummary: latest
            ? `${latest.feed_title}：新增 ${latest.new_items}，去重 ${latest.deduplicated_items}，跳过 ${latest.skipped_items}`
            : "RSS 已创建。",
          importMessage: latest
            ? `${latest.feed_title}：新增 ${latest.new_items} 条。`
            : "RSS 已创建并开始同步。",
          lastSubmitTime: formatTime(new Date().toISOString())
        });
        trackEvent("multiformat_import", { type: "rss", status: "ok" });
        return this.refreshRecent();
      })
      .catch(() => {
        this.setData({ importError: "RSS 导入失败，请检查地址。", importMessage: "" });
        trackEvent("multiformat_import", { type: "rss", status: "failed" });
      })
      .finally(() => this.setData({ importSubmitting: false }));
  },

  submitNewsletterImport() {
    const title = (this.data.newsletterTitle || "").trim();
    const rawContent = (this.data.newsletterBody || "").trim();
    if (!title || !rawContent) {
      this.setData({ importError: "请填写 newsletter 标题和正文。", importMessage: "" });
      return;
    }
    this.setData({ importSubmitting: true, importError: "", importMessage: "" });
    ingestNewsletter({
      title,
      sender: (this.data.newsletterSender || "").trim() || undefined,
      source_url: (this.data.newsletterUrl || "").trim() || undefined,
      raw_content: rawContent,
      output_language: getApp().globalData.preferences.language
    })
      .then((res) => {
        this.setData({
          newsletterTitle: "",
          newsletterSender: "",
          newsletterUrl: "",
          newsletterBody: "",
          latestImportItem: res.item,
          latestImportSummary: res.item.title || "Newsletter 导入完成",
          importMessage: res.deduplicated ? "该 newsletter 已存在，已直接复用。" : "Newsletter 已进入处理流。",
          lastSubmitTime: formatTime(new Date().toISOString())
        });
        trackEvent("multiformat_import", { type: "newsletter", status: "ok" });
        return this.refreshRecent();
      })
      .catch(() => {
        this.setData({ importError: "Newsletter 导入失败，请稍后重试。", importMessage: "" });
        trackEvent("multiformat_import", { type: "newsletter", status: "failed" });
      })
      .finally(() => this.setData({ importSubmitting: false }));
  },

  submitFileImport() {
    if (!this.data.fileName || !this.data.fileBase64) {
      this.setData({ importError: "请先选择文件。", importMessage: "" });
      return;
    }
    this.setData({ importSubmitting: true, importError: "", importMessage: "" });
    uploadCollectorFile({
      file_name: this.data.fileName,
      mime_type: this.data.fileMimeType || "application/octet-stream",
      file_base64: this.data.fileBase64,
      extracted_text: this.data.fileExtractedText || undefined,
      title: (this.data.fileTitle || "").trim() || undefined,
      source_url: (this.data.fileSourceUrl || "").trim() || undefined,
      output_language: getApp().globalData.preferences.language
    })
      .then((res) => {
        this.setData({
          fileName: "",
          fileMimeType: "",
          fileBase64: "",
          fileExtractedText: "",
          fileTitle: "",
          fileSourceUrl: "",
          latestImportItem: res.item,
          latestImportSummary: `${res.item.title || "文件导入"} · ${String((res.metadata && res.metadata.parse_status) || "parsed")}`,
          importMessage: res.deduplicated ? "该文件对应内容已存在，已直接复用。" : "文件已导入处理流。",
          lastSubmitTime: formatTime(new Date().toISOString())
        });
        trackEvent("multiformat_import", { type: "file", status: "ok" });
        return this.refreshRecent();
      })
      .catch(() => {
        this.setData({ importError: "文件导入失败，请重试。", importMessage: "" });
        trackEvent("multiformat_import", { type: "file", status: "failed" });
      })
      .finally(() => this.setData({ importSubmitting: false }));
  },

  submitYoutubeImport() {
    const videoUrl = (this.data.youtubeUrl || "").trim();
    if (!videoUrl) {
      this.setData({ importError: "请先输入 YouTube 链接。", importMessage: "" });
      return;
    }
    this.setData({ importSubmitting: true, importError: "", importMessage: "" });
    ingestYouTubeTranscript({
      video_url: videoUrl,
      title: (this.data.youtubeTitle || "").trim() || undefined,
      transcript_text: (this.data.youtubeTranscript || "").trim() || undefined,
      output_language: getApp().globalData.preferences.language
    })
      .then((res) => {
        this.setData({
          youtubeUrl: "",
          youtubeTitle: "",
          youtubeTranscript: "",
          latestImportItem: res.item,
          latestImportSummary: res.item.title || "YouTube transcript 导入完成",
          importMessage: res.deduplicated ? "该视频已存在，已直接复用。" : "YouTube transcript 已进入处理流。",
          lastSubmitTime: formatTime(new Date().toISOString())
        });
        trackEvent("multiformat_import", { type: "youtube", status: "ok" });
        return this.refreshRecent();
      })
      .catch(() => {
        this.setData({ importError: "YouTube 导入失败，请检查链接或 transcript。", importMessage: "" });
        trackEvent("multiformat_import", { type: "youtube", status: "failed" });
      })
      .finally(() => this.setData({ importSubmitting: false }));
  },

  submitResearch() {
    const keyword = (this.data.researchKeyword || "").trim();
    if (!keyword) {
      this.setData({ researchError: this.data.i18n.enterKeyword, errorTone: "error" });
      return;
    }

    const modeConfig = buildResearchModeConfig(this.data.researchMode);
    this.setData({
      researching: true,
      researchError: "",
      researchMessage: "",
      researchReport: null,
      researchActionCards: [],
      savedResearchEntryId: "",
      seededConversationJobId: "",
      researchPollFailures: 0,
      researchKeywordGroups: buildResearchKeywordGroups(keyword, this.data.researchFocus),
      researchProgress: 3,
      researchRingStyle: buildResearchRingStyle(3),
      researchStageLabel: this.data.i18n.researchingTitle,
      researchStageMessage: this.data.i18n.researchingDesc
    });
    createResearchJob({
      keyword,
      research_focus: (this.data.researchFocus || "").trim(),
      output_language: getApp().globalData.preferences.language,
      include_wechat: true,
      max_sources: modeConfig.max_sources,
      deep_research: modeConfig.deep_research,
      research_mode: modeConfig.research_mode
    })
      .then((job) => {
        const mode = job.research_mode || this.data.researchMode;
        this.setData({
          researchMode: mode,
          researchJob: job,
          researchMessage: mode === "fast" ? this.data.i18n.researchQueuedFast : this.data.i18n.researchQueuedDeep,
          researchProgress: Number(job.progress_percent || 3),
          researchRingStyle: buildResearchRingStyle(Number(job.progress_percent || 3)),
          researchStageLabel: job.stage_label || this.data.i18n.researchingTitle,
          researchStageMessage: job.message || this.data.i18n.researchingDesc,
          researchKeywordGroups: buildResearchKeywordGroups(job.keyword || keyword, job.research_focus || this.data.researchFocus)
        });
        trackEvent("inbox_submit", { source_type: "keyword_research", status: "ok" });
        this.startResearchPolling();
      })
      .catch(() => {
        this.setData({
          researching: false,
          researchError:
            t(
              getApp().globalData.preferences.language,
              "inbox.error.researchBackendUnavailable",
              "后端研究服务暂不可用：当前前端无法创建研报任务，请检查 API 是否运行。"
            )
        });
        trackEvent("inbox_submit", { source_type: "keyword_research", status: "failed" });
      });
  },

  startResearchPolling() {
    this.stopResearchPolling();
    this._researchJobTimer = setInterval(() => this.pollResearchJob(), 1800);
    this.pollResearchJob();
  },

  stopResearchPolling() {
    if (this._researchJobTimer) {
      clearInterval(this._researchJobTimer);
      this._researchJobTimer = null;
    }
  },

  pollResearchJob() {
    const job = this.data.researchJob;
    if (!job || !job.id) return;
    getResearchJob(job.id)
      .then((nextJob) => {
        const nextState = {
          researchMode: nextJob.research_mode || this.data.researchMode,
          researchJob: nextJob,
          researchPollFailures: 0,
          researchProgress: Number(nextJob.progress_percent || 0),
          researchRingStyle: buildResearchRingStyle(Number(nextJob.progress_percent || 0)),
          researchStageLabel: nextJob.stage_label || this.data.i18n.researchingTitle,
          researchStageMessage: nextJob.message || this.data.i18n.researchingDesc,
          researchKeywordGroups: buildResearchKeywordGroups(
            nextJob.keyword || this.data.researchKeyword,
            nextJob.research_focus || this.data.researchFocus
          )
        };
        if (nextJob.report) {
          nextState.researchReport = {
            ...nextJob.report,
            generated_at_display: formatTime(nextJob.report.generated_at)
          };
        }
        if (nextJob.status === "succeeded" && nextJob.report) {
          this.stopResearchPolling();
          this.ensureResearchConversation(nextJob);
          this.setData({
            ...nextState,
            researching: false,
            researchMessage: this.data.i18n.researchCompleted
          });
          return;
        }
        if (nextJob.status === "failed") {
          this.stopResearchPolling();
          this.setData({
            ...nextState,
            researching: false,
            researchError: nextJob.error || this.data.i18n.researchFailed
          });
          return;
        }
        this.setData(nextState);
      })
      .catch(() => {
        const failures = Number(this.data.researchPollFailures || 0) + 1;
        if (failures < 4) {
          this.setData({ researchPollFailures: failures });
          return;
        }
        this.stopResearchPolling();
        this.setData({
          researchPollFailures: failures,
          researching: false,
          researchError:
            t(
              getApp().globalData.preferences.language,
              "inbox.error.researchBackendUnavailable",
              "后端研究服务暂不可用：当前前端无法继续轮询研报任务，请检查 API 是否运行。"
            )
        });
      });
  },

  ensureResearchConversation(job) {
    if (!job || !job.id || this.data.seededConversationJobId === job.id) {
      return;
    }
    createResearchConversation({
      title: `${job.keyword || "研究"} 继续追问`,
      job_id: job.id
    })
      .catch(() => null)
      .finally(() => {
        this.setData({ seededConversationJobId: job.id });
      });
  },

  saveResearchReport(asFocusReference = false) {
    const report = this.data.researchReport;
    if (!report) return;
    saveResearchReport({
      report,
      collection_name: "关键词研报",
      is_focus_reference: asFocusReference
    })
      .then((result) => {
        this.setData({
          researchMessage: asFocusReference
            ? this.data.i18n.researchSavedToFocus
            : this.data.i18n.researchSaved,
          savedResearchEntryId: result.entry_id
        });
        wx.showToast({
          title: asFocusReference
            ? this.data.i18n.researchSavedToFocus
            : this.data.i18n.researchSaved,
          icon: "none"
        });
        this.refreshRecent();
      })
      .catch(() => {
        this.setData({
          researchMessage: asFocusReference
            ? this.data.i18n.researchSaveFocusFailed
            : this.data.i18n.researchSaveFailed
        });
      });
  },

  saveResearchAsFocus() {
    this.saveResearchReport(true);
  },

  planResearchActions() {
    const report = this.data.researchReport;
    if (!report) return;
    this.setData({ researchMessage: this.data.i18n.researchPlanningActions });
    createResearchActionPlan({
      report
    })
      .then((result) => {
        const cards = Array.isArray(result.cards) ? result.cards : [];
        this.setData({
          researchActionCards: cards,
          researchMessage: cards.length
            ? this.data.i18n.researchActionsPlanned
            : this.data.i18n.researchActionsEmpty
        });
      })
      .catch(() => {
        this.setData({ researchMessage: this.data.i18n.researchActionsPlanFailed });
      });
  },

  saveResearchActions(asFocusReference = false) {
    const report = this.data.researchReport;
    const cards = this.data.researchActionCards;
    if (!report || !Array.isArray(cards) || !cards.length) return;
    saveResearchActionCards({
      keyword: report.keyword,
      cards,
      collection_name: `${report.keyword} 行动卡`,
      is_focus_reference: asFocusReference
    })
      .then(() => {
        this.setData({
          researchMessage: asFocusReference
            ? this.data.i18n.researchActionsSavedToFocus
            : this.data.i18n.researchActionsSaved
        });
      })
      .catch(() => {
        this.setData({ researchMessage: this.data.i18n.researchActionsSaveFailed });
      });
  },

  saveResearchActionsToFocus() {
    this.saveResearchActions(true);
  },

  exportResearchReport() {
    this.exportResearchDocument("markdown");
  },

  saveBinaryDocument(filename, base64, successMessage, failedMessage) {
    if (!filename || !base64) {
      this.setData({ researchMessage: failedMessage });
      return;
    }
    try {
      const fs = wx.getFileSystemManager();
      const filePath = `${wx.env.USER_DATA_PATH}/${filename}`;
      fs.writeFile({
        filePath,
        data: wx.base64ToArrayBuffer(base64),
        encoding: "binary",
        success: () => {
          wx.openDocument({
            filePath,
            showMenu: true,
            success: () => {
              this.setData({ researchMessage: successMessage });
            },
            fail: () => {
              this.setData({ researchMessage: successMessage });
            }
          });
        },
        fail: () => {
          this.setData({ researchMessage: failedMessage });
        }
      });
    } catch {
      this.setData({ researchMessage: failedMessage });
    }
  },

  saveTextDocument(filename, content, successMessage, failedMessage) {
    if (!filename || !content) {
      this.setData({ researchMessage: failedMessage });
      return;
    }
    try {
      const fs = wx.getFileSystemManager();
      const filePath = `${wx.env.USER_DATA_PATH}/${filename}`;
      fs.writeFile({
        filePath,
        data: content,
        encoding: "utf8",
        success: () => {
          wx.openDocument({
            filePath,
            showMenu: true,
            success: () => {
              this.setData({ researchMessage: successMessage });
            },
            fail: () => {
              this.setData({ researchMessage: successMessage });
            }
          });
        },
        fail: () => {
          this.setData({ researchMessage: failedMessage });
        }
      });
    } catch {
      this.setData({ researchMessage: failedMessage });
    }
  },

  exportResearchDocument(format) {
    const report = this.data.researchReport;
    if (!report) return;
    const taskType =
      format === "word"
        ? "export_research_report_word"
        : format === "pdf"
          ? "export_research_report_pdf"
          : "export_research_report_markdown";
    createTask({
      task_type: taskType,
      input_payload: {
        report,
        output_language: getApp().globalData.preferences.language
      }
    })
      .then((task) => {
        const filename =
          task && task.output_payload && typeof task.output_payload.filename === "string"
            ? task.output_payload.filename
            : `${report.report_title || report.keyword}.${format === "word" ? "doc" : format === "pdf" ? "pdf" : "md"}`;
        const content =
          task && task.output_payload && typeof task.output_payload.content === "string"
            ? task.output_payload.content
            : "";
        const contentBase64 =
          task && task.output_payload && typeof task.output_payload.content_base64 === "string"
            ? task.output_payload.content_base64
            : "";
        if (format === "markdown") {
          if (!content) {
            throw new Error("empty export");
          }
          wx.setClipboardData({
            data: content,
            success: () => {
              this.setData({ researchMessage: this.data.i18n.researchExported });
            }
          });
          return;
        }
        if (format === "word") {
          this.saveTextDocument(
            filename,
            content,
            this.data.i18n.researchExportedWord,
            this.data.i18n.researchExportWordFailed
          );
          return;
        }
        this.saveBinaryDocument(
          filename,
          contentBase64,
          this.data.i18n.researchExportedPdf,
          this.data.i18n.researchExportPdfFailed
        );
      })
      .catch(() => {
        this.setData({
          researchMessage:
            format === "word"
              ? this.data.i18n.researchExportWordFailed
              : format === "pdf"
                ? this.data.i18n.researchExportPdfFailed
                : this.data.i18n.researchExportFailed
        });
      });
  },

  exportResearchWord() {
    this.exportResearchDocument("word");
  },

  exportResearchPdf() {
    this.exportResearchDocument("pdf");
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

  openSavedResearch() {
    const entryId = this.data.savedResearchEntryId;
    if (!entryId) return;
    wx.navigateTo({
      url: `/pages/knowledge/index?id=${entryId}`
    });
  },

  openResearchHistory(e) {
    const entryId = e.currentTarget.dataset.id;
    if (!entryId) return;
    wx.navigateTo({
      url: `/pages/knowledge/index?id=${entryId}`
    });
  },

  openResearchCenter() {
    wx.navigateTo({
      url: "/pages/research/index"
    });
  },

  retryItem(e) {
    const itemId = e.currentTarget.dataset.id;
    if (!itemId) return;
    reprocessItem(itemId, getApp().globalData.preferences.language).then(() => {
      wx.showToast({ title: this.data.i18n.retryDone, icon: "none" });
      trackEvent("inbox_retry", { item_id: itemId });
      this.refreshRecent();
    });
  },

  openItem(e) {
    const itemId = e.currentTarget.dataset.id;
    if (!itemId) return;
    wx.navigateTo({
      url: `/pages/item/index?id=${itemId}`
    });
  },

  openFeed() {
    wx.switchTab({
      url: "/pages/feed/index"
    });
  }
});
