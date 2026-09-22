from __future__ import annotations

import base64
import hashlib
import io

import pytest
from PIL import Image
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db.base import Base
from app.models.product_strategy_human_acceptance_entities import ProductStrategyHumanAcceptanceEvent
from app.schemas.product_strategy_human_acceptance import HumanAcceptanceCreateRequest
from app.schemas.product_strategy_visual_evidence import VisualEvidenceCreateRequest
from app.services.product_strategy import human_acceptance_service as human
from app.services.product_strategy import office_evidence_service as office
from app.services.product_strategy import visual_evidence_service as visual
from app.services.product_strategy.artifact_acceptance_service import initialize_artifact_acceptance
from app.services.product_strategy.context_packet_service import initialize_decision_context_packets


def png(color: str = "white") -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (80, 80), color).save(stream, format="PNG")
    return stream.getvalue()


@pytest.fixture()
def review_context(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(office, "OFFICE_EVIDENCE_STORAGE_ROOT", tmp_path / "office")
    monkeypatch.setattr(visual, "VISUAL_EVIDENCE_STORAGE_ROOT", tmp_path / "visual")
    monkeypatch.setattr(office, "_structural_validation", lambda *_args, **_kwargs: {"status": "pass"})
    monkeypatch.setattr(office, "_runtime_capability_summary", lambda: {"platform": "test"})
    monkeypatch.setattr(office, "_run_headless_roundtrip", lambda *_args: {
        "office_roundtrip_status": "passed", "visual_evidence_status": "rendered_unreviewed", "page_count": 1,
        "rendered_pdf_sha256": "a" * 64, "rendered_pages": [{"file_name": "page-1.png", "sha256": hashlib.sha256(png()).hexdigest()}],
        "engine": "test", "failure_reason": "",
    })
    with factory() as db:
        initialize_decision_context_packets(db)
        artifact = initialize_artifact_acceptance(db)["artifacts"][0]
        receipt = office.create_office_evidence_receipt(
            db, artifact_key=artifact["artifact_key"], file_name="fixture.docx", media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            file_base64=base64.b64encode(b"fixture-office").decode(), source_version="test",
        )["receipt"]
        checklist = {key: {"status": "pass", "note": "checked"} for key in ("clipping", "overlap", "legibility", "assets", "pagination")}
        revision = visual.create_visual_evidence_revision(db, payload=VisualEvidenceCreateRequest(
            office_receipt_key=receipt["receipt_key"], expected_office_receipt_digest=receipt["receipt_digest"],
            surface_key="desktop-home", capture_kind="desktop_browser", source_version="test", file_name="home.png",
            image_base64=base64.b64encode(png()).decode(), viewport={"width": 80, "height": 80, "device_scale_factor": 1},
            checklist=checklist, notes="fixture",
        ))["revision"]
    yield factory, artifact, receipt, revision
    engine.dispose()


def request(receipt, artifact, revision, **changes) -> HumanAcceptanceCreateRequest:
    values = {
        "idempotency_key": "review-fixture-1", "office_receipt_key": receipt["receipt_key"],
        "expected_office_receipt_digest": receipt["receipt_digest"], "expected_artifact_revision_digest": artifact["revision_digest"],
        "visual_revision_digests": [revision["revision_digest"]], "reviewer_identity": "reviewer@example.org", "author_identity": "author@example.org",
        "decision": "approve", "review_scope": "fixture review", "rationale": "Readable and complete fixture evidence.",
    }
    values.update(changes)
    return HumanAcceptanceCreateRequest(**values)


def test_named_acceptance_is_append_only_and_self_attested(review_context):
    factory, artifact, receipt, revision = review_context
    with factory() as db:
        first = human.create_event(db, request(receipt, artifact, revision))
        assert first["outcome"] == "created"
        assert first["event"]["identity_status"] == "self_attested"
        assert first["event"]["acceptance_status"] == "hold"
        duplicate = human.create_event(db, request(receipt, artifact, revision))
        assert duplicate["outcome"] == "existing"
        with pytest.raises(human.HumanAcceptanceError, match="新事件"):
            human.create_event(db, request(receipt, artifact, revision, idempotency_key="review-fixture-2", previous_event_digest=None))
        row = db.scalar(select(ProductStrategyHumanAcceptanceEvent))
        row.snapshot_payload["decision"] = "tampered"
        with pytest.raises(human.HumanAcceptanceError, match="摘要不一致"):
            human.serialize_event(row)
        db.rollback()
        with pytest.raises(DatabaseError, match="append-only"):
            db.execute(text("DELETE FROM product_strategy_human_acceptance_events"))
            db.commit()


def test_release_bridge_is_read_only_and_reports_real_missing_gates(review_context):
    factory, artifact, receipt, revision = review_context
    with factory() as db:
        human.create_event(db, request(receipt, artifact, revision))
        bridge = human.release_bridge(db, artifact["artifact_key"])
    assert bridge["bridge_version"] == "2.10.8"
    assert bridge["read_only"] is True
    assert bridge["acceptance_status"] == "hold"
    assert bridge["blocking_status"] == "blocked"
    assert {"authenticated_independent_reviewer_missing", "customer_acceptance_missing", "production_authorization_missing"} <= set(bridge["blockers"])
    assert "upstream_release_readiness_not_passed" in bridge["blockers"]
    assert len(bridge["bridge_digest"]) == 64


def test_acceptance_request_rejects_same_identity():
    with pytest.raises(ValueError, match="不同身份"):
        HumanAcceptanceCreateRequest(
            idempotency_key="same", office_receipt_key="receipt", expected_office_receipt_digest="a" * 64,
            expected_artifact_revision_digest="b" * 64, visual_revision_digests=["c" * 64], reviewer_identity="同一人", author_identity="同一人",
            decision="approve", review_scope="scope", rationale="reason",
        )
