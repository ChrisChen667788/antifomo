from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, desc, func, select
from sqlalchemy.orm import Session

from app.models.entities import Feedback, PreferenceSnapshot, SourcePreference, TopicPreference
from app.schemas.preferences import PreferenceScoreOut, PreferenceSummaryOut
from app.services.recommender import map_source_preference_score, map_topic_preference_score


def _normalize_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def _serialize_topic_preference(pref: TopicPreference) -> PreferenceScoreOut:
    raw_score = float(pref.preference_score or 0)
    return PreferenceScoreOut(
        key=pref.tag_name,
        preference_score=raw_score,
        mapped_score=round(map_topic_preference_score([raw_score]), 2),
        updated_at=_normalize_timestamp(pref.updated_at),
    )


def _serialize_source_preference(pref: SourcePreference) -> PreferenceScoreOut:
    raw_score = float(pref.preference_score or 0)
    return PreferenceScoreOut(
        key=pref.source_domain,
        preference_score=raw_score,
        mapped_score=round(map_source_preference_score(raw_score), 2),
        updated_at=_normalize_timestamp(pref.updated_at),
    )


def resolve_preference_version(db: Session, user_id: UUID) -> str:
    latest_snapshot = db.scalar(
        select(PreferenceSnapshot)
        .where(PreferenceSnapshot.user_id == user_id)
        .order_by(desc(PreferenceSnapshot.created_at))
        .limit(1)
    )
    if latest_snapshot:
        return str(latest_snapshot.id)

    timestamps = [
        db.scalar(select(func.max(TopicPreference.updated_at)).where(TopicPreference.user_id == user_id)),
        db.scalar(select(func.max(SourcePreference.updated_at)).where(SourcePreference.user_id == user_id)),
        db.scalar(select(func.max(Feedback.created_at)).where(Feedback.user_id == user_id)),
    ]
    normalized = [_normalize_timestamp(value) for value in timestamps if value is not None]
    if not normalized:
        return "initial"
    return max(normalized).isoformat()


def build_preference_summary(db: Session, user_id: UUID, *, limit: int = 6) -> PreferenceSummaryOut:
    db.flush()
    tag_rows = list(
        db.scalars(
            select(TopicPreference)
            .where(TopicPreference.user_id == user_id)
            .where(TopicPreference.preference_score != 0)
            .order_by(desc(TopicPreference.preference_score), desc(TopicPreference.updated_at))
            .limit(max(1, limit))
        )
    )
    source_rows = list(
        db.scalars(
            select(SourcePreference)
            .where(SourcePreference.user_id == user_id)
            .where(SourcePreference.preference_score != 0)
            .order_by(desc(SourcePreference.preference_score), desc(SourcePreference.updated_at))
            .limit(max(1, limit))
        )
    )
    feedback_total = int(
        db.scalar(select(func.count(Feedback.id)).where(Feedback.user_id == user_id)) or 0
    )
    last_feedback_at = _normalize_timestamp(
        db.scalar(select(func.max(Feedback.created_at)).where(Feedback.user_id == user_id))
    )
    recent_feedback_counts = {
        str(feedback_type): int(count or 0)
        for feedback_type, count in db.execute(
            select(Feedback.feedback_type, func.count(Feedback.id))
            .where(Feedback.user_id == user_id)
            .group_by(Feedback.feedback_type)
        ).all()
    }
    latest_snapshot = db.scalar(
        select(PreferenceSnapshot)
        .where(PreferenceSnapshot.user_id == user_id)
        .order_by(desc(PreferenceSnapshot.created_at))
        .limit(1)
    )

    return PreferenceSummaryOut(
        user_id=user_id,
        generated_at=datetime.now(timezone.utc),
        preference_version=resolve_preference_version(db, user_id),
        feedback_total=feedback_total,
        last_feedback_at=last_feedback_at,
        recent_feedback_counts=recent_feedback_counts,
        top_tags=[_serialize_topic_preference(pref) for pref in tag_rows],
        top_domains=[_serialize_source_preference(pref) for pref in source_rows],
        snapshot_id=latest_snapshot.id if latest_snapshot else None,
    )


def capture_preference_snapshot(
    db: Session,
    user_id: UUID,
    *,
    limit: int = 6,
) -> tuple[PreferenceSnapshot, PreferenceSummaryOut]:
    summary = build_preference_summary(db, user_id, limit=limit)
    snapshot = PreferenceSnapshot(
        user_id=user_id,
        top_tags=[entry.model_dump(mode="json") for entry in summary.top_tags],
        top_domains=[entry.model_dump(mode="json") for entry in summary.top_domains],
        snapshot_payload={
            "feedback_total": summary.feedback_total,
            "last_feedback_at": summary.last_feedback_at.isoformat() if summary.last_feedback_at else None,
            "recent_feedback_counts": summary.recent_feedback_counts,
        },
    )
    db.add(snapshot)
    db.flush()
    return snapshot, summary.model_copy(
        update={
            "snapshot_id": snapshot.id,
            "preference_version": str(snapshot.id),
        }
    )


def reset_preferences(db: Session, user_id: UUID, *, scope: str = "all") -> PreferenceSummaryOut:
    safe_scope = scope if scope in {"all", "topics", "sources"} else "all"
    if safe_scope in {"all", "topics"}:
        db.execute(delete(TopicPreference).where(TopicPreference.user_id == user_id))
    if safe_scope in {"all", "sources"}:
        db.execute(delete(SourcePreference).where(SourcePreference.user_id == user_id))
    snapshot, summary = capture_preference_snapshot(db, user_id)
    db.commit()
    db.refresh(snapshot)
    return summary


def boost_preference(
    db: Session,
    user_id: UUID,
    *,
    dimension: str,
    key: str,
    delta: float,
) -> tuple[float, PreferenceSummaryOut]:
    safe_key = key.strip()
    if not safe_key:
        raise ValueError("key is required")

    delta_decimal = Decimal(str(delta))
    if dimension == "topic":
        pref = db.scalar(
            select(TopicPreference).where(
                TopicPreference.user_id == user_id,
                TopicPreference.tag_name == safe_key,
            )
        )
        if not pref:
            pref = TopicPreference(user_id=user_id, tag_name=safe_key, preference_score=Decimal("0"))
            db.add(pref)
        pref.preference_score = Decimal(pref.preference_score or 0) + delta_decimal
        updated_score = float(pref.preference_score)
    else:
        pref = db.scalar(
            select(SourcePreference).where(
                SourcePreference.user_id == user_id,
                SourcePreference.source_domain == safe_key,
            )
        )
        if not pref:
            pref = SourcePreference(user_id=user_id, source_domain=safe_key, preference_score=Decimal("0"))
            db.add(pref)
        pref.preference_score = Decimal(pref.preference_score or 0) + delta_decimal
        updated_score = float(pref.preference_score)

    capture_preference_snapshot(db, user_id)
    db.commit()
    return updated_score, build_preference_summary(db, user_id)
