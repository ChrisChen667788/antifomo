from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


class ProductStrategyArtifactAcceptanceDraft(Base):
    """A review template, never a claim that its artifact was accepted.

    The row binds the 2.10.2 review template to a materialized 2.10.1
    decision-context packet.  It deliberately carries the missing-evidence
    state rather than attempting to inspect Office files or rendered visuals.
    """

    __tablename__ = "product_strategy_artifact_acceptance_drafts"
    __table_args__ = (
        UniqueConstraint("artifact_key", name="uq_product_strategy_artifact_acceptance_draft_key"),
        Index("idx_product_strategy_artifact_acceptance_project_status", "project_scope", "acceptance_status"),
        Index(
            "idx_product_strategy_artifact_acceptance_context_packet",
            "decision_context_packet_id",
            "revision",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    artifact_key: Mapped[str] = mapped_column(String(180), nullable=False)
    project_scope: Mapped[str] = mapped_column(String(120), nullable=False)
    decision_context_packet_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_strategy_decision_context_packets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    decision_context_packet_key: Mapped[str] = mapped_column(String(160), nullable=False)
    roadmap_card_key: Mapped[str] = mapped_column(String(120), nullable=False)
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    artifact_summary: Mapped[str] = mapped_column(Text, nullable=False)
    acceptance_status: Mapped[str] = mapped_column(String(40), nullable=False, default="hold", server_default="hold")
    blocking_status: Mapped[str] = mapped_column(String(40), nullable=False, default="blocked", server_default="blocked")
    office_evidence_status: Mapped[str] = mapped_column(String(40), nullable=False, default="missing", server_default="missing")
    visual_evidence_status: Mapped[str] = mapped_column(String(40), nullable=False, default="missing", server_default="missing")
    acceptance_checklist_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    evidence_source_bundle_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence_source_bundle_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    revision_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    can_auto_accept: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    can_auto_execute: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    can_auto_approve_release: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    requires_human_evidence_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    production_status: Mapped[str] = mapped_column(
        String(60), nullable=False, default="not_authorized", server_default="not_authorized"
    )
    seed_managed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProductStrategyArtifactAcceptanceRevision(Base):
    """Immutable review revision with a materialized field-level delta."""

    __tablename__ = "product_strategy_artifact_acceptance_revisions"
    __table_args__ = (
        UniqueConstraint("draft_id", "revision", name="uq_product_strategy_artifact_acceptance_revision"),
        Index("idx_product_strategy_artifact_acceptance_revisions_draft_created", "draft_id", "created_at"),
        Index("idx_product_strategy_artifact_acceptance_revisions_event", "event_type", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    draft_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_strategy_artifact_acceptance_drafts.id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact_key: Mapped[str] = mapped_column(String(180), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_revision_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revision_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    snapshot_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence_source_bundle_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence_source_bundle_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    field_level_diff_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    seed_managed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ProductStrategyArtifactAcceptanceInitializationAudit(Base):
    """Explicit initialization trace for HOLD-only 2.10.2 review templates."""

    __tablename__ = "product_strategy_artifact_acceptance_initialization_audits"
    __table_args__ = (
        UniqueConstraint("event_key", name="uq_product_strategy_artifact_acceptance_initialization_event_key"),
        Index("idx_product_strategy_artifact_acceptance_initialization_created", "project_scope", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    event_key: Mapped[str] = mapped_column(String(180), nullable=False)
    project_scope: Mapped[str] = mapped_column(String(120), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    instruction_evidence_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    required_context_packet_keys_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    artifact_catalog_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    context_packet_catalog_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    event_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    can_auto_accept: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    can_auto_execute: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    can_auto_approve_release: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    release_gate_mutated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
