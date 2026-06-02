from __future__ import annotations

from types import SimpleNamespace

from fastapi import BackgroundTasks
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.api import collector_ingest as collector_ingest_api
from app.api import collector_ocr_routes as collector_ocr_api
from app.core.config import get_settings
from app.db.base import Base
from app.models import CollectorIngestAttempt, Item, User
from app.services.content_extractor import ContentExtractionError, ExtractedContent
from app.schemas.collector import (
    CollectorBrowserBatchIngestRequest,
    CollectorOCRIngestRequest,
    CollectorPluginIngestRequest,
    CollectorURLIngestRequest,
)


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def _mark_ready(db: Session, item: Item, *, output_language: str | None = None, auto_archive: bool = True) -> Item:
    assert output_language or auto_archive is not None
    item.status = "ready"
    item.processing_error = None
    item.clean_content = item.raw_content or "ready"
    db.add(item)
    return item


def test_process_immediate_ingest_routes_flush_item_before_attempt() -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

        ensure_demo_user = lambda _db: None
        mark_source_collected = lambda *_args, **_kwargs: None
        vision_ocr = SimpleNamespace(
            extract=lambda **_kwargs: SimpleNamespace(
                title="OCR 标题",
                body_text="OCR 正文内容。" * 12,
                keywords=["OCR", "测试"],
                provider="mock",
                confidence=0.88,
            )
        )

        plugin_resp = collector_ingest_api.ingest_plugin_item_impl(
            CollectorPluginIngestRequest(
                source_url="https://mp.weixin.qq.com/s/plugin-process-immediate",
                title="插件正文",
                raw_content="插件正文内容。" * 20,
                process_immediately=True,
            ),
            BackgroundTasks(),
            db,
            ensure_demo_user_fn=ensure_demo_user,
            mark_source_collected_fn=mark_source_collected,
            process_item_in_session_fn=_mark_ready,
        )
        url_resp = collector_ingest_api.ingest_url_item_impl(
            CollectorURLIngestRequest(
                source_url="https://mp.weixin.qq.com/s/url-process-immediate",
                title="URL 直链",
                deduplicate=False,
                process_immediately=True,
            ),
            BackgroundTasks(),
            db,
            ensure_demo_user_fn=ensure_demo_user,
            mark_source_collected_fn=mark_source_collected,
            process_item_in_session_fn=_mark_ready,
        )
        ocr_resp = collector_ocr_api.ingest_ocr_image_impl(
            CollectorOCRIngestRequest(
                image_base64="ZmFrZV9pbWFnZV9kYXRh" * 8,
                mime_type="image/png",
                source_url="https://wechat.local/article/ocr-process-immediate",
                title_hint="OCR 入口",
                deduplicate=False,
                process_immediately=True,
            ),
            BackgroundTasks(),
            db,
            ensure_demo_user_fn=ensure_demo_user,
            mark_source_collected_fn=mark_source_collected,
            process_item_in_session_fn=_mark_ready,
            vision_ocr_service=vision_ocr,
        )

        attempts = db.scalars(select(CollectorIngestAttempt).order_by(CollectorIngestAttempt.created_at)).all()

        assert plugin_resp.item.id is not None
        assert url_resp.item.id is not None
        assert ocr_resp.item.id is not None
        assert len(attempts) == 3
        assert all(attempt.item_id is not None for attempt in attempts)
        assert {attempt.route_type for attempt in attempts} == {"plugin", "direct_url", "ocr"}
    finally:
        db.close()


def test_browser_ingest_prefers_plugin_route_when_browser_extract_succeeds() -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

        response = collector_ingest_api.ingest_browser_item_impl(
            CollectorURLIngestRequest(
                source_url="https://mp.weixin.qq.com/s/browser-success",
                title="原始标题",
                deduplicate=False,
                process_immediately=True,
            ),
            BackgroundTasks(),
            db,
            ensure_demo_user_fn=lambda _db: None,
            mark_source_collected_fn=lambda *_args, **_kwargs: None,
            process_item_in_session_fn=_mark_ready,
            extract_from_browser_fn=lambda _url: ExtractedContent(
                source_url="https://mp.weixin.qq.com/s/browser-success-final",
                source_domain="mp.weixin.qq.com",
                title="浏览器提取标题",
                raw_content="浏览器正文内容。" * 20,
                clean_content="浏览器正文内容。" * 20,
            ),
        )

        item = db.scalar(select(Item).where(Item.id == response.item.id))
        attempt = db.scalar(
            select(CollectorIngestAttempt)
            .where(CollectorIngestAttempt.item_id == response.item.id)
            .limit(1)
        )

        assert response.ingest_route == "browser_plugin"
        assert response.resolver == "browser_extract"
        assert response.body_source == "plugin_body"
        assert response.metadata["browser_extract"]["status"] == "success"
        assert response.metadata["browser_extract"]["final_url"] == "https://mp.weixin.qq.com/s/browser-success-final"
        assert item is not None
        assert item.source_type == "plugin"
        assert item.source_url == "https://mp.weixin.qq.com/s/browser-success-final"
        assert attempt is not None
        assert attempt.route_type == "plugin"
    finally:
        db.close()


def test_browser_ingest_falls_back_to_url_route_when_browser_extract_fails() -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

        response = collector_ingest_api.ingest_browser_item_impl(
            CollectorURLIngestRequest(
                source_url="https://mp.weixin.qq.com/s/browser-fallback",
                title="原始标题",
                deduplicate=False,
                process_immediately=True,
            ),
            BackgroundTasks(),
            db,
            ensure_demo_user_fn=lambda _db: None,
            mark_source_collected_fn=lambda *_args, **_kwargs: None,
            process_item_in_session_fn=_mark_ready,
            extract_from_browser_fn=lambda _url: (_ for _ in ()).throw(
                ContentExtractionError("browser extractor unavailable")
            ),
        )

        item = db.scalar(select(Item).where(Item.id == response.item.id))
        attempt = db.scalar(
            select(CollectorIngestAttempt)
            .where(CollectorIngestAttempt.item_id == response.item.id)
            .limit(1)
        )

        assert response.ingest_route == "browser_url_fallback"
        assert response.resolver == "browser_extract_fallback"
        assert response.metadata["browser_extract"]["status"] == "fallback"
        assert "browser extractor unavailable" in response.metadata["browser_extract"]["error"]
        assert item is not None
        assert item.source_type == "url"
        assert item.source_url == "https://mp.weixin.qq.com/s/browser-fallback"
        assert attempt is not None
        assert attempt.route_type == "direct_url"
    finally:
        db.close()


def test_browser_batch_ingest_aggregates_success_dedup_and_failure() -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

        def fake_browser_extract(url: str):
            if url.endswith("/batch-success"):
                return ExtractedContent(
                    source_url=url,
                    source_domain="mp.weixin.qq.com",
                    title="成功正文",
                    raw_content="成功正文内容。" * 20,
                    clean_content="成功正文内容。" * 20,
                )
            if url.endswith("/batch-fallback"):
                raise ContentExtractionError("browser extractor unavailable")
            raise ContentExtractionError("unexpected failure")

        response = collector_ingest_api.ingest_browser_items_batch_impl(
            CollectorBrowserBatchIngestRequest(
                source_urls=[
                    "https://mp.weixin.qq.com/s/batch-success",
                    "https://mp.weixin.qq.com/s/batch-fallback",
                    "https://mp.weixin.qq.com/s/batch-success",
                ],
                process_immediately=True,
            ),
            BackgroundTasks(),
            db,
            ensure_demo_user_fn=lambda _db: None,
            mark_source_collected_fn=lambda *_args, **_kwargs: None,
            process_item_in_session_fn=_mark_ready,
            extract_from_browser_fn=fake_browser_extract,
        )

        assert response.total == 2
        assert response.created == 2
        assert response.deduplicated == 0
        assert response.failed == 0
        assert [row.ingest_route for row in response.results] == ["browser_plugin", "browser_url_fallback"]
        assert [row.status for row in response.results] == ["created", "created"]
    finally:
        db.close()
