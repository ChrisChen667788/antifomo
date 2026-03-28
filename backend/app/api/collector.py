from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import time
import re
from urllib.parse import urlparse, urlunparse
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db.session import SessionLocal, get_db
from app.models.collector_entities import CollectorFeedSource
from app.models.entities import CollectorSource, Item
from app.schemas.collector import (
    CollectorDaemonCommandResponse,
    CollectorDaemonStatusResponse,
    CollectorDailySummaryResponse,
    CollectorFailedItemOut,
    CollectorFailedListResponse,
    CollectorFeedPullRequest,
    CollectorFeedPullResponse,
    CollectorFeedSourceCreateRequest,
    CollectorFeedSourceListResponse,
    CollectorFeedSourceOut,
    CollectorIngestAttemptOut,
    CollectorExternalIngestResponse,
    CollectorFileUploadRequest,
    CollectorNewsletterIngestRequest,
    CollectorOCRPreviewRequest,
    CollectorOCRPreviewResponse,
    CollectorOCRIngestRequest,
    CollectorOCRIngestResponse,
    ItemDiagnosticsOut,
    CollectorPluginIngestRequest,
    CollectorPluginIngestResponse,
    CollectorProcessPendingResponse,
    CollectorRetryFailedResponse,
    CollectorURLResolveCandidateResponse,
    CollectorURLResolveRequest,
    CollectorURLResolveResponse,
    CollectorURLIngestRequest,
    CollectorURLIngestResponse,
    CollectorSourceCreateRequest,
    CollectorSourceImportRequest,
    CollectorSourceImportResponse,
    CollectorSourceImportResult,
    CollectorSourceListResponse,
    CollectorSourceOut,
    CollectorSourceUpdateRequest,
    CollectorSummaryItemOut,
    CollectorStatusResponse,
    CollectorYouTubeIngestRequest,
    WechatAgentConfigPatchRequest,
    WechatAgentConfigResponse,
    WechatAgentCapturePreviewResponse,
    WechatAgentBatchCommandResponse,
    WechatAgentBatchStatusResponse,
    WechatAgentCommandResponse,
    WechatAgentDedupSummaryResponse,
    WechatAgentHealthResponse,
    WechatAgentOCRPreviewResponse,
    WechatAgentSelfHealResponse,
    WechatAgentStatusResponse,
)
from app.schemas.items import ItemOut
from app.services.content_extractor import extract_domain, normalize_text
from app.services.collector_daemon import (
    CollectorDaemonCommandResult,
    CollectorDaemonStatus,
    read_collector_daemon_status,
    run_collector_once,
    start_collector_daemon,
    stop_collector_daemon,
)
from app.services.collector_diagnostics import (
    create_ingest_attempt,
    infer_item_acquisition,
    list_item_attempts,
    serialize_ingest_attempt,
    serialize_item_diagnostics,
    update_item_ingest_state,
)
from app.services.collector_multiformat_service import (
    ingest_newsletter,
    ingest_uploaded_document,
    ingest_youtube_transcript,
    list_feed_sources,
    save_feed_source,
    serialize_feed_source,
    sync_rss_feeds,
)
from app.services.item_processing_runtime import (
    process_item_by_id,
    process_item_in_session,
    recover_stale_items,
)
from app.services.language import normalize_output_language
from app.services.user_context import ensure_demo_user
from app.services.vision_ocr_service import VisionOCRService
from app.services.wechat_url_resolver import resolve_wechat_article_url
from app.services.wechat_pc_agent_daemon import (
    WechatAgentCommandResult,
    WechatAgentBatchCommandResult,
    WechatAgentBatchStatus,
    WechatAgentHealthReport,
    WechatAgentSelfHealResult,
    WechatAgentStatus,
    capture_wechat_agent_preview,
    get_wechat_agent_health_report,
    read_wechat_agent_dedup_summary,
    read_wechat_agent_config,
    read_wechat_agent_batch_status,
    read_wechat_agent_status,
    reset_wechat_agent_dedup_state,
    run_wechat_agent_batch,
    run_wechat_agent_once,
    self_heal_wechat_agent,
    start_wechat_agent,
    stop_wechat_agent,
    update_wechat_agent_config,
)


router = APIRouter(prefix="/api/collector", tags=["collector"])
settings = get_settings()
vision_ocr = VisionOCRService()


def _is_valid_http_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _clean_text(value: str | None) -> str:
    return normalize_text(value or "")


def _normalize_source_url(url: str | None) -> str | None:
    if not url:
        return None
    text = str(url).strip()
    if not text:
        return None
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    normalized = parsed._replace(scheme=scheme, netloc=netloc, path=path, fragment="")
    return urlunparse(normalized)


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


def _load_item_with_tags(db: Session, item_id) -> Item | None:
    return db.scalar(select(Item).where(Item.id == item_id).options(selectinload(Item.tags)))


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


def _current_item_diagnostics(item: Item, db: Session) -> ItemDiagnosticsOut:
    attempts = list_item_attempts(db, item.id)
    return ItemDiagnosticsOut(**serialize_item_diagnostics(item, attempts))


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


def _evaluate_ocr_quality(body_text: str, confidence: float) -> tuple[bool, str | None]:
    text = _clean_text(body_text)
    if len(text) < 45:
        return False, "text_too_short"
    if confidence < 0.15:
        return False, "low_confidence"

    alnum = sum(1 for ch in text if ch.isalnum() or ("\u4e00" <= ch <= "\u9fff"))
    if alnum < 24:
        return False, "not_enough_readable_chars"

    noisy_patterns = [
        r"\b(登录|注册|用户名|密码|扫一扫|发现|通讯录)\b",
        r"\b(login|password|register|sign in|sign up)\b",
    ]
    noise_hits = 0
    lower = text.lower()
    for pattern in noisy_patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            noise_hits += 1
    if noise_hits >= 2 and len(text) < 140:
        return False, "likely_ui_text"

    comment_tokens = [
        "评论",
        "回复",
        "网友",
        "文明上网理性发言",
        "请先登录后发表评论",
        "内容由ai生成",
        "手机看",
        "打开小游戏",
    ]
    comment_hits = [token for token in comment_tokens if token in lower]
    reply_like_count = lower.count("回复") + lower.count("网友")
    if "请先登录后发表评论" in lower or "文明上网理性发言" in lower:
        return False, "comment_gate"
    if reply_like_count >= 3 and len(comment_hits) >= 3:
        return False, "comment_fragment"

    # Excessive symbol ratio usually indicates low-value OCR on chrome/UI areas.
    symbol_count = sum(1 for ch in text if not (ch.isalnum() or ch.isspace() or ("\u4e00" <= ch <= "\u9fff")))
    if symbol_count > len(text) * 0.35:
        return False, "high_symbol_ratio"

    return True, None


def _run_ocr_preview(
    *,
    image_base64: str,
    mime_type: str,
    source_url: str | None,
    title_hint: str | None,
    output_language: str,
) -> CollectorOCRPreviewResponse:
    try:
        ocr_result = vision_ocr.extract(
            image_base64=image_base64,
            mime_type=mime_type,
            source_url=source_url,
            title_hint=title_hint,
            output_language=output_language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - provider/runtime path
        raise HTTPException(status_code=500, detail=f"OCR extraction failed: {exc}") from exc

    body_text = _clean_text(ocr_result.body_text)
    quality_ok, quality_reason = _evaluate_ocr_quality(body_text, ocr_result.confidence)
    return CollectorOCRPreviewResponse(
        provider=ocr_result.provider,
        confidence=round(float(ocr_result.confidence), 3),
        text_length=len(body_text),
        title=_truncate_text(ocr_result.title, 120),
        body_preview=_truncate_text(body_text, 380),
        body_text=body_text,
        keywords=ocr_result.keywords[:8],
        quality_ok=quality_ok,
        quality_reason=quality_reason,
    )


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


def _to_daemon_status_response(status_obj: CollectorDaemonStatus) -> CollectorDaemonStatusResponse:
    return CollectorDaemonStatusResponse(
        running=status_obj.running,
        pid=status_obj.pid,
        pid_from_file=status_obj.pid_from_file,
        pid_file_present=status_obj.pid_file_present,
        uptime_seconds=status_obj.uptime_seconds,
        last_report_at=status_obj.last_report_at,
        last_daily_summary_at=status_obj.last_daily_summary_at,
        log_file=status_obj.log_file,
        log_size_bytes=status_obj.log_size_bytes,
        source_file_count=status_obj.source_file_count,
        log_tail=status_obj.log_tail,
    )


def _to_daemon_command_response(result: CollectorDaemonCommandResult) -> CollectorDaemonCommandResponse:
    return CollectorDaemonCommandResponse(
        action=result.action,
        ok=result.ok,
        message=result.message,
        status=_to_daemon_status_response(result.status),
        output=result.output,
    )


def _to_wechat_agent_status_response(status_obj: WechatAgentStatus) -> WechatAgentStatusResponse:
    return WechatAgentStatusResponse(
        running=status_obj.running,
        pid=status_obj.pid,
        pid_from_file=status_obj.pid_from_file,
        pid_file_present=status_obj.pid_file_present,
        run_once_running=status_obj.run_once_running,
        run_once_pid=status_obj.run_once_pid,
        uptime_seconds=status_obj.uptime_seconds,
        config_file=status_obj.config_file,
        config_file_present=status_obj.config_file_present,
        state_file=status_obj.state_file,
        state_file_present=status_obj.state_file_present,
        report_file=status_obj.report_file,
        report_file_present=status_obj.report_file_present,
        processed_hashes=status_obj.processed_hashes,
        last_cycle_at=status_obj.last_cycle_at,
        last_cycle_submitted=status_obj.last_cycle_submitted,
        last_cycle_submitted_new=status_obj.last_cycle_submitted_new,
        last_cycle_deduplicated_existing=status_obj.last_cycle_deduplicated_existing,
        last_cycle_failed=status_obj.last_cycle_failed,
        last_cycle_skipped_seen=status_obj.last_cycle_skipped_seen,
        last_cycle_skipped_low_quality=status_obj.last_cycle_skipped_low_quality,
        last_cycle_error=status_obj.last_cycle_error,
        last_cycle_new_item_ids=status_obj.last_cycle_new_item_ids,
        log_file=status_obj.log_file,
        log_size_bytes=status_obj.log_size_bytes,
        log_tail=status_obj.log_tail,
    )


def _to_wechat_agent_command_response(
    result: WechatAgentCommandResult,
) -> WechatAgentCommandResponse:
    return WechatAgentCommandResponse(
        action=result.action,
        ok=result.ok,
        message=result.message,
        status=_to_wechat_agent_status_response(result.status),
        output=result.output,
    )


def _to_wechat_agent_batch_status_response(
    status_obj: WechatAgentBatchStatus,
) -> WechatAgentBatchStatusResponse:
    return WechatAgentBatchStatusResponse(
        running=status_obj.running,
        total_items=status_obj.total_items,
        segment_items=status_obj.segment_items,
        start_batch_index=status_obj.start_batch_index,
        current_segment_index=status_obj.current_segment_index,
        total_segments=status_obj.total_segments,
        current_batch_index=status_obj.current_batch_index,
        started_at=status_obj.started_at,
        finished_at=status_obj.finished_at,
        submitted=status_obj.submitted,
        submitted_new=status_obj.submitted_new,
        submitted_url=status_obj.submitted_url,
        submitted_url_direct=status_obj.submitted_url_direct,
        submitted_url_share_copy=status_obj.submitted_url_share_copy,
        submitted_url_resolved=status_obj.submitted_url_resolved,
        submitted_ocr=status_obj.submitted_ocr,
        deduplicated_existing=status_obj.deduplicated_existing,
        deduplicated_existing_url=status_obj.deduplicated_existing_url,
        deduplicated_existing_url_direct=status_obj.deduplicated_existing_url_direct,
        deduplicated_existing_url_share_copy=status_obj.deduplicated_existing_url_share_copy,
        deduplicated_existing_url_resolved=status_obj.deduplicated_existing_url_resolved,
        deduplicated_existing_ocr=status_obj.deduplicated_existing_ocr,
        skipped_invalid_article=status_obj.skipped_invalid_article,
        skipped_seen=status_obj.skipped_seen,
        failed=status_obj.failed,
        validation_retries=status_obj.validation_retries,
        new_item_ids=status_obj.new_item_ids,
        last_message=status_obj.last_message,
        last_error=status_obj.last_error,
        live_report_running=status_obj.live_report_running,
        live_report_batch=status_obj.live_report_batch,
        live_report_row=status_obj.live_report_row,
        live_report_stage=status_obj.live_report_stage,
        live_report_detail=status_obj.live_report_detail,
        live_report_clicked=status_obj.live_report_clicked,
        live_report_submitted=status_obj.live_report_submitted,
        live_report_submitted_url=status_obj.live_report_submitted_url,
        live_report_submitted_url_direct=status_obj.live_report_submitted_url_direct,
        live_report_submitted_url_share_copy=status_obj.live_report_submitted_url_share_copy,
        live_report_submitted_url_resolved=status_obj.live_report_submitted_url_resolved,
        live_report_submitted_ocr=status_obj.live_report_submitted_ocr,
        live_report_skipped_seen=status_obj.live_report_skipped_seen,
        live_report_skipped_invalid_article=status_obj.live_report_skipped_invalid_article,
        live_report_failed=status_obj.live_report_failed,
        live_report_checkpoint_at=status_obj.live_report_checkpoint_at,
    )


def _to_wechat_agent_dedup_summary_response() -> WechatAgentDedupSummaryResponse:
    summary = read_wechat_agent_dedup_summary()
    return WechatAgentDedupSummaryResponse(
        processed_hashes=summary.processed_hashes,
        run_count=summary.run_count,
        last_run_started_at=summary.last_run_started_at,
        last_run_finished_at=summary.last_run_finished_at,
        last_run_submitted=summary.last_run_submitted,
        last_run_skipped_seen=summary.last_run_skipped_seen,
        last_run_failed=summary.last_run_failed,
        last_run_item_ids=summary.last_run_item_ids,
    )


def _to_wechat_agent_batch_command_response(
    result: WechatAgentBatchCommandResult,
) -> WechatAgentBatchCommandResponse:
    return WechatAgentBatchCommandResponse(
        ok=result.ok,
        message=result.message,
        batch_status=_to_wechat_agent_batch_status_response(result.batch_status),
    )


def _to_wechat_agent_config_response(payload: dict[str, object]) -> WechatAgentConfigResponse:
    return WechatAgentConfigResponse.model_validate(payload)


def _to_wechat_agent_health_response(payload: WechatAgentHealthReport) -> WechatAgentHealthResponse:
    return WechatAgentHealthResponse(
        healthy=payload.healthy,
        checked_at=payload.checked_at,
        stale_threshold_minutes=payload.stale_threshold_minutes,
        running=payload.running,
        last_cycle_at=payload.last_cycle_at,
        minutes_since_last_cycle=payload.minutes_since_last_cycle,
        reasons=payload.reasons,
        recommendation=payload.recommendation,
        status=_to_wechat_agent_status_response(payload.status),
    )


def _to_wechat_agent_self_heal_response(payload: WechatAgentSelfHealResult) -> WechatAgentSelfHealResponse:
    return WechatAgentSelfHealResponse(
        ok=payload.ok,
        action=payload.action,
        message=payload.message,
        health_before=_to_wechat_agent_health_response(payload.health_before),
        health_after=_to_wechat_agent_health_response(payload.health_after),
        output=payload.output,
    )


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
    source_url = _normalize_source_url(payload.source_url)
    if not source_url or not _is_valid_http_url(source_url):
        raise HTTPException(status_code=400, detail="source_url must start with http:// or https://")

    existing = db.scalar(
        select(CollectorSource)
        .where(CollectorSource.user_id == settings.single_user_id)
        .where(CollectorSource.source_url == source_url)
        .limit(1)
    )
    note_value = _clean_text(payload.note) or None
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
        normalized = _normalize_source_url(raw)
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
        normalized = _normalize_source_url(raw)
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
        source.note = _clean_text(payload.note) or None
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


@router.post("/newsletter/ingest", response_model=CollectorExternalIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_newsletter_item(
    payload: CollectorNewsletterIngestRequest,
    db: Session = Depends(get_db),
) -> CollectorExternalIngestResponse:
    ensure_demo_user(db)
    source_url = payload.source_url.strip() if payload.source_url else None
    if source_url and not _is_valid_http_url(source_url):
        raise HTTPException(status_code=400, detail="source_url must start with http:// or https://")
    result = ingest_newsletter(
        db,
        user_id=settings.single_user_id,
        title=payload.title,
        raw_content=payload.raw_content,
        sender=payload.sender,
        source_url=source_url,
        output_language=payload.output_language,
    )
    return CollectorExternalIngestResponse(
        item=ItemOut.model_validate(result["item"]),
        deduplicated=bool(result.get("deduplicated")),
        processing_deferred=False,
        attempt_id=result["attempt"].id if result.get("attempt") else None,
        ingest_route="newsletter",
        content_acquisition_status=result["item"].content_acquisition_status,
        resolver="newsletter_ingest",
        body_source="newsletter_body",
        fallback_used=bool(result["item"].fallback_used),
        metadata={"sender": result.get("sender")},
    )


@router.post("/files/upload", response_model=CollectorExternalIngestResponse, status_code=status.HTTP_201_CREATED)
def upload_document_item(
    payload: CollectorFileUploadRequest,
    db: Session = Depends(get_db),
) -> CollectorExternalIngestResponse:
    ensure_demo_user(db)
    source_url = payload.source_url.strip() if payload.source_url else None
    if source_url and not _is_valid_http_url(source_url):
        raise HTTPException(status_code=400, detail="source_url must start with http:// or https://")
    try:
        result = ingest_uploaded_document(
            db,
            user_id=settings.single_user_id,
            file_name=payload.file_name,
            mime_type=payload.mime_type,
            file_base64=payload.file_base64,
            extracted_text=payload.extracted_text,
            title=payload.title,
            source_url=source_url,
            output_language=payload.output_language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CollectorExternalIngestResponse(
        item=ItemOut.model_validate(result["item"]),
        deduplicated=bool(result.get("deduplicated")),
        processing_deferred=False,
        attempt_id=result["attempt"].id if result.get("attempt") else None,
        ingest_route="file_upload",
        content_acquisition_status=result["item"].content_acquisition_status,
        resolver="file_upload",
        body_source=result.get("parse_method"),
        fallback_used=bool(result["item"].fallback_used),
        metadata={
            "document_id": str(result["document"].id),
            "parse_status": result.get("parse_status"),
            "parse_method": result.get("parse_method"),
            "text_length": result.get("text_length"),
        },
    )


@router.post("/youtube/ingest", response_model=CollectorExternalIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_youtube_item(
    payload: CollectorYouTubeIngestRequest,
    db: Session = Depends(get_db),
) -> CollectorExternalIngestResponse:
    ensure_demo_user(db)
    try:
        result = ingest_youtube_transcript(
            db,
            user_id=settings.single_user_id,
            video_url=payload.video_url,
            transcript_text=payload.transcript_text,
            title=payload.title,
            output_language=payload.output_language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CollectorExternalIngestResponse(
        item=ItemOut.model_validate(result["item"]),
        deduplicated=bool(result.get("deduplicated")),
        processing_deferred=False,
        attempt_id=result["attempt"].id if result.get("attempt") else None,
        ingest_route="youtube_transcript",
        content_acquisition_status=result["item"].content_acquisition_status,
        resolver="youtube_ingest",
        body_source="youtube_transcript" if result.get("transcript_attached") else "youtube_link_only",
        fallback_used=bool(result["item"].fallback_used),
        metadata={
            "video_id": result.get("video_id"),
            "transcript_attached": bool(result.get("transcript_attached")),
        },
    )


@router.post("/plugin/ingest", response_model=CollectorPluginIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_plugin_item(
    payload: CollectorPluginIngestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> CollectorPluginIngestResponse:
    ensure_demo_user(db)
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
        process_item_in_session(db, item, output_language=resolved_language, auto_archive=True)
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
        _mark_source_collected(db, source_url, error=item.processing_error)
        db.commit()
    else:
        db.add(item)
        attempt = create_ingest_attempt(
            db,
            item=item,
            source_url=source_url,
            route_type="plugin",
            resolver="browser_plugin",
            attempt_status=attempt_status,
            body_source="plugin_body",
        )
        _mark_source_collected(db, source_url)
        db.commit()
        background_tasks.add_task(_process_item_task, item.id, resolved_language)

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


@router.post("/url/ingest", response_model=CollectorURLIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_url_item(
    payload: CollectorURLIngestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> CollectorURLIngestResponse:
    ensure_demo_user(db)
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
        process_item_in_session(db, item, output_language=resolved_language, auto_archive=True)
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
        _mark_source_collected(db, source_url, error=item.processing_error)
        db.commit()
    else:
        db.add(item)
        attempt = create_ingest_attempt(
            db,
            item=item,
            source_url=source_url,
            route_type="direct_url",
            resolver="page_fetch",
            attempt_status=attempt_status,
            body_source=body_source,
        )
        _mark_source_collected(db, source_url)
        db.commit()
        background_tasks.add_task(_process_item_task, item.id, resolved_language)

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


@router.post("/ocr/ingest", response_model=CollectorOCRIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_ocr_image(
    payload: CollectorOCRIngestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> CollectorOCRIngestResponse:
    ensure_demo_user(db)
    resolved_language = normalize_output_language(payload.output_language)
    source_url = payload.source_url.strip() if payload.source_url else None

    if source_url and not _is_valid_http_url(source_url):
        raise HTTPException(status_code=400, detail="source_url must start with http:// or https://")

    if payload.deduplicate and source_url:
        existing = _load_existing_item_by_url(db, source_url)
        if existing:
            update_item_ingest_state(existing, ingest_route=existing.ingest_route or "ocr", resolved_from_url=source_url)
            attempt = create_ingest_attempt(
                db,
                item=existing,
                source_url=source_url,
                route_type=existing.ingest_route or "ocr",
                resolver="existing_item",
                attempt_status="deduplicated",
                body_source=infer_item_acquisition(existing)[2],
            )
            db.add(existing)
            db.commit()
            return CollectorOCRIngestResponse(
                item=ItemOut.model_validate(existing),
                ocr_provider="deduplicate",
                ocr_confidence=1.0,
                ocr_text_length=len(existing.raw_content or ""),
                deduplicated=True,
                processing_deferred=False,
                attempt_id=attempt.id,
                ingest_route=existing.ingest_route or "ocr",
                content_acquisition_status=existing.content_acquisition_status,
                resolver="existing_item",
                body_source=attempt.body_source,
                fallback_used=existing.fallback_used,
            )

    try:
        ocr_result = vision_ocr.extract(
            image_base64=payload.image_base64,
            mime_type=payload.mime_type,
            source_url=source_url,
            title_hint=payload.title_hint,
            output_language=resolved_language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"OCR extraction failed: {exc}") from exc

    lines: list[str] = []
    if ocr_result.title:
        lines.append(f"标题：{_clean_text(ocr_result.title)}")
    if ocr_result.keywords:
        lines.append(f"关键词：{', '.join(ocr_result.keywords[:8])}")
    lines.append(f"正文：{_clean_text(ocr_result.body_text)}")
    raw_content = "\n".join(lines)

    fallback_used = "mock" in str(ocr_result.provider or "").lower()
    item = Item(
        user_id=settings.single_user_id,
        source_type="plugin" if source_url else "text",
        source_url=source_url,
        source_domain=extract_domain(source_url),
        title=_clean_text(ocr_result.title) or _clean_text(payload.title_hint) or None,
        raw_content=raw_content,
        output_language=resolved_language,
        ingest_route="ocr",
        content_acquisition_status="body_acquired",
        content_acquisition_note=f"OCR 已提取正文，provider={ocr_result.provider}",
        resolved_from_url=source_url,
        fallback_used=fallback_used,
        status="pending",
    )
    attempt_status = "queued"
    if payload.process_immediately:
        process_item_in_session(db, item, output_language=resolved_language, auto_archive=True)
        update_item_ingest_state(item, ingest_route="ocr", resolved_from_url=source_url, fallback_used=fallback_used)
        attempt_status = "ready" if item.status == "ready" else "failed"
        attempt = create_ingest_attempt(
            db,
            item=item,
            source_url=source_url,
            route_type="ocr",
            resolver="vision_ocr",
            attempt_status=attempt_status,
            body_source="ocr_text",
            confidence=round(ocr_result.confidence, 3),
            error_detail=item.processing_error,
        )
        _mark_source_collected(db, source_url, error=item.processing_error)
        db.commit()
    else:
        db.add(item)
        attempt = create_ingest_attempt(
            db,
            item=item,
            source_url=source_url,
            route_type="ocr",
            resolver="vision_ocr",
            attempt_status=attempt_status,
            body_source="ocr_text",
            confidence=round(ocr_result.confidence, 3),
        )
        _mark_source_collected(db, source_url)
        db.commit()
        background_tasks.add_task(_process_item_task, item.id, resolved_language)

    hydrated_item = _load_item_with_tags(db, item.id)
    if not hydrated_item:
        raise HTTPException(status_code=500, detail="failed to load item after processing")

    return CollectorOCRIngestResponse(
        item=ItemOut.model_validate(hydrated_item),
        ocr_provider=ocr_result.provider,
        ocr_confidence=round(ocr_result.confidence, 3),
        ocr_text_length=len(ocr_result.body_text),
        deduplicated=False,
        processing_deferred=not payload.process_immediately,
        attempt_id=attempt.id,
        ingest_route="ocr",
        content_acquisition_status=hydrated_item.content_acquisition_status,
        resolver="vision_ocr",
        body_source="ocr_text",
        fallback_used=hydrated_item.fallback_used,
    )


@router.post("/ocr/preview", response_model=CollectorOCRPreviewResponse)
def preview_ocr_image(
    payload: CollectorOCRPreviewRequest,
) -> CollectorOCRPreviewResponse:
    resolved_language = normalize_output_language(payload.output_language)
    source_url = payload.source_url.strip() if payload.source_url else None
    if source_url and not _is_valid_http_url(source_url):
        raise HTTPException(status_code=400, detail="source_url must start with http:// or https://")

    return _run_ocr_preview(
        image_base64=payload.image_base64,
        mime_type=payload.mime_type,
        source_url=source_url,
        title_hint=payload.title_hint,
        output_language=resolved_language,
    )


@router.post("/url/resolve", response_model=CollectorURLResolveResponse)
def resolve_url_from_preview(
    payload: CollectorURLResolveRequest,
) -> CollectorURLResolveResponse:
    body_seed = normalize_text(payload.body_text or "") or normalize_text(payload.body_preview or "")
    result = resolve_wechat_article_url(
        title_hint=payload.title_hint,
        body_preview=body_seed,
        search_limit=max(1, min(int(payload.candidate_limit or 5), 10)),
    )
    return CollectorURLResolveResponse(
        resolved_url=result.resolved_url,
        confidence=result.confidence,
        resolver=result.resolver,
        matched_via=result.matched_via,
        queries=result.queries,
        candidates=[
            CollectorURLResolveCandidateResponse(
                source_url=item.source_url,
                title=item.title,
                source_domain=item.source_domain,
                search_query=item.search_query,
                snippet=item.snippet,
                score=item.score,
                matched_title=item.matched_title,
                matched_excerpt=item.matched_excerpt,
            )
            for item in result.candidates
        ],
    )


@router.post("/process-pending", response_model=CollectorProcessPendingResponse)
def process_pending_items(
    limit: int = 20,
    output_language: str | None = None,
    db: Session = Depends(get_db),
) -> CollectorProcessPendingResponse:
    ensure_demo_user(db)
    safe_limit = max(1, min(limit, 200))
    result = recover_stale_items(
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


@router.get("/failed", response_model=CollectorFailedListResponse)
def list_failed_items(limit: int = 20, db: Session = Depends(get_db)) -> CollectorFailedListResponse:
    ensure_demo_user(db)
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


@router.post("/retry-failed", response_model=CollectorRetryFailedResponse)
def retry_failed_items(limit: int = 20, db: Session = Depends(get_db)) -> CollectorRetryFailedResponse:
    ensure_demo_user(db)
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

    for item_id in failed_item_ids:
        result = process_item_by_id(item_id, output_language=output_language, auto_archive=True)
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


@router.get("/daily-summary", response_model=CollectorDailySummaryResponse)
def get_daily_summary(
    hours: int = 24,
    limit: int = 12,
    db: Session = Depends(get_db),
) -> CollectorDailySummaryResponse:
    ensure_demo_user(db)
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
    processing_count = int(
        db.scalar(base_query.where(Item.status.in_(["pending", "processing"]))) or 0
    )
    failed_count = int(db.scalar(base_query.where(Item.status == "failed")) or 0)

    ready_period_query = base_query.where(Item.status == "ready")
    deep_read_count = int(
        db.scalar(ready_period_query.where(Item.action_suggestion == "deep_read")) or 0
    )
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


@router.get("/items/{item_id}/attempts", response_model=list[CollectorIngestAttemptOut])
def get_item_ingest_attempts(item_id: UUID, db: Session = Depends(get_db)) -> list[CollectorIngestAttemptOut]:
    ensure_demo_user(db)
    item = _load_item_with_tags(db, item_id)
    if not item or item.user_id != settings.single_user_id:
        raise HTTPException(status_code=404, detail="Item not found")
    return [CollectorIngestAttemptOut(**serialize_ingest_attempt(attempt)) for attempt in list_item_attempts(db, item_id)]


@router.get("/status", response_model=CollectorStatusResponse)
def get_collector_status(db: Session = Depends(get_db)) -> CollectorStatusResponse:
    ensure_demo_user(db)
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


@router.get("/daemon/status", response_model=CollectorDaemonStatusResponse)
def get_collector_daemon_status() -> CollectorDaemonStatusResponse:
    return _to_daemon_status_response(read_collector_daemon_status())


@router.post("/daemon/start", response_model=CollectorDaemonCommandResponse)
def start_collector_daemon_api(db: Session = Depends(get_db)) -> CollectorDaemonCommandResponse:
    ensure_demo_user(db)
    try:
        result = start_collector_daemon()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _to_daemon_command_response(result)


@router.post("/daemon/stop", response_model=CollectorDaemonCommandResponse)
def stop_collector_daemon_api(db: Session = Depends(get_db)) -> CollectorDaemonCommandResponse:
    ensure_demo_user(db)
    try:
        result = stop_collector_daemon()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _to_daemon_command_response(result)


@router.post("/daemon/run-once", response_model=CollectorDaemonCommandResponse)
def run_collector_daemon_once_api(
    output_language: str = "zh-CN",
    max_collect_per_cycle: int = 30,
    db: Session = Depends(get_db),
) -> CollectorDaemonCommandResponse:
    ensure_demo_user(db)
    safe_limit = max(5, min(max_collect_per_cycle, 200))
    try:
        result = run_collector_once(
            output_language=normalize_output_language(output_language),
            max_collect_per_cycle=safe_limit,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _to_daemon_command_response(result)


@router.get("/wechat-agent/status", response_model=WechatAgentStatusResponse)
def get_wechat_agent_status() -> WechatAgentStatusResponse:
    return _to_wechat_agent_status_response(read_wechat_agent_status())


@router.get("/wechat-agent/config", response_model=WechatAgentConfigResponse)
def get_wechat_agent_config_api() -> WechatAgentConfigResponse:
    return _to_wechat_agent_config_response(read_wechat_agent_config())


@router.put("/wechat-agent/config", response_model=WechatAgentConfigResponse)
def update_wechat_agent_config_api(
    payload: WechatAgentConfigPatchRequest,
) -> WechatAgentConfigResponse:
    config = update_wechat_agent_config(payload.model_dump(exclude_none=True))
    return _to_wechat_agent_config_response(config)


@router.get("/wechat-agent/health", response_model=WechatAgentHealthResponse)
def get_wechat_agent_health_api(
    stale_minutes: int | None = None,
) -> WechatAgentHealthResponse:
    report = get_wechat_agent_health_report(stale_minutes)
    return _to_wechat_agent_health_response(report)


@router.post("/wechat-agent/self-heal", response_model=WechatAgentSelfHealResponse)
def self_heal_wechat_agent_api(
    force: bool = False,
) -> WechatAgentSelfHealResponse:
    result = self_heal_wechat_agent(force=bool(force))
    return _to_wechat_agent_self_heal_response(result)


@router.get("/wechat-agent/preview-capture", response_model=WechatAgentCapturePreviewResponse)
def get_wechat_agent_preview_capture_api() -> WechatAgentCapturePreviewResponse:
    try:
        payload = capture_wechat_agent_preview()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - platform/runtime path
        raise HTTPException(status_code=500, detail=f"capture preview failed: {exc}") from exc
    return WechatAgentCapturePreviewResponse.model_validate(payload)


@router.get("/wechat-agent/preview-ocr", response_model=WechatAgentOCRPreviewResponse)
def get_wechat_agent_preview_ocr_api(
    output_language: str = "zh-CN",
) -> WechatAgentOCRPreviewResponse:
    resolved_language = normalize_output_language(output_language)
    try:
        capture_payload = capture_wechat_agent_preview()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - platform/runtime path
        raise HTTPException(status_code=500, detail=f"capture preview failed: {exc}") from exc

    image_base64_value = str(capture_payload.get("image_base64") or "")
    mime_type_value = str(capture_payload.get("mime_type") or "image/png")
    if not image_base64_value:
        raise HTTPException(status_code=500, detail="empty image data from capture preview")
    preview = _run_ocr_preview(
        image_base64=image_base64_value,
        mime_type=mime_type_value,
        source_url=None,
        title_hint=None,
        output_language=resolved_language,
    )
    return WechatAgentOCRPreviewResponse(
        captured_at=capture_payload["captured_at"],
        provider=preview.provider,
        confidence=preview.confidence,
        text_length=preview.text_length,
        title=preview.title,
        body_preview=preview.body_preview,
        keywords=preview.keywords,
        quality_ok=preview.quality_ok,
        quality_reason=preview.quality_reason,
    )


@router.post("/wechat-agent/start", response_model=WechatAgentCommandResponse)
def start_wechat_agent_api() -> WechatAgentCommandResponse:
    try:
        result = start_wechat_agent()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _to_wechat_agent_command_response(result)


@router.post("/wechat-agent/stop", response_model=WechatAgentCommandResponse)
def stop_wechat_agent_api() -> WechatAgentCommandResponse:
    try:
        result = stop_wechat_agent()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _to_wechat_agent_command_response(result)


@router.post("/wechat-agent/run-once", response_model=WechatAgentCommandResponse)
def run_wechat_agent_once_api(
    output_language: str = "zh-CN",
    max_items: int = 12,
    start_batch_index: int = 0,
    wait: bool = False,
) -> WechatAgentCommandResponse:
    safe_max_items = max(1, min(max_items, 200))
    safe_start_batch_index = max(0, min(start_batch_index, 1_000))
    try:
        result = run_wechat_agent_once(
            output_language=normalize_output_language(output_language),
            max_items=safe_max_items,
            start_batch_index=safe_start_batch_index,
            wait=bool(wait),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _to_wechat_agent_command_response(result)


@router.get("/wechat-agent/batch-status", response_model=WechatAgentBatchStatusResponse)
def get_wechat_agent_batch_status_api() -> WechatAgentBatchStatusResponse:
    return _to_wechat_agent_batch_status_response(read_wechat_agent_batch_status())


@router.get("/wechat-agent/dedup-summary", response_model=WechatAgentDedupSummaryResponse)
def get_wechat_agent_dedup_summary_api() -> WechatAgentDedupSummaryResponse:
    return _to_wechat_agent_dedup_summary_response()


@router.post("/wechat-agent/reset-dedup", response_model=WechatAgentDedupSummaryResponse)
def reset_wechat_agent_dedup_api(clear_runs: bool = False) -> WechatAgentDedupSummaryResponse:
    try:
        summary = reset_wechat_agent_dedup_state(clear_runs=bool(clear_runs))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return WechatAgentDedupSummaryResponse(
        processed_hashes=summary.processed_hashes,
        run_count=summary.run_count,
        last_run_started_at=summary.last_run_started_at,
        last_run_finished_at=summary.last_run_finished_at,
        last_run_submitted=summary.last_run_submitted,
        last_run_skipped_seen=summary.last_run_skipped_seen,
        last_run_failed=summary.last_run_failed,
        last_run_item_ids=summary.last_run_item_ids,
    )


@router.post("/wechat-agent/run-batch", response_model=WechatAgentBatchCommandResponse)
def run_wechat_agent_batch_api(
    output_language: str = "zh-CN",
    total_items: int = 50,
    segment_items: int = 10,
    start_batch_index: int = 0,
) -> WechatAgentBatchCommandResponse:
    safe_total_items = max(1, min(total_items, 200))
    safe_segment_items = max(1, min(segment_items, safe_total_items, 100))
    safe_start_batch_index = max(0, min(start_batch_index, 1_000))
    try:
        result = run_wechat_agent_batch(
            output_language=normalize_output_language(output_language),
            total_items=safe_total_items,
            segment_items=safe_segment_items,
            start_batch_index=safe_start_batch_index,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _to_wechat_agent_batch_command_response(result)
