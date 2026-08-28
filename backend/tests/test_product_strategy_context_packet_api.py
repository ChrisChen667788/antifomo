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
    # Keep startup isolated: no developer SQLite file and no recovery workers.
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


def test_decision_context_packets_preview_initialize_and_persisted_api(client: TestClient) -> None:
    preview = client.get("/api/product-strategy/decision-context-packets/preview")
    assert preview.status_code == 200, preview.text
    preview_payload = preview.json()
    assert preview_payload["read_only"] is True
    assert preview_payload["initialized"] is False
    assert preview_payload["approval_evidence"]["kind"] == "user_instruction"
    assert preview_payload["approval_evidence"]["actor_identity_status"] == "unverified"
    assert preview_payload["approval_evidence"]["scope"] == "product_strategy_only"
    assert len(preview_payload["packets"]) == 4
    assert len(preview_payload["excluded_cards"]) == 2
    assert all(packet["roadmap_card_key"] for packet in preview_payload["packets"])
    assert all(packet["can_auto_execute"] is False for packet in preview_payload["packets"])
    assert all(packet["can_auto_approve_release"] is False for packet in preview_payload["packets"])

    empty = client.get("/api/product-strategy/decision-context-packets")
    assert empty.status_code == 200, empty.text
    assert empty.json()["initialized"] is False
    assert empty.json()["packets"] == []

    initialized = client.post("/api/product-strategy/decision-context-packets/initialize")
    assert initialized.status_code == 200, initialized.text
    initialized_payload = initialized.json()
    assert initialized_payload["read_only"] is False
    assert initialized_payload["initialized"] is True
    assert initialized_payload["initialization"]["packets"]["created"] == 4
    assert initialized_payload["initialization"]["revisions"]["created"] == 4
    assert initialized_payload["initialization"]["approval_audit"]["created"] == 1
    assert initialized_payload["governance"]["release_gate_mutated"] is False
    assert initialized_payload["initialization_audit"]["can_auto_approve_release"] is False
    assert all(packet["revisions"][0]["previous_revision_digest"] is None for packet in initialized_payload["packets"])

    repeated = client.post("/api/product-strategy/decision-context-packets/initialize")
    assert repeated.status_code == 200, repeated.text
    repeated_payload = repeated.json()
    assert repeated_payload["initialization"]["packets"]["created"] == 0
    assert repeated_payload["initialization"]["packets"]["existing_seed_managed"] == 4
    assert repeated_payload["initialization"]["approval_audit"]["existing"] == 1
