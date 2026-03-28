from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db.session import get_db
from app.models.entities import Item
from app.schemas.feedback import FeedbackCreateRequest, FeedbackCreateResponse
from app.services.feedback_service import apply_feedback
from app.services.preference_service import capture_preference_snapshot
from app.services.user_context import ensure_demo_user


router = APIRouter(prefix="/api", tags=["feedback"])
settings = get_settings()


@router.post("/feedback", response_model=FeedbackCreateResponse)
def create_feedback(payload: FeedbackCreateRequest, db: Session = Depends(get_db)) -> FeedbackCreateResponse:
    ensure_demo_user(db)
    item = db.scalar(
        select(Item)
        .where(Item.id == payload.item_id)
        .where(Item.user_id == settings.single_user_id)
        .options(selectinload(Item.tags))
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    apply_feedback(
        db,
        user_id=settings.single_user_id,
        item=item,
        feedback_type=payload.feedback_type,
    )
    capture_preference_snapshot(db, settings.single_user_id)
    db.commit()

    return FeedbackCreateResponse(
        item_id=payload.item_id,
        feedback_type=payload.feedback_type,
        status="ok",
    )
