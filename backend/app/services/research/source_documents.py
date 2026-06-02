from __future__ import annotations

from dataclasses import dataclass

from app.schemas.research import ResearchSourceOut


@dataclass(slots=True)
class SourceDocument:
    title: str
    url: str
    domain: str | None
    snippet: str
    search_query: str
    source_type: str
    content_status: str
    excerpt: str
    source_label: str | None = None
    source_tier: str = "media"
    source_origin: str = "search"


def source_documents_to_research_source_outputs(sources: list[SourceDocument]) -> list[ResearchSourceOut]:
    return [
        ResearchSourceOut(
            title=source.title,
            url=source.url,
            domain=source.domain,
            snippet=source.snippet,
            search_query=source.search_query,
            source_type=source.source_type,
            content_status=source.content_status,
            source_label=source.source_label,
            source_tier=source.source_tier if source.source_tier in {"official", "media", "aggregate"} else "media",
        )
        for source in sources
    ]
