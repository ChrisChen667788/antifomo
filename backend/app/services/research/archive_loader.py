from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import desc, or_, select

from app.core.config import get_settings
from app.models.entities import KnowledgeEntry
from app.schemas.research import ResearchReportResponse, ResearchSourceDiagnosticsOut
from app.services.content_extractor import normalize_text
from app.services.knowledge_retrieval_service import retrieve_knowledge_entry_matches


def entry_report_payload(entry: KnowledgeEntry) -> ResearchReportResponse | None:
    payload = entry.metadata_payload if isinstance(entry.metadata_payload, dict) else None
    raw_report = payload.get("report") if isinstance(payload, dict) else None
    if not isinstance(raw_report, dict):
        return None
    try:
        return ResearchReportResponse.model_validate(raw_report)
    except Exception:
        return None


def build_archive_report_scope_hints(
    report: ResearchReportResponse,
    *,
    dedupe_strings: Callable[[list[str], int], list[str]],
    prune_industry_hints: Callable[[list[str]], list[str]],
    stored_report_concrete_targets: Callable[[ResearchReportResponse], list[str]],
) -> dict[str, object]:
    diagnostics = report.source_diagnostics if getattr(report, "source_diagnostics", None) else ResearchSourceDiagnosticsOut()
    stored_clients = dedupe_strings(
        [
            normalize_text(item)
            for item in [
                *(normalize_text(item) for item in diagnostics.scope_clients if normalize_text(item)),
                *(
                    normalize_text(item)
                    for item in stored_report_concrete_targets(report)
                    if normalize_text(item)
                ),
            ]
            if normalize_text(item)
        ],
        4,
    )
    return {
        "regions": dedupe_strings([normalize_text(item) for item in diagnostics.scope_regions if normalize_text(item)], 3),
        "industries": prune_industry_hints([normalize_text(item) for item in diagnostics.scope_industries if normalize_text(item)]),
        "clients": stored_clients,
        "company_anchors": dedupe_strings(stored_clients, 4),
        "anchor_text": normalize_text(" / ".join(stored_clients[:2])),
    }


def build_archive_context_item(
    *,
    entry: KnowledgeEntry,
    match: Any,
    scope_hints: dict[str, object],
    truncate_text: Callable[[str | None, int], str],
    report_sources_to_source_documents: Callable[..., list[Any]],
    merge_scope_hints: Callable[[dict[str, object], dict[str, object]], dict[str, object]],
    infer_input_scope_hints: Callable[[str, str | None], dict[str, object]],
    build_archive_report_scope_hints: Callable[[ResearchReportResponse], dict[str, object]],
    infer_scope_hints: Callable[[str, str | None, list[Any]], dict[str, object]],
    assess_stored_report_rewrite_mode: Callable[..., tuple[str, Any, Any]],
    resolve_stored_report_target_support: Callable[..., tuple[list[str], list[str], list[str]]],
    theme_labels_from_scope: Callable[..., set[str]],
    dedupe_strings: Callable[[list[str], int], list[str]],
    sanitize_entity_row: Callable[[str, str], str],
    is_trustworthy_scope_client_name: Callable[..., bool],
    resolved_report_readiness: Callable[[ResearchReportResponse], Any],
) -> dict[str, object] | None:
    title = normalize_text(getattr(entry, "title", "")) or "知识卡片"
    preview = getattr(match, "preview", None)
    snippet = normalize_text(getattr(preview, "snippet", "")) or truncate_text(normalize_text(entry.content or ""), 220)
    match_label = normalize_text(getattr(preview, "label", "")) or "知识命中"
    source_tier = normalize_text(getattr(preview, "source_tier", "")) or "media"
    score = float(getattr(match, "score", 0.0) or 0.0)
    match_modes = [normalize_text(item) for item in getattr(preview, "match_modes", ()) if normalize_text(item)]
    matched_terms = [normalize_text(item) for item in getattr(preview, "matched_terms", ()) if normalize_text(item)]

    report = entry_report_payload(entry)
    if report is not None:
        reference_timestamp = getattr(report, "generated_at", None) or getattr(entry, "updated_at", None) or getattr(entry, "created_at", None)
        source_documents = report_sources_to_source_documents(report.sources)
        report_scope_hints = merge_scope_hints(
            infer_input_scope_hints(report.keyword, report.research_focus),
            build_archive_report_scope_hints(report),
        )
        if source_documents:
            report_scope_hints = merge_scope_hints(
                report_scope_hints,
                infer_scope_hints(report.keyword, report.research_focus, source_documents),
            )
        rewrite_mode, _, _ = assess_stored_report_rewrite_mode(
            report,
            source_documents=source_documents,
            scope_hints=report_scope_hints,
        )
        if rewrite_mode == "guarded":
            return None

        _concrete_targets, supported_targets, _unsupported_targets = resolve_stored_report_target_support(
            report,
            source_documents=source_documents,
            scope_hints=report_scope_hints,
        )
        theme_labels = theme_labels_from_scope(scope_hints, keyword=report.keyword, research_focus=report.research_focus)
        trusted_targets = dedupe_strings(
            [
                sanitize_entity_row("target_accounts", target)
                for target in supported_targets
                if normalize_text(target)
                and is_trustworthy_scope_client_name(normalize_text(target), theme_labels=theme_labels)
            ],
            4,
        )
        diagnostics = report.source_diagnostics if getattr(report, "source_diagnostics", None) else ResearchSourceDiagnosticsOut()
        official_ratio = float(diagnostics.official_source_ratio or 0.0)
        readiness = resolved_report_readiness(report)
        if not trusted_targets and readiness.status != "ready" and official_ratio < 0.25 and report.source_count < 4:
            return None
        if trusted_targets and not any(target in snippet for target in trusted_targets):
            snippet = f"{trusted_targets[0]} · {snippet}" if snippet else trusted_targets[0]

        return {
            "kind": "stored_report",
            "entry_id": str(entry.id),
            "title": normalize_text(report.report_title) or title,
            "match_label": match_label,
            "match_snippet": snippet,
            "match_modes": match_modes,
            "matched_terms": matched_terms[:6],
            "score": round(score, 4),
            "source_tier": source_tier if source_tier in {"official", "media", "aggregate"} else "media",
            "summary": truncate_text(normalize_text(report.executive_summary), 240),
            "supported_targets": trusted_targets,
            "target_departments": dedupe_strings(
                [normalize_text(item) for item in report.target_departments if normalize_text(item)],
                3,
            ),
            "budget_signals": dedupe_strings(
                [normalize_text(item) for item in report.budget_signals if normalize_text(item)],
                3,
            ),
            "source_count": int(report.source_count or 0),
            "official_source_ratio": round(official_ratio, 4),
            "retrieval_quality": normalize_text(diagnostics.retrieval_quality),
            "evidence_mode": normalize_text(diagnostics.evidence_mode),
            "updated_at": reference_timestamp.isoformat() if isinstance(reference_timestamp, datetime) else None,
        }

    if not entry.is_focus_reference and not entry.is_pinned:
        return None
    note_timestamp = getattr(entry, "updated_at", None) or getattr(entry, "created_at", None)
    return {
        "kind": "knowledge_note",
        "entry_id": str(entry.id),
        "title": title,
        "match_label": match_label,
        "match_snippet": snippet,
        "match_modes": match_modes,
        "matched_terms": matched_terms[:6],
        "score": round(score, 4),
        "source_tier": source_tier if source_tier in {"official", "media", "aggregate"} else "media",
        "summary": truncate_text(normalize_text(entry.content or ""), 220),
        "supported_targets": [],
        "target_departments": [],
        "budget_signals": [],
        "source_count": 0,
        "official_source_ratio": 0.0,
        "retrieval_quality": "",
        "evidence_mode": "",
        "updated_at": note_timestamp.isoformat() if isinstance(note_timestamp, datetime) else None,
    }


def load_research_archive_context(
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
    limit: int,
    session_factory: Callable[[], Any],
    research_archive_query_text: Callable[[str, str | None, dict[str, object]], str],
    build_archive_context_item: Callable[..., dict[str, object] | None],
    retrieve_matches: Callable[..., list[Any]] = retrieve_knowledge_entry_matches,
) -> list[dict[str, object]]:
    query_text = research_archive_query_text(keyword, research_focus, scope_hints)
    if not query_text:
        return []
    try:
        with session_factory() as db:
            candidates = list(
                db.scalars(
                    select(KnowledgeEntry)
                    .where(KnowledgeEntry.user_id == get_settings().single_user_id)
                    .where(
                        or_(
                            KnowledgeEntry.source_domain == "research.report",
                            KnowledgeEntry.is_focus_reference.is_(True),
                            KnowledgeEntry.is_pinned.is_(True),
                        )
                    )
                    .order_by(desc(KnowledgeEntry.updated_at), desc(KnowledgeEntry.created_at))
                    .limit(240)
                )
            )
    except Exception:
        return []
    if not candidates:
        return []

    matches = retrieve_matches(candidates, query_text, limit=max(8, limit * 2))
    context_items: list[dict[str, object]] = []
    seen_entry_ids: set[str] = set()
    for match in matches:
        entry = getattr(match, "entry", None)
        entry_id = str(getattr(entry, "id", "") or "")
        if not entry_id or entry_id in seen_entry_ids:
            continue
        item = build_archive_context_item(entry=entry, match=match, scope_hints=scope_hints)
        if item is None:
            continue
        seen_entry_ids.add(entry_id)
        context_items.append(item)
        if len(context_items) >= limit:
            break
    return context_items
