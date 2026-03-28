const {
  flushPendingQueue,
  getMobileDailyBrief,
  getWechatAgentStatus,
  listItems,
  listKnowledgeEntries,
  submitFeedback
} = require("../../utils/api");
const { formatTime, scoreTo100 } = require("../../utils/format");
const { trackEvent } = require("../../utils/analytics");
const { t } = require("../../utils/i18n");
const { getPreferenceClass } = require("../../utils/preferences");

const SWIPE_MAX = 220;
const SWIPE_THRESHOLD = 108;

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function buildCardStyle(offsetX, offsetY, rotateDeg, opacity, withTransition) {
  return [
    `transform: translate3d(${offsetX}rpx, ${offsetY}rpx, 0) rotate(${rotateDeg}deg);`,
    `opacity: ${opacity};`,
    withTransition
      ? "transition: transform 280ms cubic-bezier(0.22, 0.8, 0.22, 1), opacity 220ms ease;"
      : "transition: none;"
  ].join(" ");
}

function buildPreviewSummary(text) {
  const normalized = String(text || "").replace(/\s+/g, " ").trim();
  if (!normalized) return "";

  const limit = 54;
  if (normalized.length <= limit) {
    return normalized;
  }

  const withinLimit = normalized.slice(0, limit);
  const punctuationCut = Math.max(
    withinLimit.lastIndexOf("。"),
    withinLimit.lastIndexOf("！"),
    withinLimit.lastIndexOf("？"),
    withinLimit.lastIndexOf("；"),
    withinLimit.lastIndexOf("."),
    withinLimit.lastIndexOf("!"),
    withinLimit.lastIndexOf("?"),
    withinLimit.lastIndexOf(";")
  );

  if (punctuationCut >= 16) {
    return withinLimit.slice(0, punctuationCut + 1).trim();
  }

  return `${withinLimit.slice(0, limit - 1).trim()}…`;
}

function normalizedText(value) {
  return String(value || "").toLowerCase().replace(/\s+/g, " ").trim();
}

function buildKnowledgeContext(item, entries) {
  if (!item || !Array.isArray(entries) || !entries.length) {
    return null;
  }
  const source = normalizedText(item.source_domain);
  const tags = (item.tagsText || []).map((tag) => normalizedText(tag)).filter(Boolean);
  const titleText = normalizedText(item.title);
  const summaryText = normalizedText(item.short_summary || item.long_summary || item.preview_summary);
  const scored = entries
    .map((entry) => {
      const entryTitle = normalizedText(entry.title);
      const entryContent = normalizedText(entry.content);
      let score = 0;
      if (entry.item_id && entry.item_id === item.id) score += 140;
      if (source && normalizedText(entry.source_domain) === source) score += 34;
      tags.forEach((tag) => {
        if (tag && (entryTitle.includes(tag) || entryContent.includes(tag))) {
          score += 22;
        }
      });
      const titleSeed = titleText.slice(0, 12);
      if (titleSeed && (entryTitle.includes(titleSeed) || entryContent.includes(titleSeed))) {
        score += 28;
      }
      const summarySeed = summaryText.slice(0, 18);
      if (summarySeed && entryContent.includes(summarySeed)) {
        score += 16;
      }
      if (entry.is_pinned) score += 10;
      return { ...entry, score };
    })
    .filter((entry) => entry.score >= 28)
    .sort((left, right) => right.score - left.score)
    .slice(0, 2);

  if (!scored.length) {
    return null;
  }

  const [primaryEntry, ...restEntries] = scored;
  return {
    count: scored.length,
    moreCount: restEntries.length,
    primary: {
      id: primaryEntry.id,
      title: primaryEntry.title,
      collection_name: primaryEntry.collection_name || "",
      is_pinned: !!primaryEntry.is_pinned
    }
  };
}

function buildLatestRunContext(agentStatus, items, i18n) {
  if (!agentStatus) {
    return null;
  }

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
      source_domain: item.source_domain,
      preview_summary: item.preview_summary || buildPreviewSummary(item.short_summary || item.long_summary)
    }));
  const running = !!(agentStatus.running || agentStatus.run_once_running);
  const updatedAt = formatTime(agentStatus.last_cycle_at);
  const hasData =
    running ||
    submitted > 0 ||
    submittedNew > 0 ||
    deduplicatedExisting > 0 ||
    newItems.length > 0 ||
    !!agentStatus.last_cycle_at;

  if (!hasData) {
    return null;
  }

  const metaLine = running
    ? i18n.latestRunRunning
    : updatedAt
      ? `${i18n.latestRunUpdated} ${updatedAt}`
      : i18n.latestRunEmpty;

  return {
    running,
    submitted,
    submittedNew,
    deduplicatedExisting,
    metaLine,
    emptyText: i18n.latestRunEmpty,
    newItems
  };
}

function resolveApiUrl(path) {
  const app = getApp();
  const base = ((app && app.globalData && app.globalData.apiBaseUrl) || "http://127.0.0.1:8000")
    .replace(/\/+$/, "");
  if (!path) return "";
  if (/^https?:\/\//i.test(path)) return path;
  return `${base}${String(path).startsWith("/") ? "" : "/"}${path}`;
}

Page({
  data: {
    items: [],
    currentIndex: 0,
    currentItem: null,
    nextItem: null,
    currentFeedback: { liked: false, ignored: false, saved: false },
    mode: "normal",
    focusGoalText: "",
    loading: true,
    loadError: false,
    apiMessage: "",
    feedbackState: {},
    prefClass: "",
    settingsLabel: "设置",
    i18n: {},
    cardStyle: buildCardStyle(0, 0, 0, 1, true),
    swipeDirection: "",
    swipeHint: "",
    swipeSubHint: "",
    swipeStrength: 0,
    gestureStartX: 0,
    gestureStartY: 0,
    gestureDeltaX: 0,
    gestureActive: false,
    deckLocked: false,
    latestRun: null,
    dailyBrief: null,
    dailyBriefLoading: false,
    dailyBriefError: "",
    dailyBriefPlaying: false,
    knowledgeEntries: [],
    currentKnowledgeContext: null
  },

  onLoad() {
    trackEvent("page_view", { page: "feed" });
    this.applyPreferences();
    this.tryFlushQueue();
    this.syncFeedContext();
    this.loadDailyBrief();
    this.loadKnowledgeEntries();
    this.loadItems();
  },

  onShow() {
    this.applyPreferences();
    this.tryFlushQueue();
    this.syncFeedContext();
    this.loadDailyBrief();
    this.loadKnowledgeEntries();
    if (!this.data.loading) {
      this.loadItems();
    }
  },

  onHide() {
    this.stopDailyBriefAudio();
  },

  onUnload() {
    this.stopDailyBriefAudio();
  },

  applyPreferences() {
    const app = getApp();
    const preferences = app.globalData.preferences;
    const language = preferences.language;
    const i18n = {
      kicker: t(language, "feed.kicker", "信息流"),
      title: t(language, "feed.title", "今日重点"),
      subtitle: t(
        language,
        "feed.subtitle",
        "左滑快速忽略，右滑标记感兴趣稍后再读，让系统逐步记住你的真实偏好。"
      ),
      processed: t(language, "feed.processed", "已处理"),
      latestRunKicker: t(language, "feed.latestRunKicker", "本轮采集"),
      latestRunTitle: t(language, "feed.latestRunTitle", "最新公众号刷新"),
      latestRunUpdated: t(language, "feed.latestRunUpdated", "更新于"),
      latestRunRunning: t(language, "feed.latestRunRunning", "正在采集中"),
      latestRunEmpty: t(language, "feed.latestRunEmpty", "这轮还没有新的可读文章进入摘要流。"),
      latestRunOpenInbox: t(language, "feed.latestRunOpenInbox", "查看解决方案智囊"),
      latestRunSubmitted: t(language, "feed.latestRunSubmitted", "入流"),
      latestRunNew: t(language, "feed.latestRunNew", "真正新增"),
      latestRunDedup: t(language, "feed.latestRunDedup", "历史去重"),
      latestRunPreview: t(language, "feed.latestRunPreview", "本轮新增预览"),
      dailyBriefKicker: t(language, "feed.dailyBriefKicker", "Daily Brief"),
      dailyBriefTitle: t(language, "feed.dailyBriefTitle", "今天先看这些"),
      dailyBriefRefresh: t(language, "feed.dailyBriefRefresh", "刷新简报"),
      dailyBriefOpenResearch: t(language, "feed.dailyBriefOpenResearch", "查看 Research"),
      dailyBriefPlay: t(language, "feed.dailyBriefPlay", "播放语音"),
      dailyBriefPause: t(language, "feed.dailyBriefPause", "暂停语音"),
      dailyBriefTopItems: t(language, "feed.dailyBriefTopItems", "重点内容"),
      dailyBriefWatchlist: t(language, "feed.dailyBriefWatchlist", "Watchlist 变化"),
      dailyBriefUnavailable: t(language, "feed.dailyBriefUnavailable", "当前暂无可播放音频"),
      dailyBriefError: t(language, "feed.dailyBriefError", "今日简报加载失败，请稍后重试"),
      currentCard: t(language, "feed.currentCard", "当前卡片"),
      mode: t(language, "feed.mode", "模式"),
      modeNormal: t(language, "mode.normal", "普通"),
      modeFocus: t(language, "mode.focus", "专注"),
      configureFocus: t(language, "feed.configureFocus", "设置专注"),
      logsReplay: t(language, "feed.logsReplay", "日志回放"),
      goal: t(language, "feed.goal", "目标"),
      goalUnset: t(language, "feed.goalUnset", "未设置，建议先到 Focus 页输入目标"),
      cardProgress: t(language, "feed.cardProgress", "卡片"),
      todayHighlight: t(language, "feed.todayHighlight", "今日重点"),
      value: t(language, "feed.value", "价值"),
      suggestedAction: t(language, "feed.suggestedAction", "建议动作"),
      whyRecommended: t(language, "feed.whyRecommended", "为什么推荐给你"),
      preferenceMatch: t(language, "feed.preferenceMatch", "偏好命中"),
      memoryNote: t(
        language,
        "feed.memoryNote",
        "每一次左滑/右滑，都会继续修正你的偏好画像。"
      ),
      swipeHint: t(
        language,
        "feed.swipeHint",
        "左滑忽略，右滑感兴趣稍后再读"
      ),
      swipeLeft: t(language, "feed.swipeLeft", "忽略这类内容"),
      swipeRight: t(language, "feed.swipeRight", "感兴趣稍后再读"),
      swipeLeftSub: t(language, "feed.swipeLeftSub", "减少同类卡片出现"),
      swipeRightSub: t(language, "feed.swipeRightSub", "增强同类推荐权重"),
      upNext: t(language, "feed.upNext", "下一张"),
      actionCollect: t(language, "action.collect_combo", "感兴趣稍后再读"),
      actionCollectDone: t(language, "action.collect_combo_done", "已加入稍后再读"),
      actionIgnore: t(language, "action.ignore", "忽略"),
      actionIgnoreDone: t(language, "action.ignore_done", "已忽略"),
      actionOpenDetail: t(language, "action.open_detail", "查看详情"),
      knowledgeLinked: t(language, "feed.knowledgeLinked", "关联知识"),
      knowledgeOpen: t(language, "feed.knowledgeOpen", "打开知识卡片"),
      knowledgeList: t(language, "feed.knowledgeList", "知识库"),
      knowledgePinned: t(language, "feed.knowledgePinned", "置顶"),
      knowledgeCollection: t(language, "feed.knowledgeCollection", "分组"),
      knowledgeHint: t(language, "feed.knowledgeHint", "当前卡片可直接复用已有知识，不必从零判断。"),
      empty: t(language, "feed.empty", "暂无内容，请先去解决方案智囊添加。"),
      emptyHint: t(language, "feed.emptyHint", "先把区域、行业或线索交给解决方案智囊，再回来做快速判断。"),
      loading: t(language, "feed.loading", "正在加载 Feed..."),
      retryLoad: t(language, "common.retryLoad", "重新加载"),
      openInboxCta: t(language, "feed.openInboxCta", "去解决方案智囊"),
      autoFlushed: t(language, "feed.autoFlushed", "已自动补发离线操作"),
      localMockMode: t(language, "common.localMockMode", "后端未连接，当前显示本地演示数据"),
      loadingFailed: t(language, "common.loadingFailed", "加载失败"),
      feedbackSynced: t(language, "common.feedbackSynced", "已同步反馈"),
      localOnly: t(language, "common.localOnly", "本地已记录，API 未连接"),
      itemsUnit: t(language, "common.items", "条"),
      untitled: t(language, "common.untitled", "未命名内容"),
      unknownSource: t(language, "common.unknownSource", "未知来源"),
      noSummary: t(language, "common.noSummary", "暂无摘要")
    };
    this.setData({
      prefClass: getPreferenceClass(preferences, app.globalData.systemTheme),
      settingsLabel: t(language, "common.settings", "设置"),
      i18n
    });
    wx.setNavigationBarTitle({
      title: t(language, "nav.feed", "首页")
    });
  },

  tryFlushQueue() {
    flushPendingQueue(10).then((result) => {
      if (result.flushed > 0) {
        this.setData({
          apiMessage: `${this.data.i18n.autoFlushed} ${result.flushed} ${this.data.i18n.itemsUnit}`
        });
      }
    });
  },

  onPullDownRefresh() {
    Promise.allSettled([this.loadItems(), this.loadKnowledgeEntries()]).finally(() => wx.stopPullDownRefresh());
  },

  syncFeedContext() {
    const app = getApp();
    const mode = app.globalData.currentFeedMode === "focus" ? "focus" : "normal";
    const focusGoalText = app.globalData.currentSessionGoal || "";
    this.setData({ mode, focusGoalText });
  },

  loadItems() {
    this.setData({ loading: true, loadError: false });
    return listItems(30, {
      mode: this.data.mode,
      goalText: this.data.focusGoalText,
      includePending: false
    })
      .then((res) => {
        const language = getApp().globalData.preferences.language;
        const previousFeedbackState = this.data.feedbackState || {};
        const items = (res.items || []).map((item) => {
          const score100 = scoreTo100(item.score_value);
          const shortSummary = item.short_summary || item.long_summary || this.data.i18n.noSummary;
          return {
            ...item,
            title: item.title || this.data.i18n.untitled,
            source_domain: item.source_domain || this.data.i18n.unknownSource,
            score100,
            cardActionLabel:
              item.action_suggestion === "deep_read"
                ? t(language, "action.deep_read", "立即深读")
                : item.action_suggestion === "later"
                  ? t(language, "action.later", "稍后精读")
                  : t(language, "action.skip", "可放心忽略"),
            tagsText: (item.tags || []).map((tag) => tag.tag_name || tag),
            short_summary: shortSummary,
            preview_summary: buildPreviewSummary(shortSummary),
            insight_seed: (item.long_summary || shortSummary).slice(0, 120),
            topic_match_score_label: Math.round(Number(item.topic_match_score || 0)),
            source_match_score_label: Math.round(Number(item.source_match_score || 0)),
            scoreTone:
              score100 >= 75 ? "score-high" : score100 >= 45 ? "score-mid" : "score-low"
          };
        });

        const feedbackState = {};
        items.forEach((item) => {
          feedbackState[item.id] = previousFeedbackState[item.id] || {
            liked: false,
            ignored: false,
            saved: false
          };
        });

        this.setData(
          {
            items,
            currentIndex: 0,
            loading: false,
            loadError: false,
            feedbackState,
            apiMessage: res.fromMock ? this.data.i18n.localMockMode : ""
          },
          () => {
            this.syncCurrent();
            this.loadLatestRun(items);
          }
        );
      })
      .catch(() => {
        this.setData({ loading: false, loadError: true, latestRun: null });
        wx.showToast({ title: this.data.i18n.loadingFailed, icon: "none" });
      });
  },

  loadLatestRun(items) {
    return getWechatAgentStatus()
      .then((status) => {
        this.setData({
          latestRun: buildLatestRunContext(status, items || this.data.items, this.data.i18n)
        });
      })
      .catch(() => {
        this.setData({ latestRun: null });
      });
  },

  loadKnowledgeEntries() {
    return listKnowledgeEntries(60)
      .then((res) => {
        this.setData({ knowledgeEntries: res.items || [] }, () => {
          if (this.data.currentItem) {
            this.syncCurrent();
          }
        });
      })
      .catch(() => {
        this.setData({ knowledgeEntries: [] });
      });
  },

  loadDailyBrief(forceRefresh = false) {
    this.setData({
      dailyBriefLoading: true,
      dailyBriefError: ""
    });
    getMobileDailyBrief(!!forceRefresh)
      .then((brief) => {
        this.setData({
          dailyBrief: brief || null,
          dailyBriefError: ""
        });
      })
      .catch(() => {
        this.setData({
          dailyBriefError: this.data.i18n.dailyBriefError
        });
      })
      .finally(() => {
        this.setData({ dailyBriefLoading: false });
      });
  },

  refreshDailyBrief() {
    this.loadDailyBrief(true);
  },

  stopDailyBriefAudio() {
    if (this._dailyBriefAudio) {
      try {
        this._dailyBriefAudio.stop();
        this._dailyBriefAudio.destroy();
      } catch (_) {
        // ignore player teardown errors
      }
      this._dailyBriefAudio = null;
    }
    this.setData({ dailyBriefPlaying: false });
  },

  toggleDailyBriefAudio() {
    const brief = this.data.dailyBrief;
    if (!brief || brief.audio_status !== "ready" || !brief.audio_url) {
      wx.showToast({
        title: this.data.i18n.dailyBriefUnavailable,
        icon: "none"
      });
      return;
    }
    if (this._dailyBriefAudio && this.data.dailyBriefPlaying) {
      this._dailyBriefAudio.pause();
      this.setData({ dailyBriefPlaying: false });
      return;
    }
    if (!this._dailyBriefAudio) {
      const audio = wx.createInnerAudioContext();
      audio.autoplay = false;
      audio.src = resolveApiUrl(brief.audio_url);
      audio.onPlay(() => this.setData({ dailyBriefPlaying: true }));
      audio.onPause(() => this.setData({ dailyBriefPlaying: false }));
      audio.onStop(() => this.setData({ dailyBriefPlaying: false }));
      audio.onEnded(() => this.setData({ dailyBriefPlaying: false }));
      this._dailyBriefAudio = audio;
    } else {
      this._dailyBriefAudio.src = resolveApiUrl(brief.audio_url);
    }
    this._dailyBriefAudio.play();
  },

  openDailyBriefItem(e) {
    const itemId = e.currentTarget.dataset.id;
    if (!itemId) return;
    wx.navigateTo({
      url: `/pages/item/index?id=${itemId}`
    });
  },

  openResearchCenter() {
    wx.navigateTo({
      url: "/pages/research/index"
    });
  },

  switchMode(e) {
    const mode = e.currentTarget.dataset.mode === "focus" ? "focus" : "normal";
    const app = getApp();
    app.globalData.currentFeedMode = mode;
    this.setData({ mode });
    trackEvent("feed_mode_switch", { mode });
    this.loadItems();
  },

  syncCurrent() {
    const currentItem = this.data.items[this.data.currentIndex] || null;
    const nextItem = this.data.items[this.data.currentIndex + 1] || null;
    const currentFeedback = currentItem
      ? this.data.feedbackState[currentItem.id] || { liked: false, ignored: false, saved: false }
      : { liked: false, ignored: false, saved: false };
    const currentKnowledgeContext = currentItem
      ? buildKnowledgeContext(currentItem, this.data.knowledgeEntries || [])
      : null;
    this.setData({
      currentItem,
      nextItem,
      currentKnowledgeContext,
      currentFeedback,
      cardStyle: buildCardStyle(0, 0, 0, 1, true),
      swipeDirection: "",
      swipeHint: "",
      swipeSubHint: "",
      swipeStrength: 0,
      gestureDeltaX: 0,
      gestureActive: false,
      deckLocked: false
    });
  },

  getCurrentItem() {
    return this.data.items[this.data.currentIndex] || null;
  },

  updateCardMotion(deltaX) {
    const clampedX = clamp(deltaX, -SWIPE_MAX, SWIPE_MAX);
    const ratio = Math.min(Math.abs(clampedX) / SWIPE_MAX, 1);
    const direction = clampedX <= -36 ? "ignore" : clampedX >= 36 ? "like" : "";
    const rotateDeg = clampedX / 18;
    const offsetY = Math.abs(clampedX) * 0.04;
    const hint = direction === "ignore"
      ? this.data.i18n.swipeLeft
      : direction === "like"
        ? this.data.i18n.swipeRight
        : this.data.i18n.swipeHint;
    const subHint = direction === "ignore"
      ? this.data.i18n.swipeLeftSub
      : direction === "like"
        ? this.data.i18n.swipeRightSub
        : "";
    this.setData({
      gestureDeltaX: clampedX,
      swipeDirection: direction,
      swipeHint: hint,
      swipeSubHint: subHint,
      swipeStrength: ratio,
      cardStyle: buildCardStyle(clampedX, offsetY, rotateDeg, 1, false)
    });
  },

  handleTouchStart(e) {
    if (this.data.deckLocked || !this.data.currentItem) return;
    const touch = e.touches && e.touches[0];
    if (!touch) return;
    this.setData({
      gestureStartX: touch.pageX,
      gestureStartY: touch.pageY,
      gestureActive: true
    });
  },

  handleTouchMove(e) {
    if (!this.data.gestureActive || this.data.deckLocked || !this.data.currentItem) return;
    const touch = e.touches && e.touches[0];
    if (!touch) return;
    const deltaX = touch.pageX - this.data.gestureStartX;
    const deltaY = touch.pageY - this.data.gestureStartY;
    if (Math.abs(deltaY) > Math.abs(deltaX) + 20) return;
    this.updateCardMotion(deltaX);
  },

  handleTouchEnd() {
    if (!this.data.gestureActive || this.data.deckLocked || !this.data.currentItem) return;
    const deltaX = this.data.gestureDeltaX;
    this.setData({ gestureActive: false });
    if (deltaX <= -SWIPE_THRESHOLD) {
      this.commitDecision("ignore");
      return;
    }
    if (deltaX >= SWIPE_THRESHOLD) {
      this.commitDecision("like");
      return;
    }
    this.setData({
      swipeDirection: "",
      swipeHint: this.data.i18n.swipeHint,
      swipeSubHint: "",
      swipeStrength: 0,
      cardStyle: buildCardStyle(0, 0, 0, 1, true)
    });
  },

  commitDecision(direction) {
    const item = this.getCurrentItem();
    if (!item || this.data.deckLocked) return;

    const flyX = direction === "ignore" ? -860 : 860;
    const rotateDeg = direction === "ignore" ? -18 : 18;
    this.setData({
      deckLocked: true,
      swipeDirection: direction,
      swipeHint: direction === "ignore" ? this.data.i18n.swipeLeft : this.data.i18n.swipeRight,
      swipeSubHint: direction === "ignore" ? this.data.i18n.swipeLeftSub : this.data.i18n.swipeRightSub,
      cardStyle: buildCardStyle(flyX, 24, rotateDeg, 0, true)
    });

    const nextFeedback = {
      liked: direction === "like",
      ignored: direction === "ignore",
      saved: direction === "like"
    };
    const feedbackState = {
      ...this.data.feedbackState,
      [item.id]: nextFeedback
    };
    this.setData({
      feedbackState,
      currentFeedback: nextFeedback
    });

    if (direction === "ignore") {
      this.sendFeedback("ignore");
      trackEvent("feed_swipe", { action: "ignore", item_id: item.id });
      this.setData({ apiMessage: this.data.i18n.actionIgnoreDone });
    } else {
      this.sendFeedback("like");
      this.sendFeedback("save");
      trackEvent("feed_swipe", { action: "like_read_later", item_id: item.id });
      this.setData({ apiMessage: this.data.i18n.actionCollectDone });
    }

    setTimeout(() => {
      const nextItems = this.data.items.filter((entry, index) => index !== this.data.currentIndex);
      if (!nextItems.length) {
        this.setData({
          items: [],
          currentIndex: 0,
          currentItem: null,
          nextItem: null,
          deckLocked: false,
          cardStyle: buildCardStyle(0, 0, 0, 1, true)
        });
        return;
      }
      const nextIndex = Math.min(this.data.currentIndex, nextItems.length - 1);
      this.setData(
        {
          items: nextItems,
          currentIndex: nextIndex
        },
        () => {
          this.syncCurrent();
        }
      );
    }, 260);
  },

  sendFeedback(feedbackType) {
    const item = this.getCurrentItem();
    if (!item) return;
    submitFeedback(item.id, feedbackType)
      .then(() => {
        this.setData({ apiMessage: `${this.data.i18n.feedbackSynced}：${feedbackType}` });
      })
      .catch(() => {
        this.setData({ apiMessage: this.data.i18n.localOnly });
      });
  },

  tapIgnoreAction() {
    const item = this.getCurrentItem();
    if (!item) return;
    this.commitDecision("ignore");
  },

  tapLikeAction() {
    const item = this.getCurrentItem();
    if (!item) return;
    this.commitDecision("like");
  },

  openDetail() {
    const item = this.getCurrentItem();
    if (!item) return;
    this.sendFeedback("open_detail");
    trackEvent("feed_action", { action: "open_detail", item_id: item.id });
    wx.navigateTo({
      url: `/pages/item/index?id=${item.id}`
    });
  },

  openKnowledgeList() {
    wx.navigateTo({
      url: "/pages/knowledge/index"
    });
  },

  openKnowledgeEntry(e) {
    const entryId = e.currentTarget.dataset.id;
    if (!entryId) return;
    wx.navigateTo({
      url: `/pages/knowledge/index?id=${entryId}`
    });
  },

  openInbox() {
    wx.switchTab({
      url: "/pages/inbox/index"
    });
  },

  reloadFeed() {
    this.loadItems();
  }
});
