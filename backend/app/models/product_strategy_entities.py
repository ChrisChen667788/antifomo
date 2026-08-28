from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, JSON, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


class ProductStrategySource(Base):
    """Persisted, source-scoped competitor observation.

    A row is deliberately an observation rather than a product truth.  The
    initial catalog contains vendor-published material only; ``seed_managed``
    lets a human take ownership of a row without a later seed overwriting it.
    """

    __tablename__ = "product_strategy_sources"
    __table_args__ = (
        UniqueConstraint("catalog_key", name="uq_product_strategy_source_catalog_key"),
        Index("idx_product_strategy_sources_product_observed", "product_key", "observed_at"),
        Index("idx_product_strategy_sources_evidence", "evidence_tier", "evidence_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    catalog_key: Mapped[str] = mapped_column(String(120), nullable=False)
    product_key: Mapped[str] = mapped_column(String(80), nullable=False)
    vendor: Mapped[str] = mapped_column(String(160), nullable=False)
    product_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_title: Mapped[str] = mapped_column(String(240), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(60), nullable=False, default="official_product_page", server_default="official_product_page")
    source_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence_tier: Mapped[str] = mapped_column(String(40), nullable=False, default="vendor_claim", server_default="vendor_claim")
    evidence_status: Mapped[str] = mapped_column(String(60), nullable=False, default="vendor_claim_unverified", server_default="vendor_claim_unverified")
    vendor_claim: Mapped[str] = mapped_column(Text, nullable=False)
    claimed_capabilities_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    local_implementation_status: Mapped[str] = mapped_column(String(60), nullable=False, default="not_assessed", server_default="not_assessed")
    local_implementation_notes: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    local_release_status: Mapped[str] = mapped_column(String(60), nullable=False, default="not_evaluated", server_default="not_evaluated")
    local_release_notes: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    seed_managed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProductStrategyRoadmapCard(Base):
    """A human-review-only product decision hypothesis linked to a source digest."""

    __tablename__ = "product_strategy_roadmap_cards"
    __table_args__ = (
        UniqueConstraint("card_key", name="uq_product_strategy_roadmap_card_key"),
        Index("idx_product_strategy_roadmap_cards_product_status", "product_key", "status"),
        Index("idx_product_strategy_roadmap_cards_decision", "decision", "approval_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    card_key: Mapped[str] = mapped_column(String(120), nullable=False)
    product_key: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="proposed", server_default="proposed")
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    source_catalog_keys_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence_tier: Mapped[str] = mapped_column(String(40), nullable=False, default="vendor_claim", server_default="vendor_claim")
    evidence_status: Mapped[str] = mapped_column(String(60), nullable=False, default="vendor_claim_unverified", server_default="vendor_claim_unverified")
    acceptance_criteria_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    module_targets_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    approval_status: Mapped[str] = mapped_column(String(60), nullable=False, default="human_review_required", server_default="human_review_required")
    release_impact: Mapped[str] = mapped_column(String(60), nullable=False, default="none", server_default="none")
    seed_managed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
