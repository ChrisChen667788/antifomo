from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


class ProductStrategyIteration(Base):
    """A versioned delivery-control record, not evidence that a feature shipped.

    The 2.10.3–2.11.7 train is intentionally persisted as a reviewable program:
    implementation work, external evidence, acceptance, execution authority and
    release authority stay separate for every iteration.
    """

    __tablename__ = "product_strategy_iterations"
    __table_args__ = (
        UniqueConstraint("iteration_key", name="uq_product_strategy_iteration_key"),
        Index("idx_product_strategy_iteration_scope_sequence", "project_scope", "sequence"),
        Index("idx_product_strategy_iteration_status", "implementation_status", "external_evidence_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    iteration_key: Mapped[str] = mapped_column(String(180), nullable=False)
    project_scope: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    workstream: Mapped[str] = mapped_column(String(120), nullable=False)
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    scope_boundary: Mapped[str] = mapped_column(Text, nullable=False)
    implementation_status: Mapped[str] = mapped_column(String(80), nullable=False)
    external_evidence_status: Mapped[str] = mapped_column(String(80), nullable=False)
    acceptance_status: Mapped[str] = mapped_column(String(80), nullable=False)
    dependencies_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_basis_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    delivery_artifacts_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    acceptance_criteria_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    external_evidence_requirements_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    can_auto_accept: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    can_auto_execute: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    can_auto_approve_release: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    requires_human_evidence_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    production_status: Mapped[str] = mapped_column(
        String(60), nullable=False, default="not_authorized", server_default="not_authorized"
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    revision_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    seed_managed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProductStrategyIterationRevision(Base):
    """Immutable initial or human-created revision snapshot for an iteration."""

    __tablename__ = "product_strategy_iteration_revisions"
    __table_args__ = (
        UniqueConstraint("iteration_id", "revision", name="uq_product_strategy_iteration_revision"),
        Index("idx_product_strategy_iteration_revision_created", "iteration_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    iteration_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_strategy_iterations.id", ondelete="CASCADE"),
        nullable=False,
    )
    iteration_key: Mapped[str] = mapped_column(String(180), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_revision_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revision_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    snapshot_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    field_level_diff_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    seed_managed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ProductStrategyIterationInitializationAudit(Base):
    """Explicit user-instruction trace for the fifteen-version control plane."""

    __tablename__ = "product_strategy_iteration_initialization_audits"
    __table_args__ = (
        UniqueConstraint("event_key", name="uq_product_strategy_iteration_initialization_event_key"),
        Index("idx_product_strategy_iteration_initialization_created", "project_scope", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    event_key: Mapped[str] = mapped_column(String(180), nullable=False)
    project_scope: Mapped[str] = mapped_column(String(120), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    instruction_evidence_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    iteration_program_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    iteration_keys_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    event_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    can_auto_accept: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    can_auto_execute: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    can_auto_approve_release: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    release_gate_mutated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
