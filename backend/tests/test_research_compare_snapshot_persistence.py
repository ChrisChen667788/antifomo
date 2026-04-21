from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models import User
from app.services import research_workspace_store
from app.services.research_workspace_store import (
    delete_compare_snapshot,
    get_compare_snapshot,
    list_compare_snapshots,
    save_compare_snapshot,
    save_tracking_topic,
)


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def test_compare_snapshot_round_trip_persists_rows_and_topic_link() -> None:
    db = _new_session()
    settings = get_settings()
    original_backfill_flag = research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED
    try:
        research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED = True
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

        topic = save_tracking_topic(
            db,
            {
                "name": "AI 浏览器跟踪",
                "keyword": "AI 浏览器",
            },
        )
        saved = save_compare_snapshot(
            db,
            {
                "name": "AI 浏览器对比快照",
                "query": "AI 浏览器",
                "region_filter": "华东",
                "industry_filter": "软件",
                "role_filter": "竞品",
                "tracking_topic_id": topic["id"],
                "summary": "聚焦竞品与预算信号",
                "rows": [
                    {
                        "id": "row-1",
                        "role": "竞品",
                        "name": "Perplexity",
                        "budgetSignal": "浏览器入口投入增强",
                        "sourceEntryId": "entry-1",
                    },
                    {
                        "id": "row-2",
                        "role": "甲方",
                        "name": "字节跳动",
                        "budgetSignal": "Agent 预算增加",
                        "sourceEntryId": "entry-2",
                    },
                ],
            },
        )

        listed = list_compare_snapshots(db)
        loaded = get_compare_snapshot(db, saved["id"])

        assert saved["tracking_topic_id"] == topic["id"]
        assert saved["tracking_topic_name"] == "AI 浏览器跟踪"
        assert saved["row_count"] == 2
        assert saved["source_entry_count"] == 2
        assert saved["preview_names"] == ["Perplexity", "字节跳动"]
        assert saved["roles"] == ["竞品", "甲方"]
        assert len(listed) == 1
        assert listed[0]["id"] == saved["id"]
        assert loaded is not None
        assert loaded["rows"][0]["name"] == "Perplexity"
        assert loaded["summary"] == "聚焦竞品与预算信号"
    finally:
        research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED = original_backfill_flag
        db.close()


def test_delete_compare_snapshot_removes_saved_snapshot() -> None:
    db = _new_session()
    settings = get_settings()
    original_backfill_flag = research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED
    try:
        research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED = True
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

        saved = save_compare_snapshot(
            db,
            {
                "name": "待删除快照",
                "rows": [{"id": "row-1", "role": "甲方", "name": "示例公司"}],
            },
        )

        assert delete_compare_snapshot(db, saved["id"]) is True
        assert list_compare_snapshots(db) == []
        assert get_compare_snapshot(db, saved["id"]) is None
    finally:
        research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED = original_backfill_flag
        db.close()
