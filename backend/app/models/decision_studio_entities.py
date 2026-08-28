from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


class DecisionPolicyPack(Base):
    __tablename__ = "decision_policy_packs"
    __table_args__ = (
        UniqueConstraint("pack_key", "version", name="uq_decision_policy_pack_key_version"),
        Index("idx_decision_policy_packs_kind_status", "document_kind", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    pack_key: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    authority: Mapped[str] = mapped_column(String(160), nullable=False, default="", server_default="")
    source_uri: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    document_kind: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", server_default="active")
    schema_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class KnowledgeSpace(Base):
    __tablename__ = "decision_knowledge_spaces"
    __table_args__ = (Index("idx_decision_spaces_owner_updated", "owner_user_id", "updated_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="private", server_default="private")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class KnowledgeSpaceMembership(Base):
    __tablename__ = "decision_space_memberships"
    __table_args__ = (
        UniqueConstraint("space_id", "member_id", name="uq_decision_space_member"),
        Index("idx_decision_space_members_member", "member_id", "space_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    space_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decision_knowledge_spaces.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[str] = mapped_column(String(80), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="viewer", server_default="viewer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DecisionNotebook(Base):
    __tablename__ = "decision_notebooks"
    __table_args__ = (
        Index("idx_decision_notebooks_user_updated", "user_id", "updated_at"),
        Index("idx_decision_notebooks_space_updated", "space_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    space_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decision_knowledge_spaces.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DecisionSource(Base):
    __tablename__ = "decision_sources"
    __table_args__ = (
        Index("idx_decision_sources_notebook_updated", "notebook_id", "updated_at"),
        Index("idx_decision_sources_admission", "notebook_id", "admission_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    notebook_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decision_notebooks.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False, default="text", server_default="text")
    source_uri: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False, default="text/plain", server_default="text/plain")
    labels: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    admission_status: Mapped[str] = mapped_column(String(30), nullable=False, default="accepted", server_default="accepted")
    current_revision_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    owner_label: Mapped[str] = mapped_column(String(160), nullable=False, default="", server_default="")
    trust_status: Mapped[str] = mapped_column(String(30), nullable=False, default="unverified", server_default="unverified")
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DecisionSourceRevision(Base):
    __tablename__ = "decision_source_revisions"
    __table_args__ = (
        UniqueConstraint("source_id", "revision_number", name="uq_decision_source_revision_number"),
        Index("idx_decision_source_revisions_source_created", "source_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decision_sources.id", ondelete="CASCADE"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_name: Mapped[str] = mapped_column(String(80), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(40), nullable=False, default="1", server_default="1")
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DecisionPassage(Base):
    __tablename__ = "decision_passages"
    __table_args__ = (
        UniqueConstraint("revision_id", "sequence", name="uq_decision_passage_revision_sequence"),
        Index("idx_decision_passages_revision_sequence", "revision_id", "sequence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    revision_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decision_source_revisions.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    paragraph_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    locator_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    embedding: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    embedding_model: Mapped[str] = mapped_column(String(160), nullable=False, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DecisionDocumentContract(Base):
    __tablename__ = "decision_document_contracts"
    __table_args__ = (Index("idx_decision_contracts_notebook_updated", "notebook_id", "updated_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    notebook_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decision_notebooks.id", ondelete="CASCADE"), nullable=False
    )
    policy_pack_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decision_policy_packs.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    document_kind: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", server_default="draft")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    fields_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    assumptions_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    calculations_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    gaps_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    policy_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DecisionClaim(Base):
    __tablename__ = "decision_claims"
    __table_args__ = (
        UniqueConstraint("notebook_id", "claim_key", name="uq_decision_claim_notebook_key"),
        Index("idx_decision_claims_notebook_status", "notebook_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    notebook_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decision_notebooks.id", ondelete="CASCADE"), nullable=False
    )
    claim_key: Mapped[str] = mapped_column(String(120), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    criticality: Mapped[str] = mapped_column(String(20), nullable=False, default="normal", server_default="normal")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", server_default="draft")
    passage_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    depends_on_claim_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    facts_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    owner_label: Mapped[str] = mapped_column(String(160), nullable=False, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DecisionSection(Base):
    __tablename__ = "decision_sections"
    __table_args__ = (
        UniqueConstraint("notebook_id", "section_key", name="uq_decision_section_notebook_key"),
        Index("idx_decision_sections_notebook_status", "notebook_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    notebook_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decision_notebooks.id", ondelete="CASCADE"), nullable=False
    )
    contract_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decision_document_contracts.id", ondelete="SET NULL"), nullable=True
    )
    section_key: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="waiting", server_default="waiting")
    claim_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    dependency_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="")
    build_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    findings_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    last_built_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DecisionArtifact(Base):
    __tablename__ = "decision_artifacts"
    __table_args__ = (
        Index("idx_decision_artifacts_notebook_updated", "notebook_id", "updated_at"),
        Index("idx_decision_artifacts_status_stale", "status", "stale"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    notebook_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decision_notebooks.id", ondelete="CASCADE"), nullable=False
    )
    artifact_type: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", server_default="draft")
    content_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    source_revision_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    claim_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    dependency_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    consistency_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class KnowledgeReviewThread(Base):
    __tablename__ = "decision_review_threads"
    __table_args__ = (Index("idx_decision_reviews_space_status", "space_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    space_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decision_knowledge_spaces.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open", server_default="open")
    comments_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    decision: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", server_default="pending")
    reviewer_id: Mapped[str] = mapped_column(String(80), nullable=False, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class KnowledgeConnector(Base):
    __tablename__ = "decision_connectors"
    __table_args__ = (Index("idx_decision_connectors_space_status", "space_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    space_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decision_knowledge_spaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", server_default="draft")
    endpoint: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    permissions_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    config_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="")
    last_dry_run_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class GovernedSkill(Base):
    __tablename__ = "governed_skills"
    __table_args__ = (
        UniqueConstraint("user_id", "skill_key", "version", name="uq_governed_skill_user_key_version"),
        Index("idx_governed_skills_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    skill_key: Mapped[str] = mapped_column(String(140), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    publisher: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="quarantine", server_default="quarantine")
    manifest_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    package_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    signature: Mapped[str] = mapped_column(String(128), nullable=False, default="", server_default="")
    signature_algorithm: Mapped[str] = mapped_column(String(30), nullable=False, default="hmac-sha256", server_default="hmac-sha256")
    license_id: Mapped[str] = mapped_column(String(80), nullable=False, default="", server_default="")
    permissions_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    benchmark_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class GovernedSkillRun(Base):
    __tablename__ = "governed_skill_runs"
    __table_args__ = (Index("idx_governed_skill_runs_skill_created", "skill_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    skill_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("governed_skills.id", ondelete="CASCADE"), nullable=False
    )
    notebook_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decision_notebooks.id", ondelete="SET NULL"), nullable=True
    )
    actor_id: Mapped[str] = mapped_column(String(80), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="dry_run", server_default="dry_run")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="planned", server_default="planned")
    plan_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    requested_permissions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    granted_permissions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    result_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    violations_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class DecisionValidationRun(Base):
    __tablename__ = "decision_validation_runs"
    __table_args__ = (
        Index("idx_decision_validation_user_suite_created", "user_id", "suite_key", "created_at"),
        Index("idx_decision_validation_milestone_status", "milestone_version", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    milestone_version: Mapped[str] = mapped_column(String(20), nullable=False)
    suite_key: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence_class: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    metrics_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    findings_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    input_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(160), nullable=False, default="", server_default="")
    reviewer_role: Mapped[str] = mapped_column(String(80), nullable=False, default="", server_default="")
    attestation: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    source_artifact_uri: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
