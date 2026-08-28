from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.schemas.research import (
    ResearchEntityEvidenceOut,
    ResearchEntityGraphOut,
    ResearchNormalizedEntityOut,
    ResearchRankedEntityOut,
    ResearchReportResponse,
    ResearchSourceOut,
)
from app.services.research_job_store import _rewrite_legacy_report_for_read
from app.services.llm_parser import ResearchReportResult
from app.services.research.entity_authenticity import evaluate_organization_name
from app.services.research.entity_authenticity_gate import (
    enforce_report_entity_authenticity,
    sanitize_report_result_entities,
)
from app.services.research.entity_policy import is_plausible_entity_name
from app.services.research.entity_ranking_runtime import build_runtime_entity_graph, rank_runtime_top_entities
from app.services.research.organization_identity import extract_rank_entity_candidates
from app.services.research.source_documents import SourceDocument


def _source(text: str, *, title: str = "文旅人工智能公开资料") -> SourceDocument:
    return SourceDocument(
        title=title,
        url="https://www.mct.gov.cn/example/entity-authenticity",
        domain="mct.gov.cn",
        snippet=text,
        search_query="文旅 人工智能 机构",
        source_type="policy",
        content_status="body_acquired",
        excerpt=text,
        source_label="文化和旅游部",
        source_tier="official",
    )


@pytest.mark.parametrize(
    "value,expected_reason",
    [
        ("优化公共文化场馆智慧服务", "narrative_prefix"),
        ("在线平台游客评价数据开展智能", "narrative_fragment"),
        ("综合服务", "generic_service_phrase"),
        ("AI正从智能", "narrative_fragment"),
        ("数据智能", "generic_service_phrase"),
        ("文旅智能", "generic_service_phrase"),
        ("招标公司", "generic_legal_name_stem"),
        ("采购公司", "generic_legal_name_stem"),
        ("相关公司", "generic_legal_name_stem"),
        ("省文化广电和旅游厅", "missing_admin_jurisdiction"),
        ("市文化和旅游局", "missing_admin_jurisdiction"),
        ("智慧场馆建设", "generic_commercial_phrase"),
        ("文旅数字化项目", "generic_commercial_phrase"),
        ("正如腾讯集团", "narrative_prefix"),
        ("并充分发挥中国移动智算中心", "narrative_prefix"),
        ("三省一市人大常委", "collective_organization"),
        ("中央网信办和国家发展改革委", "compound_organization"),
        ("国家层面统一部署的各批次集成办", "narrative_fragment"),
        ("落实并持续优化国家层面统一部署的各批次集成办", "narrative_prefix"),
        ("省数据集团", "missing_legal_jurisdiction"),
        ("市城投集团", "missing_legal_jurisdiction"),
        ("以人民为中心", "narrative_prefix"),
        ("人才等市级部", "narrative_fragment"),
        ("新设立公司", "narrative_prefix"),
        ("社区三级服务中心（站）全部", "narrative_fragment"),
        ("已经市政府", "narrative_prefix"),
        ("各区人民政府", "collective_organization"),
        ("虹桥国际机场等区域外籍人员一站式综合服务中心", "narrative_fragment"),
        ("在姑苏区苏锦街道举办", "narrative_fragment"),
        ("姑苏区围绕数字政府", "narrative_fragment"),
        ("姑苏区正以步行15分钟距离为半径加快布局", "narrative_fragment"),
        ("涉及市级委", "narrative_prefix"),
        ("深化市级部门政务服务中心", "narrative_prefix"),
        ("确立全省一体化大数据中心", "narrative_prefix"),
        ("跨地区跨部", "narrative_prefix"),
        ("中国大学", "generic_service_phrase"),
        ("区）人民政府", "invalid_parentheses"),
        ("山东是国内第一家省级政府", "narrative_fragment"),
        ("山东省内各云中心", "narrative_fragment"),
        ("根据浪潮集团", "narrative_prefix"),
        ("浙江信镧建设工程咨询有限公司关于浙江省民政事业发展中心", "narrative_fragment"),
        ("点开无锡市政府", "narrative_prefix"),
    ],
)
def test_news_phrases_are_not_accepted_as_organizations(value: str, expected_reason: str) -> None:
    decision = evaluate_organization_name(value)

    assert decision.accepted is False
    assert decision.reason == expected_reason
    assert is_plausible_entity_name(value) is False


@pytest.mark.parametrize(
    "value,expected",
    [
        ("中国移动通信有限公司", "中国移动通信有限公司"),
        ("常州视感科技有限公司", "常州视感科技有限公司"),
        ("中旅数智科技（深圳）有限公司", "中旅数智科技（深圳）有限公司"),
        ("浙江省文化广电和旅游厅", "浙江省文化广电和旅游厅"),
        ("北京航空航天大学", "北京航空航天大学"),
        ("上海市文物交流中心", "上海市文物交流中心"),
        ("文化和旅游部", "文化和旅游部"),
        ("工业和信息化部", "工业和信息化部"),
        ("依托中国移动通信有限公司", "中国移动通信有限公司"),
        ("依托单位中国移动通信有限公司", "中国移动通信有限公司"),
        ("随着由无锡市数据局", "无锡市数据局"),
        ("上海市黄浦区数据局（上海市黄浦区信息化委员会", "上海市黄浦区数据局"),
        ("建议推荐上海信投智能科技股份有限公司", "上海信投智能科技股份有限公司"),
    ],
)
def test_real_organizations_and_relation_prefixes_are_accepted(value: str, expected: str) -> None:
    decision = evaluate_organization_name(value)

    assert decision.accepted is True
    assert decision.normalized_name == expected


@pytest.mark.parametrize("value", ["阿里云", "腾讯云", "神州数码", "掌阅科技", "光线传媒"])
def test_curated_real_brands_can_override_generic_commercial_suffixes(value: str) -> None:
    decision = evaluate_organization_name(
        value,
        known_names=(value,),
        trusted_known_names=(value,),
    )

    assert decision.accepted is True
    assert is_plausible_entity_name(value) is True


@pytest.mark.parametrize("value", ["智慧场馆建设", "文旅数字化项目"])
def test_scope_candidate_cannot_override_generic_concept_rules(value: str) -> None:
    decision = evaluate_organization_name(value, known_names=(value,))

    assert decision.accepted is False
    assert decision.reason == "generic_commercial_phrase"


def test_labeled_official_source_extracts_real_organizations_without_relation_prefixes() -> None:
    text = (
        "（三）依托单位：中国移动通信有限公司。"
        "（四）共建单位：北京航空航天大学、中旅数智科技（深圳）有限公司、南京途牛科技有限公司。"
    )

    candidates = extract_rank_entity_candidates(text)

    assert candidates == [
        "中国移动",
        "北京航空航天大学",
        "中旅数智科技（深圳）有限公司",
        "南京途牛科技有限公司",
    ]
    assert all(not item.startswith(("依托", "共建单位")) for item in candidates)


def test_news_action_phrases_do_not_enter_entity_graph_or_rankings() -> None:
    invalid_names = {
        "优化公共文化场馆智慧服务",
        "在线平台游客评价数据开展智能",
        "综合服务",
        "AI正从智能",
        "数据智能",
        "文旅智能",
    }
    source = _source(
        "对12345旅游投诉、在线平台游客评价数据开展智能分析，优化公共文化场馆智慧服务。"
        "当前，AI正从智能行程规划到全周期服务，重塑旅游行业规则。"
        "在人工智能+文旅服务方面，推广智能讲解、智能客服。"
    )
    scope_hints = {"regions": ["长三角"], "industries": ["文旅文博"], "clients": []}

    graph = build_runtime_entity_graph([source], scope_hints=scope_hints)
    top, pending = rank_runtime_top_entities(
        [source],
        role="competitor",
        output_language="zh-CN",
        scope_hints=scope_hints,
        theme_terms=["文旅", "人工智能", "智能"],
        entity_graph=graph,
        limit=3,
    )
    emitted_names = {
        *(entity.canonical_name for entity in graph.entities),
        *(entity.name for entity in top),
        *(entity.name for entity in pending),
    }

    assert invalid_names.isdisjoint(emitted_names)
    assert graph.entities == []


def test_entity_role_rankings_require_a_local_role_relation() -> None:
    source = _source(
        "由南京市数据局指导并负责统筹政务人工智能需求。"
        "苏州市国投集团总经理出席项目签约活动。"
        "腾讯云提供政务人工智能平台与解决方案。"
        "上海文广集团代表出席活动。",
        title="长三角政务人工智能项目动态",
    )
    scope_hints = {"regions": ["长三角"], "industries": ["政务云"], "clients": []}
    graph = build_runtime_entity_graph([source], scope_hints=scope_hints)

    targets, pending_targets = rank_runtime_top_entities(
        [source],
        role="target",
        output_language="zh-CN",
        scope_hints=scope_hints,
        theme_terms=["政务", "人工智能"],
        entity_graph=graph,
        limit=5,
    )
    competitors, pending_competitors = rank_runtime_top_entities(
        [source],
        role="competitor",
        output_language="zh-CN",
        scope_hints=scope_hints,
        theme_terms=["政务", "人工智能"],
        entity_graph=graph,
        limit=5,
    )

    target_names = {item.name for item in [*targets, *pending_targets]}
    competitor_names = {item.name for item in [*competitors, *pending_competitors]}
    assert "南京市数据局" in target_names
    assert "苏州市国投集团" not in target_names
    assert "腾讯云" in competitor_names
    assert "上海文广集团" not in competitor_names


def test_model_entity_fields_require_structure_and_source_support_before_ranking() -> None:
    source = _source(
        "依托单位：中国移动通信有限公司。"
        "共建单位：北京航空航天大学、中旅数智科技（深圳）有限公司。"
    )
    parsed = ResearchReportResult(
        target_accounts=["优化公共文化场馆智慧服务", "北京航空航天大学"],
        competitor_profiles=[
            "AI正从智能",
            "中国移动通信有限公司",
            "依托中国移动通信有限公司",
            "中旅数智科技（深圳）有限公司",
            "杭州未来科技有限公司",
        ],
        ecosystem_partners=["综合服务"],
    )

    cleaned, audit = sanitize_report_result_entities(parsed, sources=[source], scope_hints={})

    assert cleaned.target_accounts == []
    assert cleaned.competitor_profiles == ["中国移动", "中旅数智科技（深圳）有限公司"]
    assert cleaned.ecosystem_partners == []
    assert audit["rejected_count"] == 5
    assert audit["unsupported_count"] == 2
    assert any("AI正从智能" in sample for sample in audit["rejected_samples"])
    assert any("missing_source_support" in sample for sample in audit["rejected_samples"])


def test_explicit_scope_name_does_not_bypass_source_support() -> None:
    parsed = ResearchReportResult(target_accounts=["杭州未来科技有限公司"])

    cleaned, audit = sanitize_report_result_entities(
        parsed,
        sources=[],
        scope_hints={"clients": ["杭州未来科技有限公司"]},
    )

    assert cleaned.target_accounts == []
    assert audit["unsupported_count"] == 1
    assert audit["rejected_count"] == 1


def test_government_target_requires_buyer_or_owner_role_support() -> None:
    source = _source(
        "采购人信息 名称：上海市松江区政务服务中心。"
        "南京市数据局推进政务云项目建设。"
        "中央网信办联合印发《政务领域人工智能大模型部署应用指引》。"
        "三省一市人大常委会分别表决通过相关规定。",
        title="政务人工智能与采购信息",
    )
    parsed = ResearchReportResult(
        target_accounts=[
            "上海市松江区政务服务中心",
            "南京市数据局",
            "中央网信办",
            "三省一市人大常委",
            "中央网信办和国家发展改革委",
        ]
    )

    cleaned, audit = sanitize_report_result_entities(parsed, sources=[source], scope_hints={})

    assert cleaned.target_accounts == ["上海市松江区政务服务中心", "南京市数据局"]
    assert audit["rejected_count"] == 3
    assert any("missing_target_role_support" in sample for sample in audit["rejected_samples"])
    assert any("collective_organization" in sample for sample in audit["rejected_samples"])


def test_procurement_notice_title_supplies_target_role_support() -> None:
    source = _source(
        "为各部门提供机器学习、人工智能等数据分析能力。",
        title="苏州市信息中心关于苏州市级政务云数据中台项目招标公告",
    )
    parsed = ResearchReportResult(target_accounts=["苏州市信息中心"])

    cleaned, audit = sanitize_report_result_entities(parsed, sources=[source], scope_hints={})

    assert cleaned.target_accounts == ["苏州市信息中心"]
    assert audit["rejected_count"] == 0


def test_final_gate_recovers_target_from_graph_only_with_procurement_role_evidence() -> None:
    procurement_source = _source(
        "为各部门提供机器学习、人工智能等数据分析能力。",
        title="苏州市信息中心关于苏州市级政务云数据中台项目招标公告",
    )
    policy_source = SourceDocument(
        title="江苏省数据局发布政务人工智能应用动态",
        url="https://jszwb.jiangsu.gov.cn/example/policy",
        domain="jszwb.jiangsu.gov.cn",
        snippet="江苏省数据局发布政务人工智能应用动态。",
        search_query="江苏 政务 人工智能",
        source_type="policy",
        content_status="body_acquired",
        excerpt="江苏省数据局发布政务人工智能应用动态。",
        source_label="江苏省数据局",
        source_tier="official",
    )
    report = ResearchReportResponse(
        keyword="长三角政务人工智能",
        report_title="长三角政务人工智能研判",
        executive_summary="基于公开证据识别采购主体。",
        consulting_angle="以采购公告中的明确角色为准。",
        source_count=2,
        generated_at=datetime.now(timezone.utc),
        entity_graph=ResearchEntityGraphOut(
            entities=[
                ResearchNormalizedEntityOut(canonical_name="苏州市信息中心", entity_type="target", source_count=1),
                ResearchNormalizedEntityOut(canonical_name="江苏省数据局", entity_type="target", source_count=1),
            ],
            target_entities=[
                ResearchNormalizedEntityOut(canonical_name="苏州市信息中心", entity_type="target", source_count=1),
                ResearchNormalizedEntityOut(canonical_name="江苏省数据局", entity_type="target", source_count=1),
            ],
        ),
    )

    cleaned = enforce_report_entity_authenticity(
        report,
        source_documents=[procurement_source, policy_source],
        scope_hints={"industries": ["政务云"]},
    )

    assert cleaned.target_accounts == ["苏州市信息中心"]


def test_entity_gate_preserves_supported_peer_move_context_but_drops_context_without_an_organization() -> None:
    source = _source(
        "中国移动通信有限公司中标上海文旅智能导览项目，项目预算为一千万元。"
    )
    supported_move = "中国移动通信有限公司中标上海文旅智能导览项目，项目预算为一千万元。"
    parsed = ResearchReportResult(
        executive_summary="竞品侧出现 AI正从智能，准备针对AI正从智能形成差异化切口。",
        key_signals=["AI正从智能", "当前，AI正从智能行程规划到全周期服务。"],
        competitor_profiles=["AI正从智能", "中国移动通信有限公司"],
        winner_peer_moves=[supported_move, "在线平台游客评价数据开展智能"],
        competition_analysis=["AI正从智能：缺少可核验的公司主体。"],
    )

    cleaned, audit = sanitize_report_result_entities(parsed, sources=[source], scope_hints={})

    assert cleaned.competitor_profiles == ["中国移动"]
    assert cleaned.winner_peer_moves == [supported_move]
    assert "AI正从智能" not in cleaned.executive_summary
    assert "待核验机构" in cleaned.executive_summary
    assert cleaned.key_signals == ["当前，AI正从智能行程规划到全周期服务。"]
    assert cleaned.competition_analysis == []
    assert audit["rejected_count"] == 2

    canonicalized = parsed.model_copy(update={"competitor_profiles": []})
    cleaned_after_legacy_canonicalization, _ = sanitize_report_result_entities(
        canonicalized,
        sources=[source],
        scope_hints={},
        prior_audit=audit,
    )
    assert cleaned_after_legacy_canonicalization.key_signals == [
        "当前，AI正从智能行程规划到全周期服务。"
    ]
    assert cleaned_after_legacy_canonicalization.competition_analysis == []


def test_final_report_cannot_emit_invalid_entities_after_authenticity_gate() -> None:
    source = _source("中国移动通信有限公司参与文旅人工智能项目建设。")
    evidence = ResearchEntityEvidenceOut(
        title=source.title,
        url=source.url,
        source_label=source.source_label,
        source_tier="official",
    )
    report = ResearchReportResponse(
        keyword="长三角文旅人工智能",
        report_title="长三角文旅人工智能研判",
        executive_summary="竞品侧出现 AI正从智能，准备针对AI正从智能形成差异化切口。",
        consulting_angle="以真实机构和来源为准。",
        source_count=1,
        generated_at=datetime.now(timezone.utc),
        competitor_profiles=["AI正从智能", "中国移动通信有限公司"],
        top_target_accounts=[
            ResearchRankedEntityOut(name="优化公共文化场馆智慧服务", score=47, evidence_links=[evidence])
        ],
        top_competitors=[
            ResearchRankedEntityOut(name="中国移动通信有限公司", score=88, evidence_links=[evidence])
        ],
        top_ecosystem_partners=[
            ResearchRankedEntityOut(name="综合服务", score=41, evidence_links=[evidence])
        ],
        entity_graph=ResearchEntityGraphOut(
            entities=[
                ResearchNormalizedEntityOut(canonical_name="数据智能", source_count=1),
                ResearchNormalizedEntityOut(canonical_name="中国移动通信有限公司", source_count=1),
            ]
        ),
    )

    cleaned = enforce_report_entity_authenticity(
        report,
        source_documents=[source],
        scope_hints={},
    )

    assert cleaned.competitor_profiles == ["中国移动"]
    assert cleaned.top_target_accounts == []
    assert [entity.name for entity in cleaned.top_competitors] == ["中国移动"]
    assert cleaned.top_ecosystem_partners == []
    assert [entity.canonical_name for entity in cleaned.entity_graph.entities] == ["中国移动"]
    assert "AI正从智能" not in cleaned.executive_summary
    assert "待核验机构" in cleaned.executive_summary
    assert cleaned.research_entity_authenticity_gate.passed is True
    assert cleaned.research_entity_authenticity_gate.status == "pass"
    assert cleaned.research_entity_authenticity_gate.rejected_count == 4
    assert cleaned.source_diagnostics.entity_authenticity_gate_passed is True


def test_external_procurement_entity_cannot_survive_local_target_account_ranking() -> None:
    external_source = SourceDocument(
        title="烟台市文化和旅游局智慧文旅平台采购公告",
        url="https://www.yantai.gov.cn/procurement/tourism-ai",
        domain="yantai.gov.cn",
        snippet="采购人：烟台市文化和旅游局。现就智慧文旅人工智能平台项目公开招标。",
        search_query="烟台 文旅 人工智能 招标",
        source_type="procurement",
        content_status="body_acquired",
        excerpt="采购人：烟台市文化和旅游局。现就智慧文旅人工智能平台项目公开招标。",
        source_label="烟台市人民政府",
        source_tier="official",
    )
    evidence = ResearchEntityEvidenceOut(
        title=external_source.title,
        url=external_source.url,
        source_label=external_source.source_label,
        source_tier="official",
    )
    report = ResearchReportResponse(
        keyword="2026年长三角文旅人工智能商机调研",
        report_title="长三角文旅人工智能商机调研",
        executive_summary="外地采购公告不得成为长三角目标账户。",
        consulting_angle="按本地采购主体核验。",
        source_count=1,
        generated_at=datetime.now(timezone.utc),
        top_target_accounts=[
            ResearchRankedEntityOut(name="烟台市文化和旅游局", score=92, evidence_links=[evidence])
        ],
        target_accounts=["烟台市文化和旅游局"],
    )

    cleaned = enforce_report_entity_authenticity(
        report,
        source_documents=[external_source],
        scope_hints={"regions": ["长三角"], "industries": ["文旅文博"]},
    )

    assert cleaned.top_target_accounts == []
    assert cleaned.target_accounts == []
    assert any("missing_local_target_role_support" in sample for sample in cleaned.research_entity_authenticity_gate.rejected_samples)


def test_legacy_job_read_rebuilds_sections_before_returning_an_ungated_report() -> None:
    report = ResearchReportResponse(
        keyword="长三角文旅人工智能",
        report_title="长三角文旅人工智能研判",
        executive_summary="竞品侧出现 AI正从智能。",
        consulting_angle="以真实机构和来源为准。",
        source_count=1,
        generated_at=datetime.now(timezone.utc),
        competitor_profiles=["AI正从智能", "中国移动通信有限公司"],
        winner_peer_moves=["在线平台游客评价数据开展智能"],
        sections=[{"title": "竞品公司概况", "items": ["AI正从智能"]}],
        sources=[
            ResearchSourceOut(
                title="文旅人工智能项目建设",
                url="https://www.mct.gov.cn/example/legacy-entity-authenticity",
                domain="mct.gov.cn",
                snippet="中国移动通信有限公司参与文旅人工智能项目建设。",
                search_query="长三角文旅人工智能",
                source_type="policy",
                content_status="body_acquired",
                source_label="文化和旅游部",
                source_tier="official",
            )
        ],
    )

    payload = _rewrite_legacy_report_for_read(
        report.model_dump(mode="json"),
        cache_key=("legacy-entity-authenticity", "1"),
    )
    cleaned = ResearchReportResponse.model_validate(payload)

    assert cleaned.research_entity_authenticity_gate.passed is True
    assert "AI正从智能" not in cleaned.competitor_profiles
    assert "在线平台游客评价数据开展智能" not in cleaned.winner_peer_moves
    assert all("AI正从智能" not in item for section in cleaned.sections for item in section.items)
