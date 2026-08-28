from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.services.release_readiness_service import _evaluate_screenshot_manifest, build_release_readiness_snapshot


@contextmanager
def _session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_release_readiness_snapshot_aggregates_current_gates(tmp_path) -> None:
    stability_report = tmp_path / "stability.json"
    stability_report.write_text(
        json.dumps(
            {
                "status": "passed",
                "generatedAt": "2026-07-09T00:00:00+00:00",
                "passed": 11,
                "failed": 0,
            }
        ),
        encoding="utf-8",
    )
    screenshot_manifest = tmp_path / "screenshot-manifest.json"
    screenshot_manifest.write_text(
        json.dumps(
            {
                "version": "2.9.5",
                "release_tag": "v2.9.5+20260814",
                "quality_gate": {
                    "expected_screenshot_count": 30,
                    "accepted_screenshot_count": 30,
                },
                "screenshots": [],
            }
        ),
        encoding="utf-8",
    )

    with _session() as db:
        snapshot = build_release_readiness_snapshot(
            db,
            now=datetime(2026, 7, 9, tzinfo=UTC),
            review_path=tmp_path / "missing-review.json",
            calibration_path=tmp_path / "missing-calibration.json",
            proof_path=tmp_path / "missing-proof.json",
            stability_report_path=stability_report,
            screenshot_manifest_path=screenshot_manifest,
            visual_manifest_paths=[],
        )

    gate_keys = {gate["key"] for gate in snapshot["gates"]}
    assert gate_keys == {
        "health",
        "research_diagnostics",
        "evidence_governance",
        "hard_failure_policy",
        "low_quality_audit",
        "independent_review",
        "expert_calibration",
        "architecture_engineering",
        "executable_validation",
        "visual_gate",
        "research_experience",
        "assurance_program",
        "industry_retrieval_assurance",
        "industry_retrieval_evidence_operations",
    }
    assert snapshot["release_version"] == "2.9.5-retrieval-evidence-operations-command-center"
    assert snapshot["summary_lines"][0].startswith("2.9.5 检索保证、证据运营与质量控制台：")
    assert next(gate for gate in snapshot["gates"] if gate["key"] == "evidence_governance")["status"] == "pass"
    assert next(gate for gate in snapshot["gates"] if gate["key"] == "hard_failure_policy")["status"] == "pass"
    assert next(gate for gate in snapshot["gates"] if gate["key"] == "architecture_engineering")["status"] == "pass"
    assert snapshot["overall_status"] == "blocked"
    assert any(action["gate_key"] == "independent_review" for action in snapshot["next_actions"])
    assert any(
        command["gate_key"] == "independent_review" and "review:validate" in command["command"]
        for command in snapshot["operator_commands"]
    )
    assert any(artifact["gate_key"] == "independent_review" for artifact in snapshot["artifacts"])
    assert any(artifact["gate_key"] == "visual_gate" for artifact in snapshot["artifacts"])
    assert any(artifact["gate_key"] == "expert_calibration" for artifact in snapshot["artifacts"])
    assert any(artifact["gate_key"] == "executable_validation" for artifact in snapshot["artifacts"])
    assert next(gate for gate in snapshot["gates"] if gate["key"] == "assurance_program")["status"] == "blocked"
    assert next(gate for gate in snapshot["gates"] if gate["key"] == "industry_retrieval_assurance")["status"] == "blocked"
    assert next(gate for gate in snapshot["gates"] if gate["key"] == "industry_retrieval_evidence_operations")["status"] == "blocked"


def test_release_readiness_visual_gate_accepts_current_manifests(tmp_path) -> None:
    stability_report = tmp_path / "stability.json"
    stability_report.write_text(
        json.dumps(
            {
                "status": "passed",
                "generatedAt": "2026-07-09T00:00:00+00:00",
                "passed": 11,
                "failed": 0,
            }
        ),
        encoding="utf-8",
    )
    screenshot_manifest = tmp_path / "screenshot-manifest.json"
    screenshot_manifest.write_text(
        json.dumps(
            {
                "version": "2.9.5",
                "release_tag": "v2.9.5+20260814",
                "quality_gate": {
                    "expected_screenshot_count": 30,
                    "accepted_screenshot_count": 30,
                },
                "screenshots": [],
            }
        ),
        encoding="utf-8",
    )
    visual_manifest = tmp_path / "visual-baseline-manifest.json"
    visual_manifest.write_text(
        json.dumps(
            {
                "baseline_id": "anti-fomo-p2.6-formal-artifact-visual-baseline",
                "summary": {
                    "sample_count": 3,
                    "artifact_count": 9,
                    "failed_validation_count": 0,
                    "failed_quicklook_count": 0,
                },
                "artifacts": [
                    {
                        "file": "sample.pdf",
                        "validation": {"status": "pass"},
                        "quicklook": {"status": "pass"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    roundtrip_manifest = tmp_path / "roundtrip-manifest.json"
    roundtrip_manifest.write_text(
        json.dumps(
            {
                "artifacts": [
                    {
                        "file": "sample.docx",
                        "status": "pass",
                        "quicklook": {"status": "skip", "reason": "quicklook scope pdf"},
                        "libreoffice_conversion": {
                            "status": "skip",
                            "reason": "LibreOffice CLI not available",
                        },
                    },
                    {
                        "file": "sample.pdf",
                        "status": "pass",
                        "quicklook": {"status": "pass"},
                    },
                ],
                "summary": {
                    "artifact_count": 2,
                    "failed_structure_count": 0,
                    "failed_quicklook_count": 0,
                    "failed_libreoffice_count": 0,
                    "quicklook_rendered_count": 1,
                    "libreoffice_skipped_count": 1,
                },
            }
        ),
        encoding="utf-8",
    )

    with _session() as db:
        snapshot = build_release_readiness_snapshot(
            db,
            now=datetime(2026, 7, 9, tzinfo=UTC),
            review_path=tmp_path / "missing-review.json",
            calibration_path=tmp_path / "missing-calibration.json",
            proof_path=tmp_path / "missing-proof.json",
            stability_report_path=stability_report,
            screenshot_manifest_path=screenshot_manifest,
            visual_manifest_paths=[visual_manifest, roundtrip_manifest],
        )

    gates = {gate["key"]: gate for gate in snapshot["gates"]}
    assert gates["visual_gate"]["status"] == "pass"
    assert gates["visual_gate"]["score"] == 100
    assert not any(command["gate_key"] == "visual_gate" for command in snapshot["operator_commands"])


def test_release_readiness_rejects_stale_screenshot_version(tmp_path) -> None:
    screenshot_manifest = tmp_path / "screenshot-manifest.json"
    screenshot_manifest.write_text(
        json.dumps(
            {
                "version": "1.8.2",
                "quality_gate": {
                    "expected_screenshot_count": 30,
                    "accepted_screenshot_count": 30,
                },
            }
        ),
        encoding="utf-8",
    )

    evidence = _evaluate_screenshot_manifest(screenshot_manifest)

    assert evidence["status"] == "blocked"
    assert evidence["details"]["required_version"] == "2.9.5"
    assert "当前版本要求 2.9.5" in evidence["summary"]


def test_release_readiness_api_returns_gate_payload() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)

    def override_get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.get("/api/system/release-readiness")
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()

    assert response.status_code == 200
    payload = response.json()
    assert payload["release_version"] == "2.9.5-retrieval-evidence-operations-command-center"
    assert {gate["key"] for gate in payload["gates"]} >= {"health", "research_diagnostics", "independent_review"}
    assert {gate["key"] for gate in payload["gates"]} >= {"assurance_program"}
    assert {gate["key"] for gate in payload["gates"]} >= {"industry_retrieval_assurance"}
    assert {gate["key"] for gate in payload["gates"]} >= {"industry_retrieval_evidence_operations"}
    assert any(command["gate_key"] == "independent_review" for command in payload["operator_commands"])
    assert any(artifact["gate_key"] == "visual_gate" for artifact in payload["artifacts"])
