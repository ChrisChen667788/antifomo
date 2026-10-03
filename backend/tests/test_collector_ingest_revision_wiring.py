from __future__ import annotations

import hashlib

from fastapi import BackgroundTasks
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api import collector_ingest as collector_ingest_api
from app.core.config import get_settings
from app.db.base import Base
from app.models import CollectorIngestAttempt, Item, User
from app.models.collector_evidence_entities import (
    CollectorDocumentRevision,
    CollectorRawAsset,
    CollectorSourceItem,
    CollectorSourceSpan,
    CollectorTransformReceipt,
)
from app.schemas.collector import CollectorPluginIngestRequest, CollectorURLIngestRequest
from app.services import item_processor
from app.services.collector_evidence_service import latest_revision_for_item
from app.services.content_extractor import normalize_text


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)()
    settings = get_settings()
    db.add(User(id=settings.single_user_id, name="collector-revision-test"))
    db.commit()
    return db


def _mark_ready(db: Session, item: Item, **_kwargs) -> Item:
    item.clean_content = item.raw_content or "ready"
    item.status = "ready"
    item.processing_error = None
    db.add(item)
    return item


def test_plugin_api_preserves_exact_payload_in_raw_asset_and_only_clean_projection_on_item() -> None:
    db = _new_session()
    try:
        raw_payload = (
            "  标题：原始插件正文  \n"
            "正文：第一段保留换行、  双空格与 &amp; 实体。\n"
            "第二段继续保留原始 payload 的精确文本。  "
        )
        response = collector_ingest_api.ingest_plugin_item_impl(
            CollectorPluginIngestRequest(
                source_url="https://example.com/plugin-exact#reader",
                title="插件精确证据",
                raw_content=raw_payload,
                process_immediately=True,
            ),
            BackgroundTasks(),
            db,
            ensure_demo_user_fn=lambda _db: None,
            mark_source_collected_fn=lambda *_args, **_kwargs: None,
            process_item_in_session_fn=_mark_ready,
        )

        raw_asset = db.scalar(select(CollectorRawAsset))
        stored_item = db.get(Item, response.item.id)

        assert raw_asset is not None
        assert raw_asset.raw_text == raw_payload
        assert raw_asset.byte_size == len(raw_payload.encode("utf-8"))
        assert stored_item is not None
        assert stored_item.raw_content == normalize_text(raw_payload)
        assert stored_item.raw_content != raw_payload
        assert response.item.raw_content == normalize_text(raw_payload)
    finally:
        db.close()


def test_plugin_processor_final_revision_stays_current_after_same_raw_replay(monkeypatch) -> None:
    db = _new_session()
    monkeypatch.setattr(
        item_processor,
        "_resolve_item_processing_stack",
        lambda _item: (
            item_processor.mock_summarizer,
            item_processor.mock_tagger,
            item_processor.mock_scorer,
            None,
        ),
    )
    try:
        raw_payload = (
            "标题：插件真实处理链\n"
            "正文：这是用于验证 API capture 与 processor capture 共用同一 revision 的正文。\n" * 8
        )
        response = collector_ingest_api.ingest_plugin_item_impl(
            CollectorPluginIngestRequest(
                source_url="https://example.com/plugin-real-processor",
                raw_content=raw_payload,
            ),
            BackgroundTasks(),
            db,
            ensure_demo_user_fn=lambda _db: None,
            mark_source_collected_fn=lambda *_args, **_kwargs: None,
        )

        stored_item = db.get(Item, response.item.id)
        raw_asset = db.scalar(select(CollectorRawAsset))
        source_item = db.scalar(
            select(CollectorSourceItem).where(CollectorSourceItem.item_id == response.item.id)
        )
        latest = latest_revision_for_item(db, item_id=response.item.id)

        assert stored_item is not None
        assert stored_item.raw_content == stored_item.clean_content
        assert stored_item.raw_content != raw_payload
        assert raw_asset is not None
        assert raw_asset.raw_text == raw_payload
        assert source_item is not None
        assert latest is not None
        assert source_item.current_revision_key == latest.revision_key
        assert latest.normalized_sha256 == hashlib.sha256(
            normalize_text(stored_item.clean_content or "").encode()
        ).hexdigest()
        latest_span = db.scalar(
            select(CollectorSourceSpan).where(CollectorSourceSpan.revision_id == latest.id)
        )
        assert latest_span is not None
        assert latest_span.text == normalize_text(stored_item.clean_content or "")
        receipts = list(db.scalars(select(CollectorTransformReceipt)))
        assert receipts
        assert {receipt.revision_id for receipt in receipts} == {latest.id}
        assert db.scalar(select(func.count()).select_from(CollectorRawAsset)) == 1
        assert db.scalar(select(func.count()).select_from(CollectorDocumentRevision)) == 2

        current_revision_key = source_item.current_revision_key
        replay = collector_ingest_api.ingest_plugin_item_impl(
            CollectorPluginIngestRequest(
                source_url="https://example.com/plugin-real-processor",
                raw_content=raw_payload,
            ),
            BackgroundTasks(),
            db,
            ensure_demo_user_fn=lambda _db: None,
            mark_source_collected_fn=lambda *_args, **_kwargs: None,
        )
        replayed_source_item = db.scalar(
            select(CollectorSourceItem).where(CollectorSourceItem.item_id == response.item.id)
        )
        replayed_latest = latest_revision_for_item(db, item_id=response.item.id)

        assert replay.deduplicated is True
        assert replay.resolver == "existing_item"
        assert replayed_source_item is not None
        assert replayed_source_item.current_revision_key == current_revision_key
        assert replayed_latest is not None
        assert replayed_latest.id == latest.id
        assert db.scalar(select(func.count()).select_from(CollectorRawAsset)) == 1
        assert db.scalar(select(func.count()).select_from(CollectorDocumentRevision)) == 2
        assert {receipt.revision_id for receipt in db.scalars(select(CollectorTransformReceipt))} == {
            latest.id
        }
    finally:
        db.close()


def test_plugin_same_payload_skips_processing_while_changed_payload_creates_revision() -> None:
    db = _new_session()
    calls: list[str] = []

    def process(db: Session, item: Item, **_kwargs) -> Item:
        calls.append(str(item.raw_content))
        return _mark_ready(db, item)

    try:
        source_url = "https://example.com/plugin-revisions"
        raw_v1 = "插件原始正文 v1，保留证据边界。\n" * 4
        raw_v2 = "插件原始正文 v2，正文已经变化。\n" * 4
        raw_v3 = "插件原始正文 v3，延迟处理修订。\n" * 4

        first = collector_ingest_api.ingest_plugin_item_impl(
            CollectorPluginIngestRequest(source_url=source_url, raw_content=raw_v1),
            BackgroundTasks(),
            db,
            ensure_demo_user_fn=lambda _db: None,
            mark_source_collected_fn=lambda *_args, **_kwargs: None,
            process_item_in_session_fn=process,
        )
        unchanged = collector_ingest_api.ingest_plugin_item_impl(
            CollectorPluginIngestRequest(source_url=source_url, raw_content=raw_v1),
            BackgroundTasks(),
            db,
            ensure_demo_user_fn=lambda _db: None,
            mark_source_collected_fn=lambda *_args, **_kwargs: None,
            process_item_in_session_fn=process,
        )
        changed = collector_ingest_api.ingest_plugin_item_impl(
            CollectorPluginIngestRequest(source_url=source_url, raw_content=raw_v2),
            BackgroundTasks(),
            db,
            ensure_demo_user_fn=lambda _db: None,
            mark_source_collected_fn=lambda *_args, **_kwargs: None,
            process_item_in_session_fn=process,
        )
        deferred_tasks = BackgroundTasks()
        deferred = collector_ingest_api.ingest_plugin_item_impl(
            CollectorPluginIngestRequest(
                source_url=source_url,
                raw_content=raw_v3,
                process_immediately=False,
            ),
            deferred_tasks,
            db,
            ensure_demo_user_fn=lambda _db: None,
            mark_source_collected_fn=lambda *_args, **_kwargs: None,
            process_item_in_session_fn=process,
        )

        assert first.deduplicated is False
        assert unchanged.deduplicated is True
        assert unchanged.resolver == "existing_item"
        assert changed.deduplicated is True
        assert changed.resolver == "existing_item_revision"
        assert changed.item.id == first.item.id
        assert deferred.deduplicated is True
        assert deferred.resolver == "existing_item_revision"
        assert deferred.processing_deferred is True
        assert len(deferred_tasks.tasks) == 1
        assert len(calls) == 2
        assert db.scalar(select(func.count()).select_from(Item)) == 1
        assert db.scalar(select(func.count()).select_from(CollectorRawAsset)) == 3
        assert db.scalar(select(func.count()).select_from(CollectorDocumentRevision)) == 3
        assert {row.raw_text for row in db.scalars(select(CollectorRawAsset))} == {
            raw_v1,
            raw_v2,
            raw_v3,
        }
    finally:
        db.close()


def test_url_refresh_refetches_existing_item_and_records_changed_revision() -> None:
    db = _new_session()
    raw_versions = [
        "<html><body>URL 抓取原文 v1，保留完整响应。</body></html>",
        "<html><body>URL 抓取原文 v2，刷新后内容变化。</body></html>",
    ]
    fetch_urls: list[str] = []

    def process(db: Session, item: Item, **_kwargs) -> Item:
        raw_content = raw_versions[len(fetch_urls)]
        fetch_urls.append(str(getattr(item, "_collector_fetch_url", "")))
        clean_content = normalize_text(raw_content)
        item._collector_raw_evidence = raw_content
        item.raw_content = clean_content
        item.clean_content = clean_content
        item.status = "ready"
        item.processing_error = None
        db.add(item)
        return item

    try:
        first_url = (
            "https://mp.weixin.qq.com/s?__biz=MzRefresh&mid=7&idx=1&sn=stable"
            "&scene=1&pass_ticket=secret-v1#wechat_redirect"
        )
        replay_url = (
            "https://mp.weixin.qq.com/s?sn=stable&idx=1&mid=7&__biz=MzRefresh"
            "&scene=9&pass_ticket=secret-v2"
        )
        refresh_url = (
            "https://mp.weixin.qq.com/s?__biz=MzRefresh&mid=7&idx=1&sn=stable"
            "&scene=21&pass_ticket=secret-v3"
        )

        assert CollectorURLIngestRequest(source_url=first_url).refresh is False
        first = collector_ingest_api.ingest_url_item_impl(
            CollectorURLIngestRequest(source_url=first_url),
            BackgroundTasks(),
            db,
            ensure_demo_user_fn=lambda _db: None,
            mark_source_collected_fn=lambda *_args, **_kwargs: None,
            process_item_in_session_fn=process,
        )
        unchanged = collector_ingest_api.ingest_url_item_impl(
            CollectorURLIngestRequest(source_url=replay_url),
            BackgroundTasks(),
            db,
            ensure_demo_user_fn=lambda _db: None,
            mark_source_collected_fn=lambda *_args, **_kwargs: None,
            process_item_in_session_fn=process,
        )
        refreshed = collector_ingest_api.ingest_url_item_impl(
            CollectorURLIngestRequest(source_url=refresh_url, refresh=True),
            BackgroundTasks(),
            db,
            ensure_demo_user_fn=lambda _db: None,
            mark_source_collected_fn=lambda *_args, **_kwargs: None,
            process_item_in_session_fn=process,
        )

        stored_item = db.get(Item, first.item.id)
        attempts = db.scalars(select(CollectorIngestAttempt)).all()

        assert first.deduplicated is False
        assert unchanged.deduplicated is True
        assert unchanged.resolver == "existing_item"
        assert refreshed.deduplicated is True
        assert refreshed.resolver == "page_refresh"
        assert refreshed.item.id == first.item.id
        assert len(fetch_urls) == 2
        assert "pass_ticket=secret-v1" in fetch_urls[0]
        assert "pass_ticket=secret-v3" in fetch_urls[1]
        assert stored_item is not None
        assert stored_item.raw_content == normalize_text(raw_versions[1])
        assert "pass_ticket" not in str(stored_item.source_url)
        assert all("pass_ticket" not in str(attempt.source_url) for attempt in attempts)
        assert db.scalar(select(func.count()).select_from(CollectorRawAsset)) == 2
        assert db.scalar(select(func.count()).select_from(CollectorDocumentRevision)) == 2
        assert {row.raw_text for row in db.scalars(select(CollectorRawAsset))} == set(raw_versions)
    finally:
        db.close()
