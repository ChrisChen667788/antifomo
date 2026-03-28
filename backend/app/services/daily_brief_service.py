from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import subprocess
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import Item
from app.models.research_entities import ResearchWatchlist, ResearchWatchlistChangeEvent
from app.models.workflow_entities import DailyBriefSnapshot
from app.services.content_extractor import normalize_text


PROJECT_ROOT = Path(__file__).resolve().parents[3]
AUDIO_ROOT = PROJECT_ROOT / ".storage" / "daily_brief_audio"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _today_key() -> str:
    return _utc_now().strftime("%Y-%m-%d")


def _top_items(db: Session, *, user_id: UUID, limit: int = 5) -> list[dict[str, Any]]:
    items = list(
        db.scalars(
            select(Item)
            .where(Item.user_id == user_id)
            .where(Item.status == "ready")
            .options(selectinload(Item.tags))
            .order_by(desc(Item.created_at))
            .limit(limit)
        )
    )
    rows: list[dict[str, Any]] = []
    for item in items:
        rows.append(
            {
                "id": str(item.id),
                "title": normalize_text(item.title or "") or "未命名内容",
                "source_domain": item.source_domain or "unknown",
                "summary": normalize_text(item.short_summary or item.long_summary or item.source_url or ""),
                "action_suggestion": item.action_suggestion or "later",
                "score_value": float(item.score_value) if item.score_value is not None else None,
                "source_url": item.source_url,
            }
        )
    return rows


def _latest_watchlist_changes(db: Session, *, user_id: UUID, limit: int = 4) -> list[dict[str, Any]]:
    events = list(
        db.scalars(
            select(ResearchWatchlistChangeEvent)
            .join(ResearchWatchlist, ResearchWatchlist.id == ResearchWatchlistChangeEvent.watchlist_id)
            .where(ResearchWatchlist.user_id == user_id)
            .order_by(desc(ResearchWatchlistChangeEvent.created_at))
            .limit(limit)
        )
    )
    return [
        {
            "id": str(event.id),
            "change_type": event.change_type,
            "summary": event.summary,
            "severity": event.severity,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }
        for event in events
    ]


def _build_audio_script(payload: dict[str, Any]) -> str:
    lines = ["Anti-fomo 今日简报。"]
    headline = normalize_text(str(payload.get("headline") or ""))
    if headline:
        lines.append(headline)
    for item in list(payload.get("top_items") or [])[:3]:
        title = normalize_text(str(item.get("title") or ""))
        summary = normalize_text(str(item.get("summary") or ""))
        if title:
            lines.append(f"重点内容：{title}。")
        if summary:
            lines.append(summary[:110])
    for change in list(payload.get("watchlist_changes") or [])[:2]:
        summary = normalize_text(str(change.get("summary") or ""))
        if summary:
            lines.append(f"Watchlist 变化：{summary}。")
    return " ".join(lines)


def _generate_audio(snapshot: DailyBriefSnapshot, *, script: str) -> tuple[str, str | None]:
    AUDIO_ROOT.mkdir(parents=True, exist_ok=True)
    audio_path = AUDIO_ROOT / f"{snapshot.id}.aiff"
    try:
        subprocess.run(["say", "-o", str(audio_path), script], check=True, capture_output=True, text=True, timeout=20)
    except Exception:
        return "unavailable", None
    return "ready", f"/api/mobile/daily-brief/audio/{snapshot.id}"


def _build_brief_payload(db: Session, *, user_id: UUID) -> dict[str, Any]:
    top_items = _top_items(db, user_id=user_id, limit=5)
    watchlist_changes = _latest_watchlist_changes(db, user_id=user_id, limit=4)
    headline = normalize_text(top_items[0]["title"]) if top_items else "今天先处理 watchlist 变化和最新高价值内容。"
    summary = "；".join(
        [row["title"] for row in top_items[:3]]
        + [change["summary"] for change in watchlist_changes[:2]]
    )
    return {
        "headline": headline,
        "summary": summary or "今天暂无新的高价值内容，建议刷新专题或继续处理稍后读。",
        "top_items": top_items,
        "watchlist_changes": watchlist_changes,
        "generated_at": _utc_now().isoformat(),
    }


def build_daily_brief_snapshot(db: Session, *, user_id: UUID, force_refresh: bool = False) -> DailyBriefSnapshot:
    brief_date = _today_key()
    existing = db.scalar(
        select(DailyBriefSnapshot)
        .where(DailyBriefSnapshot.user_id == user_id)
        .where(DailyBriefSnapshot.brief_date == brief_date)
        .order_by(desc(DailyBriefSnapshot.created_at))
        .limit(1)
    )
    if existing is not None and not force_refresh:
        return existing

    payload = _build_brief_payload(db, user_id=user_id)
    if existing is None:
        snapshot = DailyBriefSnapshot(
            user_id=user_id,
            brief_date=brief_date,
            items_payload=payload,
            audio_status="pending",
        )
        db.add(snapshot)
        db.flush()
    else:
        snapshot = existing
        snapshot.items_payload = payload
        snapshot.audio_status = "pending"
        snapshot.audio_url = None
        snapshot.audio_script = None
        db.add(snapshot)
        db.flush()

    script = _build_audio_script(payload)
    audio_status, audio_url = _generate_audio(snapshot, script=script)
    snapshot.audio_status = audio_status
    snapshot.audio_url = audio_url
    snapshot.audio_script = script
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def serialize_daily_brief(snapshot: DailyBriefSnapshot) -> dict[str, Any]:
    payload = snapshot.items_payload or {}
    return {
        "snapshot_id": str(snapshot.id),
        "brief_date": snapshot.brief_date,
        "headline": payload.get("headline") or "",
        "summary": payload.get("summary") or "",
        "top_items": payload.get("top_items") or [],
        "watchlist_changes": payload.get("watchlist_changes") or [],
        "generated_at": payload.get("generated_at") or snapshot.created_at,
        "audio_status": snapshot.audio_status,
        "audio_url": snapshot.audio_url,
        "audio_script": snapshot.audio_script,
    }
