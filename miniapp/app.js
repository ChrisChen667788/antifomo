const { getTabLabels, t } = require("./utils/i18n");
const { DEFAULT_PREFERENCES, loadPreferences, normalizePreferences, savePreferences } = require("./utils/preferences");

App({
  globalData: {
    apiBaseUrl: "http://127.0.0.1:8000",
    recommendedLanApiBaseUrl: "http://192.168.50.99:8000",
    currentSessionId: "",
    currentSessionGoal: "",
    currentSessionDuration: 25,
    currentFeedMode: "normal",
    focusOwnsWechatAgent: false,
    preferences: DEFAULT_PREFERENCES,
    systemTheme: "light",
    runtimePlatform: "unknown",
    isDevtools: false
  },
  onLaunch() {
    const savedApiBase = wx.getStorageSync("apiBaseUrl");
    if (savedApiBase) {
      this.globalData.apiBaseUrl = savedApiBase;
    }

    try {
      const systemInfo = wx.getSystemInfoSync();
      this.globalData.systemTheme = systemInfo.theme === "dark" ? "dark" : "light";
      this.globalData.runtimePlatform = systemInfo.platform || "unknown";
      this.globalData.isDevtools = systemInfo.platform === "devtools";
    } catch (_) {
      this.globalData.systemTheme = "light";
      this.globalData.runtimePlatform = "unknown";
      this.globalData.isDevtools = false;
    }

    if (
      !this.globalData.isDevtools &&
      /^https?:\/\/(?:127\.0\.0\.1|localhost)(?::\d+)?/i.test(this.globalData.apiBaseUrl) &&
      this.globalData.recommendedLanApiBaseUrl
    ) {
      this.globalData.apiBaseUrl = this.globalData.recommendedLanApiBaseUrl;
      wx.setStorageSync("apiBaseUrl", this.globalData.apiBaseUrl);
    }

    this.globalData.preferences = loadPreferences();
    this.updateTabBarLanguage();

    if (wx.onThemeChange) {
      wx.onThemeChange((res) => {
        this.globalData.systemTheme = res.theme === "dark" ? "dark" : "light";
        const pages = getCurrentPages();
        const currentPage = pages[pages.length - 1];
        if (currentPage && typeof currentPage.applyPreferences === "function") {
          currentPage.applyPreferences();
        }
      });
    }
  },

  applyPreferences(patch) {
    const next = normalizePreferences({
      ...this.globalData.preferences,
      ...patch
    });
    this.globalData.preferences = savePreferences(next);
    this.updateTabBarLanguage();
    return this.globalData.preferences;
  },

  getSettingsButtonLabel() {
    return t(this.globalData.preferences.language, "common.settings", "设置");
  },

  updateTabBarLanguage() {
    const labels = getTabLabels(this.globalData.preferences.language);
    labels.forEach((label, index) => {
      wx.setTabBarItem({
        index,
        text: label
      });
    });
  }
});
