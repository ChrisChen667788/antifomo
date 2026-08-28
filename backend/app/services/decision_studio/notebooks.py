from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.decision_studio_entities import (
    DecisionArtifact,
    DecisionNotebook,
    DecisionPassage,
    DecisionSource,
    DecisionSourceRevision,
)
from app.services.decision_studio.parsing import ParsedDocument, parse_document


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return normalized.isoformat().replace("+00:00", "Z")


def create_notebook(
    db: Session,
    *,
    user_id: UUID,
    name: str,
    description: str = "",
    space_id: UUID | None = None,
) -> DecisionNotebook:
    notebook = DecisionNotebook(
        user_id=user_id,
        space_id=space_id,
        name=name.strip()[:160],
        description=description.strip(),
    )
    db.add(notebook)
    db.commit()
    db.refresh(notebook)
    return notebook


def get_notebook(db: Session, notebook_id: UUID) -> DecisionNotebook | None:
    return db.get(DecisionNotebook, notebook_id)


def list_notebooks(db: Session, *, user_id: UUID | None = None, space_ids: list[UUID] | None = None) -> list[DecisionNotebook]:
    query = select(DecisionNotebook).order_by(DecisionNotebook.updated_at.desc())
    if user_id is not None and space_ids is None:
        query = query.where(DecisionNotebook.user_id == user_id)
    elif user_id is not None and space_ids is not None:
        query = query.where((DecisionNotebook.user_id == user_id) | (DecisionNotebook.space_id.in_(space_ids)))
    elif space_ids is not None:
        if not space_ids:
            return []
        query = query.where(DecisionNotebook.space_id.in_(space_ids))
    return list(db.scalars(query).all())


def serialize_notebook(db: Session, notebook: DecisionNotebook) -> dict[str, object]:
    source_count = db.scalar(
        select(func.count(DecisionSource.id)).where(DecisionSource.notebook_id == notebook.id)
    ) or 0
    artifact_count = db.scalar(
        select(func.count(DecisionArtifact.id)).where(DecisionArtifact.notebook_id == notebook.id)
    ) or 0
    stale_artifact_count = db.scalar(
        select(func.count(DecisionArtifact.id))
        .where(DecisionArtifact.notebook_id == notebook.id)
        .where(DecisionArtifact.stale.is_(True))
    ) or 0
    return {
        "id": str(notebook.id),
        "user_id": str(notebook.user_id),
        "space_id": str(notebook.space_id) if notebook.space_id else None,
        "name": notebook.name,
        "description": notebook.description,
        "status": notebook.status,
        "source_count": source_count,
        "artifact_count": artifact_count,
        "stale_artifact_count": stale_artifact_count,
        "created_at": _iso(notebook.created_at),
        "updated_at": _iso(notebook.updated_at),
    }


def _mark_dependent_artifacts_stale(db: Session, *, notebook_id: UUID, revision_id: UUID) -> int:
    revision_key = str(revision_id)
    changed = 0
    artifacts = db.scalars(
        select(DecisionArtifact).where(DecisionArtifact.notebook_id == notebook_id)
    ).all()
    for artifact in artifacts:
        if revision_key in set(str(value) for value in (artifact.source_revision_ids or [])) and not artifact.stale:
            artifact.stale = True
            artifact.status = "stale"
            changed += 1
    return changed


def _serialize_revision(revision: DecisionSourceRevision, *, passage_count: int) -> dict[str, object]:
    return {
        "id": str(revision.id),
        "revision_number": revision.revision_number,
        "content_hash": revision.content_hash,
        "parser_name": revision.parser_name,
        "parser_version": revision.parser_version,
        "metadata": revision.metadata_payload or {},
        "passage_count": passage_count,
        "created_at": _iso(revision.created_at),
    }


def serialize_source(db: Session, source: DecisionSource, *, include_revisions: bool = False) -> dict[str, object]:
    current_revision = db.get(DecisionSourceRevision, source.current_revision_id) if source.current_revision_id else None
    current_passage_count = 0
    if current_revision is not None:
        current_passage_count = db.scalar(
            select(func.count(DecisionPassage.id)).where(DecisionPassage.revision_id == current_revision.id)
        ) or 0
    payload: dict[str, object] = {
        "id": str(source.id),
        "notebook_id": str(source.notebook_id),
        "title": source.title,
        "source_kind": source.source_kind,
        "source_uri": source.source_uri,
        "mime_type": source.mime_type,
        "labels": list(source.labels or []),
        "admission_status": source.admission_status,
        "current_revision_id": str(source.current_revision_id) if source.current_revision_id else None,
        "current_revision_number": current_revision.revision_number if current_revision else 0,
        "current_content_hash": current_revision.content_hash if current_revision else "",
        "current_parser": current_revision.parser_name if current_revision else "",
        "current_passage_count": current_passage_count,
        "owner_label": source.owner_label,
        "trust_status": source.trust_status,
        "verified_at": _iso(source.verified_at),
        "expires_at": _iso(source.expires_at),
        "created_at": _iso(source.created_at),
        "updated_at": _iso(source.updated_at),
    }
    if include_revisions:
        revisions = db.scalars(
            select(DecisionSourceRevision)
            .where(DecisionSourceRevision.source_id == source.id)
            .order_by(DecisionSourceRevision.revision_number.desc())
        ).all()
        payload["revisions"] = [
            _serialize_revision(
                revision,
                passage_count=db.scalar(
                    select(func.count(DecisionPassage.id)).where(DecisionPassage.revision_id == revision.id)
                )
                or 0,
            )
            for revision in revisions
        ]
    return payload


def list_sources(db: Session, *, notebook_id: UUID) -> list[DecisionSource]:
    return list(
        db.scalars(
            select(DecisionSource)
            .where(DecisionSource.notebook_id == notebook_id)
            .order_by(DecisionSource.updated_at.desc())
        ).all()
    )


def create_source_revision(
    db: Session,
    *,
    notebook_id: UUID,
    title: str,
    data: bytes,
    file_name: str,
    mime_type: str,
    source_kind: str = "text",
    source_uri: str = "",
    labels: list[str] | None = None,
    source_id: UUID | None = None,
    prefer_docling: bool = False,
) -> tuple[DecisionSource, DecisionSourceRevision, ParsedDocument, int]:
    source = db.get(DecisionSource, source_id) if source_id else None
    if source is not None and source.notebook_id != notebook_id:
        raise ValueError("Source does not belong to the selected notebook.")
    if source is None:
        source = DecisionSource(
            notebook_id=notebook_id,
            title=title.strip()[:240],
            source_kind=source_kind.strip()[:40] or "text",
            source_uri=source_uri.strip(),
            mime_type=mime_type.strip()[:120] or "application/octet-stream",
            labels=list(dict.fromkeys(label.strip() for label in labels or [] if label.strip()))[:20],
        )
        db.add(source)
        db.flush()
    parsed = parse_document(data, file_name=file_name, mime_type=mime_type, prefer_docling=prefer_docling)
    if not parsed.passages:
        raise ValueError("The source produced no extractable passages.")
    content_hash = hashlib.sha256(parsed.text.encode("utf-8")).hexdigest()
    latest = db.scalar(
        select(DecisionSourceRevision)
        .where(DecisionSourceRevision.source_id == source.id)
        .order_by(DecisionSourceRevision.revision_number.desc())
        .limit(1)
    )
    if latest is not None and latest.content_hash == content_hash:
        return source, latest, parsed, 0
    stale_count = _mark_dependent_artifacts_stale(
        db,
        notebook_id=notebook_id,
        revision_id=latest.id,
    ) if latest is not None else 0
    revision = DecisionSourceRevision(
        source_id=source.id,
        revision_number=(latest.revision_number + 1) if latest else 1,
        content_hash=content_hash,
        parser_name=parsed.parser_name,
        parser_version=parsed.parser_version,
        raw_text=parsed.text,
        metadata_payload={
            "file_name": file_name,
            "mime_type": mime_type,
            "warnings": list(parsed.warnings),
        },
    )
    db.add(revision)
    db.flush()
    for passage in parsed.passages:
        db.add(
            DecisionPassage(
                revision_id=revision.id,
                sequence=passage.sequence,
                page_number=passage.page_number,
                paragraph_number=passage.paragraph_number,
                start_seconds=passage.start_seconds,
                end_seconds=passage.end_seconds,
                text=passage.text,
                locator_payload=passage.locator,
            )
        )
    source.current_revision_id = revision.id
    source.title = title.strip()[:240] or source.title
    source.source_uri = source_uri.strip() or source.source_uri
    source.mime_type = mime_type.strip()[:120] or source.mime_type
    db.commit()
    db.refresh(source)
    db.refresh(revision)
    return source, revision, parsed, stale_count


def get_passage_payload(db: Session, passage_id: UUID) -> dict[str, object] | None:
    row = db.execute(
        select(DecisionPassage, DecisionSourceRevision, DecisionSource)
        .join(DecisionSourceRevision, DecisionSourceRevision.id == DecisionPassage.revision_id)
        .join(DecisionSource, DecisionSource.id == DecisionSourceRevision.source_id)
        .where(DecisionPassage.id == passage_id)
    ).first()
    if row is None:
        return None
    passage, revision, source = row
    return {
        "id": str(passage.id),
        "notebook_id": str(source.notebook_id),
        "source_id": str(source.id),
        "source_title": source.title,
        "source_uri": source.source_uri,
        "revision_id": str(revision.id),
        "revision_number": revision.revision_number,
        "content_hash": revision.content_hash,
        "text": passage.text,
        "sequence": passage.sequence,
        "locator": {
            **dict(passage.locator_payload or {}),
            "page": passage.page_number,
            "paragraph": passage.paragraph_number,
            "start_seconds": passage.start_seconds,
            "end_seconds": passage.end_seconds,
        },
        "embedding_model": passage.embedding_model,
    }


def update_source_trust(
    db: Session,
    *,
    source: DecisionSource,
    trust_status: str,
    owner_label: str,
    expires_at: datetime | None,
) -> DecisionSource:
    source.trust_status = trust_status
    source.owner_label = owner_label.strip()[:160]
    source.verified_at = datetime.now(UTC) if trust_status == "verified" else None
    source.expires_at = expires_at
    if trust_status in {"revoked", "expired"} and source.current_revision_id:
        _mark_dependent_artifacts_stale(
            db,
            notebook_id=source.notebook_id,
            revision_id=source.current_revision_id,
        )
    db.commit()
    db.refresh(source)
    return source
