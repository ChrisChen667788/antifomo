from __future__ import annotations

import unicodedata
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class HumanAcceptanceCreateRequest(StrictModel):
    idempotency_key: str = Field(min_length=1, max_length=160)
    office_receipt_key: str = Field(min_length=1, max_length=240)
    expected_office_receipt_digest: Digest
    expected_artifact_revision_digest: Digest
    visual_revision_digests: list[Digest] = Field(min_length=1, max_length=200)
    reviewer_identity: str = Field(min_length=1, max_length=160)
    author_identity: str = Field(min_length=1, max_length=160)
    decision: Literal["approve", "reject", "request_revision"]
    review_scope: str = Field(min_length=1, max_length=2000)
    rationale: str = Field(min_length=1, max_length=10000)
    previous_event_digest: Digest | None = None

    @model_validator(mode="after")
    def validate_participants(self) -> "HumanAcceptanceCreateRequest":
        normalize = lambda value: "".join(unicodedata.normalize("NFKC", value).casefold().split())
        if normalize(self.reviewer_identity) == normalize(self.author_identity):
            raise ValueError("复核人与制作者必须是不同身份；填写姓名仍只属于自述身份。")
        if len(set(self.visual_revision_digests)) != len(self.visual_revision_digests):
            raise ValueError("视觉修订摘要不能重复。")
        return self


class HumanAcceptanceEventOut(StrictModel):
    event_key: str
    idempotency_key: str
    event_digest: Digest
    sequence: int
    previous_event_digest: Digest | None
    artifact_key: str
    artifact_revision: int
    artifact_revision_digest: Digest
    office_receipt_key: str
    office_receipt_digest: Digest
    visual_revision_digests: list[Digest]
    reviewer_identity: str
    author_identity: str
    decision: Literal["approve", "reject", "request_revision"]
    review_scope: str
    rationale: str
    identity_status: Literal["self_attested"]
    separation_of_duties_status: Literal["self_attested_distinct"]
    evidence_issues: list[str]
    acceptance_status: Literal["hold"]
    blocking_status: Literal["blocked"]
    production_status: Literal["not_authorized"]
    can_auto_accept: Literal[False]
    can_auto_approve_release: Literal[False]
    release_gate_mutated: Literal[False]
    created_at: str


class HumanAcceptanceCreateOut(StrictModel):
    outcome: Literal["created", "existing"]
    deduplicated: bool
    event: HumanAcceptanceEventOut


class HumanAcceptanceLandscapeOut(StrictModel):
    human_acceptance_version: Literal["2.10.7"]
    events: list[HumanAcceptanceEventOut]
    event_count: int
    identity_status: Literal["self_attested"]
    acceptance_status: Literal["hold"]
    blocking_status: Literal["blocked"]
    note: str


class ReleaseEvidenceBridgeOut(StrictModel):
    bridge_version: Literal["2.10.8"]
    artifact_key: str
    artifact_revision: int
    artifact_revision_digest: Digest
    office_receipts: list[dict[str, Any]]
    visual_revisions: list[dict[str, Any]]
    human_events: list[dict[str, Any]]
    upstream: dict[str, Any]
    blockers: list[str]
    bridge_digest: Digest
    read_only: Literal[True]
    acceptance_status: Literal["hold"]
    blocking_status: Literal["blocked"]
    production_status: Literal["not_authorized"]
    can_auto_accept: Literal[False]
    can_auto_approve_release: Literal[False]
    release_gate_mutated: Literal[False]
