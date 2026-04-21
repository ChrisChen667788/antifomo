from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import re
from collections import defaultdict
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import KnowledgeEntry
from app.models.research_entities import ResearchReportVersion, ResearchWatchlist, ResearchWatchlistChangeEvent
from app.schemas.research import ResearchActionCardOut, ResearchReportDocument
from app.services.content_extractor import normalize_text


settings = get_settings()

_BACKFILL_STAGE_ENTRIES = "entries"
_BACKFILL_STAGE_VERSIONS = "versions"
_BACKFILL_STAGE_DONE = "done"
_BACKFILL_CHECKPOINT_SCHEMA_VERSION = 1

_COMMERCIAL_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_COMMERCIAL_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_COMMERCIAL_IMAGE_LABEL_RE = re.compile(r"^(?:image|图片)\s*\d+$", re.IGNORECASE)
_COMMERCIAL_NOISY_SUBSTRINGS = (
    "官网/公开入口",
    "优先核验公开触达入口",
    "实体归一后命中",
    "其中官方源",
    "微信扫一扫",
    "听全文",
)

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
        return normalize_text(entity.get("name"))
    return normalize_text(getattr(entity, "name", ""))


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


def _looks_like_org_name(value: str) -> bool:
    normalized = _clean_entity_name(value)
    if not normalized:
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
        return list(graph.target_entities or graph.entities)
    if role == "competitor":
        return list(graph.competitor_entities or graph.entities)
    if role == "partner":
        return list(graph.partner_entities or graph.entities)
    return list(graph.entities)


def _graph_entity_quality(entity: Any) -> int:
    canonical_name = _clean_entity_name(getattr(entity, "canonical_name", ""))
    official_hits = int((getattr(entity, "source_tier_counts", {}) or {}).get("official") or 0)
    source_count = int(getattr(entity, "source_count", 0) or 0)
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
        canonical_name = _clean_entity_name(getattr(entity, "canonical_name", ""))
        if not canonical_name or _is_low_signal_entity_name(canonical_name):
            continue
        entity_aliases = {
            _clean_entity_name(alias).lower()
            for alias in [canonical_name, *(getattr(entity, "aliases", []) or [])]
            if _clean_entity_name(alias)
        }
        entity_urls = {
            normalize_text(getattr(link, "url", ""))
            for link in getattr(entity, "evidence_links", []) or []
            if normalize_text(getattr(link, "url", ""))
        }
        score = _graph_entity_quality(entity)
        if aliases & entity_aliases:
            score += 28
        shared_urls = raw_urls & entity_urls
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


def _confidence_score(report: ResearchReportDocument) -> int:
    diagnostics = report.source_diagnostics
    score = 20
    score += min(30, int(report.source_count * 3))
    score += 18 if report.evidence_density == "high" else 10 if report.evidence_density == "medium" else 0
    score += 18 if report.source_quality == "high" else 10 if report.source_quality == "medium" else 0
    score += min(14, int((diagnostics.official_source_ratio or 0) * 30))
    score += min(8, int((diagnostics.unique_domain_count or 0) * 1.5))
    score -= 12 if len(report.top_target_accounts) == 0 and len(report.target_accounts) == 0 else 0
    score -= 8 if len(report.public_contact_channels) == 0 else 0
    return max(5, min(score, 95))


def _confidence_level(score: int) -> str:
    if score >= 78:
        return "high"
    if score >= 56:
        return "medium"
    return "low"


def _budget_probability(report: ResearchReportDocument, *, boost: int = 0) -> int:
    diagnostics = report.source_diagnostics
    probability = 18
    probability += 18 if report.budget_signals else 0
    probability += 14 if report.tender_timeline else 0
    probability += 10 if report.target_departments else 0
    probability += 10 if report.public_contact_channels else 0
    probability += 8 if diagnostics.official_source_ratio >= 0.25 else 3 if diagnostics.official_source_ratio > 0 else 0
    probability += 8 if report.evidence_density == "high" else 4 if report.evidence_density == "medium" else 0
    probability += 6 if report.source_quality == "high" else 3 if report.source_quality == "medium" else 0
    probability += boost
    return max(10, min(probability, 92))


def _maturity_stage(report: ResearchReportDocument) -> str:
    score = 0
    score += 1 if report.strategic_directions else 0
    score += 1 if report.target_departments else 0
    score += 1 if report.budget_signals else 0
    score += 1 if report.tender_timeline else 0
    score += 1 if report.public_contact_channels else 0
    if score >= 5:
        return "scaling"
    if score >= 3:
        return "piloting"
    if score >= 2:
        return "discovering"
    return "early"


def _maturity_dimensions(report: ResearchReportDocument) -> list[dict[str, str]]:
    return [
        {
            "name": "需求清晰度",
            "level": "high" if report.strategic_directions else "medium" if report.executive_summary else "low",
            "note": report.strategic_directions[0] if report.strategic_directions else "当前仍需进一步确认核心场景与目标。",
        },
        {
            "name": "预算与采购",
            "level": "high" if report.budget_signals and report.tender_timeline else "medium" if (report.budget_signals or report.tender_timeline) else "low",
            "note": (report.budget_signals + report.tender_timeline)[0]
            if (report.budget_signals or report.tender_timeline)
            else "尚未形成明确预算窗口或采购节奏。",
        },
        {
            "name": "组织进入度",
            "level": "high" if report.target_departments and report.public_contact_channels else "medium" if (report.target_departments or report.public_contact_channels) else "low",
            "note": (report.target_departments + report.public_contact_channels)[0]
            if (report.target_departments or report.public_contact_channels)
            else "仍缺少明确部门和公开联系入口。",
        },
        {
            "name": "生态成熟度",
            "level": "high" if report.ecosystem_partners else "medium" if report.benchmark_cases else "low",
            "note": (report.ecosystem_partners + report.benchmark_cases)[0]
            if (report.ecosystem_partners or report.benchmark_cases)
            else "当前生态伙伴与标杆案例仍偏少。",
        },
    ]


def _build_methodology(report: ResearchReportDocument) -> dict[str, Any]:
    diagnostics = report.source_diagnostics
    scope_bits = _unique_strings(
        [
            report.keyword,
            report.research_focus or "",
            diagnostics.strategy_scope_summary or "",
            " / ".join(diagnostics.scope_regions),
            " / ".join(diagnostics.scope_industries),
        ],
        limit=4,
    )
    return {
        "scope_summary": "；".join(scope_bits),
        "pipeline_summary": diagnostics.pipeline_summary
        or "取数 -> 清洗 -> 分析",
        "query_plan": list(report.query_plan[:6]),
        "data_boundary": "仅使用公开网页、公告、政策、新闻、企业官网与公开披露数据；付费库和未授权后台不纳入。",
        "retained_source_count": diagnostics.retained_source_count or report.source_count,
        "unique_domain_count": diagnostics.unique_domain_count or len({item.domain for item in report.sources if item.domain}),
        "matched_source_labels": list(diagnostics.matched_source_labels[:6]),
        "matched_theme_labels": list(diagnostics.matched_theme_labels[:6]),
    }


def _build_confidence(report: ResearchReportDocument) -> dict[str, Any]:
    diagnostics = report.source_diagnostics
    score = _confidence_score(report)
    reasons = _unique_strings(
        [
            f"来源数 {report.source_count}，覆盖 {diagnostics.unique_domain_count or len({item.domain for item in report.sources if item.domain})} 个域名。",
            f"官方源占比 {round((diagnostics.official_source_ratio or 0) * 100)}%。",
            "已有预算/招采线索。" if report.budget_signals else "",
            "已识别部门与公开联系入口。" if report.target_departments or report.public_contact_channels else "",
            diagnostics.pipeline_summary,
        ],
        limit=5,
    )
    concerns = _unique_strings(
        [
            "目标账户仍不足，结果更适合做候选名单而非直接推进。" if not report.top_target_accounts and not report.target_accounts else "",
            "公开联系入口不足，销售落地仍需补采。"
            if not report.public_contact_channels
            else "",
            "官方源占比偏低，建议继续补证。"
            if diagnostics.official_source_ratio < 0.2
            else "",
            "证据密度仍偏弱。"
            if report.evidence_density == "low"
            else "",
        ],
        limit=5,
    )
    return {
        "level": _confidence_level(score),
        "score": score,
        "source_count": report.source_count,
        "official_source_ratio": diagnostics.official_source_ratio,
        "evidence_density": report.evidence_density,
        "source_quality": report.source_quality,
        "reasons": reasons,
        "concerns": concerns,
    }


def _build_coverage_gaps(report: ResearchReportDocument) -> list[dict[str, str]]:
    diagnostics = report.source_diagnostics
    gaps: list[dict[str, str]] = []
    if report.source_count < 4:
        gaps.append(
            {
                "title": "来源覆盖不足",
                "severity": "high",
                "detail": "当前可用来源偏少，报告更适合作为问题定义而非最终判断。",
                "recommended_action": "继续补行业媒体、公告、企业官网和政策源，至少补到 6-8 条有效来源。",
            }
        )
    if diagnostics.official_source_ratio < 0.2:
        gaps.append(
            {
                "title": "官方源偏少",
                "severity": "medium",
                "detail": "当前官方源占比不足，容易让预算和组织判断失真。",
                "recommended_action": "优先补官网、公告、政策、投资者关系或招采来源。",
            }
        )
    if not report.top_target_accounts and not report.target_accounts:
        gaps.append(
            {
                "title": "甲方对象不够具体",
                "severity": "high",
                "detail": "当前还没有稳定的具体甲方对象，商业动作容易泛化。",
                "recommended_action": "先把行业判断拆成具体公司、机构或园区，再生成行动卡。",
            }
        )
    if not report.public_contact_channels:
        gaps.append(
            {
                "title": "缺少公开触达入口",
                "severity": "medium",
                "detail": "即使方向正确，也还不能直接进入外联或建联阶段。",
                "recommended_action": "补官网联系我们、采购联系人、IR 邮箱或公开渠道负责人。",
            }
        )
    if not report.benchmark_cases:
        gaps.append(
            {
                "title": "缺少标杆案例",
                "severity": "low",
                "detail": "缺少可对标案例时，客户教育和方案说服力会下降。",
                "recommended_action": "补同类平台、同区域或同场景的落地案例与生态打法。",
            }
        )
    return gaps[:4]


def _match_action_cards_for_account(
    account_name: str,
    action_cards: list[ResearchActionCardOut],
) -> list[ResearchActionCardOut]:
    normalized_name = normalize_text(account_name)
    direct_matches = [
        card
        for card in action_cards
        if normalized_name and (
            normalized_name in normalize_text(card.title)
            or normalized_name in normalize_text(card.summary)
            or any(normalized_name in normalize_text(step) for step in card.recommended_steps)
        )
    ]
    return direct_matches or action_cards[:2]


def _fallback_entities(values: list[str], role: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    base_score = {"target": 66, "competitor": 61, "partner": 58}.get(role, 56)
    for index, value in enumerate(_unique_strings(values, limit=3)):
        items.append(
            {
                "name": value,
                "score": max(40, base_score - index * 7),
                "reasoning": "当前主要基于显性主题命中与检索候选生成，仍建议继续补更多正式证据。",
                "evidence_links": [],
            }
        )
    return items


def _graph_candidate_entities(report: ResearchReportDocument, role: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for entity in _graph_entities_for_role(report, role):
        canonical_name = _clean_entity_name(getattr(entity, "canonical_name", ""))
        if not canonical_name or _is_low_signal_entity_name(canonical_name):
            continue
        source_count = int(getattr(entity, "source_count", 0) or 0)
        official_hits = int((getattr(entity, "source_tier_counts", {}) or {}).get("official") or 0)
        candidates.append(
            {
                "name": canonical_name,
                "score": max(42, min(98, _graph_entity_quality(entity))),
                "reasoning": f"实体归一后命中 {source_count} 条来源，其中官方源 {official_hits} 条。",
                "evidence_links": [link.model_dump(mode="json") for link in getattr(entity, "evidence_links", [])[:4]],
            }
        )
    candidates.sort(key=lambda item: int(item.get("score") or 0), reverse=True)
    return candidates[:6]


def _build_account_snapshots(
    report: ResearchReportDocument,
    action_cards: list[ResearchActionCardOut],
) -> list[dict[str, Any]]:
    targets = [*_graph_candidate_entities(report, "target"), *(report.top_target_accounts or _fallback_entities(report.target_accounts, "target"))]
    competitors = [*_graph_candidate_entities(report, "competitor"), *(report.top_competitors or _fallback_entities(report.competitor_profiles, "competitor"))]
    partners = [*_graph_candidate_entities(report, "partner"), *(report.top_ecosystem_partners or _fallback_entities(report.ecosystem_partners, "partner"))]
    items: list[dict[str, Any]] = []

    for role, source_entities in (("target", targets), ("competitor", competitors[:2]), ("partner", partners[:2])):
        role_items: dict[str, dict[str, Any]] = {}
        for entity in source_entities[:8]:
            evidence_links = _entity_evidence_links(entity)
            name = _canonicalize_account_name(
                _entity_name(entity),
                report=report,
                role=role,
                evidence_links=evidence_links,
            )
            if _is_low_signal_entity_name(name):
                continue
            entity_score = _entity_score(entity)
            matched_cards = _match_action_cards_for_account(name, action_cards)
            slug = _slugify(name)
            candidate = {
                "slug": slug,
                "name": name,
                "role": role,
                "priority": "high" if entity_score >= 75 else "medium" if entity_score >= 55 else "low",
                "confidence_score": max(35, min(95, entity_score if entity_score else _confidence_score(report))),
                "summary": _entity_reasoning(entity)
                or f"{name} 当前已进入 {report.keyword} 的重点观察名单，适合继续做账户拆解与商机验证。",
                "why_now": _clean_commercial_rows(
                    [
                        *(report.budget_signals[:1] if role == "target" else []),
                        *(report.tender_timeline[:1] if role == "target" else []),
                        *(report.client_peer_moves[:1] if role == "target" else []),
                        _entity_reasoning(entity),
                    ],
                    limit=3,
                ),
                "departments": list(report.target_departments[:4]) if role == "target" else [],
                "contacts": list(report.public_contact_channels[:3]) if role == "target" else [],
                "signals": _clean_commercial_rows(
                    [
                        *(report.account_team_signals[:2] if role == "target" else []),
                        *(report.competition_analysis[:1] if role == "competitor" else []),
                        *(report.ecosystem_partners[:1] if role == "partner" else []),
                    ],
                    limit=3,
                ),
                "benchmark_cases": _clean_commercial_rows(report.benchmark_cases[:3], limit=3, max_length=56),
                "next_best_action": _clean_commercial_phrase(matched_cards[0].recommended_steps[0], max_clauses=1, max_length=68)
                if matched_cards and matched_cards[0].recommended_steps
                else "先补组织、预算与联系人，再决定是否进入深入方案阶段。",
                "maturity_stage": _maturity_stage(report),
                "budget_probability": _budget_probability(report, boost=4 if role == "target" else -8),
                "evidence_links": evidence_links,
            }
            existing = role_items.get(slug)
            if existing is None:
                role_items[slug] = candidate
                continue
            existing["confidence_score"] = max(existing["confidence_score"], candidate["confidence_score"])
            existing["budget_probability"] = max(existing["budget_probability"], candidate["budget_probability"])
            existing["priority"] = "high" if existing["confidence_score"] >= 75 else "medium" if existing["confidence_score"] >= 55 else "low"
            existing["why_now"] = _unique_strings([*existing["why_now"], *candidate["why_now"]], limit=4)
            existing["signals"] = _unique_strings([*existing["signals"], *candidate["signals"]], limit=4)
            existing["benchmark_cases"] = _unique_strings([*existing["benchmark_cases"], *candidate["benchmark_cases"]], limit=4)
            existing["contacts"] = _unique_strings([*existing["contacts"], *candidate["contacts"]], limit=4)
            existing["departments"] = _unique_strings([*existing["departments"], *candidate["departments"]], limit=4)
            existing["evidence_links"] = existing["evidence_links"] or candidate["evidence_links"]
        items.extend(
            sorted(
                role_items.values(),
                key=lambda item: (int(item["confidence_score"]), int(item["budget_probability"])),
                reverse=True,
            )[:3]
        )
    return items


def _opportunity_identity_key(opportunity: dict[str, Any]) -> str:
    account_slug = _slugify(str(opportunity.get("account_slug") or opportunity.get("account_name") or ""))
    title = normalize_text(str(opportunity.get("title") or ""))
    title = re.sub(r"^[^｜|]+[｜|]", "", title)
    title = re.sub(r"20\d{2}年?", "", title)
    title = title.replace("进入窗口", "").strip(" |-")
    action = normalize_text(str(opportunity.get("next_best_action") or ""))
    return "|".join(
        [
            account_slug,
            _slugify(title[:40]),
            _slugify(action[:48] or normalize_text(str(opportunity.get("entry_window") or ""))[:32]),
        ]
    )


def _build_opportunities(
    report: ResearchReportDocument,
    accounts: list[dict[str, Any]],
    action_cards: list[ResearchActionCardOut],
) -> list[dict[str, Any]]:
    opportunities: dict[str, dict[str, Any]] = {}
    entry_window = report.tender_timeline[0] if report.tender_timeline else "未来 1-2 个季度内建议持续观察预算与招采窗口。"
    benchmark_case = report.benchmark_cases[0] if report.benchmark_cases else ""
    risk_flags = _unique_strings(
        [
            "官方源不足" if report.source_diagnostics.official_source_ratio < 0.2 else "",
            "缺少公开联系人" if not report.public_contact_channels else "",
            "预算窗口仍需验证" if not report.budget_signals else "",
        ],
        limit=3,
    )
    for account in [item for item in accounts if item["role"] == "target"][:3]:
        matched_cards = _match_action_cards_for_account(account["name"], action_cards)
        score = max(42, min(96, int(account["confidence_score"] * 0.55 + account["budget_probability"] * 0.45)))
        opportunity = {
            "title": f"{account['name']}｜{report.keyword[:18]} 进入窗口",
            "account_slug": account["slug"],
            "account_name": account["name"],
            "stage": _maturity_stage(report),
            "score": score,
            "confidence_label": "高把握" if score >= 75 else "中等把握" if score >= 55 else "待验证",
            "budget_probability": account["budget_probability"],
            "entry_window": _clean_commercial_phrase(entry_window, max_clauses=1, max_length=64),
            "next_best_action": _clean_commercial_phrase(str(account["next_best_action"] or ""), max_clauses=1, max_length=68),
            "why_now": _clean_commercial_rows(account["why_now"] + report.strategic_directions[:1], limit=3, max_length=64),
            "risk_flags": risk_flags,
            "benchmark_case": _clean_commercial_phrase(benchmark_case, max_clauses=1, max_length=56),
            "related_action_titles": [card.title for card in matched_cards[:2]],
        }
        opportunities[_opportunity_identity_key(opportunity)] = opportunity
    return list(opportunities.values())


def _build_benchmark_card(report: ResearchReportDocument) -> dict[str, Any]:
    cases = _unique_strings(report.benchmark_cases, limit=4)
    comparators = _unique_strings(report.flagship_products + report.winner_peer_moves, limit=4)
    if cases:
        summary = f"当前已抽取 {len(cases)} 条可对标案例，可用于客户教育、方案说服和竞品对照。"
    else:
        summary = "当前标杆案例仍偏少，建议补充同区域、同类型或同采购路径的成功样本。"
    return {
        "summary": summary,
        "cases": cases,
        "comparators": comparators,
    }


def _build_maturity_assessment(report: ResearchReportDocument) -> dict[str, Any]:
    dimensions = _maturity_dimensions(report)
    score = sum(18 if item["level"] == "high" else 11 if item["level"] == "medium" else 5 for item in dimensions)
    return {
        "stage": _maturity_stage(report),
        "score": min(score, 92),
        "summary": "从需求清晰度、预算采购、组织进入度和生态成熟度四个维度评估当前商机成熟度。",
        "dimensions": dimensions,
    }


def build_report_knowledge_intelligence(
    report: ResearchReportDocument,
    *,
    action_cards: list[ResearchActionCardOut] | None = None,
) -> dict[str, Any]:
    cards = list(action_cards or [])
    accounts = _build_account_snapshots(report, cards)
    opportunities = _build_opportunities(report, accounts, cards)
    benchmark = _build_benchmark_card(report)
    maturity = _build_maturity_assessment(report)
    return {
        "schema_version": 10,
        "methodology": _build_methodology(report),
        "confidence": _build_confidence(report),
        "coverage_gaps": _build_coverage_gaps(report),
        "accounts": accounts,
        "opportunities": opportunities,
        "benchmark": benchmark,
        "maturity": maturity,
        "why_now": _unique_strings(
            [
                *(report.budget_signals[:2]),
                *(report.tender_timeline[:1]),
                *(report.client_peer_moves[:1]),
                *(report.strategic_directions[:1]),
            ],
            limit=4,
        ),
        "next_steps": _unique_strings(
            [
                *(cards[0].recommended_steps[:2] if cards else []),
                "把高价值甲方、预算窗口和联系人回写到账户页，形成连续跟踪。",
                "对高风险结论补官方源与标杆案例，再进入方案设计。",
            ],
            limit=4,
        ),
    }


def build_research_report_metadata(
    report: ResearchReportDocument,
    *,
    action_cards: list[ResearchActionCardOut] | None = None,
    tracking_topic_id: str | None = None,
) -> dict[str, Any]:
    cards = list(action_cards or [])
    enriched_report = report
    try:
        from app.services import research_service

        base_report = report if isinstance(report, research_service.ResearchReportResponse) else research_service.ResearchReportResponse(
            **report.model_dump(mode="python"),
            generated_at=getattr(report, "generated_at", None) or datetime.now(timezone.utc),
        )
        enriched_report = research_service._enrich_report_for_delivery(base_report)
    except Exception:
        enriched_report = report
    payload: dict[str, Any] = {
        "kind": "research_report",
        "report": enriched_report.model_dump(mode="json"),
        "action_cards": [card.model_dump(mode="json") for card in cards],
        "commercial_intelligence": build_report_knowledge_intelligence(enriched_report, action_cards=cards),
    }
    if tracking_topic_id:
        payload["tracking_topic_id"] = tracking_topic_id
    return payload


def _normalize_review_queue_resolutions(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}
    raw = payload.get("review_queue_resolutions")
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for review_id, resolution in raw.items():
        if not isinstance(review_id, str) or not isinstance(resolution, dict):
            continue
        status = normalize_text(str(resolution.get("resolution_status") or "open")).lower()
        if status not in {"open", "resolved", "deferred"}:
            status = "open"
        resolved_at = resolution.get("resolved_at")
        normalized[review_id] = {
            "resolution_status": status,
            "resolution_note": normalize_text(str(resolution.get("resolution_note") or "")),
            "resolved_at": resolved_at if isinstance(resolved_at, str) and resolved_at else None,
        }
    return normalized


def apply_review_queue_resolutions(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return payload
    report_payload = payload.get("report")
    if not isinstance(report_payload, dict):
        return payload
    raw_queue = report_payload.get("review_queue")
    if not isinstance(raw_queue, list):
        return payload

    resolutions = _normalize_review_queue_resolutions(payload)
    updated_queue: list[dict[str, Any]] = []
    for raw_item in raw_queue:
        if not isinstance(raw_item, dict):
            continue
        review_id = normalize_text(str(raw_item.get("id") or ""))
        resolution = resolutions.get(review_id, {})
        updated_item = dict(raw_item)
        updated_item["resolution_status"] = resolution.get("resolution_status") or "open"
        updated_item["resolution_note"] = resolution.get("resolution_note") or ""
        updated_item["resolved_at"] = resolution.get("resolved_at")
        updated_queue.append(updated_item)

    cloned_payload = dict(payload)
    cloned_report = dict(report_payload)
    cloned_report["review_queue"] = updated_queue
    cloned_payload["report"] = cloned_report
    return cloned_payload


def update_review_queue_resolution(
    payload: dict[str, Any] | None,
    *,
    review_id: str,
    action: str,
    note: str | None = None,
) -> dict[str, Any]:
    cloned_payload = dict(payload) if isinstance(payload, dict) else {}
    normalized_id = normalize_text(review_id)
    if not normalized_id:
        return cloned_payload

    resolutions = _normalize_review_queue_resolutions(cloned_payload)
    normalized_action = normalize_text(action).lower()
    if normalized_action not in {"open", "resolved", "deferred"}:
        normalized_action = "open"

    if normalized_action == "open":
        resolutions.pop(normalized_id, None)
    else:
        resolutions[normalized_id] = {
            "resolution_status": normalized_action,
            "resolution_note": normalize_text(note or ""),
            "resolved_at": datetime.now(timezone.utc).isoformat() if normalized_action == "resolved" else None,
        }

    if resolutions:
        cloned_payload["review_queue_resolutions"] = resolutions
    else:
        cloned_payload.pop("review_queue_resolutions", None)
    return apply_review_queue_resolutions(cloned_payload) or cloned_payload


def extract_commercial_intelligence(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    intelligence = payload.get("commercial_intelligence")
    if isinstance(intelligence, dict):
        return intelligence
    return None


def _load_research_report_entry_batch(
    db: Session,
    *,
    after_created_at: datetime | None = None,
    seen_ids_at_created_at: list[UUID] | None = None,
    limit: int = 20,
) -> list[KnowledgeEntry]:
    stmt = (
        select(KnowledgeEntry)
        .where(KnowledgeEntry.user_id == settings.single_user_id)
        .where(KnowledgeEntry.source_domain == "research.report")
        .order_by(KnowledgeEntry.created_at.asc(), KnowledgeEntry.id.asc())
        .limit(limit)
    )
    if after_created_at is not None:
        timestamp_filter = KnowledgeEntry.created_at > after_created_at
        if seen_ids_at_created_at:
            timestamp_filter = or_(
                timestamp_filter,
                and_(
                    KnowledgeEntry.created_at == after_created_at,
                    KnowledgeEntry.id.not_in(seen_ids_at_created_at),
                ),
            )
        stmt = stmt.where(timestamp_filter)
    return list(db.scalars(stmt))


def _load_research_report_version_batch(
    db: Session,
    *,
    after_created_at: datetime | None = None,
    seen_ids_at_created_at: list[UUID] | None = None,
    limit: int = 20,
) -> list[ResearchReportVersion]:
    stmt = (
        select(ResearchReportVersion)
        .order_by(ResearchReportVersion.created_at.asc(), ResearchReportVersion.id.asc())
        .limit(limit)
    )
    if after_created_at is not None:
        timestamp_filter = ResearchReportVersion.created_at > after_created_at
        if seen_ids_at_created_at:
            timestamp_filter = or_(
                timestamp_filter,
                and_(
                    ResearchReportVersion.created_at == after_created_at,
                    ResearchReportVersion.id.not_in(seen_ids_at_created_at),
                ),
            )
        stmt = stmt.where(timestamp_filter)
    return list(db.scalars(stmt))


def _load_research_report_entries(db: Session) -> list[KnowledgeEntry]:
    return list(
        db.scalars(
            select(KnowledgeEntry)
            .where(KnowledgeEntry.user_id == settings.single_user_id)
            .where(KnowledgeEntry.source_domain == "research.report")
            .order_by(desc(KnowledgeEntry.updated_at), desc(KnowledgeEntry.created_at))
        )
    )


def _load_research_report_versions(db: Session) -> list[ResearchReportVersion]:
    return list(
        db.scalars(
            select(ResearchReportVersion).order_by(desc(ResearchReportVersion.created_at))
        )
    )


def _new_backfill_stage_state() -> dict[str, Any]:
    return {
        "offset": 0,
        "last_created_at": None,
        "last_id": None,
        "seen_ids_at_created_at": [],
        "scanned": 0,
        "updated": 0,
    }


def _new_research_report_backfill_state(
    *,
    batch_size: int,
    commit_every: int,
) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": _BACKFILL_CHECKPOINT_SCHEMA_VERSION,
        "stage": _BACKFILL_STAGE_ENTRIES,
        "batch_size": batch_size,
        "commit_every": commit_every,
        "commits": 0,
        "started_at": timestamp,
        "updated_at": timestamp,
        "completed_at": None,
        _BACKFILL_STAGE_ENTRIES: _new_backfill_stage_state(),
        _BACKFILL_STAGE_VERSIONS: _new_backfill_stage_state(),
    }


def _coerce_research_report_backfill_state(
    raw_state: dict[str, Any] | None,
    *,
    batch_size: int,
    commit_every: int,
) -> dict[str, Any]:
    state = _new_research_report_backfill_state(batch_size=batch_size, commit_every=commit_every)
    if not isinstance(raw_state, dict):
        return state
    state["schema_version"] = int(raw_state.get("schema_version") or _BACKFILL_CHECKPOINT_SCHEMA_VERSION)
    stage = normalize_text(str(raw_state.get("stage") or ""))
    if stage in {_BACKFILL_STAGE_ENTRIES, _BACKFILL_STAGE_VERSIONS, _BACKFILL_STAGE_DONE}:
        state["stage"] = stage
    state["commits"] = int(raw_state.get("commits") or 0)
    state["started_at"] = normalize_text(str(raw_state.get("started_at") or "")) or state["started_at"]
    state["updated_at"] = normalize_text(str(raw_state.get("updated_at") or "")) or state["updated_at"]
    state["completed_at"] = normalize_text(str(raw_state.get("completed_at") or "")) or None
    for stage_name in (_BACKFILL_STAGE_ENTRIES, _BACKFILL_STAGE_VERSIONS):
        stage_state = raw_state.get(stage_name)
        if not isinstance(stage_state, dict):
            continue
        coerced = state[stage_name]
        coerced["offset"] = int(stage_state.get("offset") or 0)
        coerced["last_created_at"] = normalize_text(str(stage_state.get("last_created_at") or "")) or None
        coerced["last_id"] = normalize_text(str(stage_state.get("last_id") or "")) or None
        seen_ids = stage_state.get("seen_ids_at_created_at")
        if isinstance(seen_ids, list):
            coerced["seen_ids_at_created_at"] = [
                normalize_text(str(item or ""))
                for item in seen_ids
                if normalize_text(str(item or ""))
            ]
        coerced["scanned"] = int(stage_state.get("scanned") or 0)
        coerced["updated"] = int(stage_state.get("updated") or 0)
    return state


def _load_research_report_backfill_state(
    checkpoint_path: str | Path | None,
    *,
    batch_size: int,
    commit_every: int,
    resume: bool,
) -> tuple[dict[str, Any], Path | None]:
    if checkpoint_path is None:
        return _new_research_report_backfill_state(batch_size=batch_size, commit_every=commit_every), None
    path = Path(checkpoint_path).expanduser()
    if resume and path.exists():
        try:
            raw_state = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            raw_state = None
        return _coerce_research_report_backfill_state(
            raw_state,
            batch_size=batch_size,
            commit_every=commit_every,
        ), path
    return _new_research_report_backfill_state(batch_size=batch_size, commit_every=commit_every), path


def _write_research_report_backfill_state(state: dict[str, Any], checkpoint_path: Path | None) -> None:
    if checkpoint_path is None:
        return
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True)
    tmp_path = checkpoint_path.with_suffix(f"{checkpoint_path.suffix}.tmp")
    tmp_path.write_text(payload, encoding="utf-8")
    tmp_path.replace(checkpoint_path)


def _parse_backfill_uuid(value: str | None) -> UUID | None:
    normalized = normalize_text(value or "")
    if not normalized:
        return None
    try:
        return UUID(normalized)
    except (TypeError, ValueError):
        return None


def _update_backfill_stage_progress(
    state: dict[str, Any],
    *,
    stage_name: str,
    offset: int,
    cursor_created_at: datetime | None,
    cursor_id: UUID | None,
    seen_ids_at_created_at: list[UUID],
    scanned: int,
    updated: int,
) -> None:
    stage_state = state.setdefault(stage_name, _new_backfill_stage_state())
    stage_state["offset"] = int(offset)
    stage_state["last_created_at"] = cursor_created_at.isoformat() if cursor_created_at is not None else None
    stage_state["last_id"] = str(cursor_id) if cursor_id is not None else None
    stage_state["seen_ids_at_created_at"] = [str(item) for item in seen_ids_at_created_at]
    stage_state["scanned"] = int(scanned)
    stage_state["updated"] = int(updated)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()


def _commit_research_report_backfill_progress(
    db: Session,
    *,
    state: dict[str, Any],
    checkpoint_path: Path | None,
    stage_name: str,
    offset: int,
    cursor_created_at: datetime | None,
    cursor_id: UUID | None,
    seen_ids_at_created_at: list[UUID],
    scanned: int,
    updated: int,
) -> None:
    db.commit()
    state["commits"] = int(state.get("commits") or 0) + 1
    state["stage"] = stage_name
    _update_backfill_stage_progress(
        state,
        stage_name=stage_name,
        offset=offset,
        cursor_created_at=cursor_created_at,
        cursor_id=cursor_id,
        seen_ids_at_created_at=seen_ids_at_created_at,
        scanned=scanned,
        updated=updated,
    )
    _write_research_report_backfill_state(state, checkpoint_path)
    db.expire_all()


def _parse_backfill_uuid_list(values: Any) -> list[UUID]:
    if not isinstance(values, list):
        return []
    parsed: list[UUID] = []
    for value in values:
        parsed_value = _parse_backfill_uuid(str(value) if value is not None else None)
        if parsed_value is not None:
            parsed.append(parsed_value)
    return parsed


def _load_research_report_entry_ids(db: Session) -> list[UUID]:
    return list(
        db.scalars(
            select(KnowledgeEntry.id)
            .where(KnowledgeEntry.user_id == settings.single_user_id)
            .where(KnowledgeEntry.source_domain == "research.report")
            .order_by(KnowledgeEntry.created_at.asc(), KnowledgeEntry.id.asc())
        )
    )


def _load_research_report_version_ids(db: Session) -> list[UUID]:
    return list(
        db.scalars(
            select(ResearchReportVersion.id).order_by(ResearchReportVersion.created_at.asc(), ResearchReportVersion.id.asc())
        )
    )


def _load_research_report_entries_by_ids(db: Session, entry_ids: list[UUID]) -> list[KnowledgeEntry]:
    if not entry_ids:
        return []
    rows = list(db.scalars(select(KnowledgeEntry).where(KnowledgeEntry.id.in_(entry_ids))))
    row_map = {row.id: row for row in rows}
    return [row_map[row_id] for row_id in entry_ids if row_id in row_map]


def _load_research_report_versions_by_ids(db: Session, version_ids: list[UUID]) -> list[ResearchReportVersion]:
    if not version_ids:
        return []
    rows = list(db.scalars(select(ResearchReportVersion).where(ResearchReportVersion.id.in_(version_ids))))
    row_map = {row.id: row for row in rows}
    return [row_map[row_id] for row_id in version_ids if row_id in row_map]


def _rewrite_stored_report_payload(
    report_payload: dict[str, Any] | None,
    *,
    tracking_topic_id: str | None = None,
) -> tuple[ResearchReportDocument | None, list[ResearchActionCardOut], dict[str, Any] | None]:
    if not isinstance(report_payload, dict):
        return None, [], None
    try:
        from app.services import research_service

        report = research_service.ResearchReportResponse.model_validate(report_payload)
        rewritten_report = research_service.rewrite_stored_research_report(report)
        action_cards = research_service.build_research_action_cards(rewritten_report)
        payload = build_research_report_metadata(
            rewritten_report,
            action_cards=action_cards,
            tracking_topic_id=tracking_topic_id,
        )
        return rewritten_report, action_cards, payload
    except Exception:
        return None, [], None


def _backfill_research_report_entry(
    db: Session,
    entry: KnowledgeEntry,
    *,
    rewritten_entry_cache: dict[UUID, tuple[ResearchReportDocument, list[ResearchActionCardOut]]],
) -> bool:
    payload = entry.metadata_payload if isinstance(entry.metadata_payload, dict) else {}
    report_payload = payload.get("report") if isinstance(payload.get("report"), dict) else None
    if not isinstance(report_payload, dict):
        return False
    existing_intelligence = payload.get("commercial_intelligence")
    report_has_enrichment = bool(
        isinstance(report_payload, dict)
        and isinstance(report_payload.get("report_readiness"), dict)
        and isinstance(report_payload.get("commercial_summary"), dict)
        and isinstance(report_payload.get("technical_appendix"), dict)
        and isinstance(report_payload.get("review_queue"), list)
    )
    tracking_topic_id = normalize_text(str(payload.get("tracking_topic_id") or "")) or None
    rewritten_report, action_cards, rewritten_payload = _rewrite_stored_report_payload(
        report_payload,
        tracking_topic_id=tracking_topic_id,
    )
    if rewritten_report is None or rewritten_payload is None:
        return False
    if entry.id is not None:
        rewritten_entry_cache[entry.id] = (rewritten_report, action_cards)
    if (
        isinstance(existing_intelligence, dict)
        and int(existing_intelligence.get("schema_version") or 0) >= 10
        and report_has_enrichment
        and rewritten_payload.get("report") == report_payload
    ):
        return False
    updated_payload = {
        **payload,
        "report": rewritten_payload.get("report"),
        "action_cards": rewritten_payload.get("action_cards"),
        "commercial_intelligence": build_report_knowledge_intelligence(rewritten_report, action_cards=action_cards),
    }
    if tracking_topic_id:
        updated_payload["tracking_topic_id"] = tracking_topic_id
    if payload.get("review_queue_resolutions"):
        updated_payload["review_queue_resolutions"] = payload["review_queue_resolutions"]
        updated_payload = apply_review_queue_resolutions(updated_payload) or updated_payload
    entry.title = rewritten_report.report_title
    entry.metadata_payload = updated_payload
    db.add(entry)
    return True


def _backfill_research_report_version(
    db: Session,
    version: ResearchReportVersion,
    *,
    rewritten_entry_cache: dict[UUID, tuple[ResearchReportDocument, list[ResearchActionCardOut]]],
) -> bool:
    cached = rewritten_entry_cache.get(version.knowledge_entry_id) if version.knowledge_entry_id else None
    if cached is not None:
        rewritten_report, action_cards = cached
    else:
        rewritten_report, action_cards, _rewritten_payload = _rewrite_stored_report_payload(version.report_payload)
        if rewritten_report is None:
            return False
    next_title = rewritten_report.report_title
    next_payload = rewritten_report.model_dump(mode="json")
    next_action_cards = [card.model_dump(mode="json") for card in action_cards]
    next_targets = _unique_strings(
        [item.name for item in rewritten_report.top_target_accounts] or list(rewritten_report.target_accounts),
        limit=6,
    )
    next_competitors = _unique_strings(
        [item.name for item in rewritten_report.top_competitors] or list(rewritten_report.competitor_profiles),
        limit=6,
    )
    if (
        version.report_title == next_title
        and version.report_payload == next_payload
        and version.action_cards_payload == next_action_cards
        and int(version.source_count or 0) == int(rewritten_report.source_count or 0)
        and str(version.evidence_density or "low") == str(rewritten_report.evidence_density or "low")
        and str(version.source_quality or "low") == str(rewritten_report.source_quality or "low")
        and list(version.new_targets or []) == next_targets
        and list(version.new_competitors or []) == next_competitors
    ):
        return False
    version.report_title = next_title
    version.report_payload = next_payload
    version.action_cards_payload = next_action_cards
    version.source_count = int(rewritten_report.source_count or 0)
    version.evidence_density = str(rewritten_report.evidence_density or "low")
    version.source_quality = str(rewritten_report.source_quality or "low")
    version.new_targets = next_targets
    version.new_competitors = next_competitors
    if version.topic is not None and version.topic.last_report_version_id == version.id:
        version.topic.last_refresh_new_targets = list(next_targets)
        version.topic.last_refresh_new_competitors = list(next_competitors)
        db.add(version.topic)
    db.add(version)
    return True


def backfill_research_knowledge_intelligence(
    db: Session,
    *,
    batch_size: int = 20,
    commit_every: int | None = None,
    checkpoint_path: str | Path | None = None,
    resume: bool = False,
    max_rows: int | None = None,
) -> dict[str, Any]:
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")
    if commit_every is None:
        commit_every = batch_size
    if commit_every <= 0:
        raise ValueError("commit_every must be greater than 0")
    if max_rows is not None and max_rows <= 0:
        raise ValueError("max_rows must be greater than 0")

    state, resolved_checkpoint_path = _load_research_report_backfill_state(
        checkpoint_path,
        batch_size=batch_size,
        commit_every=commit_every,
        resume=resume,
    )
    state["batch_size"] = batch_size
    state["commit_every"] = commit_every
    state["completed_at"] = state.get("completed_at") if state.get("stage") == _BACKFILL_STAGE_DONE else None
    _write_research_report_backfill_state(state, resolved_checkpoint_path)

    rewritten_entry_cache: dict[UUID, tuple[ResearchReportDocument, list[ResearchActionCardOut]]] = {}
    processed_this_run = 0

    while state.get("stage") != _BACKFILL_STAGE_DONE:
        stage_name = str(state.get("stage") or _BACKFILL_STAGE_ENTRIES)
        if stage_name not in {_BACKFILL_STAGE_ENTRIES, _BACKFILL_STAGE_VERSIONS}:
            stage_name = _BACKFILL_STAGE_ENTRIES
            state["stage"] = stage_name

        stage_state = state.setdefault(stage_name, _new_backfill_stage_state())
        stage_offset = int(stage_state.get("offset") or 0)
        cursor_created_at = _parse_iso_datetime(stage_state.get("last_created_at"))
        cursor_id = _parse_backfill_uuid(stage_state.get("last_id"))
        seen_ids_at_created_at = _parse_backfill_uuid_list(stage_state.get("seen_ids_at_created_at"))
        scanned = int(stage_state.get("scanned") or 0)
        updated = int(stage_state.get("updated") or 0)
        pending_rows = 0
        stage_ids = (
            _load_research_report_entry_ids(db)
            if stage_name == _BACKFILL_STAGE_ENTRIES
            else _load_research_report_version_ids(db)
        )
        stage_total = len(stage_ids)
        if stage_offset > stage_total:
            stage_offset = stage_total
        stage_complete = stage_offset >= stage_total

        while True:
            remaining_budget = None if max_rows is None else max_rows - processed_this_run
            if remaining_budget is not None and remaining_budget <= 0:
                break
            if stage_offset >= stage_total:
                stage_complete = True
                break

            fetch_limit = batch_size
            if remaining_budget is not None:
                fetch_limit = min(fetch_limit, remaining_budget)
            fetch_limit = min(fetch_limit, max(1, commit_every - pending_rows))
            batch_ids = stage_ids[stage_offset : stage_offset + fetch_limit]
            rows = (
                _load_research_report_entries_by_ids(db, batch_ids)
                if stage_name == _BACKFILL_STAGE_ENTRIES
                else _load_research_report_versions_by_ids(db, batch_ids)
            )

            if not rows:
                stage_offset += len(batch_ids)
                scanned += len(batch_ids)
                continue

            for row in rows:
                row_updated = (
                    _backfill_research_report_entry(
                        db,
                        row,
                        rewritten_entry_cache=rewritten_entry_cache,
                    )
                    if stage_name == _BACKFILL_STAGE_ENTRIES
                    else _backfill_research_report_version(
                        db,
                        row,
                        rewritten_entry_cache=rewritten_entry_cache,
                    )
                )
                scanned += 1
                if row_updated:
                    updated += 1
                processed_this_run += 1
                pending_rows += 1
                row_created_at = row.created_at
                row_id = row.id
                if cursor_created_at is None or row_created_at != cursor_created_at:
                    cursor_created_at = row_created_at
                    seen_ids_at_created_at = [row_id]
                else:
                    seen_ids_at_created_at = [*seen_ids_at_created_at, row_id]
                cursor_id = row_id
            stage_offset += len(batch_ids)

            if pending_rows >= commit_every:
                _commit_research_report_backfill_progress(
                    db,
                    state=state,
                    checkpoint_path=resolved_checkpoint_path,
                    stage_name=stage_name,
                    offset=stage_offset,
                    cursor_created_at=cursor_created_at,
                    cursor_id=cursor_id,
                    seen_ids_at_created_at=seen_ids_at_created_at,
                    scanned=scanned,
                    updated=updated,
                )
                pending_rows = 0

        if pending_rows > 0:
            _commit_research_report_backfill_progress(
                db,
                state=state,
                checkpoint_path=resolved_checkpoint_path,
                stage_name=stage_name,
                offset=stage_offset,
                cursor_created_at=cursor_created_at,
                cursor_id=cursor_id,
                seen_ids_at_created_at=seen_ids_at_created_at,
                scanned=scanned,
                updated=updated,
            )
        else:
            _update_backfill_stage_progress(
                state,
                stage_name=stage_name,
                offset=stage_offset,
                cursor_created_at=cursor_created_at,
                cursor_id=cursor_id,
                seen_ids_at_created_at=seen_ids_at_created_at,
                scanned=scanned,
                updated=updated,
            )

        if not stage_complete:
            break

        state["stage"] = _BACKFILL_STAGE_VERSIONS if stage_name == _BACKFILL_STAGE_ENTRIES else _BACKFILL_STAGE_DONE
        if state["stage"] == _BACKFILL_STAGE_DONE:
            state["completed_at"] = datetime.now(timezone.utc).isoformat()
        else:
            state["completed_at"] = None
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        _write_research_report_backfill_state(state, resolved_checkpoint_path)

    return {
        "scanned": int(state[_BACKFILL_STAGE_ENTRIES]["scanned"]),
        "updated": int(state[_BACKFILL_STAGE_ENTRIES]["updated"]),
        "scanned_versions": int(state[_BACKFILL_STAGE_VERSIONS]["scanned"]),
        "updated_versions": int(state[_BACKFILL_STAGE_VERSIONS]["updated"]),
        "processed_this_run": processed_this_run,
        "commits": int(state.get("commits") or 0),
        "completed": state.get("stage") == _BACKFILL_STAGE_DONE,
        "stage": str(state.get("stage") or _BACKFILL_STAGE_ENTRIES),
        "batch_size": batch_size,
        "commit_every": commit_every,
        "checkpoint_path": str(resolved_checkpoint_path) if resolved_checkpoint_path is not None else None,
    }


def _entry_link(entry: KnowledgeEntry) -> dict[str, Any]:
    return {
        "entry_id": entry.id,
        "title": entry.title,
        "source_domain": entry.source_domain,
        "collection_name": entry.collection_name,
        "created_at": entry.created_at,
    }


def _severity_rank(value: str) -> int:
    normalized = normalize_text(value).lower()
    if normalized == "high":
        return 2
    if normalized == "medium":
        return 1
    return 0


def _severity_from_rank(value: int) -> str:
    if value >= 2:
        return "high"
    if value >= 1:
        return "medium"
    return "low"


def _raise_severity(value: str) -> str:
    return _severity_from_rank(min(2, _severity_rank(value) + 1))


def _lower_severity(value: str) -> str:
    return _severity_from_rank(max(0, _severity_rank(value) - 1))


def _parse_iso_datetime(value: str | None) -> datetime | None:
    normalized = normalize_text(value or "")
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None


def _review_status_label(value: str) -> str:
    normalized = normalize_text(value).lower()
    if normalized == "resolved":
        return "已核验"
    if normalized == "deferred":
        return "已延后"
    return "待处理"


def _account_timeline_from_watchlists(db: Session) -> dict[str, list[dict[str, Any]]]:
    timeline_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rows = db.execute(
        select(ResearchWatchlistChangeEvent, ResearchWatchlist.name)
        .join(ResearchWatchlist, ResearchWatchlist.id == ResearchWatchlistChangeEvent.watchlist_id)
        .where(ResearchWatchlist.user_id == settings.single_user_id)
        .order_by(desc(ResearchWatchlistChangeEvent.created_at))
        .limit(120)
    ).all()
    for event, watchlist_name in rows:
        payload = event.payload if isinstance(event.payload, dict) else {}
        candidate_names = _unique_strings(
            [
                *(str(item) for item in payload.get("accounts", []) if str(item).strip()),
                *(str(item) for item in payload.get("targets", []) if str(item).strip()),
            ],
            limit=4,
        )
        if not candidate_names:
            continue
        tags = _unique_strings(
            [
                *(str(item) for item in payload.get("why_now", []) if str(item).strip()),
                *(str(item) for item in payload.get("opportunities", []) if str(item).strip()),
                *(str(item) for item in payload.get("budget_signals", []) if str(item).strip()),
            ],
            limit=4,
        )
        budget_probability = 0
        try:
            budget_probability = int(payload.get("top_budget_probability") or 0)
        except (TypeError, ValueError):
            budget_probability = 0
        next_action = ""
        if tags:
            next_action = tags[0]
        elif budget_probability > 0:
            next_action = f"优先核验预算概率 {budget_probability}% 对应的采购与决策窗口。"
        item = {
            "id": str(event.id),
            "kind": "watchlist",
            "title": event.summary,
            "summary": normalize_text(str(payload.get("report_title") or watchlist_name or event.summary)),
            "severity": event.severity,
            "created_at": event.created_at,
            "watchlist_name": normalize_text(watchlist_name),
            "next_action": next_action,
            "budget_probability": budget_probability,
            "related_entry_id": None,
            "related_watchlist_id": str(event.watchlist_id),
            "tags": tags,
        }
        for raw_name in candidate_names:
            canonical_name = _canonicalize_account_name(raw_name)
            if _is_low_signal_entity_name(canonical_name):
                continue
            slug = _slugify(canonical_name)
            timeline_map[slug].append(item)
    return timeline_map


def _account_timeline_from_review_queue(db: Session) -> dict[str, list[dict[str, Any]]]:
    timeline_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in _load_research_report_entries(db):
        payload = apply_review_queue_resolutions(entry.metadata_payload if isinstance(entry.metadata_payload, dict) else {})
        report_payload = payload.get("report") if isinstance(payload.get("report"), dict) else {}
        raw_queue = report_payload.get("review_queue") if isinstance(report_payload.get("review_queue"), list) else []
        if not raw_queue:
            continue
        intelligence = extract_commercial_intelligence(payload) or {}
        accounts = [
            item
            for item in (intelligence.get("accounts") or [])
            if isinstance(item, dict) and str(item.get("role") or "") == "target"
        ]
        primary_account = accounts[0] if accounts else {}
        canonical_account_name = _canonicalize_account_name(
            str(primary_account.get("name") or primary_account.get("slug") or ""),
            evidence_links=list(primary_account.get("evidence_links") or []),
        )
        if _is_low_signal_entity_name(canonical_account_name):
            continue
        account_slug = _slugify(canonical_account_name)
        for raw in raw_queue[:6]:
            if not isinstance(raw, dict):
                continue
            review_id = normalize_text(str(raw.get("id") or ""))
            if not review_id:
                review_id = f"{entry.id}"
            resolution_status = normalize_text(str(raw.get("resolution_status") or "open")).lower() or "open"
            resolution_note = normalize_text(str(raw.get("resolution_note") or ""))
            created_at = (
                _parse_iso_datetime(raw.get("resolved_at"))
                or entry.updated_at
                or entry.created_at
            )
            severity = normalize_text(str(raw.get("severity") or "medium")).lower() or "medium"
            if resolution_status == "resolved":
                severity = _lower_severity(severity)
            next_action = normalize_text(str(raw.get("recommended_action") or ""))
            if resolution_status == "resolved":
                next_action = resolution_note or "该冲突结论已核验，可回到账户推进链继续执行。"
            elif resolution_status == "deferred":
                next_action = resolution_note or next_action or "当前已延后处理，需在下轮 watchlist 刷新时优先复核。"
            else:
                next_action = next_action or "优先人工或模型二次核验该结论。"
            tags = _unique_strings(
                [
                    _review_status_label(resolution_status),
                    *(str(item) for item in raw.get("missing_axes") or [] if str(item).strip()),
                    *(str(item) for item in raw.get("focus_tags") or [] if str(item).strip()),
                ],
                limit=4,
            )
            timeline_map[account_slug].append(
                {
                    "id": f"review:{entry.id}:{review_id}",
                    "kind": "review_queue",
                    "title": normalize_text(str(raw.get("section_title") or "冲突证据审查")),
                    "summary": normalize_text(str(raw.get("summary") or "")),
                    "severity": severity,
                    "created_at": created_at,
                    "watchlist_name": None,
                    "next_action": next_action,
                    "budget_probability": 0,
                    "related_entry_id": entry.id,
                    "related_watchlist_id": None,
                    "tags": tags,
                    "resolution_status": resolution_status,
                    "resolution_note": resolution_note,
                }
            )
    return timeline_map


def _stakeholder_role_meta(value: str) -> tuple[str, str, str]:
    normalized = normalize_text(value)
    if any(token in normalized for token in ("采购", "招标", "招采", "集采")):
        return "采购/招采 gatekeeper", "需先验证", "high"
    if any(token in normalized for token in ("财务", "预算", "投资")):
        return "预算 owner", "需先验证", "high"
    if any(token in normalized for token in ("信息", "数字化", "科技", "数据")):
        return "数字化 sponsor", "潜在支持者", "high"
    return "业务 sponsor", "潜在支持者", "medium"


def _clean_commercial_phrase(value: str, *, max_clauses: int = 1, max_length: int = 72) -> str:
    text = normalize_text(str(value or ""))
    if not text:
        return ""

    def _replace_link(match: re.Match[str]) -> str:
        label = normalize_text(match.group(1))
        if not label or _COMMERCIAL_IMAGE_LABEL_RE.match(label):
            return ""
        return label

    text = _COMMERCIAL_MARKDOWN_LINK_RE.sub(_replace_link, text)
    text = normalize_text(text).strip("，,、:：- ")
    if not text:
        return ""

    clauses: list[str] = []
    for raw_clause in re.split(r"[；;]", text):
        clause = normalize_text(raw_clause).strip("，,、:：- ")
        if not clause:
            continue
        if any(marker in clause for marker in _COMMERCIAL_NOISY_SUBSTRINGS):
            continue
        if _COMMERCIAL_URL_RE.search(clause):
            clause = _COMMERCIAL_URL_RE.sub("", clause).strip("，,、:：- ")
        if not clause:
            continue
        if "：" in clause:
            _, tail = clause.split("：", 1)
            tail = normalize_text(tail).strip("，,、:：- ")
            if len(tail) >= 8:
                clause = tail
        if _COMMERCIAL_IMAGE_LABEL_RE.match(clause):
            continue
        compact = re.sub(r"[\W_]+", "", clause, flags=re.UNICODE)
        if len(compact) < 6:
            continue
        clauses.append(clause)
        if len(clauses) >= max_clauses:
            break

    cleaned = "；".join(clauses) if clauses else text
    cleaned = _COMMERCIAL_URL_RE.sub("", cleaned).strip("，,、:：- ")
    if len(cleaned) > max_length:
        cleaned = cleaned[: max_length - 1].rstrip("，,、:：- ") + "…"
    return cleaned


def _clean_commercial_rows(values: list[str] | None, *, limit: int = 4, max_length: int = 72) -> list[str]:
    rows: list[str] = []
    for value in values or []:
        cleaned = _clean_commercial_phrase(str(value or ""), max_clauses=1, max_length=max_length)
        if cleaned and cleaned not in rows:
            rows.append(cleaned)
        if len(rows) >= limit:
            break
    return rows


def _build_account_plan(bucket: dict[str, Any]) -> dict[str, Any]:
    relationship_goal = (
        f"把 {bucket['name']} 从公开线索推进到至少 1 位业务 sponsor 和 1 位数字化接口人的明确映射。"
        if bucket.get("departments") or bucket.get("contacts")
        else f"先为 {bucket['name']} 建立组织入口和首轮赞助人映射。"
    )
    value_hypothesis = (
        _clean_commercial_phrase(bucket.get("why_now", [""])[0] if bucket.get("why_now") else "", max_clauses=1, max_length=72)
        or _clean_commercial_phrase(str(bucket.get("latest_signal") or ""), max_clauses=1, max_length=72)
        or f"{bucket['name']} 当前已经出现值得持续跟进的数字化/采购信号。"
    )
    proof_points = _unique_strings(
        _clean_commercial_rows(
            [
                *(bucket.get("signals") or []),
                *(bucket.get("benchmark_cases") or []),
            ],
            limit=4,
        ),
        limit=4,
    )
    return {
        "objective": _clean_commercial_phrase(
            str(bucket.get("next_best_action") or ""),
            max_clauses=1,
            max_length=68,
        ) or f"围绕 {bucket['name']} 收敛预算窗口、组织入口和下一步推进动作。",
        "relationship_goal": relationship_goal,
        "value_hypothesis": value_hypothesis,
        "strategic_wedges": _clean_commercial_rows(
            [
                *(bucket.get("why_now") or []),
                *(bucket.get("benchmark_cases") or []),
                *(bucket.get("signals") or []),
            ],
            limit=4,
        ),
        "proof_points": proof_points,
        "next_meeting_goal": (
            "确认预算归口、项目 owner、进入窗口和可联合推进的伙伴。"
            if bucket.get("budget_probability", 0) >= 60
            else "优先确认是否存在真实项目、预算意向和组织入口。"
        ),
    }


def _build_stakeholder_map(bucket: dict[str, Any]) -> list[dict[str, Any]]:
    stakeholders: list[dict[str, Any]] = []
    evidence_links = list(bucket.get("evidence_links") or [])[:2]
    for department in list(bucket.get("departments") or [])[:4]:
        role, stance, priority = _stakeholder_role_meta(str(department))
        stakeholders.append(
            {
                "name": normalize_text(str(department)),
                "role": role,
                "stance": stance,
                "priority": priority,
                "next_move": (
                    "优先确认该部门是否掌握业务需求、预算归口或技术路线。"
                    if priority == "high"
                    else "继续确认该角色在项目推进中的真实影响力。"
                ),
                "evidence_links": evidence_links,
            }
        )
    for contact in list(bucket.get("contacts") or [])[:2]:
        stakeholders.append(
            {
                "name": normalize_text(str(contact)),
                "role": "公开入口",
                "stance": "可触达",
                "priority": "medium",
                "next_move": "通过该入口确认真实对接人、部门和响应链路。",
                "evidence_links": evidence_links,
            }
        )
    deduped: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for stakeholder in stakeholders:
        name = normalize_text(str(stakeholder.get("name") or ""))
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        deduped.append(stakeholder)
    return deduped[:6]


def _build_pipeline_risks(bucket: dict[str, Any]) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []

    def add_risk(title: str, severity: str, detail: str, mitigation: str) -> None:
        normalized_title = normalize_text(title)
        if not normalized_title:
            return
        if any(existing["title"] == normalized_title for existing in risks):
            return
        risks.append(
            {
                "title": normalized_title,
                "severity": severity,
                "detail": _clean_commercial_phrase(detail, max_clauses=1, max_length=88),
                "mitigation": _clean_commercial_phrase(mitigation, max_clauses=1, max_length=88),
            }
        )

    for raw in list(bucket.get("risks") or [])[:4]:
        text = normalize_text(str(raw))
        if not text:
            continue
        if "官方源" in text:
            add_risk("官方源仍需补强", "high", text, "补官网、公告、政策或采购源，再决定是否升级为强结论。")
        elif "联系人" in text or "联系" in text:
            add_risk("组织入口仍未坐实", "high", text, "优先把公开入口转成部门、角色和真实触达路径。")
        elif "预算" in text or "窗口" in text:
            add_risk("预算窗口仍需复核", "high", text, "补预算归口、招采窗口和期次信息，再进入 close plan。")
        else:
            add_risk("推进条件仍有不确定性", "medium", text, "继续补证并缩小推进范围。")

    if not bucket.get("contacts"):
        add_risk("缺少公开联系人", "high", "当前仍缺少可用的公开联系人或公开组织入口。", "优先核验官网联系页、采购公告联系人和投资者关系入口。")
    if int(bucket.get("budget_probability") or 0) < 55:
        add_risk("预算概率偏低", "medium", "当前预算窗口和采购节奏仍不够清晰。", "继续补预算草案、采购意向和项目节奏。")
    if int(bucket.get("confidence_score") or 0) < 70:
        add_risk("证据强度仍偏弱", "medium", "当前账户结论仍偏候选推进。", "补官方源、标杆案例和账户级证据后再推进。")
    if not bucket.get("benchmark_cases"):
        add_risk("缺少可复用标杆", "low", "当前缺少同类客户或同路径的标杆案例。", "补区域/行业相似案例，增强方案说服力。")
    if not risks:
        add_risk("需持续监控推进信号", "low", "当前账户暂无显性阻塞项，但仍需持续观察预算、组织和竞品变化。", "把 Watchlist 变化、会前简报和下一次 close plan 绑定到同一条推进链。")
    return risks[:4]


def _build_close_plan(bucket: dict[str, Any]) -> list[dict[str, Any]]:
    next_action = _clean_commercial_phrase(str(bucket.get("next_best_action") or ""), max_clauses=1, max_length=72)
    first_department = normalize_text(next(iter(bucket.get("departments") or []), "关键部门"))
    first_benchmark = _clean_commercial_phrase(next(iter(bucket.get("benchmark_cases") or []), "同类标杆案例"), max_clauses=1, max_length=48)
    return [
        {
            "title": "确认业务 sponsor",
            "owner": "BD / 客户经理",
            "due_window": "本周",
            "exit_criteria": f"确认 {first_department or '关键部门'} 是否为真实发起方，并拿到下一次沟通入口。",
        },
        {
            "title": "坐实预算与时间窗口",
            "owner": "销售负责人",
            "due_window": "1-2 周",
            "exit_criteria": "确认预算归口、采购节奏和进入窗口，避免无预算强推进。",
        },
        {
            "title": "绑定方案与伙伴",
            "owner": "售前 / 生态负责人",
            "due_window": "2-3 周",
            "exit_criteria": f"形成与 {first_benchmark or '标杆案例'} 对齐的差异化说法，并确认是否需要伙伴协同。",
        },
        {
            "title": "输出 close plan 交付物",
            "owner": "咨询顾问 / 销售经理",
            "due_window": "3-4 周",
            "exit_criteria": next_action or "沉淀会前简报、关键假设、风险和下一步动作。",
        },
    ]


def _build_review_queue_index(db: Session) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for entry in _load_research_report_entries(db):
        payload = apply_review_queue_resolutions(entry.metadata_payload if isinstance(entry.metadata_payload, dict) else {})
        report_payload = payload.get("report") if isinstance(payload.get("report"), dict) else {}
        raw_queue = report_payload.get("review_queue") if isinstance(report_payload.get("review_queue"), list) else []
        if not raw_queue:
            continue
        intelligence = extract_commercial_intelligence(payload) or {}
        accounts = [
            item
            for item in (intelligence.get("accounts") or [])
            if isinstance(item, dict) and str(item.get("role") or "") == "target"
        ]
        primary_account = accounts[0] if accounts else {}
        account_name = normalize_text(str(primary_account.get("name") or ""))
        account_slug = _slugify(account_name) if account_name else None
        for raw in raw_queue[:6]:
            if not isinstance(raw, dict):
                continue
            resolution_status = normalize_text(str(raw.get("resolution_status") or "open")).lower() or "open"
            if resolution_status == "resolved":
                continue
            items.append(
                {
                    "id": normalize_text(str(raw.get("id") or f"review-{entry.id}")),
                    "severity": normalize_text(str(raw.get("severity") or "medium")) or "medium",
                    "title": normalize_text(str(raw.get("section_title") or "冲突证据审查")),
                    "summary": normalize_text(str(raw.get("summary") or "")),
                    "account_slug": account_slug,
                    "account_name": account_name or None,
                    "related_entry_id": entry.id,
                    "recommended_action": normalize_text(str(raw.get("recommended_action") or "")),
                    "evidence_links": list(raw.get("evidence_links") or [])[:3],
                    "resolution_status": resolution_status,
                    "resolution_note": normalize_text(str(raw.get("resolution_note") or "")),
                    "resolved_at": raw.get("resolved_at"),
                    "created_at": entry.created_at,
                }
            )
    severity_order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda item: (severity_order.get(str(item.get("severity")), 3), -datetime.timestamp(item.get("created_at") or datetime.now(timezone.utc))))
    return items[:12]


def _build_dashboard_alerts(accounts: list[dict[str, Any]], review_queue: list[dict[str, Any]]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []

    def add_alert(item: dict[str, Any]) -> None:
        if any(existing["id"] == item["id"] for existing in alerts):
            return
        alerts.append(item)

    for account in accounts[:10]:
        timeline_items = list(account.get("timeline") or [])
        review_timeline = [item for item in timeline_items if str(item.get("kind") or "") == "review_queue"]
        has_open_review = any(str(item.get("resolution_status") or "open") == "open" for item in review_timeline)
        has_deferred_review = any(str(item.get("resolution_status") or "open") == "deferred" for item in review_timeline)
        has_resolved_review = bool(review_timeline) and not has_open_review and not has_deferred_review
        for risk in list(account.get("pipeline_risks") or [])[:2]:
            if str(risk.get("severity") or "low") not in {"high", "medium"}:
                continue
            add_alert(
                {
                    "id": f"risk-{account['slug']}-{_slugify(str(risk.get('title') or 'risk'))}",
                    "kind": "pipeline_risk",
                    "severity": risk.get("severity") or "medium",
                    "title": str(risk.get("title") or "推进风险"),
                    "summary": str(risk.get("detail") or ""),
                    "account_slug": account["slug"],
                    "account_name": account["name"],
                    "recommended_action": str(risk.get("mitigation") or ""),
                    "created_at": None,
                }
            )
        for timeline_item in timeline_items[:5]:
            if str(timeline_item.get("kind") or "") != "watchlist":
                continue
            if str(timeline_item.get("severity") or "low") not in {"high", "medium"}:
                continue
            severity = str(timeline_item.get("severity") or "medium")
            summary = str(timeline_item.get("summary") or "")
            recommended_action = str(timeline_item.get("next_action") or "优先核验当前变化对账户推进的真实影响。")
            if has_open_review:
                severity = _raise_severity(severity)
                summary = _unique_strings([summary, "当前账户仍有待核验冲突结论，需要先确认变化是否可靠。"])[0:2]
                summary = " ".join(summary).strip()
                recommended_action = f"{recommended_action}；并先关闭待核验冲突结论。"
            elif has_deferred_review:
                severity = _severity_from_rank(max(1, _severity_rank(severity)))
                summary = _unique_strings([summary, "该账户已有延后处理的冲突项，本次变化建议与历史争议一起复核。"])[0:2]
                summary = " ".join(summary).strip()
                recommended_action = f"{recommended_action}；并把已延后审查项一起带回核验。"
            elif has_resolved_review:
                severity = _lower_severity(severity)
                recommended_action = f"{recommended_action}；相关冲突项已核验，可按账户计划继续推进。"
            add_alert(
                {
                    "id": f"watchlist-{timeline_item['id']}",
                    "kind": "watchlist",
                    "severity": severity,
                    "title": timeline_item.get("title") or "Watchlist 变化",
                    "summary": summary,
                    "account_slug": account["slug"],
                    "account_name": account["name"],
                    "recommended_action": recommended_action,
                    "created_at": timeline_item.get("created_at"),
                }
            )
    for item in review_queue[:4]:
        if str(item.get("severity") or "low") not in {"high", "medium"}:
            continue
        add_alert(
            {
                "id": f"review-{item['id']}",
                "kind": "review_queue",
                "severity": item.get("severity") or "medium",
                "title": item.get("title") or "冲突证据待审查",
                "summary": item.get("summary") or "",
                "account_slug": item.get("account_slug"),
                "account_name": item.get("account_name"),
                "recommended_action": item.get("recommended_action") or "优先人工或模型二次核验该结论。",
                "created_at": item.get("created_at"),
            }
        )
    severity_order = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(key=lambda item: (severity_order.get(str(item.get("severity")), 3), -(datetime.timestamp(item.get("created_at") or datetime.now(timezone.utc)) if item.get("created_at") else 0)))
    return alerts[:8]


def _build_role_views(
    accounts: list[dict[str, Any]],
    opportunities: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
    review_queue: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    top_accounts = accounts[:4]
    top_opportunities = opportunities[:4]
    return [
        {
            "key": "bd",
            "label": "BD 视图",
            "summary": "优先看预算概率、组织入口、下一步动作和 close plan。",
            "focus_items": _unique_strings(
                [
                    *(item.get("next_best_action") or "" for item in top_accounts),
                    *(item.get("title") or "" for item in top_opportunities),
                ],
                limit=4,
            ),
            "account_slugs": [item["slug"] for item in top_accounts[:3]],
            "opportunity_titles": [item["title"] for item in top_opportunities[:3]],
        },
        {
            "key": "exec",
            "label": "管理层视图",
            "summary": "优先看高优先级提醒、预算概率高的账户和本周必须拍板的动作。",
            "focus_items": _unique_strings(
                [
                    *(item.get("title") or "" for item in alerts[:3]),
                    *(item.get("name") or "" for item in top_accounts[:2]),
                ],
                limit=4,
            ),
            "account_slugs": [item["slug"] for item in top_accounts[:2]],
            "opportunity_titles": [item["title"] for item in top_opportunities[:2]],
        },
        {
            "key": "consulting",
            "label": "咨询视图",
            "summary": "优先看假设、缺证项、对标案例和冲突审查队列。",
            "focus_items": _unique_strings(
                [
                    *(item.get("summary") or item.get("title") or "" for item in review_queue[:3]),
                    *(value for item in top_accounts[:1] for value in (item.get("benchmark_cases") or [])),
                ],
                limit=4,
            ),
            "account_slugs": [item["slug"] for item in top_accounts[:2]],
            "opportunity_titles": [],
        },
        {
            "key": "delivery",
            "label": "交付视图",
            "summary": "优先看 close plan、风险缓释和下一次会前材料。",
            "focus_items": _unique_strings(
                [
                    *(item.get("next_best_action") or "" for item in top_accounts[:2]),
                    *(item.get("next_best_action") or "" for item in top_opportunities[:2]),
                ],
                limit=4,
            ),
            "account_slugs": [item["slug"] for item in top_accounts[:2]],
            "opportunity_titles": [item["title"] for item in top_opportunities[:2]],
        },
    ]


def _aggregate_accounts(db: Session) -> dict[str, dict[str, Any]]:
    accounts: dict[str, dict[str, Any]] = {}
    seen_opportunity_keys: defaultdict[str, set[str]] = defaultdict(set)
    watchlist_timeline = _account_timeline_from_watchlists(db)
    review_queue_timeline = _account_timeline_from_review_queue(db)
    for entry in _load_research_report_entries(db):
        payload = entry.metadata_payload if isinstance(entry.metadata_payload, dict) else {}
        intelligence = extract_commercial_intelligence(payload)
        if not intelligence:
            continue
        seen_account_slugs_for_entry: set[str] = set()
        for account in intelligence.get("accounts") or []:
            if not isinstance(account, dict) or str(account.get("role") or "") != "target":
                continue
            raw_name = str(account.get("name") or account.get("slug") or "")
            canonical_name = _canonicalize_account_name(
                raw_name,
                evidence_links=list(account.get("evidence_links") or []),
            )
            if _is_low_signal_entity_name(canonical_name):
                continue
            slug = _slugify(canonical_name)
            if not slug:
                continue
            bucket = accounts.setdefault(
                slug,
                {
                    "slug": slug,
                    "name": canonical_name or normalize_text(account.get("name")) or slug,
                    "priority": str(account.get("priority") or "medium"),
                    "report_count": 0,
                    "opportunity_count": 0,
                    "confidence_score": 0,
                    "budget_probability": 0,
                    "maturity_stage": str(account.get("maturity_stage") or ""),
                    "latest_signal": "",
                    "next_best_action": "",
                    "benchmark_cases": [],
                    "related_entry_ids": [],
                    "summary": normalize_text(account.get("summary")),
                    "why_now": [],
                    "contacts": [],
                    "departments": [],
                    "signals": [],
                    "risks": [],
                    "evidence_links": [],
                    "opportunities": [],
                    "related_entries": [],
                    "timeline": [],
                    "account_plan": {},
                    "stakeholder_map": [],
                    "close_plan": [],
                    "pipeline_risks": [],
                },
            )
            if slug not in seen_account_slugs_for_entry:
                bucket["report_count"] += 1
                bucket["related_entry_ids"] = list(dict.fromkeys([*bucket["related_entry_ids"], entry.id]))
                bucket["related_entries"].append(_entry_link(entry))
                bucket["timeline"].append(
                    {
                        "id": f"report:{entry.id}:{slug}",
                        "kind": "report",
                        "title": entry.title,
                        "summary": normalize_text(account.get("summary")) or normalize_text(entry.title),
                        "severity": "medium",
                        "created_at": entry.created_at,
                        "watchlist_name": None,
                        "next_action": normalize_text(account.get("next_best_action")),
                        "budget_probability": int(account.get("budget_probability") or 0),
                        "related_entry_id": entry.id,
                        "related_watchlist_id": None,
                        "tags": _unique_strings(
                            [
                                *(account.get("signals") or []),
                                *(account.get("why_now") or []),
                            ],
                            limit=4,
                        ),
                    }
                )
                seen_account_slugs_for_entry.add(slug)
            bucket["confidence_score"] = max(bucket["confidence_score"], int(account.get("confidence_score") or 0))
            bucket["budget_probability"] = max(bucket["budget_probability"], int(account.get("budget_probability") or 0))
            bucket["priority"] = "high" if bucket["confidence_score"] >= 75 else "medium" if bucket["confidence_score"] >= 55 else "low"
            bucket["maturity_stage"] = bucket["maturity_stage"] or str(account.get("maturity_stage") or "")
            signals = _unique_strings([*bucket["signals"], *(account.get("signals") or [])], limit=8)
            bucket["signals"] = signals
            bucket["latest_signal"] = signals[0] if signals else bucket["latest_signal"]
            bucket["next_best_action"] = bucket["next_best_action"] or normalize_text(account.get("next_best_action"))
            bucket["benchmark_cases"] = _unique_strings(
                [*bucket["benchmark_cases"], *(account.get("benchmark_cases") or [])],
                limit=6,
            )
            bucket["why_now"] = _unique_strings([*bucket["why_now"], *(account.get("why_now") or [])], limit=6)
            bucket["contacts"] = _unique_strings([*bucket["contacts"], *(account.get("contacts") or [])], limit=6)
            bucket["departments"] = _unique_strings([*bucket["departments"], *(account.get("departments") or [])], limit=6)
            bucket["evidence_links"] = bucket["evidence_links"] or list(account.get("evidence_links") or [])[:6]
        for opportunity in intelligence.get("opportunities") or []:
            if not isinstance(opportunity, dict):
                continue
            canonical_account_name = _canonicalize_account_name(str(opportunity.get("account_name") or opportunity.get("account_slug") or ""))
            account_slug = _slugify(canonical_account_name)
            if account_slug not in accounts:
                continue
            bucket = accounts[account_slug]
            normalized_opportunity = {
                **opportunity,
                "account_name": canonical_account_name or opportunity.get("account_name"),
                "account_slug": account_slug,
            }
            opportunity_key = _opportunity_identity_key(normalized_opportunity)
            if opportunity_key in seen_opportunity_keys[account_slug]:
                continue
            seen_opportunity_keys[account_slug].add(opportunity_key)
            bucket["opportunity_count"] += 1
            bucket["opportunities"].append(normalized_opportunity)
            bucket["risks"] = _unique_strings([*bucket["risks"], *(normalized_opportunity.get("risk_flags") or [])], limit=6)
            bucket["timeline"].append(
                {
                    "id": f"opportunity:{entry.id}:{account_slug}:{opportunity_key}",
                    "kind": "opportunity",
                    "title": normalize_text(str(normalized_opportunity.get("title") or "机会更新")),
                    "summary": normalize_text(str(normalized_opportunity.get("entry_window") or normalized_opportunity.get("benchmark_case") or "")),
                    "severity": "high" if int(normalized_opportunity.get("budget_probability") or 0) >= 70 else "medium",
                    "created_at": entry.created_at,
                    "watchlist_name": None,
                    "next_action": normalize_text(str(normalized_opportunity.get("next_best_action") or "")),
                    "budget_probability": int(normalized_opportunity.get("budget_probability") or 0),
                    "related_entry_id": entry.id,
                    "related_watchlist_id": None,
                    "tags": _unique_strings(
                        [
                            *(normalized_opportunity.get("why_now") or []),
                            *(normalized_opportunity.get("risk_flags") or []),
                        ],
                        limit=4,
                    ),
                }
            )
    for bucket in accounts.values():
        bucket["timeline"] = sorted(
            [
                *bucket["timeline"],
                *watchlist_timeline.get(bucket["slug"], []),
                *review_queue_timeline.get(bucket["slug"], []),
            ],
            key=lambda item: item["created_at"],
            reverse=True,
        )[:10]
        bucket["related_entries"] = sorted(
            bucket["related_entries"],
            key=lambda item: item["created_at"],
            reverse=True,
        )[:6]
        bucket["opportunities"] = sorted(
            bucket["opportunities"],
            key=lambda item: (int(item.get("score") or 0), int(item.get("budget_probability") or 0)),
            reverse=True,
        )[:6]
        bucket["stakeholder_map"] = _build_stakeholder_map(bucket)
        bucket["pipeline_risks"] = _build_pipeline_risks(bucket)
        bucket["account_plan"] = _build_account_plan(bucket)
        bucket["close_plan"] = _build_close_plan(bucket)
    return accounts


def list_knowledge_accounts(
    db: Session,
    *,
    query: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    accounts = list(_aggregate_accounts(db).values())
    normalized_query = normalize_text(query or "").lower()
    if normalized_query:
        accounts = [
            item
            for item in accounts
            if normalized_query in normalize_text(item["name"]).lower()
            or any(normalized_query in normalize_text(value).lower() for value in item["signals"])
        ]
    accounts.sort(
        key=lambda item: (item["confidence_score"], item["budget_probability"], item["report_count"]),
        reverse=True,
    )
    return accounts[: max(1, min(limit, 50))]


def get_knowledge_account_detail(db: Session, slug: str) -> dict[str, Any] | None:
    return _aggregate_accounts(db).get(_slugify(slug))


def list_knowledge_opportunities(
    db: Session,
    *,
    account_slug: str | None = None,
    limit: int = 30,
) -> list[dict[str, Any]]:
    opportunities: list[dict[str, Any]] = []
    account_filter = _slugify(account_slug) if account_slug else None
    for bucket in _aggregate_accounts(db).values():
        if account_filter and bucket["slug"] != account_filter:
            continue
        opportunities.extend(bucket["opportunities"])
    opportunities.sort(
        key=lambda item: (int(item.get("score") or 0), int(item.get("budget_probability") or 0)),
        reverse=True,
    )
    return opportunities[: max(1, min(limit, 60))]


def build_knowledge_commercial_dashboard(db: Session) -> dict[str, Any]:
    account_index = _aggregate_accounts(db)
    all_accounts = sorted(
        account_index.values(),
        key=lambda item: (item["confidence_score"], item["budget_probability"], item["report_count"]),
        reverse=True,
    )
    all_opportunities: list[dict[str, Any]] = []
    for bucket in account_index.values():
        all_opportunities.extend(bucket["opportunities"])
    all_opportunities.sort(
        key=lambda item: (int(item.get("score") or 0), int(item.get("budget_probability") or 0)),
        reverse=True,
    )
    accounts = all_accounts[:6]
    opportunities = all_opportunities[:6]
    benchmark_cases: set[str] = set()
    high_confidence = 0
    for entry in _load_research_report_entries(db):
        payload = entry.metadata_payload if isinstance(entry.metadata_payload, dict) else {}
        intelligence = extract_commercial_intelligence(payload)
        if not intelligence:
            continue
        confidence = intelligence.get("confidence") if isinstance(intelligence.get("confidence"), dict) else {}
        if int(confidence.get("score") or 0) >= 75:
            high_confidence += 1
        benchmark = intelligence.get("benchmark") if isinstance(intelligence.get("benchmark"), dict) else {}
        for item in benchmark.get("cases") or []:
            normalized = normalize_text(item)
            if normalized:
                benchmark_cases.add(normalized)
    review_queue = _build_review_queue_index(db)
    alerts = _build_dashboard_alerts(all_accounts, review_queue)
    return {
        "account_count": len(account_index),
        "opportunity_count": len(all_opportunities),
        "high_confidence_report_count": high_confidence,
        "benchmark_case_count": len(benchmark_cases),
        "top_accounts": accounts,
        "top_opportunities": opportunities,
        "top_alerts": alerts,
        "role_views": _build_role_views(all_accounts, all_opportunities, alerts, review_queue),
        "review_queue": review_queue,
    }
