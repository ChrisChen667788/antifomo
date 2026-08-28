from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.decision_program_entities import DecisionReleaseCandidate
from app.models.decision_studio_entities import DecisionValidationRun
from app.services.decision_program.common import canonical_digest, iso, utc_now
from app.services.decision_studio.validation import SUITE_SPECS, serialize_validation_run


REQUIRED_EXTERNAL_ATTESTATIONS = {
    "expert_calibration": "专家校准 artifact",
    "three_industry_blind_review": "三行业盲测 artifact",
    "customer_acceptance": "客户验收签署 artifact",
}


def release_build_digest(*, version: str, manifest: dict[str, Any]) -> str:
    return canonical_digest({"version": version.strip(), "manifest": manifest})


def _latest_validation_runs(db: Session, *, user_id: UUID) -> list[DecisionValidationRun]:
    rows = list(
        db.scalars(
            select(DecisionValidationRun)
            .where(DecisionValidationRun.user_id == user_id)
            .order_by(
                DecisionValidationRun.completed_at.desc(),
                DecisionValidationRun.created_at.desc(),
                DecisionValidationRun.id.desc(),
            )
        ).all()
    )
    latest: dict[str, DecisionValidationRun] = {}
    for row in rows:
        latest.setdefault(row.suite_key, row)
    return list(latest.values())


def _selected_validation_runs(
    db: Session,
    *,
    user_id: UUID,
    validation_run_ids: list[UUID],
) -> list[DecisionValidationRun]:
    if not validation_run_ids:
        return _latest_validation_runs(db, user_id=user_id)
    rows = list(
        db.scalars(
            select(DecisionValidationRun)
            .where(DecisionValidationRun.user_id == user_id)
            .where(DecisionValidationRun.id.in_(validation_run_ids))
        ).all()
    )
    if len(rows) != len(set(validation_run_ids)):
        raise ValueError("One or more validation runs are missing or belong to another user.")
    seen: set[str] = set()
    duplicates: list[str] = []
    for row in rows:
        if row.suite_key in seen:
            duplicates.append(row.suite_key)
        seen.add(row.suite_key)
    if duplicates:
        raise ValueError(f"A release candidate accepts one immutable run per suite: {', '.join(sorted(set(duplicates)))}")
    return rows


def _attestation_blockers(attestations: dict[str, Any], *, owner_user_id: UUID) -> list[str]:
    blockers: list[str] = []
    for key, label in REQUIRED_EXTERNAL_ATTESTATIONS.items():
        value = attestations.get(key)
        if not isinstance(value, dict):
            blockers.append(f"缺少{label}。")
            continue
        actor = str(value.get("reviewer_id") or value.get("signer") or "").strip()
        artifact_uri = str(value.get("artifact_uri") or "").strip()
        attested_at = str(value.get("attested_at") or value.get("signed_at") or "").strip()
        if not actor:
            blockers.append(f"{label}缺少审阅者或签署人。")
        elif key != "customer_acceptance" and actor == str(owner_user_id):
            blockers.append(f"{label}必须由产物所有者之外的人员提交。")
        if not artifact_uri:
            blockers.append(f"{label}缺少原始 artifact URI。")
        if not attested_at:
            blockers.append(f"{label}缺少时间戳。")
    return blockers


def _evaluate_candidate(
    db: Session,
    *,
    user_id: UUID,
    version: str,
    manifest: dict[str, Any],
    validation_run_ids: list[UUID],
    external_attestations: dict[str, Any],
) -> tuple[str, list[DecisionValidationRun], dict[str, Any], list[str]]:
    normalized_version = version.strip()
    if normalized_version != "2.0.7":
        raise ValueError("Release evidence closure currently evaluates version 2.0.7 only.")
    digest = release_build_digest(version=normalized_version, manifest=manifest)
    runs = _selected_validation_runs(db, user_id=user_id, validation_run_ids=validation_run_ids)
    by_suite = {row.suite_key: row for row in runs}
    blockers: list[str] = []
    suite_snapshot: list[dict[str, Any]] = []
    for suite_key, spec in SUITE_SPECS.items():
        run = by_suite.get(suite_key)
        if run is None:
            blockers.append(f"{spec.label}缺少冻结验证记录。")
            suite_snapshot.append({"suite_key": suite_key, "status": "blocked", "run_id": None})
            continue
        evidence_digest = str((run.evidence_payload or {}).get("release_candidate_digest") or "")
        if run.status != "pass":
            blockers.append(f"{spec.label}状态为 {run.status}。")
        if evidence_digest != digest:
            blockers.append(f"{spec.label}未绑定当前 release candidate digest。")
        suite_snapshot.append(
            {
                "suite_key": suite_key,
                "run_id": str(run.id),
                "status": run.status,
                "input_digest": run.input_digest,
                "release_candidate_digest": evidence_digest,
            }
        )
    unknown = sorted(set(by_suite) - set(SUITE_SPECS))
    if unknown:
        blockers.append(f"存在未注册验证套件：{', '.join(unknown)}。")
    blockers.extend(_attestation_blockers(external_attestations, owner_user_id=user_id))
    blockers = list(dict.fromkeys(blockers))
    snapshot = {
        "acceptance_status": "pass" if not blockers else "blocked",
        "suite_count": len(SUITE_SPECS),
        "bound_suite_count": len(by_suite),
        "suites": suite_snapshot,
        "external_attestation_keys": sorted(external_attestations),
    }
    return digest, runs, snapshot, blockers


def preview_release_candidate(
    db: Session,
    *,
    user_id: UUID,
    version: str,
    manifest: dict[str, Any],
    validation_run_ids: list[UUID],
    external_attestations: dict[str, Any],
) -> dict[str, Any]:
    digest, runs, snapshot, blockers = _evaluate_candidate(
        db,
        user_id=user_id,
        version=version,
        manifest=manifest,
        validation_run_ids=validation_run_ids,
        external_attestations=external_attestations,
    )
    return {
        "version": version.strip(),
        "build_digest": digest,
        "acceptance_status": snapshot["acceptance_status"],
        "validation_run_ids": [str(row.id) for row in runs],
        "evidence_snapshot": snapshot,
        "blockers": blockers,
        "persisted": False,
    }


def freeze_release_candidate(
    db: Session,
    *,
    user_id: UUID,
    version: str,
    manifest: dict[str, Any],
    validation_run_ids: list[UUID],
    external_attestations: dict[str, Any],
) -> DecisionReleaseCandidate:
    normalized_version = version.strip()
    digest = release_build_digest(version=normalized_version, manifest=manifest)
    existing = db.scalar(
        select(DecisionReleaseCandidate)
        .where(DecisionReleaseCandidate.user_id == user_id)
        .where(DecisionReleaseCandidate.version == normalized_version)
        .where(DecisionReleaseCandidate.build_digest == digest)
    )
    if existing is not None:
        return existing

    evaluated_digest, runs, evidence_snapshot, blockers = _evaluate_candidate(
        db,
        user_id=user_id,
        version=normalized_version,
        manifest=manifest,
        validation_run_ids=validation_run_ids,
        external_attestations=external_attestations,
    )
    if evaluated_digest != digest:
        raise RuntimeError("Release candidate digest evaluation was not deterministic.")
    frozen_at = utc_now()
    candidate = DecisionReleaseCandidate(
        user_id=user_id,
        version=normalized_version,
        build_digest=digest,
        status="frozen",
        manifest_payload=manifest,
        validation_run_ids=[str(row.id) for row in runs],
        external_attestations_payload=external_attestations,
        evidence_snapshot_payload=evidence_snapshot,
        blockers_payload=blockers,
        frozen_at=frozen_at,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


def list_release_candidates(db: Session, *, user_id: UUID, limit: int = 50) -> list[DecisionReleaseCandidate]:
    return list(
        db.scalars(
            select(DecisionReleaseCandidate)
            .where(DecisionReleaseCandidate.user_id == user_id)
            .order_by(DecisionReleaseCandidate.frozen_at.desc(), DecisionReleaseCandidate.id.desc())
            .limit(max(1, min(limit, 200)))
        ).all()
    )


def serialize_release_candidate(candidate: DecisionReleaseCandidate, db: Session | None = None) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    if db is not None and candidate.validation_run_ids:
        parsed_ids = [UUID(str(value)) for value in candidate.validation_run_ids]
        rows = list(db.scalars(select(DecisionValidationRun).where(DecisionValidationRun.id.in_(parsed_ids))).all())
        ordered = {str(row.id): row for row in rows}
        runs = [serialize_validation_run(ordered[value]) for value in candidate.validation_run_ids if value in ordered]
    return {
        "id": str(candidate.id),
        "user_id": str(candidate.user_id),
        "version": candidate.version,
        "build_digest": candidate.build_digest,
        "status": candidate.status,
        "acceptance_status": (candidate.evidence_snapshot_payload or {}).get("acceptance_status", "blocked"),
        "manifest": dict(candidate.manifest_payload or {}),
        "validation_run_ids": list(candidate.validation_run_ids or []),
        "validation_runs": runs,
        "external_attestations": dict(candidate.external_attestations_payload or {}),
        "evidence_snapshot": dict(candidate.evidence_snapshot_payload or {}),
        "blockers": list(candidate.blockers_payload or []),
        "frozen_at": iso(candidate.frozen_at),
        "created_at": iso(candidate.created_at),
    }
