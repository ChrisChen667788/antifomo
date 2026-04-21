const {
  addItemToKnowledge,
  flushPendingQueue,
  getItem,
  getItemDiagnostics,
  interpretItem,
  reprocessItem,
  submitFeedback
} = require("../../utils/api");
const { scoreTo100 } = require("../../utils/format");
const { trackEvent } = require("../../utils/analytics");
const { t } = require("../../utils/i18n");
const { getPreferenceClass } = require("../../utils/preferences");
const { buildOriginalViewModel } = require("../../utils/item-content-view");

function buildArchiveHitMessage(language, res, fallbackAction) {
  const actionLabel = res.knowledge_trigger === "save"
    ? t(language, "action.save", "稍后再读")
    : t(language, "action.like", "感兴趣");
  const thresholdValue = Number(res.knowledge_threshold);
  const thresholdLabel = Number.isFinite(thresholdValue)
    ? thresholdValue >= 4
      ? t(language, "summary.score.high", "高价值")
      : thresholdValue >= 2.8
        ? t(language, "summary.score.mid", "中价值")
        : t(language, "summary.score.low", "低价值")
    : t(language, "knowledge.ruleThreshold", "价值门槛");

  if (language === "en") {
    return res.knowledge_status === "existing"
      ? `Already archived: matched the ${thresholdLabel} auto-archive rule, triggered by ${actionLabel}.`
      : `Auto archived: matched the ${thresholdLabel} auto-archive rule, triggered by ${actionLabel}.`;
  }
  if (language === "ja") {
    return res.knowledge_status === "existing"
      ? `既にナレッジ化済み：評価 ${score} >= ${threshold}、操作 ${actionLabel}。`
      : `自動でナレッジ化：評価 ${score} >= ${threshold}、操作 ${actionLabel}。`;
  }
  if (language === "ko") {
    return res.knowledge_status === "existing"
      ? `이미 지식베이스에 있습니다: 점수 ${score} >= ${threshold}, 동작 ${actionLabel}.`
      : `자동 보관됨: 점수 ${score} >= ${threshold}, 동작 ${actionLabel}.`;
  }
  if (language === "zh-TW") {
    return res.knowledge_status === "existing"
      ? `已命中自動歸檔規則：符合「${thresholdLabel}」門檻，且已標記「${actionLabel || fallbackAction}」。`
      : `已自動歸檔：符合「${thresholdLabel}」門檻，且已標記「${actionLabel || fallbackAction}」。`;
  }
  return res.knowledge_status === "existing"
    ? `已命中自动归档规则：符合“${thresholdLabel}”门槛，且已标记“${actionLabel || fallbackAction}”。`
    : `已自动归档：符合“${thresholdLabel}”门槛，且已标记“${actionLabel || fallbackAction}”。`;
}

function buildExcerptTitle(itemTitle, index, language) {
  const baseTitle = String(itemTitle || "").trim() || t(language, "common.untitled", "未命名内容");
  if (language === "en") {
    return `${baseTitle} / Key excerpt ${index + 1}`;
  }
  if (language === "ja") {
    return `${baseTitle} / 重要抜粋 ${index + 1}`;
  }
  if (language === "ko") {
    return `${baseTitle} / 핵심 발췌 ${index + 1}`;
  }
  if (language === "zh-TW") {
    return `${baseTitle} / 關鍵摘錄 ${index + 1}`;
  }
  return `${baseTitle} / 关键摘录 ${index + 1}`;
}

function buildItemDiagnostics(item, diagnostics) {
  const source = diagnostics && typeof diagnostics === "object" ? diagnostics : {};
  return {
    ingest_route: source.ingest_route || item.ingest_route || "unknown",
    content_acquisition_status:
      source.content_acquisition_status || item.content_acquisition_status || "pending",
    content_acquisition_note:
      source.content_acquisition_note || item.content_acquisition_note || "",
    processing_status: source.processing_status || item.status || "pending",
    fallback_used:
      source.fallback_used !== undefined ? !!source.fallback_used : !!item.fallback_used,
    attempt_count: Number(source.attempt_count || 0)
  };
}

Page({
  data: {
    itemId: "",
    item: null,
    loading: true,
    loadError: false,
    currentView: "summary",
    liked: false,
    ignored: false,
    saved: false,
    reprocessState: "idle",
    insightLoading: false,
    insightData: null,
    insightExpanded: false,
    insightSheetMounted: false,
    insightSheetActive: false,
    knowledgeSaving: false,
    knowledgeEntryId: "",
    itemOriginalView: { keywords: [], paragraphs: [], keyParagraphs: [] },
    viewMotionClass: "",
    message: "",
    messageTone: "info",
    prefClass: "",
    settingsLabel: "设置",
    i18n: {}
  },

  onLoad(options) {
    const itemId = options.id || "";
    this.setData({ itemId });
    trackEvent("page_view", { page: "item", item_id: itemId });
    this.applyPreferences();
    this.tryFlushQueue();
    this.loadItem(itemId);
  },

  onShow() {
    this.applyPreferences();
    this.tryFlushQueue();
  },

  onUnload() {
    if (this._viewMotionTimer) {
      clearTimeout(this._viewMotionTimer);
      this._viewMotionTimer = null;
    }
    if (this._insightSheetTimer) {
      clearTimeout(this._insightSheetTimer);
      this._insightSheetTimer = null;
    }
  },

  applyPreferences() {
    const app = getApp();
    const preferences = app.globalData.preferences;
    const language = preferences.language;
    const i18n = {
      kicker: t(language, "item.kicker", "Target Briefing"),
      title: t(language, "item.title", "内容详情"),
      subtitle: t(language, "item.subtitle", "完整理解 + 快捷反馈，让推荐更稳定。"),
      loading: t(language, "item.loading", "正在加载内容..."),
      empty: t(language, "item.empty", "这条内容暂时不可用。"),
      emptyHint: t(language, "item.emptyHint", "可以先重试加载，或回到首页继续处理其它卡片。"),
      source: t(language, "item.source", "来源"),
      score: t(language, "item.score", "评分"),
      diagnosticsTitle: t(language, "item.diagnosticsTitle", "采集诊断"),
      diagnosticsRoute: t(language, "item.diagnosticsRoute", "路由"),
      diagnosticsBody: t(language, "item.diagnosticsBody", "正文状态"),
      diagnosticsProcessing: t(language, "item.diagnosticsProcessing", "处理状态"),
      diagnosticsFallback: t(language, "item.diagnosticsFallback", "使用兜底"),
      diagnosticsAttempts: t(language, "item.diagnosticsAttempts", "尝试次数"),
      sourceLinkCopy: t(language, "item.sourceLinkCopy", "原文链接（点击复制）"),
      shortSummary: t(language, "item.shortSummary", "短摘要"),
      longSummary: t(language, "item.longSummary", "长摘要"),
      originalContent: t(language, "item.originalContent", "原文内容"),
      originalEmpty: t(language, "item.originalEmpty", "当前还没有可展示的原文，建议重新处理或打开原链接。"),
      keyParagraphs: t(language, "item.keyParagraphs", "关键段落"),
      keyParagraphsHint: t(language, "item.keyParagraphsHint", "下面这些段落最适合单独沉淀进知识库。"),
      keyParagraphsEmpty: t(language, "item.keyParagraphsEmpty", "当前没有足够稳定的关键段落，可直接查看原文或重新处理。"),
      highlightKeywords: t(language, "item.highlightKeywords", "原文关键词"),
      viewOriginal: t(language, "item.view.original", "原文"),
      viewSummary: t(language, "item.view.summary", "摘要"),
      viewInsight: t(language, "item.view.insight", "专业解读"),
      suggestedAction: t(language, "item.suggestedAction", "建议动作"),
      whyRecommended: t(language, "item.whyRecommended", "为什么推荐给你"),
      userFeedback: t(language, "item.userFeedback", "用户反馈"),
      actionLike: t(language, "action.like", "Like"),
      actionLikeDone: t(language, "action.like_done", "已 Like"),
      actionIgnore: t(language, "action.ignore", "Ignore"),
      actionIgnoreDone: t(language, "action.ignore_done", "已 Ignore"),
      actionSave: t(language, "action.save", "稍后再读"),
      actionSaveDone: t(language, "action.save_done", "已加入稍后再读"),
      actionReprocess: t(language, "action.reprocess", "重新处理"),
      actionReprocessing: t(language, "action.reprocessing", "重新处理中..."),
      actionInaccurate: t(language, "action.inaccurate", "标记摘要不准"),
      interpretation: t(language, "item.interpretation", "专业解读"),
      interpretButton: t(language, "item.interpretButton", "生成专业解读"),
      openKnowledge: t(language, "item.openKnowledge", "查看知识卡片"),
      openKnowledgeList: t(language, "item.openKnowledgeList", "知识库列表"),
      knowledgeSaved: t(language, "item.knowledgeSaved", "已加入知识库，点击查看"),
      feedbackSynced: t(language, "common.feedbackSynced", "已同步反馈"),
      localOnly: t(language, "common.localOnly", "本地已记录，API 未连接"),
      loadingFailed: t(language, "common.loadingFailed", "加载失败"),
      noLink: t(language, "item.noLink", "无可用链接"),
      linkCopied: t(language, "item.linkCopied", "链接已复制"),
      reprocessSubmitted: t(language, "item.reprocessSubmitted", "已提交重新处理任务"),
      reprocessLocal: t(language, "item.reprocessLocal", "本地标记为重新处理"),
      untitled: t(language, "common.untitled", "未命名内容"),
      unknownSource: t(language, "common.unknownSource", "未知来源"),
      noSummary: t(language, "common.noSummary", "暂无摘要"),
      insightTitle: t(language, "insight.title", "专业解读"),
      insightSignals: t(language, "insight.keySignals", "关键信号"),
      insightKnowledge: t(language, "insight.knowledge", "知识库笔记"),
      insightClose: t(language, "insight.close", "关闭"),
      insightAdd: t(language, "insight.addKnowledge", "加入知识库"),
      insightAdded: t(language, "insight.added", "已加入知识库"),
      insightFailed: t(language, "insight.failed", "解读生成失败"),
      insightLoading: t(language, "insight.loading", "正在生成专业解读..."),
      insightPreview: t(language, "item.insightPreview", "把卡片中的核心判断抽成可执行解读，适合在查看详情时快速决策。"),
      insightSheetTitle: t(language, "item.insightSheetTitle", "专业解读"),
      insightOpenSheet: t(language, "item.insightOpenSheet", "展开完整解读"),
      saveExcerpt: t(language, "item.saveExcerpt", "摘录入知识库"),
      excerptSaved: t(language, "item.excerptSaved", "关键摘录已加入知识库"),
      excerptSaveFailed: t(language, "item.excerptSaveFailed", "摘录保存失败，请稍后重试"),
      openFeed: t(language, "knowledge.backToFeed", "返回首页"),
      retryLoad: t(language, "common.retryLoad", "重新加载")
    };
    this.setData({
      prefClass: getPreferenceClass(preferences, app.globalData.systemTheme),
      settingsLabel: t(language, "common.settings", "设置"),
      i18n
    });
    wx.setNavigationBarTitle({
      title: t(language, "nav.item", "详情")
    });
  },

  tryFlushQueue() {
    flushPendingQueue(8).then((result) => {
      if (result.flushed > 0) {
        this.setData({
          message: `${this.data.i18n.localOnly}（+${result.flushed}）`,
          messageTone: "warning"
        });
      }
    });
  },

  loadItem(itemId) {
    const language = getApp().globalData.preferences.language;
    this.setData({
      loading: true,
      loadError: false,
      currentView: "summary",
      insightLoading: false,
      insightData: null,
      insightExpanded: false,
      insightSheetMounted: false,
      insightSheetActive: false,
      knowledgeSaving: false,
      knowledgeEntryId: "",
      itemOriginalView: { keywords: [], paragraphs: [], keyParagraphs: [] },
      viewMotionClass: "",
      message: "",
      messageTone: "info"
    });
    getItem(itemId)
      .then((item) =>
        getItemDiagnostics(itemId)
          .catch(() => null)
          .then((diagnosticsRes) => ({ item, diagnosticsRes }))
      )
      .then(({ item, diagnosticsRes }) => {
        const diagnostics = buildItemDiagnostics(item, diagnosticsRes);
        const message = item._fromMock
          ? this.data.i18n.localOnly
          : diagnosticsRes && diagnosticsRes._fromMock
            ? t(language, "item.diagnosticsUnavailable", "诊断接口暂不可用，当前仅展示内容主数据。")
            : "";
        const messageTone = item._fromMock || (diagnosticsRes && diagnosticsRes._fromMock)
          ? "warning"
          : "info";
        this.setData({
          itemOriginalView: buildOriginalViewModel({
            title: item.title,
            tags: (item.tags || []).map((tag) => tag.tag_name || tag),
            shortSummary: item.short_summary || "",
            content: item.clean_content || item.raw_content || this.data.i18n.originalEmpty
          }),
          item: {
            ...item,
            score100: scoreTo100(item.score_value),
            originalContent: item.clean_content || item.raw_content || this.data.i18n.originalEmpty,
            cardActionLabel:
              item.action_suggestion === "deep_read"
                ? t(getApp().globalData.preferences.language, "action.deep_read", "立即深读")
                : item.action_suggestion === "later"
                  ? t(getApp().globalData.preferences.language, "action.later", "稍后精读")
                  : t(getApp().globalData.preferences.language, "action.skip", "可放心忽略"),
            tagsText: (item.tags || []).map((tag) => tag.tag_name || tag),
            diagnostics
          },
          loading: false,
          loadError: false,
          message,
          messageTone
        }, () => this.triggerViewMotion());
      })
      .catch(() => {
        this.setData({ loading: false, loadError: true, item: null });
        wx.showToast({ title: this.data.i18n.loadingFailed, icon: "none" });
      });
  },

  openInterpretation() {
    const { item, insightData, insightLoading } = this.data;
    if (!item || insightLoading) return;
    this.setData({ currentView: "insight" }, () => this.triggerViewMotion());
    this.showInsightSheet();

    if (insightData) {
      this.setData({ insightExpanded: true });
      return;
    }

    this.setData({ insightLoading: true, insightExpanded: true, message: "" });
    interpretItem(item.id, {
      output_language: getApp().globalData.preferences.language,
      preview: item
    })
      .then((res) => {
        this.setData({
          insightLoading: false,
          insightData: res,
          insightExpanded: true
        });
        trackEvent("item_action", { action: "interpret_open", item_id: item.id });
      })
      .catch(() => {
        this.setData({ insightLoading: false, insightExpanded: false });
        this.hideInsightSheet();
        this.setData({ message: this.data.i18n.insightFailed, messageTone: "error" });
        wx.showToast({ title: this.data.i18n.insightFailed, icon: "none" });
      });
  },

  closeInterpretation() {
    this.hideInsightSheet();
    this.setData({ insightExpanded: false });
  },

  saveInsightToKnowledge() {
    const { item, insightData, knowledgeSaving } = this.data;
    if (!item || !insightData || knowledgeSaving) return;
    this.setData({ knowledgeSaving: true });
    addItemToKnowledge(item.id, {
      title: insightData.insight_title,
      content: insightData.knowledge_note,
      output_language: getApp().globalData.preferences.language
    })
      .then((res) => {
        this.setData({
          knowledgeSaving: false,
          knowledgeEntryId: res.entry_id,
          message: this.data.i18n.knowledgeSaved,
          messageTone: "success"
        });
        wx.showToast({ title: this.data.i18n.insightAdded, icon: "success" });
      })
      .catch(() => {
        this.setData({ knowledgeSaving: false, message: this.data.i18n.localOnly, messageTone: "warning" });
        wx.showToast({ title: this.data.i18n.localOnly, icon: "none" });
      });
    trackEvent("item_action", { action: "knowledge_add", item_id: item.id });
  },

  saveExcerptParagraph(e) {
    const { item, knowledgeSaving } = this.data;
    const paragraph = e.currentTarget.dataset.paragraph || "";
    const index = Number(e.currentTarget.dataset.index || 0);
    if (!item || !paragraph || knowledgeSaving) return;
    const language = getApp().globalData.preferences.language;
    this.setData({ knowledgeSaving: true });
    addItemToKnowledge(item.id, {
      title: buildExcerptTitle(item.title, index, language),
      content: paragraph,
      output_language: language
    })
      .then((res) => {
        this.setData({
          knowledgeSaving: false,
          knowledgeEntryId: res.entry_id,
          message: this.data.i18n.excerptSaved,
          messageTone: "success"
        });
      })
      .catch(() => {
        this.setData({ knowledgeSaving: false, message: this.data.i18n.excerptSaveFailed, messageTone: "error" });
      });
  },

  openKnowledgeEntry() {
    if (!this.data.knowledgeEntryId) return;
    wx.navigateTo({
      url: `/pages/knowledge/index?id=${this.data.knowledgeEntryId}`
    });
  },

  openKnowledgeList() {
    wx.navigateTo({
      url: "/pages/knowledge/index"
    });
  },

  switchView(e) {
    const view = e.currentTarget.dataset.view || "summary";
    if (view === "insight") {
      this.openInterpretation();
      return;
    }
    this.hideInsightSheet();
    this.setData({ currentView: view }, () => this.triggerViewMotion());
  },

  triggerViewMotion() {
    if (this._viewMotionTimer) {
      clearTimeout(this._viewMotionTimer);
    }
    this.setData({ viewMotionClass: "view-stage-enter" });
    this._viewMotionTimer = setTimeout(() => {
      this.setData({ viewMotionClass: "" });
    }, 280);
  },

  showInsightSheet() {
    if (this._insightSheetTimer) {
      clearTimeout(this._insightSheetTimer);
      this._insightSheetTimer = null;
    }
    if (this.data.insightSheetMounted && this.data.insightSheetActive) {
      return;
    }
    this.setData({ insightSheetMounted: true });
    this._insightSheetTimer = setTimeout(() => {
      this.setData({ insightSheetActive: true });
    }, 24);
  },

  hideInsightSheet() {
    if (!this.data.insightSheetMounted) return;
    if (this._insightSheetTimer) {
      clearTimeout(this._insightSheetTimer);
    }
    this.setData({ insightSheetActive: false });
    this._insightSheetTimer = setTimeout(() => {
      this.setData({ insightSheetMounted: false });
    }, 220);
  },

  noopTap() {},

  sendFeedback(type) {
    const { itemId } = this.data;
    if (!itemId) return;
    submitFeedback(itemId, type)
      .then((res) => {
        if (res && res.knowledge_status === "created") {
          const language = getApp().globalData.preferences.language;
        this.setData({
          message: buildArchiveHitMessage(language, res, type),
          knowledgeEntryId: res.knowledge_entry_id || this.data.knowledgeEntryId,
          messageTone: "success"
        });
        return;
      }
        if (res && res.knowledge_status === "existing") {
          const language = getApp().globalData.preferences.language;
        this.setData({
          message: buildArchiveHitMessage(language, res, type),
          knowledgeEntryId: res.knowledge_entry_id || this.data.knowledgeEntryId,
          messageTone: "success"
        });
        return;
      }
        this.setData({ message: `${this.data.i18n.feedbackSynced}：${type}`, messageTone: "info" });
      })
      .catch(() => this.setData({ message: this.data.i18n.localOnly, messageTone: "warning" }));
  },

  tapLike() {
    const liked = !this.data.liked;
    this.setData({ liked, ignored: liked ? false : this.data.ignored });
    this.sendFeedback("like");
    trackEvent("item_action", { action: "like", item_id: this.data.itemId });
  },

  tapIgnore() {
    const ignored = !this.data.ignored;
    this.setData({ ignored, liked: ignored ? false : this.data.liked });
    this.sendFeedback("ignore");
    trackEvent("item_action", { action: "ignore", item_id: this.data.itemId });
  },

  tapSave() {
    this.setData({ saved: !this.data.saved });
    this.sendFeedback("save");
    trackEvent("item_action", { action: "save", item_id: this.data.itemId });
  },

  tapInaccurate() {
    this.sendFeedback("inaccurate");
    trackEvent("item_action", { action: "inaccurate", item_id: this.data.itemId });
  },

  tapReprocess() {
    const { itemId } = this.data;
    if (!itemId) return;
    this.setData({ reprocessState: "processing", message: "" });
    reprocessItem(itemId, getApp().globalData.preferences.language)
      .then(() => {
        this.setData({ reprocessState: "done", message: this.data.i18n.reprocessSubmitted, messageTone: "success" });
        trackEvent("item_action", { action: "reprocess", item_id: itemId });
      })
      .catch(() => {
        this.setData({ reprocessState: "done", message: this.data.i18n.reprocessLocal, messageTone: "warning" });
      });
  },

  openSource() {
    const url = this.data.item && this.data.item.source_url;
    if (!url) {
      wx.showToast({ title: this.data.i18n.noLink, icon: "none" });
      return;
    }
    wx.setClipboardData({
      data: url,
      success: () => wx.showToast({ title: this.data.i18n.linkCopied, icon: "none" })
    });
  },

  reloadItem() {
    if (!this.data.itemId) return;
    this.loadItem(this.data.itemId);
  },

  openFeed() {
    wx.switchTab({
      url: "/pages/feed/index"
    });
  }
});
