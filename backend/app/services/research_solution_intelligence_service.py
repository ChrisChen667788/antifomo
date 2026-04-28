from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Iterable

from app.schemas.research import (
    ResearchMarketIntelligencePackOut,
    ResearchProductRequirementOut,
    ResearchReportDocument,
    ResearchSolutionDeliveryPackOut,
    ResearchSolutionOutlineSectionOut,
    ResearchTenderProjectOut,
)
from app.services.content_extractor import normalize_text


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
    return _dedupe_strings((match.group(1) for match in _TECH_PARAM_RE.finditer(value)), limit=limit)


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
            f"site:ggzy.gov.cn {scope} 招标 中标 项目 技术参数",
            f"site:cecbid.org.cn {scope} 招标 中标 采购 技术要求",
            f"site:gov.cn {scope} 政策 试点 建设方案",
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

    for source in report.sources:
        text = _source_text(source)
        if not text or not _date_in_window(text, start=start, end=end):
            continue
        is_tender = any(term in text for term in _TENDER_TERMS) or str(source.source_type or "").lower() in {
            "procurement",
            "tender_feed",
            "policy",
        }
        parameters = _extract_parameters(text)
        amount_match = _AMOUNT_RE.search(text)
        vendor_match = _VENDOR_RE.search(text)
        if is_tender:
            tender_projects.append(
                ResearchTenderProjectOut(
                    project_name=_infer_project_name(source.title or source.snippet or report.report_title),
                    buyer=target_customer or (report.target_accounts[0] if report.target_accounts else ""),
                    region=" / ".join(report.source_diagnostics.scope_regions[:2]),
                    industry_or_scene=vertical_scene or scenario or " / ".join(report.source_diagnostics.scope_industries[:2]),
                    notice_type=_infer_notice_type(text),
                    publish_date=_extract_date(text),
                    amount=normalize_text(amount_match.group(1)) if amount_match else "",
                    winning_vendor=normalize_text(vendor_match.group(1)) if vendor_match else "",
                    source_title=source.title,
                    source_url=source.url,
                    source_tier=source.source_tier,
                    relevance_score=_source_relevance(source, text),
                    extracted_requirements=_dedupe_strings([source.snippet, *report.strategic_directions[:2]], limit=4),
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
        tender_projects=tender_projects[:12],
        tender_keywords=tender_keywords,
        product_catalog=list(product_rows.values())[:12],
        technical_parameter_catalog=list(technical_rows.values())[:10],
        external_source_queries=_build_external_queries(report, scenario=scenario or vertical_scene),
        intelligence_gaps=gaps,
    )
    pack.export_markdown = build_market_intelligence_markdown(pack)
    return pack


def _outline(title: str, bullets: Iterable[object]) -> ResearchSolutionOutlineSectionOut:
    return ResearchSolutionOutlineSectionOut(title=title, bullets=_dedupe_strings(bullets, limit=8))


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
    pack = ResearchSolutionDeliveryPackOut(
        scenario=resolved_scenario,
        target_customer=resolved_customer,
        vertical_scene=resolved_scene,
        clarification_questions=clarification_questions,
        intelligence_summary=intelligence_summary,
        feasibility_outline=feasibility_outline,
        project_proposal_outline=project_proposal_outline,
        client_ppt_outline=client_ppt_outline,
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
    pack.export_markdown = build_solution_delivery_markdown(pack, market_pack=market_pack)
    return pack


def build_market_intelligence_markdown(pack: ResearchMarketIntelligencePackOut) -> str:
    lines = [
        "# 近三年招投标与产品技术参数情报包",
        "",
        f"- 时间窗口: {pack.window_start} 至 {pack.window_end}",
        f"- 来源范围: {pack.source_scope_summary}",
        "",
        "## 招投标项目明细",
    ]
    if pack.tender_projects:
        for item in pack.tender_projects:
            lines.extend(
                [
                    f"- {item.project_name}",
                    f"  - 采购方/业主: {item.buyer or '待核验'}",
                    f"  - 类型/日期/金额: {item.notice_type or '待核验'} / {item.publish_date or '待核验'} / {item.amount or '待核验'}",
                    f"  - 来源: {item.source_title or '待补源'} {item.source_url}",
                    f"  - 技术参数: {'；'.join(item.technical_parameters) if item.technical_parameters else '待补招标文件或产品规格页'}",
                ]
            )
    else:
        lines.append("- 暂未形成可引用项目明细，需继续补公开招采来源。")
    lines.extend(["", "## 产品清单与技术参数"])
    for item in pack.product_catalog:
        lines.append(f"- {item.name}: {'；'.join(item.technical_parameters) if item.technical_parameters else item.source_context}")
    lines.extend(["", "## 外部检索清单"])
    lines.extend([f"- {query}" for query in pack.external_source_queries])
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
        "",
        "## 情报摘要",
        *[f"- {item}" for item in pack.intelligence_summary],
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
    lines.extend(["", "## 审阅清单"])
    lines.extend([f"- {item}" for item in pack.review_checklist])
    if market_pack is not None:
        lines.extend(["", "## 近三年公开情报附录", market_pack.export_markdown])
    return "\n".join(lines).strip()
