from __future__ import annotations

from app.schemas.research import ResearchReportDocument
from app.services.content_extractor import normalize_text
from app.services.language import localized_text


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
    evidence_gate = getattr(report, "research_evidence_gate", None)
    question_tree = getattr(report, "research_question_tree", None)
    citation_gate = getattr(report, "research_citation_gate", None)
    if evidence_gate and evidence_gate.enforced:
        lines.extend(
            [
                "",
                f"## {localized_text(resolved_language, {'zh-CN': '研究证据治理', 'zh-TW': '研究證據治理', 'en': 'Research Evidence Governance'}, '研究证据治理')}",
                "",
                f"- Evidence gate: {evidence_gate.status}",
                f"- Source admission: {evidence_gate.accepted_source_count}/{evidence_gate.candidate_source_count}",
                f"- Official sources: {evidence_gate.official_source_count}/{evidence_gate.minimum_official_source_count}",
                f"- Unique domains: {evidence_gate.unique_domain_count}/{evidence_gate.minimum_unique_domain_count}",
                f"- Question coverage: {evidence_gate.question_coverage_percent}%",
            ]
        )
        if evidence_gate.blockers:
            lines.extend(["", "### 阻断原因", *[f"- {item}" for item in evidence_gate.blockers]])
        if question_tree and question_tree.questions:
            lines.extend(["", "### 研究问题树"])
            lines.extend(
                [
                    f"- [{node.question_id}] {node.axis} · {node.coverage_status} · accepted={node.accepted_source_count}: {node.question}"
                    for node in question_tree.questions
                ]
            )
        if citation_gate and citation_gate.enforced:
            lines.extend(
                [
                    "",
                    "### 主张引用门",
                    f"- Status: {citation_gate.status}",
                    f"- Claims supported: {citation_gate.supported_claim_count}/{citation_gate.claim_count}",
                    f"- Critical claim coverage: {citation_gate.critical_claim_coverage_percent}%",
                    f"- Citation completeness: {citation_gate.citation_completeness_percent}%",
                    f"- Citation support: {citation_gate.citation_support_percent}%",
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
    if getattr(report, "market_intelligence", None):
        market_pack = report.market_intelligence
        if market_pack.tender_projects or market_pack.product_catalog or market_pack.external_source_queries:
            lines.extend(
                [
                    "",
                    f"## {localized_text(resolved_language, {'zh-CN': '近三年招投标与产品技术参数情报', 'zh-TW': '近三年招投標與產品技術參數情報', 'en': '3-Year Tender and Product Intelligence'}, '近三年招投标与产品技术参数情报')}",
                    "",
                    f"- 时间窗口: {market_pack.window_start} 至 {market_pack.window_end}",
                    f"- 来源范围: {market_pack.source_scope_summary}",
                ]
            )
            if market_pack.tender_projects:
                lines.extend(["", "### 招投标项目明细"])
                for item in market_pack.tender_projects[:10]:
                    lines.append(
                        f"- {item.project_name} | {item.notice_type or '待核验'} | {item.publish_date or '待核验'} | {item.amount or '金额待核验'} | {item.source_url}"
                    )
                    detail_bits = [
                        f"招标人/采购人: {item.buyer}" if item.buyer else "",
                        f"中标方: {item.winning_vendor}" if item.winning_vendor else "",
                        f"投标方/候选人: {'；'.join(item.bidder_candidates[:4])}" if item.bidder_candidates else "",
                        f"招标代理: {item.tender_agency}" if item.tender_agency else "",
                        f"项目编号: {item.project_code}" if item.project_code else "",
                    ]
                    detail_line = "；".join(bit for bit in detail_bits if bit)
                    if detail_line:
                        lines.append(f"  明细: {detail_line}")
                    if item.technical_parameters:
                        lines.append(f"  招标参数/技术参数: {'；'.join(item.technical_parameters[:4])}")
            if market_pack.product_catalog:
                lines.extend(["", "### 产品清单"])
                for item in market_pack.product_catalog[:10]:
                    lines.append(f"- {item.name}: {item.source_context}")
                    if item.technical_parameters:
                        lines.append(f"  参数: {'；'.join(item.technical_parameters[:5])}")
            if market_pack.external_source_queries:
                lines.extend(["", "### 后续全网公开源检索清单"])
                lines.extend([f"- {query}" for query in market_pack.external_source_queries[:10]])
            if market_pack.intelligence_gaps:
                lines.extend(["", "### 待补证缺口"])
                lines.extend([f"- {gap}" for gap in market_pack.intelligence_gaps])
    if getattr(report, "solution_delivery_pack", None):
        delivery_pack = report.solution_delivery_pack
        if delivery_pack.feasibility_outline or delivery_pack.project_proposal_outline or delivery_pack.client_ppt_outline:
            lines.extend(
                [
                    "",
                    f"## {localized_text(resolved_language, {'zh-CN': '解决方案交付包大纲', 'zh-TW': '解決方案交付包大綱', 'en': 'Solution Delivery Package Outline'}, '解决方案交付包大纲')}",
                    "",
                    f"- 场景: {delivery_pack.scenario or '待确认'}",
                    f"- 目标客户: {delivery_pack.target_customer or '待确认'}",
                    f"- 垂直场景: {delivery_pack.vertical_scene or '待确认'}",
                ]
            )
            for title, outline in [
                ("可行性研究报告大纲", delivery_pack.feasibility_outline),
                ("项目建议书大纲", delivery_pack.project_proposal_outline),
                ("对客汇报 PPT 大纲", delivery_pack.client_ppt_outline),
            ]:
                if not outline:
                    continue
                lines.extend(["", f"### {title}"])
                for section in outline[:8]:
                    lines.append(f"- {section.title}: {'；'.join(section.bullets[:4])}")
            if delivery_pack.review_checklist:
                lines.extend(["", "### 审阅确认清单"])
                lines.extend([f"- {item}" for item in delivery_pack.review_checklist])
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
