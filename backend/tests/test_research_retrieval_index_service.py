from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models.entities import KnowledgeEntry, User
from app.models.research_entities import (
    ResearchCompareSnapshot,
    ResearchMarkdownArchive,
    ResearchReportVersion,
    ResearchTrackingTopic,
    ResearchWatchlist,
    ResearchWatchlistChangeEvent,
)
from app.services.research_retrieval_index_service import (
    build_research_retrieval_index,
    search_research_retrieval_index,
)


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def _seed_demo_user(db: Session) -> User:
    settings = get_settings()
    user = User(
        id=settings.single_user_id,
        name="Demo User",
        email="demo@anti-fomo.local",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _report_payload() -> dict:
    return {
        "report_title": "上海数据集团预算窗口研判",
        "executive_summary": "上海数据集团将在 7 月启动预算复核，并同步确认政务云需求。",
        "consulting_angle": "围绕预算窗口、组织入口和项目建议书推进路径做可行性判断。",
        "target_accounts": ["上海数据集团"],
        "target_departments": ["采购中心", "数字化办公室"],
        "budget_signals": ["7 月预算复核", "政务云扩容采购意向"],
        "tender_timeline": ["7 月复核预算，8 月进入方案比选"],
        "sources": [
            {
                "title": "上海数据集团公开公告",
                "url": "https://example.gov.cn/shanghai-data-budget",
                "snippet": "公告披露预算复核、采购意向与需求确认时间窗。",
                "source_type": "policy",
                "source_tier": "official",
            }
        ],
        "sections": [
            {
                "title": "项目与商机判断",
                "summary": "预算复核和需求确认窗口已经明确。",
                "items": ["7 月启动预算复核，采购中心同步确认政务云扩容需求。"],
                "evidence_links": [
                    {
                        "title": "上海数据集团公开公告",
                        "url": "https://example.gov.cn/shanghai-data-budget",
                        "source_label": "公开公告",
                        "source_tier": "official",
                        "anchor_text": "7 月预算复核 / 采购意向",
                        "excerpt": "公告明确 7 月启动预算复核，并同步需求确认。",
                    }
                ],
            }
        ],
    }


def _seed_research_assets(db: Session) -> tuple[User, ResearchTrackingTopic]:
    user = _seed_demo_user(db)
    now = datetime.now(timezone.utc)
    topic = ResearchTrackingTopic(
        id=uuid.uuid4(),
        user_id=user.id,
        name="政务云打单专项",
        keyword="上海数据集团政务云预算",
        research_focus="用于解决方案设计和针对性打单的情报收集。",
        region_filter="上海",
        industry_filter="政务云",
    )
    version = ResearchReportVersion(
        id=uuid.uuid4(),
        topic_id=topic.id,
        report_title="上海数据集团预算窗口研判",
        report_payload=_report_payload(),
        source_count=3,
        evidence_density="high",
        source_quality="high",
        new_targets=["上海数据集团"],
        new_budget_signals=["7 月预算复核"],
        created_at=now,
    )
    report_entry = KnowledgeEntry(
        id=uuid.uuid4(),
        user_id=user.id,
        title="上海数据集团预算窗口研判",
        content="围绕预算复核、采购中心组织入口和方案比选窗口形成研报。",
        source_domain="research.report",
        metadata_payload={
            "kind": "research_report",
            "tracking_topic_id": str(topic.id),
            "report": _report_payload(),
            "commercial_intelligence": {
                "accounts": [
                    {
                        "role": "target",
                        "name": "上海数据集团",
                        "summary": "政务云预算复核窗口明确。",
                        "confidence_score": 86,
                        "budget_probability": 78,
                        "maturity_stage": "预算复核",
                        "signals": ["7 月预算复核", "采购中心确认政务云需求"],
                        "why_now": ["官方公告披露采购意向"],
                        "departments": ["采购中心"],
                        "next_best_action": "准备政务云扩容项目建议书。",
                        "benchmark_cases": ["同区域政务云扩容案例"],
                        "evidence_links": [
                            {
                                "title": "上海数据集团公开公告",
                                "url": "https://example.gov.cn/shanghai-data-budget",
                                "source_tier": "official",
                            }
                        ],
                    }
                ],
                "opportunities": [
                    {
                        "title": "政务云扩容售前推进",
                        "account_name": "上海数据集团",
                        "entry_window": "7 月预算复核后进入方案比选",
                        "budget_probability": 78,
                        "score": 88,
                        "next_best_action": "补齐采购中心访谈和技术参数清单。",
                        "why_now": ["采购意向已公开"],
                    }
                ],
            },
        },
        collection_name="研报中心",
        created_at=now,
        updated_at=now,
    )
    snapshot = ResearchCompareSnapshot(
        id=uuid.uuid4(),
        user_id=user.id,
        tracking_topic_id=topic.id,
        report_version_id=version.id,
        name="上海政务云推进快照",
        query="上海数据集团预算复核",
        region_filter="上海",
        industry_filter="政务云",
        role_filter="甲方",
        summary="重点关注预算复核、采购中心入口和官方证据配额。",
        rows_payload=[
            {
                "id": "row-1",
                "role": "甲方",
                "name": "上海数据集团",
                "clue": "预算复核窗口明确。",
                "budgetSignal": "7 月预算复核",
                "projectSignal": "政务云扩容采购意向",
                "targetDepartments": ["采购中心", "数字化办公室"],
                "publicContacts": ["官网公开联系入口"],
                "benchmarkCases": ["同区域政务云扩容案例"],
                "sourceEntryTitle": "上海数据集团预算窗口研判",
                "candidateProfileOfficialHitCount": 2,
                "sourceEntryId": str(report_entry.id),
            }
        ],
        metadata_payload={
            "snapshot_metadata_origin": "live",
            "evidence_appendix_summary": {
                "sourceEntryCount": 1,
                "directEvidenceCount": 3,
                "officialEvidenceCount": 2,
            },
            "section_diagnostics_summary": {
                "weakSectionCount": 0,
                "quotaRiskSectionCount": 0,
                "highlightedSections": ["项目与商机判断"],
            },
            "offline_evaluation_snapshot": {
                "generated_at": now.isoformat(),
                "summary_lines": ["检索命中率 100%，目标账户支撑率 100%。"],
            },
        },
        created_at=now,
        updated_at=now,
    )
    archive = ResearchMarkdownArchive(
        id=uuid.uuid4(),
        user_id=user.id,
        tracking_topic_id=topic.id,
        compare_snapshot_id=snapshot.id,
        report_version_id=version.id,
        archive_kind="compare_markdown",
        name="上海政务云推进归档",
        filename="shanghai-gov-cloud.md",
        query="上海数据集团预算复核",
        region_filter="上海",
        industry_filter="政务云",
        summary="归档预算复核、证据诊断和执行摘要。",
        content="# 上海政务云推进归档\n\n预算复核、采购中心和官方证据配额均已记录。",
        metadata_payload={"changed_section_count": 2},
        created_at=now,
        updated_at=now,
    )
    recap_archive = ResearchMarkdownArchive(
        id=uuid.uuid4(),
        user_id=user.id,
        tracking_topic_id=topic.id,
        report_version_id=version.id,
        archive_kind="topic_version_recap",
        name="上海政务云版本复盘",
        filename="shanghai-gov-cloud-recap.md",
        query="上海数据集团预算复核",
        region_filter="上海",
        industry_filter="政务云",
        summary="复盘追问影响章节和版本变化。",
        content="# 上海政务云版本复盘\n\n追问影响项目与商机判断章节。",
        metadata_payload={
            "followup_impact_summary": {
                "currentTitleResolution": "已按追问纠偏",
                "currentSummaryResolution": "已按追问纠偏",
                "currentImpactedSections": ["项目与商机判断"],
            }
        },
        created_at=now,
        updated_at=now,
    )
    watchlist = ResearchWatchlist(
        id=uuid.uuid4(),
        user_id=user.id,
        tracking_topic_id=topic.id,
        name="上海政务云观察池",
        watch_type="topic",
        query="上海数据集团 政务云 采购意向",
        region_filter="上海",
        industry_filter="政务云",
        alert_level="high",
        schedule="daily",
        status="active",
        last_checked_at=now,
        created_at=now,
        updated_at=now,
    )
    watchlist_event = ResearchWatchlistChangeEvent(
        id=uuid.uuid4(),
        watchlist_id=watchlist.id,
        change_type="new_signal",
        summary="新增采购意向公告，预算复核后进入方案比选。",
        payload={"account_name": "上海数据集团", "next_action": "补齐技术参数清单"},
        severity="high",
        created_at=now,
    )
    db.add_all([topic, version, report_entry, snapshot, archive, recap_archive, watchlist, watchlist_event])
    db.commit()
    return user, topic


def test_build_research_retrieval_index_covers_core_research_assets() -> None:
    db = _new_session()
    try:
        user, _topic = _seed_research_assets(db)

        index = build_research_retrieval_index(db, user_id=user.id)
        document_types = {chunk.document_type for chunk in index.chunks}

        assert {
            "research_report",
            "report_version",
            "compare_snapshot",
            "markdown_archive",
            "archive_recap",
            "watchlist",
            "commercial_hub",
            "account_context",
        } <= document_types
        assert index.source_counts["research_report"] >= 1
        assert index.source_counts["report_version"] >= 1
        assert index.source_counts["watchlist"] >= 1
        assert index.source_counts["account_context"] >= 1
        assert any(chunk.field_key == "section_diagnostics_summary" for chunk in index.chunks)
        assert any(chunk.field_key == "offline_evaluation_snapshot" for chunk in index.chunks)
        assert any(chunk.field_key == "followup_impact_summary" for chunk in index.chunks)
    finally:
        db.close()


def test_search_research_retrieval_index_prioritizes_official_budget_evidence() -> None:
    db = _new_session()
    try:
        user, _topic = _seed_research_assets(db)
        index = build_research_retrieval_index(db, user_id=user.id)

        hits = search_research_retrieval_index(index, "上海数据集团 7 月预算复核 官方公告", limit=5)

        assert hits
        assert hits[0].chunk.source_tier == "official"
        assert "预算复核" in hits[0].chunk.text
        assert {"sparse", "dense"} & set(hits[0].match_modes)
        assert "exact_query_hit" in hits[0].to_payload()
    finally:
        db.close()


def test_search_research_retrieval_index_covers_watchlist_and_account_context() -> None:
    db = _new_session()
    try:
        user, _topic = _seed_research_assets(db)
        index = build_research_retrieval_index(db, user_id=user.id)

        watchlist_hits = search_research_retrieval_index(
            index,
            "采购意向公告 技术参数清单",
            limit=5,
            document_types={"watchlist"},
        )
        account_hits = search_research_retrieval_index(
            index,
            "上海数据集团 项目建议书 采购中心",
            limit=5,
            document_types={"account_context", "commercial_hub"},
        )

        assert watchlist_hits
        assert any(hit.chunk.field_key == "watchlist_change" for hit in watchlist_hits)
        assert account_hits
        assert any(hit.chunk.document_type in {"account_context", "commercial_hub"} for hit in account_hits)
    finally:
        db.close()


def test_search_research_retrieval_index_supports_topic_and_document_type_filters() -> None:
    db = _new_session()
    try:
        user, topic = _seed_research_assets(db)
        other_topic = ResearchTrackingTopic(
            id=uuid.uuid4(),
            user_id=user.id,
            name="北京政务云专项",
            keyword="北京数据局预算复核",
            region_filter="北京",
            industry_filter="政务云",
        )
        other_version = ResearchReportVersion(
            id=uuid.uuid4(),
            topic_id=other_topic.id,
            report_title="北京数据局预算复核",
            report_payload={
                **_report_payload(),
                "report_title": "北京数据局预算复核",
                "target_accounts": ["北京数据局"],
            },
            source_count=2,
            created_at=datetime.now(timezone.utc),
        )
        db.add_all([other_topic, other_version])
        db.commit()
        index = build_research_retrieval_index(db, user_id=user.id)

        hits = search_research_retrieval_index(
            index,
            "预算复核 政务云",
            limit=10,
            document_types={"report_version"},
            topic_id=str(topic.id),
        )

        assert hits
        assert all(hit.chunk.document_type == "report_version" for hit in hits)
        assert all(hit.chunk.topic_id == str(topic.id) for hit in hits)
        assert all("上海" in hit.chunk.title or "上海" in hit.chunk.text for hit in hits)
    finally:
        db.close()


def test_research_retrieval_index_uses_stable_chunk_ids_and_section_parent_links() -> None:
    db = _new_session()
    try:
        user, _topic = _seed_research_assets(db)

        first_index = build_research_retrieval_index(db, user_id=user.id)
        second_index = build_research_retrieval_index(db, user_id=user.id)

        first_by_identity = {
            (chunk.document_type, chunk.document_id, chunk.field_key, chunk.label, chunk.source_url, chunk.text): chunk.chunk_id
            for chunk in first_index.chunks
        }
        second_by_identity = {
            (chunk.document_type, chunk.document_id, chunk.field_key, chunk.label, chunk.source_url, chunk.text): chunk.chunk_id
            for chunk in second_index.chunks
        }
        assert first_by_identity == second_by_identity
        assert all(not chunk_id.startswith("chunk-") for chunk_id in first_by_identity.values())

        report_chunks = [chunk for chunk in first_index.chunks if chunk.document_type == "report_version"]
        report_parent = next(chunk for chunk in report_chunks if chunk.field_key == "report_summary")
        section_parent = next(chunk for chunk in report_chunks if chunk.field_key == "section_summary")
        section_evidence = next(chunk for chunk in report_chunks if chunk.field_key == "section_evidence")
        section_item = next(chunk for chunk in report_chunks if chunk.field_key == "section_item")

        assert section_parent.parent_chunk_id == report_parent.chunk_id
        assert section_evidence.parent_chunk_id == section_parent.chunk_id
        assert section_item.parent_chunk_id == section_parent.chunk_id
    finally:
        db.close()


def test_search_research_retrieval_index_boosts_parent_block_for_child_matches() -> None:
    db = _new_session()
    try:
        user, _topic = _seed_research_assets(db)
        index = build_research_retrieval_index(db, user_id=user.id)

        hits = search_research_retrieval_index(
            index,
            "7 月预算复核 采购中心 确认政务云扩容需求",
            limit=8,
            document_types={"report_version"},
        )

        parent_hits = [hit for hit in hits if "parent_block" in hit.match_modes]
        assert parent_hits
        assert any(hit.chunk.field_key in {"report_summary", "section_summary"} for hit in parent_hits)
        assert any(hit.chunk.chunk_id == child.chunk.parent_chunk_id for hit in parent_hits for child in hits)
    finally:
        db.close()


def test_search_research_retrieval_index_marks_runtime_parent_boost() -> None:
    db = _new_session()
    try:
        user, _topic = _seed_research_assets(db)
        index = build_research_retrieval_index(db, user_id=user.id)

        hits = search_research_retrieval_index(
            index,
            "7 月预算复核 采购中心 确认政务云扩容需求",
            limit=8,
            document_types={"report_version"},
            parent_block_boost=1.35,
        )

        assert any("runtime_parent_boost" in hit.match_modes for hit in hits)
    finally:
        db.close()


def test_search_research_retrieval_index_supports_source_region_industry_field_and_perspective_filters() -> None:
    db = _new_session()
    try:
        user, topic = _seed_research_assets(db)
        topic.perspective = "bidding"
        db.commit()
        index = build_research_retrieval_index(db, user_id=user.id)

        hits = search_research_retrieval_index(
            index,
            "预算复核 官方公告",
            limit=10,
            document_types={"report_version"},
            source_tiers={"official"},
            region="上海",
            industry="政务云",
            field_keys={"section_evidence"},
            perspectives={"bidding"},
        )

        assert hits
        assert all(hit.chunk.document_type == "report_version" for hit in hits)
        assert all(hit.chunk.source_tier == "official" for hit in hits)
        assert all(hit.chunk.field_key == "section_evidence" for hit in hits)
        assert all(hit.chunk.region == "上海" for hit in hits)
        assert all(hit.chunk.industry == "政务云" for hit in hits)
        assert all(hit.chunk.metadata.get("perspective") == "bidding" for hit in hits)
    finally:
        db.close()
