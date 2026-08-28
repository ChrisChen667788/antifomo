from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
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
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_notebook_source_search_and_contract_api(client: TestClient) -> None:
    overview = client.get("/api/decision-studio/overview")
    assert overview.status_code == 200, overview.text
    assert overview.json()["version"] == "2.2.0-development"
    assert overview.json()["capabilities"][-1] == "2.2.0"
    assert overview.json()["embedding"]["model"] == "BAAI/bge-m3"

    notebook_response = client.post(
        "/api/decision-studio/notebooks",
        json={"name": "文旅 Notebook", "description": "API test"},
    )
    assert notebook_response.status_code == 201, notebook_response.text
    notebook_id = notebook_response.json()["id"]

    source_response = client.post(
        f"/api/decision-studio/notebooks/{notebook_id}/sources",
        json={
            "title": "文旅资料",
            "file_name": "tourism.txt",
            "mime_type": "text/plain",
            "content": "景区游客增长明显。\n文旅产品需要升级。",
        },
    )
    assert source_response.status_code == 201, source_response.text
    source = source_response.json()["source"]
    assert source["current_passage_count"] == 2

    degraded = client.post(
        f"/api/decision-studio/notebooks/{notebook_id}/search",
        json={
            "query": "景区游客",
            "included_source_ids": [source["id"]],
            "limit": 5,
            "require_semantic": False,
        },
    )
    assert degraded.status_code == 200, degraded.text
    assert degraded.json()["mode"] == "lexical_fallback"
    assert degraded.json()["status"] == "degraded"

    strict = client.post(
        f"/api/decision-studio/notebooks/{notebook_id}/search",
        json={"query": "景区游客", "require_semantic": True},
    )
    assert strict.status_code == 503

    packs = client.get("/api/decision-studio/policy-packs")
    assert packs.status_code == 200, packs.text
    pack = next(item for item in packs.json() if item["pack_key"] == "government_fsr_2023")
    contract = client.post(
        f"/api/decision-studio/notebooks/{notebook_id}/contracts",
        json={"policy_pack_id": pack["id"], "title": "文旅项目可研"},
    )
    assert contract.status_code == 201, contract.text
    assert contract.json()["gap_count"] >= 35

    detail = client.get(f"/api/decision-studio/notebooks/{notebook_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["source_count"] == 1
    assert len(detail.json()["contracts"]) == 1


def test_release_program_validation_audit_and_reliability_api(client: TestClient) -> None:
    specs = client.get("/api/decision-studio/validation-specs")
    assert specs.status_code == 200, specs.text
    assert specs.json()["release_version"] == "2.0.7-development"
    assert [row["version"] for row in specs.json()["milestones"]] == [
        "2.0.1",
        "2.0.2",
        "2.0.3",
        "2.0.4",
        "2.0.5",
        "2.0.6",
    ]

    metrics = {
        "candidate_count": 1,
        "created_source_count": 1,
        "updated_source_count": 0,
        "unchanged_source_count": 0,
        "failed_source_count": 0,
        "provenance_source_count": 1,
    }
    preview = client.post(
        "/api/decision-studio/validation-runs/preview",
        json={"suite_key": "real_data_activation", "metrics": metrics},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["status"] == "pass"

    recorded = client.post(
        "/api/decision-studio/validation-runs",
        json={"suite_key": "real_data_activation", "metrics": metrics},
    )
    assert recorded.status_code == 201, recorded.text
    assert recorded.json()["milestone_version"] == "2.0.1"

    runs = client.get("/api/decision-studio/validation-runs")
    assert runs.status_code == 200, runs.text
    assert len(runs.json()) == 1

    audit = client.get("/api/decision-studio/validation-runs/audit-export")
    assert audit.status_code == 200, audit.text
    assert audit.json()["chain_valid"] is True
    assert audit.json()["record_count"] == 1

    program = client.get("/api/decision-studio/release-program")
    assert program.status_code == 200, program.text
    assert program.json()["implementation_status"] == "implemented"
    assert program.json()["overall_status"] == "blocked"
    first = program.json()["milestones"][0]
    assert first["version"] == "2.0.1"
    assert first["passed_suite_count"] == 1

    probe = client.post("/api/decision-studio/reliability/probe", json={})
    assert probe.status_code == 200, probe.text
    assert probe.json()["status"] == "blocked"
    assert probe.json()["audit_chain_valid"] is True
