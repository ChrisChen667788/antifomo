from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product_strategy_artifact_acceptance_entities import (
    ProductStrategyArtifactAcceptanceDraft,
    ProductStrategyArtifactAcceptanceInitializationAudit,
    ProductStrategyArtifactAcceptanceRevision,
)
from app.models.product_strategy_context_entities import ProductStrategyDecisionContextPacket
from app.services.product_strategy.artifact_acceptance_catalog import (
    ARTIFACT_ACCEPTANCE_VERSION,
    INITIALIZATION_EVENT_KEY,
    artifact_acceptance_catalog_digest,
    artifact_acceptance_definitions,
    artifact_acceptance_governance,
    evidence_source_bundle_from_context_packet,
    field_level_revision_diff,
    instruction_evidence,
)
from app.services.product_strategy.catalog import CATALOG_VERSION, canonical_digest
from app.services.product_strategy.context_packet_catalog import PROJECT_SCOPE, context_packet_catalog_digest


class DecisionContextPacketsRequiredError(Exception):
    """Fail closed when 2.10.2 cannot bind to materialized 2.10.1 packets."""

    def __init__(self, *, missing_packet_keys: list[str], unusable_packet_keys: list[str]) -> None:
        self.missing_packet_keys = missing_packet_keys
        self.unusable_packet_keys = unusable_packet_keys
        super().__init__("2.10.2 artifact acceptance requires usable persisted 2.10.1 context packets.")


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return normalized.isoformat().replace("+00:00", "Z")


def _context_packet_shape(packet: ProductStrategyDecisionContextPacket) -> dict[str, Any]:
    """Provide only the reviewed packet fields needed for evidence binding."""

    return {
        "packet_key": packet.packet_key,
        "roadmap_card_key": packet.roadmap_card_key,
        "decision": packet.decision,
        "revision": packet.revision,
        "revision_digest": packet.revision_digest,
        "source_catalog_keys": list(packet.source_catalog_keys_payload or []),
        "source_digests": list(packet.source_digests_payload or []),
        "source_references": deepcopy(packet.source_references_payload or []),
    }


def _runtime_definition(
    definition: dict[str, Any],
    context_packet: ProductStrategyDecisionContextPacket,
) -> dict[str, Any]:
    """Pin a static template to the persisted packet revision it will review."""

    resolved = deepcopy(definition)
    bundle = evidence_source_bundle_from_context_packet(_context_packet_shape(context_packet))
    resolved["evidence_source_bundle"] = bundle
    resolved["evidence_source_bundle_digest"] = canonical_digest(bundle)
    resolved.pop("revision_digest", None)
    resolved["revision_digest"] = canonical_digest(resolved)
    return resolved


def _revision_snapshot(definition: dict[str, Any]) -> dict[str, Any]:
    """Keep diff inputs stable and avoid IDs/timestamps or self-referential digest fields."""

    return {
        key: deepcopy(value)
        for key, value in definition.items()
        if key not in {"revision_digest", "acceptance_label"}
    }


def _draft_fields(
    definition: dict[str, Any],
    context_packet: ProductStrategyDecisionContextPacket,
) -> dict[str, Any]:
    return {
        "project_scope": definition["project_scope"],
        "decision_context_packet_id": context_packet.id,
        "decision_context_packet_key": definition["decision_context_packet_key"],
        "roadmap_card_key": definition["roadmap_card_key"],
        "decision": definition["decision"],
        "artifact_type": definition["artifact_type"],
        "title": definition["title"],
        "artifact_summary": definition["artifact_summary"],
        "acceptance_status": definition["acceptance_status"],
        "blocking_status": definition["blocking_status"],
        "office_evidence_status": definition["office_evidence_status"],
        "visual_evidence_status": definition["visual_evidence_status"],
        "acceptance_checklist_payload": deepcopy(definition["acceptance_checklist"]),
        "evidence_source_bundle_payload": deepcopy(definition["evidence_source_bundle"]),
        "evidence_source_bundle_digest": definition["evidence_source_bundle_digest"],
        "revision": int(definition["revision"]),
        "revision_digest": definition["revision_digest"],
        "can_auto_accept": bool(definition["can_auto_accept"]),
        "can_auto_execute": bool(definition["can_auto_execute"]),
        "can_auto_approve_release": bool(definition["can_auto_approve_release"]),
        "requires_human_evidence_review": bool(definition["requires_human_evidence_review"]),
        "production_status": definition["production_status"],
    }


def _serialize_revision(row: ProductStrategyArtifactAcceptanceRevision) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "artifact_key": row.artifact_key,
        "revision": row.revision,
        "previous_revision_digest": row.previous_revision_digest,
        "revision_digest": row.revision_digest,
        "event_type": row.event_type,
        "snapshot": deepcopy(row.snapshot_payload or {}),
        "evidence_source_bundle": deepcopy(row.evidence_source_bundle_payload or {}),
        "evidence_source_bundle_digest": row.evidence_source_bundle_digest,
        "field_level_diff": deepcopy(row.field_level_diff_payload or {}),
        "is_immutable": bool(row.is_immutable),
        "seed_managed": bool(row.seed_managed),
        "created_at": _iso(row.created_at),
    }


def _serialize_draft(
    row: ProductStrategyArtifactAcceptanceDraft,
    revisions: list[ProductStrategyArtifactAcceptanceRevision],
) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "artifact_key": row.artifact_key,
        "project_scope": row.project_scope,
        "artifact_acceptance_catalog_digest": artifact_acceptance_catalog_digest(),
        "decision_context_packet_key": row.decision_context_packet_key,
        "roadmap_card_key": row.roadmap_card_key,
        "decision": row.decision,
        "artifact_type": row.artifact_type,
        "title": row.title,
        "artifact_summary": row.artifact_summary,
        "acceptance_status": row.acceptance_status,
        "acceptance_label": "HOLD" if row.acceptance_status == "hold" else row.acceptance_status.upper(),
        "blocking_status": row.blocking_status,
        "office_evidence_status": row.office_evidence_status,
        "visual_evidence_status": row.visual_evidence_status,
        "acceptance_checklist": deepcopy(row.acceptance_checklist_payload or []),
        "evidence_source_bundle": deepcopy(row.evidence_source_bundle_payload or {}),
        "evidence_source_bundle_digest": row.evidence_source_bundle_digest,
        "revision": row.revision,
        "revision_digest": row.revision_digest,
        "can_auto_accept": bool(row.can_auto_accept),
        "can_auto_execute": bool(row.can_auto_execute),
        "can_auto_approve_release": bool(row.can_auto_approve_release),
        "requires_human_evidence_review": bool(row.requires_human_evidence_review),
        "production_status": row.production_status,
        "release_impact": "none",
        "seed_managed": bool(row.seed_managed),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "revisions": [_serialize_revision(revision) for revision in revisions],
    }


def _serialize_audit(row: ProductStrategyArtifactAcceptanceInitializationAudit) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "event_key": row.event_key,
        "project_scope": row.project_scope,
        "event_type": row.event_type,
        "instruction_evidence": deepcopy(row.instruction_evidence_payload or {}),
        "required_context_packet_keys": list(row.required_context_packet_keys_payload or []),
        "artifact_catalog_digest": row.artifact_catalog_digest,
        "context_packet_catalog_digest": row.context_packet_catalog_digest,
        "event_digest": row.event_digest,
        "can_auto_accept": bool(row.can_auto_accept),
        "can_auto_execute": bool(row.can_auto_execute),
        "can_auto_approve_release": bool(row.can_auto_approve_release),
        "release_gate_mutated": bool(row.release_gate_mutated),
        "created_at": _iso(row.created_at),
    }


def _artifact_sort_key(row: ProductStrategyArtifactAcceptanceDraft) -> tuple[int, str]:
    order = {definition["artifact_key"]: index for index, definition in enumerate(artifact_acceptance_definitions())}
    return order.get(row.artifact_key, len(order)), row.artifact_key


def _serialized_drafts(db: Session) -> list[dict[str, Any]]:
    drafts = list(
        db.scalars(
            select(ProductStrategyArtifactAcceptanceDraft).where(
                ProductStrategyArtifactAcceptanceDraft.project_scope == PROJECT_SCOPE
            )
        ).all()
    )
    drafts.sort(key=_artifact_sort_key)
    if not drafts:
        return []

    draft_ids = [draft.id for draft in drafts]
    revision_rows = list(
        db.scalars(
            select(ProductStrategyArtifactAcceptanceRevision)
            .where(ProductStrategyArtifactAcceptanceRevision.draft_id.in_(draft_ids))
            .order_by(ProductStrategyArtifactAcceptanceRevision.revision.asc())
        ).all()
    )
    revisions_by_draft: dict[object, list[ProductStrategyArtifactAcceptanceRevision]] = {}
    for revision in revision_rows:
        revisions_by_draft.setdefault(revision.draft_id, []).append(revision)
    return [_serialize_draft(draft, revisions_by_draft.get(draft.id, [])) for draft in drafts]


def _context_packet_requirements(db: Session) -> dict[str, ProductStrategyDecisionContextPacket]:
    expected = {definition["decision_context_packet_key"] for definition in artifact_acceptance_definitions()}
    rows = list(
        db.scalars(
            select(ProductStrategyDecisionContextPacket).where(
                ProductStrategyDecisionContextPacket.packet_key.in_(expected)
            )
        ).all()
    )
    return {row.packet_key: row for row in rows}


def _context_packet_readiness(db: Session) -> dict[str, Any]:
    required_keys = [definition["decision_context_packet_key"] for definition in artifact_acceptance_definitions()]
    rows = _context_packet_requirements(db)
    missing = [key for key in required_keys if key not in rows]
    unusable = [
        key
        for key in required_keys
        if key in rows
        and (
            rows[key].status != "approved_for_context"
            or rows[key].can_auto_execute
            or rows[key].can_auto_approve_release
            or not rows[key].requires_human_change_approval
        )
    ]
    return {
        "required_context_packet_keys": required_keys,
        "missing_context_packet_keys": missing,
        "unusable_context_packet_keys": unusable,
        "ready_for_explicit_initialization": not missing and not unusable,
    }


def get_persisted_artifact_acceptance(db: Session) -> dict[str, Any]:
    artifacts = _serialized_drafts(db)
    audit = db.scalar(
        select(ProductStrategyArtifactAcceptanceInitializationAudit).where(
            ProductStrategyArtifactAcceptanceInitializationAudit.event_key == INITIALIZATION_EVENT_KEY
        )
    )
    serialized_audit = _serialize_audit(audit) if audit is not None else None
    persistent_snapshot_digest = canonical_digest(
        {
            "artifacts": [
                {
                    "artifact_key": artifact["artifact_key"],
                    "decision_context_packet_key": artifact["decision_context_packet_key"],
                    "revision": artifact["revision"],
                    "revision_digest": artifact["revision_digest"],
                    "evidence_source_bundle_digest": artifact["evidence_source_bundle_digest"],
                    "seed_managed": artifact["seed_managed"],
                    "revisions": [
                        {
                            "revision": revision["revision"],
                            "revision_digest": revision["revision_digest"],
                            "previous_revision_digest": revision["previous_revision_digest"],
                            "evidence_source_bundle_digest": revision["evidence_source_bundle_digest"],
                            "seed_managed": revision["seed_managed"],
                        }
                        for revision in artifact["revisions"]
                    ],
                }
                for artifact in artifacts
            ],
            "initialization_audit": (
                {"event_key": serialized_audit["event_key"], "event_digest": serialized_audit["event_digest"]}
                if serialized_audit
                else None
            ),
        }
    )
    return {
        "artifact_acceptance_version": ARTIFACT_ACCEPTANCE_VERSION,
        "source_catalog_version": CATALOG_VERSION,
        "catalog_digest": artifact_acceptance_catalog_digest(),
        "context_packet_catalog_digest": context_packet_catalog_digest(),
        "read_only": False,
        "initialized": bool(artifacts or serialized_audit),
        "persistent_snapshot_digest": persistent_snapshot_digest if artifacts or serialized_audit else None,
        "instruction_evidence": serialized_audit["instruction_evidence"] if serialized_audit else instruction_evidence(),
        "governance": artifact_acceptance_governance(),
        "context_packet_readiness": _context_packet_readiness(db),
        "artifacts": artifacts,
        "initialization_audit": serialized_audit,
    }


def _audit_definition() -> dict[str, Any]:
    payload = {
        "event_key": INITIALIZATION_EVENT_KEY,
        "project_scope": PROJECT_SCOPE,
        "event_type": "explicit_user_instruction_hold_only_artifact_acceptance_initialization",
        "instruction_evidence": instruction_evidence(),
        "required_context_packet_keys": [
            definition["decision_context_packet_key"] for definition in artifact_acceptance_definitions()
        ],
        "artifact_catalog_digest": artifact_acceptance_catalog_digest(),
        "context_packet_catalog_digest": context_packet_catalog_digest(),
        "can_auto_accept": False,
        "can_auto_execute": False,
        "can_auto_approve_release": False,
        "release_gate_mutated": False,
    }
    return {**payload, "event_digest": canonical_digest(payload)}


def initialize_artifact_acceptance(db: Session) -> dict[str, Any]:
    """Materialize HOLD-only templates after a separate 2.10.1 initialization.

    This function intentionally has no artifact upload, Office parser, render
    service, acceptance transition, release change, or execution operation.
    """

    readiness = _context_packet_readiness(db)
    if not readiness["ready_for_explicit_initialization"]:
        raise DecisionContextPacketsRequiredError(
            missing_packet_keys=readiness["missing_context_packet_keys"],
            unusable_packet_keys=readiness["unusable_context_packet_keys"],
        )

    packet_by_key = _context_packet_requirements(db)
    outcome = {
        "drafts": {"created": 0, "existing_seed_managed": 0, "preserved_human": 0},
        "revisions": {"created": 0, "existing": 0, "preserved_human": 0},
        "initialization_audit": {"created": 0, "existing": 0},
    }
    try:
        for static_definition in artifact_acceptance_definitions():
            packet = packet_by_key[static_definition["decision_context_packet_key"]]
            definition = _runtime_definition(static_definition, packet)
            draft = db.scalar(
                select(ProductStrategyArtifactAcceptanceDraft).where(
                    ProductStrategyArtifactAcceptanceDraft.artifact_key == definition["artifact_key"]
                )
            )
            if draft is None:
                draft = ProductStrategyArtifactAcceptanceDraft(
                    artifact_key=definition["artifact_key"],
                    seed_managed=True,
                    **_draft_fields(definition, packet),
                )
                db.add(draft)
                db.flush()
                outcome["drafts"]["created"] += 1
                snapshot = _revision_snapshot(definition)
                db.add(
                    ProductStrategyArtifactAcceptanceRevision(
                        draft_id=draft.id,
                        artifact_key=draft.artifact_key,
                        revision=definition["revision"],
                        previous_revision_digest=None,
                        revision_digest=definition["revision_digest"],
                        event_type="explicit_hold_only_initialization",
                        snapshot_payload=snapshot,
                        evidence_source_bundle_payload=deepcopy(definition["evidence_source_bundle"]),
                        evidence_source_bundle_digest=definition["evidence_source_bundle_digest"],
                        field_level_diff_payload=field_level_revision_diff(None, snapshot),
                        is_immutable=True,
                        seed_managed=True,
                    )
                )
                outcome["revisions"]["created"] += 1
                continue

            if not draft.seed_managed:
                outcome["drafts"]["preserved_human"] += 1
                outcome["revisions"]["preserved_human"] += 1
                continue

            outcome["drafts"]["existing_seed_managed"] += 1
            revision = db.scalar(
                select(ProductStrategyArtifactAcceptanceRevision).where(
                    ProductStrategyArtifactAcceptanceRevision.draft_id == draft.id,
                    ProductStrategyArtifactAcceptanceRevision.revision == definition["revision"],
                )
            )
            if revision is None:
                snapshot = _revision_snapshot(definition)
                db.add(
                    ProductStrategyArtifactAcceptanceRevision(
                        draft_id=draft.id,
                        artifact_key=draft.artifact_key,
                        revision=definition["revision"],
                        previous_revision_digest=None,
                        revision_digest=definition["revision_digest"],
                        event_type="explicit_hold_only_initialization_recovery",
                        snapshot_payload=snapshot,
                        evidence_source_bundle_payload=deepcopy(definition["evidence_source_bundle"]),
                        evidence_source_bundle_digest=definition["evidence_source_bundle_digest"],
                        field_level_diff_payload=field_level_revision_diff(None, snapshot),
                        is_immutable=True,
                        seed_managed=True,
                    )
                )
                outcome["revisions"]["created"] += 1
            else:
                outcome["revisions"]["existing"] += 1

        audit_definition = _audit_definition()
        audit = db.scalar(
            select(ProductStrategyArtifactAcceptanceInitializationAudit).where(
                ProductStrategyArtifactAcceptanceInitializationAudit.event_key == INITIALIZATION_EVENT_KEY
            )
        )
        if audit is None:
            db.add(
                ProductStrategyArtifactAcceptanceInitializationAudit(
                    event_key=audit_definition["event_key"],
                    project_scope=audit_definition["project_scope"],
                    event_type=audit_definition["event_type"],
                    instruction_evidence_payload=deepcopy(audit_definition["instruction_evidence"]),
                    required_context_packet_keys_payload=list(audit_definition["required_context_packet_keys"]),
                    artifact_catalog_digest=audit_definition["artifact_catalog_digest"],
                    context_packet_catalog_digest=audit_definition["context_packet_catalog_digest"],
                    event_digest=audit_definition["event_digest"],
                    can_auto_accept=False,
                    can_auto_execute=False,
                    can_auto_approve_release=False,
                    release_gate_mutated=False,
                )
            )
            outcome["initialization_audit"]["created"] += 1
        else:
            outcome["initialization_audit"]["existing"] += 1
        db.commit()
    except Exception:
        db.rollback()
        raise

    result = get_persisted_artifact_acceptance(db)
    result["initialization"] = outcome
    return result
