from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Feedback, Item, SourcePreference, TopicPreference


TOPIC_FEEDBACK_WEIGHTS = {
    "like": Decimal("3"),
    "save": Decimal("4"),
    "open_detail": Decimal("2"),
    "ignore": Decimal("-3"),
    "inaccurate": Decimal("-2"),
}

SOURCE_FEEDBACK_WEIGHTS = {
    "like": Decimal("2"),
    "save": Decimal("3"),
    "open_detail": Decimal("1"),
    "ignore": Decimal("-2"),
    "inaccurate": Decimal("-1"),
}


def _upsert_topic_preferences(db: Session, item: Item, feedback_type: str) -> None:
    weight = TOPIC_FEEDBACK_WEIGHTS.get(feedback_type, Decimal("0"))
    if weight == 0:
        return

    for tag in item.tags:
        pref = db.scalar(
            select(TopicPreference).where(
                TopicPreference.user_id == item.user_id,
                TopicPreference.tag_name == tag.tag_name,
            )
        )
        if not pref:
            pref = TopicPreference(
                user_id=item.user_id,
                tag_name=tag.tag_name,
                preference_score=Decimal("0"),
            )
            db.add(pref)
        pref.preference_score = Decimal(pref.preference_score) + weight


def _upsert_source_preference(db: Session, item: Item, feedback_type: str) -> None:
    if not item.source_domain:
        return
    weight = SOURCE_FEEDBACK_WEIGHTS.get(feedback_type, Decimal("0"))
    if weight == 0:
        return

    pref = db.scalar(
        select(SourcePreference).where(
            SourcePreference.user_id == item.user_id,
            SourcePreference.source_domain == item.source_domain,
        )
    )
    if not pref:
        pref = SourcePreference(
            user_id=item.user_id,
            source_domain=item.source_domain,
            preference_score=Decimal("0"),
        )
        db.add(pref)
    pref.preference_score = Decimal(pref.preference_score) + weight


def apply_feedback(
    db: Session,
    *,
    user_id,
    item: Item,
    feedback_type: str,
) -> Feedback:
    feedback = Feedback(
        user_id=user_id,
        item_id=item.id,
        feedback_type=feedback_type,
    )
    db.add(feedback)

    _upsert_topic_preferences(db, item, feedback_type)
    _upsert_source_preference(db, item, feedback_type)
    return feedback

