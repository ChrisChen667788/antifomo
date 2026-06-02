from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import re

from app.services.content_extractor import normalize_text


def research_archive_query_text(
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
    *,
    dedupe_strings: Callable[[list[str], int], list[str]],
) -> str:
    parts = [
        normalize_text(keyword),
        normalize_text(research_focus or ""),
        *[
            normalize_text(str(item))
            for key in ("regions", "industries", "clients", "company_anchors")
            for item in scope_hints.get(key, []) or []
            if normalize_text(str(item))
        ],
    ]
    return "；".join(item for item in dedupe_strings(parts, 12) if item)


def render_archive_prompt_context(archive_context_items: list[dict[str, object]]) -> str:
    if not archive_context_items:
        return "无"
    lines: list[str] = []
    for index, item in enumerate(archive_context_items[:5], start=1):
        title = normalize_text(str(item.get("title") or "")) or f"历史条目 {index}"
        match_label = normalize_text(str(item.get("match_label") or "")) or "知识命中"
        score = float(item.get("score") or 0.0)
        kind = normalize_text(str(item.get("kind") or "")) or "archive"
        lines.append(f"{index}. [{kind}] {title} | 命中: {match_label} | score={score:.3f}")
        match_snippet = normalize_text(str(item.get("match_snippet") or ""))
        if match_snippet:
            lines.append(f"   - 命中片段: {match_snippet}")
        summary = normalize_text(str(item.get("summary") or ""))
        if summary:
            lines.append(f"   - 历史摘要: {summary}")
        supported_targets = [normalize_text(str(target)) for target in item.get("supported_targets", []) or [] if normalize_text(str(target))]
        if supported_targets:
            lines.append(f"   - 历史支撑账户: {'；'.join(supported_targets[:3])}")
        target_departments = [normalize_text(str(dept)) for dept in item.get("target_departments", []) or [] if normalize_text(str(dept))]
        if target_departments:
            lines.append(f"   - 历史组织入口: {'；'.join(target_departments[:3])}")
        budget_signals = [normalize_text(str(row)) for row in item.get("budget_signals", []) or [] if normalize_text(str(row))]
        if budget_signals:
            lines.append(f"   - 历史预算/节奏: {'；'.join(budget_signals[:3])}")
        source_count = int(item.get("source_count") or 0)
        official_ratio = float(item.get("official_source_ratio") or 0.0)
        if source_count > 0:
            lines.append(f"   - 历史证据强度: 来源 {source_count} 条 / 官方占比 {round(official_ratio * 100)}%")
    return "\n".join(lines) if lines else "无"


def parse_archive_context_datetime(value: object) -> datetime | None:
    raw = normalize_text(str(value or ""))
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def archive_item_is_queryworthy(item: dict[str, object]) -> bool:
    if normalize_text(str(item.get("kind") or "")) != "stored_report":
        return False
    supported_targets = [
        normalize_text(str(target))
        for target in item.get("supported_targets", []) or []
        if normalize_text(str(target))
    ]
    if not supported_targets:
        return False
    source_count = int(item.get("source_count") or 0)
    official_ratio = float(item.get("official_source_ratio") or 0.0)
    retrieval_quality = normalize_text(str(item.get("retrieval_quality") or "")).lower()
    if source_count < 2 or official_ratio < 0.25:
        return False
    updated_at = parse_archive_context_datetime(item.get("updated_at"))
    if updated_at is not None:
        age_days = max(0.0, (datetime.now(timezone.utc) - updated_at.astimezone(timezone.utc)).total_seconds() / 86400.0)
        if age_days > 720 and (official_ratio < 0.6 or source_count < 4):
            return False
    if retrieval_quality == "low" and official_ratio < 0.5:
        return False
    return True


def archive_budget_query_term(
    value: str,
    *,
    is_actionable_budget_row: Callable[[str], bool],
    truncate_text: Callable[[str | None, int], str],
) -> str:
    normalized = normalize_text(value)
    if not is_actionable_budget_row(normalized):
        return ""
    first_segment = re.split(r"[，,；;。]", normalized, maxsplit=1)[0]
    compact = normalize_text(first_segment)
    if len(compact) > 26:
        compact = truncate_text(compact, 26)
    if not any(token in compact for token in ("预算", "采购", "招标", "中标", "立项", "经费", "扩容", "合同")):
        return ""
    return compact


def build_archive_query_expansions(
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
    targets: list[str],
    departments: list[str],
    budget_terms: list[str],
    strip_query_noise: Callable[[str], str],
    sanitize_research_focus_text: Callable[[str | None], str],
    dedupe_strings: Callable[[list[str], int], list[str]],
) -> list[str]:
    if not targets:
        return []
    keyword_seed = strip_query_noise(keyword) or normalize_text(keyword)
    focus_seed = sanitize_research_focus_text(research_focus)
    regions = [normalize_text(str(item)) for item in scope_hints.get("regions", []) or [] if normalize_text(str(item))]
    industries = [normalize_text(str(item)) for item in scope_hints.get("industries", []) or [] if normalize_text(str(item))]

    queries: list[str] = []
    for target in dedupe_strings(targets, 2):
        queries.extend(
            [
                f"\"{target}\" {keyword_seed} 预算 采购 立项",
                f"\"{target}\" {keyword_seed} 招标 项目 采购",
            ]
        )
        if regions:
            queries.append(f"\"{target}\" {regions[0]} {keyword_seed} 招标 项目")
        if industries:
            queries.append(f"\"{target}\" {industries[0]} {keyword_seed} 预算 采购")
        if focus_seed:
            queries.append(f"\"{target}\" {keyword_seed} {focus_seed}")
        for department in dedupe_strings(departments, 2):
            queries.append(f"\"{target}\" \"{department}\" {keyword_seed}")
            queries.append(f"\"{target}\" \"{department}\" 预算 采购")
        for budget_term in dedupe_strings(budget_terms, 1):
            queries.append(f"\"{target}\" {keyword_seed} {budget_term}")

    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized = normalize_text(query)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
        if len(deduped) >= 6:
            break
    return deduped


def merge_scope_hints_with_archive_context(
    scope_hints: dict[str, object],
    archive_context_items: list[dict[str, object]],
    *,
    keyword: str,
    research_focus: str | None,
    dedupe_strings: Callable[[list[str], int], list[str]],
    sanitize_report_field_rows: Callable[[str, list[str]], list[str]],
    is_actionable_budget_row: Callable[[str], bool],
    truncate_text: Callable[[str | None, int], str],
    strip_query_noise: Callable[[str], str],
    sanitize_research_focus_text: Callable[[str | None], str],
) -> dict[str, object]:
    if not archive_context_items:
        return scope_hints

    queryworthy_items = [item for item in archive_context_items if archive_item_is_queryworthy(item)]
    if not queryworthy_items:
        return scope_hints

    trusted_targets = dedupe_strings(
        [
            normalize_text(str(target))
            for item in queryworthy_items
            for target in item.get("supported_targets", []) or []
            if normalize_text(str(target))
        ],
        4,
    )
    if not trusted_targets:
        return scope_hints

    trusted_departments = sanitize_report_field_rows(
        "target_departments",
        [
            normalize_text(str(department))
            for item in queryworthy_items
            for department in item.get("target_departments", []) or []
            if normalize_text(str(department))
        ],
    )[:4]
    trusted_budget_terms = dedupe_strings(
        [
            archive_budget_query_term(
                normalize_text(str(row)),
                is_actionable_budget_row=is_actionable_budget_row,
                truncate_text=truncate_text,
            )
            for item in queryworthy_items
            for row in item.get("budget_signals", []) or []
            if normalize_text(str(row))
        ],
        3,
    )

    merged_clients = dedupe_strings(
        [
            *(normalize_text(str(item)) for item in scope_hints.get("clients", []) or [] if normalize_text(str(item))),
            *trusted_targets,
        ],
        4,
    )
    merged_company_anchors = dedupe_strings(
        [
            *(normalize_text(str(item)) for item in scope_hints.get("company_anchors", []) or [] if normalize_text(str(item))),
            *trusted_targets,
        ],
        6,
    )
    archive_query_expansions = build_archive_query_expansions(
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
        targets=trusted_targets,
        departments=trusted_departments,
        budget_terms=trusted_budget_terms,
        strip_query_noise=strip_query_noise,
        sanitize_research_focus_text=sanitize_research_focus_text,
        dedupe_strings=dedupe_strings,
    )
    return {
        **scope_hints,
        "clients": merged_clients if bool(scope_hints.get("prefer_company_entities")) or bool(scope_hints.get("clients")) else list(scope_hints.get("clients", []) or []),
        "company_anchors": merged_company_anchors,
        "archive_targets": trusted_targets,
        "archive_target_departments": trusted_departments,
        "archive_budget_signals": trusted_budget_terms,
        "strategy_query_expansions": dedupe_strings(
            [
                *(normalize_text(str(item)) for item in scope_hints.get("strategy_query_expansions", []) or [] if normalize_text(str(item))),
                *archive_query_expansions,
            ],
            12,
        ),
        "anchor_text": normalize_text(
            " / ".join(
                [
                    *[normalize_text(str(item)) for item in scope_hints.get("regions", []) or [] if normalize_text(str(item))][:2],
                    *[normalize_text(str(item)) for item in scope_hints.get("industries", []) or [] if normalize_text(str(item))][:2],
                    *merged_clients[:2],
                ]
            )
        ),
    }
