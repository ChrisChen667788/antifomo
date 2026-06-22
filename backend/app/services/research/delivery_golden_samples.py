from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

from app.services.content_extractor import normalize_text


DATASET_PATH = Path(__file__).resolve().parents[3] / "evaluation" / "delivery_golden_samples_v1.json"


@dataclass(frozen=True, slots=True)
class DeliveryGoldenSample:
    sample_id: str
    title: str
    source_basis: str
    document_types: tuple[str, ...]
    scenario_terms: tuple[str, ...]
    target_entities: tuple[str, ...]
    required_scope_terms: tuple[str, ...]
    forbidden_scope_terms: tuple[str, ...]
    required_sections: tuple[str, ...]
    review_rubric: tuple[str, ...]
    min_alignment_score: int
    max_scope_drift_issues: int
    requires_evidence_ledger: bool


@dataclass(frozen=True, slots=True)
class DeliveryGoldenSampleMatch:
    sample: DeliveryGoldenSample | None
    score: int
    matched_terms: tuple[str, ...]
    missing_required_terms: tuple[str, ...]
    forbidden_hits: tuple[str, ...]
    missing_sections: tuple[str, ...]


def _as_tuple(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list):
        return ()
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = normalize_text(str(value or ""))
        if not text or text in seen:
            continue
        rows.append(text)
        seen.add(text)
    return tuple(rows)


def _sample_from_dict(raw: dict[str, Any]) -> DeliveryGoldenSample:
    acceptance = raw.get("acceptance") if isinstance(raw.get("acceptance"), dict) else {}
    return DeliveryGoldenSample(
        sample_id=normalize_text(raw.get("sample_id")),
        title=normalize_text(raw.get("title")),
        source_basis=normalize_text(raw.get("source_basis")),
        document_types=_as_tuple(raw.get("document_types")),
        scenario_terms=_as_tuple(raw.get("scenario_terms")),
        target_entities=_as_tuple(raw.get("target_entities")),
        required_scope_terms=_as_tuple(raw.get("required_scope_terms")),
        forbidden_scope_terms=_as_tuple(raw.get("forbidden_scope_terms")),
        required_sections=_as_tuple(raw.get("required_sections")),
        review_rubric=_as_tuple(raw.get("review_rubric")),
        min_alignment_score=int(acceptance.get("min_alignment_score") or 80),
        max_scope_drift_issues=int(acceptance.get("max_scope_drift_issues") or 0),
        requires_evidence_ledger=bool(acceptance.get("requires_evidence_ledger", True)),
    )


def load_delivery_golden_samples(path: Path = DATASET_PATH) -> tuple[DeliveryGoldenSample, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    samples = payload.get("samples") if isinstance(payload, dict) else []
    if not isinstance(samples, list):
        return ()
    rows = [_sample_from_dict(item) for item in samples if isinstance(item, dict)]
    return tuple(sample for sample in rows if sample.sample_id and sample.title)


def _contains_any(text: str, terms: Iterable[str]) -> list[str]:
    lowered = text.lower()
    rows: list[str] = []
    for term in terms:
        normalized = normalize_text(term)
        if normalized and normalized.lower() in lowered:
            rows.append(normalized)
    return rows


def match_delivery_golden_sample(
    rows: Iterable[object],
    *,
    expected_scope_terms: Sequence[str] = (),
    document_kind: str = "",
    samples: Sequence[DeliveryGoldenSample] | None = None,
) -> DeliveryGoldenSampleMatch:
    sample_rows = tuple(samples) if samples is not None else load_delivery_golden_samples()
    text = normalize_text(" ".join(str(row or "") for row in rows))
    scope_hint = normalize_text(" ".join([*[str(term or "") for term in expected_scope_terms], document_kind]))
    hint_text = normalize_text(" ".join([text, scope_hint]))
    if not sample_rows or not hint_text:
        return DeliveryGoldenSampleMatch(
            sample=None,
            score=0,
            matched_terms=(),
            missing_required_terms=(),
            forbidden_hits=(),
            missing_sections=(),
        )

    scored: list[tuple[int, DeliveryGoldenSample]] = []
    for sample in sample_rows:
        hint_scenario_hits = _contains_any(scope_hint, sample.scenario_terms)
        hint_entity_hits = _contains_any(scope_hint, sample.target_entities)
        hint_required_hits = _contains_any(scope_hint, sample.required_scope_terms)
        text_scenario_hits = _contains_any(text, sample.scenario_terms)
        text_entity_hits = _contains_any(text, sample.target_entities)
        text_required_hits = _contains_any(text, sample.required_scope_terms)
        document_hit = 1 if document_kind and document_kind in sample.document_types else 0
        scope_lock_bonus = 30 if (hint_scenario_hits or hint_entity_hits or hint_required_hits) else 0
        score = (
            len(hint_scenario_hits) * 10
            + len(hint_entity_hits) * 12
            + len(hint_required_hits) * 8
            + len(text_scenario_hits) * 3
            + len(text_entity_hits) * 3
            + len(text_required_hits) * 2
            + document_hit * 8
            + scope_lock_bonus
        )
        scored.append((score, sample))
    scored.sort(key=lambda item: (-item[0], item[1].sample_id))
    best_score, best = scored[0]
    if best_score <= 0:
        return DeliveryGoldenSampleMatch(
            sample=None,
            score=0,
            matched_terms=(),
            missing_required_terms=(),
            forbidden_hits=(),
            missing_sections=(),
        )

    required_hits = tuple(_contains_any(hint_text, best.required_scope_terms))
    forbidden_hits = tuple(_contains_any(text, best.forbidden_scope_terms))
    section_hits = _contains_any(text, best.required_sections)
    missing_required = tuple(term for term in best.required_scope_terms if term not in required_hits)
    missing_sections = tuple(term for term in best.required_sections if term not in section_hits)

    required_score = round(46 * len(required_hits) / max(len(best.required_scope_terms), 1))
    section_score = round(24 * len(section_hits) / max(len(best.required_sections), 1))
    scenario_score = min(20, len(_contains_any(hint_text, best.scenario_terms)) * 4)
    entity_score = min(10, len(_contains_any(hint_text, best.target_entities)) * 5)
    penalty = min(35, len(forbidden_hits) * 14)
    alignment = max(0, min(100, required_score + section_score + scenario_score + entity_score - penalty))

    return DeliveryGoldenSampleMatch(
        sample=best,
        score=alignment,
        matched_terms=tuple(dict.fromkeys([*required_hits, *_contains_any(hint_text, best.scenario_terms)])),
        missing_required_terms=missing_required,
        forbidden_hits=forbidden_hits,
        missing_sections=missing_sections,
    )
