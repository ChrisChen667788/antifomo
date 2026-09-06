from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


class ProductStrategyOfficeEvidenceReceipt(Base):
    """Immutable local evidence for one Office artifact revision.

    A receipt proves only the recorded structural and headless-render checks.
    It never represents a human acceptance decision or release approval.
    """

    __tablename__ = "product_strategy_office_evidence_receipts"
    __table_args__ = (
        UniqueConstraint("artifact_key", "file_sha256", name="uq_product_strategy_office_receipt_artifact_file"),
        UniqueConstraint("receipt_key", name="uq_product_strategy_office_receipt_key"),
        Index("idx_product_strategy_office_receipt_artifact_created", "artifact_key", "created_at"),
        Index("idx_product_strategy_office_receipt_status", "office_roundtrip_status", "visual_evidence_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    receipt_key: Mapped[str] = mapped_column(String(240), nullable=False)
    artifact_acceptance_draft_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_strategy_artifact_acceptance_drafts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    artifact_key: Mapped[str] = mapped_column(String(180), nullable=False)
    artifact_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_revision_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    file_name: Mapped[str] = mapped_column(String(240), nullable=False)
    media_type: Mapped[str] = mapped_column(String(160), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_ref: Mapped[str] = mapped_column(String(360), nullable=False)
    source_version: Mapped[str] = mapped_column(String(120), nullable=False)
    validator_version: Mapped[str] = mapped_column(String(80), nullable=False)
    structure_status: Mapped[str] = mapped_column(String(40), nullable=False)
    office_roundtrip_status: Mapped[str] = mapped_column(String(60), nullable=False)
    visual_evidence_status: Mapped[str] = mapped_column(String(60), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    rendered_pdf_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rendered_pages_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    validation_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    receipt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_level: Mapped[str] = mapped_column(
        String(60), nullable=False, default="local_runtime_evidence", server_default="local_runtime_evidence"
    )
    human_review_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="missing", server_default="missing"
    )
    acceptance_status: Mapped[str] = mapped_column(String(40), nullable=False, default="hold", server_default="hold")
    blocking_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="blocked", server_default="blocked"
    )
    can_auto_accept: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    can_auto_approve_release: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    production_status: Mapped[str] = mapped_column(
        String(60), nullable=False, default="not_authorized", server_default="not_authorized"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
