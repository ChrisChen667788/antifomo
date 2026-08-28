from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.collector_ingest import EnsureDemoUserFn, _load_item_with_tags
from app.api.collector_ops_serializers import _to_daemon_command_response, _to_daemon_status_response
from app.api.collector_url_utils import clean_text as _clean_text
from app.core.config import get_settings
from app.db.session import get_db
from app.models.entities import Item
from app.schemas.collector import (
    CollectorBrowserExtensionVerifyResponse,
    CollectorDaemonCommandResponse,
    CollectorDaemonConfigResponse,
    CollectorDaemonConfigUpdateRequest,
    CollectorDaemonStatusResponse,
    CollectorDailySummaryResponse,
    CollectorFailedItemOut,
    CollectorFailedListResponse,
    CollectorIngestAttemptOut,
    CollectorProcessPendingResponse,
    CollectorRetryFailedResponse,
    CollectorStatusResponse,
    CollectorSummaryItemOut,
)
from app.services.collector_daemon import (
    CONFIG_FILE,
    read_collector_daemon_status,
    read_collector_daemon_config,
    run_collector_once,
    start_collector_daemon,
    stop_collector_daemon,
    update_collector_daemon_config,
    verify_browser_extension_pipeline,
)
from app.services.collector_diagnostics import list_item_attempts, serialize_ingest_attempt
from app.services.item_processing_runtime import process_item_by_id, recover_stale_items
from app.services.language import normalize_output_language
from app.services.user_context import ensure_demo_user


router = APIRouter(prefix="/api/collector", tags=["collector"])
settings = get_settings()

ProcessItemByIdFn = Callable[..., Any]
RecoverStaleItemsFn = Callable[..., dict[str, Any]]


def _to_failed_item_out(item: Item) -> CollectorFailedItemOut:
    return CollectorFailedItemOut(
        id=item.id,
        title=item.title,
        source_url=item.source_url,
        source_domain=item.source_domain,
        status=item.status,
        processing_error=item.processing_error,
        created_at=item.created_at,
        processed_at=item.processed_at,
    )


def _to_summary_item_out(item: Item) -> CollectorSummaryItemOut:
    return CollectorSummaryItemOut(
        id=item.id,
        title=item.title,
        source_url=item.source_url,
        source_domain=item.source_domain,
        score_value=float(item.score_value) if item.score_value is not None else None,
        action_suggestion=item.action_suggestion,
        short_summary=item.short_summary,
        tags=[tag.tag_name for tag in item.tags[:5]],
        created_at=item.created_at,
    )


def _truncate_text(value: str | None, limit: int = 140) -> str:
    text = _clean_text(value)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


def _build_daily_markdown(
    *,
    generated_at: datetime,
    range_hours: int,
    total_ingested: int,
    ready_count: int,
    processing_count: int,
    failed_count: int,
    deep_read_count: int,
    later_count: int,
    skip_count: int,
    top_items: list[CollectorSummaryItemOut],
    failed_items: list[CollectorFailedItemOut],
) -> str:
    lines = [
        "# Anti-fomo Collector Daily Summary",
        "",
        f"- generated_at: {generated_at.isoformat()}",
        f"- range_hours: {range_hours}",
        f"- total_ingested: {total_ingested}",
        f"- ready: {ready_count}",
        f"- processing: {processing_count}",
        f"- failed: {failed_count}",
        f"- deep_read: {deep_read_count}",
        f"- later: {later_count}",
        f"- skip: {skip_count}",
        "",
        "## Top Items",
    ]

    if not top_items:
        lines.append("- no high-priority items in this window.")
    else:
        for index, item in enumerate(top_items, start=1):
            score = f"{item.score_value:.2f}" if item.score_value is not None else "-"
            tags = ", ".join(item.tags) if item.tags else "-"
            lines.extend(
                [
                    f"{index}. **{item.title or 'Untitled'}**",
                    f"   - score/action: {score} / {item.action_suggestion or '-'}",
                    f"   - source: {item.source_domain or '-'}",
                    f"   - tags: {tags}",
                    f"   - summary: {_truncate_text(item.short_summary, 160) or '-'}",
                    f"   - url: {item.source_url or '-'}",
                ]
            )

    lines.extend(["", "## Failed Items"])
    if not failed_items:
        lines.append("- none")
    else:
        for index, item in enumerate(failed_items, start=1):
            lines.extend(
                [
                    f"{index}. **{item.title or 'Untitled'}**",
                    f"   - source: {item.source_domain or '-'}",
                    f"   - error: {_truncate_text(item.processing_error, 180) or '-'}",
                    f"   - url: {item.source_url or '-'}",
                ]
            )
    lines.append("")
    return "\n".join(lines)


def process_pending_items_impl(
    *,
    limit: int = 20,
    output_language: str | None = None,
    db: Session,
    ensure_demo_user_fn: EnsureDemoUserFn = ensure_demo_user,
    recover_stale_items_fn: RecoverStaleItemsFn = recover_stale_items,
) -> CollectorProcessPendingResponse:
    ensure_demo_user_fn(db)
    _ = output_language
    safe_limit = max(1, min(limit, 200))
    result = recover_stale_items_fn(
        limit=safe_limit,
        pending_grace_seconds=1,
        processing_stale_seconds=5,
        max_attempts=settings.pending_item_max_attempts,
        auto_archive=True,
    )
    remaining_pending = db.scalar(
        select(func.count(Item.id)).where(
            Item.user_id == settings.single_user_id,
            Item.status.in_(["pending", "processing"]),
        )
    ) or 0

    return CollectorProcessPendingResponse(
        scanned=int(result["scanned"]),
        processed=int(result["recovered"]),
        failed=int(result["failed"]),
        remaining_pending=int(remaining_pending),
        item_ids=list(result["item_ids"]),
    )


def list_failed_items_impl(
    *,
    limit: int = 20,
    db: Session,
    ensure_demo_user_fn: EnsureDemoUserFn = ensure_demo_user,
) -> CollectorFailedListResponse:
    ensure_demo_user_fn(db)
    safe_limit = max(1, min(limit, 200))

    total_failed = db.scalar(
        select(func.count(Item.id)).where(
            Item.user_id == settings.single_user_id,
            Item.status == "failed",
        )
    ) or 0

    failed_items = list(
        db.scalars(
            select(Item)
            .where(Item.user_id == settings.single_user_id)
            .where(Item.status == "failed")
            .order_by(desc(Item.created_at))
            .limit(safe_limit)
        )
    )
    return CollectorFailedListResponse(
        total_failed=int(total_failed),
        items=[_to_failed_item_out(item) for item in failed_items],
    )


def retry_failed_items_impl(
    *,
    limit: int = 20,
    output_language: str | None = None,
    db: Session,
    ensure_demo_user_fn: EnsureDemoUserFn = ensure_demo_user,
    process_item_by_id_fn: ProcessItemByIdFn = process_item_by_id,
) -> CollectorRetryFailedResponse:
    ensure_demo_user_fn(db)
    safe_limit = max(1, min(limit, 200))
    ready = 0
    failed = 0
    item_ids: list[UUID] = []
    failed_item_ids = list(
        db.scalars(
            select(Item.id)
            .where(Item.user_id == settings.single_user_id)
            .where(Item.status == "failed")
            .order_by(desc(Item.created_at))
            .limit(safe_limit)
        )
    )

    resolved_language = normalize_output_language(output_language) if output_language else None
    for item_id in failed_item_ids:
        result = process_item_by_id_fn(item_id, output_language=resolved_language, auto_archive=True)
        if result is None:
            continue
        item_ids.append(result.item_id)
        if result.status == "ready":
            ready += 1
        else:
            failed += 1
    return CollectorRetryFailedResponse(
        scanned=len(failed_item_ids),
        retried=len(failed_item_ids),
        ready=ready,
        failed=failed,
        item_ids=item_ids,
    )


def get_daily_summary_impl(
    *,
    hours: int = 24,
    limit: int = 12,
    db: Session,
    ensure_demo_user_fn: EnsureDemoUserFn = ensure_demo_user,
) -> CollectorDailySummaryResponse:
    ensure_demo_user_fn(db)
    safe_hours = max(1, min(hours, 168))
    safe_limit = max(1, min(limit, 50))
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=safe_hours)

    base_query = select(func.count(Item.id)).where(
        Item.user_id == settings.single_user_id,
        Item.created_at >= since,
    )
    total_ingested = int(db.scalar(base_query) or 0)
    ready_count = int(db.scalar(base_query.where(Item.status == "ready")) or 0)
    processing_count = int(db.scalar(base_query.where(Item.status.in_(["pending", "processing"]))) or 0)
    failed_count = int(db.scalar(base_query.where(Item.status == "failed")) or 0)

    ready_period_query = base_query.where(Item.status == "ready")
    deep_read_count = int(db.scalar(ready_period_query.where(Item.action_suggestion == "deep_read")) or 0)
    later_count = int(db.scalar(ready_period_query.where(Item.action_suggestion == "later")) or 0)
    skip_count = int(db.scalar(ready_period_query.where(Item.action_suggestion == "skip")) or 0)

    top_ready_items = list(
        db.scalars(
            select(Item)
            .where(Item.user_id == settings.single_user_id)
            .where(Item.created_at >= since)
            .where(Item.status == "ready")
            .where(Item.action_suggestion.in_(["deep_read", "later"]))
            .options(selectinload(Item.tags))
            .order_by(desc(Item.score_value), desc(Item.created_at))
            .limit(safe_limit)
        )
    )
    if not top_ready_items:
        top_ready_items = list(
            db.scalars(
                select(Item)
                .where(Item.user_id == settings.single_user_id)
                .where(Item.created_at >= since)
                .where(Item.status == "ready")
                .options(selectinload(Item.tags))
                .order_by(desc(Item.score_value), desc(Item.created_at))
                .limit(safe_limit)
            )
        )

    failed_items = list(
        db.scalars(
            select(Item)
            .where(Item.user_id == settings.single_user_id)
            .where(Item.created_at >= since)
            .where(Item.status == "failed")
            .order_by(desc(Item.created_at))
            .limit(min(safe_limit, 20))
        )
    )

    top_items_out = [_to_summary_item_out(item) for item in top_ready_items]
    failed_out = [_to_failed_item_out(item) for item in failed_items]
    markdown = _build_daily_markdown(
        generated_at=now,
        range_hours=safe_hours,
        total_ingested=total_ingested,
        ready_count=ready_count,
        processing_count=processing_count,
        failed_count=failed_count,
        deep_read_count=deep_read_count,
        later_count=later_count,
        skip_count=skip_count,
        top_items=top_items_out,
        failed_items=failed_out,
    )

    return CollectorDailySummaryResponse(
        generated_at=now,
        range_hours=safe_hours,
        total_ingested=total_ingested,
        ready_count=ready_count,
        processing_count=processing_count,
        failed_count=failed_count,
        deep_read_count=deep_read_count,
        later_count=later_count,
        skip_count=skip_count,
        top_items=top_items_out,
        failed_items=failed_out,
        markdown=markdown,
    )


def get_item_ingest_attempts_impl(
    item_id: UUID,
    *,
    db: Session,
    ensure_demo_user_fn: EnsureDemoUserFn = ensure_demo_user,
) -> list[CollectorIngestAttemptOut]:
    ensure_demo_user_fn(db)
    item = _load_item_with_tags(db, item_id)
    if not item or item.user_id != settings.single_user_id:
        raise HTTPException(status_code=404, detail="Item not found")
    return [CollectorIngestAttemptOut(**serialize_ingest_attempt(attempt)) for attempt in list_item_attempts(db, item_id)]


def get_collector_status_impl(
    *,
    db: Session,
    ensure_demo_user_fn: EnsureDemoUserFn = ensure_demo_user,
) -> CollectorStatusResponse:
    ensure_demo_user_fn(db)
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=24)

    base_query = select(func.count(Item.id)).where(
        Item.user_id == settings.single_user_id,
        Item.created_at >= since,
    )

    total = db.scalar(base_query) or 0
    ready = db.scalar(base_query.where(Item.status == "ready")) or 0
    processing = db.scalar(base_query.where(Item.status.in_(["pending", "processing"]))) or 0
    failed = db.scalar(base_query.where(Item.status == "failed")) or 0
    ocr_items = db.scalar(
        base_query.where(
            Item.raw_content.is_not(None),
            Item.raw_content.like("%正文：%"),
            Item.source_type.in_(["plugin", "text"]),
        )
    ) or 0
    latest_item_at = db.scalar(
        select(Item.created_at)
        .where(Item.user_id == settings.single_user_id)
        .order_by(desc(Item.created_at))
        .limit(1)
    )

    return CollectorStatusResponse(
        user_id=settings.single_user_id,
        now=now,
        last_24h_total=int(total),
        last_24h_ready=int(ready),
        last_24h_processing=int(processing),
        last_24h_failed=int(failed),
        last_24h_ocr_items=int(ocr_items),
        latest_item_at=latest_item_at,
    )


def get_collector_daemon_status_impl() -> CollectorDaemonStatusResponse:
    return _to_daemon_status_response(read_collector_daemon_status())


def get_collector_daemon_config_impl() -> CollectorDaemonConfigResponse:
    config = read_collector_daemon_config()
    return CollectorDaemonConfigResponse(
        wechat_clipboard_auto_import=bool(config.get("wechat_clipboard_auto_import", True)),
        wechat_export_directory_auto_import=bool(config.get("wechat_export_directory_auto_import", True)),
        wechat_export_directory_path=str(config.get("wechat_export_directory_path") or ""),
        config_file=str(CONFIG_FILE),
        updated_at=config.get("updated_at"),
    )


def update_collector_daemon_config_impl(
    payload: CollectorDaemonConfigUpdateRequest,
) -> CollectorDaemonConfigResponse:
    config = update_collector_daemon_config(
        wechat_clipboard_auto_import=payload.wechat_clipboard_auto_import,
        wechat_export_directory_auto_import=payload.wechat_export_directory_auto_import,
        wechat_export_directory_path=payload.wechat_export_directory_path,
    )
    return CollectorDaemonConfigResponse(
        wechat_clipboard_auto_import=bool(config.get("wechat_clipboard_auto_import", True)),
        wechat_export_directory_auto_import=bool(config.get("wechat_export_directory_auto_import", True)),
        wechat_export_directory_path=str(config.get("wechat_export_directory_path") or ""),
        config_file=str(CONFIG_FILE),
        updated_at=config.get("updated_at"),
    )


def verify_browser_extension_impl() -> CollectorBrowserExtensionVerifyResponse:
    record = verify_browser_extension_pipeline()
    return CollectorBrowserExtensionVerifyResponse(
        ok=bool(record.get("ok")),
        verified_at=record["verified_at"],
        message=str(record.get("message") or ""),
        output=str(record.get("output") or ""),
        report_file=str(record.get("report_file") or ""),
    )


def start_collector_daemon_impl(
    *,
    db: Session,
    ensure_demo_user_fn: EnsureDemoUserFn = ensure_demo_user,
) -> CollectorDaemonCommandResponse:
    ensure_demo_user_fn(db)
    try:
        result = start_collector_daemon()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _to_daemon_command_response(result)


def stop_collector_daemon_impl(
    *,
    db: Session,
    ensure_demo_user_fn: EnsureDemoUserFn = ensure_demo_user,
) -> CollectorDaemonCommandResponse:
    ensure_demo_user_fn(db)
    try:
        result = stop_collector_daemon()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _to_daemon_command_response(result)


def run_collector_daemon_once_impl(
    *,
    output_language: str = "zh-CN",
    max_collect_per_cycle: int = 30,
    db: Session,
    ensure_demo_user_fn: EnsureDemoUserFn = ensure_demo_user,
) -> CollectorDaemonCommandResponse:
    ensure_demo_user_fn(db)
    safe_limit = max(5, min(max_collect_per_cycle, 200))
    try:
        result = run_collector_once(
            output_language=normalize_output_language(output_language),
            max_collect_per_cycle=safe_limit,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _to_daemon_command_response(result)


@router.post("/process-pending", response_model=CollectorProcessPendingResponse)
def process_pending_items(
    limit: int = 20,
    output_language: str | None = None,
    db: Session = Depends(get_db),
) -> CollectorProcessPendingResponse:
    return process_pending_items_impl(limit=limit, output_language=output_language, db=db)


@router.get("/failed", response_model=CollectorFailedListResponse)
def list_failed_items(limit: int = 20, db: Session = Depends(get_db)) -> CollectorFailedListResponse:
    return list_failed_items_impl(limit=limit, db=db)


@router.post("/retry-failed", response_model=CollectorRetryFailedResponse)
def retry_failed_items(
    limit: int = 20,
    output_language: str | None = None,
    db: Session = Depends(get_db),
) -> CollectorRetryFailedResponse:
    return retry_failed_items_impl(limit=limit, output_language=output_language, db=db)


@router.get("/daily-summary", response_model=CollectorDailySummaryResponse)
def get_daily_summary(
    hours: int = 24,
    limit: int = 12,
    db: Session = Depends(get_db),
) -> CollectorDailySummaryResponse:
    return get_daily_summary_impl(hours=hours, limit=limit, db=db)


@router.get("/items/{item_id}/attempts", response_model=list[CollectorIngestAttemptOut])
def get_item_ingest_attempts(item_id: UUID, db: Session = Depends(get_db)) -> list[CollectorIngestAttemptOut]:
    return get_item_ingest_attempts_impl(item_id, db=db)


@router.get("/status", response_model=CollectorStatusResponse)
def get_collector_status(db: Session = Depends(get_db)) -> CollectorStatusResponse:
    return get_collector_status_impl(db=db)


@router.get("/daemon/status", response_model=CollectorDaemonStatusResponse)
def get_collector_daemon_status() -> CollectorDaemonStatusResponse:
    return get_collector_daemon_status_impl()


@router.get("/daemon/config", response_model=CollectorDaemonConfigResponse)
def get_collector_daemon_config() -> CollectorDaemonConfigResponse:
    return get_collector_daemon_config_impl()


@router.patch("/daemon/config", response_model=CollectorDaemonConfigResponse)
def update_collector_daemon_config_api(
    payload: CollectorDaemonConfigUpdateRequest,
) -> CollectorDaemonConfigResponse:
    return update_collector_daemon_config_impl(payload)


@router.post("/daemon/start", response_model=CollectorDaemonCommandResponse)
def start_collector_daemon_api(db: Session = Depends(get_db)) -> CollectorDaemonCommandResponse:
    return start_collector_daemon_impl(db=db)


@router.post("/daemon/stop", response_model=CollectorDaemonCommandResponse)
def stop_collector_daemon_api(db: Session = Depends(get_db)) -> CollectorDaemonCommandResponse:
    return stop_collector_daemon_impl(db=db)


@router.post("/daemon/run-once", response_model=CollectorDaemonCommandResponse)
def run_collector_daemon_once_api(
    output_language: str = "zh-CN",
    max_collect_per_cycle: int = 30,
    db: Session = Depends(get_db),
) -> CollectorDaemonCommandResponse:
    return run_collector_daemon_once_impl(
        output_language=output_language,
        max_collect_per_cycle=max_collect_per_cycle,
        db=db,
    )


@router.post("/browser-extension/verify", response_model=CollectorBrowserExtensionVerifyResponse)
def verify_browser_extension_api() -> CollectorBrowserExtensionVerifyResponse:
    return verify_browser_extension_impl()
