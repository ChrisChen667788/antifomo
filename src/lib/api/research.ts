import type { AppLanguage } from "@/lib/preferences";
import { request } from "@/lib/api/client";
import type {
  ApiMobileDailyBrief,
  ApiResearchActionCard,
  ApiResearchActionPlan,
  ApiResearchActionSaveResponse,
  ApiResearchAssuranceSnapshot,
  ApiResearchCompareSnapshot,
  ApiResearchCompareSnapshotDetail,
  ApiResearchClarificationPacket,
  ApiResearchClarificationSubmitPayload,
  ApiResearchClarificationSubmitResponse,
  ApiResearchConversation,
  ApiResearchDeliveryExportDiagnostics,
  ApiResearchEntityDetail,
  ApiResearchExperienceFeedback,
  ApiResearchExperienceMetrics,
  ApiResearchExperienceReadiness,
  ApiResearchExperimentActivePolicy,
  ApiResearchExperimentControlPlane,
  ApiResearchExperimentEffectiveRuntimeConfig,
  ApiResearchExperimentGateConfig,
  ApiResearchExperimentLane,
  ApiResearchExperimentOrchestration,
  ApiResearchExperimentPlan,
  ApiResearchExperimentRuntimeSnapshot,
  ApiResearchFollowupDeltaEvaluation,
  ApiResearchGoldenEvaluation,
  ApiResearchIndustryKnowledgeRetrievalBenchmark,
  ApiResearchIndustryKnowledgeRetrievalApprovalTemplate,
  ApiResearchIndustryKnowledgeRetrievalAssuranceSnapshot,
  ApiResearchIndustryKnowledgeRetrievalEvidenceOperationsSnapshot,
  ApiResearchIndustryKnowledgeRetrievalEvidenceOperationsTemplates,
  ApiResearchIndustryKnowledgeRetrievalEvidenceTemplates,
  ApiResearchIndustryKnowledgeDeliveryReview,
  ApiResearchIndustryKnowledgeSearch,
  ApiResearchIndustrySkillLibrary,
  ApiResearchJob,
  ApiResearchJobTimelineEvent,
  ApiResearchLowQualityReviewActionResponse,
  ApiResearchLowQualityReviewQueue,
  ApiResearchMarkdownArchive,
  ApiResearchMarkdownArchiveDetail,
  ApiResearchOfflineEvaluation,
  ApiResearchReport,
  ApiResearchRetrievalIndexRebuildResult,
  ApiResearchRetrievalIndexSearchResult,
  ApiResearchRetrievalIndexStatus,
  ApiResearchUpgradeDiagnostics,
  ApiResearchSaveResponse,
  ApiResearchSavedView,
  ApiResearchSectionRetrievalPack,
  ApiResearchSolutionDeliveryPack,
  ApiResearchSourceSettings,
  ApiResearchTrackingTopic,
  ApiResearchTrackingTopicRefresh,
  ApiResearchTrackingTopicTimelineEvent,
  ApiResearchTrackingTopicVersionDetail,
  ApiResearchWatchlist,
  ApiResearchWatchlistAutomationStatus,
  ApiResearchWatchlistChangeEvent,
  ApiResearchWatchlistDigestExport,
  ApiResearchWatchlistOpsSummary,
  ApiResearchWatchlistRefresh,
  ApiResearchWatchlistRun,
  ApiResearchWatchlistRunDueResponse,
  ApiResearchWorkspace,
} from "@/lib/api/types";

export function createResearchReport(payload: {
  keyword: string;
  research_focus?: string;
  followup_report_title?: string;
  followup_report_summary?: string;
  supplemental_context?: string;
  supplemental_evidence?: string;
  supplemental_requirements?: string;
  output_language?: AppLanguage;
  include_wechat?: boolean;
  max_sources?: number;
  research_mode?: "fast" | "deep";
}): Promise<ApiResearchReport> {
  return request<ApiResearchReport>("/api/research/report", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createResearchJob(payload: {
  keyword: string;
  research_focus?: string;
  followup_report_title?: string;
  followup_report_summary?: string;
  supplemental_context?: string;
  supplemental_evidence?: string;
  supplemental_requirements?: string;
  output_language?: AppLanguage;
  include_wechat?: boolean;
  max_sources?: number;
  deep_research?: boolean;
  research_mode?: "fast" | "deep";
}): Promise<ApiResearchJob> {
  return request<ApiResearchJob>("/api/research/jobs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getResearchJob(jobId: string): Promise<ApiResearchJob> {
  return request<ApiResearchJob>(`/api/research/jobs/${jobId}`, {
    method: "GET",
  });
}

export function getResearchJobClarification(jobId: string): Promise<ApiResearchClarificationPacket> {
  return request<ApiResearchClarificationPacket>(`/api/research/jobs/${jobId}/clarification`, {
    method: "GET",
  });
}

export function submitResearchJobClarification(
  jobId: string,
  payload: ApiResearchClarificationSubmitPayload,
): Promise<ApiResearchClarificationSubmitResponse> {
  return request<ApiResearchClarificationSubmitResponse>(`/api/research/jobs/${jobId}/clarification`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function submitResearchExperienceFeedback(
  jobId: string,
  payload: {
    score: number;
    reason:
      | "helpful"
      | "missing_sources"
      | "question_unclear"
      | "too_technical"
      | "recovery_failed"
      | "result_quality"
      | "other";
    comment?: string;
  },
): Promise<ApiResearchExperienceFeedback> {
  return request<ApiResearchExperienceFeedback>(`/api/research/jobs/${jobId}/experience-feedback`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getResearchExperienceMetrics(): Promise<ApiResearchExperienceMetrics> {
  return request<ApiResearchExperienceMetrics>("/api/research/experience/metrics");
}

export function getResearchExperienceReadiness(): Promise<ApiResearchExperienceReadiness> {
  return request<ApiResearchExperienceReadiness>("/api/research/experience/readiness");
}

export function getResearchJobTimeline(jobId: string): Promise<ApiResearchJobTimelineEvent[]> {
  return request<ApiResearchJobTimelineEvent[]>(`/api/research/jobs/${jobId}/timeline`, {
    method: "GET",
  });
}

export function listResearchConversations(): Promise<ApiResearchConversation[]> {
  return request<ApiResearchConversation[]>("/api/research/conversations", {
    method: "GET",
  });
}

export function createResearchConversation(payload: {
  title?: string;
  topic_id?: string;
  job_id?: string;
}): Promise<ApiResearchConversation> {
  return request<ApiResearchConversation>("/api/research/conversations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getResearchConversation(conversationId: string): Promise<ApiResearchConversation> {
  return request<ApiResearchConversation>(`/api/research/conversations/${conversationId}`, {
    method: "GET",
  });
}

export function sendResearchConversationMessage(
  conversationId: string,
  payload: { content: string },
): Promise<ApiResearchConversation> {
  return request<ApiResearchConversation>(`/api/research/conversations/${conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getMobileDailyBrief(forceRefresh = false): Promise<ApiMobileDailyBrief> {
  const suffix = forceRefresh ? "?force_refresh=true" : "";
  return request<ApiMobileDailyBrief>(`/api/mobile/daily-brief${suffix}`);
}

export function getResearchDailyBrief(forceRefresh = false): Promise<ApiMobileDailyBrief> {
  const suffix = forceRefresh ? "?force_refresh=true" : "";
  return request<ApiMobileDailyBrief>(`/api/research/daily-brief${suffix}`).catch(() => ({
    snapshot_id: "",
    brief_date: "",
    headline: "",
    summary: "",
    top_items: [],
    watchlist_changes: [],
    generated_at: null,
    audio_status: "unavailable",
    audio_url: null,
    audio_script: null,
  }));
}

export function getResearchSourceSettings(): Promise<ApiResearchSourceSettings> {
  return request<ApiResearchSourceSettings>("/api/research/source-settings", {
    method: "GET",
  });
}

export function updateResearchSourceSettings(payload: {
  enable_jianyu_tender_feed: boolean;
  enable_yuntoutiao_feed: boolean;
  enable_ggzy_feed: boolean;
  enable_cecbid_feed: boolean;
  enable_ccgp_feed: boolean;
  enable_gov_policy_feed: boolean;
  enable_local_ggzy_feed: boolean;
  enable_curated_wechat_channels: boolean;
}): Promise<ApiResearchSourceSettings> {
  return request<ApiResearchSourceSettings>("/api/research/source-settings", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function getResearchWorkspace(): Promise<ApiResearchWorkspace> {
  return request<ApiResearchWorkspace>("/api/research/workspace", {
    method: "GET",
  }).catch(() => ({
    saved_views: [],
    tracking_topics: [],
    compare_snapshots: [],
    markdown_archives: [],
  }));
}

export function getLowQualityResearchReviewQueue(
  top = 12,
  includeResolved = false,
): Promise<ApiResearchLowQualityReviewQueue> {
  const params = new URLSearchParams();
  params.set("top", String(top));
  if (includeResolved) {
    params.set("include_resolved", "true");
  }
  return request<ApiResearchLowQualityReviewQueue>(`/api/research/review-queue/low-quality?${params.toString()}`, {
    method: "GET",
  }).catch(() => ({
    generated_at: new Date().toISOString(),
    total_reports: 0,
    flagged_reports: 0,
    invalid_payloads: 0,
    issue_summary: [],
    recommendations: [],
    items: [],
  }));
}

export function getResearchOfflineEvaluation(weakestLimit = 6): Promise<ApiResearchOfflineEvaluation> {
  const params = new URLSearchParams();
  params.set("weakest_limit", String(weakestLimit));
  return request<ApiResearchOfflineEvaluation>(`/api/research/evaluation/offline?${params.toString()}`, {
    method: "GET",
  }).catch(() => ({
    generated_at: new Date().toISOString(),
    total_reports: 0,
    evaluated_reports: 0,
    invalid_payloads: 0,
    metrics: [],
    weakest_reports: [],
    summary_lines: [],
  }));
}

export function getResearchGoldenEvaluation(): Promise<ApiResearchGoldenEvaluation> {
  return request<ApiResearchGoldenEvaluation>("/api/research/evaluation/golden", {
    method: "GET",
  }).catch(() => ({
    generated_at: new Date().toISOString(),
    total_cases: 0,
    passed_cases: 0,
    average_professional_score: 0,
    average_intelligence_value_score: 0,
    average_target_support_rate: 0,
    average_section_quota_pass_rate: 0,
    cases: [],
    summary_lines: [],
  }));
}

export function getResearchExperimentControlPlane(): Promise<ApiResearchExperimentControlPlane> {
  return request<ApiResearchExperimentControlPlane>("/api/research/evaluation/control-plane", {
    method: "GET",
  }).catch(() => ({
    generated_at: new Date().toISOString(),
    total_reports: 0,
    evaluated_reports: 0,
    invalid_payloads: 0,
    lanes: [],
    summary_lines: [],
  }));
}

export function getResearchExperimentOrchestration(): Promise<ApiResearchExperimentOrchestration> {
  return request<ApiResearchExperimentOrchestration>("/api/research/experiments/orchestration", {
    method: "GET",
  }).catch(() => ({
    generated_at: new Date().toISOString(),
    total_plans: 0,
    frozen_plan_count: 0,
    locked_plan_count: 0,
    allowed_plan_count: 0,
    blocked_plan_count: 0,
    hold_plan_count: 0,
    promoted_plan_count: 0,
    revoked_plan_count: 0,
    active_policy_count: 0,
    active_policy_conflict_count: 0,
    active_policies: [],
    plans: [],
    summary_lines: [],
  }));
}

export function getResearchExperimentActivePolicies(): Promise<ApiResearchExperimentActivePolicy[]> {
  return request<ApiResearchExperimentActivePolicy[]>("/api/research/experiments/active-policies", {
    method: "GET",
  }).catch(() => []);
}

export function getResearchExperimentRuntimeSnapshot(): Promise<ApiResearchExperimentRuntimeSnapshot> {
  return request<ApiResearchExperimentRuntimeSnapshot>("/api/research/experiments/runtime-snapshot", {
    method: "GET",
  }).catch(() => ({
    generated_at: new Date().toISOString(),
    project_version_label: "",
    status: "empty",
    policy_count: 0,
    conflict_count: 0,
    strategy_count: 0,
    runtime_config: {},
    strategies: [],
    warnings: [],
    summary_lines: [],
  }));
}

export function getResearchExperimentRuntimeConfig(
  consumer: ApiResearchExperimentEffectiveRuntimeConfig["consumer"] = "all",
): Promise<ApiResearchExperimentEffectiveRuntimeConfig> {
  const params = new URLSearchParams();
  params.set("consumer", consumer);
  return request<ApiResearchExperimentEffectiveRuntimeConfig>(`/api/research/experiments/runtime-config?${params.toString()}`, {
    method: "GET",
  }).catch(() => ({
    generated_at: new Date().toISOString(),
    project_version_label: "",
    consumer,
    status: "fallback",
    enabled_lane_count: 0,
    applied_lanes: [],
    fallback_lanes: [],
    effective_config: {},
    provenance: {},
    warnings: [],
    summary_lines: [],
  }));
}

export function createResearchExperimentPlan(payload: {
  name: string;
  lane_key: ApiResearchExperimentLane["key"];
  strategy_family: ApiResearchExperimentPlan["strategy_family"];
  candidate_label: string;
  notes?: string;
  strategy_payload?: Record<string, unknown>;
  gate_config?: Partial<ApiResearchExperimentGateConfig>;
}): Promise<ApiResearchExperimentPlan> {
  return request<ApiResearchExperimentPlan>("/api/research/experiments/plans", {
    method: "POST",
    body: JSON.stringify({
      ...payload,
      gate_config: {
        minimum_sample_size: payload.gate_config?.minimum_sample_size ?? 6,
        minimum_uplift_points: payload.gate_config?.minimum_uplift_points ?? 0,
      },
    }),
  });
}

export function freezeResearchExperimentCohort(planId: string): Promise<ApiResearchExperimentPlan> {
  return request<ApiResearchExperimentPlan>(`/api/research/experiments/plans/${encodeURIComponent(planId)}/freeze-cohort`, {
    method: "POST",
  });
}

export function lockResearchExperimentBaseline(planId: string): Promise<ApiResearchExperimentPlan> {
  return request<ApiResearchExperimentPlan>(`/api/research/experiments/plans/${encodeURIComponent(planId)}/lock-baseline`, {
    method: "POST",
  });
}

export function evaluateResearchExperimentGate(planId: string): Promise<ApiResearchExperimentPlan> {
  return request<ApiResearchExperimentPlan>(`/api/research/experiments/plans/${encodeURIComponent(planId)}/evaluate-gate`, {
    method: "POST",
  });
}

export function promoteResearchExperimentRollout(planId: string, note = ""): Promise<ApiResearchExperimentPlan> {
  return request<ApiResearchExperimentPlan>(`/api/research/experiments/plans/${encodeURIComponent(planId)}/promote-rollout`, {
    method: "POST",
    body: JSON.stringify({ note }),
  });
}

export function revokeResearchExperimentRollout(planId: string, note = ""): Promise<ApiResearchExperimentPlan> {
  return request<ApiResearchExperimentPlan>(`/api/research/experiments/plans/${encodeURIComponent(planId)}/revoke-rollout`, {
    method: "POST",
    body: JSON.stringify({ note }),
  });
}

export function getResearchFollowupDeltaEvaluation(weakestLimit = 6): Promise<ApiResearchFollowupDeltaEvaluation> {
  const params = new URLSearchParams();
  params.set("weakest_limit", String(weakestLimit));
  return request<ApiResearchFollowupDeltaEvaluation>(`/api/research/evaluation/followup-delta?${params.toString()}`, {
    method: "GET",
  }).catch(() => ({
    generated_at: new Date().toISOString(),
    total_reports: 0,
    followup_reports: 0,
    invalid_payloads: 0,
    metrics: [],
    weakest_reports: [],
    summary_lines: [],
  }));
}

export function getResearchDeliveryExportDiagnostics(trendLimit = 8): Promise<ApiResearchDeliveryExportDiagnostics> {
  const params = new URLSearchParams();
  params.set("trend_limit", String(trendLimit));
  return request<ApiResearchDeliveryExportDiagnostics>(`/api/research/delivery/export-diagnostics?${params.toString()}`, {
    method: "GET",
  }).catch(() => ({
    generated_at: new Date().toISOString(),
    total_archives: 0,
    analyzed_archives: 0,
    archives_with_quality_snapshot: 0,
    archives_with_followup_summary: 0,
    trend_points: [],
    version_deltas: [],
    summary_lines: [],
  }));
}

export function getResearchUpgradeDiagnosticsPreview(): Promise<ApiResearchUpgradeDiagnostics> {
  return request<ApiResearchUpgradeDiagnostics>("/api/research/upgrade-diagnostics/preview", {
    method: "GET",
  });
}

export function getResearchAssurancePreview(): Promise<ApiResearchAssuranceSnapshot> {
  return request<ApiResearchAssuranceSnapshot>("/api/research/assurance/preview", {
    method: "GET",
  });
}

export function getResearchIndustrySkills(query = "", limit = 8): Promise<ApiResearchIndustrySkillLibrary> {
  const params = new URLSearchParams();
  if (query.trim()) params.set("query", query.trim());
  params.set("limit", String(limit));
  return request<ApiResearchIndustrySkillLibrary>(`/api/research/industry-skills?${params.toString()}`, {
    method: "GET",
  });
}

export function searchResearchIndustryKnowledge(payload: {
  query: string;
  industries?: string[];
  documentTypes?: string[];
  limit?: number;
  strategy?: "baseline_hybrid" | "prefilter_weighted_hybrid" | "prefilter_weighted_rerank";
}): Promise<ApiResearchIndustryKnowledgeSearch> {
  const params = new URLSearchParams({ query: payload.query.trim(), limit: String(payload.limit || 6) });
  if (payload.industries?.length) params.set("industries", payload.industries.join(","));
  if (payload.documentTypes?.length) params.set("document_types", payload.documentTypes.join(","));
  if (payload.strategy) params.set("strategy", payload.strategy);
  return request<ApiResearchIndustryKnowledgeSearch>(`/api/research/industry-skills/retrieve?${params.toString()}`, {
    method: "GET",
  });
}

export function getResearchIndustryKnowledgeRetrievalBenchmark(): Promise<ApiResearchIndustryKnowledgeRetrievalBenchmark> {
  return request<ApiResearchIndustryKnowledgeRetrievalBenchmark>(
    "/api/research/industry-skills/retrieval-ranking-benchmark",
    { method: "GET" },
  );
}

export function runResearchIndustryKnowledgeRetrievalBenchmark(): Promise<ApiResearchIndustryKnowledgeRetrievalBenchmark> {
  return request<ApiResearchIndustryKnowledgeRetrievalBenchmark>(
    "/api/research/industry-skills/retrieval-ranking-benchmark/run",
    { method: "POST" },
  );
}

export function getResearchIndustryKnowledgeRetrievalAssurance(): Promise<ApiResearchIndustryKnowledgeRetrievalAssuranceSnapshot> {
  return request<ApiResearchIndustryKnowledgeRetrievalAssuranceSnapshot>(
    "/api/research/industry-skills/retrieval-ranking-assurance",
    { method: "GET" },
  );
}

export function exportResearchIndustryKnowledgeRetrievalApprovalTemplate(): Promise<ApiResearchIndustryKnowledgeRetrievalApprovalTemplate> {
  return request<ApiResearchIndustryKnowledgeRetrievalApprovalTemplate>(
    "/api/research/industry-skills/retrieval-ranking-assurance/approval-template",
    { method: "POST" },
  );
}

export function exportResearchIndustryKnowledgeRetrievalEvidenceTemplates(): Promise<ApiResearchIndustryKnowledgeRetrievalEvidenceTemplates> {
  return request<ApiResearchIndustryKnowledgeRetrievalEvidenceTemplates>(
    "/api/research/industry-skills/retrieval-ranking-assurance/evidence-templates",
    { method: "POST" },
  );
}

export function getResearchIndustryKnowledgeRetrievalEvidenceOperations(): Promise<ApiResearchIndustryKnowledgeRetrievalEvidenceOperationsSnapshot> {
  return request<ApiResearchIndustryKnowledgeRetrievalEvidenceOperationsSnapshot>(
    "/api/research/industry-skills/retrieval-evidence-operations",
    { method: "GET" },
  );
}

export function exportResearchIndustryKnowledgeRetrievalEvidenceOperationsTemplates(): Promise<ApiResearchIndustryKnowledgeRetrievalEvidenceOperationsTemplates> {
  return request<ApiResearchIndustryKnowledgeRetrievalEvidenceOperationsTemplates>(
    "/api/research/industry-skills/retrieval-evidence-operations/templates",
    { method: "POST" },
  );
}

export function buildResearchIndustryKnowledgeDeliveryReview(payload: {
  case_id: string;
  report: ApiResearchReport;
  scenario?: string;
  target_customer?: string;
  vertical_scene?: string;
  supplemental_context?: string;
  use_industry_skills?: boolean;
  industry_skill_ids?: string[];
}): Promise<ApiResearchIndustryKnowledgeDeliveryReview> {
  return request<ApiResearchIndustryKnowledgeDeliveryReview>(
    "/api/research/industry-skills/retrieval-ranking-benchmark/delivery-review",
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function buildResearchSectionRetrievalPacks(payload: {
  report: ApiResearchReport;
  limit_per_section?: number;
  limit_per_source?: number;
}): Promise<ApiResearchSectionRetrievalPack[]> {
  return request<ApiResearchSectionRetrievalPack[]>("/api/research/retrieval/section-packs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function buildResearchSolutionDeliveryPack(payload: {
  report: ApiResearchReport;
  scenario?: string;
  target_customer?: string;
  vertical_scene?: string;
  supplemental_context?: string;
  use_industry_skills?: boolean;
  industry_skill_ids?: string[];
  industry_knowledge_retrieval_strategy?: "baseline_hybrid" | "prefilter_weighted_hybrid" | "prefilter_weighted_rerank";
  detail_level?: "outline" | "review_draft" | "final";
}): Promise<ApiResearchSolutionDeliveryPack> {
  return request<ApiResearchSolutionDeliveryPack>("/api/research/solution-delivery-pack", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function refreshResearchSolutionIntelligence(payload: {
  report: ApiResearchReport;
  scenario?: string;
  target_customer?: string;
  vertical_scene?: string;
  supplemental_context?: string;
  use_industry_skills?: boolean;
  industry_skill_ids?: string[];
  industry_knowledge_retrieval_strategy?: "baseline_hybrid" | "prefilter_weighted_hybrid" | "prefilter_weighted_rerank";
  detail_level?: "outline" | "review_draft" | "final";
}): Promise<ApiResearchReport> {
  return request<ApiResearchReport>("/api/research/solution-intelligence/refresh", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function rebuildResearchRetrievalIndex(payload: {
  limit_per_source?: number;
  batch_size?: number;
  max_chunks?: number | null;
  resume?: boolean;
  reset?: boolean;
} = {}): Promise<ApiResearchRetrievalIndexRebuildResult> {
  return request<ApiResearchRetrievalIndexRebuildResult>("/api/research/retrieval-index/rebuild", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getResearchRetrievalIndexStatus(): Promise<ApiResearchRetrievalIndexStatus> {
  return request<ApiResearchRetrievalIndexStatus>("/api/research/retrieval-index/status", {
    method: "GET",
  });
}

export function searchResearchRetrievalIndex(
  query: string,
  options: {
    limit?: number;
    topic_id?: string | null;
    document_type?: string | null;
    source_tier?: string | null;
    region?: string | null;
    industry?: string | null;
    field_key?: string | null;
    perspective?: string | null;
  } = {},
): Promise<ApiResearchRetrievalIndexSearchResult> {
  const params = new URLSearchParams();
  params.set("query", query);
  if (options.limit) {
    params.set("limit", String(options.limit));
  }
  if (options.topic_id) {
    params.set("topic_id", options.topic_id);
  }
  for (const key of ["document_type", "source_tier", "region", "industry", "field_key", "perspective"] as const) {
    if (options[key]) {
      params.set(key, options[key]);
    }
  }
  return request<ApiResearchRetrievalIndexSearchResult>(`/api/research/retrieval-index/search?${params.toString()}`, {
    method: "GET",
  });
}

export function rewriteLowQualityResearchReviewItem(entryId: string): Promise<ApiResearchLowQualityReviewActionResponse> {
  return request<ApiResearchLowQualityReviewActionResponse>(`/api/research/review-queue/low-quality/${entryId}/rewrite`, {
    method: "POST",
  });
}

export function resolveLowQualityResearchReviewItem(
  entryId: string,
  action: "accept" | "revert",
): Promise<ApiResearchLowQualityReviewActionResponse> {
  return request<ApiResearchLowQualityReviewActionResponse>(`/api/research/review-queue/low-quality/${entryId}/resolve`, {
    method: "POST",
    body: JSON.stringify({ action }),
  });
}

export function createResearchCompareSnapshot(payload: {
  name: string;
  query?: string;
  region_filter?: string;
  industry_filter?: string;
  role_filter?: "all" | "甲方" | "中标方" | "竞品" | "伙伴";
  tracking_topic_id?: string | null;
  summary?: string;
  rows: Array<Record<string, unknown>>;
  metadata_payload?: Record<string, unknown>;
}): Promise<ApiResearchCompareSnapshot> {
  return request<ApiResearchCompareSnapshot>("/api/research/workspace/compare-snapshots", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getResearchCompareSnapshot(snapshotId: string): Promise<ApiResearchCompareSnapshotDetail> {
  return request<ApiResearchCompareSnapshotDetail>(`/api/research/workspace/compare-snapshots/${snapshotId}`, {
    method: "GET",
  });
}

export function deleteResearchCompareSnapshot(snapshotId: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/research/workspace/compare-snapshots/${snapshotId}`, {
    method: "DELETE",
  });
}

export function createResearchMarkdownArchive(payload: {
  archive_kind: "compare_markdown" | "topic_version_recap" | "archive_diff_recap";
  name: string;
  filename: string;
  query?: string;
  region_filter?: string;
  industry_filter?: string;
  tracking_topic_id?: string | null;
  compare_snapshot_id?: string | null;
  report_version_id?: string | null;
  summary?: string;
  content: string;
  metadata_payload?: Record<string, unknown>;
}): Promise<ApiResearchMarkdownArchive> {
  return request<ApiResearchMarkdownArchive>("/api/research/workspace/markdown-archives", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getResearchMarkdownArchive(archiveId: string): Promise<ApiResearchMarkdownArchiveDetail> {
  return request<ApiResearchMarkdownArchiveDetail>(`/api/research/workspace/markdown-archives/${archiveId}`, {
    method: "GET",
  });
}

export function deleteResearchMarkdownArchive(archiveId: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/research/workspace/markdown-archives/${archiveId}`, {
    method: "DELETE",
  });
}

export function listResearchWatchlists(): Promise<ApiResearchWatchlist[]> {
  return request<ApiResearchWatchlist[]>("/api/research/watchlists", {
    method: "GET",
  }).catch(() => []);
}

export function getResearchWatchlistAutomationStatus(): Promise<ApiResearchWatchlistAutomationStatus> {
  return request<ApiResearchWatchlistAutomationStatus>("/api/research/watchlists/automation-status", {
    method: "GET",
  }).catch(() => ({
    installed: false,
    loaded: false,
    label: "com.antifomo.watchlists",
    plist_path: "",
    state_path: "",
    log_path: "",
    interval_seconds: 0,
    last_checked_at: null,
    last_due_count: 0,
    last_refreshed_count: 0,
    last_failed_count: 0,
    last_run_status: "idle",
    last_summary: "",
    last_failure_hint: "",
    alert_level: "low",
    action_required: false,
    action_required_reason: "",
    state_stale: false,
    state_age_seconds: 0,
    recent_request_failure_count: 0,
    consecutive_request_failure_count: 0,
    failed_items: [],
    last_log_size_bytes: 0,
    recommended_run_due_command: "npm run research:watchlists:run-due",
    recommended_status_command: "npm run research:watchlists:automation:status",
    recommended_install_command: "npm run research:watchlists:automation:install",
    recommended_uninstall_command: "npm run research:watchlists:automation:uninstall",
  }));
}

export function getResearchWatchlistOpsSummary(): Promise<ApiResearchWatchlistOpsSummary> {
  return request<ApiResearchWatchlistOpsSummary>("/api/research/watchlists/ops-summary", {
    method: "GET",
  }).catch(() => ({
    checked_at: new Date().toISOString(),
    active_count: 0,
    paused_count: 0,
    scheduled_count: 0,
    manual_count: 0,
    due_count: 0,
    overdue_count: 0,
    stale_count: 0,
    failed_topic_count: 0,
    unlinked_count: 0,
    next_due_at: null,
    oldest_checked_at: null,
    last_checked_at: null,
    alert_level: "low",
    action_required: false,
    recommendations: [],
    issues: [],
  }));
}

export function createResearchWatchlist(payload: {
  name: string;
  watch_type?: "topic" | "company" | "policy" | "competitor";
  query: string;
  tracking_topic_id?: string;
  research_focus?: string;
  perspective?: "all" | "regional" | "client_followup" | "bidding" | "ecosystem";
  region_filter?: string;
  industry_filter?: string;
  alert_level?: "low" | "medium" | "high";
  schedule?: string;
}): Promise<ApiResearchWatchlist> {
  return request<ApiResearchWatchlist>("/api/research/watchlists", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateResearchWatchlist(
  watchlistId: string,
  payload: {
    name?: string;
    query?: string;
    research_focus?: string;
    perspective?: "all" | "regional" | "client_followup" | "bidding" | "ecosystem";
    region_filter?: string;
    industry_filter?: string;
    alert_level?: "low" | "medium" | "high";
    schedule?: string;
    status?: "active" | "paused";
  },
): Promise<ApiResearchWatchlist> {
  return request<ApiResearchWatchlist>(`/api/research/watchlists/${watchlistId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function getResearchWatchlistChanges(watchlistId: string): Promise<ApiResearchWatchlistChangeEvent[]> {
  return request<ApiResearchWatchlistChangeEvent[]>(`/api/research/watchlists/${watchlistId}/changes`, {
    method: "GET",
  });
}

export function refreshResearchWatchlist(
  watchlistId: string,
  payload?: {
    output_language?: AppLanguage;
    include_wechat?: boolean;
    max_sources?: number;
    save_to_knowledge?: boolean;
    collection_name?: string | null;
    is_focus_reference?: boolean;
  },
): Promise<ApiResearchWatchlistRefresh> {
  return request<ApiResearchWatchlistRefresh>(`/api/research/watchlists/${watchlistId}/refresh`, {
    method: "POST",
    body: JSON.stringify(payload || {}),
  });
}

export function runDueResearchWatchlists(
  payload?: {
    output_language?: AppLanguage;
    include_wechat?: boolean;
    max_sources?: number;
    save_to_knowledge?: boolean;
    collection_name?: string | null;
    is_focus_reference?: boolean;
    limit?: number;
    retry_failed?: boolean;
    max_retry_attempts?: number;
  },
): Promise<ApiResearchWatchlistRunDueResponse> {
  const limit = payload?.limit;
  const retryFailed = payload?.retry_failed;
  const maxRetryAttempts = payload?.max_retry_attempts;
  const bodyPayload = payload ? { ...payload } : {};
  if ("limit" in bodyPayload) {
    delete bodyPayload.limit;
  }
  if ("retry_failed" in bodyPayload) {
    delete bodyPayload.retry_failed;
  }
  if ("max_retry_attempts" in bodyPayload) {
    delete bodyPayload.max_retry_attempts;
  }
  const params = new URLSearchParams();
  if (typeof limit === "number") {
    params.set("limit", String(limit));
  }
  if (typeof retryFailed === "boolean") {
    params.set("retry_failed", retryFailed ? "true" : "false");
  }
  if (typeof maxRetryAttempts === "number") {
    params.set("max_retry_attempts", String(maxRetryAttempts));
  }
  const query = params.toString();
  return request<ApiResearchWatchlistRunDueResponse>(`/api/research/watchlists/run-due${query ? `?${query}` : ""}`, {
    method: "POST",
    body: JSON.stringify(bodyPayload),
  });
}

export function getResearchWatchlistRunHistory(options: {
  limit?: number;
  status?: "refreshed" | "failed" | null;
  watchlist_id?: string | null;
} = {}): Promise<ApiResearchWatchlistRun[]> {
  const params = new URLSearchParams();
  if (options.limit) {
    params.set("limit", String(options.limit));
  }
  if (options.status) {
    params.set("status", options.status);
  }
  if (options.watchlist_id) {
    params.set("watchlist_id", options.watchlist_id);
  }
  const query = params.toString();
  return request<ApiResearchWatchlistRun[]>(`/api/research/watchlists/run-history${query ? `?${query}` : ""}`, {
    method: "GET",
  }).catch(() => []);
}

export function getResearchWatchlistDigestExport(options: {
  since_hours?: number;
  limit?: number;
} = {}): Promise<ApiResearchWatchlistDigestExport> {
  const params = new URLSearchParams();
  if (options.since_hours) {
    params.set("since_hours", String(options.since_hours));
  }
  if (options.limit) {
    params.set("limit", String(options.limit));
  }
  const query = params.toString();
  return request<ApiResearchWatchlistDigestExport>(`/api/research/watchlists/digest-export${query ? `?${query}` : ""}`, {
    method: "GET",
  });
}

export function getResearchEntityDetail(entityId: string): Promise<ApiResearchEntityDetail> {
  return request<ApiResearchEntityDetail>(`/api/research/entities/${entityId}`, {
    method: "GET",
  });
}

export function resolveResearchEntityAlias(payload: {
  entity_id: string;
  alias_name: string;
  confidence?: number;
}): Promise<ApiResearchEntityDetail> {
  return request<ApiResearchEntityDetail>("/api/research/entities/resolve-alias", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function saveResearchView(payload: {
  id?: string;
  name: string;
  query?: string;
  filter_mode?: "all" | "reports" | "actions";
  perspective?: "all" | "regional" | "client_followup" | "bidding" | "ecosystem";
  region_filter?: string;
  industry_filter?: string;
  action_type_filter?: string;
  focus_only?: boolean;
}): Promise<ApiResearchSavedView> {
  return request<ApiResearchSavedView>("/api/research/workspace/views", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteResearchView(viewId: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/research/workspace/views/${viewId}`, {
    method: "DELETE",
  });
}

export function saveResearchTrackingTopic(payload: {
  id?: string;
  name: string;
  keyword: string;
  research_focus?: string;
  perspective?: "all" | "regional" | "client_followup" | "bidding" | "ecosystem";
  region_filter?: string;
  industry_filter?: string;
  notes?: string;
}): Promise<ApiResearchTrackingTopic> {
  return request<ApiResearchTrackingTopic>("/api/research/workspace/topics", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteResearchTrackingTopic(topicId: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/research/workspace/topics/${topicId}`, {
    method: "DELETE",
  });
}

export function refreshResearchTrackingTopic(
  topicId: string,
  payload?: {
    output_language?: AppLanguage;
    include_wechat?: boolean;
    max_sources?: number;
    save_to_knowledge?: boolean;
    collection_name?: string | null;
    is_focus_reference?: boolean;
  },
): Promise<ApiResearchTrackingTopicRefresh> {
  return request<ApiResearchTrackingTopicRefresh>(`/api/research/workspace/topics/${topicId}/refresh`, {
    method: "POST",
    body: JSON.stringify(payload || {}),
  });
}

export function getResearchTrackingTopicVersions(
  topicId: string,
): Promise<ApiResearchTrackingTopicVersionDetail[]> {
  return request<ApiResearchTrackingTopicVersionDetail[]>(`/api/research/workspace/topics/${topicId}/versions`, {
    method: "GET",
  });
}

export function getResearchTrackingTopicTimeline(
  topicId: string,
): Promise<ApiResearchTrackingTopicTimelineEvent[]> {
  return request<ApiResearchTrackingTopicTimelineEvent[]>(`/api/research/workspace/topics/${topicId}/timeline`, {
    method: "GET",
  });
}

export function getResearchTrackingTopicVersion(
  topicId: string,
  versionId: string,
): Promise<ApiResearchTrackingTopicVersionDetail> {
  return request<ApiResearchTrackingTopicVersionDetail>(
    `/api/research/workspace/topics/${topicId}/versions/${versionId}`,
    {
      method: "GET",
    },
  );
}

export function saveResearchReport(payload: {
  report: ApiResearchReport;
  collection_name?: string | null;
  is_focus_reference?: boolean;
}): Promise<ApiResearchSaveResponse> {
  return request<ApiResearchSaveResponse>("/api/research/report/save", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createResearchActionPlan(payload: {
  report: ApiResearchReport;
}): Promise<ApiResearchActionPlan> {
  return request<ApiResearchActionPlan>("/api/research/action-plan", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function saveResearchActionCards(payload: {
  keyword: string;
  cards: ApiResearchActionCard[];
  collection_name?: string | null;
  is_focus_reference?: boolean;
}): Promise<ApiResearchActionSaveResponse> {
  return request<ApiResearchActionSaveResponse>("/api/research/action-plan/save", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
