from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CompetitiveEvidenceOut(BaseModel):
    tier: str
    status: str
    recorded_status: str | None = None
    vendor_claim_is_not_independent_verification: Literal[True] = True


class LocalImplementationOut(BaseModel):
    status: str
    notes: str


class LocalReleaseOut(BaseModel):
    status: str
    notes: str


class CompetitiveProductOut(BaseModel):
    id: str | None = None
    catalog_key: str
    product_key: str
    vendor: str
    product_name: str
    source_title: str
    source_url: str
    source_kind: str
    source_digest: str = Field(min_length=64, max_length=64)
    observed_at: str
    expires_at: str
    evidence: CompetitiveEvidenceOut
    vendor_claim: str
    claimed_capabilities: list[str]
    local_implementation: LocalImplementationOut
    local_release: LocalReleaseOut
    seed_managed: bool = True
    created_at: str | None = None
    updated_at: str | None = None


class RoadmapDecisionCardOut(BaseModel):
    id: str | None = None
    card_key: str
    product_key: str
    title: str
    decision: Literal["build", "integrate", "defer", "explicitly_not_copy"]
    status: str
    rationale: str
    source_catalog_keys: list[str]
    source_digest: str = Field(min_length=64, max_length=64)
    observed_at: str
    expires_at: str
    evidence: CompetitiveEvidenceOut
    acceptance_criteria: list[str]
    module_targets: list[str]
    approval_status: str
    release_impact: str
    can_auto_approve_roadmap: Literal[False] = False
    can_auto_approve_release: Literal[False] = False
    seed_managed: bool = True
    created_at: str | None = None
    updated_at: str | None = None


class ProductStrategyGovernanceOut(BaseModel):
    evidence_tier: str
    evidence_status: str
    vendor_claim_is_not_independent_verification: Literal[True] = True
    can_auto_approve_roadmap: Literal[False] = False
    can_auto_approve_release: Literal[False] = False
    release_gate_mutated: Literal[False] = False
    note: str


class CompetitiveLandscapeOut(BaseModel):
    catalog_version: str
    catalog_digest: str = Field(min_length=64, max_length=64)
    observed_at: str | None = None
    expires_at: str | None = None
    read_only: bool
    initialized: bool
    persistent_snapshot_digest: str | None = Field(default=None, min_length=64, max_length=64)
    governance: ProductStrategyGovernanceOut
    products: list[CompetitiveProductOut]
    roadmap_cards: list[RoadmapDecisionCardOut]


class ProductStrategySeedCountsOut(BaseModel):
    created: int = Field(ge=0)
    updated: int = Field(ge=0)
    preserved_human: int = Field(ge=0)


class ProductStrategySeedOut(CompetitiveLandscapeOut):
    seed: dict[str, ProductStrategySeedCountsOut]


class ContextPacketEvidenceOut(BaseModel):
    tier: str
    status: str
    recorded_status: str | None = None
    vendor_claim_is_not_independent_verification: Literal[True] = True


class ContextPacketSourceReferenceOut(BaseModel):
    catalog_key: str
    source_digest: str = Field(min_length=64, max_length=64)
    observed_at: str
    expires_at: str
    evidence: ContextPacketEvidenceOut


class ContextPacketOwnerOut(BaseModel):
    kind: str
    named_individual: Literal[False] = False
    display_name: str | None = None


class ContextPacketApprovalEvidenceOut(BaseModel):
    kind: Literal["user_instruction"]
    actor_identity_status: Literal["unverified"]
    scope: Literal["product_strategy_only"]
    approval_kind: str
    owner: ContextPacketOwnerOut
    instruction: str
    recorded_at: str
    authorization_scope: str
    does_not_approve_release: Literal[True] = True
    does_not_authorize_execution: Literal[True] = True
    requires_human_change_approval: Literal[True] = True


class DecisionContextPacketRevisionOut(BaseModel):
    id: str | None = None
    packet_key: str
    revision: int = Field(ge=1)
    previous_revision_digest: str | None = Field(default=None, min_length=64, max_length=64)
    revision_digest: str = Field(min_length=64, max_length=64)
    event_type: str
    snapshot: dict[str, Any]
    approval_evidence: ContextPacketApprovalEvidenceOut
    is_immutable: Literal[True] = True
    seed_managed: bool = True
    created_at: str | None = None


class DecisionContextPacketOut(BaseModel):
    id: str | None = None
    packet_key: str
    project_scope: Literal["anti-fomo"]
    source_catalog_version: str
    packet_catalog_digest: str = Field(min_length=64, max_length=64)
    roadmap_card_key: str
    product_key: str
    decision: Literal["build", "integrate", "defer"]
    decision_approval_status: Literal["approved_by_explicit_product_owner_instruction", "human_review_required"]
    title: str
    problem_statement: str
    rationale: str
    source_catalog_keys: list[str]
    source_digests: list[str]
    source_references: list[ContextPacketSourceReferenceOut]
    assumptions: list[str]
    constraints: list[str]
    module_targets: list[str]
    approval_evidence: ContextPacketApprovalEvidenceOut
    retention_until: str
    revision: int = Field(ge=1)
    revision_digest: str = Field(min_length=64, max_length=64)
    status: Literal["approved_for_context"]
    can_auto_execute: Literal[False] = False
    can_auto_approve_release: Literal[False] = False
    requires_human_change_approval: Literal[True] = True
    production_status: Literal["not_authorized"]
    release_impact: Literal["none"]
    seed_managed: bool = True
    created_at: str | None = None
    updated_at: str | None = None
    revisions: list[DecisionContextPacketRevisionOut] = Field(default_factory=list)


class ContextPacketExcludedCardOut(BaseModel):
    card_key: str
    product_key: str
    decision: Literal["explicitly_not_copy"]
    title: str
    rationale: str
    exclusion_reason: str
    can_auto_execute: Literal[False] = False
    can_auto_approve_release: Literal[False] = False


class ContextPacketGovernanceOut(BaseModel):
    approval_kind: Literal["user_instruction"]
    actor_identity_status: Literal["unverified"]
    scope: Literal["product_strategy_only"]
    context_packets_require_explicit_initialization: Literal[True] = True
    decision_authorization_is_not_execution_authorization: Literal[True] = True
    decision_authorization_is_not_release_approval: Literal[True] = True
    can_auto_execute: Literal[False] = False
    can_auto_approve_release: Literal[False] = False
    requires_human_change_approval: Literal[True] = True
    release_gate_mutated: Literal[False] = False
    production_status: Literal["not_authorized"]
    note: str


class DecisionContextInitializationAuditOut(BaseModel):
    id: str | None = None
    event_key: str
    project_scope: Literal["anti-fomo"]
    event_type: str
    approval_evidence: ContextPacketApprovalEvidenceOut
    allowed_decisions: list[Literal["build", "integrate", "defer"]]
    excluded_card_keys: list[str]
    source_catalog_version: str
    packet_catalog_digest: str = Field(min_length=64, max_length=64)
    event_digest: str = Field(min_length=64, max_length=64)
    can_auto_execute: Literal[False] = False
    can_auto_approve_release: Literal[False] = False
    release_gate_mutated: Literal[False] = False
    created_at: str | None = None


class DecisionContextPacketLandscapeOut(BaseModel):
    context_packet_version: Literal["2.10.1"]
    source_catalog_version: str
    catalog_digest: str = Field(min_length=64, max_length=64)
    read_only: bool
    initialized: bool
    persistent_snapshot_digest: str | None = Field(default=None, min_length=64, max_length=64)
    approval_evidence: ContextPacketApprovalEvidenceOut
    governance: ContextPacketGovernanceOut
    packets: list[DecisionContextPacketOut]
    excluded_cards: list[ContextPacketExcludedCardOut]
    initialization_audit: DecisionContextInitializationAuditOut | None = None


class ContextPacketInitializationCountsOut(BaseModel):
    created: int = Field(ge=0)
    existing_seed_managed: int | None = Field(default=None, ge=0)
    preserved_human: int | None = Field(default=None, ge=0)
    existing: int | None = Field(default=None, ge=0)


class DecisionContextPacketInitializationOut(DecisionContextPacketLandscapeOut):
    initialization: dict[str, ContextPacketInitializationCountsOut]


class ArtifactAcceptanceInstructionEvidenceOut(BaseModel):
    kind: Literal["user_instruction"]
    actor_identity_status: Literal["unverified"]
    scope: Literal["artifact_acceptance_definition_only"]
    instruction: str
    recorded_at: str
    authorization_scope: str
    does_not_approve_artifact_acceptance: Literal[True] = True
    does_not_approve_release: Literal[True] = True
    does_not_authorize_execution: Literal[True] = True
    requires_human_evidence_review: Literal[True] = True


class ArtifactAcceptanceChecklistItemOut(BaseModel):
    check_key: str
    title: str
    required: Literal[True] = True
    evidence_kind: str
    evidence_status: Literal["missing", "not_recorded"]
    result: Literal["hold"]
    blocks_acceptance: Literal[True] = True
    note: str


class ArtifactAcceptanceContextPacketBindingOut(BaseModel):
    packet_key: str
    roadmap_card_key: str
    decision: Literal["build", "integrate", "defer"]
    revision: int = Field(ge=1)
    revision_digest: str = Field(min_length=64, max_length=64)
    source_catalog_version: str
    source_catalog_keys: list[str]
    source_digests: list[str]
    source_references: list[ContextPacketSourceReferenceOut]


class ArtifactAcceptanceSourceCollectionOut(BaseModel):
    office_file_processing_performed: Literal[False] = False
    visual_render_processing_performed: Literal[False] = False
    office_evidence_status: Literal["missing"]
    visual_evidence_status: Literal["missing"]
    note: str


class ArtifactAcceptanceSourceBundleOut(BaseModel):
    bundle_kind: Literal["decision_context_packet_binding"]
    decision_context_packet: ArtifactAcceptanceContextPacketBindingOut
    evidence_collection: ArtifactAcceptanceSourceCollectionOut


class ArtifactAcceptanceChangedFieldOut(BaseModel):
    field: str
    before: Any = None
    after: Any = None
    change_type: Literal["added", "removed", "modified"]


class ArtifactAcceptanceFieldLevelDiffOut(BaseModel):
    from_revision: int | None = Field(default=None, ge=1)
    to_revision: int = Field(ge=1)
    changed_fields: list[ArtifactAcceptanceChangedFieldOut]
    auto_acceptance_forbidden: Literal[True] = True
    release_gate_mutated: Literal[False] = False


class ArtifactAcceptanceRevisionOut(BaseModel):
    id: str | None = None
    artifact_key: str
    revision: int = Field(ge=1)
    previous_revision_digest: str | None = Field(default=None, min_length=64, max_length=64)
    revision_digest: str = Field(min_length=64, max_length=64)
    event_type: str
    snapshot: dict[str, Any]
    evidence_source_bundle: ArtifactAcceptanceSourceBundleOut
    evidence_source_bundle_digest: str = Field(min_length=64, max_length=64)
    field_level_diff: ArtifactAcceptanceFieldLevelDiffOut
    is_immutable: Literal[True] = True
    seed_managed: bool = True
    created_at: str | None = None


class ArtifactAcceptanceDraftOut(BaseModel):
    id: str | None = None
    artifact_key: str
    project_scope: Literal["anti-fomo"]
    artifact_acceptance_catalog_digest: str = Field(min_length=64, max_length=64)
    decision_context_packet_key: str
    roadmap_card_key: str
    decision: Literal["build", "integrate", "defer"]
    artifact_type: str
    title: str
    artifact_summary: str
    acceptance_status: Literal["hold"]
    acceptance_label: Literal["HOLD"]
    blocking_status: Literal["blocked"]
    office_evidence_status: Literal["missing"]
    visual_evidence_status: Literal["missing"]
    acceptance_checklist: list[ArtifactAcceptanceChecklistItemOut]
    evidence_source_bundle: ArtifactAcceptanceSourceBundleOut
    evidence_source_bundle_digest: str = Field(min_length=64, max_length=64)
    revision: int = Field(ge=1)
    revision_digest: str = Field(min_length=64, max_length=64)
    can_auto_accept: Literal[False] = False
    can_auto_execute: Literal[False] = False
    can_auto_approve_release: Literal[False] = False
    requires_human_evidence_review: Literal[True] = True
    production_status: Literal["not_authorized"]
    release_impact: Literal["none"]
    seed_managed: bool = True
    created_at: str | None = None
    updated_at: str | None = None
    revisions: list[ArtifactAcceptanceRevisionOut] = Field(default_factory=list)
    initial_field_level_diff: ArtifactAcceptanceFieldLevelDiffOut | None = None


class ArtifactAcceptanceGovernanceOut(BaseModel):
    instruction_kind: Literal["user_instruction"]
    actor_identity_status: Literal["unverified"]
    scope: Literal["artifact_acceptance_definition_only"]
    artifact_definitions_require_explicit_initialization: Literal[True] = True
    requires_persisted_decision_context_packets: Literal[True] = True
    missing_office_or_visual_evidence_results_in_hold: Literal[True] = True
    no_external_office_file_processing: Literal[True] = True
    no_visual_render_validation_claim: Literal[True] = True
    can_auto_accept: Literal[False] = False
    can_auto_execute: Literal[False] = False
    can_auto_approve_release: Literal[False] = False
    requires_human_evidence_review: Literal[True] = True
    release_gate_mutated: Literal[False] = False
    production_status: Literal["not_authorized"]
    note: str


class ArtifactAcceptanceContextPacketReadinessOut(BaseModel):
    required_context_packet_keys: list[str]
    missing_context_packet_keys: list[str]
    unusable_context_packet_keys: list[str]
    ready_for_explicit_initialization: bool


class ArtifactAcceptanceInitializationAuditOut(BaseModel):
    id: str | None = None
    event_key: str
    project_scope: Literal["anti-fomo"]
    event_type: str
    instruction_evidence: ArtifactAcceptanceInstructionEvidenceOut
    required_context_packet_keys: list[str]
    artifact_catalog_digest: str = Field(min_length=64, max_length=64)
    context_packet_catalog_digest: str = Field(min_length=64, max_length=64)
    event_digest: str = Field(min_length=64, max_length=64)
    can_auto_accept: Literal[False] = False
    can_auto_execute: Literal[False] = False
    can_auto_approve_release: Literal[False] = False
    release_gate_mutated: Literal[False] = False
    created_at: str | None = None


class ArtifactAcceptanceLandscapeOut(BaseModel):
    artifact_acceptance_version: Literal["2.10.2"]
    source_catalog_version: str
    catalog_digest: str = Field(min_length=64, max_length=64)
    context_packet_catalog_digest: str = Field(min_length=64, max_length=64)
    read_only: bool
    initialized: bool
    persistent_snapshot_digest: str | None = Field(default=None, min_length=64, max_length=64)
    instruction_evidence: ArtifactAcceptanceInstructionEvidenceOut
    governance: ArtifactAcceptanceGovernanceOut
    context_packet_readiness: ArtifactAcceptanceContextPacketReadinessOut | None = None
    artifacts: list[ArtifactAcceptanceDraftOut]
    initialization_audit: ArtifactAcceptanceInitializationAuditOut | None = None


class ArtifactAcceptanceInitializationCountsOut(BaseModel):
    created: int = Field(ge=0)
    existing_seed_managed: int | None = Field(default=None, ge=0)
    preserved_human: int | None = Field(default=None, ge=0)
    existing: int | None = Field(default=None, ge=0)


class ArtifactAcceptanceInitializationOut(ArtifactAcceptanceLandscapeOut):
    initialization: dict[str, ArtifactAcceptanceInitializationCountsOut]
