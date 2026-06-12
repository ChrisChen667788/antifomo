from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
import re

from app.services.content_extractor import normalize_text
from app.services.research.entity_heuristics import (
    entity_canonical_key as heuristic_entity_canonical_key,
    extract_rank_entity_candidates as heuristic_extract_rank_entity_candidates,
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
THEME_GENERIC_SUPPRESSIONS: dict[str, tuple[str, ...]] = {"AI漫剧": ("大模型", "人工智能")}
GENERIC_FOCUS_TOKENS = {
    "预算", "招标", "采购", "中标", "甲方", "竞品", "生态伙伴", "生态", "伙伴", "领导讲话",
    "领导", "讲话", "项目", "商机", "区域", "行业", "客户", "公司", "同行", "战略", "规划",
}
GENERIC_COMPANY_ANCHOR_TOKENS = {
    "ai", "aigc", "大模型", "模型", "人工智能", "短剧", "漫剧", "动画", "内容", "平台",
    "方案", "商机", "调研", "研究", "研报", "采购", "招标", "预算", "项目", "行业", "客户",
    "生态", "伙伴", "竞品", "机会", "线索",
}
INVALID_COMPANY_ANCHOR_PHRASES = (
    "优先给具体公司", "官方业务联系方式", "公开渠道联络人信息", "公开业务联系方式",
    "公开联络人信息", "联系方式", "联络人信息", "聚焦内容平台", "聚焦动漫ip",
    "即使暂时没有明确公司",
)
SCOPE_PROMPT_NOISE_PREFIXES = (
    "我作为", "我想", "我们想", "我们要", "帮我", "请帮", "请把", "作为", "该在", "想在",
    "预计", "它将", "是依托", "不仅",
)
SCOPE_PROMPT_NOISE_TOKENS = (
    "我们公司", "找客户", "找项目", "决策权", "预算规模", "哪些重点公司", "这些客户", "一并调研",
    "把竞品公司", "竞品公司情况", "竟品公司", "包括但不限于", "精确到决策单位", "精确到决策部门",
    "已经有了哪些标杆案例", "可扩展的计算服务", "大型国际银行", "全球银行", "全球服务中心",
)
SCOPE_PROMPT_NOISE_REGEXES = (
    r"\b(?:maas|iaas|paas|saas|agent)\b.*公司",
    r"哪些[^。；;\n]{0,24}(?:公司|客户|部门|领导)",
    r"(?:预算|金额|规模)[^。；;\n]{0,16}如何",
)
QUERY_NOISE_SUFFIXES = (
    "相关商机", "商机", "机会", "线索", "情报", "调研", "研究", "研报", "专题", "分析", "建议", "方案", "报告",
)

REGION_TOKENS = (
    "北京", "上海", "广州", "深圳", "杭州", "南京", "苏州", "成都", "重庆", "武汉", "西安", "天津",
    "青岛", "郑州", "长沙", "合肥", "福州", "厦门", "宁波", "无锡", "济南", "沈阳", "大连", "哈尔滨",
    "长春", "昆明", "南宁", "南昌", "石家庄", "太原", "贵阳", "兰州", "乌鲁木齐", "呼和浩特", "海南",
    "河北", "河南", "山东", "山西", "陕西", "江苏", "浙江", "安徽", "福建", "江西", "湖北", "湖南", "广东",
    "广西", "云南", "贵州", "四川", "甘肃", "青海", "宁夏", "新疆", "西藏", "内蒙古", "辽宁", "吉林", "黑龙江",
)
ORG_PATTERN = re.compile(
    r"([A-Za-z0-9\u4e00-\u9fa5·（）()]{2,40}"
    r"(?:集团|公司|有限公司|股份有限公司|研究院|研究所|大学|医院|银行|政府|厅|局|委|办|中心|学院|学校|科技|智能|信息|控股|实验室))"
)
COMPACT_ENTITY_PATTERN = re.compile(
    r"([A-Za-z0-9\u4e00-\u9fa5·]{2,24}(?:数码|软件|信息|科技|咨询|顾问|股份|集团|服务|运营|网络|系统|通信|集成|研究院|协会|联盟))"
)
SPECIAL_ENTITY_ALIASES = (
    "德勤", "普华永道", "毕马威", "安永", "埃森哲", "IBM", "Microsoft", "OpenAI", "阿里云", "腾讯云",
    "华为", "中兴通讯", "神州数码", "新华三", "太极股份", "东软集团", "浪潮软件", "软通动力", "中电金信",
    "中国移动", "中国电信", "中国联通", "用友网络", "金蝶",
)
PARTNER_CONNECTOR_ALIASES = (
    "德勤", "普华永道", "毕马威", "安永", "埃森哲", "神州数码", "新华三", "软通动力", "中电金信",
    "中国移动", "中国电信", "中国联通", "太极股份",
)
KNOWN_LIGHTWEIGHT_ENTITY_NAMES = {
    *SPECIAL_ENTITY_ALIASES,
    "爱奇艺", "快手", "抖音", "字节跳动", "优酷", "腾讯视频", "腾讯动漫", "哔哩哔哩", "快看漫画",
    "阅文集团", "芒果超媒", "小红书", "美图", "中文在线", "掌阅科技", "华策影视", "光线传媒", "上海儒意",
    "追光动画", "百联集团", "格科半导体", "超硅半导体",
}
GENERIC_SCOPE_CLIENT_TOKENS = ("头部公司", "重点公司", "行业竞品公司", "甲方公司", "一家公司", "一人公司")
ENTITY_BLACKLIST_TOKENS = (
    "发布", "推进", "围绕", "布局", "显示", "启动", "持续", "建设", "合作", "联合", "方案", "项目", "预算",
    "政务云", "咨询与集成", "联合交付", "公开线索", "项目建设",
)
ENTITY_INVALID_PHRASE_TOKENS = (
    "怎么办", "如何", "制作", "利用", "是指", "一种", "相关商机", "相关讯息", "教程", "指南", "步骤", "案例拆解",
    "经验", "相关", "方向", "赛道", "行业", "领域", "信息", "新闻", "建议追加", "如果短期", "当前关键词范围",
    "公开线索", "优先给具体公司", "官方业务联系方式", "公开渠道联络人信息", "公开业务联系方式", "美国证券交易委",
    "证券交易委", "已向美国证券交易委", "公有云服务", "基础设施即服务", "模型即服务", "新协议", "保留了",
    "两家公司", "几家公司", "多家公司", "现在可以", "可以通过", "任何云服务", "不用再", "不再给", "宣布修订",
    "长期合作", "绑定关系", "合作协议", "基本框架", "各有关", "并经",
)
LOW_VALUE_ENTITY_NAME_TOKENS = (
    "会员中心", "入局", "掘金赛道", "保姆级", "最新版", "工作流", "完全指南", "怎么个事", "所有人都", "关于加强",
    "促进政府", "已成为", "改变系统", "支撑软件", "应用系统", "弹性服务", "模型服务", "公有云服务", "基础设施即服务",
    "模型即服务", "主力与协办", "标签服务", "用户画像服务", "英寸", "毫米硅片", "逻辑制程", "CIS集成",
)
ENTITY_FRAGMENT_PREFIX_TOKENS = (
    "此次", "由于", "相应", "相关", "本次", "该", "该类", "这个", "这类", "基于", "围绕", "通过", "针对", "聚焦",
    "正在", "已经", "主要", "因为", "如果", "对于", "已向", "即使", "现在", "过去", "未来", "同时", "但", "而是",
    "新协议", "双方", "各有关", "并经",
)
ENTITY_FRAGMENT_INFIX_TOKENS = (
    "主要基于", "相应调整", "调整系统", "相应系统", "由于公司", "基于公司", "围绕公司", "赋能", "服务于", "用于",
    "模式", "路径", "打法", "策略", "方法", "场景", "机会", "商机", "保留了", "可以通过", "任何云服务", "不用再",
    "不再给", "宣布修订", "长期合作", "绑定关系", "合作协议", "基本框架", "先进逻辑制程", "全自动智能", "各有关", "并经",
)
ENTITY_SUFFIX_TOKENS = (
    "集团", "公司", "有限公司", "股份有限公司", "研究院", "研究所", "大学", "医院", "银行", "政府", "厅", "局", "委",
    "办", "中心", "学院", "学校", "科技", "信息", "控股", "实验室", "协会", "联盟", "咨询", "顾问", "集成", "服务",
    "运营", "系统", "通信", "半导体",
)
ENTITY_LEADING_NOISE_PREFIXES = (
    "新增范围锁定到", "新增范围集中到", "新增重点锁定到", "新增重点集中到", "范围锁定到", "范围集中到", "重点锁定到",
    "重点集中到", "锁定到", "集中到", "收敛到", "聚焦到", "落到", "落在", "其中就包括", "其中包括", "其中有",
    "过去一段时间", "如果这一方案最终成形", "若最终落地", "它将被视为", "预计将是", "但该公司", "该公司", "关于",
    "例如", "比如", "诸如", "包括",
)
ENTITY_ACTION_PHRASE_TOKENS = (
    "进一步", "扩大", "推进", "推动", "打造", "贯彻", "落实", "印发", "实施", "支持", "促进", "加强", "提升", "降低",
    "举办", "表示", "介绍", "显示", "获得", "收购", "聚焦",
)
ENTITY_PLACEHOLDER_TOKENS = (
    "关键词已明确收敛到该公司", "该公司", "我方切口在于", "需重点验证", "优先核验", "顶层设计与咨询",
    "动漫 IP 咨询与发行伙伴", "区域内容集成与渠道分发伙伴", "文旅/教育场景牵线伙伴", "推出首批", "掌握底层AI服务",
    "大视听公共服务", "全方位服务",
)
CONTACT_PLACEHOLDER_TOKENS = (
    "当前已收敛到具体公司，但公开联系方式仍不足", "优先收集公开业务入口", "建议补充公开服务热线",
    "建议将关键词收敛到具体甲方公司或项目名称", "如果公开联系方式依旧不足",
)
GENERIC_COUNT_ENTITY_PATTERN = re.compile(r"^[一二三四五六七八九十百千两几多\d]+家")
DEPARTMENT_PATTERN = re.compile(
    r"([A-Za-z0-9\u4e00-\u9fa5·（）()]{2,40}"
    r"(?:采购部|采购中心|招标办|招采中心|集采中心|信息中心|信息化部|数字化部|科技部|战略发展部|数据局|数据资源局|办公室|财务部|计划财务部|运营部|网络安全部|政务服务中心|行政审批局|事业发展部|建设管理部|投资管理部))"
)
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?86[- ]?)?(?:1[3-9]\d{9}|0\d{2,3}[- ]?\d{7,8})(?!\d)")
GENERIC_CONTENT_DOMAINS = (
    "zhuanlan.zhihu.com", "www.zhihu.com", "www.bilibili.com", "segmentfault.com", "www.cnblogs.com", "news.qq.com", "mp.weixin.qq.com",
)
ENTITY_ROLE_FIELDS: dict[str, str] = {
    "target_accounts": "target", "client_peer_moves": "target", "competitor_profiles": "competitor",
    "winner_peer_moves": "competitor", "ecosystem_partners": "partner",
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
CONTACT_ROW_HINT_TOKENS = (
    "公开邮箱", "公开电话", "公开联系人", "高概率公开联系页", "官网/公开入口", "服务热线", "联系邮箱", "联系电话",
    "采购人联系人", "代理机构联系人", "可能归口部门",
)
DEPARTMENT_HINT_TOKENS = (
    "采购部", "采购中心", "招标办", "招采中心", "集采中心", "信息中心", "信息化部", "数字化部", "科技部", "数据局",
    "数据资源局", "办公室", "财务部", "计划财务部", "运营部", "网络安全部", "政务服务中心", "行政审批局", "事业发展部",
    "建设管理部", "投资管理部",
)
CASE_HINT_TOKENS = ("案例", "项目", "落地", "部署", "平台", "中标", "示范", "试点", "标杆")
PRODUCT_HINT_TOKENS = ("产品", "平台", "系统", "方案", "服务", "引擎", "模型", "套件")
NON_CONTACT_SOURCE_LABEL_TOKENS = ("云头条", "剑鱼标讯", "微信公众号", "互联网公开网页", "政府采购合规聚合")
THEME_COMPANY_PUBLIC_SOURCE_SEEDS: dict[str, tuple[str, ...]] = {
    "AI漫剧": (
        "爱奇艺", "哔哩哔哩", "腾讯视频", "腾讯动漫", "优酷", "快手", "快看漫画", "抖音", "字节跳动", "阅文集团",
        "芒果超媒", "中文在线", "掌阅科技", "美图", "华策影视", "光线传媒", "上海儒意", "追光动画",
    ),
    "政务云": ("阿里云", "腾讯云", "华为", "中兴通讯", "神州数码", "新华三", "软通动力", "太极股份", "中国移动", "中国电信", "中国联通"),
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


@lru_cache(maxsize=8192)
def strip_entity_leading_noise(value: str) -> str:
    compact = normalize_text(value)
    changed = True
    while changed and compact:
        changed = False
        for prefix in ENTITY_LEADING_NOISE_PREFIXES:
            if compact.startswith(prefix):
                compact = normalize_text(compact[len(prefix) :].lstrip("：:，,;；- "))
                changed = True
    return compact


@lru_cache(maxsize=8192)
def contains_low_value_entity_token(value: str) -> bool:
    return any(token in normalize_text(value) for token in LOW_VALUE_ENTITY_NAME_TOKENS)


@lru_cache(maxsize=8192)
def is_lightweight_entity_name(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized or len(normalized) < 2 or len(normalized) > 14:
        return False
    if normalized not in KNOWN_LIGHTWEIGHT_ENTITY_NAMES or contains_low_value_entity_token(normalized):
        return False
    if any(token in normalized for token in ENTITY_INVALID_PHRASE_TOKENS):
        return False
    if any(token in normalized for token in ("入口", "官网", "官网入口", "公开入口", "联系页", "会员中心")):
        return False
    if any(char in normalized for char in "：:（）()[]【】"):
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9\u4e00-\u9fa5·]{2,14}", normalized))


@lru_cache(maxsize=8192)
def looks_like_sentence_fragment_entity(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized or normalized in SPECIAL_ENTITY_ALIASES or normalized in KNOWN_LIGHTWEIGHT_ENTITY_NAMES:
        return False
    if normalized.lower() in {"microsoft", "openai"}:
        return False
    if re.search(r"(?:一|两|二|几|多|\d+)\s*家(?:公司|企业|厂商|机构)$", normalized):
        return True
    if normalized.startswith(ENTITY_FRAGMENT_PREFIX_TOKENS):
        return True
    if any(token in normalized for token in (*ENTITY_FRAGMENT_INFIX_TOKENS, *ENTITY_INVALID_PHRASE_TOKENS)):
        return True
    return len(normalized) >= 10 and any(token in normalized for token in ("了", "可以", "通过", "不用", "仍是", "仍将", "转向"))


@lru_cache(maxsize=8192)
def looks_like_placeholder_entity_name(value: str) -> bool:
    normalized = strip_entity_leading_noise(value)
    lowered = normalized.lower()
    if not normalized or normalized in SPECIAL_ENTITY_ALIASES or normalized in KNOWN_LIGHTWEIGHT_ENTITY_NAMES:
        return False
    if looks_like_sentence_fragment_entity(normalized):
        return True
    if "（如" in normalized or "(如" in normalized or GENERIC_COUNT_ENTITY_PATTERN.match(normalized):
        return True
    if re.search(r"(19|20)\d{2}", normalized) or "待验证" in normalized or "待驗證" in normalized:
        return True
    if normalized.startswith(("AI的", "一直", "此前", "在杭州市", "相关负责人", "对公开市场投资者而言", "上海作为")):
        return True
    if normalized.startswith(("推出首批", "构建PC端", "构建移动端", "对具有重大影响力的")):
        return True
    industry_alias_values = {alias for aliases in INDUSTRY_SCOPE_ALIASES.values() for alias in aliases}
    if normalized in industry_alias_values:
        return False
    if any(token in normalized for token in (*ENTITY_PLACEHOLDER_TOKENS, *GENERIC_SCOPE_CLIENT_TOKENS)):
        return True
    if any(token in lowered for token in ("报名通道开启", "多端联动", "opc社区", "opc创新社区", "超级个体")):
        return True
    if normalized in {"科技数码", "主办与协办", "基础算力与云服务", "区域大型系统集成", "开发集团", "各有关大学", "并经市政府"}:
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
    if normalized.endswith(("伙伴", "咨询", "顾问", "发行伙伴", "牵线伙伴")) and not any(token in normalized for token in ENTITY_SUFFIX_TOKENS):
        return True
    if len(normalized) <= 6 and normalized.endswith(("数码", "团队", "云服务")) and not any(token in normalized for token in ENTITY_SUFFIX_TOKENS):
        return True
    if any(token in normalized for token in ENTITY_ACTION_PHRASE_TOKENS) and not any(token in normalized for token in ENTITY_SUFFIX_TOKENS):
        return True
    return normalized.endswith(("人工智能", "生成式AI", "大模型", "AI")) and not any(token in normalized for token in ENTITY_SUFFIX_TOKENS)


@lru_cache(maxsize=8192)
def looks_like_fragment_entity_name(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return True
    if looks_like_sentence_fragment_entity(normalized) or looks_like_placeholder_entity_name(normalized):
        return True
    if re.match(r"^(19|20)\d{2}", normalized) or normalized.startswith(ENTITY_FRAGMENT_PREFIX_TOKENS):
        return True
    if any(token in normalized for token in ENTITY_FRAGMENT_INFIX_TOKENS):
        return True
    if len(normalized) <= 4 and normalized.endswith(("局", "委", "办", "中心", "政府")) and not any(
        token in normalized for token in (*REGION_TOKENS, "人民", "文物", "数据", "信息", "交通", "教育", "医疗")
    ) and normalized not in KNOWN_LIGHTWEIGHT_ENTITY_NAMES:
        return True
    if normalized.endswith(("服务", "系统", "社区")) and not any(token in normalized for token in ENTITY_SUFFIX_TOKENS) and normalized not in KNOWN_LIGHTWEIGHT_ENTITY_NAMES:
        return True
    return False


@lru_cache(maxsize=8192)
def trim_product_spec_from_entity_name(value: str) -> str:
    normalized = strip_entity_leading_noise(value)
    for pattern in (
        r"^([A-Za-z0-9\u4e00-\u9fa5·]{2,18}半导体)(?:\d|[一二三四五六七八九十]|先进|用|CIS|芯片|硅片|制程|工艺|项目|产线|封装|传感器).+$",
        r"^([A-Za-z0-9\u4e00-\u9fa5·]{2,18}集成电路)(?:\d|[一二三四五六七八九十]|先进|用|芯片|硅片|制程|工艺|项目|产线).+$",
    ):
        match = re.match(pattern, normalized, flags=re.IGNORECASE)
        if match:
            candidate = strip_entity_leading_noise(match.group(1))
            if candidate and not contains_low_value_entity_token(candidate):
                return candidate
    return normalized


@lru_cache(maxsize=16384)
def is_plausible_entity_name(value: str) -> bool:
    normalized = strip_entity_leading_noise(value)
    if not normalized or len(normalized) < 3:
        return False
    if looks_like_sentence_fragment_entity(normalized) or looks_like_fragment_entity_name(normalized):
        return False
    if looks_like_placeholder_entity_name(normalized) or contains_low_value_entity_token(normalized):
        return False
    if any(token in normalized for token in (*ENTITY_BLACKLIST_TOKENS, *ENTITY_INVALID_PHRASE_TOKENS)):
        return False
    if any(char in normalized for char in "，,。；;") or "：" in normalized or ":" in normalized:
        return False
    if normalized.startswith(("和", "与", "及", "或", "如", "例如", "比如", "诸如", "优先给", "官方", "公开")):
        return False
    if any(connector in normalized for connector in ("与", "及", "和")) and normalized not in SPECIAL_ENTITY_ALIASES and not any(
        token in normalized for token in ENTITY_SUFFIX_TOKENS
    ):
        return False
    if normalized.endswith(("怎么办", "如何", "制作", "是指", "相关")):
        return False
    if re.search(r"(路径|节奏|策略|打法|能力|场景|机会|商机|窗口|趋势|布局|运营|建设|规划|升级|协同|统筹)$", normalized):
        return False
    industry_alias_values = {alias for aliases in INDUSTRY_SCOPE_ALIASES.values() for alias in aliases}
    if normalized in industry_alias_values:
        return False
    if any(alias == normalized or alias in normalized for alias in SPECIAL_ENTITY_ALIASES):
        return True
    if any(token in normalized for token in ENTITY_SUFFIX_TOKENS):
        return True
    compact = re.sub(r"\s+", "", normalized)
    return bool(ORG_PATTERN.fullmatch(compact) or COMPACT_ENTITY_PATTERN.fullmatch(compact))


def extract_rank_entity_name(value: str) -> str:
    text = normalize_text(value)
    candidates = [*ORG_PATTERN.findall(text), *COMPACT_ENTITY_PATTERN.findall(text)]
    candidates.extend(alias for alias in KNOWN_LIGHTWEIGHT_ENTITY_NAMES if alias in text)
    candidates.extend(heuristic_extract_rank_entity_candidates(text))
    for candidate in candidates:
        normalized = trim_product_spec_from_entity_name(candidate)
        if (is_plausible_entity_name(normalized) or is_lightweight_entity_name(normalized)) and not looks_like_fragment_entity_name(normalized):
            return normalized
    return ""


def fallback_entity_name_from_row(value: str) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    head = strip_entity_leading_noise(normalized.split("：", 1)[0].split(":", 1)[0])
    if is_lightweight_entity_name(head):
        return head
    match = re.match(r"([A-Za-z0-9\u4e00-\u9fa5·]{2,14})(?:等|与|及|和|在|已|将|正|宣布|布局|入局|合作|参与)", normalized)
    if match:
        candidate = strip_entity_leading_noise(match.group(1))
        if is_lightweight_entity_name(candidate):
            return candidate
    return ""


def looks_like_placeholder_contact_row(value: str) -> bool:
    normalized = normalize_text(value)
    return bool(normalized) and any(token in normalized for token in CONTACT_PLACEHOLDER_TOKENS)


def entity_canonical_key(value: str) -> str:
    return heuristic_entity_canonical_key(value)


def is_theme_aligned_entity_name(value: str, *, role: str, theme_labels: list[str]) -> bool:
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


def is_trustworthy_scope_client_name(
    value: str,
    *,
    theme_labels: list[str] | None = None,
    looks_like_scope_prompt_noise: Callable[[str], bool],
) -> bool:
    normalized = strip_entity_leading_noise(value)
    active_theme_labels = [normalize_text(item) for item in theme_labels or [] if normalize_text(item)]
    lowered = normalized.lower()
    if not normalized or re.search(r"(19|20)\d{2}", normalized):
        return False
    if looks_like_scope_prompt_noise(normalized) or looks_like_placeholder_entity_name(normalized):
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
    if any(token in normalized for token in ("和", "及", "与")) and any(token in normalized for token in ("全球", "国际", "重点")) and not any(
        token in normalized for token in ("集团", "公司", "局", "委", "办", "中心", "政府")
    ):
        return False
    if "AI漫剧" in active_theme_labels and any(token in normalized for token in ("政府", "办公厅", "市委", "局", "委", "办")):
        return False
    if "政务云" in active_theme_labels and not any(
        token in normalized for token in ("政府", "局", "委", "办", "中心", "集团", "公司", "平台", "城投", "国资", "大数据", "信息")
    ):
        return False
    if normalized in KNOWN_LIGHTWEIGHT_ENTITY_NAMES or normalized in SPECIAL_ENTITY_ALIASES:
        return True
    if any(token in normalized for token in ENTITY_SUFFIX_TOKENS):
        return not (any(token in lowered for token in ("maas", "iaas", "paas", "saas")) and "公司" in normalized)
    return False
