from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from app.schemas.research import (
    ResearchEntityEvidenceOut,
    ResearchRankedEntityOut,
    ResearchReportDocument,
    ResearchReportEvaluationMetricOut,
    ResearchReportEvaluationProfileOut,
    ResearchReportReadinessOut,
    ResearchReportSelfImprovementOut,
    ResearchReviewQueueItemOut,
)
from app.services.content_extractor import normalize_text
from app.services.research.hard_failure_policy import evaluate_research_hard_failures


_TERM_RE = re.compile(r"[a-z0-9][a-z0-9._/-]{1,}|[\u4e00-\u9fff]{2,}", flags=re.IGNORECASE)
_ORG_RE = re.compile(
    r"[\u4e00-\u9fffA-Za-z0-9·（）()]{2,48}"
    r"(?:股份有限公司|有限责任公司|集团有限公司|集团|有限公司|公司|数据局|文旅局|财政局|教育局|公安局|交通局|商务局|文化和旅游局|局|厅|委|办|采购中心|交易中心|公共资源交易中心|中心|委员会|政府|办公室|研究院|研究所|大学|学院|医院|银行|协会|实验室)"
)
_PROCUREMENT_FIELD_PATTERNS: dict[str, tuple[str, ...]] = {
    "buyer": (
        r"(?:采购人|招标人|建设单位|业主单位|甲方)[:：\s]{0,4}(?P<value>[^，。；;\n]{2,80})",
    ),
    "winner": (
        r"(?:中标人|中标方|中标供应商|成交供应商|供应商名称)[:：\s]{0,4}(?P<value>[^，。；;\n]{2,80})",
    ),
    "bidder": (
        r"(?:投标人|投标方|候选供应商|中标候选人)[:：\s]{0,4}(?P<value>[^。；;\n]{2,120})",
    ),
    "agency": (
        r"(?:招标代理|采购代理机构|代理机构)[:：\s]{0,4}(?P<value>[^，。；;\n]{2,80})",
    ),
    "project": (
        r"(?:项目名称|采购项目名称|招标项目名称)[:：\s]{0,4}(?P<value>[^。；;\n]{4,120})",
    ),
}
_PROCUREMENT_TERMS = ("招标", "中标", "采购", "成交", "投标", "招标代理", "技术参数", "最高限价", "预算")
_STOPWORDS = {
    "什么",
    "哪些",
    "哪个",
    "如何",
    "以及",
    "项目",
    "方案",
    "系统",
    "平台",
    "服务",
    "采购",
    "招标",
    "中标",
    "公告",
    "行业",
    "市场",
    "需求",
    "the",
    "and",
    "for",
    "with",
}
_LOW_SIGNAL_ENTITY_TOKENS = (
    "招标公告",
    "采购公告",
    "中标公告",
    "成交公告",
    "结果公告",
    "更正公告",
    "竞争性磋商公告",
    "公开招标",
    "项目",
    "平台",
    "系统",
    "服务",
    "建设",
    "采购需求",
    "技术参数",
    "预算",
    "最高限价",
    "联系方式",
    "联系人",
    "官网",
    "新闻",
    "资讯",
)


@dataclass(slots=True)
class _CandidateEntity:
    name: str
    role: str = "entity"
    procurement: bool = False
    official_hits: int = 0
    source_titles: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)
    excerpts: list[str] = field(default_factory=list)

    @property
    def evidence_score(self) -> int:
        return min(100, 44 + self.official_hits * 16 + len(self.source_urls) * 8 + (12 if self.procurement else 0))


def _dedupe_strings(values: Iterable[object], limit: int = 20) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_text(str(value or ""))
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append(normalized)
        if len(rows) >= limit:
            break
    return rows


def _clamp_score(value: float | int) -> int:
    return max(0, min(100, int(round(float(value)))))


def _metric_status(score: int, threshold: int) -> str:
    if score >= threshold:
        return "pass"
    if score >= max(45, threshold - 15):
        return "watch"
    return "fail"


def _source_attr(source: object, field_name: str) -> str:
    return normalize_text(str(getattr(source, field_name, "") or ""))


def _source_title(source: object) -> str:
    return _source_attr(source, "title") or _source_attr(source, "url") or "未命名来源"


def _source_url(source: object) -> str:
    return _source_attr(source, "url")


def _source_tier(source: object) -> str:
    tier = _source_attr(source, "source_tier").lower()
    if tier in {"official", "media", "aggregate"}:
        return tier
    text = _source_text(source).lower()
    if any(token in text for token in ("gov.cn", ".gov", "ccgp", "ggzy", "cecbid", "官网", "官方")):
        return "official"
    return "media"


def _source_text(source: object) -> str:
    return normalize_text(
        "；".join(
            [
                _source_attr(source, "title"),
                _source_attr(source, "snippet"),
                _source_attr(source, "excerpt"),
                _source_attr(source, "search_query"),
                _source_attr(source, "source_label"),
                _source_attr(source, "source_type"),
                _source_attr(source, "domain"),
            ]
        )
    )


def _clean_entity_name(value: object) -> str:
    text = normalize_text(str(value or ""))
    if not text:
        return ""
    text = re.sub(r"^(?:采购人|招标人|建设单位|业主单位|甲方|中标人|中标方|成交供应商|供应商名称|投标人|招标代理|采购代理机构|代理机构|项目名称)[:：\s]+", "", text)
    text = re.sub(r"(?:统一社会信用代码|地址|联系人|联系方式|联系电话|电话|邮箱|网址|官网).*$", "", text)
    text = re.split(r"[，,。；;|｜\n\r]", text, maxsplit=1)[0]
    text = text.strip(" -_：:()（）[]【】《》“”\"'")
    text = normalize_text(text)
    if len(text) > 48 and not any(suffix in text[-16:] for suffix in ("有限公司", "集团", "公司", "中心", "政府", "委员会")):
        return ""
    return text[:80]


def _clean_project_name(value: object) -> str:
    text = normalize_text(str(value or ""))
    text = re.sub(r"^(?:项目名称|采购项目名称|招标项目名称)[:：\s]+", "", text)
    text = re.split(r"[；;\n\r]", text, maxsplit=1)[0]
    return text.strip(" -_：:()（）[]【】《》“”\"'")[:120]


def _looks_like_useful_entity(name: str) -> bool:
    if len(name) < 3:
        return False
    if any(token in name for token in _LOW_SIGNAL_ENTITY_TOKENS) and not any(
        suffix in name for suffix in ("有限公司", "集团", "公司", "中心", "政府", "委员会", "数据局", "文旅局")
    ):
        return False
    if name in _STOPWORDS:
        return False
    return bool(_ORG_RE.search(name) or re.search(r"[A-Za-z][A-Za-z0-9 .,&-]{2,}(?:Inc|Ltd|LLC|Cloud|AI|Tech)", name))


def _split_entity_values(value: str) -> list[str]:
    parts = re.split(r"[、,，/]|(?:\s{2,})", value)
    cleaned: list[str] = []
    for part in parts:
        candidate = _clean_entity_name(part)
        if candidate:
            cleaned.append(candidate)
    if not cleaned:
        candidate = _clean_entity_name(value)
        if candidate:
            cleaned.append(candidate)
    return _dedupe_strings(cleaned, limit=8)


def _extract_procurement_entities(text: str) -> list[tuple[str, str]]:
    entities: list[tuple[str, str]] = []
    for role, patterns in _PROCUREMENT_FIELD_PATTERNS.items():
        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                raw = normalize_text(match.group("value"))
                if role == "project":
                    project = _clean_project_name(raw)
                    if project and 4 <= len(project) <= 120 and any(term in text for term in _PROCUREMENT_TERMS):
                        entities.append((project, role))
                    continue
                for candidate in _split_entity_values(raw):
                    if _looks_like_useful_entity(candidate):
                        entities.append((candidate, role))
    return _dedupe_role_entities(entities, limit=16)


def _extract_org_entities(text: str) -> list[str]:
    entities: list[str] = []
    for match in _ORG_RE.finditer(text):
        candidate = _clean_entity_name(match.group(0))
        if candidate and _looks_like_useful_entity(candidate):
            entities.append(candidate)
    return _dedupe_strings(entities, limit=24)


def _dedupe_role_entities(values: Iterable[tuple[str, str]], limit: int = 20) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for name, role in values:
        normalized = _clean_project_name(name) if role == "project" else _clean_entity_name(name)
        if not normalized:
            continue
        key = (normalized.lower(), role)
        if key in seen:
            continue
        seen.add(key)
        rows.append((normalized, role))
        if len(rows) >= limit:
            break
    return rows


def _candidate_key(name: str, role: str) -> tuple[str, str]:
    return (normalize_text(name).lower(), role)


def _add_candidate(
    candidates: dict[tuple[str, str], _CandidateEntity],
    *,
    name: str,
    role: str,
    source: object | None = None,
    procurement: bool = False,
) -> None:
    normalized = _clean_project_name(name) if role == "project" else _clean_entity_name(name)
    if not normalized:
        return
    if role != "project" and not _looks_like_useful_entity(normalized):
        return
    key = _candidate_key(normalized, role)
    candidate = candidates.setdefault(key, _CandidateEntity(name=normalized, role=role, procurement=procurement))
    candidate.procurement = candidate.procurement or procurement
    if source is None:
        return
    title = _source_title(source)
    url = _source_url(source)
    excerpt = _source_text(source)[:240]
    if _source_tier(source) == "official":
        candidate.official_hits += 1
    if title and title not in candidate.source_titles:
        candidate.source_titles.append(title)
    if url and url not in candidate.source_urls:
        candidate.source_urls.append(url)
    if excerpt and excerpt not in candidate.excerpts:
        candidate.excerpts.append(excerpt)


def _collect_candidate_entities(report: ResearchReportDocument, sources: list[object]) -> list[_CandidateEntity]:
    candidates: dict[tuple[str, str], _CandidateEntity] = {}
    for entity in report.entity_graph.entities:
        role = entity.entity_type if entity.entity_type in {"target", "competitor", "partner"} else "entity"
        _add_candidate(candidates, name=entity.canonical_name, role=role, procurement=False)
    for source in sources:
        text = _source_text(source)
        is_procurement_source = any(term in text for term in _PROCUREMENT_TERMS)
        for name, role in _extract_procurement_entities(text):
            _add_candidate(candidates, name=name, role=role, source=source, procurement=True)
        for name in _extract_org_entities(text):
            _add_candidate(candidates, name=name, role="entity", source=source, procurement=is_procurement_source)
    rows = list(candidates.values())
    rows.sort(key=lambda item: (item.procurement, item.evidence_score, len(item.source_urls)), reverse=True)
    return rows[:24]


def _entity_names(values: Iterable[object]) -> list[str]:
    names: list[str] = []
    for value in values:
        if isinstance(value, str):
            candidate = value
        else:
            candidate = getattr(value, "name", "") or getattr(value, "canonical_name", "")
        normalized = _clean_entity_name(candidate)
        if normalized:
            names.append(normalized)
    return _dedupe_strings(names, limit=30)


def _report_output_text(report: ResearchReportDocument) -> str:
    section_text = "；".join(
        "；".join([section.title, *section.items, section.evidence_note, section.insufficiency_summary])
        for section in report.sections
    )
    tender_text = "；".join(
        "；".join(
            [
                project.project_name,
                project.buyer,
                project.winning_vendor,
                project.tender_agency,
                "；".join(project.bidder_candidates),
                "；".join(project.extracted_requirements),
                "；".join(project.technical_parameters),
            ]
        )
        for project in report.market_intelligence.tender_projects
    )
    entity_text = "；".join(
        [
            *_entity_names(report.top_target_accounts),
            *_entity_names(report.pending_target_candidates),
            *_entity_names(report.top_ecosystem_partners),
            *_entity_names(report.pending_partner_candidates),
            *_entity_names(report.top_competitors),
            *_entity_names(report.pending_competitor_candidates),
            *report.target_accounts,
            *report.target_departments,
            *report.public_contact_channels,
            *report.account_team_signals,
            *report.budget_signals,
            *report.project_distribution,
            *report.strategic_directions,
            *report.tender_timeline,
            *report.leadership_focus,
            *report.ecosystem_partners,
            *report.competitor_profiles,
            *report.benchmark_cases,
            *report.flagship_products,
            *report.key_people,
            *report.five_year_outlook,
            *report.client_peer_moves,
            *report.winner_peer_moves,
            *report.competition_analysis,
            report.commercial_summary.budget_signal,
            report.commercial_summary.entry_window,
            report.commercial_summary.competition_or_partner,
            report.commercial_summary.next_action,
            tender_text,
        ]
    )
    return normalize_text(
        "；".join(
            [
                report.keyword,
                report.research_focus or "",
                report.report_title,
                report.executive_summary,
                report.consulting_angle,
                section_text,
                entity_text,
            ]
        )
    )


def _terms(text: str, *, limit: int = 32) -> list[str]:
    normalized = normalize_text(text).lower()
    rows: list[str] = []
    for raw in _TERM_RE.findall(normalized):
        token = normalize_text(raw).lower()
        if not token or token in _STOPWORDS:
            continue
        rows.append(token)
        if len(rows) >= limit:
            break
    return _dedupe_strings(rows, limit=limit)


def _entity_in_text(name: str, text: str) -> bool:
    normalized_name = normalize_text(name)
    if not normalized_name:
        return False
    if normalized_name in text:
        return True
    compact_name = re.sub(r"[\s()（）·]", "", normalized_name).lower()
    compact_text = re.sub(r"[\s()（）·]", "", text).lower()
    if compact_name and compact_name in compact_text:
        return True
    aliases = [
        normalized_name.removesuffix("有限责任公司"),
        normalized_name.removesuffix("股份有限公司"),
        normalized_name.removesuffix("有限公司"),
        normalized_name.removesuffix("集团有限公司"),
    ]
    return any(alias and len(alias) >= 3 and alias in text for alias in aliases)


def _score_entity_recall(candidates: list[_CandidateEntity], output_text: str) -> tuple[int, list[str], list[str]]:
    if not candidates:
        return 85, [], []
    recalled: list[str] = []
    missing: list[str] = []
    for candidate in candidates:
        if _entity_in_text(candidate.name, output_text):
            recalled.append(candidate.name)
        else:
            missing.append(candidate.name)
    score = _clamp_score(len(recalled) / max(len(candidates), 1) * 100)
    return score, _dedupe_strings(recalled, 20), _dedupe_strings(missing, 20)


def _build_corrective_queries(
    *,
    report: ResearchReportDocument,
    missing_entities: list[str],
    missing_procurement_entities: list[str],
) -> list[str]:
    focus = normalize_text(report.research_focus or "")
    queries: list[str] = []
    for entity in missing_procurement_entities[:4]:
        queries.append(f"{report.keyword} {entity} 招标人 中标方 投标方 招标代理 技术参数")
    for entity in missing_entities[:4]:
        queries.append(f"{entity} {report.keyword} 官网 采购 招标 中标")
        if focus:
            queries.append(f"{entity} {focus} 预算 部门 联系方式")
    if not queries:
        queries.append(f"{report.keyword} 官方公告 招标 中标 采购 预算")
    return _dedupe_strings(queries, limit=8)


def _build_metric(
    key: str,
    label: str,
    score: int,
    *,
    threshold: int = 70,
    summary: str = "",
    evidence: Iterable[object] = (),
    gaps: Iterable[object] = (),
    improvement_actions: Iterable[object] = (),
) -> ResearchReportEvaluationMetricOut:
    return ResearchReportEvaluationMetricOut(
        key=key,
        label=label,
        score=_clamp_score(score),
        threshold=threshold,
        status=_metric_status(_clamp_score(score), threshold),  # type: ignore[arg-type]
        summary=summary,
        evidence=_dedupe_strings(evidence, limit=6),
        gaps=_dedupe_strings(gaps, limit=6),
        improvement_actions=_dedupe_strings(improvement_actions, limit=6),
    )


def _faithfulness_metric(report: ResearchReportDocument) -> ResearchReportEvaluationMetricOut:
    diagnostics = report.source_diagnostics
    review_score = int(diagnostics.generation_grounding_score or 0)
    derived = 35
    derived += int(float(diagnostics.strict_match_ratio or 0.0) * 24)
    derived += int(float(diagnostics.official_source_ratio or 0.0) * 20)
    derived += 12 if report.report_readiness.evidence_gate_passed else 0
    derived += 8 if report.evidence_density == "high" else 4 if report.evidence_density == "medium" else 0
    derived -= min(28, len(diagnostics.unsupported_claims or []) * 7)
    score = max(review_score, derived) if review_score else derived
    return _build_metric(
        "faithfulness",
        "事实支撑度",
        score,
        threshold=72,
        summary="检查报告结论是否能被检索来源、章节证据和生成支撑度共同托住。",
        evidence=[
            f"生成支撑度 {review_score}" if review_score else "",
            f"严格命中 {round(float(diagnostics.strict_match_ratio or 0.0) * 100)}%",
            f"官方源 {round(float(diagnostics.official_source_ratio or 0.0) * 100)}%",
        ],
        gaps=[
            *diagnostics.unsupported_claims[:3],
            "证据门未通过" if not report.report_readiness.evidence_gate_passed else "",
        ],
        improvement_actions=["补官方源和原始公告", "删除或降级无来源支撑的结论"],
    )


def _answer_relevancy_metric(report: ResearchReportDocument, output_text: str) -> ResearchReportEvaluationMetricOut:
    required_terms = _terms(" ".join([report.keyword, report.research_focus or ""]), limit=18)
    if not required_terms:
        return _build_metric("answer_relevancy", "问题贴合度", 78, summary="输入主题较短，按结构完整度给出基础通过分。")
    matched = [term for term in required_terms if term in output_text.lower()]
    missing = [term for term in required_terms if term not in matched]
    score = 45 + len(matched) / max(len(required_terms), 1) * 55
    return _build_metric(
        "answer_relevancy",
        "问题贴合度",
        score,
        threshold=70,
        summary="检查报告是否围绕关键词、研究焦点和范围约束展开。",
        evidence=matched[:6],
        gaps=missing[:6],
        improvement_actions=["围绕未覆盖关键词补一轮来源聚合", "让章节标题和摘要回到用户原始问题"],
    )


def _context_coverage_metric(report: ResearchReportDocument, sources: list[object]) -> ResearchReportEvaluationMetricOut:
    diagnostics = report.source_diagnostics
    accepted = int(diagnostics.accepted_source_count or 0)
    retained = int(diagnostics.retained_source_count or len(sources) or report.source_count or 0)
    accepted_ratio = accepted / max(retained, 1) if accepted else float(diagnostics.strict_match_ratio or 0.0)
    score = 28
    score += min(24, retained * 3)
    score += int(accepted_ratio * 24)
    score += min(12, int(diagnostics.unique_domain_count or 0) * 3)
    score += int(float(diagnostics.official_source_ratio or 0.0) * 12)
    if diagnostics.retrieval_quality == "high":
        score += 10
    elif diagnostics.retrieval_quality == "medium":
        score += 5
    return _build_metric(
        "context_coverage",
        "上下文覆盖",
        score,
        threshold=68,
        summary="检查检索上下文是否足够覆盖主题、来源层级和交叉验证。",
        evidence=[
            f"保留来源 {retained}",
            f"可用来源 {accepted}" if accepted else "",
            f"覆盖域名 {diagnostics.unique_domain_count}",
        ],
        gaps=[
            "来源数量偏少" if retained < 6 else "",
            "官方源比例偏低" if float(diagnostics.official_source_ratio or 0.0) < 0.25 else "",
            "跨域交叉验证不足" if int(diagnostics.unique_domain_count or 0) < 3 else "",
        ],
        improvement_actions=["扩大公开搜索和行业垂直源", "优先补政府/采购/官网原始页"],
    )


def _citation_quality_metric(report: ResearchReportDocument) -> ResearchReportEvaluationMetricOut:
    evidence_count = sum(len(section.evidence_links or []) for section in report.sections)
    official_evidence_count = sum(int((section.source_tier_counts or {}).get("official", 0) or 0) for section in report.sections)
    quota_pass_count = sum(1 for section in report.sections if section.meets_evidence_quota)
    score = 34 + min(28, evidence_count * 7) + min(20, official_evidence_count * 5) + min(18, quota_pass_count * 6)
    weak_sections = [section.title for section in report.sections if not section.meets_evidence_quota]
    return _build_metric(
        "citation_quality",
        "证据引用质量",
        score,
        threshold=68,
        summary="检查章节证据链接、官方证据和配额达成情况。",
        evidence=[f"证据链接 {evidence_count}", f"官方证据 {official_evidence_count}", f"达标章节 {quota_pass_count}"],
        gaps=weak_sections[:5],
        improvement_actions=["给弱证据章节补至少一条直接来源", "优先引用原始公告而非二手摘要"],
    )


def _actionability_metric(report: ResearchReportDocument) -> ResearchReportEvaluationMetricOut:
    readiness = report.report_readiness
    has_account = bool(report.target_accounts or report.top_target_accounts or report.commercial_summary.account_focus)
    has_window = bool(report.budget_signals or report.tender_timeline or report.commercial_summary.entry_window)
    has_department = bool(report.target_departments or report.public_contact_channels or report.account_team_signals)
    has_next = bool(report.strategic_directions or report.commercial_summary.next_action or readiness.next_verification_steps)
    score = 20 + sum(18 for flag in (has_account, has_window, has_department, has_next) if flag)
    score += 8 if readiness.actionable else 0
    return _build_metric(
        "actionability",
        "行动可执行性",
        score,
        threshold=70,
        summary="检查报告能否直接转为账户计划、补证清单和下一步动作。",
        evidence=[
            "有目标账户" if has_account else "",
            "有预算/时间窗口" if has_window else "",
            "有部门或触达入口" if has_department else "",
            "有下一步动作" if has_next else "",
        ],
        gaps=[
            "缺目标账户" if not has_account else "",
            "缺预算或时间窗口" if not has_window else "",
            "缺组织入口" if not has_department else "",
            "缺下一步动作" if not has_next else "",
        ],
        improvement_actions=["把结论改写为账户、窗口、入口、动作四段", "低证据结论进入待核验队列"],
    )


def _entity_recall_metric(
    candidates: list[_CandidateEntity],
    output_text: str,
    *,
    procurement_only: bool = False,
) -> tuple[ResearchReportEvaluationMetricOut, list[str], list[str]]:
    scoped = [candidate for candidate in candidates if candidate.procurement] if procurement_only else candidates
    score, recalled, missing = _score_entity_recall(scoped, output_text)
    if procurement_only and not scoped:
        metric = _build_metric(
            "procurement_entity_recall",
            "招投标实体召回",
            85,
            threshold=72,
            summary="当前未识别到确认的招投标来源，本指标不作为主要扣分项。",
        )
        return metric, [], []
    metric = _build_metric(
        "procurement_entity_recall" if procurement_only else "entity_recall",
        "招投标实体召回" if procurement_only else "实体召回",
        score,
        threshold=72 if procurement_only else 70,
        summary=(
            "检查确认招投标来源中的招标人、中标方、投标方、代理机构和项目名是否进入报告。"
            if procurement_only
            else "检查来源和实体图中的高价值账户、伙伴、竞品和机构是否进入报告。"
        ),
        evidence=recalled[:6],
        gaps=missing[:8],
        improvement_actions=[
            "把遗漏实体补入待核验候选清单",
            "围绕遗漏实体扩搜官网、采购公告和行业案例",
            "区分甲方、中标方、投标方、代理机构角色",
        ],
    )
    return metric, recalled, missing


def evaluate_research_report(
    report: ResearchReportDocument,
    *,
    source_documents: Iterable[object] | None = None,
) -> ResearchReportEvaluationProfileOut:
    sources = list(source_documents or report.sources or [])
    output_text = _report_output_text(report)
    candidates = _collect_candidate_entities(report, sources)
    entity_metric, recalled_entities, missing_entities = _entity_recall_metric(candidates, output_text)
    procurement_metric, procurement_recalled, missing_procurement = _entity_recall_metric(
        candidates,
        output_text,
        procurement_only=True,
    )
    metrics = [
        _faithfulness_metric(report),
        _answer_relevancy_metric(report, output_text),
        _context_coverage_metric(report, sources),
        entity_metric,
        procurement_metric,
        _citation_quality_metric(report),
        _actionability_metric(report),
    ]
    scores = {metric.key: metric.score for metric in metrics}
    overall = _clamp_score(
        scores.get("faithfulness", 0) * 0.22
        + scores.get("answer_relevancy", 0) * 0.12
        + scores.get("context_coverage", 0) * 0.16
        + scores.get("entity_recall", 0) * 0.22
        + scores.get("procurement_entity_recall", 0) * 0.12
        + scores.get("citation_quality", 0) * 0.08
        + scores.get("actionability", 0) * 0.08
    )
    hard_failure = evaluate_research_hard_failures(report)
    overall = hard_failure.cap_score(overall)
    status = "pass" if overall >= 75 and all(metric.score >= 58 for metric in metrics) else "watch" if overall >= 58 else "fail"
    corrective_queries = _build_corrective_queries(
        report=report,
        missing_entities=missing_entities,
        missing_procurement_entities=missing_procurement,
    )
    return ResearchReportEvaluationProfileOut(
        overall_score=overall,
        status=status,  # type: ignore[arg-type]
        entity_recall_score=entity_metric.score,
        procurement_entity_recall_score=procurement_metric.score,
        metrics=metrics,
        recalled_entities=_dedupe_strings([*recalled_entities, *procurement_recalled], limit=20),
        missing_entities=_dedupe_strings(missing_entities, limit=20),
        procurement_entities=_dedupe_strings([candidate.name for candidate in candidates if candidate.procurement], limit=20),
        missing_procurement_entities=_dedupe_strings(missing_procurement, limit=20),
        corrective_queries=corrective_queries,
    )


def _existing_report_entity_names(report: ResearchReportDocument) -> set[str]:
    return {
        name.lower()
        for name in _dedupe_strings(
            [
                *report.target_accounts,
                *_entity_names(report.top_target_accounts),
                *_entity_names(report.pending_target_candidates),
                *_entity_names(report.top_ecosystem_partners),
                *_entity_names(report.pending_partner_candidates),
                *_entity_names(report.top_competitors),
                *_entity_names(report.pending_competitor_candidates),
                *report.ecosystem_partners,
                *report.competitor_profiles,
            ],
            limit=80,
        )
    }


def _entity_evidence_links(name: str, sources: list[object], limit: int = 2) -> list[ResearchEntityEvidenceOut]:
    links: list[ResearchEntityEvidenceOut] = []
    for source in sources:
        text = _source_text(source)
        if not _entity_in_text(name, text):
            continue
        links.append(
            ResearchEntityEvidenceOut(
                title=_source_title(source),
                url=_source_url(source),
                source_label=_source_attr(source, "source_label") or None,
                source_tier=_source_tier(source),  # type: ignore[arg-type]
                anchor_text=name,
                excerpt=text[:220],
                confidence_tone="high" if _source_tier(source) == "official" else "low",
            )
        )
        if len(links) >= limit:
            break
    return links


def _candidate_ranked_entity(name: str, sources: list[object], *, role_note: str) -> ResearchRankedEntityOut:
    links = _entity_evidence_links(name, sources)
    official_count = sum(1 for link in links if link.source_tier == "official")
    return ResearchRankedEntityOut(
        name=name,
        score=min(76, 48 + official_count * 12 + len(links) * 6),
        reasoning=f"质量评估发现该实体在来源中出现但报告覆盖不足，先列为待核验候选；{role_note}",
        entity_mode="pending",
        evidence_links=links,
    )


def _append_review_queue(report: ResearchReportDocument, evaluation: ResearchReportEvaluationProfileOut) -> list[ResearchReviewQueueItemOut]:
    queue = list(report.review_queue or [])
    if any(item.id == "review-report-evaluation-entity-recall" for item in queue):
        return queue
    if evaluation.entity_recall_score >= 70 and evaluation.procurement_entity_recall_score >= 72:
        return queue
    queue.append(
        ResearchReviewQueueItemOut(
            id="review-report-evaluation-entity-recall",
            section_title="实体召回待补强",
            severity="high" if evaluation.status == "fail" else "medium",
            summary="质量评估发现部分来源中的高价值实体未进入报告主体，需要补充角色、证据和推进价值。",
            recommended_action="优先核验遗漏实体的官网、采购公告、招投标角色和同行案例，再决定是否进入目标账户或竞合清单。",
            evidence_links=[],
        )
    )
    return queue[:6]


def _merge_quality_profile_actions(report: ResearchReportDocument, evaluation: ResearchReportEvaluationProfileOut) -> object:
    profile = report.quality_profile
    gaps = _dedupe_strings(
        [
            *profile.gaps,
            *[f"实体召回：{name}" for name in evaluation.missing_entities[:4]],
            *[f"招投标实体：{name}" for name in evaluation.missing_procurement_entities[:4]],
        ],
        limit=8,
    )
    next_actions = _dedupe_strings(
        [
            *profile.next_actions,
            "围绕遗漏实体补官网、采购公告、中标公告和行业案例。",
            "把招标人、中标方、投标方、招标代理和技术参数拆成结构化字段。",
        ],
        limit=8,
    )
    return profile.model_copy(update={"gaps": gaps, "next_actions": next_actions})


def _apply_structured_self_improvement(
    report: ResearchReportDocument,
    evaluation: ResearchReportEvaluationProfileOut,
    *,
    sources: list[object],
) -> tuple[ResearchReportDocument, list[str], list[str]]:
    existing = _existing_report_entity_names(report)
    missing_general = [name for name in evaluation.missing_entities if name.lower() not in existing][:5]
    missing_procurement = [name for name in evaluation.missing_procurement_entities if name.lower() not in existing][:5]

    target_candidates = list(report.pending_target_candidates or [])
    partner_candidates = list(report.pending_partner_candidates or [])
    added_entities: list[str] = []
    for name in missing_general:
        if not _looks_like_useful_entity(name):
            continue
        target_candidates.append(_candidate_ranked_entity(name, sources, role_note="需确认其是否为甲方或关键账户。"))
        added_entities.append(name)
    for name in missing_procurement:
        if not _looks_like_useful_entity(name):
            continue
        partner_candidates.append(_candidate_ranked_entity(name, sources, role_note="需确认其在招投标中的中标方、投标方或代理机构角色。"))
        added_entities.append(name)

    actions: list[str] = []
    if added_entities:
        actions.append("补入遗漏实体到待核验候选清单。")
    if evaluation.corrective_queries:
        actions.append("生成下一轮扩搜查询，优先覆盖官方、采购和招投标来源。")
    if any(metric.status == "fail" for metric in evaluation.metrics if metric.key in {"faithfulness", "context_coverage"}):
        actions.append("将弱证据结论降级为待补证，并要求跨来源共识。")

    readiness = report.report_readiness if getattr(report, "report_readiness", None) else ResearchReportReadinessOut()
    readiness = readiness.model_copy(
        update={
            "next_verification_steps": _dedupe_strings(
                [
                    *readiness.next_verification_steps,
                    *evaluation.corrective_queries[:3],
                    "核验遗漏实体在招标人、中标方、投标方、代理机构中的具体角色。",
                ],
                limit=8,
            )
        }
    )
    diagnostics = report.source_diagnostics.model_copy(
        update={
            "corrective_query_plan": _dedupe_strings(
                [*report.source_diagnostics.corrective_query_plan, *evaluation.corrective_queries],
                limit=12,
            ),
            "generation_review_notes": _dedupe_strings(
                [
                    *report.source_diagnostics.generation_review_notes,
                    "输出质量评估已触发实体召回补强。",
                ],
                limit=8,
            ),
        }
    )
    market_intelligence = report.market_intelligence.model_copy(
        update={
            "external_source_queries": _dedupe_strings(
                [*report.market_intelligence.external_source_queries, *evaluation.corrective_queries],
                limit=12,
            ),
            "intelligence_gaps": _dedupe_strings(
                [
                    *report.market_intelligence.intelligence_gaps,
                    *[f"待核验遗漏实体：{name}" for name in added_entities[:6]],
                    "补齐招标人、中标方、投标方、招标代理和技术参数的原始公告证据。"
                    if evaluation.missing_procurement_entities
                    else "",
                ],
                limit=10,
            ),
        }
    )
    improved = report.model_copy(
        update={
            "pending_target_candidates": target_candidates[:8],
            "pending_partner_candidates": partner_candidates[:8],
            "report_readiness": readiness,
            "source_diagnostics": diagnostics,
            "market_intelligence": market_intelligence,
            "review_queue": _append_review_queue(report, evaluation),
            "quality_profile": _merge_quality_profile_actions(report, evaluation),
        }
    )
    return improved, _dedupe_strings(actions, limit=6), _dedupe_strings(added_entities, limit=10)


def evaluate_and_improve_research_report(
    report: ResearchReportDocument,
    *,
    source_documents: Iterable[object] | None = None,
    min_overall_score: int = 70,
    min_entity_recall_score: int = 65,
) -> ResearchReportDocument:
    sources = list(source_documents or report.sources or [])
    before = evaluate_research_report(report, source_documents=sources)
    should_improve = (
        before.overall_score < min_overall_score
        or before.entity_recall_score < min_entity_recall_score
        or before.procurement_entity_recall_score < min_entity_recall_score
    )
    if not should_improve:
        return report.model_copy(update={"evaluation_profile": before})

    improved, actions, added_entities = _apply_structured_self_improvement(report, before, sources=sources)
    if not actions:
        return report.model_copy(update={"evaluation_profile": before})

    after = evaluate_research_report(improved, source_documents=sources)
    strategies: list[str] = ["structured_entity_enrichment"]
    if before.corrective_queries:
        strategies.append("expanded_search")
    if any(metric.status == "fail" for metric in before.metrics if metric.key in {"faithfulness", "context_coverage"}):
        strategies.extend(["deeper_reasoning", "cross_source_consensus"])
    self_improvement = ResearchReportSelfImprovementOut(
        triggered=True,
        round_count=1,
        strategies=_dedupe_strings(strategies, limit=5),  # type: ignore[arg-type]
        before_score=before.overall_score,
        after_score=after.overall_score,
        actions=actions,
        added_entities=added_entities,
        corrective_queries=before.corrective_queries,
        notes=_dedupe_strings(
            [
                "本轮采用结构化补强，不直接把低置信实体提升为正式结论。",
                "扩搜查询已写入报告诊断，下一轮会优先覆盖官方、采购和招投标来源。",
            ],
            limit=4,
        ),
    )
    after = after.model_copy(update={"self_improvement": self_improvement})
    return improved.model_copy(update={"evaluation_profile": after})
