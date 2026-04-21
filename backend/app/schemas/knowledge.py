from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.research import ResearchEntityEvidenceOut


class KnowledgeMethodologyCardOut(BaseModel):
    scope_summary: str = ""
    pipeline_summary: str = ""
    query_plan: list[str] = Field(default_factory=list)
    data_boundary: str = ""
    retained_source_count: int = 0
    unique_domain_count: int = 0
    matched_source_labels: list[str] = Field(default_factory=list)
    matched_theme_labels: list[str] = Field(default_factory=list)


class KnowledgeConfidenceCardOut(BaseModel):
    level: str = "low"
    score: int = 0
    source_count: int = 0
    official_source_ratio: float = 0.0
    evidence_density: str = "low"
    source_quality: str = "low"
    reasons: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)


class KnowledgeCoverageGapOut(BaseModel):
    title: str
    severity: str = "medium"
    detail: str = ""
    recommended_action: str = ""


class KnowledgeAccountSnapshotOut(BaseModel):
    slug: str
    name: str
    role: str = "target"
    priority: str = "medium"
    confidence_score: int = 0
    summary: str = ""
    why_now: list[str] = Field(default_factory=list)
    departments: list[str] = Field(default_factory=list)
    contacts: list[str] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    benchmark_cases: list[str] = Field(default_factory=list)
    next_best_action: str = ""
    maturity_stage: str = ""
    budget_probability: int = 0
    evidence_links: list[ResearchEntityEvidenceOut] = Field(default_factory=list)


class KnowledgeOpportunityOut(BaseModel):
    title: str
    account_slug: str
    account_name: str
    stage: str = "discover"
    score: int = 0
    confidence_label: str = ""
    budget_probability: int = 0
    entry_window: str = ""
    next_best_action: str = ""
    why_now: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    benchmark_case: str = ""
    related_action_titles: list[str] = Field(default_factory=list)


class KnowledgeBenchmarkCardOut(BaseModel):
    summary: str = ""
    cases: list[str] = Field(default_factory=list)
    comparators: list[str] = Field(default_factory=list)


class KnowledgeMaturityDimensionOut(BaseModel):
    name: str
    level: str = "low"
    note: str = ""


class KnowledgeMaturityAssessmentOut(BaseModel):
    stage: str = "unknown"
    score: int = 0
    summary: str = ""
    dimensions: list[KnowledgeMaturityDimensionOut] = Field(default_factory=list)


class KnowledgeCommercialIntelligenceOut(BaseModel):
    schema_version: int = 9
    methodology: KnowledgeMethodologyCardOut = Field(default_factory=KnowledgeMethodologyCardOut)
    confidence: KnowledgeConfidenceCardOut = Field(default_factory=KnowledgeConfidenceCardOut)
    coverage_gaps: list[KnowledgeCoverageGapOut] = Field(default_factory=list)
    accounts: list[KnowledgeAccountSnapshotOut] = Field(default_factory=list)
    opportunities: list[KnowledgeOpportunityOut] = Field(default_factory=list)
    benchmark: KnowledgeBenchmarkCardOut = Field(default_factory=KnowledgeBenchmarkCardOut)
    maturity: KnowledgeMaturityAssessmentOut = Field(default_factory=KnowledgeMaturityAssessmentOut)
    why_now: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class KnowledgeLinkedEntryOut(BaseModel):
    entry_id: UUID
    title: str
    source_domain: str | None = None
    collection_name: str | None = None
    created_at: datetime


class KnowledgeAccountTimelineItemOut(BaseModel):
    id: str
    kind: str = "report"
    title: str
    summary: str = ""
    severity: str = "medium"
    created_at: datetime
    watchlist_name: str | None = None
    next_action: str = ""
    budget_probability: int = 0
    related_entry_id: UUID | None = None
    related_watchlist_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    resolution_status: str | None = None
    resolution_note: str = ""


class KnowledgeAccountPlanOut(BaseModel):
    objective: str = ""
    relationship_goal: str = ""
    value_hypothesis: str = ""
    strategic_wedges: list[str] = Field(default_factory=list)
    proof_points: list[str] = Field(default_factory=list)
    next_meeting_goal: str = ""


class KnowledgeStakeholderOut(BaseModel):
    name: str
    role: str = ""
    stance: str = "待识别"
    priority: str = "medium"
    next_move: str = ""
    evidence_links: list[ResearchEntityEvidenceOut] = Field(default_factory=list)


class KnowledgeClosePlanStepOut(BaseModel):
    title: str
    owner: str = ""
    due_window: str = ""
    exit_criteria: str = ""


class KnowledgePipelineRiskOut(BaseModel):
    title: str
    severity: str = "medium"
    detail: str = ""
    mitigation: str = ""


class KnowledgeAccountDigestOut(BaseModel):
    slug: str
    name: str
    priority: str = "medium"
    report_count: int = 0
    opportunity_count: int = 0
    confidence_score: int = 0
    budget_probability: int = 0
    maturity_stage: str = ""
    latest_signal: str = ""
    next_best_action: str = ""
    benchmark_cases: list[str] = Field(default_factory=list)
    related_entry_ids: list[UUID] = Field(default_factory=list)


class KnowledgeAccountDetailOut(KnowledgeAccountDigestOut):
    summary: str = ""
    why_now: list[str] = Field(default_factory=list)
    contacts: list[str] = Field(default_factory=list)
    departments: list[str] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    evidence_links: list[ResearchEntityEvidenceOut] = Field(default_factory=list)
    opportunities: list[KnowledgeOpportunityOut] = Field(default_factory=list)
    related_entries: list[KnowledgeLinkedEntryOut] = Field(default_factory=list)
    timeline: list[KnowledgeAccountTimelineItemOut] = Field(default_factory=list)
    account_plan: KnowledgeAccountPlanOut = Field(default_factory=KnowledgeAccountPlanOut)
    stakeholder_map: list[KnowledgeStakeholderOut] = Field(default_factory=list)
    close_plan: list[KnowledgeClosePlanStepOut] = Field(default_factory=list)
    pipeline_risks: list[KnowledgePipelineRiskOut] = Field(default_factory=list)


class KnowledgeAccountListResponse(BaseModel):
    items: list[KnowledgeAccountDigestOut] = Field(default_factory=list)


class KnowledgeOpportunityListResponse(BaseModel):
    items: list[KnowledgeOpportunityOut] = Field(default_factory=list)


class KnowledgeDashboardAlertOut(BaseModel):
    id: str
    kind: str = "watchlist"
    severity: str = "medium"
    title: str
    summary: str = ""
    account_slug: str | None = None
    account_name: str | None = None
    recommended_action: str = ""
    created_at: datetime | None = None


class KnowledgeRoleViewOut(BaseModel):
    key: str
    label: str
    summary: str = ""
    focus_items: list[str] = Field(default_factory=list)
    account_slugs: list[str] = Field(default_factory=list)
    opportunity_titles: list[str] = Field(default_factory=list)


class KnowledgeReviewQueueItemOut(BaseModel):
    id: str
    severity: str = "medium"
    title: str
    summary: str = ""
    account_slug: str | None = None
    account_name: str | None = None
    related_entry_id: UUID | None = None
    recommended_action: str = ""
    evidence_links: list[ResearchEntityEvidenceOut] = Field(default_factory=list)
    resolution_status: str = "open"
    resolution_note: str = ""
    resolved_at: datetime | None = None


class KnowledgeCommercialDashboardOut(BaseModel):
    account_count: int = 0
    opportunity_count: int = 0
    high_confidence_report_count: int = 0
    benchmark_case_count: int = 0
    top_accounts: list[KnowledgeAccountDigestOut] = Field(default_factory=list)
    top_opportunities: list[KnowledgeOpportunityOut] = Field(default_factory=list)
    top_alerts: list[KnowledgeDashboardAlertOut] = Field(default_factory=list)
    role_views: list[KnowledgeRoleViewOut] = Field(default_factory=list)
    review_queue: list[KnowledgeReviewQueueItemOut] = Field(default_factory=list)


class KnowledgeEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    item_id: UUID | None = None
    title: str
    content: str
    source_domain: str | None = None
    metadata_payload: dict | None = None
    commercial_intelligence: KnowledgeCommercialIntelligenceOut | None = None
    collection_name: str | None = None
    is_pinned: bool = False
    is_focus_reference: bool = False
    created_at: datetime
    updated_at: datetime | None = None


class KnowledgeEntryListResponse(BaseModel):
    items: list[KnowledgeEntryOut] = Field(default_factory=list)


class KnowledgeRuleOut(BaseModel):
    enabled: bool = True
    min_score_value: float = 4.0
    archive_on_like: bool = True
    archive_on_save: bool = True


class KnowledgeRuleUpdateRequest(BaseModel):
    enabled: bool | None = None
    min_score_value: float | None = Field(default=None, ge=1.0, le=5.0)
    archive_on_like: bool | None = None
    archive_on_save: bool | None = None


class KnowledgeEntryUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    content: str | None = Field(default=None, min_length=1, max_length=8000)
    collection_name: str | None = Field(default=None, max_length=80)
    is_pinned: bool | None = None
    is_focus_reference: bool | None = None
    metadata_payload: dict | None = None

    @model_validator(mode="after")
    def validate_has_any_field(self) -> "KnowledgeEntryUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self


class KnowledgeReviewQueueResolutionRequest(BaseModel):
    action: Literal["open", "resolved", "deferred"]
    note: str | None = Field(default=None, max_length=600)


class KnowledgeBatchUpdateRequest(BaseModel):
    entry_ids: list[UUID] = Field(min_length=1, max_length=24)
    collection_name: str | None = Field(default=None, max_length=80)
    is_pinned: bool | None = None
    is_focus_reference: bool | None = None

    @model_validator(mode="after")
    def validate_has_any_patch(self) -> "KnowledgeBatchUpdateRequest":
        patch_fields = {
            field_name
            for field_name in ("collection_name", "is_pinned", "is_focus_reference")
            if field_name in self.model_fields_set
        }
        if not patch_fields:
            raise ValueError("At least one patch field must be provided")
        return self


class KnowledgeMergeRequest(BaseModel):
    entry_ids: list[UUID] = Field(min_length=2, max_length=12)
    title: str | None = Field(default=None, max_length=120)
    content: str | None = Field(default=None, max_length=12000)


class KnowledgeMergePreviewRequest(BaseModel):
    entry_ids: list[UUID] = Field(min_length=1, max_length=12)
    title: str | None = Field(default=None, max_length=120)


class KnowledgeMergePreviewOut(BaseModel):
    title: str
    count: int
    titles: list[str] = Field(default_factory=list)
    more_count: int = 0
    inherit_pinned: bool = False
    inherit_focus_reference: bool = False
    inherit_collection: str | None = None
    ready: bool = False


class KnowledgeMarkdownOut(BaseModel):
    filename: str
    content: str
    entry_count: int = 1


class KnowledgeBatchMarkdownRequest(BaseModel):
    entry_ids: list[UUID] = Field(min_length=1, max_length=24)
    title: str | None = Field(default=None, max_length=120)
    output_language: str | None = Field(default=None, max_length=10)
