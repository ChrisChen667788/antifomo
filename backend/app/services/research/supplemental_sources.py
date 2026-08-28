from __future__ import annotations

from hashlib import sha256
import re
from urllib import parse

from app.schemas.research import ResearchSupplementalDocumentIn
from app.services.content_extractor import normalize_text
from app.services.research.source_documents import SourceDocument
from app.services.research.web_search import SearchHit


HTTP_URL_PATTERN = re.compile(r"https?://[^\s<>()\[\]\"']+", re.IGNORECASE)


def build_user_supplied_hits(text: str | None) -> list[SearchHit]:
    normalized = normalize_text(text or "")
    urls: list[str] = []
    for match in HTTP_URL_PATTERN.findall(normalized):
        url = match.rstrip(".,;:!?，。；：！？、")
        if url and url not in urls:
            urls.append(url)
    hits: list[SearchHit] = []
    for url in urls[:12]:
        hostname = (parse.urlparse(url).hostname or "").removeprefix("www.")
        hits.append(
            SearchHit(
                title=f"用户补充来源 · {hostname or '网页'}",
                url=url,
                snippet=normalized[:800],
                search_query="user:supplemental",
                source_label="用户补充来源",
                source_origin="user_supplied",
            )
        )
    return hits


def build_user_supplied_documents(
    documents: list[ResearchSupplementalDocumentIn],
) -> list[SourceDocument]:
    sources: list[SourceDocument] = []
    for document in documents[:4]:
        content = normalize_text(document.extracted_text)
        if not content:
            continue
        digest = sha256(
            f"{document.file_name}\n{content}".encode("utf-8")
        ).hexdigest()[:20]
        source_url = normalize_text(document.source_url or "")
        url = source_url or (
            f"https://user-material.local/{digest}/"
            f"{parse.quote(document.file_name, safe='._-')}"
        )
        domain = (parse.urlparse(url).hostname or "user-material.local").removeprefix("www.")
        sources.append(
            SourceDocument(
                title=normalize_text(document.file_name),
                url=url,
                domain=domain,
                snippet=content[:500],
                search_query="user:supplemental-document",
                source_type="user_document",
                content_status="user_supplied",
                excerpt=content[:16000],
                source_label="用户补充材料",
                source_tier="media",
                source_origin="user_supplied",
            )
        )
    return sources
