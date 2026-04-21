from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.research_entities import (
    ResearchCanonicalEntity,
    ResearchEntityAlias,
    ResearchEntityRelation,
)


settings = get_settings()


def _normalize_name(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _iter_graph_entities(report_payload: dict[str, Any]) -> list[dict[str, Any]]:
    graph = report_payload.get("entity_graph") if isinstance(report_payload, dict) else {}
    entities: list[dict[str, Any]] = []
    for key in ("entities", "target_entities", "competitor_entities", "partner_entities"):
        values = graph.get(key) if isinstance(graph, dict) else []
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict):
                continue
            canonical_name = _normalize_name(item.get("canonical_name"))
            if not canonical_name:
                continue
            entities.append(
                {
                    "canonical_name": canonical_name,
                    "entity_type": _normalize_name(item.get("entity_type")) or "generic",
                    "aliases": [
                        alias for alias in (_normalize_name(alias) for alias in item.get("aliases") or []) if alias
                    ],
                    "source_count": int(item.get("source_count") or 0),
                    "source_tier_counts": item.get("source_tier_counts") if isinstance(item.get("source_tier_counts"), dict) else {},
                    "evidence_links": [
                        link
                        for link in (item.get("evidence_links") or [])
                        if isinstance(link, dict) and _normalize_name(link.get("url"))
                    ],
                }
            )
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for item in entities:
        key = (item["canonical_name"], item["entity_type"])
        current = deduped.get(key)
        if current is None:
            deduped[key] = item
            continue
        current_aliases = set(current["aliases"])
        current_aliases.update(item["aliases"])
        current["aliases"] = sorted(current_aliases)
        current["source_count"] = max(int(current["source_count"]), int(item["source_count"]))
        if item["evidence_links"]:
            current["evidence_links"] = item["evidence_links"]
        tier_counts = dict(current.get("source_tier_counts") or {})
        for tier, count in (item.get("source_tier_counts") or {}).items():
            tier_counts[str(tier)] = max(int(tier_counts.get(str(tier), 0)), int(count or 0))
        current["source_tier_counts"] = tier_counts
    return list(deduped.values())


def _upsert_aliases(db: Session, entity: ResearchCanonicalEntity, aliases: list[str], source_count: int) -> None:
    existing_aliases = {
        row.alias_name: row
        for row in db.scalars(
            select(ResearchEntityAlias).where(ResearchEntityAlias.entity_id == entity.id)
        ).all()
    }
    for alias in [entity.canonical_name, *aliases]:
        normalized_alias = _normalize_name(alias)
        if not normalized_alias:
            continue
        existing = existing_aliases.get(normalized_alias)
        if existing is None:
            existing = ResearchEntityAlias(
                entity_id=entity.id,
                alias_name=normalized_alias,
                confidence=100 if normalized_alias == entity.canonical_name else 80,
                source_count=source_count,
            )
            db.add(existing)
        else:
            existing.source_count = max(int(existing.source_count or 0), int(source_count or 0))
            db.add(existing)


def sync_tracking_topic_entities(
    db: Session,
    *,
    topic_id: str,
    report_payload: dict[str, Any],
) -> list[str]:
    updated_ids: list[str] = []
    entities = _iter_graph_entities(report_payload)
    scope_regions = report_payload.get("source_diagnostics", {}).get("scope_regions", []) if isinstance(report_payload.get("source_diagnostics"), dict) else []
    scope_industries = report_payload.get("source_diagnostics", {}).get("scope_industries", []) if isinstance(report_payload.get("source_diagnostics"), dict) else []
    for item in entities:
        entity = db.scalar(
            select(ResearchCanonicalEntity).where(
                ResearchCanonicalEntity.user_id == settings.single_user_id,
                ResearchCanonicalEntity.canonical_name == item["canonical_name"],
                ResearchCanonicalEntity.entity_type == item["entity_type"],
            )
        )
        if entity is None:
            entity = ResearchCanonicalEntity(
                user_id=settings.single_user_id,
                canonical_name=item["canonical_name"],
                entity_type=item["entity_type"],
            )
        profile_payload = entity.profile_payload if isinstance(entity.profile_payload, dict) else {}
        linked_topic_ids = set(
            str(value)
            for value in (profile_payload.get("tracking_topic_ids") or [])
            if _normalize_name(value)
        )
        linked_topic_ids.add(str(topic_id))
        profile_payload["tracking_topic_ids"] = sorted(linked_topic_ids)
        profile_payload["evidence_links"] = item["evidence_links"][:8]
        profile_payload["source_tier_counts"] = item["source_tier_counts"]
        entity.profile_payload = profile_payload
        entity.region_hint = _normalize_name(scope_regions[0]) if scope_regions else entity.region_hint
        entity.industry_hint = _normalize_name(scope_industries[0]) if scope_industries else entity.industry_hint
        entity.last_seen_at = datetime.now(timezone.utc)
        db.add(entity)
        db.flush()
        _upsert_aliases(db, entity, item["aliases"], int(item["source_count"] or 0))
        updated_ids.append(str(entity.id))
    db.commit()
    return updated_ids


def get_entity_detail(db: Session, entity_id: str) -> dict[str, Any] | None:
    try:
        parsed_id = uuid.UUID(str(entity_id))
    except ValueError:
        return None
    entity = db.scalar(
        select(ResearchCanonicalEntity)
        .where(ResearchCanonicalEntity.id == parsed_id)
        .where(ResearchCanonicalEntity.user_id == settings.single_user_id)
    )
    if entity is None:
        return None
    aliases = db.scalars(
        select(ResearchEntityAlias)
        .where(ResearchEntityAlias.entity_id == entity.id)
        .order_by(ResearchEntityAlias.confidence.desc(), ResearchEntityAlias.source_count.desc())
    ).all()
    relations = db.scalars(
        select(ResearchEntityRelation).where(ResearchEntityRelation.from_entity_id == entity.id)
    ).all()
    profile_payload = entity.profile_payload if isinstance(entity.profile_payload, dict) else {}
    evidence_links = [
        link for link in (profile_payload.get("evidence_links") or []) if isinstance(link, dict)
    ]
    return {
        "id": str(entity.id),
        "canonical_name": entity.canonical_name,
        "entity_type": entity.entity_type,
        "region_hint": entity.region_hint or "",
        "industry_hint": entity.industry_hint or "",
        "aliases": [alias.alias_name for alias in aliases],
        "evidence_links": evidence_links,
        "linked_topic_ids": [str(value) for value in (profile_payload.get("tracking_topic_ids") or []) if _normalize_name(value)],
        "relations": [
            {
                "id": str(relation.id),
                "to_entity_id": str(relation.to_entity_id),
                "relation_type": relation.relation_type,
                "weight": int(relation.weight or 0),
                "evidence_payload": relation.evidence_payload or {},
            }
            for relation in relations
        ],
        "profile_payload": profile_payload,
        "last_seen_at": entity.last_seen_at,
        "updated_at": entity.updated_at,
    }


def attach_entity_alias(
    db: Session,
    *,
    entity_id: str,
    alias_name: str,
    confidence: int,
) -> dict[str, Any] | None:
    try:
        parsed_id = uuid.UUID(str(entity_id))
    except ValueError:
        return None
    entity = db.scalar(
        select(ResearchCanonicalEntity)
        .where(ResearchCanonicalEntity.id == parsed_id)
        .where(ResearchCanonicalEntity.user_id == settings.single_user_id)
    )
    if entity is None:
        return None
    normalized_alias = _normalize_name(alias_name)
    if not normalized_alias:
        return None
    alias = db.scalar(
        select(ResearchEntityAlias)
        .where(ResearchEntityAlias.entity_id == entity.id)
        .where(ResearchEntityAlias.alias_name == normalized_alias)
    )
    if alias is None:
        alias = ResearchEntityAlias(
            entity_id=entity.id,
            alias_name=normalized_alias,
            confidence=int(confidence or 80),
            source_count=0,
        )
    else:
        alias.confidence = max(int(alias.confidence or 0), int(confidence or 80))
    db.add(alias)
    db.commit()
    return get_entity_detail(db, str(entity.id))
