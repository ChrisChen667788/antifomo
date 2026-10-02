from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DDL,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    event,
    func,
    inspect as sa_inspect,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


TASK_STATES = (
    "proposed",
    "planned",
    "approved",
    "running",
    "succeeded",
    "failed",
    "unknown",
    "hold",
    "cancelled",
    "reconcile_required",
)
TASK_MODES = ("ask", "plan", "agent")
TASK_ENVELOPE_FROZEN_FIELDS = (
    "request_id",
    "user_id",
    "mode",
    "capability_key",
    "context_digest",
    "plan_digest",
    "content_digest",
    "effects_digest",
    "model_profile_id",
    "budget_payload",
    "budget_digest",
    "required_scope_payload",
    "scope_digest",
    "deadline",
    "idempotency_key",
    "request_digest",
    "request_payload",
    "rollback_ref",
)


class ModelProfile(Base):
    """Immutable, versioned model routing profile."""

    __tablename__ = "model_profiles"
    __table_args__ = (
        UniqueConstraint("profile_key", "revision", name="uq_model_profiles_key_revision"),
        UniqueConstraint("profile_digest", name="uq_model_profiles_digest"),
        CheckConstraint("revision > 0", name="model_profiles_revision_positive"),
        CheckConstraint("temperature >= 0", name="model_profiles_temperature_non_negative"),
        CheckConstraint("max_tokens > 0", name="model_profiles_max_tokens_positive"),
        CheckConstraint("timeout_seconds > 0", name="model_profiles_timeout_positive"),
        CheckConstraint(
            "cost_ceiling_minor_units IS NULL OR cost_ceiling_minor_units >= 0",
            name="model_profiles_cost_non_negative",
        ),
        CheckConstraint("status IN ('active', 'inactive')", name="model_profiles_status_valid"),
        Index("idx_model_profiles_key_status", "profile_key", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_key: Mapped[str] = mapped_column(String(120), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    model_revision: Mapped[str] = mapped_column(String(160), nullable=False)
    temperature: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_ceiling_minor_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fallback_order_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    profile_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TaskEnvelope(Base):
    """Current state for a governed task proposal.

    Approval and transition history live in append-only companion tables.  No
    executor is attached in PR-A, so creating or approving an envelope cannot
    create a legacy WorkTask or send a callback.
    """

    __tablename__ = "task_envelopes"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_task_envelopes_idempotency"),
        UniqueConstraint("legacy_work_task_id", name="uq_task_envelopes_legacy_work_task"),
        CheckConstraint(
            "mode IN ('ask', 'plan', 'agent')",
            name="task_envelopes_mode_valid",
        ),
        CheckConstraint(
            "state IN ('proposed', 'planned', 'approved', 'running', 'succeeded', "
            "'failed', 'unknown', 'hold', 'cancelled', 'reconcile_required')",
            name="task_envelopes_state_valid",
        ),
        CheckConstraint("revocation_epoch >= 0", name="task_envelopes_revocation_epoch_non_negative"),
        Index("idx_task_envelopes_user_created", "user_id", "created_at"),
        Index("idx_task_envelopes_request_id", "request_id"),
        Index("idx_task_envelopes_state", "state"),
    )

    task_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[str] = mapped_column(String(160), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    capability_key: Mapped[str] = mapped_column(String(160), nullable=False)
    state: Mapped[str] = mapped_column(String(30), nullable=False, default="proposed", server_default="proposed")
    context_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    plan_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effects_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("model_profiles.id", ondelete="RESTRICT"), nullable=True
    )
    budget_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    budget_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    required_scope_payload: Mapped[list] = mapped_column(JSON, nullable=False)
    scope_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    approval_ref: Mapped[str | None] = mapped_column(String(160), nullable=True)
    rollback_ref: Mapped[str | None] = mapped_column(String(240), nullable=True)
    legacy_work_task_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("work_tasks.id", ondelete="RESTRICT"), nullable=True
    )
    revocation_epoch: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class TaskApproval(Base):
    """Immutable approval bound to exact task content, effects, scope and budget."""

    __tablename__ = "task_approvals"
    __table_args__ = (
        UniqueConstraint("approval_ref", name="uq_task_approvals_ref"),
        UniqueConstraint("approval_digest", name="uq_task_approvals_digest"),
        CheckConstraint("revocation_epoch >= 0", name="task_approvals_revocation_epoch_non_negative"),
        Index("idx_task_approvals_envelope_created", "envelope_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    approval_ref: Mapped[str] = mapped_column(String(160), nullable=False)
    envelope_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("task_envelopes.task_id", ondelete="RESTRICT"), nullable=False
    )
    plan_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    effects_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_payload: Mapped[list] = mapped_column(JSON, nullable=False)
    scope_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    budget_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    budget_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    approver: Mapped[str] = mapped_column(String(160), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revocation_epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    approval_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TaskReceipt(Base):
    """Append-only, digest-chained state transition receipt."""

    __tablename__ = "task_receipts"
    __table_args__ = (
        UniqueConstraint("receipt_key", name="uq_task_receipts_key"),
        UniqueConstraint("receipt_digest", name="uq_task_receipts_digest"),
        UniqueConstraint("envelope_id", "sequence", name="uq_task_receipts_envelope_sequence"),
        CheckConstraint("sequence > 0", name="task_receipts_sequence_positive"),
        Index("idx_task_receipts_envelope_created", "envelope_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    receipt_key: Mapped[str] = mapped_column(String(100), nullable=False)
    envelope_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("task_envelopes.task_id", ondelete="RESTRICT"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_state: Mapped[str] = mapped_column(String(30), nullable=False)
    actor: Mapped[str] = mapped_column(String(160), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    previous_receipt_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    receipt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


@event.listens_for(TaskEnvelope, "before_update")
def _reject_frozen_envelope_mutation(_mapper, _connection, target: TaskEnvelope) -> None:
    state = sa_inspect(target)
    changed = [field for field in TASK_ENVELOPE_FROZEN_FIELDS if state.attrs[field].history.has_changes()]
    if changed:
        raise ValueError(f"Task envelope frozen fields cannot change: {', '.join(changed)}")


def _reject_immutable_mutation(_mapper, _connection, target) -> None:
    raise ValueError(f"{target.__class__.__name__} rows are append-only.")


for immutable_model in (ModelProfile, TaskApproval, TaskReceipt):
    event.listen(immutable_model, "before_update", _reject_immutable_mutation)
    event.listen(immutable_model, "before_delete", _reject_immutable_mutation)


_sqlite_frozen_predicate = " OR ".join(
    f"NEW.{field} IS NOT OLD.{field}" for field in TASK_ENVELOPE_FROZEN_FIELDS
)
event.listen(
    TaskEnvelope.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER IF NOT EXISTS af_task_envelopes_frozen_fields "
        "BEFORE UPDATE ON task_envelopes FOR EACH ROW "
        f"WHEN {_sqlite_frozen_predicate} BEGIN "
        "SELECT RAISE(ABORT, 'Task envelope frozen fields cannot change'); END"
    ).execute_if(dialect="sqlite"),
)


for table_name, trigger_prefix, message in (
    ("model_profiles", "af_model_profiles", "Model profiles are append-only"),
    ("task_approvals", "af_task_approvals", "Task approvals are append-only"),
    ("task_receipts", "af_task_receipts", "Task receipts are append-only"),
):
    table = Base.metadata.tables[table_name]
    for action in ("UPDATE", "DELETE"):
        event.listen(
            table,
            "after_create",
            DDL(
                f"CREATE TRIGGER IF NOT EXISTS {trigger_prefix}_no_{action.lower()} "
                f"BEFORE {action} ON {table_name} BEGIN "
                f"SELECT RAISE(ABORT, '{message}'); END"
            ).execute_if(dialect="sqlite"),
        )
