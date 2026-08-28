"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  createTask,
  getSessionArtifacts,
  getLatestSession,
  getSession,
  getTask,
  importTodoCalendar,
  listKnowledgeEntries,
  listResearchWatchlists,
  previewTodoCalendarImport,
  sendWorkBuddyWebhook,
  getWechatAgentBatchStatus,
} from "@/lib/api";
import type {
  ApiSessionArtifact,
  ApiSessionItem,
  ApiTask,
  ApiTaskBriefingContext,
  WechatAgentBatchStatus,
} from "@/lib/api/types";
import {
  readFocusAssistantHistory,
  readLatestFocusAssistantResult,
  type StoredFocusAssistantResult,
} from "@/lib/focus-assistant-storage";
import type { SessionMetrics } from "@/lib/mock-data";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { AppIcon } from "@/components/ui/app-icon";
import { WorkBuddyMark } from "@/components/ui/workbuddy-mark";
import {
  MetricCard,
  OutputBlock,
  TaskBriefingContextCard,
} from "@/components/session/session-summary-output-components";
import {
  SESSION_ID_KEY,
  buildLatestSessionItems,
  buildRecommendedDeepReads,
  buildWatchlistHighlights,
  extractSessionResearchItem,
  fallbackExecBrief,
  fallbackMarkdown,
  fallbackOutreachDraft,
  fallbackReadingList,
  fallbackSalesBrief,
  fallbackTodoDraft,
  formatAssistantTime,
  formatDuration,
  getBatchProgress,
  hasBatchSnapshot,
  mapSessionToMetrics,
  parseTaskBriefingContext,
  taskNeedsSession,
  taskSessionId,
  wait,
  watchlistDigestFromHighlights,
  type RecommendedDeepReadItem,
  type SessionResearchItem,
  type SessionSource,
  type SessionWatchlistHighlight,
  type TaskChannel,
  type TaskType,
} from "@/components/session/session-summary-panel-model";

interface SessionSummaryPanelProps {
  metrics: SessionMetrics;
}

export function SessionSummaryPanel({ metrics: initialMetrics }: SessionSummaryPanelProps) {
  const { preferences, t } = useAppPreferences();
  const [metrics, setMetrics] = useState<SessionMetrics>(initialMetrics);
  const [loadingSession, setLoadingSession] = useState(false);
  const [sessionSource, setSessionSource] = useState<SessionSource>("local");
  const [sessionItems, setSessionItems] = useState<ApiSessionItem[]>([]);
  const [recommendedDeepReads, setRecommendedDeepReads] = useState<RecommendedDeepReadItem[]>([]);
  const [markdown, setMarkdown] = useState("");
  const [readingList, setReadingList] = useState("");
  const [todoDraft, setTodoDraft] = useState("");
  const [execBrief, setExecBrief] = useState("");
  const [salesBrief, setSalesBrief] = useState("");
  const [outreachDraft, setOutreachDraft] = useState("");
  const [watchlistDigest, setWatchlistDigest] = useState("");
  const [taskMessage, setTaskMessage] = useState("");
  const [runningTask, setRunningTask] = useState<TaskType | "">("");
  const [calendarImporting, setCalendarImporting] = useState(false);
  const [assistantResult, setAssistantResult] = useState<StoredFocusAssistantResult | null>(null);
  const [assistantHistory, setAssistantHistory] = useState<StoredFocusAssistantResult[]>([]);
  const [wechatBatchStatus, setWechatBatchStatus] = useState<WechatAgentBatchStatus | null>(null);
  const [researchRecommendations, setResearchRecommendations] = useState<SessionResearchItem[]>([]);
  const [watchlistHighlights, setWatchlistHighlights] = useState<SessionWatchlistHighlight[]>([]);
  const [sessionArtifacts, setSessionArtifacts] = useState<ApiSessionArtifact[]>([]);
  const [taskContexts, setTaskContexts] = useState<Partial<Record<TaskType, ApiTaskBriefingContext | null>>>({});
  const [latestSourceFilter, setLatestSourceFilter] = useState("all");
  const [latestActionFilter, setLatestActionFilter] = useState("all");

  useEffect(() => {
    const loadSession = async () => {
      const sessionId =
        initialMetrics.sessionId ||
        (typeof window !== "undefined" ? window.localStorage.getItem(SESSION_ID_KEY) : "");
      setLoadingSession(true);
      try {
        const session = sessionId ? await getSession(sessionId) : await getLatestSession();
        if (typeof window !== "undefined") {
          window.localStorage.setItem(SESSION_ID_KEY, session.id);
        }
        setMetrics(mapSessionToMetrics(session));
        setSessionItems(session.items);
        setRecommendedDeepReads(buildRecommendedDeepReads(session.items, t));
        setSessionSource("api");
        setTaskMessage("");
      } catch {
        setSessionSource("local");
        setSessionItems([]);
        setRecommendedDeepReads([]);
        setTaskMessage(
          t("summary.task.localSession", "暂时没有读取到本轮记录，当前展示本地汇总。"),
        );
      } finally {
        setLoadingSession(false);
      }
    };

    void loadSession();
  }, [initialMetrics.sessionId, t]);

  useEffect(() => {
    const loadBatchStatus = async () => {
      try {
        const status = await getWechatAgentBatchStatus();
        setWechatBatchStatus(status);
      } catch {
        // ignore collector status failures on summary page
      }
    };
    void loadBatchStatus();
  }, []);

  useEffect(() => {
    const sessionId = metrics.sessionId;
    if (!sessionId) {
      setSessionArtifacts([]);
      return;
    }
    let active = true;
    const loadArtifacts = async () => {
      try {
        const artifacts = await getSessionArtifacts(sessionId);
        if (!active) return;
        setSessionArtifacts(artifacts);
      } catch {
        if (!active) return;
        setSessionArtifacts([]);
      }
    };
    void loadArtifacts();
    return () => {
      active = false;
    };
  }, [metrics.sessionId]);

  useEffect(() => {
    const loadResearchRecommendations = async () => {
      try {
        const response = await listKnowledgeEntries(3, { sourceDomain: "research.report" });
        setResearchRecommendations((response.items || []).map(extractSessionResearchItem));
      } catch {
        setResearchRecommendations([]);
      }
    };
    void loadResearchRecommendations();
  }, []);

  useEffect(() => {
    const loadWatchlists = async () => {
      try {
        const watchlists = await listResearchWatchlists();
        setWatchlistHighlights(buildWatchlistHighlights(watchlists));
      } catch {
        setWatchlistHighlights([]);
      }
    };
    void loadWatchlists();
  }, []);

  useEffect(() => {
    const stored = readLatestFocusAssistantResult();
    const history = readFocusAssistantHistory().filter((entry) => {
      if (entry.sessionId && metrics.sessionId) {
        return entry.sessionId === metrics.sessionId;
      }
      return true;
    });
    setAssistantHistory(history);
    if (!stored) {
      setAssistantResult(null);
      return;
    }
    if (stored.sessionId && metrics.sessionId && stored.sessionId !== metrics.sessionId) {
      setAssistantResult(null);
      return;
    }
    setAssistantResult(stored);
    if (stored.taskType === "export_markdown_summary" && !markdown && stored.content) {
      setMarkdown(stored.content);
    }
    if (stored.taskType === "export_reading_list" && !readingList && stored.content) {
      setReadingList(stored.content);
    }
    if (stored.taskType === "export_todo_draft" && !todoDraft && stored.content) {
      setTodoDraft(stored.content);
    }
  }, [metrics.sessionId, markdown, readingList, todoDraft]);

  const latestSessionItems = useMemo(
    () => buildLatestSessionItems(sessionItems, wechatBatchStatus, t),
    [sessionItems, wechatBatchStatus, t],
  );

  useEffect(() => {
    setLatestSourceFilter("all");
    setLatestActionFilter("all");
  }, [latestSessionItems.length]);

  const latestSourceOptions = useMemo(
    () => ["all", ...Array.from(new Set(latestSessionItems.map((item) => item.sourceKey)))],
    [latestSessionItems],
  );

  const latestActionOptions = useMemo(
    () => ["all", ...Array.from(new Set(latestSessionItems.map((item) => item.actionSuggestion || "later")))],
    [latestSessionItems],
  );

  const filteredLatestSessionItems = useMemo(
    () =>
      latestSessionItems.filter((item) => {
        const sourceMatch = latestSourceFilter === "all" || item.sourceKey === latestSourceFilter;
        const actionMatch =
          latestActionFilter === "all" || (item.actionSuggestion || "later") === latestActionFilter;
        return sourceMatch && actionMatch;
      }),
    [latestActionFilter, latestSourceFilter, latestSessionItems],
  );

  const latestArtifactsByType = useMemo(() => {
    const pickLatest = (artifactType: string) =>
      sessionArtifacts.find((artifact) => artifact.artifact_type === artifactType) || null;
    return {
      markdown: pickLatest("markdown_summary"),
      readingList: pickLatest("reading_list"),
      todoDraft: pickLatest("todo_draft"),
    };
  }, [sessionArtifacts]);

  const copyText = async (content: string) => {
    if (!content) return;
    try {
      await navigator.clipboard.writeText(content);
      setTaskMessage(t("common.copied", "已复制"));
    } catch {
      setTaskMessage(t("summary.task.failed", "导出任务失败，已回退本地生成结果。"));
    }
  };

  const ensureTodoDraftContent = async (): Promise<string> => {
    if (todoDraft.trim()) {
      return todoDraft;
    }
    const fallback = fallbackTodoDraft(t);
    setRunningTask("export_todo_draft");
    setTaskMessage(
      t("summary.task.runningWorkbuddy", "正在整理，请稍候。"),
    );
    try {
      const { task, channel } = await runTask("export_todo_draft");
      const content = String(task.output_payload?.content || "");
      const resolved = content || fallback;
      setTodoDraft(resolved);
      setTaskContexts((current) => ({
        ...current,
        export_todo_draft: parseTaskBriefingContext(task.output_payload),
      }));
      setTaskMessage(
        channel === "workbuddy"
          ? t("summary.task.doneWorkbuddy", "已完成导出。")
          : t("summary.task.doneDirectFallback", "已完成导出。"),
      );
      return resolved;
    } catch {
      setTodoDraft(fallback);
      setTaskMessage(t("summary.task.failed", "导出失败，已展示可用的本地结果。"));
      return fallback;
    } finally {
      setRunningTask("");
    }
  };

  const handleImportTodoToCalendar = async () => {
    if (!metrics.sessionId || calendarImporting) {
      return;
    }
    setCalendarImporting(true);
    try {
      const todoContent = await ensureTodoDraftContent();
      const preview = await previewTodoCalendarImport(metrics.sessionId, {
        output_language: preferences.language,
        todo_markdown: todoContent,
      });
      const previewLines = preview.events
        .slice(0, 3)
        .map((event, index) => {
          const start = new Date(event.start_time);
          const timeText = Number.isNaN(start.getTime())
            ? event.start_time
            : start.toLocaleString(preferences.language, {
                month: "2-digit",
                day: "2-digit",
                hour: "2-digit",
                minute: "2-digit",
                hour12: false,
              });
          return `${index + 1}. ${event.title} · ${timeText}`;
        })
        .join("\n");
      const confirmed = window.confirm(
        `${t("summary.calendar.confirmTitle", "确认导入到 Mac 日历？")}\n\n` +
          `${t("summary.calendar.confirmCalendar", "日历")}: ${preview.calendar_name}\n` +
          `${t("summary.calendar.confirmCount", "待办数量")}: ${preview.task_count}\n\n` +
          `${previewLines}` +
          (preview.task_count > 3
            ? `\n${t("summary.calendar.moreItems", "其余事项将在导入后按顺序创建。")}`
            : ""),
      );
      if (!confirmed) {
        setTaskMessage(t("summary.calendar.cancelled", "已取消导入 Mac 日历。"));
        return;
      }
      const result = await importTodoCalendar(metrics.sessionId, {
        output_language: preferences.language,
        todo_markdown: preview.markdown,
        calendar_name: preview.calendar_name,
      });
      setTaskMessage(
        `${t("summary.calendar.done", "已导入 Mac 日历")} · ${result.imported_count} ${t("common.items", "条")}`,
      );
    } catch (error) {
      const message =
        error instanceof Error && error.message
          ? error.message
          : t("summary.calendar.failed", "导入 Mac 日历失败。");
      setTaskMessage(message);
    } finally {
      setCalendarImporting(false);
    }
  };

  const buildAssistantInputPayload = () => {
    if (!assistantResult) {
      return undefined;
    }
    if (assistantResult.sessionId && metrics.sessionId && assistantResult.sessionId !== metrics.sessionId) {
      return undefined;
    }
    return {
      action_key: assistantResult.actionKey,
      action_title: assistantResult.actionTitle,
      channel_used: assistantResult.channelUsed,
      task_type: assistantResult.taskType,
      message: assistantResult.message,
      content: assistantResult.content,
      created_at: assistantResult.createdAt,
    };
  };

  const pollTaskResult = async (taskId: string): Promise<ApiTask> => {
    for (let index = 0; index < 20; index += 1) {
      const task = await getTask(taskId);
      if (task.status === "done") {
        return task;
      }
      if (task.status === "failed") {
        throw new Error(task.error_message || "Task failed");
      }
      await wait(1000);
    }
    throw new Error("Task polling timeout");
  };

  const runTaskViaWorkBuddy = async (taskType: TaskType): Promise<ApiTask> => {
    const sessionId = taskSessionId(taskType, metrics.sessionId);
    if (taskNeedsSession(taskType) && !sessionId) {
      throw new Error("session id missing");
    }
    const response = await sendWorkBuddyWebhook({
      event_type: "create_task",
      request_id: `summary_${taskType}_${Date.now()}`,
      task_type: taskType,
      session_id: sessionId,
      input_payload: {
        output_language: preferences.language,
        assistant_context: buildAssistantInputPayload(),
      },
    });
    if (!response.accepted || !response.task) {
      throw new Error("workbuddy task missing");
    }
    if (response.task.status === "done") {
      return response.task;
    }
    if (response.task.status === "failed") {
      throw new Error(response.task.error_message || "workbuddy task failed");
    }
    return pollTaskResult(response.task.id);
  };

  const runTaskDirect = async (taskType: TaskType): Promise<ApiTask> => {
    const sessionId = taskSessionId(taskType, metrics.sessionId);
    if (taskNeedsSession(taskType) && !sessionId) {
      throw new Error("session id missing");
    }
    const task = await createTask({
      task_type: taskType,
      session_id: sessionId,
      input_payload: {
        output_language: preferences.language,
        assistant_context: buildAssistantInputPayload(),
      },
    });
    if (task.status === "done") {
      return task;
    }
    return pollTaskResult(task.id);
  };

  const runTask = async (
    taskType: TaskType,
  ): Promise<{ task: ApiTask; channel: TaskChannel }> => {
    try {
      const task = await runTaskViaWorkBuddy(taskType);
      return { task, channel: "workbuddy" };
    } catch {
      const task = await runTaskDirect(taskType);
      return { task, channel: "direct" };
    }
  };

  const executeTask = async (
    taskType: TaskType,
    fallbackContent: string,
    onDone: (content: string) => void,
  ) => {
    if (runningTask) {
      return;
    }
    setRunningTask(taskType);
    setTaskContexts((current) => ({ ...current, [taskType]: null }));
    setTaskMessage(
      t("summary.task.runningWorkbuddy", "正在整理，请稍候。"),
    );
    try {
      const { task, channel } = await runTask(taskType);
      const content = String(task.output_payload?.content || fallbackContent);
      onDone(content || fallbackContent);
      setTaskContexts((current) => ({
        ...current,
        [taskType]: parseTaskBriefingContext(task.output_payload),
      }));
      if (metrics.sessionId) {
        try {
          const artifacts = await getSessionArtifacts(metrics.sessionId);
          setSessionArtifacts(artifacts);
        } catch {
          // keep current artifact snapshots if refresh fails
        }
      }
      setTaskMessage(
        channel === "workbuddy"
          ? t("summary.task.doneWorkbuddy", "已完成导出。")
          : t("summary.task.doneDirectFallback", "已完成导出。"),
      );
    } catch {
      onDone(fallbackContent);
      setTaskMessage(t("summary.task.failed", "导出失败，已展示可用的本地结果。"));
    } finally {
      setRunningTask("");
    }
  };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <MetricCard label={t("summary.metric.duration", "专注时长")} value={formatDuration(metrics.durationMinutes, t)} />
        <MetricCard label={t("summary.metric.newContent", "新增内容数")} value={`${metrics.newContentCount}`} />
        <MetricCard label={t("summary.metric.deepRead", "推荐深读数")} value={`${metrics.deepReadCount}`} />
        <MetricCard label={t("summary.metric.later", "稍后读数")} value={`${metrics.laterCount}`} />
        <MetricCard label={t("summary.metric.skip", "可忽略数")} value={`${metrics.ignorableCount}`} />
      </div>

      {hasBatchSnapshot(wechatBatchStatus) ? (
        <div className="af-glass rounded-[30px] p-5 md:p-6">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="af-kicker">{t("focus.collectorKicker", "公众号采集")}</p>
              <p className="mt-2 text-base font-semibold text-[var(--af-text-primary)]">
                {wechatBatchStatus?.running
                  ? t("focus.collectorRunning", "正在静默扫描最新文章")
                  : t("focus.collectorLatest", "最近一轮采集结果")}
              </p>
              <p className="mt-1 text-sm text-[var(--af-text-tertiary)]">
                {t("focus.collectorSubmitted", "累计入队")} {wechatBatchStatus?.submitted || 0} {t("common.items", "条")}
              </p>
            </div>
            <div className="rounded-full border border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-3 py-1 text-xs font-medium text-[var(--af-info)]">
              {getBatchProgress(wechatBatchStatus)}%
            </div>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-[var(--af-surface-inset)]">
            <div
              className="h-full rounded-full bg-[var(--af-info)] transition-all duration-500"
              style={{ width: `${getBatchProgress(wechatBatchStatus)}%` }}
            />
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-4">
            <MetricCard label={t("focus.collectorSubmittedNew", "真正新增")} value={`${wechatBatchStatus?.submitted_new || 0}`} />
            <MetricCard label={t("focus.collectorDedup", "历史去重")} value={`${wechatBatchStatus?.deduplicated_existing || 0}`} />
            <MetricCard label={t("focus.collectorSeen", "已跳过")} value={`${wechatBatchStatus?.skipped_seen || 0}`} />
            <MetricCard label={t("focus.collectorFailed", "失败")} value={`${wechatBatchStatus?.failed || 0}`} />
          </div>
          {wechatBatchStatus?.route_quality ? (
            <div
              className={`mt-3 rounded-3xl border px-4 py-3 text-sm ${
                wechatBatchStatus.route_quality.route_stability === "good"
                  ? "af-state-panel-success"
                  : wechatBatchStatus.route_quality.route_stability === "poor"
                    ? "af-state-panel-warning"
                    : "border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] text-[var(--af-text-secondary)]"
              }`}
            >
              <div className="flex flex-wrap gap-2 text-[11px]">
                <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1">
                  链接优先 {wechatBatchStatus.route_quality.url_first_share}%
                </span>
                <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1">
                  补录 {wechatBatchStatus.route_quality.ocr_share}%
                </span>
                <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1">
                  自动采集 {wechatBatchStatus.route_quality.accessibility_hit_rate}%
                </span>
              </div>
              <p className="mt-2 text-xs leading-5">{wechatBatchStatus.route_quality.recommendation}</p>
            </div>
          ) : null}
          {wechatBatchStatus?.last_message ? (
            <p className="mt-3 text-xs text-[var(--af-text-tertiary)]">
              {t("focus.collectorLastMessage", "状态")}：{wechatBatchStatus.last_message}
            </p>
          ) : null}
        </div>
      ) : null}

      {latestSessionItems.length > 0 ? (
        <div className="af-glass rounded-[30px] p-5 md:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="af-kicker">{t("summary.section.latestNew", "本轮新增卡片")}</p>
              <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">
                {t(
                  "summary.latestNewHint",
                  "优先展示最近一轮采集到的新内容，可直接进入详情继续判断。",
                )}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="rounded-full border border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] font-semibold text-[var(--af-info)]">
                {filteredLatestSessionItems.length}/{latestSessionItems.length} {t("common.items", "条")}
              </span>
              <Link
                href="/collector#latest-run"
                className="inline-flex items-center gap-1 rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-1.5 text-[11px] font-semibold text-[var(--af-text-secondary)] transition hover:bg-[var(--af-surface-hover)]"
              >
                <AppIcon name="collector" className="h-3.5 w-3.5" />
                {t("summary.latestNewCollector", "查看采集器")}
              </Link>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {latestSourceOptions.map((source) => {
              const active = latestSourceFilter === source;
              return (
                <button
                  key={source}
                  type="button"
                  onClick={() => setLatestSourceFilter(source)}
                  className={`rounded-full px-3 py-1.5 text-[11px] font-semibold transition ${
                    active
                      ? "border border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] af-chip af-chip-info"
                      : "border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] text-[var(--af-text-tertiary)] hover:bg-[var(--af-surface-hover)]"
                  }`}
                >
                  {source === "all" ? t("summary.filter.allSources", "全部来源") : source}
                </button>
              );
            })}
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {latestActionOptions.map((action) => {
              const active = latestActionFilter === action;
              const label =
                action === "all"
                  ? t("summary.filter.allActions", "全部动作")
                  : action === "deep_read"
                    ? t("action.deep_read", "立即深读")
                    : action === "skip"
                      ? t("action.skip", "可放心忽略")
                      : t("action.later", "稍后精读");
              return (
                <button
                  key={action}
                  type="button"
                  onClick={() => setLatestActionFilter(action)}
                  className={`rounded-full px-3 py-1.5 text-[11px] font-semibold transition ${
                    active
                      ? "border border-[color-mix(in_srgb,var(--af-success)_30%,var(--af-border-subtle))] af-chip af-chip-success"
                      : "border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] text-[var(--af-text-tertiary)] hover:bg-[var(--af-surface-hover)]"
                  }`}
                >
                  {label}
                </button>
              );
            })}
          </div>
          <div className="mt-3 space-y-2.5">
            {filteredLatestSessionItems.map((item) => (
              <Link
                key={item.id}
                href={`/items/${item.id}`}
                className="group block rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-4 py-3 transition hover:-translate-y-0.5 hover:bg-[var(--af-surface-hover)]"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-1 text-sm font-semibold text-[var(--af-text-primary)]">{item.title}</p>
                    <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">{item.source}</p>
                  </div>
                  <span className="shrink-0 rounded-full border border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2.5 py-0.5 text-[11px] font-semibold text-[var(--af-info)]">
                    {item.scoreLabel}
                  </span>
                </div>
                <p className="mt-2 line-clamp-2 text-sm leading-6 text-[var(--af-text-secondary)]">{item.summary}</p>
                <div className="mt-3 flex items-center justify-between gap-3">
                  <span className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px] font-semibold text-[var(--af-text-tertiary)]">
                    {item.actionLabel}
                  </span>
                  <div className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--af-info)]">
                    <AppIcon name="external" className="h-3.5 w-3.5" />
                    {t("summary.latestNewOpen", "打开详情")}
                  </div>
                </div>
              </Link>
            ))}
          </div>
          {filteredLatestSessionItems.length === 0 ? (
            <p className="mt-3 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-4 py-3 text-sm text-[var(--af-text-tertiary)]">
              {t("summary.latestNewEmpty", "当前筛选条件下没有匹配的新增卡片。")}
            </p>
          ) : null}
        </div>
      ) : null}

      {researchRecommendations.length > 0 ? (
        <div className="af-glass rounded-[30px] p-5 md:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="af-kicker">{t("summary.section.research", "推荐研报")}</p>
              <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">
                {t(
                  "summary.researchHint",
                  "带入最近的研报和行动卡，继续推进后续动作。",
                )}
              </p>
            </div>
            <Link
              href="/research"
              className="inline-flex items-center gap-1 rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-1.5 text-[11px] font-semibold text-[var(--af-text-secondary)] transition hover:bg-[var(--af-surface-hover)]"
            >
              <AppIcon name="spark" className="h-3.5 w-3.5" />
              {t("summary.researchOpen", "打开研报中心")}
            </Link>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-3">
            {researchRecommendations.map((entry) => (
              <Link
                key={entry.id}
                href={`/knowledge/${entry.id}`}
                className="group block rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4 transition hover:-translate-y-0.5 hover:bg-[var(--af-surface-hover)]"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <h4 className="min-w-0 flex-1 text-base font-semibold leading-7 text-[var(--af-text-primary)]">
                    {entry.title}
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {entry.isFocusReference ? (
                      <span className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] font-semibold text-[var(--af-info)]">
                        {t("inbox.researchHistoryFocus", "Focus 参考")}
                      </span>
                    ) : null}
                    {entry.collectionName ? (
                      <span className="rounded-full bg-[var(--af-surface-muted)] px-2.5 py-1 text-[11px] font-semibold text-[var(--af-text-secondary)]">
                        {entry.collectionName}
                      </span>
                    ) : null}
                  </div>
                </div>
                <p className="mt-3 line-clamp-3 text-sm leading-6 text-[var(--af-text-secondary)]">{entry.summary}</p>

                {(entry.scopeRegions.length ||
                  entry.scopeIndustries.length ||
                  entry.scopeClients.length ||
                  entry.topicAnchors.length ||
                  entry.matchedThemes.length ||
                  entry.filteredOldSourceCount > 0 ||
                  entry.filteredRegionConflictCount > 0 ||
                  entry.uniqueDomainCount > 0 ||
                  entry.normalizedEntityCount > 0 ||
                  entry.candidateProfileCompanies.length ||
                  entry.candidateProfileHitCount > 0) ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <span
                      className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${
                        entry.evidenceMode === "strong"
                          ? "af-chip af-chip-success"
                          : entry.evidenceMode === "provisional"
                            ? "af-chip af-chip-warning"
                            : "af-chip"
                      }`}
                    >
                      {entry.evidenceMode === "strong" ? "强证据" : entry.evidenceMode === "provisional" ? "可用初版" : "待核实"}
                    </span>
                    <span className="rounded-full bg-[var(--af-surface-muted)] px-2.5 py-1 text-[11px] text-[var(--af-text-secondary)]">
                      检索质量 {entry.retrievalQuality === "high" ? "高价值" : entry.retrievalQuality === "medium" ? "普通价值" : "低价值"}
                    </span>
                    <span className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-info)]">
                      官方源 {entry.officialSourcePercent}%
                    </span>
                    {entry.scopeRegions.map((value) => (
                      <span key={`${entry.id}-scope-region-${value}`} className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-info)]">
                        区域 · {value}
                      </span>
                    ))}
                    {entry.scopeIndustries.map((value) => (
                      <span key={`${entry.id}-scope-industry-${value}`} className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-info)]">
                        领域 · {value}
                      </span>
                    ))}
                    {entry.scopeClients.map((value) => (
                      <span key={`${entry.id}-scope-client-${value}`} className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-info)]">
                        公司 · {value}
                      </span>
                    ))}
                    {entry.topicAnchors.map((value) => (
                      <span key={`${entry.id}-anchor-${value}`} className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-info)]">
                        {value}
                      </span>
                    ))}
                    {entry.matchedThemes.map((value) => (
                      <span key={`${entry.id}-theme-${value}`} className="rounded-full bg-[color-mix(in_srgb,var(--af-success)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-success)]">
                        {value}
                      </span>
                    ))}
                    {entry.filteredOldSourceCount > 0 ? (
                      <span className="rounded-full bg-[var(--af-surface-muted)] px-2.5 py-1 text-[11px] text-[var(--af-text-tertiary)]">
                        过滤旧来源 {entry.filteredOldSourceCount}
                      </span>
                    ) : null}
                    {entry.filteredRegionConflictCount > 0 ? (
                      <span className="rounded-full bg-[color-mix(in_srgb,var(--af-danger)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-danger)]">
                        区域冲突 {entry.filteredRegionConflictCount}
                      </span>
                    ) : null}
                    {entry.uniqueDomainCount > 0 ? (
                      <span className="rounded-full bg-[var(--af-surface-muted)] px-2.5 py-1 text-[11px] text-[var(--af-text-tertiary)]">
                        来源 {entry.uniqueDomainCount}
                      </span>
                    ) : null}
                    {entry.normalizedEntityCount > 0 ? (
                      <span className="rounded-full bg-[color-mix(in_srgb,var(--af-success)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-success)]">
                        实体校正 {entry.normalizedEntityCount}
                      </span>
                    ) : null}
                    {entry.correctiveTriggered ? (
                      <span className="rounded-full bg-[color-mix(in_srgb,var(--af-warning)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-warning)]">
                        已补充核验
                      </span>
                    ) : null}
                    {entry.candidateProfileCompanies.length ? (
                      <span className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-info)]">
                        建议核验公司 {entry.candidateProfileCompanies.length}
                      </span>
                    ) : null}
                    {entry.candidateProfileHitCount > 0 ? (
                      <span className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-info)]">
                        公开来源 {entry.candidateProfileHitCount}
                      </span>
                    ) : null}
                    {entry.candidateProfileOfficialHitCount > 0 ? (
                      <span className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-info)]">
                        其中官方源 {entry.candidateProfileOfficialHitCount}
                      </span>
                    ) : null}
                    {entry.candidateProfileCompanies.map((value) => (
                      <span key={`${entry.id}-candidate-profile-${value}`} className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-info)]">
                        候选公司 · {value}
                      </span>
                    ))}
                    {entry.candidateProfileSourceLabels.map((value) => (
                      <span key={`${entry.id}-candidate-profile-source-${value}`} className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-info)]">
                        {value}
                      </span>
                    ))}
                  </div>
                ) : null}

                {entry.actionCards.length ? (
                  <div className="mt-4 grid grid-cols-1 gap-2">
                    {entry.actionCards.map((card) => (
                        <div key={`${entry.id}-${card.title}`} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
                          <div className="break-words text-sm font-semibold leading-6 text-[var(--af-text-primary)]">{card.title}</div>
                          <div className="mt-2 grid grid-cols-1 gap-1.5 break-words text-[11px] text-[var(--af-text-tertiary)]">
                          {card.targetPersona ? (
                            <div>
                              <span className="font-semibold text-[var(--af-text-secondary)]">{t("research.actionTarget", "优先对象")}：</span>
                              {card.targetPersona}
                            </div>
                          ) : null}
                          {card.executionWindow ? (
                            <div>
                              <span className="font-semibold text-[var(--af-text-secondary)]">{t("research.actionWindow", "执行窗口")}：</span>
                              {card.executionWindow}
                            </div>
                          ) : null}
                          {card.deliverable ? (
                            <div>
                              <span className="font-semibold text-[var(--af-text-secondary)]">{t("research.actionDeliverable", "产出物")}：</span>
                              {card.deliverable}
                            </div>
                          ) : null}
                        </div>
                        {card.phases.length ? (
                          <div className="mt-3 grid grid-cols-1 gap-2">
                            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">
                              {t("research.actionTimeline", "推进节奏")}
                            </div>
                            <div className="grid grid-cols-1 gap-2">
                              {card.phases.map((phase) => (
                                <div
                                  key={`${entry.id}-${card.title}-${phase.label}-${phase.content}`}
                                  className="min-w-0 overflow-hidden rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2.5"
                                >
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <span className="rounded-full bg-[var(--af-text-primary)] px-2.5 py-1 text-[11px] font-medium text-[var(--af-text-inverse)]">
                                      {phase.label}
                                    </span>
                                    {phase.horizon ? (
                                      <span className="text-[11px] font-medium text-[var(--af-text-tertiary)]">{phase.horizon}</span>
                                    ) : null}
                                  </div>
                                  <div className="mt-2 min-w-0 break-words whitespace-pre-wrap text-xs leading-5 text-[var(--af-text-secondary)] [overflow-wrap:anywhere]">
                                    {phase.content}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                ) : null}

                {(entry.topTargets.length || entry.topCompetitors.length || entry.topPartners.length) ? (
                  <div className="mt-4 space-y-2">
                    {entry.topTargets.length ? (
                      <div>
                        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-info)]">
                          {t("research.topTargets", "高价值甲方 Top 3")}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {entry.topTargets.map((value) => (
                            <span key={`${entry.id}-buyer-${value}`} className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-info)]">
                              {value}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    {entry.topCompetitors.length ? (
                      <div>
                        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-warning)]">
                          {t("research.topCompetitors", "高威胁竞品 Top 3")}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {entry.topCompetitors.map((value) => (
                            <span key={`${entry.id}-competitor-${value}`} className="rounded-full bg-[color-mix(in_srgb,var(--af-warning)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-warning)]">
                              {value}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    {entry.topPartners.length ? (
                      <div>
                        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-success)]">
                          {t("research.topPartners", "高影响力生态伙伴 Top 3")}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {entry.topPartners.map((value) => (
                            <span key={`${entry.id}-partner-${value}`} className="rounded-full bg-[color-mix(in_srgb,var(--af-success)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] text-[var(--af-success)]">
                              {value}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : null}

                <div className="mt-4 flex items-center justify-between gap-3 text-[11px] text-[var(--af-text-tertiary)]">
                  <span>{new Date(entry.createdAt).toLocaleString()}</span>
                  <span className="inline-flex items-center gap-1 font-semibold text-[var(--af-info)]">
                    <AppIcon name="external" className="h-3.5 w-3.5" />
                    {t("summary.latestNewOpen", "打开详情")}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      ) : null}

      <div className="af-glass rounded-[30px] p-5 md:p-6">
        <div className="flex items-center justify-between gap-3">
          <p className="af-kicker">{t("summary.section.deepReads", "本次推荐深读")}</p>
          <span className="text-xs text-[var(--af-text-tertiary)]">
            {t("summary.dataSource", "数据源")}：
            {sessionSource === "api"
              ? t("summary.dataSource.api", "实时记录")
              : t("summary.dataSource.local", "本地汇总")}
          </span>
        </div>
        {recommendedDeepReads.length > 0 ? (
          <div className="mt-3 space-y-2.5">
            {recommendedDeepReads.map((item, idx) => (
              <div key={item.id} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-4 py-3">
                <div className="flex items-start justify-between gap-3">
                  <p className="line-clamp-1 text-sm font-semibold text-[var(--af-text-primary)]">
                    {idx + 1}. {item.title}
                  </p>
                  <span className="shrink-0 rounded-full border border-[color-mix(in_srgb,var(--af-success)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-success)_14%,var(--af-surface-muted))] px-2.5 py-0.5 text-[11px] font-semibold text-[var(--af-success)]">
                    {item.scoreLabel}
                  </span>
                </div>
                <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">{item.source}</p>
                <p className="mt-1 line-clamp-2 text-sm leading-6 text-[var(--af-text-secondary)]">{item.summary}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-3 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-4 py-3 text-sm text-[var(--af-text-tertiary)]">
            {t("summary.emptyDeepReads", "暂无深读推荐，结束一轮 Focus 后会在这里显示优先阅读项。")}
          </p>
        )}
      </div>

      {assistantResult ? (
        <div className="af-glass rounded-[30px] p-5 md:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="af-kicker">{t("summary.assistant.title", "专注助手")}</p>
              <p className="mt-2 text-lg font-semibold tracking-[-0.02em] text-[var(--af-text-primary)]">
                {assistantResult.actionTitle}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full border border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--af-info)]">
                {assistantResult.channelUsed === "workbuddy"
                  ? t("summary.assistant.workbuddy", "已完成")
                  : t("summary.assistant.direct", "已完成")}
              </span>
              <span className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px] font-semibold tracking-[0.14em] text-[var(--af-text-tertiary)]">
                {formatAssistantTime(assistantResult.createdAt, preferences.language)}
              </span>
            </div>
          </div>
          <p className="mt-3 text-sm leading-6 text-[var(--af-text-tertiary)]">
            {assistantResult.message ||
              t(
                "summary.assistant.subtitle",
                "最近一次助手结果已保存到本轮总结。",
              )}
          </p>
          <div className="mt-3 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <p className="af-kicker">{t("summary.assistant.output", "结果摘要")}</p>
              {assistantResult.content ? (
                <button
                  type="button"
                  onClick={() => {
                    void copyText(assistantResult.content);
                  }}
                  className="inline-flex items-center gap-1 rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px] font-semibold text-[var(--af-text-tertiary)]"
                >
                  <AppIcon name="copy" className="h-3.5 w-3.5" />
                  {t("common.copy", "复制")}
                </button>
              ) : null}
            </div>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[var(--af-text-secondary)]">
              {assistantResult.content ||
                t("summary.assistant.noOutput", "本次没有可展示的结果。")}
            </p>
          </div>
          {assistantHistory.length > 1 ? (
            <div className="mt-3 border-t border-[var(--af-border-subtle)] pt-3">
              <p className="af-kicker">{t("summary.assistant.history", "最近执行")}</p>
              <div className="mt-2 space-y-2">
                {assistantHistory.slice(1, 4).map((entry) => (
                  <button
                    key={`${entry.createdAt}-${entry.actionKey}`}
                    type="button"
                    onClick={() => {
                      setAssistantResult(entry);
                    }}
                    className="flex w-full items-start justify-between gap-3 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-4 py-3 text-left transition hover:bg-[var(--af-surface-hover)]"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-[var(--af-text-primary)]">{entry.actionTitle}</p>
                      <p className="mt-1 line-clamp-2 text-xs leading-5 text-[var(--af-text-tertiary)]">
                        {entry.message ||
                          entry.content ||
                          t("summary.assistant.noOutput", "本次没有可展示的结果。")}
                      </p>
                    </div>
                    <span className="shrink-0 text-[11px] font-medium text-[var(--af-text-tertiary)]">
                      {formatAssistantTime(entry.createdAt, preferences.language)}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="af-glass rounded-[30px] p-5 md:p-6">
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => {
              void executeTask(
                "export_markdown_summary",
                fallbackMarkdown(metrics, t, preferences.language),
                setMarkdown,
              );
            }}
            disabled={Boolean(runningTask)}
            className="af-btn af-btn-primary disabled:cursor-not-allowed disabled:opacity-60"
          >
            <WorkBuddyMark size={14} />
            {runningTask === "export_markdown_summary"
              ? t("summary.btn.generating", "生成中...")
              : t("summary.btn.markdown", "整理总结")}
          </button>
          <button
            type="button"
            onClick={() => {
              void executeTask("export_reading_list", fallbackReadingList(t), setReadingList);
            }}
            disabled={Boolean(runningTask)}
            className="af-btn af-btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
          >
            <WorkBuddyMark size={14} />
            {runningTask === "export_reading_list"
              ? t("summary.btn.generating", "生成中...")
              : t("summary.btn.readingList", "整理稍后读清单")}
          </button>
          <button
            type="button"
            onClick={() => {
              void executeTask("export_todo_draft", fallbackTodoDraft(t), setTodoDraft);
            }}
            disabled={Boolean(runningTask)}
            className="af-btn af-btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
          >
            <WorkBuddyMark size={14} />
            {runningTask === "export_todo_draft"
              ? t("summary.btn.generating", "生成中...")
              : t("summary.btn.todoDraft", "整理待办草稿")}
          </button>
          <button
            type="button"
            onClick={() => {
              void executeTask("export_exec_brief", fallbackExecBrief(t), setExecBrief);
            }}
            disabled={Boolean(runningTask)}
            className="af-btn af-btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
          >
            <WorkBuddyMark size={14} />
            {runningTask === "export_exec_brief"
              ? t("summary.btn.generating", "生成中...")
              : t("summary.btn.execBrief", "生成老板简报")}
          </button>
          <button
            type="button"
            onClick={() => {
              void executeTask("export_sales_brief", fallbackSalesBrief(t), setSalesBrief);
            }}
            disabled={Boolean(runningTask)}
            className="af-btn af-btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
          >
            <WorkBuddyMark size={14} />
            {runningTask === "export_sales_brief"
              ? t("summary.btn.generating", "生成中...")
              : t("summary.btn.salesBrief", "生成销售 Brief")}
          </button>
          <button
            type="button"
            onClick={() => {
              void executeTask("export_outreach_draft", fallbackOutreachDraft(t), setOutreachDraft);
            }}
            disabled={Boolean(runningTask)}
            className="af-btn af-btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
          >
            <WorkBuddyMark size={14} />
            {runningTask === "export_outreach_draft"
              ? t("summary.btn.generating", "生成中...")
              : t("summary.btn.outreachDraft", "生成外联草稿")}
          </button>
          <button
            type="button"
            onClick={() => {
              void executeTask("export_watchlist_digest", watchlistDigestFromHighlights(watchlistHighlights, t), setWatchlistDigest);
            }}
            disabled={Boolean(runningTask)}
            className="af-btn af-btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
          >
            <WorkBuddyMark size={14} />
            {runningTask === "export_watchlist_digest"
              ? t("summary.btn.generating", "生成中...")
              : t("summary.btn.watchlistDigest", "生成监控摘要")}
          </button>
        </div>
        {loadingSession ? (
          <p className="mt-3 text-xs text-[var(--af-text-tertiary)]">
            {t("summary.syncing", "正在读取本轮记录...")}
          </p>
        ) : null}
        <p className="mt-3 text-xs text-[var(--af-text-tertiary)]">
          {t(
            "summary.task.routeHint",
            "结果会优先使用最新记录，失败时保留本地可用内容。",
          )}
        </p>
        {taskMessage ? <p className="mt-3 text-xs text-[var(--af-text-tertiary)]">{taskMessage}</p> : null}

        <OutputBlock
          title={t("summary.block.markdown", "本轮总结")}
          content={markdown}
          emptyText={t("summary.block.emptyMarkdown", "点击“整理总结”后显示结果。")}
          onCopy={copyText}
          copyLabel={t("common.copy", "复制")}
          artifact={latestArtifactsByType.markdown}
        />
        <OutputBlock
          title={t("summary.block.readingList", "稍后读清单")}
          content={readingList}
          emptyText={t("summary.block.emptyReadingList", "点击“整理稍后读清单”后显示结果。")}
          onCopy={copyText}
          copyLabel={t("common.copy", "复制")}
          artifact={latestArtifactsByType.readingList}
        />
        <OutputBlock
          title={t("summary.block.todoDraft", "待办草稿")}
          content={todoDraft}
          emptyText={t("summary.block.emptyTodoDraft", "点击“整理待办草稿”后显示结果。")}
          onCopy={copyText}
          copyLabel={t("common.copy", "复制")}
          artifact={latestArtifactsByType.todoDraft}
          extraActions={
            <button
              type="button"
              onClick={() => {
                void handleImportTodoToCalendar();
              }}
              disabled={calendarImporting || Boolean(runningTask) || !metrics.sessionId}
              className="inline-flex items-center gap-1 rounded-full border border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] font-semibold text-[var(--af-info)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              <AppIcon name="calendar" className="h-3.5 w-3.5" />
              {calendarImporting
                ? t("summary.calendar.importing", "导入中...")
                : t("summary.calendar.import", "导入 Mac 日历")}
            </button>
          }
        />
        <OutputBlock
          title={t("summary.block.execBrief", "老板简报")}
          content={execBrief}
          emptyText={t("summary.block.emptyExecBrief", "点击“生成老板简报”后显示结果。")}
          onCopy={copyText}
          copyLabel={t("common.copy", "复制")}
          contextBlock={<TaskBriefingContextCard context={taskContexts.export_exec_brief || null} title="简报依据" />}
        />
        <OutputBlock
          title={t("summary.block.salesBrief", "销售 Brief")}
          content={salesBrief}
          emptyText={t("summary.block.emptySalesBrief", "点击“生成销售 Brief”后显示结果。")}
          onCopy={copyText}
          copyLabel={t("common.copy", "复制")}
          contextBlock={<TaskBriefingContextCard context={taskContexts.export_sales_brief || null} title="账户推进参考" />}
        />
        <OutputBlock
          title={t("summary.block.outreachDraft", "外联草稿")}
          content={outreachDraft}
          emptyText={t("summary.block.emptyOutreachDraft", "点击“生成外联草稿”后显示结果。")}
          onCopy={copyText}
          copyLabel={t("common.copy", "复制")}
          contextBlock={<TaskBriefingContextCard context={taskContexts.export_outreach_draft || null} title="外联准备" compact />}
        />
        <OutputBlock
          title={t("summary.block.watchlistDigest", "监控摘要")}
          content={watchlistDigest}
          emptyText={t("summary.block.emptyWatchlistDigest", "点击“生成监控摘要”后显示结果。")}
          onCopy={copyText}
          copyLabel={t("common.copy", "复制")}
          contextBlock={<TaskBriefingContextCard context={taskContexts.export_watchlist_digest || null} title="监控参考" compact />}
        />
        <div className="mt-4">
          <p className="af-kicker">{t("summary.block.watchlistPriority", "高优先级监控变化")}</p>
          <div className="mt-3 space-y-3">
            {watchlistHighlights.length ? (
              watchlistHighlights.map((item) => (
                <article key={item.id} className="rounded-3xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap gap-2 text-[11px]">
                        <span
                          className={`rounded-full px-2 py-0.5 ${
                            item.severity === "high"
                              ? "af-chip af-chip-danger"
                              : item.severity === "medium"
                                ? "af-chip af-chip-warning"
                                : "af-chip"
                          }`}
                        >
                          {item.severity === "high" ? "高优先级" : item.severity === "medium" ? "中优先级" : "低优先级"}
                        </span>
                        <span className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2 py-0.5 text-[var(--af-info)]">{item.watchlistName}</span>
                        {item.budgetProbability > 0 ? (
                          <span className="rounded-full bg-[var(--af-surface-elevated)] px-2 py-0.5 text-[var(--af-text-secondary)]">预算概率 {item.budgetProbability}%</span>
                        ) : null}
                      </div>
                      <p className="mt-2 text-sm font-semibold text-[var(--af-text-primary)]">{item.summary}</p>
                      {item.accounts.length ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {item.accounts.map((value) => (
                            <span key={`${item.id}-${value}`} className="rounded-full bg-[var(--af-surface-muted)] px-2.5 py-1 text-[11px] text-[var(--af-text-secondary)]">
                              {value}
                            </span>
                          ))}
                        </div>
                      ) : null}
                      {item.whyNow.length ? (
                        <p className="mt-3 text-sm leading-6 text-[var(--af-text-secondary)]">{item.whyNow.join("；")}</p>
                      ) : null}
                    </div>
                    <span className="text-xs text-[var(--af-text-tertiary)]">{new Date(item.createdAt).toLocaleString()}</span>
                  </div>
                </article>
              ))
            ) : (
              <p className="text-sm text-[var(--af-text-tertiary)]">{t("summary.block.emptyWatchlistPriority", "当前还没有可用的高优先级监控变化。")}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
