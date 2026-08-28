from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.services.content_extractor import normalize_text
from app.services.industry_knowledge_rag import (
    DEFAULT_INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGY,
    INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGIES,
    hybrid_search_industry_knowledge,
    industry_knowledge_retrieval_strategy_catalog,
    knowledge_base_public_status,
    load_knowledge_base_manifest,
)
from app.services.industry_skill_library import resolve_library_dir


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BENCHMARK_ID = "industry-knowledge-retrieval-ranking-ab-v1"
DATASET_PATH = PROJECT_ROOT / "backend" / "evaluation" / "industry_knowledge_retrieval_ranking_v1.json"
DEFAULT_ARTIFACT_PATH = PROJECT_ROOT / ".tmp" / f"{BENCHMARK_ID}.json"
DEFAULT_REVIEW_PATH = PROJECT_ROOT / ".tmp" / f"{BENCHMARK_ID}-human-review.json"
DEFAULT_REVIEW_SAMPLE_DIR = PROJECT_ROOT / ".tmp" / BENCHMARK_ID / "review-samples"
RETRIEVAL_LIMIT = 10
STRATEGY_KEYS = tuple(INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGIES)

# A candidate needs a real quality improvement while preserving all retrieval
# guardrails.  These are deliberately conservative because this benchmark is
# used to decide the production default for a user-facing research flow.
MAX_GUARDRAIL_REGRESSION = 0.01
MIN_MEANINGFUL_UPLIFT = 0.01
MIN_HUMAN_REVIEW_SCORE = 4.0
MAX_LATENCY_MULTIPLIER = 2.0
REVIEW_PROTOCOL_VERSION = "industry-knowledge-retrieval-review-v2"


@dataclass(frozen=True, slots=True)
class RetrievalBenchmarkCase:
    case_id: str
    query: str
    industries: tuple[str, ...]
    document_types: tuple[str, ...]
    relevant_document_ids: tuple[str, ...]
    relevance_by_document_id: dict[str, int]
    expected_citation_terms: tuple[str, ...]
    review_note: str = ""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def industry_knowledge_benchmark_artifact_reference(path: str | Path) -> str:
    """Return a stable project-relative artifact reference without leaking local roots."""
    resolved = Path(path).expanduser().resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return resolved.name


def _dataset_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def industry_knowledge_retrieval_benchmark_digest(payload: Mapping[str, Any]) -> str:
    """Hash the fixed retrieval evidence without invalidating active human review.

    The binding intentionally excludes generated times, human scores, promotion
    decisions, and timing. Those fields change during review; retrieved
    documents, visible evidence, and actual reranker provenance must not.
    """

    arm_bindings: list[dict[str, Any]] = []
    raw_arms = payload.get("arms")
    if isinstance(raw_arms, Sequence) and not isinstance(raw_arms, (str, bytes)):
        for arm in raw_arms:
            if not isinstance(arm, Mapping):
                continue
            case_bindings: list[dict[str, Any]] = []
            raw_cases = arm.get("cases")
            if isinstance(raw_cases, Sequence) and not isinstance(raw_cases, (str, bytes)):
                for case in raw_cases:
                    if not isinstance(case, Mapping):
                        continue
                    references: list[dict[str, Any]] = []
                    raw_references = case.get("retrieved_references")
                    if isinstance(raw_references, Sequence) and not isinstance(raw_references, (str, bytes)):
                        for reference in raw_references:
                            if not isinstance(reference, Mapping):
                                continue
                            references.append(
                                {
                                    "document_id": normalize_text(str(reference.get("document_id") or "")),
                                    "title": normalize_text(str(reference.get("title") or "")),
                                    "locator": normalize_text(str(reference.get("locator") or "")),
                                    "snippet": normalize_text(str(reference.get("snippet") or "")),
                                    "match_modes": list(_normalized_strings(reference.get("match_modes"))),
                                }
                            )
                    case_bindings.append(
                        {
                            "case_id": normalize_text(str(case.get("case_id") or "")),
                            "query": normalize_text(str(case.get("query") or "")),
                            "result_document_ids": list(_normalized_strings(case.get("result_document_ids"))),
                            "retrieved_references": references,
                            "recall_at_10": case.get("recall_at_10"),
                            "ndcg_at_10": case.get("ndcg_at_10"),
                            "citation_hit_rate": case.get("citation_hit_rate"),
                            "rerank_applied": bool(case.get("rerank_applied")),
                            "rerank_backend": normalize_text(str(case.get("rerank_backend") or "")),
                            "rerank_model": normalize_text(str(case.get("rerank_model") or "")),
                        }
                    )
            arm_bindings.append(
                {
                    "strategy": normalize_text(str(arm.get("strategy") or "")),
                    "case_count": arm.get("case_count"),
                    "rerank_applied_case_count": arm.get("rerank_applied_case_count"),
                    "rerank_backend": normalize_text(str(arm.get("rerank_backend") or "")),
                    "rerank_model": normalize_text(str(arm.get("rerank_model") or "")),
                    "cases": sorted(case_bindings, key=lambda item: str(item["case_id"])),
                }
            )
    binding = {
        "benchmark_id": normalize_text(str(payload.get("benchmark_id") or "")),
        "dataset_version": normalize_text(str(payload.get("dataset_version") or "")),
        "dataset_sha256": normalize_text(str(payload.get("dataset_sha256") or "")),
        "knowledge_base_generation_id": normalize_text(str(payload.get("knowledge_base_generation_id") or "")),
        "case_count": payload.get("case_count"),
        "arms": sorted(arm_bindings, key=lambda item: str(item["strategy"])),
    }
    encoded = json.dumps(binding, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalized_strings(values: object) -> tuple[str, ...]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return ()
    rows: list[str] = []
    for value in values:
        normalized = normalize_text(str(value or ""))
        if normalized and normalized not in rows:
            rows.append(normalized)
    return tuple(rows)


def load_industry_knowledge_retrieval_benchmark_dataset(
    dataset_path: str | Path = DATASET_PATH,
) -> tuple[dict[str, Any], list[RetrievalBenchmarkCase]]:
    path = Path(dataset_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("检索排序评测集必须是 JSON 对象。")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("检索排序评测集至少需要一个题目。")

    cases: list[RetrievalBenchmarkCase] = []
    seen_case_ids: set[str] = set()
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise ValueError("检索排序评测集包含无效题目。")
        case_id = normalize_text(str(raw_case.get("case_id") or ""))
        query = normalize_text(str(raw_case.get("query") or ""))
        relevant_document_ids = _normalized_strings(raw_case.get("relevant_document_ids"))
        if not case_id or not query or not relevant_document_ids:
            raise ValueError("每个检索排序题目都必须包含 case_id、query 与 relevant_document_ids。")
        if case_id in seen_case_ids:
            raise ValueError(f"检索排序评测集存在重复 case_id：{case_id}")
        seen_case_ids.add(case_id)
        raw_relevance = raw_case.get("relevance_by_document_id")
        raw_relevance_mapping = raw_relevance if isinstance(raw_relevance, dict) else {}
        relevance = {
            document_id: max(0, int(value or 0))
            for document_id, value in raw_relevance_mapping.items()
            if document_id in relevant_document_ids
        }
        for document_id in relevant_document_ids:
            relevance.setdefault(document_id, 1)
        expected_terms = _normalized_strings(raw_case.get("expected_citation_terms"))
        if not expected_terms:
            raise ValueError(f"检索排序题目 {case_id} 缺少 expected_citation_terms。")
        cases.append(
            RetrievalBenchmarkCase(
                case_id=case_id,
                query=query,
                industries=_normalized_strings(raw_case.get("industries")),
                document_types=_normalized_strings(raw_case.get("document_types")),
                relevant_document_ids=relevant_document_ids,
                relevance_by_document_id=relevance,
                expected_citation_terms=expected_terms,
                review_note=normalize_text(str(raw_case.get("review_note") or "")),
            )
        )
    return dict(payload), cases


def _dedupe_document_ids(hits: Sequence[Mapping[str, Any]]) -> list[str]:
    document_ids: list[str] = []
    for hit in hits:
        document_id = normalize_text(str(hit.get("document_id") or ""))
        if document_id and document_id not in document_ids:
            document_ids.append(document_id)
    return document_ids[:RETRIEVAL_LIMIT]


def _review_references(hits: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Keep only the public evidence fields needed by the reviewer sample."""
    references: list[dict[str, Any]] = []
    for hit in hits[:RETRIEVAL_LIMIT]:
        document_id = normalize_text(str(hit.get("document_id") or ""))
        if not document_id:
            continue
        references.append(
            {
                "document_id": document_id,
                "title": normalize_text(str(hit.get("title") or "")),
                "locator": normalize_text(str(hit.get("locator") or "")),
                "snippet": normalize_text(str(hit.get("snippet") or "")),
                "match_modes": list(_normalized_strings(hit.get("match_modes"))),
            }
        )
    return references


def _recall_at_k(case: RetrievalBenchmarkCase, document_ids: Sequence[str]) -> float:
    relevant = set(case.relevant_document_ids)
    return round(len(relevant.intersection(document_ids[:RETRIEVAL_LIMIT])) / max(1, len(relevant)), 6)


def _ndcg_at_k(case: RetrievalBenchmarkCase, document_ids: Sequence[str]) -> float:
    ranked_relevance = [case.relevance_by_document_id.get(document_id, 0) for document_id in document_ids[:RETRIEVAL_LIMIT]]
    dcg = sum((2**relevance - 1) / math.log2(rank + 2) for rank, relevance in enumerate(ranked_relevance))
    ideal_relevance = sorted(case.relevance_by_document_id.values(), reverse=True)[:RETRIEVAL_LIMIT]
    ideal_dcg = sum((2**relevance - 1) / math.log2(rank + 2) for rank, relevance in enumerate(ideal_relevance))
    return round(dcg / ideal_dcg, 6) if ideal_dcg else 0.0


def _citation_hit_rate(case: RetrievalBenchmarkCase, hits: Sequence[Mapping[str, Any]]) -> float:
    visible_text = "\n".join(
        normalize_text(
            " ".join(
                [
                    str(hit.get("title") or ""),
                    str(hit.get("snippet") or ""),
                    str(hit.get("locator") or ""),
                ]
            )
        ).lower()
        for hit in hits[:RETRIEVAL_LIMIT]
    )
    if not visible_text:
        return 0.0
    matched = sum(1 for term in case.expected_citation_terms if term.lower() in visible_text)
    return round(matched / len(case.expected_citation_terms), 6)


def _mean(values: Sequence[float | None]) -> float | None:
    selected = [float(value) for value in values if value is not None]
    return round(sum(selected) / len(selected), 6) if selected else None


def _metric_map(arm: Mapping[str, Any]) -> dict[str, float | None]:
    return {str(metric.get("key") or ""): metric.get("value") for metric in arm.get("metrics", [])}


def _load_human_review_scores(
    path: Path,
    *,
    dataset_sha256: str,
    benchmark_digest: str,
) -> tuple[dict[tuple[str, str], float], list[str]]:
    if not path.is_file():
        return {}, ["尚未生成或完成报告人工评分；上线门禁将保持 HOLD。"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, ["报告人工评分工件不可读取；上线门禁将保持 HOLD。"]
    if not isinstance(payload, dict):
        return {}, ["报告人工评分工件格式无效；上线门禁将保持 HOLD。"]
    if payload.get("dataset_sha256") != dataset_sha256:
        return {}, ["报告人工评分对应的固定题集已变化，旧评分不能复用。"]
    if normalize_text(str(payload.get("review_status") or "")).lower() != "complete":
        return {}, ["报告人工评分尚未标记 complete，不能作为上线证据。"]
    if normalize_text(str(payload.get("review_protocol_version") or "")) != REVIEW_PROTOCOL_VERSION:
        return {}, [f"报告人工评分缺少 {REVIEW_PROTOCOL_VERSION} 复核协议，不能作为上线证据。"]
    if normalize_text(str(payload.get("benchmark_digest") or "")) != benchmark_digest:
        return {}, ["报告人工评分未绑定当前固定检索结果摘要，旧评分不能作为上线证据。"]
    if not all(
        normalize_text(str(payload.get(key) or ""))
        for key in ("reviewer_name", "reviewer_role", "reviewed_at")
    ):
        return {}, ["报告人工评分缺少评审人、角色或复核时间，不能作为上线证据。"]
    if not normalize_text(str(payload.get("attestation") or "")):
        return {}, ["报告人工评分缺少复核声明，不能作为上线证据。"]
    if not normalize_text(str(payload.get("independence_attestation") or "")):
        return {}, ["报告人工评分缺少独立性声明，不能作为上线证据。"]
    if not normalize_text(str(payload.get("conflict_disclosure") or "")):
        return {}, ["报告人工评分缺少利益冲突披露，不能作为上线证据。"]
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list):
        return {}, ["报告人工评分工件缺少 entries，不能作为上线证据。"]
    scores: dict[tuple[str, str], float] = {}
    entries_missing_report_artifact = 0
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        case_id = normalize_text(str(entry.get("case_id") or ""))
        strategy = normalize_text(str(entry.get("strategy") or ""))
        try:
            score = float(entry.get("human_review_score"))
        except (TypeError, ValueError):
            continue
        if not case_id or strategy not in STRATEGY_KEYS or not 1.0 <= score <= 5.0:
            continue
        if not normalize_text(str(entry.get("report_artifact_path") or "")):
            entries_missing_report_artifact += 1
            continue
        scores[(case_id, strategy)] = round(score, 3)
    if not scores:
        return {}, ["报告人工评分没有关联完整报告工件的有效 1-5 分记录，不能作为上线证据。"]
    warnings: list[str] = []
    if entries_missing_report_artifact:
        warnings.append(f"{entries_missing_report_artifact} 条人工评分未关联 report_artifact_path，已排除出上线证据。")
    return scores, warnings


def _evaluate_arm(
    case_list: Sequence[RetrievalBenchmarkCase],
    *,
    library_dir: Path,
    strategy: str,
    human_scores: Mapping[tuple[str, str], float],
) -> dict[str, Any]:
    spec = INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGIES[strategy]  # strategy is controlled by STRATEGY_KEYS
    results: list[dict[str, Any]] = []
    for case in case_list:
        started = time.perf_counter()
        outcome = hybrid_search_industry_knowledge(
            library_dir,
            query=case.query,
            industries=case.industries,
            document_types=case.document_types,
            limit=RETRIEVAL_LIMIT,
            strategy=strategy,
        )
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        hits = list(outcome.get("hits") or [])
        document_ids = _dedupe_document_ids(hits)
        results.append(
            {
                "case_id": case.case_id,
                "query": case.query,
                "strategy": strategy,
                "result_document_ids": document_ids,
                "retrieved_references": _review_references(hits),
                "recall_at_10": _recall_at_k(case, document_ids),
                "ndcg_at_10": _ndcg_at_k(case, document_ids),
                "citation_hit_rate": _citation_hit_rate(case, hits),
                "human_review_score": human_scores.get((case.case_id, strategy)),
                "latency_ms": latency_ms,
                "rerank_applied": bool(outcome.get("rerank_applied")),
                "rerank_backend": str(outcome.get("rerank_backend") or "disabled"),
                "rerank_model": normalize_text(str(outcome.get("rerank_model") or "")),
                "review_note": case.review_note,
            }
        )
    rerank_backends = sorted({item["rerank_backend"] for item in results if item["rerank_backend"] != "disabled"})
    rerank_models = sorted({item["rerank_model"] for item in results if item["rerank_model"]})
    return {
        "strategy": strategy,
        "label": spec.label,
        "role": "baseline" if strategy == DEFAULT_INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGY else "candidate",
        "case_count": len(results),
        "rerank_applied_case_count": sum(1 for item in results if item["rerank_applied"]),
        "rerank_backend": ", ".join(rerank_backends) if rerank_backends else "disabled",
        "rerank_model": ", ".join(rerank_models),
        "cases": results,
    }


def _with_metrics(
    arm: dict[str, Any],
    *,
    baseline_metrics: Mapping[str, float | None] | None,
) -> dict[str, Any]:
    results = list(arm.get("cases") or [])
    values = {
        "recall_at_10": _mean([item.get("recall_at_10") for item in results]),
        "ndcg_at_10": _mean([item.get("ndcg_at_10") for item in results]),
        "citation_hit_rate": _mean([item.get("citation_hit_rate") for item in results]),
        "human_review_score": _mean([item.get("human_review_score") for item in results]),
        "latency_ms": _mean([item.get("latency_ms") for item in results]),
    }
    labels = {
        "recall_at_10": "Recall@10",
        "ndcg_at_10": "nDCG@10",
        "citation_hit_rate": "引用命中率",
        "human_review_score": "报告人工评分",
        "latency_ms": "平均延迟（ms）",
    }
    metrics: list[dict[str, Any]] = []
    for key, value in values.items():
        baseline_value = baseline_metrics.get(key) if baseline_metrics is not None else value
        available = value is not None
        metrics.append(
            {
                "key": key,
                "label": labels[key],
                "value": value,
                "baseline_value": baseline_value,
                "delta": round(value - baseline_value, 6) if value is not None and baseline_value is not None else None,
                "available": available,
                "note": "待人工复核完整研报后录入 1-5 分。" if key == "human_review_score" and not available else "",
            }
        )
    arm["metrics"] = metrics
    return arm


def _apply_human_scores(
    arms: Sequence[Mapping[str, Any]],
    human_scores: Mapping[tuple[str, str], float],
) -> list[dict[str, Any]]:
    """Attach bound human scores without issuing another retrieval pass."""
    refreshed: list[dict[str, Any]] = []
    baseline_metrics: Mapping[str, float | None] | None = None

    for raw_arm in arms:
        arm = dict(raw_arm)
        cases: list[dict[str, Any]] = []
        for raw_case in arm.get("cases") or []:
            if not isinstance(raw_case, Mapping):
                continue
            case = dict(raw_case)
            key = (
                normalize_text(str(case.get("case_id") or "")),
                normalize_text(str(arm.get("strategy") or "")),
            )
            case["human_review_score"] = human_scores.get(key)
            cases.append(case)
        arm["cases"] = cases
        arm = _with_metrics(arm, baseline_metrics=baseline_metrics)
        if arm.get("strategy") == DEFAULT_INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGY:
            baseline_metrics = _metric_map(arm)
        refreshed.append(arm)

    return refreshed


def _promotion_decision(
    arms: Sequence[Mapping[str, Any]],
    *,
    case_count: int,
) -> dict[str, Any]:
    baseline = next((arm for arm in arms if arm.get("role") == "baseline"), None)
    if baseline is None:
        return {
            "decision": "block",
            "candidate_strategy": "",
            "reasons": ["缺少当前生产基线结果，无法进行 A/B 上线决策。"],
            "required_human_review_case_count": 0,
            "completed_human_review_case_count": 0,
        }
    baseline_metrics = _metric_map(baseline)
    required_human_reviews = case_count * len(arms)
    completed_human_reviews = sum(
        1 for arm in arms for item in arm.get("cases", []) if item.get("human_review_score") is not None
    )
    candidates = [arm for arm in arms if arm.get("role") == "candidate"]
    candidate_failures: dict[str, list[str]] = {}
    eligible: list[Mapping[str, Any]] = []
    for candidate in candidates:
        strategy = str(candidate.get("strategy") or "")
        metrics = _metric_map(candidate)
        failures: list[str] = []
        for key, label in (
            ("recall_at_10", "Recall@10"),
            ("ndcg_at_10", "nDCG@10"),
            ("citation_hit_rate", "引用命中率"),
        ):
            value = metrics.get(key)
            baseline_value = baseline_metrics.get(key)
            if value is None or baseline_value is None:
                failures.append(f"{label} 缺少可比结果。")
            elif value < baseline_value - MAX_GUARDRAIL_REGRESSION:
                failures.append(f"{label} 相对基线回退超过 {MAX_GUARDRAIL_REGRESSION:.0%}。")
        latency = metrics.get("latency_ms")
        baseline_latency = baseline_metrics.get("latency_ms")
        if latency is not None and baseline_latency and latency > baseline_latency * MAX_LATENCY_MULTIPLIER:
            failures.append(f"平均延迟超过基线 {MAX_LATENCY_MULTIPLIER:.1f} 倍。")
        human_score = metrics.get("human_review_score")
        baseline_human_score = baseline_metrics.get("human_review_score")
        candidate_reviews = sum(1 for item in candidate.get("cases", []) if item.get("human_review_score") is not None)
        baseline_reviews = sum(1 for item in baseline.get("cases", []) if item.get("human_review_score") is not None)
        if candidate_reviews < case_count or baseline_reviews < case_count:
            failures.append("固定题集的报告人工评分尚未全部完成。")
        elif human_score is None or human_score < MIN_HUMAN_REVIEW_SCORE:
            failures.append(f"报告人工评分未达到 {MIN_HUMAN_REVIEW_SCORE:.1f}/5。")
        elif baseline_human_score is not None and human_score < baseline_human_score:
            failures.append("报告人工评分低于当前基线。")
        if strategy == "prefilter_weighted_rerank":
            if int(candidate.get("rerank_applied_case_count") or 0) < case_count:
                failures.append("未在全部固定题目上取得真实 Cross Encoder 复排证据。")
            if "sentence-transformers" not in normalize_text(str(candidate.get("rerank_backend") or "")).lower():
                failures.append("Cross Encoder 后端不是 sentence-transformers，不能作为真实复排上线证据。")
            if not normalize_text(str(candidate.get("rerank_model") or "")):
                failures.append("未记录实际 Cross Encoder 模型名，不能作为真实复排上线证据。")
        retrieval_uplift = max(
            [
                (metrics.get(key) or 0.0) - (baseline_metrics.get(key) or 0.0)
                for key in ("recall_at_10", "ndcg_at_10", "citation_hit_rate")
            ]
        )
        human_uplift = (human_score or 0.0) - (baseline_human_score or 0.0)
        if retrieval_uplift < MIN_MEANINGFUL_UPLIFT and human_uplift < 0.1:
            failures.append("未取得足以替换生产默认策略的明确质量提升。")
        if failures:
            candidate_failures[strategy] = failures
        else:
            eligible.append(candidate)

    if eligible:
        def quality_score(arm: Mapping[str, Any]) -> tuple[float, float]:
            metrics = _metric_map(arm)
            retrieval_score = (
                float(metrics.get("ndcg_at_10") or 0.0) * 0.5
                + float(metrics.get("recall_at_10") or 0.0) * 0.3
                + float(metrics.get("citation_hit_rate") or 0.0) * 0.2
            )
            # Every candidate has already met the retrieval guardrails. The
            # complete-report review therefore selects the user-visible
            # outcome; retrieval quality resolves a human-score tie.
            return float(metrics.get("human_review_score") or 0.0), retrieval_score

        selected = max(eligible, key=quality_score)
        return {
            "decision": "promote",
            "candidate_strategy": str(selected.get("strategy") or ""),
            "reasons": ["候选策略通过固定题集、人工评分、延迟与真实复排（如适用）门禁，并以完整研报人工评分优先选择。"],
            "required_human_review_case_count": required_human_reviews,
            "completed_human_review_case_count": completed_human_reviews,
        }

    reasons = [
        f"{strategy}：{reason}"
        for strategy, failures in candidate_failures.items()
        for reason in failures
    ]
    return {
        "decision": "hold",
        "candidate_strategy": "",
        "reasons": reasons or ["尚无满足生产上线门槛的候选策略。"],
        "required_human_review_case_count": required_human_reviews,
        "completed_human_review_case_count": completed_human_reviews,
    }


def _review_template(
    *,
    dataset_payload: Mapping[str, Any],
    dataset_sha256: str,
    case_list: Sequence[RetrievalBenchmarkCase],
    arms: Sequence[Mapping[str, Any]],
    knowledge_base_generation_id: str,
    benchmark_digest: str,
    review_sample_paths: Mapping[tuple[str, str], str],
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for arm in arms:
        case_results = {str(item.get("case_id") or ""): item for item in arm.get("cases", [])}
        for case in case_list:
            result = case_results.get(case.case_id, {})
            entries.append(
                {
                    "case_id": case.case_id,
                    "strategy": str(arm.get("strategy") or ""),
                    "query": case.query,
                    "retrieved_document_ids": list(result.get("result_document_ids") or []),
                    "review_sample_path": review_sample_paths.get((case.case_id, str(arm.get("strategy") or "")), ""),
                    "report_artifact_path": "",
                    "human_review_score": None,
                    "review_note": "",
                }
            )
    return {
        "benchmark_id": BENCHMARK_ID,
        "dataset_version": str(dataset_payload.get("version") or ""),
        "dataset_sha256": dataset_sha256,
        "knowledge_base_generation_id": knowledge_base_generation_id,
        "benchmark_digest": benchmark_digest,
        "review_protocol_version": REVIEW_PROTOCOL_VERSION,
        "review_status": "pending",
        "reviewer_name": "",
        "reviewer_role": "",
        "reviewed_at": "",
        "attestation": "",
        "independence_attestation": "",
        "conflict_disclosure": "",
        "instructions": [
            "先查看 review_sample_path 的固定证据审阅样本；再对每个固定题目和策略使用同一输入条件生成完整研报，并在 report_artifact_path 记录报告文件或任务 ID。",
            "human_review_score 按 1-5 分评价事实支撑、引用可用性、方案可执行性与结构完整性；未实际查看完整研报不得填分。",
            "缺少 report_artifact_path 的评分将被系统排除，不能用于替换生产默认策略。",
            "全部条目完成后，将 review_status 改为 complete，并填写评审人、角色、时间、独立复核声明、独立性声明和利益冲突披露。",
            "benchmark_digest 必须保持不变；固定检索结果或知识库快照变化时，已有评分不能复用。",
        ],
        "entries": entries,
    }


def _review_sample_markdown(
    *,
    case: RetrievalBenchmarkCase,
    arm: Mapping[str, Any],
    result: Mapping[str, Any],
) -> str:
    """Build a traceable evidence brief; it is not a substitute for the full report."""
    references: list[str] = []
    for position, hit in enumerate(result.get("retrieved_references") or [], start=1):
        if not isinstance(hit, Mapping):
            continue
        title = normalize_text(str(hit.get("title") or "未命名资料"))
        locator = normalize_text(str(hit.get("locator") or "定位待确认"))
        document_id = normalize_text(str(hit.get("document_id") or ""))
        snippet = normalize_text(str(hit.get("snippet") or ""))
        match_modes = ", ".join(_normalized_strings(hit.get("match_modes"))) or "未标注"
        references.extend(
            [
                f"### {position}. {title}",
                f"- 文档：`{document_id}`",
                f"- 定位：{locator}",
                f"- 命中方式：{match_modes}",
                f"- 摘要：{snippet or '未返回可展示摘要。'}",
                "",
            ]
        )
    metrics = {
        "Recall@10": result.get("recall_at_10"),
        "nDCG@10": result.get("ndcg_at_10"),
        "引用命中率": result.get("citation_hit_rate"),
    }
    metric_text = "\n".join(f"- {label}：{float(value or 0) * 100:.1f}%" for label, value in metrics.items())
    return "\n".join(
        [
            "# 检索排序固定证据审阅样本",
            "",
            "> 此文件只展示本地资料检索对报告证据的影响，不能替代待人工评分的完整研报。",
            "",
            f"- 题目：{case.case_id}",
            f"- 查询：{case.query}",
            f"- 策略：{arm.get('label') or arm.get('strategy')}",
            f"- 策略标识：`{arm.get('strategy') or ''}`",
            f"- 行业范围：{', '.join(case.industries) or '未限定'}",
            f"- 文件类型：{', '.join(case.document_types) or '未限定'}",
            f"- 预期引用词：{', '.join(case.expected_citation_terms)}",
            "",
            "## 检索指标",
            metric_text,
            "",
            "## 可追溯资料片段",
            *(references or ["未检索到可展示资料片段。", ""]),
            "## 人工复核要求",
            "- 使用与本策略对应的完整研报，在人工评分模板中填写真实 report_artifact_path。",
            "- 核验报告中的结论是否能被上方资料片段支撑，以及是否错误引入跨行业材料。",
            "- 只对实际查看过的完整研报填写 1-5 分和复核说明。",
            "",
        ]
    )


def _write_review_samples(
    *,
    sample_dir: Path,
    case_list: Sequence[RetrievalBenchmarkCase],
    arms: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], str]:
    paths: dict[tuple[str, str], str] = {}
    for arm in arms:
        strategy = normalize_text(str(arm.get("strategy") or ""))
        case_results = {
            str(item.get("case_id") or ""): item
            for item in arm.get("cases", [])
            if isinstance(item, Mapping)
        }
        for case in case_list:
            result = case_results.get(case.case_id, {})
            path = sample_dir / strategy / f"{case.case_id}.md"
            _write_text(path, _review_sample_markdown(case=case, arm=arm, result=result))
            paths[(case.case_id, strategy)] = industry_knowledge_benchmark_artifact_reference(path)
    return paths


def _refresh_pending_review_template(path: Path, expected: Mapping[str, Any]) -> None:
    """Refresh machine fields while preserving any in-progress human review work."""
    if not path.is_file():
        _write_json(path, expected)
        return
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _write_json(path, expected)
        return
    if not isinstance(existing, dict) or existing.get("dataset_sha256") != expected.get("dataset_sha256"):
        _write_json(path, expected)
        return
    if normalize_text(str(existing.get("review_status") or "")).lower() == "complete":
        return
    if existing.get("benchmark_digest") != expected.get("benchmark_digest"):
        _write_json(path, expected)
        return
    existing_entries = {
        (normalize_text(str(entry.get("case_id") or "")), normalize_text(str(entry.get("strategy") or ""))): entry
        for entry in existing.get("entries", [])
        if isinstance(entry, dict)
    }
    refreshed = dict(expected)
    for key in (
        "review_protocol_version",
        "review_status",
        "reviewer_name",
        "reviewer_role",
        "reviewed_at",
        "attestation",
        "independence_attestation",
        "conflict_disclosure",
    ):
        refreshed[key] = existing.get(key, refreshed[key])
    refreshed_entries: list[dict[str, Any]] = []
    for entry in expected.get("entries", []):
        if not isinstance(entry, dict):
            continue
        previous = existing_entries.get((str(entry.get("case_id") or ""), str(entry.get("strategy") or "")), {})
        refreshed_entry = dict(entry)
        for key in ("report_artifact_path", "human_review_score", "review_note"):
            if key in previous:
                refreshed_entry[key] = previous[key]
        refreshed_entries.append(refreshed_entry)
    refreshed["entries"] = refreshed_entries
    _write_json(path, refreshed)


def register_industry_knowledge_delivery_review_artifacts(
    *,
    case_id: str,
    artifact_paths: Mapping[str, str],
    review_path: str | Path = DEFAULT_REVIEW_PATH,
    benchmark_artifact_path: str | Path = DEFAULT_ARTIFACT_PATH,
) -> list[str]:
    """Attach server-generated delivery review artifacts without fabricating scores."""
    path = Path(review_path)
    if not path.is_file():
        return ["人工评分模板尚未生成，未回写报告评审工件路径。"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["人工评分模板不可读取，未回写报告评审工件路径。"]
    if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
        return ["人工评分模板格式无效，未回写报告评审工件路径。"]
    if normalize_text(str(payload.get("review_status") or "")).lower() == "complete":
        return ["人工评分已完成；为保留已签署证据，未覆盖既有 report_artifact_path。"]
    normalized_case_id = normalize_text(case_id)
    updated = 0
    for entry in payload["entries"]:
        if not isinstance(entry, dict) or normalize_text(str(entry.get("case_id") or "")) != normalized_case_id:
            continue
        strategy = normalize_text(str(entry.get("strategy") or ""))
        delivery_artifact_path = normalize_text(str(artifact_paths.get(strategy) or ""))
        if delivery_artifact_path and entry.get("report_artifact_path") != delivery_artifact_path:
            entry["report_artifact_path"] = delivery_artifact_path
            updated += 1
    if updated:
        _write_json(path, payload)
        # No metric or score changed, so retain the cached A/B result rather
        # than making an ordinary Research Center refresh re-run 36 queries.
        persisted_benchmark = Path(benchmark_artifact_path)
        if persisted_benchmark.is_file():
            persisted_benchmark.touch()
    return [] if updated else ["未找到可回写的固定题目或策略工件路径。"]


def _base_payload(
    *,
    knowledge_base: Mapping[str, Any],
    dataset_payload: Mapping[str, Any],
    dataset_sha256: str,
    artifact_path: Path,
    review_path: Path,
    review_sample_dir: Path,
) -> dict[str, Any]:
    status = str(knowledge_base.get("status") or "unavailable")
    return {
        "benchmark_id": BENCHMARK_ID,
        "dataset_version": str(dataset_payload.get("version") or ""),
        "dataset_sha256": dataset_sha256,
        "generated_at": _utc_now(),
        "knowledge_base_generated_at": knowledge_base.get("generated_at"),
        "knowledge_base_generation_id": str(knowledge_base.get("generation_id") or ""),
        "status": status if status in {"ready", "partial"} else "unavailable",
        "case_count": 0,
        "strategies": industry_knowledge_retrieval_strategy_catalog(),
        "arms": [],
        "promotion": {
            "decision": "hold",
            "candidate_strategy": "",
            "reasons": [],
            "required_human_review_case_count": 0,
            "completed_human_review_case_count": 0,
        },
        "artifact_path": industry_knowledge_benchmark_artifact_reference(artifact_path),
        "review_template_path": industry_knowledge_benchmark_artifact_reference(review_path),
        "review_artifact_path": industry_knowledge_benchmark_artifact_reference(review_path) if review_path.is_file() else "",
        "review_sample_directory": industry_knowledge_benchmark_artifact_reference(review_sample_dir),
        "warnings": [],
    }


def run_industry_knowledge_retrieval_benchmark(
    *,
    library_dir: str | Path | None = None,
    dataset_path: str | Path = DATASET_PATH,
    artifact_path: str | Path = DEFAULT_ARTIFACT_PATH,
    review_path: str | Path = DEFAULT_REVIEW_PATH,
    review_sample_dir: str | Path = DEFAULT_REVIEW_SAMPLE_DIR,
    persist: bool = True,
) -> dict[str, Any]:
    resolved_library_dir = resolve_library_dir(library_dir)
    resolved_dataset_path = Path(dataset_path)
    resolved_artifact_path = Path(artifact_path)
    resolved_review_path = Path(review_path)
    resolved_review_sample_dir = Path(review_sample_dir)
    try:
        dataset_payload, case_list = load_industry_knowledge_retrieval_benchmark_dataset(resolved_dataset_path)
        dataset_sha256 = _dataset_digest(resolved_dataset_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "benchmark_id": BENCHMARK_ID,
            "dataset_version": "",
            "dataset_sha256": "",
            "generated_at": _utc_now(),
            "knowledge_base_generated_at": None,
            "knowledge_base_generation_id": "",
            "status": "unavailable",
            "case_count": 0,
            "strategies": industry_knowledge_retrieval_strategy_catalog(),
            "arms": [],
            "promotion": {
                "decision": "block",
                "candidate_strategy": "",
                "reasons": ["固定评测集不可用，不能形成上线决策。"],
                "required_human_review_case_count": 0,
                "completed_human_review_case_count": 0,
            },
            "artifact_path": industry_knowledge_benchmark_artifact_reference(resolved_artifact_path),
            "review_template_path": industry_knowledge_benchmark_artifact_reference(resolved_review_path),
            "review_artifact_path": "",
            "review_sample_directory": industry_knowledge_benchmark_artifact_reference(resolved_review_sample_dir),
            "warnings": [f"固定评测集读取失败：{type(exc).__name__}。"],
        }

    knowledge_base = knowledge_base_public_status(resolved_library_dir)
    manifest = load_knowledge_base_manifest(resolved_library_dir) or {}
    knowledge_base = {
        **knowledge_base,
        "generation_id": str(manifest.get("generation_id") or ""),
        "generated_at": manifest.get("generated_at") or knowledge_base.get("generated_at"),
    }
    payload = _base_payload(
        knowledge_base=knowledge_base,
        dataset_payload=dataset_payload,
        dataset_sha256=dataset_sha256,
        artifact_path=resolved_artifact_path,
        review_path=resolved_review_path,
        review_sample_dir=resolved_review_sample_dir,
    )
    if payload["status"] == "unavailable":
        payload["promotion"] = {
            "decision": "block",
            "candidate_strategy": "",
            "reasons": ["本地行业知识库不可用，无法运行检索排序 A/B。"],
            "required_human_review_case_count": 0,
            "completed_human_review_case_count": 0,
        }
        payload["warnings"] = [*knowledge_base.get("warnings", []), "请先完成本地行业资料库构建。"]
        return payload

    # Model construction is a one-off process cost, not a per-query retrieval
    # latency. Each arm gets the same unmeasured warm-up so the first observed
    # strategy does not pay for vector/FTS/reranker initialization.
    review_warnings: list[str] = []
    warmup_case = case_list[0]
    for strategy in STRATEGY_KEYS:
        try:
            hybrid_search_industry_knowledge(
                resolved_library_dir,
                query=warmup_case.query,
                industries=warmup_case.industries,
                document_types=warmup_case.document_types,
                limit=RETRIEVAL_LIMIT,
                strategy=strategy,
            )
        except Exception as exc:
            review_warnings.append(
                f"{strategy} 检索冷启动预热失败：{type(exc).__name__}；该策略延迟指标可能包含初始化开销。"
            )
    arms: list[dict[str, Any]] = []
    baseline_metrics: dict[str, float | None] | None = None
    for strategy in STRATEGY_KEYS:
        arm = _evaluate_arm(
            case_list,
            library_dir=resolved_library_dir,
            strategy=strategy,
            human_scores={},
        )
        arm = _with_metrics(arm, baseline_metrics=baseline_metrics)
        if strategy == DEFAULT_INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGY:
            baseline_metrics = _metric_map(arm)
        arms.append(arm)
    payload["case_count"] = len(case_list)
    payload["arms"] = arms
    payload["benchmark_digest"] = industry_knowledge_retrieval_benchmark_digest(payload)
    human_scores, loaded_review_warnings = _load_human_review_scores(
        resolved_review_path,
        dataset_sha256=dataset_sha256,
        benchmark_digest=str(payload["benchmark_digest"]),
    )
    review_warnings.extend(loaded_review_warnings)
    if human_scores:
        # Scores are accepted only after the digest above binds them to this
        # exact result set. Recompute metrics from the same retrieval evidence;
        # a second retrieval pass could otherwise change the A/B comparison.
        arms = _apply_human_scores(arms, human_scores)
        payload["arms"] = arms
        refreshed_digest = industry_knowledge_retrieval_benchmark_digest(payload)
        if refreshed_digest != payload["benchmark_digest"]:
            raise RuntimeError("人工评分回填意外改变了固定检索证据摘要。")
    payload["promotion"] = _promotion_decision(arms, case_count=len(case_list))
    rerank_arm = next((arm for arm in arms if arm.get("strategy") == "prefilter_weighted_rerank"), None)
    rerank_unavailable = bool(
        rerank_arm
        and int(rerank_arm.get("rerank_applied_case_count") or 0) < len(case_list)
    )
    if rerank_unavailable:
        payload["status"] = "partial"
    payload["warnings"] = [*knowledge_base.get("warnings", []), *review_warnings]
    if rerank_unavailable:
        payload["warnings"].append("候选 B 未取得真实 Cross Encoder 复排证据，当前不能替换生产默认策略。")
    if persist:
        review_sample_paths = _write_review_samples(
            sample_dir=resolved_review_sample_dir,
            case_list=case_list,
            arms=arms,
        )
        _refresh_pending_review_template(
            resolved_review_path,
            _review_template(
                dataset_payload=dataset_payload,
                dataset_sha256=dataset_sha256,
                case_list=case_list,
                arms=arms,
                knowledge_base_generation_id=str(payload["knowledge_base_generation_id"]),
                benchmark_digest=str(payload["benchmark_digest"]),
                review_sample_paths=review_sample_paths,
            )
        )
        payload["review_artifact_path"] = (
            industry_knowledge_benchmark_artifact_reference(resolved_review_path)
            if resolved_review_path.is_file()
            else ""
        )
        _write_json(resolved_artifact_path, payload)
    return payload


def _overlay_bound_review_scores(
    payload: Mapping[str, Any],
    *,
    review_path: Path,
) -> dict[str, Any] | None:
    """Refresh review-derived metrics from a persisted fixed retrieval snapshot.

    This is deliberately side-effect free: a GET can reflect a newly completed
    human review without re-running retrieval or modifying the benchmark file.
    """
    result = dict(payload)
    if not isinstance(result.get("arms"), list):
        return None
    current_digest = industry_knowledge_retrieval_benchmark_digest(result)
    recorded_digest = normalize_text(str(result.get("benchmark_digest") or ""))
    if recorded_digest and recorded_digest != current_digest:
        return None
    result["benchmark_digest"] = current_digest
    dataset_sha256 = normalize_text(str(result.get("dataset_sha256") or ""))
    if not dataset_sha256:
        return None
    scores, review_warnings = _load_human_review_scores(
        review_path,
        dataset_sha256=dataset_sha256,
        benchmark_digest=current_digest,
    )
    if scores:
        result["arms"] = _apply_human_scores(result["arms"], scores)
        result["promotion"] = _promotion_decision(
            result["arms"],
            case_count=int(result.get("case_count") or 0),
        )
    retained_warnings = [
        warning
        for warning in result.get("warnings") or []
        if isinstance(warning, str)
        and "人工评分" not in warning
        and "完整报告工件" not in warning
    ]
    result["warnings"] = [*retained_warnings, *review_warnings]
    result["review_artifact_path"] = (
        industry_knowledge_benchmark_artifact_reference(review_path) if review_path.is_file() else ""
    )
    return result


def load_latest_industry_knowledge_retrieval_benchmark(
    *,
    library_dir: str | Path | None = None,
    dataset_path: str | Path = DATASET_PATH,
    artifact_path: str | Path = DEFAULT_ARTIFACT_PATH,
    review_path: str | Path = DEFAULT_REVIEW_PATH,
) -> dict[str, Any]:
    """Return a matching persisted run without making a page load run 36 queries."""
    resolved_library_dir = resolve_library_dir(library_dir)
    resolved_dataset_path = Path(dataset_path)
    resolved_artifact_path = Path(artifact_path)
    resolved_review_path = Path(review_path)
    try:
        expected_digest = _dataset_digest(resolved_dataset_path)
        manifest = load_knowledge_base_manifest(resolved_library_dir) or {}
        if resolved_artifact_path.is_file():
            payload = json.loads(resolved_artifact_path.read_text(encoding="utf-8"))
            persisted_digest = industry_knowledge_retrieval_benchmark_digest(payload) if isinstance(payload, dict) else ""
            if (
                isinstance(payload, dict)
                and payload.get("dataset_sha256") == expected_digest
                and payload.get("knowledge_base_generation_id") == str(manifest.get("generation_id") or "")
                and normalize_text(str(payload.get("benchmark_digest") or "")) == persisted_digest
            ):
                if (
                    not resolved_review_path.is_file()
                    or resolved_review_path.stat().st_mtime <= resolved_artifact_path.stat().st_mtime
                ):
                    return payload
                overlay = _overlay_bound_review_scores(payload, review_path=resolved_review_path)
                if overlay is not None:
                    return overlay
    except (OSError, json.JSONDecodeError):
        pass
    payload = run_industry_knowledge_retrieval_benchmark(
        library_dir=resolved_library_dir,
        dataset_path=resolved_dataset_path,
        artifact_path=resolved_artifact_path,
        review_path=resolved_review_path,
        persist=False,
    )
    payload["warnings"] = [
        "尚无与当前知识库版本匹配的持久化 A/B 结果；以下为未落盘预览。",
        *payload.get("warnings", []),
    ]
    return payload
