from __future__ import annotations

from fastapi import APIRouter

from app.schemas.collector import (
    CollectorURLResolveCandidateResponse,
    CollectorURLResolveRequest,
    CollectorURLResolveResponse,
)
from app.services.content_extractor import normalize_text
from app.services.wechat_url_resolver import resolve_wechat_article_url


router = APIRouter(prefix="/api/collector", tags=["collector"])


def resolve_url_from_preview_impl(payload: CollectorURLResolveRequest) -> CollectorURLResolveResponse:
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


@router.post("/url/resolve", response_model=CollectorURLResolveResponse)
def resolve_url_from_preview(
    payload: CollectorURLResolveRequest,
) -> CollectorURLResolveResponse:
    return resolve_url_from_preview_impl(payload)
