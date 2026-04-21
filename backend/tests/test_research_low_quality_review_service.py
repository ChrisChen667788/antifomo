from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models import KnowledgeEntry, User
from app.schemas.research import ResearchCommercialSummaryOut, ResearchReportResponse, ResearchSourceDiagnosticsOut
from app.services.research_review_service import (
    list_low_quality_research_review_queue,
    resolve_low_quality_research_entry,
    rewrite_low_quality_research_entry,
)


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def _build_low_signal_report() -> ResearchReportResponse:
    return ResearchReportResponse(
        keyword="政务云 AI 行业研报",
        research_focus="预算和周期",
        output_language="zh-CN",
        research_mode="deep",
        report_title="待补证研判｜政务云 AI 行业研报",
        executive_summary="当前证据不足以形成最终商业判断，更适合作为候选名单与待补证路径。",
        consulting_angle="可用于初步行业判断。",
        sections=[],
        target_accounts=["省级数据局"],
        target_departments=[],
        public_contact_channels=[],
        account_team_signals=[],
        budget_signals=[],
        project_distribution=[],
        strategic_directions=[],
        tender_timeline=[],
        leadership_focus=[],
        ecosystem_partners=[],
        competitor_profiles=[],
        benchmark_cases=[],
        flagship_products=[],
        key_people=[],
        five_year_outlook=[],
        client_peer_moves=[],
        winner_peer_moves=[],
        competition_analysis=[],
        source_count=0,
        evidence_density="low",
        source_quality="low",
        query_plan=[],
        sources=[],
        source_diagnostics=ResearchSourceDiagnosticsOut(
            scope_regions=["长三角"],
            scope_industries=["政务云"],
            scope_clients=["省级数据局"],
            retrieval_quality="low",
            evidence_mode="fallback",
            official_source_ratio=0.0,
        ),
        commercial_summary=ResearchCommercialSummaryOut(next_action="先补公开证据"),
        generated_at=datetime.now(timezone.utc),
    )


def _create_research_entry(db: Session) -> KnowledgeEntry:
    settings = get_settings()
    db.add(User(id=settings.single_user_id, name="demo"))
    report = _build_low_signal_report()
    entry = KnowledgeEntry(
        user_id=settings.single_user_id,
        title=report.report_title,
        content="# 待补证研报\n\n旧版内容",
        source_domain="research.report",
        metadata_payload={
            "kind": "research_report",
            "report": report.model_dump(mode="json"),
            "action_cards": [],
            "commercial_intelligence": {},
        },
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def test_low_quality_review_queue_keeps_rewritten_item_until_accepted() -> None:
    db = _new_session()
    try:
        entry = _create_research_entry(db)

        before_queue = list_low_quality_research_review_queue(db, top=10)
        before_item = next(item for item in before_queue["items"] if item["entry_id"] == str(entry.id))
        assert before_item["review_status"] == "pending"
        assert before_item["risk_score"] > 0

        rewritten = rewrite_low_quality_research_entry(db, str(entry.id))
        assert rewritten["review_status"] == "rewritten"
        assert rewritten["diff"]["after_risk_score"] == 0

        after_rewrite_queue = list_low_quality_research_review_queue(db, top=10)
        rewritten_item = next(item for item in after_rewrite_queue["items"] if item["entry_id"] == str(entry.id))
        assert rewritten_item["review_status"] == "rewritten"
        assert rewritten_item["risk_score"] == 0
        assert rewritten_item["latest_rewrite"]["after_risk_score"] == 0

        accepted = resolve_low_quality_research_entry(db, entry_id=str(entry.id), action="accept")
        assert accepted["review_status"] == "accepted"
        assert accepted["item"] is None

        final_queue = list_low_quality_research_review_queue(db, top=10)
        assert [item["entry_id"] for item in final_queue["items"]] == []
    finally:
        db.close()


def test_low_quality_review_revert_restores_previous_snapshot() -> None:
    db = _new_session()
    try:
        entry = _create_research_entry(db)
        original_title = entry.title
        original_content = entry.content

        rewrite_low_quality_research_entry(db, str(entry.id))
        reverted = resolve_low_quality_research_entry(db, entry_id=str(entry.id), action="revert")

        db.refresh(entry)
        assert reverted["review_status"] == "reverted"
        assert reverted["item"]["review_status"] == "reverted"
        assert entry.title == original_title
        assert entry.content == original_content
        assert entry.metadata_payload["low_quality_review"]["status"] == "reverted"
        assert reverted["item"]["risk_score"] > 0
    finally:
        db.close()
