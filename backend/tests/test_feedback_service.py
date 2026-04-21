from __future__ import annotations

from decimal import Decimal
import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.entities import Item, ItemTag, SourcePreference, TopicPreference, User
from app.services.feedback_service import apply_feedback


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def test_feedback_updates_topic_and_source_preferences() -> None:
    db = _new_session()
    try:
        user = User(id=uuid.uuid4(), name="demo")
        db.add(user)
        db.flush()

        item = Item(
            user_id=user.id,
            source_type="text",
            source_domain="36kr.com",
            title="AI Agent 观察",
            raw_content="demo",
            status="ready",
            tags=[ItemTag(tag_name="AI Agent"), ItemTag(tag_name="创业")],
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        apply_feedback(db, user_id=user.id, item=item, feedback_type="save")
        db.commit()
        apply_feedback(db, user_id=user.id, item=item, feedback_type="ignore")
        db.commit()

        topic_scores = {
            row.tag_name: Decimal(row.preference_score)
            for row in db.scalars(
                select(TopicPreference).where(TopicPreference.user_id == user.id)
            )
        }
        source_pref = db.scalar(
            select(SourcePreference).where(
                SourcePreference.user_id == user.id,
                SourcePreference.source_domain == "36kr.com",
            )
        )

        assert topic_scores["AI Agent"] == Decimal("1")
        assert topic_scores["创业"] == Decimal("1")
        assert source_pref is not None
        assert Decimal(source_pref.preference_score) == Decimal("1")
    finally:
        db.close()
