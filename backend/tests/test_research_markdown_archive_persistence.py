from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models import User
from app.services import research_workspace_store
from app.services.research_workspace_store import (
    delete_markdown_archive,
    get_markdown_archive,
    list_markdown_archives,
    mark_tracking_topic_refreshed,
    save_compare_snapshot,
    save_markdown_archive,
    save_tracking_topic,
)


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def test_markdown_archive_round_trip_persists_compare_and_topic_links() -> None:
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
                "region_filter": "华东",
                "industry_filter": "软件",
            },
        )
        refreshed = mark_tracking_topic_refreshed(
            db,
            topic["id"],
            last_refreshed_at="2026-04-03T09:00:00+00:00",
            last_report_entry_id=None,
            last_report_title="AI 浏览器专题版本一",
            source_count=12,
            evidence_density="high",
            source_quality="medium",
            last_refresh_note="新增甲方 2 / 新增预算线索 1",
            last_refresh_new_targets=["字节跳动", "腾讯"],
            last_refresh_new_budget_signals=["Agent 预算提升"],
            report_payload={
                "keyword": "AI 浏览器",
                "target_accounts": ["字节跳动", "腾讯"],
                "competitor_profiles": ["Perplexity"],
                "budget_signals": ["Agent 预算提升"],
            },
        )
        snapshot = save_compare_snapshot(
            db,
            {
                "name": "AI 浏览器对比快照",
                "query": "AI 浏览器",
                "tracking_topic_id": topic["id"],
                "summary": "聚焦竞品与预算信号",
                "rows": [
                    {
                        "id": "row-1",
                        "role": "竞品",
                        "name": "Perplexity",
                        "budgetSignal": "浏览器入口投入增强",
                        "sourceEntryId": "entry-1",
                    }
                ],
            },
        )

        saved = save_markdown_archive(
            db,
            {
                "archive_kind": "compare_markdown",
                "name": "AI 浏览器快照归档",
                "filename": "ai-browser-compare.md",
                "query": "AI 浏览器",
                "summary": "导出当前对比矩阵和差异摘要",
                "content": "# 对比矩阵\n\n- 快照 vs 关联版本\n",
                "compare_snapshot_id": snapshot["id"],
                "metadata_payload": {"row_count": 1},
            },
        )

        listed = list_markdown_archives(db)
        loaded = get_markdown_archive(db, saved["id"])

        assert refreshed["last_report_title"] == "AI 浏览器专题版本一"
        assert saved["tracking_topic_id"] == topic["id"]
        assert saved["tracking_topic_name"] == "AI 浏览器跟踪"
        assert saved["compare_snapshot_id"] == snapshot["id"]
        assert saved["compare_snapshot_name"] == "AI 浏览器对比快照"
        assert saved["report_version_title"] == "AI 浏览器专题版本一"
        assert saved["content_length"] > 10
        assert len(listed) == 1
        assert listed[0]["id"] == saved["id"]
        assert listed[0]["metadata_payload"]["row_count"] == 1
        assert loaded is not None
        assert loaded["content"].startswith("# 对比矩阵")
        assert loaded["metadata_payload"]["row_count"] == 1
    finally:
        research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED = original_backfill_flag
        db.close()


def test_delete_markdown_archive_removes_saved_archive() -> None:
    db = _new_session()
    settings = get_settings()
    original_backfill_flag = research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED
    try:
        research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED = True
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

        saved = save_markdown_archive(
            db,
            {
                "archive_kind": "topic_version_recap",
                "name": "专题复盘归档",
                "filename": "topic-recap.md",
                "content": "# 专题版本复盘报告\n",
            },
        )

        assert delete_markdown_archive(db, saved["id"]) is True
        assert list_markdown_archives(db) == []
        assert get_markdown_archive(db, saved["id"]) is None
    finally:
        research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED = original_backfill_flag
        db.close()


def test_markdown_archive_supports_archive_diff_recap_kind() -> None:
    db = _new_session()
    settings = get_settings()
    original_backfill_flag = research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED
    try:
        research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED = True
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

        saved = save_markdown_archive(
            db,
            {
                "archive_kind": "archive_diff_recap",
                "name": "归档差异复盘",
                "filename": "archive-diff-recap.md",
                "summary": "当前归档新增 2 个 section。",
                "content": "# 历史归档差异复盘报告\n\n- 当前归档新增 2 个 section。\n",
                "metadata_payload": {
                    "current_archive_id": "archive-a",
                    "compare_archive_id": "archive-b",
                    "changed_section_count": 3,
                },
            },
        )

        loaded = get_markdown_archive(db, saved["id"])

        assert saved["archive_kind"] == "archive_diff_recap"
        assert saved["metadata_payload"]["changed_section_count"] == 3
        assert loaded is not None
        assert loaded["archive_kind"] == "archive_diff_recap"
        assert loaded["metadata_payload"]["current_archive_id"] == "archive-a"
        assert loaded["metadata_payload"]["changed_section_count"] == 3
    finally:
        research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED = original_backfill_flag
        db.close()
