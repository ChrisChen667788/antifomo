from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Iterable, Literal, Mapping, Sequence
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

import numpy as np

from app.core.config import get_settings
from app.services.content_extractor import normalize_text
from app.services.research_rag_quality_service import rerank_sources_cross_encoder


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAG_SCHEMA_VERSION = "industry-local-rag-v1"
RAG_DIR_NAME = "rag"
RAG_DATABASE_NAME = "industry_knowledge.sqlite3"
RAG_VECTOR_NAME = "industry_passages.npy"
RAG_VECTOR_METADATA_NAME = "industry_passages.metadata.json"
RAG_MANIFEST_NAME = "manifest.json"
VISION_OCR_SOURCE = PROJECT_ROOT / "scripts" / "industry_vision_ocr.swift"
DEFAULT_PASSAGE_CHARS = 840
IndustryKnowledgeRetrievalStrategy = Literal[
    "baseline_hybrid",
    "prefilter_weighted_hybrid",
    "prefilter_weighted_rerank",
]
DEFAULT_INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGY: IndustryKnowledgeRetrievalStrategy = "baseline_hybrid"


@dataclass(frozen=True, slots=True)
class IndustryKnowledgeRetrievalStrategySpec:
    key: IndustryKnowledgeRetrievalStrategy
    label: str
    description: str
    lexical_prefilter: bool
    bm25_weights: tuple[float, float, float] | None
    rerank: bool = False
    rerank_top_k: int = 20
    candidate_multiplier: int = 1


# The baseline deliberately preserves the original production behavior.  The
# other two arms are only selected explicitly by the benchmark/API caller.
INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGIES: dict[
    IndustryKnowledgeRetrievalStrategy, IndustryKnowledgeRetrievalStrategySpec
] = {
    "baseline_hybrid": IndustryKnowledgeRetrievalStrategySpec(
        key="baseline_hybrid",
        label="当前基线：混合检索",
        description="全库 BM25 取候选后再按范围过滤，并与向量结果做 RRF 融合。",
        lexical_prefilter=False,
        bm25_weights=None,
    ),
    "prefilter_weighted_hybrid": IndustryKnowledgeRetrievalStrategySpec(
        key="prefilter_weighted_hybrid",
        label="候选 A：预过滤 + 标题加权",
        description="先在 SQL 中按行业和资料类型过滤，再提高标题字段的 BM25 权重。",
        lexical_prefilter=True,
        bm25_weights=(0.0, 1.0, 3.0),
    ),
    "prefilter_weighted_rerank": IndustryKnowledgeRetrievalStrategySpec(
        key="prefilter_weighted_rerank",
        label="候选 B：预过滤 + 标题加权 + 复排",
        description="在候选 A 的基础上扩大混合候选池，并对前排资料执行可追溯复排。",
        lexical_prefilter=True,
        bm25_weights=(0.0, 1.0, 3.0),
        rerank=True,
        rerank_top_k=20,
        candidate_multiplier=8,
    ),
}
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?；;])\s*|\n+")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)")
_LANDLINE_RE = re.compile(r"(?<!\d)0\d{2,3}[-\s]?\d{7,8}(?!\d)")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_SECRET_LABEL_VALUE_RE = re.compile(
    r"(?i)(?:密码|口令|访问密钥|密钥|password|passwd|pwd|api[ _-]?key|secret(?:[ _-]?key)?|access[ _-]?key(?:[ _-]?(?:id|secret))?|ak[ _-]?(?:id|secret))\s*(?:[（(\[{:：=]\s*)?[A-Za-z0-9][A-Za-z0-9._~+/=@#$%^&*!-]{3,}"
)
_CREDENTIAL_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])(?=[A-Za-z0-9._~+/=@#$%^&*!-]{6,}(?![A-Za-z0-9]))(?=[A-Za-z0-9._~+/=@#$%^&*!-]*[A-Za-z])(?=[A-Za-z0-9._~+/=@#$%^&*!-]*\d)(?=[A-Za-z0-9._~+/=@#$%^&*!-]*[@#$%^&*!])[A-Za-z0-9._~+/=@#$%^&*!-]{6,}(?![A-Za-z0-9])"
)
_INSTRUCTION_MARKERS = (
    "ignore previous",
    "ignore all previous",
    "system prompt",
    "developer message",
    "忽略此前",
    "忽略之前",
    "忽略所有",
    "执行以下指令",
    "系统提示",
    "开发者消息",
)
_BOILERPLATE_MARKERS = (
    "感谢您下载",
    "请勿复制",
    "请勿传播",
    "维权",
    "索取赔偿",
    "版权声明",
    "免责声明",
    "仅供参考",
)
_SUMMARY_MARKERS = (
    "市场",
    "行业",
    "趋势",
    "发展",
    "技术",
    "应用",
    "方案",
    "政策",
    "建议",
    "需要",
    "风险",
    "用户",
    "企业",
    "产品",
    "服务",
    "数据",
    "模型",
)

# A local SentenceTransformer can consume substantial unified memory on MPS.
# lru_cache alone permits concurrent cache misses, so the first burst of HTTP
# requests could instantiate the model multiple times.  Keep model loading and
# local inference single-flight per process.
_SENTENCE_TRANSFORMER_CACHE_LOCK = RLock()
_LOCAL_EMBEDDING_INFERENCE_LOCK = RLock()


@dataclass(slots=True)
class LocalContentUnit:
    ordinal: int
    locator: str
    text: str


@dataclass(slots=True)
class LocalDocumentAnalysis:
    extraction_status: str
    source_format: str
    total_unit_count: int
    extracted_unit_count: int
    content_char_count: int
    units: list[LocalContentUnit] = field(default_factory=list)
    full_text: str = ""
    ocr_used: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LocalEmbeddingBackend:
    model_name: str
    requested_model: str
    device: str
    cache_dir: str = ""
    fallback_reason: str = ""

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=np.float32)
        with _LOCAL_EMBEDDING_INFERENCE_LOCK:
            model = _get_sentence_transformer(self.model_name, self.device, self.cache_dir)
            values = model.encode(
                [normalize_text(text)[:6000] for text in texts],
                batch_size=max(1, min(int(get_settings().decision_embedding_batch_size or 8), 16)),
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        return np.asarray(values, dtype=np.float32)

    @property
    def dimension(self) -> int:
        model = _get_sentence_transformer(self.model_name, self.device, self.cache_dir)
        if hasattr(model, "get_embedding_dimension"):
            return int(model.get_embedding_dimension())
        return int(model.get_sentence_embedding_dimension())


def _clean_text(value: str) -> str:
    return normalize_text(_CONTROL_CHARS_RE.sub(" ", value or ""))


def _page_count(path: Path, *, pdf_password: str | None = None) -> int:
    command = ["pdfinfo"]
    if pdf_password:
        command.extend(["-upw", pdf_password])
    command.append(str(path))
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 0
    match = re.search(r"^Pages:\s*(\d+)", completed.stdout.decode("utf-8", errors="ignore"), re.MULTILINE)
    return int(match.group(1)) if match else 0


def _pdf_text_units(path: Path, *, pdf_password: str | None = None) -> tuple[list[LocalContentUnit], int, str]:
    page_count = _page_count(path, pdf_password=pdf_password)
    command = ["pdftotext", "-raw"]
    if pdf_password:
        command.extend(["-upw", pdf_password])
    command.extend([str(path), "-"])
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return [], page_count, "extract_timeout"
    except OSError:
        return [], page_count, "extractor_unavailable"
    raw_pages = completed.stdout.decode("utf-8", errors="ignore").split("\f")
    units = [
        LocalContentUnit(ordinal=index, locator=f"第 {index} 页", text=text)
        for index, raw_page in enumerate(raw_pages, start=1)
        if (text := _clean_text(raw_page))
    ]
    if units:
        return units, page_count or len(raw_pages), "full_text_analyzed"
    return [], page_count, "extract_failed" if completed.returncode else "empty_text"


def _pptx_text_units(path: Path) -> tuple[list[LocalContentUnit], str]:
    units: list[LocalContentUnit] = []
    try:
        with ZipFile(path) as archive:
            slide_paths = sorted(
                name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
            )
            for ordinal, slide_path in enumerate(slide_paths, start=1):
                root = ElementTree.fromstring(archive.read(slide_path))
                text = _clean_text(
                    " ".join(
                        element.text or ""
                        for element in root.iter()
                        if element.tag.rsplit("}", 1)[-1] == "t" and (element.text or "").strip()
                    )
                )
                if text:
                    units.append(LocalContentUnit(ordinal=ordinal, locator=f"第 {ordinal} 张幻灯片", text=text))
    except (BadZipFile, KeyError, OSError, ElementTree.ParseError):
        return [], "extract_failed"
    return (units, "full_text_analyzed") if units else ([], "empty_text")


def prepare_macos_vision_ocr_binary(library_dir: Path) -> tuple[Path | None, str]:
    if os.uname().sysname != "Darwin":
        return None, "当前系统不支持 macOS Vision OCR。"
    if not VISION_OCR_SOURCE.is_file():
        return None, "macOS Vision OCR 源码不存在。"
    binary = library_dir / ".tools" / "industry-vision-ocr"
    try:
        if binary.is_file() and binary.stat().st_mtime_ns >= VISION_OCR_SOURCE.stat().st_mtime_ns:
            return binary, ""
        binary.parent.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            ["swiftc", str(VISION_OCR_SOURCE), "-o", str(binary)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"macOS Vision OCR 编译失败：{type(exc).__name__}。"
    if completed.returncode:
        return None, "macOS Vision OCR 编译失败。"
    return binary, ""


def _vision_ocr_units(path: Path, binary: Path, page_count: int) -> tuple[list[LocalContentUnit], str]:
    try:
        completed = subprocess.run(
            [str(binary), "--input", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=max(900, page_count * 45),
        )
    except subprocess.TimeoutExpired:
        return [], "ocr_timeout"
    except OSError:
        return [], "ocr_failed"
    units: list[LocalContentUnit] = []
    for line in completed.stdout.decode("utf-8", errors="ignore").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        text = _clean_text(str(item.get("text") or ""))
        page = int(item.get("page") or 0)
        if text and page:
            units.append(LocalContentUnit(ordinal=page, locator=f"第 {page} 页（OCR）", text=text))
    if units:
        return units, "ocr_full_text_analyzed"
    return [], "ocr_failed" if completed.returncode else "ocr_empty_text"


def _aggregate_archive_analyses(
    member_analyses: Sequence[tuple[str, LocalDocumentAnalysis]],
) -> LocalDocumentAnalysis:
    units: list[LocalContentUnit] = []
    warnings: list[str] = []
    total_unit_count = 0
    ocr_used = False
    pending_ocr = False
    for member_name, analysis in member_analyses:
        total_unit_count += analysis.total_unit_count
        ocr_used = ocr_used or analysis.ocr_used
        pending_ocr = pending_ocr or analysis.extraction_status == "ocr_pending"
        for unit in analysis.units:
            units.append(
                LocalContentUnit(
                    ordinal=len(units) + 1,
                    locator=f"{member_name} / {unit.locator}",
                    text=unit.text,
                )
            )
        if not analysis.units:
            warnings.append(f"归档内文件未提取到可用正文：{member_name}（{analysis.extraction_status}）。")
        warnings.extend(analysis.warnings)
    full_text = "\n".join(unit.text for unit in units)
    if units:
        status = "ocr_full_text_analyzed" if ocr_used else "full_text_analyzed"
    elif pending_ocr:
        status = "ocr_pending"
    else:
        status = "archive_empty"
    return LocalDocumentAnalysis(
        extraction_status=status,
        source_format="rar",
        total_unit_count=total_unit_count,
        extracted_unit_count=len(units),
        content_char_count=len(full_text),
        units=units,
        full_text=full_text,
        ocr_used=ocr_used,
        warnings=warnings,
    )


def _password_candidates_from_files(paths: Sequence[Path]) -> list[str]:
    labelled_candidates: list[str] = []
    fallback_candidates: list[str] = []

    def add_candidate(target: list[str], value: str) -> None:
        if 1 <= len(value) <= 160 and value not in target:
            target.append(value)
        ascii_suffix = re.search(r"([A-Za-z0-9][A-Za-z0-9._@#%+\-]{2,})$", value)
        if ascii_suffix:
            normalized_suffix = ascii_suffix.group(1)
            if normalized_suffix not in target:
                target.append(normalized_suffix)

    for path in paths:
        try:
            raw_bytes = path.read_bytes()
        except OSError:
            continue
        decoded_values: list[tuple[int, str]] = []
        for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "gb18030", "gbk"):
            try:
                raw_text = raw_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
            printable_count = sum(char.isprintable() or char in "\n\r\t" for char in raw_text)
            usable_count = sum(char.isascii() and char.isalnum() or "\u4e00" <= char <= "\u9fff" for char in raw_text)
            score = printable_count * 2 + usable_count * 2 - raw_text.count("\x00") * 6
            decoded_values.append((score, raw_text))
        if not decoded_values:
            continue
        raw_text = max(decoded_values, key=lambda item: item[0])[1]
        for raw_line in raw_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            match = re.search(r"(?:密码|password)\s*[:：=]?\s*(.+)$", line, re.IGNORECASE)
            candidate = (match.group(1) if match else line).strip().strip("'\"")
            add_candidate(labelled_candidates if match else fallback_candidates, candidate)
    return (labelled_candidates or fallback_candidates)[:8]


def _rar_content_analysis(path: Path, *, ocr_binary: Path | None) -> LocalDocumentAnalysis:
    executable = shutil.which("bsdtar")
    if not executable:
        return LocalDocumentAnalysis(
            extraction_status="archive_extractor_unavailable",
            source_format="rar",
            total_unit_count=0,
            extracted_unit_count=0,
            content_char_count=0,
            warnings=["RAR 归档解析器不可用。"],
        )
    try:
        listing = subprocess.run(
            [executable, "-tf", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return LocalDocumentAnalysis(
            extraction_status="archive_extract_failed",
            source_format="rar",
            total_unit_count=0,
            extracted_unit_count=0,
            content_char_count=0,
            warnings=[f"RAR 目录读取失败：{type(exc).__name__}。"],
        )
    member_names = []
    password_member_names = []
    for raw_name in listing.stdout.decode("utf-8", errors="ignore").splitlines():
        candidate = Path(raw_name.strip())
        if (
            not raw_name.strip()
            or candidate.is_absolute()
            or ".." in candidate.parts
            or candidate.suffix.casefold() not in {".pdf", ".pptx"}
        ):
            if (
                raw_name.strip()
                and not candidate.is_absolute()
                and ".." not in candidate.parts
                and candidate.suffix.casefold() == ".txt"
                and ("密码" in candidate.name or "password" in candidate.name.casefold())
            ):
                password_member_names.append(str(candidate))
            continue
        member_names.append(str(candidate))
    member_names = sorted(set(member_names))[:80]
    password_member_names = sorted(set(password_member_names))[:8]
    if listing.returncode or not member_names:
        return LocalDocumentAnalysis(
            extraction_status="archive_empty",
            source_format="rar",
            total_unit_count=0,
            extracted_unit_count=0,
            content_char_count=0,
            warnings=["RAR 中没有可解析的 PDF 或 PPTX 正文文件。"],
        )
    with tempfile.TemporaryDirectory(prefix="anti-fomo-industry-rar-") as temporary_dir:
        extraction_root = Path(temporary_dir)
        try:
            extracted = subprocess.run(
                [
                    executable,
                    "-xf",
                    str(path),
                    "-C",
                    str(extraction_root),
                    *member_names,
                    *password_member_names,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=300,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return LocalDocumentAnalysis(
                extraction_status="archive_extract_failed",
                source_format="rar",
                total_unit_count=0,
                extracted_unit_count=0,
                content_char_count=0,
                warnings=[f"RAR 内容解压失败：{type(exc).__name__}。"],
            )
        if extracted.returncode:
            return LocalDocumentAnalysis(
                extraction_status="archive_extract_failed",
                source_format="rar",
                total_unit_count=0,
                extracted_unit_count=0,
                content_char_count=0,
                warnings=["RAR 内容解压失败。"],
            )
        password_paths = [
            (extraction_root / member_name).resolve()
            for member_name in password_member_names
            if (extraction_root / member_name).resolve().is_relative_to(extraction_root.resolve())
        ]
        pdf_passwords = _password_candidates_from_files([path for path in password_paths if path.is_file()])
        analyses: list[tuple[str, LocalDocumentAnalysis]] = []
        for member_name in member_names:
            member_path = (extraction_root / member_name).resolve()
            if not member_path.is_relative_to(extraction_root.resolve()) or not member_path.is_file():
                continue
            analyses.append(
                (
                    member_name,
                    analyze_document_content(
                        member_path,
                        ocr_binary=ocr_binary,
                        pdf_passwords=pdf_passwords,
                    ),
                )
            )
    return _aggregate_archive_analyses(analyses)


def analyze_document_content(
    path: Path,
    *,
    ocr_binary: Path | None = None,
    pdf_passwords: Sequence[str] = (),
) -> LocalDocumentAnalysis:
    suffix = path.suffix.casefold()
    if suffix == ".pdf":
        password_candidates = ["", *[str(value) for value in pdf_passwords if str(value)]]
        units: list[LocalContentUnit] = []
        total_units = 0
        status = "empty_text"
        for candidate in password_candidates:
            units, total_units, status = _pdf_text_units(path, pdf_password=candidate or None)
            if units:
                break
        ocr_used = False
        warnings: list[str] = []
        if not units and status in {"empty_text", "extract_failed"}:
            if ocr_binary is None:
                status = "ocr_pending"
                warnings.append("PDF 没有可提取文本，等待 macOS Vision OCR。")
            else:
                units, status = _vision_ocr_units(path, ocr_binary, total_units)
                ocr_used = bool(units)
                if not units:
                    warnings.append("OCR 未提取到可用文本，需要人工检查原件。")
        full_text = "\n".join(unit.text for unit in units)
        return LocalDocumentAnalysis(
            extraction_status=status,
            source_format="pdf",
            total_unit_count=total_units,
            extracted_unit_count=len(units),
            content_char_count=len(full_text),
            units=units,
            full_text=full_text,
            ocr_used=ocr_used,
            warnings=warnings,
        )
    if suffix == ".pptx":
        units, status = _pptx_text_units(path)
        full_text = "\n".join(unit.text for unit in units)
        return LocalDocumentAnalysis(
            extraction_status=status,
            source_format="pptx",
            total_unit_count=max((unit.ordinal for unit in units), default=0),
            extracted_unit_count=len(units),
            content_char_count=len(full_text),
            units=units,
            full_text=full_text,
        )
    if suffix == ".rar":
        return _rar_content_analysis(path, ocr_binary=ocr_binary)
    return LocalDocumentAnalysis(
        extraction_status="unsupported_format",
        source_format=suffix.lstrip(".") or "unknown",
        total_unit_count=0,
        extracted_unit_count=0,
        content_char_count=0,
        warnings=["该文件格式未纳入本地文本/RAG 解析器。"],
    )


def _split_passages(text: str, *, max_chars: int = DEFAULT_PASSAGE_CHARS) -> list[str]:
    normalized = _clean_text(text)
    if not normalized:
        return []
    sentences = [
        item
        for item in _SENTENCE_SPLIT_RE.split(normalized)
        if item and not _looks_like_instruction(item)
    ]
    if not sentences:
        sentences = [normalized]
    passages: list[str] = []
    current: list[str] = []
    length = 0
    for sentence in sentences:
        while len(sentence) > max_chars:
            if current:
                passages.append(" ".join(current))
                current, length = [], 0
            passages.append(sentence[:max_chars])
            sentence = sentence[max_chars - 80 :]
        next_length = length + len(sentence) + 1
        if current and next_length > max_chars:
            passages.append(" ".join(current))
            current = current[-1:] if len(current[-1]) < 160 else []
            length = sum(len(item) for item in current)
        current.append(sentence)
        length += len(sentence) + 1
    if current:
        passages.append(" ".join(current))
    return [item for item in passages if len(item) >= 24]


def _summary_score(sentence: str) -> int:
    length = len(sentence)
    if length < 40 or length > 360:
        return -100
    score = 3
    score += sum(2 for marker in _SUMMARY_MARKERS if marker in sentence)
    score += 2 if re.search(r"\d+(?:\.\d+)?(?:%|亿元|万|年|月)", sentence) else 0
    score += 1 if "，" in sentence or "；" in sentence else 0
    return score


def _extract_summary_points(units: Sequence[LocalContentUnit]) -> list[str]:
    if not units:
        return []
    buckets: dict[int, tuple[int, str]] = {}
    total = max(1, len(units))
    global_candidates: list[tuple[int, str]] = []
    for index, unit in enumerate(units):
        bucket = min(4, (index * 5) // total)
        for sentence in _split_passages(unit.text, max_chars=280):
            score = _summary_score(sentence)
            if score <= 0:
                continue
            global_candidates.append((score, sentence))
            current = buckets.get(bucket)
            if current is None or score > current[0]:
                buckets[bucket] = (score, sentence)
    selected = [value[1] for _, value in sorted(buckets.items())]
    for _, sentence in sorted(global_candidates, key=lambda item: (-item[0], item[1])):
        if len(selected) >= 6:
            break
        if all(sentence != existing and sentence[:40] != existing[:40] for existing in selected):
            selected.append(sentence)
    return selected[:6]


def _extract_outline(units: Sequence[LocalContentUnit]) -> list[str]:
    headings: list[str] = []
    heading_pattern = re.compile(r"^(?:第[一二三四五六七八九十百0-9]+[章节部分]|[0-9]{1,2}[.、]|[一二三四五六七八九十]+、).{2,52}$")
    for unit in units:
        for line in re.split(r"[\n\r]+", unit.text):
            candidate = _clean_text(line)
            if heading_pattern.match(candidate) and candidate not in headings:
                headings.append(candidate)
                if len(headings) >= 16:
                    return headings
    return headings


def build_content_profile(analysis: LocalDocumentAnalysis) -> dict[str, Any]:
    summary_points = [
        sanitized
        for item in _extract_summary_points(analysis.units)
        if (sanitized := sanitize_public_reference_text(item, max_chars=460))
    ]
    outline = [
        sanitized
        for item in _extract_outline(analysis.units)
        if (sanitized := sanitize_public_reference_text(item, max_chars=180))
    ]
    return {
        "analysis_version": RAG_SCHEMA_VERSION,
        "status": analysis.extraction_status,
        "source_format": analysis.source_format,
        "total_unit_count": analysis.total_unit_count,
        "extracted_unit_count": analysis.extracted_unit_count,
        "content_coverage_ratio": round(
            analysis.extracted_unit_count / max(1, analysis.total_unit_count), 4
        )
        if analysis.total_unit_count
        else 0.0,
        "content_char_count": analysis.content_char_count,
        "full_text_sha256": hashlib.sha256(analysis.full_text.encode("utf-8")).hexdigest() if analysis.full_text else "",
        "ocr_used": analysis.ocr_used,
        "outline": outline,
        "summary_points": summary_points,
        "warnings": list(analysis.warnings),
    }


def _looks_like_instruction(text: str) -> bool:
    lowered = text.casefold()
    return any(marker in lowered for marker in _INSTRUCTION_MARKERS)


def _is_low_value_passage(text: str) -> bool:
    normalized = _clean_text(text)
    if len(normalized) < 24:
        return True
    lowered = normalized.casefold()
    if any(marker in lowered for marker in ("目录", "contents", "appendix", "版权声明", "免责声明")):
        return True
    sentence_count = len([item for item in _SENTENCE_SPLIT_RE.split(normalized) if item])
    return sentence_count <= 1 and not re.search(r"[。！？!?；;]", normalized)


def sanitize_public_reference_text(value: str, *, max_chars: int = 460) -> str:
    text = _clean_text(value)
    text = _EMAIL_RE.sub("[邮箱已隐藏]", text)
    text = _PHONE_RE.sub("[手机号已隐藏]", text)
    text = _LANDLINE_RE.sub("[电话已隐藏]", text)
    text = _SECRET_LABEL_VALUE_RE.sub("[凭据已隐藏]", text)
    text = _CREDENTIAL_TOKEN_RE.sub("[凭据已隐藏]", text)
    retained = [
        sentence
        for sentence in _SENTENCE_SPLIT_RE.split(text)
        if sentence
        and not _looks_like_instruction(sentence)
        and not any(marker in sentence.casefold() for marker in _BOILERPLATE_MARKERS)
    ]
    return _clean_text(" ".join(retained))[:max_chars]


def _passages_for_document(document: Mapping[str, Any], analysis: LocalDocumentAnalysis) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    document_id = str(document.get("document_id") or "")
    for unit in analysis.units:
        for local_ordinal, text in enumerate(_split_passages(unit.text), start=1):
            if _looks_like_instruction(text) or _is_low_value_passage(text):
                continue
            ordinal = len(rows) + 1
            passage_id = hashlib.sha1(
                f"{document_id}|{unit.ordinal}|{local_ordinal}|{text}".encode("utf-8")
            ).hexdigest()
            rows.append(
                {
                    "passage_id": f"passage_{passage_id[:20]}",
                    "document_id": document_id,
                    "ordinal": ordinal,
                    "locator": unit.locator,
                    "title": str(document.get("file_name") or document.get("title") or "本地资料"),
                    "document_type": str(document.get("document_type") or "reference_material"),
                    "document_type_label": str(document.get("document_type_label") or "参考资料"),
                    "primary_industry": str(document.get("primary_industry") or "cross_industry"),
                    "text": text,
                }
            )
    return rows


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE documents (
            document_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            document_type TEXT NOT NULL,
            document_type_label TEXT NOT NULL,
            primary_industry TEXT NOT NULL,
            extraction_status TEXT NOT NULL,
            content_profile_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE passages (
            passage_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            ordinal INTEGER NOT NULL,
            locator TEXT NOT NULL,
            title TEXT NOT NULL,
            document_type TEXT NOT NULL,
            document_type_label TEXT NOT NULL,
            primary_industry TEXT NOT NULL,
            text TEXT NOT NULL,
            vector_index INTEGER,
            FOREIGN KEY(document_id) REFERENCES documents(document_id)
        );
        CREATE INDEX passages_document_idx ON passages(document_id, ordinal);
        CREATE INDEX passages_industry_idx ON passages(primary_industry, document_type);
        CREATE VIRTUAL TABLE passages_fts USING fts5(
            passage_id UNINDEXED,
            text,
            title,
            tokenize='trigram'
        );
        """
    )


def _as_iso_now() -> str:
    return datetime.now(UTC).isoformat()


class IndustryKnowledgeBaseBuilder:
    def __init__(
        self,
        library_dir: Path,
        *,
        vector_enabled: bool = True,
        progress: Callable[[str, int, int], None] | None = None,
    ) -> None:
        self.library_dir = library_dir
        self.rag_dir = library_dir / RAG_DIR_NAME
        self.rag_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = uuid.uuid4().hex[:12]
        self.database_tmp = self.rag_dir / f"{RAG_DATABASE_NAME}.{self.run_id}.tmp"
        self.connection = sqlite3.connect(self.database_tmp)
        self.connection.execute("PRAGMA journal_mode = OFF")
        self.connection.execute("PRAGMA synchronous = OFF")
        _create_schema(self.connection)
        self.vector_enabled = vector_enabled
        self.progress = progress
        self.document_count = 0
        self.full_text_document_count = 0
        self.ocr_document_count = 0
        self.ocr_pending_count = 0
        self.unsupported_count = 0
        self.passage_count = 0

    def add_document(self, document: Mapping[str, Any], analysis: LocalDocumentAnalysis | None) -> None:
        profile = dict(document.get("content_profile") or {})
        status = str(profile.get("status") or document.get("extraction_status") or "unknown")
        self.connection.execute(
            """
            INSERT INTO documents (
                document_id, title, document_type, document_type_label, primary_industry,
                extraction_status, content_profile_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(document.get("document_id") or ""),
                str(document.get("file_name") or document.get("title") or "本地资料"),
                str(document.get("document_type") or "reference_material"),
                str(document.get("document_type_label") or "参考资料"),
                str(document.get("primary_industry") or "cross_industry"),
                status,
                json.dumps(profile, ensure_ascii=False, sort_keys=True),
                _as_iso_now(),
            ),
        )
        self.document_count += 1
        if status in {"full_text_analyzed", "ocr_full_text_analyzed"}:
            self.full_text_document_count += 1
        if status == "ocr_full_text_analyzed":
            self.ocr_document_count += 1
        if status == "ocr_pending":
            self.ocr_pending_count += 1
        if status == "unsupported_format":
            self.unsupported_count += 1
        if analysis is None:
            return
        passages = _passages_for_document(document, analysis)
        if passages:
            self.connection.executemany(
                """
                INSERT INTO passages (
                    passage_id, document_id, ordinal, locator, title, document_type,
                    document_type_label, primary_industry, text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row["passage_id"],
                        row["document_id"],
                        row["ordinal"],
                        row["locator"],
                        row["title"],
                        row["document_type"],
                        row["document_type_label"],
                        row["primary_industry"],
                        row["text"],
                    )
                    for row in passages
                ],
            )
            self.connection.executemany(
                "INSERT INTO passages_fts (passage_id, text, title) VALUES (?, ?, ?)",
                [(row["passage_id"], row["text"], row["title"]) for row in passages],
            )
            self.passage_count += len(passages)

    def _load_reusable_vectors(
        self,
        backend: LocalEmbeddingBackend,
        dimension: int,
    ) -> tuple[np.ndarray | None, dict[str, int]]:
        vector_path = self.rag_dir / RAG_VECTOR_NAME
        metadata_path = self.rag_dir / RAG_VECTOR_METADATA_NAME
        manifest_path = self.rag_dir / RAG_MANIFEST_NAME
        if not (vector_path.is_file() and metadata_path.is_file() and manifest_path.is_file()):
            return None, {}
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            vector_summary = dict(manifest.get("vector_index") or {})
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if (
                manifest.get("schema_version") != RAG_SCHEMA_VERSION
                or vector_summary.get("status") != "ready"
                or vector_summary.get("model") != backend.model_name
                or int(vector_summary.get("dimension") or 0) != dimension
                or metadata.get("generation_id") != manifest.get("generation_id")
            ):
                return None, {}
            matrix = np.load(vector_path, mmap_mode="r")
            passage_ids = [str(value) for value in metadata.get("passage_ids") or []]
            if matrix.ndim != 2 or matrix.shape != (len(passage_ids), dimension):
                return None, {}
            return matrix, {passage_id: index for index, passage_id in enumerate(passage_ids)}
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None, {}

    def _build_vectors(self) -> dict[str, Any]:
        if not self.vector_enabled or self.passage_count == 0:
            return {"status": "disabled", "backend": "none", "warnings": []}
        backend, warnings = resolve_local_embedding_backend()
        if backend is None:
            return {"status": "unavailable", "backend": "none", "warnings": warnings}
        vector_tmp = self.rag_dir / f"{RAG_VECTOR_NAME}.{self.run_id}.tmp.npy"
        metadata_tmp = self.rag_dir / f"{RAG_VECTOR_METADATA_NAME}.{self.run_id}.tmp"
        dimension = backend.dimension
        reusable_matrix, reusable_indices = self._load_reusable_vectors(backend, dimension)
        matrix = np.lib.format.open_memmap(
            vector_tmp,
            mode="w+",
            dtype=np.float32,
            shape=(self.passage_count, dimension),
        )
        cursor = self.connection.execute(
            "SELECT passage_id, text, primary_industry, document_type FROM passages ORDER BY passage_id"
        )
        passage_ids: list[str] = []
        industries: list[str] = []
        document_types: list[str] = []
        offset = 0
        reused_passage_count = 0
        encoded_passage_count = 0
        batch_size = max(1, min(int(get_settings().decision_embedding_batch_size or 8), 16))
        while rows := cursor.fetchmany(batch_size):
            vectors = np.empty((len(rows), dimension), dtype=np.float32)
            missing_indices: list[int] = []
            missing_texts: list[str] = []
            for index, row in enumerate(rows):
                prior_index = reusable_indices.get(str(row[0]))
                if reusable_matrix is not None and prior_index is not None:
                    vectors[index] = reusable_matrix[prior_index]
                    reused_passage_count += 1
                else:
                    missing_indices.append(index)
                    missing_texts.append(str(row[1]))
            if missing_texts:
                encoded_vectors = backend.encode(missing_texts)
                if encoded_vectors.shape != (len(missing_texts), dimension):
                    raise RuntimeError("本地向量模型返回了不匹配的向量维度。")
                vectors[missing_indices] = encoded_vectors
                encoded_passage_count += len(missing_texts)
            matrix[offset : offset + len(rows)] = vectors
            self.connection.executemany(
                "UPDATE passages SET vector_index = ? WHERE passage_id = ?",
                [(offset + index, str(row[0])) for index, row in enumerate(rows)],
            )
            passage_ids.extend(str(row[0]) for row in rows)
            industries.extend(str(row[2]) for row in rows)
            document_types.extend(str(row[3]) for row in rows)
            offset += len(rows)
            if self.progress is not None and (offset == self.passage_count or offset % 200 == 0):
                self.progress("embedding", offset, self.passage_count)
        matrix.flush()
        del matrix
        del reusable_matrix
        metadata_tmp.write_text(
            json.dumps(
                {
                    "generation_id": self.run_id,
                    "passage_ids": passage_ids,
                    "industries": industries,
                    "document_types": document_types,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        vector_tmp.replace(self.rag_dir / RAG_VECTOR_NAME)
        metadata_tmp.replace(self.rag_dir / RAG_VECTOR_METADATA_NAME)
        return {
            "status": "ready",
            "backend": "sentence_transformers",
            "model": backend.model_name,
            "requested_model": backend.requested_model,
            "dimension": dimension,
            "fallback_reason": backend.fallback_reason,
            "reused_passage_count": reused_passage_count,
            "encoded_passage_count": encoded_passage_count,
            "warnings": warnings,
        }

    def finalize(self) -> dict[str, Any]:
        self.connection.commit()
        vector_summary = self._build_vectors()
        self.connection.commit()
        self.connection.close()
        self.database_tmp.replace(self.rag_dir / RAG_DATABASE_NAME)
        manifest = {
            "schema_version": RAG_SCHEMA_VERSION,
            "generation_id": self.run_id,
            "generated_at": _as_iso_now(),
            "database": RAG_DATABASE_NAME,
            "vector_file": RAG_VECTOR_NAME if vector_summary.get("status") == "ready" else "",
            "vector_metadata": RAG_VECTOR_METADATA_NAME if vector_summary.get("status") == "ready" else "",
            "document_count": self.document_count,
            "full_text_document_count": self.full_text_document_count,
            "ocr_document_count": self.ocr_document_count,
            "ocr_pending_count": self.ocr_pending_count,
            "unsupported_count": self.unsupported_count,
            "passage_count": self.passage_count,
            "keyword_index": {"status": "ready", "backend": "sqlite_fts5", "tokenizer": "trigram"},
            "vector_index": vector_summary,
        }
        _write_json(self.rag_dir / RAG_MANIFEST_NAME, manifest)
        _clear_rag_caches()
        return manifest


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _cache_path_is_mounted(path: str | None) -> bool:
    if not path:
        return True
    candidate = Path(path).expanduser()
    if len(candidate.parts) >= 3 and candidate.parts[1] == "Volumes":
        return (Path("/") / candidate.parts[1] / candidate.parts[2]).is_mount()
    return True


@lru_cache(maxsize=3)
def _load_sentence_transformer(model_name: str, device: str, cache_dir: str = ""):
    from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

    kwargs: dict[str, Any] = {
        "trust_remote_code": False,
        "local_files_only": True,
    }
    if device and device != "auto":
        kwargs["device"] = device
    if cache_dir:
        kwargs["cache_folder"] = cache_dir
    return SentenceTransformer(model_name, **kwargs)


def _get_sentence_transformer(model_name: str, device: str, cache_dir: str = ""):
    """Return the cached model without allowing concurrent cold-start loads."""
    with _SENTENCE_TRANSFORMER_CACHE_LOCK:
        return _load_sentence_transformer(model_name, device, cache_dir)


def resolve_local_embedding_backend() -> tuple[LocalEmbeddingBackend | None, list[str]]:
    settings = get_settings()
    requested_model = normalize_text(settings.decision_embedding_model) or "BAAI/bge-m3"
    device = normalize_text(settings.decision_embedding_device) or "auto"
    warnings: list[str] = []
    candidates: list[tuple[str, str, str]] = []
    if _cache_path_is_mounted(settings.decision_embedding_cache_dir):
        candidates.append((requested_model, "", str(settings.decision_embedding_cache_dir or "")))
    else:
        warnings.append("BGE-M3 外接缓存盘未挂载，未尝试下载模型。")
    if requested_model != "BAAI/bge-large-zh":
        candidates.append(
            ("BAAI/bge-large-zh", f"主模型 {requested_model} 不可离线使用，已降级到本机缓存的 BAAI/bge-large-zh。", "")
        )
    for model_name, fallback_reason, cache_dir in candidates:
        try:
            _get_sentence_transformer(model_name, device, cache_dir)
        except Exception as exc:
            warnings.append(f"{model_name} 不可用：{type(exc).__name__}。")
            continue
        return (
            LocalEmbeddingBackend(
                model_name=model_name,
                requested_model=requested_model,
                device=device,
                cache_dir=cache_dir,
                fallback_reason=fallback_reason,
            ),
            warnings,
        )
    return None, warnings or ["没有可离线使用的向量模型。"]


def _rag_dir(library_dir: str | Path) -> Path:
    return Path(library_dir).expanduser() / RAG_DIR_NAME


def load_knowledge_base_manifest(library_dir: str | Path) -> dict[str, Any] | None:
    path = _rag_dir(library_dir) / RAG_MANIFEST_NAME
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("schema_version") != RAG_SCHEMA_VERSION:
        return None
    return payload if isinstance(payload, dict) else None


def knowledge_base_public_status(library_dir: str | Path) -> dict[str, Any]:
    manifest = load_knowledge_base_manifest(library_dir)
    if manifest is None:
        return {
            "status": "unavailable",
            "keyword_index_status": "unavailable",
            "vector_index_status": "unavailable",
            "hybrid_search_enabled": False,
            "warnings": ["全文行业资料 RAG 尚未建立。"],
        }
    vector = dict(manifest.get("vector_index") or {})
    keyword = dict(manifest.get("keyword_index") or {})
    vector_ready = vector.get("status") == "ready"
    return {
        "status": "ready" if vector_ready else "partial",
        "generated_at": manifest.get("generated_at"),
        "document_count": int(manifest.get("document_count") or 0),
        "full_text_document_count": int(manifest.get("full_text_document_count") or 0),
        "ocr_document_count": int(manifest.get("ocr_document_count") or 0),
        "ocr_pending_count": int(manifest.get("ocr_pending_count") or 0),
        "unsupported_count": int(manifest.get("unsupported_count") or 0),
        "passage_count": int(manifest.get("passage_count") or 0),
        "keyword_index_status": str(keyword.get("status") or "unavailable"),
        "vector_index_status": str(vector.get("status") or "unavailable"),
        "vector_model": str(vector.get("model") or ""),
        "requested_vector_model": str(vector.get("requested_model") or ""),
        "vector_fallback_reason": str(vector.get("fallback_reason") or ""),
        "hybrid_search_enabled": vector_ready and keyword.get("status") == "ready",
        "warnings": [str(item) for item in vector.get("warnings", [])],
    }


def _fts_query(query: str) -> str:
    terms = re.findall(r"[A-Za-z0-9][A-Za-z0-9+_.-]{1,}|[\u4e00-\u9fff]{2,}", query)
    safe = [term.replace('"', "") for term in terms if len(term) >= 2]
    return " OR ".join(f'"{term}"' for term in safe[:12])


def _keyword_terms(query: str) -> list[str]:
    terms = re.findall(r"[A-Za-z0-9][A-Za-z0-9+_.-]{1,}|[\u4e00-\u9fff]{2,}", query)
    return [term.casefold() for term in terms if len(term) >= 2][:12]


def _match_filters(row: Mapping[str, Any], industries: set[str], document_types: set[str]) -> bool:
    return (
        (not industries or str(row.get("primary_industry") or "") in industries)
        and (not document_types or str(row.get("document_type") or "") in document_types)
    )


def _resolve_retrieval_strategy(value: str | None) -> IndustryKnowledgeRetrievalStrategySpec:
    key = normalize_text(value or DEFAULT_INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGY).lower()
    return INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGIES.get(
        key,  # type: ignore[arg-type]
        INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGIES[DEFAULT_INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGY],
    )


def industry_knowledge_retrieval_strategy_catalog() -> list[dict[str, Any]]:
    """Return the stable public strategy catalog without exposing implementation objects."""
    return [
        {
            "key": spec.key,
            "label": spec.label,
            "description": spec.description,
            "default": spec.key == DEFAULT_INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGY,
            "lexical_prefilter": spec.lexical_prefilter,
            "title_bm25_weight": float(spec.bm25_weights[2]) if spec.bm25_weights else 1.0,
            "rerank_enabled": spec.rerank,
            "rerank_top_k": spec.rerank_top_k if spec.rerank else 0,
        }
        for spec in INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGIES.values()
    ]


def _open_connection(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _lexical_hits(
    database_path: Path,
    query: str,
    *,
    industries: set[str],
    document_types: set[str],
    limit: int,
    strategy: IndustryKnowledgeRetrievalStrategySpec,
) -> list[dict[str, Any]]:
    match = _fts_query(query)
    if not match:
        return []
    connection = _open_connection(database_path)
    try:
        try:
            filter_clauses: list[str] = []
            filter_parameters: list[str] = []
            if strategy.lexical_prefilter and industries:
                placeholders = ",".join("?" for _ in industries)
                filter_clauses.append(f"p.primary_industry IN ({placeholders})")
                filter_parameters.extend(sorted(industries))
            if strategy.lexical_prefilter and document_types:
                placeholders = ",".join("?" for _ in document_types)
                filter_clauses.append(f"p.document_type IN ({placeholders})")
                filter_parameters.extend(sorted(document_types))
            scope_filter_sql = f" AND {' AND '.join(filter_clauses)}" if filter_clauses else ""
            bm25_expression = "bm25(passages_fts)"
            if strategy.bm25_weights:
                # FTS5 has an UNINDEXED passage_id column followed by text and title.
                weights = ", ".join(str(weight) for weight in strategy.bm25_weights)
                bm25_expression = f"bm25(passages_fts, {weights})"
            candidate_limit = max(limit * 12, 48)
            rows = connection.execute(
                f"""
                SELECT p.passage_id, p.document_id, p.locator, p.title, p.document_type,
                       p.document_type_label, p.primary_industry, p.text, {bm25_expression} AS bm25_score
                FROM passages_fts
                JOIN passages AS p ON p.passage_id = passages_fts.passage_id
                WHERE passages_fts MATCH ?{scope_filter_sql}
                ORDER BY {bm25_expression}
                LIMIT ?
                """,
                (match, *filter_parameters, candidate_limit),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []

        # FTS tokenization can miss short CJK terms such as "景区". Keep its
        # ranking when it works, but guarantee a literal keyword fallback.
        if not rows:
            terms = _keyword_terms(query)
            clauses = " OR ".join("p.text LIKE ? OR p.title LIKE ?" for _ in terms)
            if clauses:
                parameters = [value for term in terms for value in (f"%{term}%", f"%{term}%")]
                filter_clauses = []
                filter_parameters = []
                if strategy.lexical_prefilter and industries:
                    placeholders = ",".join("?" for _ in industries)
                    filter_clauses.append(f"p.primary_industry IN ({placeholders})")
                    filter_parameters.extend(sorted(industries))
                if strategy.lexical_prefilter and document_types:
                    placeholders = ",".join("?" for _ in document_types)
                    filter_clauses.append(f"p.document_type IN ({placeholders})")
                    filter_parameters.extend(sorted(document_types))
                scope_filter_sql = f" AND {' AND '.join(filter_clauses)}" if filter_clauses else ""
                rows = connection.execute(
                    f"""
                    SELECT p.passage_id, p.document_id, p.locator, p.title, p.document_type,
                           p.document_type_label, p.primary_industry, p.text, 0.0 AS bm25_score
                    FROM passages AS p
                    WHERE ({clauses}){scope_filter_sql}
                    LIMIT ?
                    """,
                    (*parameters, *filter_parameters, max(limit * 12, 48)),
                ).fetchall()
    finally:
        connection.close()
    selected: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        if _match_filters(payload, industries, document_types):
            selected.append(payload)
        if len(selected) >= limit:
            break
    return selected


@lru_cache(maxsize=4)
def _load_vector_assets(vector_path: str, metadata_path: str, generation_id: str) -> tuple[np.ndarray, dict[str, Any]]:
    matrix = np.load(vector_path, mmap_mode="r")
    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    return matrix, metadata


def _dense_hits(
    database_path: Path,
    rag_dir: Path,
    manifest: Mapping[str, Any],
    query: str,
    *,
    industries: set[str],
    document_types: set[str],
    limit: int,
) -> list[dict[str, Any]]:
    vector = dict(manifest.get("vector_index") or {})
    if vector.get("status") != "ready":
        return []
    vector_path = rag_dir / str(manifest.get("vector_file") or "")
    metadata_path = rag_dir / str(manifest.get("vector_metadata") or "")
    if not vector_path.is_file() or not metadata_path.is_file():
        return []
    model_name = str(vector.get("model") or "")
    if not model_name:
        return []
    try:
        backend = LocalEmbeddingBackend(
            model_name=model_name,
            requested_model=str(vector.get("requested_model") or model_name),
            device=normalize_text(get_settings().decision_embedding_device) or "auto",
            cache_dir=_cache_dir_for_model(model_name),
        )
        query_vector = backend.encode([query])[0]
        matrix, metadata = _load_vector_assets(
            str(vector_path), str(metadata_path), str(manifest.get("generation_id") or "")
        )
    except Exception:
        return []
    if matrix.ndim != 2 or matrix.shape[1] != len(query_vector):
        return []
    candidate_count = min(matrix.shape[0], max(limit * 12, 48))
    scores = np.asarray(matrix @ query_vector, dtype=np.float32)
    row_industries = list(metadata.get("industries") or [])
    row_types = list(metadata.get("document_types") or [])
    if len(row_industries) != len(scores) or len(row_types) != len(scores):
        return []
    if industries or document_types:
        allowed = np.asarray(
            [
                (not industries or industry in industries) and (not document_types or doc_type in document_types)
                for industry, doc_type in zip(row_industries, row_types, strict=True)
            ],
            dtype=bool,
        )
        scores = np.where(allowed, scores, -np.inf)
    eligible = int(np.isfinite(scores).sum())
    if not eligible:
        return []
    candidate_count = min(candidate_count, eligible)
    indices = np.argpartition(scores, -candidate_count)[-candidate_count:]
    ranked_indices = sorted(indices.tolist(), key=lambda index: float(scores[index]), reverse=True)
    passage_ids = list(metadata.get("passage_ids") or [])
    selected_ids = [str(passage_ids[index]) for index in ranked_indices if index < len(passage_ids)]
    if not selected_ids:
        return []
    connection = _open_connection(database_path)
    try:
        placeholders = ",".join("?" for _ in selected_ids)
        rows = connection.execute(
            f"""
            SELECT passage_id, document_id, locator, title, document_type,
                   document_type_label, primary_industry, text
            FROM passages WHERE passage_id IN ({placeholders})
            """,
            selected_ids,
        ).fetchall()
    finally:
        connection.close()
    by_id = {str(row["passage_id"]): dict(row) for row in rows}
    return [
        {**by_id[passage_id], "dense_score": float(scores[index])}
        for index, passage_id in zip(ranked_indices, selected_ids, strict=True)
        if passage_id in by_id
    ][:limit]


def _clear_rag_caches() -> None:
    _load_vector_assets.cache_clear()


def _cache_dir_for_model(model_name: str) -> str:
    settings = get_settings()
    configured_model = normalize_text(settings.decision_embedding_model)
    if configured_model == model_name and _cache_path_is_mounted(settings.decision_embedding_cache_dir):
        return str(settings.decision_embedding_cache_dir or "")
    return ""


def _cross_encoder_model_is_cached(model_name: str, cache_dir: str | None) -> bool:
    """Guard benchmark runs from silently downloading a reranker model.

    The industry library is explicitly local-first.  A configured Cross Encoder
    is not proof that the model is available: its external cache volume can be
    absent or the repository can be missing.  Only invoke sentence-transformers
    when a local snapshot (or explicit local model directory) is present.
    """
    normalized_model = normalize_text(model_name)
    if not normalized_model:
        return False
    local_path = Path(normalized_model).expanduser()
    if local_path.is_dir():
        return (local_path / "config.json").is_file()
    if not _cache_path_is_mounted(cache_dir):
        return False
    cache_root = Path(
        cache_dir
        or os.environ.get("HF_HUB_CACHE")
        or (Path.home() / ".cache" / "huggingface" / "hub")
    ).expanduser()
    repository_dir = cache_root / f"models--{normalized_model.replace('/', '--')}"
    snapshots_dir = repository_dir / "snapshots"
    return snapshots_dir.is_dir() and any(
        (snapshot / "config.json").is_file() for snapshot in snapshots_dir.iterdir() if snapshot.is_dir()
    )


def _rerank_industry_knowledge_hits(
    hits: list[dict[str, Any]],
    *,
    query: str,
    strategy: IndustryKnowledgeRetrievalStrategySpec,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Rerank local passages while retaining whether a real model actually ran."""
    if not strategy.rerank or len(hits) <= 1:
        return hits, {
            "rerank_requested": strategy.rerank,
            "rerank_applied": False,
            "rerank_backend": "disabled",
            "rerank_model": "",
            "rerank_top_k": 0,
            "rerank_notes": [],
        }

    settings = get_settings()
    top_k = min(len(hits), max(1, int(strategy.rerank_top_k or 20)))
    model_name = normalize_text(settings.research_cross_encoder_model)
    backend = normalize_text(settings.research_cross_encoder_backend).lower() or "auto"
    cache_dir = settings.research_cross_encoder_cache_dir
    device = normalize_text(settings.research_cross_encoder_device) or "auto"
    if backend != "local" and not _cross_encoder_model_is_cached(model_name, cache_dir):
        cache_location = str(cache_dir or "~/.cache/huggingface/hub")
        return hits, {
            "rerank_requested": True,
            "rerank_applied": False,
            "rerank_backend": "unavailable",
            "rerank_model": model_name,
            "rerank_top_k": top_k,
            "rerank_notes": [
                f"Cross Encoder 本地快照不可用（{cache_location}），本次未下载模型也未执行启发式替代。",
                "候选 B 不具备真实复排证据，不能据此进入生产默认链路。",
            ],
        }

    @dataclass(slots=True)
    class _PassageCandidate:
        passage_id: str
        title: str
        snippet: str
        excerpt: str
        source_tier: str = "local_reference"

    candidates = [
        _PassageCandidate(
            passage_id=str(hit.get("passage_id") or ""),
            title=str(hit.get("title") or ""),
            snippet=str(hit.get("snippet") or ""),
            excerpt=str(hit.get("text") or hit.get("snippet") or ""),
        )
        for hit in hits
    ]
    try:
        reranked, profile = rerank_sources_cross_encoder(
            candidates,
            query=query,
            model_name=model_name,
            top_k=top_k,
            backend=backend,
            cache_dir=cache_dir,
            device=device,
        )
    except Exception as exc:
        return hits, {
            "rerank_requested": True,
            "rerank_applied": False,
            "rerank_backend": "failed",
            "rerank_model": model_name,
            "rerank_top_k": top_k,
            "rerank_notes": [f"本地资料复排不可用：{type(exc).__name__}。"],
        }
    by_id = {str(hit.get("passage_id") or ""): hit for hit in hits}
    ordered = [by_id[candidate.passage_id] for candidate in reranked if candidate.passage_id in by_id]
    applied = bool(profile.reranked_count and profile.backend == "sentence-transformers")
    notes = [str(note) for note in profile.notes]
    if profile.backend != "sentence-transformers":
        notes.append("未将本地启发式回退计为 Cross Encoder 复排成功。")
    return ordered, {
        "rerank_requested": True,
        "rerank_applied": applied,
        "rerank_backend": profile.backend,
        "rerank_model": profile.model_name,
        "rerank_top_k": profile.top_k,
        "rerank_notes": notes,
    }


def hybrid_search_industry_knowledge(
    library_dir: str | Path,
    *,
    query: str,
    industries: Sequence[str] | None = None,
    document_types: Sequence[str] | None = None,
    limit: int = 6,
    strategy: str | None = None,
) -> dict[str, Any]:
    normalized_query = _clean_text(query)
    strategy_spec = _resolve_retrieval_strategy(strategy)
    public_status = knowledge_base_public_status(library_dir)
    if not normalized_query or public_status["status"] == "unavailable":
        return {
            **public_status,
            "query": normalized_query,
            "strategy": strategy_spec.key,
            "strategy_label": strategy_spec.label,
            "hits": [],
        }
    rag_dir = _rag_dir(library_dir)
    manifest = load_knowledge_base_manifest(library_dir)
    if manifest is None:
        return {
            **public_status,
            "query": normalized_query,
            "strategy": strategy_spec.key,
            "strategy_label": strategy_spec.label,
            "hits": [],
        }
    database_path = rag_dir / str(manifest.get("database") or RAG_DATABASE_NAME)
    if not database_path.is_file():
        return {
            **public_status,
            "status": "unavailable",
            "query": normalized_query,
            "strategy": strategy_spec.key,
            "strategy_label": strategy_spec.label,
            "hits": [],
            "warnings": [*public_status.get("warnings", []), "本地 RAG 数据库文件不存在。"],
        }
    selected_industries = {normalize_text(item) for item in industries or [] if normalize_text(item)}
    selected_types = {normalize_text(item) for item in document_types or [] if normalize_text(item)}
    capped_limit = max(1, min(int(limit), 12))
    candidate_limit = max(capped_limit, min(96, capped_limit * max(1, strategy_spec.candidate_multiplier)))
    lexical = _lexical_hits(
        database_path,
        normalized_query,
        industries=selected_industries,
        document_types=selected_types,
        limit=candidate_limit,
        strategy=strategy_spec,
    )
    dense = _dense_hits(
        database_path,
        rag_dir,
        manifest,
        normalized_query,
        industries=selected_industries,
        document_types=selected_types,
        limit=candidate_limit,
    )
    fused: dict[str, dict[str, Any]] = {}
    for rank, row in enumerate(lexical, start=1):
        item = fused.setdefault(str(row["passage_id"]), {**row, "fused_score": 0.0, "match_modes": []})
        item["fused_score"] += 0.45 / (40 + rank)
        item["keyword_rank"] = rank
        item["match_modes"].append("keyword")
    for rank, row in enumerate(dense, start=1):
        item = fused.setdefault(str(row["passage_id"]), {**row, "fused_score": 0.0, "match_modes": []})
        item["fused_score"] += 0.55 / (40 + rank)
        item["vector_rank"] = rank
        item["vector_score"] = round(float(row.get("dense_score") or 0.0), 4)
        item["match_modes"].append("vector")
    ranked_items = sorted(fused.values(), key=lambda row: (-float(row["fused_score"]), str(row["passage_id"])))
    prepared_hits: list[dict[str, Any]] = []
    for item in ranked_items:
        snippet = sanitize_public_reference_text(str(item.get("text") or ""), max_chars=460)
        if len(snippet) < 24:
            continue
        prepared_hits.append(
            {
                "passage_id": str(item["passage_id"]),
                "document_id": str(item["document_id"]),
                "title": str(item["title"]),
                "document_type": str(item["document_type"]),
                "document_type_label": str(item["document_type_label"]),
                "industry": str(item["primary_industry"]),
                "locator": str(item["locator"]),
                "snippet": snippet,
                "match_modes": sorted(set(str(mode) for mode in item["match_modes"])),
                "keyword_rank": int(item.get("keyword_rank") or 0) or None,
                "vector_rank": int(item.get("vector_rank") or 0) or None,
                "vector_score": float(item.get("vector_score") or 0.0),
                "fused_score": round(float(item["fused_score"]), 6),
                "verification_note": "本地资料内容仅作待核验行业参考，不构成项目事实或公开证据。",
            }
        )
    reranked_hits, rerank_metadata = _rerank_industry_knowledge_hits(
        prepared_hits,
        query=normalized_query,
        strategy=strategy_spec,
    )
    hits = reranked_hits[:capped_limit]
    status = "ready" if lexical and dense else "partial"
    return {
        **public_status,
        "status": status,
        "query": normalized_query,
        "strategy": strategy_spec.key,
        "strategy_label": strategy_spec.label,
        "hits": hits,
        "keyword_hit_count": len(lexical),
        "vector_hit_count": len(dense),
        **rerank_metadata,
    }
