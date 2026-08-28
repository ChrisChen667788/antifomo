from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


class DecisionReleaseCandidate(Base):
    __tablename__ = "decision_release_candidates"
    __table_args__ = (
        UniqueConstraint("user_id", "version", "build_digest", name="uq_decision_release_candidate_digest"),
        Index("idx_decision_release_candidates_user_status", "user_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="2.0.7", server_default="2.0.7")
    build_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="frozen", server_default="frozen")
    manifest_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    validation_run_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    external_attestations_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence_snapshot_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    blockers_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    frozen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DecisionResearchRun(Base):
    __tablename__ = "decision_research_runs"
    __table_args__ = (
        UniqueConstraint("user_id", "run_key", name="uq_decision_research_run_key"),
        Index("idx_decision_research_runs_notebook_status", "notebook_id", "status", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    notebook_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decision_notebooks.id", ondelete="CASCADE"), nullable=False
    )
    run_key: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", server_default="draft")
    brief_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    question_tree_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_decisions_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_snapshot_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    checkpoint_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    audit_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    plan_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="")
    budget_fen: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    spent_fen: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DecisionQualityBenchmark(Base):
    __tablename__ = "decision_quality_benchmarks"
    __table_args__ = (
        UniqueConstraint("user_id", "benchmark_key", "version", name="uq_decision_quality_benchmark_version"),
        Index("idx_decision_quality_benchmarks_kind_status", "benchmark_kind", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    benchmark_key: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    benchmark_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    incumbent: Mapped[str] = mapped_column(String(160), nullable=False, default="", server_default="")
    challenger: Mapped[str] = mapped_column(String(160), nullable=False, default="", server_default="")
    case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    corpus_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    configuration_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metrics_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    findings_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_artifact_uri: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DecisionDocumentDraft(Base):
    __tablename__ = "decision_document_drafts"
    __table_args__ = (Index("idx_decision_document_drafts_notebook_status", "notebook_id", "status", "updated_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    notebook_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decision_notebooks.id", ondelete="CASCADE"), nullable=False
    )
    contract_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decision_document_contracts.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    document_kind: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", server_default="draft")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    blocks_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    revision_history_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    dependency_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    export_profile_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_export_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class EnterpriseIdentityProfile(Base):
    __tablename__ = "decision_identity_profiles"
    __table_args__ = (
        UniqueConstraint("space_id", "provider_type", "tenant_key", name="uq_decision_identity_provider_tenant"),
        Index("idx_decision_identity_profiles_space_status", "space_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    space_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decision_knowledge_spaces.id", ondelete="CASCADE"), nullable=False
    )
    provider_type: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    issuer_uri: Mapped[str] = mapped_column(Text, nullable=False)
    client_id_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    tenant_key: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", server_default="draft")
    role_mapping_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    allowed_domains_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30, server_default="30")
    validation_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DecisionConnectorSyncRun(Base):
    __tablename__ = "decision_connector_sync_runs"
    __table_args__ = (
        UniqueConstraint("connector_id", "idempotency_key", name="uq_decision_connector_sync_idempotency"),
        Index("idx_decision_connector_sync_connector_status", "connector_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    connector_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decision_connectors.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="dry_run", server_default="dry_run")
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    cursor_before: Mapped[str] = mapped_column(String(400), nullable=False, default="", server_default="")
    cursor_after: Mapped[str] = mapped_column(String(400), nullable=False, default="", server_default="")
    resource_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    applied_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    deleted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    acl_snapshot_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    findings_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    snapshot_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DecisionAgentRun(Base):
    __tablename__ = "decision_agent_runs"
    __table_args__ = (
        UniqueConstraint("actor_id", "idempotency_key", name="uq_decision_agent_run_idempotency"),
        Index("idx_decision_agent_runs_status_schedule", "status", "scheduled_for"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    skill_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("governed_skills.id", ondelete="RESTRICT"), nullable=False
    )
    notebook_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decision_notebooks.id", ondelete="SET NULL"), nullable=True
    )
    actor_id: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="planned", server_default="planned")
    plan_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    checkpoints_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    budget_fen: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    spent_fen: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    requested_permissions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    granted_permissions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    effect_preview_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    audit_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DecisionAgentApproval(Base):
    __tablename__ = "decision_agent_approvals"
    __table_args__ = (
        UniqueConstraint("run_id", "step_key", name="uq_decision_agent_approval_step"),
        Index("idx_decision_agent_approvals_status", "status", "requested_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decision_agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    step_key: Mapped[str] = mapped_column(String(120), nullable=False)
    action_class: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", server_default="pending")
    requested_by: Mapped[str] = mapped_column(String(80), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(80), nullable=False, default="", server_default="")
    input_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_note: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class DecisionVerticalPack(Base):
    __tablename__ = "decision_vertical_packs"
    __table_args__ = (
        UniqueConstraint("pack_key", "version", name="uq_decision_vertical_pack_version"),
        Index("idx_decision_vertical_packs_sector_status", "sector", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    pack_key: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    sector: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", server_default="draft")
    source_registry_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    ontology_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    contract_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    hard_negatives_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    review_rubric_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    licensing_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    benchmark_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DecisionCustomerPilot(Base):
    __tablename__ = "decision_customer_pilots"
    __table_args__ = (Index("idx_decision_customer_pilots_space_status", "space_id", "status", "updated_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    space_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decision_knowledge_spaces.id", ondelete="CASCADE"), nullable=False
    )
    vertical_pack_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decision_vertical_packs.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_label: Mapped[str] = mapped_column(String(200), nullable=False)
    sector: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="planned", server_default="planned")
    owner_label: Mapped[str] = mapped_column(String(160), nullable=False)
    deployment_profile_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    sla_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    workflow_evidence_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    acceptance_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    customer_signer: Mapped[str] = mapped_column(String(160), nullable=False, default="", server_default="")
    signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
