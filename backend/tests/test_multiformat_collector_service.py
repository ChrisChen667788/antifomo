from __future__ import annotations

import base64

from fastapi import BackgroundTasks
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api import collector_wechat_favorites as collector_favorites_api
from app.core.config import get_settings
from app.db.base import Base
from app.models import (
    CollectorFeedEntry,
    CollectorFeedSource,
    CollectorImportBatch,
    CollectorIngestAttempt,
    Feedback,
    Item,
    UploadedDocument,
    User,
)
from app.models.collector_evidence_entities import CollectorDocumentRevision
from app.schemas.collector import CollectorWechatFavoriteImportRequest, CollectorWechatFavoritePreviewRequest
from app.services import collector_multiformat_service as multiformat_service


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def _sqlite_dump(db: Session) -> str:
    connection = db.connection().connection
    driver_connection = getattr(connection, "driver_connection", connection)
    return "\n".join(driver_connection.iterdump())


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


def test_sync_rss_feeds_never_persists_signed_wechat_entry_url(monkeypatch) -> None:
    db = _new_session()
    settings = get_settings()
    transient_marker = "rss-private-ticket"
    signed_url = (
        "https://mp.weixin.qq.com/s?__biz=MzRss&mid=9&idx=1&sn=stable"
        f"&scene=21&pass_ticket={transient_marker}&key=temporary-rss-key"
    )
    canonical_url = (
        "https://mp.weixin.qq.com/s?__biz=MzRss&mid=9&idx=1&sn=stable"
    )
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

        def fake_fetch(_url: str, timeout_seconds: int = 12) -> bytes:
            del timeout_seconds
            escaped_url = signed_url.replace("&", "&amp;")
            return (
                "<rss version='2.0'><channel><title>WeChat Feed</title><item>"
                f"<title>Signed entry</title><link>{escaped_url}</link>"
                "</item></channel></rss>"
            ).encode("utf-8")

        monkeypatch.setattr(multiformat_service, "_fetch_url_bytes", fake_fetch)
        monkeypatch.setattr(multiformat_service, "process_item_in_session", _fast_process_item)
        feed = multiformat_service.save_feed_source(
            db,
            user_id=settings.single_user_id,
            feed_type="rss",
            source_url="https://example.com/wechat.xml",
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

        entry = db.scalar(select(CollectorFeedEntry).where(CollectorFeedEntry.feed_id == feed.id))
        item = db.scalar(select(Item).where(Item.source_url == canonical_url))
        assert results[0]["new_items"] == 1
        assert entry is not None
        assert entry.source_url == canonical_url
        assert item is not None
        assert canonical_url in str(item.raw_content)
        assert transient_marker not in _sqlite_dump(db)
        assert "temporary-rss-key" not in _sqlite_dump(db)
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


def test_changed_shorter_multiformat_payload_replaces_projection_and_reaches_processor(monkeypatch) -> None:
    db = _new_session()
    settings = get_settings()
    seen_raw: list[str] = []

    def capture_processor(db_session: Session, item: Item, **_kwargs) -> Item:
        seen_raw.append(str(getattr(item, "_collector_raw_evidence", "")))
        item.clean_content = item.raw_content
        item.status = "ready"
        db_session.add(item)
        return item

    try:
        db.add(User(id=settings.single_user_id, name="revision-demo"))
        db.commit()
        monkeypatch.setattr(multiformat_service, "process_item_in_session", capture_processor)

        source_url = "https://example.com/revision-shorter"
        long_raw = "标题：较长版本\n正文：" + ("长版本正文。" * 40)
        short_raw = "标题：短版本\n正文：内容已明确缩短。"
        multiformat_service._persist_item(
            db,
            user_id=settings.single_user_id,
            source_type="plugin",
            source_url=source_url,
            title="较长版本",
            raw_content=long_raw,
            output_language="zh-CN",
            ingest_route="newsletter",
            content_note="first",
            resolver="fixture",
            body_source="fixture_body",
        )
        changed = multiformat_service._persist_item(
            db,
            user_id=settings.single_user_id,
            source_type="plugin",
            source_url=source_url,
            title="短版本",
            raw_content=short_raw,
            output_language="zh-CN",
            ingest_route="newsletter",
            content_note="changed",
            resolver="fixture",
            body_source="fixture_body",
        )

        assert changed["revision_created"] is True
        assert changed["item"].raw_content == "标题：短版本 正文：内容已明确缩短。"
        assert seen_raw == [long_raw, short_raw]
        assert db.scalar(select(func.count()).select_from(CollectorDocumentRevision)) == 2
    finally:
        db.close()


def test_parse_wechat_favorites_export_extracts_article_urls() -> None:
    candidates = multiformat_service.parse_wechat_favorites_export(
        """
        <html><body>
          <a href="https://mp.weixin.qq.com/s?__biz=MzDemo&amp;mid=2247483650&amp;idx=1&amp;sn=abc123&amp;scene=21&amp;pass_ticket=parser-secret#wechat_redirect">
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
    assert candidates[0].fetch_url == (
        "https://mp.weixin.qq.com/s?__biz=MzDemo&mid=2247483650&idx=1&sn=abc123"
        "&scene=21&pass_ticket=parser-secret"
    )
    assert "parser-secret" not in candidates[0].raw_content
    assert "parser-secret" not in repr(candidates[0])
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
        assert db.scalar(select(func.count()).select_from(CollectorDocumentRevision)) == 1

        item.status = "needs_body"
        db.flush()
        needs_body_response = collector_favorites_api.to_wechat_favorite_batch_response(db, batch)
        assert needs_body_response.status == "needs_body"
        assert needs_body_response.failed == 1
        assert needs_body_response.failed_item_ids == [item.id]

        item.status = "degraded"
        db.flush()
        degraded_response = collector_favorites_api.to_wechat_favorite_batch_response(db, batch)
        assert degraded_response.status == "failed"
        assert degraded_response.failed_item_ids == [item.id]

        item.status = "ready"
        db.flush()

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
        assert db.scalar(select(func.count()).select_from(CollectorDocumentRevision)) == 1

        changed = multiformat_service.import_wechat_favorites(
            db,
            user_id=settings.single_user_id,
            export_text="""
            收藏一：客户 AI 中台规划（更新）
            https://mp.weixin.qq.com/s?sn=def456&idx=1&mid=2247483651&__biz=MzDemo&scene=9
            """,
            output_language="zh-CN",
            process_immediately=True,
        )
        assert changed["created"] == 0
        assert changed["deduplicated"] == 1
        assert db.scalar(select(func.count()).select_from(CollectorDocumentRevision)) == 2
    finally:
        db.close()


def test_wechat_favorites_immediate_fetch_uses_transient_url_without_persisting_secret(monkeypatch) -> None:
    db = _new_session()
    settings = get_settings()
    transient_ticket = "immediate-secret-ticket"
    fetch_url = (
        "https://mp.weixin.qq.com/s?__biz=MzImmediate&mid=2247483660&idx=1&sn=immediate123"
        f"&scene=21&pass_ticket={transient_ticket}&key=temporary-key"
    )
    seen_fetch_urls: list[str] = []

    def capture_fetch_url(db_session: Session, item: Item, **kwargs) -> Item:
        del kwargs
        seen_fetch_urls.append(str(getattr(item, "_collector_fetch_url", "")))
        return _fast_process_item(db_session, item)

    try:
        db.add(User(id=settings.single_user_id, name="immediate-fetch-user"))
        db.commit()
        monkeypatch.setattr(multiformat_service, "process_item_in_session", capture_fetch_url)

        result = multiformat_service.import_wechat_favorites(
            db,
            user_id=settings.single_user_id,
            urls=[fetch_url],
            include_text_blocks=False,
            process_immediately=True,
        )
        changed_ticket = "immediate-changed-ticket"
        changed_fetch_url = (
            "https://mp.weixin.qq.com/s?sn=immediate123&idx=1&mid=2247483660&__biz=MzImmediate"
            f"&scene=22&pass_ticket={changed_ticket}&key=temporary-changed-key"
        )
        changed = multiformat_service.import_wechat_favorites(
            db,
            user_id=settings.single_user_id,
            export_text=f"收藏一：立即刷新后的标题\n{changed_fetch_url}",
            include_text_blocks=False,
            process_immediately=True,
        )
        unchanged_ticket = "immediate-unchanged-ticket"
        unchanged_fetch_url = (
            "https://mp.weixin.qq.com/s?sn=immediate123&idx=1&mid=2247483660&__biz=MzImmediate"
            f"&scene=23&pass_ticket={unchanged_ticket}&key=temporary-unchanged-key"
        )
        unchanged = multiformat_service.import_wechat_favorites(
            db,
            user_id=settings.single_user_id,
            export_text=f"收藏一：立即刷新后的标题\n{unchanged_fetch_url}",
            include_text_blocks=False,
            process_immediately=True,
        )

        assert seen_fetch_urls == [fetch_url, changed_fetch_url, unchanged_fetch_url]
        assert result["processing_jobs"] == []
        assert changed["processing_jobs"] == []
        assert unchanged["processing_jobs"] == []
        assert changed["created"] == 0
        assert changed["deduplicated"] == 1
        assert unchanged["created"] == 0
        assert unchanged["deduplicated"] == 1
        for marker in (
            transient_ticket,
            changed_ticket,
            unchanged_ticket,
            "temporary-key",
            "temporary-changed-key",
            "temporary-unchanged-key",
        ):
            assert marker not in str(result["results"])
            assert marker not in str(changed["results"])
            assert marker not in str(unchanged["results"])
            assert marker not in str(result["batch"].result_payload)
            assert marker not in str(changed["batch"].result_payload)
            assert marker not in str(unchanged["batch"].result_payload)
            assert marker not in _sqlite_dump(db)
    finally:
        db.close()


def test_wechat_favorites_redacts_transient_url_from_import_errors(monkeypatch) -> None:
    db = _new_session()
    settings = get_settings()
    transient_ticket = "error-secret-ticket"
    fetch_url = (
        "https://mp.weixin.qq.com/s?__biz=MzError&mid=2247483662&idx=1&sn=error123"
        f"&pass_ticket={transient_ticket}&key=temporary-error-key"
    )

    def fail_with_fetch_url(*_args, **kwargs):
        raise RuntimeError(f"fetch failed for {kwargs['fetch_url']}")

    try:
        db.add(User(id=settings.single_user_id, name="error-redaction-user"))
        db.commit()
        monkeypatch.setattr(multiformat_service, "_persist_item", fail_with_fetch_url)

        result = multiformat_service.import_wechat_favorites(
            db,
            user_id=settings.single_user_id,
            urls=[fetch_url],
            include_text_blocks=False,
            process_immediately=True,
        )
        db.commit()

        assert result["invalid"] == 1
        assert transient_ticket not in str(result["results"])
        assert "temporary-error-key" not in str(result["results"])
        assert result["results"][0]["detail"] == (
            "fetch failed for "
            "https://mp.weixin.qq.com/s?__biz=MzError&mid=2247483662&idx=1&sn=error123"
        )
        assert transient_ticket not in _sqlite_dump(db)
        assert "temporary-error-key" not in _sqlite_dump(db)
    finally:
        db.close()


def test_wechat_favorites_deferred_new_changed_and_unchanged_refresh_keep_secret_only_in_jobs(monkeypatch) -> None:
    db = _new_session()
    settings = get_settings()
    first_secret = "deferred-secret-v1"
    changed_secret = "deferred-secret-v2"
    captured_results: list[dict] = []
    real_import = collector_favorites_api.import_wechat_favorites_payload

    def capture_import_result(*args, **kwargs):
        result = real_import(*args, **kwargs)
        captured_results.append(result)
        return result

    try:
        db.add(User(id=settings.single_user_id, name="deferred-fetch-user"))
        db.commit()
        monkeypatch.setattr(collector_favorites_api, "import_wechat_favorites_payload", capture_import_result)

        first_tasks = BackgroundTasks()
        first_response = collector_favorites_api.import_wechat_favorite_items_impl(
            CollectorWechatFavoriteImportRequest(
                export_text=(
                    "收藏一：待抓取正文 v1\n"
                    "https://mp.weixin.qq.com/s?__biz=MzDeferred&mid=2247483661&idx=1&sn=deferred123"
                    f"&scene=1&pass_ticket={first_secret}&key=temporary-v1"
                ),
                include_text_blocks=False,
                process_immediately=False,
            ),
            first_tasks,
            db,
            ensure_demo_user_fn=lambda _db: None,
            process_item_task_fn=lambda *_args: None,
        )
        first_job = captured_results[-1]["processing_jobs"]
        assert first_response.created == 1
        assert len(first_job) == 1
        assert captured_results[-1]["batch"].status == "queued"
        assert first_job[0]["item_id"] == str(first_response.created_item_ids[0])
        assert first_secret in str(first_job[0]["fetch_url"])
        assert len(first_tasks.tasks) == 1
        assert first_tasks.tasks[0].args[0] == first_response.created_item_ids[0]
        assert first_secret in str(first_tasks.tasks[0].args[3])
        first_item = db.get(Item, first_response.created_item_ids[0])
        assert first_item is not None
        assert first_item.status == "pending"
        assert first_item.content_acquisition_status == "pending_processing"

        changed_tasks = BackgroundTasks()
        changed_response = collector_favorites_api.import_wechat_favorite_items_impl(
            CollectorWechatFavoriteImportRequest(
                export_text=(
                    "收藏一：待抓取正文 v2\n"
                    "https://mp.weixin.qq.com/s?sn=deferred123&idx=1&mid=2247483661&__biz=MzDeferred"
                    f"&scene=9&pass_ticket={changed_secret}&key=temporary-v2"
                ),
                include_text_blocks=False,
                process_immediately=False,
            ),
            changed_tasks,
            db,
            ensure_demo_user_fn=lambda _db: None,
            process_item_task_fn=lambda *_args: None,
        )
        changed_job = captured_results[-1]["processing_jobs"]
        assert changed_response.created == 0
        assert changed_response.deduplicated == 1
        assert changed_response.created_item_ids == []
        assert len(changed_job) == 1
        assert captured_results[-1]["batch"].status == "queued"
        assert changed_job[0]["item_id"] == str(first_response.created_item_ids[0])
        assert changed_secret in str(changed_job[0]["fetch_url"])
        assert len(changed_tasks.tasks) == 1
        assert changed_tasks.tasks[0].args[0] == first_response.created_item_ids[0]
        assert changed_secret in str(changed_tasks.tasks[0].args[3])

        unchanged_secret = "deferred-secret-v3"
        unchanged_tasks = BackgroundTasks()
        unchanged_response = collector_favorites_api.import_wechat_favorite_items_impl(
            CollectorWechatFavoriteImportRequest(
                export_text=(
                    "收藏一：待抓取正文 v2\n"
                    "https://mp.weixin.qq.com/s?__biz=MzDeferred&mid=2247483661&idx=1&sn=deferred123"
                    f"&scene=10&pass_ticket={unchanged_secret}&key=temporary-v3"
                ),
                include_text_blocks=False,
                process_immediately=False,
            ),
            unchanged_tasks,
            db,
            ensure_demo_user_fn=lambda _db: None,
            process_item_task_fn=lambda *_args: None,
        )
        unchanged_job = captured_results[-1]["processing_jobs"]
        assert unchanged_response.created == 0
        assert unchanged_response.deduplicated == 1
        assert unchanged_response.created_item_ids == []
        assert len(unchanged_job) == 1
        assert unchanged_job[0]["item_id"] == str(first_response.created_item_ids[0])
        assert unchanged_secret in str(unchanged_job[0]["fetch_url"])
        assert captured_results[-1]["batch"].status == "queued"
        assert len(unchanged_tasks.tasks) == 1
        assert unchanged_tasks.tasks[0].args[0] == first_response.created_item_ids[0]
        assert unchanged_secret in str(unchanged_tasks.tasks[0].args[3])
        assert db.scalar(select(func.count()).select_from(CollectorDocumentRevision)) == 2
        attempt_statuses = list(db.scalars(select(CollectorIngestAttempt.attempt_status)))
        assert attempt_statuses == ["queued", "queued", "queued"]

        public_payload = (
            first_response.model_dump_json()
            + changed_response.model_dump_json()
            + unchanged_response.model_dump_json()
        )
        persisted_batch_payloads = " ".join(
            str(value)
            for value in db.scalars(select(CollectorImportBatch.result_payload)).all()
        )
        for secret in (
            first_secret,
            changed_secret,
            unchanged_secret,
            "temporary-v1",
            "temporary-v2",
            "temporary-v3",
        ):
            assert secret not in str(captured_results[0]["results"])
            assert secret not in str(captured_results[1]["results"])
            assert secret not in str(captured_results[2]["results"])
            assert secret not in public_payload
            assert secret not in persisted_batch_payloads
            assert secret not in _sqlite_dump(db)
    finally:
        db.close()


def test_wechat_favorites_api_preview_import_and_restore_batch(monkeypatch) -> None:
    db = _new_session()
    settings = get_settings()
    preview_marker = "preview-private-ticket"
    preview_key = "preview-private-key"
    api_url = (
        "https://mp.weixin.qq.com/s?__biz=MzDemo&mid=2247483659&idx=1&sn=api123&scene=1"
        f"&pass_ticket={preview_marker}&key={preview_key}"
    )
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()
        monkeypatch.setattr(collector_favorites_api, "ensure_demo_user", lambda _db: None)

        preview = collector_favorites_api.preview_wechat_favorite_items(
            CollectorWechatFavoritePreviewRequest(
                export_text=f"收藏一：AI 客户会议准备\n{api_url}",
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
                export_text=f"收藏一：AI 客户会议准备\n{api_url}",
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
        public_payload = (
            preview.model_dump_json()
            + imported.model_dump_json()
            + latest.model_dump_json()
            + restored.model_dump_json()
        )
        for marker in (preview_marker, preview_key):
            assert marker not in public_payload
            assert marker not in _sqlite_dump(db)
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
