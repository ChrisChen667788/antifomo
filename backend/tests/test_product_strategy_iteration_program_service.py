from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db.base import Base
from app.models.product_strategy_iteration_entities import ProductStrategyIteration, ProductStrategyIterationRevision
from app.services.product_strategy.iteration_program_catalog import preview_iteration_program
from app.services.product_strategy.iteration_program_service import (
    get_persisted_iteration_program,
    initialize_iteration_program,
)


def _session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_preview_materializes_fifteen_gated_iterations_and_fresh_agent_sources() -> None:
    preview = preview_iteration_program()

    assert preview["iteration_program_version"] == "2.10.3-2.11.7"
    assert preview["read_only"] is True
    assert preview["initialized"] is False
    assert len(preview["iterations"]) == 15
    assert [iteration["sequence"] for iteration in preview["iterations"]] == list(range(1, 16))
    assert [iteration["version"] for iteration in preview["iterations"]][-1] == "2.11.7"
    assert len(preview["agent_sources"]) >= 7
    assert preview["governance"]["office_and_visual_acceptance_remain_gated"] is True
    assert preview["governance"]["release_gate_mutated"] is False

    for source in preview["agent_sources"]:
        assert source["evidence"]["recorded_status"] == "vendor_claim_unverified"
        assert source["evidence"]["vendor_claim_is_not_independent_verification"] is True
    for iteration in preview["iterations"]:
        assert iteration["implementation_status"] == "planning_control_plane_implemented"
        assert iteration["feature_implementation_status"] == "gated_or_pending_evidence"
        assert iteration["acceptance_status"] == "hold"
        assert iteration["can_auto_accept"] is False
        assert iteration["can_auto_execute"] is False
        assert iteration["can_auto_approve_release"] is False
        assert iteration["initial_field_level_diff"]["auto_acceptance_forbidden"] is True


def test_initializer_is_idempotent_and_preserves_human_owned_iteration() -> None:
    for db in _session():
        before = get_persisted_iteration_program(db)
        assert before["initialized"] is False
        assert before["iterations"] == []

        first = initialize_iteration_program(db)
        assert first["initialized"] is True
        assert first["initialization"] == {
            "iterations": {"created": 15, "existing_seed_managed": 0, "preserved_human": 0},
            "revisions": {"created": 15, "existing": 0, "preserved_human": 0},
            "initialization_audit": {"created": 1, "existing": 0},
        }
        assert first["initialization_audit"]["release_gate_mutated"] is False
        assert all(iteration["acceptance_status"] == "hold" for iteration in first["iterations"])
        assert all(iteration["revisions"][0]["previous_revision_digest"] is None for iteration in first["iterations"])

        row = db.scalar(
            select(ProductStrategyIteration).where(
                ProductStrategyIteration.iteration_key == "2.10.3:approved-execution-proposals"
            )
        )
        assert row is not None
        revision = db.scalar(
            select(ProductStrategyIterationRevision).where(
                ProductStrategyIterationRevision.iteration_id == row.id,
                ProductStrategyIterationRevision.revision == 1,
            )
        )
        assert revision is not None
        row.seed_managed = False
        row.title = "人工维护的执行提案版本"
        revision.seed_managed = False
        revision.snapshot_payload = {"human": "preserved"}
        db.commit()

        repeat = initialize_iteration_program(db)
        assert repeat["initialization"]["iterations"] == {
            "created": 0,
            "existing_seed_managed": 14,
            "preserved_human": 1,
        }
        assert repeat["initialization"]["revisions"] == {"created": 0, "existing": 14, "preserved_human": 1}
        assert repeat["initialization"]["initialization_audit"] == {"created": 0, "existing": 1}
        db.refresh(row)
        db.refresh(revision)
        assert row.title == "人工维护的执行提案版本"
        assert revision.snapshot_payload == {"human": "preserved"}
