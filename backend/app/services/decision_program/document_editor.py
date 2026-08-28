from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.decision_program_entities import DecisionDocumentDraft
from app.models.decision_studio_entities import DecisionClaim, DecisionDocumentContract, DecisionSection
from app.services.decision_program.common import canonical_digest, iso, utc_now
from app.services.work_tasks.office_roundtrip import validate_docx_bytes, validate_pptx_bytes
from app.services.work_tasks.openxml import build_docx_bytes, build_pptx_bytes


class DocumentRevisionConflict(RuntimeError):
    pass


def _claims_by_id(db: Session, *, notebook_id: UUID) -> dict[str, DecisionClaim]:
    rows = list(
        db.scalars(
            select(DecisionClaim)
            .where(DecisionClaim.notebook_id == notebook_id)
            .where(DecisionClaim.status == "accepted")
        ).all()
    )
    return {str(row.id): row for row in rows}


def _section_block(section: DecisionSection, claims: dict[str, DecisionClaim]) -> dict[str, Any]:
    claim_ids = [str(value) for value in section.claim_ids or [] if str(value) in claims]
    selected = [claims[value] for value in claim_ids]
    content = section.content.strip() or "\n\n".join(claim.text for claim in selected)
    source_refs = list(
        dict.fromkeys(str(passage_id) for claim in selected for passage_id in claim.passage_ids or [])
    )
    dependency = canonical_digest(
        {
            "section_id": str(section.id),
            "section_dependency_hash": section.dependency_hash,
            "claim_ids": claim_ids,
            "claim_texts": [claim.text for claim in selected],
            "source_refs": source_refs,
        }
    )
    return {
        "block_key": section.section_key,
        "section_id": str(section.id),
        "title": section.title,
        "content": content,
        "owner": "machine",
        "claim_ids": claim_ids,
        "source_refs": source_refs,
        "dependency_hash": dependency,
        "stale": False,
    }


def _claim_block(claim: DecisionClaim) -> dict[str, Any]:
    source_refs = [str(value) for value in claim.passage_ids or []]
    dependency = canonical_digest({"claim_id": str(claim.id), "text": claim.text, "source_refs": source_refs})
    return {
        "block_key": f"claim-{claim.claim_key}",
        "section_id": None,
        "title": claim.claim_key,
        "content": claim.text,
        "owner": "machine",
        "claim_ids": [str(claim.id)],
        "source_refs": source_refs,
        "dependency_hash": dependency,
        "stale": False,
    }


def _build_blocks(db: Session, *, notebook_id: UUID) -> list[dict[str, Any]]:
    claims = _claims_by_id(db, notebook_id=notebook_id)
    sections = list(
        db.scalars(
            select(DecisionSection)
            .where(DecisionSection.notebook_id == notebook_id)
            .order_by(DecisionSection.created_at, DecisionSection.id)
        ).all()
    )
    if sections:
        return [_section_block(section, claims) for section in sections]
    return [_claim_block(claim) for claim in claims.values()]


def create_document_draft(
    db: Session,
    *,
    notebook_id: UUID,
    contract_id: UUID | None,
    title: str,
    document_kind: str,
) -> DecisionDocumentDraft:
    if contract_id:
        contract = db.get(DecisionDocumentContract, contract_id)
        if contract is None or contract.notebook_id != notebook_id:
            raise ValueError("Document contract does not belong to this notebook.")
        if contract.document_kind != document_kind:
            raise ValueError("Document kind must match the selected contract.")
    blocks = _build_blocks(db, notebook_id=notebook_id)
    if not blocks:
        raise ValueError("A draft requires at least one accepted Claim or compiled section.")
    dependency_hash = canonical_digest([row["dependency_hash"] for row in blocks])
    row = DecisionDocumentDraft(
        notebook_id=notebook_id,
        contract_id=contract_id,
        title=title.strip(),
        document_kind=document_kind.strip(),
        status="draft",
        revision=1,
        blocks_payload=blocks,
        revision_history_payload=[
            {"revision": 1, "action": "created", "dependency_hash": dependency_hash, "at": iso(utc_now())}
        ],
        dependency_hash=dependency_hash,
        export_profile_payload={"formats": ["docx", "pptx"], "human_blocks_preserved": True},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _assert_revision(draft: DecisionDocumentDraft, expected_revision: int) -> None:
    if draft.revision != expected_revision:
        raise DocumentRevisionConflict(
            f"Document revision conflict: expected {expected_revision}, current {draft.revision}."
        )


def update_document_block(
    db: Session,
    *,
    draft: DecisionDocumentDraft,
    expected_revision: int,
    block_key: str,
    title: str,
    content: str,
    source_refs: list[str],
    actor_id: str,
) -> DecisionDocumentDraft:
    _assert_revision(draft, expected_revision)
    blocks = [dict(value) for value in draft.blocks_payload or []]
    target = next((value for value in blocks if value.get("block_key") == block_key), None)
    if target is None:
        target = {"block_key": block_key, "claim_ids": [], "section_id": None}
        blocks.append(target)
    before_digest = canonical_digest(target)
    target.update(
        {
            "title": title.strip() or str(target.get("title") or block_key),
            "content": content,
            "owner": "human",
            "source_refs": list(dict.fromkeys(source_refs)),
            "dependency_hash": canonical_digest(
                {"content": content, "source_refs": list(dict.fromkeys(source_refs)), "actor_id": actor_id}
            ),
            "stale": False,
            "last_editor_id": actor_id,
        }
    )
    draft.blocks_payload = blocks
    draft.revision += 1
    draft.dependency_hash = canonical_digest([value.get("dependency_hash") for value in blocks])
    history = list(draft.revision_history_payload or [])
    history.append(
        {
            "revision": draft.revision,
            "action": "human_block_update",
            "block_key": block_key,
            "before_digest": before_digest,
            "after_digest": canonical_digest(target),
            "actor_id": actor_id,
            "at": iso(utc_now()),
        }
    )
    draft.revision_history_payload = history[-500:]
    db.commit()
    db.refresh(draft)
    return draft


def regenerate_document_blocks(
    db: Session,
    *,
    draft: DecisionDocumentDraft,
    expected_revision: int,
    changed_claim_ids: list[UUID],
    actor_id: str,
) -> DecisionDocumentDraft:
    _assert_revision(draft, expected_revision)
    fresh = {value["block_key"]: value for value in _build_blocks(db, notebook_id=draft.notebook_id)}
    changed = {str(value) for value in changed_claim_ids}
    blocks: list[dict[str, Any]] = []
    regenerated: list[str] = []
    preserved: list[str] = []
    stale_human: list[str] = []
    for raw in draft.blocks_payload or []:
        block = dict(raw)
        block_key = str(block.get("block_key") or "")
        intersects = not changed or bool(changed & {str(value) for value in block.get("claim_ids") or []})
        candidate = fresh.get(block_key)
        dependency_changed = bool(candidate and candidate.get("dependency_hash") != block.get("dependency_hash"))
        if block.get("owner") == "machine" and intersects and candidate:
            blocks.append(candidate)
            regenerated.append(block_key)
        else:
            if block.get("owner") == "human" and intersects and dependency_changed:
                block["stale"] = True
                block["upstream_dependency_hash"] = candidate.get("dependency_hash") if candidate else ""
                stale_human.append(block_key)
            blocks.append(block)
            preserved.append(block_key)
    draft.blocks_payload = blocks
    draft.revision += 1
    draft.dependency_hash = canonical_digest([value.get("dependency_hash") for value in blocks])
    history = list(draft.revision_history_payload or [])
    history.append(
        {
            "revision": draft.revision,
            "action": "differential_regeneration",
            "actor_id": actor_id,
            "changed_claim_ids": sorted(changed),
            "regenerated_blocks": regenerated,
            "preserved_blocks": preserved,
            "stale_human_blocks": stale_human,
            "at": iso(utc_now()),
        }
    )
    draft.revision_history_payload = history[-500:]
    db.commit()
    db.refresh(draft)
    return draft


def export_document_draft(
    db: Session,
    *,
    draft: DecisionDocumentDraft,
    export_format: str,
    brand_template: dict[str, Any],
) -> tuple[str, str, bytes, dict[str, Any]]:
    blocks = [dict(value) for value in draft.blocks_payload or []]
    stale = [str(value.get("block_key") or "") for value in blocks if value.get("stale") is True]
    if stale:
        raise ValueError(f"Resolve stale human blocks before export: {', '.join(stale)}")
    sections = [
        (
            str(value.get("title") or value.get("block_key") or "Untitled"),
            [line for line in str(value.get("content") or "").splitlines() if line.strip()] or [""],
        )
        for value in blocks
    ]
    required_texts = [draft.title, *[title for title, _ in sections[:2]]]
    if export_format == "docx":
        artifact = build_docx_bytes(
            title=draft.title,
            subtitle=f"Decision Studio evidence-aware draft r{draft.revision}",
            document_kind_label=draft.document_kind,
            meta_rows=[f"Revision: {draft.revision}", f"Dependency hash: {draft.dependency_hash}"],
            sections=sections,
            layout_rows=["A4 portrait", "Evidence-aware block layout"],
            roundtrip_rows=["OpenXML structure validation", "Manual Office visual confirmation remains required"],
            proofreading_rows=["Verify citations", "Verify customer-specific names and numbers"],
            brand_template=brand_template,
            renderer_strategy="controlled OpenXML generator plus structure roundtrip validation",
        )
        diagnostics = validate_docx_bytes(artifact, required_texts=required_texts)
        extension, mime = "docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif export_format == "pptx":
        artifact = build_pptx_bytes(
            title=draft.title,
            subtitle=f"Decision Studio evidence-aware draft r{draft.revision}",
            slides=sections,
            brand_template=brand_template,
        )
        diagnostics = validate_pptx_bytes(artifact, required_texts=required_texts)
        extension, mime = "pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    else:
        raise ValueError("Document export format must be docx or pptx.")
    metadata = {
        "format": export_format,
        "status": diagnostics.get("status"),
        "artifact_digest": hashlib.sha256(artifact).hexdigest(),
        "size_bytes": len(artifact),
        "revision": draft.revision,
        "generated_at": iso(utc_now()),
        "office_roundtrip": diagnostics,
        "manual_visual_confirmation_required": True,
    }
    draft.last_export_payload = metadata
    db.commit()
    filename_seed = "".join(character for character in draft.title if character.isalnum() or character in {"-", "_"}) or "decision-document"
    return f"{filename_seed[:60]}.{extension}", mime, artifact, metadata


def confirm_document_export(
    db: Session,
    *,
    draft: DecisionDocumentDraft,
    owner_user_id: UUID,
    actor_id: str,
    artifact_digest: str,
    reviewer_id: str,
    artifact_uri: str,
    reviewed_at,
    note: str,
) -> DecisionDocumentDraft:
    current = dict(draft.last_export_payload or {})
    if current.get("status") != "pass" or current.get("artifact_digest") != artifact_digest.lower():
        raise ValueError("Visual confirmation must bind the current structure-valid export digest.")
    if reviewer_id != actor_id:
        raise ValueError("Reviewer identity must match the authenticated actor.")
    if reviewer_id == str(owner_user_id):
        raise ValueError("Office visual confirmation requires an independent reviewer.")
    now = utc_now()
    normalized = reviewed_at.replace(tzinfo=now.tzinfo) if reviewed_at.tzinfo is None else reviewed_at.astimezone(now.tzinfo)
    if normalized > now:
        raise ValueError("Office visual review timestamp cannot be in the future.")
    draft.last_export_payload = {
        **current,
        "manual_visual_confirmation_required": False,
        "manual_visual_confirmation": {
            "status": "pass",
            "reviewer_id": reviewer_id,
            "artifact_uri": artifact_uri.strip(),
            "reviewed_at": iso(normalized),
            "note": note.strip(),
        },
    }
    db.commit()
    db.refresh(draft)
    return draft


def serialize_document_draft(draft: DecisionDocumentDraft) -> dict[str, Any]:
    return {
        "id": str(draft.id),
        "notebook_id": str(draft.notebook_id),
        "contract_id": str(draft.contract_id) if draft.contract_id else None,
        "title": draft.title,
        "document_kind": draft.document_kind,
        "status": draft.status,
        "revision": draft.revision,
        "blocks": list(draft.blocks_payload or []),
        "revision_history": list(draft.revision_history_payload or []),
        "dependency_hash": draft.dependency_hash,
        "export_profile": dict(draft.export_profile_payload or {}),
        "last_export": dict(draft.last_export_payload or {}),
        "created_at": iso(draft.created_at),
        "updated_at": iso(draft.updated_at),
    }
