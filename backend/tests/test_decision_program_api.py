from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
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


def test_program_overview_release_candidate_and_quality_api(client: TestClient) -> None:
    overview = client.get("/api/decision-studio/program/overview")
    assert overview.status_code == 200, overview.text
    assert overview.json()["version"] == "2.2.0-development"
    assert overview.json()["engineering_status"] == "implemented"
    assert overview.json()["overall_acceptance_status"] == "blocked"
    assert [row["version"] for row in overview.json()["milestones"]] == [
        "2.0.7",
        "2.1.0",
        "2.1.1",
        "2.1.2",
        "2.1.3",
        "2.1.4",
        "2.1.5",
        "2.2.0",
    ]

    preview = client.post(
        "/api/decision-studio/program/release-candidates/preview",
        json={"version": "2.0.7", "manifest": {"git_commit": "abc123"}},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["persisted"] is False
    assert preview.json()["acceptance_status"] == "blocked"

    candidate = client.post(
        "/api/decision-studio/program/release-candidates",
        json={"version": "2.0.7", "manifest": {"git_commit": "abc123"}},
    )
    assert candidate.status_code == 201, candidate.text
    assert candidate.json()["status"] == "frozen"
    assert candidate.json()["acceptance_status"] == "blocked"
    assert candidate.json()["blockers"]

    benchmark = client.post(
        "/api/decision-studio/program/quality-benchmarks",
        json={
            "benchmark_key": "retrieval-api",
            "version": "1.0.0",
            "benchmark_kind": "retrieval",
            "case_count": 10,
            "corpus_digest": "b" * 64,
            "metrics": {"ndcg_at_10": 0.99, "recall_at_20": 0.99, "clickback_rate": 1.0},
            "source_artifact_uri": "artifact://qrels.json",
        },
    )
    assert benchmark.status_code == 201, benchmark.text
    assert benchmark.json()["status"] == "blocked"


def test_research_document_identity_and_export_api(client: TestClient) -> None:
    notebook_response = client.post(
        "/api/decision-studio/notebooks",
        json={"name": "2.2.0 API Notebook", "description": "program test"},
    )
    assert notebook_response.status_code == 201, notebook_response.text
    notebook_id = notebook_response.json()["id"]
    source_response = client.post(
        f"/api/decision-studio/notebooks/{notebook_id}/sources",
        json={
            "title": "项目资料",
            "file_name": "source.txt",
            "mime_type": "text/plain",
            "content": "真实项目资料。",
        },
    )
    assert source_response.status_code == 201, source_response.text

    research = client.post(
        "/api/decision-studio/program/research-runs",
        json={
            "notebook_id": notebook_id,
            "run_key": "api-run-001",
            "title": "API Research Run",
            "brief": {"decision": "go or hold"},
            "question_tree": [{"key": "q1", "question": "证据是否充分"}],
            "source_decisions": [{"source": "official", "policy": "required"}],
            "budget_fen": 100,
        },
    )
    assert research.status_code == 201, research.text
    run_id = research.json()["id"]
    invalid_start = client.post(
        f"/api/decision-studio/program/research-runs/{run_id}/actions",
        json={"action": "start"},
    )
    assert invalid_start.status_code == 400
    approved = client.post(
        f"/api/decision-studio/program/research-runs/{run_id}/actions",
        json={"action": "approve", "expected_plan_hash": research.json()["plan_hash"]},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["source_snapshot"]
    started = client.post(
        f"/api/decision-studio/program/research-runs/{run_id}/actions",
        json={"action": "start"},
    )
    assert started.status_code == 200, started.text
    completed = client.post(
        f"/api/decision-studio/program/research-runs/{run_id}/actions",
        json={"action": "complete", "spend_fen": 50, "result": {"decision": "hold"}},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"

    claim = client.post(
        f"/api/decision-studio/notebooks/{notebook_id}/claims",
        json={
            "claim_key": "api-claim",
            "text": "当前证据支持先做最小样机。",
            "criticality": "normal",
            "status": "accepted",
            "passage_ids": [],
            "depends_on_claim_ids": [],
            "facts": {},
            "owner_label": "api-test",
        },
    )
    assert claim.status_code == 201, claim.text
    draft = client.post(
        "/api/decision-studio/program/document-drafts",
        json={
            "notebook_id": notebook_id,
            "title": "API 项目建议书",
            "document_kind": "project_proposal",
        },
    )
    assert draft.status_code == 201, draft.text
    draft_id = draft.json()["id"]
    conflict = client.put(
        f"/api/decision-studio/program/document-drafts/{draft_id}/blocks",
        json={"expected_revision": 9, "block_key": "manual", "content": "人工内容"},
    )
    assert conflict.status_code == 409, conflict.text
    export = client.post(
        f"/api/decision-studio/program/document-drafts/{draft_id}/export",
        json={"format": "docx"},
    )
    assert export.status_code == 200, export.text
    assert export.content.startswith(b"PK")
    assert export.headers["x-anti-fomo-office-status"] == "pass"

    space = client.post(
        "/api/decision-studio/spaces",
        json={"name": "Enterprise API", "description": "", "visibility": "private"},
    )
    assert space.status_code == 201, space.text
    profile = client.post(
        "/api/decision-studio/program/identity-profiles",
        json={
            "space_id": space.json()["id"],
            "provider_type": "microsoft_entra",
            "name": "Entra",
            "issuer_uri": "https://login.microsoftonline.com/example/v2.0",
            "client_id": "public-client-id",
            "tenant_key": "example",
            "role_mapping": {"research": "editor"},
            "allowed_domains": ["example.com"],
            "retention_days": 30,
        },
    )
    assert profile.status_code == 201, profile.text
    assert profile.json()["client_id_fingerprint"] != "public-client-id"
    assert "client_id" not in profile.json()
