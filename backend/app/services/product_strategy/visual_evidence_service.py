from __future__ import annotations

import base64
import binascii
import hashlib
import io
import os
import re
import tempfile
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.models.product_strategy_artifact_acceptance_entities import ProductStrategyArtifactAcceptanceDraft
from app.models.product_strategy_office_evidence_entities import ProductStrategyOfficeEvidenceReceipt
from app.models.product_strategy_visual_evidence_entities import ProductStrategyVisualEvidenceRevision
from app.schemas.product_strategy_visual_evidence import VisualEvidenceCreateRequest
from app.services.product_strategy.catalog import canonical_digest


VISUAL_EVIDENCE_VERSION = "2.10.6"
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_DIMENSION = 16384
MAX_IMAGE_PIXELS = 40_000_000
VISUAL_EVIDENCE_STORAGE_ROOT = Path(__file__).resolve().parents[4] / ".storage" / "product-strategy" / "visual-evidence"
GATES = {
    "human_review_status": "missing",
    "acceptance_status": "hold",
    "blocking_status": "blocked",
    "can_auto_accept": False,
    "can_auto_approve_release": False,
    "production_status": "not_authorized",
}
CONFLICT_CODES = {
    "office_receipt_required", "office_receipt_digest_mismatch", "office_receipt_stale",
    "revision_conflict", "concurrent_revision_conflict",
}


class VisualEvidenceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _image(payload: VisualEvidenceCreateRequest) -> tuple[bytes, int, int]:
    name = payload.file_name
    if any(char in name for char in ("/", "\\", ":")) or any(ord(char) < 32 for char in name):
        raise VisualEvidenceError("invalid_file_name", "截图文件名不能包含目录、盘符或控制字符。")
    if Path(name).suffix.lower() != ".png" or name in {".png", "..png"}:
        raise VisualEvidenceError("unsupported_image_format", "视觉证据仅接受真实 PNG 文件。")
    if len(payload.image_base64) > ((MAX_IMAGE_BYTES + 2) // 3) * 4:
        raise VisualEvidenceError("image_too_large", "PNG 文件不得超过 8 MiB。")
    try:
        data = base64.b64decode(payload.image_base64, validate=True)
    except (ValueError, binascii.Error) as error:
        raise VisualEvidenceError("invalid_base64", "截图不是有效的 Base64 内容。") from error
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise VisualEvidenceError("image_too_large", "PNG 文件必须非空且不得超过 8 MiB。")
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise VisualEvidenceError("invalid_png", "截图内容不是 PNG。")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                width, height = image.size
                if image.format != "PNG" or getattr(image, "n_frames", 1) != 1:
                    raise VisualEvidenceError("invalid_png", "截图必须是单帧 PNG。")
                if min(width, height) <= 0 or max(width, height) > MAX_IMAGE_DIMENSION or width * height > MAX_IMAGE_PIXELS:
                    raise VisualEvidenceError("image_dimensions_exceeded", "PNG 边长不得超过 16384，像素总数不得超过 4000 万。")
                image.verify()
            # Verify checks chunks/CRC; loading also rejects truncated pixel streams.
            with Image.open(io.BytesIO(data)) as decoded:
                decoded.load()
    except VisualEvidenceError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise VisualEvidenceError("invalid_png", "PNG 无法完整解码，或包含损坏的数据。") from error
    if payload.viewport is not None and payload.capture_kind != "office_page":
        expected_width = round(payload.viewport.width * payload.viewport.device_scale_factor)
        expected_height = round(payload.viewport.height * payload.viewport.device_scale_factor)
        if abs(width - expected_width) > 1 or height < expected_height - 1:
            raise VisualEvidenceError("viewport_image_mismatch", "PNG 尺寸与 viewport/像素比例不一致；全页截图可高于 viewport。")
    return data, width, height


def _diff(before: dict[str, Any], after: dict[str, Any], prefix: str = "") -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for key in sorted(before.keys() | after.keys()):
        path = f"{prefix}.{key}" if prefix else key
        old, new = before.get(key), after.get(key)
        if key in before and key in after and isinstance(old, dict) and isinstance(new, dict):
            result.extend(_diff(old, new, path))
        elif key not in before:
            result.append({"field_path": path, "before": None, "after": new, "change_type": "added"})
        elif key not in after:
            result.append({"field_path": path, "before": old, "after": None, "change_type": "removed"})
        elif old != new:
            result.append({"field_path": path, "before": old, "after": new, "change_type": "changed"})
    return result


def _serialize(row: ProductStrategyVisualEvidenceRevision) -> dict[str, Any]:
    snapshot = dict(row.snapshot_payload)
    snapshot.pop("image_storage_ref", None)
    snapshot.pop("image_size_bytes", None)
    instant = row.created_at
    normalized = instant.replace(tzinfo=UTC) if instant.tzinfo is None else instant.astimezone(UTC)
    return {
        **snapshot,
        **GATES,
        "id": str(row.id), "revision_key": row.revision_key,
        "revision": row.revision, "previous_revision_digest": row.previous_revision_digest,
        "revision_digest": row.revision_digest,
        "field_level_diff": list(row.field_level_diff_payload),
        "created_at": normalized.isoformat().replace("+00:00", "Z"),
    }


def list_visual_evidence_revisions(db: Session) -> dict[str, Any]:
    rows = db.scalars(select(ProductStrategyVisualEvidenceRevision).order_by(
        ProductStrategyVisualEvidenceRevision.revision.desc(),
        ProductStrategyVisualEvidenceRevision.created_at.desc(),
        ProductStrategyVisualEvidenceRevision.revision_key.asc(),
    )).all()
    revisions = [_serialize(row) for row in rows]
    return {
        "visual_evidence_version": VISUAL_EVIDENCE_VERSION,
        "revisions": revisions, "revision_count": len(revisions),
        "needs_revision_count": sum(row["review_status"] == "needs_revision" for row in revisions),
        "acceptance_status": "hold", "blocking_status": "blocked",
        "note": "截图与逐项观察已记录，仍需具名人工视觉复核；本记录不代表客户验收或发布授权。",
    }


def responsive_evidence_summary(db: Session) -> dict[str, Any]:
    """Summarize desktop/mobile evidence without implying real-device acceptance."""
    rows = db.scalars(select(ProductStrategyVisualEvidenceRevision).order_by(
        ProductStrategyVisualEvidenceRevision.created_at.desc(),
        ProductStrategyVisualEvidenceRevision.revision_key.asc(),
    )).all()
    latest: dict[tuple[Any, str, str], ProductStrategyVisualEvidenceRevision] = {}
    for row in rows:
        key = (row.office_receipt_id, row.surface_key, row.capture_kind)
        if key not in latest:
            latest[key] = row
    selected = list(latest.values())
    kinds = {row.capture_kind for row in selected}
    blockers = []
    if "desktop_browser" not in kinds:
        blockers.append("desktop_browser_evidence_missing")
    if "mobile_viewport" not in kinds:
        blockers.append("mobile_viewport_evidence_missing")
    if any(row.snapshot_payload.get("review_status") == "needs_revision" for row in selected):
        blockers.append("visual_revision_needed")
    if any(any(item.get("status") != "pass" for item in (row.snapshot_payload.get("checklist") or {}).values()) for row in selected):
        blockers.append("visual_checklist_incomplete")
    return {
        "responsive_evidence_version": "2.11.3",
        "desktop_browser_count": sum(row.capture_kind == "desktop_browser" for row in selected),
        "mobile_viewport_count": sum(row.capture_kind == "mobile_viewport" for row in selected),
        "office_page_count": sum(row.capture_kind == "office_page" for row in selected),
        "latest_revision_digests": sorted(row.revision_digest for row in selected),
        "physical_device_capture": False,
        "production_performance_benchmark": False,
        "blockers": sorted(set(blockers + ["named_human_visual_review_missing", "independent_device_and_performance_evidence_missing"])),
        "acceptance_status": "hold", "blocking_status": "blocked", "production_status": "not_authorized",
        "can_auto_accept": False, "can_auto_approve_release": False,
        "note": "桌面截图和 CSS 移动视口仅是本地证据；它们不等于物理真机、Office 验收或生产性能基准。",
    }


def _validate_receipt(db: Session, payload: VisualEvidenceCreateRequest) -> ProductStrategyOfficeEvidenceReceipt:
    receipt = db.scalar(select(ProductStrategyOfficeEvidenceReceipt).where(
        ProductStrategyOfficeEvidenceReceipt.receipt_key == payload.office_receipt_key,
    ).execution_options(populate_existing=True))
    if receipt is None:
        raise VisualEvidenceError("office_receipt_required", "请先选择已登记的 Office 证据收据。")
    if receipt.receipt_digest != payload.expected_office_receipt_digest:
        raise VisualEvidenceError("office_receipt_digest_mismatch", "Office 收据摘要已变化，请刷新后重试。")
    draft = db.scalar(select(ProductStrategyArtifactAcceptanceDraft).where(
        ProductStrategyArtifactAcceptanceDraft.id == receipt.artifact_acceptance_draft_id,
    ).with_for_update().execution_options(populate_existing=True))
    if (draft is None or draft.artifact_key != receipt.artifact_key
            or draft.revision != receipt.artifact_revision
            or draft.revision_digest != receipt.artifact_revision_digest):
        raise VisualEvidenceError("office_receipt_stale", "此收据对应旧版工件，请先为最新 revision 登记 Office 收据。")
    return receipt


def _verify_office_page(receipt: ProductStrategyOfficeEvidenceReceipt, page: int, image_sha: str) -> None:
    matched = []
    for entry in receipt.rendered_pages_payload or []:
        # Match the actual filename number, never lexicographic array position (1,10,2).
        match = re.fullmatch(r"page-(\d+)\.png", str(entry.get("file_name", "")), re.IGNORECASE)
        number = entry.get("page_number") or (int(match.group(1)) if match else None)
        if number == page:
            matched.append(entry)
    if len(matched) != 1 or matched[0].get("sha256") != image_sha:
        raise VisualEvidenceError("office_page_digest_mismatch", "PNG 必须与所选 Office 收据对应页的 SHA-256 完全一致。")


def _persist_image(data: bytes, digest: str) -> str:
    VISUAL_EVIDENCE_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    path = VISUAL_EVIDENCE_STORAGE_ROOT / f"{digest}.png"
    with tempfile.NamedTemporaryFile(dir=VISUAL_EVIDENCE_STORAGE_ROOT, suffix=".tmp") as stream:
        stream.write(data)
        stream.flush()
        try:
            # Hard-link publication is atomic and never replaces an old target.
            os.link(stream.name, path)
        except FileExistsError:
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise VisualEvidenceError("image_storage_conflict", "已有截图内容与摘要不一致，不能覆盖。")
    return f"visual-evidence/{digest}.png"


def create_visual_evidence_revision(db: Session, *, payload: VisualEvidenceCreateRequest) -> dict[str, Any]:
    data, width, height = _image(payload)
    image_sha = hashlib.sha256(data).hexdigest()
    try:
        # Reserve the SQLite writer before reading a mutable artifact revision.
        # PostgreSQL uses the artifact row lock in _validate_receipt instead.
        if db.bind is not None and db.bind.dialect.name == "sqlite" and not db.in_transaction():
            db.execute(text("BEGIN IMMEDIATE"))
        receipt = _validate_receipt(db, payload)
        if payload.capture_kind == "office_page":
            _verify_office_page(receipt, payload.office_page_number, image_sha)
        checklist = payload.checklist.model_dump()
        snapshot = {
            "office_receipt_key": receipt.receipt_key, "office_receipt_digest": receipt.receipt_digest,
            "artifact_key": receipt.artifact_key, "artifact_revision": receipt.artifact_revision,
            "artifact_revision_digest": receipt.artifact_revision_digest,
            "surface_key": payload.surface_key, "capture_kind": payload.capture_kind,
            "source_version": payload.source_version, "file_name": payload.file_name,
            "image_sha256": image_sha, "image_width": width, "image_height": height,
            "image_size_bytes": len(data), "image_storage_ref": f"visual-evidence/{image_sha}.png",
            "viewport": payload.viewport.model_dump() if payload.viewport else None,
            "office_page_number": payload.office_page_number, "checklist": checklist, "notes": payload.notes,
            "review_status": "needs_revision" if any(item["status"] == "fail" for item in checklist.values()) else "recorded_unverified",
            **GATES,
        }
        content_digest = canonical_digest(snapshot)
        chain = select(ProductStrategyVisualEvidenceRevision).where(
            ProductStrategyVisualEvidenceRevision.office_receipt_id == receipt.id,
            ProductStrategyVisualEvidenceRevision.surface_key == payload.surface_key,
            ProductStrategyVisualEvidenceRevision.capture_kind == payload.capture_kind,
        )
        latest = db.scalar(chain.order_by(ProductStrategyVisualEvidenceRevision.revision.desc()).limit(1))
        # Only identical retry of the latest revision is idempotent. Older content
        # must not mask an intervening revision or silently roll the UI back.
        if latest is not None and latest.content_digest == content_digest and payload.previous_revision_digest in {
            latest.previous_revision_digest, latest.revision_digest,
        }:
            result = {"outcome": "existing", "deduplicated": True, "revision": _serialize(latest)}
            db.rollback()
            return result
        previous = latest.revision_digest if latest else None
        if payload.previous_revision_digest != previous:
            raise VisualEvidenceError("revision_conflict", "视觉证据已有新修订，请刷新并基于最新摘要提交。")
        revision = latest.revision + 1 if latest else 1
        field_diff = _diff(dict(latest.snapshot_payload) if latest else {}, snapshot)
        revision_digest = canonical_digest({"snapshot": snapshot, "revision": revision, "previous_revision_digest": previous, "field_level_diff": field_diff})
        row = ProductStrategyVisualEvidenceRevision(
            revision_key=f"visual:{revision_digest}", office_receipt_id=receipt.id,
            surface_key=payload.surface_key, capture_kind=payload.capture_kind,
            revision=revision, previous_revision_digest=previous, revision_digest=revision_digest,
            content_digest=content_digest, snapshot_payload=snapshot, field_level_diff_payload=field_diff,
            created_at=datetime.now(UTC),
        )
        _persist_image(data, image_sha)
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"outcome": "created", "deduplicated": False, "revision": _serialize(row)}
    except (IntegrityError, OperationalError) as error:
        db.rollback()
        raise VisualEvidenceError("concurrent_revision_conflict", "存在并发修订，请刷新后重试；未覆盖任何已存证据。") from error
    except Exception:
        db.rollback()
        raise
