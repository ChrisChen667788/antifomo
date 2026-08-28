from __future__ import annotations

from app.schemas.research import ResearchEntityEvidenceOut
from app.services.research.delivery_evidence_ledger import build_delivery_evidence_ledger


def _official_evidence(
    *,
    title: str = "某市政务 AI 项目采购公告",
    url: str = "https://example.gov.cn/procurement/GOV-AI-2026-001",
    excerpt: str = "采购人：某市数据局。预算金额 520 万元，建设周期 12 个月。项目编号 GOV-AI-2026-001。",
) -> ResearchEntityEvidenceOut:
    return ResearchEntityEvidenceOut(
        title=title,
        url=url,
        source_label="政府采购公告",
        source_tier="official",
        anchor_text="GOV-AI-2026-001",
        excerpt=excerpt,
        confidence_tone="high",
    )


def test_claim_and_evidence_ids_are_stable_when_input_order_changes() -> None:
    rows = [
        ("投资估算", "预算金额 520 万元，来源：https://example.gov.cn/procurement/GOV-AI-2026-001"),
        ("实施计划", "建设周期 12 个月，项目编号：GOV-AI-2026-001"),
    ]
    evidence = [_official_evidence()]

    first = build_delivery_evidence_ledger(rows, evidence_links=evidence)
    second = build_delivery_evidence_ledger(list(reversed(rows)), evidence_links=list(reversed(evidence)))

    assert [claim.claim_id for claim in first.claims] == [claim.claim_id for claim in second.claims]
    assert [item.evidence_id for item in first.evidence] == [item.evidence_id for item in second.evidence]


def test_external_evidence_supports_matching_numeric_and_entity_claim() -> None:
    ledger = build_delivery_evidence_ledger(
        [("投资估算", "某市数据局项目预算金额 520 万元，建设周期 12 个月。")],
        evidence_links=[_official_evidence()],
        expected_entities=["某市数据局"],
    )

    claim = ledger.claims[0]
    assert claim.verification_status == "supported"
    assert any(relation.relation_type == "supports" for relation in claim.evidence_relations)
    assert ledger.high_confidence_coverage_percent == 100
    assert ledger.entity_consistency_score == 100
    assert ledger.numeric_consistency_score == 100


def test_entity_role_conflict_is_stable_and_blocks_ledger() -> None:
    ledger = build_delivery_evidence_ledger(
        [
            ("项目概况", "目标客户：甲市数据局。"),
            ("项目概况", "目标客户：乙市数据局。"),
        ],
        expected_entities=["甲市数据局"],
    )

    issues = [issue for issue in ledger.consistency_issues if issue.issue_type == "entity_role_conflict"]
    assert issues
    assert all(issue.issue_id.startswith("issue_") for issue in issues)
    assert any(issue.severity == "high" for issue in issues)
    assert ledger.entity_consistency_score < 100
    assert ledger.status == "fail"


def test_equivalent_amount_units_do_not_create_numeric_conflict() -> None:
    ledger = build_delivery_evidence_ledger(
        [
            ("投资估算", "项目预算金额 520 万元。"),
            ("投资估算", "项目预算金额 0.052 亿元。"),
        ]
    )

    assert not [issue for issue in ledger.consistency_issues if issue.issue_type.startswith("numeric_")]
    assert ledger.numeric_consistency_score == 100


def test_conflicting_budget_values_create_high_severity_numeric_issue() -> None:
    ledger = build_delivery_evidence_ledger(
        [
            ("投资估算", "项目预算金额 520 万元。"),
            ("投资估算", "项目预算金额 680 万元。"),
        ]
    )

    issues = [issue for issue in ledger.consistency_issues if issue.issue_type == "numeric_conflict"]
    assert len(issues) == 1
    assert issues[0].severity == "high"
    assert len(issues[0].claim_ids) == 2
    assert ledger.numeric_consistency_score < 100
    assert ledger.status == "fail"


def test_calendar_year_alone_does_not_promote_a_fact_to_high_confidence_numeric_claim() -> None:
    ledger = build_delivery_evidence_ledger(
        [("产品动态", "九天大模型入选2024年央企技术成果名单。")]
    )

    claim = ledger.claims[0]
    assert claim.claim_type == "fact"
    assert claim.confidence == "medium"
    assert claim.numeric_facts[0].metric == "calendar_year"


def test_source_attribution_rows_are_metadata_not_factual_claims() -> None:
    ledger = build_delivery_evidence_ledger(
        [
            ("政策与领导信号", "来源：上海市政府官网，2025年3月"),
            ("政策与领导信号", "上海市发布人工智能政务服务实施方案。"),
        ]
    )

    assert [claim.text for claim in ledger.claims] == ["上海市发布人工智能政务服务实施方案。"]


def test_tracking_and_design_advice_are_not_treated_as_procurement_facts() -> None:
    ledger = build_delivery_evidence_ledger(
        [
            ("项目与商机判断", "应追踪2026年6月开标后的中标公告和合同附件"),
            ("项目与商机判断", "宜采用规则可追溯、人机协同和私域知识库路线"),
            ("活跃团队与推进抓手", "媒体线索指向省数据局与省数据集团协作框架"),
            ("活跃团队与推进抓手", "当前来源未提供具体承办组织及个人信息"),
            ("关键信号", "当前公开强信号集中在上海，浙江与安徽需补充同颗粒度招标证据"),
            ("关键信号", "预算、代理机构及中标候选人尚未从现有摘要确认"),
            ("关键信号", "金额、采购人和中标结果需回查原公告"),
            ("关键信号", "采购人全称及技术参数需调取原公告正文复核"),
            ("招标时间预测", "具体项目内容、招标范围及所应达到的具体要求，以招标文件相应规定为准"),
            ("行业资讯判断", "本轮公开证据对上海覆盖较多，对江苏、安徽的具体预算覆盖不足"),
            ("关键信号", "两类厂商将积极争夺底座和平台预算"),
            ("关键信号", "当前有效公开材料偏政策和案例，缺少可用采购意向与预算金额"),
            ("公开业务联系方式", "当前证据未提供项目公开采购联系人和业务电话"),
            ("项目与商机判断", "媒体报道显示统一调度方向，但尚无可验证项目编号或金额"),
            ("项目与商机判断", "2026年应重点寻找区级续建、事项扩面与运维采购"),
            ("解决方案设计建议", "可切入电子证照调用、目录治理与合规审计"),
            ("关键信号", "因此应将本轮结论定位为高价值账户筛选，而非确定项目清单"),
            ("项目与商机判断", "交付边界可拆为知识库治理、流程编排和安全审计"),
            ("项目与商机判断", "宜定位为省级云运营生态切入机会"),
            ("政策与领导信号", "这将提升电子证照和跨域数据交换的集成需求"),
            ("关键信号", "该信号支持从门户服务和窗口导办拆分商机"),
            ("招标时间预测", "明确信息公示、异议处置和纠错救济等规则"),
            ("活跃团队与推进抓手", "需下载CTZB-2025080278采购文件并提取采购人和服务清单"),
            ("执行摘要", "方案上，应提供存量云底座与政务知识库的分期路径"),
            ("项目与商机判断", "项目已进入招标阶段，应从下一轮续建或增项机会切入"),
        ]
    )

    claim_types = {claim.text: claim.claim_type for claim in ledger.claims}
    assert claim_types == {
        "应追踪2026年6月开标后的中标公告和合同附件": "recommendation",
        "宜采用规则可追溯、人机协同和私域知识库路线": "recommendation",
        "媒体线索指向省数据局与省数据集团协作框架": "assumption",
        "当前来源未提供具体承办组织及个人信息": "assumption",
        "当前公开强信号集中在上海，浙江与安徽需补充同颗粒度招标证据": "assumption",
        "预算、代理机构及中标候选人尚未从现有摘要确认": "assumption",
        "金额、采购人和中标结果需回查原公告": "assumption",
        "采购人全称及技术参数需调取原公告正文复核": "assumption",
        "具体项目内容、招标范围及所应达到的具体要求，以招标文件相应规定为准": "assumption",
        "本轮公开证据对上海覆盖较多，对江苏、安徽的具体预算覆盖不足": "assumption",
        "两类厂商将积极争夺底座和平台预算": "assumption",
        "当前有效公开材料偏政策和案例，缺少可用采购意向与预算金额": "assumption",
        "当前证据未提供项目公开采购联系人和业务电话": "assumption",
        "媒体报道显示统一调度方向，但尚无可验证项目编号或金额": "assumption",
        "2026年应重点寻找区级续建、事项扩面与运维采购": "recommendation",
        "可切入电子证照调用、目录治理与合规审计": "recommendation",
        "因此应将本轮结论定位为高价值账户筛选，而非确定项目清单": "recommendation",
        "交付边界可拆为知识库治理、流程编排和安全审计": "recommendation",
        "宜定位为省级云运营生态切入机会": "recommendation",
        "这将提升电子证照和跨域数据交换的集成需求": "assumption",
        "该信号支持从门户服务和窗口导办拆分商机": "assumption",
        "明确信息公示、异议处置和纠错救济等规则": "recommendation",
        "需下载CTZB-2025080278采购文件并提取采购人和服务清单": "recommendation",
        "方案上，应提供存量云底座与政务知识库的分期路径": "recommendation",
        "项目已进入招标阶段，应从下一轮续建或增项机会切入": "recommendation",
    }
