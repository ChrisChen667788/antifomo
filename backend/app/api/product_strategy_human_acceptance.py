from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.product_strategy_human_acceptance import HumanAcceptanceCreateRequest, HumanAcceptanceCreateOut, HumanAcceptanceLandscapeOut, ReleaseEvidenceBridgeOut
from app.services.product_strategy import human_acceptance_service as service
from app.services.product_strategy.office_evidence_service import OfficeEvidenceError
from app.services.product_strategy.visual_evidence_service import VisualEvidenceError
from app.services.product_strategy.operation_evidence_service import OperationEvidenceError

router = APIRouter(prefix="/api/product-strategy", tags=["product-strategy"])


def guarded(call, *args):
    try:
        return call(*args)
    except (service.HumanAcceptanceError, OfficeEvidenceError, VisualEvidenceError, OperationEvidenceError) as error:
        raise HTTPException(status_code=409, detail={"code": error.code, "message": str(error), **service.GATES}) from error


@router.get("/human-acceptance-events", response_model=HumanAcceptanceLandscapeOut)
def list_events(db: Session = Depends(get_db)):
    return guarded(service.list_events, db)


@router.post("/human-acceptance-events", response_model=HumanAcceptanceCreateOut, status_code=201)
def create_event(payload: HumanAcceptanceCreateRequest, db: Session = Depends(get_db)):
    return guarded(service.create_event, db, payload)


@router.get("/release-evidence-bridge", response_model=ReleaseEvidenceBridgeOut)
def bridge(artifact_key: str = Query(min_length=1, max_length=180), db: Session = Depends(get_db)):
    return guarded(service.release_bridge, db, artifact_key)
