from __future__ import annotations

import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
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


def test_process_item_uses_shorter_timeout_for_ocr_items(monkeypatch) -> None:
    db = _new_session()
    user = User(id=uuid.uuid4(), name="demo")
    db.add(user)
    db.flush()

    calls: list[tuple[str, int | None]] = []

    def _summarize(**kwargs):
        calls.append(("summarize", kwargs.get("timeout_seconds")))
        return SummarizeResult(
            display_title="OCR 标题",
            short_summary="OCR 摘要",
            long_summary="OCR 长摘要",
            key_points=["a"],
        )

    def _tags(**kwargs):
        calls.append(("tags", kwargs.get("timeout_seconds")))
        return TagsResult(tags=["OCR"])

    def _score(**kwargs):
        calls.append(("score", kwargs.get("timeout_seconds")))
        return ScoreResult(
            score_value=3.2,
            action_suggestion="later",
            recommendation_reason=["OCR 快速处理"],
            content_density="medium",
            novelty_level="medium",
        )

    monkeypatch.setattr(item_processor.summarizer, "summarize", _summarize)
    monkeypatch.setattr(item_processor.tagger, "extract_tags", _tags)
    monkeypatch.setattr(item_processor.scorer, "score", _score)

    item = Item(
        user_id=user.id,
        source_type="plugin",
        source_url="https://mp.weixin.qq.com/s/demo",
        title="截图文章",
        raw_content="标题：截图文章\n正文：" + ("这是一段 OCR 正文内容。" * 20),
        ingest_route="ocr",
        fallback_used=False,
        status="pending",
    )

    processed = item_processor.process_item(db, item, output_language="zh-CN")

    assert processed.status == "ready"
    expected_timeout = get_settings().ocr_item_llm_timeout_seconds
    assert calls == [
        ("summarize", expected_timeout),
        ("tags", expected_timeout),
        ("score", expected_timeout),
    ]


def test_process_item_uses_mock_path_for_mock_ocr_fallback(monkeypatch) -> None:
    db = _new_session()
    user = User(id=uuid.uuid4(), name="demo")
    db.add(user)
    db.flush()

    def _unexpected_primary(**_kwargs):
        raise AssertionError("primary item llm path should not run for mock OCR fallback")

    monkeypatch.setattr(item_processor.summarizer, "summarize", _unexpected_primary)
    monkeypatch.setattr(item_processor.tagger, "extract_tags", _unexpected_primary)
    monkeypatch.setattr(item_processor.scorer, "score", _unexpected_primary)

    item = Item(
        user_id=user.id,
        source_type="plugin",
        source_url="https://mp.weixin.qq.com/s/mock-ocr",
        title="OCR 模拟截图",
        raw_content="标题：OCR 模拟截图\n正文：" + ("当前运行在本地 OCR 模拟模式。" * 12),
        ingest_route="ocr",
        fallback_used=True,
        status="pending",
    )

    processed = item_processor.process_item(db, item, output_language="zh-CN")

    assert processed.status == "ready"
    assert processed.short_summary
    assert processed.score_value is not None
