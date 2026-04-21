from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.focus_assistant import (
    FocusAssistantExecuteOut,
    FocusAssistantExecuteRequest,
    FocusAssistantPlanOut,
    FocusAssistantPlanRequest,
)
from app.schemas.tasks import WorkTaskOut
from app.services.focus_assistant import build_focus_assistant_plan, execute_focus_assistant_action
from app.services.user_context import ensure_demo_user


router = APIRouter(prefix="/api/focus-assistant", tags=["focus-assistant"])


@router.post("/plan", response_model=FocusAssistantPlanOut)
def plan_focus_assistant(
    payload: FocusAssistantPlanRequest,
    db: Session = Depends(get_db),
) -> FocusAssistantPlanOut:
    ensure_demo_user(db)
    return build_focus_assistant_plan(db, payload)


@router.post("/execute", response_model=FocusAssistantExecuteOut, status_code=status.HTTP_202_ACCEPTED)
def execute_focus_assistant(
    payload: FocusAssistantExecuteRequest,
    db: Session = Depends(get_db),
) -> FocusAssistantExecuteOut:
    ensure_demo_user(db)
    try:
        action, task = execute_focus_assistant_action(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    channel_label = "workbuddy" if payload.channel == "workbuddy" else "direct"
    return FocusAssistantExecuteOut(
        accepted=True,
        action_key=payload.action_key,
        channel_used=payload.channel,
        message=f"{action.title} 已通过 {channel_label} 通道执行",
        task=WorkTaskOut.model_validate(task),
    )
