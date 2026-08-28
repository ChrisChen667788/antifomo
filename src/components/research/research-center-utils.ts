import type {
  ApiKnowledgeEntry,
  ApiResearchExperimentPlan,
  ApiResearchLowQualityReviewQueueItem,
  ApiResearchWatchlist,
  ApiResearchWatchlistRunDueResponse,
} from "@/lib/api";
import { dedupeTextList } from "@/lib/display-list";
import { getGuardedRewriteReasonLabels, isGuardedBacklog } from "@/lib/research-diagnostics";
import { getResearchFacets, type ResearchPerspective } from "@/lib/research-facets";

export type ResearchFilter = "all" | "reports" | "actions";
export type ResearchRetrievalLens = "all" | "high_trust" | "official_rich" | "action_ready" | "needs_review";

export type ResearchCenterActionCard = {
  title: string;
  target_persona?: string;
  execution_window?: string;
  deliverable?: string;
  recommended_steps?: string[];
};

export type ResearchCenterEntry = ApiKnowledgeEntry & {
  region_label: string;
  industry_label: string;
  action_type_label: string;
};

export function triggerMarkdownDownload(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export const WATCHLIST_SCHEDULE_OPTIONS = [
  { value: "manual", fallback: "手动" },
  { value: "daily", fallback: "每日" },
  { value: "twice_daily", fallback: "每日两次" },
  { value: "weekdays", fallback: "工作日" },
  { value: "every_6h", fallback: "每 6 小时" },
] as const;

export function sortEntries<T extends ApiKnowledgeEntry>(items: T[]): T[] {
  return [...items].sort((left, right) => {
    const leftTime = new Date(left.updated_at || left.created_at).getTime();
    const rightTime = new Date(right.updated_at || right.created_at).getTime();
    return rightTime - leftTime;
  });
}

export function formatWatchlistSchedule(schedule: string, t: (key: string, fallback: string) => string) {
  const normalized = String(schedule || "manual");
  const matched = WATCHLIST_SCHEDULE_OPTIONS.find((item) => item.value === normalized);
  return matched ? t(`research.watchlistSchedule.${matched.value}`, matched.fallback) : normalized;
}

export function formatWatchlistTime(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString();
}

export function formatAutomationInterval(seconds?: number) {
  const safe = Math.max(0, Number(seconds || 0));
  if (!safe) return "";
  if (safe % 3600 === 0) {
    return `${safe / 3600}h`;
  }
  if (safe % 60 === 0) {
    return `${safe / 60}m`;
  }
  return `${safe}s`;
}

export function normalizeTextList(values: unknown): string[] {
  return dedupeTextList(values as Iterable<unknown>);
}

export function parseActionPhases(steps: string[] | undefined) {
  return (Array.isArray(steps) ? steps : [])
    .map((step) => String(step || "").trim())
    .filter(Boolean)
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

export function getResearchActionCards(entry: ApiKnowledgeEntry): ResearchCenterActionCard[] {
  const payload = (entry.metadata_payload || {}) as {
    action_cards?: ResearchCenterActionCard[];
  };
  return Array.isArray(payload.action_cards)
    ? payload.action_cards
        .map((card) => ({
          title: String(card.title || "").trim(),
          target_persona: String(card.target_persona || "").trim(),
          execution_window: String(card.execution_window || "").trim(),
          deliverable: String(card.deliverable || "").trim(),
          recommended_steps: normalizeTextList(card.recommended_steps),
        }))
        .filter((card) => card.title)
        .slice(0, 2)
    : [];
}

export function buildPreview(entry: ApiKnowledgeEntry): string {
  const report = (entry.metadata_payload as { report?: { executive_summary?: string } } | null)?.report;
  const summary = report?.executive_summary || entry.content || "";
  return summary.length > 110 ? `${summary.slice(0, 109).trim()}…` : summary;
}

export function getActionType(entry: ApiKnowledgeEntry): string {
  const payload = entry.metadata_payload as { card?: { action_type?: string } } | null;
  return payload?.card?.action_type || "";
}

export function getResearchKeyword(entry: ApiKnowledgeEntry): string {
  const payload = entry.metadata_payload as
    | {
        report?: { keyword?: string };
        keyword?: string;
      }
    | null;
  return payload?.report?.keyword || payload?.keyword || "";
}

export function getResearchSourceCount(entry: ApiKnowledgeEntry): number {
  const payload = entry.metadata_payload as
    | {
        report?: { source_count?: number };
      }
    | null;
  return Number(payload?.report?.source_count || 0);
}

export function getResearchReportMeta(
  entry: ApiKnowledgeEntry,
): { evidenceDensity: string; sourceQuality: string } {
  const payload = entry.metadata_payload as
    | {
        report?: { evidence_density?: string; source_quality?: string };
      }
    | null;
  return {
    evidenceDensity: String(payload?.report?.evidence_density || "low"),
    sourceQuality: String(payload?.report?.source_quality || "low"),
  };
}

export function getResearchSourceDiagnostics(entry: ApiKnowledgeEntry): {
  topicAnchors: string[];
  matchedThemes: string[];
  scopeRegions: string[];
  scopeIndustries: string[];
  scopeClients: string[];
  guardedBacklog: boolean;
  guardedReasonLabels: string[];
  supportedTargetAccounts: string[];
  unsupportedTargetAccounts: string[];
  filteredOldSourceCount: number;
  filteredRegionConflictCount: number;
  strictTopicSourceCount: number;
  retrievalQuality: "low" | "medium" | "high";
  evidenceMode: "strong" | "provisional" | "fallback";
  strictMatchRatio: number;
  officialSourceRatio: number;
  uniqueDomainCount: number;
  normalizedEntityCount: number;
  normalizedTargetCount: number;
  normalizedCompetitorCount: number;
  normalizedPartnerCount: number;
  expansionTriggered: boolean;
  correctiveTriggered: boolean;
  candidateProfileCompanies: string[];
  candidateProfileHitCount: number;
  candidateProfileOfficialHitCount: number;
  candidateProfileSourceLabels: string[];
} {
  const payload = entry.metadata_payload as
    | {
        report?: {
          source_diagnostics?: {
            topic_anchor_terms?: string[];
            matched_theme_labels?: string[];
            guarded_backlog?: boolean;
            guarded_rewrite_reasons?: string[];
            guarded_rewrite_reason_labels?: string[];
            supported_target_accounts?: string[];
            unsupported_target_accounts?: string[];
            filtered_old_source_count?: number;
            filtered_region_conflict_count?: number;
            strict_topic_source_count?: number;
            retrieval_quality?: "low" | "medium" | "high";
            evidence_mode?: "strong" | "provisional" | "fallback";
            strict_match_ratio?: number;
            official_source_ratio?: number;
            unique_domain_count?: number;
            normalized_entity_count?: number;
            normalized_target_count?: number;
            normalized_competitor_count?: number;
            normalized_partner_count?: number;
            expansion_triggered?: boolean;
            corrective_triggered?: boolean;
            candidate_profile_companies?: string[];
            candidate_profile_hit_count?: number;
            candidate_profile_official_hit_count?: number;
            candidate_profile_source_labels?: string[];
          };
        };
      }
    | null;
  const diagnostics = payload?.report?.source_diagnostics;
  return {
    topicAnchors: normalizeTextList(diagnostics?.topic_anchor_terms).slice(0, 3),
    matchedThemes: normalizeTextList(diagnostics?.matched_theme_labels).slice(0, 3),
    scopeRegions: normalizeTextList((diagnostics as { scope_regions?: string[] } | undefined)?.scope_regions).slice(0, 2),
    scopeIndustries: normalizeTextList((diagnostics as { scope_industries?: string[] } | undefined)?.scope_industries).slice(0, 2),
    scopeClients: normalizeTextList((diagnostics as { scope_clients?: string[] } | undefined)?.scope_clients).slice(0, 2),
    guardedBacklog: isGuardedBacklog(diagnostics),
    guardedReasonLabels: getGuardedRewriteReasonLabels(diagnostics).slice(0, 3),
    supportedTargetAccounts: normalizeTextList((diagnostics as { supported_target_accounts?: string[] } | undefined)?.supported_target_accounts).slice(0, 3),
    unsupportedTargetAccounts: normalizeTextList((diagnostics as { unsupported_target_accounts?: string[] } | undefined)?.unsupported_target_accounts).slice(0, 3),
    filteredOldSourceCount: Number(diagnostics?.filtered_old_source_count || 0),
    filteredRegionConflictCount: Number((diagnostics as { filtered_region_conflict_count?: number } | undefined)?.filtered_region_conflict_count || 0),
    strictTopicSourceCount: Number(diagnostics?.strict_topic_source_count || 0),
    retrievalQuality: (String(diagnostics?.retrieval_quality || "low") as "low" | "medium" | "high"),
    evidenceMode: (String((diagnostics as { evidence_mode?: string } | undefined)?.evidence_mode || "fallback") as "strong" | "provisional" | "fallback"),
    strictMatchRatio: Number(diagnostics?.strict_match_ratio || 0),
    officialSourceRatio: Number(diagnostics?.official_source_ratio || 0),
    uniqueDomainCount: Number(diagnostics?.unique_domain_count || 0),
    normalizedEntityCount: Number(diagnostics?.normalized_entity_count || 0),
    normalizedTargetCount: Number(diagnostics?.normalized_target_count || 0),
    normalizedCompetitorCount: Number(diagnostics?.normalized_competitor_count || 0),
    normalizedPartnerCount: Number(diagnostics?.normalized_partner_count || 0),
    expansionTriggered: Boolean(diagnostics?.expansion_triggered),
    correctiveTriggered: Boolean((diagnostics as { corrective_triggered?: boolean } | undefined)?.corrective_triggered),
    candidateProfileCompanies: normalizeTextList((diagnostics as { candidate_profile_companies?: string[] } | undefined)?.candidate_profile_companies).slice(0, 4),
    candidateProfileHitCount: Number((diagnostics as { candidate_profile_hit_count?: number } | undefined)?.candidate_profile_hit_count || 0),
    candidateProfileOfficialHitCount: Number((diagnostics as { candidate_profile_official_hit_count?: number } | undefined)?.candidate_profile_official_hit_count || 0),
    candidateProfileSourceLabels: normalizeTextList((diagnostics as { candidate_profile_source_labels?: string[] } | undefined)?.candidate_profile_source_labels).slice(0, 4),
  };
}

export function getResearchReadinessStatus(entry: ApiKnowledgeEntry): "ready" | "degraded" | "needs_evidence" {
  const payload = entry.metadata_payload as
    | {
        report?: {
          report_readiness?: {
            status?: "ready" | "degraded" | "needs_evidence";
          };
        };
      }
    | null;
  return (payload?.report?.report_readiness?.status || "needs_evidence") as "ready" | "degraded" | "needs_evidence";
}

export function getResearchCommercialSummary(entry: ApiKnowledgeEntry): {
  accountFocus: string[];
  budgetSignal: string;
  nextAction: string;
} {
  const payload = entry.metadata_payload as
    | {
        report?: {
          commercial_summary?: {
            account_focus?: string[];
            budget_signal?: string;
            next_action?: string;
          };
        };
      }
    | null;
  return {
    accountFocus: normalizeTextList(payload?.report?.commercial_summary?.account_focus).slice(0, 3),
    budgetSignal: String(payload?.report?.commercial_summary?.budget_signal || ""),
    nextAction: String(payload?.report?.commercial_summary?.next_action || ""),
  };
}

export function getResearchWeakSectionSummary(entry: ApiKnowledgeEntry): {
  title: string;
  status: "ready" | "degraded" | "needs_evidence";
  summary: string;
} | null {
  const payload = entry.metadata_payload as
    | {
        report?: {
          sections?: Array<{
            title?: string;
            status?: "ready" | "degraded" | "needs_evidence";
            insufficiency_summary?: string;
            insufficiency_reasons?: string[];
            quota_note?: string;
            confidence_reason?: string;
          }>;
        };
      }
    | null;
  const sections = Array.isArray(payload?.report?.sections) ? payload.report.sections : [];
  const target = sections.find((section) => {
    const status = String(section?.status || "").trim();
    return status === "needs_evidence" || status === "degraded" || Boolean(section?.insufficiency_reasons?.length);
  });
  if (!target) {
    return null;
  }
  return {
    title: String(target.title || "").trim() || "关键章节",
    status: (String(target.status || "needs_evidence") as "ready" | "degraded" | "needs_evidence"),
    summary:
      String(target.insufficiency_summary || "").trim() ||
      String(target.quota_note || "").trim() ||
      String(target.confidence_reason || "").trim() ||
      "当前章节仍需继续核验。",
  };
}

export function matchesRetrievalLens(entry: ApiKnowledgeEntry, lens: ResearchRetrievalLens) {
  if (lens === "all") return true;
  const diagnostics = getResearchSourceDiagnostics(entry);
  const readiness = getResearchReadinessStatus(entry);
  const commercial = getResearchCommercialSummary(entry);
  if (lens === "high_trust") {
    return diagnostics.evidenceMode === "strong" && diagnostics.retrievalQuality !== "low";
  }
  if (lens === "official_rich") {
    return diagnostics.officialSourceRatio >= 0.35 || diagnostics.candidateProfileOfficialHitCount >= 2;
  }
  if (lens === "action_ready") {
    return readiness === "ready" || commercial.accountFocus.length > 0 || Boolean(commercial.budgetSignal || commercial.nextAction);
  }
  return readiness !== "ready" || diagnostics.evidenceMode === "fallback" || diagnostics.correctiveTriggered;
}

export function classifyResearchSourceTier(source: { domain?: string | null; source_type?: string | null; source_tier?: string | null }) {
  const domain = String(source.domain || "").toLowerCase();
  const sourceType = String(source.source_type || "").toLowerCase();
  const sourceTier = String(source.source_tier || "").toLowerCase();
  if (sourceTier === "official" || sourceTier === "aggregate" || sourceTier === "media") return sourceTier;
  if (
    sourceType === "policy" ||
    sourceType === "procurement" ||
    sourceType === "filing" ||
    domain.includes("gov.cn") ||
    domain.includes("ggzy.gov.cn") ||
    domain.includes("cninfo.com.cn") ||
    domain.includes("sec.gov") ||
    domain.includes("hkexnews.hk")
  ) {
    return "official";
  }
  if (
    sourceType === "tender_feed" ||
    domain.includes("jianyu") ||
    domain.includes("cecbid") ||
    domain.includes("cebpubservice") ||
    domain.includes("china-cpp") ||
    domain.includes("chinabidding")
  ) {
    return "aggregate";
  }
  return "media";
}

function buildFallbackRankedPreview(
  entry: ApiKnowledgeEntry,
  role: "target" | "competitor" | "partner",
) {
  const valueLabel = (score: number) => {
    if (score >= 75) return "高价值";
    if (score >= 55) return "普通价值";
    return "低价值";
  };
  const payload = (entry.metadata_payload || {}) as {
    report?: {
      keyword?: string;
      research_focus?: string;
      source_count?: number;
      sources?: Array<{ title?: string; url?: string; snippet?: string; search_query?: string; source_label?: string | null; source_tier?: string | null; source_type?: string | null; domain?: string | null }>;
      pending_target_candidates?: Array<{ name?: string; score?: number; evidence_links?: Array<{ title?: string; url?: string; source_tier?: string | null }> }>;
      pending_competitor_candidates?: Array<{ name?: string; score?: number; evidence_links?: Array<{ title?: string; url?: string; source_tier?: string | null }> }>;
      pending_partner_candidates?: Array<{ name?: string; score?: number; evidence_links?: Array<{ title?: string; url?: string; source_tier?: string | null }> }>;
    };
  };
  const report = payload.report;
  if (!report) return [];
  const normalize = (items: Array<{ name?: string; score?: number; evidence_links?: Array<{ title?: string; url?: string; source_tier?: string | null }> }> | undefined) =>
    (items || []).slice(0, 3).map((item) => ({
      name: String(item?.name || "").trim(),
      score: Number(item?.score || 0),
      score_label: valueLabel(Number(item?.score || 0)),
      evidence_links: (item?.evidence_links || []).map((link) => ({
        title: link.title || link.url || "来源待确认",
        url: link.url || "",
        source_tier: classifyResearchSourceTier(link),
      })),
    })).filter((item) => item.name);
  const sourceMap = {
    target: normalize(report.pending_target_candidates),
    competitor: normalize(report.pending_competitor_candidates),
    partner: normalize(report.pending_partner_candidates),
  };
  return sourceMap[role] || [];
}

export function getResearchRankedPreview(entry: ApiKnowledgeEntry) {
  const valueLabel = (score: number) => {
    if (score >= 75) return "高价值";
    if (score >= 55) return "普通价值";
    return "低价值";
  };
  const payload = (entry.metadata_payload || {}) as {
    report?: {
      top_target_accounts?: Array<{ name: string; score: number; evidence_links?: Array<{ title?: string; url?: string; source_tier?: string | null }> }>;
      top_competitors?: Array<{ name: string; score: number; evidence_links?: Array<{ title?: string; url?: string; source_tier?: string | null }> }>;
      top_ecosystem_partners?: Array<{ name: string; score: number; evidence_links?: Array<{ title?: string; url?: string; source_tier?: string | null }> }>;
      pending_target_candidates?: Array<{ name?: string; score?: number; evidence_links?: Array<{ title?: string; url?: string; source_tier?: string | null }> }>;
      pending_competitor_candidates?: Array<{ name?: string; score?: number; evidence_links?: Array<{ title?: string; url?: string; source_tier?: string | null }> }>;
      pending_partner_candidates?: Array<{ name?: string; score?: number; evidence_links?: Array<{ title?: string; url?: string; source_tier?: string | null }> }>;
    };
  };
  const report = payload.report;
  if (!report) return [];
  const normalize = (items: Array<{ name: string; score: number; evidence_links?: Array<{ title?: string; url?: string; source_tier?: string | null }> }> | undefined) =>
    (items || []).slice(0, 3).map((item) => ({
      name: item.name,
      score: item.score,
      score_label: valueLabel(Number(item.score || 0)),
      evidence_links: (item.evidence_links || []).map((link) => ({
        title: link.title || link.url || "来源待确认",
        url: link.url || "",
        source_tier: classifyResearchSourceTier(link),
      })),
    }));
  return [
    {
      key: "target",
      title: normalize(report.top_target_accounts).length ? "甲方" : "待核验甲方",
      items: normalize(report.top_target_accounts).length ? normalize(report.top_target_accounts) : buildFallbackRankedPreview(entry, "target"),
    },
    {
      key: "competitor",
      title: normalize(report.top_competitors).length ? "竞品" : "待核验竞品",
      items: normalize(report.top_competitors).length ? normalize(report.top_competitors) : buildFallbackRankedPreview(entry, "competitor"),
    },
    {
      key: "partner",
      title: normalize(report.top_ecosystem_partners).length ? "伙伴" : "待核验伙伴",
      items: normalize(report.top_ecosystem_partners).length ? normalize(report.top_ecosystem_partners) : buildFallbackRankedPreview(entry, "partner"),
    },
  ].filter((group) => group.items.length);
}

export function qualityLabel(value: string) {
  if (value === "high") return "高";
  if (value === "medium") return "中";
  return "低";
}

export function qualityTone(value: string) {
  if (value === "high") return "af-chip af-chip-success";
  if (value === "medium") return "af-chip af-chip-warning";
  return "af-chip";
}

export function trackingStatusLabel(value?: string | null) {
  if (value === "running") return "刷新中";
  if (value === "succeeded") return "刷新成功";
  if (value === "failed") return "刷新失败";
  return "待刷新";
}

export function trackingStatusTone(value?: string | null) {
  if (value === "running") return "af-chip af-chip-info";
  if (value === "succeeded") return "af-chip af-chip-success";
  if (value === "failed") return "af-chip af-chip-danger";
  return "af-chip";
}

export function lowQualityReviewStatusLabel(status: ApiResearchLowQualityReviewQueueItem["review_status"]) {
  if (status === "rewritten") return "待验收";
  if (status === "accepted") return "已接受";
  if (status === "reverted") return "已回退";
  return "待处理";
}

export function lowQualityReviewStatusTone(status: ApiResearchLowQualityReviewQueueItem["review_status"]) {
  if (status === "rewritten") return "af-chip af-chip-info";
  if (status === "accepted") return "af-chip af-chip-success";
  if (status === "reverted") return "af-chip af-chip-warning";
  return "af-chip af-chip-danger";
}

export function offlineEvaluationStatusLabel(status: string) {
  if (status === "good") return "达标";
  if (status === "watch") return "观察";
  return "偏弱";
}

export function offlineEvaluationStatusTone(status: string) {
  if (status === "good") return "af-state-panel-success";
  if (status === "watch") return "af-state-panel-warning";
  return "af-state-panel-danger";
}

export function experimentLaneStatusLabel(status: string) {
  if (status === "ready") return "候选占优";
  if (status === "insufficient") return "样本不足";
  return "继续观察";
}

export function experimentLaneStatusTone(status: string) {
  if (status === "ready") return "af-chip af-chip-success";
  if (status === "insufficient") return "af-chip";
  return "af-chip af-chip-warning";
}

export function runtimeCacheHealthLabel(status?: string | null) {
  if (status === "warm") return "热缓存";
  if (status === "warming") return "预热中";
  if (status === "stale") return "需恢复";
  return "冷启动";
}

export function runtimeCacheHealthTone(status?: string | null) {
  if (status === "warm") return "af-chip af-chip-success";
  if (status === "warming") return "af-chip af-chip-info";
  if (status === "stale") return "af-chip af-chip-danger";
  return "af-chip";
}

export function exportDeltaTrendTone(status: string) {
  if (status === "up") return "af-state-text-success";
  if (status === "down") return "af-state-text-danger";
  return "text-[var(--af-text-tertiary)]";
}

export function experimentPlanStatusLabel(status: ApiResearchExperimentPlan["status"]) {
  if (status === "cohort_frozen") return "样本已冻结";
  if (status === "baseline_locked") return "版本已锁定";
  if (status === "gate_allowed") return "已放行";
  if (status === "gate_hold") return "待观察";
  if (status === "gate_blocked") return "已阻塞";
  if (status === "rollout_promoted") return "已确认";
  if (status === "rollout_revoked") return "已撤回";
  return "草稿";
}

export function experimentPlanStatusTone(status: ApiResearchExperimentPlan["status"]) {
  if (status === "rollout_promoted") return "af-chip af-chip-success";
  if (status === "rollout_revoked") return "af-chip";
  if (status === "gate_allowed") return "af-chip af-chip-success";
  if (status === "gate_blocked") return "af-chip af-chip-danger";
  if (status === "gate_hold") return "af-chip af-chip-warning";
  if (status === "baseline_locked") return "af-chip af-chip-info";
  if (status === "cohort_frozen") return "af-chip af-chip-info";
  return "af-chip";
}

export function experimentGateDecisionLabel(decision?: string | null) {
  if (decision === "allow") return "允许发布";
  if (decision === "block") return "暂不发布";
  if (decision === "hold") return "继续观察";
  return "尚未判定";
}

export function experimentGateDecisionTone(decision?: string | null) {
  if (decision === "allow") return "af-chip af-chip-success";
  if (decision === "block") return "af-chip af-chip-danger";
  if (decision === "hold") return "af-chip af-chip-warning";
  return "af-chip";
}

export function experimentRuntimeStatusLabel(status?: string | null) {
  if (status === "ready") return "可接入";
  if (status === "degraded") return "有告警";
  return "未启用";
}

export function experimentRuntimeStatusTone(status?: string | null) {
  if (status === "ready") return "af-chip af-chip-success";
  if (status === "degraded") return "af-chip af-chip-warning";
  return "af-chip";
}

export function watchlistAutomationStatusLabel(status?: string | null) {
  if (status === "ok") return "最近运行正常";
  if (status === "partial_failure") return "最近运行部分失败";
  if (status === "failed") return "最近运行失败";
  return "尚无自动巡检记录";
}

export function watchlistAutomationStatusTone(status?: string | null) {
  if (status === "ok") return "af-chip af-chip-success";
  if (status === "partial_failure") return "af-chip af-chip-warning";
  if (status === "failed") return "af-chip af-chip-danger";
  return "af-chip";
}

export function watchlistAutomationAlertLabel(level?: string | null) {
  if (level === "high") return "需要人工干预";
  if (level === "medium") return "建议尽快检查";
  return "自动巡检正常";
}

export function watchlistAutomationAlertTone(level?: string | null) {
  if (level === "high") return "af-chip af-chip-danger";
  if (level === "medium") return "af-chip af-chip-warning";
  return "af-chip af-chip-success";
}

export function formatWatchlistAge(seconds?: number | null) {
  const value = Number(seconds || 0);
  if (!Number.isFinite(value) || value <= 0) return "刚刚";
  if (value < 60) return `${value} 秒`;
  if (value < 3600) return `${Math.round(value / 60)} 分钟`;
  if (value < 86400) return `${Math.round(value / 3600)} 小时`;
  return `${Math.round(value / 86400)} 天`;
}

export function watchlistStatusLabel(status: ApiResearchWatchlist["status"]) {
  return status === "paused" ? "已暂停" : "运行中";
}

export function watchlistStatusTone(status: ApiResearchWatchlist["status"]) {
  return status === "paused" ? "af-chip" : "af-chip af-chip-success";
}

export function watchlistRunItemStatusLabel(status: ApiResearchWatchlistRunDueResponse["items"][number]["status"]) {
  return status === "refreshed" ? "已刷新" : "失败";
}

export function watchlistRunItemStatusTone(status: ApiResearchWatchlistRunDueResponse["items"][number]["status"]) {
  return status === "refreshed" ? "af-chip af-chip-success" : "af-chip af-chip-danger";
}

export function normalizeResearchEntry(entry: ApiKnowledgeEntry): ResearchCenterEntry {
  const facets = getResearchFacets(entry);
  return {
    ...entry,
    region_label: facets.region,
    industry_label: facets.industry,
    action_type_label: facets.actionType,
  };
}

export function buildTopicWorkspaceHref(topicId: string) {
  return `/research/topics/${topicId}`;
}

export function buildMarkdownArchiveHref(archiveId: string) {
  return `/research/archives/${archiveId}`;
}

export type { ResearchPerspective };
