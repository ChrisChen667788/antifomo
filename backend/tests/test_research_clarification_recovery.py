from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.entities import User
from app.schemas.research import (
    ResearchClarificationSubmitRequest,
    ResearchEvidenceGateOut,
    ResearchJobCreateRequest,
    ResearchReportResponse,
    ResearchReportSectionOut,
    ResearchScopeContractOut,
    ResearchSourceOut,
    ResearchSupplementalDocumentIn,
)
from app.services import research_job_store
from app.services.research.clarification import (
    attach_research_interaction,
    is_provisional_evidence_eligible,
    require_formal_research_delivery,
)
from app.services.research.supplemental_sources import (
    build_user_supplied_documents,
    build_user_supplied_hits,
)


def _near_threshold_report() -> ResearchReportResponse:
    sources = [
        ResearchSourceOut(
            title=f"官方项目来源 {index}",
            url=f"https://source{index}.gov.cn/project",
            domain=f"source{index}.gov.cn",
            snippet="某市文化和旅游局发布智慧文旅项目公告，包含建设范围与预算安排。",
            search_query="智慧文旅 项目 公告",
            source_type="government",
            content_status="extracted",
            source_tier="official" if index <= 4 else "media",
        )
        for index in range(1, 8)
    ]
    return ResearchReportResponse(
        keyword="智慧文旅项目",
        research_focus="某市智慧文旅平台建设与运营方案",
        report_title="智慧文旅项目研究草稿",
        executive_summary="现有七条独立来源已覆盖建设范围、政策依据和实施节奏，可形成方向性判断。",
        consulting_angle="先补齐一条可核验项目来源，再进入正式方案输出。",
        sections=[
            ResearchReportSectionOut(
                title="建设机会与实施路径",
                items=["建设单位可先完成统一数据底座，再分阶段上线游客服务和运营分析。"],
            )
        ],
        source_count=7,
        sources=sources,
        research_scope_contract=ResearchScopeContractOut(
            keyword="智慧文旅项目",
            research_focus="某市智慧文旅平台建设与运营方案",
            research_mode="deep",
            task_type="industry_research",
            regions=["某市"],
            industries=["文旅"],
            status="ready",
        ),
        research_evidence_gate=ResearchEvidenceGateOut(
            enforced=True,
            status="evidence_gap",
            passed=False,
            formal_report_allowed=False,
            solution_delivery_allowed=False,
            minimum_source_count=8,
            minimum_official_source_count=3,
            minimum_unique_domain_count=5,
            minimum_question_coverage_percent=80,
            candidate_source_count=9,
            accepted_source_count=7,
            official_source_count=4,
            unique_domain_count=7,
            question_coverage_percent=100,
            blockers=["有效来源 7 条，低于最低 8 条。"],
        ),
        generated_at=datetime.now(timezone.utc),
    )


def test_near_threshold_evidence_generates_provisional_recovery_packet() -> None:
    report = _near_threshold_report()

    assert is_provisional_evidence_eligible(
        report.research_evidence_gate,
        report.research_scope_contract,
    )

    resolved = attach_research_interaction(report)

    assert resolved.interaction_state == "provisional"
    assert resolved.clarification_packet.can_view_provisional is True
    assert resolved.clarification_packet.formal_delivery_allowed is False
    assert len(resolved.clarification_packet.questions) <= 3
    assert resolved.clarification_packet.evidence_snapshot_digest


def test_provisional_report_cannot_cross_formal_delivery_guard() -> None:
    report = attach_research_interaction(_near_threshold_report())

    try:
        require_formal_research_delivery(report)
    except ValueError as exc:
        assert "受限草稿" in str(exc)
    else:
        raise AssertionError("provisional report unexpectedly crossed the delivery guard")


def test_user_supplied_sources_keep_explicit_provenance() -> None:
    hits = build_user_supplied_hits(
        "请参考 https://example.gov.cn/policy 和 https://ccgp.gov.cn/project/1"
    )
    documents = build_user_supplied_documents(
        [
            ResearchSupplementalDocumentIn(
                file_name="项目会议纪要.txt",
                mime_type="text/plain",
                extracted_text="建设单位确认一期范围包括数据治理、游客服务和运营分析。",
            )
        ]
    )

    assert len(hits) == 2
    assert all(hit.source_origin == "user_supplied" for hit in hits)
    assert len(documents) == 1
    assert documents[0].source_origin == "user_supplied"
    assert documents[0].content_status == "user_supplied"


def test_clarification_continuation_is_idempotent_and_keeps_lineage(monkeypatch) -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    monkeypatch.setattr(research_job_store, "SessionLocal", session_factory)
    monkeypatch.setattr(research_job_store, "_JOBS_BACKFILL_ATTEMPTED", True)
    monkeypatch.setattr(research_job_store, "_run_research_job", lambda *_args, **_kwargs: None)
    with session_factory() as db:
        db.add(User(id=research_job_store.settings.single_user_id, name="demo"))
        db.commit()

    parent = research_job_store.create_research_job(
        ResearchJobCreateRequest(
            keyword="智慧文旅项目",
            research_focus="某市智慧文旅平台建设与运营方案",
            research_mode="deep",
        )
    )
    report = attach_research_interaction(_near_threshold_report())
    parent = research_job_store.update_research_job(
        parent.id,
        status="needs_evidence",
        report_payload=report.model_dump(mode="json"),
        interaction_state=report.interaction_state,
        clarification_payload=report.clarification_packet.model_dump(mode="json"),
        accepted_snapshot_digest=report.clarification_packet.evidence_snapshot_digest,
        finished_at=datetime.now(timezone.utc),
    )
    assert parent is not None
    request = ResearchClarificationSubmitRequest(
        action="submit_answers",
        idempotency_key="recovery-idempotency-0001",
        supplemental_urls=["https://example.gov.cn/new-project"],
    )

    first = research_job_store.submit_research_clarification(parent.id, request)
    replay = research_job_store.submit_research_clarification(parent.id, request)

    assert first.child_job is not None
    assert replay.child_job is not None
    assert replay.idempotent_replay is True
    assert replay.child_job.id == first.child_job.id
    assert first.child_job.parent_job_id == parent.id
    assert first.child_job.root_job_id == parent.root_job_id
    assert first.child_job.recovery_attempt == 1
    assert first.parent_job.resumed_child_job_id == first.child_job.id
    engine.dispose()
