from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.preferences import (
    PreferenceBoostRequest,
    PreferenceBoostResponse,
    PreferenceResetRequest,
    PreferenceSummaryOut,
)
from app.services.preference_service import build_preference_summary, boost_preference, reset_preferences
from app.services.user_context import ensure_demo_user


router = APIRouter(prefix="/api/preferences", tags=["preferences"])
settings = get_settings()


@router.get("/summary", response_model=PreferenceSummaryOut)
def get_preference_summary(db: Session = Depends(get_db)) -> PreferenceSummaryOut:
    ensure_demo_user(db)
    return build_preference_summary(db, settings.single_user_id)


@router.post("/reset", response_model=PreferenceSummaryOut)
def reset_preference_summary(
    payload: PreferenceResetRequest | None = None,
    db: Session = Depends(get_db),
) -> PreferenceSummaryOut:
    ensure_demo_user(db)
    scope = payload.scope if payload else "all"
    return reset_preferences(db, settings.single_user_id, scope=scope)


@router.post("/boost", response_model=PreferenceBoostResponse)
def boost_preference_summary(
    payload: PreferenceBoostRequest,
    db: Session = Depends(get_db),
) -> PreferenceBoostResponse:
    ensure_demo_user(db)
    try:
        updated_score, summary = boost_preference(
            db,
            settings.single_user_id,
            dimension=payload.dimension,
            key=payload.key,
            delta=payload.delta,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PreferenceBoostResponse(
        dimension=payload.dimension,
        key=payload.key.strip(),
        delta=payload.delta,
        updated_score=updated_score,
        summary=summary,
    )
