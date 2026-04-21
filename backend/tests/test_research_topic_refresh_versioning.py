from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models import KnowledgeEntry, User
from app.services import research_workspace_store
from app.services.research_workspace_store import (
    get_latest_tracking_topic_report_payload,
    get_tracking_topic,
    get_tracking_topic_version,
    list_tracking_topic_timeline,
    list_tracking_topic_versions,
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


def test_tracking_topic_refresh_creates_version_and_returns_report_payload() -> None:
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
                "name": "AI 浏览器专题",
                "keyword": "AI 浏览器",
                "research_focus": "追踪具体公司和合作伙伴",
            },
        )

        entry_id = uuid.uuid4()
        db.add(
            KnowledgeEntry(
                id=entry_id,
                user_id=settings.single_user_id,
                title="AI 浏览器专题研报",
                content="研报正文",
                collection_name="长期跟踪专题",
                metadata_payload={"kind": "research_report"},
            )
        )
        db.commit()

        first_report = {
            "keyword": "AI 浏览器",
            "research_focus": "追踪具体公司和合作伙伴",
            "report_title": "AI 浏览器专题研报",
            "executive_summary": "第一版摘要",
            "target_accounts": ["字节跳动"],
            "competitor_profiles": ["Perplexity"],
            "budget_signals": ["浏览器端 Agent 投入加大"],
            "sources": [],
        }
        refreshed = mark_tracking_topic_refreshed(
            db,
            topic["id"],
            last_refreshed_at=datetime(2026, 3, 28, 10, 0, tzinfo=timezone.utc).isoformat(),
            last_report_entry_id=str(entry_id),
            last_report_title="AI 浏览器专题研报",
            source_count=6,
            evidence_density="medium",
            source_quality="high",
            last_refresh_note="新增 1 个甲方",
            last_refresh_new_targets=["字节跳动"],
            last_refresh_new_competitors=["Perplexity"],
            last_refresh_new_budget_signals=["浏览器端 Agent 投入加大"],
            report_payload=first_report,
            action_cards_payload=[{"title": "跟进字节跳动", "owner": "BD"}],
        )

        versions = list_tracking_topic_versions(db, topic["id"])
        assert refreshed is not None
        assert refreshed["last_refresh_status"] == "succeeded"
        assert refreshed["last_report_entry_id"] == str(entry_id)
        assert len(refreshed["report_history"]) == 1
        assert refreshed["report_history"][0]["id"]
        assert versions[0]["entry_id"] == str(entry_id)
        assert versions[0]["report"]["executive_summary"] == "第一版摘要"
        assert versions[0]["action_cards"][0]["title"] == "跟进字节跳动"

        second_report = {
            **first_report,
            "report_title": "AI 浏览器专题研报 v2",
            "executive_summary": "第二版摘要",
            "target_accounts": ["字节跳动", "阿里云"],
        }
        refreshed_again = mark_tracking_topic_refreshed(
            db,
            topic["id"],
            last_refreshed_at=datetime(2026, 3, 28, 12, 30, tzinfo=timezone.utc).isoformat(),
            last_report_entry_id=None,
            last_report_title="AI 浏览器专题研报 v2",
            source_count=9,
            evidence_density="high",
            source_quality="high",
            last_refresh_note="新增阿里云",
            last_refresh_new_targets=["阿里云"],
            report_payload=second_report,
            action_cards_payload=[{"title": "跟进阿里云", "owner": "BD"}],
        )

        versions = list_tracking_topic_versions(db, topic["id"])
        latest_version = get_tracking_topic_version(db, topic["id"], versions[0]["id"])
        latest_topic = get_tracking_topic(db, topic["id"])
        latest_payload = get_latest_tracking_topic_report_payload(db, topic["id"])

        assert refreshed_again is not None
        assert len(versions) == 2
        assert versions[0]["title"] == "AI 浏览器专题研报 v2"
        assert versions[0]["entry_id"] is None
        assert versions[1]["entry_id"] == str(entry_id)
        assert latest_version is not None
        assert latest_version["report"]["executive_summary"] == "第二版摘要"
        assert latest_version["action_cards"][0]["title"] == "跟进阿里云"
        assert latest_topic is not None
        assert latest_topic["last_report_entry_id"] is None
        assert latest_topic["report_history"][0]["title"] == "AI 浏览器专题研报 v2"
        assert latest_payload is not None
        assert latest_payload["executive_summary"] == "第二版摘要"
    finally:
        research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED = original_backfill_flag
        db.close()


def test_tracking_topic_timeline_links_compare_snapshot_to_latest_report_version() -> None:
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
                "name": "AI 浏览器专题",
                "keyword": "AI 浏览器",
                "research_focus": "按版本回看专题变化",
            },
        )

        report_payload = {
            "keyword": "AI 浏览器",
            "report_title": "AI 浏览器专题研报",
            "executive_summary": "第一版摘要",
            "target_accounts": ["字节跳动"],
            "competitor_profiles": ["Perplexity"],
            "budget_signals": ["浏览器端 Agent 投入加大"],
            "sources": [],
        }
        refreshed = mark_tracking_topic_refreshed(
            db,
            topic["id"],
            last_refreshed_at=datetime(2026, 4, 3, 9, 0, tzinfo=timezone.utc).isoformat(),
            last_report_entry_id=None,
            last_report_title="AI 浏览器专题研报",
            source_count=6,
            evidence_density="medium",
            source_quality="high",
            last_refresh_note="新增 1 个甲方",
            last_refresh_new_targets=["字节跳动"],
            report_payload=report_payload,
            action_cards_payload=[],
        )

        snapshot = save_compare_snapshot(
            db,
            {
                "name": "AI 浏览器专题快照",
                "tracking_topic_id": topic["id"],
                "query": "AI 浏览器",
                "summary": "冻结版本对比结果",
                "rows": [
                    {
                        "id": "row-1",
                        "role": "竞品",
                        "name": "Perplexity",
                        "sourceEntryId": "entry-1",
                    }
                ],
            },
        )

        timeline = list_tracking_topic_timeline(db, topic["id"])
        snapshot_event = next(item for item in timeline if item["event_type"] == "compare_snapshot")
        version_event = next(item for item in timeline if item["event_type"] == "report_version")

        assert refreshed is not None
        assert snapshot["report_version_id"] == refreshed["report_history"][0]["id"]
        assert snapshot["report_version_title"] == "AI 浏览器专题研报"
        assert snapshot["linked_report_diff"]["status"] in {"aligned", "expanded", "trimmed", "mixed"}
        assert snapshot["linked_report_diff"]["headline"]
        assert snapshot["linked_report_diff"]["summary_lines"]
        assert snapshot_event["linked_report_version_id"] == refreshed["report_history"][0]["id"]
        assert snapshot_event["linked_report_version_title"] == "AI 浏览器专题研报"
        assert snapshot_event["row_count"] == 1
        assert snapshot_event["linked_report_diff_summary"]
        assert version_event["report_version_id"] == refreshed["report_history"][0]["id"]
        assert version_event["new_targets"] == ["字节跳动"]
    finally:
        research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED = original_backfill_flag
        db.close()


def test_tracking_topic_timeline_includes_archive_diff_recap_events() -> None:
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
                "name": "AI 浏览器专题",
                "keyword": "AI 浏览器",
                "research_focus": "把差异复盘挂回专题时间线",
            },
        )

        refreshed = mark_tracking_topic_refreshed(
            db,
            topic["id"],
            last_refreshed_at=datetime(2026, 4, 3, 9, 0, tzinfo=timezone.utc).isoformat(),
            last_report_entry_id=None,
            last_report_title="AI 浏览器专题研报",
            source_count=8,
            evidence_density="high",
            source_quality="high",
            last_refresh_note="新增 1 个重点客户",
            last_refresh_new_targets=["字节跳动"],
            report_payload={
                "keyword": "AI 浏览器",
                "report_title": "AI 浏览器专题研报",
                "executive_summary": "关注浏览器入口的预算与竞品演进。",
                "target_accounts": ["字节跳动"],
                "competitor_profiles": ["Perplexity"],
                "budget_signals": ["浏览器端 Agent 投入增强"],
                "sources": [],
            },
            action_cards_payload=[],
        )

        snapshot = save_compare_snapshot(
            db,
            {
                "name": "AI 浏览器专题快照",
                "tracking_topic_id": topic["id"],
                "query": "AI 浏览器",
                "summary": "冻结版本对比结果",
                "rows": [
                    {
                        "id": "row-1",
                        "role": "竞品",
                        "name": "Perplexity",
                        "sourceEntryId": "entry-1",
                    }
                ],
            },
        )

        archive = save_markdown_archive(
            db,
            {
                "archive_kind": "archive_diff_recap",
                "name": "AI 浏览器专题差异复盘",
                "filename": "ai-browser-archive-diff.md",
                "summary": "当前归档新增 2 个 section。",
                "content": "# 历史归档差异复盘报告\n\n- 当前归档新增 2 个 section。\n",
                "compare_snapshot_id": snapshot["id"],
                "metadata_payload": {
                    "current_archive_id": "archive-current",
                    "current_archive_name": "AI 浏览器快照归档",
                    "compare_archive_id": "archive-baseline",
                    "compare_archive_name": "AI 浏览器基线归档",
                    "shared_section_count": 4,
                    "added_section_count": 2,
                    "removed_section_count": 1,
                    "changed_section_count": 3,
                },
            },
        )

        timeline = list_tracking_topic_timeline(db, topic["id"])
        archive_event = next(item for item in timeline if item["event_type"] == "markdown_archive")

        assert refreshed is not None
        assert archive["tracking_topic_id"] == topic["id"]
        assert archive_event["markdown_archive_id"] == archive["id"]
        assert archive_event["markdown_archive_kind"] == "archive_diff_recap"
        assert archive_event["compare_snapshot_id"] == snapshot["id"]
        assert archive_event["compare_snapshot_name"] == "AI 浏览器专题快照"
        assert archive_event["current_markdown_archive_id"] == "archive-current"
        assert archive_event["compare_markdown_archive_id"] == "archive-baseline"
        assert archive_event["linked_report_version_id"] == refreshed["report_history"][0]["id"]
        assert archive_event["linked_report_version_title"] == "AI 浏览器专题研报"
        assert archive_event["preview_names"] == ["AI 浏览器快照归档", "AI 浏览器基线归档"]
        assert archive_event["linked_report_diff_summary"] == [
            "共享 section 4 · 变更 section 3",
            "当前新增 2 · 对照独有 1",
        ]
        assert {item["event_type"] for item in timeline} == {
            "report_version",
            "compare_snapshot",
            "markdown_archive",
        }
    finally:
        research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED = original_backfill_flag
        db.close()
