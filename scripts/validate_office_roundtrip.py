#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DEFAULT_BASELINE_DIR = ROOT / ".tmp" / "formal-artifact-visual-baseline"
DEFAULT_ARTIFACT_DIR = DEFAULT_BASELINE_DIR / "artifacts"
DEFAULT_MANIFEST_PATH = DEFAULT_BASELINE_DIR / "roundtrip-manifest.json"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.work_tasks.office_roundtrip import (  # noqa: E402
    detect_office_roundtrip_capabilities,
    validate_docx_bytes,
    validate_pdf_bytes,
    validate_pptx_bytes,
)


def _validate_file(path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".docx":
        result = validate_docx_bytes(payload)
    elif suffix == ".pptx":
        result = validate_pptx_bytes(payload)
    elif suffix == ".pdf":
        result = validate_pdf_bytes(payload)
    else:
        result = {"status": "skip", "reason": f"Unsupported extension: {suffix}"}
    return {"file": str(path), **result}


def _default_artifact_paths() -> list[Path]:
    if not DEFAULT_ARTIFACT_DIR.exists():
        return []
    return sorted(
        path
        for path in DEFAULT_ARTIFACT_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in {".docx", ".pptx", ".pdf"}
    )


def _quicklook(path: Path, output_dir: Path, *, timeout_seconds: int) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    qlmanage = detect_office_roundtrip_capabilities().get("quicklook_cli")
    if not qlmanage:
        return {"status": "skip", "reason": "qlmanage not available"}
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
    thumbnails = _thumbnail_fingerprints(output_dir, source_stem=path.name)
    return {
        "status": "pass" if completed.returncode == 0 else "fail",
        "returncode": completed.returncode,
        "stdout": completed.stdout[-1200:],
        "stderr": completed.stderr[-1200:],
        "output_dir": str(output_dir),
        "thumbnail_fingerprints": thumbnails,
    }


def _thumbnail_fingerprints(output_dir: Path, *, source_stem: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not output_dir.exists():
        return rows
    candidates = sorted(
        path
        for path in output_dir.iterdir()
        if path.is_file() and (source_stem in path.name or path.suffix.lower() in {".png", ".jpg", ".jpeg"})
    )
    for path in candidates:
        payload = path.read_bytes()
        rows.append(
            {
                "file": str(path),
                "size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    return rows


def _should_quicklook(path: Path, scope: str) -> bool:
    suffix = path.suffix.lower()
    if scope == "all":
        return True
    if scope == "pdf":
        return suffix == ".pdf"
    if scope == "office":
        return suffix in {".docx", ".pptx"}
    return False


def _open_gui(path: Path) -> dict[str, object]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        app = "Microsoft Word"
    elif suffix == ".pptx":
        app = "Microsoft PowerPoint"
    elif suffix == ".pdf":
        app = "Preview"
    else:
        return {"status": "skip", "reason": f"Unsupported extension: {suffix}"}
    completed = subprocess.run(
        ["open", "-a", app, str(path)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "status": "launched" if completed.returncode == 0 else "fail",
        "app": app,
        "returncode": completed.returncode,
        "stderr": completed.stderr[-1200:],
    }


def _libreoffice_convert(path: Path, output_dir: Path, *, timeout_seconds: int) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    capabilities = detect_office_roundtrip_capabilities()
    libreoffice = str(capabilities.get("libreoffice_cli") or "")
    if not libreoffice:
        return {"status": "skip", "reason": "LibreOffice CLI not available", "output_dir": str(output_dir)}
    try:
        completed = subprocess.run(
            [libreoffice, "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), str(path)],
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
            "stdout": str(exc.stdout or "")[-1600:],
            "stderr": str(exc.stderr or "")[-1600:],
            "output_dir": str(output_dir),
        }
    expected_pdf = output_dir / f"{path.stem}.pdf"
    result: dict[str, object] = {
        "status": "pass" if completed.returncode == 0 and expected_pdf.exists() else "fail",
        "returncode": completed.returncode,
        "stdout": completed.stdout[-1600:],
        "stderr": completed.stderr[-1600:],
        "output_pdf": str(expected_pdf),
        "output_dir": str(output_dir),
    }
    if expected_pdf.exists():
        result["pdf_validation"] = validate_pdf_bytes(expected_pdf.read_bytes())
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate DOCX/PPTX/PDF round-trip readiness.")
    parser.add_argument(
        "files",
        nargs="*",
        help="Artifacts to validate. Defaults to the current formal-artifact visual baseline.",
    )
    parser.add_argument("--quicklook", action="store_true", help="Render macOS QuickLook thumbnails when available.")
    parser.add_argument(
        "--quicklook-scope",
        choices=("all", "pdf", "office"),
        default="all",
        help="Limit QuickLook rendering to avoid known slow renderers such as PPTX on some macOS setups.",
    )
    parser.add_argument("--quicklook-timeout", type=int, default=20, help="Seconds allowed per QuickLook thumbnail.")
    parser.add_argument("--open-gui", action="store_true", help="Open artifacts in Word/PowerPoint/Preview for manual validation.")
    parser.add_argument("--libreoffice-convert", action="store_true", help="Convert Office artifacts to PDF through LibreOffice headless when available.")
    parser.add_argument("--libreoffice-timeout", type=int, default=60, help="Seconds allowed per LibreOffice conversion.")
    parser.add_argument("--quicklook-out", default="/tmp/af-office-roundtrip-thumbnails")
    parser.add_argument("--libreoffice-out", default="/tmp/af-office-roundtrip-libreoffice")
    parser.add_argument("--manifest-out", default="", help="Optional path to write the JSON validation manifest.")
    args = parser.parse_args()
    explicit_files = bool(args.files)
    files = [Path(raw) for raw in args.files] if explicit_files else _default_artifact_paths()
    if not files:
        parser.error(
            f"no artifacts supplied and no baseline artifacts found under {DEFAULT_ARTIFACT_DIR}; "
            "run `npm run office:visual-baseline` first"
        )
    if not explicit_files and not args.manifest_out:
        args.manifest_out = str(DEFAULT_MANIFEST_PATH)

    report = {
        "capabilities": detect_office_roundtrip_capabilities(),
        "artifacts": [],
    }
    exit_code = 0
    for raw in files:
        path = raw.expanduser().resolve()
        if not path.exists():
            report["artifacts"].append({"file": str(path), "status": "fail", "reason": "file not found"})
            exit_code = 1
            continue
        result = _validate_file(path)
        if args.quicklook and _should_quicklook(path, args.quicklook_scope):
            result["quicklook"] = _quicklook(path, Path(args.quicklook_out), timeout_seconds=max(1, args.quicklook_timeout))
        elif args.quicklook:
            result["quicklook"] = {"status": "skip", "reason": f"quicklook scope {args.quicklook_scope}"}
        if args.libreoffice_convert and path.suffix.lower() in {".docx", ".pptx"}:
            result["libreoffice_conversion"] = _libreoffice_convert(
                path,
                Path(args.libreoffice_out),
                timeout_seconds=max(1, args.libreoffice_timeout),
            )
        if args.open_gui:
            result["gui_open"] = _open_gui(path)
        if (
            result.get("status") == "fail"
            or result.get("quicklook", {}).get("status") in {"fail", "timeout"}
            or result.get("libreoffice_conversion", {}).get("status") in {"fail", "timeout"}
        ):
            exit_code = 1
        report["artifacts"].append(result)

    artifacts = [row for row in report["artifacts"] if isinstance(row, dict)]
    report["summary"] = {
        "artifact_count": len(artifacts),
        "failed_structure_count": sum(1 for row in artifacts if row.get("status") == "fail"),
        "failed_quicklook_count": sum(
            1 for row in artifacts if row.get("quicklook", {}).get("status") in {"fail", "timeout"}
        ),
        "failed_libreoffice_count": sum(
            1 for row in artifacts if row.get("libreoffice_conversion", {}).get("status") in {"fail", "timeout"}
        ),
        "quicklook_rendered_count": sum(1 for row in artifacts if row.get("quicklook", {}).get("status") == "pass"),
        "libreoffice_skipped_count": sum(
            1 for row in artifacts if row.get("libreoffice_conversion", {}).get("status") == "skip"
        ),
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.manifest_out:
        manifest_path = Path(args.manifest_out).expanduser().resolve()
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(rendered, encoding="utf-8")
    print(rendered)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
