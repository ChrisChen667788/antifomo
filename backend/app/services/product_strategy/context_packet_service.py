from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product_strategy_context_entities import (
    ProductStrategyDecisionContextInitializationAudit,
    ProductStrategyDecisionContextPacket,
    ProductStrategyDecisionContextPacketRevision,
)
from app.services.product_strategy.catalog import CATALOG_VERSION, canonical_digest
from app.services.product_strategy.context_packet_catalog import (
    CONTEXT_PACKET_VERSION,
    INITIALIZATION_EVENT_KEY,
    PROJECT_SCOPE,
    approval_evidence,
    context_packet_catalog_digest,
    context_packet_definitions,
    context_packet_governance,
    excluded_card_definitions,
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


def _packet_fields(definition: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_scope": definition["project_scope"],
        "roadmap_card_key": definition["roadmap_card_key"],
        "product_key": definition["product_key"],
        "decision": definition["decision"],
        "title": definition["title"],
        "problem_statement": definition["problem_statement"],
        "rationale": definition["rationale"],
        "source_catalog_keys_payload": list(definition["source_catalog_keys"]),
        "source_digests_payload": list(definition["source_digests"]),
        "source_references_payload": deepcopy(definition["source_references"]),
        "assumptions_payload": list(definition["assumptions"]),
        "constraints_payload": list(definition["constraints"]),
        "module_targets_payload": list(definition["module_targets"]),
        "owner_evidence_payload": deepcopy(definition["approval_evidence"]),
        "retention_until": _as_utc(definition["retention_until"]),
        "revision": int(definition["revision"]),
        "revision_digest": definition["revision_digest"],
        "status": definition["status"],
        "can_auto_execute": bool(definition["can_auto_execute"]),
        "can_auto_approve_release": bool(definition["can_auto_approve_release"]),
        "requires_human_change_approval": bool(definition["requires_human_change_approval"]),
        "production_status": definition["production_status"],
    }


def _revision_snapshot(definition: dict[str, Any]) -> dict[str, Any]:
    """The stored snapshot deliberately has no row ID or wall-clock timestamp."""

    snapshot = deepcopy(definition)
    snapshot["source_catalog_version"] = CATALOG_VERSION
    snapshot["packet_catalog_digest"] = context_packet_catalog_digest()
    return snapshot


def _audit_definition() -> dict[str, Any]:
    packet_digest = context_packet_catalog_digest()
    payload = {
        "event_key": INITIALIZATION_EVENT_KEY,
        "project_scope": PROJECT_SCOPE,
        "event_type": "explicit_user_instruction_context_packet_initialization",
        "approval_evidence": approval_evidence(),
        "allowed_decisions": ["build", "integrate", "defer"],
        "excluded_card_keys": [card["card_key"] for card in excluded_card_definitions()],
        "source_catalog_version": CATALOG_VERSION,
        "packet_catalog_digest": packet_digest,
        "can_auto_execute": False,
        "can_auto_approve_release": False,
        "release_gate_mutated": False,
    }
    return {**payload, "event_digest": canonical_digest(payload)}


def serialize_packet_revision(row: ProductStrategyDecisionContextPacketRevision) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "packet_key": row.packet_key,
        "revision": row.revision,
        "previous_revision_digest": row.previous_revision_digest,
        "revision_digest": row.revision_digest,
        "event_type": row.event_type,
        "snapshot": deepcopy(row.snapshot_payload or {}),
        "approval_evidence": deepcopy(row.approval_evidence_payload or {}),
        "is_immutable": bool(row.is_immutable),
        "seed_managed": bool(row.seed_managed),
        "created_at": _iso(row.created_at),
    }


def serialize_initialization_audit(row: ProductStrategyDecisionContextInitializationAudit) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "event_key": row.event_key,
        "project_scope": row.project_scope,
        "event_type": row.event_type,
        "approval_evidence": deepcopy(row.approval_evidence_payload or {}),
        "allowed_decisions": list(row.allowed_decisions_payload or []),
        "excluded_card_keys": list(row.excluded_card_keys_payload or []),
        "source_catalog_version": row.source_catalog_version,
        "packet_catalog_digest": row.packet_catalog_digest,
        "event_digest": row.event_digest,
        "can_auto_execute": bool(row.can_auto_execute),
        "can_auto_approve_release": bool(row.can_auto_approve_release),
        "release_gate_mutated": bool(row.release_gate_mutated),
        "created_at": _iso(row.created_at),
    }


def serialize_packet(
    row: ProductStrategyDecisionContextPacket,
    revisions: list[ProductStrategyDecisionContextPacketRevision],
) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "packet_key": row.packet_key,
        "project_scope": row.project_scope,
        "source_catalog_version": CATALOG_VERSION,
        "packet_catalog_digest": context_packet_catalog_digest(),
        "roadmap_card_key": row.roadmap_card_key,
        "product_key": row.product_key,
        "decision": row.decision,
        "decision_approval_status": (
            "approved_by_explicit_product_owner_instruction"
            if row.status == "approved_for_context"
            else "human_review_required"
        ),
        "title": row.title,
        "problem_statement": row.problem_statement,
        "rationale": row.rationale,
        "source_catalog_keys": list(row.source_catalog_keys_payload or []),
        "source_digests": list(row.source_digests_payload or []),
        "source_references": deepcopy(row.source_references_payload or []),
        "assumptions": list(row.assumptions_payload or []),
        "constraints": list(row.constraints_payload or []),
        "module_targets": list(row.module_targets_payload or []),
        "approval_evidence": deepcopy(row.owner_evidence_payload or {}),
        "retention_until": _iso(row.retention_until),
        "revision": row.revision,
        "revision_digest": row.revision_digest,
        "status": row.status,
        "can_auto_execute": bool(row.can_auto_execute),
        "can_auto_approve_release": bool(row.can_auto_approve_release),
        "requires_human_change_approval": bool(row.requires_human_change_approval),
        "production_status": row.production_status,
        "release_impact": "none",
        "seed_managed": bool(row.seed_managed),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "revisions": [serialize_packet_revision(revision) for revision in revisions],
    }


def _packet_sort_key(row: ProductStrategyDecisionContextPacket) -> tuple[int, str]:
    order = {definition["packet_key"]: index for index, definition in enumerate(context_packet_definitions())}
    return order.get(row.packet_key, len(order)), row.packet_key


def _serialized_packets(db: Session) -> list[dict[str, Any]]:
    packets = list(
        db.scalars(
            select(ProductStrategyDecisionContextPacket).where(
                ProductStrategyDecisionContextPacket.project_scope == PROJECT_SCOPE
            )
        ).all()
    )
    packets.sort(key=_packet_sort_key)
    if not packets:
        return []

    packet_ids = [packet.id for packet in packets]
    revision_rows = list(
        db.scalars(
            select(ProductStrategyDecisionContextPacketRevision)
            .where(ProductStrategyDecisionContextPacketRevision.packet_id.in_(packet_ids))
            .order_by(ProductStrategyDecisionContextPacketRevision.revision.asc())
        ).all()
    )
    revisions_by_packet: dict[object, list[ProductStrategyDecisionContextPacketRevision]] = {}
    for revision in revision_rows:
        revisions_by_packet.setdefault(revision.packet_id, []).append(revision)
    return [serialize_packet(packet, revisions_by_packet.get(packet.id, [])) for packet in packets]


def get_persisted_decision_context_packets(db: Session) -> dict[str, Any]:
    packets = _serialized_packets(db)
    audit = db.scalar(
        select(ProductStrategyDecisionContextInitializationAudit).where(
            ProductStrategyDecisionContextInitializationAudit.event_key == INITIALIZATION_EVENT_KEY
        )
    )
    serialized_audit = serialize_initialization_audit(audit) if audit is not None else None
    snapshot_digest = canonical_digest(
        {
            "packets": [
                {
                    "packet_key": packet["packet_key"],
                    "revision": packet["revision"],
                    "revision_digest": packet["revision_digest"],
                    "seed_managed": packet["seed_managed"],
                    "revisions": [
                        {
                            "revision": revision["revision"],
                            "previous_revision_digest": revision["previous_revision_digest"],
                            "revision_digest": revision["revision_digest"],
                            "seed_managed": revision["seed_managed"],
                        }
                        for revision in packet["revisions"]
                    ],
                }
                for packet in packets
            ],
            "initialization_audit": (
                {
                    "event_key": serialized_audit["event_key"],
                    "event_digest": serialized_audit["event_digest"],
                }
                if serialized_audit
                else None
            ),
        }
    )
    return {
        "context_packet_version": CONTEXT_PACKET_VERSION,
        "source_catalog_version": CATALOG_VERSION,
        "catalog_digest": context_packet_catalog_digest(),
        "read_only": False,
        "initialized": bool(packets or serialized_audit),
        "persistent_snapshot_digest": snapshot_digest if packets or serialized_audit else None,
        "approval_evidence": serialized_audit["approval_evidence"] if serialized_audit else approval_evidence(),
        "governance": context_packet_governance(),
        "packets": packets,
        "excluded_cards": excluded_card_definitions(),
        "initialization_audit": serialized_audit,
    }


def initialize_decision_context_packets(db: Session) -> dict[str, Any]:
    """Atomically materialize explicitly approved context packets, never updating rows.

    The endpoint is deliberately an explicit POST rather than a background or
    startup seed.  Existing human-managed packets and revisions are untouched;
    even existing seed-managed rows are not silently refreshed because a new
    source/development version should require a separate human-visible change.
    """

    definitions = context_packet_definitions()
    outcome = {
        "packets": {"created": 0, "existing_seed_managed": 0, "preserved_human": 0},
        "revisions": {"created": 0, "existing": 0, "preserved_human": 0},
        "approval_audit": {"created": 0, "existing": 0},
    }
    try:
        for definition in definitions:
            packet = db.scalar(
                select(ProductStrategyDecisionContextPacket).where(
                    ProductStrategyDecisionContextPacket.packet_key == definition["packet_key"]
                )
            )
            if packet is None:
                packet = ProductStrategyDecisionContextPacket(
                    packet_key=definition["packet_key"],
                    seed_managed=True,
                    **_packet_fields(definition),
                )
                db.add(packet)
                db.flush()
                outcome["packets"]["created"] += 1
                revision = ProductStrategyDecisionContextPacketRevision(
                    packet_id=packet.id,
                    packet_key=packet.packet_key,
                    revision=definition["revision"],
                    previous_revision_digest=None,
                    revision_digest=definition["revision_digest"],
                    event_type="explicit_user_instruction_initialization",
                    snapshot_payload=_revision_snapshot(definition),
                    approval_evidence_payload=deepcopy(definition["approval_evidence"]),
                    is_immutable=True,
                    seed_managed=True,
                )
                db.add(revision)
                outcome["revisions"]["created"] += 1
                continue

            if not packet.seed_managed:
                outcome["packets"]["preserved_human"] += 1
                outcome["revisions"]["preserved_human"] += 1
                continue

            outcome["packets"]["existing_seed_managed"] += 1
            revision = db.scalar(
                select(ProductStrategyDecisionContextPacketRevision).where(
                    ProductStrategyDecisionContextPacketRevision.packet_id == packet.id,
                    ProductStrategyDecisionContextPacketRevision.revision == definition["revision"],
                )
            )
            if revision is None:
                db.add(
                    ProductStrategyDecisionContextPacketRevision(
                        packet_id=packet.id,
                        packet_key=packet.packet_key,
                        revision=definition["revision"],
                        previous_revision_digest=None,
                        revision_digest=definition["revision_digest"],
                        event_type="explicit_user_instruction_initialization_recovery",
                        snapshot_payload=_revision_snapshot(definition),
                        approval_evidence_payload=deepcopy(definition["approval_evidence"]),
                        is_immutable=True,
                        seed_managed=True,
                    )
                )
                outcome["revisions"]["created"] += 1
            else:
                outcome["revisions"]["existing"] += 1

        audit_definition = _audit_definition()
        audit = db.scalar(
            select(ProductStrategyDecisionContextInitializationAudit).where(
                ProductStrategyDecisionContextInitializationAudit.event_key == INITIALIZATION_EVENT_KEY
            )
        )
        if audit is None:
            db.add(
                ProductStrategyDecisionContextInitializationAudit(
                    event_key=audit_definition["event_key"],
                    project_scope=audit_definition["project_scope"],
                    event_type=audit_definition["event_type"],
                    approval_evidence_payload=deepcopy(audit_definition["approval_evidence"]),
                    allowed_decisions_payload=list(audit_definition["allowed_decisions"]),
                    excluded_card_keys_payload=list(audit_definition["excluded_card_keys"]),
                    source_catalog_version=audit_definition["source_catalog_version"],
                    packet_catalog_digest=audit_definition["packet_catalog_digest"],
                    event_digest=audit_definition["event_digest"],
                    can_auto_execute=False,
                    can_auto_approve_release=False,
                    release_gate_mutated=False,
                )
            )
            outcome["approval_audit"]["created"] += 1
        else:
            outcome["approval_audit"]["existing"] += 1
        db.commit()
    except Exception:
        db.rollback()
        raise

    result = get_persisted_decision_context_packets(db)
    result["initialization"] = outcome
    return result
