from __future__ import annotations

import hashlib
import uuid

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.collector_evidence_entities import (
    CollectorDocumentRevision,
    CollectorRawAsset,
    CollectorSourceItem,
    CollectorSourceSpan,
    CollectorTransformReceipt,
)
from app.models.entities import Item, User
from app.services.collector_evidence_service import (
    canonicalize_source_url,
    latest_revision_for_item,
    mark_source_tombstone,
    record_source_capture,
    record_transform_receipts,
)


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)()


def _seed_item(db: Session) -> Item:
    user = User(id=uuid.uuid4(), name="evidence-user")
    db.add(user)
    db.flush()
    item = Item(
        user_id=user.id,
        source_type="url",
        source_url="https://mp.weixin.qq.com/s/evidence-demo",
        ingest_route="wechat_favorites",
        raw_content="capture-v1",
        status="pending",
    )
    db.add(item)
    db.flush()
    return item


def test_source_capture_is_idempotent_and_updates_only_on_new_raw_revision() -> None:
    db = _new_session()
    try:
        item = _seed_item(db)
        first = record_source_capture(
            db,
            item=item,
            connector="wechat_favorites_history",
            raw_content="<html>raw-v1</html>",
            clean_content="正文版本一",
            parser_fingerprint="parser-v1",
        )
        repeated = record_source_capture(
            db,
            item=item,
            connector="wechat_favorites_history",
            raw_content="<html>raw-v1</html>",
            clean_content="正文版本一",
            parser_fingerprint="parser-v1",
        )
        changed = record_source_capture(
            db,
            item=item,
            connector="wechat_favorites_history",
            raw_content="<html>raw-v2</html>",
            clean_content="正文版本二",
            parser_fingerprint="parser-v1",
        )
        db.flush()

        assert first.revision_created is True
        assert repeated.revision_created is False
        assert repeated.revision.id == first.revision.id
        assert changed.revision_created is True
        assert changed.source_item.id == first.source_item.id
        assert changed.revision.id != first.revision.id
        assert changed.source_item.current_revision_key == changed.revision.revision_key
        assert latest_revision_for_item(db, item_id=item.id).id == changed.revision.id
        assert db.scalar(select(func.count()).select_from(CollectorSourceItem)) == 1
        assert db.scalar(select(func.count()).select_from(CollectorRawAsset)) == 2
        assert db.scalar(select(func.count()).select_from(CollectorDocumentRevision)) == 2
        assert db.scalar(select(func.count()).select_from(CollectorSourceSpan)) == 2
    finally:
        db.close()


def test_processed_revision_stays_current_when_preliminary_capture_is_replayed() -> None:
    db = _new_session()
    try:
        item = _seed_item(db)
        raw_content = "<article>标题：原始页面\n正文：最终正文</article>"
        preliminary_text = "标题：原始页面 正文：最终正文"
        final_text = "最终正文"
        preliminary = record_source_capture(
            db,
            item=item,
            connector="plugin",
            raw_content=raw_content,
            clean_content=preliminary_text,
            parser_fingerprint="item-processor-v2",
        )
        processed = record_source_capture(
            db,
            item=item,
            connector="plugin",
            raw_content=raw_content,
            clean_content=final_text,
            parser_fingerprint="item-processor-v2",
            parse_status="body_acquired",
        )
        receipts = record_transform_receipts(
            db,
            item=item,
            revision=processed.revision,
            input_text=final_text,
            receipts=[
                {
                    "prompt_name": "summarize.txt",
                    "prompt_schema_sha256": "a" * 64,
                    "output_sha256": "b" * 64,
                    "provider": "fixture",
                    "model": "fixture-v1",
                    "status": "succeeded",
                    "parse_status": "valid",
                }
            ],
        )
        replayed = record_source_capture(
            db,
            item=item,
            connector="plugin",
            raw_content=raw_content,
            clean_content=preliminary_text,
            parser_fingerprint="item-processor-v2",
        )
        db.flush()

        assert preliminary.revision.id != processed.revision.id
        assert replayed.revision_created is False
        assert replayed.revision.id == preliminary.revision.id
        assert replayed.source_item.current_revision_key == processed.revision.revision_key
        latest = latest_revision_for_item(db, item_id=item.id)
        assert latest is not None
        assert latest.id == processed.revision.id
        assert processed.revision.normalized_sha256 == hashlib.sha256(final_text.encode()).hexdigest()
        assert preliminary.revision.normalized_sha256 == hashlib.sha256(
            preliminary_text.encode()
        ).hexdigest()

        spans = list(db.scalars(select(CollectorSourceSpan)))
        spans_by_revision = {span.revision_id: span for span in spans}
        assert spans_by_revision[preliminary.revision.id].text == preliminary_text
        assert spans_by_revision[processed.revision.id].text == final_text
        assert receipts[0].revision_id == processed.revision.id
        assert db.scalar(select(func.count()).select_from(CollectorRawAsset)) == 1
        assert db.scalar(select(func.count()).select_from(CollectorDocumentRevision)) == 2
        assert db.scalar(select(func.count()).select_from(CollectorSourceSpan)) == 2
        assert db.scalar(select(func.count()).select_from(CollectorTransformReceipt)) == 1
    finally:
        db.close()


def test_replaying_known_older_native_version_keeps_head_metadata_consistent() -> None:
    db = _new_session()
    try:
        item = _seed_item(db)
        older = record_source_capture(
            db,
            item=item,
            connector="wechat_customer_service",
            account_scope="kf-demo",
            native_item_id="msg-001",
            native_version="v1",
            raw_content="raw-v1",
            clean_content="正文版本一",
        )
        current = record_source_capture(
            db,
            item=item,
            connector="wechat_customer_service",
            account_scope="kf-demo",
            native_item_id="msg-001",
            native_version="v2",
            raw_content="raw-v2",
            clean_content="正文版本二",
        )
        replayed = record_source_capture(
            db,
            item=item,
            connector="wechat_customer_service",
            account_scope="kf-demo",
            native_item_id="msg-001",
            native_version="v1",
            raw_content="raw-v1",
            clean_content="正文版本一",
        )
        db.flush()

        assert replayed.revision_created is False
        assert replayed.revision.id == older.revision.id
        assert replayed.source_item.current_revision_key == current.revision.revision_key
        assert replayed.source_item.native_version == "v2"
        assert latest_revision_for_item(db, item_id=item.id).id == current.revision.id
    finally:
        db.close()


def test_explicit_older_backfill_records_revision_without_advancing_head() -> None:
    db = _new_session()
    try:
        item = _seed_item(db)
        current = record_source_capture(
            db,
            item=item,
            connector="wechat_customer_service",
            account_scope="kf-demo",
            native_item_id="msg-002",
            native_version="v2",
            raw_content="raw-v2",
            clean_content="正文版本二",
        )
        older_backfill = record_source_capture(
            db,
            item=item,
            connector="wechat_customer_service",
            account_scope="kf-demo",
            native_item_id="msg-002",
            native_version="v1",
            raw_content="previously unseen raw-v1",
            clean_content="正文版本一",
            advance_current=False,
        )
        db.flush()

        assert older_backfill.revision_created is True
        assert older_backfill.revision.native_version == "v1"
        assert older_backfill.source_item.current_revision_key == current.revision.revision_key
        assert older_backfill.source_item.native_version == "v2"
        assert latest_revision_for_item(db, item_id=item.id).id == current.revision.id
    finally:
        db.close()


def test_source_metadata_is_creation_seed_and_capture_diagnostics_are_revision_scoped() -> None:
    db = _new_session()
    try:
        item = _seed_item(db)
        first_metadata = {"identity_origin": "initial-import", "resolver": "first"}
        second_metadata = {"resolver": "retry", "attempt": 2}

        first = record_source_capture(
            db,
            item=item,
            connector="wechat_favorites_history",
            raw_content="raw-v1",
            clean_content="正文一",
            metadata_payload=first_metadata,
        )
        second = record_source_capture(
            db,
            item=item,
            connector="wechat_favorites_history",
            raw_content="raw-v2",
            clean_content="正文二",
            metadata_payload=second_metadata,
        )
        db.flush()

        assert second.source_item.id == first.source_item.id
        assert second.source_item.metadata_payload == {"identity_basis": "canonical_url"}
        assert first.revision.diagnostics_payload == first_metadata
        assert second.revision.diagnostics_payload == second_metadata
    finally:
        db.close()


def test_transform_receipt_is_stage_fingerprint_idempotent_and_tombstone_is_explicit() -> None:
    db = _new_session()
    try:
        item = _seed_item(db)
        capture = record_source_capture(
            db,
            item=item,
            connector="wechat_customer_service",
            account_scope="kf-demo",
            native_item_id="msg-001",
            raw_content="原始消息正文",
            clean_content="原始消息正文",
            parser_fingerprint="parser-v1",
        )
        receipt_payload = {
            "prompt_name": "summarize.txt",
            "prompt_schema_sha256": "a" * 64,
            "output_sha256": "b" * 64,
            "provider": "fixture",
            "model": "fixture-v1",
            "status": "succeeded",
            "parse_status": "valid",
            "usage": {"total_tokens": 12},
            "metadata": {},
        }
        first = record_transform_receipts(
            db,
            item=item,
            revision=capture.revision,
            input_text="原始消息正文",
            receipts=[receipt_payload],
        )
        repeated = record_transform_receipts(
            db,
            item=item,
            revision=capture.revision,
            input_text="原始消息正文",
            receipts=[receipt_payload],
        )
        changed_output = record_transform_receipts(
            db,
            item=item,
            revision=capture.revision,
            input_text="原始消息正文",
            receipts=[{**receipt_payload, "output_sha256": "c" * 64}],
        )
        next_capture = record_source_capture(
            db,
            item=item,
            connector="wechat_customer_service",
            account_scope="kf-demo",
            native_item_id="msg-001",
            raw_content="原始消息正文 v2",
            clean_content="原始消息正文",
            parser_fingerprint="parser-v1",
        )
        next_revision = record_transform_receipts(
            db,
            item=item,
            revision=next_capture.revision,
            input_text="原始消息正文",
            receipts=[receipt_payload],
        )
        tombstoned = mark_source_tombstone(
            db,
            user_id=item.user_id,
            connector="wechat_customer_service",
            account_scope="kf-demo",
            native_item_id="msg-001",
            reason="recall event",
        )
        db.flush()

        assert first[0].id == repeated[0].id
        assert changed_output[0].id != first[0].id
        assert next_revision[0].id not in {first[0].id, changed_output[0].id}
        assert db.scalar(select(func.count()).select_from(CollectorTransformReceipt)) == 3
        assert tombstoned is not None
        assert tombstoned.state == "tombstoned"
        assert tombstoned.tombstoned_at is not None
        assert tombstoned.metadata_payload["tombstone_reason"] == "recall event"
    finally:
        db.close()


def test_wechat_canonical_url_drops_transient_and_sensitive_query_values() -> None:
    canonical = canonicalize_source_url(
        "https://MP.WEIXIN.QQ.COM/s?__biz=MzDemo&mid=123&idx=1&sn=stable&"
        "scene=21&pass_ticket=secret&from=timeline#wechat_redirect"
    )

    assert canonical == "https://mp.weixin.qq.com/s?__biz=MzDemo&mid=123&idx=1&sn=stable"


def test_wechat_canonical_url_is_stable_across_query_order() -> None:
    first = canonicalize_source_url(
        "https://mp.weixin.qq.com/s?__biz=MzX&mid=1&idx=2&sn=abc&scene=1"
    )
    second = canonicalize_source_url(
        "https://mp.weixin.qq.com/s?sn=abc&idx=2&mid=1&__biz=MzX&scene=9"
    )

    assert first == second == "https://mp.weixin.qq.com/s?__biz=MzX&mid=1&idx=2&sn=abc"


def test_same_native_url_for_two_item_projections_rejects_identity_fork() -> None:
    db = _new_session()
    try:
        first_item = _seed_item(db)
        second_item = Item(
            user_id=first_item.user_id,
            source_type="url",
            source_url=first_item.source_url,
            ingest_route="wechat_favorites",
            raw_content="capture-v2",
            status="pending",
        )
        db.add(second_item)
        db.flush()

        first = record_source_capture(
            db,
            item=first_item,
            connector="wechat_favorites_history",
            raw_content="raw-one",
            clean_content="正文一",
        )
        with pytest.raises(ValueError, match="already bound"):
            record_source_capture(
                db,
                item=second_item,
                connector="wechat_favorites_history",
                raw_content="raw-two",
                clean_content="正文二",
            )
        db.flush()

        assert latest_revision_for_item(db, item_id=first_item.id).id == first.revision.id
        assert latest_revision_for_item(db, item_id=second_item.id) is None
        assert db.scalar(select(func.count()).select_from(CollectorSourceItem)) == 1
    finally:
        db.close()


def test_tombstone_uses_same_normalized_source_identity_as_capture() -> None:
    db = _new_session()
    try:
        item = _seed_item(db)
        native_item_id = "message-" + ("x" * 600)
        capture = record_source_capture(
            db,
            item=item,
            connector="  WeChat Customer Service  ",
            account_scope="  account-a  ",
            native_item_id=f"  {native_item_id}  ",
            raw_content="正文",
        )
        tombstoned = mark_source_tombstone(
            db,
            user_id=item.user_id,
            connector="wechat customer service",
            account_scope="account-a",
            native_item_id=native_item_id,
            reason="recall",
        )

        assert tombstoned is not None
        assert tombstoned.id == capture.source_item.id
        assert tombstoned.state == "tombstoned"
    finally:
        db.close()


def test_transform_receipt_rejects_cross_item_and_cross_user_lineage() -> None:
    db = _new_session()
    try:
        first_item = _seed_item(db)
        capture = record_source_capture(
            db,
            item=first_item,
            connector="wechat_favorites_history",
            raw_content="first raw",
            clean_content="first body",
        )
        second_user = User(id=uuid.uuid4(), name="other-user")
        db.add(second_user)
        db.flush()
        second_item = Item(
            user_id=second_user.id,
            source_type="text",
            raw_content="second body",
            status="pending",
        )
        db.add(second_item)
        db.flush()

        with pytest.raises(ValueError, match="does not own"):
            record_transform_receipts(
                db,
                item=second_item,
                revision=capture.revision,
                input_text="second body",
                receipts=[{"prompt_name": "summarize.txt", "status": "succeeded"}],
            )
        assert db.scalar(select(func.count()).select_from(CollectorTransformReceipt)) == 0
    finally:
        db.close()
