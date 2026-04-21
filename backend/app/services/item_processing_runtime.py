from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Event, Lock, Thread
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.entities import Item
from app.services.item_processor import process_item
from app.services.knowledge_service import maybe_auto_archive_item
from app.services.language import normalize_output_language
from app.services.session_service import sync_running_sessions_for_item


settings = get_settings()

_active_item_ids: set[UUID] = set()
_active_item_lock = Lock()
_worker_lock = Lock()
_worker_stop_event: Event | None = None
_worker_thread: Thread | None = None


@dataclass(slots=True)
class ProcessRuntimeResult:
    item_id: UUID
    status: str
    output_language: str
    processing_error: str | None
    processing_attempts: int
    source_url: str | None


def _claim_item(item_id: UUID) -> bool:
    with _active_item_lock:
        if item_id in _active_item_ids:
            return False
        _active_item_ids.add(item_id)
        return True


def _release_item(item_id: UUID) -> None:
    with _active_item_lock:
        _active_item_ids.discard(item_id)


def prepare_item_for_processing(
    db: Session,
    item: Item,
    *,
    output_language: str | None = None,
) -> str:
    resolved_language = normalize_output_language(output_language or item.output_language)
    item.output_language = resolved_language
    item.status = "processing"
    item.processing_error = None
    item.processing_started_at = datetime.now(timezone.utc)
    item.processing_attempts = int(item.processing_attempts or 0) + 1
    db.add(item)
    return resolved_language


def process_item_in_session(
    db: Session,
    item: Item,
    *,
    output_language: str | None = None,
    auto_archive: bool = True,
) -> Item:
    resolved_language = prepare_item_for_processing(db, item, output_language=output_language)
    process_item(db, item, output_language=resolved_language)
    if auto_archive and item.status == "ready":
        maybe_auto_archive_item(db, item=item, output_language=resolved_language)
    if item.status == "ready":
        sync_running_sessions_for_item(db, item)
    db.add(item)
    return item


def process_item_by_id(
    item_id: UUID,
    *,
    output_language: str | None = None,
    auto_archive: bool = True,
) -> ProcessRuntimeResult | None:
    if not _claim_item(item_id):
        return None
    try:
        return _process_item_by_id_claimed(
            item_id,
            output_language=output_language,
            auto_archive=auto_archive,
        )
    finally:
        _release_item(item_id)


def _process_item_by_id_claimed(
    item_id: UUID,
    *,
    output_language: str | None = None,
    auto_archive: bool = True,
) -> ProcessRuntimeResult | None:
    db = SessionLocal()
    try:
        item = db.scalar(select(Item).where(Item.id == item_id).options(selectinload(Item.tags)))
        if not item:
            return None
        resolved_language = normalize_output_language(output_language or item.output_language)
        process_item_in_session(
            db,
            item,
            output_language=resolved_language,
            auto_archive=auto_archive,
        )
        db.commit()
        db.refresh(item)
        return ProcessRuntimeResult(
            item_id=item.id,
            status=item.status,
            output_language=item.output_language,
            processing_error=item.processing_error,
            processing_attempts=int(item.processing_attempts or 0),
            source_url=item.source_url,
        )
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        db.rollback()
        fallback_item = db.get(Item, item_id)
        if fallback_item:
            fallback_item.status = "failed"
            fallback_item.processing_error = str(exc)
            fallback_item.processed_at = datetime.now(timezone.utc)
            db.add(fallback_item)
            db.commit()
            return ProcessRuntimeResult(
                item_id=fallback_item.id,
                status=fallback_item.status,
                output_language=fallback_item.output_language,
                processing_error=fallback_item.processing_error,
                processing_attempts=int(fallback_item.processing_attempts or 0),
                source_url=fallback_item.source_url,
            )
        raise
    finally:
        db.close()


def recover_stale_items(
    *,
    limit: int | None = None,
    pending_grace_seconds: int | None = None,
    processing_stale_seconds: int | None = None,
    max_attempts: int | None = None,
    auto_archive: bool = True,
) -> dict[str, Any]:
    safe_limit = max(1, min(limit or settings.pending_item_recovery_batch_size, 200))
    pending_grace = max(1, int(pending_grace_seconds or settings.pending_item_grace_seconds))
    processing_stale = max(5, int(processing_stale_seconds or settings.processing_stale_seconds))
    allowed_attempts = max(1, int(max_attempts or settings.pending_item_max_attempts))

    now = datetime.now(timezone.utc)
    pending_before = now - timedelta(seconds=pending_grace)
    stale_before = now - timedelta(seconds=processing_stale)

    db = SessionLocal()
    try:
        candidates = list(
            db.scalars(
                select(Item)
                .where(Item.user_id == settings.single_user_id)
                .where(Item.processing_attempts < allowed_attempts)
                .where(
                    or_(
                        and_(
                            Item.status == "pending",
                            Item.created_at <= pending_before,
                        ),
                        and_(
                            Item.status == "processing",
                            or_(
                                Item.processing_started_at.is_(None),
                                Item.processing_started_at <= stale_before,
                            ),
                        ),
                    )
                )
                .order_by(Item.created_at.asc())
                .limit(safe_limit)
            )
        )
        candidate_ids = [item.id for item in candidates if _claim_item(item.id)]
    finally:
        db.close()

    processed = 0
    failed = 0
    item_ids: list[UUID] = []
    try:
        for item_id in candidate_ids:
            result = _process_item_by_id_claimed(
                item_id,
                output_language=None,
                auto_archive=auto_archive,
            )
            if result is None:
                continue
            item_ids.append(result.item_id)
            if result.status == "ready":
                processed += 1
            else:
                failed += 1
        return {
            "scanned": len(candidates),
            "recovered": processed,
            "failed": failed,
            "item_ids": item_ids,
        }
    finally:
        for item_id in candidate_ids:
            _release_item(item_id)


def _worker_loop(stop_event: Event) -> None:
    interval = max(3, int(settings.pending_item_recovery_interval_seconds))
    while not stop_event.wait(interval):
        try:
            recover_stale_items()
        except Exception:
            continue


def start_item_recovery_worker() -> None:
    global _worker_stop_event, _worker_thread
    if not settings.pending_item_recovery_enabled:
        return
    with _worker_lock:
        if _worker_thread and _worker_thread.is_alive():
            return
        _worker_stop_event = Event()
        _worker_thread = Thread(
            target=_worker_loop,
            args=(_worker_stop_event,),
            name="anti-fomo-item-recovery",
            daemon=True,
        )
        _worker_thread.start()


def stop_item_recovery_worker() -> None:
    global _worker_stop_event, _worker_thread
    with _worker_lock:
        if _worker_stop_event is not None:
            _worker_stop_event.set()
        thread = _worker_thread
        _worker_stop_event = None
        _worker_thread = None
    if thread and thread.is_alive():
        thread.join(timeout=2.0)
