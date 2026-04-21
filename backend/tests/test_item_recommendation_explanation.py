from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.items import _to_item_out
from app.core.config import get_settings
from app.db.base import Base
from app.models import Item, ItemTag, User
from app.services.feedback_service import apply_feedback
from app.services.preference_service import capture_preference_snapshot


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def test_item_out_contains_visible_preference_explanations() -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

        seed_item = Item(
            user_id=settings.single_user_id,
            source_type="url",
            source_url="https://openai.com/blog/seed",
            source_domain="openai.com",
            title="Seed item",
            short_summary="AI agent seed",
            long_summary="AI agent seed long summary",
            score_value=4.8,
            action_suggestion="deep_read",
            status="ready",
            created_at=datetime.now(timezone.utc),
        )
        seed_item.tags = [ItemTag(tag_name="AI"), ItemTag(tag_name="Agent")]
        db.add(seed_item)
        db.flush()
        apply_feedback(db, user_id=settings.single_user_id, item=seed_item, feedback_type="save")
        snapshot, _summary = capture_preference_snapshot(db, settings.single_user_id)
        db.commit()

        candidate = Item(
            user_id=settings.single_user_id,
            source_type="url",
            source_url="https://openai.com/blog/candidate",
            source_domain="openai.com",
            title="Candidate item",
            short_summary="Latest agent workflow",
            long_summary="Latest agent workflow with new reasoning steps",
            score_value=4.5,
            action_suggestion="later",
            status="ready",
            created_at=datetime.now(timezone.utc),
        )
        candidate.tags = [ItemTag(tag_name="AI"), ItemTag(tag_name="Workflow")]
        db.add(candidate)
        db.commit()

        out = _to_item_out(db, candidate, preference_version=str(snapshot.id))

        assert (out.topic_match_score or 0) > 50
        assert (out.source_match_score or 0) > 50
        assert any("主题" in entry for entry in out.matched_preferences)
        assert any("来源" in entry for entry in out.matched_preferences)
        assert len(out.why_recommended) >= 2
        assert out.preference_version == str(snapshot.id)
    finally:
        db.close()
