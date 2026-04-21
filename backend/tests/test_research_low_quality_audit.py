from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.research import ResearchCommercialSummaryOut, ResearchReportResponse, ResearchSourceDiagnosticsOut
from app.services import research_service
from scripts import audit_low_quality_research_reports as audit_script


def _build_low_signal_report() -> ResearchReportResponse:
    return ResearchReportResponse(
        keyword="政务云 AI 行业研报",
        research_focus="预算和周期",
        output_language="zh-CN",
        research_mode="deep",
        report_title="待补证研判｜政务云 AI 行业研报",
        executive_summary="当前证据不足以形成最终商业判断，更适合作为候选名单与待补证路径。",
        consulting_angle="可用于初步行业判断。",
        sections=[],
        target_accounts=["省级数据局"],
        target_departments=[],
        public_contact_channels=[],
        account_team_signals=[],
        budget_signals=[],
        project_distribution=[],
        strategic_directions=[],
        tender_timeline=[],
        leadership_focus=[],
        ecosystem_partners=[],
        competitor_profiles=[],
        benchmark_cases=[],
        flagship_products=[],
        key_people=[],
        five_year_outlook=[],
        client_peer_moves=[],
        winner_peer_moves=[],
        competition_analysis=[],
        source_count=0,
        evidence_density="low",
        source_quality="low",
        query_plan=[],
        sources=[],
        source_diagnostics=ResearchSourceDiagnosticsOut(
            scope_regions=["长三角"],
            scope_industries=["政务云"],
            scope_clients=["省级数据局"],
            retrieval_quality="low",
            evidence_mode="fallback",
            official_source_ratio=0.0,
        ),
        commercial_summary=ResearchCommercialSummaryOut(next_action="先补公开证据"),
        generated_at=datetime.now(timezone.utc),
    )


def _audit_sample(report: ResearchReportResponse) -> dict[str, object]:
    return audit_script._audit_report(
        SimpleNamespace(id="demo-entry", updated_at=datetime.now(timezone.utc), title=report.report_title),
        report,
        {"looks_like_bad_executive_summary": research_service._looks_like_bad_executive_summary},
    )


def test_audit_ignores_expected_low_signal_issues_for_standard_guarded_backlog_report() -> None:
    rewritten = research_service.rewrite_stored_research_report(_build_low_signal_report())

    sample = _audit_sample(rewritten)

    assert sample["guarded_backlog"] is True
    assert sample["issue_codes"] == []
    assert sample["risk_score"] == 0


def test_audit_keeps_real_noise_flags_for_guarded_backlog_report() -> None:
    rewritten = research_service.rewrite_stored_research_report(_build_low_signal_report())
    noisy_rewritten = rewritten.model_copy(
        update={"target_accounts": ["建议补充公开服务热线、继续扩大搜索范围"]},
    )

    sample = _audit_sample(noisy_rewritten)

    assert sample["guarded_backlog"] is True
    assert "noisy_entity_rows" in sample["issue_codes"]
    assert sample["risk_score"] > 0
