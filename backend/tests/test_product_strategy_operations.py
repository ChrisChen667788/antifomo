from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.api.product_strategy_operations import router
from app.db.base import Base
from app.db.session import get_db
from app.models.product_strategy_context_entities import ProductStrategyDecisionContextPacket
from app.models.product_strategy_operation_entities import ProductStrategyOperationEvidence
from app.schemas.product_strategy_operations import (
    CapabilityRegistration, DryRunReceiptRequest, EvidenceGateReviewRequest, ExecutionProposal,
    PerformanceEvidence, RollbackRehearsalRequest, SkillInventoryRegistration, SourceChangeReview,
    TaskFeedbackEvidence,
)
from app.services.product_strategy.catalog import canonical_digest
from app.services.product_strategy import operation_evidence_service as service
from app.services.product_strategy.artifact_acceptance_service import initialize_artifact_acceptance
from app.services.product_strategy.context_packet_service import initialize_decision_context_packets


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def capability(**changes):
    return CapabilityRegistration.model_validate({
        "capability_key": "read-official-page", "model_id": "model-test", "model_revision": "fixture-1",
        "skill_digest": "a" * 64, "tool_key": "read_page", "allowed_parameters": ["topic"],
        "required_parameters": ["topic"], "allowed_hosts": ["example.org"], "effect": "read_only",
        "observed_at": datetime.now(UTC) - timedelta(hours=1), "expires_at": datetime.now(UTC) + timedelta(days=1),
        **changes,
    })


def proposal(db, **changes):
    packets = initialize_decision_context_packets(db)
    packet = packets["packets"][0]
    registered = service.register_capability(db, capability())["evidence"]
    return ExecutionProposal.model_validate({
        "context_packet_key": packet["packet_key"], "expected_context_digest": packet["revision_digest"],
        "capability_evidence_key": registered["evidence_key"], "arguments": {"topic": "fixture"},
        "target_urls": ["https://example.org/document"], "budget_usd": 0.5, "estimated_cost_usd": 0,
        "idempotency_key": "fixture-read-1", "rollback_plan": "No external writes; discard the local preview.", **changes,
    })


def test_proposal_is_idempotent_and_replay_never_executes_tools(db):
    request = proposal(db)
    result = service.create_proposal(db, request)
    assert result["evidence"]["payload"]["plan_status"] == "valid_plan"
    assert result["evidence"]["payload"]["can_auto_execute"] is False
    assert result["evidence"]["payload"]["side_effects_performed"] is False
    assert service.create_proposal(db, request)["outcome"] == "existing"
    with pytest.raises(service.OperationEvidenceError, match="idempotency key"):
        service.create_proposal(db, request.model_copy(update={"arguments": {"topic": "different"}}))
    replay = service.replay_proposal(db, result["evidence"]["evidence_key"])["evidence"]["payload"]
    assert replay["replay_matches"] is True
    assert replay["checkpoint_digest"] == replay["restored_digest"]
    assert replay["external_rollback_verified"] is False
    bundle = service.export_audit(db)
    assert bundle["independent_audit_status"] == "not_performed"
    assert "performance" in bundle["missing_evidence_kinds"]


def test_context_revision_change_blocks_replay(db):
    request = proposal(db)
    result = service.create_proposal(db, request)
    context = db.scalar(select(ProductStrategyDecisionContextPacket).where(ProductStrategyDecisionContextPacket.packet_key == request.context_packet_key))
    context.revision_digest = "b" * 64
    db.commit()
    with pytest.raises(service.OperationEvidenceError) as error:
        service.replay_proposal(db, result["evidence"]["evidence_key"])
    assert error.value.code == "stale_context"


def test_skill_dry_run_rollback_and_gate_reviews_are_version_bound_and_fail_closed(db):
    skill = SkillInventoryRegistration(
        skill_key="official-reader", vendor="Fixture Vendor", model_id="model-test", model_revision="fixture-1",
        skill_revision="skill-1", skill_digest="d" * 64, source_url="https://example.org/skill",
        source_digest="e" * 64, integrity_status="unverified", permission_scope=["read_page"],
        prohibited_actions=["send_message"], risk_level="medium",
        observed_at=datetime.now(UTC) - timedelta(hours=1), expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    skill_result = service.register_skill_inventory(db, skill)["evidence"]
    assert skill_result["kind"] == "skill_inventory"
    assert skill_result["payload"]["iteration_version"] == "2.10.9"
    request = proposal(db)
    proposal_result = service.create_proposal(db, request)["evidence"]
    dry = service.create_dry_run(db, DryRunReceiptRequest(
        proposal_evidence_key=proposal_result["evidence_key"], expected_proposal_digest=proposal_result["digest"],
        environment_fingerprint="f" * 64, operator_reference="operator-fixture",
        simulated_effects=["read_only_preview"], failure_policy="block_and_review", idempotency_key="dry-1",
    ))["evidence"]
    assert dry["payload"]["side_effects_performed"] is False
    rollback = service.record_rollback_rehearsal(db, RollbackRehearsalRequest(
        proposal_evidence_key=proposal_result["evidence_key"], expected_proposal_digest=proposal_result["digest"],
        environment_fingerprint="f" * 64, failure_code="simulated_timeout",
        recovery_action="restore_local_snapshot", idempotency_key="rollback-1",
    ))["evidence"]
    assert rollback["payload"]["external_rollback_verified"] is False
    rows = db.scalars(select(ProductStrategyOperationEvidence).order_by(ProductStrategyOperationEvidence.evidence_key)).all()
    index_digest = canonical_digest([{"evidence_key": row.evidence_key, "digest": row.digest} for row in rows])
    gate = service.record_evidence_gate_review(db, EvidenceGateReviewRequest(
        gate_key="release-evidence", evidence_keys=[row.evidence_key for row in rows], expected_digest=index_digest,
        decision="renew", reviewer_reference="reviewer-fixture",
        rationale="Fixture review remains blocked until independent evidence and named approval are present.",
        expires_at=datetime.now(UTC) + timedelta(days=1), idempotency_key="gate-1",
    ))["evidence"]
    assert gate["payload"]["gate_status"] == "renewal_blocked"
    assert gate["payload"]["release_gate_mutated"] is False
    assert "upstream_acceptance_hold" in gate["payload"]["blockers"]
    handoff = service.export_audit_handoff(db)
    assert handoff["schema_version"] == "independent-audit-handoff-v1"
    assert handoff["independent_audit_status"] == "not_performed"
    assert handoff["production_default"] == "baseline_hybrid"
    assert "artifact_key_missing" in handoff["blockers"]


def test_preview_rejects_undeclared_targets_parameters_and_budget(db):
    result = service.create_proposal(db, proposal(db, arguments={"undeclared": True}, target_urls=["https://other.example/document"], estimated_cost_usd=1))
    assert set(result["evidence"]["payload"]["plan_blockers"]) == {
        "undeclared_parameters", "missing_parameters", "target_outside_allowlist", "budget_exceeded",
    }
    assert result["evidence"]["payload"]["plan_status"] == "blocked"


def test_expiry_and_unknown_cost_fail_closed(db):
    request = proposal(db, estimated_cost_usd=None)
    registered = service.register_capability(db, capability(expires_at=datetime.now(UTC) - timedelta(minutes=1)))["evidence"]
    request = request.model_copy(update={"capability_evidence_key": registered["evidence_key"]})
    blockers = service.create_proposal(db, request)["evidence"]["payload"]["plan_blockers"]
    assert blockers == ["capability_expired", "cost_unknown"]


def performance(**changes):
    return PerformanceEvidence.model_validate({
        "environment_fingerprint": "c" * 64, "source_revision": "fixture", "workload": "health-read",
        "provenance": "local_measurement", "samples": [{"latency_ms": n, "success": True, "cost_usd": None} for n in range(1, 31)],
        "max_p95_ms": 40, "max_error_rate": 0, **changes,
    })


def test_performance_records_raw_samples_unknown_cost_and_matching_comparison(db):
    first = service.record_performance(db, performance())["evidence"]
    assert first["payload"]["metrics"]["p95_ms"] == 29
    assert first["payload"]["metrics"]["total_cost_usd"] is None
    assert first["payload"]["proves_sla"] is False
    second = service.record_performance(db, performance(baseline_evidence_key=first["evidence_key"], source_revision="fixture-2"))["evidence"]
    assert second["payload"]["comparison"]["p95_delta_ms"] == 0
    with pytest.raises(service.OperationEvidenceError) as error:
        service.record_performance(db, performance(baseline_evidence_key=first["evidence_key"], environment_fingerprint="d" * 64))
    assert error.value.code == "incomparable_baseline"


def test_performance_rejects_small_sample_unknown_budget_and_fake_sla(db):
    result = service.record_performance(db, performance(samples=[{"latency_ms": 100, "success": False}], max_total_cost_usd=0))["evidence"]["payload"]
    assert set(result["blockers"]) == {"fewer_than_30_samples", "latency_threshold_exceeded", "error_threshold_exceeded", "cost_unknown"}
    with pytest.raises(ValidationError):
        performance(samples=[{"latency_ms": float("nan"), "success": True}])


def test_feedback_requires_existing_artifact_and_does_not_claim_customer_acceptance(db):
    initialize_decision_context_packets(db)
    artifact = initialize_artifact_acceptance(db)["artifacts"][0]
    request = TaskFeedbackEvidence(task_key="task-fixture", artifact_revision_digest=artifact["revision_digest"],
        consent_reference="consent-fixture", deidentified=True, source_kind="synthetic_fixture", task_author_reference="author-1",
        reviewer_reference="reviewer-2", blinded=True, relevance_labels={"source-1": 3}, feedback="Fixture feedback for offline contract tests.")
    result = service.record_feedback(db, request)["evidence"]["payload"]
    assert result["customer_acceptance"] is False
    assert result["identity_status"] == "self_attested"
    with pytest.raises(ValidationError):
        TaskFeedbackEvidence.model_validate({**request.model_dump(), "reviewer_reference": "AUTHOR-1"})
    with pytest.raises(service.OperationEvidenceError):
        service.record_feedback(db, request.model_copy(update={"artifact_revision_digest": "a" * 64}))


def test_source_review_expiry_does_not_mutate_roadmap(db):
    request = SourceChangeReview(source_url="https://example.org/models", observed_at=datetime.now(UTC) - timedelta(hours=1),
        content_digest="a" * 64, reviewer_reference="reviewer-reference", decision="defer",
        rationale="Official document changed; independent task evaluation is still missing.")
    result = service.record_source_review(db, request)["evidence"]["payload"]
    assert result["change_kind"] == "baseline_missing"
    assert result["roadmap_mutated"] is False
    with pytest.raises(service.OperationEvidenceError) as error:
        service.record_source_review(db, request.model_copy(update={"observed_at": datetime.now(UTC) - timedelta(days=15)}))
    assert error.value.code == "stale_source"


def test_database_rejects_direct_mutation_and_digest_checks_detect_memory_tamper(db):
    result = service.register_capability(db, capability())["evidence"]
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE product_strategy_operation_evidence SET digest = 'tampered'"))
        db.commit()
    db.rollback()
    row = db.scalar(select(ProductStrategyOperationEvidence).where(ProductStrategyOperationEvidence.evidence_key == result["evidence_key"]))
    row.payload["effect"] = "tampered"
    with pytest.raises(service.OperationEvidenceError) as error:
        service.serialize(row)
    assert error.value.code == "evidence_integrity_failed"


def test_operations_http_api_validates_and_exports_read_only_audit(db):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        assert client.get("/api/product-strategy/operations").json()["records"] == []
        assert client.post("/api/product-strategy/operations/capabilities", json=capability().model_dump(mode="json")).status_code == 201
        invalid = client.post("/api/product-strategy/operations/proposals", json={"execute": True})
        assert invalid.status_code == 422
        bundle = client.get("/api/product-strategy/operations/audit-bundle")
        assert bundle.status_code == 200
        assert bundle.json()["can_auto_execute"] is False
