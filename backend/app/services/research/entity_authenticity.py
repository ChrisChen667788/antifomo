from __future__ import annotations

from dataclasses import dataclass
import re

from app.services.content_extractor import normalize_text


LEGAL_ORGANIZATION_SUFFIXES = (
    "股份有限公司",
    "有限责任公司",
    "集团有限公司",
    "控股有限公司",
    "有限公司",
    "总公司",
    "分公司",
    "公司",
    "集团",
)
NAMED_INSTITUTION_SUFFIXES = (
    "管理委员会",
    "专业委员会",
    "技术委员会",
    "人民政府",
    "研究中心",
    "创新中心",
    "技术中心",
    "研究院",
    "研究所",
    "博物院",
    "博物馆",
    "图书馆",
    "文化馆",
    "美术馆",
    "委员会",
    "实验室",
    "交易所",
    "大学",
    "学院",
    "学校",
    "医院",
    "银行",
    "证券",
    "保险",
    "基金",
    "信托",
    "协会",
    "学会",
    "商会",
    "联盟",
)
ADMIN_ORGANIZATION_SUFFIXES = ("中心", "政府", "办公厅", "办公室", "厅", "局", "委", "办", "部")
GENERIC_COMMERCIAL_SUFFIXES = (
    "人工智能",
    "科技",
    "智能",
    "信息",
    "服务",
    "运营",
    "系统",
    "通信",
    "集成",
    "咨询",
    "顾问",
    "网络",
    "软件",
    "数码",
    "传媒",
    "影业",
    "数据",
    "平台",
    "云",
    "建设",
    "改造",
    "升级",
    "应用",
    "项目",
    "方案",
    "需求",
    "场景",
    "能力",
    "业务",
    "工作",
    "管理",
    "治理",
    "规划",
    "产品",
    "功能",
)

RELATION_PREFIXES = (
    "依托单位",
    "共建单位",
    "建设单位",
    "采购单位",
    "采购人",
    "中标单位",
    "中标人",
    "成交供应商",
    "供应商",
    "运营单位",
    "承建单位",
    "合作单位",
    "合作伙伴",
    "合作方",
    "主办单位",
    "承办单位",
    "牵头单位",
    "建议推荐",
    "推荐",
    "现隶属于",
    "隶属于",
    "以下简称",
    "依托",
)
LEADING_NARRATIVE_PREFIXES = (
    "并充分发挥",
    "充分发挥",
    "随着",
    "与此同时",
    "正如",
    "作为",
    "其中",
    "此外",
    "优化",
    "开展",
    "推动",
    "推进",
    "提升",
    "打造",
    "构建",
    "实现",
    "促进",
    "加强",
    "支持",
    "通过",
    "围绕",
    "聚焦",
    "利用",
    "采用",
    "推出",
    "形成",
    "当前",
    "目前",
    "未来",
    "进一步",
    "落实",
    "深化",
    "涉及",
    "确立",
    "根据",
    "点开",
    "跨地区",
    "以人民为",
    "新设立",
    "已经",
    "获得",
    "此次",
    "该",
)
NARRATIVE_INFIX_PATTERNS = (
    "正从",
    "正在从",
    "数据开展",
    "评价数据",
    "可以通过",
    "服务于",
    "用于",
    "已成为",
    "将成为",
    "国家层面",
    "统一部署",
    "各批次",
    "等市级",
    "等区域",
    "重塑",
    "不再",
    "围绕",
    "正以",
    "为半径",
    "加快布局",
    "举办",
    "国内第一家",
    "省内各",
    "关于",
)
GENERIC_ENTITY_PHRASES = {
    "综合服务",
    "智慧服务",
    "智能服务",
    "平台服务",
    "运营服务",
    "技术服务",
    "数据智能",
    "文旅智能",
    "人工智能",
    "技术创新中心",
    "综合服务中心",
    "公共服务中心",
    "信息中心",
    "数据中心",
    "采购中心",
    "运营中心",
    "中国大学",
}
GENERIC_LEGAL_NAME_STEMS = {
    "公司",
    "企业",
    "厂商",
    "招标",
    "采购",
    "供应商",
    "服务",
    "运营",
    "平台",
    "科技",
    "技术",
    "信息",
    "智能",
    "数据",
    "综合服务",
    "技术服务",
    "招标代理",
}
GENERIC_LEGAL_NAME_PREFIXES = (
    "相关",
    "有关",
    "某",
    "该",
    "本项目",
    "当地",
    "地方",
    "一家",
    "多家",
    "招标",
    "采购",
    "供应商",
    "服务",
    "运营",
    "平台",
    "综合",
)
GENERIC_INSTITUTION_STEMS = {
    "相关",
    "有关",
    "综合",
    "公共",
    "技术",
    "行业",
    "平台",
    "数字",
    "智慧",
    "文化",
    "旅游",
    "文旅",
    "数据",
    "信息",
    "创新",
    "服务",
    "运营",
    "智能",
    "人工智能",
}
GENERIC_ADMIN_PREFIXES = (
    "省",
    "市",
    "区",
    "县",
    "各省",
    "各市",
    "各区",
    "各县",
    "各地",
    "当地",
    "地方",
    "有关",
    "相关",
)
CENTRAL_ADMIN_ORGANIZATION_NAMES = {
    "外交部",
    "国防部",
    "国家发展和改革委员会",
    "教育部",
    "科学技术部",
    "工业和信息化部",
    "国家民族事务委员会",
    "公安部",
    "民政部",
    "司法部",
    "财政部",
    "人力资源和社会保障部",
    "自然资源部",
    "生态环境部",
    "住房和城乡建设部",
    "交通运输部",
    "水利部",
    "农业农村部",
    "商务部",
    "文化和旅游部",
    "国家卫生健康委员会",
    "退役军人事务部",
    "应急管理部",
    "中国人民银行",
    "审计署",
}
ADMIN_OWNER_TOKENS = (
    "中国",
    "国家",
    "国务院",
    "中央",
    "人民",
    "省",
    "市",
    "区",
    "县",
    "自治",
    "兵团",
    "文化和旅游部",
    "文化和旅游厅",
    "文化和旅游局",
    "文物局",
    "数据局",
    "教育部",
    "教育厅",
    "教育局",
    "工业和信息化部",
    "发展改革委",
    "财政厅",
    "财政局",
    "商务厅",
    "商务局",
    "交通运输",
    "卫生健康",
    "市场监督",
    "自然资源",
    "生态环境",
    "广播电视",
    "应急管理",
    "大学",
    "医院",
    "集团",
    "公司",
    "研究院",
)
_TRAILING_ANNOTATION_PATTERN = re.compile(
    r"(?:[（(](?:本级|筹|筹建|以下简称[^）)]*|下称[^）)]*)[）)])+$"
)
_GENERIC_COUNT_PATTERN = re.compile(r"^(?:一|两|二|几|多|\d+)家(?:公司|企业|厂商|机构)")
_GENERIC_JURISDICTION_PLACEHOLDER_PATTERN = re.compile(
    r"^(?:省|市|区|县)(?:数据|大数据|城投|交投|文旅|国资|政务|产业)(?:公司|集团|中心|平台|研究院)$"
)
_COLLECTIVE_ORGANIZATION_PATTERN = re.compile(
    r"^(?:[一二三四五六七八九十\d]+省[一二三四五六七八九十\d]+市|多省|多市|各省|各市|各区|各县|各地|长三角(?:地区)?各)"
)
_COMPOUND_ORGANIZATION_PATTERN = re.compile(
    r"(?:中心|政府|办公厅|办公室|厅|局|委|办|部|公司|集团)(?:和|及|与|、).+"
    r"(?:中心|政府|办公厅|办公室|厅|局|委|办|部|公司|集团)$"
)
_ALLOWED_NAME_PATTERN = re.compile(r"[A-Za-z0-9\u4e00-\u9fa5·&（）()\-.]{2,64}")


@dataclass(frozen=True, slots=True)
class OrganizationNameDecision:
    original_name: str
    normalized_name: str
    accepted: bool
    reason: str
    repaired: bool = False


def _normalized_known_names(known_names: tuple[str, ...] | list[str] | set[str]) -> dict[str, str]:
    rows: dict[str, str] = {}
    for value in known_names:
        normalized = normalize_text(str(value))
        if normalized:
            rows.setdefault(normalized.lower(), normalized)
    return rows


def _has_structural_suffix(value: str) -> bool:
    return value.endswith((*LEGAL_ORGANIZATION_SUFFIXES, *NAMED_INSTITUTION_SUFFIXES, *ADMIN_ORGANIZATION_SUFFIXES))


def repair_organization_candidate(
    value: str,
    *,
    known_names: tuple[str, ...] | list[str] | set[str] = (),
) -> str:
    normalized = normalize_text(value).strip(" \t\r\n，,。；;：:、|/\\-—_\"'“”‘’【】[]")
    if not normalized:
        return ""
    normalized = _TRAILING_ANNOTATION_PATTERN.sub("", normalized).strip()
    known = _normalized_known_names(known_names)
    if normalized.lower() in known:
        return known[normalized.lower()]

    candidate = normalized
    for left, right in (("（", "）"), ("(", ")")):
        if candidate.count(left) > candidate.count(right):
            head = normalize_text(candidate.split(left, 1)[0])
            if head and _has_structural_suffix(head):
                candidate = head
                break
    for prefix in RELATION_PREFIXES:
        index = candidate.rfind(prefix)
        if index < 0:
            continue
        tail = normalize_text(candidate[index + len(prefix) :]).lstrip("：:，,、 ")
        if tail and (_has_structural_suffix(tail) or tail.lower() in known):
            candidate = tail
            break

    for prefix in ("随着由", "由", "与", "及", "和"):
        if candidate.startswith(prefix):
            tail = normalize_text(candidate[len(prefix) :]).lstrip("：:，,、 ")
            if tail and (_has_structural_suffix(tail) or tail.lower() in known):
                candidate = tail
                break

    for prefix in ("名称", "单位名称", "企业名称", "机构名称"):
        if candidate.startswith(prefix):
            candidate = normalize_text(candidate[len(prefix) :]).lstrip("：:，,、 ")
            break
    return _TRAILING_ANNOTATION_PATTERN.sub("", candidate).strip()


def evaluate_organization_name(
    value: str,
    *,
    known_names: tuple[str, ...] | list[str] | set[str] = (),
    trusted_known_names: tuple[str, ...] | list[str] | set[str] = (),
) -> OrganizationNameDecision:
    original = normalize_text(value)
    known = _normalized_known_names(known_names)
    trusted = _normalized_known_names(trusted_known_names)
    candidate = repair_organization_candidate(
        original,
        known_names=(*known_names, *trusted_known_names),
    )
    repaired = bool(candidate and candidate != original)
    is_known_candidate = candidate.lower() in known if candidate else False
    is_trusted_candidate = candidate.lower() in trusted if candidate else False
    if not candidate:
        return OrganizationNameDecision(original, "", False, "empty", repaired)
    if (
        len(candidate) < 2
        or len(candidate) > 64
        or (len(candidate) == 2 and not (is_known_candidate or is_trusted_candidate))
    ):
        return OrganizationNameDecision(original, candidate, False, "invalid_length", repaired)
    if not _ALLOWED_NAME_PATTERN.fullmatch(candidate):
        return OrganizationNameDecision(original, candidate, False, "invalid_characters", repaired)
    if candidate.count("（") != candidate.count("）") or candidate.count("(") != candidate.count(")"):
        return OrganizationNameDecision(original, candidate, False, "invalid_parentheses", repaired)
    if _GENERIC_COUNT_PATTERN.match(candidate):
        return OrganizationNameDecision(original, candidate, False, "generic_count_phrase", repaired)
    if _GENERIC_JURISDICTION_PLACEHOLDER_PATTERN.match(candidate):
        return OrganizationNameDecision(original, candidate, False, "missing_legal_jurisdiction", repaired)
    if _COLLECTIVE_ORGANIZATION_PATTERN.match(candidate):
        return OrganizationNameDecision(original, candidate, False, "collective_organization", repaired)
    if _COMPOUND_ORGANIZATION_PATTERN.search(candidate):
        return OrganizationNameDecision(original, candidate, False, "compound_organization", repaired)
    if candidate in GENERIC_ENTITY_PHRASES:
        return OrganizationNameDecision(original, candidate, False, "generic_service_phrase", repaired)
    if candidate.startswith(LEADING_NARRATIVE_PREFIXES):
        return OrganizationNameDecision(original, candidate, False, "narrative_prefix", repaired)
    if any(token in candidate for token in NARRATIVE_INFIX_PATTERNS):
        return OrganizationNameDecision(original, candidate, False, "narrative_fragment", repaired)
    if candidate.endswith(("全部", "均已完成", "全部完成", "完成标准化建设")):
        return OrganizationNameDecision(original, candidate, False, "narrative_fragment", repaired)

    legal_suffix = next((suffix for suffix in LEGAL_ORGANIZATION_SUFFIXES if candidate.endswith(suffix)), "")
    if legal_suffix:
        stem = candidate[: -len(legal_suffix)]
        if len(stem) < 2:
            return OrganizationNameDecision(original, candidate, False, "missing_legal_name_stem", repaired)
        if stem in GENERIC_LEGAL_NAME_STEMS or stem.startswith(GENERIC_LEGAL_NAME_PREFIXES):
            return OrganizationNameDecision(original, candidate, False, "generic_legal_name_stem", repaired)
        return OrganizationNameDecision(original, candidate, True, "legal_entity_suffix", repaired)

    institution_suffix = next((suffix for suffix in NAMED_INSTITUTION_SUFFIXES if candidate.endswith(suffix)), "")
    if institution_suffix:
        stem = candidate[: -len(institution_suffix)]
        if len(stem) < 2 or stem in GENERIC_INSTITUTION_STEMS:
            return OrganizationNameDecision(original, candidate, False, "missing_institution_name_stem", repaired)
        return OrganizationNameDecision(original, candidate, True, "named_institution_suffix", repaired)

    admin_suffix = next((suffix for suffix in ADMIN_ORGANIZATION_SUFFIXES if candidate.endswith(suffix)), "")
    if admin_suffix:
        if candidate in CENTRAL_ADMIN_ORGANIZATION_NAMES:
            return OrganizationNameDecision(original, candidate, True, "central_admin_unit", repaired)
        if candidate.startswith(GENERIC_ADMIN_PREFIXES):
            return OrganizationNameDecision(original, candidate, False, "missing_admin_jurisdiction", repaired)
        stem = candidate[: -len(admin_suffix)]
        has_owner = any(token in stem for token in ADMIN_OWNER_TOKENS)
        if len(stem) < 2 or not has_owner:
            return OrganizationNameDecision(original, candidate, False, "unowned_admin_unit", repaired)
        return OrganizationNameDecision(original, candidate, True, "owned_admin_unit", repaired)

    if candidate.endswith(GENERIC_COMMERCIAL_SUFFIXES):
        if is_trusted_candidate:
            return OrganizationNameDecision(original, trusted[candidate.lower()], True, "trusted_entity", repaired)
        return OrganizationNameDecision(original, candidate, False, "generic_commercial_phrase", repaired)
    if is_trusted_candidate:
        return OrganizationNameDecision(original, trusted[candidate.lower()], True, "trusted_entity", repaired)
    if is_known_candidate:
        return OrganizationNameDecision(original, known[candidate.lower()], True, "known_entity", repaired)
    return OrganizationNameDecision(original, candidate, False, "missing_organization_structure", repaired)


def is_authentic_organization_name(
    value: str,
    *,
    known_names: tuple[str, ...] | list[str] | set[str] = (),
    trusted_known_names: tuple[str, ...] | list[str] | set[str] = (),
) -> bool:
    return evaluate_organization_name(
        value,
        known_names=known_names,
        trusted_known_names=trusted_known_names,
    ).accepted
