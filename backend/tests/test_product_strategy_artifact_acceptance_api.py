from __future__ import annotations

from collections.abc import Generator

import pytest
import base64
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


def test_artifact_acceptance_preview_fails_closed_and_initialize_requires_context_packets(
    client: TestClient,
) -> None:
    preview = client.get("/api/product-strategy/artifact-acceptance/preview")
    assert preview.status_code == 200, preview.text
    preview_payload = preview.json()
    assert preview_payload["artifact_acceptance_version"] == "2.10.2"
    assert preview_payload["read_only"] is True
    assert preview_payload["initialized"] is False
    assert len(preview_payload["artifacts"]) == 4
    assert all(artifact["acceptance_status"] == "hold" for artifact in preview_payload["artifacts"])
    assert all(artifact["office_evidence_status"] == "missing" for artifact in preview_payload["artifacts"])
    assert all(artifact["visual_evidence_status"] == "missing" for artifact in preview_payload["artifacts"])
    assert preview_payload["governance"]["no_external_office_file_processing"] is True
    assert preview_payload["governance"]["no_visual_render_validation_claim"] is True

    empty = client.get("/api/product-strategy/artifact-acceptance")
    assert empty.status_code == 200, empty.text
    empty_payload = empty.json()
    assert empty_payload["initialized"] is False
    assert empty_payload["artifacts"] == []
    assert len(empty_payload["context_packet_readiness"]["missing_context_packet_keys"]) == 4

    blocked = client.post("/api/product-strategy/artifact-acceptance/initialize")
    assert blocked.status_code == 409, blocked.text
    detail = blocked.json()["detail"]
    assert detail["code"] == "decision_context_packets_required"
    assert len(detail["missing_context_packet_keys"]) == 4
    assert detail["can_auto_accept"] is False
    assert detail["can_auto_execute"] is False
    assert detail["can_auto_approve_release"] is False


def test_artifact_acceptance_initializes_only_after_context_packets_and_stays_hold(client: TestClient) -> None:
    contexts = client.post("/api/product-strategy/decision-context-packets/initialize")
    assert contexts.status_code == 200, contexts.text

    initialized = client.post("/api/product-strategy/artifact-acceptance/initialize")
    assert initialized.status_code == 200, initialized.text
    payload = initialized.json()
    assert payload["read_only"] is False
    assert payload["initialized"] is True
    assert payload["context_packet_readiness"]["ready_for_explicit_initialization"] is True
    assert payload["initialization"]["drafts"]["created"] == 4
    assert payload["initialization"]["revisions"]["created"] == 4
    assert payload["initialization"]["initialization_audit"]["created"] == 1
    assert payload["initialization_audit"]["release_gate_mutated"] is False
    assert all(artifact["acceptance_status"] == "hold" for artifact in payload["artifacts"])
    assert all(artifact["blocking_status"] == "blocked" for artifact in payload["artifacts"])
    assert all(artifact["can_auto_accept"] is False for artifact in payload["artifacts"])
    assert all(artifact["can_auto_execute"] is False for artifact in payload["artifacts"])
    assert all(artifact["can_auto_approve_release"] is False for artifact in payload["artifacts"])
    assert all(artifact["revisions"][0]["previous_revision_digest"] is None for artifact in payload["artifacts"])

    repeated = client.post("/api/product-strategy/artifact-acceptance/initialize")
    assert repeated.status_code == 200, repeated.text
    repeat_payload = repeated.json()
    assert repeat_payload["initialization"]["drafts"]["created"] == 0
    assert repeat_payload["initialization"]["drafts"]["existing_seed_managed"] == 4
    assert repeat_payload["initialization"]["revisions"]["existing"] == 4
    assert repeat_payload["initialization"]["initialization_audit"]["existing"] == 1


def test_office_evidence_receipt_api_records_local_proof_but_keeps_hold(
    client: TestClient,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.product_strategy import office_evidence_service as service

    monkeypatch.setattr(service, "OFFICE_EVIDENCE_STORAGE_ROOT", tmp_path / "office")
    monkeypatch.setattr(service, "_structural_validation", lambda *_args, **_kwargs: {"status": "pass"})
    monkeypatch.setattr(
        service,
        "_run_headless_roundtrip",
        lambda *_args, **_kwargs: {
            "office_roundtrip_status": "passed",
            "visual_evidence_status": "rendered_unreviewed",
            "page_count": 2,
            "rendered_pdf_sha256": "d" * 64,
            "rendered_pages": [
                {"file_name": "page-1.png", "size_bytes": 200, "sha256": "e" * 64},
                {"file_name": "page-2.png", "size_bytes": 240, "sha256": "f" * 64},
            ],
            "engine": "libreoffice_headless",
            "failure_reason": "",
        },
    )
    monkeypatch.setattr(service, "_runtime_capability_summary", lambda: {"platform": "test"})

    empty = client.get("/api/product-strategy/office-evidence-receipts")
    assert empty.status_code == 200, empty.text
    assert empty.json()["receipt_count"] == 0
    assert empty.json()["acceptance_status"] == "hold"

    missing = client.post(
        "/api/product-strategy/office-evidence-receipts",
        json={
            "artifact_key": "missing",
            "file_name": "review.docx",
            "media_type": "",
            "file_base64": base64.b64encode(b"fixture").decode("ascii"),
            "source_version": "2.10.5-test",
        },
    )
    assert missing.status_code == 409, missing.text
    assert missing.json()["detail"]["code"] == "artifact_acceptance_draft_required"

    assert client.post("/api/product-strategy/decision-context-packets/initialize").status_code == 200
    artifacts = client.post("/api/product-strategy/artifact-acceptance/initialize").json()["artifacts"]
    created = client.post(
        "/api/product-strategy/office-evidence-receipts",
        json={
            "artifact_key": artifacts[0]["artifact_key"],
            "file_name": "review.docx",
            "media_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "file_base64": base64.b64encode(b"fixture").decode("ascii"),
            "source_version": "2.10.5-test",
            "required_texts": ["结论"],
        },
    )
    assert created.status_code == 201, created.text
    receipt = created.json()["receipt"]
    assert receipt["office_roundtrip_status"] == "passed"
    assert receipt["visual_evidence_status"] == "rendered_unreviewed"
    assert receipt["acceptance_status"] == "hold"
    assert receipt["human_review_status"] == "missing"
    assert receipt["release_impact"] == "none"

    listed = client.get("/api/product-strategy/office-evidence-receipts")
    assert listed.status_code == 200, listed.text
    assert listed.json()["receipt_count"] == 1
    assert listed.json()["rendered_unreviewed_count"] == 1
