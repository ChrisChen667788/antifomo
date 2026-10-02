from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
TaskState = Literal[
    "proposed",
    "planned",
    "approved",
    "running",
    "succeeded",
    "failed",
    "unknown",
    "hold",
    "cancelled",
    "reconcile_required",
]
TaskMode = Literal["ask", "plan", "agent"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TaskBudget(StrictModel):
    currency: str = Field(default="CNY", pattern=r"^[A-Z]{3}$")
    max_cost_minor_units: int | None = Field(default=None, ge=0)
    max_tokens: int | None = Field(default=None, gt=0)
    max_runtime_seconds: int | None = Field(default=None, gt=0)


class TaskEnvelopeCreateRequest(StrictModel):
    request_id: str = Field(min_length=1, max_length=160)
    mode: TaskMode
    capability_key: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9][a-z0-9._:-]*$")
    context_digest: Digest
    plan_digest: Digest | None = None
    content_digest: Digest | None = None
    effects_digest: Digest | None = None
    model_profile_id: UUID | None = None
    budget: TaskBudget
    required_scopes: list[str] = Field(default_factory=lambda: ["task:read"], min_length=1, max_length=32)
    deadline: datetime | None = None
    idempotency_key: str = Field(min_length=1, max_length=160)
    rollback_ref: str | None = Field(default=None, min_length=1, max_length=240)
    request_payload: dict = Field(default_factory=dict)

    @field_validator("required_scopes")
    @classmethod
    def validate_scopes(cls, value: list[str]) -> list[str]:
        normalized = sorted({item.strip() for item in value if item.strip()})
        if len(normalized) != len(value):
            raise ValueError("required_scopes must be non-empty and unique")
        if any(len(item) > 120 for item in normalized):
            raise ValueError("required scope is too long")
        return normalized

    @model_validator(mode="after")
    def validate_frozen_digests(self) -> "TaskEnvelopeCreateRequest":
        digests = (self.plan_digest, self.content_digest, self.effects_digest)
        if any(digests) and not all(digests):
            raise ValueError("plan_digest, content_digest and effects_digest must be supplied together")
        return self


class TaskApprovalCreateRequest(StrictModel):
    approval_ref: str = Field(min_length=1, max_length=160)
    expected_context_digest: Digest
    plan_digest: Digest
    content_digest: Digest
    effects_digest: Digest
    scope: list[str] = Field(min_length=1, max_length=32)
    budget: TaskBudget
    approver: str = Field(min_length=1, max_length=160)
    expires_at: datetime
    revocation_epoch: int = Field(ge=0)

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, value: list[str]) -> list[str]:
        normalized = sorted({item.strip() for item in value if item.strip()})
        if len(normalized) != len(value):
            raise ValueError("scope must be non-empty and unique")
        if any(len(item) > 120 for item in normalized):
            raise ValueError("approval scope is too long")
        return normalized


class TaskCancelRequest(StrictModel):
    actor: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=2000)
    expected_revocation_epoch: int = Field(ge=0)


class TaskReconcileRequest(StrictModel):
    actor: str = Field(min_length=1, max_length=160)
    resolution_state: Literal["reconcile_required", "succeeded", "failed", "hold"]
    evidence_digest: Digest
    rationale: str = Field(min_length=1, max_length=4000)


class ModelProfileCreateRequest(StrictModel):
    profile_key: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9._:-]*$")
    revision: int = Field(gt=0)
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=160)
    model_revision: str = Field(min_length=1, max_length=160)
    temperature: float = Field(ge=0, le=10)
    max_tokens: int = Field(gt=0)
    timeout_seconds: int = Field(gt=0)
    cost_ceiling_minor_units: int | None = Field(default=None, ge=0)
    fallback_order: list[str] = Field(default_factory=list, max_length=16)
    status: Literal["active", "inactive"] = "active"
    expires_at: datetime | None = None

    @field_validator("temperature")
    @classmethod
    def validate_temperature_precision(cls, value: float) -> float:
        if Decimal(str(value)).as_tuple().exponent < -3:
            raise ValueError("temperature supports at most three decimal places")
        return value


class ModelProfileOut(StrictModel):
    id: UUID
    profile_key: str
    revision: int
    provider: str
    model: str
    model_revision: str
    temperature: float
    max_tokens: int
    timeout_seconds: int
    cost_ceiling_minor_units: int | None
    fallback_order: list[str]
    status: Literal["active", "inactive"]
    expires_at: datetime | None
    profile_digest: Digest
    created_at: datetime


class TaskApprovalOut(StrictModel):
    approval_ref: str
    plan_digest: Digest
    content_digest: Digest
    effects_digest: Digest
    scope: list[str]
    budget: TaskBudget
    approver: str
    expires_at: datetime
    revocation_epoch: int
    approval_digest: Digest
    created_at: datetime
    effective: bool


class TaskReceiptOut(StrictModel):
    receipt_key: str
    sequence: int
    event_type: str
    from_state: TaskState | None
    to_state: TaskState
    actor: str
    payload: dict
    previous_receipt_digest: Digest | None
    receipt_digest: Digest
    created_at: datetime


class TaskEnvelopeOut(StrictModel):
    task_id: UUID
    request_id: str
    user_id: UUID
    mode: TaskMode
    capability_key: str
    state: TaskState
    context_digest: Digest
    plan_digest: Digest | None
    content_digest: Digest | None
    effects_digest: Digest | None
    model_profile_id: UUID | None
    budget: TaskBudget
    required_scopes: list[str]
    deadline: datetime | None
    idempotency_key: str
    approval_ref: str | None
    rollback_ref: str | None
    legacy_work_task_id: UUID | None
    revocation_epoch: int
    current_approval: TaskApprovalOut | None
    receipts: list[TaskReceiptOut]
    execution_flag_enabled: bool
    execution_available: Literal[False]
    created_at: datetime
    updated_at: datetime


class TaskEnvelopeCreateOut(StrictModel):
    outcome: Literal["created", "existing"]
    deduplicated: bool
    envelope: TaskEnvelopeOut
