from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.entities import Item, ItemTag, User
from app.services.feedback_service import apply_feedback
from app.services.knowledge_service import ensure_knowledge_rule, maybe_auto_archive_item


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def test_auto_archive_creates_knowledge_entry_after_like_for_high_value_item() -> None:
    db = _new_session()
    try:
        user = User(id=uuid.uuid4(), name="demo")
        db.add(user)
        db.flush()

        item = Item(
            user_id=user.id,
            source_type="text",
            source_domain="36kr.com",
            title="AI Agent 浏览器进入加速期",
            raw_content="demo",
            short_summary="Agent Browser 正在从演示能力转向真实工作流。",
            long_summary="近期多家厂商发布 Agent Browser，竞争集中在执行能力、隐私控制和工作流集成。",
            score_value=Decimal("4.30"),
            action_suggestion="deep_read",
            status="ready",
            tags=[ItemTag(tag_name="AI Agent"), ItemTag(tag_name="浏览器")],
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        apply_feedback(db, user_id=user.id, item=item, feedback_type="like")
        db.flush()
        result = maybe_auto_archive_item(db, item=item, trigger_feedback_type="like")
        db.commit()

        assert result.status == "created"
        assert result.entry is not None
        assert result.entry.item_id == item.id
        assert "一句话概要" in result.entry.content
    finally:
        db.close()


def test_auto_archive_respects_threshold() -> None:
    db = _new_session()
    try:
        user = User(id=uuid.uuid4(), name="demo")
        db.add(user)
        db.flush()

        item = Item(
            user_id=user.id,
            source_type="text",
            source_domain="example.com",
            title="低价值内容",
            raw_content="demo",
            short_summary="信息密度一般。",
            long_summary="该内容只有少量新增信息。",
            score_value=Decimal("3.20"),
            action_suggestion="later",
            status="ready",
            tags=[ItemTag(tag_name="行业动态")],
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        rule = ensure_knowledge_rule(db, user.id)
        rule.min_score_value = Decimal("4.00")
        db.add(rule)
        db.flush()

        apply_feedback(db, user_id=user.id, item=item, feedback_type="save")
        db.flush()
        result = maybe_auto_archive_item(db, item=item, trigger_feedback_type="save")

        assert result.status == "skipped"
        assert result.reason == "below_threshold"
        assert result.entry is None
    finally:
        db.close()


def test_auto_archive_reuses_existing_entry_for_same_item() -> None:
    db = _new_session()
    try:
        user = User(id=uuid.uuid4(), name="demo")
        db.add(user)
        db.flush()

        item = Item(
            user_id=user.id,
            source_type="text",
            source_domain="example.com",
            title="高价值条目",
            raw_content="demo",
            short_summary="值得继续看。",
            long_summary="这是一条已经归档过的高价值内容。",
            score_value=Decimal("4.60"),
            action_suggestion="deep_read",
            status="ready",
            tags=[ItemTag(tag_name="AI")],
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        apply_feedback(db, user_id=user.id, item=item, feedback_type="save")
        db.flush()
        first = maybe_auto_archive_item(db, item=item, trigger_feedback_type="save")
        second = maybe_auto_archive_item(db, item=item, trigger_feedback_type="save")

        assert first.status == "created"
        assert second.status == "existing"
        assert first.entry is not None and second.entry is not None
        assert first.entry.id == second.entry.id
    finally:
        db.close()
