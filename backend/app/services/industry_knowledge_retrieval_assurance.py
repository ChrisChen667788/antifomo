from __future__ import annotations

import hashlib
import json
import math
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.services.content_extractor import normalize_text
from app.services.industry_knowledge_rag import (
    DEFAULT_INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGY,
    INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGIES,
    industry_knowledge_retrieval_strategy_catalog,
)
from app.services.industry_knowledge_retrieval_benchmark import (
    BENCHMARK_ID,
    DEFAULT_ARTIFACT_PATH,
    DEFAULT_REVIEW_PATH,
    REVIEW_PROTOCOL_VERSION,
    STRATEGY_KEYS,
    industry_knowledge_benchmark_artifact_reference,
    industry_knowledge_retrieval_benchmark_digest,
    load_latest_industry_knowledge_retrieval_benchmark,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROGRAM_VERSION = "2.8.0-retrieval-assurance"
APPROVAL_SCHEMA_VERSION = "industry-knowledge-retrieval-approval-v1"
SHADOW_SCHEMA_VERSION = "industry-knowledge-retrieval-shadow-v1"
DRIFT_SCHEMA_VERSION = "industry-knowledge-retrieval-drift-v1"
DEFAULT_APPROVAL_PATH = PROJECT_ROOT / ".tmp" / "industry-knowledge-retrieval-ranking-approval.json"
DEFAULT_SHADOW_PATH = PROJECT_ROOT / ".tmp" / "industry-knowledge-retrieval-ranking-shadow.json"
DEFAULT_DRIFT_PATH = PROJECT_ROOT / ".tmp" / "industry-knowledge-retrieval-ranking-drift.json"
MIN_FIXED_CASES = 12
MIN_SHADOW_SAMPLE_SIZE = 30
BOOTSTRAP_SAMPLES = 2000


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _artifact_reference(path: Path) -> str:
    return industry_knowledge_benchmark_artifact_reference(path)


def _canonical_digest(payload: Mapping[str, Any], *, excluded_keys: Sequence[str] = ()) -> str:
    normalized = {key: value for key, value in payload.items() if key not in set(excluded_keys)}
    encoded = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _benchmark_digest(benchmark: Mapping[str, Any]) -> str:
    """Bind downstream decisions to the exact persisted A/B result payload."""

    return industry_knowledge_retrieval_benchmark_digest(benchmark)


def _normalized(value: object) -> str:
    return normalize_text(str(value or ""))


def _safe_number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _safe_count(value: object) -> int:
    """Return a non-negative integral count without trusting artifact input."""

    number = _safe_number(value)
    if number is None or number < 0 or not number.is_integer():
        return 0
    return int(number)


def _safe_sequence(value: object) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return value
    return ()


def _metric(key: str, label: str, observed: str, target: str, status: str, note: str = "") -> dict[str, str]:
    return {
        "key": key,
        "label": label,
        "observed": observed,
        "target": target,
        "status": status,
        "note": note,
    }


def _evidence(label: str, path: Path, status: str, summary: str) -> dict[str, Any]:
    return {
        "label": label,
        "path": _artifact_reference(path),
        "exists": path.is_file(),
        "status": status,
        "summary": summary,
    }


def _round(
    index: int,
    version: str,
    key: str,
    title: str,
    status: str,
    summary: str,
    metrics: Sequence[dict[str, str]],
    next_actions: Sequence[str] = (),
    evidence: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "index": index,
        "version": version,
        "key": key,
        "title": title,
        "status": status,
        "summary": summary,
        "metrics": list(metrics),
        "next_actions": list(next_actions),
        "evidence": list(evidence),
    }


def _arm_metric(arm: Mapping[str, Any], key: str) -> float | None:
    for metric in _safe_sequence(arm.get("metrics")):
        if isinstance(metric, Mapping) and _normalized(metric.get("key")) == key:
            return _safe_number(metric.get("value"))
    return None


def _arm_by_strategy(payload: Mapping[str, Any], strategy: str) -> dict[str, Any] | None:
    for arm in _safe_sequence(payload.get("arms")):
        if isinstance(arm, Mapping) and _normalized(arm.get("strategy")) == strategy:
            return dict(arm)
    return None


def _case_ids(payload: Mapping[str, Any]) -> set[str]:
    result: set[str] = set()
    for arm in _safe_sequence(payload.get("arms")):
        if not isinstance(arm, Mapping):
            continue
        for case in _safe_sequence(arm.get("cases")):
            if isinstance(case, Mapping) and (case_id := _normalized(case.get("case_id"))):
                result.add(case_id)
    return result


def _benchmark_ready(payload: Mapping[str, Any]) -> bool:
    return (
        _normalized(payload.get("benchmark_id")) == BENCHMARK_ID
        and bool(_normalized(payload.get("dataset_sha256")))
        and bool(_normalized(payload.get("knowledge_base_generation_id")))
        and _normalized(payload.get("status")) in {"ready", "partial"}
        and bool(_safe_sequence(payload.get("arms")))
    )


def _review_summary(review: Mapping[str, Any] | None, benchmark: Mapping[str, Any]) -> dict[str, Any]:
    expected_cases = _case_ids(benchmark)
    expected_pairs = {(case_id, strategy) for case_id in expected_cases for strategy in STRATEGY_KEYS}
    result: dict[str, Any] = {
        "status": "missing",
        "valid_pair_count": 0,
        "expected_pair_count": len(expected_pairs),
        "complete": False,
        "protocol_valid": False,
        "reviewer_valid": False,
        "reviewer_name": "",
        "pairs": {},
        "warnings": [],
    }
    if not review:
        result["warnings"].append("尚未提供固定题集完整研报的独立人工复核工件。")
        return result

    result["status"] = _normalized(review.get("review_status")).lower() or "pending"
    benchmark_matches = (
        _normalized(review.get("benchmark_id")) == BENCHMARK_ID
        and _normalized(review.get("dataset_sha256")) == _normalized(benchmark.get("dataset_sha256"))
        and _normalized(review.get("knowledge_base_generation_id")) == _normalized(benchmark.get("knowledge_base_generation_id"))
        and _normalized(review.get("benchmark_digest")) == _benchmark_digest(benchmark)
    )
    protocol_valid = _normalized(review.get("review_protocol_version")) == REVIEW_PROTOCOL_VERSION
    reviewer_name = _normalized(review.get("reviewer_name"))
    reviewer_valid = all(
        _normalized(review.get(key))
        for key in (
            "reviewer_name",
            "reviewer_role",
            "reviewed_at",
            "attestation",
            "independence_attestation",
            "conflict_disclosure",
        )
    )
    result["protocol_valid"] = protocol_valid
    result["reviewer_valid"] = reviewer_valid
    result["reviewer_name"] = reviewer_name
    if not benchmark_matches:
        result["warnings"].append("人工复核工件未绑定当前固定题集、知识库快照或检索结果摘要。")
    if not protocol_valid:
        result["warnings"].append(f"人工复核工件缺少 {REVIEW_PROTOCOL_VERSION} 协议声明。")
    if not reviewer_valid:
        result["warnings"].append("人工复核工件缺少身份、独立性或利益冲突声明。")

    pairs: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in _safe_sequence(review.get("entries")):
        if not isinstance(entry, Mapping):
            continue
        case_id = _normalized(entry.get("case_id"))
        strategy = _normalized(entry.get("strategy"))
        score = _safe_number(entry.get("human_review_score"))
        artifact_path = _normalized(entry.get("report_artifact_path"))
        if (
            case_id in expected_cases
            and strategy in STRATEGY_KEYS
            and score is not None
            and 1 <= score <= 5
            and artifact_path
        ):
            pairs[(case_id, strategy)] = {
                "score": round(score, 3),
                "report_artifact_path": artifact_path,
                "review_note": _normalized(entry.get("review_note")),
            }
    result["pairs"] = pairs
    result["valid_pair_count"] = len(pairs)
    result["complete"] = (
        result["status"] == "complete"
        and benchmark_matches
        and protocol_valid
        and reviewer_valid
        and set(pairs) == expected_pairs
    )
    return result


def _paired_score_summary(
    review_summary: Mapping[str, Any],
    *,
    baseline_strategy: str,
) -> dict[str, dict[str, Any]]:
    pairs = review_summary.get("pairs") if isinstance(review_summary.get("pairs"), Mapping) else {}
    expected_cases = sorted({case_id for case_id, _strategy in pairs})
    result: dict[str, dict[str, Any]] = {}
    for strategy in STRATEGY_KEYS:
        if strategy == baseline_strategy:
            continue
        deltas: list[float] = []
        for case_id in expected_cases:
            baseline = pairs.get((case_id, baseline_strategy))
            candidate = pairs.get((case_id, strategy))
            if not isinstance(baseline, Mapping) or not isinstance(candidate, Mapping):
                continue
            baseline_score = _safe_number(baseline.get("score"))
            candidate_score = _safe_number(candidate.get("score"))
            if baseline_score is not None and candidate_score is not None:
                deltas.append(round(candidate_score - baseline_score, 4))
        result[strategy] = {
            "paired_case_count": len(deltas),
            "mean_delta": round(sum(deltas) / len(deltas), 4) if deltas else None,
            "ci_lower": None,
            "ci_upper": None,
        }
        if deltas:
            seed = int(hashlib.sha256(f"{baseline_strategy}|{strategy}|{','.join(map(str, deltas))}".encode("utf-8")).hexdigest()[:16], 16)
            generator = random.Random(seed)
            means = sorted(
                sum(generator.choice(deltas) for _ in deltas) / len(deltas)
                for _ in range(BOOTSTRAP_SAMPLES)
            )
            result[strategy]["ci_lower"] = round(means[int((len(means) - 1) * 0.025)], 4)
            result[strategy]["ci_upper"] = round(means[int((len(means) - 1) * 0.975)], 4)
    return result


def _artifact_binding_valid(
    payload: Mapping[str, Any] | None,
    benchmark: Mapping[str, Any],
    *,
    schema_version: str,
    require_decision: str | None = None,
) -> tuple[bool, list[str]]:
    if not payload:
        return False, ["工件不存在或不可读取。"]
    issues: list[str] = []
    if _normalized(payload.get("schema_version")) != schema_version:
        issues.append("schema_version 不匹配。")
    if _normalized(payload.get("benchmark_id")) != BENCHMARK_ID:
        issues.append("benchmark_id 不匹配。")
    if _normalized(payload.get("dataset_sha256")) != _normalized(benchmark.get("dataset_sha256")):
        issues.append("dataset_sha256 不匹配。")
    if _normalized(payload.get("knowledge_base_generation_id")) != _normalized(benchmark.get("knowledge_base_generation_id")):
        issues.append("knowledge_base_generation_id 不匹配。")
    if _normalized(payload.get("benchmark_digest")) != _benchmark_digest(benchmark):
        issues.append("benchmark_digest 不匹配。")
    if require_decision and _normalized(payload.get("decision")).lower() != require_decision:
        issues.append(f"decision 必须为 {require_decision}。")
    return not issues, issues


def _approval_summary(
    approval: Mapping[str, Any] | None,
    benchmark: Mapping[str, Any],
    promotion: Mapping[str, Any],
    *,
    reviewer_name: str,
    review_complete: bool,
) -> dict[str, Any]:
    valid_binding, issues = _artifact_binding_valid(
        approval,
        benchmark,
        schema_version=APPROVAL_SCHEMA_VERSION,
        require_decision="approved",
    )
    approver_valid = bool(approval) and all(
        _normalized(approval.get(key))  # type: ignore[union-attr]
        for key in ("approved_by", "approver_role", "approved_at", "attestation", "separation_attestation")
    )
    candidate_strategy = _normalized(promotion.get("candidate_strategy"))
    strategy_matches = bool(approval) and _normalized(approval.get("candidate_strategy")) == candidate_strategy  # type: ignore[union-attr]
    approver_name = _normalized(approval.get("approved_by")) if approval else ""
    separation_valid = bool(reviewer_name) and bool(approver_name) and reviewer_name.casefold() != approver_name.casefold()
    if not approver_valid:
        issues.append("批准工件缺少批准人、角色、时间、批准声明或职责分离声明。")
    if not reviewer_name:
        issues.append("完整研报复核工件未提供可验证的复核人，无法确认职责分离。")
    elif approver_name and not separation_valid:
        issues.append("批准人与完整研报复核人为同一人，不满足职责分离。")
    if not review_complete:
        issues.append("完整研报独立复核尚未完整通过，不能进入候选批准流程。")
    if not candidate_strategy or not strategy_matches:
        issues.append("批准策略未与当前评测候选策略一致。")
    if _normalized(promotion.get("decision")).lower() != "promote":
        issues.append("当前固定题集评测尚未给出 promote 候选，不能进入批准流程。")
    digest = _canonical_digest(approval or {}) if approval else ""
    return {
        "valid": (
            valid_binding
            and approver_valid
            and strategy_matches
            and separation_valid
            and review_complete
            and _normalized(promotion.get("decision")).lower() == "promote"
        ),
        "issues": issues,
        "digest": digest,
    }


def _shadow_summary(
    shadow: Mapping[str, Any] | None,
    benchmark: Mapping[str, Any],
    *,
    approval_valid: bool,
    approval_digest: str,
    candidate_strategy: str,
) -> dict[str, Any]:
    valid_binding, issues = _artifact_binding_valid(shadow, benchmark, schema_version=SHADOW_SCHEMA_VERSION)
    sample_count = _safe_count(shadow.get("sample_count")) if shadow else 0
    fallback_count = _safe_count(shadow.get("fallback_count")) if shadow else 0
    regression_count = _safe_count(shadow.get("quality_regression_count")) if shadow else 0
    if not shadow or _normalized(shadow.get("candidate_strategy")) != candidate_strategy:
        issues.append("影子运行候选策略未与批准策略一致。")
    if not shadow or _normalized(shadow.get("approval_digest")) != approval_digest:
        issues.append("影子运行未绑定当前批准工件摘要。")
    if not approval_valid:
        issues.append("当前候选尚未取得有效且职责分离的人工批准，影子运行不能计为通过。")
    if not shadow or _normalized(shadow.get("status")).lower() != "complete":
        issues.append("影子运行尚未标记 complete。")
    if not shadow or not all(_normalized(shadow.get(key)) for key in ("executed_by", "executed_at", "attestation")):
        issues.append("影子运行缺少执行人、执行时间或真实运行声明。")
    if sample_count < MIN_SHADOW_SAMPLE_SIZE:
        issues.append(f"影子运行样本少于 {MIN_SHADOW_SAMPLE_SIZE}。")
    if fallback_count or regression_count:
        issues.append("影子运行出现 fallback 或质量回退。")
    return {
        "valid": valid_binding and not issues,
        "issues": issues,
        "sample_count": sample_count,
        "fallback_count": fallback_count,
        "regression_count": regression_count,
    }


def _drift_summary(
    drift: Mapping[str, Any] | None,
    benchmark: Mapping[str, Any],
    *,
    approval_valid: bool,
    approval_digest: str,
    candidate_strategy: str,
) -> dict[str, Any]:
    valid_binding, issues = _artifact_binding_valid(drift, benchmark, schema_version=DRIFT_SCHEMA_VERSION)
    checked_case_count = _safe_count(drift.get("checked_case_count")) if drift else 0
    regression_count = _safe_count(drift.get("regression_count")) if drift else 0
    if not drift or _normalized(drift.get("candidate_strategy")) != candidate_strategy:
        issues.append("漂移工件候选策略未与批准策略一致。")
    if not drift or _normalized(drift.get("approval_digest")) != approval_digest:
        issues.append("漂移工件未绑定当前批准工件摘要。")
    if not approval_valid:
        issues.append("当前候选尚未取得有效且职责分离的人工批准，漂移检查不能计为通过。")
    if not drift or _normalized(drift.get("status")).lower() != "complete":
        issues.append("漂移检查尚未标记 complete。")
    if not drift or not all(_normalized(drift.get(key)) for key in ("executed_by", "executed_at", "attestation")):
        issues.append("漂移检查缺少执行人、执行时间或真实检查声明。")
    if checked_case_count < MIN_FIXED_CASES:
        issues.append(f"漂移检查覆盖少于 {MIN_FIXED_CASES} 个固定题目。")
    if regression_count:
        issues.append("漂移检查存在质量回退。")
    return {
        "valid": valid_binding and not issues,
        "issues": issues,
        "checked_case_count": checked_case_count,
        "regression_count": regression_count,
    }


def _round_status_score(status: str) -> int:
    return {"pass": 100, "watch": 55, "blocked": 0}.get(status, 0)


def _benchmark_payload_or_latest(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(payload) if payload is not None else load_latest_industry_knowledge_retrieval_benchmark()


def _persisted_snapshot_matches(path: Path, benchmark: Mapping[str, Any]) -> bool:
    """Require the on-disk benchmark artifact to match the current fixed evidence."""
    persisted = _read_json(path)
    if not persisted:
        return False
    persisted_digest = _benchmark_digest(persisted)
    return (
        persisted_digest == _benchmark_digest(benchmark)
        and _normalized(persisted.get("benchmark_digest")) == persisted_digest
    )


def build_industry_knowledge_retrieval_assurance_snapshot(
    *,
    benchmark_payload: Mapping[str, Any] | None = None,
    benchmark_artifact_path: str | Path = DEFAULT_ARTIFACT_PATH,
    review_path: str | Path = DEFAULT_REVIEW_PATH,
    approval_path: str | Path = DEFAULT_APPROVAL_PATH,
    shadow_path: str | Path = DEFAULT_SHADOW_PATH,
    drift_path: str | Path = DEFAULT_DRIFT_PATH,
) -> dict[str, Any]:
    """Build the 15-round retrieval assurance program without changing production routing.

    The service intentionally consumes only deterministic benchmark output and
    human-authored artifacts. It never manufactures scores, approvals, shadow
    samples, or drift evidence, and the production default remains the baseline
    until every required external proof is valid.
    """

    benchmark = _benchmark_payload_or_latest(benchmark_payload)
    benchmark_path = Path(benchmark_artifact_path)
    review_file = Path(review_path)
    approval_file = Path(approval_path)
    shadow_file = Path(shadow_path)
    drift_file = Path(drift_path)
    review = _read_json(review_file)
    approval = _read_json(approval_file)
    shadow = _read_json(shadow_file)
    drift = _read_json(drift_file)
    benchmark_ready = _benchmark_ready(benchmark)
    case_count = _safe_count(benchmark.get("case_count"))
    arms = [dict(arm) for arm in _safe_sequence(benchmark.get("arms")) if isinstance(arm, Mapping)]
    baseline_strategy = DEFAULT_INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGY
    baseline = _arm_by_strategy(benchmark, baseline_strategy)
    promotion = benchmark.get("promotion") if isinstance(benchmark.get("promotion"), Mapping) else {}
    promotion_decision = _normalized(promotion.get("decision")).lower() or "hold"
    candidate_strategy = _normalized(promotion.get("candidate_strategy"))
    review_state = _review_summary(review, benchmark)
    paired_scores = _paired_score_summary(review_state, baseline_strategy=baseline_strategy)
    approval_state = _approval_summary(
        approval,
        benchmark,
        promotion,
        reviewer_name=str(review_state.get("reviewer_name") or ""),
        review_complete=bool(review_state["complete"]),
    )
    shadow_state = _shadow_summary(
        shadow,
        benchmark,
        approval_valid=bool(approval_state["valid"]),
        approval_digest=approval_state["digest"],
        candidate_strategy=candidate_strategy,
    )
    drift_state = _drift_summary(
        drift,
        benchmark,
        approval_valid=bool(approval_state["valid"]),
        approval_digest=approval_state["digest"],
        candidate_strategy=candidate_strategy,
    )
    snapshot_bound = benchmark_ready and _persisted_snapshot_matches(benchmark_path, benchmark)
    artifact_evidence = [
        _evidence(
            "检索排序评测结果",
            benchmark_path,
            "pass" if snapshot_bound else "watch",
            "固定题集、知识库 generation、检索结果摘要与持久化策略指标必须一致。",
        ),
        _evidence(
            "完整研报人工复核",
            review_file,
            "pass" if review_state["complete"] else "blocked",
            "必须包含独立性、冲突声明、完整报告路径和每题每策略评分。",
        ),
        _evidence(
            "候选策略批准",
            approval_file,
            "pass" if approval_state["valid"] else "blocked",
            "人工批准不能由模型或代码自动生成。",
        ),
        _evidence(
            "影子运行记录",
            shadow_file,
            "pass" if shadow_state["valid"] else "blocked",
            "真实影子样本必须绑定批准摘要并记录 fallback/回退。",
        ),
        _evidence(
            "漂移检查记录",
            drift_file,
            "pass" if drift_state["valid"] else "blocked",
            "固定题集漂移检查必须绑定批准摘要。",
        ),
    ]

    rerank_arm = _arm_by_strategy(benchmark, "prefilter_weighted_rerank") or {}
    rerank_applied_case_count = _safe_count(rerank_arm.get("rerank_applied_case_count"))
    rerank_backend = _normalized(rerank_arm.get("rerank_backend")) or "不可用"
    rerank_model = _normalized(rerank_arm.get("rerank_model"))
    rerank_provenance_valid = (
        bool(case_count)
        and rerank_applied_case_count == case_count
        and "sentence-transformers" in rerank_backend.lower()
        and bool(rerank_model)
    )
    rounds: list[dict[str, Any]] = [
        _round(
            1,
            "2.6.6",
            "immutable_benchmark_snapshot",
            "固定评测快照",
            "pass" if snapshot_bound else "watch" if benchmark_ready else "blocked",
            "固定题集、知识库 generation 和持久化评测结果必须同源绑定。",
            [
                _metric(
                    "dataset_binding",
                    "题集哈希",
                    (_normalized(benchmark.get("dataset_sha256"))[:12] or "缺失"),
                    "固定且可追溯",
                    "pass" if _normalized(benchmark.get("dataset_sha256")) else "blocked",
                ),
                _metric(
                    "knowledge_base_binding",
                    "知识库 generation",
                    (_normalized(benchmark.get("knowledge_base_generation_id"))[:12] or "缺失"),
                    "固定且可追溯",
                    "pass" if _normalized(benchmark.get("knowledge_base_generation_id")) else "blocked",
                ),
                _metric(
                    "persisted_result",
                    "持久化评测",
                    "已落盘" if benchmark_path.is_file() else "仅预览",
                    "必须已落盘",
                    "pass" if benchmark_path.is_file() else "watch",
                ),
                _metric(
                    "benchmark_digest",
                    "评测快照摘要",
                    _benchmark_digest(benchmark)[:12] if benchmark_ready else "缺失",
                    "审批与运行工件必须引用",
                    "pass" if snapshot_bound else "watch" if benchmark_ready else "blocked",
                ),
            ],
            [] if snapshot_bound else ["运行固定题集并保留与当前行业知识库 generation 匹配的结果。"],
            [artifact_evidence[0]],
        ),
        _round(
            2,
            "2.6.7",
            "cohort_coverage",
            "题集分层覆盖",
            "pass" if case_count >= MIN_FIXED_CASES and len(_case_ids(benchmark)) == case_count else "watch" if case_count else "blocked",
            "评测集需要覆盖至少 12 个具备可追溯结果的跨行业固定题目。",
            [
                _metric("fixed_case_count", "固定题目", str(case_count), f">={MIN_FIXED_CASES}", "pass" if case_count >= MIN_FIXED_CASES else "watch"),
                _metric(
                    "result_coverage",
                    "结果覆盖",
                    f"{len(_case_ids(benchmark))}/{case_count}",
                    "每题均有结果",
                    "pass" if case_count and len(_case_ids(benchmark)) == case_count else "watch",
                ),
                _metric("strategy_arms", "策略臂", str(len(arms)), f">={len(STRATEGY_KEYS)}", "pass" if len(arms) >= len(STRATEGY_KEYS) else "watch"),
            ],
            [] if case_count >= MIN_FIXED_CASES else ["扩充固定题集后再将候选策略用于上线决策。"],
        ),
        _round(
            3,
            "2.6.8",
            "failure_localization",
            "逐题失败归因",
            "pass" if benchmark_ready and all(len(_safe_sequence(arm.get("cases"))) == case_count for arm in arms) else "watch" if benchmark_ready else "blocked",
            "每个策略都必须保留逐题 Recall、nDCG、引用命中和延迟，用于定位失败而非只看平均数。",
            [
                _metric(
                    "case_level_metrics",
                    "逐题指标",
                    f"{sum(len(_safe_sequence(arm.get('cases'))) for arm in arms)}/{case_count * max(1, len(arms))}",
                    "每题每策略可回溯",
                    "pass" if case_count and all(len(_safe_sequence(arm.get("cases"))) == case_count for arm in arms) else "watch",
                ),
                _metric(
                    "quality_failures",
                    "有质量告警策略",
                    str(
                        sum(
                            1
                            for arm in arms
                            if any(
                                (_safe_number(case.get("recall_at_10")) or 0) < 1
                                or (_safe_number(case.get("citation_hit_rate")) or 0) < 1
                                for case in _safe_sequence(arm.get("cases"))
                                if isinstance(case, Mapping)
                            )
                        )
                    ),
                    "允许暴露，不得隐藏",
                    "pass" if benchmark_ready else "blocked",
                    "该指标是定位队列，不等同于候选可上线。",
                ),
            ],
            [] if benchmark_ready else ["先修复知识库或评测结果，使逐题指标可读取。"],
        ),
        _round(
            4,
            "2.6.9",
            "full_report_review_integrity",
            "完整研报人工复核完整性",
            "pass" if review_state["complete"] else "blocked",
            "机器检索指标不能替代完整研报人工评分；评审人必须声明独立性与利益冲突。",
            [
                _metric(
                    "review_pairs",
                    "有效评分对",
                    f"{review_state['valid_pair_count']}/{review_state['expected_pair_count']}",
                    "每题每策略均有完整报告评分",
                    "pass" if review_state["valid_pair_count"] == review_state["expected_pair_count"] and review_state["expected_pair_count"] else "blocked",
                ),
                _metric(
                    "review_protocol",
                    "复核协议",
                    REVIEW_PROTOCOL_VERSION if review_state["protocol_valid"] else "缺失/旧版本",
                    REVIEW_PROTOCOL_VERSION,
                    "pass" if review_state["protocol_valid"] else "blocked",
                ),
                _metric(
                    "reviewer_attestation",
                    "独立复核声明",
                    "已填写" if review_state["reviewer_valid"] else "缺失",
                    "身份、独立性、利益冲突和声明齐全",
                    "pass" if review_state["reviewer_valid"] else "blocked",
                ),
            ],
            list(review_state["warnings"]) or ["完成全部固定题集完整研报的独立人工复核。"],
            [artifact_evidence[1]],
        ),
        _round(
            5,
            "2.7.0",
            "paired_human_review",
            "配对人工评分",
            "pass" if review_state["complete"] and all(item["paired_case_count"] == case_count for item in paired_scores.values()) else "blocked",
            "同一固定题目的基线与候选必须由同一复核协议下的完整研报评分进行配对比较。",
            [
                _metric(
                    f"paired_{strategy}",
                    INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGIES[strategy].label,
                    f"{item['paired_case_count']}/{case_count}",
                    "全部题目配对",
                    "pass" if item["paired_case_count"] == case_count and case_count else "blocked",
                    f"平均分差 {item['mean_delta'] if item['mean_delta'] is not None else '待评分'}。",
                )
                for strategy, item in paired_scores.items()
            ],
            ["使用同一固定输入和独立复核协议补齐基线与候选的完整研报评分。"] if not review_state["complete"] else [],
            [artifact_evidence[1]],
        ),
        _round(
            6,
            "2.7.1",
            "paired_significance",
            "人工评分显著性",
            (
                "pass"
                if candidate_strategy in paired_scores
                and paired_scores[candidate_strategy]["ci_lower"] is not None
                and float(paired_scores[candidate_strategy]["ci_lower"]) > 0
                else "blocked"
                if not review_state["complete"]
                else "watch"
            ),
            "候选策略不仅需要平均分更高，还必须以固定题集配对 bootstrap 区间证明质量增益。",
            [
                _metric(
                    f"ci_{strategy}",
                    f"{INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGIES[strategy].label} 95% CI",
                    (
                        f"{item['ci_lower']:+.2f} 到 {item['ci_upper']:+.2f}"
                        if item["ci_lower"] is not None and item["ci_upper"] is not None
                        else "待配对评分"
                    ),
                    "候选下界 > 0",
                    "pass" if item["ci_lower"] is not None and float(item["ci_lower"]) > 0 else "watch" if review_state["complete"] else "blocked",
                )
                for strategy, item in paired_scores.items()
            ],
            ["完成独立配对评分后，检查候选策略质量增益的 95% bootstrap 下界。"] if not review_state["complete"] else [],
        ),
        _round(
            7,
            "2.7.2",
            "latency_and_cost_guardrail",
            "延迟与成本边界",
            (
                "pass"
                if baseline
                and _arm_metric(baseline, "latency_ms") is not None
                and all(
                    _arm_metric(arm, "latency_ms") is not None
                    and (_arm_metric(arm, "latency_ms") or 0) <= (_arm_metric(baseline, "latency_ms") or 0) * 2
                    for arm in arms
                    if _normalized(arm.get("strategy")) != baseline_strategy
                )
                else "watch"
                if benchmark_ready
                else "blocked"
            ),
            "候选策略平均延迟不得超过基线两倍；本地 Cross Encoder 的硬件成本仍需在影子运行中观察。",
            [
                _metric(
                    "baseline_latency",
                    "基线平均延迟",
                    f"{round(_arm_metric(baseline or {}, 'latency_ms') or 0)} ms",
                    "作为候选延迟基线",
                    "pass" if baseline and _arm_metric(baseline, "latency_ms") is not None else "blocked",
                ),
                _metric(
                    "candidate_latency_guardrail",
                    "候选延迟门",
                    "已计算" if benchmark_ready else "不可用",
                    "<= 基线 2 倍",
                    "pass" if benchmark_ready else "blocked",
                    "本地复排不应被误报为零硬件成本。",
                ),
            ],
            [] if benchmark_ready else ["先生成可比较的固定题集延迟结果。"],
        ),
        _round(
            8,
            "2.7.3",
            "cross_encoder_provenance",
            "真实 Cross Encoder 证明",
            (
                "pass"
                if rerank_provenance_valid
                else "blocked"
            ),
            "候选 B 必须在每个固定题目实际使用本地 Cross Encoder；启发式或不可用回退不能计作复排。",
            [
                _metric(
                    "rerank_case_proof",
                    "实际复排覆盖",
                    f"{rerank_applied_case_count}/{case_count}",
                    "全部固定题目",
                    "pass" if case_count and rerank_applied_case_count == case_count else "blocked",
                ),
                _metric(
                    "rerank_backend",
                    "复排后端",
                    rerank_backend,
                    "sentence-transformers",
                    "pass" if "sentence-transformers" in rerank_backend.lower() else "blocked",
                ),
                _metric(
                    "rerank_model",
                    "实际复排模型",
                    rerank_model or "未记录",
                    "具名本地 Cross Encoder",
                    "pass" if rerank_model else "blocked",
                ),
            ],
            ["在已缓存 Cross Encoder 模型的本机上重跑固定题集，保存实际后端与模型证明。"],
        ),
        _round(
            9,
            "2.7.4",
            "candidate_governance",
            "候选上线判定",
            "pass" if promotion_decision == "promote" and candidate_strategy else "blocked",
            "固定题集、人工评分、延迟和真实复排均通过后，候选才能进入人工批准，不会自动生效。",
            [
                _metric("promotion_decision", "评测判定", promotion_decision, "promote", "pass" if promotion_decision == "promote" else "blocked"),
                _metric(
                    "candidate_strategy",
                    "候选策略",
                    candidate_strategy or "未产生",
                    "明确且可回滚",
                    "pass" if candidate_strategy else "blocked",
                ),
            ],
            list(promotion.get("reasons") or []) or ["保持基线默认策略，直至候选通过全部质量门。"],
            [artifact_evidence[0], artifact_evidence[1]],
        ),
        _round(
            10,
            "2.7.5",
            "human_approval",
            "人工批准与职责分离",
            "pass" if approval_state["valid"] else "blocked",
            "评测候选必须由具名负责人批准；审批工件需绑定当前题集、知识库和候选策略。",
            [
                _metric(
                    "approval_binding",
                    "审批快照绑定",
                    "有效" if approval_state["valid"] else "无效/缺失",
                    "当前 benchmark、题集、索引和候选一致",
                    "pass" if approval_state["valid"] else "blocked",
                ),
                _metric(
                    "approval_digest",
                    "审批摘要",
                    approval_state["digest"][:12] if approval_state["valid"] else "待批准",
                    "可供影子与漂移工件引用",
                    "pass" if approval_state["valid"] else "blocked",
                ),
            ],
            approval_state["issues"] or ["由独立批准人签署候选策略工件。"],
            [artifact_evidence[2]],
        ),
        _round(
            11,
            "2.7.6",
            "shadow_run",
            "受控影子运行",
            "pass" if shadow_state["valid"] else "blocked",
            "批准后的候选只可先在影子流量中观察，样本、fallback 和回退都必须留痕。",
            [
                _metric(
                    "shadow_samples",
                    "影子样本",
                    str(shadow_state["sample_count"]),
                    f">={MIN_SHADOW_SAMPLE_SIZE}",
                    "pass" if shadow_state["sample_count"] >= MIN_SHADOW_SAMPLE_SIZE else "blocked",
                ),
                _metric(
                    "shadow_failures",
                    "fallback/质量回退",
                    f"{shadow_state['fallback_count']}/{shadow_state['regression_count']}",
                    "0/0",
                    "pass" if not shadow_state["fallback_count"] and not shadow_state["regression_count"] else "blocked",
                ),
            ],
            shadow_state["issues"] or ["保持影子运行，禁止将结果用于生产默认检索。"],
            [artifact_evidence[3]],
        ),
        _round(
            12,
            "2.7.7",
            "drift_monitoring",
            "固定题集漂移监测",
            "pass" if drift_state["valid"] else "blocked",
            "候选的固定题集表现需在批准后持续检查；任一回退应保持或恢复基线。",
            [
                _metric(
                    "drift_coverage",
                    "漂移检查覆盖",
                    str(drift_state["checked_case_count"]),
                    f">={MIN_FIXED_CASES}",
                    "pass" if drift_state["checked_case_count"] >= MIN_FIXED_CASES else "blocked",
                ),
                _metric(
                    "drift_regressions",
                    "质量回退",
                    str(drift_state["regression_count"]),
                    "0",
                    "pass" if not drift_state["regression_count"] else "blocked",
                ),
            ],
            drift_state["issues"] or ["按固定题集和真实影子样本持续监测候选策略。"],
            [artifact_evidence[4]],
        ),
        _round(
            13,
            "2.7.8",
            "rollback_readiness",
            "一键回退基线",
            (
                "pass"
                if baseline_strategy == "baseline_hybrid"
                and [item["key"] for item in industry_knowledge_retrieval_strategy_catalog() if item.get("default")] == ["baseline_hybrid"]
                else "blocked"
            ),
            "基线策略保持显式默认且不依赖任何候选审批；候选证据失效时可立即回退。",
            [
                _metric("default_strategy", "生产默认", baseline_strategy, "baseline_hybrid", "pass" if baseline_strategy == "baseline_hybrid" else "blocked"),
                _metric(
                    "single_default",
                    "唯一默认策略",
                    ", ".join(item["key"] for item in industry_knowledge_retrieval_strategy_catalog() if item.get("default")) or "无",
                    "baseline_hybrid",
                    "pass"
                    if [item["key"] for item in industry_knowledge_retrieval_strategy_catalog() if item.get("default")] == ["baseline_hybrid"]
                    else "blocked",
                ),
            ],
            [] if baseline_strategy == "baseline_hybrid" else ["将生产默认恢复为 baseline_hybrid，并重新验证候选。"],
        ),
        _round(
            14,
            "2.7.9",
            "audit_chain",
            "审批、影子和漂移审计链",
            "pass" if approval_state["valid"] and shadow_state["valid"] and drift_state["valid"] else "blocked",
            "审批摘要必须被后续影子和漂移工件引用，形成不能由单次评测替代的可审计链条。",
            [
                _metric("approval_to_shadow", "审批到影子链路", "已绑定" if shadow_state["valid"] else "缺失", "同一审批摘要", "pass" if shadow_state["valid"] else "blocked"),
                _metric("approval_to_drift", "审批到漂移链路", "已绑定" if drift_state["valid"] else "缺失", "同一审批摘要", "pass" if drift_state["valid"] else "blocked"),
            ],
            ["补齐具名批准、影子和漂移工件后再审计关联摘要。"] if not (approval_state["valid"] and shadow_state["valid"] and drift_state["valid"]) else [],
            [artifact_evidence[2], artifact_evidence[3], artifact_evidence[4]],
        ),
        _round(
            15,
            "2.8.0",
            "release_readiness_integration",
            "发布就绪聚合",
            "pass" if baseline_strategy == "baseline_hybrid" and benchmark_ready else "watch" if benchmark_ready else "blocked",
            "该保证快照进入 release-readiness；任一外部证据缺失都会让聚合状态保持 blocked，而不会改变生产默认。",
            [
                _metric("integration", "Release-readiness 接入", "已接入", "只读 fail-closed 聚合", "pass"),
                _metric(
                    "production_default_protected",
                    "生产默认保护",
                    baseline_strategy,
                    "baseline_hybrid 直至全部证据通过",
                    "pass" if baseline_strategy == "baseline_hybrid" else "blocked",
                ),
            ],
            ["完成所有外部人工与运行工件前，保持 release readiness 为 blocked。"],
            artifact_evidence,
        ),
    ]
    pass_count = sum(round_item["status"] == "pass" for round_item in rounds)
    watch_count = sum(round_item["status"] == "watch" for round_item in rounds)
    blocked_count = sum(round_item["status"] == "blocked" for round_item in rounds)
    status = "blocked" if blocked_count else "watch" if watch_count else "pass"
    next_actions: list[str] = []
    for round_item in rounds:
        for action in round_item["next_actions"]:
            if action and action not in next_actions:
                next_actions.append(action)
    warnings = list(_safe_sequence(benchmark.get("warnings")))
    if status != "pass":
        warnings.append("外部人工复核、批准、影子或漂移证据未齐全，生产默认继续保持 baseline_hybrid。")
    return {
        "program_version": PROGRAM_VERSION,
        "generated_at": _utc_now(),
        "status": status,
        "score": round(sum(_round_status_score(round_item["status"]) for round_item in rounds) / len(rounds)),
        "current_default_strategy": baseline_strategy,
        "candidate_strategy": candidate_strategy,
        "promotion_decision": promotion_decision if promotion_decision in {"promote", "hold", "block"} else "block",
        "benchmark_id": _normalized(benchmark.get("benchmark_id")) or BENCHMARK_ID,
        "dataset_sha256": _normalized(benchmark.get("dataset_sha256")),
        "benchmark_digest": _benchmark_digest(benchmark),
        "knowledge_base_generation_id": _normalized(benchmark.get("knowledge_base_generation_id")),
        "case_count": case_count,
        "pass_count": pass_count,
        "watch_count": watch_count,
        "blocked_count": blocked_count,
        "rounds": rounds,
        "artifacts": artifact_evidence,
        "next_actions": next_actions[:12],
        "warnings": list(dict.fromkeys(_normalized(item) for item in warnings if _normalized(item))),
    }


def _approval_template_payload(benchmark: Mapping[str, Any]) -> dict[str, Any]:
    promotion = benchmark.get("promotion") if isinstance(benchmark.get("promotion"), Mapping) else {}
    return {
        "schema_version": APPROVAL_SCHEMA_VERSION,
        "benchmark_id": _normalized(benchmark.get("benchmark_id")) or BENCHMARK_ID,
        "dataset_sha256": _normalized(benchmark.get("dataset_sha256")),
        "knowledge_base_generation_id": _normalized(benchmark.get("knowledge_base_generation_id")),
        "benchmark_digest": _benchmark_digest(benchmark),
        "candidate_strategy": _normalized(promotion.get("candidate_strategy")),
        "decision": "pending",
        "approved_by": "",
        "approver_role": "",
        "approved_at": "",
        "attestation": "",
        "separation_attestation": "",
        "notes": "",
        "instructions": [
            "仅当固定题集、完整研报独立复核、显著性、延迟和真实 Cross Encoder 证明均已通过时，才可将 decision 改为 approved。",
            "审批人必须独立于完整研报复核人，并填写真实身份、角色、时间、审批声明和职责分离声明。",
            "此工件仅允许候选进入影子运行，不会更改生产默认策略。",
        ],
    }


def export_industry_knowledge_retrieval_approval_template(
    *,
    output_path: str | Path = DEFAULT_APPROVAL_PATH,
    benchmark_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Export a blank human-approval template; it never approves a strategy."""

    benchmark = _benchmark_payload_or_latest(benchmark_payload)
    template = _approval_template_payload(benchmark)
    path = Path(output_path)
    if path.exists():
        existing = _read_json(path)
        if existing is None:
            raise ValueError("已有审批工件不可读取；为避免覆盖人工记录，未生成新模板。")
        return existing
    _write_json(path, template)
    return template


def _write_runtime_template(path: Path, template: Mapping[str, Any]) -> dict[str, Any]:
    """Create a runtime template or only refresh an untouched pending template."""

    if not path.exists():
        _write_json(path, template)
        return dict(template)
    existing = _read_json(path)
    if existing is None:
        raise ValueError(f"已有运行工件 {path.name} 不可读取；为避免覆盖人工记录，未生成新模板。")
    has_runtime_evidence = _normalized(existing.get("status")).lower() == "complete" or any(
        _normalized(existing.get(key))
        for key in ("executed_by", "executed_at", "attestation", "notes")
    ) or any(
        _safe_count(existing.get(key))
        for key in ("sample_count", "fallback_count", "quality_regression_count", "checked_case_count", "regression_count")
    )
    if has_runtime_evidence:
        return existing
    refreshed = dict(template)
    for key in ("notes", "instructions"):
        if key in existing:
            refreshed[key] = existing[key]
    _write_json(path, refreshed)
    return refreshed


def export_industry_knowledge_retrieval_evidence_templates(
    *,
    approval_path: str | Path = DEFAULT_APPROVAL_PATH,
    shadow_path: str | Path = DEFAULT_SHADOW_PATH,
    drift_path: str | Path = DEFAULT_DRIFT_PATH,
    review_path: str | Path = DEFAULT_REVIEW_PATH,
    benchmark_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create pending audit templates without generating approval or runtime evidence.

    The templates deliberately contain no fabricated sample counts, decisions,
    reviewer identity, or quality outcomes. Operators may fill them only after
    the corresponding real approval, shadow run, or drift check occurred.
    """

    benchmark = _benchmark_payload_or_latest(benchmark_payload)
    promotion = benchmark.get("promotion") if isinstance(benchmark.get("promotion"), Mapping) else {}
    candidate_strategy = _normalized(promotion.get("candidate_strategy"))
    approval_file = Path(approval_path)
    approval = _read_json(approval_file)
    if approval is None and not approval_file.exists():
        approval = _approval_template_payload(benchmark)
        _write_json(approval_file, approval)
    elif approval is None:
        raise ValueError("已有审批工件不可读取；为避免覆盖人工记录，未生成运行模板。")
    review = _read_json(Path(review_path))
    approval_state = _approval_summary(
        approval,
        benchmark,
        promotion,
        reviewer_name=_normalized(review.get("reviewer_name")) if review else "",
        review_complete=_review_summary(review, benchmark)["complete"],
    )
    approval_digest = approval_state["digest"] if approval_state["valid"] else ""
    shared = {
        "benchmark_id": _normalized(benchmark.get("benchmark_id")) or BENCHMARK_ID,
        "dataset_sha256": _normalized(benchmark.get("dataset_sha256")),
        "knowledge_base_generation_id": _normalized(benchmark.get("knowledge_base_generation_id")),
        "benchmark_digest": _benchmark_digest(benchmark),
        "candidate_strategy": candidate_strategy,
        "approval_digest": approval_digest,
    }
    shadow = {
        "schema_version": SHADOW_SCHEMA_VERSION,
        **shared,
        "status": "pending",
        "executed_by": "",
        "executed_at": "",
        "sample_count": 0,
        "fallback_count": 0,
        "quality_regression_count": 0,
        "attestation": "",
        "notes": "",
        "instructions": [
            f"仅在候选策略已由独立负责人批准后填写，影子样本至少 {MIN_SHADOW_SAMPLE_SIZE} 条。",
            "记录真实 sample_count、fallback_count 和 quality_regression_count；不得将模拟数据或缓存结果写成运行证据。",
            "status 仅在运行完成且所有数据可追溯时改为 complete。该模板不会切换生产默认策略。",
        ],
    }
    drift = {
        "schema_version": DRIFT_SCHEMA_VERSION,
        **shared,
        "status": "pending",
        "executed_by": "",
        "executed_at": "",
        "checked_case_count": 0,
        "regression_count": 0,
        "attestation": "",
        "notes": "",
        "instructions": [
            f"在影子运行后使用至少 {MIN_FIXED_CASES} 个固定题目重跑检查。",
            "记录真实 checked_case_count 和 regression_count；发现回退时不得标记 complete/pass。",
            "status 仅在完整检查后改为 complete，且该模板不会自动上线候选策略。",
        ],
    }
    _write_runtime_template(Path(shadow_path), shadow)
    _write_runtime_template(Path(drift_path), drift)
    warnings = list(approval_state["issues"])
    if not candidate_strategy:
        warnings.append("当前没有通过 A/B 门禁的候选策略；模板只用于预先准备，不能触发上线。")
    if not approval_state["valid"]:
        warnings.append("当前审批尚未验证通过；影子和漂移模板未绑定 approval_digest，真实审批完成后需重新导出运行模板。")
    return {
        "benchmark_id": shared["benchmark_id"],
        "dataset_sha256": shared["dataset_sha256"],
        "knowledge_base_generation_id": shared["knowledge_base_generation_id"],
        "candidate_strategy": candidate_strategy,
        "approval_template_path": _artifact_reference(Path(approval_path)),
        "shadow_template_path": _artifact_reference(Path(shadow_path)),
        "drift_template_path": _artifact_reference(Path(drift_path)),
        "warnings": warnings,
    }
