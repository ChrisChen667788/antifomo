import type {
  ApiKnowledgeEntry,
  ApiResearchActionCard,
  ApiResearchReport,
  ApiResearchWatchlist,
  ApiSession,
  ApiSessionItem,
  ApiTask,
  ApiTaskBriefingContext,
  WechatAgentBatchStatus,
} from "@/lib/api/types";
import { dedupeTextList } from "@/lib/display-list";
export { getBatchProgress, hasBatchSnapshot } from "@/lib/focus-runtime-model";
import type { SessionMetrics } from "@/lib/mock-data";

export const SESSION_ID_KEY = "anti_fomo_session_id";

export type SummaryTranslateFn = (key: string, fallback?: string) => string;

export type TaskType =
  | "export_markdown_summary"
  | "export_reading_list"
  | "export_todo_draft"
  | "export_exec_brief"
  | "export_sales_brief"
  | "export_outreach_draft"
  | "export_watchlist_digest";

export type SessionSource = "local" | "api";
export type TaskChannel = "workbuddy" | "direct";

export interface RecommendedDeepReadItem {
  id: string;
  title: string;
  source: string;
  summary: string;
  scoreLabel: string;
}

export interface LatestSessionItem {
  id: string;
  title: string;
  source: string;
  sourceKey: string;
  summary: string;
  scoreLabel: string;
  actionSuggestion: string | null;
  actionLabel: string;
}

export interface SessionResearchItem {
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

export interface SessionWatchlistHighlight {
  id: string;
  watchlistId: string;
  watchlistName: string;
  severity: "low" | "medium" | "high";
  summary: string;
  createdAt: string;
  accounts: string[];
  whyNow: string[];
  budgetProbability: number;
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
  return dedupeTextList(values as Iterable<unknown>, {
    limit: 3,
    normalizer: conciseEntityName,
  });
}

export function formatDuration(minutes: number, t: SummaryTranslateFn): string {
  const hours = Math.floor(minutes / 60);
  const restMinutes = minutes % 60;
  if (hours === 0) {
    return `${restMinutes} ${t("common.minutes", "分钟")}`;
  }
  return `${hours} ${t("common.hours", "小时")} ${restMinutes} ${t("common.minutes", "分钟")}`;
}

export function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export function taskNeedsSession(taskType: TaskType): boolean {
  return taskType === "export_markdown_summary" || taskType === "export_todo_draft";
}

export function taskSessionId(taskType: TaskType, sessionId?: string): string | undefined {
  if (taskType === "export_watchlist_digest") {
    return undefined;
  }
  return sessionId || (taskNeedsSession(taskType) ? undefined : sessionId);
}

export function fallbackMarkdown(
  metrics: SessionMetrics,
  t: SummaryTranslateFn,
  locale: string,
): string {
  const now = new Date().toLocaleString(locale, { hour12: false });
  return `# ${t("summary.block.markdown", "Markdown 总结")}

- ${t("summary.block.markdown", "Markdown 总结")}: ${now}
- ${t("focus.goal", "本次目标")}: ${metrics.goalText || t("common.notSet", "未设置")}
- ${t("summary.metric.duration", "专注时长")}: ${formatDuration(metrics.durationMinutes, t)}
- ${t("summary.metric.newContent", "新增内容数")}: ${metrics.newContentCount}
- ${t("summary.metric.deepRead", "推荐深读数")}: ${metrics.deepReadCount}
- ${t("summary.metric.later", "稍后读数")}: ${metrics.laterCount}
- ${t("summary.metric.skip", "可忽略数")}: ${metrics.ignorableCount}`;
}

export function fallbackReadingList(t: SummaryTranslateFn): string {
  return `# ${t("summary.block.readingList", "稍后读清单")}

1. ${t("summary.sample.readA", "高价值内容 A（深读）")}
2. ${t("summary.sample.readB", "行业趋势内容 B（深读）")}
3. ${t("summary.sample.readC", "方法论内容 C（稍后读）")}
4. ${t("summary.sample.readD", "工具更新内容 D（稍后读）")}`;
}

export function fallbackTodoDraft(t: SummaryTranslateFn): string {
  return `# ${t("summary.block.todoDraft", "待办草稿")}

- [ ] ${t("summary.sample.todo1", "先深读 2 条高价值内容并记录要点")}
- [ ] ${t("summary.sample.todo2", "将稍后读内容归入下一个专注时段")}
- [ ] ${t("summary.sample.todo3", "把可忽略内容批量归档")}`;
}

export function fallbackExecBrief(t: SummaryTranslateFn): string {
  return `# ${t("summary.block.execBrief", "老板简报")}

- ${t("summary.metric.deepRead", "推荐深读数")}：优先同步本轮高价值内容和风险变化
- ${t("summary.block.execBriefHighlight", "建议重点")}：今天先看新增甲方、预算节点和 watchlist 变化`;
}

export function fallbackSalesBrief(t: SummaryTranslateFn): string {
  return `# ${t("summary.block.salesBrief", "销售 Brief")}

- ${t("summary.block.salesBriefNext", "下一步")}：围绕深读条目整理拜访提纲
- ${t("summary.block.salesBriefFocus", "跟进重点")}：甲方线索、竞品动作、预算时间窗`;
}

export function fallbackOutreachDraft(t: SummaryTranslateFn): string {
  return `# ${t("summary.block.outreachDraft", "外联草稿")}

您好，结合最近的公开动态，我们整理了几条和您当前项目更相关的观察，适合继续约一个 20 分钟的沟通窗口。`;
}

function fallbackWatchlistDigest(t: SummaryTranslateFn): string {
  return `# ${t("summary.block.watchlistDigest", "Watchlist Digest")}

- ${t("summary.block.watchlistDigestHint", "当前可先汇总专题刷新和新增风险提示")}。`;
}

export function buildWatchlistHighlights(watchlists: ApiResearchWatchlist[]): SessionWatchlistHighlight[] {
  return watchlists
    .flatMap((watchlist) =>
      (watchlist.latest_changes || []).map((change) => {
        const payload = change.payload || {};
        const accounts = Array.isArray(payload.accounts)
          ? payload.accounts.map((value) => String(value || "").trim()).filter(Boolean).slice(0, 3)
          : [];
        const whyNow = Array.isArray(payload.why_now)
          ? payload.why_now.map((value) => String(value || "").trim()).filter(Boolean).slice(0, 2)
          : [];
        const budgetProbability = Number(payload.top_budget_probability || 0);
        return {
          id: change.id,
          watchlistId: watchlist.id,
          watchlistName: watchlist.name,
          severity: change.severity,
          summary: change.summary,
          createdAt: change.created_at,
          accounts,
          whyNow,
          budgetProbability,
        };
      }),
    )
    .sort((left, right) => {
      const severityScore = (value: string) => (value === "high" ? 3 : value === "medium" ? 2 : 1);
      const diff = severityScore(right.severity) - severityScore(left.severity);
      if (diff !== 0) return diff;
      return new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime();
    })
    .slice(0, 6);
}

export function watchlistDigestFromHighlights(
  highlights: SessionWatchlistHighlight[],
  t: SummaryTranslateFn,
): string {
  if (!highlights.length) {
    return fallbackWatchlistDigest(t);
  }
  const lines = highlights.slice(0, 4).map((item) => {
    const accountText = item.accounts.length ? ` · 账户：${item.accounts.join(" / ")}` : "";
    const budgetText = item.budgetProbability > 0 ? ` · 预算概率 ${item.budgetProbability}%` : "";
    return `- [${item.watchlistName}] ${item.summary}${accountText}${budgetText}`;
  });
  return `# ${t("summary.block.watchlistDigest", "Watchlist Digest")}\n\n${lines.join("\n")}`;
}

export function parseTaskBriefingContext(outputPayload: ApiTask["output_payload"]): ApiTaskBriefingContext | null {
  const raw =
    outputPayload && typeof outputPayload === "object"
      ? (outputPayload.briefing_context || outputPayload.watchlist_context)
      : null;
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const typed = raw as Record<string, unknown>;
  const accountRaw = typed.account && typeof typed.account === "object" ? (typed.account as Record<string, unknown>) : null;
  const parseRows = (value: unknown) =>
    Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object") : [];
  return {
    account: accountRaw
      ? {
          slug: String(accountRaw.slug || ""),
          name: String(accountRaw.name || ""),
          objective: String(accountRaw.objective || ""),
          value_hypothesis: String(accountRaw.value_hypothesis || ""),
          next_meeting_goal: String(accountRaw.next_meeting_goal || ""),
          why_now: Array.isArray(accountRaw.why_now) ? accountRaw.why_now.map((value) => String(value || "")).filter(Boolean) : [],
          stakeholders: parseRows(accountRaw.stakeholders).map((item) => ({
            name: String(item.name || ""),
            role: String(item.role || ""),
            priority: String(item.priority || ""),
            next_move: String(item.next_move || ""),
          })),
          close_plan: parseRows(accountRaw.close_plan).map((item) => ({
            title: String(item.title || ""),
            owner: String(item.owner || ""),
            due_window: String(item.due_window || ""),
            exit_criteria: String(item.exit_criteria || ""),
          })),
          pipeline_risks: parseRows(accountRaw.pipeline_risks).map((item) => ({
            title: String(item.title || ""),
            severity: String(item.severity || ""),
            detail: String(item.detail || ""),
            mitigation: String(item.mitigation || ""),
          })),
        }
      : null,
    top_accounts: parseRows(typed.top_accounts).map((item) => ({
      slug: String(item.slug || ""),
      name: String(item.name || ""),
      budget_probability: Number(item.budget_probability || 0),
      next_best_action: String(item.next_best_action || ""),
    })),
    top_opportunities: parseRows(typed.top_opportunities).map((item) => ({
      title: String(item.title || ""),
      account_name: String(item.account_name || ""),
      budget_probability: Number(item.budget_probability || 0),
      next_step: String(item.next_step || ""),
    })),
    top_alerts: parseRows(typed.top_alerts).map((item) => ({
      title: String(item.title || ""),
      severity: String(item.severity || ""),
      summary: String(item.summary || ""),
      account_name: String(item.account_name || ""),
      recommended_action: String(item.recommended_action || ""),
    })),
    review_queue: parseRows(typed.review_queue).map((item) => ({
      id: String(item.id || ""),
      title: String(item.title || ""),
      severity: String(item.severity || ""),
      summary: String(item.summary || ""),
      account_name: String(item.account_name || ""),
      recommended_action: String(item.recommended_action || ""),
      resolution_status: String(item.resolution_status || "open"),
    })),
  };
}

export function mapSessionToMetrics(session: ApiSession): SessionMetrics {
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

function scoreLabel(score: number | null, t: SummaryTranslateFn): string {
  if (score === null) return t("summary.score.pending", "评分待补充");
  if (score >= 4.0) return t("summary.score.high", "高价值");
  if (score >= 2.8) return t("summary.score.mid", "中价值");
  return t("summary.score.low", "低价值");
}

export function buildRecommendedDeepReads(
  items: ApiSessionItem[],
  t: SummaryTranslateFn,
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

export function buildLatestSessionItems(
  items: ApiSessionItem[],
  batchStatus: WechatAgentBatchStatus | null,
  t: SummaryTranslateFn,
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

export function formatAssistantTime(iso: string, locale: string): string {
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

export function extractSessionResearchItem(entry: ApiKnowledgeEntry): SessionResearchItem {
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
