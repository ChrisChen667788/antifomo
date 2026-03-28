const {
  getKnowledgeEntry,
  getKnowledgeMergePreview,
  mergeKnowledgeEntries
} = require("../../utils/api");
const { t } = require("../../utils/i18n");
const { getPreferenceClass } = require("../../utils/preferences");

Page({
  data: {
    entryIds: [],
    entries: [],
    mergeTitle: "",
    preview: null,
    mergedEntryId: "",
    loading: true,
    loadError: false,
    syncingPreview: false,
    merging: false,
    pageNotice: "",
    pageNoticeTone: "info",
    prefClass: "",
    settingsLabel: "设置",
    i18n: {}
  },

  onLoad(options) {
    const entryIds = String(options.ids || "")
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
    const mergeTitle = decodeURIComponent(options.title || "");
    this.setData({ entryIds, mergeTitle });
    this.applyPreferences();
    this.loadEntries(entryIds);
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
      title: t(language, "knowledge.mergeTitle", "知识卡片合并"),
      subtitle: t(language, "knowledge.mergeHint", "勾选 2 条及以上卡片后可合并为新卡片"),
      loading: t(language, "knowledge.loading", "正在加载知识卡片..."),
      empty: t(language, "knowledge.empty", "未找到这张知识卡片。"),
      emptyHint: t(language, "knowledge.loadFailedHint", "知识卡片暂时不可用，可以先重试或返回上一页。"),
      previewTitle: t(language, "knowledge.mergePreviewTitle", "合并预览"),
      previewHint: t(language, "knowledge.mergePreviewHint", "新卡片会继承选中卡片里更稳定的组织状态。"),
      previewReady: t(language, "knowledge.mergePreviewReady", "已满足合并条件"),
      previewWaiting: t(language, "knowledge.mergePreviewWaiting", "至少再选 1 张卡片才可合并"),
      inheritPinned: t(language, "knowledge.inheritPinned", "继承置顶"),
      inheritFocusRef: t(language, "knowledge.inheritFocusRef", "继承 Focus 参考"),
      inheritCollection: t(language, "knowledge.inheritCollection", "继承分组"),
      selected: t(language, "knowledge.selected", "已选中"),
      mergePlaceholder: t(language, "knowledge.mergePlaceholder", "可选：为合并后的卡片指定标题"),
      mergeAction: t(language, "knowledge.mergeAction", "合并为新卡片"),
      merging: t(language, "knowledge.merging", "合并中..."),
      mergeCreated: t(language, "knowledge.mergeCreated", "已生成新的合并知识卡片"),
      mergeFailed: t(language, "knowledge.mergeFailed", "合并失败，请稍后重试"),
      openMerged: t(language, "knowledge.openMerged", "打开新卡片"),
      back: t(language, "common.cancel", "取消"),
      retryLoad: t(language, "common.retryLoad", "重新加载"),
      source: t(language, "knowledge.source", "来源"),
      createdAt: t(language, "knowledge.createdAt", "创建时间")
    };
    this.setData({
      prefClass: getPreferenceClass(preferences, app.globalData.systemTheme),
      settingsLabel: t(language, "common.settings", "设置"),
      i18n
    });
    wx.setNavigationBarTitle({
      title: t(language, "knowledge.mergeTitle", "知识卡片合并")
    });
  },

  loadEntries(entryIds) {
    if (!Array.isArray(entryIds) || entryIds.length < 2) {
      this.setData({ loading: false, loadError: true });
      return;
    }
    this.setData({ loading: true, loadError: false, mergedEntryId: "", pageNotice: "" });
    Promise.all(entryIds.map((entryId) => getKnowledgeEntry(entryId)))
      .then((entries) => {
        this.setData({
          entries,
          loading: false,
          loadError: false
        }, () => this.syncPreview());
      })
      .catch(() => {
        this.setData({ loading: false, loadError: true, entries: [] });
      });
  },

  syncPreview() {
    const entryIds = this.data.entryIds || [];
    const entries = this.data.entries || [];
    if (entryIds.length < 1 || !entries.length) {
      this.setData({ preview: null });
      return;
    }
    this.setData({ syncingPreview: true });
    getKnowledgeMergePreview({
      entry_ids: entryIds,
      title: String(this.data.mergeTitle || "").trim() || undefined,
      preview_entries: entries
    })
      .then((preview) => {
        this.setData({ preview });
      })
      .catch(() => {
        this.setData({ preview: null });
      })
      .finally(() => {
        this.setData({ syncingPreview: false });
      });
  },

  onMergeTitleInput(e) {
    this.setData({ mergeTitle: e.detail.value || "" }, () => this.syncPreview());
  },

  submitMerge() {
    const entryIds = this.data.entryIds || [];
    if (entryIds.length < 2 || this.data.merging) return;
    this.setData({ merging: true, pageNotice: "" });
    mergeKnowledgeEntries({
      entry_ids: entryIds,
      title: String(this.data.mergeTitle || "").trim() || undefined
    })
      .then((entry) => {
        this.setData({
          merging: false,
          mergedEntryId: entry.id,
          pageNotice: this.data.i18n.mergeCreated,
          pageNoticeTone: "success"
        });
      })
      .catch(() => {
        this.setData({
          merging: false,
          pageNotice: this.data.i18n.mergeFailed,
          pageNoticeTone: "error"
        });
      });
  },

  openEntry(e) {
    const entryId = e.currentTarget.dataset.id;
    if (!entryId) return;
    wx.navigateTo({
      url: `/pages/knowledge/index?id=${entryId}`
    });
  },

  openMergedEntry() {
    const entryId = this.data.mergedEntryId;
    if (!entryId) return;
    wx.redirectTo({
      url: `/pages/knowledge/index?id=${entryId}`
    });
  },

  reloadEntries() {
    this.loadEntries(this.data.entryIds || []);
  },

  goBack() {
    if (this.data.entryIds && this.data.entryIds.length) {
      wx.redirectTo({
        url: "/pages/knowledge/index"
      });
      return;
    }
    wx.navigateBack({ delta: 1 });
  }
});
