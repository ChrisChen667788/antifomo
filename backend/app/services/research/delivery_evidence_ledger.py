from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from hashlib import sha256
import re
from urllib.parse import urlsplit, urlunsplit

from app.schemas.research import (
    ResearchDeliveryClaimEvidenceRelationOut,
    ResearchDeliveryClaimOut,
    ResearchDeliveryConsistencyIssueOut,
    ResearchDeliveryEvidenceAnchorOut,
    ResearchDeliveryEvidenceLedgerOut,
    ResearchDeliveryNumericFactOut,
    ResearchEntityEvidenceOut,
)
from app.services.content_extractor import normalize_text

DeliveryRow = tuple[str, str]

_URL_PATTERN = re.compile(r"https?://[^\s；;，,）)>\]]+", re.IGNORECASE)
_DOCUMENT_REF_PATTERN = re.compile(
    r"(?:项目|采购|招标|合同|公告)(?:编号|编码)[:：]?\s*([A-Za-z0-9][A-Za-z0-9._/-]{3,})",
    re.IGNORECASE,
)
_NUMBER_PATTERN = re.compile(
    r"(?P<number>\d+(?:\.\d+)?)\s*(?P<unit>亿元|万元|元|%|％|年|个月|月|天|家|项|条|倍|套|路)",
    re.IGNORECASE,
)
_ENTITY_PATTERN = re.compile(
    r"([A-Za-z0-9\u4e00-\u9fff·（）()]{2,46}"
    r"(?:集团|股份有限公司|有限公司|公司|科技|信息|软件|智能|半导体|大学|学院|医院|银行|政府|数据局|管理局|局|委员会|委|办公室|办|中心))"
)
_ROLE_PATTERN = re.compile(
    r"(?P<role>目标客户|建议业主|建设单位|采购人|业主单位|中标供应商|中标人)"
    r"[:：]?\s*(?P<entity>[A-Za-z0-9\u4e00-\u9fff·（）()]{2,60})"
)

_ASSUMPTION_TOKENS = ("待核验", "待确认", "假设", "建议口径", "预计", "暂按", "可能")
_RECOMMENDATION_TOKENS = ("建议", "推荐", "应当", "优先", "宜", "需要")
_PROCUREMENT_TOKENS = ("采购", "招标", "中标", "投标", "预算金额", "项目编号")
_COMPLIANCE_TOKENS = ("等保", "信创", "密码", "数据安全", "网络安全", "合规")
_SCENARIO_TOKENS = ("方案", "情景", "场景", "区间", "范围", "分档", "基准", "乐观", "悲观", "上限", "下限")

_METRIC_TOKENS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("budget_amount", ("预算金额", "项目预算", "投资估算", "总投资", "预算")),
    ("winning_amount", ("中标金额", "成交金额")),
    ("procurement_amount", ("采购金额",)),
    ("construction_period", ("建设周期", "实施周期", "工期")),
    ("payback_period", ("回收期",)),
    ("coverage_rate", ("覆盖率",)),
    ("growth_rate", ("同比增长", "增长率")),
    ("reduction_rate", ("降低", "下降率")),
    ("improvement_rate", ("提升", "提高")),
    ("concurrency", ("并发",)),
)


def _stable_id(prefix: str, *values: object) -> str:
    seed = "\x1f".join(normalize_text(str(value or "")).lower() for value in values)
    return f"{prefix}_{sha256(seed.encode('utf-8')).hexdigest()[:16]}"


def _canonical_url(value: str) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    try:
        parts = urlsplit(normalized)
    except ValueError:
        return normalized
    if not parts.scheme or not parts.netloc:
        return normalized
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))


def _dedupe(values: Iterable[object], *, limit: int = 20) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_text(str(value or ""))
        if not normalized or normalized in seen:
            continue
        rows.append(normalized)
        seen.add(normalized)
        if len(rows) >= limit:
            break
    return rows


def _extract_entities(value: str) -> list[str]:
    rows = [normalize_text(match.group(1)) for match in _ENTITY_PATTERN.finditer(value)]
    for match in _ROLE_PATTERN.finditer(value):
        candidate = normalize_text(match.group("entity")).strip("，,；;。.!！?")
        candidate = re.split(r"(?:预算|建设周期|项目编号|来源|证据)[:：]?", candidate, maxsplit=1)[0]
        if candidate:
            rows.append(candidate)
    return _dedupe(rows, limit=10)


def _metric_for_context(value: str, start: int, end: int, unit: str) -> str:
    if unit in {"亿元", "万元", "元"}:
        allowed_metrics = {"budget_amount", "winning_amount", "procurement_amount"}
    elif unit in {"年", "个月", "月", "天"}:
        allowed_metrics = {"construction_period", "payback_period"}
    elif unit in {"%", "％"}:
        allowed_metrics = {"coverage_rate", "growth_rate", "reduction_rate", "improvement_rate"}
    elif unit == "路":
        allowed_metrics = {"concurrency"}
    else:
        allowed_metrics = set()
    candidates: list[tuple[int, str]] = []
    for metric, tokens in _METRIC_TOKENS:
        if allowed_metrics and metric not in allowed_metrics:
            continue
        for token in tokens:
            before = value.rfind(token, max(0, start - 24), start)
            if before >= 0:
                candidates.append((start - (before + len(token)), metric))
            after = value.find(token, end, min(len(value), end + 16))
            if after >= 0:
                candidates.append((after - end, metric))
    if candidates:
        candidates.sort(key=lambda item: (item[0], item[1]))
        return candidates[0][1]
    if unit in {"亿元", "万元", "元"}:
        return "amount"
    if unit in {"%", "％"}:
        return "percentage"
    if unit in {"年", "个月", "月", "天"}:
        return "duration"
    return "quantity"


def _normalize_numeric_value(number: float, unit: str) -> tuple[float, str]:
    if unit == "亿元":
        return number * 100_000_000, "CNY"
    if unit == "万元":
        return number * 10_000, "CNY"
    if unit == "元":
        return number, "CNY"
    if unit in {"%", "％"}:
        return number / 100, "ratio"
    if unit == "年":
        return number * 12, "month"
    if unit in {"个月", "月"}:
        return number, "month"
    if unit == "天":
        return number / 30, "month"
    return number, unit


def _extract_numeric_facts(value: str) -> list[ResearchDeliveryNumericFactOut]:
    rows: list[ResearchDeliveryNumericFactOut] = []
    for match in _NUMBER_PATTERN.finditer(value):
        raw_number = match.group("number")
        unit = match.group("unit")
        number = float(raw_number)
        if unit == "年" and 1900 <= number <= 2100:
            metric = "calendar_year"
            normalized_value, normalized_unit = number, "year"
        else:
            metric = _metric_for_context(value, match.start(), match.end(), unit)
            normalized_value, normalized_unit = _normalize_numeric_value(number, unit)
        rows.append(
            ResearchDeliveryNumericFactOut(
                metric=metric,
                raw_value=f"{raw_number}{unit}",
                normalized_value=round(normalized_value, 6),
                normalized_unit=normalized_unit,
                context=normalize_text(value[max(0, match.start() - 22) : min(len(value), match.end() + 22)]),
            )
        )
    return rows[:12]


def _claim_type(value: str, numeric_facts: Sequence[ResearchDeliveryNumericFactOut]) -> str:
    if any(token in value for token in _ASSUMPTION_TOKENS):
        return "assumption"
    if any(token in value for token in _RECOMMENDATION_TOKENS):
        return "recommendation"
    if any(token in value for token in _PROCUREMENT_TOKENS):
        return "procurement"
    if any(token in value for token in _COMPLIANCE_TOKENS):
        return "compliance"
    if numeric_facts:
        return "numeric"
    return "fact"


def _claim_confidence(claim_type: str, value: str) -> str:
    if claim_type == "assumption":
        return "low"
    if claim_type in {"numeric", "procurement", "compliance"}:
        return "high"
    if any(token in value for token in _RECOMMENDATION_TOKENS):
        return "medium"
    return "medium"


def _document_ref(value: str) -> str:
    match = _DOCUMENT_REF_PATTERN.search(value)
    return normalize_text(match.group(1)) if match else ""


def _inline_evidence(rows: Sequence[DeliveryRow]) -> list[ResearchEntityEvidenceOut]:
    evidence: list[ResearchEntityEvidenceOut] = []
    seen: set[tuple[str, str]] = set()
    for section_title, text in rows:
        urls = [_canonical_url(match.group(0)) for match in _URL_PATTERN.finditer(text)]
        document_ref = _document_ref(text)
        for url in urls:
            key = (url, document_ref)
            if key in seen:
                continue
            seen.add(key)
            evidence.append(
                ResearchEntityEvidenceOut(
                    title=f"{section_title}行内证据",
                    url=url,
                    source_label=document_ref or "inline",
                    source_tier="official" if ".gov.cn" in url.lower() else "media",
                    anchor_text=document_ref,
                    excerpt=text,
                )
            )
    return evidence


def _to_anchor(link: ResearchEntityEvidenceOut) -> ResearchDeliveryEvidenceAnchorOut:
    url = _canonical_url(link.url)
    document_ref = normalize_text(link.anchor_text) or _document_ref(
        " ".join([link.title, link.excerpt, link.anchor_text])
    )
    evidence_id = _stable_id("ev", url or document_ref or link.title)
    text = normalize_text(" ".join([link.title, link.anchor_text, link.excerpt]))
    return ResearchDeliveryEvidenceAnchorOut(
        evidence_id=evidence_id,
        title=normalize_text(link.title),
        url=url,
        source_label=link.source_label,
        source_tier=link.source_tier,
        anchor_text=normalize_text(link.anchor_text),
        excerpt=normalize_text(link.excerpt),
        document_ref=document_ref,
        entities=_extract_entities(text),
        numeric_facts=_extract_numeric_facts(text),
    )


def _token_set(value: str) -> set[str]:
    normalized = normalize_text(value).lower()
    latin = set(re.findall(r"[a-z0-9]{2,}", normalized))
    chinese_runs = re.findall(r"[\u4e00-\u9fff]{2,}", normalized)
    chinese: set[str] = set()
    for run in chinese_runs:
        chinese.add(run)
        chinese.update(run[index : index + 2] for index in range(max(0, len(run) - 1)))
        chinese.update(run[index : index + 3] for index in range(max(0, len(run) - 2)))
    return latin | chinese


def _numeric_relation(
    claim_facts: Sequence[ResearchDeliveryNumericFactOut],
    evidence_facts: Sequence[ResearchDeliveryNumericFactOut],
) -> tuple[bool, bool]:
    supports = False
    conflicts = False
    comparable_metrics = {
        "budget_amount",
        "winning_amount",
        "procurement_amount",
        "construction_period",
        "payback_period",
        "coverage_rate",
        "growth_rate",
        "reduction_rate",
        "improvement_rate",
        "concurrency",
    }
    for claim_fact in claim_facts:
        if claim_fact.metric not in comparable_metrics:
            continue
        for evidence_fact in evidence_facts:
            if claim_fact.metric != evidence_fact.metric:
                continue
            if claim_fact.normalized_unit != evidence_fact.normalized_unit:
                conflicts = True
                continue
            left = float(claim_fact.normalized_value or 0)
            right = float(evidence_fact.normalized_value or 0)
            tolerance = max(abs(left), abs(right), 1.0) * 0.01
            if abs(left - right) <= tolerance:
                supports = True
            else:
                conflicts = True
    return supports, conflicts


def _relation(
    claim: ResearchDeliveryClaimOut,
    evidence: ResearchDeliveryEvidenceAnchorOut,
) -> ResearchDeliveryClaimEvidenceRelationOut | None:
    claim_urls = {_canonical_url(match.group(0)) for match in _URL_PATTERN.finditer(claim.text)}
    direct_url = bool(evidence.url and evidence.url in claim_urls)
    direct_ref = bool(evidence.document_ref and evidence.document_ref.lower() in claim.text.lower())
    entity_overlap = set(claim.entities) & set(evidence.entities)
    numeric_support, numeric_conflict = _numeric_relation(claim.numeric_facts, evidence.numeric_facts)
    overlap = len(_token_set(claim.text) & _token_set(" ".join([evidence.title, evidence.anchor_text, evidence.excerpt])))

    if numeric_conflict and (entity_overlap or overlap >= 2):
        return ResearchDeliveryClaimEvidenceRelationOut(
            evidence_id=evidence.evidence_id,
            relation_type="conflicts",
            score=min(100, 55 + overlap * 4 + len(entity_overlap) * 10),
            rationale="证据与主张包含同类指标，但归一化后的数字或单位不一致。",
        )
    if direct_url or direct_ref or numeric_support or (entity_overlap and overlap >= 2) or overlap >= 6:
        reasons = _dedupe(
            [
                "行内 URL 一致" if direct_url else "",
                "文号/项目编号一致" if direct_ref else "",
                "数字口径一致" if numeric_support else "",
                "实体一致" if entity_overlap else "",
                f"文本锚点重合 {overlap} 个" if overlap else "",
            ],
            limit=4,
        )
        return ResearchDeliveryClaimEvidenceRelationOut(
            evidence_id=evidence.evidence_id,
            relation_type="supports",
            score=min(100, 58 + overlap * 4 + len(entity_overlap) * 10 + (15 if numeric_support else 0)),
            rationale="；".join(reasons),
        )
    if overlap >= 2 or entity_overlap:
        return ResearchDeliveryClaimEvidenceRelationOut(
            evidence_id=evidence.evidence_id,
            relation_type="background",
            score=min(70, 24 + overlap * 6 + len(entity_overlap) * 8),
            rationale="来源与主张主题相关，但尚不足以直接支撑该结论。",
        )
    return None


def _verification_status(relations: Sequence[ResearchDeliveryClaimEvidenceRelationOut]) -> str:
    if any(relation.relation_type == "conflicts" for relation in relations):
        return "conflicted"
    if any(relation.relation_type == "supports" for relation in relations):
        return "supported"
    if any(relation.relation_type == "background" for relation in relations):
        return "background_only"
    return "needs_validation"


def _issue(issue_type: str, severity: str, claim_ids: Iterable[str], summary: str, details: Iterable[str]):
    normalized_claim_ids = sorted(set(claim_ids))
    return ResearchDeliveryConsistencyIssueOut(
        issue_id=_stable_id("issue", issue_type, *normalized_claim_ids, summary),
        issue_type=issue_type,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        claim_ids=normalized_claim_ids,
        summary=summary,
        details=_dedupe(details, limit=6),
    )


def _entity_issues(
    claims: Sequence[ResearchDeliveryClaimOut],
    *,
    expected_entities: Sequence[str],
) -> list[ResearchDeliveryConsistencyIssueOut]:
    issues: list[ResearchDeliveryConsistencyIssueOut] = []
    role_values: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    expected = {normalize_text(value) for value in expected_entities if normalize_text(value)}
    for claim in claims:
        for match in _ROLE_PATTERN.finditer(claim.text):
            role = normalize_text(match.group("role"))
            entity = normalize_text(match.group("entity")).strip("，,；;。.!！?")
            entity = re.split(r"(?:预算|建设周期|项目编号|来源|证据)[:：]?", entity, maxsplit=1)[0]
            if entity:
                role_values[(claim.section_title, role)].append((claim.claim_id, entity))
                if role in {"目标客户", "建议业主", "建设单位"} and expected and entity not in expected:
                    issues.append(
                        _issue(
                            "entity_role_conflict",
                            "high",
                            [claim.claim_id],
                            f"{role}与已锁定主体不一致。",
                            [f"文档值：{entity}", f"锁定主体：{'；'.join(sorted(expected))}"],
                        )
                    )
        if claim.entities and claim.confidence == "high" and claim.verification_status == "needs_validation":
            issues.append(
                _issue(
                    "entity_not_supported",
                    "medium",
                    [claim.claim_id],
                    "高置信主张中的实体没有直接支持证据。",
                    claim.entities,
                )
            )
    for (section_title, role), values in role_values.items():
        distinct = sorted({value for _claim_id, value in values})
        if len(distinct) <= 1:
            continue
        issues.append(
            _issue(
                "entity_role_conflict",
                "high",
                [claim_id for claim_id, _value in values],
                f"{section_title or '文档'}中的{role}存在多个不一致主体。",
                distinct,
            )
        )
    return issues


def _numeric_issues(claims: Sequence[ResearchDeliveryClaimOut]) -> list[ResearchDeliveryConsistencyIssueOut]:
    groups: dict[tuple[str, str, str], list[tuple[ResearchDeliveryClaimOut, ResearchDeliveryNumericFactOut]]] = defaultdict(list)
    for claim in claims:
        entity_key = "|".join(sorted(claim.entities)) or "global"
        for fact in claim.numeric_facts:
            if fact.metric in {"quantity", "amount", "duration", "percentage"}:
                continue
            groups[(claim.section_title, entity_key, fact.metric)].append((claim, fact))

    issues: list[ResearchDeliveryConsistencyIssueOut] = []
    for (section_title, _entity_key, metric), values in groups.items():
        if len(values) <= 1:
            continue
        if all(any(token in claim.text for token in _SCENARIO_TOKENS) for claim, _fact in values):
            continue
        units = {fact.normalized_unit for _claim, fact in values}
        if len(units) > 1:
            issues.append(
                _issue(
                    "numeric_unit_mismatch",
                    "high",
                    [claim.claim_id for claim, _fact in values],
                    f"{section_title or '文档'}中的 {metric} 使用了无法统一的单位。",
                    [f"{fact.raw_value} -> {fact.normalized_unit}" for _claim, fact in values],
                )
            )
            continue
        normalized_values = sorted({round(float(fact.normalized_value or 0), 6) for _claim, fact in values})
        if len(normalized_values) <= 1:
            continue
        highest = max(abs(value) for value in normalized_values)
        if highest and max(normalized_values) - min(normalized_values) <= highest * 0.01:
            continue
        issues.append(
            _issue(
                "numeric_conflict",
                "high",
                [claim.claim_id for claim, _fact in values],
                f"{section_title or '文档'}中的 {metric} 存在相互冲突的数字口径。",
                [f"{claim.text} [{fact.raw_value}]" for claim, fact in values],
            )
        )
    return issues


def build_delivery_evidence_ledger(
    rows: Sequence[DeliveryRow],
    *,
    evidence_links: Sequence[ResearchEntityEvidenceOut] = (),
    expected_entities: Sequence[str] = (),
) -> ResearchDeliveryEvidenceLedgerOut:
    normalized_rows: list[DeliveryRow] = []
    seen_rows: set[tuple[str, str]] = set()
    for raw_section, raw_text in rows:
        section = normalize_text(raw_section)
        text = normalize_text(raw_text)
        key = (section, text)
        if not text or key in seen_rows:
            continue
        seen_rows.add(key)
        normalized_rows.append(key)

    all_links = [*evidence_links, *_inline_evidence(normalized_rows)]
    evidence_by_id: dict[str, ResearchDeliveryEvidenceAnchorOut] = {}
    for link in all_links:
        anchor = _to_anchor(link)
        current = evidence_by_id.get(anchor.evidence_id)
        anchor_quality = (
            1 if normalize_text(anchor.source_label or "") != "inline" else 0,
            1 if anchor.source_tier == "official" else 0,
            len(anchor.excerpt),
        )
        current_quality = (
            1 if current and normalize_text(current.source_label or "") != "inline" else 0,
            1 if current and current.source_tier == "official" else 0,
            len(current.excerpt) if current else -1,
        )
        if current is None or anchor_quality > current_quality:
            evidence_by_id[anchor.evidence_id] = anchor
    evidence = sorted(evidence_by_id.values(), key=lambda item: item.evidence_id)

    claims: list[ResearchDeliveryClaimOut] = []
    for section_title, text in normalized_rows:
        numeric_facts = _extract_numeric_facts(text)
        claim_type = _claim_type(text, numeric_facts)
        claim = ResearchDeliveryClaimOut(
            claim_id=_stable_id("clm", section_title, claim_type, text),
            section_title=section_title,
            claim_type=claim_type,  # type: ignore[arg-type]
            text=text,
            confidence=_claim_confidence(claim_type, text),  # type: ignore[arg-type]
            entities=_extract_entities(text),
            numeric_facts=numeric_facts,
        )
        relations = [relation for anchor in evidence if (relation := _relation(claim, anchor)) is not None]
        relations.sort(key=lambda item: (item.relation_type != "conflicts", -item.score, item.evidence_id))
        claim = claim.model_copy(
            update={
                "evidence_relations": relations[:8],
                "verification_status": _verification_status(relations),
            }
        )
        claims.append(claim)

    claims.sort(key=lambda item: item.claim_id)
    issues = [
        *_entity_issues(claims, expected_entities=expected_entities),
        *_numeric_issues(claims),
    ]
    issues_by_id = {issue.issue_id: issue for issue in issues}
    issues = sorted(issues_by_id.values(), key=lambda item: (item.severity != "high", item.issue_type, item.issue_id))

    supported = sum(claim.verification_status == "supported" for claim in claims)
    conflicted = sum(claim.verification_status == "conflicted" for claim in claims)
    background_only = sum(claim.verification_status == "background_only" for claim in claims)
    needs_validation = sum(claim.verification_status == "needs_validation" for claim in claims)
    high_claims = [claim for claim in claims if claim.confidence == "high"]
    high_supported = sum(claim.verification_status == "supported" for claim in high_claims)
    claim_coverage = round(100 * supported / max(len(claims), 1))
    high_coverage = round(100 * high_supported / max(len(high_claims), 1)) if high_claims else claim_coverage

    entity_issue_weight = sum(30 if issue.severity == "high" else 12 for issue in issues if issue.issue_type.startswith("entity_"))
    numeric_issue_weight = sum(35 if issue.severity == "high" else 14 for issue in issues if issue.issue_type.startswith("numeric_"))
    entity_score = max(0, 100 - min(100, entity_issue_weight))
    numeric_score = max(0, 100 - min(100, numeric_issue_weight))
    status = "pass"
    if any(issue.severity == "high" for issue in issues) or high_coverage < 70:
        status = "fail"
    elif high_coverage < 90 or claim_coverage < 70 or issues:
        status = "watch"

    return ResearchDeliveryEvidenceLedgerOut(
        claim_count=len(claims),
        evidence_count=len(evidence),
        supported_claim_count=supported,
        conflicted_claim_count=conflicted,
        background_only_claim_count=background_only,
        needs_validation_claim_count=needs_validation,
        high_confidence_claim_count=len(high_claims),
        high_confidence_supported_count=high_supported,
        claim_coverage_percent=claim_coverage,
        high_confidence_coverage_percent=high_coverage,
        entity_consistency_score=entity_score,
        numeric_consistency_score=numeric_score,
        status=status,  # type: ignore[arg-type]
        claims=claims,
        evidence=evidence,
        consistency_issues=issues,
    )
