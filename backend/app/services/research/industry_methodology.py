from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import re

from app.services.content_extractor import normalize_text
from app.services.research.entity_policy import INDUSTRY_SCOPE_ALIASES
from app.services.research.report_common import dedupe_strings
from app.services.research.scope_entity_runtime_dependencies import scope_term_dependencies
from app.services.research.scope_terms import strip_query_noise


@dataclass(frozen=True, slots=True)
class IndustryMethodologyProfile:
    key: str
    authority_label: str
    framework: str
    primary_questions: tuple[str, ...]
    query_templates: tuple[str, ...]
    source_preferences: tuple[str, ...]
    solution_lenses: tuple[str, ...]
    sales_lenses: tuple[str, ...]
    bidding_lenses: tuple[str, ...]
    outreach_lenses: tuple[str, ...]
    ecosystem_lenses: tuple[str, ...]


INDUSTRY_METHODOLOGY_PROFILES: dict[str, IndustryMethodologyProfile] = {
    "政务云": IndustryMethodologyProfile(
        key="政务云",
        authority_label="公共部门数字化项目调研框架",
        framework="政策牵引 -> 预算归口 -> 招采窗口 -> 建设期次 -> 运维绩效",
        primary_questions=(
            "当前牵头部门、预算归口部门和招采执行部门分别是谁",
            "项目处于立项、试点、一期建设还是二三期扩容",
            "是否已有可研、预算草案、采购意向或中标续建信号",
            "云资源、平台总包、集成运维和安全厂商分别由谁承担",
        ),
        query_templates=(
            "{region} {industry} 财政预算 采购意向 可研 批复",
            "\"{client}\" {keyword} 预算 立项 可研 采购意向",
            "{region} {industry} 一体化平台 续建 扩容 运维",
        ),
        source_preferences=("gov.cn", "ccgp.gov.cn", "ggzy.gov.cn", "数据局/政务服务局官网", "财政预算公开"),
        solution_lenses=("顶层架构统建", "试点到统建分期", "云网安一体化", "运维与绩效闭环"),
        sales_lenses=("牵头部门切入", "预算归口核验", "年度规划节点", "续建扩容窗口"),
        bidding_lenses=("采购意向前置布局", "总包与分包角色", "资质与案例匹配", "续建项目壁垒"),
        outreach_lenses=("数据局/信息中心优先", "财政与招采并行摸排", "总包伙伴联动"),
        ecosystem_lenses=("本地集成商", "云资源伙伴", "咨询可研单位", "运维服务商"),
    ),
    "文旅文博": IndustryMethodologyProfile(
        key="文旅文博",
        authority_label="文旅文博场景与公共文化项目调研框架",
        framework="游客与公共文化场景 -> 内容和资产数据 -> 运营服务 -> 招采建设 -> 商业价值",
        primary_questions=(
            "需求来自景区运营、博物馆公共文化服务、内容生产还是营销转化场景",
            "文旅主管部门、场馆或景区运营方、信息化部门和采购部门的决策链如何分布",
            "是否已有数字导览、智慧景区、文物数字化、公共文化平台或内容生产项目的预算与招采信号",
            "AI 能力如何接入票务、导览、藏品内容、游客服务和运营分析，并形成可验证的投入产出",
        ),
        query_templates=(
            "{region} 文旅 文博 人工智能",
            "{region} 景区 博物馆 数字化 招标 预算",
            "\"{client}\" {keyword} 导览 运营 采购",
        ),
        source_preferences=("文化和旅游主管部门官网", "场馆/景区官网", "政府采购与公共资源交易平台", "项目招投标公告", "上市文旅企业年报"),
        solution_lenses=("游客服务闭环", "内容与资产数据治理", "导览和运营系统集成", "试点到多场馆复制"),
        sales_lenses=("主管部门与运营主体双线", "预算和项目节点核验", "场景价值量化", "区域样板复制"),
        bidding_lenses=("采购意向前置布局", "软硬件与内容边界", "数据版权和安全", "本地实施与持续运营"),
        outreach_lenses=("文旅主管部门/场馆运营方 -> 信息化部门 -> 业务运营 -> 财务采购", "以可参观、可量化样板切入"),
        ecosystem_lenses=("文旅规划咨询", "票务与导览平台", "内容数字化团队", "本地集成与运营伙伴"),
    ),
    "医疗": IndustryMethodologyProfile(
        key="医疗",
        authority_label="临床价值与医院信息化调研框架",
        framework="临床场景 -> 信息科与医务线 -> 合规安全 -> 系统集成 -> 投入产出",
        primary_questions=(
            "需求来自临床、医务、运营还是科研教学场景",
            "信息科、医务处、设备处、财务处和采购办的分工如何",
            "是否涉及电子病历、互联互通、医保支付、数据安全等约束",
            "试点科室、医院集团复制和区域医共体扩展节奏如何",
        ),
        query_templates=(
            "{region} 医院 {keyword} 信息化 建设 采购 预算",
            "{region} 卫健 {keyword} 试点 示范 预算",
            "\"{client}\" {keyword} 信息科 医务处 招标",
        ),
        source_preferences=("医院官网", "卫健委官网", "招采公告", "试点示范名单", "医院年报/新闻"),
        solution_lenses=("临床价值闭环", "科室试点复制", "HIS/PACS/EMR 集成", "合规与数据安全"),
        sales_lenses=("信息科与医务双线推进", "示范科室案例", "ROI 与效率提升", "院级预算窗口"),
        bidding_lenses=("设备/软件采购口径", "集成改造复杂度", "资质合规", "医院集团复制能力"),
        outreach_lenses=("信息科 -> 医务处 -> 业务科室 -> 财务采购", "专家共识与标杆医院材料"),
        ecosystem_lenses=("区域总代", "医疗集成商", "科研教学伙伴", "数据安全伙伴"),
    ),
    "金融": IndustryMethodologyProfile(
        key="金融",
        authority_label="金融科技与监管约束调研框架",
        framework="监管约束 -> 场景优先级 -> 数据治理 -> 风控审计 -> ROI 与复制性",
        primary_questions=(
            "需求落在营销、风控、运营、投研还是客服场景",
            "监管合规、模型可解释、审计留痕和数据边界要求是什么",
            "总行、分行、科技子公司和业务条线的决策链如何分布",
            "试点是否能复制到更多分支机构或条线",
        ),
        query_templates=(
            "{region} 银行 {keyword} 科技 招标 采购",
            "{region} 证券 保险 {keyword} 数据治理 风控 预算",
            "\"{client}\" {keyword} 科技部 数字化 招标",
        ),
        source_preferences=("银行/保险/证券官网", "监管公告", "招采公告", "年报与业绩会", "科技子公司新闻"),
        solution_lenses=("监管合规", "数据治理", "风控审计", "场景复制"),
        sales_lenses=("科技条线切入", "业务条线共创", "监管合规证明", "总分行复制"),
        bidding_lenses=("资质安全要求", "POC 与试点", "总包合作", "审计留痕"),
        outreach_lenses=("科技部/数字化部先行", "业务部门共识", "监管与审计口径同步"),
        ecosystem_lenses=("咨询与总包", "安全厂商", "数据治理伙伴", "本地交付团队"),
    ),
    "教育": IndustryMethodologyProfile(
        key="教育",
        authority_label="教育数字化项目调研框架",
        framework="教学科研场景 -> 教委/信息中心 -> 预算批次 -> 试点扩面 -> 安全与绩效",
        primary_questions=(
            "场景属于课堂教学、科研平台、校园治理还是职教实训",
            "教委、学校信息中心、教务处和资产采购部门的分工如何",
            "是否有试点校、示范校、专项资金或年度采购批次",
            "项目是单校部署还是区域复制/集团统建",
        ),
        query_templates=(
            "{region} 教委 {keyword} 预算 试点 示范",
            "{region} 高校 学校 {keyword} 招标 采购 信息化",
            "\"{client}\" {keyword} 信息中心 教务处 采购",
        ),
        source_preferences=("教委官网", "学校官网", "招采公告", "试点示范名单", "专项资金文件"),
        solution_lenses=("教学场景闭环", "试点校复制", "教务与科研平台集成", "校园数据安全"),
        sales_lenses=("教委/学校双线", "示范校案例", "年度预算批次", "集团化复制"),
        bidding_lenses=("专项资金口径", "校园网与平台集成", "安全等保", "实施交付保障"),
        outreach_lenses=("信息中心 -> 教务处 -> 学院/职能部门", "试点校样板材料"),
        ecosystem_lenses=("本地教育集成商", "内容与平台伙伴", "科研合作单位", "安全运维伙伴"),
    ),
    "AI漫剧": IndustryMethodologyProfile(
        key="AI漫剧",
        authority_label="内容产业与 IP 商业化调研框架",
        framework="IP 供给 -> 制作工具链 -> 分发平台 -> 商业化路径 -> 版权合规",
        primary_questions=(
            "核心机会在 IP、平台分发、内容生产还是商业化变现",
            "平台方、版权方、制作工作室和发行渠道分别是谁",
            "当前信号来自立项合作、内容招商、生态伙伴还是投资布局",
            "未来机会是试水项目还是平台级长期内容供给",
        ),
        query_templates=(
            "{keyword} IP 合作 分发 平台 商业化",
            "{keyword} 版权 发行 工作室 生态 预算",
            "\"{client}\" AIGC 动画 短剧 合作 平台",
        ),
        source_preferences=("平台/内容公司官网", "IR/年报", "行业媒体", "公众号深度稿", "版权与合作公告"),
        solution_lenses=("IP 供给链路", "制作工具链", "平台分发接口", "版权与变现"),
        sales_lenses=("平台运营/内容生态切入", "先谈合作形态再谈产品", "以内容供给与效率证明价值"),
        bidding_lenses=("合作招商口径", "版权与交付边界", "联合方案伙伴", "平台准入条件"),
        outreach_lenses=("平台运营 -> 内容生态 -> 商务合作 -> 工作室", "案例以内容效率和变现为核心"),
        ecosystem_lenses=("IP 版权方", "发行渠道", "动画工作室", "内容技术伙伴"),
    ),
    "数据中心": IndustryMethodologyProfile(
        key="数据中心",
        authority_label="算力与基础设施投资调研框架",
        framework="项目批复 -> 机电土建 -> 算力设备 -> 运维能耗 -> 二三期扩容",
        primary_questions=(
            "项目处于规划、批复、一期建设还是扩容阶段",
            "预算大头落在土建机电、服务器存储还是运营服务",
            "牵头主体是国资平台、运营商还是产业园区",
            "二三期扩容和能源约束是否已经出现公开信号",
        ),
        query_templates=(
            "{region} {keyword} 可研 批复 能耗 指标",
            "{region} 智算中心 数据中心 {keyword} 招标 中标",
            "\"{client}\" {keyword} 扩容 二期 三期",
        ),
        source_preferences=("发改/工信官网", "园区与国资平台官网", "招采公告", "能耗与批复文件", "运营商官网"),
        solution_lenses=("基础设施分层", "算力与存储组合", "运维监控", "扩容节奏"),
        sales_lenses=("牵头主体摸排", "批复与能耗指标", "一期到扩容延续", "总包合作"),
        bidding_lenses=("土建机电/设备分包", "能耗与资质", "交付周期", "运维 SLA"),
        outreach_lenses=("发改/园区/国资平台先行", "总包与运营商联动"),
        ecosystem_lenses=("机电总包", "服务器存储厂商", "运营商", "运维服务商"),
    ),
    "大模型": IndustryMethodologyProfile(
        key="大模型",
        authority_label="AI 场景落地与投资验证框架",
        framework="场景优先级 -> 数据可得性 -> 模型与算力 -> 集成改造 -> ROI 与复制",
        primary_questions=(
            "是政企、医疗、金融、教育还是内容生产场景在驱动需求",
            "数据、算力、模型部署和安全合规约束分别是什么",
            "预算更偏平台建设、试点验证还是行业复制扩容",
            "需要总包、ISV、模型厂商还是本地交付伙伴共同推进",
        ),
        query_templates=(
            "{region} {keyword} 试点 示范 预算 采购",
            "{region} 大模型 {keyword} 招标 中标 项目",
            "\"{client}\" {keyword} 数据 安全 预算 采购",
        ),
        source_preferences=("gov.cn/招采网", "行业主管部门官网", "客户官网", "模型厂商官网", "公开案例与年报"),
        solution_lenses=("场景优先级", "数据与合规", "模型部署架构", "复制扩容"),
        sales_lenses=("业务场景负责人", "预算归口", "试点 ROI", "复制节奏"),
        bidding_lenses=("数据与安全要求", "模型/算力边界", "总包协同", "案例资质"),
        outreach_lenses=("业务部门 -> 信息化/科技部门 -> 预算与采购", "试点样板先行"),
        ecosystem_lenses=("模型厂商", "算力伙伴", "ISV", "本地交付伙伴"),
    ),
}


def build_generic_industry_methodology_profile(industry: str) -> IndustryMethodologyProfile:
    label = normalize_text(industry) or "目标行业"
    return IndustryMethodologyProfile(
        key=label,
        authority_label=f"{label}通用决策调研框架",
        framework="需求场景 -> 政策与市场 -> 采购和投资 -> 竞争与生态 -> 交付与风险",
        primary_questions=(
            f"{label}的核心需求、使用场景和决策主体分别是什么",
            f"{label}当前有哪些政策、市场规模、预算或投资信号",
            f"{label}的采购路径、项目窗口、代表客户和决策链如何分布",
            f"{label}的主要方案、竞争者、生态伙伴、交付约束和反证风险是什么",
        ),
        query_templates=(
            "{region} {keyword} 政策 市场 需求 数据",
            "{region} {keyword} 采购 招标 中标 投资",
            "{region} {keyword} 客户 案例 解决方案 竞争",
        ),
        source_preferences=("行业主管部门官网", "政府采购与公共资源交易平台", "企业官网与年报", "行业协会/研究机构", "高质量行业媒体"),
        solution_lenses=("需求场景闭环", "数据与系统边界", "试点到规模化", "交付与合规"),
        sales_lenses=("决策主体识别", "预算与采购窗口", "价值量化", "标杆复制"),
        bidding_lenses=("采购意向前置", "资格与案例要求", "总分包边界", "实施和运维约束"),
        outreach_lenses=("业务部门与信息化部门并行", "预算、采购和使用部门交叉核验"),
        ecosystem_lenses=("行业咨询与研究机构", "平台和技术厂商", "本地集成交付伙伴", "运营与合规伙伴"),
    )


def pick_industry_methodology_profile(
    industries: Iterable[str],
    *,
    keyword: str,
    research_focus: str | None,
) -> IndustryMethodologyProfile | None:
    candidates = [normalize_text(str(item)) for item in industries if normalize_text(str(item))]
    generic_candidates = {"大模型", "人工智能", "信息化"}
    priority_order = (
        "政务云",
        "文旅文博",
        "医疗",
        "教育",
        "金融",
        "能源",
        "数据中心",
        "智慧城市",
        "AI漫剧",
        "信息化",
        "大模型",
        "人工智能",
    )
    specific_candidates = [candidate for candidate in candidates if candidate not in generic_candidates]
    custom_candidates = [
        candidate
        for candidate in specific_candidates
        if candidate not in INDUSTRY_METHODOLOGY_PROFILES
    ]
    if custom_candidates:
        return build_generic_industry_methodology_profile(max(custom_candidates, key=len))
    sorted_candidates = sorted(
        specific_candidates,
        key=lambda candidate: priority_order.index(candidate) if candidate in priority_order else len(priority_order),
    )
    for candidate in sorted_candidates:
        profile = INDUSTRY_METHODOLOGY_PROFILES.get(candidate)
        if profile is not None:
            return profile
        return build_generic_industry_methodology_profile(candidate)
    for candidate in candidates:
        if candidate not in generic_candidates:
            continue
        profile = INDUSTRY_METHODOLOGY_PROFILES.get(candidate)
        if profile is not None:
            return profile
    lowered_seed = normalize_text(f"{keyword} {research_focus or ''}").lower()
    for label, aliases in INDUSTRY_SCOPE_ALIASES.items():
        if not any(normalize_text(alias).lower() in lowered_seed for alias in aliases):
            continue
        profile = INDUSTRY_METHODOLOGY_PROFILES.get(label)
        if profile is not None:
            return profile
    if any(token in lowered_seed for token in ("ai", "人工智能", "大模型", "生成式")):
        return INDUSTRY_METHODOLOGY_PROFILES.get("大模型")
    topic_seed = strip_query_noise(keyword, deps=scope_term_dependencies()) or normalize_text(keyword)
    topic_seed = normalize_text(
        re.sub(
            r"^(?:20\d{2}年|全国|国内|中国|全球|华东|华南|华北|西南|西北|东北|长三角|京津冀|粤港澳|成渝|地区)+",
            "",
            topic_seed,
        )
    )
    topic_match = re.search(
        r"([A-Za-z0-9\u4e00-\u9fa5]{2,16}?)(?:市场|趋势|格局|需求|机会|商机|研究|调研|分析)",
        topic_seed,
    )
    topic_label = normalize_text(topic_match.group(1) if topic_match else topic_seed[:16])
    return build_generic_industry_methodology_profile(topic_label or "通用主题")


def format_methodology_query_templates(
    profile: IndustryMethodologyProfile | None,
    *,
    keyword: str,
    research_focus: str | None,
    regions: list[str],
    industries: list[str],
    clients: list[str],
) -> list[str]:
    if profile is None:
        return []
    scope_deps = scope_term_dependencies()
    keyword_seed = strip_query_noise(keyword, deps=scope_deps) or normalize_text(keyword)
    if profile.authority_label.endswith("通用决策调研框架"):
        keyword_seed = normalize_text(
            " ".join(
                dedupe_strings(
                    [
                        profile.key,
                        "人工智能" if any(token in keyword.lower() for token in ("ai", "人工智能", "大模型", "生成式")) else "",
                    ],
                    3,
                )
            )
        )
    elif len(keyword_seed) > 24:
        keyword_seed = normalize_text(
            " ".join(
                dedupe_strings(
                    [
                        *(industries[:1] or [profile.key]),
                        "人工智能" if any(token in keyword.lower() for token in ("ai", "人工智能", "大模型", "生成式")) else "",
                    ],
                    3,
                )
            )
        )
    replacements = {
        "keyword": keyword_seed,
        "focus": strip_query_noise(research_focus or "", deps=scope_deps) or normalize_text(research_focus or ""),
        "region": normalize_text(regions[0]) if regions else "",
        "industry": normalize_text(industries[0]) if industries else profile.key,
        "client": normalize_text(clients[0]) if clients else "",
    }
    queries: list[str] = []
    for template in profile.query_templates:
        if "{client}" in template and not replacements["client"]:
            continue
        try:
            rendered = template.format(**replacements)
        except (KeyError, ValueError):
            rendered = template
        normalized = normalize_text(rendered)
        if normalized:
            queries.append(normalized)
    return dedupe_strings(queries, 8)


def build_industry_methodology_scope_hints(
    *,
    keyword: str,
    research_focus: str | None,
    regions: list[str],
    industries: list[str],
    clients: list[str],
) -> dict[str, object]:
    profile = pick_industry_methodology_profile(industries, keyword=keyword, research_focus=research_focus)
    if profile is None:
        return {}
    query_expansions = format_methodology_query_templates(
        profile,
        keyword=keyword,
        research_focus=research_focus,
        regions=regions,
        industries=industries,
        clients=clients,
    )
    return {
        "industry_methodology_profile": profile.key,
        "industry_methodology_authority": profile.authority_label,
        "industry_methodology_framework": profile.framework,
        "industry_methodology_questions": list(profile.primary_questions),
        "industry_methodology_source_preferences": list(profile.source_preferences),
        "industry_methodology_solution_lenses": list(profile.solution_lenses),
        "industry_methodology_sales_lenses": list(profile.sales_lenses),
        "industry_methodology_bidding_lenses": list(profile.bidding_lenses),
        "industry_methodology_outreach_lenses": list(profile.outreach_lenses),
        "industry_methodology_ecosystem_lenses": list(profile.ecosystem_lenses),
        "strategy_query_expansions": query_expansions,
        "strategy_scope_summary": normalize_text(f"{profile.authority_label}｜{profile.framework}"),
    }
