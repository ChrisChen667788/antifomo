from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import hmac
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.decision_studio_entities import (
    DecisionClaim,
    DecisionDocumentContract,
    GovernedSkill,
    GovernedSkillRun,
    KnowledgeConnector,
)


SKILL_RUNTIME_VERSION = "1.9.6-governed-skill-v1"
FORBIDDEN_LICENSES = {"", "unknown", "third_party_unknown", "cc-by-nc-4.0", "non-commercial"}
FORBIDDEN_PERMISSIONS = {"shell", "shell:execute", "filesystem:any", "credential:read", "network:any", "root"}


FIRST_PARTY_SKILLS: tuple[dict[str, object], ...] = (
    {
        "skill_key": "deep-research-orchestrator",
        "name": "Deep Research Orchestrator",
        "entrypoint": "plan_only",
        "permissions": ["read:notebook", "read:sources", "write:claims"],
        "description": "Question decomposition, bounded retrieval, counter-evidence and convergence plan.",
    },
    {
        "skill_key": "government-fsr-intake",
        "name": "Government FSR Intake",
        "entrypoint": "contract_gap_auditor",
        "permissions": ["read:notebook", "read:contracts", "write:contract"],
        "description": "Government feasibility-study applicability and missing-information audit.",
    },
    {
        "skill_key": "project-proposal-compiler",
        "name": "Project Proposal Compiler",
        "entrypoint": "contract_gap_auditor",
        "permissions": ["read:notebook", "read:contracts", "write:artifact"],
        "description": "Project-initiation document contract and gap compiler.",
    },
    {
        "skill_key": "solution-architecture-workbench",
        "name": "Solution Architecture Workbench",
        "entrypoint": "plan_only",
        "permissions": ["read:notebook", "read:claims", "write:artifact"],
        "description": "QAW, ATAM, ADR, C4 and proof-of-architecture orchestration.",
    },
    {
        "skill_key": "evidence-and-entity-auditor",
        "name": "Evidence and Entity Auditor",
        "entrypoint": "evidence_auditor",
        "permissions": ["read:notebook", "read:sources", "read:claims"],
        "description": "Critical-claim citation, source revision and entity evidence audit.",
    },
)


def _canonical(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def package_hash(manifest: dict[str, object], package_bytes: bytes | None = None) -> str:
    return hashlib.sha256(package_bytes if package_bytes is not None else _canonical(manifest)).hexdigest()


def signature_payload(skill: GovernedSkill) -> bytes:
    return _canonical({"manifest": skill.manifest_payload, "package_hash": skill.package_hash})


def compute_signature(skill: GovernedSkill, signing_key: str) -> str:
    return hmac.new(signing_key.encode("utf-8"), signature_payload(skill), hashlib.sha256).hexdigest()


def verify_skill_signature(skill: GovernedSkill, signing_key: str | None) -> bool:
    if not signing_key or not skill.signature:
        return False
    expected = compute_signature(skill, signing_key)
    return hmac.compare_digest(expected, skill.signature)


def _manifest_violations(manifest: dict[str, object], license_id: str, permissions: list[str]) -> list[str]:
    violations: list[str] = []
    required = {"name", "description", "entrypoint", "input_schema", "output_schema", "permissions", "license"}
    missing = sorted(key for key in required if not manifest.get(key))
    if missing:
        violations.append(f"Manifest missing required fields: {', '.join(missing)}")
    if license_id.strip().lower() in FORBIDDEN_LICENSES:
        violations.append("Skill license is missing, unknown, or non-commercial.")
    for permission in permissions:
        if permission in FORBIDDEN_PERMISSIONS or permission.startswith("shell:"):
            violations.append(f"Forbidden permission: {permission}")
    if manifest.get("runtime") not in {"anti_fomo_builtin", "mcp_connector"}:
        violations.append("Only anti_fomo_builtin and governed mcp_connector runtimes are supported.")
    return violations


def register_skill(
    db: Session,
    *,
    user_id: UUID,
    skill_key: str,
    version: str,
    publisher: str,
    manifest: dict[str, object],
    license_id: str,
    package_bytes: bytes | None = None,
) -> GovernedSkill:
    permissions = [str(value) for value in list(manifest.get("permissions") or [])]
    normalized_manifest = {
        **manifest,
        "skill_key": skill_key,
        "version": version,
        "publisher": publisher,
        "license": license_id,
        "permissions": permissions,
        "runtime_version": SKILL_RUNTIME_VERSION,
    }
    existing = db.scalar(
        select(GovernedSkill)
        .where(GovernedSkill.user_id == user_id)
        .where(GovernedSkill.skill_key == skill_key)
        .where(GovernedSkill.version == version)
    )
    digest = package_hash(normalized_manifest, package_bytes)
    if existing is not None:
        if existing.package_hash != digest:
            raise ValueError("Immutable Skill version already exists with a different package hash.")
        return existing
    violations = _manifest_violations(normalized_manifest, license_id, permissions)
    skill = GovernedSkill(
        user_id=user_id,
        skill_key=skill_key.strip()[:140],
        version=version.strip()[:40],
        publisher=publisher.strip()[:160],
        status="blocked" if violations else "quarantine",
        manifest_payload={**normalized_manifest, "registration_violations": violations},
        package_hash=digest,
        license_id=license_id.strip(),
        permissions_payload=permissions,
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


def ensure_first_party_skills(db: Session, *, user_id: UUID) -> list[GovernedSkill]:
    skills: list[GovernedSkill] = []
    for definition in FIRST_PARTY_SKILLS:
        manifest = {
            "name": definition["name"],
            "description": definition["description"],
            "entrypoint": definition["entrypoint"],
            "input_schema": {"type": "object", "required": ["notebook_id"]},
            "output_schema": {"type": "object"},
            "permissions": definition["permissions"],
            "license": "internal",
            "runtime": "anti_fomo_builtin",
            "minimum_benchmark_score": 0.85,
        }
        skills.append(
            register_skill(
                db,
                user_id=user_id,
                skill_key=str(definition["skill_key"]),
                version="1.0.0",
                publisher="anti-fomo",
                manifest=manifest,
                license_id="internal",
            )
        )
    return skills


def sign_skill(db: Session, *, skill: GovernedSkill, signing_key: str) -> GovernedSkill:
    if skill.publisher != "anti-fomo":
        raise ValueError("Only first-party packages can be signed by the local release key.")
    if not signing_key:
        raise ValueError("Decision Skill signing key is not configured.")
    skill.signature = compute_signature(skill, signing_key)
    skill.signature_algorithm = "hmac-sha256"
    skill.status = "review"
    db.commit()
    db.refresh(skill)
    return skill


def record_skill_benchmark(
    db: Session,
    *,
    skill: GovernedSkill,
    score: float,
    case_count: int,
    evidence_ref: str,
) -> GovernedSkill:
    if not 0 <= score <= 1:
        raise ValueError("Benchmark score must be between 0 and 1.")
    if case_count <= 0 or not evidence_ref.strip():
        raise ValueError("Benchmark requires cases and an evidence reference.")
    skill.benchmark_payload = {
        "score": score,
        "case_count": case_count,
        "evidence_ref": evidence_ref.strip(),
        "recorded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    db.commit()
    db.refresh(skill)
    return skill


def approve_skill(db: Session, *, skill: GovernedSkill, signing_key: str | None) -> GovernedSkill:
    violations = _manifest_violations(skill.manifest_payload, skill.license_id, list(skill.permissions_payload or []))
    if not verify_skill_signature(skill, signing_key):
        violations.append("Skill signature is missing or invalid.")
    benchmark = dict(skill.benchmark_payload or {})
    minimum = float(skill.manifest_payload.get("minimum_benchmark_score") or 1.0)
    if float(benchmark.get("score") or 0) < minimum:
        violations.append(f"Benchmark score is below {minimum:.2f}.")
    if violations:
        skill.status = "blocked"
        skill.manifest_payload = {**dict(skill.manifest_payload or {}), "approval_violations": violations}
        db.commit()
        raise ValueError("; ".join(violations))
    skill.status = "approved"
    skill.manifest_payload = {**dict(skill.manifest_payload or {}), "approval_violations": []}
    db.commit()
    db.refresh(skill)
    return skill


def _permission_violations(
    db: Session,
    *,
    skill: GovernedSkill,
    requested: list[str],
    granted: list[str],
) -> list[str]:
    declared = set(str(value) for value in skill.permissions_payload or [])
    granted_set = set(granted)
    violations: list[str] = []
    for permission in requested:
        if permission not in declared:
            violations.append(f"Undeclared permission requested: {permission}")
        if permission not in granted_set:
            violations.append(f"Permission not granted: {permission}")
        if permission in FORBIDDEN_PERMISSIONS or permission.startswith("shell:"):
            violations.append(f"Forbidden runtime permission: {permission}")
        if permission.startswith("connector:"):
            raw_connector_id = permission.split(":", 1)[1]
            try:
                connector = db.get(KnowledgeConnector, UUID(raw_connector_id))
            except ValueError:
                connector = None
            if connector is None or connector.status != "ready":
                violations.append(f"Connector is not approved: {raw_connector_id}")
    return list(dict.fromkeys(violations))


def dry_run_skill(
    db: Session,
    *,
    skill: GovernedSkill,
    notebook_id: UUID | None,
    actor_id: str,
    requested_permissions: list[str],
    granted_permissions: list[str],
) -> GovernedSkillRun:
    violations = _permission_violations(
        db,
        skill=skill,
        requested=requested_permissions,
        granted=granted_permissions,
    )
    if skill.status != "approved":
        violations.append(f"Skill status is {skill.status}; approved is required for execution.")
    run = GovernedSkillRun(
        skill_id=skill.id,
        notebook_id=notebook_id,
        actor_id=actor_id,
        mode="dry_run",
        status="blocked" if violations else "ready",
        plan_payload={
            "runtime": skill.manifest_payload.get("runtime"),
            "entrypoint": skill.manifest_payload.get("entrypoint"),
            "network_execution": False,
            "file_changes": [],
            "database_changes": ["governed_skill_runs"],
        },
        requested_permissions=requested_permissions,
        granted_permissions=granted_permissions,
        violations_payload=violations,
        completed_at=datetime.now(UTC),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _execute_builtin(db: Session, *, skill: GovernedSkill, notebook_id: UUID) -> dict[str, object]:
    entrypoint = str(skill.manifest_payload.get("entrypoint") or "")
    if entrypoint == "evidence_auditor":
        claims = list(db.scalars(select(DecisionClaim).where(DecisionClaim.notebook_id == notebook_id)).all())
        unsupported = [
            str(claim.id)
            for claim in claims
            if claim.status == "accepted" and claim.criticality == "critical" and not claim.passage_ids
        ]
        return {
            "status": "pass" if not unsupported else "blocked",
            "accepted_claim_count": sum(1 for claim in claims if claim.status == "accepted"),
            "unsupported_critical_claim_ids": unsupported,
        }
    if entrypoint == "contract_gap_auditor":
        contracts = list(
            db.scalars(
                select(DecisionDocumentContract).where(DecisionDocumentContract.notebook_id == notebook_id)
            ).all()
        )
        gaps = [
            {"contract_id": str(contract.id), "title": contract.title, "gaps": contract.gaps_payload or []}
            for contract in contracts
            if contract.gaps_payload
        ]
        return {"status": "pass" if not gaps else "blocked", "contract_gaps": gaps}
    if entrypoint == "plan_only":
        return {"status": "planned", "note": "This first-party Skill currently emits a governed plan only."}
    raise ValueError("Skill entrypoint is not implemented by the governed runtime.")


def execute_skill(
    db: Session,
    *,
    skill: GovernedSkill,
    notebook_id: UUID,
    actor_id: str,
    requested_permissions: list[str],
    granted_permissions: list[str],
) -> GovernedSkillRun:
    dry_run = dry_run_skill(
        db,
        skill=skill,
        notebook_id=notebook_id,
        actor_id=actor_id,
        requested_permissions=requested_permissions,
        granted_permissions=granted_permissions,
    )
    if dry_run.status != "ready":
        return dry_run
    result = _execute_builtin(db, skill=skill, notebook_id=notebook_id)
    run = GovernedSkillRun(
        skill_id=skill.id,
        notebook_id=notebook_id,
        actor_id=actor_id,
        mode="execute",
        status="succeeded" if result.get("status") in {"pass", "planned"} else "blocked",
        plan_payload=dry_run.plan_payload,
        requested_permissions=requested_permissions,
        granted_permissions=granted_permissions,
        result_payload=result,
        violations_payload=[],
        completed_at=datetime.now(UTC),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def serialize_skill(skill: GovernedSkill, *, signing_key: str | None = None) -> dict[str, object]:
    return {
        "id": str(skill.id),
        "skill_key": skill.skill_key,
        "version": skill.version,
        "publisher": skill.publisher,
        "status": skill.status,
        "manifest": skill.manifest_payload,
        "package_hash": skill.package_hash,
        "signature_present": bool(skill.signature),
        "signature_valid": verify_skill_signature(skill, signing_key),
        "signature_algorithm": skill.signature_algorithm,
        "license": skill.license_id,
        "permissions": list(skill.permissions_payload or []),
        "benchmark": skill.benchmark_payload or {},
    }


def serialize_skill_run(run: GovernedSkillRun) -> dict[str, object]:
    return {
        "id": str(run.id),
        "skill_id": str(run.skill_id),
        "notebook_id": str(run.notebook_id) if run.notebook_id else None,
        "actor_id": run.actor_id,
        "mode": run.mode,
        "status": run.status,
        "plan": run.plan_payload or {},
        "requested_permissions": list(run.requested_permissions or []),
        "granted_permissions": list(run.granted_permissions or []),
        "result": run.result_payload or {},
        "violations": list(run.violations_payload or []),
    }
