from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import research as research_api
from app.main import app
from app.services import industry_knowledge_retrieval_assurance as assurance


def _snapshot() -> dict[str, object]:
    return assurance.build_industry_knowledge_retrieval_assurance_snapshot(
        benchmark_payload={
            "benchmark_id": assurance.BENCHMARK_ID,
            "dataset_sha256": "dataset-digest",
            "knowledge_base_generation_id": "knowledge-generation",
            "status": "ready",
            "case_count": 0,
            "promotion": {"decision": "hold", "candidate_strategy": "", "reasons": ["fixture"]},
            "arms": [],
        },
        benchmark_artifact_path="/tmp/absent-benchmark.json",
        review_path="/tmp/absent-review.json",
        approval_path="/tmp/absent-approval.json",
        shadow_path="/tmp/absent-shadow.json",
        drift_path="/tmp/absent-drift.json",
    )


def test_assurance_api_returns_fail_closed_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(research_api, "build_industry_knowledge_retrieval_assurance_snapshot", _snapshot)

    with TestClient(app) as client:
        response = client.get("/api/research/industry-skills/retrieval-ranking-assurance")

    assert response.status_code == 200
    payload = response.json()
    assert payload["program_version"] == assurance.PROGRAM_VERSION
    assert payload["status"] == "blocked"
    assert len(payload["rounds"]) == 15
    assert payload["current_default_strategy"] == "baseline_hybrid"


def test_assurance_template_endpoints_return_conflict_for_unreadable_human_artifact(monkeypatch) -> None:
    def fail_approval() -> dict[str, object]:
        raise ValueError("已有审批工件不可读取；为避免覆盖人工记录，未生成新模板。")

    def fail_runtime() -> dict[str, object]:
        raise ValueError("已有运行工件不可读取；为避免覆盖人工记录，未生成新模板。")

    monkeypatch.setattr(research_api, "export_industry_knowledge_retrieval_approval_template", fail_approval)
    monkeypatch.setattr(research_api, "export_industry_knowledge_retrieval_evidence_templates", fail_runtime)

    with TestClient(app) as client:
        approval_response = client.post("/api/research/industry-skills/retrieval-ranking-assurance/approval-template")
        runtime_response = client.post("/api/research/industry-skills/retrieval-ranking-assurance/evidence-templates")

    assert approval_response.status_code == 409
    assert runtime_response.status_code == 409
    assert "避免覆盖人工记录" in approval_response.json()["detail"]
    assert "避免覆盖人工记录" in runtime_response.json()["detail"]
