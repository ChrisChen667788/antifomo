from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models import FocusSession, Item, SessionItem, User
from app.services.session_artifact_service import list_session_artifacts
from app.services.task_runtime import create_and_execute_task


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def test_export_tasks_persist_session_artifacts_with_real_item_links() -> None:
    db = _new_session()
    settings = get_settings()
    try:
        user = User(id=settings.single_user_id, name="demo")
        db.add(user)
        db.flush()

        session = FocusSession(
            user_id=settings.single_user_id,
            goal_text="整理 AI 浏览器行业情报",
            output_language="zh-CN",
            duration_minutes=25,
            start_time=datetime(2026, 3, 28, 9, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 3, 28, 9, 25, tzinfo=timezone.utc),
            status="finished",
            summary_text="本轮建议优先跟进深读条目。",
        )
        db.add(session)
        db.flush()

        item_a = Item(
            user_id=settings.single_user_id,
            source_type="url",
            source_url="https://example.com/a",
            source_domain="example.com",
            title="Agent Browser 行业观察",
            short_summary="行业摘要 A",
            long_summary="行业摘要 A 详细版",
            action_suggestion="deep_read",
            output_language="zh-CN",
            status="ready",
        )
        item_b = Item(
            user_id=settings.single_user_id,
            source_type="url",
            source_url="https://example.com/b",
            source_domain="example.com",
            title="竞品新动作",
            short_summary="行业摘要 B",
            long_summary="行业摘要 B 详细版",
            action_suggestion="later",
            output_language="zh-CN",
            status="ready",
        )
        db.add_all([item_a, item_b])
        db.flush()
        db.add_all(
            [
                SessionItem(session_id=session.id, item_id=item_a.id),
                SessionItem(session_id=session.id, item_id=item_b.id),
            ]
        )
        db.commit()

        reading_task = create_and_execute_task(
            db,
            user_id=settings.single_user_id,
            task_type="export_reading_list",
            session_id=session.id,
            input_payload={"output_language": "zh-CN"},
        )
        todo_task = create_and_execute_task(
            db,
            user_id=settings.single_user_id,
            task_type="export_todo_draft",
            session_id=session.id,
            input_payload={"output_language": "zh-CN"},
        )

        artifacts = list_session_artifacts(db, session.id)

        assert reading_task.status == "done"
        assert todo_task.status == "done"
        assert reading_task.output_payload is not None
        assert reading_task.output_payload["artifact_id"]
        assert "https://example.com/a" in str(reading_task.output_payload.get("content") or "")
        assert len(artifacts) == 2

        reading_artifact = next(item for item in artifacts if item["artifact_type"] == "reading_list")
        assert reading_artifact["items"][0]["title_snapshot"] == "Agent Browser 行业观察"
        assert reading_artifact["items"][0]["source_url_snapshot"] == "https://example.com/a"

        todo_artifact = next(item for item in artifacts if item["artifact_type"] == "todo_draft")
        assert todo_artifact["items"][0]["included_reason"] == "todo_followup"
        assert todo_artifact["items"][0]["source_url_snapshot"] == "https://example.com/a"
    finally:
        db.close()
