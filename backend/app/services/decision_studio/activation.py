from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.decision_studio_entities import DecisionNotebook, DecisionSource, DecisionSourceRevision
from app.models.entities import KnowledgeEntry
from app.models.research_entities import ResearchJob
from app.services.decision_studio.notebooks import create_notebook, create_source_revision, serialize_notebook
from app.services.decision_studio.parsing import parse_document
from app.services.decision_studio.validation import record_validation_run, serialize_validation_run


@dataclass(frozen=True)
class ActivationCandidate:
    source_type: str
    source_record_id: UUID
    title: str
    content: str
    source_uri: str
    source_kind: str
    labels: tuple[str, ...]
    content_hash: str
    state: str
    existing_source_id: UUID | None = None
    duplicate_of: str = ""


def _content_hash(content: str) -> str:
    parsed = parse_document(content.encode("utf-8"), file_name="activation.txt", mime_type="text/plain")
    return hashlib.sha256(parsed.text.encode("utf-8")).hexdigest()


def _report_text(job: ResearchJob) -> str:
    payload = job.report_payload if isinstance(job.report_payload, dict) else {}
    for key in ("markdown", "report_markdown", "content", "full_text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) if payload else ""


def _candidate_payload(candidate: ActivationCandidate) -> dict[str, Any]:
    return {
        "source_type": candidate.source_type,
        "source_record_id": str(candidate.source_record_id),
        "title": candidate.title,
        "source_uri": candidate.source_uri,
        "source_kind": candidate.source_kind,
        "labels": list(candidate.labels),
        "content_hash": candidate.content_hash,
        "content_chars": len(candidate.content),
        "excerpt": candidate.content[:180],
        "state": candidate.state,
        "existing_source_id": str(candidate.existing_source_id) if candidate.existing_source_id else None,
        "duplicate_of": candidate.duplicate_of or None,
    }


def _existing_sources(db: Session, notebook_id: UUID | None) -> dict[str, tuple[DecisionSource, str]]:
    if notebook_id is None:
        return {}
    sources = db.scalars(select(DecisionSource).where(DecisionSource.notebook_id == notebook_id)).all()
    result: dict[str, tuple[DecisionSource, str]] = {}
    for source in sources:
        revision = db.get(DecisionSourceRevision, source.current_revision_id) if source.current_revision_id else None
        result[source.source_uri] = (source, revision.content_hash if revision else "")
    return result


def collect_activation_candidates(
    db: Session,
    *,
    user_id: UUID,
    notebook_id: UUID | None = None,
    collection_name: str | None = None,
    knowledge_entry_ids: list[UUID] | None = None,
    research_job_ids: list[UUID] | None = None,
    include_knowledge_entries: bool = True,
    include_research_jobs: bool = True,
    limit: int = 500,
) -> list[ActivationCandidate]:
    capped_limit = max(1, min(int(limit), 2000))
    raw: list[tuple[str, UUID, str, str, str, str, tuple[str, ...]]] = []
    if include_knowledge_entries and (knowledge_entry_ids is None or knowledge_entry_ids):
        query = select(KnowledgeEntry).where(KnowledgeEntry.user_id == user_id)
        if collection_name:
            query = query.where(KnowledgeEntry.collection_name == collection_name)
        if knowledge_entry_ids is not None:
            query = query.where(KnowledgeEntry.id.in_(knowledge_entry_ids))
        entries = db.scalars(query.order_by(KnowledgeEntry.updated_at.desc()).limit(capped_limit)).all()
        for entry in entries:
            content = str(entry.content or "").strip()
            if not content:
                continue
            labels = ["activated", "knowledge-entry"]
            if entry.collection_name:
                labels.append(f"collection:{entry.collection_name}"[:80])
            if entry.source_domain:
                labels.append(f"domain:{entry.source_domain}"[:80])
            raw.append(
                (
                    "knowledge_entry",
                    entry.id,
                    entry.title or "知识条目",
                    content,
                    f"anti-fomo://knowledge-entry/{entry.id}",
                    "knowledge_entry",
                    tuple(labels),
                )
            )
    remaining = max(0, capped_limit - len(raw))
    if include_research_jobs and remaining and (research_job_ids is None or research_job_ids):
        query = (
            select(ResearchJob)
            .where(ResearchJob.user_id == user_id)
            .where(ResearchJob.status == "succeeded")
            .where(ResearchJob.report_payload.is_not(None))
        )
        if research_job_ids is not None:
            query = query.where(ResearchJob.id.in_(research_job_ids))
        jobs = db.scalars(query.order_by(ResearchJob.finished_at.desc(), ResearchJob.updated_at.desc()).limit(remaining)).all()
        for job in jobs:
            content = _report_text(job)
            if not content:
                continue
            raw.append(
                (
                    "research_job",
                    job.id,
                    f"研报：{job.keyword}",
                    content,
                    f"anti-fomo://research-job/{job.id}",
                    "research_report",
                    ("activated", "research-report", f"mode:{job.research_mode}"[:80]),
                )
            )

    existing = _existing_sources(db, notebook_id)
    seen_hashes: dict[str, str] = {}
    candidates: list[ActivationCandidate] = []
    for source_type, record_id, title, content, source_uri, source_kind, labels in raw[:capped_limit]:
        digest = _content_hash(content)
        duplicate_of = seen_hashes.get(digest, "")
        existing_row = existing.get(source_uri)
        if duplicate_of:
            state = "duplicate_input"
            existing_source_id = None
        elif existing_row and existing_row[1] == digest:
            state = "existing_unchanged"
            existing_source_id = existing_row[0].id
        elif existing_row:
            state = "existing_changed"
            existing_source_id = existing_row[0].id
        else:
            state = "new"
            existing_source_id = None
        seen_hashes.setdefault(digest, source_uri)
        candidates.append(
            ActivationCandidate(
                source_type=source_type,
                source_record_id=record_id,
                title=title.strip()[:240],
                content=content,
                source_uri=source_uri,
                source_kind=source_kind,
                labels=labels,
                content_hash=digest,
                state=state,
                existing_source_id=existing_source_id,
                duplicate_of=duplicate_of,
            )
        )
    return candidates


def preview_data_activation(db: Session, *, user_id: UUID, **selection: Any) -> dict[str, Any]:
    notebook_id = selection.get("notebook_id")
    if notebook_id is not None:
        notebook = db.get(DecisionNotebook, notebook_id)
        if notebook is None or notebook.user_id != user_id:
            raise ValueError("Activation target Notebook does not belong to the current user.")
    candidates = collect_activation_candidates(db, user_id=user_id, **selection)
    states: dict[str, int] = {}
    source_types: dict[str, int] = {}
    for candidate in candidates:
        states[candidate.state] = states.get(candidate.state, 0) + 1
        source_types[candidate.source_type] = source_types.get(candidate.source_type, 0) + 1
    return {
        "status": "ready" if candidates else "blocked",
        "candidate_count": len(candidates),
        "state_counts": states,
        "source_type_counts": source_types,
        "notebook_id": str(notebook_id) if notebook_id else None,
        "candidates": [_candidate_payload(candidate) for candidate in candidates],
        "warnings": [] if candidates else ["没有找到可激活的知识条目或已完成研报。"],
    }


def run_data_activation(
    db: Session,
    *,
    user_id: UUID,
    notebook_name: str,
    notebook_id: UUID | None = None,
    **selection: Any,
) -> dict[str, Any]:
    if notebook_id is not None:
        notebook = db.get(DecisionNotebook, notebook_id)
        if notebook is None or notebook.user_id != user_id:
            raise ValueError("Activation target Notebook does not belong to the current user.")
    else:
        initial = collect_activation_candidates(db, user_id=user_id, notebook_id=None, **selection)
        if not initial:
            raise ValueError("No knowledge entries or completed reports are available for activation.")
        notebook = create_notebook(
            db,
            user_id=user_id,
            name=notebook_name,
            description="由现有知识库与已完成研报激活，保留本地来源血缘。",
        )
    candidates = collect_activation_candidates(db, user_id=user_id, notebook_id=notebook.id, **selection)
    created = 0
    updated = 0
    unchanged = 0
    failed = 0
    provenance = 0
    results: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate.state in {"duplicate_input", "existing_unchanged"}:
            unchanged += 1
            provenance += int(bool(candidate.source_uri))
            results.append({**_candidate_payload(candidate), "result": "unchanged"})
            continue
        try:
            source, revision, parsed, _stale = create_source_revision(
                db,
                notebook_id=notebook.id,
                source_id=candidate.existing_source_id,
                title=candidate.title,
                data=candidate.content.encode("utf-8"),
                file_name=f"{candidate.source_type}-{candidate.source_record_id}.txt",
                mime_type="text/plain",
                source_kind=candidate.source_kind,
                source_uri=candidate.source_uri,
                labels=list(candidate.labels),
            )
            if candidate.state == "existing_changed":
                updated += 1
                result = "updated"
            else:
                created += 1
                result = "created"
            provenance += int(bool(source.source_uri))
            results.append(
                {
                    **_candidate_payload(candidate),
                    "result": result,
                    "decision_source_id": str(source.id),
                    "revision_id": str(revision.id),
                    "parser": parsed.parser_name,
                }
            )
        except Exception as exc:
            db.rollback()
            failed += 1
            results.append({**_candidate_payload(candidate), "result": "failed", "error": str(exc)})
    metrics = {
        "candidate_count": len(candidates),
        "created_source_count": created,
        "updated_source_count": updated,
        "unchanged_source_count": unchanged,
        "failed_source_count": failed,
        "provenance_source_count": provenance,
    }
    validation_run = record_validation_run(
        db,
        user_id=user_id,
        suite_key="real_data_activation",
        metrics=metrics,
        evidence={"notebook_id": str(notebook.id), "source_record_ids": [str(row.source_record_id) for row in candidates]},
    )
    return {
        "status": validation_run.status,
        "notebook": serialize_notebook(db, notebook),
        "metrics": metrics,
        "results": results,
        "validation_run": serialize_validation_run(validation_run),
    }
