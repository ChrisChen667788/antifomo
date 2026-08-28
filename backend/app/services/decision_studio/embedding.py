from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from functools import lru_cache
import math
import os
from pathlib import Path
import re
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.decision_studio_entities import DecisionPassage, DecisionSource, DecisionSourceRevision


class SemanticBackendUnavailable(RuntimeError):
    pass


class EmbeddingBackend(Protocol):
    @property
    def model_name(self) -> str: ...

    def encode(self, texts: Sequence[str]) -> list[list[float]]: ...


class SentenceTransformerBackend:
    def __init__(
        self,
        model_name: str,
        *,
        batch_size: int = 16,
        cache_dir: str | None = None,
        xet_cache_dir: str | None = None,
        disable_symlinks: bool = False,
        device: str = "auto",
    ) -> None:
        self._model_name = model_name
        self._batch_size = max(1, min(batch_size, 128))
        self._cache_dir = cache_dir
        self._xet_cache_dir = xet_cache_dir
        self._disable_symlinks = disable_symlinks
        self._device = device

    @property
    def model_name(self) -> str:
        return self._model_name

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            model = _load_sentence_transformer(
                self._model_name,
                self._cache_dir,
                self._xet_cache_dir,
                self._disable_symlinks,
                self._device,
            )
            vectors = model.encode(
                list(texts),
                batch_size=self._batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception as exc:  # model loading can fail offline or on unsupported hardware
            raise SemanticBackendUnavailable(f"SentenceTransformer {self._model_name} unavailable: {exc}") from exc
        return [[float(value) for value in vector] for vector in vectors]


@lru_cache(maxsize=2)
def _load_sentence_transformer(
    model_name: str,
    cache_dir: str | None = None,
    xet_cache_dir: str | None = None,
    disable_symlinks: bool = False,
    device: str = "auto",
):
    resolved_cache_dir = _prepare_cache_dir(cache_dir, label="Hugging Face Hub")
    resolved_xet_cache_dir = _prepare_cache_dir(xet_cache_dir, label="Hugging Face Xet")
    if resolved_cache_dir:
        os.environ["HF_HUB_CACHE"] = resolved_cache_dir
    if resolved_xet_cache_dir:
        os.environ["HF_XET_CACHE"] = resolved_xet_cache_dir
    if disable_symlinks:
        os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

    from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

    kwargs: dict[str, object] = {"trust_remote_code": False}
    if resolved_cache_dir:
        kwargs["cache_folder"] = resolved_cache_dir
    if device != "auto":
        kwargs["device"] = device
    return SentenceTransformer(model_name, **kwargs)


def _prepare_cache_dir(raw_path: str | None, *, label: str) -> str | None:
    if not raw_path or not raw_path.strip():
        return None
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        raise SemanticBackendUnavailable(f"{label} cache path must be absolute: {path}")
    if len(path.parts) >= 3 and path.parts[1] == "Volumes":
        volume_path = Path("/") / path.parts[1] / path.parts[2]
        if not volume_path.is_mount():
            raise SemanticBackendUnavailable(f"External cache volume is not mounted: {volume_path}")
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SemanticBackendUnavailable(f"Cannot create {label} cache directory {path}: {exc}") from exc
    if not os.access(path, os.R_OK | os.W_OK):
        raise SemanticBackendUnavailable(f"{label} cache directory is not readable and writable: {path}")
    return str(path)


def build_embedding_backend() -> EmbeddingBackend:
    settings = get_settings()
    if not settings.decision_embedding_enabled or settings.decision_embedding_provider == "disabled":
        raise SemanticBackendUnavailable("Decision Studio semantic embedding is disabled.")
    return SentenceTransformerBackend(
        settings.decision_embedding_model,
        batch_size=settings.decision_embedding_batch_size,
        cache_dir=settings.decision_embedding_cache_dir,
        xet_cache_dir=settings.decision_embedding_xet_cache_dir,
        disable_symlinks=settings.decision_embedding_disable_symlinks,
        device=settings.decision_embedding_device,
    )


def _current_passage_rows(
    db: Session,
    *,
    notebook_id: UUID,
    included_source_ids: Sequence[UUID] | None = None,
) -> list[tuple[DecisionPassage, DecisionSourceRevision, DecisionSource]]:
    now = datetime.now(UTC)
    query = (
        select(DecisionPassage, DecisionSourceRevision, DecisionSource)
        .join(DecisionSourceRevision, DecisionSourceRevision.id == DecisionPassage.revision_id)
        .join(DecisionSource, DecisionSource.id == DecisionSourceRevision.source_id)
        .where(DecisionSource.notebook_id == notebook_id)
        .where(DecisionSource.current_revision_id == DecisionSourceRevision.id)
        .where(DecisionSource.admission_status == "accepted")
        .where(DecisionSource.trust_status.notin_(["revoked", "expired"]))
        .order_by(DecisionSource.title, DecisionPassage.sequence)
    )
    if included_source_ids is not None:
        if not included_source_ids:
            return []
        query = query.where(DecisionSource.id.in_(list(included_source_ids)))
    rows = list(db.execute(query).all())
    return [row for row in rows if row[2].expires_at is None or _as_utc(row[2].expires_at) > now]


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def index_notebook_passages(
    db: Session,
    *,
    notebook_id: UUID,
    backend: EmbeddingBackend | None = None,
) -> dict[str, object]:
    effective_backend = backend or build_embedding_backend()
    rows = _current_passage_rows(db, notebook_id=notebook_id)
    passages = [row[0] for row in rows]
    vectors = effective_backend.encode([passage.text for passage in passages])
    if len(vectors) != len(passages):
        raise SemanticBackendUnavailable("Embedding backend returned a mismatched vector count.")
    dimension = 0
    for passage, vector in zip(passages, vectors, strict=True):
        dimension = len(vector)
        passage.embedding = vector
        passage.embedding_model = effective_backend.model_name
    db.commit()
    return {
        "status": "ready",
        "backend": "sentence_transformers",
        "model": effective_backend.model_name,
        "indexed_passage_count": len(passages),
        "dimension": dimension,
    }


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or len(left) != len(right):
        return -1.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm <= 0 or right_norm <= 0:
        return -1.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def _terms(text: str) -> set[str]:
    normalized = text.lower()
    latin = re.findall(r"[a-z0-9]{2,}", normalized)
    compact = re.sub(r"\s+", "", normalized)
    chinese = [compact[index : index + 2] for index in range(max(0, len(compact) - 1))]
    return set(latin + chinese)


def _lexical_score(query: str, text: str) -> float:
    query_terms = _terms(query)
    if not query_terms:
        return 0.0
    text_terms = _terms(text)
    overlap = len(query_terms & text_terms)
    return overlap / max(1, len(query_terms))


def _hit_payload(
    passage: DecisionPassage,
    revision: DecisionSourceRevision,
    source: DecisionSource,
    *,
    score: float,
    mode: str,
    ranking: dict[str, float | int] | None = None,
) -> dict[str, object]:
    return {
        "passage_id": str(passage.id),
        "source_id": str(source.id),
        "source_title": source.title,
        "source_uri": source.source_uri,
        "source_revision_id": str(revision.id),
        "revision_number": revision.revision_number,
        "text": passage.text,
        "score": round(score, 6),
        "mode": mode,
        "ranking": ranking or {},
        "locator": {
            **dict(passage.locator_payload or {}),
            "page": passage.page_number,
            "paragraph": passage.paragraph_number,
            "start_seconds": passage.start_seconds,
            "end_seconds": passage.end_seconds,
        },
    }


def search_notebook_passages(
    db: Session,
    *,
    notebook_id: UUID,
    query: str,
    included_source_ids: Sequence[UUID] | None = None,
    limit: int = 8,
    require_semantic: bool = False,
    retrieval_mode: str = "semantic",
    backend: EmbeddingBackend | None = None,
) -> dict[str, object]:
    if retrieval_mode not in {"semantic", "hybrid", "lexical"}:
        raise ValueError("Retrieval mode must be semantic, hybrid, or lexical.")
    rows = _current_passage_rows(
        db,
        notebook_id=notebook_id,
        included_source_ids=included_source_ids,
    )
    capped_limit = max(1, min(limit, 30))
    indexed_rows = [row for row in rows if row[0].embedding and row[0].embedding_model]
    warnings: list[str] = []
    if retrieval_mode == "lexical":
        ranked_lexical = sorted(
            ((_lexical_score(query, passage.text), passage, revision, source) for passage, revision, source in rows),
            key=lambda row: row[0],
            reverse=True,
        )
        return {
            "status": "ready",
            "mode": "lexical",
            "model": "",
            "included_source_ids": [str(value) for value in included_source_ids] if included_source_ids is not None else None,
            "warnings": [],
            "hits": [
                _hit_payload(passage, revision, source, score=score, mode="lexical")
                for score, passage, revision, source in ranked_lexical[:capped_limit]
                if score > 0
            ],
        }
    if indexed_rows:
        effective_backend = backend or build_embedding_backend()
        query_vector = effective_backend.encode([query])[0]
        expected_model = indexed_rows[0][0].embedding_model
        if effective_backend.model_name != expected_model:
            message = f"Query model {effective_backend.model_name} does not match index model {expected_model}."
            if require_semantic:
                raise SemanticBackendUnavailable(message)
            warnings.append(message)
        else:
            ranked = sorted(
                (
                    (_cosine(query_vector, passage.embedding), passage, revision, source)
                    for passage, revision, source in indexed_rows
                ),
                key=lambda row: row[0],
                reverse=True,
            )
            if retrieval_mode == "hybrid":
                lexical_ranked = sorted(
                    ((_lexical_score(query, passage.text), passage, revision, source) for passage, revision, source in rows),
                    key=lambda row: row[0],
                    reverse=True,
                )
                semantic_positions = {str(row[1].id): index for index, row in enumerate(ranked, start=1)}
                lexical_positions = {str(row[1].id): index for index, row in enumerate(lexical_ranked, start=1)}
                row_lookup = {str(row[1].id): row[1:] for row in ranked}
                fused = sorted(
                    (
                        (
                            (1.0 / (60 + semantic_positions[passage_id]))
                            + (1.0 / (60 + lexical_positions.get(passage_id, len(rows) + 1))),
                            passage_id,
                        )
                        for passage_id in semantic_positions
                    ),
                    reverse=True,
                )
                return {
                    "status": "ready",
                    "mode": "hybrid_rrf",
                    "model": effective_backend.model_name,
                    "included_source_ids": [str(value) for value in included_source_ids] if included_source_ids is not None else None,
                    "warnings": warnings,
                    "hits": [
                        _hit_payload(
                            row_lookup[passage_id][0],
                            row_lookup[passage_id][1],
                            row_lookup[passage_id][2],
                            score=score,
                            mode="hybrid_rrf",
                            ranking={
                                "semantic_rank": semantic_positions[passage_id],
                                "lexical_rank": lexical_positions.get(passage_id, len(rows) + 1),
                            },
                        )
                        for score, passage_id in fused[:capped_limit]
                    ],
                }
            return {
                "status": "ready",
                "mode": "semantic",
                "model": effective_backend.model_name,
                "included_source_ids": [str(value) for value in included_source_ids] if included_source_ids is not None else None,
                "warnings": warnings,
                "hits": [
                    _hit_payload(passage, revision, source, score=score, mode="semantic")
                    for score, passage, revision, source in ranked[:capped_limit]
                ],
            }
    message = "No real semantic index is available for the selected sources."
    if require_semantic:
        raise SemanticBackendUnavailable(message)
    warnings.append(message)
    ranked_lexical = sorted(
        (
            (_lexical_score(query, passage.text), passage, revision, source)
            for passage, revision, source in rows
        ),
        key=lambda row: row[0],
        reverse=True,
    )
    return {
        "status": "degraded",
        "mode": "lexical_fallback",
        "model": "",
        "included_source_ids": [str(value) for value in included_source_ids] if included_source_ids is not None else None,
        "warnings": warnings,
        "hits": [
            _hit_payload(passage, revision, source, score=score, mode="lexical_fallback")
            for score, passage, revision, source in ranked_lexical[:capped_limit]
            if score > 0
        ],
    }
