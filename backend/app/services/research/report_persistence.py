from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import KnowledgeEntry
from app.services.knowledge_service import create_or_get_standalone_knowledge_entry


settings = get_settings()


def find_existing_research_entry_by_keyword(db: Session, *, keyword: str) -> KnowledgeEntry | None:
    normalized_keyword = (keyword or "").strip()
    if not normalized_keyword:
        return None
    entries = db.scalars(
        select(KnowledgeEntry)
        .where(KnowledgeEntry.user_id == settings.single_user_id)
        .where(KnowledgeEntry.source_domain == "research.report")
        .order_by(KnowledgeEntry.updated_at.desc(), KnowledgeEntry.created_at.desc())
    ).all()
    for entry in entries:
        payload = entry.metadata_payload if isinstance(entry.metadata_payload, dict) else {}
        report_payload = payload.get("report") if isinstance(payload.get("report"), dict) else {}
        if str(report_payload.get("keyword") or "").strip() == normalized_keyword:
            return entry
    return None


def upsert_research_knowledge_entry(
    db: Session,
    *,
    keyword: str,
    title: str,
    content: str,
    collection_name: str | None,
    is_focus_reference: bool,
    metadata_payload: dict,
) -> KnowledgeEntry:
    existing_entry = find_existing_research_entry_by_keyword(db, keyword=keyword)
    if existing_entry is not None:
        existing_entry.title = title
        existing_entry.content = content
        existing_entry.source_domain = "research.report"
        if collection_name:
            existing_entry.collection_name = collection_name
        if is_focus_reference:
            existing_entry.is_focus_reference = True
        existing_entry.metadata_payload = metadata_payload
        db.add(existing_entry)
        db.commit()
        db.refresh(existing_entry)
        return existing_entry

    entry, created = create_or_get_standalone_knowledge_entry(
        db,
        user_id=settings.single_user_id,
        title=title,
        content=content,
        source_domain="research.report",
        collection_name=collection_name,
        is_focus_reference=is_focus_reference,
        metadata_payload=metadata_payload,
    )
    if not created:
        if collection_name and not entry.collection_name:
            entry.collection_name = collection_name
        if is_focus_reference and not entry.is_focus_reference:
            entry.is_focus_reference = True
        entry.metadata_payload = metadata_payload
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
