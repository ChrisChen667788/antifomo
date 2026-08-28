from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.decision_program_entities import DecisionResearchRun
from app.models.decision_studio_entities import DecisionSource
from app.services.decision_program.common import audit_event, canonical_digest, iso, utc_now


TRANSITIONS = {
    "approve": {"draft"},
    "start": {"approved"},
    "pause": {"running"},
    "resume": {"paused"},
    "checkpoint": {"running"},
    "complete": {"running"},
    "cancel": {"draft", "approved", "running", "paused"},
}


def _plan_payload(
    *,
    brief: dict[str, Any],
    question_tree: list[dict[str, Any]],
    source_decisions: list[dict[str, Any]],
    budget_fen: int,
) -> dict[str, Any]:
    return {
        "brief": brief,
        "question_tree": question_tree,
        "source_decisions": source_decisions,
        "budget_fen": budget_fen,
    }


def create_research_run(
    db: Session,
    *,
    user_id: UUID,
    actor_id: str,
    notebook_id: UUID,
    run_key: str,
    title: str,
    brief: dict[str, Any],
    question_tree: list[dict[str, Any]],
    source_decisions: list[dict[str, Any]],
    budget_fen: int,
) -> DecisionResearchRun:
    if not question_tree:
        raise ValueError("A research run requires an explicit question tree.")
    normalized_key = run_key.strip()
    existing = db.scalar(
        select(DecisionResearchRun)
        .where(DecisionResearchRun.user_id == user_id)
        .where(DecisionResearchRun.run_key == normalized_key)
    )
    payload = _plan_payload(
        brief=brief,
        question_tree=question_tree,
        source_decisions=source_decisions,
        budget_fen=budget_fen,
    )
    plan_hash = canonical_digest(payload)
    if existing is not None:
        if existing.plan_hash != plan_hash or existing.notebook_id != notebook_id:
            raise ValueError("Immutable research run_key already exists with a different plan.")
        return existing
    run = DecisionResearchRun(
        user_id=user_id,
        notebook_id=notebook_id,
        run_key=normalized_key,
        title=title.strip(),
        status="draft",
        brief_payload=brief,
        question_tree_payload=question_tree,
        source_decisions_payload=source_decisions,
        plan_hash=plan_hash,
        budget_fen=budget_fen,
        audit_payload=[audit_event(action="created", actor_id=actor_id, details={"plan_hash": plan_hash})],
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def revise_research_run_plan(
    db: Session,
    *,
    run: DecisionResearchRun,
    actor_id: str,
    expected_plan_hash: str,
    title: str,
    brief: dict[str, Any],
    question_tree: list[dict[str, Any]],
    source_decisions: list[dict[str, Any]],
    budget_fen: int,
) -> DecisionResearchRun:
    if run.status != "draft":
        raise ValueError("Only a draft research plan can be revised.")
    if run.plan_hash != expected_plan_hash:
        raise ValueError("Research plan changed since it was loaded.")
    if not question_tree:
        raise ValueError("A research run requires an explicit question tree.")
    payload = _plan_payload(
        brief=brief,
        question_tree=question_tree,
        source_decisions=source_decisions,
        budget_fen=budget_fen,
    )
    previous_hash = run.plan_hash
    run.title = title.strip()
    run.brief_payload = brief
    run.question_tree_payload = question_tree
    run.source_decisions_payload = source_decisions
    run.budget_fen = budget_fen
    run.plan_hash = canonical_digest(payload)
    audit = list(run.audit_payload or [])
    audit.append(
        audit_event(
            action="plan_revised",
            actor_id=actor_id,
            details={"previous_plan_hash": previous_hash, "plan_hash": run.plan_hash},
        )
    )
    run.audit_payload = audit
    db.commit()
    db.refresh(run)
    return run


def _snapshot_sources(db: Session, *, notebook_id: UUID) -> list[dict[str, Any]]:
    sources = list(
        db.scalars(
            select(DecisionSource)
            .where(DecisionSource.notebook_id == notebook_id)
            .where(DecisionSource.admission_status == "accepted")
            .order_by(DecisionSource.created_at, DecisionSource.id)
        ).all()
    )
    return [
        {
            "source_id": str(source.id),
            "revision_id": str(source.current_revision_id) if source.current_revision_id else None,
            "trust_status": source.trust_status,
            "title": source.title,
        }
        for source in sources
    ]


def transition_research_run(
    db: Session,
    *,
    run: DecisionResearchRun,
    actor_id: str,
    action: str,
    expected_plan_hash: str = "",
    spend_fen: int = 0,
    checkpoint: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
) -> DecisionResearchRun:
    allowed = TRANSITIONS.get(action)
    if allowed is None or run.status not in allowed:
        raise ValueError(f"Research run action {action} is not allowed from {run.status}.")
    if expected_plan_hash and expected_plan_hash != run.plan_hash:
        raise ValueError("Research plan changed since it was reviewed.")
    if run.spent_fen + spend_fen > run.budget_fen and run.budget_fen > 0:
        raise ValueError("Research run budget would be exceeded.")
    now = utc_now()
    if action == "approve":
        run.status = "approved"
        run.approved_at = now
        run.source_snapshot_payload = _snapshot_sources(db, notebook_id=run.notebook_id)
    elif action == "start":
        if not run.source_snapshot_payload:
            raise ValueError("Approved research run has no frozen source snapshot.")
        run.status = "running"
        run.started_at = now
    elif action == "pause":
        run.status = "paused"
    elif action == "resume":
        run.status = "running"
    elif action == "checkpoint":
        run.checkpoint_payload = checkpoint or {}
    elif action == "complete":
        if not result:
            raise ValueError("Completing a research run requires an explicit result payload.")
        run.status = "completed"
        run.result_payload = result
        run.checkpoint_payload = checkpoint or run.checkpoint_payload
        run.completed_at = now
    elif action == "cancel":
        run.status = "cancelled"
        run.completed_at = now
    run.spent_fen += spend_fen
    events = list(run.audit_payload or [])
    events.append(
        audit_event(
            action=action,
            actor_id=actor_id,
            details={"spend_fen": spend_fen, "status": run.status, "checkpoint_digest": canonical_digest(checkpoint or {})},
        )
    )
    run.audit_payload = events
    db.commit()
    db.refresh(run)
    return run


def serialize_research_run(run: DecisionResearchRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "user_id": str(run.user_id),
        "notebook_id": str(run.notebook_id),
        "run_key": run.run_key,
        "title": run.title,
        "status": run.status,
        "brief": dict(run.brief_payload or {}),
        "question_tree": list(run.question_tree_payload or []),
        "source_decisions": list(run.source_decisions_payload or []),
        "source_snapshot": list(run.source_snapshot_payload or []),
        "checkpoint": dict(run.checkpoint_payload or {}),
        "result": dict(run.result_payload or {}),
        "plan_hash": run.plan_hash,
        "budget_fen": run.budget_fen,
        "spent_fen": run.spent_fen,
        "audit": list(run.audit_payload or []),
        "approved_at": iso(run.approved_at),
        "started_at": iso(run.started_at),
        "completed_at": iso(run.completed_at),
        "created_at": iso(run.created_at),
        "updated_at": iso(run.updated_at),
    }


def compare_research_runs(left: DecisionResearchRun, right: DecisionResearchRun) -> dict[str, Any]:
    left_result = dict(left.result_payload or {})
    right_result = dict(right.result_payload or {})
    keys = sorted(set(left_result) | set(right_result))
    changed = [key for key in keys if left_result.get(key) != right_result.get(key)]
    return {
        "left_run_id": str(left.id),
        "right_run_id": str(right.id),
        "same_notebook": left.notebook_id == right.notebook_id,
        "plan_hash_changed": left.plan_hash != right.plan_hash,
        "source_snapshot_changed": canonical_digest(left.source_snapshot_payload) != canonical_digest(right.source_snapshot_payload),
        "changed_result_keys": changed,
        "cost_delta_fen": right.spent_fen - left.spent_fen,
        "left_status": left.status,
        "right_status": right.status,
    }
