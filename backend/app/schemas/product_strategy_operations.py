from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Key = Annotated[str, Field(min_length=1, max_length=160)]
Finite = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CapabilityRegistration(StrictModel):
    capability_key: Key
    model_id: Key
    model_revision: Key
    skill_digest: Digest
    tool_key: Key
    allowed_parameters: list[Key] = Field(max_length=40)
    required_parameters: list[Key] = Field(default_factory=list, max_length=40)
    allowed_hosts: list[str] = Field(default_factory=list, max_length=40)
    effect: Literal["read_only", "local_write", "external_write"]
    prohibited_actions: list[Key] = Field(default_factory=list, max_length=40)
    evaluation_digest: Digest | None = None
    observed_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_contract(self):
        if self.observed_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("Use timezone-aware observation and expiry timestamps.")
        if self.expires_at <= self.observed_at:
            raise ValueError("Expiry must follow observation.")
        if not set(self.required_parameters) <= set(self.allowed_parameters):
            raise ValueError("Required parameters must be declared in the allowlist.")
        for host in self.allowed_hosts:
            if not host or any(c in host for c in "/:*@?# "):
                raise ValueError("Declare exact hostnames, without URLs or wildcards.")
        return self


class SkillInventoryRegistration(StrictModel):
    """A source and integrity ledger for a model/skill pair; never an install request."""

    skill_key: Key
    vendor: Key
    model_id: Key
    model_revision: Key
    skill_revision: Key
    skill_digest: Digest
    source_url: str = Field(min_length=10, max_length=2000)
    source_digest: Digest
    signature_digest: Digest | None = None
    integrity_status: Literal["verified", "unverified", "failed"]
    permission_scope: list[Key] = Field(default_factory=list, max_length=40)
    prohibited_actions: list[Key] = Field(default_factory=list, max_length=40)
    risk_level: Literal["low", "medium", "high"]
    evaluation_evidence_key: Key | None = None
    observed_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_contract(self):
        source = urlsplit(self.source_url)
        if source.scheme != "https" or not source.hostname or source.username or source.password or source.fragment:
            raise ValueError("Skill source must be an HTTPS URL without credentials or fragments.")
        if self.observed_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("Use timezone-aware observation and expiry timestamps.")
        if self.expires_at <= self.observed_at:
            raise ValueError("Expiry must follow observation.")
        if self.integrity_status == "verified" and self.signature_digest is None:
            raise ValueError("Verified integrity requires a signature digest.")
        return self


class ExecutionProposal(StrictModel):
    context_packet_key: Key
    expected_context_digest: Digest
    capability_evidence_key: Key
    arguments: dict[str, str | int | float | bool | None] = Field(default_factory=dict, max_length=40)
    target_urls: list[str] = Field(default_factory=list, max_length=40)
    budget_usd: Finite
    estimated_cost_usd: Finite | None = None
    idempotency_key: Key
    rollback_plan: str = Field(min_length=10, max_length=4000)

    @field_validator("target_urls")
    @classmethod
    def public_url_shape(cls, values):
        for value in values:
            parts = urlsplit(value)
            if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.fragment:
                raise ValueError("Targets must be HTTPS URLs without credentials or fragments.")
        return values

    @field_validator("arguments")
    @classmethod
    def reject_credentials(cls, values):
        # This preview stores descriptors, not provider credentials or documents.
        for name, value in values.items():
            if any(word in name.lower() for word in ("password", "secret", "api_key", "token", "authorization")):
                raise ValueError("Credentials must not be included in an evidence proposal.")
            if len(str(value)) > 2000:
                raise ValueError("Argument values must be short descriptors.")
        return values


class PerformanceSample(StrictModel):
    latency_ms: Finite
    success: bool
    cost_usd: Finite | None = None


class PerformanceEvidence(StrictModel):
    environment_fingerprint: Digest
    source_revision: Key
    workload: Key
    provenance: Literal["local_measurement", "synthetic_fixture", "external_unverified"]
    samples: list[PerformanceSample] = Field(min_length=1, max_length=10000)
    max_p95_ms: Finite
    max_error_rate: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    max_total_cost_usd: Finite | None = None
    baseline_evidence_key: Key | None = None


class TaskFeedbackEvidence(StrictModel):
    task_key: Key
    artifact_revision_digest: Digest
    consent_reference: Key
    deidentified: Literal[True]
    source_kind: Literal["real_task_self_attested", "synthetic_fixture"]
    task_author_reference: Key
    reviewer_reference: Key
    blinded: bool
    relevance_labels: dict[Key, Annotated[int, Field(ge=0, le=3, strict=True)]] = Field(min_length=1, max_length=500)
    feedback: str = Field(min_length=10, max_length=5000)

    @model_validator(mode="after")
    def reviewer_is_independent(self):
        if self.task_author_reference.casefold() == self.reviewer_reference.casefold():
            raise ValueError("Task author and reviewer references must differ.")
        return self


class SourceChangeReview(StrictModel):
    source_url: str = Field(min_length=10, max_length=2000)
    observed_at: datetime
    previous_content_digest: Digest | None = None
    content_digest: Digest
    decision: Literal["build", "integrate", "defer", "explicitly_not_copy"]
    reviewer_reference: Key
    rationale: str = Field(min_length=20, max_length=5000)
    claim_status: Literal["vendor_claim_unverified"] = "vendor_claim_unverified"

    @model_validator(mode="after")
    def valid_source(self):
        url = urlsplit(self.source_url)
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError("Source must be an HTTPS URL without credentials.")
        if self.observed_at.tzinfo is None:
            raise ValueError("Observation requires a timezone.")
        return self


class DryRunReceiptRequest(StrictModel):
    proposal_evidence_key: Key
    expected_proposal_digest: Digest
    environment_fingerprint: Digest
    operator_reference: Key
    simulated_effects: list[Key] = Field(default_factory=list, max_length=40)
    failure_policy: Literal["block_and_review", "discard_local_snapshot"]
    idempotency_key: Key


class RollbackRehearsalRequest(StrictModel):
    proposal_evidence_key: Key
    expected_proposal_digest: Digest
    environment_fingerprint: Digest
    failure_code: Key
    recovery_action: Literal["restore_local_snapshot", "stop_and_review"]
    idempotency_key: Key


class EvidenceGateReviewRequest(StrictModel):
    gate_key: Key
    evidence_keys: list[Key] = Field(min_length=1, max_length=100)
    expected_digest: Digest
    decision: Literal["renew", "revoke", "hold"]
    reviewer_reference: Key
    rationale: str = Field(min_length=20, max_length=5000)
    expires_at: datetime
    idempotency_key: Key

    @model_validator(mode="after")
    def validate_expiry(self):
        if self.expires_at.tzinfo is None:
            raise ValueError("Expiry requires a timezone.")
        return self
