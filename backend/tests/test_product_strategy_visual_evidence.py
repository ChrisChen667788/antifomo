from __future__ import annotations

import base64
import hashlib
import io
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401
from app.api.product_strategy import router
from app.db.base import Base
from app.db.session import get_db
from app.models.product_strategy_artifact_acceptance_entities import ProductStrategyArtifactAcceptanceDraft
from app.models.product_strategy_visual_evidence_entities import ProductStrategyVisualEvidenceRevision
from app.schemas.product_strategy_visual_evidence import VisualEvidenceCreateRequest
from app.services.product_strategy import office_evidence_service as office
from app.services.product_strategy import visual_evidence_service as service
from app.services.product_strategy.artifact_acceptance_service import initialize_artifact_acceptance
from app.services.product_strategy.context_packet_service import initialize_decision_context_packets


def png(color="white", size=(100, 100)) -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", size, color).save(stream, format="PNG")
    return stream.getvalue()


@pytest.fixture()
def context(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'test.sqlite'}", connect_args={"check_same_thread": False, "timeout": 5})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(service, "VISUAL_EVIDENCE_STORAGE_ROOT", tmp_path / "visual")
    monkeypatch.setattr(office, "OFFICE_EVIDENCE_STORAGE_ROOT", tmp_path / "office")
    monkeypatch.setattr(office, "_structural_validation", lambda *_a, **_kw: {"status": "pass"})
    monkeypatch.setattr(office, "_runtime_capability_summary", lambda: {"platform": "test"})
    monkeypatch.setattr(office, "_run_headless_roundtrip", lambda *_a: {
        "office_roundtrip_status": "passed", "visual_evidence_status": "rendered_unreviewed",
        "page_count": 2, "rendered_pdf_sha256": "a" * 64,
        "rendered_pages": [
            {"file_name": "page-10.png", "sha256": hashlib.sha256(png("red")).hexdigest()},
            {"file_name": "page-2.png", "sha256": hashlib.sha256(png()).hexdigest()},
        ], "engine": "test", "failure_reason": "",
    })
    with factory() as db:
        initialize_decision_context_packets(db)
        artifact = initialize_artifact_acceptance(db)["artifacts"][0]
        receipt = office.create_office_evidence_receipt(db, artifact_key=artifact["artifact_key"], file_name="fixture.docx", media_type="", file_base64=base64.b64encode(b"office-fixture").decode(), source_version="test")["receipt"]
    app = FastAPI()
    app.include_router(router)
    def db_override():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = db_override
    with TestClient(app) as client:
        yield factory, receipt, client
    engine.dispose()


def request(receipt, **overrides):
    return {
        "office_receipt_key": receipt["receipt_key"], "expected_office_receipt_digest": receipt["receipt_digest"],
        "surface_key": "desktop-home", "capture_kind": "desktop_browser", "source_version": "2.10.6-test",
        "file_name": "home.png", "image_base64": base64.b64encode(png()).decode(),
        "viewport": {"width": 100, "height": 100, "device_scale_factor": 1},
        "checklist": {key: {"status": "unknown", "note": ""} for key in ("clipping", "overlap", "legibility", "assets", "pagination")},
        "notes": "", "previous_revision_digest": None, **overrides,
    }


URL = "/api/product-strategy/visual-evidence-revisions"


def test_api_records_png_and_field_revision_then_rejects_stale_update(context):
    factory, receipt, client = context
    assert client.get(URL).json()["revision_count"] == 0
    payload = request(receipt)
    response = client.post(URL, json=payload)
    assert response.status_code == 201, response.text
    first = response.json()["revision"]
    assert first["revision"] == 1 and first["image_width"] == 100
    assert first["artifact_revision_digest"] == receipt["artifact_revision_digest"]
    assert first["acceptance_status"] == "hold" and first["human_review_status"] == "missing"
    assert first["can_auto_accept"] is False and first["can_auto_approve_release"] is False
    retry = client.post(URL, json=payload)
    assert retry.json()["outcome"] == "existing"
    assert retry.json()["revision"]["revision_digest"] == first["revision_digest"]
    payload["previous_revision_digest"] = first["revision_digest"]
    payload["checklist"]["clipping"] = {"status": "fail", "note": "Bottom caption clipped"}
    second = client.post(URL, json=payload).json()["revision"]
    assert second["revision"] == 2 and second["review_status"] == "needs_revision"
    diff = {row["field_path"]: row for row in second["field_level_diff"]}
    assert diff["checklist.clipping.status"]["before"] == "unknown"
    assert diff["checklist.clipping.status"]["after"] == "fail"
    assert client.post(URL, json=payload).json()["deduplicated"] is True
    payload["notes"] = "stale submission"
    assert client.post(URL, json=payload).status_code == 409
    assert client.post(URL, json=request(receipt)).status_code == 409
    listed = client.get(URL).json()
    assert [row["revision"] for row in listed["revisions"]] == [2, 1]
    assert listed["needs_revision_count"] == 1
    with factory() as db:
        original = db.scalar(select(ProductStrategyVisualEvidenceRevision).where(ProductStrategyVisualEvidenceRevision.revision == 1))
        assert original.snapshot_payload["checklist"]["clipping"]["status"] == "unknown"
    assert (service.VISUAL_EVIDENCE_STORAGE_ROOT / f"{first['image_sha256']}.png").read_bytes() == png()


def test_responsive_summary_is_read_only_and_does_not_claim_real_device(context):
    _, _, client = context
    response = client.get("/api/product-strategy/responsive-evidence")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["responsive_evidence_version"] == "2.11.3"
    assert payload["desktop_browser_count"] == 0
    assert payload["mobile_viewport_count"] == 0
    assert payload["physical_device_capture"] is False
    assert payload["production_performance_benchmark"] is False
    assert payload["acceptance_status"] == "hold"


@pytest.mark.parametrize("name", ["../x.png", "dir/x.png", r"C:\x.png", r"dir\x.png", "file\n.png"])
def test_rejects_unsafe_file_names(context, name):
    _, receipt, client = context
    response = client.post(URL, json=request(receipt, file_name=name))
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_file_name"


@pytest.mark.parametrize("data", [b"not-an-image", b"\x89PNG\r\n\x1a\ntruncated", png()[:-12]])
def test_rejects_fake_and_truncated_png(context, data):
    _, receipt, client = context
    response = client.post(URL, json=request(receipt, image_base64=base64.b64encode(data).decode()))
    assert response.status_code == 400
    assert client.get(URL).json()["revision_count"] == 0


def test_rejects_dimensions_limit_and_bad_viewport(context, monkeypatch):
    _, receipt, client = context
    assert client.post(URL, json=request(receipt, viewport={"width": 200, "height": 100, "device_scale_factor": 1})).status_code == 400
    monkeypatch.setattr(service, "MAX_IMAGE_PIXELS", 9999)
    assert client.post(URL, json=request(receipt)).json()["detail"]["code"] == "image_dimensions_exceeded"
    monkeypatch.setattr(service, "MAX_IMAGE_BYTES", 2)
    assert client.post(URL, json=request(receipt)).json()["detail"]["code"] == "image_too_large"


def test_office_page_uses_number_and_digest_not_array_position(context):
    _, receipt, client = context
    payload = request(receipt, capture_kind="office_page", viewport=None, office_page_number=2)
    assert client.post(URL, json=payload).status_code == 201
    payload["office_page_number"] = 10
    response = client.post(URL, json=payload)
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "office_page_digest_mismatch"
    payload.update(image_base64=base64.b64encode(png("red")).decode(), surface_key="office-page-10")
    assert client.post(URL, json=payload).status_code == 201


def test_missing_receipt_wrong_digest_and_stale_artifact_fail_closed(context):
    factory, receipt, client = context
    assert client.post(URL, json=request(receipt, office_receipt_key="missing")).status_code == 409
    assert client.post(URL, json=request(receipt, expected_office_receipt_digest="0" * 64)).status_code == 409
    with factory() as db:
        draft = db.scalar(select(ProductStrategyArtifactAcceptanceDraft).where(ProductStrategyArtifactAcceptanceDraft.artifact_key == receipt["artifact_key"]))
        draft.revision += 1
        draft.revision_digest = "9" * 64
        db.commit()
    response = client.post(URL, json=request(receipt))
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "office_receipt_stale"


def test_schema_forbids_acceptance_claims_and_missing_browser_context(context):
    _, receipt, client = context
    assert client.post(URL, json=request(receipt, acceptance_status="accepted")).status_code == 422
    assert client.post(URL, json=request(receipt, viewport=None)).status_code == 422
    assert client.post(URL, json=request(receipt, capture_kind="office_page")).status_code == 422


def test_orm_and_sql_cannot_mutate_revision(context):
    factory, receipt, client = context
    assert client.post(URL, json=request(receipt)).status_code == 201
    with factory() as db:
        row = db.scalar(select(ProductStrategyVisualEvidenceRevision))
        row.surface_key = "changed"
        with pytest.raises(ValueError, match="append-only"):
            db.commit()
        db.rollback()
        for statement in ("UPDATE product_strategy_visual_evidence_revisions SET revision = 99", "DELETE FROM product_strategy_visual_evidence_revisions"):
            with pytest.raises(DatabaseError, match="append-only"):
                db.execute(text(statement))
            db.rollback()


def test_parallel_identical_writes_deduplicate_and_divergent_writes_conflict(context):
    factory, receipt, client = context
    def submit(data):
        with factory() as db:
            try:
                return service.create_visual_evidence_revision(db, payload=VisualEvidenceCreateRequest.model_validate(data))["outcome"]
            except service.VisualEvidenceError as error:
                return error.code
    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(submit, [request(receipt)] * 4))
    assert outcomes.count("created") == 1
    assert outcomes.count("existing") == 3
    previous = client.get(URL).json()["revisions"][0]["revision_digest"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(submit, [request(receipt, previous_revision_digest=previous, notes=note) for note in ("one", "two")]))
    assert outcomes.count("created") == 1
    assert outcomes.count("revision_conflict") == 1
    assert client.get(URL).json()["revision_count"] == 2


def test_office_same_file_new_artifact_revision_creates_isolated_receipt(context):
    factory, receipt, _ = context
    with factory() as db:
        draft = db.scalar(select(ProductStrategyArtifactAcceptanceDraft).where(ProductStrategyArtifactAcceptanceDraft.artifact_key == receipt["artifact_key"]))
        draft.revision += 1
        draft.revision_digest = "8" * 64
        db.commit()
        result = office.create_office_evidence_receipt(db, artifact_key=receipt["artifact_key"], file_name="fixture.docx", media_type="", file_base64=base64.b64encode(b"office-fixture").decode(), source_version="test")
    assert result["outcome"] == "created"
    assert result["receipt"]["file_sha256"] == receipt["file_sha256"]
    assert result["receipt"]["artifact_revision"] == receipt["artifact_revision"] + 1
    assert result["receipt"]["storage_ref"] != receipt["storage_ref"]
    assert result["receipt"]["receipt_key"] != receipt["receipt_key"]
