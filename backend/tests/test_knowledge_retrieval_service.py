from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.knowledge import list_knowledge_entries
from app.core.config import get_settings
from app.db.base import Base
from app.models.entities import KnowledgeEntry, User
from app.services.knowledge_retrieval_service import (
    TextRetrievalCandidate,
    retrieve_knowledge_entry_matches,
    retrieve_text_matches,
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


def test_retrieve_knowledge_entry_matches_prioritizes_report_evidence_chunks() -> None:
    db = _new_session()
    try:
        user = _seed_demo_user(db)
        now = datetime.now(timezone.utc)
        report_entry = KnowledgeEntry(
            id=uuid.uuid4(),
            user_id=user.id,
            title="上海数据集团预算窗口研判",
            content="聚焦预算窗口、组织入口和可行性判断。",
            source_domain="research.report",
            metadata_payload={
                "kind": "research_report",
                "report": {
                    "executive_summary": "优先判断上海数据集团预算复核和组织入口。",
                    "followup_context": {
                        "supplemental_evidence": "新增证据显示，上海数据集团将在 7 月启动预算复核。",
                    },
                    "sections": [
                        {
                            "title": "项目与商机判断",
                            "items": ["预算复核和需求确认窗口已经明确。"],
                            "evidence_links": [
                                {
                                    "title": "上海数据集团公开公告",
                                    "url": "https://example.com/shanghai-data",
                                    "source_label": "公开公告",
                                    "source_tier": "official",
                                    "anchor_text": "预算复核 / 时间窗",
                                    "excerpt": "公告提到 7 月将启动预算复核，并同步需求确认。",
                                }
                            ],
                        }
                    ],
                },
            },
            created_at=now,
            updated_at=now,
        )
        generic_entry = KnowledgeEntry(
            id=uuid.uuid4(),
            user_id=user.id,
            title="泛行业观察",
            content="多个行业都在推进数字化建设，但没有明确预算时间。",
            source_domain="36kr.com",
            metadata_payload={},
            created_at=now - timedelta(days=30),
            updated_at=now - timedelta(days=30),
        )
        db.add_all([report_entry, generic_entry])
        db.commit()

        matches = retrieve_knowledge_entry_matches(
            [report_entry, generic_entry],
            "上海数据集团的预算复核时间节点和新增证据是什么？",
            limit=5,
        )

        assert matches
        assert matches[0].entry.id == report_entry.id
        assert matches[0].preview.field_key in {"entry_summary", "report_summary", "supplemental_evidence", "section_summary", "section_evidence", "section_item"}
        assert matches[0].preview.source_tier == "official"
        assert "预算复核" in matches[0].preview.snippet
        assert "sparse" in matches[0].preview.match_modes
    finally:
        db.close()


def test_list_knowledge_entries_preserves_focus_filter_with_hybrid_retrieval() -> None:
    db = _new_session()
    try:
        user = _seed_demo_user(db)
        now = datetime.now(timezone.utc)
        focus_entry = KnowledgeEntry(
            id=uuid.uuid4(),
            user_id=user.id,
            title="重点账户采购信号",
            content="该账户已经释放采购窗口和组织入口信号。",
            source_domain="example.com",
            metadata_payload={},
            is_focus_reference=True,
            created_at=now,
            updated_at=now,
        )
        non_focus_entry = KnowledgeEntry(
            id=uuid.uuid4(),
            user_id=user.id,
            title="普通行业笔记",
            content="采购窗口和组织入口也被提及，但不是 focus 参考。",
            source_domain="example.com",
            metadata_payload={},
            is_focus_reference=False,
            created_at=now,
            updated_at=now,
        )
        db.add_all([focus_entry, non_focus_entry])
        db.commit()

        response = list_knowledge_entries(
            limit=10,
            focus_reference_only=True,
            query="采购窗口 组织入口",
            db=db,
        )

        assert len(response.items) == 1
        assert response.items[0].id == focus_entry.id
        assert response.items[0].retrieval_preview is not None
        assert response.items[0].retrieval_preview.field_key in {"entry_summary", "entry_title", "entry_content"}
    finally:
        db.close()


def test_retrieve_text_matches_prefers_official_procurement_candidate() -> None:
    matches = retrieve_text_matches(
        [
            TextRetrievalCandidate(
                key="official-hit",
                text="南京市数据局 电子政务云平台 采购意向 项目建设",
                source_tier="official",
                priority=12,
            ),
            TextRetrievalCandidate(
                key="media-hit",
                text="政务云行业观察与论坛讨论",
                source_tier="media",
                priority=2,
            ),
        ],
        "南京市数据局政务云预算窗口和采购意向",
        limit=5,
    )

    assert matches
    assert matches[0].key == "official-hit"
    assert matches[0].source_tier == "official"
    assert "sparse" in matches[0].match_modes
    assert matches[0].lexical_overlap >= 2


def test_retrieve_knowledge_entry_matches_can_surface_section_summary_parent_chunk() -> None:
    db = _new_session()
    try:
        user = _seed_demo_user(db)
        now = datetime.now(timezone.utc)
        report_entry = KnowledgeEntry(
            id=uuid.uuid4(),
            user_id=user.id,
            title="华东区域推进纪要",
            content="阶段性推进记录。",
            source_domain="research.report",
            metadata_payload={
                "kind": "research_report",
                "report": {
                    "executive_summary": "先围绕重点账户判断组织入口。",
                    "sections": [
                        {
                            "title": "采购中心与预算复核",
                            "items": ["7 月同步确认需求。"],
                            "evidence_links": [
                                {
                                    "title": "公开公告",
                                    "url": "https://example.com/budget-review",
                                    "source_label": "公开公告",
                                    "source_tier": "official",
                                    "anchor_text": "7 月时间窗 / 需求确认",
                                    "excerpt": "公告显示 7 月组织需求确认。",
                                }
                            ],
                        }
                    ],
                },
            },
            created_at=now,
            updated_at=now,
        )
        db.add(report_entry)
        db.commit()

        matches = retrieve_knowledge_entry_matches(
            [report_entry],
            "采购中心预算复核",
            limit=3,
        )

        assert matches
        assert matches[0].entry.id == report_entry.id
        assert matches[0].preview.field_key in {"section_evidence", "section_item"}
        assert "7 月" in matches[0].preview.snippet
        assert "routed" in matches[0].preview.match_modes
    finally:
        db.close()
