from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from statistics import fmean
from typing import Literal

from pydantic import BaseModel, Field

from app.services.research.evaluation_dataset import (
    ResearchEvaluationCase,
    ResearchEvaluationDatasetManifest,
)


DIMENSIONS = (
    "accuracy",
    "completeness",
    "insight",
    "actionability",
    "professional_expression",
)
DIMENSION_LABELS = {
    "accuracy": "准确性",
    "completeness": "完整性",
    "insight": "洞察",
    "actionability": "可执行性",
    "professional_expression": "专业表达",
}
HARD_FAILURE_CAPS = {
    "topic_mismatch": 20,
    "minimum_evidence_failed": 40,
    "unsupported_critical_claim": 59,
    "generation_fallback": 45,
    "unverified_account_truth": 25,
    "source_topology_failed": 30,
}

ExpertDecision = Literal["pending", "deliverable", "undeliverable"]
AssignmentRound = Literal["primary", "secondary"]
CalibrationStatus = Literal["pending", "in_review", "calibrated", "changes_requested"]


class ExpertDimensionRatings(BaseModel):
    accuracy: int = Field(default=0, ge=0, le=5)
    completeness: int = Field(default=0, ge=0, le=5)
    insight: int = Field(default=0, ge=0, le=5)
    actionability: int = Field(default=0, ge=0, le=5)
    professional_expression: int = Field(default=0, ge=0, le=5)

    @property
    def completed(self) -> bool:
        return all(getattr(self, key) >= 1 for key in DIMENSIONS)


class ExpertCalibrationCaseContext(BaseModel):
    case_id: str
    suite_id: str
    category: str
    keyword: str
    research_focus: str
    regions: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    required_sections: list[str] = Field(default_factory=list)


class ExpertReviewAssignment(BaseModel):
    assignment_id: str
    case_id: str
    review_round: AssignmentRound
    blind_reviewer_id: str = ""
    reviewer_domain: str = ""
    decision: ExpertDecision = "pending"
    ratings: ExpertDimensionRatings = Field(default_factory=ExpertDimensionRatings)
    notes: str = ""
    completed_at: datetime | None = None


class AutoJudgeCalibrationAssessment(BaseModel):
    case_id: str
    decision: ExpertDecision = "pending"
    overall_score: int = Field(default=0, ge=0, le=100)
    dimension_scores: ExpertDimensionRatings = Field(default_factory=ExpertDimensionRatings)
    hard_failure_codes: list[str] = Field(default_factory=list)
    judge_model: str = ""
    prompt_version: str = ""
    evaluated_at: datetime | None = None


class CalibrationCaseQualityAudit(BaseModel):
    """Independent review of the post-2.5.0 evidence and delivery contract."""

    case_id: str
    reviewer_id: str = ""
    source_topology_status: Literal["pending", "pass", "fail"] = "pending"
    source_topology_qrel_digest: str = ""
    source_topology_qrel_count: int = Field(default=0, ge=0)
    entity_precision_percent: float = Field(default=0.0, ge=0, le=100)
    local_target_precision_percent: float = Field(default=0.0, ge=0, le=100)
    external_benchmark_leak_count: int = Field(default=0, ge=0)
    formal_classification_correct: bool = False
    account_pursuit_score: int = Field(default=0, ge=0, le=5)
    architecture_traceability_score: int = Field(default=0, ge=0, le=5)
    model_arm: str = ""
    prompt_arm: str = ""
    evidence_snapshot_digest: str = ""
    notes: str = ""
    reviewed_at: datetime | None = None

    @property
    def completed(self) -> bool:
        return bool(
            self.reviewer_id.strip()
            and self.source_topology_status in {"pass", "fail"}
            and self.source_topology_qrel_digest.strip()
            and self.source_topology_qrel_count >= 1
            and self.account_pursuit_score >= 1
            and self.architecture_traceability_score >= 1
            and self.model_arm.strip()
            and self.prompt_arm.strip()
            and self.evidence_snapshot_digest.strip()
            and len(self.notes.strip()) >= 12
            and self.reviewed_at
        )


class PairedModelPromptEvaluation(BaseModel):
    case_id: str
    evidence_snapshot_digest: str = ""
    baseline_model: str = ""
    candidate_model: str = ""
    baseline_prompt_version: str = ""
    candidate_prompt_version: str = ""
    preferred_arm: Literal["pending", "baseline", "candidate", "tie"] = "pending"
    reviewer_id: str = ""
    rationale: str = ""
    reviewed_at: datetime | None = None

    @property
    def completed(self) -> bool:
        return bool(
            self.evidence_snapshot_digest.strip()
            and self.baseline_model.strip()
            and self.candidate_model.strip()
            and self.baseline_prompt_version.strip()
            and self.candidate_prompt_version.strip()
            and self.preferred_arm != "pending"
            and self.reviewer_id.strip()
            and len(self.rationale.strip()) >= 12
            and self.reviewed_at
        )


class CustomerAcceptanceSample(BaseModel):
    sample_id: str
    case_id: str
    sector: str = ""
    customer_reviewer_id: str = ""
    acceptance: Literal["pending", "accepted", "changes_requested"] = "pending"
    feedback: str = ""
    attestation: str = ""
    reviewed_at: datetime | None = None

    @property
    def completed(self) -> bool:
        return bool(
            self.sector.strip()
            and self.customer_reviewer_id.strip()
            and self.acceptance != "pending"
            and len(self.feedback.strip()) >= 12
            and len(self.attestation.strip()) >= 24
            and self.reviewed_at
        )


class ExpertReviewArbitration(BaseModel):
    case_id: str
    status: Literal["pending", "resolved"] = "pending"
    arbitrator_id: str = ""
    final_decision: ExpertDecision = "pending"
    final_ratings: ExpertDimensionRatings = Field(default_factory=ExpertDimensionRatings)
    rationale: str = ""
    resolved_at: datetime | None = None


class ExpertCalibrationArtifact(BaseModel):
    framework: Literal["research_expert_calibration_v1"] = "research_expert_calibration_v1"
    dataset_id: str
    dataset_version: str
    dataset_content_sha256: str
    rubric_version: str = "research-deliverability-rubric-v2.5.0"
    status: CalibrationStatus = "pending"
    dual_review_case_ids: list[str] = Field(default_factory=list)
    case_contexts: list[ExpertCalibrationCaseContext] = Field(default_factory=list)
    assignments: list[ExpertReviewAssignment] = Field(default_factory=list)
    auto_judge_assessments: list[AutoJudgeCalibrationAssessment] = Field(default_factory=list)
    quality_audits: list[CalibrationCaseQualityAudit] = Field(default_factory=list)
    paired_model_prompt_evaluations: list[PairedModelPromptEvaluation] = Field(default_factory=list)
    customer_acceptance_samples: list[CustomerAcceptanceSample] = Field(default_factory=list)
    arbitrations: list[ExpertReviewArbitration] = Field(default_factory=list)
    reviewer_attestations: dict[str, str] = Field(default_factory=dict)
    finalized_at: datetime | None = None
    content_sha256: str = ""

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


class ExpertCalibrationValidation(BaseModel):
    dataset_id: str
    dataset_version: str
    status: CalibrationStatus
    case_count: int = 0
    primary_completed: int = 0
    dual_review_completed: int = 0
    arbitration_required: int = 0
    arbitration_completed: int = 0
    auto_judge_completed: int = 0
    quality_audit_completed: int = 0
    paired_model_prompt_completed: int = 0
    customer_acceptance_completed: int = 0
    customer_acceptance_sectors: int = 0
    human_undeliverable_count: int = 0
    auto_gate_undeliverable_recall: float = 0.0
    inter_reviewer_agreement: float = 0.0
    dimension_averages: dict[str, float] = Field(default_factory=dict)
    auto_judge_dimension_bias: dict[str, float] = Field(default_factory=dict)
    hard_failure_cap_violations: int = 0
    entity_precision_percent: float = 0.0
    local_target_precision_percent: float = 0.0
    external_benchmark_leak_count: int = 0
    formal_classification_error_count: int = 0
    account_pursuit_average: float = 0.0
    architecture_traceability_average: float = 0.0
    calibration_complete: bool = False
    blockers: list[str] = Field(default_factory=list)


def expert_calibration_content_sha256(artifact: ExpertCalibrationArtifact) -> str:
    payload = artifact.model_dump(mode="json", exclude={"content_sha256"})
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _dual_review_case_ids(cases: list[ResearchEvaluationCase]) -> list[str]:
    by_suite: dict[str, list[str]] = {}
    for case in cases:
        by_suite.setdefault(case.suite_id, []).append(case.case_id)
    selected = [case_id for suite_ids in by_suite.values() for case_id in sorted(suite_ids)[:3]]
    if len(selected) < 30:
        selected.extend(case.case_id for case in cases if case.case_id not in selected)
    return selected[:30]


def build_expert_calibration_template(
    manifest: ResearchEvaluationDatasetManifest,
    cases: list[ResearchEvaluationCase],
) -> ExpertCalibrationArtifact:
    dual_case_ids = _dual_review_case_ids(cases)
    assignments = [
        ExpertReviewAssignment(
            assignment_id=f"{case.case_id}:primary",
            case_id=case.case_id,
            review_round="primary",
        )
        for case in cases
    ]
    assignments.extend(
        ExpertReviewAssignment(
            assignment_id=f"{case_id}:secondary",
            case_id=case_id,
            review_round="secondary",
        )
        for case_id in dual_case_ids
    )
    return ExpertCalibrationArtifact(
        dataset_id=manifest.dataset_id,
        dataset_version=manifest.version,
        dataset_content_sha256=manifest.content_sha256,
        dual_review_case_ids=dual_case_ids,
        case_contexts=[
            ExpertCalibrationCaseContext(
                case_id=case.case_id,
                suite_id=case.suite_id,
                category=case.category,
                keyword=case.keyword,
                research_focus=case.research_focus,
                regions=list(case.regions),
                entities=list(case.entities),
                required_sections=list(case.required_sections),
            )
            for case in cases
        ],
        assignments=assignments,
        auto_judge_assessments=[AutoJudgeCalibrationAssessment(case_id=case.case_id) for case in cases],
        quality_audits=[CalibrationCaseQualityAudit(case_id=case.case_id) for case in cases],
        paired_model_prompt_evaluations=[
            PairedModelPromptEvaluation(case_id=case_id)
            for case_id in dual_case_ids
        ],
        customer_acceptance_samples=[
            CustomerAcceptanceSample(sample_id=f"customer-{index + 1}", case_id=case_id)
            for index, case_id in enumerate(dual_case_ids[:3])
        ],
        arbitrations=[ExpertReviewArbitration(case_id=case_id) for case_id in dual_case_ids],
    )


def _assignment_complete(assignment: ExpertReviewAssignment) -> bool:
    return bool(
        assignment.decision != "pending"
        and assignment.ratings.completed
        and assignment.blind_reviewer_id.strip()
        and assignment.reviewer_domain.strip()
        and len(assignment.notes.strip()) >= 12
        and assignment.completed_at
    )


def _auto_assessment_complete(assessment: AutoJudgeCalibrationAssessment) -> bool:
    return bool(
        assessment.decision != "pending"
        and assessment.dimension_scores.completed
        and assessment.judge_model.strip()
        and assessment.prompt_version.strip()
        and assessment.evaluated_at
    )


def _ratings_disagree(first: ExpertDimensionRatings, second: ExpertDimensionRatings) -> bool:
    return any(abs(getattr(first, key) - getattr(second, key)) >= 2 for key in DIMENSIONS)


def validate_expert_calibration(
    manifest: ResearchEvaluationDatasetManifest,
    cases: list[ResearchEvaluationCase],
    artifact: ExpertCalibrationArtifact,
) -> ExpertCalibrationValidation:
    blockers: list[str] = []
    expected_ids = {case.case_id for case in cases}
    expected_dual_ids = set(_dual_review_case_ids(cases))
    context_ids = [context.case_id for context in artifact.case_contexts]
    if artifact.dataset_id != manifest.dataset_id or artifact.dataset_version != manifest.version:
        blockers.append("calibration dataset identity does not match the locked dataset")
    if artifact.dataset_content_sha256 != manifest.content_sha256:
        blockers.append("calibration dataset digest does not match the locked dataset")
    if set(context_ids) != expected_ids or len(context_ids) != len(set(context_ids)):
        blockers.append("calibration case contexts must match all 100 locked cases exactly once")
    if set(artifact.dual_review_case_ids) != expected_dual_ids:
        blockers.append("dual-review assignment must contain the deterministic 30-case stratified sample")

    primary = {row.case_id: row for row in artifact.assignments if row.review_round == "primary"}
    secondary = {row.case_id: row for row in artifact.assignments if row.review_round == "secondary"}
    if set(primary) != expected_ids:
        blockers.append("primary review assignments must cover all 100 locked cases")
    if set(secondary) != expected_dual_ids:
        blockers.append("secondary blind review assignments must cover exactly 30 stratified cases")
    if len(artifact.assignments) != len({row.assignment_id for row in artifact.assignments}):
        blockers.append("calibration contains duplicate assignment IDs")

    completed_primary = {key: value for key, value in primary.items() if _assignment_complete(value)}
    completed_secondary = {key: value for key, value in secondary.items() if _assignment_complete(value)}
    if len(completed_primary) != len(cases):
        blockers.append(f"primary expert review is incomplete: {len(completed_primary)}/{len(cases)}")
    if len(completed_secondary) < 30:
        blockers.append(f"secondary blind review is incomplete: {len(completed_secondary)}/30")

    same_reviewer_cases = [
        case_id
        for case_id in expected_dual_ids
        if case_id in primary
        and case_id in secondary
        and primary[case_id].blind_reviewer_id.strip()
        and primary[case_id].blind_reviewer_id.strip() == secondary[case_id].blind_reviewer_id.strip()
    ]
    if same_reviewer_cases:
        blockers.append(f"{len(same_reviewer_cases)} dual-review cases use the same reviewer in both blind slots")

    arbitration_by_case = {row.case_id: row for row in artifact.arbitrations}
    required_arbitrations: set[str] = set()
    agreeing = 0
    comparable = 0
    for case_id in expected_dual_ids:
        first = completed_primary.get(case_id)
        second = completed_secondary.get(case_id)
        if not first or not second:
            continue
        comparable += 1
        if first.decision == second.decision:
            agreeing += 1
        if first.decision != second.decision or _ratings_disagree(first.ratings, second.ratings):
            required_arbitrations.add(case_id)
    completed_arbitrations = {
        case_id
        for case_id in required_arbitrations
        if case_id in arbitration_by_case
        and arbitration_by_case[case_id].status == "resolved"
        and arbitration_by_case[case_id].final_decision != "pending"
        and arbitration_by_case[case_id].final_ratings.completed
        and arbitration_by_case[case_id].arbitrator_id.strip()
        and len(arbitration_by_case[case_id].rationale.strip()) >= 12
        and arbitration_by_case[case_id].resolved_at
    }
    if completed_arbitrations != required_arbitrations:
        blockers.append(
            f"blind-review arbitration is incomplete: {len(completed_arbitrations)}/{len(required_arbitrations)}"
        )

    human_ratings: list[ExpertDimensionRatings] = []
    human_decisions: dict[str, ExpertDecision] = {}
    for case_id in expected_ids:
        row = completed_primary.get(case_id)
        if not row:
            continue
        arbitration = arbitration_by_case.get(case_id)
        if case_id in required_arbitrations and arbitration and case_id in completed_arbitrations:
            human_ratings.append(arbitration.final_ratings)
            human_decisions[case_id] = arbitration.final_decision
        else:
            human_ratings.append(row.ratings)
            human_decisions[case_id] = row.decision
    dimension_averages = {
        key: round(fmean(getattr(row, key) for row in human_ratings), 3) if human_ratings else 0.0
        for key in DIMENSIONS
    }
    if human_ratings:
        overall_expert_average = fmean(dimension_averages.values())
        if overall_expert_average < 4.0:
            blockers.append(f"expert five-dimension average is {overall_expert_average:.3f}, expected >= 4.0")
        low_dimensions = [key for key, value in dimension_averages.items() if value < 3.5]
        if low_dimensions:
            blockers.append("expert dimensions below 3.5: " + ", ".join(low_dimensions))

    auto_rows = {
        row.case_id: row for row in artifact.auto_judge_assessments if _auto_assessment_complete(row)
    }
    if len(auto_rows) != len(cases):
        blockers.append(f"auto-judge calibration assessments are incomplete: {len(auto_rows)}/{len(cases)}")
    human_undeliverable = {
        case_id for case_id, decision in human_decisions.items() if decision == "undeliverable"
    }
    caught = sum(auto_rows.get(case_id) is not None and auto_rows[case_id].decision == "undeliverable" for case_id in human_undeliverable)
    recall = caught / len(human_undeliverable) if human_undeliverable else 0.0
    if human_decisions and not human_undeliverable:
        blockers.append("calibration set has no expert-labeled undeliverable cases")
    elif human_undeliverable and recall < 0.95:
        blockers.append(f"automatic undeliverable recall is {recall:.3f}, expected >= 0.95")

    audits_by_case = {row.case_id: row for row in artifact.quality_audits}
    if set(audits_by_case) != expected_ids or len(artifact.quality_audits) != len(audits_by_case):
        blockers.append("quality audits must cover all 100 locked cases exactly once")
    completed_audits = {
        case_id: row
        for case_id, row in audits_by_case.items()
        if row.completed
    }
    if len(completed_audits) != len(cases):
        blockers.append(f"post-2.5 quality audits are incomplete: {len(completed_audits)}/{len(cases)}")
    audit_rows = list(completed_audits.values())
    entity_precision = fmean(row.entity_precision_percent for row in audit_rows) if audit_rows else 0.0
    local_target_precision = fmean(row.local_target_precision_percent for row in audit_rows) if audit_rows else 0.0
    benchmark_leaks = sum(row.external_benchmark_leak_count for row in audit_rows)
    classification_errors = sum(not row.formal_classification_correct for row in audit_rows)
    account_pursuit_average = fmean(row.account_pursuit_score for row in audit_rows) if audit_rows else 0.0
    architecture_traceability_average = (
        fmean(row.architecture_traceability_score for row in audit_rows) if audit_rows else 0.0
    )
    topology_failures = sum(row.source_topology_status != "pass" for row in audit_rows)
    audited_categories = {
        next((case.category for case in cases if case.case_id == case_id), "")
        for case_id in completed_audits
    }
    if audit_rows and entity_precision < 99.0:
        blockers.append(f"entity precision is {entity_precision:.2f}%, expected >= 99.00%")
    if audit_rows and local_target_precision < 90.0:
        blockers.append(f"local target proof precision is {local_target_precision:.2f}%, expected >= 90.00%")
    if benchmark_leaks:
        blockers.append(f"external benchmark leakage count is {benchmark_leaks}, expected 0")
    if classification_errors:
        blockers.append(f"formal/provisional classification errors are {classification_errors}, expected 0")
    if topology_failures:
        blockers.append(f"source topology audit failures are {topology_failures}, expected 0")
    qrel_digests = {
        row.source_topology_qrel_digest.strip()
        for row in audit_rows
        if row.source_topology_qrel_digest.strip()
    }
    qrel_rows = sum(row.source_topology_qrel_count for row in audit_rows)
    if audit_rows and len(qrel_digests) != len(cases):
        blockers.append(
            f"source topology qrel digests are not case-distinct: {len(qrel_digests)}/{len(cases)}"
        )
    if audit_rows and qrel_rows < len(cases):
        blockers.append(f"source topology qrel rows are incomplete: {qrel_rows}/{len(cases)}")
    if audit_rows and account_pursuit_average < 4.0:
        blockers.append(f"account pursuit review average is {account_pursuit_average:.3f}, expected >= 4.0")
    if audit_rows and architecture_traceability_average < 4.0:
        blockers.append(
            f"architecture traceability review average is {architecture_traceability_average:.3f}, expected >= 4.0"
        )
    if audit_rows and len(audited_categories - {""}) < 6:
        blockers.append("quality audit corpus must cover at least six industry categories")

    paired_by_case = {row.case_id: row for row in artifact.paired_model_prompt_evaluations}
    if set(paired_by_case) != expected_dual_ids or len(artifact.paired_model_prompt_evaluations) != len(paired_by_case):
        blockers.append("paired model/prompt evaluations must cover the deterministic 30-case blind sample")
    completed_pairs = {
        case_id: row
        for case_id, row in paired_by_case.items()
        if row.completed
    }
    if len(completed_pairs) != len(expected_dual_ids):
        blockers.append(f"paired model/prompt evaluations are incomplete: {len(completed_pairs)}/30")
    same_arm_pairs = [
        case_id
        for case_id, row in completed_pairs.items()
        if row.baseline_model == row.candidate_model
        and row.baseline_prompt_version == row.candidate_prompt_version
    ]
    if same_arm_pairs:
        blockers.append(f"{len(same_arm_pairs)} paired evaluations compare identical model and prompt arms")

    completed_customer_samples = [
        sample for sample in artifact.customer_acceptance_samples if sample.completed
    ]
    accepted_customer_samples = [
        sample for sample in completed_customer_samples if sample.acceptance == "accepted"
    ]
    customer_sectors = {sample.sector.strip() for sample in accepted_customer_samples if sample.sector.strip()}
    customer_reviewers = {
        sample.customer_reviewer_id.strip()
        for sample in accepted_customer_samples
        if sample.customer_reviewer_id.strip()
    }
    if len(accepted_customer_samples) < 3:
        blockers.append(f"customer acceptance samples are incomplete: {len(accepted_customer_samples)}/3 accepted")
    if len(customer_sectors) < 3:
        blockers.append("customer acceptance samples must span three independent sectors")
    if len(customer_reviewers) < 3:
        blockers.append("customer acceptance samples must use three distinct customer-side reviewers")

    auto_bias: dict[str, float] = {}
    paired_ids = [case_id for case_id in human_decisions if case_id in auto_rows and case_id in completed_primary]
    for key in DIMENSIONS:
        deltas: list[float] = []
        for case_id in paired_ids:
            human_rating = (
                arbitration_by_case[case_id].final_ratings
                if case_id in required_arbitrations and case_id in completed_arbitrations
                else completed_primary[case_id].ratings
            )
            deltas.append(getattr(auto_rows[case_id].dimension_scores, key) - getattr(human_rating, key))
        auto_bias[key] = round(fmean(deltas), 3) if deltas else 0.0

    cap_violations = 0
    for assessment in auto_rows.values():
        applicable_caps = [HARD_FAILURE_CAPS[code] for code in assessment.hard_failure_codes if code in HARD_FAILURE_CAPS]
        if applicable_caps and (
            assessment.overall_score > min(applicable_caps) or assessment.decision != "undeliverable"
        ):
            cap_violations += 1
    if cap_violations:
        blockers.append(f"{cap_violations} auto-judge rows violate hard-failure score caps")

    reviewer_ids = {
        assignment.blind_reviewer_id.strip()
        for assignment in artifact.assignments
        if _assignment_complete(assignment)
    }
    missing_attestations = [
        reviewer_id
        for reviewer_id in reviewer_ids
        if len(artifact.reviewer_attestations.get(reviewer_id, "").strip()) < 24
    ]
    if missing_attestations:
        blockers.append(f"{len(missing_attestations)} expert reviewers lack substantive attestations")
    if customer_reviewers & reviewer_ids:
        blockers.append("customer acceptance reviewers must be independent from expert blind reviewers")
    if artifact.status != "calibrated":
        blockers.append(f"calibration status is {artifact.status}, expected calibrated")
    if artifact.finalized_at is None:
        blockers.append("calibration finalized_at is required")
    expected_digest = expert_calibration_content_sha256(artifact)
    if not artifact.content_sha256 or artifact.content_sha256 != expected_digest:
        blockers.append("calibration content digest is missing or invalid")

    return ExpertCalibrationValidation(
        dataset_id=manifest.dataset_id,
        dataset_version=manifest.version,
        status=artifact.status,
        case_count=len(cases),
        primary_completed=len(completed_primary),
        dual_review_completed=len(completed_secondary),
        arbitration_required=len(required_arbitrations),
        arbitration_completed=len(completed_arbitrations),
        auto_judge_completed=len(auto_rows),
        quality_audit_completed=len(completed_audits),
        paired_model_prompt_completed=len(completed_pairs),
        customer_acceptance_completed=len(accepted_customer_samples),
        customer_acceptance_sectors=len(customer_sectors),
        human_undeliverable_count=len(human_undeliverable),
        auto_gate_undeliverable_recall=round(recall, 4),
        inter_reviewer_agreement=round(agreeing / comparable, 4) if comparable else 0.0,
        dimension_averages=dimension_averages,
        auto_judge_dimension_bias=auto_bias,
        hard_failure_cap_violations=cap_violations,
        entity_precision_percent=round(entity_precision, 3),
        local_target_precision_percent=round(local_target_precision, 3),
        external_benchmark_leak_count=benchmark_leaks,
        formal_classification_error_count=classification_errors,
        account_pursuit_average=round(account_pursuit_average, 3),
        architecture_traceability_average=round(architecture_traceability_average, 3),
        calibration_complete=not blockers,
        blockers=blockers,
    )


def finalize_expert_calibration(artifact: ExpertCalibrationArtifact) -> ExpertCalibrationArtifact:
    artifact.status = "calibrated"
    artifact.finalized_at = datetime.now(timezone.utc)
    artifact.content_sha256 = expert_calibration_content_sha256(artifact)
    return artifact
