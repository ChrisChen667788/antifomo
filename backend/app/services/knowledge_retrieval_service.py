from __future__ import annotations

import hashlib
import math
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence

from app.models.entities import KnowledgeEntry
from app.services.content_extractor import normalize_text
from app.services.research_retrieval_service import build_report_retrieval_chunks

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9._/-]{1,}|[\u4e00-\u9fff]{2,}")
_CJK_RE = re.compile(r"^[\u4e00-\u9fff]+$")
_PUNCT_SPLIT_RE = re.compile(r"[^a-z0-9\u4e00-\u9fff]+")
_SENTENCE_SPLIT_RE = re.compile(r"[。！？!?；;\n]+")

_STOPWORDS = {
    "什么",
    "哪些",
    "哪个",
    "如何",
    "怎么",
    "以及",
    "还有",
    "最近",
    "当前",
    "这个",
    "那个",
    "一下",
    "现在",
    "情况",
    "问题",
    "请问",
    "是否",
    "需要",
    "我们",
    "你们",
    "their",
    "there",
    "about",
    "what",
    "when",
    "which",
    "with",
}

_MEDIA_DOMAIN_HINTS = (
    "36kr",
    "huxiu",
    "sohu",
    "163.com",
    "qq.com",
    "sina.com",
    "thepaper",
    "toutiao",
    "ifeng",
    "jiqizhixin",
    "leiphone",
    "zhihu",
    "juejin",
    "mp.weixin.qq.com",
)
_OFFICIAL_DOMAIN_SUFFIXES = (
    ".gov",
    ".gov.cn",
    ".edu",
    ".edu.cn",
    ".org",
    ".org.cn",
)
_VECTOR_DIMS = 128
_RRF_K = 50.0
_ENTRY_PARENT_FIELDS = {"entry_summary", "entry_title"}
_PARENT_CHUNK_FIELDS = {*_ENTRY_PARENT_FIELDS, "report_summary", "section_summary"}


@dataclass(slots=True)
class KnowledgeRetrievalPreview:
    snippet: str
    label: str
    field_key: str
    section_title: str
    source_tier: str
    score: float
    match_modes: tuple[str, ...]
    matched_terms: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "snippet": self.snippet,
            "label": self.label,
            "field_key": self.field_key,
            "section_title": self.section_title,
            "source_tier": self.source_tier,
            "score": round(self.score, 4),
            "match_modes": list(self.match_modes),
            "matched_terms": list(self.matched_terms),
        }


@dataclass(slots=True)
class KnowledgeEntryMatch:
    entry: KnowledgeEntry
    score: float
    preview: KnowledgeRetrievalPreview


@dataclass(slots=True)
class TextRetrievalCandidate:
    key: str
    text: str
    source_tier: str = "media"
    priority: int = 0


@dataclass(slots=True)
class TextRetrievalMatch:
    key: str
    score: float
    source_tier: str
    match_modes: tuple[str, ...]
    matched_terms: tuple[str, ...]
    lexical_overlap: int
    dense_similarity: float
    exact_query_hit: bool


@dataclass(slots=True)
class _KnowledgeRetrievalChunk:
    chunk_id: int
    entry_id: Any
    entry: KnowledgeEntry
    label: str
    field_key: str
    text: str
    section_title: str
    source_tier: str
    priority: int
    search_text: str
    search_text_lower: str
    fts_terms: tuple[str, ...]
    dense_vector: tuple[float, ...]


@dataclass(slots=True)
class _TextRetrievalChunk:
    chunk_id: int
    key: str
    text: str
    source_tier: str
    priority: int
    search_text_lower: str
    fts_terms: tuple[str, ...]
    dense_vector: tuple[float, ...]


def _is_parent_chunk_field(field_key: str) -> bool:
    return normalize_text(field_key) in _PARENT_CHUNK_FIELDS


def _is_report_chunk_field(field_key: str) -> bool:
    normalized = normalize_text(field_key)
    return bool(normalized) and normalized not in {"entry_summary", "entry_title", "entry_content", "action_card"}


def _dedupe_strings(values: Sequence[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _split_text_windows(text: str, *, max_chars: int = 240) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    sentences = _dedupe_strings(_SENTENCE_SPLIT_RE.split(normalized))
    if not sentences:
        return [normalized[:max_chars]]

    windows: list[str] = []
    current: list[str] = []
    current_length = 0
    for sentence in sentences:
        sentence_length = len(sentence)
        if current and current_length + sentence_length > max_chars:
            windows.append("；".join(current))
            current = [sentence]
            current_length = sentence_length
            continue
        current.append(sentence)
        current_length += sentence_length
    if current:
        windows.append("；".join(current))
    return _dedupe_strings(windows)


def _search_terms(text: str) -> list[str]:
    normalized = normalize_text(text).lower()
    terms: list[str] = []
    for raw in _TOKEN_RE.findall(normalized):
        token = normalize_text(raw).lower()
        if not token or token in _STOPWORDS:
            continue
        parts = [part for part in _PUNCT_SPLIT_RE.split(token) if part]
        if not parts:
            parts = [token]
        for part in parts:
            if part in _STOPWORDS:
                continue
            terms.append(part)
            if _CJK_RE.match(part) and len(part) >= 4:
                for index in range(len(part) - 1):
                    terms.append(part[index : index + 2])
    return _dedupe_strings(terms)


def _dense_terms(text: str) -> list[str]:
    normalized = normalize_text(text).lower()
    compact = re.sub(r"\s+", "", normalized)
    dense_tokens = list(_search_terms(normalized))
    if compact:
        gram_count = 0
        for size in (2, 3):
            if len(compact) < size:
                continue
            for index in range(len(compact) - size + 1):
                gram = compact[index : index + size]
                if not gram.strip():
                    continue
                dense_tokens.append(f"g:{gram}")
                gram_count += 1
                if gram_count >= 64:
                    break
            if gram_count >= 64:
                break
    return dense_tokens


def _hash_feature(value: str) -> tuple[int, float]:
    digest = hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest()
    index = int.from_bytes(digest[:4], "big") % _VECTOR_DIMS
    sign = 1.0 if digest[4] % 2 == 0 else -1.0
    return index, sign


def _dense_vector(text: str) -> tuple[float, ...]:
    values = [0.0] * _VECTOR_DIMS
    for token in _dense_terms(text):
        index, sign = _hash_feature(token)
        weight = 1.35 if token.startswith("g:") else 1.0
        values[index] += sign * weight
    norm = math.sqrt(sum(value * value for value in values))
    if norm <= 0:
        return tuple(0.0 for _ in range(_VECTOR_DIMS))
    return tuple(value / norm for value in values)


def _dot_product(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sum(left[index] * right[index] for index in range(_VECTOR_DIMS))


def _truncate_snippet(text: str, *, max_chars: int = 220) -> str:
    normalized = normalize_text(text)
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max_chars - 1].rstrip()}..."


def _is_placeholder_title(value: str) -> bool:
    normalized = normalize_text(value).lower()
    return normalized.startswith(("wechat auto", "wechat ocr"))


def _resolve_entry_title(entry: KnowledgeEntry) -> str:
    raw_title = normalize_text(entry.title or "")
    if raw_title and not _is_placeholder_title(raw_title):
        return raw_title

    item = getattr(entry, "item", None)
    item_title = normalize_text(getattr(item, "title", "") or "")
    if item_title and not _is_placeholder_title(item_title):
        return item_title

    content = normalize_text((entry.content or "").replace("\n", " "))
    if content.startswith("知识库笔记："):
        content = normalize_text(content.split("：", 1)[1] if "：" in content else content)
    if content.lower().startswith("knowledge note:"):
        content = normalize_text(content.split(":", 1)[1] if ":" in content else content)
    if len(content) >= 8:
        return content[:30]
    return raw_title or "知识卡片"


def _infer_source_tier(entry: KnowledgeEntry, explicit_tier: str = "") -> str:
    normalized_tier = normalize_text(explicit_tier).lower()
    if normalized_tier:
        return normalized_tier

    domain = normalize_text(entry.source_domain or "").lower()
    if not domain:
        return "media"
    if any(domain.endswith(suffix) for suffix in _OFFICIAL_DOMAIN_SUFFIXES):
        return "official"
    if any(hint in domain for hint in _MEDIA_DOMAIN_HINTS):
        return "media"
    if "." in domain and "/" not in domain:
        return "official"
    return "media"


def _build_entry_summary_text(entry: KnowledgeEntry) -> str:
    title = _resolve_entry_title(entry)
    item = entry.__dict__.get("item")
    payload = entry.metadata_payload if isinstance(entry.metadata_payload, dict) else None
    report_payload = payload.get("report") if isinstance(payload, dict) else None
    parts = [
        title,
        normalize_text(entry.collection_name or ""),
        normalize_text(entry.source_domain or ""),
        normalize_text(getattr(item, "short_summary", "") or ""),
        normalize_text(getattr(item, "long_summary", "") or ""),
    ]
    if isinstance(report_payload, dict):
        parts.extend(
            [
                normalize_text(str(report_payload.get("report_title") or "")),
                normalize_text(str(report_payload.get("executive_summary") or "")),
                "；".join(
                    normalize_text(str(value or ""))
                    for value in list(report_payload.get("target_accounts") or [])[:2]
                    if normalize_text(str(value or ""))
                ),
                "；".join(
                    normalize_text(str(value or ""))
                    for value in list(report_payload.get("budget_signals") or [])[:2]
                    if normalize_text(str(value or ""))
                ),
            ]
        )
    else:
        for window in _split_text_windows(entry.content or "", max_chars=160)[:2]:
            parts.append(window)
    return "；".join(part for part in parts if part)


def _recency_bonus(entry: KnowledgeEntry) -> float:
    created_at = entry.created_at
    if created_at is None:
        return 0.0
    try:
        created_utc = (
            created_at.replace(tzinfo=timezone.utc)
            if created_at.tzinfo is None
            else created_at.astimezone(timezone.utc)
        )
    except Exception:
        return 0.0
    age_days = max(0.0, (datetime.now(timezone.utc) - created_utc).total_seconds() / 86400.0)
    return max(0.0, 0.02 * (1.0 - min(age_days, 180.0) / 180.0))


def _append_chunk(
    chunks: list[_KnowledgeRetrievalChunk],
    seen: set[str],
    *,
    entry: KnowledgeEntry,
    label: str,
    field_key: str,
    text: str,
    section_title: str = "",
    source_tier: str = "",
    priority: int = 0,
) -> None:
    normalized_text = normalize_text(text)
    if not normalized_text:
        return

    dedupe_key = normalize_text(
        " | ".join(
            [
                str(entry.id),
                field_key,
                label,
                section_title,
                source_tier,
                normalized_text,
            ]
        )
    )
    if not dedupe_key or dedupe_key in seen:
        return
    seen.add(dedupe_key)

    title = _resolve_entry_title(entry)
    search_text = normalize_text(
        " ".join(
            part
            for part in [
                title,
                entry.collection_name or "",
                label,
                section_title,
                entry.source_domain or "",
                normalized_text,
            ]
            if normalize_text(part)
        )
    )
    fts_terms = tuple(_search_terms(search_text))
    chunks.append(
        _KnowledgeRetrievalChunk(
            chunk_id=len(chunks) + 1,
            entry_id=entry.id,
            entry=entry,
            label=normalize_text(label) or field_key,
            field_key=field_key,
            text=normalized_text,
            section_title=normalize_text(section_title),
            source_tier=_infer_source_tier(entry, explicit_tier=source_tier),
            priority=priority,
            search_text=search_text,
            search_text_lower=search_text.lower(),
            fts_terms=fts_terms,
            dense_vector=_dense_vector(search_text),
        )
    )


def _build_entry_chunks(entry: KnowledgeEntry) -> list[_KnowledgeRetrievalChunk]:
    seen: set[str] = set()
    chunks: list[_KnowledgeRetrievalChunk] = []

    title = _resolve_entry_title(entry)
    _append_chunk(
        chunks,
        seen,
        entry=entry,
        label="卡片总览",
        field_key="entry_summary",
        text=_build_entry_summary_text(entry),
        priority=16,
    )
    _append_chunk(
        chunks,
        seen,
        entry=entry,
        label="标题",
        field_key="entry_title",
        text=title,
        priority=14,
    )

    for window in _split_text_windows(entry.content or "", max_chars=260):
        _append_chunk(
            chunks,
            seen,
            entry=entry,
            label="知识卡片",
            field_key="entry_content",
            text=window,
            priority=7,
        )

    payload = entry.metadata_payload if isinstance(entry.metadata_payload, dict) else None
    report_payload = payload.get("report") if isinstance(payload, dict) else None
    if isinstance(report_payload, dict):
        for report_chunk in build_report_retrieval_chunks(report_payload):
            _append_chunk(
                chunks,
                seen,
                entry=entry,
                label=report_chunk.label,
                field_key=report_chunk.field_key,
                text=report_chunk.text,
                section_title=report_chunk.section_title,
                source_tier=report_chunk.source_tier,
                priority=report_chunk.priority + 2,
            )

    raw_cards = payload.get("action_cards") if isinstance(payload, dict) else None
    if isinstance(raw_cards, list):
        for card in raw_cards:
            if not isinstance(card, dict):
                continue
            _append_chunk(
                chunks,
                seen,
                entry=entry,
                label="行动建议",
                field_key="action_card",
                text="；".join(
                    part
                    for part in [
                        str(card.get("title") or ""),
                        str(card.get("summary") or ""),
                        str(card.get("recommended_action") or ""),
                    ]
                    if normalize_text(str(part or ""))
                ),
                priority=6,
            )

    return chunks


def _sparse_rank(chunks: Sequence[_KnowledgeRetrievalChunk], query_terms: Sequence[str]) -> dict[int, int]:
    fts_query_terms = _dedupe_strings(query_terms)
    if not fts_query_terms:
        return {}

    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("create virtual table knowledge_chunks using fts5(tokenized_text)")
        connection.executemany(
            "insert into knowledge_chunks(rowid, tokenized_text) values (?, ?)",
            [
                (
                    chunk.chunk_id,
                    " ".join(chunk.fts_terms),
                )
                for chunk in chunks
                if chunk.fts_terms
            ],
        )
        match_query = " OR ".join(f'"{term}"' for term in fts_query_terms[:16])
        if not match_query:
            return {}
        rows = connection.execute(
            """
            select rowid
            from knowledge_chunks
            where knowledge_chunks match ?
            order by bm25(knowledge_chunks), rowid
            limit 120
            """,
            (match_query,),
        ).fetchall()
        return {int(row[0]): index for index, row in enumerate(rows, start=1)}
    finally:
        connection.close()


def _dense_rank(chunks: Sequence[_KnowledgeRetrievalChunk], query_vector: tuple[float, ...]) -> dict[int, tuple[int, float]]:
    scored: list[tuple[int, float]] = []
    for chunk in chunks:
        similarity = _dot_product(chunk.dense_vector, query_vector)
        if similarity < 0.16:
            continue
        scored.append((chunk.chunk_id, similarity))
    scored.sort(key=lambda item: item[1], reverse=True)
    return {
        chunk_id: (index, similarity)
        for index, (chunk_id, similarity) in enumerate(scored[:120], start=1)
    }


def _expand_routed_candidate_ids(
    chunks: Sequence[_KnowledgeRetrievalChunk],
    candidate_ids: set[int],
) -> set[int]:
    if not candidate_ids:
        return set()

    by_chunk_id = {chunk.chunk_id: chunk for chunk in chunks}
    entry_child_ids: dict[Any, list[int]] = {}
    report_child_ids: dict[Any, list[int]] = {}
    section_child_ids: dict[tuple[Any, str], list[int]] = {}
    for chunk in chunks:
        if not _is_parent_chunk_field(chunk.field_key):
            entry_child_ids.setdefault(chunk.entry_id, []).append(chunk.chunk_id)
            if _is_report_chunk_field(chunk.field_key):
                report_child_ids.setdefault(chunk.entry_id, []).append(chunk.chunk_id)
            if chunk.section_title:
                section_child_ids.setdefault((chunk.entry_id, chunk.section_title), []).append(chunk.chunk_id)

    routed: set[int] = set()
    for chunk_id in list(candidate_ids):
        chunk = by_chunk_id.get(chunk_id)
        if chunk is None:
            continue
        if chunk.field_key == "section_summary" and chunk.section_title:
            routed.update(section_child_ids.get((chunk.entry_id, chunk.section_title), []))
        elif chunk.field_key == "report_summary":
            routed.update(report_child_ids.get(chunk.entry_id, []))
        elif chunk.field_key in _ENTRY_PARENT_FIELDS:
            routed.update(entry_child_ids.get(chunk.entry_id, []))
    return routed


def _boost_knowledge_chunk_score(
    chunk: _KnowledgeRetrievalChunk,
    *,
    base_score: float,
    entry_parent_scores: dict[Any, float],
    report_parent_scores: dict[Any, float],
    section_parent_scores: dict[tuple[Any, str], float],
) -> tuple[float, bool]:
    if _is_parent_chunk_field(chunk.field_key):
        return base_score, False

    score = base_score
    routed = False

    entry_parent_score = float(entry_parent_scores.get(chunk.entry_id, 0.0) or 0.0)
    if entry_parent_score > 0:
        entry_boost = min(0.12, entry_parent_score * (0.2 if chunk.field_key == "entry_content" else 0.16))
        if entry_boost > 0:
            score += entry_boost
            routed = True

    if _is_report_chunk_field(chunk.field_key):
        report_parent_score = float(report_parent_scores.get(chunk.entry_id, 0.0) or 0.0)
        if report_parent_score > 0:
            report_boost = min(0.16, report_parent_score * 0.26)
            if chunk.field_key in {"section_evidence", "section_item", "target_accounts", "target_departments", "budget_signals"}:
                report_boost += min(0.04, report_parent_score * 0.08)
            if report_boost > 0:
                score += report_boost
                routed = True

    if chunk.section_title:
        section_parent_score = float(section_parent_scores.get((chunk.entry_id, chunk.section_title), 0.0) or 0.0)
        if section_parent_score > 0:
            section_boost = min(0.22, section_parent_score * 0.42)
            if chunk.field_key == "section_evidence":
                section_boost += min(0.08, section_parent_score * 0.18)
            elif chunk.field_key == "section_item":
                section_boost += min(0.05, section_parent_score * 0.12)
            if section_boost > 0:
                score += section_boost
                routed = True

    return score, routed


def _select_preview_hit(
    hit_list: list[tuple[float, _KnowledgeRetrievalChunk, tuple[str, ...], tuple[str, ...], bool]],
) -> tuple[float, _KnowledgeRetrievalChunk, tuple[str, ...], tuple[str, ...], bool]:
    top_hit = hit_list[0]
    if not _is_parent_chunk_field(top_hit[1].field_key):
        return top_hit
    top_score = float(top_hit[0] or 0.0)
    for candidate in hit_list[1:4]:
        candidate_score, candidate_chunk, _candidate_modes, _candidate_terms, candidate_routed = candidate
        if _is_parent_chunk_field(candidate_chunk.field_key):
            continue
        if candidate_routed or candidate_score >= top_score * 0.82 or candidate_score >= top_score - 0.05:
            return candidate
    return top_hit


def _build_text_retrieval_chunks(candidates: Sequence[TextRetrievalCandidate]) -> list[_TextRetrievalChunk]:
    chunks: list[_TextRetrievalChunk] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = normalize_text(candidate.key)
        text = normalize_text(candidate.text)
        if not key or not text:
            continue
        dedupe_key = normalize_text(
            " | ".join(
                [
                    key,
                    normalize_text(candidate.source_tier),
                    str(int(candidate.priority)),
                    text,
                ]
            )
        )
        if not dedupe_key or dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        chunks.append(
            _TextRetrievalChunk(
                chunk_id=len(chunks) + 1,
                key=key,
                text=text,
                source_tier=normalize_text(candidate.source_tier).lower() or "media",
                priority=max(0, int(candidate.priority)),
                search_text_lower=text.lower(),
                fts_terms=tuple(_search_terms(text)),
                dense_vector=_dense_vector(text),
            )
        )
    return chunks


def retrieve_text_matches(
    candidates: Sequence[TextRetrievalCandidate],
    query: str,
    *,
    limit: int = 50,
) -> list[TextRetrievalMatch]:
    normalized_query = normalize_text(query)
    if not normalized_query:
        return []

    query_terms = _search_terms(normalized_query)
    if not query_terms:
        return []
    query_vector = _dense_vector(normalized_query)

    chunks = _build_text_retrieval_chunks(candidates)
    if not chunks:
        return []
    for index, chunk in enumerate(chunks, start=1):
        chunk.chunk_id = index

    sparse_ranks = _sparse_rank(chunks, query_terms)
    dense_ranks = _dense_rank(chunks, query_vector)
    by_chunk_id = {chunk.chunk_id: chunk for chunk in chunks}

    candidate_ids = set(sparse_ranks) | set(dense_ranks)
    if not candidate_ids:
        return []

    grouped_hits: dict[str, list[tuple[float, _TextRetrievalChunk, tuple[str, ...], tuple[str, ...], int, float, bool]]] = {}
    for chunk_id in candidate_ids:
        chunk = by_chunk_id.get(chunk_id)
        if chunk is None:
            continue
        matched_terms = tuple(term for term in query_terms if term in chunk.search_text_lower)[:8]
        lexical_overlap = len(matched_terms)
        dense_rank = dense_ranks.get(chunk_id)
        similarity = dense_rank[1] if dense_rank else 0.0
        exact_query_hit = normalized_query.lower() in chunk.search_text_lower

        if lexical_overlap == 0 and similarity < 0.2 and not exact_query_hit:
            continue

        score = 0.0
        match_modes: list[str] = []
        sparse_rank = sparse_ranks.get(chunk_id)
        if sparse_rank is not None:
            score += 1.0 / (_RRF_K + sparse_rank)
            match_modes.append("sparse")
        if dense_rank is not None:
            score += 1.0 / (_RRF_K + dense_rank[0]) + similarity * 0.18
            match_modes.append("dense")
        score += min(0.18, lexical_overlap * 0.035)
        if exact_query_hit:
            score += 0.06
            match_modes.append("exact")
        score += min(0.08, chunk.priority * 0.005)
        if chunk.source_tier == "official":
            score += 0.04

        grouped_hits.setdefault(chunk.key, []).append(
            (
                score,
                chunk,
                tuple(_dedupe_strings(match_modes)),
                matched_terms,
                lexical_overlap,
                similarity,
                exact_query_hit,
            )
        )

    ranked_matches: list[TextRetrievalMatch] = []
    for hit_list in grouped_hits.values():
        if not hit_list:
            continue
        hit_list.sort(key=lambda item: item[0], reverse=True)
        top_score, top_chunk, match_modes, matched_terms, lexical_overlap, similarity, exact_query_hit = hit_list[0]
        aggregate_score = top_score + sum(score * 0.18 for score, _, _, _, _, _, _ in hit_list[1:3])
        ranked_matches.append(
            TextRetrievalMatch(
                key=top_chunk.key,
                score=aggregate_score,
                source_tier=top_chunk.source_tier,
                match_modes=match_modes,
                matched_terms=matched_terms,
                lexical_overlap=lexical_overlap,
                dense_similarity=similarity,
                exact_query_hit=exact_query_hit,
            )
        )

    ranked_matches.sort(
        key=lambda item: (
            item.score,
            1 if item.source_tier == "official" else 0,
            item.lexical_overlap,
            item.dense_similarity,
        ),
        reverse=True,
    )
    return ranked_matches[: max(1, min(limit, 200))]


def retrieve_knowledge_entry_matches(
    entries: Sequence[KnowledgeEntry],
    query: str,
    *,
    limit: int = 20,
) -> list[KnowledgeEntryMatch]:
    normalized_query = normalize_text(query)
    if not normalized_query:
        return []

    query_terms = _search_terms(normalized_query)
    if not query_terms:
        return []
    query_vector = _dense_vector(normalized_query)

    chunks: list[_KnowledgeRetrievalChunk] = []
    for entry in entries:
        chunks.extend(_build_entry_chunks(entry))
    if not chunks:
        return []
    for index, chunk in enumerate(chunks, start=1):
        chunk.chunk_id = index

    sparse_ranks = _sparse_rank(chunks, query_terms)
    dense_ranks = _dense_rank(chunks, query_vector)
    by_chunk_id = {chunk.chunk_id: chunk for chunk in chunks}

    candidate_ids = set(sparse_ranks) | set(dense_ranks)
    if not candidate_ids:
        return []
    routed_candidate_ids = _expand_routed_candidate_ids(chunks, candidate_ids)
    candidate_ids |= routed_candidate_ids

    raw_hits: list[tuple[float, _KnowledgeRetrievalChunk, tuple[str, ...], tuple[str, ...]]] = []
    for chunk_id in candidate_ids:
        chunk = by_chunk_id.get(chunk_id)
        if chunk is None:
            continue
        matched_terms = tuple(term for term in query_terms if term in chunk.search_text_lower)[:8]
        lexical_overlap = len(matched_terms)
        dense_rank = dense_ranks.get(chunk_id)
        similarity = dense_rank[1] if dense_rank else 0.0
        exact_query_hit = normalized_query.lower() in chunk.search_text_lower

        if lexical_overlap == 0 and similarity < 0.2 and not exact_query_hit and chunk_id not in routed_candidate_ids:
            continue

        score = 0.0
        match_modes: list[str] = []
        sparse_rank = sparse_ranks.get(chunk_id)
        if sparse_rank is not None:
            score += 1.0 / (_RRF_K + sparse_rank)
            match_modes.append("sparse")
        if dense_rank is not None:
            score += 1.0 / (_RRF_K + dense_rank[0]) + similarity * 0.18
            match_modes.append("dense")
        score += min(0.18, lexical_overlap * 0.035)
        if exact_query_hit:
            score += 0.06
            match_modes.append("exact")
        score += min(0.08, chunk.priority * 0.005)
        if chunk.source_tier == "official":
            score += 0.04
        if chunk.entry.is_focus_reference:
            score += 0.04
        if chunk.entry.is_pinned:
            score += 0.02
        score += _recency_bonus(chunk.entry)

        raw_hits.append(
            (
                score,
                chunk,
                tuple(_dedupe_strings(match_modes)),
                matched_terms,
            )
        )

    if not raw_hits:
        return []

    entry_parent_scores: dict[Any, float] = {}
    report_parent_scores: dict[Any, float] = {}
    section_parent_scores: dict[tuple[Any, str], float] = {}
    for score, chunk, _match_modes, _matched_terms in raw_hits:
        if chunk.field_key in _ENTRY_PARENT_FIELDS:
            entry_parent_scores[chunk.entry_id] = max(entry_parent_scores.get(chunk.entry_id, 0.0), score)
        if chunk.field_key == "report_summary":
            report_parent_scores[chunk.entry_id] = max(report_parent_scores.get(chunk.entry_id, 0.0), score)
        if chunk.field_key == "section_summary" and chunk.section_title:
            route_key = (chunk.entry_id, chunk.section_title)
            section_parent_scores[route_key] = max(section_parent_scores.get(route_key, 0.0), score)

    entry_hits: dict[Any, list[tuple[float, _KnowledgeRetrievalChunk, tuple[str, ...], tuple[str, ...], bool]]] = {}
    for score, chunk, match_modes, matched_terms in raw_hits:
        adjusted_score, routed = _boost_knowledge_chunk_score(
            chunk,
            base_score=score,
            entry_parent_scores=entry_parent_scores,
            report_parent_scores=report_parent_scores,
            section_parent_scores=section_parent_scores,
        )
        adjusted_modes = list(match_modes)
        if routed:
            adjusted_modes.append("routed")
        entry_hits.setdefault(chunk.entry_id, []).append(
            (
                adjusted_score,
                chunk,
                tuple(_dedupe_strings(adjusted_modes)),
                matched_terms,
                routed,
            )
        )

    ranked_entries: list[KnowledgeEntryMatch] = []
    for hit_list in entry_hits.values():
        if not hit_list:
            continue
        hit_list.sort(key=lambda item: item[0], reverse=True)
        top_score = hit_list[0][0]
        preview_score, preview_chunk, preview_modes, preview_terms, _preview_routed = _select_preview_hit(hit_list)
        aggregate_score = top_score + sum(score * 0.18 for score, _, _, _, _ in hit_list[1:3])
        preview = KnowledgeRetrievalPreview(
            snippet=_truncate_snippet(preview_chunk.text),
            label=preview_chunk.label,
            field_key=preview_chunk.field_key,
            section_title=preview_chunk.section_title,
            source_tier=preview_chunk.source_tier,
            score=aggregate_score,
            match_modes=preview_modes,
            matched_terms=preview_terms,
        )
        ranked_entries.append(
            KnowledgeEntryMatch(
                entry=preview_chunk.entry,
                score=aggregate_score,
                preview=preview,
            )
        )

    ranked_entries.sort(
        key=lambda item: (
            item.score,
            1 if item.preview.source_tier == "official" else 0,
            1 if item.entry.is_focus_reference else 0,
            1 if item.entry.is_pinned else 0,
            item.entry.created_at or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )
    return ranked_entries[: max(1, min(limit, 100))]
