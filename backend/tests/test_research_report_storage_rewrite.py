from datetime import datetime, timezone

from app.schemas.research import ResearchCommercialSummaryOut, ResearchReportResponse, ResearchSourceDiagnosticsOut, ResearchSourceOut
from app.services import research_service


def test_rewrite_stored_research_report_uses_guarded_mode_for_low_signal_reports() -> None:
    report = ResearchReportResponse(
        keyword="政务云 AI 行业研报",
        research_focus="预算和周期",
        output_language="zh-CN",
        research_mode="deep",
        report_title="待补证研判｜政务云 AI 行业研报",
        executive_summary=(
            "当前证据不足以形成最终商业判断，更适合作为候选名单与待补证路径。"
            " 结论：先看政务云。"
        ),
        consulting_angle="可用于初步行业判断。",
        sections=[],
        target_accounts=["省级数据局"],
        target_departments=["信息中心"],
        public_contact_channels=[],
        account_team_signals=[],
        budget_signals=["若金额仍缺失，可先给出高价值预算口径：平台统建、算力扩容。"],
        project_distribution=[],
        strategic_directions=[],
        tender_timeline=[],
        leadership_focus=[],
        ecosystem_partners=[],
        competitor_profiles=["政务云总集厂商（待验证）"],
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

    rewritten = research_service.rewrite_stored_research_report(report)
    cards = research_service.build_research_action_cards(rewritten)

    assert rewritten.report_title.endswith("待核验清单与补证路径")
    assert "结论：" not in rewritten.executive_summary
    assert "当前公开来源不足以支持" in rewritten.executive_summary
    assert rewritten.commercial_summary.next_action == "先补官网、公告、采购和联系人线索，再决定是否进入正式推进。"
    assert all("若金额仍缺失" not in row for row in rewritten.budget_signals)
    assert rewritten.top_target_accounts == []
    assert rewritten.pending_target_candidates == []
    assert rewritten.source_diagnostics.guarded_backlog is True
    assert "no_sources" in rewritten.source_diagnostics.guarded_rewrite_reasons
    assert "省级数据局" in rewritten.source_diagnostics.unsupported_target_accounts
    assert len(cards) == 1
    assert cards[0].action_type == "evidence_recovery"
    assert "补证" in cards[0].title


def test_rewrite_stored_research_report_rewrites_legacy_title_and_template_summary_with_supported_source() -> None:
    report = ResearchReportResponse(
        keyword="陕西文博 VR 项目",
        research_focus="预算和周期",
        output_language="zh-CN",
        research_mode="deep",
        report_title="候选推进版｜陕西｜预算和周期｜政务服务中心：招标窗口、预算窗口与进入路径",
        executive_summary=(
            "当前结果可用于候选推进和内部讨论，但仍建议补证后再做强判断。"
            " 结论：本次研判锁定在陕西，优先围绕陕西省文物局识别高价值甲方、预算窗口与进入路径。"
            " 证据：当前最强的公开信号集中在若金额仍缺失，可先给出高价值预算口径。"
            " 动作：并用竞品差异化与伙伴牵线设计进入路径。"
        ),
        consulting_angle="可用于初步行业判断。",
        sections=[],
        target_accounts=["陕西省文物局", "陕西文化产业投资控股（集团）有限公司"],
        target_departments=["陕西历史博物馆 陈列展览部 / 信息中心（数字化部）"],
        public_contact_channels=["建议补充公开服务热线、采购公告联系人或投资者关系邮箱后重新生成。"],
        account_team_signals=[],
        budget_signals=["若金额仍缺失，可先给出高价值预算口径：平台统建、算力扩容、应用试点、集成实施、运维续费。"],
        project_distribution=[],
        strategic_directions=[],
        tender_timeline=["预计预算申报与立项窗口集中在下个财政周期前。"],
        leadership_focus=[],
        ecosystem_partners=[],
        competitor_profiles=["头部 VR 大空间内容商（如博新元宇宙等）：强项在于爆款运营经验。"],
        benchmark_cases=[],
        flagship_products=[],
        key_people=[],
        five_year_outlook=[],
        client_peer_moves=[],
        winner_peer_moves=[],
        competition_analysis=[],
        source_count=1,
        evidence_density="medium",
        source_quality="medium",
        query_plan=[],
        sources=[
            ResearchSourceOut(
                title="陕西省文物局推进数字文博 VR 建设",
                url="https://whhlyt.shaanxi.gov.cn/vr-plan",
                domain="whhlyt.shaanxi.gov.cn",
                snippet="陕西省文物局推进数字文博VR项目建设，公开提到预算申报、项目周期和数字化升级。",
                search_query="陕西文博 VR 项目",
                source_type="web",
                content_status="browser_extracted",
                source_label="官网",
                source_tier="official",
            )
        ],
        source_diagnostics=ResearchSourceDiagnosticsOut(
            scope_regions=["陕西"],
            scope_industries=["文旅"],
            scope_clients=["陕西省文物局"],
            retrieval_quality="medium",
            evidence_mode="provisional",
            official_source_ratio=1.0,
            strict_match_ratio=1.0,
            unique_domain_count=1,
        ),
        commercial_summary=ResearchCommercialSummaryOut(
            next_action="建议补充公开服务热线、采购公告联系人或投资者关系邮箱后重新生成。"
        ),
        generated_at=datetime.now(timezone.utc),
    )

    rewritten = research_service.rewrite_stored_research_report(report)
    cards = research_service.build_research_action_cards(rewritten)

    assert not rewritten.report_title.startswith("候选推进版｜")
    assert "陕西省文物局" in rewritten.report_title
    assert "待核验清单与补证路径" not in rewritten.report_title
    assert "结论：" not in rewritten.executive_summary
    assert "证据：" not in rewritten.executive_summary
    assert "先补官网、公告、采购和联系人线索" not in rewritten.commercial_summary.next_action
    assert all("若金额仍缺失" not in row for row in rewritten.budget_signals)
    assert rewritten.source_diagnostics.guarded_backlog is False
    assert rewritten.source_diagnostics.supported_target_accounts == ["陕西省文物局"]
    assert rewritten.source_diagnostics.unsupported_target_accounts == ["陕西文化产业投资控股（集团）有限公司"]
    assert any(card.action_type != "evidence_recovery" for card in cards)


def test_rewrite_stored_research_report_canonicalizes_legacy_alias_entities_from_stored_payload() -> None:
    report = ResearchReportResponse(
        keyword="长三角 AI 文旅商机",
        research_focus="关注预算和甲方",
        output_language="zh-CN",
        research_mode="deep",
        report_title="长三角｜AI 文旅：预算窗口与进入路径",
        executive_summary="围绕百联推进数字化与会员运营预算窗口判断。",
        consulting_angle="可用于初步行业判断。",
        sections=[],
        target_accounts=["百联"],
        top_target_accounts=[
            {
                "name": "百联",
                "score": 81,
                "reasoning": "已有官网线索。",
                "entity_mode": "instance",
                "score_breakdown": [],
                "evidence_links": [
                    {
                        "title": "百联集团官网",
                        "url": "https://www.bailian.com/",
                        "source_label": "百联官网",
                        "source_tier": "official",
                    }
                ],
            }
        ],
        pending_target_candidates=[],
        target_departments=[],
        public_contact_channels=[],
        account_team_signals=[],
        budget_signals=["百联围绕会员与数字化建设安排预算。"],
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
        source_count=1,
        evidence_density="medium",
        source_quality="high",
        query_plan=[],
        sources=[
            ResearchSourceOut(
                title="百联集团官网",
                url="https://www.bailian.com/",
                domain="bailian.com",
                snippet="百联数字化升级与会员运营规划。",
                search_query="长三角 AI 文旅商机",
                source_type="company",
                content_status="browser_extracted",
                source_label="百联官网",
                source_tier="official",
            )
        ],
        source_diagnostics=ResearchSourceDiagnosticsOut(
            scope_regions=["长三角"],
            scope_industries=["文旅"],
            scope_clients=["百联"],
            retrieval_quality="medium",
            evidence_mode="provisional",
            official_source_ratio=1.0,
            strict_match_ratio=1.0,
            unique_domain_count=1,
        ),
        commercial_summary=ResearchCommercialSummaryOut(next_action="优先核验预算与部门。"),
        generated_at=datetime.now(timezone.utc),
    )

    rewritten = research_service.rewrite_stored_research_report(report)

    assert "百联集团" in rewritten.target_accounts
    assert "百联" not in rewritten.target_accounts
    assert rewritten.source_diagnostics.scope_clients == ["百联集团"]


def test_rewrite_stored_research_report_strips_prompt_style_scope_entities_from_guarded_title() -> None:
    report = ResearchReportResponse(
        keyword="长三角地区政企行业和医疗行业AI大模型及应用落地",
        research_focus=(
            "我作为maas公司或者云厂商,我想在长三角推我们公司的maas产品和大模型agent产品离的中,"
            "该在政企、文旅、医疗、金融行业哪些重点公司去找客户找项目,他们哪些大概率有预算,"
            "预算规模如何、找哪些部门哪位领导有决策权,这些客户有哪些竟品公司在紧密合作,把竞品公司情况一并调研清楚"
        ),
        output_language="zh-CN",
        research_mode="deep",
        report_title="候选推进版｜长三角地区政企行业和医疗行业AI大模型及应用落地 研报：政策、商机与落地策略总览",
        executive_summary="当前结果可用于候选推进和内部讨论，但仍建议补证后再做强判断。",
        consulting_angle="可用于初步行业判断。",
        sections=[],
        target_accounts=["我作为maas公司", "我想在长三角推我们公司"],
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
            scope_industries=["大模型"],
            scope_clients=["我作为maas公司", "我想在长三角推我们公司", "金融行业哪些重点公司"],
            retrieval_quality="low",
            evidence_mode="fallback",
            official_source_ratio=0.0,
        ),
        commercial_summary=ResearchCommercialSummaryOut(next_action="先补公开证据"),
        generated_at=datetime.now(timezone.utc),
    )

    rewritten = research_service.rewrite_stored_research_report(report)

    assert rewritten.report_title == "长三角｜大模型：待核验清单与补证路径"
    assert "我作为maas公司" not in rewritten.report_title
    assert "我想在长三角推我们公司" not in rewritten.executive_summary
    assert rewritten.target_accounts == []


def test_rewrite_stored_research_report_strips_source_noise_scope_entities_from_guarded_title() -> None:
    report = ResearchReportResponse(
        keyword="2026长三角地区政务行业潜在AI采购商机",
        research_focus=(
            "包括但不限于MAAS、IAAS、PAAS、SAAS、综合解决方案、AI agent 以及其他各类云服务的需求,"
            "精确到决策单位、决策部门,已经有了哪些标杆案例,行业竞品公司有哪些、竞品近3年类似场景标杆案例有哪些,"
            "这些目标商机金额和可能的招投标时间"
        ),
        output_language="zh-CN",
        research_mode="deep",
        report_title="候选推进版｜2026年长三角及重点区域政务AI采购商机研判：从算力基座向MaaS与AI Agent应用深水区跨越",
        executive_summary="当前结果可用于候选推进和内部讨论，但仍建议补证后再做强判断。",
        consulting_angle="可用于初步行业判断。",
        sections=[],
        target_accounts=["华尔街和全球银行", "它将被视为大型国际银行"],
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
            scope_clients=["华尔街和全球银行", "它将被视为大型国际银行", "预计将是全球服务中心"],
            retrieval_quality="low",
            evidence_mode="fallback",
            official_source_ratio=0.0,
        ),
        commercial_summary=ResearchCommercialSummaryOut(next_action="先补公开证据"),
        generated_at=datetime.now(timezone.utc),
    )

    rewritten = research_service.rewrite_stored_research_report(report)

    assert rewritten.report_title == "长三角｜政务云：待核验清单与补证路径"
    assert "华尔街和全球银行" not in rewritten.report_title
    assert "大型国际银行" not in rewritten.executive_summary
    assert rewritten.target_accounts == []


def test_rewrite_stored_research_report_drops_generic_placeholder_clients_from_guarded_title() -> None:
    report = ResearchReportResponse(
        keyword="AI漫剧头部公司",
        research_focus="分析头部公司的商业化路径、预算窗口与合作机会",
        output_language="zh-CN",
        research_mode="deep",
        report_title="AIGC动画｜AI漫剧头部公司：竞争格局与切入策略",
        executive_summary="当前结果可用于候选推进和内部讨论，但仍建议补证后再做强判断。",
        consulting_angle="可用于初步行业判断。",
        sections=[],
        target_accounts=["AI漫剧头部公司", "MAAS的头部公司"],
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
            scope_regions=[],
            scope_industries=["AI漫剧"],
            scope_clients=["AI漫剧头部公司", "MAAS的头部公司"],
            retrieval_quality="low",
            evidence_mode="fallback",
            official_source_ratio=0.0,
        ),
        commercial_summary=ResearchCommercialSummaryOut(next_action="先补公开证据"),
        generated_at=datetime.now(timezone.utc),
    )

    rewritten = research_service.rewrite_stored_research_report(report)

    assert rewritten.report_title == "AI漫剧：待核验清单与补证路径"
    assert "头部公司" not in rewritten.report_title
    assert "MAAS的头部公司" not in rewritten.executive_summary


def test_source_text_cleaning_drops_award_forum_and_markdown_source_dump_noise() -> None:
    documents = research_service._report_sources_to_source_documents(
        [
            ResearchSourceOut(
                title="AI漫剧论坛主论坛嘉宾发言",
                url="https://example.com/forum-noise",
                domain="example.com",
                snippet=(
                    "![封面](https://example.com/cover.png) 图片来源：https://example.com/cover.png。"
                    "论坛嘉宾围绕行业趋势分享观点。"
                    "大会公布年度企业奖与漫剧热力榜。"
                    "阅文集团披露 AI 漫剧项目推进与 IP 改编计划。"
                    "Source: https://example.com/source.md"
                ),
                search_query="长三角 AIGC 动画",
                source_type="web",
                content_status="reader_proxy",
                source_label="媒体",
                source_tier="media",
            )
        ]
    )

    cleaned_text = research_service._source_text(documents[0])

    assert "嘉宾发言" not in cleaned_text
    assert "分享观点" not in cleaned_text
    assert "年度企业奖" not in cleaned_text
    assert "热力榜" not in cleaned_text
    assert "图片来源" not in cleaned_text
    assert "Source:" not in cleaned_text
    assert "阅文集团披露 AI 漫剧项目推进与 IP 改编计划" in cleaned_text


def test_rewrite_stored_research_report_guards_single_source_company_intent_without_concrete_target() -> None:
    report = ResearchReportResponse(
        keyword="粤港澳 AIGC 动画",
        research_focus="分析 AIGC 动画平台和合作机会",
        output_language="zh-CN",
        research_mode="deep",
        report_title="粤港澳｜AIGC动画｜科技数码：竞争格局与切入策略",
        executive_summary="优先把科技数码列为推进对象。",
        consulting_angle="可用于初步行业判断。",
        sections=[],
        target_accounts=["科技数码"],
        target_departments=[],
        public_contact_channels=["对于 粤港澳 的重点业主，优先从公共资源交易公告中提取联系人。"],
        account_team_signals=[],
        budget_signals=[],
        project_distribution=[],
        strategic_directions=[],
        tender_timeline=[],
        leadership_focus=[],
        ecosystem_partners=["算力与云服务"],
        competitor_profiles=["专业AIGC视频工具厂商（如生数科技）"],
        benchmark_cases=[],
        flagship_products=[],
        key_people=[],
        five_year_outlook=[],
        client_peer_moves=[],
        winner_peer_moves=[],
        competition_analysis=[],
        source_count=1,
        evidence_density="low",
        source_quality="medium",
        query_plan=[],
        sources=[
            ResearchSourceOut(
                title="哔哩哔哩科技数码分区",
                url="https://www.bilibili.com/v/tech/",
                domain="www.bilibili.com",
                snippet="哔哩哔哩公开展示科技数码分区内容。",
                search_query="粤港澳 AIGC 动画",
                source_type="web",
                content_status="browser_extracted",
                source_label="官网",
                source_tier="official",
            )
        ],
        source_diagnostics=ResearchSourceDiagnosticsOut(
            scope_regions=["粤港澳"],
            scope_industries=["AI漫剧"],
            scope_clients=["科技数码"],
            retrieval_quality="medium",
            evidence_mode="provisional",
            official_source_ratio=1.0,
            strict_match_ratio=0.4,
            unique_domain_count=1,
        ),
        commercial_summary=ResearchCommercialSummaryOut(next_action="先补公开证据"),
        generated_at=datetime.now(timezone.utc),
    )

    rewritten = research_service.rewrite_stored_research_report(report)

    assert rewritten.report_title.endswith("待核验清单与补证路径")
    assert "科技数码" not in rewritten.report_title
    assert rewritten.target_accounts == []
    assert rewritten.commercial_summary.next_action == "先补官网、公告、采购和联系人线索，再决定是否进入正式推进。"


def test_rewrite_stored_research_report_strips_source_dump_rows_from_summary_and_actions() -> None:
    noisy_budget = (
        "硅基思索与芜湖政企携手 共筑长三角AI漫剧产业新支点-CSDN博客 2026年1月8日，"
        "杭州硅基思索科技（集团）有限公司与芜湖市委宣传部签署合作协议。"
    )
    report = ResearchReportResponse(
        keyword="长三角 AIGC 动画",
        research_focus="分析 AI 漫剧平台合作和预算窗口",
        output_language="zh-CN",
        research_mode="deep",
        report_title="长三角｜AIGC动画｜杭州硅基思索科技有限公司：预算信号与切入策略",
        executive_summary=(
            f"优先把芜湖市镜湖区委区政府列为首批推进对象，当前公开信号已经出现{noisy_budget}这类预算或采购窗口。"
        ),
        consulting_angle="可用于初步行业判断。",
        sections=[],
        target_accounts=["阅文集团"],
        target_departments=[],
        public_contact_channels=["当前已收敛到具体公司，但公开联系方式仍不足，建议优先核验官网“联系我们”。"],
        account_team_signals=[],
        budget_signals=[noisy_budget, "文章标签：#人工智能 #大数据"],
        project_distribution=[],
        strategic_directions=[],
        tender_timeline=[],
        leadership_focus=[],
        ecosystem_partners=["中国网络视听协会"],
        competitor_profiles=["惊奇科技", "杭州硅基思索科技有限公司"],
        benchmark_cases=["大会发布首届漫剧热力榜，探讨AI技术如何降本增效。"],
        flagship_products=[],
        key_people=[],
        five_year_outlook=[],
        client_peer_moves=[],
        winner_peer_moves=[],
        competition_analysis=[],
        source_count=4,
        evidence_density="medium",
        source_quality="medium",
        query_plan=[],
        sources=[
            ResearchSourceOut(
                title="阅文集团内容生态布局",
                url="https://www.yuewen.com/article",
                domain="www.yuewen.com",
                snippet="阅文集团推进内容生态与IP商业化。",
                search_query="长三角 AIGC 动画",
                source_type="web",
                content_status="browser_extracted",
                source_label="官网",
                source_tier="media",
            ),
            ResearchSourceOut(
                title="AI漫剧行业观察",
                url="https://example.com/a",
                domain="example.com",
                snippet="行业观察提到惊奇科技和阅文集团。",
                search_query="长三角 AIGC 动画",
                source_type="web",
                content_status="browser_extracted",
                source_label="媒体",
                source_tier="media",
            ),
            ResearchSourceOut(
                title="中国网络视听协会活动",
                url="https://example.com/b",
                domain="example.com",
                snippet="公开活动提到中国网络视听协会与AI内容。",
                search_query="长三角 AIGC 动画",
                source_type="web",
                content_status="browser_extracted",
                source_label="媒体",
                source_tier="media",
            ),
            ResearchSourceOut(
                title="漫剧热力榜",
                url="https://example.com/c",
                domain="example.com",
                snippet="漫剧热力榜公开展示行业标杆。",
                search_query="长三角 AIGC 动画",
                source_type="web",
                content_status="browser_extracted",
                source_label="媒体",
                source_tier="media",
            ),
        ],
        source_diagnostics=ResearchSourceDiagnosticsOut(
            scope_regions=["长三角"],
            scope_industries=["AI漫剧"],
            scope_clients=["阅文集团"],
            retrieval_quality="high",
            evidence_mode="provisional",
            official_source_ratio=0.0,
            strict_match_ratio=0.8,
            unique_domain_count=3,
        ),
        commercial_summary=ResearchCommercialSummaryOut(next_action="先补公开证据"),
        generated_at=datetime.now(timezone.utc),
    )

    rewritten = research_service.rewrite_stored_research_report(report)

    assert "CSDN博客" not in rewritten.executive_summary
    assert "文章标签" not in rewritten.executive_summary
    assert "当前已收敛到具体公司" not in rewritten.commercial_summary.next_action
    assert rewritten.target_accounts == ["阅文集团"]
    assert rewritten.budget_signals == []
    assert rewritten.public_contact_channels == []


def test_rewrite_stored_research_report_guards_when_targets_have_no_source_support() -> None:
    report = ResearchReportResponse(
        keyword="华东制造业 AI 改造",
        research_focus="梳理重点甲方、预算窗口和进入路径",
        output_language="zh-CN",
        research_mode="deep",
        report_title="华东｜制造业AI｜上海临港集团：预算窗口与推进路径",
        executive_summary="优先把上海临港集团和上汽集团列为首批推进对象。",
        consulting_angle="可用于初步行业判断。",
        sections=[],
        target_accounts=["上海临港集团", "上汽集团"],
        target_departments=["信息化部"],
        public_contact_channels=["建议优先补官网联系页和采购联系人。"],
        account_team_signals=[],
        budget_signals=["预计 2026 年下半年会出现制造业 AI 改造预算与项目立项窗口。"],
        project_distribution=[],
        strategic_directions=[],
        tender_timeline=["预计 2026 年下半年启动项目立项和采购。"],
        leadership_focus=[],
        ecosystem_partners=["行业顾问伙伴"],
        competitor_profiles=["某工业互联网平台厂商"],
        benchmark_cases=[],
        flagship_products=[],
        key_people=[],
        five_year_outlook=[],
        client_peer_moves=[],
        winner_peer_moves=[],
        competition_analysis=[],
        source_count=3,
        evidence_density="medium",
        source_quality="medium",
        query_plan=[],
        sources=[
            ResearchSourceOut(
                title="OPC 创新社区｜工业 AI 平台实践分享",
                url="https://www.opc.example.com/article",
                domain="www.opc.example.com",
                snippet="论坛嘉宾围绕工业 AI 平台升级分享观点，未提及上海临港集团或上汽集团。",
                search_query="华东制造业 AI 改造",
                source_type="web",
                content_status="browser_extracted",
                source_label="OPC 社区",
                source_tier="media",
            ),
            ResearchSourceOut(
                title="云头条｜某厂商发布工业大模型平台",
                url="https://www.yuntoutiao.com/article",
                domain="www.yuntoutiao.com",
                snippet="某厂商发布工业大模型平台，文章未提及上海临港集团或上汽集团。",
                search_query="华东制造业 AI 改造",
                source_type="tech_media_feed",
                content_status="browser_extracted",
                source_label="云头条",
                source_tier="media",
            ),
            ResearchSourceOut(
                title="某厂商官网｜工业智能底座",
                url="https://www.vendor-example.com/solution",
                domain="www.vendor-example.com",
                snippet="某厂商介绍工业智能底座和产品路线，未出现上海临港集团或上汽集团。",
                search_query="华东制造业 AI 改造",
                source_type="web",
                content_status="browser_extracted",
                source_label="官网",
                source_tier="official",
            ),
        ],
        source_diagnostics=ResearchSourceDiagnosticsOut(
            scope_regions=["华东"],
            scope_industries=["制造业", "人工智能"],
            scope_clients=["上海临港集团", "上汽集团"],
            retrieval_quality="high",
            evidence_mode="provisional",
            official_source_ratio=0.34,
            strict_match_ratio=0.9,
            unique_domain_count=3,
        ),
        commercial_summary=ResearchCommercialSummaryOut(next_action="先补公开证据"),
        generated_at=datetime.now(timezone.utc),
    )

    rewritten = research_service.rewrite_stored_research_report(report)

    assert rewritten.report_title.endswith("待核验清单与补证路径")
    assert rewritten.target_accounts == []
    assert rewritten.top_target_accounts == []
    assert rewritten.pending_target_candidates == []
    assert rewritten.source_diagnostics.guarded_backlog is True
    assert "no_target_source_support" in rewritten.source_diagnostics.guarded_rewrite_reasons
    assert rewritten.source_diagnostics.supported_target_accounts == []
    assert rewritten.source_diagnostics.unsupported_target_accounts == ["上海临港集团", "上汽集团"]
    assert rewritten.commercial_summary.next_action == "先补官网、公告、采购和联系人线索，再决定是否进入正式推进。"


def test_rewrite_stored_research_report_guards_single_source_with_placeholder_partner_rows() -> None:
    report = ResearchReportResponse(
        keyword="河南 AIGC 动画",
        research_focus="分析头部平台与合作机会",
        output_language="zh-CN",
        research_mode="deep",
        report_title="河南｜AIGC动画｜阅文集团：竞争格局与切入策略",
        executive_summary="优先把阅文集团、河南文旅投资集团列为首批推进对象。",
        consulting_angle="可用于初步行业判断。",
        sections=[],
        target_accounts=["阅文集团", "河南文旅投资集团"],
        target_departments=[],
        public_contact_channels=["建议补充公开服务热线、采购公告联系人或投资者关系邮箱后重新生成。"],
        account_team_signals=[],
        budget_signals=[],
        project_distribution=[],
        strategic_directions=[],
        tender_timeline=[],
        leadership_focus=[],
        ecosystem_partners=["动漫 IP 咨询与发行伙伴（待验证）"],
        competitor_profiles=["腾讯云"],
        benchmark_cases=[],
        flagship_products=[],
        key_people=[],
        five_year_outlook=[],
        client_peer_moves=[],
        winner_peer_moves=[],
        competition_analysis=[],
        source_count=1,
        evidence_density="low",
        source_quality="medium",
        query_plan=[],
        sources=[
            ResearchSourceOut(
                title="哔哩哔哩 (゜-゜)つロ 干杯~-bilibili",
                url="https://www.bilibili.com/",
                domain="www.bilibili.com",
                snippet="哔哩哔哩公开展示动画和内容生态。",
                search_query="河南 AIGC 动画",
                source_type="web",
                content_status="browser_extracted",
                source_label="官网",
                source_tier="official",
            )
        ],
        source_diagnostics=ResearchSourceDiagnosticsOut(
            scope_regions=["河南"],
            scope_industries=["AI漫剧"],
            scope_clients=["阅文集团", "河南文旅投资集团"],
            retrieval_quality="medium",
            evidence_mode="provisional",
            official_source_ratio=1.0,
            strict_match_ratio=0.4,
            unique_domain_count=1,
        ),
        commercial_summary=ResearchCommercialSummaryOut(next_action="先补公开证据"),
        generated_at=datetime.now(timezone.utc),
    )

    rewritten = research_service.rewrite_stored_research_report(report)

    assert rewritten.report_title.endswith("待核验清单与补证路径")
    assert rewritten.commercial_summary.next_action == "先补官网、公告、采购和联系人线索，再决定是否进入正式推进。"
    assert rewritten.public_contact_channels == []
    assert rewritten.ecosystem_partners == []


def test_rewrite_stored_research_report_guards_procurement_aggregate_only_sources() -> None:
    report = ResearchReportResponse(
        keyword="长三角 政务大模型",
        research_focus="梳理招标窗口和推进路径",
        output_language="zh-CN",
        research_mode="deep",
        report_title="长三角｜政务大模型：招标窗口与推进路径",
        executive_summary="优先把上海市大数据中心及各区城运中心列为首批推进对象。",
        consulting_angle="可用于初步行业判断。",
        sections=[],
        target_accounts=["上海市大数据中心及各区城运中心"],
        target_departments=[],
        public_contact_channels=[],
        account_team_signals=[],
        budget_signals=[
            "国家税务总局深圳市福田区税务局2026年华富路办公区物业管理服务采购项目公开招标公告 - 中国招标投标网 中国招标投标网 · 招标 欢迎您来到中国招标投标网 主站 标讯站 资讯站"
        ],
        project_distribution=[],
        strategic_directions=[],
        tender_timeline=[],
        leadership_focus=[],
        ecosystem_partners=["顶层设计与咨询"],
        competitor_profiles=["我方切口在于多云管理或跨云AI服务"],
        benchmark_cases=[],
        flagship_products=[],
        key_people=[],
        five_year_outlook=[],
        client_peer_moves=[],
        winner_peer_moves=[],
        competition_analysis=[],
        source_count=3,
        evidence_density="low",
        source_quality="medium",
        query_plan=[],
        sources=[
            ResearchSourceOut(
                title="国家税务总局深圳市福田区税务局2026年华富路办公区物业管理服务采购项目公开招标公告 - 中国招标投标网",
                url="https://www.cecbid.org.cn/a",
                domain="www.cecbid.org.cn",
                snippet="中国招标投标网 · 招标 欢迎您来到中国招标投标网 主站 标讯站 资讯站",
                search_query="长三角 政务大模型",
                source_type="procurement",
                content_status="browser_extracted",
                source_label="中国招标投标网",
                source_tier="official",
            ),
            ResearchSourceOut(
                title="第三师五十团2026年市政综合服务采购项目的公开招标公告 - 中国招标投标网",
                url="https://www.cecbid.org.cn/b",
                domain="www.cecbid.org.cn",
                snippet="中国招标投标网 · 招标 欢迎您来到中国招标投标网 主站 标讯站 资讯站",
                search_query="长三角 政务大模型",
                source_type="procurement",
                content_status="browser_extracted",
                source_label="中国招标投标网",
                source_tier="official",
            ),
            ResearchSourceOut(
                title="和田县医共体总院开展财务收支审计服务采购项目中标结果公告 - 中国招标投标网",
                url="https://www.cecbid.org.cn/c",
                domain="www.cecbid.org.cn",
                snippet="中国招标投标网 · 招标 欢迎您来到中国招标投标网 主站 标讯站 资讯站",
                search_query="长三角 政务大模型",
                source_type="procurement",
                content_status="browser_extracted",
                source_label="中国招标投标网",
                source_tier="official",
            ),
        ],
        source_diagnostics=ResearchSourceDiagnosticsOut(
            scope_regions=["长三角"],
            scope_industries=["政务云", "大模型"],
            scope_clients=["上海市大数据中心及各区城运中心"],
            retrieval_quality="medium",
            evidence_mode="provisional",
            official_source_ratio=1.0,
            strict_match_ratio=0.2,
            unique_domain_count=1,
        ),
        commercial_summary=ResearchCommercialSummaryOut(next_action="先补公开证据"),
        generated_at=datetime.now(timezone.utc),
    )

    rewritten = research_service.rewrite_stored_research_report(report)

    assert rewritten.report_title.endswith("待核验清单与补证路径")
    assert rewritten.budget_signals == []
    assert rewritten.competitor_profiles == []
    assert rewritten.ecosystem_partners == []
