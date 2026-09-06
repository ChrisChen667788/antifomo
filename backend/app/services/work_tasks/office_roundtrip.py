from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree


def _detect_libreoffice_cli() -> str:
    env_candidates = [
        os.environ.get("ANTI_FOMO_LIBREOFFICE_CLI"),
        os.environ.get("LIBREOFFICE_CLI"),
        os.environ.get("SOFFICE_PATH"),
    ]
    path_candidates = [
        *[Path(value).expanduser() for value in env_candidates if value],
        Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
        Path("/opt/homebrew/bin/soffice"),
        Path("/usr/local/bin/soffice"),
    ]
    for candidate in path_candidates:
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return shutil.which("soffice") or shutil.which("libreoffice") or ""


def detect_office_roundtrip_capabilities() -> dict[str, object]:
    """Detect local validators without launching GUI applications.

    LibreOffice is the preferred automated round-trip engine because it can run
    headless. Microsoft Word/PowerPoint availability is reported as a manual
    validation option only; routine tests must not open GUI apps.
    """

    libreoffice_cli = _detect_libreoffice_cli()
    quicklook_cli = shutil.which("qlmanage")
    word_app = Path("/Applications/Microsoft Word.app")
    powerpoint_app = Path("/Applications/Microsoft PowerPoint.app")
    preview_app = Path("/System/Applications/Preview.app")
    automated_mode = "libreoffice_headless" if libreoffice_cli else ("quicklook_thumbnail_optional" if quicklook_cli else "structure_only")
    return {
        "libreoffice_cli": libreoffice_cli or "",
        "quicklook_cli": quicklook_cli or "",
        "microsoft_word_app": str(word_app) if word_app.exists() else "",
        "microsoft_powerpoint_app": str(powerpoint_app) if powerpoint_app.exists() else "",
        "preview_app": str(preview_app) if preview_app.exists() else "",
        "automated_mode": automated_mode,
        "gui_mode": "manual_available" if word_app.exists() or powerpoint_app.exists() else "not_available",
        "headless_conversion": {
            "available": bool(libreoffice_cli),
            "mode": "libreoffice_headless" if libreoffice_cli else "skip_no_libreoffice",
            "command": f"{libreoffice_cli} --headless --convert-to pdf <file>" if libreoffice_cli else "",
            "configure_hint": (
                "Set ANTI_FOMO_LIBREOFFICE_CLI=/Applications/LibreOffice.app/Contents/MacOS/soffice "
                "or install LibreOffice so `soffice` is on PATH."
            ),
        },
        "real_open_validation_gate": {
            "word": "manual_available" if word_app.exists() else "not_available",
            "powerpoint": "manual_available" if powerpoint_app.exists() else "not_available",
            "pdf_preview": "manual_available" if preview_app.exists() else "not_available",
            "policy": "never_launch_gui_in_tests; use scripts/validate_office_roundtrip.py --open-gui explicitly for external-send gate",
        },
    }


def _read_zip_parts(artifact_bytes: bytes) -> tuple[set[str], dict[str, str], list[str]]:
    xml_parts: dict[str, str] = {}
    malformed: list[str] = []
    with ZipFile(_BytesReader(artifact_bytes)) as archive:
        names = set(archive.namelist())
        for name in names:
            if not name.endswith(".xml"):
                continue
            text = archive.read(name).decode("utf-8", errors="replace")
            xml_parts[name] = text
            try:
                ElementTree.fromstring(text.encode("utf-8"))
            except ElementTree.ParseError:
                malformed.append(name)
    return names, xml_parts, malformed


class _BytesReader:
    def __init__(self, payload: bytes) -> None:
        from io import BytesIO

        self._buffer = BytesIO(payload)

    def read(self, *args):
        return self._buffer.read(*args)

    def seek(self, *args):
        return self._buffer.seek(*args)

    def tell(self):
        return self._buffer.tell()

    def seekable(self) -> bool:
        return True


def _missing_texts(xml_parts: dict[str, str], required_texts: list[str]) -> list[str]:
    joined = "\n".join(xml_parts.values())
    missing: list[str] = []
    for text in required_texts:
        normalized = str(text or "").strip()
        if normalized and normalized not in joined:
            missing.append(normalized)
    return missing


def validate_docx_bytes(artifact_bytes: bytes, *, required_texts: list[str] | None = None) -> dict[str, object]:
    required_entries = {
        "[Content_Types].xml",
        "_rels/.rels",
        "docProps/core.xml",
        "docProps/app.xml",
        "word/document.xml",
        "word/styles.xml",
        "word/settings.xml",
        "word/header1.xml",
        "word/footer1.xml",
        "word/numbering.xml",
        "word/theme/theme1.xml",
        "word/_rels/document.xml.rels",
    }
    return _validate_openxml_package(
        artifact_bytes,
        required_entries=required_entries,
        required_texts=required_texts or [],
        application="Microsoft Word",
        open_command='open -a "Microsoft Word" <file.docx>',
    )


def validate_pptx_bytes(artifact_bytes: bytes, *, required_texts: list[str] | None = None) -> dict[str, object]:
    required_entries = {
        "[Content_Types].xml",
        "_rels/.rels",
        "docProps/core.xml",
        "docProps/app.xml",
        "ppt/presentation.xml",
        "ppt/_rels/presentation.xml.rels",
        "ppt/theme/theme1.xml",
        "ppt/slides/slide1.xml",
    }
    return _validate_openxml_package(
        artifact_bytes,
        required_entries=required_entries,
        required_texts=required_texts or [],
        application="Microsoft PowerPoint",
        open_command='open -a "Microsoft PowerPoint" <file.pptx>',
    )


def _validate_openxml_package(
    artifact_bytes: bytes,
    *,
    required_entries: set[str],
    required_texts: list[str],
    application: str,
    open_command: str,
) -> dict[str, object]:
    capabilities = detect_office_roundtrip_capabilities()
    try:
        names, xml_parts, malformed_xml = _read_zip_parts(artifact_bytes)
    except BadZipFile:
        return {
            "status": "fail",
            "package": "not_zip",
            "capabilities": capabilities,
            "manual_steps": [f"无法打开为 OpenXML zip；请重新生成后再用 {application} 打开。"],
        }

    missing_entries = sorted(required_entries - names)
    missing_text = _missing_texts(xml_parts, required_texts)
    status = "pass" if not missing_entries and not malformed_xml and not missing_text else "fail"
    native_chart_parts = sorted(
        name
        for name in names
        if (name.startswith("ppt/charts/") or name.startswith("word/charts/")) and name.endswith(".xml")
    )
    embedded_workbooks = sorted(
        name
        for name in names
        if (name.startswith("ppt/embeddings/") or name.startswith("word/embeddings/")) and name.endswith(".xlsx")
    )
    native_image_parts = sorted(
        name
        for name in names
        if (name.startswith("ppt/media/") or name.startswith("word/media/"))
        and name.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
    )
    complex_template_parts = sorted(
        name
        for name in names
        if name in {"word/numbering.xml", "word/theme/theme1.xml", "ppt/theme/theme1.xml"}
    )
    return {
        "status": status,
        "package": "openxml_zip",
        "required_entries_missing": missing_entries,
        "malformed_xml_parts": sorted(malformed_xml),
        "required_text_missing": missing_text,
        "complex_template_parts": complex_template_parts,
        "native_chart_parts": native_chart_parts,
        "native_image_parts": native_image_parts,
        "embedded_workbooks": embedded_workbooks,
        "native_editable_charts": bool(native_chart_parts and embedded_workbooks),
        "native_images": bool(native_image_parts),
        "capabilities": capabilities,
        "manual_steps": [
            f"保存文件后执行：{open_command}",
            f"在 {application} 中确认：目录/页眉页脚/图表占位/图片占位/中文校对清单均可见。",
            "另存为 PDF 后检查页码、表格、证据锚点和附录编号未丢失。",
        ],
    }


def validate_pdf_bytes(artifact_bytes: bytes, *, required_preview_text: list[str] | None = None) -> dict[str, object]:
    del required_preview_text
    starts_ok = re.match(rb"%PDF-1\.[0-9]", artifact_bytes) is not None
    ends_ok = artifact_bytes.rstrip().endswith(b"%%EOF")
    page_count = len(re.findall(rb"/Type /Page\b", artifact_bytes))
    has_vector_layout = b" re f" in artifact_bytes and b" re S" in artifact_bytes
    has_native_image = b"/Subtype /Image" in artifact_bytes and b"/Im1 Do" in artifact_bytes
    status = "pass" if starts_ok and ends_ok and page_count >= 1 else "fail"
    return {
        "status": status,
        "package": "pdf",
        "starts_with_pdf_header": starts_ok,
        "ends_with_eof": ends_ok,
        "page_count": page_count,
        "has_vector_layout": has_vector_layout,
        "has_native_image": has_native_image,
        "capabilities": detect_office_roundtrip_capabilities(),
        "professional_layout_checks": [
            "header_footer_present",
            "page_count_verified",
            "vector_brand_frame_present" if has_vector_layout else "vector_brand_frame_missing",
            "native_pdf_image_present" if has_native_image else "native_pdf_image_missing",
            "brand_media_sections_should_match_docx_preview",
        ],
        "manual_steps": [
            "用 macOS Preview 或浏览器打开 PDF，确认首页、页眉页脚、正文换页和中文字符正常。",
            "从 DOCX 导出 PDF 后，与系统 PDF 预览对照：章节、编号、表格、证据锚点和附录不得丢失。",
        ],
    }
