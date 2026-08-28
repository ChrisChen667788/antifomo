from __future__ import annotations

from datetime import UTC
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.decision_program_entities import DecisionAgentApproval, DecisionAgentRun
from app.models.decision_studio_entities import GovernedSkill
from app.services.decision_program.common import audit_event, canonical_digest, iso, utc_now
from app.services.decision_studio.skills import FORBIDDEN_PERMISSIONS, execute_skill, serialize_skill_run


HIGH_RISK_ACTIONS = {"write", "export", "network", "delete", "external_publish"}
SEPARATION_REQUIRED_ACTIONS = {"network", "delete", "external_publish"}


def _permission_findings(skill: GovernedSkill, requested: list[str], granted: list[str]) -> list[str]:
    declared = {str(value) for value in skill.permissions_payload or []}
    granted_set = set(granted)
    findings: list[str] = []
    for permission in requested:
        if permission not in declared:
            findings.append(f"Undeclared permission requested: {permission}")
        if permission not in granted_set:
            findings.append(f"Permission not granted: {permission}")
        if permission in FORBIDDEN_PERMISSIONS or permission.startswith("shell:"):
            findings.append(f"Forbidden permission requested: {permission}")
    return list(dict.fromkeys(findings))


def create_agent_run(
    db: Session,
    *,
    skill: GovernedSkill,
    notebook_id: UUID | None,
    actor_id: str,
    idempotency_key: str,
    plan: dict[str, Any],
    requested_permissions: list[str],
    granted_permissions: list[str],
    budget_fen: int,
    scheduled_for,
) -> DecisionAgentRun:
    plan_digest = canonical_digest(plan)
    existing = db.scalar(
        select(DecisionAgentRun)
        .where(DecisionAgentRun.actor_id == actor_id)
        .where(DecisionAgentRun.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if str((existing.effect_preview_payload or {}).get("plan_digest") or "") != plan_digest:
            raise ValueError("Agent idempotency key already exists with a different plan.")
        return existing
    if skill.status != "approved":
        raise ValueError("Only approved and benchmarked Skills can be scheduled.")
    findings = _permission_findings(skill, requested_permissions, granted_permissions)
    if findings:
        raise ValueError("; ".join(findings))
    steps = [dict(value) for value in plan.get("steps") or []]
    step_keys = [str(value.get("step_key") or "").strip() for value in steps]
    if any(not value for value in step_keys) or len(step_keys) != len(set(step_keys)):
        raise ValueError("Agent plan steps require unique non-empty step_key values.")
    estimated_cost = sum(max(0, int(value.get("estimated_cost_fen") or 0)) for value in steps)
    if budget_fen and estimated_cost > budget_fen:
        raise ValueError("Agent plan estimate exceeds its budget.")
    high_risk = [
        {"step_key": step["step_key"], "action_class": str(step.get("action_class") or "read")}
        for step in steps
        if str(step.get("action_class") or "read") in HIGH_RISK_ACTIONS
    ]
    row = DecisionAgentRun(
        skill_id=skill.id,
        notebook_id=notebook_id,
        actor_id=actor_id,
        idempotency_key=idempotency_key,
        status="planned",
        plan_payload={**plan, "steps": steps},
        budget_fen=budget_fen,
        requested_permissions=requested_permissions,
        granted_permissions=granted_permissions,
        effect_preview_payload={
            "plan_digest": plan_digest,
            "step_count": len(steps),
            "estimated_cost_fen": estimated_cost,
            "high_risk_steps": high_risk,
            "external_effects_executed": False,
        },
        audit_payload=[audit_event(action="planned", actor_id=actor_id, details={"plan_digest": plan_digest})],
        scheduled_for=scheduled_for,
    )
    db.add(row)
    db.flush()
    now = utc_now()
    for step in steps:
        action_class = str(step.get("action_class") or "read")
        if action_class not in HIGH_RISK_ACTIONS:
            continue
        db.add(
            DecisionAgentApproval(
                run_id=row.id,
                step_key=str(step["step_key"]),
                action_class=action_class,
                status="pending",
                requested_by=actor_id,
                input_digest=canonical_digest(step),
                requested_at=now,
            )
        )
    db.commit()
    db.refresh(row)
    return row


def decide_agent_approval(
    db: Session,
    *,
    approval: DecisionAgentApproval,
    reviewer_id: str,
    decision: str,
    note: str,
) -> DecisionAgentApproval:
    if approval.status != "pending":
        raise ValueError("Agent approval has already been decided.")
    if approval.action_class in SEPARATION_REQUIRED_ACTIONS and reviewer_id == approval.requested_by:
        raise ValueError("This action class requires an independent reviewer.")
    approval.status = decision
    approval.reviewer_id = reviewer_id
    approval.decision_note = note.strip()
    approval.decided_at = utc_now()
    db.commit()
    db.refresh(approval)
    return approval


def _approval_for_step(db: Session, *, run_id: UUID, step_key: str) -> DecisionAgentApproval | None:
    return db.scalar(
        select(DecisionAgentApproval)
        .where(DecisionAgentApproval.run_id == run_id)
        .where(DecisionAgentApproval.step_key == step_key)
    )


def transition_agent_run(
    db: Session,
    *,
    run: DecisionAgentRun,
    skill: GovernedSkill,
    actor_id: str,
    action: str,
    spend_fen: int,
    step_result: dict[str, Any],
) -> DecisionAgentRun:
    now = utc_now()
    if action == "start":
        if run.status != "planned":
            raise ValueError("Only a planned Agent run can start.")
        scheduled_for = (
            run.scheduled_for.replace(tzinfo=UTC)
            if run.scheduled_for and run.scheduled_for.tzinfo is None
            else run.scheduled_for
        )
        if scheduled_for and scheduled_for > now:
            raise ValueError("Agent run is scheduled for a future time.")
        run.status = "running"
        run.started_at = now
    elif action == "pause":
        if run.status != "running":
            raise ValueError("Only a running Agent can pause.")
        run.status = "paused"
    elif action == "resume":
        if run.status != "paused":
            raise ValueError("Only a paused Agent can resume.")
        run.status = "running"
    elif action == "cancel":
        if run.status not in {"planned", "running", "paused"}:
            raise ValueError("Completed or cancelled Agent runs are immutable.")
        run.status = "cancelled"
        run.completed_at = now
    elif action == "rollback":
        if run.status not in {"completed", "blocked"}:
            raise ValueError("Only a completed or blocked Agent run can roll back.")
        if (run.effect_preview_payload or {}).get("external_effects_executed") is True:
            raise ValueError("External effects require an approved compensating action; automatic rollback is disabled.")
        run.status = "rolled_back"
        run.result_payload = {
            **dict(run.result_payload or {}),
            "rollback": {
                "status": "completed",
                "mode": "internal_checkpoint_only",
                "rolled_back_at": iso(now),
                "checkpoint_count": len(run.checkpoints_payload or []),
            },
        }
        run.completed_at = now
    elif action == "advance":
        if run.status != "running":
            raise ValueError("Only a running Agent can advance.")
        steps = [dict(value) for value in (run.plan_payload or {}).get("steps") or []]
        if run.current_step >= len(steps):
            raise ValueError("Agent run has no remaining step.")
        step = steps[run.current_step]
        step_key = str(step.get("step_key") or "")
        approval = _approval_for_step(db, run_id=run.id, step_key=step_key)
        if approval is not None and approval.status != "approved":
            raise ValueError(f"Step {step_key} requires an approved decision before execution.")
        projected = run.spent_fen + spend_fen
        if run.budget_fen and projected > run.budget_fen:
            raise ValueError("Agent run budget would be exceeded.")
        checkpoints = list(run.checkpoints_payload or [])
        checkpoints.append(
            {
                "step_key": step_key,
                "step_index": run.current_step,
                "action_class": str(step.get("action_class") or "read"),
                "input_digest": canonical_digest(step),
                "result": step_result,
                "result_digest": canonical_digest(step_result),
                "spend_fen": spend_fen,
                "completed_at": iso(now),
            }
        )
        run.checkpoints_payload = checkpoints
        run.current_step += 1
        run.spent_fen = projected
        if run.current_step == len(steps):
            governed_result: dict[str, Any] = {"status": "completed_without_notebook"}
            if run.notebook_id is not None:
                governed = execute_skill(
                    db,
                    skill=skill,
                    notebook_id=run.notebook_id,
                    actor_id=actor_id,
                    requested_permissions=list(run.requested_permissions or []),
                    granted_permissions=list(run.granted_permissions or []),
                )
                governed_result = serialize_skill_run(governed)
                if governed.status == "blocked":
                    run.status = "blocked"
                else:
                    run.status = "completed"
            else:
                run.status = "completed"
            run.result_payload = {
                "checkpoint_count": len(checkpoints),
                "governed_skill_run": governed_result,
                "external_effects_executed": False,
            }
            run.completed_at = now
    else:
        raise ValueError("Unsupported Agent run action.")
    audit = list(run.audit_payload or [])
    audit.append(audit_event(action=action, actor_id=actor_id, details={"status": run.status, "current_step": run.current_step}))
    run.audit_payload = audit
    db.commit()
    db.refresh(run)
    return run


def list_agent_approvals(db: Session, *, run_id: UUID) -> list[DecisionAgentApproval]:
    return list(
        db.scalars(
            select(DecisionAgentApproval)
            .where(DecisionAgentApproval.run_id == run_id)
            .order_by(DecisionAgentApproval.requested_at, DecisionAgentApproval.id)
        ).all()
    )


def serialize_agent_approval(row: DecisionAgentApproval) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "run_id": str(row.run_id),
        "step_key": row.step_key,
        "action_class": row.action_class,
        "status": row.status,
        "requested_by": row.requested_by,
        "reviewer_id": row.reviewer_id,
        "input_digest": row.input_digest,
        "decision_note": row.decision_note,
        "requested_at": iso(row.requested_at),
        "decided_at": iso(row.decided_at),
    }


def serialize_agent_run(row: DecisionAgentRun, *, approvals: list[DecisionAgentApproval] | None = None) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "skill_id": str(row.skill_id),
        "notebook_id": str(row.notebook_id) if row.notebook_id else None,
        "actor_id": row.actor_id,
        "idempotency_key": row.idempotency_key,
        "status": row.status,
        "plan": dict(row.plan_payload or {}),
        "checkpoints": list(row.checkpoints_payload or []),
        "current_step": row.current_step,
        "budget_fen": row.budget_fen,
        "spent_fen": row.spent_fen,
        "requested_permissions": list(row.requested_permissions or []),
        "granted_permissions": list(row.granted_permissions or []),
        "effect_preview": dict(row.effect_preview_payload or {}),
        "result": dict(row.result_payload or {}),
        "audit": list(row.audit_payload or []),
        "approvals": [serialize_agent_approval(value) for value in approvals or []],
        "scheduled_for": iso(row.scheduled_for),
        "started_at": iso(row.started_at),
        "completed_at": iso(row.completed_at),
    }
