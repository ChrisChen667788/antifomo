from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from app.schemas.research import ResearchReportDocument
from app.services.content_extractor import normalize_text

_GENERIC_EXACT_ENTITY_NAMES = {
    "中国政府",
    "个人中心",
    "首页",
    "官网",
    "关于我们",
    "办公厅",
    "详情页",
    "中国大学",
    "香港城市大学",
    "客服中心",
    "资讯中心",
    "政府信息",
    "科技数码",
    "内容及服务",
    "标签服务",
    "优化运营",
    "任务中心",
    "买家中心",
    "卖家中心",
    "微短剧服务中心",
    "一人公司",
    "一家公司",
    "个人主页",
    "个人账号",
    "头部公司",
    "MAAS的头部公司",
    "开发集团",
    "各有关大学",
    "并经市政府",
    "社区中心",
    "专家委",
    "前瞻布局",
    "中国政府网政策",
    "中国政府网政策/讲话",
    "直辖市人民政府",
    "国务院各部委",
    "将这款新型数据中心",
    "今日国务院常务会",
    "大结局",
    "主办与协办",
    "云服务",
    "雪鸡观察局",
    "创办自己的初创公司",
    "这是在为大型数据中心采购批量处理器的公司",
}
_GENERIC_ENTITY_PREFIXES = (
    "当前证据不足",
    "建议追加",
    "若需形成",
    "重点跟进",
    "跟踪其",
    "切入",
    "作为核心竞对",
    "构建",
    "建设",
    "为深入贯彻",
    "为锡山乃至长三角的",
    "是依托",
    "到如今",
    "此次",
    "由于",
    "其中",
    "如以上内容有误",
    "预计将",
    "它将",
    "所在国",
    "拟禁止",
    "禁止美国政府",
    "大会吸引",
    "空间提供",
    "为主题的",
    "把搜索范围",
    "即使暂时没有",
    "将这款",
    "今日国务院常务会",
    "消防工作向城乡并重转变",
    "这是在为",
    "各有关",
    "并经",
)
_GENERIC_ENTITY_CONTAINS = (
    "当前证据不足",
    "建议追加",
    "若需形成",
    "交叉检索",
    "公开线索",
    "项目代号",
    "进入窗口",
    "预算窗口",
    "招标窗口",
    "重点跟进",
    "跟踪其",
    "切入",
    "作为核心竞对",
    "角色定位",
    "优势在于",
    "切口在于",
    "客户案例",
    "公开招标公告",
    "政策、商机与落地策略总览",
    "百度百科",
    "网易订阅",
    "搜狐",
    "腾讯新闻",
    "知乎",
    "抖音",
    "微信公众号",
    "大会在",
    "风向已定",
    "爆发元年",
    "新赛道",
    "新风口",
    "透视",
    "初创公司",
    "中国政府网",
    "政策解读",
    "关于印发",
    "印发",
    "解读",
    "携手",
    "联合相关委办",
    "专家委员",
    "云头条",
    "江苏网信网",
    "举办",
)
_GENERIC_ENTITY_SUFFIXES = (
    "服务中心",
    "客服中心",
    "资讯中心",
    "任务中心",
    "买家中心",
    "卖家中心",
    "个人中心",
    "内容及服务",
    "标签服务",
)
_ACCOUNT_QUALIFIER_HINTS = (
    "区域",
    "总部",
    "中心",
    "部门",
    "业务",
    "技术中台",
    "创新中心",
    "华南区",
    "粤港澳",
    "北京总部",
    "深圳总部",
    "大湾区",
    "研发部",
    "事业部",
    "商业化生态部",
    "团队",
    "中台",
    "基地",
)
_ACCOUNT_PLACEHOLDER_PREFIX_BLACKLIST = (
    "重点",
    "目标",
    "潜在",
    "核心",
    "头部",
    "行业",
    "典型",
    "标杆",
    "相关",
    "部分",
    "一批",
    "若干",
    "多个",
    "某",
    "某家",
)
_ORG_HINT_TOKENS = (
    "公司",
    "集团",
    "政府",
    "人民政府",
    "局",
    "委",
    "厅",
    "办",
    "管委会",
    "海关",
    "电视台",
    "广播电视",
    "文旅",
    "银行",
    "大学",
    "学院",
    "研究院",
    "中心",
    "招标中心",
    "招标",
    "国企",
    "文投",
    "城投",
    "云",
    "科技",
    "动漫",
    "哔哩哔哩",
    "快手",
    "爱奇艺",
    "阅文",
    "腾讯",
    "阿里",
    "华为",
    "百度",
    "字节",
    "芒果",
)
_ACCOUNT_ALIAS_MAP = {
    "上海市文旅局": "上海市文化和旅游局",
    "上海市文化和旅游局（上海市广播电视局": "上海市文化和旅游局（上海市广播电视局）",
    "华为云服务": "华为云",
    "阿里巴巴云": "阿里云",
    "腾讯视频": "腾讯",
    "腾讯动漫": "腾讯",
}
_OFFICIAL_DOMAIN_NAME_MAP = {
    "bilibili.com": "哔哩哔哩",
    "yuewen.com": "阅文集团",
    "iqiyi.com": "爱奇艺",
    "kuaishou.com": "快手科技",
    "klingai.com": "快手科技",
    "tencent.com": "腾讯",
    "aliyun.com": "阿里云",
    "alibabacloud.com": "阿里云",
    "huawei.com": "华为云",
    "baidu.com": "百度智能云",
}
_KNOWN_ORG_EXACT_NAMES = {
    *_ACCOUNT_ALIAS_MAP.values(),
    *_OFFICIAL_DOMAIN_NAME_MAP.values(),
    "Microsoft",
    "OpenAI",
    "腾讯",
    "阿里云",
    "华为云",
    "百度智能云",
    "德勤",
    "普华永道",
    "毕马威",
    "安永",
    "埃森哲",
    "IBM",
}
_SENTENCE_FRAGMENT_ENTITY_TOKENS = (
    "新协议",
    "保留了",
    "两家公司",
    "几家公司",
    "多家公司",
    "现在可以",
    "可以通过",
    "任何云服务",
    "不用再",
    "不再给",
    "宣布修订",
    "长期合作",
    "绑定关系",
    "合作协议",
    "基本框架",
)
_SENTENCE_FRAGMENT_ENTITY_PREFIXES = (
    "现在",
    "过去",
    "未来",
    "同时",
    "但",
    "而是",
    "新协议",
    "双方",
)


def _slugify(value: str) -> str:
    normalized = normalize_text(value).lower()
    normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "unknown-account"


def _unique_strings(values: list[str] | tuple[str, ...], *, limit: int | None = None) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = normalize_text(value)
        if not normalized or normalized in result:
            continue
        result.append(normalized)
        if limit is not None and len(result) >= limit:
            break
    return result


def _entity_name(entity: Any) -> str:
    if isinstance(entity, dict):
        return normalize_text(entity.get("name") or entity.get("canonical_name"))
    return normalize_text(getattr(entity, "name", "") or getattr(entity, "canonical_name", ""))


def _entity_canonical_name(entity: Any) -> str:
    if isinstance(entity, dict):
        return _clean_entity_name(entity.get("canonical_name") or entity.get("name") or "")
    return _clean_entity_name(getattr(entity, "canonical_name", "") or getattr(entity, "name", ""))


def _entity_role(entity: Any) -> str:
    if isinstance(entity, dict):
        return normalize_text(entity.get("entity_type")).lower()
    return normalize_text(getattr(entity, "entity_type", "")).lower()


def _clean_entity_name(value: str) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    normalized = (
        normalized.replace("【", "[")
        .replace("】", "]")
        .replace("（", "(")
        .replace("）", ")")
        .replace("：", ":")
        .replace("｜", "|")
    )
    normalized = normalized.strip(" -_|[]")
    if "(" in normalized and ")" not in normalized:
        normalized = f"{normalized})"
    return normalize_text(normalized)


def _looks_like_sentence_fragment_entity_name(value: str) -> bool:
    normalized = _clean_entity_name(value)
    if not normalized or normalized in _KNOWN_ORG_EXACT_NAMES:
        return False
    if re.search(r"(?:一|两|二|几|多|\d+)\s*家(?:公司|企业|厂商|机构)$", normalized):
        return True
    if normalized.startswith(_SENTENCE_FRAGMENT_ENTITY_PREFIXES):
        return True
    if any(token in normalized for token in _SENTENCE_FRAGMENT_ENTITY_TOKENS):
        return True
    if len(normalized) >= 10 and any(token in normalized for token in ("了", "可以", "通过", "不用", "仍是", "仍将", "转向")):
        return True
    return False


def _looks_like_org_name(value: str) -> bool:
    normalized = _clean_entity_name(value)
    if not normalized:
        return False
    if _looks_like_sentence_fragment_entity_name(normalized):
        return False
    if normalized in _KNOWN_ORG_EXACT_NAMES:
        return True
    if _looks_like_named_account_placeholder(normalized):
        return True
    if normalized.count(":") >= 1 or normalized.count("|") >= 1:
        return False
    if any(token in normalized for token in ("预算", "商机", "窗口", "路径", "策略", "打法", "场景", "能力", "机会", "节奏")):
        return False
    if (
        any(connector in normalized for connector in ("及", "与", "和"))
        and not re.search(r"(集团|公司|有限公司|股份有限公司|研究院|研究所|大学|医院|银行|政府|厅|局|委|办|中心|学院|学校|科技)$", normalized)
    ):
        return False
    if any(token in normalized for token in _ORG_HINT_TOKENS):
        return True
    if re.search(r"(集团|公司|局|委|厅|办|台|云|科技|政府)$", normalized):
        return True
    return False


def _looks_like_named_account_placeholder(value: str) -> bool:
    normalized = _clean_entity_name(value)
    if not normalized or len(normalized) > 18:
        return False
    match = re.fullmatch(
        r"(?P<prefix>[\u4e00-\u9fffA-Za-z0-9]{2,14}?)(客户|甲方|业主)(?P<suffix>[A-Za-z0-9甲乙丙丁一二三四五六七八九十]{0,4})",
        normalized,
    )
    if not match:
        return False
    prefix = _clean_entity_name(match.group("prefix"))
    if not prefix:
        return False
    if prefix in _ACCOUNT_PLACEHOLDER_PREFIX_BLACKLIST:
        return False
    if any(prefix.startswith(token) for token in _ACCOUNT_PLACEHOLDER_PREFIX_BLACKLIST):
        return False
    if any(token in prefix for token in ("预算", "采购", "项目", "方案", "窗口", "路径", "打法", "场景", "能力", "商机", "机会")):
        return False
    return True


def _extract_name_from_title(title: str) -> str:
    normalized = _clean_entity_name(title)
    if not normalized:
        return ""
    candidates: list[str] = []
    for splitter in ("_", "|"):
        if splitter in normalized:
            candidates.extend(part for part in normalized.split(splitter) if part)
    candidates.append(normalized)
    for candidate in reversed(candidates):
        candidate = _clean_entity_name(candidate)
        if candidate and _looks_like_org_name(candidate) and not _is_low_signal_entity_name(candidate):
            return candidate
    return ""


def _canonical_name_from_evidence_links(evidence_links: list[dict[str, str]] | None) -> str:
    links = list(evidence_links or [])
    links.sort(key=lambda item: 0 if normalize_text(item.get("source_tier", "")) == "official" else 1)
    for link in links:
        url = normalize_text(link.get("url"))
        domain = urlparse(url).netloc.lower().removeprefix("www.") if url else ""
        for known_domain, canonical_name in _OFFICIAL_DOMAIN_NAME_MAP.items():
            if domain == known_domain or domain.endswith(f".{known_domain}"):
                return canonical_name
        title_candidate = _extract_name_from_title(link.get("title", ""))
        if title_candidate:
            return title_candidate
        label_candidate = _clean_entity_name(link.get("source_label", "").removesuffix("官网").removesuffix("集团官网"))
        if label_candidate and _looks_like_org_name(label_candidate) and not _is_low_signal_entity_name(label_candidate):
            return label_candidate
    return ""


def _graph_entities_for_role(report: ResearchReportDocument, role: str) -> list[Any]:
    graph = report.entity_graph
    if role == "target":
        return list(graph.target_entities) or [entity for entity in graph.entities if _entity_role(entity) == role]
    if role == "competitor":
        return list(graph.competitor_entities) or [entity for entity in graph.entities if _entity_role(entity) == role]
    if role == "partner":
        return list(graph.partner_entities) or [entity for entity in graph.entities if _entity_role(entity) == role]
    return list(graph.entities)


def _graph_entity_quality(entity: Any) -> int:
    canonical_name = _entity_canonical_name(entity)
    source_tier_counts = (entity.get("source_tier_counts") if isinstance(entity, dict) else getattr(entity, "source_tier_counts", {})) or {}
    official_hits = int(source_tier_counts.get("official") or 0)
    source_count = int((entity.get("source_count") if isinstance(entity, dict) else getattr(entity, "source_count", 0)) or 0)
    score = official_hits * 16 + source_count * 6
    score += 12 if _looks_like_org_name(canonical_name) else -12
    score -= 32 if _is_low_signal_entity_name(canonical_name) else 0
    return score


def _best_graph_canonical_name(
    value: str,
    *,
    report: ResearchReportDocument | None,
    role: str,
    evidence_links: list[dict[str, str]] | None = None,
) -> str:
    if report is None:
        return ""
    normalized = _clean_entity_name(value)
    aliases = {normalized.lower()}
    raw_urls = {normalize_text(item.get("url")) for item in (evidence_links or []) if normalize_text(item.get("url"))}
    best_name = ""
    best_score = 0
    for entity in _graph_entities_for_role(report, role):
        canonical_name = _entity_canonical_name(entity)
        if not canonical_name or _is_low_signal_entity_name(canonical_name):
            continue
        entity_aliases = {
            _clean_entity_name(alias).lower()
            for alias in [
                canonical_name,
                *((entity.get("aliases") if isinstance(entity, dict) else getattr(entity, "aliases", [])) or []),
            ]
            if _clean_entity_name(alias)
        }
        entity_urls = {
            normalize_text(link.get("url") if isinstance(link, dict) else getattr(link, "url", ""))
            for link in ((entity.get("evidence_links") if isinstance(entity, dict) else getattr(entity, "evidence_links", [])) or [])
            if normalize_text(link.get("url") if isinstance(link, dict) else getattr(link, "url", ""))
        }
        direct_match = bool(aliases & entity_aliases)
        shared_urls = raw_urls & entity_urls
        if not direct_match and not shared_urls:
            continue
        score = _graph_entity_quality(entity)
        if direct_match:
            score += 28
        if shared_urls:
            score += 22 + len(shared_urls) * 6
        if score > best_score:
            best_score = score
            best_name = canonical_name
    return best_name


def _canonicalize_account_name(
    value: str,
    *,
    report: ResearchReportDocument | None = None,
    role: str = "target",
    evidence_links: list[dict[str, str]] | None = None,
) -> str:
    normalized = _clean_entity_name(value)
    if not normalized:
        return ""
    graph_name = _best_graph_canonical_name(normalized, report=report, role=role, evidence_links=evidence_links)
    if graph_name:
        normalized = graph_name
    else:
        for marker in ("联合相关委办", "联合", "携手", "关于印发", "印发", "解读", "出台", "启用", "启航", "举行", "部署"):
            if marker in normalized:
                prefix = _clean_entity_name(normalized.split(marker, 1)[0])
                if prefix and (_looks_like_org_name(prefix) or len(prefix) <= 14):
                    normalized = prefix
                    break
        for splitter in (":", "|"):
            if splitter in normalized:
                prefix = _clean_entity_name(normalized.split(splitter, 1)[0])
                if prefix:
                    normalized = prefix
                    break
        bracket_match = re.match(r"^(?P<base>[^()]+)\((?P<detail>[^()]+)\)$", normalized)
        if bracket_match:
            base = _clean_entity_name(bracket_match.group("base"))
            detail = _clean_entity_name(bracket_match.group("detail"))
            if base and detail and any(token in detail for token in _ACCOUNT_QUALIFIER_HINTS):
                normalized = base
        if "/" in normalized:
            segments = [_clean_entity_name(part) for part in normalized.split("/") if _clean_entity_name(part)]
            if segments:
                evidence_name = _canonical_name_from_evidence_links(evidence_links)
                if evidence_name and evidence_name in segments:
                    normalized = evidence_name
                else:
                    normalized = segments[0]
        normalized = _ACCOUNT_ALIAS_MAP.get(normalized, normalized)
        if _is_low_signal_entity_name(normalized) or not _looks_like_org_name(normalized):
            evidence_name = _canonical_name_from_evidence_links(evidence_links)
            if evidence_name:
                normalized = _ACCOUNT_ALIAS_MAP.get(evidence_name, evidence_name)
    normalized = _clean_entity_name(normalized)
    if _is_low_signal_entity_name(normalized) or not _looks_like_org_name(normalized):
        return ""
    return normalized


def _is_low_signal_entity_name(value: str) -> bool:
    normalized = _clean_entity_name(value)
    lowered = normalized.lower()
    if not normalized:
        return True
    if _looks_like_sentence_fragment_entity_name(normalized):
        return True
    if normalized in _GENERIC_EXACT_ENTITY_NAMES:
        return True
    if any(normalized.startswith(token) for token in _GENERIC_ENTITY_PREFIXES):
        return True
    if any(token in normalized for token in _GENERIC_ENTITY_CONTAINS):
        return True
    if any(token in lowered for token in ("个人中心", "详情页", "官网首页", "公司简介", "首页", "点击", "阅读原文")):
        return True
    if any(normalized.endswith(token) for token in _GENERIC_ENTITY_SUFFIXES):
        prefix = normalized[: -len(next(token for token in _GENERIC_ENTITY_SUFFIXES if normalized.endswith(token)))]
        if not _looks_like_org_name(prefix):
            return True
    if normalized.endswith(("——", "-", "_")):
        return True
    if normalized.count(":") >= 1 or normalized.count("|") >= 1:
        return True
    if "——" in normalized and not _looks_like_org_name(normalized):
        return True
    if normalized.endswith("观察局"):
        return True
    if normalized.startswith("在") and "举办" in normalized:
        return True
    if normalized.startswith("使") and "数据中心" in normalized:
        return True
    if re.search(r"\d+\s*亿", normalized):
        return True
    if normalized.count("、") >= 2:
        return True
    if any(normalized.startswith(token) for token in ("为", "是", "由", "到", "当前", "建议", "若", "即使", "把", "其中", "由于", "它", "预计", "并且")):
        return True
    if len(normalized) >= 18 and not _looks_like_org_name(normalized):
        return True
    if normalized.endswith("常务会") or normalized.endswith("政策"):
        return True
    if re.search(r"(路径|节奏|打法|策略|商机|机会|窗口|场景|能力)$", normalized) and not _looks_like_org_name(normalized):
        return True
    if re.search(r"(项目|预算|采购|商机|窗口|部署|生态|工具|平台|服务|能力)$", normalized) and not _looks_like_org_name(normalized):
        return True
    if len(normalized) <= 2:
        return True
    return False


def _entity_score(entity: Any) -> int:
    if isinstance(entity, dict):
        return int(entity.get("score") or 0)
    return int(getattr(entity, "score", 0) or 0)


def _entity_reasoning(entity: Any) -> str:
    if isinstance(entity, dict):
        return normalize_text(entity.get("reasoning"))
    return normalize_text(getattr(entity, "reasoning", ""))


def _entity_evidence_links(entity: Any) -> list[dict[str, str]]:
    raw_links = entity.get("evidence_links") if isinstance(entity, dict) else getattr(entity, "evidence_links", [])
    links: list[dict[str, str]] = []
    for raw in raw_links or []:
        title = normalize_text((raw or {}).get("title") if isinstance(raw, dict) else getattr(raw, "title", ""))
        url = normalize_text((raw or {}).get("url") if isinstance(raw, dict) else getattr(raw, "url", ""))
        if not url:
            continue
        links.append(
            {
                "title": title or url,
                "url": url,
                "source_label": normalize_text(
                    (raw or {}).get("source_label") if isinstance(raw, dict) else getattr(raw, "source_label", "")
                ),
                "source_tier": normalize_text(
                    (raw or {}).get("source_tier") if isinstance(raw, dict) else getattr(raw, "source_tier", "")
                )
                or "media",
                "anchor_text": normalize_text(
                    ((raw or {}).get("anchor_text") or "") if isinstance(raw, dict) else (getattr(raw, "anchor_text", "") or "")
                ),
            }
        )
    return links[:4]

