from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ReleaseReadinessGateStatus = Literal["pass", "watch", "blocked"]
ReleaseReadinessActionPriority = Literal["high", "medium", "low"]

InternalSkillStage = Literal["production", "internal_candidate", "third_party_test_package"]
InternalSkillEvaluationStatus = Literal["passed", "in_progress", "not_evaluated", "blocked"]
InternalSkillDataBoundary = Literal["local_only", "local_app", "external_optional", "external_blocked"]
InternalSkillExternalApiStatus = Literal["none", "optional_disabled", "blocked_until_review"]
InternalSkillSecretStatus = Literal["not_required", "required_for_optional_external_api", "blocked_until_review"]
ModelRouteStatus = Literal["configured", "fallback", "disabled", "local", "external"]
ModelScanStatus = Literal["ready", "partial", "blocked"]
ModelScanRouteStatus = Literal["ready", "skipped", "blocked"]
ModelUpgradeStatus = Literal["applied", "no_change", "blocked"]


class ReleaseReadinessEvidenceOut(BaseModel):
    label: str
    status: ReleaseReadinessGateStatus
    summary: str
    source: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class ReleaseReadinessActionOut(BaseModel):
    priority: ReleaseReadinessActionPriority
    owner: str
    action: str
    reason: str
    gate_key: str = ""
    gate_label: str = ""


class ReleaseReadinessOperatorCommandOut(BaseModel):
    gate_key: str
    gate_label: str
    label: str
    command: str
    purpose: str


class ReleaseReadinessArtifactOut(BaseModel):
    gate_key: str
    gate_label: str
    label: str
    path: str
    exists: bool = False
    status: ReleaseReadinessGateStatus
    summary: str


class ReleaseReadinessGateOut(BaseModel):
    key: str
    label: str
    status: ReleaseReadinessGateStatus
    score: int = 0
    target: str
    observed: str
    summary: str
    evidence: list[ReleaseReadinessEvidenceOut] = Field(default_factory=list)
    actions: list[ReleaseReadinessActionOut] = Field(default_factory=list)


class ReleaseReadinessSnapshotOut(BaseModel):
    generated_at: datetime
    release_version: str
    overall_status: ReleaseReadinessGateStatus
    readiness_score: int = 0
    summary_lines: list[str] = Field(default_factory=list)
    gates: list[ReleaseReadinessGateOut] = Field(default_factory=list)
    next_actions: list[ReleaseReadinessActionOut] = Field(default_factory=list)
    operator_commands: list[ReleaseReadinessOperatorCommandOut] = Field(default_factory=list)
    artifacts: list[ReleaseReadinessArtifactOut] = Field(default_factory=list)


class InternalSkillDependencyOut(BaseModel):
    name: str
    dependency_type: str
    optional: bool = False
    license: str = "internal"


class InternalSkillRegressionSuiteOut(BaseModel):
    path: str
    gate: str
    cadence: str


class InternalSkillVersionHistoryOut(BaseModel):
    version: str
    released_at: str
    change_summary: str
    rollback: str


class InternalSkillRegistryEntryOut(BaseModel):
    skill_id: str
    name: str
    version: str
    stage: InternalSkillStage
    evaluation_status: InternalSkillEvaluationStatus
    owner: str
    license: str
    data_boundary: InternalSkillDataBoundary
    external_api_status: InternalSkillExternalApiStatus
    secret_status: InternalSkillSecretStatus
    default_enabled: bool
    default_generation_enabled: bool
    admission_reason: str
    dependencies: list[InternalSkillDependencyOut] = Field(default_factory=list)
    regression_suites: list[InternalSkillRegressionSuiteOut] = Field(default_factory=list)
    applicable_documents: list[str] = Field(default_factory=list)
    baselines: list[str] = Field(default_factory=list)
    version_history: list[InternalSkillVersionHistoryOut] = Field(default_factory=list)
    rollback: str
    notes: str = ""


class InternalSkillGovernanceSummaryOut(BaseModel):
    total_skills: int
    production_skills: int
    evaluated_skills: int
    default_chain_skills: int
    blocked_from_default_chain: int
    external_api_skills: int
    secret_required_skills: int
    data_egress_modes: list[str] = Field(default_factory=list)


class InternalSkillRuntimeDiagnosticsOut(BaseModel):
    generated_at: str
    default_chain_blocking_enforced: bool
    unreviewed_default_chain_count: int
    external_api_status_visible: bool
    secret_status_visible: bool
    data_egress_status_visible: bool
    secret_values_exposed: bool
    external_api_skill_ids: list[str] = Field(default_factory=list)
    secret_bound_skill_ids: list[str] = Field(default_factory=list)
    data_egress_modes: list[str] = Field(default_factory=list)


class InternalSkillGovernanceSnapshotOut(BaseModel):
    registry_version: str
    summary: InternalSkillGovernanceSummaryOut
    diagnostics: InternalSkillRuntimeDiagnosticsOut
    default_chain_skill_ids: list[str] = Field(default_factory=list)
    blocked_from_default_chain_skill_ids: list[str] = Field(default_factory=list)
    entries: list[InternalSkillRegistryEntryOut] = Field(default_factory=list)


class ModelRuntimeRouteOut(BaseModel):
    key: str
    label: str
    provider: str
    effective_provider: str
    model: str | None = None
    base_url: str | None = None
    strategy: str
    fallback: str
    status: ModelRouteStatus
    upgrade_managed: bool = False


class ModuleModelBindingOut(BaseModel):
    key: str
    label: str
    area: str
    route_key: str | None = None
    provider: str
    model: str | None = None
    strategy: str
    fallback: str
    status: ModelRouteStatus
    upgrade_managed: bool = False


class ModelControlPlaneSnapshotOut(BaseModel):
    generated_at: datetime
    policy_version: str
    routes: list[ModelRuntimeRouteOut] = Field(default_factory=list)
    modules: list[ModuleModelBindingOut] = Field(default_factory=list)


class SupportedModelOut(BaseModel):
    id: str
    owned_by: str = ""
    created: int | None = None
    routes: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    excluded: bool = False
    exclusion_reason: str = ""
    scores: dict[str, int] = Field(default_factory=dict)
    rank_reason: str = ""


class ModelScanRouteOut(BaseModel):
    route_key: str
    label: str
    provider: str
    base_url: str | None = None
    status: ModelScanRouteStatus
    model_count: int = 0
    models: list[str] = Field(default_factory=list)
    error_code: str = ""
    message: str = ""


class ModelRecommendationOut(BaseModel):
    role: Literal["generation", "strategy", "vision"]
    route_key: str
    model: str
    current_model: str | None = None
    change_required: bool = False
    score: int = 0
    reason: str = ""


class SupportedModelScanOut(BaseModel):
    generated_at: datetime
    policy_version: str
    status: ModelScanStatus
    total_discovered: int = 0
    routes: list[ModelScanRouteOut] = Field(default_factory=list)
    models: list[SupportedModelOut] = Field(default_factory=list)
    recommendations: list[ModelRecommendationOut] = Field(default_factory=list)
    message: str = ""


class StrongestModelUpgradeOut(BaseModel):
    generated_at: datetime
    status: ModelUpgradeStatus
    previous_models: dict[str, str | None] = Field(default_factory=dict)
    applied_models: dict[str, str | None] = Field(default_factory=dict)
    changed_fields: list[str] = Field(default_factory=list)
    persisted: bool = False
    runtime_reloaded: bool = False
    message: str = ""
    scan: SupportedModelScanOut
