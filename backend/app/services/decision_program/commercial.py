from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.decision_program_entities import DecisionCustomerPilot, DecisionReleaseCandidate, DecisionVerticalPack
from app.services.decision_program.common import iso, utc_now


REQUIRED_WORKFLOW_EVIDENCE = {
    "source_ingest": "来源导入与 ACL artifact",
    "research_run": "研究运行 artifact",
    "decision_document": "决策文档 artifact",
    "office_roundtrip": "Office roundtrip artifact",
    "audit_export": "审计导出 artifact",
    "recovery_drill": "恢复演练 artifact",
}


def create_customer_pilot(
    db: Session,
    *,
    space_id: UUID,
    vertical_pack_id: UUID | None,
    name: str,
    customer_label: str,
    sector: str,
    owner_label: str,
    deployment_profile: dict[str, Any],
    sla: dict[str, Any],
) -> DecisionCustomerPilot:
    if vertical_pack_id:
        pack = db.get(DecisionVerticalPack, vertical_pack_id)
        if pack is None or pack.sector != sector:
            raise ValueError("Pilot sector must match its vertical evidence pack.")
    row = DecisionCustomerPilot(
        space_id=space_id,
        vertical_pack_id=vertical_pack_id,
        name=name.strip(),
        customer_label=customer_label.strip(),
        sector=sector.strip(),
        status="planned",
        owner_label=owner_label.strip(),
        deployment_profile_payload=deployment_profile,
        sla_payload=sla,
        workflow_evidence_payload={},
        acceptance_payload={},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _evidence_blockers(evidence: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for key, label in REQUIRED_WORKFLOW_EVIDENCE.items():
        value = evidence.get(key)
        if not isinstance(value, dict) or value.get("status") != "pass" or not str(value.get("artifact_uri") or "").strip():
            blockers.append(f"缺少合格的{label}。")
    return blockers


def _release_acceptance_ready(db: Session, *, user_id: UUID) -> bool:
    candidate = db.scalar(
        select(DecisionReleaseCandidate)
        .where(DecisionReleaseCandidate.user_id == user_id)
        .order_by(DecisionReleaseCandidate.frozen_at.desc(), DecisionReleaseCandidate.id.desc())
    )
    return bool(candidate and (candidate.evidence_snapshot_payload or {}).get("acceptance_status") == "pass")


def update_customer_pilot(
    db: Session,
    *,
    pilot: DecisionCustomerPilot,
    user_id: UUID,
    action: str,
    workflow_evidence: dict[str, Any],
    acceptance: dict[str, Any],
    customer_signer: str,
) -> DecisionCustomerPilot:
    if action == "start":
        if pilot.status != "planned":
            raise ValueError("Only a planned Pilot can start.")
        pilot.status = "active"
    elif action == "record_evidence":
        if pilot.status not in {"active", "acceptance_pending"}:
            raise ValueError("Pilot evidence can only be recorded while active or under acceptance.")
        pilot.workflow_evidence_payload = {**dict(pilot.workflow_evidence_payload or {}), **workflow_evidence}
    elif action == "request_acceptance":
        if pilot.status != "active":
            raise ValueError("Only an active Pilot can request acceptance.")
        blockers = _evidence_blockers(dict(pilot.workflow_evidence_payload or {}))
        if blockers:
            raise ValueError("; ".join(blockers))
        pilot.status = "acceptance_pending"
        pilot.acceptance_payload = {**acceptance, "requested_at": iso(utc_now()), "status": "pending"}
    elif action == "reject":
        if pilot.status != "acceptance_pending":
            raise ValueError("Only a pending acceptance can be rejected.")
        pilot.status = "rejected"
        pilot.acceptance_payload = {**dict(pilot.acceptance_payload or {}), **acceptance, "status": "rejected"}
    elif action == "signoff":
        if pilot.status != "acceptance_pending":
            raise ValueError("Only a pending acceptance can be signed off.")
        blockers = _evidence_blockers(dict(pilot.workflow_evidence_payload or {}))
        if blockers:
            raise ValueError("; ".join(blockers))
        if not _release_acceptance_ready(db, user_id=user_id):
            raise ValueError("The bound 2.0.7 release candidate still lacks complete external acceptance evidence.")
        if not customer_signer.strip():
            raise ValueError("Customer signoff requires a named signer.")
        if acceptance.get("decision") != "accepted" or not str(acceptance.get("artifact_uri") or "").strip():
            raise ValueError("Customer signoff requires accepted decision and original acceptance artifact URI.")
        pilot.status = "accepted"
        pilot.customer_signer = customer_signer.strip()
        pilot.signed_at = utc_now()
        pilot.acceptance_payload = {**acceptance, "status": "accepted", "signed_at": iso(pilot.signed_at)}
    else:
        raise ValueError("Unsupported customer Pilot action.")
    db.commit()
    db.refresh(pilot)
    return pilot


def serialize_customer_pilot(pilot: DecisionCustomerPilot) -> dict[str, Any]:
    evidence = dict(pilot.workflow_evidence_payload or {})
    return {
        "id": str(pilot.id),
        "space_id": str(pilot.space_id),
        "vertical_pack_id": str(pilot.vertical_pack_id) if pilot.vertical_pack_id else None,
        "name": pilot.name,
        "customer_label": pilot.customer_label,
        "sector": pilot.sector,
        "status": pilot.status,
        "owner_label": pilot.owner_label,
        "deployment_profile": dict(pilot.deployment_profile_payload or {}),
        "sla": dict(pilot.sla_payload or {}),
        "workflow_evidence": evidence,
        "evidence_blockers": _evidence_blockers(evidence),
        "acceptance": dict(pilot.acceptance_payload or {}),
        "customer_signer": pilot.customer_signer,
        "signed_at": iso(pilot.signed_at),
        "created_at": iso(pilot.created_at),
    }
