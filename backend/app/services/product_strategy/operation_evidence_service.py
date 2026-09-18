from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import math
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.product_strategy_context_entities import ProductStrategyDecisionContextPacket
from app.models.product_strategy_operation_entities import ProductStrategyOperationEvidence as Evidence
from app.schemas.product_strategy_operations import (
    CapabilityRegistration, DryRunReceiptRequest, EvidenceGateReviewRequest, ExecutionProposal,
    PerformanceEvidence, RollbackRehearsalRequest, SkillInventoryRegistration, SourceChangeReview,
    TaskFeedbackEvidence,
)
from app.services.product_strategy.catalog import canonical_digest

BOUNDARY = {"can_auto_execute": False, "can_auto_accept": False, "can_auto_approve_release": False,
            "production_status": "not_authorized", "acceptance_status": "hold"}


class OperationEvidenceError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def serialize(row: Evidence) -> dict:
    payload = deepcopy(row.payload)
    if canonical_digest({"kind": row.kind, "payload": payload}) != row.digest:
        raise OperationEvidenceError("evidence_integrity_failed", "Stored evidence digest is inconsistent.")
    return {"evidence_key": row.evidence_key, "kind": row.kind, "digest": row.digest, "payload": payload,
            "created_at": row.created_at.isoformat() if row.created_at else None, **BOUNDARY}


def _save(db: Session, kind: str, payload: dict, *, key: str | None = None) -> dict:
    digest = canonical_digest({"kind": kind, "payload": payload})
    evidence_key = key or f"ops:{digest}"
    existing = db.scalar(select(Evidence).where(Evidence.evidence_key == evidence_key))
    if existing is not None:
        if existing.digest != digest:
            raise OperationEvidenceError("idempotency_conflict", "This idempotency key already binds different evidence.")
        return {"outcome": "existing", "evidence": serialize(existing)}
    row = Evidence(evidence_key=evidence_key, kind=kind, payload=payload, digest=digest)
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        existing = db.scalar(select(Evidence).where(Evidence.evidence_key == evidence_key))
        if existing is None or existing.digest != digest:
            raise OperationEvidenceError("idempotency_conflict", "Concurrent evidence registration conflicts.")
        return {"outcome": "existing", "evidence": serialize(existing)}
    db.commit()
    return {"outcome": "created", "evidence": serialize(row)}


def _get(db: Session, key: str, kind: str) -> Evidence:
    row = db.scalar(select(Evidence).where(Evidence.evidence_key == key, Evidence.kind == kind))
    if row is None:
        raise OperationEvidenceError("evidence_not_found", f"Required {kind} evidence is missing.")
    serialize(row)
    return row


def list_evidence(db: Session, *, limit: int = 100) -> dict:
    rows = db.scalars(select(Evidence).order_by(Evidence.created_at.desc(), Evidence.evidence_key).limit(limit)).all()
    return {"records": [serialize(row) for row in rows], "limit": limit, **BOUNDARY}


def register_capability(db: Session, request: CapabilityRegistration) -> dict:
    if request.observed_at > datetime.now(UTC):
        raise OperationEvidenceError("future_observation", "An observation cannot be in the future.")
    return _save(db, "capability", {**request.model_dump(mode="json"), "iteration_version": "2.10.9", "identity_status": "declared_unverified",
                                   "signature_status": "missing", "evaluation_status": "reference_unverified" if request.evaluation_digest else "missing"})


def register_skill_inventory(db: Session, request: SkillInventoryRegistration) -> dict:
    if request.observed_at > datetime.now(UTC):
        raise OperationEvidenceError("future_observation", "An observation cannot be in the future.")
    evaluation = "reference_unverified" if request.evaluation_evidence_key else "missing"
    return _save(db, "skill_inventory", {
        **request.model_dump(mode="json"),
        "iteration_version": "2.10.9",
        "identity_status": "declared_unverified",
        "signature_status": "provided_unverified" if request.signature_digest else "missing",
        "evaluation_status": evaluation,
        "install_or_execution_requested": False,
        **BOUNDARY,
    })


def _preview(db: Session, request: ExecutionProposal, *, now: datetime | None = None) -> dict:
    capability = _get(db, request.capability_evidence_key, "capability")
    declaration = capability.payload
    context = db.scalar(select(ProductStrategyDecisionContextPacket).where(
        ProductStrategyDecisionContextPacket.packet_key == request.context_packet_key))
    if context is None or context.revision_digest != request.expected_context_digest:
        raise OperationEvidenceError("stale_context", "Proposal must bind the current persisted context revision.")
    reasons = []
    instant = now or datetime.now(UTC)
    if datetime.fromisoformat(declaration["expires_at"].replace("Z", "+00:00")) <= instant:
        reasons.append("capability_expired")
    if set(request.arguments) - set(declaration["allowed_parameters"]):
        reasons.append("undeclared_parameters")
    if set(declaration["required_parameters"]) - set(request.arguments):
        reasons.append("missing_parameters")
    if declaration["tool_key"] in declaration["prohibited_actions"]:
        reasons.append("prohibited_action")
    if any(urlsplit(url).hostname.lower() not in [h.lower() for h in declaration["allowed_hosts"]] for url in request.target_urls):
        reasons.append("target_outside_allowlist")
    if request.estimated_cost_usd is None:
        reasons.append("cost_unknown")
    elif request.estimated_cost_usd > request.budget_usd:
        reasons.append("budget_exceeded")
    return {"request": request.model_dump(mode="json"), "iteration_version": "2.11.0", "capability_digest": capability.digest,
            "permission_preview": {"effect": declaration["effect"], "target_urls": request.target_urls,
                                   "tool_key": declaration["tool_key"], "argument_names": sorted(request.arguments)},
            "plan_status": "blocked" if reasons else "valid_plan",
            "plan_blockers": reasons, "execution_blockers": ["named_execution_approval_missing", "capability_signature_missing", "independent_evaluation_missing"],
            "side_effects_performed": False, **BOUNDARY}


def create_proposal(db: Session, request: ExecutionProposal) -> dict:
    return _save(db, "execution_proposal", {**_preview(db, request), "iteration_version": "2.11.0"},
                 key=f"proposal:{canonical_digest(request.idempotency_key)}")


def replay_proposal(db: Session, evidence_key: str) -> dict:
    original = _get(db, evidence_key, "execution_proposal")
    previous = original.payload
    request = ExecutionProposal.model_validate(previous["request"])
    current = _preview(db, request)
    differences = [{"field": field, "before": previous.get(field), "after": current.get(field)}
                   for field in sorted(set(previous) | set(current)) if previous.get(field) != current.get(field)]
    # Exercise rollback only on an isolated in-memory snapshot. Never invoke a
    # tool or advertise this as a rollback of an external service.
    checkpoint = deepcopy(previous)
    sandbox = deepcopy(checkpoint)
    sandbox["local_simulated_change"] = original.digest
    sandbox = deepcopy(checkpoint)
    return _save(db, "replay", {"proposal_key": original.evidence_key, "proposal_digest": original.digest,
                               "mode": "isolated_plan_replay", "field_diff": differences,
                               "replay_matches": not differences, "checkpoint_digest": canonical_digest(checkpoint),
                               "restored_digest": canonical_digest(sandbox), "rollback_scope": "in_memory_snapshot_only",
                               "external_rollback_verified": False, "iteration_version": "2.11.1", **BOUNDARY})


def create_dry_run(db: Session, request: DryRunReceiptRequest) -> dict:
    proposal = _get(db, request.proposal_evidence_key, "execution_proposal")
    if proposal.digest != request.expected_proposal_digest:
        raise OperationEvidenceError("stale_proposal", "Dry-run must bind the current proposal digest.")
    payload = {
        **request.model_dump(mode="json"),
        "iteration_version": "2.11.0",
        "proposal_digest": proposal.digest,
        "mode": "isolated_no_side_effects",
        "execution_requested": False,
        "side_effects_performed": False,
        "failure_status": "blocked_for_review",
        **BOUNDARY,
    }
    return _save(db, "dry_run", payload, key=f"dry-run:{canonical_digest(request.idempotency_key)}")


def record_rollback_rehearsal(db: Session, request: RollbackRehearsalRequest) -> dict:
    proposal = _get(db, request.proposal_evidence_key, "execution_proposal")
    if proposal.digest != request.expected_proposal_digest:
        raise OperationEvidenceError("stale_proposal", "Rollback rehearsal must bind the current proposal digest.")
    checkpoint = canonical_digest(proposal.payload)
    payload = {
        **request.model_dump(mode="json"),
        "iteration_version": "2.11.1",
        "proposal_digest": proposal.digest,
        "checkpoint_digest": checkpoint,
        "restored_digest": checkpoint,
        "rollback_scope": "in_memory_snapshot_only",
        "external_rollback_verified": False,
        "side_effects_performed": False,
        "recovery_status": "local_rehearsal_recorded",
        **BOUNDARY,
    }
    return _save(db, "rollback_rehearsal", payload, key=f"rollback:{canonical_digest(request.idempotency_key)}")


def record_performance(db: Session, request: PerformanceEvidence) -> dict:
    latencies = sorted(sample.latency_ms for sample in request.samples)
    count = len(latencies)
    p95 = latencies[math.ceil(count * .95) - 1]
    error_rate = sum(not sample.success for sample in request.samples) / count
    costs_complete = all(sample.cost_usd is not None for sample in request.samples)
    total_cost = sum(sample.cost_usd for sample in request.samples) if costs_complete else None
    reasons = []
    if count < 30:
        reasons.append("fewer_than_30_samples")
    if request.provenance != "local_measurement":
        reasons.append("not_local_measurement")
    if p95 > request.max_p95_ms:
        reasons.append("latency_threshold_exceeded")
    if error_rate > request.max_error_rate:
        reasons.append("error_threshold_exceeded")
    if request.max_total_cost_usd is not None:
        if total_cost is None:
            reasons.append("cost_unknown")
        elif total_cost > request.max_total_cost_usd:
            reasons.append("cost_threshold_exceeded")
    comparison = None
    if request.baseline_evidence_key:
        baseline = _get(db, request.baseline_evidence_key, "performance").payload
        if any(baseline[field] != getattr(request, field) for field in ("environment_fingerprint", "workload", "provenance")):
            raise OperationEvidenceError("incomparable_baseline", "Compare only matching environments, workloads and provenance.")
        comparison = {"baseline_digest": _get(db, request.baseline_evidence_key, "performance").digest,
                      "p95_delta_ms": p95 - baseline["metrics"]["p95_ms"],
                      "error_rate_delta": error_rate - baseline["metrics"]["error_rate"]}
    return _save(db, "performance", {**request.model_dump(mode="json"), "iteration_version": "2.11.2",
                 "metrics": {"sample_count": count, "p50_ms": latencies[math.ceil(count * .5) - 1], "p95_ms": p95,
                             "error_rate": error_rate, "total_cost_usd": total_cost, "cost_complete": costs_complete},
                 "threshold_status": "fail" if reasons else "pass", "blockers": reasons, "comparison": comparison,
                 "measurement_status": "submitted_unverified", "proves_sla": False, **BOUNDARY})


def record_feedback(db: Session, request: TaskFeedbackEvidence) -> dict:
    from app.models.product_strategy_artifact_acceptance_entities import ProductStrategyArtifactAcceptanceDraft
    artifact = db.scalar(select(ProductStrategyArtifactAcceptanceDraft).where(
        ProductStrategyArtifactAcceptanceDraft.revision_digest == request.artifact_revision_digest))
    if artifact is None:
        raise OperationEvidenceError("artifact_revision_missing", "Feedback must reference a current persisted artifact revision.")
    latest_revision = db.scalar(select(ProductStrategyArtifactAcceptanceDraft).where(
        ProductStrategyArtifactAcceptanceDraft.artifact_key == artifact.artifact_key,
    ).order_by(ProductStrategyArtifactAcceptanceDraft.revision.desc()).limit(1))
    if latest_revision is None or latest_revision.revision_digest != artifact.revision_digest:
        raise OperationEvidenceError("stale_artifact_revision", "Feedback must bind the latest artifact revision.")
    return _save(db, "task_feedback", {**request.model_dump(mode="json"), "iteration_version": "2.11.5", "identity_status": "self_attested",
                                      "consent_status": "reference_unverified", "blind_review_status": "self_attested" if request.blinded else "not_blinded",
                                      "customer_acceptance": False, **BOUNDARY})


def record_source_review(db: Session, request: SourceChangeReview) -> dict:
    now = datetime.now(UTC)
    if request.observed_at > now or now - request.observed_at > timedelta(days=14):
        raise OperationEvidenceError("stale_source", "Source observations must be within the past fourteen days.")
    return _save(db, "source_review", {**request.model_dump(mode="json"), "iteration_version": "2.11.4",
                 "change_kind": "baseline_missing" if request.previous_content_digest is None else (
                     "unchanged" if request.previous_content_digest == request.content_digest else "content_changed"),
                 "expires_at": (request.observed_at + timedelta(days=14)).isoformat(),
                 "reviewer_identity_status": "self_attested", "roadmap_mutated": False, **BOUNDARY})


def record_evidence_gate_review(db: Session, request: EvidenceGateReviewRequest) -> dict:
    rows = []
    missing = []
    for key in request.evidence_keys:
        row = db.scalar(select(Evidence).where(Evidence.evidence_key == key))
        if row is None:
            missing.append(key)
        else:
            serialize(row)
            rows.append(row)
    if missing:
        raise OperationEvidenceError("evidence_missing", f"Evidence keys are missing: {', '.join(missing)}")
    current_digest = canonical_digest([{"evidence_key": row.evidence_key, "digest": row.digest} for row in rows])
    if current_digest != request.expected_digest:
        raise OperationEvidenceError("evidence_digest_mismatch", "Gate review must bind the current evidence index digest.")
    expires = request.expires_at.astimezone(UTC)
    blockers = []
    if expires <= datetime.now(UTC):
        blockers.append("review_expired")
    if request.decision == "renew" and any(row.payload.get("acceptance_status") == "hold" for row in rows):
        blockers.append("upstream_acceptance_hold")
    if request.decision == "renew" and blockers:
        status = "renewal_blocked"
    else:
        status = {"renew": "renewal_recorded", "revoke": "revocation_recorded", "hold": "held"}[request.decision]
    return _save(db, "evidence_gate_review", {
        **request.model_dump(mode="json"),
        "iteration_version": "2.11.8",
        "evidence_digests": [{"evidence_key": row.evidence_key, "digest": row.digest} for row in rows],
        "current_index_digest": current_digest,
        "reviewer_identity_status": "self_attested",
        "gate_status": status,
        "blockers": blockers,
        "release_gate_mutated": False,
        "production_default": "baseline_hybrid",
        **BOUNDARY,
    }, key=f"gate:{canonical_digest(request.idempotency_key)}")


def export_audit(db: Session) -> dict:
    rows = db.scalars(select(Evidence).order_by(Evidence.created_at, Evidence.evidence_key)).all()
    records = [serialize(row) for row in rows]
    kinds = {row.kind for row in rows}
    expected = {"capability", "skill_inventory", "execution_proposal", "dry_run", "replay", "rollback_rehearsal", "performance", "task_feedback", "source_review", "evidence_gate_review"}
    index = [{"evidence_key": row.evidence_key, "digest": row.digest, "kind": row.kind} for row in rows]
    return {"schema_version": "operation-audit-v1", "records": records, "index": index,
            "bundle_digest": canonical_digest(index), "missing_evidence_kinds": sorted(expected - kinds),
            "independent_audit_status": "not_performed", "scope": "product_strategy_operation_evidence_only",
            "required_default_strategy": "baseline_hybrid", **BOUNDARY}


def export_audit_handoff(db: Session, *, artifact_key: str | None = None) -> dict:
    """Aggregate a read-only handoff index; it is never an independent audit."""
    from app.services.product_strategy.iteration_program_service import get_persisted_iteration_program
    from app.services.release_readiness_service import build_release_readiness_snapshot

    operations = export_audit(db)
    program = get_persisted_iteration_program(db)
    raw_release = build_release_readiness_snapshot(db)
    blockers = ["independent_audit_not_performed", "production_authorization_missing"]
    bridge = None
    if artifact_key:
        from app.services.product_strategy.human_acceptance_service import HumanAcceptanceError, release_bridge
        try:
            bridge = release_bridge(db, artifact_key)
            blockers.extend(bridge["blockers"])
        except HumanAcceptanceError as error:
            blockers.append(error.code)
    else:
        blockers.append("artifact_key_missing")
    blockers.extend(f"operation_evidence_missing:{kind}" for kind in operations["missing_evidence_kinds"])
    if raw_release["overall_status"] != "pass":
        blockers.append("upstream_release_readiness_not_passed")
    snapshot = {
        "schema_version": "independent-audit-handoff-v1",
        "iteration_program_version": program["iteration_program_version"],
        "iteration_program_digest": program["program_digest"],
        "operation_bundle_digest": operations["bundle_digest"],
        "artifact_key": artifact_key,
        "release_readiness": {"overall_status": raw_release["overall_status"], "release_version": raw_release["release_version"]},
        "bridge": bridge,
        "blockers": sorted(set(blockers)),
        "independent_audit_status": "not_performed",
        "read_only": True,
        "release_gate_mutated": False,
        "production_default": "baseline_hybrid",
        **BOUNDARY,
    }
    return {**snapshot, "handoff_digest": canonical_digest(snapshot)}
