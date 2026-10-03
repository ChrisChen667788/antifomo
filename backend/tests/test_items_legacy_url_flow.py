from __future__ import annotations

from uuid import UUID

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.api import collector_operations, items as items_api
from app.core.config import get_settings
from app.db.base import Base
from app.models.entities import Item
from app.schemas.items import ItemBatchCreateRequest, ItemCreateRequest
from app.services.source_url_privacy import canonicalize_persisted_url, normalize_fetch_url
from app.services.user_context import ensure_demo_user


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)()


def test_legacy_create_persists_canonical_url_and_queues_transient_fetch_url() -> None:
    db = _new_session()
    try:
        submitted_url = (
            "HTTPS://MP.WEIXIN.QQ.COM/s/?sn=stable&idx=1&mid=7&__biz=MzLegacy"
            "&scene=21&pass_ticket=session-secret#wechat_redirect"
        )
        expected_fetch_url = normalize_fetch_url(submitted_url)
        expected_source_url = canonicalize_persisted_url(submitted_url)
        background_tasks = BackgroundTasks()

        response = items_api.create_item(
            ItemCreateRequest(source_type="url", source_url=submitted_url),
            background_tasks,
            db,
        )

        stored = db.get(Item, response.id)
        assert expected_fetch_url is not None
        assert expected_source_url is not None
        assert stored is not None
        assert stored.source_url == expected_source_url
        assert response.source_url == expected_source_url
        assert "pass_ticket" not in response.model_dump_json()
        assert len(background_tasks.tasks) == 1
        task = background_tasks.tasks[0]
        assert task.func is items_api._process_item_task
        assert task.args == (response.id, "zh-CN", expected_fetch_url)
        assert "pass_ticket=session-secret" in task.args[2]
    finally:
        db.close()


def test_legacy_create_rejects_invalid_url_without_echoing_input() -> None:
    db = _new_session()
    try:
        invalid_url = "not-a-url?pass_ticket=must-not-echo"

        with pytest.raises(HTTPException) as raised:
            items_api.create_item(
                ItemCreateRequest(source_type="url", source_url=invalid_url),
                BackgroundTasks(),
                db,
            )

        assert raised.value.status_code == 400
        assert "must-not-echo" not in str(raised.value.detail)
        assert db.scalar(select(func.count()).select_from(Item)) == 0
    finally:
        db.close()


def test_legacy_batch_deduplicates_canonical_urls_and_never_returns_fetch_secrets() -> None:
    db = _new_session()
    try:
        settings = get_settings()
        ensure_demo_user(db)
        existing_url = "https://mp.weixin.qq.com/s?__biz=MzExisting&mid=1&idx=1&sn=stable-one"
        db.add(
            Item(
                user_id=settings.single_user_id,
                source_type="url",
                source_url=existing_url,
                status="pending",
            )
        )
        db.commit()

        existing_fetch_url = existing_url + "&scene=1&pass_ticket=existing-secret"
        first_new_fetch_url = (
            "https://mp.weixin.qq.com/s?sn=stable-two&idx=1&mid=2&__biz=MzNew"
            "&scene=21&pass_ticket=first-new-secret"
        )
        duplicate_new_fetch_url = (
            "https://mp.weixin.qq.com/s?__biz=MzNew&mid=2&idx=1&sn=stable-two"
            "&scene=9&pass_ticket=duplicate-secret"
        )
        invalid_url = "not-a-url?pass_ticket=invalid-secret"
        expected_new_source_url = canonicalize_persisted_url(first_new_fetch_url)
        expected_new_fetch_url = normalize_fetch_url(first_new_fetch_url)
        background_tasks = BackgroundTasks()

        response = items_api.create_items_batch(
            ItemBatchCreateRequest(
                urls=[
                    existing_fetch_url,
                    first_new_fetch_url,
                    duplicate_new_fetch_url,
                    invalid_url,
                ]
            ),
            background_tasks,
            db,
        )

        assert [result.status for result in response.results] == [
            "skipped",
            "created",
            "skipped",
            "invalid",
        ]
        assert response.created == 1
        assert response.skipped == 2
        assert response.invalid == 1
        assert response.results[0].source_url == existing_url
        assert response.results[1].source_url == expected_new_source_url
        assert response.results[2].source_url == expected_new_source_url
        assert response.results[3].source_url == ""
        serialized_response = response.model_dump_json()
        for secret in (
            "existing-secret",
            "first-new-secret",
            "duplicate-secret",
            "invalid-secret",
        ):
            assert secret not in serialized_response

        stored_urls = list(db.scalars(select(Item.source_url).order_by(Item.source_url)))
        assert stored_urls == sorted([existing_url, expected_new_source_url])
        assert all("pass_ticket" not in str(url) for url in stored_urls)
        assert len(background_tasks.tasks) == 1
        task = background_tasks.tasks[0]
        assert task.func is items_api._process_item_task
        assert task.args[1:] == ("zh-CN", expected_new_fetch_url)
        assert isinstance(task.args[0], UUID)
        assert "pass_ticket=first-new-secret" in task.args[2]
    finally:
        db.close()


def test_legacy_background_task_forwards_fetch_url_only_in_memory(monkeypatch) -> None:
    item_id = UUID("00000000-0000-0000-0000-000000000099")
    fetch_url = "https://mp.weixin.qq.com/s?__biz=MzFetch&pass_ticket=transient"
    received: dict[str, object] = {}

    def process_item_by_id(item_id_arg: UUID, **kwargs):
        received["item_id"] = item_id_arg
        received.update(kwargs)

    monkeypatch.setattr(items_api, "process_item_by_id", process_item_by_id)

    items_api._process_item_task(item_id, "en", fetch_url)

    assert received == {
        "item_id": item_id,
        "output_language": "en",
        "auto_archive": True,
        "fetch_url": fetch_url,
    }


def test_item_api_canonicalizes_wechat_urls_loaded_from_legacy_rows() -> None:
    db = _new_session()
    try:
        settings = get_settings()
        ensure_demo_user(db)
        item_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        attempt_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        legacy_url = (
            "HTTPS://reader:password@MP.WEIXIN.QQ.COM.:443/s/?sn=stable&idx=1&mid=7&"
            "__biz=MzLegacy&scene=21&pass_ticket=legacy-secret&key=temporary"
            "#wechat_redirect"
        )
        canonical_url = canonicalize_persisted_url(legacy_url)
        db.execute(
            text(
                "INSERT INTO items "
                "(id, user_id, source_type, source_url, resolved_from_url, raw_content, "
                "clean_content, status, "
                "processing_error, content_acquisition_note) "
                "VALUES (:id, :user_id, 'url', :source_url, :resolved_from_url, :raw_content, "
                ":clean_content, 'ready', :error_detail, :error_detail)"
            ),
            {
                "id": item_id.hex,
                "user_id": settings.single_user_id.hex,
                "source_url": legacy_url,
                "resolved_from_url": legacy_url,
                "raw_content": f"legacy link: {legacy_url}",
                "clean_content": f"clean link: {legacy_url}",
                "error_detail": f"fetch failed for {legacy_url}",
            },
        )
        db.execute(
            text(
                "INSERT INTO collector_ingest_attempts "
                "(id, user_id, item_id, source_url, source_type, route_type, resolver, "
                "attempt_status, error_detail) VALUES "
                "(:id, :user_id, :item_id, :source_url, 'url', 'direct_url', 'legacy', "
                "'failed', :error_detail)"
            ),
            {
                "id": attempt_id.hex,
                "user_id": settings.single_user_id.hex,
                "item_id": item_id.hex,
                "source_url": legacy_url,
                "error_detail": f"attempt failed for {legacy_url}",
            },
        )
        db.commit()

        detail = items_api.get_item(item_id, db)
        listed = items_api._list_items_impl(db, limit=10)
        diagnostics = items_api.get_item_diagnostics(item_id, db)
        attempts = collector_operations.get_item_ingest_attempts_impl(item_id, db=db)

        assert detail.source_url == canonical_url
        assert detail.resolved_from_url == canonical_url
        assert listed.items[0].source_url == canonical_url
        assert listed.items[0].resolved_from_url == canonical_url
        assert canonical_url in str(detail.processing_error)
        assert canonical_url in str(detail.content_acquisition_note)
        assert canonical_url in str(detail.raw_content)
        assert canonical_url in str(detail.clean_content)
        assert diagnostics.latest_attempt is not None
        assert diagnostics.latest_attempt.source_url == canonical_url
        assert canonical_url in str(diagnostics.latest_attempt.error_detail)
        assert attempts[0].source_url == canonical_url
        assert canonical_url in str(attempts[0].error_detail)
        assert "legacy-secret" not in detail.model_dump_json()
        assert "temporary" not in listed.model_dump_json()
        assert "legacy-secret" not in diagnostics.model_dump_json()
        assert "temporary" not in attempts[0].model_dump_json()
        persisted = db.execute(
            text("SELECT source_url FROM items WHERE id = :id"),
            {"id": item_id.hex},
        ).scalar_one()
        assert "pass_ticket=legacy-secret" in persisted
    finally:
        db.close()
