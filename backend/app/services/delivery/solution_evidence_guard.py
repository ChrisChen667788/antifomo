from __future__ import annotations

from typing import Iterable

from app.schemas.research import (
    ResearchReportDocument,
    ResearchSolutionArchitectureReadinessOut,
    ResearchSolutionDeliveryPackOut,
)
from app.services.content_extractor import normalize_text
from app.services.research.hard_failure_policy import evaluate_research_hard_failures


def _dedupe_strings(values: Iterable[object], limit: int = 10) -> list[str]:
    seen: set[str] = set()
    rows: list[str] = []
    for value in values:
        normalized = normalize_text(str(value or ""))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        rows.append(normalized)
        if len(rows) >= limit:
            break
    return rows


def _scenario_from_report(report: ResearchReportDocument) -> str:
    text = normalize_text(" ".join([report.keyword, report.research_focus or "", report.report_title]))
    for value in ("电商数字人", "文旅AIGC平台", "AI营销平台", "政务AI解决方案", "政务AI", "数字人", "AIGC", "AI营销"):
        if value.lower() in text.lower():
            return value
    return report.keyword


def evaluate_solution_delivery_guard(
    report: ResearchReportDocument,
    *,
    scenario: str = "",
    target_customer: str = "",
    vertical_scene: str = "",
) -> tuple[str, str, str, ResearchSolutionDeliveryPackOut | None]:
    resolved_scenario = normalize_text(scenario) or _scenario_from_report(report)
    resolved_customer = normalize_text(target_customer) or (report.target_accounts[0] if report.target_accounts else "")
    resolved_scene = normalize_text(vertical_scene) or normalize_text(report.research_focus or "")
    evidence_gate = getattr(report, "research_evidence_gate", None)
    citation_gate = getattr(report, "research_citation_gate", None)
    hard_failure = evaluate_research_hard_failures(report)
    evidence_blocked = bool(evidence_gate and evidence_gate.enforced and not evidence_gate.passed)
    citation_blocked = bool(citation_gate and citation_gate.enforced and not citation_gate.passed)
    if not hard_failure.blocked:
        return resolved_scenario, resolved_customer, resolved_scene, None

    blockers = _dedupe_strings(
        [
            *(evidence_gate.blockers if evidence_blocked else []),
            *(citation_gate.blockers if citation_blocked else []),
            *(citation_gate.warnings if citation_blocked else []),
        ],
        limit=8,
    )
    next_actions = _dedupe_strings(
        [
            *(evidence_gate.next_actions if evidence_blocked else []),
            "重新生成主张证据账本并确认关键主张覆盖率达到 100%。" if citation_blocked else "",
        ],
        limit=6,
    )
    policy = "研究证据或主张引用门未通过，仅返回补证清单，不生成完整架构蓝图、可研、项目建议书或客户 PPT。"
    markdown = "\n".join(
        [
            "# 解决方案生成已阻断",
            "",
            policy,
            "",
            "## 阻断原因",
            *[f"- {item}" for item in blockers],
        ]
    )
    pack = ResearchSolutionDeliveryPackOut(
        scenario=resolved_scenario,
        target_customer=resolved_customer,
        vertical_scene=resolved_scene,
        evidence_policy=policy,
        grounding_checks=blockers,
        clarification_questions=_dedupe_strings(
            [
                *(evidence_gate.next_actions if evidence_blocked else []),
                "逐条补齐无证据关键主张，并重新运行引用完整性检查。" if citation_blocked else "",
            ],
            limit=6,
        ),
        architecture_readiness=ResearchSolutionArchitectureReadinessOut(
            overall_score=0,
            status="blocked",
            summary=policy,
            validation_actions=blockers,
            assumptions=["正式方案生成依赖 research evidence gate 与 citation gate 同时通过。"],
        ),
        review_checklist=blockers,
        next_steps=next_actions,
        export_markdown=markdown,
    )
    return resolved_scenario, resolved_customer, resolved_scene, pack
