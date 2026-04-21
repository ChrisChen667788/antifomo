const { t } = require("../../utils/i18n");
const {
  DEFAULT_PREFERENCES,
  getPreferenceClass
} = require("../../utils/preferences");
const {
  getPreferenceSummary,
  getLatestSession,
  getApiHealth,
  resetPreferences,
  getWorkBuddyHealth,
  sendWorkBuddyWebhook
} = require("../../utils/api");

const FONT_VALUES = ["system", "serif", "mono"];
const SIZE_VALUES = ["sm", "md", "lg"];
const LANGUAGE_VALUES = ["zh-CN", "zh-TW", "en", "ja", "ko"];
const THEME_VALUES = ["light", "dark", "system"];

Page({
  data: {
    preferences: DEFAULT_PREFERENCES,
    prefClass: "",
    i18n: {},
    fontOptions: [],
    sizeOptions: [],
    languageOptions: [],
    themeOptions: [],
    selectedFontIndex: 0,
    selectedSizeIndex: 1,
    selectedLanguageIndex: 0,
    apiBaseInput: "",
    apiBaseStatus: "",
    apiBaseTone: "info",
    preferenceSummary: null,
    preferenceMessage: "",
    preferenceTone: "info",
    preferenceLoading: false,
    preferenceResetting: false,
    runtimePlatformLabel: "",
    apiSuggestion: "",
    workbuddyHealth: null,
    workbuddyModeText: "",
    workbuddyProviderText: "",
    workbuddyRolesText: "",
    workbuddyRouteText: "",
    latestSessionId: "",
    workbuddyMessage: "",
    workbuddyOutput: "",
    workbuddyRunning: false
  },

  onLoad() {
    this.applyPreferences();
    this.refreshPreferenceSummary();
    this.refreshWorkBuddyStatus();
  },

  onShow() {
    this.applyPreferences();
    this.refreshPreferenceSummary();
    this.refreshWorkBuddyStatus();
  },

  applyPreferences() {
    const app = getApp();
    const preferences = app.globalData.preferences || DEFAULT_PREFERENCES;
    const language = preferences.language || "zh-CN";
    const runtimePlatform = app.globalData.runtimePlatform || "unknown";
    const runtimePlatformLabel =
      runtimePlatform === "devtools"
        ? (language === "en" ? "Developer Tools" : "开发者工具")
        : runtimePlatform === "ios"
          ? "iPhone"
          : runtimePlatform === "android"
            ? "Android"
            : runtimePlatform;

    const i18n = {
      kicker: t(language, "settings.kicker", "Control Panel"),
      title: t(language, "settings.title", "常用设置"),
      desc: t(language, "settings.desc", "设置会实时生效并保存在当前设备。"),
      font: t(language, "settings.font", "字体"),
      textSize: t(language, "settings.textSize", "文字大小"),
      language: t(language, "settings.language", "语言"),
      theme: t(language, "settings.theme", "外观模式"),
      reset: t(language, "settings.reset", "恢复默认"),
      preview: t(language, "common.previewText", "预览：设置将影响字体、字号、语言与主题。"),
      apiBaseTitle: t(language, "settings.apiBaseTitle", "后端连接"),
      apiBaseDesc: t(
        language,
        "settings.apiBaseDesc",
        language === "en"
          ? "The miniapp uses this API address. On a real device, localhost will not work."
          : "小程序通过这里连接后端。真机预览时不能使用 localhost / 127.0.0.1。"
      ),
      apiBaseLabel: t(language, "settings.apiBaseLabel", "API 地址"),
      apiBasePlaceholder: t(language, "settings.apiBasePlaceholder", "例如 http://192.168.50.99:8000"),
      apiBaseSave: t(language, "settings.apiBaseSave", "保存地址"),
      apiBaseTest: t(language, "settings.apiBaseTest", "测试连接"),
      apiBaseRuntime: t(language, "settings.apiBaseRuntime", "当前运行环境"),
      apiBaseSuggestion: t(language, "settings.apiBaseSuggestion", "推荐地址"),
      apiBaseSaved: t(language, "settings.apiBaseSaved", "API 地址已保存。"),
      apiBaseHealthy: t(language, "settings.apiBaseHealthy", "后端连接正常。"),
      apiBaseUnreachable: t(language, "settings.apiBaseUnreachable", "后端不可达，请检查地址和电脑服务。"),
      apiBaseLoopbackWarning: t(
        language,
        "settings.apiBaseLoopbackWarning",
        language === "en"
          ? "Real device preview cannot access localhost. Switch to your Mac LAN IP."
          : "真机预览无法访问 localhost，请改成你的 Mac 局域网 IP。"
      ),
      preferenceTitle: t(language, "settings.preferenceTitle", "偏好画像"),
      preferenceDesc: t(language, "settings.preferenceDesc", "查看系统根据你的反馈学习到的主题与来源权重。"),
      preferenceFeedbackTotal: t(language, "settings.preferenceFeedbackTotal", "累计反馈"),
      preferenceTopTags: t(language, "settings.preferenceTopTags", "主题偏好"),
      preferenceTopSources: t(language, "settings.preferenceTopSources", "来源偏好"),
      preferenceRefresh: t(language, "settings.preferenceRefresh", "刷新偏好"),
      preferenceReset: t(language, "settings.preferenceReset", "重置画像"),
      preferenceResetting: t(language, "settings.preferenceResetting", "重置中..."),
      preferenceEmpty: t(language, "settings.preferenceEmpty", "还没有稳定偏好，先多滑几张卡。"),
      preferenceResetDone: t(language, "settings.preferenceResetDone", "偏好画像已重置。"),
      preferenceLoadFailed: t(language, "settings.preferenceLoadFailed", "偏好数据读取失败。"),
      collector: t(language, "settings.collector", language === "en" ? "OCR Collector" : "打开 OCR 采集器"),
      workbuddyTitle: t(language, "settings.workbuddyTitle", "WorkBuddy 控制通道"),
      workbuddyDesc: t(language, "settings.workbuddyDesc", "检查 webhook 通道状态，并通过 WorkBuddy 事件触发导出任务。"),
      workbuddyReady: t(language, "settings.workbuddyReady", "通道已就绪"),
      workbuddyUnavailable: t(
        language,
        "settings.workbuddyUnavailable",
        language === "zh-TW"
          ? "API 目前不可用"
          : language === "en"
            ? "API unavailable"
            : language === "ja"
              ? "API は現在利用できません"
              : language === "ko"
                ? "API를 현재 사용할 수 없습니다"
                : "API 当前不可用"
      ),
      workbuddySignatureOn: t(language, "settings.workbuddySignatureOn", "签名校验：开启"),
      workbuddySignatureOff: t(language, "settings.workbuddySignatureOff", "签名校验：关闭"),
      workbuddyLatestSession: t(language, "settings.workbuddyLatestSession", "最近 Session"),
      workbuddyNoSession: t(language, "settings.workbuddyNoSession", "未找到可用 Session"),
      workbuddyRefresh: t(language, "settings.workbuddyRefresh", "刷新状态"),
      workbuddyPing: t(language, "settings.workbuddyPing", "发送 Ping"),
      workbuddyMarkdown: t(language, "settings.workbuddyMarkdown", "导出 Markdown"),
      workbuddyReadingList: t(language, "settings.workbuddyReadingList", "导出稍后读"),
      workbuddyTodoDraft: t(language, "settings.workbuddyTodoDraft", "导出待办草稿"),
      workbuddyRunning: t(language, "settings.workbuddyRunning", "执行中..."),
      workbuddyOutputTitle: t(language, "settings.workbuddyOutputTitle", "最近输出"),
      workbuddyOutputEmpty: t(language, "settings.workbuddyOutputEmpty", "这里会显示最近一次 webhook 返回的任务结果。"),
      workbuddyNeedSession: t(language, "settings.workbuddyNeedSession", "该任务需要 Session，先完成一轮 Focus。"),
      workbuddyPingDone: t(language, "settings.workbuddyPingDone", "Ping 已返回 pong。"),
      workbuddyTaskDone: t(language, "settings.workbuddyTaskDone", "WorkBuddy 任务已执行完成。"),
      workbuddyFailed: t(language, "settings.workbuddyFailed", "WorkBuddy 通道调用失败。"),
      workbuddyCliReady: t(language, "settings.workbuddyCliReady", "官方 CLI：已检测"),
      workbuddyCliMissing: t(language, "settings.workbuddyCliMissing", "官方 CLI：未检测到"),
      workbuddyCliAuthed: t(language, "settings.workbuddyCliAuthed", "官方 CLI：已登录"),
      workbuddyCliLoginRequired: t(language, "settings.workbuddyCliLoginRequired", "官方 CLI：需要登录 CodeBuddy"),
      workbuddyGatewayReady: t(language, "settings.workbuddyGatewayReady", "官方 Gateway：已连通"),
      workbuddyGatewayMissing: t(language, "settings.workbuddyGatewayMissing", "官方 Gateway：未配置"),
      workbuddyGatewayDown: t(language, "settings.workbuddyGatewayDown", "官方 Gateway：已配置但未连通"),
      workbuddyGatewayLabel: t(language, "settings.workbuddyGatewayLabel", "Gateway 地址"),
      workbuddyOfficialHint: t(language, "settings.workbuddyOfficialHint", "如需切到腾讯官方链路，请先完成 CodeBuddy 登录并启动官方 Gateway。"),
      workbuddyProvider: t(language, "settings.workbuddyProvider", "当前提供方"),
      workbuddyMode: t(language, "settings.workbuddyMode", "当前接入模式"),
      workbuddyRoles: t(language, "settings.workbuddyRoles", "当前实际作用"),
      workbuddyRoute: t(language, "settings.workbuddyRoute", "默认执行路径"),
      workbuddyModeOfficialCli: t(language, "settings.workbuddyModeOfficialCli", "腾讯官方 CodeBuddy CLI 桥接"),
      workbuddyModeOfficialGateway: t(language, "settings.workbuddyModeOfficialGateway", "腾讯官方 CodeBuddy Gateway 桥接"),
      workbuddyModeLocal: t(language, "settings.workbuddyModeLocal", "本地兼容 webhook 适配层"),
      workbuddyRouteOfficial: t(language, "settings.workbuddyRouteOfficial", "默认优先走腾讯官方通道"),
      workbuddyRouteLocal: t(language, "settings.workbuddyRouteLocal", "当前回退到本地兼容通道"),
      workbuddyRolesEmpty: t(language, "settings.workbuddyRolesEmpty", "未返回角色信息"),
      workbuddyUnavailableDetail: t(language, "settings.workbuddyUnavailableDetail", "暂未读取到后端 WorkBuddy 状态")
    };

    const fontOptions = FONT_VALUES.map((value) => t(language, `settings.font.${value}`, value));
    const sizeOptions = SIZE_VALUES.map((value) => t(language, `settings.textSize.${value}`, value));
    const languageOptions = LANGUAGE_VALUES.map((value) => t(language, `settings.language.${value}`, value));
    const themeOptions = THEME_VALUES.map((value) => ({
      value,
      label: t(language, `settings.theme.${value}`, value)
    }));

    this.setData({
      preferences,
      prefClass: getPreferenceClass(preferences, app.globalData.systemTheme),
      i18n,
      fontOptions,
      sizeOptions,
      languageOptions,
      themeOptions,
      selectedFontIndex: Math.max(0, FONT_VALUES.indexOf(preferences.fontFamily)),
      selectedSizeIndex: Math.max(0, SIZE_VALUES.indexOf(preferences.textSize)),
      selectedLanguageIndex: Math.max(0, LANGUAGE_VALUES.indexOf(preferences.language)),
      apiBaseInput: app.globalData.apiBaseUrl || "",
      runtimePlatformLabel,
      apiSuggestion: app.globalData.recommendedLanApiBaseUrl || ""
    });

    wx.setNavigationBarTitle({
      title: t(language, "common.settingsPageTitle", "设置")
    });
  },

  updatePreferences(patch) {
    const app = getApp();
    app.applyPreferences(patch);
    this.applyPreferences();
  },

  onFontChange(e) {
    const index = Number(e.detail.value || 0);
    this.updatePreferences({ fontFamily: FONT_VALUES[index] });
  },

  onSizeChange(e) {
    const index = Number(e.detail.value || 0);
    this.updatePreferences({ textSize: SIZE_VALUES[index] });
  },

  onLanguageChange(e) {
    const index = Number(e.detail.value || 0);
    this.updatePreferences({ language: LANGUAGE_VALUES[index] });
  },

  onThemeChange(e) {
    const next = e.currentTarget.dataset.value;
    if (!next) return;
    this.updatePreferences({ themeMode: next });
  },

  onReset() {
    const app = getApp();
    app.applyPreferences(DEFAULT_PREFERENCES);
    this.applyPreferences();
  },

  refreshPreferenceSummary() {
    this.setData({ preferenceLoading: true });
    return getPreferenceSummary()
      .then((summary) => {
        this.setData({
          preferenceSummary: summary,
          preferenceMessage: summary._fromMock ? this.data.i18n.preferenceLoadFailed : "",
          preferenceTone: summary._fromMock ? "warning" : "info",
          preferenceLoading: false
        });
      })
      .catch(() => {
        this.setData({
          preferenceLoading: false,
          preferenceMessage: this.data.i18n.preferenceLoadFailed,
          preferenceTone: "warning"
        });
      });
  },

  onResetPreferenceSummary() {
    this.setData({ preferenceResetting: true });
    resetPreferences("all")
      .then((summary) => {
        this.setData({
          preferenceSummary: summary,
          preferenceMessage: this.data.i18n.preferenceResetDone,
          preferenceTone: summary._fromMock ? "warning" : "success",
          preferenceResetting: false
        });
      })
      .catch(() => {
        this.setData({
          preferenceResetting: false,
          preferenceMessage: this.data.i18n.preferenceLoadFailed,
          preferenceTone: "warning"
        });
      });
  },

  onOpenCollector() {
    wx.navigateTo({
      url: "/pages/collector/index"
    });
  },

  sanitizeApiBase(value) {
    const raw = String(value || "").trim();
    if (!raw) return "";
    const withProtocol = /^https?:\/\//i.test(raw) ? raw : `http://${raw}`;
    return withProtocol.replace(/\/+$/, "");
  },

  onApiBaseInput(e) {
    this.setData({
      apiBaseInput: e.detail.value || ""
    });
  },

  onSaveApiBase() {
    const app = getApp();
    const sanitized = this.sanitizeApiBase(this.data.apiBaseInput);
    if (!sanitized) {
      this.setData({
        apiBaseStatus: this.data.i18n.apiBaseUnreachable,
        apiBaseTone: "error"
      });
      return;
    }
    app.globalData.apiBaseUrl = sanitized;
    wx.setStorageSync("apiBaseUrl", sanitized);
    this.setData({
      apiBaseInput: sanitized,
      apiBaseStatus: this.data.i18n.apiBaseSaved,
      apiBaseTone: "success"
    });
  },

  onUseSuggestedApiBase() {
    if (!this.data.apiSuggestion) return;
    this.setData({
      apiBaseInput: this.data.apiSuggestion
    });
    this.onSaveApiBase();
  },

  onTestApiBase() {
    const language = (getApp().globalData.preferences || {}).language || "zh-CN";
    const sanitized = this.sanitizeApiBase(this.data.apiBaseInput);
    if (!sanitized) {
      this.setData({
        apiBaseStatus: this.data.i18n.apiBaseUnreachable,
        apiBaseTone: "error"
      });
      return;
    }
    const isDevtools = !!getApp().globalData.isDevtools;
    if (!isDevtools && /^https?:\/\/(?:127\.0\.0\.1|localhost)(?::\d+)?/i.test(sanitized)) {
      this.setData({
        apiBaseStatus: this.data.i18n.apiBaseLoopbackWarning,
        apiBaseTone: "warning"
      });
      return;
    }
    this.setData({
      apiBaseStatus: t(language, "settings.workbuddyRunning", "执行中..."),
      apiBaseTone: "info"
    });
    getApiHealth(sanitized)
      .then(() => {
        this.setData({
          apiBaseStatus: this.data.i18n.apiBaseHealthy,
          apiBaseTone: "success"
        });
      })
      .catch((error) => {
        const message =
          error && error.message && /REAL_DEVICE_LOOPBACK_API_BASE/.test(String(error.message))
            ? this.data.i18n.apiBaseLoopbackWarning
            : this.data.i18n.apiBaseUnreachable;
        this.setData({
          apiBaseStatus: message,
          apiBaseTone: "error"
        });
      });
  },

  refreshWorkBuddyStatus() {
    const language = (getApp().globalData.preferences || {}).language || "zh-CN";
    return Promise.allSettled([getWorkBuddyHealth(), getLatestSession()]).then((results) => {
      const healthRes = results[0];
      const sessionRes = results[1];
      const health = healthRes.status === "fulfilled" ? healthRes.value : null;
      const integrationMode = health && health.integration_mode ? String(health.integration_mode) : "";
      const workbuddyModeText =
        integrationMode === "official_gateway_bridge"
          ? this.data.i18n.workbuddyModeOfficialGateway
          : integrationMode === "official_cli_bridge"
            ? this.data.i18n.workbuddyModeOfficialCli
            : integrationMode === "local_webhook_adapter"
              ? this.data.i18n.workbuddyModeLocal
              : this.data.i18n.workbuddyUnavailableDetail;
      const workbuddyProviderText =
        health && health.provider_label ? String(health.provider_label) : this.data.i18n.workbuddyUnavailableDetail;
      const workbuddyRolesText =
        health && Array.isArray(health.active_roles) && health.active_roles.length
          ? health.active_roles.join(" / ")
          : this.data.i18n.workbuddyRolesEmpty;
      const workbuddyRouteText =
        health && health.official_tencent_connected
          ? this.data.i18n.workbuddyRouteOfficial
          : this.data.i18n.workbuddyRouteLocal;
      this.setData({
        workbuddyHealth: health,
        workbuddyModeText,
        workbuddyProviderText,
        workbuddyRolesText,
        workbuddyRouteText,
        latestSessionId: sessionRes.status === "fulfilled" ? (sessionRes.value.id || "") : "",
        workbuddyMessage:
          healthRes.status === "fulfilled"
            ? (health && health.official_tencent_connected
              ? this.data.i18n.workbuddyRouteOfficial
              : t(language, "settings.workbuddyReady", "通道已就绪"))
            : ""
      });
    }).catch(() => {
      this.setData({
        workbuddyMessage: this.data.i18n.workbuddyFailed
      });
    });
  },

  buildWorkBuddyRequestId(prefix) {
    return `${prefix}_${Date.now()}`;
  },

  runWorkBuddy(eventType, taskType) {
    if (this.data.workbuddyRunning) {
      return;
    }

    if (
      eventType === "create_task" &&
      taskType &&
      taskType !== "export_reading_list" &&
      !this.data.latestSessionId
    ) {
      this.setData({ workbuddyMessage: this.data.i18n.workbuddyNeedSession });
      return;
    }

    this.setData({
      workbuddyRunning: true,
      workbuddyMessage: this.data.i18n.workbuddyRunning
    });

    const payload =
      eventType === "ping"
        ? {
            event_type: "ping",
            request_id: this.buildWorkBuddyRequestId("wb_ping")
          }
        : {
            event_type: "create_task",
            request_id: this.buildWorkBuddyRequestId("wb_task"),
            task_type: taskType,
            session_id:
              taskType !== "export_reading_list" ? (this.data.latestSessionId || undefined) : undefined,
            input_payload: {
              output_language: (getApp().globalData.preferences || {}).language || "zh-CN"
            }
          };

    sendWorkBuddyWebhook(payload)
      .then((res) => {
        this.setData({
          workbuddyMessage:
            eventType === "ping" ? this.data.i18n.workbuddyPingDone : this.data.i18n.workbuddyTaskDone,
          workbuddyOutput:
            res && res.task && res.task.output_payload && res.task.output_payload.content
              ? String(res.task.output_payload.content)
              : ""
        });
      })
      .catch(() => {
        this.setData({
          workbuddyMessage: this.data.i18n.workbuddyFailed
        });
      })
      .finally(() => {
        this.setData({ workbuddyRunning: false });
      });
  },

  onWorkBuddyRefresh() {
    this.refreshWorkBuddyStatus();
  },

  onWorkBuddyPing() {
    this.runWorkBuddy("ping");
  },

  onWorkBuddyMarkdown() {
    this.runWorkBuddy("create_task", "export_markdown_summary");
  },

  onWorkBuddyReadingList() {
    this.runWorkBuddy("create_task", "export_reading_list");
  },

  onWorkBuddyTodoDraft() {
    this.runWorkBuddy("create_task", "export_todo_draft");
  }
});
