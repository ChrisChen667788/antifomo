from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ReleaseCandidateFreezeRequest(BaseModel):
    version: str = Field(default="2.0.7", min_length=1, max_length=20)
    manifest: dict[str, Any] = Field(default_factory=dict)
    validation_run_ids: list[UUID] = Field(default_factory=list, max_length=100)
    external_attestations: dict[str, Any] = Field(default_factory=dict)


class ResearchRunCreateRequest(BaseModel):
    notebook_id: UUID
    run_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=240)
    brief: dict[str, Any] = Field(default_factory=dict)
    question_tree: list[dict[str, Any]] = Field(default_factory=list, max_length=200)
    source_decisions: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
    budget_fen: int = Field(default=0, ge=0, le=10_000_000)


class ResearchRunActionRequest(BaseModel):
    action: Literal["approve", "start", "pause", "resume", "checkpoint", "complete", "cancel"]
    expected_plan_hash: str = Field(default="", max_length=64)
    spend_fen: int = Field(default=0, ge=0, le=10_000_000)
    checkpoint: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)


class ResearchRunPlanUpdateRequest(BaseModel):
    expected_plan_hash: str = Field(min_length=64, max_length=64)
    title: str = Field(min_length=1, max_length=240)
    brief: dict[str, Any] = Field(default_factory=dict)
    question_tree: list[dict[str, Any]] = Field(min_length=1, max_length=200)
    source_decisions: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
    budget_fen: int = Field(default=0, ge=0, le=10_000_000)


class QualityBenchmarkRecordRequest(BaseModel):
    benchmark_key: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=40)
    benchmark_kind: Literal["retrieval", "parser", "model_ab", "vertical_pack"]
    incumbent: str = Field(default="", max_length=160)
    challenger: str = Field(default="", max_length=160)
    case_count: int = Field(ge=0, le=1_000_000)
    corpus_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    configuration: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    source_artifact_uri: str = Field(default="", max_length=4000)


class DocumentDraftCreateRequest(BaseModel):
    notebook_id: UUID
    contract_id: UUID | None = None
    title: str = Field(min_length=1, max_length=240)
    document_kind: str = Field(min_length=1, max_length=60)


class DocumentBlockUpdateRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    block_key: str = Field(min_length=1, max_length=120)
    title: str = Field(default="", max_length=240)
    content: str = Field(max_length=200_000)
    source_refs: list[str] = Field(default_factory=list, max_length=500)
    owner: Literal["human", "machine"] = "human"


class DocumentRegenerateRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    changed_claim_ids: list[UUID] = Field(default_factory=list, max_length=500)


class DocumentExportRequest(BaseModel):
    format: Literal["docx", "pptx"]
    brand_template: dict[str, Any] = Field(default_factory=dict)


class DocumentExportConfirmationRequest(BaseModel):
    artifact_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    reviewer_id: str = Field(min_length=1, max_length=160)
    artifact_uri: str = Field(min_length=1, max_length=4000)
    reviewed_at: datetime
    note: str = Field(min_length=20, max_length=4000)


class IdentityProfileCreateRequest(BaseModel):
    space_id: UUID
    provider_type: Literal["oidc", "saml", "microsoft_entra", "wecom"]
    name: str = Field(min_length=1, max_length=160)
    issuer_uri: str = Field(min_length=1, max_length=4000)
    client_id: str = Field(min_length=1, max_length=1000)
    tenant_key: str = Field(min_length=1, max_length=120)
    role_mapping: dict[str, str] = Field(default_factory=dict)
    allowed_domains: list[str] = Field(default_factory=list, max_length=100)
    retention_days: int = Field(default=30, ge=1, le=3650)


class ConnectorSyncRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=120)
    mode: Literal["dry_run", "apply"] = "dry_run"
    cursor_before: str = Field(default="", max_length=400)
    resources: list[dict[str, Any]] = Field(default_factory=list, max_length=10_000)
    acl_snapshot: list[dict[str, Any]] = Field(default_factory=list, max_length=10_000)


class AgentRunCreateRequest(BaseModel):
    skill_id: UUID
    notebook_id: UUID | None = None
    idempotency_key: str = Field(min_length=8, max_length=120)
    plan: dict[str, Any]
    requested_permissions: list[str] = Field(default_factory=list, max_length=100)
    granted_permissions: list[str] = Field(default_factory=list, max_length=100)
    budget_fen: int = Field(default=0, ge=0, le=10_000_000)
    scheduled_for: datetime | None = None

    @model_validator(mode="after")
    def validate_steps(self) -> "AgentRunCreateRequest":
        steps = self.plan.get("steps") if isinstance(self.plan, dict) else None
        if not isinstance(steps, list) or not steps:
            raise ValueError("Agent plan requires at least one step.")
        return self


class AgentRunActionRequest(BaseModel):
    action: Literal["start", "advance", "pause", "resume", "cancel", "rollback"]
    spend_fen: int = Field(default=0, ge=0, le=10_000_000)
    step_result: dict[str, Any] = Field(default_factory=dict)


class AgentApprovalDecisionRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str = Field(min_length=1, max_length=4000)


class VerticalPackBenchmarkRequest(BaseModel):
    task_count: int = Field(ge=0, le=1_000_000)
    expert_review_count: int = Field(ge=0, le=1_000_000)
    pass_rate: float = Field(ge=0, le=1)
    critical_error_count: int = Field(ge=0, le=1_000_000)
    artifact_uri: str = Field(default="", max_length=4000)


class CustomerPilotCreateRequest(BaseModel):
    space_id: UUID
    vertical_pack_id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    customer_label: str = Field(min_length=1, max_length=200)
    sector: str = Field(min_length=1, max_length=40)
    owner_label: str = Field(min_length=1, max_length=160)
    deployment_profile: dict[str, Any] = Field(default_factory=dict)
    sla: dict[str, Any] = Field(default_factory=dict)


class CustomerPilotUpdateRequest(BaseModel):
    action: Literal["start", "record_evidence", "request_acceptance", "reject", "signoff"]
    workflow_evidence: dict[str, Any] = Field(default_factory=dict)
    acceptance: dict[str, Any] = Field(default_factory=dict)
    customer_signer: str = Field(default="", max_length=160)
