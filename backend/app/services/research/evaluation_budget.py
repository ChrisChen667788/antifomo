from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal, ROUND_HALF_UP

from pydantic import BaseModel, Field

from app.services.research.evaluation_dataset import (
    ResearchEvaluationCase,
    ResearchEvaluationDatasetManifest,
)
from app.services.research.evaluation_runner import ResearchEvaluationObservation


class ResearchLiveEvaluationBatch(BaseModel):
    batch_number: int
    case_ids: list[str]
    target_cost_ceiling_usd: float


class ResearchLiveEvaluationPlan(BaseModel):
    dataset_id: str
    dataset_version: str
    dataset_content_sha256: str
    selected_case_count: int
    batch_size: int
    batch_count: int
    target_cost_ceiling_usd: float
    approved_budget_usd: float | None = None
    budget_sufficient: bool = False
    batches: list[ResearchLiveEvaluationBatch] = Field(default_factory=list)


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _case_cost_ceiling(case: ResearchEvaluationCase) -> Decimal:
    value = case.metric_targets.get("estimated_cost_usd")
    if value is None or value <= 0:
        raise ValueError(f"case {case.case_id} requires a positive estimated_cost_usd target")
    return Decimal(str(value))


def build_research_live_evaluation_plan(
    manifest: ResearchEvaluationDatasetManifest,
    cases: list[ResearchEvaluationCase],
    *,
    batch_size: int = 5,
    approved_budget_usd: float | None = None,
) -> ResearchLiveEvaluationPlan:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    if approved_budget_usd is not None and approved_budget_usd < 0:
        raise ValueError("approved_budget_usd must be non-negative")
    batches: list[ResearchLiveEvaluationBatch] = []
    for offset in range(0, len(cases), batch_size):
        batch_cases = cases[offset : offset + batch_size]
        batch_cost = sum((_case_cost_ceiling(case) for case in batch_cases), Decimal("0"))
        batches.append(
            ResearchLiveEvaluationBatch(
                batch_number=len(batches) + 1,
                case_ids=[case.case_id for case in batch_cases],
                target_cost_ceiling_usd=_money(batch_cost),
            )
        )
    total = sum((Decimal(str(batch.target_cost_ceiling_usd)) for batch in batches), Decimal("0"))
    budget = Decimal(str(approved_budget_usd)) if approved_budget_usd is not None else None
    return ResearchLiveEvaluationPlan(
        dataset_id=manifest.dataset_id,
        dataset_version=manifest.version,
        dataset_content_sha256=manifest.content_sha256,
        selected_case_count=len(cases),
        batch_size=batch_size,
        batch_count=len(batches),
        target_cost_ceiling_usd=_money(total),
        approved_budget_usd=approved_budget_usd,
        budget_sufficient=budget is not None and budget >= total,
        batches=batches,
    )


class BudgetedResearchEvaluationExecutor:
    def __init__(
        self,
        executor: Callable[[ResearchEvaluationCase], ResearchEvaluationObservation],
        *,
        approved_budget_usd: float,
    ) -> None:
        if approved_budget_usd <= 0:
            raise ValueError("approved_budget_usd must be positive")
        self._executor = executor
        self._approved_budget = Decimal(str(approved_budget_usd))
        self._observed_cost = Decimal("0")
        self._blocked_reason = ""

    @property
    def observed_cost_usd(self) -> float:
        return _money(self._observed_cost)

    def __call__(self, case: ResearchEvaluationCase) -> ResearchEvaluationObservation:
        if self._blocked_reason:
            raise RuntimeError(self._blocked_reason)
        if self._observed_cost >= self._approved_budget:
            raise RuntimeError("approved live-evaluation budget is exhausted")
        observation = self._executor(case)
        if observation.estimated_cost_usd is None:
            self._blocked_reason = (
                "provider pricing is unavailable; remaining live-evaluation cases were blocked"
            )
            raise RuntimeError(self._blocked_reason)
        self._observed_cost += Decimal(str(observation.estimated_cost_usd))
        if self._observed_cost > self._approved_budget:
            self._blocked_reason = "observed live-evaluation cost exceeded the approved budget"
            raise RuntimeError(self._blocked_reason)
        return observation
