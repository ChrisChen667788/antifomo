from __future__ import annotations

import json
from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.collector_ingest import EnsureDemoUserFn, ProcessItemTaskFn, _process_item_task
from app.core.config import get_settings
from app.db.session import get_db
from app.models.collector_entities import CollectorImportBatch
from app.models.entities import Feedback, Item
from app.schemas.collector import (
    CollectorWechatFavoriteImportBatchListResponse,
    CollectorWechatFavoriteImportBatchResponse,
    CollectorWechatFavoriteImportRequest,
    CollectorWechatFavoriteImportResponse,
    CollectorWechatFavoritePreviewRequest,
    CollectorWechatFavoritePreviewResponse,
)
from app.services.collector_imports.wechat_favorites import parse_wechat_favorites_export
from app.services.collector_multiformat_service import import_wechat_favorites as import_wechat_favorites_payload
from app.services.language import normalize_output_language
from app.services.user_context import ensure_demo_user


router = APIRouter(prefix="/api/collector", tags=["collector"])
settings = get_settings()


def _json_list(value: object) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _json_dict(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _uuid_list(value: object) -> list[UUID]:
    item_ids: list[UUID] = []
    seen: set[UUID] = set()
    for raw in _json_list(value):
        try:
            item_id = UUID(str(raw))
        except (TypeError, ValueError):
            continue
        if item_id in seen:
            continue
        seen.add(item_id)
        item_ids.append(item_id)
    return item_ids


def to_wechat_favorite_batch_response(
    db: Session,
    batch: CollectorImportBatch,
) -> CollectorWechatFavoriteImportBatchResponse:
    item_ids = _uuid_list(batch.item_ids)
    created_item_ids = _uuid_list(batch.created_item_ids)
    results = _json_list(batch.result_payload)[:100]
    source_summary = _json_dict(batch.source_payload)
    items_by_id = {
        item.id: item
        for item in db.scalars(
            select(Item)
            .where(Item.user_id == batch.user_id)
            .where(Item.id.in_(item_ids))
        )
    } if item_ids else {}
    triaged_item_ids = {
        item_id
        for item_id in db.scalars(
            select(Feedback.item_id)
            .where(Feedback.user_id == batch.user_id)
            .where(Feedback.item_id.in_(item_ids))
            .where(Feedback.feedback_type.in_(["ignore", "save"]))
        )
    } if item_ids else set()
    review_item_ids = [item_id for item_id in item_ids if item_id not in triaged_item_ids]
    ready_item_ids = [
        item_id
        for item_id in review_item_ids
        if items_by_id.get(item_id) is not None and items_by_id[item_id].status == "ready"
    ]
    failed_item_ids = [
        item_id
        for item_id in review_item_ids
        if items_by_id.get(item_id) is not None and items_by_id[item_id].status == "failed"
    ]
    processing_count = sum(
        1
        for item_id in review_item_ids
        if items_by_id.get(item_id) is not None and items_by_id[item_id].status in {"pending", "processing"}
    )
    if not item_ids and batch.total_candidates == 0:
        status_label = "empty"
    elif not review_item_ids:
        status_label = "reviewed"
    elif processing_count:
        status_label = "processing"
    elif failed_item_ids and len(failed_item_ids) == len(review_item_ids):
        status_label = "failed"
    else:
        status_label = "ready"
    return CollectorWechatFavoriteImportBatchResponse(
        id=batch.id,
        import_type="wechat_favorites",
        source_label=batch.source_label,
        status=status_label,
        output_language=normalize_output_language(batch.output_language),
        processing_deferred=batch.processing_deferred,
        total_candidates=batch.total_candidates,
        created=batch.created_count,
        deduplicated=batch.deduplicated_count,
        invalid=batch.invalid_count,
        skipped=batch.skipped_count,
        item_ids=item_ids,
        created_item_ids=created_item_ids,
        review_item_ids=review_item_ids,
        ready=len(ready_item_ids),
        processing=processing_count,
        failed=len(failed_item_ids),
        triaged=len(triaged_item_ids),
        failed_item_ids=failed_item_ids,
        results=results,
        source_summary=source_summary,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


def preview_wechat_favorite_items_impl(
    payload: CollectorWechatFavoritePreviewRequest,
    db: Session,
    *,
    ensure_demo_user_fn: EnsureDemoUserFn = ensure_demo_user,
) -> CollectorWechatFavoritePreviewResponse:
    ensure_demo_user_fn(db)
    candidates = parse_wechat_favorites_export(
        payload.export_text,
        urls=payload.urls,
        include_text_blocks=payload.include_text_blocks,
        limit=payload.limit,
    )
    url_candidates = sum(1 for candidate in candidates if candidate.extraction_mode == "wechat_favorites_url")
    text_candidates = sum(1 for candidate in candidates if candidate.extraction_mode == "wechat_favorites_text")
    return CollectorWechatFavoritePreviewResponse(
        total_candidates=len(candidates),
        url_candidates=url_candidates,
        text_candidates=text_candidates,
        samples=[
            {
                "source_url": candidate.source_url,
                "title": candidate.title,
                "body_source": candidate.extraction_mode,
            }
            for candidate in candidates[:8]
        ],
    )


def list_wechat_favorite_import_batches_impl(
    *,
    limit: int = 5,
    include_reviewed: bool = False,
    db: Session,
    ensure_demo_user_fn: EnsureDemoUserFn = ensure_demo_user,
) -> CollectorWechatFavoriteImportBatchListResponse:
    ensure_demo_user_fn(db)
    safe_limit = max(1, min(limit, 50))
    scan_limit = 100 if not include_reviewed else safe_limit
    batches = list(
        db.scalars(
            select(CollectorImportBatch)
            .where(CollectorImportBatch.user_id == settings.single_user_id)
            .where(CollectorImportBatch.import_type == "wechat_favorites")
            .order_by(desc(CollectorImportBatch.created_at))
            .limit(scan_limit)
        )
    )
    responses: list[CollectorWechatFavoriteImportBatchResponse] = []
    for batch in batches:
        response = to_wechat_favorite_batch_response(db, batch)
        if not include_reviewed and response.status in {"reviewed", "empty"}:
            continue
        responses.append(response)
        if len(responses) >= safe_limit:
            break
    return CollectorWechatFavoriteImportBatchListResponse(total=len(responses), items=responses)


def get_wechat_favorite_import_batch_impl(
    batch_id: UUID,
    *,
    db: Session,
    ensure_demo_user_fn: EnsureDemoUserFn = ensure_demo_user,
) -> CollectorWechatFavoriteImportBatchResponse:
    ensure_demo_user_fn(db)
    batch = db.scalar(
        select(CollectorImportBatch)
        .where(CollectorImportBatch.user_id == settings.single_user_id)
        .where(CollectorImportBatch.import_type == "wechat_favorites")
        .where(CollectorImportBatch.id == batch_id)
    )
    if batch is None:
        raise HTTPException(status_code=404, detail="WeChat Favorites import batch not found")
    return to_wechat_favorite_batch_response(db, batch)


def import_wechat_favorite_items_impl(
    payload: CollectorWechatFavoriteImportRequest,
    background_tasks: BackgroundTasks,
    db: Session,
    *,
    ensure_demo_user_fn: EnsureDemoUserFn = ensure_demo_user,
    process_item_task_fn: ProcessItemTaskFn = _process_item_task,
) -> CollectorWechatFavoriteImportResponse:
    ensure_demo_user_fn(db)
    result = import_wechat_favorites_payload(
        db,
        user_id=settings.single_user_id,
        export_text=payload.export_text,
        urls=payload.urls,
        output_language=payload.output_language,
        limit=payload.limit,
        include_text_blocks=payload.include_text_blocks,
        process_immediately=payload.process_immediately,
    )
    # Item persistence can commit before the batch is created. Commit the batch
    # explicitly so the frontend never receives an ID that disappears on poll.
    db.commit()
    if result.get("batch") is not None:
        db.refresh(result["batch"])
    if not payload.process_immediately:
        for item_id in result["created_item_ids"]:
            background_tasks.add_task(process_item_task_fn, UUID(str(item_id)), payload.output_language)
    batch_response = (
        to_wechat_favorite_batch_response(db, result["batch"])
        if result.get("batch") is not None
        else None
    )
    return CollectorWechatFavoriteImportResponse(
        batch_id=UUID(str(result["batch_id"])) if result.get("batch_id") else None,
        batch=batch_response,
        total_candidates=result["total_candidates"],
        created=result["created"],
        deduplicated=result["deduplicated"],
        invalid=result["invalid"],
        skipped=result["skipped"],
        processing_deferred=not payload.process_immediately,
        created_item_ids=result["created_item_ids"],
        results=result["results"],
    )


@router.post("/wechat-favorites/preview", response_model=CollectorWechatFavoritePreviewResponse)
def preview_wechat_favorite_items(
    payload: CollectorWechatFavoritePreviewRequest,
    db: Session = Depends(get_db),
) -> CollectorWechatFavoritePreviewResponse:
    return preview_wechat_favorite_items_impl(payload, db, ensure_demo_user_fn=ensure_demo_user)


@router.get("/wechat-favorites/batches", response_model=CollectorWechatFavoriteImportBatchListResponse)
def list_wechat_favorite_import_batches(
    limit: int = 5,
    include_reviewed: bool = False,
    db: Session = Depends(get_db),
) -> CollectorWechatFavoriteImportBatchListResponse:
    return list_wechat_favorite_import_batches_impl(
        limit=limit,
        include_reviewed=include_reviewed,
        db=db,
        ensure_demo_user_fn=ensure_demo_user,
    )


@router.get("/wechat-favorites/batches/{batch_id}", response_model=CollectorWechatFavoriteImportBatchResponse)
def get_wechat_favorite_import_batch(
    batch_id: UUID,
    db: Session = Depends(get_db),
) -> CollectorWechatFavoriteImportBatchResponse:
    return get_wechat_favorite_import_batch_impl(batch_id, db=db, ensure_demo_user_fn=ensure_demo_user)


@router.post(
    "/wechat-favorites/import",
    response_model=CollectorWechatFavoriteImportResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_wechat_favorite_items(
    payload: CollectorWechatFavoriteImportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> CollectorWechatFavoriteImportResponse:
    return import_wechat_favorite_items_impl(
        payload,
        background_tasks,
        db,
        ensure_demo_user_fn=ensure_demo_user,
        process_item_task_fn=_process_item_task,
    )
