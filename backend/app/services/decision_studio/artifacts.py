from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.decision_studio_entities import DecisionArtifact, DecisionClaim
from app.services.decision_studio.claim_graph import serialize_claim


ARTIFACT_RUNTIME_VERSION = "2.0.0-evidence-bound-artifacts-v1"
SUPPORTED_ARTIFACT_TYPES = {
    "executive_brief",
    "mind_map",
    "data_table",
    "slide_outline",
    "infographic_spec",
    "audio_script",
}


def _hash(payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _accepted_claims(db: Session, notebook_id: UUID) -> list[DecisionClaim]:
    return list(
        db.scalars(
            select(DecisionClaim)
            .where(DecisionClaim.notebook_id == notebook_id)
            .where(DecisionClaim.status == "accepted")
            .order_by(DecisionClaim.criticality.desc(), DecisionClaim.claim_key)
        ).all()
    )


def _evidence_bound_claims(db: Session, notebook_id: UUID) -> list[dict[str, object]]:
    claims = [serialize_claim(db, claim) for claim in _accepted_claims(db, notebook_id)]
    if not claims:
        raise ValueError("At least one accepted claim is required before generating an artifact.")
    uncited = [str(claim["claim_key"]) for claim in claims if not claim.get("citations")]
    if uncited:
        raise ValueError(f"Every accepted claim must have a current passage citation: {', '.join(uncited)}")
    invalid = [
        str(claim["claim_key"])
        for claim in claims
        if any(
            not citation.get("is_current_revision")
            or citation.get("source_admission_status") != "accepted"
            or citation.get("source_trust_status") in {"revoked", "expired"}
            for citation in list(claim.get("citations") or [])
        )
    ]
    if invalid:
        raise ValueError(f"Claims contain stale, rejected, revoked, or expired citations: {', '.join(invalid)}")
    return claims


def _citation_summary(claim: dict[str, object]) -> list[dict[str, object]]:
    return [
        {
            "passage_id": citation["passage_id"],
            "source_id": citation["source_id"],
            "source_title": citation["source_title"],
            "source_revision_id": citation["source_revision_id"],
            "revision_number": citation["revision_number"],
            "locator": citation["locator"],
        }
        for citation in list(claim.get("citations") or [])
    ]


def _lineage(claims: list[dict[str, object]]) -> dict[str, object]:
    claim_ids = [str(claim["id"]) for claim in claims]
    critical_claim_ids = [
        str(claim["id"])
        for claim in claims
        if str(claim.get("criticality")) == "critical"
    ]
    revision_ids = sorted(
        {
            str(citation["source_revision_id"])
            for claim in claims
            for citation in list(claim.get("citations") or [])
        }
    )
    return {
        "runtime": ARTIFACT_RUNTIME_VERSION,
        "claim_ids": claim_ids,
        "critical_claim_ids": critical_claim_ids,
        "source_revision_ids": revision_ids,
        "citation_count": sum(len(list(claim.get("citations") or [])) for claim in claims),
    }


def _render_payload(
    *,
    artifact_type: str,
    title: str,
    claims: list[dict[str, object]],
    lineage: dict[str, object],
) -> dict[str, object]:
    rows = [
        {
            "claim_id": claim["id"],
            "claim_key": claim["claim_key"],
            "text": claim["text"],
            "criticality": claim["criticality"],
            "facts": claim.get("facts") or {},
            "citations": _citation_summary(claim),
        }
        for claim in claims
    ]
    if artifact_type == "executive_brief":
        content: dict[str, object] = {
            "headline": title,
            "decision_points": rows,
            "source_note": "All decision points are bound to passage-level source revisions.",
        }
    elif artifact_type == "mind_map":
        content = {
            "root": {"id": "root", "label": title},
            "nodes": [
                {
                    "id": row["claim_id"],
                    "label": row["text"],
                    "criticality": row["criticality"],
                    "citations": row["citations"],
                }
                for row in rows
            ],
            "edges": [
                {"from": dependency_id, "to": claim["id"], "kind": "claim_dependency"}
                for claim in claims
                for dependency_id in list(claim.get("depends_on_claim_ids") or [])
            ],
        }
    elif artifact_type == "data_table":
        content = {
            "columns": ["claim_key", "text", "criticality", "facts", "citations"],
            "rows": rows,
        }
    elif artifact_type == "slide_outline":
        content = {
            "slides": [
                {
                    "slide": index,
                    "title": str(row["claim_key"]),
                    "bullets": [row["text"]],
                    "citations": row["citations"],
                }
                for index, row in enumerate(rows, start=1)
            ]
        }
    elif artifact_type == "infographic_spec":
        content = {
            "canvas": {"ratio": "16:9", "title": title},
            "blocks": [
                {
                    "order": index,
                    "label": row["claim_key"],
                    "statement": row["text"],
                    "facts": row["facts"],
                    "citations": row["citations"],
                }
                for index, row in enumerate(rows, start=1)
            ],
        }
    elif artifact_type == "audio_script":
        segments = [
            {
                "order": index,
                "transcript": str(row["text"]),
                "source_cues": row["citations"],
            }
            for index, row in enumerate(rows, start=1)
        ]
        content = {
            "segments": segments,
            "transcript": "\n".join(str(segment["transcript"]) for segment in segments),
            "estimated_seconds": max(15, round(sum(len(str(row["text"])) for row in rows) / 4.2)),
        }
    else:
        raise ValueError(f"Unsupported artifact type: {artifact_type}")
    return {
        "artifact_type": artifact_type,
        "title": title,
        "content": content,
        "lineage": lineage,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }


def generate_artifact(
    db: Session,
    *,
    notebook_id: UUID,
    artifact_type: str,
    title: str,
) -> tuple[DecisionArtifact, bool]:
    if artifact_type not in SUPPORTED_ARTIFACT_TYPES:
        raise ValueError(f"Unsupported artifact type: {artifact_type}")
    claims = _evidence_bound_claims(db, notebook_id)
    lineage = _lineage(claims)
    dependency_hash = _hash(
        {
            "runtime": ARTIFACT_RUNTIME_VERSION,
            "artifact_type": artifact_type,
            "claims": claims,
        }
    )
    consistency_hash = _hash(
        {
            "claims": [
                {
                    "id": claim["id"],
                    "text": claim["text"],
                    "facts": claim.get("facts") or {},
                }
                for claim in claims
            ]
        }
    )
    existing = db.scalar(
        select(DecisionArtifact)
        .where(DecisionArtifact.notebook_id == notebook_id)
        .where(DecisionArtifact.artifact_type == artifact_type)
        .where(DecisionArtifact.dependency_hash == dependency_hash)
        .where(DecisionArtifact.stale.is_(False))
        .order_by(DecisionArtifact.updated_at.desc())
        .limit(1)
    )
    if existing is not None:
        return existing, True
    for prior in db.scalars(
        select(DecisionArtifact)
        .where(DecisionArtifact.notebook_id == notebook_id)
        .where(DecisionArtifact.artifact_type == artifact_type)
        .where(DecisionArtifact.stale.is_(False))
    ).all():
        prior.stale = True
        prior.status = "stale"
    artifact = DecisionArtifact(
        notebook_id=notebook_id,
        artifact_type=artifact_type,
        title=title.strip()[:240] or artifact_type.replace("_", " ").title(),
        status="ready",
        content_payload=_render_payload(
            artifact_type=artifact_type,
            title=title.strip()[:240] or artifact_type.replace("_", " ").title(),
            claims=claims,
            lineage=lineage,
        ),
        source_revision_ids=list(lineage["source_revision_ids"]),
        claim_ids=list(lineage["claim_ids"]),
        dependency_hash=dependency_hash,
        consistency_hash=consistency_hash,
        stale=False,
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact, False


def list_artifacts(db: Session, *, notebook_id: UUID) -> list[DecisionArtifact]:
    return list(
        db.scalars(
            select(DecisionArtifact)
            .where(DecisionArtifact.notebook_id == notebook_id)
            .order_by(DecisionArtifact.updated_at.desc())
        ).all()
    )


def audit_artifact_consistency(db: Session, *, notebook_id: UUID) -> dict[str, object]:
    claims = _accepted_claims(db, notebook_id)
    critical_ids = {str(claim.id) for claim in claims if claim.criticality == "critical"}
    artifacts = [artifact for artifact in list_artifacts(db, notebook_id=notebook_id) if not artifact.stale]
    findings: list[dict[str, object]] = []
    hashes = {artifact.consistency_hash for artifact in artifacts if artifact.status == "ready"}
    if len(hashes) > 1:
        findings.append({"severity": "high", "code": "cross_artifact_consistency_hash_mismatch"})
    for artifact in artifacts:
        missing = sorted(critical_ids - {str(value) for value in artifact.claim_ids or []})
        if missing:
            findings.append(
                {
                    "severity": "high",
                    "code": "critical_claim_missing_from_artifact",
                    "artifact_id": str(artifact.id),
                    "missing_claim_ids": missing,
                }
            )
    return {
        "status": "blocked" if findings else ("pass" if artifacts else "watch"),
        "artifact_count": len(artifacts),
        "critical_claim_count": len(critical_ids),
        "findings": findings,
    }


def serialize_artifact(artifact: DecisionArtifact) -> dict[str, object]:
    return {
        "id": str(artifact.id),
        "notebook_id": str(artifact.notebook_id),
        "artifact_type": artifact.artifact_type,
        "title": artifact.title,
        "status": artifact.status,
        "content": artifact.content_payload or {},
        "source_revision_ids": list(artifact.source_revision_ids or []),
        "claim_ids": list(artifact.claim_ids or []),
        "dependency_hash": artifact.dependency_hash,
        "consistency_hash": artifact.consistency_hash,
        "stale": artifact.stale,
        "created_at": artifact.created_at,
        "updated_at": artifact.updated_at,
    }
