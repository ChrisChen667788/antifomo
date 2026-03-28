from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models import FocusSession, Item, SessionItem, User
from app.models.research_entities import ResearchWatchlist, ResearchWatchlistChangeEvent
from app.services import daily_brief_service
from app.services.task_runtime import create_and_execute_task


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def test_daily_brief_uses_current_user_items_and_watchlist_changes(monkeypatch) -> None:
    db = _new_session()
    settings = get_settings()
    another_user_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    try:
        db.add_all(
            [
                User(id=settings.single_user_id, name="demo"),
                User(id=another_user_id, name="other"),
            ]
        )
        db.flush()

        db.add(
            Item(
                user_id=settings.single_user_id,
                source_type="url",
                source_url="https://example.com/a",
                source_domain="example.com",
                title="今日重点 A",
                short_summary="需要优先阅读的重点摘要",
                action_suggestion="deep_read",
                output_language="zh-CN",
                status="ready",
            )
        )
        db.add(
            Item(
                user_id=another_user_id,
                source_type="url",
                source_url="https://example.com/b",
                source_domain="example.com",
                title="其他用户内容",
                short_summary="不应出现在 demo 用户日报里",
                action_suggestion="later",
                output_language="zh-CN",
                status="ready",
            )
        )
        db.flush()

        demo_watchlist = ResearchWatchlist(
            user_id=settings.single_user_id,
            name="Demo Watchlist",
            query="AI 浏览器",
        )
        other_watchlist = ResearchWatchlist(
            user_id=another_user_id,
            name="Other Watchlist",
            query="无关主题",
        )
        db.add_all([demo_watchlist, other_watchlist])
        db.flush()

        db.add_all(
            [
                ResearchWatchlistChangeEvent(
                    watchlist_id=demo_watchlist.id,
                    change_type="added",
                    summary="新增上海甲方招采线索",
                    severity="high",
                    payload={},
                ),
                ResearchWatchlistChangeEvent(
                    watchlist_id=other_watchlist.id,
                    change_type="risk",
                    summary="其他用户的风险提示",
                    severity="medium",
                    payload={},
                ),
            ]
        )
        db.commit()

        monkeypatch.setattr(
            daily_brief_service,
            "_generate_audio",
            lambda snapshot, script: ("ready", f"/api/mobile/daily-brief/audio/{snapshot.id}"),
        )

        snapshot = daily_brief_service.build_daily_brief_snapshot(
            db,
            user_id=settings.single_user_id,
            force_refresh=True,
        )
        payload = daily_brief_service.serialize_daily_brief(snapshot)

        assert payload["headline"] == "今日重点 A"
        assert payload["top_items"][0]["title"] == "今日重点 A"
        assert len(payload["watchlist_changes"]) == 1
        assert payload["watchlist_changes"][0]["summary"] == "新增上海甲方招采线索"
        assert payload["audio_status"] == "ready"
    finally:
        db.close()


def test_extended_export_tasks_generate_expected_outputs() -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.flush()

        session = FocusSession(
            user_id=settings.single_user_id,
            goal_text="跟进浏览器赛道客户",
            output_language="zh-CN",
            duration_minutes=30,
            start_time=datetime(2026, 3, 28, 9, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 3, 28, 9, 30, tzinfo=timezone.utc),
            status="finished",
            summary_text="优先整理拜访提纲和老板同步要点。",
        )
        db.add(session)
        db.flush()

        item = Item(
            user_id=settings.single_user_id,
            source_type="url",
            source_url="https://example.com/browser",
            source_domain="example.com",
            title="浏览器赛道项目更新",
            short_summary="甲方试点继续推进，适合输出销售和老板简报。",
            long_summary="甲方试点继续推进，适合输出销售和老板简报。",
            action_suggestion="deep_read",
            output_language="zh-CN",
            status="ready",
        )
        db.add(item)
        db.flush()
        db.add(SessionItem(session_id=session.id, item_id=item.id))

        watchlist = ResearchWatchlist(
            user_id=settings.single_user_id,
            name="AI Browser Watchlist",
            query="AI 浏览器",
        )
        db.add(watchlist)
        db.flush()
        db.add(
            ResearchWatchlistChangeEvent(
                watchlist_id=watchlist.id,
                change_type="added",
                summary="新增重点甲方和预算信号",
                severity="high",
                payload={},
            )
        )
        db.commit()

        exec_task = create_and_execute_task(
            db,
            user_id=settings.single_user_id,
            task_type="export_exec_brief",
            session_id=session.id,
            input_payload={"output_language": "zh-CN"},
        )
        sales_task = create_and_execute_task(
            db,
            user_id=settings.single_user_id,
            task_type="export_sales_brief",
            session_id=session.id,
            input_payload={"output_language": "zh-CN"},
        )
        outreach_task = create_and_execute_task(
            db,
            user_id=settings.single_user_id,
            task_type="export_outreach_draft",
            input_payload={"output_language": "zh-CN"},
        )
        digest_task = create_and_execute_task(
            db,
            user_id=settings.single_user_id,
            task_type="export_watchlist_digest",
            input_payload={"output_language": "zh-CN"},
        )

        assert exec_task.status == "done"
        assert "老板" in str(exec_task.output_payload.get("content") or "")
        assert sales_task.status == "done"
        assert "销售" in str(sales_task.output_payload.get("content") or "")
        assert outreach_task.status == "done"
        assert "外联" in str(outreach_task.output_payload.get("content") or "")
        assert digest_task.status == "done"
        assert digest_task.output_payload["change_count"] == 1
        assert "新增重点甲方和预算信号" in str(digest_task.output_payload.get("content") or "")
    finally:
        db.close()
