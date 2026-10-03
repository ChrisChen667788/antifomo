from __future__ import annotations

import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import CollectorIngestAttempt, Item, User
from app.models.collector_evidence_entities import CollectorSourceItem
from app.services import collector_multiformat_service as multiformat_service
from app.services.collector_diagnostics import create_ingest_attempt, update_item_ingest_state
from app.services.collector_evidence_service import record_source_capture
from app.services.source_url_privacy import (
    canonicalize_persisted_url,
    normalize_fetch_url,
    redact_sensitive_urls,
)


RAW_WECHAT_URL = (
    "HTTPS://reader:password@MP.WEIXIN.QQ.COM.:443/s/?sn=z-last&scene=21&mid=123&"
    "__biz=MzDemo&idx=1&pass_ticket=private-ticket&chksm=stable&sn=a-first"
    "#wechat_redirect"
)
CANONICAL_WECHAT_URL = (
    "https://mp.weixin.qq.com/s?__biz=MzDemo&mid=123&idx=1&"
    "sn=a-first&sn=z-last&chksm=stable"
)


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)()


def test_fetch_url_keeps_query_but_persisted_url_uses_wechat_allowlist() -> None:
    fetch_url = normalize_fetch_url(RAW_WECHAT_URL)
    persisted_url = canonicalize_persisted_url(RAW_WECHAT_URL)

    assert fetch_url is not None
    assert "pass_ticket=private-ticket" in fetch_url
    assert "scene=21" in fetch_url
    assert fetch_url.endswith("#wechat_redirect") is False
    assert persisted_url == CANONICAL_WECHAT_URL
    assert "reader" not in persisted_url
    assert "password" not in persisted_url
    assert "private-ticket" not in persisted_url


def test_persisted_url_keeps_non_wechat_resource_query() -> None:
    assert canonicalize_persisted_url(
        "https://user:secret@WWW.YOUTUBE.COM:443/watch/?v=demo123&list=playlist#chapter"
    ) == "https://www.youtube.com/watch?v=demo123&list=playlist"


def test_redact_sensitive_urls_canonicalizes_urls_embedded_in_text() -> None:
    redacted = redact_sensitive_urls(
        f"fetch failed for {RAW_WECHAT_URL}；fallback https://user:secret@example.com/path?q=1."
    )

    assert CANONICAL_WECHAT_URL in redacted
    assert "https://example.com/path?q=1." in redacted
    assert "private-ticket" not in redacted
    assert "reader:password" not in redacted
    assert "user:secret" not in redacted


def test_item_attempt_and_evidence_urls_are_defensively_canonicalized() -> None:
    db = _new_session()
    try:
        user = User(id=uuid.uuid4(), name="privacy-user")
        item = Item(
            user_id=user.id,
            source_type="url",
            source_url=RAW_WECHAT_URL,
            resolved_from_url=RAW_WECHAT_URL,
            ingest_route="direct_url",
            raw_content="privacy fixture",
            status="pending",
        )
        db.add_all([user, item])
        db.flush()

        update_item_ingest_state(item, resolved_from_url=RAW_WECHAT_URL)
        attempt = create_ingest_attempt(
            db,
            item=item,
            source_url=RAW_WECHAT_URL,
            route_type="direct_url",
            resolver="privacy_test",
            attempt_status="queued",
        )
        capture = record_source_capture(
            db,
            item=item,
            connector="privacy_test",
            raw_content="privacy fixture",
            canonical_url=RAW_WECHAT_URL,
        )
        db.commit()

        assert item.source_url == CANONICAL_WECHAT_URL
        assert item.resolved_from_url == CANONICAL_WECHAT_URL
        assert attempt.source_url == CANONICAL_WECHAT_URL
        assert capture.source_item.canonical_url == CANONICAL_WECHAT_URL
    finally:
        db.close()


def test_multiformat_persists_only_canonical_urls(monkeypatch) -> None:
    db = _new_session()
    try:
        user = User(id=uuid.uuid4(), name="multiformat-privacy-user")
        db.add(user)
        db.commit()

        def fake_process(
            db_session: Session,
            item: Item,
            *,
            output_language: str | None = None,
            auto_archive: bool = True,
        ) -> Item:
            del output_language, auto_archive
            item.clean_content = item.raw_content
            item.status = "ready"
            db_session.add(item)
            db_session.flush()
            return item

        monkeypatch.setattr(multiformat_service, "process_item_in_session", fake_process)
        result = multiformat_service.ingest_newsletter(
            db,
            user_id=user.id,
            title="URL privacy fixture",
            raw_content="A sufficiently explicit newsletter body for the persistence boundary test.",
            source_url=RAW_WECHAT_URL,
        )

        stored_item = db.get(Item, result["item"].id)
        stored_attempt = db.scalar(
            select(CollectorIngestAttempt).where(CollectorIngestAttempt.item_id == stored_item.id)
        )
        stored_source = db.scalar(
            select(CollectorSourceItem).where(CollectorSourceItem.item_id == stored_item.id)
        )

        assert stored_item is not None
        assert stored_item.source_url == CANONICAL_WECHAT_URL
        assert stored_item.resolved_from_url == CANONICAL_WECHAT_URL
        assert stored_attempt is not None
        assert stored_attempt.source_url == CANONICAL_WECHAT_URL
        assert stored_source is not None
        assert stored_source.canonical_url == CANONICAL_WECHAT_URL
    finally:
        db.close()
