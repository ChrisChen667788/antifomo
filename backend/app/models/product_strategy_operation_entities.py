from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import DDL, DateTime, JSON, String, event, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.types import CompatibleUuid as Uuid
from app.db.base import Base


class ProductStrategyOperationEvidence(Base):
    """Immutable local observations, never execution or production authorization."""

    __tablename__ = "product_strategy_operation_evidence"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evidence_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


@event.listens_for(ProductStrategyOperationEvidence, "before_update")
@event.listens_for(ProductStrategyOperationEvidence, "before_delete")
def reject_mutation(_mapper, _connection, _target):
    raise ValueError("Operation evidence is append-only; register a new observation instead.")


for action in ("UPDATE", "DELETE"):
    event.listen(ProductStrategyOperationEvidence.__table__, "after_create", DDL(
        f"CREATE TRIGGER IF NOT EXISTS af_operations_no_{action.lower()} BEFORE {action} ON product_strategy_operation_evidence "
        "BEGIN SELECT RAISE(ABORT, 'Operation evidence is append-only'); END"
    ).execute_if(dialect="sqlite"))

event.listen(ProductStrategyOperationEvidence.__table__, "after_create", DDL(
    "CREATE OR REPLACE FUNCTION af_reject_operation_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ "
    "BEGIN RAISE EXCEPTION 'Operation evidence is append-only'; END; $$"
).execute_if(dialect="postgresql"))
event.listen(ProductStrategyOperationEvidence.__table__, "after_create", DDL(
    "CREATE TRIGGER af_operations_immutable BEFORE UPDATE OR DELETE ON product_strategy_operation_evidence "
    "FOR EACH ROW EXECUTE FUNCTION af_reject_operation_mutation()"
).execute_if(dialect="postgresql"))
