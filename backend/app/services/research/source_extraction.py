from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.services.content_extractor import ContentExtractionError, extract_domain, normalize_text
from app.services.research.source_documents import SourceDocument
from app.services.research.web_search import SearchHit


@dataclass(frozen=True, slots=True)
class SourceExtractionDependencies:
    classify_source_type: Callable[[str], str]
    classify_source_tier: Callable[..., str]
    derive_source_label: Callable[..., str | None]
    truncate_text: Callable[[str | None, int], str]
    clean_source_text_for_analysis: Callable[[str], str]
    extract_from_browser: Callable[..., object]
    extract_from_url: Callable[..., object]
    extract_from_reader_proxy: Callable[..., object]


def extract_source_document(
    hit: SearchHit,
    *,
    timeout_seconds: int,
    excerpt_chars: int,
    deps: SourceExtractionDependencies,
) -> SourceDocument:
    title = normalize_text(hit.title) or hit.url
    domain = extract_domain(hit.url)
    source_type = hit.source_hint or deps.classify_source_type(hit.url)
    source_origin = "adapter" if bool(getattr(hit, "source_label", None)) else "search"
    source_label = deps.derive_source_label(source_type=source_type, domain=domain, fallback=getattr(hit, "source_label", None))
    source_tier = deps.classify_source_tier(source_type=source_type, domain=domain, source_label=source_label)
    snippet = deps.truncate_text(
        deps.clean_source_text_for_analysis(hit.snippet or "") or deps.clean_source_text_for_analysis(title),
        180,
    )

    extracted_title = title
    excerpt = snippet
    content_status = "snippet_only"

    if source_type != "tender_feed":
        if source_type == "wechat" or (domain or "").endswith("mp.weixin.qq.com"):
            try:
                extracted = deps.extract_from_browser(hit.url, timeout_seconds=max(timeout_seconds, 12))
                extracted_title = normalize_text(getattr(extracted, "title", "") or title) or title
                excerpt = deps.truncate_text(
                    deps.clean_source_text_for_analysis(
                        getattr(extracted, "clean_content", "") or getattr(extracted, "raw_content", "") or snippet
                    ),
                    excerpt_chars,
                )
                content_status = "browser_extracted"
            except ContentExtractionError:
                pass
        if content_status == "snippet_only":
            try:
                extracted = deps.extract_from_url(hit.url, timeout_seconds=timeout_seconds)
                extracted_title = normalize_text(getattr(extracted, "title", "") or title) or title
                excerpt = deps.truncate_text(
                    deps.clean_source_text_for_analysis(
                        getattr(extracted, "clean_content", "") or getattr(extracted, "raw_content", "") or snippet
                    ),
                    excerpt_chars,
                )
                content_status = "extracted"
            except ContentExtractionError:
                try:
                    extracted = deps.extract_from_reader_proxy(hit.url, timeout_seconds=max(timeout_seconds + 2, 10))
                    extracted_title = normalize_text(getattr(extracted, "title", "") or title) or title
                    excerpt = deps.truncate_text(
                        deps.clean_source_text_for_analysis(
                            getattr(extracted, "clean_content", "") or getattr(extracted, "raw_content", "") or snippet
                        ),
                        excerpt_chars,
                    )
                    content_status = "reader_proxy"
                except ContentExtractionError:
                    pass

    return SourceDocument(
        title=extracted_title,
        url=hit.url,
        domain=domain,
        snippet=snippet,
        search_query=hit.search_query,
        source_type=source_type,
        content_status=content_status,
        excerpt=excerpt,
        source_label=source_label,
        source_tier=source_tier,
        source_origin=source_origin,
    )


def extract_source_document_best_effort(
    hit: SearchHit,
    *,
    timeout_seconds: int,
    excerpt_chars: int,
    deps: SourceExtractionDependencies,
) -> SourceDocument | None:
    try:
        return extract_source_document(
            hit,
            timeout_seconds=timeout_seconds,
            excerpt_chars=excerpt_chars,
            deps=deps,
        )
    except Exception:
        domain = extract_domain(hit.url)
        source_type = hit.source_hint or deps.classify_source_type(hit.url)
        source_label = deps.derive_source_label(
            source_type=source_type,
            domain=domain,
            fallback=getattr(hit, "source_label", None),
        )
        source_tier = deps.classify_source_tier(
            source_type=source_type,
            domain=domain,
            source_label=source_label,
        )
        if not normalize_text(hit.url):
            return None
        return SourceDocument(
            title=normalize_text(hit.title) or hit.url,
            url=hit.url,
            domain=domain,
            snippet=deps.truncate_text(deps.clean_source_text_for_analysis(hit.snippet), 180),
            search_query=hit.search_query,
            source_type=source_type,
            content_status="fetch_failed",
            excerpt=deps.truncate_text(deps.clean_source_text_for_analysis(hit.snippet), excerpt_chars),
            source_label=source_label,
            source_tier=source_tier,
            source_origin="adapter" if bool(getattr(hit, "source_label", None)) else "search",
        )
