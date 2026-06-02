from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import re

from app.schemas.research import (
    ResearchActionCardOut,
    ResearchEntityEvidenceOut,
    ResearchRankedEntityOut,
    ResearchReportDocument,
    ResearchReportSectionOut,
    ResearchSourceDiagnosticsOut,
)
from app.services.content_extractor import extract_domain, normalize_text
from app.services.language import localized_text


@dataclass(frozen=True, slots=True)
class ResearchActionCardDependencies:
    dedupe_strings: Callable[[Iterable[str], int], list[str]]
    extract_rank_entity_name: Callable[[str], str]
    theme_labels_from_scope: Callable[..., list[str]]
    looks_like_scope_prompt_noise: Callable[[str], bool]
    looks_like_placeholder_entity_name: Callable[[str], bool]
    looks_like_fragment_entity_name: Callable[[str], bool]
    contains_low_value_entity_token: Callable[[str], bool]
    is_trustworthy_scope_client_name: Callable[..., bool]
    is_theme_aligned_entity_name: Callable[..., bool]
    is_lightweight_entity_name: Callable[[str], bool]
    is_actionable_budget_row: Callable[[str], bool]
    is_summary_fact_row: Callable[[str], bool]
    is_low_signal_execution_report: Callable[[ResearchReportDocument], bool]


def _research_section_items(report: ResearchReportDocument, aliases: tuple[str, ...]) -> list[str]:
    normalized_aliases = tuple(alias.lower() for alias in aliases)
    for section in report.sections:
        title = normalize_text(section.title).lower()
        if any(alias in title for alias in normalized_aliases):
            return [normalize_text(item) for item in section.items if normalize_text(item)]
    return []


def _truncate_sentence(value: str, limit: int = 82) -> str:
    text = normalize_text(value)
    if len(text) <= limit:
        return text
    clipped = text[: limit - 1].rstrip(" ，,：:；;、")
    return f"{clipped}…"


def _build_action_summary(primary: list[str], secondary: list[str], *, fallback: str) -> str:
    seeds = [item for item in primary[:2] if item] + [item for item in secondary[:1] if item]
    if not seeds:
        return _truncate_sentence(fallback, 96)
    return _truncate_sentence("；".join(seeds), 108)


def _research_section(report: ResearchReportDocument, aliases: tuple[str, ...]) -> ResearchReportSectionOut | None:
    normalized_aliases = tuple(alias.lower() for alias in aliases)
    for section in report.sections:
        title = normalize_text(section.title).lower()
        if any(alias in title for alias in normalized_aliases):
            return section
    return None


def _is_low_value_action_url(url: str) -> bool:
    normalized = normalize_text(url).lower()
    if not normalized:
        return True
    if any(normalized.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
        return True
    return any(token in normalized for token in ("/static/", "/images/", "/image/", "common/images"))


def _format_action_evidence_link(link: ResearchEntityEvidenceOut) -> str | None:
    url = normalize_text(link.url)
    if not url or _is_low_value_action_url(url):
        return None
    title = normalize_text(link.title)
    source_label = normalize_text(link.source_label)
    domain = extract_domain(url) or ""
    label_parts: list[str] = []
    if source_label and source_label not in {title, domain}:
        label_parts.append(source_label)
    if title and title not in {source_label, domain}:
        label_parts.append(_truncate_sentence(title, 48))
    if not label_parts and domain:
        label_parts.append(domain)
    label = "｜".join(part for part in label_parts if part)
    return f"{label} {url}".strip()


def _sanitize_action_evidence_rows(rows: list[str], *, limit: int = 3) -> list[str]:
    normalized_rows: list[str] = []
    seen: set[str] = set()
    for raw in rows:
        text = normalize_text(raw)
        if not text:
            continue
        urls = re.findall(r"https?://[^\s)]+", text)
        if urls:
            preferred_url = next((url for url in urls if not _is_low_value_action_url(url)), "")
            if not preferred_url:
                text = re.sub(r"https?://[^\s)]+", " ", text)
                text = re.sub(r"\s+", " ", text).strip(" ，,；;()[]")
                if not text:
                    continue
            else:
                text_without_urls = re.sub(r"https?://[^\s)]+", " ", text)
                text_without_urls = re.sub(r"\s+", " ", text_without_urls).strip(" ，,；;()[]")
                domain = extract_domain(preferred_url) or ""
                if not text_without_urls:
                    text = domain or preferred_url
                else:
                    text = f"{_truncate_sentence(text_without_urls, 64)} {preferred_url}"
        if len(text) > 140:
            text = _truncate_sentence(text, 140)
        if text in seen:
            continue
        seen.add(text)
        normalized_rows.append(text)
        if len(normalized_rows) >= max(1, limit):
            break
    return normalized_rows


def _build_action_evidence(
    report: ResearchReportDocument,
    *,
    section_aliases: tuple[str, ...],
    fallback_rows: list[str],
    limit: int = 3,
) -> list[str]:
    evidence_rows: list[str] = []
    section = _research_section(report, section_aliases)
    if section and getattr(section, "evidence_links", None):
        for link in section.evidence_links:
            formatted = _format_action_evidence_link(link)
            if formatted:
                evidence_rows.append(formatted)
    if len(evidence_rows) < limit:
        evidence_rows.extend(fallback_rows)
    return _sanitize_action_evidence_rows(evidence_rows, limit=limit)


def entity_names_from_ranked(
    ranked: list[ResearchRankedEntityOut],
    fallback_rows: list[str],
    *,
    limit: int = 3,
    deps: ResearchActionCardDependencies,
) -> list[str]:
    names = [normalize_text(item.name) for item in ranked if normalize_text(item.name)]
    if len(names) < limit:
        for row in fallback_rows:
            candidate = deps.extract_rank_entity_name(row)
            if not candidate:
                continue
            if any(
                candidate == existing
                or (len(candidate) >= 2 and len(existing) >= 2 and (candidate in existing or existing in candidate))
                for existing in names
            ):
                continue
            names.append(candidate)
            if len(names) >= limit:
                break
    return deps.dedupe_strings(names, limit)


def _pick_rows_for_entities(
    rows: list[str],
    names: list[str],
    *,
    limit: int = 3,
    deps: ResearchActionCardDependencies,
) -> list[str]:
    matched: list[str] = []
    for name in names:
        for row in rows:
            normalized_row = normalize_text(row)
            if normalized_row and name and name in normalized_row:
                matched.append(normalized_row)
    if len(matched) < limit:
        matched.extend(normalize_text(row) for row in rows if normalize_text(row))
    return deps.dedupe_strings(matched, limit)


def _derive_scope_anchor(report: ResearchReportDocument) -> str:
    for candidate in (
        *report.target_accounts,
        *report.project_distribution,
        *report.strategic_directions,
    ):
        normalized = normalize_text(candidate)
        if normalized:
            return normalized
    return normalize_text(report.research_focus or "") or normalize_text(report.keyword)


def derive_entry_window(report: ResearchReportDocument, output_language: str) -> str:
    timeline = " ".join(normalize_text(item) for item in report.tender_timeline)
    if any(token in timeline for token in ("采购意向", "预算", "立项", "规划", "前期")):
        return localized_text(
            output_language,
            {
                "zh-CN": "优先在招标前 3-6 个月入场，围绕预算、立项和需求定义建立关系。",
                "zh-TW": "優先在招標前 3-6 個月入場，圍繞預算、立項與需求定義建立關係。",
                "en": "Enter 3-6 months before the tender, focusing on budget and requirement shaping.",
            },
            "优先在招标前 3-6 个月入场，围绕预算、立项和需求定义建立关系。",
        )
    if any(token in timeline for token in ("招标", "挂网", "开标", "投标", "公告")):
        return localized_text(
            output_language,
            {
                "zh-CN": "优先在开标前 4-8 周入场，补齐伙伴、方案与资格材料。",
                "zh-TW": "優先在開標前 4-8 週入場，補齊夥伴、方案與資格材料。",
                "en": "Enter 4-8 weeks before bid opening to finalize partners, solution, and qualification materials.",
            },
            "优先在开标前 4-8 周入场，补齐伙伴、方案与资格材料。",
        )
    return localized_text(
        output_language,
        {
            "zh-CN": "按同类项目常见节奏，建议至少提前一个预算周期建立关系并验证需求。",
            "zh-TW": "按同類專案常見節奏，建議至少提前一個預算週期建立關係並驗證需求。",
            "en": "Based on typical project cycles, establish contact at least one budget cycle earlier.",
        },
        "按同类项目常见节奏，建议至少提前一个预算周期建立关系并验证需求。",
    )


def _derive_visit_sequence(
    report: ResearchReportDocument,
    output_language: str,
    *,
    deps: ResearchActionCardDependencies,
) -> list[str]:
    departments = deps.dedupe_strings(report.target_departments, 8)
    ordered: list[str] = []
    category_map = (
        ("业务/场景发起部门", ("业务", "运营", "政务服务", "应用", "建设管理", "事业发展")),
        ("信息化/数字化部门", ("信息中心", "信息化部", "数字化部", "科技部", "数据局", "数据资源局")),
        ("预算/财务部门", ("财务", "计划财务", "预算", "投资管理")),
        ("采购/招采部门", ("采购", "招标", "招采", "集采")),
        ("领导/办公室", ("书记", "市长", "主任", "局长", "厅长", "办公室")),
    )
    for label, tokens in category_map:
        matched = next((item for item in departments if any(token in item for token in tokens)), "")
        if matched:
            ordered.append(f"{label}：{matched}")
    if not ordered:
        ordered = [
            localized_text(
                output_language,
                {
                    "zh-CN": "先找业务/场景发起人确认刚需，再找信息化/数字化部门验证路线。",
                    "zh-TW": "先找業務/場景發起人確認剛需，再找資訊化/數位化部門驗證路線。",
                    "en": "Start with business owners, then validate the route with digital or IT teams.",
                },
                "先找业务/场景发起人确认刚需，再找信息化/数字化部门验证路线。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "第二步补预算与财务依据，第三步再进入采购/招采。",
                    "zh-TW": "第二步補預算與財務依據，第三步再進入採購/招採。",
                    "en": "Second, validate budget ownership, and only then approach procurement.",
                },
                "第二步补预算与财务依据，第三步再进入采购/招采。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "最后争取领导层背书，用政策、预算和标杆案例统一叙事。",
                    "zh-TW": "最後爭取領導層背書，用政策、預算與標竿案例統一敘事。",
                    "en": "Finally seek leadership sponsorship using policy, budget, and benchmark cases.",
                },
                "最后争取领导层背书，用政策、预算和标杆案例统一叙事。",
            ),
        ]
    return ordered[:4]


def _derive_competitor_weaknesses(
    report: ResearchReportDocument,
    competitor_names: list[str],
    *,
    deps: ResearchActionCardDependencies,
) -> list[str]:
    analysis = [normalize_text(item) for item in report.competition_analysis if normalize_text(item)]
    results: list[str] = []
    for name in competitor_names:
        matched = next((item for item in analysis if name in item), "")
        if matched:
            results.append(matched)
            continue
        if any(token in name for token in ("云", "平台", "科技", "智能", "信息")):
            results.append(f"{name}：公开线索更偏平台/产品叙事，可能在本地生态、场景定制和跨部门协同上存在短板。")
        else:
            results.append(f"{name}：公开线索显示其在同类项目活跃，但差异化叙事、区域伙伴和本地交付深度仍需重点验证。")
    return deps.dedupe_strings(results, 3)


def _build_contact_and_partner_steps(
    *,
    buyers: list[str],
    contacts: list[str],
    partners: list[str],
    output_language: str,
) -> list[str]:
    steps: list[str] = []
    if buyers:
        steps.append(f"优先围绕 {', '.join(buyers[:3])} 建立首轮名单，先确认业务牵头人与信息化接口人。")
    if contacts:
        steps.append(f"优先核验公开触达入口：{'；'.join(contacts[:3])}")
    else:
        steps.append(
            localized_text(
                output_language,
                {
                    "zh-CN": "先从甲方官网“联系我们”、采购公告联系人和投资者关系入口核验公开触达方式。",
                    "zh-TW": "先從甲方官網「聯絡我們」、採購公告聯絡人與投資者關係入口核驗公開觸達方式。",
                    "en": "Validate public contact channels through official contact pages and procurement notices.",
                },
                "先从甲方官网“联系我们”、采购公告联系人和投资者关系入口核验公开触达方式。",
            )
        )
    if partners:
        steps.append(f"同步借力 {', '.join(partners[:3])} 作为牵线或联合调研伙伴，而不是单纯产品供应商。")
    return steps[:4]


def _build_phased_steps(
    *,
    short_term: list[str],
    mid_term: list[str],
    long_term: list[str],
    deps: ResearchActionCardDependencies,
) -> list[str]:
    phased: list[str] = []
    if short_term:
        phased.append(f"短期（1-2周）：{'；'.join(deps.dedupe_strings(short_term, 2))}")
    if mid_term:
        phased.append(f"中期（2-6周）：{'；'.join(deps.dedupe_strings(mid_term, 2))}")
    if long_term:
        phased.append(f"长期（6周以上）：{'；'.join(deps.dedupe_strings(long_term, 2))}")
    return phased[:3]


def _has_minimum_action_card_inputs(
    report: ResearchReportDocument,
    *,
    deps: ResearchActionCardDependencies,
) -> bool:
    theme_labels = deps.theme_labels_from_scope(
        {
            "industries": list(getattr(getattr(report, "source_diagnostics", None), "scope_industries", []) or []),
            "regions": list(getattr(getattr(report, "source_diagnostics", None), "scope_regions", []) or []),
            "clients": list(getattr(getattr(report, "source_diagnostics", None), "scope_clients", []) or []),
        },
        keyword=report.keyword,
        research_focus=report.research_focus,
    )
    buyers = deps.dedupe_strings(
        [
            normalize_text(name)
            for name in [
                *entity_names_from_ranked(report.top_target_accounts, report.target_accounts, limit=3, deps=deps),
                *(normalize_text(item) for item in report.target_accounts if normalize_text(item)),
            ]
            if normalize_text(name)
            and not deps.looks_like_scope_prompt_noise(normalize_text(name))
            and not deps.looks_like_placeholder_entity_name(normalize_text(name))
            and not deps.looks_like_fragment_entity_name(normalize_text(name))
            and not deps.contains_low_value_entity_token(normalize_text(name))
            and (
                deps.is_trustworthy_scope_client_name(normalize_text(name), theme_labels=theme_labels)
                or deps.is_theme_aligned_entity_name(normalize_text(name), role="target", theme_labels=theme_labels)
                or deps.is_lightweight_entity_name(normalize_text(name))
            )
        ],
        3,
    )
    budget_rows = [row for row in report.budget_signals if deps.is_actionable_budget_row(row)]
    timing_rows = [row for row in report.tender_timeline if deps.is_summary_fact_row(row)]
    return bool(buyers) and bool(budget_rows or timing_rows)


def build_research_action_cards(
    report: ResearchReportDocument,
    *,
    deps: ResearchActionCardDependencies,
) -> list[ResearchActionCardOut]:
    output_language = report.output_language
    if deps.is_low_signal_execution_report(report) and not _has_minimum_action_card_inputs(report, deps=deps):
        diagnostics = report.source_diagnostics if getattr(report, "source_diagnostics", None) else ResearchSourceDiagnosticsOut()
        official_ratio = round(float(diagnostics.official_source_ratio or 0.0) * 100)
        evidence_mode_label = normalize_text(diagnostics.evidence_mode_label) or normalize_text(diagnostics.evidence_mode) or localized_text(
            output_language,
            {"zh-CN": "兜底候选", "zh-TW": "兜底候選", "en": "Fallback"},
            "兜底候选",
        )
        return [
            ResearchActionCardOut(
                action_type="evidence_recovery",
                priority="high",
                title=localized_text(
                    output_language,
                    {
                        "zh-CN": "补证收口行动卡",
                        "zh-TW": "補證收口行動卡",
                        "en": "Evidence Recovery Card",
                    },
                    "补证收口行动卡",
                ),
                summary=localized_text(
                    output_language,
                    {
                        "zh-CN": "当前证据门槛不足，先收敛主题并补官方源、采购线索和联系人，再决定是否进入正式推进。",
                        "zh-TW": "目前證據門檻不足，先收斂主題並補官方源、採購線索與聯絡人，再決定是否進入正式推進。",
                        "en": "Evidence is below threshold. Narrow the topic and recover official, procurement, and contact evidence before moving into formal execution.",
                    },
                    "当前证据门槛不足，先收敛主题并补官方源、采购线索和联系人，再决定是否进入正式推进。",
                ),
                recommended_steps=[
                    localized_text(
                        output_language,
                        {
                            "zh-CN": "先把主题收敛到 1-2 个具体账户或项目编号，避免继续沿用泛行业结论。",
                            "zh-TW": "先把主題收斂到 1-2 個具體帳戶或專案編號，避免繼續沿用泛產業結論。",
                            "en": "Reduce the topic to 1-2 concrete buyers or project IDs instead of carrying forward broad industry claims.",
                        },
                        "先把主题收敛到 1-2 个具体账户或项目编号，避免继续沿用泛行业结论。",
                    ),
                    localized_text(
                        output_language,
                        {
                            "zh-CN": "补官网、公告、采购和投资者关系页面，至少拿到 1 条官方或准官方来源。",
                            "zh-TW": "補官網、公告、採購與投資者關係頁面，至少拿到 1 條官方或準官方來源。",
                            "en": "Add official pages, notices, procurement records, and IR pages until you have at least one official or near-official source.",
                        },
                        "补官网、公告、采购和投资者关系页面，至少拿到 1 条官方或准官方来源。",
                    ),
                    localized_text(
                        output_language,
                        {
                            "zh-CN": "补组织入口、联系人和预算窗口，再回到正式研报与行动卡生成。",
                            "zh-TW": "補組織入口、聯絡人與預算窗口，再回到正式研報與行動卡生成。",
                            "en": "Recover buyer-org, contact, and budget-window evidence before regenerating the formal report and action cards.",
                        },
                        "补组织入口、联系人和预算窗口，再回到正式研报与行动卡生成。",
                    ),
                ],
                evidence=[
                    localized_text(
                        output_language,
                        {"zh-CN": f"当前来源数：{report.source_count}", "zh-TW": f"目前來源數：{report.source_count}", "en": f"Current source count: {report.source_count}"},
                        f"当前来源数：{report.source_count}",
                    ),
                    localized_text(
                        output_language,
                        {"zh-CN": f"官方源占比：{official_ratio}%", "zh-TW": f"官方源占比：{official_ratio}%", "en": f"Official-source ratio: {official_ratio}%"},
                        f"官方源占比：{official_ratio}%",
                    ),
                    localized_text(
                        output_language,
                        {"zh-CN": f"证据模式：{evidence_mode_label}", "zh-TW": f"證據模式：{evidence_mode_label}", "en": f"Evidence mode: {evidence_mode_label}"},
                        f"证据模式：{evidence_mode_label}",
                    ),
                ],
                target_persona=localized_text(
                    output_language,
                    {
                        "zh-CN": "研究员、行业顾问、销售负责人",
                        "zh-TW": "研究員、產業顧問、銷售負責人",
                        "en": "Researchers, industry advisors, and sales owners",
                    },
                    "研究员、行业顾问、销售负责人",
                ),
                execution_window=localized_text(
                    output_language,
                    {
                        "zh-CN": "下一轮输出前 1-2 天内完成",
                        "zh-TW": "下一輪輸出前 1-2 天內完成",
                        "en": "Complete within 1-2 days before the next report run.",
                    },
                    "下一轮输出前 1-2 天内完成",
                ),
                deliverable=localized_text(
                    output_language,
                    {
                        "zh-CN": "补证清单、官方源链接、联系人与预算窗口核验结果",
                        "zh-TW": "補證清單、官方源連結、聯絡人與預算窗口核驗結果",
                        "en": "Evidence backlog, official links, and verified contact / budget-window results",
                    },
                    "补证清单、官方源链接、联系人与预算窗口核验结果",
                ),
            )
        ]
    solution_design = _research_section_items(report, ("解决方案设计", "解決方案設計", "solution design"))
    sales_strategy = _research_section_items(report, ("销售策略", "銷售策略", "sales strategy"))
    bidding_strategy = _research_section_items(report, ("投标规划", "投標規劃", "bidding strategy"))
    outreach_strategy = _research_section_items(report, ("陌生拜访", "陌生拜訪", "outreach strategy"))
    ecosystem_strategy = _research_section_items(report, ("生态伙伴", "生態夥伴", "ecosystem strategy"))
    commercial_opportunities = _research_section_items(report, ("项目与商机", "專案與商機", "opportunity"))
    next_actions = _research_section_items(report, ("下一步行动", "下一步行動", "next actions"))
    risks = _research_section_items(report, ("风险提示", "風險提示", "risks"))

    competition = [normalize_text(item) for item in report.competition_analysis if normalize_text(item)]
    buyer_peers = [normalize_text(item) for item in report.client_peer_moves if normalize_text(item)]
    winner_peers = [normalize_text(item) for item in report.winner_peer_moves if normalize_text(item)]
    outlook = [normalize_text(item) for item in report.five_year_outlook if normalize_text(item)]
    buyers = entity_names_from_ranked(report.top_target_accounts, report.target_accounts, limit=3, deps=deps)
    competitors = entity_names_from_ranked(report.top_competitors, report.competitor_profiles, limit=3, deps=deps)
    partners = entity_names_from_ranked(report.top_ecosystem_partners, report.ecosystem_partners, limit=3, deps=deps)
    contacts = _pick_rows_for_entities(report.public_contact_channels, buyers + partners, limit=3, deps=deps) or deps.dedupe_strings(report.public_contact_channels, 3)
    department_rows = _pick_rows_for_entities(report.target_departments, buyers, limit=3, deps=deps) or deps.dedupe_strings(report.target_departments, 3)
    budget_rows = deps.dedupe_strings(report.budget_signals, 3)
    timeline_rows = deps.dedupe_strings(report.tender_timeline, 3)
    benchmark_rows = deps.dedupe_strings(report.benchmark_cases, 3)
    partner_rows = _pick_rows_for_entities(report.ecosystem_partners, partners, limit=3, deps=deps) or deps.dedupe_strings(report.ecosystem_partners, 3)
    competitor_weaknesses = _derive_competitor_weaknesses(report, competitors, deps=deps)
    visit_sequence = _derive_visit_sequence(report, output_language, deps=deps)
    scope_anchor = _derive_scope_anchor(report)
    entry_window = derive_entry_window(report, output_language)

    cards: list[ResearchActionCardOut] = []

    def add_card(
        *,
        action_type: str,
        priority: str,
        title_map: dict[str, str],
        primary: list[str],
        secondary: list[str],
        long_horizon: list[str],
        evidence: list[str],
        fallback: str,
        target_persona_map: dict[str, str],
        execution_window_map: dict[str, str],
        deliverable_map: dict[str, str],
    ) -> None:
        steps = _build_phased_steps(
            short_term=primary,
            mid_term=secondary,
            long_term=long_horizon,
            deps=deps,
        )
        if not steps and not evidence and not fallback:
            return
        cards.append(
            ResearchActionCardOut(
                action_type=action_type,
                priority=priority,
                title=localized_text(output_language, title_map, title_map.get("zh-CN", "行动卡")),
                summary=_build_action_summary(primary, secondary, fallback=fallback),
                recommended_steps=steps,
                evidence=[item for item in evidence if item][:3],
                target_persona=localized_text(
                    output_language,
                    target_persona_map,
                    target_persona_map.get("zh-CN", ""),
                ),
                execution_window=localized_text(
                    output_language,
                    execution_window_map,
                    execution_window_map.get("zh-CN", ""),
                ),
                deliverable=localized_text(
                    output_language,
                    deliverable_map,
                    deliverable_map.get("zh-CN", ""),
                ),
            )
        )

    add_card(
        action_type="buyer_entry",
        priority="high",
        title_map={
            "zh-CN": "甲方建联行动卡",
            "zh-TW": "甲方建聯行動卡",
            "en": "Buyer Entry Card",
        },
        primary=_build_contact_and_partner_steps(
            buyers=buyers,
            contacts=contacts,
            partners=partners,
            output_language=output_language,
        ),
        secondary=department_rows or budget_rows or commercial_opportunities,
        long_horizon=[
            entry_window,
            f"围绕 {scope_anchor} 形成甲方分层名单，并持续补预算、项目代号和公开联系人。",
        ],
        evidence=_build_action_evidence(
            report,
            section_aliases=("项目与商机", "專案與商機", "opportunity", "销售策略", "銷售策略", "sales strategy"),
            fallback_rows=budget_rows + timeline_rows + buyer_peers,
        ),
        fallback=f"围绕 {scope_anchor} 收敛 3 类甲方、公开触达方式与预算口径，优先做首轮建联。",
        target_persona_map={
            "zh-CN": "客户经理、区域销售、行业顾问",
            "zh-TW": "客戶經理、區域銷售、產業顧問",
            "en": "Account managers, regional sales, and industry advisors",
        },
        execution_window_map={
            "zh-CN": entry_window,
            "zh-TW": entry_window,
            "en": entry_window,
        },
        deliverable_map={
            "zh-CN": "甲方名单、公开联系入口、建联话术和首轮拜访计划",
            "zh-TW": "甲方名單、公開聯絡入口、建聯話術與首輪拜訪計畫",
            "en": "Buyer list, public contact routes, outreach script, and first-visit plan",
        },
    )
    add_card(
        action_type="solution_differentiation",
        priority="high",
        title_map={
            "zh-CN": "差异化方案行动卡",
            "zh-TW": "差異化方案行動卡",
            "en": "Differentiated Solution Card",
        },
        primary=competitor_weaknesses or solution_design,
        secondary=benchmark_rows or competition or report.flagship_products,
        long_horizon=[
            "把竞品短板转成标书和汇报中的差异化章节，提前准备标杆案例与 ROI 证明。",
            f"围绕 {scope_anchor} 把本地生态、场景定制、交付节奏做成 3 条核心卖点。",
        ],
        evidence=_build_action_evidence(
            report,
            section_aliases=("解决方案设计", "解決方案設計", "solution design"),
            fallback_rows=competition + benchmark_rows + report.flagship_products,
        ),
        fallback=f"围绕 {scope_anchor} 的预算、决策部门和竞品线索，设计更强调场景定制、本地生态和交付节奏的方案。",
        target_persona_map={
            "zh-CN": "解决方案架构师、售前经理、产品经理",
            "zh-TW": "解決方案架構師、售前經理、產品經理",
            "en": "Solution architects, pre-sales managers, and product leads",
        },
        execution_window_map={
            "zh-CN": "未来 3-5 个工作日完成对标差异化方案和价值假设。",
            "zh-TW": "未來 3-5 個工作日完成對標差異化方案與價值假設。",
            "en": "Draft differentiated solution hypotheses within 3-5 business days.",
        },
        deliverable_map={
            "zh-CN": "竞品短板清单、差异化卖点和标杆案例对照",
            "zh-TW": "競品短板清單、差異化賣點與標竿案例對照",
            "en": "Competitor gaps, differentiated messaging, and benchmark comparisons",
        },
    )
    add_card(
        action_type="project_timing",
        priority="high",
        title_map={
            "zh-CN": "入场时钟与投标节奏卡",
            "zh-TW": "入場時鐘與投標節奏卡",
            "en": "Entry Timing and Bid Rhythm Card",
        },
        primary=timeline_rows or budget_rows or report.project_distribution,
        secondary=next_actions or bidding_strategy or outlook,
        long_horizon=[
            "持续跟踪采购意向、预算草案、立项批复、二三期扩容与试点转正信号。",
            "把伙伴、资质、POC、案例和价格策略按标前节奏提前排好。",
        ],
        evidence=_build_action_evidence(
            report,
            section_aliases=("投标规划", "投標規劃", "bidding strategy", "下一步行动", "下一步行動", "next actions"),
            fallback_rows=timeline_rows + budget_rows + winner_peers,
        ),
        fallback=entry_window,
        target_persona_map={
            "zh-CN": "销售负责人、投标经理、项目经理",
            "zh-TW": "銷售負責人、投標經理、專案經理",
            "en": "Sales owners, bid managers, and project managers",
        },
        execution_window_map={
            "zh-CN": entry_window,
            "zh-TW": entry_window,
            "en": entry_window,
        },
        deliverable_map={
            "zh-CN": "项目阶段判断、入场时间表和标前资源排期",
            "zh-TW": "專案階段判斷、入場時間表與標前資源排期",
            "en": "Project-stage view, entry timeline, and pre-bid resource plan",
        },
    )
    add_card(
        action_type="visit_sequence",
        priority="medium",
        title_map={
            "zh-CN": "年轻销售拜访顺序卡",
            "zh-TW": "年輕銷售拜訪順序卡",
            "en": "Visit Sequence Card for Junior Sales",
        },
        primary=visit_sequence,
        secondary=department_rows or report.leadership_focus or sales_strategy,
        long_horizon=[
            "在拿到业务需求和预算口径后，再争取领导层背书，避免过早越级。",
            "每轮拜访结束后，把新拿到的部门、联系人和顾虑回写到名单库，动态调整顺序。",
        ],
        evidence=_build_action_evidence(
            report,
            section_aliases=("陌生拜访", "陌生拜訪", "outreach strategy", "销售策略", "銷售策略", "sales strategy"),
            fallback_rows=department_rows + report.leadership_focus + report.public_contact_channels,
        ),
        fallback=f"围绕 {scope_anchor}，先验证业务发起部门，再进入信息化/预算/招采，最后争取领导背书。",
        target_persona_map={
            "zh-CN": "年轻销售、BD、区域客户经理",
            "zh-TW": "年輕銷售、BD、區域客戶經理",
            "en": "Junior sales, BD, and regional account managers",
        },
        execution_window_map={
            "zh-CN": "先在 1 周内完成部门映射，再按 2-3 周节奏推进多角色建联。",
            "zh-TW": "先在 1 週內完成部門映射，再按 2-3 週節奏推進多角色建聯。",
            "en": "Map departments in week 1, then sequence multi-role outreach over 2-3 weeks.",
        },
        deliverable_map={
            "zh-CN": "拜访顺序、角色画像和每一层的沟通目标",
            "zh-TW": "拜訪順序、角色畫像與每一層的溝通目標",
            "en": "Visit order, stakeholder map, and role-specific communication goals",
        },
    )
    add_card(
        action_type="ecosystem_bridge",
        priority="medium",
        title_map={
            "zh-CN": "生态牵线行动卡",
            "zh-TW": "生態牽線行動卡",
            "en": "Ecosystem Bridge Card",
        },
        primary=partner_rows or ecosystem_strategy,
        secondary=contacts or winner_peers or buyer_peers,
        long_horizon=[
            "按牵线价值、区域影响力和联合交付能力排序，筛掉纯产品售卖型公司。",
            "将伙伴分成咨询牵线方、区域总包、行业集成商三组，分别设计合作说法。",
        ],
        evidence=_build_action_evidence(
            report,
            section_aliases=("生态伙伴", "生態夥伴", "ecosystem strategy"),
            fallback_rows=partner_rows + winner_peers + report.public_contact_channels,
        ),
        fallback=f"优先筛出能牵线、联合调研或咨询集成的伙伴，为 {scope_anchor} 构建进入路径。",
        target_persona_map={
            "zh-CN": "生态合作经理、渠道负责人、区域销售",
            "zh-TW": "生態合作經理、渠道負責人、區域銷售",
            "en": "Ecosystem managers, channel owners, and regional sales",
        },
        execution_window_map={
            "zh-CN": "未来 1 周内确定 2-3 家能协同切入甲方的伙伴，并完成分工。",
            "zh-TW": "未來 1 週內確定 2-3 家能協同切入甲方的夥伴，並完成分工。",
            "en": "Within one week, confirm 2-3 partners that can open doors to the buyer.",
        },
        deliverable_map={
            "zh-CN": "伙伴名单、公开联系入口、联合拜访与联合方案建议",
            "zh-TW": "夥伴名單、公開聯絡入口、聯合拜訪與聯合方案建議",
            "en": "Partner list, public contact routes, and a joint-visit plan",
        },
    )
    add_card(
        action_type="two_week_attack_plan",
        priority="high",
        title_map={
            "zh-CN": "两周推进作战卡",
            "zh-TW": "兩週推進作戰卡",
            "en": "Two-week Execution Card",
        },
        primary=(next_actions or commercial_opportunities or solution_design)[:3],
        secondary=risks or benchmark_rows or contacts,
        long_horizon=[
            "如果前两周建联有效，立即进入方案共创、伙伴绑定和标前测试准备。",
            "如果证据仍弱，则回到区域/甲方池继续扩搜，不要直接进入低质量投标。",
        ],
        evidence=_build_action_evidence(
            report,
            section_aliases=("下一步行动", "下一步行動", "next actions", "项目与商机", "專案與商機", "opportunity"),
            fallback_rows=benchmark_rows + budget_rows + timeline_rows,
        ),
        fallback=f"先完成甲方筛选、方案差异化和伙伴分工，再决定是否进入标前排期。",
        target_persona_map={
            "zh-CN": "区域负责人、销售经理、售前经理",
            "zh-TW": "區域負責人、銷售經理、售前經理",
            "en": "Regional leads, sales managers, and pre-sales managers",
        },
        execution_window_map={
            "zh-CN": "未来两周内，完成名单、触达、方案和标前资源准备。",
            "zh-TW": "未來兩週內，完成名單、觸達、方案與標前資源準備。",
            "en": "Within two weeks, finish targeting, outreach, solution framing, and pre-bid preparation.",
        },
        deliverable_map={
            "zh-CN": "两周推进看板、角色分工、拜访纪要模板和下一轮判断标准",
            "zh-TW": "兩週推進看板、角色分工、拜訪紀要模板與下一輪判斷標準",
            "en": "A two-week execution board, role split, visit memo template, and next-step criteria",
        },
    )
    return cards
