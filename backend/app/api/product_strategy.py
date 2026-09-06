from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.product_strategy import (
    ArtifactAcceptanceInitializationOut,
    ArtifactAcceptanceLandscapeOut,
    CompetitiveLandscapeOut,
    DecisionContextPacketInitializationOut,
    DecisionContextPacketLandscapeOut,
    IterationProgramInitializationOut,
    IterationProgramLandscapeOut,
    OfficeEvidenceReceiptCreateOut,
    OfficeEvidenceReceiptCreateRequest,
    OfficeEvidenceReceiptLandscapeOut,
    ProductStrategySeedOut,
)
from app.services.product_strategy.artifact_acceptance_catalog import preview_artifact_acceptance
from app.services.product_strategy.artifact_acceptance_service import (
    DecisionContextPacketsRequiredError,
    get_persisted_artifact_acceptance,
    initialize_artifact_acceptance,
)
from app.services.product_strategy.context_packet_catalog import preview_decision_context_packets
from app.services.product_strategy.context_packet_service import (
    get_persisted_decision_context_packets,
    initialize_decision_context_packets,
)
from app.services.product_strategy.iteration_program_catalog import preview_iteration_program
from app.services.product_strategy.iteration_program_service import (
    get_persisted_iteration_program,
    initialize_iteration_program,
)
from app.services.product_strategy.office_evidence_service import (
    OfficeEvidenceError,
    create_office_evidence_receipt,
    list_office_evidence_receipts,
)
from app.services.product_strategy.catalog import preview_competitive_landscape
from app.services.product_strategy.service import get_persisted_competitive_landscape, seed_competitive_landscape


router = APIRouter(prefix="/api/product-strategy", tags=["product-strategy"])


@router.get("/competitive-landscape/preview", response_model=CompetitiveLandscapeOut)
def get_competitive_landscape_preview() -> dict:
    """Read-only static catalog; it performs no network request and no database write."""

    return preview_competitive_landscape()


@router.get("/competitive-landscape", response_model=CompetitiveLandscapeOut)
def get_competitive_landscape(db: Session = Depends(get_db)) -> dict:
    """Return only explicitly persisted product-intelligence observations."""

    return get_persisted_competitive_landscape(db)


@router.post("/competitive-landscape/seed", response_model=ProductStrategySeedOut)
def seed_competitive_landscape_catalog(db: Session = Depends(get_db)) -> dict:
    """Explicitly initialize the catalog; human-managed rows are never overwritten."""

    return seed_competitive_landscape(db)


@router.get("/decision-context-packets/preview", response_model=DecisionContextPacketLandscapeOut)
def get_decision_context_packets_preview() -> dict:
    """Read-only 2.10.1 packet preview; it performs no database write."""

    return preview_decision_context_packets()


@router.get("/decision-context-packets", response_model=DecisionContextPacketLandscapeOut)
def get_decision_context_packets(db: Session = Depends(get_db)) -> dict:
    """Return only packets materialized by the explicit initializer."""

    return get_persisted_decision_context_packets(db)


@router.post("/decision-context-packets/initialize", response_model=DecisionContextPacketInitializationOut)
def initialize_context_packets(db: Session = Depends(get_db)) -> dict:
    """Materialize approved decision context without authorizing execution or release."""

    return initialize_decision_context_packets(db)


@router.get("/artifact-acceptance/preview", response_model=ArtifactAcceptanceLandscapeOut)
def get_artifact_acceptance_preview() -> dict:
    """Read-only 2.10.2 HOLD-only acceptance template preview."""

    return preview_artifact_acceptance()


@router.get("/artifact-acceptance", response_model=ArtifactAcceptanceLandscapeOut)
def get_artifact_acceptance(db: Session = Depends(get_db)) -> dict:
    """Return only templates materialized after 2.10.1 packet initialization."""

    return get_persisted_artifact_acceptance(db)


@router.post("/artifact-acceptance/initialize", response_model=ArtifactAcceptanceInitializationOut)
def initialize_artifact_acceptance_templates(db: Session = Depends(get_db)) -> dict:
    """Explicitly initialize HOLD-only templates; never accept, execute, or release."""

    try:
        return initialize_artifact_acceptance(db)
    except DecisionContextPacketsRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "decision_context_packets_required",
                "message": "2.10.2 初始化需要先显式持久化可用的 2.10.1 决策上下文包；不会自动初始化。",
                "missing_context_packet_keys": error.missing_packet_keys,
                "unusable_context_packet_keys": error.unusable_packet_keys,
                "can_auto_accept": False,
                "can_auto_execute": False,
                "can_auto_approve_release": False,
            },
        ) from error


@router.get("/office-evidence-receipts", response_model=OfficeEvidenceReceiptLandscapeOut)
def get_office_evidence_receipts(db: Session = Depends(get_db)) -> dict:
    """Return immutable 2.10.5 local Office evidence without changing HOLD."""

    return list_office_evidence_receipts(db)


@router.post("/office-evidence-receipts", response_model=OfficeEvidenceReceiptCreateOut, status_code=201)
def register_office_evidence_receipt(
    payload: OfficeEvidenceReceiptCreateRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Validate and persist a local Office receipt; never accept or release it."""

    try:
        return create_office_evidence_receipt(
            db,
            artifact_key=payload.artifact_key,
            file_name=payload.file_name,
            media_type=payload.media_type,
            file_base64=payload.file_base64,
            source_version=payload.source_version,
            required_texts=payload.required_texts,
            rendered_pdf_base64=payload.rendered_pdf_base64,
            render_engine=payload.render_engine,
        )
    except OfficeEvidenceError as error:
        status_code = status.HTTP_409_CONFLICT if error.code == "artifact_acceptance_draft_required" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail={
                "code": error.code,
                "message": str(error),
                "acceptance_status": "hold",
                "can_auto_accept": False,
                "can_auto_approve_release": False,
            },
        ) from error


@router.get("/iteration-program/preview", response_model=IterationProgramLandscapeOut)
def get_iteration_program_preview() -> dict:
    """Read-only 2.10.3–2.11.7 plan and official-agent observation preview."""

    return preview_iteration_program()


@router.get("/iteration-program", response_model=IterationProgramLandscapeOut)
def get_iteration_program(db: Session = Depends(get_db)) -> dict:
    """Return only explicitly materialized fifteen-version control records."""

    return get_persisted_iteration_program(db)


@router.post("/iteration-program/initialize", response_model=IterationProgramInitializationOut)
def initialize_product_strategy_iteration_program(db: Session = Depends(get_db)) -> dict:
    """Persist a reviewable program; it never accepts, executes, or releases."""

    return initialize_iteration_program(db)
