from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.decision_program_entities import DecisionQualityBenchmark
from app.services.decision_program.common import iso


def _finding(key: str, actual: Any, target: str, passed: bool) -> dict[str, Any]:
    return {"key": key, "actual": actual, "target": target, "status": "pass" if passed else "blocked"}


def evaluate_quality_benchmark(
    *,
    benchmark_kind: str,
    case_count: int,
    metrics: dict[str, Any],
    source_artifact_uri: str,
) -> tuple[str, list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    if benchmark_kind == "retrieval":
        ndcg = float(metrics.get("ndcg_at_10") or 0)
        recall = float(metrics.get("recall_at_20") or 0)
        false_positive_rate = float(metrics.get("critical_cross_industry_false_positive_rate") or 1)
        clickback = float(metrics.get("clickback_rate") or 0)
        findings.extend(
            [
                _finding("case_count", case_count, ">= 600 human qrels", case_count >= 600),
                _finding("ndcg_at_10", ndcg, ">= 0.82", ndcg >= 0.82),
                _finding("recall_at_20", recall, ">= 0.92", recall >= 0.92),
                _finding("critical_cross_industry_false_positive_rate", false_positive_rate, "<= 0.01", false_positive_rate <= 0.01),
                _finding("clickback_rate", clickback, ">= 0.99", clickback >= 0.99),
            ]
        )
    elif benchmark_kind == "parser":
        order = float(metrics.get("order_preservation_rate") or 0)
        tables = float(metrics.get("table_preservation_rate") or 0)
        locators = float(metrics.get("locator_clickback_rate") or 0)
        empty = int(metrics.get("empty_output_count") or 0)
        findings.extend(
            [
                _finding("case_count", case_count, ">= 200 real documents", case_count >= 200),
                _finding("order_preservation_rate", order, ">= 0.99", order >= 0.99),
                _finding("table_preservation_rate", tables, ">= 0.99", tables >= 0.99),
                _finding("locator_clickback_rate", locators, ">= 0.99", locators >= 0.99),
                _finding("empty_output_count", empty, "= 0", empty == 0),
            ]
        )
    elif benchmark_kind == "model_ab":
        quality_delta = float(metrics.get("quality_score_delta") or 0)
        citation_delta = float(metrics.get("citation_coverage_delta") or 0)
        cost_delta = float(metrics.get("cost_delta_rate") or 0)
        critical_regressions = int(metrics.get("critical_regression_count") or 0)
        findings.extend(
            [
                _finding("case_count", case_count, ">= 100 paired cases", case_count >= 100),
                _finding("quality_score_delta", quality_delta, ">= 0.05", quality_delta >= 0.05),
                _finding("citation_coverage_delta", citation_delta, ">= 0", citation_delta >= 0),
                _finding("cost_delta_rate", cost_delta, "<= 0.50", cost_delta <= 0.50),
                _finding("critical_regression_count", critical_regressions, "= 0", critical_regressions == 0),
            ]
        )
    elif benchmark_kind == "vertical_pack":
        expert_reviews = int(metrics.get("expert_review_count") or 0)
        pass_rate = float(metrics.get("pass_rate") or 0)
        critical_errors = int(metrics.get("critical_error_count") or 0)
        findings.extend(
            [
                _finding("case_count", case_count, ">= 100 tasks", case_count >= 100),
                _finding("expert_review_count", expert_reviews, ">= 30", expert_reviews >= 30),
                _finding("pass_rate", pass_rate, ">= 0.90", pass_rate >= 0.90),
                _finding("critical_error_count", critical_errors, "= 0", critical_errors == 0),
            ]
        )
    else:
        raise ValueError("Unsupported quality benchmark kind.")
    findings.append(_finding("source_artifact_uri", bool(source_artifact_uri.strip()), "required", bool(source_artifact_uri.strip())))
    status = "pass" if findings and all(row["status"] == "pass" for row in findings) else "blocked"
    return status, findings


def record_quality_benchmark(
    db: Session,
    *,
    user_id: UUID,
    benchmark_key: str,
    version: str,
    benchmark_kind: str,
    incumbent: str,
    challenger: str,
    case_count: int,
    corpus_digest: str,
    configuration: dict[str, Any],
    metrics: dict[str, Any],
    source_artifact_uri: str,
) -> DecisionQualityBenchmark:
    status, findings = evaluate_quality_benchmark(
        benchmark_kind=benchmark_kind,
        case_count=case_count,
        metrics=metrics,
        source_artifact_uri=source_artifact_uri,
    )
    existing = db.scalar(
        select(DecisionQualityBenchmark)
        .where(DecisionQualityBenchmark.user_id == user_id)
        .where(DecisionQualityBenchmark.benchmark_key == benchmark_key.strip())
        .where(DecisionQualityBenchmark.version == version.strip())
    )
    if existing is not None:
        if existing.corpus_digest != corpus_digest.lower() or existing.metrics_payload != metrics:
            raise ValueError("Immutable benchmark version already exists with different evidence.")
        return existing
    row = DecisionQualityBenchmark(
        user_id=user_id,
        benchmark_key=benchmark_key.strip(),
        version=version.strip(),
        benchmark_kind=benchmark_kind,
        status=status,
        incumbent=incumbent.strip(),
        challenger=challenger.strip(),
        case_count=case_count,
        corpus_digest=corpus_digest.lower(),
        configuration_payload=configuration,
        metrics_payload=metrics,
        findings_payload=findings,
        source_artifact_uri=source_artifact_uri.strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def serialize_quality_benchmark(row: DecisionQualityBenchmark) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "benchmark_key": row.benchmark_key,
        "version": row.version,
        "benchmark_kind": row.benchmark_kind,
        "status": row.status,
        "incumbent": row.incumbent,
        "challenger": row.challenger,
        "case_count": row.case_count,
        "corpus_digest": row.corpus_digest,
        "configuration": dict(row.configuration_payload or {}),
        "metrics": dict(row.metrics_payload or {}),
        "findings": list(row.findings_payload or []),
        "source_artifact_uri": row.source_artifact_uri,
        "created_at": iso(row.created_at),
    }
