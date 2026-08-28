from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.entities import User
from app.models.research_entities import ResearchJob
from app.schemas.research import ResearchJobCreateRequest
from app.services import research_job_store


def _session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)


def test_research_job_queue_persists_request_and_recovers_running_job(monkeypatch) -> None:
    engine, sessions = _session_factory()
    monkeypatch.setattr(research_job_store, "SessionLocal", sessions)
    monkeypatch.setattr(research_job_store, "_JOBS_BACKFILL_ATTEMPTED", True)
    with sessions() as db:
        db.add(User(id=research_job_store.settings.single_user_id, name="demo"))
        db.commit()

    created = research_job_store.create_research_job(
        ResearchJobCreateRequest(
            keyword="杭州智慧文旅",
            research_focus="核验采购信号",
            supplemental_context="用户补充范围",
            research_mode="deep",
        )
    )
    claimed = research_job_store._claim_next_research_job()

    assert claimed is not None
    job_id, payload = claimed
    assert job_id == created.id
    assert payload.supplemental_context == "用户补充范围"
    with sessions() as db:
        row = db.scalar(select(ResearchJob).where(ResearchJob.id == uuid.UUID(created.id)))
        assert row is not None
        assert row.status == "running"
        assert row.request_payload["supplemental_context"] == "用户补充范围"
        assert row.execution_attempts == 1
        assert row.worker_id

    assert research_job_store.recover_interrupted_research_jobs() == 1
    with sessions() as db:
        row = db.scalar(select(ResearchJob).where(ResearchJob.id == uuid.UUID(created.id)))
        assert row is not None
        assert row.status == "queued"
        assert row.stage_key == "recovering"
        assert row.worker_id == ""
        assert row.lease_expires_at is None
    engine.dispose()


def test_research_job_recovery_rejects_expired_legacy_job(monkeypatch) -> None:
    engine, sessions = _session_factory()
    monkeypatch.setattr(research_job_store, "SessionLocal", sessions)
    monkeypatch.setattr(research_job_store, "_JOBS_BACKFILL_ATTEMPTED", True)
    with sessions() as db:
        db.add(User(id=research_job_store.settings.single_user_id, name="demo"))
        db.add(
            ResearchJob(
                user_id=research_job_store.settings.single_user_id,
                keyword="历史任务",
                status="running",
                request_payload={},
                updated_at=datetime.now(timezone.utc) - timedelta(days=2),
            )
        )
        db.commit()

    assert research_job_store.recover_interrupted_research_jobs() == 0
    with sessions() as db:
        row = db.scalar(select(ResearchJob).where(ResearchJob.keyword == "历史任务"))
        assert row is not None
        assert row.status == "failed"
        assert row.stage_key == "failed"
        assert row.finished_at is not None
        assert "snapshot" in str(row.error)
    engine.dispose()
