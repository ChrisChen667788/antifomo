from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.schemas.research import ResearchEntityEvidenceOut, ResearchReportSectionOut
from app.services.language import localized_text
from app.services.llm_parser import ResearchReportResult
from app.services.research.source_documents import SourceDocument


@dataclass(frozen=True, slots=True)
class ReportSectionsDependencies:
    build_section_evidence_links: Callable[..., tuple[list[ResearchEntityEvidenceOut], dict[str, int], float]]
    section_signal_quality: Callable[..., tuple[str, str, str]]
    section_evidence_quota: Callable[[str, list[str]], int]
    section_quota_note: Callable[..., tuple[bool, int, str]]
    section_confidence_profile: Callable[..., tuple[str, str, str, bool, str]]
    section_next_verification_steps: Callable[..., list[str]]
    section_insufficiency_profile: Callable[..., tuple[str, list[str], str]]


SECTION_TITLE_TRANSLATIONS: dict[str, tuple[dict[str, str], str]] = {
    "industry_brief": ({"zh-CN": "行业资讯判断", "zh-TW": "產業資訊判斷", "en": "Industry View"}, "行业资讯判断"),
    "key_signals": ({"zh-CN": "关键信号", "zh-TW": "關鍵信號", "en": "Key Signals"}, "关键信号"),
    "policy_and_leadership": ({"zh-CN": "政策与领导信号", "zh-TW": "政策與領導信號", "en": "Policy and Leadership"}, "政策与领导信号"),
    "commercial_opportunities": ({"zh-CN": "项目与商机判断", "zh-TW": "專案與商機判斷", "en": "Opportunity Map"}, "项目与商机判断"),
    "solution_design": ({"zh-CN": "解决方案设计建议", "zh-TW": "解決方案設計建議", "en": "Solution Design"}, "解决方案设计建议"),
    "sales_strategy": ({"zh-CN": "销售策略", "zh-TW": "銷售策略", "en": "Sales Strategy"}, "销售策略"),
    "bidding_strategy": ({"zh-CN": "投标规划", "zh-TW": "投標規劃", "en": "Bidding Strategy"}, "投标规划"),
    "outreach_strategy": ({"zh-CN": "陌生拜访建议", "zh-TW": "陌生拜訪建議", "en": "Outreach Strategy"}, "陌生拜访建议"),
    "ecosystem_strategy": ({"zh-CN": "生态伙伴建议", "zh-TW": "生態夥伴建議", "en": "Ecosystem Strategy"}, "生态伙伴建议"),
    "target_accounts": ({"zh-CN": "重点甲方与目标客户", "zh-TW": "重點甲方與目標客戶", "en": "Target Accounts"}, "重点甲方与目标客户"),
    "target_departments": ({"zh-CN": "高概率决策部门", "zh-TW": "高機率決策部門", "en": "Likely Decision Departments"}, "高概率决策部门"),
    "public_contact_channels": ({"zh-CN": "公开业务联系方式", "zh-TW": "公開業務聯絡方式", "en": "Public Contact Channels"}, "公开业务联系方式"),
    "account_team_signals": ({"zh-CN": "活跃团队与推进抓手", "zh-TW": "活躍團隊與推進抓手", "en": "Active Teams and Execution Handles"}, "活跃团队与推进抓手"),
    "budget_signals": ({"zh-CN": "预算与投资信号", "zh-TW": "預算與投資信號", "en": "Budget Signals"}, "预算与投资信号"),
    "project_distribution": ({"zh-CN": "项目分布与期次判断", "zh-TW": "專案分佈與期次判斷", "en": "Project Distribution"}, "项目分布与期次判断"),
    "strategic_directions": ({"zh-CN": "战略方向", "zh-TW": "戰略方向", "en": "Strategic Directions"}, "战略方向"),
    "tender_timeline": ({"zh-CN": "招标时间预测", "zh-TW": "招標時間預測", "en": "Tender Timeline"}, "招标时间预测"),
    "leadership_focus": ({"zh-CN": "领导近三年关注点", "zh-TW": "領導近三年關注點", "en": "Leadership Focus"}, "领导近三年关注点"),
    "ecosystem_partners": ({"zh-CN": "活跃生态伙伴", "zh-TW": "活躍生態夥伴", "en": "Ecosystem Partners"}, "活跃生态伙伴"),
    "competitor_profiles": ({"zh-CN": "竞品公司概况", "zh-TW": "競品公司概況", "en": "Competitor Profiles"}, "竞品公司概况"),
    "benchmark_cases": ({"zh-CN": "同领域标杆案例", "zh-TW": "同領域標竿案例", "en": "Benchmark Cases"}, "同领域标杆案例"),
    "flagship_products": ({"zh-CN": "明星产品与方案", "zh-TW": "明星產品與方案", "en": "Flagship Products"}, "明星产品与方案"),
    "key_people": ({"zh-CN": "关键人物", "zh-TW": "關鍵人物", "en": "Key People"}, "关键人物"),
    "five_year_outlook": ({"zh-CN": "未来五年演化判断", "zh-TW": "未來五年演化判斷", "en": "Five-Year Outlook"}, "未来五年演化判断"),
    "client_peer_moves": ({"zh-CN": "甲方同行 Top 3 动态", "zh-TW": "甲方同行 Top 3 動態", "en": "Top 3 Buyer Peer Moves"}, "甲方同行 Top 3 动态"),
    "winner_peer_moves": ({"zh-CN": "中标方同行 Top 3 动态", "zh-TW": "中標方同行 Top 3 動態", "en": "Top 3 Winner Peer Moves"}, "中标方同行 Top 3 动态"),
    "competition_analysis": ({"zh-CN": "竞争分析", "zh-TW": "競爭分析", "en": "Competition Analysis"}, "竞争分析"),
    "risks": ({"zh-CN": "风险提示", "zh-TW": "風險提示", "en": "Risks"}, "风险提示"),
    "next_actions": ({"zh-CN": "下一步行动", "zh-TW": "下一步行動", "en": "Next Actions"}, "下一步行动"),
}

SECTION_KEYS: tuple[str, ...] = tuple(SECTION_TITLE_TRANSLATIONS)


def build_section_title_map(output_language: str) -> dict[str, str]:
    return {
        key: localized_text(output_language, translations, fallback)
        for key, (translations, fallback) in SECTION_TITLE_TRANSLATIONS.items()
    }


def build_sections(
    result: ResearchReportResult,
    output_language: str,
    sources: list[SourceDocument],
    *,
    deps: ReportSectionsDependencies,
) -> list[ResearchReportSectionOut]:
    title_map = build_section_title_map(output_language)
    sections: list[ResearchReportSectionOut] = []
    for key in SECTION_KEYS:
        items = getattr(result, key)
        if not items:
            continue
        section_title = title_map[key]
        evidence_links, source_tier_counts, official_source_ratio = deps.build_section_evidence_links(
            section_title=section_title,
            items=items,
            sources=sources,
            limit=3,
        )
        evidence_density, source_quality, evidence_note = deps.section_signal_quality(
            items,
            sources,
            evidence_links=evidence_links,
            source_tier_counts=source_tier_counts,
            official_source_ratio=official_source_ratio,
        )
        evidence_quota = deps.section_evidence_quota(key, items)
        meets_evidence_quota, quota_gap, quota_note = deps.section_quota_note(
            section_title=section_title,
            evidence_count=len(evidence_links),
            evidence_quota=evidence_quota,
            official_source_ratio=official_source_ratio,
        )
        confidence_tone, confidence_label, confidence_reason, contradiction_detected, contradiction_note = deps.section_confidence_profile(
            section_title=section_title,
            items=items,
            sources=sources,
            evidence_density=evidence_density,
            source_quality=source_quality,
            official_source_ratio=official_source_ratio,
            meets_evidence_quota=meets_evidence_quota,
            evidence_links=evidence_links,
        )
        next_verification_steps = deps.section_next_verification_steps(
            section_title=section_title,
            output_language=output_language,
            evidence_density=evidence_density,
            source_quality=source_quality,
            official_source_ratio=official_source_ratio,
            evidence_count=len(evidence_links),
            evidence_quota=evidence_quota,
            contradiction_detected=contradiction_detected,
        )
        section_status, insufficiency_reasons, insufficiency_summary = deps.section_insufficiency_profile(
            section_title=section_title,
            output_language=output_language,
            evidence_density=evidence_density,
            source_quality=source_quality,
            official_source_ratio=official_source_ratio,
            quota_gap=quota_gap,
            contradiction_detected=contradiction_detected,
        )
        tinted_evidence_links = [link.model_copy(update={"confidence_tone": confidence_tone}) for link in evidence_links]
        sections.append(
            ResearchReportSectionOut(
                title=section_title,
                items=items,
                status=section_status,
                evidence_density=evidence_density,
                source_quality=source_quality,
                confidence_tone=confidence_tone,
                confidence_label=confidence_label,
                confidence_reason=confidence_reason,
                evidence_note=evidence_note,
                insufficiency_reasons=insufficiency_reasons,
                insufficiency_summary=insufficiency_summary,
                source_tier_counts=source_tier_counts,
                official_source_ratio=official_source_ratio,
                evidence_links=tinted_evidence_links,
                evidence_count=len(evidence_links),
                evidence_quota=evidence_quota,
                meets_evidence_quota=meets_evidence_quota,
                quota_gap=quota_gap,
                quota_note=quota_note,
                next_verification_steps=next_verification_steps,
                contradiction_detected=contradiction_detected,
                contradiction_note=contradiction_note,
            )
        )
    return sections
