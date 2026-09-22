from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.product_strategy_operations import (
    CapabilityRegistration, DryRunReceiptRequest, EvidenceGateReviewRequest, ExecutionProposal,
    PerformanceEvidence, RollbackRehearsalRequest, SkillInventoryRegistration, SourceChangeReview,
    TaskFeedbackEvidence,
)
from app.services.product_strategy import operation_evidence_service as service

router = APIRouter(prefix="/api/product-strategy/operations", tags=["product-strategy"])


def respond(call, *args, **kwargs):
    try:
        return call(*args, **kwargs)
    except service.OperationEvidenceError as error:
        raise HTTPException(status_code=409, detail={"code": error.code, "message": str(error), **service.BOUNDARY}) from error


@router.get("")
def list_records(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db)):
    return respond(lambda: service.list_evidence(db, limit=limit))


@router.post("/capabilities", status_code=201)
def capabilities(payload: CapabilityRegistration, db: Session = Depends(get_db)):
    return respond(service.register_capability, db, payload)


@router.post("/skills", status_code=201)
def skills(payload: SkillInventoryRegistration, db: Session = Depends(get_db)):
    return respond(service.register_skill_inventory, db, payload)


@router.post("/proposals", status_code=201)
def proposals(payload: ExecutionProposal, db: Session = Depends(get_db)):
    return respond(service.create_proposal, db, payload)


@router.post("/proposals/{evidence_key}/replay", status_code=201)
def replay(evidence_key: str, db: Session = Depends(get_db)):
    return respond(service.replay_proposal, db, evidence_key)


@router.post("/dry-runs", status_code=201)
def dry_runs(payload: DryRunReceiptRequest, db: Session = Depends(get_db)):
    return respond(service.create_dry_run, db, payload)


@router.post("/rollback-rehearsals", status_code=201)
def rollback_rehearsals(payload: RollbackRehearsalRequest, db: Session = Depends(get_db)):
    return respond(service.record_rollback_rehearsal, db, payload)


@router.post("/performance", status_code=201)
def performance(payload: PerformanceEvidence, db: Session = Depends(get_db)):
    return respond(service.record_performance, db, payload)


@router.post("/feedback", status_code=201)
def feedback(payload: TaskFeedbackEvidence, db: Session = Depends(get_db)):
    return respond(service.record_feedback, db, payload)


@router.post("/source-reviews", status_code=201)
def source_reviews(payload: SourceChangeReview, db: Session = Depends(get_db)):
    return respond(service.record_source_review, db, payload)


@router.post("/gate-reviews", status_code=201)
def gate_reviews(payload: EvidenceGateReviewRequest, db: Session = Depends(get_db)):
    return respond(service.record_evidence_gate_review, db, payload)


@router.get("/audit-bundle")
def audit_bundle(db: Session = Depends(get_db)):
    return respond(service.export_audit, db)


@router.get("/audit-handoff")
def audit_handoff(artifact_key: str | None = None, db: Session = Depends(get_db)):
    return respond(service.export_audit_handoff, db, artifact_key=artifact_key)
