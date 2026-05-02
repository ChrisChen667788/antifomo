from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.entities import Item, ItemTag, User
from app.services.feedback_service import apply_feedback
from app.services.knowledge_cleaning_service import clean_knowledge_content, is_low_signal_knowledge_payload
from app.services.knowledge_service import create_or_get_standalone_knowledge_entry, ensure_knowledge_rule, maybe_auto_archive_item


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


def test_knowledge_cleaning_removes_placeholder_and_duplicate_rows() -> None:
    content = "\n".join(
        [
            "暂无可归档内容",
            "AI 标识监管要求平台补齐显著标识和用户提示。",
            "AI 标识监管要求平台补齐显著标识和用户提示。",
            "微信扫一扫 听全文",
            "下一步应核验监管公告和平台整改口径。",
        ]
    )

    cleaned = clean_knowledge_content(content)

    assert "暂无可归档内容" not in cleaned
    assert "微信扫一扫" not in cleaned
    assert cleaned.count("AI 标识监管") == 1
    assert "下一步应核验" in cleaned


def test_standalone_knowledge_entry_sanitizes_low_signal_content() -> None:
    db = _new_session()
    try:
        user = User(id=uuid.uuid4(), name="demo")
        db.add(user)
        db.flush()

        entry, created = create_or_get_standalone_knowledge_entry(
            db,
            user_id=user.id,
            title="placeholder",
            content="暂无可归档内容\n政务云采购项目出现预算和招标窗口。\n政务云采购项目出现预算和招标窗口。",
        )

        assert created is True
        assert entry.title == "知识卡片"
        assert entry.content == "政务云采购项目出现预算和招标窗口。"
        assert not is_low_signal_knowledge_payload(entry.title, entry.content)
    finally:
        db.close()
