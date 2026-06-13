from __future__ import annotations

from base64 import b64encode
import html

from app.schemas.research import (
    ResearchMarketIntelligencePackOut,
    ResearchReportDocument,
    ResearchSolutionDeliveryPackOut,
)
from app.services.delivery.market_intelligence import build_market_intelligence_pack
from app.services.language import localized_text, normalize_output_language
from app.services.research_delivery_quality_service import review_and_improve_formal_document_sections
from app.services.research_solution_intelligence_service import build_solution_delivery_pack
from app.services.work_tasks.context import _context_list, _context_text
from app.services.work_tasks.pdf import _build_simple_pdf


def _normalize_research_delivery_supplement(raw: dict | None) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {
        "project_name": _context_text(raw.get("project_name")),
        "project_owner": _context_text(raw.get("project_owner")),
        "solution_scenario": _context_text(raw.get("solution_scenario")),
        "target_customer": _context_text(raw.get("target_customer")),
        "vertical_scene": _context_text(raw.get("vertical_scene")),
        "project_region": _context_text(raw.get("project_region")),
        "implementation_window": _context_text(raw.get("implementation_window")),
        "investment_estimate": _context_text(raw.get("investment_estimate")),
        "construction_basis": _context_text(raw.get("construction_basis")),
        "scope_statement": _context_text(raw.get("scope_statement")),
        "expected_benefits": _context_text(raw.get("expected_benefits")),
        "cross_validation_notes": _context_text(raw.get("cross_validation_notes")),
        "supplemental_context": _context_text(raw.get("supplemental_context")),
        "supplemental_evidence": _context_text(raw.get("supplemental_evidence")),
        "supplemental_requirements": _context_text(raw.get("supplemental_requirements")),
    }


def _dedupe_export_rows(values: list[str], *, limit: int = 6, preserve_labels: bool = False) -> list[str]:
    rows: list[str] = []
    for value in values:
        normalized = _context_text(value, preserve_labels=preserve_labels)
        if normalized and normalized not in rows:
            rows.append(normalized)
    return rows[:limit]


def _report_followup_rows(report: ResearchReportDocument) -> list[str]:
    context = getattr(report, "followup_context", None)
    if context is None:
        return []
    diagnostics = getattr(report, "followup_diagnostics", None)
    rows = [
        f"上一版研报标题：{_context_text(getattr(context, 'followup_report_title', ''))}",
        f"上一版执行摘要：{_context_text(getattr(context, 'followup_report_summary', ''))}",
        f"人工补充新信息：{_context_text(getattr(context, 'supplemental_context', ''))}",
        f"人工补充新证据/待核验线索：{_context_text(getattr(context, 'supplemental_evidence', ''))}",
        f"人工补充新需求：{_context_text(getattr(context, 'supplemental_requirements', ''))}",
    ]
    if diagnostics is not None and getattr(diagnostics, "enabled", False):
        title_resolution = _context_text(getattr(diagnostics, "title_resolution", ""))
        summary_resolution = _context_text(getattr(diagnostics, "summary_resolution", ""))
        resolution_labels = {
            "baseline": "基线生成",
            "reused": "沿用基线",
            "corrected": "已按追问纠偏",
        }
        if title_resolution:
            rows.append(f"标题处理：{resolution_labels.get(title_resolution, title_resolution)}")
        if summary_resolution:
            rows.append(f"摘要处理：{resolution_labels.get(summary_resolution, summary_resolution)}")
        for impact in list(getattr(diagnostics, "impacted_sections", []) or [])[:4]:
            section_title = _context_text(getattr(impact, "section_title", ""))
            impact_label = _context_text(getattr(impact, "impact_label", ""))
            impact_score = int(getattr(impact, "impact_score", 0) or 0)
            next_action = _context_text(getattr(impact, "next_action", ""))
            if section_title:
                rows.append(
                    f"重点影响章节：{section_title}（{impact_label or 'impact'} / {impact_score}）"
                    + (f"；下一步：{next_action}" if next_action else "")
                )
    return [row for row in rows if not row.endswith("：")]


FORMAL_REPORT_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "solution_design": ("解决方案设计建议", "解決方案設計建議", "solution design"),
    "sales_strategy": ("销售策略", "銷售策略", "sales strategy"),
    "bidding_strategy": ("投标规划", "投標規劃", "bidding strategy"),
    "outreach_strategy": ("陌生拜访建议", "陌生拜訪建議", "outreach strategy"),
    "risks": ("风险提示", "風險提示", "risks"),
    "next_actions": ("下一步行动", "下一步行動", "next actions"),
}


def _report_section_rows(
    report: ResearchReportDocument,
    key: str,
    *,
    limit: int = 6,
) -> list[str]:
    aliases = tuple(alias.lower() for alias in FORMAL_REPORT_SECTION_ALIASES.get(key, ()))
    if not aliases:
        return []
    rows: list[str] = []
    for section in report.sections:
        title = _context_text(section.title).lower()
        if not title or not any(alias in title for alias in aliases):
            continue
        rows.extend(_dedupe_export_rows([_context_text(item) for item in section.items], limit=limit))
    return _dedupe_export_rows(rows, limit=limit)


def _build_formal_document_context(
    report_payload: dict,
    *,
    output_language: str,
    delivery_supplement: dict | None,
) -> tuple[ResearchReportDocument, dict[str, str], dict[str, str]]:
    report = ResearchReportDocument.model_validate(report_payload)
    resolved_language = normalize_output_language(output_language or report.output_language)
    supplement = _normalize_research_delivery_supplement(delivery_supplement)
    scope_regions = _context_list(getattr(getattr(report, "source_diagnostics", None), "scope_regions", []), limit=2)
    solution_pack = getattr(report, "solution_delivery_pack", None)
    target_customer = (
        supplement.get("target_customer")
        or next((item.name for item in report.top_target_accounts if getattr(item, "name", "")), "")
        or next((item for item in report.target_accounts if _context_text(item)), "")
    )
    solution_scenario = (
        supplement.get("solution_scenario")
        or _context_text(getattr(solution_pack, "scenario", ""))
        or report.keyword
        or report.report_title
    )
    vertical_scene = (
        supplement.get("vertical_scene")
        or _context_text(getattr(solution_pack, "vertical_scene", ""))
        or report.research_focus
        or ""
    )
    project_owner = (
        supplement.get("project_owner")
        or target_customer
        or localized_text(
            resolved_language,
            {"zh-CN": "待补充业主/建设单位", "zh-TW": "待補充業主/建設單位", "en": "Owner to be confirmed"},
            "待补充业主/建设单位",
        )
    )
    default_project_name = (
        f"{target_customer}{solution_scenario}"
        if target_customer and solution_scenario
        else (
            f"{solution_scenario}建设项目"
            if solution_scenario
            else (
                f"{vertical_scene}建设项目"
                if vertical_scene
                else report.report_title
            )
        )
    )
    context = {
        "project_name": supplement.get("project_name")
        or default_project_name
        or localized_text(
            resolved_language,
            {"zh-CN": "专题研究项目", "zh-TW": "專題研究專案", "en": "Research Project"},
            "专题研究项目",
        ),
        "project_owner": project_owner,
        "target_customer": target_customer or project_owner,
        "solution_scenario": solution_scenario,
        "vertical_scene": vertical_scene,
        "project_region": supplement.get("project_region") or " / ".join(scope_regions) or report.keyword,
        "implementation_window": supplement.get("implementation_window")
        or next((item for item in report.tender_timeline if _context_text(item)), "")
        or localized_text(
            resolved_language,
            {"zh-CN": "建议按年度预算与招采窗口滚动推进", "zh-TW": "建議按年度預算與招採窗口滾動推進", "en": "Plan against annual budget and procurement windows"},
            "建议按年度预算与招采窗口滚动推进",
        ),
        "investment_estimate": supplement.get("investment_estimate")
        or next((item for item in report.budget_signals if _context_text(item)), "")
        or localized_text(
            resolved_language,
            {"zh-CN": "当前需结合公开预算与立项口径进一步测算", "zh-TW": "目前需結合公開預算與立項口徑進一步測算", "en": "Needs further sizing against public budget evidence"},
            "当前需结合公开预算与立项口径进一步测算",
        ),
        "construction_basis": supplement.get("construction_basis")
        or localized_text(
            resolved_language,
            {
                "zh-CN": "依据公开政策、招采公告、行业披露、公众号线索与当前研报结论交叉形成。",
                "zh-TW": "依據公開政策、招採公告、產業披露、公眾號線索與目前研報結論交叉形成。",
                "en": "Built from public policy, procurement notices, industry disclosures, curated WeChat leads, and the current research conclusion.",
            },
            "依据公开政策、招采公告、行业披露、公众号线索与当前研报结论交叉形成。",
        ),
        "scope_statement": supplement.get("scope_statement")
        or next((item for item in report.strategic_directions if _context_text(item)), "")
        or next((item for item in report.project_distribution if _context_text(item)), ""),
        "expected_benefits": supplement.get("expected_benefits")
        or next((item for item in report.five_year_outlook if _context_text(item)), "")
        or next((item for item in report.competition_analysis if _context_text(item)), ""),
        "cross_validation_notes": supplement.get("cross_validation_notes")
        or supplement.get("supplemental_evidence")
        or next((item for item in _report_followup_rows(report) if "新证据" in item), ""),
    }
    return report, supplement, context


def _build_runtime_formal_document_packs(
    report: ResearchReportDocument,
    *,
    context: dict[str, str],
    supplement: dict[str, str],
):
    market_pack = build_market_intelligence_pack(
        report,
        scenario=context.get("solution_scenario", ""),
        target_customer=context.get("target_customer", "") or context.get("project_owner", ""),
        vertical_scene=context.get("vertical_scene", ""),
    )
    solution_pack = build_solution_delivery_pack(
        report,
        scenario=context.get("solution_scenario", ""),
        target_customer=context.get("target_customer", "") or context.get("project_owner", ""),
        vertical_scene=context.get("vertical_scene", ""),
        supplemental_context=supplement.get("supplemental_context", ""),
    )
    return market_pack, solution_pack


def _build_formal_document_sections(
    *,
    report: ResearchReportDocument,
    output_language: str,
    document_kind: str,
    context: dict[str, str],
    supplement: dict[str, str],
) -> tuple[
    list[tuple[str, list[str]]],
    ResearchMarketIntelligencePackOut,
    ResearchSolutionDeliveryPackOut,
]:
    resolved_language = normalize_output_language(output_language or report.output_language)
    official_ratio = round(float(getattr(getattr(report, "source_diagnostics", None), "official_source_ratio", 0.0) or 0.0) * 100)
    evidence_rows = _dedupe_export_rows(
        [
            f"来源数量：{report.source_count}；证据密度：{report.evidence_density}；来源质量：{report.source_quality}；官方源占比：{official_ratio}%",
            context.get("construction_basis", ""),
            supplement.get("supplemental_context", ""),
            supplement.get("supplemental_evidence", ""),
            supplement.get("supplemental_requirements", ""),
            *_report_followup_rows(report),
        ],
        limit=8,
        preserve_labels=True,
    )
    market_pack, solution_pack = _build_runtime_formal_document_packs(
        report,
        context=context,
        supplement=supplement,
    )
    tender_rows = _dedupe_export_rows(
        [
            *[
                f"{item.project_name}（{item.notice_type or '公开线索'} / {item.publish_date or '日期待核验'} / {item.amount or '金额待核验'}）"
                for item in list(getattr(market_pack, "tender_projects", []) or [])[:6]
            ],
            *list(getattr(market_pack, "intelligence_gaps", []) or [])[:3],
        ],
        limit=8,
    )
    product_rows = _dedupe_export_rows(
        [
            *[
                f"{item.name}：{'；'.join((item.technical_parameters or [])[:3]) or item.source_context or '参数待核验'}"
                for item in list(getattr(market_pack, "product_catalog", []) or [])[:6]
            ],
            *[
                f"{section.title}：{'；'.join((section.bullets or [])[:3])}"
                for section in list(getattr(solution_pack, "client_ppt_outline", []) or [])[:3]
            ],
        ],
        limit=10,
    )
    feasibility_sections = [
        (
            localized_text(resolved_language, {"zh-CN": "一、项目概况", "zh-TW": "一、專案概況", "en": "1. Project Overview"}, "一、项目概况"),
            _dedupe_export_rows(
                [
                    f"项目名称：{context['project_name']}",
                    f"建议业主/建设单位：{context['project_owner']}",
                    f"目标客户：{context['target_customer']}",
                    f"项目/方案场景：{context['solution_scenario']}",
                    f"垂直场景：{context['vertical_scene']}",
                    f"建议区域/范围：{context['project_region']}",
                    f"实施窗口：{context['implementation_window']}",
                    f"核心结论：{report.executive_summary}",
                ],
                limit=8,
                preserve_labels=True,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "二、研究依据与交叉验证输入", "zh-TW": "二、研究依據與交叉驗證輸入", "en": "2. Inputs and Cross-Validation"}, "二、研究依据与交叉验证输入"),
            evidence_rows,
        ),
        (
            localized_text(resolved_language, {"zh-CN": "三、建设必要性与需求分析", "zh-TW": "三、建設必要性與需求分析", "en": "3. Need and Demand Analysis"}, "三、建设必要性与需求分析"),
            _dedupe_export_rows(
                [
                    report.consulting_angle,
                    *tender_rows[:4],
                    *report.commercial_summary.account_focus,
                    *report.budget_signals,
                    *report.leadership_focus,
                    *report.key_people,
                ],
                limit=8,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "四、建设目标与范围", "zh-TW": "四、建設目標與範圍", "en": "4. Goals and Scope"}, "四、建设目标与范围"),
            _dedupe_export_rows(
                [
                    context.get("scope_statement", ""),
                    f"项目/方案场景：{context['solution_scenario']}",
                    f"垂直场景：{context['vertical_scene']}",
                    supplement.get("supplemental_requirements", ""),
                    *report.strategic_directions,
                    *report.project_distribution,
                    *report.target_departments,
                ],
                limit=8,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "五、可行性分析", "zh-TW": "五、可行性分析", "en": "5. Feasibility Analysis"}, "五、可行性分析"),
            _dedupe_export_rows(
                [
                    *_report_section_rows(report, "solution_design", limit=6),
                    *product_rows,
                    *report.benchmark_cases,
                    *report.flagship_products,
                    *report.public_contact_channels,
                    *report.account_team_signals,
                ],
                limit=10,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "六、投资估算与综合效益", "zh-TW": "六、投資估算與綜合效益", "en": "6. Investment and Benefits"}, "六、投资估算与综合效益"),
            _dedupe_export_rows(
                [
                    f"投资估算/预算口径：{context['investment_estimate']}",
                    context.get("expected_benefits", ""),
                    *report.budget_signals,
                    *report.five_year_outlook,
                ],
                limit=8,
                preserve_labels=True,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "七、实施路径与保障措施", "zh-TW": "七、實施路徑與保障措施", "en": "7. Implementation and Assurance"}, "七、实施路径与保障措施"),
            _dedupe_export_rows(
                [
                    *report.tender_timeline,
                    *_report_section_rows(report, "sales_strategy", limit=5),
                    *_report_section_rows(report, "bidding_strategy", limit=5),
                    *_report_section_rows(report, "outreach_strategy", limit=5),
                    *_report_section_rows(report, "next_actions", limit=5),
                ],
                limit=10,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "八、风险控制与结论建议", "zh-TW": "八、風險控制與結論建議", "en": "8. Risks and Recommendation"}, "八、风险控制与结论建议"),
            _dedupe_export_rows(
                [
                    *report.competition_analysis,
                    *report.technical_appendix.limitations,
                    *[item.summary for item in report.review_queue],
                    report.commercial_summary.next_action,
                ],
                limit=8,
            ),
        ),
    ]
    proposal_sections = [
        (
            localized_text(resolved_language, {"zh-CN": "一、项目背景", "zh-TW": "一、專案背景", "en": "1. Project Background"}, "一、项目背景"),
            _dedupe_export_rows(
                [
                    f"项目名称：{context['project_name']}",
                    f"建议建设单位：{context['project_owner']}",
                    f"目标客户：{context['target_customer']}",
                    f"项目/方案场景：{context['solution_scenario']}",
                    f"垂直场景：{context['vertical_scene']}",
                    f"建议建设区域：{context['project_region']}",
                    report.executive_summary,
                    context.get("construction_basis", ""),
                ],
                limit=8,
                preserve_labels=True,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "二、建设目标", "zh-TW": "二、建設目標", "en": "2. Objectives"}, "二、建设目标"),
            _dedupe_export_rows(
                [
                    context.get("scope_statement", ""),
                    f"项目/方案场景：{context['solution_scenario']}",
                    f"垂直场景：{context['vertical_scene']}",
                    supplement.get("supplemental_requirements", ""),
                    *report.strategic_directions,
                    *report.target_departments,
                    *product_rows[:4],
                ],
                limit=8,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "三、建设内容与方案设计", "zh-TW": "三、建設內容與方案設計", "en": "3. Scope and Solution"}, "三、建设内容与方案设计"),
            _dedupe_export_rows(
                [
                    *_report_section_rows(report, "solution_design", limit=6),
                    *product_rows,
                    *report.benchmark_cases,
                    *report.flagship_products,
                    *report.ecosystem_partners,
                ],
                limit=10,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "四、实施计划", "zh-TW": "四、實施計畫", "en": "4. Implementation Plan"}, "四、实施计划"),
            _dedupe_export_rows(
                [
                    f"建议实施窗口：{context['implementation_window']}",
                    *report.tender_timeline,
                    *_report_section_rows(report, "next_actions", limit=5),
                    *_report_section_rows(report, "sales_strategy", limit=5),
                ],
                limit=8,
                preserve_labels=True,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "五、投资测算与预期效益", "zh-TW": "五、投資測算與預期效益", "en": "5. Investment and Outcomes"}, "五、投资测算与预期效益"),
            _dedupe_export_rows(
                [
                    f"建议投资口径：{context['investment_estimate']}",
                    context.get("expected_benefits", ""),
                    *report.budget_signals,
                    *report.five_year_outlook,
                ],
                limit=8,
                preserve_labels=True,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "六、组织协同与风险提示", "zh-TW": "六、組織協同與風險提示", "en": "6. Organization and Risks"}, "六、组织协同与风险提示"),
            _dedupe_export_rows(
                [
                    *report.account_team_signals,
                    *report.public_contact_channels,
                    *report.competition_analysis,
                    *report.technical_appendix.limitations,
                    *[item.summary for item in report.review_queue],
                ],
                limit=10,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "七、交叉验证附注", "zh-TW": "七、交叉驗證附註", "en": "7. Cross-Validation Notes"}, "七、交叉验证附注"),
            _dedupe_export_rows(
                [
                    supplement.get("cross_validation_notes", ""),
                    context.get("cross_validation_notes", ""),
                    *evidence_rows,
                ],
                limit=8,
                preserve_labels=True,
            ),
        ),
    ]
    sections = feasibility_sections if document_kind == "feasibility_study" else proposal_sections
    return sections, market_pack, solution_pack


def _build_formal_document_html(
    *,
    title: str,
    subtitle: str,
    meta_rows: list[str],
    sections: list[tuple[str, list[str]]],
) -> str:
    blocks = [
        "<html><head><meta charset='utf-8' />",
        "<style>",
        "body{font-family:'PingFang SC','Microsoft YaHei',sans-serif;padding:40px 44px;color:#0f172a;line-height:1.75;background:#ffffff;}",
        "h1{font-size:28px;margin:0 0 8px;}h2{font-size:18px;margin:24px 0 10px;color:#0f172a;}p{margin:0;}ul{margin:8px 0 0 18px;padding:0;}",
        ".subtitle{color:#475569;font-size:14px;margin-bottom:18px;}.meta{border:1px solid #dbeafe;background:#f8fbff;border-radius:16px;padding:16px 18px;margin-bottom:24px;}",
        ".meta p{margin:4px 0;}.section{margin-top:16px;padding-top:2px;}.section li{margin:6px 0;}",
        "</style></head><body>",
        f"<h1>{html.escape(title)}</h1>",
        f"<p class='subtitle'>{html.escape(subtitle)}</p>",
        "<div class='meta'>",
    ]
    blocks.extend([f"<p>{html.escape(row)}</p>" for row in meta_rows if _context_text(row)])
    blocks.append("</div>")
    for section_title, rows in sections:
        blocks.append(f"<div class='section'><h2>{html.escape(section_title)}</h2><ul>")
        blocks.extend([f"<li>{html.escape(row)}</li>" for row in rows if _context_text(row)])
        blocks.append("</ul></div>")
    blocks.append("</body></html>")
    return "\n".join(blocks)


def _build_formal_document_plaintext(
    *,
    title: str,
    subtitle: str,
    meta_rows: list[str],
    sections: list[tuple[str, list[str]]],
) -> str:
    lines = [title, "", subtitle, ""]
    lines.extend([f"- {row}" for row in meta_rows if _context_text(row)])
    for section_title, rows in sections:
        lines.extend(["", section_title])
        lines.extend([f"- {row}" for row in rows if _context_text(row)])
    return "\n".join(lines).strip()


def _build_formal_document_bundle(
    *,
    report_payload: dict,
    output_language: str,
    document_kind: str,
    delivery_supplement: dict | None,
) -> tuple[str, str, str]:
    report, supplement, context = _build_formal_document_context(
        report_payload,
        output_language=output_language,
        delivery_supplement=delivery_supplement,
    )
    resolved_language = normalize_output_language(output_language or report.output_language)
    title = (
        f"{context['project_name']}可行性研究报告"
        if document_kind == "feasibility_study"
        else f"{context['project_name']}项目建议书"
    )
    subtitle = localized_text(
        resolved_language,
        {
            "zh-CN": "基于当前研报、公开来源与人工补充信息交叉整理",
            "zh-TW": "基於目前研報、公開來源與人工補充資訊交叉整理",
            "en": "Compiled from the current research report, public sources, and manual supplements.",
        },
        "基于当前研报、公开来源与人工补充信息交叉整理",
    )
    meta_rows = _dedupe_export_rows(
        [
            f"项目名称：{context['project_name']}",
            f"建议业主/建设单位：{context['project_owner']}",
            f"目标客户：{context['target_customer']}",
            f"项目/方案场景：{context['solution_scenario']}",
            f"垂直场景：{context['vertical_scene']}",
            f"建议区域：{context['project_region']}",
            f"实施窗口：{context['implementation_window']}",
            f"投资估算：{context['investment_estimate']}",
            f"来源数量：{report.source_count}",
            supplement.get("cross_validation_notes", ""),
        ],
        limit=8,
        preserve_labels=True,
    )
    sections, market_pack, solution_pack = _build_formal_document_sections(
        report=report,
        output_language=resolved_language,
        document_kind=document_kind,
        context=context,
        supplement=supplement,
    )
    sections, _delivery_quality = review_and_improve_formal_document_sections(
        sections,
        review_target=document_kind,
        source_support_score=max(
            int(getattr(market_pack, "source_support_score", 0) or 0),
            int(getattr(solution_pack, "source_support_score", 0) or 0),
        ),
        grounded_count=len(list(getattr(solution_pack, "grounding_checks", []) or [])),
        checklist_count=len(list(getattr(solution_pack, "review_checklist", []) or [])),
        evidence_note_count=len(list(getattr(solution_pack, "intelligence_summary", []) or []))
        + len(list(getattr(market_pack, "intelligence_gaps", []) or [])),
    )
    html_content = _build_formal_document_html(
        title=title,
        subtitle=subtitle,
        meta_rows=meta_rows,
        sections=sections,
    )
    plain_text = _build_formal_document_plaintext(
        title=title,
        subtitle=subtitle,
        meta_rows=meta_rows,
        sections=sections,
    )
    return title, html_content, plain_text


def build_feasibility_study_word_document(
    report_payload: dict,
    *,
    output_language: str = "zh-CN",
    delivery_supplement: dict | None = None,
) -> tuple[str, str, str]:
    title, html_content, _ = _build_formal_document_bundle(
        report_payload=report_payload,
        output_language=output_language,
        document_kind="feasibility_study",
        delivery_supplement=delivery_supplement,
    )
    filename_seed = "".join(ch for ch in title if ch.isalnum() or ch in {" ", "-", "_"}) or "feasibility-study"
    return f"{filename_seed[:48].replace(' ', '_')}.doc", html_content, "application/msword"


def build_feasibility_study_pdf_document(
    report_payload: dict,
    *,
    output_language: str = "zh-CN",
    delivery_supplement: dict | None = None,
) -> tuple[str, str, str, str]:
    title, _, plain_text = _build_formal_document_bundle(
        report_payload=report_payload,
        output_language=output_language,
        document_kind="feasibility_study",
        delivery_supplement=delivery_supplement,
    )
    filename_seed = "".join(ch for ch in title if ch.isalnum() or ch in {" ", "-", "_"}) or "feasibility-study"
    pdf_bytes = _build_simple_pdf(plain_text.splitlines())
    return f"{filename_seed[:48].replace(' ', '_')}.pdf", plain_text, b64encode(pdf_bytes).decode("ascii"), "application/pdf"


def build_research_market_intelligence_markdown(
    report_payload: dict,
    *,
    output_language: str = "zh-CN",
    delivery_supplement: dict | None = None,
) -> tuple[str, str]:
    report = ResearchReportDocument.model_validate(report_payload)
    supplement = _normalize_research_delivery_supplement(delivery_supplement)
    pack = build_market_intelligence_pack(
        report,
        scenario=supplement.get("solution_scenario", ""),
        target_customer=supplement.get("target_customer", "") or supplement.get("project_owner", ""),
        vertical_scene=supplement.get("vertical_scene", ""),
    )
    filename_seed = "".join(
        ch
        for ch in (
            supplement.get("solution_scenario")
            or supplement.get("vertical_scene")
            or supplement.get("target_customer")
            or report.keyword
            or "market-intelligence"
        )
        if ch.isalnum() or ch in {" ", "-", "_"}
    ).strip().replace(" ", "_")
    if not filename_seed:
        filename_seed = "market-intelligence"
    return f"{filename_seed[:48]}-intelligence-pack.md", pack.export_markdown


def build_research_solution_delivery_markdown(
    report_payload: dict,
    *,
    output_language: str = "zh-CN",
    delivery_supplement: dict | None = None,
) -> tuple[str, str]:
    report = ResearchReportDocument.model_validate(report_payload)
    supplement = _normalize_research_delivery_supplement(delivery_supplement)
    pack = build_solution_delivery_pack(
        report,
        scenario=supplement.get("solution_scenario", ""),
        target_customer=supplement.get("target_customer", "") or supplement.get("project_owner", ""),
        vertical_scene=supplement.get("vertical_scene", ""),
        supplemental_context=supplement.get("supplemental_context", ""),
    )
    filename_seed = "".join(
        ch
        for ch in (
            supplement.get("solution_scenario")
            or supplement.get("vertical_scene")
            or supplement.get("target_customer")
            or report.keyword
            or "solution-delivery"
        )
        if ch.isalnum() or ch in {" ", "-", "_"}
    ).strip().replace(" ", "_")
    if not filename_seed:
        filename_seed = "solution-delivery"
    return f"{filename_seed[:48]}-solution-delivery.md", pack.export_markdown


def build_project_proposal_word_document(
    report_payload: dict,
    *,
    output_language: str = "zh-CN",
    delivery_supplement: dict | None = None,
) -> tuple[str, str, str]:
    title, html_content, _ = _build_formal_document_bundle(
        report_payload=report_payload,
        output_language=output_language,
        document_kind="project_proposal",
        delivery_supplement=delivery_supplement,
    )
    filename_seed = "".join(ch for ch in title if ch.isalnum() or ch in {" ", "-", "_"}) or "project-proposal"
    return f"{filename_seed[:48].replace(' ', '_')}.doc", html_content, "application/msword"


def build_project_proposal_pdf_document(
    report_payload: dict,
    *,
    output_language: str = "zh-CN",
    delivery_supplement: dict | None = None,
) -> tuple[str, str, str, str]:
    title, _, plain_text = _build_formal_document_bundle(
        report_payload=report_payload,
        output_language=output_language,
        document_kind="project_proposal",
        delivery_supplement=delivery_supplement,
    )
    filename_seed = "".join(ch for ch in title if ch.isalnum() or ch in {" ", "-", "_"}) or "project-proposal"
    pdf_bytes = _build_simple_pdf(plain_text.splitlines())
    return f"{filename_seed[:48].replace(' ', '_')}.pdf", plain_text, b64encode(pdf_bytes).decode("ascii"), "application/pdf"

