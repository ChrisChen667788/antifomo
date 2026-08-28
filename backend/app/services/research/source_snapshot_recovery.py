from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

from sqlalchemy import desc, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.research_entities import ResearchJob
from app.schemas.research import ResearchSourceOut
from app.services.content_extractor import normalize_text
from app.services.research.report_storage_runtime import report_sources_to_documents
from app.services.research.source_documents import SourceDocument


EVIDENCE_SNAPSHOT_CANDIDATE_STATUSES = ("succeeded", "needs_evidence")


@dataclass(frozen=True, slots=True)
class RecentEvidenceSnapshot:
    job_id: str
    finished_at: datetime
    age_hours: int
    sources: tuple[SourceDocument, ...]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def build_recent_evidence_snapshot(
    *,
    job_id: object,
    job_keyword: str,
    job_research_focus: str | None,
    finished_at: datetime | None,
    report_payload: dict[str, Any] | None,
    keyword: str,
    research_focus: str | None,
    max_age_hours: int,
    now: datetime | None = None,
) -> RecentEvidenceSnapshot | None:
    if (
        normalize_text(job_keyword).casefold() != normalize_text(keyword).casefold()
        or normalize_text(job_research_focus or "").casefold() != normalize_text(research_focus or "").casefold()
        or finished_at is None
        or not isinstance(report_payload, dict)
    ):
        return None
    resolved_now = _as_utc(now or datetime.now(timezone.utc))
    resolved_finished_at = _as_utc(finished_at)
    age_hours = max(0, int((resolved_now - resolved_finished_at).total_seconds() // 3600))
    if resolved_finished_at < resolved_now - timedelta(hours=max(1, int(max_age_hours))):
        return None
    gate = report_payload.get("research_evidence_gate")
    if not isinstance(gate, dict) or not gate.get("passed") or not gate.get("formal_report_allowed"):
        return None
    if (
        int(gate.get("accepted_source_count") or 0) < 8
        or int(gate.get("official_source_count") or 0) < 3
        or int(gate.get("unique_domain_count") or 0) < 5
    ):
        return None
    source_rows = report_payload.get("sources")
    if not isinstance(source_rows, list):
        return None
    parsed_sources: list[ResearchSourceOut] = []
    for row in source_rows:
        if not isinstance(row, dict):
            continue
        try:
            parsed_sources.append(ResearchSourceOut.model_validate(row))
        except Exception:
            continue
    documents = report_sources_to_documents(parsed_sources)
    for document in documents:
        document.source_origin = "snapshot_cache"
    official_count = sum(document.source_tier == "official" for document in documents)
    unique_domain_count = len(
        {normalize_text(document.domain or "").casefold() for document in documents if normalize_text(document.domain or "")}
    )
    if len(documents) < 8 or official_count < 3 or unique_domain_count < 5:
        return None
    return RecentEvidenceSnapshot(
        job_id=str(job_id),
        finished_at=resolved_finished_at,
        age_hours=age_hours,
        sources=tuple(documents),
    )


def load_recent_evidence_snapshot(
    *,
    keyword: str,
    research_focus: str | None,
    max_age_hours: int | None = None,
    limit: int = 32,
    excluded_job_ids: tuple[str, ...] = (),
) -> RecentEvidenceSnapshot | None:
    settings = get_settings()
    if not settings.research_snapshot_recovery_enabled:
        return None
    resolved_max_age_hours = max(1, int(max_age_hours or settings.research_snapshot_recovery_max_age_hours))
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=resolved_max_age_hours)
    with SessionLocal() as db:
        jobs = db.scalars(
            select(ResearchJob)
            .where(ResearchJob.user_id == settings.single_user_id)
            .where(ResearchJob.status.in_(EVIDENCE_SNAPSHOT_CANDIDATE_STATUSES))
            .where(ResearchJob.finished_at.is_not(None))
            .where(ResearchJob.finished_at >= cutoff)
            .order_by(desc(ResearchJob.finished_at))
            .limit(max(1, int(limit)))
        ).all()
    excluded = {normalize_text(str(job_id)).casefold() for job_id in excluded_job_ids if normalize_text(str(job_id))}
    for job in jobs:
        if normalize_text(str(job.id)).casefold() in excluded:
            continue
        snapshot = build_recent_evidence_snapshot(
            job_id=job.id,
            job_keyword=job.keyword,
            job_research_focus=job.research_focus,
            finished_at=job.finished_at,
            report_payload=job.report_payload,
            keyword=keyword,
            research_focus=research_focus,
            max_age_hours=resolved_max_age_hours,
            now=now,
        )
        if snapshot is not None:
            return snapshot
    return None


def load_evidence_snapshot_by_job_id(
    *,
    job_id: str,
    keyword: str,
    research_focus: str | None,
    max_age_hours: int = 168,
) -> RecentEvidenceSnapshot | None:
    try:
        parsed_job_id = uuid.UUID(str(job_id))
    except ValueError:
        return None
    settings = get_settings()
    with SessionLocal() as db:
        job = db.scalar(
            select(ResearchJob)
            .where(ResearchJob.id == parsed_job_id)
            .where(ResearchJob.user_id == settings.single_user_id)
        )
        if job is None:
            return None
        report_payload = job.report_payload
        snapshot_at = job.finished_at or job.updated_at
        if (
            normalize_text(job.keyword).casefold() != normalize_text(keyword).casefold()
            or normalize_text(job.research_focus or "").casefold()
            != normalize_text(research_focus or "").casefold()
            or snapshot_at is None
            or not isinstance(report_payload, dict)
        ):
            return None
        now = datetime.now(timezone.utc)
        resolved_snapshot_at = _as_utc(snapshot_at)
        age_hours = max(0, int((now - resolved_snapshot_at).total_seconds() // 3600))
        if resolved_snapshot_at < now - timedelta(hours=max(1, int(max_age_hours))):
            return None
        source_rows = report_payload.get("sources")
        if not isinstance(source_rows, list):
            return None
        accepted_urls = {
            normalize_text(str(row.get("url") or ""))
            for row in list(report_payload.get("research_source_admissions") or [])
            if isinstance(row, dict) and row.get("decision") == "accepted"
        }
        parsed_sources: list[ResearchSourceOut] = []
        for row in source_rows:
            if not isinstance(row, dict):
                continue
            try:
                source = ResearchSourceOut.model_validate(row)
            except Exception:
                continue
            if accepted_urls and normalize_text(source.url) not in accepted_urls:
                continue
            parsed_sources.append(source)
        documents = report_sources_to_documents(parsed_sources)
        for document in documents:
            document.source_origin = "snapshot_cache"
        if not documents:
            return None
        return RecentEvidenceSnapshot(
            job_id=str(job.id),
            finished_at=resolved_snapshot_at,
            age_hours=age_hours,
            sources=tuple(documents),
        )
