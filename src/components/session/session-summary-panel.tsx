"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  createTask,
  getSessionArtifacts,
  getLatestSession,
  getSession,
  getTask,
  importTodoCalendar,
  listKnowledgeEntries,
  previewTodoCalendarImport,
  sendWorkBuddyWebhook,
  getWechatAgentBatchStatus,
} from "@/lib/api";
import type {
  ApiKnowledgeEntry,
  ApiResearchActionCard,
  ApiResearchReport,
  ApiSessionArtifact,
  ApiSession,
  ApiSessionItem,
  WechatAgentBatchStatus,
} from "@/lib/api";
import {
  readFocusAssistantHistory,
  readLatestFocusAssistantResult,
  type StoredFocusAssistantResult,
} from "@/lib/focus-assistant-storage";
import type { SessionMetrics } from "@/lib/mock-data";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { AppIcon } from "@/components/ui/app-icon";
import { WorkBuddyMark } from "@/components/ui/workbuddy-mark";

const SESSION_ID_KEY = "anti_fomo_session_id";

interface SessionSummaryPanelProps {
  metrics: SessionMetrics;
}

type TaskType =
  | "export_markdown_summary"
  | "export_reading_list"
  | "export_todo_draft"
  | "export_exec_brief"
  | "export_sales_brief"
  | "export_outreach_draft"
  | "export_watchlist_digest";
type SessionSource = "local" | "api";
type TaskChannel = "workbuddy" | "direct";

interface RecommendedDeepReadItem {
  id: string;
  title: string;
  source: string;
  summary: string;
  scoreLabel: string;
}

interface LatestSessionItem {
  id: string;
  title: string;
  source: string;
  sourceKey: string;
  summary: string;
  scoreLabel: string;
  actionSuggestion: string | null;
  actionLabel: string;
}

interface SessionResearchItem {
  id: string;
  title: string;
  summary: string;
  createdAt: string;
  isFocusReference: boolean;
  collectionName: string | null;
  topTargets: string[];
  topCompetitors: string[];
  topPartners: string[];
  scopeRegions: string[];
  scopeIndustries: string[];
  scopeClients: string[];
  topicAnchors: string[];
  matchedThemes: string[];
  filteredOldSourceCount: number;
  filteredRegionConflictCount: number;
  retrievalQuality: string;
  evidenceMode: string;
  officialSourcePercent: number;
  uniqueDomainCount: number;
  normalizedEntityCount: number;
  correctiveTriggered: boolean;
  candidateProfileCompanies: string[];
  candidateProfileHitCount: number;
  candidateProfileOfficialHitCount: number;
  candidateProfileSourceLabels: string[];
  actionCards: Array<{
    title: string;
    targetPersona: string;
    executionWindow: string;
    deliverable: string;
    phases: Array<{
      label: string;
      horizon: string;
      content: string;
    }>;
  }>;
}

function normalizeStepList(values: unknown): string[] {
  return Array.isArray(values)
    ? values.map((value) => String(value || "").trim()).filter(Boolean)
    : [];
}

function parseActionPhases(steps: string[] | undefined) {
  return normalizeStepList(steps)
    .map((step) => {
      const match = step.match(/^(短期|中期|长期|Short term|Mid term|Long term)(?:（([^）]+)）|\(([^)]+)\))?[:：]\s*(.+)$/i);
      if (!match) {
        return {
          label: "关键动作",
          horizon: "",
          content: step,
        };
      }
      return {
        label: match[1],
        horizon: match[2] || match[3] || "",
        content: match[4],
      };
    })
    .slice(0, 3);
}

function conciseEntityName(value: unknown): string {
  const normalized = String(value || "").trim();
  if (!normalized) return "";
  const primary = normalized.split(/[：:]/)[0]?.trim() || normalized;
  return primary.split(/\s*[·•|｜]\s*/)[0]?.trim() || primary;
}

function normalizeEntityNames(values: unknown): string[] {
  return (Array.isArray(values) ? values : [])
    .map((value) => conciseEntityName(value))
    .filter(Boolean)
    .slice(0, 3);
}

function hasBatchSnapshot(status: WechatAgentBatchStatus | null): boolean {
  if (!status) return false;
  return Boolean(
    status.total_segments ||
      status.finished_at ||
      status.running ||
      status.submitted ||
      status.submitted_new ||
      status.deduplicated_existing ||
      status.skipped_seen ||
      status.failed,
  );
}

function getBatchProgress(status: WechatAgentBatchStatus | null): number {
  if (!status || status.total_segments <= 0) {
    return 0;
  }
  if (status.running) {
    return Math.max(8, Math.min(96, Math.round((Math.max(status.current_segment_index, 1) / status.total_segments) * 100)));
  }
  return status.finished_at ? 100 : 0;
}

function formatDuration(minutes: number, t: (key: string, fallback?: string) => string): string {
  const hours = Math.floor(minutes / 60);
  const restMinutes = minutes % 60;
  if (hours === 0) {
    return `${restMinutes} ${t("common.minutes", "分钟")}`;
  }
  return `${hours} ${t("common.hours", "小时")} ${restMinutes} ${t("common.minutes", "分钟")}`;
}

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function taskNeedsSession(taskType: TaskType): boolean {
  return taskType === "export_markdown_summary" || taskType === "export_todo_draft";
}

function taskSessionId(taskType: TaskType, sessionId?: string): string | undefined {
  if (taskType === "export_watchlist_digest") {
    return undefined;
  }
  return sessionId || (taskNeedsSession(taskType) ? undefined : sessionId);
}

function fallbackMarkdown(
  metrics: SessionMetrics,
  t: (key: string, fallback?: string) => string,
  locale: string,
): string {
  const now = new Date().toLocaleString(locale, { hour12: false });
  return `# ${t("summary.block.markdown", "Markdown 总结")}

- ${t("summary.block.markdown", "Markdown 总结")}: ${now}
- ${t("focus.goal", "本次目标")}: ${metrics.goalText || t("common.notSet", "未设置")}
- ${t("summary.metric.duration", "Session 时长")}: ${formatDuration(metrics.durationMinutes, t)}
- ${t("summary.metric.newContent", "新增内容数")}: ${metrics.newContentCount}
- ${t("summary.metric.deepRead", "推荐深读数")}: ${metrics.deepReadCount}
- ${t("summary.metric.later", "稍后读数")}: ${metrics.laterCount}
- ${t("summary.metric.skip", "可忽略数")}: ${metrics.ignorableCount}`;
}

function fallbackReadingList(t: (key: string, fallback?: string) => string): string {
  return `# ${t("summary.block.readingList", "稍后读清单")}

1. ${t("summary.sample.readA", "高价值内容 A（深读）")}
2. ${t("summary.sample.readB", "行业趋势内容 B（深读）")}
3. ${t("summary.sample.readC", "方法论内容 C（稍后读）")}
4. ${t("summary.sample.readD", "工具更新内容 D（稍后读）")}`;
}

function fallbackTodoDraft(t: (key: string, fallback?: string) => string): string {
  return `# ${t("summary.block.todoDraft", "待办草稿")}

- [ ] ${t("summary.sample.todo1", "先深读 2 条高价值内容并记录要点")}
- [ ] ${t("summary.sample.todo2", "将稍后读内容归入下一个专注时段")}
- [ ] ${t("summary.sample.todo3", "把可忽略内容批量归档")}`;
}

function fallbackExecBrief(t: (key: string, fallback?: string) => string): string {
  return `# ${t("summary.block.execBrief", "老板简报")}

- ${t("summary.metric.deepRead", "推荐深读数")}：优先同步本轮高价值内容和风险变化
- ${t("summary.block.execBriefHighlight", "建议重点")}：今天先看新增甲方、预算节点和 watchlist 变化`;
}

function fallbackSalesBrief(t: (key: string, fallback?: string) => string): string {
  return `# ${t("summary.block.salesBrief", "销售 Brief")}

- ${t("summary.block.salesBriefNext", "下一步")}：围绕深读条目整理拜访提纲
- ${t("summary.block.salesBriefFocus", "跟进重点")}：甲方线索、竞品动作、预算时间窗`;
}

function fallbackOutreachDraft(t: (key: string, fallback?: string) => string): string {
  return `# ${t("summary.block.outreachDraft", "外联草稿")}

您好，结合最近的公开动态，我们整理了几条和您当前项目更相关的观察，适合继续约一个 20 分钟的沟通窗口。`;
}

function fallbackWatchlistDigest(t: (key: string, fallback?: string) => string): string {
  return `# ${t("summary.block.watchlistDigest", "Watchlist Digest")}

- ${t("summary.block.watchlistDigestHint", "当前可先汇总专题刷新和新增风险提示")}。`;
}

function mapSessionToMetrics(session: ApiSession): SessionMetrics {
  return {
    sessionId: session.id,
    durationMinutes: session.duration_minutes,
    goalText: session.goal_text || undefined,
    newContentCount: session.metrics.new_content_count,
    deepReadCount: session.metrics.deep_read_count,
    laterCount: session.metrics.later_count,
    ignorableCount: session.metrics.skip_count,
  };
}

function scoreLabel(
  score: number | null,
  t: (key: string, fallback?: string) => string,
): string {
  if (score === null) return t("summary.score.pending", "评分待补充");
  if (score >= 4.0) return t("summary.score.high", "高价值");
  if (score >= 2.8) return t("summary.score.mid", "中价值");
  return t("summary.score.low", "低价值");
}

function buildRecommendedDeepReads(
  items: ApiSessionItem[],
  t: (key: string, fallback?: string) => string,
): RecommendedDeepReadItem[] {
  const deepReadItems = items.filter((item) => item.action_suggestion === "deep_read");
  return deepReadItems.slice(0, 6).map((item) => ({
    id: item.id,
    title: item.title || t("common.untitled", "未命名内容"),
    source: item.source_domain || t("common.unknownSource", "未知来源"),
    summary: item.short_summary || t("common.noSummary", "暂无摘要"),
    scoreLabel: scoreLabel(item.score_value, t),
  }));
}

function buildLatestSessionItems(
  items: ApiSessionItem[],
  batchStatus: WechatAgentBatchStatus | null,
  t: (key: string, fallback?: string) => string,
): LatestSessionItem[] {
  if (!items.length) {
    return [];
  }
  const itemMap = new Map(items.map((item) => [item.id, item]));
  const matched = (batchStatus?.new_item_ids || [])
    .map((id) => itemMap.get(id))
    .filter((item): item is ApiSessionItem => Boolean(item));
  const fallbackLimit = Math.min(
    items.length,
    Math.max(1, Math.min(4, batchStatus?.submitted_new || items.length)),
  );
  const selected = matched.length > 0 ? matched : items.slice(0, fallbackLimit);
  return selected.slice(0, 4).map((item) => ({
    id: item.id,
    title: item.title || t("common.untitled", "未命名内容"),
    source: item.source_domain || t("common.unknownSource", "未知来源"),
    sourceKey: item.source_domain || "unknown",
    summary: item.short_summary || t("common.noSummary", "暂无摘要"),
    scoreLabel: scoreLabel(item.score_value, t),
    actionSuggestion: item.action_suggestion,
    actionLabel:
      item.action_suggestion === "deep_read"
        ? t("action.deep_read", "立即深读")
        : item.action_suggestion === "skip"
          ? t("action.skip", "可放心忽略")
          : t("action.later", "稍后精读"),
  }));
}

function formatAssistantTime(iso: string, locale: string): string {
  try {
    return new Intl.DateTimeFormat(locale, {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(new Date(iso));
  } catch {
    return iso.slice(0, 16).replace("T", " ");
  }
}

function extractSessionResearchItem(entry: ApiKnowledgeEntry): SessionResearchItem {
  const payload = entry.metadata_payload;
  const typedPayload =
    payload && typeof payload === "object"
      ? (payload as {
          report?: ApiResearchReport;
          action_cards?: ApiResearchActionCard[];
        })
      : null;
  const report = typedPayload?.report;
  const actionCards = Array.isArray(typedPayload?.action_cards) ? typedPayload?.action_cards || [] : [];
  const topTargets = normalizeEntityNames(
    report?.top_target_accounts?.length
      ? report.top_target_accounts.map((item) => item.name)
      : report?.pending_target_candidates?.map((item) => item.name) || [],
  );
  const topCompetitors = normalizeEntityNames(
    report?.top_competitors?.length
      ? report.top_competitors.map((item) => item.name)
      : report?.pending_competitor_candidates?.map((item) => item.name) || [],
  );
  const topPartners = normalizeEntityNames(
    report?.top_ecosystem_partners?.length
      ? report.top_ecosystem_partners.map((item) => item.name)
      : report?.pending_partner_candidates?.map((item) => item.name) || [],
  );
  const summary =
    String(report?.executive_summary || "").trim() ||
    String(entry.content || "")
      .split("\n")
      .map((line) => line.replace(/^#+\s*/, "").replace(/^- /, "").trim())
      .filter(Boolean)[0] ||
    "暂无摘要";
  return {
    id: entry.id,
    title: entry.title,
    summary,
    createdAt: entry.created_at,
    isFocusReference: !!entry.is_focus_reference,
    collectionName: entry.collection_name || null,
    topTargets,
    topCompetitors,
    topPartners,
    scopeRegions: normalizeEntityNames((report?.source_diagnostics as { scope_regions?: string[] } | undefined)?.scope_regions || []),
    scopeIndustries: normalizeEntityNames((report?.source_diagnostics as { scope_industries?: string[] } | undefined)?.scope_industries || []),
    scopeClients: normalizeEntityNames((report?.source_diagnostics as { scope_clients?: string[] } | undefined)?.scope_clients || []),
    topicAnchors: normalizeEntityNames(report?.source_diagnostics?.topic_anchor_terms || []),
    matchedThemes: normalizeEntityNames(report?.source_diagnostics?.matched_theme_labels || []),
    filteredOldSourceCount: Number(report?.source_diagnostics?.filtered_old_source_count || 0),
    filteredRegionConflictCount: Number((report?.source_diagnostics as { filtered_region_conflict_count?: number } | undefined)?.filtered_region_conflict_count || 0),
    retrievalQuality: String(report?.source_diagnostics?.retrieval_quality || "low"),
    evidenceMode: String((report?.source_diagnostics as { evidence_mode?: string } | undefined)?.evidence_mode || "fallback"),
    officialSourcePercent: Math.round(Number(report?.source_diagnostics?.official_source_ratio || 0) * 100),
    uniqueDomainCount: Number(report?.source_diagnostics?.unique_domain_count || 0),
    normalizedEntityCount: Number(report?.source_diagnostics?.normalized_entity_count || 0),
    correctiveTriggered: Boolean((report?.source_diagnostics as { corrective_triggered?: boolean } | undefined)?.corrective_triggered),
    candidateProfileCompanies: normalizeEntityNames((report?.source_diagnostics as { candidate_profile_companies?: string[] } | undefined)?.candidate_profile_companies || []),
    candidateProfileHitCount: Number((report?.source_diagnostics as { candidate_profile_hit_count?: number } | undefined)?.candidate_profile_hit_count || 0),
    candidateProfileOfficialHitCount: Number((report?.source_diagnostics as { candidate_profile_official_hit_count?: number } | undefined)?.candidate_profile_official_hit_count || 0),
    candidateProfileSourceLabels: normalizeEntityNames((report?.source_diagnostics as { candidate_profile_source_labels?: string[] } | undefined)?.candidate_profile_source_labels || []),
    actionCards: actionCards
      .map((card) => ({
        title: String(card.title || "").trim(),
        targetPersona: String(card.target_persona || "").trim(),
        executionWindow: String(card.execution_window || "").trim(),
        deliverable: String(card.deliverable || "").trim(),
        phases: parseActionPhases(card.recommended_steps),
      }))
      .filter((card) => card.title)
      .slice(0, 2),
  };
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
  const [sessionArtifacts, setSessionArtifacts] = useState<ApiSessionArtifact[]>([]);
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
          t("summary.task.localSession", "未能读取实时 Session，当前展示本地汇总。"),
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
      t("summary.task.runningWorkbuddy", "正在通过 WorkBuddy 执行任务，失败会自动回退。"),
    );
    try {
      const { content, channel } = await runTask("export_todo_draft");
      const resolved = content || fallback;
      setTodoDraft(resolved);
      setTaskMessage(
        channel === "workbuddy"
          ? t("summary.task.doneWorkbuddy", "已通过 WorkBuddy 完成导出。")
          : t("summary.task.doneDirectFallback", "WorkBuddy 不可用，已自动回退直连导出。"),
      );
      return resolved;
    } catch {
      setTodoDraft(fallback);
      setTaskMessage(t("summary.task.failed", "导出任务失败，已回退本地生成结果。"));
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

  const pollTaskContent = async (taskId: string): Promise<string> => {
    for (let index = 0; index < 20; index += 1) {
      const task = await getTask(taskId);
      if (task.status === "done") {
        return task.output_payload?.content || "";
      }
      if (task.status === "failed") {
        throw new Error(task.error_message || "Task failed");
      }
      await wait(1000);
    }
    throw new Error("Task polling timeout");
  };

  const runTaskViaWorkBuddy = async (taskType: TaskType): Promise<string> => {
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
      return response.task.output_payload?.content || "";
    }
    if (response.task.status === "failed") {
      throw new Error(response.task.error_message || "workbuddy task failed");
    }
    return pollTaskContent(response.task.id);
  };

  const runTaskDirect = async (taskType: TaskType): Promise<string> => {
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
      return task.output_payload?.content || "";
    }
    return pollTaskContent(task.id);
  };

  const runTask = async (
    taskType: TaskType,
  ): Promise<{ content: string; channel: TaskChannel }> => {
    try {
      const content = await runTaskViaWorkBuddy(taskType);
      return { content, channel: "workbuddy" };
    } catch {
      const content = await runTaskDirect(taskType);
      return { content, channel: "direct" };
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
    setTaskMessage(
      t("summary.task.runningWorkbuddy", "正在通过 WorkBuddy 执行任务，失败会自动回退。"),
    );
    try {
      const { content, channel } = await runTask(taskType);
      onDone(content || fallbackContent);
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
          ? t("summary.task.doneWorkbuddy", "已通过 WorkBuddy 完成导出。")
          : t("summary.task.doneDirectFallback", "WorkBuddy 不可用，已自动回退直连导出。"),
      );
    } catch {
      onDone(fallbackContent);
      setTaskMessage(t("summary.task.failed", "导出任务失败，已回退本地生成结果。"));
    } finally {
      setRunningTask("");
    }
  };

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <MetricCard label={t("summary.metric.duration", "Session 时长")} value={formatDuration(metrics.durationMinutes, t)} />
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
              <p className="mt-2 text-base font-semibold text-slate-900">
                {wechatBatchStatus?.running
                  ? t("focus.collectorRunning", "正在静默扫描最新文章")
                  : t("focus.collectorLatest", "最近一轮采集结果")}
              </p>
              <p className="mt-1 text-sm text-slate-500">
                {t("focus.collectorSubmitted", "累计入队")} {wechatBatchStatus?.submitted || 0} {t("common.items", "条")}
              </p>
            </div>
            <div className="rounded-full border border-sky-200/80 bg-sky-50/80 px-3 py-1 text-xs font-medium text-sky-700">
              {getBatchProgress(wechatBatchStatus)}%
            </div>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200/80">
            <div
              className="h-full rounded-full bg-gradient-to-r from-sky-400 via-blue-500 to-cyan-400 transition-all duration-500"
              style={{ width: `${getBatchProgress(wechatBatchStatus)}%` }}
            />
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-4">
            <MetricCard label={t("focus.collectorSubmittedNew", "真正新增")} value={`${wechatBatchStatus?.submitted_new || 0}`} />
            <MetricCard label={t("focus.collectorDedup", "历史去重")} value={`${wechatBatchStatus?.deduplicated_existing || 0}`} />
            <MetricCard label={t("focus.collectorSeen", "已跳过")} value={`${wechatBatchStatus?.skipped_seen || 0}`} />
            <MetricCard label={t("focus.collectorFailed", "失败")} value={`${wechatBatchStatus?.failed || 0}`} />
          </div>
          {wechatBatchStatus?.last_message ? (
            <p className="mt-3 text-xs text-slate-500">
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
              <p className="mt-2 text-sm text-slate-500">
                {t(
                  "summary.latestNewHint",
                  "优先展示最近一轮采集命中的新卡片，可直接进入详情继续判断。",
                )}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="rounded-full border border-sky-200/80 bg-sky-50/80 px-2.5 py-1 text-[11px] font-semibold text-sky-700">
                {filteredLatestSessionItems.length}/{latestSessionItems.length} {t("common.items", "条")}
              </span>
              <Link
                href="/collector#latest-run"
                className="inline-flex items-center gap-1 rounded-full border border-white/85 bg-white/75 px-3 py-1.5 text-[11px] font-semibold text-slate-600 transition hover:bg-white/90"
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
                      ? "border border-sky-200/85 bg-sky-50 text-sky-700"
                      : "border border-white/85 bg-white/70 text-slate-500 hover:bg-white/90"
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
                      ? "border border-emerald-200/85 bg-emerald-50 text-emerald-700"
                      : "border border-white/85 bg-white/70 text-slate-500 hover:bg-white/90"
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
                className="group block rounded-2xl border border-white/85 bg-white/60 px-4 py-3 transition hover:-translate-y-0.5 hover:bg-white/75"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-1 text-sm font-semibold text-slate-900">{item.title}</p>
                    <p className="mt-1 text-xs text-slate-500">{item.source}</p>
                  </div>
                  <span className="shrink-0 rounded-full border border-sky-200/85 bg-sky-50 px-2.5 py-0.5 text-[11px] font-semibold text-sky-700">
                    {item.scoreLabel}
                  </span>
                </div>
                <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-700">{item.summary}</p>
                <div className="mt-3 flex items-center justify-between gap-3">
                  <span className="rounded-full border border-white/85 bg-white/75 px-2.5 py-1 text-[11px] font-semibold text-slate-500">
                    {item.actionLabel}
                  </span>
                  <div className="inline-flex items-center gap-1 text-xs font-semibold text-sky-700">
                    <AppIcon name="external" className="h-3.5 w-3.5" />
                    {t("summary.latestNewOpen", "打开详情")}
                  </div>
                </div>
              </Link>
            ))}
          </div>
          {filteredLatestSessionItems.length === 0 ? (
            <p className="mt-3 rounded-2xl border border-white/85 bg-white/55 px-4 py-3 text-sm text-slate-500">
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
              <p className="mt-2 text-sm text-slate-500">
                {t(
                  "summary.researchHint",
                  "把最近沉淀的行业研报和行动卡带回本次总结，便于继续推进销售、投标与生态动作。",
                )}
              </p>
            </div>
            <Link
              href="/research"
              className="inline-flex items-center gap-1 rounded-full border border-white/85 bg-white/75 px-3 py-1.5 text-[11px] font-semibold text-slate-600 transition hover:bg-white/90"
            >
              <AppIcon name="spark" className="h-3.5 w-3.5" />
              {t("summary.researchOpen", "打开研报中心")}
            </Link>
          </div>
          <div className="mt-4 grid gap-3 xl:grid-cols-3">
            {researchRecommendations.map((entry) => (
              <Link
                key={entry.id}
                href={`/knowledge/${entry.id}`}
                className="group block rounded-2xl border border-white/85 bg-white/60 p-4 transition hover:-translate-y-0.5 hover:bg-white/75"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <h4 className="min-w-0 flex-1 text-base font-semibold leading-7 text-slate-900">
                    {entry.title}
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {entry.isFocusReference ? (
                      <span className="rounded-full bg-sky-100 px-2.5 py-1 text-[11px] font-semibold text-sky-700">
                        {t("inbox.researchHistoryFocus", "Focus 参考")}
                      </span>
                    ) : null}
                    {entry.collectionName ? (
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600">
                        {entry.collectionName}
                      </span>
                    ) : null}
                  </div>
                </div>
                <p className="mt-3 line-clamp-3 text-sm leading-6 text-slate-600">{entry.summary}</p>

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
                          ? "bg-emerald-50 text-emerald-700"
                          : entry.evidenceMode === "provisional"
                            ? "bg-amber-50 text-amber-700"
                            : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {entry.evidenceMode === "strong" ? "强证据" : entry.evidenceMode === "provisional" ? "可用初版" : "兜底候选"}
                    </span>
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-600">
                      检索质量 {entry.retrievalQuality === "high" ? "高价值" : entry.retrievalQuality === "medium" ? "普通价值" : "低价值"}
                    </span>
                    <span className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] text-sky-700">
                      官方源 {entry.officialSourcePercent}%
                    </span>
                    {entry.scopeRegions.map((value) => (
                      <span key={`${entry.id}-scope-region-${value}`} className="rounded-full bg-cyan-50 px-2.5 py-1 text-[11px] text-cyan-700">
                        区域 · {value}
                      </span>
                    ))}
                    {entry.scopeIndustries.map((value) => (
                      <span key={`${entry.id}-scope-industry-${value}`} className="rounded-full bg-blue-50 px-2.5 py-1 text-[11px] text-blue-700">
                        领域 · {value}
                      </span>
                    ))}
                    {entry.scopeClients.map((value) => (
                      <span key={`${entry.id}-scope-client-${value}`} className="rounded-full bg-fuchsia-50 px-2.5 py-1 text-[11px] text-fuchsia-700">
                        公司 · {value}
                      </span>
                    ))}
                    {entry.topicAnchors.map((value) => (
                      <span key={`${entry.id}-anchor-${value}`} className="rounded-full bg-violet-50 px-2.5 py-1 text-[11px] text-violet-700">
                        {value}
                      </span>
                    ))}
                    {entry.matchedThemes.map((value) => (
                      <span key={`${entry.id}-theme-${value}`} className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] text-emerald-700">
                        {value}
                      </span>
                    ))}
                    {entry.filteredOldSourceCount > 0 ? (
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-500">
                        剔除过旧来源 {entry.filteredOldSourceCount}
                      </span>
                    ) : null}
                    {entry.filteredRegionConflictCount > 0 ? (
                      <span className="rounded-full bg-rose-50 px-2.5 py-1 text-[11px] text-rose-700">
                        拦截越界区域 {entry.filteredRegionConflictCount}
                      </span>
                    ) : null}
                    {entry.uniqueDomainCount > 0 ? (
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-500">
                        域名 {entry.uniqueDomainCount}
                      </span>
                    ) : null}
                    {entry.normalizedEntityCount > 0 ? (
                      <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] text-emerald-700">
                        归一化实体 {entry.normalizedEntityCount}
                      </span>
                    ) : null}
                    {entry.correctiveTriggered ? (
                      <span className="rounded-full bg-orange-50 px-2.5 py-1 text-[11px] text-orange-700">
                        已触发纠错检索
                      </span>
                    ) : null}
                    {entry.candidateProfileCompanies.length ? (
                      <span className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] text-sky-700">
                        候选补证公司 {entry.candidateProfileCompanies.length}
                      </span>
                    ) : null}
                    {entry.candidateProfileHitCount > 0 ? (
                      <span className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] text-sky-700">
                        补证公开源 {entry.candidateProfileHitCount}
                      </span>
                    ) : null}
                    {entry.candidateProfileOfficialHitCount > 0 ? (
                      <span className="rounded-full bg-cyan-50 px-2.5 py-1 text-[11px] text-cyan-700">
                        其中官方源 {entry.candidateProfileOfficialHitCount}
                      </span>
                    ) : null}
                    {entry.candidateProfileCompanies.map((value) => (
                      <span key={`${entry.id}-candidate-profile-${value}`} className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] text-sky-700">
                        候选公司 · {value}
                      </span>
                    ))}
                    {entry.candidateProfileSourceLabels.map((value) => (
                      <span key={`${entry.id}-candidate-profile-source-${value}`} className="rounded-full bg-cyan-50 px-2.5 py-1 text-[11px] text-cyan-700">
                        {value}
                      </span>
                    ))}
                  </div>
                ) : null}

                {entry.actionCards.length ? (
                  <div className="mt-4 grid gap-2">
                    {entry.actionCards.map((card) => (
                        <div key={`${entry.id}-${card.title}`} className="rounded-2xl border border-slate-200/80 bg-slate-50/85 p-3">
                          <div className="break-words text-sm font-semibold leading-6 text-slate-900">{card.title}</div>
                          <div className="mt-2 grid gap-1.5 break-words text-[11px] text-slate-500">
                          {card.targetPersona ? (
                            <div>
                              <span className="font-semibold text-slate-700">{t("research.actionTarget", "优先对象")}：</span>
                              {card.targetPersona}
                            </div>
                          ) : null}
                          {card.executionWindow ? (
                            <div>
                              <span className="font-semibold text-slate-700">{t("research.actionWindow", "执行窗口")}：</span>
                              {card.executionWindow}
                            </div>
                          ) : null}
                          {card.deliverable ? (
                            <div>
                              <span className="font-semibold text-slate-700">{t("research.actionDeliverable", "产出物")}：</span>
                              {card.deliverable}
                            </div>
                          ) : null}
                        </div>
                        {card.phases.length ? (
                          <div className="mt-3 grid gap-2">
                            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                              {t("research.actionTimeline", "推进节奏")}
                            </div>
                            <div className="grid gap-2">
                              {card.phases.map((phase) => (
                                <div
                                  key={`${entry.id}-${card.title}-${phase.label}-${phase.content}`}
                                  className="min-w-0 overflow-hidden rounded-2xl border border-white/80 bg-white/80 px-3 py-2.5"
                                >
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <span className="rounded-full bg-slate-900 px-2.5 py-1 text-[11px] font-medium text-white">
                                      {phase.label}
                                    </span>
                                    {phase.horizon ? (
                                      <span className="text-[11px] font-medium text-slate-500">{phase.horizon}</span>
                                    ) : null}
                                  </div>
                                  <div className="mt-2 min-w-0 break-words whitespace-pre-wrap text-xs leading-5 text-slate-600 [overflow-wrap:anywhere]">
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
                        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-sky-600">
                          {t("research.topTargets", "高价值甲方 Top 3")}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {entry.topTargets.map((value) => (
                            <span key={`${entry.id}-buyer-${value}`} className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] text-sky-800">
                              {value}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    {entry.topCompetitors.length ? (
                      <div>
                        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-600">
                          {t("research.topCompetitors", "高威胁竞品 Top 3")}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {entry.topCompetitors.map((value) => (
                            <span key={`${entry.id}-competitor-${value}`} className="rounded-full bg-amber-50 px-2.5 py-1 text-[11px] text-amber-800">
                              {value}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    {entry.topPartners.length ? (
                      <div>
                        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-600">
                          {t("research.topPartners", "高影响力生态伙伴 Top 3")}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {entry.topPartners.map((value) => (
                            <span key={`${entry.id}-partner-${value}`} className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] text-emerald-800">
                              {value}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : null}

                <div className="mt-4 flex items-center justify-between gap-3 text-[11px] text-slate-400">
                  <span>{new Date(entry.createdAt).toLocaleString()}</span>
                  <span className="inline-flex items-center gap-1 font-semibold text-sky-700">
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
          <span className="text-xs text-slate-500">
            {t("summary.dataSource", "数据源")}：
            {sessionSource === "api"
              ? t("summary.dataSource.api", "实时 Session")
              : t("summary.dataSource.local", "本地汇总")}
          </span>
        </div>
        {recommendedDeepReads.length > 0 ? (
          <div className="mt-3 space-y-2.5">
            {recommendedDeepReads.map((item, idx) => (
              <div key={item.id} className="rounded-2xl border border-white/85 bg-white/60 px-4 py-3">
                <div className="flex items-start justify-between gap-3">
                  <p className="line-clamp-1 text-sm font-semibold text-slate-900">
                    {idx + 1}. {item.title}
                  </p>
                  <span className="shrink-0 rounded-full border border-emerald-200/85 bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700">
                    {item.scoreLabel}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-500">{item.source}</p>
                <p className="mt-1 line-clamp-2 text-sm leading-6 text-slate-700">{item.summary}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-3 rounded-2xl border border-white/85 bg-white/55 px-4 py-3 text-sm text-slate-500">
            {t("summary.emptyDeepReads", "暂无深读推荐，结束一轮 Focus 后会在这里显示优先阅读项。")}
          </p>
        )}
      </div>

      {assistantResult ? (
        <div className="af-glass rounded-[30px] p-5 md:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="af-kicker">{t("summary.assistant.title", "Focus Assistant 回流")}</p>
              <p className="mt-2 text-lg font-semibold tracking-[-0.02em] text-slate-900">
                {assistantResult.actionTitle}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full border border-sky-200/85 bg-sky-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-sky-700">
                {assistantResult.channelUsed === "workbuddy"
                  ? t("summary.assistant.workbuddy", "WorkBuddy")
                  : t("summary.assistant.direct", "直连")}
              </span>
              <span className="rounded-full border border-white/85 bg-white/65 px-2.5 py-1 text-[11px] font-semibold tracking-[0.14em] text-slate-500">
                {formatAssistantTime(assistantResult.createdAt, preferences.language)}
              </span>
            </div>
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-500">
            {assistantResult.message ||
              t(
                "summary.assistant.subtitle",
                "最近一次 Assistant 执行结果已回流到当前 Session Summary。",
              )}
          </p>
          <div className="mt-3 rounded-2xl border border-white/85 bg-white/60 px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <p className="af-kicker">{t("summary.assistant.output", "输出摘要")}</p>
              {assistantResult.content ? (
                <button
                  type="button"
                  onClick={() => {
                    void copyText(assistantResult.content);
                  }}
                  className="inline-flex items-center gap-1 rounded-full border border-white/85 bg-white/75 px-2.5 py-1 text-[11px] font-semibold text-slate-500"
                >
                  <AppIcon name="copy" className="h-3.5 w-3.5" />
                  {t("common.copy", "复制")}
                </button>
              ) : null}
            </div>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">
              {assistantResult.content ||
                t("summary.assistant.noOutput", "本次动作未返回可展示的文本输出。")}
            </p>
          </div>
          {assistantHistory.length > 1 ? (
            <div className="mt-3 border-t border-white/60 pt-3">
              <p className="af-kicker">{t("summary.assistant.history", "最近执行")}</p>
              <div className="mt-2 space-y-2">
                {assistantHistory.slice(1, 4).map((entry) => (
                  <button
                    key={`${entry.createdAt}-${entry.actionKey}`}
                    type="button"
                    onClick={() => {
                      setAssistantResult(entry);
                    }}
                    className="flex w-full items-start justify-between gap-3 rounded-2xl border border-white/85 bg-white/55 px-4 py-3 text-left transition hover:bg-white/75"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-slate-900">{entry.actionTitle}</p>
                      <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">
                        {entry.message ||
                          entry.content ||
                          t("summary.assistant.noOutput", "本次动作未返回可展示的文本输出。")}
                      </p>
                    </div>
                    <span className="shrink-0 text-[11px] font-medium text-slate-400">
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
              : t("summary.btn.markdown", "生成 Markdown 总结")}
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
              : t("summary.btn.readingList", "生成稍后读清单")}
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
              : t("summary.btn.todoDraft", "生成待办草稿")}
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
              void executeTask("export_watchlist_digest", fallbackWatchlistDigest(t), setWatchlistDigest);
            }}
            disabled={Boolean(runningTask)}
            className="af-btn af-btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
          >
            <WorkBuddyMark size={14} />
            {runningTask === "export_watchlist_digest"
              ? t("summary.btn.generating", "生成中...")
              : t("summary.btn.watchlistDigest", "生成 Watchlist Digest")}
          </button>
        </div>
        {loadingSession ? (
          <p className="mt-3 text-xs text-slate-500">
            {t("summary.syncing", "正在同步实时 Session...")}
          </p>
        ) : null}
        <p className="mt-3 text-xs text-slate-500">
          {t(
            "summary.task.routeHint",
            "导出优先通过 WorkBuddy 执行，异常时自动回退到本地 API。",
          )}
        </p>
        {taskMessage ? <p className="mt-3 text-xs text-slate-500">{taskMessage}</p> : null}

        <OutputBlock
          title={t("summary.block.markdown", "Markdown 总结")}
          content={markdown}
          emptyText={t("summary.block.emptyMarkdown", "点击“生成 Markdown 总结”后显示结果。")}
          onCopy={copyText}
          copyLabel={t("common.copy", "复制")}
          artifact={latestArtifactsByType.markdown}
        />
        <OutputBlock
          title={t("summary.block.readingList", "稍后读清单")}
          content={readingList}
          emptyText={t("summary.block.emptyReadingList", "点击“生成稍后读清单”后显示结果。")}
          onCopy={copyText}
          copyLabel={t("common.copy", "复制")}
          artifact={latestArtifactsByType.readingList}
        />
        <OutputBlock
          title={t("summary.block.todoDraft", "待办草稿")}
          content={todoDraft}
          emptyText={t("summary.block.emptyTodoDraft", "点击“生成待办草稿”后显示结果。")}
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
              className="inline-flex items-center gap-1 rounded-full border border-sky-200/80 bg-sky-50/80 px-2.5 py-1 text-[11px] font-semibold text-sky-700 disabled:cursor-not-allowed disabled:opacity-60"
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
        />
        <OutputBlock
          title={t("summary.block.salesBrief", "销售 Brief")}
          content={salesBrief}
          emptyText={t("summary.block.emptySalesBrief", "点击“生成销售 Brief”后显示结果。")}
          onCopy={copyText}
          copyLabel={t("common.copy", "复制")}
        />
        <OutputBlock
          title={t("summary.block.outreachDraft", "外联草稿")}
          content={outreachDraft}
          emptyText={t("summary.block.emptyOutreachDraft", "点击“生成外联草稿”后显示结果。")}
          onCopy={copyText}
          copyLabel={t("common.copy", "复制")}
        />
        <OutputBlock
          title={t("summary.block.watchlistDigest", "Watchlist Digest")}
          content={watchlistDigest}
          emptyText={t("summary.block.emptyWatchlistDigest", "点击“生成 Watchlist Digest”后显示结果。")}
          onCopy={copyText}
          copyLabel={t("common.copy", "复制")}
        />
      </div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="af-glass rounded-3xl p-4">
      <p className="af-kicker">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-slate-900">{value}</p>
    </div>
  );
}

function OutputBlock({
  title,
  content,
  emptyText,
  onCopy,
  copyLabel,
  artifact,
  extraActions,
}: {
  title: string;
  content: string;
  emptyText: string;
  onCopy: (content: string) => Promise<void>;
  copyLabel: string;
  artifact?: ApiSessionArtifact | null;
  extraActions?: ReactNode;
}) {
  return (
    <div className="mt-4">
      <p className="af-kicker">{title}</p>
      {content ? (
        <div className="mt-2">
          <div className="mb-2 flex flex-wrap justify-end gap-2">
            {extraActions}
            <button
              type="button"
              onClick={() => {
                void onCopy(content);
              }}
              className="inline-flex items-center gap-1 rounded-full border border-white/85 bg-white/75 px-2.5 py-1 text-[11px] font-semibold text-slate-500"
            >
              <AppIcon name="copy" className="h-3.5 w-3.5" />
              {copyLabel}
            </button>
          </div>
          <textarea
            readOnly
            value={content}
            rows={8}
            className="w-full rounded-2xl border border-white/85 bg-white/70 px-4 py-3 font-mono text-xs leading-6 text-slate-700 outline-none md:text-sm"
          />
          {artifact?.items?.length ? <ArtifactSources artifact={artifact} /> : null}
        </div>
      ) : (
        <div className="mt-2 space-y-2">
          <p className="rounded-2xl border border-white/85 bg-white/55 px-4 py-3 text-sm text-slate-500">
            {emptyText}
          </p>
          {extraActions ? <div className="flex justify-end">{extraActions}</div> : null}
        </div>
      )}
    </div>
  );
}

function ArtifactSources({ artifact }: { artifact: ApiSessionArtifact }) {
  return (
    <div className="mt-3 rounded-2xl border border-white/85 bg-white/55 px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
        来源条目
      </p>
      <div className="mt-2 space-y-2">
        {artifact.items.map((item) => (
          <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium text-slate-800">{item.title_snapshot}</div>
              <div className="truncate text-xs text-slate-500">
                {item.included_reason || "artifact_reference"}
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {item.source_url_snapshot ? (
                <a
                  href={item.source_url_snapshot}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-full border border-sky-200/80 bg-sky-50 px-2.5 py-1 text-[11px] font-semibold text-sky-700"
                >
                  原文
                </a>
              ) : null}
              {item.item_id ? (
                <Link
                  href={`/items/${item.item_id}`}
                  className="rounded-full border border-white/85 bg-white/80 px-2.5 py-1 text-[11px] font-semibold text-slate-600"
                >
                  详情
                </Link>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
