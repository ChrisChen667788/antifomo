from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from app.schemas.research import (
    ResearchMethodologyAxisOut,
    ResearchReportDocument,
    ResearchSectionRetrievalHitOut,
    ResearchSectionRetrievalPackOut,
)
from app.services.content_extractor import normalize_text
from app.services.research_quality_service import build_research_quality_profile
from app.services.research_retrieval_index_service import (
    ResearchRetrievalIndex,
    ResearchRetrievalIndexHit,
    search_research_retrieval_index,
)


_SECTION_AXIS_HINTS: dict[str, tuple[str, ...]] = {
    "项目与商机判断": ("budget", "procurement", "commercial", "target_account", "budget_window"),
    "预算": ("budget", "procurement", "cost", "window"),
    "采购": ("budget", "procurement", "cost", "window"),
    "招采": ("budget", "procurement", "cost", "window"),
    "组织": ("buyer", "target_account", "org"),
    "入口": ("buyer", "target_account", "org"),
    "部门": ("buyer", "target_account", "org"),
    "解决方案": ("solution", "scenario", "product", "fit"),
    "方案": ("solution", "scenario", "product", "fit"),
    "竞品": ("competition", "ecosystem"),
    "伙伴": ("ecosystem", "partner", "competition"),
    "生态": ("ecosystem", "partner", "competition"),
    "风险": ("risk", "delivery", "security", "compliance"),
    "合规": ("risk", "delivery", "security", "compliance"),
    "政策": ("policy", "market_context"),
}


@dataclass(slots=True)
class SectionRetrievalTarget:
    section_title: str
    query: str
    axes: list[ResearchMethodologyAxisOut] = field(default_factory=list)
    required_terms: list[str] = field(default_factory=list)


def _dedupe_strings(values: Iterable[object], limit: int = 12) -> list[str]:
    seen: set[str] = set()
    rows: list[str] = []
    for value in values:
        normalized = normalize_text(str(value or ""))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        rows.append(normalized)
        if len(rows) >= limit:
            break
    return rows


def _entity_names(values: Iterable[object]) -> list[str]:
    names: list[str] = []
    for value in values:
        if isinstance(value, str):
            candidate = normalize_text(value)
        elif isinstance(value, dict):
            candidate = normalize_text(str(value.get("name") or ""))
        else:
            candidate = normalize_text(str(getattr(value, "name", "") or ""))
        if candidate and candidate not in names:
            names.append(candidate)
    return names


def _section_text(report: ResearchReportDocument, section_title: str) -> str:
    for section in report.sections:
        if normalize_text(section.title) == normalize_text(section_title):
            return normalize_text(
                "；".join(
                    [
                        section.title,
                        *section.items,
                        section.evidence_note,
                        section.insufficiency_summary,
                        *section.next_verification_steps,
                    ]
                )
            )
    return normalize_text(section_title)


def _axis_score(axis: ResearchMethodologyAxisOut, section_text: str) -> int:
    terms = _dedupe_strings(
        [
            axis.key,
            axis.label,
            *axis.checkpoints,
            *axis.passed,
            *axis.missing,
            *_SECTION_AXIS_HINTS.get(section_text, ()),
        ],
        limit=24,
    )
    score = 0
    normalized_axis_key = normalize_text(axis.key).lower()
    normalized_axis_label = normalize_text(axis.label)
    if normalized_axis_label and normalized_axis_label in section_text:
        score += 5
    for hint, axis_hints in _SECTION_AXIS_HINTS.items():
        if hint in section_text and any(item in normalized_axis_key for item in axis_hints):
            score += 4
    for term in terms:
        if term and term in section_text:
            score += 2
    return score


def _select_axes_for_section(
    axes: list[ResearchMethodologyAxisOut],
    *,
    report: ResearchReportDocument,
    section_title: str,
) -> list[ResearchMethodologyAxisOut]:
    section_text = _section_text(report, section_title)
    ranked = sorted(
        axes,
        key=lambda axis: (_axis_score(axis, section_text), bool(axis.missing), axis.label),
        reverse=True,
    )
    selected = [axis for axis in ranked if _axis_score(axis, section_text) > 0][:2]
    if selected:
        return selected
    missing_first = [axis for axis in ranked if axis.missing]
    return (missing_first or ranked)[:2]


def _target_query(
    report: ResearchReportDocument,
    *,
    section_title: str,
    axes: list[ResearchMethodologyAxisOut],
) -> tuple[str, list[str]]:
    accounts = _dedupe_strings(
        [
            *report.target_accounts,
            *_entity_names(report.top_target_accounts),
            *_entity_names(report.pending_target_candidates),
        ],
        limit=5,
    )
    axis_terms = _dedupe_strings(
        [
            *(axis.label for axis in axes),
            *(checkpoint for axis in axes for checkpoint in axis.checkpoints),
            *(missing for axis in axes for missing in axis.missing),
            *(passed for axis in axes for passed in axis.passed),
        ],
        limit=10,
    )
    required_terms = _dedupe_strings([*accounts, *axis_terms], limit=14)
    query_parts = _dedupe_strings(
        [
            report.keyword,
            report.research_focus or "",
            section_title,
            *accounts,
            *axis_terms,
            *report.target_departments[:4],
            *report.budget_signals[:4],
            *report.tender_timeline[:3],
        ],
        limit=22,
    )
    query = normalize_text(" ".join(query_parts))
    if len(query) > 520:
        query = query[:520]
    return query, required_terms


def build_section_retrieval_targets(report: ResearchReportDocument) -> list[SectionRetrievalTarget]:
    quality_profile = (
        report.quality_profile
        if getattr(report, "quality_profile", None) and report.quality_profile.methodology.axes
        else build_research_quality_profile(report)
    )
    axes = list(quality_profile.methodology.axes)
    targets: list[SectionRetrievalTarget] = []
    for section in report.sections:
        title = normalize_text(section.title)
        if not title:
            continue
        selected_axes = _select_axes_for_section(axes, report=report, section_title=title)
        query, required_terms = _target_query(report, section_title=title, axes=selected_axes)
        targets.append(
            SectionRetrievalTarget(
                section_title=title,
                query=query,
                axes=selected_axes,
                required_terms=required_terms,
            )
        )
    if targets:
        return targets
    selected_axes = axes[:2]
    query, required_terms = _target_query(report, section_title="总体研判", axes=selected_axes)
    return [SectionRetrievalTarget(section_title="总体研判", query=query, axes=selected_axes, required_terms=required_terms)]


def _hit_to_out(hit: ResearchRetrievalIndexHit) -> ResearchSectionRetrievalHitOut:
    chunk = hit.chunk
    snippet = normalize_text(chunk.text)
    if len(snippet) > 260:
        snippet = f"{snippet[:260]}..."
    return ResearchSectionRetrievalHitOut(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        document_type=chunk.document_type,
        title=chunk.title,
        snippet=snippet,
        field_key=chunk.field_key,
        label=chunk.label,
        source_tier=chunk.source_tier,
        source_url=chunk.source_url,
        score=round(float(hit.score or 0.0), 4),
        matched_terms=list(hit.matched_terms),
        match_modes=list(hit.match_modes),
    )


def _coverage(required_terms: list[str], hits: list[ResearchRetrievalIndexHit]) -> tuple[float, list[str]]:
    if not required_terms:
        return (1.0 if hits else 0.0, [])
    haystack = normalize_text(
        "；".join("；".join([hit.chunk.title, hit.chunk.label, hit.chunk.text]) for hit in hits)
    )
    covered = [term for term in required_terms if normalize_text(term) and normalize_text(term) in haystack]
    missing = [term for term in required_terms if term not in covered]
    return (len(covered) / max(len(required_terms), 1), missing[:6])


def _pack_status(support_score: int, official_hit_count: int, hit_count: int) -> str:
    if support_score >= 72 and official_hit_count > 0:
        return "ready"
    if support_score >= 42 or hit_count >= 2:
        return "degraded"
    return "needs_evidence"


def _next_steps(status: str, target: SectionRetrievalTarget, missing_terms: list[str]) -> list[str]:
    if status == "ready":
        return ["将该章节证据纳入正式研报正文，并保留官方来源链接。"]
    if status == "degraded":
        terms = "、".join(missing_terms[:3]) or "官方来源和时间窗口"
        return [f"补充 {terms} 的官方或一手来源，再把章节从候选判断升级为正式结论。"]
    axis_labels = "、".join(axis.label for axis in target.axes[:2]) or "关键方法论轴"
    return [f"围绕 {axis_labels} 重新检索官方公告、采购记录、组织入口和项目时间线。"]


def build_section_retrieval_packs(
    report: ResearchReportDocument,
    index: ResearchRetrievalIndex,
    *,
    limit_per_section: int = 4,
) -> list[ResearchSectionRetrievalPackOut]:
    packs: list[ResearchSectionRetrievalPackOut] = []
    capped_limit = max(1, min(int(limit_per_section or 4), 10))
    for target in build_section_retrieval_targets(report):
        hits = search_research_retrieval_index(index, target.query, limit=capped_limit)
        official_hit_count = sum(1 for hit in hits if hit.chunk.source_tier == "official")
        max_score = max((float(hit.score or 0.0) for hit in hits), default=0.0)
        coverage_rate, missing_terms = _coverage(target.required_terms, hits)
        support_score = min(
            100,
            int(
                round(
                    official_hit_count * 18
                    + len(hits) * 9
                    + min(max_score, 1.0) * 34
                    + coverage_rate * 28
                )
            ),
        )
        status = _pack_status(support_score, official_hit_count, len(hits))
        packs.append(
            ResearchSectionRetrievalPackOut(
                section_title=target.section_title,
                query=target.query,
                target_axes=[axis.label for axis in target.axes],
                status=status,  # type: ignore[arg-type]
                hit_count=len(hits),
                official_hit_count=official_hit_count,
                support_score=support_score,
                hits=[_hit_to_out(hit) for hit in hits],
                missing_terms=missing_terms,
                next_steps=_next_steps(status, target, missing_terms),
            )
        )
    return packs


def attach_section_retrieval_packs(
    report: ResearchReportDocument,
    index: ResearchRetrievalIndex,
    *,
    limit_per_section: int = 4,
) -> ResearchReportDocument:
    quality_profile = (
        report.quality_profile
        if getattr(report, "quality_profile", None) and report.quality_profile.methodology.axes
        else build_research_quality_profile(report)
    )
    packs = build_section_retrieval_packs(report, index, limit_per_section=limit_per_section)
    return report.model_copy(
        update={
            "quality_profile": quality_profile.model_copy(update={"section_retrieval_packs": packs}),
        }
    )
