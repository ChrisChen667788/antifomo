from __future__ import annotations

import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.entities import Item, User
from app.services import item_processor
from app.services.llm_parser import ScoreResult, SummarizeResult, TagsResult


def _new_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def test_process_item_uses_refined_display_title(monkeypatch) -> None:
    db = _new_session()
    user = User(id=uuid.uuid4(), name="demo")
    db.add(user)
    db.flush()

    monkeypatch.setattr(
        item_processor.summarizer,
        "summarize",
        lambda **kwargs: SummarizeResult(
            display_title="更直接的主题标题",
            short_summary="短摘要",
            long_summary="长摘要",
            key_points=["a", "b", "c"],
        ),
    )
    monkeypatch.setattr(
        item_processor.tagger,
        "extract_tags",
        lambda **kwargs: TagsResult(tags=["测试"]),
    )
    monkeypatch.setattr(
        item_processor.scorer,
        "score",
        lambda **kwargs: ScoreResult(
            score_value=3.8,
            action_suggestion="deep_read",
            recommendation_reason=["信息增量高"],
            content_density="high",
            novelty_level="high",
        ),
    )

    item = Item(
        user_id=user.id,
        source_type="text",
        title="原标题很夸张",
        raw_content="这是一段用于测试的正文内容。" * 20,
        status="pending",
    )

    processed = item_processor.process_item(db, item, output_language="zh-CN")
    assert processed.title == "更直接的主题标题"
    assert processed.short_summary == "短摘要"
    assert processed.status == "ready"
