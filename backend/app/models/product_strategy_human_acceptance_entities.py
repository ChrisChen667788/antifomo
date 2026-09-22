from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DDL, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, Uuid, event, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProductStrategyHumanAcceptanceEvent(Base):
    """Append-only, self-attested review decisions; never release approvals."""

    __tablename__ = "product_strategy_human_acceptance_events"
    __table_args__ = (
        UniqueConstraint("event_key", name="uq_ps_acceptance_event_key"),
        UniqueConstraint("idempotency_key", name="uq_ps_acceptance_idempotency"),
        UniqueConstraint("artifact_key", "sequence", name="uq_ps_acceptance_sequence"),
        Index("idx_ps_acceptance_artifact_created", "artifact_key", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_key: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_key: Mapped[str] = mapped_column(String(180), nullable=False)
    office_receipt_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("product_strategy_office_evidence_receipts.id", ondelete="RESTRICT"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_event_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


@event.listens_for(ProductStrategyHumanAcceptanceEvent, "before_update")
@event.listens_for(ProductStrategyHumanAcceptanceEvent, "before_delete")
def _reject_event_mutation(_mapper, _connection, _target) -> None:
    raise ValueError("Human acceptance events are append-only.")


for action in ("UPDATE", "DELETE"):
    event.listen(ProductStrategyHumanAcceptanceEvent.__table__, "after_create", DDL(
        f"CREATE TRIGGER IF NOT EXISTS af_acceptance_no_{action.lower()} BEFORE {action} ON product_strategy_human_acceptance_events "
        "BEGIN SELECT RAISE(ABORT, 'Human acceptance events are append-only'); END"
    ).execute_if(dialect="sqlite"))
event.listen(ProductStrategyHumanAcceptanceEvent.__table__, "after_create", DDL(
    "CREATE OR REPLACE FUNCTION af_reject_acceptance_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ "
    "BEGIN RAISE EXCEPTION 'Human acceptance events are append-only'; END; $$"
).execute_if(dialect="postgresql"))
event.listen(ProductStrategyHumanAcceptanceEvent.__table__, "after_create", DDL(
    "CREATE TRIGGER af_acceptance_immutable BEFORE UPDATE OR DELETE ON product_strategy_human_acceptance_events "
    "FOR EACH ROW EXECUTE FUNCTION af_reject_acceptance_mutation()"
).execute_if(dialect="postgresql"))
