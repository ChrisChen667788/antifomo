from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


SpaceRole = Literal["viewer", "reviewer", "editor"]
TrustStatus = Literal["unverified", "verified", "revoked", "expired"]
ClaimStatus = Literal["draft", "accepted", "rejected"]
ClaimCriticality = Literal["normal", "critical"]
FieldState = Literal["evidence", "calculated", "assumption", "missing", "not_applicable"]
ArtifactType = Literal[
    "executive_brief",
    "mind_map",
    "data_table",
    "slide_outline",
    "infographic_spec",
    "audio_script",
]


class SpaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    visibility: Literal["private", "shared"] = "private"


class MembershipUpdateRequest(BaseModel):
    member_id: str = Field(min_length=1, max_length=80)
    role: SpaceRole


class ReviewCreateRequest(BaseModel):
    target_type: str = Field(min_length=1, max_length=40)
    target_id: str = Field(min_length=1, max_length=80)
    comment: str = Field(default="", max_length=4000)


class ReviewCommentRequest(BaseModel):
    comment: str = Field(min_length=1, max_length=4000)


class ReviewDecisionRequest(BaseModel):
    decision: Literal["approved", "changes_requested", "rejected"]


class ConnectorCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    connector_type: Literal[
        "local_folder",
        "http",
        "mcp",
        "tencent_docs",
        "feishu",
        "notion",
        "microsoft365",
        "sharepoint",
    ]
    endpoint: str = Field(min_length=1, max_length=2000)
    permissions: list[str] = Field(default_factory=list, max_length=30)


class ConnectorInvokeRequest(BaseModel):
    action: Literal["list_resources", "read_resource", "search"]
    arguments: dict[str, Any] = Field(default_factory=dict)
    granted_permissions: list[str] = Field(default_factory=list, max_length=30)
    dry_run: bool = True


class NotebookCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    space_id: UUID | None = None


class SourceRevisionCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    file_name: str = Field(default="source.txt", min_length=1, max_length=240)
    mime_type: str = Field(default="text/plain", min_length=1, max_length=120)
    source_kind: str = Field(default="text", min_length=1, max_length=40)
    source_uri: str = Field(default="", max_length=4000)
    labels: list[str] = Field(default_factory=list, max_length=20)
    source_id: UUID | None = None
    content: str | None = Field(default=None, max_length=5_000_000)
    content_base64: str | None = Field(default=None, max_length=10_000_000)
    prefer_docling: bool = False

    @model_validator(mode="after")
    def validate_content(self) -> "SourceRevisionCreateRequest":
        if (self.content is None) == (self.content_base64 is None):
            raise ValueError("Provide exactly one of content or content_base64.")
        return self


class SemanticSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    included_source_ids: list[UUID] | None = Field(default=None, max_length=200)
    limit: int = Field(default=8, ge=1, le=30)
    require_semantic: bool = True
    retrieval_mode: Literal["semantic", "hybrid", "lexical"] = "semantic"


class SourceTrustUpdateRequest(BaseModel):
    trust_status: TrustStatus
    owner_label: str = Field(default="", max_length=160)
    expires_at: datetime | None = None


class ContractCreateRequest(BaseModel):
    policy_pack_id: UUID
    title: str = Field(min_length=1, max_length=240)


class ContractFieldUpdateRequest(BaseModel):
    state: FieldState
    value: Any = None
    owner: str = Field(default="", max_length=160)
    evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    note: str = Field(default="", max_length=4000)


class ContractAssumptionRequest(BaseModel):
    assumption_key: str = Field(min_length=1, max_length=120)
    statement: str = Field(min_length=1, max_length=4000)
    owner: str = Field(min_length=1, max_length=160)
    validation_action: str = Field(min_length=1, max_length=2000)


class CalculationInput(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    value: int | float | str
    source_refs: list[str] = Field(default_factory=list, max_length=100)
    assumption_ref: str = Field(default="", max_length=120)


class ContractCalculationRequest(BaseModel):
    calculation_key: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=240)
    operation: Literal["sum", "subtract", "multiply", "divide", "ratio"]
    inputs: list[CalculationInput] = Field(min_length=1, max_length=100)
    unit: str = Field(default="", max_length=80)


class ClaimCreateRequest(BaseModel):
    claim_key: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=20_000)
    criticality: ClaimCriticality = "normal"
    status: ClaimStatus = "draft"
    passage_ids: list[UUID] = Field(default_factory=list, max_length=100)
    depends_on_claim_ids: list[UUID] = Field(default_factory=list, max_length=100)
    facts: dict[str, Any] = Field(default_factory=dict)
    owner_label: str = Field(default="", max_length=160)


class SectionUpsertRequest(BaseModel):
    section_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=240)
    claim_ids: list[UUID] = Field(default_factory=list, max_length=500)
    contract_id: UUID | None = None


class SectionCompileRequest(BaseModel):
    force: bool = False
    max_workers: int = Field(default=4, ge=1, le=4)


class SkillRegisterRequest(BaseModel):
    skill_key: str = Field(min_length=1, max_length=140)
    version: str = Field(min_length=1, max_length=40)
    publisher: str = Field(min_length=1, max_length=160)
    manifest: dict[str, Any]
    license_id: str = Field(min_length=1, max_length=80)


class SkillBenchmarkRequest(BaseModel):
    score: float = Field(ge=0, le=1)
    case_count: int = Field(gt=0, le=100_000)
    evidence_ref: str = Field(min_length=1, max_length=2000)


class SkillRunRequest(BaseModel):
    notebook_id: UUID | None = None
    requested_permissions: list[str] = Field(default_factory=list, max_length=100)
    granted_permissions: list[str] = Field(default_factory=list, max_length=100)


class ArtifactGenerateRequest(BaseModel):
    artifact_type: ArtifactType
    title: str = Field(min_length=1, max_length=240)


class DataActivationRequest(BaseModel):
    notebook_name: str = Field(default="现有知识与研报", min_length=1, max_length=160)
    notebook_id: UUID | None = None
    collection_name: str | None = Field(default=None, max_length=80)
    knowledge_entry_ids: list[UUID] | None = Field(default=None, max_length=500)
    research_job_ids: list[UUID] | None = Field(default=None, max_length=500)
    include_knowledge_entries: bool = True
    include_research_jobs: bool = True
    limit: int = Field(default=500, ge=1, le=2000)

    @model_validator(mode="after")
    def validate_selection(self) -> "DataActivationRequest":
        if not self.include_knowledge_entries and not self.include_research_jobs:
            raise ValueError("At least one activation source type must be enabled.")
        return self


class ValidationRunRequest(BaseModel):
    suite_key: str = Field(min_length=1, max_length=80)
    metrics: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    reviewer_id: str = Field(default="", max_length=160)
    reviewer_role: str = Field(default="", max_length=80)
    attestation: str = Field(default="", max_length=4000)
    source_artifact_uri: str = Field(default="", max_length=4000)
    reviewed_at: datetime | None = None


class ReliabilityProbeRequest(BaseModel):
    audit_sample_limit: int = Field(default=1000, ge=1, le=10_000)
