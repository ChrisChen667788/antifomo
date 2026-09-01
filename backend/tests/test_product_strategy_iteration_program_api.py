from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app import main as main_module
from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)

    def override_db() -> Generator[Session, None, None]:
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(main_module, "engine", engine)
    monkeypatch.setattr(main_module, "start_item_recovery_worker", lambda: None)
    monkeypatch.setattr(main_module, "stop_item_recovery_worker", lambda: None)
    monkeypatch.setattr(main_module, "start_research_job_worker", lambda: None)
    monkeypatch.setattr(main_module, "stop_research_job_worker", lambda: None)
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_iteration_program_preview_and_explicit_initialization_are_gated(client: TestClient) -> None:
    preview = client.get("/api/product-strategy/iteration-program/preview")
    assert preview.status_code == 200, preview.text
    preview_payload = preview.json()
    assert preview_payload["iteration_program_version"] == "2.10.3-2.11.7"
    assert preview_payload["read_only"] is True
    assert preview_payload["initialized"] is False
    assert len(preview_payload["iterations"]) == 15
    assert len(preview_payload["agent_sources"]) >= 7
    assert preview_payload["governance"]["vendor_claim_is_not_independent_verification"] is True
    assert preview_payload["governance"]["can_auto_execute"] is False
    assert preview_payload["governance"]["can_auto_approve_release"] is False

    empty = client.get("/api/product-strategy/iteration-program")
    assert empty.status_code == 200, empty.text
    assert empty.json()["initialized"] is False
    assert empty.json()["iterations"] == []

    initialized = client.post("/api/product-strategy/iteration-program/initialize")
    assert initialized.status_code == 200, initialized.text
    payload = initialized.json()
    assert payload["read_only"] is False
    assert payload["initialized"] is True
    assert len(payload["iterations"]) == 15
    assert payload["initialization"]["iterations"]["created"] == 15
    assert payload["initialization"]["revisions"]["created"] == 15
    assert payload["initialization_audit"]["release_gate_mutated"] is False
    assert all(iteration["acceptance_status"] == "hold" for iteration in payload["iterations"])
    assert all(iteration["can_auto_accept"] is False for iteration in payload["iterations"])

    repeated = client.post("/api/product-strategy/iteration-program/initialize")
    assert repeated.status_code == 200, repeated.text
    repeat = repeated.json()
    assert repeat["initialization"]["iterations"]["existing_seed_managed"] == 15
    assert repeat["initialization"]["revisions"]["existing"] == 15
