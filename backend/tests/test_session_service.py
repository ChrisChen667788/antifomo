from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.entities import FocusSession, Item, SessionItem, User
from app.services import session_service
from app.services.session_service import (
    calculate_remaining_seconds,
    finish_session,
    gather_items_in_window,
    pause_session,
    resume_session,
    sync_running_sessions_for_item,
)


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def test_gather_items_in_window_includes_same_second_items() -> None:
    db = _new_session()
    try:
        user = User(id=uuid.uuid4(), name="demo")
        db.add(user)
        db.flush()

        # start_time has microseconds; item created at the same second boundary.
        start_time = datetime(2026, 3, 16, 10, 15, 49, 921010, tzinfo=timezone.utc)
        item = Item(
            user_id=user.id,
            source_type="text",
            title="same-second",
            raw_content="demo",
            status="ready",
            created_at=datetime(2026, 3, 16, 10, 15, 49, tzinfo=timezone.utc),
        )
        db.add(item)
        db.commit()

        items = gather_items_in_window(
            db,
            user_id=user.id,
            start_time=start_time,
            end_time=datetime(2026, 3, 16, 10, 16, 22, 156262, tzinfo=timezone.utc),
        )
        assert len(items) == 1
        assert items[0].id == item.id
    finally:
        db.close()


def test_pause_resume_finish_keeps_active_windows_only(monkeypatch) -> None:
    db = _new_session()
    try:
        user = User(id=uuid.uuid4(), name="demo")
        db.add(user)
        db.flush()

        session = FocusSession(
            user_id=user.id,
            goal_text="finish pause resume",
            output_language="zh-CN",
            duration_minutes=25,
            start_time=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
            current_window_started_at=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
            elapsed_seconds=0,
            status="running",
        )
        db.add(session)
        db.flush()

        before_pause = Item(
            user_id=user.id,
            source_type="text",
            title="before pause",
            raw_content="demo",
            status="ready",
            created_at=datetime(2026, 4, 4, 10, 5, tzinfo=timezone.utc),
        )
        paused_gap = Item(
            user_id=user.id,
            source_type="text",
            title="during pause",
            raw_content="demo",
            status="ready",
            created_at=datetime(2026, 4, 4, 10, 12, tzinfo=timezone.utc),
        )
        after_resume = Item(
            user_id=user.id,
            source_type="text",
            title="after resume",
            raw_content="demo",
            status="ready",
            created_at=datetime(2026, 4, 4, 10, 23, tzinfo=timezone.utc),
        )
        db.add_all([before_pause, paused_gap, after_resume])
        db.commit()

        class PauseDateTime(datetime):
            @classmethod
            def now(cls, tz=None):  # type: ignore[override]
                value = datetime(2026, 4, 4, 10, 10, tzinfo=timezone.utc)
                return value if tz else value.replace(tzinfo=None)

        monkeypatch.setattr(session_service, "datetime", PauseDateTime)
        session, paused_items, paused_metrics = pause_session(db, session)

        assert session.status == "paused"
        assert session.elapsed_seconds == 10 * 60
        assert calculate_remaining_seconds(session) == 15 * 60
        assert [item.title for item in paused_items] == ["before pause"]
        assert paused_metrics.new_content_count == 1

        class ResumeDateTime(datetime):
            @classmethod
            def now(cls, tz=None):  # type: ignore[override]
                value = datetime(2026, 4, 4, 10, 20, tzinfo=timezone.utc)
                return value if tz else value.replace(tzinfo=None)

        monkeypatch.setattr(session_service, "datetime", ResumeDateTime)
        session, resumed_items, resumed_metrics = resume_session(db, session)

        assert session.status == "running"
        assert session.current_window_started_at == datetime(2026, 4, 4, 10, 20, tzinfo=timezone.utc)
        assert [item.title for item in resumed_items] == ["before pause"]
        assert resumed_metrics.new_content_count == 1

        class FinishDateTime(datetime):
            @classmethod
            def now(cls, tz=None):  # type: ignore[override]
                value = datetime(2026, 4, 4, 10, 25, tzinfo=timezone.utc)
                return value if tz else value.replace(tzinfo=None)

        monkeypatch.setattr(session_service, "datetime", FinishDateTime)
        session, finished_items, finished_metrics = finish_session(db, session, output_language="zh-CN")

        assert session.status == "finished"
        assert session.elapsed_seconds == 15 * 60
        assert calculate_remaining_seconds(session) == 10 * 60
        assert [item.title for item in finished_items] == ["before pause", "after resume"]
        assert finished_metrics.new_content_count == 2
        assert session.summary_text

        persisted_item_ids = {
            row.item_id
            for row in db.query(SessionItem).filter(SessionItem.session_id == session.id).all()
        }
        assert before_pause.id in persisted_item_ids
        assert after_resume.id in persisted_item_ids
        assert paused_gap.id not in persisted_item_ids
    finally:
        db.close()


def test_sync_running_sessions_for_item_respects_resumed_window_start() -> None:
    db = _new_session()
    try:
        user = User(id=uuid.uuid4(), name="demo")
        db.add(user)
        db.flush()

        session = FocusSession(
            user_id=user.id,
            goal_text="resumed",
            output_language="zh-CN",
            duration_minutes=25,
            start_time=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
            current_window_started_at=datetime(2026, 4, 4, 10, 20, tzinfo=timezone.utc),
            elapsed_seconds=10 * 60,
            status="running",
        )
        db.add(session)
        db.flush()

        paused_gap_item = Item(
            user_id=user.id,
            source_type="text",
            title="paused gap",
            raw_content="demo",
            status="ready",
            created_at=datetime(2026, 4, 4, 10, 12, tzinfo=timezone.utc),
        )
        resumed_item = Item(
            user_id=user.id,
            source_type="text",
            title="resumed item",
            raw_content="demo",
            status="ready",
            created_at=datetime(2026, 4, 4, 10, 22, tzinfo=timezone.utc),
        )
        db.add_all([paused_gap_item, resumed_item])
        db.commit()

        assert sync_running_sessions_for_item(db, paused_gap_item) == 0
        assert sync_running_sessions_for_item(db, resumed_item) == 1
        db.flush()

        persisted_item_ids = {
            row.item_id
            for row in db.query(SessionItem).filter(SessionItem.session_id == session.id).all()
        }
        assert resumed_item.id in persisted_item_ids
        assert paused_gap_item.id not in persisted_item_ids
    finally:
        db.close()
