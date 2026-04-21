from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from html import unescape
from html.parser import HTMLParser
import json
import re
import ssl
from typing import Callable, Iterable
from urllib import parse, request

from app.core.config import get_settings
from app.schemas.research import (
    ResearchActionCardOut,
    ResearchCommercialSummaryOut,
    ResearchEntityGraphOut,
    ResearchEntityEvidenceOut,
    ResearchFollowupContextOut,
    ResearchNormalizedEntityOut,
    ResearchReportDocument,
    ResearchReportRequest,
    ResearchReportResponse,
    ResearchReportReadinessOut,
    ResearchReviewQueueItemOut,
    ResearchRankedEntityOut,
    ResearchScenarioOut,
    ResearchReportSectionOut,
    ResearchScoreFactorOut,
    ResearchSourceDiagnosticsOut,
    ResearchSourceOut,
    ResearchTechnicalAppendixOut,
)
from app.services.browser_content_extractor import extract_from_browser
from app.services.content_extractor import (
    ContentExtractionError,
    extract_domain,
    extract_from_reader_proxy,
    extract_from_url,
    normalize_text,
)
from app.services.language import localized_text
from app.services.llm_parser import (
    ResearchReportResult,
    parse_research_report_response,
    parse_research_strategy_scope_response,
    parse_research_strategy_refine_response,
)
from app.services.llm_service import get_llm_service, get_strategy_llm_service
from app.services.research_source_adapters import (
    CURATED_WECHAT_CHANNELS,
    collect_enabled_source_hits,
    read_research_source_settings,
)


@dataclass(slots=True)
class SearchHit:
    title: str
    url: str
    snippet: str
    search_query: str
    source_hint: str | None = None
    source_label: str | None = None


@dataclass(slots=True)
class SourceDocument:
    title: str
    url: str
    domain: str | None
    snippet: str
    search_query: str
    source_type: str
    content_status: str
    excerpt: str
    source_label: str | None = None
    source_tier: str = "media"
    source_origin: str = "search"


@dataclass(slots=True)
class RankedEntityCandidate:
    name: str
    score: int
    reasoning: str
    score_breakdown: list[ResearchScoreFactorOut]
    evidence_links: list[ResearchEntityEvidenceOut]


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


ResearchProgressCallback = Callable[[str, int, str], None]
ResearchSnapshotCallback = Callable[[ResearchReportResponse], None]


RESEARCH_SOURCE_SITE_QUERIES = (
    ("official_policy", "site:gov.cn {keyword} 领导 讲话 规划 战略"),
    ("public_procurement", "site:ccgp.gov.cn {keyword} 招标 中标 预算"),
    ("public_resource", "site:ggzy.gov.cn {keyword} 招标 中标 项目"),
    ("public_tender_portal", "site:cecbid.org.cn {keyword} 招标 中标 采购 预算"),
    ("public_service_portal", "site:cebpubservice.com {keyword} 招标 中标 项目"),
    ("public_procurement_portal", "site:china-cpp.com {keyword} 采购 招标 项目"),
    ("listed_filings", "site:cninfo.com.cn {keyword} 公告 年报 战略 预算"),
    ("hk_listed_filings", "site:hkexnews.hk {keyword} 公告 战略 合作"),
    ("global_filings", "site:sec.gov {keyword} annual report strategy partnership"),
    ("media_and_web", "{keyword} 中标 项目 二期 三期 四期 预算 金额"),
    ("client_peers", "{keyword} 甲方 同行 区域 动向 预算 项目"),
    ("winner_peers", "{keyword} 中标方 同行 集成商 厂商 动向 竞争"),
    ("ecosystem", "{keyword} 生态伙伴 渠道 集成商 ISV 咨询"),
)

INDUSTRY_SCOPE_ALIASES: dict[str, tuple[str, ...]] = {
    "政务云": ("政务云", "政务", "政府云", "政务大模型", "数据局", "智慧政务", "电子政务"),
    "大模型": ("大模型", "模型", "生成式AI", "AI", "人工智能", "算力", "MaaS"),
    "人工智能": ("人工智能", "AI", "智能", "大模型", "模型", "算力"),
    "AI漫剧": ("AI漫剧", "漫剧", "AI短剧", "AIGC短剧", "AIGC漫剧", "AI动画", "AIGC动画", "动漫短剧", "漫画短剧"),
    "数据中心": ("数据中心", "算力", "服务器", "机房", "存储", "智算中心"),
    "信息化": ("信息化", "数字化", "平台", "系统", "软件", "集成"),
    "智慧城市": ("智慧城市", "城市治理", "城市运行", "数字城市", "城市大脑"),
    "医疗": ("医疗", "医院", "卫健", "医共体", "医保"),
    "教育": ("教育", "学校", "高校", "职教", "教委"),
    "金融": ("金融", "银行", "证券", "保险", "资管"),
    "能源": ("能源", "电力", "电网", "光伏", "风电", "储能"),
}

THEME_QUERY_EXPANSION_TEMPLATES: dict[str, tuple[str, ...]] = {
    "AI漫剧": (
        "{keyword} AIGC动画 短剧 平台 商业化",
        "{keyword} 漫剧 IP 内容平台 合作 发行",
        "{keyword} AI短剧 动漫 版权 平台 投资",
        "site:mp.weixin.qq.com {keyword} AIGC动画 短剧 平台",
    ),
    "政务云": (
        "{keyword} 数据局 政务云 一体化 招标 预算",
        "{keyword} 政务云 建设 采购 中标 二期 三期",
        "site:gov.cn {keyword} 数据局 政务云 规划",
        "site:ggzy.gov.cn {keyword} 政务云 建设 项目",
    ),
}

THEME_GENERIC_SUPPRESSIONS: dict[str, tuple[str, ...]] = {
    "AI漫剧": ("大模型", "人工智能"),
}

THEME_STRICT_MUST_INCLUDE_TERMS: dict[str, tuple[str, ...]] = {
    "AI漫剧": ("ai漫剧", "漫剧", "ai短剧", "aigc短剧", "aigc漫剧", "ai动画", "aigc动画", "动漫短剧", "漫画短剧"),
}

THEME_ROLE_ARCHETYPES: dict[str, dict[str, tuple[str, ...]]] = {
    "AI漫剧": {
        "target": (
            "短剧内容平台运营方（待验证）",
            "动漫 IP 版权运营机构（待验证）",
            "文旅/教育数字内容运营主体（待验证）",
        ),
        "competitor": (
            "AIGC 短剧生成平台服务商（待验证）",
            "动漫内容工业化制作团队（待验证）",
            "AI 视频分镜与角色生成厂商（待验证）",
        ),
        "partner": (
            "动漫 IP 咨询与发行伙伴（待验证）",
            "区域内容集成与渠道分发伙伴（待验证）",
            "文旅/教育场景牵线伙伴（待验证）",
        ),
    },
    "政务云": {
        "target": (
            "省级数据局/政务服务管理局（待验证）",
            "地市级大数据中心或信息中心（待验证）",
            "政务云运营平台公司或城投平台（待验证）",
        ),
        "competitor": (
            "政务云总集厂商（待验证）",
            "政务一体化平台交付厂商（待验证）",
            "本地云资源与集成服务商（待验证）",
        ),
        "partner": (
            "区域总包与咨询伙伴（待验证）",
            "本地政务集成与运维伙伴（待验证）",
            "有政府关系的生态牵线方（待验证）",
        ),
    },
}

THEME_COMPANY_PUBLIC_SOURCE_SEEDS: dict[str, tuple[str, ...]] = {
    "AI漫剧": (
        "爱奇艺",
        "哔哩哔哩",
        "腾讯视频",
        "腾讯动漫",
        "优酷",
        "快手",
        "快看漫画",
        "抖音",
        "字节跳动",
        "阅文集团",
        "芒果超媒",
        "中文在线",
        "掌阅科技",
        "美图",
        "华策影视",
        "光线传媒",
        "上海儒意",
        "追光动画",
    ),
    "政务云": (
        "阿里云",
        "腾讯云",
        "华为",
        "中兴通讯",
        "神州数码",
        "新华三",
        "软通动力",
        "太极股份",
        "中国移动",
        "中国电信",
        "中国联通",
    ),
}

THEME_OFFICIAL_QUERY_TEMPLATES: dict[str, tuple[str, ...]] = {
    "AI漫剧": (
        "site:iqiyi.com {keyword} AIGC动画 短剧 合作 平台",
        "site:ir.iqiyi.com {keyword} 内容 业务 合作 生态",
        "site:bilibili.com {keyword} AIGC动画 内容 生态 合作",
        "site:ir.bilibili.com {keyword} 内容 合作 生态 平台",
        "site:v.qq.com {keyword} 短剧 动画 平台 合作",
        "site:ac.qq.com {keyword} 漫画 动漫 IP 合作 平台",
        "site:youku.com {keyword} 动漫 短剧 合作 平台",
        "site:yuewen.com {keyword} IP 动漫 短剧 合作",
        "site:mgtv.com {keyword} 内容 短剧 AIGC 合作",
        "site:kuaishou.com {keyword} 短剧 AIGC 内容 平台",
        "site:ir.kuaishou.com {keyword} 内容 业务 合作",
        "site:bytedance.com {keyword} 短剧 AIGC 内容 平台",
        "site:kuaikanmanhua.com {keyword} 漫画 IP 短剧 合作",
        "site:zhuiguang.com {keyword} 动画 IP 内容 合作",
        "site:col.com {keyword} 动漫 IP AIGC 合作",
    ),
    "政务云": (
        "site:aliyun.com {keyword} 政务云 政务 合作",
        "site:cloud.tencent.com {keyword} 政务云 合作 案例",
        "site:huawei.com {keyword} 政务云 行业 数字政府",
        "site:h3c.com {keyword} 政务云 数字政府 合作",
    ),
}

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

THEME_ENTITY_ALLOW_TOKENS: dict[str, dict[str, tuple[str, ...]]] = {
    "AI漫剧": {
        "target": ("视频", "动漫", "漫画", "影业", "传媒", "内容", "动画", "平台", "IP", "短剧", "文旅", "教育", "发行"),
        "competitor": ("视频", "动漫", "漫画", "影业", "传媒", "内容", "动画", "平台", "IP", "短剧", "AIGC", "AI", "生成"),
        "partner": ("咨询", "顾问", "发行", "渠道", "版权", "IP", "运营", "集成", "联盟", "文旅", "教育", "生态"),
    },
}

THEME_ENTITY_BLOCK_TOKENS: dict[str, dict[str, tuple[str, ...]]] = {
    "AI漫剧": {
        "target": ("政府", "市委", "市政府", "局", "委", "办", "中心", "大学", "学院", "学校", "医院", "银行", "证券"),
        "competitor": ("政府", "市委", "局", "委", "办", "中心", "大学", "学院", "学校", "医院", "银行", "证券"),
        "partner": ("政府", "市委", "局", "委", "办", "中心", "大学", "学院", "学校", "医院", "银行", "证券"),
    },
}


GENERIC_FOCUS_TOKENS = {
    "预算", "招标", "采购", "中标", "甲方", "竞品", "生态伙伴", "生态", "伙伴", "领导讲话",
    "领导", "讲话", "项目", "商机", "区域", "行业", "客户", "公司", "同行", "战略", "规划",
}

GENERIC_COMPANY_ANCHOR_TOKENS = {
    "ai", "aigc", "大模型", "模型", "人工智能", "短剧", "漫剧", "动画", "内容", "平台",
    "方案", "商机", "调研", "研究", "研报", "采购", "招标", "预算", "项目", "行业", "客户",
    "生态", "伙伴", "竞品", "机会", "线索",
}

COMPANY_ENTITY_QUERY_TOKENS = (
    "公司", "企业", "厂商", "平台方", "平台", "工作室", "发行方", "版权方", "内容方", "甲方公司",
    "公司名单", "企业名单", "头部玩家", "company", "companies", "player", "players", "studio",
)

HEAD_COMPANY_QUERY_TOKENS = (
    "头部", "龙头", "领先", "头部玩家", "top", "leading", "leader", "leaders", "头部公司",
)

GENERIC_COMPANY_NAME_TOKENS = (
    "集团", "公司", "有限公司", "股份有限公司", "科技", "智能", "信息", "传媒", "影业", "视频",
    "动漫", "漫画", "平台", "工作室", "网络", "数据", "云", "软件", "娱乐", "文化",
)

INVALID_COMPANY_ANCHOR_PHRASES = (
    "优先给具体公司",
    "官方业务联系方式",
    "公开渠道联络人信息",
    "公开业务联系方式",
    "公开联络人信息",
    "联系方式",
    "联络人信息",
    "聚焦内容平台",
    "聚焦动漫ip",
    "即使暂时没有明确公司",
)

SCOPE_PROMPT_NOISE_PREFIXES = (
    "我作为",
    "我想",
    "我们想",
    "我们要",
    "帮我",
    "请帮",
    "请把",
    "作为",
    "该在",
    "想在",
    "预计",
    "它将",
    "是依托",
    "不仅",
)

SCOPE_PROMPT_NOISE_TOKENS = (
    "我们公司",
    "找客户",
    "找项目",
    "决策权",
    "预算规模",
    "哪些重点公司",
    "这些客户",
    "一并调研",
    "把竞品公司",
    "竞品公司情况",
    "竟品公司",
    "包括但不限于",
    "精确到决策单位",
    "精确到决策部门",
    "已经有了哪些标杆案例",
    "可扩展的计算服务",
    "大型国际银行",
    "全球银行",
    "全球服务中心",
)

GENERIC_SCOPE_CLIENT_TOKENS = (
    "头部公司",
    "重点公司",
    "行业竞品公司",
    "甲方公司",
    "一家公司",
    "一人公司",
)

SCOPE_PROMPT_NOISE_REGEXES = (
    r"\b(?:maas|iaas|paas|saas|agent)\b.*公司",
    r"哪些[^。；;\n]{0,24}(?:公司|客户|部门|领导)",
    r"(?:预算|金额|规模)[^。；;\n]{0,16}如何",
)

QUERY_NOISE_SUFFIXES = (
    "相关商机",
    "商机",
    "机会",
    "线索",
    "情报",
    "调研",
    "研究",
    "研报",
    "专题",
    "分析",
    "建议",
    "方案",
    "报告",
)

PROCUREMENT_DOMAINS = {
    "ccgp.gov.cn",
    "www.ccgp.gov.cn",
    "ggzy.gov.cn",
    "www.ggzy.gov.cn",
    "chinabidding.com",
    "www.chinabidding.com",
}

GENERIC_CONTENT_DOMAINS = {
    "zhuanlan.zhihu.com",
    "www.zhihu.com",
    "www.bilibili.com",
    "segmentfault.com",
    "www.cnblogs.com",
    "news.qq.com",
    "mp.weixin.qq.com",
}

POLICY_DOMAINS = {
    "gov.cn",
    "www.gov.cn",
}

EXCHANGE_DOMAINS = {
    "cninfo.com.cn",
    "www.cninfo.com.cn",
    "hkexnews.hk",
    "www.hkexnews.hk",
    "sec.gov",
    "www.sec.gov",
}

REGION_TOKENS = (
    "北京", "上海", "广州", "深圳", "杭州", "南京", "苏州", "成都", "重庆", "武汉", "西安",
    "天津", "青岛", "郑州", "长沙", "合肥", "福州", "厦门", "宁波", "无锡", "济南", "沈阳",
    "大连", "哈尔滨", "长春", "昆明", "南宁", "南昌", "石家庄", "太原", "贵阳", "兰州",
    "乌鲁木齐", "呼和浩特", "海南", "河北", "河南", "山东", "山西", "陕西", "江苏", "浙江",
    "安徽", "福建", "江西", "湖北", "湖南", "广东", "广西", "云南", "贵州", "四川", "重庆",
    "甘肃", "青海", "宁夏", "新疆", "西藏", "内蒙古", "辽宁", "吉林", "黑龙江",
)

REGION_SCOPE_ALIASES: dict[str, tuple[str, ...]] = {
    "长三角": ("长三角", "上海", "江苏", "浙江", "安徽", "南京", "苏州", "杭州", "宁波", "无锡", "合肥"),
    "京津冀": ("京津冀", "北京", "天津", "河北"),
    "粤港澳": ("粤港澳", "广东", "广州", "深圳", "珠海", "佛山", "东莞", "中山", "香港", "澳门"),
    "成渝": ("成渝", "成都", "重庆", "四川"),
}

ORG_PATTERN = re.compile(
    r"([A-Za-z0-9\u4e00-\u9fa5·（）()]{2,40}"
    r"(?:集团|公司|有限公司|股份有限公司|研究院|研究所|大学|医院|银行|政府|厅|局|委|办|中心|学院|学校|科技|智能|信息|控股|实验室))"
)

COMPACT_ENTITY_PATTERN = re.compile(
    r"([A-Za-z0-9\u4e00-\u9fa5·]{2,24}(?:数码|软件|信息|科技|咨询|顾问|股份|集团|服务|运营|网络|系统|通信|集成|研究院|协会|联盟))"
)

SPECIAL_ENTITY_ALIASES = (
    "德勤", "普华永道", "毕马威", "安永", "埃森哲", "IBM",
    "阿里云", "腾讯云", "华为", "中兴通讯", "神州数码", "新华三",
    "太极股份", "东软集团", "浪潮软件", "软通动力", "中电金信",
    "中国移动", "中国电信", "中国联通", "用友网络", "金蝶",
)

PARTNER_CONNECTOR_ALIASES = (
    "德勤", "普华永道", "毕马威", "安永", "埃森哲",
    "神州数码", "新华三", "软通动力", "中电金信",
    "中国移动", "中国电信", "中国联通", "太极股份",
)

KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS: dict[str, tuple[tuple[str, str], ...]] = {
    "爱奇艺": (
        ("https://www.iqiyi.com/", "爱奇艺官网"),
        ("https://ir.iqiyi.com/", "爱奇艺投资者关系"),
    ),
    "快手": (
        ("https://www.kuaishou.com/", "快手官网"),
        ("https://ir.kuaishou.com/", "快手投资者关系"),
    ),
    "抖音": (
        ("https://www.douyin.com/", "抖音官网"),
        ("https://www.bytedance.com/zh/", "字节跳动官网"),
    ),
    "字节跳动": (
        ("https://www.bytedance.com/zh/", "字节跳动官网"),
        ("https://www.bytedance.com/zh/contact", "字节跳动联系我们"),
    ),
    "阿里云": (
        ("https://www.aliyun.com/", "阿里云官网"),
        ("https://www.alibabagroup.com/cn/global/home", "阿里巴巴集团官网"),
    ),
    "优酷": (
        ("https://www.youku.com/", "优酷官网"),
        ("https://www.alibabagroup.com/cn/global/home", "阿里巴巴集团官网"),
    ),
    "腾讯云": (
        ("https://cloud.tencent.com/", "腾讯云官网"),
        ("https://www.tencent.com/zh-cn/", "腾讯官网"),
    ),
    "腾讯视频": (
        ("https://v.qq.com/", "腾讯视频官网"),
        ("https://www.tencent.com/zh-cn/", "腾讯官网"),
    ),
    "腾讯动漫": (
        ("https://ac.qq.com/", "腾讯动漫官网"),
        ("https://www.tencent.com/zh-cn/", "腾讯官网"),
    ),
    "华为": (
        ("https://www.huawei.com/cn/", "华为官网"),
        ("https://www.huawei.com/cn/contact-us", "华为联系我们"),
    ),
    "哔哩哔哩": (
        ("https://www.bilibili.com/", "哔哩哔哩官网"),
        ("https://ir.bilibili.com/", "哔哩哔哩投资者关系"),
    ),
    "快看漫画": (
        ("https://www.kuaikanmanhua.com/", "快看漫画官网"),
        ("https://www.kuaikanmanhua.com/about", "快看漫画公开入口"),
    ),
    "阅文集团": (
        ("https://www.yuewen.com/", "阅文集团官网"),
        ("https://ir.yuewen.com/", "阅文集团投资者关系"),
    ),
    "芒果超媒": (
        ("https://www.mgtv.com/", "芒果TV官网"),
        ("https://www.mangomedia.com.cn/", "芒果超媒官网"),
    ),
    "小红书": (
        ("https://www.xiaohongshu.com/", "小红书官网"),
        ("https://www.xiaohongshu.com/explore", "小红书公开入口"),
    ),
    "美图": (
        ("https://www.meitu.com/", "美图官网"),
        ("https://ir.meitu.com/", "美图投资者关系"),
    ),
    "中文在线": (
        ("https://www.col.com/", "中文在线官网"),
        ("https://www.col.com/About/contact", "中文在线联系我们"),
    ),
    "掌阅科技": (
        ("https://www.zhangyue.com/", "掌阅官网"),
        ("https://www.zhangyue.com/about", "掌阅公开入口"),
    ),
    "华策影视": (
        ("https://www.huacemedia.com/", "华策影视官网"),
        ("https://www.huacemedia.com/contact", "华策影视联系我们"),
    ),
    "光线传媒": (
        ("https://www.ewang.com/", "光线传媒官网"),
        ("https://www.ewang.com/about", "光线传媒公开入口"),
    ),
    "上海儒意": (
        ("https://www.ruyi.cn/", "儒意官网"),
        ("https://www.ruyi.cn/contact", "儒意联系我们"),
    ),
    "追光动画": (
        ("https://www.zhuiguang.com/", "追光动画官网"),
        ("https://www.zhuiguang.com/about", "追光动画公开入口"),
    ),
    "中兴通讯": (
        ("https://www.zte.com.cn/china/", "中兴通讯官网"),
        ("https://www.zte.com.cn/china/about/contact", "中兴通讯联系我们"),
    ),
    "中国移动": (
        ("https://www.10086.cn/", "中国移动官网"),
        ("https://ir.chinamobile.com/", "中国移动投资者关系"),
    ),
    "中国电信": (
        ("https://www.189.cn/", "中国电信官网"),
        ("https://www.chinatelecom-h.com/", "中国电信投资者关系"),
    ),
    "中国联通": (
        ("https://www.10010.com/", "中国联通官网"),
        ("https://www.chinaunicom.com.hk/", "中国联通投资者关系"),
    ),
    "神州数码": (
        ("https://www.digitalchina.com/", "神州数码官网"),
        ("https://www.digitalchina.com/Contact/index.html", "神州数码联系我们"),
    ),
    "新华三": (
        ("https://www.h3c.com/cn/", "新华三官网"),
        ("https://www.h3c.com/cn/About_H3C/Contact_Us/", "新华三联系我们"),
    ),
    "软通动力": (
        ("https://www.isoftstone.com/", "软通动力官网"),
        ("https://www.isoftstone.com/contact", "软通动力联系我们"),
    ),
    "太极股份": (
        ("https://www.taiji.com.cn/", "太极股份官网"),
        ("https://www.taiji.com.cn/col/col25/index.html", "太极股份联系我们"),
    ),
    "德勤": (
        ("https://www2.deloitte.com/cn/zh.html", "德勤官网"),
        ("https://www2.deloitte.com/cn/zh/pages/about-deloitte/articles/contact-us.html", "德勤联系我们"),
    ),
    "埃森哲": (
        ("https://www.accenture.com/cn-zh", "埃森哲官网"),
        ("https://www.accenture.com/cn-zh/about/contact-us", "埃森哲联系我们"),
    ),
}

KNOWN_LIGHTWEIGHT_ENTITY_NAMES = {
    *SPECIAL_ENTITY_ALIASES,
    *KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS.keys(),
}

_RESEARCH_ACCOUNT_ALIAS_MAP = {
    "上海市文旅局": "上海市文化和旅游局",
    "华为云服务": "华为云",
    "阿里巴巴云": "阿里云",
    "腾讯视频": "腾讯",
    "腾讯动漫": "腾讯",
}

_OFFICIAL_DOMAIN_ENTITY_MAP: dict[str, str] = {}
for _canonical_name, _seed_sources in KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS.items():
    for _seed_url, _seed_label in _seed_sources:
        _seed_domain = normalize_text(extract_domain(_seed_url) or "").lower().removeprefix("www.")
        if _seed_domain:
            _OFFICIAL_DOMAIN_ENTITY_MAP.setdefault(_seed_domain, _canonical_name)

ENTITY_BLACKLIST_TOKENS = (
    "发布", "推进", "围绕", "布局", "显示", "启动", "持续", "建设", "合作", "联合", "方案",
    "项目", "预算", "政务云", "咨询与集成", "联合交付", "公开线索", "项目建设",
)

ENTITY_INVALID_PHRASE_TOKENS = (
    "怎么办", "如何", "制作", "利用", "是指", "一种", "相关商机", "相关讯息", "教程", "指南",
    "步骤", "案例拆解", "经验", "相关", "方向", "赛道", "行业", "领域", "信息", "新闻",
    "建议追加", "如果短期", "当前关键词范围", "公开线索", "优先给具体公司",
    "官方业务联系方式", "公开渠道联络人信息", "公开业务联系方式",
    "美国证券交易委", "证券交易委", "已向美国证券交易委", "公有云服务", "基础设施即服务", "模型即服务",
)

LOW_VALUE_ENTITY_NAME_TOKENS = (
    "会员中心", "入局", "掘金赛道", "保姆级", "最新版", "工作流", "完全指南", "怎么个事",
    "所有人都", "关于加强", "促进政府", "已成为", "改变系统", "支撑软件", "应用系统", "弹性服务",
    "模型服务", "公有云服务", "基础设施即服务", "模型即服务", "主力与协办", "标签服务", "用户画像服务",
)

ENTITY_FRAGMENT_PREFIX_TOKENS = (
    "此次", "由于", "相应", "相关", "本次", "该", "该类", "这个", "这类", "基于", "围绕", "通过",
    "针对", "聚焦", "正在", "已经", "主要", "因为", "如果", "对于", "已向", "即使",
)

ENTITY_FRAGMENT_INFIX_TOKENS = (
    "主要基于", "相应调整", "调整系统", "相应系统", "由于公司", "基于公司", "围绕公司", "赋能",
    "服务于", "用于", "模式", "路径", "打法", "策略", "方法", "场景", "机会", "商机",
)

ENTITY_SUFFIX_TOKENS = (
    "集团", "公司", "有限公司", "股份有限公司", "研究院", "研究所", "大学", "医院", "银行", "政府",
    "厅", "局", "委", "办", "中心", "学院", "学校", "科技", "信息", "控股", "实验室",
    "协会", "联盟", "咨询", "顾问", "集成", "服务", "运营", "系统", "通信",
)

PERSON_ROLE_PATTERN = re.compile(
    r"([\u4e00-\u9fa5]{2,4})(?:同志)?(?:在[^。；;\n]{0,12})?"
    r"(?:表示|指出|强调|要求|担任|出席|主持|提到|介绍)?"
    r"[^。；;\n]{0,18}?"
    r"(书记|市长|局长|厅长|主任|董事长|总经理|总裁|副总裁|院长|校长|负责人)"
)

DEPARTMENT_PATTERN = re.compile(
    r"([A-Za-z0-9\u4e00-\u9fa5·（）()]{2,40}"
    r"(?:采购部|采购中心|招标办|招采中心|集采中心|信息中心|信息化部|数字化部|科技部|战略发展部|数据局|数据资源局|办公室|财务部|计划财务部|运营部|网络安全部|政务服务中心|行政审批局|事业发展部|建设管理部|投资管理部))"
)

EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:\+?86[- ]?)?(?:1[3-9]\d{9}|0\d{2,3}[- ]?\d{7,8})(?!\d)"
)

MONEY_PATTERN = re.compile(
    r"(?:预算|投资|金额|规模|采购金额|中标金额|合同金额|总投资|资金|经费|财政投入|项目投资)"
    r"[^。；;\n]{0,28}?"
    r"(\d+(?:\.\d+)?(?:亿|万|千)?元|\d+(?:\.\d+)?\s?(?:million|billion|mn|bn)\s?(?:usd|dollars?)?)",
    re.IGNORECASE,
)

SOURCE_DATE_PATTERN = re.compile(
    r"(?P<year>20\d{2}|19\d{2})"
    r"(?:[\-/年\.](?P<month>0?[1-9]|1[0-2]))?"
    r"(?:[\-/月\.](?P<day>0?[1-9]|[12]\d|3[01]))?"
    r"(?:日)?"
)

SOURCE_MAX_AGE_YEARS = 7


class _DuckDuckGoResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchHit] = []
        self._current_title: list[str] = []
        self._current_snippet: list[str] = []
        self._current_url: str | None = None
        self._current_query: str = ""
        self._capture_mode: str | None = None

    def begin_query(self, query: str) -> None:
        self._current_query = query

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        attrs_map = {str(k).lower(): str(v) for k, v in attrs if k and v}
        class_name = attrs_map.get("class", "")
        href = attrs_map.get("href", "")
        if tag == "a" and "result__a" in class_name:
            self._flush_current()
            self._current_url = _unwrap_duckduckgo_link(href)
            self._capture_mode = "title"
            return
        if tag == "a" and "result__snippet" in class_name:
            if not self._current_url:
                self._current_url = _unwrap_duckduckgo_link(href)
            self._capture_mode = "snippet"

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        if tag == "a" and self._capture_mode in {"title", "snippet"}:
            self._capture_mode = None

    def handle_data(self, data: str) -> None:  # type: ignore[override]
        text = normalize_text(data)
        if not text:
            return
        if self._capture_mode == "title":
            self._current_title.append(text)
        elif self._capture_mode == "snippet":
            self._current_snippet.append(text)

    def close(self) -> None:
        super().close()
        self._flush_current()

    def _flush_current(self) -> None:
        title = normalize_text(" ".join(self._current_title))
        snippet = normalize_text(" ".join(self._current_snippet))
        url = normalize_text(self._current_url or "")
        if title and url:
            self.results.append(
                SearchHit(
                    title=title,
                    url=url,
                    snippet=snippet,
                    search_query=self._current_query,
                )
            )
        self._current_title = []
        self._current_snippet = []
        self._current_url = None
        self._capture_mode = None


class _BingResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchHit] = []
        self._current_query: str = ""
        self._inside_result = False
        self._result_depth = 0
        self._capture_title = False
        self._capture_snippet = False
        self._current_title: list[str] = []
        self._current_snippet: list[str] = []
        self._current_url: str | None = None

    def begin_query(self, query: str) -> None:
        self._current_query = query

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        attrs_map = {str(k).lower(): str(v) for k, v in attrs if k and v}
        class_name = attrs_map.get("class", "")
        href = attrs_map.get("href", "")
        if tag == "li" and "b_algo" in class_name:
            self._flush_current()
            self._inside_result = True
            self._result_depth = 1
            return
        if self._inside_result:
            self._result_depth += 1
            if tag == "a" and href.startswith("http") and self._current_url is None:
                self._current_url = normalize_http_url(href)
                self._capture_title = True
                return
            if tag == "p":
                self._capture_snippet = True

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        if self._capture_title and tag == "a":
            self._capture_title = False
        if self._capture_snippet and tag == "p":
            self._capture_snippet = False
        if self._inside_result:
            self._result_depth -= 1
            if self._result_depth <= 0:
                self._inside_result = False
                self._flush_current()

    def handle_data(self, data: str) -> None:  # type: ignore[override]
        text = normalize_text(data)
        if not text:
            return
        if self._capture_title:
            self._current_title.append(text)
        elif self._capture_snippet:
            self._current_snippet.append(text)

    def close(self) -> None:
        super().close()
        self._flush_current()

    def _flush_current(self) -> None:
        title = normalize_text(" ".join(self._current_title))
        snippet = normalize_text(" ".join(self._current_snippet))
        url = normalize_text(self._current_url or "")
        if title and url:
            self.results.append(
                SearchHit(
                    title=title,
                    url=url,
                    snippet=snippet,
                    search_query=self._current_query,
                )
            )
        self._current_title = []
        self._current_snippet = []
        self._current_url = None
        self._capture_title = False
        self._capture_snippet = False


def _unwrap_duckduckgo_link(url: str) -> str:
    raw = unescape(url or "").strip()
    if not raw:
        return ""
    if raw.startswith("//"):
        raw = f"https:{raw}"
    parsed = parse.urlparse(raw)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        params = parse.parse_qs(parsed.query)
        redirect = params.get("uddg")
        if redirect:
            return parse.unquote(redirect[0])
    return raw


def _truncate_text(value: str, limit: int) -> str:
    text = normalize_text(value)
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rstrip(" ，,：:；;")
    return f"{cut}…"


def _build_scoped_official_query_expansions(
    keyword: str,
    research_focus: str | None,
    *,
    scope_hints: dict[str, object] | None = None,
    include_wechat: bool = False,
    limit: int = 8,
) -> list[str]:
    scope_hints = scope_hints or {}
    normalized_keyword = _strip_query_noise(keyword) or normalize_text(keyword)
    normalized_focus = _sanitize_research_focus_text(research_focus)
    regions = [normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    industries = [normalize_text(str(item)) for item in scope_hints.get("industries", []) if normalize_text(str(item))]
    buyers = [normalize_text(str(item)) for item in scope_hints.get("clients", []) if normalize_text(str(item))]
    topic_anchors = _extract_topic_anchor_terms(normalized_keyword, normalized_focus)
    expanded_regions = _expand_region_scope_terms(regions[:1])[:3]
    official_regions = expanded_regions or regions[:1]
    official_industries = _dedupe_strings(
        [
            *industries[:1],
            *[
                normalize_text(alias)
                for alias in (INDUSTRY_SCOPE_ALIASES.get(normalize_text(industries[0]), ()) if industries else ())
                if normalize_text(alias)
            ][:2],
            *topic_anchors[:1],
        ],
        3,
    )
    official_buyers = _dedupe_strings(buyers[:2], 2)
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

    if official_buyers:
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

    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized = normalize_text(query)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped[:limit]


def _build_query_plan(
    keyword: str,
    research_focus: str | None,
    include_wechat: bool,
    *,
    scope_hints: dict[str, object] | None = None,
    preferred_wechat_accounts: Iterable[str] | None = None,
    limit: int = 8,
) -> list[str]:
    normalized_keyword = _strip_query_noise(keyword) or normalize_text(keyword)
    normalized_focus = _sanitize_research_focus_text(research_focus)
    scope_hints = scope_hints or {}
    scope_regions = [normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    scope_industries = [normalize_text(str(item)) for item in scope_hints.get("industries", []) if normalize_text(str(item))]
    scope_clients = [normalize_text(str(item)) for item in scope_hints.get("clients", []) if normalize_text(str(item))]
    topic_anchors = _extract_topic_anchor_terms(normalized_keyword, normalized_focus)
    strategy_query_expansions = [
        normalize_text(str(item))
        for item in scope_hints.get("strategy_query_expansions", [])
        if normalize_text(str(item))
    ]
    scoped_official_queries = _build_scoped_official_query_expansions(
        normalized_keyword,
        normalized_focus,
        scope_hints=scope_hints,
        include_wechat=include_wechat,
        limit=8,
    )
    matched_theme_labels = [
        label
        for label, aliases in INDUSTRY_SCOPE_ALIASES.items()
        if any(alias in f"{normalized_keyword} {normalized_focus}" for alias in aliases)
    ]
    scoped_prefix = normalize_text(" ".join([*scope_regions[:1], *scope_industries[:1], *scope_clients[:1]]))
    scoped_keyword = normalize_text(" ".join([scoped_prefix, normalized_keyword])) if scoped_prefix else normalized_keyword
    queries = [scoped_keyword]
    scoped_region_expansions = _expand_region_scope_terms(scope_regions[:1])[:4]
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
        for template in THEME_QUERY_EXPANSION_TEMPLATES.get(label, ()):
            queries.append(template.format(keyword=scoped_keyword))
    for _, template in RESEARCH_SOURCE_SITE_QUERIES:
        queries.append(template.format(keyword=scoped_keyword))
    if normalized_focus:
        queries.append(f"{scoped_keyword} {normalized_focus}")
    if include_wechat:
        queries.append(f"site:mp.weixin.qq.com {scoped_keyword}")
        queries.append(f"site:mp.weixin.qq.com {scoped_keyword} 招标 中标 预算")
        if normalized_focus:
            queries.append(f"site:mp.weixin.qq.com {scoped_keyword} {normalized_focus} 采购 战略")
        for account in _dedupe_strings(preferred_wechat_accounts or [], 3):
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
    seen: set[str] = set()
    deduped: list[str] = []
    for query in queries:
        if not query or query in seen:
            continue
        seen.add(query)
        deduped.append(query)
    return deduped[:limit]


def _safe_urlopen(req: request.Request, *, timeout_seconds: int):
    try:
        return request.urlopen(req, timeout=timeout_seconds)
    except Exception as exc:
        message = str(exc).lower()
        if "certificate verify failed" not in message:
            raise
        insecure_context = ssl._create_unverified_context()
        return request.urlopen(req, timeout=timeout_seconds, context=insecure_context)


def _search_duckduckgo(query: str, *, timeout_seconds: int, limit: int) -> list[SearchHit]:
    url = f"https://html.duckduckgo.com/html/?q={parse.quote_plus(query)}"
    req = request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            )
        },
    )
    with _safe_urlopen(req, timeout_seconds=timeout_seconds) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    parser = _DuckDuckGoResultParser()
    parser.begin_query(query)
    parser.feed(html)
    parser.close()
    return parser.results[:limit]


def _search_bing(query: str, *, timeout_seconds: int, limit: int) -> list[SearchHit]:
    url = f"https://www.bing.com/search?q={parse.quote_plus(query)}&setlang=zh-Hans"
    req = request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            )
        },
    )
    with _safe_urlopen(req, timeout_seconds=timeout_seconds) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    parser = _BingResultParser()
    parser.begin_query(query)
    parser.feed(html)
    parser.close()
    return parser.results[:limit]


def _search_public_web(query: str, *, timeout_seconds: int, limit: int) -> list[SearchHit]:
    results: list[SearchHit] = []
    try:
        results.extend(_search_duckduckgo(query, timeout_seconds=timeout_seconds, limit=limit))
    except Exception:
        pass
    if len(results) < max(2, limit // 2):
        try:
            results.extend(_search_bing(query, timeout_seconds=timeout_seconds, limit=limit))
        except Exception:
            pass
    return _dedupe_hits(results)[:limit]


def _tokenize_for_match(*values: str) -> list[str]:
    text = normalize_text(" ".join(values))
    if not text:
        return []
    rough = re.split(r"[\s,，、/|:：;；（）()]+", text)
    tokens = [token.strip() for token in rough if len(token.strip()) >= 2]
    compact = re.sub(r"\s+", "", text)
    if 2 <= len(compact) <= 24:
        tokens.append(compact)
    return list(dict.fromkeys(tokens))


@lru_cache(maxsize=8192)
def _looks_like_scope_prompt_noise(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return False
    lowered = normalized.lower()
    if any(lowered.startswith(prefix) for prefix in [item.lower() for item in SCOPE_PROMPT_NOISE_PREFIXES]):
        return True
    if any(token.lower() in lowered for token in SCOPE_PROMPT_NOISE_TOKENS):
        return True
    if any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in SCOPE_PROMPT_NOISE_REGEXES):
        return True
    if "的" in normalized and not any(token in normalized for token in ENTITY_SUFFIX_TOKENS):
        return True
    if any(token in normalized for token in ("哪些", "如何", "怎么", "需求", "预算", "招投标", "找客户", "找项目", "哪位领导")):
        return True
    if (
        any(token in normalized for token in ("和", "及", "与"))
        and any(token in normalized for token in ("全球", "大型", "国际", "重点"))
        and not any(token in normalized for token in ("集团", "公司", "局", "委", "办", "中心", "大学", "医院"))
    ):
        return True
    return False


def _strip_query_noise(value: str) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    stripped = text
    for suffix in QUERY_NOISE_SUFFIXES:
        stripped = re.sub(f"{re.escape(suffix)}$", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"(相关|相關|关于|關於)$", "", stripped, flags=re.IGNORECASE)
    return normalize_text(stripped) or text


def _sanitize_research_focus_text(value: str | None) -> str:
    text = _strip_query_noise(value or "")
    if not text:
        return ""
    negative_scope_phrases = (
        "不要扩展到",
        "不要扩展至",
        "不扩展到",
        "不扩展至",
        "不要包含",
        "不包含",
        "不考虑",
        "排除",
        "剔除",
    )
    for prefix in (
        "重点关注:",
        "重点关注：",
        "包括但不限于",
        "优先关注",
        "最好精确到",
        "精确到",
    ):
        if text.startswith(prefix):
            text = normalize_text(text[len(prefix) :])
    segments = re.split(r"[，,；;。]+", text)
    cleaned_segments: list[str] = []
    for segment in segments:
        normalized = normalize_text(segment)
        if not normalized:
            continue
        if any(phrase in normalized for phrase in negative_scope_phrases):
            continue
        if any(phrase in normalized for phrase in INVALID_COMPANY_ANCHOR_PHRASES):
            continue
        if _looks_like_scope_prompt_noise(normalized):
            continue
        cleaned_segments.append(normalized)
    compact_tokens = [
        token
        for token in _tokenize_for_match(" ".join(cleaned_segments))
        if token not in GENERIC_FOCUS_TOKENS
        and len(normalize_text(token)) >= 2
        and not any(phrase in normalize_text(token) for phrase in INVALID_COMPANY_ANCHOR_PHRASES)
    ]
    if compact_tokens:
        return normalize_text(" ".join(_dedupe_strings(compact_tokens, 8)))
    return normalize_text(" ".join(cleaned_segments[:2]))


def _extract_explicit_exclusion_terms(value: str | None) -> list[str]:
    text = normalize_text(value or "")
    if not text:
        return []
    segments = re.split(r"[，,；;。]+", text)
    terms: list[str] = []
    negative_scope_phrases = (
        "不要扩展到",
        "不要扩展至",
        "不扩展到",
        "不扩展至",
        "不要包含",
        "不包含",
        "不考虑",
        "排除",
        "剔除",
    )
    for segment in segments:
        normalized = normalize_text(segment)
        if not normalized:
            continue
        for prefix in negative_scope_phrases:
            if normalized.startswith(prefix):
                tail = normalize_text(normalized[len(prefix) :])
                if not tail:
                    continue
                for part in re.split(r"[、/\\| ]+", tail):
                    candidate = normalize_text(part)
                    if candidate and candidate not in GENERIC_FOCUS_TOKENS:
                        terms.append(candidate)
                break
    return _dedupe_strings(terms, 8)


def _extract_topic_anchor_terms(keyword: str, research_focus: str | None) -> list[str]:
    keyword_seed = _strip_query_noise(keyword)
    focus_seed = _sanitize_research_focus_text(research_focus)
    anchors: list[str] = []
    for seed in (keyword_seed, focus_seed):
        if not seed:
            continue
        if len(seed) <= 18 and len(seed.split()) <= 4:
            anchors.append(seed)
        compact = re.sub(r"\s+", "", seed)
        if 2 <= len(compact) <= 24:
            anchors.append(compact)
        anchors.extend(
            token
            for token in _tokenize_for_match(seed)
            if token not in GENERIC_FOCUS_TOKENS
            and len(normalize_text(token)) >= 2
            and not any(phrase in normalize_text(token) for phrase in INVALID_COMPANY_ANCHOR_PHRASES)
        )
    lowered_seed = normalize_text(f"{keyword_seed} {focus_seed}").lower()
    matched_labels: list[str] = []
    for label, aliases in INDUSTRY_SCOPE_ALIASES.items():
        if any(alias.lower() in lowered_seed for alias in aliases):
            matched_labels.append(label)
            anchors.append(label)
            anchors.extend(aliases)
    for dominant, suppressed in THEME_GENERIC_SUPPRESSIONS.items():
        if dominant in matched_labels:
            anchors = [
                anchor
                for anchor in anchors
                if normalize_text(anchor) == dominant
                or normalize_text(anchor) not in suppressed
                and normalize_text(anchor).lower() not in {
                    normalize_text(alias).lower()
                    for suppressed_label in suppressed
                    for alias in INDUSTRY_SCOPE_ALIASES.get(suppressed_label, ())
                    if normalize_text(alias)
                }
            ]
    return list(dict.fromkeys(normalize_text(anchor) for anchor in anchors if normalize_text(anchor)))


def _extract_company_anchor_terms(keyword: str, research_focus: str | None) -> list[str]:
    keyword_seed = normalize_text(_strip_query_noise(keyword))
    focus_seed = normalize_text(_sanitize_research_focus_text(research_focus))
    seed_text = normalize_text(" ".join(item for item in [keyword_seed, focus_seed] if normalize_text(item)))
    if not keyword_seed and not focus_seed:
        return []
    anchors: list[str] = []
    for alias in SPECIAL_ENTITY_ALIASES:
        if alias in seed_text:
            anchors.append(alias)
    for match in ORG_PATTERN.findall(keyword_seed):
        anchors.append(normalize_text(match))
    for match in ORG_PATTERN.findall(focus_seed):
        normalized = normalize_text(match)
        if normalized in SPECIAL_ENTITY_ALIASES or any(normalized.endswith(token) for token in ("集团", "公司", "有限公司", "股份有限公司", "研究院", "研究所")):
            anchors.append(normalized)
    for match in COMPACT_ENTITY_PATTERN.findall(keyword_seed):
        anchors.append(normalize_text(match))
    for token in _tokenize_for_match(keyword_seed):
        normalized = normalize_text(token)
        lowered = normalized.lower()
        if not normalized or normalized in GENERIC_FOCUS_TOKENS:
            continue
        if any(phrase in normalized for phrase in INVALID_COMPANY_ANCHOR_PHRASES):
            continue
        if _looks_like_scope_prompt_noise(normalized):
            continue
        if normalized in SPECIAL_ENTITY_ALIASES:
            anchors.append(normalized)
            continue
        if any(theme in lowered for theme in GENERIC_COMPANY_ANCHOR_TOKENS):
            continue
        if any(theme in normalized for theme in GENERIC_FOCUS_TOKENS):
            continue
        if _is_lightweight_entity_name(normalized):
            anchors.append(normalized)
    cleaned: list[str] = []
    for anchor in anchors:
        normalized = normalize_text(anchor)
        if not normalized:
            continue
        if any(phrase in normalized for phrase in INVALID_COMPANY_ANCHOR_PHRASES):
            continue
        if _looks_like_scope_prompt_noise(normalized):
            continue
        if _looks_like_fragment_entity_name(normalized):
            continue
        if _contains_low_value_entity_token(normalized):
            continue
        if normalized.startswith(("如", "例如", "比如", "诸如", "優先給", "优先给", "官方", "公开")):
            continue
        cleaned.append(normalized)
    return list(dict.fromkeys(cleaned))


def _clean_company_anchor_candidate(value: str) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    if _looks_like_scope_prompt_noise(normalized):
        return ""
    normalized = re.sub(r"^(分析|梳理|研究|盘点|聚焦|关注|围绕|拆解|追踪|观察|看|找|筛选)", "", normalized)
    normalized = re.sub(r"(?:这些|这类|相关)?公司.*$", "", normalized)
    normalized = re.sub(r"(?:的)?(?:AI|AIGC)?商机.*$", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"(合作平台|平台合作|商业化路径|商业模式|机会点|落地路径|案例分析).*$", "", normalized)
    normalized = normalize_text(normalized.strip("：:，,、/| "))
    if _looks_like_scope_prompt_noise(normalized):
        return ""
    return normalized


def _resolved_company_anchor_terms(
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object] | None = None,
) -> list[str]:
    scope = scope_hints or {}
    candidates: list[str] = []
    candidates.extend(_extract_company_anchor_terms(keyword, research_focus))
    candidates.extend(normalize_text(str(item)) for item in scope.get("company_anchors", []) or [])
    candidates.extend(normalize_text(str(item)) for item in scope.get("clients", []) or [])
    candidates.extend(normalize_text(str(item)) for item in scope.get("seed_companies", []) or [])
    cleaned: list[str] = []
    generic_company_like_tokens = ("头部", "行业", "赛道", "领域", "玩家", "公司名单", "企业名单", "商业化", "商机")
    generic_theme_tokens = ("ai漫剧", "漫剧", "aigc", "动画", "短剧")
    company_suffixes = ("集团", "公司", "有限公司", "股份有限公司", "科技", "传媒", "控股", "影业", "视频")
    for candidate in candidates:
        normalized = _clean_company_anchor_candidate(candidate)
        lowered = normalized.lower()
        if not normalized:
            continue
        if any(token in lowered for token in generic_company_like_tokens):
            continue
        if any(token in lowered for token in generic_theme_tokens) and normalized not in KNOWN_LIGHTWEIGHT_ENTITY_NAMES:
            continue
        if normalized in KNOWN_LIGHTWEIGHT_ENTITY_NAMES or normalized in SPECIAL_ENTITY_ALIASES:
            cleaned.append(normalized)
            continue
        if any(normalized.endswith(token) for token in company_suffixes):
            cleaned.append(normalized)
            continue
        if re.fullmatch(r"[A-Za-z0-9\u4e00-\u9fa5·]{2,10}", normalized):
            cleaned.append(normalized)
    return _dedupe_strings(cleaned, 12)


def _source_matches_company_anchor(source: SearchHit | SourceDocument, company_anchor_terms: list[str]) -> bool:
    if not company_anchor_terms:
        return True
    haystack = normalize_text(
        " ".join(
            [
                str(getattr(source, "title", "") or ""),
                str(getattr(source, "snippet", "") or ""),
                str(getattr(source, "excerpt", "") or ""),
                str(getattr(source, "search_query", "") or ""),
                str(getattr(source, "source_label", "") or ""),
                str(getattr(source, "url", "") or ""),
                str(getattr(source, "domain", "") or ""),
            ]
        )
    ).lower()
    return any(normalize_text(term).lower() in haystack for term in company_anchor_terms if normalize_text(term))


def _score_hit(hit: SearchHit, *, keyword: str, research_focus: str | None) -> tuple[int, SearchHit]:
    haystack = normalize_text(
        " ".join(
            [
                hit.title,
                hit.snippet,
                hit.search_query,
                hit.source_label or "",
                hit.url,
                extract_domain(hit.url) or "",
            ]
        )
    ).lower()
    domain = (extract_domain(hit.url) or "").lower()
    keyword_tokens = [token for token in _tokenize_for_match(keyword) if token not in GENERIC_FOCUS_TOKENS]
    focus_tokens = [token for token in _tokenize_for_match(research_focus or "") if token not in GENERIC_FOCUS_TOKENS]
    topic_anchor_terms = [
        term.lower()
        for term in _extract_topic_anchor_terms(keyword, research_focus)
        if term and term.lower() not in {token.lower() for token in GENERIC_FOCUS_TOKENS}
    ]
    company_anchor_terms = [
        term.lower()
        for term in _resolved_company_anchor_terms(keyword, research_focus)
        if normalize_text(term)
    ]
    scope_seed = normalize_text(f"{keyword} {research_focus or ''}")
    region_tokens = [region for region in REGION_TOKENS if region in scope_seed]
    industry_tokens = [
        label
        for label, aliases in INDUSTRY_SCOPE_ALIASES.items()
        if any(alias in scope_seed for alias in aliases)
    ]
    sensitive_tokens = _tokenize_for_match("政策 领导 发言 中标 商机 预算 战略 规划 项目 二期 三期 四期 未来五年 刚需 招标 采购 生态伙伴 甲方 同行 厂商 集成商 竞争 区域")

    score = 0
    if "mp.weixin.qq.com" in domain:
        score += 10
    if domain in PROCUREMENT_DOMAINS or "ccgp.gov.cn" in domain or "ggzy.gov.cn" in domain:
        score += 16
    if domain in POLICY_DOMAINS or ".gov." in domain or domain.endswith(".gov.cn"):
        score += 12
    if domain in EXCHANGE_DOMAINS:
        score += 10
    if "annual report" in haystack or "年报" in haystack or "公告" in haystack:
        score += 4
    if "招标" in haystack or "中标" in haystack or "采购" in haystack:
        score += 5
    keyword_match_count = sum(1 for token in keyword_tokens if token.lower() in haystack)
    focus_match_count = sum(1 for token in focus_tokens if token.lower() in haystack)
    anchor_match_count = sum(1 for token in topic_anchor_terms if token in haystack)
    company_match_count = sum(1 for token in company_anchor_terms if token in haystack or token in domain)
    region_match = any(region.lower() in haystack for region in region_tokens)
    industry_match = any(industry.lower() in haystack for industry in industry_tokens)
    if keyword_match_count:
        score += 6 + min(keyword_match_count, 3) * 3
    if focus_match_count:
        score += 4 + min(focus_match_count, 3) * 2
    if anchor_match_count:
        score += 8 + min(anchor_match_count, 3) * 3
    if company_match_count:
        score += 14 + min(company_match_count, 2) * 5
    if region_match:
        score += 6
    if industry_match:
        score += 6
    if company_anchor_terms and company_match_count == 0:
        return 0, hit
    if topic_anchor_terms and anchor_match_count == 0 and not region_match and not industry_match:
        return 0, hit
    if keyword_match_count + focus_match_count == 0 and not region_match and not industry_match:
        return 0, hit
    if any(token.lower() in haystack for token in sensitive_tokens):
        score += 5
    if hit.snippet:
        score += 2
    return score, hit


def _semantic_score_hit(
    hit: SearchHit,
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object] | None = None,
) -> tuple[int, SearchHit]:
    scope = scope_hints or {}
    haystack = normalize_text(
        " ".join(
            [
                hit.title,
                hit.snippet,
                hit.search_query,
                hit.source_label or "",
                hit.url,
                extract_domain(hit.url) or "",
            ]
        )
    ).lower()
    title_haystack = normalize_text(hit.title).lower()
    domain = (extract_domain(hit.url) or "").lower()
    topic_anchor_terms = [normalize_text(item).lower() for item in _extract_topic_anchor_terms(keyword, research_focus) if normalize_text(item)]
    company_anchor_terms = [
        normalize_text(item).lower()
        for item in _resolved_company_anchor_terms(keyword, research_focus, scope)
        if normalize_text(item)
    ]
    theme_terms = [normalize_text(item).lower() for item in _build_theme_terms(keyword, research_focus, scope) if normalize_text(item)]
    scope_regions = [
        normalize_text(item).lower()
        for item in _expand_region_scope_terms(
            [normalize_text(str(item)) for item in scope.get("regions", []) or [] if normalize_text(str(item))]
        )
    ]
    scope_industries = [
        normalize_text(item).lower()
        for item in [
            *[normalize_text(str(item)) for item in scope.get("industries", []) or [] if normalize_text(str(item))],
            *[
                normalize_text(alias)
                for industry in scope.get("industries", []) or []
                for alias in INDUSTRY_SCOPE_ALIASES.get(normalize_text(str(industry)), ())
                if normalize_text(alias)
            ],
        ]
    ]
    scope_clients = [normalize_text(str(item)).lower() for item in scope.get("clients", []) or [] if normalize_text(str(item))]
    source_type = hit.source_hint or _classify_source_type(hit.url)
    source_label = _derive_source_label(source_type=source_type, domain=domain, fallback=hit.source_label)
    source_tier = _classify_source_tier(source_type=source_type, domain=domain, source_label=source_label)

    theme_match_count = sum(1 for term in theme_terms if term in haystack)
    topic_match_count = sum(1 for term in topic_anchor_terms if term in haystack)
    company_match_count = sum(1 for term in company_anchor_terms if term in haystack or term in domain)
    region_match_count = sum(1 for term in scope_regions if term in haystack)
    industry_match_count = sum(1 for term in scope_industries if term in haystack)
    client_match_count = sum(1 for term in scope_clients if term in haystack)

    score = 0
    if theme_match_count:
        score += 12 + min(theme_match_count, 4) * 4
    if topic_match_count:
        score += 10 + min(topic_match_count, 3) * 4
    if company_match_count:
        score += 16 + min(company_match_count, 2) * 6
    if region_match_count:
        score += 6 + min(region_match_count, 2) * 2
    if industry_match_count:
        score += 6 + min(industry_match_count, 2) * 2
    if client_match_count:
        score += 10 + min(client_match_count, 2) * 4
    if any(term in title_haystack for term in topic_anchor_terms[:4]):
        score += 6
    if any(term in title_haystack for term in company_anchor_terms[:4]):
        score += 8
    if source_tier == "official":
        score += 8
    elif source_tier == "aggregate":
        score += 4
    if source_type == "wechat":
        score += 3
    if bool(scope.get("prefer_company_entities")) and company_anchor_terms and company_match_count == 0:
        return 0, hit
    if topic_anchor_terms and topic_match_count == 0 and theme_match_count == 0 and company_match_count == 0:
        return 0, hit
    return score, hit


def _rrf_score(rank: int, *, k: int = 60) -> float:
    return 1.0 / float(k + max(rank, 1))


def _hybrid_rank_hits(
    hits: Iterable[SearchHit],
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object] | None = None,
) -> list[SearchHit]:
    deduped_hits = _dedupe_hits(hits)
    if not deduped_hits:
        return []

    lexical_scores: dict[str, int] = {}
    semantic_scores: dict[str, int] = {}
    scope_scores: dict[str, int] = {}
    hits_by_url: dict[str, SearchHit] = {}
    theme_terms = _build_theme_terms(keyword, research_focus, scope_hints or {})
    company_anchor_terms = _resolved_company_anchor_terms(keyword, research_focus, scope_hints)

    for hit in deduped_hits:
        normalized_url = normalize_text(hit.url)
        if not normalized_url:
            continue
        hits_by_url[normalized_url] = hit
        lexical_scores[normalized_url] = _score_hit(hit, keyword=keyword, research_focus=research_focus)[0]
        semantic_scores[normalized_url] = _semantic_score_hit(
            hit,
            keyword=keyword,
            research_focus=research_focus,
            scope_hints=scope_hints,
        )[0]
        scope_scores[normalized_url] = _source_scope_match_score(
            hit,
            scope_hints=scope_hints or {},
            company_anchor_terms=company_anchor_terms,
            theme_terms=theme_terms,
        )

    lexical_ranked = [url for url, _ in sorted(lexical_scores.items(), key=lambda item: item[1], reverse=True) if _ > 0]
    semantic_ranked = [url for url, _ in sorted(semantic_scores.items(), key=lambda item: item[1], reverse=True) if _ > 0]
    scope_ranked = [url for url, _ in sorted(scope_scores.items(), key=lambda item: item[1], reverse=True) if _ > 0]

    hybrid_scores: dict[str, float] = {}
    for ranked_urls, score_map in (
        (lexical_ranked, lexical_scores),
        (semantic_ranked, semantic_scores),
        (scope_ranked, scope_scores),
    ):
        for index, url in enumerate(ranked_urls, start=1):
            hybrid_scores[url] = hybrid_scores.get(url, 0.0) + _rrf_score(index) + float(score_map.get(url, 0)) / 1000.0

    ordered_urls = sorted(
        hybrid_scores,
        key=lambda url: (
            hybrid_scores.get(url, 0.0),
            lexical_scores.get(url, 0),
            semantic_scores.get(url, 0),
            scope_scores.get(url, 0),
        ),
        reverse=True,
    )
    return [hits_by_url[url] for url in ordered_urls if hybrid_scores.get(url, 0.0) > 0]


def _source_rerank_score(
    source: SourceDocument,
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object] | None = None,
) -> int:
    theme_terms = _build_theme_terms(keyword, research_focus, scope_hints or {})
    company_anchor_terms = _resolved_company_anchor_terms(keyword, research_focus, scope_hints)
    base = _source_scope_match_score(
        source,
        scope_hints=scope_hints or {},
        company_anchor_terms=company_anchor_terms,
        theme_terms=theme_terms,
    )
    text = normalize_text(
        " ".join(
            [
                source.title,
                source.snippet,
                source.excerpt,
                source.search_query,
                source.source_label or "",
                source.url,
                source.domain or "",
            ]
        )
    ).lower()
    score = base
    if source.source_tier == "official":
        score += 18
    elif source.source_tier == "aggregate":
        score += 8
    if source.content_status == "browser_extracted":
        score += 10
    elif source.content_status == "extracted":
        score += 7
    elif source.content_status == "reader_proxy":
        score += 5
    elif source.content_status in {"snippet_only", "fetch_failed"}:
        score -= 6
    if len(normalize_text(source.excerpt)) >= 260:
        score += 4
    if len(normalize_text(source.excerpt)) < 120:
        score -= 4
    if company_anchor_terms and not _source_matches_company_anchor(source, company_anchor_terms):
        score -= 14 if bool((scope_hints or {}).get("prefer_company_entities")) else 6
    if any(term in text for term in ("官网", "联系我们", "投资者关系", "合作", "采购", "招标", "中标")):
        score += 4
    if any(term in text for term in ("访问受限", "待补全", "captcha", "验证后即可继续访问")):
        score -= 10
    return score


def _rerank_sources_hybrid(
    sources: Iterable[SourceDocument],
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object] | None = None,
) -> list[SourceDocument]:
    deduped_sources = _dedupe_sources(sources)
    if not deduped_sources:
        return []
    ranked = sorted(
        deduped_sources,
        key=lambda source: (
            _source_rerank_score(
                source,
                keyword=keyword,
                research_focus=research_focus,
                scope_hints=scope_hints,
            ),
            1 if source.source_tier == "official" else 0,
            len(normalize_text(source.excerpt)),
        ),
        reverse=True,
    )
    filtered = [
        source
        for source in ranked
        if _source_rerank_score(
            source,
            keyword=keyword,
            research_focus=research_focus,
            scope_hints=scope_hints,
        )
        > 0
    ]
    return filtered or ranked


def _refine_sources_for_report(
    sources: Iterable[SourceDocument],
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
    company_anchor_terms: list[str],
    theme_terms: list[str],
) -> list[SourceDocument]:
    deduped_sources = _dedupe_sources(sources)
    if not deduped_sources:
        return []
    filtered_sources = _filter_sources_by_theme_relevance(
        deduped_sources,
        theme_terms=theme_terms,
        scope_hints=scope_hints,
        company_anchor_terms=company_anchor_terms,
    )
    return _rerank_sources_hybrid(
        filtered_sources or deduped_sources,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
    )


def _source_scope_match_score(
    source: SourceDocument | SearchHit,
    *,
    scope_hints: dict[str, object],
    company_anchor_terms: list[str],
    theme_terms: list[str],
) -> int:
    text = normalize_text(
        " ".join(
                [
                    source.title,
                    source.snippet,
                    str(getattr(source, "excerpt", "") or ""),
                    source.search_query,
                    str(getattr(source, "source_label", "") or ""),
                    str(getattr(source, "domain", "") or ""),
                    source.url,
                ]
            )
        ).lower()
    score = 0
    regions = [
        item.lower()
        for item in _expand_region_scope_terms(
            [normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
        )
    ]
    industries = [normalize_text(str(item)).lower() for item in scope_hints.get("industries", []) if normalize_text(str(item))]
    industry_aliases = [
        normalize_text(alias).lower()
        for industry in scope_hints.get("industries", []) or []
        for alias in INDUSTRY_SCOPE_ALIASES.get(normalize_text(str(industry)), ())
        if normalize_text(alias)
    ]
    clients = [normalize_text(str(item)).lower() for item in scope_hints.get("clients", []) if normalize_text(str(item))]
    company_terms = [normalize_text(item).lower() for item in company_anchor_terms if normalize_text(item)]
    if bool(scope_hints.get("prefer_company_entities")) and company_terms and not any(term in text for term in company_terms):
        return 0
    source_tier = normalize_text(str(getattr(source, "source_tier", "") or "")).lower()
    if not source_tier:
        source_type = str(getattr(source, "source_type", "") or getattr(source, "source_hint", "") or _classify_source_type(source.url))
        domain = str(getattr(source, "domain", "") or extract_domain(source.url) or "")
        source_label = str(getattr(source, "source_label", "") or "")
        source_tier = _classify_source_tier(source_type=source_type, domain=domain, source_label=source_label)
    if any(term in text for term in theme_terms):
        score += 4
    if any(region in text for region in regions):
        score += 4
    if any(industry in text for industry in [*industries, *industry_aliases]):
        score += 4
    if any(client in text for client in clients):
        score += 6
    if any(term in text for term in company_terms):
        score += 8
    if source_tier == "official" and score > 0:
        score += 2
    return score


def _dedupe_hits(hits: Iterable[SearchHit]) -> list[SearchHit]:
    deduped: list[SearchHit] = []
    seen_urls: set[str] = set()
    for hit in hits:
        normalized_url = normalize_text(hit.url)
        if not normalized_url or normalized_url in seen_urls:
            continue
        seen_urls.add(normalized_url)
        deduped.append(hit)
    return deduped


def _build_company_seed_hits(company_names: list[str], *, keyword: str) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for company in _dedupe_strings(company_names, 4):
        normalized = normalize_text(company)
        if not normalized:
            continue
        for url, label in KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS.get(normalized, ()):
            hits.append(
                SearchHit(
                    title=f"{normalized} {label}",
                    url=url,
                    snippet=f"{normalized} 官方公开入口，优先用于补充官网、IR、公开业务联系渠道。",
                    search_query=f"{keyword} {normalized} 官方公开入口",
                    source_hint="web",
                    source_label=label,
                )
            )
    return hits


def _collect_theme_seed_companies(
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
) -> list[str]:
    seed_names: list[str] = []
    industries = [normalize_text(str(item)) for item in scope_hints.get("industries", []) or [] if normalize_text(str(item))]
    topic_terms = _extract_topic_anchor_terms(keyword, research_focus)
    for industry in industries:
        seed_names.extend(THEME_COMPANY_PUBLIC_SOURCE_SEEDS.get(industry, ()))
    lowered_terms = " ".join(topic_terms).lower()
    if any(token in lowered_terms for token in ("ai漫剧", "漫剧", "ai短剧", "aigc动画", "动漫短剧")):
        seed_names.extend(THEME_COMPANY_PUBLIC_SOURCE_SEEDS.get("AI漫剧", ()))
    if any(token in lowered_terms for token in ("政务云", "数字政府", "政务")):
        seed_names.extend(THEME_COMPANY_PUBLIC_SOURCE_SEEDS.get("政务云", ()))
    seed_names.extend(
        normalize_text(str(item))
        for item in scope_hints.get("company_anchors", []) or []
        if normalize_text(str(item))
    )
    seed_names.extend(
        normalize_text(str(item))
        for item in scope_hints.get("clients", []) or []
        if normalize_text(str(item))
    )
    return _dedupe_strings(seed_names, 12)


def _build_corrective_query_plan(
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
    include_wechat: bool,
    preferred_wechat_accounts: Iterable[str] | None = None,
    limit: int = 8,
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
        _build_scoped_official_query_expansions(
            keyword,
            research_focus,
            scope_hints=scope_hints,
            include_wechat=include_wechat,
            limit=max(6, limit),
        )
    )
    seed_companies = _collect_theme_seed_companies(keyword=keyword, research_focus=research_focus, scope_hints=scope_hints)
    for industry in industries:
        for template in THEME_OFFICIAL_QUERY_TEMPLATES.get(industry, ()):
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
        for account in _dedupe_strings(preferred_wechat_accounts or [], 2):
            queries.append(f'site:mp.weixin.qq.com "{account}" {keyword}')
            if research_focus:
                queries.append(f'site:mp.weixin.qq.com "{account}" {keyword} {normalize_text(research_focus)}')
    exclusion_terms = [normalize_text(str(item)) for item in scope_hints.get('strategy_exclusion_terms', []) or [] if normalize_text(str(item))]
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


def _dedupe_sources(sources: Iterable[SourceDocument]) -> list[SourceDocument]:
    deduped: list[SourceDocument] = []
    seen_urls: set[str] = set()
    for source in sources:
        normalized_url = normalize_text(source.url)
        if normalized_url and normalized_url in seen_urls:
            continue
        if normalized_url:
            seen_urls.add(normalized_url)
        deduped.append(source)
    return deduped


def _select_hits_with_source_balance(hits: list[SearchHit], *, limit: int) -> list[SearchHit]:
    selected: list[SearchHit] = []
    seen_urls: set[str] = set()
    official_quota = max(2, round(limit * 0.45))
    aggregate_quota = max(1, round(limit * 0.25))

    def classify_hit_tier(hit: SearchHit) -> str:
        source_type = hit.source_hint or _classify_source_type(hit.url)
        domain = extract_domain(hit.url)
        source_label = _derive_source_label(
            source_type=source_type,
            domain=domain,
            fallback=getattr(hit, "source_label", None),
        )
        return _classify_source_tier(source_type=source_type, domain=domain, source_label=source_label)

    def take_hits(match: Callable[[SearchHit], bool], quota: int) -> None:
        if quota <= 0:
            return
        taken = 0
        for hit in hits:
            if taken >= quota:
                break
            normalized_url = normalize_text(hit.url)
            if not normalized_url or normalized_url in seen_urls or not match(hit):
                continue
            seen_urls.add(normalized_url)
            selected.append(hit)
            taken += 1

    take_hits(lambda hit: classify_hit_tier(hit) == "official", official_quota)
    take_hits(lambda hit: classify_hit_tier(hit) == "aggregate", aggregate_quota)
    take_hits(lambda hit: hit.source_hint == "tech_media_feed", 1)
    take_hits(lambda hit: True, limit - len(selected))
    return selected[:limit]


def _classify_source_type(url: str) -> str:
    domain = (extract_domain(url) or "").lower()
    if "jianyu360.com" in domain or "jianyu360.cn" in domain:
        return "tender_feed"
    if "yuntoutiao.com" in domain:
        return "tech_media_feed"
    if "mp.weixin.qq.com" in domain:
        return "wechat"
    if domain in PROCUREMENT_DOMAINS or "ccgp.gov.cn" in domain or "ggzy.gov.cn" in domain:
        return "procurement"
    if domain in EXCHANGE_DOMAINS:
        return "filing"
    if ".gov." in domain or domain.endswith(".gov.cn"):
        return "policy"
    return "web"


def _classify_source_tier(*, source_type: str, domain: str | None, source_label: str | None) -> str:
    normalized_domain = (domain or "").lower()
    normalized_label = normalize_text(source_label or "").lower()
    if source_type in {"policy", "procurement", "filing", "official_tender_feed", "official_tender_news", "official_policy_speech", "regional_public_resource"}:
        return "official"
    if any(token in normalized_label for token in ("官网", "投资者关系", "联系我们", "官方")):
        return "official"
    if any(token in normalized_label for token in ("公共资源", "招标投标网", "政府采购", "中国政府网")):
        return "official"
    if any(token in normalized_domain for token in ("gov.cn", "ggzy.gov.cn", "cninfo.com.cn", "sec.gov", "hkexnews.hk")):
        return "official"
    if source_type in {"tender_feed", "compliant_procurement_aggregate"}:
        return "aggregate"
    if any(token in normalized_label for token in ("剑鱼标讯", "云头条", "合规聚合")):
        return "aggregate" if "云头条" not in normalized_label else "media"
    if any(token in normalized_domain for token in ("jianyu", "cecbid", "cebpubservice", "china-cpp", "chinabidding")):
        return "aggregate"
    return "media"


def _derive_source_label(*, source_type: str, domain: str | None, fallback: str | None) -> str | None:
    if fallback:
        return fallback
    normalized_domain = (domain or "").lower()
    if "ggzy.gov.cn" in normalized_domain:
        return "全国公共资源交易平台"
    if "gov.cn" in normalized_domain:
        return "中国政府网政策/讲话"
    if "cninfo.com.cn" in normalized_domain:
        return "巨潮资讯公告"
    if "hkexnews.hk" in normalized_domain:
        return "港交所公告"
    if "sec.gov" in normalized_domain:
        return "SEC 公告"
    if "mp.weixin.qq.com" in normalized_domain:
        return "微信公众号"
    if "cecbid" in normalized_domain or "cebpubservice" in normalized_domain or "china-cpp" in normalized_domain:
        return "政府采购合规聚合"
    if "jianyu" in normalized_domain:
        return "剑鱼标讯"
    if "yuntoutiao" in normalized_domain:
        return "云头条"
    if source_type == "web":
        return "互联网公开网页"
    return None


def _extract_source_document(hit: SearchHit, *, timeout_seconds: int, excerpt_chars: int) -> SourceDocument:
    title = normalize_text(hit.title) or hit.url
    domain = extract_domain(hit.url)
    source_type = hit.source_hint or _classify_source_type(hit.url)
    source_origin = "adapter" if bool(getattr(hit, "source_label", None)) else "search"
    source_label = _derive_source_label(source_type=source_type, domain=domain, fallback=getattr(hit, "source_label", None))
    source_tier = _classify_source_tier(source_type=source_type, domain=domain, source_label=source_label)
    snippet = _truncate_text(
        _clean_source_text_for_analysis(hit.snippet or "") or _clean_source_text_for_analysis(title),
        180,
    )

    extracted_title = title
    excerpt = snippet
    content_status = "snippet_only"

    if source_type != "tender_feed":
        if source_type == "wechat" or (domain or "").endswith("mp.weixin.qq.com"):
            try:
                extracted = extract_from_browser(hit.url, timeout_seconds=max(timeout_seconds, 12))
                extracted_title = normalize_text(extracted.title or title) or title
                excerpt = _truncate_text(
                    _clean_source_text_for_analysis(extracted.clean_content or extracted.raw_content or snippet),
                    excerpt_chars,
                )
                content_status = "browser_extracted"
            except ContentExtractionError:
                pass
        if content_status == "snippet_only":
            try:
                extracted = extract_from_url(hit.url, timeout_seconds=timeout_seconds)
                extracted_title = normalize_text(extracted.title or title) or title
                excerpt = _truncate_text(
                    _clean_source_text_for_analysis(extracted.clean_content or extracted.raw_content or snippet),
                    excerpt_chars,
                )
                content_status = "extracted"
            except ContentExtractionError:
                try:
                    extracted = extract_from_reader_proxy(hit.url, timeout_seconds=max(timeout_seconds + 2, 10))
                    extracted_title = normalize_text(extracted.title or title) or title
                    excerpt = _truncate_text(
                        _clean_source_text_for_analysis(extracted.clean_content or extracted.raw_content or snippet),
                        excerpt_chars,
                    )
                    content_status = "reader_proxy"
                except ContentExtractionError:
                    pass

    return SourceDocument(
        title=extracted_title,
        url=hit.url,
        domain=domain,
        snippet=snippet,
        search_query=hit.search_query,
        source_type=source_type,
        content_status=content_status,
        excerpt=excerpt,
        source_label=source_label,
        source_tier=source_tier,
        source_origin=source_origin,
    )


def _extract_source_document_best_effort(
    hit: SearchHit,
    *,
    timeout_seconds: int,
    excerpt_chars: int,
) -> SourceDocument | None:
    try:
        return _extract_source_document(
            hit,
            timeout_seconds=timeout_seconds,
            excerpt_chars=excerpt_chars,
        )
    except Exception:
        domain = extract_domain(hit.url)
        source_type = hit.source_hint or _classify_source_type(hit.url)
        source_label = _derive_source_label(
            source_type=source_type,
            domain=domain,
            fallback=getattr(hit, "source_label", None),
        )
        source_tier = _classify_source_tier(
            source_type=source_type,
            domain=domain,
            source_label=source_label,
        )
        if not normalize_text(hit.url):
            return None
        return SourceDocument(
            title=normalize_text(hit.title) or hit.url,
            url=hit.url,
            domain=domain,
            snippet=_truncate_text(
                _clean_source_text_for_analysis(hit.snippet or "") or _clean_source_text_for_analysis(hit.title or hit.url),
                180,
            ),
            search_query=hit.search_query,
            source_type=source_type,
            content_status="fetch_failed",
            excerpt=_truncate_text(
                _clean_source_text_for_analysis(hit.snippet or "") or _clean_source_text_for_analysis(hit.title or hit.url),
                excerpt_chars,
            ),
            source_label=source_label,
            source_tier=source_tier,
            source_origin="adapter" if bool(getattr(hit, "source_label", None)) else "search",
        )


def _parse_source_datetime(
    *,
    year: str,
    month: str | None = None,
    day: str | None = None,
) -> datetime | None:
    try:
        resolved_year = int(year)
        resolved_month = max(1, min(12, int(month or "1")))
        resolved_day = max(1, min(28 if resolved_month == 2 else 31, int(day or "1")))
        if resolved_year < 1900:
            return None
        return datetime(resolved_year, resolved_month, resolved_day, tzinfo=timezone.utc)
    except ValueError:
        return None


def _extract_source_dates(value: str) -> list[datetime]:
    text = normalize_text(value)
    if not text:
        return []
    dates: list[datetime] = []
    for match in SOURCE_DATE_PATTERN.finditer(text):
        parsed = _parse_source_datetime(
            year=str(match.group("year") or ""),
            month=match.group("month"),
            day=match.group("day"),
        )
        if parsed:
            dates.append(parsed)
    return dates


def _infer_source_published_at(source: SourceDocument) -> datetime | None:
    date_candidates: list[datetime] = []
    for candidate in (
        source.title,
        source.snippet,
        source.excerpt,
        source.url,
        source.search_query,
    ):
        date_candidates.extend(_extract_source_dates(candidate))
    if not date_candidates:
        return None
    return max(date_candidates)


def _filter_recent_sources(
    sources: list[SourceDocument],
    *,
    max_age_years: int = SOURCE_MAX_AGE_YEARS,
) -> list[SourceDocument]:
    now = datetime.now(timezone.utc)
    cutoff = datetime(max(now.year - max_age_years, 1900), now.month, now.day, tzinfo=timezone.utc)
    filtered: list[SourceDocument] = []
    for source in sources:
        published_at = _infer_source_published_at(source)
        if published_at and published_at < cutoff:
            continue
        filtered.append(source)
    return filtered


def _source_text(source: SourceDocument) -> str:
    return _source_text_cached(source.title, source.snippet, source.excerpt)


@lru_cache(maxsize=4096)
def _source_text_cached(title: str, snippet: str, excerpt: str) -> str:
    return normalize_text(
        " ".join(
            [
                _clean_source_text_for_analysis(title),
                _clean_source_text_for_analysis(snippet),
                _clean_source_text_for_analysis(excerpt),
            ]
        )
    )


def _source_theme_match_score(
    source: SourceDocument,
    *,
    theme_terms: list[str],
    scope_hints: dict[str, object],
) -> int:
    if not theme_terms:
        return 0
    text = _source_text(source)
    lowered = text.lower()
    title_lower = normalize_text(source.title).lower()
    label_lower = normalize_text(source.source_label or "").lower()
    regions = [
        item.lower()
        for item in _expand_region_scope_terms(
            [normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
        )
    ]
    clients = [normalize_text(str(item)).lower() for item in scope_hints.get("clients", []) if normalize_text(str(item))]
    exclusion_terms = [
        normalize_text(str(item)).lower()
        for item in scope_hints.get("strategy_exclusion_terms", [])
        if normalize_text(str(item))
    ]
    score = 0
    title_hits = sum(1 for term in theme_terms if term in title_lower)
    body_hits = sum(1 for term in theme_terms if term in lowered)
    label_hits = sum(1 for term in theme_terms if term in label_lower)
    if title_hits:
        score += min(title_hits, 3) * 6
    if body_hits:
        score += min(body_hits, 4) * 4
    if label_hits:
        score += min(label_hits, 2) * 3
    if regions and any(region in lowered for region in regions):
        score += 3
    if clients and any(client in lowered or client in title_lower for client in clients):
        score += 5
    if exclusion_terms and any(term in lowered or term in title_lower for term in exclusion_terms):
        score -= 18
    return score


def _filter_sources_by_theme_relevance(
    sources: list[SourceDocument],
    *,
    theme_terms: list[str],
    scope_hints: dict[str, object],
    company_anchor_terms: list[str] | None = None,
) -> list[SourceDocument]:
    if not sources or not theme_terms:
        return sources
    sources = [source for source in sources if not _source_has_region_conflict(source, scope_hints=scope_hints)]
    if not sources:
        return []
    prefer_company_entities = bool(scope_hints.get("prefer_company_entities"))
    theme_labels = [
        normalize_text(str(item))
        for item in scope_hints.get("industries", []) or []
        if normalize_text(str(item))
    ]
    seed_companies = [
        normalize_text(str(item))
        for item in scope_hints.get("seed_companies", []) or []
        if normalize_text(str(item))
    ]
    if prefer_company_entities:
        company_scoped_sources = [
            source
            for source in sources
            if _source_supports_company_intent(
                source,
                theme_labels=theme_labels,
                seed_companies=seed_companies,
            )
        ]
        if company_scoped_sources:
            sources = company_scoped_sources
    strict_theme_terms = _build_strict_theme_terms(scope_hints)
    if strict_theme_terms:
        strict_sources = [
            source
            for source in sources
            if any(term in _source_text(source).lower() or term in normalize_text(source.title).lower() for term in strict_theme_terms)
        ]
        if strict_sources:
            sources = strict_sources
    company_terms = [normalize_text(item) for item in company_anchor_terms or [] if normalize_text(item)]
    scored_sources = [
        (
            source,
            _source_theme_match_score(source, theme_terms=theme_terms, scope_hints=scope_hints),
            _source_scope_match_score(
                source,
                scope_hints=scope_hints,
                company_anchor_terms=company_terms,
                theme_terms=theme_terms,
            ),
        )
        for source in sources
    ]
    matched = [source for source, theme_score, _ in scored_sources if theme_score >= 8]
    if company_terms:
        matched = [source for source in matched if _source_matches_company_anchor(source, company_terms)]
        if matched:
            return matched
        title_matched = [
            source
            for source, theme_score, scope_score in scored_sources
            if theme_score >= 12 and scope_score >= 8 and _source_matches_company_anchor(source, company_terms)
        ]
        if title_matched:
            return title_matched
        return []
    scoped_matched = [source for source, theme_score, scope_score in scored_sources if theme_score >= 6 and scope_score >= 4]
    if scoped_matched:
        minimum = min(4, len(sources))
        if len(scoped_matched) >= max(2, minimum):
            return scoped_matched
        title_scoped = [source for source, theme_score, scope_score in scored_sources if theme_score >= 10 and scope_score >= 3]
        if len(title_scoped) >= 2:
            return title_scoped
        return scoped_matched
    if len(matched) >= min(4, len(sources)):
        return matched
    title_matched = [source for source, theme_score, _ in scored_sources if theme_score >= 12]
    if len(title_matched) >= 2:
        return title_matched
    return sources


def _dedupe_strings(values: Iterable[str], limit: int) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
        if len(deduped) >= limit:
            break
    return deduped


def _prune_industry_hints(values: Iterable[str]) -> list[str]:
    hints = _dedupe_strings((normalize_text(value) for value in values), 4)
    if not hints:
        return []
    pruned = list(hints)
    for dominant, suppressed in THEME_GENERIC_SUPPRESSIONS.items():
        if dominant in pruned:
            pruned = [item for item in pruned if item == dominant or item not in suppressed]
    generic_hints = {"大模型", "人工智能", "信息化"}
    if any(item not in generic_hints for item in pruned):
        pruned = [item for item in pruned if item not in generic_hints] + [item for item in pruned if item in generic_hints]
    return _dedupe_strings(pruned, 4)


@lru_cache(maxsize=8192)
def _strip_org_public_suffixes(value: str) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    stripped = normalized
    suffixes = (
        "集团官网",
        "官网入口",
        "官网主页",
        "官网首页",
        "官方网站",
        "官网",
        "投资者关系",
        "投资者关系主页",
        "联系我们",
        "公开入口",
        "品牌官网",
    )
    changed = True
    while changed:
        changed = False
        for suffix in suffixes:
            if stripped.endswith(suffix) and len(stripped) > len(suffix) + 1:
                stripped = normalize_text(stripped[: -len(suffix)])
                changed = True
                break
    return stripped


@lru_cache(maxsize=1)
def _normalized_entity_suffixes() -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                normalize_text(suffix)
                for suffix in ENTITY_SUFFIX_TOKENS
                if normalize_text(suffix)
            },
            key=len,
            reverse=True,
        )
    )


@lru_cache(maxsize=1)
def _normalized_entity_suffixes_lower() -> tuple[str, ...]:
    return tuple(suffix.lower() for suffix in _normalized_entity_suffixes())


def _entity_alias_lookup_key(name: str) -> str:
    return _entity_alias_lookup_key_cached(normalize_text(_strip_org_public_suffixes(name)))


@lru_cache(maxsize=16384)
def _entity_alias_lookup_key_cached(normalized_name: str) -> str:
    lowered = normalized_name.lower()
    stripped = lowered
    changed = True
    while changed:
        changed = False
        for suffix_normalized in _normalized_entity_suffixes_lower():
            if stripped.endswith(suffix_normalized) and len(stripped) > len(suffix_normalized) + 1:
                stripped = stripped[: -len(suffix_normalized)]
                changed = True
                break
    stripped = re.sub(r"[^a-z0-9\u4e00-\u9fa5]+", "", stripped)
    return stripped or lowered


def _org_surface_variants(value: str) -> list[str]:
    normalized = normalize_text(_strip_org_public_suffixes(value))
    if not normalized:
        return []
    return list(_org_surface_variants_cached(normalized))


@lru_cache(maxsize=8192)
def _org_surface_variants_cached(normalized_value: str) -> tuple[str, ...]:
    variants = [normalized_value]
    cleaned = _strip_entity_leading_noise(normalized_value)
    if cleaned and cleaned not in variants:
        variants.append(cleaned)
    bracketless = normalize_text(re.sub(r"[（(][^（）()]{1,24}[）)]", "", normalized_value))
    if bracketless and bracketless not in variants:
        variants.append(bracketless)
    stripped = normalized_value
    changed = True
    while changed:
        changed = False
        for suffix in _normalized_entity_suffixes():
            if stripped.endswith(suffix) and len(stripped) > len(suffix) + 1:
                stripped = normalize_text(stripped[: -len(suffix)])
                changed = True
                break
    if (
        stripped
        and stripped != normalized_value
        and len(stripped) >= 2
        and stripped not in variants
        and not _looks_like_scope_prompt_noise(stripped)
        and not _contains_low_value_entity_token(stripped)
    ):
        variants.append(stripped)
    return tuple(_dedupe_strings(variants, 6))


def _scope_org_names_key(scope_hints: dict[str, object] | None) -> tuple[str, ...]:
    if not scope_hints:
        return ()
    bucket_values: list[tuple[str, ...]] = []
    for bucket in ("company_anchors", "clients", "seed_companies"):
        normalized_items: list[str] = []
        for item in scope_hints.get(bucket, []) or []:
            normalized = normalize_text(str(item))
            if normalized:
                normalized_items.append(normalized)
        bucket_values.append(tuple(normalized_items))
    return _scope_org_names_key_cached(*bucket_values)


@lru_cache(maxsize=512)
def _scope_org_names_key_cached(
    company_anchors: tuple[str, ...],
    clients: tuple[str, ...],
    seed_companies: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(_dedupe_strings([*company_anchors, *clients, *seed_companies], 24))


def _collect_scope_org_names(scope_hints: dict[str, object] | None) -> list[str]:
    return list(_scope_org_names_key(scope_hints))


def _register_org_alias(
    alias_map: dict[str, str],
    canonical_name: str,
    alias_name: str | None = None,
    *,
    replace: bool = False,
) -> None:
    canonical = normalize_text(canonical_name)
    alias = normalize_text(alias_name or canonical_name)
    if not canonical or not alias:
        return
    key = _entity_alias_lookup_key(alias)
    if not key:
        return
    if replace or key not in alias_map:
        alias_map[key] = canonical


@lru_cache(maxsize=1)
def _base_org_alias_lookup_map() -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for canonical in [*KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS.keys(), *SPECIAL_ENTITY_ALIASES]:
        for alias in _org_surface_variants(canonical):
            _register_org_alias(alias_map, canonical, alias)
    for alias, canonical in _RESEARCH_ACCOUNT_ALIAS_MAP.items():
        _register_org_alias(alias_map, canonical, canonical, replace=True)
        for variant in _org_surface_variants(alias):
            _register_org_alias(alias_map, canonical, variant, replace=True)
    return alias_map


@lru_cache(maxsize=512)
def _org_alias_lookup_map_cached(scope_org_names: tuple[str, ...]) -> dict[str, str]:
    alias_map = dict(_base_org_alias_lookup_map())
    for canonical in scope_org_names:
        for alias in _org_surface_variants(canonical):
            _register_org_alias(alias_map, canonical, alias, replace=True)
    return alias_map


def _org_alias_lookup_map(scope_hints: dict[str, object] | None = None) -> dict[str, str]:
    return _org_alias_lookup_map_cached(_scope_org_names_key(scope_hints))


def _canonical_org_name_from_domain(domain: str | None) -> str:
    normalized = normalize_text(domain or "").lower().removeprefix("www.")
    if not normalized:
        return ""
    for known_domain, canonical_name in _OFFICIAL_DOMAIN_ENTITY_MAP.items():
        if normalized == known_domain or normalized.endswith(f".{known_domain}"):
            return canonical_name
    return ""


def _resolve_known_org_name(
    value: str,
    *,
    scope_hints: dict[str, object] | None = None,
    source: SourceDocument | None = None,
) -> str:
    scope_org_names = _scope_org_names_key(scope_hints)
    normalized = _resolve_known_org_name_cached(value, scope_org_names)
    if not normalized:
        return ""
    if source is not None:
        domain_canonical = _canonical_org_name_from_domain(source.domain or extract_domain(source.url))
        if domain_canonical:
            source_text = _source_text(source)
            if any(alias in source_text for alias in _org_surface_variants(domain_canonical)):
                return domain_canonical
            if _is_lightweight_entity_name(normalized):
                return domain_canonical
    return normalized


@lru_cache(maxsize=16384)
def _resolve_known_org_name_cached(value: str, scope_org_names: tuple[str, ...]) -> str:
    normalized = normalize_text(_strip_org_public_suffixes(value))
    if not normalized:
        return ""
    alias_map = _org_alias_lookup_map_cached(scope_org_names)
    for variant in _org_surface_variants(normalized):
        resolved = alias_map.get(_entity_alias_lookup_key(variant))
        if resolved:
            return resolved
    return normalized


def _org_entity_variants(value: str, *, scope_hints: dict[str, object] | None = None) -> list[str]:
    return list(_org_entity_variants_cached(value, _scope_org_names_key(scope_hints)))


@lru_cache(maxsize=8192)
def _org_entity_variants_cached(value: str, scope_org_names: tuple[str, ...]) -> tuple[str, ...]:
    canonical = _resolve_known_org_name_cached(value, scope_org_names)
    if not canonical:
        return ()
    variants = list(_org_surface_variants(canonical))
    for alias, mapped in _RESEARCH_ACCOUNT_ALIAS_MAP.items():
        if normalize_text(mapped) == canonical:
            variants.extend(_org_surface_variants(alias))
    for candidate in [*KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS.keys(), *SPECIAL_ENTITY_ALIASES, *scope_org_names]:
        if _resolve_known_org_name_cached(candidate, scope_org_names) == canonical:
            variants.extend(_org_surface_variants(candidate))
    return tuple(_dedupe_strings(variants, 10))


def _known_org_alias_candidates_from_text(
    value: str,
    *,
    scope_hints: dict[str, object] | None = None,
) -> list[str]:
    return list(_known_org_alias_candidates_from_text_cached(value, _scope_org_names_key(scope_hints)))


@lru_cache(maxsize=4096)
def _known_org_alias_candidates_from_text_cached(value: str, scope_org_names: tuple[str, ...]) -> tuple[str, ...]:
    text = normalize_text(value)
    if not text:
        return ()
    candidates: list[str] = []
    for canonical in [
        *KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS.keys(),
        *SPECIAL_ENTITY_ALIASES,
        *_RESEARCH_ACCOUNT_ALIAS_MAP.keys(),
        *scope_org_names,
    ]:
        if any(alias in text for alias in _org_surface_variants(canonical)):
            candidates.append(_resolve_known_org_name_cached(canonical, scope_org_names))
    return tuple(_dedupe_strings(candidates, 12))


def _entity_canonical_key(name: str) -> str:
    return _entity_canonical_key_cached(name)


@lru_cache(maxsize=16384)
def _entity_canonical_key_cached(name: str) -> str:
    normalized = normalize_text(_resolve_known_org_name(name))
    return _entity_alias_lookup_key(normalized)


def _infer_entity_graph_type(
    name: str,
    text: str,
    *,
    scope_hints: dict[str, object],
) -> str:
    lowered_name = normalize_text(name).lower()
    lowered_text = normalize_text(text).lower()
    scope_clients = [normalize_text(str(item)).lower() for item in scope_hints.get("clients", []) if normalize_text(str(item))]
    target_markers = ("政府", "局", "委", "办", "中心", "医院", "大学", "银行", "学校", "城投", "交投")
    partner_markers = ("咨询", "顾问", "集成", "渠道", "联盟", "研究院", "研究所", "运营商", "总包")
    competitor_markers = ("科技", "信息", "软件", "智能", "数据", "云", "系统", "平台", "通信")

    if any(client and client in lowered_name for client in scope_clients):
        return "target"
    if any(token in lowered_name for token in target_markers) or any(token in lowered_text for token in ("采购", "预算", "招标", "业主", "甲方")):
        return "target"
    if any(token in lowered_name for token in partner_markers) or any(token in lowered_text for token in ("合作伙伴", "联合体", "咨询", "渠道", "生态伙伴", "集成商")):
        return "partner"
    if any(token in lowered_name for token in competitor_markers) or any(token in lowered_text for token in ("中标", "成交", "竞品", "厂商", "平台", "产品", "解决方案")):
        return "competitor"
    return "generic"


def _pick_entity_graph_type(existing: str, incoming: str) -> str:
    priority = {"target": 4, "competitor": 3, "partner": 2, "generic": 1}
    return incoming if priority.get(incoming, 0) > priority.get(existing, 0) else existing


def _build_entity_graph(
    sources: list[SourceDocument],
    *,
    scope_hints: dict[str, object],
) -> ResearchEntityGraphOut:
    graph_state: dict[str, dict[str, object]] = {}
    for source in sources:
        text = _source_text(source)
        if not text:
            continue
        candidates = _extract_rank_entity_candidates(text, scope_hints=scope_hints)
        domain_canonical = _canonical_org_name_from_domain(source.domain or extract_domain(source.url))
        if domain_canonical:
            candidates.append(_resolve_known_org_name(domain_canonical, scope_hints=scope_hints, source=source))
        for candidate in candidates:
            raw_name = normalize_text(candidate)
            name = _resolve_known_org_name(candidate, scope_hints=scope_hints, source=source)
            if not name or not _is_plausible_entity_name(name):
                continue
            key = _entity_canonical_key(name)
            role = _infer_entity_graph_type(name, text, scope_hints=scope_hints)
            state = graph_state.setdefault(
                key,
                {
                    "canonical_name": name,
                    "entity_type": role,
                    "aliases": set(),
                    "source_urls": set(),
                    "source_tier_counts": Counter(),
                    "evidence_links": [],
                },
            )
            state["entity_type"] = _pick_entity_graph_type(str(state["entity_type"]), role)
            aliases = state["aliases"]
            if isinstance(aliases, set):
                aliases.update(_org_entity_variants(name, scope_hints=scope_hints))
                if raw_name:
                    aliases.update(_org_surface_variants(raw_name))
            canonical_name = normalize_text(str(state["canonical_name"]))
            if len(name) > len(canonical_name):
                state["canonical_name"] = name
            source_urls = state["source_urls"]
            if isinstance(source_urls, set):
                source_urls.add(source.url)
            tier_counts = state["source_tier_counts"]
            if isinstance(tier_counts, Counter):
                tier_counts[source.source_tier or "media"] += 1
            evidence_links = state["evidence_links"]
            if isinstance(evidence_links, list):
                evidence = _build_entity_evidence(source)
                if evidence.url and not any(getattr(item, "url", "") == evidence.url for item in evidence_links):
                    evidence_links.append(evidence)

    def materialize(entity_type: str | None = None) -> list[ResearchNormalizedEntityOut]:
        nodes: list[ResearchNormalizedEntityOut] = []
        for state in graph_state.values():
            role = str(state["entity_type"])
            if entity_type and role != entity_type:
                continue
            aliases = sorted(
                [normalize_text(item) for item in state["aliases"] if normalize_text(item)],
                key=len,
                reverse=True,
            )
            canonical = normalize_text(str(state["canonical_name"])) or (aliases[0] if aliases else "")
            if not canonical:
                continue
            urls = state["source_urls"]
            tier_counts = state["source_tier_counts"]
            links = state["evidence_links"]
            nodes.append(
                ResearchNormalizedEntityOut(
                    canonical_name=canonical,
                    entity_type=role if role in {"target", "competitor", "partner", "generic"} else "generic",
                    aliases=aliases[:6],
                    source_count=len(urls) if isinstance(urls, set) else 0,
                    source_tier_counts=dict(tier_counts) if isinstance(tier_counts, Counter) else {},
                    evidence_links=list(links)[:3] if isinstance(links, list) else [],
                )
            )
        return sorted(
            nodes,
            key=lambda item: (-int(item.source_count), -int(item.source_tier_counts.get("official", 0)), item.canonical_name),
        )

    return ResearchEntityGraphOut(
        entities=materialize()[:24],
        target_entities=materialize("target")[:12],
        competitor_entities=materialize("competitor")[:12],
        partner_entities=materialize("partner")[:12],
    )


def _entity_graph_lookup(graph: ResearchEntityGraphOut) -> dict[str, ResearchNormalizedEntityOut]:
    lookup: dict[str, ResearchNormalizedEntityOut] = {}
    for entity in graph.entities:
        keys = [entity.canonical_name, *entity.aliases]
        for key in keys:
            normalized = _entity_canonical_key(key)
            if normalized and normalized not in lookup:
                lookup[normalized] = entity
    return lookup


def _retrieval_quality_band(
    *,
    strict_match_ratio: float,
    official_source_ratio: float,
    unique_domain_count: int,
    normalized_entity_count: int,
) -> str:
    score = 0
    if strict_match_ratio >= 0.7:
        score += 2
    elif strict_match_ratio >= 0.45:
        score += 1
    if official_source_ratio >= 0.45:
        score += 2
    elif official_source_ratio >= 0.25:
        score += 1
    if unique_domain_count >= 5:
        score += 2
    elif unique_domain_count >= 3:
        score += 1
    if normalized_entity_count >= 9:
        score += 2
    elif normalized_entity_count >= 4:
        score += 1
    if score >= 6:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def _evidence_mode_from_metrics(
    *,
    retained_source_count: int,
    strict_topic_source_count: int,
    strict_match_ratio: float,
    official_source_ratio: float,
    unique_domain_count: int,
) -> tuple[str, str]:
    if (
        retained_source_count >= 4
        and strict_topic_source_count >= 2
        and strict_match_ratio >= 0.45
        and official_source_ratio >= 0.25
        and unique_domain_count >= 3
    ):
        return "strong", "强证据"
    if retained_source_count > 0 and (strict_topic_source_count > 0 or unique_domain_count >= 1):
        return "provisional", "可用初版"
    return "fallback", "兜底候选"


SUMMARY_GUIDANCE_TOKENS = (
    "建议",
    "建議",
    "追加",
    "优先",
    "優先",
    "继续",
    "繼續",
    "收敛到",
    "收斂到",
    "交叉检索",
    "交叉檢索",
    "重新生成",
    "后重试",
    "後重試",
    "把搜索范围",
    "把搜尋範圍",
    "不要只盯",
    "至少要回答",
)

BAD_SUMMARY_PHRASES = (
    *SUMMARY_GUIDANCE_TOKENS,
    "当前关键词范围",
    "优先给具体公司",
    "官方业务联系方式",
    "公开渠道联络人信息",
    "已向美国证券交易委",
    "美国证券交易委",
    "当前证据不足",
    "建议补充",
)

BAD_EXEC_SUMMARY_PHRASES = (
    "当前关键词范围",
    "优先给具体公司",
    "官方业务联系方式",
    "公开渠道联络人信息",
    "已向美国证券交易委",
    "美国证券交易委",
    "当前证据不足",
    "建议补充",
    "继续扩大搜索范围",
    "扩大搜索范围",
)

FIELD_ROW_NOISE_TOKENS = (
    "若金额仍缺失",
    "若暂未拿到明确金额",
    "可先给出高价值预算口径",
    "这些口径最适合后续销售",
    "尽量颗粒度细致到具体的垂直赛道",
    "精确到有预算的甲方公司",
    "建议补充公开服务热线",
    "建议将关键词收敛到具体甲方公司或项目名称",
    "继续扩大搜索范围",
    "当前证据不足",
    "优先给具体公司",
    "把高价值甲方",
    "预算判断不要只盯",
    "优先收集公开业务入口",
    "当前已收敛到具体公司，但公开联系方式仍不足",
    "如果公开联系方式依旧不足",
    "若需形成前三名单",
    "建议追加政府采购、公共资源交易、上市公告和行业媒体对",
)

ENTITY_LEADING_NOISE_PREFIXES = (
    "其中就包括",
    "其中包括",
    "其中有",
    "过去一段时间",
    "如果这一方案最终成形",
    "若最终落地",
    "它将被视为",
    "预计将是",
    "但该公司",
    "该公司",
    "关于",
    "例如",
    "比如",
    "诸如",
    "包括",
)

ENTITY_ACTION_PHRASE_TOKENS = (
    "进一步",
    "扩大",
    "推进",
    "推动",
    "打造",
    "贯彻",
    "落实",
    "印发",
    "实施",
    "支持",
    "促进",
    "加强",
    "提升",
    "降低",
    "举办",
    "表示",
    "介绍",
    "显示",
    "获得",
    "收购",
    "聚焦",
)

SOURCE_ARTIFACT_TOKENS = (
    "header_",
    "deal/deallist.html",
    "交易公开-全国公共资源交易平台",
    "全国公共资源交易平台 ·",
    "[政府采购](",
    "* [政府采购](",
    "返回顶部",
    "跳转到主要内容区域",
    "首页 关于我们 价值定位 组织架构",
    "报告共计：",
    "报告共计:",
    "发布于：",
    "发布于:",
    "文章标签：",
    "文章标签:",
    "csdn博客",
    "互联网公开网页",
    "公开线索 1 条，代表样本",
    "中国政府网政策/讲话",
    "豆瓣 ",
    "关注民生周刊",
    "微信 微博",
    "民生网首页",
    "首页 云头条",
    "ai头条 联系我们",
    "微信公众号 扫码",
    "中国招标投标网 主站",
    "欢迎您来到中国招标投标网",
    "客服中心 隐私声明 登录 注册",
    "公司简介 愿景及使命 发展历程 业务架构",
    "工作环境 员工活动 esg 环境 社会",
)

SOURCE_AWARD_NOISE_TOKENS = (
    "奖项",
    "获奖",
    "颁奖",
    "热力榜",
    "作品奖",
    "企业奖",
    "创新奖",
    "荣誉奖",
    "入围名单",
    "获奖名单",
    "评选结果",
)

SOURCE_FORUM_NOISE_TOKENS = (
    "论坛",
    "峰会",
    "大会",
    "年会",
    "沙龙",
    "闭门会",
    "圆桌",
)

SOURCE_FORUM_SPEECH_TOKENS = (
    "发言",
    "致辞",
    "演讲",
    "分享",
    "主持",
    "对话",
    "观点",
)

SOURCE_MARKDOWN_DUMP_TOKENS = (
    "markdown content",
    "source dump",
    "图片来源",
    "图源",
    "原图",
    "封面图",
    "点击查看原图",
    "查看原图",
    "source:",
    "sources:",
    "source url:",
    "source link:",
)

MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\([^)]*\)")
MARKDOWN_LINK_PATTERN = re.compile(r"(?<!\!)\[([^\]]+)\]\(([^)]+)\)")
RAW_MEDIA_URL_PATTERN = re.compile(r"https?://\S+\.(?:png|jpg|jpeg|gif|webp|svg|bmp)(?:\?\S*)?", re.IGNORECASE)
SOURCE_TEXT_SPLIT_PATTERN = re.compile(r"[。！？!?；;\n]+|\s+[|｜]\s+|\s+-\s+|(?<=\S)\s+·\s+(?=\S)")
SOURCE_DUMP_PREFIX_PATTERN = re.compile(
    r"^(?:source|sources|source url|source link|来源|圖片來源|图片来源|图源|原图|封面图|image source)[:：-]",
    re.IGNORECASE,
)

CONTACT_PLACEHOLDER_TOKENS = (
    "当前已收敛到具体公司，但公开联系方式仍不足",
    "优先收集公开业务入口",
    "建议补充公开服务热线",
    "建议将关键词收敛到具体甲方公司或项目名称",
    "如果公开联系方式依旧不足",
)

ENTITY_PLACEHOLDER_TOKENS = (
    "关键词已明确收敛到该公司",
    "该公司",
    "我方切口在于",
    "需重点验证",
    "优先核验",
    "顶层设计与咨询",
    "动漫 IP 咨询与发行伙伴",
    "区域内容集成与渠道分发伙伴",
    "文旅/教育场景牵线伙伴",
    "推出首批",
    "掌握底层AI服务",
    "大视听公共服务",
    "全方位服务",
)

GENERIC_COUNT_ENTITY_PATTERN = re.compile(r"^[一二三四五六七八九十百千两几多\d]+家")

COMMERCIAL_BUDGET_SIGNAL_TOKENS = (
    "预算",
    "采购",
    "招标",
    "中标",
    "项目",
    "投资",
    "经费",
    "金额",
    "资金",
    "专项",
    "立项",
    "合同额",
    "财政",
    "扩容",
)

BUDGET_ROW_NOISE_TOKENS = (
    "同比增长",
    "经济数据",
    "中国经济",
    "开局良好",
    "民生网首页",
    "微信 微博",
    "豆瓣 ",
    "关注民生周刊",
    "客户端 专题报道",
    "市场规模",
    "爆发元年",
    "公开市场投资者",
    "newcomer",
    "云头条",
)

BUDGET_ROW_CONTEXT_TOKENS = (
    "预算",
    "采购",
    "招标",
    "中标",
    "项目",
    "立项",
    "合同",
    "签约",
    "批复",
    "经费",
    "专项",
    "财政",
)


def _looks_like_insufficient(value: str) -> bool:
    lowered = normalize_text(value).lower()
    return any(
        token in lowered
        for token in (
            "当前证据不足",
            "目前證據不足",
            "current evidence is insufficient",
            "evidence is insufficient",
            "待补充",
            "待補充",
            "insufficient",
        )
    )


@lru_cache(maxsize=8192)
def _strip_entity_leading_noise(value: str) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    compact = normalized
    changed = True
    while changed and compact:
        changed = False
        for prefix in ENTITY_LEADING_NOISE_PREFIXES:
            if compact.startswith(prefix):
                compact = normalize_text(compact[len(prefix) :].lstrip("：:，,;；- "))
                changed = True
    return compact


@lru_cache(maxsize=8192)
def _looks_like_source_artifact_text(value: str) -> bool:
    normalized = normalize_text(value)
    lowered = normalized.lower()
    if not normalized:
        return False
    if any(token in lowered for token in SOURCE_ARTIFACT_TOKENS):
        return True
    if "http://" in lowered or "https://" in lowered:
        if any(token in lowered for token in ("[", "](", "javascript:", "deal/deallist", "ggzy.gov.cn/deal")):
            return True
    if normalized.count("全国公共资源交易平台") >= 2:
        return True
    if normalized.count("·") >= 2 and any(token in normalized for token in ("公示", "公告", "交易公开")):
        return True
    if normalized.count("：") >= 2 and any(
            token in normalized for token in ("报告共计", "发布于", "文章标签", "CSDN博客", "腾讯新闻")
    ):
        return True
    return False


def _looks_like_source_noise_segment(value: str, *, raw_value: str | None = None) -> bool:
    normalized = normalize_text(value)
    lowered = normalized.lower()
    raw_lower = str(raw_value or value).lower()
    if not normalized:
        return False
    if _looks_like_source_artifact_text(normalized):
        return True
    if SOURCE_DUMP_PREFIX_PATTERN.match(normalized):
        return True
    if any(token in normalized for token in SOURCE_AWARD_NOISE_TOKENS):
        return True
    if any(token in normalized for token in SOURCE_FORUM_NOISE_TOKENS) and any(
        token in normalized for token in SOURCE_FORUM_SPEECH_TOKENS
    ):
        return True
    if any(token in lowered for token in SOURCE_MARKDOWN_DUMP_TOKENS):
        return True
    if any(token in raw_lower for token in ("![", "](http", "](https")):
        return True
    if raw_lower.count("](") >= 2:
        return True
    if RAW_MEDIA_URL_PATTERN.search(raw_lower):
        return True
    return False


def _clean_source_text_for_analysis(value: str) -> str:
    return _clean_source_text_for_analysis_cached(str(value or ""))


@lru_cache(maxsize=8192)
def _clean_source_text_for_analysis_cached(raw: str) -> str:
    normalized_raw = normalize_text(raw)
    if not normalized_raw:
        return ""
    without_images = MARKDOWN_IMAGE_PATTERN.sub(" ", raw)
    without_links = MARKDOWN_LINK_PATTERN.sub(lambda match: match.group(1), without_images)
    without_media_urls = RAW_MEDIA_URL_PATTERN.sub(" ", without_links)
    cleaned_segments: list[str] = []
    for raw_segment in SOURCE_TEXT_SPLIT_PATTERN.split(without_media_urls):
        normalized = normalize_text(raw_segment)
        if not normalized or _looks_like_source_noise_segment(normalized, raw_value=raw_segment):
            continue
        cleaned_segments.append(normalized)
    if cleaned_segments:
        return normalize_text("。".join(cleaned_segments))
    normalized = normalize_text(without_media_urls)
    if _looks_like_source_noise_segment(normalized, raw_value=without_media_urls):
        return ""
    return normalized


@lru_cache(maxsize=8192)
def _looks_like_placeholder_entity_name(value: str) -> bool:
    normalized = _strip_entity_leading_noise(value)
    lowered = normalized.lower()
    if not normalized:
        return False
    if "（如" in normalized or "(如" in normalized:
        return True
    if normalized.startswith(("AI的", "一直", "此前", "在杭州市", "相关负责人", "对公开市场投资者而言", "上海作为")):
        return True
    if normalized.startswith(("推出首批", "构建PC端", "构建移动端", "对具有重大影响力的")):
        return True
    industry_alias_values = {
        normalize_text(alias)
        for aliases in INDUSTRY_SCOPE_ALIASES.values()
        for alias in aliases
        if normalize_text(alias)
    }
    if normalized in industry_alias_values:
        return False
    if GENERIC_COUNT_ENTITY_PATTERN.match(normalized):
        return True
    if re.search(r"(19|20)\d{2}", normalized):
        return True
    if "待验证" in normalized or "待驗證" in normalized:
        return True
    if any(token in normalized for token in ENTITY_PLACEHOLDER_TOKENS):
        return True
    if any(token in normalized for token in GENERIC_SCOPE_CLIENT_TOKENS):
        return True
    if any(token in lowered for token in ("报名通道开启", "多端联动", "opc社区", "opc创新社区", "超级个体")):
        return True
    if normalized in {"科技数码", "主办与协办", "基础算力与云服务", "区域大型系统集成"}:
        return True
    if len(normalized) <= 6 and normalized.endswith("公司") and any(token in normalized for token in ("音乐", "内容", "行业", "平台", "企业", "厂商")):
        return True
    if normalized.endswith(("服务中心", "信息中心", "数据中心")) and not any(
        token in normalized for token in (*REGION_TOKENS, "人民", "市", "省", "区", "县", "集团", "公司", "大学", "医院")
    ):
        return True
    if normalized.endswith(("系统", "方案", "平台")) and not any(
        token in normalized for token in ("公司", "集团", "科技", "软件", "信息", "智能", "云", "股份", "有限公司")
    ):
        return True
    if normalized.endswith(("伙伴", "咨询", "顾问", "发行伙伴", "牵线伙伴")) and not any(
        token in normalized for token in ENTITY_SUFFIX_TOKENS
    ):
        return True
    if len(normalized) <= 6 and normalized.endswith(("数码", "团队", "云服务")) and not any(
        token in normalized for token in ENTITY_SUFFIX_TOKENS
    ):
        return True
    if any(token in normalized for token in ENTITY_ACTION_PHRASE_TOKENS) and not any(
        token in normalized for token in ENTITY_SUFFIX_TOKENS
    ):
        return True
    if normalized.endswith(("人工智能", "生成式AI", "大模型", "AI")) and not any(
        token in normalized for token in ENTITY_SUFFIX_TOKENS
    ):
        return True
    return False


def _looks_like_placeholder_contact_row(value: str) -> bool:
    normalized = normalize_text(value)
    return bool(normalized) and any(token in normalized for token in CONTACT_PLACEHOLDER_TOKENS)


def _is_actionable_budget_row(value: str) -> bool:
    normalized = normalize_text(value)
    if (
        not normalized
        or _looks_like_insufficient(normalized)
        or _looks_like_source_artifact_text(normalized)
        or any(token in normalized for token in BUDGET_ROW_NOISE_TOKENS)
        or any(token in normalized for token in FIELD_ROW_NOISE_TOKENS)
    ):
        return False
    has_money_signal = bool(MONEY_PATTERN.search(normalized))
    has_strict_budget_signal = any(
        token in normalized for token in ("预算", "采购", "招标", "中标", "经费", "金额", "资金", "专项", "立项", "合同额", "财政", "扩容")
    )
    has_budget_context = any(token in normalized for token in BUDGET_ROW_CONTEXT_TOKENS)
    has_project_or_investment_signal = any(token in normalized for token in ("项目", "投资"))
    if has_money_signal or has_strict_budget_signal:
        return True
    if has_project_or_investment_signal and any(
        token in normalized for token in ("预算", "采购", "招标", "中标", "立项", "合同", "财政", "金额", "经费", "专项")
    ):
        return True
    if "投资" in normalized and not (has_money_signal or has_budget_context):
        return False
    return False


def _summary_contains_output_noise(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return False
    if len(normalized) > 320:
        return True
    if _looks_like_source_artifact_text(normalized):
        return True
    if any(token in normalized for token in FIELD_ROW_NOISE_TOKENS):
        return True
    if any(token in normalized for token in ("CSDN博客", "腾讯新闻", "文章标签", "报告共计", "中国政府网政策/讲话")):
        return True
    for candidate in _extract_rank_entity_candidates(normalized)[:6]:
        cleaned = _strip_entity_leading_noise(candidate)
        if not cleaned or _looks_like_scope_prompt_noise(cleaned) or _looks_like_placeholder_entity_name(cleaned):
            return True
    return False


def _concrete_rows(values: Iterable[str]) -> list[str]:
    return [normalize_text(value) for value in values if normalize_text(value) and not _looks_like_insufficient(value)]


def _is_summary_fact_row(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized or _looks_like_insufficient(normalized):
        return False
    if _looks_like_source_artifact_text(normalized):
        return False
    if any(token in normalized for token in SUMMARY_GUIDANCE_TOKENS):
        return False
    if any(token in normalized for token in FIELD_ROW_NOISE_TOKENS):
        return False
    if len(normalized) > 48 and "：" not in normalized and ":" not in normalized and "（" not in normalized:
        return False
    return True


def _summary_fact_rows(values: Iterable[str], *, limit: int = 3) -> list[str]:
    return _dedupe_strings([normalize_text(value) for value in values if _is_summary_fact_row(value)], limit)


def _looks_like_bad_executive_summary(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return True
    if len(normalized) < 36:
        return True
    if _summary_contains_output_noise(normalized):
        return True
    if any(token in normalized for token in BAD_EXEC_SUMMARY_PHRASES):
        return True
    if normalized.count("：") > 3 or normalized.count(":") > 3:
        return True
    if normalized.startswith(("本次", "当前", "建议", "研究", "报告")) and len(normalized) > 80:
        return True
    if len(normalized) > 220 and "。" not in normalized and "." not in normalized:
        return True
    return False


def _entity_display_labels(values: Iterable[str], *, limit: int = 2) -> list[str]:
    labels: list[str] = []
    for value in values:
        normalized = normalize_text(value)
        if not normalized or _looks_like_insufficient(normalized):
            continue
        if "待验证" in normalized or "待驗證" in normalized:
            continue
        if _looks_like_source_artifact_text(normalized):
            continue
        if any(token in normalized for token in SUMMARY_GUIDANCE_TOKENS):
            continue
        entity_name = _extract_rank_entity_name(normalized) or _fallback_entity_name_from_row(normalized)
        label = _strip_entity_leading_noise(entity_name or normalized.split("：", 1)[0].split(":", 1)[0])
        if (
            not label
            or _looks_like_fragment_entity_name(label)
            or _contains_low_value_entity_token(label)
            or _looks_like_placeholder_entity_name(label)
            or _looks_like_scope_prompt_noise(label)
        ):
            continue
        labels.append(label)
    return _dedupe_strings(labels, limit)


def _company_convergence_is_weak(
    *,
    scope_hints: dict[str, object],
    target_rows: Iterable[str],
    competitor_rows: Iterable[str],
) -> bool:
    if not bool(scope_hints.get("prefer_company_entities")):
        return False
    theme_labels = [
        normalize_text(str(item))
        for item in scope_hints.get("industries", []) or []
        if normalize_text(str(item))
    ]
    seed_companies = [
        normalize_text(str(item))
        for item in scope_hints.get("seed_companies", []) or []
        if normalize_text(str(item))
    ]
    candidates = _dedupe_strings(
        [*_entity_display_labels(target_rows, limit=3), *_entity_display_labels(competitor_rows, limit=3)],
        4,
    )
    concrete = [
        item
        for item in candidates
        if _is_company_like_entity_name(
            item,
            role="target",
            theme_labels=theme_labels,
            seed_companies=seed_companies,
        )
    ]
    minimum = 2 if bool(scope_hints.get("prefer_head_companies")) else 1
    return len(concrete) < minimum


def _company_intent_summary_needs_override(
    *,
    scope_hints: dict[str, object],
    summary: str,
    accounts: list[str],
    competitors: list[str],
) -> bool:
    if not bool(scope_hints.get("prefer_company_entities")):
        return False
    normalized_summary = normalize_text(summary)
    anchors = _dedupe_strings(
        [
            *accounts,
            *competitors,
            *[
                normalize_text(str(item))
                for item in scope_hints.get("seed_companies", []) or []
                if normalize_text(str(item))
            ],
        ],
        4,
    )
    if _company_convergence_is_weak(
        scope_hints=scope_hints,
        target_rows=accounts,
        competitor_rows=competitors,
    ):
        return True
    if not normalized_summary:
        return True
    if anchors and not any(anchor in normalized_summary for anchor in anchors):
        return True
    blocked_tokens = {
        token
        for label in [
            normalize_text(str(item))
            for item in scope_hints.get("industries", []) or []
            if normalize_text(str(item))
        ]
        for token in THEME_ENTITY_BLOCK_TOKENS.get(label, {}).get("target", ())
        if normalize_text(token)
    }
    return any(token in normalized_summary for token in blocked_tokens) and not any(anchor in normalized_summary for anchor in anchors)


ENTITY_ROLE_FIELDS: dict[str, str] = {
    "target_accounts": "target",
    "client_peer_moves": "target",
    "competitor_profiles": "competitor",
    "winner_peer_moves": "competitor",
    "ecosystem_partners": "partner",
}

ENTITY_ROLE_CONTEXT_TOKENS: dict[str, tuple[str, ...]] = {
    "target": ("采购", "预算", "招标", "项目", "建设", "立项", "规划", "部署", "业主", "甲方"),
    "competitor": ("中标", "成交", "方案", "平台", "交付", "厂商", "案例", "竞品", "产品", "解决方案"),
    "partner": ("合作", "伙伴", "联合", "生态", "咨询", "顾问", "渠道", "集成", "联盟", "牵线", "总包"),
}

ENTITY_ROLE_NAME_HINTS: dict[str, tuple[str, ...]] = {
    "target": ("政府", "局", "委", "办", "中心", "医院", "大学", "银行", "学校", "集团", "城投", "交投", "水务", "地铁"),
    "competitor": ("科技", "信息", "软件", "智能", "云", "数据", "通信", "平台", "系统", "股份", "有限公司"),
    "partner": ("咨询", "顾问", "集成", "渠道", "联盟", "协会", "研究院", "研究所", "运营", "服务"),
}

CONTACT_PAGE_TOKENS = ("contact", "lxwm", "about", "relation", "ir", "investor", "join", "service", "联系我们", "联络", "联系")
COMPANY_PROFILE_PAGE_TOKENS = (
    *CONTACT_PAGE_TOKENS,
    "官网",
    "官方",
    "公开入口",
    "关于我们",
    "公司简介",
    "企业简介",
    "品牌介绍",
    "aboutus",
    "about-us",
    "official",
    "profile",
    "company",
    "business",
    "solution",
    "brand",
    "investor relations",
)
CONTACT_ROW_HINT_TOKENS = (
    "公开邮箱",
    "公开电话",
    "公开联系人",
    "高概率公开联系页",
    "官网/公开入口",
    "服务热线",
    "联系邮箱",
    "联系电话",
    "采购人联系人",
    "代理机构联系人",
    "可能归口部门",
)
DEPARTMENT_HINT_TOKENS = (
    "采购部",
    "采购中心",
    "招标办",
    "招采中心",
    "集采中心",
    "信息中心",
    "信息化部",
    "数字化部",
    "科技部",
    "数据局",
    "数据资源局",
    "办公室",
    "财务部",
    "计划财务部",
    "运营部",
    "网络安全部",
    "政务服务中心",
    "行政审批局",
    "事业发展部",
    "建设管理部",
    "投资管理部",
)
CASE_HINT_TOKENS = ("案例", "项目", "落地", "部署", "平台", "中标", "示范", "试点", "标杆")
PRODUCT_HINT_TOKENS = ("产品", "平台", "系统", "方案", "服务", "引擎", "模型", "套件")
NON_CONTACT_SOURCE_LABEL_TOKENS = ("云头条", "剑鱼标讯", "微信公众号", "互联网公开网页", "政府采购合规聚合")


@lru_cache(maxsize=8192)
def _contains_low_value_entity_token(value: str) -> bool:
    normalized = normalize_text(value)
    return any(token in normalized for token in LOW_VALUE_ENTITY_NAME_TOKENS)


@lru_cache(maxsize=8192)
def _is_lightweight_entity_name(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized or len(normalized) < 2 or len(normalized) > 14:
        return False
    if normalized not in KNOWN_LIGHTWEIGHT_ENTITY_NAMES:
        return False
    if _contains_low_value_entity_token(normalized):
        return False
    if any(token in normalized for token in ENTITY_INVALID_PHRASE_TOKENS):
        return False
    if any(token in normalized for token in ("入口", "官网", "官网入口", "公开入口", "联系页", "会员中心")):
        return False
    if any(char in normalized for char in "：:（）()[]【】"):
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9\u4e00-\u9fa5·]{2,14}", normalized))


@lru_cache(maxsize=8192)
def _looks_like_fragment_entity_name(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return True
    if _looks_like_placeholder_entity_name(normalized):
        return True
    if re.match(r"^(19|20)\d{2}", normalized):
        return True
    if normalized.startswith(ENTITY_FRAGMENT_PREFIX_TOKENS):
        return True
    if any(token in normalized for token in ENTITY_FRAGMENT_INFIX_TOKENS):
        return True
    if (
        len(normalized) <= 4
        and normalized.endswith(("局", "委", "办", "中心", "政府"))
        and not any(token in normalized for token in (*REGION_TOKENS, "人民", "文物", "数据", "信息", "交通", "教育", "医疗"))
        and normalized not in KNOWN_LIGHTWEIGHT_ENTITY_NAMES
    ):
        return True
    if (
        normalized.endswith(("服务", "系统", "社区"))
        and not any(token in normalized for token in ENTITY_SUFFIX_TOKENS)
        and normalized not in KNOWN_LIGHTWEIGHT_ENTITY_NAMES
    ):
        return True
    if (
        normalized.endswith("中心")
        and (
            "新型" in normalized
            or not any(
                token in normalized
                for token in (
                    *REGION_TOKENS,
                    "市", "省", "区", "县", "政府", "政务", "局", "委", "办", "大学", "医院", "学校",
                    "人民", "公共", "资源", "交易", "采购", "服务", "管理", "研究", "信息化",
                )
            )
        )
        and normalized not in KNOWN_LIGHTWEIGHT_ENTITY_NAMES
    ):
        return True
    return False


@lru_cache(maxsize=8192)
def _fallback_entity_name_from_row(value: str) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    head = _strip_entity_leading_noise(normalized.split("：", 1)[0].split(":", 1)[0])
    if _is_lightweight_entity_name(head):
        return head
    match = re.match(r"([A-Za-z0-9\u4e00-\u9fa5·]{2,14})(?:等|与|及|和|在|已|将|正|宣布|布局|入局|合作|参与)", normalized)
    if match:
        candidate = _strip_entity_leading_noise(match.group(1))
        if _is_lightweight_entity_name(candidate):
            return candidate
    return ""


@lru_cache(maxsize=8192)
def _is_useful_public_contact_row(value: str) -> bool:
    normalized = normalize_text(value)
    lowered = normalized.lower()
    if not normalized or _looks_like_insufficient(normalized):
        return False
    if normalized.startswith(("对于 ", "對於 ", "围绕 ", "圍繞 ")):
        return False
    if _looks_like_source_artifact_text(normalized) or _looks_like_placeholder_contact_row(normalized):
        return False
    if _contains_low_value_entity_token(normalized):
        return False
    if any(lowered.endswith(ext) for ext in (".webp", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".bmp")):
        return False
    if lowered.startswith("http") and any(domain in lowered for domain in GENERIC_CONTENT_DOMAINS):
        return False
    if any(domain in lowered for domain in GENERIC_CONTENT_DOMAINS):
        return False
    label = normalize_text(normalized.split("：", 1)[0].split(":", 1)[0])
    if any(token in label for token in NON_CONTACT_SOURCE_LABEL_TOKENS):
        return False
    if any(token in label for token in ("中国政府网", "政策/讲话", "互联网公开网页", "腾讯新闻")):
        return False
    if label in {"中国大学"}:
        return False
    if label and ("：" in normalized or ":" in normalized) and not (
        _is_plausible_entity_name(label) or _is_lightweight_entity_name(label)
    ):
        return False
    if EMAIL_PATTERN.search(normalized) or PHONE_PATTERN.search(normalized):
        return True
    if any(token in normalized for token in CONTACT_ROW_HINT_TOKENS):
        return True
    if any(token in lowered for token in CONTACT_PAGE_TOKENS):
        return True
    return False


@lru_cache(maxsize=8192)
def _is_useful_department_row(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized or _looks_like_insufficient(normalized):
        return False
    if _contains_low_value_entity_token(normalized):
        return False
    if any(token in normalized for token in DEPARTMENT_HINT_TOKENS):
        return True
    return bool(DEPARTMENT_PATTERN.search(normalized))


@lru_cache(maxsize=16384)
def _sanitize_entity_row(field_key: str, value: str) -> str:
    normalized = normalize_text(value)
    if not normalized or _looks_like_insufficient(normalized) or _looks_like_source_artifact_text(normalized):
        return ""
    if _contains_low_value_entity_token(normalized):
        return ""
    role = ENTITY_ROLE_FIELDS.get(field_key, "")
    if not role:
        return normalized
    candidate = _extract_rank_entity_name(normalized)
    if not candidate:
        candidate = _fallback_entity_name_from_row(normalized)
    if not candidate:
        return ""
    candidate = _strip_entity_leading_noise(candidate)
    if not _is_plausible_entity_name(candidate) and not _is_lightweight_entity_name(candidate):
        return ""
    if _looks_like_fragment_entity_name(candidate):
        return ""
    if _contains_low_value_entity_token(candidate):
        return ""
    if _looks_like_scope_prompt_noise(candidate):
        return ""
    if _looks_like_placeholder_entity_name(candidate):
        return ""
    name_hints = ENTITY_ROLE_NAME_HINTS.get(role, ())
    context_hints = ENTITY_ROLE_CONTEXT_TOKENS.get(role, ())
    has_name_hint = any(token in candidate for token in name_hints)
    has_context_hint = any(token in normalized for token in context_hints)
    if role == "target":
        if not has_name_hint and not has_context_hint:
            return ""
        if any(token in candidate for token in ("国际招标", "招标有限责任公司", "招标有限公司", "招标代理")):
            return ""
        if candidate.endswith(("办公厅", "办公室")) and not has_context_hint:
            return ""
        if any(token in candidate for token in ("科技", "软件", "智能", "平台", "模型", "芯片", "华为", "腾讯云", "阿里云", "火山引擎")) and not has_context_hint:
            return ""
    elif role == "competitor":
        if any(token in candidate for token in ("政府", "局", "委", "办", "中心", "医院", "大学", "学校", "银行")):
            return ""
    elif role == "partner":
        if any(token in candidate for token in ("政府", "市委", "市政府", "局", "委", "办", "中心", "办公室", "办公厅")):
            return ""
        if any(token in candidate for token in ("模型", "芯片", "平台", "产品")) and not any(alias in candidate for alias in PARTNER_CONNECTOR_ALIASES):
            return ""
    if not has_name_hint and not has_context_hint and candidate == normalized:
        return ""
    if candidate != normalized and ("：" in normalized or ":" in normalized):
        return candidate
    if "：" not in normalized and ":" not in normalized and candidate != normalized and len(normalized) > len(candidate) + 6:
        return candidate
    return normalized


def _sanitize_generic_row(field_key: str, value: str) -> str:
    normalized = normalize_text(value)
    if not normalized or _looks_like_insufficient(normalized):
        return ""
    if any(token in normalized for token in FIELD_ROW_NOISE_TOKENS):
        return ""
    if _looks_like_source_artifact_text(normalized):
        return ""
    if field_key == "budget_signals" and not _is_actionable_budget_row(normalized):
        return ""
    if field_key == "benchmark_cases":
        if not any(token in normalized for token in CASE_HINT_TOKENS):
            return ""
        if normalized.startswith(("行业", "產業", "行业案例", "案例拆解")) or "拆解" in normalized:
            return ""
        if any(
            token in normalized
            for token in ("热力榜", "年度作品奖", "年度企业奖", "内容创作奖", "技术创新奖", "特别荣誉奖")
        ):
            return ""
        if normalized.startswith(("相关负责人表示", "有关负责人表示")):
            return ""
        if any(token in normalized for token in ("营商环境", "服务保障", "全力支持项目落地", "共同培育")) and not any(
            token in normalized for token in ("中标", "部署", "平台", "试点", "案例")
        ):
            return ""
        if len(normalized) > 96 and "：" not in normalized and ":" not in normalized:
            return ""
    if field_key == "flagship_products":
        if not any(token in normalized for token in PRODUCT_HINT_TOKENS):
            return ""
    if _contains_low_value_entity_token(normalized):
        return ""
    return normalized


def _sanitize_report_field_rows(field_key: str, values: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    canonical_rows: dict[str, str] = {}
    canonical_order: list[str] = []
    for raw in values:
        normalized = normalize_text(str(raw))
        if not normalized:
            continue
        if field_key == "public_contact_channels":
            candidate = normalized if _is_useful_public_contact_row(normalized) else ""
        elif field_key == "target_departments":
            candidate = normalized if _is_useful_department_row(normalized) else ""
        elif field_key in ENTITY_ROLE_FIELDS:
            candidate = _sanitize_entity_row(field_key, normalized)
        else:
            candidate = _sanitize_generic_row(field_key, normalized)
        candidate = normalize_text(candidate)
        if not candidate:
            continue
        if field_key in ENTITY_ROLE_FIELDS:
            entity_name = _extract_rank_entity_name(candidate) or _fallback_entity_name_from_row(candidate) or candidate
            canonical_key = _entity_canonical_key(entity_name)
            if canonical_key:
                existing = canonical_rows.get(canonical_key, "")
                if not existing:
                    canonical_rows[canonical_key] = candidate
                    canonical_order.append(canonical_key)
                elif len(candidate) > len(existing):
                    canonical_rows[canonical_key] = candidate
                continue
        if candidate in seen:
            continue
        seen.add(candidate)
        cleaned.append(candidate)
    for canonical_key in canonical_order:
        candidate = normalize_text(canonical_rows.get(canonical_key, ""))
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        cleaned.append(candidate)
    return cleaned


def _extract_matching_sentences(
    sources: list[SourceDocument],
    *,
    keywords: tuple[str, ...],
    limit: int,
    scope_hints: dict[str, object] | None = None,
) -> list[str]:
    sentences: list[str] = []
    normalized_keywords = tuple(normalize_text(item).lower() for item in keywords if normalize_text(item))
    for source in sources:
        chunks = re.split(r"[。！？!?；;\n]", _source_text(source))
        for chunk in chunks:
            text = normalize_text(chunk)
            lowered = text.lower()
            if not text:
                continue
            if any(keyword in lowered for keyword in normalized_keywords):
                if scope_hints and _text_has_region_conflict(text, scope_hints=scope_hints):
                    continue
                sentences.append(_truncate_text(text, 110))
    return _dedupe_strings(sentences, limit)


def _extract_money_signals(
    sources: list[SourceDocument],
    *,
    limit: int,
    scope_hints: dict[str, object] | None = None,
) -> list[str]:
    signals: list[str] = []
    for source in sources:
        text = _source_text(source)
        for match in MONEY_PATTERN.finditer(text):
            start = max(0, match.start() - 18)
            end = min(len(text), match.end() + 26)
            candidate = _truncate_text(text[start:end], 110)
            if scope_hints and _text_has_region_conflict(candidate, scope_hints=scope_hints):
                continue
            signals.append(candidate)
    if not signals:
        signals = _extract_matching_sentences(
            sources,
            keywords=("预算", "投资", "金额", "经费", "财政投入"),
            limit=limit,
            scope_hints=scope_hints,
        )
    return _dedupe_strings(signals, limit)


def _extract_region_distribution(
    sources: list[SourceDocument],
    *,
    limit: int,
    scope_hints: dict[str, object] | None = None,
) -> list[str]:
    counter: Counter[str] = Counter()
    region_examples: dict[str, str] = {}
    allowed_regions = set()
    if scope_hints:
        allowed_regions = {
            item.lower()
            for item in _expand_region_scope_terms(
                [normalize_text(str(region)) for region in scope_hints.get("regions", []) if normalize_text(str(region))]
            )
        }
    for source in sources:
        text = _source_text(source)
        for region in REGION_TOKENS:
            if allowed_regions and region.lower() not in allowed_regions:
                continue
            if region in text:
                counter[region] += 1
                region_examples.setdefault(region, _truncate_text(source.title, 64))
    rows = [
        f"{region}：公开线索 {count} 条，代表样本 {region_examples.get(region, '待补充')}"
        for region, count in counter.most_common(limit)
    ]
    return _dedupe_strings(rows, limit)


def _expand_region_scope_terms(regions: list[str]) -> list[str]:
    expanded: list[str] = []
    for raw_region in regions:
        normalized = normalize_text(raw_region)
        if not normalized:
            continue
        expanded.append(normalized)
        expanded.extend(REGION_SCOPE_ALIASES.get(normalized, ()))
    return _dedupe_strings(expanded, 24)


def _text_has_region_conflict(text: str, *, scope_hints: dict[str, object]) -> bool:
    scope_regions = [normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    if not scope_regions:
        return False
    allowed_regions = [item.lower() for item in _expand_region_scope_terms(scope_regions)]
    normalized_text = normalize_text(text).lower()
    if not normalized_text:
        return False
    explicit_region_hits = [region for region in REGION_TOKENS if region.lower() in normalized_text]
    explicit_region_hits.extend(
        label
        for label in REGION_SCOPE_ALIASES
        if label.lower() in normalized_text
    )
    explicit_region_hits = list(dict.fromkeys(explicit_region_hits))
    if not explicit_region_hits:
        return False
    if any(hit.lower() in allowed_regions for hit in explicit_region_hits):
        return False
    return not any(term in normalized_text for term in allowed_regions)


def _source_has_region_conflict(source: SourceDocument, *, scope_hints: dict[str, object]) -> bool:
    return _text_has_region_conflict(_source_text(source), scope_hints=scope_hints)


def _count_region_conflicts(sources: list[SourceDocument], *, scope_hints: dict[str, object]) -> int:
    if not sources:
        return 0
    return sum(1 for source in sources if _source_has_region_conflict(source, scope_hints=scope_hints))


def _region_conflict_signature(source: SourceDocument) -> str:
    return normalize_text(" | ".join([source.url or "", source.title or "", source.domain or ""]))


def _extract_org_candidates(
    sources: list[SourceDocument],
    *,
    limit: int,
    scope_hints: dict[str, object] | None = None,
) -> list[str]:
    candidates: list[str] = []
    for source in sources:
        for match in _extract_rank_entity_candidates(_source_text(source), scope_hints=scope_hints):
            value = normalize_text(match)
            if 2 <= len(value) <= 36:
                candidates.append(value)
    return _dedupe_strings(candidates, limit)


def _pick_industry_methodology_profile(
    industries: Iterable[str],
    *,
    keyword: str,
    research_focus: str | None,
) -> IndustryMethodologyProfile | None:
    candidates = [normalize_text(str(item)) for item in industries if normalize_text(str(item))]
    priority_order = (
        "政务云",
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
    sorted_candidates = sorted(
        candidates,
        key=lambda candidate: priority_order.index(candidate) if candidate in priority_order else len(priority_order),
    )
    for candidate in sorted_candidates:
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
    return None


def _format_methodology_query_templates(
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
    replacements = {
        "keyword": _strip_query_noise(keyword) or normalize_text(keyword),
        "focus": _strip_query_noise(research_focus or "") or normalize_text(research_focus or ""),
        "region": normalize_text(regions[0]) if regions else "",
        "industry": normalize_text(industries[0]) if industries else profile.key,
        "client": normalize_text(clients[0]) if clients else "",
    }
    queries: list[str] = []
    for template in profile.query_templates:
        try:
            rendered = template.format(**replacements)
        except Exception:
            rendered = template
        normalized = normalize_text(rendered)
        if normalized:
            queries.append(normalized)
    return _dedupe_strings(queries, 8)


def _build_industry_methodology_scope_hints(
    *,
    keyword: str,
    research_focus: str | None,
    regions: list[str],
    industries: list[str],
    clients: list[str],
) -> dict[str, object]:
    profile = _pick_industry_methodology_profile(industries, keyword=keyword, research_focus=research_focus)
    if profile is None:
        return {}
    query_expansions = _format_methodology_query_templates(
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


def _render_industry_methodology_context(scope_hints: dict[str, object]) -> str:
    profile = normalize_text(str(scope_hints.get("industry_methodology_profile", "")))
    framework = normalize_text(str(scope_hints.get("industry_methodology_framework", "")))
    authority = normalize_text(str(scope_hints.get("industry_methodology_authority", "")))
    questions = _dedupe_strings(scope_hints.get("industry_methodology_questions", []) or [], 4)
    sources = _dedupe_strings(scope_hints.get("industry_methodology_source_preferences", []) or [], 5)
    if not profile and not framework and not questions:
        return ""
    rows: list[str] = []
    if profile or authority:
        rows.append(f"行业方法论：{profile or '行业研究'}｜{authority or '咨询调研框架'}")
    if framework:
        rows.append(f"分析框架：{framework}")
    if questions:
        rows.append(f"优先核验：{'；'.join(questions)}")
    if sources:
        rows.append(f"来源优先级：{'、'.join(sources)}")
    return "\n".join(rows)


def _build_industry_methodology_rows(
    *,
    scope_hints: dict[str, object],
    output_language: str,
    scope_anchor: str,
) -> dict[str, list[str]]:
    profile = normalize_text(str(scope_hints.get("industry_methodology_profile", "")))
    framework = normalize_text(str(scope_hints.get("industry_methodology_framework", "")))
    if not profile and not framework:
        return {}
    solution_lenses = _dedupe_strings(scope_hints.get("industry_methodology_solution_lenses", []) or [], 4)
    sales_lenses = _dedupe_strings(scope_hints.get("industry_methodology_sales_lenses", []) or [], 4)
    bidding_lenses = _dedupe_strings(scope_hints.get("industry_methodology_bidding_lenses", []) or [], 4)
    outreach_lenses = _dedupe_strings(scope_hints.get("industry_methodology_outreach_lenses", []) or [], 4)
    ecosystem_lenses = _dedupe_strings(scope_hints.get("industry_methodology_ecosystem_lenses", []) or [], 4)
    questions = _dedupe_strings(scope_hints.get("industry_methodology_questions", []) or [], 4)
    label = profile or scope_anchor
    return {
        "industry_brief": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"{label} 建议按“{framework or '需求拆解 -> 预算验证 -> 招采节奏 -> 扩容路径'}”来组织研究，而不是只做泛行业素材汇总。",
                    "zh-TW": f"{label} 建議按「{framework or '需求拆解 -> 預算驗證 -> 招採節奏 -> 擴容路徑'}」來組織研究，而不是只做泛行業素材彙整。",
                    "en": f"For {label}, organize the memo around {framework or 'demand, budget, procurement timing, and expansion path'} instead of generic market commentary.",
                },
                f"{label} 建议按“{framework or '需求拆解 -> 预算验证 -> 招采节奏 -> 扩容路径'}”来组织研究，而不是只做泛行业素材汇总。",
            )
        ],
        "solution_design": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"方案设计优先围绕 {label} 的 {(' / '.join(solution_lenses) or '场景闭环 / 分期实施 / 集成改造 / 扩容路径')} 拆解。",
                    "zh-TW": f"方案設計優先圍繞 {label} 的 {(' / '.join(solution_lenses) or '場景閉環 / 分期實施 / 整合改造 / 擴容路徑')} 拆解。",
                    "en": f"Solution design should emphasize {', '.join(solution_lenses) or 'use-case closure, phased rollout, integration, and expansion'} for {label}.",
                },
                f"方案设计优先围绕 {label} 的 {(' / '.join(solution_lenses) or '场景闭环 / 分期实施 / 集成改造 / 扩容路径')} 拆解。",
            )
        ],
        "sales_strategy": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"销售推进优先验证 {(' / '.join(sales_lenses) or '牵头部门 / 预算归口 / 年度节点 / 扩容窗口')}，避免只聊产品能力。",
                    "zh-TW": f"銷售推進優先驗證 {(' / '.join(sales_lenses) or '牽頭部門 / 預算歸口 / 年度節點 / 擴容窗口')}，避免只聊產品能力。",
                    "en": f"Sales planning should validate {', '.join(sales_lenses) or 'the buyer lead, budget owner, planning cycle, and expansion window'} before pitching product.",
                },
                f"销售推进优先验证 {(' / '.join(sales_lenses) or '牵头部门 / 预算归口 / 年度节点 / 扩容窗口')}，避免只聊产品能力。",
            )
        ],
        "bidding_strategy": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"投标布局优先核验 {(' / '.join(bidding_lenses) or '采购意向 / 总分包结构 / 资质要求 / 交付壁垒')}。",
                    "zh-TW": f"投標布局優先核驗 {(' / '.join(bidding_lenses) or '採購意向 / 總分包結構 / 資質要求 / 交付壁壘')}。",
                    "en": f"Bidding planning should verify {', '.join(bidding_lenses) or 'intent notices, prime/subcontract structure, qualification requirements, and delivery barriers'}.",
                },
                f"投标布局优先核验 {(' / '.join(bidding_lenses) or '采购意向 / 总分包结构 / 资质要求 / 交付壁垒')}。",
            )
        ],
        "outreach_strategy": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"拜访顺序建议按 {(' / '.join(outreach_lenses) or '牵头部门 -> 预算归口 -> 采购执行 -> 落地部门')} 展开。",
                    "zh-TW": f"拜訪順序建議按 {(' / '.join(outreach_lenses) or '牽頭部門 -> 預算歸口 -> 採購執行 -> 落地部門')} 展開。",
                    "en": f"Outreach should follow {', '.join(outreach_lenses) or 'business lead, budget owner, procurement, then implementation teams'}.",
                },
                f"拜访顺序建议按 {(' / '.join(outreach_lenses) or '牵头部门 -> 预算归口 -> 采购执行 -> 落地部门')} 展开。",
            )
        ],
        "ecosystem_strategy": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"生态优先围绕 {(' / '.join(ecosystem_lenses) or '总包 / 集成 / 顾问 / 本地交付')} 建立牵线链路。",
                    "zh-TW": f"生態優先圍繞 {(' / '.join(ecosystem_lenses) or '總包 / 整合 / 顧問 / 在地交付')} 建立牽線鏈路。",
                    "en": f"Ecosystem mapping should prioritize {', '.join(ecosystem_lenses) or 'primes, integrators, advisors, and local delivery partners'}.",
                },
                f"生态优先围绕 {(' / '.join(ecosystem_lenses) or '总包 / 集成 / 顾问 / 本地交付')} 建立牵线链路。",
            )
        ],
        "next_actions": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"先补证这几个问题：{'；'.join(questions) if questions else '锁定牵头部门、预算口径、招采窗口和扩容路径'}。",
                    "zh-TW": f"先補證這幾個問題：{'；'.join(questions) if questions else '鎖定牽頭部門、預算口徑、招採窗口與擴容路徑'}。",
                    "en": f"First validate these questions: {'; '.join(questions) if questions else 'buyer lead, budget line, procurement window, and expansion path'}.",
                },
                f"先补证这几个问题：{'；'.join(questions) if questions else '锁定牵头部门、预算口径、招采窗口和扩容路径'}。",
            )
        ],
    }


def _infer_input_scope_hints(
    keyword: str,
    research_focus: str | None,
) -> dict[str, object]:
    seed_text = normalize_text(" ".join([keyword, _sanitize_research_focus_text(research_focus)]))
    exclusion_terms = _extract_explicit_exclusion_terms(research_focus)
    if not seed_text:
        return {
            "regions": [],
            "industries": [],
            "clients": [],
            "company_anchors": [],
            "strategy_must_include_terms": [],
            "strategy_exclusion_terms": exclusion_terms,
            "strategy_query_expansions": [],
            "strategy_scope_summary": "",
            "anchor_text": "",
            "industry_methodology_profile": "",
            "industry_methodology_authority": "",
            "industry_methodology_framework": "",
            "industry_methodology_questions": [],
            "industry_methodology_source_preferences": [],
            "industry_methodology_solution_lenses": [],
            "industry_methodology_sales_lenses": [],
            "industry_methodology_bidding_lenses": [],
            "industry_methodology_outreach_lenses": [],
            "industry_methodology_ecosystem_lenses": [],
        }

    region_hints = _dedupe_strings(
        [
            label
            for label, aliases in REGION_SCOPE_ALIASES.items()
            if any(alias in seed_text for alias in aliases)
        ]
        + [region for region in REGION_TOKENS if region in seed_text],
        4,
    )
    industry_hints = _prune_industry_hints(
        [
            label
            for label, aliases in INDUSTRY_SCOPE_ALIASES.items()
            if any(alias in seed_text for alias in aliases)
        ]
    )
    theme_labels = _dedupe_strings(
        [*industry_hints, *_theme_labels_from_scope({}, keyword=keyword, research_focus=research_focus)],
        3,
    )
    prefer_company_entities, prefer_head_companies = _infer_company_query_preferences(
        seed_text,
        theme_labels=theme_labels,
    )
    company_anchors = _extract_company_anchor_terms(keyword, research_focus)
    client_candidates = [
        item
        for item in company_anchors[:3]
        if _is_theme_aligned_entity_name(item, role="target", theme_labels=theme_labels)
    ]
    if not client_candidates:
        client_candidates = _dedupe_strings(
            [
                item
                for item in ORG_PATTERN.findall(seed_text)
                if _is_theme_aligned_entity_name(item, role="target", theme_labels=theme_labels)
            ],
            3,
        )
    strategy_must_include_terms = _dedupe_strings(
        [
            term
            for label in industry_hints
            for term in THEME_STRICT_MUST_INCLUDE_TERMS.get(label, ())
        ],
        8,
    )
    seed_companies = _dedupe_strings(
        [
            item
            for label in theme_labels
            for item in THEME_COMPANY_PUBLIC_SOURCE_SEEDS.get(label, ())
        ],
        12,
    )
    methodology_scope_hints = _build_industry_methodology_scope_hints(
        keyword=keyword,
        research_focus=research_focus,
        regions=region_hints,
        industries=theme_labels or industry_hints,
        clients=client_candidates,
    )

    return {
        "regions": region_hints,
        "industries": industry_hints,
        "clients": client_candidates,
        "company_anchors": company_anchors[:4],
        "prefer_company_entities": prefer_company_entities,
        "prefer_head_companies": prefer_head_companies,
        "seed_companies": seed_companies if prefer_company_entities or prefer_head_companies else [],
        "strategy_must_include_terms": strategy_must_include_terms,
        "strategy_exclusion_terms": exclusion_terms,
        "strategy_query_expansions": [],
        "strategy_scope_summary": "",
        "anchor_text": normalize_text(" / ".join(region_hints[:2] + industry_hints[:2] + client_candidates[:2])),
        **methodology_scope_hints,
    }


def _infer_scope_hints(
    keyword: str,
    research_focus: str | None,
    sources: list[SourceDocument],
) -> dict[str, object]:
    seed_text = normalize_text(
        " ".join([keyword, _sanitize_research_focus_text(research_focus)] + [f"{source.title} {source.snippet}" for source in sources[:10]])
    )
    region_counter: Counter[str] = Counter()
    for label, aliases in REGION_SCOPE_ALIASES.items():
        if any(alias in seed_text for alias in aliases):
            region_counter[label] += 4
    for region in REGION_TOKENS:
        if region in seed_text:
            region_counter[region] += 3
    for source in sources:
        text = _source_text(source)
        for label, aliases in REGION_SCOPE_ALIASES.items():
            if any(alias in text for alias in aliases):
                region_counter[label] += 1
        for region in REGION_TOKENS:
            if region in text:
                region_counter[region] += 1

    region_hints = [region for region, _ in region_counter.most_common(3)]

    normalized_seed = seed_text.lower()
    industry_hints: list[str] = []
    for label, aliases in INDUSTRY_SCOPE_ALIASES.items():
        if any(alias.lower() in normalized_seed for alias in aliases):
            industry_hints.append(label)
    industry_hints = list(dict.fromkeys(industry_hints))[:3]
    theme_labels = _dedupe_strings(
        [*industry_hints, *_theme_labels_from_scope({}, keyword=keyword, research_focus=research_focus)],
        3,
    )
    prefer_company_entities, prefer_head_companies = _infer_company_query_preferences(
        seed_text,
        theme_labels=theme_labels,
    )

    company_anchors = _extract_company_anchor_terms(keyword, research_focus)
    org_candidates = _extract_org_candidates(sources, limit=24)
    client_candidates = [
        item
        for item in company_anchors[:3]
        if _is_theme_aligned_entity_name(item, role="target", theme_labels=theme_labels)
    ]
    if theme_labels:
        client_candidates.extend(
            item
            for item in org_candidates
            if _is_theme_aligned_entity_name(item, role="target", theme_labels=theme_labels)
        )
    else:
        client_candidates.extend(
            item
            for item in org_candidates
            if any(
                token in item
                for token in ("政府", "局", "委", "办", "中心", "医院", "大学", "银行", "学校", "集团", "城投", "交投", "水务", "地铁")
            )
        )
    client_candidates = _dedupe_strings(client_candidates, 3)
    if not client_candidates:
        keyword_orgs = ORG_PATTERN.findall(seed_text)
        client_candidates = _dedupe_strings(
            [
                item
                for item in keyword_orgs
                if _is_theme_aligned_entity_name(item, role="target", theme_labels=theme_labels)
            ]
            or keyword_orgs,
            3,
        )

    seed_companies = _dedupe_strings(
        [
            item
            for label in theme_labels
            for item in THEME_COMPANY_PUBLIC_SOURCE_SEEDS.get(label, ())
        ],
        12,
    )
    methodology_scope_hints = _build_industry_methodology_scope_hints(
        keyword=keyword,
        research_focus=research_focus,
        regions=region_hints,
        industries=theme_labels or industry_hints,
        clients=client_candidates,
    )

    return {
        "regions": region_hints,
        "industries": industry_hints,
        "clients": client_candidates,
        "company_anchors": company_anchors[:4],
        "prefer_company_entities": prefer_company_entities,
        "prefer_head_companies": prefer_head_companies,
        "seed_companies": seed_companies if prefer_company_entities or prefer_head_companies else [],
        "anchor_text": normalize_text(" / ".join(region_hints[:2] + industry_hints[:2] + client_candidates[:2])),
        **methodology_scope_hints,
    }


def _merge_scope_hints(
    base: dict[str, object],
    refined: dict[str, object],
) -> dict[str, object]:
    base_regions = [normalize_text(str(item)) for item in (base.get("regions", []) or []) if normalize_text(str(item))]
    refined_regions = [normalize_text(str(item)) for item in (refined.get("regions", []) or []) if normalize_text(str(item))]
    if base_regions:
        allowed_terms = {item.lower() for item in _expand_region_scope_terms(base_regions)}
        region_candidates = list(base_regions)
        region_candidates.extend(
            item
            for item in refined_regions
            if item.lower() in allowed_terms
            or any(alias.lower() in allowed_terms for alias in REGION_SCOPE_ALIASES.get(item, ()))
        )
        regions = _dedupe_strings(region_candidates, 3)
    else:
        regions = _dedupe_strings([*refined_regions], 3)
    base_industries = [normalize_text(str(item)) for item in (base.get("industries", []) or []) if normalize_text(str(item))]
    refined_industries = [normalize_text(str(item)) for item in (refined.get("industries", []) or []) if normalize_text(str(item))]
    if base_industries:
        allowed_industry_terms = {
            normalize_text(alias)
            for industry in base_industries
            for alias in (industry, *INDUSTRY_SCOPE_ALIASES.get(industry, ()))
            if normalize_text(alias)
        }
        industry_candidates = list(base_industries)
        industry_candidates.extend(
            item
            for item in refined_industries
            if item in allowed_industry_terms
            or any(normalize_text(alias) in allowed_industry_terms for alias in INDUSTRY_SCOPE_ALIASES.get(item, ()))
        )
        industries = _prune_industry_hints(industry_candidates)
    else:
        industries = _prune_industry_hints(refined_industries)

    base_clients = [normalize_text(str(item)) for item in (base.get("clients", []) or []) if normalize_text(str(item))]
    refined_clients = [normalize_text(str(item)) for item in (refined.get("clients", []) or []) if normalize_text(str(item))]
    if base_clients:
        clients = _dedupe_strings(
            [
                *base_clients,
                *[
                    item
                    for item in refined_clients
                    if any(base_client in item or item in base_client for base_client in base_clients)
                ],
            ],
            3,
        )
    else:
        clients = _dedupe_strings(refined_clients, 3)

    base_company_anchors = [
        normalize_text(str(item))
        for item in (base.get("company_anchors", []) or [])
        if normalize_text(str(item))
    ]
    refined_company_anchors = [
        normalize_text(str(item))
        for item in (refined.get("company_anchors", []) or [])
        if normalize_text(str(item))
    ]
    if base_company_anchors:
        company_anchors = _dedupe_strings(
            [
                *base_company_anchors,
                *[
                    item
                    for item in refined_company_anchors
                    if any(anchor in item or item in anchor for anchor in base_company_anchors)
                ],
            ],
            4,
        )
    else:
        company_anchors = _dedupe_strings(refined_company_anchors, 4)
    strategy_must_include_terms = _dedupe_strings(
        [*(base.get("strategy_must_include_terms", []) or []), *(refined.get("strategy_must_include_terms", []) or [])],
        8,
    )
    strategy_exclusion_terms = _dedupe_strings(
        [*(base.get("strategy_exclusion_terms", []) or []), *(refined.get("strategy_exclusion_terms", []) or [])],
        8,
    )
    strategy_query_expansions = _dedupe_strings(
        [
            item
            for item in [*(base.get("strategy_query_expansions", []) or []), *(refined.get("strategy_query_expansions", []) or [])]
            if normalize_text(str(item))
            and not any(exclusion in normalize_text(str(item)) for exclusion in strategy_exclusion_terms)
        ],
        10,
    )
    strategy_scope_summary = normalize_text(str(refined.get("strategy_scope_summary", ""))) or normalize_text(
        str(base.get("strategy_scope_summary", ""))
    )
    prefer_company_entities = bool(base.get("prefer_company_entities")) or bool(refined.get("prefer_company_entities"))
    prefer_head_companies = bool(base.get("prefer_head_companies")) or bool(refined.get("prefer_head_companies"))
    seed_companies = _dedupe_strings(
        [
            normalize_text(str(item))
            for item in [*(base.get("seed_companies", []) or []), *(refined.get("seed_companies", []) or [])]
            if normalize_text(str(item))
        ],
        12,
    )
    industry_methodology_profile = normalize_text(str(refined.get("industry_methodology_profile", ""))) or normalize_text(
        str(base.get("industry_methodology_profile", ""))
    )
    industry_methodology_authority = normalize_text(str(refined.get("industry_methodology_authority", ""))) or normalize_text(
        str(base.get("industry_methodology_authority", ""))
    )
    industry_methodology_framework = normalize_text(str(refined.get("industry_methodology_framework", ""))) or normalize_text(
        str(base.get("industry_methodology_framework", ""))
    )
    industry_methodology_questions = _dedupe_strings(
        [*(base.get("industry_methodology_questions", []) or []), *(refined.get("industry_methodology_questions", []) or [])],
        6,
    )
    industry_methodology_source_preferences = _dedupe_strings(
        [
            *(base.get("industry_methodology_source_preferences", []) or []),
            *(refined.get("industry_methodology_source_preferences", []) or []),
        ],
        6,
    )
    industry_methodology_solution_lenses = _dedupe_strings(
        [
            *(base.get("industry_methodology_solution_lenses", []) or []),
            *(refined.get("industry_methodology_solution_lenses", []) or []),
        ],
        6,
    )
    industry_methodology_sales_lenses = _dedupe_strings(
        [
            *(base.get("industry_methodology_sales_lenses", []) or []),
            *(refined.get("industry_methodology_sales_lenses", []) or []),
        ],
        6,
    )
    industry_methodology_bidding_lenses = _dedupe_strings(
        [
            *(base.get("industry_methodology_bidding_lenses", []) or []),
            *(refined.get("industry_methodology_bidding_lenses", []) or []),
        ],
        6,
    )
    industry_methodology_outreach_lenses = _dedupe_strings(
        [
            *(base.get("industry_methodology_outreach_lenses", []) or []),
            *(refined.get("industry_methodology_outreach_lenses", []) or []),
        ],
        6,
    )
    industry_methodology_ecosystem_lenses = _dedupe_strings(
        [
            *(base.get("industry_methodology_ecosystem_lenses", []) or []),
            *(refined.get("industry_methodology_ecosystem_lenses", []) or []),
        ],
        6,
    )
    anchor_text = normalize_text(" / ".join(regions[:2] + industries[:2] + clients[:2]))
    if not anchor_text:
        anchor_text = normalize_text(str(refined.get("anchor_text", ""))) or normalize_text(str(base.get("anchor_text", "")))
    return {
        "regions": regions,
        "industries": industries,
        "clients": clients,
        "company_anchors": company_anchors,
        "prefer_company_entities": prefer_company_entities,
        "prefer_head_companies": prefer_head_companies,
        "seed_companies": seed_companies,
        "strategy_must_include_terms": strategy_must_include_terms,
        "strategy_exclusion_terms": strategy_exclusion_terms,
        "strategy_query_expansions": strategy_query_expansions,
        "strategy_scope_summary": strategy_scope_summary,
        "anchor_text": anchor_text,
        "industry_methodology_profile": industry_methodology_profile,
        "industry_methodology_authority": industry_methodology_authority,
        "industry_methodology_framework": industry_methodology_framework,
        "industry_methodology_questions": industry_methodology_questions,
        "industry_methodology_source_preferences": industry_methodology_source_preferences,
        "industry_methodology_solution_lenses": industry_methodology_solution_lenses,
        "industry_methodology_sales_lenses": industry_methodology_sales_lenses,
        "industry_methodology_bidding_lenses": industry_methodology_bidding_lenses,
        "industry_methodology_outreach_lenses": industry_methodology_outreach_lenses,
        "industry_methodology_ecosystem_lenses": industry_methodology_ecosystem_lenses,
    }


def _build_theme_terms(
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
) -> list[str]:
    terms = _extract_topic_anchor_terms(keyword, research_focus or "")
    for label in scope_hints.get("industries", []) or []:
        normalized = normalize_text(str(label))
        if not normalized:
            continue
        terms.append(normalized)
        for alias in INDUSTRY_SCOPE_ALIASES.get(normalized, ()):
            terms.append(alias)
    for item in scope_hints.get("strategy_must_include_terms", []) or []:
        normalized = normalize_text(str(item))
        if normalized:
            terms.append(normalized)
    for region in scope_hints.get("regions", []) or []:
        normalized = normalize_text(str(region))
        if normalized:
            terms.append(normalized)
    return list(dict.fromkeys(term.lower() for term in terms if len(normalize_text(term)) >= 2))


def _build_strict_theme_terms(scope_hints: dict[str, object]) -> list[str]:
    terms = [
        normalize_text(str(item)).lower()
        for item in scope_hints.get("strategy_must_include_terms", []) or []
        if normalize_text(str(item))
    ]
    return list(dict.fromkeys(terms))


def _research_result_needs_override(result: ResearchReportResult) -> bool:
    title = normalize_text(result.report_title).lower()
    summary = normalize_text(result.executive_summary).lower()
    generic_title_tokens = {
        "研究主题待确认",
        "研究主題待確認",
        "research topic pending",
    }
    return (
        title in generic_title_tokens
        or _looks_like_insufficient(summary)
        or len(_concrete_rows(result.target_accounts)) < 2
        or len(_concrete_rows(result.competitor_profiles)) < 2
    )


def _looks_like_bad_report_title(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return True
    lowered = normalized.lower()
    if re.match(r"^(19|20)\d{2}", normalized):
        return True
    if len(normalized) > 42:
        return True
    if any(token in normalized for token in ENTITY_INVALID_PHRASE_TOKENS):
        return True
    if any(token in normalized for token in ("当前证据不足", "当前證據不足", "建议", "建議", "报告", "研报", "研究主题待确认")):
        return True
    if lowered.startswith(("本次", "当前", "建议", "research", "report")):
        return True
    if normalized.count("：") > 1 or normalized.count(":") > 1:
        return True
    if any(token in normalized for token in ("社区", "服务", "系统")) and not any(token in normalized for token in ("公司", "集团", "中心", "平台", "场景", "赛道")):
        return True
    return False


def _is_theme_aligned_report_title(
    value: str,
    *,
    scope_hints: dict[str, object],
    keyword: str,
    research_focus: str | None,
) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return False
    theme_labels = _theme_labels_from_scope(scope_hints, keyword=keyword, research_focus=research_focus)
    if not theme_labels:
        return True
    scope_text = normalize_text(" ".join([keyword, research_focus or "", str(scope_hints.get("anchor_text", ""))]))
    for theme_label in theme_labels:
        blocked_tokens = THEME_ENTITY_BLOCK_TOKENS.get(theme_label, {}).get("target", ())
        if any(token in normalized for token in blocked_tokens) and not any(token in scope_text for token in blocked_tokens):
            return False
    return True


TITLE_SCOPE_GENERIC_TOKENS = (
    "相关商机",
    "潛在商機",
    "潜在商机",
    "市场机会",
    "市場機會",
    "机会分析",
    "機會分析",
    "解决方案",
    "解決方案",
    "研究",
    "研报",
    "報告",
    "报告",
)

SCENARIO_PRIORITY_TOKENS = (
    "漫剧",
    "短剧",
    "动画",
    "動漫",
    "内容",
    "內容",
    "政务服务",
    "政務服務",
    "政务云",
    "政務雲",
    "数据中心",
    "數據中心",
    "采购",
    "採購",
    "招标",
    "標案",
    "预算",
    "預算",
    "平台",
    "场景",
    "場景",
)

TITLE_STAGE_LABELS = (
    ("四期", "扩容窗口"),
    ("三期", "扩容窗口"),
    ("二期", "扩容窗口"),
    ("扩容", "扩容窗口"),
    ("中标", "交付窗口"),
    ("開標", "招标窗口"),
    ("开标", "招标窗口"),
    ("招标", "招标窗口"),
    ("立项", "立项窗口"),
    ("試點", "试点切入"),
    ("试点", "试点切入"),
    ("预算", "预算窗口"),
)


def _sanitize_title_scope_token(value: str) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    if _looks_like_scope_prompt_noise(normalized):
        return ""
    if _looks_like_fragment_entity_name(normalized) or _contains_low_value_entity_token(normalized):
        return ""
    compact = normalized
    for prefix in ("优先关注", "優先關注", "重点关注", "重點關注", "锁定", "鎖定"):
        if compact.startswith(prefix):
            compact = normalize_text(compact[len(prefix) :])
    for token in TITLE_SCOPE_GENERIC_TOKENS:
        compact = compact.replace(token, "")
    compact = re.sub(r"(?:19|20)\d{2}年?", "", compact)
    compact = re.sub(r"[：:|｜/]+$", "", compact)
    compact = re.sub(r"\s+", "", compact)
    compact = _strip_entity_leading_noise(compact)
    if (
        not compact
        or compact in GENERIC_FOCUS_TOKENS
        or _looks_like_placeholder_entity_name(compact)
        or any(token in compact for token in GENERIC_SCOPE_CLIENT_TOKENS)
    ):
        return ""
    if len(compact) > 18:
        return ""
    return compact


def _theme_labels_from_scope(
    scope_hints: dict[str, object],
    *,
    keyword: str,
    research_focus: str | None,
) -> list[str]:
    labels = [
        normalize_text(str(item))
        for item in scope_hints.get("industries", []) or []
        if normalize_text(str(item))
    ]
    lowered_terms = " ".join(_extract_topic_anchor_terms(keyword, research_focus)).lower()
    if any(token in lowered_terms for token in ("ai漫剧", "漫剧", "ai短剧", "aigc动画", "动漫短剧", "漫画短剧")):
        labels.append("AI漫剧")
    if any(token in lowered_terms for token in ("政务云", "数字政府", "政务")):
        labels.append("政务云")
    return _dedupe_strings(labels, 3)


def _infer_company_query_preferences(
    seed_text: str,
    *,
    theme_labels: list[str],
) -> tuple[bool, bool]:
    lowered = normalize_text(seed_text).lower()
    prefer_company_entities = any(token in lowered for token in COMPANY_ENTITY_QUERY_TOKENS)
    prefer_head_companies = prefer_company_entities and any(token in lowered for token in HEAD_COMPANY_QUERY_TOKENS)
    if not prefer_company_entities and "AI漫剧" in theme_labels:
        prefer_company_entities = any(
            token in lowered
            for token in ("发行方", "版权方", "平台方", "工作室", "内容平台", "短剧平台", "动漫平台")
        )
    return prefer_company_entities, prefer_head_companies


def _is_theme_aligned_entity_name(
    value: str,
    *,
    role: str,
    theme_labels: list[str],
) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return False
    if not theme_labels:
        return True
    for theme_label in theme_labels:
        if normalized in THEME_COMPANY_PUBLIC_SOURCE_SEEDS.get(theme_label, ()):
            return True
        allow_tokens = THEME_ENTITY_ALLOW_TOKENS.get(theme_label, {}).get(role, ())
        block_tokens = THEME_ENTITY_BLOCK_TOKENS.get(theme_label, {}).get(role, ())
        if any(token in normalized for token in block_tokens):
            return False
        if any(token in normalized for token in allow_tokens):
            return True
    return not any(
        token in normalized
        for theme_label in theme_labels
        for token in THEME_ENTITY_BLOCK_TOKENS.get(theme_label, {}).get(role, ())
    )


def _filter_theme_aligned_rows(
    values: Iterable[str],
    *,
    role: str,
    theme_labels: list[str],
    scope_hints: dict[str, object],
) -> list[str]:
    filtered: list[str] = []
    seed_companies = [
        normalize_text(str(item))
        for item in (scope_hints.get("seed_companies", []) or [])
        if normalize_text(str(item))
    ]
    prefer_company_entities = bool(scope_hints.get("prefer_company_entities"))
    for value in values:
        normalized = normalize_text(value)
        if not normalized:
            continue
        entity_name = _extract_rank_entity_name(normalized) or _fallback_entity_name_from_row(normalized) or normalized
        if not _is_theme_aligned_entity_name(entity_name, role=role, theme_labels=theme_labels):
            continue
        if prefer_company_entities and role in {"target", "competitor"} and not _is_company_like_entity_name(
            entity_name,
            role=role,
            theme_labels=theme_labels,
            seed_companies=seed_companies,
        ):
            continue
        filtered.append(normalized)
    return _dedupe_strings(filtered, 6)


def _is_company_like_entity_name(
    value: str,
    *,
    role: str,
    theme_labels: list[str],
    seed_companies: list[str],
) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return False
    if normalized in seed_companies or _is_lightweight_entity_name(normalized) or normalized in SPECIAL_ENTITY_ALIASES:
        return True
    if any(
        token in normalized
        for token in ("政府", "市委", "市政府", "局", "委", "办", "中心", "大学", "学院", "学校", "医院", "银行", "证券")
    ):
        return False
    theme_company_tokens = [
        token
        for label in theme_labels
        for token in THEME_ENTITY_ALLOW_TOKENS.get(label, {}).get(role, ())
        if normalize_text(token) and token not in {"内容", "运营", "服务"}
    ]
    return any(token in normalized for token in [*GENERIC_COMPANY_NAME_TOKENS, *theme_company_tokens])


def _filtered_rank_fallback_values(
    values: Iterable[str],
    *,
    role: str,
    scope_hints: dict[str, object],
) -> list[str]:
    theme_labels = [
        normalize_text(str(item))
        for item in scope_hints.get("industries", []) or []
        if normalize_text(str(item))
    ]
    seed_companies = [
        normalize_text(str(item))
        for item in scope_hints.get("seed_companies", []) or []
        if normalize_text(str(item))
    ]
    prefer_company_entities = bool(scope_hints.get("prefer_company_entities"))
    candidates: list[str] = []
    for value in values:
        normalized = normalize_text(str(value))
        if (
            not normalized
            or _looks_like_insufficient(normalized)
            or _looks_like_source_artifact_text(normalized)
            or _looks_like_scope_prompt_noise(normalized)
        ):
            continue
        extracted = _extract_rank_entity_candidates(normalized, scope_hints=scope_hints)
        fallback = _fallback_entity_name_from_row(normalized)
        for candidate in [*extracted, *([fallback] if fallback else [])]:
            compact = _resolve_known_org_name(candidate, scope_hints=scope_hints)
            compact = _strip_entity_leading_noise(compact)
            if (
                not compact
                or _looks_like_fragment_entity_name(compact)
                or _contains_low_value_entity_token(compact)
                or _looks_like_placeholder_entity_name(compact)
                or _looks_like_scope_prompt_noise(compact)
            ):
                continue
            if theme_labels and not _is_theme_aligned_entity_name(compact, role=role, theme_labels=theme_labels):
                continue
            if prefer_company_entities and role in {"target", "competitor"} and not _is_company_like_entity_name(
                compact,
                role=role,
                theme_labels=theme_labels,
                seed_companies=seed_companies,
            ):
                continue
            candidates.append(compact)
    return _dedupe_strings(candidates, 12)


def _source_supports_company_intent(
    source: SourceDocument,
    *,
    theme_labels: list[str],
    seed_companies: list[str],
) -> bool:
    text = _source_text(source)
    normalized_text = normalize_text(text)
    title = normalize_text(source.title)
    domain = normalize_text(source.domain or "").lower()
    if any(company and company in normalized_text for company in seed_companies):
        return True
    if any(
        token in normalized_text
        for token in (
            "官网",
            "官網",
            "投资者关系",
            "投資者關係",
            "联系我们",
            "聯絡我們",
            "商务合作",
            "商務合作",
            "商业化",
            "商業化",
            "发行",
            "發行",
            "版权",
            "版權",
            "IP",
        )
    ):
        return True
    blocked_tokens = {
        token
        for label in theme_labels
        for token in THEME_ENTITY_BLOCK_TOKENS.get(label, {}).get("target", ())
        if normalize_text(token)
    }
    if blocked_tokens and any(token in title for token in blocked_tokens) and not any(token in title for token in GENERIC_COMPANY_NAME_TOKENS):
        return False
    if source.source_tier == "official" and domain and not any(
        token in domain for token in ("gov.cn", "ggzy.gov.cn", "ccgp.gov.cn", "cninfo.com.cn", "hkexnews.hk", "mp.weixin.qq.com")
    ):
        return True
    if any(token in title for token in GENERIC_COMPANY_NAME_TOKENS):
        return True
    theme_company_tokens = [
        token
        for label in theme_labels
        for token in THEME_ENTITY_ALLOW_TOKENS.get(label, {}).get("target", ())
        if normalize_text(token) and token not in {"内容", "內容", "运营", "運營", "服务", "服務"}
    ]
    if any(token in title for token in theme_company_tokens):
        return True
    return any(
        _is_company_like_entity_name(
            candidate,
            role="target",
            theme_labels=theme_labels,
            seed_companies=seed_companies,
        )
        for candidate in _extract_rank_entity_candidates(normalized_text)[:6]
    )


def _pick_primary_stage_phrase(stage_rows: Iterable[str]) -> str:
    for row in stage_rows:
        normalized = normalize_text(row)
        if not normalized:
            continue
        for token, label in TITLE_STAGE_LABELS:
            if token in normalized:
                return label
    return ""


def _pick_primary_scenario_hint(
    *,
    keyword: str,
    research_focus: str | None,
    regions: list[str],
    industries: list[str],
    company_anchors: list[str],
) -> str:
    candidates: list[tuple[int, int, str]] = []
    region_set = {normalize_text(item) for item in regions}
    industry_set = {normalize_text(item) for item in industries}
    company_set = {normalize_text(item) for item in company_anchors}
    for token in _extract_topic_anchor_terms(keyword, research_focus):
        normalized = _sanitize_title_scope_token(token)
        if not normalized:
            continue
        if normalized in region_set or normalized in industry_set or normalized in company_set:
            continue
        score = min(len(normalized), 10)
        if any(priority in normalized for priority in SCENARIO_PRIORITY_TOKENS):
            score += 8
        if any(theme in normalized for theme in ("AI", "AIGC", "政务", "內容", "内容", "采购", "招标", "预算", "交付")):
            score += 3
        candidates.append((score, len(normalized), normalized))
    if not candidates:
        return ""
    candidates.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return candidates[0][2]


def _compress_title_segments(segments: Iterable[str], *, limit: int = 3) -> list[str]:
    cleaned: list[str] = []
    for item in segments:
        normalized = _sanitize_title_scope_token(item)
        if not normalized:
            continue
        if normalized in cleaned:
            continue
        cleaned.append(normalized)
        if len(cleaned) >= limit:
            break
    return cleaned


def _scope_anchor_text_segments(value: str | None) -> list[str]:
    normalized = normalize_text(value or "")
    if not normalized:
        return []
    return [
        normalize_text(part)
        for part in re.split(r"[|｜/／]+", normalized)
        if normalize_text(part)
    ]


def _build_report_title_suffix(
    *,
    intelligence: dict[str, list[str]],
    selected_company_anchor: str,
    stage_hint: str,
    output_language: str,
) -> str:
    budget_rows = _summary_fact_rows(intelligence.get("budget_signals", []), limit=2)
    timeline_rows = _summary_fact_rows(
        [*intelligence.get("tender_timeline", []), *intelligence.get("project_distribution", [])],
        limit=2,
    )
    competitor_rows = _entity_display_labels(intelligence.get("competitor_profiles", []), limit=2)
    partner_rows = _entity_display_labels(intelligence.get("ecosystem_partners", []), limit=2)
    target_rows = _entity_display_labels(intelligence.get("target_accounts", []), limit=2)
    if stage_hint:
        suffix = f"{stage_hint}与推进路径"
    elif budget_rows and (competitor_rows or partner_rows):
        suffix = "预算信号与切入策略"
    elif competitor_rows or partner_rows:
        suffix = "竞争格局与切入策略"
    elif selected_company_anchor or target_rows:
        suffix = "账户优先级与推进路径"
    elif budget_rows or timeline_rows:
        suffix = "进入窗口与推进路径"
    else:
        suffix = "重点机会与推进路径"
    return localized_text(
        output_language,
        {
            "zh-CN": suffix,
            "zh-TW": suffix.replace("与", "與"),
            "en": (
                "Entry Window & Execution Path"
                if suffix in {"扩容窗口与推进路径", "交付窗口与推进路径", "招标窗口与推进路径", "立项窗口与推进路径", "试点切入与推进路径", "预算窗口与推进路径", "进入窗口与推进路径"}
                else "Budget Signals & Entry Strategy"
                if suffix == "预算信号与切入策略"
                else "Competition Landscape & Entry Strategy"
                if suffix == "竞争格局与切入策略"
                else "Account Priorities & Execution Path"
                if suffix == "账户优先级与推进路径"
                else "Priority Opportunities & Execution Path"
            ),
        },
        suffix,
    )


def _build_exec_summary_override(
    *,
    scope_anchor: str,
    accounts: list[str],
    budgets: list[str],
    competitors: list[str],
    partners: list[str],
    teams: list[str],
    output_language: str,
) -> str:
    conclusion_subject = "、".join(accounts[:2]) if accounts else scope_anchor
    budget_anchor = next((item for item in budgets if _is_actionable_budget_row(item)), "")
    team_anchor = teams[0] if teams else ""
    competitor_anchor = competitors[0] if competitors else ""
    partner_anchor = partners[0] if partners else ""
    if accounts and budget_anchor:
        conclusion_line = f"优先把{conclusion_subject}列为首批推进对象，当前公开信号已经出现{budget_anchor}这类预算或采购窗口。"
    elif accounts:
        conclusion_line = f"优先把{conclusion_subject}列为首批推进对象，先确认预算归口、业务牵头部门和进入窗口。"
    elif budget_anchor:
        conclusion_line = f"当前更适合围绕{scope_anchor}继续收敛到具体账户，尤其优先核验{budget_anchor}对应的项目窗口。"
    else:
        conclusion_line = f"当前应先把{scope_anchor}收敛到 1-2 个可验证账户，再进入更强的商业判断。"
    evidence_parts = _dedupe_strings(
        [
            budget_anchor,
            team_anchor,
            f"竞品侧出现 {competitor_anchor}" if competitor_anchor else "",
            f"伙伴侧可借力 {partner_anchor}" if partner_anchor else "",
        ],
        3,
    )
    evidence_line = (
        f"公开证据目前主要集中在{'、'.join(evidence_parts)}。"
        if evidence_parts
        else "公开证据目前主要集中在范围锁定、账户筛选和进入窗口判断。"
    )
    action_parts: list[str] = []
    if accounts:
        if team_anchor:
            action_parts.append(f"先围绕{conclusion_subject}核验{team_anchor}是否是业务或预算牵头团队")
        else:
            action_parts.append(f"先围绕{conclusion_subject}补业务牵头部门和预算归口")
    else:
        action_parts.append("先把主题收敛到 1-2 个可验证账户，再补预算归口和组织入口")
    if budget_anchor:
        action_parts.append(f"围绕“{budget_anchor}”倒排会前材料和拜访节奏")
    elif team_anchor:
        action_parts.append(f"从{team_anchor}对应的公开入口补联系人与会前材料")
    if competitor_anchor and partner_anchor:
        action_parts.append(f"准备针对{competitor_anchor}的差异化切口，并评估{partner_anchor}是否适合牵线")
    elif competitor_anchor:
        action_parts.append(f"准备针对{competitor_anchor}的差异化切口")
    elif partner_anchor:
        action_parts.append(f"评估{partner_anchor}是否适合作为牵线或联合推进伙伴")
    action_parts.append("把研判拆成两条主线：方案侧先定义场景、试点与扩容路径，打单侧先锁定账户、部门、预算与伙伴节奏")
    action_line = "；".join(_dedupe_strings(action_parts, 3)) or "先锁定重点账户，再补预算归口、组织入口和首轮沟通材料。"
    if output_language.startswith("en"):
        return (
            f"Prioritize {conclusion_subject} as the first execution target within {scope_anchor}. "
            f"The strongest public signals currently cluster around {', '.join(evidence_parts) if evidence_parts else 'account scoping, buyer qualification, and entry timing'}. "
            f"The next step is to {action_line.rstrip('.')}."
        )
    return f"{conclusion_line}{evidence_line}下一步建议{action_line.rstrip('。')}。"


def _build_scope_summary_sentence(
    *,
    scope_anchor: str,
    accounts: list[str],
    budgets: list[str],
    competitors: list[str],
    partners: list[str],
    teams: list[str],
    output_language: str,
) -> str:
    clauses: list[str] = [
        localized_text(
            output_language,
            {
                "zh-CN": f"本次研判锁定在 {scope_anchor} 范围内",
                "zh-TW": f"本次研判鎖定在 {scope_anchor} 範圍內",
                "en": f"This memo is constrained to {scope_anchor}",
            },
            f"本次研判锁定在 {scope_anchor} 范围内",
        )
    ]
    if accounts:
        clauses.append(localized_text(output_language, {"zh-CN": f"甲方线索优先收敛到 {'、'.join(accounts[:2])}", "zh-TW": f"甲方線索優先收斂到 {'、'.join(accounts[:2])}", "en": f"buyer-side leads converge around {' / '.join(accounts[:2])}"}, f"甲方线索优先收敛到 {'、'.join(accounts[:2])}"))
    if budgets:
        clauses.append(localized_text(output_language, {"zh-CN": f"预算与采购信号集中在 {'、'.join(budgets[:2])}", "zh-TW": f"預算與採購信號集中在 {'、'.join(budgets[:2])}", "en": f"budget and procurement signals cluster around {' / '.join(budgets[:2])}"}, f"预算与采购信号集中在 {'、'.join(budgets[:2])}"))
    if competitors:
        clauses.append(localized_text(output_language, {"zh-CN": f"高相关竞合对象包括 {'、'.join(competitors[:2])}", "zh-TW": f"高相關競合對象包括 {'、'.join(competitors[:2])}", "en": f"high-relevance competitors include {' / '.join(competitors[:2])}"}, f"高相关竞合对象包括 {'、'.join(competitors[:2])}"))
    if partners:
        clauses.append(localized_text(output_language, {"zh-CN": f"可用生态抓手集中在 {'、'.join(partners[:2])}", "zh-TW": f"可用生態抓手集中在 {'、'.join(partners[:2])}", "en": f"ecosystem leverage points include {' / '.join(partners[:2])}"}, f"可用生态抓手集中在 {'、'.join(partners[:2])}"))
    if teams:
        clauses.append(localized_text(output_language, {"zh-CN": f"活跃团队线索包括 {'、'.join(teams[:2])}", "zh-TW": f"活躍團隊線索包括 {'、'.join(teams[:2])}", "en": f"active team signals include {' / '.join(teams[:2])}"}, f"活跃团队线索包括 {'、'.join(teams[:2])}"))
    sentence = "，".join(clauses)
    if output_language.startswith("en"):
        return sentence + "."
    return sentence + "。"


def _select_title_company_anchor(
    company_anchors: list[str],
    *,
    scope_hints: dict[str, object],
    keyword: str,
    research_focus: str | None,
) -> str:
    theme_labels = _theme_labels_from_scope(scope_hints, keyword=keyword, research_focus=research_focus)
    if not company_anchors:
        return ""
    for candidate in company_anchors:
        normalized = normalize_text(candidate)
        if not normalized:
            continue
        if not _is_theme_aligned_entity_name(normalized, role="target", theme_labels=theme_labels):
            continue
        return normalized
    return ""


def _build_report_title_override(
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
    intelligence: dict[str, list[str]],
    output_language: str,
) -> str:
    regions = _dedupe_strings([normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))], 2)
    industries = _dedupe_strings([normalize_text(str(item)) for item in scope_hints.get("industries", []) if normalize_text(str(item))], 2)
    theme_labels = _theme_labels_from_scope(scope_hints, keyword=keyword, research_focus=research_focus)
    company_anchors = _clean_scope_entity_names(
        [
            *[_extract_rank_entity_name(item) for item in intelligence.get("target_accounts", []) if _extract_rank_entity_name(item)],
            *[normalize_text(str(item)) for item in scope_hints.get("company_anchors", []) if normalize_text(str(item))],
        ],
        limit=4,
        theme_labels=theme_labels,
    )
    company_anchors = [
        item
        for item in company_anchors
        if normalize_text(item)
        and not _looks_like_fragment_entity_name(item)
        and not _contains_low_value_entity_token(item)
        and (
            item in KNOWN_LIGHTWEIGHT_ENTITY_NAMES
            or any(token in item for token in ENTITY_SUFFIX_TOKENS)
            or any(token in item for token in ("集团", "公司", "平台", "银行", "大学", "医院", "中心", "局", "委", "办"))
        )
    ]
    selected_company_anchor = _select_title_company_anchor(
        company_anchors,
        scope_hints=scope_hints,
        keyword=keyword,
        research_focus=research_focus,
    )
    stage_rows = _dedupe_strings(
        [
            *[normalize_text(item) for item in intelligence.get("tender_timeline", []) if normalize_text(item)],
            *[normalize_text(item) for item in intelligence.get("project_distribution", []) if normalize_text(item)],
        ],
        2,
    )
    stage_hint = _pick_primary_stage_phrase(stage_rows)
    scenario_hint = _pick_primary_scenario_hint(
        keyword=keyword,
        research_focus=research_focus,
        regions=regions,
        industries=industries,
        company_anchors=company_anchors,
    )
    scope_segments = _compress_title_segments(
        [
            *regions[:1],
            scenario_hint or (industries[0] if industries else ""),
            selected_company_anchor,
        ],
        limit=3,
    )
    if not scope_segments:
        scope_segments = _compress_title_segments(
            [
                normalize_text(str(scope_hints.get("anchor_text", ""))),
                normalize_text(research_focus or ""),
                normalize_text(keyword),
            ],
            limit=3,
        )
    title_scope = "｜".join(scope_segments)
    if not title_scope:
        title_scope = normalize_text(keyword)
    suffix = _build_report_title_suffix(
        intelligence=intelligence,
        selected_company_anchor=selected_company_anchor,
        stage_hint=stage_hint,
        output_language=output_language,
    )
    return localized_text(
        output_language,
        {
            "zh-CN": f"{title_scope}：{suffix}",
            "zh-TW": f"{title_scope}：{suffix}",
            "en": f"{title_scope}: {suffix}",
        },
        f"{title_scope}：{suffix}",
    )


def _apply_topic_specific_overrides(
    result: ResearchReportResult,
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    scope_hints: dict[str, object],
    intelligence: dict[str, list[str]],
) -> ResearchReportResult:
    payload = result.model_dump(mode="python")
    theme_labels = _theme_labels_from_scope(scope_hints, keyword=keyword, research_focus=research_focus)
    if theme_labels:
        for field_key, role in (
            ("target_accounts", "target"),
            ("competitor_profiles", "competitor"),
            ("ecosystem_partners", "partner"),
            ("client_peer_moves", "target"),
            ("winner_peer_moves", "competitor"),
        ):
            payload[field_key] = _filter_theme_aligned_rows(
                payload.get(field_key, []),
                role=role,
                theme_labels=theme_labels,
                scope_hints=scope_hints,
            )
    scope_anchor = normalize_text(str(scope_hints.get("anchor_text", ""))) or normalize_text(research_focus or "") or keyword
    accounts = _entity_display_labels(payload.get("target_accounts", []) or intelligence.get("target_accounts", []), limit=2)
    budgets = _summary_fact_rows(
        [item for item in intelligence.get("budget_signals", []) if _is_actionable_budget_row(item)],
        limit=2,
    )
    competitors = _entity_display_labels(payload.get("competitor_profiles", []) or intelligence.get("competitor_profiles", []), limit=2)
    partners = _entity_display_labels(payload.get("ecosystem_partners", []) or intelligence.get("ecosystem_partners", []), limit=2)
    teams = _summary_fact_rows(payload.get("account_team_signals", []) or intelligence.get("account_team_signals", []), limit=2)
    original_summary = normalize_text(result.executive_summary)
    original_consulting_angle = normalize_text(result.consulting_angle)
    needs_override = _research_result_needs_override(result) or _company_intent_summary_needs_override(
        scope_hints=scope_hints,
        summary=original_summary,
        accounts=accounts,
        competitors=competitors,
    ) or _summary_contains_output_noise(original_summary)

    payload["report_title"] = _build_report_title_override(
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
        intelligence=intelligence,
        output_language=output_language,
    )

    summary_rows = [
        _build_scope_summary_sentence(
            scope_anchor=scope_anchor,
            accounts=accounts,
            budgets=budgets,
            competitors=competitors,
            partners=partners,
            teams=teams,
            output_language=output_language,
        )
    ]
    if accounts and budgets:
        summary_rows.append(localized_text(output_language, {"zh-CN": "研判重点应先围绕甲方收敛、预算口径和采购节奏同步推进，而不是泛泛讨论赛道趋势。", "zh-TW": "研判重點應先圍繞甲方收斂、預算口徑與採購節奏同步推進，而不是泛泛討論賽道趨勢。", "en": "The memo should prioritize buyer convergence, budget validation, and procurement timing instead of generic market commentary."}, "研判重点应先围绕甲方收敛、预算口径和采购节奏同步推进，而不是泛泛讨论赛道趋势。"))
    if competitors or partners:
        summary_rows.append(localized_text(output_language, {"zh-CN": "竞品与生态判断应优先服务于进入路径设计：谁在抢预算、谁适合合作、谁能帮助尽快触达甲方。", "zh-TW": "競品與生態判斷應優先服務於進入路徑設計：誰在搶預算、誰適合合作、誰能幫助盡快觸達甲方。", "en": "Competition and ecosystem analysis should be used to shape the entry path: who is contesting budget, who is coopetition-ready, and who can accelerate buyer access."}, "竞品与生态判断应优先服务于进入路径设计：谁在抢预算、谁适合合作、谁能帮助尽快触达甲方。"))
    if summary_rows:
        if needs_override or not original_summary or _looks_like_insufficient(original_summary) or _looks_like_bad_executive_summary(original_summary):
            payload["executive_summary"] = _build_exec_summary_override(
                scope_anchor=scope_anchor,
                accounts=accounts,
                budgets=budgets,
                competitors=competitors,
                partners=partners,
                teams=teams,
                output_language=output_language,
            )
        else:
            payload["executive_summary"] = original_summary

    consulting_angle_override = localized_text(
        output_language,
        {
            "zh-CN": f"建议围绕 {scope_anchor} 同时服务两类任务：方案设计上聚焦场景拆解、试点路径和扩容逻辑；打单策略上聚焦账户收敛、预算口径、竞品差异化和伙伴牵线。",
            "zh-TW": f"建議圍繞 {scope_anchor} 同時服務兩類任務：方案設計上聚焦場景拆解、試點路徑與擴容邏輯；打單策略上聚焦帳戶收斂、預算口徑、競品差異化與夥伴牽線。",
            "en": f"For {scope_anchor}, the memo should serve both solution design and deal strategy: use-case decomposition, pilot-to-scale logic, buyer targeting, budget validation, competitor differentiation, and partner-led access.",
        },
        f"建议围绕 {scope_anchor} 同时服务两类任务：方案设计上聚焦场景拆解、试点路径和扩容逻辑；打单策略上聚焦账户收敛、预算口径、竞品差异化和伙伴牵线。",
    )
    if needs_override or not original_consulting_angle or _looks_like_insufficient(original_consulting_angle):
        payload["consulting_angle"] = consulting_angle_override

    if not _concrete_rows(payload.get("key_signals", [])):
        payload["key_signals"] = _dedupe_strings(
            [*accounts[:1], *budgets[:1], *competitors[:1], *partners[:1]],
            4,
        )
    if not _concrete_rows(payload.get("commercial_opportunities", [])):
        payload["commercial_opportunities"] = _dedupe_strings(
            [*accounts[:2], *budgets[:2]],
            4,
        )
    if not _concrete_rows(payload.get("competition_analysis", [])):
        payload["competition_analysis"] = _dedupe_strings(
            [*competitors[:2], *partners[:1]],
            4,
        )
    if not _concrete_rows(payload.get("account_team_signals", [])):
        payload["account_team_signals"] = _dedupe_strings(teams, 4)

    return ResearchReportResult.model_validate(payload)


def _apply_strategy_scope_planning(
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    input_scope_hints: dict[str, object],
) -> dict[str, object]:
    strategy_llm = get_strategy_llm_service()
    if strategy_llm is None:
        return input_scope_hints

    try:
        raw = strategy_llm.run_prompt(
            "research_strategy_scope.txt",
            {
                "keyword": keyword,
                "research_focus": research_focus or "",
                "output_language": output_language,
                "scope_hints": json.dumps(input_scope_hints, ensure_ascii=False),
            },
        )
        planned = parse_research_strategy_scope_response(raw)
    except Exception:
        return input_scope_hints

    merged = _merge_scope_hints(
        input_scope_hints,
        {
            "regions": planned.locked_regions,
            "industries": planned.locked_industries,
            "clients": planned.locked_clients,
            "company_anchors": planned.company_anchors,
            "strategy_must_include_terms": planned.must_include_terms,
            "strategy_exclusion_terms": planned.must_exclude_terms,
            "strategy_query_expansions": planned.query_expansions,
            "strategy_scope_summary": planned.reasoning_summary,
        },
    )
    return merged


def _apply_strategy_llm_refinement(
    result: ResearchReportResult,
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    scope_hints: dict[str, object],
    intelligence: dict[str, list[str]],
) -> ResearchReportResult:
    strategy_llm = get_strategy_llm_service()
    if strategy_llm is None:
        return result

    current_report = {
        "report_title": result.report_title,
        "executive_summary": result.executive_summary,
        "consulting_angle": result.consulting_angle,
        "target_accounts": result.target_accounts[:4],
        "target_departments": result.target_departments[:4],
        "public_contact_channels": result.public_contact_channels[:4],
        "account_team_signals": result.account_team_signals[:4],
        "budget_signals": result.budget_signals[:4],
        "project_distribution": result.project_distribution[:4],
        "strategic_directions": result.strategic_directions[:4],
        "tender_timeline": result.tender_timeline[:4],
        "ecosystem_partners": result.ecosystem_partners[:4],
        "competitor_profiles": result.competitor_profiles[:4],
        "benchmark_cases": result.benchmark_cases[:4],
    }
    try:
        raw = strategy_llm.run_prompt(
            "research_strategy_refine.txt",
            {
                "keyword": keyword,
                "research_focus": research_focus or "",
                "output_language": output_language,
                "scope_hints": json.dumps(scope_hints, ensure_ascii=False),
                "source_intelligence": json.dumps(intelligence, ensure_ascii=False),
                "current_report": json.dumps(current_report, ensure_ascii=False),
            },
        )
        refined = parse_research_strategy_refine_response(raw)
    except Exception:
        return result

    payload = result.model_dump(mode="python")
    refined_title = normalize_text(refined.report_title)
    if refined_title and not _looks_like_bad_report_title(refined_title) and _is_theme_aligned_report_title(
        refined_title,
        scope_hints=scope_hints,
        keyword=keyword,
        research_focus=research_focus,
    ):
        payload["report_title"] = refined_title
    refined_summary = normalize_text(refined.executive_summary)
    if refined_summary and not _looks_like_bad_executive_summary(refined_summary):
        payload["executive_summary"] = normalize_text(refined.executive_summary)
    if normalize_text(refined.consulting_angle):
        payload["consulting_angle"] = normalize_text(refined.consulting_angle)
    if _looks_like_bad_report_title(str(payload.get("report_title", ""))):
        payload["report_title"] = _build_report_title_override(
            keyword=keyword,
            research_focus=research_focus,
            scope_hints=scope_hints,
            intelligence=intelligence,
            output_language=output_language,
        )
    return ResearchReportResult.model_validate(payload)


def _build_expanded_query_plan(
    keyword: str,
    research_focus: str | None,
    *,
    scope_hints: dict[str, object],
    include_wechat: bool,
    preferred_wechat_accounts: Iterable[str] | None = None,
    limit: int = 8,
) -> list[str]:
    keyword_seed = _strip_query_noise(keyword) or keyword
    regions = [normalize_text(item) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    industries = [normalize_text(item) for item in scope_hints.get("industries", []) if normalize_text(str(item))]
    clients = [normalize_text(item) for item in scope_hints.get("clients", []) if normalize_text(str(item))]
    focus = _sanitize_research_focus_text(research_focus)
    topic_anchors = _extract_topic_anchor_terms(keyword_seed, focus)
    expanded_regions = _expand_region_scope_terms(regions[:1])[:4]
    strategy_query_expansions = [
        normalize_text(str(item))
        for item in scope_hints.get("strategy_query_expansions", [])
        if normalize_text(str(item))
    ]
    scoped_official_queries = _build_scoped_official_query_expansions(
        keyword_seed,
        focus,
        scope_hints=scope_hints,
        include_wechat=include_wechat,
        limit=max(6, limit),
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
        for account in _dedupe_strings(preferred_wechat_accounts or [], 2):
            queries.append(f'site:mp.weixin.qq.com "{account}" {base}')
            if focus:
                queries.append(f'site:mp.weixin.qq.com "{account}" {base} {focus}')
    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized = normalize_text(query)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped[:limit]


def _build_company_contact_query_plan(
    company_names: list[str],
    *,
    keyword: str,
    research_focus: str | None,
    limit: int = 8,
) -> list[str]:
    queries: list[str] = []
    keyword_seed = _strip_query_noise(keyword) or normalize_text(keyword)
    focus_seed = _strip_query_noise(research_focus or "")
    for company in _dedupe_strings(company_names, 4):
        normalized = normalize_text(company)
        if not normalized or not _is_plausible_entity_name(normalized):
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
    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized = normalize_text(query)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped[:limit]


def _build_company_profile_query_plan(
    company_names: list[str],
    *,
    keyword: str,
    research_focus: str | None,
    limit: int = 8,
) -> list[str]:
    queries: list[str] = []
    keyword_seed = _strip_query_noise(keyword) or normalize_text(keyword)
    focus_seed = _strip_query_noise(research_focus or "")
    for company in _dedupe_strings(company_names, 4):
        normalized = normalize_text(company)
        if not normalized or not _is_plausible_entity_name(normalized):
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
    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized = normalize_text(query)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped[:limit]


def _build_company_team_query_plan(
    company_names: list[str],
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
    limit: int = 8,
) -> list[str]:
    queries: list[str] = []
    keyword_seed = _strip_query_noise(keyword) or normalize_text(keyword)
    focus_seed = _strip_query_noise(research_focus or "")
    region_terms = _expand_region_scope_terms(
        [normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    )
    industry_terms = [normalize_text(str(item)) for item in scope_hints.get("industries", []) if normalize_text(str(item))]
    for company in _dedupe_strings(company_names, 4):
        normalized = normalize_text(company)
        if not normalized or not _is_plausible_entity_name(normalized):
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
    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized = normalize_text(query)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped[:limit]


def _rank_org_rows(
    sources: list[SourceDocument],
    *,
    role: str,
    context_keywords: tuple[str, ...],
    preferred_source_types: tuple[str, ...],
    name_bias_tokens: tuple[str, ...],
    scope_hints: dict[str, object],
    theme_terms: list[str],
    limit: int,
) -> list[str]:
    scored: dict[str, tuple[int, str]] = {}
    scope_regions = [normalize_text(item) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    scope_clients = [normalize_text(item) for item in scope_hints.get("clients", []) if normalize_text(str(item))]
    scope_anchor = normalize_text(str(scope_hints.get("anchor_text", ""))).lower()

    for source in sources:
        text = _source_text(source)
        lowered = text.lower()
        title_text = normalize_text(source.title or "")
        label_text = normalize_text(source.source_label or "")
        if theme_terms and not any(term in lowered for term in theme_terms):
            continue
        for match in ORG_PATTERN.findall(text):
            name = normalize_text(match)
            if not _is_plausible_entity_name(name):
                continue
            if role == "target" and source.source_tier == "media":
                if not any(client in name for client in scope_clients) and not any(
                    token in name for token in ("政府", "局", "委", "办", "中心", "医院", "大学", "银行", "学校", "集团", "城投", "交投")
                ):
                    if not any(token in text for token in ("采购", "预算", "招标", "项目", "建设", "立项", "扩容")):
                        continue
            if role == "partner" and source.source_tier == "media":
                if not any(token in name for token in ("咨询", "顾问", "集成", "渠道", "联盟", "研究院", "研究所", "运营", "服务")):
                    if not any(token in text for token in ("合作", "伙伴", "联合", "联盟", "咨询", "顾问", "渠道", "集成")):
                        continue
            score = 1
            if any(token in text for token in context_keywords):
                score += 4
            if any(token in name for token in name_bias_tokens):
                score += 3
            if source.source_type in preferred_source_types:
                score += 3
            if source.source_tier == "official":
                score += 4
            elif source.source_tier == "aggregate":
                score += 2
            if any(client in name for client in scope_clients):
                score += 4
            if any(client and (client in title_text or client in label_text or client in text) for client in scope_clients):
                score += 3
            if any(region in text for region in scope_regions):
                score += 2
            if scope_anchor and scope_anchor in lowered:
                score += 1
            row = f"{name}：{_truncate_text(source.title or source.snippet or source.excerpt, 88)}"
            current = scored.get(name)
            if current is None or score > current[0]:
                scored[name] = (score, row)

    ordered = sorted(scored.items(), key=lambda item: (-item[1][0], item[0]))
    return [row for _, (_, row) in ordered[:limit]]


def _extract_key_people_rows(
    sources: list[SourceDocument],
    *,
    scope_hints: dict[str, object],
    limit: int,
) -> list[str]:
    scored: dict[str, tuple[int, str]] = {}
    scope_regions = [normalize_text(item) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    for source in sources:
        text = _source_text(source)
        for name, role in PERSON_ROLE_PATTERN.findall(text):
            person = normalize_text(name)
            if len(person) < 2:
                continue
            score = 1
            if source.source_type in {"policy", "procurement", "filing"}:
                score += 2
            if any(region in text for region in scope_regions):
                score += 1
            row = f"{person}{role}：{_truncate_text(source.title or source.snippet, 88)}"
            current = scored.get(person)
            if current is None or score > current[0]:
                scored[person] = (score, row)
    ordered = sorted(scored.items(), key=lambda item: (-item[1][0], item[0]))
    return [row for _, (_, row) in ordered[:limit]]


def _extract_department_rows(
    sources: list[SourceDocument],
    *,
    scope_hints: dict[str, object],
    limit: int,
) -> list[str]:
    scored: dict[str, tuple[int, str]] = {}
    scope_regions = [normalize_text(item) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    for source in sources:
        text = _source_text(source)
        lowered = text.lower()
        for match in DEPARTMENT_PATTERN.findall(text):
            department = normalize_text(match)
            if len(department) < 3:
                continue
            score = 1
            if source.source_type in {"procurement", "policy", "filing", "official_tender_feed", "official_policy_speech"}:
                score += 2
            if any(region in text for region in scope_regions):
                score += 1
            if any(token in lowered for token in ("预算", "招标", "采购", "规划", "信息化", "数字化")):
                score += 1
            row = f"{department}：{_truncate_text(source.title or source.snippet, 92)}"
            current = scored.get(department)
            if current is None or score > current[0]:
                scored[department] = (score, row)
    ordered = sorted(scored.items(), key=lambda item: (-item[1][0], item[0]))
    return [row for _, (_, row) in ordered[:limit]]


def _extract_public_contact_rows(
    sources: list[SourceDocument],
    *,
    output_language: str,
    limit: int,
) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    contact_person_pattern = re.compile(r"(联系人|联络人|联系人姓名|项目联系人|采购人联系人|代理机构联系人)[:：]?\s*([A-Za-z\u4e00-\u9fa5]{2,24})")
    agency_pattern = re.compile(r"(采购代理机构|招标代理机构|代理机构)[:：]?\s*([A-Za-z0-9\u4e00-\u9fa5·（）()]{2,40})")
    contact_page_tokens = ("contact", "lxwm", "about", "relation", "ir", "investor", "join", "service", "联系我们", "联络", "联系")
    department_contact_pattern = re.compile(
        r"((采购中心|招标办|信息中心|数据局|数字化部|科技部|计划财务部|预算处|运营管理部|办公室)[A-Za-z\u4e00-\u9fa5（）()\\-]{0,16})"
    )
    line_contact_pattern = re.compile(
        r"([A-Za-z0-9\u4e00-\u9fa5·（）()]{2,36})(联系人|联系电话|联系邮箱|服务热线|咨询电话)[:：]?\s*([A-Za-z0-9@\-.+\u4e00-\u9fa5]{2,48})"
    )

    def is_valid_contact_value(value: str) -> bool:
        normalized = normalize_text(value)
        lowered = normalized.lower()
        if not normalized:
            return False
        if any(lowered.endswith(ext) for ext in (".webp", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".bmp")):
            return False
        if lowered.startswith("http") and any(domain in lowered for domain in GENERIC_CONTENT_DOMAINS):
            return False
        return True

    def allow_public_entry(source: SourceDocument) -> bool:
        domain = normalize_text(source.domain or "").lower()
        title_or_url = f"{source.title or ''} {source.url or ''}".lower()
        if source.source_tier in {"official", "aggregate"}:
            return True
        if any(token in title_or_url for token in contact_page_tokens):
            return True
        if domain in GENERIC_CONTENT_DOMAINS:
            return False
        return False

    for source in sources:
        text = _source_text(source)
        emails = EMAIL_PATTERN.findall(text)
        phones = PHONE_PATTERN.findall(text)
        contacts = contact_person_pattern.findall(text)
        agencies = agency_pattern.findall(text)
        domain = normalize_text(source.domain or "")
        label = normalize_text(source.source_label or domain or source.title)
        title_or_url = f"{source.title or ''} {source.url or ''}".lower()
        contact_departments = [normalize_text(item[0]) for item in department_contact_pattern.findall(text)]
        line_contacts = line_contact_pattern.findall(text)
        for _, person in contacts[:2]:
            row = f"{label}：公开联系人 {normalize_text(person)}"
            if row not in seen:
                seen.add(row)
                rows.append(row)
        for department in contact_departments[:2]:
            row = f"{label}：可能归口部门 {department}"
            if row not in seen:
                seen.add(row)
                rows.append(row)
        for owner, field_name, value in line_contacts[:2]:
            normalized_owner = normalize_text(owner)
            normalized_value = normalize_text(value)
            if not normalized_value or not is_valid_contact_value(normalized_value):
                continue
            row = f"{label}：{normalized_owner}{field_name} {normalized_value}"
            if row not in seen:
                seen.add(row)
                rows.append(row)
        for _, agency in agencies[:1]:
            row = f"{label}：代理/服务机构 {normalize_text(agency)}"
            if row not in seen:
                seen.add(row)
                rows.append(row)
        for email in emails[:2]:
            if not is_valid_contact_value(email):
                continue
            row = f"{label}：公开邮箱 {email}"
            if row not in seen:
                seen.add(row)
                rows.append(row)
        for phone in phones[:2]:
            if not is_valid_contact_value(phone):
                continue
            row = f"{label}：公开电话 {normalize_text(phone)}"
            if row not in seen:
                seen.add(row)
                rows.append(row)
        if domain and allow_public_entry(source):
            row = f"{label}：官网/公开入口 https://{domain}"
            if row not in seen:
                seen.add(row)
                rows.append(row)
        if any(token in title_or_url for token in contact_page_tokens) and is_valid_contact_value(source.url or ""):
            row = f"{label}：高概率公开联系页 {source.url or f'https://{domain}'}"
            if row not in seen:
                seen.add(row)
                rows.append(row)
        if len(rows) >= limit:
            break
    if rows:
        return rows[:limit]
    return _dedupe_strings(
        [
            localized_text(
                output_language,
                {
                    "zh-CN": "当前证据不足：建议优先查看甲方官网“联系我们”与采购公告联系人信息。",
                    "zh-TW": "目前證據不足：建議優先查看甲方官網「聯絡我們」與採購公告聯絡人資訊。",
                    "en": "Evidence is insufficient: verify public contact channels through the buyer website and procurement notices.",
                },
                "当前证据不足：建议优先查看甲方官网“联系我们”与采购公告联系人信息。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "建议补充公开服务热线、采购公告联系人或投资者关系邮箱后重新生成。",
                    "zh-TW": "建議補充公開服務熱線、採購公告聯絡人或投資者關係郵箱後重新生成。",
                    "en": "Add public hotlines, procurement contacts, or investor relations emails and rerun.",
                },
                "建议补充公开服务热线、采购公告联系人或投资者关系邮箱后重新生成。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "建议将关键词收敛到具体甲方公司或项目名称，以提升公开联系方式命中率。",
                    "zh-TW": "建議將關鍵詞收斂到具體甲方公司或專案名稱，以提升公開聯絡方式命中率。",
                    "en": "Narrow the keyword to a specific buyer or project to improve public contact matching.",
                },
                "建议将关键词收敛到具体甲方公司或项目名称，以提升公开联系方式命中率。",
            ),
        ],
        limit,
    )


def _source_mentions_entity(source: SourceDocument, entity_name: str) -> bool:
    normalized_name = normalize_text(entity_name)
    if not normalized_name:
        return False
    return _source_mentions_entity_cached(_source_text(source), normalized_name)


@lru_cache(maxsize=16384)
def _source_mentions_entity_cached(text: str, normalized_name: str) -> bool:
    variants = _org_entity_variants(normalized_name)
    if any(variant in text for variant in variants):
        return True
    canonical_name = _entity_canonical_key(normalized_name)
    canonical_text = _entity_canonical_key(text)
    return bool(canonical_name and canonical_text and canonical_name in canonical_text)


def _source_negates_entity(source: SourceDocument, entity_name: str) -> bool:
    normalized_name = normalize_text(entity_name)
    if not normalized_name:
        return False
    negative_tokens = ("未提及", "未出现", "未涉及", "未覆盖", "没有提及", "并未提及", "并未出现", "不涉及", "未见")
    for sentence in re.split(r"[。！？!?；;\n]", _source_text(source)):
        normalized_sentence = normalize_text(sentence)
        if normalized_name in normalized_sentence and any(token in normalized_sentence for token in negative_tokens):
            return True
    return False


def _source_supports_target_account(
    source: SourceDocument,
    entity_name: str,
    *,
    theme_terms: list[str],
    scope_hints: dict[str, object],
) -> bool:
    if not _source_mentions_entity(source, entity_name):
        return False
    if _source_negates_entity(source, entity_name):
        return False
    if _stored_source_is_low_signal(source, theme_terms=theme_terms, scope_hints=scope_hints):
        return False
    return True


def _build_entity_specific_contact_rows(
    sources: list[SourceDocument],
    *,
    entity_names: list[str],
    output_language: str,
    limit: int,
) -> list[str]:
    if not entity_names:
        return []

    normalized_entities = [
        normalize_text(name)
        for name in entity_names
        if normalize_text(name) and "待验证" not in normalize_text(name) and "待驗證" not in normalize_text(name)
        and (_is_plausible_entity_name(normalize_text(name)) or _is_lightweight_entity_name(normalize_text(name)))
    ]
    if not normalized_entities:
        return []

    contact_person_pattern = re.compile(
        r"(联系人|联络人|联系人姓名|项目联系人|采购人联系人|代理机构联系人)[:：]?\s*([A-Za-z\u4e00-\u9fa5]{2,24})"
    )
    line_contact_pattern = re.compile(
        r"([A-Za-z0-9\u4e00-\u9fa5·（）()]{2,36})(联系人|联系电话|联系邮箱|服务热线|咨询电话)[:：]?\s*([A-Za-z0-9@\-.+\u4e00-\u9fa5]{2,48})"
    )
    procurement_like_source_types = {
        "procurement",
        "official_tender_feed",
        "compliant_procurement_aggregate",
        "tender_feed",
    }
    official_contact_source_types = {
        "policy",
        "filing",
        "official_policy_speech",
    }

    def is_valid_contact_value(value: str) -> bool:
        normalized = normalize_text(value)
        lowered = normalized.lower()
        if not normalized:
            return False
        if any(lowered.endswith(ext) for ext in (".webp", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".bmp")):
            return False
        if lowered.startswith("http") and any(domain in lowered for domain in GENERIC_CONTENT_DOMAINS):
            return False
        return True

    def looks_like_company_domain(domain: str) -> bool:
        lowered = normalize_text(domain).lower()
        if not lowered:
            return False
        if lowered in GENERIC_CONTENT_DOMAINS or lowered in PROCUREMENT_DOMAINS or lowered in POLICY_DOMAINS or lowered in EXCHANGE_DOMAINS:
            return False
        if lowered.endswith(".gov.cn") or lowered.endswith(".edu.cn"):
            return False
        return "." in lowered

    scored_rows: dict[str, int] = {}

    def add_row(row: str, score: int) -> None:
        normalized = normalize_text(row)
        if not normalized or not _is_useful_public_contact_row(normalized):
            return
        current = scored_rows.get(normalized)
        if current is None or score > current:
            scored_rows[normalized] = score

    for entity in _dedupe_strings(normalized_entities, 6):
        for source in sources:
            if not _source_mentions_entity(source, entity):
                continue
            text = _source_text(source)
            domain = normalize_text(source.domain or "")
            title_or_url = f"{source.title or ''} {source.url or ''}".lower()
            label = normalize_text(source.source_label or source.title or domain or entity)
            contact_page = any(token in title_or_url for token in CONTACT_PAGE_TOKENS)
            official_like = source.source_tier == "official" or source.source_type in official_contact_source_types
            procurement_like = source.source_type in procurement_like_source_types

            if looks_like_company_domain(domain) and official_like:
                add_row(f"{entity}：官方公开入口 https://{domain}", 92)

            if contact_page and source.url and is_valid_contact_value(source.url):
                add_row(f"{entity}：高概率公开联系页 {source.url}", 96 if official_like else 82)

            for _, person in contact_person_pattern.findall(text)[:2]:
                normalized_person = normalize_text(person)
                if not normalized_person:
                    continue
                prefix = "采购/项目联系人" if procurement_like else "公开联系人"
                add_row(
                    f"{entity}：{prefix} {normalized_person}（{label}）",
                    94 if procurement_like else 84,
                )

            for owner, field_name, value in line_contact_pattern.findall(text)[:3]:
                normalized_owner = normalize_text(owner)
                normalized_value = normalize_text(value)
                if not normalized_value or not is_valid_contact_value(normalized_value):
                    continue
                owner_text = normalized_owner if normalized_owner and normalized_owner != entity else ""
                add_row(
                    f"{entity}：{owner_text}{field_name} {normalized_value}（{label}）",
                    98 if procurement_like else (90 if official_like else 80),
                )

            for email in EMAIL_PATTERN.findall(text)[:2]:
                if not is_valid_contact_value(email):
                    continue
                add_row(
                    f"{entity}：公开邮箱 {email}（{label}）",
                    96 if official_like else (92 if procurement_like else 78),
                )

            for phone in PHONE_PATTERN.findall(text)[:2]:
                normalized_phone = normalize_text(phone)
                if not is_valid_contact_value(normalized_phone):
                    continue
                add_row(
                    f"{entity}：公开电话 {normalized_phone}（{label}）",
                    95 if procurement_like else (88 if official_like else 76),
                )

    ordered = [
        row
        for row, _ in sorted(
            scored_rows.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]
    if ordered:
        return ordered[:limit]
    return []


def _build_entity_specific_team_rows(
    sources: list[SourceDocument],
    *,
    entity_names: list[str],
    scope_hints: dict[str, object],
    output_language: str,
    limit: int,
) -> list[str]:
    if not entity_names:
        return []

    normalized_entities = [
        normalize_text(name)
        for name in entity_names
        if normalize_text(name) and "待验证" not in normalize_text(name) and "待驗證" not in normalize_text(name)
        and (_is_plausible_entity_name(normalize_text(name)) or _is_lightweight_entity_name(normalize_text(name)))
    ]
    if not normalized_entities:
        return []

    team_keywords = (
        "团队",
        "事业群",
        "事业部",
        "业务线",
        "业务部",
        "行业线",
        "政企",
        "政务",
        "行业解决方案",
        "行业方案",
        "区域公司",
        "区域团队",
        "创新中心",
        "研究院",
        "交付中心",
        "运营团队",
        "商务合作",
        "合作团队",
        "内容生态",
        "生态合作",
        "大客户部",
        "客户成功",
        "公共事务",
        "投资者关系",
    )
    scope_regions = [normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    scope_region_terms = _expand_region_scope_terms(scope_regions)
    scope_industries = [normalize_text(str(item)) for item in scope_hints.get("industries", []) if normalize_text(str(item))]
    scored_rows: dict[str, int] = {}

    def add_row(row: str, score: int) -> None:
        normalized = normalize_text(row)
        if not normalized:
            return
        current = scored_rows.get(normalized)
        if current is None or score > current:
            scored_rows[normalized] = score

    for entity in _dedupe_strings(normalized_entities, 6):
        for source in sources:
            if not _source_mentions_entity(source, entity):
                continue
            text = _source_text(source)
            chunks = re.split(r"[。！？!?；;\n]", text)
            label = normalize_text(source.source_label or source.title or source.domain or entity)
            for chunk in chunks:
                sentence = normalize_text(chunk)
                if not sentence or entity not in sentence:
                    continue
                if _text_has_region_conflict(sentence, scope_hints=scope_hints):
                    continue
                if not any(token in sentence for token in team_keywords):
                    continue
                score = 72
                if source.source_tier == "official":
                    score += 12
                elif source.source_tier == "aggregate":
                    score += 6
                if any(region and region in sentence for region in scope_region_terms):
                    score += 8
                if any(industry and industry in sentence for industry in scope_industries):
                    score += 6
                if any(token in sentence for token in ("负责", "牵头", "落地", "推进", "合作", "运营", "交付")):
                    score += 6
                add_row(f"{entity}：{_truncate_text(sentence, 108)}（{label}）", score)

    ordered = [
        row
        for row, _ in sorted(
            scored_rows.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]
    if ordered:
        return ordered[:limit]

    scope_text = " / ".join(_dedupe_strings([*scope_regions[:2], *scope_industries[:2]], 3)) or normalize_text(
        str(scope_hints.get("anchor_text", ""))
    ) or localized_text(
        output_language,
        {
            "zh-CN": "当前范围",
            "zh-TW": "目前範圍",
            "en": "the current scope",
        },
        "当前范围",
    )
    return _dedupe_strings(
        [
            localized_text(
                output_language,
                {
                    "zh-CN": f"当前已收敛到具体公司，建议优先核验其在 {scope_text} 下的政企/行业方案团队、区域交付团队与商务合作团队公开线索。",
                    "zh-TW": f"目前已收斂到具體公司，建議優先核驗其在 {scope_text} 下的政企/產業方案團隊、區域交付團隊與商務合作團隊公開線索。",
                    "en": f"The report converged to specific companies. Next verify public signals for their regional delivery, industry solution, and business partnership teams within {scope_text}.",
                },
                f"当前已收敛到具体公司，建议优先核验其在 {scope_text} 下的政企/行业方案团队、区域交付团队与商务合作团队公开线索。",
            ),
        ],
        limit,
    )


def _source_type_weight(source: SourceDocument) -> int:
    if source.source_tier == "official":
        return 18
    if source.source_tier == "aggregate":
        return 12
    return 8


def _build_entity_evidence(
    source: SourceDocument,
) -> ResearchEntityEvidenceOut:
    return ResearchEntityEvidenceOut(
        title=source.title,
        url=source.url,
        source_label=source.source_label,
        source_tier=source.source_tier if source.source_tier in {"official", "media", "aggregate"} else "media",
        excerpt=_clean_source_text_for_analysis(source.excerpt or source.snippet),
    )


_CONFLICT_POSITIVE_TOKENS = (
    "已发布",
    "已启动",
    "已上线",
    "已签约",
    "已合作",
    "落地",
    "上线",
    "签约",
    "合作",
    "中标",
    "确认",
    "明确",
    "获批",
    "推进",
)
_CONFLICT_NEGATIVE_TOKENS = (
    "尚未",
    "暂无",
    "未披露",
    "未启动",
    "未合作",
    "否认",
    "辟谣",
    "传闻",
    "未经证实",
    "推迟",
    "延后",
    "取消",
    "不涉及",
    "未见",
)


def _excerpt_for_evidence(source: SourceDocument, *, matched_terms: list[str] | None = None) -> str:
    terms = [term for term in (matched_terms or []) if normalize_text(term)]
    candidates = re.split(r"[。！？!?；;\n]", _source_text(source))
    for candidate in candidates:
        normalized = normalize_text(candidate)
        if not normalized:
            continue
        if terms and any(term.lower() in normalized.lower() for term in terms):
            return normalized[:140]
    fallback = normalize_text(source.excerpt or source.snippet or source.title)
    return fallback[:140]


def _section_confidence_profile(
    *,
    section_title: str,
    items: list[str],
    sources: list[SourceDocument],
    evidence_density: str,
    source_quality: str,
    official_source_ratio: float,
    meets_evidence_quota: bool,
    evidence_links: list[ResearchEntityEvidenceOut],
) -> tuple[str, str, str, bool, str]:
    anchor_terms = [
        token
        for token in _tokenize_for_match(section_title, *items[:3])
        if len(token) >= 2 and token not in GENERIC_FOCUS_TOKENS
    ][:8]
    matched_texts: list[str] = []
    matched_urls = {normalize_text(link.url) for link in evidence_links if normalize_text(link.url)}
    for source in sources:
        source_text = _source_text(source)
        if normalize_text(source.url) in matched_urls:
            matched_texts.append(source_text)
            continue
        if anchor_terms and any(term.lower() in source_text.lower() for term in anchor_terms):
            matched_texts.append(source_text)
    positive_hits = sum(1 for text in matched_texts if any(token in text for token in _CONFLICT_POSITIVE_TOKENS))
    negative_hits = sum(1 for text in matched_texts if any(token in text for token in _CONFLICT_NEGATIVE_TOKENS))
    contradiction_detected = positive_hits > 0 and negative_hits > 0
    contradiction_note = (
        f"{section_title} 的相关来源里同时出现了确认性和否定/未证实表述，当前应按冲突信息处理。"
        if contradiction_detected
        else ""
    )
    if contradiction_detected:
        return "conflict", "交叉验证冲突", contradiction_note, True, contradiction_note
    if meets_evidence_quota and official_source_ratio >= 0.35 and evidence_density == "high" and source_quality != "low":
        return "high", "高置信结论", f"{section_title} 已满足证据配额，且有较高官方源占比与多源支撑。", False, ""
    return "low", "待补证结论", f"{section_title} 当前仍需继续补官方源、交叉验证或增加直接证据。", False, ""


def _extract_rank_entity_name(value: str) -> str:
    candidates = _extract_rank_entity_candidates(value)
    return candidates[0] if candidates else ""


@lru_cache(maxsize=16384)
def _is_plausible_entity_name(value: str) -> bool:
    normalized = _strip_entity_leading_noise(value)
    if not normalized or len(normalized) < 3:
        return False
    if _looks_like_fragment_entity_name(normalized):
        return False
    if _looks_like_placeholder_entity_name(normalized):
        return False
    if _contains_low_value_entity_token(normalized):
        return False
    if any(token in normalized for token in ENTITY_BLACKLIST_TOKENS):
        return False
    if any(token in normalized for token in ENTITY_INVALID_PHRASE_TOKENS):
        return False
    if any(char in normalized for char in "，,。；;"):
        return False
    if normalized.startswith(("和", "与", "及", "或", "如", "例如", "比如", "诸如", "优先给", "官方", "公开")):
        return False
    if (
        any(connector in normalized for connector in ("与", "及", "和"))
        and normalized not in SPECIAL_ENTITY_ALIASES
        and not any(token in normalized for token in ENTITY_SUFFIX_TOKENS)
    ):
        return False
    if "：" in normalized or ":" in normalized:
        return False
    if normalized.endswith(("怎么办", "如何", "制作", "是指", "相关")):
        return False
    if re.search(r"(路径|节奏|策略|打法|能力|场景|机会|商机|窗口|趋势|布局|运营|建设|规划|升级|协同|统筹)$", normalized):
        return False
    industry_alias_values = {
        normalize_text(alias)
        for aliases in INDUSTRY_SCOPE_ALIASES.values()
        for alias in aliases
        if normalize_text(alias)
    }
    if normalized in industry_alias_values:
        return False
    if any(alias == normalized or alias in normalized for alias in SPECIAL_ENTITY_ALIASES):
        return True
    if any(token in normalized for token in ENTITY_SUFFIX_TOKENS):
        return True
    compact = re.sub(r"\s+", "", normalized)
    if ORG_PATTERN.fullmatch(compact) or COMPACT_ENTITY_PATTERN.fullmatch(compact):
        return True
    return False


def _extract_rank_entity_candidates(
    value: str,
    *,
    scope_hints: dict[str, object] | None = None,
) -> list[str]:
    return list(_extract_rank_entity_candidates_cached(value, _scope_org_names_key(scope_hints)))


@lru_cache(maxsize=16384)
def _extract_rank_entity_candidates_cached(
    value: str,
    scope_org_names: tuple[str, ...],
) -> tuple[str, ...]:
    text = normalize_text(value)
    if not text:
        return ()
    candidates: list[str] = []
    for match in ORG_PATTERN.findall(text):
        candidates.append(normalize_text(match))
    for match in COMPACT_ENTITY_PATTERN.findall(text):
        candidates.append(normalize_text(match))
    for alias in KNOWN_LIGHTWEIGHT_ENTITY_NAMES:
        if alias in text:
            candidates.append(alias)
    candidates.extend(_known_org_alias_candidates_from_text_cached(text, scope_org_names))
    filtered: list[str] = []
    for candidate in candidates:
        normalized = _resolve_known_org_name_cached(candidate, scope_org_names)
        normalized = _strip_entity_leading_noise(normalized)
        if not _is_plausible_entity_name(normalized) and not _is_lightweight_entity_name(normalized):
            continue
        if _looks_like_fragment_entity_name(normalized):
            continue
        if (
            any(connector in normalized for connector in ("与", "及", "和"))
            and normalized not in SPECIAL_ENTITY_ALIASES
            and not any(token in normalized for token in ENTITY_SUFFIX_TOKENS)
        ):
            continue
        filtered.append(normalized)
    return tuple(_dedupe_strings(filtered, 5))


def _build_ranked_entity_reasoning(
    *,
    output_language: str,
    role: str,
    official_hits: int,
    matched_signals: list[str],
    scope_regions: list[str],
    scope_industries: list[str],
    evidence_count: int,
) -> str:
    signal_text = "、".join(matched_signals[:3]) or localized_text(
        output_language,
        {"zh-CN": "公开线索", "zh-TW": "公開線索", "en": "public evidence"},
        "公开线索",
    )
    scope_bits = [item for item in [*(scope_regions[:1] or []), *(scope_industries[:1] or [])] if item]
    scope_text = " / ".join(scope_bits) if scope_bits else localized_text(
        output_language,
        {"zh-CN": "当前关键词范围", "zh-TW": "目前關鍵詞範圍", "en": "the current keyword scope"},
        "当前关键词范围",
    )
    if role == "target":
        return localized_text(
            output_language,
            {
                "zh-CN": f"高价值甲方候选：在 {scope_text} 范围内命中 {evidence_count} 条相关线索，包含 {official_hits} 条官方/招采证据，且与 {signal_text} 高度相关。",
                "zh-TW": f"高價值甲方候選：在 {scope_text} 範圍內命中 {evidence_count} 條相關線索，包含 {official_hits} 條官方/招採證據，且與 {signal_text} 高度相關。",
                "en": f"High-value buyer candidate: {evidence_count} matching signals within {scope_text}, including {official_hits} official or tender sources, with strong relevance to {signal_text}.",
            },
            f"高价值甲方候选：在 {scope_text} 范围内命中 {evidence_count} 条相关线索，包含 {official_hits} 条官方/招采证据，且与 {signal_text} 高度相关。",
        )
    if role == "competitor":
        return localized_text(
            output_language,
            {
                "zh-CN": f"高威胁竞品候选：在 {scope_text} 范围内命中 {evidence_count} 条中标/方案/平台相关线索，包含 {official_hits} 条较高可信证据，显示其对 {signal_text} 有较强覆盖。",
                "zh-TW": f"高威脅競品候選：在 {scope_text} 範圍內命中 {evidence_count} 條中標/方案/平台相關線索，包含 {official_hits} 條較高可信證據，顯示其對 {signal_text} 有較強覆蓋。",
                "en": f"High-threat competitor candidate: {evidence_count} bid/solution/platform signals within {scope_text}, including {official_hits} stronger sources, indicating solid coverage around {signal_text}.",
            },
            f"高威胁竞品候选：在 {scope_text} 范围内命中 {evidence_count} 条中标/方案/平台相关线索，包含 {official_hits} 条较高可信证据，显示其对 {signal_text} 有较强覆盖。",
        )
    return localized_text(
        output_language,
        {
            "zh-CN": f"高影响力生态伙伴候选：在 {scope_text} 范围内命中 {evidence_count} 条合作/联合/渠道相关线索，包含 {official_hits} 条高可信证据，更偏牵线、集成或生态协同，而非单纯自研产品输出。",
            "zh-TW": f"高影響力生態夥伴候選：在 {scope_text} 範圍內命中 {evidence_count} 條合作/聯合/渠道相關線索，包含 {official_hits} 條高可信證據，更偏牽線、整合或生態協同，而非單純自研產品輸出。",
            "en": f"High-influence ecosystem partner candidate: {evidence_count} collaboration/channel signals within {scope_text}, including {official_hits} stronger sources, indicating connector, integrator, or ecosystem-building roles rather than pure product output.",
        },
        f"高影响力生态伙伴候选：在 {scope_text} 范围内命中 {evidence_count} 条合作/联合/渠道相关线索，包含 {official_hits} 条高可信证据，更偏牵线、集成或生态协同，而非单纯自研产品输出。",
    )


def _build_fallback_entity_reasoning(
    *,
    output_language: str,
    role: str,
    evidence_count: int,
    scope_regions: list[str],
    scope_industries: list[str],
) -> str:
    scope_bits = [item for item in [*(scope_regions[:1] or []), *(scope_industries[:1] or [])] if item]
    scope_text = " / ".join(scope_bits) if scope_bits else localized_text(
        output_language,
        {"zh-CN": "当前关键词范围", "zh-TW": "目前關鍵詞範圍", "en": "the current keyword scope"},
        "当前关键词范围",
    )
    if role == "target":
        return localized_text(
            output_language,
            {
                "zh-CN": f"基于 {scope_text} 范围内的公开线索交叉归纳得出，当前直接证据相对有限，但该主体在预算、采购或项目语境中的出现频次较高，建议继续作为高价值甲方候选跟踪。",
                "zh-TW": f"基於 {scope_text} 範圍內的公開線索交叉歸納得出，目前直接證據相對有限，但該主體在預算、採購或專案語境中的出現頻次較高，建議持續作為高價值甲方候選追蹤。",
                "en": f"Derived from cross-reading public signals within {scope_text}. Direct evidence is still limited, but the entity appears frequently in budget, procurement, or project contexts and should remain on the buyer watchlist.",
            },
            f"基于 {scope_text} 范围内的公开线索交叉归纳得出，当前直接证据相对有限，但该主体在预算、采购或项目语境中的出现频次较高，建议继续作为高价值甲方候选跟踪。",
        )
    if role == "competitor":
        return localized_text(
            output_language,
            {
                "zh-CN": f"基于 {scope_text} 范围内的公开线索交叉归纳得出，当前直接中标证据有限，但该主体在方案、平台、交付或竞对语境中的出现频次较高，建议作为高威胁竞品持续观察。",
                "zh-TW": f"基於 {scope_text} 範圍內的公開線索交叉歸納得出，目前直接中標證據有限，但該主體在方案、平台、交付或競對語境中的出現頻次較高，建議作為高威脅競品持續觀察。",
                "en": f"Derived from cross-reading public signals within {scope_text}. Direct winning evidence is limited, but the entity appears frequently in solution, platform, delivery, or rivalry contexts and should remain on the competitor watchlist.",
            },
            f"基于 {scope_text} 范围内的公开线索交叉归纳得出，当前直接中标证据有限，但该主体在方案、平台、交付或竞对语境中的出现频次较高，建议作为高威胁竞品持续观察。",
        )
    return localized_text(
        output_language,
        {
            "zh-CN": f"基于 {scope_text} 范围内的公开线索交叉归纳得出，当前直接合作证据有限，但该主体在咨询、集成、渠道或联盟语境中的出现频次较高，更适合作为潜在牵线或生态协同伙伴。",
            "zh-TW": f"基於 {scope_text} 範圍內的公開線索交叉歸納得出，目前直接合作證據有限，但該主體在諮詢、整合、渠道或聯盟語境中的出現頻次較高，更適合作為潛在牽線或生態協同夥伴。",
            "en": f"Derived from cross-reading public signals within {scope_text}. Direct collaboration evidence is limited, but the entity appears repeatedly in consulting, integration, channel, or alliance contexts and is better treated as a potential connector or ecosystem partner.",
        },
        f"基于 {scope_text} 范围内的公开线索交叉归纳得出，当前直接合作证据有限，但该主体在咨询、集成、渠道或联盟语境中的出现频次较高，更适合作为潜在牵线或生态协同伙伴。",
    )


def _build_score_factor(
    *,
    label: str,
    score: int,
    note: str,
) -> ResearchScoreFactorOut:
    return ResearchScoreFactorOut(label=label, score=score, note=note)


def _score_bucket_label(score: int, output_language: str) -> str:
    if score >= 75:
        return localized_text(
            output_language,
            {"zh-CN": "高价值", "zh-TW": "高價值", "en": "High Value"},
            "高价值",
        )
    if score >= 55:
        return localized_text(
            output_language,
            {"zh-CN": "普通价值", "zh-TW": "普通價值", "en": "Medium Value"},
            "普通价值",
        )
    return localized_text(
        output_language,
        {"zh-CN": "低价值", "zh-TW": "低價值", "en": "Low Value"},
        "低价值",
    )


def _rank_top_entities(
    sources: list[SourceDocument],
    *,
    role: str,
    output_language: str,
    scope_hints: dict[str, object],
    theme_terms: list[str],
    entity_graph: ResearchEntityGraphOut | None = None,
    fallback_values: Iterable[str] | None = None,
    limit: int = 3,
) -> tuple[list[ResearchRankedEntityOut], list[ResearchRankedEntityOut]]:
    role_context_map = {
        "target": ("招标", "采购", "预算", "项目", "建设", "规划", "部署", "业主", "甲方"),
        "competitor": ("中标", "平台", "产品", "解决方案", "厂商", "交付", "案例", "集成商"),
        "partner": ("合作", "伙伴", "联合", "生态", "咨询", "集成商", "渠道", "联盟", "运营"),
    }
    positive_name_tokens_map = {
        "target": ("政府", "局", "委", "办", "中心", "医院", "大学", "银行", "学校", "集团", "城投", "交投"),
        "competitor": ("科技", "信息", "软件", "智能", "云", "数据", "通信", "股份", "有限公司"),
        "partner": ("咨询", "顾问", "集成", "渠道", "联盟", "协会", "研究院", "研究所", "运营", "服务"),
    }
    preferred_source_types_map = {
        "target": {"procurement", "policy", "filing", "official_tender_feed", "official_policy_speech", "compliant_procurement_aggregate"},
        "competitor": {"tender_feed", "web", "tech_media_feed", "filing", "official_tender_feed"},
        "partner": {"web", "tech_media_feed", "procurement", "policy", "official_tender_feed"},
    }
    partner_penalty_tokens = ("产品", "平台", "芯片", "模型", "自研", "算法", "大模型")
    institution_tokens = ("政府", "数据局", "局", "委", "办", "中心", "医院", "大学", "学校", "银行", "城投", "交投", "水务", "地铁")
    vendor_tokens = ("科技", "软件", "云", "数码", "智能", "信息", "平台", "模型", "算法", "芯片")
    scope_regions = [normalize_text(item) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    scope_industries = [normalize_text(item) for item in scope_hints.get("industries", []) if normalize_text(str(item))]
    scope_clients = [normalize_text(item) for item in scope_hints.get("clients", []) if normalize_text(str(item))]
    seed_companies = [
        normalize_text(str(item))
        for item in (scope_hints.get("seed_companies", []) or [])
        if normalize_text(str(item))
    ]
    prefer_company_entities = bool(scope_hints.get("prefer_company_entities"))
    prefer_head_companies = bool(scope_hints.get("prefer_head_companies"))
    theme_labels = [label for label in scope_industries if normalize_text(label)]
    context_keywords = role_context_map.get(role, ())
    if prefer_company_entities and role in {"target", "competitor"}:
        themed_company_tokens = [
            token
            for label in theme_labels
            for token in THEME_ENTITY_ALLOW_TOKENS.get(label, {}).get(role, ())
            if normalize_text(token) and token not in {"内容", "运营", "服务"}
        ]
        positive_tokens = tuple(
            dict.fromkeys(
                [
                    *themed_company_tokens,
                    *GENERIC_COMPANY_NAME_TOKENS,
                    "版权",
                    "发行",
                    "商业化",
                ]
            )
        )
    else:
        positive_tokens = positive_name_tokens_map.get(role, ())
    preferred_source_types = preferred_source_types_map.get(role, set())
    graph_lookup = _entity_graph_lookup(entity_graph) if entity_graph else {}

    def build_entity_result(
        *,
        name: str,
        score: int,
        reasoning: str,
        score_breakdown: list[ResearchScoreFactorOut],
        evidence_links: list[ResearchEntityEvidenceOut],
        entity_mode: Literal["instance", "pending"] = "instance",
    ) -> ResearchRankedEntityOut:
        return ResearchRankedEntityOut(
            name=name,
            score=score,
            reasoning=reasoning,
            entity_mode=entity_mode,
            score_breakdown=score_breakdown,
            evidence_links=evidence_links,
        )

    def build_archetype_results() -> list[ResearchRankedEntityOut]:
        if role == "target" and scope_clients:
            return [
                build_entity_result(
                    name=name,
                    score=max(52, 68 - index * 6),
                    reasoning=localized_text(
                        output_language,
                        {
                            "zh-CN": f"关键词已经直接收敛到 {name}，当前主要缺的是更高置信的项目、预算与官网联络证据，因此先将其保留为重点甲方候选并继续补证。",
                            "zh-TW": f"關鍵詞已直接收斂到 {name}，目前主要缺的是更高置信的專案、預算與官網聯絡證據，因此先將其保留為重點甲方候選並持續補證。",
                            "en": f"The query already converges on {name}. What is missing is higher-confidence project, budget, and official-contact evidence, so it remains on the buyer shortlist pending further verification.",
                        },
                        f"关键词已经直接收敛到 {name}，当前主要缺的是更高置信的项目、预算与官网联络证据，因此先将其保留为重点甲方候选并继续补证。",
                    ),
                    score_breakdown=[
                        _build_score_factor(
                            label="公司锚点命中",
                            score=28,
                            note=name,
                        ),
                        _build_score_factor(
                            label="公开证据待补",
                            score=18,
                            note="优先补官网联系页、采购公告联系人和投资者关系入口",
                        ),
                    ],
                    evidence_links=[],
                    entity_mode="pending",
                )
                for index, name in enumerate(scope_clients[:limit])
            ]
        theme_label = next((label for label in scope_industries if label in THEME_ROLE_ARCHETYPES), "")
        archetypes = THEME_ROLE_ARCHETYPES.get(theme_label, {}).get(role, ())
        if not archetypes:
            return []
        role_label = {
            "target": localized_text(output_language, {"zh-CN": "高价值甲方", "zh-TW": "高價值甲方", "en": "buyer target"}, "高价值甲方"),
            "competitor": localized_text(output_language, {"zh-CN": "高威胁竞品", "zh-TW": "高威脅競品", "en": "competitor threat"}, "高威胁竞品"),
            "partner": localized_text(output_language, {"zh-CN": "高影响力生态伙伴", "zh-TW": "高影響力生態夥伴", "en": "ecosystem partner"}, "高影响力生态伙伴"),
        }.get(role, localized_text(output_language, {"zh-CN": "候选对象", "zh-TW": "候選對象", "en": "candidate"}, "候选对象"))
        return [
            build_entity_result(
                name=name,
                score=max(24, 36 - index * 2),
                reasoning=localized_text(
                    output_language,
                    {
                        "zh-CN": f"当前公开证据还不足以锁定具体公司名，这里先按 {theme_label or '当前主题'} 的 {role_label} 角色给出高价值候选补位，建议补充区域、客户类型或项目词后再确认公司名。",
                        "zh-TW": f"目前公開證據仍不足以鎖定具體公司名，先按 {theme_label or '目前主題'} 的 {role_label} 角色給出高價值候選補位，建議補充區域、客戶類型或專案詞後再確認公司名。",
                        "en": f"Public evidence is still insufficient to lock a concrete company. This is a role-based placeholder for {theme_label or 'the current theme'} and should be refined with more region, client-type, or project keywords.",
                    },
                    f"当前公开证据还不足以锁定具体公司名，这里先按 {theme_label or '当前主题'} 的 {role_label} 角色给出高价值候选补位，建议补充区域、客户类型或项目词后再确认公司名。",
                ),
                score_breakdown=[
                    _build_score_factor(
                        label="主题收敛",
                        score=18,
                        note=theme_label or "当前关键词主题",
                    ),
                    _build_score_factor(
                        label="角色化兜底",
                        score=12,
                        note="当前缺少高置信实体证据",
                    ),
                ],
                evidence_links=[],
                entity_mode="pending",
            )
            for index, name in enumerate(archetypes[:limit])
        ]

    def allow_role_candidate(name: str, text: str) -> bool:
        if theme_labels and not _is_theme_aligned_entity_name(name, role=role, theme_labels=theme_labels):
            return False
        if prefer_company_entities and role in {"target", "competitor"} and not _is_company_like_entity_name(
            name,
            role=role,
            theme_labels=theme_labels,
            seed_companies=seed_companies,
        ):
            return False
        if any(client and (client in name or name in client) for client in scope_clients):
            return role == "target"
        if role == "target":
            if prefer_company_entities:
                return (
                    any(token in name for token in positive_tokens)
                    or any(
                        token in text
                        for token in ("合作", "版权", "发行", "平台", "内容", "动画", "短剧", "AIGC", "商业化", "团队", "生态", "案例")
                    )
                )
            return (
                any(token in name for token in positive_tokens)
                or any(token in text for token in ("预算", "采购", "招标", "建设", "立项", "扩容"))
            )
        if role == "competitor":
            if any(token in name for token in institution_tokens):
                return False
            return (
                any(token in name for token in positive_tokens)
                or any(token in text for token in ("中标", "成交", "方案", "平台", "交付", "厂商", "案例"))
            )
        if any(token in name for token in institution_tokens) or any(token in name for token in partner_penalty_tokens):
            return False
        if any(token in name for token in vendor_tokens) and not any(alias in name for alias in PARTNER_CONNECTOR_ALIASES):
            return False
        return (
            any(alias in name for alias in PARTNER_CONNECTOR_ALIASES)
            or
            any(token in name for token in positive_tokens)
            or any(token in text for token in ("合作", "伙伴", "联合", "联盟", "咨询", "顾问", "渠道", "集成"))
        )

    def is_duplicate_name(name: str) -> bool:
        for existing in used_names:
            if name == existing:
                return True
            if len(name) >= 5 and len(existing) >= 5 and (name in existing or existing in name):
                return True
        return False

    def has_instance_support(name: str, state: dict[str, object]) -> bool:
        if theme_labels and not _is_theme_aligned_entity_name(name, role=role, theme_labels=theme_labels):
            return False
        if prefer_company_entities and role in {"target", "competitor"} and not _is_company_like_entity_name(
            name,
            role=role,
            theme_labels=theme_labels,
            seed_companies=seed_companies,
        ):
            return False
        graph_entity = graph_lookup.get(_entity_canonical_key(name))
        evidence_count = int(state.get("evidence_count", 0) or 0)
        official_hits = int(state.get("official_hits", 0) or 0)
        evidence_links = [item for item in list(state.get("links", [])) if getattr(item, "url", "")]
        graph_source_count = int(getattr(graph_entity, "source_count", 0) or 0) if graph_entity is not None else 0
        graph_official_count = int(getattr(graph_entity, "source_tier_counts", {}).get("official", 0) or 0) if graph_entity is not None else 0
        support_count = max(evidence_count, len(evidence_links), graph_source_count)
        has_official_support = official_hits > 0 or graph_official_count > 0
        if any(client and (client in name or name in client) for client in scope_clients):
            return has_official_support or support_count >= 1
        if prefer_head_companies and role in {"target", "competitor"}:
            return has_official_support or support_count >= 2
        return has_official_support or support_count >= 2

    scored: dict[str, dict[str, object]] = {}
    for source in sources:
        text = _source_text(source)
        lowered = text.lower()
        if theme_terms and not any(term in lowered for term in theme_terms):
            continue
        matched_signals = [token for token in context_keywords if token in text]
        official_hit = 1 if source.source_tier == "official" else 0
        extracted_names = _extract_rank_entity_candidates(text, scope_hints=scope_hints)
        domain_canonical = _canonical_org_name_from_domain(source.domain or extract_domain(source.url))
        if domain_canonical:
            extracted_names.append(domain_canonical)
        for name in _dedupe_strings(extracted_names, 8):
            name = _resolve_known_org_name(name, scope_hints=scope_hints, source=source)
            if len(name) < 3:
                continue
            if not allow_role_candidate(name, text):
                continue
            graph_entity = graph_lookup.get(_entity_canonical_key(name))
            if graph_entity is not None:
                graph_role = normalize_text(graph_entity.entity_type)
                if graph_role not in {role, "generic"}:
                    continue
                canonical_name = normalize_text(graph_entity.canonical_name)
                if canonical_name:
                    name = canonical_name
            if theme_labels and not _is_theme_aligned_entity_name(name, role=role, theme_labels=theme_labels):
                continue
            if prefer_company_entities and role in {"target", "competitor"} and not _is_company_like_entity_name(
                name,
                role=role,
                theme_labels=theme_labels,
                seed_companies=seed_companies,
            ):
                continue
            score = _source_type_weight(source)
            score_breakdown = [
                _build_score_factor(
                    label="来源层级",
                    score=_source_type_weight(source),
                    note=f"{source.source_tier or 'media'} / {source.source_type}",
                )
            ]
            score += min(len(matched_signals), 3) * 6
            if matched_signals:
                score_breakdown.append(
                    _build_score_factor(
                        label="角色信号",
                        score=min(len(matched_signals), 3) * 6,
                        note="、".join(matched_signals[:3]),
                    )
                )
            score += sum(1 for token in positive_tokens if token in name) * 4
            if any(token in name for token in positive_tokens):
                score_breakdown.append(
                    _build_score_factor(
                        label="实体匹配",
                        score=sum(1 for token in positive_tokens if token in name) * 4,
                        note=name,
                    )
                )
            if source.source_type in preferred_source_types:
                score += 8
                score_breakdown.append(
                    _build_score_factor(
                        label="优先来源类型",
                        score=8,
                        note=source.source_type,
                    )
                )
            if any(region and region in text for region in scope_regions):
                score += 5
                score_breakdown.append(
                    _build_score_factor(
                        label="区域收敛",
                        score=5,
                        note=" / ".join(scope_regions[:2]) or "命中区域",
                    )
                )
            if any(client and client in name for client in scope_clients):
                score += 10
                score_breakdown.append(
                    _build_score_factor(
                        label="甲方范围贴合",
                        score=10,
                        note=" / ".join(scope_clients[:2]) or "命中甲方范围",
                    )
                )
            if prefer_company_entities and role in {"target", "competitor"} and (
                name in seed_companies or _is_lightweight_entity_name(name)
            ):
                score += 8
                score_breakdown.append(
                    _build_score_factor(
                        label="公司名单命中",
                        score=8,
                        note=name,
                    )
                )
            if role == "target" and any(token in name for token in vendor_tokens) and not any(client and client in name for client in scope_clients):
                score -= 10
                score_breakdown.append(
                    _build_score_factor(
                        label="业主角色惩罚",
                        score=-10,
                        note="更像厂商或平台方",
                    )
                )
            if role == "partner":
                if any(token in text for token in ("联合体", "合作伙伴", "咨询", "渠道", "集成", "联盟")):
                    score += 10
                    score_breakdown.append(
                        _build_score_factor(
                            label="生态协同信号",
                            score=10,
                            note="合作 / 渠道 / 咨询 / 集成",
                        )
                    )
                if any(token in text for token in partner_penalty_tokens):
                    score -= 8
                    score_breakdown.append(
                        _build_score_factor(
                            label="产品型惩罚",
                            score=-8,
                            note="更像自研产品或平台输出",
                        )
                    )
            if role == "competitor" and any(token in text for token in ("中标", "成交", "落地", "案例")):
                score += 8
                score_breakdown.append(
                    _build_score_factor(
                        label="竞标活跃度",
                        score=8,
                        note="中标 / 成交 / 落地 / 案例",
                    )
                )
            if role == "target" and any(token in text for token in ("预算", "采购", "项目", "建设")):
                score += 8
                score_breakdown.append(
                    _build_score_factor(
                        label="预算与项目信号",
                        score=8,
                        note="预算 / 采购 / 项目 / 建设",
                    )
                )
            if graph_entity is not None:
                graph_source_count = int(graph_entity.source_count)
                graph_official_count = int(graph_entity.source_tier_counts.get("official", 0))
                graph_bonus = min(graph_source_count, 4) * 2 + min(graph_official_count, 2) * 3
                if graph_bonus:
                    score += graph_bonus
                    score_breakdown.append(
                        _build_score_factor(
                            label="实体归一化覆盖",
                            score=graph_bonus,
                            note=f"归一后命中 {graph_source_count} 个来源，官方源 {graph_official_count} 个",
                        )
                    )

            state = scored.setdefault(
                name,
                {
                    "score": 0,
                    "evidence_count": 0,
                    "official_hits": 0,
                    "signals": [],
                    "links": [],
                    "score_breakdown": [],
                },
            )
            state["score"] = int(state["score"]) + score
            state["evidence_count"] = int(state["evidence_count"]) + 1
            state["official_hits"] = int(state["official_hits"]) + official_hit
            state["signals"] = _dedupe_strings([*state["signals"], *matched_signals], 4)
            existing_breakdown = list(state["score_breakdown"])
            for factor in score_breakdown:
                index = next((idx for idx, current in enumerate(existing_breakdown) if current.label == factor.label and current.note == factor.note), -1)
                if index >= 0:
                    merged = existing_breakdown[index]
                    existing_breakdown[index] = ResearchScoreFactorOut(
                        label=merged.label,
                        score=merged.score + factor.score,
                        note=merged.note,
                    )
                else:
                    existing_breakdown.append(factor)
            state["score_breakdown"] = existing_breakdown[:8]
            links = list(state["links"])
            evidence = _build_entity_evidence(source)
            if evidence.url and not any(item.url == evidence.url for item in links):
                links.append(evidence)
            state["links"] = links[:3]

    ranked = sorted(scored.items(), key=lambda item: (-int(item[1]["score"]), -int(item[1]["official_hits"]), item[0]))
    results: list[ResearchRankedEntityOut] = []
    pending: list[ResearchRankedEntityOut] = []
    used_names: set[str] = set()
    for name, state in ranked:
        if is_duplicate_name(name):
            continue
        reasoning = _build_ranked_entity_reasoning(
            output_language=output_language,
            role=role,
            official_hits=int(state["official_hits"]),
            matched_signals=list(state["signals"]),
            scope_regions=scope_regions,
            scope_industries=scope_industries,
            evidence_count=int(state["evidence_count"]),
        )
        entity = build_entity_result(
            name=name,
            score=min(100, int(state["score"])),
            reasoning=reasoning,
            score_breakdown=sorted(
                list(state["score_breakdown"]),
                key=lambda item: abs(int(item.score)),
                reverse=True,
            )[:5],
            evidence_links=list(state["links"]),
            entity_mode="instance" if has_instance_support(name, state) else "pending",
        )
        if entity.entity_mode == "instance" and len(results) < limit:
            used_names.add(name)
            results.append(entity)
            continue
        if len(pending) < limit:
            pending.append(entity)

    def is_valid_fallback_name(name: str) -> bool:
        if not name or len(name) < 3 or is_duplicate_name(name):
            return False
        if not _is_plausible_entity_name(name):
            return False
        if theme_labels and not _is_theme_aligned_entity_name(name, role=role, theme_labels=theme_labels):
            return False
        if prefer_company_entities and role in {"target", "competitor"} and not _is_company_like_entity_name(
            name,
            role=role,
            theme_labels=theme_labels,
            seed_companies=seed_companies,
        ):
            return False
        return allow_role_candidate(name, name)

    fallback_pool: list[str] = []
    if sources:
        fallback_pool.extend(seed_companies)
        for raw in fallback_values or []:
            name = _extract_rank_entity_name(str(raw))
            if name:
                graph_entity = graph_lookup.get(_entity_canonical_key(name))
                if graph_entity is not None and normalize_text(graph_entity.canonical_name):
                    name = normalize_text(graph_entity.canonical_name)
                fallback_pool.append(_resolve_known_org_name(name, scope_hints=scope_hints))
        fallback_pool.extend(_extract_org_candidates(sources, limit=48, scope_hints=scope_hints))
        if entity_graph is not None:
            fallback_pool.extend(entity.canonical_name for entity in entity_graph.entities if normalize_text(entity.canonical_name))
        fallback_pool.extend(scope_clients)
    for name in _dedupe_strings(fallback_pool, 18):
        name = _resolve_known_org_name(name, scope_hints=scope_hints)
        if len(pending) >= limit:
            break
        if not is_valid_fallback_name(name):
            continue
        related_sources = [source for source in sources if name in _source_text(source)][:3]
        graph_entity = graph_lookup.get(_entity_canonical_key(name))
        graph_source_count = int(getattr(graph_entity, "source_count", 0) or 0) if graph_entity is not None else 0
        graph_official_hits = (
            int((getattr(graph_entity, "source_tier_counts", {}) or {}).get("official", 0) or 0)
            if graph_entity is not None
            else 0
        )
        has_scope_anchor = any(client and (client in name or name in client) for client in scope_clients)
        if not related_sources and not has_scope_anchor and graph_source_count == 0:
            continue
        official_hits = max(sum(1 for source in related_sources if source.source_tier == "official"), graph_official_hits)
        evidence_links = [_build_entity_evidence(source) for source in related_sources]
        signals: list[str] = []
        for source in related_sources:
            text = _source_text(source)
            signals.extend([token for token in context_keywords if token in text])
        evidence_count = max(1, len(related_sources), graph_source_count)
        base_score = 34 + min(evidence_count, 3) * 9 + official_hits * 8
        if role == "target" and any(client and client in name for client in scope_clients):
            base_score += 8
        if role == "partner" and any(token in name for token in ("咨询", "顾问", "集成", "渠道", "联盟", "研究院", "协会")):
            base_score += 8
        if role == "competitor" and any(token in name for token in ("科技", "信息", "软件", "智能", "数据", "云")):
            base_score += 6
        if prefer_head_companies and name in seed_companies:
            base_score += 8
        pending.append(
            build_entity_result(
                name=name,
                score=min(92, base_score),
                reasoning=(
                    _build_ranked_entity_reasoning(
                        output_language=output_language,
                        role=role,
                        official_hits=official_hits,
                        matched_signals=_dedupe_strings(signals, 4),
                        scope_regions=scope_regions,
                        scope_industries=scope_industries,
                        evidence_count=evidence_count,
                    )
                    if signals
                    else _build_fallback_entity_reasoning(
                        output_language=output_language,
                        role=role,
                        evidence_count=evidence_count,
                        scope_regions=scope_regions,
                        scope_industries=scope_industries,
                    )
                ),
                score_breakdown=[
                    _build_score_factor(
                        label="范围收敛",
                        score=18,
                        note=" / ".join(scope_regions[:1] + scope_industries[:1]) or "当前关键词范围",
                    ),
                    _build_score_factor(
                        label="公开证据覆盖",
                        score=min(evidence_count, 3) * 8,
                        note=f"命中 {evidence_count} 条可用线索",
                    ),
                    _build_score_factor(
                        label="官方/招采可信度",
                        score=official_hits * 8,
                        note=f"官方或招采证据 {official_hits} 条",
                    ),
                ],
                evidence_links=evidence_links[:3],
                entity_mode="pending",
            )
        )
    if len(pending) < limit and sources:
        relaxed_pool = _dedupe_strings(
            [*seed_companies, *_extract_org_candidates(sources, limit=64, scope_hints=scope_hints), *scope_clients],
            24,
        )
        for name in relaxed_pool:
            name = _resolve_known_org_name(name, scope_hints=scope_hints)
            if len(pending) >= limit or not name or is_duplicate_name(name):
                continue
            if not allow_role_candidate(name, name):
                continue
            related_sources = [source for source in sources if name in _source_text(source)][:2]
            graph_entity = graph_lookup.get(_entity_canonical_key(name))
            graph_source_count = int(getattr(graph_entity, "source_count", 0) or 0) if graph_entity is not None else 0
            has_scope_anchor = any(client and (client in name or name in client) for client in scope_clients)
            if not related_sources and not has_scope_anchor and graph_source_count == 0:
                continue
            pending.append(
                build_entity_result(
                    name=name,
                    score=28 + min(len(related_sources), 2) * 7,
                    reasoning=_build_fallback_entity_reasoning(
                        output_language=output_language,
                        role=role,
                        evidence_count=max(1, len(related_sources)),
                        scope_regions=scope_regions,
                        scope_industries=scope_industries,
                    ),
                    score_breakdown=[
                        _build_score_factor(
                            label="弱证据补位",
                            score=18,
                            note="仅作为待补证候选，不代表高置信结论",
                        ),
                        _build_score_factor(
                            label="公开线索命中",
                            score=min(len(related_sources), 2) * 7,
                            note=f"命中 {len(related_sources)} 条相关来源",
                        ),
                    ],
                    evidence_links=[_build_entity_evidence(source) for source in related_sources][:2],
                    entity_mode="pending",
                )
            )
    if not results and not pending:
        pending.extend(build_archetype_results()[:limit])
    return results, pending


def _build_candidate_profile_support(
    profile_sources: list[SourceDocument],
    candidate_names: Iterable[str],
) -> dict[str, dict[str, object]]:
    def company_variants(value: str) -> list[str]:
        normalized = normalize_text(value)
        if not normalized:
            return []
        variants = _org_entity_variants(normalized)
        extracted = _extract_rank_entity_name(normalized)
        if extracted and extracted not in variants:
            variants.extend(_org_entity_variants(extracted))
        canonical = _entity_canonical_key(normalized)
        if canonical and canonical not in variants:
            variants.append(canonical)
        return _dedupe_strings(variants, 6)

    def known_seed_domains(value: str) -> set[str]:
        domains: set[str] = set()
        for variant in company_variants(value):
            for url, _label in KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS.get(variant, ()):
                domain = normalize_text(extract_domain(url) or "").lower()
                if domain:
                    domains.add(domain)
        return domains

    def source_supports_candidate_profile(source: SourceDocument, entity_name: str) -> bool:
        variants = company_variants(entity_name)
        if not variants:
            return False
        for variant in variants:
            if _source_mentions_entity(source, variant) and not _source_negates_entity(source, variant):
                return True
        if source.source_tier != "official":
            return False
        metadata_text = normalize_text(
            " ".join(
                [
                    source.title,
                    source.url,
                    source.source_label or "",
                    source.search_query,
                ]
            )
        ).lower()
        query_text = normalize_text(source.search_query).lower()
        domain = normalize_text(source.domain or "").lower()
        profile_like = any(token in metadata_text for token in COMPANY_PROFILE_PAGE_TOKENS)
        return bool(
            (profile_like or (domain and domain in known_seed_domains(entity_name)))
            and any(variant.lower() in query_text for variant in variants)
        )

    support: dict[str, dict[str, object]] = {}
    normalized_names = [normalize_text(name) for name in candidate_names if normalize_text(name)]
    for name in normalized_names:
        support[name] = {
            "hit_count": 0,
            "official_hit_count": 0,
            "source_labels": [],
            "evidence_links": [],
        }

    for source in profile_sources:
        evidence = _build_entity_evidence(source)
        for name in normalized_names:
            if not source_supports_candidate_profile(source, name):
                continue
            state = support[name]
            state["hit_count"] = int(state["hit_count"]) + 1
            if source.source_tier == "official":
                state["official_hit_count"] = int(state["official_hit_count"]) + 1
            labels = list(state["source_labels"])
            label = normalize_text(source.source_label or source.title or source.domain or "")
            if label and label not in labels:
                labels.append(label)
            state["source_labels"] = labels[:6]
            links = list(state["evidence_links"])
            if evidence.url and not any(item.url == evidence.url for item in links):
                links.append(evidence)
            state["evidence_links"] = links[:3]
    return support


def _promote_pending_entities_with_candidate_profiles(
    results: list[ResearchRankedEntityOut],
    pending: list[ResearchRankedEntityOut],
    *,
    candidate_profile_support: dict[str, dict[str, object]],
    limit: int = 3,
) -> tuple[list[ResearchRankedEntityOut], list[ResearchRankedEntityOut]]:
    if not candidate_profile_support:
        return results, pending

    promoted_results = list(results)
    remaining_pending: list[ResearchRankedEntityOut] = []
    used_names = {normalize_text(item.name) for item in promoted_results if normalize_text(item.name)}

    for entity in pending:
        key = normalize_text(entity.name)
        support = candidate_profile_support.get(key)
        hit_count = int((support or {}).get("hit_count", 0) or 0)
        official_hit_count = int((support or {}).get("official_hit_count", 0) or 0)
        if (
            len(promoted_results) < limit
            and support
            and (official_hit_count > 0 or hit_count >= 2)
            and key
            and key not in used_names
        ):
            existing_labels = {
                f"{factor.label}::{factor.note}": factor for factor in entity.score_breakdown
            }
            boost_factor = _build_score_factor(
                label="候选补证命中",
                score=min(18, 8 + official_hit_count * 6 + min(hit_count, 3) * 3),
                note=f"补证公开源 {hit_count} 条，官方源 {official_hit_count} 条",
            )
            existing_labels[f"{boost_factor.label}::{boost_factor.note}"] = boost_factor
            evidence_links = list(entity.evidence_links)
            for evidence in list(support.get("evidence_links", [])):
                if evidence.url and not any(item.url == evidence.url for item in evidence_links):
                    evidence_links.append(evidence)
            promoted_results.append(
                entity.model_copy(
                    update={
                        "entity_mode": "instance",
                        "score": min(100, max(int(entity.score), 58) + int(boost_factor.score)),
                        "reasoning": f"{entity.reasoning} 已补充官网/联系页/团队页公开线索，当前可升级为实例级候选。",
                        "score_breakdown": sorted(
                            existing_labels.values(),
                            key=lambda item: abs(int(item.score)),
                            reverse=True,
                        )[:5],
                        "evidence_links": evidence_links[:3],
                    }
                )
            )
            used_names.add(key)
            continue
        remaining_pending.append(entity)
    return promoted_results[:limit], remaining_pending[:limit]


def _scope_insufficient_rows(
    *,
    output_language: str,
    scope_hints: dict[str, object],
    dimension_label: str,
    limit: int,
) -> list[str]:
    anchor = normalize_text(str(scope_hints.get("anchor_text", "")))
    scope_text = anchor or localized_text(
        output_language,
        {
            "zh-CN": "当前关键词范围",
            "zh-TW": "目前關鍵詞範圍",
            "en": "the current keyword scope",
        },
        "当前关键词范围",
    )
    templates = localized_text(
        output_language,
        {
            "zh-CN": f"当前证据不足：建议继续补充 {scope_text} 的 {dimension_label} 公开线索。",
            "zh-TW": f"目前證據不足：建議繼續補充 {scope_text} 的 {dimension_label} 公開線索。",
            "en": f"Current evidence is insufficient: expand public evidence for {dimension_label} within {scope_text}.",
        },
        f"当前证据不足：建议继续补充 {scope_text} 的 {dimension_label} 公开线索。",
    )
    followups = [
        localized_text(
            output_language,
            {
                "zh-CN": f"建议追加政府采购、公共资源交易、上市公告和行业媒体对 {scope_text} 的交叉检索。",
                "zh-TW": f"建議追加政府採購、公共資源交易、上市公告與產業媒體對 {scope_text} 的交叉檢索。",
                "en": f"Add government procurement, public resource exchange, filings, and media cross-searches around {scope_text}.",
            },
            f"建议追加政府采购、公共资源交易、上市公告和行业媒体对 {scope_text} 的交叉检索。",
        ),
        localized_text(
            output_language,
            {
                "zh-CN": f"若需形成前三名单，建议继续加入甲方全称、区域或项目代号后重试。",
                "zh-TW": f"若需形成前三名單，建議加入甲方全稱、區域或專案代號後重試。",
                "en": "To derive a top-3 list, add the buyer full name, region, or project code and rerun.",
            },
            "若需形成前三名单，建议继续加入甲方全称、区域或项目代号后重试。",
        ),
    ]
    return _dedupe_strings([templates] + followups, limit)


def _build_dimension_fallback_rows(
    *,
    output_language: str,
    scope_hints: dict[str, object],
    dimension_key: str,
    dimension_label: str,
    limit: int,
) -> list[str]:
    anchor = normalize_text(str(scope_hints.get("anchor_text", "")))
    regions = [normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    industries = [normalize_text(str(item)) for item in scope_hints.get("industries", []) if normalize_text(str(item))]
    clients = [normalize_text(str(item)) for item in scope_hints.get("clients", []) if normalize_text(str(item))]
    region_text = "、".join(regions[:2]) or localized_text(
        output_language,
        {"zh-CN": "重点区域", "zh-TW": "重點區域", "en": "priority regions"},
        "重点区域",
    )
    industry_text = "、".join(industries[:2]) or anchor or localized_text(
        output_language,
        {"zh-CN": "目标行业", "zh-TW": "目標行業", "en": "target sector"},
        "目标行业",
    )
    client_text = "、".join(clients[:2]) or localized_text(
        output_language,
        {"zh-CN": "目标业主类型", "zh-TW": "目標業主類型", "en": "target buyer types"},
        "目标业主类型",
    )

    templates: dict[str, list[str]] = {
        "target_accounts": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"若当前还无法锁定具体甲方，优先在 {region_text} 内跟踪与 {industry_text} 直接相关的业主单位，如数据局、政务服务中心、信息中心、城运中心、行业主管部门或大型平台型国企。",
                    "zh-TW": f"若目前仍無法鎖定具體甲方，優先在 {region_text} 內追蹤與 {industry_text} 直接相關的業主單位，如資料局、政務服務中心、資訊中心、城運中心、行業主管部門或大型平台型國企。",
                    "en": f"If named buyers are still unclear, prioritize buyer entities in {region_text} that are directly tied to {industry_text}, such as data bureaus, digital service centers, information centers, city operation centers, sector regulators, or platform SOEs.",
                },
                f"若当前还无法锁定具体甲方，优先在 {region_text} 内跟踪与 {industry_text} 直接相关的业主单位，如数据局、政务服务中心、信息中心、城运中心、行业主管部门或大型平台型国企。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": f"把搜索范围收敛到 {client_text} + “预算/采购意向/二期/扩容/升级”，优先识别近 12 个月出现过统建、试点、一期上线后二期扩容的业主。",
                    "zh-TW": f"把檢索範圍收斂到 {client_text} +「預算/採購意向/二期/擴容/升級」，優先識別近 12 個月出現過統建、試點、一期上線後二期擴容的業主。",
                    "en": f"Narrow searches to {client_text} plus budget/procurement intention/phase-two expansion terms, prioritizing buyers that showed pilot-to-phase-two expansion in the past 12 months.",
                },
                f"把搜索范围收敛到 {client_text} + “预算/采购意向/二期/扩容/升级”，优先识别近 12 个月出现过统建、试点、一期上线后二期扩容的业主。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": f"即使暂时没有明确公司名，也应优先建立一份 {region_text} {industry_text} 的重点业主名单池，再用招标公告联系人、预算归口和项目代号反推具体甲方。",
                    "zh-TW": f"即使暫時沒有明確公司名，也應優先建立一份 {region_text} {industry_text} 的重點業主名單池，再用招標公告聯絡人、預算歸口與專案代號反推具體甲方。",
                    "en": f"Even without named companies, build a priority buyer pool for {region_text} and {industry_text}, then use tender contacts, budget owners, and project codes to infer specific accounts.",
                },
                f"即使暂时没有明确公司名，也应优先建立一份 {region_text} {industry_text} 的重点业主名单池，再用招标公告联系人、预算归口和项目代号反推具体甲方。",
            ),
        ],
        "target_departments": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"若缺少明确部门名称，优先把 {industry_text} 相关业主拆成四类部门：业务牵头部门、预算审批部门、采购招采部门、实施落地部门，并分别收集公开线索。",
                    "zh-TW": f"若缺少明確部門名稱，優先把 {industry_text} 相關業主拆成四類部門：業務牽頭、預算審批、採購招採、實施落地，並分別收集公開線索。",
                    "en": f"If department names are missing, split buyers tied to {industry_text} into four groups: business lead, budget owner, procurement, and implementation departments, then collect public signals for each.",
                },
                f"若缺少明确部门名称，优先把 {industry_text} 相关业主拆成四类部门：业务牵头部门、预算审批部门、采购招采部门、实施落地部门，并分别收集公开线索。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "优先排查采购中心、招标办、信息中心、数据局/数字化部、科技部、计划财务部、运营管理部等部门是否在公告、工作报告或组织架构中直接出现。",
                    "zh-TW": "優先排查採購中心、招標辦、資訊中心、資料局/數位化部、科技部、計畫財務部、營運管理部等部門是否在公告、工作報告或組織架構中直接出現。",
                    "en": "Prioritize procurement centers, tender offices, information centers, data/digital departments, technology teams, finance/planning, and operations functions in public notices and org disclosures.",
                },
                "优先排查采购中心、招标办、信息中心、数据局/数字化部、科技部、计划财务部、运营管理部等部门是否在公告、工作报告或组织架构中直接出现。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "如果目标是销售推进，先锁定“预算归口 + 技术把关 + 招采执行”三类部门组合，再反推关键联系人。",
                    "zh-TW": "如果目標是銷售推進，先鎖定「預算歸口 + 技術把關 + 招採執行」三類部門組合，再反推關鍵聯絡人。",
                    "en": "For sales progression, first lock the combination of budget owner, technical gatekeeper, and procurement executor, then infer the likely contacts.",
                },
                "如果目标是销售推进，先锁定“预算归口 + 技术把关 + 招采执行”三类部门组合，再反推关键联系人。",
            ),
        ],
        "public_contact_channels": [
            localized_text(
                output_language,
                {
                    "zh-CN": "优先收集公开业务入口：官网“联系我们”、采购/中标公告联系人、服务热线、投资者关系邮箱、政务公开电话。",
                    "zh-TW": "優先收集公開業務入口：官網「聯絡我們」、採購/中標公告聯絡人、服務熱線、投資者關係郵箱、政務公開電話。",
                    "en": "Collect public business channels first: official contact pages, tender contacts, hotlines, investor-relations mailboxes, and public-service phones.",
                },
                "优先收集公开业务入口：官网“联系我们”、采购/中标公告联系人、服务热线、投资者关系邮箱、政务公开电话。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": f"对于 {region_text} 的重点业主，优先从公共资源交易公告和采购意向公告中提取联系人、联系方式和代理机构信息。",
                    "zh-TW": f"對於 {region_text} 的重點業主，優先從公共資源交易公告與採購意向公告中提取聯絡人、聯絡方式與代理機構資訊。",
                    "en": f"For buyers in {region_text}, extract contacts, phone/email clues, and agency information from public procurement and tender notices.",
                },
                f"对于 {region_text} 的重点业主，优先从公共资源交易公告和采购意向公告中提取联系人、联系方式和代理机构信息。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "如果公开联系方式依旧不足，不要停在“无数据”，而应明确下一步去哪个官方公告栏目、哪个官网板块补证据。",
                    "zh-TW": "如果公開聯絡方式仍不足，不要停在「無資料」，而應明確下一步去哪個官方公告欄目、哪個官網板塊補證據。",
                    "en": "If public contact data is still weak, specify exactly which official notice pages or website sections should be checked next instead of returning blank.",
                },
                "如果公开联系方式依旧不足，不要停在“无数据”，而应明确下一步去哪个官方公告栏目、哪个官网板块补证据。",
            ),
        ],
        "budget_signals": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"若暂未拿到明确金额，优先看 {region_text} 内与 {industry_text} 相关的采购意向、预算草案、立项批复、可研批复、财政报告与年报披露。",
                    "zh-TW": f"若暫未拿到明確金額，優先查看 {region_text} 內與 {industry_text} 相關的採購意向、預算草案、立項批復、可研批復、財政報告與年報披露。",
                    "en": f"If exact amounts are missing, inspect procurement intentions, budget drafts, project approvals, feasibility approvals, fiscal reports, and filings tied to {industry_text} in {region_text}.",
                },
                f"若暂未拿到明确金额，优先看 {region_text} 内与 {industry_text} 相关的采购意向、预算草案、立项批复、可研批复、财政报告与年报披露。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "预算判断不要只盯单笔中标额，应同时跟踪总投资、年度预算、二三期扩容预算和运维服务预算。",
                    "zh-TW": "預算判斷不要只盯單筆中標額，應同時追蹤總投資、年度預算、二三期擴容預算與運維服務預算。",
                    "en": "Do not rely only on single award sizes; also track total investment, annual budgets, phase-two/three expansion budgets, and service OPEX budgets.",
                },
                "预算判断不要只盯单笔中标额，应同时跟踪总投资、年度预算、二三期扩容预算和运维服务预算。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "若金额仍缺失，可先给出高价值预算口径：平台统建、算力扩容、应用试点、集成实施、运维续费，这些口径最适合后续销售和投标拆解。",
                    "zh-TW": "若金額仍缺失，可先給出高價值預算口徑：平台統建、算力擴容、應用試點、整合實施、運維續費，這些口徑最適合後續銷售與投標拆解。",
                    "en": "If hard amounts are still missing, output the highest-value budget buckets first: platform build, capacity expansion, pilot applications, integration delivery, and renewal services.",
                },
                "若金额仍缺失，可先给出高价值预算口径：平台统建、算力扩容、应用试点、集成实施、运维续费，这些口径最适合后续销售和投标拆解。",
            ),
        ],
        "competitor_profiles": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"如果竞品公司名不够明确，先围绕 {industry_text} 抽取“高频中标方 / 集成总包 / 平台厂商 / 咨询牵线方”四类主体，再按威胁度排序。",
                    "zh-TW": f"如果競品公司名不夠明確，先圍繞 {industry_text} 抽取「高頻中標方 / 整合總包 / 平台廠商 / 諮詢牽線方」四類主體，再按威脅度排序。",
                    "en": f"If named competitors are still weak, first group entities around {industry_text} into frequent winners, integration primes, platform vendors, and connector advisors, then rank by threat.",
                },
                f"如果竞品公司名不够明确，先围绕 {industry_text} 抽取“高频中标方 / 集成总包 / 平台厂商 / 咨询牵线方”四类主体，再按威胁度排序。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "竞品画像至少要回答三件事：谁拿预算、谁有平台能力、谁掌握地方关系或交付生态。",
                    "zh-TW": "競品畫像至少要回答三件事：誰拿預算、誰有平台能力、誰掌握地方關係或交付生態。",
                    "en": "A usable competitor profile must answer three things: who captures budget, who owns the platform layer, and who controls local relationships or delivery ecosystems.",
                },
                "竞品画像至少要回答三件事：谁拿预算、谁有平台能力、谁掌握地方关系或交付生态。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "若缺少公司名，也应给出相对聚焦的竞对类型组合，方便后续继续查公司名单，而不是停在“证据不足”。",
                    "zh-TW": "若缺少公司名，也應給出相對聚焦的競對類型組合，方便後續繼續查公司名單，而不是停在「證據不足」。",
                    "en": "Even without exact names, provide a focused competitor-type cluster so the next step can resolve company names instead of stopping at 'insufficient evidence'.",
                },
                "若缺少公司名，也应给出相对聚焦的竞对类型组合，方便后续继续查公司名单，而不是停在“证据不足”。",
            ),
        ],
        "ecosystem_partners": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"生态伙伴优先找“能牵线、能带项目、能补关系或交付”的主体，而不是只看纯产品公司；在 {region_text} 内优先排查总包、集成商、咨询顾问、运营商和研究院。",
                    "zh-TW": f"生態夥伴優先找「能牽線、能帶專案、能補關係或交付」的主體，而不是只看純產品公司；在 {region_text} 內優先排查總包、整合商、諮詢顧問、運營商與研究院。",
                    "en": f"For ecosystem partners, prioritize connectors, project carriers, relationship brokers, and delivery enablers over pure product vendors, especially integrators, advisors, operators, and institutes in {region_text}.",
                },
                f"生态伙伴优先找“能牵线、能带项目、能补关系或交付”的主体，而不是只看纯产品公司；在 {region_text} 内优先排查总包、集成商、咨询顾问、运营商和研究院。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "如果短期找不到明确伙伴公司名，也至少应先圈定“咨询牵线方 + 区域总包 + 行业集成商”三种伙伴角色。",
                    "zh-TW": "如果短期找不到明確夥伴公司名，也至少應先圈定「諮詢牽線方 + 區域總包 + 行業整合商」三種夥伴角色。",
                    "en": "If partner names are still unclear, first lock three partner roles: connector advisor, regional prime, and sector integrator.",
                },
                "如果短期找不到明确伙伴公司名，也至少应先圈定“咨询牵线方 + 区域总包 + 行业集成商”三种伙伴角色。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "伙伴筛选标准应包含行业影响力、牵线概率、项目协同能力和地方落地资源，而不是只看技术强弱。",
                    "zh-TW": "夥伴篩選標準應包含行業影響力、牽線機率、專案協同能力與地方落地資源，而不是只看技術強弱。",
                    "en": "Partner screening should prioritize industry influence, introduction probability, delivery synergy, and local access instead of raw product strength alone.",
                },
                "伙伴筛选标准应包含行业影响力、牵线概率、项目协同能力和地方落地资源，而不是只看技术强弱。",
            ),
        ],
    }
    if dimension_key in templates:
        return _dedupe_strings(templates[dimension_key], limit)
    return _scope_insufficient_rows(
        output_language=output_language,
        scope_hints=scope_hints,
        dimension_label=dimension_label,
        limit=limit,
    )


def _ensure_minimum_rows(
    primary: list[str],
    *,
    backup: list[str],
    output_language: str,
    scope_hints: dict[str, object],
    dimension_key: str,
    dimension_label: str,
    min_count: int = 3,
    limit: int = 6,
) -> list[str]:
    rows = _dedupe_strings(primary + backup, limit)
    if len(rows) >= min_count:
        return rows
    fill = _build_dimension_fallback_rows(
        output_language=output_language,
        scope_hints=scope_hints,
        dimension_key=dimension_key,
        dimension_label=dimension_label,
        limit=max(min_count, 3),
    )
    return _dedupe_strings(rows + fill, limit)


def _extract_people_signals(sources: list[SourceDocument], *, limit: int) -> list[str]:
    rows = _extract_matching_sentences(
        sources,
        keywords=("董事长", "总经理", "副总裁", "主任", "局长", "厅长", "书记", "市长", "负责人", "总裁"),
        limit=limit,
    )
    return rows


def _build_source_intelligence(
    sources: list[SourceDocument],
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    scope_hints: dict[str, object],
) -> dict[str, list[str]]:
    theme_terms = _build_theme_terms(keyword, research_focus, scope_hints)
    company_anchor_rows = [
        f"{name}：关键词已明确收敛到该公司，优先补官网、采购公告与投资者关系公开线索。"
        for name in _dedupe_strings(scope_hints.get("company_anchors", []) or [], 3)
    ]
    company_contact_rows = [
        f"{name}：优先核验官网“联系我们”、商务合作入口、采购公告联系人和投资者关系邮箱。"
        for name in _dedupe_strings(scope_hints.get("company_anchors", []) or [], 3)
    ]
    company_team_rows = [
        f"{name}：优先核验其在目标区域和场景下的政企/行业方案团队、区域交付团队、商务合作团队与创新中心公开动态。"
        for name in _dedupe_strings(scope_hints.get("company_anchors", []) or [], 3)
    ]
    target_accounts = _rank_org_rows(
        sources,
        role="target",
        context_keywords=("招标", "采购", "预算", "项目", "建设", "规划", "部署"),
        preferred_source_types=("procurement", "policy", "tender_feed", "filing"),
        name_bias_tokens=("政府", "局", "委", "办", "中心", "医院", "大学", "银行", "集团", "学校", "城投", "交投"),
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        limit=6,
    )
    target_departments = _extract_department_rows(
        sources,
        scope_hints=scope_hints,
        limit=5,
    )
    public_contact_channels = _extract_public_contact_rows(
        sources,
        output_language=output_language,
        limit=5,
    )
    competitor_profiles = _rank_org_rows(
        sources,
        role="competitor",
        context_keywords=("中标", "平台", "产品", "解决方案", "合作", "厂商", "公司", "集成商"),
        preferred_source_types=("tender_feed", "tech_media_feed", "web", "filing"),
        name_bias_tokens=("科技", "信息", "软件", "智能", "云", "数据", "通信", "有限公司", "股份", "集团"),
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        limit=6,
    )
    ecosystem_partners = _rank_org_rows(
        sources,
        role="partner",
        context_keywords=("伙伴", "合作", "联合", "生态", "咨询", "集成商", "研究院", "渠道", "联盟"),
        preferred_source_types=("tech_media_feed", "web", "procurement", "policy"),
        name_bias_tokens=("集成", "咨询", "研究院", "研究所", "联盟", "科技", "信息", "公司"),
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        limit=6,
    )
    account_team_signals = _build_entity_specific_team_rows(
        sources,
        entity_names=_dedupe_strings(
            [
                *(normalize_text(str(item)) for item in scope_hints.get("company_anchors", []) if normalize_text(str(item))),
                *(_extract_rank_entity_name(item) for item in target_accounts if _extract_rank_entity_name(item)),
                *(_extract_rank_entity_name(item) for item in ecosystem_partners if _extract_rank_entity_name(item)),
            ],
            6,
        ),
        scope_hints=scope_hints,
        output_language=output_language,
        limit=5,
    )

    budget_signals = _extract_money_signals(sources, limit=6, scope_hints=scope_hints)
    project_distribution = _extract_region_distribution(sources, limit=5, scope_hints=scope_hints)
    strategic_directions = _extract_matching_sentences(
        sources,
        keywords=("战略", "规划", "路线", "顶层设计", "五年", "十四五", "三年行动", "建设目标"),
        limit=5,
        scope_hints=scope_hints,
    )
    tender_timeline = _extract_matching_sentences(
        sources,
        keywords=("招标", "采购", "投标", "开标", "中标", "公示", "征求意见", "意向公开"),
        limit=5,
        scope_hints=scope_hints,
    )
    leadership_focus = _extract_matching_sentences(
        sources,
        keywords=("讲话", "强调", "指出", "要求", "部署", "工作报告", "会议"),
        limit=5,
        scope_hints=scope_hints,
    )
    ecosystem_partner_clues = _extract_matching_sentences(
        sources,
        keywords=("合作", "伙伴", "生态", "联合", "集成商", "ISV", "渠道", "顾问", "联盟"),
        limit=6,
        scope_hints=scope_hints,
    )
    benchmark_cases = _extract_matching_sentences(
        sources,
        keywords=("试点", "示范", "标杆", "案例", "样板", "落地"),
        limit=5,
        scope_hints=scope_hints,
    )
    flagship_products = _extract_matching_sentences(
        sources,
        keywords=("平台", "产品", "解决方案", "系统", "大模型", "云", "套件"),
        limit=5,
        scope_hints=scope_hints,
    )
    key_people = _extract_key_people_rows(sources, scope_hints=scope_hints, limit=5) or _extract_people_signals(sources, limit=5)

    if not project_distribution:
        project_distribution = _extract_matching_sentences(
            sources,
            keywords=("二期", "三期", "四期", "扩建", "升级", "场景"),
            limit=5,
            scope_hints=scope_hints,
        )

    client_peer_moves = target_accounts[:3]
    winner_peer_moves = _extract_matching_sentences(
        sources,
        keywords=("中标", "成交", "联合体", "总包", "厂商", "集成商", "平台"),
        limit=6,
        scope_hints=scope_hints,
    )
    if not winner_peer_moves:
        winner_peer_moves = competitor_profiles[:3]

    competition_analysis = _dedupe_strings(
        competitor_profiles[:2]
        + winner_peer_moves[:2]
        + _extract_matching_sentences(
            sources,
            keywords=("竞争", "优势", "差异化", "资质", "案例", "生态"),
            limit=4,
            scope_hints=scope_hints,
        ),
        5,
    )
    five_year_outlook = _extract_matching_sentences(
        sources,
        keywords=("未来五年", "五年", "二期", "三期", "四期", "扩容", "平台化", "升级"),
        limit=5,
        scope_hints=scope_hints,
    )
    if not five_year_outlook:
        anchor = normalize_text(str(scope_hints.get("anchor_text", ""))) or keyword
        five_year_outlook = _dedupe_strings(
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
        "target_accounts": _ensure_minimum_rows(
            target_accounts,
            backup=company_anchor_rows,
            output_language=output_language,
            scope_hints=scope_hints,
            dimension_key="target_accounts",
            dimension_label=localized_text(output_language, {"zh-CN": "重点甲方", "zh-TW": "重點甲方", "en": "target accounts"}, "重点甲方"),
        ),
        "target_departments": _ensure_minimum_rows(
            target_departments,
            backup=_extract_matching_sentences(
                sources,
                keywords=("采购中心", "招标办", "信息中心", "数据局", "科技部", "财务部"),
                limit=5,
                scope_hints=scope_hints,
            ),
            output_language=output_language,
            scope_hints=scope_hints,
            dimension_key="target_departments",
            dimension_label=localized_text(output_language, {"zh-CN": "决策部门", "zh-TW": "決策部門", "en": "decision departments"}, "决策部门"),
        ),
        "public_contact_channels": _ensure_minimum_rows(
            public_contact_channels,
            backup=company_contact_rows,
            output_language=output_language,
            scope_hints=scope_hints,
            dimension_key="public_contact_channels",
            dimension_label=localized_text(output_language, {"zh-CN": "公开联系方式", "zh-TW": "公開聯絡方式", "en": "public contact channels"}, "公开联系方式"),
        ),
        "account_team_signals": _ensure_minimum_rows(
            account_team_signals,
            backup=company_team_rows,
            output_language=output_language,
            scope_hints=scope_hints,
            dimension_key="account_team_signals",
            dimension_label=localized_text(output_language, {"zh-CN": "活跃团队情报", "zh-TW": "活躍團隊情報", "en": "active team signals"}, "活跃团队情报"),
        ),
        "budget_signals": _ensure_minimum_rows(
            budget_signals,
            backup=tender_timeline[:2],
            output_language=output_language,
            scope_hints=scope_hints,
            dimension_key="budget_signals",
            dimension_label=localized_text(output_language, {"zh-CN": "预算与投资信号", "zh-TW": "預算與投資信號", "en": "budget signals"}, "预算与投资信号"),
        ),
        "project_distribution": _ensure_minimum_rows(
            project_distribution,
            backup=_extract_matching_sentences(
                sources,
                keywords=("二期", "三期", "四期", "扩建", "区域"),
                limit=5,
                scope_hints=scope_hints,
            ),
            output_language=output_language,
            scope_hints=scope_hints,
            dimension_key="project_distribution",
            dimension_label=localized_text(output_language, {"zh-CN": "项目分布", "zh-TW": "專案分佈", "en": "project distribution"}, "项目分布"),
        ),
        "strategic_directions": _ensure_minimum_rows(
            strategic_directions,
            backup=leadership_focus[:2],
            output_language=output_language,
            scope_hints=scope_hints,
            dimension_key="strategic_directions",
            dimension_label=localized_text(output_language, {"zh-CN": "战略方向", "zh-TW": "戰略方向", "en": "strategic directions"}, "战略方向"),
        ),
        "tender_timeline": _ensure_minimum_rows(
            tender_timeline,
            backup=budget_signals[:2],
            output_language=output_language,
            scope_hints=scope_hints,
            dimension_key="tender_timeline",
            dimension_label=localized_text(output_language, {"zh-CN": "招标时间预测", "zh-TW": "招標時間預測", "en": "tender timeline"}, "招标时间预测"),
        ),
        "leadership_focus": _ensure_minimum_rows(
            leadership_focus,
            backup=_extract_matching_sentences(
                sources,
                keywords=("工作报告", "部署", "强调", "要求"),
                limit=5,
                scope_hints=scope_hints,
            ),
            output_language=output_language,
            scope_hints=scope_hints,
            dimension_key="leadership_focus",
            dimension_label=localized_text(output_language, {"zh-CN": "领导关注点", "zh-TW": "領導關注點", "en": "leadership focus"}, "领导关注点"),
        ),
        "ecosystem_partners": _ensure_minimum_rows(
            ecosystem_partners,
            backup=ecosystem_partner_clues,
            output_language=output_language,
            scope_hints=scope_hints,
            dimension_key="ecosystem_partners",
            dimension_label=localized_text(output_language, {"zh-CN": "生态伙伴", "zh-TW": "生態夥伴", "en": "ecosystem partners"}, "生态伙伴"),
        ),
        "competitor_profiles": _ensure_minimum_rows(
            competitor_profiles,
            backup=winner_peer_moves,
            output_language=output_language,
            scope_hints=scope_hints,
            dimension_key="competitor_profiles",
            dimension_label=localized_text(output_language, {"zh-CN": "竞品公司", "zh-TW": "競品公司", "en": "competitor profiles"}, "竞品公司"),
        ),
        "benchmark_cases": _ensure_minimum_rows(
            benchmark_cases,
            backup=_extract_matching_sentences(
                sources,
                keywords=("案例", "示范", "试点", "样板"),
                limit=5,
                scope_hints=scope_hints,
            ),
            output_language=output_language,
            scope_hints=scope_hints,
            dimension_key="benchmark_cases",
            dimension_label=localized_text(output_language, {"zh-CN": "标杆案例", "zh-TW": "標竿案例", "en": "benchmark cases"}, "标杆案例"),
        ),
        "flagship_products": _ensure_minimum_rows(
            flagship_products,
            backup=_extract_matching_sentences(
                sources,
                keywords=("平台", "产品", "系统", "解决方案"),
                limit=5,
                scope_hints=scope_hints,
            ),
            output_language=output_language,
            scope_hints=scope_hints,
            dimension_key="flagship_products",
            dimension_label=localized_text(output_language, {"zh-CN": "明星产品", "zh-TW": "明星產品", "en": "flagship products"}, "明星产品"),
        ),
        "key_people": _ensure_minimum_rows(
            key_people,
            backup=_extract_matching_sentences(sources, keywords=("董事长", "总经理", "局长", "主任"), limit=5),
            output_language=output_language,
            scope_hints=scope_hints,
            dimension_key="key_people",
            dimension_label=localized_text(output_language, {"zh-CN": "关键人物", "zh-TW": "關鍵人物", "en": "key people"}, "关键人物"),
        ),
        "client_peer_moves": _ensure_minimum_rows(
            client_peer_moves,
            backup=target_accounts + company_anchor_rows,
            output_language=output_language,
            scope_hints=scope_hints,
            dimension_key="client_peer_moves",
            dimension_label=localized_text(output_language, {"zh-CN": "甲方同行", "zh-TW": "甲方同行", "en": "buyer peer moves"}, "甲方同行"),
        ),
        "winner_peer_moves": _ensure_minimum_rows(
            winner_peer_moves,
            backup=competitor_profiles,
            output_language=output_language,
            scope_hints=scope_hints,
            dimension_key="winner_peer_moves",
            dimension_label=localized_text(output_language, {"zh-CN": "中标方同行", "zh-TW": "中標方同行", "en": "winner peer moves"}, "中标方同行"),
        ),
        "competition_analysis": _ensure_minimum_rows(
            competition_analysis,
            backup=competitor_profiles[:2] + ecosystem_partners[:1],
            output_language=output_language,
            scope_hints=scope_hints,
            dimension_key="competition_analysis",
            dimension_label=localized_text(output_language, {"zh-CN": "竞争分析", "zh-TW": "競爭分析", "en": "competition analysis"}, "竞争分析"),
        ),
        "five_year_outlook": _ensure_minimum_rows(
            five_year_outlook,
            backup=strategic_directions[:2],
            output_language=output_language,
            scope_hints=scope_hints,
            dimension_key="five_year_outlook",
            dimension_label=localized_text(output_language, {"zh-CN": "未来五年演化", "zh-TW": "未來五年演化", "en": "five-year outlook"}, "未来五年演化"),
        ),
    }

    methodology_rows = _build_industry_methodology_rows(
        scope_hints=scope_hints,
        output_language=output_language,
        scope_anchor=normalize_text(str(scope_hints.get("anchor_text", ""))) or keyword,
    )
    for field_key, rows in methodology_rows.items():
        if not rows:
            continue
        limit = 5 if field_key in {"industry_brief", "solution_design", "sales_strategy", "bidding_strategy", "outreach_strategy", "ecosystem_strategy"} else 4
        intelligence[field_key] = _dedupe_strings(rows + intelligence.get(field_key, []), limit)

    if research_focus:
        intelligence["strategic_directions"] = _dedupe_strings(
            [f"{normalize_text(research_focus)}"] + intelligence["strategic_directions"],
            5,
        )
    return intelligence


def _merge_result_with_intelligence(
    parsed: ResearchReportResult,
    intelligence: dict[str, list[str]],
) -> ResearchReportResult:
    payload = parsed.model_dump(mode="python")
    grounded_first_fields = {
        "public_contact_channels",
        "budget_signals",
        "project_distribution",
        "strategic_directions",
        "tender_timeline",
        "leadership_focus",
        "benchmark_cases",
        "flagship_products",
        "key_people",
        "five_year_outlook",
        "client_peer_moves",
        "winner_peer_moves",
        "competition_analysis",
    }
    min_count_overrides = {
        "target_accounts": 3,
        "target_departments": 3,
        "public_contact_channels": 3,
        "account_team_signals": 3,
        "budget_signals": 3,
        "project_distribution": 3,
        "strategic_directions": 3,
        "tender_timeline": 3,
        "leadership_focus": 3,
        "ecosystem_partners": 3,
        "competitor_profiles": 3,
        "benchmark_cases": 3,
        "flagship_products": 3,
        "key_people": 3,
        "five_year_outlook": 3,
        "client_peer_moves": 3,
        "winner_peer_moves": 3,
        "competition_analysis": 3,
    }
    for key, values in intelligence.items():
        current = _sanitize_report_field_rows(key, payload.get(key, []))
        sanitized_values = _sanitize_report_field_rows(key, values)
        min_count = min_count_overrides.get(key, 2)
        if key in grounded_first_fields and sanitized_values:
            payload[key] = sanitized_values
            continue
        if len(current) >= min_count:
            payload[key] = current
            continue
        payload[key] = _sanitize_report_field_rows(
            key,
            _dedupe_strings(current + sanitized_values, max(6, min_count)),
        )
    for key, values in list(payload.items()):
        if isinstance(values, list):
            payload[key] = _sanitize_report_field_rows(key, values)
    return ResearchReportResult.model_validate(payload)


def _source_quality_level(sources: list[SourceDocument]) -> str:
    if not sources:
        return "low"
    official_count = sum(1 for source in sources if source.source_tier == "official")
    official_ratio = official_count / max(len(sources), 1)
    if official_count >= 4 or official_ratio >= 0.55:
        return "high"
    if official_count >= 2 or official_ratio >= 0.3:
        return "medium"
    return "low"


def _official_coverage_is_weak(
    sources: list[SourceDocument],
    *,
    min_ratio: float,
    min_count: int,
) -> bool:
    if not sources:
        return True
    official_count = sum(1 for source in sources if source.source_tier == "official")
    official_ratio = official_count / max(len(sources), 1)
    return official_count < min_count or official_ratio < min_ratio


def _evidence_density_level(sources: list[SourceDocument], parsed: ResearchReportResult) -> str:
    if not sources:
        return "low"
    concrete_groups = 0
    for values in (
        parsed.target_accounts,
        parsed.target_departments,
        parsed.public_contact_channels,
        parsed.account_team_signals,
        parsed.budget_signals,
        parsed.project_distribution,
        parsed.strategic_directions,
        parsed.tender_timeline,
        parsed.leadership_focus,
        parsed.ecosystem_partners,
        parsed.competitor_profiles,
        parsed.benchmark_cases,
        parsed.flagship_products,
        parsed.key_people,
        parsed.five_year_outlook,
        parsed.client_peer_moves,
        parsed.winner_peer_moves,
        parsed.competition_analysis,
    ):
        if _concrete_rows(values):
            concrete_groups += 1
    if len(sources) >= 8 and concrete_groups >= 8:
        return "high"
    if len(sources) >= 4 and concrete_groups >= 4:
        return "medium"
    return "low"


def _extract_section_anchor_terms(section_title: str, items: list[str]) -> list[str]:
    seeds = [normalize_text(section_title)] + [normalize_text(item) for item in items[:4]]
    phrases: list[str] = []
    split_markers = ("正在", "围绕", "通過", "通过", "面向", "提供", "推进", "布局", "联合", "依托", "适合", "加速")
    for seed in seeds:
        if not seed:
            continue
        primary = re.split(r"[：:；;。.!?\n]", seed, maxsplit=1)[0].strip()
        if len(primary) >= 4 and primary not in phrases:
            phrases.append(primary)
        for marker in split_markers:
            if marker not in primary:
                continue
            head = primary.split(marker, 1)[0].strip(" ，,、；;:：")
            if 2 <= len(head) <= 24 and head not in phrases:
                phrases.append(head)
        for token in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", seed):
            lowered = token.lower()
            if len(lowered) >= 2 and lowered not in phrases:
                phrases.append(lowered)
    return phrases[:16]


def _build_section_evidence_links(
    *,
    section_title: str,
    items: list[str],
    sources: list[SourceDocument],
    limit: int = 3,
) -> tuple[list[ResearchEntityEvidenceOut], dict[str, int], float]:
    anchor_terms = _extract_section_anchor_terms(section_title, items)
    if not anchor_terms or not sources:
        return [], {}, 0.0
    scored: list[tuple[int, SourceDocument, list[str]]] = []
    for source in sources:
        haystack = normalize_text(
            " ".join(
                part
                for part in [
                    source.title,
                    source.snippet,
                    source.excerpt,
                    source.search_query,
                    source.source_label or "",
                ]
                if normalize_text(part)
            )
        ).lower()
        if not haystack:
            continue
        matched_terms = [term for term in anchor_terms if term and term.lower() in haystack]
        if not matched_terms:
            continue
        score = len(matched_terms) * 5
        if source.source_tier == "official":
            score += 8
        elif source.source_tier == "aggregate":
            score += 3
        if normalize_text(section_title).lower() and normalize_text(section_title).lower() in haystack:
            score += 4
        scored.append((score, source, matched_terms[:3]))
    if not scored:
        return [], {}, 0.0
    scored.sort(
        key=lambda item: (
            item[0],
            1 if item[1].source_tier == "official" else 0,
            len(item[2]),
        ),
        reverse=True,
    )
    support_rows = scored[: max(limit + 2, 4)]
    tier_counts: Counter[str] = Counter()
    for _, source, _ in support_rows:
        tier_counts[source.source_tier or "media"] += 1
    official_ratio = (
        float(tier_counts.get("official", 0)) / max(sum(tier_counts.values()), 1)
        if tier_counts
        else 0.0
    )
    links: list[ResearchEntityEvidenceOut] = []
    seen_urls: set[str] = set()
    for _, source, matched_terms in scored:
        if source.url in seen_urls:
            continue
        seen_urls.add(source.url)
        links.append(
            ResearchEntityEvidenceOut(
                title=source.title,
                url=source.url,
                source_label=source.source_label,
                source_tier=source.source_tier if source.source_tier in {"official", "media", "aggregate"} else "media",
                anchor_text=" / ".join(matched_terms[:2]),
                excerpt=_excerpt_for_evidence(source, matched_terms=matched_terms[:2]),
            )
        )
        if len(links) >= max(1, limit):
            break
    return links, dict(tier_counts), round(official_ratio, 3)


def _section_signal_quality(
    items: list[str],
    sources: list[SourceDocument],
    *,
    evidence_links: list[ResearchEntityEvidenceOut] | None = None,
    source_tier_counts: dict[str, int] | None = None,
    official_source_ratio: float = 0.0,
) -> tuple[str, str, str]:
    concrete_count = len(_concrete_rows(items))
    tier_counts = Counter(source_tier_counts or {})
    support_count = sum(tier_counts.values()) if tier_counts else len(evidence_links or [])
    official_count = int(tier_counts.get("official", 0))
    anchor_count = len(evidence_links or [])
    if concrete_count >= 3 and support_count >= 3 and official_count >= 1:
        return "high", "high", f"已锚定 {anchor_count or support_count} 条来源，其中官方源占比较高。"
    if concrete_count >= 2 and support_count >= 2:
        return (
            "medium",
            "medium" if official_count >= 1 or official_source_ratio >= 0.3 else "low",
            f"已锚定 {anchor_count or support_count} 条来源，建议继续补官方源与专项交叉验证。",
        )
    if concrete_count >= 2 and sources:
        return "medium", "medium" if official_count >= 1 else "low", "已有可用线索，建议继续补更多定向证据。"
    return "low", "low" if official_count == 0 else "medium", "当前证据较弱，更多结论应视为待验证线索。"


def _section_evidence_quota(section_key: str, items: list[str]) -> int:
    critical_sections = {
        "commercial_opportunities",
        "sales_strategy",
        "bidding_strategy",
        "outreach_strategy",
        "target_accounts",
        "target_departments",
        "public_contact_channels",
        "budget_signals",
        "tender_timeline",
        "ecosystem_partners",
        "competitor_profiles",
        "benchmark_cases",
    }
    if section_key in critical_sections:
        return 2 if len(items) >= 2 else 1
    if len(items) >= 4:
        return 2
    return 1 if items else 0


def _section_quota_note(
    *,
    section_title: str,
    evidence_count: int,
    evidence_quota: int,
    official_source_ratio: float,
) -> tuple[bool, int, str]:
    if evidence_quota <= 0:
        return True, 0, ""
    quota_gap = max(evidence_quota - evidence_count, 0)
    if quota_gap <= 0:
        if official_source_ratio >= 0.3:
            return True, 0, f"{section_title} 已满足证据配额，且已有官方源支撑。"
        return True, 0, f"{section_title} 已满足证据配额。"
    if evidence_count >= 1 and official_source_ratio >= 0.35:
        return True, 0, f"{section_title} 当前证据条数未满配额，但已有官方源可作为首轮判断支撑。"
    return False, quota_gap, f"{section_title} 还缺 {quota_gap} 条高相关证据，建议继续补官方源或专项交叉验证。"


def _section_next_verification_steps(
    *,
    section_title: str,
    output_language: str,
    evidence_density: str,
    source_quality: str,
    official_source_ratio: float,
    evidence_count: int,
    evidence_quota: int,
    contradiction_detected: bool,
) -> list[str]:
    normalized_title = normalize_text(section_title).lower()
    quota_gap = max(int(evidence_quota or 0) - int(evidence_count or 0), 0)
    steps: list[str] = []

    if any(token in normalized_title for token in ("联系", "contact", "部门", "department", "商务", "组织")):
        source_hint = localized_text(
            output_language,
            {
                "zh-CN": "官网联系页、采购公告联系人和公开职责说明",
                "zh-TW": "官網聯絡頁、採購公告聯絡人與公開職責說明",
                "en": "official contact pages, procurement contacts, and public org-role pages",
            },
            "官网联系页、采购公告联系人和公开职责说明",
        )
    elif any(token in normalized_title for token in ("预算", "招标", "投标", "采购", "项目", "tender", "budget", "project")):
        source_hint = localized_text(
            output_language,
            {
                "zh-CN": "采购公告、招标文件、预算批复和项目立项/中标公告",
                "zh-TW": "採購公告、招標文件、預算批覆與專案立項/中標公告",
                "en": "procurement notices, tender files, budget approvals, and project / award notices",
            },
            "采购公告、招标文件、预算批复和项目立项/中标公告",
        )
    elif any(token in normalized_title for token in ("竞品", "伙伴", "生态", "案例", "benchmark", "partner", "competitor")):
        source_hint = localized_text(
            output_language,
            {
                "zh-CN": "官网案例页、合作发布和中标/落地公告",
                "zh-TW": "官網案例頁、合作發布與中標/落地公告",
                "en": "official case pages, partnership releases, and award / deployment announcements",
            },
            "官网案例页、合作发布和中标/落地公告",
        )
    else:
        source_hint = localized_text(
            output_language,
            {
                "zh-CN": "官网、政策/采购公告和公开披露页",
                "zh-TW": "官網、政策/採購公告與公開披露頁",
                "en": "official sites, policy / procurement notices, and public disclosure pages",
            },
            "官网、政策/采购公告和公开披露页",
        )

    if contradiction_detected:
        steps.append(
            localized_text(
                output_language,
                {
                    "zh-CN": f"优先回到 {source_hint} 核对冲突口径，并把“已确认 / 待确认”线索分开记录。",
                    "zh-TW": f"優先回到 {source_hint} 核對衝突口徑，並把「已確認 / 待確認」線索分開記錄。",
                    "en": f"Recheck conflicting claims against {source_hint}, and separate confirmed vs. pending signals.",
                },
                f"优先回到 {source_hint} 核对冲突口径，并把“已确认 / 待确认”线索分开记录。",
            )
        )
    if quota_gap > 0:
        steps.append(
            localized_text(
                output_language,
                {
                    "zh-CN": f"至少再补 {quota_gap} 条高相关公开证据，优先从 {source_hint} 里补齐。",
                    "zh-TW": f"至少再補 {quota_gap} 條高相關公開證據，優先從 {source_hint} 補齊。",
                    "en": f"Add at least {quota_gap} more high-relevance public evidence items, prioritizing {source_hint}.",
                },
                f"至少再补 {quota_gap} 条高相关公开证据，优先从 {source_hint} 里补齐。",
            )
        )
    if official_source_ratio < 0.3:
        steps.append(
            localized_text(
                output_language,
                {
                    "zh-CN": f"至少补 1 条来自 {source_hint} 的官方或准官方来源，降低媒体/聚合源偏差。",
                    "zh-TW": f"至少補 1 條來自 {source_hint} 的官方或準官方來源，降低媒體/聚合源偏差。",
                    "en": f"Add at least one official or near-official source from {source_hint} to reduce media / aggregator bias.",
                },
                f"至少补 1 条来自 {source_hint} 的官方或准官方来源，降低媒体/聚合源偏差。",
            )
        )
    if evidence_density == "low" or source_quality == "low":
        steps.append(
            localized_text(
                output_language,
                {
                    "zh-CN": f"把 {section_title} 拆成更具体的实体、项目编号或时间窗，再做一轮定向补证。",
                    "zh-TW": f"把 {section_title} 拆成更具體的實體、專案編號或時間窗，再做一輪定向補證。",
                    "en": f"Split {section_title} into more concrete entities, project IDs, or time windows before another targeted evidence pass.",
                },
                f"把 {section_title} 拆成更具体的实体、项目编号或时间窗，再做一轮定向补证。",
            )
    )
    return _dedupe_strings(steps, 3)


def _section_insufficiency_profile(
    *,
    section_title: str,
    output_language: str,
    evidence_density: str,
    source_quality: str,
    official_source_ratio: float,
    quota_gap: int,
    contradiction_detected: bool,
) -> tuple[str, list[str], str]:
    reasons: list[str] = []
    if contradiction_detected:
        reasons.append(
            localized_text(
                output_language,
                {
                    "zh-CN": "当前存在冲突表述，需先回到同一口径核对“已确认 / 待确认”信息。",
                    "zh-TW": "目前存在衝突表述，需先回到同一口徑核對「已確認 / 待確認」資訊。",
                    "en": "Conflicting claims are present. Recheck confirmed vs. pending signals against a consistent source set first.",
                },
                "当前存在冲突表述，需先回到同一口径核对“已确认 / 待确认”信息。",
            )
        )
    if quota_gap > 0:
        reasons.append(
            localized_text(
                output_language,
                {
                    "zh-CN": f"高相关证据配额仍缺 {quota_gap} 条，当前结论还不够稳。",
                    "zh-TW": f"高相關證據配額仍缺 {quota_gap} 條，目前結論仍不夠穩。",
                    "en": f"The section is still short of {quota_gap} high-relevance evidence items.",
                },
                f"高相关证据配额仍缺 {quota_gap} 条，当前结论还不够稳。",
            )
        )
    if official_source_ratio < 0.3:
        reasons.append(
            localized_text(
                output_language,
                {
                    "zh-CN": "官方或准官方来源占比偏低，媒体/聚合源偏差还没有压下来。",
                    "zh-TW": "官方或準官方來源佔比偏低，媒體/聚合來源偏差仍未壓下來。",
                    "en": "Official or near-official source coverage is still too low.",
                },
                "官方或准官方来源占比偏低，媒体/聚合源偏差还没有压下来。",
            )
        )
    if evidence_density == "low":
        reasons.append(
            localized_text(
                output_language,
                {
                    "zh-CN": "直接证据密度偏低，章节判断更多还是线索归纳，不是强验证结论。",
                    "zh-TW": "直接證據密度偏低，章節判斷仍偏線索歸納，還不是強驗證結論。",
                    "en": "Direct evidence density is low, so this section is still more indicative than verified.",
                },
                "直接证据密度偏低，章节判断更多还是线索归纳，不是强验证结论。",
            )
        )
    if source_quality == "low":
        reasons.append(
            localized_text(
                output_language,
                {
                    "zh-CN": "来源质量偏低，仍需补更多官方页、采购页或公开披露页。",
                    "zh-TW": "來源品質偏低，仍需補更多官方頁、採購頁或公開披露頁。",
                    "en": "Source quality is low; more official, procurement, or disclosure pages are needed.",
                },
                "来源质量偏低，仍需补更多官方页、采购页或公开披露页。",
            )
        )

    deduped = _dedupe_strings(reasons, 4)
    if contradiction_detected or quota_gap > 0 or evidence_density == "low":
        status = "needs_evidence"
    elif deduped:
        status = "degraded"
    else:
        status = "ready"
    if deduped:
        summary = localized_text(
            output_language,
            {
                "zh-CN": f"{section_title} 当前仍未达到稳定推进门槛：{'；'.join(deduped[:2])}",
                "zh-TW": f"{section_title} 目前仍未達到穩定推進門檻：{'；'.join(deduped[:2])}",
                "en": f"{section_title} is still below the execution threshold: {'; '.join(deduped[:2])}",
            },
            f"{section_title} 当前仍未达到稳定推进门槛：{'；'.join(deduped[:2])}",
        )
    else:
        summary = localized_text(
            output_language,
            {
                "zh-CN": f"{section_title} 当前章节证据结构已达到首轮推进门槛。",
                "zh-TW": f"{section_title} 目前章節證據結構已達到首輪推進門檻。",
                "en": f"{section_title} has reached the first-pass evidence threshold.",
            },
            f"{section_title} 当前章节证据结构已达到首轮推进门槛。",
        )
    return status, deduped, summary


def _primary_section_items(report: ResearchReportDocument, aliases: tuple[str, ...]) -> list[str]:
    section = _research_section(report, aliases)
    if section:
        return [normalize_text(item) for item in section.items if normalize_text(item)]
    return []


def _resolved_report_readiness(report: ResearchReportDocument) -> ResearchReportReadinessOut:
    readiness = report.report_readiness if getattr(report, "report_readiness", None) else None
    if readiness and (
        int(getattr(readiness, "score", 0) or 0) > 0
        or bool(getattr(readiness, "reasons", []))
        or bool(getattr(readiness, "missing_axes", []))
        or bool(getattr(readiness, "next_verification_steps", []))
    ):
        return readiness
    return _build_report_readiness(report)


def _is_low_signal_execution_report(report: ResearchReportDocument) -> bool:
    title = normalize_text(getattr(report, "report_title", ""))
    if title.endswith(("待核验清单与补证路径", "待核驗清單與補證路徑", "Verification Backlog and Evidence Path")):
        return True
    diagnostics = report.source_diagnostics if getattr(report, "source_diagnostics", None) else ResearchSourceDiagnosticsOut()
    readiness = _resolved_report_readiness(report)
    official_ratio = float(diagnostics.official_source_ratio or 0.0)
    target_names = _dedupe_strings(
        [
            _sanitize_entity_row("target_accounts", normalize_text(name))
            for name in [
                *(normalize_text(item.name) for item in report.top_target_accounts if normalize_text(item.name)),
                *(normalize_text(item) for item in report.target_accounts if normalize_text(item)),
            ]
            if normalize_text(name)
        ],
        4,
    )
    actionable_budget_rows = [row for row in report.budget_signals if _is_actionable_budget_row(row)]
    return (
        readiness.status == "needs_evidence"
        or (readiness.status != "ready" and not target_names and not actionable_budget_rows)
        or (readiness.status == "degraded" and official_ratio < 0.12 and not target_names)
    ) and (
        int(getattr(report, "source_count", 0) or 0) < 3
        or diagnostics.evidence_mode == "fallback"
        or official_ratio < 0.15
        or diagnostics.retrieval_quality == "low"
        or (not target_names and not actionable_budget_rows)
    )


def _build_commercial_summary(report: ResearchReportDocument) -> ResearchCommercialSummaryOut:
    if _is_low_signal_execution_report(report):
        output_language = getattr(report, "output_language", "zh-CN")
        return ResearchCommercialSummaryOut(
            account_focus=[],
            budget_signal="",
            entry_window="",
            competition_or_partner="",
            next_action=localized_text(
                output_language,
                {
                    "zh-CN": "先补官网、公告、采购和联系人线索，再决定是否进入正式推进。",
                    "zh-TW": "先補官網、公告、採購與聯絡人線索，再決定是否進入正式推進。",
                    "en": "Add official pages, notices, procurement records, and contact evidence before deciding whether to enter formal execution.",
                },
                "先补官网、公告、采购和联系人线索，再决定是否进入正式推进。",
            ),
        )
    diagnostics = report.source_diagnostics if getattr(report, "source_diagnostics", None) else ResearchSourceDiagnosticsOut()
    theme_labels = _theme_labels_from_scope(
        {
            "industries": list(diagnostics.scope_industries),
            "regions": list(diagnostics.scope_regions),
            "clients": list(diagnostics.scope_clients),
        },
        keyword=report.keyword,
        research_focus=report.research_focus,
    )
    account_focus = _dedupe_strings(
        [
            normalize_text(name)
            for name in [
                *_entity_names_from_ranked(report.top_target_accounts, report.target_accounts, limit=3),
                *(normalize_text(item) for item in report.target_accounts if normalize_text(item)),
            ]
            if normalize_text(name)
            and not _looks_like_scope_prompt_noise(normalize_text(name))
            and not _looks_like_placeholder_entity_name(normalize_text(name))
            and not _looks_like_fragment_entity_name(normalize_text(name))
            and not _contains_low_value_entity_token(normalize_text(name))
            and (
                _is_trustworthy_scope_client_name(normalize_text(name), theme_labels=theme_labels)
                or _is_theme_aligned_entity_name(normalize_text(name), role="target", theme_labels=theme_labels)
                or _is_lightweight_entity_name(normalize_text(name))
            )
        ],
        3,
    )
    competitor_names = _entity_display_labels(
        [
            *(normalize_text(item.name) for item in report.top_competitors if normalize_text(item.name)),
            *(normalize_text(item) for item in report.competitor_profiles if normalize_text(item)),
        ],
        limit=2,
    )
    partner_names = _entity_display_labels(
        [
            *(normalize_text(item.name) for item in report.top_ecosystem_partners if normalize_text(item.name)),
            *(normalize_text(item) for item in report.ecosystem_partners if normalize_text(item)),
        ],
        limit=2,
    )
    competition_or_partner_parts: list[str] = []
    if competitor_names:
        competition_or_partner_parts.append(f"竞品侧重点关注 {'、'.join(competitor_names[:2])}")
    if partner_names:
        competition_or_partner_parts.append(f"伙伴侧可优先联动 {'、'.join(partner_names[:2])}")
    competition_or_partner = "；".join(competition_or_partner_parts)
    budget_signal_rows = [row for row in report.budget_signals if _is_actionable_budget_row(row)]
    budget_signal = normalize_text(
        (
            _summary_fact_rows(budget_signal_rows, limit=1)
            or _summary_fact_rows(report.project_distribution, limit=1)
            or [""]
        )[0]
    )
    entry_window = normalize_text((report.tender_timeline or [""])[0]) or _derive_entry_window(report, report.output_language)
    primary_accounts = "、".join(account_focus[:2])
    department_hint = _truncate_sentence(normalize_text((report.target_departments or report.account_team_signals or [""])[0]), 56)
    contact_rows = [
        row
        for row in report.public_contact_channels
        if _is_useful_public_contact_row(row) and not _looks_like_placeholder_contact_row(row)
    ]
    contact_hint = _truncate_sentence(normalize_text((contact_rows or [""])[0]), 56)
    benchmark_rows = [
        row
        for row in report.benchmark_cases
        if normalize_text(row)
        and not _looks_like_source_artifact_text(row)
        and not any(token in normalize_text(row) for token in FIELD_ROW_NOISE_TOKENS)
    ]
    benchmark_hint = _truncate_sentence(normalize_text((benchmark_rows or [""])[0]), 56)
    next_action_steps: list[str] = []
    if account_focus:
        if department_hint:
            next_action_steps.append(f"先围绕{primary_accounts}锁定{department_hint}这类业务或预算牵头部门")
        else:
            next_action_steps.append(f"先围绕{primary_accounts}确认业务牵头部门和预算归口")
    else:
        next_action_steps.append("先把主题收敛到 1-2 个重点账户，再补业务牵头部门和预算归口")
    if budget_signal:
        next_action_steps.append(f"结合“{budget_signal}”倒排会前材料和拜访节奏")
    elif entry_window:
        next_action_steps.append(f"围绕“{entry_window}”倒排接触窗口和方案节奏")
    if contact_hint:
        next_action_steps.append(f"同步核验{contact_hint}等公开触达入口")
    elif benchmark_hint:
        next_action_steps.append(f"首轮沟通带上“{benchmark_hint}”这类标杆案例")
    if competitor_names and partner_names:
        next_action_steps.append(f"准备针对{competitor_names[0]}的差异化切口，并评估{partner_names[0]}是否适合牵线")
    elif competitor_names:
        next_action_steps.append(f"准备针对{competitor_names[0]}的差异化切口")
    elif partner_names:
        next_action_steps.append(f"评估{partner_names[0]}是否适合作为牵线或联合推进伙伴")
    next_action = _truncate_sentence("；".join(_dedupe_strings(next_action_steps, 3)) or "", 132)
    if next_action and not next_action.endswith(("。", ".", "!", "！", "?", "？")):
        next_action = f"{next_action}。"
    if not next_action and account_focus:
        next_action = f"围绕{account_focus[0]}继续补预算归口、组织入口与联系人。"
    return ResearchCommercialSummaryOut(
        account_focus=account_focus,
        budget_signal=budget_signal,
        entry_window=entry_window,
        competition_or_partner=competition_or_partner,
        next_action=next_action,
    )


def _build_report_readiness(report: ResearchReportDocument) -> ResearchReportReadinessOut:
    score = 12
    reasons: list[str] = []
    missing_axes: list[str] = []
    next_steps: list[str] = []
    diagnostics = report.source_diagnostics
    official_ratio = float(diagnostics.official_source_ratio or 0.0)
    account_count = len(report.top_target_accounts or report.target_accounts)
    has_budget = bool(report.budget_signals or report.tender_timeline)
    has_contacts = bool(report.public_contact_channels or report.target_departments)
    section_failures = [
        section.title
        for section in report.sections
        if not getattr(section, "meets_evidence_quota", True)
        and any(token in normalize_text(section.title) for token in ("甲方", "预算", "招标", "生态", "竞品", "联系"))
    ]

    if report.source_count >= 6:
        score += 20
        reasons.append(f"已保留 {report.source_count} 条有效来源。")
    else:
        missing_axes.append("来源覆盖")
        next_steps.append("补到至少 6 条高相关来源，再进入强结论模式。")
    if official_ratio >= 0.25:
        score += 18
        reasons.append(f"官方源占比 {round(official_ratio * 100)}%。")
    else:
        missing_axes.append("官方源")
        next_steps.append("补官网、公告、政策、招采等官方源。")
    if account_count >= 1:
        score += 18
        reasons.append(f"已锁定 {account_count} 个重点账户。")
    else:
        missing_axes.append("具体账户")
        next_steps.append("先把行业判断收敛到具体公司、机构或业主单位。")
    if has_budget:
        score += 14
        reasons.append("已有预算或进入窗口线索。")
    else:
        missing_axes.append("预算/窗口")
        next_steps.append("补预算草案、招标窗口、项目期次或投资节奏。")
    if has_contacts:
        score += 12
        reasons.append("已有组织入口或公开联系线索。")
    else:
        missing_axes.append("组织入口")
        next_steps.append("补决策部门、联系人或公开组织入口。")
    if report.evidence_density == "high":
        score += 10
    elif report.evidence_density == "medium":
        score += 6
    if not section_failures:
        score += 6
    else:
        next_steps.append(f"优先补强这些章节的证据：{' / '.join(section_failures[:3])}")
    score = max(8, min(score, 96))
    actionable = score >= 62 and account_count >= 1 and has_budget
    evidence_gate_passed = official_ratio >= 0.2 and report.source_count >= 5 and not section_failures[:2]
    if actionable and evidence_gate_passed and has_contacts:
        status = "ready"
    elif score >= 42 and account_count >= 1:
        status = "degraded"
    else:
        status = "needs_evidence"
    if status == "degraded":
        reasons.append("当前可用于候选推进，但仍需补证后再做强判断。")
    if status == "needs_evidence":
        reasons.append("当前更适合输出候选名单与待补证路径，不宜直接当作最终商业判断。")
    return ResearchReportReadinessOut(
        status=status,
        score=score,
        actionable=actionable,
        evidence_gate_passed=evidence_gate_passed,
        reasons=_dedupe_strings(reasons, 5),
        missing_axes=_dedupe_strings(missing_axes, 5),
        next_verification_steps=_dedupe_strings(next_steps, 5),
    )


def _build_technical_appendix(report: ResearchReportDocument) -> ResearchTechnicalAppendixOut:
    diagnostics = report.source_diagnostics
    readiness = _resolved_report_readiness(report)
    output_language = getattr(report, "output_language", "zh-CN")
    account_focus = _dedupe_strings(
        [
            *(normalize_text(item.name) for item in report.top_target_accounts if normalize_text(item.name)),
            *(normalize_text(item) for item in report.target_accounts if normalize_text(item)),
        ],
        3,
    )
    key_assumptions = _dedupe_strings(
        [
            (
                f"当前判断默认以 {'/'.join(account_focus[:2])} 作为优先进入对象。"
                if account_focus
                else "当前判断默认先把行业主题收敛到可验证的具体账户。"
            ),
            (
                f"公开源口径以 {round(float(diagnostics.official_source_ratio or 0.0) * 100)}% 官方源占比为当前可信度基线。"
                if report.source_count
                else "当前仍需补公开源，尤其是官网、公告和采购信息。"
            ),
            (
                f"当前时间判断默认以 {normalize_text((report.tender_timeline or report.strategic_directions or ['近期预算窗口'])[0])} 为主要进入窗口。"
                if report.tender_timeline or report.strategic_directions
                else "当前仍默认预算窗口未完全确认，进入节奏需继续验证。"
            ),
            "本研判仅基于公开网页、公告、政策、行业媒体和浏览器可获取正文，不包含未授权后台数据。",
        ],
        4,
    )
    scenario_comparison = [
        ResearchScenarioOut(
            name="乐观情景",
            summary=(
                "预算与部门口径被进一步确认，且官方源继续补强。"
                if report.budget_signals or report.public_contact_channels
                else "下一轮公开源补强后，出现更明确的预算和组织入口。"
            ),
            implication="可直接进入账户计划、伙伴绑定和 close plan 执行。",
        ),
        ResearchScenarioOut(
            name="基准情景",
            summary=(
                "当前以候选推进为主，边推进边补证。"
                if readiness.status != "ready"
                else "当前已具备首轮推进条件，但仍需同步补证。"
            ),
            implication="适合先做会前简报、部门映射和公开触达，再决定是否进入更重资源投入。",
        ),
        ResearchScenarioOut(
            name="保守情景",
            summary=(
                "若预算、联系人或官方源迟迟无法补齐，则当前结论需要降级。"
            ),
            implication="保留为候选账户与审查队列，不建议直接当作最终销售/咨询判断。",
        ),
    ]
    limitations = _dedupe_strings(
        [
            *(f"仍缺关键维度：{axis}" for axis in readiness.missing_axes[:3]),
            (
                f"官方源占比仅 {round(float(diagnostics.official_source_ratio or 0.0) * 100)}%，仍有继续补强空间。"
                if float(diagnostics.official_source_ratio or 0.0) < 0.3
                else ""
            ),
            "部分账户、伙伴或竞品仍来自公开线索推断，需要进一步做交叉核验。",
            (
                "当前公开联系人不足，部分行动建议仍以组织入口和部门推断为主。"
                if not report.public_contact_channels
                else ""
            ),
        ],
        4,
    )
    technical_appendix = _dedupe_strings(
        [
            f"检索计划：{'；'.join(report.query_plan[:4])}" if report.query_plan else "",
            (
                f"来源结构：共保留 {report.source_count} 条来源，官方源 {diagnostics.source_tier_counts.get('official', 0)} 条，媒体源 {diagnostics.source_tier_counts.get('media', 0)} 条，聚合源 {diagnostics.source_tier_counts.get('aggregate', 0)} 条。"
            ),
            (
                f"Pipeline：{diagnostics.pipeline_summary or '取数 -> 清洗 -> 分析'}；取数 {next((stage.value for stage in diagnostics.pipeline_stages if stage.key == 'fetch'), 0)}，清洗 {next((stage.value for stage in diagnostics.pipeline_stages if stage.key == 'clean'), 0)}，分析 {next((stage.value for stage in diagnostics.pipeline_stages if stage.key == 'analyze'), 0)}。"
            ),
            (
                f"实体归一：共识别 {diagnostics.normalized_entity_count} 个实体，其中甲方 {diagnostics.normalized_target_count} 个、竞品 {diagnostics.normalized_competitor_count} 个、伙伴 {diagnostics.normalized_partner_count} 个。"
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "边界说明：不绕过登录、付费墙或未授权后台数据；若证据不足会明确降级或进入审查队列。",
                    "zh-TW": "邊界說明：不繞過登入、付費牆或未授權後台資料；若證據不足會明確降級或進入審查佇列。",
                    "en": "Boundary: no login, paywall, or unauthorized backend bypass is used; weak evidence is explicitly downgraded or queued for review.",
                },
                "边界说明：不绕过登录、付费墙或未授权后台数据；若证据不足会明确降级或进入审查队列。",
            ),
        ],
        5,
    )
    return ResearchTechnicalAppendixOut(
        key_assumptions=key_assumptions,
        scenario_comparison=scenario_comparison,
        limitations=limitations,
        technical_appendix=technical_appendix,
    )


def _review_queue_severity(section: ResearchReportSectionOut) -> str:
    if section.contradiction_detected or section.confidence_tone == "conflict":
        return "high"
    if not section.meets_evidence_quota or (section.evidence_count or 0) <= 0:
        return "medium"
    return "low"


def _build_review_queue(report: ResearchReportDocument) -> list[ResearchReviewQueueItemOut]:
    items: list[ResearchReviewQueueItemOut] = []
    readiness = _resolved_report_readiness(report)
    for section in report.sections:
        severity = _review_queue_severity(section)
        should_include = (
            severity == "high"
            or not section.meets_evidence_quota
            or section.confidence_tone in {"low", "conflict"}
        )
        if not should_include:
            continue
        summary_parts = [
            normalize_text(section.contradiction_note),
            normalize_text(section.quota_note),
            normalize_text(section.confidence_reason),
        ]
        recommended_action = (
            "优先补官方源与原始公告，再对冲突结论做二次审查。"
            if severity == "high"
            else "优先补强该章节的官方源、原始网页和账户级证据，再决定是否保留结论。"
        )
        items.append(
            ResearchReviewQueueItemOut(
                id=re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", normalize_text(f"review-{section.title}").lower()).strip("-")
                or "review-section",
                section_title=section.title,
                severity=severity,
                summary="；".join(part for part in summary_parts if part) or f"{section.title} 仍需继续补证。",
                recommended_action=recommended_action,
                evidence_links=list(section.evidence_links[:3]),
            )
        )
    if readiness.status != "ready" and readiness.missing_axes:
        items.append(
            ResearchReviewQueueItemOut(
                id="review-report-readiness",
                section_title="总体待核验",
                severity="medium",
                summary=f"当前仍缺关键维度：{' / '.join(readiness.missing_axes[:3])}",
                recommended_action="先补关键维度，再决定是否进入正式推进；不要把当前版本当作最终结论。",
                evidence_links=[],
            )
        )
    deduped: list[ResearchReviewQueueItemOut] = []
    seen_ids: set[str] = set()
    for item in items:
        if item.id in seen_ids:
            continue
        seen_ids.add(item.id)
        deduped.append(item)
    severity_order = {"high": 0, "medium": 1, "low": 2}
    deduped.sort(key=lambda item: (severity_order.get(item.severity, 3), item.section_title))
    return deduped[:6]


def _enrich_report_for_delivery(report: ResearchReportResponse) -> ResearchReportResponse:
    readiness = _build_report_readiness(report)
    staged = report.model_copy(update={"report_readiness": readiness})
    commercial_summary = _build_commercial_summary(staged)
    enriched = staged.model_copy(
        update={
            "commercial_summary": commercial_summary,
        }
    )
    enriched = enriched.model_copy(
        update={
            "technical_appendix": _build_technical_appendix(enriched),
            "review_queue": _build_review_queue(enriched),
        }
    )
    return _apply_report_readiness_guardrails(enriched)


def _apply_report_readiness_guardrails(report: ResearchReportResponse) -> ResearchReportResponse:
    readiness = report.report_readiness
    if readiness.status == "ready":
        return report
    if normalize_text(report.report_title).endswith(("待核验清单与补证路径", "待核驗清單與補證路徑", "Verification Backlog and Evidence Path")):
        return report
    executive_summary = normalize_text(report.executive_summary)
    consulting_angle = normalize_text(report.consulting_angle)
    if readiness.status == "degraded":
        summary_note = "当前版本适合候选推进，关键预算、官方源或组织入口仍需继续核验。"
        angle_note = "建议按轻量推进处理，并同步补关键证据。"
    else:
        summary_note = "当前版本更适合作为待核验清单，不建议直接作为最终商业判断。"
        angle_note = "建议先补关键证据，再决定是否进入正式推进。"

    def _append_guardrail_note(text: str, note: str) -> str:
        normalized = normalize_text(text)
        if not normalized:
            return note
        if note in normalized:
            return normalized
        if normalized.endswith(("。", "！", "？")):
            return f"{normalized}{note}"
        if normalized.endswith((".", "!", "?")):
            return f"{normalized} {note}"
        return f"{normalized}。{note}"

    return report.model_copy(
        update={
            "executive_summary": _append_guardrail_note(executive_summary, summary_note),
            "consulting_angle": _append_guardrail_note(consulting_angle, angle_note),
        }
    )


def _build_source_diagnostics(
    sources: list[SourceDocument],
    *,
    enabled_source_labels: list[str],
    scope_hints: dict[str, object],
    recency_window_years: int,
    filtered_old_source_count: int,
    filtered_region_conflict_count: int,
    retained_source_count: int,
    strict_topic_source_count: int,
    topic_anchor_terms: list[str],
    matched_theme_labels: list[str],
    entity_graph: ResearchEntityGraphOut,
    expansion_triggered: bool,
    corrective_triggered: bool,
    candidate_profile_companies: list[str],
    candidate_profile_hit_count: int,
    candidate_profile_official_hit_count: int,
    candidate_profile_source_labels: list[str],
) -> ResearchSourceDiagnosticsOut:
    source_type_counts: Counter[str] = Counter()
    source_tier_counts: Counter[str] = Counter()
    source_label_counts: Counter[str] = Counter()
    adapter_hit_count = 0
    for source in sources:
        source_type_counts[source.source_type] += 1
        source_tier_counts[source.source_tier or "media"] += 1
        if source.source_label:
            source_label_counts[source.source_label] += 1
        if source.source_origin == "adapter":
            adapter_hit_count += 1
    matched_source_labels = [label for label, _ in source_label_counts.most_common()]
    unique_domains = len({source.domain for source in sources if normalize_text(source.domain or "")})
    official_count = int(source_tier_counts.get("official", 0))
    strict_match_ratio = (strict_topic_source_count / retained_source_count) if retained_source_count else 0.0
    official_source_ratio = (official_count / retained_source_count) if retained_source_count else 0.0
    retrieval_quality = _retrieval_quality_band(
        strict_match_ratio=strict_match_ratio,
        official_source_ratio=official_source_ratio,
        unique_domain_count=unique_domains,
        normalized_entity_count=len(entity_graph.entities),
    )
    evidence_mode, evidence_mode_label = _evidence_mode_from_metrics(
        retained_source_count=retained_source_count,
        strict_topic_source_count=strict_topic_source_count,
        strict_match_ratio=strict_match_ratio,
        official_source_ratio=official_source_ratio,
        unique_domain_count=unique_domains,
    )
    fetch_count = max(adapter_hit_count + max(len(sources) - adapter_hit_count, 0), 0)
    clean_removed_count = max(filtered_old_source_count, 0) + max(filtered_region_conflict_count, 0)
    pipeline_stages = [
        {
            "key": "fetch",
            "label": "取数",
            "value": fetch_count,
            "summary": f"汇总 {fetch_count} 条候选来源，覆盖 {max(len(enabled_source_labels), len(matched_source_labels) or 0)} 类输入通道。",
        },
        {
            "key": "clean",
            "label": "清洗",
            "value": max(retained_source_count, 0),
            "summary": f"保留 {max(retained_source_count, 0)} 条可用来源，剔除 {clean_removed_count} 条过旧或越界结果。",
        },
        {
            "key": "analyze",
            "label": "分析",
            "value": len(entity_graph.entities),
            "summary": f"归一 {len(entity_graph.entities)} 个实体，官方源占比 {round(official_source_ratio * 100)}%。",
        },
    ]
    pipeline_summary = " -> ".join(stage["summary"] for stage in pipeline_stages)
    return ResearchSourceDiagnosticsOut(
        enabled_source_labels=list(dict.fromkeys(enabled_source_labels)),
        matched_source_labels=matched_source_labels,
        scope_regions=_dedupe_strings(scope_hints.get("regions", []) or [], 3),
        scope_industries=_dedupe_strings(scope_hints.get("industries", []) or [], 3),
        scope_clients=_dedupe_strings(scope_hints.get("clients", []) or [], 3),
        source_type_counts=dict(source_type_counts),
        source_tier_counts=dict(source_tier_counts),
        adapter_hit_count=adapter_hit_count,
        search_hit_count=max(len(sources) - adapter_hit_count, 0),
        recency_window_years=recency_window_years,
        filtered_old_source_count=max(filtered_old_source_count, 0),
        filtered_region_conflict_count=max(filtered_region_conflict_count, 0),
        retained_source_count=max(retained_source_count, 0),
        strict_topic_source_count=max(strict_topic_source_count, 0),
        topic_anchor_terms=list(dict.fromkeys(item for item in topic_anchor_terms if normalize_text(item)))[:8],
        matched_theme_labels=list(dict.fromkeys(item for item in matched_theme_labels if normalize_text(item)))[:8],
        retrieval_quality=retrieval_quality if retrieval_quality in {"low", "medium", "high"} else "low",
        evidence_mode=evidence_mode if evidence_mode in {"strong", "provisional", "fallback"} else "fallback",
        evidence_mode_label=evidence_mode_label,
        strict_match_ratio=round(strict_match_ratio, 3),
        official_source_ratio=round(official_source_ratio, 3),
        unique_domain_count=unique_domains,
        normalized_entity_count=len(entity_graph.entities),
        normalized_target_count=len(entity_graph.target_entities),
        normalized_competitor_count=len(entity_graph.competitor_entities),
        normalized_partner_count=len(entity_graph.partner_entities),
        expansion_triggered=expansion_triggered,
        corrective_triggered=corrective_triggered,
        candidate_profile_companies=_dedupe_strings(candidate_profile_companies, 6),
        candidate_profile_hit_count=max(candidate_profile_hit_count, 0),
        candidate_profile_official_hit_count=max(candidate_profile_official_hit_count, 0),
        candidate_profile_source_labels=_dedupe_strings(candidate_profile_source_labels, 8),
        strategy_model_used=bool(scope_hints.get("strategy_scope_summary") or scope_hints.get("strategy_query_expansions")),
        strategy_scope_summary=normalize_text(str(scope_hints.get("strategy_scope_summary", ""))),
        strategy_query_expansion_count=len(scope_hints.get("strategy_query_expansions", []) or []),
        strategy_exclusion_terms=_dedupe_strings(scope_hints.get("strategy_exclusion_terms", []) or [], 8),
        pipeline_summary=pipeline_summary,
        pipeline_stages=pipeline_stages,
    )


def _collect_matched_theme_labels(
    sources: list[SourceDocument],
    *,
    scope_hints: dict[str, object],
    topic_anchor_terms: list[str],
) -> list[str]:
    if not sources:
        return topic_anchor_terms[:4]
    haystack = normalize_text(
        " ".join(
            " ".join(
                [
                    source.title,
                    source.snippet,
                    source.excerpt,
                    source.search_query,
                    source.source_label or "",
                    source.domain or "",
                ]
            )
            for source in sources
        )
    ).lower()
    candidates: list[str] = []
    for label in [*(scope_hints.get("industries", []) or []), *(scope_hints.get("clients", []) or []), *(scope_hints.get("regions", []) or [])]:
        normalized = normalize_text(str(label))
        if not normalized:
            continue
        aliases = [normalized, *INDUSTRY_SCOPE_ALIASES.get(normalized, ())]
        if any(normalize_text(alias).lower() in haystack for alias in aliases if normalize_text(alias)):
            candidates.append(normalized)
    if not candidates:
        candidates.extend(topic_anchor_terms[:4])
    return list(dict.fromkeys(item for item in candidates if normalize_text(item)))


def _render_source_digest(sources: list[SourceDocument]) -> str:
    chunks: list[str] = []
    for index, source in enumerate(sources, start=1):
        chunks.append(
            "\n".join(
                [
                    f"[Source {index}]",
                    f"Title: {source.title}",
                    f"Domain: {source.domain or 'unknown'}",
                    f"Label: {source.source_label or 'unknown'}",
                    f"Tier: {source.source_tier}",
                    f"URL: {source.url}",
                    f"Search Query: {source.search_query}",
                    f"Snippet: {source.snippet}",
                    f"Excerpt: {source.excerpt}",
                ]
            )
        )
    return "\n\n".join(chunks)


def _build_sections(
    result: ResearchReportResult,
    output_language: str,
    sources: list[SourceDocument],
) -> list[ResearchReportSectionOut]:
    title_map = {
        "industry_brief": localized_text(
            output_language,
            {"zh-CN": "行业资讯判断", "zh-TW": "產業資訊判斷", "en": "Industry View"},
            "行业资讯判断",
        ),
        "key_signals": localized_text(
            output_language,
            {"zh-CN": "关键信号", "zh-TW": "關鍵信號", "en": "Key Signals"},
            "关键信号",
        ),
        "policy_and_leadership": localized_text(
            output_language,
            {"zh-CN": "政策与领导信号", "zh-TW": "政策與領導信號", "en": "Policy and Leadership"},
            "政策与领导信号",
        ),
        "commercial_opportunities": localized_text(
            output_language,
            {"zh-CN": "项目与商机判断", "zh-TW": "專案與商機判斷", "en": "Opportunity Map"},
            "项目与商机判断",
        ),
        "solution_design": localized_text(
            output_language,
            {"zh-CN": "解决方案设计建议", "zh-TW": "解決方案設計建議", "en": "Solution Design"},
            "解决方案设计建议",
        ),
        "sales_strategy": localized_text(
            output_language,
            {"zh-CN": "销售策略", "zh-TW": "銷售策略", "en": "Sales Strategy"},
            "销售策略",
        ),
        "bidding_strategy": localized_text(
            output_language,
            {"zh-CN": "投标规划", "zh-TW": "投標規劃", "en": "Bidding Strategy"},
            "投标规划",
        ),
        "outreach_strategy": localized_text(
            output_language,
            {"zh-CN": "陌生拜访建议", "zh-TW": "陌生拜訪建議", "en": "Outreach Strategy"},
            "陌生拜访建议",
        ),
        "ecosystem_strategy": localized_text(
            output_language,
            {"zh-CN": "生态伙伴建议", "zh-TW": "生態夥伴建議", "en": "Ecosystem Strategy"},
            "生态伙伴建议",
        ),
        "target_accounts": localized_text(
            output_language,
            {"zh-CN": "重点甲方与目标客户", "zh-TW": "重點甲方與目標客戶", "en": "Target Accounts"},
            "重点甲方与目标客户",
        ),
        "target_departments": localized_text(
            output_language,
            {"zh-CN": "高概率决策部门", "zh-TW": "高機率決策部門", "en": "Likely Decision Departments"},
            "高概率决策部门",
        ),
        "public_contact_channels": localized_text(
            output_language,
            {"zh-CN": "公开业务联系方式", "zh-TW": "公開業務聯絡方式", "en": "Public Contact Channels"},
            "公开业务联系方式",
        ),
        "account_team_signals": localized_text(
            output_language,
            {"zh-CN": "活跃团队与推进抓手", "zh-TW": "活躍團隊與推進抓手", "en": "Active Teams and Execution Handles"},
            "活跃团队与推进抓手",
        ),
        "budget_signals": localized_text(
            output_language,
            {"zh-CN": "预算与投资信号", "zh-TW": "預算與投資信號", "en": "Budget Signals"},
            "预算与投资信号",
        ),
        "project_distribution": localized_text(
            output_language,
            {"zh-CN": "项目分布与期次判断", "zh-TW": "專案分佈與期次判斷", "en": "Project Distribution"},
            "项目分布与期次判断",
        ),
        "strategic_directions": localized_text(
            output_language,
            {"zh-CN": "战略方向", "zh-TW": "戰略方向", "en": "Strategic Directions"},
            "战略方向",
        ),
        "tender_timeline": localized_text(
            output_language,
            {"zh-CN": "招标时间预测", "zh-TW": "招標時間預測", "en": "Tender Timeline"},
            "招标时间预测",
        ),
        "leadership_focus": localized_text(
            output_language,
            {"zh-CN": "领导近三年关注点", "zh-TW": "領導近三年關注點", "en": "Leadership Focus"},
            "领导近三年关注点",
        ),
        "ecosystem_partners": localized_text(
            output_language,
            {"zh-CN": "活跃生态伙伴", "zh-TW": "活躍生態夥伴", "en": "Ecosystem Partners"},
            "活跃生态伙伴",
        ),
        "competitor_profiles": localized_text(
            output_language,
            {"zh-CN": "竞品公司概况", "zh-TW": "競品公司概況", "en": "Competitor Profiles"},
            "竞品公司概况",
        ),
        "benchmark_cases": localized_text(
            output_language,
            {"zh-CN": "同领域标杆案例", "zh-TW": "同領域標竿案例", "en": "Benchmark Cases"},
            "同领域标杆案例",
        ),
        "flagship_products": localized_text(
            output_language,
            {"zh-CN": "明星产品与方案", "zh-TW": "明星產品與方案", "en": "Flagship Products"},
            "明星产品与方案",
        ),
        "key_people": localized_text(
            output_language,
            {"zh-CN": "关键人物", "zh-TW": "關鍵人物", "en": "Key People"},
            "关键人物",
        ),
        "five_year_outlook": localized_text(
            output_language,
            {"zh-CN": "未来五年演化判断", "zh-TW": "未來五年演化判斷", "en": "Five-Year Outlook"},
            "未来五年演化判断",
        ),
        "client_peer_moves": localized_text(
            output_language,
            {"zh-CN": "甲方同行 Top 3 动态", "zh-TW": "甲方同行 Top 3 動態", "en": "Top 3 Buyer Peer Moves"},
            "甲方同行 Top 3 动态",
        ),
        "winner_peer_moves": localized_text(
            output_language,
            {"zh-CN": "中标方同行 Top 3 动态", "zh-TW": "中標方同行 Top 3 動態", "en": "Top 3 Winner Peer Moves"},
            "中标方同行 Top 3 动态",
        ),
        "competition_analysis": localized_text(
            output_language,
            {"zh-CN": "竞争分析", "zh-TW": "競爭分析", "en": "Competition Analysis"},
            "竞争分析",
        ),
        "risks": localized_text(
            output_language,
            {"zh-CN": "风险提示", "zh-TW": "風險提示", "en": "Risks"},
            "风险提示",
        ),
        "next_actions": localized_text(
            output_language,
            {"zh-CN": "下一步行动", "zh-TW": "下一步行動", "en": "Next Actions"},
            "下一步行动",
        ),
    }
    sections: list[ResearchReportSectionOut] = []
    for key in (
        "industry_brief",
        "key_signals",
        "policy_and_leadership",
        "commercial_opportunities",
        "solution_design",
        "sales_strategy",
        "bidding_strategy",
        "outreach_strategy",
        "ecosystem_strategy",
        "target_accounts",
        "target_departments",
        "public_contact_channels",
        "account_team_signals",
        "budget_signals",
        "project_distribution",
        "strategic_directions",
        "tender_timeline",
        "leadership_focus",
        "ecosystem_partners",
        "competitor_profiles",
        "benchmark_cases",
        "flagship_products",
        "key_people",
        "five_year_outlook",
        "client_peer_moves",
        "winner_peer_moves",
        "competition_analysis",
        "risks",
        "next_actions",
    ):
        items = getattr(result, key)
        if items:
            evidence_links, source_tier_counts, official_source_ratio = _build_section_evidence_links(
                section_title=title_map[key],
                items=items,
                sources=sources,
                limit=3,
            )
            evidence_density, source_quality, evidence_note = _section_signal_quality(
                items,
                sources,
                evidence_links=evidence_links,
                source_tier_counts=source_tier_counts,
                official_source_ratio=official_source_ratio,
            )
            evidence_quota = _section_evidence_quota(key, items)
            meets_evidence_quota, quota_gap, quota_note = _section_quota_note(
                section_title=title_map[key],
                evidence_count=len(evidence_links),
                evidence_quota=evidence_quota,
                official_source_ratio=official_source_ratio,
            )
            confidence_tone, confidence_label, confidence_reason, contradiction_detected, contradiction_note = _section_confidence_profile(
                section_title=title_map[key],
                items=items,
                sources=sources,
                evidence_density=evidence_density,
                source_quality=source_quality,
                official_source_ratio=official_source_ratio,
                meets_evidence_quota=meets_evidence_quota,
                evidence_links=evidence_links,
            )
            next_verification_steps = _section_next_verification_steps(
                section_title=title_map[key],
                output_language=output_language,
                evidence_density=evidence_density,
                source_quality=source_quality,
                official_source_ratio=official_source_ratio,
                evidence_count=len(evidence_links),
                evidence_quota=evidence_quota,
                contradiction_detected=contradiction_detected,
            )
            section_status, insufficiency_reasons, insufficiency_summary = _section_insufficiency_profile(
                section_title=title_map[key],
                output_language=output_language,
                evidence_density=evidence_density,
                source_quality=source_quality,
                official_source_ratio=official_source_ratio,
                quota_gap=quota_gap,
                contradiction_detected=contradiction_detected,
            )
            tinted_evidence_links = [
                link.model_copy(update={"confidence_tone": confidence_tone})
                for link in evidence_links
            ]
            sections.append(
                ResearchReportSectionOut(
                    title=title_map[key],
                    items=items,
                    status=section_status,
                    evidence_density=evidence_density,
                    source_quality=source_quality,
                    confidence_tone=confidence_tone,
                    confidence_label=confidence_label,
                    confidence_reason=confidence_reason,
                    evidence_note=evidence_note,
                    insufficiency_reasons=insufficiency_reasons,
                    insufficiency_summary=insufficiency_summary,
                    source_tier_counts=source_tier_counts,
                    official_source_ratio=official_source_ratio,
                    evidence_links=tinted_evidence_links,
                    evidence_count=len(evidence_links),
                    evidence_quota=evidence_quota,
                    meets_evidence_quota=meets_evidence_quota,
                    quota_gap=quota_gap,
                    quota_note=quota_note,
                    next_verification_steps=next_verification_steps,
                    contradiction_detected=contradiction_detected,
                    contradiction_note=contradiction_note,
                )
            )
    return sections


def _research_section_items(report: ResearchReportDocument, aliases: tuple[str, ...]) -> list[str]:
    normalized_aliases = tuple(alias.lower() for alias in aliases)
    for section in report.sections:
        title = normalize_text(section.title).lower()
        if any(alias in title for alias in normalized_aliases):
            return [normalize_text(item) for item in section.items if normalize_text(item)]
    return []


def _truncate_sentence(value: str, limit: int = 82) -> str:
    text = normalize_text(value)
    if len(text) <= limit:
        return text
    clipped = text[: limit - 1].rstrip(" ，,：:；;、")
    return f"{clipped}…"


def _build_action_summary(primary: list[str], secondary: list[str], *, fallback: str) -> str:
    seeds = [item for item in primary[:2] if item] + [item for item in secondary[:1] if item]
    if not seeds:
        return _truncate_sentence(fallback, 96)
    return _truncate_sentence("；".join(seeds), 108)


def _research_section(report: ResearchReportDocument, aliases: tuple[str, ...]) -> ResearchReportSectionOut | None:
    normalized_aliases = tuple(alias.lower() for alias in aliases)
    for section in report.sections:
        title = normalize_text(section.title).lower()
        if any(alias in title for alias in normalized_aliases):
            return section
    return None


def _is_low_value_action_url(url: str) -> bool:
    normalized = normalize_text(url).lower()
    if not normalized:
        return True
    if any(normalized.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
        return True
    return any(token in normalized for token in ("/static/", "/images/", "/image/", "common/images"))


def _format_action_evidence_link(link: ResearchEntityEvidenceOut) -> str | None:
    url = normalize_text(link.url)
    if not url or _is_low_value_action_url(url):
        return None
    title = normalize_text(link.title)
    source_label = normalize_text(link.source_label)
    domain = extract_domain(url) or ""
    label_parts: list[str] = []
    if source_label and source_label not in {title, domain}:
        label_parts.append(source_label)
    if title and title not in {source_label, domain}:
        label_parts.append(_truncate_sentence(title, 48))
    if not label_parts and domain:
        label_parts.append(domain)
    label = "｜".join(part for part in label_parts if part)
    return f"{label} {url}".strip()


def _sanitize_action_evidence_rows(rows: list[str], *, limit: int = 3) -> list[str]:
    normalized_rows: list[str] = []
    seen: set[str] = set()
    for raw in rows:
        text = normalize_text(raw)
        if not text:
            continue
        urls = re.findall(r"https?://[^\s)]+", text)
        if urls:
            preferred_url = next((url for url in urls if not _is_low_value_action_url(url)), "")
            if not preferred_url:
                text = re.sub(r"https?://[^\s)]+", " ", text)
                text = re.sub(r"\s+", " ", text).strip(" ，,；;()[]")
                if not text:
                    continue
            else:
                text_without_urls = re.sub(r"https?://[^\s)]+", " ", text)
                text_without_urls = re.sub(r"\s+", " ", text_without_urls).strip(" ，,；;()[]")
                domain = extract_domain(preferred_url) or ""
                if not text_without_urls:
                    text = domain or preferred_url
                else:
                    text = f"{_truncate_sentence(text_without_urls, 64)} {preferred_url}"
        if len(text) > 140:
            text = _truncate_sentence(text, 140)
        if text in seen:
            continue
        seen.add(text)
        normalized_rows.append(text)
        if len(normalized_rows) >= max(1, limit):
            break
    return normalized_rows


def _build_action_evidence(
    report: ResearchReportDocument,
    *,
    section_aliases: tuple[str, ...],
    fallback_rows: list[str],
    limit: int = 3,
) -> list[str]:
    evidence_rows: list[str] = []
    section = _research_section(report, section_aliases)
    if section and getattr(section, "evidence_links", None):
        for link in section.evidence_links:
            formatted = _format_action_evidence_link(link)
            if formatted:
                evidence_rows.append(formatted)
    if len(evidence_rows) < limit:
        evidence_rows.extend(fallback_rows)
    return _sanitize_action_evidence_rows(evidence_rows, limit=limit)


def _entity_names_from_ranked(
    ranked: list[ResearchRankedEntityOut],
    fallback_rows: list[str],
    *,
    limit: int = 3,
) -> list[str]:
    names = [normalize_text(item.name) for item in ranked if normalize_text(item.name)]
    if len(names) < limit:
        for row in fallback_rows:
            candidate = _extract_rank_entity_name(row)
            if not candidate:
                continue
            if any(
                candidate == existing
                or (len(candidate) >= 2 and len(existing) >= 2 and (candidate in existing or existing in candidate))
                for existing in names
            ):
                continue
            names.append(candidate)
            if len(names) >= limit:
                break
    return _dedupe_strings(names, limit)


def _pick_rows_for_entities(rows: list[str], names: list[str], *, limit: int = 3) -> list[str]:
    matched: list[str] = []
    for name in names:
        for row in rows:
            normalized_row = normalize_text(row)
            if normalized_row and name and name in normalized_row:
                matched.append(normalized_row)
    if len(matched) < limit:
        matched.extend(normalize_text(row) for row in rows if normalize_text(row))
    return _dedupe_strings(matched, limit)


def _derive_scope_anchor(report: ResearchReportDocument) -> str:
    for candidate in (
        *report.target_accounts,
        *report.project_distribution,
        *report.strategic_directions,
    ):
        normalized = normalize_text(candidate)
        if normalized:
            return normalized
    return normalize_text(report.research_focus or "") or normalize_text(report.keyword)


def _derive_entry_window(report: ResearchReportDocument, output_language: str) -> str:
    timeline = " ".join(normalize_text(item) for item in report.tender_timeline)
    if any(token in timeline for token in ("采购意向", "预算", "立项", "规划", "前期")):
        return localized_text(
            output_language,
            {
                "zh-CN": "优先在招标前 3-6 个月入场，围绕预算、立项和需求定义建立关系。",
                "zh-TW": "優先在招標前 3-6 個月入場，圍繞預算、立項與需求定義建立關係。",
                "en": "Enter 3-6 months before the tender, focusing on budget and requirement shaping.",
            },
            "优先在招标前 3-6 个月入场，围绕预算、立项和需求定义建立关系。",
        )
    if any(token in timeline for token in ("招标", "挂网", "开标", "投标", "公告")):
        return localized_text(
            output_language,
            {
                "zh-CN": "优先在开标前 4-8 周入场，补齐伙伴、方案与资格材料。",
                "zh-TW": "優先在開標前 4-8 週入場，補齊夥伴、方案與資格材料。",
                "en": "Enter 4-8 weeks before bid opening to finalize partners, solution, and qualification materials.",
            },
            "优先在开标前 4-8 周入场，补齐伙伴、方案与资格材料。",
        )
    return localized_text(
        output_language,
        {
            "zh-CN": "按同类项目常见节奏，建议至少提前一个预算周期建立关系并验证需求。",
            "zh-TW": "按同類專案常見節奏，建議至少提前一個預算週期建立關係並驗證需求。",
            "en": "Based on typical project cycles, establish contact at least one budget cycle earlier.",
        },
        "按同类项目常见节奏，建议至少提前一个预算周期建立关系并验证需求。",
    )


def _derive_visit_sequence(report: ResearchReportDocument, output_language: str) -> list[str]:
    departments = _dedupe_strings(report.target_departments, 8)
    ordered: list[str] = []
    category_map = (
        ("业务/场景发起部门", ("业务", "运营", "政务服务", "应用", "建设管理", "事业发展")),
        ("信息化/数字化部门", ("信息中心", "信息化部", "数字化部", "科技部", "数据局", "数据资源局")),
        ("预算/财务部门", ("财务", "计划财务", "预算", "投资管理")),
        ("采购/招采部门", ("采购", "招标", "招采", "集采")),
        ("领导/办公室", ("书记", "市长", "主任", "局长", "厅长", "办公室")),
    )
    for label, tokens in category_map:
        matched = next((item for item in departments if any(token in item for token in tokens)), "")
        if matched:
            ordered.append(f"{label}：{matched}")
    if not ordered:
        ordered = [
            localized_text(
                output_language,
                {
                    "zh-CN": "先找业务/场景发起人确认刚需，再找信息化/数字化部门验证路线。",
                    "zh-TW": "先找業務/場景發起人確認剛需，再找資訊化/數位化部門驗證路線。",
                    "en": "Start with business owners, then validate the route with digital or IT teams.",
                },
                "先找业务/场景发起人确认刚需，再找信息化/数字化部门验证路线。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "第二步补预算与财务依据，第三步再进入采购/招采。",
                    "zh-TW": "第二步補預算與財務依據，第三步再進入採購/招採。",
                    "en": "Second, validate budget ownership, and only then approach procurement.",
                },
                "第二步补预算与财务依据，第三步再进入采购/招采。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "最后争取领导层背书，用政策、预算和标杆案例统一叙事。",
                    "zh-TW": "最後爭取領導層背書，用政策、預算與標竿案例統一敘事。",
                    "en": "Finally seek leadership sponsorship using policy, budget, and benchmark cases.",
                },
                "最后争取领导层背书，用政策、预算和标杆案例统一叙事。",
            ),
        ]
    return ordered[:4]


def _derive_competitor_weaknesses(report: ResearchReportDocument, competitor_names: list[str]) -> list[str]:
    analysis = [normalize_text(item) for item in report.competition_analysis if normalize_text(item)]
    results: list[str] = []
    for name in competitor_names:
        matched = next((item for item in analysis if name in item), "")
        if matched:
            results.append(matched)
            continue
        if any(token in name for token in ("云", "平台", "科技", "智能", "信息")):
            results.append(f"{name}：公开线索更偏平台/产品叙事，可能在本地生态、场景定制和跨部门协同上存在短板。")
        else:
            results.append(f"{name}：公开线索显示其在同类项目活跃，但差异化叙事、区域伙伴和本地交付深度仍需重点验证。")
    return _dedupe_strings(results, 3)


def _build_contact_and_partner_steps(
    *,
    buyers: list[str],
    contacts: list[str],
    partners: list[str],
    output_language: str,
) -> list[str]:
    steps: list[str] = []
    if buyers:
        steps.append(f"优先围绕 {', '.join(buyers[:3])} 建立首轮名单，先确认业务牵头人与信息化接口人。")
    if contacts:
        steps.append(f"优先核验公开触达入口：{'；'.join(contacts[:3])}")
    else:
        steps.append(
            localized_text(
                output_language,
                {
                    "zh-CN": "先从甲方官网“联系我们”、采购公告联系人和投资者关系入口核验公开触达方式。",
                    "zh-TW": "先從甲方官網「聯絡我們」、採購公告聯絡人與投資者關係入口核驗公開觸達方式。",
                    "en": "Validate public contact channels through official contact pages and procurement notices.",
                },
                "先从甲方官网“联系我们”、采购公告联系人和投资者关系入口核验公开触达方式。",
            )
        )
    if partners:
        steps.append(f"同步借力 {', '.join(partners[:3])} 作为牵线或联合调研伙伴，而不是单纯产品供应商。")
    return steps[:4]


def _build_phased_steps(
    *,
    short_term: list[str],
    mid_term: list[str],
    long_term: list[str],
) -> list[str]:
    phased: list[str] = []
    if short_term:
        phased.append(f"短期（1-2周）：{'；'.join(_dedupe_strings(short_term, 2))}")
    if mid_term:
        phased.append(f"中期（2-6周）：{'；'.join(_dedupe_strings(mid_term, 2))}")
    if long_term:
        phased.append(f"长期（6周以上）：{'；'.join(_dedupe_strings(long_term, 2))}")
    return phased[:3]


def _has_minimum_action_card_inputs(report: ResearchReportDocument) -> bool:
    theme_labels = _theme_labels_from_scope(
        {
            "industries": list(getattr(getattr(report, "source_diagnostics", None), "scope_industries", []) or []),
            "regions": list(getattr(getattr(report, "source_diagnostics", None), "scope_regions", []) or []),
            "clients": list(getattr(getattr(report, "source_diagnostics", None), "scope_clients", []) or []),
        },
        keyword=report.keyword,
        research_focus=report.research_focus,
    )
    buyers = _dedupe_strings(
        [
            normalize_text(name)
            for name in [
                *_entity_names_from_ranked(report.top_target_accounts, report.target_accounts, limit=3),
                *(normalize_text(item) for item in report.target_accounts if normalize_text(item)),
            ]
            if normalize_text(name)
            and not _looks_like_scope_prompt_noise(normalize_text(name))
            and not _looks_like_placeholder_entity_name(normalize_text(name))
            and not _looks_like_fragment_entity_name(normalize_text(name))
            and not _contains_low_value_entity_token(normalize_text(name))
            and (
                _is_trustworthy_scope_client_name(normalize_text(name), theme_labels=theme_labels)
                or _is_theme_aligned_entity_name(normalize_text(name), role="target", theme_labels=theme_labels)
                or _is_lightweight_entity_name(normalize_text(name))
            )
        ],
        3,
    )
    budget_rows = [row for row in report.budget_signals if _is_actionable_budget_row(row)]
    timing_rows = [row for row in report.tender_timeline if _is_summary_fact_row(row)]
    return bool(buyers) and bool(budget_rows or timing_rows)


def build_research_action_cards(report: ResearchReportDocument) -> list[ResearchActionCardOut]:
    output_language = report.output_language
    if _is_low_signal_execution_report(report) and not _has_minimum_action_card_inputs(report):
        diagnostics = report.source_diagnostics if getattr(report, "source_diagnostics", None) else ResearchSourceDiagnosticsOut()
        official_ratio = round(float(diagnostics.official_source_ratio or 0.0) * 100)
        evidence_mode_label = normalize_text(diagnostics.evidence_mode_label) or normalize_text(diagnostics.evidence_mode) or localized_text(
            output_language,
            {"zh-CN": "兜底候选", "zh-TW": "兜底候選", "en": "Fallback"},
            "兜底候选",
        )
        return [
            ResearchActionCardOut(
                action_type="evidence_recovery",
                priority="high",
                title=localized_text(
                    output_language,
                    {
                        "zh-CN": "补证收口行动卡",
                        "zh-TW": "補證收口行動卡",
                        "en": "Evidence Recovery Card",
                    },
                    "补证收口行动卡",
                ),
                summary=localized_text(
                    output_language,
                    {
                        "zh-CN": "当前证据门槛不足，先收敛主题并补官方源、采购线索和联系人，再决定是否进入正式推进。",
                        "zh-TW": "目前證據門檻不足，先收斂主題並補官方源、採購線索與聯絡人，再決定是否進入正式推進。",
                        "en": "Evidence is below threshold. Narrow the topic and recover official, procurement, and contact evidence before moving into formal execution.",
                    },
                    "当前证据门槛不足，先收敛主题并补官方源、采购线索和联系人，再决定是否进入正式推进。",
                ),
                recommended_steps=[
                    localized_text(
                        output_language,
                        {
                            "zh-CN": "先把主题收敛到 1-2 个具体账户或项目编号，避免继续沿用泛行业结论。",
                            "zh-TW": "先把主題收斂到 1-2 個具體帳戶或專案編號，避免繼續沿用泛產業結論。",
                            "en": "Reduce the topic to 1-2 concrete buyers or project IDs instead of carrying forward broad industry claims.",
                        },
                        "先把主题收敛到 1-2 个具体账户或项目编号，避免继续沿用泛行业结论。",
                    ),
                    localized_text(
                        output_language,
                        {
                            "zh-CN": "补官网、公告、采购和投资者关系页面，至少拿到 1 条官方或准官方来源。",
                            "zh-TW": "補官網、公告、採購與投資者關係頁面，至少拿到 1 條官方或準官方來源。",
                            "en": "Add official pages, notices, procurement records, and IR pages until you have at least one official or near-official source.",
                        },
                        "补官网、公告、采购和投资者关系页面，至少拿到 1 条官方或准官方来源。",
                    ),
                    localized_text(
                        output_language,
                        {
                            "zh-CN": "补组织入口、联系人和预算窗口，再回到正式研报与行动卡生成。",
                            "zh-TW": "補組織入口、聯絡人與預算窗口，再回到正式研報與行動卡生成。",
                            "en": "Recover buyer-org, contact, and budget-window evidence before regenerating the formal report and action cards.",
                        },
                        "补组织入口、联系人和预算窗口，再回到正式研报与行动卡生成。",
                    ),
                ],
                evidence=[
                    localized_text(
                        output_language,
                        {"zh-CN": f"当前来源数：{report.source_count}", "zh-TW": f"目前來源數：{report.source_count}", "en": f"Current source count: {report.source_count}"},
                        f"当前来源数：{report.source_count}",
                    ),
                    localized_text(
                        output_language,
                        {"zh-CN": f"官方源占比：{official_ratio}%", "zh-TW": f"官方源占比：{official_ratio}%", "en": f"Official-source ratio: {official_ratio}%"},
                        f"官方源占比：{official_ratio}%",
                    ),
                    localized_text(
                        output_language,
                        {"zh-CN": f"证据模式：{evidence_mode_label}", "zh-TW": f"證據模式：{evidence_mode_label}", "en": f"Evidence mode: {evidence_mode_label}"},
                        f"证据模式：{evidence_mode_label}",
                    ),
                ],
                target_persona=localized_text(
                    output_language,
                    {
                        "zh-CN": "研究员、行业顾问、销售负责人",
                        "zh-TW": "研究員、產業顧問、銷售負責人",
                        "en": "Researchers, industry advisors, and sales owners",
                    },
                    "研究员、行业顾问、销售负责人",
                ),
                execution_window=localized_text(
                    output_language,
                    {
                        "zh-CN": "下一轮输出前 1-2 天内完成",
                        "zh-TW": "下一輪輸出前 1-2 天內完成",
                        "en": "Complete within 1-2 days before the next report run.",
                    },
                    "下一轮输出前 1-2 天内完成",
                ),
                deliverable=localized_text(
                    output_language,
                    {
                        "zh-CN": "补证清单、官方源链接、联系人与预算窗口核验结果",
                        "zh-TW": "補證清單、官方源連結、聯絡人與預算窗口核驗結果",
                        "en": "Evidence backlog, official links, and verified contact / budget-window results",
                    },
                    "补证清单、官方源链接、联系人与预算窗口核验结果",
                ),
            )
        ]
    solution_design = _research_section_items(report, ("解决方案设计", "解決方案設計", "solution design"))
    sales_strategy = _research_section_items(report, ("销售策略", "銷售策略", "sales strategy"))
    bidding_strategy = _research_section_items(report, ("投标规划", "投標規劃", "bidding strategy"))
    outreach_strategy = _research_section_items(report, ("陌生拜访", "陌生拜訪", "outreach strategy"))
    ecosystem_strategy = _research_section_items(report, ("生态伙伴", "生態夥伴", "ecosystem strategy"))
    commercial_opportunities = _research_section_items(report, ("项目与商机", "專案與商機", "opportunity"))
    next_actions = _research_section_items(report, ("下一步行动", "下一步行動", "next actions"))
    risks = _research_section_items(report, ("风险提示", "風險提示", "risks"))

    competition = [normalize_text(item) for item in report.competition_analysis if normalize_text(item)]
    buyer_peers = [normalize_text(item) for item in report.client_peer_moves if normalize_text(item)]
    winner_peers = [normalize_text(item) for item in report.winner_peer_moves if normalize_text(item)]
    outlook = [normalize_text(item) for item in report.five_year_outlook if normalize_text(item)]
    buyers = _entity_names_from_ranked(report.top_target_accounts, report.target_accounts, limit=3)
    competitors = _entity_names_from_ranked(report.top_competitors, report.competitor_profiles, limit=3)
    partners = _entity_names_from_ranked(report.top_ecosystem_partners, report.ecosystem_partners, limit=3)
    contacts = _pick_rows_for_entities(report.public_contact_channels, buyers + partners, limit=3) or _dedupe_strings(report.public_contact_channels, 3)
    department_rows = _pick_rows_for_entities(report.target_departments, buyers, limit=3) or _dedupe_strings(report.target_departments, 3)
    budget_rows = _dedupe_strings(report.budget_signals, 3)
    timeline_rows = _dedupe_strings(report.tender_timeline, 3)
    benchmark_rows = _dedupe_strings(report.benchmark_cases, 3)
    partner_rows = _pick_rows_for_entities(report.ecosystem_partners, partners, limit=3) or _dedupe_strings(report.ecosystem_partners, 3)
    competitor_weaknesses = _derive_competitor_weaknesses(report, competitors)
    visit_sequence = _derive_visit_sequence(report, output_language)
    scope_anchor = _derive_scope_anchor(report)
    entry_window = _derive_entry_window(report, output_language)

    cards: list[ResearchActionCardOut] = []

    def add_card(
        *,
        action_type: str,
        priority: str,
        title_map: dict[str, str],
        primary: list[str],
        secondary: list[str],
        long_horizon: list[str],
        evidence: list[str],
        fallback: str,
        target_persona_map: dict[str, str],
        execution_window_map: dict[str, str],
        deliverable_map: dict[str, str],
    ) -> None:
        steps = _build_phased_steps(
            short_term=primary,
            mid_term=secondary,
            long_term=long_horizon,
        )
        if not steps and not evidence and not fallback:
            return
        cards.append(
            ResearchActionCardOut(
                action_type=action_type,
                priority=priority,
                title=localized_text(output_language, title_map, title_map.get("zh-CN", "行动卡")),
                summary=_build_action_summary(primary, secondary, fallback=fallback),
                recommended_steps=steps,
                evidence=[item for item in evidence if item][:3],
                target_persona=localized_text(
                    output_language,
                    target_persona_map,
                    target_persona_map.get("zh-CN", ""),
                ),
                execution_window=localized_text(
                    output_language,
                    execution_window_map,
                    execution_window_map.get("zh-CN", ""),
                ),
                deliverable=localized_text(
                    output_language,
                    deliverable_map,
                    deliverable_map.get("zh-CN", ""),
                ),
            )
        )

    add_card(
        action_type="buyer_entry",
        priority="high",
        title_map={
            "zh-CN": "甲方建联行动卡",
            "zh-TW": "甲方建聯行動卡",
            "en": "Buyer Entry Card",
        },
        primary=_build_contact_and_partner_steps(
            buyers=buyers,
            contacts=contacts,
            partners=partners,
            output_language=output_language,
        ),
        secondary=department_rows or budget_rows or commercial_opportunities,
        long_horizon=[
            entry_window,
            f"围绕 {scope_anchor} 形成甲方分层名单，并持续补预算、项目代号和公开联系人。",
        ],
        evidence=_build_action_evidence(
            report,
            section_aliases=("项目与商机", "專案與商機", "opportunity", "销售策略", "銷售策略", "sales strategy"),
            fallback_rows=budget_rows + timeline_rows + buyer_peers,
        ),
        fallback=f"围绕 {scope_anchor} 收敛 3 类甲方、公开触达方式与预算口径，优先做首轮建联。",
        target_persona_map={
            "zh-CN": "客户经理、区域销售、行业顾问",
            "zh-TW": "客戶經理、區域銷售、產業顧問",
            "en": "Account managers, regional sales, and industry advisors",
        },
        execution_window_map={
            "zh-CN": entry_window,
            "zh-TW": entry_window,
            "en": entry_window,
        },
        deliverable_map={
            "zh-CN": "甲方名单、公开联系入口、建联话术和首轮拜访计划",
            "zh-TW": "甲方名單、公開聯絡入口、建聯話術與首輪拜訪計畫",
            "en": "Buyer list, public contact routes, outreach script, and first-visit plan",
        },
    )
    add_card(
        action_type="solution_differentiation",
        priority="high",
        title_map={
            "zh-CN": "差异化方案行动卡",
            "zh-TW": "差異化方案行動卡",
            "en": "Differentiated Solution Card",
        },
        primary=competitor_weaknesses or solution_design,
        secondary=benchmark_rows or competition or report.flagship_products,
        long_horizon=[
            "把竞品短板转成标书和汇报中的差异化章节，提前准备标杆案例与 ROI 证明。",
            f"围绕 {scope_anchor} 把本地生态、场景定制、交付节奏做成 3 条核心卖点。",
        ],
        evidence=_build_action_evidence(
            report,
            section_aliases=("解决方案设计", "解決方案設計", "solution design"),
            fallback_rows=competition + benchmark_rows + report.flagship_products,
        ),
        fallback=f"围绕 {scope_anchor} 的预算、决策部门和竞品线索，设计更强调场景定制、本地生态和交付节奏的方案。",
        target_persona_map={
            "zh-CN": "解决方案架构师、售前经理、产品经理",
            "zh-TW": "解決方案架構師、售前經理、產品經理",
            "en": "Solution architects, pre-sales managers, and product leads",
        },
        execution_window_map={
            "zh-CN": "未来 3-5 个工作日完成对标差异化方案和价值假设。",
            "zh-TW": "未來 3-5 個工作日完成對標差異化方案與價值假設。",
            "en": "Draft differentiated solution hypotheses within 3-5 business days.",
        },
        deliverable_map={
            "zh-CN": "竞品短板清单、差异化卖点和标杆案例对照",
            "zh-TW": "競品短板清單、差異化賣點與標竿案例對照",
            "en": "Competitor gaps, differentiated messaging, and benchmark comparisons",
        },
    )
    add_card(
        action_type="project_timing",
        priority="high",
        title_map={
            "zh-CN": "入场时钟与投标节奏卡",
            "zh-TW": "入場時鐘與投標節奏卡",
            "en": "Entry Timing and Bid Rhythm Card",
        },
        primary=timeline_rows or budget_rows or report.project_distribution,
        secondary=next_actions or bidding_strategy or outlook,
        long_horizon=[
            "持续跟踪采购意向、预算草案、立项批复、二三期扩容与试点转正信号。",
            "把伙伴、资质、POC、案例和价格策略按标前节奏提前排好。",
        ],
        evidence=_build_action_evidence(
            report,
            section_aliases=("投标规划", "投標規劃", "bidding strategy", "下一步行动", "下一步行動", "next actions"),
            fallback_rows=timeline_rows + budget_rows + winner_peers,
        ),
        fallback=entry_window,
        target_persona_map={
            "zh-CN": "销售负责人、投标经理、项目经理",
            "zh-TW": "銷售負責人、投標經理、專案經理",
            "en": "Sales owners, bid managers, and project managers",
        },
        execution_window_map={
            "zh-CN": entry_window,
            "zh-TW": entry_window,
            "en": entry_window,
        },
        deliverable_map={
            "zh-CN": "项目阶段判断、入场时间表和标前资源排期",
            "zh-TW": "專案階段判斷、入場時間表與標前資源排期",
            "en": "Project-stage view, entry timeline, and pre-bid resource plan",
        },
    )
    add_card(
        action_type="visit_sequence",
        priority="medium",
        title_map={
            "zh-CN": "年轻销售拜访顺序卡",
            "zh-TW": "年輕銷售拜訪順序卡",
            "en": "Visit Sequence Card for Junior Sales",
        },
        primary=visit_sequence,
        secondary=department_rows or report.leadership_focus or sales_strategy,
        long_horizon=[
            "在拿到业务需求和预算口径后，再争取领导层背书，避免过早越级。",
            "每轮拜访结束后，把新拿到的部门、联系人和顾虑回写到名单库，动态调整顺序。",
        ],
        evidence=_build_action_evidence(
            report,
            section_aliases=("陌生拜访", "陌生拜訪", "outreach strategy", "销售策略", "銷售策略", "sales strategy"),
            fallback_rows=department_rows + report.leadership_focus + report.public_contact_channels,
        ),
        fallback=f"围绕 {scope_anchor}，先验证业务发起部门，再进入信息化/预算/招采，最后争取领导背书。",
        target_persona_map={
            "zh-CN": "年轻销售、BD、区域客户经理",
            "zh-TW": "年輕銷售、BD、區域客戶經理",
            "en": "Junior sales, BD, and regional account managers",
        },
        execution_window_map={
            "zh-CN": "先在 1 周内完成部门映射，再按 2-3 周节奏推进多角色建联。",
            "zh-TW": "先在 1 週內完成部門映射，再按 2-3 週節奏推進多角色建聯。",
            "en": "Map departments in week 1, then sequence multi-role outreach over 2-3 weeks.",
        },
        deliverable_map={
            "zh-CN": "拜访顺序、角色画像和每一层的沟通目标",
            "zh-TW": "拜訪順序、角色畫像與每一層的溝通目標",
            "en": "Visit order, stakeholder map, and role-specific communication goals",
        },
    )
    add_card(
        action_type="ecosystem_bridge",
        priority="medium",
        title_map={
            "zh-CN": "生态牵线行动卡",
            "zh-TW": "生態牽線行動卡",
            "en": "Ecosystem Bridge Card",
        },
        primary=partner_rows or ecosystem_strategy,
        secondary=contacts or winner_peers or buyer_peers,
        long_horizon=[
            "按牵线价值、区域影响力和联合交付能力排序，筛掉纯产品售卖型公司。",
            "将伙伴分成咨询牵线方、区域总包、行业集成商三组，分别设计合作说法。",
        ],
        evidence=_build_action_evidence(
            report,
            section_aliases=("生态伙伴", "生態夥伴", "ecosystem strategy"),
            fallback_rows=partner_rows + winner_peers + report.public_contact_channels,
        ),
        fallback=f"优先筛出能牵线、联合调研或咨询集成的伙伴，为 {scope_anchor} 构建进入路径。",
        target_persona_map={
            "zh-CN": "生态合作经理、渠道负责人、区域销售",
            "zh-TW": "生態合作經理、渠道負責人、區域銷售",
            "en": "Ecosystem managers, channel owners, and regional sales",
        },
        execution_window_map={
            "zh-CN": "未来 1 周内确定 2-3 家能协同切入甲方的伙伴，并完成分工。",
            "zh-TW": "未來 1 週內確定 2-3 家能協同切入甲方的夥伴，並完成分工。",
            "en": "Within one week, confirm 2-3 partners that can open doors to the buyer.",
        },
        deliverable_map={
            "zh-CN": "伙伴名单、公开联系入口、联合拜访与联合方案建议",
            "zh-TW": "夥伴名單、公開聯絡入口、聯合拜訪與聯合方案建議",
            "en": "Partner list, public contact routes, and a joint-visit plan",
        },
    )
    add_card(
        action_type="two_week_attack_plan",
        priority="high",
        title_map={
            "zh-CN": "两周推进作战卡",
            "zh-TW": "兩週推進作戰卡",
            "en": "Two-week Execution Card",
        },
        primary=(next_actions or commercial_opportunities or solution_design)[:3],
        secondary=risks or benchmark_rows or contacts,
        long_horizon=[
            "如果前两周建联有效，立即进入方案共创、伙伴绑定和标前测试准备。",
            "如果证据仍弱，则回到区域/甲方池继续扩搜，不要直接进入低质量投标。",
        ],
        evidence=_build_action_evidence(
            report,
            section_aliases=("下一步行动", "下一步行動", "next actions", "项目与商机", "專案與商機", "opportunity"),
            fallback_rows=benchmark_rows + budget_rows + timeline_rows,
        ),
        fallback=f"先完成甲方筛选、方案差异化和伙伴分工，再决定是否进入标前排期。",
        target_persona_map={
            "zh-CN": "区域负责人、销售经理、售前经理",
            "zh-TW": "區域負責人、銷售經理、售前經理",
            "en": "Regional leads, sales managers, and pre-sales managers",
        },
        execution_window_map={
            "zh-CN": "未来两周内，完成名单、触达、方案和标前资源准备。",
            "zh-TW": "未來兩週內，完成名單、觸達、方案與標前資源準備。",
            "en": "Within two weeks, finish targeting, outreach, solution framing, and pre-bid preparation.",
        },
        deliverable_map={
            "zh-CN": "两周推进看板、角色分工、拜访纪要模板和下一轮判断标准",
            "zh-TW": "兩週推進看板、角色分工、拜訪紀要模板與下一輪判斷標準",
            "en": "A two-week execution board, role split, visit memo template, and next-step criteria",
        },
    )
    return cards


def build_research_report_markdown(
    report: ResearchReportDocument,
    *,
    output_language: str | None = None,
) -> tuple[str, str]:
    resolved_language = normalize_text(output_language or report.output_language or "zh-CN") or "zh-CN"
    filename_seed = "".join(
        ch for ch in (report.report_title or report.keyword or "research-report") if ch.isalnum() or ch in {" ", "-", "_"}
    ).strip().replace(" ", "_")
    if not filename_seed:
        filename_seed = "research-report"
    filename = f"{filename_seed[:48]}.md"

    lines = [
        f"# {report.report_title}",
        "",
        f"- {localized_text(resolved_language, {'zh-CN': '关键词', 'zh-TW': '關鍵詞', 'en': 'Keyword'}, '关键词')}: {report.keyword}",
        f"- {localized_text(resolved_language, {'zh-CN': '来源数', 'zh-TW': '來源數', 'en': 'Source Count'}, '来源数')}: {report.source_count}",
        f"- {localized_text(resolved_language, {'zh-CN': '证据密度', 'zh-TW': '證據密度', 'en': 'Evidence Density'}, '证据密度')}: {getattr(report, 'evidence_density', 'low')}",
        f"- {localized_text(resolved_language, {'zh-CN': '来源质量', 'zh-TW': '來源品質', 'en': 'Source Quality'}, '来源质量')}: {getattr(report, 'source_quality', 'low')}",
    ]
    if report.research_focus:
        lines.append(
            f"- {localized_text(resolved_language, {'zh-CN': '补充关注点', 'zh-TW': '補充關注點', 'en': 'Research Focus'}, '补充关注点')}: {report.research_focus}"
        )
    followup_context = getattr(report, "followup_context", None)
    if followup_context and (
        normalize_text(getattr(followup_context, "followup_report_title", ""))
        or normalize_text(getattr(followup_context, "supplemental_context", ""))
        or normalize_text(getattr(followup_context, "supplemental_evidence", ""))
        or normalize_text(getattr(followup_context, "supplemental_requirements", ""))
    ):
        lines.extend(
            [
                f"- {localized_text(resolved_language, {'zh-CN': '追问/补证上下文', 'zh-TW': '追問/補證上下文', 'en': 'Follow-up Context'}, '追问/补证上下文')}: "
                f"{normalize_text(getattr(followup_context, 'followup_report_title', '')) or localized_text(resolved_language, {'zh-CN': '已提供补充输入', 'zh-TW': '已提供補充輸入', 'en': 'Supplemented'}, '已提供补充输入')}",
            ]
        )
    if getattr(report, "generated_at", None):
        lines.append(
            f"- {localized_text(resolved_language, {'zh-CN': '生成时间', 'zh-TW': '生成時間', 'en': 'Generated At'}, '生成时间')}: {getattr(report, 'generated_at')}"
        )
    lines.extend(
        [
            "",
            f"## {localized_text(resolved_language, {'zh-CN': '执行摘要', 'zh-TW': '執行摘要', 'en': 'Executive Summary'}, '执行摘要')}",
            "",
            report.executive_summary,
            "",
            f"## {localized_text(resolved_language, {'zh-CN': '咨询价值', 'zh-TW': '顧問價值', 'en': 'Consulting Angle'}, '咨询价值')}",
            "",
            report.consulting_angle,
            "",
            f"## {localized_text(resolved_language, {'zh-CN': '研究方法与证据边界', 'zh-TW': '研究方法與證據邊界', 'en': 'Methodology and Evidence Boundaries'}, '研究方法与证据边界')}",
            "",
            f"- {localized_text(resolved_language, {'zh-CN': '方法', 'zh-TW': '方法', 'en': 'Method'}, '方法')}: "
            f"{localized_text(resolved_language, {'zh-CN': '基于公开网页、招投标公告、政策文件、行业媒体与公开披露做交叉检索与结构化归纳。', 'zh-TW': '基於公開網頁、招投標公告、政策文件、產業媒體與公開揭露做交叉檢索與結構化歸納。', 'en': 'Cross-search and structured synthesis over public web pages, tender notices, policy documents, industry media, and public filings.'}, '基于公开网页、招投标公告、政策文件、行业媒体与公开披露做交叉检索与结构化归纳。')}",
            f"- {localized_text(resolved_language, {'zh-CN': '边界', 'zh-TW': '邊界', 'en': 'Boundary'}, '边界')}: "
            f"{localized_text(resolved_language, {'zh-CN': '不绕过登录、付费墙或未授权后台数据；证据不足时会明确标注。', 'zh-TW': '不繞過登入、付費牆或未授權後台資料；證據不足時會明確標註。', 'en': 'No login, paywall, or unauthorized backend bypass is used; insufficient evidence is explicitly marked.'}, '不绕过登录、付费墙或未授权后台数据；证据不足时会明确标注。')}",
        ]
    )
    ranked_groups = [
        (
            localized_text(resolved_language, {"zh-CN": "高价值甲方 Top 3", "zh-TW": "高價值甲方 Top 3", "en": "Top 3 High-Value Buyers"}, "高价值甲方 Top 3"),
            getattr(report, "top_target_accounts", []),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "高威胁竞品 Top 3", "zh-TW": "高威脅競品 Top 3", "en": "Top 3 High-Threat Competitors"}, "高威胁竞品 Top 3"),
            getattr(report, "top_competitors", []),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "高影响力生态伙伴 Top 3", "zh-TW": "高影響力生態夥伴 Top 3", "en": "Top 3 High-Influence Ecosystem Partners"}, "高影响力生态伙伴 Top 3"),
            getattr(report, "top_ecosystem_partners", []),
        ),
    ]
    for title, items in ranked_groups:
        if not items:
            continue
        lines.extend(["", f"## {title}", ""])
        for index, item in enumerate(items, start=1):
            lines.append(
                f"### {index}. {item.name}（{localized_text(resolved_language, {'zh-CN': '价值等级', 'zh-TW': '價值等級', 'en': 'Value Tier'}, '价值等级')}: {_score_bucket_label(int(item.score), resolved_language)}）"
            )
            if item.reasoning:
                lines.append("")
                lines.append(item.reasoning)
            if item.evidence_links:
                lines.append("")
                lines.append(
                    localized_text(
                        resolved_language,
                        {"zh-CN": "证据链接：", "zh-TW": "證據連結：", "en": "Evidence Links:"},
                        "证据链接：",
                    )
                )
                lines.extend(
                    [
                        f"- {link.title} | {link.source_label or link.source_tier or 'source'} | {link.url}"
                        for link in item.evidence_links
                    ]
                )
    if report.query_plan:
        lines.extend(
            [
                "",
                f"## {localized_text(resolved_language, {'zh-CN': '检索路径', 'zh-TW': '檢索路徑', 'en': 'Search Plan'}, '检索路径')}",
                "",
            ]
        )
        lines.extend([f"- {query}" for query in report.query_plan])
    if followup_context and (
        normalize_text(getattr(followup_context, "followup_report_summary", ""))
        or normalize_text(getattr(followup_context, "supplemental_context", ""))
        or normalize_text(getattr(followup_context, "supplemental_evidence", ""))
        or normalize_text(getattr(followup_context, "supplemental_requirements", ""))
    ):
        lines.extend(
            [
                "",
                f"## {localized_text(resolved_language, {'zh-CN': '追问/补证输入', 'zh-TW': '追問/補證輸入', 'en': 'Follow-up Inputs'}, '追问/补证输入')}",
                "",
            ]
        )
        if normalize_text(getattr(followup_context, "followup_report_summary", "")):
            lines.append(f"- 上一版执行摘要：{getattr(followup_context, 'followup_report_summary')}")
        if normalize_text(getattr(followup_context, "supplemental_context", "")):
            lines.append(f"- 人工补充新信息：{getattr(followup_context, 'supplemental_context')}")
        if normalize_text(getattr(followup_context, "supplemental_evidence", "")):
            lines.append(f"- 人工补充新证据/待核验线索：{getattr(followup_context, 'supplemental_evidence')}")
        if normalize_text(getattr(followup_context, "supplemental_requirements", "")):
            lines.append(f"- 人工补充新需求：{getattr(followup_context, 'supplemental_requirements')}")
    for section in report.sections:
        lines.extend(["", f"## {section.title}", ""])
        lines.append(
            f"- {localized_text(resolved_language, {'zh-CN': '证据密度', 'zh-TW': '證據密度', 'en': 'Evidence Density'}, '证据密度')}: {section.evidence_density}"
        )
        lines.append(
            f"- {localized_text(resolved_language, {'zh-CN': '来源质量', 'zh-TW': '來源品質', 'en': 'Source Quality'}, '来源质量')}: {section.source_quality}"
        )
        if getattr(section, "official_source_ratio", 0):
            lines.append(
                f"- {localized_text(resolved_language, {'zh-CN': '官方源占比', 'zh-TW': '官方源佔比', 'en': 'Official Source Ratio'}, '官方源占比')}: {round(float(getattr(section, 'official_source_ratio', 0.0)) * 100)}%"
            )
        lines.extend([f"- {item}" for item in section.items])
        if getattr(section, "evidence_note", ""):
            lines.append("")
            lines.append(
                f"{localized_text(resolved_language, {'zh-CN': '说明', 'zh-TW': '說明', 'en': 'Note'}, '说明')}: {section.evidence_note}"
            )
        if getattr(section, "evidence_links", None):
            lines.append("")
            lines.append(
                localized_text(
                    resolved_language,
                    {"zh-CN": "证据锚点：", "zh-TW": "證據錨點：", "en": "Evidence Anchors:"},
                    "证据锚点：",
                )
            )
            lines.extend(
                [
                    f"- {(link.anchor_text or link.title)} | {link.source_label or link.source_tier or 'source'} | {link.url}"
                    for link in section.evidence_links
                ]
            )
        if getattr(section, "next_verification_steps", None):
            lines.append("")
            lines.append(
                localized_text(
                    resolved_language,
                    {"zh-CN": "下一步补证：", "zh-TW": "下一步補證：", "en": "Next Verification Steps:"},
                    "下一步补证：",
                )
            )
            lines.extend([f"- {value}" for value in section.next_verification_steps if normalize_text(value)])
    if getattr(report, "technical_appendix", None):
        appendix = report.technical_appendix
        lines.extend(
            [
                "",
                f"## {localized_text(resolved_language, {'zh-CN': '方法与边界', 'zh-TW': '方法與邊界', 'en': 'Method & Boundaries'}, '方法与边界')}",
                "",
            ]
        )
        if appendix.key_assumptions:
            lines.append(f"### {localized_text(resolved_language, {'zh-CN': '关键假设', 'zh-TW': '關鍵假設', 'en': 'Key Assumptions'}, '关键假设')}")
            lines.append("")
            lines.extend([f"- {value}" for value in appendix.key_assumptions])
        if appendix.scenario_comparison:
            lines.extend(["", f"### {localized_text(resolved_language, {'zh-CN': '情景对比', 'zh-TW': '情景對比', 'en': 'Scenario Comparison'}, '情景对比')}", ""])
            for scenario in appendix.scenario_comparison:
                lines.append(f"- {scenario.name}: {scenario.summary}")
                if scenario.implication:
                    lines.append(f"  {localized_text(resolved_language, {'zh-CN': '影响', 'zh-TW': '影響', 'en': 'Implication'}, '影响')}: {scenario.implication}")
        if appendix.limitations:
            lines.extend(["", f"### {localized_text(resolved_language, {'zh-CN': '限制条件', 'zh-TW': '限制條件', 'en': 'Limitations'}, '限制条件')}", ""])
            lines.extend([f"- {value}" for value in appendix.limitations])
        if appendix.technical_appendix:
            lines.extend(["", f"### {localized_text(resolved_language, {'zh-CN': '方法附录', 'zh-TW': '方法附錄', 'en': 'Technical Notes'}, '方法附录')}", ""])
            lines.extend([f"- {value}" for value in appendix.technical_appendix])
    if getattr(report, "review_queue", None):
        lines.extend(
            [
                "",
                f"## {localized_text(resolved_language, {'zh-CN': '待核验结论', 'zh-TW': '待核驗結論', 'en': 'Findings to Verify'}, '待核验结论')}",
                "",
            ]
        )
        for item in report.review_queue:
            lines.append(f"- {item.section_title} [{item.severity}]: {item.summary}")
            if item.recommended_action:
                lines.append(f"  {localized_text(resolved_language, {'zh-CN': '建议', 'zh-TW': '建議', 'en': 'Action'}, '建议')}: {item.recommended_action}")
    if report.sources:
        lines.extend(
            [
                "",
                f"## {localized_text(resolved_language, {'zh-CN': '参考来源', 'zh-TW': '參考來源', 'en': 'References'}, '参考来源')}",
                "",
            ]
        )
        for index, source in enumerate(report.sources, start=1):
            lines.extend(
                [
                    f"### [{index}] {source.title}",
                    "",
                    f"- URL: {source.url}",
                    f"- Domain: {source.domain or 'web'}",
                    f"- Query: {source.search_query}",
                    f"- Type: {source.source_type}",
                    f"- Status: {source.content_status}",
                    "",
                    source.snippet,
                    "",
                ]
            )
    return filename, "\n".join(lines).strip()


def _emit_research_progress(
    progress_callback: ResearchProgressCallback | None,
    stage_key: str,
    progress_percent: int,
    message: str,
) -> None:
    if progress_callback is None:
        return
    progress_callback(stage_key, progress_percent, message)


def _emit_research_snapshot(
    snapshot_callback: ResearchSnapshotCallback | None,
    report: ResearchReportResponse,
) -> None:
    if snapshot_callback is None:
        return
    snapshot_callback(report)


def _resolve_research_mode(payload: ResearchReportRequest) -> str:
    mode = normalize_text(str(getattr(payload, "research_mode", "") or "")).lower()
    if mode in {"fast", "deep"}:
        return mode
    deep_flag = getattr(payload, "deep_research", None)
    if deep_flag is False:
        return "fast"
    return "deep"


def _build_research_runtime(payload: ResearchReportRequest) -> dict[str, int | bool]:
    mode = _resolve_research_mode(payload)
    if mode == "fast":
        effective_max_sources = min(max(6, int(payload.max_sources)), 8)
        return {
            "mode": 0,
            "query_limit": 4,
            "expanded_query_limit": 3,
            "search_result_limit": 6,
            "effective_max_sources": effective_max_sources,
            "adapter_per_source_limit": 2,
            "expanded_adapter_per_source_limit": 2,
            "enough_hit_threshold": max(effective_max_sources + 2, 8),
            "expanded_selected_limit": min(10, effective_max_sources + 2),
            "search_timeout_seconds": 9,
            "url_timeout_seconds": 14,
            "llm_timeout_seconds": 24,
            "expansion_min_sources": 4,
            "expansion_min_dimensions": 3,
            "enable_expansion": True,
        }
    effective_max_sources = min(max(8, int(payload.max_sources)), 18)
    return {
        "mode": 1,
        "query_limit": min(12, max(6, get_settings().research_search_query_limit)),
        "expanded_query_limit": 8,
        "search_result_limit": min(12, max(8, get_settings().research_max_search_results)),
        "effective_max_sources": effective_max_sources,
        "adapter_per_source_limit": max(3, min(6, effective_max_sources // 2 or 1)),
        "expanded_adapter_per_source_limit": max(2, min(4, effective_max_sources // 2 or 1)),
        "enough_hit_threshold": max(effective_max_sources * 2, effective_max_sources + 2),
        "expanded_selected_limit": min(14, max(effective_max_sources + 2, effective_max_sources)),
        "search_timeout_seconds": min(get_settings().research_search_timeout_seconds, 15),
        "url_timeout_seconds": min(get_settings().url_fetch_timeout_seconds, 22),
        "llm_timeout_seconds": max(get_settings().research_llm_timeout_seconds, 45),
        "expansion_min_sources": min(effective_max_sources, 6),
        "expansion_min_dimensions": 5,
        "enable_expansion": True,
    }


def _build_research_focus_terms(keyword: str, research_focus: str | None) -> list[str]:
    chips = [normalize_text(keyword)]
    extra = [
        token
        for token in _tokenize_for_match(research_focus or "")
        if token not in GENERIC_FOCUS_TOKENS and len(normalize_text(token)) >= 2
    ]
    for token in extra:
        normalized = normalize_text(token)
        if not normalized or normalized in chips:
            continue
        chips.append(normalized)
        if len(chips) >= 4:
            break
    if len(chips) == 1 and research_focus:
        chips.append(_truncate_text(re.sub(r"\s+", " / ", research_focus), 18))
    return chips[:4]


def _build_progress_message(stage_label: str, *, keyword: str, research_focus: str | None, mode: str) -> str:
    chips = _build_research_focus_terms(keyword, _sanitize_research_focus_text(research_focus))
    scope = " / ".join(item for item in chips if item)
    mode_label = "深度调研" if mode == "deep" else "极速调研"
    if scope:
        return f"{mode_label} · {scope} · {stage_label}"
    return f"{mode_label} · {stage_label}"


def _build_followup_context(payload: ResearchReportRequest) -> ResearchFollowupContextOut:
    return ResearchFollowupContextOut(
        followup_report_title=normalize_text(payload.followup_report_title or ""),
        followup_report_summary=_truncate_text(normalize_text(payload.followup_report_summary or ""), 1200),
        supplemental_context=_truncate_text(normalize_text(payload.supplemental_context or ""), 1800),
        supplemental_evidence=_truncate_text(normalize_text(payload.supplemental_evidence or ""), 2200),
        supplemental_requirements=_truncate_text(normalize_text(payload.supplemental_requirements or ""), 1600),
    )


def _build_followup_planning_focus(
    research_focus: str | None,
    *,
    followup_context: ResearchFollowupContextOut,
) -> str | None:
    parts = [
        normalize_text(research_focus or ""),
        normalize_text(followup_context.supplemental_requirements or ""),
        normalize_text(followup_context.supplemental_context or ""),
        _truncate_text(normalize_text(followup_context.supplemental_evidence or ""), 240),
    ]
    merged = "；".join(part for part in parts if part)
    return _sanitize_research_focus_text(merged) or None


def _render_followup_prompt_context(followup_context: ResearchFollowupContextOut) -> str:
    sections = [
        ("上一版研报标题", followup_context.followup_report_title),
        ("上一版执行摘要", followup_context.followup_report_summary),
        ("人工补充新信息", followup_context.supplemental_context),
        ("人工补充新证据/待核验线索", followup_context.supplemental_evidence),
        ("人工补充新需求", followup_context.supplemental_requirements),
    ]
    lines = [f"- {label}: {value}" for label, value in sections if normalize_text(value)]
    return "\n".join(lines) if lines else "无"


def _to_research_source_outputs(sources: list[SourceDocument]) -> list[ResearchSourceOut]:
    return [
        ResearchSourceOut(
            title=source.title,
            url=source.url,
            domain=source.domain,
            snippet=source.snippet,
            search_query=source.search_query,
            source_type=source.source_type,
            content_status=source.content_status,
            source_label=source.source_label,
            source_tier=source.source_tier if source.source_tier in {"official", "media", "aggregate"} else "media",
        )
        for source in sources
    ]


def _build_partial_report_result(
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    research_mode: str,
    source_intelligence: dict[str, list[str]],
    scope_hints: dict[str, object],
    llm: object | None,
    llm_timeout_seconds: int,
) -> ResearchReportResult:
    scope_anchor = normalize_text(str(scope_hints.get("anchor_text", ""))) or normalize_text(research_focus or "") or keyword
    fallback = ResearchReportResult(
        report_title="",
        executive_summary="",
        consulting_angle="",
        industry_brief=list(source_intelligence.get("industry_brief", [])),
        key_signals=list(source_intelligence.get("key_signals", [])),
        policy_and_leadership=list(source_intelligence.get("policy_and_leadership", [])),
        commercial_opportunities=list(source_intelligence.get("commercial_opportunities", [])),
        solution_design=list(source_intelligence.get("solution_design", [])),
        sales_strategy=list(source_intelligence.get("sales_strategy", [])),
        bidding_strategy=list(source_intelligence.get("bidding_strategy", [])),
        outreach_strategy=list(source_intelligence.get("outreach_strategy", [])),
        ecosystem_strategy=list(source_intelligence.get("ecosystem_strategy", [])),
        target_accounts=list(source_intelligence.get("target_accounts", [])),
        target_departments=list(source_intelligence.get("target_departments", [])),
        public_contact_channels=list(source_intelligence.get("public_contact_channels", [])),
        account_team_signals=list(source_intelligence.get("account_team_signals", [])),
        budget_signals=list(source_intelligence.get("budget_signals", [])),
        project_distribution=list(source_intelligence.get("project_distribution", [])),
        strategic_directions=list(source_intelligence.get("strategic_directions", [])),
        tender_timeline=list(source_intelligence.get("tender_timeline", [])),
        leadership_focus=list(source_intelligence.get("leadership_focus", [])),
        ecosystem_partners=list(source_intelligence.get("ecosystem_partners", [])),
        competitor_profiles=list(source_intelligence.get("competitor_profiles", [])),
        benchmark_cases=list(source_intelligence.get("benchmark_cases", [])),
        flagship_products=list(source_intelligence.get("flagship_products", [])),
        key_people=list(source_intelligence.get("key_people", [])),
        five_year_outlook=list(source_intelligence.get("five_year_outlook", [])),
        client_peer_moves=list(source_intelligence.get("client_peer_moves", [])),
        winner_peer_moves=list(source_intelligence.get("winner_peer_moves", [])),
        competition_analysis=list(source_intelligence.get("competition_analysis", [])),
        risks=list(source_intelligence.get("risks", [])),
        next_actions=list(source_intelligence.get("next_actions", [])),
    )

    if llm is not None:
        try:
            raw = llm.run_prompt(
                "research_report_outline.txt",
                {
                    "keyword": keyword,
                "research_focus": research_focus or "",
                "output_language": output_language,
                "research_mode": research_mode,
                "scope_hints": json.dumps(scope_hints, ensure_ascii=False),
                "source_intelligence": json.dumps(source_intelligence, ensure_ascii=False),
                "industry_methodology_context": _render_industry_methodology_context(scope_hints),
                "__timeout_seconds": str(max(14, min(llm_timeout_seconds, 24))),
            },
        )
            outline = parse_research_strategy_refine_response(raw)
            if normalize_text(outline.report_title):
                fallback.report_title = normalize_text(outline.report_title)
            if normalize_text(outline.executive_summary):
                fallback.executive_summary = normalize_text(outline.executive_summary)
            if normalize_text(outline.consulting_angle):
                fallback.consulting_angle = normalize_text(outline.consulting_angle)
        except Exception:
            pass

    fallback = _apply_topic_specific_overrides(
        fallback,
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        scope_hints=scope_hints,
        intelligence=source_intelligence,
    )
    if not normalize_text(fallback.consulting_angle):
        fallback.consulting_angle = localized_text(
            output_language,
            {
                "zh-CN": f"优先围绕 {scope_anchor} 做范围锁定、预算核验、竞品对比和伙伴进入路径设计。",
                "zh-TW": f"優先圍繞 {scope_anchor} 做範圍鎖定、預算核驗、競品對比與夥伴進入路徑設計。",
                "en": f"Prioritize scope locking, budget validation, competitor comparison, and partner-led entry design around {scope_anchor}.",
            },
            f"优先围绕 {scope_anchor} 做范围锁定、预算核验、竞品对比和伙伴进入路径设计。",
        )
    return fallback


def _build_partial_report_response(
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    research_mode: str,
    parsed: ResearchReportResult,
    query_plan: list[str],
    sources: list[SourceDocument],
    source_diagnostics: ResearchSourceDiagnosticsOut,
    entity_graph: ResearchEntityGraphOut,
) -> ResearchReportResponse:
    evidence_density = _evidence_density_level(sources, parsed)
    source_quality = _source_quality_level(sources)
    sections = _build_sections(parsed, output_language, sources)
    report = ResearchReportResponse(
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        research_mode=research_mode,
        report_title=parsed.report_title,
        executive_summary=parsed.executive_summary,
        consulting_angle=parsed.consulting_angle,
        sections=sections,
        target_accounts=parsed.target_accounts,
        top_target_accounts=[],
        target_departments=parsed.target_departments,
        public_contact_channels=parsed.public_contact_channels,
        account_team_signals=parsed.account_team_signals,
        budget_signals=parsed.budget_signals,
        project_distribution=parsed.project_distribution,
        strategic_directions=parsed.strategic_directions,
        tender_timeline=parsed.tender_timeline,
        leadership_focus=parsed.leadership_focus,
        ecosystem_partners=parsed.ecosystem_partners,
        top_ecosystem_partners=[],
        competitor_profiles=parsed.competitor_profiles,
        top_competitors=[],
        benchmark_cases=parsed.benchmark_cases,
        flagship_products=parsed.flagship_products,
        key_people=parsed.key_people,
        five_year_outlook=parsed.five_year_outlook,
        client_peer_moves=parsed.client_peer_moves,
        winner_peer_moves=parsed.winner_peer_moves,
        competition_analysis=parsed.competition_analysis,
        source_count=len(sources),
        evidence_density=evidence_density,
        source_quality=source_quality,
        query_plan=query_plan,
        sources=_to_research_source_outputs(sources),
        source_diagnostics=source_diagnostics,
        entity_graph=entity_graph,
        generated_at=datetime.now(timezone.utc),
    )
    return _enrich_report_for_delivery(report)


def _stored_report_section_aliases() -> dict[str, tuple[str, ...]]:
    return {
        "industry_brief": ("行业资讯判断", "產業資訊判斷", "industry view"),
        "key_signals": ("关键信号", "關鍵信號", "key signals"),
        "policy_and_leadership": ("政策与领导信号", "政策與領導信號", "policy and leadership"),
        "commercial_opportunities": ("项目与商机判断", "專案與商機判斷", "opportunity map"),
        "solution_design": ("解决方案设计建议", "解決方案設計建議", "solution design"),
        "sales_strategy": ("销售策略", "銷售策略", "sales strategy"),
        "bidding_strategy": ("投标规划", "投標規劃", "bidding strategy"),
        "outreach_strategy": ("陌生拜访建议", "陌生拜訪建議", "outreach strategy"),
        "ecosystem_strategy": ("生态伙伴建议", "生態夥伴建議", "ecosystem strategy"),
        "risks": ("风险提示", "風險提示", "risks"),
        "next_actions": ("下一步行动", "下一步行動", "next actions"),
    }


def _report_sources_to_source_documents(sources: list[ResearchSourceOut]) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    for source in sources:
        url = normalize_text(source.url)
        if not url:
            continue
        title = normalize_text(source.title) or url
        domain = normalize_text(source.domain or "") or extract_domain(url)
        source_type = normalize_text(source.source_type) or _classify_source_type(url)
        source_label = _derive_source_label(
            source_type=source_type,
            domain=domain,
            fallback=normalize_text(source.source_label or "") or None,
        )
        source_tier = (
            source.source_tier
            if source.source_tier in {"official", "media", "aggregate"}
            else _classify_source_tier(source_type=source_type, domain=domain, source_label=source_label)
        )
        snippet = _truncate_text(
            _clean_source_text_for_analysis(source.snippet or "") or _clean_source_text_for_analysis(title),
            180,
        )
        documents.append(
            SourceDocument(
                title=title,
                url=url,
                domain=domain,
                snippet=snippet,
                search_query=normalize_text(source.search_query),
                source_type=source_type,
                content_status=normalize_text(source.content_status) or "snippet_only",
                excerpt=snippet,
                source_label=source_label,
                source_tier=source_tier,
                source_origin="adapter" if source_label else "search",
            )
        )
    return _dedupe_sources(documents)


def _stored_report_to_result(report: ResearchReportResponse) -> ResearchReportResult:
    section_aliases = _stored_report_section_aliases()
    payload: dict[str, object] = {
        "report_title": normalize_text(report.report_title),
        "executive_summary": normalize_text(report.executive_summary),
        "consulting_angle": normalize_text(report.consulting_angle),
        "industry_brief": _research_section_items(report, section_aliases["industry_brief"]),
        "key_signals": _research_section_items(report, section_aliases["key_signals"]),
        "policy_and_leadership": _research_section_items(report, section_aliases["policy_and_leadership"]),
        "commercial_opportunities": _research_section_items(report, section_aliases["commercial_opportunities"]),
        "solution_design": _research_section_items(report, section_aliases["solution_design"]),
        "sales_strategy": _research_section_items(report, section_aliases["sales_strategy"]),
        "bidding_strategy": _research_section_items(report, section_aliases["bidding_strategy"]),
        "outreach_strategy": _research_section_items(report, section_aliases["outreach_strategy"]),
        "ecosystem_strategy": _research_section_items(report, section_aliases["ecosystem_strategy"]),
        "target_accounts": list(report.target_accounts),
        "target_departments": list(report.target_departments),
        "public_contact_channels": list(report.public_contact_channels),
        "account_team_signals": list(report.account_team_signals),
        "budget_signals": list(report.budget_signals),
        "project_distribution": list(report.project_distribution),
        "strategic_directions": list(report.strategic_directions),
        "tender_timeline": list(report.tender_timeline),
        "leadership_focus": list(report.leadership_focus),
        "ecosystem_partners": list(report.ecosystem_partners),
        "competitor_profiles": list(report.competitor_profiles),
        "benchmark_cases": list(report.benchmark_cases),
        "flagship_products": list(report.flagship_products),
        "key_people": list(report.key_people),
        "five_year_outlook": list(report.five_year_outlook),
        "client_peer_moves": list(report.client_peer_moves),
        "winner_peer_moves": list(report.winner_peer_moves),
        "competition_analysis": list(report.competition_analysis),
        "risks": _research_section_items(report, section_aliases["risks"]),
        "next_actions": _research_section_items(report, section_aliases["next_actions"]),
    }
    for key, value in list(payload.items()):
        if isinstance(value, list):
            payload[key] = _sanitize_report_field_rows(key, value)
    return ResearchReportResult.model_validate(payload)


def _report_intelligence_from_result(report: ResearchReportResponse, result: ResearchReportResult) -> dict[str, list[str]]:
    return {
        "industry_brief": list(result.industry_brief),
        "key_signals": list(result.key_signals),
        "policy_and_leadership": list(result.policy_and_leadership),
        "commercial_opportunities": list(result.commercial_opportunities),
        "solution_design": list(result.solution_design),
        "sales_strategy": list(result.sales_strategy),
        "bidding_strategy": list(result.bidding_strategy),
        "outreach_strategy": list(result.outreach_strategy),
        "ecosystem_strategy": list(result.ecosystem_strategy),
        "target_accounts": _dedupe_strings(
            [
                *result.target_accounts,
                *(normalize_text(item.name) for item in report.top_target_accounts if normalize_text(item.name)),
                *(normalize_text(item.name) for item in report.pending_target_candidates if normalize_text(item.name)),
            ],
            6,
        ),
        "target_departments": list(result.target_departments),
        "public_contact_channels": list(result.public_contact_channels),
        "account_team_signals": list(result.account_team_signals),
        "budget_signals": list(result.budget_signals),
        "project_distribution": list(result.project_distribution),
        "strategic_directions": list(result.strategic_directions),
        "tender_timeline": list(result.tender_timeline),
        "leadership_focus": list(result.leadership_focus),
        "ecosystem_partners": _dedupe_strings(
            [
                *result.ecosystem_partners,
                *(normalize_text(item.name) for item in report.top_ecosystem_partners if normalize_text(item.name)),
                *(normalize_text(item.name) for item in report.pending_partner_candidates if normalize_text(item.name)),
            ],
            6,
        ),
        "competitor_profiles": _dedupe_strings(
            [
                *result.competitor_profiles,
                *(normalize_text(item.name) for item in report.top_competitors if normalize_text(item.name)),
                *(normalize_text(item.name) for item in report.pending_competitor_candidates if normalize_text(item.name)),
            ],
            6,
        ),
        "benchmark_cases": list(result.benchmark_cases),
        "flagship_products": list(result.flagship_products),
        "key_people": list(result.key_people),
        "five_year_outlook": list(result.five_year_outlook),
        "client_peer_moves": list(result.client_peer_moves),
        "winner_peer_moves": list(result.winner_peer_moves),
        "competition_analysis": list(result.competition_analysis),
        "risks": list(result.risks),
        "next_actions": list(result.next_actions),
    }


def _canonical_org_name_from_evidence_links(
    evidence_links: Iterable[object] | None,
    *,
    scope_hints: dict[str, object],
) -> str:
    for raw_link in evidence_links or []:
        if isinstance(raw_link, dict):
            title = normalize_text(str(raw_link.get("title") or ""))
            url = normalize_text(str(raw_link.get("url") or ""))
            source_label = normalize_text(str(raw_link.get("source_label") or ""))
        else:
            title = normalize_text(str(getattr(raw_link, "title", "") or ""))
            url = normalize_text(str(getattr(raw_link, "url", "") or ""))
            source_label = normalize_text(str(getattr(raw_link, "source_label", "") or ""))
        domain_canonical = _canonical_org_name_from_domain(extract_domain(url) or "")
        if domain_canonical:
            return _resolve_known_org_name(domain_canonical, scope_hints=scope_hints)
        title_candidates = _extract_rank_entity_candidates(title, scope_hints=scope_hints)
        if title_candidates:
            return title_candidates[0]
        label_candidate = _strip_org_public_suffixes(source_label.removesuffix("官网").removesuffix("集团官网"))
        if label_candidate and (_is_plausible_entity_name(label_candidate) or _is_lightweight_entity_name(label_candidate)):
            return _resolve_known_org_name(label_candidate, scope_hints=scope_hints)
    return ""


def _canonicalize_stored_entity_name(
    value: str,
    *,
    field_key: str,
    scope_hints: dict[str, object],
    source_documents: list[SourceDocument],
    evidence_links: Iterable[object] | None = None,
) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    role_field = field_key in ENTITY_ROLE_FIELDS
    candidate = _sanitize_entity_row(field_key, normalized) if role_field else normalize_text(value)
    linked_canonical = _canonical_org_name_from_evidence_links(evidence_links, scope_hints=scope_hints)
    if not candidate:
        return linked_canonical
    entity_name = _extract_rank_entity_name(candidate) or _fallback_entity_name_from_row(candidate) or candidate
    entity_name = _resolve_known_org_name(entity_name, scope_hints=scope_hints)
    if linked_canonical and (
        not entity_name
        or _looks_like_fragment_entity_name(entity_name)
        or _contains_low_value_entity_token(entity_name)
        or _looks_like_placeholder_entity_name(entity_name)
    ):
        entity_name = linked_canonical
    if not entity_name:
        return ""
    if role_field and not (_is_plausible_entity_name(entity_name) or _is_lightweight_entity_name(entity_name)):
        return linked_canonical if linked_canonical and (_is_plausible_entity_name(linked_canonical) or _is_lightweight_entity_name(linked_canonical)) else ""
    if linked_canonical and _entity_canonical_key(linked_canonical) != _entity_canonical_key(entity_name):
        canonical_supported = any(_source_mentions_entity(source, linked_canonical) for source in source_documents)
        candidate_supported = any(_source_mentions_entity(source, entity_name) for source in source_documents)
        if canonical_supported and not candidate_supported:
            entity_name = linked_canonical
    return normalize_text(entity_name)


def _canonicalize_stored_entity_rows(
    values: Iterable[str],
    *,
    field_key: str,
    scope_hints: dict[str, object],
    source_documents: list[SourceDocument],
) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values:
        candidate = _canonicalize_stored_entity_name(
            normalize_text(str(raw)),
            field_key=field_key,
            scope_hints=scope_hints,
            source_documents=source_documents,
        )
        key = _entity_canonical_key(candidate)
        if not candidate or not key or key in seen:
            continue
        seen.add(key)
        cleaned.append(candidate)
    return cleaned


def _canonicalize_stored_ranked_entities(
    entities: Iterable[ResearchRankedEntityOut],
    *,
    field_key: str,
    scope_hints: dict[str, object],
    source_documents: list[SourceDocument],
) -> list[ResearchRankedEntityOut]:
    deduped: dict[str, ResearchRankedEntityOut] = {}
    order: list[str] = []
    for entity in entities:
        canonical_name = _canonicalize_stored_entity_name(
            entity.name,
            field_key=field_key,
            scope_hints=scope_hints,
            source_documents=source_documents,
            evidence_links=entity.evidence_links,
        )
        canonical_key = _entity_canonical_key(canonical_name)
        if not canonical_name or not canonical_key:
            continue
        updated = entity.model_copy(update={"name": canonical_name})
        current = deduped.get(canonical_key)
        if current is None:
            deduped[canonical_key] = updated
            order.append(canonical_key)
            continue
        if int(updated.score or 0) > int(current.score or 0):
            merged_links = list(current.evidence_links)
            for link in updated.evidence_links:
                if getattr(link, "url", "") and not any(getattr(item, "url", "") == getattr(link, "url", "") for item in merged_links):
                    merged_links.append(link)
            deduped[canonical_key] = updated.model_copy(update={"evidence_links": merged_links[:3]})
    return [deduped[key] for key in order]


def _canonicalize_stored_report_entities(
    report: ResearchReportResponse,
    *,
    scope_hints: dict[str, object],
    source_documents: list[SourceDocument],
) -> ResearchReportResponse:
    canonical_top_targets = _canonicalize_stored_ranked_entities(
        report.top_target_accounts,
        field_key="target_accounts",
        scope_hints=scope_hints,
        source_documents=source_documents,
    )
    canonical_pending_targets = _canonicalize_stored_ranked_entities(
        report.pending_target_candidates,
        field_key="target_accounts",
        scope_hints=scope_hints,
        source_documents=source_documents,
    )
    canonical_top_partners = _canonicalize_stored_ranked_entities(
        report.top_ecosystem_partners,
        field_key="ecosystem_partners",
        scope_hints=scope_hints,
        source_documents=source_documents,
    )
    canonical_pending_partners = _canonicalize_stored_ranked_entities(
        report.pending_partner_candidates,
        field_key="ecosystem_partners",
        scope_hints=scope_hints,
        source_documents=source_documents,
    )
    canonical_top_competitors = _canonicalize_stored_ranked_entities(
        report.top_competitors,
        field_key="competitor_profiles",
        scope_hints=scope_hints,
        source_documents=source_documents,
    )
    canonical_pending_competitors = _canonicalize_stored_ranked_entities(
        report.pending_competitor_candidates,
        field_key="competitor_profiles",
        scope_hints=scope_hints,
        source_documents=source_documents,
    )
    canonical_targets = _dedupe_strings(
        [
            *[item.name for item in canonical_top_targets],
            *[item.name for item in canonical_pending_targets],
            *_canonicalize_stored_entity_rows(
                report.target_accounts,
                field_key="target_accounts",
                scope_hints=scope_hints,
                source_documents=source_documents,
            ),
        ],
        6,
    )
    canonical_partners = _dedupe_strings(
        [
            *[item.name for item in canonical_top_partners],
            *[item.name for item in canonical_pending_partners],
            *_canonicalize_stored_entity_rows(
                report.ecosystem_partners,
                field_key="ecosystem_partners",
                scope_hints=scope_hints,
                source_documents=source_documents,
            ),
        ],
        6,
    )
    canonical_competitors = _dedupe_strings(
        [
            *[item.name for item in canonical_top_competitors],
            *[item.name for item in canonical_pending_competitors],
            *_canonicalize_stored_entity_rows(
                report.competitor_profiles,
                field_key="competitor_profiles",
                scope_hints=scope_hints,
                source_documents=source_documents,
            ),
        ],
        6,
    )
    diagnostics = report.source_diagnostics.model_copy(
        update={
            "scope_clients": canonical_targets[:4],
        }
    )
    return report.model_copy(
        update={
            "target_accounts": canonical_targets,
            "top_target_accounts": canonical_top_targets,
            "pending_target_candidates": canonical_pending_targets,
            "ecosystem_partners": canonical_partners,
            "top_ecosystem_partners": canonical_top_partners,
            "pending_partner_candidates": canonical_pending_partners,
            "competitor_profiles": canonical_competitors,
            "top_competitors": canonical_top_competitors,
            "pending_competitor_candidates": canonical_pending_competitors,
            "source_diagnostics": diagnostics,
        }
    )


def _canonicalize_stored_result_entities(
    result: ResearchReportResult,
    *,
    scope_hints: dict[str, object],
    source_documents: list[SourceDocument],
) -> ResearchReportResult:
    return result.model_copy(
        update={
            "target_accounts": _canonicalize_stored_entity_rows(
                result.target_accounts,
                field_key="target_accounts",
                scope_hints=scope_hints,
                source_documents=source_documents,
            ),
            "ecosystem_partners": _canonicalize_stored_entity_rows(
                result.ecosystem_partners,
                field_key="ecosystem_partners",
                scope_hints=scope_hints,
                source_documents=source_documents,
            ),
            "competitor_profiles": _canonicalize_stored_entity_rows(
                result.competitor_profiles,
                field_key="competitor_profiles",
                scope_hints=scope_hints,
                source_documents=source_documents,
            ),
        }
    )


def _clean_candidate_profile_company_names(values: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        normalized = normalize_text(str(value))
        if (
            not normalized
            or "待验证" in normalized
            or "待驗證" in normalized
            or _looks_like_insufficient(normalized)
            or _looks_like_scope_prompt_noise(normalized)
            or _looks_like_source_artifact_text(normalized)
        ):
            continue
        candidate = _extract_rank_entity_name(normalized) or _fallback_entity_name_from_row(normalized) or normalized
        candidate = _strip_entity_leading_noise(candidate)
        if (
            not candidate
            or re.search(r"(19|20)\d{2}", candidate)
            or _looks_like_fragment_entity_name(candidate)
            or _contains_low_value_entity_token(candidate)
            or _looks_like_scope_prompt_noise(candidate)
            or _looks_like_placeholder_entity_name(candidate)
        ):
            continue
        if not _is_plausible_entity_name(candidate) and not _is_lightweight_entity_name(candidate):
            continue
        cleaned.append(candidate)
    return _dedupe_strings(cleaned, 6)


def _is_trustworthy_scope_client_name(value: str, *, theme_labels: list[str] | None = None) -> bool:
    normalized = _strip_entity_leading_noise(value)
    active_theme_labels = [normalize_text(item) for item in theme_labels or [] if normalize_text(item)]
    lowered = normalized.lower()
    if not normalized:
        return False
    if re.search(r"(19|20)\d{2}", normalized):
        return False
    if _looks_like_scope_prompt_noise(normalized):
        return False
    if _looks_like_placeholder_entity_name(normalized):
        return False
    if normalized in {"中国政府", "办公厅", "一网通办", "随申办"}:
        return False
    if any(token in normalized for token in GENERIC_SCOPE_CLIENT_TOKENS):
        return False
    if any(token in normalized for token in ("公开招标公告", "采购项目", "中标结果", "代表样本", "成功举办")):
        return False
    if normalized.startswith(("访", "第", "相关负责人", "对公开市场投资者而言", "在杭州市")):
        return False
    if normalized.startswith(("一家", "一人", "一个", "一种", "是依托", "不仅", "构建", "办公厅", "上海作为")):
        return False
    if (
        any(token in normalized for token in ("和", "及", "与"))
        and any(token in normalized for token in ("全球", "国际", "重点"))
        and not any(token in normalized for token in ("集团", "公司", "局", "委", "办", "中心", "政府"))
    ):
        return False
    if "AI漫剧" in active_theme_labels and any(token in normalized for token in ("政府", "办公厅", "市委", "局", "委", "办")):
        return False
    if "政务云" in active_theme_labels and not any(
        token in normalized
        for token in ("政府", "局", "委", "办", "中心", "集团", "公司", "平台", "城投", "国资", "大数据", "信息")
    ):
        return False
    if normalized in KNOWN_LIGHTWEIGHT_ENTITY_NAMES or normalized in SPECIAL_ENTITY_ALIASES:
        return True
    if any(token in normalized for token in ENTITY_SUFFIX_TOKENS):
        if any(token in lowered for token in ("maas", "iaas", "paas", "saas")) and "公司" in normalized:
            return False
        return True
    return False


def _clean_scope_entity_names(
    values: Iterable[str],
    *,
    limit: int = 4,
    theme_labels: list[str] | None = None,
) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        normalized = normalize_text(str(value))
        if (
            not normalized
            or _looks_like_insufficient(normalized)
            or _looks_like_scope_prompt_noise(normalized)
            or _looks_like_source_artifact_text(normalized)
        ):
            continue
        candidate = _extract_rank_entity_name(normalized) or _fallback_entity_name_from_row(normalized)
        candidate = _strip_entity_leading_noise(candidate)
        if (
            not candidate
            or _looks_like_fragment_entity_name(candidate)
            or _contains_low_value_entity_token(candidate)
            or _looks_like_scope_prompt_noise(candidate)
            or _looks_like_placeholder_entity_name(candidate)
        ):
            continue
        if not _is_plausible_entity_name(candidate) and not _is_lightweight_entity_name(candidate):
            continue
        if not _is_trustworthy_scope_client_name(candidate, theme_labels=theme_labels):
            continue
        cleaned.append(candidate)
    return _dedupe_strings(cleaned, limit)


def _stored_source_is_low_signal(
    source: SourceDocument,
    *,
    theme_terms: list[str],
    scope_hints: dict[str, object],
) -> bool:
    text = _source_text(source)
    if not text:
        return True
    lowered = text.lower()
    domain = normalize_text(source.domain or "").lower()
    title_lower = normalize_text(source.title).lower()
    client_terms = [
        normalize_text(str(item)).lower()
        for item in scope_hints.get("clients", []) or []
        if normalize_text(str(item))
    ]
    if any(token in text for token in FIELD_ROW_NOISE_TOKENS):
        return True
    if any(token in lowered for token in ("header_", "[source", "javascript:", "返回顶部", "跳转到主要内容区域")):
        return True
    if _looks_like_insufficient(text):
        return True
    theme_score = _source_theme_match_score(
        source,
        theme_terms=theme_terms,
        scope_hints=scope_hints,
    )
    procurement_aggregate_like = any(token in domain for token in ("cecbid", "cebpubservice", "chinabidding", "china-cpp", "jianyu"))
    tech_media_like = source.source_type == "tech_media_feed" or "yuntoutiao" in domain
    client_hit = any(term in lowered or term in title_lower for term in client_terms)
    if procurement_aggregate_like and not client_hit and theme_score < 14:
        return True
    if tech_media_like and not client_hit and theme_score < 16:
        return True
    if theme_terms and theme_score < 6 and source.source_tier != "official":
        return True
    if source.source_tier == "aggregate" and source.content_status == "snippet_only" and theme_score < 8:
        return True
    return False


def _stored_report_concrete_targets(report: ResearchReportResponse) -> list[str]:
    return _dedupe_strings(
        [
            _sanitize_entity_row("target_accounts", normalize_text(name))
            for name in [
                *(normalize_text(item.name) for item in report.top_target_accounts if normalize_text(item.name)),
                *(normalize_text(item.name) for item in report.pending_target_candidates if normalize_text(item.name)),
                *(normalize_text(item) for item in report.target_accounts if normalize_text(item)),
            ]
            if normalize_text(name)
        ],
        4,
    )


def _resolve_stored_report_target_support(
    report: ResearchReportResponse,
    *,
    source_documents: list[SourceDocument],
    scope_hints: dict[str, object],
) -> tuple[list[str], list[str], list[str]]:
    theme_terms = _build_theme_terms(report.keyword, report.research_focus, scope_hints)
    concrete_targets = _stored_report_concrete_targets(report)
    supported_targets = [
        target
        for target in concrete_targets
        if any(
            _source_supports_target_account(
                source,
                target,
                theme_terms=theme_terms,
                scope_hints=scope_hints,
            )
            for source in source_documents
        )
    ]
    supported_target_set = {target for target in supported_targets}
    unsupported_targets = [target for target in concrete_targets if target not in supported_target_set]
    return concrete_targets, supported_targets, unsupported_targets


def _guarded_rewrite_reason_label(reason: str, output_language: str) -> str:
    reason_map = {
        "single_source_nonready": {
            "zh-CN": "来源过少，当前报告还没达到可推进门槛。",
            "zh-TW": "來源過少，目前報告還沒達到可推進門檻。",
            "en": "Too few sources to treat this report as execution-ready.",
        },
        "no_sources": {
            "zh-CN": "没有保留到可用来源。",
            "zh-TW": "沒有保留到可用來源。",
            "en": "No usable sources were retained.",
        },
        "fallback_low_support": {
            "zh-CN": "当前仍是兜底候选，严格命中或官方源支撑不足。",
            "zh-TW": "目前仍是兜底候選，嚴格命中或官方源支撐不足。",
            "en": "The result is still fallback-grade and lacks strong strict-match or official-source support.",
        },
        "low_retrieval_low_official": {
            "zh-CN": "检索质量偏低，且官方源覆盖不足。",
            "zh-TW": "檢索品質偏低，且官方源覆蓋不足。",
            "en": "Retrieval quality is low and official-source coverage is too weak.",
        },
        "source_noise_majority": {
            "zh-CN": "保留来源里噪声占比过高。",
            "zh-TW": "保留來源裡噪聲佔比過高。",
            "en": "Too much of the retained source set is low-signal noise.",
        },
        "no_target_source_support": {
            "zh-CN": "目标账户没有被来源正文支撑。",
            "zh-TW": "目標帳戶沒有被來源正文支撐。",
            "en": "The named target accounts are not supported by source text.",
        },
        "unsupported_targets": {
            "zh-CN": "目标账户只有推断，没有形成预算、官方源或正文共同支撑。",
            "zh-TW": "目標帳戶只有推斷，沒有形成預算、官方源或正文共同支撐。",
            "en": "The target accounts are inferred only and lack budget, official-source, or source-text support.",
        },
        "no_concrete_targets": {
            "zh-CN": "当前还没有收敛到可验证的具体账户。",
            "zh-TW": "目前還沒有收斂到可驗證的具體帳戶。",
            "en": "The report has not converged on concrete accounts that can be verified.",
        },
        "post_rewrite_low_signal_guard": {
            "zh-CN": "重写后仍然低信号，继续保留在待核验 backlog。",
            "zh-TW": "重寫後仍然低訊號，繼續保留在待核驗 backlog。",
            "en": "The rewritten result is still low-signal and remains in the verification backlog.",
        },
    }
    template = reason_map.get(reason)
    if template:
        return localized_text(output_language, template, template.get("zh-CN", reason))
    return normalize_text(reason.replace("_", " ")) or reason


def _apply_guarded_rewrite_diagnostics(
    source_diagnostics: ResearchSourceDiagnosticsOut,
    *,
    output_language: str,
    guarded_backlog: bool,
    guarded_rewrite_reasons: Iterable[str],
    supported_target_accounts: Iterable[str],
    unsupported_target_accounts: Iterable[str],
) -> ResearchSourceDiagnosticsOut:
    reason_codes = _dedupe_strings(
        [normalize_text(str(reason)) for reason in guarded_rewrite_reasons if normalize_text(str(reason))],
        8,
    )
    supported_accounts = _dedupe_strings(
        [normalize_text(str(item)) for item in supported_target_accounts if normalize_text(str(item))],
        4,
    )
    unsupported_accounts = _dedupe_strings(
        [
            normalize_text(str(item))
            for item in unsupported_target_accounts
            if normalize_text(str(item)) and normalize_text(str(item)) not in supported_accounts
        ],
        4,
    )
    return source_diagnostics.model_copy(
        update={
            "guarded_backlog": guarded_backlog,
            "guarded_rewrite_reasons": reason_codes,
            "guarded_rewrite_reason_labels": [_guarded_rewrite_reason_label(reason, output_language) for reason in reason_codes],
            "supported_target_accounts": supported_accounts,
            "unsupported_target_accounts": unsupported_accounts,
        }
    )


def _assess_stored_report_rewrite_mode(
    report: ResearchReportResponse,
    *,
    source_documents: list[SourceDocument],
    scope_hints: dict[str, object],
) -> tuple[str, list[str], dict[str, float]]:
    diagnostics = report.source_diagnostics if getattr(report, "source_diagnostics", None) else ResearchSourceDiagnosticsOut()
    retained_source_count = len(source_documents)
    official_ratio = float(diagnostics.official_source_ratio or 0.0)
    strict_match_ratio = float(diagnostics.strict_match_ratio or 0.0)
    unique_domain_count = int(
        diagnostics.unique_domain_count
        or len({normalize_text(source.domain or "") for source in source_documents if normalize_text(source.domain or "")})
    )
    theme_terms = _build_theme_terms(report.keyword, report.research_focus, scope_hints)
    readiness = _resolved_report_readiness(report)
    actionable_budget_rows = [row for row in report.budget_signals if _is_actionable_budget_row(row)]
    actionable_timeline_rows = [row for row in report.tender_timeline if _is_summary_fact_row(row)]
    prefer_company_entities = bool(scope_hints.get("prefer_company_entities"))
    bad_executive_summary = _looks_like_bad_executive_summary(report.executive_summary)
    concrete_targets, supported_targets, _unsupported_targets = _resolve_stored_report_target_support(
        report,
        source_documents=source_documents,
        scope_hints=scope_hints,
    )
    supported_target_count = len(supported_targets)
    low_signal_source_count = sum(
        1
        for source in source_documents
        if _stored_source_is_low_signal(
            source,
            theme_terms=theme_terms,
            scope_hints=scope_hints,
        )
    )
    reasons: list[str] = []
    if retained_source_count <= 1 and readiness.status != "ready" and (
        not concrete_targets or not (actionable_budget_rows or actionable_timeline_rows)
    ):
        reasons.append("single_source_nonready")
    if retained_source_count == 0:
        reasons.append("no_sources")
    if diagnostics.evidence_mode == "fallback" and (official_ratio < 0.12 or strict_match_ratio < 0.25):
        reasons.append("fallback_low_support")
    if diagnostics.retrieval_quality == "low" and official_ratio < 0.15 and unique_domain_count < 3:
        reasons.append("low_retrieval_low_official")
    if retained_source_count and low_signal_source_count >= max(2, (retained_source_count + 1) // 2):
        reasons.append("source_noise_majority")
    if concrete_targets and supported_target_count == 0:
        reasons.append("no_target_source_support")
    if concrete_targets and supported_target_count == 0 and readiness.status != "ready" and (
        low_signal_source_count >= max(1, retained_source_count // 2)
        or not actionable_budget_rows
        or official_ratio < 0.55
    ):
        reasons.append("unsupported_targets")
    if not concrete_targets and (
        official_ratio < 0.1
        or (readiness.status != "ready" and retained_source_count < 4)
        or (readiness.status != "ready" and prefer_company_entities)
        or (readiness.status != "ready" and not actionable_budget_rows and low_signal_source_count >= max(1, retained_source_count // 2))
        or (readiness.status != "ready" and bad_executive_summary)
    ):
        reasons.append("no_concrete_targets")
    return (
        "guarded" if reasons else "rewrite",
        reasons,
        {
            "retained_source_count": float(retained_source_count),
            "official_ratio": official_ratio,
            "strict_match_ratio": strict_match_ratio,
            "unique_domain_count": float(unique_domain_count),
            "low_signal_source_count": float(low_signal_source_count),
            "concrete_target_count": float(len(concrete_targets)),
            "supported_target_count": float(supported_target_count),
        },
    )


def _build_guarded_rewrite_title(
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
    output_language: str,
) -> str:
    scope_segments = _compress_title_segments(
        [
            *[normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))][:1],
            *[normalize_text(str(item)) for item in scope_hints.get("industries", []) if normalize_text(str(item))][:1],
            *[normalize_text(str(item)) for item in scope_hints.get("clients", []) if normalize_text(str(item))][:1],
        ],
        limit=3,
    )
    fallback_segments = _compress_title_segments(
        [
            normalize_text(research_focus or ""),
            normalize_text(keyword),
        ],
        limit=2,
    )
    title_scope = "｜".join(scope_segments or fallback_segments) or normalize_text(keyword) or "研究主题"
    return localized_text(
        output_language,
        {
            "zh-CN": f"{title_scope}：待核验清单与补证路径",
            "zh-TW": f"{title_scope}：待核驗清單與補證路徑",
            "en": f"{title_scope}: Verification Backlog and Evidence Path",
        },
        f"{title_scope}：待核验清单与补证路径",
    )


def _build_guarded_stored_research_report(
    report: ResearchReportResponse,
    *,
    source_documents: list[SourceDocument],
    scope_hints: dict[str, object],
    output_language: str,
    source_diagnostics: ResearchSourceDiagnosticsOut,
    entity_graph: ResearchEntityGraphOut,
    guarded_rewrite_reasons: list[str] | None = None,
    supported_target_accounts: list[str] | None = None,
    unsupported_target_accounts: list[str] | None = None,
) -> ResearchReportResponse:
    theme_labels = _theme_labels_from_scope(scope_hints, keyword=report.keyword, research_focus=report.research_focus)
    sanitized_departments = _sanitize_report_field_rows("target_departments", report.target_departments)
    sanitized_budget_signals = _sanitize_report_field_rows("budget_signals", report.budget_signals)
    sanitized_tender_timeline = _sanitize_report_field_rows("tender_timeline", report.tender_timeline)
    theme_terms = _build_theme_terms(report.keyword, report.research_focus, scope_hints)
    supported_accounts = _dedupe_strings(
        [
            normalize_text(str(item))
            for item in (
                supported_target_accounts
                if supported_target_accounts is not None
                else source_diagnostics.supported_target_accounts
            )
            if normalize_text(str(item))
        ],
        4,
    )
    safe_account_candidates = _dedupe_strings(
        [
            _sanitize_entity_row("target_accounts", normalize_text(item))
            for item in [
                *(normalize_text(str(item)) for item in scope_hints.get("clients", []) if normalize_text(str(item))),
                *(normalize_text(item) for item in report.target_accounts if normalize_text(item)),
            ]
            if normalize_text(item)
        ],
        4,
    )
    if not supported_accounts:
        supported_accounts = [
            item
            for item in safe_account_candidates
            if any(
                _source_supports_target_account(
                    source,
                    item,
                    theme_terms=theme_terms,
                    scope_hints=scope_hints,
                )
                for source in source_documents
            )
        ]
    unsupported_accounts = _dedupe_strings(
        [
            normalize_text(str(item))
            for item in (
                unsupported_target_accounts
                if unsupported_target_accounts is not None
                else source_diagnostics.unsupported_target_accounts
            )
            if normalize_text(str(item)) and normalize_text(str(item)) not in supported_accounts
        ],
        4,
    )
    safe_accounts = supported_accounts[:2]
    guarded_source_diagnostics = _apply_guarded_rewrite_diagnostics(
        source_diagnostics,
        output_language=output_language,
        guarded_backlog=True,
        guarded_rewrite_reasons=guarded_rewrite_reasons or source_diagnostics.guarded_rewrite_reasons,
        supported_target_accounts=supported_accounts,
        unsupported_target_accounts=unsupported_accounts,
    )
    guarded_scope_hints = {
        **scope_hints,
        "clients": safe_accounts,
        "company_anchors": _dedupe_strings(safe_accounts, 4),
        "anchor_text": normalize_text(
            " / ".join(
                [
                    *[normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))][:1],
                    *[normalize_text(str(item)) for item in scope_hints.get("industries", []) if normalize_text(str(item))][:1],
                    *safe_accounts[:1],
                ]
            )
        ),
    }
    safe_departments = sanitized_departments[:3]
    safe_budgets = _summary_fact_rows(sanitized_budget_signals, limit=2)
    safe_timeline = _summary_fact_rows(sanitized_tender_timeline, limit=2)
    safe_key_signals = _dedupe_strings([*safe_accounts[:1], *safe_budgets[:1], *safe_timeline[:1]], 3)
    scope_anchor_segments = _compress_title_segments(
        [
            *_scope_anchor_text_segments(str(guarded_scope_hints.get("anchor_text", ""))),
            *[normalize_text(str(item)) for item in guarded_scope_hints.get("regions", []) if normalize_text(str(item))][:1],
            *[normalize_text(str(item)) for item in guarded_scope_hints.get("industries", []) if normalize_text(str(item))][:1],
            *[normalize_text(str(item)) for item in guarded_scope_hints.get("clients", []) if normalize_text(str(item))][:1],
            normalize_text(report.research_focus or ""),
            normalize_text(report.keyword),
        ],
        limit=4,
    )
    scope_anchor = " / ".join(scope_anchor_segments) or normalize_text(report.keyword)
    guarded_summary = localized_text(
        output_language,
        {
            "zh-CN": (
                f"当前公开来源不足以支持对 {scope_anchor} 形成具体账户、预算或竞对判断。"
                " 这一版仅保留为待核验清单，优先补官网、公告、采购和联系人线索后再进入正式推进。"
            ),
            "zh-TW": (
                f"目前公開來源不足以支撐對 {scope_anchor} 形成具體帳戶、預算或競對判斷。"
                " 這一版僅保留為待核驗清單，優先補官網、公告、採購與聯絡人線索後再進入正式推進。"
            ),
            "en": (
                f"Current public sources are not strong enough to support concrete buyer, budget, or competitor judgments for {scope_anchor}. "
                "Keep this version as a verification backlog and add official pages, notices, procurement records, and contact evidence before formal execution."
            ),
        },
        f"当前公开来源不足以支持对 {scope_anchor} 形成具体账户、预算或竞对判断。这一版仅保留为待核验清单，优先补官网、公告、采购和联系人线索后再进入正式推进。",
    )
    guarded_consulting_angle = localized_text(
        output_language,
        {
            "zh-CN": "先做范围收敛与补证，不做强销售判断，也不输出过度具体的推进承诺。",
            "zh-TW": "先做範圍收斂與補證，不做強銷售判斷，也不輸出過度具體的推進承諾。",
            "en": "Prioritize scope reduction and evidence recovery; do not force a strong sales judgment or overly specific execution claims yet.",
        },
        "先做范围收敛与补证，不做强销售判断，也不输出过度具体的推进承诺。",
    )
    guarded_result = ResearchReportResult(
        report_title=_build_guarded_rewrite_title(
            keyword=report.keyword,
            research_focus=report.research_focus,
            scope_hints=guarded_scope_hints,
            output_language=output_language,
        ),
        executive_summary=guarded_summary,
        consulting_angle=guarded_consulting_angle,
        industry_brief=[],
        key_signals=safe_key_signals,
        policy_and_leadership=[],
        commercial_opportunities=[],
        solution_design=[],
        sales_strategy=[],
        bidding_strategy=[],
        outreach_strategy=[],
        ecosystem_strategy=[],
        target_accounts=safe_accounts,
        target_departments=safe_departments,
        public_contact_channels=[],
        account_team_signals=safe_departments[:2],
        budget_signals=safe_budgets,
        project_distribution=[],
        strategic_directions=[],
        tender_timeline=safe_timeline,
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
        risks=[
            localized_text(
                output_language,
                {
                    "zh-CN": "当前版本证据门槛不足，若继续沿用会放大错误账户和动作建议。",
                    "zh-TW": "目前版本證據門檻不足，若繼續沿用會放大錯誤帳戶與動作建議。",
                    "en": "Evidence is below the required threshold; forcing this report forward would amplify wrong buyers and wrong next actions.",
                },
                "当前版本证据门槛不足，若继续沿用会放大错误账户和动作建议。",
            )
        ],
        next_actions=[
            localized_text(
                output_language,
                {
                    "zh-CN": "先补官网、公告、采购和联系人线索，再重新生成正式研报。",
                    "zh-TW": "先補官網、公告、採購與聯絡人線索，再重新生成正式研報。",
                    "en": "Add official pages, notices, procurement records, and contact evidence, then regenerate the formal report.",
                },
                "先补官网、公告、采购和联系人线索，再重新生成正式研报。",
            )
        ],
    )
    sections = _build_sections(guarded_result, output_language, source_documents)
    guarded_report = ResearchReportResponse(
        keyword=normalize_text(report.keyword),
        research_focus=normalize_text(report.research_focus or "") or None,
        output_language=output_language,
        research_mode=report.research_mode,
        report_title=guarded_result.report_title,
        executive_summary=guarded_result.executive_summary,
        consulting_angle=guarded_result.consulting_angle,
        sections=sections,
        target_accounts=guarded_result.target_accounts,
        top_target_accounts=[],
        pending_target_candidates=[],
        target_departments=guarded_result.target_departments,
        public_contact_channels=guarded_result.public_contact_channels,
        account_team_signals=guarded_result.account_team_signals,
        budget_signals=guarded_result.budget_signals,
        project_distribution=guarded_result.project_distribution,
        strategic_directions=guarded_result.strategic_directions,
        tender_timeline=guarded_result.tender_timeline,
        leadership_focus=guarded_result.leadership_focus,
        ecosystem_partners=guarded_result.ecosystem_partners,
        top_ecosystem_partners=[],
        pending_partner_candidates=[],
        competitor_profiles=guarded_result.competitor_profiles,
        top_competitors=[],
        pending_competitor_candidates=[],
        benchmark_cases=guarded_result.benchmark_cases,
        flagship_products=guarded_result.flagship_products,
        key_people=guarded_result.key_people,
        five_year_outlook=guarded_result.five_year_outlook,
        client_peer_moves=guarded_result.client_peer_moves,
        winner_peer_moves=guarded_result.winner_peer_moves,
        competition_analysis=guarded_result.competition_analysis,
        source_count=len(source_documents),
        evidence_density=_evidence_density_level(source_documents, guarded_result),
        source_quality=_source_quality_level(source_documents),
        query_plan=[normalize_text(item) for item in report.query_plan if normalize_text(item)],
        sources=_to_research_source_outputs(source_documents),
        source_diagnostics=guarded_source_diagnostics,
        entity_graph=entity_graph,
        generated_at=report.generated_at,
    )
    return _enrich_report_for_delivery(guarded_report)


def rewrite_stored_research_report(report: ResearchReportResponse) -> ResearchReportResponse:
    keyword = normalize_text(report.keyword)
    research_focus = normalize_text(report.research_focus or "") or None
    output_language = report.output_language
    source_documents = _report_sources_to_source_documents(report.sources)
    diagnostics = report.source_diagnostics if getattr(report, "source_diagnostics", None) else ResearchSourceDiagnosticsOut()
    base_scope_hints = _infer_input_scope_hints(keyword, research_focus)
    report = _canonicalize_stored_report_entities(
        report,
        scope_hints=base_scope_hints,
        source_documents=source_documents,
    )
    diagnostics = report.source_diagnostics if getattr(report, "source_diagnostics", None) else ResearchSourceDiagnosticsOut()
    stored_clients = _dedupe_strings(
        [
            _canonicalize_stored_entity_name(
                normalize_text(item),
                field_key="target_accounts",
                scope_hints=base_scope_hints,
                source_documents=source_documents,
            )
            for item in [
                *(normalize_text(item) for item in diagnostics.scope_clients if normalize_text(item)),
                *(normalize_text(item.name) for item in report.top_target_accounts if normalize_text(item.name)),
                *(normalize_text(item.name) for item in report.pending_target_candidates if normalize_text(item.name)),
                *(normalize_text(item) for item in report.target_accounts if normalize_text(item)),
            ]
            if normalize_text(item)
        ],
        4,
    )
    stored_scope_hints = {
        "regions": _dedupe_strings([normalize_text(item) for item in diagnostics.scope_regions if normalize_text(item)], 3),
        "industries": _dedupe_strings([normalize_text(item) for item in diagnostics.scope_industries if normalize_text(item)], 3),
        "clients": stored_clients,
        "company_anchors": _dedupe_strings(stored_clients, 4),
        "strategy_must_include_terms": [],
        "strategy_exclusion_terms": _dedupe_strings(
            [normalize_text(item) for item in diagnostics.strategy_exclusion_terms if normalize_text(item)],
            8,
        ),
        "strategy_query_expansions": [],
        "strategy_scope_summary": normalize_text(diagnostics.strategy_scope_summary),
        "anchor_text": normalize_text(" / ".join(stored_clients[:2])),
    }
    scope_hints = _merge_scope_hints(base_scope_hints, stored_scope_hints)
    if source_documents:
        scope_hints = _merge_scope_hints(
            scope_hints,
            _infer_scope_hints(keyword, research_focus, source_documents),
        )
    stored_regions = [normalize_text(str(item)) for item in stored_scope_hints.get("regions", []) or [] if normalize_text(str(item))]
    stored_industries = [normalize_text(str(item)) for item in stored_scope_hints.get("industries", []) or [] if normalize_text(str(item))]
    if stored_regions or stored_industries:
        scope_hints = {
            **scope_hints,
            "regions": _dedupe_strings(stored_regions or [normalize_text(str(item)) for item in scope_hints.get("regions", []) or [] if normalize_text(str(item))], 3),
            "industries": _prune_industry_hints(stored_industries or [normalize_text(str(item)) for item in scope_hints.get("industries", []) or [] if normalize_text(str(item))]),
        }
    sanitized_scope_clients = _dedupe_strings(
        [
            _sanitize_entity_row("target_accounts", normalize_text(str(item)))
            for item in scope_hints.get("clients", []) or []
            if normalize_text(str(item))
        ],
        4,
    )
    scope_hints = {
        **scope_hints,
        "clients": sanitized_scope_clients,
        "company_anchors": _dedupe_strings(
            [
                *(normalize_text(str(item)) for item in scope_hints.get("company_anchors", []) if normalize_text(str(item))),
                *sanitized_scope_clients,
            ],
            4,
        ),
        "anchor_text": normalize_text(
            " / ".join(
                [
                    *[normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))][:2],
                    *[normalize_text(str(item)) for item in scope_hints.get("industries", []) if normalize_text(str(item))][:2],
                    *sanitized_scope_clients[:2],
                ]
            )
        ),
    }

    entity_graph = _build_entity_graph(source_documents, scope_hints=scope_hints)
    topic_anchor_terms = diagnostics.topic_anchor_terms or _extract_topic_anchor_terms(keyword, research_focus)
    matched_theme_labels = _collect_matched_theme_labels(
        source_documents,
        scope_hints=scope_hints,
        topic_anchor_terms=topic_anchor_terms,
    )
    candidate_profile_companies = _clean_candidate_profile_company_names(
        [
            *diagnostics.candidate_profile_companies,
            *(normalize_text(item.name) for item in report.top_target_accounts if normalize_text(item.name)),
            *(normalize_text(item.name) for item in report.top_competitors if normalize_text(item.name)),
            *(normalize_text(item.name) for item in report.top_ecosystem_partners if normalize_text(item.name)),
            *(normalize_text(item) for item in scope_hints.get("clients", []) if normalize_text(str(item))),
        ]
    )
    source_diagnostics = _build_source_diagnostics(
        source_documents,
        enabled_source_labels=_dedupe_strings(
            [normalize_text(item) for item in diagnostics.enabled_source_labels if normalize_text(item)]
            or [normalize_text(source.source_label or "") for source in source_documents if normalize_text(source.source_label or "")],
            8,
        ),
        scope_hints=scope_hints,
        recency_window_years=int(diagnostics.recency_window_years or SOURCE_MAX_AGE_YEARS),
        filtered_old_source_count=int(diagnostics.filtered_old_source_count or 0),
        filtered_region_conflict_count=int(diagnostics.filtered_region_conflict_count or 0),
        retained_source_count=len(source_documents),
        strict_topic_source_count=len(source_documents),
        topic_anchor_terms=topic_anchor_terms,
        matched_theme_labels=matched_theme_labels,
        entity_graph=entity_graph,
        expansion_triggered=bool(diagnostics.expansion_triggered),
        corrective_triggered=bool(diagnostics.corrective_triggered),
        candidate_profile_companies=candidate_profile_companies,
        candidate_profile_hit_count=0,
        candidate_profile_official_hit_count=0,
        candidate_profile_source_labels=[],
    )
    _concrete_targets, supported_target_accounts, unsupported_target_accounts = _resolve_stored_report_target_support(
        report,
        source_documents=source_documents,
        scope_hints=scope_hints,
    )
    source_diagnostics = _apply_guarded_rewrite_diagnostics(
        source_diagnostics,
        output_language=output_language,
        guarded_backlog=False,
        guarded_rewrite_reasons=[],
        supported_target_accounts=supported_target_accounts,
        unsupported_target_accounts=unsupported_target_accounts,
    )
    rewrite_mode, rewrite_reasons, _rewrite_metrics = _assess_stored_report_rewrite_mode(
        report,
        source_documents=source_documents,
        scope_hints=scope_hints,
    )
    if rewrite_mode == "guarded":
        guarded_scope_hints = {
            **scope_hints,
            "strategy_scope_summary": normalize_text(" / ".join(rewrite_reasons)),
        }
        return _build_guarded_stored_research_report(
            report,
            source_documents=source_documents,
            scope_hints=guarded_scope_hints,
            output_language=output_language,
            source_diagnostics=source_diagnostics,
            entity_graph=entity_graph,
            guarded_rewrite_reasons=rewrite_reasons,
            supported_target_accounts=supported_target_accounts,
            unsupported_target_accounts=unsupported_target_accounts,
        )

    base_result = _stored_report_to_result(report)
    combined_intelligence = _report_intelligence_from_result(report, base_result)
    if source_documents:
        source_intelligence = _build_source_intelligence(
            source_documents,
            keyword=keyword,
            research_focus=research_focus,
            output_language=output_language,
            scope_hints=scope_hints,
        )
        for key, values in source_intelligence.items():
            combined_intelligence[key] = _sanitize_report_field_rows(
                key,
                [*(combined_intelligence.get(key, []) or []), *values],
            )

    parsed = _merge_result_with_intelligence(base_result, combined_intelligence)
    parsed = _apply_topic_specific_overrides(
        parsed,
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        scope_hints=scope_hints,
        intelligence=combined_intelligence,
    )
    parsed = _canonicalize_stored_result_entities(
        parsed,
        scope_hints=scope_hints,
        source_documents=source_documents,
    )

    theme_terms = _build_theme_terms(keyword, research_focus, scope_hints)
    top_target_accounts, pending_target_candidates = _rank_top_entities(
        source_documents,
        role="target",
        output_language=output_language,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        entity_graph=entity_graph,
        fallback_values=_filtered_rank_fallback_values(parsed.target_accounts, role="target", scope_hints=scope_hints),
        limit=3,
    )
    top_competitors, pending_competitor_candidates = _rank_top_entities(
        source_documents,
        role="competitor",
        output_language=output_language,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        entity_graph=entity_graph,
        fallback_values=_filtered_rank_fallback_values(
            [*parsed.competitor_profiles, *parsed.winner_peer_moves],
            role="competitor",
            scope_hints=scope_hints,
        ),
        limit=3,
    )
    top_ecosystem_partners, pending_partner_candidates = _rank_top_entities(
        source_documents,
        role="partner",
        output_language=output_language,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        entity_graph=entity_graph,
        fallback_values=_filtered_rank_fallback_values(
            parsed.ecosystem_partners,
            role="partner",
            scope_hints=scope_hints,
        ),
        limit=3,
    )

    merged_public_contact_channels = _dedupe_strings(
        [
            *_build_entity_specific_contact_rows(
                source_documents,
                entity_names=_dedupe_strings(
                    [
                        *(normalize_text(item.name) for item in top_target_accounts if normalize_text(item.name)),
                        *(normalize_text(item.name) for item in top_ecosystem_partners if normalize_text(item.name)),
                        *(normalize_text(item) for item in scope_hints.get("clients", []) if normalize_text(str(item))),
                    ],
                    6,
                ),
                output_language=output_language,
                limit=5,
            ),
            *parsed.public_contact_channels,
        ],
        5,
    )
    merged_account_team_signals = _dedupe_strings(
        [
            *_build_entity_specific_team_rows(
                source_documents,
                entity_names=_dedupe_strings(
                    [
                        *(normalize_text(item.name) for item in top_target_accounts if normalize_text(item.name)),
                        *(normalize_text(item.name) for item in pending_target_candidates if normalize_text(item.name)),
                        *(normalize_text(item.name) for item in top_ecosystem_partners if normalize_text(item.name)),
                        *(normalize_text(item.name) for item in pending_partner_candidates if normalize_text(item.name)),
                        *(normalize_text(item) for item in scope_hints.get("clients", []) if normalize_text(str(item))),
                    ],
                    6,
                ),
                scope_hints=scope_hints,
                output_language=output_language,
                limit=5,
            ),
            *parsed.account_team_signals,
        ],
        5,
    )

    sections = _build_sections(parsed, output_language, source_documents)
    rewritten_report = ResearchReportResponse(
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        research_mode=report.research_mode,
        report_title=parsed.report_title,
        executive_summary=parsed.executive_summary,
        consulting_angle=parsed.consulting_angle,
        sections=sections,
        target_accounts=parsed.target_accounts,
        top_target_accounts=top_target_accounts,
        pending_target_candidates=pending_target_candidates,
        target_departments=parsed.target_departments,
        public_contact_channels=_sanitize_report_field_rows("public_contact_channels", merged_public_contact_channels),
        account_team_signals=_sanitize_report_field_rows("account_team_signals", merged_account_team_signals),
        budget_signals=parsed.budget_signals,
        project_distribution=parsed.project_distribution,
        strategic_directions=parsed.strategic_directions,
        tender_timeline=parsed.tender_timeline,
        leadership_focus=parsed.leadership_focus,
        ecosystem_partners=parsed.ecosystem_partners,
        top_ecosystem_partners=top_ecosystem_partners,
        pending_partner_candidates=pending_partner_candidates,
        competitor_profiles=parsed.competitor_profiles,
        top_competitors=top_competitors,
        pending_competitor_candidates=pending_competitor_candidates,
        benchmark_cases=parsed.benchmark_cases,
        flagship_products=parsed.flagship_products,
        key_people=parsed.key_people,
        five_year_outlook=parsed.five_year_outlook,
        client_peer_moves=parsed.client_peer_moves,
        winner_peer_moves=parsed.winner_peer_moves,
        competition_analysis=parsed.competition_analysis,
        source_count=len(source_documents),
        evidence_density=_evidence_density_level(source_documents, parsed),
        source_quality=_source_quality_level(source_documents),
        query_plan=[normalize_text(item) for item in report.query_plan if normalize_text(item)],
        sources=_to_research_source_outputs(source_documents),
        source_diagnostics=source_diagnostics,
        entity_graph=entity_graph,
        generated_at=report.generated_at,
    )
    enriched_report = _enrich_report_for_delivery(rewritten_report)
    if (
        not normalize_text(enriched_report.report_title).endswith(("待核验清单与补证路径", "待核驗清單與補證路徑", "Verification Backlog and Evidence Path"))
        and _is_low_signal_execution_report(enriched_report)
    ):
        guarded_scope_hints = {
            **scope_hints,
            "strategy_scope_summary": normalize_text("post_rewrite_low_signal_guard"),
        }
        return _build_guarded_stored_research_report(
            report,
            source_documents=source_documents,
            scope_hints=guarded_scope_hints,
            output_language=output_language,
            source_diagnostics=source_diagnostics,
            entity_graph=entity_graph,
            guarded_rewrite_reasons=["post_rewrite_low_signal_guard"],
            supported_target_accounts=supported_target_accounts,
            unsupported_target_accounts=unsupported_target_accounts,
        )
    return enriched_report


def generate_research_report(
    payload: ResearchReportRequest,
    *,
    progress_callback: ResearchProgressCallback | None = None,
    snapshot_callback: ResearchSnapshotCallback | None = None,
) -> ResearchReportResponse:
    settings = get_settings()
    llm = get_llm_service()

    keyword = normalize_text(payload.keyword)
    report_research_focus = normalize_text(payload.research_focus or "") or None
    followup_context = _build_followup_context(payload)
    research_focus = _build_followup_planning_focus(
        report_research_focus,
        followup_context=followup_context,
    ) or report_research_focus
    output_language = payload.output_language
    research_mode = _resolve_research_mode(payload)
    runtime = _build_research_runtime(payload)
    source_settings = read_research_source_settings()
    preferred_wechat_accounts = (
        CURATED_WECHAT_CHANNELS
        if payload.include_wechat and source_settings.enable_curated_wechat_channels
        else ()
    )
    input_scope_hints = _infer_input_scope_hints(keyword, research_focus)
    input_scope_hints = _apply_strategy_scope_planning(
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        input_scope_hints=input_scope_hints,
    )

    _emit_research_progress(
        progress_callback,
        "planning",
        6,
        _build_progress_message("正在规划检索路径", keyword=keyword, research_focus=research_focus, mode=research_mode),
    )
    query_plan = _build_query_plan(
        keyword,
        research_focus,
        payload.include_wechat,
        scope_hints=input_scope_hints,
        preferred_wechat_accounts=preferred_wechat_accounts,
        limit=int(runtime["query_limit"]),
    )
    _emit_research_progress(
        progress_callback,
        "adapters",
        14,
        _build_progress_message("正在汇总定向信息源", keyword=keyword, research_focus=research_focus, mode=research_mode),
    )
    adapter_settings, adapter_hits = collect_enabled_source_hits(
        keyword,
        research_focus,
        timeout_seconds=int(runtime["search_timeout_seconds"]),
        per_source_limit=int(runtime["adapter_per_source_limit"]),
    )
    adapter_query_plan = [
        f"source:{label}"
        for label in adapter_settings.enabled_labels()
    ]

    search_hits: list[SearchHit] = []
    effective_query_plan = query_plan[: max(1, int(runtime["query_limit"]))]
    enough_hit_threshold = int(runtime["enough_hit_threshold"])
    search_hits.extend(adapter_hits)
    _emit_research_progress(
        progress_callback,
        "search",
        26,
        _build_progress_message("正在检索公开网页与招采来源", keyword=keyword, research_focus=research_focus, mode=research_mode),
    )
    for query in effective_query_plan:
        try:
            results = _search_public_web(
                query,
                timeout_seconds=int(runtime["search_timeout_seconds"]),
                limit=int(runtime["search_result_limit"]),
            )
        except Exception:
            results = []
        search_hits.extend(results)
        if len(_dedupe_hits(search_hits)) >= enough_hit_threshold:
            break

    ranked_hits = [
        hit
        for hit in _hybrid_rank_hits(
            search_hits,
            keyword=keyword,
            research_focus=research_focus,
            scope_hints=input_scope_hints,
        )
    ]
    selected_hits = _select_hits_with_source_balance(
        ranked_hits,
        limit=min(int(runtime["effective_max_sources"]), settings.research_max_sources),
    )

    sources: list[SourceDocument] = []
    _emit_research_progress(
        progress_callback,
        "extracting",
        42,
        _build_progress_message("正在抽取正文与证据片段", keyword=keyword, research_focus=research_focus, mode=research_mode),
    )
    for hit in selected_hits:
        sources.append(
            _extract_source_document(
                hit,
                timeout_seconds=int(runtime["url_timeout_seconds"]),
                excerpt_chars=settings.research_source_excerpt_chars,
            )
        )
    recent_filter_input_count = len(sources)
    sources = _filter_recent_sources(sources)
    filtered_old_source_count = max(recent_filter_input_count - len(sources), 0)
    filtered_region_conflict_signatures: set[str] = set()

    _emit_research_progress(
        progress_callback,
        "scoping",
        56,
        _build_progress_message("正在收敛区域、行业与客户范围", keyword=keyword, research_focus=research_focus, mode=research_mode),
    )
    scope_hints = _merge_scope_hints(input_scope_hints, _infer_scope_hints(keyword, research_focus, sources))
    theme_terms = _build_theme_terms(keyword, research_focus, scope_hints)
    topic_anchor_terms = _extract_topic_anchor_terms(keyword, research_focus)
    company_anchor_terms = _resolved_company_anchor_terms(keyword, research_focus, scope_hints)
    expansion_triggered = False
    corrective_triggered = False
    candidate_profile_companies: list[str] = []
    candidate_profile_hit_count = 0
    candidate_profile_official_hit_count = 0
    candidate_profile_source_labels: list[str] = []
    candidate_profile_sources: list[SourceDocument] = []
    filtered_region_conflict_signatures.update(
        _region_conflict_signature(source)
        for source in sources
        if _source_has_region_conflict(source, scope_hints=scope_hints)
    )
    sources = _refine_sources_for_report(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
        company_anchor_terms=company_anchor_terms,
        theme_terms=theme_terms,
    )
    strict_topic_source_count = len(sources)
    theme_seed_companies = _collect_theme_seed_companies(
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
    )
    company_contact_queries = _build_company_contact_query_plan(
        [
            *company_anchor_terms[:3],
            *scope_hints.get("company_anchors", [])[:3],
            *scope_hints.get("clients", [])[:2],
            *theme_seed_companies[:4],
        ],
        keyword=keyword,
        research_focus=research_focus,
        limit=4 if research_mode == "fast" else 6,
    )
    company_profile_queries = _build_company_profile_query_plan(
        [
            *company_anchor_terms[:3],
            *scope_hints.get("company_anchors", [])[:3],
            *scope_hints.get("clients", [])[:2],
            *theme_seed_companies[:4],
        ],
        keyword=keyword,
        research_focus=research_focus,
        limit=4 if research_mode == "fast" else 6,
    )
    company_enrichment_queries = _dedupe_strings(
        [*company_profile_queries, *company_contact_queries],
        6 if research_mode == "fast" else 10,
    )
    if company_enrichment_queries:
        _emit_research_progress(
            progress_callback,
            "company_contacts",
            61,
            _build_progress_message("正在补充官网与公开联系方式", keyword=keyword, research_focus=research_focus, mode=research_mode),
        )
        company_contact_hits: list[SearchHit] = []
        seed_contact_hits = _build_company_seed_hits(
            [
                *company_anchor_terms[:3],
                *scope_hints.get("company_anchors", [])[:3],
                *scope_hints.get("clients", [])[:2],
                *theme_seed_companies[:4],
            ],
            keyword=keyword,
        )
        company_contact_hits.extend(seed_contact_hits)
        for query in company_enrichment_queries:
            try:
                results = _search_public_web(
                    query,
                    timeout_seconds=max(8, int(runtime["search_timeout_seconds"]) - 1),
                    limit=max(3, int(runtime["search_result_limit"]) - 2),
                )
            except Exception:
                results = []
            company_contact_hits.extend(results)
        ranked_contact_hits = [
            hit
            for hit in _hybrid_rank_hits(
                company_contact_hits,
                keyword=keyword,
                research_focus=research_focus,
                scope_hints=scope_hints,
            )
        ]
        selected_contact_hits = _select_hits_with_source_balance(
            ranked_contact_hits,
            limit=3 if research_mode == "fast" else 5,
        )
        if not selected_contact_hits and seed_contact_hits:
            selected_contact_hits = _dedupe_hits(seed_contact_hits)[:2]
        elif seed_contact_hits:
            selected_urls = {normalize_text(hit.url) for hit in selected_contact_hits if normalize_text(hit.url)}
            official_seed_hits = [
                hit
                for hit in _dedupe_hits(seed_contact_hits)
                if normalize_text(hit.url) and normalize_text(hit.url) not in selected_urls
            ]
            if official_seed_hits and not any(
                _classify_source_tier(
                    source_type=hit.source_hint or _classify_source_type(hit.url),
                    domain=extract_domain(hit.url),
                    source_label=_derive_source_label(
                        source_type=hit.source_hint or _classify_source_type(hit.url),
                        domain=extract_domain(hit.url),
                        fallback=getattr(hit, "source_label", None),
                    ),
                )
                == "official"
                for hit in selected_contact_hits
            ):
                selected_contact_hits = [official_seed_hits[0], *selected_contact_hits]
                selected_contact_hits = _dedupe_hits(selected_contact_hits)[: (3 if research_mode == "fast" else 5)]
        if selected_contact_hits:
            contact_sources = [
                source
                for source in (
                    _extract_source_document_best_effort(
                        hit,
                        timeout_seconds=int(runtime["url_timeout_seconds"]),
                        excerpt_chars=settings.research_source_excerpt_chars,
                    )
                    for hit in selected_contact_hits
                )
                if source is not None
            ]
            if not contact_sources and seed_contact_hits:
                contact_sources = [
                    source
                    for source in (
                        _extract_source_document_best_effort(
                            hit,
                            timeout_seconds=int(runtime["url_timeout_seconds"]),
                            excerpt_chars=settings.research_source_excerpt_chars,
                        )
                        for hit in _dedupe_hits(seed_contact_hits)[:2]
                    )
                    if source is not None
                ]
            if contact_sources:
                sources = _dedupe_sources([*sources, *contact_sources])
                filtered_region_conflict_signatures.update(
                    _region_conflict_signature(source)
                    for source in sources
                    if _source_has_region_conflict(source, scope_hints=scope_hints)
                )
                refined_sources = _refine_sources_for_report(
                    sources,
                    keyword=keyword,
                    research_focus=research_focus,
                    scope_hints=scope_hints,
                    company_anchor_terms=company_anchor_terms,
                    theme_terms=theme_terms,
                )
                if refined_sources:
                    sources = refined_sources
                elif contact_sources:
                    sources = _dedupe_sources(contact_sources)
    scope_hints = _merge_scope_hints(input_scope_hints, _infer_scope_hints(keyword, research_focus, sources))
    theme_terms = _build_theme_terms(keyword, research_focus, scope_hints)
    source_intelligence = _build_source_intelligence(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        scope_hints=scope_hints,
    )
    concrete_dimension_count = sum(
        1
        for key in (
            "target_accounts",
            "account_team_signals",
            "budget_signals",
            "ecosystem_partners",
            "competitor_profiles",
            "client_peer_moves",
            "winner_peer_moves",
            "leadership_focus",
        )
        if len(_concrete_rows(source_intelligence.get(key, []))) >= 3
    )
    company_convergence_weak = _company_convergence_is_weak(
        scope_hints=scope_hints,
        target_rows=source_intelligence.get("target_accounts", []),
        competitor_rows=source_intelligence.get("competitor_profiles", []),
    )
    if (
        bool(runtime["enable_expansion"])
        and (
            len(sources) < int(runtime["expansion_min_sources"])
            or concrete_dimension_count < int(runtime["expansion_min_dimensions"])
            or company_convergence_weak
            or _official_coverage_is_weak(
                sources,
                min_ratio=0.35 if bool(scope_hints.get("prefer_company_entities")) else (0.25 if research_mode == "fast" else 0.35),
                min_count=2 if bool(scope_hints.get("prefer_company_entities")) else (1 if research_mode == "fast" else 2),
            )
        )
    ):
        expansion_triggered = True
        _emit_research_progress(
            progress_callback,
            "expanding",
            66,
            _build_progress_message("证据不足，正在扩大搜索范围", keyword=keyword, research_focus=research_focus, mode=research_mode),
        )
        expanded_query_plan = _build_expanded_query_plan(
            keyword,
            research_focus,
            scope_hints=scope_hints,
            include_wechat=payload.include_wechat,
            preferred_wechat_accounts=preferred_wechat_accounts,
            limit=int(runtime["expanded_query_limit"]),
        )
        if expanded_query_plan:
            expanded_search_hits: list[SearchHit] = []
            expanded_seed = " ".join(
                item
                for item in [
                    keyword,
                    *(scope_hints.get("regions", []) or [])[:1],
                    *(scope_hints.get("industries", []) or [])[:1],
                    *(scope_hints.get("clients", []) or [])[:1],
                ]
                if normalize_text(str(item))
            )
            _, expanded_adapter_hits = collect_enabled_source_hits(
                expanded_seed or keyword,
                research_focus or normalize_text(str(scope_hints.get("anchor_text", ""))) or None,
                timeout_seconds=max(10, int(runtime["search_timeout_seconds"]) - 1),
                per_source_limit=int(runtime["expanded_adapter_per_source_limit"]),
            )
            expanded_search_hits.extend(expanded_adapter_hits)
            for query in expanded_query_plan:
                try:
                    results = _search_public_web(
                        query,
                        timeout_seconds=int(runtime["search_timeout_seconds"]),
                        limit=max(3, int(runtime["search_result_limit"]) - 2),
                    )
                except Exception:
                    results = []
                expanded_search_hits.extend(results)
            combined_ranked_hits = [
                hit
                for hit in _hybrid_rank_hits(
                    search_hits + expanded_search_hits,
                    keyword=keyword,
                    research_focus=research_focus,
                    scope_hints=scope_hints,
                )
            ]
            selected_hits = _select_hits_with_source_balance(
                combined_ranked_hits,
                limit=int(runtime["expanded_selected_limit"]),
            )
            expanded_sources = [
                source
                for source in (
                    _extract_source_document_best_effort(
                        hit,
                        timeout_seconds=int(runtime["url_timeout_seconds"]),
                        excerpt_chars=settings.research_source_excerpt_chars,
                    )
                    for hit in selected_hits
                )
                if source is not None
            ]
            expanded_recent_input_count = len(expanded_sources)
            expanded_sources = _filter_recent_sources(expanded_sources)
            filtered_old_source_count += max(expanded_recent_input_count - len(expanded_sources), 0)
            effective_query_plan = _dedupe_strings(
                effective_query_plan + expanded_query_plan,
                max(int(runtime["query_limit"]), int(runtime["expanded_query_limit"])) + 4,
            )
            sources = _dedupe_sources([*sources, *expanded_sources])
            filtered_region_conflict_signatures.update(
                _region_conflict_signature(source)
                for source in sources
                if _source_has_region_conflict(source, scope_hints=scope_hints)
            )
            sources = _refine_sources_for_report(
                sources,
                keyword=keyword,
                research_focus=research_focus,
                scope_hints=scope_hints,
                company_anchor_terms=company_anchor_terms,
                theme_terms=theme_terms,
            )
            scope_hints = _merge_scope_hints(input_scope_hints, _infer_scope_hints(keyword, research_focus, sources))
            theme_terms = _build_theme_terms(keyword, research_focus, scope_hints)
            company_anchor_terms = _resolved_company_anchor_terms(keyword, research_focus, scope_hints)
            sources = _refine_sources_for_report(
                sources,
                keyword=keyword,
                research_focus=research_focus,
                scope_hints=scope_hints,
                company_anchor_terms=company_anchor_terms,
                theme_terms=theme_terms,
            )
            strict_topic_source_count = len(sources)
            scope_hints = _merge_scope_hints(input_scope_hints, _infer_scope_hints(keyword, research_focus, sources))
            theme_terms = _build_theme_terms(keyword, research_focus, scope_hints)
            company_anchor_terms = _resolved_company_anchor_terms(keyword, research_focus, scope_hints)
            source_intelligence = _build_source_intelligence(
                sources,
                keyword=keyword,
                research_focus=research_focus,
                output_language=output_language,
                scope_hints=scope_hints,
            )
    company_convergence_weak = _company_convergence_is_weak(
        scope_hints=scope_hints,
        target_rows=source_intelligence.get("target_accounts", []),
        competitor_rows=source_intelligence.get("competitor_profiles", []),
    )
    provisional_unique_domain_count = len({source.domain for source in sources if normalize_text(source.domain or "")})
    provisional_official_ratio = (
        sum(1 for source in sources if source.source_tier == "official") / len(sources)
        if sources
        else 0.0
    )
    provisional_retrieval_quality = _retrieval_quality_band(
        strict_match_ratio=(strict_topic_source_count / len(sources)) if sources else 0.0,
        official_source_ratio=provisional_official_ratio,
        unique_domain_count=provisional_unique_domain_count,
        normalized_entity_count=0,
    )
    if (
        len(sources) == 0
        or strict_topic_source_count == 0
        or company_convergence_weak
        or provisional_retrieval_quality == "low"
    ):
        corrective_triggered = True
        _emit_research_progress(
            progress_callback,
            "corrective",
            74,
            _build_progress_message("证据仍偏弱，正在执行纠错检索", keyword=keyword, research_focus=research_focus, mode=research_mode),
        )
        seed_companies = theme_seed_companies
        corrective_query_plan = _build_corrective_query_plan(
            keyword=keyword,
            research_focus=research_focus,
            scope_hints=scope_hints,
            include_wechat=payload.include_wechat,
            preferred_wechat_accounts=preferred_wechat_accounts,
            limit=max(4, min(int(runtime["expanded_query_limit"]) + 2, 10)),
        )
        corrective_hits: list[SearchHit] = _build_company_seed_hits(seed_companies, keyword=keyword)
        for query in corrective_query_plan:
            try:
                results = _search_public_web(
                    query,
                    timeout_seconds=max(10, int(runtime["search_timeout_seconds"])),
                    limit=max(4, int(runtime["search_result_limit"])),
                )
            except Exception:
                results = []
            corrective_hits.extend(results)
        ranked_corrective_hits = [
            hit
            for hit in _hybrid_rank_hits(
                corrective_hits,
                keyword=keyword,
                research_focus=research_focus,
                scope_hints=scope_hints,
            )
        ]
        selected_corrective_hits = _select_hits_with_source_balance(
            ranked_corrective_hits,
            limit=max(4, min(int(runtime["expanded_selected_limit"]), settings.research_max_sources)),
        )
        if not selected_corrective_hits and corrective_hits:
            selected_corrective_hits = _dedupe_hits(corrective_hits)[:3]
        corrective_sources = [
            source
            for source in (
                _extract_source_document_best_effort(
                    hit,
                    timeout_seconds=int(runtime["url_timeout_seconds"]),
                    excerpt_chars=settings.research_source_excerpt_chars,
                )
                for hit in selected_corrective_hits
            )
            if source is not None
        ]
        corrective_recent_input_count = len(corrective_sources)
        corrective_sources = _filter_recent_sources(corrective_sources)
        filtered_old_source_count += max(corrective_recent_input_count - len(corrective_sources), 0)
        if corrective_sources:
            effective_query_plan = _dedupe_strings(
                effective_query_plan + corrective_query_plan,
                max(int(runtime["query_limit"]), int(runtime["expanded_query_limit"])) + 8,
            )
            sources = _dedupe_sources([*sources, *corrective_sources])
            filtered_region_conflict_signatures.update(
                _region_conflict_signature(source)
                for source in sources
                if _source_has_region_conflict(source, scope_hints=scope_hints)
            )
            sources = _refine_sources_for_report(
                sources,
                keyword=keyword,
                research_focus=research_focus,
                scope_hints=scope_hints,
                company_anchor_terms=company_anchor_terms,
                theme_terms=theme_terms,
            )
            scope_hints = _merge_scope_hints(input_scope_hints, _infer_scope_hints(keyword, research_focus, sources))
            theme_terms = _build_theme_terms(keyword, research_focus, scope_hints)
            company_anchor_terms = _resolved_company_anchor_terms(keyword, research_focus, scope_hints)
            sources = _refine_sources_for_report(
                sources,
                keyword=keyword,
                research_focus=research_focus,
                scope_hints=scope_hints,
                company_anchor_terms=company_anchor_terms,
                theme_terms=theme_terms,
            )
            strict_topic_source_count = len(sources)
            source_intelligence = _build_source_intelligence(
                sources,
                keyword=keyword,
                research_focus=research_focus,
                output_language=output_language,
                scope_hints=scope_hints,
            )
    entity_graph = _build_entity_graph(
        sources,
        scope_hints=scope_hints,
    )
    matched_theme_labels = _collect_matched_theme_labels(
        sources,
        scope_hints=scope_hints,
        topic_anchor_terms=topic_anchor_terms,
    )
    source_diagnostics = _build_source_diagnostics(
        sources,
        enabled_source_labels=adapter_settings.enabled_labels(),
        scope_hints=scope_hints,
        recency_window_years=SOURCE_MAX_AGE_YEARS,
        filtered_old_source_count=filtered_old_source_count,
        filtered_region_conflict_count=len(filtered_region_conflict_signatures),
        retained_source_count=len(sources),
        strict_topic_source_count=strict_topic_source_count,
        topic_anchor_terms=topic_anchor_terms,
        matched_theme_labels=matched_theme_labels,
        entity_graph=entity_graph,
        expansion_triggered=expansion_triggered,
        corrective_triggered=corrective_triggered,
        candidate_profile_companies=candidate_profile_companies,
        candidate_profile_hit_count=candidate_profile_hit_count,
        candidate_profile_official_hit_count=candidate_profile_official_hit_count,
        candidate_profile_source_labels=candidate_profile_source_labels,
    )
    outline_result = _build_partial_report_result(
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        research_mode=research_mode,
        source_intelligence=source_intelligence,
        scope_hints=scope_hints,
        llm=llm,
        llm_timeout_seconds=int(runtime["llm_timeout_seconds"]),
    )
    _emit_research_progress(
        progress_callback,
        "synthesizing",
        82,
        _build_progress_message("正在综合多源证据生成研报", keyword=keyword, research_focus=research_focus, mode=research_mode),
    )
    _emit_research_snapshot(
        snapshot_callback,
        _build_partial_report_response(
            keyword=keyword,
            research_focus=research_focus,
            output_language=output_language,
            research_mode=research_mode,
            parsed=outline_result,
            query_plan=effective_query_plan + adapter_query_plan,
            sources=sources,
            source_diagnostics=source_diagnostics,
            entity_graph=entity_graph,
        ),
    )
    source_digest = _render_source_digest(sources)
    source_summary = json.dumps(
        [
            {
                "title": source.title,
                "url": source.url,
                "domain": source.domain,
                "source_type": source.source_type,
                "source_label": source.source_label,
                "source_tier": source.source_tier,
                "content_status": source.content_status,
            }
            for source in sources
        ],
        ensure_ascii=False,
    )

    raw = llm.run_prompt(
        "research_report.txt",
        {
            "keyword": keyword,
            "research_focus": report_research_focus or research_focus or "",
            "output_language": output_language,
            "research_mode": research_mode,
            "query_plan": " | ".join(effective_query_plan),
            "__timeout_seconds": str(int(runtime["llm_timeout_seconds"])),
            "source_count": str(len(sources)),
            "source_summary": source_summary,
            "source_digest": source_digest,
            "followup_context": _render_followup_prompt_context(followup_context),
            "followup_report_title": followup_context.followup_report_title,
            "followup_report_summary": followup_context.followup_report_summary,
            "supplemental_context": followup_context.supplemental_context,
            "supplemental_evidence": followup_context.supplemental_evidence,
            "supplemental_requirements": followup_context.supplemental_requirements,
            "outline_hint": json.dumps(
                {
                    "report_title": outline_result.report_title,
                    "executive_summary": outline_result.executive_summary,
                    "consulting_angle": outline_result.consulting_angle,
                },
                ensure_ascii=False,
            ),
            "scope_hints": json.dumps(scope_hints, ensure_ascii=False),
            "source_intelligence": json.dumps(source_intelligence, ensure_ascii=False),
            "industry_methodology_context": _render_industry_methodology_context(scope_hints),
        },
    )
    parsed = _merge_result_with_intelligence(
        parse_research_report_response(raw, output_language=output_language),
        source_intelligence,
    )
    parsed = _apply_topic_specific_overrides(
        parsed,
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        scope_hints=scope_hints,
        intelligence=source_intelligence,
    )
    parsed = _apply_strategy_llm_refinement(
        parsed,
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        scope_hints=scope_hints,
        intelligence=source_intelligence,
    )
    _emit_research_progress(
        progress_callback,
        "ranking",
        92,
        _build_progress_message("正在生成甲方、竞品与伙伴排序", keyword=keyword, research_focus=research_focus, mode=research_mode),
    )
    top_target_accounts, pending_target_candidates = _rank_top_entities(
        sources,
        role="target",
        output_language=output_language,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        entity_graph=entity_graph,
        fallback_values=_filtered_rank_fallback_values(parsed.target_accounts, role="target", scope_hints=scope_hints),
        limit=3,
    )
    top_competitors, pending_competitor_candidates = _rank_top_entities(
        sources,
        role="competitor",
        output_language=output_language,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        entity_graph=entity_graph,
        fallback_values=_filtered_rank_fallback_values(
            [*parsed.competitor_profiles, *parsed.winner_peer_moves],
            role="competitor",
            scope_hints=scope_hints,
        ),
        limit=3,
    )
    top_ecosystem_partners, pending_partner_candidates = _rank_top_entities(
        sources,
        role="partner",
        output_language=output_language,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        entity_graph=entity_graph,
        fallback_values=_filtered_rank_fallback_values(
            parsed.ecosystem_partners,
            role="partner",
            scope_hints=scope_hints,
        ),
        limit=3,
    )
    candidate_public_profile_names = _dedupe_strings(
        [
            *(normalize_text(item.name) for item in top_target_accounts if normalize_text(item.name)),
            *(normalize_text(item.name) for item in pending_target_candidates if normalize_text(item.name)),
            *(normalize_text(item.name) for item in top_ecosystem_partners if normalize_text(item.name)),
            *(normalize_text(item.name) for item in pending_partner_candidates if normalize_text(item.name)),
            *(normalize_text(item.name) for item in top_competitors if normalize_text(item.name)),
            *(normalize_text(item.name) for item in pending_competitor_candidates if normalize_text(item.name)),
        ],
        6,
    )
    if candidate_public_profile_names:
        candidate_profile_companies = _dedupe_strings(candidate_public_profile_names, 6)
        public_profile_queries = _dedupe_strings(
            [
                *_build_company_profile_query_plan(
                    candidate_public_profile_names,
                    keyword=keyword,
                    research_focus=research_focus,
                    limit=4 if research_mode == "fast" else 6,
                ),
                *_build_company_contact_query_plan(
                    candidate_public_profile_names,
                    keyword=keyword,
                    research_focus=research_focus,
                    limit=4 if research_mode == "fast" else 6,
                ),
                *_build_company_team_query_plan(
                    candidate_public_profile_names,
                    keyword=keyword,
                    research_focus=research_focus,
                    scope_hints=scope_hints,
                    limit=4 if research_mode == "fast" else 6,
                ),
            ],
            8 if research_mode == "fast" else 12,
        )
        if public_profile_queries:
            _emit_research_progress(
                progress_callback,
                "candidate_profiles",
                94,
                _build_progress_message("正在补充候选公司官网、联系页与团队公开线索", keyword=keyword, research_focus=research_focus, mode=research_mode),
            )
            public_profile_hits: list[SearchHit] = []
            seed_profile_hits = _build_company_seed_hits(candidate_public_profile_names, keyword=keyword)
            public_profile_hits.extend(seed_profile_hits)
            for query in public_profile_queries:
                try:
                    results = _search_public_web(
                        query,
                        timeout_seconds=max(8, int(runtime["search_timeout_seconds"]) - 1),
                        limit=max(3, int(runtime["search_result_limit"]) - 2),
                    )
                except Exception:
                    results = []
                public_profile_hits.extend(results)
            ranked_profile_hits = [
                hit
                for hit in _hybrid_rank_hits(
                    public_profile_hits,
                    keyword=keyword,
                    research_focus=research_focus,
                    scope_hints=scope_hints,
                )
            ]
            selected_profile_hits = _select_hits_with_source_balance(
                ranked_profile_hits,
                limit=3 if research_mode == "fast" else 5,
            )
            if not selected_profile_hits and seed_profile_hits:
                selected_profile_hits = _dedupe_hits(seed_profile_hits)[:2]
            if selected_profile_hits:
                profile_sources = [
                    source
                    for source in (
                        _extract_source_document_best_effort(
                            hit,
                            timeout_seconds=int(runtime["url_timeout_seconds"]),
                            excerpt_chars=settings.research_source_excerpt_chars,
                        )
                        for hit in selected_profile_hits
                    )
                    if source is not None
                ]
                if profile_sources:
                    candidate_profile_sources = list(profile_sources)
                    candidate_profile_hit_count = len(profile_sources)
                    candidate_profile_official_hit_count = sum(
                        1 for source in profile_sources if source.source_tier == "official"
                    )
                    candidate_profile_source_labels = _dedupe_strings(
                        [
                            normalize_text(source.source_label or source.title or source.domain or "")
                            for source in profile_sources
                        ],
                        8,
                    )
                    sources = _dedupe_sources([*sources, *profile_sources])
                    filtered_region_conflict_signatures.update(
                        _region_conflict_signature(source)
                        for source in sources
                        if _source_has_region_conflict(source, scope_hints=scope_hints)
                    )
                    refined_sources = _refine_sources_for_report(
                        sources,
                        keyword=keyword,
                        research_focus=research_focus,
                        scope_hints=scope_hints,
                        company_anchor_terms=company_anchor_terms,
                        theme_terms=theme_terms,
                    )
                    if refined_sources:
                        sources = refined_sources
                    corrective_triggered = True
                    scope_hints = _merge_scope_hints(input_scope_hints, _infer_scope_hints(keyword, research_focus, sources))
                    theme_terms = _build_theme_terms(keyword, research_focus, scope_hints)
                    company_anchor_terms = _resolved_company_anchor_terms(keyword, research_focus, scope_hints)
                    entity_graph = _build_entity_graph(
                        sources,
                        scope_hints=scope_hints,
                    )
                    top_target_accounts, pending_target_candidates = _rank_top_entities(
                        sources,
                        role="target",
                        output_language=output_language,
                        scope_hints=scope_hints,
                        theme_terms=theme_terms,
                        entity_graph=entity_graph,
                        fallback_values=_filtered_rank_fallback_values(
                            parsed.target_accounts,
                            role="target",
                            scope_hints=scope_hints,
                        ),
                        limit=3,
                    )
                    top_competitors, pending_competitor_candidates = _rank_top_entities(
                        sources,
                        role="competitor",
                        output_language=output_language,
                        scope_hints=scope_hints,
                        theme_terms=theme_terms,
                        entity_graph=entity_graph,
                        fallback_values=_filtered_rank_fallback_values(
                            [*parsed.competitor_profiles, *parsed.winner_peer_moves],
                            role="competitor",
                            scope_hints=scope_hints,
                        ),
                        limit=3,
                    )
                    top_ecosystem_partners, pending_partner_candidates = _rank_top_entities(
                        sources,
                        role="partner",
                        output_language=output_language,
                        scope_hints=scope_hints,
                        theme_terms=theme_terms,
                        entity_graph=entity_graph,
                        fallback_values=_filtered_rank_fallback_values(
                            parsed.ecosystem_partners,
                            role="partner",
                            scope_hints=scope_hints,
                        ),
                        limit=3,
                    )
    if candidate_profile_sources:
        candidate_profile_support = _build_candidate_profile_support(
            candidate_profile_sources,
            candidate_profile_companies,
        )
        top_target_accounts, pending_target_candidates = _promote_pending_entities_with_candidate_profiles(
            top_target_accounts,
            pending_target_candidates,
            candidate_profile_support=candidate_profile_support,
            limit=3,
        )
        top_competitors, pending_competitor_candidates = _promote_pending_entities_with_candidate_profiles(
            top_competitors,
            pending_competitor_candidates,
            candidate_profile_support=candidate_profile_support,
            limit=3,
        )
        top_ecosystem_partners, pending_partner_candidates = _promote_pending_entities_with_candidate_profiles(
            top_ecosystem_partners,
            pending_partner_candidates,
            candidate_profile_support=candidate_profile_support,
            limit=3,
        )
    entity_specific_contact_rows = _build_entity_specific_contact_rows(
        sources,
        entity_names=_dedupe_strings(
            [
                *(normalize_text(item.name) for item in top_target_accounts if normalize_text(item.name)),
                *(normalize_text(item.name) for item in top_ecosystem_partners if normalize_text(item.name)),
                *(normalize_text(str(item)) for item in scope_hints.get("clients", []) if normalize_text(str(item))),
            ],
            6,
        ),
        output_language=output_language,
        limit=5,
    )
    entity_specific_team_rows = _build_entity_specific_team_rows(
        sources,
        entity_names=_dedupe_strings(
            [
                *(normalize_text(item.name) for item in top_target_accounts if normalize_text(item.name)),
                *(normalize_text(item.name) for item in pending_target_candidates if normalize_text(item.name)),
                *(normalize_text(item.name) for item in top_ecosystem_partners if normalize_text(item.name)),
                *(normalize_text(item.name) for item in pending_partner_candidates if normalize_text(item.name)),
                *(normalize_text(str(item)) for item in scope_hints.get("clients", []) if normalize_text(str(item))),
            ],
            6,
        ),
        scope_hints=scope_hints,
        output_language=output_language,
        limit=5,
    )
    merged_public_contact_channels = _dedupe_strings(
        [
            *entity_specific_contact_rows,
            *parsed.public_contact_channels,
        ],
        5,
    )
    merged_account_team_signals = _dedupe_strings(
        [
            *entity_specific_team_rows,
            *parsed.account_team_signals,
        ],
        5,
    )
    matched_theme_labels = _collect_matched_theme_labels(
        sources,
        scope_hints=scope_hints,
        topic_anchor_terms=topic_anchor_terms,
    )
    source_diagnostics = _build_source_diagnostics(
        sources,
        enabled_source_labels=adapter_settings.enabled_labels(),
        scope_hints=scope_hints,
        recency_window_years=SOURCE_MAX_AGE_YEARS,
        filtered_old_source_count=filtered_old_source_count,
        filtered_region_conflict_count=len(filtered_region_conflict_signatures),
        retained_source_count=len(sources),
        strict_topic_source_count=strict_topic_source_count,
        topic_anchor_terms=topic_anchor_terms,
        matched_theme_labels=matched_theme_labels,
        entity_graph=entity_graph,
        expansion_triggered=expansion_triggered,
        corrective_triggered=corrective_triggered,
        candidate_profile_companies=candidate_profile_companies,
        candidate_profile_hit_count=candidate_profile_hit_count,
        candidate_profile_official_hit_count=candidate_profile_official_hit_count,
        candidate_profile_source_labels=candidate_profile_source_labels,
    )
    evidence_density = _evidence_density_level(sources, parsed)
    source_quality = _source_quality_level(sources)
    _emit_research_progress(
        progress_callback,
        "packaging",
        97,
        _build_progress_message("正在整理结构化结论与来源", keyword=keyword, research_focus=research_focus, mode=research_mode),
    )
    sections = _build_sections(parsed, output_language, sources)
    final_report = ResearchReportResponse(
        keyword=keyword,
        research_focus=report_research_focus,
        followup_context=followup_context,
        output_language=output_language,
        research_mode=research_mode,
        report_title=parsed.report_title,
        executive_summary=parsed.executive_summary,
        consulting_angle=parsed.consulting_angle,
        sections=sections,
        target_accounts=parsed.target_accounts,
        top_target_accounts=top_target_accounts,
        pending_target_candidates=pending_target_candidates,
        target_departments=parsed.target_departments,
        public_contact_channels=merged_public_contact_channels,
        account_team_signals=merged_account_team_signals,
        budget_signals=parsed.budget_signals,
        project_distribution=parsed.project_distribution,
        strategic_directions=parsed.strategic_directions,
        tender_timeline=parsed.tender_timeline,
        leadership_focus=parsed.leadership_focus,
        ecosystem_partners=parsed.ecosystem_partners,
        top_ecosystem_partners=top_ecosystem_partners,
        pending_partner_candidates=pending_partner_candidates,
        competitor_profiles=parsed.competitor_profiles,
        top_competitors=top_competitors,
        pending_competitor_candidates=pending_competitor_candidates,
        benchmark_cases=parsed.benchmark_cases,
        flagship_products=parsed.flagship_products,
        key_people=parsed.key_people,
        five_year_outlook=parsed.five_year_outlook,
        client_peer_moves=parsed.client_peer_moves,
        winner_peer_moves=parsed.winner_peer_moves,
        competition_analysis=parsed.competition_analysis,
        source_count=len(sources),
        evidence_density=evidence_density,
        source_quality=source_quality,
        query_plan=effective_query_plan + adapter_query_plan,
        sources=_to_research_source_outputs(sources),
        source_diagnostics=source_diagnostics,
        entity_graph=entity_graph,
        generated_at=datetime.now(timezone.utc),
    )
    final_report = _enrich_report_for_delivery(final_report)
    _emit_research_snapshot(snapshot_callback, final_report)
    return final_report
