from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
import hashlib
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.decision_studio_entities import (
    DecisionClaim,
    DecisionDocumentContract,
    DecisionPassage,
    DecisionSection,
    DecisionSource,
    DecisionSourceRevision,
)


CLAIM_GRAPH_VERSION = "1.9.4-claim-section-v1"


def _hash(payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _passage_rows(db: Session, passage_ids: list[UUID]) -> list[tuple[DecisionPassage, DecisionSourceRevision, DecisionSource]]:
    if not passage_ids:
        return []
    return list(
        db.execute(
            select(DecisionPassage, DecisionSourceRevision, DecisionSource)
            .join(DecisionSourceRevision, DecisionSourceRevision.id == DecisionPassage.revision_id)
            .join(DecisionSource, DecisionSource.id == DecisionSourceRevision.source_id)
            .where(DecisionPassage.id.in_(passage_ids))
        ).all()
    )


def _validate_claim_evidence(
    db: Session,
    *,
    notebook_id: UUID,
    status: str,
    criticality: str,
    passage_ids: list[UUID],
) -> None:
    if status != "accepted":
        return
    if criticality == "critical" and not passage_ids:
        raise ValueError("Critical accepted claims require at least one passage citation.")
    rows = _passage_rows(db, passage_ids)
    if len(rows) != len(set(passage_ids)):
        raise ValueError("One or more passage citations do not exist.")
    for _passage, revision, source in rows:
        if source.notebook_id != notebook_id:
            raise ValueError("Cross-notebook passage citations are not allowed.")
        if source.current_revision_id != revision.id:
            raise ValueError("Accepted claims must cite the current immutable source revision.")
        if source.admission_status != "accepted" or source.trust_status in {"revoked", "expired"}:
            raise ValueError("Rejected, revoked, or expired sources cannot support accepted claims.")
        if criticality == "critical" and (source.trust_status != "verified" or not source.owner_label.strip()):
            raise ValueError("Critical accepted claims require a verified source with an accountable owner.")


def _claim_graph(db: Session, notebook_id: UUID, *, candidate: tuple[str, list[str]] | None = None) -> dict[str, list[str]]:
    claims = db.scalars(select(DecisionClaim).where(DecisionClaim.notebook_id == notebook_id)).all()
    graph = {str(claim.id): [str(value) for value in claim.depends_on_claim_ids or []] for claim in claims}
    if candidate:
        graph[candidate[0]] = candidate[1]
    return graph


def _assert_acyclic(graph: dict[str, list[str]]) -> None:
    state: dict[str, int] = {}

    def visit(node: str) -> None:
        if state.get(node) == 1:
            raise ValueError("Claim dependency graph contains a cycle.")
        if state.get(node) == 2:
            return
        state[node] = 1
        for dependency in graph.get(node, []):
            if dependency in graph:
                visit(dependency)
        state[node] = 2

    for node in graph:
        visit(node)


def create_claim(
    db: Session,
    *,
    notebook_id: UUID,
    claim_key: str,
    text: str,
    criticality: str,
    status: str,
    passage_ids: list[UUID],
    depends_on_claim_ids: list[UUID],
    facts: dict[str, object],
    owner_label: str,
) -> DecisionClaim:
    existing_dependencies = list(
        db.scalars(
            select(DecisionClaim.id)
            .where(DecisionClaim.notebook_id == notebook_id)
            .where(DecisionClaim.id.in_(depends_on_claim_ids))
        ).all()
    ) if depends_on_claim_ids else []
    if len(existing_dependencies) != len(set(depends_on_claim_ids)):
        raise ValueError("Claim dependencies must exist in the same notebook.")
    _validate_claim_evidence(
        db,
        notebook_id=notebook_id,
        status=status,
        criticality=criticality,
        passage_ids=passage_ids,
    )
    claim = DecisionClaim(
        notebook_id=notebook_id,
        claim_key=claim_key.strip()[:120],
        text=text.strip(),
        criticality=criticality,
        status=status,
        passage_ids=[str(value) for value in dict.fromkeys(passage_ids)],
        depends_on_claim_ids=[str(value) for value in dict.fromkeys(depends_on_claim_ids)],
        facts_payload=facts,
        owner_label=owner_label.strip()[:160],
    )
    db.add(claim)
    db.flush()
    _assert_acyclic(
        _claim_graph(
            db,
            notebook_id,
            candidate=(str(claim.id), list(claim.depends_on_claim_ids)),
        )
    )
    db.commit()
    db.refresh(claim)
    return claim


def serialize_claim(db: Session, claim: DecisionClaim) -> dict[str, object]:
    passage_ids = [UUID(str(value)) for value in claim.passage_ids or []]
    citations = []
    for passage, revision, source in _passage_rows(db, passage_ids):
        citations.append(
            {
                "passage_id": str(passage.id),
                "source_id": str(source.id),
                "source_title": source.title,
                "source_revision_id": str(revision.id),
                "revision_number": revision.revision_number,
                "is_current_revision": source.current_revision_id == revision.id,
                "source_admission_status": source.admission_status,
                "source_trust_status": source.trust_status,
                "locator": {
                    **dict(passage.locator_payload or {}),
                    "page": passage.page_number,
                    "paragraph": passage.paragraph_number,
                },
            }
        )
    return {
        "id": str(claim.id),
        "notebook_id": str(claim.notebook_id),
        "claim_key": claim.claim_key,
        "text": claim.text,
        "criticality": claim.criticality,
        "status": claim.status,
        "passage_ids": list(claim.passage_ids or []),
        "depends_on_claim_ids": list(claim.depends_on_claim_ids or []),
        "facts": claim.facts_payload or {},
        "owner_label": claim.owner_label,
        "citations": citations,
    }


def claim_evidence_findings(db: Session, claims: list[DecisionClaim]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for claim in claims:
        if claim.status != "accepted":
            continue
        passage_ids = [UUID(str(value)) for value in claim.passage_ids or []]
        if not passage_ids:
            findings.append(
                {
                    "key": f"missing_citation:{claim.id}",
                    "severity": "high" if claim.criticality == "critical" else "medium",
                    "claim_ids": [str(claim.id)],
                    "message": "Accepted claim has no passage citation.",
                }
            )
            continue
        rows = _passage_rows(db, passage_ids)
        if len(rows) != len(set(passage_ids)):
            findings.append(
                {
                    "key": f"missing_passage:{claim.id}",
                    "severity": "high",
                    "claim_ids": [str(claim.id)],
                    "message": "Accepted claim references a missing passage.",
                }
            )
            continue
        invalid_reasons: list[str] = []
        for _passage, revision, source in rows:
            if source.current_revision_id != revision.id:
                invalid_reasons.append("non_current_revision")
            if source.admission_status != "accepted":
                invalid_reasons.append("source_not_admitted")
            if source.trust_status in {"revoked", "expired"}:
                invalid_reasons.append(f"source_{source.trust_status}")
            if claim.criticality == "critical" and (
                source.trust_status != "verified" or not source.owner_label.strip()
            ):
                invalid_reasons.append("critical_source_not_verified")
        if invalid_reasons:
            findings.append(
                {
                    "key": f"invalid_citation:{claim.id}",
                    "severity": "high",
                    "claim_ids": [str(claim.id)],
                    "reasons": sorted(set(invalid_reasons)),
                    "message": "Accepted claim citation is no longer valid for compilation.",
                }
            )
    return findings


def upsert_section(
    db: Session,
    *,
    notebook_id: UUID,
    section_key: str,
    title: str,
    claim_ids: list[UUID],
    contract_id: UUID | None = None,
) -> DecisionSection:
    if contract_id:
        contract = db.get(DecisionDocumentContract, contract_id)
        if contract is None or contract.notebook_id != notebook_id:
            raise ValueError("Section contract does not belong to the notebook.")
    claims = list(
        db.scalars(
            select(DecisionClaim)
            .where(DecisionClaim.notebook_id == notebook_id)
            .where(DecisionClaim.id.in_(claim_ids))
        ).all()
    ) if claim_ids else []
    if len(claims) != len(set(claim_ids)):
        raise ValueError("Every section claim must exist in the notebook.")
    section = db.scalar(
        select(DecisionSection)
        .where(DecisionSection.notebook_id == notebook_id)
        .where(DecisionSection.section_key == section_key)
    )
    if section is None:
        section = DecisionSection(
            notebook_id=notebook_id,
            contract_id=contract_id,
            section_key=section_key.strip()[:120],
            title=title.strip()[:240],
        )
        db.add(section)
    section.contract_id = contract_id
    section.title = title.strip()[:240]
    section.claim_ids = [str(value) for value in dict.fromkeys(claim_ids)]
    section.status = "waiting"
    db.commit()
    db.refresh(section)
    return section


def _consistency_findings(claims: list[DecisionClaim]) -> list[dict[str, object]]:
    values_by_key: dict[str, dict[str, list[str]]] = {}
    for claim in claims:
        if claim.status != "accepted":
            continue
        for key, value in dict(claim.facts_payload or {}).items():
            normalized = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
            values_by_key.setdefault(str(key), {}).setdefault(normalized, []).append(str(claim.id))
    findings: list[dict[str, object]] = []
    for key, values in values_by_key.items():
        if len(values) <= 1:
            continue
        findings.append(
            {
                "key": f"fact_conflict:{key}",
                "severity": "high",
                "fact_key": key,
                "values": [json.loads(value) for value in values],
                "claim_ids": [claim_id for claim_ids in values.values() for claim_id in claim_ids],
                "message": f"Accepted claims contain conflicting values for {key}.",
            }
        )
    return findings


def _section_dependency(section: DecisionSection, claims: list[DecisionClaim]) -> str:
    return _hash(
        {
            "compiler": CLAIM_GRAPH_VERSION,
            "section_key": section.section_key,
            "claims": [
                {
                    "id": str(claim.id),
                    "text": claim.text,
                    "status": claim.status,
                    "criticality": claim.criticality,
                    "passage_ids": claim.passage_ids,
                    "facts": claim.facts_payload,
                }
                for claim in sorted(claims, key=lambda item: item.claim_key)
            ],
        }
    )


def _render_section(plan: dict[str, object]) -> str:
    lines = [f"## {plan['title']}"]
    claims = list(plan.get("claims") or [])
    if not claims:
        return "\n\n".join([*lines, "本章节暂无通过证据门的主张，保持阻断状态。"])
    for claim in claims:
        citations = list(claim.get("citations") or [])
        citation_text = " ".join(
            f"[来源：{citation['source_title']} · r{citation['revision_number']} · {citation['locator']}]"
            for citation in citations
        )
        lines.append(f"- {claim['text']} {citation_text}".rstrip())
    return "\n".join(lines)


def compile_notebook_sections(
    db: Session,
    *,
    notebook_id: UUID,
    force: bool = False,
    max_workers: int = 4,
) -> dict[str, object]:
    sections = list(
        db.scalars(
            select(DecisionSection)
            .where(DecisionSection.notebook_id == notebook_id)
            .order_by(DecisionSection.created_at)
        ).all()
    )
    all_claims = list(db.scalars(select(DecisionClaim).where(DecisionClaim.notebook_id == notebook_id)).all())
    claims_by_id = {str(claim.id): claim for claim in all_claims}
    global_findings = [*_consistency_findings(all_claims), *claim_evidence_findings(db, all_claims)]
    conflicting_claim_ids = {
        claim_id
        for finding in global_findings
        for claim_id in list(finding.get("claim_ids") or [])
    }
    plans: list[dict[str, object]] = []
    skipped: list[str] = []
    blocked: list[str] = []
    section_claims: dict[str, list[DecisionClaim]] = {}
    for section in sections:
        claims = [claims_by_id[value] for value in section.claim_ids or [] if value in claims_by_id]
        accepted = [claim for claim in claims if claim.status == "accepted"]
        section_claims[str(section.id)] = accepted
        dependency_hash = _section_dependency(section, accepted)
        if not force and section.dependency_hash == dependency_hash and section.status == "approved":
            skipped.append(section.section_key)
            continue
        section_findings = [
            finding for finding in global_findings
            if any(claim_id in conflicting_claim_ids for claim_id in list(finding.get("claim_ids") or []))
            and any(str(claim.id) in list(finding.get("claim_ids") or []) for claim in accepted)
        ]
        if not accepted or section_findings:
            section.status = "blocked"
            section.findings_payload = section_findings or [{"severity": "high", "message": "No accepted claims."}]
            section.dependency_hash = dependency_hash
            blocked.append(section.section_key)
            continue
        plans.append(
            {
                "section_id": str(section.id),
                "title": section.title,
                "dependency_hash": dependency_hash,
                "claims": [serialize_claim(db, claim) for claim in accepted],
            }
        )
    rendered: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, 4))) as pool:
        futures = {pool.submit(_render_section, plan): str(plan["section_id"]) for plan in plans}
        for future, section_id in futures.items():
            rendered[section_id] = future.result()
    built: list[str] = []
    for plan in plans:
        section = db.get(DecisionSection, UUID(str(plan["section_id"])))
        if section is None:
            continue
        section.content = rendered[str(section.id)]
        section.dependency_hash = str(plan["dependency_hash"])
        section.build_version += 1
        section.status = "approved"
        section.findings_payload = []
        section.last_built_at = datetime.now(UTC)
        built.append(section.section_key)
    db.commit()
    return {
        "framework": CLAIM_GRAPH_VERSION,
        "notebook_id": str(notebook_id),
        "built_section_keys": built,
        "skipped_section_keys": skipped,
        "blocked_section_keys": blocked,
        "incremental_rebuild": not force,
        "global_findings": global_findings,
        "status": "blocked" if blocked or global_findings else "pass",
    }


def serialize_section(section: DecisionSection) -> dict[str, object]:
    return {
        "id": str(section.id),
        "notebook_id": str(section.notebook_id),
        "contract_id": str(section.contract_id) if section.contract_id else None,
        "section_key": section.section_key,
        "title": section.title,
        "status": section.status,
        "claim_ids": list(section.claim_ids or []),
        "content": section.content,
        "dependency_hash": section.dependency_hash,
        "build_version": section.build_version,
        "findings": list(section.findings_payload or []),
        "last_built_at": section.last_built_at,
    }
