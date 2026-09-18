from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DDL, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, Uuid, event, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProductStrategyVisualEvidenceRevision(Base):
    """Append-only visual observations; no row represents human acceptance."""

    __tablename__ = "product_strategy_visual_evidence_revisions"
    __table_args__ = (
        UniqueConstraint("revision_key", name="uq_product_strategy_visual_revision_key"),
        UniqueConstraint("office_receipt_id", "surface_key", "capture_kind", "revision", name="uq_product_strategy_visual_revision_number"),
        Index("idx_product_strategy_visual_receipt_created", "office_receipt_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    revision_key: Mapped[str] = mapped_column(String(100), nullable=False)
    office_receipt_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("product_strategy_office_evidence_receipts.id", ondelete="RESTRICT"), nullable=False
    )
    surface_key: Mapped[str] = mapped_column(String(120), nullable=False)
    capture_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_revision_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revision_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    field_level_diff_payload: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


@event.listens_for(ProductStrategyVisualEvidenceRevision, "before_update")
@event.listens_for(ProductStrategyVisualEvidenceRevision, "before_delete")
def _reject_revision_mutation(_mapper, _connection, _target) -> None:
    raise ValueError("Visual evidence revisions are append-only.")


for _action in ("UPDATE", "DELETE"):
    event.listen(
        ProductStrategyVisualEvidenceRevision.__table__, "after_create",
        DDL(f"CREATE TRIGGER IF NOT EXISTS af_visual_no_{_action.lower()} BEFORE {_action} ON product_strategy_visual_evidence_revisions BEGIN SELECT RAISE(ABORT, 'Visual evidence revisions are append-only'); END").execute_if(dialect="sqlite"),
    )

event.listen(
    ProductStrategyVisualEvidenceRevision.__table__, "after_create",
    DDL("CREATE OR REPLACE FUNCTION af_reject_visual_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Visual evidence revisions are append-only'; END; $$").execute_if(dialect="postgresql"),
)
event.listen(
    ProductStrategyVisualEvidenceRevision.__table__, "after_create",
    DDL("CREATE TRIGGER af_visual_immutable BEFORE UPDATE OR DELETE ON product_strategy_visual_evidence_revisions FOR EACH ROW EXECUTE FUNCTION af_reject_visual_mutation()").execute_if(dialect="postgresql"),
)
