from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import User, WorkTask
from app.models.task_envelope_entities import TaskEnvelope


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(id=get_settings().single_user_id, name="Demo User"))
        db.commit()

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def _payload() -> dict:
    return {
        "request_id": "api-request-1",
        "mode": "plan",
        "capability_key": "export.research-report",
        "context_digest": "a" * 64,
        "plan_digest": "b" * 64,
        "content_digest": "c" * 64,
        "effects_digest": "d" * 64,
        "budget": {
            "currency": "CNY",
            "max_cost_minor_units": 100,
            "max_tokens": 1000,
            "max_runtime_seconds": 30,
        },
        "required_scopes": ["artifact:write", "task:read"],
        "idempotency_key": "api-idempotency-1",
        "request_payload": {"artifact": "research-report"},
    }


def test_task_envelope_api_create_replay_approve_and_cancel(client: TestClient) -> None:
    created = client.post("/api/task-envelopes", json=_payload())
    assert created.status_code == 201
    body = created.json()
    assert body["outcome"] == "created"
    assert body["envelope"]["state"] == "planned"
    assert body["envelope"]["execution_flag_enabled"] is False
    assert body["envelope"]["execution_available"] is False
    assert body["envelope"]["legacy_work_task_id"] is None
    task_id = body["envelope"]["task_id"]

    replay = client.post("/api/task-envelopes", json=_payload())
    assert replay.status_code == 201
    assert replay.json()["outcome"] == "existing"
    assert replay.json()["envelope"]["task_id"] == task_id

    approval = {
        "approval_ref": "api-approval-1",
        "expected_context_digest": "a" * 64,
        "plan_digest": "b" * 64,
        "content_digest": "c" * 64,
        "effects_digest": "d" * 64,
        "scope": ["artifact:write", "task:read"],
        "budget": _payload()["budget"],
        "approver": "named-reviewer",
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        "revocation_epoch": 0,
    }
    approved = client.post(f"/api/task-envelopes/{task_id}/approve", json=approval)
    assert approved.status_code == 200
    assert approved.json()["state"] == "approved"
    assert approved.json()["current_approval"]["effective"] is True

    cancelled = client.post(
        f"/api/task-envelopes/{task_id}/cancel",
        json={
            "actor": "named-reviewer",
            "reason": "stop before execution",
            "expected_revocation_epoch": 0,
        },
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["state"] == "cancelled"
    assert cancelled.json()["current_approval"]["effective"] is False

    with next(app.dependency_overrides[get_db]()) as db:
        assert db.scalar(select(func.count()).select_from(TaskEnvelope)) == 1
        assert db.scalar(select(func.count()).select_from(WorkTask)) == 0


def test_task_envelope_api_returns_structured_conflict(client: TestClient) -> None:
    assert client.post("/api/task-envelopes", json=_payload()).status_code == 201
    changed = _payload()
    changed["request_payload"] = {"artifact": "changed"}
    response = client.post("/api/task-envelopes", json=changed)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "idempotency_conflict"
