#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rewrite stored low-quality research reports using current cleanup rules.")
    parser.add_argument("--database-url", help="Override backend DATABASE_URL for this run.")
    parser.add_argument(
        "--audit-json",
        default=str(ROOT / ".tmp" / "research_low_quality_audit.json"),
        help="Audit JSON used to select low-quality reports.",
    )
    parser.add_argument("--top", type=int, default=10, help="Number of top bad reports to rewrite from the audit file.")
    parser.add_argument("--entry-id", action="append", default=[], help="Explicit entry ID to rewrite. Can be repeated.")
    parser.add_argument(
        "--json-out",
        default=str(ROOT / ".tmp" / "research_low_quality_rewrite_report.json"),
        help="Rewrite JSON output path.",
    )
    parser.add_argument(
        "--md-out",
        default=str(ROOT / ".tmp" / "research_low_quality_rewrite_report.md"),
        help="Rewrite Markdown output path.",
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
    text = _normalize(value)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


def _load_target_entry_ids(audit_path: Path, explicit_ids: list[str], top: int) -> list[str]:
    normalized_ids = [_normalize(item) for item in explicit_ids if _normalize(item)]
    if normalized_ids:
        return list(dict.fromkeys(normalized_ids))
    if not audit_path.exists():
        raise FileNotFoundError(f"audit report not found: {audit_path}")
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    samples = payload.get("samples") if isinstance(payload, dict) else []
    if not isinstance(samples, list):
        return []
    entry_ids = [
        _normalize(str(item.get("entry_id") or ""))
        for item in samples[: max(1, top)]
        if isinstance(item, dict) and _normalize(str(item.get("entry_id") or ""))
    ]
    return list(dict.fromkeys(entry_ids))


def _extract_frontmatter_value(content: str, label: str) -> str:
    match = re.search(rf"^- {re.escape(label)}:\s*(.+)$", content, flags=re.MULTILINE)
    return _normalize(match.group(1)) if match else ""


def _extract_markdown_section(content: str, heading: str) -> str:
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


def _extract_markdown_list(content: str, heading: str) -> list[str]:
    body = _extract_markdown_section(content, heading)
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


def _render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Research Rewrite Report")
    lines.append("")
    lines.append(f"- Requested targets: `{report['requested_targets']}`")
    lines.append(f"- Rewritten entries: `{report['rewritten_count']}`")
    lines.append("")
    for item in report["items"]:
        lines.append(f"## {item['after_title'] or item['entry_id']}")
        lines.append("")
        lines.append(f"- Entry ID: `{item['entry_id']}`")
        lines.append(f"- Rewrite mode: `{item['rewrite_mode']}`")
        lines.append(f"- Before title: {item['before_title'] or '(empty)'}")
        lines.append(f"- After title: {item['after_title'] or '(empty)'}")
        lines.append(f"- Before next action: {item['before_next_action'] or '(empty)'}")
        lines.append(f"- After next action: {item['after_next_action'] or '(empty)'}")
        lines.append(f"- Action cards: `{', '.join(item['action_card_types']) or '(empty)'}`")
        lines.append(f"- Before top targets: `{', '.join(item['before_top_targets']) or '(empty)'}`")
        lines.append(f"- After top targets: `{', '.join(item['after_top_targets']) or '(empty)'}`")
        lines.append(f"- After pending targets: `{', '.join(item['after_pending_targets']) or '(empty)'}`")
        lines.append("")
        lines.append("Before summary:")
        lines.append(item["before_summary"] or "(empty)")
        lines.append("")
        lines.append("After summary:")
        lines.append(item["after_summary"] or "(empty)")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    _bootstrap_backend(args.database_url)

    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models.entities import KnowledgeEntry
    from app.schemas.research import ResearchCommercialSummaryOut, ResearchReportResponse, ResearchSourceDiagnosticsOut
    from app.services.knowledge_intelligence_service import (
        apply_review_queue_resolutions,
        build_research_report_metadata,
    )
    from app.services.research_service import (
        build_research_action_cards,
        build_research_report_markdown,
        rewrite_stored_research_report,
    )

    def synthesize_report_from_entry(entry: KnowledgeEntry) -> ResearchReportResponse | None:
        content = entry.content or ""
        if not _normalize(content):
            return None
        keyword = _extract_frontmatter_value(content, "关键词") or _normalize(entry.title)
        research_focus = _extract_frontmatter_value(content, "补充关注点") or None
        source_count = _coerce_int(_extract_frontmatter_value(content, "来源数"), 0)
        executive_summary = _extract_markdown_section(content, "执行摘要")
        consulting_angle = _extract_markdown_section(content, "咨询价值")
        query_plan = _extract_markdown_list(content, "检索路径")
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

    target_ids = _load_target_entry_ids(Path(args.audit_json), args.entry_id, args.top)
    if not target_ids:
        print(json.dumps({"requested_targets": 0, "rewritten_count": 0}, ensure_ascii=False))
        return 0

    db = SessionLocal()
    results: list[dict[str, Any]] = []
    try:
        for raw_id in target_ids:
            try:
                entry_uuid = UUID(raw_id)
            except ValueError:
                continue
            entry = db.scalar(select(KnowledgeEntry).where(KnowledgeEntry.id == entry_uuid))
            if entry is None:
                continue
            payload = entry.metadata_payload if isinstance(entry.metadata_payload, dict) else {}
            raw_report = payload.get("report") if isinstance(payload.get("report"), dict) else None
            if isinstance(raw_report, dict):
                try:
                    previous_report = ResearchReportResponse.model_validate(raw_report)
                except Exception:
                    previous_report = synthesize_report_from_entry(entry)
            else:
                previous_report = synthesize_report_from_entry(entry)
            if previous_report is None:
                continue

            rewritten_report = rewrite_stored_research_report(previous_report)
            action_cards = build_research_action_cards(rewritten_report)
            _, markdown_content = build_research_report_markdown(
                rewritten_report,
                output_language=rewritten_report.output_language,
            )
            updated_payload = build_research_report_metadata(
                rewritten_report,
                action_cards=action_cards,
                tracking_topic_id=str(payload.get("tracking_topic_id") or "") or None,
            )
            if payload.get("review_queue_resolutions"):
                updated_payload["review_queue_resolutions"] = payload["review_queue_resolutions"]
                updated_payload = apply_review_queue_resolutions(updated_payload) or updated_payload

            entry.title = rewritten_report.report_title
            entry.content = markdown_content
            entry.metadata_payload = updated_payload
            db.add(entry)

            previous_next_action = _normalize(getattr(previous_report.commercial_summary, "next_action", ""))
            rewritten_next_action = _normalize(getattr(rewritten_report.commercial_summary, "next_action", ""))
            rewrite_mode = (
                "guarded"
                if rewritten_report.report_title.endswith(("待核验清单与补证路径", "待核驗清單與補證路徑", "Verification Backlog and Evidence Path"))
                else "rewrite"
            )
            results.append(
                {
                    "entry_id": raw_id,
                    "rewrite_mode": rewrite_mode,
                    "before_title": _normalize(previous_report.report_title),
                    "after_title": _normalize(rewritten_report.report_title),
                    "before_summary": _clip(previous_report.executive_summary, limit=280),
                    "after_summary": _clip(rewritten_report.executive_summary, limit=280),
                    "before_next_action": _clip(previous_next_action, limit=220),
                    "after_next_action": _clip(rewritten_next_action, limit=220),
                    "action_card_types": [_normalize(item.action_type) for item in action_cards if _normalize(item.action_type)],
                    "before_top_targets": [_normalize(item.name) for item in previous_report.top_target_accounts if _normalize(item.name)],
                    "after_top_targets": [_normalize(item.name) for item in rewritten_report.top_target_accounts if _normalize(item.name)],
                    "after_pending_targets": [_normalize(item.name) for item in rewritten_report.pending_target_candidates if _normalize(item.name)],
                    "before_official_ratio": float(previous_report.source_diagnostics.official_source_ratio or 0.0),
                    "after_official_ratio": float(rewritten_report.source_diagnostics.official_source_ratio or 0.0),
                    "before_source_count": int(previous_report.source_count or 0),
                    "after_source_count": int(rewritten_report.source_count or 0),
                }
            )
        db.commit()
    finally:
        db.close()

    report = {
        "requested_targets": len(target_ids),
        "rewritten_count": len(results),
        "items": results,
    }
    json_path = Path(args.json_out)
    md_path = Path(args.md_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "requested_targets": report["requested_targets"],
                "rewritten_count": report["rewritten_count"],
                "json_out": str(json_path),
                "md_out": str(md_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
