from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
import re

from app.schemas.research import (
    ResearchMarketIntelligencePackOut,
    ResearchProductRequirementOut,
    ResearchReportDocument,
    ResearchTenderProjectOut,
)
from app.services.content_extractor import normalize_text
from app.services.research_rag_quality_service import build_retrieval_correction_profile


_TENDER_TERMS = ("招标", "中标", "采购", "采购意向", "成交", "竞争性磋商", "公开招标", "公共资源", "预算", "标段")
_TENDER_CLASSIFIER_TERMS = (
    "招标",
    "中标",
    "采购意向",
    "成交",
    "竞争性磋商",
    "公开招标",
    "公共资源",
    "标段",
    "项目编号",
    "招标编号",
    "采购编号",
    "中标候选人",
    "最高限价",
)
_PRODUCT_TERMS = (
    "数字人",
    "AIGC",
    "大模型",
    "智能体",
    "AI营销",
    "政务AI",
    "平台",
    "系统",
    "引擎",
    "模型",
    "算力",
    "知识库",
    "RAG",
    "多模态",
    "语音",
    "视频",
)
_TECH_PARAM_RE = re.compile(
    r"((?:≥|<=|>=|不低于|不少于|支持|具备|并发|时延|响应|准确率|吞吐|QPS|GPU|CPU|内存|存储|接口|API|SDK|国产化|信创|等保|私有化|多租户|SLA|可用性)[^。；;，,\n]{0,80})",
    flags=re.IGNORECASE,
)
_DATE_RE = re.compile(r"(20[2-3]\d)[年./-]?(0?[1-9]|1[0-2])?[月./-]?(0?[1-9]|[12]\d|3[01])?")
_AMOUNT_RE = re.compile(r"((?:预算|金额|中标价|成交价|投资|最高限价)[^。；;，,\n]{0,40}(?:万元|亿元|万|元))")
_VENDOR_RE = re.compile(r"(?:中标(?:供应商|人|单位)?|成交(?:供应商|人|单位)?)[：: ]?([^。；;，,\n]{2,40})")
_BUYER_RE = re.compile(r"(?:招标人|采购人|采购单位|项目业主|建设单位)[：: ]?([^。；;，,\n]{2,50})")
_AGENCY_RE = re.compile(r"(?:招标代理(?:机构)?|采购代理(?:机构)?|代理机构)[：: ]?([^。；;，,\n]{2,50})")
_PROJECT_CODE_RE = re.compile(r"(?:项目编号|招标编号|采购编号|项目代码|标段编号)[：: ]?([A-Za-z0-9_\-（）()【】\u4e00-\u9fff]{3,60})")
_CONTACT_RE = re.compile(r"(?:联系人|联系方式|联系电话|电话)[：: ]?([^。；;，,\n]{3,60})")
_BIDDER_RE = re.compile(
    r"(?:投标人|投标单位|供应商|中标候选人|第一中标候选人|第二中标候选人|第三中标候选人)[：: ]?([^。；;，,\n]{2,50})"
)
_TENDER_PARAM_RE = re.compile(
    r"((?:资格|资质|证书|工期|服务期|交付期|质保|评分|评审|标段|包件|投标保证金|最高限价|采购需求|建设内容|技术规格|技术要求|招标参数)[^。；;，,\n]{0,90})"
)


def _dedupe_strings(values: Iterable[object], limit: int = 10) -> list[str]:
    seen: set[str] = set()
    rows: list[str] = []
    for value in values:
        normalized = normalize_text(str(value or ""))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        rows.append(normalized)
        if len(rows) >= limit:
            break
    return rows


def _source_text(source: object) -> str:
    return normalize_text(
        "；".join(
            [
                str(getattr(source, "title", "") or ""),
                str(getattr(source, "snippet", "") or ""),
                str(getattr(source, "search_query", "") or ""),
                str(getattr(source, "source_label", "") or ""),
                str(getattr(source, "source_type", "") or ""),
            ]
        )
    )


def _window() -> tuple[datetime, datetime]:
    end = datetime.now(timezone.utc)
    return end - timedelta(days=365 * 3), end


def _date_in_window(value: str, *, start: datetime, end: datetime) -> bool:
    match = _DATE_RE.search(value)
    if not match:
        return True
    year = int(match.group(1))
    month = int(match.group(2) or 1)
    day = int(match.group(3) or 1)
    try:
        found = datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return True
    return start <= found <= end


def _extract_date(value: str) -> str:
    match = _DATE_RE.search(value)
    if not match:
        return ""
    year = match.group(1)
    month = match.group(2)
    day = match.group(3)
    if month and day:
        return f"{year}-{int(month):02d}-{int(day):02d}"
    if month:
        return f"{year}-{int(month):02d}"
    return year


def _extract_parameters(value: str, *, limit: int = 8) -> list[str]:
    return _dedupe_strings(
        [
            *(match.group(1) for match in _TECH_PARAM_RE.finditer(value)),
            *(match.group(1) for match in _TENDER_PARAM_RE.finditer(value)),
        ],
        limit=limit,
    )


def _extract_first(pattern: re.Pattern[str], value: str) -> str:
    match = pattern.search(value)
    return normalize_text(match.group(1)) if match else ""


def _extract_bidders(value: str, *, winning_vendor: str = "", limit: int = 6) -> list[str]:
    rows = _dedupe_strings((match.group(1) for match in _BIDDER_RE.finditer(value)), limit=limit + 2)
    if winning_vendor:
        rows = [row for row in rows if row != winning_vendor]
    return rows[:limit]


def _infer_notice_type(value: str) -> str:
    if "采购意向" in value:
        return "采购意向"
    if "中标" in value or "成交" in value:
        return "中标/成交"
    if "招标" in value:
        return "招标公告"
    if "竞争性磋商" in value:
        return "竞争性磋商"
    return "公开线索"


def _infer_project_name(value: str) -> str:
    title = normalize_text(value)
    if len(title) <= 80:
        return title
    for separator in ("：", ":", "-", "—", "】"):
        if separator in title:
            candidate = normalize_text(title.split(separator)[-1])
            if 6 <= len(candidate) <= 80:
                return candidate
    return title[:80]


def _source_relevance(source: object, text: str) -> int:
    score = 20
    if getattr(source, "source_tier", "") == "official":
        score += 24
    if any(term in text for term in _TENDER_TERMS):
        score += 24
    if any(term.lower() in text.lower() for term in _PRODUCT_TERMS):
        score += 18
    if _extract_parameters(text):
        score += 12
    if _extract_date(text):
        score += 8
    return min(score, 100)


def _looks_like_tender_source(source: object, text: str) -> bool:
    source_type = str(getattr(source, "source_type", "") or "").lower()
    if source_type in {"procurement", "tender_feed"}:
        return True
    if source_type in {"policy", "media", "news"} and not any(term in text for term in _TENDER_CLASSIFIER_TERMS):
        return False
    return any(term in text for term in _TENDER_CLASSIFIER_TERMS) or bool(
        _BUYER_RE.search(text)
        or _VENDOR_RE.search(text)
        or _AGENCY_RE.search(text)
        or _PROJECT_CODE_RE.search(text)
    )


def _tender_project_key(item: ResearchTenderProjectOut) -> str:
    project = normalize_text(item.project_name)
    project = re.sub(r"(公开招标公告|招标公告|中标成交公告|中标公告|成交公告|采购意向|结果公示)$", "", project)
    buyer = normalize_text(item.buyer)
    return f"{project[:64]}|{buyer[:32]}".lower()


def _merge_tender_projects(items: list[ResearchTenderProjectOut]) -> list[ResearchTenderProjectOut]:
    merged: dict[str, ResearchTenderProjectOut] = {}
    for item in items:
        key = _tender_project_key(item)
        existing = merged.get(key)
        if existing is None:
            merged[key] = item
            continue
        existing.buyer = existing.buyer or item.buyer
        existing.region = existing.region or item.region
        existing.industry_or_scene = existing.industry_or_scene or item.industry_or_scene
        existing.notice_type = existing.notice_type if existing.notice_type != "公开线索" else item.notice_type
        existing.publish_date = existing.publish_date or item.publish_date
        existing.amount = existing.amount or item.amount
        existing.winning_vendor = existing.winning_vendor or item.winning_vendor
        existing.tender_agency = existing.tender_agency or item.tender_agency
        existing.project_code = existing.project_code or item.project_code
        existing.buyer_contact = existing.buyer_contact or item.buyer_contact
        existing.bidder_candidates = _dedupe_strings([*existing.bidder_candidates, *item.bidder_candidates], limit=8)
        existing.extracted_requirements = _dedupe_strings(
            [*existing.extracted_requirements, *item.extracted_requirements],
            limit=8,
        )
        existing.technical_parameters = _dedupe_strings(
            [*existing.technical_parameters, *item.technical_parameters],
            limit=10,
        )
        if item.relevance_score > existing.relevance_score:
            existing.source_title = item.source_title or existing.source_title
            existing.source_url = item.source_url or existing.source_url
            existing.source_tier = item.source_tier
            existing.relevance_score = item.relevance_score
    return list(merged.values())


def _build_external_queries(report: ResearchReportDocument, scenario: str = "") -> list[str]:
    scope_terms = _dedupe_strings(
        [
            report.keyword,
            report.research_focus or "",
            scenario,
            *report.target_accounts[:3],
            *report.target_departments[:2],
            *report.flagship_products[:3],
        ],
        limit=8,
    )
    scope = " ".join(scope_terms)
    return _dedupe_strings(
        [
            f"site:ccgp.gov.cn {scope} 采购意向 招标 中标 近三年",
            f"site:ggzy.gov.cn {scope} 招标 中标 项目 技术参数 招标代理 投标人",
            f"site:cecbid.org.cn {scope} 招标 中标 采购 技术要求 中标候选人",
            f"site:gov.cn {scope} 政策 试点 建设方案",
            f"{scope} 招标人 中标方 投标方 招标代理 招标参数",
            f"{scope} 产品清单 技术参数 招标文件",
            f"{scope} 解决方案 项目建议书 可行性研究报告",
            f"{scope} 企业官网 产品白皮书 技术规格",
        ],
        limit=10,
    )


def build_market_intelligence_pack(
    report: ResearchReportDocument,
    *,
    scenario: str = "",
    target_customer: str = "",
    vertical_scene: str = "",
) -> ResearchMarketIntelligencePackOut:
    start, end = _window()
    tender_projects: list[ResearchTenderProjectOut] = []
    product_rows: dict[str, ResearchProductRequirementOut] = {}
    technical_rows: dict[str, ResearchProductRequirementOut] = {}
    tender_keywords = _dedupe_strings([*_TENDER_TERMS, report.keyword, scenario, vertical_scene], limit=12)
    opportunity_keywords = _dedupe_strings(
        [report.keyword, scenario, vertical_scene, "政策", "试点", "建设方案", "应用场景"],
        limit=12,
    )
    diagnostics = getattr(report, "source_diagnostics", None)
    scope_hints = {
        "regions": list(getattr(diagnostics, "scope_regions", []) or []),
        "industries": list(getattr(diagnostics, "scope_industries", []) or []),
        "clients": list(getattr(diagnostics, "scope_clients", []) or []),
        "company_anchors": list(getattr(diagnostics, "candidate_profile_companies", []) or []),
    }
    correction_profile = build_retrieval_correction_profile(
        report.sources,
        keyword=report.keyword,
        research_focus=report.research_focus or scenario or vertical_scene,
        scope_hints=scope_hints,
        query_plan=report.query_plan,
        corrective_query_limit=8,
    )
    rejected_urls = correction_profile.rejected_urls

    for source in report.sources:
        source_url = normalize_text(getattr(source, "url", "") or "")
        text = _source_text(source)
        if not text or not _date_in_window(text, start=start, end=end):
            continue
        is_tender = _looks_like_tender_source(source, text)
        if source_url in rejected_urls and not is_tender:
            continue
        parameters = _extract_parameters(text)
        amount_match = _AMOUNT_RE.search(text)
        vendor_match = _VENDOR_RE.search(text)
        winning_vendor = normalize_text(vendor_match.group(1)) if vendor_match else ""
        if is_tender:
            tender_projects.append(
                ResearchTenderProjectOut(
                    project_name=_infer_project_name(source.title or source.snippet or report.report_title),
                    buyer=target_customer or _extract_first(_BUYER_RE, text) or (report.target_accounts[0] if report.target_accounts else ""),
                    region=" / ".join(report.source_diagnostics.scope_regions[:2]),
                    industry_or_scene=vertical_scene or scenario or " / ".join(report.source_diagnostics.scope_industries[:2]),
                    notice_type=_infer_notice_type(text),
                    publish_date=_extract_date(text),
                    amount=normalize_text(amount_match.group(1)) if amount_match else "",
                    winning_vendor=winning_vendor,
                    bidder_candidates=_extract_bidders(text, winning_vendor=winning_vendor),
                    tender_agency=_extract_first(_AGENCY_RE, text),
                    project_code=_extract_first(_PROJECT_CODE_RE, text),
                    buyer_contact=_extract_first(_CONTACT_RE, text),
                    source_title=source.title,
                    source_url=source.url,
                    source_tier=source.source_tier,
                    relevance_score=_source_relevance(source, text),
                    extracted_requirements=_dedupe_strings(
                        [
                            source.snippet,
                            _extract_first(_BUYER_RE, text),
                            _extract_first(_AGENCY_RE, text),
                            _extract_first(_PROJECT_CODE_RE, text),
                            *report.strategic_directions[:2],
                        ],
                        limit=6,
                    ),
                    technical_parameters=parameters,
                )
            )
        product_candidates = _dedupe_strings(
            [
                *report.flagship_products,
                *(term for term in _PRODUCT_TERMS if term.lower() in text.lower()),
            ],
            limit=10,
        )
        for product in product_candidates:
            row = product_rows.get(product)
            if row is None:
                row = ResearchProductRequirementOut(
                    name=product,
                    category=_infer_notice_type(text) if is_tender else "产品/能力线索",
                    source_context=source.title,
                )
            row.evidence_urls = _dedupe_strings([*row.evidence_urls, source.url], limit=5)
            row.linked_projects = _dedupe_strings([*row.linked_projects, source.title], limit=5)
            row.technical_parameters = _dedupe_strings([*row.technical_parameters, *parameters], limit=10)
            product_rows[product] = row
        if parameters:
            parameter_key = product_candidates[0] if product_candidates else "技术参数"
            row = technical_rows.get(parameter_key) or ResearchProductRequirementOut(
                name=parameter_key,
                category="技术参数",
                source_context=source.title,
            )
            row.evidence_urls = _dedupe_strings([*row.evidence_urls, source.url], limit=5)
            row.technical_parameters = _dedupe_strings([*row.technical_parameters, *parameters], limit=12)
            technical_rows[parameter_key] = row

    fallback_text = normalize_text("；".join([*report.budget_signals, *report.tender_timeline]))
    if not tender_projects and fallback_text and any(term in fallback_text for term in _TENDER_CLASSIFIER_TERMS):
        tender_projects.append(
            ResearchTenderProjectOut(
                project_name=f"{report.keyword} 近三年招采补证候选",
                buyer=target_customer or (report.target_accounts[0] if report.target_accounts else ""),
                industry_or_scene=vertical_scene or scenario,
                notice_type="待外部检索",
                relevance_score=42,
                extracted_requirements=_dedupe_strings([*report.budget_signals, *report.tender_timeline], limit=5),
            )
        )

    tender_projects = _merge_tender_projects(tender_projects)
    tender_projects.sort(key=lambda item: (item.relevance_score, item.source_tier == "official"), reverse=True)
    source_scope = (
        (
            "覆盖公开网页、政府采购、公共资源交易、招投标公开平台、企业官网/产品页、行业媒体和当前已抓取来源；"
            "不使用未授权登录库或付费墙数据。"
        )
        if tender_projects
        else (
            "覆盖政府/主管部门政策、公开通知、企业官网/产品页、行业媒体和当前已抓取来源；"
            "不使用未授权登录库或付费墙数据。"
        )
    )
    gaps = _dedupe_strings(
        [
            "当前样本以政策/试点来源为主，尚未形成可引用交易明细；如需投标材料，应补公开交易来源。"
            if len(tender_projects) < 3
            else "",
            "产品清单或技术参数不足，建议补招标文件、产品白皮书、官网规格页和竞品交付案例。"
            if len(product_rows) < 3 or len(technical_rows) < 2
            else "",
            "如果要形成正式对客材料，需人工确认目标客户、建设范围、预算口径和交付边界。",
        ],
        limit=5,
    )
    pack = ResearchMarketIntelligencePackOut(
        lookback_years=3,
        window_start=start.date().isoformat(),
        window_end=end.date().isoformat(),
        source_scope_summary=source_scope,
        source_support_score=correction_profile.relevance_score,
        validated_source_count=correction_profile.accepted_source_count,
        ambiguous_source_count=correction_profile.ambiguous_source_count,
        rejected_source_count=correction_profile.rejected_source_count,
        tender_projects=tender_projects[:12],
        tender_keywords=tender_keywords if tender_projects else opportunity_keywords,
        product_catalog=list(product_rows.values())[:12],
        technical_parameter_catalog=list(technical_rows.values())[:10],
        external_source_queries=_dedupe_strings(
            [
                *_build_external_queries(report, scenario=scenario or vertical_scene),
                *correction_profile.corrective_queries,
            ],
            limit=14,
        ),
        corrective_queries=correction_profile.corrective_queries,
        intelligence_gaps=gaps,
    )
    pack.export_markdown = build_market_intelligence_markdown(pack)
    return pack


def build_market_intelligence_markdown(pack: ResearchMarketIntelligencePackOut) -> str:
    lines = [
        "# 近三年招投标与产品技术参数情报包",
        "",
        f"- 时间窗口: {pack.window_start} 至 {pack.window_end}",
        f"- 来源范围: {pack.source_scope_summary}",
        f"- 来源支撑: {pack.source_support_score}/100；高相关 {pack.validated_source_count} 条；需复核 {pack.ambiguous_source_count} 条；弱相关 {pack.rejected_source_count} 条",
        "",
        "## 招投标项目明细",
    ]
    if pack.tender_projects:
        for item in pack.tender_projects:
            lines.extend(
                [
                    f"- {item.project_name}",
                    f"  - 招标人/采购人: {item.buyer or '待核验'}",
                    f"  - 中标方: {item.winning_vendor or '待核验'}",
                    f"  - 投标方/候选人: {'；'.join(item.bidder_candidates) if item.bidder_candidates else '待核验'}",
                    f"  - 招标代理: {item.tender_agency or '待核验'}",
                    f"  - 项目编号/联系方式: {item.project_code or '待核验'} / {item.buyer_contact or '待核验'}",
                    f"  - 类型/日期/金额: {item.notice_type or '待核验'} / {item.publish_date or '待核验'} / {item.amount or '待核验'}",
                    f"  - 来源: {item.source_title or '待补源'} {item.source_url}",
                    f"  - 招标参数/技术参数: {'；'.join(item.technical_parameters) if item.technical_parameters else '待补招标文件或产品规格页'}",
                ]
            )
    else:
        lines.append("- 暂未形成可引用项目明细，需继续补公开招采来源。")
    lines.extend(["", "## 产品清单与技术参数"])
    for item in pack.product_catalog:
        lines.append(f"- {item.name}: {'；'.join(item.technical_parameters) if item.technical_parameters else item.source_context}")
    lines.extend(["", "## 外部检索清单"])
    lines.extend([f"- {query}" for query in pack.external_source_queries])
    if pack.corrective_queries:
        lines.extend(["", "## 建议补充检索"])
        lines.extend([f"- {query}" for query in pack.corrective_queries])
    if pack.intelligence_gaps:
        lines.extend(["", "## 待补证缺口"])
        lines.extend([f"- {gap}" for gap in pack.intelligence_gaps])
    return "\n".join(lines).strip()
