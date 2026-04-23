from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.items import OutputLanguage

ResearchMode = Literal["fast", "deep"]


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


ResearchFilterMode = Literal["all", "reports", "actions"]
ResearchPerspectiveMode = Literal["all", "regional", "client_followup", "bidding", "ecosystem"]
ResearchWatchType = Literal["topic", "company", "policy", "competitor"]
ResearchCompareRole = Literal["甲方", "中标方", "竞品", "伙伴"]
ResearchCompareSnapshotDiffStatus = Literal["unavailable", "aligned", "expanded", "trimmed", "mixed"]
ResearchTopicTimelineEventType = Literal["report_version", "compare_snapshot", "markdown_archive"]
ResearchMarkdownArchiveKind = Literal["compare_markdown", "topic_version_recap", "archive_diff_recap"]


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
    key: Literal["retrieval_hit_rate", "target_support_rate", "section_quota_pass_rate"]
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


class ResearchOfflineEvaluationOut(BaseModel):
    generated_at: datetime
    total_reports: int = 0
    evaluated_reports: int = 0
    invalid_payloads: int = 0
    metrics: list[ResearchOfflineEvaluationMetricOut] = Field(default_factory=list)
    weakest_reports: list[ResearchOfflineEvaluationWeakReportOut] = Field(default_factory=list)
    summary_lines: list[str] = Field(default_factory=list)


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
    summary: str = ""
    next_due_at: datetime | None = None
    error: str | None = None


class ResearchWatchlistRunDueResponse(BaseModel):
    checked_at: datetime
    due_count: int = 0
    refreshed_count: int = 0
    failed_count: int = 0
    items: list[ResearchWatchlistRunDueItemOut] = Field(default_factory=list)


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
    candidate_profile_companies: list[str] = Field(default_factory=list)
    candidate_profile_hit_count: int = 0
    candidate_profile_official_hit_count: int = 0
    candidate_profile_source_labels: list[str] = Field(default_factory=list)
    strategy_model_used: bool = False
    strategy_scope_summary: str = ""
    strategy_query_expansion_count: int = 0
    strategy_exclusion_terms: list[str] = Field(default_factory=list)
    pipeline_summary: str = ""
    pipeline_stages: list[ResearchPipelineStageOut] = Field(default_factory=list)


class ResearchFollowupContextOut(BaseModel):
    followup_report_title: str = ""
    followup_report_summary: str = ""
    supplemental_context: str = ""
    supplemental_evidence: str = ""
    supplemental_requirements: str = ""


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
    entity_graph: ResearchEntityGraphOut = Field(default_factory=ResearchEntityGraphOut)
    report_readiness: ResearchReportReadinessOut = Field(default_factory=ResearchReportReadinessOut)
    commercial_summary: ResearchCommercialSummaryOut = Field(default_factory=ResearchCommercialSummaryOut)
    technical_appendix: ResearchTechnicalAppendixOut = Field(default_factory=ResearchTechnicalAppendixOut)
    review_queue: list[ResearchReviewQueueItemOut] = Field(default_factory=list)


class ResearchReportResponse(ResearchReportDocument):
    generated_at: datetime


ResearchJobStatus = Literal["queued", "running", "succeeded", "failed"]


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


class ResearchJobTimelineEventOut(BaseModel):
    stage_key: str
    stage_label: str
    message: str
    progress_percent: int = 0
    created_at: datetime | str


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
