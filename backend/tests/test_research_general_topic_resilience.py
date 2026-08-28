from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.research import (
    ResearchEvidenceGateOut,
    ResearchEntityEvidenceOut,
    ResearchRankedEntityOut,
    ResearchReportResponse,
    ResearchReportSectionOut,
    ResearchSourceDiagnosticsOut,
    ResearchSourceOut,
)
from app.services.research.candidate_profile_enrichment import (
    _candidate_profile_enrichment_requested,
    _topical_profile_sources,
)
from app.services.research.company_source_enrichment import _company_enrichment_seed_names
from app.services.research.evidence_governance import (
    apply_evidence_governance_diagnostics,
    build_evidence_gap_report,
    build_research_claim_governance,
    build_research_evidence_governance,
    build_research_question_tree,
    build_research_scope_contract,
)
from app.services.research.evidence_expansion import _requires_company_convergence
from app.services.research.report_assembly import _stabilize_report_header
from app.services.research.scope_hints import infer_input_scope_hints, merge_scope_hints
from app.services.research.entity_heuristics import filter_sources_by_theme_relevance
from app.services.research.source_documents import SourceDocument, source_documents_to_research_source_outputs
from app.services.research_job_store import (
    _progress_callback,
    _report_payload_needs_evidence,
    _research_job_completion_state,
)
from app.services.research_service import _build_query_plan
from app.services.research_rag_quality_service import build_retrieval_correction_profile


GOVERNMENT_TOPIC = "2026年长三角地区政府行业AI需求调研及潜在需求情报搜集并分析"


def _source(title: str, text: str, *, domain: str, tier: str = "media") -> SourceDocument:
    return SourceDocument(
        title=title,
        url=f"https://{domain}/article",
        domain=domain,
        snippet=text,
        search_query="长三角 政务云 人工智能",
        source_type="policy" if tier == "official" else "web",
        content_status="extracted",
        excerpt=text,
        source_label=domain,
        source_tier=tier,
    )


def test_government_topic_is_locked_before_generic_ai_and_uses_short_recall_queries() -> None:
    scope = infer_input_scope_hints(GOVERNMENT_TOPIC, None)

    assert scope["regions"] == ["长三角"]
    assert scope["industries"] == ["政务云"]
    assert scope["industry_methodology_profile"] == "政务云"
    assert str(scope["strategy_scope_summary"]).startswith("公共部门数字化项目调研框架")

    queries = _build_query_plan(
        GOVERNMENT_TOPIC,
        None,
        False,
        scope_hints=scope,
        limit=8,
    )

    assert queries[:5] == [
        "长三角 数字政府 人工智能 政务服务",
        "上海 数字政府 人工智能 政务服务",
        "江苏 数字政府 人工智能 政务服务",
        "site:gov.cn 上海 数字政府 人工智能 政务服务",
        "site:ccgp.gov.cn 上海 政务云 人工智能",
    ]
    assert all(GOVERNMENT_TOPIC not in query for query in queries)
    assert all(len(query) <= 96 for query in queries)


def test_government_question_recovery_queries_cover_all_axes_without_the_full_prompt() -> None:
    scope = infer_input_scope_hints(GOVERNMENT_TOPIC, None)
    contract = build_research_scope_contract(
        keyword=GOVERNMENT_TOPIC,
        research_focus=None,
        research_mode="deep",
        scope_hints=scope,
    )
    tree = build_research_question_tree(contract=contract, scope_hints=scope)
    correction = build_retrieval_correction_profile(
        [],
        keyword=GOVERNMENT_TOPIC,
        scope_hints=scope,
        corrective_query_limit=8,
    )

    assert len(tree.corrective_queries) == 12
    assert all(GOVERNMENT_TOPIC not in query for query in tree.corrective_queries)
    assert all(len(query) <= 72 for query in tree.corrective_queries)
    assert [node.axis for node in tree.questions] == [
        "需求与范围",
        "政策与市场",
        "账户与招采",
        "方案与竞争",
        "投入与交付",
        "风险与反证",
    ]
    assert all(GOVERNMENT_TOPIC not in query for query in correction.corrective_queries)
    assert all(len(query) <= 96 for query in correction.corrective_queries)


def test_locked_topic_rejects_strategy_model_industry_drift() -> None:
    scope = infer_input_scope_hints(GOVERNMENT_TOPIC, None)

    merged = merge_scope_hints(
        scope,
        {
            "industries": ["数据中心"],
            "company_anchors": ["中兴通讯"],
            "prefer_company_entities": True,
            "prefer_head_companies": True,
            "strategy_scope_summary": "算力与基础设施投资调研框架",
            "strategy_must_include_terms": ["服务器", "算力"],
            "strategy_query_expansions": [
                "长三角 智算中心 服务器 采购",
                "长三角 数字政府 人工智能 采购",
            ],
        },
    )

    assert merged["industries"] == ["政务云"]
    assert str(merged["strategy_scope_summary"]).startswith("公共部门数字化项目调研框架")
    assert "服务器" not in merged["strategy_must_include_terms"]
    assert "长三角 智算中心 服务器 采购" not in merged["strategy_query_expansions"]
    assert "长三角 数字政府 人工智能 采购" in merged["strategy_query_expansions"]
    assert merged["prefer_company_entities"] is False
    assert merged["prefer_head_companies"] is False
    assert merged["company_anchors"] == []


def test_broad_industry_scope_does_not_trigger_candidate_company_profile_search() -> None:
    scope = infer_input_scope_hints(GOVERNMENT_TOPIC, None)

    assert _candidate_profile_enrichment_requested(scope) is False
    assert _candidate_profile_enrichment_requested({"clients": ["无锡市数据局"]}) is True


def test_report_source_keeps_extracted_body_when_search_snippet_is_only_a_date() -> None:
    source = _source(
        "招投标监管数字化实践",
        "2022年12月6日",
        domain="cecbid.org.cn",
    )
    source.excerpt = "开发建设数字侦探评标系统，并公开查处案件数量和处罚金额。"

    output = source_documents_to_research_source_outputs([source])[0]

    assert "数字侦探" in output.snippet
    assert output.snippet != source.snippet


def test_unlisted_industries_receive_a_generic_decision_methodology() -> None:
    vehicle = infer_input_scope_hints("2026年全国新能源汽车行业AI应用需求与竞争格局分析", None)
    pet = infer_input_scope_hints("华东宠物经济市场趋势和渠道机会研究", None)

    assert vehicle["industries"] == ["新能源汽车"]
    assert vehicle["industry_methodology_profile"] == "新能源汽车"
    assert "采购和投资" in str(vehicle["industry_methodology_framework"])
    assert pet["regions"] == ["华东"]
    assert pet["industries"] == ["宠物经济"]
    assert pet["industry_methodology_profile"] == "宠物经济"


def test_government_evidence_is_not_rejected_as_an_unrelated_vertical() -> None:
    scope = infer_input_scope_hints(GOVERNMENT_TOPIC, None)
    sources = [
        _source("上海数字政府人工智能行动方案", "上海数字政府人工智能应用场景、政策规划、试点和数据安全要求。", domain="sh.gov.cn", tier="official"),
        _source("江苏政务大模型采购意向", "采购人：江苏省数据局。该局发布政务大模型平台采购意向、预算和招标项目。", domain="ccgp.gov.cn", tier="official"),
        _source("浙江智慧政务平台中标公告", "浙江智慧政务平台系统中标，披露厂商、项目和交付周期。", domain="ggzy.gov.cn", tier="official"),
        _source("安徽电子政务需求调研", "安徽电子政务在公共服务、城市治理和业务运营场景的需求与痛点。", domain="ah-research.cn"),
        _source("数字政府投入产出测算", "长三角数字政府项目投资成本、实施周期、运维绩效、收益和扩容路径。", domain="economics.cn"),
        _source("政务AI安全合规指南", "政务人工智能涉及数据安全、隐私、模型审计、风险和合规限制。", domain="security.cn", tier="official"),
        _source("政务AI竞争与生态", "政务AI产品、平台、解决方案、厂商竞争、案例与生态伙伴合作。", domain="market.cn"),
        _source("政务服务智能化交付复盘", "数字政府系统集成、项目交付、运维和二期扩容的实践案例。", domain="delivery.cn"),
    ]

    result = build_research_evidence_governance(
        sources,
        keyword=GOVERNMENT_TOPIC,
        research_focus=None,
        research_mode="deep",
        scope_hints=scope,
    )

    assert result.gate.status == "evidence_ready"
    assert result.gate.accepted_source_count == 8
    assert result.gate.official_source_count == 4
    assert result.question_tree.coverage_percent == 100


def test_strategy_exact_terms_do_not_collapse_broader_industry_alias_sources() -> None:
    scope = infer_input_scope_hints(GOVERNMENT_TOPIC, None)
    scope["strategy_must_include_terms"] = ["政务云"]
    sources = [
        _source("上海政务云建设方案", "采购人：上海市大数据中心。项目包含政务云平台建设、采购预算和数据安全要求。", domain="sh.gov.cn", tier="official"),
        _source("江苏数字政府行动计划", "江苏数字政府应用场景、政策规划和试点任务。", domain="js.gov.cn", tier="official"),
        _source("浙江智慧政务采购公告", "浙江智慧政务系统采购、中标厂商和交付周期。", domain="zj.gov.cn", tier="official"),
        _source("安徽电子政务需求调研", "安徽电子政务公共服务场景、部门需求和业务痛点。", domain="ah.gov.cn"),
        _source("长三角数字政府投入测算", "数字政府项目投资成本、实施周期、运维绩效和扩容路径。", domain="economics.cn"),
        _source("政务人工智能安全指南", "政府部门人工智能涉及数据安全、审计、风险和合规限制。", domain="security.cn", tier="official"),
        _source("智慧政务竞争生态", "智慧政务产品、平台厂商、竞品案例和生态伙伴合作。", domain="market.cn"),
        _source("政务服务智能化复盘", "政务服务系统集成、项目交付、运维和二期扩容实践。", domain="delivery.cn"),
    ]

    filtered = filter_sources_by_theme_relevance(
        sources,
        theme_terms=["政务云", "数字政府", "智慧政务", "电子政务", "政务服务", "政府部门"],
        scope_hints=scope,
        company_anchor_terms=[],
    )
    governance = build_research_evidence_governance(
        filtered,
        keyword=GOVERNMENT_TOPIC,
        research_focus=None,
        research_mode="deep",
        scope_hints=scope,
    )

    assert len(filtered) == 8
    assert governance.gate.status == "evidence_ready"


def test_broad_industry_topic_does_not_inject_preconfigured_vendor_seeds() -> None:
    scope = infer_input_scope_hints(GOVERNMENT_TOPIC, None)

    broad_seeds = _company_enrichment_seed_names(
        input_scope_hints=scope,
        scope_hints=scope,
        company_anchor_terms=[],
        theme_seed_companies=["阿里云", "腾讯云", "中兴通讯"],
        dedupe_strings=lambda values, limit: list(dict.fromkeys(values))[:limit],
    )
    focused_seeds = _company_enrichment_seed_names(
        input_scope_hints={**scope, "clients": ["上海市数据局"]},
        scope_hints={**scope, "clients": ["上海市数据局"]},
        company_anchor_terms=["上海市数据局"],
        theme_seed_companies=["阿里云", "腾讯云"],
        dedupe_strings=lambda values, limit: list(dict.fromkeys(values))[:limit],
    )

    assert broad_seeds == []
    assert focused_seeds[:3] == ["上海市数据局", "阿里云", "腾讯云"]


def test_model_inferred_company_focus_cannot_override_broad_user_intent() -> None:
    explicit_scope = infer_input_scope_hints(GOVERNMENT_TOPIC, None)
    model_augmented_scope = {
        **explicit_scope,
        "prefer_company_entities": True,
        "company_anchors": ["中兴通讯"],
        "seed_companies": ["中兴通讯", "阿里云"],
    }

    seeds = _company_enrichment_seed_names(
        input_scope_hints=explicit_scope,
        scope_hints=model_augmented_scope,
        company_anchor_terms=["中兴通讯"],
        theme_seed_companies=["阿里云", "腾讯云"],
        dedupe_strings=lambda values, limit: list(dict.fromkeys(values))[:limit],
    )

    assert seeds == []
    assert _requires_company_convergence(explicit_scope) is False
    assert _requires_company_convergence(model_augmented_scope) is True


def test_evidence_gap_is_terminal_and_contains_diagnostics_instead_of_empty_success() -> None:
    scope = infer_input_scope_hints(GOVERNMENT_TOPIC, None)
    governance = build_research_evidence_governance(
        [_source("泛AI行业观察", "人工智能行业趋势综述。", domain="media.example")],
        keyword=GOVERNMENT_TOPIC,
        research_focus=None,
        research_mode="deep",
        scope_hints=scope,
    )
    diagnostics = apply_evidence_governance_diagnostics(ResearchSourceDiagnosticsOut(), governance)
    report = build_evidence_gap_report(
        keyword=GOVERNMENT_TOPIC,
        research_focus=None,
        output_language="zh-CN",
        research_mode="deep",
        query_plan=["长三角 政务云 人工智能"],
        governance=governance,
        source_diagnostics=diagnostics,
    )

    status, stage, message = _research_job_completion_state(report)

    assert status == "needs_evidence"
    assert stage == "needs_evidence"
    assert "正式研报未生成" in message
    assert report.sections[0].title == "本轮检索诊断"
    assert report.sections[1].title == "候选证据复核清单"
    assert report.sections[1].items
    assert _report_payload_needs_evidence(report.model_dump(mode="json")) is True


def test_invalid_pages_and_static_identity_seeds_do_not_become_topic_evidence() -> None:
    scope = infer_input_scope_hints(GOVERNMENT_TOPIC, None)
    invalid = _source(
        "404",
        "长三角政务云人工智能需求、采购、项目、方案、投资和安全合规。",
        domain="vendor.example",
        tier="official",
    )
    governance = build_research_evidence_governance(
        [invalid],
        keyword=GOVERNMENT_TOPIC,
        research_focus=None,
        research_mode="deep",
        scope_hints=scope,
    )

    assert governance.gate.accepted_source_count == 0
    assert governance.admissions[0].decision == "rejected"
    assert "页面无效" in governance.admissions[0].reasons[0]

    invalid_procurement = _source(
        "错误页面！中国政府采购网",
        "主办单位：财政部国库司。网站标识码与版权信息。",
        domain="ccgp.gov.cn",
        tier="official",
    )
    invalid_procurement.url = "https://www.ccgp.gov.cn/cggg/dfgg/example.htm"
    invalid_procurement_governance = build_research_evidence_governance(
        [invalid_procurement],
        keyword=GOVERNMENT_TOPIC,
        research_focus=None,
        research_mode="deep",
        scope_hints=scope,
    )

    assert invalid_procurement_governance.admissions[0].decision == "rejected"
    assert "页面无效" in invalid_procurement_governance.admissions[0].reasons[0]

    identity_seed = _source(
        "中兴通讯官网",
        "中兴通讯官方公开入口。",
        domain="zte.com.cn",
        tier="official",
    )
    identity_seed.url = "https://www.zte.com.cn/"
    identity_seed.search_query = f"{GOVERNMENT_TOPIC} 中兴通讯 官方公开入口"
    identity_seed.snippet = "中兴通讯 官方公开入口，优先用于补充官网、IR、公开业务联系渠道"
    topical_case = _source(
        "中兴通讯数字政府案例",
        "中兴通讯为南京数字政府项目提供政务云人工智能平台。",
        domain="zte.com.cn",
        tier="official",
    )
    topical_case.url = "https://www.zte.com.cn/government/case"

    assert _topical_profile_sources(
        [identity_seed, topical_case],
        seed_profile_urls={identity_seed.url},
    ) == [topical_case]

    identity_governance = build_research_evidence_governance(
        [identity_seed],
        keyword=GOVERNMENT_TOPIC,
        research_focus=None,
        research_mode="deep",
        scope_hints=scope,
    )
    assert identity_governance.admissions[0].decision == "rejected"
    assert "只用于实体核验" in identity_governance.admissions[0].reasons[0]

    topical_case.search_query = f"{GOVERNMENT_TOPIC} 中兴通讯 官方公开入口"
    topical_case_governance = build_research_evidence_governance(
        [topical_case],
        keyword=GOVERNMENT_TOPIC,
        research_focus=None,
        research_mode="deep",
        scope_hints=scope,
    )
    assert topical_case_governance.admissions[0].decision == "accepted"

    institution_home = _source(
        "上海市数据局",
        "上海市数据局负责数字政府、政务云、人工智能、采购、项目和数据安全工作。",
        domain="sdb.sh.gov.cn",
        tier="official",
    )
    institution_home.url = "https://sdb.sh.gov.cn/"
    unresolved_news = _source(
        "Google News",
        "长三角数字政府人工智能政务服务改革项目。",
        domain="news.google.com",
    )
    unresolved_news.url = "https://news.google.com/rss/articles/example?oc=5"
    static_governance = build_research_evidence_governance(
        [institution_home, unresolved_news],
        keyword=GOVERNMENT_TOPIC,
        research_focus=None,
        research_mode="deep",
        scope_hints=scope,
    )

    assert [row.decision for row in static_governance.admissions] == ["rejected", "rejected"]
    assert "只用于实体核验" in static_governance.admissions[0].reasons[0]
    assert "聚合跳转页" in static_governance.admissions[1].reasons[0]


def test_job_progress_does_not_move_backwards(monkeypatch) -> None:
    updates: list[int] = []

    def capture_update(_job_id: str, **changes: object) -> None:
        updates.append(int(changes["progress_percent"]))

    monkeypatch.setattr("app.services.research_job_store.update_research_job", capture_update)
    callback = _progress_callback("job-id")
    callback("corrective", 74, "正在执行纠错检索")
    callback("question_recovery", 68, "正在按证据缺口逐题补检")

    assert updates == [74, 74]


def test_advice_does_not_count_as_an_unsupported_factual_citation() -> None:
    statement = "南京市数据局于2025年启动政务人工智能试点"
    source = ResearchSourceOut(
        title="南京政务人工智能试点公告",
        url="https://www.nanjing.gov.cn/ai-pilot",
        domain="www.nanjing.gov.cn",
        snippet=statement,
        search_query="南京 政务 人工智能 试点",
        source_type="policy",
        content_status="extracted",
        source_label="南京市政府",
        source_tier="official",
    )
    report = ResearchReportResponse(
        keyword="南京政务人工智能",
        report_title="南京政务人工智能调研",
        executive_summary=statement,
        consulting_angle="用于需求分析。",
        sections=[
            ResearchReportSectionOut(
                title="解决方案设计建议",
                items=["投标前须以甲方等保、密码应用和数据管理制度为准。"],
                evidence_links=[
                    ResearchEntityEvidenceOut(
                        title=source.title,
                        url=source.url,
                        source_label=source.source_label,
                        source_tier="official",
                        excerpt=source.snippet,
                    )
                ],
            )
        ],
        source_count=1,
        sources=[source],
        generated_at=datetime.now(timezone.utc),
    )

    result = build_research_claim_governance(report)

    assert result.ledger.claim_count == 2
    assert result.citation_gate.claim_count == 1
    assert result.citation_gate.citation_completeness_percent == 100
    assert result.citation_gate.status == "pass"


def test_citation_marker_is_not_a_claim_and_richer_source_excerpt_wins_url_deduplication() -> None:
    statement = "上海方案提出集中纳管高频算法模型超100个、数源目录超200个"
    source = ResearchSourceOut(
        title="上海智慧好办实施方案",
        url="https://www.shanghai.gov.cn/smart-service",
        domain="www.shanghai.gov.cn",
        snippet=f"到2025年底，{statement}，并统筹算力支撑。",
        search_query="上海 智慧好办 算法模型 数源目录",
        source_type="policy",
        content_status="extracted",
        source_label="上海市政府",
        source_tier="official",
    )
    report = ResearchReportResponse(
        keyword="上海政务人工智能",
        report_title="上海政务人工智能调研",
        executive_summary=f"{statement}。【官方：上海市政府，2024】",
        consulting_angle="用于需求分析。",
        sections=[
            ResearchReportSectionOut(
                title="关键信号",
                items=[statement],
                evidence_links=[
                    ResearchEntityEvidenceOut(
                        title=source.title,
                        url=source.url,
                        source_label=source.source_label,
                        source_tier="official",
                        excerpt="上海市政府公开文件",
                    )
                ],
            )
        ],
        source_count=1,
        sources=[source],
        generated_at=datetime.now(timezone.utc),
    )

    result = build_research_claim_governance(report)

    assert result.ledger.claim_count == 2
    assert result.citation_gate.claim_count == 2
    assert result.citation_gate.supported_claim_count == 2
    assert result.citation_gate.status == "pass"


def test_risk_controls_and_verification_actions_are_not_treated_as_unsupported_facts() -> None:
    statement = "上海市数据局于2025年启动政务人工智能试点"
    source = ResearchSourceOut(
        title="上海政务人工智能试点公告",
        url="https://www.shanghai.gov.cn/ai-pilot",
        domain="www.shanghai.gov.cn",
        snippet=statement,
        search_query="上海 政务 人工智能 试点",
        source_type="policy",
        content_status="extracted",
        source_label="上海市政府",
        source_tier="official",
    )
    report = ResearchReportResponse(
        keyword="上海政务人工智能",
        report_title="上海政务人工智能调研",
        executive_summary=statement,
        consulting_angle="用于需求分析。",
        sections=[
            ResearchReportSectionOut(
                title="风险提示",
                items=[
                    "任何金额区间均需在财政预算、可研批复或采购公告中补证。",
                    "需反查历年合同起止时间与框架协议到期日。",
                    "不能将区域整体判断等同于各城市均已有项目窗口。",
                    "该目标完成后的模型运营是2026年续建机会。",
                    "因此本报告将其定义为高潜需求地图，而非完整市场规模测算。",
                    "上海方案给出了明确能力指标，但当前未披露对应采购金额。",
                    "不能据此估算市级项目规模。",
                    "当前未发现对应项目包、项目阶段或采购主体。",
                    "政策牵引强于单一技术采购。",
                ],
            )
        ],
        source_count=1,
        sources=[source],
        generated_at=datetime.now(timezone.utc),
    )

    result = build_research_claim_governance(report)

    assert result.ledger.claim_count == 10
    assert result.citation_gate.claim_count == 1
    assert result.citation_gate.status == "pass"


def test_repeated_or_mismatched_summary_is_rebuilt_from_evidenced_sections() -> None:
    repeated = "公开证据集中在某机构的算力项目与生态活动，需要进一步核验是否属于政务采购。"
    report = ResearchReportResponse(
        keyword=GOVERNMENT_TOPIC,
        report_title="长三角｜政务大模型｜中共江苏省委：招标窗口与推进路径",
        executive_summary=f"优先把中共江苏省委列为首批推进对象。{repeated}{repeated}",
        consulting_angle="用于需求分析。",
        sections=[
            ResearchReportSectionOut(
                title="行业资讯判断",
                items=["长三角政务AI需求正从单点模型转向算力、数据、模型管理与安全治理协同建设。"],
                evidence_count=1,
                evidence_links=[
                    ResearchEntityEvidenceOut(
                        title="南京数字政府人工智能公告",
                        url="https://www.nanjing.gov.cn/ai",
                        source_label="南京市政府",
                        source_tier="official",
                    )
                ],
            )
        ],
        top_target_accounts=[ResearchRankedEntityOut(name="南京市数据局", score=80)],
        source_count=1,
        source_diagnostics=ResearchSourceDiagnosticsOut(
            scope_regions=["长三角"],
            scope_industries=["政务云"],
        ),
        generated_at=datetime.now(timezone.utc),
    )

    stabilized = _stabilize_report_header(report)

    assert stabilized.report_title == "长三角政务云AI需求与机会调研"
    assert stabilized.executive_summary.startswith("长三角政务AI需求正从单点模型")
    assert stabilized.executive_summary.count(repeated) == 0


def test_government_office_title_is_rebuilt_when_it_is_not_a_verified_target() -> None:
    report = ResearchReportResponse(
        keyword=GOVERNMENT_TOPIC,
        report_title="长三角｜政务大模型｜上海市人民政府办公厅：扩容窗口与推进路径",
        executive_summary="无锡市城运中心和无锡市数据局具有可核验的项目需求。",
        consulting_angle="用于需求分析。",
        top_target_accounts=[
            ResearchRankedEntityOut(name="无锡市城运中心", score=88),
            ResearchRankedEntityOut(name="无锡市数据局", score=82),
        ],
        source_count=8,
        source_diagnostics=ResearchSourceDiagnosticsOut(
            scope_regions=["长三角"],
            scope_industries=["政务云"],
        ),
        generated_at=datetime.now(timezone.utc),
    )

    stabilized = _stabilize_report_header(report)

    assert stabilized.report_title == "长三角政务云AI需求与机会调研"


def test_evidence_ready_report_replaces_diagnostic_consulting_angle_with_substantive_content() -> None:
    solution = "围绕高频政务事项建设可追溯的知识治理、流程编排、模型推理与安全审计闭环。"
    report = ResearchReportResponse(
        keyword=GOVERNMENT_TOPIC,
        report_title="长三角政务云AI需求与机会调研",
        executive_summary="已形成证据支持的行业判断。",
        consulting_angle="请先并行补齐三类材料，随后再推进标题收敛。",
        sections=[
            ResearchReportSectionOut(
                title="解决方案设计建议",
                items=[solution],
                evidence_count=2,
            )
        ],
        source_count=8,
        research_evidence_gate=ResearchEvidenceGateOut(
            enforced=True,
            status="evidence_ready",
            passed=True,
            formal_report_allowed=True,
        ),
        generated_at=datetime.now(timezone.utc),
    )

    stabilized = _stabilize_report_header(report)

    assert stabilized.consulting_angle == solution

    variant = report.model_copy(
        update={
            "consulting_angle": (
                "并行补齐区域与采购信号，基于 current_report 重写标题，"
                "避免泛化表达。建议先补关键证据。"
            )
        }
    )

    assert _stabilize_report_header(variant).consulting_angle == solution


def test_placeholder_report_title_is_rebuilt_from_locked_scope() -> None:
    for placeholder in (
        "待补充范围与证据：无法收敛研究标题",
        "研究范围与目标客户尚未明确：待基于结构化证据收敛",
        "证据不足：待补充区域、场景与主体后收敛标题",
    ):
        report = ResearchReportResponse(
            keyword=GOVERNMENT_TOPIC,
            report_title=placeholder,
            executive_summary="已形成证据支持的行业判断。",
            consulting_angle="用于需求分析。",
            source_count=8,
            source_diagnostics=ResearchSourceDiagnosticsOut(
                scope_regions=["长三角"],
                scope_industries=["政务云"],
            ),
            generated_at=datetime.now(timezone.utc),
        )

        stabilized = _stabilize_report_header(report)

        assert stabilized.report_title == "长三角政务云AI需求与机会调研"
