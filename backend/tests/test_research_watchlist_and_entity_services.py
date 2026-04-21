from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models import ResearchTrackingTopic, User
from app.services.entity_catalog_service import get_entity_detail, sync_tracking_topic_entities
from app.services.research_watchlist_service import (
    append_watchlist_change_events,
    compute_watchlist_next_due_at,
    get_watchlist_model,
    list_watchlist_change_events,
    list_due_watchlists,
    list_watchlists,
    normalize_watchlist_schedule,
    save_watchlist,
)


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def test_watchlist_stores_latest_change_events() -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.flush()
        topic = ResearchTrackingTopic(
            user_id=settings.single_user_id,
            name="AIGC 跟踪",
            keyword="AIGC",
            research_focus="长三角营销内容",
            perspective="all",
            region_filter="长三角",
            industry_filter="营销",
            notes="",
        )
        db.add(topic)
        db.commit()

        watchlist = save_watchlist(
            db,
            {
                "name": "AIGC Watchlist",
                "watch_type": "topic",
                "query": "AIGC",
                "tracking_topic_id": str(topic.id),
                "region_filter": "长三角",
                "industry_filter": "营销",
                "alert_level": "medium",
                "schedule": "manual",
            },
        )
        append_watchlist_change_events(
            db,
            watchlist["id"],
            [
                {
                    "change_type": "added",
                    "summary": "新增甲方线索 2 条",
                    "payload": {"targets": ["品牌A", "品牌B"]},
                    "severity": "high",
                }
            ],
        )

        rows = list_watchlists(db)
        assert len(rows) == 1
        assert rows[0]["latest_changes"]
        assert rows[0]["latest_changes"][0]["summary"] == "新增甲方线索 2 条"
        assert list_watchlist_change_events(db, watchlist["id"])[0]["severity"] == "high"
    finally:
        db.close()


def test_watchlist_schedule_marks_due_items_and_next_due() -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.flush()
        topic = ResearchTrackingTopic(
            user_id=settings.single_user_id,
            name="AI 漫剧跟踪",
            keyword="AI 漫剧",
            research_focus="头部公司与商机",
            perspective="all",
            region_filter="",
            industry_filter="内容",
            notes="",
        )
        db.add(topic)
        db.commit()

        daily_watchlist = save_watchlist(
            db,
            {
                "name": "Daily Watchlist",
                "watch_type": "topic",
                "query": "AI 漫剧",
                "tracking_topic_id": str(topic.id),
                "schedule": "daily",
            },
        )
        due = list_due_watchlists(db)
        assert len(due) == 1
        assert str(due[0].id) == daily_watchlist["id"]
        payload = list_watchlists(db)[0]
        assert payload["is_due"] is True
        assert payload["next_due_at"] is not None

        watchlist_model = get_watchlist_model(db, daily_watchlist["id"])
        assert watchlist_model is not None
        append_watchlist_change_events(
            db,
            daily_watchlist["id"],
            [{"summary": "已刷新", "change_type": "rewritten", "severity": "low"}],
            checked_at=datetime.now(timezone.utc),
        )
        watchlist_model = get_watchlist_model(db, daily_watchlist["id"])
        assert watchlist_model is not None
        next_due_at = compute_watchlist_next_due_at(watchlist_model)
        assert next_due_at is not None
        assert next_due_at > datetime.now(timezone.utc) - timedelta(minutes=1)
        assert normalize_watchlist_schedule("weekday") == "weekdays"
    finally:
        db.close()


def test_entity_catalog_syncs_canonical_name_aliases_and_topic_links() -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

        updated_ids = sync_tracking_topic_entities(
            db,
            topic_id="topic-001",
            report_payload={
                "source_diagnostics": {
                    "scope_regions": ["长三角"],
                    "scope_industries": ["营销"],
                },
                "entity_graph": {
                    "entities": [
                        {
                            "canonical_name": "腾讯云",
                            "entity_type": "partner",
                            "aliases": ["Tencent Cloud", "腾讯云计算"],
                            "source_count": 3,
                            "source_tier_counts": {"official": 1, "media": 2},
                            "evidence_links": [
                                {
                                    "title": "腾讯云案例",
                                    "url": "https://cloud.tencent.com/case",
                                    "source_label": "腾讯云",
                                    "source_tier": "official",
                                }
                            ],
                        }
                    ],
                    "target_entities": [],
                    "competitor_entities": [],
                    "partner_entities": [],
                },
            },
        )

        assert len(updated_ids) == 1
        detail = get_entity_detail(db, updated_ids[0])
        assert detail is not None
        assert detail["canonical_name"] == "腾讯云"
        assert "Tencent Cloud" in detail["aliases"]
        assert "topic-001" in detail["linked_topic_ids"]
        assert detail["evidence_links"][0]["url"] == "https://cloud.tencent.com/case"
    finally:
        db.close()
