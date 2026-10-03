from __future__ import annotations

from fastapi import BackgroundTasks
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api import collector_operations, items as items_api
from app.core.config import get_settings
from app.db.base import Base
from app.models.entities import Item, User
from app.schemas.items import ItemBatchReprocessRequest


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)()


def test_review_statuses_are_visible_counted_and_batch_retryable() -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="review-user"))
        items = [
            Item(
                user_id=settings.single_user_id,
                source_type="text",
                title=f"status-{status}",
                raw_content="正文",
                status=status,
                processing_error=f"{status}-reason",
            )
            for status in ("failed", "needs_body", "degraded")
        ]
        db.add_all(items)
        db.commit()

        failed = collector_operations.list_failed_items_impl(
            db=db,
            ensure_demo_user_fn=lambda _db: None,
        )
        assert failed.total_failed == 3
        assert {item.status for item in failed.items} == {"failed", "needs_body", "degraded"}

        status = collector_operations.get_collector_status_impl(
            db=db,
            ensure_demo_user_fn=lambda _db: None,
        )
        assert status.last_24h_failed == 1
        assert status.last_24h_needs_body == 1
        assert status.last_24h_degraded == 1

        daily = collector_operations.get_daily_summary_impl(
            db=db,
            ensure_demo_user_fn=lambda _db: None,
        )
        assert daily.failed_count == 1
        assert daily.needs_body_count == 1
        assert daily.degraded_count == 1
        assert {item.status for item in daily.failed_items} == {"failed", "needs_body", "degraded"}

        result = items_api.reprocess_items_batch(
            ItemBatchReprocessRequest(item_ids=[item.id for item in items], failed_only=True),
            BackgroundTasks(),
            db,
        )
        assert result.accepted == 3
        assert result.skipped == 0
        assert {item.status for item in items} == {"processing"}
    finally:
        db.close()


def test_item_list_projection_redacts_raw_payload_and_llm_receipts_without_changing_shape() -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="projection-user"))
        item = Item(
            user_id=settings.single_user_id,
            source_type="text",
            title="safe list projection",
            raw_content="<html data-token='secret'>" + ("raw" * 500) + "</html>",
            clean_content="clean body",
            short_summary="summary",
            long_summary="long summary",
            llm_receipts=[{"response_id": "sensitive-runtime-id"}],
            status="ready",
        )
        db.add(item)
        db.commit()

        response = items_api._list_items_impl(db, limit=10)
        payload = response.model_dump(mode="json")
        assert len(payload["items"]) == 1
        assert payload["items"][0]["raw_content"] is None
        assert payload["items"][0]["llm_receipts"] == []

        detail = items_api._to_item_out(db, item)
        assert detail.raw_content == item.raw_content
        assert detail.llm_receipts == item.llm_receipts
    finally:
        db.close()
