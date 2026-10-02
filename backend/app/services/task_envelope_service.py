from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.task_envelope_entities import ModelProfile, TaskApproval, TaskEnvelope, TaskReceipt
from app.schemas.task_envelopes import (
    ModelProfileCreateRequest,
    TaskApprovalCreateRequest,
    TaskCancelRequest,
    TaskEnvelopeCreateRequest,
    TaskReconcileRequest,
)
from app.services.product_strategy.catalog import canonical_digest


class TaskEnvelopeError(ValueError):
    def __init__(self, code: str, message: str, *, status_code: int = 409):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _json_payload(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _profile_snapshot(request: ModelProfileCreateRequest) -> dict[str, Any]:
    return {
        "profile_key": request.profile_key,
        "revision": request.revision,
        "provider": request.provider,
        "model": request.model,
        "model_revision": request.model_revision,
        "temperature": float(request.temperature),
        "max_tokens": request.max_tokens,
        "timeout_seconds": request.timeout_seconds,
        "cost_ceiling_minor_units": request.cost_ceiling_minor_units,
        "fallback_order": list(request.fallback_order),
        "status": request.status,
        "expires_at": _utc(request.expires_at).isoformat() if request.expires_at else None,
    }


def create_model_profile(db: Session, request: ModelProfileCreateRequest) -> tuple[str, ModelProfile]:
    snapshot = _profile_snapshot(request)
    digest = canonical_digest(snapshot)
    existing = db.scalar(
        select(ModelProfile).where(
            ModelProfile.profile_key == request.profile_key,
            ModelProfile.revision == request.revision,
        )
    )
    if existing is not None:
        if existing.profile_digest != digest:
            raise TaskEnvelopeError(
                "model_profile_revision_conflict",
                "This model profile revision is already bound to different settings.",
            )
        return "existing", existing

    row = ModelProfile(
        id=uuid4(),
        profile_key=request.profile_key,
        revision=request.revision,
        provider=request.provider,
        model=request.model,
        model_revision=request.model_revision,
        temperature=Decimal(str(request.temperature)),
        max_tokens=request.max_tokens,
        timeout_seconds=request.timeout_seconds,
        cost_ceiling_minor_units=request.cost_ceiling_minor_units,
        fallback_order_payload=request.fallback_order,
        status=request.status,
        expires_at=request.expires_at,
        profile_digest=digest,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        concurrent = db.scalar(
            select(ModelProfile).where(
                ModelProfile.profile_key == request.profile_key,
                ModelProfile.revision == request.revision,
            )
        )
        if concurrent is not None and concurrent.profile_digest == digest:
            return "existing", concurrent
        raise TaskEnvelopeError(
            "model_profile_revision_conflict",
            "Concurrent model profile registration conflicts with this revision.",
        ) from error
    db.refresh(row)
    return "created", row


def serialize_model_profile(row: ModelProfile) -> dict[str, Any]:
    snapshot = {
        "profile_key": row.profile_key,
        "revision": row.revision,
        "provider": row.provider,
        "model": row.model,
        "model_revision": row.model_revision,
        "temperature": float(row.temperature),
        "max_tokens": row.max_tokens,
        "timeout_seconds": row.timeout_seconds,
        "cost_ceiling_minor_units": row.cost_ceiling_minor_units,
        "fallback_order": list(row.fallback_order_payload or []),
        "status": row.status,
        "expires_at": _utc(row.expires_at).isoformat() if row.expires_at else None,
    }
    if canonical_digest(snapshot) != row.profile_digest:
        raise TaskEnvelopeError("model_profile_integrity_failed", "Model profile digest verification failed.")
    return {
        "id": row.id,
        **snapshot,
        "expires_at": row.expires_at,
        "profile_digest": row.profile_digest,
        "created_at": row.created_at,
    }


def _profile_blockers(db: Session, request: TaskEnvelopeCreateRequest, now: datetime) -> list[str]:
    blockers: list[str] = []
    if request.deadline is not None and _utc(request.deadline) <= now:
        blockers.append("deadline_elapsed")
    if request.model_profile_id is None:
        return blockers

    profile = db.get(ModelProfile, request.model_profile_id)
    if profile is None:
        raise TaskEnvelopeError("model_profile_not_found", "Model profile not found.", status_code=422)
    serialize_model_profile(profile)
    if profile.status != "active":
        blockers.append("model_profile_inactive")
    if profile.expires_at is not None and _utc(profile.expires_at) <= now:
        blockers.append("model_profile_expired")
    if request.budget.max_tokens is not None and request.budget.max_tokens > profile.max_tokens:
        blockers.append("token_budget_exceeds_profile")
    if (
        request.budget.max_runtime_seconds is not None
        and request.budget.max_runtime_seconds > profile.timeout_seconds
    ):
        blockers.append("runtime_budget_exceeds_profile")
    if (
        profile.cost_ceiling_minor_units is not None
        and request.budget.max_cost_minor_units is not None
        and request.budget.max_cost_minor_units > profile.cost_ceiling_minor_units
    ):
        blockers.append("cost_budget_exceeds_profile")
    return blockers


def _receipt_snapshot(
    *,
    envelope_id: UUID,
    sequence: int,
    event_type: str,
    from_state: str | None,
    to_state: str,
    actor: str,
    payload: dict[str, Any],
    previous_receipt_digest: str | None,
) -> dict[str, Any]:
    return {
        "envelope_id": str(envelope_id),
        "sequence": sequence,
        "event_type": event_type,
        "from_state": from_state,
        "to_state": to_state,
        "actor": actor,
        "payload": payload,
        "previous_receipt_digest": previous_receipt_digest,
    }


def _append_receipt(
    db: Session,
    *,
    envelope: TaskEnvelope,
    event_type: str,
    from_state: str | None,
    to_state: str,
    actor: str,
    payload: dict[str, Any],
) -> TaskReceipt:
    latest = db.scalar(
        select(TaskReceipt)
        .where(TaskReceipt.envelope_id == envelope.task_id)
        .order_by(TaskReceipt.sequence.desc())
        .limit(1)
    )
    sequence = latest.sequence + 1 if latest is not None else 1
    previous = latest.receipt_digest if latest is not None else None
    snapshot = _receipt_snapshot(
        envelope_id=envelope.task_id,
        sequence=sequence,
        event_type=event_type,
        from_state=from_state,
        to_state=to_state,
        actor=actor,
        payload=payload,
        previous_receipt_digest=previous,
    )
    digest = canonical_digest(snapshot)
    row = TaskReceipt(
        id=uuid4(),
        receipt_key=f"task-receipt:{digest}",
        envelope_id=envelope.task_id,
        sequence=sequence,
        event_type=event_type,
        from_state=from_state,
        to_state=to_state,
        actor=actor,
        payload=payload,
        previous_receipt_digest=previous,
        receipt_digest=digest,
    )
    db.add(row)
    return row


def _serialize_receipt(row: TaskReceipt) -> dict[str, Any]:
    snapshot = _receipt_snapshot(
        envelope_id=row.envelope_id,
        sequence=row.sequence,
        event_type=row.event_type,
        from_state=row.from_state,
        to_state=row.to_state,
        actor=row.actor,
        payload=row.payload,
        previous_receipt_digest=row.previous_receipt_digest,
    )
    if canonical_digest(snapshot) != row.receipt_digest or row.receipt_key != f"task-receipt:{row.receipt_digest}":
        raise TaskEnvelopeError("receipt_integrity_failed", "Task receipt digest verification failed.")
    return {
        "receipt_key": row.receipt_key,
        "sequence": row.sequence,
        "event_type": row.event_type,
        "from_state": row.from_state,
        "to_state": row.to_state,
        "actor": row.actor,
        "payload": row.payload,
        "previous_receipt_digest": row.previous_receipt_digest,
        "receipt_digest": row.receipt_digest,
        "created_at": row.created_at,
    }


def _approval_snapshot(
    *,
    approval_ref: str,
    envelope_id: UUID,
    plan_digest: str,
    content_digest: str,
    effects_digest: str,
    scope: list[str],
    scope_digest: str,
    budget: dict[str, Any],
    budget_digest: str,
    approver: str,
    expires_at: datetime,
    revocation_epoch: int,
) -> dict[str, Any]:
    return {
        "approval_ref": approval_ref,
        "envelope_id": str(envelope_id),
        "plan_digest": plan_digest,
        "content_digest": content_digest,
        "effects_digest": effects_digest,
        "scope": scope,
        "scope_digest": scope_digest,
        "budget": budget,
        "budget_digest": budget_digest,
        "approver": approver,
        "expires_at": _utc(expires_at).isoformat(),
        "revocation_epoch": revocation_epoch,
    }


def _serialize_approval(row: TaskApproval, envelope: TaskEnvelope, *, now: datetime) -> dict[str, Any]:
    snapshot = _approval_snapshot(
        approval_ref=row.approval_ref,
        envelope_id=row.envelope_id,
        plan_digest=row.plan_digest,
        content_digest=row.content_digest,
        effects_digest=row.effects_digest,
        scope=list(row.scope_payload),
        scope_digest=row.scope_digest,
        budget=dict(row.budget_payload),
        budget_digest=row.budget_digest,
        approver=row.approver,
        expires_at=row.expires_at,
        revocation_epoch=row.revocation_epoch,
    )
    if canonical_digest(snapshot) != row.approval_digest:
        raise TaskEnvelopeError("approval_integrity_failed", "Task approval digest verification failed.")
    binding_matches = (
        row.plan_digest == envelope.plan_digest
        and row.content_digest == envelope.content_digest
        and row.effects_digest == envelope.effects_digest
        and row.scope_digest == envelope.scope_digest
        and row.budget_digest == envelope.budget_digest
        and canonical_digest(list(row.scope_payload)) == envelope.scope_digest
        and canonical_digest(dict(row.budget_payload)) == envelope.budget_digest
    )
    if not binding_matches:
        raise TaskEnvelopeError(
            "approval_binding_changed",
            "Task content, scope or budget no longer matches the recorded approval.",
        )
    effective = (
        envelope.state == "approved"
        and envelope.approval_ref == row.approval_ref
        and envelope.revocation_epoch == row.revocation_epoch
        and _utc(row.expires_at) > now
    )
    return {
        "approval_ref": row.approval_ref,
        "plan_digest": row.plan_digest,
        "content_digest": row.content_digest,
        "effects_digest": row.effects_digest,
        "scope": list(row.scope_payload),
        "budget": dict(row.budget_payload),
        "approver": row.approver,
        "expires_at": row.expires_at,
        "revocation_epoch": row.revocation_epoch,
        "approval_digest": row.approval_digest,
        "created_at": row.created_at,
        "effective": effective,
    }


def serialize_envelope(db: Session, envelope: TaskEnvelope, *, now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now(UTC)
    approval = None
    if envelope.approval_ref:
        approval_row = db.scalar(
            select(TaskApproval).where(TaskApproval.approval_ref == envelope.approval_ref)
        )
        if approval_row is None or approval_row.envelope_id != envelope.task_id:
            raise TaskEnvelopeError("approval_integrity_failed", "Current approval reference is missing or mismatched.")
        approval = _serialize_approval(approval_row, envelope, now=current)

    receipt_rows = list(
        db.scalars(
            select(TaskReceipt)
            .where(TaskReceipt.envelope_id == envelope.task_id)
            .order_by(TaskReceipt.sequence)
        )
    )
    receipts = [_serialize_receipt(row) for row in receipt_rows]
    for index, receipt in enumerate(receipts):
        expected_previous = receipts[index - 1]["receipt_digest"] if index else None
        if receipt["previous_receipt_digest"] != expected_previous:
            raise TaskEnvelopeError("receipt_chain_failed", "Task receipt chain is incomplete.")
    if not receipts or receipts[-1]["to_state"] != envelope.state:
        raise TaskEnvelopeError(
            "state_receipt_mismatch",
            "Task state does not match the latest immutable receipt.",
        )
    expected_approval_ref = None
    expected_revocation_epoch = 0
    for receipt in receipts:
        if receipt["event_type"] == "approval_recorded":
            expected_approval_ref = receipt["payload"].get("approval_ref")
        if receipt["event_type"] == "task_cancelled":
            expected_revocation_epoch = int(receipt["payload"].get("revocation_epoch", -1))
    if envelope.approval_ref != expected_approval_ref:
        raise TaskEnvelopeError(
            "approval_receipt_mismatch",
            "Current approval reference does not match the immutable receipt chain.",
        )
    if envelope.revocation_epoch != expected_revocation_epoch:
        raise TaskEnvelopeError(
            "revocation_receipt_mismatch",
            "Current revocation epoch does not match the immutable receipt chain.",
        )

    return {
        "task_id": envelope.task_id,
        "request_id": envelope.request_id,
        "user_id": envelope.user_id,
        "mode": envelope.mode,
        "capability_key": envelope.capability_key,
        "state": envelope.state,
        "context_digest": envelope.context_digest,
        "plan_digest": envelope.plan_digest,
        "content_digest": envelope.content_digest,
        "effects_digest": envelope.effects_digest,
        "model_profile_id": envelope.model_profile_id,
        "budget": dict(envelope.budget_payload),
        "required_scopes": list(envelope.required_scope_payload),
        "deadline": envelope.deadline,
        "idempotency_key": envelope.idempotency_key,
        "approval_ref": envelope.approval_ref,
        "rollback_ref": envelope.rollback_ref,
        "legacy_work_task_id": envelope.legacy_work_task_id,
        "revocation_epoch": envelope.revocation_epoch,
        "current_approval": approval,
        "receipts": receipts,
        "execution_flag_enabled": bool(get_settings().anti_fomo_task_envelope),
        "execution_available": False,
        "created_at": envelope.created_at,
        "updated_at": envelope.updated_at,
    }


def create_envelope(
    db: Session,
    *,
    user_id: UUID,
    request: TaskEnvelopeCreateRequest,
    actor: str = "api",
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(UTC)
    request_snapshot = request.model_dump(mode="json")
    request_digest = canonical_digest({"user_id": str(user_id), "request": request_snapshot})

    existing = db.scalar(select(TaskEnvelope).where(TaskEnvelope.idempotency_key == request.idempotency_key))
    if existing is None and db.bind is not None and db.bind.dialect.name == "sqlite":
        # A deferred SQLite read transaction permits multiple callers to see
        # no row and then race on INSERT.  Re-open as IMMEDIATE and recheck so
        # the idempotency decision and first receipt are one serialized write.
        db.rollback()
        db.execute(text("BEGIN IMMEDIATE"))
        existing = db.scalar(
            select(TaskEnvelope).where(TaskEnvelope.idempotency_key == request.idempotency_key)
        )
    if existing is not None:
        if existing.user_id != user_id:
            db.rollback()
            raise TaskEnvelopeError(
                "cross_user_idempotency_replay",
                "This idempotency key belongs to another user.",
                status_code=403,
            )
        if existing.request_digest != request_digest:
            db.rollback()
            raise TaskEnvelopeError(
                "idempotency_conflict",
                "This idempotency key is already bound to different task content.",
            )
        result = {
            "outcome": "existing",
            "deduplicated": True,
            "envelope": serialize_envelope(db, existing, now=current),
        }
        db.rollback()
        return result

    budget_payload = request.budget.model_dump(mode="json")
    required_scopes = list(request.required_scopes)
    blockers = _profile_blockers(db, request, current)
    if blockers:
        initial_state = "hold"
    elif request.plan_digest and request.content_digest and request.effects_digest:
        initial_state = "planned"
    else:
        initial_state = "proposed"

    envelope = TaskEnvelope(
        task_id=uuid4(),
        request_id=request.request_id,
        user_id=user_id,
        mode=request.mode,
        capability_key=request.capability_key,
        state=initial_state,
        context_digest=request.context_digest,
        plan_digest=request.plan_digest,
        content_digest=request.content_digest,
        effects_digest=request.effects_digest,
        model_profile_id=request.model_profile_id,
        budget_payload=budget_payload,
        budget_digest=canonical_digest(budget_payload),
        required_scope_payload=required_scopes,
        scope_digest=canonical_digest(required_scopes),
        deadline=request.deadline,
        idempotency_key=request.idempotency_key,
        request_digest=request_digest,
        request_payload=request_snapshot,
        rollback_ref=request.rollback_ref,
        revocation_epoch=0,
    )
    db.add(envelope)
    _append_receipt(
        db,
        envelope=envelope,
        event_type="proposal_held" if blockers else "proposal_created",
        from_state=None,
        to_state=initial_state,
        actor=actor,
        payload={
            "request_digest": request_digest,
            "budget_digest": envelope.budget_digest,
            "scope_digest": envelope.scope_digest,
            "blockers": blockers,
            "execution_available": False,
        },
    )
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        concurrent = db.scalar(
            select(TaskEnvelope).where(TaskEnvelope.idempotency_key == request.idempotency_key)
        )
        if concurrent is not None:
            if concurrent.user_id != user_id:
                raise TaskEnvelopeError(
                    "cross_user_idempotency_replay",
                    "This idempotency key belongs to another user.",
                    status_code=403,
                ) from error
            if concurrent.request_digest == request_digest:
                return {
                    "outcome": "existing",
                    "deduplicated": True,
                    "envelope": serialize_envelope(db, concurrent, now=current),
                }
        raise TaskEnvelopeError(
            "idempotency_conflict",
            "Concurrent task proposal conflicts with this idempotency key.",
        ) from error
    db.refresh(envelope)
    return {"outcome": "created", "deduplicated": False, "envelope": serialize_envelope(db, envelope, now=current)}


def get_envelope(db: Session, *, user_id: UUID, task_id: UUID) -> TaskEnvelope:
    envelope = db.get(TaskEnvelope, task_id)
    if envelope is None or envelope.user_id != user_id:
        raise TaskEnvelopeError("task_envelope_not_found", "Task envelope not found.", status_code=404)
    return envelope


def approve_envelope(
    db: Session,
    *,
    user_id: UUID,
    task_id: UUID,
    request: TaskApprovalCreateRequest,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(UTC)
    envelope = get_envelope(db, user_id=user_id, task_id=task_id)
    scope_payload = list(request.scope)
    budget_payload = request.budget.model_dump(mode="json")
    scope_digest = canonical_digest(scope_payload)
    budget_digest = canonical_digest(budget_payload)
    approval_snapshot = _approval_snapshot(
        approval_ref=request.approval_ref,
        envelope_id=envelope.task_id,
        plan_digest=request.plan_digest,
        content_digest=request.content_digest,
        effects_digest=request.effects_digest,
        scope=scope_payload,
        scope_digest=scope_digest,
        budget=budget_payload,
        budget_digest=budget_digest,
        approver=request.approver,
        expires_at=request.expires_at,
        revocation_epoch=request.revocation_epoch,
    )
    approval_digest = canonical_digest(approval_snapshot)

    existing = db.scalar(select(TaskApproval).where(TaskApproval.approval_ref == request.approval_ref))
    if existing is not None:
        if (
            existing.envelope_id == envelope.task_id
            and existing.approval_digest == approval_digest
            and envelope.state == "approved"
            and envelope.approval_ref == existing.approval_ref
            and envelope.revocation_epoch == existing.revocation_epoch
        ):
            if _utc(existing.expires_at) <= current:
                raise TaskEnvelopeError("approval_expired", "Approval is already expired.")
            return serialize_envelope(db, envelope, now=current)
        if existing.envelope_id == envelope.task_id and existing.approval_digest == approval_digest:
            raise TaskEnvelopeError("approval_revoked", "This approval is no longer effective.")
        raise TaskEnvelopeError("approval_ref_conflict", "Approval reference is already bound elsewhere.")

    if envelope.state != "planned":
        raise TaskEnvelopeError(
            "invalid_state_transition",
            f"Task approval requires planned state; current state is {envelope.state}.",
        )
    if request.expected_context_digest != envelope.context_digest:
        raise TaskEnvelopeError("context_digest_changed", "Task context changed after the approval request was prepared.")
    for field in ("plan_digest", "content_digest", "effects_digest"):
        if getattr(request, field) != getattr(envelope, field):
            raise TaskEnvelopeError(f"{field}_changed", f"{field} does not match the frozen task proposal.")
    if scope_digest != envelope.scope_digest:
        raise TaskEnvelopeError("scope_changed", "Approval scope does not match the task proposal.")
    if budget_digest != envelope.budget_digest:
        raise TaskEnvelopeError("budget_changed", "Approval budget does not match the task proposal.")
    if request.revocation_epoch != envelope.revocation_epoch:
        raise TaskEnvelopeError("approval_revoked", "Approval revocation epoch is stale.")
    if _utc(request.expires_at) <= current:
        raise TaskEnvelopeError("approval_expired", "Approval is already expired.")
    if envelope.deadline is not None and _utc(envelope.deadline) <= current:
        raise TaskEnvelopeError("deadline_elapsed", "Task deadline has elapsed.")

    if envelope.model_profile_id is not None:
        profile = db.get(ModelProfile, envelope.model_profile_id)
        if profile is None or profile.status != "active":
            raise TaskEnvelopeError("model_profile_unavailable", "Model profile is no longer active.")
        serialize_model_profile(profile)
        if profile.expires_at is not None and _utc(profile.expires_at) <= current:
            raise TaskEnvelopeError("model_profile_expired", "Model profile has expired.")

    approval = TaskApproval(
        id=uuid4(),
        approval_ref=request.approval_ref,
        envelope_id=envelope.task_id,
        plan_digest=request.plan_digest,
        content_digest=request.content_digest,
        effects_digest=request.effects_digest,
        scope_payload=scope_payload,
        scope_digest=scope_digest,
        budget_payload=budget_payload,
        budget_digest=budget_digest,
        approver=request.approver,
        expires_at=request.expires_at,
        revocation_epoch=request.revocation_epoch,
        approval_digest=approval_digest,
    )
    old_state = envelope.state
    envelope.state = "approved"
    envelope.approval_ref = request.approval_ref
    db.add(approval)
    _append_receipt(
        db,
        envelope=envelope,
        event_type="approval_recorded",
        from_state=old_state,
        to_state="approved",
        actor=request.approver,
        payload={
            "approval_ref": request.approval_ref,
            "approval_digest": approval_digest,
            "expires_at": _utc(request.expires_at).isoformat(),
            "revocation_epoch": request.revocation_epoch,
            "execution_available": False,
        },
    )
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise TaskEnvelopeError(
            "approval_conflict",
            "Concurrent approval registration conflicts with this task.",
        ) from error
    db.refresh(envelope)
    return serialize_envelope(db, envelope, now=current)


def cancel_envelope(
    db: Session,
    *,
    user_id: UUID,
    task_id: UUID,
    request: TaskCancelRequest,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(UTC)
    envelope = get_envelope(db, user_id=user_id, task_id=task_id)
    if envelope.state not in {"proposed", "planned", "approved", "hold", "reconcile_required"}:
        raise TaskEnvelopeError(
            "invalid_state_transition",
            f"Task in {envelope.state} state cannot be cancelled by this control plane.",
        )
    if request.expected_revocation_epoch != envelope.revocation_epoch:
        raise TaskEnvelopeError("revocation_epoch_changed", "Task revocation epoch changed; refresh before cancelling.")
    old_state = envelope.state
    old_epoch = envelope.revocation_epoch
    envelope.revocation_epoch += 1
    envelope.state = "cancelled"
    _append_receipt(
        db,
        envelope=envelope,
        event_type="task_cancelled",
        from_state=old_state,
        to_state="cancelled",
        actor=request.actor,
        payload={
            "reason": request.reason,
            "approval_ref": envelope.approval_ref,
            "previous_revocation_epoch": old_epoch,
            "revocation_epoch": envelope.revocation_epoch,
        },
    )
    db.commit()
    db.refresh(envelope)
    return serialize_envelope(db, envelope, now=current)


def reconcile_envelope(
    db: Session,
    *,
    user_id: UUID,
    task_id: UUID,
    request: TaskReconcileRequest,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(UTC)
    envelope = get_envelope(db, user_id=user_id, task_id=task_id)
    if envelope.state not in {"unknown", "reconcile_required"}:
        raise TaskEnvelopeError(
            "invalid_state_transition",
            f"Task in {envelope.state} state does not require reconciliation.",
        )
    if envelope.state == "reconcile_required" and request.resolution_state == "reconcile_required":
        raise TaskEnvelopeError("invalid_state_transition", "Task is already waiting for reconciliation.")
    old_state = envelope.state
    envelope.state = request.resolution_state
    _append_receipt(
        db,
        envelope=envelope,
        event_type="reconciliation_recorded",
        from_state=old_state,
        to_state=request.resolution_state,
        actor=request.actor,
        payload={"evidence_digest": request.evidence_digest, "rationale": request.rationale},
    )
    db.commit()
    db.refresh(envelope)
    return serialize_envelope(db, envelope, now=current)
