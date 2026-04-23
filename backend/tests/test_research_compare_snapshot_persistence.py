from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models import User
from app.models.entities import KnowledgeEntry
from app.models.research_entities import ResearchCompareSnapshot
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


def test_compare_snapshot_round_trip_persists_metadata_payload() -> None:
    db = _new_session()
    settings = get_settings()
    original_backfill_flag = research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED
    try:
        research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED = True
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

        metadata_payload = {
            "evidence_appendix_summary": {
                "mode": "compare",
                "sourceEntryCount": 2,
                "directEvidenceCount": 5,
                "officialEvidenceCount": 3,
                "mediaEvidenceCount": 1,
                "aggregateEvidenceCount": 1,
                "uncoveredEntities": ["示例甲方"],
                "officialCoverageLeaders": ["示例甲方 ×2"],
            },
            "section_diagnostics_summary": {
                "mode": "compare",
                "sourceReportCount": 2,
                "weakSectionCount": 3,
                "quotaRiskSectionCount": 2,
                "contradictionSectionCount": 1,
                "highlightedSections": ["采购路径", "预算口径"],
            },
            "offline_evaluation_snapshot": {
                "generated_at": "2026-04-23T09:00:00Z",
                "total_reports": 12,
                "evaluated_reports": 10,
                "invalid_payloads": 1,
                "metrics": [
                    {
                        "key": "retrieval_hit_rate",
                        "label": "检索命中率",
                        "percent": 78,
                        "status": "good",
                        "benchmark": 0.72,
                        "numerator": 7,
                        "denominator": 9,
                    }
                ],
                "summary_lines": ["当前检索命中率 78%，目标账户支撑率 74%。"],
            },
        }

        saved = save_compare_snapshot(
            db,
            {
                "name": "带元数据的快照",
                "rows": [{"id": "row-1", "role": "甲方", "name": "示例公司"}],
                "metadata_payload": metadata_payload,
            },
        )

        loaded = get_compare_snapshot(db, saved["id"])

        assert saved["metadata_payload"] == metadata_payload
        assert loaded is not None
        assert loaded["metadata_payload"] == metadata_payload
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


def test_legacy_compare_snapshot_backfills_missing_metadata_on_read() -> None:
    db = _new_session()
    settings = get_settings()
    original_backfill_flag = research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED
    try:
        research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED = True
        db.add(User(id=settings.single_user_id, name="demo"))
        db.add(
            KnowledgeEntry(
                user_id=settings.single_user_id,
                source_domain="research.report",
                title="AI 浏览器研报",
                content="示例内容",
                metadata_payload={
                    "report": {
                        "report_title": "AI 浏览器研报",
                        "keyword": "AI 浏览器",
                        "executive_summary": "聚焦浏览器入口机会。",
                        "consulting_angle": "入口布局",
                        "sections": [
                            {
                                "id": "section-1",
                                "title": "预算口径",
                                "summary": "预算仍需核验",
                                "status": "needs_evidence",
                                "evidence_quota": 2,
                                "meets_evidence_quota": False,
                                "quota_gap": 1,
                            }
                        ],
                        "target_accounts": ["示例甲方"],
                        "top_target_accounts": [{"name": "示例甲方", "score": 80, "reasoning": "目标客户"}],
                        "pending_target_candidates": [],
                        "target_departments": [],
                        "public_contact_channels": [],
                        "account_team_signals": [],
                        "budget_signals": ["预算扩大"],
                        "project_distribution": [],
                        "strategic_directions": [],
                        "tender_timeline": [],
                        "leadership_focus": [],
                        "ecosystem_partners": [],
                        "top_ecosystem_partners": [],
                        "pending_partner_candidates": [],
                        "competitor_profiles": [],
                        "top_competitors": [],
                        "pending_competitor_candidates": [],
                        "benchmark_cases": [],
                        "flagship_products": [],
                        "key_people": [],
                        "five_year_outlook": [],
                        "client_peer_moves": [],
                        "winner_peer_moves": [],
                        "competition_analysis": [],
                        "source_count": 3,
                        "evidence_density": "medium",
                        "source_quality": "medium",
                        "query_plan": [],
                        "sources": [
                            {
                                "title": "政府采购公告",
                                "url": "https://example.gov.cn/tender",
                                "domain": "example.gov.cn",
                                "snippet": "官方招采信息",
                                "search_query": "AI 浏览器 招标",
                                "source_type": "procurement",
                                "content_status": "ok",
                                "source_label": "采购网",
                                "source_tier": "official",
                            }
                        ],
                        "source_diagnostics": {
                            "strict_topic_source_count": 2,
                            "strict_match_ratio": 0.51,
                            "retrieval_quality": "high",
                            "official_source_ratio": 0.5,
                            "supported_target_accounts": ["示例甲方"],
                            "unsupported_target_accounts": [],
                        },
                        "report_readiness": {
                            "status": "needs_evidence",
                            "score": 62,
                            "actionable": True,
                            "evidence_gate_passed": False,
                            "reasons": ["预算章节仍需补证"],
                        },
                        "generated_at": "2026-04-23T09:00:00Z",
                    }
                },
            )
        )
        db.commit()

        legacy_snapshot = ResearchCompareSnapshot(
            user_id=settings.single_user_id,
            name="历史快照",
            query="AI 浏览器",
            rows_payload=[
                {
                    "id": "row-1",
                    "role": "甲方",
                    "name": "示例甲方",
                    "sourceEntryId": "entry-1",
                    "sourceEntryTitle": "AI 浏览器研报",
                    "candidateProfileHitCount": 3,
                    "candidateProfileOfficialHitCount": 2,
                    "evidenceLinks": [
                        {
                            "title": "政府采购公告",
                            "url": "https://example.gov.cn/tender",
                            "sourceTier": "official",
                            "sourceLabel": "采购网",
                        }
                    ],
                    "weakSections": [
                        {
                            "title": "预算口径",
                            "status": "needs_evidence",
                            "insufficiencySummary": "预算仍需核验",
                            "evidenceQuota": 2,
                            "meetsEvidenceQuota": False,
                            "quotaGap": 1,
                            "contradictionDetected": False,
                        }
                    ],
                },
                {
                    "id": "row-2",
                    "role": "竞品",
                    "name": "竞品公司",
                    "sourceEntryId": "entry-1",
                    "sourceEntryTitle": "AI 浏览器研报",
                    "candidateProfileHitCount": 1,
                    "candidateProfileOfficialHitCount": 0,
                    "evidenceLinks": [],
                    "weakSections": [],
                },
            ],
            metadata_payload={},
        )
        db.add(legacy_snapshot)
        db.commit()

        listed = list_compare_snapshots(db)
        loaded = get_compare_snapshot(db, str(legacy_snapshot.id))
        db.refresh(legacy_snapshot)

        assert listed[0]["metadata_payload"]["evidence_appendix_summary"]["sourceEntryCount"] == 1
        assert listed[0]["metadata_payload"]["evidence_appendix_summary"]["officialEvidenceCount"] == 1
        assert listed[0]["metadata_payload"]["section_diagnostics_summary"]["weakSectionCount"] == 1
        assert listed[0]["metadata_payload"]["offline_evaluation_snapshot"]["evaluated_reports"] == 1
        assert listed[0]["metadata_payload"]["snapshot_metadata_origin"] == "legacy_backfill"
        assert listed[0]["metadata_payload"]["snapshot_metadata_backfilled_fields"] == [
            "evidence_appendix_summary",
            "section_diagnostics_summary",
            "offline_evaluation_snapshot",
        ]
        assert loaded is not None
        assert loaded["metadata_payload"]["evidence_appendix_summary"]["uncoveredEntities"] == ["竞品公司"]
        assert loaded["metadata_payload"]["section_diagnostics_summary"]["highlightedSections"] == ["预算口径（待补 1）"]
        assert legacy_snapshot.metadata_payload["offline_evaluation_snapshot"]["summary_lines"]
    finally:
        research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED = original_backfill_flag
        db.close()


def test_compare_snapshot_backfill_does_not_override_existing_metadata_payload() -> None:
    db = _new_session()
    settings = get_settings()
    original_backfill_flag = research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED
    try:
        research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED = True
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

        metadata_payload = {
            "evidence_appendix_summary": {"sourceEntryCount": 9},
            "section_diagnostics_summary": {"weakSectionCount": 7},
            "offline_evaluation_snapshot": {"evaluated_reports": 4},
        }
        saved = save_compare_snapshot(
            db,
            {
                "name": "已有 metadata 的快照",
                "rows": [{"id": "row-1", "role": "甲方", "name": "示例公司"}],
                "metadata_payload": metadata_payload,
            },
        )

        listed = list_compare_snapshots(db)
        loaded = get_compare_snapshot(db, saved["id"])

        assert listed[0]["metadata_payload"] == metadata_payload
        assert loaded is not None
        assert loaded["metadata_payload"] == metadata_payload
    finally:
        research_workspace_store._WORKSPACE_BACKFILL_ATTEMPTED = original_backfill_flag
        db.close()
