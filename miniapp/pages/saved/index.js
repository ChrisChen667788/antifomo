const { listSavedItems } = require("../../utils/api");
const { scoreTo100 } = require("../../utils/format");
const { t } = require("../../utils/i18n");
const { getPreferenceClass } = require("../../utils/preferences");

function relevanceScore(item) {
  let score = item.score100 || 50;
  const tags = item.tagsText || [];
  if (tags.some((tag) => String(tag).toLowerCase().indexOf("ai") >= 0)) score += 8;
  if (tags.some((tag) => String(tag).indexOf("商业") >= 0)) score += 4;
  if (tags.some((tag) => String(tag).indexOf("求职") >= 0)) score += 4;
  return score;
}

Page({
  data: {
    sourceItems: [],
    items: [],
    loading: true,
    tagFilter: "all",
    sortMode: "latest",
    sortLabel: "",
    tagOptions: [],
    sortOptions: [],
    prefClass: "",
    settingsLabel: "设置",
    i18n: {}
  },

  onLoad() {
    this.applyPreferences();
    this.loadItems();
  },

  onShow() {
    this.applyPreferences();
  },

  onPullDownRefresh() {
    this.loadItems().finally(() => wx.stopPullDownRefresh());
  },

  applyPreferences() {
    const app = getApp();
    const preferences = app.globalData.preferences;
    const language = preferences.language;
    const i18n = {
      kicker: t(language, "saved.kicker", "稍后再读"),
      title: t(language, "saved.title", "稍后再读"),
      subtitle: t(language, "saved.subtitle", "把值得继续消化的内容沉淀成稳定的回看清单。"),
      filter: t(language, "saved.filter", "筛选"),
      sort: t(language, "saved.sort", "排序"),
      loading: t(language, "saved.loading", "正在加载稍后再读内容..."),
      empty: t(language, "saved.empty", "当前筛选条件下暂无稍后再读内容。"),
      score: t(language, "saved.score", "评分"),
      source: t(language, "saved.source", "来源"),
      detail: t(language, "saved.detail", "查看详情"),
      untitled: t(language, "common.untitled", "未命名内容"),
      unknownSource: t(language, "common.unknownSource", "未知来源")
    };
    this.setData({
      prefClass: getPreferenceClass(preferences, app.globalData.systemTheme),
      settingsLabel: t(language, "common.settings", "设置"),
      i18n,
      tagOptions: [
        { key: "all", label: t(language, "saved.filter.all", "全部") },
        { key: "ai", label: t(language, "saved.filter.ai", "AI") },
        { key: "business", label: t(language, "saved.filter.business", "商业") },
        { key: "job", label: t(language, "saved.filter.job", "求职") }
      ],
      sortOptions: [
        { key: "latest", label: t(language, "saved.sort.latest", "最新") },
        { key: "score", label: t(language, "saved.sort.score", "评分") },
        { key: "relevance", label: t(language, "saved.sort.relevance", "最相关") }
      ],
      sortLabel:
        ({
          latest: t(language, "saved.sort.latest", "最新"),
          score: t(language, "saved.sort.score", "评分"),
          relevance: t(language, "saved.sort.relevance", "最相关")
        })[this.data.sortMode] || t(language, "saved.sort.latest", "最新")
    });
    wx.setNavigationBarTitle({
      title: t(language, "nav.saved", "Saved")
    });
  },

  loadItems() {
    this.setData({ loading: true });
    return listSavedItems(50)
      .then((res) => {
        const sourceItems = (res.items || []).map((item) => ({
          ...item,
          score100: scoreTo100(item.score_value),
          tagsText: (item.tags || []).map((tag) => tag.tag_name || tag)
        }));
        this.setData({ sourceItems, loading: false }, () => this.applyFilters());
      })
      .catch(() => {
        this.setData({ loading: false });
      });
  },

  setTagFilter(e) {
    this.setData({ tagFilter: e.currentTarget.dataset.key }, () => this.applyFilters());
  },

  setSortMode(e) {
    const index = Number(e.detail.value || 0);
    const next = this.data.sortOptions[index];
    this.setData({ sortMode: next.key, sortLabel: next.label }, () => this.applyFilters());
  },

  applyFilters() {
    const { sourceItems, tagFilter, sortMode } = this.data;
    let result = sourceItems.filter((item) => {
      if (tagFilter === "all") return true;
      if (tagFilter === "ai") {
        return (item.tagsText || []).some((tag) => String(tag).toLowerCase().indexOf("ai") >= 0);
      }
      if (tagFilter === "business") {
        return (item.tagsText || []).some((tag) => String(tag).indexOf("商业") >= 0 || String(tag).toLowerCase().indexOf("business") >= 0);
      }
      return (item.tagsText || []).some((tag) => String(tag).indexOf("求职") >= 0 || String(tag).toLowerCase().indexOf("job") >= 0);
    });

    if (sortMode === "score") {
      result = result.slice().sort((a, b) => (b.score100 || 0) - (a.score100 || 0));
    } else if (sortMode === "relevance") {
      result = result.slice().sort((a, b) => relevanceScore(b) - relevanceScore(a));
    }

    this.setData({ items: result });
  },

  openDetail(e) {
    const itemId = e.currentTarget.dataset.id;
    wx.navigateTo({
      url: `/pages/item/index?id=${itemId}`
    });
  }
});
