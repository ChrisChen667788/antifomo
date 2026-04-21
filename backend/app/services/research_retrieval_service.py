from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.services.content_extractor import normalize_text

_SENTENCE_SPLIT_RE = re.compile(r"[。！？!?；;\n]+")
_QUESTION_TERM_RE = re.compile(r"[a-z0-9][a-z0-9._/-]{1,}|[\u4e00-\u9fff]{2,}")
_CJK_RE = re.compile(r"^[\u4e00-\u9fff]+$")

_QUESTION_STOPWORDS = {
    "什么",
    "哪些",
    "哪个",
    "如何",
    "怎么",
    "以及",
    "还有",
    "最近",
    "当前",
    "这个",
    "那个",
    "一下",
    "现在",
    "情况",
    "问题",
    "请问",
    "是否",
    "需要",
    "我们",
    "你们",
    "their",
    "there",
    "about",
    "what",
    "when",
    "which",
    "with",
}

_FOCUS_GROUP_HINTS: dict[str, tuple[str, ...]] = {
    "budget": ("预算", "采购", "立项", "招标", "中标", "timeline", "budget", "tender", "procurement"),
    "buyer": ("甲方", "客户", "账户", "buyer", "target", "客户群", "联系人", "部门"),
    "competitor": ("竞品", "竞争", "对手", "competitor", "threat"),
    "partner": ("伙伴", "生态", "渠道", "partner", "alliance"),
    "evidence": ("证据", "依据", "来源", "证明", "引用", "evidence", "source", "why"),
    "delta": ("新增", "补证", "变化", "更新", "delta", "change", "new"),
    "timing": ("时间", "排期", "节奏", "窗口", "timeline", "schedule", "timing"),
}

_FIELD_FOCUS_GROUPS: dict[str, tuple[str, ...]] = {
    "executive_summary": ("evidence",),
    "consulting_angle": ("evidence",),
    "budget_signals": ("budget", "timing"),
    "tender_timeline": ("budget", "timing"),
    "project_distribution": ("budget", "timing"),
    "target_accounts": ("buyer",),
    "public_contact_channels": ("buyer",),
    "account_team_signals": ("buyer",),
    "target_departments": ("buyer",),
    "competitor_profiles": ("competitor",),
    "competition_analysis": ("competitor",),
    "winner_peer_moves": ("competitor",),
    "ecosystem_partners": ("partner",),
    "benchmark_cases": ("partner",),
    "strategic_directions": ("partner", "evidence"),
    "leadership_focus": ("evidence",),
    "supplemental_context": ("delta",),
    "supplemental_evidence": ("delta", "evidence"),
    "supplemental_requirements": ("delta",),
    "followup_report_summary": ("delta",),
    "section_item": ("evidence",),
    "section_evidence": ("evidence",),
    "source": ("evidence",),
}


@dataclass(slots=True)
class ResearchRetrievalChunk:
    text: str
    label: str
    field_key: str
    source_title: str = ""
    source_url: str = ""
    source_tier: str = ""
    section_title: str = ""
    focus_groups: tuple[str, ...] = ()
    priority: int = 0
    evidence_links: list[dict[str, str]] = field(default_factory=list)

    def to_payload(self, *, score: int = 0) -> dict[str, Any]:
        return {
            "label": self.label,
            "field_key": self.field_key,
            "text": self.text,
            "source_title": self.source_title,
            "source_url": self.source_url,
            "source_tier": self.source_tier or "media",
            "section_title": self.section_title,
            "score": score,
            "evidence_links": list(self.evidence_links),
        }


def _dedupe_strings(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _question_terms(question: str) -> list[str]:
    normalized = normalize_text(question).lower()
    terms: list[str] = []
    for raw in _QUESTION_TERM_RE.findall(normalized):
        token = normalize_text(raw).lower()
        if not token or token in _QUESTION_STOPWORDS:
            continue
        terms.append(token)
        if _CJK_RE.match(token) and len(token) >= 4:
            for index in range(len(token) - 1):
                terms.append(token[index : index + 2])
    return _dedupe_strings(terms)


def _question_focus_groups(question: str) -> set[str]:
    normalized = normalize_text(question).lower()
    groups: set[str] = set()
    for group, hints in _FOCUS_GROUP_HINTS.items():
        if any(normalize_text(hint).lower() in normalized for hint in hints if normalize_text(hint)):
            groups.add(group)
    return groups


def _split_text_windows(text: str, *, max_chars: int = 220) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    sentences = _dedupe_strings(_SENTENCE_SPLIT_RE.split(normalized))
    if not sentences:
        return [normalized[:max_chars]]

    windows: list[str] = []
    current: list[str] = []
    current_length = 0
    for sentence in sentences:
        sentence_length = len(sentence)
        if current and current_length + sentence_length > max_chars:
            windows.append("；".join(current))
            current = [sentence]
            current_length = sentence_length
            continue
        current.append(sentence)
        current_length += sentence_length
    if current:
        windows.append("；".join(current))
    return _dedupe_strings(windows)


def _focus_groups_for_field(field_key: str, *, section_title: str = "") -> tuple[str, ...]:
    groups = list(_FIELD_FOCUS_GROUPS.get(field_key, ()))
    lowered_section = normalize_text(section_title).lower()
    if any(token in lowered_section for token in ("甲方", "客户", "buyer")):
        groups.append("buyer")
    if any(token in lowered_section for token in ("预算", "招标", "采购", "timeline", "时间")):
        groups.extend(["budget", "timing"])
    if any(token in lowered_section for token in ("竞品", "竞争", "competitor")):
        groups.append("competitor")
    if any(token in lowered_section for token in ("伙伴", "生态", "partner")):
        groups.append("partner")
    if any(token in lowered_section for token in ("证据", "来源", "evidence")):
        groups.append("evidence")
    return tuple(_dedupe_strings(groups))


def _focus_groups_from_text(text: str) -> tuple[str, ...]:
    normalized = normalize_text(text).lower()
    groups: list[str] = []
    for group, hints in _FOCUS_GROUP_HINTS.items():
        if any(normalize_text(hint).lower() in normalized for hint in hints if normalize_text(hint)):
            groups.append(group)
    return tuple(_dedupe_strings(groups))


def _collect_report_evidence_links(report: dict[str, Any]) -> list[dict[str, str]]:
    evidence_links: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for section in list(report.get("sections") or []):
        if not isinstance(section, dict):
            continue
        for raw_link in list(section.get("evidence_links") or []):
            if not isinstance(raw_link, dict):
                continue
            url = normalize_text(str(raw_link.get("url") or ""))
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            evidence_links.append(
                {
                    "title": normalize_text(str(raw_link.get("title") or url)) or url,
                    "url": url,
                    "meta": " / ".join(
                        part
                        for part in [
                            normalize_text(str(raw_link.get("source_tier") or "media")) or "media",
                            normalize_text(str(raw_link.get("source_label") or "")),
                        ]
                        if part
                    ),
                }
            )
    for source in list(report.get("sources") or []):
        if not isinstance(source, dict):
            continue
        url = normalize_text(str(source.get("url") or ""))
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        evidence_links.append(
            {
                "title": normalize_text(str(source.get("title") or url)) or url,
                "url": url,
                "meta": " / ".join(
                    part
                    for part in [
                        normalize_text(str(source.get("source_tier") or "media")) or "media",
                        normalize_text(str(source.get("source_type") or "web")) or "web",
                    ]
                    if part
                ),
            }
        )
    return evidence_links


def _append_chunk(
    chunks: list[ResearchRetrievalChunk],
    seen: set[str],
    *,
    text: str,
    label: str,
    field_key: str,
    source_title: str = "",
    source_url: str = "",
    source_tier: str = "",
    section_title: str = "",
    evidence_links: list[dict[str, str]] | None = None,
    priority: int = 0,
) -> None:
    for window in _split_text_windows(text):
        dedupe_key = normalize_text(" | ".join([field_key, section_title, source_url, window]))
        if not dedupe_key or dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        chunks.append(
            ResearchRetrievalChunk(
                text=window,
                label=normalize_text(label) or field_key,
                field_key=field_key,
                source_title=normalize_text(source_title),
                source_url=normalize_text(source_url),
                source_tier=normalize_text(source_tier),
                section_title=normalize_text(section_title),
                focus_groups=tuple(
                    _dedupe_strings(
                        [
                            *_focus_groups_for_field(field_key, section_title=section_title),
                            *_focus_groups_from_text(window),
                        ]
                    )
                ),
                priority=priority,
                evidence_links=list(evidence_links or []),
            )
        )


def build_report_retrieval_chunks(report: dict[str, Any] | None) -> list[ResearchRetrievalChunk]:
    if not isinstance(report, dict):
        return []

    chunks: list[ResearchRetrievalChunk] = []
    seen: set[str] = set()
    global_evidence_links = _collect_report_evidence_links(report)

    _append_chunk(
        chunks,
        seen,
        text=str(report.get("executive_summary") or ""),
        label="执行摘要",
        field_key="executive_summary",
        priority=9,
    )
    _append_chunk(
        chunks,
        seen,
        text=str(report.get("consulting_angle") or ""),
        label="咨询视角",
        field_key="consulting_angle",
        priority=7,
    )

    followup_context = report.get("followup_context")
    if isinstance(followup_context, dict):
        for field_key, label, priority in (
            ("followup_report_summary", "上一版执行摘要", 7),
            ("supplemental_context", "人工补充新信息", 8),
            ("supplemental_evidence", "人工补充新证据/待核验线索", 14),
            ("supplemental_requirements", "人工补充新需求", 8),
        ):
            _append_chunk(
                chunks,
                seen,
                text=str(followup_context.get(field_key) or ""),
                label=label,
                field_key=field_key,
                evidence_links=global_evidence_links[:2],
                priority=priority,
            )

    field_specs = (
        ("budget_signals", "预算线索", 10),
        ("tender_timeline", "时间节点", 10),
        ("project_distribution", "项目分布", 8),
        ("target_accounts", "重点甲方", 9),
        ("public_contact_channels", "公开联系入口", 9),
        ("account_team_signals", "团队信号", 8),
        ("target_departments", "组织入口", 8),
        ("competitor_profiles", "竞品画像", 8),
        ("competition_analysis", "竞争判断", 7),
        ("winner_peer_moves", "中标方动态", 7),
        ("ecosystem_partners", "生态伙伴", 8),
        ("benchmark_cases", "标杆案例", 6),
        ("strategic_directions", "行动方向", 6),
        ("leadership_focus", "高层关注点", 5),
    )
    for field_key, label, priority in field_specs:
        values = report.get(field_key)
        if not isinstance(values, list):
            continue
        for value in values:
            _append_chunk(
                chunks,
                seen,
                text=str(value or ""),
                label=label,
                field_key=field_key,
                priority=priority,
            )

    for section in list(report.get("sections") or []):
        if not isinstance(section, dict):
            continue
        section_title = normalize_text(str(section.get("title") or "章节"))
        evidence_links: list[dict[str, str]] = []
        for raw_link in list(section.get("evidence_links") or []):
            if not isinstance(raw_link, dict):
                continue
            url = normalize_text(str(raw_link.get("url") or ""))
            if not url:
                continue
            evidence_links.append(
                {
                    "title": normalize_text(str(raw_link.get("title") or url)) or url,
                    "url": url,
                    "meta": " / ".join(
                        part
                        for part in [
                            normalize_text(str(raw_link.get("source_tier") or "media")) or "media",
                            normalize_text(str(raw_link.get("source_label") or "")),
                        ]
                        if part
                    ),
                }
            )
            _append_chunk(
                chunks,
                seen,
                text="；".join(
                    part
                    for part in [
                        str(raw_link.get("anchor_text") or ""),
                        str(raw_link.get("excerpt") or ""),
                        str(raw_link.get("title") or ""),
                    ]
                    if normalize_text(str(part or ""))
                ),
                label=f"{section_title} 证据",
                field_key="section_evidence",
                source_title=str(raw_link.get("title") or ""),
                source_url=url,
                source_tier=str(raw_link.get("source_tier") or ""),
                section_title=section_title,
                evidence_links=[evidence_links[-1]],
                priority=12 if normalize_text(str(raw_link.get("source_tier") or "")) == "official" else 10,
            )
        for item in list(section.get("items") or []):
            _append_chunk(
                chunks,
                seen,
                text=str(item or ""),
                label=section_title,
                field_key="section_item",
                section_title=section_title,
                evidence_links=evidence_links[:2],
                priority=8,
            )

    for source in list(report.get("sources") or []):
        if not isinstance(source, dict):
            continue
        source_url = normalize_text(str(source.get("url") or ""))
        source_title = normalize_text(str(source.get("title") or ""))
        snippet = normalize_text(str(source.get("snippet") or ""))
        evidence = []
        if source_url:
            evidence.append(
                {
                    "title": source_title or source_url,
                    "url": source_url,
                    "meta": " / ".join(
                        part
                        for part in [
                            normalize_text(str(source.get("source_tier") or "media")) or "media",
                            normalize_text(str(source.get("source_type") or "web")),
                        ]
                        if part
                    ),
                }
            )
        _append_chunk(
            chunks,
            seen,
            text="；".join(part for part in [source_title, snippet] if part),
            label="来源摘要",
            field_key="source",
            source_title=source_title,
            source_url=source_url,
            source_tier=str(source.get("source_tier") or ""),
            evidence_links=evidence,
            priority=6,
        )

    return chunks


def _chunk_score(
    chunk: ResearchRetrievalChunk,
    *,
    normalized_question: str,
    question_terms: list[str],
    focus_groups: set[str],
) -> int:
    haystack = normalize_text(" ".join([chunk.label, chunk.section_title, chunk.source_title, chunk.text])).lower()
    if not haystack:
        return 0

    overlap = sum(1 for term in question_terms if term and term in haystack)
    focus_overlap = len(set(chunk.focus_groups) & focus_groups)
    score = chunk.priority + overlap * 6 + focus_overlap * 9

    if normalized_question and normalized_question in haystack:
        score += 12
    if chunk.source_tier == "official":
        score += 4
    if chunk.source_url:
        score += 2
    if len(chunk.text) >= 40:
        score += 2
    if "delta" in focus_groups and chunk.field_key.startswith("supplemental_"):
        score += 10
    if "evidence" in focus_groups and chunk.field_key in {"section_evidence", "source"}:
        score += 8
    if overlap == 0 and focus_overlap == 0 and chunk.priority < 8:
        score -= 8
    return score


def retrieve_report_evidence_chunks(
    question: str,
    report: dict[str, Any] | None,
    *,
    limit: int = 4,
) -> list[dict[str, Any]]:
    chunks = build_report_retrieval_chunks(report)
    if not chunks:
        return []

    normalized_question = normalize_text(question).lower()
    question_terms = _question_terms(question)
    focus_groups = _question_focus_groups(question)
    scored = [
        (chunk, _chunk_score(chunk, normalized_question=normalized_question, question_terms=question_terms, focus_groups=focus_groups))
        for chunk in chunks
    ]
    ranked = sorted(
        scored,
        key=lambda item: (
            item[1],
            1 if item[0].source_tier == "official" else 0,
            len(item[0].evidence_links),
            len(item[0].text),
        ),
        reverse=True,
    )

    selected: list[dict[str, Any]] = []
    seen_texts: set[str] = set()
    for chunk, score in ranked:
        if score <= 0:
            continue
        normalized_text = normalize_text(chunk.text)
        if not normalized_text or normalized_text in seen_texts:
            continue
        seen_texts.add(normalized_text)
        selected.append(chunk.to_payload(score=score))
        if len(selected) >= limit:
            break
    return selected
