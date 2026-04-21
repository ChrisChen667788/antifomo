from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.entities import WorkTask
from app.schemas.tasks import WorkTaskCreateRequest, WorkTaskOut
from app.services.task_runtime import create_and_execute_task
from app.services.user_context import ensure_demo_user


router = APIRouter(prefix="/api/tasks", tags=["tasks"])
settings = get_settings()


def _get_task_or_404(db: Session, task_id: UUID) -> WorkTask:
    task = db.scalar(
        select(WorkTask)
        .where(WorkTask.id == task_id)
        .where(WorkTask.user_id == settings.single_user_id)
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("", response_model=WorkTaskOut, status_code=status.HTTP_201_CREATED)
def create_task(payload: WorkTaskCreateRequest, db: Session = Depends(get_db)) -> WorkTaskOut:
    ensure_demo_user(db)
    task = create_and_execute_task(
        db,
        user_id=settings.single_user_id,
        task_type=payload.task_type,
        session_id=payload.session_id,
        input_payload=payload.input_payload,
    )
    return WorkTaskOut.model_validate(task)


@router.get("/{task_id}", response_model=WorkTaskOut)
def get_task(task_id: UUID, db: Session = Depends(get_db)) -> WorkTaskOut:
    ensure_demo_user(db)
    task = _get_task_or_404(db, task_id)
    return WorkTaskOut.model_validate(task)
