from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from app.schemas.research import ResearchReportDocument, ResearchReportResponse, ResearchSourceOut
from app.services.content_extractor import extract_domain, normalize_text
from app.services.llm_parser import ResearchReportResult
from app.services.research.source_documents import SourceDocument


def stored_report_section_aliases() -> dict[str, tuple[str, ...]]:
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


def report_sources_to_source_documents(
    sources: list[ResearchSourceOut],
    *,
    classify_source_type: Callable[[str], str],
    classify_source_tier: Callable[..., str],
    derive_source_label: Callable[..., str | None],
    clean_source_text_for_analysis: Callable[[str], str],
    truncate_text: Callable[[str, int], str],
    dedupe_sources: Callable[[Iterable[SourceDocument]], list[SourceDocument]],
) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    for source in sources:
        url = normalize_text(source.url)
        if not url:
            continue
        title = normalize_text(source.title) or url
        domain = normalize_text(source.domain or "") or extract_domain(url)
        source_type = normalize_text(source.source_type) or classify_source_type(url)
        source_label = derive_source_label(
            source_type=source_type,
            domain=domain,
            fallback=normalize_text(source.source_label or "") or None,
        )
        source_tier = (
            source.source_tier
            if source.source_tier in {"official", "media", "aggregate"}
            else classify_source_tier(source_type=source_type, domain=domain, source_label=source_label)
        )
        snippet = truncate_text(
            clean_source_text_for_analysis(source.snippet or "") or clean_source_text_for_analysis(title),
            1200,
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
                source_origin=(
                    source.source_origin
                    if source.source_origin in {"search", "adapter", "snapshot_cache", "user_supplied"}
                    else ("adapter" if source_label else "search")
                ),
            )
        )
    return dedupe_sources(documents)


def stored_report_to_result(
    report: ResearchReportResponse,
    *,
    research_section_items: Callable[[ResearchReportDocument, tuple[str, ...]], list[str]],
    sanitize_report_field_rows: Callable[[str, Iterable[str]], list[str]],
) -> ResearchReportResult:
    section_aliases = stored_report_section_aliases()
    payload: dict[str, Any] = {
        "report_title": normalize_text(report.report_title),
        "executive_summary": normalize_text(report.executive_summary),
        "consulting_angle": normalize_text(report.consulting_angle),
        "industry_brief": research_section_items(report, section_aliases["industry_brief"]),
        "key_signals": research_section_items(report, section_aliases["key_signals"]),
        "policy_and_leadership": research_section_items(report, section_aliases["policy_and_leadership"]),
        "commercial_opportunities": research_section_items(report, section_aliases["commercial_opportunities"]),
        "solution_design": research_section_items(report, section_aliases["solution_design"]),
        "sales_strategy": research_section_items(report, section_aliases["sales_strategy"]),
        "bidding_strategy": research_section_items(report, section_aliases["bidding_strategy"]),
        "outreach_strategy": research_section_items(report, section_aliases["outreach_strategy"]),
        "ecosystem_strategy": research_section_items(report, section_aliases["ecosystem_strategy"]),
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
        "risks": research_section_items(report, section_aliases["risks"]),
        "next_actions": research_section_items(report, section_aliases["next_actions"]),
    }
    for key, value in list(payload.items()):
        if isinstance(value, list):
            payload[key] = sanitize_report_field_rows(key, value)
    return ResearchReportResult.model_validate(payload)
