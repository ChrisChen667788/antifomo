from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from hashlib import sha256
import re

from app.schemas.research import (
    ResearchDeliveryClaimOut,
    ResearchDeliveryEvidenceLedgerOut,
    ResearchDeliverySemanticChallengeIssueOut,
    ResearchDeliverySemanticChallengeOut,
)
from app.services.content_extractor import normalize_text
from app.services.research.delivery_golden_samples import match_delivery_golden_sample
from app.services.research.source_documents import looks_like_source_artifact_text

DeliveryRow = tuple[str, str]

_ROLE_PATTERN = re.compile(
    r"(?P<role>目标客户|建议业主|建设单位|采购人|业主单位|中标供应商|中标人)"
    r"[:：]?\s*(?P<entity>[A-Za-z0-9\u4e00-\u9fff·（）()]{2,60})"
)

_NOISE_TOKENS = (
    "返回顶部",
    "当前位置",
    "网站首页",
    "登录 注册",
    "扫码关注",
    "相关阅读",
    "上一篇",
    "下一篇",
    "点击查看原文",
    "阅读原文",
)

_TEMPLATE_TOKENS = (
    "待补充",
    "待完善",
    "占位",
    "TODO",
    "TBD",
    "模板说明",
    "请输入",
    "此处填写",
)

_BENCHMARK_TOKENS = ("对标", "参考案例", "标杆案例", "类比", "可借鉴", "benchmark")
_SCENARIO_TOKENS = ("方案", "情景", "场景", "区间", "范围", "分档", "基准", "乐观", "悲观", "上限", "下限")

_DOMAIN_PROFILES: dict[str, tuple[str, ...]] = {
    "government": ("政务", "政府", "政务服务", "热线", "工单", "公共数据", "审批", "市民"),
    "tourism": ("文旅", "景区", "游客", "导览", "门票", "酒店", "票务", "数字人讲解"),
    "ecommerce": ("电商", "直播", "带货", "私域", "转化率", "GMV", "店铺", "电商客服"),
    "manufacturing": ("制造", "产线", "机器视觉", "MES", "ERP", "PLC", "设备数据", "工业互联网"),
    "healthcare": ("医疗", "医学", "医院", "医保", "病历", "门诊", "影像", "临床"),
    "education": ("学校", "校园", "教务", "课堂", "学生", "课程"),
    "finance": ("银行", "金融", "风控", "信贷", "反欺诈", "保险"),
}

_COMPARABLE_METRICS = {
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


def _stable_id(prefix: str, *values: object) -> str:
    seed = "\x1f".join(normalize_text(str(value or "")).lower() for value in values)
    return f"{prefix}_{sha256(seed.encode('utf-8')).hexdigest()[:16]}"


def _dedupe(values: Iterable[object], *, limit: int = 20) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = normalize_text(str(value or ""))
        if not text or text in seen:
            continue
        rows.append(text)
        seen.add(text)
        if len(rows) >= limit:
            break
    return rows


def _normalize_rows(rows: Iterable[DeliveryRow]) -> list[DeliveryRow]:
    normalized: list[DeliveryRow] = []
    seen: set[DeliveryRow] = set()
    for section, text in rows:
        item = (normalize_text(section), normalize_text(text))
        if not item[1] or item in seen:
            continue
        normalized.append(item)
        seen.add(item)
    return normalized


def _issue(
    issue_type: str,
    severity: str,
    *,
    section_title: str = "",
    claim_ids: Iterable[str] = (),
    summary: str,
    evidence: Iterable[object] = (),
    suggested_action: str,
) -> ResearchDeliverySemanticChallengeIssueOut:
    ids = sorted(set(claim_id for claim_id in claim_ids if claim_id))
    rows = _dedupe(evidence, limit=6)
    return ResearchDeliverySemanticChallengeIssueOut(
        issue_id=_stable_id("sch", issue_type, severity, section_title, *ids, summary, *rows[:3]),
        issue_type=issue_type,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        section_title=section_title,
        claim_ids=ids,
        summary=summary,
        evidence=rows,
        suggested_action=suggested_action,
    )


def _domain_hits(value: str) -> dict[str, list[str]]:
    lowered = value.lower()
    hits: dict[str, list[str]] = {}
    for domain, terms in _DOMAIN_PROFILES.items():
        matched = [term for term in terms if term.lower() in lowered]
        if domain == "government" and set(matched) <= {"政府"}:
            continue
        if matched:
            hits[domain] = matched
    return hits


def _expected_domains(expected_scope_terms: Sequence[str]) -> set[str]:
    text = normalize_text(" ".join(str(term or "") for term in expected_scope_terms))
    return set(_domain_hits(text))


def _scope_drift_issues(
    rows: Sequence[DeliveryRow],
    *,
    expected_scope_terms: Sequence[str],
) -> list[ResearchDeliverySemanticChallengeIssueOut]:
    expected = _expected_domains(expected_scope_terms)
    if not expected:
        return []
    issues: list[ResearchDeliverySemanticChallengeIssueOut] = []
    for section, text in rows:
        if "覆盖公开网页、政府采购" in text or "不使用未授权登录库" in text:
            continue
        if any(token.lower() in text.lower() for token in _BENCHMARK_TOKENS):
            continue
        row_hits = _domain_hits(text)
        drift_domains = sorted(domain for domain in row_hits if domain not in expected)
        if not drift_domains:
            continue
        evidence = [f"{domain}: {'、'.join(row_hits[domain][:4])}" for domain in drift_domains]
        issues.append(
            _issue(
                "scope_drift",
                "high",
                section_title=section,
                summary=f"{section or '文档'}出现与锁定范围不一致的行业/场景词。",
                evidence=[text, *evidence],
                suggested_action="将该段移入对标/参考案例，或改写为当前项目范围内的业务、客户和建设内容。",
            )
        )
        if len(issues) >= 6:
            break
    return issues


def _role_entity(value: str) -> str:
    entity = normalize_text(value).strip("，,；;。.!！?")
    entity = re.split(r"(?:预算|建设周期|项目编号|来源|证据|。|，|；)", entity, maxsplit=1)[0]
    return normalize_text(entity)


def _cross_section_entity_issues(
    claims: Sequence[ResearchDeliveryClaimOut],
    *,
    expected_entities: Sequence[str],
) -> list[ResearchDeliverySemanticChallengeIssueOut]:
    expected = {normalize_text(entity) for entity in expected_entities if normalize_text(entity)}
    by_role: dict[str, list[tuple[ResearchDeliveryClaimOut, str]]] = defaultdict(list)
    issues: list[ResearchDeliverySemanticChallengeIssueOut] = []
    for claim in claims:
        for match in _ROLE_PATTERN.finditer(claim.text):
            role = normalize_text(match.group("role"))
            entity = _role_entity(match.group("entity"))
            if not entity:
                continue
            by_role[role].append((claim, entity))
            if role in {"目标客户", "建议业主", "建设单位", "采购人", "业主单位"} and expected and entity not in expected:
                issues.append(
                    _issue(
                        "entity_conflict",
                        "high",
                        section_title=claim.section_title,
                        claim_ids=[claim.claim_id],
                        summary=f"{role}与锁定主体不一致。",
                        evidence=[f"文档值：{entity}", f"锁定主体：{'；'.join(sorted(expected))}", claim.text],
                        suggested_action="统一客户、业主、采购人和建设单位口径；无法确认时降级为待核验并阻断外发。",
                    )
                )
    for role, values in by_role.items():
        distinct = sorted({entity for _claim, entity in values})
        sections = sorted({claim.section_title for claim, _entity in values if claim.section_title})
        if len(distinct) <= 1 or len(sections) <= 1:
            continue
        issues.append(
            _issue(
                "entity_conflict",
                "high",
                claim_ids=[claim.claim_id for claim, _entity in values],
                summary=f"跨章节的{role}存在多个不一致主体。",
                evidence=[*distinct, *[f"{claim.section_title}: {claim.text}" for claim, _entity in values][:4]],
                suggested_action="将主体映射到同一份实体表，并在项目概况、投资、实施、招采章节同步替换。",
            )
        )
    return issues[:8]


def _cross_section_numeric_issues(
    claims: Sequence[ResearchDeliveryClaimOut],
) -> list[ResearchDeliverySemanticChallengeIssueOut]:
    groups: dict[tuple[str, str], list[tuple[ResearchDeliveryClaimOut, object]]] = defaultdict(list)
    for claim in claims:
        if any(token in claim.text for token in _SCENARIO_TOKENS):
            continue
        for fact in claim.numeric_facts:
            if fact.metric not in _COMPARABLE_METRICS or not fact.normalized_unit:
                continue
            groups[(fact.metric, fact.normalized_unit)].append((claim, fact))

    issues: list[ResearchDeliverySemanticChallengeIssueOut] = []
    for (metric, unit), values in groups.items():
        sections = sorted({claim.section_title for claim, _fact in values if claim.section_title})
        if len(sections) <= 1 or len(values) <= 1:
            continue
        numeric_values = [round(float(getattr(fact, "normalized_value", 0) or 0), 6) for _claim, fact in values]
        distinct = sorted(set(numeric_values))
        if len(distinct) <= 1:
            continue
        highest = max(abs(value) for value in distinct)
        if highest and max(distinct) - min(distinct) <= highest * 0.01:
            continue
        issues.append(
            _issue(
                "cross_section_conflict",
                "high",
                claim_ids=[claim.claim_id for claim, _fact in values],
                summary=f"跨章节的 {metric} 数字口径不一致。",
                evidence=[
                    f"{claim.section_title}: {claim.text} [{getattr(fact, 'raw_value', '')} -> {getattr(fact, 'normalized_value', '')} {unit}]"
                    for claim, fact in values
                ],
                suggested_action="在证据账本中锁定唯一数字来源；如为情景测算，显式标注基准/乐观/悲观口径。",
            )
        )
    return issues[:8]


def _unsupported_claim_issues(
    ledger: ResearchDeliveryEvidenceLedgerOut,
) -> list[ResearchDeliverySemanticChallengeIssueOut]:
    issues: list[ResearchDeliverySemanticChallengeIssueOut] = []
    for claim in ledger.claims:
        if claim.confidence != "high":
            continue
        if claim.verification_status == "supported":
            continue
        severity = "high" if claim.verification_status == "conflicted" else "medium"
        issues.append(
            _issue(
                "unsupported_high_confidence_claim",
                severity,
                section_title=claim.section_title,
                claim_ids=[claim.claim_id],
                summary="高置信主张未获得直接支持证据。",
                evidence=[claim.text, f"verification_status={claim.verification_status}"],
                suggested_action="补 URL、文号、项目编号或 source/chunk ID；补不到证据时改为假设或待核验。",
            )
        )
        if len(issues) >= 6:
            break
    return issues


def _ledger_conflict_issues(
    ledger: ResearchDeliveryEvidenceLedgerOut,
) -> list[ResearchDeliverySemanticChallengeIssueOut]:
    rows: list[ResearchDeliverySemanticChallengeIssueOut] = []
    for issue in ledger.consistency_issues:
        issue_type = "numeric_conflict" if issue.issue_type.startswith("numeric_") else "entity_conflict"
        rows.append(
            _issue(
                issue_type,
                issue.severity,
                claim_ids=issue.claim_ids,
                summary=issue.summary,
                evidence=issue.details,
                suggested_action="优先处理证据账本中的实体/数字一致性问题，再进入正式外发。",
            )
        )
    return rows[:8]


def _source_contamination_issues(rows: Sequence[DeliveryRow]) -> list[ResearchDeliverySemanticChallengeIssueOut]:
    issues: list[ResearchDeliverySemanticChallengeIssueOut] = []
    for section, text in rows:
        if not (looks_like_source_artifact_text(text) or any(token in text for token in _NOISE_TOKENS)):
            continue
        issues.append(
            _issue(
                "source_contamination",
                "high",
                section_title=section,
                summary=f"{section or '文档'}包含网页导航、页脚或来源转储噪声。",
                evidence=[text],
                suggested_action="先清洗网页导航、登录提示、相关阅读、页脚和来源转储，再生成交付文档。",
            )
        )
        if len(issues) >= 5:
            break
    return issues


def _template_language_issues(rows: Sequence[DeliveryRow]) -> list[ResearchDeliverySemanticChallengeIssueOut]:
    hits: list[tuple[str, str, str]] = []
    for section, text in rows:
        matched = [token for token in _TEMPLATE_TOKENS if token.lower() in text.lower()]
        if matched:
            hits.append((section, text, "、".join(matched)))
    if not hits:
        return []
    severity = "medium" if len(hits) >= 3 else "low"
    return [
        _issue(
            "template_language",
            severity,
            summary="文档仍存在模板占位或未完稿表达。",
            evidence=[f"{section}: {text}（{matched}）" for section, text, matched in hits[:6]],
            suggested_action="交付前替换占位表达；无法补充的信息进入假设台账或待核验清单。",
        )
    ]


def _golden_sample_issue(
    rows: Sequence[DeliveryRow],
    *,
    expected_scope_terms: Sequence[str],
    document_kind: str,
) -> tuple[
    ResearchDeliverySemanticChallengeIssueOut | None,
    str,
    str,
    int,
]:
    if not any(normalize_text(term) for term in expected_scope_terms):
        return None, "", "", 0
    match = match_delivery_golden_sample(
        [item for row in rows for item in row],
        expected_scope_terms=expected_scope_terms,
        document_kind=document_kind,
    )
    if match.sample is None:
        return None, "", "", 0
    issue = None
    if match.score < match.sample.min_alignment_score:
        issue = _issue(
            "missing_gold_sample_review",
            "medium" if match.score < 70 else "low",
            summary=f"与黄金样本“{match.sample.title}”的范围和章节对齐不足。",
            evidence=[
                f"alignment_score={match.score}",
                f"缺少范围词：{'；'.join(match.missing_required_terms[:5]) or '无'}",
                f"禁入词命中：{'；'.join(match.forbidden_hits[:5]) or '无'}",
                f"缺少章节：{'；'.join(match.missing_sections[:5]) or '无'}",
            ],
            suggested_action="按黄金样本补齐范围术语、关键章节和证据台账；禁入场景必须移除或改为对标说明。",
        )
    return issue, match.sample.sample_id, match.sample.title, match.score


def build_delivery_semantic_challenge(
    rows: Sequence[DeliveryRow],
    *,
    evidence_ledger: ResearchDeliveryEvidenceLedgerOut,
    expected_scope_terms: Sequence[str] = (),
    expected_entities: Sequence[str] = (),
    document_kind: str = "",
) -> ResearchDeliverySemanticChallengeOut:
    normalized_rows = _normalize_rows(rows)
    issues: list[ResearchDeliverySemanticChallengeIssueOut] = []
    issues.extend(_source_contamination_issues(normalized_rows))
    issues.extend(_scope_drift_issues(normalized_rows, expected_scope_terms=expected_scope_terms))
    issues.extend(_cross_section_entity_issues(evidence_ledger.claims, expected_entities=expected_entities))
    issues.extend(_cross_section_numeric_issues(evidence_ledger.claims))
    issues.extend(_unsupported_claim_issues(evidence_ledger))
    issues.extend(_ledger_conflict_issues(evidence_ledger))
    issues.extend(_template_language_issues(normalized_rows))

    golden_issue, golden_id, golden_title, golden_score = _golden_sample_issue(
        normalized_rows,
        expected_scope_terms=expected_scope_terms,
        document_kind=document_kind,
    )
    if golden_issue is not None:
        issues.append(golden_issue)

    issue_by_id = {issue.issue_id: issue for issue in issues}
    severity_order = {"high": 0, "medium": 1, "low": 2}
    issues = sorted(
        issue_by_id.values(),
        key=lambda item: (severity_order[item.severity], item.issue_type, item.issue_id),
    )
    high_count = sum(issue.severity == "high" for issue in issues)
    medium_count = sum(issue.severity == "medium" for issue in issues)
    low_count = sum(issue.severity == "low" for issue in issues)
    scope_count = sum(issue.issue_type == "scope_drift" for issue in issues)
    cross_count = sum(
        issue.issue_type in {"cross_section_conflict", "entity_conflict", "numeric_conflict"}
        for issue in issues
    )
    score = max(0, 100 - high_count * 24 - medium_count * 10 - low_count * 4 - scope_count * 6)
    if golden_score:
        score = min(score, max(50, golden_score + 12))
    if high_count:
        status = "fail"
        score = min(score, 67)
    elif score >= 84 and not medium_count:
        status = "pass"
    elif score >= 68:
        status = "watch"
    else:
        status = "fail"

    recommended_actions = _dedupe(
        [
            issue.suggested_action
            for issue in issues
            if issue.severity in {"high", "medium"} and issue.suggested_action
        ]
        or [
            "保留语义挑战者结果，正式外发前继续复核范围、主体、数字和证据锚点。",
        ],
        limit=6,
    )
    return ResearchDeliverySemanticChallengeOut(
        status=status,  # type: ignore[arg-type]
        overall_score=score,
        issue_count=len(issues),
        high_severity_count=high_count,
        scope_drift_count=scope_count,
        cross_section_conflict_count=cross_count,
        golden_sample_id=golden_id,
        golden_sample_title=golden_title,
        golden_sample_alignment_score=golden_score,
        issues=issues[:20],
        recommended_actions=recommended_actions,
    )
