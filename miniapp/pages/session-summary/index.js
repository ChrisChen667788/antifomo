const {
  getSession,
  getLatestSession,
  createTask,
  flushPendingQueue,
  importTodoCalendar,
  listKnowledgeEntries,
  previewTodoCalendarImport,
  sendWorkBuddyWebhook,
  getWechatAgentBatchStatus
} = require("../../utils/api");
const { trackEvent } = require("../../utils/analytics");
const { t } = require("../../utils/i18n");
const { getPreferenceClass } = require("../../utils/preferences");
const {
  getLatestFocusAssistantResult,
  getFocusAssistantHistory
} = require("../../utils/focus-assistant-storage");

function formatAssistantTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  const hours = `${date.getHours()}`.padStart(2, "0");
  const minutes = `${date.getMinutes()}`.padStart(2, "0");
  return `${month}-${day} ${hours}:${minutes}`;
}

function fallbackSummary(session) {
  const metrics = session.metrics || {};
  const language = (getApp().globalData.preferences || {}).language || "zh-CN";
  return `# ${t(language, "summary.markdownTitle", "Markdown 总结")}

- ${t(language, "focus.goal", "本次目标")}: ${session.goal_text || t(language, "common.notSet", "未设置")}
- ${t(language, "summary.duration", "Session 时长")}: ${session.duration_minutes || 25} ${t(language, "common.minutes", "分钟")}
- ${t(language, "summary.newContent", "新增内容数")}: ${metrics.new_content_count || 0}
- ${t(language, "summary.deepRead", "推荐深读数")}: ${metrics.deep_read_count || 0}
- ${t(language, "summary.later", "稍后读数")}: ${metrics.later_count || 0}
- ${t(language, "summary.skip", "可忽略数")}: ${metrics.skip_count || 0}

## 建议下一步
1. 先处理推荐深读内容。
2. 将可忽略内容快速归档。
3. 用下一次 Focus 处理剩余稍后读。`;
}

function buildLocalizedSystemSummary(session, language) {
  const metrics = session.metrics || {};
  const goal = session.goal_text || t(language, "common.notSet", "未设置");
  const newCount = metrics.new_content_count || 0;
  const deepRead = metrics.deep_read_count || 0;
  const later = metrics.later_count || 0;
  const skip = metrics.skip_count || 0;

  if (language === "zh-TW") {
    return `這輪專注圍繞「${goal}」完成，期間新增 ${newCount} 條內容，其中建議深讀 ${deepRead} 條、稍後讀 ${later} 條、可忽略 ${skip} 條。建議先處理深讀項，再統一整理其餘內容。`;
  }
  if (language === "en") {
    return `This focus block centered on "${goal}". ${newCount} new items arrived: ${deepRead} deep reads, ${later} read-later items, and ${skip} skippable items. Start with the deep reads, then batch the rest.`;
  }
  if (language === "ja") {
    return `今回の集中は「${goal}」を軸に完了しました。新規項目は ${newCount} 件で、そのうち深読み推奨 ${deepRead} 件、後で読む ${later} 件、スキップ可 ${skip} 件です。まず深読み項目から処理し、その後に残りをまとめて整理してください。`;
  }
  if (language === "ko") {
    return `이번 집중 세션은 "${goal}"을 중심으로 마무리되었습니다. 새로 들어온 항목은 ${newCount}개이며, 이 중 정독 ${deepRead}개, 나중에 읽기 ${later}개, 건너뛰기 ${skip}개입니다. 먼저 정독 항목을 처리한 뒤 나머지를 한 번에 정리하세요.`;
  }
  return `这轮专注围绕“${goal}”完成，期间新增 ${newCount} 条内容，其中建议深读 ${deepRead} 条、稍后读 ${later} 条、可忽略 ${skip} 条。建议先处理深读项，再统一整理其余内容。`;
}

function resolveDisplayedSummary(session, language) {
  if (!session) {
    return { text: "", notice: "" };
  }

  const localizedSummary = buildLocalizedSystemSummary(session, language);
  const summaryText = String(session.summary_text || "").trim();
  const outputLanguage = String(session.output_language || "").trim();

  if (!summaryText) {
    return { text: localizedSummary, notice: "" };
  }

  if (outputLanguage && outputLanguage !== language) {
    return {
      text: localizedSummary,
      notice: t(
        language,
        "summary.languageAdjusted",
        language === "zh-TW"
          ? "此摘要原始語言與目前介面不一致，已改用目前語言重述。"
          : language === "en"
            ? "This summary was generated in another language and has been rephrased in the current UI language."
            : language === "ja"
              ? "この要約は別の言語で生成されたため、現在の表示言語で再構成しています。"
              : language === "ko"
                ? "이 요약은 다른 언어로 생성되어 현재 UI 언어로 다시 표시하고 있습니다."
                : "此摘要原始语言与当前界面不一致，已改用当前语言重述。"
      )
    };
  }

  return { text: summaryText, notice: "" };
}

function fallbackReadingList(language) {
  return `# ${t(language, "summary.readingListTitle", "稍后读清单")}

1. ${t(language, "summary.sample.readA", "高价值内容 A（深读）")}
2. ${t(language, "summary.sample.readB", "行业趋势内容 B（深读）")}
3. ${t(language, "summary.sample.readC", "方法论内容 C（稍后读）")}
4. ${t(language, "summary.sample.readD", "工具更新内容 D（稍后读）")}`;
}

function fallbackTodoDraft(language) {
  return `# ${t(language, "summary.todoDraftTitle", "待办草稿")}

- [ ] ${t(language, "summary.sample.todo1", "先深读 2 条高价值内容并记录要点")}
- [ ] ${t(language, "summary.sample.todo2", "将稍后读内容归入下一个专注时段")}
- [ ] ${t(language, "summary.sample.todo3", "把可忽略内容批量归档")}`;
}

function taskNeedsSession(taskType) {
  return taskType !== "export_reading_list";
}

function buildSessionMetrics(session) {
  const metrics = session && session.metrics ? session.metrics : {};
  return {
    newContentCount: Number(metrics.new_content_count || 0),
    deepReadCount: Number(metrics.deep_read_count || 0),
    laterCount: Number(metrics.later_count || 0),
    skipCount: Number(metrics.skip_count || 0)
  };
}

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

function buildBatchSummary(status, i18n) {
  if (!hasBatchSnapshot(status)) {
    return {
      visible: false,
      progress: 0,
      title: "",
      summary: "",
      lastMessage: "",
      metrics: {
        submittedNew: 0,
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
  return {
    visible: true,
    progress,
    title: status.running ? i18n.collectorRunning : i18n.collectorLatest,
    summary: `${i18n.collectorSubmitted} ${Number(status.submitted || 0)} ${i18n.items || "条"}`,
    lastMessage: status.last_message || "",
    metrics: {
      submittedNew: Number(status.submitted_new || 0),
      deduplicatedExisting: Number(status.deduplicated_existing || 0),
      skippedSeen: Number(status.skipped_seen || 0),
      failed: Number(status.failed || 0)
    }
  };
}

function buildScoreLabel(score, language) {
  const numeric = Number(score);
  if (!Number.isFinite(numeric)) {
    return t(language, "summary.score.pending", "评分待补充");
  }
  if (numeric >= 4) {
    return t(language, "summary.score.high", "高价值");
  }
  if (numeric >= 2.8) {
    return t(language, "summary.score.mid", "中价值");
  }
  return t(language, "summary.score.low", "低价值");
}

function buildLatestSessionItems(session, status, language) {
  const items = Array.isArray(session && session.items) ? session.items : [];
  if (!items.length) {
    return [];
  }
  const itemMap = {};
  items.forEach((item) => {
    if (item && item.id) {
      itemMap[item.id] = item;
    }
  });
  const matched = Array.isArray(status && status.new_item_ids)
    ? status.new_item_ids
      .map((id) => itemMap[id])
      .filter(Boolean)
    : [];
  const fallbackLimit = Math.min(
    items.length,
    Math.max(1, Math.min(4, Number((status && status.submitted_new) || 0) || items.length))
  );
  const selected = matched.length ? matched.slice(0, 4) : items.slice(0, fallbackLimit);
  return selected.map((item) => ({
    id: item.id,
    title: item.title || t(language, "common.untitled", "未命名内容"),
    source: item.source_domain || t(language, "common.unknownSource", "未知来源"),
    sourceKey: item.source_domain || "unknown",
    summary: item.short_summary || t(language, "common.noSummary", "暂无摘要"),
    scoreLabel: buildScoreLabel(item.score_value, language),
    actionSuggestion: item.action_suggestion || "later",
    actionLabel:
      item.action_suggestion === "deep_read"
        ? t(language, "action.deep_read", "立即深读")
        : item.action_suggestion === "skip"
          ? t(language, "action.skip", "可放心忽略")
          : t(language, "action.later", "稍后精读")
  }));
}

function buildLatestSourceOptions(items, language) {
  const seen = {};
  const options = [
    {
      key: "all",
      label: t(language, "summary.filter.allSources", "全部来源")
    }
  ];
  items.forEach((item) => {
    const key = item.sourceKey || "unknown";
    if (seen[key]) return;
    seen[key] = true;
    options.push({
      key,
      label: item.source || t(language, "common.unknownSource", "未知来源")
    });
  });
  return options;
}

function buildLatestActionOptions(items, language) {
  const seen = {};
  const options = [
    {
      key: "all",
      label: t(language, "summary.filter.allActions", "全部动作")
    }
  ];
  items.forEach((item) => {
    const key = item.actionSuggestion || "later";
    if (seen[key]) return;
    seen[key] = true;
    options.push({
      key,
      label: item.actionLabel
    });
  });
  return options;
}

function filterLatestSessionItems(items, sourceFilter, actionFilter) {
  return items.filter((item) => {
    const sourceMatch = sourceFilter === "all" || item.sourceKey === sourceFilter;
    const actionMatch = actionFilter === "all" || (item.actionSuggestion || "later") === actionFilter;
    return sourceMatch && actionMatch;
  });
}

function getFallbackTaskContent(taskType, session) {
  const language = (getApp().globalData.preferences || {}).language || "zh-CN";
  if (taskType === "export_reading_list") {
    return fallbackReadingList(language);
  }
  if (taskType === "export_todo_draft") {
    return fallbackTodoDraft(language);
  }
  return fallbackSummary(session || {});
}

function extractResearchRecommendation(entry, language) {
  const payload = entry && entry.metadata_payload && typeof entry.metadata_payload === "object"
    ? entry.metadata_payload
    : null;
  const report = payload && payload.report ? payload.report : null;
  const actionCards = Array.isArray(payload && payload.action_cards) ? payload.action_cards : [];
  const summary =
    String(report && report.executive_summary || "").trim() ||
    String(entry && entry.content || "")
      .split("\n")
      .map((line) => String(line || "").replace(/^#+\s*/, "").replace(/^- /, "").trim())
      .filter(Boolean)[0] ||
    t(language, "common.noSummary", "暂无摘要");
  const normalizeNames = (list) =>
    (Array.isArray(list) ? list : [])
      .map((item) => String(item || "").trim())
      .filter(Boolean)
      .slice(0, 3);
  const parseActionPhases = (steps) =>
    (Array.isArray(steps) ? steps : [])
      .map((step) => String(step || "").trim())
      .filter(Boolean)
      .map((step) => {
        const match = step.match(/^(短期|中期|长期|Short term|Mid term|Long term)(?:（([^）]+)）|\(([^)]+)\))?[:：]\s*(.+)$/i);
        if (!match) {
          return {
            label: "关键动作",
            horizon: "",
            content: step
          };
        }
        return {
          label: match[1],
          horizon: match[2] || match[3] || "",
          content: match[4]
        };
      })
      .slice(0, 3);
  return {
    id: entry.id,
    title: entry.title,
    summary,
    createdAt: entry.created_at,
    isFocusReference: !!entry.is_focus_reference,
    collectionName: entry.collection_name || "",
    topicAnchors: normalizeNames(report && report.source_diagnostics && report.source_diagnostics.topic_anchor_terms),
    matchedThemes: normalizeNames(report && report.source_diagnostics && report.source_diagnostics.matched_theme_labels),
    filteredOldSourceCount: Number((report && report.source_diagnostics && report.source_diagnostics.filtered_old_source_count) || 0),
    retrievalQuality: String((report && report.source_diagnostics && report.source_diagnostics.retrieval_quality) || "low"),
    evidenceMode: String((report && report.source_diagnostics && report.source_diagnostics.evidence_mode) || "fallback"),
    officialSourcePercent: Math.round(Number((report && report.source_diagnostics && report.source_diagnostics.official_source_ratio) || 0) * 100),
    uniqueDomainCount: Number((report && report.source_diagnostics && report.source_diagnostics.unique_domain_count) || 0),
    normalizedEntityCount: Number((report && report.source_diagnostics && report.source_diagnostics.normalized_entity_count) || 0),
    correctiveTriggered: Boolean(report && report.source_diagnostics && report.source_diagnostics.corrective_triggered),
    candidateProfileCompanies: normalizeNames(report && report.source_diagnostics && report.source_diagnostics.candidate_profile_companies),
    candidateProfileHitCount: Number((report && report.source_diagnostics && report.source_diagnostics.candidate_profile_hit_count) || 0),
    candidateProfileOfficialHitCount: Number((report && report.source_diagnostics && report.source_diagnostics.candidate_profile_official_hit_count) || 0),
    candidateProfileSourceLabels: normalizeNames(report && report.source_diagnostics && report.source_diagnostics.candidate_profile_source_labels),
    topTargets: normalizeNames(
      Array.isArray(report && report.top_target_accounts) && report.top_target_accounts.length
        ? report.top_target_accounts.map((item) => item.name)
        : report && report.target_accounts
    ),
    topCompetitors: normalizeNames(
      Array.isArray(report && report.top_competitors) && report.top_competitors.length
        ? report.top_competitors.map((item) => item.name)
        : report && report.competitor_profiles
    ),
    topPartners: normalizeNames(
      Array.isArray(report && report.top_ecosystem_partners) && report.top_ecosystem_partners.length
        ? report.top_ecosystem_partners.map((item) => item.name)
        : report && report.ecosystem_partners
    ),
    actionCards: actionCards
      .map((card) => ({
        title: String(card.title || "").trim(),
        target_persona: String(card.target_persona || "").trim(),
        execution_window: String(card.execution_window || "").trim(),
        deliverable: String(card.deliverable || "").trim(),
        phases: parseActionPhases(card.recommended_steps)
      }))
      .filter((card) => card.title)
      .slice(0, 2)
  };
}

Page({
  data: {
    sessionId: "",
    session: null,
    displaySummary: "",
    summaryNotice: "",
    loading: true,
    taskLoadingType: "",
    calendarLoading: false,
    taskMessage: "",
    taskTone: "info",
    markdown: "",
    readingList: "",
    todoDraft: "",
    sessionMetrics: buildSessionMetrics(null),
    latestSessionItems: [],
    assistantResult: null,
    assistantHistory: [],
    collectorBatchStatus: null,
    collectorBatchSummary: {
      visible: false,
      progress: 0,
      title: "",
      summary: "",
      lastMessage: "",
      metrics: {
        submittedNew: 0,
        deduplicatedExisting: 0,
        skippedSeen: 0,
        failed: 0
      }
    },
    latestSourceFilter: "all",
    latestActionFilter: "all",
    latestSourceOptions: [],
    latestActionOptions: [],
    filteredLatestSessionItems: [],
    researchRecommendations: [],
    prefClass: "",
    settingsLabel: "设置",
    i18n: {}
  },

  onLoad(options) {
    const app = getApp();
    const sessionId = options.sessionId || app.globalData.currentSessionId || "";
    this.setData({ sessionId });
    trackEvent("page_view", { page: "session_summary", session_id: sessionId || "" });
    this.applyPreferences();
    this.tryFlushQueue();
    this.loadSession();
    this.loadBatchStatus();
    this.loadResearchRecommendations();
  },

  onShow() {
    this.applyPreferences();
    this.tryFlushQueue();
    this.loadBatchStatus();
    this.loadResearchRecommendations();
    if (!this.data.session) {
      this.loadSession();
    }
  },

  onPullDownRefresh() {
    this.loadSession().finally(() => wx.stopPullDownRefresh());
  },

  applyPreferences() {
    const app = getApp();
    const preferences = app.globalData.preferences;
    const language = preferences.language;
    const i18n = {
      kicker: t(language, "summary.kicker", "Return Channel"),
      title: t(language, "summary.title", "Session 回流中心"),
      subtitle: t(language, "summary.subtitle", "将专注期间积压的信息压缩成可执行清单。"),
      goal: t(language, "focus.goal", "本次目标"),
      goalUnset: t(language, "common.notSet", "未设置"),
      exportsTitle: t(language, "summary.exportsTitle", "导出任务"),
      exportsHint: t(language, "summary.exportsHint", "优先通过 WorkBuddy 执行，失败时自动回退直连 API。"),
      outputsTitle: t(language, "summary.outputsTitle", "导出结果"),
      outputsHint: t(language, "summary.outputsHint", "导出结果会保留在本地，方便稍后复制或继续加工。"),
      loading: t(language, "summary.loading", "正在加载 Session..."),
      emptySession: t(language, "summary.emptySession", "暂无可用 Session，请先去 Focus 页面开始一次专注。"),
      duration: t(language, "summary.duration", "Session 时长"),
      newContent: t(language, "summary.newContent", "新增内容数"),
      deepRead: t(language, "summary.deepRead", "推荐深读"),
      later: t(language, "summary.later", "稍后读"),
      skip: t(language, "summary.skip", "可忽略"),
      systemSummary: t(language, "summary.systemSummary", "系统总结"),
      systemSummaryEmpty: t(language, "summary.systemSummaryEmpty", "尚未生成总结，可先执行导出任务。"),
      generateMarkdown: t(language, "summary.generateMarkdown", "生成 Markdown 总结"),
      generateReadingList: t(language, "summary.generateReadingList", "生成稍后读清单"),
      generateTodoDraft: t(language, "summary.generateTodoDraft", "生成待办草稿"),
      markdownTitle: t(language, "summary.markdownTitle", "Markdown 总结"),
      readingListTitle: t(language, "summary.readingListTitle", "稍后读清单"),
      todoDraftTitle: t(language, "summary.todoDraftTitle", "待办草稿"),
      copyMarkdown: t(language, "summary.copyMarkdown", "复制 Markdown"),
      copyReadingList: t(language, "summary.copyReadingList", "复制清单"),
      copyTodo: t(language, "summary.copyTodo", "复制待办"),
      importTodoCalendar: t(language, "summary.importTodoCalendar", "导入 Mac 日历"),
      importingCalendar: t(language, "summary.importingCalendar", "导入中..."),
      calendarConfirmTitle: t(language, "summary.calendarConfirmTitle", "确认导入到 Mac 日历？"),
      calendarConfirmDetail: t(language, "summary.calendarConfirmDetail", "将根据待办草稿创建日历事项。"),
      calendarConfirmCount: t(language, "summary.calendarConfirmCount", "待办数量"),
      calendarConfirmCalendar: t(language, "summary.calendarConfirmCalendar", "日历"),
      calendarImported: t(language, "summary.calendarImported", "已导入 Mac 日历"),
      calendarCancelled: t(language, "summary.calendarCancelled", "已取消导入 Mac 日历"),
      calendarFailed: t(language, "summary.calendarFailed", "导入 Mac 日历失败"),
      cancel: t(language, "common.cancel", "取消"),
      placeholder: t(language, "summary.placeholder", "点击上方按钮后展示结果"),
      routeHint: t(language, "summary.routeHint", "导出优先通过 WorkBuddy 执行，失败时自动回退直连 API。"),
      statusTitle: t(language, "summary.statusTitle", "当前状态"),
      assistantTitle: t(language, "summary.assistantTitle", "Focus Assistant 回流"),
      assistantHint: t(language, "summary.assistantHint", "最近一次专注辅助动作已经回流到当前总结页。"),
      assistantOutput: t(language, "summary.assistantOutput", "输出摘要"),
      assistantNoOutput: t(language, "summary.assistantNoOutput", "本次动作未返回可展示的文本输出。"),
      assistantCopy: t(language, "summary.assistantCopy", "复制结果"),
      assistantWorkBuddy: t(language, "summary.assistantWorkBuddy", "WorkBuddy"),
      assistantDirect: t(language, "summary.assistantDirect", "直连"),
      assistantHistory: t(language, "summary.assistantHistory", "最近执行"),
      collectorKicker: t(language, "focus.collectorKicker", "公众号采集"),
      collectorRunning: t(language, "focus.collectorRunning", "正在静默扫描最新文章"),
      collectorLatest: t(language, "focus.collectorLatest", "最近一轮采集结果"),
      collectorSubmitted: t(language, "focus.collectorSubmitted", "累计入队"),
      collectorSubmittedNew: t(language, "focus.collectorSubmittedNew", "真正新增"),
      collectorDedup: t(language, "focus.collectorDedup", "历史去重"),
      collectorSeen: t(language, "focus.collectorSeen", "已跳过"),
      collectorFailed: t(language, "focus.collectorFailed", "失败"),
      collectorLastMessage: t(language, "focus.collectorLastMessage", "状态"),
      latestNewTitle: t(language, "summary.latestNew.title", "本轮新增卡片"),
      latestNewHint: t(language, "summary.latestNew.hint", "优先展示最近一轮采集命中的新卡片，可直接进入详情继续判断。"),
      latestNewOpen: t(language, "summary.latestNew.open", "打开详情"),
      latestNewCollector: t(language, "summary.latestNew.collector", "查看采集器"),
      latestNewEmpty: t(language, "summary.latestNew.empty", "当前筛选条件下没有匹配的新增卡片。"),
      researchTitle: t(language, "summary.researchTitle", "推荐研报"),
      researchHint: t(language, "summary.researchHint", "把最近沉淀的行业研报与行动卡带回本次总结，继续推进销售、投标与生态动作。"),
      researchOpen: t(language, "summary.researchOpen", "打开研报中心"),
      researchOpenDetail: t(language, "summary.researchOpenDetail", "打开知识卡片"),
      researchActionTarget: t(language, "research.actionTarget", "优先对象"),
      researchActionWindow: t(language, "research.actionWindow", "执行窗口"),
      researchActionDeliverable: t(language, "research.actionDeliverable", "产出物"),
      researchActionTimeline: t(language, "research.actionTimeline", "推进节奏"),
      researchTopTargets: t(language, "research.topTargets", "高价值甲方 Top 3"),
      researchTopCompetitors: t(language, "research.topCompetitors", "高威胁竞品 Top 3"),
      researchTopPartners: t(language, "research.topPartners", "高影响力生态伙伴 Top 3"),
      items: t(language, "common.items", "条"),
      taskQueued: t(language, "summary.taskQueued", "任务已离线排队，恢复网络后会自动补发"),
      taskRunningWorkBuddy: t(language, "summary.taskRunningWorkBuddy", "正在通过 WorkBuddy 执行任务，失败会自动回退。"),
      taskDoneWorkBuddy: t(language, "summary.taskDoneWorkBuddy", "已通过 WorkBuddy 完成导出"),
      taskDoneDirectFallback: t(language, "summary.taskDoneDirectFallback", "WorkBuddy 不可用，已回退直连导出"),
      taskFailed: t(language, "summary.taskFailed", "生成失败或任务执行中"),
      localSession: t(language, "summary.localSession", "后端未连接，当前为本地演示 session"),
      copied: t(language, "summary.copied", "已复制"),
      minutes: t(language, "common.minutes", "分钟")
    };
    const summaryState = resolveDisplayedSummary(this.data.session, language);
    this.setData({
      prefClass: getPreferenceClass(preferences, app.globalData.systemTheme),
      settingsLabel: t(language, "common.settings", "设置"),
      i18n,
      displaySummary: summaryState.text,
      summaryNotice: summaryState.notice,
      collectorBatchSummary: buildBatchSummary(this.data.collectorBatchStatus, i18n)
    });
    this.syncLatestSessionView({ resetFilters: false });
    wx.setNavigationBarTitle({
      title: t(language, "nav.summary", "Summary")
    });
    this.syncAssistantResult();
  },

  loadSession() {
    const { sessionId } = this.data;
    this.setData({ loading: true });
    const loadPrimarySession = sessionId ? getSession(sessionId) : getLatestSession();
    return loadPrimarySession
      .then((session) => {
        if (session && !session._fromMock) {
          return session;
        }
        if (sessionId) {
          return getLatestSession().then((fallbackSession) => {
            if (fallbackSession && !fallbackSession._fromMock) {
              return fallbackSession;
            }
            return session;
          });
        }
        return session;
      })
      .then((session) => {
        const language = (getApp().globalData.preferences || {}).language || "zh-CN";
        const summaryState = resolveDisplayedSummary(session, language);
        const resolvedSessionId = session && session.id ? session.id : sessionId;
        if (resolvedSessionId && resolvedSessionId !== this.data.sessionId) {
          getApp().globalData.currentSessionId = resolvedSessionId;
        }
        this.setData({
          sessionId: resolvedSessionId || "",
          session,
          sessionMetrics: buildSessionMetrics(session),
          displaySummary: summaryState.text,
          summaryNotice: summaryState.notice,
          loading: false,
          taskMessage: session._fromMock ? this.data.i18n.localSession : "",
          taskTone: session._fromMock ? "warning" : "info"
        });
        this.syncLatestSessionView({ session, resetFilters: false });
        this.syncAssistantResult(session.id);
      })
      .catch(() => {
        this.setData({ loading: false, latestSessionItems: [], filteredLatestSessionItems: [] });
        this.syncAssistantResult();
      });
  },

  loadBatchStatus() {
    return getWechatAgentBatchStatus()
      .then((status) => {
        const language = (getApp().globalData.preferences || {}).language || "zh-CN";
        this.setData({
          collectorBatchStatus: status,
          collectorBatchSummary: buildBatchSummary(status, this.data.i18n || {})
        });
        this.syncLatestSessionView({ status, resetFilters: false, language });
      })
      .catch(() => Promise.resolve());
  },

  loadResearchRecommendations() {
    const language = (getApp().globalData.preferences || {}).language || "zh-CN";
    return listKnowledgeEntries(3, { sourceDomain: "research.report" })
      .then((response) => {
        this.setData({
          researchRecommendations: (response.items || []).map((entry) =>
            extractResearchRecommendation(entry, language)
          )
        });
      })
      .catch(() => {
        this.setData({ researchRecommendations: [] });
      });
  },

  syncLatestSessionView(options) {
    const opts = options || {};
    const language = opts.language || (getApp().globalData.preferences || {}).language || "zh-CN";
    const session = Object.prototype.hasOwnProperty.call(opts, "session") ? opts.session : this.data.session;
    const status = Object.prototype.hasOwnProperty.call(opts, "status")
      ? opts.status
      : this.data.collectorBatchStatus;
    const latestSessionItems = buildLatestSessionItems(session, status, language);
    const latestSourceOptions = buildLatestSourceOptions(latestSessionItems, language);
    const latestActionOptions = buildLatestActionOptions(latestSessionItems, language);
    const sourceKeys = latestSourceOptions.map((option) => option.key);
    const actionKeys = latestActionOptions.map((option) => option.key);
    const latestSourceFilter =
      opts.resetFilters || sourceKeys.indexOf(this.data.latestSourceFilter) < 0
        ? "all"
        : this.data.latestSourceFilter;
    const latestActionFilter =
      opts.resetFilters || actionKeys.indexOf(this.data.latestActionFilter) < 0
        ? "all"
        : this.data.latestActionFilter;
    const filteredLatestSessionItems = filterLatestSessionItems(
      latestSessionItems,
      latestSourceFilter,
      latestActionFilter
    );
    this.setData({
      latestSessionItems,
      latestSourceOptions,
      latestActionOptions,
      latestSourceFilter,
      latestActionFilter,
      filteredLatestSessionItems
    });
  },

  selectLatestSourceFilter(e) {
    const key = e.currentTarget.dataset.key || "all";
    const filteredLatestSessionItems = filterLatestSessionItems(
      this.data.latestSessionItems,
      key,
      this.data.latestActionFilter
    );
    this.setData({
      latestSourceFilter: key,
      filteredLatestSessionItems
    });
  },

  selectLatestActionFilter(e) {
    const key = e.currentTarget.dataset.key || "all";
    const filteredLatestSessionItems = filterLatestSessionItems(
      this.data.latestSessionItems,
      this.data.latestSourceFilter,
      key
    );
    this.setData({
      latestActionFilter: key,
      filteredLatestSessionItems
    });
  },

  openCollector() {
    wx.navigateTo({
      url: "/pages/collector/index"
    });
  },

  openResearchCenter() {
    wx.navigateTo({
      url: "/pages/research/index"
    });
  },

  openResearchEntry(e) {
    const entryId = e.currentTarget.dataset.entryId;
    if (!entryId) return;
    wx.navigateTo({
      url: `/pages/knowledge/index?id=${entryId}`
    });
  },

  syncAssistantResult(activeSessionId) {
    const language = (getApp().globalData.preferences || {}).language || "zh-CN";
    const currentSessionId = activeSessionId || (this.data.session && this.data.session.id) || this.data.sessionId || "";
    const stored = getLatestFocusAssistantResult();
    const history = getFocusAssistantHistory().filter((entry) => {
      if (entry.sessionId && currentSessionId) {
        return entry.sessionId === currentSessionId;
      }
      return true;
    });
    if (!stored) {
      this.setData({ assistantResult: null, assistantHistory: history });
      return;
    }
    if (stored.sessionId && currentSessionId && stored.sessionId !== currentSessionId) {
      this.setData({ assistantResult: null, assistantHistory: history });
      return;
    }
    const assistantResult = {
      ...stored,
      channelLabel:
        stored.channelUsed === "workbuddy"
          ? t(language, "summary.assistantWorkBuddy", "WorkBuddy")
          : t(language, "summary.assistantDirect", "直连"),
      displayTime: formatAssistantTime(stored.createdAt),
      preview: String(stored.content || "").slice(0, 280).trim()
    };
    const patch = {
      assistantResult,
      assistantHistory: history
        .slice(1, 4)
        .map((entry) => ({
          ...entry,
          displayTime: formatAssistantTime(entry.createdAt),
          preview: String(entry.content || entry.message || "").slice(0, 120).trim()
        }))
    };
    if (stored.taskType === "export_markdown_summary" && !this.data.markdown && stored.content) {
      patch.markdown = stored.content;
    }
    if (stored.taskType === "export_reading_list" && !this.data.readingList && stored.content) {
      patch.readingList = stored.content;
    }
    if (stored.taskType === "export_todo_draft" && !this.data.todoDraft && stored.content) {
      patch.todoDraft = stored.content;
    }
    this.setData(patch);
  },

  showAssistantHistory(e) {
    const index = Number(e.currentTarget.dataset.index || -1);
    const entry = this.data.assistantHistory[index];
    if (!entry) return;
    const language = (getApp().globalData.preferences || {}).language || "zh-CN";
    this.setData({
      assistantResult: {
        ...entry,
        channelLabel:
          entry.channelUsed === "workbuddy"
            ? t(language, "summary.assistantWorkBuddy", "WorkBuddy")
            : t(language, "summary.assistantDirect", "直连"),
        preview: String(entry.content || entry.message || "").slice(0, 280).trim()
      }
    });
  },

  runTask(taskType) {
    if (this.data.taskLoadingType) {
      return Promise.reject(new Error("task is running"));
    }

    const { sessionId, session } = this.data;
    const assistantResult = this.data.assistantResult;
    const payload = {
      task_type: taskType,
      session_id: taskNeedsSession(taskType) ? (sessionId || undefined) : undefined,
      input_payload: {
        output_language: getApp().globalData.preferences.language,
        assistant_context: assistantResult ? {
          action_key: assistantResult.actionKey,
          action_title: assistantResult.actionTitle,
          channel_used: assistantResult.channelUsed,
          task_type: assistantResult.taskType,
          message: assistantResult.message,
          content: assistantResult.content,
          created_at: assistantResult.createdAt
        } : undefined
      }
    };
    const fallbackContent = getFallbackTaskContent(taskType, session || {});

    this.setData({
      taskLoadingType: taskType,
      taskMessage: this.data.i18n.taskRunningWorkBuddy,
      taskTone: "info"
    });

    return sendWorkBuddyWebhook({
      event_type: "create_task",
      request_id: `miniapp_${taskType}_${Date.now()}`,
      task_type: taskType,
      session_id: payload.session_id,
      input_payload: payload.input_payload
    }).then((response) => {
      if (!response || response._fromMock || !response.accepted || !response.task) {
        throw new Error("workbuddy unavailable");
      }
      if (response.task.status !== "done") {
        throw new Error("workbuddy task not done");
      }
      const content =
        (response.task.output_payload && response.task.output_payload.content) || fallbackContent;
      return {
        content,
        channel: "workbuddy",
        queued: false
      };
    }).catch(() => {
      return createTask(payload).then((task) => {
        if (task.status === "failed") {
          throw new Error("direct task failed");
        }
        const content =
          (task.output_payload && task.output_payload.content) || fallbackContent;
        return {
          content,
          channel: "direct",
          queued: !!task.queued
        };
      });
    }).finally(() => {
      this.setData({ taskLoadingType: "" });
    });
  },

  tryFlushQueue() {
    flushPendingQueue(10).then((result) => {
      if (result.flushed > 0) {
        this.setData({
          taskMessage: `${this.data.i18n.taskQueued} (+${result.flushed})`,
          taskTone: "warning"
        });
      }
    });
  },

  generateMarkdown() {
    this.runTask("export_markdown_summary")
      .then(({ content, channel, queued }) => {
        this.setData({
          markdown: content,
          taskMessage: queued
            ? this.data.i18n.taskQueued
            : channel === "workbuddy"
              ? this.data.i18n.taskDoneWorkBuddy
              : this.data.i18n.taskDoneDirectFallback,
          taskTone: queued
            ? "warning"
            : channel === "workbuddy"
              ? "success"
              : "info"
        });
        trackEvent("session_task", { task_type: "export_markdown_summary" });
      })
      .catch(() => this.setData({
        markdown: getFallbackTaskContent("export_markdown_summary", this.data.session || {}),
        taskMessage: this.data.i18n.taskFailed,
        taskTone: "error"
      }));
  },

  generateReadingList() {
    this.runTask("export_reading_list")
      .then(({ content, channel, queued }) => {
        this.setData({
          readingList: content,
          taskMessage: queued
            ? this.data.i18n.taskQueued
            : channel === "workbuddy"
              ? this.data.i18n.taskDoneWorkBuddy
              : this.data.i18n.taskDoneDirectFallback,
          taskTone: queued
            ? "warning"
            : channel === "workbuddy"
              ? "success"
              : "info"
        });
        trackEvent("session_task", { task_type: "export_reading_list" });
      })
      .catch(() => this.setData({
        readingList: getFallbackTaskContent("export_reading_list", this.data.session || {}),
        taskMessage: this.data.i18n.taskFailed,
        taskTone: "error"
      }));
  },

  generateTodoDraft() {
    this.runTask("export_todo_draft")
      .then(({ content, channel, queued }) => {
        this.setData({
          todoDraft: content,
          taskMessage: queued
            ? this.data.i18n.taskQueued
            : channel === "workbuddy"
              ? this.data.i18n.taskDoneWorkBuddy
              : this.data.i18n.taskDoneDirectFallback,
          taskTone: queued
            ? "warning"
            : channel === "workbuddy"
              ? "success"
              : "info"
        });
        trackEvent("session_task", { task_type: "export_todo_draft" });
      })
      .catch(() => this.setData({
        todoDraft: getFallbackTaskContent("export_todo_draft", this.data.session || {}),
        taskMessage: this.data.i18n.taskFailed,
        taskTone: "error"
      }));
  },

  ensureTodoDraft() {
    if ((this.data.todoDraft || "").trim()) {
      return Promise.resolve(this.data.todoDraft);
    }
    return this.runTask("export_todo_draft")
      .then(({ content, channel, queued }) => {
        const resolved = content || getFallbackTaskContent("export_todo_draft", this.data.session || {});
        this.setData({
          todoDraft: resolved,
          taskMessage: queued
            ? this.data.i18n.taskQueued
            : channel === "workbuddy"
              ? this.data.i18n.taskDoneWorkBuddy
              : this.data.i18n.taskDoneDirectFallback,
          taskTone: queued
            ? "warning"
            : channel === "workbuddy"
              ? "success"
              : "info"
        });
        return resolved;
      })
      .catch(() => {
        const fallback = getFallbackTaskContent("export_todo_draft", this.data.session || {});
        this.setData({
          todoDraft: fallback,
          taskMessage: this.data.i18n.taskFailed,
          taskTone: "error"
        });
        return fallback;
      });
  },

  importTodoToCalendar() {
    if (this.data.calendarLoading || !this.data.sessionId) {
      return;
    }
    this.setData({
      calendarLoading: true,
      taskMessage: this.data.i18n.importingCalendar,
      taskTone: "info"
    });
    this.ensureTodoDraft()
      .then((todoDraft) =>
        previewTodoCalendarImport(this.data.sessionId, {
          output_language: getApp().globalData.preferences.language,
          todo_markdown: todoDraft
        })
      )
      .then((preview) => {
        const previewLines = (preview.events || [])
          .slice(0, 3)
          .map((event, index) => {
            const start = new Date(event.start_time);
            const dateText = Number.isNaN(start.getTime())
              ? event.start_time
              : formatAssistantTime(start.toISOString());
            return `${index + 1}. ${event.title}\n${dateText}`;
          })
          .join("\n\n");
        return new Promise((resolve, reject) => {
          wx.showModal({
            title: this.data.i18n.calendarConfirmTitle,
            content:
              `${this.data.i18n.calendarConfirmDetail}\n` +
              `${this.data.i18n.calendarConfirmCalendar}：${preview.calendar_name}\n` +
              `${this.data.i18n.calendarConfirmCount}：${preview.task_count}\n\n` +
              previewLines,
            confirmText: this.data.i18n.importTodoCalendar,
            cancelText: this.data.i18n.cancel,
            success: (result) => {
              if (!result.confirm) {
                reject(new Error("CALENDAR_IMPORT_CANCELLED"));
                return;
              }
              resolve(preview);
            },
            fail: reject
          });
        });
      })
      .then((preview) =>
        importTodoCalendar(this.data.sessionId, {
          output_language: getApp().globalData.preferences.language,
          todo_markdown: preview.markdown,
          calendar_name: preview.calendar_name
        })
      )
      .then((result) => {
        this.setData({
          taskMessage: `${this.data.i18n.calendarImported} · ${result.imported_count}${this.data.i18n.items}`,
          taskTone: "success"
        });
      })
      .catch((error) => {
        const message =
          error && error.message === "CALENDAR_IMPORT_CANCELLED"
            ? this.data.i18n.calendarCancelled
            : error && error.message
              ? error.message
              : this.data.i18n.calendarFailed;
        this.setData({
          taskMessage: message,
          taskTone: error && error.message === "CALENDAR_IMPORT_CANCELLED" ? "warning" : "error"
        });
      })
      .finally(() => {
        this.setData({ calendarLoading: false });
      });
  },

  copyText(e) {
    const text = e.currentTarget.dataset.content || "";
    if (!text) return;
    wx.setClipboardData({
      data: text,
      success: () => {
        wx.showToast({ title: this.data.i18n.copied, icon: "none" });
        trackEvent("session_copy_output");
      }
    });
  },

  openLatestItem(e) {
    const itemId = e.currentTarget.dataset.itemId;
    if (!itemId) return;
    trackEvent("session_open_new_item", { item_id: itemId });
    wx.navigateTo({
      url: `/pages/item/index?id=${itemId}`
    });
  }
});
