from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db.base import Base
from app.models.product_strategy_context_entities import (
    ProductStrategyDecisionContextPacket,
    ProductStrategyDecisionContextPacketRevision,
)
from app.services.product_strategy.context_packet_catalog import preview_decision_context_packets
from app.services.product_strategy.context_packet_service import (
    get_persisted_decision_context_packets,
    initialize_decision_context_packets,
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


def test_preview_is_database_free_and_exposes_authorization_boundary() -> None:
    preview = preview_decision_context_packets()

    assert preview["read_only"] is True
    assert preview["initialized"] is False
    assert preview["persistent_snapshot_digest"] is None
    assert preview["approval_evidence"]["kind"] == "user_instruction"
    assert preview["approval_evidence"]["actor_identity_status"] == "unverified"
    assert preview["approval_evidence"]["scope"] == "product_strategy_only"
    assert preview["approval_evidence"]["owner"]["named_individual"] is False
    assert {packet["decision"] for packet in preview["packets"]} == {"build", "integrate", "defer"}
    assert len(preview["packets"]) == 4
    assert len(preview["excluded_cards"]) == 2
    assert {card["decision"] for card in preview["excluded_cards"]} == {"explicitly_not_copy"}
    assert all(packet["status"] == "approved_for_context" for packet in preview["packets"])
    assert all(packet["can_auto_execute"] is False for packet in preview["packets"])
    assert all(packet["can_auto_approve_release"] is False for packet in preview["packets"])
    assert all(packet["requires_human_change_approval"] is True for packet in preview["packets"])
    assert all(packet["source_catalog_version"] == "2.10.0" for packet in preview["packets"])
    assert all(len(packet["packet_catalog_digest"]) == 64 for packet in preview["packets"])


def test_initialize_is_idempotent_and_records_immutable_revision_chain() -> None:
    for db in _session():
        before = get_persisted_decision_context_packets(db)
        assert before["initialized"] is False
        assert before["packets"] == []
        assert before["initialization_audit"] is None

        first = initialize_decision_context_packets(db)
        assert first["initialized"] is True
        assert first["initialization"]["packets"] == {
            "created": 4,
            "existing_seed_managed": 0,
            "preserved_human": 0,
        }
        assert first["initialization"]["revisions"] == {
            "created": 4,
            "existing": 0,
            "preserved_human": 0,
        }
        assert first["initialization"]["approval_audit"] == {"created": 1, "existing": 0}
        assert first["governance"]["release_gate_mutated"] is False
        assert first["governance"]["decision_authorization_is_not_execution_authorization"] is True
        assert first["governance"]["decision_authorization_is_not_release_approval"] is True
        assert len(first["packets"]) == 4
        assert first["initialization_audit"]["source_catalog_version"] == "2.10.0"
        assert len(first["initialization_audit"]["packet_catalog_digest"]) == 64

        for packet in first["packets"]:
            assert packet["revision"] == 1
            assert len(packet["revision_digest"]) == 64
            assert packet["revisions"]
            assert packet["revisions"][0]["previous_revision_digest"] is None
            assert packet["revisions"][0]["is_immutable"] is True
            assert packet["can_auto_execute"] is False
            assert packet["can_auto_approve_release"] is False
            assert packet["production_status"] == "not_authorized"

        repeat = initialize_decision_context_packets(db)
        assert repeat["initialization"]["packets"] == {
            "created": 0,
            "existing_seed_managed": 4,
            "preserved_human": 0,
        }
        assert repeat["initialization"]["revisions"] == {
            "created": 0,
            "existing": 4,
            "preserved_human": 0,
        }
        assert repeat["initialization"]["approval_audit"] == {"created": 0, "existing": 1}
        assert repeat["persistent_snapshot_digest"] == first["persistent_snapshot_digest"]


def test_initializer_preserves_human_managed_packet_and_revision_without_overwrite() -> None:
    for db in _session():
        initialize_decision_context_packets(db)
        packet = db.scalar(
            select(ProductStrategyDecisionContextPacket).where(
                ProductStrategyDecisionContextPacket.roadmap_card_key == "workbuddy:integrate"
            )
        )
        assert packet is not None
        revision = db.scalar(
            select(ProductStrategyDecisionContextPacketRevision).where(
                ProductStrategyDecisionContextPacketRevision.packet_id == packet.id,
                ProductStrategyDecisionContextPacketRevision.revision == 1,
            )
        )
        assert revision is not None
        packet.seed_managed = False
        packet.title = "人工维护的结果回传上下文"
        revision.seed_managed = False
        revision.snapshot_payload = {"human": "preserved"}
        db.commit()

        result = initialize_decision_context_packets(db)
        assert result["initialization"]["packets"]["preserved_human"] == 1
        assert result["initialization"]["revisions"]["preserved_human"] == 1
        db.refresh(packet)
        db.refresh(revision)
        assert packet.title == "人工维护的结果回传上下文"
        assert revision.snapshot_payload == {"human": "preserved"}
