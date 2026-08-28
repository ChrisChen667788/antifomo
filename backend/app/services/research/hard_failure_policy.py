from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.services.research.delivery_scope import requires_account_truth


HardFailureCode = Literal[
    "topic_mismatch",
    "minimum_evidence_failed",
    "unsupported_critical_claim",
    "generation_fallback",
    "unverified_account_truth",
    "source_topology_failed",
]


@dataclass(frozen=True, slots=True)
class ResearchHardFailureAssessment:
    blocked: bool
    score_cap: int
    failure_codes: tuple[HardFailureCode, ...]
    reasons: tuple[str, ...]

    def cap_score(self, score: int | float) -> int:
        return max(0, min(round(float(score)), self.score_cap))


def _is_enforced_failure(gate: Any) -> bool:
    return bool(gate and getattr(gate, "enforced", False) and not getattr(gate, "passed", False))


def evaluate_research_hard_failures(report: Any) -> ResearchHardFailureAssessment:
    """Return the single fail-closed score policy used by every delivery surface."""

    evidence_gate = getattr(report, "research_evidence_gate", None)
    citation_gate = getattr(report, "research_citation_gate", None)
    score_cap = 100
    failure_codes: list[HardFailureCode] = []
    reasons: list[str] = []

    if _is_enforced_failure(evidence_gate):
        if getattr(evidence_gate, "status", "") == "blocked_topic_mismatch":
            score_cap = min(score_cap, 20)
            failure_codes.append("topic_mismatch")
        else:
            score_cap = min(score_cap, 40)
            failure_codes.append("minimum_evidence_failed")
        reasons.extend(str(value) for value in getattr(evidence_gate, "blockers", []) if str(value).strip())

    if _is_enforced_failure(citation_gate):
        score_cap = min(score_cap, 59)
        failure_codes.append("unsupported_critical_claim")
        reasons.extend(str(value) for value in getattr(citation_gate, "blockers", []) if str(value).strip())

    contract = getattr(report, "research_scope_contract", None)
    if requires_account_truth(contract):
        local_target_proofs = int(getattr(evidence_gate, "local_target_proof_count", 0) or 0)
        if local_target_proofs < 1:
            score_cap = min(score_cap, 25)
            failure_codes.append("unverified_account_truth")
            reasons.append("客户/账户交付缺少本地采购人、建设单位或业主角色的一手证据。")
        local_decision_sources = int(getattr(evidence_gate, "local_decision_source_count", 0) or 0)
        external_benchmarks = int(getattr(evidence_gate, "external_benchmark_count", 0) or 0)
        if local_decision_sources < 1 and external_benchmarks > 0:
            score_cap = min(score_cap, 30)
            failure_codes.append("source_topology_failed")
            reasons.append("当前主要依赖外部标杆，不能作为本地账户或预算结论。")

    diagnostics = getattr(report, "source_diagnostics", None)
    if diagnostics and getattr(diagnostics, "generation_fallback_used", False):
        score_cap = min(score_cap, 45)
        failure_codes.append("generation_fallback")
        generation_notes = [
            str(value)
            for value in getattr(diagnostics, "generation_notes", [])
            if str(value).strip()
        ]
        reasons.extend(generation_notes or ["正式研报模型未成功返回，当前为降级草稿。"])

    return ResearchHardFailureAssessment(
        blocked=bool(failure_codes),
        score_cap=score_cap,
        failure_codes=tuple(dict.fromkeys(failure_codes)),
        reasons=tuple(dict.fromkeys(reasons)),
    )
