from __future__ import annotations

import copy
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.entities import KnowledgeEntry
from app.schemas.research import ResearchCommercialSummaryOut, ResearchReportResponse, ResearchSourceDiagnosticsOut
from app.services.knowledge_intelligence_service import (
    apply_review_queue_resolutions,
    build_research_report_metadata,
)
from app.services import research_service


LEGACY_TITLE_PREFIXES = (
    "候选推进版｜",
    "候選推進版｜",
    "待补证研判｜",
    "待補證研判｜",
)

GUARDED_TITLE_SUFFIXES = (
    "待核验清单与补证路径",
    "待核驗清單與補證路徑",
    "Verification Backlog and Evidence Path",
)

GENERIC_NEXT_ACTION_TOKENS = (
    "尽量颗粒度细致到具体的垂直赛道",
    "精确到有预算的甲方公司",
    "决策部门、联系方式、竞品公司分析、核心需求等",
    "建议补充公开服务热线",
    "重新生成",
    "扩大搜索范围",
    "继续扩大搜索范围",
)

ROW_NOISE_TOKENS = (
    "若金额仍缺失",
    "可先给出高价值预算口径",
    "这些口径最适合后续销售",
    "尽量颗粒度细致到具体的垂直赛道",
    "精确到有预算的甲方公司",
    "建议补充公开服务热线",
    "继续扩大搜索范围",
    "当前证据不足",
    "优先给具体公司",
    "把高价值甲方",
)

ENTITY_NOISE_PREFIXES = (
    "AI的",
    "一直",
    "此前",
    "若金额",
    "当前",
    "建议",
    "尽量",
    "精确",
    "把高价值",
)

ENTITY_HINT_SUFFIXES = (
    "公司",
    "集团",
    "政府",
    "市政府",
    "委员会",
    "委",
    "局",
    "办",
    "中心",
    "医院",
    "大学",
    "学院",
    "学校",
    "银行",
    "研究院",
    "研究所",
    "事务所",
    "平台",
    "系统",
    "科技",
    "软件",
    "智能",
    "股份",
    "有限公司",
)

SECTION_IMPORTANT_TOKENS = ("甲方", "预算", "招标", "采购", "竞品", "伙伴", "联系")

LOW_QUALITY_REVIEW_STATUSES = {"pending", "rewritten", "accepted", "reverted"}


@dataclass
class AuditIssue:
    code: str
    severity: str
    weight: int
    summary: str
    evidence: str = ""


@dataclass
class SuspiciousRow:
    field: str
    value: str
    reason: str


def _normalize(value: str | None) -> str:
    return " ".join((value or "").replace("\u3000", " ").split())


def _clip(value: str | None, *, limit: int = 180) -> str:
    normalized = _normalize(value)
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1].rstrip()}…"


def _add_issue(issues: list[AuditIssue], code: str, severity: str, weight: int, summary: str, evidence: str = "") -> None:
    issues.append(
        AuditIssue(
            code=code,
            severity=severity,
            weight=weight,
            summary=summary,
            evidence=_clip(evidence, limit=160),
        )
    )


def _looks_like_bad_entity_name(value: str) -> bool:
    normalized = _normalize(value)
    if not normalized:
        return False
    if any(token in normalized for token in ROW_NOISE_TOKENS):
        return True
    if normalized.startswith(ENTITY_NOISE_PREFIXES):
        return True
    if any(char in normalized for char in "，。；：:[]【】") and "·" not in normalized:
        return True
    if any(char in normalized for char in "()（）") and "·" not in normalized:
        compact = normalized.translate(str.maketrans("", "", "()（）"))
        if not compact.endswith(ENTITY_HINT_SUFFIXES) and not normalized.endswith(ENTITY_HINT_SUFFIXES):
            return True
    if len(normalized) <= 18:
        return False
    return not normalized.endswith(ENTITY_HINT_SUFFIXES)


def _looks_like_noisy_row(value: str) -> bool:
    normalized = _normalize(value)
    if not normalized:
        return False
    if any(token in normalized for token in ROW_NOISE_TOKENS):
        return True
    if normalized.count("；") + normalized.count(";") >= 2:
        return True
    if len(normalized) >= 90 and "：" not in normalized and ":" not in normalized:
        return True
    return False


def _is_guarded_backlog_summary(value: str) -> bool:
    normalized = _normalize(value)
    return (
        normalized.startswith("当前公开来源不足以支持对")
        and "仅保留为待核验清单" in normalized
        and "先补官网、公告、采购和联系人线索" in normalized
    )


def _is_guarded_backlog_title(value: str) -> bool:
    normalized = _normalize(value)
    return normalized.endswith(GUARDED_TITLE_SUFFIXES)


def _is_guarded_backlog_next_action(value: str) -> bool:
    normalized = _normalize(value)
    if not normalized.startswith("先补官网、公告、采购和联系人线索"):
        return False
    return "正式推进" in normalized or "正式研报" in normalized


def _is_standard_guarded_backlog_report(title: str, executive_summary: str, next_action: str) -> bool:
    return (
        _is_guarded_backlog_title(title)
        and _is_guarded_backlog_summary(executive_summary)
        and _is_guarded_backlog_next_action(next_action)
    )


def _collect_suspicious_rows(report: Any) -> list[SuspiciousRow]:
    rows: list[SuspiciousRow] = []

    entity_fields = {
        "top_target_accounts": [item.name for item in getattr(report, "top_target_accounts", []) or [] if _normalize(getattr(item, "name", ""))],
        "top_competitors": [item.name for item in getattr(report, "top_competitors", []) or [] if _normalize(getattr(item, "name", ""))],
        "top_ecosystem_partners": [item.name for item in getattr(report, "top_ecosystem_partners", []) or [] if _normalize(getattr(item, "name", ""))],
        "candidate_profile_companies": list(getattr(getattr(report, "source_diagnostics", None), "candidate_profile_companies", []) or []),
    }
    for field_name, values in entity_fields.items():
        for value in values:
            if _looks_like_bad_entity_name(str(value)):
                rows.append(SuspiciousRow(field=field_name, value=_normalize(str(value)), reason="疑似实体名噪声或句子片段"))

    text_fields = {
        "target_accounts": list(getattr(report, "target_accounts", []) or []),
        "competitor_profiles": list(getattr(report, "competitor_profiles", []) or []),
        "ecosystem_partners": list(getattr(report, "ecosystem_partners", []) or []),
        "public_contact_channels": list(getattr(report, "public_contact_channels", []) or []),
        "budget_signals": list(getattr(report, "budget_signals", []) or []),
        "benchmark_cases": list(getattr(report, "benchmark_cases", []) or []),
    }
    for field_name, values in text_fields.items():
        for value in values:
            if _looks_like_noisy_row(str(value)):
                rows.append(SuspiciousRow(field=field_name, value=_normalize(str(value)), reason="疑似提示词泄漏或过长模板句"))
    return rows[:6]


def _collect_important_section_failures(report: Any, *, contradictions_only: bool = False) -> list[str]:
    failed: list[str] = []
    for section in getattr(report, "sections", []) or []:
        title = _normalize(getattr(section, "title", ""))
        if not title:
            continue
        if not any(token in title for token in SECTION_IMPORTANT_TOKENS):
            continue
        contradiction_detected = bool(getattr(section, "contradiction_detected", False))
        meets_evidence_quota = bool(getattr(section, "meets_evidence_quota", True))
        if contradiction_detected or (not contradictions_only and not meets_evidence_quota):
            failed.append(title)
    return failed[:4]


def _derive_suggested_focus(issues: list[AuditIssue]) -> list[str]:
    issue_codes = {issue.code for issue in issues}
    suggestions: list[str] = []
    if "legacy_title_prefix" in issue_codes or "title_scope_noise" in issue_codes:
        suggestions.append("标题模板与 scope 压缩")
    if "bad_executive_summary" in issue_codes:
        suggestions.append("执行摘要 rewrite 规则")
    if "generic_next_action" in issue_codes:
        suggestions.append("行动卡 / next action 具体化")
    if "weak_source_coverage" in issue_codes or "weak_official_ratio" in issue_codes:
        suggestions.append("官方源命中率与证据门槛")
    if "noisy_entity_rows" in issue_codes:
        suggestions.append("实体归一与候选字段清洗")
    if "important_section_failures" in issue_codes:
        suggestions.append("章节级补证 quota")
    return suggestions or ["人工复核"]


def _normalize_review_status(payload: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return "pending", {}
    review_state = payload.get("low_quality_review")
    if not isinstance(review_state, dict):
        return "pending", {}
    status = _normalize(str(review_state.get("status") or "pending")).lower()
    if status not in LOW_QUALITY_REVIEW_STATUSES:
        status = "pending"
    return status, dict(review_state)


def _sanitize_review_snapshot_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    cloned = copy.deepcopy(payload) if isinstance(payload, dict) else {}
    review_state = cloned.get("low_quality_review")
    if isinstance(review_state, dict):
        review_state.pop("previous_snapshot", None)
        review_state.pop("latest_rewrite", None)
        if not review_state:
            cloned.pop("low_quality_review", None)
        else:
            cloned["low_quality_review"] = review_state
    return cloned


def _attach_review_state(sample: dict[str, Any], payload: dict[str, Any] | None) -> dict[str, Any]:
    review_status, review_state = _normalize_review_status(payload)
    updated = dict(sample)
    updated["review_status"] = review_status
    updated["review_updated_at"] = review_state.get("updated_at")
    updated["has_rewrite_snapshot"] = isinstance(review_state.get("previous_snapshot"), dict)
    latest_rewrite = review_state.get("latest_rewrite")
    updated["latest_rewrite"] = latest_rewrite if isinstance(latest_rewrite, dict) else None
    return updated


def _audit_report(entry: Any, report: Any) -> dict[str, Any]:
    issues: list[AuditIssue] = []
    title = _normalize(getattr(report, "report_title", ""))
    executive_summary = _normalize(getattr(report, "executive_summary", ""))
    readiness = getattr(report, "report_readiness", None)
    readiness_status = _normalize(getattr(readiness, "status", ""))
    source_count = int(getattr(report, "source_count", 0) or 0)
    diagnostics = getattr(report, "source_diagnostics", None)
    official_ratio = float(getattr(diagnostics, "official_source_ratio", 0.0) or 0.0)
    retrieval_quality = _normalize(getattr(diagnostics, "retrieval_quality", ""))
    evidence_mode = _normalize(getattr(diagnostics, "evidence_mode", ""))
    next_action = _normalize(getattr(getattr(report, "commercial_summary", None), "next_action", ""))
    is_guarded_backlog = _is_standard_guarded_backlog_report(title, executive_summary, next_action)

    if title.startswith(LEGACY_TITLE_PREFIXES):
        _add_issue(issues, "legacy_title_prefix", "high", 24, "标题仍带旧版候选/待补证前缀。", title)
    separator_count = title.count("｜") + title.count("|") + title.count("/")
    if separator_count >= 3 or len(title) >= 42:
        _add_issue(issues, "title_scope_noise", "medium", 10, "标题 scope 过长或分隔过多，阅读阻力偏高。", title)

    if _is_guarded_backlog_summary(executive_summary):
        pass
    elif research_service._looks_like_bad_executive_summary(executive_summary):
        _add_issue(issues, "bad_executive_summary", "high", 22, "执行摘要仍是模板腔或结论颗粒度不够。", executive_summary)
    elif all(token in executive_summary for token in ("结论：", "证据：", "动作：")):
        _add_issue(issues, "templated_executive_summary", "medium", 10, "执行摘要仍保留旧版“结论/证据/动作”串联模板。", executive_summary)

    if not next_action:
        _add_issue(issues, "missing_next_action", "medium", 10, "commercial_summary.next_action 为空。")
    elif any(token in next_action for token in GENERIC_NEXT_ACTION_TOKENS):
        _add_issue(issues, "generic_next_action", "high", 18, "下一步动作仍偏提示词/模板句，没有收敛到可执行动作。", next_action)
    elif len(next_action) >= 150 or next_action.count("；") + next_action.count(";") >= 3:
        _add_issue(issues, "bloated_next_action", "medium", 10, "下一步动作过长，信息密度偏低。", next_action)

    if not is_guarded_backlog:
        if source_count == 0:
            _add_issue(issues, "weak_source_coverage", "high", 26, "source_count 为 0，报告没有有效来源支撑。")
        elif source_count < 3:
            _add_issue(issues, "weak_source_coverage", "high", 20, f"source_count 仅 {source_count}，证据覆盖明显不足。")
        elif source_count < 5:
            _add_issue(issues, "weak_source_coverage", "medium", 12, f"source_count 仅 {source_count}，仍低于当前强结论基线。")

        if official_ratio < 0.1:
            _add_issue(issues, "weak_official_ratio", "high", 18, f"官方源占比仅 {round(official_ratio * 100)}%。")
        elif official_ratio < 0.2:
            _add_issue(issues, "weak_official_ratio", "medium", 12, f"官方源占比仅 {round(official_ratio * 100)}%。")
        elif official_ratio < 0.25:
            _add_issue(issues, "weak_official_ratio", "low", 6, f"官方源占比 {round(official_ratio * 100)}%，仍未过稳态阈值。")

        if retrieval_quality == "low":
            _add_issue(issues, "low_retrieval_quality", "medium", 10, "source_diagnostics.retrieval_quality 为 low。")
        if evidence_mode == "fallback":
            _add_issue(issues, "fallback_evidence_mode", "high", 14, "当前仍处于 fallback evidence mode。")
        elif evidence_mode == "provisional":
            _add_issue(issues, "provisional_evidence_mode", "medium", 8, "当前仅达到 provisional evidence mode。")

        if readiness_status == "needs_evidence":
            _add_issue(issues, "needs_evidence", "high", 14, "报告 readiness 仍是 needs_evidence。")
        elif readiness_status == "degraded":
            _add_issue(issues, "degraded_readiness", "medium", 8, "报告 readiness 为 degraded。")

    suspicious_rows = _collect_suspicious_rows(report)
    if suspicious_rows:
        _add_issue(
            issues,
            "noisy_entity_rows",
            "high" if len(suspicious_rows) >= 3 else "medium",
            min(18, 8 + len(suspicious_rows) * 3),
            f"实体/候选字段中发现 {len(suspicious_rows)} 条疑似噪声或提示词泄漏。",
            suspicious_rows[0].value,
        )

    section_failures = _collect_important_section_failures(report, contradictions_only=is_guarded_backlog)
    if len(section_failures) >= 2:
        _add_issue(
            issues,
            "important_section_failures",
            "medium",
            10,
            f"关键章节仍有 {len(section_failures)} 处未过证据门槛或存在冲突。",
            " / ".join(section_failures[:3]),
        )

    risk_score = sum(issue.weight for issue in issues)
    source_preview = [
        {
            "title": _normalize(getattr(source, "title", "")),
            "domain": _normalize(getattr(source, "domain", "")),
            "source_tier": _normalize(getattr(source, "source_tier", "")),
        }
        for source in (getattr(report, "sources", []) or [])[:3]
    ]

    return {
        "entry_id": str(entry.id),
        "updated_at": entry.updated_at.isoformat() if getattr(entry, "updated_at", None) else None,
        "entry_title": _normalize(getattr(entry, "title", "")),
        "report_title": title,
        "keyword": _normalize(getattr(report, "keyword", "")),
        "research_focus": _normalize(getattr(report, "research_focus", "")),
        "risk_score": risk_score,
        "issue_count": len(issues),
        "readiness_status": readiness_status,
        "guarded_backlog": is_guarded_backlog,
        "source_count": source_count,
        "official_source_ratio": round(official_ratio, 4),
        "retrieval_quality": retrieval_quality,
        "evidence_mode": evidence_mode,
        "issue_codes": [issue.code for issue in issues],
        "issues": [asdict(issue) for issue in issues],
        "suggested_focus": _derive_suggested_focus(issues),
        "executive_summary": _clip(executive_summary, limit=280),
        "next_action": _clip(next_action, limit=220),
        "suspicious_rows": [asdict(row) for row in suspicious_rows],
        "important_section_failures": section_failures,
        "source_preview": source_preview,
    }


def synthesize_report_from_entry(entry: KnowledgeEntry) -> ResearchReportResponse | None:
    content = entry.content or ""
    if not _normalize(content):
        return None

    def _extract_frontmatter_value(label: str) -> str:
        match = re.search(rf"^- {re.escape(label)}:\s*(.+)$", content, flags=re.MULTILINE)
        return _normalize(match.group(1)) if match else ""

    def _extract_markdown_section(heading: str) -> str:
        match = re.search(
            rf"^##\s+{re.escape(heading)}\s*$\n(?P<body>.*?)(?=^##\s+|\Z)",
            content,
            flags=re.MULTILINE | re.DOTALL,
        )
        if not match:
            return ""
        body = match.group("body")
        lines = [_normalize(line) for line in body.splitlines() if _normalize(line)]
        return "\n".join(lines).strip()

    def _extract_markdown_list(heading: str) -> list[str]:
        body = _extract_markdown_section(heading)
        if not body:
            return []
        items: list[str] = []
        for line in body.splitlines():
            normalized = _normalize(line)
            if normalized.startswith(("- ", "* ")):
                items.append(_normalize(normalized[2:]))
        return items

    def _coerce_int(value: str, default: int = 0) -> int:
        match = re.search(r"\d+", value or "")
        return int(match.group(0)) if match else default

    keyword = _extract_frontmatter_value("关键词") or _normalize(entry.title)
    research_focus = _extract_frontmatter_value("补充关注点") or None
    source_count = _coerce_int(_extract_frontmatter_value("来源数"), 0)
    executive_summary = _extract_markdown_section("执行摘要")
    consulting_angle = _extract_markdown_section("咨询价值")
    query_plan = _extract_markdown_list("检索路径")
    generated_at = entry.updated_at if getattr(entry, "updated_at", None) else datetime.now(timezone.utc)
    if not keyword:
        return None
    return ResearchReportResponse(
        keyword=keyword,
        research_focus=research_focus,
        output_language="zh-CN",
        research_mode="deep",
        report_title=_normalize(entry.title) or keyword,
        executive_summary=executive_summary or "当前存量研报 payload 缺失，已转为最小可修复报告结构。",
        consulting_angle=consulting_angle or "先补正式 report payload，再继续做版本化重写与补证。",
        sections=[],
        target_accounts=[],
        target_departments=[],
        public_contact_channels=[],
        account_team_signals=[],
        budget_signals=[],
        project_distribution=[],
        strategic_directions=[],
        tender_timeline=[],
        leadership_focus=[],
        ecosystem_partners=[],
        competitor_profiles=[],
        benchmark_cases=[],
        flagship_products=[],
        key_people=[],
        five_year_outlook=[],
        client_peer_moves=[],
        winner_peer_moves=[],
        competition_analysis=[],
        source_count=source_count,
        evidence_density="low",
        source_quality="low",
        query_plan=query_plan,
        sources=[],
        source_diagnostics=ResearchSourceDiagnosticsOut(
            retrieval_quality="low" if source_count <= 1 else "medium",
            evidence_mode="fallback" if source_count <= 1 else "provisional",
            official_source_ratio=0.0,
        ),
        commercial_summary=ResearchCommercialSummaryOut(next_action="先补正式 report payload，再决定是否进入正式推进。"),
        generated_at=generated_at,
    )


def _audit_entry(entry: KnowledgeEntry) -> dict[str, Any]:
    payload = entry.metadata_payload if isinstance(entry.metadata_payload, dict) else {}
    raw_report = payload.get("report") if isinstance(payload.get("report"), dict) else None
    if not isinstance(raw_report, dict):
        sample = {
            "entry_id": str(entry.id),
            "updated_at": entry.updated_at.isoformat() if getattr(entry, "updated_at", None) else None,
            "entry_title": _normalize(getattr(entry, "title", "")),
            "report_title": "",
            "keyword": "",
            "research_focus": "",
            "risk_score": 100,
            "issue_count": 1,
            "readiness_status": "",
            "guarded_backlog": False,
            "source_count": 0,
            "official_source_ratio": 0.0,
            "retrieval_quality": "",
            "evidence_mode": "",
            "issue_codes": ["invalid_report_payload"],
            "issues": [asdict(AuditIssue("invalid_report_payload", "high", 100, "metadata_payload.report 缺失或不是 dict。"))],
            "suggested_focus": ["存量数据清洗"],
            "executive_summary": "",
            "next_action": "",
            "suspicious_rows": [],
            "important_section_failures": [],
            "source_preview": [],
        }
        return _attach_review_state(sample, payload)
    try:
        report = ResearchReportResponse.model_validate(raw_report)
    except Exception:
        sample = {
            "entry_id": str(entry.id),
            "updated_at": entry.updated_at.isoformat() if getattr(entry, "updated_at", None) else None,
            "entry_title": _normalize(getattr(entry, "title", "")),
            "report_title": _normalize(str(raw_report.get("report_title") or "")),
            "keyword": _normalize(str(raw_report.get("keyword") or "")),
            "research_focus": _normalize(str(raw_report.get("research_focus") or "")),
            "risk_score": 90,
            "issue_count": 1,
            "readiness_status": "",
            "guarded_backlog": False,
            "source_count": int(raw_report.get("source_count") or 0),
            "official_source_ratio": 0.0,
            "retrieval_quality": "",
            "evidence_mode": "",
            "issue_codes": ["invalid_report_schema"],
            "issues": [asdict(AuditIssue("invalid_report_schema", "high", 90, "report payload 无法通过当前 schema 校验。"))],
            "suggested_focus": ["存量 schema 兼容"],
            "executive_summary": _clip(str(raw_report.get("executive_summary") or ""), limit=280),
            "next_action": "",
            "suspicious_rows": [],
            "important_section_failures": [],
            "source_preview": [],
        }
        return _attach_review_state(sample, payload)
    return _attach_review_state(_audit_report(entry, report), payload)


def list_low_quality_research_review_queue(
    db: Session,
    *,
    top: int = 12,
    include_resolved: bool = False,
) -> dict[str, Any]:
    entries = list(
        db.scalars(
            select(KnowledgeEntry)
            .where(KnowledgeEntry.source_domain == "research.report")
            .order_by(desc(KnowledgeEntry.updated_at), desc(KnowledgeEntry.created_at))
        )
    )
    samples: list[dict[str, Any]] = []
    issue_counter: Counter[str] = Counter()
    invalid_payloads = 0
    for entry in entries:
        sample = _audit_entry(entry)
        review_status = str(sample.get("review_status") or "pending")
        risk_score = int(sample.get("risk_score") or 0)
        if sample.get("issue_codes") in (["invalid_report_payload"], ["invalid_report_schema"]):
            invalid_payloads += 1
        if risk_score > 0:
            issue_counter.update(sample.get("issue_codes") or [])
        include_item = risk_score > 0 or review_status == "rewritten"
        if not include_resolved and review_status == "accepted":
            include_item = False
        if not include_item:
            continue
        samples.append(sample)

    samples.sort(
        key=lambda item: (
            0 if str(item.get("review_status") or "pending") == "rewritten" else 1,
            -int(item.get("risk_score") or 0),
            -int(item.get("issue_count") or 0),
            str(item.get("updated_at") or ""),
        )
    )
    top_samples = samples[: max(1, top)]

    recommendations: list[str] = []
    if issue_counter.get("weak_official_ratio") or issue_counter.get("weak_source_coverage"):
        recommendations.append("优先回看官方源命中率和 source gate；这是当前低质量样本最常见的根因。")
    if issue_counter.get("bad_executive_summary") or issue_counter.get("templated_executive_summary"):
        recommendations.append("继续压缩执行摘要模板，避免“结论/证据/动作”串联式旧输出。")
    if issue_counter.get("generic_next_action") or issue_counter.get("bloated_next_action"):
        recommendations.append("next_action 需要更硬的账户、部门、时间窗锚点，避免提示词残留。")
    if issue_counter.get("legacy_title_prefix") or issue_counter.get("title_scope_noise"):
        recommendations.append("存量旧标题样式仍在库内，建议结合回灌脚本做历史重写或重新生成。")
    if issue_counter.get("noisy_entity_rows"):
        recommendations.append("实体归一和候选字段清洗仍要继续收口，尤其是 candidate_profile_companies。")
    if invalid_payloads:
        recommendations.append("有少量存量 payload 未过当前 schema，后续可以单独做历史兼容清洗。")
    if not recommendations:
        recommendations.append("当前没有发现明显低质量样本，可缩小 top 范围继续抽检。")

    return {
        "generated_at": datetime.now(timezone.utc),
        "total_reports": len(entries),
        "flagged_reports": len(samples),
        "invalid_payloads": invalid_payloads,
        "issue_summary": [
            {"code": code, "count": count}
            for code, count in sorted(issue_counter.items(), key=lambda item: (-item[1], item[0]))
        ],
        "recommendations": recommendations,
        "items": top_samples,
    }


def _load_research_entry(db: Session, entry_id: str) -> KnowledgeEntry:
    try:
        parsed_id = UUID(entry_id)
    except ValueError as exc:
        raise ValueError("Invalid research entry id") from exc
    entry = db.scalar(select(KnowledgeEntry).where(KnowledgeEntry.id == parsed_id))
    if entry is None or entry.source_domain != "research.report":
        raise LookupError("Research report not found")
    return entry


def _load_previous_report(entry: KnowledgeEntry) -> tuple[dict[str, Any], ResearchReportResponse]:
    payload = entry.metadata_payload if isinstance(entry.metadata_payload, dict) else {}
    raw_report = payload.get("report") if isinstance(payload.get("report"), dict) else None
    if isinstance(raw_report, dict):
        try:
            return payload, ResearchReportResponse.model_validate(raw_report)
        except Exception:
            pass
    synthesized = synthesize_report_from_entry(entry)
    if synthesized is None:
        raise ValueError("Research report payload is missing and could not be synthesized")
    return payload, synthesized


def _build_rewrite_diff(
    previous_report: ResearchReportResponse,
    rewritten_report: ResearchReportResponse,
    *,
    before_risk_score: int,
    after_risk_score: int,
) -> dict[str, Any]:
    previous_next_action = _normalize(getattr(previous_report.commercial_summary, "next_action", ""))
    rewritten_next_action = _normalize(getattr(rewritten_report.commercial_summary, "next_action", ""))
    rewrite_mode = (
        "guarded"
        if rewritten_report.report_title.endswith(GUARDED_TITLE_SUFFIXES)
        else "rewrite"
    )
    return {
        "rewrite_mode": rewrite_mode,
        "before_title": _normalize(previous_report.report_title),
        "after_title": _normalize(rewritten_report.report_title),
        "before_summary": _clip(previous_report.executive_summary, limit=280),
        "after_summary": _clip(rewritten_report.executive_summary, limit=280),
        "before_next_action": _clip(previous_next_action, limit=220),
        "after_next_action": _clip(rewritten_next_action, limit=220),
        "before_top_targets": [_normalize(item.name) for item in previous_report.top_target_accounts if _normalize(item.name)],
        "after_top_targets": [_normalize(item.name) for item in rewritten_report.top_target_accounts if _normalize(item.name)],
        "after_pending_targets": [_normalize(item.name) for item in rewritten_report.pending_target_candidates if _normalize(item.name)],
        "before_risk_score": before_risk_score,
        "after_risk_score": after_risk_score,
        "rewritten_at": datetime.now(timezone.utc).isoformat(),
    }


def rewrite_low_quality_research_entry(db: Session, entry_id: str) -> dict[str, Any]:
    entry = _load_research_entry(db, entry_id)
    previous_payload, previous_report = _load_previous_report(entry)
    before_sample = _audit_report(entry, previous_report)

    rewritten_report = research_service.rewrite_stored_research_report(previous_report)
    after_sample = _audit_report(entry, rewritten_report)
    diff = _build_rewrite_diff(
        previous_report,
        rewritten_report,
        before_risk_score=int(before_sample.get("risk_score") or 0),
        after_risk_score=int(after_sample.get("risk_score") or 0),
    )

    action_cards = research_service.build_research_action_cards(rewritten_report)
    _, markdown_content = research_service.build_research_report_markdown(
        rewritten_report,
        output_language=rewritten_report.output_language,
    )
    updated_payload = build_research_report_metadata(
        rewritten_report,
        action_cards=action_cards,
        tracking_topic_id=str(previous_payload.get("tracking_topic_id") or "") or None,
    )
    if previous_payload.get("review_queue_resolutions"):
        updated_payload["review_queue_resolutions"] = previous_payload["review_queue_resolutions"]
        updated_payload = apply_review_queue_resolutions(updated_payload) or updated_payload

    previous_status, previous_review_state = _normalize_review_status(previous_payload)
    snapshot = previous_review_state.get("previous_snapshot")
    if not isinstance(snapshot, dict):
        snapshot = {
            "title": entry.title,
            "content": entry.content,
            "metadata_payload": _sanitize_review_snapshot_payload(previous_payload),
        }
    updated_payload["low_quality_review"] = {
        "status": "rewritten",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "previous_status": previous_status,
        "previous_snapshot": snapshot,
        "latest_rewrite": diff,
    }

    entry.title = rewritten_report.report_title
    entry.content = markdown_content
    entry.metadata_payload = updated_payload
    db.add(entry)
    db.commit()
    db.refresh(entry)

    item = _audit_entry(entry)
    return {
        "entry_id": str(entry.id),
        "review_status": "rewritten",
        "diff": item.get("latest_rewrite") or diff,
        "item": item,
    }


def resolve_low_quality_research_entry(
    db: Session,
    *,
    entry_id: str,
    action: str,
) -> dict[str, Any]:
    normalized_action = _normalize(action).lower()
    if normalized_action not in {"accept", "revert"}:
        raise ValueError("Unsupported low-quality review action")

    entry = _load_research_entry(db, entry_id)
    payload = entry.metadata_payload if isinstance(entry.metadata_payload, dict) else {}
    _status, review_state = _normalize_review_status(payload)

    if normalized_action == "accept":
        next_payload = copy.deepcopy(payload)
        latest_rewrite = review_state.get("latest_rewrite")
        next_payload["low_quality_review"] = {
            "status": "accepted",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "accepted_at": datetime.now(timezone.utc).isoformat(),
            "latest_rewrite": latest_rewrite if isinstance(latest_rewrite, dict) else None,
        }
        entry.metadata_payload = next_payload
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return {
            "entry_id": str(entry.id),
            "review_status": "accepted",
            "item": None,
        }

    snapshot = review_state.get("previous_snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("No previous snapshot available for revert")
    restored_payload = snapshot.get("metadata_payload")
    next_payload = _sanitize_review_snapshot_payload(restored_payload if isinstance(restored_payload, dict) else {})
    next_payload["low_quality_review"] = {
        "status": "reverted",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "reverted_at": datetime.now(timezone.utc).isoformat(),
        "latest_rewrite": review_state.get("latest_rewrite") if isinstance(review_state.get("latest_rewrite"), dict) else None,
    }
    entry.title = str(snapshot.get("title") or entry.title)
    entry.content = str(snapshot.get("content") or entry.content)
    entry.metadata_payload = next_payload
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {
        "entry_id": str(entry.id),
        "review_status": "reverted",
        "item": _audit_entry(entry),
    }
