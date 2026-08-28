from __future__ import annotations

from datetime import UTC, datetime
import json

from app.schemas.research import ResearchReportResponse, ResearchSourceOut
from app.services.delivery.executable_validation import (
    build_proof_of_architecture,
    load_reference_proof_artifact,
    run_reference_proof_suite,
    write_reference_proof_artifact,
)
from app.services.delivery.decision_engineering import (
    build_reference_architecture_decision_engineering,
    validate_architecture_decision_engineering,
)
from app.services.research_solution_intelligence_service import build_solution_delivery_pack


def _report() -> ResearchReportResponse:
    return ResearchReportResponse(
        keyword="文旅智能导览",
        research_focus="面向景区的智能导览、内容生成、游客服务和运营分析。",
        report_title="文旅智能导览解决方案研判",
        executive_summary="公开招采显示景区需要可审计、可扩容且受控的智能导览能力。",
        consulting_angle="先用隔离试点验证接口、成本、安全和恢复指标。",
        target_accounts=["某文旅集团"],
        target_departments=["信息化部", "运营中心"],
        budget_signals=["试点预算 120 万元"],
        tender_timeline=["2026 Q3 试点招标"],
        strategic_directions=["先做导览试点，再扩展运营平台"],
        flagship_products=["智能导览平台", "内容安全网关"],
        source_count=2,
        sources=[
            ResearchSourceOut(
                title="景区智能导览采购公告",
                url="https://procurement.example.gov.cn/tourism-ai",
                domain="procurement.example.gov.cn",
                snippet="采购智能导览、API 接口、并发 500、私有化部署、等保二级和审计日志。",
                search_query="景区 智能导览 招标",
                source_tier="official",
                source_type="procurement",
                content_status="fetched",
            ),
            ResearchSourceOut(
                title="文旅集团数字化试点计划",
                url="https://tourism.example.gov.cn/digital-plan",
                domain="tourism.example.gov.cn",
                snippet="计划验证游客服务、内容生成、运营指标和人工复核流程。",
                search_query="文旅 数字化 试点",
                source_tier="official",
                source_type="policy",
                content_status="fetched",
            ),
        ],
        generated_at=datetime(2026, 7, 13, tzinfo=UTC),
    )


def test_reference_proof_suite_executes_three_domain_vertical_simulators() -> None:
    payload = run_reference_proof_suite(generated_at=datetime(2026, 7, 13, tzinfo=UTC))

    assert payload["machine_status"] == "passed"
    assert payload["scenario_count"] == 3
    assert payload["passed_scenario_count"] == 3
    assert payload["blind_review_status"] == "pending"
    assert {row["domain"] for row in payload["scenarios"]} == {"medical", "finance", "tourism"}
    assert all(len(row["checks"]) == 8 for row in payload["scenarios"])
    assert all(check["status"] == "passed" for row in payload["scenarios"] for check in row["checks"])


def test_reference_architecture_contract_covers_qaw_atam_adr_c4_and_traceability() -> None:
    engineering = build_reference_architecture_decision_engineering()
    result = validate_architecture_decision_engineering(engineering)

    assert result["status"] == "pass"
    assert result["qaw_scenario_count"] == 6
    assert result["adr_count"] == 3
    assert result["c4_view_count"] == 5
    assert result["traceability_coverage_percent"] == 100
    assert result["orphan_component_count"] == 0


def test_proof_artifact_digest_and_delivery_pack_evidence_are_fail_closed(tmp_path) -> None:
    path = tmp_path / "solution-proof.json"
    write_reference_proof_artifact(path, generated_at=datetime(2026, 7, 13, tzinfo=UTC))
    payload, digest = load_reference_proof_artifact(path)
    assert payload is not None
    assert digest

    report = _report()
    delivery = build_solution_delivery_pack(
        report,
        target_customer="某文旅集团",
        vertical_scene="景区智能导览",
    )
    proof = build_proof_of_architecture(
        report,
        engineering=delivery.architecture_decision_engineering,
        artifact_path=path,
    )

    assert proof.status == "human_pending"
    assert proof.scenario_test_coverage_percent == 100
    assert proof.high_risk_decision_evidence_percent == 100
    assert all(check.status == "passed" for check in proof.checks if not check.external_evidence_required)
    assert any(check.status == "human_pending" for check in proof.checks if check.external_evidence_required)
    assert proof.customer_evidence.limitations
    assert proof.internal_evidence.artifact_paths
    assert any("真实样本端到端盲评待完成" in blocker for blocker in proof.blockers)

    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["passed_scenario_count"] = 0
    path.write_text(json.dumps(tampered), encoding="utf-8")
    assert load_reference_proof_artifact(path) == (None, "")
