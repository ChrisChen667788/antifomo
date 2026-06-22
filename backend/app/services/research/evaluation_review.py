from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.services.research.evaluation_dataset import (
    ResearchEvaluationCase,
    ResearchEvaluationDatasetManifest,
)


ReviewDecision = Literal["pending", "approved", "changes_requested"]
ReviewStatus = Literal["pending", "approved", "changes_requested"]


class ResearchEvaluationCaseReview(BaseModel):
    case_id: str
    suite_id: str
    keyword: str
    research_focus: str
    regions: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    expected_behavior: str
    reference_answer_terms: list[str]
    expected_source_domains: list[str]
    curation_notes: str
    source_relevance_notes: str
    decision: ReviewDecision = "pending"
    notes: str = ""


class ResearchEvaluationReviewArtifact(BaseModel):
    dataset_id: str
    dataset_version: str
    dataset_content_sha256: str
    review_status: ReviewStatus = "pending"
    reviewer_name: str = ""
    reviewer_role: str = ""
    reviewed_at: date | None = None
    attestation: str = ""
    review_content_sha256: str = ""
    cases: list[ResearchEvaluationCaseReview]

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


class ResearchEvaluationReviewValidation(BaseModel):
    dataset_id: str
    dataset_version: str
    review_status: ReviewStatus
    case_count: int
    approved_case_count: int
    changes_requested_case_count: int
    pending_case_count: int
    independent_review_complete: bool
    blockers: list[str] = Field(default_factory=list)


def research_evaluation_review_content_sha256(
    artifact: ResearchEvaluationReviewArtifact,
) -> str:
    payload = artifact.model_dump(mode="json", exclude={"review_content_sha256"})
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_research_evaluation_review_template(
    manifest: ResearchEvaluationDatasetManifest,
    cases: list[ResearchEvaluationCase],
) -> ResearchEvaluationReviewArtifact:
    return ResearchEvaluationReviewArtifact(
        dataset_id=manifest.dataset_id,
        dataset_version=manifest.version,
        dataset_content_sha256=manifest.content_sha256,
        cases=[
            ResearchEvaluationCaseReview(
                case_id=case.case_id,
                suite_id=case.suite_id,
                keyword=case.keyword,
                research_focus=case.research_focus,
                regions=list(case.regions),
                entities=list(case.entities),
                expected_behavior=case.expected_behavior,
                reference_answer_terms=list(case.reference_answer_terms),
                expected_source_domains=list(case.expected_source_domains),
                curation_notes=case.curation_notes,
                source_relevance_notes=case.source_relevance_notes,
            )
            for case in cases
        ],
    )


def finalize_research_evaluation_review(
    artifact: ResearchEvaluationReviewArtifact,
    *,
    reviewer_name: str,
    reviewer_role: str,
    attestation: str,
    reviewed_at: date | None = None,
) -> ResearchEvaluationReviewArtifact:
    decisions = {case.decision for case in artifact.cases}
    artifact.review_status = "approved" if decisions == {"approved"} else "changes_requested"
    artifact.reviewer_name = reviewer_name.strip()
    artifact.reviewer_role = reviewer_role.strip()
    artifact.reviewed_at = reviewed_at or datetime.now(timezone.utc).date()
    artifact.attestation = attestation.strip()
    artifact.review_content_sha256 = research_evaluation_review_content_sha256(artifact)
    return artifact


def validate_research_evaluation_review(
    manifest: ResearchEvaluationDatasetManifest,
    cases: list[ResearchEvaluationCase],
    artifact: ResearchEvaluationReviewArtifact,
) -> ResearchEvaluationReviewValidation:
    expected_case_ids = {case.case_id for case in cases}
    review_case_ids = [case.case_id for case in artifact.cases]
    blockers: list[str] = []
    if artifact.dataset_id != manifest.dataset_id or artifact.dataset_version != manifest.version:
        blockers.append("review dataset identity does not match the locked dataset")
    if artifact.dataset_content_sha256 != manifest.content_sha256:
        blockers.append("review dataset digest does not match the locked dataset")
    if len(review_case_ids) != len(set(review_case_ids)):
        blockers.append("review contains duplicate case IDs")
    missing = sorted(expected_case_ids - set(review_case_ids))
    unexpected = sorted(set(review_case_ids) - expected_case_ids)
    if missing:
        blockers.append(f"review is missing {len(missing)} locked cases")
    if unexpected:
        blockers.append(f"review contains {len(unexpected)} unexpected cases")
    expected_context = {
        case.case_id: (
            case.suite_id,
            case.keyword,
            case.research_focus,
            case.regions,
            case.entities,
            case.expected_behavior,
            case.reference_answer_terms,
            case.expected_source_domains,
            case.curation_notes,
            case.source_relevance_notes,
        )
        for case in cases
    }
    altered_context = [
        case.case_id
        for case in artifact.cases
        if case.case_id in expected_context
        and (
            case.suite_id,
            case.keyword,
            case.research_focus,
            case.regions,
            case.entities,
            case.expected_behavior,
            case.reference_answer_terms,
            case.expected_source_domains,
            case.curation_notes,
            case.source_relevance_notes,
        )
        != expected_context[case.case_id]
    ]
    if altered_context:
        blockers.append(f"review changed locked context for {len(altered_context)} cases")
    if artifact.review_status != "approved":
        blockers.append(f"review status is {artifact.review_status}, expected approved")
    if not artifact.reviewer_name.strip() or not artifact.reviewer_role.strip():
        blockers.append("reviewer name and role are required")
    if artifact.reviewer_name.strip().casefold() == manifest.locked_by.strip().casefold():
        blockers.append("independent reviewer must differ from the dataset locker")
    if artifact.reviewed_at is None:
        blockers.append("reviewed_at is required")
    if len(artifact.attestation.strip()) < 24:
        blockers.append("independent review attestation is too short")
    non_approved = [case for case in artifact.cases if case.decision != "approved"]
    if non_approved:
        blockers.append(f"{len(non_approved)} cases are not approved")
    incomplete_notes = [case for case in artifact.cases if len(case.notes.strip()) < 8]
    if incomplete_notes:
        blockers.append(f"{len(incomplete_notes)} cases require substantive review notes")
    expected_digest = research_evaluation_review_content_sha256(artifact)
    if not artifact.review_content_sha256 or artifact.review_content_sha256 != expected_digest:
        blockers.append("review content digest is missing or invalid; finalize the review again")

    approved = sum(case.decision == "approved" for case in artifact.cases)
    changes_requested = sum(case.decision == "changes_requested" for case in artifact.cases)
    pending = sum(case.decision == "pending" for case in artifact.cases)
    return ResearchEvaluationReviewValidation(
        dataset_id=manifest.dataset_id,
        dataset_version=manifest.version,
        review_status=artifact.review_status,
        case_count=len(artifact.cases),
        approved_case_count=approved,
        changes_requested_case_count=changes_requested,
        pending_case_count=pending,
        independent_review_complete=not blockers,
        blockers=blockers,
    )
