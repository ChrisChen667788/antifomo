"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ApiMobileDailyBrief,
  ApiKnowledgeEntry,
  ApiResearchCompareSnapshot,
  ApiResearchLowQualityReviewQueue,
  ApiResearchLowQualityReviewQueueItem,
  ApiResearchMarkdownArchive,
  ApiResearchOfflineEvaluation,
  ApiResearchSavedView,
  ApiResearchSourceSettings,
  ApiResearchTrackingTopic,
  ApiResearchWatchlist,
  ApiResearchWatchlistAutomationStatus,
  ApiResearchWatchlistRunDueResponse,
  createResearchWatchlist,
  deleteResearchCompareSnapshot,
  deleteResearchMarkdownArchive,
  deleteResearchTrackingTopic,
  deleteResearchView,
  getLowQualityResearchReviewQueue,
  getResearchDailyBrief,
  getResearchMarkdownArchive,
  getResearchOfflineEvaluation,
  getResearchWatchlistAutomationStatus,
  listResearchWatchlists,
  getResearchSourceSettings,
  getResearchWorkspace,
  listKnowledgeEntries,
  refreshResearchWatchlist,
  refreshResearchTrackingTopic,
  resolveLowQualityResearchReviewItem,
  rewriteLowQualityResearchReviewItem,
  runDueResearchWatchlists,
  saveResearchTrackingTopic,
  saveResearchView,
  updateResearchWatchlist,
  updateResearchSourceSettings,
} from "@/lib/api";
import {
  buildFacetOptions,
  getResearchFacets,
  getResearchPerspectiveScore,
  type ResearchPerspective,
} from "@/lib/research-facets";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { ResearchArchiveSectionLinkPopover } from "@/components/research/research-archive-section-link-popover";
import { ResearchConsolePanel } from "@/components/research/research-console-panel";
import { AppIcon } from "@/components/ui/app-icon";
import { dedupeTextList } from "@/lib/display-list";
import { getGuardedRewriteReasonLabels, isGuardedBacklog } from "@/lib/research-diagnostics";
import {
  archiveDeliveryMetricToneClassName,
  buildArchiveDeliveryDigest,
  buildArchiveDeliveryScore,
} from "@/lib/research-archive-metadata";
import { sanitizeExternalDisplayText } from "@/lib/commercial-risk-copy";

type ResearchFilter = "all" | "reports" | "actions";
type ResearchRetrievalLens = "all" | "high_trust" | "official_rich" | "action_ready" | "needs_review";
type ArchiveDeliveryFilter = "all" | "strong_evidence" | "needs_followup" | "official_rich";
type ArchiveSortMode = "updated_desc" | "evidence_strength" | "outstanding_count" | "official_ratio";

type ResearchCenterActionCard = {
  title: string;
  target_persona?: string;
  execution_window?: string;
  deliverable?: string;
  recommended_steps?: string[];
};

const WATCHLIST_SCHEDULE_OPTIONS = [
  { value: "manual", fallback: "手动" },
  { value: "daily", fallback: "每日" },
  { value: "twice_daily", fallback: "每日两次" },
  { value: "weekdays", fallback: "工作日" },
  { value: "every_6h", fallback: "每 6 小时" },
] as const;

function sortEntries<T extends ApiKnowledgeEntry>(items: T[]): T[] {
  return [...items].sort((left, right) => {
    const leftTime = new Date(left.updated_at || left.created_at).getTime();
    const rightTime = new Date(right.updated_at || right.created_at).getTime();
    return rightTime - leftTime;
  });
}

function formatWatchlistSchedule(schedule: string, t: (key: string, fallback: string) => string) {
  const normalized = String(schedule || "manual");
  const matched = WATCHLIST_SCHEDULE_OPTIONS.find((item) => item.value === normalized);
  return matched ? t(`research.watchlistSchedule.${matched.value}`, matched.fallback) : normalized;
}

function formatWatchlistTime(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString();
}

function formatAutomationInterval(seconds?: number) {
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

function normalizeTextList(values: unknown): string[] {
  return dedupeTextList(values as Iterable<unknown>);
}

function parseActionPhases(steps: string[] | undefined) {
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

function getResearchActionCards(entry: ApiKnowledgeEntry): ResearchCenterActionCard[] {
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

function buildPreview(entry: ApiKnowledgeEntry): string {
  const report = (entry.metadata_payload as { report?: { executive_summary?: string } } | null)?.report;
  const summary = report?.executive_summary || entry.content || "";
  return summary.length > 110 ? `${summary.slice(0, 109).trim()}…` : summary;
}

function getActionType(entry: ApiKnowledgeEntry): string {
  const payload = entry.metadata_payload as { card?: { action_type?: string } } | null;
  return payload?.card?.action_type || "";
}

function getResearchKeyword(entry: ApiKnowledgeEntry): string {
  const payload = entry.metadata_payload as
    | {
        report?: { keyword?: string };
        keyword?: string;
      }
    | null;
  return payload?.report?.keyword || payload?.keyword || "";
}

function getResearchSourceCount(entry: ApiKnowledgeEntry): number {
  const payload = entry.metadata_payload as
    | {
        report?: { source_count?: number };
      }
    | null;
  return Number(payload?.report?.source_count || 0);
}

function getResearchReportMeta(
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

function getResearchSourceDiagnostics(entry: ApiKnowledgeEntry): {
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

function getResearchReadinessStatus(entry: ApiKnowledgeEntry): "ready" | "degraded" | "needs_evidence" {
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

function getResearchCommercialSummary(entry: ApiKnowledgeEntry): {
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

function getResearchWeakSectionSummary(entry: ApiKnowledgeEntry): {
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
      "当前章节仍需继续补证。",
  };
}

function matchesRetrievalLens(entry: ApiKnowledgeEntry, lens: ResearchRetrievalLens) {
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

function classifyResearchSourceTier(source: { domain?: string | null; source_type?: string | null; source_tier?: string | null }) {
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

function getResearchRankedPreview(entry: ApiKnowledgeEntry) {
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
      title: normalize(report.top_target_accounts).length ? "甲方" : "待补证甲方",
      items: normalize(report.top_target_accounts).length ? normalize(report.top_target_accounts) : buildFallbackRankedPreview(entry, "target"),
    },
    {
      key: "competitor",
      title: normalize(report.top_competitors).length ? "竞品" : "待补证竞品",
      items: normalize(report.top_competitors).length ? normalize(report.top_competitors) : buildFallbackRankedPreview(entry, "competitor"),
    },
    {
      key: "partner",
      title: normalize(report.top_ecosystem_partners).length ? "伙伴" : "待补证伙伴",
      items: normalize(report.top_ecosystem_partners).length ? normalize(report.top_ecosystem_partners) : buildFallbackRankedPreview(entry, "partner"),
    },
  ].filter((group) => group.items.length);
}

function qualityLabel(value: string) {
  if (value === "high") return "高";
  if (value === "medium") return "中";
  return "低";
}

function qualityTone(value: string) {
  if (value === "high") return "bg-emerald-100 text-emerald-700";
  if (value === "medium") return "bg-amber-100 text-amber-700";
  return "bg-slate-100 text-slate-500";
}

function trackingStatusLabel(value?: string | null) {
  if (value === "running") return "刷新中";
  if (value === "succeeded") return "刷新成功";
  if (value === "failed") return "刷新失败";
  return "待刷新";
}

function trackingStatusTone(value?: string | null) {
  if (value === "running") return "bg-sky-100 text-sky-700";
  if (value === "succeeded") return "bg-emerald-100 text-emerald-700";
  if (value === "failed") return "bg-rose-100 text-rose-700";
  return "bg-slate-100 text-slate-500";
}

function lowQualityReviewStatusLabel(status: ApiResearchLowQualityReviewQueueItem["review_status"]) {
  if (status === "rewritten") return "待验收";
  if (status === "accepted") return "已接受";
  if (status === "reverted") return "已回退";
  return "待处理";
}

function lowQualityReviewStatusTone(status: ApiResearchLowQualityReviewQueueItem["review_status"]) {
  if (status === "rewritten") return "bg-sky-100 text-sky-700";
  if (status === "accepted") return "bg-emerald-100 text-emerald-700";
  if (status === "reverted") return "bg-amber-100 text-amber-700";
  return "bg-rose-100 text-rose-700";
}

function offlineEvaluationStatusLabel(status: string) {
  if (status === "good") return "达标";
  if (status === "watch") return "观察";
  return "偏弱";
}

function offlineEvaluationStatusTone(status: string) {
  if (status === "good") return "border-emerald-200 bg-emerald-50/75 text-emerald-700";
  if (status === "watch") return "border-amber-200 bg-amber-50/75 text-amber-700";
  return "border-rose-200 bg-rose-50/75 text-rose-700";
}

function watchlistAutomationStatusLabel(status?: string | null) {
  if (status === "ok") return "最近运行正常";
  if (status === "partial_failure") return "最近运行部分失败";
  if (status === "failed") return "最近运行失败";
  return "尚无自动巡检记录";
}

function watchlistAutomationStatusTone(status?: string | null) {
  if (status === "ok") return "bg-emerald-50 text-emerald-700";
  if (status === "partial_failure") return "bg-amber-50 text-amber-700";
  if (status === "failed") return "bg-rose-50 text-rose-700";
  return "bg-slate-100 text-slate-600";
}

function watchlistAutomationAlertLabel(level?: string | null) {
  if (level === "high") return "需要人工干预";
  if (level === "medium") return "建议尽快检查";
  return "自动巡检正常";
}

function watchlistAutomationAlertTone(level?: string | null) {
  if (level === "high") return "bg-rose-100 text-rose-700";
  if (level === "medium") return "bg-amber-100 text-amber-700";
  return "bg-emerald-100 text-emerald-700";
}

function formatWatchlistAge(seconds?: number | null) {
  const value = Number(seconds || 0);
  if (!Number.isFinite(value) || value <= 0) return "刚刚";
  if (value < 60) return `${value} 秒`;
  if (value < 3600) return `${Math.round(value / 60)} 分钟`;
  if (value < 86400) return `${Math.round(value / 3600)} 小时`;
  return `${Math.round(value / 86400)} 天`;
}

function watchlistStatusLabel(status: ApiResearchWatchlist["status"]) {
  return status === "paused" ? "已暂停" : "运行中";
}

function watchlistStatusTone(status: ApiResearchWatchlist["status"]) {
  return status === "paused" ? "bg-slate-100 text-slate-600" : "bg-emerald-50 text-emerald-700";
}

function watchlistRunItemStatusLabel(status: ApiResearchWatchlistRunDueResponse["items"][number]["status"]) {
  return status === "refreshed" ? "已刷新" : "失败";
}

function watchlistRunItemStatusTone(status: ApiResearchWatchlistRunDueResponse["items"][number]["status"]) {
  return status === "refreshed" ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700";
}

type ResearchCenterEntry = ApiKnowledgeEntry & {
  region_label: string;
  industry_label: string;
  action_type_label: string;
};

function normalizeResearchEntry(entry: ApiKnowledgeEntry): ResearchCenterEntry {
  const facets = getResearchFacets(entry);
  return {
    ...entry,
    region_label: facets.region,
    industry_label: facets.industry,
    action_type_label: facets.actionType,
  };
}

function buildTopicWorkspaceHref(topicId: string) {
  return `/research/topics/${topicId}`;
}

function buildMarkdownArchiveHref(archiveId: string) {
  return `/research/archives/${archiveId}`;
}

function markdownArchiveKindLabel(kind: ApiResearchMarkdownArchive["archive_kind"]) {
  if (kind === "topic_version_recap") return "版本复盘";
  if (kind === "archive_diff_recap") return "差异复盘";
  return "Compare 导出";
}

function markdownArchiveKindTone(kind: ApiResearchMarkdownArchive["archive_kind"]) {
  if (kind === "topic_version_recap") return "bg-amber-50 text-amber-700";
  if (kind === "archive_diff_recap") return "bg-emerald-50 text-emerald-700";
  return "bg-sky-50 text-sky-700";
}

export function ResearchCenter() {
  const { t } = useAppPreferences();
  const [filter, setFilter] = useState<ResearchFilter>("all");
  const [retrievalLens, setRetrievalLens] = useState<ResearchRetrievalLens>("all");
  const [perspective, setPerspective] = useState<ResearchPerspective>("all");
  const [focusOnly, setFocusOnly] = useState(false);
  const [queryDraft, setQueryDraft] = useState("");
  const [query, setQuery] = useState("");
  const [regionFilter, setRegionFilter] = useState("");
  const [industryFilter, setIndustryFilter] = useState("");
  const [actionTypeFilter, setActionTypeFilter] = useState("");
  const [reports, setReports] = useState<ResearchCenterEntry[]>([]);
  const [actions, setActions] = useState<ResearchCenterEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sourceSettings, setSourceSettings] = useState<ApiResearchSourceSettings | null>(null);
  const [sourceSaving, setSourceSaving] = useState(false);
  const [sourceError, setSourceError] = useState("");
  const [savedViews, setSavedViews] = useState<ApiResearchSavedView[]>([]);
  const [trackingTopics, setTrackingTopics] = useState<ApiResearchTrackingTopic[]>([]);
  const [compareSnapshots, setCompareSnapshots] = useState<ApiResearchCompareSnapshot[]>([]);
  const [markdownArchives, setMarkdownArchives] = useState<ApiResearchMarkdownArchive[]>([]);
  const [watchlists, setWatchlists] = useState<ApiResearchWatchlist[]>([]);
  const [watchlistAutomation, setWatchlistAutomation] = useState<ApiResearchWatchlistAutomationStatus | null>(null);
  const [dailyBrief, setDailyBrief] = useState<ApiMobileDailyBrief | null>(null);
  const [dailyBriefLoading, setDailyBriefLoading] = useState(true);
  const [dailyBriefRefreshing, setDailyBriefRefreshing] = useState(false);
  const [dailyBriefError, setDailyBriefError] = useState("");
  const [lowQualityQueue, setLowQualityQueue] = useState<ApiResearchLowQualityReviewQueue | null>(null);
  const [lowQualityLoading, setLowQualityLoading] = useState(true);
  const [offlineEvaluation, setOfflineEvaluation] = useState<ApiResearchOfflineEvaluation | null>(null);
  const [offlineEvaluationLoading, setOfflineEvaluationLoading] = useState(true);
  const [offlineEvaluationRefreshing, setOfflineEvaluationRefreshing] = useState(false);
  const [lowQualityActionKey, setLowQualityActionKey] = useState("");
  const [lowQualityMessage, setLowQualityMessage] = useState("");
  const [lowQualityError, setLowQualityError] = useState("");
  const [workspaceSaving, setWorkspaceSaving] = useState(false);
  const [refreshingTopicId, setRefreshingTopicId] = useState<string>("");
  const [refreshingWatchlistId, setRefreshingWatchlistId] = useState<string>("");
  const [runningDueWatchlists, setRunningDueWatchlists] = useState(false);
  const [watchlistActionKey, setWatchlistActionKey] = useState("");
  const [watchlistMessage, setWatchlistMessage] = useState("");
  const [watchlistError, setWatchlistError] = useState("");
  const [lastRunDueResult, setLastRunDueResult] = useState<ApiResearchWatchlistRunDueResponse | null>(null);
  const [archiveLinkMessage, setArchiveLinkMessage] = useState("");
  const [archiveDeliveryFilter, setArchiveDeliveryFilter] = useState<ArchiveDeliveryFilter>("all");
  const [archiveSortMode, setArchiveSortMode] = useState<ArchiveSortMode>("updated_desc");

  useEffect(() => {
    let active = true;
    getResearchSourceSettings()
      .then((res) => {
        if (!active) return;
        setSourceSettings(res);
        setSourceError("");
      })
      .catch(() => {
        if (!active) return;
        setSourceError("研究来源设置暂时无法从后端读取，当前先使用本地安全默认值。");
        setSourceSettings({
          enable_jianyu_tender_feed: true,
          enable_yuntoutiao_feed: true,
          enable_ggzy_feed: true,
          enable_cecbid_feed: true,
          enable_ccgp_feed: true,
          enable_gov_policy_feed: true,
          enable_local_ggzy_feed: true,
          enable_curated_wechat_channels: true,
          enabled_source_labels: ["剑鱼标讯", "云头条", "全国公共资源交易平台", "中国招标投标网", "政府采购合规聚合", "中国政府网政策/讲话", "地方公共资源交易平台", "精选公众号观察池"],
          connector_statuses: [
            {
              key: "public_open_source_adapters",
              label: "公开招采与行业源适配器",
              status: "active",
              detail: "当前已接入公开招投标、政策讲话、行业媒体与聚合源；不绕过登录墙和付费墙。",
              requires_authorization: false,
            },
            {
              key: "curated_wechat_channels",
              label: "精选公众号观察池",
              status: "active",
              detail: "优先补充公众号观察池，当前包含 云技术 / 智能超参数 / 数说123之算力大模型。",
              requires_authorization: false,
            },
          ],
          updated_at: null,
        });
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    getResearchWorkspace()
      .then((res) => {
        if (!active) return;
        setSavedViews(res.saved_views || []);
        setTrackingTopics(res.tracking_topics || []);
        setCompareSnapshots(res.compare_snapshots || []);
        setMarkdownArchives(res.markdown_archives || []);
      })
      .catch(() => {
        if (!active) return;
        setSavedViews([]);
        setTrackingTopics([]);
        setCompareSnapshots([]);
        setMarkdownArchives([]);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    listResearchWatchlists()
      .then((res) => {
        if (!active) return;
        setWatchlists(res || []);
      })
      .catch(() => {
        if (!active) return;
        setWatchlists([]);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    getResearchWatchlistAutomationStatus()
      .then((res) => {
        if (!active) return;
        setWatchlistAutomation(res);
      })
      .catch(() => {
        if (!active) return;
        setWatchlistAutomation(null);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    setDailyBriefLoading(true);
    setDailyBriefError("");
    getResearchDailyBrief(false)
      .then((res) => {
        if (!active) return;
        setDailyBrief(res);
      })
      .catch(() => {
        if (!active) return;
        setDailyBrief(null);
        setDailyBriefError("Daily Brief 加载失败，请稍后重试。");
      })
      .finally(() => {
        if (!active) return;
        setDailyBriefLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    setLowQualityLoading(true);
    getLowQualityResearchReviewQueue(12)
      .then((res) => {
        if (!active) return;
        setLowQualityQueue(res);
      })
      .catch(() => {
        if (!active) return;
        setLowQualityQueue(null);
      })
      .finally(() => {
        if (!active) return;
        setLowQualityLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    setOfflineEvaluationLoading(true);
    getResearchOfflineEvaluation(6)
      .then((res) => {
        if (!active) return;
        setOfflineEvaluation(res);
      })
      .catch(() => {
        if (!active) return;
        setOfflineEvaluation(null);
      })
      .finally(() => {
        if (!active) return;
        setOfflineEvaluationLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    Promise.all([
      listKnowledgeEntries(40, {
        sourceDomain: "research.report",
        query: query || undefined,
        focusReferenceOnly: focusOnly,
      }),
      listKnowledgeEntries(60, {
        sourceDomain: "research.action_card",
        query: query || undefined,
        focusReferenceOnly: focusOnly,
      }),
    ])
      .then(([reportRes, actionRes]) => {
        if (!active) return;
        setReports(sortEntries((reportRes.items || []).map(normalizeResearchEntry)));
        setActions(sortEntries((actionRes.items || []).map(normalizeResearchEntry)));
      })
      .catch(() => {
        if (!active) return;
        setReports([]);
        setActions([]);
        setError(t("research.centerLoadFailed", "商机情报中心加载失败，请稍后重试"));
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [focusOnly, query, t]);

  const refreshResearchCards = async () => {
    const [reportRes, actionRes] = await Promise.all([
      listKnowledgeEntries(40, {
        sourceDomain: "research.report",
        query: query || undefined,
        focusReferenceOnly: focusOnly,
      }),
      listKnowledgeEntries(60, {
        sourceDomain: "research.action_card",
        query: query || undefined,
        focusReferenceOnly: focusOnly,
      }),
    ]);
    setReports(sortEntries((reportRes.items || []).map(normalizeResearchEntry)));
    setActions(sortEntries((actionRes.items || []).map(normalizeResearchEntry)));
  };

  const refreshLowQualityQueue = async () => {
    const queue = await getLowQualityResearchReviewQueue(12);
    setLowQualityQueue(queue);
    return queue;
  };

  const refreshOfflineEvaluation = async () => {
    setOfflineEvaluationRefreshing(true);
    try {
      const evaluation = await getResearchOfflineEvaluation(6);
      setOfflineEvaluation(evaluation);
      return evaluation;
    } finally {
      setOfflineEvaluationLoading(false);
      setOfflineEvaluationRefreshing(false);
    }
  };

  const handleRefreshDailyBrief = async () => {
    setDailyBriefRefreshing(true);
    setDailyBriefError("");
    try {
      const brief = await getResearchDailyBrief(true);
      setDailyBrief(brief);
    } catch {
      setDailyBriefError("Daily Brief 刷新失败，请稍后重试。");
    } finally {
      setDailyBriefRefreshing(false);
      setDailyBriefLoading(false);
    }
  };

  const handleRewriteLowQualityItem = async (entryId: string) => {
    setLowQualityActionKey(`${entryId}:rewrite`);
    setLowQualityMessage("");
    setLowQualityError("");
    try {
      await rewriteLowQualityResearchReviewItem(entryId);
      await Promise.all([refreshLowQualityQueue(), refreshResearchCards(), refreshOfflineEvaluation()]);
      setLowQualityMessage("已生成 rewrite diff，请复核后接受或回退。");
    } catch {
      setLowQualityError("低质量研报重写失败，请稍后重试。");
    } finally {
      setLowQualityActionKey("");
    }
  };

  const handleResolveLowQualityItem = async (entryId: string, action: "accept" | "revert") => {
    setLowQualityActionKey(`${entryId}:${action}`);
    setLowQualityMessage("");
    setLowQualityError("");
    try {
      await resolveLowQualityResearchReviewItem(entryId, action);
      await Promise.all([refreshLowQualityQueue(), refreshOfflineEvaluation()]);
      if (action === "revert") {
        await refreshResearchCards();
        setLowQualityMessage("已回退到 rewrite 前版本。");
      } else {
        setLowQualityMessage("已接受当前 rewrite 结果。");
      }
    } catch {
      setLowQualityError(action === "accept" ? "接受 rewrite 结果失败，请稍后重试。" : "回退失败，当前记录缺少可恢复快照。");
    } finally {
      setLowQualityActionKey("");
    }
  };

  const allItems = useMemo(() => sortEntries([...reports, ...actions]), [actions, reports]);

  const regionOptions = useMemo(
    () => buildFacetOptions(allItems.map((item) => item.region_label), t("research.centerRegionAll", "全部区域")),
    [allItems, t],
  );
  const industryOptions = useMemo(
    () =>
      buildFacetOptions(
        allItems.map((item) => item.industry_label),
        t("research.centerIndustryAll", "全部行业"),
      ),
    [allItems, t],
  );
  const actionTypeOptions = useMemo(
    () =>
      buildFacetOptions(
        actions.map((item) => item.action_type_label),
        t("research.centerActionTypeAll", "全部动作类型"),
      ),
    [actions, t],
  );

  const visibleItems = useMemo(() => {
    let baseItems: ResearchCenterEntry[] = allItems;
    if (filter === "reports") baseItems = reports;
    if (filter === "actions") baseItems = actions;
    return baseItems
      .filter((item) => {
        if (regionFilter && item.region_label !== regionFilter) return false;
        if (industryFilter && item.industry_label !== industryFilter) return false;
        if (actionTypeFilter) {
          if (item.source_domain !== "research.action_card") return false;
          if (item.action_type_label !== actionTypeFilter) return false;
        }
        if (!matchesRetrievalLens(item, retrievalLens)) return false;
        return getResearchPerspectiveScore(item, perspective) > 0;
      })
      .sort((left, right) => {
        const scoreGap = getResearchPerspectiveScore(right, perspective) - getResearchPerspectiveScore(left, perspective);
        if (scoreGap !== 0) return scoreGap;
        return new Date(right.updated_at || right.created_at).getTime() - new Date(left.updated_at || left.created_at).getTime();
      });
  }, [actionTypeFilter, allItems, filter, industryFilter, perspective, regionFilter, reports, actions, retrievalLens]);

  const visibleMarkdownArchives = useMemo(() => {
    return markdownArchives
      .map((archive) => ({
        archive,
        digest: buildArchiveDeliveryDigest(archive),
        score: buildArchiveDeliveryScore(archive),
      }))
      .filter(({ score }) => {
        if (archiveDeliveryFilter === "strong_evidence") {
          return score.hasEvidenceSignal && score.evidenceStrength >= 18 && score.outstandingCount <= 1;
        }
        if (archiveDeliveryFilter === "needs_followup") {
          return score.outstandingCount > 0;
        }
        if (archiveDeliveryFilter === "official_rich") {
          return score.hasEvidenceSignal && score.officialRatio >= 0.45 && score.officialCount > 0;
        }
        return true;
      })
      .sort((left, right) => {
        if (archiveSortMode === "evidence_strength" && right.score.evidenceStrength !== left.score.evidenceStrength) {
          return right.score.evidenceStrength - left.score.evidenceStrength;
        }
        if (archiveSortMode === "outstanding_count" && right.score.outstandingCount !== left.score.outstandingCount) {
          return right.score.outstandingCount - left.score.outstandingCount;
        }
        if (archiveSortMode === "official_ratio" && right.score.officialRatio !== left.score.officialRatio) {
          return right.score.officialRatio - left.score.officialRatio;
        }
        return new Date(right.archive.updated_at).getTime() - new Date(left.archive.updated_at).getTime();
      });
  }, [archiveDeliveryFilter, archiveSortMode, markdownArchives]);

  const filterMeta = [
    { key: "all" as const, label: t("research.centerFilterAll", "全部"), count: reports.length + actions.length },
    { key: "reports" as const, label: t("research.centerFilterReports", "研报"), count: reports.length },
    { key: "actions" as const, label: t("research.centerFilterActions", "行动卡"), count: actions.length },
  ];

  const archiveFilterMeta: Array<{ key: ArchiveDeliveryFilter; label: string }> = [
    { key: "all", label: t("research.archiveFilterAll", "全部归档") },
    { key: "strong_evidence", label: t("research.archiveFilterStrongEvidence", "证据较强") },
    { key: "needs_followup", label: t("research.archiveFilterNeedsFollowup", "待补证较多") },
    { key: "official_rich", label: t("research.archiveFilterOfficialRich", "官方源占比较高") },
  ];

  const archiveSortMeta: Array<{ key: ArchiveSortMode; label: string }> = [
    { key: "updated_desc", label: t("research.archiveSortUpdated", "按更新时间") },
    { key: "evidence_strength", label: t("research.archiveSortEvidence", "按证据强度") },
    { key: "outstanding_count", label: t("research.archiveSortOutstanding", "按待补证数量") },
    { key: "official_ratio", label: t("research.archiveSortOfficialRatio", "按官方源占比") },
  ];

  const perspectiveMeta: Array<{ key: ResearchPerspective; label: string; desc: string }> = [
    {
      key: "all",
      label: t("research.centerViewAll", "全部视角"),
      desc: t("research.centerViewAllDesc", "综合查看全部研报与行动卡"),
    },
    {
      key: "regional",
      label: t("research.centerViewRegional", "区域情报"),
      desc: t("research.centerViewRegionalDesc", "优先看地区、区域和分层推进线索"),
    },
    {
      key: "client_followup",
      label: t("research.centerViewClient", "甲方跟进"),
      desc: t("research.centerViewClientDesc", "聚焦甲方角色、拜访和销售推进"),
    },
    {
      key: "bidding",
      label: t("research.centerViewBidding", "投标排期"),
      desc: t("research.centerViewBiddingDesc", "集中看预算、采购、中标和项目分期"),
    },
    {
      key: "ecosystem",
      label: t("research.centerViewEcosystem", "生态合作"),
      desc: t("research.centerViewEcosystemDesc", "查看伙伴、渠道、联合交付与竞合"),
    },
  ];

  const activePerspective = perspectiveMeta.find((item) => item.key === perspective) || perspectiveMeta[0];

  const overviewStats = [
    {
      label: t("research.centerMetricAll", "总卡片"),
      value: String(allItems.length),
      tone: "text-slate-900",
      detail: "当前工作区中的全部研报与行动卡",
    },
    {
      label: t("research.centerMetricReports", "研报"),
      value: String(reports.length),
      tone: "text-sky-700",
      detail: "已沉淀的关键词研究与专题研报",
    },
    {
      label: t("research.centerMetricActions", "行动卡"),
      value: String(actions.length),
      tone: "text-amber-700",
      detail: "可以直接下发的推进建议与动作包",
    },
    {
      label: t("research.centerMetricFocus", "Focus 参考"),
      value: String(allItems.filter((item) => item.is_focus_reference).length),
      tone: "text-emerald-700",
      detail: "已回流到 Focus 的研究素材",
    },
  ];
  const retrievalLensMeta: Array<{ key: ResearchRetrievalLens; label: string; desc: string; count: number }> = [
    {
      key: "all",
      label: "全部",
      desc: "综合查看全部研报与行动卡",
      count: allItems.length,
    },
    {
      key: "high_trust",
      label: "高可信",
      desc: "优先看强证据和较稳的检索结果",
      count: allItems.filter((item) => matchesRetrievalLens(item, "high_trust")).length,
    },
    {
      key: "official_rich",
      label: "官方源强",
      desc: "优先看官方源占比和官方补证更强的条目",
      count: allItems.filter((item) => matchesRetrievalLens(item, "official_rich")).length,
    },
    {
      key: "action_ready",
      label: "可推进",
      desc: "更接近可推进账户与机会信号",
      count: allItems.filter((item) => matchesRetrievalLens(item, "action_ready")).length,
    },
    {
      key: "needs_review",
      label: "待复核",
      desc: "优先处理待补证、纠偏触发和弱证据条目",
      count: allItems.filter((item) => matchesRetrievalLens(item, "needs_review")).length,
    },
  ];
  const activeFilterLabels = [
    regionFilter ? `${t("research.centerRegionLabel", "区域")} · ${regionFilter}` : "",
    industryFilter ? `${t("research.centerIndustryLabel", "行业")} · ${industryFilter}` : "",
    actionTypeFilter ? `${t("research.centerActionTypeLabel", "动作类型")} · ${actionTypeFilter}` : "",
    focusOnly ? t("research.centerFocusOnlyOn", "仅看 Focus 参考") : "",
    query ? `${t("common.searchPlaceholder", "搜索")} · ${query}` : "",
    retrievalLens !== "all"
      ? `检索视图 · ${(retrievalLensMeta.find((item) => item.key === retrievalLens) || retrievalLensMeta[0]).label}`
      : "",
    perspective !== "all" ? `${t("research.centerPerspectiveLabel", "业务视角")} · ${activePerspective.label}` : "",
  ].filter(Boolean);

  const handleSearchSubmit = () => {
    setQuery(queryDraft.trim());
  };

  const clearFacetFilters = () => {
    setRegionFilter("");
    setIndustryFilter("");
    setActionTypeFilter("");
    setFocusOnly(false);
    setQuery("");
    setQueryDraft("");
    setPerspective("all");
    setRetrievalLens("all");
  };

  const buildCompareHref = (overrides?: {
    query?: string;
    region?: string;
    industry?: string;
    topicId?: string;
  }) => {
    const params = new URLSearchParams();
    const compareQuery = (overrides?.query ?? query).trim();
    const compareRegion = overrides?.region ?? regionFilter;
    const compareIndustry = overrides?.industry ?? industryFilter;
    const compareTopicId = overrides?.topicId || "";
    if (compareQuery) params.set("query", compareQuery);
    if (compareRegion) params.set("region", compareRegion);
    if (compareIndustry) params.set("industry", compareIndustry);
    if (compareTopicId) params.set("topicId", compareTopicId);
    const queryString = params.toString();
    return queryString ? `/research/compare?${queryString}` : "/research/compare";
  };

  const buildCompareSnapshotHref = (snapshotId: string) =>
    `/research/compare?snapshot=${encodeURIComponent(snapshotId)}`;

  const triggerMarkdownDownload = (filename: string, content: string) => {
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const applySavedView = (view: ApiResearchSavedView) => {
    setFilter(view.filter_mode);
    setPerspective(view.perspective);
    setRegionFilter(view.region_filter || "");
    setIndustryFilter(view.industry_filter || "");
    setActionTypeFilter(view.action_type_filter || "");
    setFocusOnly(!!view.focus_only);
    setQuery(view.query || "");
    setQueryDraft(view.query || "");
  };

  const handleSaveCurrentView = async () => {
    const trimmedQuery = query.trim();
    const nameSeed = trimmedQuery || activePerspective.label || t("research.centerViewAll", "全部视角");
    setWorkspaceSaving(true);
    try {
      const saved = await saveResearchView({
        name: `${nameSeed} · ${new Date().toLocaleDateString()}`,
        query: trimmedQuery,
        filter_mode: filter,
        perspective,
        region_filter: regionFilter,
        industry_filter: industryFilter,
        action_type_filter: actionTypeFilter,
        focus_only: focusOnly,
      });
      setSavedViews((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
    } finally {
      setWorkspaceSaving(false);
    }
  };

  const handleDeleteSavedView = async (viewId: string) => {
    setWorkspaceSaving(true);
    try {
      await deleteResearchView(viewId);
      setSavedViews((current) => current.filter((item) => item.id !== viewId));
    } finally {
      setWorkspaceSaving(false);
    }
  };

  const handleDeleteCompareSnapshot = async (snapshotId: string) => {
    setWorkspaceSaving(true);
    try {
      await deleteResearchCompareSnapshot(snapshotId);
      setCompareSnapshots((current) => current.filter((item) => item.id !== snapshotId));
    } finally {
      setWorkspaceSaving(false);
    }
  };

  const handleDownloadMarkdownArchive = async (archive: ApiResearchMarkdownArchive) => {
    const detail = await getResearchMarkdownArchive(archive.id);
    triggerMarkdownDownload(detail.filename, detail.content);
  };

  const handleDeleteMarkdownArchive = async (archiveId: string) => {
    setWorkspaceSaving(true);
    try {
      await deleteResearchMarkdownArchive(archiveId);
      setMarkdownArchives((current) => current.filter((item) => item.id !== archiveId));
    } finally {
      setWorkspaceSaving(false);
    }
  };

  const handleSaveTrackingTopic = async () => {
    const keyword = query.trim() || getResearchKeyword(visibleItems[0] || reports[0] || actions[0] || ({} as ApiKnowledgeEntry));
    if (!keyword) return;
    const focusText = activeFilterLabels.join(" / ");
    setWorkspaceSaving(true);
    try {
      const saved = await saveResearchTrackingTopic({
        name: `${keyword} 跟踪`,
        keyword,
        research_focus: focusText,
        perspective,
        region_filter: regionFilter,
        industry_filter: industryFilter,
        notes: visibleItems[0]?.title || "",
      });
      setTrackingTopics((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
    } finally {
      setWorkspaceSaving(false);
    }
  };

  const applyTrackingTopic = (topic: ApiResearchTrackingTopic) => {
    setPerspective(topic.perspective);
    setRegionFilter(topic.region_filter || "");
    setIndustryFilter(topic.industry_filter || "");
    setQuery(topic.keyword || "");
    setQueryDraft(topic.keyword || "");
    setActionTypeFilter("");
    setFocusOnly(false);
  };

  const handleDeleteTrackingTopic = async (topicId: string) => {
    setWorkspaceSaving(true);
    try {
      await deleteResearchTrackingTopic(topicId);
      setTrackingTopics((current) => current.filter((item) => item.id !== topicId));
    } finally {
      setWorkspaceSaving(false);
    }
  };

  const handleRefreshTrackingTopic = async (topicId: string) => {
    setRefreshingTopicId(topicId);
    setTrackingTopics((current) =>
      current.map((item) =>
        item.id === topicId
          ? {
              ...item,
              last_refresh_status: "running",
              last_refresh_error: "",
              last_refresh_note: "正在刷新专题研报并补充新增情报",
            }
          : item,
      ),
    );
    try {
      const result = await refreshResearchTrackingTopic(topicId, {
        output_language: "zh-CN",
        include_wechat: true,
        max_sources: 12,
        save_to_knowledge: true,
      });
      setTrackingTopics((current) =>
        current.map((item) => (item.id === topicId ? result.topic : item)),
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "专题刷新失败";
      setTrackingTopics((current) =>
        current.map((item) =>
          item.id === topicId
            ? {
                ...item,
                last_refresh_status: "failed",
                last_refresh_error: message,
                last_refresh_note: "专题刷新失败，请检查当前关键词公开源与模型链路",
              }
            : item,
        ),
      );
    } finally {
      setRefreshingTopicId("");
    }
  };

  const handleCreateWatchlist = async (topic: ApiResearchTrackingTopic) => {
    setWorkspaceSaving(true);
    try {
      const saved = await createResearchWatchlist({
        name: `${topic.name} Watchlist`,
        watch_type: "topic",
        query: topic.keyword,
        tracking_topic_id: topic.id,
        research_focus: topic.research_focus,
        perspective: topic.perspective,
        region_filter: topic.region_filter,
        industry_filter: topic.industry_filter,
        alert_level: "medium",
        schedule: "daily",
      });
      setWatchlists((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
    } finally {
      setWorkspaceSaving(false);
    }
  };

  const handleUpdateWatchlistSchedule = async (watchlistId: string, schedule: string) => {
    const currentWatchlist = watchlists.find((item) => item.id === watchlistId);
    if (!currentWatchlist || currentWatchlist.schedule === schedule) return;
    setWatchlistActionKey(`${watchlistId}-schedule`);
    setWatchlistError("");
    try {
      const saved = await updateResearchWatchlist(watchlistId, { schedule });
      setWatchlists((current) => current.map((item) => (item.id === watchlistId ? saved : item)));
      setWatchlistMessage(`已更新 ${saved.name} 的刷新频率`);
    } catch {
      setWatchlistError("更新 Watchlist 频率失败，请稍后重试。");
    } finally {
      setWatchlistActionKey("");
    }
  };

  const handleToggleWatchlistStatus = async (watchlist: ApiResearchWatchlist) => {
    const nextStatus = watchlist.status === "paused" ? "active" : "paused";
    setWatchlistActionKey(`${watchlist.id}-status`);
    setWatchlistError("");
    try {
      const saved = await updateResearchWatchlist(watchlist.id, { status: nextStatus });
      setWatchlists((current) => current.map((item) => (item.id === watchlist.id ? saved : item)));
      setWatchlistMessage(nextStatus === "paused" ? `已暂停 ${saved.name}` : `已恢复 ${saved.name}`);
    } catch {
      setWatchlistError("更新 Watchlist 状态失败，请稍后重试。");
    } finally {
      setWatchlistActionKey("");
    }
  };

  const handleRefreshWatchlist = async (watchlistId: string) => {
    setRefreshingWatchlistId(watchlistId);
    setWatchlistError("");
    try {
      const result = await refreshResearchWatchlist(watchlistId, {
        output_language: "zh-CN",
        include_wechat: true,
        max_sources: 12,
        save_to_knowledge: true,
      });
      setWatchlists((current) =>
        current.map((item) => (item.id === watchlistId ? result.watchlist : item)),
      );
      setTrackingTopics((current) =>
        current.map((item) => (item.id === result.topic.id ? result.topic : item)),
      );
      setWatchlistMessage(
        result.changes?.length
          ? `${result.watchlist.name} 已刷新，识别到 ${result.changes.length} 条变化`
          : `${result.watchlist.name} 已刷新，暂无新增变化`,
      );
    } catch {
      setWatchlistError("手动刷新 Watchlist 失败，请稍后重试。");
    } finally {
      setRefreshingWatchlistId("");
    }
  };

  const handleRunDueWatchlists = async () => {
    setRunningDueWatchlists(true);
    setWatchlistError("");
    try {
      const result = await runDueResearchWatchlists({
        output_language: "zh-CN",
        include_wechat: true,
        max_sources: 12,
        save_to_knowledge: true,
        limit: 6,
      });
      setLastRunDueResult(result);
      setWatchlistMessage(
        result.due_count
          ? `本轮检查 ${result.due_count} 个到期 Watchlist，已刷新 ${result.refreshed_count} 个，失败 ${result.failed_count} 个。`
          : "当前没有到期 Watchlist。",
      );
      const [workspace, nextWatchlists, automation] = await Promise.all([
        getResearchWorkspace(),
        listResearchWatchlists(),
        getResearchWatchlistAutomationStatus().catch(() => null),
      ]);
      setTrackingTopics(workspace.tracking_topics || []);
      setCompareSnapshots(workspace.compare_snapshots || []);
      setMarkdownArchives(workspace.markdown_archives || []);
      setWatchlists(nextWatchlists || []);
      if (automation) {
        setWatchlistAutomation(automation);
      }
    } catch {
      setWatchlistError("执行到期 Watchlist 失败，请检查自动巡检状态和日志。");
    } finally {
      setRunningDueWatchlists(false);
    }
  };

  const copyWatchlistOpsText = async (value: string, label: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setWatchlistMessage(`${label}已复制`);
      setWatchlistError("");
    } catch {
      setWatchlistError("复制失败，请稍后重试。");
    }
  };

  const toggleResearchSource = async (
    key:
      | "enable_jianyu_tender_feed"
      | "enable_yuntoutiao_feed"
      | "enable_ggzy_feed"
      | "enable_cecbid_feed"
      | "enable_ccgp_feed"
      | "enable_gov_policy_feed"
      | "enable_local_ggzy_feed"
      | "enable_curated_wechat_channels",
  ) => {
    if (!sourceSettings || sourceSaving) return;
    const previousSettings = sourceSettings;
    const nextPayload: ApiResearchSourceSettings = {
      enable_jianyu_tender_feed:
        key === "enable_jianyu_tender_feed"
          ? !sourceSettings.enable_jianyu_tender_feed
          : sourceSettings.enable_jianyu_tender_feed,
      enable_yuntoutiao_feed:
        key === "enable_yuntoutiao_feed"
          ? !sourceSettings.enable_yuntoutiao_feed
          : sourceSettings.enable_yuntoutiao_feed,
      enable_ggzy_feed:
        key === "enable_ggzy_feed"
          ? !sourceSettings.enable_ggzy_feed
          : sourceSettings.enable_ggzy_feed,
      enable_cecbid_feed:
        key === "enable_cecbid_feed"
          ? !sourceSettings.enable_cecbid_feed
          : sourceSettings.enable_cecbid_feed,
      enable_ccgp_feed:
        key === "enable_ccgp_feed"
          ? !sourceSettings.enable_ccgp_feed
          : sourceSettings.enable_ccgp_feed,
      enable_gov_policy_feed:
        key === "enable_gov_policy_feed"
          ? !sourceSettings.enable_gov_policy_feed
          : sourceSettings.enable_gov_policy_feed,
      enable_local_ggzy_feed:
        key === "enable_local_ggzy_feed"
          ? !sourceSettings.enable_local_ggzy_feed
          : sourceSettings.enable_local_ggzy_feed,
      enable_curated_wechat_channels:
        key === "enable_curated_wechat_channels"
          ? !sourceSettings.enable_curated_wechat_channels
          : sourceSettings.enable_curated_wechat_channels,
      enabled_source_labels: sourceSettings.enabled_source_labels,
      connector_statuses: sourceSettings.connector_statuses,
      updated_at: sourceSettings.updated_at,
    };
    setSourceSaving(true);
    setSourceError("");
    setSourceSettings((current) =>
      current
        ? {
            ...current,
            ...nextPayload,
          }
        : current,
    );
    try {
      const next = await updateResearchSourceSettings(nextPayload);
      setSourceSettings(next);
      setSourceError("");
    } catch {
      setSourceSettings(previousSettings);
      setSourceError("研究来源设置保存失败，请检查后端研究服务是否可用后重试。");
    } finally {
      setSourceSaving(false);
    }
  };

  return (
    <div className="space-y-5">
      <section className="af-glass rounded-[34px] p-5 md:p-7">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div className="max-w-3xl">
            <p className="af-kicker">{t("research.centerKicker", "Research Center")}</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-slate-900 md:text-[2rem]">
              {t("research.centerTitle", "商机情报中心")}
            </h2>
            <p className="mt-3 text-sm leading-6 text-slate-500 md:text-[15px]">
              {t(
                "research.centerDesc",
                "统一查看保存过的情报简报、推荐动作和 Focus 参考，快速回到客户推进、投标排期与生态协同。",
              )}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="af-glass-orb-btn inline-flex h-11 items-center gap-2 rounded-full px-4 text-sm font-medium text-slate-700">
              <AppIcon name="source" className="h-4 w-4" />
              <span>{t("research.centerSourceToggle", "公开源")}</span>
              <span className="rounded-full bg-white/70 px-2 py-0.5 text-[11px] text-slate-500">
                {sourceSettings?.enabled_source_labels?.length || 0}
              </span>
            </div>
            <Link href={buildCompareHref()} className="af-btn af-btn-secondary border px-4 py-2">
              {t("research.centerOpenCompare", "打开对比矩阵")}
            </Link>
            <Link href="/inbox" className="af-btn af-btn-secondary border px-4 py-2">
              {t("research.centerBackToInbox", "返回解决方案智囊")}
            </Link>
          </div>
        </div>

        <div className="mt-5 rounded-[28px] border border-white/70 bg-white/72 p-4 shadow-[0_18px_45px_rgba(15,23,42,0.08)] backdrop-blur-xl">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="max-w-2xl">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                {t("research.centerSourcePanelKicker", "Research Sources")}
              </p>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {t(
                  "research.centerSourcePanelDesc",
                  "将公开招投标与行业媒体流并入研报线索池。当前仅抓取公开页面，不绕过登录或付费墙。",
                )}
              </p>
            </div>
            <div className="rounded-full border border-white/70 bg-white/70 px-3 py-1 text-xs font-medium text-slate-500">
              {t("research.centerSourceActive", "当前开启")} · {sourceSettings?.enabled_source_labels?.join(" / ") || t("research.centerSourceNone", "无")}
            </div>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {[
              {
                key: "enable_jianyu_tender_feed" as const,
                title: t("research.centerSourceJianyu", "剑鱼标讯"),
                desc: t(
                  "research.centerSourceJianyuDesc",
                  "补充公开招标公告、中标成交、采购意向与项目分包线索。",
                ),
                enabled: !!sourceSettings?.enable_jianyu_tender_feed,
              },
              {
                key: "enable_yuntoutiao_feed" as const,
                title: t("research.centerSourceYuntoutiao", "云头条"),
                desc: t(
                  "research.centerSourceYuntoutiaoDesc",
                  "补充云计算、AI、产业竞争和技术商业化动态解读。",
                ),
                enabled: !!sourceSettings?.enable_yuntoutiao_feed,
              },
              {
                key: "enable_ggzy_feed" as const,
                title: t("research.centerSourceGgzy", "全国公共资源交易平台"),
                desc: t(
                  "research.centerSourceGgzyDesc",
                  "补充工程建设、政府采购、成交公示等全国公共资源交易公告。",
                ),
                enabled: !!sourceSettings?.enable_ggzy_feed,
              },
              {
                key: "enable_cecbid_feed" as const,
                title: t("research.centerSourceCecbid", "中国招标投标网"),
                desc: t(
                  "research.centerSourceCecbidDesc",
                  "补充招标、结果、资讯和招标前信息公示等公开招采流。",
                ),
                enabled: !!sourceSettings?.enable_cecbid_feed,
              },
              {
                key: "enable_ccgp_feed" as const,
                title: t("research.centerSourceCcgp", "政府采购合规聚合"),
                desc: t(
                  "research.centerSourceCcgpDesc",
                  "以公开、合规、稳定的采购聚合源替代直抓政府采购网，补充采购人、预算和中标线索。",
                ),
                enabled: !!sourceSettings?.enable_ccgp_feed,
              },
              {
                key: "enable_gov_policy_feed" as const,
                title: t("research.centerSourceGovPolicy", "中国政府网政策/讲话"),
                desc: t(
                  "research.centerSourceGovPolicyDesc",
                  "补充政府工作报告、政策文件、领导讲话与战略规划等官方信号。",
                ),
                enabled: !!sourceSettings?.enable_gov_policy_feed,
              },
              {
                key: "enable_local_ggzy_feed" as const,
                title: t("research.centerSourceLocalGgzy", "地方公共资源交易平台"),
                desc: t(
                  "research.centerSourceLocalGgzyDesc",
                  "按区域定向补充省市公共资源交易平台与地方政府采购平台公开公告。",
                ),
                enabled: !!sourceSettings?.enable_local_ggzy_feed,
              },
              {
                key: "enable_curated_wechat_channels" as const,
                title: t("research.centerSourceCuratedWechat", "精选公众号观察池"),
                desc: t(
                  "research.centerSourceCuratedWechatDesc",
                  "优先把云技术、智能超参数、数说123之算力大模型纳入公众号观察池，增强云、算力和大模型主题线索。",
                ),
                enabled: !!sourceSettings?.enable_curated_wechat_channels,
              },
            ].map((source) => (
              <button
                key={source.key}
                type="button"
                onClick={() => void toggleResearchSource(source.key)}
                disabled={sourceSaving}
                className={`rounded-[24px] border px-4 py-4 text-left transition disabled:cursor-not-allowed disabled:opacity-70 ${
                  source.enabled
                    ? "border-sky-200 bg-sky-50/75 shadow-[0_14px_35px_rgba(56,189,248,0.14)]"
                    : "border-white/70 bg-white/72"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{source.title}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {source.enabled
                        ? t("research.centerSourceEnabled", "已开启")
                        : t("research.centerSourceDisabled", "已关闭")}
                    </p>
                  </div>
                  <span
                    className={`inline-flex h-8 min-w-14 items-center rounded-full px-1 ${
                      source.enabled ? "bg-sky-500/90" : "bg-slate-300/90"
                    }`}
                  >
                    <span
                      className={`h-6 w-6 rounded-full bg-white shadow transition ${
                        source.enabled ? "translate-x-6" : "translate-x-0"
                      }`}
                    />
                  </span>
                </div>
                <p className="mt-3 text-sm leading-6 text-slate-600">{source.desc}</p>
              </button>
            ))}
          </div>
          {sourceError ? <p className="mt-3 text-sm text-amber-700">{sourceError}</p> : null}
          {sourceSettings?.connector_statuses?.length ? (
            <div className="mt-4 rounded-[24px] border border-white/70 bg-white/68 p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                {t("research.centerConnectorStatus", "授权/接入状态")}
              </p>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                {sourceSettings.connector_statuses.map((status) => (
                  <div key={status.key} className="rounded-[18px] border border-slate-200/80 bg-slate-50/75 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-slate-900">{status.label}</p>
                      <span
                        className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${
                          status.status === "active"
                            ? "bg-emerald-100 text-emerald-700"
                            : status.status === "authorization_required"
                              ? "bg-amber-100 text-amber-700"
                              : "bg-slate-100 text-slate-500"
                        }`}
                      >
                        {status.status === "active"
                          ? t("research.centerConnectorActive", "已启用")
                          : status.status === "authorization_required"
                            ? t("research.centerConnectorAuthorization", "需授权")
                            : t("research.centerConnectorAvailable", "可接入")}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{status.detail}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          {sourceSaving ? (
            <p className="mt-3 text-xs text-slate-500">
              {t("research.centerSourceSaving", "正在保存公开源设置...")}
            </p>
          ) : null}
        </div>

        <div className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {overviewStats.map((stat) => (
            <div key={stat.label} className="rounded-[26px] border border-white/60 bg-white/60 p-4 shadow-[0_12px_35px_rgba(15,23,42,0.06)]">
              <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-slate-400">
                {stat.label}
              </p>
              <p className={`mt-3 text-3xl font-semibold tracking-[-0.05em] ${stat.tone}`}>{stat.value}</p>
            </div>
          ))}
        </div>
      </section>

      <ResearchConsolePanel
        trackingTopics={trackingTopics.map((item) => ({
          id: item.id,
          name: item.name,
          keyword: item.keyword,
        }))}
      />

      <section className="af-glass rounded-[30px] p-5 md:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="max-w-3xl">
            <p className="af-kicker">Offline Evaluation</p>
            <h3 className="mt-2 text-xl font-semibold text-slate-900">离线回归评估</h3>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              将检索命中率、目标账户支撑率和章节证据配额通过率前台化，方便每轮 rewrite 后快速回看质量回归。
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="rounded-full border border-white/70 bg-white/70 px-3 py-1 text-xs font-medium text-slate-500">
              扫描研报 · {offlineEvaluation?.total_reports ?? 0}
            </div>
            <div className="rounded-full border border-white/70 bg-white/70 px-3 py-1 text-xs font-medium text-slate-500">
              可评估 · {offlineEvaluation?.evaluated_reports ?? 0}
            </div>
            {(offlineEvaluation?.invalid_payloads ?? 0) > 0 ? (
              <div className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
                schema 异常 · {offlineEvaluation?.invalid_payloads ?? 0}
              </div>
            ) : null}
            <button
              type="button"
              onClick={() => void refreshOfflineEvaluation()}
              disabled={offlineEvaluationRefreshing}
              className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
            >
              {offlineEvaluationRefreshing ? "刷新中..." : "刷新评估"}
            </button>
          </div>
        </div>

        {offlineEvaluationLoading ? (
          <p className="mt-4 text-sm text-slate-500">{t("common.loading", "加载中")}</p>
        ) : (
          <>
            {offlineEvaluation?.generated_at ? (
              <p className="mt-3 text-xs text-slate-500">更新于 · {formatWatchlistTime(offlineEvaluation.generated_at)}</p>
            ) : null}

            {offlineEvaluation?.metrics?.length ? (
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                {offlineEvaluation.metrics.map((metric) => (
                  <div
                    key={metric.key}
                    className={`rounded-[24px] border p-4 shadow-[0_12px_30px_rgba(15,23,42,0.05)] ${offlineEvaluationStatusTone(metric.status)}`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold">{sanitizeExternalDisplayText(metric.label)}</p>
                      <span className="rounded-full bg-white/80 px-2.5 py-1 text-[11px] font-medium text-slate-700">
                        {offlineEvaluationStatusLabel(metric.status)}
                      </span>
                    </div>
                    <p className="mt-3 text-3xl font-semibold tracking-[-0.05em]">{metric.percent}%</p>
                    <p className="mt-2 text-xs text-slate-500">
                      当前 {metric.numerator}/{metric.denominator} · 基准 {Math.round(metric.benchmark * 100)}%
                    </p>
                    <p className="mt-3 text-sm leading-6 text-slate-600">
                      {sanitizeExternalDisplayText(metric.summary)}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-500">当前暂无离线回归样本。</p>
            )}

            <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,0.95fr),minmax(0,1.05fr)]">
              <div className="rounded-[24px] border border-white/70 bg-white/68 p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-slate-900">回归摘要</p>
                  <span className="text-[11px] uppercase tracking-[0.14em] text-slate-400">Regression Notes</span>
                </div>
                {offlineEvaluation?.summary_lines?.length ? (
                  <div className="mt-3 space-y-2">
                    {offlineEvaluation.summary_lines.map((line) => (
                      <div key={line} className="rounded-[18px] border border-slate-200/70 bg-slate-50/85 px-3 py-2 text-sm leading-6 text-slate-600">
                        {sanitizeExternalDisplayText(line)}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-slate-500">当前没有额外摘要。</p>
                )}
              </div>

              <div className="rounded-[24px] border border-white/70 bg-white/68 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">弱样本回归列表</p>
                    <p className="mt-1 text-xs text-slate-500">优先处理目标账户缺支撑、章节配额未达标和检索命中偏弱的旧报告。</p>
                  </div>
                  <span className="text-[11px] uppercase tracking-[0.14em] text-slate-400">
                    Top {Math.min(offlineEvaluation?.weakest_reports?.length ?? 0, 4)}
                  </span>
                </div>
                {offlineEvaluation?.weakest_reports?.length ? (
                  <div className="mt-3 space-y-3">
                    {offlineEvaluation.weakest_reports.slice(0, 4).map((item) => {
                      const quotaGap = Math.max(item.quota_total_section_count - item.quota_passed_section_count, 0);
                      const reportTitle = sanitizeExternalDisplayText(item.report_title || item.entry_title || "知识卡片");
                      return (
                        <div key={item.entry_id} className="rounded-[20px] border border-slate-200/80 bg-slate-50/80 p-4">
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div className="min-w-0 flex-1">
                              <Link href={`/knowledge/${item.entry_id}`} className="block">
                                <p className="text-sm font-semibold text-slate-900 transition hover:text-sky-700">{reportTitle}</p>
                              </Link>
                              <p className="mt-1 text-xs text-slate-500">
                                {sanitizeExternalDisplayText(item.keyword || "未标注关键词")}
                              </p>
                            </div>
                            <span className="rounded-full bg-rose-100 px-2.5 py-1 text-[11px] font-medium text-rose-700">
                              弱度 {item.weakness_score}
                            </span>
                          </div>
                          <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-600">
                            <span className={`rounded-full px-2.5 py-1 font-medium ${item.retrieval_hit ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}`}>
                              {item.retrieval_hit ? "检索命中已过线" : "检索命中偏弱"}
                            </span>
                            <span className="rounded-full bg-white px-2.5 py-1">
                              目标支撑 {item.supported_target_accounts}/{item.supported_target_accounts + item.unsupported_target_accounts}
                            </span>
                            <span className="rounded-full bg-white px-2.5 py-1">
                              章节配额 {item.quota_passed_section_count}/{item.quota_total_section_count}
                            </span>
                            <span className="rounded-full bg-white px-2.5 py-1">
                              官方源 {Math.round(item.official_source_ratio * 100)}%
                            </span>
                            <span className="rounded-full bg-white px-2.5 py-1">
                              严格命中 {Math.round(item.strict_match_ratio * 100)}%
                            </span>
                          </div>
                          {(item.unsupported_targets.length || item.failing_sections.length) ? (
                            <div className="mt-3 space-y-2">
                              {item.unsupported_targets.length ? (
                                <p className="text-sm leading-6 text-slate-600">
                                  待补证账户 · {sanitizeExternalDisplayText(item.unsupported_targets.join(" / "))}
                                </p>
                              ) : null}
                              {item.failing_sections.length ? (
                                <p className="text-sm leading-6 text-slate-600">
                                  未过配额章节 · {sanitizeExternalDisplayText(item.failing_sections.join(" / "))} {quotaGap > 0 ? `(${quotaGap} 处待补)` : ""}
                                </p>
                              ) : null}
                            </div>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-slate-500">当前没有需要优先回归的弱样本。</p>
                )}
              </div>
            </div>
          </>
        )}
      </section>

      <div className="grid gap-5 xl:grid-cols-[300px,minmax(0,1fr)]">
        <aside className="space-y-4 xl:sticky xl:top-24 xl:self-start">
          <section className="af-glass rounded-[30px] p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="af-kicker">Daily Brief</p>
                <h3 className="mt-2 text-lg font-semibold text-slate-900">今日研究摘要</h3>
                <p className="mt-2 text-sm text-slate-500">
                  {sanitizeExternalDisplayText("优先查看当日重点增量与 Watchlist 变化，再决定是否刷新专题。")}
                </p>
              </div>
              <button
                type="button"
                onClick={() => void handleRefreshDailyBrief()}
                className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                disabled={dailyBriefRefreshing}
              >
                {dailyBriefRefreshing ? "刷新中..." : "刷新"}
              </button>
            </div>
            {dailyBriefLoading ? (
              <p className="mt-4 text-sm text-slate-500">{t("common.loading", "加载中")}</p>
            ) : dailyBrief ? (
              <div className="mt-4 space-y-3">
                <div className="rounded-[22px] border border-white/60 bg-white/65 p-4">
                  <p className="text-sm font-semibold text-slate-900">
                    {sanitizeExternalDisplayText(dailyBrief.headline || "今天优先处理 Watchlist 变化和新增高价值内容。")}
                  </p>
                  <p className="mt-2 text-sm leading-6 text-slate-600">
                    {sanitizeExternalDisplayText(dailyBrief.summary || "今天暂无新的高价值内容，建议刷新专题或继续处理稍后读。")}
                  </p>
                  {dailyBrief.generated_at ? (
                    <p className="mt-2 text-xs text-slate-500">
                      生成于 · {formatWatchlistTime(dailyBrief.generated_at)}
                    </p>
                  ) : null}
                </div>
                {dailyBrief.top_items?.length ? (
                  <div className="space-y-2">
                    {dailyBrief.top_items.slice(0, 3).map((item) => (
                      <Link
                        key={item.id}
                        href={`/items/${item.id}`}
                        className="block rounded-[20px] border border-white/60 bg-white/65 p-3 transition hover:border-sky-200 hover:bg-white/80"
                      >
                        <p className="text-[11px] uppercase tracking-[0.12em] text-slate-400">{item.source_domain}</p>
                        <p className="mt-1 text-sm font-semibold text-slate-900">{item.title}</p>
                        <p className="mt-1 text-xs leading-5 text-slate-500">{sanitizeExternalDisplayText(item.summary)}</p>
                      </Link>
                    ))}
                  </div>
                ) : null}
                {dailyBrief.watchlist_changes?.length ? (
                  <div className="rounded-[22px] border border-white/60 bg-white/65 p-4">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-slate-400">Watchlist 变化</p>
                    <div className="mt-2 space-y-2">
                      {dailyBrief.watchlist_changes.slice(0, 2).map((change) => (
                        <div key={change.id} className="rounded-2xl border border-slate-200/80 bg-slate-50/80 px-3 py-2">
                          <p className="text-sm text-slate-700">{sanitizeExternalDisplayText(change.summary)}</p>
                          <p className="mt-1 text-[11px] uppercase tracking-[0.12em] text-slate-400">
                            {change.change_type} · {change.severity}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-500">当前没有 Daily Brief，可先刷新一次。</p>
            )}
            {dailyBriefError ? <p className="mt-3 text-sm text-rose-600">{dailyBriefError}</p> : null}
          </section>

          <section className="af-glass rounded-[30px] p-5">
            <p className="af-kicker">{t("research.centerFilterTitle", "视图筛选")}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {filterMeta.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setFilter(item.key)}
                  className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                    filter === item.key
                      ? "bg-slate-900 text-white"
                      : "border border-slate-200 bg-white/70 text-slate-600"
                  }`}
                >
                  {item.label} · {item.count}
                </button>
              ))}
            </div>

            <div className="mt-4 space-y-3">
              <div className="flex items-center gap-2 rounded-[20px] border border-white/60 bg-white/70 px-3 py-2 shadow-[0_10px_30px_rgba(15,23,42,0.05)]">
                <input
                  value={queryDraft}
                  onChange={(event) => setQueryDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      handleSearchSubmit();
                    }
                  }}
                  placeholder={t("research.centerSearchPlaceholder", "搜索关键词、甲方、预算、投标...")}
                  className="min-w-0 flex-1 bg-transparent text-sm text-slate-700 outline-none placeholder:text-slate-400"
                />
                <button type="button" onClick={handleSearchSubmit} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                  {t("research.centerSearchSubmit", "搜索")}
                </button>
              </div>

              <button
                type="button"
                onClick={() => setFocusOnly((value) => !value)}
                className={`af-btn w-full justify-center border px-4 py-2 ${focusOnly ? "af-btn-primary" : "af-btn-secondary"}`}
              >
                {focusOnly
                  ? t("research.centerFocusOnlyOn", "仅看 Focus 参考")
                  : t("research.centerFocusOnlyOff", "包含全部")}
              </button>
            </div>

            <div className="mt-4 space-y-3">
              <div>
                <p className="text-sm text-slate-500">检索视图</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {retrievalLensMeta.map((item) => (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => setRetrievalLens(item.key)}
                      className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                        retrievalLens === item.key
                          ? "bg-slate-900 text-white"
                          : "border border-slate-200 bg-white/70 text-slate-600"
                      }`}
                    >
                      {item.label} · {item.count}
                    </button>
                  ))}
                </div>
                <p className="mt-2 text-sm text-slate-500">
                  {(retrievalLensMeta.find((item) => item.key === retrievalLens) || retrievalLensMeta[0]).desc}
                </p>
              </div>

              <div>
                <p className="text-sm text-slate-500">{t("research.centerPerspectiveLabel", "业务视角")}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {perspectiveMeta.map((item) => (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => setPerspective(item.key)}
                      className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                        perspective === item.key
                          ? "bg-slate-900 text-white"
                          : "border border-slate-200 bg-white/70 text-slate-600"
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
                <p className="mt-2 text-sm text-slate-500">{activePerspective.desc}</p>
              </div>

              <label className="space-y-2 text-sm text-slate-500">
                <span>{t("research.centerRegionLabel", "区域")}</span>
                <select
                  value={regionFilter}
                  onChange={(event) => setRegionFilter(event.target.value)}
                  className="af-input w-full bg-white/70"
                >
                  {regionOptions.map((option, index) => (
                    <option key={option} value={index === 0 ? "" : option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-2 text-sm text-slate-500">
                <span>{t("research.centerIndustryLabel", "行业")}</span>
                <select
                  value={industryFilter}
                  onChange={(event) => setIndustryFilter(event.target.value)}
                  className="af-input w-full bg-white/70"
                >
                  {industryOptions.map((option, index) => (
                    <option key={option} value={index === 0 ? "" : option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-2 text-sm text-slate-500">
                <span>{t("research.centerActionTypeLabel", "动作类型")}</span>
                <select
                  value={actionTypeFilter}
                  onChange={(event) => setActionTypeFilter(event.target.value)}
                  className="af-input w-full bg-white/70"
                >
                  {actionTypeOptions.map((option, index) => (
                    <option key={option} value={index === 0 ? "" : option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="mt-4 rounded-[22px] border border-white/60 bg-white/55 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.2em] text-slate-400">
                {t("research.centerFilteredResult", "当前视图")}
              </p>
              <p className="mt-3 text-3xl font-semibold tracking-[-0.05em] text-slate-900">{visibleItems.length}</p>
              <p className="mt-1 text-sm text-slate-500">
                {t("research.centerFilteredResultHint", "张匹配卡片，适合继续整理为方案或行动卡。")}
              </p>
              <button type="button" onClick={clearFacetFilters} className="mt-4 text-sm font-medium text-slate-700 underline decoration-slate-300 underline-offset-4">
                {t("research.centerClearFilters", "清空筛选")}
              </button>
            </div>
          </section>

          <section className="af-glass rounded-[30px] p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="af-kicker">{t("research.markdownArchiveKicker", "Markdown Archives")}</p>
                <h3 className="mt-2 text-lg font-semibold text-slate-900">
                  {t("research.markdownArchiveTitle", "历史归档中心")}
                </h3>
                <p className="mt-2 text-sm text-slate-500">
                  {t("research.markdownArchiveDesc", "收口 compare 导出和版本复盘报告，方便后续回看、下载和继续跳转到对应工作台。")}
                </p>
              </div>
              <div className="grid min-w-[260px] gap-3 sm:grid-cols-2">
                <label className="space-y-2 text-sm text-slate-500">
                  <span>{t("research.archiveFilterLabel", "交付筛选")}</span>
                  <select
                    value={archiveDeliveryFilter}
                    onChange={(event) => setArchiveDeliveryFilter(event.target.value as ArchiveDeliveryFilter)}
                    className="af-input w-full bg-white/70"
                  >
                    {archiveFilterMeta.map((option) => (
                      <option key={option.key} value={option.key}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="space-y-2 text-sm text-slate-500">
                  <span>{t("research.archiveSortLabel", "排序方式")}</span>
                  <select
                    value={archiveSortMode}
                    onChange={(event) => setArchiveSortMode(event.target.value as ArchiveSortMode)}
                    className="af-input w-full bg-white/70"
                  >
                    {archiveSortMeta.map((option) => (
                      <option key={option.key} value={option.key}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
            {archiveLinkMessage ? <p className="mt-3 text-sm text-slate-500">{archiveLinkMessage}</p> : null}
            <div className="mt-3 flex flex-wrap gap-2 text-xs">
              <span className="rounded-full bg-white/80 px-2.5 py-1 text-slate-600">
                {t("research.archiveVisibleCount", "可见归档")} · {visibleMarkdownArchives.length}
              </span>
              <span className="rounded-full bg-white/80 px-2.5 py-1 text-slate-600">
                {archiveFilterMeta.find((item) => item.key === archiveDeliveryFilter)?.label || t("research.archiveFilterAll", "全部归档")}
              </span>
              <span className="rounded-full bg-white/80 px-2.5 py-1 text-slate-600">
                {archiveSortMeta.find((item) => item.key === archiveSortMode)?.label || t("research.archiveSortUpdated", "按更新时间")}
              </span>
            </div>

            <div className="mt-4 space-y-3">
              {visibleMarkdownArchives.length ? (
                visibleMarkdownArchives.map(({ archive, digest: archiveDigest }) => {
                  return (
                    <article key={archive.id} className="rounded-[22px] border border-white/60 bg-white/65 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-sm font-semibold text-slate-900">{archive.name}</p>
                            <span className={`rounded-full px-2.5 py-1 text-[11px] ${markdownArchiveKindTone(archive.archive_kind)}`}>
                              {markdownArchiveKindLabel(archive.archive_kind)}
                            </span>
                          </div>
                          <p className="mt-1 text-xs text-slate-500">
                            {archive.query || t("research.centerSavedViewsNoQuery", "无关键词")} · {new Date(archive.updated_at).toLocaleDateString()}
                          </p>
                        </div>
                        <button
                          type="button"
                          disabled={workspaceSaving}
                          onClick={() => void handleDeleteMarkdownArchive(archive.id)}
                          className="text-xs font-medium text-slate-400 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {t("common.delete", "删除")}
                        </button>
                      </div>
                      {archive.summary ? (
                      <p className="mt-2 text-sm leading-6 text-slate-600">{sanitizeExternalDisplayText(archive.summary)}</p>
                      ) : null}
                      {archive.preview_text ? (
                        <p className="mt-2 text-xs leading-5 text-slate-500">{archive.preview_text}</p>
                      ) : null}
                      {archiveDigest ? (
                        <>
                          <div className="mt-2 flex flex-wrap gap-2 text-xs">
                            {archiveDigest.metrics.map((metric) => (
                              <span
                                key={`${archive.id}-${metric.label}`}
                                className={`rounded-full px-2.5 py-1 ${archiveDeliveryMetricToneClassName(metric.tone)}`}
                              >
                                {metric.label} {metric.value}
                              </span>
                            ))}
                          </div>
                          {archiveDigest.notes.length ? (
                            <p className="mt-2 text-xs leading-5 text-slate-500">{archiveDigest.notes[0]}</p>
                          ) : null}
                          {archiveDigest.outstandingItems.length ? (
                            <p className="mt-2 text-xs leading-5 text-rose-600">
                              {archiveDigest.outstandingLabel} · {archiveDigest.outstandingItems.slice(0, 3).join(" / ")}
                            </p>
                          ) : null}
                        </>
                      ) : null}
                      <div className="mt-2 flex flex-wrap gap-2 text-xs">
                        <span className="rounded-full bg-white/80 px-2.5 py-1 text-slate-600">
                          {Math.max(1, Math.round(archive.content_length / 1024))} KB
                        </span>
                        {archive.tracking_topic_name ? (
                          <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
                            {archive.tracking_topic_name}
                          </span>
                        ) : null}
                        {archive.compare_snapshot_name ? (
                          <span className="rounded-full bg-cyan-50 px-2.5 py-1 text-cyan-700">
                            {archive.compare_snapshot_name}
                          </span>
                        ) : null}
                        {archive.report_version_title ? (
                          <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-700">
                            {archive.report_version_title}
                          </span>
                        ) : null}
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Link href={buildMarkdownArchiveHref(archive.id)} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                          {t("research.markdownArchivePreview", "在线预览")}
                        </Link>
                        <button
                          type="button"
                          onClick={() => void handleDownloadMarkdownArchive(archive)}
                          className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                        >
                          {t("research.markdownArchiveDownload", "下载 Markdown")}
                        </button>
                        {archive.archive_kind === "archive_diff_recap" ? (
                          <ResearchArchiveSectionLinkPopover
                            archiveId={archive.id}
                            buttonLabel="变化深链"
                            buttonClassName="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                            onCopyMessage={setArchiveLinkMessage}
                          />
                        ) : null}
                        {archive.compare_snapshot_id ? (
                          <Link href={buildCompareSnapshotHref(archive.compare_snapshot_id)} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                            {t("research.compareOpenSnapshot", "打开快照")}
                          </Link>
                        ) : null}
                        {archive.tracking_topic_id ? (
                          <Link href={buildTopicWorkspaceHref(archive.tracking_topic_id)} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                            {t("research.openTopicWorkspace", "专题工作台")}
                          </Link>
                        ) : null}
                      </div>
                    </article>
                  );
                })
              ) : (
                <p className="text-sm text-slate-500">
                  {t("research.markdownArchiveEmpty", "还没有 Markdown 归档，先在对比矩阵或专题工作台里保存一次导出结果。")}
                </p>
              )}
            </div>
          </section>

          <section className="af-glass rounded-[30px] p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="af-kicker">{t("research.compareSnapshotKicker", "Compare Snapshots")}</p>
                <h3 className="mt-2 text-lg font-semibold text-slate-900">
                  {t("research.compareSnapshotTitle", "已保存对比快照")}
                </h3>
                <p className="mt-2 text-sm text-slate-500">
                  {t("research.compareSnapshotWorkspaceDesc", "冻结当前 compare 结果，便于复盘、转发和后续与新版本继续对照。")}
                </p>
              </div>
            </div>

            <div className="mt-4 space-y-3">
              {compareSnapshots.length ? (
                compareSnapshots.map((snapshot) => (
                  <article key={snapshot.id} className="rounded-[22px] border border-white/60 bg-white/65 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{snapshot.name}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          {snapshot.query || t("research.centerSavedViewsNoQuery", "无关键词")} · {new Date(snapshot.updated_at).toLocaleDateString()}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => void handleDeleteCompareSnapshot(snapshot.id)}
                        className="text-xs font-medium text-slate-400 hover:text-slate-700"
                      >
                        {t("common.delete", "删除")}
                      </button>
                    </div>
                    {snapshot.summary ? (
                      <p className="mt-2 text-sm leading-6 text-slate-600">{sanitizeExternalDisplayText(snapshot.summary)}</p>
                    ) : null}
                    <div className="mt-2 flex flex-wrap gap-2 text-xs">
                      <span className="rounded-full bg-white/80 px-2.5 py-1 text-slate-600">
                        实体 {snapshot.row_count}
                      </span>
                      <span className="rounded-full bg-white/80 px-2.5 py-1 text-slate-600">
                        来源研报 {snapshot.source_entry_count}
                      </span>
                      {snapshot.roles.map((role) => (
                        <span key={`${snapshot.id}-${role}`} className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">
                          {role}
                        </span>
                      ))}
                      {snapshot.tracking_topic_name ? (
                        <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
                          {snapshot.tracking_topic_name}
                        </span>
                      ) : null}
                      {snapshot.report_version_title ? (
                        <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-700">
                          {snapshot.report_version_title}
                        </span>
                      ) : null}
                    </div>
                    {snapshot.preview_names.length ? (
                      <p className="mt-2 text-xs leading-5 text-slate-500">
                        {snapshot.preview_names.join(" / ")}
                      </p>
                    ) : null}
                    {snapshot.linked_report_diff?.summary_lines?.length ? (
                      <p className="mt-2 text-xs leading-5 text-slate-500">
                        {snapshot.linked_report_diff.summary_lines[0]}
                      </p>
                    ) : null}
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Link href={buildCompareSnapshotHref(snapshot.id)} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                        {t("research.compareOpenSnapshot", "打开快照")}
                      </Link>
                      {snapshot.tracking_topic_id ? (
                        <Link href={buildTopicWorkspaceHref(snapshot.tracking_topic_id)} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                          {t("research.openTopicWorkspace", "专题工作台")}
                        </Link>
                      ) : null}
                    </div>
                  </article>
                ))
              ) : (
                <p className="text-sm text-slate-500">
                  {t("research.compareSnapshotEmpty", "还没有保存的对比快照，先在对比矩阵里固定一次结果。")}
                </p>
              )}
            </div>
          </section>

          <section className="af-glass rounded-[30px] p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="af-kicker">{t("research.centerSavedViewsKicker", "Saved Views")}</p>
                <h3 className="mt-2 text-lg font-semibold text-slate-900">
                  {t("research.centerSavedViewsTitle", "保存视图")}
                </h3>
                <p className="mt-2 text-sm text-slate-500">
                  {t("research.centerSavedViewsDesc", "把当前筛选和业务视角保存成可复用入口。")}
                </p>
              </div>
              <button
                type="button"
                onClick={() => void handleSaveCurrentView()}
                disabled={workspaceSaving}
                className="af-btn af-btn-secondary border px-3 py-1.5 text-sm"
              >
                {t("research.centerSaveCurrentView", "保存当前视图")}
              </button>
            </div>

            <div className="mt-4 space-y-3">
              {savedViews.length ? (
                savedViews.map((view) => (
                  <article key={view.id} className="rounded-[22px] border border-white/60 bg-white/65 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{view.name}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          {view.query || t("research.centerSavedViewsNoQuery", "无关键词")} · {new Date(view.updated_at).toLocaleDateString()}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => void handleDeleteSavedView(view.id)}
                        className="text-xs font-medium text-slate-400 hover:text-slate-700"
                      >
                        {t("common.delete", "删除")}
                      </button>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button type="button" onClick={() => applySavedView(view)} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                        {t("research.centerApplyView", "应用视图")}
                      </button>
                      <Link href={buildCompareHref({ query: view.query, region: view.region_filter, industry: view.industry_filter })} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                        {t("research.centerOpenCompare", "打开对比矩阵")}
                      </Link>
                    </div>
                  </article>
                ))
              ) : (
                <p className="text-sm text-slate-500">
                  {t("research.centerSavedViewsEmpty", "还没有保存视图，先固定一组筛选条件。")}
                </p>
              )}
            </div>
          </section>

          <section className="af-glass rounded-[30px] p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="af-kicker">{t("research.centerTrackingKicker", "Tracking Topics")}</p>
                <h3 className="mt-2 text-lg font-semibold text-slate-900">
                  {t("research.centerTrackingTitle", "长期跟踪专题")}
                </h3>
                <p className="mt-2 text-sm text-slate-500">
                  {t("research.centerTrackingDesc", "把高价值关键词沉淀成长期专题，便于持续刷新研报和竞对观察。")}
                </p>
              </div>
              <button
                type="button"
                onClick={() => void handleSaveTrackingTopic()}
                disabled={workspaceSaving}
                className="af-btn af-btn-secondary border px-3 py-1.5 text-sm"
              >
                {t("research.centerSaveTopic", "加入长期跟踪")}
              </button>
            </div>

            <div className="mt-4 space-y-3">
              {trackingTopics.length ? (
                trackingTopics.map((topic) => (
                  <article key={topic.id} className="rounded-[22px] border border-white/60 bg-white/65 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{topic.name}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          {topic.keyword} · {new Date(topic.updated_at).toLocaleDateString()}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => void handleDeleteTrackingTopic(topic.id)}
                        className="text-xs font-medium text-slate-400 hover:text-slate-700"
                      >
                        {t("common.delete", "删除")}
                      </button>
                    </div>
                    {topic.research_focus ? (
                      <p className="mt-2 text-sm leading-6 text-slate-600">{topic.research_focus}</p>
                    ) : null}
                    {topic.last_refreshed_at ? (
                      <p className="mt-2 text-xs text-slate-500">
                        {t("research.centerTrackingLastRefresh", "最近刷新")} · {new Date(topic.last_refreshed_at).toLocaleString()}
                      </p>
                    ) : null}
                    <div className="mt-2 flex flex-wrap gap-2 text-xs">
                      <span className={`rounded-full px-2.5 py-1 font-medium ${trackingStatusTone(topic.last_refresh_status)}`}>
                        {trackingStatusLabel(topic.last_refresh_status)}
                      </span>
                      {topic.last_refresh_new_targets?.length ? (
                        <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
                          新增甲方 {topic.last_refresh_new_targets.length}
                        </span>
                      ) : null}
                      {topic.last_refresh_new_competitors?.length ? (
                        <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-700">
                          新增竞品 {topic.last_refresh_new_competitors.length}
                        </span>
                      ) : null}
                      {topic.last_refresh_new_budget_signals?.length ? (
                        <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700">
                          新增预算线索 {topic.last_refresh_new_budget_signals.length}
                        </span>
                      ) : null}
                    </div>
                    {topic.last_refresh_note ? (
                      <p className="mt-2 text-xs leading-5 text-slate-500">{sanitizeExternalDisplayText(topic.last_refresh_note)}</p>
                    ) : null}
                    {topic.last_refresh_error ? (
                      <p className="mt-2 text-xs leading-5 text-rose-600">{topic.last_refresh_error}</p>
                    ) : null}
                    {topic.last_refresh_new_targets?.length || topic.last_refresh_new_competitors?.length || topic.last_refresh_new_budget_signals?.length ? (
                      <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
                        {topic.last_refresh_new_targets?.slice(0, 2).map((value) => (
                          <span key={`${topic.id}-new-target-${value}`} className="rounded-full bg-sky-50 px-2 py-1 text-sky-700">
                            甲方 · {value}
                          </span>
                        ))}
                        {topic.last_refresh_new_competitors?.slice(0, 2).map((value) => (
                          <span key={`${topic.id}-new-competitor-${value}`} className="rounded-full bg-amber-50 px-2 py-1 text-amber-700">
                            竞品 · {value}
                          </span>
                        ))}
                        {topic.last_refresh_new_budget_signals?.slice(0, 1).map((value) => (
                          <span key={`${topic.id}-new-budget-${value}`} className="rounded-full bg-emerald-50 px-2 py-1 text-emerald-700">
                            预算 · {value}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => void handleRefreshTrackingTopic(topic.id)}
                        className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                        disabled={refreshingTopicId === topic.id}
                      >
                        {refreshingTopicId === topic.id
                          ? t("research.centerRefreshingTopic", "刷新中...")
                          : t("research.centerRefreshTopic", "一键刷新研报")}
                      </button>
                      <button type="button" onClick={() => applyTrackingTopic(topic)} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                        {t("research.centerApplyTopic", "应用专题")}
                      </button>
                      <button type="button" onClick={() => void handleCreateWatchlist(topic)} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                        {t("research.centerCreateWatchlist", "设为 Watchlist")}
                      </button>
                      {topic.last_report_entry_id ? (
                        <Link href={`/knowledge/${topic.last_report_entry_id}`} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                          {t("research.centerOpenLatestReport", "打开最新研报")}
                        </Link>
                      ) : null}
                      <Link href={buildTopicWorkspaceHref(topic.id)} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                        {t("research.centerOpenTopicWorkspace", "专题版本对比")}
                      </Link>
                      <Link href={buildCompareHref({ query: topic.keyword, region: topic.region_filter, industry: topic.industry_filter, topicId: topic.id })} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                        {t("research.centerOpenCompare", "打开对比矩阵")}
                      </Link>
                    </div>
                    {topic.report_history?.length ? (
                      <div className="mt-3 rounded-[18px] border border-white/60 bg-white/55 p-3">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                          {t("research.centerTopicHistory", "最近版本")}
                        </p>
                        <div className="mt-2 space-y-2">
                          {topic.report_history.slice(0, 2).map((version) => (
                            <div key={`${topic.id}-${version.refreshed_at}`} className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                              <span>{new Date(version.refreshed_at).toLocaleString()}</span>
                              <span className={`rounded-full px-2 py-0.5 font-medium ${qualityTone(version.evidence_density)}`}>
                                {t("research.centerEvidenceDensity", "证据密度")}·{qualityLabel(version.evidence_density)}
                              </span>
                              <span className={`rounded-full px-2 py-0.5 font-medium ${qualityTone(version.source_quality)}`}>
                                {t("research.centerSourceQuality", "来源质量")}·{qualityLabel(version.source_quality)}
                              </span>
                              <span>{t("research.centerCardSources", "来源数")} {version.source_count}</span>
                              {version.new_target_count ? <span>新增甲方 {version.new_target_count}</span> : null}
                              {version.new_competitor_count ? <span>新增竞品 {version.new_competitor_count}</span> : null}
                              {version.new_budget_signal_count ? <span>新增预算 {version.new_budget_signal_count}</span> : null}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </article>
                ))
              ) : (
                <p className="text-sm text-slate-500">
                  {t("research.centerTrackingEmpty", "还没有长期跟踪专题，可把高价值关键词固定下来。")}
                </p>
              )}
            </div>
          </section>

          <section className="af-glass rounded-[30px] p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="af-kicker">Review Queue</p>
                <h3 className="mt-2 text-lg font-semibold text-slate-900">低质量研报审计队列</h3>
                <p className="mt-2 text-sm text-slate-500">
                  {sanitizeExternalDisplayText("将 audit / rewrite 治理沉淀为可审查队列，支持先查看 diff，再决定接受或回退。")}
                </p>
              </div>
              <div className="rounded-full border border-white/70 bg-white/70 px-3 py-1.5 text-xs text-slate-500">
                待处理 · {lowQualityQueue?.flagged_reports ?? 0}
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2 text-[11px]">
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">
                扫描研报 {lowQualityQueue?.total_reports ?? 0}
              </span>
              <span className="rounded-full bg-rose-50 px-2.5 py-1 text-rose-700">
                队列样本 {lowQualityQueue?.items.length ?? 0}
              </span>
              {(lowQualityQueue?.invalid_payloads ?? 0) > 0 ? (
                <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-700">
                  schema 异常 {lowQualityQueue?.invalid_payloads ?? 0}
                </span>
              ) : null}
            </div>
            {lowQualityQueue?.recommendations?.length ? (
              <p className="mt-3 rounded-2xl border border-white/60 bg-white/65 px-3 py-2 text-sm text-slate-600">
                {sanitizeExternalDisplayText(lowQualityQueue.recommendations[0])}
              </p>
            ) : null}
            {lowQualityMessage ? <p className="mt-3 text-sm text-emerald-700">{lowQualityMessage}</p> : null}
            {lowQualityError ? <p className="mt-3 text-sm text-rose-600">{lowQualityError}</p> : null}
            {lowQualityLoading ? (
              <p className="mt-4 text-sm text-slate-500">{t("common.loading", "加载中")}</p>
            ) : lowQualityQueue?.items.length ? (
              <div className="mt-4 space-y-3">
                {lowQualityQueue.items.map((item) => {
                  const latestRewrite = item.latest_rewrite;
                  const rewriteBusy = lowQualityActionKey === `${item.entry_id}:rewrite`;
                  const acceptBusy = lowQualityActionKey === `${item.entry_id}:accept`;
                  const revertBusy = lowQualityActionKey === `${item.entry_id}:revert`;
                  return (
                    <article key={item.entry_id} className="rounded-[22px] border border-white/60 bg-white/65 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-slate-900">{item.report_title || item.entry_title || item.entry_id}</p>
                          <p className="mt-1 text-xs text-slate-500">
                            {item.keyword || "历史研报"} · 风险 {item.risk_score} · 来源 {item.source_count}
                          </p>
                        </div>
                        <div className="flex flex-wrap justify-end gap-2 text-[11px]">
                          <span className={`rounded-full px-2.5 py-1 font-medium ${lowQualityReviewStatusTone(item.review_status)}`}>
                            {lowQualityReviewStatusLabel(item.review_status)}
                          </span>
                          {item.guarded_backlog ? (
                            <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-700">guarded backlog</span>
                          ) : null}
                          <span className={`rounded-full px-2.5 py-1 font-medium ${qualityTone(item.retrieval_quality || "low")}`}>
                            检索·{qualityLabel(item.retrieval_quality || "low")}
                          </span>
                          <span className="rounded-full bg-white/80 px-2.5 py-1 text-slate-500">
                            官方源 {Math.round((item.official_source_ratio || 0) * 100)}%
                          </span>
                        </div>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-slate-600">{item.executive_summary || item.next_action || "待人工复核"}</p>
                      {item.issues?.length ? (
                        <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                          {item.issues.slice(0, 3).map((issue) => (
                            <span key={`${item.entry_id}-${issue.code}`} className="rounded-full bg-rose-50 px-2 py-1 text-rose-700">
                              {issue.code}
                            </span>
                          ))}
                        </div>
                      ) : null}
                      {item.suggested_focus?.length ? (
                        <p className="mt-2 text-xs text-slate-500">建议收口：{item.suggested_focus.join(" / ")}</p>
                      ) : null}
                      {latestRewrite ? (
                        <div className="mt-3 rounded-[18px] border border-sky-100 bg-sky-50/70 p-3">
                          <div className="flex flex-wrap items-center gap-2 text-[11px] text-sky-700">
                            <span className="rounded-full bg-white/80 px-2 py-1">
                              {latestRewrite.rewrite_mode === "guarded" ? "guarded rewrite" : "standard rewrite"}
                            </span>
                            <span>
                              风险 {latestRewrite.before_risk_score} → {latestRewrite.after_risk_score}
                            </span>
                          </div>
                          <p className="mt-2 text-xs text-slate-500">Before · {latestRewrite.before_title || "空标题"}</p>
                          <p className="mt-1 text-sm font-medium text-slate-900">After · {latestRewrite.after_title || "空标题"}</p>
                          {latestRewrite.after_summary ? (
                            <p className="mt-2 text-sm leading-6 text-slate-600">{sanitizeExternalDisplayText(latestRewrite.after_summary)}</p>
                          ) : null}
                        </div>
                      ) : null}
                      <div className="mt-3 flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => void handleRewriteLowQualityItem(item.entry_id)}
                          className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                          disabled={Boolean(lowQualityActionKey)}
                        >
                          {rewriteBusy ? "重写中..." : "执行 rewrite"}
                        </button>
                        {item.review_status === "rewritten" ? (
                          <button
                            type="button"
                            onClick={() => void handleResolveLowQualityItem(item.entry_id, "accept")}
                            className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                            disabled={Boolean(lowQualityActionKey)}
                          >
                            {acceptBusy ? "接受中..." : "接受结果"}
                          </button>
                        ) : null}
                        {item.has_rewrite_snapshot ? (
                          <button
                            type="button"
                            onClick={() => void handleResolveLowQualityItem(item.entry_id, "revert")}
                            className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                            disabled={Boolean(lowQualityActionKey)}
                          >
                            {revertBusy ? "回退中..." : "回退版本"}
                          </button>
                        ) : null}
                        <Link href={`/knowledge/${item.entry_id}`} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                          打开研报
                        </Link>
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-500">当前没有待处理的低质量研报。</p>
            )}
          </section>

          <section className="af-glass rounded-[30px] p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="af-kicker">{t("research.watchlistKicker", "Watchlists")}</p>
                <h3 className="mt-2 text-lg font-semibold text-slate-900">
                  {t("research.watchlistTitle", "长期监控 Watchlist")}
                </h3>
                <p className="mt-2 text-sm text-slate-500">
                  {sanitizeExternalDisplayText(t("research.watchlistDesc", "将专题刷新结果沉淀为变化摘要，集中查看当日新增内容。"))}
                </p>
              </div>
              <button
                type="button"
                onClick={() => void handleRunDueWatchlists()}
                className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                disabled={runningDueWatchlists}
              >
                {runningDueWatchlists
                  ? t("research.watchlistRunDueRunning", "执行中...")
                  : t("research.watchlistRunDue", "执行到期 Watchlist")}
              </button>
            </div>
            {watchlistMessage ? <p className="mt-3 text-sm text-emerald-700">{watchlistMessage}</p> : null}
            {watchlistError ? <p className="mt-2 text-sm text-rose-600">{watchlistError}</p> : null}
            <div className="mt-4 rounded-[22px] border border-white/60 bg-white/65 p-4 text-xs text-slate-600">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded-full px-2.5 py-1 font-medium ${
                    watchlistAutomation?.loaded
                      ? "bg-emerald-50 text-emerald-700"
                      : watchlistAutomation?.installed
                        ? "bg-amber-50 text-amber-700"
                        : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {watchlistAutomation?.loaded
                    ? t("research.watchlistAutomationLoaded", "本地自动巡检已加载")
                    : watchlistAutomation?.installed
                      ? t("research.watchlistAutomationInstalled", "已安装，等待 launchd 加载")
                      : t("research.watchlistAutomationMissing", "尚未安装本地自动巡检")}
                </span>
                <span className={`rounded-full px-2.5 py-1 font-medium ${watchlistAutomationStatusTone(watchlistAutomation?.last_run_status)}`}>
                  {watchlistAutomationStatusLabel(watchlistAutomation?.last_run_status)}
                </span>
                <span className={`rounded-full px-2.5 py-1 font-medium ${watchlistAutomationAlertTone(watchlistAutomation?.alert_level)}`}>
                  {watchlistAutomationAlertLabel(watchlistAutomation?.alert_level)}
                </span>
                {watchlistAutomation?.interval_seconds ? (
                  <span className="rounded-full bg-white/75 px-2.5 py-1 text-slate-500">
                    {t("research.watchlistAutomationInterval", "巡检间隔")} · {formatAutomationInterval(watchlistAutomation.interval_seconds)}
                  </span>
                ) : null}
                {watchlistAutomation?.last_checked_at ? (
                  <span className="rounded-full bg-white/75 px-2.5 py-1 text-slate-500">
                    {t("research.watchlistAutomationLastRun", "最近自动运行")} · {formatWatchlistTime(watchlistAutomation.last_checked_at)}
                  </span>
                ) : null}
              </div>
              {watchlistAutomation?.action_required ? (
                <div className="mt-3 rounded-2xl border border-rose-200/80 bg-rose-50/75 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-rose-700">当前需要处理</p>
                    <div className="flex flex-wrap gap-2">
                      {watchlistAutomation?.recommended_run_due_command ? (
                        <button
                          type="button"
                          className="af-btn af-btn-secondary border px-2.5 py-1 text-[11px]"
                          onClick={() =>
                            void copyWatchlistOpsText(
                              watchlistAutomation.recommended_run_due_command,
                              "手动重跑命令",
                            )
                          }
                        >
                          复制重跑命令
                        </button>
                      ) : null}
                      {watchlistAutomation?.recommended_status_command ? (
                        <button
                          type="button"
                          className="af-btn af-btn-secondary border px-2.5 py-1 text-[11px]"
                          onClick={() =>
                            void copyWatchlistOpsText(
                              watchlistAutomation.recommended_status_command,
                              "巡检状态命令",
                            )
                          }
                        >
                          复制状态命令
                        </button>
                      ) : null}
                    </div>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-rose-800">
                    {sanitizeExternalDisplayText(
                      watchlistAutomation.action_required_reason || watchlistAutomation.last_failure_hint || "当前自动巡检需要人工检查。",
                    )}
                  </p>
                </div>
              ) : null}
              <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-2xl border border-slate-200/80 bg-slate-50/80 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.12em] text-slate-500">
                    {t("research.watchlistAutomationDue", "最近到期")}
                  </p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">{watchlistAutomation?.last_due_count ?? 0}</p>
                </div>
                <div className="rounded-2xl border border-slate-200/80 bg-slate-50/80 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.12em] text-slate-500">
                    {t("research.watchlistAutomationRefreshed", "最近刷新")}
                  </p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">{watchlistAutomation?.last_refreshed_count ?? 0}</p>
                </div>
                <div className="rounded-2xl border border-slate-200/80 bg-slate-50/80 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.12em] text-slate-500">
                    {t("research.watchlistAutomationFailed", "最近失败")}
                  </p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">{watchlistAutomation?.last_failed_count ?? 0}</p>
                </div>
                <div className="rounded-2xl border border-slate-200/80 bg-slate-50/80 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.12em] text-slate-500">日志大小</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">
                    {watchlistAutomation?.last_log_size_bytes
                      ? `${Math.max(1, Math.round(watchlistAutomation.last_log_size_bytes / 1024))} KB`
                      : "—"}
                  </p>
                </div>
                <div className="rounded-2xl border border-slate-200/80 bg-slate-50/80 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.12em] text-slate-500">状态新鲜度</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">
                    {watchlistAutomation?.last_checked_at
                      ? `${formatWatchlistAge(watchlistAutomation.state_age_seconds)} 前`
                      : "—"}
                  </p>
                  <p className={`mt-1 text-[11px] ${watchlistAutomation?.state_stale ? "text-rose-600" : "text-slate-500"}`}>
                    {watchlistAutomation?.state_stale ? "状态已过期" : "状态仍在刷新窗口内"}
                  </p>
                </div>
                <div className="rounded-2xl border border-slate-200/80 bg-slate-50/80 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.12em] text-slate-500">最近请求失败</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">{watchlistAutomation?.recent_request_failure_count ?? 0}</p>
                  <p className="mt-1 text-[11px] text-slate-500">
                    连续失败 {watchlistAutomation?.consecutive_request_failure_count ?? 0}
                  </p>
                </div>
              </div>
              <p className="mt-2 text-slate-500">
                {watchlistAutomation?.last_summary
                  ? sanitizeExternalDisplayText(watchlistAutomation.last_summary)
                  : t(
                    "research.watchlistAutomationHint",
                    "建议把本地 watchlist 调度交给 launchd，每小时触发一次，脚本只刷新已到期 watchlist 并写回提醒状态。",
                  )}
              </p>
              {watchlistAutomation?.last_failure_hint ? (
                <p className="mt-2 text-sm text-rose-600">{sanitizeExternalDisplayText(watchlistAutomation.last_failure_hint)}</p>
              ) : null}
              {lastRunDueResult ? (
                <div className="mt-3 rounded-2xl border border-sky-100 bg-sky-50/70 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.12em] text-sky-600">最近一次手动执行</p>
                      <p className="mt-1 text-sm font-semibold text-slate-900">
                        {formatWatchlistTime(lastRunDueResult.checked_at) || "刚刚"}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2 text-[11px]">
                      <span className="rounded-full bg-white/85 px-2.5 py-1 text-slate-600">
                        到期 {lastRunDueResult.due_count}
                      </span>
                      <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700">
                        刷新 {lastRunDueResult.refreshed_count}
                      </span>
                      <span className="rounded-full bg-rose-50 px-2.5 py-1 text-rose-700">
                        失败 {lastRunDueResult.failed_count}
                      </span>
                    </div>
                  </div>
                  {lastRunDueResult.items.length ? (
                    <div className="mt-3 space-y-2">
                      {lastRunDueResult.items.slice(0, 4).map((item) => (
                        <div key={`${item.watchlist_id}-last-run`} className="rounded-2xl border border-white/70 bg-white/80 px-3 py-2">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="text-sm font-semibold text-slate-900">{item.name}</p>
                            <span className={`rounded-full px-2 py-1 text-[11px] ${watchlistRunItemStatusTone(item.status)}`}>
                              {watchlistRunItemStatusLabel(item.status)}
                            </span>
                          </div>
                          <p className="mt-1 text-sm leading-6 text-slate-600">
                            {sanitizeExternalDisplayText(item.error || item.summary)}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
              <div className="mt-3 grid gap-2 lg:grid-cols-2">
                <div className="rounded-2xl border border-slate-200/80 bg-white/84 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-slate-500">重跑命令</p>
                    <button
                      type="button"
                      className="af-btn af-btn-secondary border px-2.5 py-1 text-[11px]"
                      onClick={() =>
                        void copyWatchlistOpsText(
                          watchlistAutomation?.recommended_run_due_command || "npm run research:watchlists:run-due",
                          "重跑命令",
                        )
                      }
                    >
                      {t("common.copy", "复制")}
                    </button>
                  </div>
                  <code className="mt-2 block overflow-x-auto rounded-2xl border border-slate-200/80 bg-slate-950/95 px-3 py-2 text-[11px] leading-5 text-slate-100">
                    {watchlistAutomation?.recommended_run_due_command || "npm run research:watchlists:run-due"}
                  </code>
                </div>
                <div className="rounded-2xl border border-slate-200/80 bg-white/84 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-slate-500">状态命令</p>
                    <button
                      type="button"
                      className="af-btn af-btn-secondary border px-2.5 py-1 text-[11px]"
                      onClick={() =>
                        void copyWatchlistOpsText(
                          watchlistAutomation?.recommended_status_command || "npm run research:watchlists:automation:status",
                          "状态命令",
                        )
                      }
                    >
                      {t("common.copy", "复制")}
                    </button>
                  </div>
                  <code className="mt-2 block overflow-x-auto rounded-2xl border border-slate-200/80 bg-slate-950/95 px-3 py-2 text-[11px] leading-5 text-slate-100">
                    {watchlistAutomation?.recommended_status_command || "npm run research:watchlists:automation:status"}
                  </code>
                </div>
              </div>
              <div className="mt-3 grid gap-2 lg:grid-cols-2">
                <div className="rounded-2xl border border-slate-200/80 bg-white/84 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-slate-500">安装命令</p>
                    <button
                      type="button"
                      className="af-btn af-btn-secondary border px-2.5 py-1 text-[11px]"
                      onClick={() =>
                        void copyWatchlistOpsText(
                          watchlistAutomation?.recommended_install_command ||
                            "npm run research:watchlists:automation:install",
                          "安装命令",
                        )
                      }
                    >
                      {t("common.copy", "复制")}
                    </button>
                  </div>
                  <code className="mt-2 block overflow-x-auto rounded-2xl border border-slate-200/80 bg-slate-950/95 px-3 py-2 text-[11px] leading-5 text-slate-100">
                    {watchlistAutomation?.recommended_install_command || "npm run research:watchlists:automation:install"}
                  </code>
                </div>
                <div className="rounded-2xl border border-slate-200/80 bg-white/84 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-slate-500">卸载命令</p>
                    <button
                      type="button"
                      className="af-btn af-btn-secondary border px-2.5 py-1 text-[11px]"
                      onClick={() =>
                        void copyWatchlistOpsText(
                          watchlistAutomation?.recommended_uninstall_command ||
                            "npm run research:watchlists:automation:uninstall",
                          "卸载命令",
                        )
                      }
                    >
                      {t("common.copy", "复制")}
                    </button>
                  </div>
                  <code className="mt-2 block overflow-x-auto rounded-2xl border border-slate-200/80 bg-slate-950/95 px-3 py-2 text-[11px] leading-5 text-slate-100">
                    {watchlistAutomation?.recommended_uninstall_command || "npm run research:watchlists:automation:uninstall"}
                  </code>
                </div>
              </div>
              <div className="mt-3 grid gap-2 lg:grid-cols-3">
                {[
                  { label: "launchd plist", value: watchlistAutomation?.plist_path || "" },
                  { label: "状态文件", value: watchlistAutomation?.state_path || "" },
                  { label: "运行日志", value: watchlistAutomation?.log_path || "" },
                ].map((item) => (
                  <div key={item.label} className="rounded-2xl border border-slate-200/80 bg-white/84 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-[11px] uppercase tracking-[0.12em] text-slate-500">{item.label}</p>
                      {item.value ? (
                        <button
                          type="button"
                          className="af-btn af-btn-secondary border px-2.5 py-1 text-[11px]"
                          onClick={() => void copyWatchlistOpsText(item.value, `${item.label}路径`)}
                        >
                          {t("common.copy", "复制")}
                        </button>
                      ) : null}
                    </div>
                    <p className="mt-2 break-all text-[11px] leading-5 text-slate-600">
                      {item.value || "当前未返回路径"}
                    </p>
                  </div>
                ))}
              </div>
              {watchlistAutomation?.failed_items?.length ? (
                <div className="mt-3 space-y-2">
                  <p className="text-[11px] uppercase tracking-[0.12em] text-slate-500">最近失败样本</p>
                  {watchlistAutomation.failed_items.map((item) => (
                    <div key={`${item.watchlist_id || item.name}-failed`} className="rounded-2xl border border-rose-100 bg-rose-50/70 px-3 py-2">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-slate-900">{item.name}</p>
                        <span className="rounded-full bg-white/80 px-2 py-1 text-[11px] text-rose-700">
                          {item.change_count ? `changes ${item.change_count}` : "failed"}
                        </span>
                      </div>
                      <p className="mt-1 text-sm leading-6 text-slate-600">{sanitizeExternalDisplayText(item.error || item.summary)}</p>
                      {item.next_due_at ? (
                        <p className="mt-1 text-xs text-slate-500">下次到期 · {formatWatchlistTime(item.next_due_at)}</p>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
            <div className="mt-4 space-y-3">
              {watchlists.length ? (
                watchlists.map((watchlist) => (
                  <article key={watchlist.id} className="rounded-[22px] border border-white/60 bg-white/65 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{watchlist.name}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          {watchlist.query} · {watchlist.alert_level} · {formatWatchlistSchedule(watchlist.schedule, t)}
                        </p>
                        <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
                          <span className={`rounded-full px-2.5 py-1 ${watchlistStatusTone(watchlist.status)}`}>
                            {watchlistStatusLabel(watchlist.status)}
                          </span>
                          {watchlist.is_due ? (
                            <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-700">
                              {t("research.watchlistDueNow", "已到刷新窗口")}
                            </span>
                          ) : null}
                          {watchlist.last_checked_at ? (
                            <span className="rounded-full bg-white/75 px-2.5 py-1 text-slate-500">
                              {t("research.watchlistLastChecked", "最近检查")} · {formatWatchlistTime(watchlist.last_checked_at)}
                            </span>
                          ) : null}
                          {watchlist.next_due_at ? (
                            <span className="rounded-full bg-white/75 px-2.5 py-1 text-slate-500">
                              {t("research.watchlistNextDue", "下次到期")} · {formatWatchlistTime(watchlist.next_due_at)}
                            </span>
                          ) : null}
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        <select
                          value={watchlist.schedule}
                          onChange={(event) => void handleUpdateWatchlistSchedule(watchlist.id, event.target.value)}
                          className="af-input min-w-[136px] bg-white/70 py-1.5 text-xs"
                          disabled={watchlistActionKey === `${watchlist.id}-schedule`}
                        >
                          {WATCHLIST_SCHEDULE_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                              {formatWatchlistSchedule(option.value, t)}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          onClick={() => void handleToggleWatchlistStatus(watchlist)}
                          className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                          disabled={watchlistActionKey === `${watchlist.id}-status`}
                        >
                          {watchlistActionKey === `${watchlist.id}-status`
                            ? "处理中..."
                            : watchlist.status === "paused"
                              ? "恢复 Watchlist"
                              : "暂停 Watchlist"}
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleRefreshWatchlist(watchlist.id)}
                          className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                          disabled={refreshingWatchlistId === watchlist.id}
                        >
                          {refreshingWatchlistId === watchlist.id
                            ? t("research.watchlistRefreshing", "刷新中...")
                            : t("research.watchlistRefresh", "刷新 Watchlist")}
                        </button>
                      </div>
                    </div>
                    {watchlist.status === "paused" ? (
                      <p className="mt-3 text-xs text-slate-500">
                        当前已暂停自动刷新，仍可手动执行一次 Watchlist。
                      </p>
                    ) : null}
                    <div className="mt-3 space-y-2">
                      {(watchlist.latest_changes?.length
                        ? watchlist.latest_changes.slice(0, 3)
                        : []).map((change) => (
                        <div key={change.id} className="rounded-2xl border border-slate-200/80 bg-slate-50/80 px-3 py-2">
                          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                            {change.change_type} · {change.severity}
                          </p>
                          <p className="mt-1 text-sm text-slate-700">{sanitizeExternalDisplayText(change.summary)}</p>
                        </div>
                      ))}
                      {!watchlist.latest_changes?.length ? (
                        <p className="text-sm text-slate-500">
                          {t("research.watchlistEmpty", "还没有变化摘要，可先刷新一次 Watchlist。")}
                        </p>
                      ) : null}
                    </div>
                  </article>
                ))
              ) : (
                <p className="text-sm text-slate-500">
                  {t("research.watchlistEmpty", "还没有变化摘要，可先刷新一次 Watchlist。")}
                </p>
              )}
            </div>
          </section>
        </aside>

        <div className="space-y-4">
          <section className="af-glass rounded-[30px] p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="af-kicker">{t("research.centerResultKicker", "Workspace")}</p>
                <h3 className="mt-2 text-xl font-semibold tracking-[-0.03em] text-slate-900">
                  {t("research.centerResultTitle", "研究结果工作台")}
                </h3>
                <p className="mt-2 text-sm text-slate-500">{activePerspective.desc}</p>
              </div>
              <div className="rounded-full border border-white/70 bg-white/70 px-3 py-1.5 text-sm text-slate-500">
                {t("research.centerVisibleCount", "可见卡片")} · {visibleItems.length}
              </div>
            </div>

            {activeFilterLabels.length ? (
              <div className="mt-4 flex flex-wrap gap-2">
                {activeFilterLabels.map((label) => (
                  <span key={label} className="rounded-full bg-slate-900 px-3 py-1.5 text-xs font-medium text-white/90">
                    {label}
                  </span>
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-500">
                {t("research.centerNoFilterHint", "当前展示全部研报与行动卡，可从左侧按区域、行业或动作类型快速收窄。")}
              </p>
            )}
          </section>

          {loading ? (
            <section className="af-glass rounded-[30px] p-5 md:p-7 text-sm text-slate-500">
              {t("common.loading", "加载中")}
            </section>
          ) : null}
          {error ? (
            <section className="af-glass rounded-[30px] p-5 md:p-7 text-sm text-rose-600">
              {error}
            </section>
          ) : null}

          {!loading && !error && visibleItems.length === 0 ? (
            <section className="af-glass rounded-[30px] p-5 md:p-7 text-sm text-slate-500">
              {t("research.centerEmpty", "当前没有匹配的研报或行动卡。")}
            </section>
          ) : null}

          {!loading && !error ? (
            <section className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
              {visibleItems.map((entry) => {
                const isReport = entry.source_domain === "research.report";
                const actionType = isReport ? null : getActionType(entry);
                const sourceCount = getResearchSourceCount(entry);
                const keyword = getResearchKeyword(entry);
                const reportMeta = getResearchReportMeta(entry);
                const diagnosticsMeta = isReport ? getResearchSourceDiagnostics(entry) : null;
                const readinessStatus = isReport ? getResearchReadinessStatus(entry) : "needs_evidence";
                const weakSectionSummary = isReport ? getResearchWeakSectionSummary(entry) : null;
                const rankedPreview = isReport ? getResearchRankedPreview(entry) : [];
                const actionCards = isReport ? getResearchActionCards(entry) : [];
                return (
                  <article
                    key={entry.id}
                    className="af-glass rounded-[28px] p-5 transition duration-200 hover:-translate-y-0.5 hover:shadow-[0_20px_45px_rgba(15,23,42,0.08)]"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${
                          isReport ? "bg-sky-100 text-sky-700" : "bg-amber-100 text-amber-700"
                        }`}
                      >
                        {isReport ? t("research.centerReportBadge", "研报") : t("research.centerActionBadge", "行动卡")}
                      </span>
                      {entry.is_focus_reference ? (
                        <span className="rounded-full bg-slate-900 px-2.5 py-1 text-[11px] font-semibold text-white/90">
                          {t("research.centerFocusBadge", "Focus 参考")}
                        </span>
                      ) : null}
                    </div>

                    <Link href={`/knowledge/${entry.id}`} className="block">
                      <h3 className="mt-4 text-lg font-semibold leading-7 text-slate-900">{entry.title}</h3>
                      <p className="mt-3 text-sm leading-6 text-slate-600">{buildPreview(entry)}</p>
                    </Link>

                    {isReport && diagnosticsMeta ? (
                      <div className="mt-4 space-y-3">
                        <div className="grid gap-3 sm:grid-cols-2">
                          <div className="rounded-[18px] border border-white/60 bg-white/55 p-3">
                            <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">可信度</p>
                            <div className="mt-2 flex flex-wrap gap-2">
                              <span
                                className={`rounded-full px-2.5 py-1 text-[11px] ${
                                  diagnosticsMeta.evidenceMode === "strong"
                                    ? "bg-emerald-50 text-emerald-700"
                                    : diagnosticsMeta.evidenceMode === "provisional"
                                      ? "bg-amber-50 text-amber-700"
                                      : "bg-slate-100 text-slate-600"
                                }`}
                              >
                                {diagnosticsMeta.evidenceMode === "strong"
                                  ? "强证据"
                                  : diagnosticsMeta.evidenceMode === "provisional"
                                    ? "可用初版"
                                    : "兜底候选"}
                              </span>
                              <span className="rounded-full bg-white/75 px-2.5 py-1 text-[11px] text-slate-500">
                                官方源 {Math.round(diagnosticsMeta.officialSourceRatio * 100)}%
                              </span>
                              <span className="rounded-full bg-white/75 px-2.5 py-1 text-[11px] text-slate-500">
                                严格命中 {Math.round(diagnosticsMeta.strictMatchRatio * 100)}%
                              </span>
                            </div>
                            <p className="mt-2 text-xs leading-5 text-slate-500">
                              {diagnosticsMeta.correctiveTriggered
                                ? "当前已触发纠错检索，优先看新增官方源和严格命中结果。"
                                : diagnosticsMeta.expansionTriggered
                                  ? "当前已扩搜补证，建议继续核对关键实体和范围。"
                                  : "当前展示的是本次检索链路的可信度摘要。"}
                            </p>
                          </div>
                          <div className="rounded-[18px] border border-white/60 bg-white/55 p-3">
                            <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">账户与门槛</p>
                            <div className="mt-2 flex flex-wrap gap-2">
                              <span
                                className={`rounded-full px-2.5 py-1 text-[11px] ${
                                  diagnosticsMeta.unsupportedTargetAccounts.length
                                    ? "bg-rose-50 text-rose-700"
                                    : diagnosticsMeta.supportedTargetAccounts.length
                                      ? "bg-emerald-50 text-emerald-700"
                                      : "bg-slate-100 text-slate-600"
                                }`}
                              >
                                {diagnosticsMeta.unsupportedTargetAccounts.length
                                  ? "目标账户待支撑"
                                  : diagnosticsMeta.supportedTargetAccounts.length
                                    ? `已支撑 ${diagnosticsMeta.supportedTargetAccounts.length} 个账户`
                                    : "待收敛到账户"}
                              </span>
                              <span
                                className={`rounded-full px-2.5 py-1 text-[11px] ${
                                  readinessStatus === "ready"
                                    ? "bg-emerald-50 text-emerald-700"
                                    : readinessStatus === "degraded"
                                      ? "bg-amber-50 text-amber-700"
                                      : "bg-slate-100 text-slate-600"
                                }`}
                              >
                                {readinessStatus === "ready"
                                  ? "可直接推进"
                                  : readinessStatus === "degraded"
                                    ? "候选推进"
                                    : "待补证"}
                              </span>
                              {diagnosticsMeta.guardedBacklog ? (
                                <span className="rounded-full bg-rose-50 px-2.5 py-1 text-[11px] text-rose-700">
                                  Guarded backlog
                                </span>
                              ) : null}
                            </div>
                            <p className="mt-2 text-xs leading-5 text-slate-500">
                              {diagnosticsMeta.unsupportedTargetAccounts.slice(0, 2).join(" / ") ||
                                diagnosticsMeta.supportedTargetAccounts.slice(0, 2).join(" / ") ||
                                "当前还没有稳定的目标账户支撑，适合继续补证。"}
                            </p>
                          </div>
                        </div>
                        {weakSectionSummary ? (
                          <div className="rounded-[18px] border border-amber-200/80 bg-amber-50/75 p-3">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-[11px] uppercase tracking-[0.18em] text-amber-700">最弱章节</p>
                              <span
                                className={`rounded-full px-2.5 py-1 text-[11px] ${
                                  weakSectionSummary.status === "needs_evidence"
                                    ? "bg-rose-100 text-rose-700"
                                    : "bg-amber-100 text-amber-700"
                                }`}
                              >
                                {weakSectionSummary.status === "needs_evidence" ? "待补证" : "待收紧"}
                              </span>
                            </div>
                            <p className="mt-2 text-sm font-semibold text-slate-900">{weakSectionSummary.title}</p>
                            <p className="mt-2 text-xs leading-5 text-slate-600">{weakSectionSummary.summary}</p>
                          </div>
                        ) : null}
                      </div>
                    ) : null}

                    {isReport && actionCards.length ? (
                      <div className="mt-4 grid gap-3">
                        {actionCards.map((card) => (
                          <div key={`${entry.id}-${card.title}`} className="rounded-[18px] border border-white/60 bg-white/55 p-3">
                            <p className="break-words text-sm font-semibold leading-6 text-slate-900">{card.title}</p>
                            <div className="mt-2 grid gap-2 break-words text-xs text-slate-500">
                              {card.target_persona ? (
                                <div className="rounded-2xl border border-slate-200/70 bg-slate-50/85 px-3 py-2">
                                  <span className="font-medium text-slate-700">{t("research.actionTarget", "优先对象")}：</span>
                                  {card.target_persona}
                                </div>
                              ) : null}
                              {card.execution_window ? (
                                <div className="rounded-2xl border border-slate-200/70 bg-slate-50/85 px-3 py-2">
                                  <span className="font-medium text-slate-700">{t("research.actionWindow", "执行窗口")}：</span>
                                  {card.execution_window}
                                </div>
                              ) : null}
                              {card.deliverable ? (
                                <div className="rounded-2xl border border-slate-200/70 bg-slate-50/85 px-3 py-2">
                                  <span className="font-medium text-slate-700">{t("research.actionDeliverable", "产出物")}：</span>
                                  {card.deliverable}
                                </div>
                              ) : null}
                            </div>
                            {parseActionPhases(card.recommended_steps).length ? (
                              <div className="mt-3 grid gap-2">
                                {parseActionPhases(card.recommended_steps).map((phase) => (
                                  <div key={`${card.title}-${phase.label}-${phase.content}`} className="min-w-0 overflow-hidden rounded-2xl border border-slate-200/70 bg-white/85 px-3 py-2">
                                    <div className="flex flex-wrap items-center gap-2">
                                      <span className="rounded-full bg-slate-900 px-2 py-0.5 text-[10px] font-semibold text-white/90">
                                        {phase.label}
                                      </span>
                                      {phase.horizon ? (
                                        <span className="text-[11px] font-medium text-slate-500">{phase.horizon}</span>
                                      ) : null}
                                    </div>
                                    <p className="mt-2 min-w-0 break-words whitespace-pre-wrap text-xs leading-5 text-slate-600 [overflow-wrap:anywhere]">
                                      {phase.content}
                                    </p>
                                  </div>
                                ))}
                              </div>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    ) : null}

                    <div className="mt-4 flex flex-wrap gap-2">
                      {keyword ? (
                        <span className="rounded-full bg-white/70 px-2.5 py-1 text-[11px] text-slate-500">
                          {keyword}
                        </span>
                      ) : null}
                      {actionType ? (
                        <span className="rounded-full bg-white/70 px-2.5 py-1 text-[11px] text-slate-500">
                          {entry.action_type_label || actionType}
                        </span>
                      ) : null}
                      {entry.region_label ? (
                        <span className="rounded-full bg-white/70 px-2.5 py-1 text-[11px] text-slate-500">
                          {entry.region_label}
                        </span>
                      ) : null}
                      {entry.industry_label ? (
                        <span className="rounded-full bg-white/70 px-2.5 py-1 text-[11px] text-slate-500">
                          {entry.industry_label}
                        </span>
                      ) : null}
                      {isReport ? (
                        <>
                          <span className={`rounded-full px-2.5 py-1 text-[11px] ${qualityTone(reportMeta.evidenceDensity)}`}>
                            {t("research.centerEvidenceDensity", "证据密度")}·{qualityLabel(reportMeta.evidenceDensity)}
                          </span>
                          <span className={`rounded-full px-2.5 py-1 text-[11px] ${qualityTone(reportMeta.sourceQuality)}`}>
                            {t("research.centerSourceQuality", "来源质量")}·{qualityLabel(reportMeta.sourceQuality)}
                          </span>
                        </>
                      ) : null}
                    </div>

                    <div className="mt-5 grid gap-3 sm:grid-cols-3">
                      <div className="rounded-[18px] border border-white/60 bg-white/55 p-3">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                          {t("research.centerCardCollection", "分组")}
                        </p>
                        <p className="mt-2 text-sm font-medium text-slate-700">
                          {entry.collection_name || t("common.none", "暂无")}
                        </p>
                      </div>
                      <div className="rounded-[18px] border border-white/60 bg-white/55 p-3">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                          {t("research.centerCardSources", "来源数")}
                        </p>
                        <p className="mt-2 text-sm font-medium text-slate-700">{sourceCount || "—"}</p>
                      </div>
                      <div className="rounded-[18px] border border-white/60 bg-white/55 p-3">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                          {t("research.centerCardUpdated", "更新")}
                        </p>
                        <p className="mt-2 text-sm font-medium text-slate-700">
                          {new Date(entry.updated_at || entry.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>

                    {isReport && rankedPreview.length ? (
                      <div className="mt-4 grid gap-3">
                        {rankedPreview.map((group) => (
                          <div key={`${entry.id}-${group.key}`} className="rounded-[18px] border border-white/60 bg-white/55 p-3">
                            <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{group.title}</p>
                            <div className="mt-2 flex flex-wrap gap-2">
                              {group.items.map((itemValue) => (
                                <span key={`${group.key}-${itemValue.name}`} className="rounded-full bg-slate-900 px-2.5 py-1 text-[11px] text-white/90">
                                  {itemValue.name} · {itemValue.score_label}
                                </span>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : null}

                    {isReport && diagnosticsMeta && (diagnosticsMeta.scopeRegions.length || diagnosticsMeta.scopeIndustries.length || diagnosticsMeta.scopeClients.length || diagnosticsMeta.topicAnchors.length || diagnosticsMeta.matchedThemes.length || diagnosticsMeta.guardedBacklog || diagnosticsMeta.guardedReasonLabels.length || diagnosticsMeta.supportedTargetAccounts.length || diagnosticsMeta.unsupportedTargetAccounts.length || diagnosticsMeta.filteredOldSourceCount || diagnosticsMeta.filteredRegionConflictCount || diagnosticsMeta.normalizedEntityCount || diagnosticsMeta.uniqueDomainCount || diagnosticsMeta.candidateProfileCompanies.length || diagnosticsMeta.candidateProfileHitCount) ? (
                      <div className="mt-4 rounded-[18px] border border-white/60 bg-white/55 p-3">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                          {t("research.sourceDiagnosticsTitle", "采集诊断")}
                        </p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          <span
                            className={`rounded-full px-2.5 py-1 text-[11px] ${
                              diagnosticsMeta.evidenceMode === "strong"
                                ? "bg-emerald-50 text-emerald-700"
                                : diagnosticsMeta.evidenceMode === "provisional"
                                  ? "bg-amber-50 text-amber-700"
                                  : "bg-slate-100 text-slate-600"
                            }`}
                          >
                            {diagnosticsMeta.evidenceMode === "strong"
                              ? "强证据"
                              : diagnosticsMeta.evidenceMode === "provisional"
                                ? "可用初版"
                                : "兜底候选"}
                          </span>
                          {diagnosticsMeta.guardedBacklog ? (
                            <span className="rounded-full bg-rose-50 px-2.5 py-1 text-[11px] text-rose-700">
                              Guarded backlog
                            </span>
                          ) : null}
                          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-500">
                            检索质量 {diagnosticsMeta.retrievalQuality === "high" ? "高" : diagnosticsMeta.retrievalQuality === "medium" ? "中" : "低"}
                          </span>
                          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-500">
                            严格命中 {Math.round(diagnosticsMeta.strictMatchRatio * 100)}%
                          </span>
                          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-500">
                            官方源 {Math.round(diagnosticsMeta.officialSourceRatio * 100)}%
                          </span>
                          {diagnosticsMeta.uniqueDomainCount > 0 ? (
                            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-500">
                              域名 {diagnosticsMeta.uniqueDomainCount}
                            </span>
                          ) : null}
                          {diagnosticsMeta.scopeRegions.map((value) => (
                            <span key={`${entry.id}-scope-region-${value}`} className="rounded-full bg-cyan-50 px-2.5 py-1 text-[11px] text-cyan-700">
                              区域 · {value}
                            </span>
                          ))}
                          {diagnosticsMeta.scopeIndustries.map((value) => (
                            <span key={`${entry.id}-scope-industry-${value}`} className="rounded-full bg-blue-50 px-2.5 py-1 text-[11px] text-blue-700">
                              领域 · {value}
                            </span>
                          ))}
                          {diagnosticsMeta.scopeClients.map((value) => (
                            <span key={`${entry.id}-scope-client-${value}`} className="rounded-full bg-fuchsia-50 px-2.5 py-1 text-[11px] text-fuchsia-700">
                              公司 · {value}
                            </span>
                          ))}
                          {diagnosticsMeta.topicAnchors.map((value) => (
                            <span key={`${entry.id}-anchor-${value}`} className="rounded-full bg-violet-50 px-2.5 py-1 text-[11px] text-violet-700">
                              {value}
                            </span>
                          ))}
                          {diagnosticsMeta.matchedThemes.map((value) => (
                            <span key={`${entry.id}-theme-${value}`} className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] text-emerald-700">
                              {value}
                            </span>
                          ))}
                          {diagnosticsMeta.filteredOldSourceCount > 0 ? (
                            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-500">
                              {t("research.sourceDiagnosticsFilteredOld", "剔除过旧来源")} {diagnosticsMeta.filteredOldSourceCount}
                            </span>
                          ) : null}
                          {diagnosticsMeta.filteredRegionConflictCount > 0 ? (
                            <span className="rounded-full bg-rose-50 px-2.5 py-1 text-[11px] text-rose-700">
                              拦截越界区域 {diagnosticsMeta.filteredRegionConflictCount}
                            </span>
                          ) : null}
                          {diagnosticsMeta.strictTopicSourceCount > 0 ? (
                            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-500">
                              {t("research.sourceDiagnosticsStrictTopic", "严格主题保留")} {diagnosticsMeta.strictTopicSourceCount}
                            </span>
                          ) : null}
                          {diagnosticsMeta.normalizedEntityCount > 0 ? (
                            <span className="rounded-full bg-violet-50 px-2.5 py-1 text-[11px] text-violet-700">
                              实体 {diagnosticsMeta.normalizedEntityCount}
                            </span>
                          ) : null}
                          {diagnosticsMeta.expansionTriggered ? (
                            <span className="rounded-full bg-amber-50 px-2.5 py-1 text-[11px] text-amber-700">
                              已扩搜
                            </span>
                          ) : null}
                          {diagnosticsMeta.correctiveTriggered ? (
                            <span className="rounded-full bg-orange-50 px-2.5 py-1 text-[11px] text-orange-700">
                              已触发纠错检索
                            </span>
                          ) : null}
                          {diagnosticsMeta.candidateProfileCompanies.length ? (
                            <span className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] text-sky-700">
                              候选补证公司 {diagnosticsMeta.candidateProfileCompanies.length}
                            </span>
                          ) : null}
                          {diagnosticsMeta.candidateProfileHitCount > 0 ? (
                            <span className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] text-sky-700">
                              补证公开源 {diagnosticsMeta.candidateProfileHitCount}
                            </span>
                          ) : null}
                          {diagnosticsMeta.candidateProfileOfficialHitCount > 0 ? (
                            <span className="rounded-full bg-cyan-50 px-2.5 py-1 text-[11px] text-cyan-700">
                              其中官方源 {diagnosticsMeta.candidateProfileOfficialHitCount}
                            </span>
                          ) : null}
                        </div>
                        {diagnosticsMeta.guardedReasonLabels.length ? (
                          <div className="mt-2 flex flex-wrap gap-2">
                            {diagnosticsMeta.guardedReasonLabels.map((value) => (
                              <span key={`${entry.id}-guarded-reason-${value}`} className="rounded-full bg-rose-50 px-2.5 py-1 text-[11px] text-rose-700">
                                {value}
                              </span>
                            ))}
                          </div>
                        ) : null}
                        {diagnosticsMeta.supportedTargetAccounts.length || diagnosticsMeta.unsupportedTargetAccounts.length ? (
                          <div className="mt-2 flex flex-wrap gap-2">
                            {diagnosticsMeta.supportedTargetAccounts.map((value) => (
                              <span key={`${entry.id}-supported-target-${value}`} className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] text-emerald-700">
                                已支撑 · {value}
                              </span>
                            ))}
                            {diagnosticsMeta.unsupportedTargetAccounts.map((value) => (
                              <span key={`${entry.id}-unsupported-target-${value}`} className="rounded-full bg-rose-50 px-2.5 py-1 text-[11px] text-rose-700">
                                未支撑 · {value}
                              </span>
                            ))}
                          </div>
                        ) : null}
                        {diagnosticsMeta.normalizedEntityCount > 0 ? (
                          <div className="mt-2 flex flex-wrap gap-2">
                            <span className="rounded-full bg-violet-50 px-2.5 py-1 text-[11px] text-violet-700">
                              甲方 {diagnosticsMeta.normalizedTargetCount}
                            </span>
                            <span className="rounded-full bg-violet-50 px-2.5 py-1 text-[11px] text-violet-700">
                              竞品 {diagnosticsMeta.normalizedCompetitorCount}
                            </span>
                            <span className="rounded-full bg-violet-50 px-2.5 py-1 text-[11px] text-violet-700">
                              伙伴 {diagnosticsMeta.normalizedPartnerCount}
                            </span>
                          </div>
                        ) : null}
                        {diagnosticsMeta.candidateProfileCompanies.length ? (
                          <div className="mt-2 flex flex-wrap gap-2">
                            {diagnosticsMeta.candidateProfileCompanies.map((value) => (
                              <span
                                key={`${entry.id}-candidate-profile-${value}`}
                                className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] text-sky-700"
                              >
                                候选公司 · {value}
                              </span>
                            ))}
                          </div>
                        ) : null}
                        {diagnosticsMeta.candidateProfileSourceLabels.length ? (
                          <div className="mt-2 flex flex-wrap gap-2">
                            {diagnosticsMeta.candidateProfileSourceLabels.map((value) => (
                              <span
                                key={`${entry.id}-candidate-profile-source-${value}`}
                                className="rounded-full bg-cyan-50 px-2.5 py-1 text-[11px] text-cyan-700"
                              >
                                {value}
                              </span>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    ) : null}

                    <div className="mt-4 flex flex-wrap gap-2">
                      <Link href={`/knowledge/${entry.id}`} className="af-btn af-btn-secondary border px-3 py-1.5 text-sm">
                        <AppIcon name="knowledge" className="h-4 w-4" />
                        {t("research.centerOpenCard", "查看卡片")}
                      </Link>
                      {!isReport ? (
                        <Link
                          href={`/knowledge/${entry.id}/edit`}
                          className="af-btn af-btn-primary px-3 py-1.5 text-sm"
                        >
                          <AppIcon name="edit" className="h-4 w-4" />
                          {t("research.centerEditAction", "编辑行动卡")}
                        </Link>
                      ) : null}
                    </div>
                  </article>
                );
              })}
            </section>
          ) : null}
        </div>
      </div>
    </div>
  );
}
