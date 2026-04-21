from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models import User
from app.services import research_workspace_store
from app.services.research_workspace_store import (
    get_tracking_topic,
    list_saved_views,
    list_tracking_topics,
    save_saved_view,
    save_tracking_topic,
)


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def test_research_workspace_round_trip_persists_saved_view_and_topic() -> None:
    db = _new_session()
    settings = get_settings()
    original_backfill_flag = research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED
    try:
        research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED = True
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

        saved_view = save_saved_view(
            db,
            {
                "name": "长三角游戏",
                "query": "游戏 发行",
                "filter_mode": "reports",
                "perspective": "regional",
                "region_filter": "长三角",
                "industry_filter": "游戏",
                "focus_only": True,
            },
        )
        topic = save_tracking_topic(
            db,
            {
                "name": "上海发行观察",
                "keyword": "上海 游戏 发行",
                "research_focus": "找具体发行商和甲方",
                "perspective": "client_followup",
                "region_filter": "长三角",
                "industry_filter": "游戏",
                "notes": "优先保留官方源",
            },
        )

        views = list_saved_views(db)
        topics = list_tracking_topics(db)
        loaded_topic = get_tracking_topic(db, topic["id"])

        assert len(views) == 1
        assert views[0]["id"] == saved_view["id"]
        assert views[0]["focus_only"] is True
        assert views[0]["region_filter"] == "长三角"

        assert len(topics) == 1
        assert topics[0]["id"] == topic["id"]
        assert topics[0]["last_refresh_status"] == "idle"
        assert topics[0]["report_history"] == []
        assert topics[0]["last_report_entry_id"] is None

        assert loaded_topic is not None
        assert loaded_topic["keyword"] == "上海 游戏 发行"
        assert loaded_topic["research_focus"] == "找具体发行商和甲方"
        assert loaded_topic["report_history"] == []
    finally:
        research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED = original_backfill_flag
        db.close()
