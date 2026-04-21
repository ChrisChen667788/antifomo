from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models import Item, User
from app.services.collector_diagnostics import (
    create_ingest_attempt,
    list_item_attempts,
    serialize_item_diagnostics,
    update_item_ingest_state,
)


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def test_collector_attempts_and_diagnostics_capture_route_and_access_state() -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

        plugin_item = Item(
            user_id=settings.single_user_id,
            source_type="plugin",
            source_url="https://mp.weixin.qq.com/s/plugin-demo",
            source_domain="mp.weixin.qq.com",
            title="插件正文测试",
            raw_content="这是插件提交的正文内容。" * 20,
            clean_content="这是插件提交的正文内容。" * 20,
            ingest_route="plugin",
            status="ready",
        )
        update_item_ingest_state(
            plugin_item,
            ingest_route="plugin",
            resolved_from_url=plugin_item.source_url,
            fallback_used=False,
        )
        db.add(plugin_item)
        db.flush()
        attempt = create_ingest_attempt(
            db,
            item=plugin_item,
            source_url=plugin_item.source_url,
            route_type="plugin",
            resolver="browser_plugin",
            attempt_status="ready",
            body_source="plugin_body",
        )
        db.commit()

        attempts = list_item_attempts(db, plugin_item.id)
        diagnostics = serialize_item_diagnostics(plugin_item, attempts)

        assert attempt.id
        assert len(attempts) == 1
        assert diagnostics["ingest_route"] == "plugin"
        assert diagnostics["content_acquisition_status"] == "body_acquired"
        assert diagnostics["body_source"] == "plugin_body"
        assert diagnostics["latest_attempt"]["resolver"] == "browser_plugin"

        access_limited_item = Item(
            user_id=settings.single_user_id,
            source_type="url",
            source_url="https://mp.weixin.qq.com/s/access-limited-demo",
            source_domain="mp.weixin.qq.com",
            title="公众号文章（访问受限）",
            raw_content="该链接当前访问受限，未能抓取到正文。可能需要登录或验证码。",
            clean_content="该链接当前访问受限，未能抓取到正文。可能需要登录或验证码。",
            ingest_route="direct_url",
            status="ready",
        )
        update_item_ingest_state(
            access_limited_item,
            ingest_route="direct_url",
            resolved_from_url=access_limited_item.source_url,
            fallback_used=False,
        )
        db.add(access_limited_item)
        db.commit()

        access_diagnostics = serialize_item_diagnostics(access_limited_item, [])
        assert access_diagnostics["content_acquisition_status"] == "access_limited"
        assert "访问受限" in str(access_diagnostics["content_acquisition_note"] or "")
    finally:
        db.close()
