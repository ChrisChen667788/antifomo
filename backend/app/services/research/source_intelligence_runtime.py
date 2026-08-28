from __future__ import annotations

from collections import Counter
import re

from app.services.content_extractor import normalize_text
from app.services.language import localized_text
from app.services.research.entity_policy import (
    DEPARTMENT_PATTERN,
    EMAIL_PATTERN,
    GENERIC_CONTENT_DOMAINS,
    ORG_PATTERN,
    PHONE_PATTERN,
    REGION_TOKENS,
    is_plausible_entity_name,
    text_has_industry_conflict,
)
from app.services.research.entity_ranking_runtime import (
    build_entity_specific_team_rows,
    text_has_region_conflict,
    truncate_text,
)
from app.services.research.report_common import dedupe_strings
from app.services.research.report_row_quality import MONEY_PATTERN
from app.services.research.ranking_source_utility import (
    RankingSourceUtilityDependencies,
    extract_department_rows,
    extract_key_people_rows,
    extract_public_contact_rows,
    rank_org_rows,
)
from app.services.research.scope_entity_runtime_dependencies import scope_entity_runtime_functions
from app.services.research.scope_hints import expand_region_scope_terms
from app.services.research.source_documents import SourceDocument, source_document_text
from app.services.research.source_intelligence import (
    SourceIntelligenceDependencies,
    build_source_intelligence as build_source_intelligence_with_dependencies,
)


PERSON_ROLE_PATTERN = re.compile(
    r"([\u4e00-\u9fa5]{2,4})(?:同志)?(?:在[^。；;\n]{0,12})?"
    r"(?:表示|指出|强调|要求|担任|出席|主持|提到|介绍)?"
    r"[^。；;\n]{0,18}?"
    r"(书记|市长|局长|厅长|主任|董事长|总经理|总裁|副总裁|院长|校长|负责人)"
)

def _extract_matching_sentences(
    sources: list[SourceDocument],
    *,
    keywords: tuple[str, ...],
    limit: int,
    scope_hints: dict[str, object] | None = None,
) -> list[str]:
    sentences: list[str] = []
    normalized_keywords = tuple(normalize_text(item).lower() for item in keywords if normalize_text(item))
    for source in sources:
        chunks = re.split(r"[。！？!?；;\n]", source_document_text(source))
        for chunk in chunks:
            text = normalize_text(chunk)
            lowered = text.lower()
            if not text:
                continue
            if any(keyword in lowered for keyword in normalized_keywords):
                if scope_hints and text_has_region_conflict(text, scope_hints=scope_hints):
                    continue
                if scope_hints and text_has_industry_conflict(text, scope_hints=scope_hints):
                    continue
                sentences.append(truncate_text(text, 110))
    return dedupe_strings(sentences, limit)

def _extract_money_signals(
    sources: list[SourceDocument],
    *,
    limit: int,
    scope_hints: dict[str, object] | None = None,
) -> list[str]:
    signals: list[str] = []
    for source in sources:
        text = source_document_text(source)
        for match in MONEY_PATTERN.finditer(text):
            start = max(0, match.start() - 18)
            end = min(len(text), match.end() + 26)
            candidate = truncate_text(text[start:end], 110)
            if scope_hints and text_has_region_conflict(candidate, scope_hints=scope_hints):
                continue
            if scope_hints and text_has_industry_conflict(candidate, scope_hints=scope_hints):
                continue
            signals.append(candidate)
    if not signals:
        signals = _extract_matching_sentences(
            sources,
            keywords=("预算", "投资", "金额", "经费", "财政投入"),
            limit=limit,
            scope_hints=scope_hints,
        )
    return dedupe_strings(signals, limit)

def _extract_region_distribution(
    sources: list[SourceDocument],
    *,
    limit: int,
    scope_hints: dict[str, object] | None = None,
) -> list[str]:
    counter: Counter[str] = Counter()
    region_examples: dict[str, str] = {}
    allowed_regions = set()
    if scope_hints:
        allowed_regions = {
            item.lower()
            for item in expand_region_scope_terms(
                [normalize_text(str(region)) for region in scope_hints.get("regions", []) if normalize_text(str(region))]
            )
        }
    for source in sources:
        text = source_document_text(source)
        for region in REGION_TOKENS:
            if allowed_regions and region.lower() not in allowed_regions:
                continue
            if region in text:
                counter[region] += 1
                region_examples.setdefault(region, truncate_text(source.title, 64))
    rows = [
        f"{region}：公开线索 {count} 条，代表样本 {region_examples.get(region, '待补充')}"
        for region, count in counter.most_common(limit)
    ]
    return dedupe_strings(rows, limit)

def _build_industry_methodology_rows(
    *,
    scope_hints: dict[str, object],
    output_language: str,
    scope_anchor: str,
) -> dict[str, list[str]]:
    profile = normalize_text(str(scope_hints.get("industry_methodology_profile", "")))
    framework = normalize_text(str(scope_hints.get("industry_methodology_framework", "")))
    if not profile and not framework:
        return {}
    solution_lenses = dedupe_strings(scope_hints.get("industry_methodology_solution_lenses", []) or [], 4)
    sales_lenses = dedupe_strings(scope_hints.get("industry_methodology_sales_lenses", []) or [], 4)
    bidding_lenses = dedupe_strings(scope_hints.get("industry_methodology_bidding_lenses", []) or [], 4)
    outreach_lenses = dedupe_strings(scope_hints.get("industry_methodology_outreach_lenses", []) or [], 4)
    ecosystem_lenses = dedupe_strings(scope_hints.get("industry_methodology_ecosystem_lenses", []) or [], 4)
    questions = dedupe_strings(scope_hints.get("industry_methodology_questions", []) or [], 4)
    label = profile or scope_anchor
    return {
        "industry_brief": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"{label} 建议按“{framework or '需求拆解 -> 预算验证 -> 招采节奏 -> 扩容路径'}”来组织研究，而不是只做泛行业素材汇总。",
                    "zh-TW": f"{label} 建議按「{framework or '需求拆解 -> 預算驗證 -> 招採節奏 -> 擴容路徑'}」來組織研究，而不是只做泛行業素材彙整。",
                    "en": f"For {label}, organize the memo around {framework or 'demand, budget, procurement timing, and expansion path'} instead of generic market commentary.",
                },
                f"{label} 建议按“{framework or '需求拆解 -> 预算验证 -> 招采节奏 -> 扩容路径'}”来组织研究，而不是只做泛行业素材汇总。",
            )
        ],
        "solution_design": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"方案设计优先围绕 {label} 的 {(' / '.join(solution_lenses) or '场景闭环 / 分期实施 / 集成改造 / 扩容路径')} 拆解。",
                    "zh-TW": f"方案設計優先圍繞 {label} 的 {(' / '.join(solution_lenses) or '場景閉環 / 分期實施 / 整合改造 / 擴容路徑')} 拆解。",
                    "en": f"Solution design should emphasize {', '.join(solution_lenses) or 'use-case closure, phased rollout, integration, and expansion'} for {label}.",
                },
                f"方案设计优先围绕 {label} 的 {(' / '.join(solution_lenses) or '场景闭环 / 分期实施 / 集成改造 / 扩容路径')} 拆解。",
            )
        ],
        "sales_strategy": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"销售推进优先验证 {(' / '.join(sales_lenses) or '牵头部门 / 预算归口 / 年度节点 / 扩容窗口')}，避免只聊产品能力。",
                    "zh-TW": f"銷售推進優先驗證 {(' / '.join(sales_lenses) or '牽頭部門 / 預算歸口 / 年度節點 / 擴容窗口')}，避免只聊產品能力。",
                    "en": f"Sales planning should validate {', '.join(sales_lenses) or 'the buyer lead, budget owner, planning cycle, and expansion window'} before pitching product.",
                },
                f"销售推进优先验证 {(' / '.join(sales_lenses) or '牵头部门 / 预算归口 / 年度节点 / 扩容窗口')}，避免只聊产品能力。",
            )
        ],
        "bidding_strategy": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"投标布局优先核验 {(' / '.join(bidding_lenses) or '采购意向 / 总分包结构 / 资质要求 / 交付壁垒')}。",
                    "zh-TW": f"投標布局優先核驗 {(' / '.join(bidding_lenses) or '採購意向 / 總分包結構 / 資質要求 / 交付壁壘')}。",
                    "en": f"Bidding planning should verify {', '.join(bidding_lenses) or 'intent notices, prime/subcontract structure, qualification requirements, and delivery barriers'}.",
                },
                f"投标布局优先核验 {(' / '.join(bidding_lenses) or '采购意向 / 总分包结构 / 资质要求 / 交付壁垒')}。",
            )
        ],
        "outreach_strategy": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"拜访顺序建议按 {(' / '.join(outreach_lenses) or '牵头部门 -> 预算归口 -> 采购执行 -> 落地部门')} 展开。",
                    "zh-TW": f"拜訪順序建議按 {(' / '.join(outreach_lenses) or '牽頭部門 -> 預算歸口 -> 採購執行 -> 落地部門')} 展開。",
                    "en": f"Outreach should follow {', '.join(outreach_lenses) or 'business lead, budget owner, procurement, then implementation teams'}.",
                },
                f"拜访顺序建议按 {(' / '.join(outreach_lenses) or '牵头部门 -> 预算归口 -> 采购执行 -> 落地部门')} 展开。",
            )
        ],
        "ecosystem_strategy": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"生态优先围绕 {(' / '.join(ecosystem_lenses) or '总包 / 集成 / 顾问 / 本地交付')} 建立牵线链路。",
                    "zh-TW": f"生態優先圍繞 {(' / '.join(ecosystem_lenses) or '總包 / 整合 / 顧問 / 在地交付')} 建立牽線鏈路。",
                    "en": f"Ecosystem mapping should prioritize {', '.join(ecosystem_lenses) or 'primes, integrators, advisors, and local delivery partners'}.",
                },
                f"生态优先围绕 {(' / '.join(ecosystem_lenses) or '总包 / 集成 / 顾问 / 本地交付')} 建立牵线链路。",
            )
        ],
        "next_actions": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"先补证这几个问题：{'；'.join(questions) if questions else '锁定牵头部门、预算口径、招采窗口和扩容路径'}。",
                    "zh-TW": f"先補證這幾個問題：{'；'.join(questions) if questions else '鎖定牽頭部門、預算口徑、招採窗口與擴容路徑'}。",
                    "en": f"First validate these questions: {'; '.join(questions) if questions else 'buyer lead, budget line, procurement window, and expansion path'}.",
                },
                f"先补证这几个问题：{'；'.join(questions) if questions else '锁定牵头部门、预算口径、招采窗口和扩容路径'}。",
            )
        ],
    }

def _scope_insufficient_rows(
    *,
    output_language: str,
    scope_hints: dict[str, object],
    dimension_label: str,
    limit: int,
) -> list[str]:
    anchor = normalize_text(str(scope_hints.get("anchor_text", "")))
    scope_text = anchor or localized_text(
        output_language,
        {
            "zh-CN": "当前关键词范围",
            "zh-TW": "目前關鍵詞範圍",
            "en": "the current keyword scope",
        },
        "当前关键词范围",
    )
    templates = localized_text(
        output_language,
        {
            "zh-CN": f"当前证据不足：建议继续补充 {scope_text} 的 {dimension_label} 公开线索。",
            "zh-TW": f"目前證據不足：建議繼續補充 {scope_text} 的 {dimension_label} 公開線索。",
            "en": f"Current evidence is insufficient: expand public evidence for {dimension_label} within {scope_text}.",
        },
        f"当前证据不足：建议继续补充 {scope_text} 的 {dimension_label} 公开线索。",
    )
    followups = [
        localized_text(
            output_language,
            {
                "zh-CN": f"建议追加政府采购、公共资源交易、上市公告和行业媒体对 {scope_text} 的交叉检索。",
                "zh-TW": f"建議追加政府採購、公共資源交易、上市公告與產業媒體對 {scope_text} 的交叉檢索。",
                "en": f"Add government procurement, public resource exchange, filings, and media cross-searches around {scope_text}.",
            },
            f"建议追加政府采购、公共资源交易、上市公告和行业媒体对 {scope_text} 的交叉检索。",
        ),
        localized_text(
            output_language,
            {
                "zh-CN": f"若需形成前三名单，建议继续加入甲方全称、区域或项目代号后重试。",
                "zh-TW": f"若需形成前三名單，建議加入甲方全稱、區域或專案代號後重試。",
                "en": "To derive a top-3 list, add the buyer full name, region, or project code and rerun.",
            },
            "若需形成前三名单，建议继续加入甲方全称、区域或项目代号后重试。",
        ),
    ]
    return dedupe_strings([templates] + followups, limit)

def _build_dimension_fallback_rows(
    *,
    output_language: str,
    scope_hints: dict[str, object],
    dimension_key: str,
    dimension_label: str,
    limit: int,
) -> list[str]:
    anchor = normalize_text(str(scope_hints.get("anchor_text", "")))
    regions = [normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    industries = [normalize_text(str(item)) for item in scope_hints.get("industries", []) if normalize_text(str(item))]
    clients = [normalize_text(str(item)) for item in scope_hints.get("clients", []) if normalize_text(str(item))]
    region_text = "、".join(regions[:2]) or localized_text(
        output_language,
        {"zh-CN": "重点区域", "zh-TW": "重點區域", "en": "priority regions"},
        "重点区域",
    )
    industry_text = "、".join(industries[:2]) or anchor or localized_text(
        output_language,
        {"zh-CN": "目标行业", "zh-TW": "目標行業", "en": "target sector"},
        "目标行业",
    )
    client_text = "、".join(clients[:2]) or localized_text(
        output_language,
        {"zh-CN": "目标业主类型", "zh-TW": "目標業主類型", "en": "target buyer types"},
        "目标业主类型",
    )

    templates: dict[str, list[str]] = {
        "target_accounts": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"若当前还无法锁定具体甲方，优先在 {region_text} 内跟踪与 {industry_text} 直接相关的业主单位，如数据局、政务服务中心、信息中心、城运中心、行业主管部门或大型平台型国企。",
                    "zh-TW": f"若目前仍無法鎖定具體甲方，優先在 {region_text} 內追蹤與 {industry_text} 直接相關的業主單位，如資料局、政務服務中心、資訊中心、城運中心、行業主管部門或大型平台型國企。",
                    "en": f"If named buyers are still unclear, prioritize buyer entities in {region_text} that are directly tied to {industry_text}, such as data bureaus, digital service centers, information centers, city operation centers, sector regulators, or platform SOEs.",
                },
                f"若当前还无法锁定具体甲方，优先在 {region_text} 内跟踪与 {industry_text} 直接相关的业主单位，如数据局、政务服务中心、信息中心、城运中心、行业主管部门或大型平台型国企。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": f"把搜索范围收敛到 {client_text} + “预算/采购意向/二期/扩容/升级”，优先识别近 12 个月出现过统建、试点、一期上线后二期扩容的业主。",
                    "zh-TW": f"把檢索範圍收斂到 {client_text} +「預算/採購意向/二期/擴容/升級」，優先識別近 12 個月出現過統建、試點、一期上線後二期擴容的業主。",
                    "en": f"Narrow searches to {client_text} plus budget/procurement intention/phase-two expansion terms, prioritizing buyers that showed pilot-to-phase-two expansion in the past 12 months.",
                },
                f"把搜索范围收敛到 {client_text} + “预算/采购意向/二期/扩容/升级”，优先识别近 12 个月出现过统建、试点、一期上线后二期扩容的业主。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": f"即使暂时没有明确公司名，也应优先建立一份 {region_text} {industry_text} 的重点业主名单池，再用招标公告联系人、预算归口和项目代号反推具体甲方。",
                    "zh-TW": f"即使暫時沒有明確公司名，也應優先建立一份 {region_text} {industry_text} 的重點業主名單池，再用招標公告聯絡人、預算歸口與專案代號反推具體甲方。",
                    "en": f"Even without named companies, build a priority buyer pool for {region_text} and {industry_text}, then use tender contacts, budget owners, and project codes to infer specific accounts.",
                },
                f"即使暂时没有明确公司名，也应优先建立一份 {region_text} {industry_text} 的重点业主名单池，再用招标公告联系人、预算归口和项目代号反推具体甲方。",
            ),
        ],
        "target_departments": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"若缺少明确部门名称，优先把 {industry_text} 相关业主拆成四类部门：业务牵头部门、预算审批部门、采购招采部门、实施落地部门，并分别收集公开线索。",
                    "zh-TW": f"若缺少明確部門名稱，優先把 {industry_text} 相關業主拆成四類部門：業務牽頭、預算審批、採購招採、實施落地，並分別收集公開線索。",
                    "en": f"If department names are missing, split buyers tied to {industry_text} into four groups: business lead, budget owner, procurement, and implementation departments, then collect public signals for each.",
                },
                f"若缺少明确部门名称，优先把 {industry_text} 相关业主拆成四类部门：业务牵头部门、预算审批部门、采购招采部门、实施落地部门，并分别收集公开线索。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "优先排查采购中心、招标办、信息中心、数据局/数字化部、科技部、计划财务部、运营管理部等部门是否在公告、工作报告或组织架构中直接出现。",
                    "zh-TW": "優先排查採購中心、招標辦、資訊中心、資料局/數位化部、科技部、計畫財務部、營運管理部等部門是否在公告、工作報告或組織架構中直接出現。",
                    "en": "Prioritize procurement centers, tender offices, information centers, data/digital departments, technology teams, finance/planning, and operations functions in public notices and org disclosures.",
                },
                "优先排查采购中心、招标办、信息中心、数据局/数字化部、科技部、计划财务部、运营管理部等部门是否在公告、工作报告或组织架构中直接出现。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "如果目标是销售推进，先锁定“预算归口 + 技术把关 + 招采执行”三类部门组合，再反推关键联系人。",
                    "zh-TW": "如果目標是銷售推進，先鎖定「預算歸口 + 技術把關 + 招採執行」三類部門組合，再反推關鍵聯絡人。",
                    "en": "For sales progression, first lock the combination of budget owner, technical gatekeeper, and procurement executor, then infer the likely contacts.",
                },
                "如果目标是销售推进，先锁定“预算归口 + 技术把关 + 招采执行”三类部门组合，再反推关键联系人。",
            ),
        ],
        "public_contact_channels": [
            localized_text(
                output_language,
                {
                    "zh-CN": "优先收集公开业务入口：官网“联系我们”、采购/中标公告联系人、服务热线、投资者关系邮箱、政务公开电话。",
                    "zh-TW": "優先收集公開業務入口：官網「聯絡我們」、採購/中標公告聯絡人、服務熱線、投資者關係郵箱、政務公開電話。",
                    "en": "Collect public business channels first: official contact pages, tender contacts, hotlines, investor-relations mailboxes, and public-service phones.",
                },
                "优先收集公开业务入口：官网“联系我们”、采购/中标公告联系人、服务热线、投资者关系邮箱、政务公开电话。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": f"对于 {region_text} 的重点业主，优先从公共资源交易公告和采购意向公告中提取联系人、联系方式和代理机构信息。",
                    "zh-TW": f"對於 {region_text} 的重點業主，優先從公共資源交易公告與採購意向公告中提取聯絡人、聯絡方式與代理機構資訊。",
                    "en": f"For buyers in {region_text}, extract contacts, phone/email clues, and agency information from public procurement and tender notices.",
                },
                f"对于 {region_text} 的重点业主，优先从公共资源交易公告和采购意向公告中提取联系人、联系方式和代理机构信息。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "如果公开联系方式依旧不足，不要停在“无数据”，而应明确下一步去哪个官方公告栏目、哪个官网板块补证据。",
                    "zh-TW": "如果公開聯絡方式仍不足，不要停在「無資料」，而應明確下一步去哪個官方公告欄目、哪個官網板塊補證據。",
                    "en": "If public contact data is still weak, specify exactly which official notice pages or website sections should be checked next instead of returning blank.",
                },
                "如果公开联系方式依旧不足，不要停在“无数据”，而应明确下一步去哪个官方公告栏目、哪个官网板块补证据。",
            ),
        ],
        "budget_signals": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"若暂未拿到明确金额，优先看 {region_text} 内与 {industry_text} 相关的采购意向、预算草案、立项批复、可研批复、财政报告与年报披露。",
                    "zh-TW": f"若暫未拿到明確金額，優先查看 {region_text} 內與 {industry_text} 相關的採購意向、預算草案、立項批復、可研批復、財政報告與年報披露。",
                    "en": f"If exact amounts are missing, inspect procurement intentions, budget drafts, project approvals, feasibility approvals, fiscal reports, and filings tied to {industry_text} in {region_text}.",
                },
                f"若暂未拿到明确金额，优先看 {region_text} 内与 {industry_text} 相关的采购意向、预算草案、立项批复、可研批复、财政报告与年报披露。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "预算判断不要只盯单笔中标额，应同时跟踪总投资、年度预算、二三期扩容预算和运维服务预算。",
                    "zh-TW": "預算判斷不要只盯單筆中標額，應同時追蹤總投資、年度預算、二三期擴容預算與運維服務預算。",
                    "en": "Do not rely only on single award sizes; also track total investment, annual budgets, phase-two/three expansion budgets, and service OPEX budgets.",
                },
                "预算判断不要只盯单笔中标额，应同时跟踪总投资、年度预算、二三期扩容预算和运维服务预算。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "若金额仍缺失，可先给出高价值预算口径：平台统建、算力扩容、应用试点、集成实施、运维续费，这些口径最适合后续销售和投标拆解。",
                    "zh-TW": "若金額仍缺失，可先給出高價值預算口徑：平台統建、算力擴容、應用試點、整合實施、運維續費，這些口徑最適合後續銷售與投標拆解。",
                    "en": "If hard amounts are still missing, output the highest-value budget buckets first: platform build, capacity expansion, pilot applications, integration delivery, and renewal services.",
                },
                "若金额仍缺失，可先给出高价值预算口径：平台统建、算力扩容、应用试点、集成实施、运维续费，这些口径最适合后续销售和投标拆解。",
            ),
        ],
        "competitor_profiles": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"如果竞品公司名不够明确，先围绕 {industry_text} 抽取“高频中标方 / 集成总包 / 平台厂商 / 咨询牵线方”四类主体，再按威胁度排序。",
                    "zh-TW": f"如果競品公司名不夠明確，先圍繞 {industry_text} 抽取「高頻中標方 / 整合總包 / 平台廠商 / 諮詢牽線方」四類主體，再按威脅度排序。",
                    "en": f"If named competitors are still weak, first group entities around {industry_text} into frequent winners, integration primes, platform vendors, and connector advisors, then rank by threat.",
                },
                f"如果竞品公司名不够明确，先围绕 {industry_text} 抽取“高频中标方 / 集成总包 / 平台厂商 / 咨询牵线方”四类主体，再按威胁度排序。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "竞品画像至少要回答三件事：谁拿预算、谁有平台能力、谁掌握地方关系或交付生态。",
                    "zh-TW": "競品畫像至少要回答三件事：誰拿預算、誰有平台能力、誰掌握地方關係或交付生態。",
                    "en": "A usable competitor profile must answer three things: who captures budget, who owns the platform layer, and who controls local relationships or delivery ecosystems.",
                },
                "竞品画像至少要回答三件事：谁拿预算、谁有平台能力、谁掌握地方关系或交付生态。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "若缺少公司名，也应给出相对聚焦的竞对类型组合，方便后续继续查公司名单，而不是停在“证据不足”。",
                    "zh-TW": "若缺少公司名，也應給出相對聚焦的競對類型組合，方便後續繼續查公司名單，而不是停在「證據不足」。",
                    "en": "Even without exact names, provide a focused competitor-type cluster so the next step can resolve company names instead of stopping at 'insufficient evidence'.",
                },
                "若缺少公司名，也应给出相对聚焦的竞对类型组合，方便后续继续查公司名单，而不是停在“证据不足”。",
            ),
        ],
        "ecosystem_partners": [
            localized_text(
                output_language,
                {
                    "zh-CN": f"生态伙伴优先找“能牵线、能带项目、能补关系或交付”的主体，而不是只看纯产品公司；在 {region_text} 内优先排查总包、集成商、咨询顾问、运营商和研究院。",
                    "zh-TW": f"生態夥伴優先找「能牽線、能帶專案、能補關係或交付」的主體，而不是只看純產品公司；在 {region_text} 內優先排查總包、整合商、諮詢顧問、運營商與研究院。",
                    "en": f"For ecosystem partners, prioritize connectors, project carriers, relationship brokers, and delivery enablers over pure product vendors, especially integrators, advisors, operators, and institutes in {region_text}.",
                },
                f"生态伙伴优先找“能牵线、能带项目、能补关系或交付”的主体，而不是只看纯产品公司；在 {region_text} 内优先排查总包、集成商、咨询顾问、运营商和研究院。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "如果短期找不到明确伙伴公司名，也至少应先圈定“咨询牵线方 + 区域总包 + 行业集成商”三种伙伴角色。",
                    "zh-TW": "如果短期找不到明確夥伴公司名，也至少應先圈定「諮詢牽線方 + 區域總包 + 行業整合商」三種夥伴角色。",
                    "en": "If partner names are still unclear, first lock three partner roles: connector advisor, regional prime, and sector integrator.",
                },
                "如果短期找不到明确伙伴公司名，也至少应先圈定“咨询牵线方 + 区域总包 + 行业集成商”三种伙伴角色。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "伙伴筛选标准应包含行业影响力、牵线概率、项目协同能力和地方落地资源，而不是只看技术强弱。",
                    "zh-TW": "夥伴篩選標準應包含行業影響力、牽線機率、專案協同能力與地方落地資源，而不是只看技術強弱。",
                    "en": "Partner screening should prioritize industry influence, introduction probability, delivery synergy, and local access instead of raw product strength alone.",
                },
                "伙伴筛选标准应包含行业影响力、牵线概率、项目协同能力和地方落地资源，而不是只看技术强弱。",
            ),
        ],
    }
    if dimension_key in templates:
        return dedupe_strings(templates[dimension_key], limit)
    return _scope_insufficient_rows(
        output_language=output_language,
        scope_hints=scope_hints,
        dimension_label=dimension_label,
        limit=limit,
    )

def _ensure_minimum_rows(
    primary: list[str],
    *,
    backup: list[str],
    output_language: str,
    scope_hints: dict[str, object],
    dimension_key: str,
    dimension_label: str,
    min_count: int = 3,
    limit: int = 6,
) -> list[str]:
    rows = dedupe_strings(
        [
            row
            for row in [*primary, *backup]
            if not text_has_industry_conflict(str(row), scope_hints=scope_hints)
        ],
        limit,
    )
    if len(rows) >= min_count:
        return rows
    fill = _build_dimension_fallback_rows(
        output_language=output_language,
        scope_hints=scope_hints,
        dimension_key=dimension_key,
        dimension_label=dimension_label,
        limit=max(min_count, 3),
    )
    return dedupe_strings(
        [
            row
            for row in [*rows, *fill]
            if not text_has_industry_conflict(str(row), scope_hints=scope_hints)
        ],
        limit,
    )

def _extract_people_signals(sources: list[SourceDocument], *, limit: int) -> list[str]:
    rows = _extract_matching_sentences(
        sources,
        keywords=("董事长", "总经理", "副总裁", "主任", "局长", "厅长", "书记", "市长", "负责人", "总裁"),
        limit=limit,
    )
    return rows

def ranking_source_utility_dependencies() -> RankingSourceUtilityDependencies:
    return RankingSourceUtilityDependencies(
        source_text=source_document_text,
        truncate_text=truncate_text,
        is_plausible_entity_name=is_plausible_entity_name,
        dedupe_strings=dedupe_strings,
        org_pattern=ORG_PATTERN,
        person_role_pattern=PERSON_ROLE_PATTERN,
        department_pattern=DEPARTMENT_PATTERN,
        email_pattern=EMAIL_PATTERN,
        phone_pattern=PHONE_PATTERN,
        generic_content_domains=GENERIC_CONTENT_DOMAINS,
    )


def build_source_intelligence(
    sources: list[SourceDocument],
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    scope_hints: dict[str, object],
) -> dict[str, list[str]]:
    runtime = scope_entity_runtime_functions()
    ranking_deps = ranking_source_utility_dependencies()

    def bound_rank_org_rows(*args, **kwargs):
        return rank_org_rows(*args, **kwargs, deps=ranking_deps)

    def bound_extract_department_rows(*args, **kwargs):
        return extract_department_rows(*args, **kwargs, deps=ranking_deps)

    def bound_extract_public_contact_rows(*args, **kwargs):
        return extract_public_contact_rows(*args, **kwargs, deps=ranking_deps)

    def bound_extract_key_people_rows(*args, **kwargs):
        return extract_key_people_rows(*args, **kwargs, deps=ranking_deps)

    return build_source_intelligence_with_dependencies(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        scope_hints=scope_hints,
        deps=SourceIntelligenceDependencies(
            build_theme_terms=runtime.build_theme_terms,
            dedupe_strings=dedupe_strings,
            rank_org_rows=bound_rank_org_rows,
            extract_department_rows=bound_extract_department_rows,
            extract_public_contact_rows=bound_extract_public_contact_rows,
            build_entity_specific_team_rows=build_entity_specific_team_rows,
            extract_rank_entity_name=runtime.extract_rank_entity_name,
            extract_money_signals=_extract_money_signals,
            extract_region_distribution=_extract_region_distribution,
            extract_matching_sentences=_extract_matching_sentences,
            extract_key_people_rows=bound_extract_key_people_rows,
            extract_people_signals=_extract_people_signals,
            ensure_minimum_rows=_ensure_minimum_rows,
            build_industry_methodology_rows=_build_industry_methodology_rows,
        ),
    )
