from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db.base import Base
from app.models.product_strategy_artifact_acceptance_entities import (
    ProductStrategyArtifactAcceptanceDraft,
    ProductStrategyArtifactAcceptanceRevision,
)
from app.services.product_strategy.artifact_acceptance_catalog import preview_artifact_acceptance
from app.services.product_strategy.artifact_acceptance_service import (
    DecisionContextPacketsRequiredError,
    get_persisted_artifact_acceptance,
    initialize_artifact_acceptance,
)
from app.services.product_strategy.context_packet_service import initialize_decision_context_packets


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


def test_preview_is_database_free_and_fails_closed_on_missing_evidence() -> None:
    preview = preview_artifact_acceptance()

    assert preview["artifact_acceptance_version"] == "2.10.2"
    assert preview["read_only"] is True
    assert preview["initialized"] is False
    assert preview["persistent_snapshot_digest"] is None
    assert preview["instruction_evidence"]["kind"] == "user_instruction"
    assert preview["instruction_evidence"]["actor_identity_status"] == "unverified"
    assert preview["instruction_evidence"]["scope"] == "artifact_acceptance_definition_only"
    assert preview["governance"]["no_external_office_file_processing"] is True
    assert preview["governance"]["no_visual_render_validation_claim"] is True
    assert preview["governance"]["release_gate_mutated"] is False
    assert len(preview["artifacts"]) == 4

    for artifact in preview["artifacts"]:
        assert artifact["acceptance_status"] == "hold"
        assert artifact["acceptance_label"] == "HOLD"
        assert artifact["blocking_status"] == "blocked"
        assert artifact["office_evidence_status"] == "missing"
        assert artifact["visual_evidence_status"] == "missing"
        assert artifact["can_auto_accept"] is False
        assert artifact["can_auto_execute"] is False
        assert artifact["can_auto_approve_release"] is False
        assert artifact["requires_human_evidence_review"] is True
        assert all(item["result"] == "hold" for item in artifact["acceptance_checklist"])
        assert all(item["blocks_acceptance"] is True for item in artifact["acceptance_checklist"])
        assert artifact["evidence_source_bundle"]["evidence_collection"]["office_file_processing_performed"] is False
        assert artifact["evidence_source_bundle"]["evidence_collection"]["visual_render_processing_performed"] is False
        initial_diff = artifact["initial_field_level_diff"]
        assert initial_diff["from_revision"] is None
        assert initial_diff["to_revision"] == 1
        assert initial_diff["changed_fields"]
        assert initial_diff["auto_acceptance_forbidden"] is True
        assert initial_diff["release_gate_mutated"] is False


def test_initializer_requires_context_packets_then_is_idempotent() -> None:
    for db in _session():
        before = get_persisted_artifact_acceptance(db)
        assert before["initialized"] is False
        assert before["artifacts"] == []
        assert len(before["context_packet_readiness"]["missing_context_packet_keys"]) == 4

        with pytest.raises(DecisionContextPacketsRequiredError) as error:
            initialize_artifact_acceptance(db)
        assert len(error.value.missing_packet_keys) == 4
        assert error.value.unusable_packet_keys == []

        initialize_decision_context_packets(db)
        first = initialize_artifact_acceptance(db)
        assert first["initialized"] is True
        assert first["initialization"] == {
            "drafts": {"created": 4, "existing_seed_managed": 0, "preserved_human": 0},
            "revisions": {"created": 4, "existing": 0, "preserved_human": 0},
            "initialization_audit": {"created": 1, "existing": 0},
        }
        assert first["context_packet_readiness"]["ready_for_explicit_initialization"] is True
        assert first["initialization_audit"]["can_auto_accept"] is False
        assert first["initialization_audit"]["can_auto_execute"] is False
        assert first["initialization_audit"]["can_auto_approve_release"] is False
        assert first["initialization_audit"]["release_gate_mutated"] is False

        for artifact in first["artifacts"]:
            assert artifact["acceptance_status"] == "hold"
            assert artifact["blocking_status"] == "blocked"
            assert artifact["revisions"][0]["previous_revision_digest"] is None
            assert artifact["revisions"][0]["is_immutable"] is True
            assert artifact["revisions"][0]["field_level_diff"]["auto_acceptance_forbidden"] is True
            assert artifact["revisions"][0]["field_level_diff"]["release_gate_mutated"] is False

        repeat = initialize_artifact_acceptance(db)
        assert repeat["initialization"] == {
            "drafts": {"created": 0, "existing_seed_managed": 4, "preserved_human": 0},
            "revisions": {"created": 0, "existing": 4, "preserved_human": 0},
            "initialization_audit": {"created": 0, "existing": 1},
        }
        assert repeat["persistent_snapshot_digest"] == first["persistent_snapshot_digest"]


def test_initializer_preserves_human_managed_draft_and_revision() -> None:
    for db in _session():
        initialize_decision_context_packets(db)
        initialize_artifact_acceptance(db)

        draft = db.scalar(
            select(ProductStrategyArtifactAcceptanceDraft).where(
                ProductStrategyArtifactAcceptanceDraft.roadmap_card_key == "workbuddy:integrate"
            )
        )
        assert draft is not None
        revision = db.scalar(
            select(ProductStrategyArtifactAcceptanceRevision).where(
                ProductStrategyArtifactAcceptanceRevision.draft_id == draft.id,
                ProductStrategyArtifactAcceptanceRevision.revision == 1,
            )
        )
        assert revision is not None

        draft.seed_managed = False
        draft.title = "人工维护的回传边界验收草案"
        revision.seed_managed = False
        revision.snapshot_payload = {"human": "preserved"}
        db.commit()

        result = initialize_artifact_acceptance(db)
        assert result["initialization"]["drafts"]["preserved_human"] == 1
        assert result["initialization"]["revisions"]["preserved_human"] == 1
        db.refresh(draft)
        db.refresh(revision)
        assert draft.title == "人工维护的回传边界验收草案"
        assert revision.snapshot_payload == {"human": "preserved"}
