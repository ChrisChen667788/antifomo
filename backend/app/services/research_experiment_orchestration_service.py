from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import KnowledgeEntry
from app.models.research_entities import ResearchExperimentPlan
from app.schemas.research import (
    ResearchExperimentActivePolicyOut,
    ResearchExperimentGateConfigOut,
    ResearchExperimentOrchestrationOut,
    ResearchExperimentRolloutActionRequest,
    ResearchExperimentRolloutManifestOut,
    ResearchExperimentPlanCreateRequest,
    ResearchExperimentPlanOut,
    ResearchExperimentRolloutGateOut,
)
from app.services.content_extractor import normalize_text
from app.services.research_evaluation_service import (
    build_research_experiment_lane,
    list_research_experiment_entry_ids,
)


settings = get_settings()
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@lru_cache(maxsize=1)
def _project_version_label() -> str:
    try:
        payload = json.loads((PROJECT_ROOT / "package.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "local-dev"
    version = normalize_text(str(payload.get("version") or ""))
    return version or "local-dev"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any, *, limit: int = 2000) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        normalized = normalize_text(str(item or ""))
        if normalized and normalized not in items:
            items.append(normalized)
        if len(items) >= limit:
            break
    return items


def _gate_config_from_payload(payload: Any) -> ResearchExperimentGateConfigOut:
    data = _dict(payload)
    try:
        return ResearchExperimentGateConfigOut.model_validate(data)
    except Exception:
        return ResearchExperimentGateConfigOut()


def _lane_from_payload(payload: Any):
    data = _dict(payload)
    if not data:
        return None
    try:
        from app.schemas.research import ResearchExperimentLaneOut

        return ResearchExperimentLaneOut.model_validate(data)
    except Exception:
        return None


def _gate_from_payload(payload: Any) -> ResearchExperimentRolloutGateOut | None:
    data = _dict(payload)
    if not data:
        return None
    try:
        return ResearchExperimentRolloutGateOut.model_validate(data)
    except Exception:
        return None


def _gate_history_from_payload(payload: Any) -> list[ResearchExperimentRolloutGateOut]:
    if not isinstance(payload, list):
        return []
    gates: list[ResearchExperimentRolloutGateOut] = []
    for item in payload:
        gate = _gate_from_payload(item)
        if gate is not None:
            gates.append(gate)
    return gates


def _rollout_manifest_from_payload(payload: Any) -> ResearchExperimentRolloutManifestOut | None:
    data = _dict(payload)
    if not data:
        return None
    try:
        return ResearchExperimentRolloutManifestOut.model_validate(data)
    except Exception:
        return None


def _parse_plan_id(plan_id: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(plan_id))
    except ValueError:
        return None


def _get_plan_model(db: Session, plan_id: str) -> ResearchExperimentPlan | None:
    parsed = _parse_plan_id(plan_id)
    if parsed is None:
        return None
    return db.scalar(
        select(ResearchExperimentPlan)
        .where(ResearchExperimentPlan.id == parsed)
        .where(ResearchExperimentPlan.user_id == settings.single_user_id)
    )


def _serialize_plan(plan: ResearchExperimentPlan) -> dict[str, Any]:
    cohort_payload = _dict(plan.cohort_payload)
    baseline_payload = _dict(plan.baseline_payload)
    latest_gate_payload = _dict(plan.latest_gate_payload)
    gate_config = _gate_config_from_payload(plan.gate_config_payload)
    baseline_lane = _lane_from_payload(baseline_payload.get("lane_snapshot"))
    latest_gate = _gate_from_payload(latest_gate_payload)
    gate_history = _gate_history_from_payload(plan.gate_history_payload)
    rollout_manifest = _rollout_manifest_from_payload(plan.rollout_payload)
    return ResearchExperimentPlanOut(
        id=str(plan.id),
        name=plan.name,
        lane_key=plan.lane_key,  # type: ignore[arg-type]
        strategy_family=plan.strategy_family,  # type: ignore[arg-type]
        candidate_label=plan.candidate_label,
        notes=plan.notes,
        strategy_payload=_dict(plan.strategy_payload),
        gate_config=gate_config,
        status=plan.status,  # type: ignore[arg-type]
        cohort_size=int(cohort_payload.get("sample_size") or len(_string_list(cohort_payload.get("entry_ids")))),
        cohort_entry_ids=_string_list(cohort_payload.get("entry_ids")),
        cohort_preview_titles=_string_list(cohort_payload.get("preview_titles"), limit=8),
        cohort_frozen_at=plan.cohort_frozen_at,
        baseline_version_label=normalize_text(str(baseline_payload.get("version_label") or "")),
        baseline_lane=baseline_lane,
        baseline_locked_at=plan.baseline_locked_at,
        latest_gate=latest_gate,
        gate_history=gate_history[-8:],
        gate_history_count=len(gate_history),
        rollout_manifest=rollout_manifest,
        last_gate_evaluated_at=plan.last_gate_evaluated_at,
        promoted_at=plan.promoted_at,
        rollout_revoked_at=plan.rollout_revoked_at,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    ).model_dump(mode="python")


def list_research_experiment_plans(db: Session) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(ResearchExperimentPlan)
        .where(ResearchExperimentPlan.user_id == settings.single_user_id)
        .order_by(desc(ResearchExperimentPlan.updated_at), desc(ResearchExperimentPlan.created_at))
    ).all()
    return [_serialize_plan(row) for row in rows]


def _active_policies_from_plans(
    plans: list[ResearchExperimentPlanOut],
) -> list[ResearchExperimentActivePolicyOut]:
    active_by_lane: dict[str, list[ResearchExperimentPlanOut]] = {}
    for plan in plans:
        manifest = plan.rollout_manifest
        if manifest is None or manifest.decision != "promoted" or manifest.revoked_at is not None:
            continue
        active_by_lane.setdefault(plan.lane_key, []).append(plan)

    active_policies: list[ResearchExperimentActivePolicyOut] = []
    for lane_key, lane_plans in active_by_lane.items():
        sorted_plans = sorted(
            lane_plans,
            key=lambda item: item.promoted_at or item.created_at,
            reverse=True,
        )
        active_plan = sorted_plans[0]
        manifest = active_plan.rollout_manifest
        if manifest is None:
            continue
        active_policies.append(
            ResearchExperimentActivePolicyOut(
                lane_key=lane_key,  # type: ignore[arg-type]
                plan_id=active_plan.id,
                plan_name=active_plan.name,
                strategy_family=active_plan.strategy_family,
                candidate_label=active_plan.candidate_label,
                promoted_version_label=manifest.promoted_version_label,
                baseline_version_label=manifest.baseline_version_label,
                candidate_percent=manifest.candidate_percent,
                observed_uplift_points=manifest.observed_uplift_points,
                sample_size=manifest.sample_size,
                promoted_at=manifest.promoted_at,
                gate_evaluated_at=manifest.gate_evaluated_at,
                activation_payload=manifest.activation_payload,
                conflict_plan_ids=[plan.id for plan in sorted_plans[1:]],
            )
        )
    return sorted(active_policies, key=lambda item: item.lane_key)


def list_research_experiment_active_policies(db: Session) -> list[ResearchExperimentActivePolicyOut]:
    plans = [ResearchExperimentPlanOut(**item) for item in list_research_experiment_plans(db)]
    return _active_policies_from_plans(plans)


def build_research_experiment_orchestration(db: Session) -> ResearchExperimentOrchestrationOut:
    plans = [ResearchExperimentPlanOut(**item) for item in list_research_experiment_plans(db)]
    frozen_count = sum(1 for plan in plans if plan.cohort_frozen_at is not None)
    locked_count = sum(1 for plan in plans if plan.baseline_locked_at is not None)
    allowed_count = sum(1 for plan in plans if plan.latest_gate and plan.latest_gate.decision == "allow")
    blocked_count = sum(1 for plan in plans if plan.latest_gate and plan.latest_gate.decision == "block")
    hold_count = sum(1 for plan in plans if plan.latest_gate and plan.latest_gate.decision == "hold")
    promoted_count = sum(1 for plan in plans if plan.rollout_manifest and plan.rollout_manifest.decision == "promoted")
    revoked_count = sum(1 for plan in plans if plan.rollout_manifest and plan.rollout_manifest.decision == "revoked")
    active_policies = _active_policies_from_plans(plans)
    active_conflict_count = sum(len(policy.conflict_plan_ids) for policy in active_policies)
    summary_lines = [
        f"实验计划 {len(plans)} 个，已冻结 cohort {frozen_count} 个，已锁定 baseline {locked_count} 个。",
        f"最近 gate 判定：允许 {allowed_count} 个，阻塞 {blocked_count} 个，待观察 {hold_count} 个。",
        f"Rollout manifest：已确认 {promoted_count} 个，已撤回 {revoked_count} 个，当前生效策略 {len(active_policies)} 个。",
    ]
    if active_conflict_count:
        summary_lines.append(f"当前仍存在 {active_conflict_count} 个同 lane 生效冲突，需要撤回旧 manifest。")
    return ResearchExperimentOrchestrationOut(
        generated_at=_utc_now(),
        total_plans=len(plans),
        frozen_plan_count=frozen_count,
        locked_plan_count=locked_count,
        allowed_plan_count=allowed_count,
        blocked_plan_count=blocked_count,
        hold_plan_count=hold_count,
        promoted_plan_count=promoted_count,
        revoked_plan_count=revoked_count,
        active_policy_count=len(active_policies),
        active_policy_conflict_count=active_conflict_count,
        active_policies=active_policies,
        plans=plans,
        summary_lines=summary_lines,
    )


def create_research_experiment_plan(
    db: Session,
    payload: ResearchExperimentPlanCreateRequest,
) -> dict[str, Any]:
    plan = ResearchExperimentPlan(
        user_id=settings.single_user_id,
        name=payload.name,
        lane_key=payload.lane_key,
        strategy_family=payload.strategy_family,
        candidate_label=payload.candidate_label,
        notes=payload.notes,
        strategy_payload=payload.strategy_payload,
        gate_config_payload=payload.gate_config.model_dump(mode="json"),
        cohort_payload={},
        baseline_payload={},
        latest_gate_payload={},
        gate_history_payload=[],
        rollout_payload={},
        status="draft",
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return _serialize_plan(plan)


def freeze_research_experiment_cohort(
    db: Session,
    plan_id: str,
) -> dict[str, Any]:
    plan = _get_plan_model(db, plan_id)
    if plan is None:
        raise LookupError("Experiment plan not found")
    if plan.baseline_locked_at is not None:
        raise ValueError("Baseline already locked; cohort can no longer be replaced")

    entry_ids = list_research_experiment_entry_ids(db, plan.lane_key)
    parsed_ids: list[uuid.UUID] = []
    for entry_id in entry_ids:
        parsed = _parse_plan_id(entry_id)
        if parsed is not None:
            parsed_ids.append(parsed)
    title_rows = []
    if parsed_ids:
        title_rows = db.scalars(
            select(KnowledgeEntry)
            .where(KnowledgeEntry.user_id == settings.single_user_id)
            .where(KnowledgeEntry.id.in_(parsed_ids))
            .order_by(desc(KnowledgeEntry.updated_at), desc(KnowledgeEntry.created_at))
        ).all()
    preview_titles = [
        normalize_text(row.title or "") or str(row.id)
        for row in title_rows[:8]
    ]
    frozen_at = _utc_now()
    plan.cohort_payload = {
        "entry_ids": entry_ids,
        "sample_size": len(entry_ids),
        "preview_titles": preview_titles,
        "frozen_at": frozen_at.isoformat(),
        "lane_key": plan.lane_key,
    }
    plan.cohort_frozen_at = frozen_at
    plan.status = "cohort_frozen"
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return _serialize_plan(plan)


def lock_research_experiment_baseline(
    db: Session,
    plan_id: str,
) -> dict[str, Any]:
    plan = _get_plan_model(db, plan_id)
    if plan is None:
        raise LookupError("Experiment plan not found")
    cohort_payload = _dict(plan.cohort_payload)
    entry_ids = set(_string_list(cohort_payload.get("entry_ids")))
    if not entry_ids:
        raise ValueError("Freeze cohort before locking baseline")
    if plan.promoted_at is not None and plan.rollout_revoked_at is None:
        raise ValueError("Rollout already promoted; revoke it before relocking baseline")

    lane = build_research_experiment_lane(db, plan.lane_key, entry_ids=entry_ids)
    locked_at = _utc_now()
    plan.baseline_payload = {
        "version_label": _project_version_label(),
        "locked_at": locked_at.isoformat(),
        "lane_snapshot": lane.model_dump(mode="json"),
        "baseline_percent": lane.baseline.percent,
        "candidate_percent_at_lock": lane.candidate.percent,
    }
    plan.baseline_locked_at = locked_at
    plan.latest_gate_payload = {}
    plan.gate_history_payload = []
    plan.rollout_payload = {}
    plan.last_gate_evaluated_at = None
    plan.promoted_at = None
    plan.rollout_revoked_at = None
    plan.status = "baseline_locked"
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return _serialize_plan(plan)


def evaluate_research_experiment_rollout_gate(
    db: Session,
    plan_id: str,
) -> dict[str, Any]:
    plan = _get_plan_model(db, plan_id)
    if plan is None:
        raise LookupError("Experiment plan not found")

    cohort_payload = _dict(plan.cohort_payload)
    baseline_payload = _dict(plan.baseline_payload)
    entry_ids = set(_string_list(cohort_payload.get("entry_ids")))
    baseline_lane = _lane_from_payload(baseline_payload.get("lane_snapshot"))
    if not entry_ids or baseline_lane is None:
        raise ValueError("Freeze cohort and lock baseline before evaluating rollout gate")

    gate_config = _gate_config_from_payload(plan.gate_config_payload)
    current_lane = build_research_experiment_lane(db, plan.lane_key, entry_ids=entry_ids)
    locked_baseline_percent = baseline_lane.baseline.percent
    candidate_percent = current_lane.candidate.percent
    observed_uplift = candidate_percent - locked_baseline_percent
    sample_size = current_lane.candidate.denominator
    reasons: list[str] = []

    if current_lane.status == "insufficient":
        reasons.append("当前 lane 仍缺少可比较候选样本。")
    if sample_size < gate_config.minimum_sample_size:
        reasons.append(
            f"候选样本 {sample_size} 小于 rollout gate 要求的 {gate_config.minimum_sample_size}。"
        )
    if observed_uplift < gate_config.minimum_uplift_points:
        reasons.append(
            f"候选提升 {observed_uplift} pt，低于阈值 {gate_config.minimum_uplift_points} pt。"
        )

    if current_lane.status == "insufficient" or sample_size < gate_config.minimum_sample_size:
        decision = "hold"
    elif observed_uplift < gate_config.minimum_uplift_points:
        decision = "block"
    else:
        decision = "allow"
        reasons.append("候选样本量与 uplift 均达到 rollout gate。")

    evaluated_at = _utc_now()
    gate = ResearchExperimentRolloutGateOut(
        decision=decision,  # type: ignore[arg-type]
        lane_key=plan.lane_key,  # type: ignore[arg-type]
        baseline_version_label=normalize_text(str(baseline_payload.get("version_label") or "")),
        locked_baseline_percent=locked_baseline_percent,
        candidate_percent=candidate_percent,
        observed_uplift_points=observed_uplift,
        required_uplift_points=gate_config.minimum_uplift_points,
        sample_size=sample_size,
        minimum_sample_size=gate_config.minimum_sample_size,
        reasons=reasons,
        evaluated_at=evaluated_at,
        current_lane=current_lane,
    )
    plan.latest_gate_payload = gate.model_dump(mode="json")
    gate_history = [
        item.model_dump(mode="json")
        for item in _gate_history_from_payload(plan.gate_history_payload)
    ]
    gate_history.append(gate.model_dump(mode="json"))
    plan.gate_history_payload = gate_history[-30:]
    plan.last_gate_evaluated_at = evaluated_at
    if plan.promoted_at is not None and plan.rollout_revoked_at is None:
        plan.status = "rollout_promoted"
    elif plan.rollout_revoked_at is not None:
        plan.status = "rollout_revoked"
    else:
        plan.status = {
            "allow": "gate_allowed",
            "hold": "gate_hold",
            "block": "gate_blocked",
        }[decision]
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return _serialize_plan(plan)


def promote_research_experiment_rollout(
    db: Session,
    plan_id: str,
    payload: ResearchExperimentRolloutActionRequest,
) -> dict[str, Any]:
    plan = _get_plan_model(db, plan_id)
    if plan is None:
        raise LookupError("Experiment plan not found")
    latest_gate = _gate_from_payload(plan.latest_gate_payload)
    if latest_gate is None:
        raise ValueError("Evaluate rollout gate before promoting a strategy")
    if latest_gate.decision != "allow":
        raise ValueError("Only allowed rollout gates can be promoted")

    baseline_payload = _dict(plan.baseline_payload)
    gate_config = _gate_config_from_payload(plan.gate_config_payload)
    promoted_at = _utc_now()
    superseded_plan_ids: list[str] = []
    active_peer_rows = db.scalars(
        select(ResearchExperimentPlan)
        .where(ResearchExperimentPlan.user_id == settings.single_user_id)
        .where(ResearchExperimentPlan.lane_key == plan.lane_key)
        .where(ResearchExperimentPlan.id != plan.id)
        .where(ResearchExperimentPlan.promoted_at.is_not(None))
        .where(ResearchExperimentPlan.rollout_revoked_at.is_(None))
    ).all()
    for peer in active_peer_rows:
        peer_manifest = _rollout_manifest_from_payload(peer.rollout_payload)
        if peer_manifest is None or peer_manifest.decision != "promoted":
            continue
        superseded_plan_ids.append(str(peer.id))
        revoked_manifest = peer_manifest.model_copy(
            update={
                "decision": "revoked",
                "note": f"Superseded by {plan.name} ({plan.id}).",
                "revoked_at": promoted_at,
            }
        )
        peer.rollout_payload = revoked_manifest.model_dump(mode="json")
        peer.rollout_revoked_at = promoted_at
        peer.status = "rollout_revoked"
        db.add(peer)
    manifest = ResearchExperimentRolloutManifestOut(
        decision="promoted",
        plan_id=str(plan.id),
        plan_name=plan.name,
        lane_key=plan.lane_key,  # type: ignore[arg-type]
        strategy_family=plan.strategy_family,  # type: ignore[arg-type]
        candidate_label=plan.candidate_label,
        baseline_version_label=normalize_text(str(baseline_payload.get("version_label") or "")),
        promoted_version_label=_project_version_label(),
        gate_evaluated_at=latest_gate.evaluated_at,
        locked_baseline_percent=latest_gate.locked_baseline_percent,
        candidate_percent=latest_gate.candidate_percent,
        observed_uplift_points=latest_gate.observed_uplift_points,
        sample_size=latest_gate.sample_size,
        note=payload.note,
        activation_payload={
            "lane_key": plan.lane_key,
            "strategy_family": plan.strategy_family,
            "candidate_label": plan.candidate_label,
            "superseded_plan_ids": superseded_plan_ids,
            "strategy_payload": _dict(plan.strategy_payload),
            "gate_config": gate_config.model_dump(mode="json"),
            "baseline": {
                "version_label": normalize_text(str(baseline_payload.get("version_label") or "")),
                "baseline_percent": latest_gate.locked_baseline_percent,
            },
            "rollout_gate": latest_gate.model_dump(mode="json"),
        },
        promoted_at=promoted_at,
        revoked_at=None,
    )
    plan.rollout_payload = manifest.model_dump(mode="json")
    plan.promoted_at = promoted_at
    plan.rollout_revoked_at = None
    plan.status = "rollout_promoted"
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return _serialize_plan(plan)


def revoke_research_experiment_rollout(
    db: Session,
    plan_id: str,
    payload: ResearchExperimentRolloutActionRequest,
) -> dict[str, Any]:
    plan = _get_plan_model(db, plan_id)
    if plan is None:
        raise LookupError("Experiment plan not found")
    manifest = _rollout_manifest_from_payload(plan.rollout_payload)
    if plan.promoted_at is None or manifest is None:
        raise ValueError("No promoted rollout manifest exists for this experiment")

    revoked_at = _utc_now()
    revoked_manifest = manifest.model_copy(
        update={
            "decision": "revoked",
            "note": payload.note or manifest.note,
            "revoked_at": revoked_at,
        }
    )
    plan.rollout_payload = revoked_manifest.model_dump(mode="json")
    plan.rollout_revoked_at = revoked_at
    plan.status = "rollout_revoked"
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return _serialize_plan(plan)
