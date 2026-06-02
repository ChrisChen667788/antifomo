from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from app.schemas.research import (
    ResearchReportDocument,
    ResearchReportReadinessOut,
    ResearchSourceDiagnosticsOut,
)
from app.services.content_extractor import normalize_text


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
    official_ratio = float(diagnostics.official_source_ratio or 0.0)
    account_count = len(report.top_target_accounts or report.target_accounts)
    has_budget = bool(report.budget_signals or report.tender_timeline)
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
