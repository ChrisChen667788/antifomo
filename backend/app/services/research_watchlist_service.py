from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.research_entities import ResearchWatchlist, ResearchWatchlistChangeEvent


settings = get_settings()


def _normalize_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _serialize_change_event(event: ResearchWatchlistChangeEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "watchlist_id": str(event.watchlist_id),
        "change_type": event.change_type,
        "summary": event.summary,
        "payload": event.payload or {},
        "severity": event.severity,
        "created_at": event.created_at,
    }


def _serialize_watchlist(
    watchlist: ResearchWatchlist,
    *,
    latest_changes: list[ResearchWatchlistChangeEvent] | None = None,
) -> dict[str, Any]:
    return {
        "id": str(watchlist.id),
        "tracking_topic_id": str(watchlist.tracking_topic_id) if watchlist.tracking_topic_id else None,
        "name": watchlist.name,
        "watch_type": watchlist.watch_type,
        "query": watchlist.query,
        "research_focus": watchlist.tracking_topic.research_focus if watchlist.tracking_topic else "",
        "perspective": watchlist.tracking_topic.perspective if watchlist.tracking_topic else "all",
        "region_filter": watchlist.region_filter,
        "industry_filter": watchlist.industry_filter,
        "alert_level": watchlist.alert_level,
        "schedule": watchlist.schedule,
        "status": watchlist.status,
        "last_checked_at": watchlist.last_checked_at,
        "created_at": watchlist.created_at,
        "updated_at": watchlist.updated_at,
        "latest_changes": [
            _serialize_change_event(item) for item in (latest_changes or [])
        ],
    }


def list_watchlists(db: Session) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(ResearchWatchlist)
        .where(ResearchWatchlist.user_id == settings.single_user_id)
        .order_by(desc(ResearchWatchlist.updated_at))
    ).all()
    result: list[dict[str, Any]] = []
    for row in rows:
        latest_changes = db.scalars(
            select(ResearchWatchlistChangeEvent)
            .where(ResearchWatchlistChangeEvent.watchlist_id == row.id)
            .order_by(desc(ResearchWatchlistChangeEvent.created_at))
            .limit(3)
        ).all()
        result.append(_serialize_watchlist(row, latest_changes=list(latest_changes)))
    return result


def get_watchlist_model(db: Session, watchlist_id: str) -> ResearchWatchlist | None:
    try:
        parsed_id = uuid.UUID(str(watchlist_id))
    except ValueError:
        return None
    return db.scalar(
        select(ResearchWatchlist)
        .where(ResearchWatchlist.id == parsed_id)
        .where(ResearchWatchlist.user_id == settings.single_user_id)
    )


def save_watchlist(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    watchlist_id = payload.get("id")
    existing = get_watchlist_model(db, str(watchlist_id)) if watchlist_id else None
    tracking_topic_id = payload.get("tracking_topic_id")
    parsed_tracking_topic_id: uuid.UUID | None = None
    if tracking_topic_id:
        try:
            parsed_tracking_topic_id = uuid.UUID(str(tracking_topic_id))
        except ValueError:
            parsed_tracking_topic_id = None
    watchlist = existing or ResearchWatchlist(user_id=settings.single_user_id)
    watchlist.tracking_topic_id = parsed_tracking_topic_id
    watchlist.name = str(payload.get("name") or "未命名 Watchlist")
    watchlist.watch_type = str(payload.get("watch_type") or "topic")
    watchlist.query = str(payload.get("query") or "")
    watchlist.region_filter = str(payload.get("region_filter") or "")
    watchlist.industry_filter = str(payload.get("industry_filter") or "")
    watchlist.alert_level = str(payload.get("alert_level") or "medium")
    watchlist.schedule = str(payload.get("schedule") or "manual")
    watchlist.status = str(payload.get("status") or "active")
    if payload.get("last_checked_at"):
        watchlist.last_checked_at = _normalize_datetime(payload.get("last_checked_at"))
    db.add(watchlist)
    db.commit()
    db.refresh(watchlist)
    return _serialize_watchlist(watchlist)


def list_watchlist_change_events(db: Session, watchlist_id: str) -> list[dict[str, Any]]:
    watchlist = get_watchlist_model(db, watchlist_id)
    if watchlist is None:
        return []
    events = db.scalars(
        select(ResearchWatchlistChangeEvent)
        .where(ResearchWatchlistChangeEvent.watchlist_id == watchlist.id)
        .order_by(desc(ResearchWatchlistChangeEvent.created_at))
        .limit(30)
    ).all()
    return [_serialize_change_event(item) for item in events]


def append_watchlist_change_events(
    db: Session,
    watchlist_id: str,
    events: list[dict[str, Any]],
    *,
    checked_at: datetime | None = None,
) -> list[dict[str, Any]]:
    watchlist = get_watchlist_model(db, watchlist_id)
    if watchlist is None:
        return []
    created: list[ResearchWatchlistChangeEvent] = []
    for payload in events:
        event = ResearchWatchlistChangeEvent(
            watchlist_id=watchlist.id,
            change_type=str(payload.get("change_type") or "rewritten"),
            summary=str(payload.get("summary") or ""),
            payload=payload.get("payload") if isinstance(payload.get("payload"), dict) else {},
            severity=str(payload.get("severity") or "medium"),
        )
        db.add(event)
        created.append(event)
    watchlist.last_checked_at = checked_at or datetime.now(timezone.utc)
    db.add(watchlist)
    db.commit()
    for event in created:
        db.refresh(event)
    db.refresh(watchlist)
    return [_serialize_change_event(item) for item in created]
