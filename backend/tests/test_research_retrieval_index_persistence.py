from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models.entities import KnowledgeEntry, User
from app.models.research_entities import ResearchRetrievalIndexBuildCheckpoint, ResearchRetrievalIndexChunkRecord
from app.services.research_retrieval_index_service import (
    load_persistent_research_retrieval_index,
    rebuild_persistent_research_retrieval_index,
    search_persistent_research_retrieval_index,
)


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def _seed_user_and_report(db: Session) -> User:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    user = User(
        id=settings.single_user_id,
        name="Demo User",
        email="demo@anti-fomo.local",
    )
    report_payload = {
        "report_title": "上海数据集团预算窗口研判",
        "executive_summary": "上海数据集团将在 7 月启动预算复核，并确认政务云扩容需求。",
        "consulting_angle": "围绕预算窗口、组织入口和项目建议书推进路径做可行性判断。",
        "target_accounts": ["上海数据集团"],
        "target_departments": ["采购中心"],
        "budget_signals": ["7 月预算复核"],
        "tender_timeline": ["8 月方案比选"],
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
                "items": ["7 月预算复核，采购中心确认政务云扩容采购意向。"],
                "evidence_links": [
                    {
                        "title": "上海数据集团公开公告",
                        "url": "https://example.gov.cn/shanghai-data-budget",
                        "source_tier": "official",
                        "excerpt": "7 月预算复核。",
                    }
                ],
            }
        ],
    }
    entry = KnowledgeEntry(
        id=uuid.uuid4(),
        user_id=user.id,
        title="上海数据集团预算窗口研判",
        content="上海数据集团 7 月预算复核，采购中心确认政务云扩容采购意向。",
        source_domain="research.report",
        metadata_payload={"kind": "research_report", "report": report_payload},
        collection_name="研报中心",
        created_at=now,
        updated_at=now,
    )
    db.add_all([user, entry])
    db.commit()
    db.refresh(user)
    return user


def _chunk_count(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(ResearchRetrievalIndexChunkRecord)) or 0)


def test_persistent_retrieval_index_rebuild_can_resume_from_checkpoint() -> None:
    db = _new_session()
    try:
        user = _seed_user_and_report(db)

        partial = rebuild_persistent_research_retrieval_index(
            db,
            user_id=user.id,
            batch_size=1,
            max_chunks=1,
            reset=True,
        )
        checkpoint = db.scalars(select(ResearchRetrievalIndexBuildCheckpoint)).one()

        assert partial.completed is False
        assert partial.next_offset == 1
        assert checkpoint.status == "running"
        assert _chunk_count(db) == 1

        resumed = rebuild_persistent_research_retrieval_index(
            db,
            user_id=user.id,
            batch_size=2,
            resume=True,
        )

        assert resumed.completed is True
        assert resumed.start_offset == 1
        assert _chunk_count(db) == resumed.total_chunks
        assert db.scalars(select(ResearchRetrievalIndexBuildCheckpoint)).one().status == "completed"
    finally:
        db.close()


def test_persistent_retrieval_index_loads_and_searches_without_duplicate_incremental_rows() -> None:
    db = _new_session()
    try:
        user = _seed_user_and_report(db)

        first = rebuild_persistent_research_retrieval_index(db, user_id=user.id, reset=True)
        first_count = _chunk_count(db)
        second = rebuild_persistent_research_retrieval_index(db, user_id=user.id, reset=False, resume=False)
        second_count = _chunk_count(db)
        index = load_persistent_research_retrieval_index(db, user_id=user.id)
        hits = search_persistent_research_retrieval_index(db, "上海数据集团 预算复核 采购中心", user_id=user.id)

        assert first.completed is True
        assert second.completed is True
        assert first_count == second_count
        assert len(index.chunks) == first_count
        assert hits
        assert hits[0].chunk.source_tier == "official"
        assert "预算复核" in hits[0].chunk.text
    finally:
        db.close()
