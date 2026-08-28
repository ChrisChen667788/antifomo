from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import User
from app.models.research_entities import ResearchJob
from app.schemas.research import ResearchReportResponse
from app.services.research_assurance_service import build_research_assurance_snapshot


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


def _formal_report_payload(now: datetime) -> dict:
    report = ResearchReportResponse(
        keyword="上海文旅 AI",
        report_title="上海文旅 AI 研究样本",
        executive_summary="用于验证质量保障聚合的最小正式研报样本。",
        consulting_angle="验证证据、实体、主张、成本与交付真值的聚合逻辑。",
        source_count=1,
        generated_at=now,
        research_scope_contract={
            "keyword": "上海文旅 AI",
            "task_type": "industry_research",
            "industries": ["文旅"],
            "status": "ready",
        },
        research_evidence_gate={
            "enforced": True,
            "status": "evidence_ready",
            "passed": True,
            "formal_report_allowed": True,
            "local_decision_source_count": 2,
        },
        research_citation_gate={"enforced": True, "status": "pass", "passed": True},
        research_entity_authenticity_gate={"enforced": True, "status": "pass", "passed": True},
        research_claim_evidence_ledger={
            "claim_count": 1,
            "high_confidence_claim_count": 1,
            "high_confidence_supported_count": 1,
            "high_confidence_coverage_percent": 100,
            "status": "pass",
        },
        report_readiness={"status": "ready", "score": 88, "actionable": True, "evidence_gate_passed": True},
        delivery_truth={
            "status": "formal",
            "delivery_mode": "market_scan",
            "formal_delivery_allowed": True,
            "section_confidence_cap": "high",
            "next_action": "已完成正式交付判断。",
        },
        source_diagnostics={
            "source_topology_counts": {"local_comparable": 1},
            "generation_status": "succeeded",
            "runtime_source_reranker_enabled": False,
        },
    )
    return report.model_dump(mode="json")


def _round(snapshot: dict, key: str) -> dict:
    return next(row for row in snapshot["rounds"] if row["key"] == key)


def test_assurance_snapshot_uses_real_reports_and_never_approves_missing_human_artifacts(tmp_path) -> None:
    now = datetime(2026, 8, 10, tzinfo=UTC)
    package_path = tmp_path / "package.json"
    package_path.write_text(json.dumps({"version": "2.6.5"}), encoding="utf-8")
    screenshot_path = tmp_path / "screenshot-manifest.json"
    screenshot_path.write_text(
        json.dumps(
            {
                "version": "2.6.5",
                "quality_gate": {"expected_screenshot_count": 2, "accepted_screenshot_count": 2},
                "screenshots": [{"path": "one.png"}, {"path": "two.png"}],
            }
        ),
        encoding="utf-8",
    )

    settings = get_settings()
    with _session() as db:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.add(
            ResearchJob(
                user_id=settings.single_user_id,
                keyword="上海文旅 AI",
                status="succeeded",
                report_payload=_formal_report_payload(now),
                metrics_payload={
                    "cost_ledger": {
                        "model_call_count": 1,
                        "priced_entry_count": 1,
                        "unpriced_entry_count": 0,
                        "estimated_cost_usd": 0.012345,
                    }
                },
                finished_at=now,
            )
        )
        db.add(
            ResearchJob(
                user_id=settings.single_user_id,
                keyword="历史坏数据",
                status="succeeded",
                report_payload={"schema": "obsolete"},
                finished_at=now,
            )
        )
        db.commit()

        snapshot = build_research_assurance_snapshot(
            db,
            now=now,
            review_path=tmp_path / "missing-review.json",
            calibration_path=tmp_path / "missing-calibration.json",
            screenshot_manifest_path=screenshot_path,
            package_path=package_path,
        )

    assert snapshot["program_version"] == "2.6.5"
    assert [row["version"] for row in snapshot["rounds"]] == [
        "2.5.1",
        "2.5.2",
        "2.5.3",
        "2.5.4",
        "2.5.5",
        "2.5.6",
        "2.5.7",
        "2.5.8",
        "2.5.9",
        "2.6.0",
        "2.6.1",
        "2.6.2",
        "2.6.3",
        "2.6.4",
        "2.6.5",
    ]
    assert snapshot["report_sample_size"] == 2
    assert snapshot["valid_report_count"] == 1
    assert snapshot["invalid_report_count"] == 1
    assert _round(snapshot, "payload_compatibility")["status"] == "blocked"
    assert _round(snapshot, "cost_ledger_coverage")["status"] == "pass"
    assert _round(snapshot, "visual_office_queue_durability")["metrics"][0]["status"] == "pass"
    assert _round(snapshot, "independent_review_packet")["status"] == "blocked"
    assert _round(snapshot, "expert_calibration_customer_acceptance")["status"] == "blocked"
    assert _round(snapshot, "assurance_command_center")["status"] == "blocked"


def test_assurance_preview_api_returns_the_read_only_program_snapshot() -> None:
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
            response = client.get("/api/research/assurance/preview")
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()

    assert response.status_code == 200
    payload = response.json()
    assert payload["program_version"] == "2.6.5"
    assert len(payload["rounds"]) == 15
    assert payload["rounds"][-1]["key"] == "assurance_command_center"
