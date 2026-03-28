from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db.session import get_db
from app.models.entities import FocusSession, Item, SessionItem
from app.schemas.sessions import (
    SessionArtifactOut,
    SessionFinishResponse,
    SessionFinishRequest,
    SessionItemOut,
    SessionMetricsOut,
    SessionOut,
    SessionStartRequest,
    SessionTodoCalendarEventOut,
    SessionTodoCalendarImportResponse,
    SessionTodoCalendarPreviewResponse,
    SessionTodoCalendarRequest,
)
from app.services.session_artifact_service import list_session_artifacts
from app.services.mac_calendar_service import (
    build_todo_calendar_preview,
    import_todo_preview_to_mac_calendar,
)
from app.services.language import normalize_output_language
from app.services.session_service import (
    compute_session_metrics,
    finish_session,
    gather_items_in_window,
)
from app.services.work_task_service import build_todo_draft
from app.services.user_context import ensure_demo_user


router = APIRouter(prefix="/api/sessions", tags=["sessions"])
settings = get_settings()


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _get_session_or_404(db: Session, session_id: UUID) -> FocusSession:
    session = db.scalar(
        select(FocusSession)
        .where(FocusSession.id == session_id)
        .where(FocusSession.user_id == settings.single_user_id)
        .options(
            selectinload(FocusSession.session_items)
            .selectinload(SessionItem.item)
            .selectinload(Item.tags)
        )
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _build_session_out(session: FocusSession, items: list[Item]) -> SessionOut:
    metrics = compute_session_metrics(items)
    session_items = [
        SessionItemOut(
            id=item.id,
            title=item.title,
            source_domain=item.source_domain,
            short_summary=item.short_summary,
            action_suggestion=item.action_suggestion,
            score_value=float(item.score_value) if item.score_value is not None else None,
            tags=[tag.tag_name for tag in item.tags],
        )
        for item in items
    ]
    return SessionOut(
        id=session.id,
        user_id=session.user_id,
        goal_text=session.goal_text,
        output_language=normalize_output_language(session.output_language),
        duration_minutes=session.duration_minutes,
        start_time=_ensure_utc(session.start_time),
        end_time=_ensure_utc(session.end_time),
        status=session.status,
        summary_text=session.summary_text,
        created_at=_ensure_utc(session.created_at),
        metrics=SessionMetricsOut(
            new_content_count=metrics.new_content_count,
            deep_read_count=metrics.deep_read_count,
            later_count=metrics.later_count,
            skip_count=metrics.skip_count,
        ),
        items=session_items,
    )


def _resolve_session_items(db: Session, session: FocusSession) -> list[Item]:
    if session.status == "running":
        return gather_items_in_window(
            db,
            user_id=session.user_id,
            start_time=session.start_time,
            end_time=datetime.now(timezone.utc),
        )
    return [row.item for row in session.session_items if row.item is not None]


@router.post("/start", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def start_session(payload: SessionStartRequest, db: Session = Depends(get_db)) -> SessionOut:
    ensure_demo_user(db)

    session = FocusSession(
        user_id=settings.single_user_id,
        goal_text=payload.goal_text,
        output_language=payload.output_language,
        duration_minutes=payload.duration_minutes,
        start_time=datetime.now(timezone.utc),
        status="running",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _build_session_out(session, [])


@router.post("/{session_id}/finish", response_model=SessionFinishResponse)
def finish_user_session(
    session_id: UUID,
    payload: SessionFinishRequest | None = None,
    db: Session = Depends(get_db),
) -> SessionFinishResponse:
    ensure_demo_user(db)
    session = _get_session_or_404(db, session_id)
    if session.status != "running":
        raise HTTPException(status_code=400, detail="Session already finished or cancelled")

    resolved_language = normalize_output_language(
        payload.output_language if payload else session.output_language
    )
    session.output_language = resolved_language

    try:
        session, _, _ = finish_session(db, session, output_language=resolved_language)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    db.refresh(session)

    finished_items = [
        row.item
        for row in session.session_items
        if row.item is not None
    ]
    return SessionFinishResponse(session=_build_session_out(session, finished_items))


@router.get("/latest", response_model=SessionOut)
def get_latest_session(db: Session = Depends(get_db)) -> SessionOut:
    ensure_demo_user(db)
    session = db.scalar(
        select(FocusSession)
        .where(FocusSession.user_id == settings.single_user_id)
        .options(
            selectinload(FocusSession.session_items)
            .selectinload(SessionItem.item)
            .selectinload(Item.tags)
        )
        .order_by(desc(FocusSession.start_time))
        .limit(1)
    )
    if not session:
        raise HTTPException(status_code=404, detail="No session found")

    items = _resolve_session_items(db, session)
    return _build_session_out(session, items)


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: UUID, db: Session = Depends(get_db)) -> SessionOut:
    ensure_demo_user(db)
    session = _get_session_or_404(db, session_id)
    items = _resolve_session_items(db, session)

    return _build_session_out(session, items)


@router.get("/{session_id}/artifacts", response_model=list[SessionArtifactOut])
def get_session_artifacts(session_id: UUID, db: Session = Depends(get_db)) -> list[SessionArtifactOut]:
    ensure_demo_user(db)
    _ = _get_session_or_404(db, session_id)
    return [SessionArtifactOut(**item) for item in list_session_artifacts(db, session_id)]


def _resolve_todo_markdown(
    *,
    session: FocusSession,
    items: list[Item],
    payload: SessionTodoCalendarRequest,
) -> tuple[str, str]:
    resolved_language = normalize_output_language(
        payload.output_language or session.output_language
    )
    todo_markdown = (payload.todo_markdown or "").strip()
    if not todo_markdown:
        todo_markdown = build_todo_draft(
            session,
            items,
            output_language=resolved_language,
        )
    return todo_markdown, resolved_language


@router.post(
    "/{session_id}/todo-calendar-preview",
    response_model=SessionTodoCalendarPreviewResponse,
)
def preview_todo_calendar_import(
    session_id: UUID,
    payload: SessionTodoCalendarRequest | None = None,
    db: Session = Depends(get_db),
) -> SessionTodoCalendarPreviewResponse:
    ensure_demo_user(db)
    session = _get_session_or_404(db, session_id)
    items = _resolve_session_items(db, session)
    resolved_payload = payload or SessionTodoCalendarRequest()
    todo_markdown, resolved_language = _resolve_todo_markdown(
        session=session,
        items=items,
        payload=resolved_payload,
    )
    preview = build_todo_calendar_preview(
        session=session,
        todo_markdown=todo_markdown,
        output_language=resolved_language,
        calendar_name=resolved_payload.calendar_name,
    )
    return SessionTodoCalendarPreviewResponse(
        calendar_name=preview.calendar_name,
        summary_title=preview.summary_title,
        task_count=preview.task_count,
        tasks=preview.tasks,
        events=[
            SessionTodoCalendarEventOut(
                title=event.title,
                notes=event.notes,
                start_time=event.start_time,
                end_time=event.end_time,
            )
            for event in preview.events
        ],
        markdown=preview.markdown,
    )


@router.post(
    "/{session_id}/todo-calendar-import",
    response_model=SessionTodoCalendarImportResponse,
)
def import_todo_calendar(
    session_id: UUID,
    payload: SessionTodoCalendarRequest | None = None,
    db: Session = Depends(get_db),
) -> SessionTodoCalendarImportResponse:
    ensure_demo_user(db)
    session = _get_session_or_404(db, session_id)
    items = _resolve_session_items(db, session)
    resolved_payload = payload or SessionTodoCalendarRequest()
    todo_markdown, resolved_language = _resolve_todo_markdown(
        session=session,
        items=items,
        payload=resolved_payload,
    )
    preview = build_todo_calendar_preview(
        session=session,
        todo_markdown=todo_markdown,
        output_language=resolved_language,
        calendar_name=resolved_payload.calendar_name,
    )
    try:
        imported_titles = import_todo_preview_to_mac_calendar(preview)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return SessionTodoCalendarImportResponse(
        calendar_name=preview.calendar_name,
        imported_count=len(imported_titles),
        imported_titles=imported_titles,
    )
