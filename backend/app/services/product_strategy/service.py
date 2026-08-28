from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product_strategy_entities import ProductStrategyRoadmapCard, ProductStrategySource
from app.services.product_strategy.catalog import (
    CATALOG_VERSION,
    canonical_digest,
    catalog_digest,
    catalog_governance,
    catalog_roadmap_cards,
    catalog_sources,
    effective_evidence_status,
)


def _as_utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return normalized.isoformat().replace("+00:00", "Z")


def _source_fields(definition: dict[str, Any]) -> dict[str, Any]:
    local_implementation = dict(definition["local_implementation"])
    local_release = dict(definition["local_release"])
    return {
        "product_key": definition["product_key"],
        "vendor": definition["vendor"],
        "product_name": definition["product_name"],
        "source_title": definition["source_title"],
        "source_url": definition["source_url"],
        "source_kind": definition["source_kind"],
        "source_digest": definition["source_digest"],
        "observed_at": _as_utc(definition["observed_at"]),
        "expires_at": _as_utc(definition["expires_at"]),
        "evidence_tier": definition["evidence_tier"],
        "evidence_status": definition["evidence_status"],
        "vendor_claim": definition["vendor_claim"],
        "claimed_capabilities_payload": list(definition["claimed_capabilities"]),
        "local_implementation_status": local_implementation["status"],
        "local_implementation_notes": local_implementation["notes"],
        "local_release_status": local_release["status"],
        "local_release_notes": local_release["notes"],
    }


def _roadmap_card_fields(definition: dict[str, Any]) -> dict[str, Any]:
    return {
        "product_key": definition["product_key"],
        "title": definition["title"],
        "decision": definition["decision"],
        "status": definition["status"],
        "rationale": definition["rationale"],
        "source_catalog_keys_payload": list(definition["source_catalog_keys"]),
        "source_digest": definition["source_digest"],
        "observed_at": _as_utc(definition["observed_at"]),
        "expires_at": _as_utc(definition["expires_at"]),
        "evidence_tier": definition["evidence_tier"],
        "evidence_status": definition["evidence_status"],
        "acceptance_criteria_payload": list(definition["acceptance_criteria"]),
        "module_targets_payload": list(definition["module_targets"]),
        "approval_status": definition["approval_status"],
        "release_impact": definition["release_impact"],
    }


def _assign_if_changed(row: Any, fields: dict[str, Any]) -> bool:
    changed = False
    for name, value in fields.items():
        current = getattr(row, name)
        if isinstance(current, datetime) and isinstance(value, datetime):
            equal = _as_utc(current) == _as_utc(value)
        else:
            equal = current == value
        if not equal:
            setattr(row, name, value)
            changed = True
    return changed


def _seed_sources(db: Session) -> dict[str, int]:
    outcome = {"created": 0, "updated": 0, "preserved_human": 0}
    for definition in catalog_sources():
        row = db.scalar(
            select(ProductStrategySource).where(ProductStrategySource.catalog_key == definition["catalog_key"])
        )
        if row is None:
            db.add(
                ProductStrategySource(
                    catalog_key=definition["catalog_key"],
                    seed_managed=True,
                    **_source_fields(definition),
                )
            )
            outcome["created"] += 1
            continue
        if not row.seed_managed:
            outcome["preserved_human"] += 1
            continue
        if _assign_if_changed(row, _source_fields(definition)):
            outcome["updated"] += 1
    return outcome


def _seed_roadmap_cards(db: Session) -> dict[str, int]:
    outcome = {"created": 0, "updated": 0, "preserved_human": 0}
    for definition in catalog_roadmap_cards():
        row = db.scalar(
            select(ProductStrategyRoadmapCard).where(ProductStrategyRoadmapCard.card_key == definition["card_key"])
        )
        if row is None:
            db.add(
                ProductStrategyRoadmapCard(
                    card_key=definition["card_key"],
                    seed_managed=True,
                    **_roadmap_card_fields(definition),
                )
            )
            outcome["created"] += 1
            continue
        if not row.seed_managed:
            outcome["preserved_human"] += 1
            continue
        if _assign_if_changed(row, _roadmap_card_fields(definition)):
            outcome["updated"] += 1
    return outcome


def seed_competitive_landscape(db: Session) -> dict[str, Any]:
    """Persist the static catalog without ever replacing human-managed rows."""

    source_outcome = _seed_sources(db)
    card_outcome = _seed_roadmap_cards(db)
    db.commit()
    landscape = get_persisted_competitive_landscape(db)
    landscape["seed"] = {
        "sources": source_outcome,
        "roadmap_cards": card_outcome,
    }
    return landscape


def serialize_source(row: ProductStrategySource) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "catalog_key": row.catalog_key,
        "product_key": row.product_key,
        "vendor": row.vendor,
        "product_name": row.product_name,
        "source_title": row.source_title,
        "source_url": row.source_url,
        "source_kind": row.source_kind,
        "source_digest": row.source_digest,
        "observed_at": _iso(row.observed_at),
        "expires_at": _iso(row.expires_at),
        "evidence": {
            "tier": row.evidence_tier,
            "status": effective_evidence_status(row.evidence_status, row.expires_at),
            "recorded_status": row.evidence_status,
            "vendor_claim_is_not_independent_verification": True,
        },
        "vendor_claim": row.vendor_claim,
        "claimed_capabilities": list(row.claimed_capabilities_payload or []),
        "local_implementation": {
            "status": row.local_implementation_status,
            "notes": row.local_implementation_notes,
        },
        "local_release": {
            "status": row.local_release_status,
            "notes": row.local_release_notes,
        },
        "seed_managed": bool(row.seed_managed),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def serialize_roadmap_card(row: ProductStrategyRoadmapCard) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "card_key": row.card_key,
        "product_key": row.product_key,
        "title": row.title,
        "decision": row.decision,
        "status": row.status,
        "rationale": row.rationale,
        "source_catalog_keys": list(row.source_catalog_keys_payload or []),
        "source_digest": row.source_digest,
        "observed_at": _iso(row.observed_at),
        "expires_at": _iso(row.expires_at),
        "evidence": {
            "tier": row.evidence_tier,
            "status": effective_evidence_status(row.evidence_status, row.expires_at),
            "recorded_status": row.evidence_status,
            "vendor_claim_is_not_independent_verification": True,
        },
        "acceptance_criteria": list(row.acceptance_criteria_payload or []),
        "module_targets": list(row.module_targets_payload or []),
        "approval_status": row.approval_status,
        "release_impact": row.release_impact,
        "can_auto_approve_roadmap": False,
        "can_auto_approve_release": False,
        "seed_managed": bool(row.seed_managed),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _product_sort_key(row: ProductStrategySource) -> tuple[int, str]:
    ordered_keys = [definition["product_key"] for definition in catalog_sources()]
    try:
        return ordered_keys.index(row.product_key), row.catalog_key
    except ValueError:
        return len(ordered_keys), row.catalog_key


def _card_sort_key(row: ProductStrategyRoadmapCard) -> tuple[int, str]:
    ordered_keys = [definition["product_key"] for definition in catalog_sources()]
    try:
        return ordered_keys.index(row.product_key), row.card_key
    except ValueError:
        return len(ordered_keys), row.card_key


def get_persisted_competitive_landscape(db: Session) -> dict[str, Any]:
    sources = list(db.scalars(select(ProductStrategySource)).all())
    cards = list(db.scalars(select(ProductStrategyRoadmapCard)).all())
    sources.sort(key=_product_sort_key)
    cards.sort(key=_card_sort_key)
    products = [serialize_source(row) for row in sources]
    roadmap_cards = [serialize_roadmap_card(row) for row in cards]
    observed_at = max((_as_utc(row.observed_at) for row in sources), default=None)
    expires_at = min((_as_utc(row.expires_at) for row in sources), default=None)
    snapshot_digest = canonical_digest(
        {
            "products": [
                {
                    "catalog_key": item["catalog_key"],
                    "source_digest": item["source_digest"],
                    "seed_managed": item["seed_managed"],
                    "vendor_claim": item["vendor_claim"],
                }
                for item in products
            ],
            "roadmap_cards": [
                {
                    "card_key": item["card_key"],
                    "source_digest": item["source_digest"],
                    "decision": item["decision"],
                    "seed_managed": item["seed_managed"],
                }
                for item in roadmap_cards
            ],
        }
    )
    return {
        "catalog_version": CATALOG_VERSION,
        "catalog_digest": catalog_digest(),
        "observed_at": _iso(observed_at),
        "expires_at": _iso(expires_at),
        "read_only": False,
        "initialized": bool(products or roadmap_cards),
        "persistent_snapshot_digest": snapshot_digest if products or roadmap_cards else None,
        "governance": catalog_governance(),
        "products": products,
        "roadmap_cards": roadmap_cards,
    }
