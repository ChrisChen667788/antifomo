from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app import models  # noqa: F401
from app.db.base import Base
from app.models.entities import User, WorkTask
from app.models.task_envelope_entities import ModelProfile, TaskApproval, TaskEnvelope, TaskReceipt
from app.schemas.task_envelopes import (
    ModelProfileCreateRequest,
    TaskApprovalCreateRequest,
    TaskBudget,
    TaskCancelRequest,
    TaskEnvelopeCreateRequest,
    TaskReconcileRequest,
)
from app.services.task_envelope_service import (
    TaskEnvelopeError,
    approve_envelope,
    cancel_envelope,
    create_envelope,
    create_model_profile,
    reconcile_envelope,
    serialize_envelope,
)


CONTEXT = "a" * 64
PLAN = "b" * 64
CONTENT = "c" * 64
EFFECTS = "d" * 64


def _request(*, key: str = "task-key", planned: bool = True, model_profile_id: UUID | None = None):
    return TaskEnvelopeCreateRequest(
        request_id=f"request-{key}",
        mode="plan",
        capability_key="export.research-report",
        context_digest=CONTEXT,
        plan_digest=PLAN if planned else None,
        content_digest=CONTENT if planned else None,
        effects_digest=EFFECTS if planned else None,
        model_profile_id=model_profile_id,
        budget=TaskBudget(currency="CNY", max_cost_minor_units=100, max_tokens=1000, max_runtime_seconds=30),
        required_scopes=["artifact:write", "task:read"],
        deadline=datetime.now(UTC) + timedelta(hours=2),
        idempotency_key=key,
        rollback_ref="rollback:local-export",
        request_payload={"artifact": "research-report"},
    )


def _approval(*, ref: str = "approval-1", expires_at: datetime | None = None, **overrides):
    values = {
        "approval_ref": ref,
        "expected_context_digest": CONTEXT,
        "plan_digest": PLAN,
        "content_digest": CONTENT,
        "effects_digest": EFFECTS,
        "scope": ["artifact:write", "task:read"],
        "budget": TaskBudget(
            currency="CNY",
            max_cost_minor_units=100,
            max_tokens=1000,
            max_runtime_seconds=30,
        ),
        "approver": "named-reviewer",
        "expires_at": expires_at or datetime.now(UTC) + timedelta(hours=1),
        "revocation_epoch": 0,
    }
    values.update(overrides)
    return TaskApprovalCreateRequest(**values)


def _engine(path: Path | None = None):
    url = f"sqlite+pysqlite:///{path}" if path else "sqlite+pysqlite:///:memory:"
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})
    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection, _record):  # type: ignore[no-untyped-def]
        dbapi_connection.execute("PRAGMA foreign_keys=ON")
        if path:
            dbapi_connection.execute("PRAGMA journal_mode=WAL")
            dbapi_connection.execute("PRAGMA busy_timeout=30000")
    Base.metadata.create_all(engine)
    return engine


def _create_user(engine, user_id: UUID) -> None:
    with Session(engine) as db:
        db.add(User(id=user_id, name=f"user-{user_id}"))
        db.commit()


def test_100_replays_create_one_envelope_and_no_execution(tmp_path: Path) -> None:
    engine = _engine(tmp_path / "concurrent.sqlite")
    user_id = uuid4()
    _create_user(engine, user_id)
    request = _request()

    def submit(_index: int) -> str:
        with Session(engine) as db:
            return create_envelope(db, user_id=user_id, request=request)["outcome"]

    with ThreadPoolExecutor(max_workers=20) as pool:
        outcomes = list(pool.map(submit, range(100)))

    assert outcomes.count("created") == 1
    assert outcomes.count("existing") == 99
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(TaskEnvelope)) == 1
        assert db.scalar(select(func.count()).select_from(TaskReceipt)) == 1
        assert db.scalar(select(func.count()).select_from(TaskApproval)) == 0
        assert db.scalar(select(func.count()).select_from(WorkTask)) == 0
    engine.dispose()


def test_idempotency_conflict_and_cross_user_replay_are_rejected() -> None:
    engine = _engine()
    owner = uuid4()
    other = uuid4()
    _create_user(engine, owner)
    _create_user(engine, other)
    with Session(engine) as db:
        create_envelope(db, user_id=owner, request=_request())
        changed = _request()
        changed.request_payload = {"artifact": "different"}
        with pytest.raises(TaskEnvelopeError, match="different task content") as conflict:
            create_envelope(db, user_id=owner, request=changed)
        assert conflict.value.code == "idempotency_conflict"
        with pytest.raises(TaskEnvelopeError, match="another user") as cross_user:
            create_envelope(db, user_id=other, request=_request())
        assert cross_user.value.code == "cross_user_idempotency_replay"
        assert cross_user.value.status_code == 403


@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"expected_context_digest": "e" * 64}, "context_digest_changed"),
        ({"plan_digest": "e" * 64}, "plan_digest_changed"),
        ({"content_digest": "e" * 64}, "content_digest_changed"),
        ({"effects_digest": "e" * 64}, "effects_digest_changed"),
        ({"scope": ["task:read"]}, "scope_changed"),
        ({"budget": TaskBudget(max_tokens=999)}, "budget_changed"),
        ({"revocation_epoch": 1}, "approval_revoked"),
    ],
)
def test_approval_is_bound_to_frozen_content_scope_budget_and_epoch(override: dict, code: str) -> None:
    engine = _engine()
    user_id = uuid4()
    _create_user(engine, user_id)
    with Session(engine) as db:
        created = create_envelope(db, user_id=user_id, request=_request())
        with pytest.raises(TaskEnvelopeError) as captured:
            approve_envelope(
                db,
                user_id=user_id,
                task_id=created["envelope"]["task_id"],
                request=_approval(**override),
            )
        assert captured.value.code == code
        db.rollback()
        assert db.scalar(select(func.count()).select_from(TaskApproval)) == 0
        assert db.scalar(select(func.count()).select_from(WorkTask)) == 0


def test_approval_expiry_and_proposed_state_fail_closed() -> None:
    engine = _engine()
    user_id = uuid4()
    _create_user(engine, user_id)
    with Session(engine) as db:
        planned = create_envelope(db, user_id=user_id, request=_request(key="planned"))
        with pytest.raises(TaskEnvelopeError) as expired:
            approve_envelope(
                db,
                user_id=user_id,
                task_id=planned["envelope"]["task_id"],
                request=_approval(ref="expired", expires_at=datetime.now(UTC) - timedelta(seconds=1)),
            )
        assert expired.value.code == "approval_expired"
        db.rollback()

        proposed = create_envelope(db, user_id=user_id, request=_request(key="proposed", planned=False))
        with pytest.raises(TaskEnvelopeError) as state_error:
            approve_envelope(
                db,
                user_id=user_id,
                task_id=proposed["envelope"]["task_id"],
                request=_approval(ref="proposal-approval"),
            )
        assert state_error.value.code == "invalid_state_transition"
        assert db.scalar(select(func.count()).select_from(WorkTask)) == 0


def test_idempotent_approval_replay_does_not_revive_expired_approval() -> None:
    engine = _engine()
    user_id = uuid4()
    _create_user(engine, user_id)
    baseline = datetime(2026, 10, 2, 0, 0, tzinfo=UTC)
    with Session(engine) as db:
        created = create_envelope(db, user_id=user_id, request=_request(), now=baseline)
        approval = _approval(expires_at=baseline + timedelta(seconds=1))
        approve_envelope(
            db,
            user_id=user_id,
            task_id=created["envelope"]["task_id"],
            request=approval,
            now=baseline,
        )
        with pytest.raises(TaskEnvelopeError) as expired:
            approve_envelope(
                db,
                user_id=user_id,
                task_id=created["envelope"]["task_id"],
                request=approval,
                now=baseline + timedelta(seconds=2),
            )
        assert expired.value.code == "approval_expired"


def test_approve_then_cancel_revokes_approval_without_execution() -> None:
    engine = _engine()
    user_id = uuid4()
    _create_user(engine, user_id)
    with Session(engine) as db:
        created = create_envelope(db, user_id=user_id, request=_request())
        task_id = created["envelope"]["task_id"]
        approval_request = _approval()
        approved = approve_envelope(
            db,
            user_id=user_id,
            task_id=task_id,
            request=approval_request,
        )
        assert approved["state"] == "approved"
        assert approved["current_approval"]["effective"] is True
        assert approved["execution_available"] is False
        assert approved["legacy_work_task_id"] is None

        cancelled = cancel_envelope(
            db,
            user_id=user_id,
            task_id=task_id,
            request=TaskCancelRequest(
                actor="named-reviewer",
                reason="approval revoked before execution",
                expected_revocation_epoch=0,
            ),
        )
        assert cancelled["state"] == "cancelled"
        assert cancelled["revocation_epoch"] == 1
        assert cancelled["current_approval"]["effective"] is False
        assert [item["event_type"] for item in cancelled["receipts"]] == [
            "proposal_created",
            "approval_recorded",
            "task_cancelled",
        ]
        with pytest.raises(TaskEnvelopeError) as revoked:
            approve_envelope(db, user_id=user_id, task_id=task_id, request=approval_request)
        assert revoked.value.code == "approval_revoked"
        assert db.scalar(select(func.count()).select_from(WorkTask)) == 0


def test_expired_or_over_budget_model_profile_places_proposal_on_hold() -> None:
    engine = _engine()
    user_id = uuid4()
    _create_user(engine, user_id)
    with Session(engine) as db:
        _, profile = create_model_profile(
            db,
            ModelProfileCreateRequest(
                profile_key="research.fixed",
                revision=1,
                provider="mock",
                model="fixed-fixture",
                model_revision="sha256:test",
                temperature=0,
                max_tokens=100,
                timeout_seconds=10,
                cost_ceiling_minor_units=10,
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
            ),
        )
        held = create_envelope(
            db,
            user_id=user_id,
            request=_request(key="held", model_profile_id=profile.id),
        )
        assert held["envelope"]["state"] == "hold"
        assert held["envelope"]["receipts"][0]["payload"]["blockers"] == [
            "model_profile_expired",
            "token_budget_exceeds_profile",
            "runtime_budget_exceeds_profile",
            "cost_budget_exceeds_profile",
        ]
        assert db.scalar(select(func.count()).select_from(WorkTask)) == 0


def test_model_profile_rejects_precision_that_storage_cannot_preserve() -> None:
    with pytest.raises(ValidationError, match="at most three decimal places"):
        ModelProfileCreateRequest(
            profile_key="research.invalid-precision",
            revision=1,
            provider="mock",
            model="fixture",
            model_revision="sha256:test",
            temperature=0.1234,
            max_tokens=100,
            timeout_seconds=10,
        )


def test_approved_envelope_frozen_binding_cannot_be_mutated() -> None:
    engine = _engine()
    user_id = uuid4()
    _create_user(engine, user_id)
    with Session(engine) as db:
        created = create_envelope(db, user_id=user_id, request=_request())
        task_id = created["envelope"]["task_id"]
        approve_envelope(db, user_id=user_id, task_id=task_id, request=_approval())

        envelope = db.get(TaskEnvelope, task_id)
        envelope.content_digest = "e" * 64
        with pytest.raises(ValueError, match="frozen fields cannot change"):
            db.commit()
        db.rollback()

        with pytest.raises(DBAPIError, match="Task envelope frozen fields cannot change"):
            db.execute(
                text("UPDATE task_envelopes SET required_scope_payload = :scope WHERE task_id = :task_id"),
                {"scope": '["external:write"]', "task_id": task_id.hex},
            )
            db.commit()
        db.rollback()

        envelope = db.get(TaskEnvelope, task_id)
        serialized = serialize_envelope(db, envelope)
        assert serialized["current_approval"]["effective"] is True
        assert serialized["required_scopes"] == ["artifact:write", "task:read"]


def test_state_approval_and_revocation_tampering_fails_receipt_verification() -> None:
    engine = _engine()
    user_id = uuid4()
    _create_user(engine, user_id)
    with Session(engine) as db:
        created = create_envelope(db, user_id=user_id, request=_request())
        task_id = created["envelope"]["task_id"]
        approve_envelope(db, user_id=user_id, task_id=task_id, request=_approval())
        db.execute(
            text(
                "UPDATE task_envelopes SET state = 'succeeded', approval_ref = NULL, "
                "revocation_epoch = 9 WHERE task_id = :task_id"
            ),
            {"task_id": task_id.hex},
        )
        db.commit()
        envelope = db.get(TaskEnvelope, task_id)
        with pytest.raises(TaskEnvelopeError) as captured:
            serialize_envelope(db, envelope)
        assert captured.value.code == "state_receipt_mismatch"


def test_foreign_keys_are_enabled_for_control_plane_evidence() -> None:
    engine = _engine()
    user_id = uuid4()
    _create_user(engine, user_id)
    with Session(engine) as db:
        create_envelope(db, user_id=user_id, request=_request())
        assert db.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        with pytest.raises(DBAPIError):
            db.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id.hex})
            db.commit()
        db.rollback()


def test_runtime_sqlite_engine_enables_foreign_keys() -> None:
    from app.db.session import engine as runtime_engine

    if runtime_engine.dialect.name == "sqlite":
        with runtime_engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1


def test_invalid_reconcile_transition_and_append_only_receipt_guard() -> None:
    engine = _engine()
    user_id = uuid4()
    _create_user(engine, user_id)
    with Session(engine) as db:
        created = create_envelope(db, user_id=user_id, request=_request(planned=False))
        task_id = created["envelope"]["task_id"]
        with pytest.raises(TaskEnvelopeError) as invalid:
            reconcile_envelope(
                db,
                user_id=user_id,
                task_id=task_id,
                request=TaskReconcileRequest(
                    actor="operator",
                    resolution_state="hold",
                    evidence_digest="f" * 64,
                    rationale="No external execution exists.",
                ),
            )
        assert invalid.value.code == "invalid_state_transition"
        db.rollback()

        receipt_id = db.scalar(select(TaskReceipt.id))
        with pytest.raises(DBAPIError, match="Task receipts are append-only"):
            db.execute(
                text("UPDATE task_receipts SET actor = 'tampered' WHERE id = :id"),
                {"id": receipt_id.hex},
            )
            db.commit()
        db.rollback()
