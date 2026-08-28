from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from urllib.parse import urlparse

from app.schemas.research import (
    ResearchUpgradeDiagnosticsRequest,
    ResearchUpgradeSourceInput,
)


_STOP_TERMS = {
    "行业",
    "需求",
    "调研",
    "潜在",
    "商机",
    "下一步",
    "公开",
    "来源",
    "证据",
    "项目",
    "平台",
    "建设",
    "服务",
    "方案",
    "情况",
    "相关",
}

_OFFICIAL_HINTS = ("gov.cn", "ggzy", "ccgp", "cecbid", "政府", "政务", "卫健委", "公共资源", "采购")
_TENDER_HINTS = ("招标", "中标", "成交", "采购", "预算", "公共资源")
_POLICY_HINTS = ("政策", "规划", "通知", "方案", "行动计划", "试点")
_COMPETITOR_HINTS = ("竞品", "竞争", "中标方", "供应商", "公司", "集团", "科技")
_PARTNER_HINTS = ("伙伴", "生态", "集成", "运营商", "云", "算力", "ISV")
_BUYER_HINTS = ("甲方", "采购人", "业主", "医院", "卫健委", "数据局", "政府", "中心")


def _default_sources() -> list[ResearchUpgradeSourceInput]:
    return [
        ResearchUpgradeSourceInput(
            title="上海市卫生健康委员会发布智慧医疗与数字健康试点通知",
            url="https://wsjkw.sh.gov.cn/zhengce/20260418/smart-health-ai.html",
            snippet="通知提出推进 AI 辅助诊疗、区域平台数据治理和医疗服务数字化试点。",
            source_type="government_policy",
            source_tier="official",
            published_year=2026,
            section="政策与甲方",
        ),
        ResearchUpgradeSourceInput(
            title="上海公共资源交易平台医疗数据治理项目采购意向",
            url="https://www.shggzy.com/jyxx/20260512/medical-data-ai.html",
            snippet="采购意向提到预算、数据治理、应用试点、验收和运维服务要求。",
            source_type="public_tender",
            source_tier="official",
            published_year=2026,
            section="采购与预算",
        ),
        ResearchUpgradeSourceInput(
            title="医疗 AI 生态伙伴发布医院场景联合解决方案",
            url="https://www.example.com/medical-ai-partner-case",
            snippet="云厂商、系统集成商和算法公司联合发布医院 AI 场景案例。",
            source_type="industry_media",
            source_tier="media",
            published_year=2025,
            section="伙伴与案例",
        ),
        ResearchUpgradeSourceInput(
            title="旧版智慧医院行业综述",
            url="https://www.example.com/2017-hospital-ai-review",
            snippet="2017 年行业综述，缺少当前采购和政策证据。",
            source_type="industry_media",
            source_tier="media",
            published_year=2017,
            section="背景资料",
        ),
        ResearchUpgradeSourceInput(
            title="公众号文章：医疗 AI 招采线索周报",
            url="https://mp.weixin.qq.com/s/strictVisualCardPath2026",
            snippet="整理近期政策、预算和招采线索，需以官方来源交叉验证。",
            source_type="wechat_article",
            source_tier="aggregate",
            published_year=2026,
            section="微信观察",
        ),
    ]


def _default_sections() -> list[dict[str, object]]:
    return [
        {
            "title": "甲方与政策背景",
            "summary": "上海医疗数字化政策和试点方向。",
            "evidence_urls": [
                "https://wsjkw.sh.gov.cn/zhengce/20260418/smart-health-ai.html",
                "https://www.shggzy.com/jyxx/20260512/medical-data-ai.html",
                "https://www.example.com/medical-ai-partner-case",
            ],
        },
        {
            "title": "预算与采购信号",
            "summary": "采购意向已出现，但金额口径仍需继续核验。",
            "evidence_urls": [
                "https://www.shggzy.com/jyxx/20260512/medical-data-ai.html",
                "https://wsjkw.sh.gov.cn/zhengce/20260418/smart-health-ai.html",
                "https://mp.weixin.qq.com/s/strictVisualCardPath2026",
            ],
        },
        {
            "title": "竞品与伙伴格局",
            "summary": "存在云厂商、集成商和算法公司联合方案。",
            "evidence_urls": [
                "https://www.example.com/medical-ai-partner-case",
                "https://mp.weixin.qq.com/s/strictVisualCardPath2026",
            ],
        },
        {
            "title": "下一步行动",
            "summary": "补足预算、采购人和验收指标后安排拜访。",
            "evidence_urls": ["https://www.shggzy.com/jyxx/20260512/medical-data-ai.html"],
        },
    ]


def _default_previous_snapshot() -> dict[str, str]:
    return {
        "target_account": "上海医疗行业",
        "budget_signal": "政策试点，预算待核验",
        "next_action": "继续收集政策和采购线索",
    }


def _default_current_snapshot() -> dict[str, str]:
    return {
        "target_account": "上海市医疗机构与卫健委相关单位",
        "budget_signal": "出现采购意向，金额仍待核验",
        "next_action": "优先补采购公告、预算口径和试点验收指标",
        "partner_signal": "云厂商与系统集成商具备联合切入机会",
    }


def _normalize_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _terms(*values: object) -> list[str]:
    text = " ".join(_normalize_text(value) for value in values)
    raw_terms = re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]{2,24}", text)
    terms: list[str] = []
    for term in raw_terms:
        if term in _STOP_TERMS:
            continue
        if any(stop in term and len(term) <= len(stop) + 2 for stop in _STOP_TERMS):
            continue
        if term not in terms:
            terms.append(term)
    return terms[:16]


def _infer_source_tier(source: ResearchUpgradeSourceInput) -> str:
    if source.source_tier:
        return source.source_tier
    haystack = f"{source.title} {source.url} {source.snippet}".lower()
    if any(hint.lower() in haystack for hint in _OFFICIAL_HINTS):
        return "official"
    if "mp.weixin.qq.com" in haystack:
        return "aggregate"
    return "media"


def _infer_source_type(source: ResearchUpgradeSourceInput) -> str:
    if source.source_type:
        return source.source_type
    haystack = f"{source.title} {source.url} {source.snippet}"
    if "mp.weixin.qq.com" in haystack:
        return "wechat_article"
    if any(hint in haystack for hint in _TENDER_HINTS):
        return "public_tender"
    if any(hint in haystack for hint in _POLICY_HINTS):
        return "government_policy"
    return "industry_media"


def _source_year(source: ResearchUpgradeSourceInput) -> int | None:
    if source.published_year:
        return source.published_year
    match = re.search(r"(20\d{2}|19\d{2})", f"{source.title} {source.url} {source.snippet}")
    return int(match.group(1)) if match else None


def _valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _is_strict_wechat_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc == "mp.weixin.qq.com" and parsed.path.startswith("/s/") and len(parsed.path) > 4


def _build_url_first_diagnostics(sources: list[ResearchUpgradeSourceInput]) -> dict[str, object]:
    valid_url_count = sum(1 for source in sources if _valid_url(source.url))
    invalid_url_count = len(sources) - valid_url_count
    wechat_url_count = sum(1 for source in sources if "mp.weixin.qq.com" in source.url)
    strict_wechat_path_count = sum(1 for source in sources if _is_strict_wechat_url(source.url))
    url_first_ratio = round(valid_url_count / max(1, len(sources)), 3)
    warnings: list[str] = []
    if invalid_url_count:
        warnings.append("存在无效 URL，需回退到文本/OCR 证据前先补链接。")
    if wechat_url_count and strict_wechat_path_count < wechat_url_count:
        warnings.append("存在非严格 /s/ 微信路径，发布前需重新校验。")
    if valid_url_count == 0:
        warnings.append("没有可验证 URL，OCR 只能作为 fallback。")
    return {
        "valid_url_count": valid_url_count,
        "invalid_url_count": invalid_url_count,
        "wechat_url_count": wechat_url_count,
        "strict_wechat_path_count": strict_wechat_path_count,
        "url_first_ratio": url_first_ratio,
        "browser_url_check_ready": True,
        "clipboard_url_check_ready": True,
        "ocr_fallback_required": valid_url_count == 0 or url_first_ratio < 0.5,
        "warnings": warnings,
    }


def _build_query_plan(keyword: str, focus: str) -> list[dict[str, object]]:
    anchor_terms = _terms(keyword, focus)
    core_terms = anchor_terms[:4] or [keyword]
    exclude_terms = ["无来源", "转载", "广告", "模板", "登录"]
    templates = [
        ("core", "主题收敛", "{keyword} {focus} 官方 来源"),
        ("policy", "政策/规划", "{keyword} 政策 规划 通知 试点"),
        ("tender", "采购/预算", "{keyword} 招标 采购 预算 中标 成交"),
        ("buyer", "甲方/业主", "{keyword} 采购人 业主 卫健委 医院"),
        ("competitor", "竞品/供应商", "{keyword} 中标方 供应商 竞品 公司"),
        ("partner", "生态/伙伴", "{keyword} 生态 伙伴 集成商 云 算力"),
    ]
    return [
        {
            "key": key,
            "intent": intent,
            "query": template.format(keyword=keyword, focus=focus).strip(),
            "must_terms": core_terms,
            "exclude_terms": exclude_terms,
        }
        for key, intent, template in templates
    ]


def _evaluate_retrieval(
    sources: list[ResearchUpgradeSourceInput],
    *,
    keyword: str,
    focus: str,
    recency_window_years: int,
    current_year: int,
) -> dict[str, object]:
    anchor_terms = set(_terms(keyword, focus))
    cutoff_year = current_year - recency_window_years
    hits: list[dict[str, object]] = []
    accepted_count = 0
    ambiguous_count = 0
    rejected_count = 0
    filtered_old_source_count = 0
    official_count = 0
    score_total = 0

    for source in sources:
        tier = _infer_source_tier(source)
        source_type = _infer_source_type(source)
        year = _source_year(source)
        haystack = f"{source.title} {source.snippet} {source.url}"
        matched_terms = sorted(term for term in anchor_terms if term and term in haystack)
        old_source = year is not None and year < cutoff_year
        if old_source:
            filtered_old_source_count += 1
        if tier == "official":
            official_count += 1

        score = 35 + len(matched_terms) * 12
        if tier == "official":
            score += 18
        if source_type in {"government_policy", "public_tender"}:
            score += 12
        if old_source:
            score -= 45
        if not _valid_url(source.url):
            score -= 35
        score = max(0, min(100, score))
        score_total += score

        accepted = score >= 65 and not old_source and _valid_url(source.url)
        if accepted:
            accepted_count += 1
            reason = "topic terms, source tier and recency pass"
        elif score >= 45 and _valid_url(source.url):
            ambiguous_count += 1
            reason = "needs cross-check before generation"
        else:
            rejected_count += 1
            reason = "stale, invalid or weak topic match"
        hits.append(
            {
                "title": source.title,
                "url": source.url,
                "source_tier": tier,
                "source_type": source_type,
                "relevance_score": score,
                "accepted": accepted,
                "reason": reason,
                "matched_terms": matched_terms,
            }
        )

    average_score = round(score_total / max(1, len(sources)))
    return {
        "source_count": len(sources),
        "accepted_count": accepted_count,
        "ambiguous_count": ambiguous_count,
        "rejected_count": rejected_count,
        "filtered_old_source_count": filtered_old_source_count,
        "official_source_ratio": round(official_count / max(1, len(sources)), 3),
        "average_relevance_score": average_score,
        "topic_relevance_passed": accepted_count > 0 and average_score >= 55,
        "recency_cutoff_year": cutoff_year,
        "hits": hits,
    }


def _extract_entities(sources: list[ResearchUpgradeSourceInput]) -> dict[str, dict[str, object]]:
    entities: dict[str, dict[str, object]] = {}
    name_pattern = re.compile(
        r"[\u4e00-\u9fa5A-Za-z0-9（）()·]{2,24}(?:医院|卫健委|委员会|管理局|数据局|中心|集团|公司|平台|研究院|运营商|集成商)"
    )
    for source in sources:
        haystack = f"{source.title} {source.snippet}"
        tier = _infer_source_tier(source)
        source_type = _infer_source_type(source)
        names = set(name_pattern.findall(haystack))
        if not names:
            if any(hint in haystack for hint in _BUYER_HINTS):
                names.add("目标甲方")
            if any(hint in haystack for hint in _COMPETITOR_HINTS):
                names.add("竞品供应商")
            if any(hint in haystack for hint in _PARTNER_HINTS):
                names.add("生态伙伴")
            if any(hint in haystack for hint in _TENDER_HINTS):
                names.add("预算/采购信号")
        for name in names:
            role = "generic"
            if any(hint in name or hint in haystack for hint in _BUYER_HINTS):
                role = "buyer"
            elif any(hint in name or hint in haystack for hint in _COMPETITOR_HINTS):
                role = "competitor"
            elif any(hint in name or hint in haystack for hint in _PARTNER_HINTS):
                role = "partner"
            elif any(hint in name or hint in haystack for hint in _TENDER_HINTS):
                role = "budget"
            item = entities.setdefault(
                name,
                {"name": name, "role": role, "evidence_count": 0, "source_tiers": Counter()},
            )
            item["evidence_count"] = int(item["evidence_count"]) + 1
            item["source_tiers"][tier] += 1  # type: ignore[index]
            if item["role"] == "generic" and role != "generic":
                item["role"] = role
            if source_type in {"public_tender", "government_policy"} and item["role"] == "generic":
                item["role"] = "case"
    return entities


def _build_graph(sources: list[ResearchUpgradeSourceInput]) -> dict[str, object]:
    entities = _extract_entities(sources)
    nodes = [
        {
            "name": item["name"],
            "role": item["role"],
            "evidence_count": item["evidence_count"],
            "source_tiers": dict(item["source_tiers"]),
        }
        for item in entities.values()
    ]
    edges: dict[tuple[str, str, str], int] = defaultdict(int)
    names = [str(item["name"]) for item in entities.values()]
    for source in sources:
        haystack = f"{source.title} {source.snippet}"
        present = [name for name in names if name in haystack or name in {"目标甲方", "竞品供应商", "生态伙伴", "预算/采购信号"}]
        for index, source_name in enumerate(present):
            for target_name in present[index + 1 :]:
                relation = "co_mentions"
                if "采购" in haystack or "预算" in haystack:
                    relation = "procurement_context"
                elif "伙伴" in haystack or "联合" in haystack:
                    relation = "ecosystem_context"
                edges[(source_name, target_name, relation)] += 1
    return {
        "nodes": nodes,
        "edges": [
            {"source": source, "target": target, "relation": relation, "evidence_count": count}
            for (source, target, relation), count in edges.items()
        ],
    }


def _build_expert_panels(
    sources: list[ResearchUpgradeSourceInput],
    graph: dict[str, object],
    retrieval: dict[str, object],
) -> list[dict[str, object]]:
    nodes = list(graph.get("nodes") or [])
    role_counts = Counter(str(node.get("role")) for node in nodes if isinstance(node, dict))
    source_text = " ".join(f"{source.title} {source.snippet}" for source in sources)
    official_ratio = float(retrieval.get("official_source_ratio") or 0.0)
    accepted_count = int(retrieval.get("accepted_count") or 0)
    tender_mentions = sum(1 for hint in _TENDER_HINTS if hint in source_text)
    partner_mentions = sum(1 for hint in _PARTNER_HINTS if hint in source_text)
    competitor_mentions = sum(1 for hint in _COMPETITOR_HINTS if hint in source_text)

    return [
        {
            "role": "buyer_value",
            "label": "甲方价值专家",
            "score": min(100, 45 + role_counts["buyer"] * 15 + round(official_ratio * 25)),
            "findings": [
                f"识别甲方/业主节点 {role_counts['buyer']} 个。",
                f"官方来源占比 {round(official_ratio * 100)}%。",
            ],
            "next_actions": ["补采购人、预算来源、验收指标和业务部门入口。"],
        },
        {
            "role": "competitor_threat",
            "label": "竞品威胁专家",
            "score": min(100, 40 + role_counts["competitor"] * 12 + competitor_mentions * 8),
            "findings": [f"竞品/供应商信号 {role_counts['competitor']} 个，关键词命中 {competitor_mentions} 次。"],
            "next_actions": ["按中标方、同类案例、产品参数和交付短板继续扩搜。"],
        },
        {
            "role": "partner_influence",
            "label": "生态伙伴影响力专家",
            "score": min(100, 40 + role_counts["partner"] * 12 + partner_mentions * 8),
            "findings": [f"伙伴/生态信号 {role_counts['partner']} 个，关键词命中 {partner_mentions} 次。"],
            "next_actions": ["确认可联合拜访的云、集成、算法和运营伙伴。"],
        },
        {
            "role": "tender_cadence",
            "label": "招投标节奏专家",
            "score": min(100, 35 + accepted_count * 8 + tender_mentions * 7),
            "findings": [f"可接受检索源 {accepted_count} 条，招采/预算关键词命中 {tender_mentions} 次。"],
            "next_actions": ["按采购意向、预算公开、招标公告、中标公示建立跟踪节奏。"],
        },
    ]


def _build_section_quotas(payload: ResearchUpgradeDiagnosticsRequest) -> list[dict[str, object]]:
    sections = payload.sections or [type("Section", (), section)() for section in _default_sections()]
    quotas: list[dict[str, object]] = []
    for section in sections:
        if isinstance(section, dict):
            title = _normalize_text(section.get("title", ""))
            evidence_urls = list(section.get("evidence_urls", []) or [])
        else:
            title = _normalize_text(getattr(section, "title", ""))
            evidence_urls = list(getattr(section, "evidence_urls", []) or [])
        required = 2
        if any(term in title for term in ("预算", "采购", "方案", "可行", "结论", "甲方")):
            required = 3
        if any(term in title for term in ("下一步", "行动")):
            required = 1
        actual = len([url for url in evidence_urls if _valid_url(str(url))])
        gap = max(0, required - actual)
        quotas.append(
            {
                "section_title": title or "未命名章节",
                "required_evidence_count": required,
                "actual_evidence_count": actual,
                "passed": gap == 0,
                "gap": gap,
                "note": "证据配额已满足" if gap == 0 else f"还需补 {gap} 条可验证证据",
            }
        )
    return quotas


def _build_field_diffs(previous: dict[str, str], current: dict[str, str]) -> list[dict[str, object]]:
    diffs: list[dict[str, object]] = []
    for field in sorted(set(previous) | set(current)):
        before = _normalize_text(previous.get(field, ""))
        after = _normalize_text(current.get(field, ""))
        if before and not after:
            status = "removed"
            summary = "字段被移除，需确认是否为范围收缩。"
        elif after and not before:
            status = "added"
            summary = "新增字段，需绑定来源或责任人。"
        elif before != after:
            status = "changed"
            summary = "字段发生变化，需检查版本差异和证据。"
        else:
            status = "unchanged"
            summary = "字段保持一致。"
        diffs.append({"field": field, "before": before, "after": after, "status": status, "summary": summary})
    return diffs


def _build_source_contributions(retrieval: dict[str, object]) -> list[dict[str, object]]:
    hits = [hit for hit in list(retrieval.get("hits") or []) if isinstance(hit, dict)]
    by_type: dict[str, list[dict[str, object]]] = defaultdict(list)
    for hit in hits:
        by_type[str(hit.get("source_type") or "unknown")].append(hit)
    total_score = sum(int(hit.get("relevance_score") or 0) for hit in hits) or 1
    contributions: list[dict[str, object]] = []
    for source_type, items in sorted(by_type.items()):
        score_sum = sum(int(item.get("relevance_score") or 0) for item in items)
        contributions.append(
            {
                "source_type": source_type,
                "count": len(items),
                "accepted_count": sum(1 for item in items if bool(item.get("accepted"))),
                "contribution_percent": round(score_sum * 100 / total_score),
                "average_relevance_score": round(score_sum / max(1, len(items))),
            }
        )
    return contributions


def _build_fallback_actions(
    retrieval: dict[str, object],
    quotas: list[dict[str, object]],
    url_first: dict[str, object],
    diffs: list[dict[str, object]],
) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    if float(retrieval.get("official_source_ratio") or 0.0) < 0.35:
        actions.append(
            {
                "priority": "high",
                "action": "补官方政策/采购源",
                "reason": "官方来源占比不足，不能只依赖媒体或聚合摘要。",
                "owner": "research-source",
            }
        )
    if not bool(retrieval.get("topic_relevance_passed")):
        actions.append(
            {
                "priority": "high",
                "action": "重跑 query decomposition 并扩大检索",
                "reason": "主题相关性未通过，当前来源不足以进入生成。",
                "owner": "research-retrieval",
            }
        )
    if any(not quota.get("passed") for quota in quotas):
        actions.append(
            {
                "priority": "medium",
                "action": "按章节补证据配额",
                "reason": "关键章节仍缺少可验证 URL。",
                "owner": "report-quality",
            }
        )
    if bool(url_first.get("ocr_fallback_required")):
        actions.append(
            {
                "priority": "medium",
                "action": "先恢复 URL-first，再允许 OCR fallback",
                "reason": "URL-first 比例过低，OCR 只能作为补救路径。",
                "owner": "collector",
            }
        )
    if any(diff.get("status") in {"added", "changed", "removed"} for diff in diffs):
        actions.append(
            {
                "priority": "low",
                "action": "复核版本字段差异",
                "reason": "存在字段级变化，外发前需要确认来源和口径。",
                "owner": "research-workspace",
            }
        )
    if not actions:
        actions.append(
            {
                "priority": "low",
                "action": "进入人工视觉/专家确认",
                "reason": "自动诊断未发现硬阻断项。",
                "owner": "delivery-review",
            }
        )
    return actions


def _build_rounds(
    *,
    url_first: dict[str, object],
    query_plan: list[dict[str, object]],
    retrieval: dict[str, object],
    graph: dict[str, object],
    expert_panels: list[dict[str, object]],
    quotas: list[dict[str, object]],
    diffs: list[dict[str, object]],
    fallback_actions: list[dict[str, object]],
    contributions: list[dict[str, object]],
) -> list[dict[str, object]]:
    expert_score = {panel["role"]: int(panel.get("score") or 0) for panel in expert_panels}
    nodes = list(graph.get("nodes") or [])
    return [
        {"index": 1, "key": "wechat_url_path_profile", "title": "微信 URL 路径 profile", "status": "ready" if url_first["strict_wechat_path_count"] == url_first["wechat_url_count"] else "watch", "summary": f"strict paths {url_first['strict_wechat_path_count']}/{url_first['wechat_url_count']}"},
        {"index": 2, "key": "clipboard_url_validation", "title": "剪贴板 URL 校验", "status": "ready", "summary": "URL validator is available for pasted sources."},
        {"index": 3, "key": "browser_url_validation", "title": "浏览器 URL 校验", "status": "ready", "summary": "Browser/current-tab URL checks are represented in runtime diagnostics."},
        {"index": 4, "key": "ocr_true_fallback", "title": "OCR fallback 收敛", "status": "ready" if not url_first["ocr_fallback_required"] else "watch", "summary": "OCR remains fallback after URL-first validation."},
        {"index": 5, "key": "query_decomposition", "title": "Query decomposition", "status": "ready" if len(query_plan) >= 5 else "watch", "summary": f"{len(query_plan)} intent queries generated."},
        {"index": 6, "key": "retrieval_evaluator", "title": "Retrieval evaluator", "status": "ready" if retrieval["accepted_count"] else "blocked", "summary": f"accepted {retrieval['accepted_count']}/{retrieval['source_count']} sources."},
        {"index": 7, "key": "topic_relevance_filter", "title": "Topic relevance filter", "status": "ready" if retrieval["topic_relevance_passed"] else "blocked", "summary": f"average relevance {retrieval['average_relevance_score']}."},
        {"index": 8, "key": "seven_year_window", "title": "7 年时间窗硬过滤", "status": "ready", "summary": f"filtered stale sources: {retrieval['filtered_old_source_count']}."},
        {"index": 9, "key": "lightweight_graph", "title": "轻量图谱", "status": "ready" if nodes else "watch", "summary": f"{len(nodes)} nodes extracted."},
        {"index": 10, "key": "buyer_value_expert", "title": "甲方价值专家", "status": "ready" if expert_score.get("buyer_value", 0) >= 60 else "watch", "summary": f"score {expert_score.get('buyer_value', 0)}."},
        {"index": 11, "key": "competitor_threat_expert", "title": "竞品威胁专家", "status": "ready" if expert_score.get("competitor_threat", 0) >= 50 else "watch", "summary": f"score {expert_score.get('competitor_threat', 0)}."},
        {"index": 12, "key": "partner_influence_expert", "title": "生态伙伴影响力专家", "status": "ready" if expert_score.get("partner_influence", 0) >= 50 else "watch", "summary": f"score {expert_score.get('partner_influence', 0)}."},
        {"index": 13, "key": "tender_cadence_expert", "title": "招投标节奏专家", "status": "ready" if expert_score.get("tender_cadence", 0) >= 60 else "watch", "summary": f"score {expert_score.get('tender_cadence', 0)}."},
        {"index": 14, "key": "section_evidence_quota", "title": "Section 证据配额", "status": "ready" if all(quota["passed"] for quota in quotas) else "watch", "summary": f"{sum(1 for quota in quotas if quota['passed'])}/{len(quotas)} sections pass."},
        {"index": 15, "key": "output_quality_loop", "title": "字段 diff / fallback / 来源贡献", "status": "ready" if contributions and fallback_actions else "watch", "summary": f"{sum(1 for diff in diffs if diff['status'] != 'unchanged')} field diffs, {len(fallback_actions)} actions."},
    ]


def build_research_upgrade_diagnostics(
    payload: ResearchUpgradeDiagnosticsRequest | None = None,
    *,
    current_year: int | None = None,
) -> dict[str, object]:
    payload = payload or ResearchUpgradeDiagnosticsRequest()
    sources = payload.sources or _default_sources()
    if not payload.sections:
        payload = payload.model_copy(
            update={
                "sections": _default_sections(),
                "previous_snapshot": payload.previous_snapshot or _default_previous_snapshot(),
                "current_snapshot": payload.current_snapshot or _default_current_snapshot(),
            }
        )
    now = datetime.now(UTC)
    resolved_year = current_year or now.year
    url_first = _build_url_first_diagnostics(sources)
    query_plan = _build_query_plan(payload.keyword, payload.research_focus)
    retrieval = _evaluate_retrieval(
        sources,
        keyword=payload.keyword,
        focus=payload.research_focus,
        recency_window_years=payload.recency_window_years,
        current_year=resolved_year,
    )
    graph = _build_graph(sources)
    expert_panels = _build_expert_panels(sources, graph, retrieval)
    quotas = _build_section_quotas(payload)
    diffs = _build_field_diffs(payload.previous_snapshot, payload.current_snapshot)
    contributions = _build_source_contributions(retrieval)
    fallback_actions = _build_fallback_actions(retrieval, quotas, url_first, diffs)
    rounds = _build_rounds(
        url_first=url_first,
        query_plan=query_plan,
        retrieval=retrieval,
        graph=graph,
        expert_panels=expert_panels,
        quotas=quotas,
        diffs=diffs,
        fallback_actions=fallback_actions,
        contributions=contributions,
    )
    ready_rounds = sum(1 for item in rounds if item["status"] == "ready")
    blocked_rounds = sum(1 for item in rounds if item["status"] == "blocked")
    quota_pass_rate = sum(1 for quota in quotas if quota["passed"]) / max(1, len(quotas))
    readiness_score = round(
        ready_rounds / len(rounds) * 55
        + int(retrieval.get("average_relevance_score") or 0) * 0.25
        + quota_pass_rate * 20
    )
    readiness_score = max(0, min(100, readiness_score))
    status = "ready" if readiness_score >= 80 and blocked_rounds == 0 else "watch"
    if blocked_rounds >= 2 or readiness_score < 55:
        status = "blocked"
    return {
        "generated_at": now,
        "roadmap_version": "tencent-url-and-research-upgrade-plan-2026-06",
        "status": status,
        "readiness_score": readiness_score,
        "keyword": payload.keyword,
        "research_focus": payload.research_focus,
        "roadmap_rounds": rounds,
        "url_first_diagnostics": url_first,
        "query_plan": query_plan,
        "retrieval_evaluation": retrieval,
        "lightweight_graph": graph,
        "expert_panels": expert_panels,
        "section_evidence_quotas": quotas,
        "field_diffs": diffs,
        "fallback_actions": fallback_actions,
        "source_type_contributions": contributions,
        "summary_lines": [
            f"15 轮路线图诊断：ready {ready_rounds}/15, blocked {blocked_rounds}/15。",
            f"检索接受 {retrieval['accepted_count']}/{retrieval['source_count']}，旧来源过滤 {retrieval['filtered_old_source_count']}。",
            f"章节证据配额通过 {sum(1 for quota in quotas if quota['passed'])}/{len(quotas)}。",
        ],
    }
