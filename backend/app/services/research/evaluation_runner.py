from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
from statistics import fmean
import time
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from app.schemas.research import ResearchReportRequest, ResearchReportResponse
from app.services.research.evaluation_dataset import (
    ResearchEvaluationCase,
    ResearchEvaluationDatasetManifest,
)
from app.services.research_service import execute_research_report_workflow


MetricDirection = Literal["min", "max"]
ObservedBehavior = Literal["answer", "guard", "refuse", "error"]


class ResearchEvaluationSourceObservation(BaseModel):
    url: str
    domain: str = ""
    source_tier: str = "media"


class ResearchEvaluationObservation(BaseModel):
    run_id: str = ""
    status: Literal["succeeded", "failed"] = "succeeded"
    observed_behavior: ObservedBehavior = "answer"
    text: str = ""
    section_titles: list[str] = Field(default_factory=list)
    supported_section_count: int = 0
    section_count: int = 0
    sources: list[ResearchEvaluationSourceObservation] = Field(default_factory=list)
    latency_ms: float = 0.0
    estimated_cost_usd: float | None = None
    error: str = ""


class ResearchEvaluationMetricResult(BaseModel):
    key: str
    value: float | None = None
    target: float | None = None
    direction: MetricDirection = "min"
    passed: bool | None = None
    available: bool = True
    note: str = ""


class ResearchEvaluationCaseResult(BaseModel):
    case_id: str
    suite_id: str
    expected_behavior: str
    observed_behavior: ObservedBehavior
    status: Literal["passed", "failed", "error", "not_gate_eligible"]
    metrics: dict[str, ResearchEvaluationMetricResult]
    required_section_coverage: float
    unavailable_metrics: list[str] = Field(default_factory=list)
    run_id: str = ""
    error: str = ""


class ResearchEvaluationRunResult(BaseModel):
    dataset_id: str
    dataset_version: str
    dataset_status: str
    started_at: datetime
    finished_at: datetime
    selected_case_count: int
    succeeded_case_count: int
    failed_case_count: int
    error_case_count: int
    aggregate_metrics: dict[str, ResearchEvaluationMetricResult]
    release_gate_eligible: bool
    release_gate_passed: bool
    gate_blockers: list[str] = Field(default_factory=list)
    cases: list[ResearchEvaluationCaseResult]

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


ResearchEvaluationExecutor = Callable[[ResearchEvaluationCase], ResearchEvaluationObservation]


def _normalized(value: str) -> str:
    return re.sub(r"[\W_]+", "", value.casefold(), flags=re.UNICODE)


def _coverage(expected: Iterable[str], observed_text: str) -> float:
    terms = [_normalized(value) for value in expected if _normalized(value)]
    if not terms:
        return 1.0
    haystack = _normalized(observed_text)
    return sum(1 for term in terms if term in haystack) / len(terms)


def _section_coverage(expected: list[str], observed: list[str]) -> float:
    if not expected:
        return 1.0
    normalized_observed = [_normalized(value) for value in observed]
    hits = 0
    for title in expected:
        normalized_title = _normalized(title)
        if any(normalized_title in candidate or candidate in normalized_title for candidate in normalized_observed):
            hits += 1
    return hits / len(expected)


def _source_retrieval_metrics(
    case: ResearchEvaluationCase,
    sources: list[ResearchEvaluationSourceObservation],
    *,
    k: int = 5,
) -> dict[str, float] | None:
    expected_domains = {value.casefold().removeprefix("www.") for value in case.expected_source_domains if value}
    expected_urls = {value.rstrip("/").casefold() for value in case.expected_source_urls if value}
    references = {f"domain:{value}" for value in expected_domains} | {f"url:{value}" for value in expected_urls}
    if not references:
        return None

    matched_references: set[str] = set()
    relevances: list[int] = []
    for source in sources[:k]:
        source_url = source.url.rstrip("/").casefold()
        source_domain = (source.domain or urlparse(source.url).netloc).casefold().removeprefix("www.")
        matches: set[str] = set()
        if source_domain in expected_domains:
            matches.add(f"domain:{source_domain}")
        if source_url in expected_urls:
            matches.add(f"url:{source_url}")
        matched_references.update(matches)
        relevances.append(1 if matches else 0)

    recall = len(matched_references) / len(references)
    first_relevant = next((index for index, value in enumerate(relevances, start=1) if value), None)
    mrr = 1.0 / first_relevant if first_relevant else 0.0
    dcg = sum(value / math.log2(index + 1) for index, value in enumerate(relevances, start=1))
    ideal_count = min(len(references), k)
    idcg = sum(1.0 / math.log2(index + 1) for index in range(1, ideal_count + 1))
    return {
        "recall_at_5": recall,
        "mrr": mrr,
        "ndcg_at_5": dcg / idcg if idcg else 0.0,
    }


def _metric(
    key: str,
    value: float | None,
    target: float | None,
    *,
    direction: MetricDirection,
    unavailable_note: str = "",
) -> ResearchEvaluationMetricResult:
    if value is None:
        return ResearchEvaluationMetricResult(
            key=key,
            value=None,
            target=target,
            direction=direction,
            passed=None,
            available=False,
            note=unavailable_note,
        )
    passed = None
    if target is not None:
        passed = value <= target if direction == "max" else value >= target
    return ResearchEvaluationMetricResult(
        key=key,
        value=round(value, 8),
        target=target,
        direction=direction,
        passed=passed,
    )


def score_research_evaluation_case(
    case: ResearchEvaluationCase,
    observation: ResearchEvaluationObservation,
) -> ResearchEvaluationCaseResult:
    retrieval = _source_retrieval_metrics(case, observation.sources)
    answer_terms = case.reference_answer_terms or case.required_terms
    answer_correctness = _coverage(answer_terms, observation.text)
    citation_support_rate = (
        observation.supported_section_count / observation.section_count
        if observation.section_count > 0
        else 0.0
    )
    refusal_accuracy = float(observation.observed_behavior == case.expected_behavior)
    targets = case.metric_targets
    metrics = {
        "recall_at_5": _metric(
            "recall_at_5",
            retrieval["recall_at_5"] if retrieval else None,
            targets.get("recall_at_5"),
            direction="min",
            unavailable_note="expected_source_domains or expected_source_urls require human curation",
        ),
        "mrr": _metric(
            "mrr",
            retrieval["mrr"] if retrieval else None,
            targets.get("mrr"),
            direction="min",
            unavailable_note="expected source ranking requires human curation",
        ),
        "ndcg_at_5": _metric(
            "ndcg_at_5",
            retrieval["ndcg_at_5"] if retrieval else None,
            targets.get("ndcg_at_5"),
            direction="min",
            unavailable_note="graded source relevance requires human curation",
        ),
        "citation_support_rate": _metric(
            "citation_support_rate",
            citation_support_rate,
            targets.get("citation_support_rate"),
            direction="min",
        ),
        "answer_correctness": _metric(
            "answer_correctness",
            answer_correctness,
            targets.get("answer_correctness"),
            direction="min",
        ),
        "refusal_accuracy": _metric(
            "refusal_accuracy",
            refusal_accuracy,
            targets.get("refusal_accuracy"),
            direction="min",
        ),
        "latency_ms": _metric(
            "latency_ms",
            observation.latency_ms,
            targets.get("latency_ms"),
            direction="max",
        ),
        "estimated_cost_usd": _metric(
            "estimated_cost_usd",
            observation.estimated_cost_usd,
            targets.get("estimated_cost_usd"),
            direction="max",
            unavailable_note="the configured provider did not supply pricing",
        ),
    }
    unavailable = [key for key, metric in metrics.items() if not metric.available]
    failed = [metric for metric in metrics.values() if metric.passed is False]
    if observation.status == "failed" or observation.observed_behavior == "error":
        status: Literal["passed", "failed", "error", "not_gate_eligible"] = "error"
    elif unavailable:
        status = "not_gate_eligible"
    elif failed:
        status = "failed"
    else:
        status = "passed"
    return ResearchEvaluationCaseResult(
        case_id=case.case_id,
        suite_id=case.suite_id,
        expected_behavior=case.expected_behavior,
        observed_behavior=observation.observed_behavior,
        status=status,
        metrics=metrics,
        required_section_coverage=round(
            _section_coverage(case.required_sections, observation.section_titles),
            8,
        ),
        unavailable_metrics=unavailable,
        run_id=observation.run_id,
        error=observation.error,
    )


def _aggregate_metric(
    key: str,
    results: list[ResearchEvaluationCaseResult],
) -> ResearchEvaluationMetricResult:
    available = [result.metrics[key] for result in results if result.metrics[key].available]
    direction: MetricDirection = "max" if key in {"latency_ms", "estimated_cost_usd"} else "min"
    if not available:
        return _metric(key, None, None, direction=direction, unavailable_note="no scored cases")
    values = [metric.value for metric in available if metric.value is not None]
    targets = [metric.target for metric in available if metric.target is not None]
    return _metric(
        key,
        fmean(values) if values else None,
        fmean(targets) if targets else None,
        direction=direction,
    )


def run_research_evaluation(
    manifest: ResearchEvaluationDatasetManifest,
    cases: list[ResearchEvaluationCase],
    executor: ResearchEvaluationExecutor,
) -> ResearchEvaluationRunResult:
    started_at = datetime.now(timezone.utc)
    results: list[ResearchEvaluationCaseResult] = []
    for case in cases:
        try:
            observation = executor(case)
        except Exception as exc:
            observation = ResearchEvaluationObservation(
                status="failed",
                observed_behavior="error",
                error=f"{exc.__class__.__name__}: {exc}",
            )
        results.append(score_research_evaluation_case(case, observation))

    aggregate_metrics = {
        key: _aggregate_metric(key, results)
        for key in manifest.required_metrics
    }
    unavailable_required = [key for key, metric in aggregate_metrics.items() if not metric.available]
    blockers: list[str] = []
    if manifest.status != "locked":
        blockers.append(f"dataset status is {manifest.status}; locked is required")
    if len(cases) != manifest.expected_case_count:
        blockers.append(
            f"selected {len(cases)} of {manifest.expected_case_count} cases; a full run is required"
        )
    if unavailable_required:
        blockers.append("required metrics unavailable: " + ", ".join(unavailable_required))
    release_gate_eligible = not blockers
    release_gate_passed = release_gate_eligible and all(
        metric.passed is not False for metric in aggregate_metrics.values()
    ) and all(result.status == "passed" for result in results)
    return ResearchEvaluationRunResult(
        dataset_id=manifest.dataset_id,
        dataset_version=manifest.version,
        dataset_status=manifest.status,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        selected_case_count=len(cases),
        succeeded_case_count=sum(result.status in {"passed", "not_gate_eligible"} for result in results),
        failed_case_count=sum(result.status == "failed" for result in results),
        error_case_count=sum(result.status == "error" for result in results),
        aggregate_metrics=aggregate_metrics,
        release_gate_eligible=release_gate_eligible,
        release_gate_passed=release_gate_passed,
        gate_blockers=blockers,
        cases=results,
    )


def _report_text(report: ResearchReportResponse) -> str:
    values = [
        report.report_title,
        report.executive_summary,
        report.consulting_angle,
        *report.target_accounts,
        *report.budget_signals,
        *report.strategic_directions,
    ]
    for section in report.sections:
        values.extend([section.title, *section.items])
    return "\n".join(value for value in values if value)


def _observed_behavior(report: ResearchReportResponse) -> ObservedBehavior:
    text = _report_text(report)
    if any(marker in text for marker in ("无法提供", "不能提供", "拒绝提供", "无权提供", "不应提供")):
        return "refuse"
    if any(marker in text for marker in ("需授权", "合规边界", "敏感信息", "隐私风险", "安全边界")):
        return "guard"
    return "answer"


def execute_research_evaluation_case(case: ResearchEvaluationCase) -> ResearchEvaluationObservation:
    started = time.perf_counter()
    execution = execute_research_report_workflow(
        ResearchReportRequest(
            keyword=case.keyword,
            research_focus=case.research_focus,
            output_language=case.language,
            include_wechat=False,
            research_mode="deep",
            max_sources=14,
        )
    )
    report = execution.report
    metrics = execution.metrics.snapshot()
    cost_ledger = metrics.get("cost_ledger") if isinstance(metrics.get("cost_ledger"), dict) else {}
    latency_ms = float(metrics.get("gauges", {}).get("duration_ms", 0.0)) if isinstance(metrics.get("gauges"), dict) else 0.0
    if latency_ms <= 0:
        latency_ms = (time.perf_counter() - started) * 1000
    estimated_cost = cost_ledger.get("estimated_cost_usd") if isinstance(cost_ledger, dict) else None
    return ResearchEvaluationObservation(
        run_id=execution.metrics.run_id,
        observed_behavior=_observed_behavior(report),
        text=_report_text(report),
        section_titles=[section.title for section in report.sections],
        supported_section_count=sum(
            1 for section in report.sections if section.evidence_count > 0 or section.evidence_links
        ),
        section_count=len(report.sections),
        sources=[
            ResearchEvaluationSourceObservation(
                url=source.url,
                domain=source.domain or "",
                source_tier=source.source_tier,
            )
            for source in report.sources
        ],
        latency_ms=latency_ms,
        estimated_cost_usd=float(estimated_cost) if estimated_cost is not None else None,
    )
