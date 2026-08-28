from __future__ import annotations

from datetime import UTC, datetime

from app.schemas.research import (
    ResearchCitationGateOut,
    ResearchEvidenceGateOut,
    ResearchReportResponse,
    ResearchSourceDiagnosticsOut,
)
from app.services.research.evaluation_dataset import DATASET_PATH, load_research_evaluation_dataset
from app.services.research.expert_calibration import (
    ExpertDimensionRatings,
    build_expert_calibration_template,
    expert_calibration_content_sha256,
    finalize_expert_calibration,
    validate_expert_calibration,
)
from app.services.research.hard_failure_policy import evaluate_research_hard_failures


def test_expert_calibration_template_has_100_primary_and_30_blind_reviews() -> None:
    manifest, cases = load_research_evaluation_dataset(DATASET_PATH)
    artifact = build_expert_calibration_template(manifest, cases)

    assert len(artifact.case_contexts) == 100
    assert sum(row.review_round == "primary" for row in artifact.assignments) == 100
    assert sum(row.review_round == "secondary" for row in artifact.assignments) == 30
    assert len(artifact.dual_review_case_ids) == 30
    assert all("expected_behavior" not in row.model_dump() for row in artifact.case_contexts)

    result = validate_expert_calibration(manifest, cases, artifact)
    assert result.calibration_complete is False
    assert result.primary_completed == 0
    assert any("primary expert review is incomplete" in blocker for blocker in result.blockers)


def test_completed_expert_calibration_computes_recall_agreement_and_bias() -> None:
    manifest, cases = load_research_evaluation_dataset(DATASET_PATH)
    artifact = build_expert_calibration_template(manifest, cases)
    case_by_id = {case.case_id: case for case in cases}
    now = datetime(2026, 7, 13, tzinfo=UTC)
    ratings = ExpertDimensionRatings(
        accuracy=4,
        completeness=4,
        insight=4,
        actionability=4,
        professional_expression=4,
    )
    for assignment in artifact.assignments:
        assignment.blind_reviewer_id = "expert-a" if assignment.review_round == "primary" else "expert-b"
        assignment.reviewer_domain = case_by_id[assignment.case_id].category
        assignment.decision = (
            "deliverable" if case_by_id[assignment.case_id].expected_behavior == "answer" else "undeliverable"
        )
        assignment.ratings = ratings.model_copy(deep=True)
        assignment.notes = "已按范围、证据、引用、洞察和可执行性完成独立盲评。"
        assignment.completed_at = now
    for assessment in artifact.auto_judge_assessments:
        expected = case_by_id[assessment.case_id].expected_behavior
        assessment.decision = "deliverable" if expected == "answer" else "undeliverable"
        assessment.overall_score = 80 if expected == "answer" else 20
        assessment.dimension_scores = ratings.model_copy(deep=True)
        assessment.hard_failure_codes = [] if expected == "answer" else ["topic_mismatch"]
        assessment.judge_model = "deterministic-test-judge"
        assessment.prompt_version = "rubric-v1.8.4"
        assessment.evaluated_at = now
    for audit in artifact.quality_audits:
        audit.reviewer_id = "quality-expert"
        audit.source_topology_status = "pass"
        audit.source_topology_qrel_digest = f"qrel-{audit.case_id}"
        audit.source_topology_qrel_count = 1
        audit.entity_precision_percent = 100
        audit.local_target_precision_percent = 100
        audit.external_benchmark_leak_count = 0
        audit.formal_classification_correct = True
        audit.account_pursuit_score = 4
        audit.architecture_traceability_score = 4
        audit.model_arm = "baseline-model"
        audit.prompt_arm = "research-rubric-v2.5.0"
        audit.evidence_snapshot_digest = f"snapshot-{audit.case_id}"
        audit.notes = "已复核来源拓扑、实体真值、账户推进、方案追溯与交付状态。"
        audit.reviewed_at = now
    for pair in artifact.paired_model_prompt_evaluations:
        pair.evidence_snapshot_digest = f"snapshot-{pair.case_id}"
        pair.baseline_model = "baseline-model"
        pair.candidate_model = "candidate-model"
        pair.baseline_prompt_version = "research-rubric-v2.4.2"
        pair.candidate_prompt_version = "research-rubric-v2.5.0"
        pair.preferred_arm = "candidate"
        pair.reviewer_id = "quality-expert"
        pair.rationale = "在相同固定证据集下完成成对比较，候选版本的事实与假设边界更清晰。"
        pair.reviewed_at = now
    for index, sample in enumerate(artifact.customer_acceptance_samples, start=1):
        sample.sector = ["政府", "文旅", "医疗"][index - 1]
        sample.customer_reviewer_id = f"customer-reviewer-{index}"
        sample.acceptance = "accepted"
        sample.feedback = "客户侧确认材料清楚地区分了事实、假设、待核验项和下一步动作。"
        sample.attestation = "本人代表客户侧独立完成材料可用性评审，未参与模型或提示词开发。"
        sample.reviewed_at = now
    artifact.reviewer_attestations = {
        "expert-a": "本人独立完成主评，未接触另一评审结论或自动裁判输出。",
        "expert-b": "本人独立完成双盲复评，未接触主评结论或自动裁判输出。",
    }
    finalize_expert_calibration(artifact)
    artifact.content_sha256 = expert_calibration_content_sha256(artifact)

    result = validate_expert_calibration(manifest, cases, artifact)

    assert result.calibration_complete is True
    assert result.primary_completed == 100
    assert result.dual_review_completed == 30
    assert result.inter_reviewer_agreement == 1.0
    assert result.auto_gate_undeliverable_recall == 1.0
    assert result.hard_failure_cap_violations == 0
    assert result.quality_audit_completed == 100
    assert result.paired_model_prompt_completed == 30
    assert result.customer_acceptance_completed == 3
    assert result.entity_precision_percent == 100
    assert set(result.dimension_averages) == {
        "accuracy",
        "completeness",
        "insight",
        "actionability",
        "professional_expression",
    }


def test_hard_failure_policy_applies_the_strictest_cap() -> None:
    now = datetime(2026, 7, 13, tzinfo=UTC)
    report = ResearchReportResponse(
        keyword="医疗AI",
        report_title="错误主题报告",
        executive_summary="无支撑关键主张。",
        consulting_angle="不得交付。",
        source_count=0,
        research_evidence_gate=ResearchEvidenceGateOut(
            enforced=True,
            status="blocked_topic_mismatch",
            passed=False,
            blockers=["主题错位"],
        ),
        research_citation_gate=ResearchCitationGateOut(
            enforced=True,
            status="fail",
            passed=False,
            blockers=["关键主张无证据"],
        ),
        generated_at=now,
    )

    result = evaluate_research_hard_failures(report)

    assert now.tzinfo is UTC
    assert result.blocked is True
    assert result.score_cap == 20
    assert result.cap_score(96) == 20
    assert result.failure_codes == ("topic_mismatch", "unsupported_critical_claim")


def test_hard_failure_policy_blocks_deterministic_generation_fallback() -> None:
    report = ResearchReportResponse(
        keyword="长三角文旅文博人工智能",
        report_title="长三角文旅文博人工智能机会研判",
        executive_summary="当前为降级草稿。",
        consulting_angle="等待正式模型恢复后重新生成。",
        source_count=6,
        generated_at=datetime(2026, 7, 14, tzinfo=UTC),
        source_diagnostics=ResearchSourceDiagnosticsOut(
            generation_provider="mock",
            generation_model="deterministic-mock",
            generation_status="fallback",
            generation_fallback_used=True,
            generation_notes=["正式研报模型超时，当前为降级草稿。"],
        ),
    )

    result = evaluate_research_hard_failures(report)

    assert result.blocked is True
    assert result.score_cap == 45
    assert result.failure_codes == ("generation_fallback",)
