from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import re
from urllib import parse

from app.schemas.research import (
    ResearchCitationGateOut,
    ResearchDeliveryEvidenceLedgerOut,
    ResearchEntityEvidenceOut,
    ResearchEntityGraphOut,
    ResearchEvidenceGateOut,
    ResearchQuestionNodeOut,
    ResearchQuestionTreeOut,
    ResearchReportReadinessOut,
    ResearchReportResponse,
    ResearchReportSectionOut,
    ResearchScopeContractOut,
    ResearchSolutionDeliveryPackOut,
    ResearchSourceAdmissionOut,
    ResearchSourceDiagnosticsOut,
)
from app.services.content_extractor import normalize_text
from app.services.research.delivery_evidence_ledger import build_delivery_evidence_ledger
from app.services.research.delivery_scope import requires_account_truth
from app.services.research.entity_authenticity_gate import source_has_target_role_evidence
from app.services.research.entity_policy import INDUSTRY_SCOPE_ALIASES
from app.services.research.report_scope_runtime import prune_industry_hints
from app.services.research.scope_hints import REGION_SCOPE_ALIASES, infer_explicit_industry_labels
from app.services.research.source_documents import (
    SourceDocument,
    source_documents_to_research_source_outputs,
)
from app.services.research.source_topology import assess_source_topology, topology_counts


_GENERIC_SCOPE_TERMS = {
    "ai",
    "aigc",
    "人工智能",
    "大模型",
    "模型",
    "智能",
    "数字化",
    "信息化",
    "平台",
    "系统",
    "行业",
    "调研",
    "研究",
    "研报",
    "需求",
    "方案",
    "商机",
}
_GENERIC_INDUSTRIES = {"大模型", "人工智能", "信息化"}
_INVALID_PAGE_TITLES = {
    "404",
    "403",
    "not found",
    "page not found",
    "页面不存在",
    "访问被拒绝",
}
_INVALID_PAGE_TITLE_TOKENS = (
    "错误页面",
    "页面错误",
    "页面不存在",
    "网页不存在",
    "访问出错",
    "error page",
    "page error",
    "not found",
)
_ATOMIC_SPLIT_RE = re.compile(r"[。！？!?；;\n]+")
_CITATION_ONLY_RE = re.compile(r"^(?:【[^】]+】|\[[^\]]+\])$")
_TIME_SCOPE_RE = re.compile(r"(?:20\d{2}(?:年|年度)?|上半年|下半年|未来\s*[1-9]\s*年|近\s*[1-9]\s*年|\d+[-至到]\d+\s*个月)")

_QUESTION_SPECS: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "demand_scope",
        "需求与范围",
        ("需求", "场景", "痛点", "试点", "应用", "业务", "临床", "运营"),
        ("official", "media"),
    ),
    (
        "policy_market",
        "政策与市场",
        ("政策", "规划", "监管", "示范", "试点", "工作报告", "行动计划", "指导意见"),
        ("official",),
    ),
    (
        "buyer_procurement",
        "账户与招采",
        ("采购", "招标", "中标", "预算", "项目", "部门", "客户", "医院", "信息科", "采购意向"),
        ("official",),
    ),
    (
        "solution_competition",
        "方案与竞争",
        ("方案", "产品", "平台", "系统", "架构", "厂商", "竞争", "竞品", "案例", "合作"),
        ("official", "media"),
    ),
    (
        "economics_delivery",
        "投入与交付",
        ("投资", "成本", "收益", "roi", "实施", "交付", "周期", "扩容", "运维", "绩效"),
        ("official", "media"),
    ),
    (
        "risk_counterevidence",
        "风险与反证",
        ("风险", "安全", "合规", "数据", "隐私", "限制", "挑战", "失败", "审计", "反对"),
        ("official", "media"),
    ),
)

_QUESTION_QUERY_TERMS = {
    "demand_scope": "应用场景 牵头部门 需求",
    "policy_market": "政策 规划 试点 建设",
    "buyer_procurement": "财政预算 采购意向 招标 中标",
    "solution_competition": "平台 集成 运维 安全 厂商",
    "economics_delivery": "预算 金额 实施周期 运维 绩效",
    "risk_counterevidence": "合规 数据安全 验收 风险",
}

_QUESTION_OFFICIAL_SITES = {
    "buyer_procurement": "ccgp.gov.cn",
    "solution_competition": "ggzy.gov.cn",
}


@dataclass(frozen=True, slots=True)
class ResearchEvidenceGovernanceResult:
    contract: ResearchScopeContractOut
    question_tree: ResearchQuestionTreeOut
    admissions: list[ResearchSourceAdmissionOut]
    gate: ResearchEvidenceGateOut
    accepted_sources: list[SourceDocument]


@dataclass(frozen=True, slots=True)
class ResearchClaimGovernanceResult:
    ledger: ResearchDeliveryEvidenceLedgerOut
    citation_gate: ResearchCitationGateOut


def _dedupe(values: Iterable[object], limit: int = 24) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_text(str(value or ""))
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        seen.add(key)
        rows.append(normalized)
        if len(rows) >= limit:
            break
    return rows


def _stable_id(prefix: str, *values: object) -> str:
    seed = "\x1f".join(normalize_text(str(value or "")).casefold() for value in values)
    return f"{prefix}_{sha256(seed.encode('utf-8')).hexdigest()[:16]}"


def _task_type(keyword: str, research_focus: str | None) -> str:
    text = normalize_text(f"{keyword} {research_focus or ''}").casefold()
    if any(token in text for token in ("竞品", "竞争", "竞对", "competitive", "对标")):
        return "competitive_research"
    if any(token in text for token in ("解决方案", "架构", "可研", "项目建议书", "solution")):
        return "solution_research"
    if any(
        token in text
        for token in (
            "客户",
            "账户",
            "甲方",
            "打单",
            "销售",
            "潜在需求情报",
            "需求情报",
            "潜在客户",
            "潜在甲方",
        )
    ):
        return "account_intelligence"
    if any(token in text for token in ("行业", "市场", "趋势", "格局", "需求", "产业")):
        return "industry_research"
    return "general_research"


def _specific_industry_terms(industries: Sequence[str]) -> list[str]:
    return _dedupe(
        alias
        for industry in industries
        if industry not in _GENERIC_INDUSTRIES
        for alias in (industry, *INDUSTRY_SCOPE_ALIASES.get(industry, ()))
        if normalize_text(alias).casefold() not in _GENERIC_SCOPE_TERMS
    )


def _topic_terms(keyword: str, research_focus: str | None) -> list[str]:
    text = normalize_text(f"{keyword} {research_focus or ''}")
    rough = re.split(r"[\s,，、/|:：;；（）()\-]+", text)
    semantic_fragments = re.split(
        r"(?:调研|研究|分析|搜集|收集|潜在需求|需求|情报|报告|研报|专题|商机|机会)",
        text,
    )
    explicit_industries = infer_explicit_industry_labels(text)
    return _dedupe(
        token
        for token in [*explicit_industries, *rough, *semantic_fragments]
        if len(normalize_text(token)) >= 2
        and len(normalize_text(token)) <= 18
        and normalize_text(token).casefold() not in _GENERIC_SCOPE_TERMS
        and not _TIME_SCOPE_RE.fullmatch(normalize_text(token))
    )


def build_research_scope_contract(
    *,
    keyword: str,
    research_focus: str | None,
    research_mode: str,
    scope_hints: dict[str, object],
) -> ResearchScopeContractOut:
    regions = _dedupe(scope_hints.get("regions", []) or [], 4)
    industries = prune_industry_hints(_dedupe(scope_hints.get("industries", []) or [], 4))
    clients = _dedupe(scope_hints.get("clients", []) or [], 4)
    exclusions = _dedupe(scope_hints.get("strategy_exclusion_terms", []) or [], 12)
    specific_industry_terms = _specific_industry_terms(industries)
    topics = _topic_terms(keyword, research_focus)
    must_include = _dedupe(
        [
            *(scope_hints.get("strategy_must_include_terms", []) or []),
            *specific_industry_terms,
            *clients,
            *topics[:6],
        ],
        20,
    )
    generic_terms = _dedupe(
        term
        for term in _GENERIC_SCOPE_TERMS
        if term in normalize_text(f"{keyword} {research_focus or ''}").casefold()
    )
    time_scope = _dedupe(_TIME_SCOPE_RE.findall(normalize_text(f"{keyword} {research_focus or ''}")), 6)
    task_type = _task_type(keyword, research_focus)
    methodology = normalize_text(str(scope_hints.get("industry_methodology_profile") or ""))
    status = "ready" if industries or clients or topics else "needs_clarification"
    reasons = []
    if status == "ready":
        reasons.append("已从用户问题锁定至少一个行业、主体或非通用主题锚点。")
    else:
        reasons.append("当前问题只有通用研究词，生成正式研报前需要补行业、主体或场景范围。")
    namespace_seed = "|".join([*regions[:2], *industries[:2], *clients[:2], task_type])
    scope_namespace = f"scope_{sha256(namespace_seed.encode('utf-8')).hexdigest()[:12]}"
    return ResearchScopeContractOut(
        contract_id=_stable_id("rsc", keyword, research_focus, research_mode, namespace_seed),
        keyword=normalize_text(keyword),
        research_focus=normalize_text(research_focus or ""),
        research_mode="fast" if research_mode == "fast" else "deep",
        task_type=task_type,  # type: ignore[arg-type]
        regions=regions,
        industries=industries,
        clients=clients,
        time_scope=time_scope,
        must_include_terms=must_include,
        generic_terms=generic_terms,
        exclusion_terms=exclusions,
        industry_methodology=methodology,
        scope_namespace=scope_namespace,
        status=status,
        reasons=reasons,
    )


def build_research_question_tree(
    *,
    contract: ResearchScopeContractOut,
    scope_hints: dict[str, object],
) -> ResearchQuestionTreeOut:
    methodology_questions = _dedupe(scope_hints.get("industry_methodology_questions", []) or [], 6)
    base = normalize_text(" ".join([*contract.regions[:1], *contract.industries[:1], *contract.clients[:1]]))
    nodes: list[ResearchQuestionNodeOut] = []
    for index, (axis, label, _tokens, preferred_tiers) in enumerate(_QUESTION_SPECS):
        question = methodology_questions[index] if index < len(methodology_questions) else {
            "demand_scope": "用户问题中的真实需求、场景边界和优先级分别是什么？",
            "policy_market": "哪些政策、监管、市场和时间信号能支撑该判断？",
            "buyer_procurement": "目标账户、决策部门、预算和采购窗口是否有一手证据？",
            "solution_competition": "现有方案、竞品、伙伴和可替代路径分别是什么？",
            "economics_delivery": "成本收益、实施周期、扩容和运维约束是否可量化？",
            "risk_counterevidence": "有哪些反证、冲突、合规和交付风险可能推翻当前结论？",
        }[axis]
        query_terms = _QUESTION_QUERY_TERMS[axis]
        query = normalize_text(f"{base} {query_terms}")
        official_site = _QUESTION_OFFICIAL_SITES.get(axis, "gov.cn")
        nodes.append(
            ResearchQuestionNodeOut(
                question_id=f"q_{index + 1:02d}_{axis}",
                axis=label,
                question=question,
                query=query,
                required_source_count=1,
                preferred_source_tiers=list(preferred_tiers),
                corrective_queries=[
                    normalize_text(f"{base} {query_terms} 官方 公告 数据"),
                    normalize_text(f"site:{official_site} {base} {query_terms}"),
                ],
            )
        )
    primary_corrective_queries = [node.corrective_queries[0] for node in nodes if node.corrective_queries]
    secondary_corrective_queries = [node.corrective_queries[1] for node in nodes if len(node.corrective_queries) > 1]
    return ResearchQuestionTreeOut(
        root_question=contract.keyword,
        question_count=len(nodes),
        uncovered_question_count=len(nodes),
        questions=nodes,
        corrective_queries=_dedupe(
            [*primary_corrective_queries, *secondary_corrective_queries],
            12,
        ),
    )


def _source_text(source: SourceDocument) -> str:
    # Search queries are intentionally excluded: they describe intent, not source content.
    return normalize_text(
        " ".join(
            [
                source.title,
                source.snippet,
                source.excerpt,
                source.source_label or "",
                source.domain or "",
            ]
        )
    ).casefold()


def _source_id(source: SourceDocument) -> str:
    return _stable_id("src", source.url, source.title, source.domain)


def _region_terms(regions: Sequence[str]) -> list[str]:
    return _dedupe(
        alias
        for region in regions
        for alias in (region, *REGION_SCOPE_ALIASES.get(region, ()))
    )


def _source_industry_labels(text: str) -> set[str]:
    labels: set[str] = set()
    for label, aliases in INDUSTRY_SCOPE_ALIASES.items():
        if label in _GENERIC_INDUSTRIES:
            continue
        if any(normalize_text(alias).casefold() in text for alias in (label, *aliases)):
            labels.add(label)
    return labels


def _matched_question_ids(text: str, tree: ResearchQuestionTreeOut) -> list[str]:
    matched: list[str] = []
    for node, spec in zip(tree.questions, _QUESTION_SPECS, strict=False):
        tokens = spec[2]
        if any(token.casefold() in text for token in tokens):
            matched.append(node.question_id)
    return matched


def _is_identity_only_source(source: SourceDocument) -> bool:
    identity_text = normalize_text(" ".join([source.search_query, source.snippet])).casefold()
    has_identity_marker = any(
        marker in identity_text
        for marker in (
            "官方公开入口",
            "优先用于补充官网",
            "优先用于补充官网、ir",
            "商务合作 联系方式",
        )
    )
    if not has_identity_marker:
        return False
    title = normalize_text(source.title).casefold()
    path = parse.urlparse(source.url).path.casefold().rstrip("/")
    identity_title = any(
        marker in title
        for marker in ("官网", "官方网站", "联系我们", "contact us", "投资者关系", "公司简介")
    )
    identity_path = any(
        marker in f"/{path.lstrip('/')}"
        for marker in ("/contact", "/about", "/company", "/profile", "/investor", "/ir/")
    )
    root_like_path = path in {"", "/china", "/cn", "/zh", "/zh-cn", "/global/home"}
    return identity_title or identity_path or root_like_path


def _is_static_institution_page(source: SourceDocument) -> bool:
    title = normalize_text(source.title).casefold()
    path = parse.urlparse(source.url).path.casefold().rstrip("/")
    static_path = path in {"", "/china", "/cn", "/zh", "/zh-cn", "/global/home"} or path.endswith(
        ("/portal/hall", "/pc/portal/hall")
    )
    institution_title = title.endswith(
        ("人民政府", "数据局", "管理局", "委员会", "政务服务网", "政府门户网站")
    )
    topical_title = any(
        token in title
        for token in ("通知", "公告", "方案", "政策", "行动", "改革", "项目", "招标", "中标", "人工智能", "建设")
    )
    return static_path and institution_title and not topical_title


def _is_unresolved_aggregator_source(source: SourceDocument) -> bool:
    parsed = parse.urlparse(source.url)
    domain = normalize_text(parsed.hostname or "").casefold().removeprefix("www.")
    title = normalize_text(source.title).casefold()
    return domain == "news.google.com" and (
        "/rss/articles/" in parsed.path.casefold() or title in {"google news", "谷歌新闻"}
    )


def _admit_source(
    source: SourceDocument,
    *,
    contract: ResearchScopeContractOut,
    question_tree: ResearchQuestionTreeOut,
    scope_hints: dict[str, object],
) -> ResearchSourceAdmissionOut:
    text = _source_text(source)
    topology = assess_source_topology(
        source,
        contract=contract,
        scope_hints=scope_hints,
    )
    industry_terms = _specific_industry_terms(contract.industries)
    region_terms = _region_terms(contract.regions)
    client_terms = contract.clients
    topic_terms = [term for term in contract.must_include_terms if term.casefold() not in _GENERIC_SCOPE_TERMS]
    industry_hits = [term for term in industry_terms if term.casefold() in text]
    region_hits = [term for term in region_terms if term.casefold() in text]
    client_hits = [term for term in client_terms if term.casefold() in text]
    topic_hits = [term for term in topic_terms if term.casefold() in text]
    exclusion_hits = [term for term in contract.exclusion_terms if term.casefold() in text]
    matched_questions = _matched_question_ids(text, question_tree)
    has_target_role_evidence = source_has_target_role_evidence(source, scope_hints=scope_hints)
    if contract.task_type == "account_intelligence" and not has_target_role_evidence:
        matched_questions = [
            question_id
            for question_id in matched_questions
            if not question_id.endswith("buyer_procurement")
        ]
    source_labels = _source_industry_labels(text)
    target_specific_labels = {industry for industry in contract.industries if industry not in _GENERIC_INDUSTRIES}
    conflict_labels = source_labels - target_specific_labels
    has_target_industry = bool(industry_hits) if target_specific_labels else bool(topic_hits)
    tier = source.source_tier if source.source_tier in {"official", "media", "aggregate"} else "media"
    score = 0
    score += 48 if industry_hits else 0
    score += min(24, len(topic_hits) * 6)
    score += 16 if region_hits else 0
    score += 24 if client_hits else 0
    score += min(12, len(matched_questions) * 3)
    score += 5 if tier == "official" else 0
    score = max(0, min(100, score))
    reasons: list[str] = []
    missing: list[str] = []

    normalized_title = normalize_text(source.title).casefold().strip(" -_|:：")
    # A known aggregation endpoint deserves its actionable diagnostic even when
    # the URL-safety classifier has also rejected the redirect host.
    if _is_unresolved_aggregator_source(source):
        decision = "rejected"
        reasons.append("聚合跳转页未还原到原始发布页面，不得作为独立主题证据。")
    elif not topology.url_safe:
        decision = "rejected"
        reasons.append("来源 URL 为搜索、跳转或不安全入口，不能作为证据。")
    elif topology.source_topology == "unqualified":
        decision = "rejected"
        reasons.append("来源不具备可采纳的证据拓扑。")
    elif _is_identity_only_source(source) or _is_static_institution_page(source):
        decision = "rejected"
        reasons.append("机构身份页只用于实体核验，不得作为主题事实证据。")
    elif (
        not text
        or source.content_status in {"failed", "error", "empty"}
        or normalized_title in _INVALID_PAGE_TITLES
        or any(token in normalized_title for token in _INVALID_PAGE_TITLE_TOKENS)
    ):
        decision = "rejected"
        reasons.append("来源正文为空、页面无效或抽取失败。")
    elif exclusion_hits:
        decision = "rejected"
        reasons.append(f"命中排除范围：{' / '.join(exclusion_hits[:3])}。")
    elif target_specific_labels and not has_target_industry:
        decision = "rejected"
        missing.extend(sorted(target_specific_labels))
        if conflict_labels:
            reasons.append(f"来源属于其他行业：{' / '.join(sorted(conflict_labels))}。")
        reasons.append("未命中目标行业的内容锚点；通用 AI/模型词不计为行业匹配。")
    elif target_specific_labels and conflict_labels and not industry_hits:
        decision = "rejected"
        reasons.append(f"来源行业与 scope contract 冲突：{' / '.join(sorted(conflict_labels))}。")
    elif not matched_questions:
        decision = "ambiguous" if score >= 35 else "rejected"
        reasons.append("来源与范围可能相关，但未能回答任何研究子问题。")
    elif score >= 45:
        decision = "accepted"
        reasons.append("来源通过主题锚点并至少覆盖一个研究子问题。")
    elif score >= 28:
        decision = "ambiguous"
        reasons.append("来源存在部分范围信号，尚不足以进入正式证据集合。")
    else:
        decision = "rejected"
        reasons.append("来源相关性不足。")

    if contract.regions and not region_hits:
        missing.append("区域锚点")
        if decision == "accepted":
            reasons.append("未直接命中区域，仅作为行业级背景证据。")
    return ResearchSourceAdmissionOut(
        source_id=_source_id(source),
        title=normalize_text(source.title),
        url=normalize_text(source.url),
        domain=normalize_text(source.domain or ""),
        source_tier=tier,  # type: ignore[arg-type]
        source_origin=(
            source.source_origin
            if source.source_origin in {"search", "adapter", "snapshot_cache", "user_supplied"}
            else "search"
        ),
        decision=decision,  # type: ignore[arg-type]
        relevance_score=score,
        **topology.as_admission_fields(),
        matched_scope_terms=_dedupe([*industry_hits, *region_hits, *client_hits, *topic_hits], 12),
        missing_scope_terms=_dedupe(missing, 8),
        matched_question_ids=matched_questions,
        reasons=_dedupe([*reasons, *topology.reasons], 6),
    )


def _apply_question_coverage(
    tree: ResearchQuestionTreeOut,
    admissions: Sequence[ResearchSourceAdmissionOut],
) -> ResearchQuestionTreeOut:
    accepted = [row for row in admissions if row.decision == "accepted"]
    nodes: list[ResearchQuestionNodeOut] = []
    for node in tree.questions:
        matches = [row for row in accepted if node.question_id in row.matched_question_ids]
        if node.question_id.endswith("buyer_procurement"):
            matches = [
                row
                for row in matches
                if row.source_topology == "local_target_proof" and row.account_pursuit_eligible
            ]
        else:
            matches = [
                row
                for row in matches
                if row.evidence_lane in {"decision", "context"} and row.formal_claim_eligible
            ]
        source_ids = [row.source_id for row in matches]
        official_count = sum(row.source_tier == "official" for row in matches)
        if len(matches) >= node.required_source_count:
            coverage_status = "covered"
        elif matches:
            coverage_status = "partial"
        else:
            coverage_status = "uncovered"
        nodes.append(
            node.model_copy(
                update={
                    "matched_source_ids": source_ids,
                    "accepted_source_count": len(matches),
                    "official_source_count": official_count,
                    "coverage_status": coverage_status,
                }
            )
        )
    covered = sum(node.coverage_status == "covered" for node in nodes)
    partial = sum(node.coverage_status == "partial" for node in nodes)
    uncovered = sum(node.coverage_status == "uncovered" for node in nodes)
    coverage = round(100 * covered / max(len(nodes), 1))
    status = "ready" if coverage >= 80 else "needs_retrieval" if accepted else "blocked"
    corrective = _dedupe(
        query
        for node in nodes
        if node.coverage_status != "covered"
        for query in node.corrective_queries
    )
    return tree.model_copy(
        update={
            "question_count": len(nodes),
            "covered_question_count": covered,
            "partial_question_count": partial,
            "uncovered_question_count": uncovered,
            "coverage_percent": coverage,
            "status": status,
            "questions": nodes,
            "corrective_queries": corrective,
        }
    )


def evaluate_research_evidence(
    sources: Sequence[SourceDocument],
    *,
    contract: ResearchScopeContractOut,
    question_tree: ResearchQuestionTreeOut,
    scope_hints: dict[str, object],
) -> ResearchEvidenceGovernanceResult:
    admissions = [
        _admit_source(
            source,
            contract=contract,
            question_tree=question_tree,
            scope_hints=scope_hints,
        )
        for source in sources
    ]
    admission_by_id = {row.source_id: row for row in admissions}
    accepted_sources = [
        source
        for source in sources
        if admission_by_id.get(_source_id(source)) is not None
        and admission_by_id[_source_id(source)].decision == "accepted"
    ]
    covered_tree = _apply_question_coverage(question_tree, admissions)
    accepted_rows = [row for row in admissions if row.decision == "accepted"]
    accepted_source_ids = {row.source_id for row in accepted_rows}
    concrete_buyer_source_count = sum(
        row.decision == "accepted" and row.account_pursuit_eligible
        for row in admissions
    )
    local_decision_source_count = sum(
        row.decision == "accepted" and row.evidence_lane == "decision" and row.current_signal
        for row in admissions
    )
    source_topology = topology_counts(
        [
            assess_source_topology(source, contract=contract, scope_hints=scope_hints)
            for source in sources
        ]
    )
    local_target_proof_count = sum(
        row.decision == "accepted" and row.source_topology == "local_target_proof"
        for row in admissions
    )
    external_benchmark_count = sum(
        row.decision == "accepted" and row.source_topology == "external_benchmark"
        for row in admissions
    )
    policy_context_count = sum(
        row.decision == "accepted" and row.source_topology == "policy_context"
        for row in admissions
    )
    historical_context_count = sum(
        row.decision == "accepted" and row.source_topology == "historical_context"
        for row in admissions
    )
    unsafe_source_count = sum(not row.url_safe for row in admissions)
    ambiguous_count = sum(row.decision == "ambiguous" for row in admissions)
    rejected_count = sum(row.decision == "rejected" for row in admissions)
    official_count = sum(row.source_tier == "official" for row in accepted_rows)
    unique_domains = len({row.domain.casefold() for row in accepted_rows if row.domain})
    deep = contract.research_mode == "deep"
    minimum_sources = 8 if deep else 4
    minimum_official = 3 if deep else 1
    minimum_domains = 5 if deep else 3
    minimum_coverage = 80 if deep else 60
    blockers: list[str] = []
    warnings: list[str] = []
    if contract.status != "ready":
        blockers.append("scope contract 尚未锁定行业、主体或具体场景。")
    if len(accepted_rows) < minimum_sources:
        blockers.append(f"有效来源 {len(accepted_rows)} 条，低于最低 {minimum_sources} 条。")
    if official_count < minimum_official:
        blockers.append(f"一手/官方来源 {official_count} 条，低于最低 {minimum_official} 条。")
    if unique_domains < minimum_domains:
        blockers.append(f"独立来源域 {unique_domains} 个，低于最低 {minimum_domains} 个。")
    if covered_tree.coverage_percent < minimum_coverage:
        blockers.append(
            f"子问题覆盖 {covered_tree.coverage_percent}%，低于最低 {minimum_coverage}%。"
        )
    account_task = requires_account_truth(contract)
    if account_task and concrete_buyer_source_count < 1:
        blockers.append("账户/方案任务未取得可验证的采购人、建设单位或需求负责方证据。")
    if account_task and local_decision_source_count < 2:
        blockers.append("账户/方案任务缺少至少两条当前本地决策证据，外部标杆不得替代本地机会证明。")
    reranker_enabled = bool(scope_hints.get("runtime_source_reranker_enabled"))
    runtime_status = normalize_text(str(scope_hints.get("runtime_strategy_status") or ""))
    reranker_used = bool(scope_hints.get("reranker_used"))
    runtime_blocked = reranker_enabled and runtime_status == "degraded" and not reranker_used
    if runtime_blocked:
        blockers.append("深度研究 reranker 已启用但运行降级，不能静默回退后继续正式交付。")
    elif deep and not reranker_enabled:
        warnings.append("当前未启用实验控制面的语义 reranker；来源仍经过确定性 scope gate。")
    if not accepted_rows and len(admissions) >= 2 and rejected_count == len(admissions):
        status = "blocked_topic_mismatch"
    elif runtime_blocked:
        status = "blocked_runtime_degraded"
    elif blockers:
        status = "evidence_gap"
    else:
        status = "evidence_ready"
    passed = status == "evidence_ready"
    next_actions = _dedupe(
        [
            "检索候选来源不足，请检查公共搜索可用性并扩展行业专用查询。" if len(admissions) < minimum_sources else "",
            "补充目标行业的一手政策、官网、采购或项目来源。" if official_count < minimum_official else "",
            "扩大独立来源域，避免转载或同源聚合重复计数。" if unique_domains < minimum_domains else "",
            (
                "补检采购公告、采购意向、项目业主或牵头建设单位，锁定至少一个具体账户。"
                if account_task and concrete_buyer_source_count < 1
                else ""
            ),
            "检查并恢复语义 reranker 后重跑。" if runtime_blocked else "",
            *covered_tree.corrective_queries,
        ],
        10,
    )
    gate = ResearchEvidenceGateOut(
        enforced=True,
        status=status,  # type: ignore[arg-type]
        passed=passed,
        formal_report_allowed=passed,
        solution_delivery_allowed=passed,
        minimum_source_count=minimum_sources,
        minimum_official_source_count=minimum_official,
        minimum_unique_domain_count=minimum_domains,
        minimum_question_coverage_percent=minimum_coverage,
        candidate_source_count=len(admissions),
        accepted_source_count=len(accepted_rows),
        ambiguous_source_count=ambiguous_count,
        rejected_source_count=rejected_count,
        official_source_count=official_count,
        unique_domain_count=unique_domains,
        question_coverage_percent=covered_tree.coverage_percent,
        local_target_proof_count=local_target_proof_count,
        local_decision_source_count=local_decision_source_count,
        external_benchmark_count=external_benchmark_count,
        policy_context_count=policy_context_count,
        historical_context_count=historical_context_count,
        unsafe_source_count=unsafe_source_count,
        blockers=_dedupe(blockers, 8),
        warnings=_dedupe(warnings, 6),
        next_actions=next_actions,
    )
    return ResearchEvidenceGovernanceResult(
        contract=contract,
        question_tree=covered_tree,
        admissions=admissions,
        gate=gate,
        accepted_sources=accepted_sources,
    )


def build_research_evidence_governance(
    sources: Sequence[SourceDocument],
    *,
    keyword: str,
    research_focus: str | None,
    research_mode: str,
    scope_hints: dict[str, object],
) -> ResearchEvidenceGovernanceResult:
    contract = build_research_scope_contract(
        keyword=keyword,
        research_focus=research_focus,
        research_mode=research_mode,
        scope_hints=scope_hints,
    )
    tree = build_research_question_tree(contract=contract, scope_hints=scope_hints)
    return evaluate_research_evidence(
        sources,
        contract=contract,
        question_tree=tree,
        scope_hints=scope_hints,
    )


def apply_evidence_governance_diagnostics(
    diagnostics: ResearchSourceDiagnosticsOut,
    result: ResearchEvidenceGovernanceResult,
) -> ResearchSourceDiagnosticsOut:
    candidate_count = result.gate.candidate_source_count
    accepted_count = result.gate.accepted_source_count
    strict_ratio = accepted_count / max(candidate_count, 1) if candidate_count else 0.0
    relevance_score = round(
        sum(row.relevance_score for row in result.admissions if row.decision == "accepted")
        / max(accepted_count, 1)
    )
    correction_status = "ready" if result.gate.passed else "needs_expansion"
    if result.gate.status == "blocked_topic_mismatch":
        correction_status = "needs_filtering"
    return diagnostics.model_copy(
        update={
            "retained_source_count": accepted_count,
            "strict_topic_source_count": accepted_count,
            "strict_match_ratio": round(strict_ratio, 3),
            "official_source_ratio": round(result.gate.official_source_count / max(accepted_count, 1), 3),
            "unique_domain_count": result.gate.unique_domain_count,
            "retrieval_quality": "high" if result.gate.passed else "low",
            "evidence_mode": "strong" if result.gate.passed else "fallback",
            "evidence_mode_label": "证据门已通过" if result.gate.passed else "证据门已阻断",
            "correction_status": correction_status,
            "retrieval_relevance_score": relevance_score,
            "accepted_source_count": accepted_count,
            "ambiguous_source_count": result.gate.ambiguous_source_count,
            "rejected_source_count": result.gate.rejected_source_count,
            "source_topology_counts": {
                "local_target_proof": result.gate.local_target_proof_count,
                "local_comparable": max(
                    0,
                    result.gate.local_decision_source_count - result.gate.local_target_proof_count,
                ),
                "external_benchmark": result.gate.external_benchmark_count,
                "policy_context": result.gate.policy_context_count,
                "historical_context": result.gate.historical_context_count,
                "unqualified": result.gate.unsafe_source_count,
            },
            "local_target_proof_count": result.gate.local_target_proof_count,
            "local_decision_source_count": result.gate.local_decision_source_count,
            "external_benchmark_count": result.gate.external_benchmark_count,
            "policy_context_count": result.gate.policy_context_count,
            "historical_context_count": result.gate.historical_context_count,
            "unsafe_source_count": result.gate.unsafe_source_count,
            "corrective_query_plan": result.question_tree.corrective_queries,
            "correction_notes": _dedupe([*result.gate.blockers, *result.gate.warnings], 8),
        }
    )


def render_question_tree_prompt_context(tree: ResearchQuestionTreeOut) -> str:
    lines = [
        f"Question coverage gate: {tree.coverage_percent}% ({tree.covered_question_count}/{tree.question_count})",
        "Only use accepted evidence assigned to the corresponding question. Do not move evidence across questions.",
    ]
    for node in tree.questions:
        lines.append(
            f"- [{node.question_id}] {node.axis}: {node.question} | accepted={node.accepted_source_count} | status={node.coverage_status}"
        )
    return "\n".join(lines)


def build_evidence_gap_report(
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    research_mode: str,
    query_plan: Sequence[str],
    governance: ResearchEvidenceGovernanceResult,
    source_diagnostics: ResearchSourceDiagnosticsOut,
    entity_graph: ResearchEntityGraphOut | None = None,
) -> ResearchReportResponse:
    english = output_language == "en"
    title = (
        f"{keyword}: Evidence Gap Brief"
        if english
        else f"{keyword}：证据缺口与补证路径"
    )
    blockers = governance.gate.blockers or ["当前证据未达到正式研报门槛。"]
    candidate_count = governance.gate.candidate_source_count
    accepted_count = governance.gate.accepted_source_count
    ambiguous_count = governance.gate.ambiguous_source_count
    rejected_count = governance.gate.rejected_source_count
    summary = (
        f"This is not a formal report. Retrieval found {candidate_count} candidates, but only "
        f"{accepted_count} passed the evidence gate. " + " ".join(blockers[:3])
        if english
        else (
            f"本轮不是正式研报。检索得到 {candidate_count} 条候选来源，仅 {accepted_count} 条通过证据门；"
            + "；".join(blockers[:3])
        )
    )
    diagnostic_section = ResearchReportSectionOut(
        title="Retrieval diagnosis" if english else "本轮检索诊断",
        items=[
            (
                f"Candidates {candidate_count}; accepted {accepted_count}; ambiguous {ambiguous_count}; rejected {rejected_count}."
                if english
                else f"候选 {candidate_count} 条；通过 {accepted_count} 条；待复核 {ambiguous_count} 条；拒绝 {rejected_count} 条。"
            ),
            *blockers[:3],
        ],
        status="needs_evidence",
        evidence_density="low",
        source_quality="low",
        confidence_tone="low",
        confidence_label="Evidence required" if english else "待补证",
        confidence_reason="The formal evidence gate did not pass." if english else "正式证据门未通过。",
        insufficiency_reasons=blockers[:4],
        insufficiency_summary=summary,
        evidence_count=accepted_count,
        evidence_quota=governance.gate.minimum_source_count,
        meets_evidence_quota=False,
        quota_gap=max(0, governance.gate.minimum_source_count - accepted_count),
        next_verification_steps=governance.gate.next_actions[:3],
    )
    candidate_rows = [
        normalize_text(
            " | ".join(
                [
                    row.decision,
                    row.title,
                    row.reasons[0] if row.reasons else "",
                    row.url,
                ]
            )
        )
        for row in governance.admissions
        if row.decision != "accepted"
    ][:6]
    candidate_section = ResearchReportSectionOut(
        title="Candidate evidence review" if english else "候选证据复核清单",
        items=candidate_rows or governance.gate.next_actions[:3],
        status="needs_evidence",
        evidence_density="low",
        source_quality="low",
        confidence_tone="low",
        confidence_label="Review required" if english else "需复核",
        confidence_reason=(
            "These sources were found but did not qualify as formal evidence."
            if english
            else "这些来源已被检索到，但尚未达到正式证据标准。"
        ),
        insufficiency_reasons=blockers[:3],
        insufficiency_summary=(
            "Review scope matching, extraction quality, and source independence before admission."
            if english
            else "需复核主题匹配、正文抽取质量和来源独立性后再决定是否采纳。"
        ),
        evidence_count=0,
        evidence_quota=max(1, governance.gate.minimum_source_count),
        meets_evidence_quota=False,
        quota_gap=max(1, governance.gate.minimum_source_count),
        next_verification_steps=governance.gate.next_actions[:3],
    )
    question_sections = [
        ResearchReportSectionOut(
            title=node.axis,
            items=node.corrective_queries[:2] or governance.gate.next_actions[:2],
            status="needs_evidence",
            evidence_density="low",
            source_quality="low",
            confidence_tone="low",
            confidence_label="待补证" if not english else "Evidence required",
            confidence_reason=node.question,
            insufficiency_reasons=[node.coverage_status],
            insufficiency_summary=(
                f"该子问题当前命中 {node.accepted_source_count} 条可用来源。"
                if not english
                else f"This question currently has {node.accepted_source_count} accepted sources."
            ),
            evidence_count=node.accepted_source_count,
            evidence_quota=node.required_source_count,
            meets_evidence_quota=False,
            quota_gap=max(0, node.required_source_count - node.accepted_source_count),
            next_verification_steps=node.corrective_queries[:3],
        )
        for node in governance.question_tree.questions
        if node.coverage_status != "covered"
    ]
    sections = [diagnostic_section, candidate_section, *question_sections]
    readiness = ResearchReportReadinessOut(
        status="needs_evidence",
        score=20 if governance.gate.status == "blocked_topic_mismatch" else 35,
        actionable=False,
        evidence_gate_passed=False,
        reasons=blockers[:5],
        missing_axes=[node.axis for node in governance.question_tree.questions if node.coverage_status != "covered"][:5],
        next_verification_steps=governance.gate.next_actions[:5],
    )
    citation_gate = ResearchCitationGateOut(
        enforced=True,
        status="fail",
        passed=False,
        blockers=["研究证据门未通过，未进入主张起草和引用检查阶段。"],
    )
    solution_stub = ResearchSolutionDeliveryPackOut(
        scenario=keyword,
        evidence_policy="研究证据门未通过，仅返回补证动作，不生成架构蓝图或客户版材料。",
        clarification_questions=governance.gate.next_actions[:5],
        grounding_checks=blockers[:5],
        next_steps=governance.gate.next_actions[:5],
    )
    return ResearchReportResponse(
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,  # type: ignore[arg-type]
        research_mode=research_mode,  # type: ignore[arg-type]
        report_title=title,
        executive_summary=summary,
        consulting_angle=(
            "Use this brief to close evidence gaps before analysis."
            if english
            else "本轮只用于补证，不作为商业判断或解决方案输入。"
        ),
        sections=sections,
        source_count=len(governance.accepted_sources),
        evidence_density="low",
        source_quality="low",
        query_plan=_dedupe([*query_plan, *governance.question_tree.corrective_queries], 24),
        sources=source_documents_to_research_source_outputs(governance.accepted_sources),
        source_diagnostics=source_diagnostics,
        research_scope_contract=governance.contract,
        research_question_tree=governance.question_tree,
        research_source_admissions=governance.admissions,
        research_evidence_gate=governance.gate,
        research_citation_gate=citation_gate,
        entity_graph=entity_graph or ResearchEntityGraphOut(),
        report_readiness=readiness,
        solution_delivery_pack=solution_stub,
        generated_at=datetime.now(timezone.utc),
    )


def _atomic_claim_rows(report: ResearchReportResponse) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []

    def append(section: str, value: object) -> None:
        for segment in _ATOMIC_SPLIT_RE.split(normalize_text(str(value or ""))):
            normalized = normalize_text(segment)
            if len(normalized) < 8 or _CITATION_ONLY_RE.fullmatch(normalized):
                continue
            rows.append((section, normalized))

    append("执行摘要", report.executive_summary)
    for section in report.sections:
        for item in section.items:
            append(section.title, item)
    for label, values in (
        ("目标账户", report.target_accounts),
        ("预算与采购", report.budget_signals),
        ("招采时间线", report.tender_timeline),
        ("战略方向", report.strategic_directions),
        ("竞争分析", report.competition_analysis),
        ("标杆案例", report.benchmark_cases),
        ("未来展望", report.five_year_outlook),
    ):
        for value in values:
            append(label, value)
    return rows[:120]


def _research_evidence_links(report: ResearchReportResponse) -> list[ResearchEntityEvidenceOut]:
    links_by_key: dict[str, ResearchEntityEvidenceOut] = {}
    key_order: list[str] = []

    def add(link: ResearchEntityEvidenceOut) -> None:
        key = normalize_text(link.url) or normalize_text(f"{link.title}|{link.excerpt}")
        if not key:
            return
        current = links_by_key.get(key)
        if current is None:
            links_by_key[key] = link
            key_order.append(key)
            return
        current_quality = (
            1 if current.source_tier == "official" else 0,
            len(normalize_text(current.excerpt)),
            len(normalize_text(current.anchor_text)),
        )
        candidate_quality = (
            1 if link.source_tier == "official" else 0,
            len(normalize_text(link.excerpt)),
            len(normalize_text(link.anchor_text)),
        )
        if candidate_quality > current_quality:
            links_by_key[key] = link

    for section in report.sections:
        for link in section.evidence_links:
            add(link)
    for source in report.sources:
        add(
            ResearchEntityEvidenceOut(
                title=source.title,
                url=source.url,
                source_label=source.source_label,
                source_tier=source.source_tier,
                anchor_text=source.search_query,
                excerpt=source.snippet,
                confidence_tone="high" if source.source_tier == "official" else "low",
            )
        )
    return [links_by_key[key] for key in key_order[:60]]


def build_research_claim_governance(report: ResearchReportResponse) -> ResearchClaimGovernanceResult:
    ledger = build_delivery_evidence_ledger(
        _atomic_claim_rows(report),
        evidence_links=_research_evidence_links(report),
        expected_entities=[
            *report.target_accounts[:4],
            *(entity.name for entity in report.top_target_accounts[:4]),
        ],
    )
    evidence_required_claims = [
        claim
        for claim in ledger.claims
        if claim.claim_type not in {"recommendation", "assumption"}
    ]
    critical_claims = [claim for claim in evidence_required_claims if claim.confidence == "high"]
    unsupported_critical = [
        claim.claim_id
        for claim in critical_claims
        if claim.verification_status != "supported"
    ]
    critical_supported = len(critical_claims) - len(unsupported_critical)
    critical_coverage = (
        round(100 * critical_supported / len(critical_claims))
        if critical_claims
        else 100
    )
    supported_claim_count = sum(
        claim.verification_status == "supported"
        for claim in evidence_required_claims
    )
    conflicted_claim_count = sum(
        claim.verification_status == "conflicted"
        for claim in evidence_required_claims
    )
    claim_coverage = (
        round(100 * supported_claim_count / len(evidence_required_claims))
        if evidence_required_claims
        else 0
    )
    support_denominator = supported_claim_count + conflicted_claim_count
    support_percent = (
        round(100 * supported_claim_count / support_denominator)
        if support_denominator
        else 0
    )
    blockers: list[str] = []
    warnings: list[str] = []
    if not evidence_required_claims:
        blockers.append("成稿未提取到可核验原子主张。")
    if conflicted_claim_count:
        blockers.append(f"存在 {conflicted_claim_count} 条冲突主张。")
    if critical_coverage < 100:
        blockers.append(f"关键主张证据覆盖 {critical_coverage}%，低于 100%。")
    if claim_coverage < 90:
        blockers.append(f"事实主张证据完整率 {claim_coverage}%，低于 90%。")
    if support_percent < 95:
        warnings.append(f"已建立关系中的引用支持率 {support_percent}%，低于 95%。")
    if not blockers and support_percent >= 95:
        status = "pass"
    elif not conflicted_claim_count and critical_coverage == 100 and claim_coverage >= 70:
        status = "watch"
    else:
        status = "fail"
    gate = ResearchCitationGateOut(
        enforced=True,
        status=status,  # type: ignore[arg-type]
        passed=status == "pass",
        claim_count=len(evidence_required_claims),
        supported_claim_count=supported_claim_count,
        critical_claim_count=len(critical_claims),
        supported_critical_claim_count=critical_supported,
        conflicted_claim_count=conflicted_claim_count,
        citation_completeness_percent=claim_coverage,
        critical_claim_coverage_percent=critical_coverage,
        citation_support_percent=support_percent,
        unsupported_critical_claim_ids=unsupported_critical[:20],
        blockers=_dedupe(blockers, 8),
        warnings=_dedupe(warnings, 6),
    )
    return ResearchClaimGovernanceResult(ledger=ledger, citation_gate=gate)
