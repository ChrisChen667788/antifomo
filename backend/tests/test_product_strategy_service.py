from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db.base import Base
from app.models.product_strategy_entities import ProductStrategyRoadmapCard, ProductStrategySource
from app.services.product_strategy.catalog import effective_evidence_status, preview_competitive_landscape
from app.services.product_strategy.service import get_persisted_competitive_landscape, seed_competitive_landscape


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


def test_preview_is_static_vendor_claim_only_and_does_not_require_persistence() -> None:
    preview = preview_competitive_landscape()

    assert preview["read_only"] is True
    assert preview["initialized"] is False
    assert preview["persistent_snapshot_digest"] is None
    assert preview["governance"]["vendor_claim_is_not_independent_verification"] is True
    assert preview["governance"]["can_auto_approve_roadmap"] is False
    assert preview["governance"]["can_auto_approve_release"] is False
    assert [item["product_key"] for item in preview["products"]] == [
        "workbuddy",
        "trae",
        "qwen_work",
        "langhub",
        "baidu_dumate",
        "tencent_qclaw",
    ]
    assert all(item["source_url"].startswith("https://") for item in preview["products"])
    assert all(len(item["source_digest"]) == 64 for item in preview["products"])
    assert all(item["evidence"]["tier"] == "vendor_claim" for item in preview["products"])
    assert all(item["evidence"]["vendor_claim_is_not_independent_verification"] for item in preview["products"])
    assert {item["decision"] for item in preview["roadmap_cards"]} == {
        "build",
        "integrate",
        "defer",
        "explicitly_not_copy",
    }
    assert all(item["can_auto_approve_roadmap"] is False for item in preview["roadmap_cards"])
    assert all(item["can_auto_approve_release"] is False for item in preview["roadmap_cards"])


def test_expired_catalog_evidence_is_exposed_as_stale_without_changing_its_recorded_tier() -> None:
    assert (
        effective_evidence_status(
            "vendor_claim_unverified",
            "2026-11-26T00:00:00Z",
            now=datetime(2026, 11, 26, 0, 0, 1, tzinfo=UTC),
        )
        == "stale"
    )


def test_seed_is_idempotent_and_preserves_human_managed_rows() -> None:
    for db in _session():
        before = get_persisted_competitive_landscape(db)
        assert before["initialized"] is False
        assert before["products"] == []

        first = seed_competitive_landscape(db)
        assert first["initialized"] is True
        assert first["seed"]["sources"] == {"created": 6, "updated": 0, "preserved_human": 0}
        assert first["seed"]["roadmap_cards"] == {"created": 6, "updated": 0, "preserved_human": 0}
        assert len(first["products"]) == 6
        assert len(first["roadmap_cards"]) == 6
        assert first["persistent_snapshot_digest"]

        second = seed_competitive_landscape(db)
        assert second["seed"]["sources"] == {"created": 0, "updated": 0, "preserved_human": 0}
        assert second["seed"]["roadmap_cards"] == {"created": 0, "updated": 0, "preserved_human": 0}

        source = db.scalar(
            select(ProductStrategySource).where(ProductStrategySource.catalog_key == "workbuddy:official-product")
        )
        card = db.scalar(
            select(ProductStrategyRoadmapCard).where(ProductStrategyRoadmapCard.card_key == "workbuddy:integrate")
        )
        assert source is not None
        assert card is not None
        source.seed_managed = False
        source.vendor_claim = "人工复核后的 WorkBuddy 观察。"
        card.seed_managed = False
        card.title = "人工维护的 WorkBuddy 路线卡"
        db.commit()

        preserved = seed_competitive_landscape(db)
        assert preserved["seed"]["sources"]["preserved_human"] == 1
        assert preserved["seed"]["roadmap_cards"]["preserved_human"] == 1
        db.refresh(source)
        db.refresh(card)
        assert source.vendor_claim == "人工复核后的 WorkBuddy 观察。"
        assert card.title == "人工维护的 WorkBuddy 路线卡"
