from __future__ import annotations

import base64
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
import uuid

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core import config as app_config
from app.models.product_strategy_office_evidence_entities import ProductStrategyOfficeEvidenceReceipt
from app.services.product_strategy import office_evidence_service as service
from app.services.product_strategy.artifact_acceptance_service import initialize_artifact_acceptance
from app.services.product_strategy.catalog import canonical_digest
from app.services.product_strategy.context_packet_service import initialize_decision_context_packets


@pytest.mark.parametrize("prior_revision", ["20260906_0035", "20260909_0038"])
def test_upgrade_preserves_receipts_and_enforces_fingerprint_and_immutability(
    tmp_path, monkeypatch, prior_revision,
):
    """Exercise real upgrade paths, including a DB that already ran the broken migration."""
    backend = Path(__file__).resolve().parents[1]
    url = f"sqlite:///{tmp_path / 'upgrade.db'}"
    monkeypatch.setattr(app_config, "get_settings", lambda: SimpleNamespace(database_url=url))
    alembic = Config(str(backend / "alembic.ini"))
    alembic.set_main_option("script_location", str(backend / "alembic"))
    command.upgrade(alembic, prior_revision)
    engine = create_engine(url)
    with Session(engine) as db:
        initialize_decision_context_packets(db)
        artifact = initialize_artifact_acceptance(db)["artifacts"][0]

    # A pre-fingerprint receipt retains its original digest/key and remains readable.
    snapshot = {
        "office_evidence_version": "2.10.5",
        "artifact_key": artifact["artifact_key"],
        "artifact_revision": artifact["revision"],
        "artifact_revision_digest": artifact["revision_digest"],
        "file_name": "legacy.docx", "media_type": service.ALLOWED_MEDIA_TYPES[".docx"],
        "file_size_bytes": 10, "file_sha256": "a" * 64,
        "storage_ref": "office-evidence/legacy/source.docx", "source_version": "2.10.5",
        "validator_version": service.VALIDATOR_VERSION,
        "structure_status": "pass", "office_roundtrip_status": "unavailable",
        "visual_evidence_status": "missing", "page_count": 0, "rendered_pdf_sha256": None,
        "rendered_pages": [], "validation": {"manual_gates": ["named_human_visual_review_missing"]},
        "evidence_level": "local_runtime_evidence", "human_review_status": "missing",
        "acceptance_status": "hold", "blocking_status": "blocked", "can_auto_accept": False,
        "can_auto_approve_release": False, "production_status": "not_authorized", "release_impact": "none",
    }
    legacy_digest = canonical_digest(snapshot)
    legacy_values = {key: value for key, value in snapshot.items() if key not in {
        "office_evidence_version", "release_impact", "rendered_pages", "validation",
    }}
    legacy_values.update(
        id=uuid.uuid4().hex, receipt_key="legacy-office-receipt", receipt_digest=legacy_digest,
        artifact_acceptance_draft_id=artifact["id"].replace("-", ""),
        rendered_pages_payload=snapshot["rendered_pages"], validation_payload=snapshot["validation"],
        created_at=datetime.now(UTC),
    )
    office = Table("product_strategy_office_evidence_receipts", MetaData(), autoload_with=engine)
    with engine.begin() as connection:
        connection.execute(office.insert(), legacy_values)

    command.upgrade(alembic, "head")
    constraints = {item["name"] for item in inspect(engine).get_unique_constraints(office.name)}
    assert "uq_product_strategy_office_receipt_input_digest" in constraints
    assert "uq_product_strategy_office_receipt_artifact_file" not in constraints
    assert "uq_product_strategy_office_receipt_revision_file" not in constraints
    with Session(engine) as db:
        legacy = db.scalar(select(ProductStrategyOfficeEvidenceReceipt).where(
            ProductStrategyOfficeEvidenceReceipt.receipt_key == "legacy-office-receipt",
        ))
        assert service._serialize(legacy)["receipt_digest"] == legacy_digest
        assert legacy.input_digest is None

    monkeypatch.setattr(service, "OFFICE_EVIDENCE_STORAGE_ROOT", tmp_path / "office")
    monkeypatch.setattr(service, "_structural_validation", lambda *_a, **_kw: {"status": "pass"})
    monkeypatch.setattr(service, "_runtime_capability_summary", lambda: {"platform": "test"})
    monkeypatch.setattr(service, "_run_headless_roundtrip", lambda *_a: {
        "office_roundtrip_status": "unavailable", "visual_evidence_status": "missing", "page_count": 0,
        "rendered_pdf_sha256": None, "rendered_pages": [], "engine": "none", "failure_reason": "test",
    })
    payload = {
        "artifact_key": artifact["artifact_key"], "file_name": "review.docx",
        "media_type": service.ALLOWED_MEDIA_TYPES[".docx"],
        "file_base64": base64.b64encode(b"same-office-file").decode("ascii"),
        "source_version": "2.10.5-test", "required_texts": ["first review"],
    }
    with Session(engine) as db:
        first = service.create_office_evidence_receipt(db, **payload)
        second = service.create_office_evidence_receipt(db, **{**payload, "required_texts": ["second review"]})
        retry = service.create_office_evidence_receipt(db, **payload)
        assert first["outcome"] == second["outcome"] == "created"
        assert first["receipt"]["receipt_key"] != second["receipt"]["receipt_key"]
        assert first["receipt"]["file_sha256"] == second["receipt"]["file_sha256"]
        assert retry["outcome"] == "existing"
        assert retry["receipt"]["receipt_digest"] == first["receipt"]["receipt_digest"]
        assert service.list_office_evidence_receipts(db)["receipt_count"] == 3

    # Core/raw SQL bypasses ORM events, so this specifically proves migrated DB triggers.
    for sql in (
        "UPDATE product_strategy_office_evidence_receipts SET source_version = 'changed' WHERE receipt_key = :key",
        "DELETE FROM product_strategy_office_evidence_receipts WHERE receipt_key = :key",
    ):
        with pytest.raises(DBAPIError, match="Office evidence receipts are append-only"):
            with engine.begin() as connection:
                connection.execute(text(sql), {"key": first["receipt"]["receipt_key"]})
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    engine.dispose()
