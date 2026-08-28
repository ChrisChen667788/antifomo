from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


class ProductStrategyDecisionContextPacket(Base):
    """A project-scoped, reviewable context snapshot for one approved decision.

    ``seed_managed`` is deliberately an ownership boundary.  The initializer
    never updates an existing row; if a reviewer marks it false, subsequent
    initialization must preserve it and its revision history unchanged.
    """

    __tablename__ = "product_strategy_decision_context_packets"
    __table_args__ = (
        UniqueConstraint("packet_key", name="uq_product_strategy_context_packet_key"),
        Index("idx_product_strategy_context_packets_project_status", "project_scope", "status"),
        Index("idx_product_strategy_context_packets_card", "roadmap_card_key", "decision"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    packet_key: Mapped[str] = mapped_column(String(160), nullable=False)
    project_scope: Mapped[str] = mapped_column(String(120), nullable=False)
    roadmap_card_key: Mapped[str] = mapped_column(String(120), nullable=False)
    product_key: Mapped[str] = mapped_column(String(80), nullable=False)
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    problem_statement: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    source_catalog_keys_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_digests_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_references_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    assumptions_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    constraints_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    module_targets_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    owner_evidence_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    retention_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    revision_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(60), nullable=False, default="approved_for_context", server_default="approved_for_context"
    )
    can_auto_execute: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    can_auto_approve_release: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    requires_human_change_approval: Mapped[bool] = mapped_column(
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


class ProductStrategyDecisionContextPacketRevision(Base):
    """An append-only packet snapshot and initialization approval audit record."""

    __tablename__ = "product_strategy_decision_context_packet_revisions"
    __table_args__ = (
        UniqueConstraint("packet_id", "revision", name="uq_product_strategy_context_packet_revision"),
        Index("idx_product_strategy_context_revisions_packet_created", "packet_id", "created_at"),
        Index("idx_product_strategy_context_revisions_event", "event_type", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    packet_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_strategy_decision_context_packets.id", ondelete="CASCADE"),
        nullable=False,
    )
    packet_key: Mapped[str] = mapped_column(String(160), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_revision_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revision_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    snapshot_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    approval_evidence_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    seed_managed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ProductStrategyDecisionContextInitializationAudit(Base):
    """One explicit user-instruction authorization event for the 2.10.1 seed."""

    __tablename__ = "product_strategy_decision_context_initialization_audits"
    __table_args__ = (
        UniqueConstraint("event_key", name="uq_product_strategy_context_initialization_event_key"),
        Index("idx_product_strategy_context_initialization_created", "project_scope", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    event_key: Mapped[str] = mapped_column(String(160), nullable=False)
    project_scope: Mapped[str] = mapped_column(String(120), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    approval_evidence_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    allowed_decisions_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    excluded_card_keys_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_catalog_version: Mapped[str] = mapped_column(String(40), nullable=False)
    packet_catalog_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    event_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    can_auto_execute: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    can_auto_approve_release: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    release_gate_mutated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
