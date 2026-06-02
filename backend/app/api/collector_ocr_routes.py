from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.collector_ingest import (
    EnsureDemoUserFn,
    MarkSourceCollectedFn,
    ProcessItemInSessionFn,
    ProcessItemTaskFn,
    _load_existing_item_by_url,
    _load_item_with_tags,
    _mark_source_collected,
    _persist_new_item,
    _process_item_task,
)
from app.api.collector_ocr import (
    crop_preview_image_base64 as _ocr_crop_preview_image_base64,
    evaluate_ocr_quality as _ocr_evaluate_ocr_quality,
    normalize_ocr_preview_quality_reason as _ocr_normalize_ocr_preview_quality_reason,
    run_ocr_preview as _ocr_run_ocr_preview,
    run_ocr_preview_with_variants as _ocr_run_ocr_preview_with_variants,
)
from app.api.collector_url_utils import clean_text as _clean_text, is_valid_http_url as _is_valid_http_url
from app.core.config import get_settings
from app.db.session import get_db
from app.models.entities import Item
from app.schemas.collector import (
    CollectorOCRIngestRequest,
    CollectorOCRIngestResponse,
    CollectorOCRPreviewRequest,
    CollectorOCRPreviewResponse,
)
from app.schemas.items import ItemOut
from app.services.collector_diagnostics import (
    create_ingest_attempt,
    infer_item_acquisition,
    update_item_ingest_state,
)
from app.services.content_extractor import extract_domain
from app.services.item_processing_runtime import process_item_in_session
from app.services.language import normalize_output_language
from app.services.user_context import ensure_demo_user
from app.services.vision_ocr_service import VisionOCRService


router = APIRouter(prefix="/api/collector", tags=["collector"])
settings = get_settings()
vision_ocr = VisionOCRService()

try:  # pragma: no cover - optional dependency path
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

RunOcrPreviewWithVariantsFn = Callable[..., CollectorOCRPreviewResponse]


def _truncate_text(value: str | None, limit: int = 140) -> str:
    text = _clean_text(value)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


def _evaluate_ocr_quality(body_text: str, confidence: float) -> tuple[bool, str | None]:
    return _ocr_evaluate_ocr_quality(body_text, confidence, clean_text=_clean_text)


def _run_ocr_preview(
    *,
    image_base64: str,
    mime_type: str,
    source_url: str | None,
    title_hint: str | None,
    output_language: str,
) -> CollectorOCRPreviewResponse:
    return _ocr_run_ocr_preview(
        image_base64=image_base64,
        mime_type=mime_type,
        source_url=source_url,
        title_hint=title_hint,
        output_language=output_language,
        vision_ocr=vision_ocr,
        clean_text=_clean_text,
        truncate_text=_truncate_text,
        evaluate_quality=_evaluate_ocr_quality,
    )


def _normalize_ocr_preview_quality_reason(reason: str | None) -> str:
    return _ocr_normalize_ocr_preview_quality_reason(reason, clean_text=_clean_text)


def _crop_preview_image_base64(
    image_base64: str,
    *,
    variant_name: str,
) -> str | None:
    return _ocr_crop_preview_image_base64(image_base64, variant_name=variant_name, image_cls=Image)


def _run_ocr_preview_with_variants(
    *,
    image_base64: str,
    mime_type: str,
    source_url: str | None,
    title_hint: str | None,
    output_language: str,
) -> CollectorOCRPreviewResponse:
    return _ocr_run_ocr_preview_with_variants(
        image_base64=image_base64,
        mime_type=mime_type,
        source_url=source_url,
        title_hint=title_hint,
        output_language=output_language,
        run_ocr_preview=_run_ocr_preview,
        normalize_quality_reason=_normalize_ocr_preview_quality_reason,
        crop_preview_image_base64=_crop_preview_image_base64,
    )


def ingest_ocr_image_impl(
    payload: CollectorOCRIngestRequest,
    background_tasks: BackgroundTasks,
    db: Session,
    *,
    ensure_demo_user_fn: EnsureDemoUserFn = ensure_demo_user,
    mark_source_collected_fn: MarkSourceCollectedFn = _mark_source_collected,
    process_item_in_session_fn: ProcessItemInSessionFn = process_item_in_session,
    process_item_task_fn: ProcessItemTaskFn = _process_item_task,
    vision_ocr_service: Any = vision_ocr,
) -> CollectorOCRIngestResponse:
    ensure_demo_user_fn(db)
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
        ocr_result = vision_ocr_service.extract(
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
        _persist_new_item(db, item)
        process_item_in_session_fn(db, item, output_language=resolved_language, auto_archive=True)
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
        mark_source_collected_fn(db, source_url, item.processing_error)
        db.commit()
    else:
        _persist_new_item(db, item)
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
        mark_source_collected_fn(db, source_url, None)
        db.commit()
        background_tasks.add_task(process_item_task_fn, item.id, resolved_language)

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


def preview_ocr_image_impl(
    payload: CollectorOCRPreviewRequest,
    *,
    run_ocr_preview_with_variants_fn: RunOcrPreviewWithVariantsFn,
) -> CollectorOCRPreviewResponse:
    resolved_language = normalize_output_language(payload.output_language)
    source_url = payload.source_url.strip() if payload.source_url else None
    if source_url and not _is_valid_http_url(source_url):
        raise HTTPException(status_code=400, detail="source_url must start with http:// or https://")

    return run_ocr_preview_with_variants_fn(
        image_base64=payload.image_base64,
        mime_type=payload.mime_type,
        source_url=source_url,
        title_hint=payload.title_hint,
        output_language=resolved_language,
    )


@router.post("/ocr/ingest", response_model=CollectorOCRIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_ocr_image(
    payload: CollectorOCRIngestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> CollectorOCRIngestResponse:
    return ingest_ocr_image_impl(payload, background_tasks, db)


@router.post("/ocr/preview", response_model=CollectorOCRPreviewResponse)
def preview_ocr_image(
    payload: CollectorOCRPreviewRequest,
) -> CollectorOCRPreviewResponse:
    return preview_ocr_image_impl(payload, run_ocr_preview_with_variants_fn=_run_ocr_preview_with_variants)
