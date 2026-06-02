from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from app.services.content_extractor import normalize_text


@dataclass(frozen=True, slots=True)
class SourceQueryPlanDependencies:
    strip_query_noise: Callable[[str], str]
    sanitize_research_focus_text: Callable[[str | None], str]
    extract_topic_anchor_terms: Callable[[str, str | None], list[str]]
    expand_region_scope_terms: Callable[[list[str]], list[str]]
    dedupe_strings: Callable[[Iterable[str], int], list[str]]
    collect_theme_seed_companies: Callable[..., list[str]]
    is_plausible_entity_name: Callable[[str], bool]
    industry_scope_aliases: dict[str, tuple[str, ...]]
    theme_query_expansion_templates: dict[str, tuple[str, ...]]
    research_source_site_queries: tuple[tuple[str, str], ...]
    theme_official_query_templates: dict[str, tuple[str, ...]]


def _dedupe_queries(queries: Iterable[str], *, limit: int, exclusions: Iterable[str] = ()) -> list[str]:
    exclusion_terms = [normalize_text(str(item)) for item in exclusions if normalize_text(str(item))]
    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized = normalize_text(query)
        if not normalized or normalized in seen:
            continue
        if any(exclusion in normalized for exclusion in exclusion_terms):
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped[:limit]


def build_scoped_official_query_expansions(
    keyword: str,
    research_focus: str | None,
    *,
    scope_hints: dict[str, object] | None,
    include_wechat: bool,
    limit: int,
    deps: SourceQueryPlanDependencies,
) -> list[str]:
    scope_hints = scope_hints or {}
    normalized_keyword = deps.strip_query_noise(keyword) or normalize_text(keyword)
    normalized_focus = deps.sanitize_research_focus_text(research_focus)
    regions = [normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    industries = [normalize_text(str(item)) for item in scope_hints.get("industries", []) if normalize_text(str(item))]
    buyers = [normalize_text(str(item)) for item in scope_hints.get("clients", []) if normalize_text(str(item))]
    topic_anchors = deps.extract_topic_anchor_terms(normalized_keyword, normalized_focus)
    expanded_regions = deps.expand_region_scope_terms(regions[:1])[:3]
    official_regions = expanded_regions or regions[:1]
    official_industries = deps.dedupe_strings(
        [
            *industries[:1],
            *[
                normalize_text(alias)
                for alias in (deps.industry_scope_aliases.get(normalize_text(industries[0]), ()) if industries else ())
                if normalize_text(alias)
            ][:2],
            *topic_anchors[:1],
        ],
        3,
    )
    official_buyers = deps.dedupe_strings(buyers[:2], 2)
    queries: list[str] = []

    primary_regions = official_regions[:1]
    primary_industries = official_industries[:1]
    extra_regions = official_regions[1:2]
    extra_industries = official_industries[1:2]

    if primary_regions and primary_industries:
        queries.extend(
            [
                f"site:gov.cn {primary_regions[0]} {primary_industries[0]} {normalized_keyword} 规划 预算 战略",
                f"site:ggzy.gov.cn {primary_regions[0]} {primary_industries[0]} {normalized_keyword} 招标 项目 中标",
                f"site:ccgp.gov.cn {primary_regions[0]} {primary_industries[0]} {normalized_keyword} 采购意向 招标 中标",
            ]
        )
    elif primary_regions:
        queries.extend(
            [
                f"site:gov.cn {primary_regions[0]} {normalized_keyword} 规划 预算 战略",
                f"site:ggzy.gov.cn {primary_regions[0]} {normalized_keyword} 招标 项目 中标",
                f"site:ccgp.gov.cn {primary_regions[0]} {normalized_keyword} 采购意向 招标 中标",
            ]
        )

    for buyer in official_buyers[:2]:
        quoted_buyer = f"\"{buyer}\""
        queries.extend(
            [
                f"site:gov.cn {quoted_buyer} {normalized_keyword} 规划 预算",
                f"site:ggzy.gov.cn {quoted_buyer} {normalized_keyword} 招标 项目",
                f"site:ccgp.gov.cn {quoted_buyer} {normalized_keyword} 采购意向 中标",
            ]
        )
        if official_regions:
            queries.extend(
                [
                    f"site:gov.cn {official_regions[0]} {quoted_buyer} 规划 战略",
                    f"site:ggzy.gov.cn {official_regions[0]} {quoted_buyer} 项目 招标",
                ]
            )
        if official_industries:
            queries.extend(
                [
                    f"site:gov.cn {quoted_buyer} {official_industries[0]} 规划 战略",
                    f"site:ggzy.gov.cn {quoted_buyer} {official_industries[0]} 招标 项目",
                ]
            )
        if normalized_focus:
            queries.append(f"site:gov.cn {quoted_buyer} {normalized_focus} 预算 规划")

    if extra_regions and primary_industries:
        for region in extra_regions:
            queries.extend(
                [
                    f"site:gov.cn {region} {primary_industries[0]} {normalized_keyword} 规划 预算 战略",
                    f"site:ggzy.gov.cn {region} {primary_industries[0]} {normalized_keyword} 招标 项目 中标",
                    f"site:ccgp.gov.cn {region} {primary_industries[0]} {normalized_keyword} 采购意向 招标 中标",
                ]
            )
    if primary_regions and extra_industries:
        for industry in extra_industries:
            queries.extend(
                [
                    f"site:gov.cn {primary_regions[0]} {industry} {normalized_keyword} 规划 预算 战略",
                    f"site:ggzy.gov.cn {primary_regions[0]} {industry} {normalized_keyword} 招标 项目 中标",
                    f"site:ccgp.gov.cn {primary_regions[0]} {industry} {normalized_keyword} 采购意向 招标 中标",
                ]
            )

    if include_wechat and official_buyers:
        queries.append(f"site:mp.weixin.qq.com \"{official_buyers[0]}\" {normalized_keyword} 采购 规划")
    return _dedupe_queries(queries, limit=limit)


def build_query_plan(
    keyword: str,
    research_focus: str | None,
    include_wechat: bool,
    *,
    scope_hints: dict[str, object] | None,
    preferred_wechat_accounts: Iterable[str] | None,
    limit: int,
    deps: SourceQueryPlanDependencies,
) -> list[str]:
    normalized_keyword = deps.strip_query_noise(keyword) or normalize_text(keyword)
    normalized_focus = deps.sanitize_research_focus_text(research_focus)
    scope_hints = scope_hints or {}
    scope_regions = [normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    scope_industries = [normalize_text(str(item)) for item in scope_hints.get("industries", []) if normalize_text(str(item))]
    scope_clients = [normalize_text(str(item)) for item in scope_hints.get("clients", []) if normalize_text(str(item))]
    topic_anchors = deps.extract_topic_anchor_terms(normalized_keyword, normalized_focus)
    strategy_query_expansions = [
        normalize_text(str(item))
        for item in scope_hints.get("strategy_query_expansions", [])
        if normalize_text(str(item))
    ]
    scoped_official_queries = build_scoped_official_query_expansions(
        normalized_keyword,
        normalized_focus,
        scope_hints=scope_hints,
        include_wechat=include_wechat,
        limit=8,
        deps=deps,
    )
    matched_theme_labels = [
        label
        for label, aliases in deps.industry_scope_aliases.items()
        if any(alias in f"{normalized_keyword} {normalized_focus}" for alias in aliases)
    ]
    scoped_prefix = normalize_text(" ".join([*scope_regions[:1], *scope_industries[:1], *scope_clients[:1]]))
    scoped_keyword = normalize_text(" ".join([scoped_prefix, normalized_keyword])) if scoped_prefix else normalized_keyword
    queries = [scoped_keyword]
    scoped_region_expansions = deps.expand_region_scope_terms(scope_regions[:1])[:4]
    if scope_clients:
        queries.append(f"\"{scope_clients[0]}\" {normalized_keyword}")
    if scope_regions and scope_industries:
        queries.append(f"{scope_regions[0]} {scope_industries[0]} {normalized_keyword}")
    for region_term in scoped_region_expansions[:2]:
        if region_term != scope_regions[0]:
            queries.append(f"{region_term} {normalized_keyword}")
    if topic_anchors:
        queries.append(f"\"{topic_anchors[0]}\"")
        if normalized_focus:
            queries.append(f"\"{topic_anchors[0]}\" {normalize_text(' '.join([scoped_prefix, normalized_focus])) or normalized_focus}")
    queries.extend(strategy_query_expansions)
    queries.extend(scoped_official_queries)
    for label in matched_theme_labels:
        for template in deps.theme_query_expansion_templates.get(label, ()):
            queries.append(template.format(keyword=scoped_keyword))
    for _, template in deps.research_source_site_queries:
        queries.append(template.format(keyword=scoped_keyword))
    if normalized_focus:
        queries.append(f"{scoped_keyword} {normalized_focus}")
    if include_wechat:
        queries.append(f"site:mp.weixin.qq.com {scoped_keyword}")
        queries.append(f"site:mp.weixin.qq.com {scoped_keyword} 招标 中标 预算")
        if normalized_focus:
            queries.append(f"site:mp.weixin.qq.com {scoped_keyword} {normalized_focus} 采购 战略")
        for account in deps.dedupe_strings(preferred_wechat_accounts or [], 3):
            queries.append(f'site:mp.weixin.qq.com "{account}" {scoped_keyword}')
            if normalized_focus:
                queries.append(f'site:mp.weixin.qq.com "{account}" {scoped_keyword} {normalized_focus}')
    if normalized_focus:
        queries.append(f"{scoped_keyword} {normalized_focus} 招标 预算 中标")
        queries.append(f"{scoped_keyword} {normalized_focus} 领导 讲话 战略")
        queries.append(f"{scoped_keyword} {normalized_focus} 生态伙伴 集成商")
    if scope_clients:
        queries.extend(
            [
                f"\"{scope_clients[0]}\" {normalized_keyword} 官网 联系方式 招标",
                f"\"{scope_clients[0]}\" {normalized_keyword} 预算 项目 采购",
            ]
        )
    if scope_regions:
        queries.extend(
            [
                f"site:ggzy.gov.cn {scope_regions[0]} {normalized_keyword} 招标 中标 项目",
                f"site:gov.cn {scope_regions[0]} {normalized_keyword} 讲话 规划 战略",
            ]
        )
        for region_term in scoped_region_expansions[:2]:
            if region_term != scope_regions[0]:
                queries.extend(
                    [
                        f"site:ggzy.gov.cn {region_term} {normalized_keyword} 招标 中标 项目",
                        f"site:gov.cn {region_term} {normalized_keyword} 讲话 规划 战略",
                    ]
                )
    return _dedupe_queries(queries, limit=limit)


def build_corrective_query_plan(
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
    include_wechat: bool,
    preferred_wechat_accounts: Iterable[str] | None,
    limit: int,
    deps: SourceQueryPlanDependencies,
) -> list[str]:
    queries: list[str] = []
    industries = [normalize_text(str(item)) for item in scope_hints.get("industries", []) or [] if normalize_text(str(item))]
    regions = [normalize_text(str(item)) for item in scope_hints.get("regions", []) or [] if normalize_text(str(item))]
    strategy_query_expansions = [
        normalize_text(str(item))
        for item in scope_hints.get("strategy_query_expansions", []) or []
        if normalize_text(str(item))
    ]
    queries.extend(strategy_query_expansions)
    queries.extend(
        build_scoped_official_query_expansions(
            keyword,
            research_focus,
            scope_hints=scope_hints,
            include_wechat=include_wechat,
            limit=max(6, limit),
            deps=deps,
        )
    )
    seed_companies = deps.collect_theme_seed_companies(keyword=keyword, research_focus=research_focus, scope_hints=scope_hints)
    for industry in industries:
        for template in deps.theme_official_query_templates.get(industry, ()):
            queries.append(template.format(keyword=keyword))
    for company in seed_companies[:6]:
        queries.extend(
            [
                f"{company} {keyword} 官网 合作 平台",
                f"{company} {keyword} 投资者关系 合作 战略",
                f"{company} {keyword} 联系我们 商务合作",
                f"{company} {keyword} 团队 业务 负责人",
            ]
        )
    if regions:
        region = regions[0]
        queries.extend(
            [
                f"{region} {keyword} 采购意向 项目 招标",
                f"{region} {keyword} 场景 合作 平台 内容",
            ]
        )
    if include_wechat:
        queries.append(f"site:mp.weixin.qq.com {keyword} 平台 合作 内容 AIGC")
        for account in deps.dedupe_strings(preferred_wechat_accounts or [], 2):
            queries.append(f'site:mp.weixin.qq.com "{account}" {keyword}')
            if research_focus:
                queries.append(f'site:mp.weixin.qq.com "{account}" {keyword} {normalize_text(research_focus)}')
    exclusions = [normalize_text(str(item)) for item in scope_hints.get("strategy_exclusion_terms", []) or [] if normalize_text(str(item))]
    return _dedupe_queries(queries, limit=limit, exclusions=exclusions)


def build_expanded_query_plan(
    keyword: str,
    research_focus: str | None,
    *,
    scope_hints: dict[str, object],
    include_wechat: bool,
    preferred_wechat_accounts: Iterable[str] | None,
    limit: int,
    deps: SourceQueryPlanDependencies,
) -> list[str]:
    keyword_seed = deps.strip_query_noise(keyword) or keyword
    regions = [normalize_text(item) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    industries = [normalize_text(item) for item in scope_hints.get("industries", []) if normalize_text(str(item))]
    clients = [normalize_text(item) for item in scope_hints.get("clients", []) if normalize_text(str(item))]
    focus = deps.sanitize_research_focus_text(research_focus)
    topic_anchors = deps.extract_topic_anchor_terms(keyword_seed, focus)
    expanded_regions = deps.expand_region_scope_terms(regions[:1])[:4]
    strategy_query_expansions = [
        normalize_text(str(item))
        for item in scope_hints.get("strategy_query_expansions", [])
        if normalize_text(str(item))
    ]
    scoped_official_queries = build_scoped_official_query_expansions(
        keyword_seed,
        focus,
        scope_hints=scope_hints,
        include_wechat=include_wechat,
        limit=max(6, limit),
        deps=deps,
    )
    query_seed = [keyword_seed]
    if regions:
        query_seed.append(regions[0])
    if industries:
        query_seed.append(industries[0])
    if focus:
        query_seed.append(focus)
    base = " ".join(item for item in query_seed if item)
    queries = [
        f"{base} 预算 投资 采购 金额",
        f"{base} 招标 中标 采购意向 二期 三期 四期",
        f"{base} 领导 讲话 工作报告 战略 规划",
        f"{base} 生态伙伴 集成商 ISV 咨询",
        f"{base} 标杆案例 解决方案 平台 产品",
    ]
    queries.extend(strategy_query_expansions)
    queries.extend(scoped_official_queries)
    if topic_anchors:
        anchor = topic_anchors[0]
        queries.extend(
            [
                f"\"{anchor}\" 甲方 预算 采购 中标",
                f"\"{anchor}\" 标杆案例 竞品 生态伙伴",
                f"\"{anchor}\" 领导 讲话 规划 招标",
            ]
        )
    if clients:
        queries.extend(
            [
                f"{clients[0]} {keyword_seed} 预算 项目 招标",
                f"{clients[0]} {keyword_seed} 领导 讲话 战略",
            ]
        )
    if regions:
        queries.extend(
            [
                f"site:ccgp.gov.cn {regions[0]} {keyword_seed} 招标 中标 预算",
                f"site:ggzy.gov.cn {regions[0]} {keyword_seed} 项目 招标 中标",
                f"site:cecbid.org.cn {regions[0]} {keyword_seed} 招标 中标 采购",
                f"site:cebpubservice.com {regions[0]} {keyword_seed} 招标 中标",
            ]
        )
        for region_term in expanded_regions[:3]:
            if region_term != regions[0]:
                queries.extend(
                    [
                        f"site:ccgp.gov.cn {region_term} {keyword_seed} 招标 中标 预算",
                        f"site:ggzy.gov.cn {region_term} {keyword_seed} 项目 招标 中标",
                    ]
                )
    if include_wechat:
        queries.append(f"site:mp.weixin.qq.com {base} 招标 预算 生态伙伴")
        queries.append(f"site:mp.weixin.qq.com {base} 中标 采购 战略 规划")
        for account in deps.dedupe_strings(preferred_wechat_accounts or [], 2):
            queries.append(f'site:mp.weixin.qq.com "{account}" {base}')
            if focus:
                queries.append(f'site:mp.weixin.qq.com "{account}" {base} {focus}')
    return _dedupe_queries(queries, limit=limit)


def build_company_contact_query_plan(
    company_names: list[str],
    *,
    keyword: str,
    research_focus: str | None,
    limit: int,
    deps: SourceQueryPlanDependencies,
) -> list[str]:
    queries: list[str] = []
    keyword_seed = deps.strip_query_noise(keyword) or normalize_text(keyword)
    focus_seed = deps.strip_query_noise(research_focus or "")
    for company in deps.dedupe_strings(company_names, 4):
        normalized = normalize_text(company)
        if not normalized or not deps.is_plausible_entity_name(normalized):
            continue
        queries.extend(
            [
                f"\"{normalized}\" 官网 联系我们",
                f"\"{normalized}\" 商务合作 联系方式",
                f"\"{normalized}\" 投资者关系 邮箱",
                f"site:ir.* \"{normalized}\" investor relations contact",
                f"site:*.com \"{normalized}\" about contact",
                f"\"{normalized}\" 采购 联系人",
                f"\"{normalized}\" 招标 联系人",
            ]
        )
        if keyword_seed:
            queries.append(f"\"{normalized}\" {keyword_seed} 官网")
        if focus_seed:
            queries.append(f"\"{normalized}\" {focus_seed} 联系方式")
    return _dedupe_queries(queries, limit=limit)


def build_company_profile_query_plan(
    company_names: list[str],
    *,
    keyword: str,
    research_focus: str | None,
    limit: int,
    deps: SourceQueryPlanDependencies,
) -> list[str]:
    queries: list[str] = []
    keyword_seed = deps.strip_query_noise(keyword) or normalize_text(keyword)
    focus_seed = deps.strip_query_noise(research_focus or "")
    for company in deps.dedupe_strings(company_names, 4):
        normalized = normalize_text(company)
        if not normalized or not deps.is_plausible_entity_name(normalized):
            continue
        queries.extend(
            [
                f"\"{normalized}\" 官网 关于我们",
                f"\"{normalized}\" 公司简介 业务介绍",
                f"\"{normalized}\" 官方 网站",
                f"\"{normalized}\" 品牌介绍 官方",
                f"\"{normalized}\" 投资者关系 年报",
                f"site:*.com \"{normalized}\" official profile",
                f"site:*.com \"{normalized}\" about us company",
            ]
        )
        if keyword_seed:
            queries.append(f"\"{normalized}\" {keyword_seed} 官网 解决方案")
        if focus_seed:
            queries.append(f"\"{normalized}\" {focus_seed} 官方")
    return _dedupe_queries(queries, limit=limit)


def build_company_team_query_plan(
    company_names: list[str],
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
    limit: int,
    deps: SourceQueryPlanDependencies,
) -> list[str]:
    queries: list[str] = []
    keyword_seed = deps.strip_query_noise(keyword) or normalize_text(keyword)
    focus_seed = deps.strip_query_noise(research_focus or "")
    region_terms = deps.expand_region_scope_terms(
        [normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    )
    industry_terms = [normalize_text(str(item)) for item in scope_hints.get("industries", []) if normalize_text(str(item))]
    for company in deps.dedupe_strings(company_names, 4):
        normalized = normalize_text(company)
        if not normalized or not deps.is_plausible_entity_name(normalized):
            continue
        queries.extend(
            [
                f"\"{normalized}\" 团队 政企 行业解决方案",
                f"\"{normalized}\" 区域团队 商务合作",
                f"\"{normalized}\" 官网 团队 行业解决方案",
                f"site:*.com \"{normalized}\" team business partnership",
            ]
        )
        for region in region_terms[:2]:
            queries.append(f"\"{normalized}\" {region} 团队")
        for industry in industry_terms[:2]:
            queries.append(f"\"{normalized}\" {industry} 团队")
        if keyword_seed:
            queries.append(f"\"{normalized}\" {keyword_seed} 团队")
        if focus_seed:
            queries.append(f"\"{normalized}\" {focus_seed} 团队")
    return _dedupe_queries(queries, limit=limit)
