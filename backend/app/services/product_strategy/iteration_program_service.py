from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product_strategy_iteration_entities import (
    ProductStrategyIteration,
    ProductStrategyIterationInitializationAudit,
    ProductStrategyIterationRevision,
)
from app.services.product_strategy.catalog import canonical_digest
from app.services.product_strategy.iteration_program_catalog import (
    INITIALIZATION_EVENT_KEY,
    ITERATION_PROGRAM_VERSION,
    PROJECT_SCOPE,
    governance,
    instruction_evidence,
    iteration_definitions,
    preview_iteration_program,
    program_digest,
)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return normalized.isoformat().replace("+00:00", "Z")


def _snapshot(definition: dict[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in definition.items()
        if key not in {"revision_digest", "initial_field_level_diff"}
    }


def _initial_diff(definition: dict[str, Any]) -> dict[str, Any]:
    snapshot = _snapshot(definition)
    return {
        "from_revision": None,
        "to_revision": definition["revision"],
        "changed_fields": [
            {"field": key, "before": None, "after": value, "change_type": "added"}
            for key, value in snapshot.items()
        ],
        "auto_acceptance_forbidden": True,
        "release_gate_mutated": False,
    }


def _row_fields(definition: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_scope": definition["project_scope"],
        "version": definition["version"],
        "sequence": int(definition["sequence"]),
        "title": definition["title"],
        "workstream": definition["workstream"],
        "decision": definition["decision"],
        "purpose": definition["purpose"],
        "scope_boundary": definition["scope_boundary"],
        "implementation_status": definition["implementation_status"],
        "external_evidence_status": definition["external_evidence_status"],
        "acceptance_status": definition["acceptance_status"],
        "dependencies_payload": deepcopy(definition["dependencies"]),
        "source_basis_payload": deepcopy(definition["source_basis"]),
        "delivery_artifacts_payload": deepcopy(definition["delivery_artifacts"]),
        "acceptance_criteria_payload": deepcopy(definition["acceptance_criteria"]),
        "external_evidence_requirements_payload": deepcopy(definition["external_evidence_requirements"]),
        "can_auto_accept": bool(definition["can_auto_accept"]),
        "can_auto_execute": bool(definition["can_auto_execute"]),
        "can_auto_approve_release": bool(definition["can_auto_approve_release"]),
        "requires_human_evidence_review": bool(definition["requires_human_evidence_review"]),
        "production_status": definition["production_status"],
        "revision": int(definition["revision"]),
        "revision_digest": definition["revision_digest"],
    }


def _serialize_revision(row: ProductStrategyIterationRevision) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "iteration_key": row.iteration_key,
        "revision": row.revision,
        "previous_revision_digest": row.previous_revision_digest,
        "revision_digest": row.revision_digest,
        "event_type": row.event_type,
        "snapshot": deepcopy(row.snapshot_payload or {}),
        "field_level_diff": deepcopy(row.field_level_diff_payload or {}),
        "is_immutable": bool(row.is_immutable),
        "seed_managed": bool(row.seed_managed),
        "created_at": _iso(row.created_at),
    }


def _serialize_iteration(
    row: ProductStrategyIteration,
    revisions: list[ProductStrategyIterationRevision],
) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "iteration_key": row.iteration_key,
        "project_scope": row.project_scope,
        "version": row.version,
        "sequence": row.sequence,
        "title": row.title,
        "workstream": row.workstream,
        "decision": row.decision,
        "purpose": row.purpose,
        "scope_boundary": row.scope_boundary,
        "implementation_status": row.implementation_status,
        "feature_implementation_status": "gated_or_pending_evidence",
        "external_evidence_status": row.external_evidence_status,
        "acceptance_status": row.acceptance_status,
        "dependencies": deepcopy(row.dependencies_payload or []),
        "source_basis": deepcopy(row.source_basis_payload or []),
        "delivery_artifacts": deepcopy(row.delivery_artifacts_payload or []),
        "acceptance_criteria": deepcopy(row.acceptance_criteria_payload or []),
        "external_evidence_requirements": deepcopy(row.external_evidence_requirements_payload or []),
        "can_auto_accept": bool(row.can_auto_accept),
        "can_auto_execute": bool(row.can_auto_execute),
        "can_auto_approve_release": bool(row.can_auto_approve_release),
        "requires_human_evidence_review": bool(row.requires_human_evidence_review),
        "production_status": row.production_status,
        "revision": row.revision,
        "revision_digest": row.revision_digest,
        "seed_managed": bool(row.seed_managed),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "revisions": [_serialize_revision(revision) for revision in revisions],
        "initial_field_level_diff": _initial_diff(
            {
                **_snapshot_from_row(row),
                "revision": row.revision,
                "revision_digest": row.revision_digest,
            }
        ),
    }


def _snapshot_from_row(row: ProductStrategyIteration) -> dict[str, Any]:
    return {
        "iteration_key": row.iteration_key,
        "project_scope": row.project_scope,
        "version": row.version,
        "sequence": row.sequence,
        "title": row.title,
        "workstream": row.workstream,
        "decision": row.decision,
        "purpose": row.purpose,
        "scope_boundary": row.scope_boundary,
        "implementation_status": row.implementation_status,
        "feature_implementation_status": "gated_or_pending_evidence",
        "external_evidence_status": row.external_evidence_status,
        "acceptance_status": row.acceptance_status,
        "dependencies": deepcopy(row.dependencies_payload or []),
        "source_basis": deepcopy(row.source_basis_payload or []),
        "delivery_artifacts": deepcopy(row.delivery_artifacts_payload or []),
        "acceptance_criteria": deepcopy(row.acceptance_criteria_payload or []),
        "external_evidence_requirements": deepcopy(row.external_evidence_requirements_payload or []),
        "can_auto_accept": bool(row.can_auto_accept),
        "can_auto_execute": bool(row.can_auto_execute),
        "can_auto_approve_release": bool(row.can_auto_approve_release),
        "requires_human_evidence_review": bool(row.requires_human_evidence_review),
        "production_status": row.production_status,
    }


def _serialize_audit(row: ProductStrategyIterationInitializationAudit) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "event_key": row.event_key,
        "project_scope": row.project_scope,
        "event_type": row.event_type,
        "instruction_evidence": deepcopy(row.instruction_evidence_payload or {}),
        "iteration_program_digest": row.iteration_program_digest,
        "iteration_keys": list(row.iteration_keys_payload or []),
        "event_digest": row.event_digest,
        "can_auto_accept": bool(row.can_auto_accept),
        "can_auto_execute": bool(row.can_auto_execute),
        "can_auto_approve_release": bool(row.can_auto_approve_release),
        "release_gate_mutated": bool(row.release_gate_mutated),
        "created_at": _iso(row.created_at),
    }


def _sorted_iterations(db: Session) -> list[ProductStrategyIteration]:
    return list(
        db.scalars(
            select(ProductStrategyIteration)
            .where(ProductStrategyIteration.project_scope == PROJECT_SCOPE)
            .order_by(ProductStrategyIteration.sequence.asc(), ProductStrategyIteration.iteration_key.asc())
        ).all()
    )


def _serialized_iterations(db: Session) -> list[dict[str, Any]]:
    iterations = _sorted_iterations(db)
    if not iterations:
        return []
    ids = [iteration.id for iteration in iterations]
    revisions = list(
        db.scalars(
            select(ProductStrategyIterationRevision)
            .where(ProductStrategyIterationRevision.iteration_id.in_(ids))
            .order_by(ProductStrategyIterationRevision.revision.asc())
        ).all()
    )
    revisions_by_iteration: dict[object, list[ProductStrategyIterationRevision]] = {}
    for revision in revisions:
        revisions_by_iteration.setdefault(revision.iteration_id, []).append(revision)
    return [_serialize_iteration(iteration, revisions_by_iteration.get(iteration.id, [])) for iteration in iterations]


def get_persisted_iteration_program(db: Session) -> dict[str, Any]:
    preview = preview_iteration_program()
    iterations = _serialized_iterations(db)
    audit = db.scalar(
        select(ProductStrategyIterationInitializationAudit).where(
            ProductStrategyIterationInitializationAudit.event_key == INITIALIZATION_EVENT_KEY
        )
    )
    serialized_audit = _serialize_audit(audit) if audit is not None else None
    snapshot_payload = {
        "iterations": [
            {
                "iteration_key": iteration["iteration_key"],
                "revision": iteration["revision"],
                "revision_digest": iteration["revision_digest"],
                "seed_managed": iteration["seed_managed"],
                "revisions": [
                    {
                        "revision": revision["revision"],
                        "revision_digest": revision["revision_digest"],
                        "previous_revision_digest": revision["previous_revision_digest"],
                        "seed_managed": revision["seed_managed"],
                    }
                    for revision in iteration["revisions"]
                ],
            }
            for iteration in iterations
        ],
        "initialization_audit": (
            {"event_key": serialized_audit["event_key"], "event_digest": serialized_audit["event_digest"]}
            if serialized_audit
            else None
        ),
    }
    initialized = bool(iterations or serialized_audit)
    return {
        **preview,
        "read_only": False,
        "initialized": initialized,
        "persistent_snapshot_digest": canonical_digest(snapshot_payload) if initialized else None,
        "instruction_evidence": serialized_audit["instruction_evidence"] if serialized_audit else instruction_evidence(),
        "governance": governance(),
        "iterations": iterations,
        "initialization_audit": serialized_audit,
    }


def _audit_definition() -> dict[str, Any]:
    payload = {
        "event_key": INITIALIZATION_EVENT_KEY,
        "project_scope": PROJECT_SCOPE,
        "event_type": "explicit_user_instruction_iteration_program_initialization",
        "instruction_evidence": instruction_evidence(),
        "iteration_program_digest": program_digest(),
        "iteration_keys": [definition["iteration_key"] for definition in iteration_definitions()],
        "can_auto_accept": False,
        "can_auto_execute": False,
        "can_auto_approve_release": False,
        "release_gate_mutated": False,
    }
    return {**payload, "event_digest": canonical_digest(payload)}


def initialize_iteration_program(db: Session) -> dict[str, Any]:
    """Explicitly materialize the fifteen-version plan; never authorizes execution.

    Existing human-owned rows and revisions are preserved.  The initializer has
    no network request, no Office/visual processing, no action runner and no
    release-readiness mutation.
    """

    outcome = {
        "iterations": {"created": 0, "existing_seed_managed": 0, "preserved_human": 0},
        "revisions": {"created": 0, "existing": 0, "preserved_human": 0},
        "initialization_audit": {"created": 0, "existing": 0},
    }
    try:
        for definition in iteration_definitions():
            row = db.scalar(
                select(ProductStrategyIteration).where(
                    ProductStrategyIteration.iteration_key == definition["iteration_key"]
                )
            )
            if row is None:
                row = ProductStrategyIteration(
                    iteration_key=definition["iteration_key"],
                    **_row_fields(definition),
                    seed_managed=True,
                )
                db.add(row)
                db.flush()
                outcome["iterations"]["created"] += 1
            elif row.seed_managed:
                outcome["iterations"]["existing_seed_managed"] += 1
            else:
                outcome["iterations"]["preserved_human"] += 1

            revision = db.scalar(
                select(ProductStrategyIterationRevision).where(
                    ProductStrategyIterationRevision.iteration_id == row.id,
                    ProductStrategyIterationRevision.revision == 1,
                )
            )
            if revision is None:
                revision = ProductStrategyIterationRevision(
                    iteration_id=row.id,
                    iteration_key=row.iteration_key,
                    revision=1,
                    previous_revision_digest=None,
                    revision_digest=row.revision_digest,
                    event_type="iteration_program_initialized",
                    snapshot_payload=_snapshot(definition),
                    field_level_diff_payload=_initial_diff(definition),
                    is_immutable=True,
                    seed_managed=True,
                )
                db.add(revision)
                outcome["revisions"]["created"] += 1
            elif revision.seed_managed:
                outcome["revisions"]["existing"] += 1
            else:
                outcome["revisions"]["preserved_human"] += 1

        audit_definition = _audit_definition()
        audit = db.scalar(
            select(ProductStrategyIterationInitializationAudit).where(
                ProductStrategyIterationInitializationAudit.event_key == INITIALIZATION_EVENT_KEY
            )
        )
        if audit is None:
            db.add(
                ProductStrategyIterationInitializationAudit(
                    event_key=audit_definition["event_key"],
                    project_scope=audit_definition["project_scope"],
                    event_type=audit_definition["event_type"],
                    instruction_evidence_payload=deepcopy(audit_definition["instruction_evidence"]),
                    iteration_program_digest=audit_definition["iteration_program_digest"],
                    iteration_keys_payload=list(audit_definition["iteration_keys"]),
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

    result = get_persisted_iteration_program(db)
    result["initialization"] = outcome
    return result
