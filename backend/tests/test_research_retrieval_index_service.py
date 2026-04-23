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
    db.add_all([topic, version, report_entry, snapshot, archive])
    db.commit()
    return user, topic


def test_build_research_retrieval_index_covers_core_research_assets() -> None:
    db = _new_session()
    try:
        user, _topic = _seed_research_assets(db)

        index = build_research_retrieval_index(db, user_id=user.id)
        document_types = {chunk.document_type for chunk in index.chunks}

        assert {"research_report", "report_version", "compare_snapshot", "markdown_archive"} <= document_types
        assert index.source_counts["research_report"] >= 1
        assert index.source_counts["report_version"] >= 1
        assert any(chunk.field_key == "section_diagnostics_summary" for chunk in index.chunks)
        assert any(chunk.field_key == "offline_evaluation_snapshot" for chunk in index.chunks)
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
