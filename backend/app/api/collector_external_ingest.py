from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.collector_url_utils import is_valid_http_url
from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.collector import (
    CollectorExternalIngestResponse,
    CollectorFileUploadRequest,
    CollectorNewsletterIngestRequest,
    CollectorYouTubeIngestRequest,
)
from app.schemas.items import ItemOut
from app.services.collector_multiformat_service import (
    ingest_newsletter,
    ingest_uploaded_document,
    ingest_youtube_transcript,
)
from app.services.user_context import ensure_demo_user


router = APIRouter(prefix="/api/collector", tags=["collector"])
settings = get_settings()


@router.post("/newsletter/ingest", response_model=CollectorExternalIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_newsletter_item(
    payload: CollectorNewsletterIngestRequest,
    db: Session = Depends(get_db),
) -> CollectorExternalIngestResponse:
    ensure_demo_user(db)
    source_url = payload.source_url.strip() if payload.source_url else None
    if source_url and not is_valid_http_url(source_url):
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
    if source_url and not is_valid_http_url(source_url):
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
