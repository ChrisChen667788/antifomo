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
    ResearchExperimentGateConfigOut,
    ResearchExperimentOrchestrationOut,
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
        last_gate_evaluated_at=plan.last_gate_evaluated_at,
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


def build_research_experiment_orchestration(db: Session) -> ResearchExperimentOrchestrationOut:
    plans = [ResearchExperimentPlanOut(**item) for item in list_research_experiment_plans(db)]
    frozen_count = sum(1 for plan in plans if plan.cohort_frozen_at is not None)
    locked_count = sum(1 for plan in plans if plan.baseline_locked_at is not None)
    allowed_count = sum(1 for plan in plans if plan.latest_gate and plan.latest_gate.decision == "allow")
    blocked_count = sum(1 for plan in plans if plan.latest_gate and plan.latest_gate.decision == "block")
    hold_count = sum(1 for plan in plans if plan.latest_gate and plan.latest_gate.decision == "hold")
    summary_lines = [
        f"实验计划 {len(plans)} 个，已冻结 cohort {frozen_count} 个，已锁定 baseline {locked_count} 个。",
        f"最近 gate 判定：允许 {allowed_count} 个，阻塞 {blocked_count} 个，待观察 {hold_count} 个。",
    ]
    return ResearchExperimentOrchestrationOut(
        generated_at=_utc_now(),
        total_plans=len(plans),
        frozen_plan_count=frozen_count,
        locked_plan_count=locked_count,
        allowed_plan_count=allowed_count,
        blocked_plan_count=blocked_count,
        hold_plan_count=hold_count,
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
    plan.last_gate_evaluated_at = None
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
    plan.last_gate_evaluated_at = evaluated_at
    plan.status = {
        "allow": "gate_allowed",
        "hold": "gate_hold",
        "block": "gate_blocked",
    }[decision]
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return _serialize_plan(plan)
