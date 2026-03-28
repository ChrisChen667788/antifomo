from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models import Item, ItemTag, User
from app.services.feedback_service import apply_feedback
from app.services.preference_service import (
    boost_preference,
    build_preference_summary,
    capture_preference_snapshot,
    reset_preferences,
)


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def test_preference_summary_exposes_top_tags_domains_and_snapshot() -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

        item = Item(
            user_id=settings.single_user_id,
            source_type="url",
            source_url="https://openai.com/blog/demo",
            source_domain="openai.com",
            title="Agent signal",
            short_summary="agent signal",
            long_summary="agent signal long summary",
            score_value=4.6,
            status="ready",
            created_at=datetime.now(timezone.utc),
        )
        item.tags = [
            ItemTag(tag_name="AI"),
            ItemTag(tag_name="Agent"),
        ]
        db.add(item)
        db.flush()

        apply_feedback(db, user_id=settings.single_user_id, item=item, feedback_type="like")
        snapshot, summary = capture_preference_snapshot(db, settings.single_user_id)
        db.commit()

        rebuilt = build_preference_summary(db, settings.single_user_id)

        assert summary.snapshot_id == snapshot.id
        assert summary.preference_version == str(snapshot.id)
        assert summary.feedback_total == 1
        assert rebuilt.feedback_total == 1
        assert any(entry.key == "AI" for entry in rebuilt.top_tags)
        assert any(entry.key == "Agent" for entry in rebuilt.top_tags)
        assert any(entry.key == "openai.com" for entry in rebuilt.top_domains)
        assert rebuilt.preference_version == str(snapshot.id)
    finally:
        db.close()


def test_preference_boost_and_reset_update_summary() -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

        updated_score, boosted = boost_preference(
            db,
            settings.single_user_id,
            dimension="topic",
            key="AI",
            delta=2.0,
        )

        assert updated_score == 2.0
        assert boosted.top_tags
        assert boosted.top_tags[0].key == "AI"

        reset_summary = reset_preferences(db, settings.single_user_id, scope="topics")
        assert reset_summary.top_tags == []
    finally:
        db.close()
