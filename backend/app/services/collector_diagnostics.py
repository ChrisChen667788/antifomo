from __future__ import annotations

from typing import Any
import uuid

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import Item
from app.models.workflow_entities import CollectorIngestAttempt
from app.services.content_extractor import normalize_text


settings = get_settings()

_ACCESS_LIMITED_HINTS = (
    "访问受限",
    "未能抓取到正文",
    "暂未获取正文",
    "暂未获取到正文",
    "需要登录",
    "验证码",
    "access is restricted",
    "text is not available",
)


def _normalized_text(value: str | None) -> str:
    return normalize_text(value or "")


def _contains_access_limited_marker(item: Item) -> bool:
    haystack = " ".join(
        [
            _normalized_text(item.title),
            _normalized_text(item.raw_content),
            _normalized_text(item.clean_content),
            _normalized_text(item.processing_error),
        ]
    ).lower()
    return any(marker.lower() in haystack for marker in _ACCESS_LIMITED_HINTS)


def infer_item_acquisition(item: Item) -> tuple[str, str | None, str]:
    if item.status in {"pending", "processing"}:
        return "pending_processing", "等待正文处理完成", "pending"
    if _contains_access_limited_marker(item):
        return "access_limited", "链接访问受限，当前未能稳定获取正文", "access_limited_placeholder"
    body = _normalized_text(item.clean_content or item.raw_content)
    if len(body) >= 40:
        if item.ingest_route == "plugin":
            return "body_acquired", "已通过浏览器插件写入正文", "plugin_body"
        if item.ingest_route == "ocr":
            return "body_acquired", "已通过 OCR 写入正文", "ocr_text"
        return "body_acquired", "已获取正文", "direct_fetch"
    if item.source_url:
        return "title_only", "仅保存链接与标题，正文待补全", "title_only"
    return "missing_body", "当前缺少正文内容", "missing_body"


def update_item_ingest_state(
    item: Item,
    *,
    ingest_route: str | None = None,
    resolved_from_url: str | None = None,
    fallback_used: bool | None = None,
    content_acquisition_status: str | None = None,
    content_acquisition_note: str | None = None,
) -> Item:
    if ingest_route is not None:
        item.ingest_route = ingest_route
    if resolved_from_url is not None:
        item.resolved_from_url = resolved_from_url
    if fallback_used is not None:
        item.fallback_used = bool(fallback_used)
    if content_acquisition_status is None:
        content_acquisition_status, inferred_note, _ = infer_item_acquisition(item)
        if content_acquisition_note is None:
            content_acquisition_note = inferred_note
    item.content_acquisition_status = content_acquisition_status
    item.content_acquisition_note = content_acquisition_note
    return item


def create_ingest_attempt(
    db: Session,
    *,
    item: Item,
    source_url: str | None,
    route_type: str,
    resolver: str | None,
    attempt_status: str,
    body_source: str | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
    confidence: float | None = None,
) -> CollectorIngestAttempt:
    attempt = CollectorIngestAttempt(
        user_id=item.user_id,
        item_id=item.id,
        source_url=source_url,
        source_type=item.source_type,
        route_type=route_type,
        resolver=resolver,
        attempt_status=attempt_status,
        error_code=error_code,
        error_detail=error_detail,
        body_source=body_source,
        body_length=len(_normalized_text(item.clean_content or item.raw_content)) or None,
        confidence=confidence,
    )
    db.add(attempt)
    return attempt


def list_item_attempts(db: Session, item_id: uuid.UUID) -> list[CollectorIngestAttempt]:
    return list(
        db.scalars(
            select(CollectorIngestAttempt)
            .where(CollectorIngestAttempt.item_id == item_id)
            .where(CollectorIngestAttempt.user_id == settings.single_user_id)
            .order_by(desc(CollectorIngestAttempt.created_at))
        )
    )


def serialize_ingest_attempt(attempt: CollectorIngestAttempt) -> dict[str, Any]:
    return {
        "id": str(attempt.id),
        "item_id": str(attempt.item_id),
        "source_url": attempt.source_url,
        "source_type": attempt.source_type,
        "route_type": attempt.route_type,
        "resolver": attempt.resolver,
        "attempt_status": attempt.attempt_status,
        "error_code": attempt.error_code,
        "error_detail": attempt.error_detail,
        "body_source": attempt.body_source,
        "body_length": attempt.body_length,
        "confidence": attempt.confidence,
        "created_at": attempt.created_at,
    }


def serialize_item_diagnostics(item: Item, attempts: list[CollectorIngestAttempt] | None = None) -> dict[str, Any]:
    acquisition_status, acquisition_note, body_source = infer_item_acquisition(item)
    latest_attempt = (attempts or [None])[0]
    return {
        "item_id": str(item.id),
        "source_type": item.source_type,
        "source_url": item.source_url,
        "ingest_route": item.ingest_route or "unknown",
        "resolved_from_url": item.resolved_from_url,
        "content_acquisition_status": item.content_acquisition_status or acquisition_status,
        "content_acquisition_note": item.content_acquisition_note or acquisition_note,
        "fallback_used": bool(item.fallback_used),
        "body_source": latest_attempt.body_source if latest_attempt and latest_attempt.body_source else body_source,
        "processing_status": item.status,
        "processing_error": item.processing_error,
        "latest_attempt": serialize_ingest_attempt(latest_attempt) if latest_attempt else None,
        "attempt_count": len(attempts or []),
    }
