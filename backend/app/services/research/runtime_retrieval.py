from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.content_extractor import normalize_text
from app.services.research.source_documents import SourceDocument
from app.services.research_retrieval_index_service import (
    ResearchRetrievalIndex,
    ResearchRetrievalIndexChunk,
    build_research_retrieval_index,
    load_persistent_research_retrieval_index,
)


def source_documents_to_runtime_retrieval_chunks(
    sources: list[SourceDocument],
    *,
    scope_hints: dict[str, object],
) -> list[ResearchRetrievalIndexChunk]:
    regions = [normalize_text(str(item)) for item in scope_hints.get("regions", []) or [] if normalize_text(str(item))]
    industries = [normalize_text(str(item)) for item in scope_hints.get("industries", []) or [] if normalize_text(str(item))]
    now = datetime.now(timezone.utc)
    chunks: list[ResearchRetrievalIndexChunk] = []
    for index, source in enumerate(sources, start=1):
        text = normalize_text(
            "；".join(
                part
                for part in [source.title, source.search_query, source.snippet, source.excerpt]
                if normalize_text(part)
            )
        )
        if not text:
            continue
        document_id = normalize_text(source.url) or f"runtime-source-{index}"
        label = normalize_text(source.source_label or "") or normalize_text(source.source_type or "") or "runtime_source"
        chunks.append(
            ResearchRetrievalIndexChunk(
                chunk_id=f"runtime-source-{index}",
                document_id=document_id,
                document_type="runtime_source",
                title=normalize_text(source.title) or document_id,
                text=text[:840],
                field_key="source_excerpt",
                label=label,
                source_tier=source.source_tier if source.source_tier in {"official", "media", "aggregate"} else "media",
                source_url=normalize_text(source.url),
                region=" / ".join(regions[:2]),
                industry=" / ".join(industries[:2]),
                created_at=now,
                updated_at=now,
                priority=18 if source.source_tier == "official" else 10 if source.source_tier == "media" else 7,
                metadata={
                    "source_type": normalize_text(source.source_type),
                    "content_status": normalize_text(source.content_status),
                },
            )
        )
    return chunks


def load_runtime_research_retrieval_index(
    *,
    sources: list[SourceDocument],
    scope_hints: dict[str, object],
) -> ResearchRetrievalIndex:
    settings = get_settings()
    base_index = ResearchRetrievalIndex(chunks=[], built_at=datetime.now(timezone.utc), source_counts={})
    try:
        with SessionLocal() as db:
            base_index = load_persistent_research_retrieval_index(
                db,
                user_id=settings.single_user_id,
                limit=6000,
            )
            if not base_index.chunks:
                base_index = build_research_retrieval_index(
                    db,
                    user_id=settings.single_user_id,
                    limit_per_source=240,
                )
    except Exception:
        base_index = ResearchRetrievalIndex(chunks=[], built_at=datetime.now(timezone.utc), source_counts={})

    runtime_chunks = source_documents_to_runtime_retrieval_chunks(sources, scope_hints=scope_hints)
    combined_chunks = [*runtime_chunks, *base_index.chunks]
    return ResearchRetrievalIndex(
        chunks=combined_chunks,
        built_at=datetime.now(timezone.utc),
        source_counts=dict(Counter(chunk.document_type for chunk in combined_chunks)),
    )
