from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
import re
import tempfile
from typing import Iterable
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile


PARSER_VERSION = "1.9.2-native-v1"


@dataclass(frozen=True)
class ParsedPassage:
    text: str
    sequence: int
    page_number: int | None = None
    paragraph_number: int | None = None
    start_seconds: int | None = None
    end_seconds: int | None = None
    locator: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedDocument:
    text: str
    passages: tuple[ParsedPassage, ...]
    parser_name: str
    parser_version: str
    warnings: tuple[str, ...] = ()


class _VisibleHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._ignored_depth += 1
        elif tag.lower() in {"p", "div", "li", "br", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1
        elif tag.lower() in {"p", "div", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def _normalize(value: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line)


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "gb18030", "latin-1"):
        try:
            decoded = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        normalized = _normalize(decoded)
        if normalized:
            return normalized
    return ""


def _split_passages(
    paragraphs: Iterable[tuple[str, dict[str, object]]],
    *,
    max_chars: int = 1000,
) -> tuple[ParsedPassage, ...]:
    passages: list[ParsedPassage] = []
    for paragraph_index, (raw_text, locator) in enumerate(paragraphs, start=1):
        text = _normalize(raw_text)
        if not text:
            continue
        chunks = [text[index : index + max_chars] for index in range(0, len(text), max_chars)]
        for chunk_index, chunk in enumerate(chunks, start=1):
            normalized_locator = dict(locator)
            if len(chunks) > 1:
                normalized_locator["chunk"] = chunk_index
            passages.append(
                ParsedPassage(
                    text=chunk,
                    sequence=len(passages) + 1,
                    page_number=_optional_int(normalized_locator.get("page")),
                    paragraph_number=_optional_int(normalized_locator.get("paragraph")) or paragraph_index,
                    start_seconds=_optional_int(normalized_locator.get("start_seconds")),
                    end_seconds=_optional_int(normalized_locator.get("end_seconds")),
                    locator=normalized_locator,
                )
            )
    return tuple(passages)


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _xml_texts(xml_bytes: bytes) -> list[str]:
    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError:
        return []
    texts: list[str] = []
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] in {"t", "tab", "br"}:
            if node.tag.endswith("tab"):
                texts.append("\t")
            elif node.tag.endswith("br"):
                texts.append("\n")
            elif node.text:
                texts.append(node.text)
    return texts


def _parse_docx(data: bytes) -> list[tuple[str, dict[str, object]]]:
    with ZipFile(BytesIO(data)) as archive:
        xml_bytes = archive.read("word/document.xml")
    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError:
        return []
    rows: list[tuple[str, dict[str, object]]] = []
    paragraph = 0
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] != "p":
            continue
        text = _normalize("".join(_xml_texts(ElementTree.tostring(node, encoding="utf-8"))))
        if text:
            paragraph += 1
            rows.append((text, {"paragraph": paragraph, "format": "docx"}))
    return rows


def _numeric_suffix(value: str) -> int:
    match = re.search(r"(\d+)(?=\D*$)", value)
    return int(match.group(1)) if match else 0


def _parse_pptx(data: bytes) -> list[tuple[str, dict[str, object]]]:
    rows: list[tuple[str, dict[str, object]]] = []
    with ZipFile(BytesIO(data)) as archive:
        names = sorted(
            (name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
            key=_numeric_suffix,
        )
        for slide_number, name in enumerate(names, start=1):
            text = _normalize(" ".join(_xml_texts(archive.read(name))))
            if text:
                rows.append((text, {"page": slide_number, "paragraph": 1, "format": "pptx"}))
    return rows


def _parse_xlsx(data: bytes) -> list[tuple[str, dict[str, object]]]:
    rows: list[tuple[str, dict[str, object]]] = []
    with ZipFile(BytesIO(data)) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared = _xml_texts(archive.read("xl/sharedStrings.xml"))
        sheet_names = sorted(
            (name for name in archive.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)),
            key=_numeric_suffix,
        )
        for sheet_number, name in enumerate(sheet_names, start=1):
            try:
                root = ElementTree.fromstring(archive.read(name))
            except ElementTree.ParseError:
                continue
            row_number = 0
            for row in root.iter():
                if row.tag.rsplit("}", 1)[-1] != "row":
                    continue
                row_number += 1
                cells: list[str] = []
                for cell in row:
                    if cell.tag.rsplit("}", 1)[-1] != "c":
                        continue
                    cell_type = cell.attrib.get("t")
                    value_node = next((node for node in cell if node.tag.rsplit("}", 1)[-1] == "v"), None)
                    if value_node is None or value_node.text is None:
                        continue
                    value = value_node.text
                    if cell_type == "s" and value.isdigit() and int(value) < len(shared):
                        value = shared[int(value)]
                    cells.append(value)
                text = _normalize(" | ".join(cells))
                if text:
                    rows.append((text, {"sheet": sheet_number, "row": row_number, "format": "xlsx"}))
    return rows


def _decode_pdf_literal(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        token = match.group(1)
        if token.isdigit():
            try:
                return chr(int(token, 8))
            except ValueError:
                return ""
        return {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", "(": "(", ")": ")"}.get(token, token)

    return re.sub(r"\\([0-7]{1,3}|.)", replace, value)


def _parse_pdf(data: bytes) -> tuple[list[tuple[str, dict[str, object]]], str]:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]

        reader = PdfReader(BytesIO(data), strict=False)
        rows = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = _normalize(page.extract_text() or "")
            if text:
                rows.append((text, {"page": page_number, "paragraph": 1, "format": "pdf"}))
        if rows:
            return rows, "pypdf"
    except Exception:
        pass
    raw = data.decode("latin-1", errors="ignore")
    parts = [_decode_pdf_literal(match.group(1)) for match in re.finditer(r"\((.*?)\)\s*Tj", raw, re.S)]
    for match in re.finditer(r"\[(.*?)\]\s*TJ", raw, re.S):
        value = " ".join(_decode_pdf_literal(item) for item in re.findall(r"\((.*?)\)", match.group(1), re.S))
        if value:
            parts.append(value)
    text = _normalize(" ".join(parts))
    rows = [(text, {"page": 1, "paragraph": 1, "format": "pdf"})] if text else []
    return rows, "native_pdf_basic"


def _native_parse(data: bytes, *, file_name: str, mime_type: str) -> tuple[list[tuple[str, dict[str, object]]], str]:
    suffix = Path(file_name).suffix.lower()
    lowered_mime = mime_type.lower()
    try:
        if suffix == ".docx" or "wordprocessingml" in lowered_mime:
            return _parse_docx(data), "native_docx"
        if suffix == ".pptx" or "presentationml" in lowered_mime:
            return _parse_pptx(data), "native_pptx"
        if suffix == ".xlsx" or "spreadsheetml" in lowered_mime:
            return _parse_xlsx(data), "native_xlsx"
    except (BadZipFile, KeyError):
        return [], "invalid_ooxml"
    if suffix == ".pdf" or lowered_mime == "application/pdf":
        return _parse_pdf(data)
    if suffix in {".html", ".htm"} or lowered_mime in {"text/html", "application/xhtml+xml"}:
        parser = _VisibleHTMLParser()
        parser.feed(data.decode("utf-8", errors="ignore"))
        text = _normalize("".join(parser.parts))
        return [(line, {"paragraph": index, "format": "html"}) for index, line in enumerate(text.splitlines(), 1)], "native_html"
    text = _decode_text(data)
    return [(line, {"paragraph": index, "format": "text"}) for index, line in enumerate(text.splitlines(), 1)], "native_text"


def _docling_parse(data: bytes, *, file_name: str) -> ParsedDocument | None:
    try:
        from docling.document_converter import DocumentConverter  # type: ignore[import-not-found]
    except ImportError:
        return None
    suffix = Path(file_name).suffix or ".bin"
    with tempfile.NamedTemporaryFile(suffix=suffix) as handle:
        handle.write(data)
        handle.flush()
        result = DocumentConverter().convert(handle.name)
    markdown = _normalize(result.document.export_to_markdown())
    if not markdown:
        return None
    passages = _split_passages(
        (line, {"paragraph": index, "format": suffix.lstrip(".")})
        for index, line in enumerate(markdown.splitlines(), start=1)
    )
    return ParsedDocument(
        text="\n".join(passage.text for passage in passages),
        passages=passages,
        parser_name="docling",
        parser_version=str(getattr(result, "version", "unknown")),
    )


def parse_document(
    data: bytes,
    *,
    file_name: str,
    mime_type: str,
    prefer_docling: bool = False,
) -> ParsedDocument:
    warnings: list[str] = []
    if prefer_docling:
        docling = _docling_parse(data, file_name=file_name)
        if docling is not None:
            return docling
        warnings.append("Docling unavailable or returned no content; native parser used.")
    rows, parser_name = _native_parse(data, file_name=file_name, mime_type=mime_type)
    passages = _split_passages(rows)
    if not passages:
        warnings.append("No extractable passage was found.")
    return ParsedDocument(
        text="\n".join(passage.text for passage in passages),
        passages=passages,
        parser_name=parser_name,
        parser_version=PARSER_VERSION,
        warnings=tuple(warnings),
    )
