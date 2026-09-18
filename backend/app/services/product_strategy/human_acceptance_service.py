from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.models.product_strategy_artifact_acceptance_entities import ProductStrategyArtifactAcceptanceDraft as Artifact
from app.models.product_strategy_human_acceptance_entities import ProductStrategyHumanAcceptanceEvent as Event
from app.models.product_strategy_office_evidence_entities import ProductStrategyOfficeEvidenceReceipt as Receipt
from app.models.product_strategy_visual_evidence_entities import ProductStrategyVisualEvidenceRevision as Visual
from app.schemas.product_strategy_human_acceptance import HumanAcceptanceCreateRequest
from app.services.product_strategy.catalog import canonical_digest
from app.services.product_strategy import office_evidence_service, visual_evidence_service, operation_evidence_service
from app.services.release_readiness_service import build_release_readiness_snapshot

GATES = {"acceptance_status": "hold", "blocking_status": "blocked", "production_status": "not_authorized",
         "can_auto_accept": False, "can_auto_approve_release": False, "release_gate_mutated": False}


class HumanAcceptanceError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def serialize_event(row: Event) -> dict:
    snapshot = deepcopy(row.snapshot_payload)
    expected = canonical_digest({"snapshot": snapshot, "sequence": row.sequence, "previous_event_digest": row.previous_event_digest})
    if expected != row.event_digest or row.event_key != f"acceptance:{expected}":
        raise HumanAcceptanceError("event_integrity_failed", "验收事件摘要不一致，停止导出。")
    instant = row.created_at
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=UTC)
    return {**snapshot, "event_key": row.event_key, "event_digest": row.event_digest, "sequence": row.sequence,
            "previous_event_digest": row.previous_event_digest, "created_at": instant.isoformat(), **GATES}


def list_events(db: Session) -> dict:
    rows = db.scalars(select(Event).order_by(Event.created_at.desc(), Event.event_key)).all()
    return {"human_acceptance_version": "2.10.7", "events": [serialize_event(row) for row in rows],
            "event_count": len(rows), "identity_status": "self_attested", "acceptance_status": "hold", "blocking_status": "blocked",
            "note": "具名意见仅记录自述身份；未经独立身份校验、客户确认及发布评审，不升级为验收或生产授权。"}


def _bound_evidence(db: Session, request: HumanAcceptanceCreateRequest):
    receipt = db.scalar(select(Receipt).where(Receipt.receipt_key == request.office_receipt_key))
    if receipt is None:
        raise HumanAcceptanceError("receipt_missing", "Office 收据不存在。")
    office_evidence_service._serialize(receipt)
    artifact = db.scalar(select(Artifact).where(Artifact.id == receipt.artifact_acceptance_draft_id).with_for_update().execution_options(populate_existing=True))
    if (artifact is None or artifact.revision_digest != request.expected_artifact_revision_digest
            or receipt.artifact_revision_digest != artifact.revision_digest
            or receipt.artifact_revision != artifact.revision
            or receipt.receipt_digest != request.expected_office_receipt_digest):
        raise HumanAcceptanceError("stale_evidence", "工件或收据修订已变化，请刷新并重新复核。")
    issues = []
    if receipt.structure_status != "pass" or receipt.office_roundtrip_status != "passed":
        issues.append("office_roundtrip_not_passed")
    for digest in request.visual_revision_digests:
        visual = db.scalar(select(Visual).where(Visual.revision_digest == digest, Visual.office_receipt_id == receipt.id))
        if visual is None:
            raise HumanAcceptanceError("visual_revision_missing", "视觉修订不存在或属于另一份 Office 收据。")
        data = visual_evidence_service._serialize(visual)
        latest = db.scalar(select(Visual).where(Visual.office_receipt_id == receipt.id,
                           Visual.surface_key == visual.surface_key, Visual.capture_kind == visual.capture_kind)
                           .order_by(Visual.revision.desc()).limit(1))
        if latest.revision_digest != digest:
            raise HumanAcceptanceError("stale_visual_revision", "不能针对已被替代的视觉修订提交新意见。")
        if any(item["status"] != "pass" for item in data["checklist"].values()):
            issues.append(f"visual_checklist_incomplete:{visual.surface_key}")
    return artifact, receipt, sorted(set(issues))


def create_event(db: Session, request: HumanAcceptanceCreateRequest) -> dict:
    request_digest = canonical_digest(request.model_dump(mode="json"))
    try:
        if db.bind is not None and db.bind.dialect.name == "sqlite" and not db.in_transaction():
            db.execute(text("BEGIN IMMEDIATE"))
        existing = db.scalar(select(Event).where(Event.idempotency_key == request.idempotency_key))
        if existing is not None:
            if existing.request_digest != request_digest:
                raise HumanAcceptanceError("idempotency_conflict", "幂等键已绑定其他评审内容。")
            result = {"outcome": "existing", "deduplicated": True, "event": serialize_event(existing)}
            db.rollback()
            return result
        artifact, receipt, issues = _bound_evidence(db, request)
        latest = db.scalar(select(Event).where(Event.artifact_key == artifact.artifact_key).order_by(Event.sequence.desc()).limit(1))
        if latest is not None:
            serialize_event(latest)
        previous = latest.event_digest if latest else None
        if request.previous_event_digest != previous:
            raise HumanAcceptanceError("event_revision_conflict", "验收意见已有新事件，请基于最新摘要提交。")
        sequence = latest.sequence + 1 if latest else 1
        snapshot = {
            "idempotency_key": request.idempotency_key, "artifact_key": artifact.artifact_key,
            "artifact_revision": artifact.revision, "artifact_revision_digest": artifact.revision_digest,
            "office_receipt_key": receipt.receipt_key, "office_receipt_digest": receipt.receipt_digest,
            "visual_revision_digests": sorted(request.visual_revision_digests),
            "reviewer_identity": request.reviewer_identity, "author_identity": request.author_identity,
            "decision": request.decision, "review_scope": request.review_scope, "rationale": request.rationale,
            "identity_status": "self_attested", "separation_of_duties_status": "self_attested_distinct",
            "evidence_issues": issues, **GATES,
        }
        digest = canonical_digest({"snapshot": snapshot, "sequence": sequence, "previous_event_digest": previous})
        row = Event(event_key=f"acceptance:{digest}", idempotency_key=request.idempotency_key, request_digest=request_digest,
                    artifact_key=artifact.artifact_key, office_receipt_id=receipt.id, sequence=sequence,
                    previous_event_digest=previous, event_digest=digest, snapshot_payload=snapshot, created_at=datetime.now(UTC))
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"outcome": "created", "deduplicated": False, "event": serialize_event(row)}
    except (IntegrityError, OperationalError) as error:
        db.rollback()
        raise HumanAcceptanceError("concurrent_review_conflict", "并发意见冲突，未覆盖旧事件，请刷新重试。") from error
    except Exception:
        db.rollback()
        raise


def release_bridge(db: Session, artifact_key: str) -> dict:
    artifact = db.scalar(select(Artifact).where(Artifact.artifact_key == artifact_key))
    if artifact is None:
        raise HumanAcceptanceError("artifact_missing", "请指定已持久化的验收工件。")
    receipts = db.scalars(select(Receipt).where(Receipt.artifact_key == artifact_key).order_by(Receipt.created_at, Receipt.receipt_key)).all()
    current_receipts = [row for row in receipts if row.artifact_revision_digest == artifact.revision_digest and row.artifact_revision == artifact.revision]
    receipt_ids = [row.id for row in current_receipts]
    all_visual = db.scalars(select(Visual).where(Visual.office_receipt_id.in_(receipt_ids)).order_by(Visual.revision)).all() if receipt_ids else []
    latest_visual = {}
    for row in all_visual:
        visual_evidence_service._serialize(row)
        latest_visual[(row.office_receipt_id, row.surface_key, row.capture_kind)] = row
    visual = list(latest_visual.values())
    events = [serialize_event(row) for row in db.scalars(select(Event).where(Event.artifact_key == artifact_key).order_by(Event.sequence)).all()]
    blockers = ["authenticated_independent_reviewer_missing", "customer_acceptance_missing", "production_authorization_missing"]
    if not current_receipts:
        blockers.append("current_office_receipt_missing")
    if not any(row.office_roundtrip_status == "passed" and row.structure_status == "pass" for row in current_receipts):
        blockers.append("office_roundtrip_not_passed")
    kinds = {row.capture_kind for row in visual}
    for kind in ("office_page", "desktop_browser", "mobile_viewport"):
        if kind not in kinds:
            blockers.append(f"visual_kind_missing:{kind}")
    for receipt in current_receipts:
        office_evidence_service._serialize(receipt)
        reviewed_pages = {row.snapshot_payload.get("office_page_number") for row in visual if row.office_receipt_id == receipt.id and row.capture_kind == "office_page"}
        if not set(range(1, receipt.page_count + 1)) <= reviewed_pages:
            blockers.append(f"office_page_review_incomplete:{receipt.receipt_key}")
    if any(any(item["status"] != "pass" for item in row.snapshot_payload["checklist"].values()) for row in visual):
        blockers.append("visual_checklist_incomplete")
    current_digests = {row.revision_digest for row in visual}
    if not events or events[-1]["artifact_revision_digest"] != artifact.revision_digest:
        blockers.append("current_named_review_missing")
    elif events[-1]["decision"] != "approve":
        blockers.append("latest_review_not_approved")
    elif not current_digests <= set(events[-1]["visual_revision_digests"]):
        blockers.append("named_review_does_not_cover_latest_visuals")
    raw_upstream = build_release_readiness_snapshot(db)
    upstream = {"overall_status": raw_upstream["overall_status"], "release_version": raw_upstream["release_version"],
                "gates": [{"key": row["key"], "status": row["status"]} for row in raw_upstream["gates"]]}
    if upstream["overall_status"] != "pass":
        blockers.append("upstream_release_readiness_not_passed")
    operations = operation_evidence_service.export_audit(db)
    upstream["operation_bundle_digest"] = operations["bundle_digest"]
    upstream["missing_operation_evidence_kinds"] = operations["missing_evidence_kinds"]
    if operations["missing_evidence_kinds"]:
        blockers.append("operation_evidence_incomplete")
    snapshot = {
        "bridge_version": "2.10.8", "artifact_key": artifact_key, "artifact_revision": artifact.revision,
        "artifact_revision_digest": artifact.revision_digest,
        "office_receipts": [{"receipt_key": row.receipt_key, "digest": row.receipt_digest, "page_count": row.page_count,
                             "office_roundtrip_status": row.office_roundtrip_status} for row in current_receipts],
        "visual_revisions": [{"revision_key": row.revision_key, "digest": row.revision_digest, "capture_kind": row.capture_kind} for row in visual],
        "human_events": [{"event_key": row["event_key"], "digest": row["event_digest"], "decision": row["decision"],
                          "artifact_revision_digest": row["artifact_revision_digest"], "identity_status": "self_attested"} for row in events],
        "upstream": upstream, "blockers": sorted(set(blockers)), "read_only": True, **GATES,
    }
    return {**snapshot, "bridge_digest": canonical_digest(snapshot)}
