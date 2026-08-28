from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.decision_program_entities import (
    DecisionAgentRun,
    DecisionConnectorSyncRun,
    DecisionCustomerPilot,
    DecisionDocumentDraft,
    DecisionQualityBenchmark,
    DecisionReleaseCandidate,
    DecisionResearchRun,
    DecisionVerticalPack,
    EnterpriseIdentityProfile,
)
from app.models.decision_studio_entities import DecisionNotebook, KnowledgeConnector, KnowledgeSpace
from app.services.decision_program.common import iso, utc_now


def _count(db: Session, model, *conditions) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0)


def _milestone(version: str, label: str, acceptance_status: str, evidence: dict[str, Any], blockers: list[str]) -> dict[str, Any]:
    return {
        "version": version,
        "label": label,
        "engineering_status": "implemented",
        "acceptance_status": acceptance_status,
        "evidence": evidence,
        "blockers": blockers,
    }


def build_decision_program_overview(db: Session, *, user_id: UUID) -> dict[str, Any]:
    notebook_ids = list(db.scalars(select(DecisionNotebook.id).where(DecisionNotebook.user_id == user_id)).all())
    space_ids = list(db.scalars(select(KnowledgeSpace.id).where(KnowledgeSpace.owner_user_id == user_id)).all())
    connector_ids = (
        list(db.scalars(select(KnowledgeConnector.id).where(KnowledgeConnector.space_id.in_(space_ids))).all())
        if space_ids
        else []
    )
    latest_candidate = db.scalar(
        select(DecisionReleaseCandidate)
        .where(DecisionReleaseCandidate.user_id == user_id)
        .order_by(DecisionReleaseCandidate.frozen_at.desc(), DecisionReleaseCandidate.id.desc())
    )
    release_pass = bool(latest_candidate and (latest_candidate.evidence_snapshot_payload or {}).get("acceptance_status") == "pass")
    completed_research = _count(db, DecisionResearchRun, DecisionResearchRun.user_id == user_id, DecisionResearchRun.status == "completed")
    retrieval_pass = _count(
        db,
        DecisionQualityBenchmark,
        DecisionQualityBenchmark.user_id == user_id,
        DecisionQualityBenchmark.benchmark_kind == "retrieval",
        DecisionQualityBenchmark.status == "pass",
    )
    parser_pass = _count(
        db,
        DecisionQualityBenchmark,
        DecisionQualityBenchmark.user_id == user_id,
        DecisionQualityBenchmark.benchmark_kind == "parser",
        DecisionQualityBenchmark.status == "pass",
    )
    draft_rows = (
        list(db.scalars(select(DecisionDocumentDraft).where(DecisionDocumentDraft.notebook_id.in_(notebook_ids))).all())
        if notebook_ids
        else []
    )
    valid_exports = sum(
        (row.last_export_payload or {}).get("status") == "pass"
        and ((row.last_export_payload or {}).get("manual_visual_confirmation") or {}).get("status") == "pass"
        for row in draft_rows
    )
    identity_ready = (
        _count(
            db,
            EnterpriseIdentityProfile,
            EnterpriseIdentityProfile.space_id.in_(space_ids),
            EnterpriseIdentityProfile.status == "ready",
        )
        if space_ids
        else 0
    )
    sync_applied = (
        _count(
            db,
            DecisionConnectorSyncRun,
            DecisionConnectorSyncRun.connector_id.in_(connector_ids),
            DecisionConnectorSyncRun.status == "applied",
        )
        if connector_ids
        else 0
    )
    agent_completed = _count(db, DecisionAgentRun, DecisionAgentRun.actor_id == str(user_id), DecisionAgentRun.status == "completed")
    active_packs = _count(db, DecisionVerticalPack, DecisionVerticalPack.status == "active")
    accepted_pilot_rows = (
        list(
            db.scalars(
                select(DecisionCustomerPilot)
                .where(DecisionCustomerPilot.space_id.in_(space_ids))
                .where(DecisionCustomerPilot.status == "accepted")
            ).all()
        )
        if space_ids
        else []
    )
    accepted_pilots = len(accepted_pilot_rows)
    accepted_sectors = sorted({row.sector for row in accepted_pilot_rows})
    pilot_ready = {"medical", "finance", "tourism"}.issubset(accepted_sectors)
    milestones = [
        _milestone(
            "2.0.7",
            "Release Evidence Closure",
            "pass" if release_pass else "blocked",
            {"latest_candidate_id": str(latest_candidate.id) if latest_candidate else None},
            [] if release_pass else ["冻结候选尚未绑定全部验证运行与真实外部验收 artifact。"],
        ),
        _milestone(
            "2.1.0",
            "Research Control Room",
            "pass" if completed_research else "blocked",
            {"completed_research_runs": completed_research},
            [] if completed_research else ["尚无完成且可审计的 Research Run。"],
        ),
        _milestone(
            "2.1.1",
            "Retrieval and Parsing Quality",
            "pass" if retrieval_pass and parser_pass else "blocked",
            {"retrieval_benchmarks_passed": retrieval_pass, "parser_benchmarks_passed": parser_pass},
            [] if retrieval_pass and parser_pass else ["600 条 qrels 与 200 份真实文档基准尚未全部达标。"],
        ),
        _milestone(
            "2.1.2",
            "Evidence-Aware Document Editor",
            "blocked",
            {"structure_valid_exports": valid_exports},
            ["结构校验可自动完成，但 Office 真实打开和视觉确认仍需人工 artifact。"],
        ),
        _milestone(
            "2.1.3",
            "Enterprise Identity and Connectors",
            "pass" if identity_ready and sync_applied else "blocked",
            {"identity_profiles_ready": identity_ready, "connector_syncs_applied": sync_applied},
            [] if identity_ready and sync_applied else ["尚缺真实企业身份配置或受控连接器同步证据。"],
        ),
        _milestone(
            "2.1.4",
            "Governed Agent Operations",
            "pass" if agent_completed else "blocked",
            {"completed_agent_runs": agent_completed},
            [] if agent_completed else ["尚无通过审批、预算和 checkpoint 门禁的完整 Agent Run。"],
        ),
        _milestone(
            "2.1.5",
            "Vertical Evidence Packs",
            "pass" if active_packs >= 3 else "blocked",
            {"active_vertical_packs": active_packs, "required": 3},
            [] if active_packs >= 3 else ["医疗、金融、文旅三包仍需各自 100 任务与 30 份专家复核。"],
        ),
        _milestone(
            "2.2.0",
            "Commercial Team Decision OS",
            "pass" if pilot_ready else "blocked",
            {"accepted_customer_pilots": accepted_pilots, "accepted_sectors": accepted_sectors},
            [] if pilot_ready else ["医疗、金融、文旅三个 Pilot 尚未全部继承 readiness 并完成客户签署。"],
        ),
    ]
    overall = "pass" if all(value["acceptance_status"] == "pass" for value in milestones) else "blocked"
    return {
        "version": "2.2.0-development",
        "generated_at": iso(utc_now()),
        "engineering_status": "implemented",
        "overall_acceptance_status": overall,
        "milestones": milestones,
        "honesty_note": "本地工程实现与商业放行分开计算；人工、专家、客户或生产证据缺失时不自动转绿。",
    }
