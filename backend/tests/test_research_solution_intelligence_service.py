from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.schemas.research import (
    ResearchCitationGateOut,
    ResearchEvidenceGateOut,
    ResearchReportReadinessOut,
    ResearchReportResponse,
    ResearchSourceOut,
)
from app.services import industry_skill_library
from app.services.delivery.market_intelligence import build_market_intelligence_pack
from app.services.industry_knowledge_rag import LocalContentUnit, LocalDocumentAnalysis
from app.services.industry_skill_library import build_industry_skill_library
from app.services.research_solution_intelligence_service import build_solution_delivery_pack


def _report() -> ResearchReportResponse:
    return ResearchReportResponse(
        keyword="文旅AIGC平台",
        research_focus="面向景区客户设计 AIGC 导览、数字人讲解和营销内容生成平台。",
        output_language="zh-CN",
        research_mode="deep",
        report_title="文旅AIGC平台解决方案机会研判",
        executive_summary="近三年文旅数字化和AIGC内容建设需求增加，景区客户更关注导览体验、内容生产和营销转化。",
        consulting_angle="先锁定目标景区和文旅集团，再用近三年招采、产品清单和技术参数反推方案边界。",
        target_accounts=["某文旅集团"],
        target_departments=["数字化部", "市场营销部"],
        budget_signals=["2025 年智慧景区平台升级预算"],
        tender_timeline=["2025 年采购意向后进入公开招标"],
        strategic_directions=["先做数字人导览试点，再扩展到AIGC营销内容平台。"],
        benchmark_cases=["智慧景区数字人讲解项目"],
        flagship_products=["数字人导览平台", "AIGC内容生成平台"],
        source_count=3,
        evidence_density="medium",
        source_quality="medium",
        sources=[
            ResearchSourceOut(
                title="某市智慧文旅AIGC导览平台公开招标公告",
                url="https://ggzy.example.gov.cn/tender/aigc-tourism",
                domain="ggzy.example.gov.cn",
                snippet=(
                    "2025年5月公开招标，项目编号 WLAIGC-2025-01，采购人：某文旅集团，招标代理：某招标代理公司，"
                    "预算金额 680万元，建设数字人导览、AIGC内容生成、支持并发不少于500路、接口API、等保二级，"
                    "投标人需提供大模型相关软件著作权证书。"
                ),
                search_query="文旅 AIGC 数字人 公开招标 技术参数",
                source_type="procurement",
                content_status="fetched",
                source_tier="official",
            ),
            ResearchSourceOut(
                title="景区AI营销平台中标成交公告",
                url="https://ccgp.example.gov.cn/win/ai-marketing",
                domain="ccgp.example.gov.cn",
                snippet="2024年中标成交，AI营销平台包含游客画像、内容生成、活动投放和数据看板，中标供应商：某科技公司。第一中标候选人：某科技公司；第二中标候选人：某数智公司。",
                search_query="景区 AI营销平台 中标",
                source_type="procurement",
                content_status="fetched",
                source_tier="official",
            ),
        ],
        generated_at=datetime.now(timezone.utc),
    )


def test_market_intelligence_pack_extracts_three_year_tenders_products_and_parameters() -> None:
    pack = build_market_intelligence_pack(
        _report(),
        scenario="文旅AIGC平台",
        target_customer="某文旅集团",
        vertical_scene="景区数字人导览",
    )

    assert pack.lookback_years == 3
    assert pack.tender_projects
    assert pack.tender_projects[0].buyer == "某文旅集团"
    assert "680万元" in pack.tender_projects[0].amount
    assert pack.tender_projects[0].tender_agency == "某招标代理公司"
    assert pack.tender_projects[0].project_code == "WLAIGC-2025-01"
    assert any(
        "某数智公司" in value or "某科技公司" in value
        for project in pack.tender_projects
        for value in project.bidder_candidates
    )
    assert any("并发" in value or "API" in value for value in pack.tender_projects[0].technical_parameters)
    assert any(item.name == "数字人" or "数字人" in item.name for item in pack.product_catalog)
    assert any("site:ccgp.gov.cn" in query for query in pack.external_source_queries)
    assert pack.source_support_score > 0
    assert pack.validated_source_count >= 1
    assert "招投标项目明细" in pack.export_markdown
    assert "来源支撑" in pack.export_markdown
    assert "招标代理" in pack.export_markdown


def test_solution_delivery_pack_builds_feasibility_proposal_and_ppt_outlines() -> None:
    pack = build_solution_delivery_pack(
        _report(),
        scenario="文旅AIGC平台",
        target_customer="某文旅集团",
        vertical_scene="景区数字人导览",
        supplemental_context="客户希望先做小范围试点。",
    )

    assert pack.scenario == "文旅AIGC平台"
    assert pack.target_customer == "某文旅集团"
    assert pack.feasibility_outline
    assert pack.project_proposal_outline
    assert {document.document_kind for document in pack.compiled_documents} == {
        "solution_design",
        "consulting_report",
        "project_proposal",
        "feasibility_study",
    }
    assert all(document.sections for document in pack.compiled_documents)
    assert pack.client_ppt_outline
    assert {item.artifact_type for item in pack.advisory_artifacts} == {
        "client_brief",
        "bidding_prep_memo",
        "execution_materials",
    }
    assert any("客户 brief" in item.title for item in pack.advisory_artifacts)
    assert any("投标准备" in item.markdown for item in pack.advisory_artifacts)
    assert pack.source_support_score > 0
    assert pack.grounding_checks
    assert any("目标客户" in item for item in pack.clarification_questions)
    assert pack.quantitative_decision_model.alternative_options
    assert pack.quantitative_decision_model.tender_score_response_matrix
    assert pack.quantitative_decision_model.financial_scenarios
    assert "Advisory-grade 交付产物" in pack.export_markdown
    assert "对客汇报 PPT 大纲" in pack.export_markdown
    assert "量化决策模型" in pack.export_markdown
    assert pack.solution_quality_profile.overall_score > 0
    assert pack.project_proposal_quality_profile.overall_score > 0
    assert pack.evidence_ledger.claim_count > 0
    assert pack.evidence_ledger.evidence_count > 0
    assert all(claim.claim_id.startswith("clm_") for claim in pack.evidence_ledger.claims)
    assert all(item.evidence_id.startswith("ev_") for item in pack.evidence_ledger.evidence)
    assert pack.semantic_challenge.issue_count >= 0
    assert pack.semantic_challenge.golden_sample_alignment_score >= 0
    assert pack.architecture_readiness.overall_score > 0
    assert pack.architecture_readiness.blueprint_sections
    assert any(section.title == "模型、数据与集成层" for section in pack.architecture_readiness.blueprint_sections)
    assert any("接口" in item or "API" in item for item in pack.architecture_readiness.non_functional_requirements)
    assert pack.architecture_readiness.validation_actions
    assert pack.architect_workbench.customer_scenarios
    assert any("信息化" in stakeholder.role for stakeholder in pack.architect_workbench.stakeholders)
    assert any("系统集成" in criterion.criterion for criterion in pack.architect_workbench.decision_criteria)
    assert pack.architect_workbench.capability_architecture_matrix
    assert any(
        "接口" in " ".join(mapping.integration_surfaces)
        or "API" in " ".join(mapping.integration_surfaces)
        for mapping in pack.architect_workbench.capability_architecture_matrix
    )
    assert pack.architect_workbench.architecture_decision_records
    assert any("API-first" in record.selected_direction for record in pack.architect_workbench.architecture_decision_records)
    assert pack.architect_workbench.integration_dependencies
    assert any(
        dependency.operational_owner == "安全合规负责人"
        for dependency in pack.architect_workbench.integration_dependencies
    )
    assert pack.architect_workbench.next_meeting_agenda
    assert pack.architecture_export_bundle.adr_table
    assert pack.architecture_export_bundle.dependency_workshop_checklist
    assert pack.architecture_export_bundle.stakeholder_brief.key_messages
    assert pack.architecture_export_bundle.customer_technical_workshop_agenda
    assert "架构交付导出包" in pack.architecture_export_bundle.export_markdown
    assert "ADR 表" in pack.architecture_export_bundle.export_markdown
    assert "集成依赖 workshop 清单" in pack.architecture_export_bundle.export_markdown
    assert "Stakeholder Brief" in pack.architecture_export_bundle.export_markdown
    engineering = pack.architecture_decision_engineering
    assert engineering.status == "ready_for_review"
    assert len(engineering.quality_attribute_scenarios) >= 6
    assert all(scenario.response_measure for scenario in engineering.quality_attribute_scenarios)
    assert all({option.option_type for option in adr.options} == {"baseline", "pilot", "target"} for adr in engineering.adrs)
    assert {view.level for view in engineering.c4_views} == {"context", "container", "component", "dynamic", "deployment"}
    assert engineering.traceability_coverage_percent == 100
    assert engineering.orphan_component_count == 0
    assert pack.proof_of_architecture.scenario_test_coverage_percent == 100
    assert pack.project_proposal_quality_profile.self_review.triggered is True
    assert (
        pack.project_proposal_quality_profile.self_review.after_score
        >= pack.project_proposal_quality_profile.self_review.before_score
    )
    assert any("安全合规" in section.title for section in pack.project_proposal_outline)
    assert "交付质量自审" in pack.export_markdown
    assert "主张—证据账本与一致性检查" in pack.export_markdown
    assert "语义挑战者审查记录" in pack.export_markdown
    assert "四类专用文档编译器" in pack.export_markdown
    assert "解决方案架构就绪度" in pack.export_markdown
    assert "架构蓝图" in pack.export_markdown
    assert "解决方案架构师工作台" in pack.export_markdown
    assert "干系人问题地图" in pack.export_markdown
    assert "能力到架构矩阵" in pack.export_markdown
    assert "ADR 架构决策记录" in pack.export_markdown
    assert "集成依赖诊断" in pack.export_markdown
    assert "架构交付导出包" in pack.export_markdown
    assert "客户技术 workshop 议程" in pack.export_markdown
    assert "QAW / ATAM / ADR / C4 架构决策工程" in pack.export_markdown
    assert "Proof of Architecture 与验收证据" in pack.export_markdown


def test_solution_delivery_pack_uses_local_industry_skill_without_inflating_project_evidence(tmp_path, monkeypatch) -> None:
    source_root = tmp_path / "行业资讯"
    source_root.mkdir()
    (source_root / "2026中国旅游AI营销白皮书.pdf").write_bytes(b"fixture")
    def fake_analyze(path, *, ocr_binary=None):
        text = "文旅景区游客旅程、内容生产与营销转化需要结合高峰期服务保障和内容版权。"
        return LocalDocumentAnalysis(
            extraction_status="full_text_analyzed",
            source_format="pdf",
            total_unit_count=2,
            extracted_unit_count=2,
            content_char_count=len(text),
            units=[LocalContentUnit(ordinal=1, locator="第 1 页", text=text)],
            full_text=text,
        )

    monkeypatch.setattr(industry_skill_library, "analyze_document_content", fake_analyze)
    output_dir = tmp_path / "industry-skills"
    build_industry_skill_library(source_root=source_root, library_dir=output_dir, workers=1, build_rag=False)
    monkeypatch.setenv("INDUSTRY_SKILL_CATALOG_PATH", str(output_dir / "catalog.json"))

    baseline = build_solution_delivery_pack(
        _report(),
        scenario="文旅AIGC平台",
        target_customer="某文旅集团",
        vertical_scene="景区数字人导览",
        use_industry_skills=False,
    )
    pack = build_solution_delivery_pack(
        _report(),
        scenario="文旅AIGC平台",
        target_customer="某文旅集团",
        vertical_scene="景区数字人导览",
    )

    assert pack.industry_skill_context.status == "available"
    assert any(skill.industry == "tourism_hospitality" for skill in pack.industry_skill_context.selected_skills)
    assert pack.source_support_score == baseline.source_support_score
    assert any(section.title == "行业资料技能与规范性要求" for section in pack.feasibility_outline)
    assert all(
        any(section.title == "行业资料技能与规范性要求" for section in document.sections)
        for document in pack.compiled_documents
    )
    assert "本地行业资料技能" in pack.export_markdown
    assert "不计入公开来源支撑度" in pack.export_markdown


def test_solution_delivery_pack_passes_explicit_retrieval_strategy_to_local_skill_context(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_context(**kwargs):
        captured.update(kwargs)
        from app.schemas.research import ResearchIndustrySkillContextOut

        return ResearchIndustrySkillContextOut(
            status="not_selected",
            query="fixture",
            retrieval_strategy=kwargs["retrieval_strategy"],
            retrieval_strategy_label="候选 A：预过滤 + 标题加权",
        )

    monkeypatch.setattr("app.services.research_solution_intelligence_service.build_industry_skill_context", fake_context)
    pack = build_solution_delivery_pack(
        _report(),
        scenario="文旅AIGC平台",
        target_customer="某文旅集团",
        vertical_scene="景区数字人导览",
        industry_knowledge_retrieval_strategy="prefilter_weighted_hybrid",
    )

    assert captured["retrieval_strategy"] == "prefilter_weighted_hybrid"
    assert pack.industry_skill_context.retrieval_strategy == "prefilter_weighted_hybrid"


def test_solution_delivery_pack_passes_fixed_retrieval_scope_to_local_skill_context(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_context(**kwargs):
        captured.update(kwargs)
        from app.schemas.research import ResearchIndustrySkillContextOut

        return ResearchIndustrySkillContextOut(status="not_selected", query="fixture")

    monkeypatch.setattr("app.services.research_solution_intelligence_service.build_industry_skill_context", fake_context)
    build_solution_delivery_pack(
        _report(),
        scenario="政务数据开放",
        industry_knowledge_retrieval_industries=["government_public"],
        industry_knowledge_retrieval_document_types=["policy_standard"],
    )

    assert captured["retrieval_industries"] == ["government_public"]
    assert captured["retrieval_document_types"] == ["policy_standard"]


def test_delivery_review_route_generates_strategy_isolated_artifacts(tmp_path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from app.api import research as research_api
    from app.main import app
    from app.schemas.research import ResearchIndustrySkillContextOut

    report = _report().model_copy(
        update={
            "research_evidence_gate": ResearchEvidenceGateOut(
                enforced=True,
                status="evidence_ready",
                passed=True,
                formal_report_allowed=True,
                solution_delivery_allowed=True,
                accepted_source_count=2,
                official_source_count=1,
                unique_domain_count=2,
                question_coverage_percent=100,
            ),
            "research_citation_gate": ResearchCitationGateOut(enforced=True, status="pass", passed=True),
            "report_readiness": ResearchReportReadinessOut(
                status="ready", score=90, actionable=True, evidence_gate_passed=True
            ),
        }
    )
    monkeypatch.setattr(
        research_api,
        "load_industry_knowledge_retrieval_benchmark_dataset",
        lambda: ({}, [type("Case", (), {"case_id": "case-a", "query": "景区 AIGC 导览", "industries": ("tourism_hospitality",), "document_types": ("whitepaper",)})()]),
    )
    monkeypatch.setattr(research_api, "resolve_library_dir", lambda: tmp_path / "industry-skills")
    monkeypatch.setattr(research_api, "register_industry_knowledge_delivery_review_artifacts", lambda **_kwargs: [])

    def unavailable_industry_context(*, retrieval_strategy, **_kwargs):
        return ResearchIndustrySkillContextOut(
            status="unavailable",
            query="fixture",
            retrieval_strategy=retrieval_strategy,
            retrieval_strategy_label="",
            rerank_backend="unavailable",
        )

    # The label written into a review artifact is a versioned strategy-catalog
    # fact, not a property of an optional local industry library.  Force the
    # no-library state so this test stays deterministic in a clean CI checkout.
    monkeypatch.setattr(
        "app.services.research_solution_intelligence_service.build_industry_skill_context",
        unavailable_industry_context,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/research/industry-skills/retrieval-ranking-benchmark/delivery-review",
            json={"case_id": "case-a", "report": report.model_dump(mode="json")},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert {artifact["strategy"] for artifact in payload["artifacts"]} == {
        "baseline_hybrid",
        "prefilter_weighted_hybrid",
        "prefilter_weighted_rerank",
    }
    paths = [artifact["report_artifact_path"] for artifact in payload["artifacts"]]
    assert all(path.startswith("../") is False for path in paths)
    assert all(not path.startswith(str(tmp_path)) for path in paths)
    assert all(path.endswith(".md") for path in paths)
    artifact_root = tmp_path / "industry-knowledge-retrieval-ranking-ab-v1" / "delivery-review" / "case-a"
    absolute_paths = [next(artifact_root.rglob(Path(path).name)) for path in paths]
    assert all(path.is_file() for path in absolute_paths)
    candidate_a = next(path for path in absolute_paths if path.name == "prefilter_weighted_hybrid.md")
    assert "候选 A：预过滤 + 标题加权" in candidate_a.read_text(encoding="utf-8")
