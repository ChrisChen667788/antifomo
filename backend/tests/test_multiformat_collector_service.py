from __future__ import annotations

import base64

from fastapi import BackgroundTasks
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.api import collector_wechat_favorites as collector_favorites_api
from app.core.config import get_settings
from app.db.base import Base
from app.models import (
    CollectorFeedEntry,
    CollectorFeedSource,
    CollectorImportBatch,
    Feedback,
    Item,
    UploadedDocument,
    User,
)
from app.schemas.collector import CollectorWechatFavoriteImportRequest, CollectorWechatFavoritePreviewRequest
from app.services import collector_multiformat_service as multiformat_service


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def test_sync_rss_feeds_creates_feed_entries_and_items(monkeypatch) -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

        def fake_fetch(_url: str, timeout_seconds: int = 12) -> bytes:
            return """
            <rss version="2.0">
              <channel>
                <title>Demo Feed</title>
                <item>
                  <title>Demo RSS Entry</title>
                  <link>https://example.com/rss-entry</link>
                  <description>这是一个来自 RSS 的正文摘要，用来验证统一 Item 入流。</description>
                  <pubDate>Sat, 28 Mar 2026 12:30:00 +0000</pubDate>
                </item>
              </channel>
            </rss>
            """.encode("utf-8")

        monkeypatch.setattr(multiformat_service, "_fetch_url_bytes", fake_fetch)
        monkeypatch.setattr(multiformat_service, "process_item_in_session", _fast_process_item)

        feed = multiformat_service.save_feed_source(
            db,
            user_id=settings.single_user_id,
            feed_type="rss",
            source_url="https://example.com/feed.xml",
            title="",
            note="",
        )
        results = multiformat_service.sync_rss_feeds(
            db,
            user_id=settings.single_user_id,
            feed_id=feed.id,
            limit=4,
            output_language="zh-CN",
        )

        assert len(results) == 1
        assert results[0]["new_items"] == 1
        assert db.scalar(select(CollectorFeedSource).where(CollectorFeedSource.id == feed.id)).last_synced_at is not None
        assert db.scalar(select(CollectorFeedEntry).where(CollectorFeedEntry.feed_id == feed.id)) is not None
        item = db.scalar(select(Item).where(Item.source_url == "https://example.com/rss-entry"))
        assert item is not None
        assert item.ingest_route == "rss_feed"
        assert item.status == "ready"
    finally:
        db.close()


def test_file_newsletter_and_youtube_ingest_create_items_and_document(monkeypatch) -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()
        monkeypatch.setattr(multiformat_service, "process_item_in_session", _fast_process_item)

        newsletter = multiformat_service.ingest_newsletter(
            db,
            user_id=settings.single_user_id,
            title="Demo Newsletter",
            raw_content="这里是 newsletter 正文，包含足够长度来完成摘要和打分。" * 4,
            sender="Demo Sender",
            source_url="https://example.com/newsletter/demo",
            output_language="zh-CN",
        )
        assert newsletter["item"].ingest_route == "newsletter"
        assert newsletter["item"].status == "ready"

        uploaded = multiformat_service.ingest_uploaded_document(
            db,
            user_id=settings.single_user_id,
            file_name="demo.txt",
            mime_type="text/plain",
            file_base64=base64.b64encode(("这是文件正文。" * 40).encode("utf-8")).decode("ascii"),
            extracted_text=None,
            title="Demo File",
            source_url=None,
            output_language="zh-CN",
        )
        assert uploaded["item"].ingest_route == "file_upload"
        assert uploaded["document"].id is not None
        assert uploaded["parse_status"] == "parsed"
        stored_document = db.scalar(select(UploadedDocument).where(UploadedDocument.id == uploaded["document"].id))
        assert stored_document is not None

        monkeypatch.setattr(multiformat_service, "_fetch_youtube_title", lambda _url: "Demo Video")
        youtube = multiformat_service.ingest_youtube_transcript(
            db,
            user_id=settings.single_user_id,
            video_url="https://www.youtube.com/watch?v=demo1234567",
            transcript_text="这是 YouTube transcript 文本。" * 30,
            title=None,
            output_language="zh-CN",
        )
        assert youtube["item"].ingest_route == "youtube_transcript"
        assert youtube["transcript_attached"] is True
        assert youtube["item"].status == "ready"
    finally:
        db.close()


def test_parse_wechat_favorites_export_extracts_article_urls() -> None:
    candidates = multiformat_service.parse_wechat_favorites_export(
        """
        <html><body>
          <a href="https://mp.weixin.qq.com/s?__biz=MzDemo&amp;mid=2247483650&amp;idx=1&amp;sn=abc123&amp;scene=21#wechat_redirect">
            AI 方案架构收藏
          </a>
          https://mp.weixin.qq.com/s/demo-short?from=timeline
          https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz=MzDemo
        </body></html>
        """,
        limit=10,
    )

    assert len(candidates) == 2
    assert candidates[0].title == "AI 方案架构收藏"
    assert candidates[0].source_url == (
        "https://mp.weixin.qq.com/s?__biz=MzDemo&mid=2247483650&idx=1&sn=abc123"
    )
    assert candidates[1].source_url == "https://mp.weixin.qq.com/s/demo-short"


def test_parse_wechat_favorites_export_decodes_escaped_and_encoded_urls() -> None:
    candidates = multiformat_service.parse_wechat_favorites_export(
        r"""
        {"title":"JSON 转义收藏","url":"https:\/\/mp.weixin.qq.com\/s?__biz=MzDemo\u0026mid=2247483653\u0026idx=1\u0026sn=json123\u0026from=timeline"}
        [InternetShortcut]
        URL=https%3A%2F%2Fmp.weixin.qq.com%2Fs%3F__biz%3DMzDemo%26mid%3D2247483654%26idx%3D1%26sn%3Dencoded456%26scene%3D1
        """,
        limit=10,
    )

    assert [candidate.source_url for candidate in candidates] == [
        "https://mp.weixin.qq.com/s?__biz=MzDemo&mid=2247483653&idx=1&sn=json123",
        "https://mp.weixin.qq.com/s?__biz=MzDemo&mid=2247483654&idx=1&sn=encoded456",
    ]


def test_parse_wechat_favorites_export_can_preview_text_blocks() -> None:
    candidates = multiformat_service.parse_wechat_favorites_export(
        """
        标题：微信收藏里的方案架构文章

        这是一段从微信收藏复制出来的公众号正文，包含足够长的内容，用于验证没有链接时也能生成候选卡片。
        它讨论客户业务场景、系统集成依赖、数据治理边界和后续交付动作，长度足以进入文本块解析。
        """,
        limit=10,
    )

    assert len(candidates) == 1
    assert candidates[0].extraction_mode == "wechat_favorites_text"
    assert candidates[0].source_url and candidates[0].source_url.startswith("https://wechat.local/favorites/")


def test_parse_wechat_favorites_export_keeps_mixed_url_and_text_blocks() -> None:
    candidates = multiformat_service.parse_wechat_favorites_export(
        """
        收藏一：AI 中台采购清单
        https://mp.weixin.qq.com/s?__biz=MzDemo&mid=2247483652&idx=1&sn=abc789&scene=1

        这是一段没有原文链接的微信收藏正文，讨论客户现场调研、系统集成依赖、非功能要求和验收材料。
        它需要在同一次导入中保留下来，不能因为前面已经识别到公众号链接就被跳过。
        """,
        limit=10,
    )

    assert [candidate.extraction_mode for candidate in candidates] == [
        "wechat_favorites_url",
        "wechat_favorites_text",
    ]
    assert candidates[1].source_url and candidates[1].source_url.startswith("https://wechat.local/favorites/")


def test_import_wechat_favorites_creates_items_and_deduplicates(monkeypatch) -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()
        monkeypatch.setattr(multiformat_service, "process_item_in_session", _fast_process_item)

        export_text = """
        收藏一：客户 AI 中台规划
        https://mp.weixin.qq.com/s?__biz=MzDemo&mid=2247483651&idx=1&sn=def456&scene=1
        """
        first = multiformat_service.import_wechat_favorites(
            db,
            user_id=settings.single_user_id,
            export_text=export_text,
            output_language="zh-CN",
            process_immediately=True,
        )
        assert first["created"] == 1
        assert first["deduplicated"] == 0
        assert first["batch_id"]
        item = db.scalar(select(Item).where(Item.ingest_route == "wechat_favorites"))
        assert item is not None
        assert item.source_type == "url"
        assert item.source_url == "https://mp.weixin.qq.com/s?__biz=MzDemo&mid=2247483651&idx=1&sn=def456"
        assert item.status == "ready"
        batch = db.scalar(select(CollectorImportBatch).where(CollectorImportBatch.id == first["batch"].id))
        assert batch is not None
        assert batch.total_candidates == 1
        assert batch.created_count == 1
        assert batch.item_ids == [str(item.id)]
        batch_response = collector_favorites_api.to_wechat_favorite_batch_response(db, batch)
        assert batch_response.ready == 1
        assert batch_response.review_item_ids == [item.id]

        db.add(Feedback(user_id=settings.single_user_id, item_id=item.id, feedback_type="save"))
        db.commit()
        triaged_response = collector_favorites_api.to_wechat_favorite_batch_response(db, batch)
        assert triaged_response.triaged == 1
        assert triaged_response.review_item_ids == []
        assert triaged_response.status == "reviewed"

        second = multiformat_service.import_wechat_favorites(
            db,
            user_id=settings.single_user_id,
            export_text=export_text,
            output_language="zh-CN",
            process_immediately=True,
        )
        assert second["created"] == 0
        assert second["deduplicated"] == 1
    finally:
        db.close()


def test_wechat_favorites_api_preview_import_and_restore_batch(monkeypatch) -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()
        monkeypatch.setattr(collector_favorites_api, "ensure_demo_user", lambda _db: None)

        preview = collector_favorites_api.preview_wechat_favorite_items(
            CollectorWechatFavoritePreviewRequest(
                export_text="""
                收藏一：AI 客户会议准备
                https://mp.weixin.qq.com/s?__biz=MzDemo&mid=2247483659&idx=1&sn=api123&scene=1
                """,
                limit=10,
            ),
            db,
        )

        assert preview.total_candidates == 1
        assert preview.url_candidates == 1
        assert preview.samples[0].source_url == (
            "https://mp.weixin.qq.com/s?__biz=MzDemo&mid=2247483659&idx=1&sn=api123"
        )

        imported = collector_favorites_api.import_wechat_favorite_items(
            CollectorWechatFavoriteImportRequest(
                export_text="""
                收藏一：AI 客户会议准备
                https://mp.weixin.qq.com/s?__biz=MzDemo&mid=2247483659&idx=1&sn=api123&scene=1
                """,
                process_immediately=False,
                limit=10,
            ),
            BackgroundTasks(),
            db,
        )

        assert imported.batch_id is not None
        assert imported.batch is not None
        assert imported.batch.status == "processing"
        assert imported.batch.processing == 1
        assert imported.batch.review_item_ids == imported.created_item_ids
        db.expire_all()
        assert db.get(CollectorImportBatch, imported.batch_id) is not None

        latest = collector_favorites_api.list_wechat_favorite_import_batches(limit=5, include_reviewed=False, db=db)
        assert latest.total == 1
        assert latest.items[0].id == imported.batch_id
        restored = collector_favorites_api.get_wechat_favorite_import_batch(imported.batch_id, db=db)
        assert restored.review_item_ids == imported.created_item_ids
    finally:
        db.close()


def _fast_process_item(db: Session, item: Item, *, output_language: str | None = None, auto_archive: bool = True) -> Item:
    del output_language, auto_archive
    item.clean_content = item.raw_content or ""
    item.short_summary = "stub summary"
    item.long_summary = "stub long summary"
    item.score_value = 3
    item.action_suggestion = "later"
    item.status = "ready"
    db.add(item)
    db.flush()
    return item
