const COPY = {
  "zh-CN": {
    live: "实时 API 数据",
    degraded: "实时 API · 降级内容；请在详情页复核采集诊断",
    empty: "实时 API · 暂无数据；未回退演示内容",
    unavailable: "实时 API · 不可用；当前未展示替代内容",
    demo: "本地演示数据；不能当作实时同步内容"
  },
  "zh-TW": {
    live: "即時 API 資料",
    degraded: "即時 API · 降級內容；請在詳情頁覆核採集診斷",
    empty: "即時 API · 暫無資料；未回退演示內容",
    unavailable: "即時 API · 不可用；目前未顯示替代內容",
    demo: "本地演示資料；不能當作即時同步內容"
  },
  en: {
    live: "Live API data",
    degraded: "Live API · degraded content; review collector diagnostics in item detail",
    empty: "Live API · no data; demo content was not substituted",
    unavailable: "Live API · unavailable; no substitute content is shown",
    demo: "Local demo data; this is not live synchronized content"
  }
};

function hasFallbackContent(items) {
  return Array.isArray(items) && items.some((item) => item && item.fallback_used === true);
}

function resolveDataSourceState(options = {}) {
  if (options.fromMock) return "demo";
  if (options.unavailable) return "unavailable";
  const items = Array.isArray(options.items) ? options.items : [];
  if (options.fallbackUsed || hasFallbackContent(items)) return "degraded";
  const itemCount = options.itemCount !== undefined ? Number(options.itemCount) : items.length;
  if (!Number.isFinite(itemCount) || itemCount <= 0) return "empty";
  return "live";
}

function getDataSourceStateCopy(language, state) {
  const dictionary = COPY[language] || COPY.en;
  return dictionary[state] || dictionary.live;
}

function getDataSourceStateTone(state) {
  return state === "demo" || state === "degraded" || state === "unavailable" ? "warning" : "info";
}

module.exports = {
  getDataSourceStateCopy,
  getDataSourceStateTone,
  hasFallbackContent,
  resolveDataSourceState
};
