from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.task_envelopes import (
    TaskApprovalCreateRequest,
    TaskCancelRequest,
    TaskEnvelopeCreateOut,
    TaskEnvelopeCreateRequest,
    TaskEnvelopeOut,
    TaskReconcileRequest,
)
from app.services.task_envelope_service import (
    TaskEnvelopeError,
    approve_envelope,
    cancel_envelope,
    create_envelope,
    get_envelope,
    reconcile_envelope,
    serialize_envelope,
)
from app.services.user_context import ensure_demo_user


router = APIRouter(prefix="/api/task-envelopes", tags=["task-envelopes"])


def _raise_api_error(error: TaskEnvelopeError) -> None:
    raise HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": str(error)},
    ) from error


@router.post("", response_model=TaskEnvelopeCreateOut, status_code=status.HTTP_201_CREATED)
def create_task_envelope(
    payload: TaskEnvelopeCreateRequest,
    db: Session = Depends(get_db),
) -> TaskEnvelopeCreateOut:
    settings = get_settings()
    ensure_demo_user(db)
    db.commit()
    try:
        result = create_envelope(db, user_id=settings.single_user_id, request=payload)
    except TaskEnvelopeError as error:
        _raise_api_error(error)
    return TaskEnvelopeCreateOut.model_validate(result)


@router.get("/{task_id}", response_model=TaskEnvelopeOut)
def read_task_envelope(task_id: UUID, db: Session = Depends(get_db)) -> TaskEnvelopeOut:
    settings = get_settings()
    ensure_demo_user(db)
    try:
        envelope = get_envelope(db, user_id=settings.single_user_id, task_id=task_id)
        result = serialize_envelope(db, envelope)
    except TaskEnvelopeError as error:
        _raise_api_error(error)
    return TaskEnvelopeOut.model_validate(result)


@router.post("/{task_id}/approve", response_model=TaskEnvelopeOut)
def approve_task_envelope(
    task_id: UUID,
    payload: TaskApprovalCreateRequest,
    db: Session = Depends(get_db),
) -> TaskEnvelopeOut:
    settings = get_settings()
    ensure_demo_user(db)
    db.commit()
    try:
        result = approve_envelope(
            db,
            user_id=settings.single_user_id,
            task_id=task_id,
            request=payload,
        )
    except TaskEnvelopeError as error:
        _raise_api_error(error)
    return TaskEnvelopeOut.model_validate(result)


@router.post("/{task_id}/cancel", response_model=TaskEnvelopeOut)
def cancel_task_envelope(
    task_id: UUID,
    payload: TaskCancelRequest,
    db: Session = Depends(get_db),
) -> TaskEnvelopeOut:
    settings = get_settings()
    ensure_demo_user(db)
    db.commit()
    try:
        result = cancel_envelope(
            db,
            user_id=settings.single_user_id,
            task_id=task_id,
            request=payload,
        )
    except TaskEnvelopeError as error:
        _raise_api_error(error)
    return TaskEnvelopeOut.model_validate(result)


@router.post("/{task_id}/reconcile", response_model=TaskEnvelopeOut)
def reconcile_task_envelope(
    task_id: UUID,
    payload: TaskReconcileRequest,
    db: Session = Depends(get_db),
) -> TaskEnvelopeOut:
    settings = get_settings()
    ensure_demo_user(db)
    db.commit()
    try:
        result = reconcile_envelope(
            db,
            user_id=settings.single_user_id,
            task_id=task_id,
            request=payload,
        )
    except TaskEnvelopeError as error:
        _raise_api_error(error)
    return TaskEnvelopeOut.model_validate(result)
