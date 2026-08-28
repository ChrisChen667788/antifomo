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


def test_wechat_metric_boilerplate_does_not_become_title_or_summary(monkeypatch) -> None:
    db = _new_session()
    user = User(id=uuid.uuid4(), name="demo")
    db.add(user)
    db.flush()

    captured: dict[str, str] = {}

    def _summarize(**kwargs):
        captured["clean_content"] = kwargs["clean_content"]
        return SummarizeResult(
            display_title="2026.04.29本文字数：1446，阅读时长大约2分钟",
            short_summary="近日，因未有效落实人工智能生成合成内容标识规定要求，剪映、猫箱、即梦AI等被网信部门约谈。",
            long_summary="监管部门围绕 AI 合成内容标识提出整改要求，相关 App 需要完善显著标识、用户提示和平台审核机制。",
            key_points=["AI 内容标识整改", "相关 App 被约谈"],
        )

    monkeypatch.setattr(item_processor.summarizer, "summarize", _summarize)
    monkeypatch.setattr(item_processor.tagger, "extract_tags", lambda **kwargs: TagsResult(tags=["AI治理"]))
    monkeypatch.setattr(
        item_processor.scorer,
        "score",
        lambda **kwargs: ScoreResult(score_value=4.1, action_suggestion="deep_read"),
    )

    item = Item(
        user_id=user.id,
        source_type="plugin",
        source_url="https://mp.weixin.qq.com/s/demo-ai-label",
        title="2026.04.29本文字数：1446，阅读时长大约2分钟",
        raw_content=(
            "标题：2026.04.29本文字数：1446，阅读时长大约2分钟\n"
            "正文：2026.04.29本文字数：1446，阅读时长大约2分钟作者｜第一财经 秦新安"
            "近日，因未有效落实人工智能生成合成内容标识规定要求，剪映、猫箱、即梦AI网站被网信部门约谈、责令改正、警告。"
            "相关平台需要补充显式标识、内容审核和用户提示机制。"
        ),
        status="pending",
    )

    processed = item_processor.process_item(db, item, output_language="zh-CN")

    assert "本文字数" not in captured["clean_content"]
    assert "阅读时长" not in captured["clean_content"]
    assert "本文字数" not in (processed.title or "")
    assert "剪映" in (processed.title or "")


def test_wechat_local_home_header_does_not_become_title(monkeypatch) -> None:
    db = _new_session()
    user = User(id=uuid.uuid4(), name="demo")
    db.add(user)
    db.flush()

    bad_header = "长安君 中央政法委长安剑 2026年5月9日 06:00"

    def _summarize(**kwargs):
        return SummarizeResult(
            display_title=bad_header,
            short_summary=(
                "长安君 中央政法委长安剑 2026年5月9日 06:00 北京649人 点击蓝字 可以关注我们喔！"
                "每天3分钟，速览天下事 5月9日星期六，封面新闻关注政法动态。"
            ),
            long_summary="每天3分钟，速览天下事，梳理政法、社会治理和公共事件动态。",
            key_points=["政法动态", "新闻速览"],
        )

    monkeypatch.setattr(item_processor.summarizer, "summarize", _summarize)
    monkeypatch.setattr(item_processor.tagger, "extract_tags", lambda **kwargs: TagsResult(tags=["政法"]))
    monkeypatch.setattr(
        item_processor.scorer,
        "score",
        lambda **kwargs: ScoreResult(score_value=3.2, action_suggestion="later"),
    )

    item = Item(
        user_id=user.id,
        source_type="plugin",
        source_url="https://wechat.local/article/942c1099361456c91a4fec6f25de8395e3d8e753",
        source_domain="wechat.local",
        title=bad_header,
        raw_content=(
            f"标题：{bad_header}\n"
            f"正文：{bad_header} 北京649人 点击蓝字 可以关注我们喔！"
            "每天3分钟，速览天下事 5月9日星期六，农历三月廿三，封面新闻关注政法动态。"
            "中央政法委长安剑发布多条公共治理观察，包含社会治理、公共安全和基层动态。"
        ),
        status="pending",
    )

    processed = item_processor.process_item(db, item, output_language="zh-CN")

    assert processed.status == "ready"
    assert processed.title
    assert "长安君 中央政法委长安剑" not in processed.title
    assert "06:00" not in processed.title
    assert "每天3分钟" in processed.title


def test_wechat_favorites_processing_stack_uses_strategy_llm(monkeypatch) -> None:
    strategy_service = object()
    monkeypatch.setattr(item_processor.settings, "wechat_favorites_llm_role", "strategy")
    monkeypatch.setattr(item_processor, "get_strategy_llm_service", lambda: strategy_service)
    item_processor.reset_wechat_processing_stack()

    summarizer, tagger, scorer = item_processor._resolve_wechat_processing_stack()

    assert summarizer.llm_service is strategy_service
    assert tagger.llm_service is strategy_service
    assert scorer.llm_service is strategy_service
    item_processor.reset_wechat_processing_stack()
