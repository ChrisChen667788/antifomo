from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.research_entities import ResearchWatchlist, ResearchWatchlistChangeEvent


settings = get_settings()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_watchlist_schedule(value: str | None) -> str:
    normalized = str(value or "manual").strip().lower()
    aliases = {
        "weekday": "weekdays",
        "workdays": "weekdays",
        "weekdays_only": "weekdays",
        "half_daily": "twice_daily",
        "every12h": "twice_daily",
        "12h": "twice_daily",
        "every6h": "every_6h",
        "6h": "every_6h",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized in {"manual", "daily", "twice_daily", "weekdays", "every_6h"}:
        return normalized
    return "manual"


def _next_weekday(value: datetime) -> datetime:
    candidate = value
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def compute_watchlist_next_due_at(
    watchlist: ResearchWatchlist,
    *,
    now: datetime | None = None,
) -> datetime | None:
    schedule = normalize_watchlist_schedule(watchlist.schedule)
    if watchlist.status != "active" or schedule == "manual":
        return None
    reference_now = _normalize_datetime(now) or _utc_now()
    baseline = _normalize_datetime(watchlist.last_checked_at)
    if baseline is None:
        return reference_now
    if schedule == "every_6h":
        return baseline + timedelta(hours=6)
    if schedule == "twice_daily":
        return baseline + timedelta(hours=12)
    if schedule == "weekdays":
        return _next_weekday(baseline + timedelta(days=1))
    return baseline + timedelta(days=1)


def is_watchlist_due(
    watchlist: ResearchWatchlist,
    *,
    now: datetime | None = None,
) -> bool:
    reference_now = _normalize_datetime(now) or _utc_now()
    next_due_at = compute_watchlist_next_due_at(watchlist, now=reference_now)
    return next_due_at is not None and next_due_at <= reference_now


def _load_latest_changes(db: Session, watchlist_id: uuid.UUID, limit: int = 3) -> list[ResearchWatchlistChangeEvent]:
    return list(
        db.scalars(
            select(ResearchWatchlistChangeEvent)
            .where(ResearchWatchlistChangeEvent.watchlist_id == watchlist_id)
            .order_by(desc(ResearchWatchlistChangeEvent.created_at))
            .limit(limit)
        )
    )


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
    now: datetime | None = None,
) -> dict[str, Any]:
    reference_now = _normalize_datetime(now) or _utc_now()
    next_due_at = compute_watchlist_next_due_at(watchlist, now=reference_now)
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
        "next_due_at": next_due_at,
        "is_due": bool(next_due_at and next_due_at <= reference_now),
        "created_at": watchlist.created_at,
        "updated_at": watchlist.updated_at,
        "latest_changes": [
            _serialize_change_event(item) for item in (latest_changes or [])
        ],
    }


def list_watchlists(db: Session) -> list[dict[str, Any]]:
    reference_now = _utc_now()
    rows = db.scalars(
        select(ResearchWatchlist)
        .where(ResearchWatchlist.user_id == settings.single_user_id)
        .order_by(desc(ResearchWatchlist.updated_at))
    ).all()
    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            _serialize_watchlist(
                row,
                latest_changes=_load_latest_changes(db, row.id, limit=3),
                now=reference_now,
            )
        )
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


def get_watchlist_payload(db: Session, watchlist_id: str) -> dict[str, Any] | None:
    watchlist = get_watchlist_model(db, watchlist_id)
    if watchlist is None:
        return None
    return _serialize_watchlist(
        watchlist,
        latest_changes=_load_latest_changes(db, watchlist.id, limit=3),
        now=_utc_now(),
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
    watchlist.schedule = normalize_watchlist_schedule(str(payload.get("schedule") or "manual"))
    watchlist.status = str(payload.get("status") or "active")
    if payload.get("last_checked_at"):
        watchlist.last_checked_at = _normalize_datetime(payload.get("last_checked_at"))
    db.add(watchlist)
    db.commit()
    db.refresh(watchlist)
    return _serialize_watchlist(
        watchlist,
        latest_changes=_load_latest_changes(db, watchlist.id, limit=3),
        now=_utc_now(),
    )


def list_due_watchlists(
    db: Session,
    *,
    now: datetime | None = None,
    limit: int = 12,
) -> list[ResearchWatchlist]:
    reference_now = _normalize_datetime(now) or _utc_now()
    rows = list(
        db.scalars(
            select(ResearchWatchlist)
            .where(ResearchWatchlist.user_id == settings.single_user_id)
            .where(ResearchWatchlist.status == "active")
            .order_by(desc(ResearchWatchlist.updated_at))
        )
    )
    due_rows = [row for row in rows if is_watchlist_due(row, now=reference_now)]
    return due_rows[: max(1, limit)]


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
    watchlist.last_checked_at = checked_at or _utc_now()
    db.add(watchlist)
    db.commit()
    for event in created:
        db.refresh(event)
    db.refresh(watchlist)
    return [_serialize_change_event(item) for item in created]
