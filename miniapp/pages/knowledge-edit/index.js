const { getKnowledgeEntry, updateKnowledgeEntry } = require("../../utils/api");
const { t } = require("../../utils/i18n");
const { getPreferenceClass } = require("../../utils/preferences");

Page({
  data: {
    entryId: "",
    entry: null,
    draftTitle: "",
    draftContent: "",
    draftCollection: "",
    draftPinned: false,
    draftFocusReference: false,
    loading: true,
    loadError: false,
    saving: false,
    pageNotice: "",
    pageNoticeTone: "info",
    prefClass: "",
    settingsLabel: "设置",
    i18n: {}
  },

  onLoad(options) {
    const entryId = options.id || "";
    this.setData({ entryId });
    this.applyPreferences();
    if (!entryId) {
      this.setData({ loading: false, loadError: true });
      return;
    }
    this.loadEntry(entryId);
  },

  onShow() {
    this.applyPreferences();
  },

  applyPreferences() {
    const app = getApp();
    const preferences = app.globalData.preferences;
    const language = preferences.language;
    const i18n = {
      kicker: t(language, "knowledge.kicker", "知识库"),
      title: t(language, "knowledge.edit", "编辑"),
      subtitle: t(language, "knowledge.subtitle", "将沉淀下来的结构化理解整理成可复用记录。"),
      loading: t(language, "knowledge.loading", "正在加载知识卡片..."),
      empty: t(language, "knowledge.empty", "未找到这张知识卡片。"),
      emptyHint: t(language, "knowledge.loadFailedHint", "知识卡片暂时不可用，可以先重试或返回上一页。"),
      source: t(language, "knowledge.source", "来源"),
      createdAt: t(language, "knowledge.createdAt", "创建时间"),
      updatedAt: t(language, "knowledge.updatedAt", "最近更新"),
      content: t(language, "knowledge.content", "卡片内容"),
      group: t(language, "knowledge.group", "分组"),
      groupPlaceholder: t(language, "knowledge.groupPlaceholder", "输入分组名称，例如：AI 制药"),
      focusRef: t(language, "knowledge.focusRef", "Focus 参考"),
      pin: t(language, "knowledge.pin", "置顶"),
      save: t(language, "common.save", "保存"),
      saving: t(language, "common.saving", "保存中..."),
      cancel: t(language, "common.cancel", "取消"),
      retryLoad: t(language, "common.retryLoad", "重新加载"),
      editSaved: t(language, "knowledge.editSaved", "知识卡片已保存"),
      editSaveFailed: t(language, "knowledge.editSaveFailed", "保存失败，请稍后重试"),
      editValidation: t(language, "knowledge.editValidation", "标题和内容都需要保留，避免生成空卡片。"),
      openItem: t(language, "knowledge.openItem", "打开原内容详情"),
      openCard: t(language, "knowledge.openRelated", "查看卡片")
    };
    this.setData({
      prefClass: getPreferenceClass(preferences, app.globalData.systemTheme),
      settingsLabel: t(language, "common.settings", "设置"),
      i18n
    });
    wx.setNavigationBarTitle({
      title: `${t(language, "knowledge.title", "知识卡片")} · ${t(language, "knowledge.edit", "编辑")}`
    });
  },

  loadEntry(entryId) {
    this.setData({ loading: true, loadError: false, pageNotice: "" });
    getKnowledgeEntry(entryId)
      .then((entry) => {
        this.setData({
          loading: false,
          loadError: false,
          entry,
          draftTitle: entry.title || "",
          draftContent: entry.content || "",
          draftCollection: entry.collection_name || "",
          draftPinned: !!entry.is_pinned,
          draftFocusReference: !!entry.is_focus_reference,
          pageNotice: entry._fromMock ? this.data.i18n.emptyHint : "",
          pageNoticeTone: entry._fromMock ? "warning" : "info"
        });
      })
      .catch(() => {
        this.setData({ loading: false, loadError: true, entry: null });
      });
  },

  onTitleInput(e) {
    this.setData({ draftTitle: e.detail.value || "" });
  },

  onContentInput(e) {
    this.setData({ draftContent: e.detail.value || "" });
  },

  onCollectionInput(e) {
    this.setData({ draftCollection: e.detail.value || "" });
  },

  togglePinnedDraft() {
    this.setData({ draftPinned: !this.data.draftPinned });
  },

  toggleFocusDraft() {
    this.setData({ draftFocusReference: !this.data.draftFocusReference });
  },

  saveEntry() {
    const entryId = this.data.entryId;
    if (!entryId || this.data.saving) return;
    const title = String(this.data.draftTitle || "").trim();
    const content = String(this.data.draftContent || "").trim();
    const collectionName = String(this.data.draftCollection || "").trim();
    if (!title || !content) {
      this.setData({
        pageNotice: this.data.i18n.editValidation,
        pageNoticeTone: "error"
      });
      return;
    }

    this.setData({ saving: true, pageNotice: "" });
    updateKnowledgeEntry(entryId, {
      title,
      content,
      collection_name: collectionName || null,
      is_pinned: !!this.data.draftPinned,
      is_focus_reference: !!this.data.draftFocusReference
    })
      .then((entry) => {
        this.setData({
          entry,
          draftTitle: entry.title || "",
          draftContent: entry.content || "",
          draftCollection: entry.collection_name || "",
          draftPinned: !!entry.is_pinned,
          draftFocusReference: !!entry.is_focus_reference,
          saving: false,
          pageNotice: this.data.i18n.editSaved,
          pageNoticeTone: "success"
        });
      })
      .catch(() => {
        this.setData({
          saving: false,
          pageNotice: this.data.i18n.editSaveFailed,
          pageNoticeTone: "error"
        });
      });
  },

  reloadEntry() {
    if (!this.data.entryId) return;
    this.loadEntry(this.data.entryId);
  },

  backToDetail() {
    if (this.data.entryId) {
      wx.redirectTo({
        url: `/pages/knowledge/index?id=${this.data.entryId}`
      });
      return;
    }
    wx.navigateBack({ delta: 1 });
  },

  openItem() {
    const itemId = this.data.entry && this.data.entry.item_id;
    if (!itemId) return;
    wx.navigateTo({
      url: `/pages/item/index?id=${itemId}`
    });
  }
});
