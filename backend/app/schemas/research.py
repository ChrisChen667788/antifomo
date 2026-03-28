from __future__ import annotations

from datetime import datetime
from typing import Literal

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


ResearchFilterMode = Literal["all", "reports", "actions"]
ResearchPerspectiveMode = Literal["all", "regional", "client_followup", "bidding", "ecosystem"]
ResearchWatchType = Literal["topic", "company", "policy", "competitor"]


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
    created_at: datetime
    updated_at: datetime
    latest_changes: list[ResearchWatchlistChangeEventOut] = Field(default_factory=list)


class ResearchWorkspaceOut(BaseModel):
    saved_views: list[ResearchSavedViewOut] = Field(default_factory=list)
    tracking_topics: list[ResearchTrackingTopicOut] = Field(default_factory=list)


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


class ResearchSourceDiagnosticsOut(BaseModel):
    enabled_source_labels: list[str] = Field(default_factory=list)
    matched_source_labels: list[str] = Field(default_factory=list)
    scope_regions: list[str] = Field(default_factory=list)
    scope_industries: list[str] = Field(default_factory=list)
    scope_clients: list[str] = Field(default_factory=list)
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


class ResearchReportSectionOut(BaseModel):
    title: str
    items: list[str] = Field(default_factory=list)
    evidence_density: Literal["low", "medium", "high"] = "low"
    source_quality: Literal["low", "medium", "high"] = "low"
    evidence_note: str = ""


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
