from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.services.content_extractor import normalize_text
from app.services.language import localized_text
from app.services.research.source_documents import SourceDocument


@dataclass(frozen=True, slots=True)
class SourceIntelligenceDependencies:
    build_theme_terms: Callable[[str, str | None, dict[str, object]], list[str]]
    dedupe_strings: Callable[..., list[str]]
    rank_org_rows: Callable[..., list[str]]
    extract_department_rows: Callable[..., list[str]]
    extract_public_contact_rows: Callable[..., list[str]]
    build_entity_specific_team_rows: Callable[..., list[str]]
    extract_rank_entity_name: Callable[[str], str]
    extract_money_signals: Callable[..., list[str]]
    extract_region_distribution: Callable[..., list[str]]
    extract_matching_sentences: Callable[..., list[str]]
    extract_key_people_rows: Callable[..., list[str]]
    extract_people_signals: Callable[..., list[str]]
    ensure_minimum_rows: Callable[..., list[str]]
    build_industry_methodology_rows: Callable[..., dict[str, list[str]]]


def build_source_intelligence(
    sources: list[SourceDocument],
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    scope_hints: dict[str, object],
    deps: SourceIntelligenceDependencies,
) -> dict[str, list[str]]:
    theme_terms = deps.build_theme_terms(keyword, research_focus, scope_hints)
    company_anchor_rows = [
        f"{name}：关键词已明确收敛到该公司，优先补官网、采购公告与投资者关系公开线索。"
        for name in deps.dedupe_strings(scope_hints.get("company_anchors", []) or [], 3)
    ]
    company_contact_rows = [
        f"{name}：优先核验官网“联系我们”、商务合作入口、采购公告联系人和投资者关系邮箱。"
        for name in deps.dedupe_strings(scope_hints.get("company_anchors", []) or [], 3)
    ]
    company_team_rows = [
        f"{name}：优先核验其在目标区域和场景下的政企/行业方案团队、区域交付团队、商务合作团队与创新中心公开动态。"
        for name in deps.dedupe_strings(scope_hints.get("company_anchors", []) or [], 3)
    ]
    target_accounts = deps.rank_org_rows(
        sources,
        role="target",
        context_keywords=("招标", "采购", "预算", "项目", "建设", "规划", "部署"),
        preferred_source_types=("procurement", "policy", "tender_feed", "filing"),
        name_bias_tokens=("政府", "局", "委", "办", "中心", "医院", "大学", "银行", "集团", "学校", "城投", "交投"),
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        limit=6,
    )
    target_departments = deps.extract_department_rows(sources, scope_hints=scope_hints, limit=5)
    public_contact_channels = deps.extract_public_contact_rows(sources, output_language=output_language, limit=5)
    competitor_profiles = deps.rank_org_rows(
        sources,
        role="competitor",
        context_keywords=("中标", "平台", "产品", "解决方案", "合作", "厂商", "公司", "集成商"),
        preferred_source_types=("tender_feed", "tech_media_feed", "web", "filing"),
        name_bias_tokens=("科技", "信息", "软件", "智能", "云", "数据", "通信", "有限公司", "股份", "集团"),
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        limit=6,
    )
    ecosystem_partners = deps.rank_org_rows(
        sources,
        role="partner",
        context_keywords=("伙伴", "合作", "联合", "生态", "咨询", "集成商", "研究院", "渠道", "联盟"),
        preferred_source_types=("tech_media_feed", "web", "procurement", "policy"),
        name_bias_tokens=("集成", "咨询", "研究院", "研究所", "联盟", "科技", "信息", "公司"),
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        limit=6,
    )
    account_team_signals = deps.build_entity_specific_team_rows(
        sources,
        entity_names=deps.dedupe_strings(
            [
                *(normalize_text(str(item)) for item in scope_hints.get("company_anchors", []) if normalize_text(str(item))),
                *(deps.extract_rank_entity_name(item) for item in target_accounts if deps.extract_rank_entity_name(item)),
                *(deps.extract_rank_entity_name(item) for item in ecosystem_partners if deps.extract_rank_entity_name(item)),
            ],
            6,
        ),
        scope_hints=scope_hints,
        output_language=output_language,
        limit=5,
    )
    budget_signals = deps.extract_money_signals(sources, limit=6, scope_hints=scope_hints)
    project_distribution = deps.extract_region_distribution(sources, limit=5, scope_hints=scope_hints)
    strategic_directions = deps.extract_matching_sentences(
        sources,
        keywords=("战略", "规划", "路线", "顶层设计", "五年", "十四五", "三年行动", "建设目标"),
        limit=5,
        scope_hints=scope_hints,
    )
    tender_timeline = deps.extract_matching_sentences(
        sources,
        keywords=("招标", "采购", "投标", "开标", "中标", "公示", "征求意见", "意向公开"),
        limit=5,
        scope_hints=scope_hints,
    )
    leadership_focus = deps.extract_matching_sentences(
        sources,
        keywords=("讲话", "强调", "指出", "要求", "部署", "工作报告", "会议"),
        limit=5,
        scope_hints=scope_hints,
    )
    ecosystem_partner_clues = deps.extract_matching_sentences(
        sources,
        keywords=("合作", "伙伴", "生态", "联合", "集成商", "ISV", "渠道", "顾问", "联盟"),
        limit=6,
        scope_hints=scope_hints,
    )
    benchmark_cases = deps.extract_matching_sentences(
        sources,
        keywords=("试点", "示范", "标杆", "案例", "样板", "落地"),
        limit=5,
        scope_hints=scope_hints,
    )
    flagship_products = deps.extract_matching_sentences(
        sources,
        keywords=("平台", "产品", "解决方案", "系统", "大模型", "云", "套件"),
        limit=5,
        scope_hints=scope_hints,
    )
    key_people = deps.extract_key_people_rows(sources, scope_hints=scope_hints, limit=5) or deps.extract_people_signals(sources, limit=5)
    if not project_distribution:
        project_distribution = deps.extract_matching_sentences(
            sources,
            keywords=("二期", "三期", "四期", "扩建", "升级", "场景"),
            limit=5,
            scope_hints=scope_hints,
        )
    client_peer_moves = target_accounts[:3]
    winner_peer_moves = deps.extract_matching_sentences(
        sources,
        keywords=("中标", "成交", "联合体", "总包", "厂商", "集成商", "平台"),
        limit=6,
        scope_hints=scope_hints,
    )
    if not winner_peer_moves:
        winner_peer_moves = competitor_profiles[:3]
    competition_analysis = deps.dedupe_strings(
        competitor_profiles[:2]
        + winner_peer_moves[:2]
        + deps.extract_matching_sentences(
            sources,
            keywords=("竞争", "优势", "差异化", "资质", "案例", "生态"),
            limit=4,
            scope_hints=scope_hints,
        ),
        5,
    )
    five_year_outlook = deps.extract_matching_sentences(
        sources,
        keywords=("未来五年", "五年", "二期", "三期", "四期", "扩容", "平台化", "升级"),
        limit=5,
        scope_hints=scope_hints,
    )
    if not five_year_outlook:
        anchor = normalize_text(str(scope_hints.get("anchor_text", ""))) or keyword
        five_year_outlook = deps.dedupe_strings(
            [
                localized_text(
                    output_language,
                    {
                        "zh-CN": f"{anchor} 更可能沿着“试点验证 -> 区域复制 -> 二三期扩容 -> 平台统建”演进。",
                        "zh-TW": f"{anchor} 更可能沿著「試點驗證 -> 區域複製 -> 二三期擴容 -> 平台統建」演進。",
                        "en": f"{anchor} is likely to evolve from pilots to regional replication, then phase expansion and platform consolidation.",
                    },
                    f"{anchor} 更可能沿着“试点验证 -> 区域复制 -> 二三期扩容 -> 平台统建”演进。",
                )
            ],
            5,
        )
    intelligence = {
        "target_accounts": deps.ensure_minimum_rows(
            target_accounts,
            backup=company_anchor_rows,
            output_language=output_language,
            scope_hints=scope_hints,
            dimension_key="target_accounts",
            dimension_label=localized_text(output_language, {"zh-CN": "重点甲方", "zh-TW": "重點甲方", "en": "target accounts"}, "重点甲方"),
        ),
        "target_departments": deps.ensure_minimum_rows(
            target_departments,
            backup=deps.extract_matching_sentences(sources, keywords=("采购中心", "招标办", "信息中心", "数据局", "科技部", "财务部"), limit=5, scope_hints=scope_hints),
            output_language=output_language,
            scope_hints=scope_hints,
            dimension_key="target_departments",
            dimension_label=localized_text(output_language, {"zh-CN": "决策部门", "zh-TW": "決策部門", "en": "decision departments"}, "决策部门"),
        ),
        "public_contact_channels": deps.ensure_minimum_rows(public_contact_channels, backup=company_contact_rows, output_language=output_language, scope_hints=scope_hints, dimension_key="public_contact_channels", dimension_label=localized_text(output_language, {"zh-CN": "公开联系方式", "zh-TW": "公開聯絡方式", "en": "public contact channels"}, "公开联系方式")),
        "account_team_signals": deps.ensure_minimum_rows(account_team_signals, backup=company_team_rows, output_language=output_language, scope_hints=scope_hints, dimension_key="account_team_signals", dimension_label=localized_text(output_language, {"zh-CN": "活跃团队情报", "zh-TW": "活躍團隊情報", "en": "active team signals"}, "活跃团队情报")),
        "budget_signals": deps.ensure_minimum_rows(budget_signals, backup=tender_timeline[:2], output_language=output_language, scope_hints=scope_hints, dimension_key="budget_signals", dimension_label=localized_text(output_language, {"zh-CN": "预算与投资信号", "zh-TW": "預算與投資信號", "en": "budget signals"}, "预算与投资信号")),
        "project_distribution": deps.ensure_minimum_rows(project_distribution, backup=deps.extract_matching_sentences(sources, keywords=("二期", "三期", "四期", "扩建", "区域"), limit=5, scope_hints=scope_hints), output_language=output_language, scope_hints=scope_hints, dimension_key="project_distribution", dimension_label=localized_text(output_language, {"zh-CN": "项目分布", "zh-TW": "專案分佈", "en": "project distribution"}, "项目分布")),
        "strategic_directions": deps.ensure_minimum_rows(strategic_directions, backup=leadership_focus[:2], output_language=output_language, scope_hints=scope_hints, dimension_key="strategic_directions", dimension_label=localized_text(output_language, {"zh-CN": "战略方向", "zh-TW": "戰略方向", "en": "strategic directions"}, "战略方向")),
        "tender_timeline": deps.ensure_minimum_rows(tender_timeline, backup=budget_signals[:2], output_language=output_language, scope_hints=scope_hints, dimension_key="tender_timeline", dimension_label=localized_text(output_language, {"zh-CN": "招标时间预测", "zh-TW": "招標時間預測", "en": "tender timeline"}, "招标时间预测")),
        "leadership_focus": deps.ensure_minimum_rows(leadership_focus, backup=deps.extract_matching_sentences(sources, keywords=("工作报告", "部署", "强调", "要求"), limit=5, scope_hints=scope_hints), output_language=output_language, scope_hints=scope_hints, dimension_key="leadership_focus", dimension_label=localized_text(output_language, {"zh-CN": "领导关注点", "zh-TW": "領導關注點", "en": "leadership focus"}, "领导关注点")),
        "ecosystem_partners": deps.ensure_minimum_rows(ecosystem_partners, backup=ecosystem_partner_clues, output_language=output_language, scope_hints=scope_hints, dimension_key="ecosystem_partners", dimension_label=localized_text(output_language, {"zh-CN": "生态伙伴", "zh-TW": "生態夥伴", "en": "ecosystem partners"}, "生态伙伴")),
        "competitor_profiles": deps.ensure_minimum_rows(competitor_profiles, backup=winner_peer_moves, output_language=output_language, scope_hints=scope_hints, dimension_key="competitor_profiles", dimension_label=localized_text(output_language, {"zh-CN": "竞品公司", "zh-TW": "競品公司", "en": "competitor profiles"}, "竞品公司")),
        "benchmark_cases": deps.ensure_minimum_rows(benchmark_cases, backup=deps.extract_matching_sentences(sources, keywords=("案例", "示范", "试点", "样板"), limit=5, scope_hints=scope_hints), output_language=output_language, scope_hints=scope_hints, dimension_key="benchmark_cases", dimension_label=localized_text(output_language, {"zh-CN": "标杆案例", "zh-TW": "標竿案例", "en": "benchmark cases"}, "标杆案例")),
        "flagship_products": deps.ensure_minimum_rows(flagship_products, backup=deps.extract_matching_sentences(sources, keywords=("平台", "产品", "系统", "解决方案"), limit=5, scope_hints=scope_hints), output_language=output_language, scope_hints=scope_hints, dimension_key="flagship_products", dimension_label=localized_text(output_language, {"zh-CN": "明星产品", "zh-TW": "明星產品", "en": "flagship products"}, "明星产品")),
        "key_people": deps.ensure_minimum_rows(key_people, backup=deps.extract_matching_sentences(sources, keywords=("董事长", "总经理", "局长", "主任"), limit=5), output_language=output_language, scope_hints=scope_hints, dimension_key="key_people", dimension_label=localized_text(output_language, {"zh-CN": "关键人物", "zh-TW": "關鍵人物", "en": "key people"}, "关键人物")),
        "client_peer_moves": deps.ensure_minimum_rows(client_peer_moves, backup=target_accounts + company_anchor_rows, output_language=output_language, scope_hints=scope_hints, dimension_key="client_peer_moves", dimension_label=localized_text(output_language, {"zh-CN": "甲方同行", "zh-TW": "甲方同行", "en": "buyer peer moves"}, "甲方同行")),
        "winner_peer_moves": deps.ensure_minimum_rows(winner_peer_moves, backup=competitor_profiles, output_language=output_language, scope_hints=scope_hints, dimension_key="winner_peer_moves", dimension_label=localized_text(output_language, {"zh-CN": "中标方同行", "zh-TW": "中標方同行", "en": "winner peer moves"}, "中标方同行")),
        "competition_analysis": deps.ensure_minimum_rows(competition_analysis, backup=competitor_profiles[:2] + ecosystem_partners[:1], output_language=output_language, scope_hints=scope_hints, dimension_key="competition_analysis", dimension_label=localized_text(output_language, {"zh-CN": "竞争分析", "zh-TW": "競爭分析", "en": "competition analysis"}, "竞争分析")),
        "five_year_outlook": deps.ensure_minimum_rows(five_year_outlook, backup=strategic_directions[:2], output_language=output_language, scope_hints=scope_hints, dimension_key="five_year_outlook", dimension_label=localized_text(output_language, {"zh-CN": "未来五年演化", "zh-TW": "未來五年演化", "en": "five-year outlook"}, "未来五年演化"),
        ),
    }
    methodology_rows = deps.build_industry_methodology_rows(
        scope_hints=scope_hints,
        output_language=output_language,
        scope_anchor=normalize_text(str(scope_hints.get("anchor_text", ""))) or keyword,
    )
    for field_key, rows in methodology_rows.items():
        if not rows:
            continue
        limit = 5 if field_key in {"industry_brief", "solution_design", "sales_strategy", "bidding_strategy", "outreach_strategy", "ecosystem_strategy"} else 4
        intelligence[field_key] = deps.dedupe_strings(rows + intelligence.get(field_key, []), limit)
    if research_focus:
        intelligence["strategic_directions"] = deps.dedupe_strings(
            [f"{normalize_text(research_focus)}"] + intelligence["strategic_directions"],
            5,
        )
    return intelligence
