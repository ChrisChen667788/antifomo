from __future__ import annotations

import base64

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models import CollectorFeedEntry, CollectorFeedSource, Item, UploadedDocument, User
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
