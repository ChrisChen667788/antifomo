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
