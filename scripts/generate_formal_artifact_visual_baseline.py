#!/usr/bin/env python3
from __future__ import annotations

import argparse
from base64 import b64decode
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.research.real_business_golden_samples import (  # noqa: E402
    RealBusinessGoldenSample,
    build_real_business_research_report,
    load_real_business_delivery_golden_samples,
)
from app.services.work_tasks.formal_documents import (  # noqa: E402
    build_feasibility_study_docx_document,
    build_project_proposal_pdf_document_with_diagnostics,
    build_research_solution_delivery_pptx_document,
)
from app.services.work_tasks.office_roundtrip import (  # noqa: E402
    detect_office_roundtrip_capabilities,
    validate_docx_bytes,
    validate_pdf_bytes,
    validate_pptx_bytes,
)


ArtifactBuilder = Callable[[dict, str, dict], tuple[str, str, str, str, dict[str, object]]]


def _safe_filename(value: str, *, fallback: str = "artifact") -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value).strip("-")
    return safe[:96] or fallback


def _sha256(payload: bytes | str) -> str:
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


_W3CDTF_RE = re.compile(rb"(<dcterms:(?:created|modified)[^>]*>).*?(</dcterms:(?:created|modified)>)")


def _normalized_artifact_sha256(payload: bytes) -> str:
    """Hash artifact payload content without volatile OpenXML zip metadata."""

    try:
        with ZipFile(BytesIO(payload)) as archive:
            chunks: list[bytes] = []
            for name in sorted(archive.namelist()):
                content = archive.read(name)
                if name == "docProps/core.xml":
                    content = _W3CDTF_RE.sub(rb"\1NORMALIZED\2", content)
                chunks.extend([name.encode("utf-8"), b"\0", content, b"\0"])
            return _sha256(b"".join(chunks))
    except BadZipFile:
        return _sha256(payload)


def _first(values: tuple[str, ...], *, fallback: str) -> str:
    return next((value for value in values if value), fallback)


def _numeric_chart_rows(sample: RealBusinessGoldenSample) -> list[dict[str, object]]:
    labels = [
        ("官方源", len(sample.sources)),
        ("目标账户", len(sample.target_accounts)),
        ("标杆场景", len(sample.benchmark_cases)),
        ("产品组合", len(sample.flagship_products)),
    ]
    return [{"label": label, "value": value} for label, value in labels]


def _sample_supplement(sample: RealBusinessGoldenSample) -> dict[str, object]:
    source_titles = "；".join(source.title for source in sample.sources[:3])
    return {
        "project_name": f"{sample.scenario}专项交付",
        "project_owner": sample.target_customer,
        "target_customer": sample.target_customer,
        "solution_scenario": sample.scenario,
        "vertical_scene": sample.vertical_scene,
        "project_region": "上海 / 长三角" if "长三角" in sample.topic else "上海",
        "implementation_window": _first(sample.tender_timeline, fallback="2026 年度滚动推进"),
        "investment_estimate": _first(sample.budget_signals, fallback="公开材料暂未披露金额，需按假设测算"),
        "construction_basis": f"基于真实业务黄金样本 {sample.sample_id}、公开政策/试点来源和当前研报交叉形成。",
        "scope_statement": _first(sample.strategic_directions, fallback=sample.research_focus),
        "expected_benefits": _first(sample.five_year_outlook, fallback=sample.executive_summary),
        "cross_validation_notes": f"已纳入来源：{source_titles}",
        "supplemental_context": "用于 P2.6 历史样本 artifact 视觉回归批量基线，不作为最终外发版本。",
        "supplemental_evidence": source_titles,
        "supplemental_requirements": "检查 DOCX/PPTX 原生图片嵌入、PDF 矢量版式框架和 artifact 指纹稳定性。",
        "brand_template": {
            "template_id": f"{sample.sample_id}-p26-baseline",
            "display_name": f"{sample.target_customer}专业汇报模板",
            "primary_color": "#1D4ED8",
            "secondary_color": "#047857",
            "accent_color": "#EA580C",
            "logo_text": sample.target_customer[:18],
            "confidentiality_label": "历史样本回归基线",
            "footer_text": f"Anti-FOMO P2.6 · {sample.sample_id}",
        },
        "chart_assets": [
            {
                "asset_id": f"{sample.sample_id}-evidence-chart",
                "title": "证据覆盖与业务机会指标图",
                "description": "用于基线验证的原生可编辑图表数据源。",
                "source": "real_business_delivery_golden_v1",
                "unit": "数量/评分",
                "period": "2026",
                "replacement_slot": "chart-evidence-opportunity",
                "data": _numeric_chart_rows(sample),
            }
        ],
        "image_assets": [
            {
                "asset_id": f"{sample.sample_id}-scenario-image",
                "title": f"{sample.vertical_scene[:28]}场景示意图",
                "description": "用于基线验证的原生图片占位；外发前替换为授权图片或架构图。",
                "source": "real_business_delivery_golden_v1",
                "unit": "16:9 PNG",
                "period": "2026",
                "replacement_slot": "image-scenario-baseline",
                "data": [
                    {"label": "目标客户", "value": sample.target_customer},
                    {"label": "场景", "value": sample.vertical_scene},
                ],
            }
        ],
        "renderer_strategy": (
            "P2.6 视觉回归基线：结构校验默认执行；可选 QuickLook 缩略图 fingerprint；"
            "LibreOffice/GUI Office 仍作为外发前门禁。"
        ),
    }


def _artifact_builders() -> list[tuple[str, ArtifactBuilder]]:
    return [
        ("feasibility_docx", build_feasibility_study_docx_document),
        ("solution_pptx", build_research_solution_delivery_pptx_document),
        ("project_proposal_pdf", build_project_proposal_pdf_document_with_diagnostics),
    ]


def _validate_artifact(path: Path, payload: bytes) -> dict[str, object]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return validate_docx_bytes(payload)
    if suffix == ".pptx":
        return validate_pptx_bytes(payload)
    if suffix == ".pdf":
        return validate_pdf_bytes(payload)
    return {"status": "skip", "reason": f"unsupported suffix: {suffix}"}


def _thumbnail_fingerprints(output_dir: Path) -> list[dict[str, object]]:
    if not output_dir.exists():
        return []
    rows: list[dict[str, object]] = []
    for path in sorted(output_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            continue
        payload = path.read_bytes()
        rows.append({"file": str(path), "size_bytes": len(payload), "sha256": _sha256(payload)})
    return rows


def _quicklook(path: Path, output_dir: Path, *, timeout_seconds: int) -> dict[str, object]:
    qlmanage = detect_office_roundtrip_capabilities().get("quicklook_cli")
    if not qlmanage:
        return {"status": "skip", "reason": "qlmanage not available"}
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(
            [str(qlmanage), "-t", "-s", "1200", "-o", str(output_dir), str(path)],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "timeout_seconds": timeout_seconds,
            "stdout": str(exc.stdout or "")[-1200:],
            "stderr": str(exc.stderr or "")[-1200:],
            "output_dir": str(output_dir),
        }
    return {
        "status": "pass" if completed.returncode == 0 else "fail",
        "returncode": completed.returncode,
        "stdout": completed.stdout[-1200:],
        "stderr": completed.stderr[-1200:],
        "output_dir": str(output_dir),
        "thumbnail_fingerprints": _thumbnail_fingerprints(output_dir),
    }


def _build_baseline(
    *,
    output_dir: Path,
    limit: int,
    quicklook: bool,
    quicklook_all: bool,
    quicklook_timeout: int,
) -> dict[str, object]:
    samples = list(load_real_business_delivery_golden_samples())
    if limit > 0:
        samples = samples[:limit]
    artifact_dir = output_dir / "artifacts"
    quicklook_dir = output_dir / "quicklook"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, object] = {
        "baseline_id": "anti-fomo-p2.6-formal-artifact-visual-baseline",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "dataset": "backend/evaluation/real_business_delivery_golden_v1.json",
        "capabilities": detect_office_roundtrip_capabilities(),
        "quicklook_enabled": quicklook,
        "quicklook_scope": "all" if quicklook_all else ("pdf" if quicklook else "none"),
        "samples": [],
        "artifacts": [],
    }
    artifacts: list[dict[str, object]] = []
    for sample in samples:
        report = build_real_business_research_report(sample)
        supplement = _sample_supplement(sample)
        sample_artifacts: list[str] = []
        for artifact_kind, builder in _artifact_builders():
            original_filename, preview_text, content_base64, mime_type, diagnostics = builder(
                report.model_dump(mode="json"),
                output_language="zh-CN",
                delivery_supplement=supplement,
            )
            payload = b64decode(content_base64)
            suffix = Path(original_filename).suffix or ".bin"
            output_name = f"{_safe_filename(sample.sample_id)}-{artifact_kind}{suffix}"
            output_path = artifact_dir / output_name
            output_path.write_bytes(payload)
            validation = _validate_artifact(output_path, payload)
            should_quicklook = bool(quicklook and (quicklook_all or suffix.lower() == ".pdf"))
            quicklook_result = (
                _quicklook(
                    output_path,
                    quicklook_dir / output_path.stem,
                    timeout_seconds=max(1, quicklook_timeout),
                )
                if should_quicklook
                else {
                    "status": "skip",
                    "reason": "quicklook disabled" if not quicklook else "quicklook pdf-only scope",
                }
            )
            visual_regression = diagnostics.get("visual_regression") if isinstance(diagnostics, dict) else {}
            artifact_row: dict[str, object] = {
                "sample_id": sample.sample_id,
                "topic": sample.topic,
                "artifact_kind": artifact_kind,
                "file": str(output_path),
                "original_filename": original_filename,
                "mime_type": mime_type,
                "size_bytes": len(payload),
                "sha256": _sha256(payload),
                "normalized_sha256": _normalized_artifact_sha256(payload),
                "preview_sha256": _sha256(preview_text),
                "visual_fingerprint": (
                    visual_regression.get("fingerprint")
                    if isinstance(visual_regression, dict)
                    else ""
                ),
                "diagnostics": diagnostics,
                "validation": validation,
                "quicklook": quicklook_result,
            }
            artifacts.append(artifact_row)
            sample_artifacts.append(str(output_path))
        manifest["samples"].append(
            {
                "sample_id": sample.sample_id,
                "topic": sample.topic,
                "artifact_files": sample_artifacts,
                "source_count": len(sample.sources),
            }
        )
    manifest["artifacts"] = artifacts
    manifest["summary"] = {
        "sample_count": len(samples),
        "artifact_count": len(artifacts),
        "failed_validation_count": sum(1 for row in artifacts if row.get("validation", {}).get("status") == "fail"),
        "failed_quicklook_count": sum(1 for row in artifacts if row.get("quicklook", {}).get("status") in {"fail", "timeout"}),
    }
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate visual-regression baselines for formal delivery artifacts.")
    parser.add_argument("--output-dir", default="/tmp/af-formal-artifact-visual-baseline", help="Directory for generated artifacts and manifest.")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of real-business samples; 0 means all.")
    parser.add_argument("--quicklook", action="store_true", help="Render macOS QuickLook thumbnails for PDF artifacts and include image hashes.")
    parser.add_argument("--quicklook-all", action="store_true", help="Also try DOCX/PPTX QuickLook thumbnails; this can be slow or timeout on some macOS setups.")
    parser.add_argument("--quicklook-timeout", type=int, default=20, help="Seconds allowed per QuickLook thumbnail.")
    parser.add_argument("--manifest-name", default="visual-baseline-manifest.json", help="Manifest filename inside output-dir.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = _build_baseline(
        output_dir=output_dir,
        limit=max(0, args.limit),
        quicklook=bool(args.quicklook),
        quicklook_all=bool(args.quicklook_all),
        quicklook_timeout=max(1, args.quicklook_timeout),
    )
    manifest_path = output_dir / args.manifest_name
    rendered = json.dumps(manifest, ensure_ascii=False, indent=2)
    manifest_path.write_text(rendered, encoding="utf-8")
    print(rendered)
    summary = manifest.get("summary", {})
    if summary.get("failed_validation_count") or summary.get("failed_quicklook_count"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
