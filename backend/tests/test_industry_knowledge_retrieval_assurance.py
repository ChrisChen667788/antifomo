from __future__ import annotations

import json

from app.services import industry_knowledge_retrieval_assurance as assurance


def _benchmark(*, candidate: str = "", decision: str = "hold", rerank_applied: int = 0) -> dict[str, object]:
    case_ids = [f"case-{index}" for index in range(1, 13)]
    return {
        "benchmark_id": assurance.BENCHMARK_ID,
        "dataset_sha256": "dataset-digest",
        "knowledge_base_generation_id": "knowledge-generation",
        "status": "ready",
        "case_count": len(case_ids),
        "promotion": {
            "decision": decision,
            "candidate_strategy": candidate,
            "reasons": [] if candidate else ["尚无候选。"],
        },
        "arms": [
            {
                "strategy": strategy,
                "case_count": len(case_ids),
                "rerank_applied_case_count": rerank_applied if strategy == "prefilter_weighted_rerank" else 0,
                "rerank_backend": "sentence-transformers" if strategy == "prefilter_weighted_rerank" else "disabled",
                "rerank_model": "BAAI/bge-reranker-v2-m3" if strategy == "prefilter_weighted_rerank" else "",
                "metrics": [
                    {"key": "recall_at_10", "value": 1.0},
                    {"key": "ndcg_at_10", "value": 1.0},
                    {"key": "citation_hit_rate", "value": 1.0},
                    {"key": "latency_ms", "value": 10.0 if strategy == "baseline_hybrid" else 15.0},
                ],
                "cases": [
                    {
                        "case_id": case_id,
                        "recall_at_10": 1.0,
                        "citation_hit_rate": 1.0,
                    }
                    for case_id in case_ids
                ],
            }
            for strategy in assurance.STRATEGY_KEYS
        ],
    }


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
        "reviewed_at": "2026-08-13T00:00:00+00:00",
        "attestation": "I reviewed every complete report.",
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
        "approved_at": "2026-08-13T00:00:00+00:00",
        "attestation": "Approved for controlled shadow only.",
        "separation_attestation": "I am not the complete-report reviewer.",
    }


def test_assurance_keeps_default_baseline_when_external_evidence_is_missing(tmp_path) -> None:
    benchmark = _benchmark()
    snapshot = assurance.build_industry_knowledge_retrieval_assurance_snapshot(
        benchmark_payload=benchmark,
        benchmark_artifact_path=tmp_path / "benchmark.json",
        review_path=tmp_path / "review.json",
        approval_path=tmp_path / "approval.json",
        shadow_path=tmp_path / "shadow.json",
        drift_path=tmp_path / "drift.json",
    )

    assert snapshot["current_default_strategy"] == "baseline_hybrid"
    assert snapshot["status"] == "blocked"
    assert len(snapshot["rounds"]) == 15
    assert next(round_item for round_item in snapshot["rounds"] if round_item["key"] == "full_report_review_integrity")["status"] == "blocked"
    assert next(round_item for round_item in snapshot["rounds"] if round_item["key"] == "rollback_readiness")["status"] == "pass"


def test_assurance_accepts_only_bound_human_and_runtime_artifacts(tmp_path) -> None:
    benchmark = _benchmark(candidate="prefilter_weighted_rerank", decision="promote", rerank_applied=12)
    benchmark_path = tmp_path / "benchmark.json"
    benchmark_path.write_text(json.dumps(benchmark), encoding="utf-8")
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(_review(benchmark)), encoding="utf-8")
    approval_path = tmp_path / "approval.json"
    approval = _approval(benchmark)
    approval_path.write_text(json.dumps(approval), encoding="utf-8")
    approval_digest = assurance._canonical_digest(approval)
    shadow_path = tmp_path / "shadow.json"
    shadow_path.write_text(
        json.dumps(
            {
                "schema_version": assurance.SHADOW_SCHEMA_VERSION,
                "benchmark_id": assurance.BENCHMARK_ID,
                "dataset_sha256": benchmark["dataset_sha256"],
                "knowledge_base_generation_id": benchmark["knowledge_base_generation_id"],
                "benchmark_digest": assurance._benchmark_digest(benchmark),
                "candidate_strategy": "prefilter_weighted_rerank",
                "approval_digest": approval_digest,
                "status": "complete",
                "executed_by": "Runtime Owner",
                "executed_at": "2026-08-13T00:00:00+00:00",
                "attestation": "Recorded from the real controlled shadow run.",
                "sample_count": 30,
                "fallback_count": 0,
                "quality_regression_count": 0,
            }
        ),
        encoding="utf-8",
    )
    drift_path = tmp_path / "drift.json"
    drift_path.write_text(
        json.dumps(
            {
                "schema_version": assurance.DRIFT_SCHEMA_VERSION,
                "benchmark_id": assurance.BENCHMARK_ID,
                "dataset_sha256": benchmark["dataset_sha256"],
                "knowledge_base_generation_id": benchmark["knowledge_base_generation_id"],
                "benchmark_digest": assurance._benchmark_digest(benchmark),
                "candidate_strategy": "prefilter_weighted_rerank",
                "approval_digest": approval_digest,
                "status": "complete",
                "executed_by": "Runtime Owner",
                "executed_at": "2026-08-13T00:00:00+00:00",
                "attestation": "Recorded from the real fixed-set drift check.",
                "checked_case_count": 12,
                "regression_count": 0,
            }
        ),
        encoding="utf-8",
    )

    snapshot = assurance.build_industry_knowledge_retrieval_assurance_snapshot(
        benchmark_payload=benchmark,
        benchmark_artifact_path=benchmark_path,
        review_path=review_path,
        approval_path=approval_path,
        shadow_path=shadow_path,
        drift_path=drift_path,
    )

    assert next(round_item for round_item in snapshot["rounds"] if round_item["key"] == "full_report_review_integrity")["status"] == "pass"
    assert next(round_item for round_item in snapshot["rounds"] if round_item["key"] == "human_approval")["status"] == "pass"
    assert next(round_item for round_item in snapshot["rounds"] if round_item["key"] == "shadow_run")["status"] == "pass"
    assert next(round_item for round_item in snapshot["rounds"] if round_item["key"] == "drift_monitoring")["status"] == "pass"


def test_evidence_templates_do_not_overwrite_existing_approved_artifact(tmp_path) -> None:
    benchmark = _benchmark(candidate="prefilter_weighted_rerank", decision="promote", rerank_applied=12)
    approval_path = tmp_path / "approval.json"
    approval = _approval(benchmark)
    approval_path.write_text(json.dumps(approval), encoding="utf-8")
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(_review(benchmark)), encoding="utf-8")

    templates = assurance.export_industry_knowledge_retrieval_evidence_templates(
        approval_path=approval_path,
        shadow_path=tmp_path / "shadow.json",
        drift_path=tmp_path / "drift.json",
        review_path=review_path,
        benchmark_payload=benchmark,
    )

    assert json.loads(approval_path.read_text(encoding="utf-8")) == approval
    assert templates["candidate_strategy"] == "prefilter_weighted_rerank"
    shadow = json.loads((tmp_path / "shadow.json").read_text(encoding="utf-8"))
    assert shadow["approval_digest"] == assurance._canonical_digest(approval)
    assert shadow["status"] == "pending"


def test_runtime_evidence_without_operator_attestation_stays_blocked(tmp_path) -> None:
    benchmark = _benchmark(candidate="prefilter_weighted_rerank", decision="promote", rerank_applied=12)
    approval = _approval(benchmark)
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(json.dumps(approval), encoding="utf-8")
    shadow_path = tmp_path / "shadow.json"
    shadow_path.write_text(
        json.dumps(
            {
                "schema_version": assurance.SHADOW_SCHEMA_VERSION,
                "benchmark_id": assurance.BENCHMARK_ID,
                "dataset_sha256": benchmark["dataset_sha256"],
                "knowledge_base_generation_id": benchmark["knowledge_base_generation_id"],
                "benchmark_digest": assurance._benchmark_digest(benchmark),
                "candidate_strategy": "prefilter_weighted_rerank",
                "approval_digest": assurance._canonical_digest(approval),
                "status": "complete",
                "sample_count": 30,
                "fallback_count": 0,
                "quality_regression_count": 0,
            }
        ),
        encoding="utf-8",
    )

    snapshot = assurance.build_industry_knowledge_retrieval_assurance_snapshot(
        benchmark_payload=benchmark,
        approval_path=approval_path,
        shadow_path=shadow_path,
        review_path=tmp_path / "missing-review.json",
        drift_path=tmp_path / "missing-drift.json",
    )

    shadow_round = next(round_item for round_item in snapshot["rounds"] if round_item["key"] == "shadow_run")
    assert shadow_round["status"] == "blocked"
    assert any("执行人" in action for action in shadow_round["next_actions"])


def test_shadow_and_drift_cannot_pass_without_valid_approval(tmp_path) -> None:
    benchmark = _benchmark(candidate="prefilter_weighted_rerank", decision="promote", rerank_applied=12)
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(_review(benchmark)), encoding="utf-8")
    approval = _approval(benchmark)
    approval["decision"] = "pending"
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(json.dumps(approval), encoding="utf-8")
    approval_digest = assurance._canonical_digest(approval)
    shadow_path = tmp_path / "shadow.json"
    shadow_path.write_text(
        json.dumps(
            {
                "schema_version": assurance.SHADOW_SCHEMA_VERSION,
                "benchmark_id": assurance.BENCHMARK_ID,
                "dataset_sha256": benchmark["dataset_sha256"],
                "knowledge_base_generation_id": benchmark["knowledge_base_generation_id"],
                "benchmark_digest": assurance._benchmark_digest(benchmark),
                "candidate_strategy": "prefilter_weighted_rerank",
                "approval_digest": approval_digest,
                "status": "complete",
                "executed_by": "Runtime Owner",
                "executed_at": "2026-08-13T00:00:00+00:00",
                "attestation": "Recorded from a real controlled shadow run.",
                "sample_count": 30,
                "fallback_count": 0,
                "quality_regression_count": 0,
            }
        ),
        encoding="utf-8",
    )
    drift_path = tmp_path / "drift.json"
    drift_path.write_text(
        json.dumps(
            {
                "schema_version": assurance.DRIFT_SCHEMA_VERSION,
                "benchmark_id": assurance.BENCHMARK_ID,
                "dataset_sha256": benchmark["dataset_sha256"],
                "knowledge_base_generation_id": benchmark["knowledge_base_generation_id"],
                "benchmark_digest": assurance._benchmark_digest(benchmark),
                "candidate_strategy": "prefilter_weighted_rerank",
                "approval_digest": approval_digest,
                "status": "complete",
                "executed_by": "Runtime Owner",
                "executed_at": "2026-08-13T00:00:00+00:00",
                "attestation": "Recorded from a real drift check.",
                "checked_case_count": 12,
                "regression_count": 0,
            }
        ),
        encoding="utf-8",
    )

    snapshot = assurance.build_industry_knowledge_retrieval_assurance_snapshot(
        benchmark_payload=benchmark,
        review_path=review_path,
        approval_path=approval_path,
        shadow_path=shadow_path,
        drift_path=drift_path,
    )

    assert next(round_item for round_item in snapshot["rounds"] if round_item["key"] == "human_approval")["status"] == "blocked"
    assert next(round_item for round_item in snapshot["rounds"] if round_item["key"] == "shadow_run")["status"] == "blocked"
    assert next(round_item for round_item in snapshot["rounds"] if round_item["key"] == "drift_monitoring")["status"] == "blocked"


def test_same_person_cannot_review_and_approve_a_candidate(tmp_path) -> None:
    benchmark = _benchmark(candidate="prefilter_weighted_rerank", decision="promote", rerank_applied=12)
    review = _review(benchmark)
    review["reviewer_name"] = "Release Owner"
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(json.dumps(_approval(benchmark)), encoding="utf-8")

    snapshot = assurance.build_industry_knowledge_retrieval_assurance_snapshot(
        benchmark_payload=benchmark,
        review_path=review_path,
        approval_path=approval_path,
        shadow_path=tmp_path / "shadow.json",
        drift_path=tmp_path / "drift.json",
    )

    approval_round = next(round_item for round_item in snapshot["rounds"] if round_item["key"] == "human_approval")
    assert approval_round["status"] == "blocked"
    assert any("同一人" in action for action in approval_round["next_actions"])


def test_templates_preserve_any_existing_human_runtime_record(tmp_path) -> None:
    benchmark = _benchmark(candidate="prefilter_weighted_rerank", decision="promote", rerank_applied=12)
    approval = _approval(benchmark)
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(json.dumps(approval), encoding="utf-8")
    shadow_path = tmp_path / "shadow.json"
    shadow = {"status": "pending", "notes": "Operator has started collecting samples."}
    shadow_path.write_text(json.dumps(shadow), encoding="utf-8")
    drift_path = tmp_path / "drift.json"
    drift = {"status": "complete", "checked_case_count": 12, "attestation": "Recorded separately."}
    drift_path.write_text(json.dumps(drift), encoding="utf-8")

    assurance.export_industry_knowledge_retrieval_evidence_templates(
        approval_path=approval_path,
        shadow_path=shadow_path,
        drift_path=drift_path,
        benchmark_payload=benchmark,
    )

    assert json.loads(shadow_path.read_text(encoding="utf-8")) == shadow
    assert json.loads(drift_path.read_text(encoding="utf-8")) == drift


def test_invalid_counts_fail_closed_without_raising(tmp_path) -> None:
    benchmark = _benchmark(candidate="prefilter_weighted_rerank", decision="promote", rerank_applied=12)
    benchmark["case_count"] = "not-a-count"
    snapshot = assurance.build_industry_knowledge_retrieval_assurance_snapshot(
        benchmark_payload=benchmark,
        review_path=tmp_path / "review.json",
        approval_path=tmp_path / "approval.json",
        shadow_path=tmp_path / "shadow.json",
        drift_path=tmp_path / "drift.json",
    )

    assert snapshot["case_count"] == 0
    assert snapshot["status"] == "blocked"


def test_persisted_snapshot_with_a_wrong_digest_is_not_accepted_as_immutable_evidence(tmp_path) -> None:
    benchmark = _benchmark(candidate="prefilter_weighted_rerank", decision="promote", rerank_applied=12)
    benchmark_path = tmp_path / "benchmark.json"
    tampered = {**benchmark, "benchmark_digest": "wrong-digest"}
    benchmark_path.write_text(json.dumps(tampered), encoding="utf-8")

    snapshot = assurance.build_industry_knowledge_retrieval_assurance_snapshot(
        benchmark_payload=benchmark,
        benchmark_artifact_path=benchmark_path,
        review_path=tmp_path / "review.json",
        approval_path=tmp_path / "approval.json",
        shadow_path=tmp_path / "shadow.json",
        drift_path=tmp_path / "drift.json",
    )

    immutable_round = next(round_item for round_item in snapshot["rounds"] if round_item["key"] == "immutable_benchmark_snapshot")
    assert immutable_round["status"] == "watch"
