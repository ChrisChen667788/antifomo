from __future__ import annotations

from app.schemas.research import (
    ResearchCitationGateOut,
    ResearchEvidenceGateOut,
    ResearchReportResponse,
    ResearchScopeContractOut,
    ResearchSourceDiagnosticsOut,
    ResearchSourceOut,
)
from app.services.research_quality_service import build_research_quality_profile
from app.services.research_report_evaluation_service import evaluate_research_report
from app.services.research_solution_intelligence_service import build_solution_delivery_pack
from app.services.research.evidence_governance import (
    apply_evidence_governance_diagnostics,
    build_evidence_gap_report,
    build_research_claim_governance,
    build_research_evidence_governance,
)
from app.services.research.source_documents import SourceDocument


def _source(
    title: str,
    text: str,
    *,
    domain: str,
    tier: str = "media",
) -> SourceDocument:
    return SourceDocument(
        title=title,
        url=f"https://{domain}/article",
        domain=domain,
        snippet=text,
        search_query="2026 上海 医疗 AI",
        source_type="policy" if tier == "official" else "web",
        content_status="extracted",
        excerpt=text,
        source_label=domain,
        source_tier=tier,
    )


def _scope_hints() -> dict[str, object]:
    return {
        "regions": ["上海"],
        "industries": ["医疗", "大模型", "人工智能"],
        "clients": [],
        "industry_methodology_profile": "医疗",
        "industry_methodology_questions": [
            "需求来自临床、医务、运营还是科研教学场景？",
            "卫健政策和试点名单提供了哪些市场信号？",
            "医院信息科、采购办和预算窗口分别是什么？",
            "现有医疗 AI 方案、厂商和标杆案例有哪些？",
        ],
        "strategy_exclusion_terms": [],
        "strategy_must_include_terms": ["医疗", "医院", "卫健", "临床"],
    }


def test_medical_scope_rejects_codex_sources_and_blocks_formal_delivery() -> None:
    sources = [
        _source(
            "OpenAI updates Codex third-party model support",
            "Codex now supports more coding models and developer tools.",
            domain="example-tech.com",
        ),
        _source(
            "Accounts linked to a model provider are blocked",
            "The report discusses OpenAI accounts, coding tools and model access.",
            domain="example-news.com",
        ),
    ]

    result = build_research_evidence_governance(
        sources,
        keyword="2026年下半年上海医疗行业AI潜在需求行业调研及商机情报分析",
        research_focus=None,
        research_mode="deep",
        scope_hints=_scope_hints(),
    )

    assert result.contract.industry_methodology == "医疗"
    assert result.gate.status == "blocked_topic_mismatch"
    assert result.gate.formal_report_allowed is False
    assert result.gate.solution_delivery_allowed is False
    assert result.gate.accepted_source_count == 0
    assert result.gate.rejected_source_count == 2
    assert all(row.decision == "rejected" for row in result.admissions)
    assert sum(
        result.gate.model_dump()[key]
        for key in ("accepted_source_count", "ambiguous_source_count", "rejected_source_count")
    ) == result.gate.candidate_source_count


def test_deep_medical_evidence_pack_passes_source_and_question_gates() -> None:
    sources = [
        _source("上海卫健委医疗AI试点通知", "上海卫健委发布医疗AI临床试点政策和行动计划。", domain="wsjkw.sh.gov.cn", tier="official"),
        _source("医院AI采购意向", "上海医院信息科发布医疗AI系统采购意向、预算和招标项目。", domain="ccgp-sh.gov.cn", tier="official"),
        _source("医院平台建设方案", "上海医院医疗AI平台架构、系统集成方案和厂商合作要求。", domain="hospital-a.cn", tier="official"),
        _source("临床需求调研", "医疗AI用于临床诊疗、医务运营和科研教学场景，解决医生痛点。", domain="med-research.cn"),
        _source("医疗AI投入产出", "医院医疗AI投资成本、实施周期、ROI收益和后续扩容测算。", domain="health-economics.cn"),
        _source("医疗数据安全规范", "医疗AI涉及患者数据安全、隐私合规、模型审计和交付风险。", domain="cac-health.gov.cn", tier="official"),
        _source("医疗AI厂商竞争", "医疗AI产品、平台厂商、竞品、标杆案例和生态伙伴竞争格局。", domain="medical-market.cn"),
        _source("医院AI运维实践", "医疗AI系统上线后的运维绩效、交付周期和院内扩容路径。", domain="hospital-b.cn"),
    ]

    result = build_research_evidence_governance(
        sources,
        keyword="2026年下半年上海医疗行业AI需求与商机分析",
        research_focus="临床场景、医院采购和解决方案",
        research_mode="deep",
        scope_hints=_scope_hints(),
    )

    assert result.gate.status == "evidence_ready"
    assert result.gate.passed is True
    assert result.gate.accepted_source_count == 8
    assert result.gate.official_source_count >= 3
    assert result.gate.unique_domain_count >= 5
    assert result.question_tree.coverage_percent >= 80
    assert len(result.accepted_sources) == 8


def test_broad_market_opportunity_query_is_not_misclassified_as_account_pursuit() -> None:
    result = build_research_evidence_governance(
        [
            _source(
                "上海卫健委医疗AI试点通知",
                "上海卫健委发布医疗AI临床试点政策和行动计划。",
                domain="wsjkw.sh.gov.cn",
                tier="official",
            )
        ],
        keyword="2026年下半年上海医疗行业AI需求与商机分析",
        research_focus="临床场景、医院采购和解决方案",
        research_mode="deep",
        scope_hints=_scope_hints(),
    )

    assert result.contract.task_type == "solution_research"
    assert result.contract.clients == []
    assert not any("账户/方案任务" in blocker for blocker in result.gate.blockers)


def test_account_intelligence_requires_concrete_buyer_role_evidence() -> None:
    sources = [
        _source(
            f"长三角政务AI政策与建设动态{index}",
            "长三角数字政府人工智能政策、规划、平台、系统、项目、运维和数据安全持续推进。",
            domain=f"policy-{index}.gov.cn",
            tier="official",
        )
        for index in range(8)
    ]
    scope_hints = {
        "regions": ["长三角"],
        "industries": ["政务云", "人工智能"],
        "clients": [],
        "strategy_exclusion_terms": [],
        "strategy_must_include_terms": ["政务", "人工智能"],
    }

    result = build_research_evidence_governance(
        sources,
        keyword="长三角政府行业AI潜在需求情报搜集与分析",
        research_focus=None,
        research_mode="deep",
        scope_hints=scope_hints,
    )

    assert result.contract.task_type == "account_intelligence"
    assert result.gate.status == "evidence_gap"
    assert result.gate.passed is False
    assert any("需求负责方证据" in blocker for blocker in result.gate.blockers)
    buyer_question = next(node for node in result.question_tree.questions if node.question_id.endswith("buyer_procurement"))
    assert buyer_question.coverage_status == "uncovered"
    assert any("采购意向" in query for query in result.gate.next_actions)


def test_external_procurement_source_is_benchmark_not_local_account_proof() -> None:
    scope_hints = {
        "regions": ["长三角"],
        "industries": ["文旅文博", "人工智能"],
        "clients": [],
        "strategy_exclusion_terms": [],
        "strategy_must_include_terms": ["文旅", "文博", "人工智能"],
    }
    source = _source(
        "烟台市文化和旅游局智慧文旅采购公告",
        "2026年采购人：烟台市文化和旅游局。智慧文旅人工智能平台项目公开招标。",
        domain="yantai.gov.cn",
        tier="official",
    )

    result = build_research_evidence_governance(
        [source],
        keyword="2026年长三角文旅行业人工智能潜在需求和商机情报调研",
        research_focus="本地采购窗口与业主单位",
        research_mode="deep",
        scope_hints=scope_hints,
    )

    admission = result.admissions[0]
    assert admission.source_topology == "external_benchmark"
    assert admission.evidence_lane == "benchmark"
    assert admission.account_pursuit_eligible is False
    assert result.gate.local_target_proof_count == 0
    assert result.gate.external_benchmark_count == 1


def test_local_current_procurement_source_becomes_account_proof() -> None:
    scope_hints = {
        "regions": ["长三角"],
        "industries": ["文旅文博", "人工智能"],
        "clients": [],
        "strategy_exclusion_terms": [],
        "strategy_must_include_terms": ["文旅", "文博", "人工智能"],
    }
    source = _source(
        "上海市文化和旅游局智慧场馆人工智能采购意向",
        "2026年采购人：上海市文化和旅游局。拟采购智慧场馆人工智能导览与服务平台。",
        domain="sh.gov.cn",
        tier="official",
    )

    result = build_research_evidence_governance(
        [source],
        keyword="2026年长三角文旅行业人工智能潜在需求和商机情报调研",
        research_focus="本地采购窗口与业主单位",
        research_mode="deep",
        scope_hints=scope_hints,
    )

    admission = result.admissions[0]
    assert admission.source_topology == "local_target_proof"
    assert admission.evidence_lane == "decision"
    assert admission.account_pursuit_eligible is True
    assert result.gate.local_target_proof_count == 1


def test_evidence_gap_report_contains_no_formal_solution_blueprint() -> None:
    result = build_research_evidence_governance(
        [_source("Codex update", "Codex coding model update.", domain="tech.example")],
        keyword="上海医疗AI需求调研",
        research_focus=None,
        research_mode="deep",
        scope_hints=_scope_hints(),
    )
    diagnostics = apply_evidence_governance_diagnostics(ResearchSourceDiagnosticsOut(), result)

    report = build_evidence_gap_report(
        keyword="上海医疗AI需求调研",
        research_focus=None,
        output_language="zh-CN",
        research_mode="deep",
        query_plan=["上海 医疗 AI"],
        governance=result,
        source_diagnostics=diagnostics,
    )

    assert report.report_readiness.evidence_gate_passed is False
    assert report.research_evidence_gate.status == "evidence_gap"
    assert any("检索候选来源不足" in item for item in report.research_evidence_gate.next_actions)
    assert report.solution_delivery_pack.compiled_documents == []
    assert report.solution_delivery_pack.architecture_readiness.blueprint_sections == []
    assert "不生成架构蓝图" in report.solution_delivery_pack.evidence_policy


def test_claim_governance_requires_claim_level_evidence() -> None:
    statement = "上海市第一人民医院2026年医疗AI系统采购预算为100万元"
    report = ResearchReportResponse(
        keyword="上海医疗AI采购",
        output_language="zh-CN",
        research_mode="deep",
        report_title="上海医疗AI采购研判",
        executive_summary=statement,
        consulting_angle="用于核验采购窗口和预算。",
        source_count=1,
        sources=[
            ResearchSourceOut(
                title="上海市第一人民医院医疗AI采购公告",
                url="https://hospital.example/procurement",
                domain="hospital.example",
                snippet=statement,
                search_query="上海 医疗 AI 采购",
                source_type="procurement",
                content_status="extracted",
                source_label="医院官网",
                source_tier="official",
            )
        ],
        generated_at="2026-07-13T00:00:00Z",
    )

    result = build_research_claim_governance(report)

    assert result.ledger.claim_count == 1
    assert result.ledger.supported_claim_count == 1
    assert result.citation_gate.critical_claim_coverage_percent == 100
    assert result.citation_gate.citation_completeness_percent == 100
    assert result.citation_gate.status == "pass"


def test_medical_scope_selects_medical_methodology_before_generic_ai() -> None:
    report = ResearchReportResponse(
        keyword="上海医疗行业AI潜在需求",
        output_language="zh-CN",
        research_mode="deep",
        report_title="上海医疗AI需求研判",
        executive_summary="医疗AI需求来自临床、医务和医院运营场景。",
        consulting_angle="用于医院方案设计。",
        source_count=0,
        source_diagnostics=ResearchSourceDiagnosticsOut(scope_industries=["医疗", "大模型", "人工智能"]),
        research_scope_contract=ResearchScopeContractOut(
            industries=["医疗", "大模型", "人工智能"],
            industry_methodology="医疗",
            status="ready",
        ),
        generated_at="2026-07-13T00:00:00Z",
    )

    profile = build_research_quality_profile(report)

    assert profile.methodology.industry_key == "medical_ai"


def test_hard_topic_failure_caps_quality_and_evaluation_scores() -> None:
    report = ResearchReportResponse(
        keyword="上海医疗AI需求调研",
        output_language="zh-CN",
        research_mode="deep",
        report_title="看似完整的跑题报告",
        executive_summary="这是一个结构完整但没有医疗证据的结论。",
        consulting_angle="不应外发。",
        source_count=0,
        research_evidence_gate=ResearchEvidenceGateOut(
            enforced=True,
            status="blocked_topic_mismatch",
            passed=False,
            blockers=["来源主题错位。"],
        ),
        generated_at="2026-07-13T00:00:00Z",
    )

    quality = build_research_quality_profile(report)
    evaluation = evaluate_research_report(report)

    assert quality.overall_score <= 20
    assert quality.status == "needs_evidence"
    assert evaluation.overall_score <= 20
    assert evaluation.status == "fail"


def test_solution_pack_is_blocked_when_citation_gate_fails() -> None:
    report = ResearchReportResponse(
        keyword="上海医疗AI需求调研",
        output_language="zh-CN",
        research_mode="deep",
        report_title="上海医疗AI需求研判",
        executive_summary="当前关键主张尚未绑定证据。",
        consulting_angle="内部补证。",
        source_count=8,
        research_evidence_gate=ResearchEvidenceGateOut(
            enforced=True,
            status="evidence_ready",
            passed=True,
            formal_report_allowed=True,
            solution_delivery_allowed=True,
        ),
        research_citation_gate=ResearchCitationGateOut(
            enforced=True,
            status="fail",
            passed=False,
            blockers=["关键主张证据覆盖低于 100%。"],
        ),
        generated_at="2026-07-13T00:00:00Z",
    )

    pack = build_solution_delivery_pack(report)

    assert pack.compiled_documents == []
    assert pack.architecture_readiness.status == "blocked"
    assert "不生成完整架构蓝图" in pack.evidence_policy
