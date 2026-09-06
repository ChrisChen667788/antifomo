from __future__ import annotations

import base64
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db.base import Base
from app.models.product_strategy_artifact_acceptance_entities import ProductStrategyArtifactAcceptanceDraft
from app.models.product_strategy_office_evidence_entities import ProductStrategyOfficeEvidenceReceipt
from app.services.product_strategy.artifact_acceptance_service import initialize_artifact_acceptance
from app.services.product_strategy.context_packet_service import initialize_decision_context_packets
from app.services.product_strategy import office_evidence_service as service
from app.services.work_tasks.office_roundtrip import validate_pdf_bytes


def _session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _render_result() -> dict:
    return {
        "office_roundtrip_status": "passed",
        "visual_evidence_status": "rendered_unreviewed",
        "page_count": 1,
        "rendered_pdf_sha256": "b" * 64,
        "rendered_pages": [{"file_name": "page-1.png", "size_bytes": 128, "sha256": "c" * 64}],
        "engine": "libreoffice_headless",
        "failure_reason": "",
    }


def test_pdf_validator_accepts_word_pdf_1_x_headers() -> None:
    assert validate_pdf_bytes(b"%PDF-1.7\n/Type /Page\n%%EOF")["status"] == "pass"


def test_receipt_binds_artifact_revision_and_remains_hold(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "OFFICE_EVIDENCE_STORAGE_ROOT", tmp_path / "office")
    monkeypatch.setattr(service, "_structural_validation", lambda *_args, **_kwargs: {"status": "pass"})
    monkeypatch.setattr(service, "_run_headless_roundtrip", lambda *_args, **_kwargs: _render_result())
    monkeypatch.setattr(service, "_runtime_capability_summary", lambda: {"platform": "test"})

    for db in _session():
        initialize_decision_context_packets(db)
        initialized = initialize_artifact_acceptance(db)
        artifact = initialized["artifacts"][0]
        payload = base64.b64encode(b"deterministic-office-fixture").decode("ascii")

        created = service.create_office_evidence_receipt(
            db,
            artifact_key=artifact["artifact_key"],
            file_name="review.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            file_base64=payload,
            source_version="2.10.5-test",
            required_texts=["证据"],
        )

        assert created["outcome"] == "created"
        receipt = created["receipt"]
        assert receipt["artifact_revision"] == artifact["revision"]
        assert receipt["artifact_revision_digest"] == artifact["revision_digest"]
        assert receipt["structure_status"] == "pass"
        assert receipt["office_roundtrip_status"] == "passed"
        assert receipt["visual_evidence_status"] == "rendered_unreviewed"
        assert receipt["human_review_status"] == "missing"
        assert receipt["acceptance_status"] == "hold"
        assert receipt["blocking_status"] == "blocked"
        assert receipt["can_auto_accept"] is False
        assert receipt["can_auto_approve_release"] is False
        assert receipt["release_impact"] == "none"
        assert (service.OFFICE_EVIDENCE_STORAGE_ROOT / receipt["file_sha256"] / "source.docx").exists()

        repeated = service.create_office_evidence_receipt(
            db,
            artifact_key=artifact["artifact_key"],
            file_name="review.docx",
            media_type="",
            file_base64=payload,
            source_version="ignored-on-dedupe",
        )
        assert repeated["outcome"] == "existing"
        assert repeated["deduplicated"] is True
        assert repeated["receipt"]["receipt_digest"] == receipt["receipt_digest"]
        assert len(db.scalars(select(ProductStrategyOfficeEvidenceReceipt)).all()) == 1

        landscape = service.list_office_evidence_receipts(db)
        assert landscape["receipt_count"] == 1
        assert landscape["local_roundtrip_passed_count"] == 1
        assert landscape["rendered_unreviewed_count"] == 1
        assert landscape["requires_named_human_review"] is True
        assert landscape["acceptance_status"] == "hold"


def test_receipt_rejects_unbound_or_unsafe_inputs(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "OFFICE_EVIDENCE_STORAGE_ROOT", tmp_path / "office")
    monkeypatch.setattr(service, "_structural_validation", lambda *_args, **_kwargs: {"status": "pass"})
    payload = base64.b64encode(b"fixture").decode("ascii")
    for db in _session():
        with pytest.raises(service.OfficeEvidenceError) as missing:
            service.create_office_evidence_receipt(
                db,
                artifact_key="missing",
                file_name="review.docx",
                media_type="",
                file_base64=payload,
                source_version="test",
            )
        assert missing.value.code == "artifact_acceptance_draft_required"

        initialize_decision_context_packets(db)
        initialize_artifact_acceptance(db)
        draft = db.scalar(select(ProductStrategyArtifactAcceptanceDraft))
        assert draft is not None

        with pytest.raises(service.OfficeEvidenceError) as unsafe:
            service.create_office_evidence_receipt(
                db,
                artifact_key=draft.artifact_key,
                file_name="../review.docx",
                media_type="",
                file_base64=payload,
                source_version="test",
            )
        assert unsafe.value.code == "invalid_file_name"

        with pytest.raises(service.OfficeEvidenceError) as unsupported:
            service.create_office_evidence_receipt(
                db,
                artifact_key=draft.artifact_key,
                file_name="review.pdf",
                media_type="application/pdf",
                file_base64=payload,
                source_version="test",
            )
        assert unsupported.value.code == "unsupported_office_format"

        with pytest.raises(service.OfficeEvidenceError) as incomplete:
            service.create_office_evidence_receipt(
                db,
                artifact_key=draft.artifact_key,
                file_name="review.docx",
                media_type="",
                file_base64=payload,
                source_version="test",
                rendered_pdf_base64=base64.b64encode(b"%PDF-1.4\n%%EOF").decode("ascii"),
            )
        assert incomplete.value.code == "incomplete_render_evidence"
