from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import KnowledgeEntry
from app.models.research_entities import (
    ResearchCompareSnapshot,
    ResearchMarkdownArchive,
    ResearchReportVersion,
    ResearchTrackingTopic,
)
from app.services.content_extractor import normalize_text
from app.services.knowledge_retrieval_service import TextRetrievalCandidate, retrieve_text_matches
from app.services.research_retrieval_service import build_report_retrieval_chunks


RESEARCH_RETRIEVAL_INDEX_SCHEMA_VERSION = 1

_VALID_SOURCE_TIERS = {"official", "media", "aggregate"}


@dataclass(slots=True)
class ResearchRetrievalIndexChunk:
    chunk_id: str
    document_id: str
    document_type: str
    title: str
    text: str
    field_key: str
    label: str
    source_tier: str = "media"
    source_url: str = ""
    parent_chunk_id: str = ""
    topic_id: str = ""
    topic_name: str = ""
    region: str = ""
    industry: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def search_text(self) -> str:
        return "；".join(
            part
            for part in [
                self.title,
                self.label,
                self.field_key,
                self.topic_name,
                self.region,
                self.industry,
                self.text,
            ]
            if normalize_text(part)
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_type": self.document_type,
            "title": self.title,
            "text": self.text,
            "field_key": self.field_key,
            "label": self.label,
            "source_tier": self.source_tier,
            "source_url": self.source_url,
            "parent_chunk_id": self.parent_chunk_id,
            "topic_id": self.topic_id,
            "topic_name": self.topic_name,
            "region": self.region,
            "industry": self.industry,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else None,
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else None,
            "priority": self.priority,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class ResearchRetrievalIndex:
    chunks: list[ResearchRetrievalIndexChunk]
    built_at: datetime
    schema_version: int = RESEARCH_RETRIEVAL_INDEX_SCHEMA_VERSION
    source_counts: dict[str, int] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "built_at": self.built_at.isoformat(),
            "chunk_count": len(self.chunks),
            "source_counts": dict(self.source_counts),
        }


@dataclass(slots=True)
class ResearchRetrievalIndexHit:
    chunk: ResearchRetrievalIndexChunk
    score: float
    match_modes: tuple[str, ...]
    matched_terms: tuple[str, ...]
    lexical_overlap: int
    dense_similarity: float
    exact_query_hit: bool

    def to_payload(self) -> dict[str, Any]:
        return {
            **self.chunk.to_payload(),
            "score": round(self.score, 4),
            "match_modes": list(self.match_modes),
            "matched_terms": list(self.matched_terms),
            "lexical_overlap": self.lexical_overlap,
            "dense_similarity": round(self.dense_similarity, 4),
            "exact_query_hit": self.exact_query_hit,
        }


def _safe_text(value: Any) -> str:
    return normalize_text(str(value or ""))


def _safe_source_tier(value: Any) -> str:
    normalized = _safe_text(value).lower()
    return normalized if normalized in _VALID_SOURCE_TIERS else "media"


def _dedupe_strings(values: list[Any], limit: int = 12) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        normalized = _safe_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        items.append(normalized)
        if len(items) >= limit:
            break
    return items


def _split_text_windows(text: str, *, max_chars: int = 320) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    if len(normalized) <= max_chars:
        return [normalized]
    windows: list[str] = []
    cursor = 0
    while cursor < len(normalized):
        window = normalize_text(normalized[cursor : cursor + max_chars])
        if window:
            windows.append(window)
        cursor += max_chars - 60
    return _dedupe_strings(windows, limit=40)


def _document_time(value: Any) -> datetime | None:
    return value if isinstance(value, datetime) else None


def _join_values(value: Any, *, limit: int = 5) -> str:
    if isinstance(value, list):
        return "；".join(_dedupe_strings(value, limit=limit))
    if isinstance(value, dict):
        return "；".join(_dedupe_strings(value.values(), limit=limit))
    return _safe_text(value)


def _summary_payload_text(payload: Any, *, limit: int = 8) -> str:
    if isinstance(payload, dict):
        return "；".join(
            _dedupe_strings(
                [
                    payload.get("summary"),
                    payload.get("pipeline_summary"),
                    payload.get("mode"),
                    payload.get("generated_at"),
                    payload.get("sourceEntryCount"),
                    payload.get("directEvidenceCount"),
                    payload.get("officialEvidenceCount"),
                    payload.get("weakSectionCount"),
                    payload.get("quotaRiskSectionCount"),
                    payload.get("contradictionSectionCount"),
                    payload.get("highlightedSections"),
                    payload.get("summary_lines"),
                ],
                limit=limit,
            )
        )
    return _join_values(payload, limit=limit)


def _append_chunk(
    chunks: list[ResearchRetrievalIndexChunk],
    seen: set[str],
    *,
    document_id: str,
    document_type: str,
    title: str,
    text: str,
    field_key: str,
    label: str,
    source_tier: str = "media",
    source_url: str = "",
    parent_chunk_id: str = "",
    topic_id: str = "",
    topic_name: str = "",
    region: str = "",
    industry: str = "",
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    priority: int = 0,
    metadata: dict[str, Any] | None = None,
) -> None:
    normalized_text = _safe_text(text)
    if not document_id or not normalized_text:
        return
    dedupe_key = normalize_text("|".join([document_type, document_id, field_key, label, source_url, normalized_text]))
    if not dedupe_key or dedupe_key in seen:
        return
    seen.add(dedupe_key)
    chunk_id = f"chunk-{len(chunks) + 1}"
    chunks.append(
        ResearchRetrievalIndexChunk(
            chunk_id=chunk_id,
            document_id=document_id,
            document_type=document_type,
            title=_safe_text(title) or "未命名研究资产",
            text=normalized_text,
            field_key=_safe_text(field_key) or "content",
            label=_safe_text(label) or _safe_text(field_key) or "内容",
            source_tier=_safe_source_tier(source_tier),
            source_url=_safe_text(source_url),
            parent_chunk_id=_safe_text(parent_chunk_id),
            topic_id=_safe_text(topic_id),
            topic_name=_safe_text(topic_name),
            region=_safe_text(region),
            industry=_safe_text(industry),
            created_at=created_at,
            updated_at=updated_at,
            priority=max(0, int(priority or 0)),
            metadata=dict(metadata or {}),
        )
    )


def _append_report_chunks(
    chunks: list[ResearchRetrievalIndexChunk],
    seen: set[str],
    *,
    report_payload: dict[str, Any],
    document_id: str,
    document_type: str,
    title: str,
    topic_id: str = "",
    topic_name: str = "",
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    parent_chunk_id = ""
    for report_chunk in build_report_retrieval_chunks(report_payload):
        if report_chunk.field_key == "report_summary":
            parent_chunk_id = f"chunk-{len(chunks) + 1}"
        _append_chunk(
            chunks,
            seen,
            document_id=document_id,
            document_type=document_type,
            title=title,
            text=report_chunk.text,
            field_key=report_chunk.field_key,
            label=report_chunk.label,
            source_tier=report_chunk.source_tier,
            source_url=report_chunk.source_url,
            parent_chunk_id="" if report_chunk.field_key == "report_summary" else parent_chunk_id,
            topic_id=topic_id,
            topic_name=topic_name,
            created_at=created_at,
            updated_at=updated_at,
            priority=report_chunk.priority + (4 if document_type in {"research_report", "report_version"} else 0),
            metadata={
                **dict(metadata or {}),
                "section_title": report_chunk.section_title,
                "evidence_links": list(report_chunk.evidence_links),
            },
        )


def _append_knowledge_entry_chunks(
    chunks: list[ResearchRetrievalIndexChunk],
    seen: set[str],
    entry: KnowledgeEntry,
) -> None:
    payload = entry.metadata_payload if isinstance(entry.metadata_payload, dict) else {}
    report_payload = payload.get("report") if isinstance(payload.get("report"), dict) else None
    document_type = "research_report" if entry.source_domain == "research.report" or report_payload else "knowledge_entry"
    document_id = str(entry.id)
    title = normalize_text(entry.title or "") or "知识卡片"
    metadata = {
        "source_domain": entry.source_domain or "",
        "collection_name": entry.collection_name or "",
        "is_pinned": bool(entry.is_pinned),
        "is_focus_reference": bool(entry.is_focus_reference),
        "knowledge_entry_id": document_id,
    }
    _append_chunk(
        chunks,
        seen,
        document_id=document_id,
        document_type=document_type,
        title=title,
        text="；".join(part for part in [title, entry.content or ""] if normalize_text(part))[:900],
        field_key="entry_summary",
        label="知识卡片总览",
        source_tier="official" if document_type == "research_report" else "media",
        created_at=_document_time(entry.created_at),
        updated_at=_document_time(entry.updated_at),
        priority=12 if document_type == "research_report" else 8,
        metadata=metadata,
    )
    if report_payload:
        _append_report_chunks(
            chunks,
            seen,
            report_payload=report_payload,
            document_id=document_id,
            document_type="research_report",
            title=title,
            topic_id=_safe_text(payload.get("tracking_topic_id")),
            created_at=_document_time(entry.created_at),
            updated_at=_document_time(entry.updated_at),
            metadata=metadata,
        )
    elif entry.content:
        for window in _split_text_windows(entry.content):
            _append_chunk(
                chunks,
                seen,
                document_id=document_id,
                document_type="knowledge_entry",
                title=title,
                text=window,
                field_key="entry_content",
                label="知识卡片正文",
                created_at=_document_time(entry.created_at),
                updated_at=_document_time(entry.updated_at),
                priority=6,
                metadata=metadata,
            )


def _append_report_version_chunks(
    chunks: list[ResearchRetrievalIndexChunk],
    seen: set[str],
    version: ResearchReportVersion,
) -> None:
    topic = version.topic
    topic_id = str(topic.id) if topic is not None else str(version.topic_id)
    topic_name = topic.name if topic is not None else ""
    metadata = {
        "report_version_id": str(version.id),
        "knowledge_entry_id": str(version.knowledge_entry_id) if version.knowledge_entry_id else "",
        "source_count": int(version.source_count or 0),
        "evidence_density": version.evidence_density or "low",
        "source_quality": version.source_quality or "low",
        "new_targets": list(version.new_targets or []),
        "new_competitors": list(version.new_competitors or []),
    }
    _append_report_chunks(
        chunks,
        seen,
        report_payload=version.report_payload if isinstance(version.report_payload, dict) else {},
        document_id=str(version.id),
        document_type="report_version",
        title=version.report_title,
        topic_id=topic_id,
        topic_name=topic_name,
        created_at=_document_time(version.created_at),
        updated_at=_document_time(version.created_at),
        metadata=metadata,
    )


def _append_compare_snapshot_chunks(
    chunks: list[ResearchRetrievalIndexChunk],
    seen: set[str],
    snapshot: ResearchCompareSnapshot,
) -> None:
    topic = snapshot.tracking_topic
    metadata = snapshot.metadata_payload if isinstance(snapshot.metadata_payload, dict) else {}
    document_id = str(snapshot.id)
    title = snapshot.name or "Compare Snapshot"
    topic_id = str(snapshot.tracking_topic_id) if snapshot.tracking_topic_id else ""
    topic_name = topic.name if topic is not None else ""
    _append_chunk(
        chunks,
        seen,
        document_id=document_id,
        document_type="compare_snapshot",
        title=title,
        text="；".join(part for part in [snapshot.summary, snapshot.query, snapshot.region_filter, snapshot.industry_filter] if normalize_text(part)),
        field_key="snapshot_summary",
        label="对比快照总览",
        topic_id=topic_id,
        topic_name=topic_name,
        region=snapshot.region_filter or "",
        industry=snapshot.industry_filter or "",
        created_at=_document_time(snapshot.created_at),
        updated_at=_document_time(snapshot.updated_at),
        priority=10,
        metadata={
            "role_filter": snapshot.role_filter or "all",
            "report_version_id": str(snapshot.report_version_id) if snapshot.report_version_id else "",
            "snapshot_metadata_origin": _safe_text(metadata.get("snapshot_metadata_origin")),
        },
    )
    for field_key, label in [
        ("evidence_appendix_summary", "证据附录诊断"),
        ("section_diagnostics_summary", "章节证据诊断"),
        ("offline_evaluation_snapshot", "离线回归指标"),
    ]:
        diagnostic_text = _summary_payload_text(metadata.get(field_key), limit=10)
        _append_chunk(
            chunks,
            seen,
            document_id=document_id,
            document_type="compare_snapshot",
            title=title,
            text=diagnostic_text,
            field_key=field_key,
            label=label,
            source_tier="official" if field_key == "evidence_appendix_summary" else "aggregate",
            topic_id=topic_id,
            topic_name=topic_name,
            region=snapshot.region_filter or "",
            industry=snapshot.industry_filter or "",
            created_at=_document_time(snapshot.created_at),
            updated_at=_document_time(snapshot.updated_at),
            priority=8,
            metadata={
                "snapshot_metadata_origin": _safe_text(metadata.get("snapshot_metadata_origin")),
                "report_version_id": str(snapshot.report_version_id) if snapshot.report_version_id else "",
            },
        )
    for row in list(snapshot.rows_payload or [])[:120]:
        if not isinstance(row, dict):
            continue
        row_text = "；".join(
            part
            for part in [
                row.get("name"),
                row.get("role"),
                row.get("clue"),
                row.get("budgetSignal"),
                row.get("projectSignal"),
                row.get("strategySignal"),
                row.get("competitionSignal"),
                _join_values(row.get("targetDepartments"), limit=4),
                _join_values(row.get("publicContacts"), limit=4),
                _join_values(row.get("competitorHighlights"), limit=4),
                _join_values(row.get("partnerHighlights"), limit=4),
                _join_values(row.get("benchmarkCases"), limit=4),
                _join_values(row.get("candidateProfileCompanies"), limit=4),
                row.get("sourceEntryTitle"),
            ]
            if _safe_text(part)
        )
        source_tier = "official" if int(row.get("candidateProfileOfficialHitCount") or 0) > 0 else "media"
        _append_chunk(
            chunks,
            seen,
            document_id=document_id,
            document_type="compare_snapshot",
            title=title,
            text=row_text,
            field_key="snapshot_row",
            label=f"{_safe_text(row.get('role')) or '实体'}对比行",
            source_tier=source_tier,
            topic_id=topic_id,
            topic_name=topic_name,
            region=snapshot.region_filter or "",
            industry=snapshot.industry_filter or "",
            created_at=_document_time(snapshot.created_at),
            updated_at=_document_time(snapshot.updated_at),
            priority=9,
            metadata={
                "entity_name": _safe_text(row.get("name")),
                "role": _safe_text(row.get("role")),
                "source_entry_id": _safe_text(row.get("sourceEntryId")),
            },
        )


def _append_markdown_archive_chunks(
    chunks: list[ResearchRetrievalIndexChunk],
    seen: set[str],
    archive: ResearchMarkdownArchive,
) -> None:
    topic = archive.tracking_topic
    document_id = str(archive.id)
    title = archive.name or archive.filename or "Markdown Archive"
    topic_id = str(archive.tracking_topic_id) if archive.tracking_topic_id else ""
    topic_name = topic.name if topic is not None else ""
    metadata = archive.metadata_payload if isinstance(archive.metadata_payload, dict) else {}
    _append_chunk(
        chunks,
        seen,
        document_id=document_id,
        document_type="markdown_archive",
        title=title,
        text="；".join(part for part in [archive.summary, archive.query, archive.archive_kind] if normalize_text(part)),
        field_key="archive_summary",
        label="归档总览",
        topic_id=topic_id,
        topic_name=topic_name,
        region=archive.region_filter or "",
        industry=archive.industry_filter or "",
        created_at=_document_time(archive.created_at),
        updated_at=_document_time(archive.updated_at),
        priority=8,
        metadata={
            "archive_kind": archive.archive_kind or "compare_markdown",
            "filename": archive.filename,
            "compare_snapshot_id": str(archive.compare_snapshot_id) if archive.compare_snapshot_id else "",
            "report_version_id": str(archive.report_version_id) if archive.report_version_id else "",
            "changed_section_count": int(metadata.get("changed_section_count") or 0),
        },
    )
    for window in _split_text_windows(archive.content or "", max_chars=420)[:80]:
        _append_chunk(
            chunks,
            seen,
            document_id=document_id,
            document_type="markdown_archive",
            title=title,
            text=window,
            field_key="archive_content",
            label="归档正文",
            topic_id=topic_id,
            topic_name=topic_name,
            region=archive.region_filter or "",
            industry=archive.industry_filter or "",
            created_at=_document_time(archive.created_at),
            updated_at=_document_time(archive.updated_at),
            priority=5,
            metadata={"archive_kind": archive.archive_kind or "compare_markdown", "filename": archive.filename},
        )


def build_research_retrieval_index(
    db: Session,
    *,
    user_id: UUID | None = None,
    limit_per_source: int = 240,
) -> ResearchRetrievalIndex:
    settings = get_settings()
    resolved_user_id = user_id or settings.single_user_id
    capped_limit = max(1, min(int(limit_per_source or 240), 500))
    chunks: list[ResearchRetrievalIndexChunk] = []
    seen: set[str] = set()

    entries = list(
        db.scalars(
            select(KnowledgeEntry)
            .where(KnowledgeEntry.user_id == resolved_user_id)
            .order_by(desc(KnowledgeEntry.updated_at), desc(KnowledgeEntry.created_at))
            .limit(capped_limit)
        )
    )
    for entry in entries:
        _append_knowledge_entry_chunks(chunks, seen, entry)

    versions = list(
        db.scalars(
            select(ResearchReportVersion)
            .join(ResearchTrackingTopic, ResearchTrackingTopic.id == ResearchReportVersion.topic_id)
            .where(ResearchTrackingTopic.user_id == resolved_user_id)
            .order_by(desc(ResearchReportVersion.created_at))
            .limit(capped_limit)
        )
    )
    for version in versions:
        _append_report_version_chunks(chunks, seen, version)

    snapshots = list(
        db.scalars(
            select(ResearchCompareSnapshot)
            .where(ResearchCompareSnapshot.user_id == resolved_user_id)
            .order_by(desc(ResearchCompareSnapshot.updated_at), desc(ResearchCompareSnapshot.created_at))
            .limit(capped_limit)
        )
    )
    for snapshot in snapshots:
        _append_compare_snapshot_chunks(chunks, seen, snapshot)

    archives = list(
        db.scalars(
            select(ResearchMarkdownArchive)
            .where(ResearchMarkdownArchive.user_id == resolved_user_id)
            .order_by(desc(ResearchMarkdownArchive.updated_at), desc(ResearchMarkdownArchive.created_at))
            .limit(capped_limit)
        )
    )
    for archive in archives:
        _append_markdown_archive_chunks(chunks, seen, archive)

    source_counts = dict(Counter(chunk.document_type for chunk in chunks))
    return ResearchRetrievalIndex(
        chunks=chunks,
        built_at=datetime.now(timezone.utc),
        source_counts=source_counts,
    )


def search_research_retrieval_index(
    index: ResearchRetrievalIndex,
    query: str,
    *,
    limit: int = 10,
    document_types: set[str] | None = None,
    topic_id: str | None = None,
    source_tiers: set[str] | None = None,
) -> list[ResearchRetrievalIndexHit]:
    normalized_query = normalize_text(query)
    if not normalized_query or not index.chunks:
        return []

    normalized_topic_id = _safe_text(topic_id)
    normalized_document_types = {_safe_text(item) for item in (document_types or set()) if _safe_text(item)}
    normalized_source_tiers = {_safe_source_tier(item) for item in (source_tiers or set()) if _safe_text(item)}
    filtered_chunks = [
        chunk
        for chunk in index.chunks
        if (not normalized_document_types or chunk.document_type in normalized_document_types)
        and (not normalized_topic_id or chunk.topic_id == normalized_topic_id)
        and (not normalized_source_tiers or chunk.source_tier in normalized_source_tiers)
    ]
    if not filtered_chunks:
        return []

    by_key = {chunk.chunk_id: chunk for chunk in filtered_chunks}
    matches = retrieve_text_matches(
        [
            TextRetrievalCandidate(
                key=chunk.chunk_id,
                text=chunk.search_text(),
                source_tier=chunk.source_tier,
                priority=chunk.priority,
            )
            for chunk in filtered_chunks
        ],
        normalized_query,
        limit=max(1, min(limit * 4, 80)),
    )

    hits: list[ResearchRetrievalIndexHit] = []
    for match in matches:
        chunk = by_key.get(match.key)
        if chunk is None:
            continue
        hits.append(
            ResearchRetrievalIndexHit(
                chunk=chunk,
                score=match.score,
                match_modes=match.match_modes,
                matched_terms=match.matched_terms,
                lexical_overlap=match.lexical_overlap,
                dense_similarity=match.dense_similarity,
                exact_query_hit=match.exact_query_hit,
            )
        )
        if len(hits) >= max(1, min(limit, 40)):
            break
    return hits
