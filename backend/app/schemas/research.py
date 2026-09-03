from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.items import OutputLanguage
from app.schemas.research_runtime import ResearchRunMetricsOut

ResearchMode = Literal["fast", "deep"]


class ResearchSupplementalDocumentIn(BaseModel):
    file_name: str = Field(min_length=1, max_length=240)
    mime_type: str = Field(default="text/plain", max_length=120)
    extracted_text: str = Field(default="", max_length=24000)
    file_base64: str | None = Field(default=None, max_length=16000000)
    source_url: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def require_document_content(self) -> "ResearchSupplementalDocumentIn":
        if not self.extracted_text.strip() and not (self.file_base64 or "").strip():
            raise ValueError("extracted_text or file_base64 is required")
        return self


class ResearchConnectorStatusOut(BaseModel):
    key: str
    label: str
    status: Literal["active", "available", "authorization_required"] = "available"
    detail: str = ""
    requires_authorization: bool = False


class ResearchReportRequest(BaseModel):
    keyword: str = Field(min_length=2, max_length=120)
    research_focus: str | None = Field(default=None, max_length=280)
    followup_report_title: str | None = Field(default=None, max_length=180)
    followup_report_summary: str | None = Field(default=None, max_length=1600)
    supplemental_context: str | None = Field(default=None, max_length=2400)
    supplemental_evidence: str | None = Field(default=None, max_length=3200)
    supplemental_requirements: str | None = Field(default=None, max_length=2000)
    output_language: OutputLanguage = "zh-CN"
    include_wechat: bool = True
    research_mode: ResearchMode = "deep"
    max_sources: int = Field(default=14, ge=6, le=24)
    runtime_strategy_config: dict[str, Any] = Field(default_factory=dict)
    supplemental_documents: list[ResearchSupplementalDocumentIn] = Field(default_factory=list, max_length=4)


class ResearchSourceSettingsOut(BaseModel):
    enable_jianyu_tender_feed: bool = True
    enable_yuntoutiao_feed: bool = True
    enable_ggzy_feed: bool = True
    enable_cecbid_feed: bool = True
    enable_ccgp_feed: bool = True
    enable_gov_policy_feed: bool = True
    enable_local_ggzy_feed: bool = True
    enable_curated_wechat_channels: bool = True
    enabled_source_labels: list[str] = Field(default_factory=list)
    connector_statuses: list["ResearchConnectorStatusOut"] = Field(default_factory=list)
    updated_at: datetime | None = None


class ResearchSourceSettingsUpdate(BaseModel):
    enable_jianyu_tender_feed: bool
    enable_yuntoutiao_feed: bool
    enable_ggzy_feed: bool
    enable_cecbid_feed: bool
    enable_ccgp_feed: bool
    enable_gov_policy_feed: bool
    enable_local_ggzy_feed: bool
    enable_curated_wechat_channels: bool


ResearchUpgradeRoundStatus = Literal["ready", "watch", "blocked"]
ResearchUpgradeExpertRole = Literal["buyer_value", "competitor_threat", "partner_influence", "tender_cadence"]


class ResearchUpgradeSourceInput(BaseModel):
    title: str = Field(default="", max_length=240)
    url: str = Field(default="", max_length=800)
    snippet: str = Field(default="", max_length=1600)
    source_type: str = Field(default="", max_length=80)
    source_tier: str = Field(default="", max_length=40)
    published_year: int | None = Field(default=None, ge=1990, le=2100)
    section: str = Field(default="", max_length=120)


class ResearchUpgradeSectionInput(BaseModel):
    title: str = Field(default="", max_length=160)
    summary: str = Field(default="", max_length=1200)
    evidence_urls: list[str] = Field(default_factory=list)


class ResearchUpgradeDiagnosticsRequest(BaseModel):
    keyword: str = Field(default="上海医疗行业 AI 需求调研和潜在商机", min_length=2, max_length=160)
    research_focus: str = Field(default="预算、采购、政策、甲方、竞品、伙伴和下一步拜访动作", max_length=360)
    recency_window_years: int = Field(default=7, ge=1, le=15)
    sources: list[ResearchUpgradeSourceInput] = Field(default_factory=list)
    sections: list[ResearchUpgradeSectionInput] = Field(default_factory=list)
    previous_snapshot: dict[str, str] = Field(default_factory=dict)
    current_snapshot: dict[str, str] = Field(default_factory=dict)


class ResearchUpgradeRoadmapRoundOut(BaseModel):
    index: int
    key: str
    title: str
    status: ResearchUpgradeRoundStatus = "ready"
    summary: str = ""


class ResearchUpgradeUrlFirstDiagnosticsOut(BaseModel):
    valid_url_count: int = 0
    invalid_url_count: int = 0
    wechat_url_count: int = 0
    strict_wechat_path_count: int = 0
    url_first_ratio: float = 0.0
    browser_url_check_ready: bool = True
    clipboard_url_check_ready: bool = True
    ocr_fallback_required: bool = False
    warnings: list[str] = Field(default_factory=list)


class ResearchUpgradeQueryFragmentOut(BaseModel):
    key: str
    intent: str
    query: str
    must_terms: list[str] = Field(default_factory=list)
    exclude_terms: list[str] = Field(default_factory=list)


class ResearchUpgradeRetrievalHitEvaluationOut(BaseModel):
    title: str
    url: str = ""
    source_tier: str = ""
    source_type: str = ""
    relevance_score: int = 0
    accepted: bool = False
    reason: str = ""
    matched_terms: list[str] = Field(default_factory=list)


class ResearchUpgradeRetrievalEvaluationOut(BaseModel):
    source_count: int = 0
    accepted_count: int = 0
    ambiguous_count: int = 0
    rejected_count: int = 0
    filtered_old_source_count: int = 0
    official_source_ratio: float = 0.0
    average_relevance_score: int = 0
    topic_relevance_passed: bool = False
    recency_cutoff_year: int = 0
    hits: list[ResearchUpgradeRetrievalHitEvaluationOut] = Field(default_factory=list)


class ResearchUpgradeGraphNodeOut(BaseModel):
    name: str
    role: Literal["buyer", "competitor", "partner", "budget", "case", "generic"] = "generic"
    evidence_count: int = 0
    source_tiers: dict[str, int] = Field(default_factory=dict)


class ResearchUpgradeGraphEdgeOut(BaseModel):
    source: str
    target: str
    relation: str
    evidence_count: int = 0


class ResearchUpgradeLightweightGraphOut(BaseModel):
    nodes: list[ResearchUpgradeGraphNodeOut] = Field(default_factory=list)
    edges: list[ResearchUpgradeGraphEdgeOut] = Field(default_factory=list)


class ResearchUpgradeExpertPanelOut(BaseModel):
    role: ResearchUpgradeExpertRole
    label: str
    score: int = 0
    findings: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class ResearchUpgradeSectionQuotaOut(BaseModel):
    section_title: str
    required_evidence_count: int = 0
    actual_evidence_count: int = 0
    passed: bool = False
    gap: int = 0
    note: str = ""


class ResearchUpgradeFieldDiffOut(BaseModel):
    field: str
    before: str = ""
    after: str = ""
    status: Literal["added", "removed", "changed", "unchanged"] = "unchanged"
    summary: str = ""


class ResearchUpgradeFallbackActionOut(BaseModel):
    priority: Literal["high", "medium", "low"] = "medium"
    action: str
    reason: str = ""
    owner: str = ""


class ResearchUpgradeSourceContributionOut(BaseModel):
    source_type: str
    count: int = 0
    accepted_count: int = 0
    contribution_percent: int = 0
    average_relevance_score: int = 0


class ResearchUpgradeDiagnosticsOut(BaseModel):
    generated_at: datetime
    roadmap_version: str = "tencent-url-and-research-upgrade-plan-2026-06"
    status: Literal["ready", "watch", "blocked"] = "watch"
    readiness_score: int = 0
    keyword: str = ""
    research_focus: str = ""
    roadmap_rounds: list[ResearchUpgradeRoadmapRoundOut] = Field(default_factory=list)
    url_first_diagnostics: ResearchUpgradeUrlFirstDiagnosticsOut = Field(default_factory=ResearchUpgradeUrlFirstDiagnosticsOut)
    query_plan: list[ResearchUpgradeQueryFragmentOut] = Field(default_factory=list)
    retrieval_evaluation: ResearchUpgradeRetrievalEvaluationOut = Field(default_factory=ResearchUpgradeRetrievalEvaluationOut)
    lightweight_graph: ResearchUpgradeLightweightGraphOut = Field(default_factory=ResearchUpgradeLightweightGraphOut)
    expert_panels: list[ResearchUpgradeExpertPanelOut] = Field(default_factory=list)
    section_evidence_quotas: list[ResearchUpgradeSectionQuotaOut] = Field(default_factory=list)
    field_diffs: list[ResearchUpgradeFieldDiffOut] = Field(default_factory=list)
    fallback_actions: list[ResearchUpgradeFallbackActionOut] = Field(default_factory=list)
    source_type_contributions: list[ResearchUpgradeSourceContributionOut] = Field(default_factory=list)
    summary_lines: list[str] = Field(default_factory=list)


ResearchFilterMode = Literal["all", "reports", "actions"]
ResearchPerspectiveMode = Literal["all", "regional", "client_followup", "bidding", "ecosystem"]
ResearchWatchType = Literal["topic", "company", "policy", "competitor"]
ResearchCompareRole = Literal["甲方", "中标方", "竞品", "伙伴"]
ResearchCompareSnapshotDiffStatus = Literal["unavailable", "aligned", "expanded", "trimmed", "mixed"]
ResearchTopicTimelineEventType = Literal["report_version", "compare_snapshot", "markdown_archive"]
ResearchMarkdownArchiveKind = Literal["compare_markdown", "topic_version_recap", "archive_diff_recap"]
ResearchExperimentLaneKey = Literal["query_recovery", "routing_followup", "reranker_official_recall"]
ResearchExperimentStrategyFamily = Literal["query_plan", "routing_policy", "reranker"]
ResearchExperimentPlanStatus = Literal[
    "draft",
    "cohort_frozen",
    "baseline_locked",
    "gate_allowed",
    "gate_hold",
    "gate_blocked",
    "rollout_promoted",
    "rollout_revoked",
]
ResearchExperimentGateDecision = Literal["allow", "hold", "block"]
ResearchExperimentRolloutDecision = Literal["promoted", "revoked"]
ResearchExperimentRuntimeConsumer = Literal[
    "all",
    "query_generation",
    "section_routing",
    "retrieval_search",
    "source_reranker",
]


class ResearchSavedViewBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    query: str = Field(default="", max_length=120)
    filter_mode: ResearchFilterMode = "all"
    perspective: ResearchPerspectiveMode = "all"
    region_filter: str = Field(default="", max_length=40)
    industry_filter: str = Field(default="", max_length=40)
    action_type_filter: str = Field(default="", max_length=40)
    focus_only: bool = False


class ResearchSavedViewCreateRequest(ResearchSavedViewBase):
    id: str | None = Field(default=None, max_length=64)


class ResearchSavedViewOut(ResearchSavedViewBase):
    id: str
    created_at: datetime
    updated_at: datetime


class ResearchTrackingTopicBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    keyword: str = Field(min_length=1, max_length=120)
    research_focus: str = Field(default="", max_length=280)
    perspective: ResearchPerspectiveMode = "all"
    region_filter: str = Field(default="", max_length=40)
    industry_filter: str = Field(default="", max_length=40)
    notes: str = Field(default="", max_length=800)


class ResearchTrackingTopicCreateRequest(ResearchTrackingTopicBase):
    id: str | None = Field(default=None, max_length=64)


class ResearchTrackingTopicOut(ResearchTrackingTopicBase):
    id: str
    created_at: datetime
    updated_at: datetime
    last_refreshed_at: datetime | None = None
    last_refresh_status: Literal["idle", "running", "succeeded", "failed"] = "idle"
    last_refresh_error: str | None = None
    last_refresh_note: str | None = None
    last_refresh_new_targets: list[str] = Field(default_factory=list)
    last_refresh_new_competitors: list[str] = Field(default_factory=list)
    last_refresh_new_budget_signals: list[str] = Field(default_factory=list)
    last_report_entry_id: str | None = None
    last_report_title: str | None = None
    report_history: list["ResearchTrackingTopicReportVersionOut"] = Field(default_factory=list)


class ResearchWatchlistBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    watch_type: ResearchWatchType = "topic"
    query: str = Field(min_length=1, max_length=120)
    tracking_topic_id: str | None = Field(default=None, max_length=64)
    research_focus: str = Field(default="", max_length=280)
    perspective: ResearchPerspectiveMode = "all"
    region_filter: str = Field(default="", max_length=40)
    industry_filter: str = Field(default="", max_length=40)
    alert_level: Literal["low", "medium", "high"] = "medium"
    schedule: str = Field(default="manual", max_length=30)


class ResearchWatchlistCreateRequest(ResearchWatchlistBase):
    pass


class ResearchWatchlistUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    query: str | None = Field(default=None, min_length=1, max_length=120)
    research_focus: str | None = Field(default=None, max_length=280)
    perspective: ResearchPerspectiveMode | None = None
    region_filter: str | None = Field(default=None, max_length=40)
    industry_filter: str | None = Field(default=None, max_length=40)
    alert_level: Literal["low", "medium", "high"] | None = None
    schedule: str | None = Field(default=None, max_length=30)
    status: Literal["active", "paused"] | None = None


class ResearchWatchlistChangeEventOut(BaseModel):
    id: str
    watchlist_id: str
    change_type: Literal["added", "removed", "rewritten", "risk"] = "rewritten"
    summary: str
    payload: dict = Field(default_factory=dict)
    severity: Literal["low", "medium", "high"] = "medium"
    created_at: datetime


class ResearchWatchlistOut(ResearchWatchlistBase):
    id: str
    status: Literal["active", "paused"] = "active"
    last_checked_at: datetime | None = None
    next_due_at: datetime | None = None
    is_due: bool = False
    created_at: datetime
    updated_at: datetime
    latest_changes: list[ResearchWatchlistChangeEventOut] = Field(default_factory=list)


class ResearchWorkspaceOut(BaseModel):
    saved_views: list[ResearchSavedViewOut] = Field(default_factory=list)
    tracking_topics: list[ResearchTrackingTopicOut] = Field(default_factory=list)
    compare_snapshots: list["ResearchCompareSnapshotOut"] = Field(default_factory=list)
    markdown_archives: list["ResearchMarkdownArchiveOut"] = Field(default_factory=list)


class ResearchLowQualityIssueSummaryOut(BaseModel):
    code: str
    count: int = 0


class ResearchLowQualityIssueOut(BaseModel):
    code: str
    severity: Literal["low", "medium", "high"] = "medium"
    weight: int = 0
    summary: str
    evidence: str = ""


class ResearchLowQualitySuspiciousRowOut(BaseModel):
    field: str
    value: str
    reason: str


class ResearchLowQualitySourcePreviewOut(BaseModel):
    title: str = ""
    domain: str = ""
    source_tier: str = ""


class ResearchLowQualityRewriteDiffOut(BaseModel):
    rewrite_mode: Literal["rewrite", "guarded"] = "rewrite"
    before_title: str = ""
    after_title: str = ""
    before_summary: str = ""
    after_summary: str = ""
    before_next_action: str = ""
    after_next_action: str = ""
    before_top_targets: list[str] = Field(default_factory=list)
    after_top_targets: list[str] = Field(default_factory=list)
    after_pending_targets: list[str] = Field(default_factory=list)
    before_risk_score: int = 0
    after_risk_score: int = 0
    rewritten_at: datetime | None = None


class ResearchLowQualityReviewQueueItemOut(BaseModel):
    entry_id: str
    updated_at: datetime | None = None
    entry_title: str = ""
    report_title: str = ""
    keyword: str = ""
    research_focus: str = ""
    risk_score: int = 0
    issue_count: int = 0
    readiness_status: str = ""
    guarded_backlog: bool = False
    source_count: int = 0
    official_source_ratio: float = 0.0
    retrieval_quality: str = ""
    evidence_mode: str = ""
    issue_codes: list[str] = Field(default_factory=list)
    issues: list[ResearchLowQualityIssueOut] = Field(default_factory=list)
    suggested_focus: list[str] = Field(default_factory=list)
    executive_summary: str = ""
    next_action: str = ""
    suspicious_rows: list[ResearchLowQualitySuspiciousRowOut] = Field(default_factory=list)
    important_section_failures: list[str] = Field(default_factory=list)
    source_preview: list[ResearchLowQualitySourcePreviewOut] = Field(default_factory=list)
    review_status: Literal["pending", "rewritten", "accepted", "reverted"] = "pending"
    review_updated_at: datetime | None = None
    has_rewrite_snapshot: bool = False
    latest_rewrite: ResearchLowQualityRewriteDiffOut | None = None


class ResearchLowQualityReviewQueueOut(BaseModel):
    generated_at: datetime
    total_reports: int = 0
    flagged_reports: int = 0
    invalid_payloads: int = 0
    issue_summary: list[ResearchLowQualityIssueSummaryOut] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    items: list[ResearchLowQualityReviewQueueItemOut] = Field(default_factory=list)


class ResearchLowQualityReviewResolveRequest(BaseModel):
    action: Literal["accept", "revert"]


class ResearchLowQualityReviewActionResponse(BaseModel):
    entry_id: str
    review_status: Literal["rewritten", "accepted", "reverted"]
    item: ResearchLowQualityReviewQueueItemOut | None = None
    diff: ResearchLowQualityRewriteDiffOut | None = None


class ResearchOfflineEvaluationMetricOut(BaseModel):
    key: Literal[
        "retrieval_hit_rate",
        "target_support_rate",
        "section_quota_pass_rate",
        "official_source_recall_at_5",
        "unsupported_target_rate",
        "reranker_official_recall_at_5",
        "solution_delivery_quality_pass_rate",
        "project_proposal_quality_pass_rate",
        "delivery_self_review_gain_rate",
    ]
    label: str
    numerator: int = 0
    denominator: int = 0
    rate: float = 0.0
    percent: int = 0
    benchmark: float = 0.0
    status: Literal["good", "watch", "bad"] = "watch"
    summary: str = ""


class ResearchOfflineEvaluationWeakReportOut(BaseModel):
    entry_id: str
    entry_title: str = ""
    report_title: str = ""
    keyword: str = ""
    weakness_score: int = 0
    retrieval_hit: bool = False
    supported_target_accounts: int = 0
    unsupported_target_accounts: int = 0
    unsupported_targets: list[str] = Field(default_factory=list)
    quota_passed_section_count: int = 0
    quota_total_section_count: int = 0
    failing_sections: list[str] = Field(default_factory=list)
    official_source_ratio: float = 0.0
    strict_match_ratio: float = 0.0
    retrieval_quality: Literal["low", "medium", "high"] = "low"
    solution_delivery_quality_score: int = 0
    project_proposal_quality_score: int = 0
    delivery_quality_status: Literal["pass", "watch", "fail"] = "watch"
    delivery_missing_axes: list[str] = Field(default_factory=list)


class ResearchOfflineEvaluationOut(BaseModel):
    generated_at: datetime
    total_reports: int = 0
    evaluated_reports: int = 0
    invalid_payloads: int = 0
    metrics: list[ResearchOfflineEvaluationMetricOut] = Field(default_factory=list)
    weakest_reports: list[ResearchOfflineEvaluationWeakReportOut] = Field(default_factory=list)
    summary_lines: list[str] = Field(default_factory=list)


class ResearchExperimentArmOut(BaseModel):
    key: str
    label: str
    role: Literal["baseline", "candidate"]
    numerator: int = 0
    denominator: int = 0
    rate: float = 0.0
    percent: int = 0
    summary: str = ""


class ResearchExperimentLaneOut(BaseModel):
    key: ResearchExperimentLaneKey
    label: str
    metric_label: str
    baseline: ResearchExperimentArmOut
    candidate: ResearchExperimentArmOut
    uplift_points: int = 0
    status: Literal["ready", "watch", "insufficient"] = "watch"
    interpretation: str = ""


class ResearchExperimentControlPlaneOut(BaseModel):
    generated_at: datetime
    total_reports: int = 0
    evaluated_reports: int = 0
    invalid_payloads: int = 0
    lanes: list[ResearchExperimentLaneOut] = Field(default_factory=list)
    summary_lines: list[str] = Field(default_factory=list)


class ResearchExperimentGateConfigOut(BaseModel):
    minimum_sample_size: int = Field(default=6, ge=1, le=500)
    minimum_uplift_points: int = Field(default=0, ge=-100, le=100)


class ResearchExperimentPlanCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    lane_key: ResearchExperimentLaneKey
    strategy_family: ResearchExperimentStrategyFamily
    candidate_label: str = Field(min_length=1, max_length=180)
    notes: str = Field(default="", max_length=1200)
    strategy_payload: dict[str, Any] = Field(default_factory=dict)
    gate_config: ResearchExperimentGateConfigOut = Field(default_factory=ResearchExperimentGateConfigOut)


class ResearchExperimentRolloutGateOut(BaseModel):
    decision: ResearchExperimentGateDecision
    lane_key: ResearchExperimentLaneKey
    baseline_version_label: str = ""
    locked_baseline_percent: int = 0
    candidate_percent: int = 0
    observed_uplift_points: int = 0
    required_uplift_points: int = 0
    sample_size: int = 0
    minimum_sample_size: int = 0
    reasons: list[str] = Field(default_factory=list)
    evaluated_at: datetime
    current_lane: ResearchExperimentLaneOut | None = None


class ResearchExperimentRolloutActionRequest(BaseModel):
    note: str = Field(default="", max_length=1200)


class ResearchExperimentRolloutManifestOut(BaseModel):
    decision: ResearchExperimentRolloutDecision
    plan_id: str
    plan_name: str = ""
    lane_key: ResearchExperimentLaneKey
    strategy_family: ResearchExperimentStrategyFamily
    candidate_label: str = ""
    baseline_version_label: str = ""
    promoted_version_label: str = ""
    gate_evaluated_at: datetime | None = None
    locked_baseline_percent: int = 0
    candidate_percent: int = 0
    observed_uplift_points: int = 0
    sample_size: int = 0
    note: str = ""
    activation_payload: dict[str, Any] = Field(default_factory=dict)
    promoted_at: datetime | None = None
    revoked_at: datetime | None = None


class ResearchExperimentActivePolicyOut(BaseModel):
    lane_key: ResearchExperimentLaneKey
    plan_id: str
    plan_name: str = ""
    strategy_family: ResearchExperimentStrategyFamily
    candidate_label: str = ""
    promoted_version_label: str = ""
    baseline_version_label: str = ""
    candidate_percent: int = 0
    observed_uplift_points: int = 0
    sample_size: int = 0
    promoted_at: datetime | None = None
    gate_evaluated_at: datetime | None = None
    activation_payload: dict[str, Any] = Field(default_factory=dict)
    conflict_plan_ids: list[str] = Field(default_factory=list)


class ResearchExperimentRuntimeStrategyOut(BaseModel):
    lane_key: ResearchExperimentLaneKey
    plan_id: str
    plan_name: str = ""
    strategy_family: ResearchExperimentStrategyFamily
    candidate_label: str = ""
    enabled: bool = True
    promoted_version_label: str = ""
    baseline_version_label: str = ""
    promoted_at: datetime | None = None
    gate_evaluated_at: datetime | None = None
    runtime_config: dict[str, Any] = Field(default_factory=dict)
    gate: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ResearchExperimentRuntimeSnapshotOut(BaseModel):
    generated_at: datetime
    project_version_label: str = ""
    status: Literal["ready", "degraded", "empty"] = "empty"
    policy_count: int = 0
    conflict_count: int = 0
    strategy_count: int = 0
    runtime_config: dict[str, Any] = Field(default_factory=dict)
    strategies: list[ResearchExperimentRuntimeStrategyOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary_lines: list[str] = Field(default_factory=list)


class ResearchExperimentEffectiveRuntimeConfigOut(BaseModel):
    generated_at: datetime
    project_version_label: str = ""
    consumer: ResearchExperimentRuntimeConsumer = "all"
    status: Literal["ready", "degraded", "fallback"] = "fallback"
    enabled_lane_count: int = 0
    applied_lanes: list[ResearchExperimentLaneKey] = Field(default_factory=list)
    fallback_lanes: list[ResearchExperimentLaneKey] = Field(default_factory=list)
    effective_config: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    summary_lines: list[str] = Field(default_factory=list)


class ResearchExperimentPlanOut(BaseModel):
    id: str
    name: str
    lane_key: ResearchExperimentLaneKey
    strategy_family: ResearchExperimentStrategyFamily
    candidate_label: str
    notes: str = ""
    strategy_payload: dict[str, Any] = Field(default_factory=dict)
    gate_config: ResearchExperimentGateConfigOut = Field(default_factory=ResearchExperimentGateConfigOut)
    status: ResearchExperimentPlanStatus = "draft"
    cohort_size: int = 0
    cohort_entry_ids: list[str] = Field(default_factory=list)
    cohort_preview_titles: list[str] = Field(default_factory=list)
    cohort_frozen_at: datetime | None = None
    baseline_version_label: str = ""
    baseline_lane: ResearchExperimentLaneOut | None = None
    baseline_locked_at: datetime | None = None
    latest_gate: ResearchExperimentRolloutGateOut | None = None
    gate_history: list[ResearchExperimentRolloutGateOut] = Field(default_factory=list)
    gate_history_count: int = 0
    rollout_manifest: ResearchExperimentRolloutManifestOut | None = None
    last_gate_evaluated_at: datetime | None = None
    promoted_at: datetime | None = None
    rollout_revoked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ResearchExperimentOrchestrationOut(BaseModel):
    generated_at: datetime
    total_plans: int = 0
    frozen_plan_count: int = 0
    locked_plan_count: int = 0
    allowed_plan_count: int = 0
    blocked_plan_count: int = 0
    hold_plan_count: int = 0
    promoted_plan_count: int = 0
    revoked_plan_count: int = 0
    active_policy_count: int = 0
    active_policy_conflict_count: int = 0
    active_policies: list[ResearchExperimentActivePolicyOut] = Field(default_factory=list)
    plans: list[ResearchExperimentPlanOut] = Field(default_factory=list)
    summary_lines: list[str] = Field(default_factory=list)


class ResearchFollowupDeltaMetricOut(BaseModel):
    key: Literal[
        "followup_title_resolution_rate",
        "followup_summary_resolution_rate",
        "followup_impacted_section_routing_rate",
        "followup_delta_official_support_rate",
    ]
    label: str
    numerator: int = 0
    denominator: int = 0
    rate: float = 0.0
    percent: int = 0
    benchmark: float = 0.0
    status: Literal["good", "watch", "bad"] = "watch"
    summary: str = ""


class ResearchFollowupDeltaWeakReportOut(BaseModel):
    entry_id: str
    entry_title: str = ""
    report_title: str = ""
    keyword: str = ""
    impacted_section_count: int = 0
    official_supported_section_count: int = 0
    title_resolution: Literal["baseline", "reused", "corrected"] = "baseline"
    summary_resolution: Literal["baseline", "reused", "corrected"] = "baseline"
    weak_reasons: list[str] = Field(default_factory=list)


class ResearchFollowupDeltaEvaluationOut(BaseModel):
    generated_at: datetime
    total_reports: int = 0
    followup_reports: int = 0
    invalid_payloads: int = 0
    metrics: list[ResearchFollowupDeltaMetricOut] = Field(default_factory=list)
    weakest_reports: list[ResearchFollowupDeltaWeakReportOut] = Field(default_factory=list)
    summary_lines: list[str] = Field(default_factory=list)


class ResearchDeliveryExportTrendPointOut(BaseModel):
    archive_id: str
    archive_kind: ResearchMarkdownArchiveKind
    archive_name: str
    updated_at: datetime
    solution_quality_percent: int = 0
    proposal_quality_percent: int = 0
    self_review_gain_percent: int = 0
    followup_impacted_section_count: int = 0
    changed_section_count: int = 0


class ResearchDeliveryExportVersionDeltaOut(BaseModel):
    key: Literal[
        "solution_delivery_quality_pass_rate",
        "project_proposal_quality_pass_rate",
        "delivery_self_review_gain_rate",
        "followup_impacted_section_count",
        "changed_section_count",
    ]
    label: str
    current_value: int = 0
    previous_value: int = 0
    delta_value: int = 0
    trend: Literal["up", "flat", "down"] = "flat"
    summary: str = ""


class ResearchDeliveryExportDiagnosticsOut(BaseModel):
    generated_at: datetime
    total_archives: int = 0
    analyzed_archives: int = 0
    archives_with_quality_snapshot: int = 0
    archives_with_followup_summary: int = 0
    trend_points: list[ResearchDeliveryExportTrendPointOut] = Field(default_factory=list)
    version_deltas: list[ResearchDeliveryExportVersionDeltaOut] = Field(default_factory=list)
    summary_lines: list[str] = Field(default_factory=list)


class ResearchGoldenEvaluationCaseOut(BaseModel):
    case_id: str
    title: str
    expected_methodology: str = ""
    professional_score: int = 0
    intelligence_value_score: int = 0
    target_support_rate: float = 0.0
    section_quota_pass_rate: float = 0.0
    passed: bool = False
    issues: list[str] = Field(default_factory=list)


class ResearchGoldenEvaluationOut(BaseModel):
    generated_at: datetime
    total_cases: int = 0
    passed_cases: int = 0
    average_professional_score: int = 0
    average_intelligence_value_score: int = 0
    average_target_support_rate: float = 0.0
    average_section_quota_pass_rate: float = 0.0
    cases: list[ResearchGoldenEvaluationCaseOut] = Field(default_factory=list)
    summary_lines: list[str] = Field(default_factory=list)


class ResearchRetrievalIndexRebuildRequest(BaseModel):
    limit_per_source: int = Field(default=240, ge=1, le=500)
    batch_size: int = Field(default=200, ge=1, le=1000)
    max_chunks: int | None = Field(default=None, ge=1, le=10000)
    resume: bool = True
    reset: bool = False


class ResearchRetrievalIndexRebuildOut(BaseModel):
    user_id: str
    schema_version: int = 2
    total_chunks: int = 0
    indexed_chunks: int = 0
    start_offset: int = 0
    next_offset: int = 0
    completed: bool = False
    batch_commits: int = 0
    source_counts: dict[str, int] = Field(default_factory=dict)
    backend: str = "sqlite"
    checkpoint_status: Literal["idle", "running", "completed", "failed"] = "idle"
    message: str = ""


class ResearchRetrievalIndexStatusOut(BaseModel):
    user_id: str
    schema_version: int = 2
    backend: str = "sqlite"
    checkpoint_status: Literal["idle", "running", "completed", "failed"] = "idle"
    total_chunks: int = 0
    indexed_chunks: int = 0
    next_offset: int = 0
    progress_percent: int = 0
    persisted_chunk_count: int = 0
    parent_link_count: int = 0
    orphan_child_count: int = 0
    remaining_chunks: int = 0
    persisted_reuse_percent: int = 0
    checkpoint_resume_ready: bool = False
    cache_health: Literal["cold", "warming", "warm", "stale"] = "cold"
    recovery_mode: Literal["none", "resume", "reset_recommended"] = "none"
    recovery_recommendation: str = ""
    source_counts: dict[str, int] = Field(default_factory=dict)
    document_type_counts: dict[str, int] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime | None = None


class ResearchRetrievalIndexSearchHitOut(BaseModel):
    chunk_id: str
    document_id: str
    document_type: str
    title: str
    snippet: str = ""
    field_key: str = ""
    label: str = ""
    source_tier: Literal["official", "media", "aggregate"] = "media"
    source_url: str = ""
    parent_chunk_id: str = ""
    topic_id: str = ""
    topic_name: str = ""
    region: str = ""
    industry: str = ""
    score: float = 0.0
    matched_terms: list[str] = Field(default_factory=list)
    match_modes: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class ResearchRetrievalIndexSearchOut(BaseModel):
    query: str
    hit_count: int = 0
    hits: list[ResearchRetrievalIndexSearchHitOut] = Field(default_factory=list)
    runtime_strategy_status: Literal["ready", "degraded", "fallback"] = "fallback"
    runtime_strategy_config: dict[str, Any] = Field(default_factory=dict)
    runtime_strategy_warnings: list[str] = Field(default_factory=list)


class ResearchCompareSnapshotCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    query: str = Field(default="", max_length=120)
    region_filter: str = Field(default="", max_length=40)
    industry_filter: str = Field(default="", max_length=40)
    role_filter: Literal["all", "甲方", "中标方", "竞品", "伙伴"] = "all"
    tracking_topic_id: str | None = Field(default=None, max_length=64)
    summary: str = Field(default="", max_length=600)
    rows: list[dict[str, Any]] = Field(default_factory=list, min_length=1, max_length=80)
    metadata_payload: dict[str, Any] = Field(default_factory=dict)


class ResearchCompareSnapshotOut(BaseModel):
    id: str
    name: str
    query: str = ""
    region_filter: str = ""
    industry_filter: str = ""
    role_filter: Literal["all", "甲方", "中标方", "竞品", "伙伴"] = "all"
    tracking_topic_id: str | None = None
    tracking_topic_name: str | None = None
    report_version_id: str | None = None
    report_version_title: str | None = None
    report_version_refreshed_at: datetime | None = None
    summary: str = ""
    row_count: int = 0
    source_entry_count: int = 0
    roles: list[ResearchCompareRole] = Field(default_factory=list)
    preview_names: list[str] = Field(default_factory=list)
    linked_report_diff: "ResearchCompareSnapshotLinkedVersionDiffOut | None" = None
    metadata_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ResearchCompareSnapshotDetailOut(ResearchCompareSnapshotOut):
    rows: list[dict[str, Any]] = Field(default_factory=list)


class ResearchCompareSnapshotDiffAxisOut(BaseModel):
    key: str
    label: str
    snapshot_count: int = 0
    linked_count: int = 0
    overlap_count: int = 0
    snapshot_only: list[str] = Field(default_factory=list)
    linked_only: list[str] = Field(default_factory=list)


class ResearchCompareSnapshotLinkedVersionDiffOut(BaseModel):
    status: ResearchCompareSnapshotDiffStatus = "unavailable"
    headline: str = ""
    summary_lines: list[str] = Field(default_factory=list)
    axes: list[ResearchCompareSnapshotDiffAxisOut] = Field(default_factory=list)


class ResearchMarkdownArchiveCreateRequest(BaseModel):
    archive_kind: ResearchMarkdownArchiveKind = "compare_markdown"
    name: str = Field(min_length=1, max_length=160)
    filename: str = Field(min_length=1, max_length=180)
    query: str = Field(default="", max_length=120)
    region_filter: str = Field(default="", max_length=40)
    industry_filter: str = Field(default="", max_length=40)
    tracking_topic_id: str | None = Field(default=None, max_length=64)
    compare_snapshot_id: str | None = Field(default=None, max_length=64)
    report_version_id: str | None = Field(default=None, max_length=64)
    summary: str = Field(default="", max_length=800)
    content: str = Field(min_length=1, max_length=200000)
    metadata_payload: dict[str, Any] = Field(default_factory=dict)


class ResearchMarkdownArchiveOut(BaseModel):
    id: str
    archive_kind: ResearchMarkdownArchiveKind = "compare_markdown"
    name: str
    filename: str
    query: str = ""
    region_filter: str = ""
    industry_filter: str = ""
    tracking_topic_id: str | None = None
    tracking_topic_name: str | None = None
    compare_snapshot_id: str | None = None
    compare_snapshot_name: str | None = None
    report_version_id: str | None = None
    report_version_title: str | None = None
    report_version_refreshed_at: datetime | None = None
    summary: str = ""
    preview_text: str = ""
    content_length: int = 0
    metadata_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ResearchMarkdownArchiveDetailOut(ResearchMarkdownArchiveOut):
    content: str = ""


class ResearchTrackingTopicRefreshRequest(BaseModel):
    output_language: OutputLanguage = "zh-CN"
    include_wechat: bool = True
    max_sources: int = Field(default=16, ge=6, le=24)
    save_to_knowledge: bool = True
    collection_name: str | None = Field(default=None, max_length=80)
    is_focus_reference: bool = False


class ResearchTrackingTopicRefreshResponse(BaseModel):
    topic: ResearchTrackingTopicOut
    report: ResearchReportResponse
    saved_entry_id: str | None = None
    saved_entry_title: str | None = None
    report_version_id: str | None = None
    persistence_status: Literal["persisted", "failed"] = "persisted"
    persistence_error: str | None = None


class ResearchWatchlistRefreshResponse(BaseModel):
    watchlist: ResearchWatchlistOut
    topic: ResearchTrackingTopicOut
    report: ResearchReportResponse
    changes: list[ResearchWatchlistChangeEventOut] = Field(default_factory=list)


class ResearchWatchlistRunDueItemOut(BaseModel):
    watchlist_id: str
    name: str
    status: Literal["refreshed", "failed"]
    change_count: int = 0
    attempt_count: int = 1
    retry_count: int = 0
    summary: str = ""
    next_due_at: datetime | None = None
    error: str | None = None
    notification_level: Literal["low", "medium", "high"] = "low"


class ResearchWatchlistRunDueResponse(BaseModel):
    checked_at: datetime
    run_id: str = ""
    due_count: int = 0
    refreshed_count: int = 0
    failed_count: int = 0
    retry_count: int = 0
    notifications: list[str] = Field(default_factory=list)
    items: list[ResearchWatchlistRunDueItemOut] = Field(default_factory=list)


class ResearchWatchlistRunOut(BaseModel):
    id: str
    run_id: str
    watchlist_id: str | None = None
    watchlist_name: str
    status: Literal["refreshed", "failed"]
    change_count: int = 0
    attempt_count: int = 1
    retry_count: int = 0
    summary: str = ""
    error: str | None = None
    notification_level: Literal["low", "medium", "high"] = "low"
    notification_payload: dict = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class ResearchWatchlistDigestExportOut(BaseModel):
    generated_at: datetime
    window_start: datetime
    window_end: datetime
    run_count: int = 0
    refreshed_count: int = 0
    failed_count: int = 0
    change_count: int = 0
    retry_count: int = 0
    alert_level: Literal["low", "medium", "high"] = "low"
    summary_lines: list[str] = Field(default_factory=list)
    runs: list[ResearchWatchlistRunOut] = Field(default_factory=list)
    export_markdown: str = ""


class ResearchWatchlistOpsIssueOut(BaseModel):
    watchlist_id: str | None = None
    topic_id: str | None = None
    name: str
    issue_type: Literal["due", "overdue", "refresh_failed", "stale", "unlinked"]
    severity: Literal["low", "medium", "high"] = "medium"
    summary: str
    last_checked_at: datetime | None = None
    next_due_at: datetime | None = None
    last_refreshed_at: datetime | None = None
    error: str | None = None


class ResearchWatchlistOpsSummaryOut(BaseModel):
    checked_at: datetime
    active_count: int = 0
    paused_count: int = 0
    scheduled_count: int = 0
    manual_count: int = 0
    due_count: int = 0
    overdue_count: int = 0
    stale_count: int = 0
    failed_topic_count: int = 0
    unlinked_count: int = 0
    next_due_at: datetime | None = None
    oldest_checked_at: datetime | None = None
    last_checked_at: datetime | None = None
    alert_level: Literal["low", "medium", "high"] = "low"
    action_required: bool = False
    recommendations: list[str] = Field(default_factory=list)
    issues: list[ResearchWatchlistOpsIssueOut] = Field(default_factory=list)


class ResearchWatchlistAutomationStatusOut(BaseModel):
    installed: bool = False
    loaded: bool = False
    label: str
    plist_path: str
    state_path: str
    log_path: str
    interval_seconds: int = 0
    last_checked_at: datetime | None = None
    last_due_count: int = 0
    last_refreshed_count: int = 0
    last_failed_count: int = 0
    last_run_status: Literal["idle", "ok", "partial_failure", "failed"] = "idle"
    last_summary: str = ""
    last_failure_hint: str = ""
    alert_level: Literal["low", "medium", "high"] = "low"
    action_required: bool = False
    action_required_reason: str = ""
    state_stale: bool = False
    state_age_seconds: int = 0
    recent_request_failure_count: int = 0
    consecutive_request_failure_count: int = 0
    failed_items: list[ResearchWatchlistRunDueItemOut] = Field(default_factory=list)
    last_log_size_bytes: int = 0
    recommended_run_due_command: str = ""
    recommended_status_command: str = ""
    recommended_install_command: str = ""
    recommended_uninstall_command: str = ""


class ResearchSourceOut(BaseModel):
    title: str
    url: str
    domain: str | None = None
    snippet: str
    search_query: str
    source_type: str
    content_status: str
    source_label: str | None = None
    source_tier: Literal["official", "media", "aggregate"] = "media"
    source_origin: Literal["search", "adapter", "snapshot_cache", "user_supplied"] = "search"


class ResearchEntityEvidenceOut(BaseModel):
    title: str
    url: str
    source_label: str | None = None
    source_tier: Literal["official", "media", "aggregate"] = "media"
    anchor_text: str = ""
    excerpt: str = ""
    confidence_tone: Literal["high", "low", "conflict"] = "low"


class ResearchScoreFactorOut(BaseModel):
    label: str
    score: int = 0
    note: str = ""


class ResearchRankedEntityOut(BaseModel):
    name: str
    score: int = 0
    reasoning: str = ""
    entity_mode: Literal["instance", "pending"] = "instance"
    score_breakdown: list[ResearchScoreFactorOut] = Field(default_factory=list)
    evidence_links: list[ResearchEntityEvidenceOut] = Field(default_factory=list)


class ResearchNormalizedEntityOut(BaseModel):
    canonical_name: str
    entity_type: Literal["target", "competitor", "partner", "generic"] = "generic"
    aliases: list[str] = Field(default_factory=list)
    source_count: int = 0
    source_tier_counts: dict[str, int] = Field(default_factory=dict)
    evidence_links: list[ResearchEntityEvidenceOut] = Field(default_factory=list)


class ResearchEntityGraphOut(BaseModel):
    entities: list[ResearchNormalizedEntityOut] = Field(default_factory=list)
    target_entities: list[ResearchNormalizedEntityOut] = Field(default_factory=list)
    competitor_entities: list[ResearchNormalizedEntityOut] = Field(default_factory=list)
    partner_entities: list[ResearchNormalizedEntityOut] = Field(default_factory=list)


class ResearchEntityRelationOut(BaseModel):
    id: str
    to_entity_id: str
    relation_type: str
    weight: int = 0
    evidence_payload: dict = Field(default_factory=dict)


class ResearchEntityDetailOut(BaseModel):
    id: str
    canonical_name: str
    entity_type: Literal["target", "competitor", "partner", "generic"] = "generic"
    region_hint: str = ""
    industry_hint: str = ""
    aliases: list[str] = Field(default_factory=list)
    evidence_links: list[ResearchEntityEvidenceOut] = Field(default_factory=list)
    linked_topic_ids: list[str] = Field(default_factory=list)
    relations: list[ResearchEntityRelationOut] = Field(default_factory=list)
    profile_payload: dict = Field(default_factory=dict)
    last_seen_at: datetime | None = None
    updated_at: datetime


class ResearchEntityAliasResolveRequest(BaseModel):
    entity_id: str = Field(min_length=1, max_length=64)
    alias_name: str = Field(min_length=1, max_length=160)
    confidence: int = Field(default=80, ge=0, le=100)


class ResearchScopeContractOut(BaseModel):
    framework: Literal["research_scope_contract_v1"] = "research_scope_contract_v1"
    contract_id: str = ""
    keyword: str = ""
    research_focus: str = ""
    research_mode: Literal["fast", "deep"] = "deep"
    task_type: Literal[
        "industry_research",
        "account_intelligence",
        "competitive_research",
        "solution_research",
        "general_research",
    ] = "general_research"
    regions: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    clients: list[str] = Field(default_factory=list)
    time_scope: list[str] = Field(default_factory=list)
    must_include_terms: list[str] = Field(default_factory=list)
    generic_terms: list[str] = Field(default_factory=list)
    exclusion_terms: list[str] = Field(default_factory=list)
    industry_methodology: str = ""
    scope_namespace: str = ""
    status: Literal["ready", "needs_clarification"] = "needs_clarification"
    reasons: list[str] = Field(default_factory=list)


class ResearchQuestionNodeOut(BaseModel):
    question_id: str
    axis: str
    question: str
    query: str = ""
    required_source_count: int = 1
    preferred_source_tiers: list[str] = Field(default_factory=list)
    matched_source_ids: list[str] = Field(default_factory=list)
    accepted_source_count: int = 0
    official_source_count: int = 0
    coverage_status: Literal["covered", "partial", "uncovered"] = "uncovered"
    corrective_queries: list[str] = Field(default_factory=list)


class ResearchQuestionTreeOut(BaseModel):
    framework: Literal["research_question_tree_v1"] = "research_question_tree_v1"
    root_question: str = ""
    question_count: int = 0
    covered_question_count: int = 0
    partial_question_count: int = 0
    uncovered_question_count: int = 0
    coverage_percent: int = 0
    status: Literal["ready", "needs_retrieval", "blocked"] = "needs_retrieval"
    questions: list[ResearchQuestionNodeOut] = Field(default_factory=list)
    corrective_queries: list[str] = Field(default_factory=list)


class ResearchSourceAdmissionOut(BaseModel):
    source_id: str
    title: str = ""
    url: str = ""
    domain: str = ""
    source_tier: Literal["official", "media", "aggregate"] = "media"
    source_origin: Literal["search", "adapter", "snapshot_cache", "user_supplied"] = "search"
    decision: Literal["accepted", "ambiguous", "rejected"] = "rejected"
    relevance_score: int = 0
    source_topology: Literal[
        "local_target_proof",
        "local_comparable",
        "external_benchmark",
        "policy_context",
        "historical_context",
        "unqualified",
    ] = "unqualified"
    evidence_lane: Literal["decision", "benchmark", "context", "rejected"] = "rejected"
    local_scope_match: bool = False
    current_signal: bool = False
    primary_origin: bool = False
    url_safe: bool = False
    snapshot_or_reused: bool = False
    formal_claim_eligible: bool = False
    account_pursuit_eligible: bool = False
    matched_scope_terms: list[str] = Field(default_factory=list)
    missing_scope_terms: list[str] = Field(default_factory=list)
    matched_question_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class ResearchEvidenceGateOut(BaseModel):
    framework: Literal["research_evidence_gate_v1"] = "research_evidence_gate_v1"
    enforced: bool = False
    status: Literal[
        "evidence_ready",
        "evidence_gap",
        "blocked_topic_mismatch",
        "blocked_runtime_degraded",
    ] = "evidence_gap"
    passed: bool = False
    formal_report_allowed: bool = False
    solution_delivery_allowed: bool = False
    minimum_source_count: int = 0
    minimum_official_source_count: int = 0
    minimum_unique_domain_count: int = 0
    minimum_question_coverage_percent: int = 0
    candidate_source_count: int = 0
    accepted_source_count: int = 0
    ambiguous_source_count: int = 0
    rejected_source_count: int = 0
    official_source_count: int = 0
    unique_domain_count: int = 0
    question_coverage_percent: int = 0
    local_target_proof_count: int = 0
    local_decision_source_count: int = 0
    external_benchmark_count: int = 0
    policy_context_count: int = 0
    historical_context_count: int = 0
    unsafe_source_count: int = 0
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


ResearchInteractionState = Literal[
    "ready",
    "provisional",
    "awaiting_user",
    "recovering",
    "system_degraded",
    "blocked",
]
ResearchClarificationInputKind = Literal[
    "single_choice",
    "multi_choice",
    "short_text",
    "url_list",
    "file_or_url",
]
ResearchClarificationAction = Literal[
    "submit_answers",
    "continue_search",
    "view_provisional",
    "retry_system",
]


class ResearchClarificationOptionOut(BaseModel):
    value: str
    label: str
    description: str = ""


class ResearchClarificationQuestionOut(BaseModel):
    question_id: str
    input_kind: ResearchClarificationInputKind = "short_text"
    prompt: str
    reason: str = ""
    required: bool = True
    placeholder: str = ""
    accepted_file_types: list[str] = Field(default_factory=list)
    options: list[ResearchClarificationOptionOut] = Field(default_factory=list)


class ResearchRecoveryOptionOut(BaseModel):
    action: ResearchClarificationAction
    label: str
    description: str = ""
    recommended: bool = False


class ResearchClarificationPacketOut(BaseModel):
    schema_version: Literal["research_clarification_v1"] = "research_clarification_v1"
    active: bool = False
    interaction_state: ResearchInteractionState = "ready"
    reason_code: str = ""
    title: str = ""
    summary: str = ""
    accepted_source_count: int = 0
    minimum_source_count: int = 0
    evidence_snapshot_digest: str = ""
    can_view_provisional: bool = False
    formal_delivery_allowed: bool = False
    system_retryable: bool = False
    recovery_attempt: int = 0
    recovery_limit: int = 3
    recovery_exhausted: bool = False
    requires_evidence_input: bool = False
    recovery_blocked_reason: str = ""
    questions: list[ResearchClarificationQuestionOut] = Field(default_factory=list)
    recovery_options: list[ResearchRecoveryOptionOut] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class ResearchClarificationAnswerIn(BaseModel):
    question_id: str = Field(min_length=1, max_length=120)
    values: list[str] = Field(default_factory=list, max_length=12)


class ResearchClarificationSubmitRequest(BaseModel):
    action: ResearchClarificationAction = "submit_answers"
    idempotency_key: str = Field(min_length=8, max_length=120)
    answers: list[ResearchClarificationAnswerIn] = Field(default_factory=list, max_length=8)
    supplemental_urls: list[str] = Field(default_factory=list, max_length=12)
    supplemental_text: str = Field(default="", max_length=8000)
    supplemental_documents: list[ResearchSupplementalDocumentIn] = Field(default_factory=list, max_length=4)


class ResearchCitationGateOut(BaseModel):
    framework: Literal["research_citation_gate_v1"] = "research_citation_gate_v1"
    enforced: bool = False
    status: Literal["pass", "watch", "fail"] = "watch"
    passed: bool = False
    claim_count: int = 0
    supported_claim_count: int = 0
    critical_claim_count: int = 0
    supported_critical_claim_count: int = 0
    conflicted_claim_count: int = 0
    citation_completeness_percent: int = 0
    critical_claim_coverage_percent: int = 0
    citation_support_percent: int = 0
    unsupported_critical_claim_ids: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ResearchEntityAuthenticityGateOut(BaseModel):
    framework: Literal["research_entity_authenticity_gate_v1"] = "research_entity_authenticity_gate_v1"
    enforced: bool = False
    status: Literal["not_run", "pass", "fail"] = "not_run"
    passed: bool = False
    checked_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    repaired_count: int = 0
    unsupported_count: int = 0
    rejected_samples: list[str] = Field(default_factory=list)
    repair_samples: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ResearchPipelineStageOut(BaseModel):
    key: Literal["fetch", "clean", "analyze"]
    label: str
    value: int = 0
    summary: str = ""


class ResearchSourceDiagnosticsOut(BaseModel):
    enabled_source_labels: list[str] = Field(default_factory=list)
    matched_source_labels: list[str] = Field(default_factory=list)
    scope_regions: list[str] = Field(default_factory=list)
    scope_industries: list[str] = Field(default_factory=list)
    scope_clients: list[str] = Field(default_factory=list)
    guarded_backlog: bool = False
    guarded_rewrite_reasons: list[str] = Field(default_factory=list)
    guarded_rewrite_reason_labels: list[str] = Field(default_factory=list)
    supported_target_accounts: list[str] = Field(default_factory=list)
    unsupported_target_accounts: list[str] = Field(default_factory=list)
    source_type_counts: dict[str, int] = Field(default_factory=dict)
    source_tier_counts: dict[str, int] = Field(default_factory=dict)
    adapter_hit_count: int = 0
    search_hit_count: int = 0
    search_query_count: int = 0
    search_retry_count: int = 0
    search_zero_result_query_count: int = 0
    search_unique_domain_count: int = 0
    fresh_source_count: int = 0
    snapshot_recovery_used: bool = False
    snapshot_recovery_source_count: int = 0
    snapshot_recovery_job_id: str = ""
    snapshot_recovery_age_hours: int = 0
    recency_window_years: int = 7
    filtered_old_source_count: int = 0
    filtered_region_conflict_count: int = 0
    retained_source_count: int = 0
    strict_topic_source_count: int = 0
    topic_anchor_terms: list[str] = Field(default_factory=list)
    matched_theme_labels: list[str] = Field(default_factory=list)
    retrieval_quality: Literal["low", "medium", "high"] = "low"
    evidence_mode: Literal["strong", "provisional", "fallback"] = "fallback"
    evidence_mode_label: str = "兜底候选"
    strict_match_ratio: float = 0.0
    official_source_ratio: float = 0.0
    unique_domain_count: int = 0
    normalized_entity_count: int = 0
    normalized_target_count: int = 0
    normalized_competitor_count: int = 0
    normalized_partner_count: int = 0
    expansion_triggered: bool = False
    corrective_triggered: bool = False
    correction_status: Literal["ready", "needs_filtering", "needs_expansion"] = "ready"
    retrieval_relevance_score: int = 0
    accepted_source_count: int = 0
    ambiguous_source_count: int = 0
    rejected_source_count: int = 0
    source_topology_counts: dict[str, int] = Field(default_factory=dict)
    local_target_proof_count: int = 0
    local_decision_source_count: int = 0
    external_benchmark_count: int = 0
    policy_context_count: int = 0
    historical_context_count: int = 0
    unsafe_source_count: int = 0
    corrective_query_plan: list[str] = Field(default_factory=list)
    correction_notes: list[str] = Field(default_factory=list)
    generation_grounding_score: int = 0
    response_quality_score: int = 0
    generation_provider: str = ""
    generation_model: str = ""
    generation_status: Literal["succeeded", "fallback", "failed", ""] = ""
    generation_fallback_used: bool = False
    generation_notes: list[str] = Field(default_factory=list)
    entity_authenticity_gate_status: Literal["not_run", "pass", "fail"] = "not_run"
    entity_authenticity_gate_passed: bool = False
    entity_authenticity_checked_count: int = 0
    entity_authenticity_rejected_count: int = 0
    entity_authenticity_repaired_count: int = 0
    entity_authenticity_unsupported_count: int = 0
    entity_authenticity_rejected_samples: list[str] = Field(default_factory=list)
    entity_authenticity_repair_samples: list[str] = Field(default_factory=list)
    supported_claims: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    generation_review_notes: list[str] = Field(default_factory=list)
    reranker_used: bool = False
    reranker_model: str = ""
    reranker_top_k: int = 0
    reranker_backend: str = ""
    reranker_notes: list[str] = Field(default_factory=list)
    candidate_profile_companies: list[str] = Field(default_factory=list)
    candidate_profile_hit_count: int = 0
    candidate_profile_official_hit_count: int = 0
    candidate_profile_source_labels: list[str] = Field(default_factory=list)
    quality_expansion_triggered: bool = False
    quality_expansion_rounds: int = 0
    quality_expansion_before_score: int = 0
    quality_expansion_after_score: int = 0
    quality_expansion_added_source_count: int = 0
    quality_expansion_query_plan: list[str] = Field(default_factory=list)
    quality_expansion_notes: list[str] = Field(default_factory=list)
    strategy_model_used: bool = False
    strategy_scope_summary: str = ""
    strategy_query_expansion_count: int = 0
    strategy_exclusion_terms: list[str] = Field(default_factory=list)
    runtime_strategy_status: Literal["ready", "degraded", "fallback", ""] = ""
    runtime_strategy_applied_lanes: list[ResearchExperimentLaneKey] = Field(default_factory=list)
    runtime_strategy_fallback_lanes: list[ResearchExperimentLaneKey] = Field(default_factory=list)
    runtime_strategy_warnings: list[str] = Field(default_factory=list)
    runtime_query_recovery_enabled: bool = False
    runtime_source_reranker_enabled: bool = False
    pipeline_summary: str = ""
    pipeline_stages: list[ResearchPipelineStageOut] = Field(default_factory=list)


class ResearchFollowupContextOut(BaseModel):
    followup_report_title: str = ""
    followup_report_summary: str = ""
    supplemental_context: str = ""
    supplemental_evidence: str = ""
    supplemental_requirements: str = ""


class ResearchFollowupSectionImpactOut(BaseModel):
    section_title: str
    status: Literal["ready", "degraded", "needs_evidence"] = "needs_evidence"
    impact_score: int = 0
    impact_label: Literal["high", "medium", "low"] = "low"
    reason: str = ""
    matched_inputs: list[str] = Field(default_factory=list)
    retrieval_support_score: int = 0
    retrieval_hit_count: int = 0
    official_hit_count: int = 0
    next_action: str = ""


class ResearchFollowupDiagnosticsOut(BaseModel):
    enabled: bool = False
    input_sections: list[str] = Field(default_factory=list)
    planning_focus: str = ""
    summary: str = ""
    scope_rebuilt: bool = False
    query_decomposition_applied: bool = False
    decomposition_queries: list[str] = Field(default_factory=list)
    rebuilt_regions: list[str] = Field(default_factory=list)
    rebuilt_industries: list[str] = Field(default_factory=list)
    rebuilt_clients: list[str] = Field(default_factory=list)
    rebuilt_company_anchors: list[str] = Field(default_factory=list)
    rebuilt_must_include_terms: list[str] = Field(default_factory=list)
    rebuilt_exclusion_terms: list[str] = Field(default_factory=list)
    title_resolution: Literal["baseline", "reused", "corrected"] = "baseline"
    summary_resolution: Literal["baseline", "reused", "corrected"] = "baseline"
    impacted_sections: list[ResearchFollowupSectionImpactOut] = Field(default_factory=list)


class ResearchReportSectionOut(BaseModel):
    title: str
    items: list[str] = Field(default_factory=list)
    status: Literal["ready", "degraded", "needs_evidence"] = "needs_evidence"
    evidence_density: Literal["low", "medium", "high"] = "low"
    source_quality: Literal["low", "medium", "high"] = "low"
    confidence_tone: Literal["high", "low", "conflict"] = "low"
    confidence_label: str = ""
    confidence_reason: str = ""
    evidence_note: str = ""
    insufficiency_reasons: list[str] = Field(default_factory=list)
    insufficiency_summary: str = ""
    source_tier_counts: dict[str, int] = Field(default_factory=dict)
    official_source_ratio: float = 0.0
    evidence_links: list[ResearchEntityEvidenceOut] = Field(default_factory=list)
    evidence_count: int = 0
    evidence_quota: int = 0
    meets_evidence_quota: bool = False
    quota_gap: int = 0
    quota_note: str = ""
    next_verification_steps: list[str] = Field(default_factory=list)
    contradiction_detected: bool = False
    contradiction_note: str = ""


class ResearchReportReadinessOut(BaseModel):
    status: Literal["ready", "degraded", "needs_evidence"] = "needs_evidence"
    score: int = 0
    actionable: bool = False
    evidence_gate_passed: bool = False
    reasons: list[str] = Field(default_factory=list)
    missing_axes: list[str] = Field(default_factory=list)
    next_verification_steps: list[str] = Field(default_factory=list)


class ResearchDeliveryTruthOut(BaseModel):
    framework: Literal["research_delivery_truth_v1"] = "research_delivery_truth_v1"
    status: Literal["formal", "provisional", "awaiting_user", "system_degraded"] = "awaiting_user"
    delivery_mode: Literal["account_pursuit", "market_scan", "evidence_recovery"] = "evidence_recovery"
    formal_delivery_allowed: bool = False
    customer_material_allowed: bool = False
    section_confidence_cap: Literal["high", "low"] = "low"
    decisive_reasons: list[str] = Field(default_factory=list)
    blocking_gate_keys: list[str] = Field(default_factory=list)
    next_action: str = ""


class ResearchCommercialSummaryOut(BaseModel):
    account_focus: list[str] = Field(default_factory=list)
    budget_signal: str = ""
    entry_window: str = ""
    competition_or_partner: str = ""
    next_action: str = ""


class ResearchScenarioOut(BaseModel):
    name: str
    summary: str = ""
    implication: str = ""


class ResearchTechnicalAppendixOut(BaseModel):
    key_assumptions: list[str] = Field(default_factory=list)
    scenario_comparison: list[ResearchScenarioOut] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    technical_appendix: list[str] = Field(default_factory=list)


class ResearchReviewQueueItemOut(BaseModel):
    id: str
    section_title: str
    severity: Literal["high", "medium", "low"] = "medium"
    summary: str = ""
    recommended_action: str = ""
    evidence_links: list[ResearchEntityEvidenceOut] = Field(default_factory=list)
    resolution_status: Literal["open", "resolved", "deferred"] = "open"
    resolution_note: str = ""
    resolved_at: datetime | None = None


class ResearchQualityDimensionOut(BaseModel):
    key: Literal["professional_rigor", "intelligence_value", "actionability", "evidence_strength"]
    label: str
    score: int = 0
    status: Literal["strong", "usable", "weak"] = "weak"
    summary: str = ""
    evidence: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class ResearchMethodologyAxisOut(BaseModel):
    key: str
    label: str
    checkpoints: list[str] = Field(default_factory=list)
    passed: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    implication: str = ""


class ResearchIndustryMethodologyOut(BaseModel):
    industry_key: str = "generic"
    industry_label: str = "通用 B2B 解决方案研究"
    framework_name: str = "市场-账户-预算-竞争-落地五段式"
    summary: str = ""
    axes: list[ResearchMethodologyAxisOut] = Field(default_factory=list)
    recommended_questions: list[str] = Field(default_factory=list)


class ResearchSectionEvidencePackOut(BaseModel):
    section_title: str
    status: Literal["ready", "degraded", "needs_evidence"] = "needs_evidence"
    support_score: int = 0
    evidence_count: int = 0
    official_evidence_count: int = 0
    quota_gap: int = 0
    source_titles: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class ResearchSectionRetrievalHitOut(BaseModel):
    chunk_id: str
    document_id: str
    document_type: str
    title: str
    snippet: str = ""
    field_key: str = ""
    label: str = ""
    source_tier: Literal["official", "media", "aggregate"] = "media"
    source_url: str = ""
    score: float = 0.0
    matched_terms: list[str] = Field(default_factory=list)
    match_modes: list[str] = Field(default_factory=list)


class ResearchSectionRetrievalPackOut(BaseModel):
    section_title: str
    query: str
    target_axes: list[str] = Field(default_factory=list)
    status: Literal["ready", "degraded", "needs_evidence"] = "needs_evidence"
    hit_count: int = 0
    official_hit_count: int = 0
    support_score: int = 0
    hits: list[ResearchSectionRetrievalHitOut] = Field(default_factory=list)
    missing_terms: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class ResearchSectionRetrievalPackRequest(BaseModel):
    report: "ResearchReportDocument"
    limit_per_section: int = Field(default=4, ge=1, le=10)
    limit_per_source: int = Field(default=240, ge=1, le=500)


class ResearchTenderProjectOut(BaseModel):
    project_name: str
    buyer: str = ""
    region: str = ""
    industry_or_scene: str = ""
    notice_type: str = ""
    publish_date: str = ""
    amount: str = ""
    winning_vendor: str = ""
    bidder_candidates: list[str] = Field(default_factory=list)
    tender_agency: str = ""
    project_code: str = ""
    buyer_contact: str = ""
    source_title: str = ""
    source_url: str = ""
    source_tier: Literal["official", "media", "aggregate"] = "media"
    relevance_score: int = 0
    extracted_requirements: list[str] = Field(default_factory=list)
    technical_parameters: list[str] = Field(default_factory=list)


class ResearchProductRequirementOut(BaseModel):
    name: str
    category: str = ""
    source_context: str = ""
    evidence_urls: list[str] = Field(default_factory=list)
    linked_projects: list[str] = Field(default_factory=list)
    technical_parameters: list[str] = Field(default_factory=list)


class ResearchMarketIntelligencePackOut(BaseModel):
    lookback_years: int = 3
    window_start: str = ""
    window_end: str = ""
    source_scope_summary: str = ""
    source_support_score: int = 0
    validated_source_count: int = 0
    ambiguous_source_count: int = 0
    rejected_source_count: int = 0
    corrective_queries: list[str] = Field(default_factory=list)
    tender_projects: list[ResearchTenderProjectOut] = Field(default_factory=list)
    tender_keywords: list[str] = Field(default_factory=list)
    product_catalog: list[ResearchProductRequirementOut] = Field(default_factory=list)
    technical_parameter_catalog: list[ResearchProductRequirementOut] = Field(default_factory=list)
    external_source_queries: list[str] = Field(default_factory=list)
    intelligence_gaps: list[str] = Field(default_factory=list)
    export_markdown: str = ""


class ResearchSolutionOutlineSectionOut(BaseModel):
    title: str
    bullets: list[str] = Field(default_factory=list)


class ResearchDeliveryCompiledSectionOut(BaseModel):
    title: str
    purpose: str = ""
    bullets: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    validation_actions: list[str] = Field(default_factory=list)


class ResearchDeliveryCompiledDocumentOut(BaseModel):
    framework: Literal[
        "solution_design_compiler_v1",
        "consulting_report_compiler_v1",
        "project_proposal_compiler_v1",
        "feasibility_study_compiler_v1",
    ]
    document_kind: Literal["solution_design", "consulting_report", "project_proposal", "feasibility_study"]
    title: str
    audience: str = ""
    purpose: str = ""
    evidence_policy: str = ""
    sections: list[ResearchDeliveryCompiledSectionOut] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    validation_actions: list[str] = Field(default_factory=list)
    quality_gates: list[str] = Field(default_factory=list)
    export_markdown: str = ""


class ResearchDecisionCriterionScoreOut(BaseModel):
    criterion_key: str
    label: str
    weight_percent: int = 0
    score: int = 0
    rationale: str = ""


class ResearchDecisionAlternativeOptionOut(BaseModel):
    option_id: str
    name: str
    summary: str = ""
    weighted_score: int = 0
    rank: int = 0
    criterion_scores: list[ResearchDecisionCriterionScoreOut] = Field(default_factory=list)
    decision_rationale: str = ""
    assumptions: list[str] = Field(default_factory=list)
    validation_actions: list[str] = Field(default_factory=list)


class ResearchTenderScoreResponseItemOut(BaseModel):
    score_item: str
    weight_percent: int = 0
    response_strategy: str = ""
    mapped_sections: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    owner: str = ""
    risk_level: Literal["high", "medium", "low"] = "medium"
    validation_action: str = ""


class ResearchFinancialScenarioOut(BaseModel):
    scenario_key: Literal["pessimistic", "base", "optimistic"]
    label: str
    capex_cny: float | None = None
    annual_opex_cny: float | None = None
    annual_benefit_cny: float | None = None
    tco_3y_cny: float | None = None
    net_benefit_3y_cny: float | None = None
    payback_months: float | None = None
    npv_3y_cny: float | None = None
    irr_percent: float | None = None
    roi_percent: float | None = None
    confidence: Literal["high", "medium", "low"] = "low"
    assumptions: list[str] = Field(default_factory=list)


class ResearchSensitivityVariableOut(BaseModel):
    variable_key: str
    label: str
    base_value: float | None = None
    low_value: float | None = None
    high_value: float | None = None
    unit: str = ""
    impact_summary: str = ""
    validation_action: str = ""


class ResearchQuantitativeDecisionModelOut(BaseModel):
    framework: Literal["delivery_quantitative_decision_model_v1"] = "delivery_quantitative_decision_model_v1"
    status: Literal["ready", "assumption_required", "blocked"] = "assumption_required"
    recommended_option_id: str = ""
    summary: str = ""
    alternative_options: list[ResearchDecisionAlternativeOptionOut] = Field(default_factory=list)
    tender_score_response_matrix: list[ResearchTenderScoreResponseItemOut] = Field(default_factory=list)
    financial_scenarios: list[ResearchFinancialScenarioOut] = Field(default_factory=list)
    sensitivity_variables: list[ResearchSensitivityVariableOut] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    validation_actions: list[str] = Field(default_factory=list)
    export_markdown: str = ""


class ResearchAdvisoryArtifactOut(BaseModel):
    artifact_type: Literal["client_brief", "bidding_prep_memo", "execution_materials"]
    title: str
    audience: str = ""
    purpose: str = ""
    source_policy: str = ""
    markdown: str = ""
    review_checklist: list[str] = Field(default_factory=list)


class ResearchDeliveryQualityMetricOut(BaseModel):
    key: str
    label: str
    score: int = 0
    threshold: int = 75
    status: Literal["pass", "watch", "fail"] = "watch"
    summary: str = ""
    gaps: list[str] = Field(default_factory=list)
    improvement_actions: list[str] = Field(default_factory=list)


class ResearchDeliverySelfReviewOut(BaseModel):
    triggered: bool = False
    before_score: int = 0
    after_score: int = 0
    actions: list[str] = Field(default_factory=list)
    added_sections: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ResearchDeliveryNumericFactOut(BaseModel):
    metric: str
    raw_value: str
    normalized_value: float | None = None
    normalized_unit: str = ""
    context: str = ""


class ResearchDeliveryEvidenceAnchorOut(BaseModel):
    evidence_id: str
    title: str = ""
    url: str = ""
    source_label: str | None = None
    source_tier: Literal["official", "media", "aggregate"] = "media"
    anchor_text: str = ""
    excerpt: str = ""
    document_ref: str = ""
    entities: list[str] = Field(default_factory=list)
    numeric_facts: list[ResearchDeliveryNumericFactOut] = Field(default_factory=list)


class ResearchDeliveryClaimEvidenceRelationOut(BaseModel):
    evidence_id: str
    relation_type: Literal["supports", "conflicts", "background", "needs_validation"] = "needs_validation"
    score: int = 0
    rationale: str = ""


class ResearchDeliveryClaimOut(BaseModel):
    claim_id: str
    section_title: str = ""
    claim_type: Literal[
        "fact",
        "numeric",
        "recommendation",
        "procurement",
        "compliance",
        "assumption",
    ] = "fact"
    text: str
    confidence: Literal["high", "medium", "low"] = "medium"
    entities: list[str] = Field(default_factory=list)
    numeric_facts: list[ResearchDeliveryNumericFactOut] = Field(default_factory=list)
    evidence_relations: list[ResearchDeliveryClaimEvidenceRelationOut] = Field(default_factory=list)
    verification_status: Literal["supported", "conflicted", "background_only", "needs_validation"] = (
        "needs_validation"
    )


class ResearchDeliveryConsistencyIssueOut(BaseModel):
    issue_id: str
    issue_type: Literal[
        "entity_role_conflict",
        "entity_not_supported",
        "numeric_conflict",
        "numeric_unit_mismatch",
    ]
    severity: Literal["high", "medium", "low"] = "medium"
    claim_ids: list[str] = Field(default_factory=list)
    summary: str = ""
    details: list[str] = Field(default_factory=list)


class ResearchDeliveryEvidenceLedgerOut(BaseModel):
    framework: Literal["delivery_claim_evidence_ledger_v1"] = "delivery_claim_evidence_ledger_v1"
    claim_count: int = 0
    evidence_count: int = 0
    supported_claim_count: int = 0
    conflicted_claim_count: int = 0
    background_only_claim_count: int = 0
    needs_validation_claim_count: int = 0
    high_confidence_claim_count: int = 0
    high_confidence_supported_count: int = 0
    claim_coverage_percent: int = 0
    high_confidence_coverage_percent: int = 0
    entity_consistency_score: int = 100
    numeric_consistency_score: int = 100
    status: Literal["pass", "watch", "fail"] = "watch"
    claims: list[ResearchDeliveryClaimOut] = Field(default_factory=list)
    evidence: list[ResearchDeliveryEvidenceAnchorOut] = Field(default_factory=list)
    consistency_issues: list[ResearchDeliveryConsistencyIssueOut] = Field(default_factory=list)


class ResearchDeliverySemanticChallengeIssueOut(BaseModel):
    issue_id: str
    issue_type: Literal[
        "scope_drift",
        "cross_section_conflict",
        "unsupported_high_confidence_claim",
        "source_contamination",
        "entity_conflict",
        "numeric_conflict",
        "template_language",
        "missing_gold_sample_review",
    ]
    severity: Literal["high", "medium", "low"] = "medium"
    section_title: str = ""
    claim_ids: list[str] = Field(default_factory=list)
    summary: str = ""
    evidence: list[str] = Field(default_factory=list)
    suggested_action: str = ""


class ResearchDeliverySemanticChallengeOut(BaseModel):
    framework: Literal["delivery_semantic_challenger_v1"] = "delivery_semantic_challenger_v1"
    status: Literal["pass", "watch", "fail"] = "watch"
    overall_score: int = 0
    issue_count: int = 0
    high_severity_count: int = 0
    scope_drift_count: int = 0
    cross_section_conflict_count: int = 0
    golden_sample_id: str = ""
    golden_sample_title: str = ""
    golden_sample_alignment_score: int = 0
    issues: list[ResearchDeliverySemanticChallengeIssueOut] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class ResearchDeliveryQualityProfileOut(BaseModel):
    framework: Literal["china_tech_delivery_review_v1"] = "china_tech_delivery_review_v1"
    framework_label: str = "中国科技项目交付质量自审"
    review_target: Literal["solution_delivery", "project_proposal", "feasibility_study"] = "solution_delivery"
    overall_score: int = 0
    status: Literal["pass", "watch", "fail"] = "watch"
    metrics: list[ResearchDeliveryQualityMetricOut] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    required_axes: list[str] = Field(default_factory=list)
    missing_axes: list[str] = Field(default_factory=list)
    evidence_ledger: ResearchDeliveryEvidenceLedgerOut = Field(default_factory=ResearchDeliveryEvidenceLedgerOut)
    semantic_challenge: ResearchDeliverySemanticChallengeOut = Field(
        default_factory=ResearchDeliverySemanticChallengeOut
    )
    self_review: ResearchDeliverySelfReviewOut = Field(default_factory=ResearchDeliverySelfReviewOut)


class ResearchSolutionArchitectureBlueprintSectionOut(BaseModel):
    title: str
    purpose: str = ""
    components: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class ResearchSolutionArchitectureReadinessOut(BaseModel):
    framework: Literal["solution_architecture_readiness_v1"] = "solution_architecture_readiness_v1"
    framework_label: str = "解决方案架构就绪度"
    overall_score: int = 0
    status: Literal["ready", "watch", "blocked"] = "watch"
    summary: str = ""
    metrics: list[ResearchDeliveryQualityMetricOut] = Field(default_factory=list)
    blueprint_sections: list[ResearchSolutionArchitectureBlueprintSectionOut] = Field(default_factory=list)
    non_functional_requirements: list[str] = Field(default_factory=list)
    integration_risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    validation_actions: list[str] = Field(default_factory=list)
    stakeholder_questions: list[str] = Field(default_factory=list)


class ResearchCustomerScenarioOut(BaseModel):
    name: str
    target_customer: str = ""
    primary_roles: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    desired_outcomes: list[str] = Field(default_factory=list)
    success_metrics: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class ResearchSolutionStakeholderOut(BaseModel):
    role: str
    influence: Literal["high", "medium", "low"] = "medium"
    likely_concerns: list[str] = Field(default_factory=list)
    decision_questions: list[str] = Field(default_factory=list)
    required_materials: list[str] = Field(default_factory=list)


class ResearchSolutionDecisionCriterionOut(BaseModel):
    criterion: str
    why_it_matters: str = ""
    evidence: list[str] = Field(default_factory=list)
    validation_action: str = ""


class ResearchSolutionCapabilityArchitectureMappingOut(BaseModel):
    business_capability: str
    application_services: list[str] = Field(default_factory=list)
    data_dependencies: list[str] = Field(default_factory=list)
    model_dependencies: list[str] = Field(default_factory=list)
    integration_surfaces: list[str] = Field(default_factory=list)
    security_constraints: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    validation_actions: list[str] = Field(default_factory=list)


class ResearchSolutionArchitectureDecisionRecordOut(BaseModel):
    decision: str
    context: str = ""
    options: list[str] = Field(default_factory=list)
    selected_direction: str = ""
    tradeoffs: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    validation_evidence: list[str] = Field(default_factory=list)


class ResearchSolutionIntegrationDependencyOut(BaseModel):
    dependency: str
    source_system: str = ""
    api_or_data_contract: str = ""
    auth_boundary: str = ""
    deployment_assumption: str = ""
    operational_owner: str = ""
    risk_level: Literal["high", "medium", "low"] = "medium"
    validation_action: str = ""
    evidence: list[str] = Field(default_factory=list)


class ResearchSolutionArchitectWorkbenchOut(BaseModel):
    framework: Literal["solution_architect_workbench_v1"] = "solution_architect_workbench_v1"
    framework_label: str = "解决方案架构师工作台"
    customer_scenarios: list[ResearchCustomerScenarioOut] = Field(default_factory=list)
    stakeholders: list[ResearchSolutionStakeholderOut] = Field(default_factory=list)
    decision_criteria: list[ResearchSolutionDecisionCriterionOut] = Field(default_factory=list)
    capability_architecture_matrix: list[ResearchSolutionCapabilityArchitectureMappingOut] = Field(default_factory=list)
    architecture_decision_records: list[ResearchSolutionArchitectureDecisionRecordOut] = Field(default_factory=list)
    integration_dependencies: list[ResearchSolutionIntegrationDependencyOut] = Field(default_factory=list)
    next_meeting_agenda: list[str] = Field(default_factory=list)


class ResearchArchitectureAdrTableRowOut(BaseModel):
    decision: str
    context: str = ""
    selected_direction: str = ""
    options: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    validation_evidence: list[str] = Field(default_factory=list)
    owner: str = "解决方案架构师"
    status: Literal["draft", "review_ready", "confirmed"] = "draft"


class ResearchArchitectureDependencyWorkshopItemOut(BaseModel):
    dependency: str
    owner: str = ""
    risk_level: Literal["high", "medium", "low"] = "medium"
    source_system: str = ""
    required_inputs: list[str] = Field(default_factory=list)
    workshop_questions: list[str] = Field(default_factory=list)
    expected_decision: str = ""
    validation_action: str = ""
    evidence: list[str] = Field(default_factory=list)


class ResearchArchitectureStakeholderBriefOut(BaseModel):
    title: str = ""
    audience: str = ""
    summary: str = ""
    key_messages: list[str] = Field(default_factory=list)
    stakeholder_questions: list[str] = Field(default_factory=list)
    required_materials: list[str] = Field(default_factory=list)
    decision_criteria: list[str] = Field(default_factory=list)


class ResearchArchitectureWorkshopAgendaItemOut(BaseModel):
    topic: str
    owner: str = ""
    duration_minutes: int = 15
    questions: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class ResearchSolutionArchitectureExportBundleOut(BaseModel):
    framework: Literal["solution_architecture_export_bundle_v1"] = "solution_architecture_export_bundle_v1"
    framework_label: str = "架构交付导出包"
    adr_table: list[ResearchArchitectureAdrTableRowOut] = Field(default_factory=list)
    dependency_workshop_checklist: list[ResearchArchitectureDependencyWorkshopItemOut] = Field(default_factory=list)
    stakeholder_brief: ResearchArchitectureStakeholderBriefOut = Field(default_factory=ResearchArchitectureStakeholderBriefOut)
    customer_technical_workshop_agenda: list[ResearchArchitectureWorkshopAgendaItemOut] = Field(default_factory=list)
    export_markdown: str = ""


class ResearchQualityAttributeScenarioOut(BaseModel):
    scenario_id: str
    quality_attribute: Literal[
        "availability",
        "reliability",
        "security",
        "performance",
        "cost",
        "operability",
        "maintainability",
        "ai_risk",
    ]
    business_source: str = ""
    stimulus: str = ""
    environment: str = ""
    artifact: str = ""
    response: str = ""
    response_measure: str = ""
    priority: Literal["high", "medium", "low"] = "medium"
    status: Literal["draft", "confirmed", "validated"] = "draft"
    evidence: list[str] = Field(default_factory=list)
    acceptance_test_ids: list[str] = Field(default_factory=list)


class ResearchArchitectureOptionOut(BaseModel):
    option_id: str
    option_type: Literal["baseline", "pilot", "target"]
    name: str
    description: str = ""
    benefits: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class ResearchArchitectureDecisionRecordV2Out(BaseModel):
    adr_id: str
    title: str
    status: Literal["proposed", "accepted", "validated", "rejected"] = "proposed"
    context: str = ""
    drivers: list[str] = Field(default_factory=list)
    options: list[ResearchArchitectureOptionOut] = Field(default_factory=list)
    selected_option_id: str = ""
    evidence: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    consequences: list[str] = Field(default_factory=list)
    rollback_conditions: list[str] = Field(default_factory=list)
    validation_action_ids: list[str] = Field(default_factory=list)
    owner: str = "解决方案架构师"
    due_date: str = ""
    risk_level: Literal["high", "medium", "low"] = "medium"


class ResearchATAMUtilityNodeOut(BaseModel):
    node_id: str
    quality_attribute: str
    scenario_ids: list[str] = Field(default_factory=list)
    priority: Literal["high", "medium", "low"] = "medium"
    difficulty: Literal["high", "medium", "low"] = "medium"


class ResearchATAMFindingOut(BaseModel):
    finding_id: str
    finding_type: Literal[
        "risk",
        "non_risk",
        "sensitivity_point",
        "tradeoff_point",
        "risk_theme",
    ]
    title: str
    details: str = ""
    scenario_ids: list[str] = Field(default_factory=list)
    adr_ids: list[str] = Field(default_factory=list)
    owner: str = ""


class ResearchATAMAssessmentOut(BaseModel):
    framework: Literal["atam_utility_tree_v1"] = "atam_utility_tree_v1"
    utility_tree: list[ResearchATAMUtilityNodeOut] = Field(default_factory=list)
    findings: list[ResearchATAMFindingOut] = Field(default_factory=list)
    risk_theme_count: int = 0
    high_risk_count: int = 0


class ResearchC4ElementOut(BaseModel):
    element_id: str
    name: str
    element_type: Literal["person", "software_system", "container", "component", "deployment_node"]
    description: str = ""
    technology: str = ""
    business_scenario_ids: list[str] = Field(default_factory=list)
    data_assets: list[str] = Field(default_factory=list)
    interfaces: list[str] = Field(default_factory=list)
    responsibility_boundary: str = ""
    quality_scenario_ids: list[str] = Field(default_factory=list)
    deployment_target: str = ""


class ResearchC4RelationshipOut(BaseModel):
    source_id: str
    target_id: str
    description: str = ""
    interface: str = ""
    data_flow: str = ""


class ResearchC4ViewOut(BaseModel):
    view_id: str
    level: Literal["context", "container", "component", "dynamic", "deployment"]
    title: str
    audience: str = ""
    element_ids: list[str] = Field(default_factory=list)
    relationships: list[ResearchC4RelationshipOut] = Field(default_factory=list)


class ResearchWellArchitectedCheckOut(BaseModel):
    check_id: str
    pillar: Literal[
        "reliability",
        "security",
        "performance",
        "cost",
        "operations",
        "ai_data",
        "ai_model",
        "ai_content",
        "ai_supply_chain",
        "ai_human_oversight",
        "ai_continuous_monitoring",
    ]
    status: Literal["pass", "watch", "blocked"] = "watch"
    question: str = ""
    finding: str = ""
    evidence: list[str] = Field(default_factory=list)
    action: str = ""
    owner: str = ""


class ResearchArchitectureTraceabilityLinkOut(BaseModel):
    requirement_id: str
    business_requirement: str = ""
    capability: str = ""
    component_ids: list[str] = Field(default_factory=list)
    data_assets: list[str] = Field(default_factory=list)
    interfaces: list[str] = Field(default_factory=list)
    deployment_node_ids: list[str] = Field(default_factory=list)
    risk_ids: list[str] = Field(default_factory=list)
    acceptance_test_ids: list[str] = Field(default_factory=list)


class ResearchArchitectureDecisionEngineeringOut(BaseModel):
    framework: Literal["qaw_atam_c4_decision_engineering_v1"] = "qaw_atam_c4_decision_engineering_v1"
    status: Literal["ready_for_review", "workshop_only", "blocked"] = "blocked"
    summary: str = ""
    quality_attribute_scenarios: list[ResearchQualityAttributeScenarioOut] = Field(default_factory=list)
    atam: ResearchATAMAssessmentOut = Field(default_factory=ResearchATAMAssessmentOut)
    adrs: list[ResearchArchitectureDecisionRecordV2Out] = Field(default_factory=list)
    c4_elements: list[ResearchC4ElementOut] = Field(default_factory=list)
    c4_views: list[ResearchC4ViewOut] = Field(default_factory=list)
    well_architected_checks: list[ResearchWellArchitectedCheckOut] = Field(default_factory=list)
    traceability_links: list[ResearchArchitectureTraceabilityLinkOut] = Field(default_factory=list)
    traceability_coverage_percent: int = 0
    orphan_component_count: int = 0
    high_risk_decision_count: int = 0
    workshop_questions: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class ResearchExecutableValidationCheckOut(BaseModel):
    check_id: str
    category: Literal[
        "api_contract",
        "representative_data_flow",
        "capacity_cost",
        "threat_model",
        "access_boundary",
        "failure_recovery",
        "observability",
        "rollback",
        "customer_confirmation",
    ]
    scenario_ids: list[str] = Field(default_factory=list)
    adr_ids: list[str] = Field(default_factory=list)
    input_spec: dict[str, Any] = Field(default_factory=dict)
    execution_method: str = ""
    command: str = ""
    owner: str = ""
    due_date: str = ""
    threshold: str = ""
    artifact_path: str = ""
    artifact_sha256: str = ""
    status: Literal["planned", "running", "passed", "failed", "human_pending", "blocked"] = "planned"
    result_summary: str = ""
    external_evidence_required: bool = False


class ResearchMinimumPrototypeOut(BaseModel):
    prototype_id: str = "minimum-vertical-solution-simulator"
    kind: Literal["vertical_simulator", "executable_prototype"] = "vertical_simulator"
    scope: str = ""
    command: str = ""
    linked_scenario_ids: list[str] = Field(default_factory=list)
    linked_adr_ids: list[str] = Field(default_factory=list)
    status: Literal["not_run", "passed", "failed"] = "not_run"
    artifact_path: str = ""
    artifact_sha256: str = ""
    result_summary: str = ""


class ResearchAcceptanceEvidenceOut(BaseModel):
    audience: Literal["customer", "internal"]
    confirmed_findings: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    disputes: list[str] = Field(default_factory=list)
    pending_validations: list[str] = Field(default_factory=list)
    artifact_paths: list[str] = Field(default_factory=list)


class ResearchProofOfArchitectureOut(BaseModel):
    framework: Literal["proof_of_architecture_v1"] = "proof_of_architecture_v1"
    status: Literal["machine_pass", "human_pending", "blocked"] = "blocked"
    summary: str = ""
    checks: list[ResearchExecutableValidationCheckOut] = Field(default_factory=list)
    prototypes: list[ResearchMinimumPrototypeOut] = Field(default_factory=list)
    customer_evidence: ResearchAcceptanceEvidenceOut = Field(
        default_factory=lambda: ResearchAcceptanceEvidenceOut(audience="customer")
    )
    internal_evidence: ResearchAcceptanceEvidenceOut = Field(
        default_factory=lambda: ResearchAcceptanceEvidenceOut(audience="internal")
    )
    scenario_test_coverage_percent: int = 0
    high_risk_decision_evidence_percent: int = 0
    blockers: list[str] = Field(default_factory=list)


class ResearchAccountPursuitCardOut(BaseModel):
    account_name: str
    account_role: str = ""
    status: Literal["verified", "market_hypothesis", "blocked"] = "blocked"
    confidence: Literal["high", "medium", "low"] = "low"
    current_signal: str = ""
    signal_kind: Literal["procurement", "owner", "policy", "unknown"] = "unknown"
    procurement_stage: Literal["intent", "tender", "award", "discovery", "unknown"] = "unknown"
    budget_signal: str = ""
    incumbent_or_partner: str = ""
    facts: list[str] = Field(default_factory=list)
    inferences: list[str] = Field(default_factory=list)
    evidence_links: list[ResearchEntityEvidenceOut] = Field(default_factory=list)
    next_proof_sources: list[str] = Field(default_factory=list)
    next_action: str = ""
    timebox: str = ""


class ResearchAccountPursuitPackOut(BaseModel):
    framework: Literal["account_pursuit_research_v1"] = "account_pursuit_research_v1"
    status: Literal["ready", "market_scan", "evidence_recovery"] = "evidence_recovery"
    summary: str = ""
    verified_account_count: int = 0
    cards: list[ResearchAccountPursuitCardOut] = Field(default_factory=list)
    market_scan_actions: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class ResearchArchitectureTraceabilityItemOut(BaseModel):
    item_id: str
    component: str = ""
    classification: Literal["fact", "assumption", "benchmark", "recommendation"] = "assumption"
    statement: str
    evidence_links: list[ResearchEntityEvidenceOut] = Field(default_factory=list)
    customer_material_allowed: bool = False
    validation_action: str = ""


class ResearchCustomerArchitectureTraceabilityOut(BaseModel):
    framework: Literal["customer_architecture_traceability_v1"] = "customer_architecture_traceability_v1"
    status: Literal["ready_for_workshop", "assumption_required", "blocked"] = "blocked"
    target_account: str = ""
    facts: list[ResearchArchitectureTraceabilityItemOut] = Field(default_factory=list)
    assumptions: list[ResearchArchitectureTraceabilityItemOut] = Field(default_factory=list)
    benchmarks: list[ResearchArchitectureTraceabilityItemOut] = Field(default_factory=list)
    recommendations: list[ResearchArchitectureTraceabilityItemOut] = Field(default_factory=list)
    current_estate_questions: list[str] = Field(default_factory=list)
    option_tradeoff_questions: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class ResearchCommercialBuyerMapEntryOut(BaseModel):
    role: str
    organization: str = ""
    status: Literal["verified", "to_verify", "unknown"] = "unknown"
    evidence_links: list[ResearchEntityEvidenceOut] = Field(default_factory=list)
    next_proof: str = ""


class ResearchCommercialBidPackOut(BaseModel):
    framework: Literal["commercial_bid_engineering_v1"] = "commercial_bid_engineering_v1"
    status: Literal["ready_for_review", "market_only", "blocked"] = "blocked"
    account_name: str = ""
    buyer_map: list[ResearchCommercialBuyerMapEntryOut] = Field(default_factory=list)
    budget_route: str = ""
    procurement_calendar: list[str] = Field(default_factory=list)
    competitor_or_incumbent_evidence: list[str] = Field(default_factory=list)
    partner_role_fit: list[str] = Field(default_factory=list)
    qualification_plan: list[str] = Field(default_factory=list)
    win_themes: list[str] = Field(default_factory=list)
    loss_risks: list[str] = Field(default_factory=list)
    no_bid_triggers: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class ResearchIndustrySkillReferenceOut(BaseModel):
    document_id: str
    title: str
    document_type: str
    document_type_label: str
    published_year: int | None = None
    excerpt: str = ""
    relevance_score: int = 0
    verification_note: str = "本地资料仅作行业参考，项目事实仍需单独核验。"


class ResearchIndustryKnowledgeBaseOut(BaseModel):
    status: Literal["ready", "partial", "unavailable", "not_built"] = "unavailable"
    generated_at: datetime | None = None
    document_count: int = 0
    full_text_document_count: int = 0
    ocr_document_count: int = 0
    ocr_pending_count: int = 0
    unsupported_count: int = 0
    passage_count: int = 0
    keyword_index_status: str = "unavailable"
    vector_index_status: str = "unavailable"
    vector_model: str = ""
    requested_vector_model: str = ""
    vector_fallback_reason: str = ""
    hybrid_search_enabled: bool = False
    warnings: list[str] = Field(default_factory=list)


class ResearchIndustryKnowledgeHitOut(BaseModel):
    passage_id: str
    document_id: str
    title: str
    document_type: str
    document_type_label: str
    industry: str
    locator: str = ""
    snippet: str = ""
    match_modes: list[Literal["keyword", "vector"]] = Field(default_factory=list)
    keyword_rank: int | None = None
    vector_rank: int | None = None
    vector_score: float = 0.0
    fused_score: float = 0.0
    verification_note: str = "本地资料内容仅作待核验行业参考，不构成项目事实或公开证据。"


class ResearchIndustryKnowledgeRetrievalStrategyOut(BaseModel):
    key: Literal["baseline_hybrid", "prefilter_weighted_hybrid", "prefilter_weighted_rerank"]
    label: str
    description: str
    default: bool = False
    lexical_prefilter: bool = False
    title_bm25_weight: float = 1.0
    rerank_enabled: bool = False
    rerank_top_k: int = 0


class ResearchIndustryKnowledgeBenchmarkCaseOut(BaseModel):
    case_id: str
    query: str
    industries: list[str] = Field(default_factory=list)
    document_types: list[str] = Field(default_factory=list)
    relevant_document_ids: list[str] = Field(default_factory=list)
    relevance_by_document_id: dict[str, int] = Field(default_factory=dict)
    expected_citation_terms: list[str] = Field(default_factory=list)
    human_review_score: float | None = None
    review_note: str = ""


class ResearchIndustryKnowledgeBenchmarkMetricOut(BaseModel):
    key: Literal["recall_at_10", "ndcg_at_10", "citation_hit_rate", "human_review_score", "latency_ms"]
    label: str
    value: float | None = None
    baseline_value: float | None = None
    delta: float | None = None
    available: bool = True
    note: str = ""


class ResearchIndustryKnowledgeBenchmarkCaseResultOut(BaseModel):
    case_id: str
    query: str
    strategy: str
    result_document_ids: list[str] = Field(default_factory=list)
    retrieved_references: list["ResearchIndustryKnowledgeBenchmarkReferenceOut"] = Field(default_factory=list)
    recall_at_10: float = 0.0
    ndcg_at_10: float = 0.0
    citation_hit_rate: float = 0.0
    human_review_score: float | None = None
    latency_ms: float = 0.0
    rerank_applied: bool = False
    rerank_backend: str = "disabled"
    rerank_model: str = ""
    review_note: str = ""


class ResearchIndustryKnowledgeBenchmarkReferenceOut(BaseModel):
    document_id: str
    title: str = ""
    locator: str = ""
    snippet: str = ""
    match_modes: list[str] = Field(default_factory=list)


class ResearchIndustryKnowledgeBenchmarkArmOut(BaseModel):
    strategy: str
    label: str
    role: Literal["baseline", "candidate"]
    case_count: int = 0
    metrics: list[ResearchIndustryKnowledgeBenchmarkMetricOut] = Field(default_factory=list)
    rerank_applied_case_count: int = 0
    rerank_backend: str = "disabled"
    rerank_model: str = ""
    cases: list[ResearchIndustryKnowledgeBenchmarkCaseResultOut] = Field(default_factory=list)


class ResearchIndustryKnowledgeBenchmarkPromotionOut(BaseModel):
    decision: Literal["promote", "hold", "block"] = "hold"
    candidate_strategy: str = ""
    reasons: list[str] = Field(default_factory=list)
    required_human_review_case_count: int = 0
    completed_human_review_case_count: int = 0


class ResearchIndustryKnowledgeBenchmarkOut(BaseModel):
    benchmark_id: str = "industry-knowledge-retrieval-ranking-ab-v1"
    dataset_version: str = ""
    dataset_sha256: str = ""
    benchmark_digest: str = ""
    generated_at: datetime
    knowledge_base_generated_at: datetime | None = None
    knowledge_base_generation_id: str = ""
    status: Literal["ready", "partial", "unavailable"] = "unavailable"
    case_count: int = 0
    strategies: list[ResearchIndustryKnowledgeRetrievalStrategyOut] = Field(default_factory=list)
    arms: list[ResearchIndustryKnowledgeBenchmarkArmOut] = Field(default_factory=list)
    promotion: ResearchIndustryKnowledgeBenchmarkPromotionOut = Field(default_factory=ResearchIndustryKnowledgeBenchmarkPromotionOut)
    artifact_path: str = ""
    review_template_path: str = ""
    review_artifact_path: str = ""
    review_sample_directory: str = ""
    warnings: list[str] = Field(default_factory=list)


class ResearchIndustryKnowledgeRetrievalAssuranceMetricOut(BaseModel):
    key: str
    label: str
    observed: str
    target: str
    status: Literal["pass", "watch", "blocked"]
    note: str = ""


class ResearchIndustryKnowledgeRetrievalAssuranceEvidenceOut(BaseModel):
    label: str
    path: str
    exists: bool = False
    status: Literal["pass", "watch", "blocked"]
    summary: str


class ResearchIndustryKnowledgeRetrievalAssuranceRoundOut(BaseModel):
    index: int
    version: str
    key: str
    title: str
    status: Literal["pass", "watch", "blocked"]
    summary: str
    metrics: list[ResearchIndustryKnowledgeRetrievalAssuranceMetricOut] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    evidence: list[ResearchIndustryKnowledgeRetrievalAssuranceEvidenceOut] = Field(default_factory=list)


class ResearchIndustryKnowledgeRetrievalAssuranceSnapshotOut(BaseModel):
    program_version: str
    generated_at: datetime
    status: Literal["pass", "watch", "blocked"]
    score: int = 0
    current_default_strategy: str
    candidate_strategy: str = ""
    promotion_decision: Literal["promote", "hold", "block"] = "hold"
    benchmark_id: str
    dataset_sha256: str = ""
    benchmark_digest: str = ""
    knowledge_base_generation_id: str = ""
    case_count: int = 0
    pass_count: int = 0
    watch_count: int = 0
    blocked_count: int = 0
    rounds: list[ResearchIndustryKnowledgeRetrievalAssuranceRoundOut] = Field(default_factory=list)
    artifacts: list[ResearchIndustryKnowledgeRetrievalAssuranceEvidenceOut] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ResearchIndustryKnowledgeRetrievalApprovalTemplateOut(BaseModel):
    schema_version: str
    benchmark_id: str
    dataset_sha256: str = ""
    knowledge_base_generation_id: str = ""
    benchmark_digest: str = ""
    candidate_strategy: str = ""
    decision: Literal["pending", "approved", "rejected"] = "pending"
    approved_by: str = ""
    approver_role: str = ""
    approved_at: str = ""
    attestation: str = ""
    separation_attestation: str = ""
    notes: str = ""
    instructions: list[str] = Field(default_factory=list)


class ResearchIndustryKnowledgeRetrievalEvidenceTemplatesOut(BaseModel):
    benchmark_id: str
    dataset_sha256: str = ""
    knowledge_base_generation_id: str = ""
    candidate_strategy: str = ""
    approval_template_path: str
    shadow_template_path: str
    drift_template_path: str
    warnings: list[str] = Field(default_factory=list)


class ResearchIndustryKnowledgeRetrievalEvidenceOperationsSnapshotOut(BaseModel):
    program_version: str
    generated_at: datetime
    status: Literal["pass", "watch", "blocked"]
    score: int = 0
    parent_program_version: str = ""
    parent_status: Literal["pass", "watch", "blocked"] = "blocked"
    current_default_strategy: str
    candidate_strategy: str = ""
    benchmark_digest: str = ""
    evidence_chain_digest: str = ""
    case_count: int = 0
    pass_count: int = 0
    watch_count: int = 0
    blocked_count: int = 0
    rounds: list[ResearchIndustryKnowledgeRetrievalAssuranceRoundOut] = Field(default_factory=list)
    artifacts: list[ResearchIndustryKnowledgeRetrievalAssuranceEvidenceOut] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ResearchIndustryKnowledgeRetrievalEvidenceOperationsTemplatesOut(BaseModel):
    program_version: str
    benchmark_digest: str = ""
    incident_register_path: str
    revocation_record_path: str
    audit_handoff_path: str
    created_paths: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    template_summaries: dict[str, str] = Field(default_factory=dict)


class ResearchIndustryKnowledgeSearchOut(ResearchIndustryKnowledgeBaseOut):
    query: str = ""
    strategy: Literal["baseline_hybrid", "prefilter_weighted_hybrid", "prefilter_weighted_rerank"] = "baseline_hybrid"
    strategy_label: str = ""
    keyword_hit_count: int = 0
    vector_hit_count: int = 0
    rerank_requested: bool = False
    rerank_applied: bool = False
    rerank_backend: str = "disabled"
    rerank_model: str = ""
    rerank_top_k: int = 0
    rerank_notes: list[str] = Field(default_factory=list)
    hits: list[ResearchIndustryKnowledgeHitOut] = Field(default_factory=list)


class ResearchIndustrySkillOut(BaseModel):
    skill_id: str
    name: str
    industry: str
    industry_label: str
    description: str = ""
    document_count: int = 0
    full_content_document_count: int = 0
    document_type_counts: dict[str, int] = Field(default_factory=dict)
    selection_reason: str = ""
    guidance: list[str] = Field(default_factory=list)
    quality_checklist: list[str] = Field(default_factory=list)
    learned_outline: list[str] = Field(default_factory=list)
    reference_highlights: list[str] = Field(default_factory=list)
    references: list[ResearchIndustrySkillReferenceOut] = Field(default_factory=list)


class ResearchIndustrySkillContextOut(BaseModel):
    status: Literal["available", "not_selected", "unavailable"] = "not_selected"
    catalog_version: str = ""
    query: str = ""
    retrieval_strategy: Literal["baseline_hybrid", "prefilter_weighted_hybrid", "prefilter_weighted_rerank"] = "baseline_hybrid"
    retrieval_strategy_label: str = ""
    rerank_applied: bool = False
    rerank_backend: str = "disabled"
    selected_skills: list[ResearchIndustrySkillOut] = Field(default_factory=list)
    source_document_count: int = 0
    guidance_summary: list[str] = Field(default_factory=list)
    knowledge_base: ResearchIndustryKnowledgeBaseOut = Field(default_factory=ResearchIndustryKnowledgeBaseOut)
    retrieval_hits: list[ResearchIndustryKnowledgeHitOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ResearchIndustrySkillLibraryOut(BaseModel):
    status: Literal["available", "unavailable"] = "unavailable"
    catalog_version: str = ""
    generated_at: datetime | None = None
    document_count: int = 0
    skill_count: int = 0
    available_industries: list[str] = Field(default_factory=list)
    knowledge_base: ResearchIndustryKnowledgeBaseOut = Field(default_factory=ResearchIndustryKnowledgeBaseOut)
    suggested_skills: list[ResearchIndustrySkillOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ResearchSolutionDeliveryPackOut(BaseModel):
    scenario: str = ""
    target_customer: str = ""
    vertical_scene: str = ""
    source_support_score: int = 0
    evidence_policy: str = ""
    industry_skill_context: ResearchIndustrySkillContextOut = Field(default_factory=ResearchIndustrySkillContextOut)
    grounding_checks: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)
    intelligence_summary: list[str] = Field(default_factory=list)
    compiled_documents: list[ResearchDeliveryCompiledDocumentOut] = Field(default_factory=list)
    quantitative_decision_model: ResearchQuantitativeDecisionModelOut = Field(
        default_factory=ResearchQuantitativeDecisionModelOut
    )
    feasibility_outline: list[ResearchSolutionOutlineSectionOut] = Field(default_factory=list)
    project_proposal_outline: list[ResearchSolutionOutlineSectionOut] = Field(default_factory=list)
    client_ppt_outline: list[ResearchSolutionOutlineSectionOut] = Field(default_factory=list)
    advisory_artifacts: list[ResearchAdvisoryArtifactOut] = Field(default_factory=list)
    evidence_ledger: ResearchDeliveryEvidenceLedgerOut = Field(default_factory=ResearchDeliveryEvidenceLedgerOut)
    semantic_challenge: ResearchDeliverySemanticChallengeOut = Field(
        default_factory=ResearchDeliverySemanticChallengeOut
    )
    solution_quality_profile: ResearchDeliveryQualityProfileOut = Field(default_factory=ResearchDeliveryQualityProfileOut)
    project_proposal_quality_profile: ResearchDeliveryQualityProfileOut = Field(
        default_factory=lambda: ResearchDeliveryQualityProfileOut(review_target="project_proposal")
    )
    architecture_readiness: ResearchSolutionArchitectureReadinessOut = Field(
        default_factory=ResearchSolutionArchitectureReadinessOut
    )
    architect_workbench: ResearchSolutionArchitectWorkbenchOut = Field(
        default_factory=ResearchSolutionArchitectWorkbenchOut
    )
    architecture_export_bundle: ResearchSolutionArchitectureExportBundleOut = Field(
        default_factory=ResearchSolutionArchitectureExportBundleOut
    )
    architecture_decision_engineering: ResearchArchitectureDecisionEngineeringOut = Field(
        default_factory=ResearchArchitectureDecisionEngineeringOut
    )
    proof_of_architecture: ResearchProofOfArchitectureOut = Field(default_factory=ResearchProofOfArchitectureOut)
    customer_architecture_traceability: ResearchCustomerArchitectureTraceabilityOut = Field(
        default_factory=ResearchCustomerArchitectureTraceabilityOut
    )
    review_checklist: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    export_markdown: str = ""


class ResearchSolutionDeliveryRequest(BaseModel):
    report: "ResearchReportResponse"
    scenario: str = Field(default="", max_length=160)
    target_customer: str = Field(default="", max_length=160)
    vertical_scene: str = Field(default="", max_length=240)
    supplemental_context: str = Field(default="", max_length=2400)
    use_industry_skills: bool = True
    industry_skill_ids: list[str] = Field(default_factory=list, max_length=8)
    industry_knowledge_retrieval_strategy: Literal[
        "baseline_hybrid", "prefilter_weighted_hybrid", "prefilter_weighted_rerank"
    ] = "baseline_hybrid"
    detail_level: Literal["outline", "review_draft", "final"] = "outline"


class ResearchIndustryKnowledgeDeliveryReviewRequest(BaseModel):
    case_id: str = Field(min_length=1, max_length=120)
    report: "ResearchReportResponse"
    scenario: str = Field(default="", max_length=160)
    target_customer: str = Field(default="", max_length=160)
    vertical_scene: str = Field(default="", max_length=240)
    supplemental_context: str = Field(default="", max_length=2400)
    use_industry_skills: bool = True
    industry_skill_ids: list[str] = Field(default_factory=list, max_length=8)


class ResearchIndustryKnowledgeDeliveryReviewArtifactOut(BaseModel):
    strategy: Literal["baseline_hybrid", "prefilter_weighted_hybrid", "prefilter_weighted_rerank"]
    strategy_label: str
    report_artifact_path: str


class ResearchIndustryKnowledgeDeliveryReviewOut(BaseModel):
    benchmark_id: str = "industry-knowledge-retrieval-ranking-ab-v1"
    case_id: str
    query: str
    source_report_title: str
    source_report_digest: str
    generated_at: datetime
    artifacts: list[ResearchIndustryKnowledgeDeliveryReviewArtifactOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ResearchQualityProfileOut(BaseModel):
    overall_score: int = 0
    status: Literal["high_value", "usable", "needs_evidence"] = "needs_evidence"
    headline: str = ""
    professional_score: int = 0
    intelligence_value_score: int = 0
    actionability_score: int = 0
    evidence_score: int = 0
    dimensions: list[ResearchQualityDimensionOut] = Field(default_factory=list)
    methodology: ResearchIndustryMethodologyOut = Field(default_factory=ResearchIndustryMethodologyOut)
    section_evidence_packs: list[ResearchSectionEvidencePackOut] = Field(default_factory=list)
    section_retrieval_packs: list[ResearchSectionRetrievalPackOut] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class ResearchReportEvaluationMetricOut(BaseModel):
    key: str
    label: str
    score: int = 0
    threshold: int = 70
    status: Literal["pass", "watch", "fail"] = "watch"
    summary: str = ""
    evidence: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    improvement_actions: list[str] = Field(default_factory=list)


class ResearchReportSelfImprovementOut(BaseModel):
    triggered: bool = False
    round_count: int = 0
    strategies: list[
        Literal[
            "expanded_search",
            "deeper_reasoning",
            "cross_source_consensus",
            "industry_analogy",
            "structured_entity_enrichment",
        ]
    ] = Field(default_factory=list)
    before_score: int = 0
    after_score: int = 0
    actions: list[str] = Field(default_factory=list)
    added_entities: list[str] = Field(default_factory=list)
    corrective_queries: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ResearchReportEvaluationProfileOut(BaseModel):
    framework: Literal["deepeval_style_custom"] = "deepeval_style_custom"
    framework_label: str = "DeepEval 风格自定义 RAG 评估"
    overall_score: int = 0
    status: Literal["pass", "watch", "fail"] = "watch"
    entity_recall_score: int = 0
    procurement_entity_recall_score: int = 0
    metrics: list[ResearchReportEvaluationMetricOut] = Field(default_factory=list)
    recalled_entities: list[str] = Field(default_factory=list)
    missing_entities: list[str] = Field(default_factory=list)
    procurement_entities: list[str] = Field(default_factory=list)
    missing_procurement_entities: list[str] = Field(default_factory=list)
    corrective_queries: list[str] = Field(default_factory=list)
    self_improvement: ResearchReportSelfImprovementOut = Field(default_factory=ResearchReportSelfImprovementOut)


class ResearchTrackingTopicReportVersionOut(BaseModel):
    id: str
    entry_id: str | None = None
    title: str
    refreshed_at: datetime
    source_count: int = 0
    evidence_density: Literal["low", "medium", "high"] = "low"
    source_quality: Literal["low", "medium", "high"] = "low"
    new_target_count: int = 0
    new_competitor_count: int = 0
    new_budget_signal_count: int = 0


class ResearchReportDocument(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    keyword: str
    research_focus: str | None = None
    followup_context: ResearchFollowupContextOut = Field(default_factory=ResearchFollowupContextOut)
    followup_diagnostics: ResearchFollowupDiagnosticsOut = Field(default_factory=ResearchFollowupDiagnosticsOut)
    output_language: OutputLanguage = "zh-CN"
    research_mode: ResearchMode = "deep"
    report_title: str
    executive_summary: str
    consulting_angle: str
    sections: list[ResearchReportSectionOut] = Field(default_factory=list)
    target_accounts: list[str] = Field(default_factory=list)
    top_target_accounts: list[ResearchRankedEntityOut] = Field(default_factory=list)
    pending_target_candidates: list[ResearchRankedEntityOut] = Field(default_factory=list)
    target_departments: list[str] = Field(default_factory=list)
    public_contact_channels: list[str] = Field(default_factory=list)
    account_team_signals: list[str] = Field(default_factory=list)
    budget_signals: list[str] = Field(default_factory=list)
    project_distribution: list[str] = Field(default_factory=list)
    strategic_directions: list[str] = Field(default_factory=list)
    tender_timeline: list[str] = Field(default_factory=list)
    leadership_focus: list[str] = Field(default_factory=list)
    ecosystem_partners: list[str] = Field(default_factory=list)
    top_ecosystem_partners: list[ResearchRankedEntityOut] = Field(default_factory=list)
    pending_partner_candidates: list[ResearchRankedEntityOut] = Field(default_factory=list)
    competitor_profiles: list[str] = Field(default_factory=list)
    top_competitors: list[ResearchRankedEntityOut] = Field(default_factory=list)
    pending_competitor_candidates: list[ResearchRankedEntityOut] = Field(default_factory=list)
    benchmark_cases: list[str] = Field(default_factory=list)
    flagship_products: list[str] = Field(default_factory=list)
    key_people: list[str] = Field(default_factory=list)
    five_year_outlook: list[str] = Field(default_factory=list)
    client_peer_moves: list[str] = Field(default_factory=list)
    winner_peer_moves: list[str] = Field(default_factory=list)
    competition_analysis: list[str] = Field(default_factory=list)
    source_count: int
    evidence_density: Literal["low", "medium", "high"] = "low"
    source_quality: Literal["low", "medium", "high"] = "low"
    query_plan: list[str] = Field(default_factory=list)
    sources: list[ResearchSourceOut] = Field(default_factory=list)
    source_diagnostics: ResearchSourceDiagnosticsOut = Field(default_factory=ResearchSourceDiagnosticsOut)
    research_scope_contract: ResearchScopeContractOut = Field(default_factory=ResearchScopeContractOut)
    research_question_tree: ResearchQuestionTreeOut = Field(default_factory=ResearchQuestionTreeOut)
    research_source_admissions: list[ResearchSourceAdmissionOut] = Field(default_factory=list)
    research_evidence_gate: ResearchEvidenceGateOut = Field(default_factory=ResearchEvidenceGateOut)
    interaction_state: ResearchInteractionState = "ready"
    clarification_packet: ResearchClarificationPacketOut = Field(default_factory=ResearchClarificationPacketOut)
    research_claim_evidence_ledger: ResearchDeliveryEvidenceLedgerOut = Field(
        default_factory=ResearchDeliveryEvidenceLedgerOut
    )
    research_citation_gate: ResearchCitationGateOut = Field(default_factory=ResearchCitationGateOut)
    research_entity_authenticity_gate: ResearchEntityAuthenticityGateOut = Field(
        default_factory=ResearchEntityAuthenticityGateOut
    )
    entity_graph: ResearchEntityGraphOut = Field(default_factory=ResearchEntityGraphOut)
    report_readiness: ResearchReportReadinessOut = Field(default_factory=ResearchReportReadinessOut)
    delivery_truth: ResearchDeliveryTruthOut = Field(default_factory=ResearchDeliveryTruthOut)
    account_pursuit_pack: ResearchAccountPursuitPackOut = Field(default_factory=ResearchAccountPursuitPackOut)
    commercial_bid_pack: ResearchCommercialBidPackOut = Field(default_factory=ResearchCommercialBidPackOut)
    commercial_summary: ResearchCommercialSummaryOut = Field(default_factory=ResearchCommercialSummaryOut)
    technical_appendix: ResearchTechnicalAppendixOut = Field(default_factory=ResearchTechnicalAppendixOut)
    review_queue: list[ResearchReviewQueueItemOut] = Field(default_factory=list)
    quality_profile: ResearchQualityProfileOut = Field(default_factory=ResearchQualityProfileOut)
    evaluation_profile: ResearchReportEvaluationProfileOut = Field(default_factory=ResearchReportEvaluationProfileOut)
    market_intelligence: ResearchMarketIntelligencePackOut = Field(default_factory=ResearchMarketIntelligencePackOut)
    solution_delivery_pack: ResearchSolutionDeliveryPackOut = Field(default_factory=ResearchSolutionDeliveryPackOut)


class ResearchReportResponse(ResearchReportDocument):
    generated_at: datetime


ResearchJobStatus = Literal["queued", "running", "succeeded", "needs_evidence", "failed"]


class ResearchJobCreateRequest(ResearchReportRequest):
    deep_research: bool | None = None

    @model_validator(mode="after")
    def sync_research_mode(self) -> "ResearchJobCreateRequest":
        if self.deep_research is not None:
            self.research_mode = "deep" if self.deep_research else "fast"
        self.deep_research = self.research_mode == "deep"
        return self


class ResearchJobOut(BaseModel):
    id: str
    status: ResearchJobStatus = "queued"
    keyword: str
    research_focus: str | None = None
    output_language: OutputLanguage = "zh-CN"
    include_wechat: bool = True
    research_mode: ResearchMode = "deep"
    max_sources: int = 14
    deep_research: bool = True
    progress_percent: int = 0
    stage_key: str = "queued"
    stage_label: str = ""
    message: str = ""
    estimated_seconds: int | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    report: ResearchReportResponse | None = None
    timeline: list["ResearchJobTimelineEventOut"] = Field(default_factory=list)
    metrics: ResearchRunMetricsOut | None = None
    interaction_state: ResearchInteractionState = "recovering"
    clarification_packet: ResearchClarificationPacketOut = Field(default_factory=ResearchClarificationPacketOut)
    parent_job_id: str | None = None
    root_job_id: str | None = None
    resumed_child_job_id: str | None = None
    recovery_attempt: int = 0
    recovery_limit: int = 3
    recovery_exhausted: bool = False
    requires_evidence_input: bool = False
    accepted_snapshot_digest: str = ""
    formal_delivery_allowed: bool = False


class ResearchJobTimelineEventOut(BaseModel):
    stage_key: str
    stage_label: str
    message: str
    progress_percent: int = 0
    created_at: datetime | str


class ResearchClarificationSubmitResponse(BaseModel):
    parent_job_id: str
    action: ResearchClarificationAction
    outcome: Literal[
        "recovery_started",
        "idempotent_replay",
        "provisional_viewed",
        "recovery_blocked",
    ] = "recovery_started"
    message: str = ""
    idempotent_replay: bool = False
    recovery_exhausted: bool = False
    requires_evidence_input: bool = False
    child_job: ResearchJobOut | None = None
    parent_job: ResearchJobOut


ResearchExperienceFeedbackReason = Literal[
    "helpful",
    "missing_sources",
    "question_unclear",
    "too_technical",
    "recovery_failed",
    "result_quality",
    "other",
]


class ResearchExperienceFeedbackRequest(BaseModel):
    score: int = Field(ge=1, le=5)
    reason: ResearchExperienceFeedbackReason = "helpful"
    comment: str = Field(default="", max_length=800)


class ResearchExperienceFeedbackOut(BaseModel):
    job_id: str
    score: int
    reason: ResearchExperienceFeedbackReason
    comment: str = ""
    recorded_at: datetime


class ResearchExperienceMetricsOut(BaseModel):
    generated_at: datetime
    sample_size: int = 0
    completed_count: int = 0
    ready_count: int = 0
    provisional_count: int = 0
    awaiting_user_count: int = 0
    system_degraded_count: int = 0
    clarification_started_count: int = 0
    clarification_resumed_count: int = 0
    clarification_recovery_count: int = 0
    clarification_conversion_rate: float = 0
    stale_recovery_count: int = 0
    idempotent_replay_count: int = 0
    median_time_to_result_seconds: int = 0
    industry_bucket_count: int = 0
    industry_distribution: dict[str, int] = Field(default_factory=dict)
    user_supplied_source_count: int = 0
    provenance_missing_count: int = 0
    formal_gate_bypass_count: int = 0
    feedback_count: int = 0
    average_feedback_score: float = 0
    too_technical_feedback_rate: float = 0
    top_feedback_reasons: list[str] = Field(default_factory=list)


class ResearchExperienceReadinessOut(BaseModel):
    generated_at: datetime
    release_version: str = "2.3.1"
    status: Literal["pass", "watch", "blocked"] = "blocked"
    score: int = 0
    sample_target: int = 120
    metrics: ResearchExperienceMetricsOut
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class ResearchAssuranceMetricOut(BaseModel):
    key: str
    label: str
    observed: str = ""
    target: str = ""
    status: Literal["pass", "watch", "blocked"] = "watch"
    summary: str = ""


class ResearchAssuranceRoundOut(BaseModel):
    index: int = Field(ge=1)
    version: str
    key: str
    label: str
    status: Literal["pass", "watch", "blocked"] = "watch"
    score: int = Field(default=0, ge=0, le=100)
    summary: str = ""
    metrics: list[ResearchAssuranceMetricOut] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class ResearchAssuranceSnapshotOut(BaseModel):
    generated_at: datetime
    program_version: str = "2.6.5"
    status: Literal["pass", "watch", "blocked"] = "blocked"
    score: int = Field(default=0, ge=0, le=100)
    report_sample_size: int = 0
    valid_report_count: int = 0
    invalid_report_count: int = 0
    rounds: list[ResearchAssuranceRoundOut] = Field(default_factory=list)
    summary_lines: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class ResearchConversationCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=160)
    topic_id: str | None = Field(default=None, max_length=64)
    job_id: str | None = Field(default=None, max_length=64)


class ResearchConversationMessageCreateRequest(BaseModel):
    content: str = Field(min_length=2, max_length=1200)


class ResearchConversationMessageOut(BaseModel):
    id: str
    conversation_id: str
    role: Literal["user", "assistant"] = "assistant"
    message_type: str = "text"
    content: str
    payload: dict = Field(default_factory=dict)
    created_at: datetime


class ResearchConversationOut(BaseModel):
    id: str
    topic_id: str | None = None
    job_id: str | None = None
    title: str
    status: str = "active"
    context_payload: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    messages: list[ResearchConversationMessageOut] = Field(default_factory=list)


class ResearchActionCardOut(BaseModel):
    action_type: str
    priority: str = "medium"
    title: str
    summary: str
    recommended_steps: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    target_persona: str = ""
    execution_window: str = ""
    deliverable: str = ""


class ResearchTrackingTopicVersionDetailOut(BaseModel):
    id: str
    topic_id: str
    entry_id: str | None = None
    title: str
    refreshed_at: datetime
    source_count: int = 0
    evidence_density: Literal["low", "medium", "high"] = "low"
    source_quality: Literal["low", "medium", "high"] = "low"
    refresh_note: str | None = None
    new_targets: list[str] = Field(default_factory=list)
    new_competitors: list[str] = Field(default_factory=list)
    new_budget_signals: list[str] = Field(default_factory=list)
    report: ResearchReportResponse | None = None
    action_cards: list[ResearchActionCardOut] = Field(default_factory=list)


class ResearchTrackingTopicTimelineEventOut(BaseModel):
    id: str
    topic_id: str
    event_type: ResearchTopicTimelineEventType
    occurred_at: datetime
    title: str
    summary: str = ""
    query: str = ""
    entry_id: str | None = None
    report_version_id: str | None = None
    linked_report_version_id: str | None = None
    linked_report_version_title: str | None = None
    linked_report_version_refreshed_at: datetime | None = None
    source_count: int = 0
    evidence_density: Literal["low", "medium", "high"] | None = None
    source_quality: Literal["low", "medium", "high"] | None = None
    new_targets: list[str] = Field(default_factory=list)
    new_competitors: list[str] = Field(default_factory=list)
    new_budget_signals: list[str] = Field(default_factory=list)
    compare_snapshot_id: str | None = None
    compare_snapshot_name: str | None = None
    markdown_archive_id: str | None = None
    markdown_archive_kind: ResearchMarkdownArchiveKind | None = None
    current_markdown_archive_id: str | None = None
    compare_markdown_archive_id: str | None = None
    row_count: int = 0
    source_entry_count: int = 0
    roles: list[ResearchCompareRole] = Field(default_factory=list)
    preview_names: list[str] = Field(default_factory=list)
    linked_report_diff_summary: list[str] = Field(default_factory=list)
    followup_title_resolution: str = ""
    followup_summary_resolution: str = ""
    followup_impacted_sections: list[str] = Field(default_factory=list)


class ResearchActionPlanRequest(BaseModel):
    report: ResearchReportDocument


class ResearchActionPlanResponse(BaseModel):
    keyword: str
    generated_at: datetime
    cards: list[ResearchActionCardOut] = Field(default_factory=list)


class ResearchActionSaveItemOut(BaseModel):
    entry_id: str
    title: str
    created_at: datetime


class ResearchActionSaveRequest(BaseModel):
    keyword: str
    cards: list[ResearchActionCardOut] = Field(default_factory=list, min_length=1, max_length=12)
    collection_name: str | None = Field(default=None, max_length=80)
    is_focus_reference: bool = False


class ResearchActionSaveResponse(BaseModel):
    created_count: int = 0
    items: list[ResearchActionSaveItemOut] = Field(default_factory=list)


class ResearchReportSaveRequest(BaseModel):
    report: ResearchReportDocument
    collection_name: str | None = Field(default=None, max_length=80)
    is_focus_reference: bool = False


class ResearchReportSaveResponse(BaseModel):
    entry_id: str
    title: str
    created_at: datetime


ResearchSourceSettingsOut.model_rebuild()
ResearchTrackingTopicOut.model_rebuild()
ResearchCompareSnapshotCreateRequest.model_rebuild()
ResearchCompareSnapshotOut.model_rebuild()
ResearchCompareSnapshotDetailOut.model_rebuild()
ResearchMarkdownArchiveCreateRequest.model_rebuild()
ResearchMarkdownArchiveOut.model_rebuild()
ResearchMarkdownArchiveDetailOut.model_rebuild()
ResearchWorkspaceOut.model_rebuild()
ResearchLowQualityReviewQueueItemOut.model_rebuild()
ResearchLowQualityReviewQueueOut.model_rebuild()
ResearchLowQualityReviewActionResponse.model_rebuild()
ResearchSectionRetrievalPackRequest.model_rebuild()
ResearchSolutionDeliveryRequest.model_rebuild()
