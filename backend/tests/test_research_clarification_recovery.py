from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.entities import User
from app.models.research_entities import ResearchJob
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


def _zero_evidence_report() -> ResearchReportResponse:
    report = _near_threshold_report()
    return report.model_copy(
        update={
            "source_count": 0,
            "sources": [],
            "research_evidence_gate": report.research_evidence_gate.model_copy(
                update={
                    "candidate_source_count": 12,
                    "accepted_source_count": 0,
                    "official_source_count": 0,
                    "unique_domain_count": 0,
                    "question_coverage_percent": 0,
                    "blockers": ["有效来源 0 条，低于最低 8 条。"],
                }
            ),
        }
    )


def _isolated_job_store(monkeypatch):
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
    return engine, session_factory


def _create_zero_evidence_job(*, recovery_attempt: int = 0):
    job = research_job_store.create_research_job(
        ResearchJobCreateRequest(
            keyword="指定建设单位项目",
            research_focus="核验公开采购与建设证据",
            research_mode="deep",
        ),
        recovery_attempt=recovery_attempt,
    )
    report = attach_research_interaction(_zero_evidence_report())
    resolved = research_job_store.update_research_job(
        job.id,
        status="needs_evidence",
        progress_percent=100,
        stage_key="needs_evidence",
        report_payload=report.model_dump(mode="json"),
        interaction_state=report.interaction_state,
        clarification_payload=report.clarification_packet.model_dump(mode="json"),
        accepted_snapshot_digest=report.clarification_packet.evidence_snapshot_digest,
        finished_at=datetime.now(timezone.utc),
    )
    assert resolved is not None
    return resolved


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


def test_repeated_zero_evidence_text_does_not_create_another_child(monkeypatch) -> None:
    engine, session_factory = _isolated_job_store(monkeypatch)
    parent = _create_zero_evidence_job(recovery_attempt=1)

    assert parent.requires_evidence_input is True
    assert parent.recovery_exhausted is False
    assert parent.clarification_packet.reason_code == "evidence_input_required"
    assert parent.clarification_packet.recovery_blocked_reason == "evidence_input_required"

    response = research_job_store.submit_research_clarification(
        parent.id,
        ResearchClarificationSubmitRequest(
            action="submit_answers",
            idempotency_key="zero-evidence-text-only-0001",
            supplemental_text="建设单位和项目范围已补充，请继续调研。",
        ),
    )

    assert response.outcome == "recovery_blocked"
    assert response.child_job is None
    assert response.requires_evidence_input is True
    assert response.recovery_exhausted is False
    assert "没有创建新任务" in response.message
    with session_factory() as db:
        assert db.scalar(select(func.count(ResearchJob.id))) == 1
    engine.dispose()


def test_zero_evidence_recovery_accepts_url_before_limit(monkeypatch) -> None:
    engine, session_factory = _isolated_job_store(monkeypatch)
    parent = _create_zero_evidence_job(recovery_attempt=1)

    response = research_job_store.submit_research_clarification(
        parent.id,
        ResearchClarificationSubmitRequest(
            action="submit_answers",
            idempotency_key="zero-evidence-with-url-0001",
            supplemental_text="补充建设单位范围。",
            supplemental_urls=["https://example.gov.cn/project/notice"],
        ),
    )

    assert response.outcome == "recovery_started"
    assert response.child_job is not None
    assert response.child_job.recovery_attempt == 2
    assert response.child_job.recovery_limit == 3
    with session_factory() as db:
        assert db.scalar(select(func.count(ResearchJob.id))) == 2
    engine.dispose()


def test_recovery_limit_returns_terminal_actionable_state_without_child(monkeypatch) -> None:
    engine, session_factory = _isolated_job_store(monkeypatch)
    parent = _create_zero_evidence_job(
        recovery_attempt=research_job_store.MAX_CLARIFICATION_RECOVERY_ATTEMPTS
    )

    assert parent.recovery_exhausted is True
    assert parent.requires_evidence_input is False
    assert parent.interaction_state == "blocked"
    assert parent.clarification_packet.reason_code == "recovery_limit_reached"
    assert parent.clarification_packet.recovery_options == []

    response = research_job_store.submit_research_clarification(
        parent.id,
        ResearchClarificationSubmitRequest(
            action="submit_answers",
            idempotency_key="recovery-limit-with-url-0001",
            supplemental_urls=["https://example.gov.cn/project/new-evidence"],
        ),
    )

    assert response.outcome == "recovery_blocked"
    assert response.child_job is None
    assert response.recovery_exhausted is True
    assert response.parent_job.progress_percent == 100
    assert "没有创建新任务" in response.message
    with session_factory() as db:
        assert db.scalar(select(func.count(ResearchJob.id))) == 1
    engine.dispose()


def test_system_degraded_job_remains_retryable_at_evidence_recovery_limit(monkeypatch) -> None:
    engine, session_factory = _isolated_job_store(monkeypatch)
    job = research_job_store.create_research_job(
        ResearchJobCreateRequest(
            keyword="系统失败任务",
            research_focus="验证系统重试不受证据补证上限影响",
            research_mode="deep",
        ),
        recovery_attempt=research_job_store.MAX_CLARIFICATION_RECOVERY_ATTEMPTS,
    )
    parent = research_job_store.update_research_job(
        job.id,
        status="failed",
        progress_percent=80,
        error="temporary model gateway failure",
        finished_at=datetime.now(timezone.utc),
    )

    assert parent is not None
    assert parent.recovery_exhausted is False
    assert parent.clarification_packet.system_retryable is True

    response = research_job_store.submit_research_clarification(
        parent.id,
        ResearchClarificationSubmitRequest(
            action="retry_system",
            idempotency_key="system-retry-at-evidence-limit-0001",
        ),
    )

    assert response.outcome == "recovery_started"
    assert response.child_job is not None
    assert response.child_job.recovery_attempt == 4
    with session_factory() as db:
        assert db.scalar(select(func.count(ResearchJob.id))) == 2
    engine.dispose()
