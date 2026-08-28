from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import re
from collections import defaultdict
from threading import RLock
import time
from typing import Any
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import KnowledgeEntry
from app.models.research_entities import ResearchReportVersion, ResearchWatchlist, ResearchWatchlistChangeEvent
from app.schemas.research import ResearchActionCardOut, ResearchReportDocument, ResearchReportResponse
from app.services.content_extractor import normalize_text
from app.services.knowledge_intelligence.commercial_text import (
    _clean_commercial_phrase,
    _clean_commercial_rows,
)
from app.services.knowledge_intelligence.entity_quality import (
    _best_graph_canonical_name,
    _canonical_name_from_evidence_links,
    _canonicalize_account_name,
    _clean_entity_name,
    _entity_canonical_name,
    _entity_evidence_links,
    _entity_name,
    _entity_reasoning,
    _entity_role,
    _entity_score,
    _extract_name_from_title,
    _graph_entities_for_role,
    _graph_entity_quality,
    _is_low_signal_entity_name,
    _looks_like_named_account_placeholder,
    _looks_like_org_name,
    _looks_like_sentence_fragment_entity_name,
    _slugify,
    _unique_strings,
)
from app.services.knowledge_intelligence.report_metadata import (
    _canonicalize_report_for_knowledge_backfill,
    _opportunity_identity_key,
    apply_review_queue_resolutions,
    build_report_knowledge_intelligence,
    build_research_report_metadata,
    extract_commercial_intelligence,
    update_review_queue_resolution,
)


settings = get_settings()

_BACKFILL_STAGE_ENTRIES = "entries"
_BACKFILL_STAGE_VERSIONS = "versions"
_BACKFILL_STAGE_DONE = "done"
_BACKFILL_CHECKPOINT_SCHEMA_VERSION = 1
_COMMERCIAL_AGGREGATE_CACHE_TTL_SECONDS = 60.0
_COMMERCIAL_AGGREGATE_CACHE_MAX_ENTRIES = 16
_COMMERCIAL_AGGREGATE_CACHE_LOCK = RLock()
_COMMERCIAL_AGGREGATE_CACHE: dict[tuple[Any, ...], tuple[float, dict[str, dict[str, Any]]]] = {}
_COMMERCIAL_DASHBOARD_CACHE: dict[tuple[Any, ...], tuple[float, dict[str, Any]]] = {}


def _commercial_cache_signature(db: Session) -> tuple[Any, ...]:
    report_count, report_max_updated, report_max_created = db.execute(
        select(
            func.count(KnowledgeEntry.id),
            func.max(KnowledgeEntry.updated_at),
            func.max(KnowledgeEntry.created_at),
        )
        .where(KnowledgeEntry.user_id == settings.single_user_id)
        .where(KnowledgeEntry.source_domain == "research.report")
    ).one()
    watchlist_count, watchlist_max_updated = db.execute(
        select(func.count(ResearchWatchlist.id), func.max(ResearchWatchlist.updated_at)).where(
            ResearchWatchlist.user_id == settings.single_user_id
        )
    ).one()
    event_count, event_max_created = db.execute(
        select(func.count(ResearchWatchlistChangeEvent.id), func.max(ResearchWatchlistChangeEvent.created_at))
        .join(ResearchWatchlist, ResearchWatchlist.id == ResearchWatchlistChangeEvent.watchlist_id)
        .where(ResearchWatchlist.user_id == settings.single_user_id)
    ).one()
    return (
        int(report_count or 0),
        report_max_updated,
        report_max_created,
        int(watchlist_count or 0),
        watchlist_max_updated,
        int(event_count or 0),
        event_max_created,
    )

def _load_research_report_entry_batch(
    db: Session,
    *,
    after_created_at: datetime | None = None,
    seen_ids_at_created_at: list[UUID] | None = None,
    limit: int = 20,
) -> list[KnowledgeEntry]:
    stmt = (
        select(KnowledgeEntry)
        .where(KnowledgeEntry.user_id == settings.single_user_id)
        .where(KnowledgeEntry.source_domain == "research.report")
        .order_by(KnowledgeEntry.created_at.asc(), KnowledgeEntry.id.asc())
        .limit(limit)
    )
    if after_created_at is not None:
        timestamp_filter = KnowledgeEntry.created_at > after_created_at
        if seen_ids_at_created_at:
            timestamp_filter = or_(
                timestamp_filter,
                and_(
                    KnowledgeEntry.created_at == after_created_at,
                    KnowledgeEntry.id.not_in(seen_ids_at_created_at),
                ),
            )
        stmt = stmt.where(timestamp_filter)
    return list(db.scalars(stmt))


def _load_research_report_version_batch(
    db: Session,
    *,
    after_created_at: datetime | None = None,
    seen_ids_at_created_at: list[UUID] | None = None,
    limit: int = 20,
) -> list[ResearchReportVersion]:
    stmt = (
        select(ResearchReportVersion)
        .order_by(ResearchReportVersion.created_at.asc(), ResearchReportVersion.id.asc())
        .limit(limit)
    )
    if after_created_at is not None:
        timestamp_filter = ResearchReportVersion.created_at > after_created_at
        if seen_ids_at_created_at:
            timestamp_filter = or_(
                timestamp_filter,
                and_(
                    ResearchReportVersion.created_at == after_created_at,
                    ResearchReportVersion.id.not_in(seen_ids_at_created_at),
                ),
            )
        stmt = stmt.where(timestamp_filter)
    return list(db.scalars(stmt))


def _load_research_report_entries(db: Session) -> list[KnowledgeEntry]:
    return list(
        db.scalars(
            select(KnowledgeEntry)
            .where(KnowledgeEntry.user_id == settings.single_user_id)
            .where(KnowledgeEntry.source_domain == "research.report")
            .order_by(desc(KnowledgeEntry.updated_at), desc(KnowledgeEntry.created_at))
        )
    )


def _load_research_report_versions(db: Session) -> list[ResearchReportVersion]:
    return list(
        db.scalars(
            select(ResearchReportVersion).order_by(desc(ResearchReportVersion.created_at))
        )
    )


def _new_backfill_stage_state() -> dict[str, Any]:
    return {
        "offset": 0,
        "last_created_at": None,
        "last_id": None,
        "seen_ids_at_created_at": [],
        "scanned": 0,
        "updated": 0,
    }


def _new_research_report_backfill_state(
    *,
    batch_size: int,
    commit_every: int,
) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": _BACKFILL_CHECKPOINT_SCHEMA_VERSION,
        "stage": _BACKFILL_STAGE_ENTRIES,
        "batch_size": batch_size,
        "commit_every": commit_every,
        "commits": 0,
        "started_at": timestamp,
        "updated_at": timestamp,
        "completed_at": None,
        _BACKFILL_STAGE_ENTRIES: _new_backfill_stage_state(),
        _BACKFILL_STAGE_VERSIONS: _new_backfill_stage_state(),
    }


def _coerce_research_report_backfill_state(
    raw_state: dict[str, Any] | None,
    *,
    batch_size: int,
    commit_every: int,
) -> dict[str, Any]:
    state = _new_research_report_backfill_state(batch_size=batch_size, commit_every=commit_every)
    if not isinstance(raw_state, dict):
        return state
    state["schema_version"] = int(raw_state.get("schema_version") or _BACKFILL_CHECKPOINT_SCHEMA_VERSION)
    stage = normalize_text(str(raw_state.get("stage") or ""))
    if stage in {_BACKFILL_STAGE_ENTRIES, _BACKFILL_STAGE_VERSIONS, _BACKFILL_STAGE_DONE}:
        state["stage"] = stage
    state["commits"] = int(raw_state.get("commits") or 0)
    state["started_at"] = normalize_text(str(raw_state.get("started_at") or "")) or state["started_at"]
    state["updated_at"] = normalize_text(str(raw_state.get("updated_at") or "")) or state["updated_at"]
    state["completed_at"] = normalize_text(str(raw_state.get("completed_at") or "")) or None
    for stage_name in (_BACKFILL_STAGE_ENTRIES, _BACKFILL_STAGE_VERSIONS):
        stage_state = raw_state.get(stage_name)
        if not isinstance(stage_state, dict):
            continue
        coerced = state[stage_name]
        coerced["offset"] = int(stage_state.get("offset") or 0)
        coerced["last_created_at"] = normalize_text(str(stage_state.get("last_created_at") or "")) or None
        coerced["last_id"] = normalize_text(str(stage_state.get("last_id") or "")) or None
        seen_ids = stage_state.get("seen_ids_at_created_at")
        if isinstance(seen_ids, list):
            coerced["seen_ids_at_created_at"] = [
                normalize_text(str(item or ""))
                for item in seen_ids
                if normalize_text(str(item or ""))
            ]
        coerced["scanned"] = int(stage_state.get("scanned") or 0)
        coerced["updated"] = int(stage_state.get("updated") or 0)
    return state


def _load_research_report_backfill_state(
    checkpoint_path: str | Path | None,
    *,
    batch_size: int,
    commit_every: int,
    resume: bool,
) -> tuple[dict[str, Any], Path | None]:
    if checkpoint_path is None:
        return _new_research_report_backfill_state(batch_size=batch_size, commit_every=commit_every), None
    path = Path(checkpoint_path).expanduser()
    if resume and path.exists():
        try:
            raw_state = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            raw_state = None
        return _coerce_research_report_backfill_state(
            raw_state,
            batch_size=batch_size,
            commit_every=commit_every,
        ), path
    return _new_research_report_backfill_state(batch_size=batch_size, commit_every=commit_every), path


def _write_research_report_backfill_state(state: dict[str, Any], checkpoint_path: Path | None) -> None:
    if checkpoint_path is None:
        return
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True)
    tmp_path = checkpoint_path.with_suffix(f"{checkpoint_path.suffix}.tmp")
    tmp_path.write_text(payload, encoding="utf-8")
    tmp_path.replace(checkpoint_path)


def _parse_backfill_uuid(value: str | None) -> UUID | None:
    normalized = normalize_text(value or "")
    if not normalized:
        return None
    try:
        return UUID(normalized)
    except (TypeError, ValueError):
        return None


def _update_backfill_stage_progress(
    state: dict[str, Any],
    *,
    stage_name: str,
    offset: int,
    cursor_created_at: datetime | None,
    cursor_id: UUID | None,
    seen_ids_at_created_at: list[UUID],
    scanned: int,
    updated: int,
) -> None:
    stage_state = state.setdefault(stage_name, _new_backfill_stage_state())
    stage_state["offset"] = int(offset)
    stage_state["last_created_at"] = cursor_created_at.isoformat() if cursor_created_at is not None else None
    stage_state["last_id"] = str(cursor_id) if cursor_id is not None else None
    stage_state["seen_ids_at_created_at"] = [str(item) for item in seen_ids_at_created_at]
    stage_state["scanned"] = int(scanned)
    stage_state["updated"] = int(updated)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()


def _commit_research_report_backfill_progress(
    db: Session,
    *,
    state: dict[str, Any],
    checkpoint_path: Path | None,
    stage_name: str,
    offset: int,
    cursor_created_at: datetime | None,
    cursor_id: UUID | None,
    seen_ids_at_created_at: list[UUID],
    scanned: int,
    updated: int,
) -> None:
    db.commit()
    state["commits"] = int(state.get("commits") or 0) + 1
    state["stage"] = stage_name
    _update_backfill_stage_progress(
        state,
        stage_name=stage_name,
        offset=offset,
        cursor_created_at=cursor_created_at,
        cursor_id=cursor_id,
        seen_ids_at_created_at=seen_ids_at_created_at,
        scanned=scanned,
        updated=updated,
    )
    _write_research_report_backfill_state(state, checkpoint_path)
    db.expire_all()


def _parse_backfill_uuid_list(values: Any) -> list[UUID]:
    if not isinstance(values, list):
        return []
    parsed: list[UUID] = []
    for value in values:
        parsed_value = _parse_backfill_uuid(str(value) if value is not None else None)
        if parsed_value is not None:
            parsed.append(parsed_value)
    return parsed


def _load_research_report_entry_ids(db: Session) -> list[UUID]:
    return list(
        db.scalars(
            select(KnowledgeEntry.id)
            .where(KnowledgeEntry.user_id == settings.single_user_id)
            .where(KnowledgeEntry.source_domain == "research.report")
            .order_by(KnowledgeEntry.created_at.asc(), KnowledgeEntry.id.asc())
        )
    )


def _load_research_report_version_ids(db: Session) -> list[UUID]:
    return list(
        db.scalars(
            select(ResearchReportVersion.id).order_by(ResearchReportVersion.created_at.asc(), ResearchReportVersion.id.asc())
        )
    )


def _load_research_report_entries_by_ids(db: Session, entry_ids: list[UUID]) -> list[KnowledgeEntry]:
    if not entry_ids:
        return []
    rows = list(db.scalars(select(KnowledgeEntry).where(KnowledgeEntry.id.in_(entry_ids))))
    row_map = {row.id: row for row in rows}
    return [row_map[row_id] for row_id in entry_ids if row_id in row_map]


def _load_research_report_versions_by_ids(db: Session, version_ids: list[UUID]) -> list[ResearchReportVersion]:
    if not version_ids:
        return []
    rows = list(db.scalars(select(ResearchReportVersion).where(ResearchReportVersion.id.in_(version_ids))))
    row_map = {row.id: row for row in rows}
    return [row_map[row_id] for row_id in version_ids if row_id in row_map]


def _rewrite_stored_report_payload(
    report_payload: dict[str, Any] | None,
    *,
    tracking_topic_id: str | None = None,
) -> tuple[ResearchReportDocument | None, list[ResearchActionCardOut], dict[str, Any] | None]:
    if not isinstance(report_payload, dict):
        return None, [], None
    try:
        report = ResearchReportResponse.model_validate(report_payload)
        rewritten_report = _canonicalize_report_for_knowledge_backfill(report)
        action_cards: list[ResearchActionCardOut] = []
        payload = build_research_report_metadata(
            rewritten_report,
            action_cards=action_cards,
            tracking_topic_id=tracking_topic_id,
        )
        return rewritten_report, action_cards, payload
    except Exception:
        return None, [], None


def _backfill_research_report_entry(
    db: Session,
    entry: KnowledgeEntry,
    *,
    rewritten_entry_cache: dict[UUID, tuple[ResearchReportDocument, list[ResearchActionCardOut]]],
) -> bool:
    payload = entry.metadata_payload if isinstance(entry.metadata_payload, dict) else {}
    report_payload = payload.get("report") if isinstance(payload.get("report"), dict) else None
    if not isinstance(report_payload, dict):
        return False
    existing_intelligence = payload.get("commercial_intelligence")
    report_has_enrichment = bool(
        isinstance(report_payload, dict)
        and isinstance(report_payload.get("report_readiness"), dict)
        and isinstance(report_payload.get("commercial_summary"), dict)
        and isinstance(report_payload.get("technical_appendix"), dict)
        and isinstance(report_payload.get("review_queue"), list)
    )
    tracking_topic_id = normalize_text(str(payload.get("tracking_topic_id") or "")) or None
    rewritten_report, action_cards, rewritten_payload = _rewrite_stored_report_payload(
        report_payload,
        tracking_topic_id=tracking_topic_id,
    )
    if rewritten_report is None or rewritten_payload is None:
        return False
    if entry.id is not None:
        rewritten_entry_cache[entry.id] = (rewritten_report, action_cards)
    if (
        isinstance(existing_intelligence, dict)
        and int(existing_intelligence.get("schema_version") or 0) >= 10
        and report_has_enrichment
        and rewritten_payload.get("report") == report_payload
    ):
        return False
    updated_payload = {
        **payload,
        "report": rewritten_payload.get("report"),
        "action_cards": rewritten_payload.get("action_cards"),
        "commercial_intelligence": build_report_knowledge_intelligence(rewritten_report, action_cards=action_cards),
    }
    if tracking_topic_id:
        updated_payload["tracking_topic_id"] = tracking_topic_id
    if payload.get("review_queue_resolutions"):
        updated_payload["review_queue_resolutions"] = payload["review_queue_resolutions"]
        updated_payload = apply_review_queue_resolutions(updated_payload) or updated_payload
    entry.title = rewritten_report.report_title
    entry.metadata_payload = updated_payload
    db.add(entry)
    return True


def _backfill_research_report_version(
    db: Session,
    version: ResearchReportVersion,
    *,
    rewritten_entry_cache: dict[UUID, tuple[ResearchReportDocument, list[ResearchActionCardOut]]],
) -> bool:
    cached = rewritten_entry_cache.get(version.knowledge_entry_id) if version.knowledge_entry_id else None
    if cached is not None:
        rewritten_report, action_cards = cached
    else:
        rewritten_report, action_cards, _rewritten_payload = _rewrite_stored_report_payload(version.report_payload)
        if rewritten_report is None:
            return False
    next_title = rewritten_report.report_title
    next_payload = rewritten_report.model_dump(mode="json")
    next_action_cards = [card.model_dump(mode="json") for card in action_cards]
    next_targets = _unique_strings(
        [item.name for item in rewritten_report.top_target_accounts] or list(rewritten_report.target_accounts),
        limit=6,
    )
    next_competitors = _unique_strings(
        [item.name for item in rewritten_report.top_competitors] or list(rewritten_report.competitor_profiles),
        limit=6,
    )
    if (
        version.report_title == next_title
        and version.report_payload == next_payload
        and version.action_cards_payload == next_action_cards
        and int(version.source_count or 0) == int(rewritten_report.source_count or 0)
        and str(version.evidence_density or "low") == str(rewritten_report.evidence_density or "low")
        and str(version.source_quality or "low") == str(rewritten_report.source_quality or "low")
        and list(version.new_targets or []) == next_targets
        and list(version.new_competitors or []) == next_competitors
    ):
        return False
    version.report_title = next_title
    version.report_payload = next_payload
    version.action_cards_payload = next_action_cards
    version.source_count = int(rewritten_report.source_count or 0)
    version.evidence_density = str(rewritten_report.evidence_density or "low")
    version.source_quality = str(rewritten_report.source_quality or "low")
    version.new_targets = next_targets
    version.new_competitors = next_competitors
    if version.topic is not None and version.topic.last_report_version_id == version.id:
        version.topic.last_refresh_new_targets = list(next_targets)
        version.topic.last_refresh_new_competitors = list(next_competitors)
        db.add(version.topic)
    db.add(version)
    return True


def backfill_research_knowledge_intelligence(
    db: Session,
    *,
    batch_size: int = 20,
    commit_every: int | None = None,
    checkpoint_path: str | Path | None = None,
    resume: bool = False,
    max_rows: int | None = None,
) -> dict[str, Any]:
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")
    if commit_every is None:
        commit_every = batch_size
    if commit_every <= 0:
        raise ValueError("commit_every must be greater than 0")
    if max_rows is not None and max_rows <= 0:
        raise ValueError("max_rows must be greater than 0")

    state, resolved_checkpoint_path = _load_research_report_backfill_state(
        checkpoint_path,
        batch_size=batch_size,
        commit_every=commit_every,
        resume=resume,
    )
    state["batch_size"] = batch_size
    state["commit_every"] = commit_every
    state["completed_at"] = state.get("completed_at") if state.get("stage") == _BACKFILL_STAGE_DONE else None
    _write_research_report_backfill_state(state, resolved_checkpoint_path)

    rewritten_entry_cache: dict[UUID, tuple[ResearchReportDocument, list[ResearchActionCardOut]]] = {}
    processed_this_run = 0

    while state.get("stage") != _BACKFILL_STAGE_DONE:
        stage_name = str(state.get("stage") or _BACKFILL_STAGE_ENTRIES)
        if stage_name not in {_BACKFILL_STAGE_ENTRIES, _BACKFILL_STAGE_VERSIONS}:
            stage_name = _BACKFILL_STAGE_ENTRIES
            state["stage"] = stage_name

        stage_state = state.setdefault(stage_name, _new_backfill_stage_state())
        stage_offset = int(stage_state.get("offset") or 0)
        cursor_created_at = _parse_iso_datetime(stage_state.get("last_created_at"))
        cursor_id = _parse_backfill_uuid(stage_state.get("last_id"))
        seen_ids_at_created_at = _parse_backfill_uuid_list(stage_state.get("seen_ids_at_created_at"))
        scanned = int(stage_state.get("scanned") or 0)
        updated = int(stage_state.get("updated") or 0)
        pending_rows = 0
        stage_ids = (
            _load_research_report_entry_ids(db)
            if stage_name == _BACKFILL_STAGE_ENTRIES
            else _load_research_report_version_ids(db)
        )
        stage_total = len(stage_ids)
        if stage_offset > stage_total:
            stage_offset = stage_total
        stage_complete = stage_offset >= stage_total

        while True:
            remaining_budget = None if max_rows is None else max_rows - processed_this_run
            if remaining_budget is not None and remaining_budget <= 0:
                break
            if stage_offset >= stage_total:
                stage_complete = True
                break

            fetch_limit = batch_size
            if remaining_budget is not None:
                fetch_limit = min(fetch_limit, remaining_budget)
            fetch_limit = min(fetch_limit, max(1, commit_every - pending_rows))
            batch_ids = stage_ids[stage_offset : stage_offset + fetch_limit]
            rows = (
                _load_research_report_entries_by_ids(db, batch_ids)
                if stage_name == _BACKFILL_STAGE_ENTRIES
                else _load_research_report_versions_by_ids(db, batch_ids)
            )

            if not rows:
                stage_offset += len(batch_ids)
                scanned += len(batch_ids)
                continue

            for row in rows:
                row_updated = (
                    _backfill_research_report_entry(
                        db,
                        row,
                        rewritten_entry_cache=rewritten_entry_cache,
                    )
                    if stage_name == _BACKFILL_STAGE_ENTRIES
                    else _backfill_research_report_version(
                        db,
                        row,
                        rewritten_entry_cache=rewritten_entry_cache,
                    )
                )
                scanned += 1
                if row_updated:
                    updated += 1
                processed_this_run += 1
                pending_rows += 1
                row_created_at = row.created_at
                row_id = row.id
                if cursor_created_at is None or row_created_at != cursor_created_at:
                    cursor_created_at = row_created_at
                    seen_ids_at_created_at = [row_id]
                else:
                    seen_ids_at_created_at = [*seen_ids_at_created_at, row_id]
                cursor_id = row_id
            stage_offset += len(batch_ids)

            if pending_rows >= commit_every:
                _commit_research_report_backfill_progress(
                    db,
                    state=state,
                    checkpoint_path=resolved_checkpoint_path,
                    stage_name=stage_name,
                    offset=stage_offset,
                    cursor_created_at=cursor_created_at,
                    cursor_id=cursor_id,
                    seen_ids_at_created_at=seen_ids_at_created_at,
                    scanned=scanned,
                    updated=updated,
                )
                pending_rows = 0

        if pending_rows > 0:
            _commit_research_report_backfill_progress(
                db,
                state=state,
                checkpoint_path=resolved_checkpoint_path,
                stage_name=stage_name,
                offset=stage_offset,
                cursor_created_at=cursor_created_at,
                cursor_id=cursor_id,
                seen_ids_at_created_at=seen_ids_at_created_at,
                scanned=scanned,
                updated=updated,
            )
        else:
            _update_backfill_stage_progress(
                state,
                stage_name=stage_name,
                offset=stage_offset,
                cursor_created_at=cursor_created_at,
                cursor_id=cursor_id,
                seen_ids_at_created_at=seen_ids_at_created_at,
                scanned=scanned,
                updated=updated,
            )

        if not stage_complete:
            break

        state["stage"] = _BACKFILL_STAGE_VERSIONS if stage_name == _BACKFILL_STAGE_ENTRIES else _BACKFILL_STAGE_DONE
        if state["stage"] == _BACKFILL_STAGE_DONE:
            state["completed_at"] = datetime.now(timezone.utc).isoformat()
        else:
            state["completed_at"] = None
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        _write_research_report_backfill_state(state, resolved_checkpoint_path)

    return {
        "scanned": int(state[_BACKFILL_STAGE_ENTRIES]["scanned"]),
        "updated": int(state[_BACKFILL_STAGE_ENTRIES]["updated"]),
        "scanned_versions": int(state[_BACKFILL_STAGE_VERSIONS]["scanned"]),
        "updated_versions": int(state[_BACKFILL_STAGE_VERSIONS]["updated"]),
        "processed_this_run": processed_this_run,
        "commits": int(state.get("commits") or 0),
        "completed": state.get("stage") == _BACKFILL_STAGE_DONE,
        "stage": str(state.get("stage") or _BACKFILL_STAGE_ENTRIES),
        "batch_size": batch_size,
        "commit_every": commit_every,
        "checkpoint_path": str(resolved_checkpoint_path) if resolved_checkpoint_path is not None else None,
    }


def _entry_link(entry: KnowledgeEntry) -> dict[str, Any]:
    return {
        "entry_id": entry.id,
        "title": entry.title,
        "source_domain": entry.source_domain,
        "collection_name": entry.collection_name,
        "created_at": entry.created_at,
    }


def _severity_rank(value: str) -> int:
    normalized = normalize_text(value).lower()
    if normalized == "high":
        return 2
    if normalized == "medium":
        return 1
    return 0


def _severity_from_rank(value: int) -> str:
    if value >= 2:
        return "high"
    if value >= 1:
        return "medium"
    return "low"


def _raise_severity(value: str) -> str:
    return _severity_from_rank(min(2, _severity_rank(value) + 1))


def _lower_severity(value: str) -> str:
    return _severity_from_rank(max(0, _severity_rank(value) - 1))


def _parse_iso_datetime(value: str | None) -> datetime | None:
    normalized = normalize_text(value or "")
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None


def _review_status_label(value: str) -> str:
    normalized = normalize_text(value).lower()
    if normalized == "resolved":
        return "已核验"
    if normalized == "deferred":
        return "已延后"
    return "待处理"


def _account_timeline_from_watchlists(db: Session) -> dict[str, list[dict[str, Any]]]:
    timeline_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rows = db.execute(
        select(ResearchWatchlistChangeEvent, ResearchWatchlist.name)
        .join(ResearchWatchlist, ResearchWatchlist.id == ResearchWatchlistChangeEvent.watchlist_id)
        .where(ResearchWatchlist.user_id == settings.single_user_id)
        .order_by(desc(ResearchWatchlistChangeEvent.created_at))
        .limit(120)
    ).all()
    for event, watchlist_name in rows:
        payload = event.payload if isinstance(event.payload, dict) else {}
        candidate_names = _unique_strings(
            [
                *(str(item) for item in payload.get("accounts", []) if str(item).strip()),
                *(str(item) for item in payload.get("targets", []) if str(item).strip()),
            ],
            limit=4,
        )
        if not candidate_names:
            continue
        tags = _unique_strings(
            [
                *(str(item) for item in payload.get("why_now", []) if str(item).strip()),
                *(str(item) for item in payload.get("opportunities", []) if str(item).strip()),
                *(str(item) for item in payload.get("budget_signals", []) if str(item).strip()),
            ],
            limit=4,
        )
        budget_probability = 0
        try:
            budget_probability = int(payload.get("top_budget_probability") or 0)
        except (TypeError, ValueError):
            budget_probability = 0
        next_action = ""
        if tags:
            next_action = tags[0]
        elif budget_probability > 0:
            next_action = f"优先核验预算概率 {budget_probability}% 对应的采购与决策窗口。"
        item = {
            "id": str(event.id),
            "kind": "watchlist",
            "title": event.summary,
            "summary": normalize_text(str(payload.get("report_title") or watchlist_name or event.summary)),
            "severity": event.severity,
            "created_at": event.created_at,
            "watchlist_name": normalize_text(watchlist_name),
            "next_action": next_action,
            "budget_probability": budget_probability,
            "related_entry_id": None,
            "related_watchlist_id": str(event.watchlist_id),
            "tags": tags,
        }
        for raw_name in candidate_names:
            canonical_name = _canonicalize_account_name(raw_name)
            if _is_low_signal_entity_name(canonical_name):
                continue
            slug = _slugify(canonical_name)
            timeline_map[slug].append(item)
    return timeline_map


def _account_timeline_from_review_queue(db: Session) -> dict[str, list[dict[str, Any]]]:
    timeline_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in _load_research_report_entries(db):
        payload = apply_review_queue_resolutions(entry.metadata_payload if isinstance(entry.metadata_payload, dict) else {})
        report_payload = payload.get("report") if isinstance(payload.get("report"), dict) else {}
        raw_queue = report_payload.get("review_queue") if isinstance(report_payload.get("review_queue"), list) else []
        if not raw_queue:
            continue
        intelligence = extract_commercial_intelligence(payload) or {}
        accounts = [
            item
            for item in (intelligence.get("accounts") or [])
            if isinstance(item, dict) and str(item.get("role") or "") == "target"
        ]
        primary_account = accounts[0] if accounts else {}
        canonical_account_name = _canonicalize_account_name(
            str(primary_account.get("name") or primary_account.get("slug") or ""),
            evidence_links=list(primary_account.get("evidence_links") or []),
        )
        if _is_low_signal_entity_name(canonical_account_name):
            continue
        account_slug = _slugify(canonical_account_name)
        for raw in raw_queue[:6]:
            if not isinstance(raw, dict):
                continue
            review_id = normalize_text(str(raw.get("id") or ""))
            if not review_id:
                review_id = f"{entry.id}"
            resolution_status = normalize_text(str(raw.get("resolution_status") or "open")).lower() or "open"
            resolution_note = normalize_text(str(raw.get("resolution_note") or ""))
            created_at = (
                _parse_iso_datetime(raw.get("resolved_at"))
                or entry.updated_at
                or entry.created_at
            )
            severity = normalize_text(str(raw.get("severity") or "medium")).lower() or "medium"
            if resolution_status == "resolved":
                severity = _lower_severity(severity)
            next_action = normalize_text(str(raw.get("recommended_action") or ""))
            if resolution_status == "resolved":
                next_action = resolution_note or "该冲突结论已核验，可回到账户推进链继续执行。"
            elif resolution_status == "deferred":
                next_action = resolution_note or next_action or "当前已延后处理，需在下轮 watchlist 刷新时优先复核。"
            else:
                next_action = next_action or "优先人工或模型二次核验该结论。"
            tags = _unique_strings(
                [
                    _review_status_label(resolution_status),
                    *(str(item) for item in raw.get("missing_axes") or [] if str(item).strip()),
                    *(str(item) for item in raw.get("focus_tags") or [] if str(item).strip()),
                ],
                limit=4,
            )
            timeline_map[account_slug].append(
                {
                    "id": f"review:{entry.id}:{review_id}",
                    "kind": "review_queue",
                    "title": normalize_text(str(raw.get("section_title") or "冲突证据审查")),
                    "summary": normalize_text(str(raw.get("summary") or "")),
                    "severity": severity,
                    "created_at": created_at,
                    "watchlist_name": None,
                    "next_action": next_action,
                    "budget_probability": 0,
                    "related_entry_id": entry.id,
                    "related_watchlist_id": None,
                    "tags": tags,
                    "resolution_status": resolution_status,
                    "resolution_note": resolution_note,
                }
            )
    return timeline_map


def _stakeholder_role_meta(value: str) -> tuple[str, str, str]:
    normalized = normalize_text(value)
    if any(token in normalized for token in ("采购", "招标", "招采", "集采")):
        return "采购/招采 gatekeeper", "需先验证", "high"
    if any(token in normalized for token in ("财务", "预算", "投资")):
        return "预算 owner", "需先验证", "high"
    if any(token in normalized for token in ("信息", "数字化", "科技", "数据")):
        return "数字化 sponsor", "潜在支持者", "high"
    return "业务 sponsor", "潜在支持者", "medium"


def _build_account_plan(bucket: dict[str, Any]) -> dict[str, Any]:
    relationship_goal = (
        f"把 {bucket['name']} 从公开线索推进到至少 1 位业务 sponsor 和 1 位数字化接口人的明确映射。"
        if bucket.get("departments") or bucket.get("contacts")
        else f"先为 {bucket['name']} 建立组织入口和首轮赞助人映射。"
    )
    value_hypothesis = (
        _clean_commercial_phrase(bucket.get("why_now", [""])[0] if bucket.get("why_now") else "", max_clauses=1, max_length=72)
        or _clean_commercial_phrase(str(bucket.get("latest_signal") or ""), max_clauses=1, max_length=72)
        or f"{bucket['name']} 当前已经出现值得持续跟进的数字化/采购信号。"
    )
    proof_points = _unique_strings(
        _clean_commercial_rows(
            [
                *(bucket.get("signals") or []),
                *(bucket.get("benchmark_cases") or []),
            ],
            limit=4,
        ),
        limit=4,
    )
    return {
        "objective": _clean_commercial_phrase(
            str(bucket.get("next_best_action") or ""),
            max_clauses=1,
            max_length=68,
        ) or f"围绕 {bucket['name']} 收敛预算窗口、组织入口和下一步推进动作。",
        "relationship_goal": relationship_goal,
        "value_hypothesis": value_hypothesis,
        "strategic_wedges": _clean_commercial_rows(
            [
                *(bucket.get("why_now") or []),
                *(bucket.get("benchmark_cases") or []),
                *(bucket.get("signals") or []),
            ],
            limit=4,
        ),
        "proof_points": proof_points,
        "next_meeting_goal": (
            "确认预算归口、项目 owner、进入窗口和可联合推进的伙伴。"
            if bucket.get("budget_probability", 0) >= 60
            else "优先确认是否存在真实项目、预算意向和组织入口。"
        ),
    }


def _build_stakeholder_map(bucket: dict[str, Any]) -> list[dict[str, Any]]:
    stakeholders: list[dict[str, Any]] = []
    evidence_links = list(bucket.get("evidence_links") or [])[:2]
    for department in list(bucket.get("departments") or [])[:4]:
        role, stance, priority = _stakeholder_role_meta(str(department))
        stakeholders.append(
            {
                "name": normalize_text(str(department)),
                "role": role,
                "stance": stance,
                "priority": priority,
                "next_move": (
                    "优先确认该部门是否掌握业务需求、预算归口或技术路线。"
                    if priority == "high"
                    else "继续确认该角色在项目推进中的真实影响力。"
                ),
                "evidence_links": evidence_links,
            }
        )
    for contact in list(bucket.get("contacts") or [])[:2]:
        stakeholders.append(
            {
                "name": normalize_text(str(contact)),
                "role": "公开入口",
                "stance": "可触达",
                "priority": "medium",
                "next_move": "通过该入口确认真实对接人、部门和响应链路。",
                "evidence_links": evidence_links,
            }
        )
    deduped: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for stakeholder in stakeholders:
        name = normalize_text(str(stakeholder.get("name") or ""))
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        deduped.append(stakeholder)
    return deduped[:6]


def _build_pipeline_risks(bucket: dict[str, Any]) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []

    def add_risk(title: str, severity: str, detail: str, mitigation: str) -> None:
        normalized_title = normalize_text(title)
        if not normalized_title:
            return
        if any(existing["title"] == normalized_title for existing in risks):
            return
        risks.append(
            {
                "title": normalized_title,
                "severity": severity,
                "detail": _clean_commercial_phrase(detail, max_clauses=1, max_length=88),
                "mitigation": _clean_commercial_phrase(mitigation, max_clauses=1, max_length=88),
            }
        )

    for raw in list(bucket.get("risks") or [])[:4]:
        text = normalize_text(str(raw))
        if not text:
            continue
        if "官方源" in text:
            add_risk("官方源仍需补强", "high", text, "补官网、公告、政策或采购源，再决定是否升级为强结论。")
        elif "联系人" in text or "联系" in text:
            add_risk("组织入口仍未坐实", "high", text, "优先把公开入口转成部门、角色和真实触达路径。")
        elif "预算" in text or "窗口" in text:
            add_risk("预算窗口仍需复核", "high", text, "补预算归口、招采窗口和期次信息，再进入 close plan。")
        else:
            add_risk("推进条件仍有不确定性", "medium", text, "继续补证并缩小推进范围。")

    if not bucket.get("contacts"):
        add_risk("缺少公开联系人", "high", "当前仍缺少可用的公开联系人或公开组织入口。", "优先核验官网联系页、采购公告联系人和投资者关系入口。")
    if int(bucket.get("budget_probability") or 0) < 55:
        add_risk("预算概率偏低", "medium", "当前预算窗口和采购节奏仍不够清晰。", "继续补预算草案、采购意向和项目节奏。")
    if int(bucket.get("confidence_score") or 0) < 70:
        add_risk("证据强度仍偏弱", "medium", "当前账户结论仍偏候选推进。", "补官方源、标杆案例和账户级证据后再推进。")
    if not bucket.get("benchmark_cases"):
        add_risk("缺少可复用标杆", "low", "当前缺少同类客户或同路径的标杆案例。", "补区域/行业相似案例，增强方案说服力。")
    if not risks:
        add_risk("需持续监控推进信号", "low", "当前账户暂无显性阻塞项，但仍需持续观察预算、组织和竞品变化。", "把 Watchlist 变化、会前简报和下一次 close plan 绑定到同一条推进链。")
    return risks[:4]


def _build_close_plan(bucket: dict[str, Any]) -> list[dict[str, Any]]:
    next_action = _clean_commercial_phrase(str(bucket.get("next_best_action") or ""), max_clauses=1, max_length=72)
    first_department = normalize_text(next(iter(bucket.get("departments") or []), "关键部门"))
    first_benchmark = _clean_commercial_phrase(next(iter(bucket.get("benchmark_cases") or []), "同类标杆案例"), max_clauses=1, max_length=48)
    return [
        {
            "title": "确认业务 sponsor",
            "owner": "BD / 客户经理",
            "due_window": "本周",
            "exit_criteria": f"确认 {first_department or '关键部门'} 是否为真实发起方，并拿到下一次沟通入口。",
        },
        {
            "title": "坐实预算与时间窗口",
            "owner": "销售负责人",
            "due_window": "1-2 周",
            "exit_criteria": "确认预算归口、采购节奏和进入窗口，避免无预算强推进。",
        },
        {
            "title": "绑定方案与伙伴",
            "owner": "售前 / 生态负责人",
            "due_window": "2-3 周",
            "exit_criteria": f"形成与 {first_benchmark or '标杆案例'} 对齐的差异化说法，并确认是否需要伙伴协同。",
        },
        {
            "title": "输出 close plan 交付物",
            "owner": "咨询顾问 / 销售经理",
            "due_window": "3-4 周",
            "exit_criteria": next_action or "沉淀会前简报、关键假设、风险和下一步动作。",
        },
    ]


def _build_review_queue_index(db: Session) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for entry in _load_research_report_entries(db):
        payload = apply_review_queue_resolutions(entry.metadata_payload if isinstance(entry.metadata_payload, dict) else {})
        report_payload = payload.get("report") if isinstance(payload.get("report"), dict) else {}
        raw_queue = report_payload.get("review_queue") if isinstance(report_payload.get("review_queue"), list) else []
        if not raw_queue:
            continue
        intelligence = extract_commercial_intelligence(payload) or {}
        accounts = [
            item
            for item in (intelligence.get("accounts") or [])
            if isinstance(item, dict) and str(item.get("role") or "") == "target"
        ]
        primary_account = accounts[0] if accounts else {}
        account_name = normalize_text(str(primary_account.get("name") or ""))
        account_slug = _slugify(account_name) if account_name else None
        for raw in raw_queue[:6]:
            if not isinstance(raw, dict):
                continue
            resolution_status = normalize_text(str(raw.get("resolution_status") or "open")).lower() or "open"
            if resolution_status == "resolved":
                continue
            items.append(
                {
                    "id": normalize_text(str(raw.get("id") or f"review-{entry.id}")),
                    "severity": normalize_text(str(raw.get("severity") or "medium")) or "medium",
                    "title": normalize_text(str(raw.get("section_title") or "冲突证据审查")),
                    "summary": normalize_text(str(raw.get("summary") or "")),
                    "account_slug": account_slug,
                    "account_name": account_name or None,
                    "related_entry_id": entry.id,
                    "recommended_action": normalize_text(str(raw.get("recommended_action") or "")),
                    "evidence_links": list(raw.get("evidence_links") or [])[:3],
                    "resolution_status": resolution_status,
                    "resolution_note": normalize_text(str(raw.get("resolution_note") or "")),
                    "resolved_at": raw.get("resolved_at"),
                    "created_at": entry.created_at,
                }
            )
    severity_order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda item: (severity_order.get(str(item.get("severity")), 3), -datetime.timestamp(item.get("created_at") or datetime.now(timezone.utc))))
    return items[:12]


def _build_dashboard_alerts(accounts: list[dict[str, Any]], review_queue: list[dict[str, Any]]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []

    def add_alert(item: dict[str, Any]) -> None:
        if any(existing["id"] == item["id"] for existing in alerts):
            return
        alerts.append(item)

    for account in accounts[:10]:
        timeline_items = list(account.get("timeline") or [])
        review_timeline = [item for item in timeline_items if str(item.get("kind") or "") == "review_queue"]
        has_open_review = any(str(item.get("resolution_status") or "open") == "open" for item in review_timeline)
        has_deferred_review = any(str(item.get("resolution_status") or "open") == "deferred" for item in review_timeline)
        has_resolved_review = bool(review_timeline) and not has_open_review and not has_deferred_review
        for risk in list(account.get("pipeline_risks") or [])[:2]:
            if str(risk.get("severity") or "low") not in {"high", "medium"}:
                continue
            add_alert(
                {
                    "id": f"risk-{account['slug']}-{_slugify(str(risk.get('title') or 'risk'))}",
                    "kind": "pipeline_risk",
                    "severity": risk.get("severity") or "medium",
                    "title": str(risk.get("title") or "推进风险"),
                    "summary": str(risk.get("detail") or ""),
                    "account_slug": account["slug"],
                    "account_name": account["name"],
                    "recommended_action": str(risk.get("mitigation") or ""),
                    "created_at": None,
                }
            )
        for timeline_item in timeline_items[:5]:
            if str(timeline_item.get("kind") or "") != "watchlist":
                continue
            if str(timeline_item.get("severity") or "low") not in {"high", "medium"}:
                continue
            severity = str(timeline_item.get("severity") or "medium")
            summary = str(timeline_item.get("summary") or "")
            recommended_action = str(timeline_item.get("next_action") or "优先核验当前变化对账户推进的真实影响。")
            if has_open_review:
                severity = _raise_severity(severity)
                summary = _unique_strings([summary, "当前账户仍有待核验冲突结论，需要先确认变化是否可靠。"])[0:2]
                summary = " ".join(summary).strip()
                recommended_action = f"{recommended_action}；并先关闭待核验冲突结论。"
            elif has_deferred_review:
                severity = _severity_from_rank(max(1, _severity_rank(severity)))
                summary = _unique_strings([summary, "该账户已有延后处理的冲突项，本次变化建议与历史争议一起复核。"])[0:2]
                summary = " ".join(summary).strip()
                recommended_action = f"{recommended_action}；并把已延后审查项一起带回核验。"
            elif has_resolved_review:
                severity = _lower_severity(severity)
                recommended_action = f"{recommended_action}；相关冲突项已核验，可按账户计划继续推进。"
            add_alert(
                {
                    "id": f"watchlist-{timeline_item['id']}",
                    "kind": "watchlist",
                    "severity": severity,
                    "title": timeline_item.get("title") or "Watchlist 变化",
                    "summary": summary,
                    "account_slug": account["slug"],
                    "account_name": account["name"],
                    "recommended_action": recommended_action,
                    "created_at": timeline_item.get("created_at"),
                }
            )
    for item in review_queue[:4]:
        if str(item.get("severity") or "low") not in {"high", "medium"}:
            continue
        add_alert(
            {
                "id": f"review-{item['id']}",
                "kind": "review_queue",
                "severity": item.get("severity") or "medium",
                "title": item.get("title") or "冲突证据待审查",
                "summary": item.get("summary") or "",
                "account_slug": item.get("account_slug"),
                "account_name": item.get("account_name"),
                "recommended_action": item.get("recommended_action") or "优先人工或模型二次核验该结论。",
                "created_at": item.get("created_at"),
            }
        )
    severity_order = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(key=lambda item: (severity_order.get(str(item.get("severity")), 3), -(datetime.timestamp(item.get("created_at") or datetime.now(timezone.utc)) if item.get("created_at") else 0)))
    return alerts[:8]


def _build_role_views(
    accounts: list[dict[str, Any]],
    opportunities: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
    review_queue: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    top_accounts = accounts[:4]
    top_opportunities = opportunities[:4]
    return [
        {
            "key": "bd",
            "label": "BD 视图",
            "summary": "优先看预算概率、组织入口、下一步动作和 close plan。",
            "focus_items": _unique_strings(
                [
                    *(item.get("next_best_action") or "" for item in top_accounts),
                    *(item.get("title") or "" for item in top_opportunities),
                ],
                limit=4,
            ),
            "account_slugs": [item["slug"] for item in top_accounts[:3]],
            "opportunity_titles": [item["title"] for item in top_opportunities[:3]],
        },
        {
            "key": "exec",
            "label": "管理层视图",
            "summary": "优先看高优先级提醒、预算概率高的账户和本周必须拍板的动作。",
            "focus_items": _unique_strings(
                [
                    *(item.get("title") or "" for item in alerts[:3]),
                    *(item.get("name") or "" for item in top_accounts[:2]),
                ],
                limit=4,
            ),
            "account_slugs": [item["slug"] for item in top_accounts[:2]],
            "opportunity_titles": [item["title"] for item in top_opportunities[:2]],
        },
        {
            "key": "consulting",
            "label": "咨询视图",
            "summary": "优先看假设、缺证项、对标案例和冲突审查队列。",
            "focus_items": _unique_strings(
                [
                    *(item.get("summary") or item.get("title") or "" for item in review_queue[:3]),
                    *(value for item in top_accounts[:1] for value in (item.get("benchmark_cases") or [])),
                ],
                limit=4,
            ),
            "account_slugs": [item["slug"] for item in top_accounts[:2]],
            "opportunity_titles": [],
        },
        {
            "key": "delivery",
            "label": "交付视图",
            "summary": "优先看 close plan、风险缓释和下一次会前材料。",
            "focus_items": _unique_strings(
                [
                    *(item.get("next_best_action") or "" for item in top_accounts[:2]),
                    *(item.get("next_best_action") or "" for item in top_opportunities[:2]),
                ],
                limit=4,
            ),
            "account_slugs": [item["slug"] for item in top_accounts[:2]],
            "opportunity_titles": [item["title"] for item in top_opportunities[:2]],
        },
    ]


def _aggregate_accounts_uncached(db: Session) -> dict[str, dict[str, Any]]:
    accounts: dict[str, dict[str, Any]] = {}
    seen_opportunity_keys: defaultdict[str, set[str]] = defaultdict(set)
    watchlist_timeline = _account_timeline_from_watchlists(db)
    review_queue_timeline = _account_timeline_from_review_queue(db)
    for entry in _load_research_report_entries(db):
        payload = entry.metadata_payload if isinstance(entry.metadata_payload, dict) else {}
        intelligence = extract_commercial_intelligence(payload)
        if not intelligence:
            continue
        seen_account_slugs_for_entry: set[str] = set()
        for account in intelligence.get("accounts") or []:
            if not isinstance(account, dict) or str(account.get("role") or "") != "target":
                continue
            raw_name = str(account.get("name") or account.get("slug") or "")
            canonical_name = _canonicalize_account_name(
                raw_name,
                evidence_links=list(account.get("evidence_links") or []),
            )
            if _is_low_signal_entity_name(canonical_name):
                continue
            slug = _slugify(canonical_name)
            if not slug:
                continue
            bucket = accounts.setdefault(
                slug,
                {
                    "slug": slug,
                    "name": canonical_name or normalize_text(account.get("name")) or slug,
                    "priority": str(account.get("priority") or "medium"),
                    "report_count": 0,
                    "opportunity_count": 0,
                    "confidence_score": 0,
                    "budget_probability": 0,
                    "maturity_stage": str(account.get("maturity_stage") or ""),
                    "latest_signal": "",
                    "next_best_action": "",
                    "benchmark_cases": [],
                    "related_entry_ids": [],
                    "summary": normalize_text(account.get("summary")),
                    "why_now": [],
                    "contacts": [],
                    "departments": [],
                    "signals": [],
                    "risks": [],
                    "evidence_links": [],
                    "opportunities": [],
                    "related_entries": [],
                    "timeline": [],
                    "account_plan": {},
                    "stakeholder_map": [],
                    "close_plan": [],
                    "pipeline_risks": [],
                },
            )
            if slug not in seen_account_slugs_for_entry:
                bucket["report_count"] += 1
                bucket["related_entry_ids"] = list(dict.fromkeys([*bucket["related_entry_ids"], entry.id]))
                bucket["related_entries"].append(_entry_link(entry))
                bucket["timeline"].append(
                    {
                        "id": f"report:{entry.id}:{slug}",
                        "kind": "report",
                        "title": entry.title,
                        "summary": normalize_text(account.get("summary")) or normalize_text(entry.title),
                        "severity": "medium",
                        "created_at": entry.created_at,
                        "watchlist_name": None,
                        "next_action": normalize_text(account.get("next_best_action")),
                        "budget_probability": int(account.get("budget_probability") or 0),
                        "related_entry_id": entry.id,
                        "related_watchlist_id": None,
                        "tags": _unique_strings(
                            [
                                *(account.get("signals") or []),
                                *(account.get("why_now") or []),
                            ],
                            limit=4,
                        ),
                    }
                )
                seen_account_slugs_for_entry.add(slug)
            bucket["confidence_score"] = max(bucket["confidence_score"], int(account.get("confidence_score") or 0))
            bucket["budget_probability"] = max(bucket["budget_probability"], int(account.get("budget_probability") or 0))
            bucket["priority"] = "high" if bucket["confidence_score"] >= 75 else "medium" if bucket["confidence_score"] >= 55 else "low"
            bucket["maturity_stage"] = bucket["maturity_stage"] or str(account.get("maturity_stage") or "")
            signals = _unique_strings([*bucket["signals"], *(account.get("signals") or [])], limit=8)
            bucket["signals"] = signals
            bucket["latest_signal"] = signals[0] if signals else bucket["latest_signal"]
            bucket["next_best_action"] = bucket["next_best_action"] or normalize_text(account.get("next_best_action"))
            bucket["benchmark_cases"] = _unique_strings(
                [*bucket["benchmark_cases"], *(account.get("benchmark_cases") or [])],
                limit=6,
            )
            bucket["why_now"] = _unique_strings([*bucket["why_now"], *(account.get("why_now") or [])], limit=6)
            bucket["contacts"] = _unique_strings([*bucket["contacts"], *(account.get("contacts") or [])], limit=6)
            bucket["departments"] = _unique_strings([*bucket["departments"], *(account.get("departments") or [])], limit=6)
            bucket["evidence_links"] = bucket["evidence_links"] or list(account.get("evidence_links") or [])[:6]
        for opportunity in intelligence.get("opportunities") or []:
            if not isinstance(opportunity, dict):
                continue
            canonical_account_name = _canonicalize_account_name(str(opportunity.get("account_name") or opportunity.get("account_slug") or ""))
            account_slug = _slugify(canonical_account_name)
            if account_slug not in accounts:
                continue
            bucket = accounts[account_slug]
            normalized_opportunity = {
                **opportunity,
                "account_name": canonical_account_name or opportunity.get("account_name"),
                "account_slug": account_slug,
            }
            opportunity_key = _opportunity_identity_key(normalized_opportunity)
            if opportunity_key in seen_opportunity_keys[account_slug]:
                continue
            seen_opportunity_keys[account_slug].add(opportunity_key)
            bucket["opportunity_count"] += 1
            bucket["opportunities"].append(normalized_opportunity)
            bucket["risks"] = _unique_strings([*bucket["risks"], *(normalized_opportunity.get("risk_flags") or [])], limit=6)
            bucket["timeline"].append(
                {
                    "id": f"opportunity:{entry.id}:{account_slug}:{opportunity_key}",
                    "kind": "opportunity",
                    "title": normalize_text(str(normalized_opportunity.get("title") or "机会更新")),
                    "summary": normalize_text(str(normalized_opportunity.get("entry_window") or normalized_opportunity.get("benchmark_case") or "")),
                    "severity": "high" if int(normalized_opportunity.get("budget_probability") or 0) >= 70 else "medium",
                    "created_at": entry.created_at,
                    "watchlist_name": None,
                    "next_action": normalize_text(str(normalized_opportunity.get("next_best_action") or "")),
                    "budget_probability": int(normalized_opportunity.get("budget_probability") or 0),
                    "related_entry_id": entry.id,
                    "related_watchlist_id": None,
                    "tags": _unique_strings(
                        [
                            *(normalized_opportunity.get("why_now") or []),
                            *(normalized_opportunity.get("risk_flags") or []),
                        ],
                        limit=4,
                    ),
                }
            )
    for bucket in accounts.values():
        bucket["timeline"] = sorted(
            [
                *bucket["timeline"],
                *watchlist_timeline.get(bucket["slug"], []),
                *review_queue_timeline.get(bucket["slug"], []),
            ],
            key=lambda item: item["created_at"],
            reverse=True,
        )[:10]
        bucket["related_entries"] = sorted(
            bucket["related_entries"],
            key=lambda item: item["created_at"],
            reverse=True,
        )[:6]
        bucket["opportunities"] = sorted(
            bucket["opportunities"],
            key=lambda item: (int(item.get("score") or 0), int(item.get("budget_probability") or 0)),
            reverse=True,
        )[:6]
        bucket["stakeholder_map"] = _build_stakeholder_map(bucket)
        bucket["pipeline_risks"] = _build_pipeline_risks(bucket)
        bucket["account_plan"] = _build_account_plan(bucket)
        bucket["close_plan"] = _build_close_plan(bucket)
    return accounts


def _aggregate_accounts(
    db: Session,
    *,
    signature: tuple[Any, ...] | None = None,
) -> dict[str, dict[str, Any]]:
    signature = signature or _commercial_cache_signature(db)
    cache_key = (id(db.get_bind()), str(settings.single_user_id), signature)
    now = time.monotonic()
    with _COMMERCIAL_AGGREGATE_CACHE_LOCK:
        cached = _COMMERCIAL_AGGREGATE_CACHE.get(cache_key)
        if cached and now - cached[0] <= _COMMERCIAL_AGGREGATE_CACHE_TTL_SECONDS:
            return cached[1]

        # Build under the lock so concurrent cache misses share one report scan.
        accounts = _aggregate_accounts_uncached(db)
        if (
            cache_key not in _COMMERCIAL_AGGREGATE_CACHE
            and len(_COMMERCIAL_AGGREGATE_CACHE) >= _COMMERCIAL_AGGREGATE_CACHE_MAX_ENTRIES
        ):
            oldest_key = min(_COMMERCIAL_AGGREGATE_CACHE, key=lambda key: _COMMERCIAL_AGGREGATE_CACHE[key][0])
            _COMMERCIAL_AGGREGATE_CACHE.pop(oldest_key, None)
        _COMMERCIAL_AGGREGATE_CACHE[cache_key] = (time.monotonic(), accounts)
        return accounts


def list_knowledge_accounts(
    db: Session,
    *,
    query: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    accounts = list(_aggregate_accounts(db).values())
    normalized_query = normalize_text(query or "").lower()
    if normalized_query:
        accounts = [
            item
            for item in accounts
            if normalized_query in normalize_text(item["name"]).lower()
            or any(normalized_query in normalize_text(value).lower() for value in item["signals"])
        ]
    accounts.sort(
        key=lambda item: (item["confidence_score"], item["budget_probability"], item["report_count"]),
        reverse=True,
    )
    return accounts[: max(1, min(limit, 50))]


def get_knowledge_account_detail(db: Session, slug: str) -> dict[str, Any] | None:
    return _aggregate_accounts(db).get(_slugify(slug))


def list_knowledge_opportunities(
    db: Session,
    *,
    account_slug: str | None = None,
    limit: int = 30,
) -> list[dict[str, Any]]:
    opportunities: list[dict[str, Any]] = []
    account_filter = _slugify(account_slug) if account_slug else None
    for bucket in _aggregate_accounts(db).values():
        if account_filter and bucket["slug"] != account_filter:
            continue
        opportunities.extend(bucket["opportunities"])
    opportunities.sort(
        key=lambda item: (int(item.get("score") or 0), int(item.get("budget_probability") or 0)),
        reverse=True,
    )
    return opportunities[: max(1, min(limit, 60))]


def _build_knowledge_commercial_dashboard_uncached(
    db: Session,
    *,
    signature: tuple[Any, ...],
) -> dict[str, Any]:
    account_index = _aggregate_accounts(db, signature=signature)
    all_accounts = sorted(
        account_index.values(),
        key=lambda item: (item["confidence_score"], item["budget_probability"], item["report_count"]),
        reverse=True,
    )
    all_opportunities: list[dict[str, Any]] = []
    for bucket in account_index.values():
        all_opportunities.extend(bucket["opportunities"])
    all_opportunities.sort(
        key=lambda item: (int(item.get("score") or 0), int(item.get("budget_probability") or 0)),
        reverse=True,
    )
    accounts = all_accounts[:6]
    opportunities = all_opportunities[:6]
    benchmark_cases: set[str] = set()
    high_confidence = 0
    for entry in _load_research_report_entries(db):
        payload = entry.metadata_payload if isinstance(entry.metadata_payload, dict) else {}
        intelligence = extract_commercial_intelligence(payload)
        if not intelligence:
            continue
        confidence = intelligence.get("confidence") if isinstance(intelligence.get("confidence"), dict) else {}
        if int(confidence.get("score") or 0) >= 75:
            high_confidence += 1
        benchmark = intelligence.get("benchmark") if isinstance(intelligence.get("benchmark"), dict) else {}
        for item in benchmark.get("cases") or []:
            normalized = normalize_text(item)
            if normalized:
                benchmark_cases.add(normalized)
    review_queue = _build_review_queue_index(db)
    alerts = _build_dashboard_alerts(all_accounts, review_queue)
    return {
        "account_count": len(account_index),
        "opportunity_count": len(all_opportunities),
        "high_confidence_report_count": high_confidence,
        "benchmark_case_count": len(benchmark_cases),
        "top_accounts": accounts,
        "top_opportunities": opportunities,
        "top_alerts": alerts,
        "role_views": _build_role_views(all_accounts, all_opportunities, alerts, review_queue),
        "review_queue": review_queue,
    }


def build_knowledge_commercial_dashboard(db: Session) -> dict[str, Any]:
    signature = _commercial_cache_signature(db)
    cache_key = (id(db.get_bind()), str(settings.single_user_id), signature)
    now = time.monotonic()
    with _COMMERCIAL_AGGREGATE_CACHE_LOCK:
        cached = _COMMERCIAL_DASHBOARD_CACHE.get(cache_key)
        if cached and now - cached[0] <= _COMMERCIAL_AGGREGATE_CACHE_TTL_SECONDS:
            return cached[1]

        dashboard = _build_knowledge_commercial_dashboard_uncached(db, signature=signature)
        if (
            cache_key not in _COMMERCIAL_DASHBOARD_CACHE
            and len(_COMMERCIAL_DASHBOARD_CACHE) >= _COMMERCIAL_AGGREGATE_CACHE_MAX_ENTRIES
        ):
            oldest_key = min(_COMMERCIAL_DASHBOARD_CACHE, key=lambda key: _COMMERCIAL_DASHBOARD_CACHE[key][0])
            _COMMERCIAL_DASHBOARD_CACHE.pop(oldest_key, None)
        _COMMERCIAL_DASHBOARD_CACHE[cache_key] = (time.monotonic(), dashboard)
        return dashboard
