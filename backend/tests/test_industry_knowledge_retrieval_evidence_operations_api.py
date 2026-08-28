from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import research as research_api
from app.main import app
from app.services import industry_knowledge_retrieval_evidence_operations as operations


def _snapshot() -> dict[str, object]:
    return operations.build_industry_knowledge_retrieval_evidence_operations_snapshot(
        benchmark_payload={
            "benchmark_id": "industry-knowledge-retrieval-ranking-ab-v1",
            "dataset_sha256": "dataset-digest",
            "knowledge_base_generation_id": "knowledge-generation",
            "benchmark_digest": "fixture-digest",
            "status": "ready",
            "case_count": 0,
            "promotion": {"decision": "hold", "candidate_strategy": "", "reasons": ["fixture"]},
            "arms": [],
        },
        benchmark_artifact_path="/tmp/absent-evidence-operations-benchmark.json",
        review_path="/tmp/absent-evidence-operations-review.json",
        approval_path="/tmp/absent-evidence-operations-approval.json",
        shadow_path="/tmp/absent-evidence-operations-shadow.json",
        drift_path="/tmp/absent-evidence-operations-drift.json",
        incident_path="/tmp/absent-evidence-operations-incidents.json",
        revocation_path="/tmp/absent-evidence-operations-revocation.json",
        handoff_path="/tmp/absent-evidence-operations-handoff.json",
    )


def test_evidence_operations_api_returns_fail_closed_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(research_api, "build_industry_knowledge_retrieval_evidence_operations_snapshot", _snapshot)

    with TestClient(app) as client:
        response = client.get("/api/research/industry-skills/retrieval-evidence-operations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["program_version"] == operations.PROGRAM_VERSION
    assert payload["status"] == "blocked"
    assert payload["current_default_strategy"] == "baseline_hybrid"
    assert len(payload["rounds"]) == 15


def test_evidence_operations_templates_api_does_not_change_default(monkeypatch) -> None:
    monkeypatch.setattr(
        research_api,
        "export_industry_knowledge_retrieval_evidence_operations_templates",
        lambda: {
            "program_version": operations.PROGRAM_VERSION,
            "benchmark_digest": "fixture-digest",
            "incident_register_path": ".tmp/incidents.json",
            "revocation_record_path": ".tmp/revocation.json",
            "audit_handoff_path": ".tmp/handoff.json",
            "created_paths": [".tmp/incidents.json"],
            "warnings": ["pending only"],
            "template_summaries": {"incident": "pending", "revocation": "pending", "handoff": "pending"},
        },
    )

    with TestClient(app) as client:
        response = client.post("/api/research/industry-skills/retrieval-evidence-operations/templates")

    assert response.status_code == 200
    assert response.json()["template_summaries"]["incident"] == "pending"
