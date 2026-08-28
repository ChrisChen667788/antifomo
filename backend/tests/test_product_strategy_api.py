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
    # FastAPI startup normally auto-creates the local demo schema and starts
    # recovery workers. Keep this API test fully isolated from the developer's
    # real SQLite file and background workers.
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


def test_competitive_landscape_preview_seed_and_persisted_api(client: TestClient) -> None:
    preview = client.get("/api/product-strategy/competitive-landscape/preview")
    assert preview.status_code == 200, preview.text
    preview_payload = preview.json()
    assert preview_payload["read_only"] is True
    assert preview_payload["initialized"] is False
    assert preview_payload["governance"]["release_gate_mutated"] is False
    assert {item["product_key"] for item in preview_payload["products"]} == {
        "workbuddy",
        "trae",
        "qwen_work",
        "langhub",
        "baidu_dumate",
        "tencent_qclaw",
    }
    assert all(item["evidence"]["recorded_status"] == "vendor_claim_unverified" for item in preview_payload["products"])
    assert {item["evidence"]["status"] for item in preview_payload["products"]} <= {
        "vendor_claim_unverified",
        "stale",
    }

    empty = client.get("/api/product-strategy/competitive-landscape")
    assert empty.status_code == 200, empty.text
    assert empty.json()["initialized"] is False
    assert empty.json()["products"] == []

    seeded = client.post("/api/product-strategy/competitive-landscape/seed")
    assert seeded.status_code == 200, seeded.text
    seeded_payload = seeded.json()
    assert seeded_payload["read_only"] is False
    assert seeded_payload["initialized"] is True
    assert seeded_payload["seed"]["sources"]["created"] == 6
    assert seeded_payload["seed"]["roadmap_cards"]["created"] == 6
    assert all(item["can_auto_approve_release"] is False for item in seeded_payload["roadmap_cards"])

    repeat = client.post("/api/product-strategy/competitive-landscape/seed")
    assert repeat.status_code == 200, repeat.text
    assert repeat.json()["seed"]["sources"]["created"] == 0
    assert repeat.json()["seed"]["roadmap_cards"]["created"] == 0
