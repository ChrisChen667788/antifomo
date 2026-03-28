from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import KnowledgeEntry
from app.models.research_entities import (
    ResearchReportVersion,
    ResearchSavedView,
    ResearchTrackingTopic,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TMP_DIR = PROJECT_ROOT / ".tmp"
LEGACY_WORKSPACE_FILE = TMP_DIR / "research_workspace.json"

settings = get_settings()
_WORKSPACE_BACKFILL_ATTEMPTED = False


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip())
        except ValueError:
            return _utc_now()
        if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return _utc_now()


def _coerce_uuid(value: Any) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return uuid.UUID(value.strip())
        except ValueError:
            pass
    return uuid.uuid4()


def _read_legacy_workspace() -> dict[str, list[dict[str, Any]]]:
    if not LEGACY_WORKSPACE_FILE.exists():
        return {"saved_views": [], "tracking_topics": []}
    try:
        payload = json.loads(LEGACY_WORKSPACE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"saved_views": [], "tracking_topics": []}
    if not isinstance(payload, dict):
        return {"saved_views": [], "tracking_topics": []}
    return {
        "saved_views": list(payload.get("saved_views") or []),
        "tracking_topics": list(payload.get("tracking_topics") or []),
    }


def _serialize_report_version(version: ResearchReportVersion) -> dict[str, Any]:
    return {
        "id": str(version.id),
        "entry_id": str(version.knowledge_entry_id) if version.knowledge_entry_id else None,
        "title": version.report_title,
        "refreshed_at": version.created_at,
        "source_count": int(version.source_count or 0),
        "evidence_density": str(version.evidence_density or "low"),
        "source_quality": str(version.source_quality or "low"),
        "new_target_count": len(version.new_targets or []),
        "new_competitor_count": len(version.new_competitors or []),
        "new_budget_signal_count": len(version.new_budget_signals or []),
    }


def _serialize_topic(topic: ResearchTrackingTopic, *, versions: list[ResearchReportVersion] | None = None) -> dict[str, Any]:
    ordered_versions = versions or sorted(topic.report_versions, key=lambda item: item.created_at, reverse=True)
    latest_version = topic.last_report_version or (ordered_versions[0] if ordered_versions else None)
    return {
        "id": str(topic.id),
        "name": topic.name,
        "keyword": topic.keyword,
        "research_focus": topic.research_focus or "",
        "perspective": topic.perspective,
        "region_filter": topic.region_filter or "",
        "industry_filter": topic.industry_filter or "",
        "notes": topic.notes or "",
        "created_at": topic.created_at,
        "updated_at": topic.updated_at,
        "last_refreshed_at": topic.last_refreshed_at,
        "last_refresh_status": topic.last_refresh_status or "idle",
        "last_refresh_error": topic.last_refresh_error,
        "last_refresh_note": topic.last_refresh_note,
        "last_refresh_new_targets": list(topic.last_refresh_new_targets or []),
        "last_refresh_new_competitors": list(topic.last_refresh_new_competitors or []),
        "last_refresh_new_budget_signals": list(topic.last_refresh_new_budget_signals or []),
        "last_report_entry_id": str(latest_version.knowledge_entry_id) if latest_version and latest_version.knowledge_entry_id else None,
        "last_report_title": latest_version.report_title if latest_version else None,
        "report_history": [_serialize_report_version(item) for item in ordered_versions[:8]],
    }


def _serialize_saved_view(view: ResearchSavedView) -> dict[str, Any]:
    return {
        "id": str(view.id),
        "name": view.name,
        "query": view.query,
        "filter_mode": view.filter_mode,
        "perspective": view.perspective,
        "region_filter": view.region_filter,
        "industry_filter": view.industry_filter,
        "action_type_filter": view.action_type_filter,
        "focus_only": bool(view.focus_only),
        "created_at": view.created_at,
        "updated_at": view.updated_at,
    }


def _serialize_version_detail(version: ResearchReportVersion) -> dict[str, Any]:
    return {
        "id": str(version.id),
        "topic_id": str(version.topic_id),
        "entry_id": str(version.knowledge_entry_id) if version.knowledge_entry_id else None,
        "title": version.report_title,
        "refreshed_at": version.created_at,
        "source_count": int(version.source_count or 0),
        "evidence_density": str(version.evidence_density or "low"),
        "source_quality": str(version.source_quality or "low"),
        "refresh_note": version.refresh_note,
        "new_targets": list(version.new_targets or []),
        "new_competitors": list(version.new_competitors or []),
        "new_budget_signals": list(version.new_budget_signals or []),
        "report": version.report_payload or None,
        "action_cards": list(version.action_cards_payload or []),
    }


def _maybe_backfill_workspace(db: Session) -> None:
    global _WORKSPACE_BACKFILL_ATTEMPTED
    if _WORKSPACE_BACKFILL_ATTEMPTED:
        return
    has_views = bool(db.scalar(select(func.count(ResearchSavedView.id)).where(ResearchSavedView.user_id == settings.single_user_id)))
    has_topics = bool(db.scalar(select(func.count(ResearchTrackingTopic.id)).where(ResearchTrackingTopic.user_id == settings.single_user_id)))
    if has_views or has_topics:
        _WORKSPACE_BACKFILL_ATTEMPTED = True
        return

    legacy = _read_legacy_workspace()
    if not legacy["saved_views"] and not legacy["tracking_topics"]:
        _WORKSPACE_BACKFILL_ATTEMPTED = True
        return

    knowledge_entry_ids: list[uuid.UUID] = []
    for topic in legacy["tracking_topics"]:
        for item in list(topic.get("report_history") or []):
            entry_id = item.get("entry_id")
            if isinstance(entry_id, str) and entry_id.strip():
                try:
                    knowledge_entry_ids.append(uuid.UUID(entry_id))
                except ValueError:
                    continue
    knowledge_entries = {
        entry.id: entry
        for entry in db.scalars(
            select(KnowledgeEntry).where(KnowledgeEntry.id.in_(knowledge_entry_ids))
        ).all()
    } if knowledge_entry_ids else {}

    for view in legacy["saved_views"]:
        db.add(
            ResearchSavedView(
                id=_coerce_uuid(view.get("id")),
                user_id=settings.single_user_id,
                name=str(view.get("name") or "未命名视图"),
                query=str(view.get("query") or ""),
                filter_mode=str(view.get("filter_mode") or "all"),
                perspective=str(view.get("perspective") or "all"),
                region_filter=str(view.get("region_filter") or ""),
                industry_filter=str(view.get("industry_filter") or ""),
                action_type_filter=str(view.get("action_type_filter") or ""),
                focus_only=bool(view.get("focus_only") or False),
                created_at=_normalize_datetime(view.get("created_at")),
                updated_at=_normalize_datetime(view.get("updated_at") or view.get("created_at")),
            )
        )

    for topic_payload in legacy["tracking_topics"]:
        topic = ResearchTrackingTopic(
            id=_coerce_uuid(topic_payload.get("id")),
            user_id=settings.single_user_id,
            name=str(topic_payload.get("name") or "未命名专题"),
            keyword=str(topic_payload.get("keyword") or ""),
            research_focus=str(topic_payload.get("research_focus") or ""),
            perspective=str(topic_payload.get("perspective") or "all"),
            region_filter=str(topic_payload.get("region_filter") or ""),
            industry_filter=str(topic_payload.get("industry_filter") or ""),
            notes=str(topic_payload.get("notes") or ""),
            last_refreshed_at=_normalize_datetime(topic_payload.get("last_refreshed_at")) if topic_payload.get("last_refreshed_at") else None,
            last_refresh_status=str(topic_payload.get("last_refresh_status") or "idle"),
            last_refresh_error=topic_payload.get("last_refresh_error"),
            last_refresh_note=topic_payload.get("last_refresh_note"),
            last_refresh_new_targets=list(topic_payload.get("last_refresh_new_targets") or []),
            last_refresh_new_competitors=list(topic_payload.get("last_refresh_new_competitors") or []),
            last_refresh_new_budget_signals=list(topic_payload.get("last_refresh_new_budget_signals") or []),
            created_at=_normalize_datetime(topic_payload.get("created_at")),
            updated_at=_normalize_datetime(topic_payload.get("updated_at") or topic_payload.get("created_at")),
        )
        db.add(topic)
        db.flush()

        versions: list[ResearchReportVersion] = []
        for version_payload in list(topic_payload.get("report_history") or []):
            entry_id_value = version_payload.get("entry_id")
            knowledge_entry_id: uuid.UUID | None = None
            if isinstance(entry_id_value, str) and entry_id_value.strip():
                try:
                    knowledge_entry_id = uuid.UUID(entry_id_value)
                except ValueError:
                    knowledge_entry_id = None
            linked_entry = knowledge_entries.get(knowledge_entry_id) if knowledge_entry_id else None
            metadata_payload = linked_entry.metadata_payload if linked_entry and isinstance(linked_entry.metadata_payload, dict) else {}
            report_payload = metadata_payload.get("report") if isinstance(metadata_payload.get("report"), dict) else {}
            action_cards_payload = metadata_payload.get("action_cards") if isinstance(metadata_payload.get("action_cards"), list) else []
            version = ResearchReportVersion(
                topic_id=topic.id,
                knowledge_entry_id=knowledge_entry_id,
                report_title=str(version_payload.get("title") or linked_entry.title if linked_entry else "未命名研报"),
                report_payload=report_payload or {},
                action_cards_payload=action_cards_payload or [],
                source_count=int(version_payload.get("source_count") or 0),
                evidence_density=str(version_payload.get("evidence_density") or "low"),
                source_quality=str(version_payload.get("source_quality") or "low"),
                refresh_note=str(topic_payload.get("last_refresh_note") or "") or None,
                new_targets=[],
                new_competitors=[],
                new_budget_signals=[],
                created_at=_normalize_datetime(version_payload.get("refreshed_at")),
            )
            db.add(version)
            db.flush()
            versions.append(version)

        if versions:
            ordered_versions = sorted(versions, key=lambda item: item.created_at, reverse=True)
            topic.last_report_version_id = ordered_versions[0].id

    db.commit()
    _WORKSPACE_BACKFILL_ATTEMPTED = True


def list_saved_views(db: Session) -> list[dict[str, Any]]:
    _maybe_backfill_workspace(db)
    views = db.scalars(
        select(ResearchSavedView)
        .where(ResearchSavedView.user_id == settings.single_user_id)
        .order_by(desc(ResearchSavedView.updated_at), desc(ResearchSavedView.created_at))
    ).all()
    return [_serialize_saved_view(item) for item in views]


def list_tracking_topics(db: Session) -> list[dict[str, Any]]:
    _maybe_backfill_workspace(db)
    topics = db.scalars(
        select(ResearchTrackingTopic)
        .where(ResearchTrackingTopic.user_id == settings.single_user_id)
        .order_by(desc(ResearchTrackingTopic.updated_at), desc(ResearchTrackingTopic.created_at))
    ).all()
    return [_serialize_topic(item) for item in topics]


def save_saved_view(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    _maybe_backfill_workspace(db)
    view_id = _coerce_uuid(payload.get("id")) if payload.get("id") else None
    existing = None
    if view_id is not None:
        existing = db.scalar(
            select(ResearchSavedView)
            .where(ResearchSavedView.id == view_id)
            .where(ResearchSavedView.user_id == settings.single_user_id)
        )
    view = existing or ResearchSavedView(id=view_id or uuid.uuid4(), user_id=settings.single_user_id)
    view.name = str(payload.get("name") or "未命名视图")
    view.query = str(payload.get("query") or "")
    view.filter_mode = str(payload.get("filter_mode") or "all")
    view.perspective = str(payload.get("perspective") or "all")
    view.region_filter = str(payload.get("region_filter") or "")
    view.industry_filter = str(payload.get("industry_filter") or "")
    view.action_type_filter = str(payload.get("action_type_filter") or "")
    view.focus_only = bool(payload.get("focus_only") or False)
    if existing is None and payload.get("created_at"):
        view.created_at = _normalize_datetime(payload.get("created_at"))
    db.add(view)
    db.commit()
    db.refresh(view)
    return _serialize_saved_view(view)


def delete_saved_view(db: Session, view_id: str) -> bool:
    _maybe_backfill_workspace(db)
    try:
        parsed_view_id = uuid.UUID(str(view_id))
    except ValueError:
        return False
    existing = db.scalar(
        select(ResearchSavedView)
        .where(ResearchSavedView.id == parsed_view_id)
        .where(ResearchSavedView.user_id == settings.single_user_id)
    )
    if existing is None:
        return False
    db.delete(existing)
    db.commit()
    return True


def save_tracking_topic(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    _maybe_backfill_workspace(db)
    topic_id = _coerce_uuid(payload.get("id")) if payload.get("id") else None
    existing = None
    if topic_id is not None:
        existing = db.scalar(
            select(ResearchTrackingTopic)
            .where(ResearchTrackingTopic.id == topic_id)
            .where(ResearchTrackingTopic.user_id == settings.single_user_id)
        )
    topic = existing or ResearchTrackingTopic(id=topic_id or uuid.uuid4(), user_id=settings.single_user_id)
    topic.name = str(payload.get("name") or "未命名专题")
    topic.keyword = str(payload.get("keyword") or "")
    topic.research_focus = str(payload.get("research_focus") or "")
    topic.perspective = str(payload.get("perspective") or "all")
    topic.region_filter = str(payload.get("region_filter") or "")
    topic.industry_filter = str(payload.get("industry_filter") or "")
    topic.notes = str(payload.get("notes") or "")
    if existing is None and payload.get("created_at"):
        topic.created_at = _normalize_datetime(payload.get("created_at"))
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return _serialize_topic(topic)


def get_tracking_topic(db: Session, topic_id: str) -> dict[str, Any] | None:
    _maybe_backfill_workspace(db)
    try:
        parsed_topic_id = uuid.UUID(str(topic_id))
    except ValueError:
        return None
    topic = db.scalar(
        select(ResearchTrackingTopic)
        .where(ResearchTrackingTopic.id == parsed_topic_id)
        .where(ResearchTrackingTopic.user_id == settings.single_user_id)
    )
    if topic is None:
        return None
    return _serialize_topic(topic)


def get_latest_tracking_topic_report_payload(db: Session, topic_id: str) -> dict[str, Any] | None:
    _maybe_backfill_workspace(db)
    try:
        parsed_topic_id = uuid.UUID(str(topic_id))
    except ValueError:
        return None
    version = db.scalar(
        select(ResearchReportVersion)
        .where(ResearchReportVersion.topic_id == parsed_topic_id)
        .order_by(desc(ResearchReportVersion.created_at))
        .limit(1)
    )
    if version is None or not isinstance(version.report_payload, dict):
        return None
    return version.report_payload


def list_tracking_topic_versions(db: Session, topic_id: str) -> list[dict[str, Any]]:
    _maybe_backfill_workspace(db)
    try:
        parsed_topic_id = uuid.UUID(str(topic_id))
    except ValueError:
        return []
    versions = db.scalars(
        select(ResearchReportVersion)
        .join(ResearchTrackingTopic, ResearchTrackingTopic.id == ResearchReportVersion.topic_id)
        .where(ResearchTrackingTopic.user_id == settings.single_user_id)
        .where(ResearchReportVersion.topic_id == parsed_topic_id)
        .order_by(desc(ResearchReportVersion.created_at))
    ).all()
    return [_serialize_version_detail(item) for item in versions]


def get_tracking_topic_version(db: Session, topic_id: str, version_id: str) -> dict[str, Any] | None:
    _maybe_backfill_workspace(db)
    try:
        parsed_topic_id = uuid.UUID(str(topic_id))
        parsed_version_id = uuid.UUID(str(version_id))
    except ValueError:
        return None
    version = db.scalar(
        select(ResearchReportVersion)
        .join(ResearchTrackingTopic, ResearchTrackingTopic.id == ResearchReportVersion.topic_id)
        .where(ResearchTrackingTopic.user_id == settings.single_user_id)
        .where(ResearchReportVersion.topic_id == parsed_topic_id)
        .where(ResearchReportVersion.id == parsed_version_id)
    )
    if version is None:
        return None
    return _serialize_version_detail(version)


def mark_tracking_topic_refreshed(
    db: Session,
    topic_id: str,
    *,
    last_refreshed_at: str | datetime,
    last_report_entry_id: str | None,
    last_report_title: str | None,
    source_count: int = 0,
    evidence_density: str = "low",
    source_quality: str = "low",
    last_refresh_note: str | None = None,
    last_refresh_new_targets: list[str] | None = None,
    last_refresh_new_competitors: list[str] | None = None,
    last_refresh_new_budget_signals: list[str] | None = None,
    report_payload: dict[str, Any] | None = None,
    action_cards_payload: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    _maybe_backfill_workspace(db)
    try:
        parsed_topic_id = uuid.UUID(str(topic_id))
    except ValueError:
        return None
    topic = db.scalar(
        select(ResearchTrackingTopic)
        .where(ResearchTrackingTopic.id == parsed_topic_id)
        .where(ResearchTrackingTopic.user_id == settings.single_user_id)
    )
    if topic is None:
        return None

    entry_uuid: uuid.UUID | None = None
    if last_report_entry_id:
        try:
            entry_uuid = uuid.UUID(str(last_report_entry_id))
        except ValueError:
            entry_uuid = None
    version = ResearchReportVersion(
        topic_id=topic.id,
        knowledge_entry_id=entry_uuid,
        report_title=str(last_report_title or "未命名研报"),
        report_payload=report_payload or {},
        action_cards_payload=action_cards_payload or [],
        source_count=int(source_count or 0),
        evidence_density=str(evidence_density or "low"),
        source_quality=str(source_quality or "low"),
        refresh_note=str(last_refresh_note or "") or None,
        new_targets=list(last_refresh_new_targets or []),
        new_competitors=list(last_refresh_new_competitors or []),
        new_budget_signals=list(last_refresh_new_budget_signals or []),
        created_at=_normalize_datetime(last_refreshed_at),
    )
    db.add(version)
    db.flush()

    topic.last_refreshed_at = _normalize_datetime(last_refreshed_at)
    topic.last_refresh_status = "succeeded"
    topic.last_refresh_error = None
    topic.last_refresh_note = str(last_refresh_note or "")
    topic.last_refresh_new_targets = list(last_refresh_new_targets or [])
    topic.last_refresh_new_competitors = list(last_refresh_new_competitors or [])
    topic.last_refresh_new_budget_signals = list(last_refresh_new_budget_signals or [])
    topic.last_report_version_id = version.id
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return _serialize_topic(topic, versions=list_tracking_topic_version_models(db, topic.id))


def mark_tracking_topic_refresh_started(db: Session, topic_id: str, *, note: str | None = None) -> dict[str, Any] | None:
    _maybe_backfill_workspace(db)
    try:
        parsed_topic_id = uuid.UUID(str(topic_id))
    except ValueError:
        return None
    topic = db.scalar(
        select(ResearchTrackingTopic)
        .where(ResearchTrackingTopic.id == parsed_topic_id)
        .where(ResearchTrackingTopic.user_id == settings.single_user_id)
    )
    if topic is None:
        return None
    topic.last_refresh_status = "running"
    topic.last_refresh_error = None
    topic.last_refresh_note = str(note or "")
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return _serialize_topic(topic)


def mark_tracking_topic_refresh_failed(db: Session, topic_id: str, *, error: str, note: str | None = None) -> dict[str, Any] | None:
    _maybe_backfill_workspace(db)
    try:
        parsed_topic_id = uuid.UUID(str(topic_id))
    except ValueError:
        return None
    topic = db.scalar(
        select(ResearchTrackingTopic)
        .where(ResearchTrackingTopic.id == parsed_topic_id)
        .where(ResearchTrackingTopic.user_id == settings.single_user_id)
    )
    if topic is None:
        return None
    topic.last_refresh_status = "failed"
    topic.last_refresh_error = str(error or "")
    topic.last_refresh_note = str(note or "")
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return _serialize_topic(topic)


def delete_tracking_topic(db: Session, topic_id: str) -> bool:
    _maybe_backfill_workspace(db)
    try:
        parsed_topic_id = uuid.UUID(str(topic_id))
    except ValueError:
        return False
    topic = db.scalar(
        select(ResearchTrackingTopic)
        .where(ResearchTrackingTopic.id == parsed_topic_id)
        .where(ResearchTrackingTopic.user_id == settings.single_user_id)
    )
    if topic is None:
        return False
    db.delete(topic)
    db.commit()
    return True


def list_tracking_topic_version_models(db: Session, topic_id: uuid.UUID) -> list[ResearchReportVersion]:
    return db.scalars(
        select(ResearchReportVersion)
        .where(ResearchReportVersion.topic_id == topic_id)
        .order_by(desc(ResearchReportVersion.created_at))
    ).all()
