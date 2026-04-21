from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.workflow_entities import DailyBriefSnapshot
from app.schemas.mobile import MobileDailyBriefResponse
from app.services.daily_brief_service import build_daily_brief_snapshot, serialize_daily_brief
from app.services.user_context import ensure_demo_user


router = APIRouter(prefix="/api/mobile", tags=["mobile"])
settings = get_settings()


@router.get("/daily-brief", response_model=MobileDailyBriefResponse)
def get_mobile_daily_brief(
    force_refresh: bool = False,
    db: Session = Depends(get_db),
) -> MobileDailyBriefResponse:
    ensure_demo_user(db)
    snapshot = build_daily_brief_snapshot(db, user_id=settings.single_user_id, force_refresh=force_refresh)
    return MobileDailyBriefResponse(**serialize_daily_brief(snapshot))


@router.get("/daily-brief/audio/{snapshot_id}")
def get_mobile_daily_brief_audio(snapshot_id: UUID, db: Session = Depends(get_db)) -> FileResponse:
    ensure_demo_user(db)
    snapshot = db.scalar(
        select(DailyBriefSnapshot)
        .where(DailyBriefSnapshot.id == snapshot_id)
        .where(DailyBriefSnapshot.user_id == settings.single_user_id)
    )
    if snapshot is None or not snapshot.audio_url:
        raise HTTPException(status_code=404, detail="Daily brief audio not found")
    storage_path = Path(__file__).resolve().parents[3] / ".storage" / "daily_brief_audio" / f"{snapshot.id}.aiff"
    if not storage_path.exists():
        raise HTTPException(status_code=404, detail="Audio file missing")
    return FileResponse(path=storage_path, media_type="audio/aiff", filename=storage_path.name)
