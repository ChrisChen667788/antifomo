from __future__ import annotations

import base64
import hashlib
import os
import platform
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.product_strategy_artifact_acceptance_entities import ProductStrategyArtifactAcceptanceDraft
from app.models.product_strategy_office_evidence_entities import ProductStrategyOfficeEvidenceReceipt
from app.services.product_strategy.catalog import canonical_digest
from app.services.work_tasks.office_roundtrip import (
    detect_office_roundtrip_capabilities,
    validate_docx_bytes,
    validate_pdf_bytes,
    validate_pptx_bytes,
)


OFFICE_EVIDENCE_VERSION = "2.10.5"
VALIDATOR_VERSION = "anti-fomo-office-receipt-v1"
PROJECT_ROOT = Path(__file__).resolve().parents[4]
OFFICE_EVIDENCE_STORAGE_ROOT = PROJECT_ROOT / ".storage" / "product-strategy" / "office-evidence"
MAX_OFFICE_ARTIFACT_BYTES = 20 * 1024 * 1024
ALLOWED_MEDIA_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


class OfficeEvidenceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return normalized.isoformat().replace("+00:00", "Z")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _safe_file_name(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized or Path(normalized).name != normalized or normalized in {".", ".."}:
        raise OfficeEvidenceError("invalid_file_name", "文件名必须是不含目录的 DOCX 或 PPTX 文件名。")
    suffix = Path(normalized).suffix.lower()
    if suffix not in ALLOWED_MEDIA_TYPES:
        raise OfficeEvidenceError("unsupported_office_format", "2.10.5 当前只接收 DOCX 或 PPTX 证据文件。")
    return normalized


def _decode_payload(file_base64: str) -> bytes:
    encoded = str(file_base64 or "").strip()
    if not encoded:
        raise OfficeEvidenceError("empty_file", "Office 证据文件不能为空。")
    if len(encoded) > ((MAX_OFFICE_ARTIFACT_BYTES + 2) // 3) * 4 + 16:
        raise OfficeEvidenceError("file_too_large", "Office 证据文件不得超过 20 MB。")
    try:
        payload = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise OfficeEvidenceError("invalid_base64", "Office 证据文件不是有效的 Base64 内容。") from exc
    if not payload:
        raise OfficeEvidenceError("empty_file", "Office 证据文件不能为空。")
    if len(payload) > MAX_OFFICE_ARTIFACT_BYTES:
        raise OfficeEvidenceError("file_too_large", "Office 证据文件不得超过 20 MB。")
    return payload


def _structural_validation(suffix: str, payload: bytes, required_texts: list[str]) -> dict[str, Any]:
    if suffix == ".docx":
        raw = validate_docx_bytes(payload, required_texts=required_texts)
    else:
        raw = validate_pptx_bytes(payload, required_texts=required_texts)
    return {
        "status": raw.get("status", "fail"),
        "package": raw.get("package", "unknown"),
        "required_entries_missing": list(raw.get("required_entries_missing") or []),
        "malformed_xml_parts": list(raw.get("malformed_xml_parts") or []),
        "required_text_missing": list(raw.get("required_text_missing") or []),
        "native_editable_charts": bool(raw.get("native_editable_charts")),
        "native_images": bool(raw.get("native_images")),
    }


def _runtime_capability_summary() -> dict[str, Any]:
    raw = detect_office_roundtrip_capabilities()
    return {
        "platform": platform.system().lower(),
        "automated_mode": raw.get("automated_mode", "structure_only"),
        "libreoffice_available": bool(raw.get("libreoffice_cli")),
        "quicklook_available": bool(raw.get("quicklook_cli")),
        "microsoft_word_available": bool(raw.get("microsoft_word_app")),
        "microsoft_powerpoint_available": bool(raw.get("microsoft_powerpoint_app")),
        "gui_open_performed": False,
    }


def _run_headless_roundtrip(source_path: Path, receipt_dir: Path) -> dict[str, Any]:
    capabilities = detect_office_roundtrip_capabilities()
    libreoffice = str(capabilities.get("libreoffice_cli") or "")
    if not libreoffice:
        return {
            "office_roundtrip_status": "unavailable",
            "visual_evidence_status": "missing",
            "page_count": 0,
            "rendered_pdf_sha256": None,
            "rendered_pages": [],
            "engine": "none",
            "failure_reason": "libreoffice_headless_unavailable",
        }

    render_dir = receipt_dir / "render"
    render_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="af-office-receipt-") as profile_dir:
        command = [
            libreoffice,
            "--headless",
            f"-env:UserInstallation=file://{profile_dir}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(render_dir),
            str(source_path),
        ]
        try:
            completed = subprocess.run(command, text=True, capture_output=True, check=False, timeout=90)
        except subprocess.TimeoutExpired:
            return {
                "office_roundtrip_status": "failed",
                "visual_evidence_status": "missing",
                "page_count": 0,
                "rendered_pdf_sha256": None,
                "rendered_pages": [],
                "engine": "libreoffice_headless",
                "failure_reason": "conversion_timeout",
            }

    pdf_path = render_dir / f"{source_path.stem}.pdf"
    if completed.returncode != 0 or not pdf_path.exists() or not pdf_path.stat().st_size:
        return {
            "office_roundtrip_status": "failed",
            "visual_evidence_status": "missing",
            "page_count": 0,
            "rendered_pdf_sha256": None,
            "rendered_pages": [],
            "engine": "libreoffice_headless",
            "failure_reason": "conversion_failed",
            "stderr_tail": completed.stderr[-600:],
        }

    pdf_payload = pdf_path.read_bytes()
    pdf_validation = validate_pdf_bytes(pdf_payload)
    pdftoppm = shutil.which("pdftoppm")
    pages: list[dict[str, Any]] = []
    if pdftoppm:
        prefix = render_dir / "page"
        rendered = subprocess.run(
            [pdftoppm, "-png", "-r", "144", str(pdf_path), str(prefix)],
            text=True,
            capture_output=True,
            check=False,
            timeout=90,
        )
        if rendered.returncode == 0:
            for page in sorted(render_dir.glob("page-*.png")):
                page_payload = page.read_bytes()
                pages.append(
                    {
                        "file_name": page.name,
                        "size_bytes": len(page_payload),
                        "sha256": _sha256(page_payload),
                    }
                )

    passed = pdf_validation.get("status") == "pass"
    return {
        "office_roundtrip_status": "passed" if passed else "failed",
        "visual_evidence_status": "rendered_unreviewed" if passed and pages else "missing",
        "page_count": len(pages) or int(pdf_validation.get("page_count") or 0),
        "rendered_pdf_sha256": _sha256(pdf_payload),
        "rendered_pages": pages,
        "engine": "libreoffice_headless",
        "pdf_validation": {
            "status": pdf_validation.get("status"),
            "starts_with_pdf_header": bool(pdf_validation.get("starts_with_pdf_header")),
            "ends_with_eof": bool(pdf_validation.get("ends_with_eof")),
        },
        "failure_reason": "" if passed else "rendered_pdf_validation_failed",
    }


def _run_supplied_render_evidence(pdf_base64: str, render_engine: str, receipt_dir: Path) -> dict[str, Any]:
    pdf_payload = _decode_payload(pdf_base64)
    pdf_validation = validate_pdf_bytes(pdf_payload)
    if pdf_validation.get("status") != "pass":
        raise OfficeEvidenceError("invalid_rendered_pdf", "伴随渲染文件不是可校验的 PDF。")
    engine = str(render_engine or "").strip()
    if engine not in {"microsoft_word_manual_export", "microsoft_powerpoint_manual_export"}:
        raise OfficeEvidenceError("invalid_render_engine", "伴随 PDF 必须标明由 Microsoft Word 或 PowerPoint 实机导出。")

    render_dir = receipt_dir / "render"
    render_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = render_dir / "manual-office-export.pdf"
    pdf_path.write_bytes(pdf_payload)
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        raise OfficeEvidenceError("page_renderer_unavailable", "当前环境缺少 pdftoppm，无法生成页级视觉证据。")
    rendered = subprocess.run(
        [pdftoppm, "-png", "-r", "144", str(pdf_path), str(render_dir / "page")],
        text=True,
        capture_output=True,
        check=False,
        timeout=90,
    )
    if rendered.returncode != 0:
        raise OfficeEvidenceError("page_render_failed", "伴随 PDF 无法生成页级视觉证据。")
    pages = []
    for page in sorted(render_dir.glob("page-*.png")):
        page_payload = page.read_bytes()
        pages.append({"file_name": page.name, "size_bytes": len(page_payload), "sha256": _sha256(page_payload)})
    if not pages:
        raise OfficeEvidenceError("page_render_failed", "伴随 PDF 未产生可记录的页面。")
    return {
        "office_roundtrip_status": "passed",
        "visual_evidence_status": "rendered_unreviewed",
        "page_count": len(pages),
        "rendered_pdf_sha256": _sha256(pdf_payload),
        "rendered_pages": pages,
        "engine": engine,
        "pdf_validation": {
            "status": pdf_validation.get("status"),
            "starts_with_pdf_header": bool(pdf_validation.get("starts_with_pdf_header")),
            "ends_with_eof": bool(pdf_validation.get("ends_with_eof")),
        },
        "failure_reason": "",
    }


def _serialize(row: ProductStrategyOfficeEvidenceReceipt) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "receipt_key": row.receipt_key,
        "artifact_key": row.artifact_key,
        "artifact_revision": row.artifact_revision,
        "artifact_revision_digest": row.artifact_revision_digest,
        "file_name": row.file_name,
        "media_type": row.media_type,
        "file_size_bytes": row.file_size_bytes,
        "file_sha256": row.file_sha256,
        "storage_ref": row.storage_ref,
        "source_version": row.source_version,
        "validator_version": row.validator_version,
        "structure_status": row.structure_status,
        "office_roundtrip_status": row.office_roundtrip_status,
        "visual_evidence_status": row.visual_evidence_status,
        "page_count": row.page_count,
        "rendered_pdf_sha256": row.rendered_pdf_sha256,
        "rendered_pages": list(row.rendered_pages_payload or []),
        "validation": dict(row.validation_payload or {}),
        "receipt_digest": row.receipt_digest,
        "evidence_level": row.evidence_level,
        "human_review_status": row.human_review_status,
        "acceptance_status": row.acceptance_status,
        "blocking_status": row.blocking_status,
        "can_auto_accept": bool(row.can_auto_accept),
        "can_auto_approve_release": bool(row.can_auto_approve_release),
        "production_status": row.production_status,
        "release_impact": "none",
        "created_at": _iso(row.created_at),
    }


def list_office_evidence_receipts(db: Session) -> dict[str, Any]:
    rows = list(
        db.scalars(
            select(ProductStrategyOfficeEvidenceReceipt).order_by(
                ProductStrategyOfficeEvidenceReceipt.created_at.desc(),
                ProductStrategyOfficeEvidenceReceipt.receipt_key.asc(),
            )
        ).all()
    )
    receipts = [_serialize(row) for row in rows]
    return {
        "office_evidence_version": OFFICE_EVIDENCE_VERSION,
        "receipts": receipts,
        "receipt_count": len(receipts),
        "local_roundtrip_passed_count": sum(1 for row in receipts if row["office_roundtrip_status"] == "passed"),
        "rendered_unreviewed_count": sum(1 for row in receipts if row["visual_evidence_status"] == "rendered_unreviewed"),
        "acceptance_status": "hold",
        "blocking_status": "blocked",
        "requires_named_human_review": True,
        "can_auto_accept": False,
        "can_auto_approve_release": False,
        "production_status": "not_authorized",
        "release_impact": "none",
        "note": "本地结构与无头渲染收据不能替代 Microsoft Office 实机打开、具名人工视觉复核、客户验收或发布批准。",
    }


def create_office_evidence_receipt(
    db: Session,
    *,
    artifact_key: str,
    file_name: str,
    media_type: str,
    file_base64: str,
    source_version: str,
    required_texts: list[str] | None = None,
    rendered_pdf_base64: str | None = None,
    render_engine: str | None = None,
) -> dict[str, Any]:
    draft = db.scalar(
        select(ProductStrategyArtifactAcceptanceDraft).where(
            ProductStrategyArtifactAcceptanceDraft.artifact_key == str(artifact_key or "").strip()
        )
    )
    if draft is None:
        raise OfficeEvidenceError(
            "artifact_acceptance_draft_required",
            "必须先初始化并选择一个 2.10.2 HOLD 验收草稿。",
        )

    safe_name = _safe_file_name(file_name)
    suffix = Path(safe_name).suffix.lower()
    expected_media_type = ALLOWED_MEDIA_TYPES[suffix]
    normalized_media_type = str(media_type or "").strip().lower()
    if normalized_media_type and normalized_media_type != expected_media_type:
        raise OfficeEvidenceError("media_type_mismatch", "文件扩展名与 Office media type 不一致。")
    payload = _decode_payload(file_base64)
    file_sha256 = _sha256(payload)

    existing = db.scalar(
        select(ProductStrategyOfficeEvidenceReceipt).where(
            ProductStrategyOfficeEvidenceReceipt.artifact_key == draft.artifact_key,
            ProductStrategyOfficeEvidenceReceipt.file_sha256 == file_sha256,
        )
    )
    if existing is not None:
        return {"outcome": "existing", "deduplicated": True, "receipt": _serialize(existing)}

    receipt_dir = OFFICE_EVIDENCE_STORAGE_ROOT / file_sha256
    receipt_dir.mkdir(parents=True, exist_ok=True)
    source_path = receipt_dir / f"source{suffix}"
    if not source_path.exists():
        temp_path = receipt_dir / f".source-{os.getpid()}{suffix}.tmp"
        temp_path.write_bytes(payload)
        temp_path.replace(source_path)

    required = [str(item).strip() for item in (required_texts or []) if str(item).strip()]
    structure = _structural_validation(suffix, payload, required)
    if bool(rendered_pdf_base64) != bool(render_engine):
        raise OfficeEvidenceError("incomplete_render_evidence", "伴随 PDF 与 Microsoft Office 导出引擎必须同时提供。")
    render = (
        _run_supplied_render_evidence(rendered_pdf_base64, render_engine, receipt_dir)
        if rendered_pdf_base64 and render_engine
        else _run_headless_roundtrip(source_path, receipt_dir)
    )
    runtime = _runtime_capability_summary()
    if rendered_pdf_base64:
        runtime["gui_open_performed"] = True
    validation = {
        "structure": structure,
        "roundtrip": {
            key: value
            for key, value in render.items()
            if key not in {"rendered_pages", "rendered_pdf_sha256", "page_count", "visual_evidence_status", "office_roundtrip_status"}
        },
        "runtime": runtime,
        "required_texts": required,
        "manual_gates": [
            "microsoft_office_real_open_not_verified" if not rendered_pdf_base64 else "microsoft_office_export_recorded_not_independently_verified",
            "named_human_visual_review_missing",
            "customer_acceptance_missing",
        ],
    }
    source_version_normalized = str(source_version or "").strip() or "unspecified"
    storage_ref = f"office-evidence/{file_sha256}/source{suffix}"
    snapshot = {
        "office_evidence_version": OFFICE_EVIDENCE_VERSION,
        "artifact_key": draft.artifact_key,
        "artifact_revision": draft.revision,
        "artifact_revision_digest": draft.revision_digest,
        "file_name": safe_name,
        "media_type": expected_media_type,
        "file_size_bytes": len(payload),
        "file_sha256": file_sha256,
        "storage_ref": storage_ref,
        "source_version": source_version_normalized,
        "validator_version": VALIDATOR_VERSION,
        "structure_status": structure["status"],
        "office_roundtrip_status": render["office_roundtrip_status"],
        "visual_evidence_status": render["visual_evidence_status"],
        "page_count": render["page_count"],
        "rendered_pdf_sha256": render["rendered_pdf_sha256"],
        "rendered_pages": render["rendered_pages"],
        "validation": validation,
        "evidence_level": "local_runtime_evidence",
        "human_review_status": "missing",
        "acceptance_status": "hold",
        "blocking_status": "blocked",
        "can_auto_accept": False,
        "can_auto_approve_release": False,
        "production_status": "not_authorized",
        "release_impact": "none",
    }
    receipt_digest = canonical_digest(snapshot)
    row = ProductStrategyOfficeEvidenceReceipt(
        receipt_key=f"{draft.artifact_key}:office:{file_sha256[:16]}",
        artifact_acceptance_draft_id=draft.id,
        artifact_key=draft.artifact_key,
        artifact_revision=draft.revision,
        artifact_revision_digest=draft.revision_digest,
        file_name=safe_name,
        media_type=expected_media_type,
        file_size_bytes=len(payload),
        file_sha256=file_sha256,
        storage_ref=storage_ref,
        source_version=source_version_normalized,
        validator_version=VALIDATOR_VERSION,
        structure_status=str(structure["status"]),
        office_roundtrip_status=str(render["office_roundtrip_status"]),
        visual_evidence_status=str(render["visual_evidence_status"]),
        page_count=int(render["page_count"]),
        rendered_pdf_sha256=render["rendered_pdf_sha256"],
        rendered_pages_payload=list(render["rendered_pages"]),
        validation_payload=validation,
        receipt_digest=receipt_digest,
        evidence_level="local_runtime_evidence",
        human_review_status="missing",
        acceptance_status="hold",
        blocking_status="blocked",
        can_auto_accept=False,
        can_auto_approve_release=False,
        production_status="not_authorized",
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        winner = db.scalar(
            select(ProductStrategyOfficeEvidenceReceipt).where(
                ProductStrategyOfficeEvidenceReceipt.artifact_key == draft.artifact_key,
                ProductStrategyOfficeEvidenceReceipt.file_sha256 == file_sha256,
            )
        )
        if winner is None:
            raise
        return {"outcome": "existing", "deduplicated": True, "receipt": _serialize(winner)}
    db.refresh(row)
    return {"outcome": "created", "deduplicated": False, "receipt": _serialize(row)}
