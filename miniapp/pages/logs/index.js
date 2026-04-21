const { clearEvents, listEvents } = require("../../utils/analytics");
const { t } = require("../../utils/i18n");
const { getPreferenceClass } = require("../../utils/preferences");

function formatTs(ts) {
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) {
    return "";
  }
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

Page({
  data: {
    events: [],
    replayList: [],
    replaying: false,
    replayIndex: -1,
    prefClass: "",
    settingsLabel: "设置",
    i18n: {}
  },

  onLoad() {
    this.applyPreferences();
    this.refreshEvents();
  },

  onShow() {
    this.applyPreferences();
    this.refreshEvents();
  },

  onUnload() {
    this.stopReplay();
  },

  applyPreferences() {
    const app = getApp();
    const preferences = app.globalData.preferences;
    const language = preferences.language;
    const i18n = {
      kicker: t(language, "logs.kicker", "Analytics"),
      title: t(language, "logs.title", "操作日志回放"),
      subtitle: t(language, "logs.subtitle", "查看关键交互埋点，并按时间顺序回放用户操作轨迹。"),
      refresh: t(language, "logs.refresh", "刷新"),
      startReplay: t(language, "logs.startReplay", "开始回放"),
      replaying: t(language, "logs.replaying", "回放中..."),
      stopReplay: t(language, "logs.stopReplay", "停止回放"),
      clear: t(language, "logs.clear", "清空日志"),
      progress: t(language, "logs.progress", "回放进度"),
      empty: t(language, "logs.empty", "暂无日志。先在首页/解决方案智囊/专注页面做一些操作再回来查看。"),
      replayCurrent: t(language, "logs.replayCurrent", "Replay Current"),
      cleared: t(language, "logs.cleared", "已清空日志"),
      noReplay: t(language, "logs.noReplay", "暂无日志可回放"),
      replayDone: t(language, "logs.replayDone", "回放完成")
    };
    this.setData({
      prefClass: getPreferenceClass(preferences, app.globalData.systemTheme),
      settingsLabel: t(language, "common.settings", "设置"),
      i18n
    });
    wx.setNavigationBarTitle({
      title: t(language, "logs.title", "Logs")
    });
  },

  refreshEvents() {
    const events = listEvents(240).map((evt) => ({
      ...evt,
      timeText: formatTs(evt.ts),
      payloadText: JSON.stringify(evt.payload || {})
    }));
    this.setData({ events });
  },

  clearAll() {
    clearEvents();
    this.stopReplay();
    this.setData({ events: [], replayList: [], replayIndex: -1 });
    wx.showToast({ title: this.data.i18n.cleared, icon: "none" });
  },

  startReplay() {
    if (this.data.replaying) {
      return;
    }
    const replayList = this.data.events.slice().reverse();
    if (!replayList.length) {
      wx.showToast({ title: this.data.i18n.noReplay, icon: "none" });
      return;
    }
    this.setData({
      replaying: true,
      replayList,
      replayIndex: 0
    });
    this.runReplayTick();
  },

  runReplayTick() {
    this.stopReplayTimer();
    this._replayTimer = setInterval(() => {
      if (!this.data.replaying) {
        this.stopReplayTimer();
        return;
      }
      const next = this.data.replayIndex + 1;
      if (next >= this.data.replayList.length) {
        this.stopReplay();
        wx.showToast({ title: this.data.i18n.replayDone, icon: "none" });
        return;
      }
      this.setData({ replayIndex: next });
    }, 700);
  },

  stopReplayTimer() {
    if (this._replayTimer) {
      clearInterval(this._replayTimer);
      this._replayTimer = null;
    }
  },

  stopReplay() {
    this.stopReplayTimer();
    this.setData({ replaying: false });
  }
});
