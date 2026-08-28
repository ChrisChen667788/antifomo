from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from app.schemas.research import (
    ResearchReportDocument,
    ResearchReportReadinessOut,
    ResearchSourceDiagnosticsOut,
)
from app.services.content_extractor import normalize_text
from app.services.research.hard_failure_policy import evaluate_research_hard_failures
from app.services.research.delivery_scope import requires_account_truth


@dataclass(frozen=True, slots=True)
class ReportReadinessDependencies:
    dedupe_strings: Callable[[Iterable[str], int], list[str]]
    sanitize_entity_row: Callable[[str, str], str]
    is_actionable_budget_row: Callable[[str], bool]


def build_report_readiness(
    report: ResearchReportDocument,
    *,
    deps: ReportReadinessDependencies,
) -> ResearchReportReadinessOut:
    score = 12
    reasons: list[str] = []
    missing_axes: list[str] = []
    next_steps: list[str] = []
    diagnostics = report.source_diagnostics
    generation_fallback_used = bool(diagnostics.generation_fallback_used)
    snapshot_recovery_used = bool(diagnostics.snapshot_recovery_used)
    if generation_fallback_used:
        reasons.extend(
            diagnostics.generation_notes[:1]
            or ["正式研报模型未成功返回，当前为降级草稿。"]
        )
        missing_axes.append("正式模型输出")
        next_steps.append("恢复模型额度与连接后重新生成正式研报，再进入交付。")
    if snapshot_recovery_used:
        reasons.append("本轮因公开搜索波动复用了近期同题证据，结论已重新生成但证据新鲜度尚未独立确认。")
        missing_axes.append("新鲜证据复核")
        next_steps.append("公开搜索稳定后使用全新证据重跑，并核对来源数量、官方源与独立域门槛。")
    research_evidence_gate = getattr(report, "research_evidence_gate", None)
    hard_failure = evaluate_research_hard_failures(report)
    if research_evidence_gate and research_evidence_gate.enforced and not research_evidence_gate.passed:
        return ResearchReportReadinessOut(
            status="needs_evidence",
            score=hard_failure.score_cap,
            actionable=False,
            evidence_gate_passed=False,
            reasons=deps.dedupe_strings(research_evidence_gate.blockers, 5),
            missing_axes=deps.dedupe_strings(
                [
                    node.axis
                    for node in getattr(report, "research_question_tree", None).questions
                    if node.coverage_status != "covered"
                ]
                if getattr(report, "research_question_tree", None)
                else ["研究证据"],
                5,
            ),
            next_verification_steps=deps.dedupe_strings(research_evidence_gate.next_actions, 5),
        )
    research_citation_gate = getattr(report, "research_citation_gate", None)
    official_ratio = float(diagnostics.official_source_ratio or 0.0)
    contract = getattr(report, "research_scope_contract", None)
    account_task = requires_account_truth(contract)
    named_account_count = len(report.top_target_accounts or report.target_accounts)
    local_target_proof_count = int(getattr(research_evidence_gate, "local_target_proof_count", 0) or 0)
    local_decision_source_count = int(getattr(research_evidence_gate, "local_decision_source_count", 0) or 0)
    has_verified_account = bool(named_account_count and local_target_proof_count >= 1)
    account_count = named_account_count if not account_task else (named_account_count if has_verified_account else 0)
    has_budget = bool(report.budget_signals or report.tender_timeline)
    if account_task:
        has_budget = has_budget and local_decision_source_count >= 1
    has_contacts = bool(report.public_contact_channels or report.target_departments)
    section_failures = [
        section.title
        for section in report.sections
        if not getattr(section, "meets_evidence_quota", True)
        and any(token in normalize_text(section.title) for token in ("甲方", "预算", "招标", "生态", "竞品", "联系"))
    ]

    if report.source_count >= 6:
        score += 20
        reasons.append(f"已保留 {report.source_count} 条有效来源。")
    else:
        missing_axes.append("来源覆盖")
        next_steps.append("补到至少 6 条高相关来源，再进入强结论模式。")
    if official_ratio >= 0.25:
        score += 18
        reasons.append(f"官方源占比 {round(official_ratio * 100)}%。")
    else:
        missing_axes.append("官方源")
        next_steps.append("补官网、公告、政策、招采等官方源。")
    if account_count >= 1:
        score += 18
        reasons.append(f"已锁定 {account_count} 个重点账户。")
    else:
        missing_axes.append("具体账户")
        if account_task:
            next_steps.append("补检当前本地采购人、建设单位或业务牵头部门的一手页面，再锁定命名账户。")
        else:
            next_steps.append("先把行业判断收敛到具体公司、机构或业主单位。")
    if has_budget:
        score += 14
        reasons.append("已有预算或进入窗口线索。")
    else:
        missing_axes.append("预算/窗口")
        next_steps.append("补预算草案、招标窗口、项目期次或投资节奏。")
    if has_contacts:
        score += 12
        reasons.append("已有组织入口或公开联系线索。")
    else:
        missing_axes.append("组织入口")
        next_steps.append("补决策部门、联系人或公开组织入口。")
    if report.evidence_density == "high":
        score += 10
    elif report.evidence_density == "medium":
        score += 6
    if not section_failures:
        score += 6
    else:
        next_steps.append(f"优先补强这些章节的证据：{' / '.join(section_failures[:3])}")
    score = max(8, min(score, 96))
    actionable = score >= 62 and account_count >= 1 and has_budget
    evidence_gate_passed = official_ratio >= 0.2 and report.source_count >= 5 and not section_failures[:2]
    if account_task:
        actionable = actionable and has_verified_account and local_decision_source_count >= 2
        evidence_gate_passed = evidence_gate_passed and has_verified_account and local_decision_source_count >= 2
    if actionable and evidence_gate_passed and has_contacts:
        status = "ready"
    elif score >= 42 and account_count >= 1:
        status = "degraded"
    else:
        status = "needs_evidence"
    if status == "degraded":
        reasons.append("当前可用于候选推进，但仍需补证后再做强判断。")
    if status == "needs_evidence":
        reasons.append("当前更适合输出候选名单与待补证路径，不宜直接当作最终商业判断。")
    if research_citation_gate and research_citation_gate.enforced and not research_citation_gate.passed:
        score = hard_failure.cap_score(score)
        actionable = False
        evidence_gate_passed = False
        status = "needs_evidence"
        reasons.extend(research_citation_gate.blockers)
        next_steps.append("逐条补齐关键主张证据并重新运行引用完整性门禁。")
    if generation_fallback_used:
        score = hard_failure.cap_score(score)
        actionable = False
        evidence_gate_passed = False
        status = "needs_evidence"
    if snapshot_recovery_used:
        score = min(score, 58)
        actionable = False
        evidence_gate_passed = False
        status = "needs_evidence"
    return ResearchReportReadinessOut(
        status=status,
        score=score,
        actionable=actionable,
        evidence_gate_passed=evidence_gate_passed,
        reasons=deps.dedupe_strings(reasons, 5),
        missing_axes=deps.dedupe_strings(missing_axes, 5),
        next_verification_steps=deps.dedupe_strings(next_steps, 5),
    )


def resolved_report_readiness(
    report: ResearchReportDocument,
    *,
    deps: ReportReadinessDependencies,
) -> ResearchReportReadinessOut:
    readiness = report.report_readiness if getattr(report, "report_readiness", None) else None
    if readiness and (
        int(getattr(readiness, "score", 0) or 0) > 0
        or bool(getattr(readiness, "reasons", []))
        or bool(getattr(readiness, "missing_axes", []))
        or bool(getattr(readiness, "next_verification_steps", []))
    ):
        return readiness
    return build_report_readiness(report, deps=deps)


def is_low_signal_execution_report(
    report: ResearchReportDocument,
    *,
    deps: ReportReadinessDependencies,
) -> bool:
    title = normalize_text(getattr(report, "report_title", ""))
    if title.endswith(("待核验清单与补证路径", "待核驗清單與補證路徑", "Verification Backlog and Evidence Path")):
        return True
    diagnostics = report.source_diagnostics if getattr(report, "source_diagnostics", None) else ResearchSourceDiagnosticsOut()
    readiness = resolved_report_readiness(report, deps=deps)
    official_ratio = float(diagnostics.official_source_ratio or 0.0)
    target_names = deps.dedupe_strings(
        [
            deps.sanitize_entity_row("target_accounts", normalize_text(name))
            for name in [
                *(normalize_text(item.name) for item in report.top_target_accounts if normalize_text(item.name)),
                *(normalize_text(item) for item in report.target_accounts if normalize_text(item)),
            ]
            if normalize_text(name)
        ],
        4,
    )
    actionable_budget_rows = [row for row in report.budget_signals if deps.is_actionable_budget_row(row)]
    return (
        readiness.status == "needs_evidence"
        or (readiness.status != "ready" and not target_names and not actionable_budget_rows)
        or (readiness.status == "degraded" and official_ratio < 0.12 and not target_names)
    ) and (
        int(getattr(report, "source_count", 0) or 0) < 3
        or diagnostics.evidence_mode == "fallback"
        or official_ratio < 0.15
        or diagnostics.retrieval_quality == "low"
        or (not target_names and not actionable_budget_rows)
    )
