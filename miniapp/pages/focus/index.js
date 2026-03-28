const {
  createFocusAssistantPlan,
  executeFocusAssistantAction,
  getSession,
  getWechatAgentConfig,
  getWechatAgentBatchStatus,
  getWechatAgentStatus,
  listKnowledgeEntries,
  runWechatAgentBatch,
  runWechatAgentOnce,
  startSession,
  finishSession,
  startWechatAgent,
  stopWechatAgent,
  updateWechatAgentConfig
} = require("../../utils/api");
const { formatCountdown } = require("../../utils/format");
const { trackEvent } = require("../../utils/analytics");
const { t } = require("../../utils/i18n");
const { getPreferenceClass } = require("../../utils/preferences");
const {
  buildLatestFocusAssistantResult,
  appendFocusAssistantResult
} = require("../../utils/focus-assistant-storage");

function hasBatchSnapshot(status) {
  if (!status) return false;
  return !!(
    status.total_segments ||
    status.finished_at ||
    status.running ||
    status.submitted ||
    status.submitted_new ||
    status.deduplicated_existing ||
    status.skipped_seen ||
    status.failed
  );
}

function buildBatchStatusView(status, i18n) {
  if (!hasBatchSnapshot(status)) {
    return {
      visible: false,
      running: false,
      progress: 0,
      title: "",
      summary: "",
      lastMessage: "",
      lastError: "",
    metrics: {
      submittedNew: 0,
      submittedUrl: 0,
      submittedUrlDirect: 0,
      submittedUrlShareCopy: 0,
      submittedUrlResolved: 0,
      submittedOcr: 0,
      deduplicatedExisting: 0,
      skippedSeen: 0,
        failed: 0
      }
    };
  }

  const totalSegments = Math.max(Number(status.total_segments || 0), 0);
  const currentSegment = Math.max(Number(status.current_segment_index || 0), status.running ? 1 : 0);
  const progress = totalSegments
    ? status.running
      ? Math.max(8, Math.min(96, Math.round((currentSegment / totalSegments) * 100)))
      : status.finished_at
        ? 100
        : 0
    : 0;

  const submittedUrl = Math.max(Number(status.submitted_url || 0), Number(status.live_report_submitted_url || 0));
  const submittedUrlDirect = Math.max(
    Number(status.submitted_url_direct || 0),
    Number(status.live_report_submitted_url_direct || 0)
  );
  const submittedUrlShareCopy = Math.max(
    Number(status.submitted_url_share_copy || 0),
    Number(status.live_report_submitted_url_share_copy || 0)
  );
  const submittedUrlResolved = Math.max(
    Number(status.submitted_url_resolved || 0),
    Number(status.live_report_submitted_url_resolved || 0)
  );
  const submittedOcr = Math.max(Number(status.submitted_ocr || 0), Number(status.live_report_submitted_ocr || 0));
  return {
    visible: true,
    running: !!status.running,
    progress,
    title: status.running
      ? i18n.collectorRunning
      : i18n.collectorLatest,
    summary: status.running
      ? `第 ${Math.max(currentSegment, 1)}/${Math.max(totalSegments, 1)} 段 · ${i18n.collectorSubmitted} ${Number(status.submitted || 0)} ${i18n.itemsUnit}`
      : `第 ${totalSegments} ${i18n.collectorSegments} · ${i18n.collectorSubmitted} ${Number(status.submitted || 0)} ${i18n.itemsUnit}`,
    lastMessage: status.last_message || "",
    lastError: status.last_error || "",
    metrics: {
      submittedNew: Number(status.submitted_new || 0),
      submittedUrl,
      submittedUrlDirect,
      submittedUrlShareCopy,
      submittedUrlResolved,
      submittedOcr,
      deduplicatedExisting: Number(status.deduplicated_existing || 0),
      skippedSeen: Number(status.skipped_seen || 0),
      failed: Number(status.failed || 0)
    }
  };
}

function normalizeTotalSeconds(value, fallback) {
  return Math.max(60, Number(value || fallback || 25) * 60);
}

function computeRemainingSeconds(endAtMs, totalSeconds) {
  if (!Number.isFinite(endAtMs) || !Number.isFinite(totalSeconds) || totalSeconds <= 0) {
    return 0;
  }
  return Math.max(0, Math.min(totalSeconds, Math.ceil((endAtMs - Date.now()) / 1000)));
}

function computeProgressPercent(totalSeconds, remainingSeconds) {
  if (!Number.isFinite(totalSeconds) || totalSeconds <= 0) {
    return 0;
  }
  return Math.max(
    0,
    Math.min(100, Math.floor(((totalSeconds - Math.max(0, remainingSeconds)) / totalSeconds) * 100))
  );
}

function parseServerUtcDate(value) {
  const text = String(value || "").trim();
  if (!text) return NaN;
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/i.test(text) ? text : `${text}Z`;
  return Date.parse(normalized);
}

Page({
  data: {
    duration: 25,
    goalText: "",
    secondsLeft: 1500,
    running: false,
    sessionId: "",
    sessionClosed: false,
    sessionMessage: "",
    startingSession: false,
    focusOwnsWechatAgent: false,
    muteIncoming: true,
    summaryAfter: true,
    generateTodo: true,
    newItemsCount: 0,
    referenceEntries: [],
    assistantPlan: null,
    assistantLoading: false,
    assistantExecutingKey: "",
    assistantMessage: "",
    assistantOutputPreview: "",
    strategyCount: 3,
    countdownText: "25:00",
    progressPercent: 0,
    collectorBatchStatus: null,
    collectorBatchView: {
      visible: false,
      running: false,
      progress: 0,
      title: "",
      summary: "",
      lastMessage: "",
      lastError: "",
      metrics: {
        submittedNew: 0,
        submittedUrl: 0,
        submittedOcr: 0,
        deduplicatedExisting: 0,
        skippedSeen: 0,
        failed: 0
      }
    },
    prefClass: "",
    settingsLabel: "设置",
    i18n: {}
  },

  getSelectedDurationMinutes(fallback) {
    const candidate = Number(this._selectedDurationMinutes || fallback || this.data.duration || 25);
    return candidate >= 50 ? 50 : 25;
  },

  setSelectedDurationMinutes(duration) {
    const normalized = Number(duration) >= 50 ? 50 : 25;
    this._selectedDurationMinutes = normalized;
    return normalized;
  },

  clearFocusWechatOwnership() {
    const app = getApp();
    app.globalData.focusOwnsWechatAgent = false;
    this.setData({ focusOwnsWechatAgent: false });
    this._startLoopAfterBatch = false;
  },

  onLoad() {
    this.setSelectedDurationMinutes(this.data.duration);
    this._pausedByUser = false;
    trackEvent("page_view", { page: "focus" });
    this.applyPreferences();
    this.loadKnowledgeReferences();
    this.setData({
      countdownText: formatCountdown(this.data.secondsLeft)
    });
    this.restoreActiveSession();
    this.refreshBatchStatus();
  },

  onShow() {
    this.applyPreferences();
    this.loadKnowledgeReferences();
    this.restoreActiveSession();
    this.refreshBatchStatus();
    this.startSessionPolling();
  },

  onHide() {
    this.stopSessionPolling();
  },

  onUnload() {
    this.stopTimer();
    this.stopSessionPolling();
  },

  getCountdownTotalSeconds(totalSecondsOverride) {
    if (Number.isFinite(totalSecondsOverride) && totalSecondsOverride > 0) {
      return Math.max(60, Math.floor(totalSecondsOverride));
    }
    if (Number.isFinite(this._countdownTotalSeconds) && this._countdownTotalSeconds > 0) {
      return Math.max(60, Math.floor(this._countdownTotalSeconds));
    }
    return normalizeTotalSeconds(this.getSelectedDurationMinutes());
  },

  getRemainingSecondsFromRuntime(totalSecondsOverride) {
    const totalSeconds = this.getCountdownTotalSeconds(totalSecondsOverride);
    if (Number.isFinite(this._countdownEndAtMs) && this._countdownEndAtMs > 0) {
      return computeRemainingSeconds(this._countdownEndAtMs, totalSeconds);
    }
    return Math.max(0, Math.min(totalSeconds, Math.floor(Number(this.data.secondsLeft || 0))));
  },

  syncCountdownState(remainingSeconds, totalSecondsOverride) {
    const totalSeconds = this.getCountdownTotalSeconds(totalSecondsOverride);
    const nextRemaining = Math.max(0, Math.min(totalSeconds, Math.floor(Number(remainingSeconds || 0))));
    const nextProgress = computeProgressPercent(totalSeconds, nextRemaining);
    this.setData({
      secondsLeft: nextRemaining,
      countdownText: formatCountdown(nextRemaining),
      progressPercent: nextProgress
    });
  },

  setCountdownRuntime(totalSeconds, endAtMs) {
    this._countdownTotalSeconds = this.getCountdownTotalSeconds(totalSeconds);
    this._countdownEndAtMs = Number.isFinite(endAtMs) ? endAtMs : null;
  },

  clearCountdownRuntime() {
    this._countdownTotalSeconds = null;
    this._countdownEndAtMs = null;
  },

  applyPreferences() {
    const app = getApp();
    const preferences = app.globalData.preferences;
    const language = preferences.language;
    const i18n = {
      kicker: t(language, "focus.kicker", "Focus Flight Deck"),
      title: t(language, "focus.title", "深度专注模式"),
      subtitle: t(language, "focus.subtitle", "开启一个稳定工作窗口，信息延后回流，不打断主任务。"),
      setupTitle: t(language, "focus.setupTitle", "专注设置"),
      setupHint: t(language, "focus.setupHint", "先设定目标和策略，再进入一个不被打断的工作窗口。"),
      overviewDuration: t(language, "focus.overviewDuration", "时长"),
      overviewReferences: t(language, "focus.overviewReferences", "参考卡"),
      overviewStrategies: t(language, "focus.overviewStrategies", "已启用策略"),
      duration: t(language, "focus.duration", "时长选择"),
      goal: t(language, "focus.goal", "本次目标"),
      goalPlaceholder: t(language, "focus.goalPlaceholder", "例如：整理 AI 行业求职材料"),
      goalUnset: t(language, "focus.goalUnset", "未设置目标"),
      strategy: t(language, "focus.strategy", "专注策略"),
      strategyMute: t(language, "focus.strategy.mute", "新内容暂不打断"),
      strategySummary: t(language, "focus.strategy.summary", "结束后统一汇总"),
      strategyTodo: t(language, "focus.strategy.todo", "生成待办建议"),
      referenceTitle: t(language, "focus.referenceTitle", "本轮参考卡"),
      referenceSubtitle: t(language, "focus.referenceSubtitle", "把明确加入 Focus 参考的卡片放在视线边缘，辅助判断但不打断专注。"),
      referenceEmpty: t(language, "focus.referenceEmpty", "还没有 Focus 参考卡片，可以去知识库批量加入。"),
      referenceOpen: t(language, "focus.referenceOpen", "打开"),
      referenceList: t(language, "focus.referenceList", "知识库"),
      countdown: t(language, "focus.countdown", "倒计时"),
      progress: t(language, "focus.progress", "进度"),
      stateRunning: t(language, "focus.state.running", "专注进行中"),
      stateDone: t(language, "focus.state.done", "本轮已完成"),
      stateReady: t(language, "focus.state.ready", "准备开始"),
      newItems: t(language, "focus.newItems", "本次新增内容"),
      start: t(language, "focus.start", "开始"),
      pause: t(language, "focus.pause", "暂停"),
      finishEarly: t(language, "focus.finishEarly", "提前结束"),
      reset: t(language, "focus.reset", "重置"),
      openSummary: t(language, "focus.openSummary", "查看 Session Summary"),
      assistantTitle: t(language, "focus.assistant.title", "Focus Assistant"),
      assistantSubtitle: t(language, "focus.assistant.subtitle", "先生成安全动作计划，再确认是否通过 WorkBuddy 或直连通道执行。"),
      assistantBuild: t(language, "focus.assistant.build", "生成计划"),
      assistantExecuting: t(language, "focus.assistant.executing", "执行中..."),
      assistantToWorkBuddy: t(language, "focus.assistant.toWorkBuddy", "交给 WorkBuddy"),
      assistantDirect: t(language, "focus.assistant.direct", "直接执行"),
      assistantBlocked: t(language, "focus.assistant.blocked", "当前不支持的高风险动作"),
      assistantPlanFailed: t(language, "focus.assistant.planFailed", "生成 Assistant 计划失败，请稍后重试。"),
      assistantExecuteFailed: t(language, "focus.assistant.executeFailed", "执行失败，请稍后重试。"),
      autoCollectEnabled: t(language, "focus.autoCollectEnabled", "已自动接入公众号采集，新文章会静默进入解析队列。"),
      autoCollectReady: t(language, "focus.autoCollectReady", "公众号采集已接入本轮专注。"),
      autoCollectFailed: t(language, "focus.autoCollectFailed", "专注已开始，但公众号自动采集启动失败，可去采集器页检查。"),
      collectorKicker: t(language, "focus.collectorKicker", "公众号采集"),
      collectorRunning: t(language, "focus.collectorRunning", "正在静默扫描最新文章"),
      collectorLatest: t(language, "focus.collectorLatest", "最近一轮采集结果"),
      collectorSubmitted: t(language, "focus.collectorSubmitted", "累计入队"),
      collectorSubmittedNew: t(language, "focus.collectorSubmittedNew", "真正新增"),
      collectorSubmittedUrl: t(language, "focus.collectorSubmittedUrl", "链接入队"),
      collectorUrlDirect: t(language, "focus.collectorUrlDirect", "直接真链"),
      collectorUrlShareCopy: t(language, "focus.collectorUrlShareCopy", "分享取链"),
      collectorUrlResolved: t(language, "focus.collectorUrlResolved", "真链恢复"),
      collectorSubmittedOcr: t(language, "focus.collectorSubmittedOcr", "OCR兜底"),
      collectorDedup: t(language, "focus.collectorDedup", "历史去重"),
      collectorSeen: t(language, "focus.collectorSeen", "已跳过"),
      collectorFailed: t(language, "focus.collectorFailed", "失败"),
      collectorLastMessage: t(language, "focus.collectorLastMessage", "状态"),
      collectorLastError: t(language, "focus.collectorLastError", "最近错误"),
      collectorSegments: t(language, "focus.collectorSegments", "段"),
      modeNormal: t(language, "mode.normal", "Normal"),
      modeFocus: t(language, "mode.focus", "Focus"),
      itemsUnit: t(language, "common.items", "条"),
      minutes: t(language, "common.minutes", "分钟"),
      starting: t(language, "focus.starting", "启动中..."),
      sessionStarted: t(language, "focus.sessionStarted", "Focus Session 已启动。"),
      sessionLocal: t(language, "focus.sessionLocal", "后端未连接，当前以本地计时模式运行。"),
      sessionFinished: t(language, "focus.sessionFinished", "本轮 Focus Session 已结束并生成回流摘要。"),
      sessionFinishFallback: t(language, "focus.sessionFinishFallback", "本轮已结束，待后端可用时可补发 finish。")
    };
    this.setData({
      prefClass: getPreferenceClass(preferences, app.globalData.systemTheme),
      settingsLabel: t(language, "common.settings", "设置"),
      i18n,
      collectorBatchView: buildBatchStatusView(this.data.collectorBatchStatus, i18n)
    });
    wx.setNavigationBarTitle({
      title: t(language, "nav.focus", "Focus")
    });
  },

  chooseDuration(e) {
    if (this.data.running || (this.data.sessionId && !this.data.sessionClosed)) {
      return;
    }
    const duration = this.setSelectedDurationMinutes(Number(e.currentTarget.dataset.duration || 25));
    const total = duration * 60;
    if (!this.data.running) {
      this.clearCountdownRuntime();
      this._countdownTotalSeconds = total;
    }
    this.setData({
      duration,
      secondsLeft: this.data.running ? this.data.secondsLeft : total,
      countdownText: this.data.running ? this.data.countdownText : formatCountdown(total),
      progressPercent: this.data.running ? this.data.progressPercent : 0
    });
    trackEvent("focus_duration_change", { duration });
  },

  onGoalInput(e) {
    this.setData({ goalText: e.detail.value });
  },

  onToggleMute(e) {
    this.setData({ muteIncoming: !!e.detail.value }, () => this.syncStrategyCount());
  },

  onToggleSummary(e) {
    this.setData({ summaryAfter: !!e.detail.value }, () => this.syncStrategyCount());
  },

  onToggleTodo(e) {
    this.setData({ generateTodo: !!e.detail.value }, () => this.syncStrategyCount());
  },

  syncStrategyCount() {
    const count = [this.data.muteIncoming, this.data.summaryAfter, this.data.generateTodo].filter(Boolean).length;
    this.setData({ strategyCount: count });
  },

  loadKnowledgeReferences() {
    return listKnowledgeEntries(40, { focusReferenceOnly: true })
      .then((res) => {
        const explicit = (res.items || []).slice(0, 4);
        if (explicit.length) {
          this.setData({ referenceEntries: explicit });
          return;
        }
        return listKnowledgeEntries(40).then((fallback) => {
          const items = (fallback.items || []).filter((entry) => entry.is_pinned).slice(0, 3);
          this.setData({ referenceEntries: items });
        });
      })
      .catch(() => {
        this.setData({ referenceEntries: [] });
      });
  },

  startSessionPolling() {
    this.stopSessionPolling();
    const sessionId = this.data.sessionId || getApp().globalData.currentSessionId;
    if (!sessionId || this.data.sessionClosed) {
      return;
    }
    this._sessionPoller = setInterval(() => {
      this.refreshSessionSnapshot();
      this.refreshBatchStatus();
    }, 8000);
  },

  stopSessionPolling() {
    if (this._sessionPoller) {
      clearInterval(this._sessionPoller);
      this._sessionPoller = null;
    }
  },

  restoreActiveSession() {
    const app = getApp();
    const sessionId = app.globalData.currentSessionId || this.data.sessionId;
    if (!sessionId) {
      return Promise.resolve();
    }
    return this.refreshSessionSnapshot(sessionId);
  },

  refreshSessionSnapshot(sessionIdOverride) {
    const app = getApp();
    const sessionId = sessionIdOverride || this.data.sessionId || app.globalData.currentSessionId;
    if (!sessionId) {
      return Promise.resolve();
    }
    return getSession(sessionId)
      .then((session) => {
        const hasLocalRuntime =
          Number.isFinite(this._countdownEndAtMs) &&
          this._countdownEndAtMs > 0 &&
          (this.data.running || (this.data.secondsLeft > 0 && !this.data.sessionClosed));
        if (session && session._fromMock && hasLocalRuntime) {
          const localDuration = this.getSelectedDurationMinutes(app.globalData.currentSessionDuration);
          const totalSeconds = normalizeTotalSeconds(localDuration);
          const remaining = this.getRemainingSecondsFromRuntime(totalSeconds);
          const progressPercent = computeProgressPercent(totalSeconds, remaining);
          this.setData({
            sessionId,
            goalText: app.globalData.currentSessionGoal || this.data.goalText,
            duration: localDuration,
            sessionClosed: false,
            focusOwnsWechatAgent: !!app.globalData.focusOwnsWechatAgent,
            newItemsCount: Number((session.metrics && session.metrics.new_content_count) || this.data.newItemsCount || 0),
            secondsLeft: remaining,
            countdownText: formatCountdown(remaining),
            progressPercent,
            running: remaining > 0
          });
          return;
        }

        const resolvedDuration = this.setSelectedDurationMinutes(
          Number(session.duration_minutes || this.getSelectedDurationMinutes())
        );
        const totalSeconds = normalizeTotalSeconds(resolvedDuration);
        const startMs = parseServerUtcDate(session.start_time || "");
        const isRunning = session.status === "running";
        const endAtMs = isRunning && !Number.isNaN(startMs)
          ? startMs + totalSeconds * 1000
          : null;
        const remaining = isRunning && endAtMs
          ? computeRemainingSeconds(endAtMs, totalSeconds)
          : this.getRemainingSecondsFromRuntime(totalSeconds);
        const progressPercent = isRunning
          ? computeProgressPercent(totalSeconds, remaining)
          : 100;

        app.globalData.currentSessionId = session.id || sessionId;
        app.globalData.currentSessionGoal = session.goal_text || "";
        app.globalData.currentSessionDuration = resolvedDuration;
        app.globalData.currentFeedMode = isRunning ? "focus" : app.globalData.currentFeedMode;

        if (this._pausedByUser && isRunning) {
          this.setData({
            sessionId: session.id || sessionId,
            goalText: session.goal_text || this.data.goalText,
            duration: resolvedDuration,
            sessionClosed: false,
            focusOwnsWechatAgent: !!app.globalData.focusOwnsWechatAgent,
            newItemsCount: Number((session.metrics && session.metrics.new_content_count) || 0)
          });
          return;
        }

        if (isRunning && endAtMs) {
          this.setCountdownRuntime(totalSeconds, endAtMs);
        }

        this.setData({
          sessionId: session.id || sessionId,
          goalText: session.goal_text || this.data.goalText,
          duration: resolvedDuration,
          sessionClosed: !isRunning,
          focusOwnsWechatAgent: !!app.globalData.focusOwnsWechatAgent,
          newItemsCount: Number((session.metrics && session.metrics.new_content_count) || 0),
          secondsLeft: isRunning ? remaining : 0,
          countdownText: isRunning ? formatCountdown(remaining) : "00:00",
          progressPercent: isRunning ? progressPercent : 100,
          running: isRunning && remaining > 0
        });

        if (isRunning && remaining > 0) {
          if (!this._timer) {
            this.startTimer(totalSeconds, remaining, endAtMs);
          } else {
            this.syncCountdownState(remaining, totalSeconds);
          }
        }
        if (!isRunning) {
          this._pausedByUser = false;
          app.globalData.currentFeedMode = "normal";
          this.clearFocusWechatOwnership();
          this.stopTimer();
          this.clearCountdownRuntime();
          this.stopSessionPolling();
        }
      })
      .catch(() => Promise.resolve());
  },

  refreshBatchStatus() {
    return getWechatAgentBatchStatus()
      .then((status) => {
        this.setData({
          collectorBatchStatus: status,
          collectorBatchView: buildBatchStatusView(status, this.data.i18n || {})
        });
        if (this._startLoopAfterBatch && status && !status.running) {
          this._startLoopAfterBatch = false;
          return this.startFocusLoopAgent();
        }
        return null;
      })
      .catch(() => Promise.resolve());
  },

  startFocusLoopAgent() {
    return startWechatAgent()
      .then(() => {
        this.setData({
          sessionMessage: this.data.i18n.autoCollectEnabled
        });
      })
      .catch(() => {
        this.setData({
          sessionMessage: this.data.i18n.autoCollectFailed
        });
      });
  },

  enableFocusCollection() {
    const app = getApp();
    const language = app.globalData.preferences.language;
    return getWechatAgentStatus()
      .catch(() => ({ running: false }))
      .then((status) => {
        const alreadyRunning = !!(status && status.running);
        if (alreadyRunning) {
          app.globalData.focusOwnsWechatAgent = false;
          this.setData({
            focusOwnsWechatAgent: false,
            sessionMessage: this.data.i18n.autoCollectReady
          });
          return this.refreshBatchStatus();
        }

        app.globalData.focusOwnsWechatAgent = true;
        this.setData({ focusOwnsWechatAgent: true });
        return getWechatAgentConfig()
          .catch(() => null)
          .then((config) => {
            const previousInterval = Number(config && config.loop_interval_sec);
            this._focusPreviousLoopInterval = Number.isFinite(previousInterval) ? previousInterval : null;
            if (this._focusPreviousLoopInterval && this._focusPreviousLoopInterval > 90) {
              return updateWechatAgentConfig({ loop_interval_sec: 90 }).catch(() => null);
            }
            return null;
          })
          .then(() =>
            runWechatAgentBatch({
              output_language: language,
              total_items: 12,
              segment_items: 6
            })
          )
          .then((res) => {
            const batchStatus = res.batch_status || null;
            if (batchStatus) {
              this.setData({
                collectorBatchStatus: batchStatus,
                collectorBatchView: buildBatchStatusView(batchStatus, this.data.i18n || {})
              });
            }
            if (res && res.ok) {
              this._startLoopAfterBatch = true;
              this.setData({
                sessionMessage: this.data.i18n.autoCollectEnabled
              });
              return batchStatus;
            }
            this._startLoopAfterBatch = false;
            return this.startFocusLoopAgent();
          })
          .catch(() =>
            runWechatAgentOnce({
              output_language: language,
              max_items: 6
            })
              .then(() => this.startFocusLoopAgent())
              .catch(() => this.startFocusLoopAgent())
          );
      })
      .catch(() => {
        this.setData({
          sessionMessage: this.data.i18n.autoCollectFailed
        });
      });
  },

  resumeFocusCollectionIfNeeded() {
    const app = getApp();
    const language = app.globalData.preferences.language;
    return getWechatAgentStatus()
      .catch(() => ({ running: false }))
      .then((status) => {
        if (status && status.running) {
          this.setData({
            sessionMessage: this.data.i18n.autoCollectReady
          });
          return this.refreshBatchStatus();
        }
        return getWechatAgentConfig()
          .catch(() => null)
          .then((config) => {
            const previousInterval = Number(config && config.loop_interval_sec);
            this._focusPreviousLoopInterval = Number.isFinite(previousInterval) ? previousInterval : null;
            if (this._focusPreviousLoopInterval && this._focusPreviousLoopInterval > 90) {
              return updateWechatAgentConfig({ loop_interval_sec: 90 }).catch(() => null);
            }
            return null;
          })
          .then(() => {
            app.globalData.focusOwnsWechatAgent = true;
            this.setData({ focusOwnsWechatAgent: true });
            return startWechatAgent();
          })
          .then(() => {
            this.setData({
              sessionMessage: this.data.i18n.autoCollectEnabled
            });
            return this.refreshBatchStatus();
          })
          .catch(() => {
            this.setData({
              sessionMessage: this.data.i18n.autoCollectFailed
            });
          });
      });
  },

  disableFocusCollectionIfOwned() {
    const app = getApp();
    const ownsAgent = !!(this.data.focusOwnsWechatAgent || app.globalData.focusOwnsWechatAgent);
    this.clearFocusWechatOwnership();
    if (!ownsAgent) {
      return Promise.resolve();
    }
    const previousInterval = Number(this._focusPreviousLoopInterval);
    this._focusPreviousLoopInterval = null;
    const restoreIntervalPromise = Number.isFinite(previousInterval) && previousInterval > 0
      ? updateWechatAgentConfig({ loop_interval_sec: previousInterval }).catch(() => null)
      : Promise.resolve();
    return restoreIntervalPromise.then(() => stopWechatAgent().catch(() => null));
  },

  buildAssistantPlan() {
    if (this.data.assistantLoading) return;
    this.setData({ assistantLoading: true, assistantMessage: "" });
    createFocusAssistantPlan({
      goal_text: this.data.goalText || undefined,
      duration_minutes: this.getSelectedDurationMinutes(),
      output_language: getApp().globalData.preferences.language
    })
      .then((plan) => {
        this.setData({ assistantPlan: plan });
      })
      .catch(() => {
        this.setData({ assistantMessage: this.data.i18n.assistantPlanFailed });
      })
      .finally(() => {
        this.setData({ assistantLoading: false });
      });
  },

  runAssistantAction(e) {
    const action = e.currentTarget.dataset.action;
    const channel = e.currentTarget.dataset.channel || "workbuddy";
    if (!action || this.data.assistantExecutingKey) return;
    const actionKey = `${action}:${channel}`;
    this.setData({ assistantExecutingKey: actionKey, assistantMessage: "" });
    executeFocusAssistantAction({
      action_key: action,
      goal_text: this.data.goalText || undefined,
      duration_minutes: this.getSelectedDurationMinutes(),
      output_language: getApp().globalData.preferences.language,
      channel
    })
      .then((result) => {
        const task = result.task || {};
        const preview = String((task.output_payload && task.output_payload.content) || "").slice(0, 220).trim();
        appendFocusAssistantResult(buildLatestFocusAssistantResult({
          action: (this.data.assistantPlan && this.data.assistantPlan.actions || []).find((entry) => entry.key === action) || {
            key: action,
            title: action
          },
          channelUsed: result.channel_used || channel,
          message: result.message || "",
          task,
          sessionId: this.data.sessionId || "",
          goalText: this.data.goalText || "",
          durationMinutes: this.getSelectedDurationMinutes()
        }));
        this.setData({
          assistantMessage: result.message || "",
          assistantOutputPreview: preview
        });
      })
      .catch(() => {
        this.setData({ assistantMessage: this.data.i18n.assistantExecuteFailed });
      })
      .finally(() => {
        this.setData({ assistantExecutingKey: "" });
      });
  },

  startOrPause() {
    if (this.data.running) {
      if (!this.data.sessionId) {
        const remaining = this.getRemainingSecondsFromRuntime();
        this.clearCountdownRuntime();
        this.syncCountdownState(remaining);
      }
      this.stopTimer();
      this.setData({ running: false });
      this._pausedByUser = true;
      this.disableFocusCollectionIfOwned().finally(() => {
        this.setData({
          sessionMessage: this.data.i18n.statePaused || "已暂停，公众号自动采集也已停止。"
        });
      });
      trackEvent("focus_pause");
      return;
    }
    if (this.data.startingSession) {
      return;
    }
    this._pausedByUser = false;
    this.ensureSession().then(() => {
      this.startTimer();
      this.setData({ running: true });
      this.resumeFocusCollectionIfNeeded();
      trackEvent("focus_start", {
        duration: this.data.duration,
        goal_text: this.data.goalText || ""
      });
    });
  },

  ensureSession() {
    if (this.data.sessionId && !this.data.sessionClosed) {
      this.startSessionPolling();
      this.refreshSessionSnapshot();
      return Promise.resolve();
    }
    this.setData({ startingSession: true });
    return startSession({
      goal_text: this.data.goalText || undefined,
      duration_minutes: this.getSelectedDurationMinutes(),
      output_language: getApp().globalData.preferences.language
    })
      .then((session) => {
        const app = getApp();
        const selectedDuration = this.setSelectedDurationMinutes(
          Number(session.duration_minutes || this.getSelectedDurationMinutes())
        );
        const totalSeconds = selectedDuration * 60;
        app.globalData.currentSessionId = session.id;
        app.globalData.currentSessionGoal = this.data.goalText || "";
        app.globalData.currentSessionDuration = selectedDuration;
        app.globalData.currentFeedMode = "focus";
        this.setCountdownRuntime(totalSeconds, Date.now() + totalSeconds * 1000);
        this.setData({
          sessionId: session.id,
          duration: selectedDuration,
          sessionClosed: false,
          secondsLeft: totalSeconds,
          countdownText: formatCountdown(totalSeconds),
          progressPercent: 0,
          sessionMessage: this.data.i18n.sessionStarted
        });
        return this.enableFocusCollection()
          .then(() => this.refreshSessionSnapshot(session.id))
          .finally(() => {
            this.startSessionPolling();
          });
      })
      .catch(() => {
        const app = getApp();
        const selectedDuration = this.getSelectedDurationMinutes();
        const totalSeconds = selectedDuration * 60;
        app.globalData.currentSessionGoal = this.data.goalText || "";
        app.globalData.currentSessionDuration = selectedDuration;
        app.globalData.currentFeedMode = "focus";
        this.setCountdownRuntime(totalSeconds, Date.now() + totalSeconds * 1000);
        this.syncCountdownState(totalSeconds, totalSeconds);
        this.setData({
          duration: selectedDuration,
          sessionMessage: this.data.i18n.sessionLocal
        });
      })
      .finally(() => {
        this.setData({ startingSession: false });
      });
  },

  startTimer(totalSecondsOverride, remainingSecondsOverride, endAtMsOverride) {
    this.stopTimer();
    const totalSeconds = this.getCountdownTotalSeconds(totalSecondsOverride);
    if (Number.isFinite(endAtMsOverride) && endAtMsOverride > 0) {
      this.setCountdownRuntime(totalSeconds, endAtMsOverride);
    } else if (!Number.isFinite(this._countdownEndAtMs) || this._countdownEndAtMs <= 0) {
      const seedRemaining = Number.isFinite(remainingSecondsOverride)
        ? Math.floor(remainingSecondsOverride)
        : Math.max(0, Math.min(totalSeconds, Math.floor(Number(this.data.secondsLeft || totalSeconds))));
      this.setCountdownRuntime(totalSeconds, Date.now() + seedRemaining * 1000);
    } else {
      this._countdownTotalSeconds = totalSeconds;
    }

    const tick = () => {
      const next = this.getRemainingSecondsFromRuntime(totalSeconds);
      if (next <= 0) {
        this.stopTimer();
        this.clearCountdownRuntime();
        this.setData({
          running: false,
          secondsLeft: 0,
          countdownText: "00:00",
          progressPercent: 100
        });
        this.finalizeSession();
        return;
      }

      if (next !== this.data.secondsLeft) {
        this.syncCountdownState(next, totalSeconds);
      }
    };

    tick();
    this._timer = setInterval(tick, 250);
  },

  stopTimer() {
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
  },

  finishEarly() {
    this.clearCountdownRuntime();
    this.stopTimer();
    this.setData({
      running: false,
      secondsLeft: 0,
      countdownText: "00:00",
      progressPercent: 100
    });
    this._pausedByUser = false;
    this.disableFocusCollectionIfOwned().finally(() => {
      void this.finalizeSession();
    });
    trackEvent("focus_finish_early");
  },

  resetTimer() {
    this.stopTimer();
    this.clearCountdownRuntime();
    this._pausedByUser = false;
    void this.finalizeSession().finally(() => {
      const app = getApp();
      const selectedDuration = this.getSelectedDurationMinutes();
      const totalSeconds = selectedDuration * 60;
      this._countdownTotalSeconds = totalSeconds;
      app.globalData.currentSessionId = "";
      app.globalData.currentSessionGoal = "";
      app.globalData.currentFeedMode = "normal";
      this.setData({
        duration: selectedDuration,
        running: false,
        secondsLeft: totalSeconds,
        countdownText: formatCountdown(totalSeconds),
        newItemsCount: 0,
        progressPercent: 0,
        sessionId: "",
        sessionClosed: false,
        sessionMessage: "",
        focusOwnsWechatAgent: false
      });
    });
    trackEvent("focus_reset");
  },

  finalizeSession() {
    const { sessionId, sessionClosed } = this.data;
    const app = getApp();
    const releaseCollector = () =>
      this.disableFocusCollectionIfOwned().finally(() => {
        this._pausedByUser = false;
        this.clearCountdownRuntime();
        app.globalData.currentSessionId = "";
        app.globalData.currentSessionGoal = "";
        app.globalData.currentFeedMode = "normal";
      });

    if (!sessionId || sessionClosed) {
      return releaseCollector();
    }
    return finishSession(sessionId, {
      output_language: getApp().globalData.preferences.language
    })
      .then(() => {
        this.setData({
          sessionClosed: true,
          sessionMessage: this.data.i18n.sessionFinished
        });
        trackEvent("focus_finish", { status: "ok" });
      })
      .catch(() => {
        this.setData({
          sessionClosed: true,
          sessionMessage: this.data.i18n.sessionFinishFallback
        });
        trackEvent("focus_finish", { status: "fallback" });
      })
      .finally(() => {
        this.stopSessionPolling();
      })
      .then(() => releaseCollector());
  },

  jumpSummary() {
    const { sessionId } = this.data;
    wx.switchTab({
      url: "/pages/session-summary/index",
      fail: () => {
        wx.navigateTo({
          url: `/pages/session-summary/index?sessionId=${sessionId || ""}`
        });
      }
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
  }
});
