from __future__ import annotations

import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.collector_url_utils import (
    clean_text,
    is_valid_http_url,
    normalize_source_url,
)
from app.core.config import get_settings
from app.db.session import get_db
from app.models.collector_entities import CollectorFeedSource
from app.models.entities import CollectorSource
from app.schemas.collector import (
    CollectorFeedPullRequest,
    CollectorFeedPullResponse,
    CollectorFeedSourceCreateRequest,
    CollectorFeedSourceListResponse,
    CollectorFeedSourceOut,
    CollectorSourceCreateRequest,
    CollectorSourceImportRequest,
    CollectorSourceImportResponse,
    CollectorSourceImportResult,
    CollectorSourceListResponse,
    CollectorSourceOut,
    CollectorSourceUpdateRequest,
)
from app.services.collector_multiformat_service import (
    list_feed_sources,
    save_feed_source,
    serialize_feed_source,
    sync_rss_feeds,
)
from app.services.content_extractor import extract_domain
from app.services.user_context import ensure_demo_user


router = APIRouter(prefix="/api/collector", tags=["collector"])
settings = get_settings()


def _to_source_out(source: CollectorSource) -> CollectorSourceOut:
    return CollectorSourceOut(
        id=source.id,
        source_url=source.source_url,
        source_domain=source.source_domain,
        note=source.note,
        enabled=source.enabled,
        last_collected_at=source.last_collected_at,
        last_error=source.last_error,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def _get_source_or_404(db: Session, source_id: UUID) -> CollectorSource:
    source = db.scalar(
        select(CollectorSource)
        .where(CollectorSource.id == source_id)
        .where(CollectorSource.user_id == settings.single_user_id)
        .limit(1)
    )
    if not source:
        raise HTTPException(status_code=404, detail="collector source not found")
    return source


def _get_feed_or_404(db: Session, feed_id: UUID) -> CollectorFeedSource:
    feed = db.scalar(
        select(CollectorFeedSource)
        .where(CollectorFeedSource.id == feed_id)
        .where(CollectorFeedSource.user_id == settings.single_user_id)
        .limit(1)
    )
    if not feed:
        raise HTTPException(status_code=404, detail="collector feed source not found")
    return feed


def _flush_with_retry(
    db: Session,
    *,
    objects: list[object] | None = None,
    max_retries: int = 3,
    wait_sec: float = 0.35,
) -> None:
    attempt = 0
    while True:
        try:
            db.flush()
            return
        except OperationalError as exc:  # pragma: no cover - contention path
            db.rollback()
            error_text = str(exc).lower()
            if "database is locked" not in error_text and "database table is locked" not in error_text:
                raise
            attempt += 1
            if attempt > max_retries:
                raise
            if objects:
                for value in objects:
                    db.add(value)
            time.sleep(wait_sec * attempt)


@router.get("/sources", response_model=CollectorSourceListResponse)
def list_collector_sources(
    limit: int = 200,
    enabled_only: bool = False,
    db: Session = Depends(get_db),
) -> CollectorSourceListResponse:
    ensure_demo_user(db)
    safe_limit = max(1, min(limit, 500))
    base = select(CollectorSource).where(CollectorSource.user_id == settings.single_user_id)
    if enabled_only:
        base = base.where(CollectorSource.enabled.is_(True))

    total_query = select(func.count(CollectorSource.id)).where(
        CollectorSource.user_id == settings.single_user_id
    )
    if enabled_only:
        total_query = total_query.where(CollectorSource.enabled.is_(True))
    total = int(db.scalar(total_query) or 0)

    items = list(
        db.scalars(
            base.order_by(
                desc(CollectorSource.enabled),
                desc(CollectorSource.updated_at),
                desc(CollectorSource.created_at),
            ).limit(safe_limit)
        )
    )
    return CollectorSourceListResponse(
        total=total,
        items=[_to_source_out(source) for source in items],
    )


@router.post("/sources", response_model=CollectorSourceOut)
def create_collector_source(
    payload: CollectorSourceCreateRequest,
    db: Session = Depends(get_db),
) -> CollectorSourceOut:
    ensure_demo_user(db)
    source_url = normalize_source_url(payload.source_url)
    if not source_url or not is_valid_http_url(source_url):
        raise HTTPException(status_code=400, detail="source_url must start with http:// or https://")

    existing = db.scalar(
        select(CollectorSource)
        .where(CollectorSource.user_id == settings.single_user_id)
        .where(CollectorSource.source_url == source_url)
        .limit(1)
    )
    note_value = clean_text(payload.note) or None
    if existing:
        existing.enabled = payload.enabled
        if note_value is not None:
            existing.note = note_value
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return _to_source_out(existing)

    source = CollectorSource(
        user_id=settings.single_user_id,
        source_url=source_url,
        source_domain=extract_domain(source_url),
        note=note_value,
        enabled=payload.enabled,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return _to_source_out(source)


@router.post("/sources/import", response_model=CollectorSourceImportResponse)
def import_collector_sources(
    payload: CollectorSourceImportRequest,
    db: Session = Depends(get_db),
) -> CollectorSourceImportResponse:
    ensure_demo_user(db)

    normalized_urls: list[str] = []
    seen: set[str] = set()
    for raw in payload.urls:
        normalized = normalize_source_url(raw)
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        normalized_urls.append(normalized)

    existing_urls: set[str] = set()
    if normalized_urls:
        existing_urls = {
            value
            for value in db.scalars(
                select(CollectorSource.source_url).where(
                    CollectorSource.user_id == settings.single_user_id,
                    CollectorSource.source_url.in_(normalized_urls),
                )
            )
            if value
        }

    created = 0
    exists = 0
    invalid = 0
    results: list[CollectorSourceImportResult] = []

    for raw in payload.urls:
        normalized = normalize_source_url(raw)
        if not normalized:
            invalid += 1
            results.append(
                CollectorSourceImportResult(
                    source_url=raw,
                    status="invalid",
                    detail="URL must start with http:// or https://",
                )
            )
            continue

        if normalized in existing_urls:
            exists += 1
            source = db.scalar(
                select(CollectorSource)
                .where(CollectorSource.user_id == settings.single_user_id)
                .where(CollectorSource.source_url == normalized)
                .limit(1)
            )
            if source and payload.enabled:
                source.enabled = True
                db.add(source)
            results.append(
                CollectorSourceImportResult(
                    source_url=normalized,
                    status="exists",
                    source_id=source.id if source else None,
                )
            )
            continue

        source = CollectorSource(
            user_id=settings.single_user_id,
            source_url=normalized,
            source_domain=extract_domain(normalized),
            enabled=payload.enabled,
        )
        db.add(source)
        _flush_with_retry(db, objects=[source])
        existing_urls.add(normalized)
        created += 1
        results.append(
            CollectorSourceImportResult(
                source_url=normalized,
                status="created",
                source_id=source.id,
            )
        )

    db.commit()
    return CollectorSourceImportResponse(
        total=len(payload.urls),
        created=created,
        exists=exists,
        invalid=invalid,
        results=results,
    )


@router.patch("/sources/{source_id}", response_model=CollectorSourceOut)
def update_collector_source(
    source_id: UUID,
    payload: CollectorSourceUpdateRequest,
    db: Session = Depends(get_db),
) -> CollectorSourceOut:
    ensure_demo_user(db)
    source = _get_source_or_404(db, source_id)
    if payload.enabled is not None:
        source.enabled = payload.enabled
    if payload.note is not None:
        source.note = clean_text(payload.note) or None
    db.add(source)
    db.commit()
    db.refresh(source)
    return _to_source_out(source)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collector_source(
    source_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    ensure_demo_user(db)
    source = _get_source_or_404(db, source_id)
    db.delete(source)
    db.commit()


@router.get("/feeds", response_model=CollectorFeedSourceListResponse)
def get_collector_feed_sources(
    feed_type: str | None = "rss",
    db: Session = Depends(get_db),
) -> CollectorFeedSourceListResponse:
    ensure_demo_user(db)
    items = list_feed_sources(db, user_id=settings.single_user_id, feed_type=feed_type)
    return CollectorFeedSourceListResponse(
        total=len(items),
        items=[CollectorFeedSourceOut.model_validate(item) for item in items],
    )


@router.post("/rss/sources", response_model=CollectorFeedSourceOut, status_code=status.HTTP_201_CREATED)
def create_rss_feed_source(
    payload: CollectorFeedSourceCreateRequest,
    db: Session = Depends(get_db),
) -> CollectorFeedSourceOut:
    ensure_demo_user(db)
    try:
        feed = save_feed_source(
            db,
            user_id=settings.single_user_id,
            feed_type="rss",
            source_url=payload.source_url,
            title=payload.title,
            note=payload.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload.pull_immediately:
        sync_rss_feeds(
            db,
            user_id=settings.single_user_id,
            feed_id=feed.id,
            limit=payload.limit,
            output_language=payload.output_language,
        )
        feed = _get_feed_or_404(db, feed.id)

    return CollectorFeedSourceOut.model_validate(serialize_feed_source(feed))


@router.post("/rss/pull", response_model=CollectorFeedPullResponse)
def pull_rss_feed_sources(
    payload: CollectorFeedPullRequest,
    db: Session = Depends(get_db),
) -> CollectorFeedPullResponse:
    ensure_demo_user(db)
    results = sync_rss_feeds(
        db,
        user_id=settings.single_user_id,
        feed_id=payload.feed_id,
        limit=payload.limit,
        output_language=payload.output_language,
    )
    return CollectorFeedPullResponse(total=len(results), results=results)
