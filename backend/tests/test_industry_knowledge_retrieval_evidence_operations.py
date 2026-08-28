from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

from app.services import industry_knowledge_retrieval_assurance as assurance
from app.services import industry_knowledge_retrieval_evidence_operations as operations


NOW = datetime(2026, 8, 14, 6, tzinfo=UTC)


def _write(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _benchmark() -> dict[str, object]:
    case_ids = [f"case-{index}" for index in range(1, 13)]
    payload: dict[str, object] = {
        "benchmark_id": assurance.BENCHMARK_ID,
        "dataset_sha256": "dataset-digest",
        "knowledge_base_generation_id": "knowledge-generation",
        "status": "ready",
        "case_count": len(case_ids),
        "promotion": {
            "decision": "promote",
            "candidate_strategy": "prefilter_weighted_rerank",
            "reasons": ["test fixture only"],
        },
        "arms": [
            {
                "strategy": strategy,
                "case_count": len(case_ids),
                "rerank_applied_case_count": len(case_ids) if strategy == "prefilter_weighted_rerank" else 0,
                "rerank_backend": "sentence-transformers" if strategy == "prefilter_weighted_rerank" else "disabled",
                "rerank_model": "BAAI/bge-reranker-v2-m3" if strategy == "prefilter_weighted_rerank" else "",
                "metrics": [
                    {"key": "recall_at_10", "value": 1.0},
                    {"key": "ndcg_at_10", "value": 1.0},
                    {"key": "citation_hit_rate", "value": 1.0},
                    {"key": "latency_ms", "value": 10.0 if strategy == "baseline_hybrid" else 15.0},
                ],
                "cases": [
                    {"case_id": case_id, "recall_at_10": 1.0, "citation_hit_rate": 1.0}
                    for case_id in case_ids
                ],
            }
            for strategy in assurance.STRATEGY_KEYS
        ],
    }
    payload["benchmark_digest"] = assurance._benchmark_digest(payload)
    return payload


def _review(benchmark: dict[str, object]) -> dict[str, object]:
    case_ids = [f"case-{index}" for index in range(1, 13)]
    return {
        "benchmark_id": assurance.BENCHMARK_ID,
        "dataset_sha256": benchmark["dataset_sha256"],
        "knowledge_base_generation_id": benchmark["knowledge_base_generation_id"],
        "benchmark_digest": assurance._benchmark_digest(benchmark),
        "review_protocol_version": assurance.REVIEW_PROTOCOL_VERSION,
        "review_status": "complete",
        "reviewer_name": "Independent Reviewer",
        "reviewer_role": "domain reviewer",
        "reviewed_at": "2026-08-14T00:00:00+00:00",
        "attestation": "I reviewed every complete report from this fixed cohort.",
        "independence_attestation": "I did not implement the retrieval candidate.",
        "conflict_disclosure": "No conflict.",
        "entries": [
            {
                "case_id": case_id,
                "strategy": strategy,
                "report_artifact_path": f"reports/{case_id}-{strategy}.md",
                "human_review_score": 4.5 if strategy == "prefilter_weighted_rerank" else 4.0,
            }
            for case_id in case_ids
            for strategy in assurance.STRATEGY_KEYS
        ],
    }


def _approval(benchmark: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": assurance.APPROVAL_SCHEMA_VERSION,
        "benchmark_id": assurance.BENCHMARK_ID,
        "dataset_sha256": benchmark["dataset_sha256"],
        "knowledge_base_generation_id": benchmark["knowledge_base_generation_id"],
        "benchmark_digest": assurance._benchmark_digest(benchmark),
        "candidate_strategy": "prefilter_weighted_rerank",
        "decision": "approved",
        "approved_by": "Release Owner",
        "approver_role": "quality owner",
        "approved_at": "2026-08-14T01:00:00+00:00",
        "attestation": "Approved for controlled shadow only.",
        "separation_attestation": "I am independent from the complete report reviewer.",
    }


def _runtime_artifacts(benchmark: dict[str, object], approval: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    binding = {
        "benchmark_id": assurance.BENCHMARK_ID,
        "dataset_sha256": benchmark["dataset_sha256"],
        "knowledge_base_generation_id": benchmark["knowledge_base_generation_id"],
        "benchmark_digest": assurance._benchmark_digest(benchmark),
        "candidate_strategy": "prefilter_weighted_rerank",
        "approval_digest": assurance._canonical_digest(approval),
        "status": "complete",
    }
    shadow = {
        **binding,
        "schema_version": assurance.SHADOW_SCHEMA_VERSION,
        "executed_by": "Shadow Operator",
        "executed_at": "2026-08-14T02:00:00+00:00",
        "attestation": "Recorded from a controlled shadow run.",
        "sample_count": 30,
        "fallback_count": 0,
        "quality_regression_count": 0,
    }
    drift = {
        **binding,
        "schema_version": assurance.DRIFT_SCHEMA_VERSION,
        "executed_by": "Drift Operator",
        "executed_at": "2026-08-14T03:00:00+00:00",
        "attestation": "Recorded from a fixed-set drift check.",
        "checked_case_count": 12,
        "regression_count": 0,
    }
    return shadow, drift


def _paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "benchmark_artifact_path": tmp_path / "benchmark.json",
        "review_path": tmp_path / "review.json",
        "approval_path": tmp_path / "approval.json",
        "shadow_path": tmp_path / "shadow.json",
        "drift_path": tmp_path / "drift.json",
        "incident_path": tmp_path / "incidents.json",
        "revocation_path": tmp_path / "revocation.json",
        "handoff_path": tmp_path / "handoff.json",
    }


def _complete_artifacts(tmp_path: Path) -> tuple[dict[str, object], dict[str, Path]]:
    paths = _paths(tmp_path)
    benchmark = _benchmark()
    review = _review(benchmark)
    approval = _approval(benchmark)
    shadow, drift = _runtime_artifacts(benchmark, approval)
    _write(paths["benchmark_artifact_path"], benchmark)
    _write(paths["review_path"], review)
    _write(paths["approval_path"], approval)
    _write(paths["shadow_path"], shadow)
    _write(paths["drift_path"], drift)
    _write(
        paths["incident_path"],
        {
            "schema_version": operations.INCIDENT_SCHEMA_VERSION,
            "benchmark_digest": assurance._benchmark_digest(benchmark),
            "status": "complete",
            "updated_by": "Incident Owner",
            "updated_at": "2026-08-14T04:00:00+00:00",
            "attestation": "No unclosed retrieval incidents or manual waivers remain.",
            "incidents": [],
        },
    )
    _write(
        paths["revocation_path"],
        {
            "schema_version": operations.REVOCATION_SCHEMA_VERSION,
            "benchmark_digest": assurance._benchmark_digest(benchmark),
            "status": "acknowledged",
            "rollback_target": "baseline_hybrid",
            "confirmed_by": "Production Owner",
            "confirmed_at": "2026-08-14T05:00:00+00:00",
            "attestation": "Candidate revocation returns production to baseline_hybrid.",
        },
    )
    preliminary = operations.build_industry_knowledge_retrieval_evidence_operations_snapshot(now=NOW, **paths)
    _write(
        paths["handoff_path"],
        {
            "schema_version": operations.HANDOFF_SCHEMA_VERSION,
            "evidence_chain_digest": preliminary["evidence_chain_digest"],
            "status": "complete",
            "handed_off_by": "Independent Audit Owner",
            "handed_off_at": "2026-08-14T05:30:00+00:00",
            "attestation": "The complete bound evidence package was handed to an independent audit owner.",
        },
    )
    return benchmark, paths


def test_evidence_operations_fail_closed_when_external_artifacts_are_missing(tmp_path: Path) -> None:
    benchmark = _benchmark()
    paths = _paths(tmp_path)
    _write(paths["benchmark_artifact_path"], benchmark)

    snapshot = operations.build_industry_knowledge_retrieval_evidence_operations_snapshot(now=NOW, **paths)

    assert snapshot["status"] == "blocked"
    assert snapshot["current_default_strategy"] == "baseline_hybrid"
    assert len(snapshot["rounds"]) == 15
    assert next(item for item in snapshot["rounds"] if item["key"] == "incident_register")["status"] == "blocked"
    assert next(item for item in snapshot["rounds"] if item["key"] == "release_readiness_bridge")["status"] == "blocked"


def test_evidence_operations_accepts_a_complete_bound_and_fresh_chain(tmp_path: Path) -> None:
    benchmark, paths = _complete_artifacts(tmp_path)

    snapshot = operations.build_industry_knowledge_retrieval_evidence_operations_snapshot(
        benchmark_payload=benchmark,
        now=NOW,
        **paths,
    )

    assert snapshot["status"] == "pass"
    assert snapshot["score"] == 100
    assert snapshot["pass_count"] == 15
    assert snapshot["blocked_count"] == 0
    assert snapshot["current_default_strategy"] == "baseline_hybrid"
    assert snapshot["evidence_chain_digest"]
    assert all(item["status"] == "pass" for item in snapshot["rounds"])


def test_evidence_operations_rejects_stale_or_reused_handoff(tmp_path: Path) -> None:
    benchmark, paths = _complete_artifacts(tmp_path)
    handoff = json.loads(paths["handoff_path"].read_text(encoding="utf-8"))
    handoff["handed_off_at"] = "2026-07-01T00:00:00+00:00"
    _write(paths["handoff_path"], handoff)

    stale_snapshot = operations.build_industry_knowledge_retrieval_evidence_operations_snapshot(
        benchmark_payload=benchmark,
        now=NOW,
        **paths,
    )
    assert stale_snapshot["status"] == "blocked"
    assert next(item for item in stale_snapshot["rounds"] if item["key"] == "independent_audit_handoff")["status"] == "blocked"

    handoff["handed_off_at"] = "2026-08-14T05:30:00+00:00"
    handoff["evidence_chain_digest"] = "wrong-chain"
    _write(paths["handoff_path"], handoff)
    reused_snapshot = operations.build_industry_knowledge_retrieval_evidence_operations_snapshot(
        benchmark_payload=benchmark,
        now=NOW,
        **paths,
    )
    assert next(item for item in reused_snapshot["rounds"] if item["key"] == "independent_audit_handoff")["status"] == "blocked"


def test_evidence_operations_templates_are_pending_and_do_not_overwrite(tmp_path: Path) -> None:
    benchmark = _benchmark()
    paths = _paths(tmp_path)
    _write(paths["benchmark_artifact_path"], benchmark)
    first = operations.export_industry_knowledge_retrieval_evidence_operations_templates(
        benchmark_payload=benchmark,
        incident_path=paths["incident_path"],
        revocation_path=paths["revocation_path"],
        handoff_path=paths["handoff_path"],
    )
    incident = json.loads(paths["incident_path"].read_text(encoding="utf-8"))
    incident["updated_by"] = "Human Owner"
    _write(paths["incident_path"], incident)

    second = operations.export_industry_knowledge_retrieval_evidence_operations_templates(
        benchmark_payload=benchmark,
        incident_path=paths["incident_path"],
        revocation_path=paths["revocation_path"],
        handoff_path=paths["handoff_path"],
    )

    assert len(first["created_paths"]) == 3
    assert second["created_paths"] == []
    assert json.loads(paths["incident_path"].read_text(encoding="utf-8"))["updated_by"] == "Human Owner"
    assert first["template_summaries"] == {"incident": "pending", "revocation": "pending", "handoff": "pending"}


def test_evidence_operations_refuses_unbound_templates(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    try:
        operations.export_industry_knowledge_retrieval_evidence_operations_templates(
            incident_path=paths["incident_path"],
            revocation_path=paths["revocation_path"],
            handoff_path=paths["handoff_path"],
            benchmark_artifact_path=paths["benchmark_artifact_path"],
        )
    except ValueError as exc:
        assert "无摘要模板" in str(exc)
    else:
        raise AssertionError("unbound evidence-operations templates must be rejected")
