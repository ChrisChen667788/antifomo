from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Iterable

from app.schemas.research import (
    ResearchAdvisoryArtifactOut,
    ResearchMarketIntelligencePackOut,
    ResearchProductRequirementOut,
    ResearchReportDocument,
    ResearchSolutionDeliveryPackOut,
    ResearchSolutionOutlineSectionOut,
    ResearchTenderProjectOut,
)
from app.services.content_extractor import normalize_text
from app.services.research_delivery_quality_service import review_and_improve_solution_delivery_pack
from app.services.research_rag_quality_service import build_retrieval_correction_profile


_TENDER_TERMS = ("招标", "中标", "采购", "采购意向", "成交", "竞争性磋商", "公开招标", "公共资源", "预算", "标段")
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
        is_tender = any(term in text for term in _TENDER_TERMS) or str(source.source_type or "").lower() in {
            "procurement",
            "tender_feed",
            "policy",
        }
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

    if not tender_projects and (report.budget_signals or report.tender_timeline):
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
        "覆盖公开网页、政府采购、公共资源交易、招投标公开平台、企业官网/产品页、行业媒体和当前已抓取来源；"
        "不使用未授权登录库或付费墙数据。"
    )
    gaps = _dedupe_strings(
        [
            "近三年明确招标/中标明细不足，建议继续跑政府采购、公共资源交易和招投标公开平台专项检索。"
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
        tender_keywords=tender_keywords,
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


def _outline(title: str, bullets: Iterable[object]) -> ResearchSolutionOutlineSectionOut:
    return ResearchSolutionOutlineSectionOut(title=title, bullets=_dedupe_strings(bullets, limit=8))


def _artifact_markdown(
    *,
    title: str,
    audience: str,
    purpose: str,
    source_policy: str,
    sections: list[ResearchSolutionOutlineSectionOut],
) -> str:
    lines = [
        f"# {title}",
        "",
        f"- 受众: {audience}",
        f"- 用途: {purpose}",
        f"- 证据口径: {source_policy}",
        "",
    ]
    for section in sections:
        lines.append(f"## {section.title}")
        lines.extend([f"- {bullet}" for bullet in section.bullets])
        lines.append("")
    return "\n".join(lines).strip()


def _build_advisory_artifacts(
    report: ResearchReportDocument,
    *,
    market_pack: ResearchMarketIntelligencePackOut,
    scenario: str,
    target_customer: str,
    vertical_scene: str,
    evidence_policy: str,
) -> list[ResearchAdvisoryArtifactOut]:
    customer = target_customer or (report.target_accounts[0] if report.target_accounts else "待确认客户")
    scene = vertical_scene or report.research_focus or scenario
    top_projects = [item.project_name for item in market_pack.tender_projects[:3]]
    top_requirements = [
        param
        for item in market_pack.technical_parameter_catalog[:4]
        for param in item.technical_parameters[:2]
    ]
    client_sections = [
        _outline("客户场景与触发信号", [f"目标客户：{customer}", f"场景：{scene}", report.executive_summary, *report.budget_signals[:2]]),
        _outline("可交流方案主张", [*report.strategic_directions[:3], *[item.name for item in market_pack.product_catalog[:4]], report.commercial_summary.next_action]),
        _outline("公开证据与边界", [market_pack.source_scope_summary, *top_projects, *market_pack.intelligence_gaps[:2]]),
        _outline("建议会议目标", ["确认牵头部门、试点范围、数据边界和预算口径。", "争取客户提供现有流程、系统接口和历史项目材料。"]),
    ]
    bidding_sections = [
        _outline("机会判断", [f"客户/业主：{customer}", f"场景：{scenario}", report.consulting_angle, *report.tender_timeline[:3]]),
        _outline("招采与竞标准备", [*[item.project_name for item in market_pack.tender_projects[:4]], *report.competition_analysis[:3], *market_pack.tender_keywords[:5]]),
        _outline("技术与资质关注", [*top_requirements, *report.technical_appendix.limitations[:2], "补齐投标资质、业绩案例、产品参数和安全合规说明。"]),
        _outline("投标准备动作", ["建立招标文件预审清单。", "准备技术偏离表、商务条款风险表和评分点响应矩阵。", report.commercial_summary.next_action]),
    ]
    execution_sections = [
        _outline("交付拆解", [f"一期建议聚焦：{scene}", *report.project_distribution[:3], *report.target_departments[:4]]),
        _outline("近期行动", ["7 日内完成客户访谈提纲、需求确认表和演示脚本。", "30 日内完成原型范围、预算测算和项目建议书初稿。", report.commercial_summary.next_action]),
        _outline("材料清单", ["客户 brief", "投标准备 memo", "需求访谈表", "方案架构页", "技术参数表", "风险与待核验清单"]),
        _outline("风险控制", [*market_pack.intelligence_gaps[:3], *report.technical_appendix.limitations[:3], "所有客户版结论保留来源或标注为假设。"]),
    ]
    specs = [
        (
            "client_brief",
            f"{customer} {scenario} 客户 brief",
            "客户业务负责人 / 信息化牵头部门",
            "用于客户初次交流、场景确认和下一步共创邀约。",
            client_sections,
        ),
        (
            "bidding_prep_memo",
            f"{customer} {scenario} 投标准备 memo",
            "售前、投标、解决方案和商务团队",
            "用于招采前研判、评分点预判、材料责任分工。",
            bidding_sections,
        ),
        (
            "execution_materials",
            f"{customer} {scenario} 执行材料清单",
            "项目负责人 / 交付 PM / 售前负责人",
            "用于把研究结论转成可下发的任务、清单和交付物。",
            execution_sections,
        ),
    ]
    artifacts: list[ResearchAdvisoryArtifactOut] = []
    for artifact_type, title, audience, purpose, sections in specs:
        review_checklist = _dedupe_strings(
            [
                "确认客户名称、牵头部门和场景是否可对外表达。",
                "确认所有确定性判断是否有官方源、客户材料或招采证据支撑。",
                "确认预算、时间、产品参数和竞品表述是否需要降级为假设。",
            ],
            limit=6,
        )
        artifacts.append(
            ResearchAdvisoryArtifactOut(
                artifact_type=artifact_type,
                title=title,
                audience=audience,
                purpose=purpose,
                source_policy=evidence_policy,
                markdown=_artifact_markdown(
                    title=title,
                    audience=audience,
                    purpose=purpose,
                    source_policy=evidence_policy,
                    sections=sections,
                ),
                review_checklist=review_checklist,
            )
        )
    return artifacts


def _scenario_from_report(report: ResearchReportDocument) -> str:
    text = normalize_text(" ".join([report.keyword, report.research_focus or "", report.report_title]))
    for value in ("电商数字人", "文旅AIGC平台", "AI营销平台", "政务AI解决方案", "政务AI", "数字人", "AIGC", "AI营销"):
        if value.lower() in text.lower():
            return value
    return report.keyword


def build_solution_delivery_pack(
    report: ResearchReportDocument,
    *,
    scenario: str = "",
    target_customer: str = "",
    vertical_scene: str = "",
    supplemental_context: str = "",
) -> ResearchSolutionDeliveryPackOut:
    resolved_scenario = normalize_text(scenario) or _scenario_from_report(report)
    resolved_customer = normalize_text(target_customer) or (report.target_accounts[0] if report.target_accounts else "")
    resolved_scene = normalize_text(vertical_scene) or normalize_text(report.research_focus or "")
    market_pack = build_market_intelligence_pack(
        report,
        scenario=resolved_scenario,
        target_customer=resolved_customer,
        vertical_scene=resolved_scene,
    )
    intelligence_summary = _dedupe_strings(
        [
            f"来源支撑度 {market_pack.source_support_score}/100，可直接采用来源 {market_pack.validated_source_count} 条，需复核来源 {market_pack.ambiguous_source_count} 条。",
            f"近三年公开招采候选 {len(market_pack.tender_projects)} 条，产品/能力线索 {len(market_pack.product_catalog)} 条，技术参数线索 {len(market_pack.technical_parameter_catalog)} 组。",
            report.executive_summary,
            report.commercial_summary.budget_signal,
            supplemental_context,
            *report.budget_signals[:2],
            *report.benchmark_cases[:2],
        ],
        limit=8,
    )
    clarification_questions = _dedupe_strings(
        [
            "目标客户是谁？如果暂不明确，请至少给出行业、区域和客户类型。",
            "更垂直的场景是什么？例如电商直播数字人、景区AIGC导览、政务热线AI助手、招商AI营销平台。",
            "本次材料面向谁审阅？内部立项、客户汇报、招采前交流还是正式申报？",
            "预算口径、建设周期、部署形态、数据安全边界是否已有硬约束？",
        ],
        limit=6,
    )
    feasibility_outline = [
        _outline("一、项目概况", [f"项目/场景：{resolved_scenario}", f"建议客户/业主：{resolved_customer or '待确认'}", f"垂直场景：{resolved_scene or '待确认'}"]),
        _outline("二、研究依据与近三年公开情报", [market_pack.source_scope_summary, *[item.project_name for item in market_pack.tender_projects[:4]], *market_pack.intelligence_gaps[:2]]),
        _outline("三、建设必要性与需求分析", [report.consulting_angle, *report.leadership_focus[:2], *report.budget_signals[:2]]),
        _outline("四、建设内容与技术方案", [*report.strategic_directions[:3], *[item.name for item in market_pack.product_catalog[:4]]]),
        _outline("五、投资估算与效益分析", [*report.budget_signals[:3], "结合近三年同类招采金额、产品模块和交付范围形成分档预算。"]),
        _outline("六、风险、边界与结论", [*report.technical_appendix.limitations[:3], *market_pack.intelligence_gaps[:2], report.commercial_summary.next_action]),
    ]
    project_proposal_outline = [
        _outline("一、项目背景", [report.executive_summary, market_pack.source_scope_summary]),
        _outline("二、建设目标", [f"围绕 {resolved_scenario} 建立可演示、可试点、可扩展的方案闭环。", *report.strategic_directions[:3]]),
        _outline("三、建设内容", [*report.project_distribution[:3], *[item.name for item in market_pack.product_catalog[:5]]]),
        _outline("四、实施计划", [*report.tender_timeline[:3], "建议分为调研确认、原型验证、试点上线、规模推广四阶段。"]),
        _outline("五、投资测算", [*report.budget_signals[:3], "按软件平台、模型/算力、集成实施、运营运维、培训推广拆分。"]),
        _outline("六、组织协同与风险控制", [*report.target_departments[:4], *report.competition_analysis[:3]]),
    ]
    client_ppt_outline = [
        _outline("1. 客户当前业务挑战", [report.executive_summary, resolved_scene]),
        _outline("2. 外部趋势与近三年招采参考", [*[item.project_name for item in market_pack.tender_projects[:4]], *market_pack.tender_keywords[:5]]),
        _outline("3. 建设目标与总体架构", [*report.strategic_directions[:3], "业务层、智能中台层、模型/数据层、安全运维层。"]),
        _outline("4. 核心功能与产品清单", [*[item.name for item in market_pack.product_catalog[:6]]]),
        _outline("5. 技术参数与交付边界", [*[param for item in market_pack.technical_parameter_catalog[:3] for param in item.technical_parameters[:2]]]),
        _outline("6. 实施路线与预算口径", [*report.tender_timeline[:3], *report.budget_signals[:3]]),
        _outline("7. 下一步共创计划", [report.commercial_summary.next_action, "客户确认范围后输出正式可研、建议书和对客汇报稿。"]),
    ]
    evidence_policy = (
        "仅把已命中主题、客户或招采/技术参数的来源写成确定判断；其余内容保留为待核验假设。"
        if market_pack.source_support_score < 70
        else "当前来源可支撑初版方案大纲，正式对客前仍需确认预算、客户和交付边界。"
    )
    advisory_artifacts = _build_advisory_artifacts(
        report,
        market_pack=market_pack,
        scenario=resolved_scenario,
        target_customer=resolved_customer,
        vertical_scene=resolved_scene,
        evidence_policy=evidence_policy,
    )
    pack = ResearchSolutionDeliveryPackOut(
        scenario=resolved_scenario,
        target_customer=resolved_customer,
        vertical_scene=resolved_scene,
        source_support_score=market_pack.source_support_score,
        evidence_policy=evidence_policy,
        grounding_checks=_dedupe_strings(
            [
                f"已通过来源校正筛出 {market_pack.validated_source_count} 条高相关来源。",
                f"仍有 {market_pack.ambiguous_source_count} 条来源需要人工复核。",
                *market_pack.intelligence_gaps[:2],
            ],
            limit=6,
        ),
        clarification_questions=clarification_questions,
        intelligence_summary=intelligence_summary,
        feasibility_outline=feasibility_outline,
        project_proposal_outline=project_proposal_outline,
        client_ppt_outline=client_ppt_outline,
        advisory_artifacts=advisory_artifacts,
        review_checklist=_dedupe_strings(
            [
                "确认目标客户和业务牵头部门是否准确。",
                "确认近三年招采项目是否和目标场景同类、同区域或同采购路径。",
                "确认产品清单、技术参数和部署边界是否可对外表达。",
                "确认预算口径、实施周期和交付责任边界。",
                "确认哪些内容可进入客户版，哪些只保留内部版。",
            ],
            limit=8,
        ),
        next_steps=_dedupe_strings(
            [
                "用户确认目标客户/垂直场景后，补跑专项公开源检索并锁定材料版本。",
                "先审阅大纲，再细化为可研、项目建议书或对客汇报 PPT 完稿。",
                "导出前保留证据附录，避免对客材料出现无来源强结论。",
            ],
            limit=6,
        ),
    )
    pack = review_and_improve_solution_delivery_pack(pack)
    pack.export_markdown = build_solution_delivery_markdown(pack, market_pack=market_pack)
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


def _outline_markdown(title: str, sections: list[ResearchSolutionOutlineSectionOut]) -> list[str]:
    lines = [f"## {title}"]
    for section in sections:
        lines.append(f"### {section.title}")
        lines.extend([f"- {bullet}" for bullet in section.bullets])
    return lines


def build_solution_delivery_markdown(
    pack: ResearchSolutionDeliveryPackOut,
    *,
    market_pack: ResearchMarketIntelligencePackOut | None = None,
) -> str:
    lines = [
        "# 解决方案交付包大纲",
        "",
        f"- 场景: {pack.scenario or '待确认'}",
        f"- 目标客户: {pack.target_customer or '待确认'}",
        f"- 垂直场景: {pack.vertical_scene or '待确认'}",
        f"- 来源支撑: {pack.source_support_score}/100",
        f"- 证据口径: {pack.evidence_policy or '正式对客前需复核关键来源。'}",
        "",
        "## 情报摘要",
        *[f"- {item}" for item in pack.intelligence_summary],
        "",
        "## 生成前核验",
        *[f"- {item}" for item in pack.grounding_checks],
        "",
        "## 用户确认问题",
        *[f"- {item}" for item in pack.clarification_questions],
        "",
    ]
    lines.extend(_outline_markdown("可行性研究报告大纲", pack.feasibility_outline))
    lines.append("")
    lines.extend(_outline_markdown("项目建议书大纲", pack.project_proposal_outline))
    lines.append("")
    lines.extend(_outline_markdown("对客汇报 PPT 大纲", pack.client_ppt_outline))
    if pack.advisory_artifacts:
        lines.extend(["", "## Advisory-grade 交付产物"])
        for artifact in pack.advisory_artifacts:
            lines.extend(
                [
                    f"### {artifact.title}",
                    f"- 类型: {artifact.artifact_type}",
                    f"- 受众: {artifact.audience}",
                    f"- 用途: {artifact.purpose}",
                    f"- 证据口径: {artifact.source_policy}",
                ]
            )
    lines.extend(["", "## 审阅清单"])
    lines.extend([f"- {item}" for item in pack.review_checklist])
    lines.extend(["", "## 交付质量自审"])
    for profile in (pack.solution_quality_profile, pack.project_proposal_quality_profile):
        lines.extend(
            [
                f"### {profile.framework_label} / {profile.review_target}",
                f"- 综合评分: {profile.overall_score}/100",
                f"- 审查状态: {profile.status}",
                f"- 重点缺口: {'；'.join(profile.gaps[:3]) if profile.gaps else '当前未发现阻塞性交付缺口。'}",
            ]
        )
        if profile.self_review.triggered:
            lines.append(
                f"- 自修订: {profile.self_review.before_score} -> {profile.self_review.after_score}；"
                f"{'；'.join(profile.self_review.actions[:3])}"
            )
    if market_pack is not None:
        lines.extend(["", "## 近三年公开情报附录", market_pack.export_markdown])
    return "\n".join(lines).strip()
