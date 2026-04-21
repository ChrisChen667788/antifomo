#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit low-quality research reports from the local knowledge store.")
    parser.add_argument("--database-url", help="Override backend DATABASE_URL for this run.")
    parser.add_argument("--top", type=int, default=10, help="Number of worst samples to keep in the output.")
    parser.add_argument(
        "--json-out",
        default=str(ROOT / ".tmp" / "research_low_quality_audit.json"),
        help="JSON output path.",
    )
    parser.add_argument(
        "--md-out",
        default=str(ROOT / ".tmp" / "research_low_quality_audit.md"),
        help="Markdown output path.",
    )
    return parser.parse_args()


def _bootstrap_backend(database_url: str | None) -> None:
    os.chdir(BACKEND_ROOT)
    if database_url:
        os.environ["DATABASE_URL"] = database_url
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))


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


def _audit_report(entry: Any, report: Any, helpers: dict[str, Any]) -> dict[str, Any]:
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
    elif helpers["looks_like_bad_executive_summary"](executive_summary):
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


def _render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Research Low-quality Audit")
    lines.append("")
    lines.append(f"- Generated at: `{report['generated_at']}`")
    lines.append(f"- Total reports scanned: `{report['total_reports']}`")
    lines.append(f"- Flagged reports: `{report['flagged_reports']}`")
    lines.append(f"- Top samples kept: `{len(report['samples'])}`")
    lines.append("")
    lines.append("## Issue Summary")
    lines.append("")
    for item in report["issue_summary"]:
        lines.append(f"- `{item['code']}`: {item['count']}")
    lines.append("")
    lines.append("## Recommendations")
    lines.append("")
    for recommendation in report["recommendations"]:
        lines.append(f"- {recommendation}")
    lines.append("")
    lines.append("## Top Samples")
    lines.append("")

    for index, sample in enumerate(report["samples"], start=1):
        lines.append(f"### {index}. {sample['report_title'] or sample['entry_title'] or sample['entry_id']}")
        lines.append("")
        lines.append(f"- Entry ID: `{sample['entry_id']}`")
        lines.append(f"- Updated at: `{sample['updated_at']}`")
        lines.append(f"- Risk score: `{sample['risk_score']}`")
        lines.append(f"- Readiness: `{sample['readiness_status']}`")
        lines.append(f"- Source count: `{sample['source_count']}`")
        lines.append(f"- Official ratio: `{sample['official_source_ratio']}`")
        lines.append(f"- Retrieval quality: `{sample['retrieval_quality']}`")
        lines.append(f"- Evidence mode: `{sample['evidence_mode']}`")
        lines.append(f"- Suggested focus: `{', '.join(sample['suggested_focus'])}`")
        lines.append("")
        lines.append("Issues:")
        for issue in sample["issues"]:
            evidence = f" | {issue['evidence']}" if issue.get("evidence") else ""
            lines.append(f"- [{issue['severity']}/{issue['weight']}] `{issue['code']}` {issue['summary']}{evidence}")
        lines.append("")
        lines.append(f"Executive summary: {sample['executive_summary'] or '(empty)'}")
        lines.append("")
        lines.append(f"Next action: {sample['next_action'] or '(empty)'}")
        lines.append("")
        if sample["suspicious_rows"]:
            lines.append("Suspicious rows:")
            for row in sample["suspicious_rows"]:
                lines.append(f"- `{row['field']}`: {row['value']} ({row['reason']})")
            lines.append("")
        if sample["important_section_failures"]:
            lines.append("Section failures:")
            for section in sample["important_section_failures"]:
                lines.append(f"- {section}")
            lines.append("")
        if sample["source_preview"]:
            lines.append("Source preview:")
            for source in sample["source_preview"]:
                label = " / ".join(part for part in (source["source_tier"], source["domain"]) if part)
                lines.append(f"- {source['title']} ({label})")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    _bootstrap_backend(args.database_url)

    from sqlalchemy import desc, select

    from app.db.session import SessionLocal, engine
    from app.models.entities import KnowledgeEntry
    from app.schemas.research import ResearchReportResponse
    from app.services import research_service

    helpers = {
        "looks_like_bad_executive_summary": research_service._looks_like_bad_executive_summary,
    }

    db = SessionLocal()
    samples: list[dict[str, Any]] = []
    issue_counter: Counter[str] = Counter()
    invalid_payloads = 0
    total_reports = 0

    try:
        entries = list(
            db.scalars(
                select(KnowledgeEntry)
                .where(KnowledgeEntry.source_domain == "research.report")
                .order_by(desc(KnowledgeEntry.updated_at), desc(KnowledgeEntry.created_at))
            )
        )
        total_reports = len(entries)
        for entry in entries:
            payload = entry.metadata_payload if isinstance(entry.metadata_payload, dict) else {}
            raw_report = payload.get("report") if isinstance(payload.get("report"), dict) else None
            if not isinstance(raw_report, dict):
                invalid_payloads += 1
                samples.append(
                    {
                        "entry_id": str(entry.id),
                        "updated_at": entry.updated_at.isoformat() if getattr(entry, "updated_at", None) else None,
                        "entry_title": _normalize(getattr(entry, "title", "")),
                        "report_title": "",
                        "keyword": "",
                        "research_focus": "",
                        "risk_score": 100,
                        "issue_count": 1,
                        "readiness_status": "",
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
                )
                issue_counter["invalid_report_payload"] += 1
                continue

            try:
                report = ResearchReportResponse.model_validate(raw_report)
            except Exception:
                invalid_payloads += 1
                samples.append(
                    {
                        "entry_id": str(entry.id),
                        "updated_at": entry.updated_at.isoformat() if getattr(entry, "updated_at", None) else None,
                        "entry_title": _normalize(getattr(entry, "title", "")),
                        "report_title": _normalize(str(raw_report.get("report_title") or "")),
                        "keyword": _normalize(str(raw_report.get("keyword") or "")),
                        "research_focus": _normalize(str(raw_report.get("research_focus") or "")),
                        "risk_score": 90,
                        "issue_count": 1,
                        "readiness_status": "",
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
                )
                issue_counter["invalid_report_schema"] += 1
                continue

            sample = _audit_report(entry, report, helpers)
            if sample["risk_score"] <= 0:
                continue
            samples.append(sample)
            issue_counter.update(sample["issue_codes"])
    finally:
        db.close()

    samples.sort(
        key=lambda item: (
            -int(item["risk_score"]),
            -int(item["issue_count"]),
            item["updated_at"] or "",
        )
    )
    top_samples = samples[: max(1, args.top)]

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

    report = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "database_url": str(engine.url),
        "total_reports": total_reports,
        "flagged_reports": len(samples),
        "invalid_payloads": invalid_payloads,
        "issue_summary": [
            {"code": code, "count": count}
            for code, count in sorted(issue_counter.items(), key=lambda item: (-item[1], item[0]))
        ],
        "recommendations": recommendations,
        "samples": top_samples,
    }

    json_path = Path(args.json_out)
    md_path = Path(args.md_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")

    print(json.dumps({
        "total_reports": report["total_reports"],
        "flagged_reports": report["flagged_reports"],
        "top_samples": len(top_samples),
        "json_out": str(json_path),
        "md_out": str(md_path),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
