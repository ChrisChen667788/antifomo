from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.api.collector_url_utils import (
    clean_text as _clean_text,
    is_valid_http_url as _is_valid_http_url,
    normalize_source_url as _normalize_source_url,
)
from app.core.config import get_settings
from app.db.session import SessionLocal, get_db
from app.models.entities import CollectorSource, Item
from app.schemas.collector import (
    CollectorBrowserBatchIngestItemResponse,
    CollectorBrowserBatchIngestRequest,
    CollectorBrowserBatchIngestResponse,
    CollectorExternalIngestResponse,
    CollectorPluginIngestRequest,
    CollectorPluginIngestResponse,
    CollectorURLIngestRequest,
    CollectorURLIngestResponse,
)
from app.schemas.items import ItemOut
from app.services.browser_content_extractor import extract_from_browser
from app.services.content_extractor import ContentExtractionError, extract_domain
from app.services.collector_diagnostics import (
    create_ingest_attempt,
    infer_item_acquisition,
    update_item_ingest_state,
)
from app.services.item_processing_runtime import process_item_by_id, process_item_in_session
from app.services.language import normalize_output_language
from app.services.user_context import ensure_demo_user


router = APIRouter(prefix="/api/collector", tags=["collector"])
settings = get_settings()

EnsureDemoUserFn = Callable[[Session], Any]
MarkSourceCollectedFn = Callable[[Session, str | None, str | None], None]
ProcessItemInSessionFn = Callable[..., Item]
ProcessItemTaskFn = Callable[[UUID, str | None], None]
ExtractFromBrowserFn = Callable[[str], Any]


def _load_existing_item_by_url(db: Session, source_url: str | None) -> Item | None:
    if not source_url:
        return None
    return db.scalar(
        select(Item)
        .where(Item.user_id == settings.single_user_id)
        .where(Item.source_url == source_url)
        .options(selectinload(Item.tags))
        .order_by(desc(Item.created_at))
        .limit(1)
    )


def _load_item_with_tags(db: Session, item_id: UUID) -> Item | None:
    return db.scalar(select(Item).where(Item.id == item_id).options(selectinload(Item.tags)))


def _persist_new_item(db: Session, item: Item) -> None:
    db.add(item)
    db.flush()


def _mark_source_collected(db: Session, source_url: str | None, error: str | None = None) -> None:
    normalized = _normalize_source_url(source_url)
    if not normalized:
        return
    source = db.scalar(
        select(CollectorSource)
        .where(CollectorSource.user_id == settings.single_user_id)
        .where(CollectorSource.source_url == normalized)
        .limit(1)
    )
    if not source:
        return
    source.last_collected_at = datetime.now(timezone.utc)
    source.last_error = _clean_text(error) or None
    db.add(source)


def _process_item_task(item_id: UUID, output_language: str | None = None) -> None:
    result = process_item_by_id(item_id, output_language=output_language, auto_archive=True)
    if result is None:
        return
    db = SessionLocal()
    try:
        item = _load_item_with_tags(db, result.item_id)
        if item is not None:
            update_item_ingest_state(item)
            db.add(item)
        _mark_source_collected(db, result.source_url, error=result.processing_error)
        db.commit()
    finally:
        db.close()


def ingest_plugin_item_impl(
    payload: CollectorPluginIngestRequest,
    background_tasks: BackgroundTasks,
    db: Session,
    *,
    ensure_demo_user_fn: EnsureDemoUserFn = ensure_demo_user,
    mark_source_collected_fn: MarkSourceCollectedFn = _mark_source_collected,
    process_item_in_session_fn: ProcessItemInSessionFn = process_item_in_session,
    process_item_task_fn: ProcessItemTaskFn = _process_item_task,
) -> CollectorPluginIngestResponse:
    ensure_demo_user_fn(db)
    resolved_language = normalize_output_language(payload.output_language)
    source_url = payload.source_url.strip()

    if not _is_valid_http_url(source_url):
        raise HTTPException(status_code=400, detail="source_url must start with http:// or https://")

    if payload.deduplicate:
        existing = _load_existing_item_by_url(db, source_url)
        if existing:
            update_item_ingest_state(existing, ingest_route=existing.ingest_route or "plugin", resolved_from_url=source_url)
            attempt = create_ingest_attempt(
                db,
                item=existing,
                source_url=source_url,
                route_type=existing.ingest_route or "plugin",
                resolver="existing_item",
                attempt_status="deduplicated",
                body_source=infer_item_acquisition(existing)[2],
            )
            db.add(existing)
            db.commit()
            return CollectorPluginIngestResponse(
                item=ItemOut.model_validate(existing),
                deduplicated=True,
                processing_deferred=False,
                attempt_id=attempt.id,
                ingest_route=existing.ingest_route or "plugin",
                content_acquisition_status=existing.content_acquisition_status,
                resolver="existing_item",
                body_source=attempt.body_source,
                fallback_used=existing.fallback_used,
            )

    item = Item(
        user_id=settings.single_user_id,
        source_type="plugin",
        source_url=source_url,
        source_domain=extract_domain(source_url),
        title=_clean_text(payload.title) or None,
        raw_content=_clean_text(payload.raw_content),
        output_language=resolved_language,
        ingest_route="plugin",
        content_acquisition_status="body_acquired",
        content_acquisition_note="浏览器插件已提交正文",
        resolved_from_url=source_url,
        fallback_used=False,
        status="pending",
    )
    attempt_status = "queued"
    if payload.process_immediately:
        _persist_new_item(db, item)
        process_item_in_session_fn(db, item, output_language=resolved_language, auto_archive=True)
        update_item_ingest_state(item, ingest_route="plugin", resolved_from_url=source_url, fallback_used=False)
        attempt_status = "ready" if item.status == "ready" else "failed"
        attempt = create_ingest_attempt(
            db,
            item=item,
            source_url=source_url,
            route_type="plugin",
            resolver="browser_plugin",
            attempt_status=attempt_status,
            body_source="plugin_body",
            error_detail=item.processing_error,
        )
        mark_source_collected_fn(db, source_url, item.processing_error)
        db.commit()
    else:
        _persist_new_item(db, item)
        attempt = create_ingest_attempt(
            db,
            item=item,
            source_url=source_url,
            route_type="plugin",
            resolver="browser_plugin",
            attempt_status=attempt_status,
            body_source="plugin_body",
        )
        mark_source_collected_fn(db, source_url, None)
        db.commit()
        background_tasks.add_task(process_item_task_fn, item.id, resolved_language)

    hydrated_item = _load_item_with_tags(db, item.id)
    if not hydrated_item:
        raise HTTPException(status_code=500, detail="failed to load item after processing")

    return CollectorPluginIngestResponse(
        item=ItemOut.model_validate(hydrated_item),
        deduplicated=False,
        processing_deferred=not payload.process_immediately,
        attempt_id=attempt.id,
        ingest_route="plugin",
        content_acquisition_status=hydrated_item.content_acquisition_status,
        resolver="browser_plugin",
        body_source="plugin_body",
        fallback_used=hydrated_item.fallback_used,
    )


def ingest_url_item_impl(
    payload: CollectorURLIngestRequest,
    background_tasks: BackgroundTasks,
    db: Session,
    *,
    ensure_demo_user_fn: EnsureDemoUserFn = ensure_demo_user,
    mark_source_collected_fn: MarkSourceCollectedFn = _mark_source_collected,
    process_item_in_session_fn: ProcessItemInSessionFn = process_item_in_session,
    process_item_task_fn: ProcessItemTaskFn = _process_item_task,
) -> CollectorURLIngestResponse:
    ensure_demo_user_fn(db)
    resolved_language = normalize_output_language(payload.output_language)
    source_url = _normalize_source_url(payload.source_url)
    if not source_url or not _is_valid_http_url(source_url):
        raise HTTPException(status_code=400, detail="source_url must start with http:// or https://")

    if payload.deduplicate:
        existing = _load_existing_item_by_url(db, source_url)
        if existing:
            update_item_ingest_state(existing, ingest_route=existing.ingest_route or "direct_url", resolved_from_url=source_url)
            attempt = create_ingest_attempt(
                db,
                item=existing,
                source_url=source_url,
                route_type=existing.ingest_route or "direct_url",
                resolver="existing_item",
                attempt_status="deduplicated",
                body_source=infer_item_acquisition(existing)[2],
            )
            db.add(existing)
            db.commit()
            return CollectorURLIngestResponse(
                item=ItemOut.model_validate(existing),
                deduplicated=True,
                ingest_mode="url",
                processing_deferred=False,
                attempt_id=attempt.id,
                ingest_route=existing.ingest_route or "direct_url",
                content_acquisition_status=existing.content_acquisition_status,
                resolver="existing_item",
                body_source=attempt.body_source,
                fallback_used=existing.fallback_used,
            )

    item = Item(
        user_id=settings.single_user_id,
        source_type="url",
        source_url=source_url,
        source_domain=extract_domain(source_url),
        title=_clean_text(payload.title) or None,
        raw_content=None,
        output_language=resolved_language,
        ingest_route="direct_url",
        content_acquisition_status="pending_processing",
        content_acquisition_note="待抓取正文",
        resolved_from_url=source_url,
        fallback_used=False,
        status="pending",
    )
    attempt_status = "queued"
    body_source = "pending"
    if payload.process_immediately:
        _persist_new_item(db, item)
        process_item_in_session_fn(db, item, output_language=resolved_language, auto_archive=True)
        update_item_ingest_state(item, ingest_route="direct_url", resolved_from_url=source_url, fallback_used=False)
        _, _, body_source = infer_item_acquisition(item)
        attempt_status = "ready" if item.status == "ready" else "failed"
        attempt = create_ingest_attempt(
            db,
            item=item,
            source_url=source_url,
            route_type="direct_url",
            resolver="page_fetch",
            attempt_status=attempt_status,
            body_source=body_source,
            error_detail=item.processing_error,
        )
        mark_source_collected_fn(db, source_url, item.processing_error)
        db.commit()
    else:
        _persist_new_item(db, item)
        attempt = create_ingest_attempt(
            db,
            item=item,
            source_url=source_url,
            route_type="direct_url",
            resolver="page_fetch",
            attempt_status=attempt_status,
            body_source=body_source,
        )
        mark_source_collected_fn(db, source_url, None)
        db.commit()
        background_tasks.add_task(process_item_task_fn, item.id, resolved_language)

    hydrated_item = _load_item_with_tags(db, item.id)
    if not hydrated_item:
        raise HTTPException(status_code=500, detail="failed to load item after processing")

    return CollectorURLIngestResponse(
        item=ItemOut.model_validate(hydrated_item),
        deduplicated=False,
        ingest_mode="url",
        processing_deferred=not payload.process_immediately,
        attempt_id=attempt.id,
        ingest_route="direct_url",
        content_acquisition_status=hydrated_item.content_acquisition_status,
        resolver="page_fetch",
        body_source=body_source,
        fallback_used=hydrated_item.fallback_used,
    )


def ingest_browser_item_impl(
    payload: CollectorURLIngestRequest,
    background_tasks: BackgroundTasks,
    db: Session,
    *,
    ensure_demo_user_fn: EnsureDemoUserFn = ensure_demo_user,
    mark_source_collected_fn: MarkSourceCollectedFn = _mark_source_collected,
    process_item_in_session_fn: ProcessItemInSessionFn = process_item_in_session,
    process_item_task_fn: ProcessItemTaskFn = _process_item_task,
    extract_from_browser_fn: ExtractFromBrowserFn = extract_from_browser,
) -> CollectorExternalIngestResponse:
    ensure_demo_user_fn(db)
    source_url = _normalize_source_url(payload.source_url)
    if not source_url or not _is_valid_http_url(source_url):
        raise HTTPException(status_code=400, detail="source_url must start with http:// or https://")

    browser_error: str | None = None
    try:
        extracted = extract_from_browser_fn(source_url)
    except ContentExtractionError as exc:
        browser_error = _clean_text(str(exc)) or "browser extraction failed"
    else:
        plugin_response = ingest_plugin_item_impl(
            CollectorPluginIngestRequest(
                source_url=extracted.source_url or source_url,
                title=extracted.title or payload.title,
                raw_content=extracted.raw_content or extracted.clean_content,
                output_language=payload.output_language,
                deduplicate=payload.deduplicate,
                process_immediately=payload.process_immediately,
            ),
            background_tasks,
            db,
            ensure_demo_user_fn=ensure_demo_user_fn,
            mark_source_collected_fn=mark_source_collected_fn,
            process_item_in_session_fn=process_item_in_session_fn,
            process_item_task_fn=process_item_task_fn,
        )
        return CollectorExternalIngestResponse(
            item=plugin_response.item,
            deduplicated=plugin_response.deduplicated,
            processing_deferred=plugin_response.processing_deferred,
            attempt_id=plugin_response.attempt_id,
            ingest_route="browser_plugin",
            content_acquisition_status=plugin_response.content_acquisition_status,
            resolver="browser_extract",
            body_source=plugin_response.body_source,
            fallback_used=plugin_response.fallback_used,
            metadata={
                "browser_extract": {
                    "status": "success",
                    "input_url": source_url,
                    "final_url": extracted.source_url,
                    "body_length": len(extracted.clean_content or extracted.raw_content or ""),
                }
            },
        )

    url_response = ingest_url_item_impl(
        CollectorURLIngestRequest(
            source_url=source_url,
            title=payload.title,
            output_language=payload.output_language,
            deduplicate=payload.deduplicate,
            process_immediately=payload.process_immediately,
        ),
        background_tasks,
        db,
        ensure_demo_user_fn=ensure_demo_user_fn,
        mark_source_collected_fn=mark_source_collected_fn,
        process_item_in_session_fn=process_item_in_session_fn,
        process_item_task_fn=process_item_task_fn,
    )
    return CollectorExternalIngestResponse(
        item=url_response.item,
        deduplicated=url_response.deduplicated,
        processing_deferred=url_response.processing_deferred,
        attempt_id=url_response.attempt_id,
        ingest_route="browser_url_fallback",
        content_acquisition_status=url_response.content_acquisition_status,
        resolver="browser_extract_fallback",
        body_source=url_response.body_source,
        fallback_used=url_response.fallback_used,
        metadata={
            "browser_extract": {
                "status": "fallback",
                "input_url": source_url,
                "error": browser_error,
            }
        },
    )


def ingest_browser_items_batch_impl(
    payload: CollectorBrowserBatchIngestRequest,
    background_tasks: BackgroundTasks,
    db: Session,
    *,
    ensure_demo_user_fn: EnsureDemoUserFn = ensure_demo_user,
    mark_source_collected_fn: MarkSourceCollectedFn = _mark_source_collected,
    process_item_in_session_fn: ProcessItemInSessionFn = process_item_in_session,
    process_item_task_fn: ProcessItemTaskFn = _process_item_task,
    extract_from_browser_fn: ExtractFromBrowserFn = extract_from_browser,
) -> CollectorBrowserBatchIngestResponse:
    ensure_demo_user_fn(db)

    normalized_urls: list[str] = []
    seen: set[str] = set()
    for raw_url in payload.source_urls:
        normalized = _normalize_source_url(raw_url)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        normalized_urls.append(normalized)

    created = 0
    deduplicated = 0
    failed = 0
    results: list[CollectorBrowserBatchIngestItemResponse] = []

    for source_url in normalized_urls:
        try:
            response = ingest_browser_item_impl(
                CollectorURLIngestRequest(
                    source_url=source_url,
                    output_language=payload.output_language,
                    deduplicate=payload.deduplicate,
                    process_immediately=payload.process_immediately,
                ),
                background_tasks,
                db,
                ensure_demo_user_fn=ensure_demo_user_fn,
                mark_source_collected_fn=mark_source_collected_fn,
                process_item_in_session_fn=process_item_in_session_fn,
                process_item_task_fn=process_item_task_fn,
                extract_from_browser_fn=extract_from_browser_fn,
            )
            is_deduplicated = bool(response.deduplicated)
            if is_deduplicated:
                deduplicated += 1
            else:
                created += 1
            results.append(
                CollectorBrowserBatchIngestItemResponse(
                    source_url=source_url,
                    item_id=response.item.id,
                    status="deduplicated" if is_deduplicated else "created",
                    ingest_route=response.ingest_route,
                    resolver=response.resolver,
                    body_source=response.body_source,
                    deduplicated=is_deduplicated,
                    fallback_used=response.fallback_used,
                )
            )
        except HTTPException as exc:
            failed += 1
            results.append(
                CollectorBrowserBatchIngestItemResponse(
                    source_url=source_url,
                    status="failed",
                    error=_clean_text(str(exc.detail)) or "browser batch ingest failed",
                )
            )
        except Exception as exc:  # noqa: BLE001
            failed += 1
            results.append(
                CollectorBrowserBatchIngestItemResponse(
                    source_url=source_url,
                    status="failed",
                    error=_clean_text(str(exc)) or "browser batch ingest failed",
                )
            )

    return CollectorBrowserBatchIngestResponse(
        total=len(normalized_urls),
        created=created,
        deduplicated=deduplicated,
        failed=failed,
        results=results,
    )


@router.post("/browser/ingest", response_model=CollectorExternalIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_browser_item(
    payload: CollectorURLIngestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> CollectorExternalIngestResponse:
    return ingest_browser_item_impl(payload, background_tasks, db)


@router.post("/browser/batch-ingest", response_model=CollectorBrowserBatchIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_browser_items_batch(
    payload: CollectorBrowserBatchIngestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> CollectorBrowserBatchIngestResponse:
    return ingest_browser_items_batch_impl(payload, background_tasks, db)


@router.post("/plugin/ingest", response_model=CollectorPluginIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_plugin_item(
    payload: CollectorPluginIngestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> CollectorPluginIngestResponse:
    return ingest_plugin_item_impl(payload, background_tasks, db)


@router.post("/url/ingest", response_model=CollectorURLIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_url_item(
    payload: CollectorURLIngestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> CollectorURLIngestResponse:
    return ingest_url_item_impl(payload, background_tasks, db)
